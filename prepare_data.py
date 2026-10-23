"""
Combine and clean the 11 curated phishing/spam email datasets
(Champa, Rabbi & Zibran, 2024) into a three-column training file.

Usage:
    pip install pandas ftfy
    python prepare_data.py <folder with the 11 CSVs> <output folder>

Outputs (in <output folder>):
    data.csv             email_address, body, label ("scam" / "not scam")
                         -> the training file for train_baseline.py and train_distilbert.py
    combined_clean.csv   every unique email: email_address, body, label, category, source
                         (category = scam | spam | legit)
    cleaning_report.txt  counts at every step
"""
import csv
import hashlib
import re
import sys
from pathlib import Path

import pandas as pd

from email_features import LABEL_NOT_SCAM, LABEL_SCAM, make_body, parse_address

csv.field_size_limit(sys.maxsize)
IN_DIR, OUT_DIR = Path(sys.argv[1]), Path(sys.argv[2])
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Order matters: when the same email appears in several files, the copy from the
# earliest file in this list is kept.
FILES = ["Nazario", "Nigerian_Fraud", "Nazario_5", "Nigerian_5", "SpamAssasin",
         "CEAS_08", "TREC_05", "TREC_06", "TREC_07", "Enron", "Ling"]
SCAM_SOURCES = {"Nazario", "Nigerian_Fraud", "Nazario_5", "Nigerian_5"}  # label 1 = phishing/fraud
PREPROCESSED_SOURCES = {"Enron", "Ling"}   # lower-cased and tokenised by their publishers
MAX_CHARS, MIN_CHARS = 10_000, 20
LEGIT_PER_SCAM, SEED = 3, 42

report = []


def log(msg=""):
    print(msg)
    report.append(msg)


def dedup_key(s: str) -> str:
    return hashlib.md5(re.sub(r"[^a-z0-9]", "", s.lower()).encode()).hexdigest()


# 1. Load each file and check its labels
frames = []
log("STEP 1  Load files and check label counts (as downloaded)")
log(f"{'file':16s}{'rows':>8s}{'label 0':>9s}{'label 1':>9s}{'no label':>9s}{'no sender':>11s}")
for name in FILES:
    df = pd.read_csv(IN_DIR / f"{name}.csv", engine="python")
    df["label"] = pd.to_numeric(df["label"], errors="coerce")
    if "sender" not in df:                       # Enron and Ling have no sender column
        df["sender"] = ""
    vc = df["label"].value_counts()
    missing = int((~df["label"].isin([0, 1])).sum())
    no_sender = int(df["sender"].isna().sum() + (df["sender"].astype(str).str.strip() == "").sum())
    log(f"{name:16s}{len(df):8d}{int(vc.get(0, 0)):9d}{int(vc.get(1, 0)):9d}{missing:9d}{no_sender:11d}")
    df["source"] = name
    frames.append(df[["sender", "subject", "body", "label", "source"]])
raw = pd.concat(frames, ignore_index=True)
log(f"{'TOTAL':16s}{len(raw):8d}")

# 2. Drop broken rows
log("\nSTEP 2  Drop broken rows")
n = len(raw)
raw = raw[raw["label"].isin([0, 1])]
log(f"  missing or invalid label: -{n - len(raw)}")
n = len(raw)
raw = raw[raw["body"].notna() & (raw["body"].astype(str).str.strip() != "")]
log(f"  empty email content:      -{n - len(raw)}")
raw["label"] = raw["label"].astype(int)

# 3. Build the three columns
log("\nSTEP 3  Build the three columns")
raw["email_address"] = raw["sender"].map(parse_address)
log("  email_address: extracted the bare address from 'Name <address>', lower-cased;")
log("    blank if missing, unparseable, or a dataset collector's own address (monkey.org,")
log("    spamassassin.taint.org)")
raw["text"] = [make_body(s, b) for s, b in zip(raw["subject"], raw["body"])]
raw["text"] = raw["text"].str.slice(0, MAX_CHARS)
naz = raw["source"].isin(["Nazario", "Nazario_5"]) & (raw["label"] == 1)
raw.loc[naz, "text"] = raw.loc[naz, "text"].str.replace(r"\bjose\b", "[name]", case=False, regex=True)
log("  body: subject + content; decoded encoded subject lines, repaired garbled characters,")
log("    masked email addresses inside the text as [email] and years as [year], removed the")
log("    Nazario collection domain, replaced the Nazario collector's name with [name],")
log(f"    normalised whitespace, cut at {MAX_CHARS} characters")
n = len(raw)
raw = raw[raw["text"].str.len() >= MIN_CHARS]
log(f"  body shorter than {MIN_CHARS} characters after cleaning: -{n - len(raw)}")

