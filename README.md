# Scam Email Checker

RMIT Foundations of AI 2026 S2, Assignment 3 prototype.

Paste a suspicious email (or upload a screenshot of it) and the app rates it **Low / Medium / High risk**, with plain-language reasons and safe next steps. Everything runs on your own computer with free, open-source software. No paid APIs or accounts are needed.

## Run it (standard lab computer)

You need **Python 3.10 or newer** and **Git LFS**. The trained models and the dataset are stored with Git LFS.

1. Get the code, including the model files:
   ```
   git lfs install
   git clone https://github.com/Adithyan-Kunnummal/email-scam-detector.git
   cd email-scam-detector
   ```
   If you downloaded a zip, or `baseline_model.joblib` is only a few hundred bytes, run `git lfs pull` inside the folder.

2. Install the libraries:
   ```
   pip install -r requirements.txt
   ```
   This includes PyTorch, which is a large download. To run with the lighter baseline model only, install just:
   ```
   pip install pandas scikit-learn joblib ftfy fastapi uvicorn
   ```

3. Start the app:
   ```
   python -m uvicorn app:app
   ```

4. Open **http://localhost:8000** in a web browser.

You can also open `frontend/index.html` directly while the server is running. If the server isn't running, the page still works in a clearly labelled **demo mode** that uses simple browser rules instead of the trained model.

### Which model is used

| Situation | Model | Shown in Details as |
|---|---|---|
| `scam_model/` present and PyTorch installed | DistilBERT (fine-tuned) | `distilbert` |
| PyTorch not installed, or `scam_model/` missing | TF-IDF + logistic regression (`baseline_model.joblib`) | `baseline` |

To force the baseline, run `SCAM_MODEL_DIR=none python -m uvicorn app:app` (PowerShell: `$env:SCAM_MODEL_DIR="none"; python -m uvicorn app:app`).

## Using the app

- **Paste text:** paste the email into the box. Adding the sender's address and subject is optional but gives better checks.
- **Screenshot:** choose or drag in a PNG/JPG. The text is read in your browser with Tesseract.js, so the image never leaves your device. Check and correct the text, then press **Check this email**. The first use downloads Tesseract.js from a CDN, so you need an internet connection. Screenshots don't show the real address behind links, so pasted text gives a better check.
- **Try an example:** six built-in samples (tax refund, missed parcel, visa fee, uni timetable, crypto tip, job offer). More are in `samples/demo_emails.md`.
- The result shows the risk level as a colour, an icon **and** a word, the reasons, and next steps. The raw model score is only in the collapsible **Details** section. Other features: a large-text toggle, "Share with someone I trust" (copies a summary), and feedback buttons (saved in this browser only).
- Nothing is stored on the server. Remove names and account numbers before checking.

## How it works

DistilBERT predicts from the email content. Rule-based checks look for specific warning signs in the sender address, links and wording, including a lookalike-domain check against official Australian domains.

```
Web page (frontend/) --POST /check {text, sender?}--> FastAPI (app.py)
   1. clean_text()          same cleaning as the training data (email_features.py)
   2. MODEL                 DistilBERT (or the baseline) reads the email CONTENT only
                            -> scam probability
   3. RULE CHECKS           content: urgency, money, login requests, raw-IP links,
                                     lookalike LINK domains
                            scam types the model misses (strong signs): investment,
                                     job, gift-card payment, prize, "Hi Mum" new number,
                                     move to WhatsApp/Telegram, asks for a password/PIN
                            sender:  lookalike SENDER domain, government claim from a
                                     non-.gov.au sender, unusual ending (.xyz ...),
                                     free webmail + official-sounding text
                            lookalike check = domain_check.py + official_domains.txt
   4. risk_level()          lookalike sender or link, or 2 strong signs -> High;
                            otherwise probability + 0.05 per warning sign ->
                            High (>=0.7) / Medium (>=0.2; 0.4 for the baseline) / Low,
                            and 1 strong sign is never Low. Cut-offs chosen on the
                            validation split with tune_thresholds.py.
                            Real official sender + only official links + no strong
                            sign -> High is lowered to Medium (never Low).
   <-- {risk_level, scam_probability, reasons[], flags[], next_steps[], model}
```

