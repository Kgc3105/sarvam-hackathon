"""Generates public/icon-192.png and public/icon-512.png for the installable app."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

PUBLIC = Path(__file__).resolve().parent.parent / "public"
for size in (192, 512):
    img = Image.new("RGB", (size, size), (31, 42, 90))
    d = ImageDraw.Draw(img)
    pad = size // 10
    d.ellipse([pad, pad, size - pad, size - pad], fill=(242, 162, 12))
    font = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", int(size * 0.42))
    d.text((size / 2, size / 2), "₹", font=font, fill=(31, 42, 90), anchor="mm")
    img.save(PUBLIC / f"icon-{size}.png")
    print("wrote", PUBLIC / f"icon-{size}.png")
