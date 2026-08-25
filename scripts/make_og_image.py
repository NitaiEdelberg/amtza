"""Regenerate frontend/public/og-image.png — the social-share / link-preview card.

Run after changing the title or tagline:
    backend/venv/bin/pip install Pillow      # not a runtime dependency
    backend/venv/bin/python scripts/make_og_image.py

It has to be a raster image: og:image is read by Facebook, WhatsApp, Slack and
X, none of which render SVG, so the app's own SVG assets can't stand in.

1200x630 is the size every one of those crops to.
"""
from PIL import Image, ImageDraw, ImageFont, features
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "frontend" / "public" / "og-image.png"
W, H = 1200, 630

# Pillow bundles libraqm, which applies the bidi algorithm, so Hebrew strings are
# passed in logical order and come out laid right-to-left. Reversing them by hand
# — the usual workaround when raqm is absent — renders אמצע as עצמא here.
assert features.check("raqm"), "Pillow without raqm would lay Hebrew out left-to-right"

img = Image.new("RGB", (W, H), "#0f1117")
d = ImageDraw.Draw(img)

# The app's blue→purple wash, drawn row by row, then covered by a rounded card so
# it survives only as a frame.
for y in range(H):
    t = y / H
    d.line([(0, y), (W, y)], fill=(int(0x6c + (0xa7 - 0x6c) * t),
                                   int(0x8e + (0x8b - 0x8e) * t),
                                   int(0xff + (0xfa - 0xff) * t)))
d.rounded_rectangle([28, 28, W - 28, H - 28], radius=28, fill="#0f1117")

FONT_DIR = "/usr/share/fonts/truetype/dejavu"
f_title = ImageFont.truetype(f"{FONT_DIR}/DejaVuSans-Bold.ttf", 150)
f_he = ImageFont.truetype(f"{FONT_DIR}/DejaVuSans.ttf", 52)
f_en = ImageFont.truetype(f"{FONT_DIR}/DejaVuSans.ttf", 46)
f_foot = ImageFont.truetype(f"{FONT_DIR}/DejaVuSans.ttf", 34)


def centre(text, font, y, fill):
    d.text(((W - d.textbbox((0, 0), text, font=font)[2]) / 2, y), text, font=font, fill=fill)


centre("אמצע", f_title, 120, "#a5b9ff")
centre("מצאו את המילה שבאמצע", f_he, 315, "#e8eaf6")
centre("Find the word in the middle", f_en, 395, "#9ca3c4")
centre("עברית · English", f_foot, 495, "#6c8eff")

img.save(OUT, optimize=True)
print(f"wrote {OUT} ({img.size[0]}x{img.size[1]})")
