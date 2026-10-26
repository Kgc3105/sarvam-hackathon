# Bolo Khata · बोलो खाता

**Speak your udhaar. We keep the khata and send polite reminders in your customer's language.**

A voice-first credit ledger for kirana shop owners, built on Sarvam AI.

## One user · one problem · one flow

- **User:** Ramesh-bhai, who runs a small kirana store. He speaks Hindi; his customers speak Hindi, Tamil, Bengali and other languages.
- **Problem:** Udhaar (store credit) lives in a paper notebook. Entries get lost, totals are guessed, and asking a regular customer for money is awkward, especially in a language he doesn't write.
- **Flow:**
  1. **Input:** he taps the mic and says, in any Indian language or code-mixed speech, *"Ramesh ne 200 ka atta aur 50 ka tel udhaar liya, aur Sunita ne 300 wapas diye"*.
  2. The khata updates instantly: Ramesh **+₹250** (atta, oil), Sunita **−₹300**, with running balances.
  3. **Result:** he taps **🔊 Voice reminder** next to a customer, picks that customer's language, and gets a warm, respectful reminder as a **voice note** (plus text he can share on WhatsApp).

## AI task → Sarvam API

| AI task | Sarvam API / model |
|---|---|
| Shopkeeper's spoken entry → text, auto-detecting the language | **Saaras v3** speech-to-text (`saaras:v3`, `language_code=unknown`) |
| Free-form sentence (any language, number words like "do sau") → structured ledger entries (customer, credit/payment, amount, items) | **Sarvam-105B** chat completions (`sarvam-105b`) |
| Polite reminder in the customer's language and native script | **Sarvam-105B** chat completions |
| Reminder → natural voice note | **Bulbul v3** text-to-speech (`bulbul:v3`, speaker `priya`) |

## Refined from the idea library

Not a copy of any one idea. It refines three library ideas for a user none of them targeted, the smallest business in India:
- **#36 Dispatcher-in-Your-Pocket:** voice notes → structured events, applied here to a shop ledger.
- **#15 / #24 Finance Ops / Accounts Payable:** ledger and reconciliation, shrunk from ERP scale down to a corner shop.
- **#7 Sales Agent:** reminders and follow-ups, as a friendly voice note in the customer's own language.

## Run locally

```bash
pip install -r requirements.txt
cp .env.example .env        # then put your key in .env as SARVAM_API_KEY=...
python app.py               # open http://localhost:8000
```

**Zero-credit demo mode:** set `MOCK=1` in `.env`, or leave the key empty. The full UI then runs on canned responses and makes no API calls.

**Credit saving:** reasoning is switched off for the short LLM tasks, and every Sarvam response is cached in memory, so repeating the same demo step costs nothing. `GET /api/status` shows call counts.

## Deploy (Render)

1. Push this repo to GitHub.
2. On Render, choose **New → Blueprint** and pick the repo (it reads `render.yaml`).
3. Set the `SARVAM_API_KEY` environment variable in the Render dashboard. Never commit it.
4. Open the live URL on your phone. Browsers only allow the mic on HTTPS, which Render provides.

## API

- `POST /api/voice-entry` (multipart `audio`, ≤25 s): returns the transcript, detected language, parsed entries and a confirmation in the speaker's language
- `POST /api/text-entry` `{text}`: same, but from typed text
- `POST /api/reminder` `{customer, amount, items, language, shop}`: returns the reminder text and a base64 WAV voice note
- `GET /api/status`: mode, models and API usage counters

## 3-minute demo script

1. Tap the mic and say in Hindi: *"Ramesh ne do sau ka atta aur pachaas ka tel udhaar liya."* The ledger shows Ramesh: Due ₹250.
2. Tap the Tamil chip (*"Kumar 350 rupees ku arisi vaanginaar…"*). Kumar: Due ₹350. Different language, same khata.
3. Say *"Sunita ne teen sau wapas diye"* to show a payment reducing a balance.
4. Next to Ramesh, choose **Tamil** and tap **🔊 Voice reminder**. A Tamil voice note plays, ready to download or share.

## Ledger storage

For the MVP the ledger is stored in the browser (`localStorage`). No customer data is kept on the server.
