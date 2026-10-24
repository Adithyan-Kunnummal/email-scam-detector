"""
Fine-tune DistilBERT to classify an email's content (subject + body) as scam / not scam.

The model reads ONLY the email content. The sender address is checked separately by the
rule-based checks in app.py (including the lookalike-domain check), not by the model.

Input (CSV):
    data.csv   body, label ("scam" / "not scam"); any other columns are ignored

Run in Google Colab (Runtime -> Change runtime type -> T4 GPU):
    !pip install -q transformers datasets accelerate scikit-learn ftfy
    # upload data.csv and email_features.py (and domain_check.py), then:
    !python train_distilbert.py
    # keep the model if Colab disconnects: save to Google Drive
    #   from google.colab import drive; drive.mount('/content/drive')
    #   !python train_distilbert.py --out /content/drive/MyDrive/scam_model
Expected time on a T4: about 5-8 minutes of training (mixed precision is on automatically).

Output: a folder (default ./scam_model) that app.py loads.
"""
import argparse
import inspect
import json
import os

import numpy as np
import torch
from datasets import Dataset
from sklearn.metrics import accuracy_score, confusion_matrix, precision_recall_fscore_support
from sklearn.model_selection import train_test_split
from transformers import (AutoModelForSequenceClassification, AutoTokenizer,
                          DataCollatorWithPadding, Trainer, TrainingArguments)

import email_features as ef

ap = argparse.ArgumentParser()
ap.add_argument("--data", default="data.csv")
ap.add_argument("--out", default="scam_model")
ap.add_argument("--model-name", default="distilbert-base-uncased")
ap.add_argument("--epochs", type=float, default=2)
ap.add_argument("--max-len", type=int, default=256)
ap.add_argument("--limit", type=int, default=0, help="use only N emails (quick test run)")
ap.add_argument("--no-clean", action="store_true",
                help="skip clean_text() on the body (only if the data was already cleaned with it)")
args = ap.parse_args()
SEED = 42

df = ef.load_dataset(args.data, clean=not args.no_clean)
df["label"] = df["y"]                          # the Trainer expects integer labels in `label`
if args.limit:
    df = df.sample(n=min(args.limit, len(df)), random_state=SEED)
# Same 80/20 split as train_baseline.py, so the two models are compared on the same test set
train_df, test_df = train_test_split(df, test_size=0.2, stratify=df["label"], random_state=SEED)
train_df, val_df = train_test_split(train_df, test_size=0.1, stratify=train_df["label"], random_state=SEED)
print(f"train {len(train_df)}  val {len(val_df)}  test {len(test_df)}")

tok = AutoTokenizer.from_pretrained(args.model_name)


def to_ds(frame):
    ds = Dataset.from_pandas(frame[["body", "label"]].reset_index(drop=True))
    return ds.map(lambda b: tok(b["body"], truncation=True, max_length=args.max_len),
                  batched=True, remove_columns=["body"])


train_ds, val_ds, test_ds = to_ds(train_df), to_ds(val_df), to_ds(test_df)


def metrics(eval_pred):
    logits, labels = eval_pred
    preds = np.argmax(logits, axis=-1)
    p, r, f1, _ = precision_recall_fscore_support(labels, preds, average="binary",
                                                  pos_label=1, zero_division=0)
    return {"accuracy": accuracy_score(labels, preds), "precision": p, "recall": r, "f1": f1}


model = AutoModelForSequenceClassification.from_pretrained(
    args.model_name, num_labels=2,
    id2label={0: ef.LABEL_NOT_SCAM, 1: ef.LABEL_SCAM},
    label2id={ef.LABEL_NOT_SCAM: 0, ef.LABEL_SCAM: 1})

training_args = TrainingArguments(
    output_dir=os.path.join(os.path.dirname(os.path.abspath(args.out)), "checkpoints"),
    num_train_epochs=args.epochs,
    learning_rate=2e-5,
    per_device_train_batch_size=16,
    per_device_eval_batch_size=32,
    weight_decay=0.01,
    eval_strategy="epoch",
    save_strategy="epoch",
    save_total_limit=1,
    load_best_model_at_end=True,
    metric_for_best_model="recall",   # missing a scam is the costlier error for our users
    fp16=torch.cuda.is_available(),   # mixed precision roughly halves training time on a GPU
    report_to="none",
    seed=SEED,
)
# newer transformers versions call the tokenizer argument `processing_class`
tok_kw = "processing_class" if "processing_class" in inspect.signature(Trainer.__init__).parameters else "tokenizer"
trainer = Trainer(model=model, args=training_args, train_dataset=train_ds, eval_dataset=val_ds,
                  data_collator=DataCollatorWithPadding(tok), compute_metrics=metrics,
                  **{tok_kw: tok})
trainer.train()


def report(name, y_true, y_pred):
    y_true, y_pred = np.asarray(y_true), np.asarray(y_pred)
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    p, r, f1, _ = precision_recall_fscore_support(y_true, y_pred, average="binary",
                                                  pos_label=1, zero_division=0)
    print(f"\n=== {name} ({len(y_true)} emails) ===")
    print(f"accuracy {accuracy_score(y_true, y_pred):.3f}  precision {p:.3f}  recall {r:.3f}  f1 {f1:.3f}")
    print(f"Missed scams: {fn}   False alarms: {fp}")


preds = np.argmax(trainer.predict(test_ds).predictions, axis=-1)
report("Test set", test_df["label"], preds)

trainer.save_model(args.out)
tok.save_pretrained(args.out)
with open(os.path.join(args.out, "input_format.json"), "w") as f:
    json.dump({"input": "email content (subject + body), cleaned with email_features.clean_text",
               "max_length": args.max_len, "labels": {"0": ef.LABEL_NOT_SCAM, "1": ef.LABEL_SCAM}}, f, indent=2)
print(f"\nSaved model to {args.out}  (in Colab: zip it and download, or save straight to Drive)")
