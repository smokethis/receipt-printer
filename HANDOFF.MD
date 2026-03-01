# Claude Code Handoff: ROOT CAUSE FOUND — 16-bit Shift Register Fix

## The Root Cause

The Waveshare 4" ILI9486 display does NOT have a native SPI interface. It uses
**two 74HC4094 shift registers** on the carrier PCB to convert SPI into a 16-bit
parallel bus. The ILI9486 chip itself runs in **16-bit parallel mode**.

This means every SPI byte pair fills the 16-bit shift register, which then
latches onto the ILI9486's parallel data bus. The ILI9486 reads 16-bit words,
not 8-bit bytes.

### Why solid fills worked

RGB565 pixels are 16 bits — one pixel = one shift register word. When every
pixel is the same color, the byte order within each word doesn't matter much
(and for extreme values like black 0x0000 and white 0xFFFF, byte-swapping
is a no-op).

### Why gradients broke

Our command parameters were sent as single bytes, but the shift register
combines adjacent bytes into 16-bit words. The ILI9486's init registers were
receiving garbage values from misaligned byte pairs. In particular, the gamma
curve registers (0xE0, 0xE1, 0xE2) were receiving wrong values, causing the
non-monotonic brightness transfer function.

### Proof

The fbcp-ili9341 project (which successfully drives this exact display) pads
EVERY command parameter with 0x00:

```c
// fbcp-ili9341/ili9486.cpp — note the 0x00 padding before each value:
SPI_TRANSFER(0xE0, 0x00,0x00, 0x00,0x2C, 0x00,0x2C, 0x00,0x0B, ...);
//                 ^^^^pad  ^^^^pad  ^^^^pad  ^^^^pad
```

This is gated behind `DISPLAY_SPI_BUS_IS_16BITS_WIDE`.

## The Fix for app/display.py

We need to go back to direct SPI (not fbtft) and pad all command parameters.
The fbtft driver cannot be fixed without kernel module changes.

### 1. Command sending must pad parameters to 16 bits

Every command byte is sent alone (with DC low). But command parameters and
pixel data are sent with DC high. Each parameter byte needs a 0x00 prefix
to form a proper 16-bit shift register word.

**Old (broken):**
```python
def _command(self, cmd, *data):
    # DC low, send command
    lgpio.gpio_write(self._gpio, _PIN_DC, 0)
    self._spi.xfer2([cmd])
    if data:
        lgpio.gpio_write(self._gpio, _PIN_DC, 1)
        self._spi.xfer2(list(data))
```

**New (fixed):**
```python
def _command(self, cmd, *data):
    # DC low, send command byte (padded to 16 bits)
    lgpio.gpio_write(self._gpio, _PIN_DC, 0)
    self._spi.xfer2([0x00, cmd])
    if data:
        # DC high, send each parameter byte padded to 16 bits
        lgpio.gpio_write(self._gpio, _PIN_DC, 1)
        padded = []
        for b in data:
            padded.extend([0x00, b])
        self._spi.xfer2(padded)
```

### 2. Use COLMOD=0x55 (RGB565, 16-bit pixels)

With RGB565, each pixel is 16 bits = one shift register word. This means
pixel data does NOT need extra padding — it's naturally 16-bit aligned.

The init sequence must set:
```python
self._command(0x3A, 0x55)  # COLMOD = RGB565
```

### 3. Pixel data: send RGB565 big-endian, no padding needed

Each 16-bit RGB565 pixel fills exactly one shift register word. Big-endian
byte order means the first byte goes to the high 8 bits and the second byte
goes to the low 8 bits of the shift register, matching the ILI9486's
16-bit parallel interface.

**Pixel conversion (same as current code, which is already correct):**
```python
raw = np.frombuffer(rotated.tobytes(), dtype=np.uint8)
r = raw[0::3].astype(np.uint16)
g = raw[1::3].astype(np.uint16)
b = raw[2::3].astype(np.uint16)
rgb565 = (r & 0xF8) << 8 | (g & 0xFC) << 3 | b >> 3
data = rgb565.astype('>u2').tobytes()  # big-endian
```

