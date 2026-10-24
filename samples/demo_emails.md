# Demo emails

Emails for the demo and walkthrough video, with the result the app gives using the DistilBERT
model in `scam_model/` (checked 24 Oct 2026). Paste the subject and body into the text box and
the sender into the sender field. Emails 1–6 are also "Try an example" buttons on the page, as
are four more genuine emails (assignment reminder, electricity bill, dentist appointment, message
from a friend), which all come out Low.

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

## Genuine bank and government emails (the official-sender cap)

The model rates these genuine emails as scams (scores 0.85–0.999), because its training data has almost no genuine bank or government emails. **With their real sender address they are Medium**: the explanation says the address is official but could be faked, so check in the official app. **Without a sender address they stay High.** Good for showing in the demo why adding the sender helps, and for the report's limitations.

| Email | Sender | With sender | Without sender |
|---|---|---|---|
| "Your parcel is on its way. Tracking number: 33ABC123456. Estimated delivery: Tuesday. You can follow your delivery in the AusPost app." (with subject and greeting) | notifications@auspost.com.au | Medium | High (0.85) |
| "Your Medicare claim has been processed. We have paid $41.20 for your claim on 21 October into your nominated bank account. You can see your claims history in the Medicare app through myGov." | noreply@servicesaustralia.gov.au | Medium | High (0.999) |
| "Your monthly eStatement for your Everyday Account is now available in the CommBank app. We will never ask you for your password or NetCode by email." | noreply@commbank.com.au | Medium | High (0.99) |
| "Never share your password or PIN with anyone. Your new card has been sent and will arrive within 5 business days. Activate it in the NAB app." | no-reply@nab.com.au | Medium | High (0.84) |

A forged official sender does not get the same treatment if anything contradicts it:

| Email | Sender | Result | Why |
|---|---|---|---|
| "Your account is suspended. Verify your details at https://commbank-verify.com within 24 hours." | noreply@commbank.com.au | High | the link imitates commbank.com.au |
| "Your account is suspended. Verify your details at https://bit.ly/3xYz within 24 hours." | noreply@commbank.com.au | High | the link isn't an official website, so the address isn't trusted |
| "Your account is suspended. Reply to this email with your NetBank client number and password within 24 hours." | noreply@commbank.com.au | High | asks for a password by email |
| "Your account is suspended. Reply with your NetBank password within 24 hours." | commbank.support@outlook.com | High | personal webmail is never trusted |

## Screenshots for the OCR demo

Take screenshots of emails 1, 3 and 11 (for example, paste them into an email draft and screenshot it), crop them to just the email, and upload them on the "Upload screenshot" tab. Screenshots don't contain the real address behind a link, so the link rules work only when the address is visible in the text.
