"""Haq Hisaab - wage-theft checker for India's daily-wage workers.

A construction / farm / domestic worker speaks their work story in their own language
(and can add a photo of the attendance card or wage slip). Haq Hisaab works out exactly
what they are owed - with deterministic maths, never the LLM - explains it back to them
out loud, and drafts the demand letter and the Labour Office complaint.

Sarvam APIs used:
  Saaras v3      speech-to-text   (worker's spoken story, any Indian language, auto-detected)
  Sarvam Vision  document AI      (attendance card / hajri register / wage slip photo -> text)
  Sarvam-105B    chat completions (story / register -> structured facts; explanation + letters)
  Bulbul v3      text-to-speech   (explanation spoken back in the worker's language)

Credit saving: every Sarvam response is cached in memory by request hash, and MOCK=1
runs the whole app with canned responses and zero API calls.
"""
import base64
import hashlib
import io
import json
import os
import re
import time
import wave
import zipfile
from pathlib import Path
from typing import Optional

import requests
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

load_dotenv()

API_KEY = os.getenv("SARVAM_API_KEY", "").strip()
MOCK = os.getenv("MOCK", "0") == "1" or not API_KEY
BASE = "https://api.sarvam.ai"
HEADERS = {"api-subscription-key": API_KEY}
STT_MODEL = "saaras:v3"
CHAT_MODEL = "sarvam-105b"
TTS_MODEL = "bulbul:v3"
TTS_SPEAKER = os.getenv("TTS_SPEAKER", "shubh")
DOC_JOB = f"{BASE}/doc-ai/v1/job"
VISION_TERMINAL = {"completed", "partially_completed", "failed", "rejected"}

# Code on Wages, 2019 s.14: overtime is paid at not less than twice the normal rate.
OVERTIME_MULTIPLIER = 2
HOURS_PER_DAY = 8
# National floor-level minimum wage notified by the Government of India (per day).
NATIONAL_FLOOR_WAGE = 178

LANGUAGES = {
    "hi-IN": "Hindi", "bn-IN": "Bengali", "ta-IN": "Tamil", "te-IN": "Telugu",
    "kn-IN": "Kannada", "ml-IN": "Malayalam", "mr-IN": "Marathi", "gu-IN": "Gujarati",
    "pa-IN": "Punjabi", "od-IN": "Odia", "en-IN": "English",
}

app = FastAPI(title="Haq Hisaab")
# On Vercel, public/ is served by the CDN; locally and on Render FastAPI serves it.
PUBLIC = Path(__file__).parent / "public"

_cache = {}
usage = {"stt_calls": 0, "chat_calls": 0, "tts_calls": 0, "tts_chars": 0, "vision_pages": 0, "cache_hits": 0}


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


def _post(url, what, **kw):
    try:
        return requests.post(url, **kw)
    except requests.RequestException as e:
        raise HTTPException(504, f"Sarvam {what} did not respond - please try again ({type(e).__name__})")


def _get(url, what, **kw):
    try:
        return requests.get(url, **kw)
    except requests.RequestException as e:
        raise HTTPException(504, f"Sarvam {what} did not respond - please try again ({type(e).__name__})")


# ---------------------------------------------------------------- Sarvam calls
def sarvam_stt(audio, filename, content_type):
    k = _key("stt", audio)
    if (hit := _cached(k)) is not None:
        return hit
    if MOCK:
        out = {"transcript": "मैंने अक्टूबर में 26 दिन साइट पर काम किया, ठेकेदार ने 600 रुपये रोज़ बोला था, "
                             "पर सिर्फ 12000 दिए। 20 घंटे ओवरटाइम का कुछ नहीं दिया।", "language_code": "hi-IN"}
    else:
        r = _post(f"{BASE}/speech-to-text", "speech-to-text", headers=HEADERS,
                  files={"file": (filename, audio, (content_type or "audio/webm").split(";")[0])},
                  data={"model": STT_MODEL, "mode": "transcribe", "language_code": "unknown"}, timeout=60)
        if not r.ok:
            _raise(r, "speech-to-text")
        j = r.json()
        out = {"transcript": j.get("transcript", ""), "language_code": j.get("language_code") or "hi-IN"}
        usage["stt_calls"] += 1
    _cache[k] = out
    return out


