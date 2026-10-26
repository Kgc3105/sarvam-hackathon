"""Live evaluation of Haq Hisaab against the real Sarvam APIs.

Hard credit cap: aborts before exceeding MAX_CHAT chat calls, MAX_TTS_CHARS TTS characters,
MAX_STT speech-to-text calls or MAX_VISION pages. Writes eval/results.md and eval/results.json.

    python eval/run_eval.py
"""
import base64
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")
import app  # noqa: E402

MAX_CHAT, MAX_TTS_CHARS, MAX_STT, MAX_VISION = 20, 1500, 3, 1
KEYS = ("days_worked", "daily_rate", "amount_paid", "overtime_hours", "deductions")

# (language, worker's story, expected facts, expected total due)
STORIES = [
    ("Hindi", "मैंने अक्टूबर में 26 दिन साइट पर काम किया, ठेकेदार ने 600 रुपये रोज़ बोला था, पर सिर्फ 12000 दिए। 20 घंटे ओवरटाइम का कुछ नहीं दिया।",
     {"days_worked": 26, "daily_rate": 600, "amount_paid": 12000, "overtime_hours": 20}, 6600),
    ("Hinglish", "Bhaiya maine 20 din loading ka kaam kiya, roz ke saade paanch sau tay hue the, malik ne bas 8000 diye",
     {"days_worked": 20, "daily_rate": 550, "amount_paid": 8000}, 3000),
    ("Tamil", "நான் 22 நாள் கட்டிட வேலை செய்தேன், ஒரு நாளுக்கு 700 ரூபாய் சொன்னாங்க, ஆனா 11000 தான் கொடுத்தாங்க.",
     {"days_worked": 22, "daily_rate": 700, "amount_paid": 11000}, 4400),
    ("Bengali (native digits, deduction)", "আমি ২৪ দিন ইটভাটায় কাজ করেছি, রোজ ৪৫০ টাকা বলেছিল, কিন্তু ৮০০০ টাকা দিয়েছে, আর ১০০০ টাকা কেটে নিয়েছে।",
     {"days_worked": 24, "daily_rate": 450, "amount_paid": 8000, "deductions": 1000}, 2800),
    ("Marathi (2 h/day overtime)", "मी 25 दिवस शेतात काम केलं, रोज 400 ठरले होते, मालकाने फक्त 7000 दिले, आणि रोज 2 तास जास्त काम केलं.",
     {"days_worked": 25, "daily_rate": 400, "amount_paid": 7000, "overtime_hours": 50}, 8000),
    ("Telugu (monthly salary)", "నేను ఇంటి పనిమనిషిగా నెలకు 7800 జీతానికి పని చేశాను, 26 రోజులు పని చేశాను, కానీ 5000 మాత్రమే ఇచ్చారు.",
     {"days_worked": 26, "daily_rate": 300, "amount_paid": 5000}, 2800),
    ("Code-mixed Hinglish (Latin script)", "Maine 22 days kaam kiya site pe, contractor ne per day 650 bola tha, but sirf 10000 pay kiya. 12 hours overtime ka bhi nahi diya.",
     {"days_worked": 22, "daily_rate": 650, "amount_paid": 10000, "overtime_hours": 12}, 6250),
    ("Code-mixed Hindi + English (mixed scripts)", "मैंने 22 days काम किया, contractor ने 650 per day बोला था, but सिर्फ 10000 pay किया, और 12 hours overtime का पैसा नहीं दिया।",
     {"days_worked": 22, "daily_rate": 650, "amount_paid": 10000, "overtime_hours": 12}, 6250),
    ("English (paid in full)", "I worked 10 days as a painter at 800 per day and the contractor paid me 8000.",
     {"days_worked": 10, "daily_rate": 800, "amount_paid": 8000}, 0),
]
VOICE = ("hi-IN", "मैंने पंद्रह दिन काम किया, पाँच सौ रुपये रोज़ तय हुए थे, ठेकेदार ने सिर्फ पाँच हज़ार दिए।",
         {"days_worked": 15, "daily_rate": 500, "amount_paid": 5000}, 2500)
