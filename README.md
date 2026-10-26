# Haq Hisaab · हक़ हिसाब

**For India's daily-wage workers: speak your work story in your own language, find out exactly how much you are owed, and get the letters to claim it.**

Built on Sarvam AI: Saaras v3 · Sarvam Vision · Sarvam-105B · Bulbul v3.

## The problem

Most of India's workforce is informal: construction labourers, farm hands, brick-kiln workers, loaders and domestic workers. Wage theft is routine. Contractors pay less than the promised rate, skip overtime, and make unexplained deductions. The worker usually cannot do the legal maths, cannot read the attendance register the contractor keeps, and cannot write a complaint in English. So the money is simply lost.

## One user · one problem · one flow

**User:** Raju Yadav, a construction worker at a site in Pune. He speaks Hindi and signs with a thumbprint.

| Step | Input | What happens | Sarvam API |
|---|---|---|---|
| 1. Batao (tell) | Raju speaks: *"मैंने अक्टूबर में 26 दिन काम किया, ठेकेदार ने 600 रोज़ बोला था, पर सिर्फ 12000 दिए। 20 घंटे ओवरटाइम का कुछ नहीं दिया।"* | Speech → text in any of 22 Indian languages, language auto-detected | **Saaras v3** |
| 1b. Evidence (optional) | Photo of his hajri (attendance) card or wage slip | Indic handwriting and print → text | **Sarvam Vision** (Document AI) |
| 2. Hisaab (the maths) | — | Story / card → structured facts (days, promised rate, amount paid, overtime, deductions). Conflicts between the story and the card are flagged. | **Sarvam-105B** |
| 2b. | Facts | **Plain arithmetic, not AI**: 26 × ₹600 + 20 h × ₹75 × 2 (overtime is double, Code on Wages 2019 s.14) − ₹12,000 = **₹6,600 owed**. Also flags minimum-wage violations and deductions. | none (on purpose) |
| 3. Haq maango (claim) | Tap one button | Spoken explanation in his language, a polite-but-firm letter to the contractor, and a formal complaint to the district Labour Office | **Sarvam-105B** + **Bulbul v3** |

**Result:** Raju hears, in Hindi, that he is owed ₹6,600 and why, and gets a ready letter (Hindi) and complaint (English) to share on WhatsApp or print.

## Why it stands out

- **Niche, high impact:** wage recovery for informal workers. No library idea targets this user.
- **The AI never touches the money:** the LLM only extracts facts and writes text. Every rupee comes from deterministic, tested Python, and the model is instructed never to change a number.
- **Evidence from paper:** Sarvam Vision reads the contractor's own Hindi attendance card, and the app flags it when the card and the worker's story disagree.
- **Voice in, voice out:** usable by someone who cannot read.

### Refined from the idea library (not a copy)

- **#38 Freight-Invoice Reconciliation:** promised vs paid, flag the mismatch, draft a dispute letter in their language. Applied to a worker's wages instead of supplier invoices.
- **#46 Grievance Drafter:** a voice complaint becomes a structured, cited administrative complaint (the Labour Office under the Code on Wages, 2019).
- **#29 Scheme-to-Pocket:** interviewing informal and gig workers by voice in their language.

## Tested live on Sarvam AI: 10/10 passed

| Test | Result |
|---|---|
| Work stories → facts → correct amount owed: Hindi, Hinglish ("saade paanch sau" = 550), Tamil, Bengali (native ২৪ digits + deduction), Marathi ("2 hours extra daily" → 50 h overtime), Telugu (monthly salary → daily rate), English (paid in full → ₹0) | **7/7** |
| Real voice round-trip: Bulbul speaks → Saaras hears (detected `hi-IN`) → facts → ₹2,500 owed | **pass** |
| Sarvam Vision reads [the attendance card](samples/attendance_card.jpg): worker, contractor, site, month, 26 days, ₹600/day, ₹12,000 paid, 20 h overtime | **pass** (~6–8 s) |
| Hindi explanation + employer letter + Labour Office complaint all quote exactly ₹6,600, spoken by Bulbul | **pass** |

Full outputs, including the generated letters, are in [eval/results.md](eval/results.md). Rerun with `python eval/run_eval.py` (it has a hard credit cap).

## Run locally

```bash
pip install -r requirements.txt
cp .env.example .env        # then put your key in .env as SARVAM_API_KEY=...
python app.py               # open http://localhost:8000
```

**Zero-credit demo mode:** set `MOCK=1` in `.env`, or leave the key empty. The full UI runs on canned responses with no API calls. Every Sarvam response is also cached in memory, so repeating a demo step is free.

## Deploy

**Vercel:** Import the GitHub repo at vercel.com → New Project. Vercel detects FastAPI from `app.py` + `requirements.txt`. Add the environment variable `SARVAM_API_KEY`, then Deploy.

**Render:** New → Blueprint → pick this repo (it uses `render.yaml`) → set `SARVAM_API_KEY`.

Open the live HTTPS link on a phone: the mic and camera both work there.

## API

- `POST /api/story-voice` (multipart `audio`, ≤25 s) → transcript, detected language, facts
- `POST /api/story-text` `{text}` → facts
- `POST /api/evidence-photo` (multipart `image`, `language`) → text read by Sarvam Vision, facts
- `POST /api/calculate` `{facts}` → line-by-line wage calculation, flags, total due (no AI)
- `POST /api/claim` `{facts, language}` → spoken explanation (base64 WAV), employer letter, Labour Office complaint
- `GET /api/status` → mode, models, API usage counters

## 3-minute demo

1. Tap 🎙️ and say (or tap the Hindi sample): *"26 din kaam kiya, 600 roz bola tha, sirf 12000 diye, 20 ghante overtime ka kuch nahi diya."* Step 2 fills in and shows **You are owed ₹6,600**, line by line.
2. Tap **📷 Add card / slip** and choose `samples/attendance_card.jpg`. Sarvam Vision reads the Hindi card and the facts are confirmed "📷 from card".
3. Type a state minimum wage of 700 and watch the minimum-wage violation appear, with the extra amount due.
4. Tap **🔊 Explain to me & write my letters**. Raju hears the explanation in Hindi and gets the letter and the complaint. Switch the language to Tamil and run it again.

Not legal advice. Free legal aid in India: NALSA helpline **15100**.
