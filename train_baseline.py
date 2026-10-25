"""
Baseline scam-email classifier: TF-IDF on the email content (subject + body) fed into
logistic regression. Trains in about a minute on a laptop CPU.

The model reads ONLY the email content. The sender address is checked separately by the
rule-based checks in app.py (including the lookalike-domain check), not by the model.
The app falls back to this model when no trained DistilBERT folder is present, so it
must behave like DistilBERT: content in, scam probability out.

Input (CSV):
    data/data_combined.csv (default)   body, label ("scam" / "not scam"); any other columns are ignored

Run:
    pip install pandas scikit-learn joblib ftfy
    python train_baseline.py                 # or: python train_baseline.py --data my.csv

Output: baseline_model.joblib
"""
import argparse

import joblib
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

import email_features as ef

ap = argparse.ArgumentParser()
ap.add_argument("--data", default="data/data_combined.csv")
ap.add_argument("--out", default="baseline_model.joblib")
ap.add_argument("--no-clean", action="store_true",
                help="skip clean_text() on the body (only if the data was already cleaned with it)")
args = ap.parse_args()
SEED = 42


def report(name, y_true, y_pred):
    print(f"\n=== {name} ({len(y_true)} emails) ===")
    print(classification_report(y_true, y_pred, target_names=["not scam", "scam"], digits=3,
                                zero_division=0))
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    print(f"Missed scams: {fn}   False alarms: {fp}")


df = ef.load_dataset(args.data, clean=not args.no_clean)
# Same 80/20 split as train_distilbert.py, so the two models are compared on the same test set
train_df, test_df = train_test_split(df, test_size=0.2, stratify=df["y"], random_state=SEED)

model = Pipeline([
    ("tfidf", TfidfVectorizer(lowercase=True, ngram_range=(1, 2), min_df=2,
                              max_features=50_000, sublinear_tf=True)),
    ("clf", LogisticRegression(max_iter=2000, class_weight="balanced")),
]).fit(train_df["body"], train_df["y"])

preds = model.predict(test_df["body"])
report("Test set", test_df["y"], preds)

# What the model learned: check for leakage (names, domains, dates, dataset markers)
vocab = model.named_steps["tfidf"].get_feature_names_out()
coefs = model.named_steps["clf"].coef_[0]
order = np.argsort(coefs)
print("\nTop scam words learned:", ", ".join(vocab[order[-15:]][::-1]))
print("Top not-scam words learned:", ", ".join(vocab[order[:15]]))

joblib.dump(model, args.out)
print(f"\nSaved {args.out}")
