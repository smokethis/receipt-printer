# Display Investigation: ILI9486 Gradient Rendering

## The Problem

Solid colour fills rendered correctly, but any gradient or varying-brightness
pattern showed non-monotonic brightness — values would rise to a peak, dip back
down, then rise again instead of smoothly increasing. The issue persisted across
every software configuration we tested.

## What We Ruled Out

We ran roughly 20 diagnostic tests eliminating potential causes:

- **Framebuffer integrity**: bytes written to `/dev/fb1` read back identically
- **Byte order**: little-endian confirmed correct; big-endian produced garbage
- **Pixel format**: broken under both RGB565 (COLMOD=0x55) and RGB666 (0x66)
- **Gamma curves**: broken with kernel defaults, Waveshare values, and panel
  factory defaults (no gamma registers written at all)
- **Power/VCOM registers**: broken even with minimal init (Sleep Out + COLMOD +
  Display On, nothing else)
- **SPI mode**: mode 0 correct; modes 1–3 degraded or failed
- **SPI bit order**: bit-reversed data produced garbage, confirming MSB-first
  is correct
- **Window addressing**: column/row geometry was correct

## The Breakthrough

A 16-block transfer function test (test TR) displayed solid blocks at 16
evenly-spaced red values. Each block was uniform, but their brightness was
**non-monotonic** — individual pixel values were being mapped to wrong
brightness levels even in solid fills. This proved the issue was in value
interpretation, not spatial rendering.

## Root Cause

The Waveshare 4" LCD carrier PCB has **two 74HC4094 shift registers** between
the SPI bus and the ILI9486 chip. The ILI9486 itself runs in **16-bit parallel
mode**, not SPI mode. The shift registers convert the SPI byte stream into
16-bit parallel words.

This means every byte we send over SPI gets paired with an adjacent byte to
form a 16-bit word on the ILI9486's data bus. Command parameters sent as
single bytes get combined with neighbouring bytes into garbled 16-bit values.

In particular, the gamma curve registers (0xE0, 0xE1, 0xE2) — which control
the voltage-to-brightness transfer function — were receiving garbage values.
This produced the non-monotonic brightness mapping.

### Why solid fills worked

Extreme values like black (0x0000) and white (0xFFFF) are symmetrical across
byte boundaries. Mid-tone solid fills appeared uniform because every pixel had
the same (wrong) brightness — you can't see a transfer function error when
there's only one input value on screen.

### Why the fbtft kernel driver can't work

The `fb_ili9486` fbtft driver sends unpadded 8-bit commands and parameters. It
has no awareness of the shift register hardware. This is unfixable without
kernel module changes.

## The Fix

All command parameters must be **padded to 16 bits** by prefixing each byte
with 0x00, so each parameter fills one complete shift register word:

```python
def _command(self, cmd, *data):
    lgpio.gpio_write(self._gpio, _PIN_DC, 0)
    self._spi.xfer2([0x00, cmd])          # command byte, padded
    if data:
        lgpio.gpio_write(self._gpio, _PIN_DC, 1)
        padded = []
        for b in data:
            padded.extend([0x00, b])      # each param byte, padded
        self._spi.xfer2(padded)
```

Pixel data in RGB565 mode (COLMOD=0x55) does **not** need padding — each
16-bit pixel naturally fills one shift register word.

This approach is consistent with the [fbcp-ili9341](https://github.com/juj/fbcp-ili9341)
project, which successfully drives this display using a `DISPLAY_SPI_BUS_IS_16BITS_WIDE`
compile flag, and the [micropython discussion](https://github.com/orgs/micropython/discussions/10404)
that first documented the shift register architecture.

## Architecture Going Forward

Direct SPI from Python (bypassing fbtft) using:

- 16-bit padded commands via `spidev`
- COLMOD=0x55 (RGB565, 16-bit pixels)
- Pillow for rendering → NumPy for RGB888→RGB565 conversion → SPI transfer