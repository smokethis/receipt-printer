from app.ui.screen import Screen
from app.ui.components import Button
from app.display import DISPLAY_WIDTH, DISPLAY_HEIGHT

_COLS = 2
_ROWS = 2
_PAD = 10
_BUTTON_W = (DISPLAY_WIDTH - _PAD * (_COLS + 1)) // _COLS
_BUTTON_H = (DISPLAY_HEIGHT - _PAD * (_ROWS + 1)) // _ROWS

_MENU_ITEMS = [
    ("Print Food",    "print_food"),
    ("Find Recipe",   "find_recipe"),
    ("Ask Question",  "ask_question"),
    ("Settings",      "settings"),
]


class MainMenuScreen(Screen):
    def __init__(self, screen_manager):
        super().__init__()
        for i, (label, target) in enumerate(_MENU_ITEMS):
            col = i % _COLS
            row = i // _COLS
            x = _PAD + col * (_BUTTON_W + _PAD)
            y = _PAD + row * (_BUTTON_H + _PAD)
            self.components.append(
                Button(x, y, _BUTTON_W, _BUTTON_H, label,
                       lambda t=target: screen_manager.switch_to(t))
            )
