"""
Backend API the web app calls.

  pip install fastapi uvicorn joblib scikit-learn pandas ftfy   (+ transformers torch for DistilBERT)
  uvicorn app:app --reload
  POST http://localhost:8000/check   {"text": "subject + email content", "sender": "optional@address"}
  http://localhost:8000              the web page (frontend/)

How a check works:
  - the MODEL reads only the email content (subject + body) and gives a scam probability.
    It uses ./scam_model (DistilBERT) if present and torch is installed, otherwise
    baseline_model.joblib.
  - RULE-BASED CHECKS look for warning signs in the sender address, the links and the
    wording, including a lookalike-domain check against official_domains.txt.
  - a lookalike sender or link makes the result High; otherwise each warning sign adds
    a little to the model's probability before the Low / Medium / High cut-offs.
email_features.py, domain_check.py and official_domains.txt must sit next to this file.
Explanations are template-based, so the prototype needs no paid API.
"""
import os
import re

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import email_features as ef
from domain_check import PROTECTED_SUFFIXES

MODEL_DIR = os.environ.get("SCAM_MODEL_DIR", "scam_model")
BASELINE_PATH = os.environ.get("BASELINE_MODEL", "baseline_model.joblib")

MAX_TEXT_CHARS = 20_000

# Low / Medium / High cut-offs on (model probability + SIGN_WEIGHT per warning sign).
# DistilBERT's cut-offs were chosen on the validation split (tune_thresholds.py,
# PROJECT_CONTEXT.md section 5e). The baseline scores many genuine modern emails 0.2-0.5,
# so it keeps the higher Medium cut-off.
HIGH_CUTOFF, SIGN_WEIGHT = 0.7, 0.05
MEDIUM_CUTOFFS = {"distilbert": 0.2, "baseline": 0.4}

# ---------- load the classifier ----------
MODEL_USED = None
if os.path.isdir(MODEL_DIR):
    try:
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer
        _tok = AutoTokenizer.from_pretrained(MODEL_DIR)
        _model = AutoModelForSequenceClassification.from_pretrained(MODEL_DIR).eval()

        def scam_probability(body: str) -> float:
            enc = _tok(body, truncation=True, max_length=256, return_tensors="pt")
            with torch.no_grad():
                probs = torch.softmax(_model(**enc).logits, dim=-1)[0]
            return float(probs[1])          # index 1 = "scam"
        MODEL_USED = "distilbert"
    except ImportError as e:            # torch / transformers not installed: use the baseline
        print(f"Found {MODEL_DIR} but could not load it ({e}); using {BASELINE_PATH} instead.")

if MODEL_USED is None:
    import joblib
    _clf = joblib.load(BASELINE_PATH)

    def scam_probability(body: str) -> float:
        return float(_clf.predict_proba([body])[0][1])
    MODEL_USED = "baseline"
MEDIUM_CUTOFF = MEDIUM_CUTOFFS[MODEL_USED]

# ---------- rule-based warning signs (produce the reasons users see) ----------
URL_RE = re.compile(r"https?://[^\s<>\"')]+", re.I)
URGENCY = ["urgent", "immediately", "within 24 hours", "suspended", "verify your",
           "final notice", "act now", "account will be", "locked"]
MONEY = ["gift card", "bitcoin", "crypto", "refund", "payment", "bank details",
         "wire", "fee", "overdue"]
CREDENTIALS = ["password", "sign in", "log in", "login", "confirm your details", "security code"]
# Genuine emails often say "we will never ask for your password"; that is not a request
SAFE_CREDENTIAL_PHRASES = re.compile(r"(never|not|won't|will not|don't|do not) (ever )?"
                                     r"(ask|request|provide|share|give|send|disclose)[^.]{0,40}"
                                     r"(password|log ?in|sign in|security code|netcode|pin)")
GOV_WORDS = ("ato", "mygov", "centrelink", "medicare", "home affairs")
# Scam types the model misses because the training data has few examples of them
# (PROJECT_CONTEXT 5b, 5e): investment, job and gift-card payment scams.
INVESTMENT = re.compile(r"guaranteed (returns?|profits?|income)|risk[- ]free (investment|returns?|profit)"
                        r"|crypto(currency)? (trading|investment|platform)|trading (platform|bot|signals?)"
                        r"|double your (money|investment)|investment opportunity|passive income"
                        r"|returns? of \d+ ?%|(made|earned|making|earning) \$[\d,]+ (last|this|a|per|in) "
                        r"(week|month|day)|account manager will guide")
