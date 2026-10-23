"""
Shared email processing for the scam email checker.

Used by prepare_data.py, train_baseline.py, train_distilbert.py and app.py, so
training data and emails pasted into the app are processed in exactly the same way.

Dataset format (data.csv):
    email_address  sender's email address, e.g. "alerts@mygov-secure.xyz" (may be blank)
    body           subject + email content, already cleaned with clean_text()
    label          "scam" or "not scam"

Why the address is turned into general warning signs instead of being given to
the model as-is: in the public datasets, legitimate senders are mostly a few
organisations and mailing lists (enron.com, samba.org, python.org ...). A model
fed raw domains learns "enron.com = safe", which says nothing about the emails
our users receive. Features like "free webmail" or "random-looking name" carry
over to any sender.
"""
import re
from email.header import decode_header, make_header
from email.utils import parseaddr

import numpy as np

# ---------------------------------------------------------------- labels
LABEL_SCAM, LABEL_NOT_SCAM = "scam", "not scam"


def to_binary_label(value) -> int:
    """'scam' / 'not scam' (or 1 / 0) -> 1 / 0."""
    v = str(value).strip().lower().replace("_", " ").replace("-", " ")
    if v in {"scam", "1", "1.0", "phishing", "fraud"}:
        return 1
    if v in {"not scam", "0", "0.0", "legit", "legitimate", "ham", "safe"}:
        return 0
    raise ValueError(f"Unrecognised label: {value!r}")


# ---------------------------------------------------------------- loading a dataset
REQUIRED_COLUMNS = ("email_address", "body", "label")


def load_dataset(path, clean=True, min_chars=20, verbose=True):
    """Read any CSV with columns email_address, body, label and prepare it for training.

    - column names are matched ignoring case and surrounding spaces; extra columns are ignored
    - email_address may be blank or in "Name <address>" form
    - label may be scam / not scam (also 1 / 0, phishing, fraud, legit, legitimate, ham, safe)
    - body is cleaned with clean_text() unless clean=False, so training text matches what
      app.py sees; running it on already-cleaned text is harmless
    - rows with a body under `min_chars` characters and duplicate bodies are dropped
    Returns a DataFrame with email_address, body, label (original text) and y (1 = scam, 0 = not).
    """
    import pandas as pd
    df = pd.read_csv(path, keep_default_na=False, dtype=str, encoding_errors="replace")
    df.columns = [c.strip().lower() for c in df.columns]
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise SystemExit(f"{path} is missing column(s): {', '.join(missing)}. "
                         f"Found: {', '.join(df.columns)}. Expected: {', '.join(REQUIRED_COLUMNS)}.")
    df = df[list(REQUIRED_COLUMNS)].copy()
    bad = sorted({v for v in df["label"].unique() if _label_or_none(v) is None})
    if bad:
        raise SystemExit(f"{path}: unrecognised label value(s) {bad[:10]}. "
                         f"Use 'scam' / 'not scam' (or 1 / 0).")
    df["y"] = df["label"].map(to_binary_label)
    df["email_address"] = df["email_address"].str.strip()
    n0 = len(df)
    if clean:
        df["body"] = df["body"].map(clean_text)
    df = df[df["body"].str.len() >= min_chars]
    n1 = len(df)
    df = df.drop_duplicates(subset="body").reset_index(drop=True)
    if verbose:
        print(f"{path}: {n0} rows -> {len(df)} used ({n0 - n1} too short, {n1 - len(df)} duplicates); "
              f"{int(df['y'].sum())} scam ({df['y'].mean():.0%}), {int((df['y'] == 0).sum())} not scam; "
              f"{(df['email_address'] != '').mean():.0%} with a sender address")
        if not 0.15 <= df["y"].mean() <= 0.85:
            print("  Warning: classes are very unbalanced; watch recall on the scam class.")
    return df


def _label_or_none(value):
    try:
        return to_binary_label(value)
    except ValueError:
        return None


# ---------------------------------------------------------------- body text
MIME_WORD = re.compile(r"=\?[\w-]+\?[bqBQ]\?[^?\s]*\?=")
EMAIL_ADDR = re.compile(r"[\w.+-]+@[\w-]+(\.[\w-]+)+")


def _decode_mime_words(s: str) -> str:
    """Decode encoded header text such as '=?utf-8?B?SGVsbG8=?=' to plain text."""
    def one(m):
        try:
            return str(make_header(decode_header(m.group(0))))
        except Exception:
            return m.group(0)
    return MIME_WORD.sub(one, s) if "=?" in s else s