This produces 2 bytes per pixel in big-endian order, which is exactly what the
16-bit shift register needs.

### 4. Full init sequence with 16-bit padding

Use the fbcp-ili9341 init sequence as reference. Here are the key registers
with proper padding (each parameter preceded by 0x00 in the _command call):

```python
def _init_panel(self):
    self._reset()
    self._command(0xB0, 0x00)          # Interface Mode Control
    self._command(0x11)                 # Sleep Out
    time.sleep(0.25)
    self._command(0x3A, 0x55)          # COLMOD: RGB565

    # MADCTL — for landscape 480×320 with BGR subpixel order
    # Adjust MX/MY/MV bits as needed for desired orientation
    self._command(0x36, 0x48)          # MX + BGR

    # Power Control
    self._command(0xC2, 0x44)
    self._command(0xC5, 0x00, 0x00, 0x00, 0x00)

    # Positive Gamma — use Waveshare values, NOT PiScreen values
    self._command(0xE0,
        0x0F, 0x1F, 0x1C, 0x0C, 0x0F, 0x08, 0x48, 0x98,
        0x37, 0x0A, 0x13, 0x04, 0x11, 0x0D, 0x00)
    # Negative Gamma
    self._command(0xE1,
        0x0F, 0x32, 0x2E, 0x0B, 0x0D, 0x05, 0x47, 0x75,
        0x37, 0x06, 0x10, 0x03, 0x24, 0x20, 0x00)
    # Digital Gamma
    self._command(0xE2,
        0x0F, 0x32, 0x2E, 0x0B, 0x0D, 0x05, 0x47, 0x75,
        0x37, 0x06, 0x10, 0x03, 0x24, 0x20, 0x00)

    self._command(0x11)                # Sleep Out (again)
    self._command(0x29)                # Display On
```

The gamma values above are the kernel driver's values. They MIGHT need to
change to Waveshare-specific values, but the padding fix should make them
work correctly first. If colors still look off after the padding fix,
try the values from fbcp-ili9341's ili9486.cpp.

### 5. Write method with column/row addressing

```python
def write(self, img):
    rotated = img.transpose(Image.Transpose.ROTATE_90)
    # ... RGB565 conversion as before ...

    # Column address set: 0–319
    self._command(0x2A, 0x00, 0x00, 0x01, 0x3F)
    # Row address set: 0–479
    self._command(0x2B, 0x00, 0x00, 0x01, 0xDF)
    # Memory Write
    self._command(0x2C)
    # Pixel data — 16-bit aligned, no extra padding needed
    self._data(data)
```

### 6. Data sending — pixel data does NOT need padding

The `_data()` method sends raw pixel bytes. Since RGB565 pixels are 16-bit
aligned, they don't need 0x00 padding:

```python
def _data(self, data):
    lgpio.gpio_write(self._gpio, _PIN_DC, 1)
    data = bytes(data)
    chunk = 4096
    for i in range(0, len(data), chunk):
        self._spi.writebytes2(data[i:i + chunk])
```

This stays the same as current code.

## What to change

1. **app/display.py**: Update `_command()` to pad each byte to 16 bits
2. **app/display.py**: Ensure COLMOD is 0x55 (RGB565) — it already is
3. **app/display.py**: No changes needed to `_data()` or `write()`
4. **diagnose_display.py**: Update the direct SPI tests to use 16-bit padded
   commands and RGB565 pixel data for a confirmation test

## Confirmation test first

Before changing app/display.py, add a quick confirmation test to
diagnose_display.py:

