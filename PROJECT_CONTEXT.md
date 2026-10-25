# Project Context: Scam Email Checker (FOAI Assignment 3 prototype)

Hand-off notes for implementing the working prototype in Claude Code. Last updated 24 Oct 2026.

## 1. The assignment

- RMIT Foundations of AI 2026 S2, Assignment 3: a group project to design and pitch an AI product. Worth 40 marks, due 1 November 2026, 11:59pm.
- Deliverables, submitted as one zip:
  1. proposal document
  2. mock-up / prototype
  3. project plan
  4. 3-minute pitch slide deck
  5. `contribution.doc`
- The mock-up / prototype alone is worth 4 marks ("clearly demonstrating user–system interaction and workflow"). A working prototype is "highly desirable but not compulsory".
- **Hard constraint from the spec:** the system must be self-contained and must not rely on proprietary software, paid platforms or paid subscriptions. The teaching team must be able to run it on standard RMIT lab computers. Open-source libraries are fine if the installation steps are clearly documented. A screen-recorded walkthrough (MP4) and annotated screenshots are also accepted as evidence.

## 2. The product

- A **web app where a user pastes a suspicious email (or uploads a screenshot of it), optionally with the sender's address**, and the system rates it **Low / Medium / High risk**, with plain-language reasons and safe next steps.
- **Target users:** international students in Australia and older people.
- **Decision: no Gmail API / Gmail add-on in the prototype**, because it's too complex. That is a "future direction" in the proposal.

## 3. Architecture (prototype)

**One-line description:** DistilBERT predicts from the email content; rule-based checks look for specific warning signs in the sender address, links and wording, including a lookalike-domain check against official Australian domains.

```
[Web page] -- paste text OR upload screenshot, + optional sender address
     |  (screenshot -> Tesseract.js OCR in the browser -> editable text box -> user confirms)
     v
POST /check {text, sender?}  -->  [FastAPI backend: app.py]
   1. clean_text(text)                          (same cleaning as the training data)
   2. MODEL: DistilBERT reads the email CONTENT only -> scam probability
      (falls back to the TF-IDF + logistic regression baseline if ./scam_model is absent)
   3. RULE-BASED CHECKS -> reasons
        content: urgency, money/payment, login/password requests, raw-IP links,
                 lookalike LINK domains
        strong:  investment, job, gift-card payment, prize, family member ("Hi Mum")
                 with a new number or asking for money, urgent money request,
                 move to WhatsApp/Telegram, asks for a password/PIN by email
                 (scam types the model misses, sections 5e-5f)
        sender:  lookalike SENDER domain, government claim from a non-.gov.au sender,
                 unusual domain ending (.xyz…), free webmail + official-sounding text
      lookalike check = domain_check.py + official_domains.txt (no training)
   4. risk_level(): lookalike sender or link, or 2 strong signs -> High;
                    otherwise probability + 0.05 per warning sign -> >=0.7 High,
                    >=0.2 Medium (0.4 with the baseline), else Low; 1 strong sign is never Low;
                    real official sender + only official links + no strong sign -> High becomes Medium
   5. template reasons + next steps
     <-- JSON {risk_level, scam_probability, reasons[], next_steps[], model}
[Result card] level + reasons + next steps + feedback buttons
```

Design decisions already made:

- **The model reads only the email content.** The sender address is never given to the model; it is handled entirely by the rule-based checks. (Tested: adding sender features to the model changed nothing on the test set — 9 missed scams either way — and removed a dataset shortcut where a missing sender nudged emails towards "scam".)
- **Address signals are asymmetric.** A lookalike address or link raises the result to High. A real official sender can only lower High to Medium, never to Low, and only if every link goes to an official website and no strong scam sign fires, because sender addresses can be forged (section 5f). *(Changed 24 Oct 2026: previously an official address never lowered the risk.)*
- **No trained model for domains.** A trained domain classifier was tested and rejected (section 5c).
- **The UI shows Low/Medium/High, not a raw percentage or scam/not-scam.** The model is evaluated as a binary classifier, but users see three levels so uncertainty is shown honestly.
  - Wording: High = "Likely a scam"; Medium = "Be careful – check first"; Low = "No strong warning signs found" (never "Safe").
  - The probability may appear only in a collapsible "Details" section, and it is the model's raw content score, not the final adjusted score (so it can look low on a High result triggered by a lookalike domain).
