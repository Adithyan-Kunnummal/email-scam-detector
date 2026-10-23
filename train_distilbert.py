"""
Fine-tune DistilBERT on (sender, body) pairs to classify emails as scam / not scam.

The model reads two pieces of text:
  1. a short description of the sender, e.g. "sender: free webmail address; many
     digits in name" (from email_features.sender_description - no raw domains)
  2. the email body (subject + content)

Input (CSV, three columns):
    data.csv      email_address, body, label ("scam" / "not scam")
    au_test.csv   same columns, optional Australian test set (never trained on)

Run in Google Colab (Runtime -> Change runtime type -> T4 GPU):
    !pip install -q transformers datasets accelerate scikit-learn ftfy
    # upload data.csv, email_features.py (and au_test.csv), then:
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
import pandas as pd
import torch
from datasets import Dataset
from sklearn.metrics import accuracy_score, confusion_matrix, precision_recall_fscore_support
from sklearn.model_selection import train_test_split
from transformers import (AutoModelForSequenceClassification, AutoTokenizer,
                          DataCollatorWithPadding, Trainer, TrainingArguments)

import email_features as ef

ap = argparse.ArgumentParser()
ap.add_argument("--data", default="data.csv")
ap.add_argument("--au-test", default="au_test.csv")
ap.add_argument("--out", default="scam_model")
ap.add_argument("--model-name", default="distilbert-base-uncased")
ap.add_argument("--epochs", type=float, default=2)
ap.add_argument("--max-len", type=int, default=256)
ap.add_argument("--sender-dropout", type=float, default=0.3)
ap.add_argument("--limit", type=int, default=0, help="use only N emails (quick test run)")
ap.add_argument("--no-clean", action="store_true",
                help="skip clean_text() on the body (only if the data was already cleaned with it)")
args = ap.parse_args()
SEED = 42


def load(path):
    df = ef.load_dataset(path, clean=not args.no_clean)
    df["label"] = df["y"]                       # the Trainer expects integer labels in `label`
    return df


df = load(args.data)
if args.limit:
    df = df.sample(n=min(args.limit, len(df)), random_state=SEED)
# Same 80/20 split as train_baseline.py, so the two models are compared on the same test set
train_df, test_df = train_test_split(df, test_size=0.2, stratify=df["label"], random_state=SEED)
train_df, val_df = train_test_split(train_df, test_size=0.1, stratify=train_df["label"], random_state=SEED)
rng = np.random.default_rng(SEED)
train_df = train_df.copy()
train_df.loc[rng.random(len(train_df)) < args.sender_dropout, "email_address"] = ""
print(f"train {len(train_df)}  val {len(val_df)}  test {len(test_df)}")

tok = AutoTokenizer.from_pretrained(args.model_name)


def encode(batch):
    senders = [ef.sender_description(a) for a in batch["email_address"]]
    # only the body is cut if the pair is too long; the short sender description is kept
    return tok(senders, batch["body"], truncation="only_second", max_length=args.max_len)


def to_ds(frame):
    ds = Dataset.from_pandas(frame[["email_address", "body", "label"]].reset_index(drop=True))
    return ds.map(encode, batched=True, remove_columns=["email_address", "body"])


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


def evaluate(name, ds):
    out = trainer.predict(ds)
    preds = np.argmax(out.predictions, axis=-1)
    tn, fp, fn, tp = confusion_matrix(out.label_ids, preds, labels=[0, 1]).ravel()
    m = out.metrics
    print(f"\n=== {name} ({len(ds)} emails) ===")
    print(f"accuracy {m['test_accuracy']:.3f}  precision {m['test_precision']:.3f}  "
          f"recall {m['test_recall']:.3f}  f1 {m['test_f1']:.3f}")
    print(f"Missed scams: {fn}   False alarms: {fp}")


evaluate("Test set, with sender addresses", test_ds)
evaluate("Test set, sender addresses removed", to_ds(test_df.assign(email_address="")))
if os.path.exists(args.au_test):
    evaluate("Australian test set", to_ds(load(args.au_test)))

trainer.save_model(args.out)
tok.save_pretrained(args.out)
with open(os.path.join(args.out, "input_format.json"), "w") as f:
    json.dump({"inputs": ["email_features.sender_description(email_address)", "body"],
               "max_length": args.max_len, "labels": {"0": ef.LABEL_NOT_SCAM, "1": ef.LABEL_SCAM}}, f, indent=2)
print(f"\nSaved model to {args.out}  (in Colab: zip it and download, or save straight to Drive)")