```python
def tv_padded_gradient():
    """Test gradient with 16-bit padded commands and RGB565 pixel data."""
    before("TV: PADDED 16-BIT — gradient with shift-register-aware commands",
           """
Full hardware reset, then init with ALL command parameters padded
to 16 bits (0x00 prefix on each parameter byte). Uses COLMOD=0x55
(RGB565) with 2 bytes per pixel (no padding on pixel data).

If this is smooth, the 16-bit shift register hypothesis is confirmed.
           """)

    if _get_spi() is None:
        print("  spidev/lgpio not available — skipping")
        after("Could not run.")
        return

    import time
    spi, gpio = _get_spi()
    import lgpio as _lgpio

    def cmd16(c, *data):
        """Send command + parameters, all padded to 16 bits."""
        _lgpio.gpio_write(gpio, 24, 0)   # DC low
        spi.xfer2([0x00, c])              # command padded
        if data:
            _lgpio.gpio_write(gpio, 24, 1)  # DC high
            padded = []
            for b in data:
                padded.extend([0x00, b])
            spi.xfer2(padded)

    def send_data(buf):
        _lgpio.gpio_write(gpio, 24, 1)
        buf = bytes(buf)
        for i in range(0, len(buf), 4096):
            spi.writebytes2(buf[i:i+4096])

    # Hardware reset
    _spi_reset()

    # Init with 16-bit padded commands
    cmd16(0xB0, 0x00)
    cmd16(0x11)
    time.sleep(0.25)
    cmd16(0x3A, 0x55)      # COLMOD = RGB565
    cmd16(0x36, 0x48)      # MADCTL: MX + BGR
    cmd16(0xC2, 0x44)
    cmd16(0xC5, 0x00, 0x00, 0x00, 0x00)

    # Gamma — kernel values (now properly padded, so panel actually receives them)
    cmd16(0xE0,
        0x0F, 0x1F, 0x1C, 0x0C, 0x0F, 0x08, 0x48, 0x98,
        0x37, 0x0A, 0x13, 0x04, 0x11, 0x0D, 0x00)
    cmd16(0xE1,
        0x0F, 0x32, 0x2E, 0x0B, 0x0D, 0x05, 0x47, 0x75,
        0x37, 0x06, 0x10, 0x03, 0x24, 0x20, 0x00)
    cmd16(0xE2,
        0x0F, 0x32, 0x2E, 0x0B, 0x0D, 0x05, 0x47, 0x75,
        0x37, 0x06, 0x10, 0x03, 0x24, 0x20, 0x00)

    cmd16(0x11)
    cmd16(0x29)
    time.sleep(0.05)

    # Set window
    cmd16(0x2A, 0x00, 0x00, 0x01, 0x3F)
    cmd16(0x2B, 0x00, 0x00, 0x01, 0xDF)
    cmd16(0x2C)

    # Build RGB565 gradient — big-endian, 2 bytes per pixel
    import struct
    buf = bytearray()
    for y in range(480):
        for col in range(320):
            r5 = col * 31 // 319
            rgb565 = r5 << 11
            buf += struct.pack('>H', rgb565)

    print(f"  Sending {len(buf)} bytes ({len(buf)//2} pixels × 2 bpp)")
    send_data(buf)

    after("""
SMOOTH RED GRADIENT
  → CONFIRMED. The 16-bit shift register was the root cause.
  → Apply the same padding fix to app/display.py.

STILL BROKEN
  → The shift register hypothesis is wrong or incomplete.
  → Report back for further analysis.
    """)
```

Wire this into `--gamma-diag` after the existing tests.

## What NOT to change yet

Do NOT modify app/display.py until TV confirms the fix works. Only add the
TV test to diagnose_display.py for now.

## fbtft is dead for this display

The fbtft fb_ili9486 kernel driver cannot work correctly with this hardware
without kernel-level modifications. The driver sends unpadded 8-bit commands
and parameters, which get mangled by the shift register. The direct SPI
approach in app/display.py is the correct path forward for this dedicated
embedded device.

## Summary

The entire debugging journey:
1. Geometry/addressing → fixed (fbtft + correct overlay)
2. Gradient wrapping → caused by 16-bit shift register on Waveshare PCB
3. The shift register requires 0x00 padding on all command parameters
4. Pixel data (RGB565, 16-bit) is naturally aligned — no padding needed
5. The fbtft driver doesn't know about the shift register → abandon fbtft
6. Fix app/display.py to use padded commands + direct SPI