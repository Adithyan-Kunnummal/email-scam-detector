"""
Step 3: Backend API the web app calls.

  pip install fastapi uvicorn joblib scikit-learn        (+ transformers torch if using DistilBERT)
  uvicorn app:app --reload
  POST http://localhost:8000/check   {"text": "...", "sender": "optional@address"}

Uses ./scam_model (DistilBERT) if present, otherwise baseline_model.joblib.
Explanations are template-based so the prototype needs no paid API
(the spec says markers must be able to run it without paid subscriptions).
"""
import os
import re

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# ---------- load the classifier ----------
if os.path.isdir("scam_model"):
    from transformers import pipeline
    _clf = pipeline("text-classification", model="scam_model", truncation=True, max_length=256)

    def scam_probability(text: str) -> float:
        out = _clf(text, top_k=None)
        return next(o["score"] for o in out if o["label"] == "scam")
    MODEL_USED = "distilbert"
else:
    import joblib
    _clf = joblib.load("baseline_model.joblib")

    def scam_probability(text: str) -> float:
        return float(_clf.predict_proba([text])[0][1])
    MODEL_USED = "baseline"

# ---------- simple rule-based signals ----------
URL_RE = re.compile(r"https?://[^\s<>\"')]+", re.I)
TRUSTED = {"ato", "mygov", "auspost", "centrelink", "servicesaustralia", "commbank",
           "westpac", "anz", "nab", "rmit", "homeaffairs"}
URGENCY = ["urgent", "immediately", "within 24 hours", "suspended", "verify your",
           "final notice", "act now", "account will be", "locked"]
MONEY = ["gift card", "bitcoin", "crypto", "refund", "payment", "bank details",
         "wire", "fee", "overdue"]
CREDENTIALS = ["password", "sign in", "log in", "login", "confirm your details", "security code"]


def signals(text: str, sender: str | None) -> list[str]:
    t = text.lower()
    found = []
    if any(k in t for k in URGENCY):
        found.append("It pressures you to act quickly, a common scam tactic.")
    if any(k in t for k in MONEY):
        found.append("It mentions money, refunds or payment.")
    if any(k in t for k in CREDENTIALS):
        found.append("It asks you to sign in or share login details.")
    for url in URL_RE.findall(text):
        host = re.sub(r"^https?://", "", url.lower()).split("/")[0]
        if re.fullmatch(r"[\d.]+(:\d+)?", host):
            found.append("A link goes to a raw number address instead of a website name.")
        elif any(b in host for b in TRUSTED) and not host.endswith((".gov.au", ".com.au", ".edu.au")):
            found.append(f"A link mentions a trusted brand but goes to '{host}'.")
    if sender and "@" in sender:
        domain = sender.lower().split("@")[-1]
        if any(b in t for b in ("ato", "mygov", "centrelink")) and not domain.endswith(".gov.au"):
            found.append(f"It claims to be from government but was sent from '{domain}'.")
    return list(dict.fromkeys(found))  # de-duplicate, keep order


def risk_level(p: float, n_signals: int) -> str:
    # Placeholder thresholds: tune these on your validation set in the evaluation phase.
    score = min(1.0, p + 0.05 * n_signals)
    if score >= 0.7:
        return "High"
    if score >= 0.4:
        return "Medium"
    return "Low"


NEXT_STEPS = {
    "High": ["Don't click links, open attachments or reply.",
             "Contact the organisation through its official app or website.",
             "Report it to Scamwatch (scamwatch.gov.au) and delete it."],
    "Medium": ["Don't click links in this email.",
               "Check with the organisation directly using contact details you already trust."],
    "Low": ["No strong warning signs found, but stay careful with links and payment requests."],
}

# ---------- API ----------
app = FastAPI(title="Scam email checker")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class EmailIn(BaseModel):
    text: str
    sender: str | None = None


@app.post("/check")
def check(email: EmailIn):
    p = scam_probability(email.text)
    reasons = signals(email.text, email.sender)
    level = risk_level(p, len(reasons))
    return {
        "risk_level": level,
        "scam_probability": round(p, 3),
        "reasons": reasons or ["The wording resembles scam emails the model was trained on."
                               if p >= 0.5 else "No specific warning signs detected."],
        "next_steps": NEXT_STEPS[level],
        "model": MODEL_USED,
    }