raw["category"] = "legit"
raw.loc[(raw["label"] == 1) & raw["source"].isin(SCAM_SOURCES), "category"] = "scam"
raw.loc[(raw["label"] == 1) & ~raw["source"].isin(SCAM_SOURCES), "category"] = "spam"

# 4. Remove duplicates
log("\nSTEP 4  Remove duplicates (same body after ignoring case, spacing and punctuation)")
raw["key"] = raw["text"].map(dedup_key)
labels_per_key = raw.groupby("key")["label"].nunique()
conflict = set(labels_per_key[labels_per_key > 1].index)
n = len(raw)
raw = raw[~raw["key"].isin(conflict)]
log(f"  labelled both ways in different files (all copies dropped): -{n - len(raw)} rows "
    f"({len(conflict)} distinct emails)")
raw["cat_rank"] = raw["category"].map({"scam": 0, "spam": 1, "legit": 2})
raw["src_rank"] = raw["source"].map({s: i for i, s in enumerate(FILES)})
raw["has_addr"] = (raw["email_address"] != "").astype(int)
# prefer: scam over spam, then a copy that has a sender address, then file order
raw = raw.sort_values(["key", "cat_rank", "has_addr", "src_rank"], ascending=[True, True, False, True])
n = len(raw)
dupes = raw[raw.duplicated("key", keep="first")]["source"].value_counts()
clean = raw.drop_duplicates("key", keep="first").sort_values("src_rank")
log(f"  duplicate copies removed: -{n - len(clean)}")
for s in FILES:
    if s in dupes:
        log(f"      {s:16s}{int(dupes[s]):7d} copies already seen in another file")

clean = clean.drop(columns=["body"]).rename(columns={"text": "body"})
clean["label"] = clean["label"].map({1: LABEL_SCAM, 0: LABEL_NOT_SCAM})
clean[["email_address", "body", "label", "category", "source"]].to_csv(
    OUT_DIR / "combined_clean.csv", index=False)
log(f"\nSTEP 5  combined_clean.csv: {len(clean)} unique emails")
log(pd.crosstab(clean["source"], clean["category"]).reindex(FILES).fillna(0).astype(int).to_string())
log("  totals: " + ", ".join(f"{k} {v}" for k, v in clean["category"].value_counts().items()))

# 5. Scam-focused training file
log("\nSTEP 6  Build data.csv (scam vs not scam)")
scam = clean[clean["category"] == "scam"]
pool = clean[(clean["category"] == "legit") & ~clean["source"].isin(PREPROCESSED_SOURCES)]
n_legit = min(len(pool), LEGIT_PER_SCAM * len(scam))
legit = pd.concat(g.sample(n=max(1, round(n_legit * len(g) / len(pool))), random_state=SEED)
                  for _, g in pool.groupby("source"))
log(f"  scam: {len(scam)}  |  not scam, sampled {LEGIT_PER_SCAM}:1 across sources: {len(legit)}")
log("  not-scam sources: " + ", ".join(f"{k} {v}" for k, v in legit["source"].value_counts().items()))
data = pd.concat([scam, legit]).sample(frac=1, random_state=SEED)
for lab in (LABEL_SCAM, LABEL_NOT_SCAM):
    log(f"  {lab:9s} with an email address: {(data.loc[data.label == lab, 'email_address'] != '').mean():.0%}")
data[["email_address", "body", "label"]].to_csv(OUT_DIR / "data.csv", index=False)
log(f"  data.csv: {len(data)} emails, columns email_address, body, label")

(OUT_DIR / "cleaning_report.txt").write_text("\n".join(report) + "\n")
