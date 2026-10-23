"""
Backend API the web app calls.

  pip install fastapi uvicorn joblib scikit-learn pandas ftfy   (+ transformers torch for DistilBERT)
  uvicorn app:app --reload
  POST http://localhost:8000/check   {"text": "subject + email content", "sender": "optional@address"}
  http://localhost:8000              the web page (frontend/)

Uses ./scam_model (DistilBERT) if present and torch is installed, otherwise baseline_model.joblib.
email_features.py must sit next to this file: it cleans the pasted text and turns the
sender address into warning signs exactly as during training.
Explanations are template-based, so the prototype needs no paid API.
"""
import os
import re

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import email_features as ef

MODEL_DIR = os.environ.get("SCAM_MODEL_DIR", "scam_model")
BASELINE_PATH = os.environ.get("BASELINE_MODEL", "baseline_model.joblib")

MAX_TEXT_CHARS = 20_000

# ---------- load the classifier ----------
MODEL_USED = None
if os.path.isdir(MODEL_DIR):
    try:
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer
        _tok = AutoTokenizer.from_pretrained(MODEL_DIR)
        _model = AutoModelForSequenceClassification.from_pretrained(MODEL_DIR).eval()
        # Models saved by the current train_distilbert.py read (sender description, body)
        # pairs and include input_format.json; older ones read the body only.
        _PAIR_INPUT = os.path.exists(os.path.join(MODEL_DIR, "input_format.json"))

        def scam_probability(body: str, sender: str) -> float:
            if _PAIR_INPUT:
                enc = _tok(ef.sender_description(sender), body, truncation="only_second",
                           max_length=256, return_tensors="pt")
            else:
                enc = _tok(body, truncation=True, max_length=256, return_tensors="pt")
            with torch.no_grad():
                probs = torch.softmax(_model(**enc).logits, dim=-1)[0]
            return float(probs[1])          # index 1 = "scam"
        MODEL_USED = "distilbert" if _PAIR_INPUT else "distilbert (body only)"
    except ImportError as e:            # torch / transformers not installed: use the baseline
        print(f"Found {MODEL_DIR} but could not load it ({e}); using {BASELINE_PATH} instead.")

if MODEL_USED is None:
    import joblib
    import pandas as pd
    _clf = joblib.load(BASELINE_PATH)

    def scam_probability(body: str, sender: str) -> float:
        row = pd.DataFrame({"email_address": [sender], "body": [body]})
        return float(_clf.predict_proba(row)[0][1])
    MODEL_USED = "baseline"

# ---------- rule-based warning signs (produce the reasons users see) ----------
URL_RE = re.compile(r"https?://[^\s<>\"')]+", re.I)
TRUSTED = {"ato", "mygov", "auspost", "centrelink", "servicesaustralia", "commbank",
           "westpac", "anz", "nab", "rmit", "homeaffairs"}
URGENCY = ["urgent", "immediately", "within 24 hours", "suspended", "verify your",
           "final notice", "act now", "account will be", "locked"]
MONEY = ["gift card", "bitcoin", "crypto", "refund", "payment", "bank details",
         "wire", "fee", "overdue"]
CREDENTIALS = ["password", "sign in", "log in", "login", "confirm your details", "security code"]
GOV_WORDS = ("ato", "mygov", "centrelink", "medicare", "home affairs")


def signals(text: str, sender: str) -> dict[str, str]:
    """Warning signs found, as {flag: reason shown to the user}, in the order found."""
    t = text.lower()
    found = {}

    def add(flag, reason):
        if reason not in found.values():
            found.setdefault(flag, reason)

    if any(k in t for k in URGENCY):
        add("urgency", "It pressures you to act quickly, a common scam tactic.")
    if any(k in t for k in MONEY):
        add("money", "It mentions money, refunds or payment.")
    if any(k in t for k in CREDENTIALS):
        add("credentials", "It asks you to sign in or share login details.")
    for url in URL_RE.findall(text):
        host = re.sub(r"^https?://", "", url.lower()).split("/")[0]
        if re.fullmatch(r"[\d.]+(:\d+)?", host):
            add("raw_ip_link", "A link goes to a raw number address instead of a website name.")
        elif any(b in host for b in TRUSTED) and not host.endswith((".gov.au", ".com.au", ".edu.au")):
            add("lookalike_link", f"A link mentions a trusted brand but goes to '{host}'.")
    addr = ef.parse_address(sender)
    if addr:
        domain = addr.split("@")[1]
        f = ef.sender_features(addr)
        if any(re.search(rf"\b{w}\b", t) for w in GOV_WORDS) and not domain.endswith(".gov.au"):
            add("fake_gov_sender", f"It claims to be from government but was sent from '{domain}'.")
        if f["brand_on_unofficial_domain"]:
            add("brand_sender", f"The sender uses a well-known brand name on an unofficial domain ('{domain}').")
        if f["suspicious_domain_ending"]:
            add("suspicious_domain_ending",
                f"The sender's domain ending (.{domain.rsplit('.', 1)[1]}) is common in scams.")
        if f["free_webmail"] and any(w in t for w in ("bank", "account", "government", "invoice")):
            add("official_from_webmail",
                "An official-sounding message was sent from a free personal email account.")
    return found


def risk_level(p: float, n_signals: int) -> str:
    # Placeholder thresholds: tune these on validation data in the evaluation phase.
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
    # subject + email content (pasted, or extracted from a screenshot)
    text: str = Field(min_length=1, max_length=MAX_TEXT_CHARS)
    sender: str | None = Field(default=None, max_length=320)


@app.post("/check")
def check(email: EmailIn):
    sender = email.sender or ""
    body = ef.clean_text(email.text)       # same cleaning as the training data
    if not body:
        raise HTTPException(status_code=422, detail="The email text is empty.")
    p = scam_probability(body, sender)
    found = signals(email.text, sender)    # rules read the original text (links intact)
    level = risk_level(p, len(found))
    return {
        "risk_level": level,
        "scam_probability": round(p, 3),
        "reasons": list(found.values()) or ["The wording resembles scam emails the model was trained on."
                                            if p >= 0.5 else "No specific warning signs detected."],
        "flags": list(found),
        "next_steps": NEXT_STEPS[level],
        "model": MODEL_USED,
    }


# Serve the web page too, so http://localhost:8000 opens the app (registered after /check).
_FRONTEND = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend")
if os.path.isdir(_FRONTEND):
    app.mount("/", StaticFiles(directory=_FRONTEND, html=True), name="frontend")
