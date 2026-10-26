"""Bolo Khata - a voice-first udhaar (credit) ledger for kirana shop owners.

Sarvam APIs used:
  Saaras v3      speech-to-text   (shopkeeper speaks an entry in any Indian language)
  Sarvam-105B    chat completions (turn the spoken sentence into structured ledger entries,
                                   and write a polite reminder in the customer's language)
  Bulbul v3      text-to-speech   (reminder becomes a voice note)

Credit saving: every Sarvam response is cached in memory by request hash, and MOCK=1
runs the whole app with canned responses and zero API calls.
"""
import base64
import hashlib
import io
import json
import os
import re
import wave
from pathlib import Path

import requests
from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

load_dotenv()

API_KEY = os.getenv("SARVAM_API_KEY", "").strip()
MOCK = os.getenv("MOCK", "0") == "1" or not API_KEY
BASE = "https://api.sarvam.ai"
HEADERS = {"api-subscription-key": API_KEY}
STT_MODEL = "saaras:v3"
CHAT_MODEL = "sarvam-105b"
TTS_MODEL = "bulbul:v3"
TTS_SPEAKER = os.getenv("TTS_SPEAKER", "priya")

LANGUAGES = {
    "hi-IN": "Hindi", "bn-IN": "Bengali", "ta-IN": "Tamil", "te-IN": "Telugu",
    "kn-IN": "Kannada", "ml-IN": "Malayalam", "mr-IN": "Marathi", "gu-IN": "Gujarati",
    "pa-IN": "Punjabi", "od-IN": "Odia", "en-IN": "English",
}

app = FastAPI(title="Bolo Khata")
STATIC = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=STATIC), name="static")

_cache = {}
usage = {"stt_calls": 0, "chat_calls": 0, "tts_calls": 0, "tts_chars": 0, "cache_hits": 0}


def _key(*parts):
    h = hashlib.sha256()
    for p in parts:
        h.update(p if isinstance(p, bytes) else json.dumps(p, sort_keys=True, ensure_ascii=False).encode())
    return h.hexdigest()


def _cached(k):
    if k in _cache:
        usage["cache_hits"] += 1
        return _cache[k]
    return None


def _raise(r, what):
    try:
        detail = r.json()
    except ValueError:
        detail = r.text[:300]
    raise HTTPException(status_code=502, detail=f"Sarvam {what} failed ({r.status_code}): {detail}")


# ---------------------------------------------------------------- Sarvam calls
def sarvam_stt(audio, filename, content_type):
    k = _key("stt", audio)
    if (hit := _cached(k)) is not None:
        return hit
    if MOCK:
        out = {"transcript": "रमेश ने दो सौ रुपये का आटा और पचास का तेल उधार लिया", "language_code": "hi-IN"}
    else:
        r = requests.post(
            f"{BASE}/speech-to-text",
            headers=HEADERS,
            files={"file": (filename, audio, content_type or "audio/webm")},
            data={"model": STT_MODEL, "mode": "transcribe", "language_code": "unknown"},
            timeout=60,
        )
        if not r.ok:
            _raise(r, "speech-to-text")
        j = r.json()
        out = {"transcript": j.get("transcript", ""), "language_code": j.get("language_code") or "hi-IN"}
        usage["stt_calls"] += 1
    _cache[k] = out
    return out


def _strip_think(text):
    return re.sub(r"<think>.*?</think>", "", text or "", flags=re.S).strip()


def sarvam_chat(system, user, max_tokens=1200):
    k = _key("chat", system, user)
    if (hit := _cached(k)) is not None:
        return hit
    r = requests.post(
        f"{BASE}/v1/chat/completions",
        headers={**HEADERS, "Content-Type": "application/json"},
        json={
            "model": CHAT_MODEL,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "temperature": 0.2,
            "max_tokens": max_tokens,
            # Reasoning is on by default and can eat the whole token budget, leaving
            # empty content. These are short extraction/writing tasks: switch it off.
            "reasoning_effort": None,
        },
        timeout=90,
    )
    if not r.ok:
        _raise(r, "chat")
    content = _strip_think(r.json()["choices"][0]["message"].get("content") or "")
    usage["chat_calls"] += 1
    _cache[k] = content
    return content


def sarvam_tts(text, lang):
    """Returns base64 WAV."""
    k = _key("tts", text, lang, TTS_SPEAKER)
    if (hit := _cached(k)) is not None:
        return hit
    if MOCK:
        b64 = _silent_wav_b64()
    else:
        body = {"text": text[:2400], "model": TTS_MODEL, "speaker": TTS_SPEAKER, "target_language_code": lang}
        url = f"{BASE}/text-to-speech"
        hdr = {**HEADERS, "Content-Type": "application/json"}
        r = requests.post(url, headers=hdr, json=body, timeout=60)
        if r.status_code in (400, 422):  # newer docs name the field language_code
            body.pop("target_language_code")
            body["language_code"] = lang
            r = requests.post(url, headers=hdr, json=body, timeout=60)
        if not r.ok:
            _raise(r, "text-to-speech")
        j = r.json()
        audios = j.get("audios") or ([j["audio"]] if j.get("audio") else [])
        if not audios:
            raise HTTPException(502, "Sarvam text-to-speech returned no audio")
        b64 = audios[0]
        usage["tts_calls"] += 1
        usage["tts_chars"] += len(text)
    _cache[k] = b64
    return b64