- **Explanations are template-based. No paid LLM API** (spec constraint).
- **Thresholds in `risk_level()` were tuned on the validation split** (`tune_thresholds.py`, section 5e): Medium from 0.2 (DistilBERT) or 0.4 (baseline), High from 0.7, +0.05 per warning sign.
- **Strong-sign rules cover scam types the model misses** (investment, job, gift-card payment, prize, "Hi Mum", move to WhatsApp/Telegram). One strong sign makes the result at least Medium; two make it High. They follow Scamwatch's scam categories, and the explanations say which type it looks like.
- **The baseline stays as a fallback** so markers can run the app without installing PyTorch or training DistilBERT.

## 4. Existing code

All files sit in one folder. `email_features.py`, `domain_check.py` and `official_domains.txt` must sit next to `app.py` and the training scripts.

| File | What it does | Status |
|---|---|---|
| `email_features.py` | Shared module. `load_dataset()` (reads and checks a training CSV, section 5d), `clean_text()` (decode encoded subjects, fix garbled characters, mask addresses as `[email]` and years as `[year]`), `parse_address()`, `sender_features()` (used by the **rules**: has sender, free webmail, many digits in name, unusual domain ending, hyphen/digits in domain, lookalike domain), `check_domain()`, `to_binary_label()`. | Tested |
| `domain_check.py` | Lookalike-domain check (**not a trained model**): compares a domain with the official allowlist after undoing look-alike characters (0→o, 1→l, rn→m…), small typos (edit distance), extra words (auspost-refund), the real address placed in front of another site (auspost.com.au.verify-id.com, mygov.gov.au.evil.com) and wrong endings (telstra.co). `.gov.au` / `.edu.au` addresses are never flagged (registration is restricted), nor is a brand's exact name on another country's ending (vodafone.co.nz, up.pt; section 5e). Returns verdict official / lookalike / unrelated + a plain-language reason. | Tested (section 5c) |
| `official_domains.txt` | Allowlist: 125 official domains from `domains_labelled.csv` (rows with `is_scam` = 0) + genuine sister domains (googlemail.com, optusnet.com.au …). Add a brand's other real domains here if they get flagged. | Done |
| `prepare_data.py` | Builds `data.csv` from the 11 curated CSVs (Champa, Rabbi & Zibran, 2024). Writes `cleaning_report.txt`. | Tested |
| `train_baseline.py` | TF-IDF on the email content + logistic regression (`class_weight="balanced"`). Reports the test set and top scam / not-scam words for leakage checks. Saves `baseline_model.joblib`. Run with `--data data_combined.csv`. | Tested: 99.6% accuracy, 9 missed scams, 8 false alarms on 3,812 test emails |
| `train_distilbert.py` | Fine-tunes `distilbert-base-uncased` on the email content, 2 epochs, max_len 256, best checkpoint by recall, fp16 on GPU. Same 80/20 split as the baseline. Flags: `--data --out --epochs --limit --no-clean`. Saves `./scam_model`. Train in Colab on a T4 (about 5–8 min); save to Google Drive. | **Trained 24 Oct 2026** on `data_combined.csv` (Colab T4); model in `scam_model/`. Results in section 5e |
| `app.py` | FastAPI `POST /check` with `{text, sender?}`: steps 1–5 in section 3. Loads `./scam_model` if present, else `baseline_model.joblib`. | Tested with both models, lookalike and genuine domain cases, and `samples/demo_emails.md` |
| `tune_thresholds.py` | Chooses the risk-level cut-offs on the validation split (same splits as training); `--test` reports the chosen cut-offs once on the test set. | Done |
| `samples/demo_emails.md` | Demo emails with the result each gets, and known false alarms. | Done |
| `evaluate_domain_check.py` | `python evaluate_domain_check.py data/domains_labelled.csv data.csv` (needs the `email_address` column, so `data.csv`, not the 2-column `data_combined.csv`) compares the lookalike check with a trained domain classifier on held-out brands and unrelated genuine domains. | Tested |
| `requirements.txt` | Python dependencies. | Done |

Run: `pip install -r requirements.txt`, `python train_baseline.py`, then `uvicorn app:app --reload`.

Backend test results (baseline model):

