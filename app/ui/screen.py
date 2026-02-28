from app.display import DISPLAY_WIDTH, DISPLAY_HEIGHT
from app.ui.theme import COLOR_BG
import logging
log = logging.getLogger(__name__)


class Screen:
    _BG_COLOR = COLOR_BG

    def __init__(self):
        self.components = []
        self.dirty = True

    def handle_tap(self, x, y):
        for component in self.components:
            if component.contains(x, y):
                component.handle_tap(x, y)
                break

    def render(self, draw):
        draw.rectangle([0, 0, DISPLAY_WIDTH - 1, DISPLAY_HEIGHT - 1], fill=self._BG_COLOR)
        for component in self.components:
            component.render(draw)


class ScreenManager:
    def __init__(self):
        self.screens = {}
        self._active_name = None
        self._dirty = False

    @property
    def active_screen(self):
        return self.screens.get(self._active_name)

    @property
    def dirty(self):
        active = self.active_screen
        return self._dirty or (active.dirty if active else False)

    @dirty.setter
    def dirty(self, value):
        self._dirty = value
        active = self.active_screen
        if active:
            active.dirty = value

    def add(self, name, screen):
        self.screens[name] = screen

    def switch_to(self, name):
        self._active_name = name
        self._dirty = True
