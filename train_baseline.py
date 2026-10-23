"""
Baseline scam-email classifier: TF-IDF on the body + sender warning signs,
fed into logistic regression. Trains in about a minute on a laptop CPU.

Input (CSV, three columns):
    data.csv      email_address, body, label ("scam" / "not scam")   training data
    au_test.csv   same columns, optional: hand-built Australian test set (never trained on)

Run:
    pip install pandas scikit-learn joblib ftfy
    python train_baseline.py                 # or: python train_baseline.py --data my.csv

Output: baseline_model.joblib (needs email_features.py next to it when loaded)
"""
import argparse
import os

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer

import email_features as ef

ap = argparse.ArgumentParser()
ap.add_argument("--data", default="data.csv")
ap.add_argument("--au-test", default="au_test.csv")
ap.add_argument("--out", default="baseline_model.joblib")
ap.add_argument("--sender-dropout", type=float, default=0.3,
                help="share of training rows whose sender is blanked, so the model also "
                     "works when users don't paste a sender")
ap.add_argument("--no-clean", action="store_true",
                help="skip clean_text() on the body (only if the data was already cleaned with it)")
args = ap.parse_args()
SEED = 42


def load(path):
    return ef.load_dataset(path, clean=not args.no_clean)


def report(name, model, df):
    pred = model.predict(df[["email_address", "body"]])
    print(f"\n=== {name} ({len(df)} emails) ===")
    print(classification_report(df["y"], pred, target_names=["not scam", "scam"], digits=3))
    tn, fp, fn, tp = confusion_matrix(df["y"], pred, labels=[0, 1]).ravel()
    print(f"Missed scams: {fn}   False alarms: {fp}")


def build(use_sender=True):
    parts = [("body", TfidfVectorizer(lowercase=True, ngram_range=(1, 2), min_df=2,
                                      max_features=50_000, sublinear_tf=True), "body")]
    if use_sender:
        parts.append(("sender", FunctionTransformer(
            ef.sender_matrix, feature_names_out=ef.sender_feature_names), "email_address"))
    return Pipeline([("features", ColumnTransformer(parts)),
                     ("clf", LogisticRegression(max_iter=2000, class_weight="balanced"))])


df = load(args.data)
train_df, test_df = train_test_split(df, test_size=0.2, stratify=df["y"], random_state=SEED)

# Sender dropout: blank some training senders in BOTH classes. In the datasets more
# scams than legitimate emails lack a sender, and users often won't paste one.
rng = np.random.default_rng(SEED)
train_df = train_df.copy()
train_df.loc[rng.random(len(train_df)) < args.sender_dropout, "email_address"] = ""

model = build(use_sender=True).fit(train_df[["email_address", "body"]], train_df["y"])

report("Test set, with sender addresses", model, test_df)
report("Test set, sender addresses removed", model, test_df.assign(email_address=""))
if os.path.exists(args.au_test):
    report("Australian test set", model, load(args.au_test))

# Does the sender help? Same split, body only.
body_only = build(use_sender=False).fit(train_df[["email_address", "body"]], train_df["y"])
fn_with = ((model.predict(test_df[["email_address", "body"]]) == 0) & (test_df["y"] == 1)).sum()
fn_without = ((body_only.predict(test_df[["email_address", "body"]]) == 0) & (test_df["y"] == 1)).sum()
print(f"\nMissed scams on the test set: body + sender {fn_with}, body only {fn_without}")

# What the model learned (useful for the proposal's explainability discussion)
names = model.named_steps["features"].get_feature_names_out()
coefs = model.named_steps["clf"].coef_[0]
words = [(c, n.split("__", 1)[1]) for c, n in zip(coefs, names) if n.startswith("body__")]
print("\nTop scam words learned:", ", ".join(w for _, w in sorted(words, reverse=True)[:15]))
print("Sender warning-sign weights (positive = pushes towards scam):")
for n, c in zip(ef.SENDER_FEATURES, coefs[-len(ef.SENDER_FEATURES):]):
    print(f"  {n:28s}{c:+.2f}")

joblib.dump(model, args.out)
print(f"\nSaved {args.out}")
