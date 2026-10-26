"""Live multilingual accuracy test for Bolo Khata against the real Sarvam APIs.

Hard credit cap: aborts before exceeding MAX_CHAT chat calls, MAX_TTS_CHARS TTS characters
or MAX_STT speech-to-text calls. Writes eval/results.md and eval/results.json.

    python eval/run_eval.py
"""
import base64
import difflib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")
import app  # noqa: E402

MAX_CHAT, MAX_TTS_CHARS, MAX_STT = 30, 800, 4

# (language, spoken/typed entry, expected [(customer, type, amount)])
TEXT_CASES = [
    ("Hinglish", "Ramesh ne 200 ka atta aur 50 ka tel udhaar liya", [("Ramesh", "credit", 250)]),
    ("Hindi", "सुनीता ने तीन सौ रुपये वापस दिए", [("Sunita", "payment", 300)]),
    ("Hindi (dedh sau)", "Mohan ne dedh sau ka doodh udhaar liya", [("Mohan", "credit", 150)]),
    ("Hindi (dhai sau)", "Pinky ne dhai sau ki chini li, paise baad mein degi", [("Pinky", "credit", 250)]),
    ("Multi-customer", "Raju ne 120 ka sabun udhaar liya aur Geeta ne 400 jama kiye", [("Raju", "credit", 120), ("Geeta", "payment", 400)]),
    ("Tamil", "குமார் 350 ரூபாய்க்கு அரிசி கடனாக வாங்கினார்", [("Kumar", "credit", 350)]),
    ("Telugu", "లక్ష్మి 500 రూపాయలు తిరిగి ఇచ్చింది", [("Lakshmi", "payment", 500)]),
    ("Bengali (native digits)", "রহিম ২০০ টাকার চাল বাকিতে নিয়েছে", [("Rahim", "credit", 200)]),
    ("Marathi", "सुरेशने 180 रुपयांचे तेल उधार घेतले", [("Suresh", "credit", 180)]),
    ("Kannada", "ರವಿ 600 ರೂಪಾಯಿ ಬಾಕಿ ಹಣ ವಾಪಸ್ ಕೊಟ್ಟರು", [("Ravi", "payment", 600)]),
    ("Gujarati", "મહેશે 90 રૂપિયાની ખાંડ ઉધાર લીધી", [("Mahesh", "credit", 90)]),
    ("Malayalam", "അനിൽ 75 രൂപയുടെ പാൽ കടമായി വാങ്ങി", [("Anil", "credit", 75)]),
    ("English", "Fatima took milk and bread for 120 on credit", [("Fatima", "credit", 120)]),
    ("Not a ledger entry", "Aaj mausam bahut accha hai", []),
]

# Real audio round-trip: Bulbul speaks the entry, Saaras hears it, Sarvam-105B parses it.
VOICE_CASES = [
    ("hi-IN", "Hindi voice", "रमेश ने दो सौ पचास रुपये का आटा उधार लिया", [("Ramesh", "credit", 250)]),
    ("ta-IN", "Tamil voice", "குமார் முன்னூறு ரூபாய் திருப்பிக் கொடுத்தார்", [("Kumar", "payment", 300)]),
    ("bn-IN", "Bengali voice", "রহিম একশো টাকার চিনি বাকিতে নিয়েছে", [("Rahim", "credit", 100)]),
]

REMINDER_LANGS = ["bn-IN", "te-IN", "mr-IN", "kn-IN"]
SCRIPT_RANGES = {
    "hi-IN": (0x0900, 0x097F), "mr-IN": (0x0900, 0x097F), "bn-IN": (0x0980, 0x09FF), "ta-IN": (0x0B80, 0x0BFF),
    "te-IN": (0x0C00, 0x0C7F), "kn-IN": (0x0C80, 0x0CFF), "ml-IN": (0x0D00, 0x0D7F), "gu-IN": (0x0A80, 0x0AFF),
}
NATIVE_DIGITS = {c: str(i) for base in (0x0966, 0x09E6, 0x0BE6, 0x0C66, 0x0CE6, 0x0D66, 0x0AE6) for i, c in
                 enumerate(chr(base + k) for k in range(10))}


def budget_ok(chat=0, tts=0, stt=0):
    u = app.usage
    return (u["chat_calls"] + chat <= MAX_CHAT and u["tts_chars"] + tts <= MAX_TTS_CHARS
            and u["stt_calls"] + stt <= MAX_STT)


def name_match(a, b):
    a, b = a.lower().replace(" ", ""), b.lower().replace(" ", "")
    return a == b or a.startswith(b[:4]) or difflib.SequenceMatcher(None, a, b).ratio() >= 0.7


def check(entries, expected):
    if len(entries) != len(expected):
        return False
    left = list(entries)
    for name, typ, amt in expected:
        hit = next((e for e in left if name_match(e["customer"], name) and e["type"] == typ
                    and abs(e["amount"] - amt) < 0.01), None)
        if not hit:
            return False
        left.remove(hit)
    return True