def _silent_wav_b64():
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(8000)
        w.writeframes(b"\x00\x00" * 8000)
    return base64.b64encode(buf.getvalue()).decode()


# ---------------------------------------------------------------- business logic
PARSE_SYSTEM = """You are the bookkeeper for a small Indian kirana shop. The shopkeeper speaks ledger entries in any Indian language or code-mixed speech.
Extract every credit (udhaar: customer took goods/money and owes) or payment (customer paid back) mentioned.
Reply with ONLY a JSON object, no prose, no markdown:
{"entries":[{"customer":"<customer name in English letters, title case>","type":"credit"|"payment","amount":<number in rupees>,"items":"<short English description of goods, empty for payments>"}],
 "confirmation":"<one short sentence confirming what was recorded, in the SAME language and script the shopkeeper used>"}
Convert number words to digits (e.g. "do sau" = 200, "dedh sau" = 150). If multiple items for one customer, sum them into one entry and list the items.
If nothing ledger-related is said, return {"entries":[],"confirmation":"<ask them to repeat, in their language>"}."""


def parse_entries(text):
    if MOCK:
        return {
            "entries": [{"customer": "Ramesh", "type": "credit", "amount": 250, "items": "atta, oil"}],
            "confirmation": "रमेश के खाते में ₹250 उधार (आटा, तेल) लिख दिया।",
        }
    raw = sarvam_chat(PARSE_SYSTEM, text)
    m = re.search(r"\{.*\}", raw, flags=re.S)
    if not m:
        raise HTTPException(502, f"Could not read ledger entry from model output: {raw[:200]}")
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError:
        raise HTTPException(502, f"Model returned invalid JSON: {raw[:200]}")
    clean = []
    for e in data.get("entries", []):
        try:
            amt = float(e.get("amount", 0))
        except (TypeError, ValueError):
            continue
        name = str(e.get("customer", "")).strip()
        if not name or amt <= 0:
            continue
        clean.append({
            "customer": name.title(),
            "type": "payment" if str(e.get("type")).lower() == "payment" else "credit",
            "amount": round(amt, 2),
            "items": str(e.get("items", "")).strip(),
        })
    return {"entries": clean, "confirmation": str(data.get("confirmation", "")).strip()}


REMINDER_SYSTEM = """You write short, warm, respectful payment reminders that a neighbourhood kirana shopkeeper sends to a regular customer as a voice note.
Rules: write ONLY the message text, in the requested language and its native script; 2-3 short sentences, under 60 words; greet the customer by name; mention the exact amount due in rupees and what it was for; no threats, no guilt, keep the relationship friendly; end with a thank-you. Write numbers as digits."""


def write_reminder(customer, amount, items, lang, shop):
    lang_name = LANGUAGES.get(lang, "Hindi")
    if MOCK:
        return f"नमस्ते {customer} जी, {shop} से याद दिला रहे हैं कि आपका ₹{amount:g} ({items}) बाकी है। सुविधा अनुसार चुका दीजिए। धन्यवाद!"
    user = f"Language: {lang_name}\nShop name: {shop}\nCustomer: {customer}\nAmount due: Rs {amount:g}\nFor: {items or 'groceries'}"
    return sarvam_chat(REMINDER_SYSTEM, user, max_tokens=1000).strip().strip('"')


# ---------------------------------------------------------------- routes
@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/api/status")
def status():
    return {"mock": MOCK, "models": {"stt": STT_MODEL, "chat": CHAT_MODEL, "tts": TTS_MODEL},
            "usage": usage, "languages": LANGUAGES}


@app.post("/api/voice-entry")
async def voice_entry(audio: UploadFile = File(...)):
    data = await audio.read()
    if not data:
        raise HTTPException(400, "Empty recording")
    if len(data) > 2_000_000:
        raise HTTPException(400, "Recording too long - keep it under 25 seconds")
    stt = sarvam_stt(data, audio.filename or "entry.webm", audio.content_type or "audio/webm")
    if not stt["transcript"].strip():
        raise HTTPException(422, "Could not hear anything - please try again")
    return {**stt, **parse_entries(stt["transcript"])}


class TextEntry(BaseModel):
    text: str


@app.post("/api/text-entry")
def text_entry(body: TextEntry):
    if not body.text.strip():
        raise HTTPException(400, "Empty entry")
    return {"transcript": body.text, "language_code": None, **parse_entries(body.text[:1000])}


class ReminderReq(BaseModel):
    customer: str
    amount: float
    items: str = ""
    language: str = "hi-IN"
    shop: str = "Sharma Kirana Store"


@app.post("/api/reminder")
def reminder(body: ReminderReq):
    if body.amount <= 0:
        raise HTTPException(400, "Nothing is due")
    lang = body.language if body.language in LANGUAGES else "hi-IN"
    text = write_reminder(body.customer, body.amount, body.items, lang, body.shop)
    return {"text": text, "language": lang, "audio_b64": sarvam_tts(text, lang), "mime": "audio/wav"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