def clean_text(s: str) -> str:
    """Clean subject + body text. Apply to training data AND to text users paste."""
    try:
        from ftfy import fix_text
    except ImportError:          # ftfy is optional at run time; only repairs garbled characters
        def fix_text(x):
            return x
    s = _decode_mime_words(str(s))
    s = fix_text(s)                                           # repair garbled encodings
    s = EMAIL_ADDR.sub("[email]", s)                          # mask addresses inside the text
    s = re.sub(r"\S*monkey\.org\S*", "", s, flags=re.I)       # Nazario collection domain (leakage)
    s = re.sub(r"\b(?:19[89]\d|20[0-3]\d)\b", "[year]", s)    # years reveal which era/source
    s = s.replace("\r\n", "\n").replace("\r", "\n").replace("\t", " ").replace("\xa0", " ")
    s = re.sub(r"([-=+*_~#.])(\s?\1){5,}", r"\1\1\1", s)      # shrink long divider lines
    s = re.sub(r"[ ]{2,}", " ", s)
    s = re.sub(r" *\n *", "\n", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def make_body(subject, content) -> str:
    """Combine subject and email content into one cleaned `body` string."""
    subject = "" if subject is None or str(subject) == "nan" else str(subject).strip()
    content = "" if content is None or str(content) == "nan" else str(content)
    return clean_text(f"{subject}\n\n{content}" if subject else content)


# ---------------------------------------------------------------- sender address
# Addresses that belong to the dataset collectors, not to the real sender
DATASET_ADDRESSES = re.compile(r"monkey\.org$|spamassassin\.taint\.org$", re.I)

FREE_WEBMAIL = {
    "gmail.com", "googlemail.com", "yahoo.com", "yahoo.co.uk", "yahoo.com.au", "yahoo.co.in",
    "yahoo.fr", "yahoo.de", "yahoo.co.kr", "ymail.com", "rocketmail.com", "hotmail.com",
    "hotmail.co.uk", "hotmail.fr", "outlook.com", "live.com", "msn.com", "aol.com", "mail.com",
    "gmx.com", "gmx.net", "gmx.de", "yandex.com", "yandex.ru", "mail.ru", "zoho.com",
    "protonmail.com", "proton.me", "icloud.com", "me.com", "qq.com", "163.com", "126.com",
    "rediffmail.com", "virgilio.it", "libero.it", "web.de", "bigpond.com", "optusnet.com.au",
}
SUSPICIOUS_TLDS = {
    "xyz", "top", "click", "link", "work", "loan", "online", "site", "club", "info", "biz",
    "ru", "cn", "tk", "ml", "ga", "cf", "gq", "pw", "su", "ws", "cc", "buzz", "rest", "icu",
}
# Brand -> its real domain endings. A brand word on any other domain is a warning sign.
BRANDS = {
    "mygov": ("my.gov.au", "gov.au"), "ato": ("ato.gov.au",), "centrelink": ("gov.au",),
    "medicare": ("gov.au",), "auspost": ("auspost.com.au",), "commbank": ("commbank.com.au", "cba.com.au"),
    "westpac": ("westpac.com.au",), "anz": ("anz.com", "anz.com.au"), "nab": ("nab.com.au",),
    "paypal": ("paypal.com", "paypal.com.au"), "apple": ("apple.com", "icloud.com"),
    "amazon": ("amazon.com", "amazon.com.au"), "netflix": ("netflix.com",),
    "microsoft": ("microsoft.com",), "linkedin": ("linkedin.com",), "dhl": ("dhl.com",),
    "fedex": ("fedex.com",), "linkt": ("linkt.com.au",), "telstra": ("telstra.com", "telstra.com.au"),
}


def parse_address(raw) -> str:
    """'Ann Garcia <AnGarcia@mcoe.org>' -> 'angarcia@mcoe.org'. Returns '' if none."""
    if raw is None or str(raw).strip() in {"", "nan"}:
        return ""
    addr = parseaddr(str(raw))[1].strip().lower()
    if not re.fullmatch(r"[^@\s]+@[\w-]+(\.[\w-]+)+", addr):
        return ""
    if DATASET_ADDRESSES.search(addr.split("@")[1]):
        return ""
    return addr


# Deliberately NOT used as features, because the public datasets make them misleading:
#  - "random-looking name": the CEAS 2008 organisers anonymised sender names in their
#    legitimate emails (e.g. vyjpfgjw@gmail.com), so the model would learn
#    "random-looking = legitimate", the opposite of reality.
#  - "many subdomains": in the data this is mostly university and mailing-list servers
#    (legitimate), but real phishing often uses subdomain tricks.
SENDER_FEATURES = [
    "has_sender", "free_webmail", "many_digits_in_name", "suspicious_domain_ending",
    "hyphen_or_digits_in_domain", "brand_on_unofficial_domain",
]


def sender_features(address) -> dict:
    """General warning signs from a sender address (0/1 each)."""
    addr = parse_address(address)
    f = dict.fromkeys(SENDER_FEATURES, 0)
    if not addr:
        return f
    local, domain = addr.split("@", 1)
    labels = domain.split(".")
    tokens = set(re.split(r"[.\-]", domain))
    f["has_sender"] = 1
    f["free_webmail"] = int(domain in FREE_WEBMAIL)
    f["many_digits_in_name"] = int(sum(c.isdigit() for c in local) >= 4)
    f["suspicious_domain_ending"] = int(labels[-1] in SUSPICIOUS_TLDS)
    f["hyphen_or_digits_in_domain"] = int(bool(re.search(r"[-\d]", ".".join(labels[:-1]))))
    f["brand_on_unofficial_domain"] = int(any(
        b in tokens and not any(domain == o or domain.endswith("." + o) for o in official)
        for b, official in BRANDS.items()))
    return f


def sender_matrix(addresses) -> np.ndarray:
    """For scikit-learn: list/Series of addresses -> (n, len(SENDER_FEATURES)) array."""
    if hasattr(addresses, "to_numpy"):
        addresses = addresses.to_numpy().ravel()
    return np.array([[sender_features(a)[k] for k in SENDER_FEATURES] for a in addresses], dtype=float)


def sender_feature_names(transformer=None, input_features=None):
    """Feature names for scikit-learn's FunctionTransformer(feature_names_out=...)."""
    return np.array(SENDER_FEATURES, dtype=object)


_PHRASES = {
    "free_webmail": "free webmail address",
    "many_digits_in_name": "many digits in name",
    "suspicious_domain_ending": "unusual domain ending",
    "hyphen_or_digits_in_domain": "hyphen or digits in domain",
    "brand_on_unofficial_domain": "brand name on an unofficial domain",
}


def sender_description(address) -> str:
    """For DistilBERT: a short, domain-free description of the sender."""
    f = sender_features(address)
    if not f["has_sender"]:
        return "sender not provided"
    signs = [p for k, p in _PHRASES.items() if f[k]]
    return "sender: " + ("; ".join(signs) if signs else "no warning signs")
