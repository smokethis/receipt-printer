import time

import numpy as np
from PIL import Image

try:
    import spidev
    import lgpio
    _HW_AVAILABLE = True
except ImportError:
    _HW_AVAILABLE = False

DISPLAY_WIDTH = 480
DISPLAY_HEIGHT = 320

# GPIO pin numbers (BCM)
_PIN_DC = 24
_PIN_RST = 25
_PIN_LED = 18

# SPI settings
_SPI_BUS = 0
_SPI_DEVICE = 0
_SPI_SPEED = 16_000_000


class ILI9486:
    def __init__(self):
        if not _HW_AVAILABLE:
            raise RuntimeError("spidev/lgpio not available — not running on Pi?")

        self._spi = spidev.SpiDev()
        self._spi.open(_SPI_BUS, _SPI_DEVICE)
        self._spi.max_speed_hz = _SPI_SPEED
        self._spi.mode = 0

        self._gpio = lgpio.gpiochip_open(0)
        lgpio.gpio_claim_output(self._gpio, _PIN_DC)
        lgpio.gpio_claim_output(self._gpio, _PIN_RST)
        lgpio.gpio_claim_output(self._gpio, _PIN_LED)

        self.backlight(True)
        self._init_panel()

    def _command(self, cmd, *data):
        """Pull DC low, send command byte; if data given, pull DC high and send.

        Every byte is padded to 16 bits (0x00 prefix) because the Waveshare PCB
        uses two 74HC4094 shift registers that latch SPI bytes in 16-bit pairs
        onto the ILI9486's parallel data bus.
        """
        lgpio.gpio_write(self._gpio, _PIN_DC, 0)
        self._spi.xfer2([0x00, cmd])
        if data:
            lgpio.gpio_write(self._gpio, _PIN_DC, 1)
            padded = []
            for b in data:
                padded.extend([0x00, b])
            self._spi.xfer2(padded)

    def _data(self, data):
        """Send raw bytes with DC high, chunked to respect spidev's transfer limit."""
        lgpio.gpio_write(self._gpio, _PIN_DC, 1)
        data = bytes(data)
        chunk = 4096
        for i in range(0, len(data), chunk):
            self._spi.writebytes2(data[i:i + chunk])

    def _reset(self):
        lgpio.gpio_write(self._gpio, _PIN_RST, 1)
        time.sleep(0.01)
        lgpio.gpio_write(self._gpio, _PIN_RST, 0)
        time.sleep(0.10)   # 100 ms active-low pulse
        lgpio.gpio_write(self._gpio, _PIN_RST, 1)
        time.sleep(0.12)   # 120 ms post-reset settle

    def _init_panel(self):
        self._reset()

        # Interface Mode Control
        self._command(0xB0, 0x00)
        # Sleep Out — must be followed by ≥120 ms delay
        self._command(0x11)
        time.sleep(0.25)
        # COLMOD: 16-bit colour (RGB565) — correct for parallel mode via shift register
        self._command(0x3A, 0x55)
        # MADCTL: BGR subpixel order (bit 3), MX/MY for correct landscape orientation
        self._command(0x36, 0x48)
        # Power Control 3
        self._command(0xC2, 0x44)
        # VCOM Control 1
        self._command(0xC5, 0x00, 0x00, 0x00, 0x00)
        # PGAMCTRL (Positive Gamma) — 15 values from kernel fb_ili9486.c
        self._command(0xE0,
            0x0F, 0x1F, 0x1C, 0x0C, 0x0F, 0x08, 0x48, 0x98,
            0x37, 0x0A, 0x13, 0x04, 0x11, 0x0D, 0x00)
        # NGAMCTRL (Negative Gamma)
        self._command(0xE1,
            0x0F, 0x32, 0x2E, 0x0B, 0x0D, 0x05, 0x47, 0x75,
            0x37, 0x06, 0x10, 0x03, 0x24, 0x20, 0x00)
        # Digital Gamma Control 1
        self._command(0xE2,
            0x0F, 0x32, 0x2E, 0x0B, 0x0D, 0x05, 0x47, 0x75,
            0x37, 0x06, 0x10, 0x03, 0x24, 0x20, 0x00)
        # Sleep Out (repeated as in kernel source)
        self._command(0x11)
        # Display On
        self._command(0x29)

    def write(self, img):
        """Accept a 480×320 PIL RGB image, rotate to portrait, convert to RGB565, send."""
        # Rotate landscape→portrait: 480×320 becomes 320×480
        rotated = img.transpose(Image.Transpose.ROTATE_90)
        # RGB888 → RGB565, big-endian (MSB first) for the 16-bit shift register
        raw = np.frombuffer(rotated.tobytes(), dtype=np.uint8)
        r = raw[0::3].astype(np.uint16)
        g = raw[1::3].astype(np.uint16)
        b = raw[2::3].astype(np.uint16)
        rgb565 = (r & 0xF8) << 8 | (g & 0xFC) << 3 | b >> 3
        data = rgb565.astype('>u2').tobytes()

        # Column address set: 0–319 (0x013F)
        self._command(0x2A, 0x00, 0x00, 0x01, 0x3F)
        # Row address set: 0–479 (0x01DF)
        self._command(0x2B, 0x00, 0x00, 0x01, 0xDF)
        # Memory Write, then pixel data
        self._command(0x2C)
        self._data(data)

    def backlight(self, on):
        lgpio.gpio_write(self._gpio, _PIN_LED, 1 if on else 0)

    def close(self):
        self.backlight(False)
        self._spi.close()
        lgpio.gpiochip_close(self._gpio)


_display = None


def get_display():
    global _display
    if _display is None:
        _display = ILI9486()
    return _display


def write_to_display(img):
    get_display().write(img)