def _strip_think(text):
    return re.sub(r"<think>.*?</think>", "", text or "", flags=re.S).strip()


def sarvam_chat(system, user, max_tokens=1500):
    k = _key("chat", system, user)
    if (hit := _cached(k)) is not None:
        return hit
    r = _post(f"{BASE}/v1/chat/completions", "chat", headers={**HEADERS, "Content-Type": "application/json"},
              json={
                  "model": CHAT_MODEL,
                  "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                  "temperature": 0.2,
                  "max_tokens": max_tokens,
                  # Reasoning is on by default and can eat the whole token budget, leaving
                  # empty content. These are extraction/writing tasks: switch it off.
                  "reasoning_effort": None,
              }, timeout=90)
    if not r.ok:
        _raise(r, "chat")
    try:
        content = _strip_think(r.json()["choices"][0]["message"].get("content") or "")
    except (KeyError, IndexError, ValueError):
        raise HTTPException(502, "Sarvam chat returned an unexpected response")
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
        r = _post(url, "text-to-speech", headers=hdr, json=body, timeout=60)
        if r.status_code in (400, 422):  # newer docs name the field language_code
            body.pop("target_language_code")
            body["language_code"] = lang
            r = _post(url, "text-to-speech", headers=hdr, json=body, timeout=60)
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


def sarvam_vision(image, filename, lang="hi-IN"):
    """Sarvam Vision Document AI (digitise job): image -> markdown text."""
    k = _key("vision", image, lang)
    if (hit := _cached(k)) is not None:
        return hit
    if MOCK:
        text = ("| तारीख | हाज़िरी | |\n|---|---|---|\n" + "\n".join(f"| {d}/10 | P | |" for d in range(1, 27))
                + "\n\nकुल हाज़िरी: 26 दिन   मज़दूरी दर: 600/-   भुगतान: 12000/-   ठेकेदार: रमेश कंस्ट्रक्शन")
        _cache[k] = text
        return text
    mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "pdf": "application/pdf"}.get(
        filename.rsplit(".", 1)[-1].lower(), "image/jpeg")
    r = _post(f"{DOC_JOB}/digitise", "vision", headers=HEADERS, files={"file": (filename, image, mime)},
              data={"language": lang, "output_format": "md", "content_type": "mixed"}, timeout=90)
    if not r.ok:
        _raise(r, "vision")
    job_id = r.json()["job_id"]
    deadline, delay, status = time.monotonic() + 90, 1.5, ""
    while True:
        s = _get(f"{DOC_JOB}/{job_id}/status", "vision", headers=HEADERS, timeout=30)
        if not s.ok:
            _raise(s, "vision status")
        status = str(s.json().get("status", "")).lower()
        if status in VISION_TERMINAL:
            break
        if time.monotonic() + delay > deadline:
            raise HTTPException(504, "Sarvam Vision is taking too long - try a clearer, smaller photo")
        time.sleep(delay)
        delay = min(delay * 1.5, 4)
    if status not in ("completed", "partially_completed"):
        raise HTTPException(502, f"Sarvam Vision could not read the photo (job {status})")
    text = _vision_text(job_id)
    usage["vision_pages"] += 1
    _cache[k] = text
    return text


def _unzip_text(blob):
    with zipfile.ZipFile(io.BytesIO(blob)) as zf:
        names = [n for n in zf.namelist() if n.lower().endswith((".md", ".html", ".txt")) and "metadata/" not in n]
        return "\n\n".join(zf.read(n).decode("utf-8", "replace") for n in sorted(names))


