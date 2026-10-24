"""
Choose the Low / Medium / High cut-offs in app.py on the validation split.

    python tune_thresholds.py [--data data/data_combined.csv]
    python tune_thresholds.py --test     # once, after choosing: final check on the test set

Uses the model app.py loads (DistilBERT if ./scam_model is present) and the same rule-based
checks, on the validation emails train_distilbert.py held out (same seed and splits), so the
test set stays untouched. The baseline was trained on these emails, so tune with DistilBERT.
--test reports the cut-offs currently in app.py on the test set instead (about 10 minutes).

Goal: as few real scams as possible in Low, then as few genuine emails as possible in High.
Takes a few minutes on a laptop CPU.
"""
import argparse
import itertools

import numpy as np
from sklearn.model_selection import train_test_split

import app
import email_features as ef

ap = argparse.ArgumentParser()
ap.add_argument("--data", default="data/data_combined.csv")
ap.add_argument("--test", action="store_true", help="report app.py's cut-offs on the test set")
args = ap.parse_args()
SEED = 42

df = ef.load_dataset(args.data)
# Same splits as train_distilbert.py: 80/20 train/test, then 10% of train for validation
train_df, test_df = train_test_split(df, test_size=0.2, stratify=df["y"], random_state=SEED)
_, val_df = train_test_split(train_df, test_size=0.1, stratify=train_df["y"], random_state=SEED)
if args.test:
    val_df = test_df
print(f"{'Test' if args.test else 'Validation'} set: {len(val_df)} emails "
      f"({int(val_df['y'].sum())} scam), model: {app.MODEL_USED}")

y = val_df["y"].to_numpy()
p = np.array([app.scam_probability(b) for b in val_df["body"]])
found = [app.signals(b, "") for b in val_df["body"]]   # training data has no sender to check
n_sig = np.array([len(f) for f in found])
look = np.array([bool(app.LOOKALIKE_FLAGS & f.keys()) for f in found])
n_strong = np.array([len(app.STRONG_FLAGS & f.keys()) for f in found])


def levels(medium, high, weight):
    score = np.minimum(1.0, p + weight * n_sig)
    lv = np.where(score >= high, 2, np.where(score >= medium, 1, 0))
    lv = np.where(n_strong > 0, np.maximum(lv, 1), lv)
    return np.where(look | (n_strong >= 2), 2, lv)


if args.test:
    lv = levels(app.MEDIUM_CUTOFF, app.HIGH_CUTOFF, app.SIGN_WEIGHT)
    for name, mask in [("scams", y == 1), ("genuine", y == 0)]:
        print(f"  {name:8s} Low {np.sum(mask & (lv == 0)):5d}  Medium {np.sum(mask & (lv == 1)):4d}"
              f"  High {np.sum(mask & (lv == 2)):5d}")
    raise SystemExit

rows = []
for medium, high, weight in itertools.product([0.1, 0.2, 0.3, 0.4, 0.5], [0.6, 0.7, 0.8, 0.9],
                                              [0.0, 0.05, 0.1, 0.15]):
    lv = levels(medium, high, weight)
    rows.append((int(np.sum((y == 1) & (lv == 0))), int(np.sum((y == 0) & (lv == 2))),
                 int(np.sum((y == 0) & (lv == 1))), int(np.sum((y == 1) & (lv == 2))), medium, high, weight))

print(f"\n{'scams Low':>9} {'genuine High':>12} {'genuine Med':>11} {'scams High':>10}   medium high weight")
current = (app.MEDIUM_CUTOFF, app.HIGH_CUTOFF, app.SIGN_WEIGHT)
shown = sorted(rows)[:12]
for r in sorted(rows, key=lambda r: (r[4], r[6])):   # every setting with the current High cut-off
    if r[5] == app.HIGH_CUTOFF and r not in shown:
        shown.append(r)
for r in shown:
    mark = "  <- app.py now" if r[4:] == current else ""
    print(f"{r[0]:9d} {r[1]:12d} {r[2]:11d} {r[3]:10d}   {r[4]:6} {r[5]:4} {r[6]:6}{mark}")

print(f"\nScams scored below 0.1 by the model: {int(np.sum((y == 1) & (p < 0.1)))} of {int(y.sum())}; "
      f"genuine scored above 0.9: {int(np.sum((y == 0) & (p > 0.9)))} of {int((y == 0).sum())}")
print("Rule signs fired on genuine emails:",
      dict(sorted({k: sum(k in f for f, t in zip(found, y) if t == 0)
                   for f in found for k in f}.items())))