| Input | Result | Why |
|---|---|---|
| "Your parcel is ready…" from `notify@auspost-delivery.com.au` | High | sender imitates auspost.com.au |
| "Please review your recent activity at https://c0mmbank.com.au/review", no sender | High | link imitates commbank.com.au (model alone: 0.31) |
| "ATO Refund notice… send your bank details" from `ato.refunds@gmail.com` | High | model 0.84 + money, government-claim and free-webmail signs |
| Genuine Australia Post tracking email from `notifications.auspost.com.au` | Low | — |
| RMIT tutorial email from `rmit.edu.au`; casual email with no sender | Low | — |

## 5. Data

### 5a. Training datasets: `data.csv` and `data_combined.csv`

- Built by `prepare_data.py` from the 11 curated corpora: 19,056 emails, 4,764 scam / 14,292 not scam. Scams = Nazario + Nigerian Fraud; not scam = legitimate emails from SpamAssassin, CEAS-08, TREC-05/06/07 and the `_5` files, sampled 3:1. Spam and the pre-processed (lower-cased, tokenised) Enron/Ling files are excluded.
- Training files have two columns: `body`, `label`. The model trains on the email content only; sender addresses are not part of the training data (they are checked at run time by the rules).
- Leakage removed: collector address jose@monkey.org, collector name, years, encoded subjects. Remaining known shortcut: "enron" and "713" (Enron's area code) are top not-scam words — harmless for users but worth noting as a limitation.
- No separate Australian test set is being built. Australian relevance comes from the address checks: `official_domains.txt` (allowlist) and `domains_labelled.csv` (evaluation of the lookalike check).
- **Current training file: `data_combined.csv`** = `data.csv` + 18 genuine scams from the teammate's file (section 5b): 19,074 emails, 4,782 scam / 14,292 not scam, columns `body`, `label`. Baseline on it: 99.4% accuracy, 13 missed scams, 9 false alarms (different random test split from `data.csv`; on the identical split the two files differ by 1 missed scam).

### 5b. Teammate's `combined_clean.csv` — decision: do NOT combine as-is; 18 genuine scams extracted

55,776 rows, columns `text`, `is_scam`. Findings:
- **The label is spam vs legitimate, not scam vs legitimate.** Only ~3–5% of `is_scam=1` rows are scam-like (our scam model flags 5.1%; 3.2% contain phishing/fraud phrases); at least 22% are pharmacy, replica-watch, dating or stock ads. Of rows that match our corpus exactly, 3,918 are what we classed as spam vs 1 scam.
- **It teaches shortcuts.** A model trained on it learns "replica", "watches", "love" as scam words and "enron", "2007", "2008", "university", "edu" as legitimate words — so a fake university email would look safer for mentioning a university.
- 23% of rows are the lower-cased Enron/Ling text excluded from our data.

**Genuine scams extracted (done 24 Oct 2026).** Pipeline: 27,543 `is_scam=1` rows → 21,834 after removing lower-cased Enron/Ling rows → 18,495 after cleaning and de-duplication → 693 candidates (content model ≥ 0.5 or phishing/fraud phrases) → 205 after removing near-copies of our corpus (488 matched emails we classed as spam) → 177 unique after collapsing template variants → **18 genuine scams on manual review**: 11 pyramid/chain-letter money schemes, 2 phishing, 2 malware lures, 2 prize/lottery frauds, 1 grant fraud. A random sample of 120 non-candidates contained no clear phishing or fraud (fake "CNN Alert" and celebrity-video lures were excluded as unverifiable from text). Files: `teammate_new_scams.csv` (the 18), `teammate_candidates_reviewed.csv` (all 177 with the decision), `data_combined.csv` (`data.csv` + the 18; 4,782 scam / 14,292 not scam).

Effect, measured on the identical 3,812-email test set: `data.csv` only → 9 missed scams, 8 false alarms; `data.csv` + 18 → 10 missed, 9 false alarms (no measurable difference). Useful finding for the report: the current model catches only 6 of the 18 (score ≥ 0.5) and scores the 11 pyramid/chain-letter schemes at 0.25 on average, so **"get-rich-quick" investment-style scams are a coverage gap** — relevant because investment scams cause Australia's largest losses. `data_combined.csv` is fine to use (it adds that category, and credits the teammate's work); 18 examples are too few to fix the gap on their own.

### 5c. Australian domain list (`domains_labelled.csv`) — decision: allowlist + lookalike check, not a trained model

1,494 domains: 125 official, 1,369 fake (about 10 systematic variants per brand). Evaluation (`evaluate_domain_check.py`, 31 brands held out):

