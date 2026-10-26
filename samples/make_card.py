"""Generates samples/attendance_card.jpg - a demo hajri (attendance) card for testing Sarvam Vision."""
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, features

OUT = Path(__file__).parent / "attendance_card.jpg"
FONT = "C:/Windows/Fonts/Nirmala.ttc"
layout = ImageFont.Layout.RAQM if features.check("raqm") else ImageFont.Layout.BASIC


def font(size):
    return ImageFont.truetype(FONT, size, layout_engine=layout)


random.seed(7)
W, H = 1100, 1400
img = Image.new("RGB", (W, H), (247, 241, 222))
d = ImageDraw.Draw(img)
ink = (28, 36, 92)
d.text((60, 40), "हाज़िरी कार्ड  /  ATTENDANCE CARD", font=font(44), fill=ink)
d.text((60, 110), "ठेकेदार: रमेश कंस्ट्रक्शन, हडपसर साइट, पुणे", font=font(32), fill=ink)
d.text((60, 160), "मज़दूर का नाम: राजू यादव        माह: अक्टूबर 2026", font=font(32), fill=ink)
d.text((60, 210), "मज़दूरी दर: ₹600 प्रतिदिन (8 घंटे)", font=font(32), fill=ink)

absent = {5, 12, 19, 26}  # Sundays off -> 26 days present out of 30
x0, y0, cw, ch = 60, 290, 245, 64
for i in range(30):
    day = i + 1
    col, row = i // 10, i % 10
    x, y = x0 + col * (cw + 90), y0 + row * ch
    d.rectangle([x, y, x + cw, y + ch], outline=ink, width=2)
    mark = "A" if day in absent else "P"
    extra = "  +2 घंटे" if day in {3, 4, 10, 11, 17, 18, 24, 25, 29, 30} else ""
    d.text((x + 12, y + 14), f"{day:02d}/10   {mark}{extra}", font=font(28), fill=ink)

d.text((60, 970), "कुल हाज़िरी: 26 दिन", font=font(36), fill=ink)
d.text((60, 1025), "ओवरटाइम: 20 घंटे", font=font(36), fill=ink)
d.text((60, 1080), "भुगतान मिला: ₹12,000 (नकद)", font=font(36), fill=ink)
d.text((60, 1150), "हस्ताक्षर ठेकेदार: ____________     मज़दूर: अंगूठा", font=font(30), fill=ink)

img = img.rotate(-1.2, expand=True, fillcolor=(230, 225, 210)).filter(ImageFilter.GaussianBlur(0.6))
img.save(OUT, quality=82)
print("wrote", OUT, img.size, "layout:", "raqm" if layout == ImageFont.Layout.RAQM else "basic")
