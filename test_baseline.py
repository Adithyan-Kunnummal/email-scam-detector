"""Quick check that baseline_model.joblib loads and scores an email: python test_baseline.py"""
import joblib

import email_features as ef

model = joblib.load("baseline_model.joblib")

email = """Your myGov account has been suspended

Dear customer, verify your bank details within 24 hours to receive your ATO refund."""

body = ef.clean_text(email)                   # the model reads the email content only
p_scam = model.predict_proba([body])[0][1]    # probability of scam (class 1)
label = model.predict([body])[0]              # 1 = scam, 0 = not scam (cutoff 0.5)
print(f"Scam probability: {p_scam:.2f}  label: {label}")
