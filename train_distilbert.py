"""
Step 2: Fine-tune DistilBERT as the scam-email classifier.

Run this in Google Colab with a free GPU:
  Runtime -> Change runtime type -> T4 GPU
  !pip install -q transformers datasets accelerate scikit-learn
  upload data.csv (and au_test.csv), then:  !python train_distilbert.py

Same CSV format as train_baseline.py (text,label with 1 = scam).
Output: a folder ./scam_model you can load in app.py.
"""
import os
import numpy as np
import pandas as pd
from datasets import Dataset
from sklearn.metrics import accuracy_score, precision_recall_fscore_support, confusion_matrix
from sklearn.model_selection import train_test_split
from transformers import (AutoModelForSequenceClassification, AutoTokenizer,
                          DataCollatorWithPadding, Trainer, TrainingArguments)

MODEL_NAME = "distilbert-base-uncased"
MAX_LEN = 256          # emails are truncated to this many tokens; scam cues are usually early
OUT_DIR = "scam_model"


def load(path):
    df = pd.read_csv(path).dropna(subset=["text", "label"])
    df["text"] = df["text"].astype(str).str.strip()
    df["label"] = df["label"].astype(int)
    df = df[df["text"].str.len() > 20]
    return df.drop_duplicates(subset="text")


df = load("data.csv")
train_df, test_df = train_test_split(df, test_size=0.2, stratify=df["label"], random_state=42)
train_df, val_df = train_test_split(train_df, test_size=0.1, stratify=train_df["label"], random_state=42)
print(f"train {len(train_df)}  val {len(val_df)}  test {len(test_df)}")

tok = AutoTokenizer.from_pretrained(MODEL_NAME)


def to_ds(frame):
    ds = Dataset.from_pandas(frame[["text", "label"]].reset_index(drop=True))
    return ds.map(lambda b: tok(b["text"], truncation=True, max_length=MAX_LEN), batched=True)


train_ds, val_ds, test_ds = to_ds(train_df), to_ds(val_df), to_ds(test_df)


def metrics(eval_pred):
    logits, labels = eval_pred
    preds = np.argmax(logits, axis=-1)
    p, r, f1, _ = precision_recall_fscore_support(labels, preds, average="binary", pos_label=1)
    return {"accuracy": accuracy_score(labels, preds), "precision": p, "recall": r, "f1": f1}


model = AutoModelForSequenceClassification.from_pretrained(
    MODEL_NAME, num_labels=2, id2label={0: "legit", 1: "scam"}, label2id={"legit": 0, "scam": 1}
)

args = TrainingArguments(
    output_dir="checkpoints",
    num_train_epochs=2,
    learning_rate=2e-5,
    per_device_train_batch_size=16,
    per_device_eval_batch_size=32,
    weight_decay=0.01,
    eval_strategy="epoch",
    save_strategy="epoch",
    load_best_model_at_end=True,
    metric_for_best_model="recall",   # missing a scam is the costlier error for our users
    report_to="none",
)

trainer = Trainer(model=model, args=args, train_dataset=train_ds, eval_dataset=val_ds,
                  processing_class=tok, data_collator=DataCollatorWithPadding(tok),
                  compute_metrics=metrics)
trainer.train()


def evaluate(name, ds):
    out = trainer.predict(ds)
    preds = np.argmax(out.predictions, axis=-1)
    tn, fp, fn, tp = confusion_matrix(out.label_ids, preds, labels=[0, 1]).ravel()
    m = out.metrics
    print(f"\n=== {name} ===")
    print(f"accuracy {m['test_accuracy']:.3f}  precision {m['test_precision']:.3f}  "
          f"recall {m['test_recall']:.3f}  f1 {m['test_f1']:.3f}")
    print(f"Missed scams: {fn}   False alarms: {fp}")


evaluate("General test set", test_ds)
if os.path.exists("au_test.csv"):
    evaluate("Australian test set", to_ds(load("au_test.csv")))

trainer.save_model(OUT_DIR)
tok.save_pretrained(OUT_DIR)
print(f"\nSaved model to ./{OUT_DIR}  (zip it and download from Colab)")
