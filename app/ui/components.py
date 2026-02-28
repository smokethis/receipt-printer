from app.ui.theme import (
    COLOR_BUTTON, COLOR_TEXT,
    FONT_SIZE_NORMAL, load_font,
)


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
    def __init__(self, x, y, width, height, label, on_tap):
        super().__init__(x, y, width, height)
        self.label = label
        self.on_tap = on_tap
        self._font = load_font(FONT_SIZE_NORMAL)

    def handle_tap(self, tx, ty):
        self.on_tap()

    def render(self, draw):
        draw.rectangle(
            [self.x, self.y, self.x + self.width - 1, self.y + self.height - 1],
            fill=COLOR_BUTTON,
        )
        bbox = draw.textbbox((0, 0), self.label, font=self._font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        text_x = self.x + (self.width - text_w) // 2
        text_y = self.y + (self.height - text_h) // 2
        draw.text((text_x, text_y), self.label, font=self._font, fill=COLOR_TEXT)


class Label(Component):
    def __init__(self, x, y, text, font_size=None):
        super().__init__(x, y, 0, 0)
        self.text = text
        self._font = load_font(font_size or FONT_SIZE_NORMAL)

    def render(self, draw):
        draw.text((self.x, self.y), self.text, font=self._font, fill=COLOR_TEXT)
