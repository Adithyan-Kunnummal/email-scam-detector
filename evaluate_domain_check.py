"""
Evaluate the lookalike-domain check against a trained domain classifier.

    python evaluate_domain_check.py [data/domains_labelled.csv] [data.csv]

domains_labelled.csv: columns domain, is_scam (0 = official, 1 = fake); each official
domain is followed by its fakes. data.csv (optional): legitimate sender domains are
added to the false-alarm test.

Brand-held-out test: a quarter of the brands (official domain + its fakes) are hidden
from the trained classifier, so it is tested on brands it has never seen - like a new
scam target. The lookalike check is never trained; it only uses the official domains.
"""
import sys

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

from domain_check import DomainChecker

domains_path = sys.argv[1] if len(sys.argv) > 1 else "data/domains_labelled.csv"
data_path = sys.argv[2] if len(sys.argv) > 2 else None

d = pd.read_csv(domains_path, dtype=str)
d["y"] = d["is_scam"].astype(int)
brand, cur = [], None
for dom, y in zip(d.domain, d.y):
    cur = dom if y == 0 else cur
    brand.append(cur)
d["brand"] = brand
print(f"{len(d)} domains: {int((d.y == 0).sum())} official, {int(d.y.sum())} fake, {d.brand.nunique()} brands")

# Genuine domains that are not on the list: none of these should be flagged
unrelated = """abc.net.au sbs.com.au smh.com.au theage.com.au news.com.au bom.gov.au health.gov.au
education.gov.au rba.gov.au abs.gov.au accc.gov.au moneysmart.gov.au studyaustralia.gov.au
immi.homeaffairs.gov.au uq.edu.au unsw.edu.au sydney.edu.au anu.edu.au deakin.edu.au latrobe.edu.au
qut.edu.au uts.edu.au mq.edu.au adelaide.edu.au uwa.edu.au curtin.edu.au griffith.edu.au bankwest.com.au
hsbc.com.au canva.com atlassian.com xero.com afl.com.au cricket.com.au dominos.com.au aldi.com.au
bigpond.com gmail.com yahoo.com.au hotmail.com github.com zoom.us dropbox.com docusign.net
mailchimp.com sendgrid.net joesplumbing.com.au service.vic.gov.au humanservices.gov.au""".split()
if data_path:
    senders = pd.read_csv(data_path, keep_default_na=False, dtype=str)
    if "email_address" not in senders.columns:      # training files only need body, label
        raise SystemExit(f"{data_path} has no email_address column; run without it.")
    senders = senders[(senders.label.str.lower() == "not scam") & (senders.email_address != "")]
    unrelated += (senders.email_address.str.split("@").str[1].drop_duplicates()
                  .sample(min(1500, len(senders)), random_state=0).tolist())
unrelated = [u for u in dict.fromkeys(unrelated) if u not in set(d.domain)]

brands = np.array(d.brand.unique())
np.random.default_rng(0).shuffle(brands)
test_brands = set(brands[: len(brands) // 4])
tr, te = d[~d.brand.isin(test_brands)], d[d.brand.isin(test_brands)]
print(f"Brand-held-out test: {len(te)} domains from {len(test_brands)} unseen brands; "
      f"{len(unrelated)} unrelated genuine domains\n")


def show(name, pred_te, pred_un):
    pred_te, y = np.asarray(pred_te), te.y.values
    caught = ((pred_te == 1) & (y == 1)).sum()
    print(f"{name}\n  fakes caught: {caught}/{int(y.sum())} ({caught / y.sum():.0%})"
          f"   official wrongly flagged: {int(((pred_te == 1) & (y == 0)).sum())}/{int((y == 0).sum())}"
          f"   unrelated genuine wrongly flagged: {int(np.sum(pred_un))}/{len(pred_un)} "
          f"({np.mean(pred_un):.1%})")


vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5))
clf = LogisticRegression(max_iter=3000, class_weight="balanced").fit(vec.fit_transform(tr.domain), tr.y)
show("A) Trained classifier (character n-grams + logistic regression)",
     clf.predict(vec.transform(te.domain)), clf.predict(vec.transform(unrelated)))

dc = DomainChecker(d.domain[d.y == 0])
look = lambda x: int(dc.check(x)["verdict"] == "lookalike")
show("B) Allowlist + lookalike check (no training)",
     [look(x) for x in te.domain], [look(x) for x in unrelated])
missed = [x for x, y in zip(d.domain, d.y) if y == 1 and not look(x)]
print(f"\nB on the whole list: {1 - len(missed) / d.y.sum():.1%} of fakes caught; missed e.g. {missed[:10]}")
