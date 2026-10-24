# Report notes: Scam Email Checker prototype

Facts, numbers and reasons for the Assignment 3 report (proposal, prototype evidence and pitch), collected from the development work up to 24 Oct 2026. Every number below was measured on the code and data in the repository (branch `distilbert-and-rules`). Section 9 lists the commands to reproduce them.

---

## 1. Problem and users

- **Problem:** scam emails imitate trusted organisations (ATO, myGov, Australia Post, banks) and push people to pay, sign in or share details. Investment scams cause Australia's largest losses.
- **Target users:** international students in Australia (visa, university and tax scams; unfamiliar with local organisations) and older people (less confident spotting fake addresses).
- **Product:** a web app where the user pastes a suspicious email, or uploads a screenshot, optionally adds the sender's address, and gets **Low / Medium / High risk** with plain-language reasons and safe next steps.
- **Constraints from the brief:** self-contained, free and open-source only, no paid platforms or APIs, runs on a standard RMIT lab computer.

## 2. How the system works

**One-line description:** DistilBERT reads the email content and gives a scam probability; rule-based checks look for specific warning signs in the sender address, links and wording, including a lookalike-domain check against official Australian domains. The two are combined into a risk level with explanations.

```
Web page -- paste text / screenshot (OCR in the browser) + optional sender
   v  POST /check {text, sender}
FastAPI backend (app.py)
 1. clean_text()   same cleaning as the training data
 2. MODEL          DistilBERT reads the email CONTENT only -> scam probability
                   (falls back to TF-IDF + logistic regression if PyTorch is missing)
 3. RULES          content:  urgency, money, login requests, raw-IP links, lookalike links
                   strong:   investment, job, gift-card payment, prize, "Hi Mum" new number,
                             move to WhatsApp/Telegram, asks for a password/PIN by email
                   sender:   lookalike domain, government claim from a non-.gov.au address,
                             unusual ending (.xyz), free webmail + official-sounding text
 4. RISK LEVEL     lookalike sender/link or 2 strong signs -> High
                   else score = probability + 0.05 per sign:
                   >= 0.7 High, >= 0.2 Medium (0.4 for the baseline), else Low;
                   1 strong sign is never Low
                   real official sender + only official links + no strong sign
                   -> High lowered to Medium (never Low)
 5. EXPLANATION    template reasons + next steps (no paid LLM)
   v  {risk_level, scam_probability, reasons, flags, next_steps, model}
Result card: colour + icon + word, reasons, next steps, Details, feedback buttons
```

**Interface features (prototype evidence):**
- Paste text or upload a screenshot. OCR uses **Tesseract.js in the browser**, so the image never leaves the device; the extracted text is editable before checking.
- The result is shown with colour, icon **and** word, never colour alone. Wording: High = "Likely a scam", Medium = "Be careful – check first", Low = "No strong warning signs found" (never "Safe").
- The model's score appears only in a collapsible **Details** section, labelled as the content model's score.
- Accessibility for older users: large-text toggle, high contrast, simple wording, big buttons, keyboard accessible.
- "Share with someone I trust" copies a summary; feedback buttons ("This is a scam" / "This is safe") are stored in the browser only.
- Privacy note on the page: nothing is stored on the server.
- Demo mode: if the backend isn't running, the page still works with simple browser rules, clearly labelled.

## 3. Data

### 3a. Training data
- **Source:** 11 curated public email corpora (Champa, Rabbi & Zibran, 2024).
  - Scams: Nazario phishing corpus and the Nigerian Fraud (419) corpus.
  - Not scam: legitimate emails from SpamAssassin, CEAS-08, TREC-05/06/07 and the `_5` files, sampled 3 legitimate : 1 scam.
  - Excluded: spam (advertising is not a scam), and the pre-processed, lower-cased Enron/Ling files.