def _vision_text(job_id):
    r = _get(f"{DOC_JOB}/{job_id}/results", "vision results", headers=HEADERS, params={"format": "md"}, timeout=60)
    if r.ok:
        if r.content[:2] == b"PK":  # results can arrive as a ZIP bundle (page .md + metadata)
            text = _unzip_text(r.content)
            if text.strip():
                return text
        elif "json" in r.headers.get("Content-Type", ""):
            data = r.json()
            pages = [p.get("content", "") for d in data.get("documents") or []
                     for p in sorted(d.get("pages") or [], key=lambda p: p.get("page_number") or 0)]
            if any(p.strip() for p in pages):
                return "\n\n".join(pages)
        elif r.text.strip():
            return r.text
    d = _get(f"{DOC_JOB}/{job_id}/download-url", "vision download", headers=HEADERS, timeout=30)
    if not d.ok:
        _raise(d, "vision download")
    dl = d.json()  # presigned URL: never send the API key here
    z = requests.request(dl.get("method", "GET"), dl["url"], headers=dl.get("headers") or {}, timeout=120)
    z.raise_for_status()
    return _unzip_text(z.content)


def _silent_wav_b64():
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(8000)
        w.writeframes(b"\x00\x00" * 8000)
    return base64.b64encode(buf.getvalue()).decode()


def _json_from(raw):
    m = re.search(r"\{.*\}", raw or "", flags=re.S)
    if not m:
        raise HTTPException(502, f"Could not read the model output: {(raw or '')[:200]}")
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        raise HTTPException(502, f"Model returned invalid JSON: {raw[:200]}")


# ---------------------------------------------------------------- facts extraction
FACT_FIELDS = ["worker_name", "employer_name", "work_type", "work_place", "period", "days_worked", "daily_rate",
               "amount_paid", "overtime_hours", "deductions", "deduction_reason"]
NUMERIC = {"days_worked", "daily_rate", "amount_paid", "overtime_hours", "deductions"}

FACTS_SYSTEM = """You help Indian daily-wage workers (construction, farm, factory, domestic, loading) check if they were underpaid.
Read the worker's account (spoken in any Indian language or code-mixed, or text from a photo of an attendance card / wage slip).
Reply with ONLY a JSON object, no prose, no markdown:
{"worker_name": string|null, "employer_name": string|null (the actual NAME of the contractor / company; null if they only say a generic word like thekedar, malik, seth, contractor), "work_type": string|null (in English),
 "work_place": string|null, "period": string|null (e.g. "October 2026"),
 "days_worked": number|null, "daily_rate": number|null (rupees per day that was PROMISED/agreed; if a monthly salary was agreed, divide by 26),
 "amount_paid": number|null (total rupees actually received for this period, including advances),
 "overtime_hours": number|null (extra hours WORKED beyond normal 8-hour days, whether or not they were paid for them - "12 hours overtime ka paisa nahi diya" means 12; if they say "2 ghante roz extra" for N days, multiply),
 "deductions": number|null (ONLY money the worker explicitly says was cut / deducted / kaat liya for some reason such as advance, food, tools, damage, commission. The unpaid balance is NOT a deduction - use null),
 "deduction_reason": string|null}
Convert number words to digits ("dedh sau"=150, "paune"/"sava"/"dhai" fractions, native-script digits). Names in English letters.
Use null for anything not stated - never guess."""


def extract_facts(text, source="story"):
    if MOCK:
        if source == "photo":
            return {"employer_name": "Ramesh Construction", "days_worked": 26, "daily_rate": 600, "amount_paid": 12000}
        return {"worker_name": None, "employer_name": None, "work_type": "construction", "work_place": "site",
                "period": "October", "days_worked": 26, "daily_rate": 600, "amount_paid": 12000,
                "overtime_hours": 20, "deductions": None, "deduction_reason": None}
    data = _json_from(sarvam_chat(FACTS_SYSTEM, f"Source: {source}\n\n{text[:6000]}"))
    return clean_facts(data)


def clean_facts(data):
    out = {}
    for f in FACT_FIELDS:
        v = data.get(f)
        if f in NUMERIC:
            try:
                v = float(str(v).replace(",", "").replace("₹", "")) if v not in (None, "") else None
            except ValueError:
                v = None
            if v is not None and (v < 0 or v > 10_000_000):
                v = None
        else:
            v = str(v).strip()[:120] if v not in (None, "", "null") else None
        out[f] = v
    return out


