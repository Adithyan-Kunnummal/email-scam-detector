const API_URL = "http://localhost:8000/check";
const LEVELS = {
  High:   { kicker: "High risk",   title: "Likely a scam",                 icon: "i-high", sub: "This email has strong signs of a scam. Don't act on it." },
  Medium: { kicker: "Medium risk", title: "Be careful – check first",      icon: "i-med",  sub: "There are some warning signs. Check with the organisation before you do anything." },
  Low:    { kicker: "Low risk",    title: "No strong warning signs found", icon: "i-low",  sub: "This doesn't mean it is safe. Stay careful with links and payment requests." }
};

const SAMPLES = {
  ato: {
    sender: "ato-refunds@mygov-secure-au.com",
    subject: "You are eligible for a tax refund of $1,284.60",
    body: "Australian Taxation Office\n\nDear taxpayer,\n\nAfter the annual calculation of your fiscal activity we have determined that you are eligible to receive a tax refund of $1,284.60.\n\nTo receive your refund you must verify your bank details within 24 hours, otherwise your refund will be cancelled.\n\nLog in here to confirm your details: http://203.0.113.45/mygov/refund-login\n\nRegards,\nATO Refunds Team"
  },
  parcel: {
    sender: "noreply@auspost-delivery.info",
    subject: "Your parcel could not be delivered",
    body: "Hi,\n\nWe attempted to deliver your parcel today but no one was home. Your parcel is being held at our depot.\n\nA redelivery fee of $2.99 is required. Please pay now to schedule a new delivery: https://auspost.redelivery-au.com/track?id=AP88213\n\nIf the fee is not paid within 48 hours the parcel will be returned to the sender.\n\nAustralia Post"
  },
  visa: {
    sender: "immigration.officer@homeaffairs-gov.org",
    subject: "FINAL NOTICE: Student visa compliance",
    body: "Department of Home Affairs\n\nOur records show a problem with your student visa (subclass 500). Your visa will be cancelled unless you act now.\n\nAn urgent compliance fee of $650 must be paid today. Payment is accepted by gift card or Bitcoin only. Reply to this email with the gift card codes.\n\nDo not tell your university about this matter. It is confidential.\n\nCompliance Section"
  },
  uni: {
    sender: "exams@rmit.edu.au",
    subject: "Your Semester 2 exam timetable is now available",
    body: "Hi Priya,\n\nYour personal exam timetable for Semester 2, 2026 is now available.\n\nYou can see it any time in the myRMIT app under Study > Exams. Please check the dates, times and locations, and contact Student Connect if you think there is a clash.\n\nGood luck with your exams.\n\nExaminations Team\nRMIT University"
  },
  invest: {
    sender: "sarah.wins88@gmail.com",
    subject: "I couldn't believe it either",
    body: "Hi!\n\nI made $3,000 last week with this crypto trading platform that a famous Australian businessman uses. It's a guaranteed return, and you can start with just $250.\n\nOur account manager will guide you through everything. Only a few spots are left this month, so sign up today.\n\nSarah"
  },
  job: {
    sender: "hr.recruit2026@gmail.com",
    subject: "Remote job offer - start today",
    body: "Hello,\n\nWe saw your resume online and think you are a great fit. Work from home 2 hours a day and earn $800/week rating products for online stores. No experience needed.\n\nMessage our HR team on WhatsApp to start today.\n\nRecruitment Team"
  }
};

const $ = (id) => document.getElementById(id);
const initialResultHTML = document.getElementById("result").innerHTML;
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const store = {
  get(k, d) { try { const v = localStorage.getItem(k); return v === null ? d : JSON.parse(v); } catch { return d; } },
  set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch {} }
};

/* ---------- text size ---------- */
function setLarge(on) {
  document.documentElement.classList.toggle("large-text", on);
  $("ts-std").setAttribute("aria-pressed", String(!on));
  $("ts-lg").setAttribute("aria-pressed", String(on));
  store.set("largeText", on);
}
$("ts-std").onclick = () => setLarge(false);
$("ts-lg").onclick = () => setLarge(true);
setLarge(store.get("largeText", false));

/* ---------- tabs ---------- */
const tabs = [$("tab-paste"), $("tab-shot")];
function selectTab(tab) {
  tabs.forEach((t) => {
    const on = t === tab;
    t.setAttribute("aria-selected", String(on));
    t.tabIndex = on ? 0 : -1;
  });
  $("pane-shot").hidden = tab.id !== "tab-shot";
  if (tab.id === "tab-shot") loadTesseract().catch(() => {});
}
tabs.forEach((t, i) => {
  t.onclick = () => selectTab(t);
  t.onkeydown = (e) => {
    if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
      const next = tabs[(i + (e.key === "ArrowRight" ? 1 : -1) + tabs.length) % tabs.length];
      selectTab(next); next.focus(); e.preventDefault();
    }
  };
});

