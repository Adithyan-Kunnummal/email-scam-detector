import joblib

model = joblib.load("baseline_model.joblib")

email = """MyGov ATO Bank transfer Account reset password"""

p_scam = model.predict_proba([email])[0][1]   # probability of scam (class 1)
label = model.predict([email])[0]             # 1 = scam, 0 = legitimate (cutoff 0.5)
print(f"Scam probability: {p_scam:.2f}  label: {label}")