- **`data.csv`:** 19,056 emails (4,764 scam, 14,292 not scam).
- **`data_combined.csv` (used for training):** `data.csv` plus 18 genuine scams from a teammate's dataset, giving 19,074 emails (4,782 scam = 25%, 14,292 not scam). Columns: `body` (subject + content) and `label`.
- **Leakage removed:** the collector's address (jose@monkey.org), the collector's name, years (they reveal the source era), and encoded subjects. Email addresses inside the text are masked as `[email]`.
- **Remaining known shortcut:** "enron" and "713" (Enron's area code) are among the top not-scam words.

### 3b. Teammate's dataset (`combined_clean.csv`): not merged as-is
- 55,776 rows, but the label is **spam vs legitimate, not scam vs legitimate**. Only about 3–5% of its "scam" rows are actually scams; at least 22% are pharmacy, replica-watch, dating or stock adverts.
- Training on it teaches shortcuts: "replica", "watches" and "love" become scam words, while "university" and "edu" become safe words, so a fake university email would look safer.
- **18 genuine scams extracted** after filtering 27,543 rows down to 177 candidates and reviewing them manually: 11 pyramid/chain-letter schemes, 2 phishing, 2 malware lures, 2 prize/lottery frauds, 1 grant fraud.
- The baseline caught only 6 of the 18 and scored the pyramid schemes 0.25 on average, which **first showed the gap on "get-rich-quick" scams**.

### 3c. Australian domain list (`domains_labelled.csv`)
- 1,494 domains: 125 official brand domains and 1,369 fakes (about 10 generated variants per brand).
- The official domains became the allowlist (`official_domains.txt`, 125 domains plus the brands' genuine sister domains).

### 3d. Splits (identical for both models)
- 80/20 stratified train/test split, seed 42: **test set = 3,815 emails (956 scam)**.
- 10% of the training part held out for validation: **1,526 emails (383 scam)**, used for checkpoint selection and for tuning the risk cut-offs.
- DistilBERT trained on 13,733 emails.

## 4. Models

| | Baseline | DistilBERT |
|---|---|---|
| Method | TF-IDF (1–2 word n-grams, 50,000 features) + logistic regression, `class_weight="balanced"` | `distilbert-base-uncased` fine-tuned for 2 classes |
| Training | about 1 minute on a laptop CPU | 2 epochs, learning rate 2e-5, batch 16, max 256 tokens, mixed precision, **Google Colab T4 GPU** (minutes) |
| Model selection | – | best epoch by **recall** on validation (missing a scam is the costlier error) |
| Input | email content only | email content only |
| Speed in the app | instant | well under a second per email on a laptop CPU (3,815 emails in 528 s, batched) |
| Role | fallback when PyTorch isn't installed | main model |

**Why the sender address is not given to the model:** in the public datasets, legitimate senders are mostly a few organisations and mailing lists (enron.com, samba.org), so a model trained on addresses learns where an email came from, not whether it is a scam. Tested: adding sender features changed nothing on the test set (9 missed scams either way). Instead, sender addresses are handled by the rule-based checks.

**Training note:** the first Colab run went to the CPU by mistake. It showed 24 s per step, about 11.5 hours in total, and the warning "no accelerator is found". It was restarted on a T4 GPU.

## 5. Results

### 5a. Models on the test set (3,815 emails, threshold 0.5)

| Model | Accuracy | Precision (scam) | Recall (scam) | Missed scams | False alarms |
|---|---|---|---|---|---|
| Baseline | 99.4% | 99.1% | 98.6% | 13 | 9 |
| DistilBERT | 99.3% | 98.8% | 98.4% | 15 | 11 |

- **The two models are tied;** a difference of 2 emails is noise.
- **Scores this high overstate real-world accuracy.** The scams and genuine emails come from different sources and eras, so part of the task is telling the sources apart.
- **DistilBERT is very confident:** almost all scores are below 0.05 or above 0.95. With the original cut-offs (0.4 / 0.7) it put only 2 scams and 1 genuine email in Medium, while the baseline put 26 scams and 16 genuine emails there.

### 5b. Modern emails (24 hand-written examples, a sanity check only)
The test set is 2000s email, so 24 modern Australian examples (12 genuine, 12–13 scams) were written to see how the models handle today's emails. They are not a statistically valid test.

Model score only:

| | DistilBERT | Baseline |
|---|---|---|
| Genuine scored ≥ 0.2 (of 12) | 4 | 8 |
| Genuine scored ≥ 0.7 | 2 | 2 |
| Scams scored < 0.2 (of 12) | 5 | 2 |
| Scams scored ≥ 0.7 | 6 | 5 |

What the examples showed:
- DistilBERT reads meaning better: it scored a gift-card visa-fee scam 0.999 (baseline 0.32) and gave most genuine notifications near-zero scores.
- **Both models miss investment, job, prize and "Hi Mum" scams** (scores 0.005–0.08), because these types are almost absent from the training data.
- **DistilBERT is unstable on short genuine notifications.** An Australia Post tracking email scored 0.85 with a subject and greeting but 0.03 without them. Genuine Medicare and CommBank emails scored about 0.99, because they use bank and government wording.

### 5c. Improvements made in response
1. **Strong-sign rules** for investment, job, gift-card payment, prize and family-impersonation ("Hi Mum") scams, and for moving the chat to WhatsApp/Telegram. They follow Scamwatch's scam categories. One strong sign gives at least Medium; two give High. On the training data they fire on only 31 of 11,433 genuine emails (0.3%).
2. **Cut-offs tuned on the validation split** (`tune_thresholds.py`):

   | Medium cut-off | Scams rated Low (of 383) | Genuine rated High (of 1,143) | Genuine rated Medium |
   |---|---|---|---|
   | 0.4 (original) | 9 | 3 | 4 |
   | **0.2 (chosen)** | **6** | **3** | **4** |
   | 0.1 with sign weight 0.1 | 4 | 3 | 231 |

   A larger per-sign weight moves many genuine emails into Medium, because "money" and "urgency" words are common in normal email, so the weight stays at 0.05. The baseline keeps 0.4, because it scores many genuine modern emails 0.2–0.5.
3. **Lookalike-check fixes.** Testing showed **8 genuine test emails wrongly forced to High** by false lookalike-link matches:
   - a link-parsing bug: `groups.google.com?hl=en` kept `?hl=en` in the address;
   - Google's genuine domains (`googlepages.com`, `googlecode.com`) were missing from the allowlist;
   - `cetus-links.org` matched the brand Linkt;
   - a brand's real overseas site (`vodafone.co.nz`) or an unrelated site (`up.pt`, a Portuguese university, not Up Bank) was flagged.

   After the fixes, genuine emails rated High went back to the model's own 10.

4. **Official-sender cap for genuine bank and government emails.**
   - **The problem:** the model rated genuine emails as scams: CommBank eStatement 0.99, Medicare claim 0.999, NAB card notice 0.84, Australia Post tracking 0.85. Its training data has almost no genuine bank or government emails, so words like "bank", "account" and "myGov" mean scam to it.
   - **The rule:** if the sender is a real official address (on the allowlist, or `.gov.au`), every link goes to an official website and no strong scam sign fires, High is lowered to **Medium, never Low**. The explanation says the address is official but could be faked.
   - **Personal mail never counts:** free webmail (outlook.com, icloud.com) and the exact domains internet providers give customers (`telstra.com`, `iinet.net.au`). In the old data, 15 Nigerian-fraud emails came from personal `@telstra.com` accounts.
   - **Added alongside:** a strong sign for **asking for a password, PIN or one-time code by email**. It fires on 0 of 14,292 genuine training emails; safety advice like "never share your password" is ignored.
   - **Results:** genuine CommBank, NAB, Medicare and Australia Post emails from their real addresses are now **Medium instead of High** (still High without a sender address). Forged official senders stay High if a link goes elsewhere (lookalike site, bit.ly) or a password is requested.
   - **The trade-off, measured on `data.csv`:** **16 of 4,764 scams (0.3%)**, forged PayPal, eBay, Amazon, Apple, DHL and Microsoft addresses, drop from High to Medium. They're still warned. The data can't show the benefit, because it has almost no genuine official emails (1 of 61 genuine official-sender emails was affected; the other 60 were already Low).
   - **Why it's acceptable:** major banks and agencies now publish DMARC policies that make forging their exact domain harder, but the app can't verify an address the user types in. The proper fix is header checks in an email add-on (section 8).
   - **The test set has no sender addresses,** so this rule doesn't affect 5d.

### 5d. Final system on the test set (DistilBERT + rules + tuned cut-offs, run once)

| | Low | Medium | High |
|---|---|---|---|
| Scams (956) | 13 (1.4%) | 3 | 940 (98.3%) |
| Genuine (2,859) | 2,842 (99.4%) | 7 | 10 (0.3%) |

- **On the test set the gain is small.** The model alone at the original cut-offs gave 14 scams Low, 1 genuine Medium and 10 genuine High, so the new setup keeps one more scam out of Low and puts 6 more genuine emails at Medium. That's expected, because the test set contains few of the modern scam types the rules target.
- **On the modern examples:**

  | | Before the rules | After |
  |---|---|---|
  | Scams (13) | 5 Low, 1 Medium, 7 High | **0 Low**, 5 Medium, 8 High |
  | Genuine (12) | 9 Low, 1 Medium, 2 High | 8 Low, 2 Medium, 2 High |

  The baseline fallback gives the same scam results: 0 Low, 5 Medium, 8 High.

### 5e. Lookalike-domain check vs a trained domain classifier
Evaluation with 31 brands held out (344 domains, 313 fakes), plus 1,541 unrelated genuine domains (a list of common genuine sites plus a sample of sender domains from `data.csv`):

| Approach | Fakes caught (unseen brands) | Official domains wrongly flagged | Unrelated genuine domains wrongly flagged |
|---|---|---|---|
| Trained classifier (character n-grams + logistic regression, balanced) | 77% | 8 / 31 | 74% (abc.net.au, canva.com, xero.com …) |
| **Allowlist + lookalike check (no training)** | **96%** | **0 / 31** | **0.5%** |

- On the whole list the lookalike check catches 94.2% of fakes. The misses are very short brand names (asc.com for ASIC, dhi.com for DHL), which are deliberately not fuzzy-matched to avoid false alarms.
- **Why the trained classifier fails:** its only genuine examples are 125 big brands, so it learns "any domain not on the list is fake". Class weighting only moves it along a trade-off; in earlier runs, without weighting it flagged 99.9% of unrelated genuine domains, and with a strict 0.95 cut-off it caught only 6% of fakes.
- **Why the lookalike check is better:** it flags only domains that resemble a known brand, explains which brand, and is updated by editing a text file.
- **What it checks for:** look-alike characters (0→o, rn→m), small typos, extra words (auspost-refund), the real address placed in front of another site (auspost.com.au.verify-id.com), and wrong endings (telstra.co). `.gov.au` and `.edu.au` are never flagged, because registration is restricted to government and education bodies.

### 5f. Example results from the working app (good for screenshots and the video)

| Email | Model score | Result | Reason shown |
|---|---|---|---|
| ATO refund, verify bank details, raw-IP link | 0.999 | High | lookalike sender, raw-IP link, urgency, money, login request |
| Linkt unpaid toll, link to linkt-pay.top | 0.003 | High | link and sender imitate linkt.com.au (the model alone would miss it) |
| `https://c0mmbank.com.au/review` | 0.012 | High | link imitates commbank.com.au |
| Home Affairs visa fee paid by gift card | 0.999 | High | gift-card payment, lookalike sender |
| Job: earn $800/week rating products, message on WhatsApp | 0.016 | High | job-scam and WhatsApp signs |
| "I made $3,000 last week with this crypto trading platform" | 0.005 | Medium | investment-scam sign |
| "Hi Mum, I broke my phone. This is my new number" | 0.03 | Medium | family-impersonation sign |
| RMIT assignment reminder; AGL bill | ≈0.00 | Low | – |

## 6. Design decisions and reasons

| Decision | Reason |
|---|---|
| Model reads content only; sender handled by rules | avoids dataset shortcuts; tested with no loss of accuracy |
| A real official sender lowers High to Medium only, never to Low, and only with official links and no strong sign | the model wrongly flags genuine bank and government emails; addresses can be forged, so an official address never makes an email look safe (16 forged-brand scams, 0.3%, go High → Medium) |
| Lookalike sender or link → High on its own | genuine organisations don't send from imitation addresses; catches scams the model misses (Linkt toll 0.003 → High) |
| Three levels, not scam/not scam or a percentage | shows uncertainty honestly; Medium = "check first" |
| Never say "Safe" | the system can miss scams; Low means "no strong warning signs found" |
| Template explanations, no LLM | the brief forbids paid APIs; templates are predictable and testable |
| Rules for scam types missing from the data | cheap, explainable, follow Scamwatch categories; retraining needs data we don't have |
| Cut-offs tuned on validation, test set used once | avoids tuning to the test set |
| Baseline kept as fallback | markers can run the app without installing PyTorch (a large download) |
| OCR in the browser | screenshots never leave the user's device |
| Allowlist instead of a trained domain classifier | 96% vs 77% fakes caught, 0.5% vs 74% false alarms |

## 7. Limitations (be upfront in the report)
- **Old, mixed-source training data:** 99% test scores overstate real-world accuracy, and the model has never seen modern genuine notifications or modern scam types.
- **False alarms on genuine bank and government emails:** the model scores them 0.84–0.999. With the real sender address the official-sender cap makes them Medium; without the sender they are still High.
- **The official-sender cap trusts an address the app can't verify:** a forged official address with official-looking links and no strong scam sign gets Medium instead of High (0.3% of scams in the data).
- **DistilBERT is overconfident and unstable on short notifications** (Australia Post tracking: 0.85 vs 0.03 depending on the subject line).
- **The strong-sign rules are hand-written keyword patterns;** scammers can avoid them by rewording.
- **Lookalike check:**
  - a brand name in a subdomain of another site (my-gov-au.verify-id.com) isn't flagged, because only the registered name is checked;
  - a brand's exact name on another country's ending (commbank.co.nz) isn't flagged;
  - very short brand names aren't fuzzy-matched;
  - the fake-domain list looks generated, so real scam domains may be more varied.
- **Screenshots** lose the real address behind links, so link checks are weaker.
- **The modern examples are only 24 hand-written emails,** not a proper evaluation.
- **English only.**

## 8. Future directions
- **A modern evaluation set:** a few hundred recent real scams (Scamwatch alerts, public phishing collections) and genuine notifications, kept separate from training.
- **Retraining** with modern emails; **calibrating** DistilBERT's scores (temperature scaling) so Medium reflects real uncertainty.
- **Gmail add-on / Outlook add-in** that checks the open email in one click and reads real headers (SPF/DKIM/DMARC). Needs a sensitive OAuth scope and verification; automatic inbox scanning needs a restricted scope and an annual security assessment.
- **A multilingual model** (XLM-RoBERTa) and explanations in the user's language, for international students.
- **A trained fusion model** to learn how much each warning sign should count; drift monitoring and retraining.
- **SMS and messaging channels** (most "Hi Mum" and toll scams arrive by text).

## 9. Reproducing the results

```
pip install -r requirements.txt
python train_baseline.py --data data/data_combined.csv            # baseline numbers (5a)
# DistilBERT: in Colab with a T4 GPU (see the header of train_distilbert.py)
python train_distilbert.py --data data_combined.csv --out scam_model
python tune_thresholds.py                                          # validation table (5c)
python tune_thresholds.py --test                                   # final system (5d)
python evaluate_domain_check.py data/domains_labelled.csv data.csv # domain table (5e)
python -m uvicorn app:app                                          # app at http://localhost:8000
```

Demo emails with expected results: `samples/demo_emails.md`. Design record: `PROJECT_CONTEXT.md`.

## 10. Suggested figures
1. The architecture diagram (section 2) redrawn as a flowchart.
2. Screenshots of the result card at all three levels: the Linkt toll (High from a lookalike link despite a 0.003 model score), the crypto tip (Medium), the RMIT reminder (Low).
3. Screenshot flow: upload → OCR progress → editable text → result.
4. A bar chart of the final system's Low/Medium/High split for scams and genuine emails (5d).
5. The domain-check comparison table (5e).
6. A before/after table of the modern scam types with and without the strong-sign rules (5d).

## 11. Key numbers at a glance
- 19,074 training emails (25% scam); test set 3,815; validation set 1,526.
- Baseline 99.4% / DistilBERT 99.3% accuracy; 13 / 15 missed scams; 9 / 11 false alarms.
- Final system: 1.4% of scams rated Low, 0.3% of genuine emails rated High (test set).
- Modern scam examples rated Low: 5 of 13 before the rules, 0 of 13 after.
- Genuine bank and government emails with their real sender: High → Medium; cost: 16 forged-brand scams (0.3%) High → Medium.
- Lookalike check: 96% of unseen-brand fakes caught, 0 of 31 official domains flagged, 0.5% false alarms (a trained classifier: 77%, 8/31, 74%).
- 18 genuine scams found in 55,776 rows of the teammate's spam dataset.