# ---------------------------------------------------------------- deterministic wage maths
class Facts(BaseModel):
    worker_name: Optional[str] = None
    employer_name: Optional[str] = None
    work_type: Optional[str] = None
    work_place: Optional[str] = None
    period: Optional[str] = None
    days_worked: Optional[float] = None
    daily_rate: Optional[float] = None
    amount_paid: Optional[float] = None
    overtime_hours: Optional[float] = None
    deductions: Optional[float] = None
    deduction_reason: Optional[str] = None
    state_min_wage: Optional[float] = None  # entered by the user from their state's notification


def calculate(f: Facts):
    """All money maths is plain Python so every rupee is explainable and testable."""
    missing = [k for k in ("days_worked", "daily_rate", "amount_paid") if getattr(f, k) is None]
    days, rate, paid = f.days_worked or 0, f.daily_rate or 0, f.amount_paid or 0
    ot_hours, deductions = f.overtime_hours or 0, f.deductions or 0
    hourly = rate / HOURS_PER_DAY if rate else 0
    agreed = round(days * rate, 2)
    overtime = round(ot_hours * hourly * OVERTIME_MULTIPLIER, 2)
    earned = agreed + overtime
    owed = round(max(0.0, earned - paid), 2)
    lines = [
        {"label": f"Agreed wages: {days:g} days × ₹{rate:g}", "amount": agreed},
        {"label": f"Overtime: {ot_hours:g} h × ₹{hourly:g}/h × {OVERTIME_MULTIPLIER} (Code on Wages 2019, s.14)",
         "amount": overtime},
        {"label": "Received", "amount": -paid},
    ]
    flags = []
    floor = f.state_min_wage or NATIONAL_FLOOR_WAGE
    floor_name = "your state's minimum wage" if f.state_min_wage else "the national floor wage"
    min_wage_gap = 0.0
    if rate and rate < floor:
        min_wage_gap = round(days * (floor - rate), 2)
        flags.append(f"The agreed rate ₹{rate:g}/day is below {floor_name} (₹{floor:g}/day). "
                     f"A wage below the minimum is illegal even if you agreed to it: a further ₹{min_wage_gap:g} is due.")
    if deductions:
        flags.append(f"₹{deductions:g} was deducted ({f.deduction_reason or 'no reason given'}). "
                     "Deductions are only allowed for reasons the law lists (e.g. advances, fines with notice).")
    if ot_hours and not rate:
        flags.append("Tell us your daily rate to price the overtime.")
    total = round(owed + min_wage_gap, 2)
    return {"missing": missing, "lines": lines, "earned": round(earned, 2), "paid": paid, "owed": owed,
            "min_wage_gap": min_wage_gap, "total_due": total, "flags": flags, "hourly": round(hourly, 2),
            "complete": not missing}


# ---------------------------------------------------------------- explanation + letters
CLAIM_SYSTEM = """You are a kind, plain-spoken labour-rights helper for Indian daily-wage workers. You are given the worker's facts and an
already-computed wage calculation. NEVER recompute or change any number - use the numbers exactly as given.
Reply with ONLY a JSON object, no markdown:
{"explanation": "<spoken explanation for the worker in {LANG} (native script), 4-6 short simple sentences: how much they earned, how much they got, exactly how much is still owed and why (overtime is paid double by law), and the next step: first ask the employer with the letter, and if not paid, give the complaint to the district Labour Office; free legal help: NALSA helpline 15100. Warm, respectful, no jargon. Write rupee amounts as digits.>",
 "employer_letter": "<short, polite but firm letter from the worker to the employer in {LANG} (native script), with a breakdown of the amount due, asking for payment within 7 days. Placeholders in [brackets] for anything unknown.>",
 "complaint": "<formal complaint in English to the Inspector-cum-Facilitator / Assistant Labour Commissioner of the district under the Code on Wages, 2019: subject line, worker and employer details (placeholders if unknown), facts, wage calculation table in plain text, relief sought, date and signature placeholders.>"}"""