JOB = re.compile(r"(earn|make|paid) (up to )?\$[\d,]+ ?(/|per|a|an|each) ?(day|week|hour|task)"
                 r"|work (from|at) home[^.]{0,60}(earn|\$)|no experience (needed|required|necessary)"
                 r"|(rating|reviewing|liking) (products|videos|hotels|apps)|task[- ]based (job|work)")
OFF_PLATFORM = re.compile(r"(message|contact|text|add|chat with|reach) (us|me|our( [a-z]+){1,2})? ?(on|via) "
                          r"(whatsapp|telegram|signal|wechat)")
GIFT_CARD_PAYMENT = re.compile(r"(pay|paid|payment|purchase|buy)[^.]{0,40}gift ?cards?|gift ?card (codes?|numbers?)")
PRIZE = re.compile(r"you('ve| have) (won|been selected)|congratulations[^.]{0,40}(won|winner|selected)"
                   r"|claim your (prize|reward|winnings|voucher)|lottery winner")
# Family-emergency ("Hi Mum") scams: a new number, or a claim to be a relative plus a money request
RELATIVE = r"(son|daughter|mum|mom|dad|grandson|granddaughter|grandma|grandpa|nephew|niece|brother|sister)"
MONEY_ASK = r"(need|send|transfer|lend|borrow|pay)\b[^.]{0,40}(\$\s?\d[\d,]*|money|cash|funds)"
FAMILY = re.compile(r"\b(hi|hey) (mum|mom|dad)\b[^.]{0,80}(new number|broke|lost)|this is my new number"
                    r"|my (old )?phone (is |got )?(broken|broke|lost|died)[^.]{0,80}(new number|this number)"
                    rf"|\b(it'?s|this is|its) (me,? )?(your |ur )?{RELATIVE}\b[\s\S]{{0,150}}{MONEY_ASK}"
                    rf"|(^|\b(hi|hey) )(mum|mom|dad|grandma|grandpa)\b[\s\S]{{0,150}}{MONEY_ASK}")
EMERGENCY = r"(emergency|urgent(ly)?|asap|right now|immediately|today|in trouble|hospital|arrested)"
URGENT_MONEY = re.compile(rf"{MONEY_ASK}[\s\S]{{0,100}}\b{EMERGENCY}\b|\b{EMERGENCY}\b[\s\S]{{0,100}}{MONEY_ASK}")
# Asking for a password or PIN to be sent back: genuine organisations never do this by email
SECRET_REQUEST = re.compile(r"\b(reply|respond|send|provide|tell us|give us)\b[^.=\n]{0,60}"
                            r"\b(password|passcode|pin|security code|netcode|one[- ]time code|card number)\b")
LOOKALIKE_FLAGS = {"lookalike_link", "lookalike_sender"}
# Each of these is a strong sign on its own: at least Medium, and two together make High.
STRONG_FLAGS = {"investment", "job", "off_platform", "gift_card_payment", "prize", "family_impersonation",
                "secret_request", "urgent_money"}


def link_hosts(text: str) -> list[str]:
    """Web addresses (host names) of the links in the text."""
    return [re.split(r"[/?#:]", re.sub(r"^https?://", "", url.lower()))[0] for url in URL_RE.findall(text)]


def is_official(domain: str) -> bool:
    """On the official allowlist, or an ending only government / education bodies can register."""
    return (any(domain == s or domain.endswith("." + s) for s in PROTECTED_SUFFIXES)
            or ef.check_domain(domain)["verdict"] == "official")


# Internet providers' customer mail: anyone with an internet plan can get one of these exact
# addresses (the providers' own staff and notices use other domains or subdomains)
ISP_MAIL = {"telstra.com", "optushome.com.au", "iinet.net.au", "tpg.com.au", "internode.on.net",
            "dodo.com.au", "westnet.com.au", "adam.com.au", "ozemail.com.au"}