- **The sender address is never given to the model.** In the public datasets, legitimate senders are mostly a few organisations (enron.com, python.org ...), so a model learns where an email came from rather than whether it is a scam. Adding sender features to the model changed nothing on the test set.
- **A lookalike address or link makes the result High.** Genuine organisations don't send from imitation addresses.
- **A real official sender can lower High to Medium, never to Low.** The model rates many genuine bank and government emails as scams, because its training data has almost none. If the sender is an organisation's real address (on the allowlist, or `.gov.au`), every link goes to an official website and there is no strong scam sign, the result is capped at Medium with the note that addresses can be faked. Personal mail (outlook.com, icloud.com, telstra.com …) never counts. In the training data this cap would move 16 of 4,764 scams (0.3%, forged PayPal, eBay, Apple … addresses) from High to Medium.
- **The lookalike check is not a trained model.** It compares a domain with the allowlist after undoing look-alike characters (0→o, rn→m …), small typos, extra words (auspost-refund.com), the real address placed in front of another site (my.gov.au.secure-check.com) and wrong endings (telstra.co). `.gov.au` and `.edu.au` addresses are never flagged, because only government and education bodies can register them. A brand's exact name on another country's ending (vodafone.co.nz) is not flagged either, because it is usually the brand's own overseas site. If a brand's genuine domain gets flagged, add it to `official_domains.txt`.

## Files

| File | Purpose |
|---|---|
| `app.py` | Backend API (`POST /check`); also serves the web page |
| `email_features.py` | Shared text cleaning, dataset loading and sender warning signs, used by every script |
| `domain_check.py` | Lookalike-domain check (allowlist + rules, no training) |
| `official_domains.txt` | Allowlist of official brand domains used by the lookalike check |
| `frontend/` | Web page: `index.html`, `style.css`, `script.js` |
| `baseline_model.joblib` | Trained TF-IDF + logistic regression model (email content only) |
| `scam_model/` | Fine-tuned DistilBERT model (email content only) |
| `data.csv` | Emails built by `prepare_data.py` (`email_address, body, label`; the models read only `body`) |
| `data/data_combined.csv` | **Current training file:** `data.csv` + 18 genuine scams from a teammate's dataset |
| `data/domains_labelled.csv` | 125 official + 1,369 fake Australian brand domains (`domain, is_scam`) |
| `cleaning_report.txt` | How `data.csv` was built, with counts at every step |
| `prepare_data.py` | Builds `data.csv` from the 11 curated datasets (Champa, Rabbi & Zibran, 2024) |
| `train_baseline.py` | Trains the baseline model (about a minute on a laptop) |
| `train_distilbert.py` | Fine-tunes DistilBERT (run in Google Colab on a T4 GPU) |
| `evaluate_domain_check.py` | Compares the lookalike check with a trained domain classifier |
| `tune_thresholds.py` | Chooses the Low / Medium / High cut-offs on the validation split; `--test` reports them on the test set |
| `samples/demo_emails.md` | Demo emails with the result each gets, plus known false alarms |
| `test_baseline.py` | Quick check that the baseline model loads and scores an email |
| `PROJECT_CONTEXT.md` | Design decisions, data findings and remaining work |

## Retraining

```
python prepare_data.py <folder with the 11 CSVs> <output folder>                # rebuild data.csv
python train_baseline.py --data data/data_combined.csv                           # about a minute
python train_distilbert.py --data data/data_combined.csv --out scam_model        # in Colab; see the file header
python evaluate_domain_check.py data/domains_labelled.csv data.csv              # lookalike-check evaluation
python tune_thresholds.py                                                        # risk cut-offs (validation split)
```

Any CSV with the columns `body, label` works (`--data my.csv`); other columns (such as `email_address`) are ignored, because the models read only the email content. Label values: `scam` / `not scam` (also `1`/`0`, `phishing`, `fraud`, `legit`, `legitimate`, `ham`, `safe`). `spam` is rejected on purpose: decide whether spam counts as scam and relabel it. See `email_features.load_dataset()`.

After training on new data, check the "Top scam words" / "Top not-scam words" lines for leakage (names, domains, dates, area codes or dataset markers).

**Model results** (`data/data_combined.csv`, the same 3,815 held-out emails): DistilBERT 99.3% accuracy, 15 missed scams, 11 false alarms; baseline 99.4%, 13 missed scams, 9 false alarms. Scores this high on mixed-source public data overstate real-world accuracy. Known shortcut: "enron" and "713" (Enron's area code) are top not-scam words.

**Full system** (DistilBERT + rules, cut-offs tuned on the validation split): on the test set, 13 of 956 scams (1.4%) are rated Low and 10 of 2,859 genuine emails (0.3%) are rated High. Both models miss modern investment, job, prize and "Hi Mum" scams, so rules for these keep them out of Low. See `PROJECT_CONTEXT.md` section 5e and `samples/demo_emails.md`.

**Lookalike check** (31 brands held out): catches 96% of fake domains for unseen brands, flags 0 of 31 official domains and 0.5% of unrelated genuine domains. A trained character n-gram classifier caught 77% but flagged 74% of unrelated genuine domains (abc.net.au, canva.com, xero.com …), because its only genuine examples are 125 big brands.
