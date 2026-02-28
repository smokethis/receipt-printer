import os
from PIL import ImageFont

# ── Palette ──────────────────────────────────────────────────────────────────
COLOR_BG     = (30,  30,  35)   # screen background
COLOR_BUTTON = (50, 100, 180)   # button fill
COLOR_TEXT   = (255, 255, 255)  # primary text

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