def fmt(entries):
    return "; ".join(f"{e['customer']} {e['type']} ₹{e['amount']:g}" for e in entries) or "(none)"


def main():
    if app.MOCK:
        sys.exit("No SARVAM_API_KEY / MOCK=1 - nothing to evaluate live.")
    rows, out = [], {"text": [], "voice": [], "reminders": []}

    for lang, text, exp in TEXT_CASES:
        if not budget_ok(chat=1):
            print("credit cap reached, stopping text cases"); break
        t = time.time()
        try:
            res = app.parse_entries(text)
            ok, got, err = check(res["entries"], exp), res["entries"], ""
        except Exception as e:  # noqa: BLE001
            ok, got, err = False, [], str(getattr(e, "detail", e))
        ms = int((time.time() - t) * 1000)
        out["text"].append({"lang": lang, "input": text, "expected": exp, "got": got, "pass": ok, "ms": ms, "error": err})
        print(f"[{'PASS' if ok else 'FAIL'}] {lang:24} {ms:5}ms  {fmt(got)} {err}")

    for code, label, text, exp in VOICE_CASES:
        if not budget_ok(chat=1, tts=len(text), stt=1):
            print("credit cap reached, stopping voice cases"); break
        t = time.time()
        try:
            wav = base64.b64decode(app.sarvam_tts(text, code))
            stt = app.sarvam_stt(wav, "entry.wav", "audio/wav")
            res = app.parse_entries(stt["transcript"])
            ok, got, err = check(res["entries"], exp), res["entries"], ""
            heard, det = stt["transcript"], stt["language_code"]
        except Exception as e:  # noqa: BLE001
            ok, got, err, heard, det = False, [], str(getattr(e, "detail", e)), "", ""
        ms = int((time.time() - t) * 1000)
        out["voice"].append({"lang": label, "spoken": text, "heard": heard, "detected": det, "expected": exp,
                             "got": got, "pass": ok, "ms": ms, "error": err})
        print(f"[{'PASS' if ok else 'FAIL'}] {label:24} {ms:5}ms  detected={det} {fmt(got)} {err}")

    for code in REMINDER_LANGS:
        if not budget_ok(chat=1):
            print("credit cap reached, stopping reminders"); break
        try:
            txt = app.write_reminder("Ramesh", 250, "atta, oil", code, "Sharma Kirana Store")
            lo, hi = SCRIPT_RANGES[code]
            letters = [c for c in txt if c.isalpha()]
            native = sum(lo <= ord(c) <= hi for c in letters) / max(1, len(letters))
            ascii_txt = "".join(NATIVE_DIGITS.get(c, c) for c in txt)
            ok = native >= 0.6 and "250" in ascii_txt
        except Exception as e:  # noqa: BLE001
            txt, native, ok = str(getattr(e, "detail", e)), 0, False
        out["reminders"].append({"lang": app.LANGUAGES[code], "text": txt, "native_script_ratio": round(native, 2), "pass": ok})
        print(f"[{'PASS' if ok else 'FAIL'}] reminder {code}  script={native:.0%}")

    out["usage"] = dict(app.usage)
    (ROOT / "eval" / "results.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

    def score(k):
        return sum(r["pass"] for r in out[k]), len(out[k])

    md = ["# Live evaluation: Bolo Khata on Sarvam AI", "",
          f"Text entries parsed correctly: **{score('text')[0]}/{score('text')[1]}**  ",
          f"Voice round-trips (Bulbul → Saaras → Sarvam-105B): **{score('voice')[0]}/{score('voice')[1]}**  ",
          f"Reminders in the right script with the right amount: **{score('reminders')[0]}/{score('reminders')[1]}**", "",
          "## Ledger parsing (Sarvam-105B)", "", "| Language | Input | Parsed | Result | Latency |", "|---|---|---|---|---|"]
    for r in out["text"]:
        md.append(f"| {r['lang']} | {r['input']} | {fmt(r['got'])} | {'✅' if r['pass'] else '❌'} | {r['ms']} ms |")
    md += ["", "## Voice round-trip (Bulbul v3 → Saaras v3 → Sarvam-105B)", "",
           "| Language | Spoken | Heard (detected language) | Parsed | Result |", "|---|---|---|---|---|"]
    for r in out["voice"]:
        md.append(f"| {r['lang']} | {r['spoken']} | {r['heard']} ({r['detected']}) | {fmt(r['got'])} | {'✅' if r['pass'] else '❌'} |")
    md += ["", "## Reminders (Sarvam-105B)", "", "| Language | Reminder | Native script | Result |", "|---|---|---|---|"]
    for r in out["reminders"]:
        md.append(f"| {r['lang']} | {r['text']} | {r['native_script_ratio']:.0%} | {'✅' if r['pass'] else '❌'} |")
    md += ["", f"API usage for this run: `{json.dumps(out['usage'])}`"]
    (ROOT / "eval" / "results.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("usage:", app.usage)


if __name__ == "__main__":
    main()