| Approach | Fakes caught (unseen brands) | Official domains wrongly flagged | Unrelated genuine domains wrongly flagged |
|---|---|---|---|
| Trained classifier, no class weighting | 100% | 31 / 31 | 99.9% |
| Trained classifier, `class_weight="balanced"` | 77% | 8 / 31 | 75.0% (abc.net.au, canva.com, xero.com, zoom.us …) |
| Same, stricter cut-off 0.95 | 6% | 0 / 31 | 0.4% |
| **Allowlist + lookalike check (`domain_check.py`)** | **96%** | **0 / 31** | **0.4%** |

The trained model fails because the only genuine examples are 125 big brands, so it learns "any domain not on the list is fake"; class weighting only moves it along a trade-off. The lookalike check flags only domains that resemble a known brand, explains which brand, and is updated by editing `official_domains.txt`. Whole-list catch rate 94.2%; misses are very short brand names (asc.com for asic, dhi.com for dhl), deliberately not fuzzy-matched to avoid false alarms. Caveat: the fake list looks generated, so real scam domains may be more varied.

### 5e. DistilBERT results, risk cut-offs and extra rules (24 Oct 2026)

**DistilBERT vs baseline, same 3,815-email test set** (`data_combined.csv`, cut-off 0.5):

| Model | Accuracy | Scam recall | Missed scams | False alarms |
|---|---|---|---|---|
| DistilBERT (2 epochs, Colab T4) | 99.3% | 98.4% | 15 | 11 |
| Baseline (TF-IDF + logistic regression) | 99.4% | 98.6% | 13 | 9 |

The two are tied on this test set; a difference of 2 emails is noise. DistilBERT is very confident: almost every score is below 0.05 or above 0.95.

**Modern emails (24 hand-written examples, `samples/demo_emails.md`; a sanity check, not an evaluation).** The test set is 2000s email, so it can't show how the models handle today's scams:
- DistilBERT reads meaning better. It scored a gift-card visa scam 0.999 (baseline 0.32) and was right on most genuine notifications.
- Both models miss **investment, job, prize and "Hi Mum" scams** (scores 0.005–0.08). These categories are almost absent from the training data, which confirms the gap found in 5b.
- DistilBERT is **unstable on short genuine notifications**. An Australia Post tracking email scored 0.85 with a subject and greeting but 0.03 without them, and genuine Medicare and CommBank emails scored about 0.99. These stay as known false alarms; a genuine sender address never lowers the risk, by design.

**Changes made in response:**
1. **Strong-sign rules** for the scam types the model misses: investment, job, gift-card payment, prize, family impersonation ("Hi Mum, new number") and moving the conversation to WhatsApp/Telegram. One strong sign gives at least Medium; two give High. They follow Scamwatch's scam categories. On the training data they fire on 0.3% of genuine emails, mostly "investment" (Enron's energy-trading emails) and "prize" (award announcements). On the modern examples, scams rated Low went from 5 of 13 to 0 of 13.
2. **Cut-offs tuned on the validation split** (`tune_thresholds.py`; 1,526 emails, 383 scam, not used for training). Lowering Medium from 0.4 to 0.2 cut the scams rated Low from 9 to 6 without adding genuine emails to High. A larger per-sign weight moved 32–231 genuine emails into Medium, because "money" and "urgency" words are common in normal email, so the weight stays at 0.05. The baseline keeps Medium at 0.4, because it scores many genuine modern emails between 0.2 and 0.5.
3. **Lookalike-check fixes**, found because rules forced 8 genuine test emails to High:
   - link hosts now stop at `?` and `#` (`groups.google.com?hl=en` was read as an unknown domain);
   - added Google's genuine domains (`googlepages.com`, `googlecode.com` …) to the allowlist;
   - typos are matched only against the whole name, not each hyphenated word (`cetus-links.org` had matched `linkt`);
   - a brand's exact name on another country's ending is not flagged (`vodafone.co.nz`, `up.pt`). Trade-off: `commbank.co.nz` is no longer flagged; `commbank-login.co.nz` and `telstra.co` still are.

   The domain evaluation is unchanged: 96% of unseen-brand fakes caught, 0/31 official domains flagged, 94.2% caught on the whole list. 0.5% of unrelated genuine domains are wrongly flagged, measured on a sample of `data.csv` senders.

**Final system on the test set** (DistilBERT + rules + cut-offs, run once after tuning):

| | Low | Medium | High |
|---|---|---|---|
| Scams (956) | 13 (1.4%) | 3 | 940 |
| Genuine (2,859) | 2,840 | 9 | 10 (0.3%) |

