"""
Step 1: Baseline scam-email classifier (TF-IDF + Logistic Regression).

Fast, runs on any laptop in seconds, and gives you a number to beat.
If DistilBERT doesn't clearly beat this, say so in the proposal.

Input files (CSV, two columns):
  data.csv      -> text,label   (label: 1 = scam, 0 = legitimate)  general training data
  au_test.csv   -> text,label   optional: your hand-built Australian test set (never trained on)

Run:  python train_baseline.py
"""
import os
import joblib
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline


def load(path):
    df = pd.read_csv(path)
    df = df.dropna(subset=["text", "label"])
    df["text"] = df["text"].astype(str).str.strip()
    df["label"] = df["label"].astype(int)
    df = df[df["text"].str.len() > 20]           # drop empty / junk rows
    return df.drop_duplicates(subset="text")     # duplicates leak between train and test


def report(name, y_true, y_pred):
    print(f"\n=== {name} ===")
    print(classification_report(y_true, y_pred, target_names=["legit", "scam"], digits=3))
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    print(f"Missed scams (false negatives): {fn}   False alarms (false positives): {fp}")


df = load("data.csv")
print(f"Loaded {len(df)} emails  ({df['label'].mean():.0%} scam)")

train_df, test_df = train_test_split(
    df, test_size=0.2, stratify=df["label"], random_state=42
)

model = Pipeline([
    ("tfidf", TfidfVectorizer(lowercase=True, ngram_range=(1, 2), min_df=2,
                              max_features=50_000, sublinear_tf=True)),
    ("clf", LogisticRegression(max_iter=1000, class_weight="balanced")),
])
model.fit(train_df["text"], train_df["label"])

report("General test set (20% held out)", test_df["label"], model.predict(test_df["text"]))

if os.path.exists("au_test.csv"):
    au = load("au_test.csv")
    report(f"Australian test set ({len(au)} emails)", au["label"], model.predict(au["text"]))

# Top words pushing towards "scam" - useful for the proposal's explainability discussion
vocab = model.named_steps["tfidf"].get_feature_names_out()
coefs = model.named_steps["clf"].coef_[0]
top = sorted(zip(coefs, vocab), reverse=True)[:15]
print("\nTop scam indicators learned:", ", ".join(w for _, w in top))

joblib.dump(model, "baseline_model.joblib")
print("\nSaved baseline_model.joblib")
