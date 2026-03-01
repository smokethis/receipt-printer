import textwrap
import threading
import logging

from app.display import DISPLAY_WIDTH, DISPLAY_HEIGHT
from app.ui.components import Button
from app.ui.screen import Screen
from app.ui.theme import COLOR_BG, COLOR_TEXT, FONT_SIZE_NORMAL, FONT_SIZE_HEADING, load_font

logger = logging.getLogger(__name__)

# ── layout constants ──────────────────────────────────────────────────────────
_PAD    = 12
_BTN_W  = DISPLAY_WIDTH - _PAD * 2   # 456 px
_BTN_H  = 52
_BACK_W = 100
_BACK_H = 44
_NAV_W  = 100
_BOT_Y  = DISPLAY_HEIGHT - _BACK_H - _PAD   # 264 — bottom row y
_WRAP   = 36                                  # chars per wrapped line
_LINE_H = FONT_SIZE_NORMAL                    # 24 px
_LPP    = (_BOT_Y - _PAD) // _LINE_H         # lines per page ≈ 10


class FindRecipeScreen(Screen):
    def __init__(self, screen_manager):
        super().__init__()
        self._sm           = screen_manager
        self._state        = "ask_comfort"
        self._font         = load_font(FONT_SIZE_NORMAL)
        self._font_head    = load_font(FONT_SIZE_HEADING)
        self._suggestions  = []
        self._recipe_lines = []
        self._recipe_page  = 0
        self._error        = None
        self._rebuild()

    # ── state machine ─────────────────────────────────────────────────────────

    def _set_state(self, state):
        self._state = state
        self._rebuild()
        self.dirty = True

    def _rebuild(self):
        self.components = []
        builder = getattr(self, f"_build_{self._state}", None)
        if builder:
            builder()

    # ── component builders ────────────────────────────────────────────────────

    def _build_ask_comfort(self):
        half = (DISPLAY_WIDTH - _PAD * 3) // 2
        self.components += [
            Button(_PAD,           110, half, 70, "Yes",
                   lambda: self._start_search(True)),
            Button(_PAD * 2 + half, 110, half, 70, "No",
                   lambda: self._start_search(False)),
            Button(_PAD, _BOT_Y, _BACK_W, _BACK_H,
                   "Back", lambda: self._sm.switch_to("menu")),
        ]

    def _build_loading(self):
        pass  # render() draws the centred message; no buttons needed

    def _build_recipe_loading(self):
        pass

    def _build_suggestions(self):
        for i, s in enumerate(self._suggestions):
            label = s["name"]
            if s.get("comfort_match"):
                label += " (fav)"
            self.components.append(Button(
                _PAD, _PAD + i * (_BTN_H + _PAD), _BTN_W, _BTN_H,
                label[:34],
                lambda n=s["name"]: self._start_recipe(n),
            ))
        self.components.append(Button(
            _PAD, _BOT_Y, _BACK_W, _BACK_H,
            "Back", lambda: self._set_state("ask_comfort"),
        ))

    def _build_recipe(self):
        total = self._total_pages()
        if self._recipe_page > 0:
            self.components.append(Button(
                _PAD + _BACK_W + _PAD, _BOT_Y, _NAV_W, _BACK_H,
                "< Prev", lambda: self._turn_page(-1),
            ))
        if self._recipe_page < total - 1:
            self.components.append(Button(
                DISPLAY_WIDTH - _NAV_W - _PAD, _BOT_Y, _NAV_W, _BACK_H,
                "Next >", lambda: self._turn_page(1),
            ))
        self.components.append(Button(
            _PAD, _BOT_Y, _BACK_W, _BACK_H,
            "Back", lambda: self._set_state("suggestions"),
        ))

    def _build_error(self):
        self.components.append(Button(
            _PAD, _BOT_Y, _BACK_W, _BACK_H,
            "Back", lambda: self._set_state("ask_comfort"),
        ))

    # ── pagination ────────────────────────────────────────────────────────────

    def _total_pages(self):
        return max(1, -(-len(self._recipe_lines) // _LPP))  # ceiling division

    def _turn_page(self, delta):
        self._recipe_page = max(0, min(self._total_pages() - 1,
                                       self._recipe_page + delta))
        self.components = []
        self._build_recipe()
        self.dirty = True

    # ── background workers ────────────────────────────────────────────────────

    def _start_search(self, comfort_mode):
        self._set_state("loading")
        threading.Thread(target=self._fetch_suggestions,
                         args=(comfort_mode,), daemon=True).start()

    def _fetch_suggestions(self, comfort_mode):
        try:
            from app.claude import get_suggestions
            self._suggestions = get_suggestions(comfort_mode)
            self._set_state("suggestions")
        except Exception as exc:
            logger.exception("get_suggestions failed")
            self._error = str(exc)
            self._set_state("error")

    def _start_recipe(self, name):
        self._set_state("recipe_loading")
        threading.Thread(target=self._fetch_recipe,
                         args=(name,), daemon=True).start()

    def _fetch_recipe(self, name):
        try:
            from app.claude import get_recipe
            data = get_recipe(name)
            self._recipe_lines = self._format_recipe(data)
            self._recipe_page  = 0
            self._set_state("recipe")
        except Exception as exc:
            logger.exception("get_recipe failed")
            self._error = str(exc)
            self._set_state("error")

    # ── recipe formatting ─────────────────────────────────────────────────────

    @staticmethod
    def _format_recipe(r):
        def wrap(s):
            return textwrap.wrap(s, _WRAP) or [s]

        lines = [r.get("name", "Recipe"), f"Serves: {r.get('serves', '?')}", ""]

        lines.append("Ingredients:")
        for ing in r.get("ingredients", []):
            lines += wrap(f"  {ing['item']}: {ing['quantity']}")

        if r.get("youll_need"):
            lines += ["", "You'll need:"]
            lines += [f"  {x}" for x in r["youll_need"]]

        lines += ["", "Steps:"]
        for i, step in enumerate(r.get("steps", []), 1):
            lines += wrap(f"{i}. {step}")

        return lines

    # ── render ────────────────────────────────────────────────────────────────

    def render(self, draw):
        draw.rectangle([0, 0, DISPLAY_WIDTH - 1, DISPLAY_HEIGHT - 1], fill=COLOR_BG)

        if self._state in ("loading", "recipe_loading"):
            msg = ("Finding recipes..."
                   if self._state == "loading"
                   else "Getting recipe...")
            bb = draw.textbbox((0, 0), msg, font=self._font)
            tw, th = bb[2] - bb[0], bb[3] - bb[1]
            draw.text(((DISPLAY_WIDTH - tw) // 2, (DISPLAY_HEIGHT - th) // 2),
                      msg, font=self._font, fill=COLOR_TEXT)

        elif self._state == "ask_comfort":
            draw.text((_PAD, _PAD), "Find Recipe",
                      font=self._font_head, fill=COLOR_TEXT)
            draw.text((_PAD, _PAD + FONT_SIZE_HEADING + 8),
                      "Comfort food?", font=self._font, fill=COLOR_TEXT)

        elif self._state == "recipe":
            start = self._recipe_page * _LPP
            y = _PAD
            for i, line in enumerate(self._recipe_lines[start:start + _LPP]):
                if i == 0 and start == 0:
                    draw.text((_PAD, y), line, font=self._font_head, fill=COLOR_TEXT)
                    y += FONT_SIZE_HEADING
                else:
                    draw.text((_PAD, y), line, font=self._font, fill=COLOR_TEXT)
                    y += _LINE_H

        elif self._state == "error":
            draw.text((_PAD, _PAD), "Error", font=self._font_head, fill=COLOR_TEXT)
            y = _PAD + FONT_SIZE_HEADING + 8
            for line in textwrap.wrap(self._error or "Unknown error", _WRAP):
                draw.text((_PAD, y), line, font=self._font, fill=COLOR_TEXT)
                y += _LINE_H

        for component in self.components:
            component.render(draw)