Compared with the model alone at the old cut-offs (14 scams Low, 1 genuine Medium, 10 genuine High), the test-set gain is small: one more scam kept out of Low, at the cost of 8 more genuine emails at Medium (numbers updated 25 Oct after the family-emergency rules, section 5g). That is expected, because the test set contains few of the modern scam types the rules target. The main gain is on modern scams (above).

**Limitations for the report:** the test data is old and mixed-source, so its scores overstate real-world accuracy; the strong-sign rules are hand-written keyword patterns that scammers can avoid by rewording; a brand name in a subdomain of another site (`my-gov-au.verify-id.com`) is not flagged, because only the registered name is checked; screenshots lose link addresses.

### 5f. Genuine bank and government emails: official-sender cap (24 Oct 2026)

**Problem.** DistilBERT rates many genuine bank and government emails as scams (CommBank eStatement 0.99, Medicare claim 0.999, NAB card notice 0.84, Australia Post tracking 0.85). In the training data, words like "bank", "account", "myGov" and "password" appear almost only in phishing; there are almost no genuine notifications from these organisations.

**Change (`official_sender()` in `app.py`).** If all of these hold, a High result is lowered to **Medium (never Low)**:
- the sender is a real official address: on the allowlist, or ending in `.gov.au` / `.edu.au`;
- every link in the email goes to an official website;
- no lookalike, raw-IP or strong scam sign fires.

The reason shown is: "The sender's address is a real official address and its links go to official websites, so it may be genuine. But addresses can be faked: check in the official app or website before you act."

Personal mail never counts: free webmail (outlook.com, icloud.com …) and the exact domains Australian internet providers give their customers (`telstra.com`, `iinet.net.au`, `tpg.com.au` …). Without the provider exclusion, 15 Nigerian-fraud emails from personal `@telstra.com` accounts would have been capped.

**Added with it:** a strong sign for **asking for a password, PIN or one-time code by email** (genuine organisations never do this). It fires on 0 of 14,292 genuine training emails. Safety advice such as "never share your password" is ignored. A forged CommBank address asking for a password by reply therefore stays High.

**Trade-off, measured on `data.csv` (which has sender addresses):**

| | Official-sender condition holds | Lowered from High to Medium |
|---|---|---|
| Scams (4,764) | 16 | 16 (0.3%), all forged brand addresses: eBay 3, PayPal 3, Amazon 2, Apple 4, DHL, Microsoft, Google, Uber |
| Genuine (14,292) | 61 | 1 (the other 60 were already Low) |

The dataset can't show the benefit, because it has almost no genuine bank or government emails. The hand-written examples can: genuine CommBank, NAB, Medicare and Australia Post emails sent from their real addresses are now Medium instead of High. Forged official senders were common in the 2000s data; today, major banks and government agencies publish DMARC policies that make forging their exact domain harder. But the app can't verify an address the user types in. The proper fix is checking SPF/DKIM/DMARC in a Gmail add-on (section 7) and retraining with genuine notifications.

The test set has no sender addresses, so this cap doesn't change the section 5e test-set results.

### 5g. Family-emergency scams (25 Oct 2026)

**Problem.** "Hi, it's your son. I need $10,000 because I need help and I am in an emergency" was rated **Low** (model score 0.07, no rule fired). The training data has no family-emergency ("Hi Mum") scams; they appeared later and mostly arrive by text message. The family rule only looked for "new number / broken phone", "$10,000" is not a money keyword, and "emergency" was not an urgency word.

**Change.** Two strong signs (two together give High):
- **Family claim + money request** (`family_impersonation`, widened): "it's (me,) your son / daughter / grandson …" or "Hi Mum / Dad / Grandma …", followed within about 150 characters by a request for money ("need / send / transfer … $800 / money / cash").
- **Urgent money request** (`urgent_money`, new): a money request close to "emergency / urgent / asap / right now / today / in trouble / hospital / arrested".

**Results.**
- Four family-emergency variations (son, Mum, grandson, daughter) are now High, in the backend and the browser demo. The "new number" message without a money request stays Medium.
- Genuine family messages ("Hi Mum, are we still on for dinner?", "Dad, I'll pay you back on Friday"), bills and invoices stay Low.
- Training data: the widened family rule fires on 0 of 14,292 genuine emails; urgent money fires on 4 genuine (0.03%, news items such as "will pay $3.64 more … effective today") and 111 scams.
- Test set: scams unchanged (13 Low, 3 Medium, 940 High); genuine Medium 7 → 9, genuine High unchanged at 10.