/* ---------- screenshot OCR (Tesseract.js, runs in the browser) ---------- */
let tessPromise = null;
let ocrRunId = 0;
let thumbUrl = null;
function loadTesseract() {
  if (window.Tesseract) return Promise.resolve();
  if (!tessPromise) {
    tessPromise = new Promise((resolve, reject) => {
      const s = document.createElement("script");
      s.src = "https://cdn.jsdelivr.net/npm/tesseract.js@5.1.1/dist/tesseract.min.js";
      s.onload = resolve;
      s.onerror = () => { tessPromise = null; reject(new Error("load")); };
      document.head.appendChild(s);
    });
  }
  return tessPromise;
}
function ocrError(msg) {
  $("ocr").hidden = true;
  $("ocr-err").hidden = false;
  $("ocr-err-msg").textContent = msg;
}
async function runOcr(file) {
  if (!file) return;
  const runId = ++ocrRunId;
  $("image-preview").hidden = true; // Hide any previous image before processing a new one.
  if (!/^image\/(png|jpeg)$/.test(file.type)) return ocrError("That file isn't a PNG or JPG picture. Choose a screenshot instead.");
  if (file.size > 8 * 1024 * 1024) return ocrError("Please choose a screenshot smaller than 8 MB.");
  $("ocr-err").hidden = true; $("ocr-ok").hidden = true;
  $("ocr").hidden = false;
  if (thumbUrl) URL.revokeObjectURL(thumbUrl);
  thumbUrl = URL.createObjectURL(file);
  $("thumb").src = thumbUrl;
  $("image-preview").hidden = false; // Keep the image visible after OCR completes.
  $("ocr-msg").textContent = "Reading the text in your screenshot…";
  $("ocr-bar").style.width = "4%";
  try {
    await loadTesseract();
    const worker = await Tesseract.createWorker("eng", 1, {
      logger: (m) => {
        if (m.status === "recognizing text") {
          $("ocr-bar").style.width = Math.round(10 + m.progress * 90) + "%";
          $("ocr-msg").textContent = "Reading the text… " + Math.round(m.progress * 100) + "%";
        }
      }
    });
    let data;
    try {
      ({ data } = await worker.recognize(file));
    } finally {
      await worker.terminate();
    }
    if (runId !== ocrRunId) return; // Don't overwrite the form if the user pressed Clear.
    const text = (data.text || "").trim();
    if (text.replace(/\s/g, "").length < 25) {
      return ocrError("We couldn't find much text in that picture. Try a clearer, closer screenshot, or paste the email text instead.");
    }
    $("ocr").hidden = true;
    $("body").value = text;
    $("ocr-ok").hidden = false;
    $("body").focus();
  } catch (e) {
    if (runId === ocrRunId) {
      ocrError("We couldn't read that screenshot. Check your internet connection the first time you use this, or paste the email text instead.");
    }
  }
}
$("file").onchange = (e) => runOcr(e.target.files[0]);
const drop = $("drop");
["dragenter", "dragover"].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.add("over"); }));
["dragleave", "drop"].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.remove("over"); }));
drop.addEventListener("drop", (e) => runOcr(e.dataTransfer.files[0]));

/* ---------- demo mode: mirrors the rules in app.py when the backend isn't running ----------
   (except the official-sender cap and the full lookalike check, which need official_domains.txt) */
