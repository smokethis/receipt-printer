from PIL import ImageFont

# ── Palette ──────────────────────────────────────────────────────────────────
COLOR_BG     = (30,  30,  35)   # screen background
COLOR_BUTTON = (50, 100, 180)   # button fill
COLOR_TEXT   = (255, 255, 255)  # primary text
COLOR_STROKE = (0,   0,   0)    # text stroke / shadow

# ── Font sizes ────────────────────────────────────────────────────────────────
FONT_SIZE_NORMAL  = 24
FONT_SIZE_HEADING = 32

# ── Font loader ───────────────────────────────────────────────────────────────
_FONT_PATH = "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf"


def load_font(size=FONT_SIZE_NORMAL):
    try:
        return ImageFont.truetype(_FONT_PATH, size)
    except (IOError, OSError):
        return ImageFont.load_default()