**Not retrained.** The model still scores these scams 0.01–0.27. Fixing the model itself needs a few hundred family-emergency scams *and* genuine family messages (so it doesn't learn "mum" or "$" = scam), with real examples held out for testing. Listed as future work.

### 5d. Format required for any training file

| Requirement | Detail |
|---|---|
| File | CSV, UTF-8, with a header row |
| Columns | `body`, `label`. Names are matched ignoring case and surrounding spaces; any other columns (e.g. `email_address`) are ignored. |
| `body` | Subject + email content in one string (e.g. `subject + "\n\n" + content`). |
| `label` | `scam` / `not scam`. Also accepted: `1`/`0`, `not_scam`, `Not Scam`, `phishing`, `fraud`, `legit`, `legitimate`, `ham`, `safe`. **`spam` is rejected on purpose**: decide whether spam counts as scam and relabel it. |

The scripts automatically run `clean_text()` on every body (`--no-clean` skips it), drop bodies under 20 characters and duplicates, print class balance, and stop with a clear message on a missing column or unknown label.

After training on any new data:
1. **Look for leakage** in the "Top scam words" / "Top not-scam words" lines: names, domains, dates, area codes or dataset markers mean the model is learning where an email came from.
2. **Very high scores (99%+)** on a mixed-source dataset usually mean the classes come from different sources or eras; treat them as an upper bound.
3. DistilBERT has no class weighting; if scams are a small minority, watch its scam recall.

## 6. What to build in Claude Code

### A. Web front end (main task)

- A single page (plain HTML/CSS/JS, or a simple framework) that calls `POST http://localhost:8000/check` with `{text, sender}`.
- **Input area:**
  - Large text box for the email content (required).
  - Optional fields for sender address and subject (subject is prepended to the text).
  - Two tabs or buttons: **"Paste text"** and **"Upload screenshot"**.
- **Screenshot input with open-source OCR (required):**
  - Use **Tesseract.js** (open-source, Apache-2.0) running **in the browser**, so the image never leaves the user's device.
  - Flow: user uploads or drags in a screenshot (PNG/JPG), progress indicator while OCR runs, extracted text fills an **editable text box with a prompt like "Check the text is right, then press Check"**. The confirmed text is sent to `/check` exactly like pasted text.
  - Tell users to crop to just the email. If OCR returns little or no text, ask for a clearer screenshot or pasted text.
  - Known limitation: screenshots don't show the real web address behind links, so link checks are weaker than with pasted text.
- **Result card:**
  - The risk level shown with colour, icon **and** word (never colour alone).
  - Reasons list and next steps (don't click, contact the organisation via its official app or website, report to Scamwatch).
  - Collapsible "Details" with the probability, labelled as the content model's score.
  - "This is a scam" / "This is safe" feedback buttons (can just log locally for the prototype).
- **Accessibility for older users:** large default font or a large-text toggle, high contrast, simple wording, big buttons, keyboard accessible. A "Share with someone I trust" option that copies a summary.
- Privacy note on the page: nothing is stored; remove personal details before checking.

### B. Backend touches (`app.py`)

- Keep the `/check` contract unchanged.
- Optionally: return which rules fired as structured flags; input validation (empty or very long text); redact identifiers before any logging (nothing is logged by default).

### C. Supporting deliverables

- **README** with step-by-step run instructions for a marker on a standard lab computer, including how to run with the baseline model if `scam_model` isn't present.
- **Sample emails** (scam and legitimate, including lookalike-domain examples and a couple of screenshots) for the demo.
- Make sure it works end to end with the baseline model, so the demo doesn't depend on Colab.
- Record a **screen walkthrough (MP4)** and take **annotated screenshots** for the mock-up deliverable.

## 7. Future directions (proposal only, don't build)

- **Gmail add-on:** checks the open email in one click and reads real headers for SPF/DKIM/DMARC checks. Uses a sensitive scope, which needs OAuth verification.
- **Automatic inbox scanning:** restricted Gmail scope, annual third-party security assessment (CASA). Opt-in only.
- **Multilingual model** (XLM-RoBERTa) and LLM explanations in the user's language.
- **Trained fusion model** to learn how much each warning sign should count, plus drift monitoring and retraining.
- **Outlook add-in, SMS and messaging channels.**