def write_claim(f: Facts, calc, lang):
    lang_name = LANGUAGES.get(lang, "Hindi")
    if MOCK:
        return {
            "explanation": f"आपने कुल ₹{calc['earned']:g} कमाए, आपको ₹{calc['paid']:g} मिले। आपका ₹{calc['total_due']:g} अभी बाकी है। "
                           "ओवरटाइम का पैसा कानून से दोगुना मिलता है। पहले ठेकेदार को यह चिट्ठी दें, फिर भी न मिले तो "
                           "ज़िला श्रम कार्यालय में शिकायत दें। मुफ़्त कानूनी मदद: 15100।",
            "employer_letter": f"सेवा में, {f.employer_name or '[ठेकेदार का नाम]'}\n... बकाया ₹{calc['total_due']:g} ...",
            "complaint": f"To: The Inspector-cum-Facilitator, [District]\nSubject: Non-payment of wages - Rs {calc['total_due']:g}\n...",
        }
    facts = f.model_dump()
    user = (f"Language for explanation and employer letter: {lang_name}\n"
            f"Worker facts: {json.dumps(facts, ensure_ascii=False)}\n"
            f"Computed calculation (use exactly): {json.dumps(calc, ensure_ascii=False)}")
    data = _json_from(sarvam_chat(CLAIM_SYSTEM.replace("{LANG}", lang_name), user, max_tokens=2500))
    return {k: str(data.get(k, "")).strip() for k in ("explanation", "employer_letter", "complaint")}


# ---------------------------------------------------------------- routes
@app.get("/")
def index():
    return FileResponse(PUBLIC / "index.html")


@app.get("/api/status")
def status():
    return {"mock": MOCK, "models": {"stt": STT_MODEL, "chat": CHAT_MODEL, "tts": TTS_MODEL, "vision": "sarvam-vision"},
            "usage": usage, "languages": LANGUAGES, "national_floor_wage": NATIONAL_FLOOR_WAGE}


@app.post("/api/story-voice")
def story_voice(audio: UploadFile = File(...)):
    data = audio.file.read()
    if not data:
        raise HTTPException(400, "Empty recording")
    if len(data) > 2_000_000:
        raise HTTPException(400, "Recording too long - keep it under 25 seconds")
    stt = sarvam_stt(data, audio.filename or "story.webm", audio.content_type or "audio/webm")
    if not stt["transcript"].strip():
        raise HTTPException(422, "Could not hear anything - please try again")
    return {**stt, "facts": extract_facts(stt["transcript"])}


class Story(BaseModel):
    text: str


@app.post("/api/story-text")
def story_text(body: Story):
    if not body.text.strip():
        raise HTTPException(400, "Please describe your work and payment")
    return {"transcript": body.text, "language_code": None, "facts": extract_facts(body.text[:3000])}


@app.post("/api/evidence-photo")
def evidence_photo(image: UploadFile = File(...), language: str = Form("hi-IN")):
    data = image.file.read()
    if not data:
        raise HTTPException(400, "Empty photo")
    if len(data) > 8_000_000:
        raise HTTPException(400, "Photo too large - please use a smaller photo")
    text = sarvam_vision(data, image.filename or "card.jpg", language if language in LANGUAGES else "hi-IN")
    if not text.strip():
        raise HTTPException(422, "Could not read any text in the photo - try a clearer photo")
    return {"page_text": text[:4000], "facts": extract_facts(text, source="photo")}


@app.post("/api/calculate")
def api_calculate(f: Facts):
    return calculate(f)


class ClaimReq(BaseModel):
    facts: Facts
    language: str = "hi-IN"
    speak: bool = True


@app.post("/api/claim")
def claim(body: ClaimReq):
    calc = calculate(body.facts)
    if not calc["complete"]:
        raise HTTPException(400, "Please fill: " + ", ".join(m.replace("_", " ") for m in calc["missing"]))
    lang = body.language if body.language in LANGUAGES else "hi-IN"
    out = write_claim(body.facts, calc, lang)
    audio = sarvam_tts(out["explanation"], lang) if body.speak and out["explanation"] else None
    return {**out, "calc": calc, "language": lang, "audio_b64": audio, "mime": "audio/wav"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