def official_sender(text: str, sender: str, found: dict) -> str:
    """The sender's domain if it is an organisation's real address and nothing in the email
    contradicts it (every link goes to an official website, no lookalike or strong scam sign).
    Personal mail never counts: anyone can get an outlook.com, icloud.com or telstra.com address."""
    if (LOOKALIKE_FLAGS | STRONG_FLAGS | {"raw_ip_link"}) & found.keys():
        return ""
    addr = ef.parse_address(sender)
    if not addr:
        return ""
    domain = addr.split("@")[1]
    if (domain in ISP_MAIL or any(domain == w or domain.endswith("." + w) for w in ef.FREE_WEBMAIL)
            or not is_official(domain)):
        return ""
    return domain if all(is_official(h) for h in link_hosts(text)) else ""


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
    t_requests = SAFE_CREDENTIAL_PHRASES.sub("", t)
    if any(k in t_requests for k in CREDENTIALS):
        add("credentials", "It asks you to sign in or share login details.")
    if SECRET_REQUEST.search(t_requests):
        add("secret_request", "It asks you to send a password, PIN or code. Real organisations never "
                              "ask for these by email.")
    if GIFT_CARD_PAYMENT.search(t):
        add("gift_card_payment", "It asks for payment with gift cards. Real organisations never do this.")
    if INVESTMENT.search(t):
        add("investment", "It promises easy or guaranteed money from investing, a sign of investment scams.")
    if JOB.search(t):
        add("job", "It offers easy money for simple work, a sign of job scams.")
    if OFF_PLATFORM.search(t):
        add("off_platform", "It asks you to continue the conversation on WhatsApp, Telegram or a similar app.")
    if PRIZE.search(t):
        add("prize", "It says you have won or been selected for a prize, a common scam hook.")
    if FAMILY.search(t):
        add("family_impersonation", "It claims to be a family member who needs money or has a new number. "
                                    "Call them on the number you already have before doing anything.")
    if URGENT_MONEY.search(t):
        add("urgent_money", "It asks for money urgently, a pressure tactic common in scams.")
    for host in link_hosts(text):
        if re.fullmatch(r"[\d.]+", host):
            add("raw_ip_link", "A link goes to a raw number address instead of a website name.")
            continue
        d = ef.check_domain(host)
        if d["verdict"] == "lookalike":
            add("lookalike_link", f"A link goes to '{host}', which imitates the real address "
                                  f"{d['imitates']}.")
    addr = ef.parse_address(sender)
    if addr:
        domain = addr.split("@")[1]
        f = ef.sender_features(addr)
        if f["lookalike_domain"]:
            add("lookalike_sender", f"The sender's address ('{domain}') imitates the real address "
                                    f"{ef.check_domain(domain)['imitates']}.")
        elif any(re.search(rf"\b{w}\b", t) for w in GOV_WORDS) and not domain.endswith(".gov.au"):
            add("fake_gov_sender", f"It claims to be from government but was sent from '{domain}'.")
        if f["suspicious_domain_ending"]:
            add("suspicious_domain_ending",
                f"The sender's domain ending (.{domain.rsplit('.', 1)[1]}) is common in scams.")
        if f["free_webmail"] and any(w in t for w in ("bank", "account", "government", "invoice")):
            add("official_from_webmail",
                "An official-sounding message was sent from a free personal email account.")
    return found


def risk_level(p: float, n_signals: int, lookalike: bool = False, n_strong: int = 0) -> str:
    # A sender or link imitating a known organisation's address is treated as High on its
    # own: genuine organisations do not send from lookalike addresses.
    if lookalike or n_strong >= 2:
        return "High"
    score = min(1.0, p + SIGN_WEIGHT * n_signals)
    if score >= HIGH_CUTOFF:
        return "High"
    # A strong sign (investment, job, gift-card payment ...) is never Low, because the model
    # has seen too few of these scams to score them reliably.
    if score >= MEDIUM_CUTOFF or n_strong:
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
    p = scam_probability(body)             # model: email content only
    found = signals(email.text, sender)    # rules read the original text (links intact)
    level = risk_level(p, len(found), lookalike=bool(LOOKALIKE_FLAGS & found.keys()),
                       n_strong=len(STRONG_FLAGS & found.keys()))
    # The model flags many genuine bank and government emails, because its training data has
    # almost none. A real official sender with only official links lowers High to Medium, never
    # to Low: the address the user typed can't be verified and could be forged.
    official = official_sender(email.text, sender, found)
    if official and level == "High":
        level = "Medium"
        found["official_sender"] = (f"The sender's address ({official}) is a real official address and "
                                    "its links go to official websites, so it may be genuine. But "
                                    "addresses can be faked: check in the official app or website "
                                    "before you act.")
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
