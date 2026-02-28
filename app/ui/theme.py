import os
from PIL import ImageFont

# ── Palette ──────────────────────────────────────────────────────────────────
COLOR_BG     = (15,  15,  18)   # screen background
COLOR_BUTTON = (30,  60, 110)   # button fill
COLOR_TEXT   = (180, 180, 180)  # primary text

# ── Font sizes ────────────────────────────────────────────────────────────────
FONT_SIZE_NORMAL  = 24
FONT_SIZE_HEADING = 32

# ── Font loader ───────────────────────────────────────────────────────────────
_FONT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "assets", "fonts")


def load_font(size=FONT_SIZE_NORMAL):
    path = os.path.join(_FONT_DIR, f"ter-u{size}b.pil")
    try:
        return ImageFont.load(path)
    except (IOError, OSError):
        return ImageFont.load_default()
