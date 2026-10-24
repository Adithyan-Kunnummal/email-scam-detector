# Demo emails

Emails for the demo and walkthrough video, with the result the app gives using the DistilBERT
model in `scam_model/` (checked 24 Oct 2026). Paste the subject and body into the text box and
the sender into the sender field. The first six are also the "Try an example" buttons on the page.

These were written for the demo. They are not part of the training or test data, and the
results are a sanity check, not an evaluation (see PROJECT_CONTEXT.md section 5e).

## Good for the demo

| # | Email | Sender | Result | Why |
|---|---|---|---|---|
| 1 | "Tax refund" button: ATO refund, verify bank details, link to a raw IP address | ato-refunds@mygov-secure-au.com | High | model 0.999; lookalike sender, raw-IP link, urgency |
| 2 | "Missed parcel" button: $2.99 redelivery fee, link to auspost.redelivery-au.com | noreply@auspost-delivery.info | High | lookalike sender imitating auspost.com.au |
| 3 | "Visa fee" button: Home Affairs compliance fee by gift card or Bitcoin | immigration.officer@homeaffairs-gov.org | High | gift-card payment, lookalike sender |
| 4 | "Crypto tip" button: "I made $3,000 last week with this crypto trading platform" | sarah.wins88@gmail.com | Medium | the model scores it 0.005; the investment-scam rule keeps it out of Low |
| 5 | "Job offer" button: earn $800/week rating products, message HR on WhatsApp | hr.recruit2026@gmail.com | High | job-scam and WhatsApp rules (model alone: 0.016) |
| 6 | "Uni timetable" button: RMIT exam timetable in the myRMIT app | exams@rmit.edu.au | Medium | genuine, but the model scores it 0.66. Shows that Medium means "check first", not "scam" |
| 7 | "Linkt: You have an unpaid toll of $4.85. Pay now to avoid a $95 late fee: https://linkt-pay.top/au" | billing@linkt-au.top | High | the model scores it 0.003; the lookalike link and sender rules catch it |
| 8 | "Please review your recent activity at https://c0mmbank.com.au/review" | (none) | High | link imitates commbank.com.au (0 → o) |
| 9 | "Hi Mum, I broke my phone. This is my new number, please save it." | (none) | Medium | family-impersonation rule (model alone: 0.03) |
| 10 | "Congratulations! You have been selected to receive a $1,000 Woolworths voucher. Complete a short survey and pay a $2 shipping fee to claim your reward." | (none) | Medium | prize rule (model alone: 0.08) |
| 11 | "Hi everyone, reminder that Assignment 3 is due Friday 1 November at 11:59pm. Submit via Canvas." | lecturer@rmit.edu.au | Low | genuine |
| 12 | "Your AGL bill for 1 Aug - 31 Oct is $214.36, due on 20 November. View and pay your bill in the AGL app or at agl.com.au." | (none) | Low | genuine |

## Known false alarms (use in the report, not the demo)

| Email | Result | Why |
|---|---|---|
| "Your parcel is on its way. Tracking number: 33ABC123456. Estimated delivery: Tuesday. You can follow your delivery in the AusPost app." | High (0.85) | Short notification emails look like the phishing in the training data. Without the subject and greeting the same text scores 0.03, so the model is unstable on this kind of email. |
| "Your Medicare claim has been processed. We have paid $41.20 ... into your nominated bank account." | High (0.999) | Government and bank wording with no link. The model has seen few genuine emails like this. |
| "Your monthly eStatement ... is now available in the CommBank app. We will never ask you for your password or NetCode by email." | High (0.99) | Same reason. A genuine sender address does not lower the risk, by design, because addresses can be forged. |

## Screenshots for the OCR demo

Take screenshots of emails 1, 3 and 11 (for example, paste them into an email draft and screenshot it), crop them to just the email, and upload them on the "Upload screenshot" tab. Screenshots don't contain the real address behind a link, so the link rules work only when the address is visible in the text.