CARD = ROOT / "samples" / "attendance_card.jpg"
CARD_EXPECT = {"days_worked": 26, "daily_rate": 600, "amount_paid": 12000, "overtime_hours": 20}


def budget_ok(chat=0, tts=0, stt=0, vision=0):
    u = app.usage
    return (u["chat_calls"] + chat <= MAX_CHAT and u["tts_chars"] + tts <= MAX_TTS_CHARS
            and u["stt_calls"] + stt <= MAX_STT and u["vision_pages"] + vision <= MAX_VISION)


def facts_match(got, exp):
    invented_deduction = "deductions" not in exp and got.get("deductions")  # unpaid balance mislabelled as a deduction
    return not invented_deduction and all(got.get(k) is not None and abs(got[k] - v) < 0.01 for k, v in exp.items())


def fmt(f):
    return ", ".join(f"{k.replace('_', ' ')} {f[k]:g}" for k in KEYS if f.get(k) is not None) or "(none)"


def run():
    if app.MOCK:
        sys.exit("No SARVAM_API_KEY / MOCK=1 - nothing to evaluate live.")
    out = {"stories": [], "voice": None, "vision": None, "claim": None}

    for lang, text, exp, due in STORIES:
        if not budget_ok(chat=1):
            print("credit cap reached"); break
        t = time.time()
        try:
            f = app.extract_facts(text)
            calc = app.calculate(app.Facts(**f))
            ok = facts_match(f, exp) and abs(calc["total_due"] - due) < 0.01
            err = ""
        except Exception as e:  # noqa: BLE001
            f, calc, ok, err = {}, {"total_due": None}, False, str(getattr(e, "detail", e))
        ms = int((time.time() - t) * 1000)
        out["stories"].append({"lang": lang, "story": text, "facts": f, "expected_due": due,
                               "total_due": calc["total_due"], "pass": ok, "ms": ms, "error": err})
        print(f"[{'PASS' if ok else 'FAIL'}] {lang:36} {ms:5}ms due={calc['total_due']} (exp {due})  {fmt(f)} {err}")

    code, text, exp, due = VOICE
    if budget_ok(chat=1, tts=len(text), stt=1):
        t = time.time()
        try:
            wav = base64.b64decode(app.sarvam_tts(text, code))
            stt = app.sarvam_stt(wav, "story.wav", "audio/wav")
            f = app.extract_facts(stt["transcript"])
            calc = app.calculate(app.Facts(**f))
            ok = facts_match(f, exp) and abs(calc["total_due"] - due) < 0.01
            out["voice"] = {"spoken": text, "heard": stt["transcript"], "detected": stt["language_code"], "facts": f,
                            "total_due": calc["total_due"], "expected_due": due, "pass": ok, "ms": int((time.time() - t) * 1000)}
        except Exception as e:  # noqa: BLE001
            out["voice"] = {"spoken": text, "pass": False, "error": str(getattr(e, "detail", e))}
        print(f"[{'PASS' if out['voice']['pass'] else 'FAIL'}] voice round-trip  {out['voice']}")

    if CARD.exists() and budget_ok(chat=1, vision=1):
        t = time.time()
        try:
            page = app.sarvam_vision(CARD.read_bytes(), CARD.name, "hi-IN")
            f = app.extract_facts(page, source="photo")
            ok = facts_match(f, CARD_EXPECT)
            out["vision"] = {"page_text": page[:1500], "facts": f, "pass": ok, "ms": int((time.time() - t) * 1000)}
        except Exception as e:  # noqa: BLE001
            out["vision"] = {"pass": False, "error": str(getattr(e, "detail", e))}
        print(f"[{'PASS' if out['vision']['pass'] else 'FAIL'}] vision card  {out['vision'].get('facts') or out['vision'].get('error')}")

    if budget_ok(chat=1, tts=600):
        t = time.time()
        try:
            facts = app.Facts(worker_name="Raju Yadav", employer_name="Ramesh Construction", period="October 2026",
                              days_worked=26, daily_rate=600, amount_paid=12000, overtime_hours=20)
            calc = app.calculate(facts)
            c = app.write_claim(facts, calc, "hi-IN")
            audio = base64.b64decode(app.sarvam_tts(c["explanation"], "hi-IN"))
            amount_ok = all(("6600" in c[k].replace(",", "") or "6,600" in c[k]) for k in ("explanation", "employer_letter", "complaint"))
            ok = amount_ok and audio[:4] == b"RIFF" and "15100" in c["explanation"]
            out["claim"] = {**c, "audio_bytes": len(audio), "pass": ok, "ms": int((time.time() - t) * 1000)}
        except Exception as e:  # noqa: BLE001
            out["claim"] = {"pass": False, "error": str(getattr(e, "detail", e))}
        print(f"[{'PASS' if out['claim']['pass'] else 'FAIL'}] claim + spoken explanation")

    out["usage"] = dict(app.usage)
    (ROOT / "eval" / "results.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    write_md(out)
    print("usage:", app.usage)


def write_md(out):
    s = out["stories"]
    md = ["# Live evaluation: Haq Hisaab on Sarvam AI", "",
          f"- Work stories understood and wages computed correctly: **{sum(r['pass'] for r in s)}/{len(s)}**"]
    for k, label in (("voice", "Real voice round-trip (Bulbul → Saaras → Sarvam-105B)"),
                     ("vision", "Attendance-card photo read by Sarvam Vision"),
                     ("claim", "Explanation + employer letter + Labour Office complaint, all quoting the exact amount, spoken by Bulbul")):
        if out[k]:
            md.append(f"- {label}: **{'pass' if out[k]['pass'] else 'FAIL'}**")
    md += ["", "## Work stories (Sarvam-105B extraction → deterministic wage maths)", "",
           "| Language | Story | Facts extracted | Owed | Expected | Result |", "|---|---|---|---|---|---|"]
    for r in s:
        md.append(f"| {r['lang']} | {r['story']} | {fmt(r['facts'])} | ₹{r['total_due']} | ₹{r['expected_due']} | {'✅' if r['pass'] else '❌'} |")
    if out["voice"] and "heard" in out["voice"]:
        v = out["voice"]
        md += ["", "## Voice round-trip", "", f"- Spoken: {v['spoken']}", f"- Heard by Saaras ({v['detected']}): {v['heard']}",
               f"- Facts: {fmt(v['facts'])} → owed ₹{v['total_due']} {'✅' if v['pass'] else '❌'}"]
    if out["vision"] and "facts" in out["vision"]:
        v = out["vision"]
        md += ["", "## Sarvam Vision: attendance card ([samples/attendance_card.jpg](../samples/attendance_card.jpg))", "",
               f"- Facts read from the photo: {fmt(v['facts'])} {'✅' if v['pass'] else '❌'} ({v['ms']} ms)", "",
               "<details><summary>Text Sarvam Vision extracted</summary>", "", "```", v["page_text"], "```", "</details>"]
    if out["claim"] and "explanation" in out["claim"]:
        c = out["claim"]
        md += ["", "## Claim output (Hindi)", "", f"**Spoken explanation:** {c['explanation']}", "",
               "<details><summary>Letter to employer</summary>", "", "```", c["employer_letter"], "```", "</details>", "",
               "<details><summary>Complaint to Labour Office</summary>", "", "```", c["complaint"], "```", "</details>"]
    md += ["", f"API usage for this run: `{json.dumps(out['usage'])}`"]
    (ROOT / "eval" / "results.md").write_text("\n".join(md) + "\n", encoding="utf-8")


if __name__ == "__main__":
    run()
