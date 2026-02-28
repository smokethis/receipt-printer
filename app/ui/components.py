from PIL import ImageFont

_FONT_PATH = "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf"


def _load_font(size):
    try:
        return ImageFont.truetype(_FONT_PATH, size)
    except (IOError, OSError):
        return ImageFont.load_default()


class Component:
    def __init__(self, x, y, width, height):
        self.x = x
        self.y = y
        self.width = width
        self.height = height

    def contains(self, tx, ty):
        return self.x <= tx < self.x + self.width and self.y <= ty < self.y + self.height

    def handle_tap(self, tx, ty):
        pass

    def render(self, draw):
        pass


class Button(Component):
    _BG_COLOR = (50, 100, 180)
    _TEXT_COLOR = (255, 255, 255)
    _FONT_SIZE = 24

    def __init__(self, x, y, width, height, label, on_tap):
        super().__init__(x, y, width, height)
        self.label = label
        self.on_tap = on_tap
        self._font = _load_font(self._FONT_SIZE)

    def handle_tap(self, tx, ty):
        self.on_tap()

    def render(self, draw):
        draw.rectangle(
            [self.x, self.y, self.x + self.width - 1, self.y + self.height - 1],
            fill=self._BG_COLOR,
        )
        bbox = draw.textbbox((0, 0), self.label, font=self._font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        text_x = self.x + (self.width - text_w) // 2
        text_y = self.y + (self.height - text_h) // 2
        draw.text((text_x, text_y), self.label, stroke_width=1, stroke_fill=(0,0,0), font=self._font, fill=self._TEXT_COLOR)


class Label(Component):
    _TEXT_COLOR = (255, 255, 255)
    _FONT_SIZE = 24

    def __init__(self, x, y, text, font_size=None):
        super().__init__(x, y, 0, 0)
        self.text = text
        self._font = _load_font(font_size or self._FONT_SIZE)

    def render(self, draw):
        draw.text((self.x, self.y), self.text, stroke_width=1, stroke_fill=(0,0,0), font=self._font, fill=self._TEXT_COLOR)