const URGENCY = ["urgent", "immediately", "within 24 hours", "suspended", "verify your", "final notice", "act now", "account will be", "locked"];
const MONEY = ["gift card", "bitcoin", "crypto", "refund", "payment", "bank details", "wire", "fee", "overdue"];
const CREDENTIALS = ["password", "sign in", "log in", "login", "confirm your details", "security code"];
const SAFE_CREDENTIAL_PHRASES = /(never|not|won't|will not|don't|do not) (ever )?(ask|request|provide|share|give|send|disclose)[^.]{0,40}(password|log ?in|sign in|security code|netcode|pin)/g;
const SECRET_REQUEST = /\b(reply|respond|send|provide|tell us|give us)\b[^.=\n]{0,60}\b(password|passcode|pin|security code|netcode|one[- ]time code|card number)\b/;
const INVESTMENT = /guaranteed (returns?|profits?|income)|risk[- ]free (investment|returns?|profit)|crypto(currency)? (trading|investment|platform)|trading (platform|bot|signals?)|double your (money|investment)|investment opportunity|passive income|returns? of \d+ ?%|(made|earned|making|earning) \$[\d,]+ (last|this|a|per|in) (week|month|day)|account manager will guide/;
const JOB = /(earn|make|paid) (up to )?\$[\d,]+ ?(\/|per|a|an|each) ?(day|week|hour|task)|work (from|at) home[^.]{0,60}(earn|\$)|no experience (needed|required|necessary)|(rating|reviewing|liking) (products|videos|hotels|apps)|task[- ]based (job|work)/;
const OFF_PLATFORM = /(message|contact|text|add|chat with|reach) (us|me|our( [a-z]+){1,2})? ?(on|via) (whatsapp|telegram|signal|wechat)/;
const GIFT_CARD_PAYMENT = /(pay|paid|payment|purchase|buy)[^.]{0,40}gift ?cards?|gift ?card (codes?|numbers?)/;
const PRIZE = /you('ve| have) (won|been selected)|congratulations[^.]{0,40}(won|winner|selected)|claim your (prize|reward|winnings|voucher)|lottery winner/;
const FAMILY = /\b(hi|hey) (mum|mom|dad)\b[^.]{0,80}(new number|broke|lost)|this is my new number|my (old )?phone (is |got )?(broken|broke|lost|died)[^.]{0,80}(new number|this number)/;
const STRONG_FLAGS = ["investment", "job", "off_platform", "gift_card_payment", "prize", "family_impersonation", "secret_request"];
const TRUSTED = ["ato", "mygov", "auspost", "centrelink", "servicesaustralia", "commbank", "westpac", "anz", "nab", "rmit", "homeaffairs"];
function demoSignals(text, sender) {
  const t = text.toLowerCase(), found = [], flags = [];
  const add = (flag, msg) => { if (!found.includes(msg)) { found.push(msg); flags.push(flag); } };
  if (URGENCY.some((k) => t.includes(k))) add("urgency", "It pressures you to act quickly, a common scam tactic.");
  if (MONEY.some((k) => t.includes(k))) add("money", "It mentions money, refunds or payment.");
  const tReq = t.replace(SAFE_CREDENTIAL_PHRASES, "");
  if (CREDENTIALS.some((k) => tReq.includes(k))) add("credentials", "It asks you to sign in or share login details.");
  if (SECRET_REQUEST.test(tReq)) add("secret_request", "It asks you to send a password, PIN or code. Real organisations never ask for these by email.");
  if (GIFT_CARD_PAYMENT.test(t)) add("gift_card_payment", "It asks for payment with gift cards. Real organisations never do this.");
  if (INVESTMENT.test(t)) add("investment", "It promises easy or guaranteed money from investing, a sign of investment scams.");
  if (JOB.test(t)) add("job", "It offers easy money for simple work, a sign of job scams.");
  if (OFF_PLATFORM.test(t)) add("off_platform", "It asks you to continue the conversation on WhatsApp, Telegram or a similar app.");
  if (PRIZE.test(t)) add("prize", "It says you have won or been selected for a prize, a common scam hook.");
  if (FAMILY.test(t)) add("family_impersonation", "It claims to be a family member with a new number. Call them on the number you already have before doing anything.");
  for (const url of text.match(/https?:\/\/[^\s<>"')]+/gi) || []) {
    const host = url.toLowerCase().replace(/^https?:\/\//, "").split(/[\/?#]/)[0];
    if (/^[\d.]+(:\d+)?$/.test(host)) add("raw_ip_link", "A link goes to a raw number address instead of a website name.");
    else if (TRUSTED.some((b) => host.includes(b)) && !/\.(gov|com|edu)\.au$/.test(host)) add("lookalike_link", `A link mentions a trusted brand but goes to '${host}'.`);
  }
  if (sender && sender.includes("@")) {
    const domain = sender.toLowerCase().split("@").pop();
    if (["ato", "mygov", "centrelink"].some((b) => t.includes(b)) && !domain.endsWith(".gov.au"))
      add("fake_gov_sender", `It claims to be from government but was sent from '${domain}'.`);
  }
  return { found, flags };
}
function demoCheck(text, sender) {
  const words = ["verify", "refund", "suspended", "gift card", "bitcoin", "urgent", "click", "confirm", "fee", "cancelled", "final notice", "dear customer", "dear taxpayer", "confidential"];
  const hits = words.filter((w) => text.toLowerCase().includes(w)).length;
  const p = Math.min(0.97, 0.06 + (1 - Math.exp(-0.4 * hits)));
  const { found, flags } = demoSignals(text, sender);
  const score = Math.min(1, p + 0.05 * found.length);
  // as in app.py: a lookalike link or two strong signs are High on their own, one strong sign is never Low
  const strong = flags.filter((f) => STRONG_FLAGS.includes(f)).length;
  const level = flags.includes("lookalike_link") || strong >= 2 || score >= 0.7 ? "High"
    : score >= 0.2 || strong ? "Medium" : "Low";
  const steps = {
    High: ["Don't click links, open attachments or reply.", "Contact the organisation through its official app or website.", "Report it to Scamwatch (scamwatch.gov.au) and delete it."],
    Medium: ["Don't click links in this email.", "Check with the organisation directly using contact details you already trust."],
    Low: ["No strong warning signs found, but stay careful with links and payment requests."]
  }[level];
  return {
    risk_level: level, scam_probability: Math.round(p * 1000) / 1000,
    reasons: found.length ? found : [p >= 0.5 ? "The wording resembles scam emails the model was trained on." : "No specific warning signs detected."],
    flags, next_steps: steps, model: "demo (simulated)"
  };
}

// The progress UI advances only on real events, never on a fake percentage.
async function callApi(text, sender, controller, onResponse, onFallback) {
  const timer = setTimeout(() => controller.abort(), 8000);
  try {
    const r = await fetch(API_URL, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, sender: sender || null }), signal: controller.signal
    });
    if (!r.ok) throw new Error("HTTP " + r.status);
    onResponse(); // The server really responded; now process its returned JSON.
    return { data: await r.json(), live: true };
  } catch {
    onFallback(); // The server failed or timed out; this is NOT a live model result.
    return { data: demoCheck(text, sender), live: false };
  } finally { clearTimeout(timer); }
}

/* ---------- evidence cards and text highlighting ----------
   These are explanations of observable rule matches, NOT token-level
   attribution of the DistilBERT model's decision. No links are activated. */
const WARNING_INFO = {
  urgency: {
    title: "Urgent or pressuring language",
    why: "Scammers often create time pressure so people act before checking the request. Legitimate messages can also have deadlines.",
    check: "Pause and verify the request using the organisation's official website or app."
  },
  money: {
    title: "Money or payment mentioned",
    why: "Requests involving refunds, fees or bank details deserve extra verification. Mentioning money alone does not prove a scam.",
    check: "Check whether the charge or refund exists by visiting the organisation independently."
  },
  credentials: {
    title: "Account details requested",
    why: "Links asking for passwords, verification codes or banking information can be used to steal accounts or money.",
    check: "Do not enter details through the email link. Sign in using an app or address you already trust."
  },
  lookalike_link: {
    title: "Website address needs checking",
    why: "A URL can contain a brand name yet lead to an unrelated domain. The visible address is not proof of who owns the website.",
    check: "Compare the actual domain with the address published on the organisation's official site. Do not open the suspicious link."
  },
  raw_ip_link: {
    title: "Unusual numerical link",
    why: "A link pointing to a numerical IP address rather than a recognisable domain can be suspicious, especially for account-related requests.",
    check: "Avoid the link and navigate to the service through its official website instead."
  },
  fake_gov_sender: {
    title: "Sender domain may not match",
    why: "The sender's email domain may not be associated with the government organisation named in the message. A sender address alone is not proof of authenticity.",
    check: "Verify the sender and request through an official government website, not by replying."
  },
  gift_card_payment: {
    title: "Gift card payment requested",
    why: "Scammers commonly demand gift card codes because they can be redeemed quickly and are difficult to recover.",
    check: "Do not buy or send gift cards to pay a fee or resolve an account issue."
  },
  investment: {
    title: "Investment returns promised",
    why: "Guaranteed profits or unusually easy returns are common features of investment scams. Investment returns are never guaranteed.",
    check: "Verify the business independently and avoid sending funds based only on the email."
  },
  job: {
    title: "Unusually easy job offer",
    why: "Offers of high pay for minimal work can be a way to obtain personal details or recruit victims into payment scams.",
    check: "Verify the employer and job posting independently; never pay money to start a job."
  },
  off_platform: {
    title: "Moved to an external messaging app",
    why: "A request to switch to WhatsApp or Telegram may bypass the platform's normal checks and reporting features.",
    check: "Confirm who you are talking to through a known, trusted channel."
  },
  prize: {
    title: "Unexpected prize or reward",
    why: "Unexpected prizes can be used to lure people into clicking links or paying a 'release' fee.",
    check: "Verify the offer independently and do not pay to claim an unsolicited prize."
  },
  family_impersonation: {
    title: "Possible family impersonation",
    why: "Scammers may pretend to be a relative using a new phone number to request immediate help or money.",
    check: "Call the person on a number you already know before responding."
  },
  general: {
    title: "Additional analysis observation",
    why: "This observation comes from the email analysis. The interface cannot identify an exact supporting phrase for every model prediction.",
    check: "Consider the entire email and verify unexpected requests independently."
  },
  none: {
    title: "No matching warning patterns",
    why: "The available rules did not identify a specific warning in this email. A low-risk assessment does not guarantee safety.",
    check: "Check the sender and any unexpected links before acting."
  }
};

function inferWarningKey(reason) {
  const r = String(reason).toLowerCase();
  if (/no specific warning signs|no strong warning signs/.test(r)) return "none";
  if (/gift card/.test(r)) return "gift_card_payment";
  if (/investment|guaranteed money|guaranteed returns/.test(r)) return "investment";
  if (/easy money|job scam|simple work/.test(r)) return "job";
  if (/whatsapp|telegram|messaging app/.test(r)) return "off_platform";
  if (/family member|new number/.test(r)) return "family_impersonation";
  if (/prize|winner/.test(r)) return "prize";
  if (/raw number address|raw ip|numerical ip/.test(r)) return "raw_ip_link";
  if (/mentions a trusted brand|lookalike|link.*unofficial domain|trusted brand but/.test(r)) return "lookalike_link";
  if (/government but was sent|sender.*domain|sender.*unofficial domain/.test(r)) return "fake_gov_sender";
  if (/login details|log in|sign in|password|security code|credentials/.test(r)) return "credentials";
  if (/pressures you|quickly|act urgently|urgency/.test(r)) return "urgency";
  if (/money|refund|payment|bank details|fee/.test(r)) return "money";
  return null;
}

function getWarningItems(res) {
  const reasons = Array.isArray(res.reasons) ? res.reasons : [];
  const flags = Array.isArray(res.flags) ? res.flags : [];
  const aligned = reasons.length === flags.length;
  if (!reasons.length) return [{ key: "none", text: "No specific warning signs detected." }];
  return reasons.map((text, index) => {
    const inferred = inferWarningKey(text);
    const suggested = aligned ? flags[index] : null;
    const key = inferred || (Object.hasOwn(WARNING_INFO, suggested) ? suggested : "general");
    return { key, text: String(text) };
  });
}

function renderWarningCards(items) {
  return `<div class="warning-cards">
    ${items.map(({key, text}, index) => {
      const info = WARNING_INFO[key] || WARNING_INFO.general;
      const neutral = key === "none";
      return `<details class="warning-card${neutral ? " warning-neutral" : ""}" ${index === 0 && !neutral ? "open" : ""}>
        <summary>
          <span class="warning-symbol" aria-hidden="true">${neutral ? "i" : "!"}</span>
          <span class="warning-heading"><strong>${esc(info.title)}</strong><span>${esc(text)}</span></span>
          <svg class="warning-chevron" width="18" height="18" aria-hidden="true"><use href="#i-chev"/></svg>
        </summary>
        <div class="warning-card-content">
          <p><strong>Why it matters</strong> ${esc(info.why)}</p>
          <p><strong>What to check</strong> ${esc(info.check)}</p>
        </div>
      </details>`;
    }).join("")}
  </div>`;
}

// Highlight only phrases matched by known rules. Text remains text, never a live link.
// Keep original input editable; present a separate, read-only annotated copy.
const HIGHLIGHT_RULES = {
  urgency: [/\b(?:urgent(?:ly)?|immediately|within\s+(?:24|48)\s+hours?|act now|final notice|suspended|will be cancelled|returned to the sender|only a few spots)\b/gi],
  money: [/\b(?:redelivery fee|bank details|refunds?|payments?|pay now|gift cards?|bitcoin|crypto|fees?|overdue)\b/gi, /\$\s?\d[\d,.]*/g],
  credentials: [/\b(?:verify your (?:bank details|identity|password)|confirm your details|log in|login|sign in|password|security code|gift card codes)\b/gi],
  gift_card_payment: [/\b(?:gift cards?|gift card codes|pay(?:ment)? (?:is )?accepted by gift card)\b/gi],
  investment: [/\b(?:guaranteed returns?|guaranteed profits?|crypto trading platform|risk[- ]free investment|account manager will guide|passive income|investment opportunity)\b/gi],
  job: [/\b(?:work from home|no experience needed|rating products|remote job offer|earn \$[\d,]+\/?week)\b/gi],
  off_platform: [/\b(?:WhatsApp|Telegram|Signal|WeChat)\b/gi],
  prize: [/\b(?:claim your prize|lottery winner|you have won|you've won|congratulations)\b/gi],
  family_impersonation: [/\b(?:this is my new number|my phone is broken|hi mum|hi dad)\b/gi]
};

function suspiciousUrlSpans(text, kind) {
  const spans = [];
  const re = /https?:\/\/[^\s<>"')]+/gi;
  for (const m of text.matchAll(re)) {
    const urlText = m[0].replace(/[.,;!?]+$/, "");
    let hostname;
    try { hostname = new URL(urlText).hostname.toLowerCase(); }
    catch { continue; }
    const numericHost = /^(?:\d{1,3}\.){3}\d{1,3}$/.test(hostname);
    const lookalikeHost = TRUSTED.some((brand) => hostname.includes(brand)) && !/\.(?:gov|com|edu)\.au$/.test(hostname);
    if ((kind === "raw_ip_link" && numericHost) || (kind === "lookalike_link" && lookalikeHost)) {
      spans.push({ start: m.index, end: m.index + urlText.length, kind: "link" });
    }
  }
  return spans;
}

function annotatedTextHTML(text, warningKeys, sender) {
  const spans = [];
  const active = new Set(warningKeys);
  for (const key of active) {
    for (const rule of HIGHLIGHT_RULES[key] || []) {
      for (const m of text.matchAll(rule)) {
        if (m[0].length) spans.push({ start: m.index, end: m.index + m[0].length, kind: key });
      }
    }
    if (key === "raw_ip_link" || key === "lookalike_link") {
      spans.push(...suspiciousUrlSpans(text, key));
    }
  }
  if (active.has("fake_gov_sender") && sender) {
    const start = text.indexOf("From: " + sender);
    if (start >= 0) spans.push({ start: start + 6, end: start + 6 + sender.length, kind: "sender" });
  }
  // If multiple rules find overlapping spans, prefer the longest matching phrase.
  spans.sort((a, b) => a.start - b.start || b.end - a.end);
  let cursor = 0, count = 0, html = "";
  for (const span of spans) {
    if (span.start < cursor || span.end > text.length) continue;
    html += esc(text.slice(cursor, span.start));
    html += `<mark class="evidence-mark evidence-${span.kind}" title="Rule-based match">${esc(text.slice(span.start, span.end))}</mark>`;
    cursor = span.end;
    count++;
  }
  html += esc(text.slice(cursor));
  return { html, count };
}

function renderEmailEvidence(items, email) {
  const body = (email && email.body) || "";
  const subject = (email && email.subject) || "";
  const sender = (email && email.sender) || "";
  const header = [subject ? "Subject: " + subject : "", sender ? "From: " + sender : ""].filter(Boolean).join("\n");
  const source = (header ? header + "\n\n" : "") + body;
  const { html, count } = annotatedTextHTML(source, items.map((item) => item.key), sender);
  return `<details class="highlight-review" ${count ? "open" : ""}>
      <summary><svg width="17" height="17" aria-hidden="true"><use href="#i-chev"/></svg>
        ${count ? `Highlighted email <span class="evidence-count">${count} rule match${count === 1 ? "" : "es"}</span>` : "Review analysed email"}
      </summary>
      <p class="highlight-note">${count
        ? "Coloured phrases are matches from simple detection rules—not an explanation of how DistilBERT made its prediction. Matches alone don't prove a scam."
        : "No exact phrases matched the current highlighting rules. The AI can still assess overall wording; no phrase-level model explanation is available."}</p>
      <div class="annotated-email" role="region" aria-label="Read-only email with highlighted warning phrases">${html}</div>
      <p class="highlight-note">This is a read-only copy. Edit the original email on the left and select Check this email to update the analysis. Links cannot be opened here.</p>
    </details>`;
}

/* ---------- animated scan panel ----------
   Stage 1 is completed input preparation, stage 2 waits for the actual
   FastAPI response, stage 3 prepares a real report or demo fallback.
   The moving bar is deliberately indeterminate: we do not know the model's %.
*/
function renderScanning(fromScreenshot) {
  const card = $("result");
  card.className = "card result scanning";
  card.setAttribute("aria-busy", "true");
  card.innerHTML = `
    <div class="scan-shell">
      <div class="scan-emblem" aria-hidden="true">
        <svg width="42" height="42" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
          <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
          <path d="m9 12 2 2 4-4"/>
        </svg>
      </div>
      <div class="scan-label">EMAIL SECURITY CHECK</div>
      <h2 id="res-h" tabindex="-1">Checking your email…</h2>
      <p class="scan-description" id="scan-description" role="status">Waiting for the local analysis server to respond.</p>
      <div class="scan-progress-track" aria-hidden="true"><span></span></div>
      <p class="scan-progress-caption">Analysis in progress · No estimated percentage</p>
      <ol class="scan-steps" aria-label="Analysis stages">
        <li class="scan-step is-done" id="scan-prepared">
          <span class="scan-step-marker" aria-hidden="true">✓</span>
          <span class="scan-step-copy"><strong>${fromScreenshot ? "Screenshot text ready" : "Email text ready"}</strong><small>Prepared the text you reviewed</small></span>
        </li>
        <li class="scan-step is-active" id="scan-server">
          <span class="scan-step-marker" aria-hidden="true"><span class="scan-mini-spinner"></span></span>
          <span class="scan-step-copy"><strong>Contacting local AI</strong><small id="scan-server-detail">Awaiting the Python backend</small></span>
        </li>
        <li class="scan-step" id="scan-report">
          <span class="scan-step-marker" aria-hidden="true">3</span>
          <span class="scan-step-copy"><strong>Preparing your report</strong><small>Risk level, reasons and advice</small></span>
        </li>
      </ol>
      <p class="scan-privacy">Your screenshot remains in your browser; the text is sent to your configured analysis server.</p>
    </div>`;
}

function scanningStage(stage) {
  const server = $("scan-server");
  const report = $("scan-report");
  if (!server || !report) return; // A previous scan may have been cleared.
  server.classList.remove("is-active");
  server.classList.add(stage === "response" ? "is-done" : "is-skipped");
  server.querySelector(".scan-step-marker").textContent = stage === "response" ? "✓" : "!";
  $("scan-server-detail").textContent = stage === "response" ? "Response received" : "Server unavailable or timed out";
  report.classList.add("is-active");
  report.querySelector(".scan-step-marker").innerHTML = '<span class="scan-mini-spinner"></span>';
  $("res-h").textContent = stage === "response" ? "Preparing your report…" : "Checking with browser rules…";
  $("scan-description").textContent = stage === "response"
    ? "Reading the analysis returned by your Python backend."
    : "The local AI could not be reached. Preparing a clearly labelled demo result instead.";
}

/* ---------- render ---------- */
let last = null;
function render(res, live, email) {
  const L = LEVELS[res.risk_level] || LEVELS.Medium;
  const pct = Math.round(res.scam_probability * 100);
  const card = $("result");
  const warningItems = getWarningItems(res);
  card.removeAttribute("aria-busy");
  card.className = "card result fresh lv-" + res.risk_level;
  card.innerHTML = `
    <div class="verdict">
      <div class="source-banner ${live ? "source-live" : "source-demo"}" role="status">
        ${live ? "LIVE MODEL RESULT — Analysed by your local Python backend." : "DEMO ONLY — The Python backend could not be reached. This preview uses simple browser rules, not your trained AI model."}
      </div>
      <div class="verdict-head">
        <svg class="icon tone" aria-hidden="true"><use href="#${L.icon}"/></svg>
        <div>
          <div class="kicker tone">${L.kicker}</div>
          <h2 id="res-h" class="tone" tabindex="-1">${L.title}</h2>
          <p class="sub">${L.sub}</p>
        </div>
      </div>
      <div class="levels" aria-hidden="true">
        ${["Low", "Medium", "High"].map((l) => `<div class="s-${l}${l === res.risk_level ? " on" : ""}"><i></i>${l}</div>`).join("")}
      </div>
    </div>
    <div class="result-body">
      <div>
        <h3>Why we think this</h3>
        <p class="warning-intro">Select any finding to learn why it matters and how to verify it.</p>
        ${renderWarningCards(warningItems)}
      </div>
      <div class="evidence-section">
        <h3>Where we noticed it</h3>
        ${renderEmailEvidence(warningItems, email)}
      </div>
      <div>
        <h3>What to do next</h3>
        <ol class="list steps">${res.next_steps.map((s) => `<li><span>${esc(s)}</span></li>`).join("")}</ol>
      </div>
      ${res.risk_level !== "Low" ? `
      <div class="help">
        <p><b>Already clicked a link or paid?</b> Call your bank now, using the number on your card.</p>
        <p>For free help with stolen personal details, call IDCARE on <b class="mono">1800 595 160</b>.</p>
      </div>` : ""}
      <div class="divider"></div>
      <div class="actions">
        <button type="button" class="btn btn-soft" id="share"><svg width="20" height="20" aria-hidden="true"><use href="#i-share"/></svg> Share with someone I trust</button>
        <textarea class="copybox" id="copybox" readonly hidden aria-label="Summary to share"></textarea>
        <div class="feedback">
          <span class="label" id="fb-label">Do you know what this email really is?</span>
          <div class="row" role="group" aria-labelledby="fb-label">
            <button type="button" class="btn btn-soft" data-fb="scam" aria-pressed="false">It's a scam</button>
            <button type="button" class="btn btn-soft" data-fb="safe" aria-pressed="false">It's genuine</button>
          </div>
        </div>
        <p class="status" id="status" role="status"></p>
        <details>
          <summary><svg width="16" height="16" aria-hidden="true"><use href="#i-chev"/></svg> Details</summary>
          <div class="details-body">
            <p>The AI model's scam score for this email:</p>
            <div class="meter" role="img" aria-label="Scam score ${pct} out of 100"><i style="left:${pct}%"></i></div>
            <div class="meter-scale"><span style="left:0">0</span><span style="left:40%">40</span><span style="left:70%">70</span><span style="left:100%">100</span></div>
            <dl class="kv">
              <dt>Model score</dt><dd>${res.scam_probability.toFixed(3)}</dd>
              <dt>Warning signs</dt><dd>${res.flags && res.flags.length ? esc(res.flags.join(", ")) : "See explanations above"}</dd>
              <dt>Model</dt><dd>${esc(res.model)}</dd>
              <dt>Checked by</dt><dd><span class="mode ${live ? "live" : ""}">${live ? "Local server" : "Demo mode in this page"}</span></dd>
            </dl>
            <p class="small">The bar shows the raw model score, while the Low / Medium / High category also accounts for rule-based warning signs. These thresholds are provisional. ${live ? "" : "To use your trained model, start the Python backend in VS Code with <span class=\"mono\">uvicorn app:app --reload</span>."}</p>
          </div>
        </details>
      </div>
    </div>`;
  last = res;

  $("share").onclick = shareSummary;
  card.querySelectorAll("[data-fb]").forEach((b) => b.onclick = () => feedback(b));
}

function summaryText() {
  const L = LEVELS[last.risk_level];
  return `I checked an email with Scam Email Checker.\n` +
    `Result: ${L.kicker} – ${L.title}\n` +
    `Why:\n${last.reasons.map((r) => "• " + r).join("\n")}\n` +
    `Suggested next steps:\n${last.next_steps.map((s) => "• " + s).join("\n")}\n` +
    `Can you help me check it before I do anything?`;
}
async function shareSummary() {
  const text = summaryText();
  try {
    await navigator.clipboard.writeText(text);
    $("status").textContent = "Summary copied. Paste it into a message or email to someone you trust.";
  } catch {
    const box = $("copybox");
    box.hidden = false; box.value = text; box.focus(); box.select();
    $("status").textContent = "Copy the selected summary (Ctrl+C), then paste it into a message.";
  }
}
function feedback(btn) {
  document.querySelectorAll("[data-fb]").forEach((b) => b.setAttribute("aria-pressed", String(b === btn)));
  // Only the verdict is kept, never the email text.
  const log = store.get("feedback", []);
  log.push({ at: new Date().toISOString(), predicted: last.risk_level, score: last.scam_probability, user_says: btn.dataset.fb });
  store.set("feedback", log);
  $("status").textContent = "Thanks. Your answer is saved on this device only and helps us test the checker.";
}

/* ---------- clear the form and previous result ---------- */
let scanId = 0;
let scanAbort = null;
let scanLoadingTimer = null; // Show the scanning panel only when the API takes longer than 250 ms.
function clearForm() {
  scanId++; // Discard results arriving from a scan that was cleared.
  clearTimeout(scanLoadingTimer); // Stop a pending loading screen from appearing after Clear.
  scanLoadingTimer = null;
  if (scanAbort) scanAbort.abort();
  scanAbort = null;
  $("check").disabled = false;
  $("check").textContent = "Check this email";
  document.querySelectorAll("[data-sample]").forEach((b) => { b.disabled = false; });
  ocrRunId++; // Ignore OCR results still processing in the background.
  $("form").reset();
  $("body-err").textContent = "";
  $("ocr").hidden = true;
  $("ocr-err").hidden = true;
  $("ocr-ok").hidden = true;
  $("image-preview").hidden = true; // Remove the preview when Clear is clicked.
  $("ocr-bar").style.width = "0";
  if (thumbUrl) URL.revokeObjectURL(thumbUrl);
  thumbUrl = null;
  $("thumb").removeAttribute("src");
  const card = $("result");
  card.removeAttribute("aria-busy");
  card.className = "card result";
  card.innerHTML = initialResultHTML;
  last = null;
  selectTab($("tab-paste"));
  $("body").focus();
}
$("clear").addEventListener("click", clearForm);

/* ---------- submit ---------- */
async function check(moveFocus) {
  const btn = $("check");
  if (btn.disabled) return; // Avoid simultaneous scans or accidental double submissions.
  const subject = $("subject").value.trim();
  const body = $("body").value.trim();
  const sender = $("sender").value.trim();
  $("body-err").textContent = "";
  if (body.length < 20) {
    $("body-err").textContent = "Paste the email text first. It needs at least a sentence or two.";
    if (!$("pane-shot").hidden) selectTab($("tab-paste"));
    $("body").focus();
    return;
  }
  if (body.length > 20000) {
    $("body-err").textContent = "That's very long. Paste just the email itself, without earlier replies.";
    return;
  }
  const thisScan = ++scanId;
  scanAbort = new AbortController();
  btn.disabled = true;
  btn.innerHTML = `<svg class="spin" width="22" height="22" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" stroke-width="3" stroke-dasharray="40 20"/></svg> Checking…`;
  document.querySelectorAll("[data-sample]").forEach((b) => { b.disabled = true; });
  const text = subject ? subject + "\n\n" + body : body;
  const fromScreenshot = !$("ocr-ok").hidden;
  // Avoid flashing the scanning panel when DistilBERT returns almost instantly.
  // This is a 250 ms SHOW delay, not a delay to the model or its result.
  scanLoadingTimer = setTimeout(() => {
    if (thisScan !== scanId) return;
    scanLoadingTimer = null;
    renderScanning(fromScreenshot);
    if (moveFocus && window.innerWidth < 940) {
      $("result").scrollIntoView({
        behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth",
        block: "nearest"
      });
    }
  }, 250);
  try {
    const { data, live } = await callApi(text, sender, scanAbort,
      () => { if (thisScan === scanId) scanningStage("response"); },
      () => { if (thisScan === scanId) scanningStage("fallback"); }
    );
    if (thisScan !== scanId) return; // User pressed Clear while the request was running.
    clearTimeout(scanLoadingTimer); // If the API finished quickly, never display the scanning panel.
    scanLoadingTimer = null;
    render(data, live, { body, subject, sender });
    if (moveFocus) {
      const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
      $("result").scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "start" });
      $("res-h").focus({ preventScroll: true });
    }
  } finally {
    if (thisScan === scanId) {
      clearTimeout(scanLoadingTimer);
      scanLoadingTimer = null;
      scanAbort = null;
      btn.disabled = false;
      btn.textContent = "Check this email";
      document.querySelectorAll("[data-sample]").forEach((b) => { b.disabled = false; });
    }
  }
}
$("form").addEventListener("submit", (e) => { e.preventDefault(); check(true); });

function loadSample(key) {
  const s = SAMPLES[key];
  $("sender").value = s.sender; $("subject").value = s.subject; $("body").value = s.body;
  $("ocr-ok").hidden = true;
  selectTab($("tab-paste"));
}
document.querySelectorAll("[data-sample]").forEach((b) => b.onclick = () => { loadSample(b.dataset.sample); check(true); });

// Start with an empty form and an empty results panel.
// The sample buttons still let you test the design with one click.

