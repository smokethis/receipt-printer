#!/usr/bin/env python3
"""
ILI9486 orientation diagnostic — via /dev/fb1 (fbtft framebuffer).

Requires the following in /boot/firmware/config.txt (or /boot/config.txt):
  dtoverlay=fbtft,ili9486,bgr=1,speed=16000000,rotate=0,dc_pin=24,reset_pin=25,led_pin=18

Tests:
  T1  ALIVE      — full white fill
  T2  ROW 0      — thick white bar at framebuffer rows 0–39
  T3  COL 0      — thick white bar at framebuffer cols 0–39
  T4  ORIGIN     — L-bracket at (col=0, row=0)
  T5  MIDPOINT   — cross at the centre of each axis
  T6  GRADIENT   — smooth red gradient left→right to check for banding
  TH  SPI CONFIG   — read driver's SPI bit-order and mode flags
  TI  BITREV       — pre-reversed gradient to test for bit-reversal in pipeline
  TJ  DRIVER INFO  — dump fbtft module and device parameters from sysfs
  TK  GAMMA BYPASS — write linear gamma and retest red gradient
  TL  SNOOP SPI    — check fbtft pixel format conversion (RGB565→RGB666?)
  TM  DIRECT SPI   — RGB666 gradient bypassing fbtft entirely
  TN  NO GAMMA     — full reinit without gamma registers, then gradient
  TO  WS GAMMA     — reinit with Waveshare gamma values, then gradient
  TP  MINIMAL INIT — bare minimum init (sleep out + COLMOD only), then gradient
  TQ  RGB565 MIN   — same minimal init but COLMOD=0x55 with 2-byte pixels
  TR  TRANSFER FN  — 16 discrete brightness blocks to map the exact input→brightness curve
  TS  BITREV DIRECT — bit-reversed gradient bytes via direct SPI
  TT  SPI MODES    — test all 4 SPI clock modes with red/green split pattern
  TU  TRANSFER BITREV — 16 brightness blocks with bit-reversed pixel bytes
  TV  PADDED 16-BIT  — gradient with shift-register-aware 16-bit padded commands
"""

import glob
import os
import struct
import subprocess
import sys

FB_PATH   = '/dev/fb1'
FB_WIDTH  = 320
FB_HEIGHT = 480
FB_BPP    = 2   # RGB565, 2 bytes/pixel


# ── RGB565 colour helpers ──────────────────────────────────────────────────────

def _px(r, g, b):
    """Pack RGB888 into a 2-byte little-endian RGB565 value."""
    return struct.pack('<H', ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3))

WHITE = _px(255, 255, 255)
BLACK = _px(0,   0,   0  )
RED   = _px(255, 0,   0  )
GREEN = _px(0,   255, 0  )


# ── Framebuffer write helpers ──────────────────────────────────────────────────

def fill(x0, y0, x1, y1, pixel):
    """Fill a rectangle (inclusive) in the framebuffer with one colour."""
    row = pixel * (x1 - x0 + 1)
    with open(FB_PATH, 'r+b') as fb:
        for y in range(y0, y1 + 1):
            fb.seek((y * FB_WIDTH + x0) * FB_BPP)
            fb.write(row)


def clear():
    fill(0, 0, FB_WIDTH - 1, FB_HEIGHT - 1, BLACK)


# ── UI helpers ────────────────────────────────────────────────────────────────

W = 64

def before(title, body):
    """Print test description then block until the user presses Enter."""
    print(f"\n{'=' * W}")
    print(f"  {title}")
    print(f"{'─' * W}")
    for line in body.strip().splitlines():
        print(f"  {line}")
    print(f"{'─' * W}")
    print("  Press Enter to write to display ...")
    input()


def wait(message):
    """Print a sub-test prompt and block until the user presses Enter."""
    print(f"\n{'─' * W}")
    for line in message.strip().splitlines():
        print(f"  {line}")
    print(f"{'─' * W}")
    print("  Press Enter to run ...")
    input()


def after(observations):
    """Print what to observe then block until the user is ready to continue."""
    print()
    print(f"  ┌─ WHAT TO LOOK FOR {'─' * (W - 22)}")
    for line in observations.strip().splitlines():
        print(f"  │  {line}")
    print(f"  └{'─' * (W - 2)}")
    print("  Press Enter for next test ...")
    input()


# ── Tests ─────────────────────────────────────────────────────────────────────

def t1_alive():
    before("T1: ALIVE — full white fill",
           f"""
Writes white to every pixel in the {FB_WIDTH}×{FB_HEIGHT} framebuffer.
           """)
    fill(0, 0, FB_WIDTH - 1, FB_HEIGHT - 1, WHITE)
    after("""
PURE WHITE screen
  → fbtft is alive and mapped to this display. Proceed.

BACKLIGHT ON but no image / no change
  → fbtft overlay may not be active, or wrong device node.
    Stop and check config.txt + dmesg.
    """)


def t2_row_zero():
    before("T2: WHERE IS ROW 0? — white bar at framebuffer y = 0..39",
           f"""
Clears to black, then fills rows 0–39 with white (full width).
40 rows out of {FB_HEIGHT} = {40 * 100 // FB_HEIGHT}% of the display height.
           """)
    clear()
    fill(0, 0, FB_WIDTH - 1, 39, WHITE)
    after(f"""
A white bar spanning ~{40 * 100 // FB_HEIGHT}% of one axis.

Note which PHYSICAL EDGE the bar is pressed against.
That edge is where framebuffer row 0 (y=0) lives.
    """)


def t3_col_zero():
    before("T3: WHERE IS COL 0? — white bar at framebuffer x = 0..39",
           f"""
Clears to black, then fills columns 0–39 with white (full height).
40 cols out of {FB_WIDTH} = {40 * 100 // FB_WIDTH}% of the display width.
           """)
    clear()
    fill(0, 0, 39, FB_HEIGHT - 1, WHITE)
    after(f"""
A white bar spanning ~{40 * 100 // FB_WIDTH}% of one axis.

Note which PHYSICAL EDGE the bar is pressed against.
That edge is where framebuffer column 0 (x=0) lives.

After T2 and T3 you know the physical direction of each axis.
    """)


def t4_origin():
    before("T4: ORIGIN — L-bracket at (col=0, row=0)",
           """
Clears to black, then draws two overlapping bars:
  RED   bar: x = 0..29, full height  (left 30 columns)
  GREEN bar: y = 0..29, full width   (top  30 rows)

The overlap patch is the physical corner at (x=0, y=0).
           """)
    clear()
    fill(0,          0, 29,           FB_HEIGHT - 1, RED)
    fill(0,          0, FB_WIDTH - 1, 29,            GREEN)
    after("""
Look for the L-shaped corner.

The overlap patch (where RED and GREEN meet) is address (x=0, y=0).
RED arm extends along the column (x) direction.
GREEN arm extends along the row (y) direction.

Note which PHYSICAL CORNER has the overlap.
    """)


def t5_midpoint():
    cx = FB_WIDTH  // 2   # 240
    cy = FB_HEIGHT // 2   # 160
    hw = 5
    before("T5: MIDPOINT — cross at the centre of each axis",
           f"""
Clears to black, then draws:
  RED   bar: x = {cx - hw}..{cx + hw}, full height  (centred on col {cx}, half of {FB_WIDTH})
  GREEN bar: y = {cy - hw}..{cy + hw}, full width   (centred on row {cy}, half of {FB_HEIGHT})
           """)
    clear()
    fill(cx - hw, 0,       cx + hw,      FB_HEIGHT - 1, RED)
    fill(0,       cy - hw, FB_WIDTH - 1, cy + hw,       GREEN)
    after(f"""
RED bar at the physical CENTRE of the horizontal axis
  → {FB_WIDTH} columns is correct.

GREEN bar at the physical CENTRE of the vertical axis
  → {FB_HEIGHT} rows is correct.

If either bar is visibly off-centre, the assumed framebuffer
dimensions don't match the physical panel.
    """)


def ta_fbset():
    before("TA: FBSET — read kernel framebuffer geometry",
           """
Reads what the kernel thinks /dev/fb1 looks like.
Compare against our assumptions: 320×480, 16bpp, stride=640.
           """)

    result = subprocess.run(['fbset', '-fb', FB_PATH, '-i'],
                            capture_output=True, text=True)
    print(result.stdout)
    if result.stderr:
        print(f"  stderr: {result.stderr}")

    try:
        size = os.path.getsize(FB_PATH)
        expected = FB_WIDTH * FB_HEIGHT * FB_BPP
        print(f"  /dev/fb1 size : {size} bytes")
        print(f"  Expected      : {expected} bytes (={FB_WIDTH}×{FB_HEIGHT}×{FB_BPP})")
        if size != expected:
            print(f"  *** MISMATCH — off by {size - expected} bytes ***")
    except OSError as e:
        print(f"  Could not stat: {e}")

    stride_path = '/sys/class/graphics/fb1/stride'
    try:
        with open(stride_path) as f:
            stride = int(f.read().strip())
        expected_stride = FB_WIDTH * FB_BPP
        print(f"  Kernel stride : {stride} bytes/line")
        print(f"  Expected      : {expected_stride} bytes/line (={FB_WIDTH}×{FB_BPP})")
        if stride != expected_stride:
            print(f"  *** STRIDE MISMATCH ***")
    except (OSError, ValueError):
        print(f"  ({stride_path} not readable)")

    after("""
KEY THINGS TO CHECK in the fbset output:

  geometry W H W H BPP — do W and H match 320 and 480?
  Is BPP 16?

  rgba R/O,G/O,B/O,A/O — are the color bit offsets what we expect?
    RGB565 should be: 11/5, 5/6, 0/5, 0/0

  If stride ≠ 640, our row addressing is wrong and THAT explains
  the gradient banding — every row's pixels shift relative to the
  physical scanline.
    """)


def tb_step_wedge():
    before("TB: STEP WEDGE — 8 bands of known red values",
           """
8 vertical bands (40px wide), each a fixed red intensity.
Every band should be brighter than the one to its left.
If any band goes DARK unexpectedly, note which band number.
           """)
    clear()

    red_levels = [0, 36, 72, 108, 144, 180, 216, 255]
    band_w = FB_WIDTH // len(red_levels)  # 40

    for i, r in enumerate(red_levels):
        x0 = i * band_w
        x1 = x0 + band_w - 1
        pixel = _px(r, 0, 0)
        rgb565_val = ((r & 0xF8) << 8)  # green and blue are 0
        print(f"  Band {i}: r={r:3d}  RGB565=0x{rgb565_val:04X}  "
              f"bytes={pixel.hex()}  cols {x0}–{x1}")
        fill(x0, 0, x1, FB_HEIGHT - 1, pixel)

    after("""
8 bands, monotonically increasing brightness left→right.

ALL BANDS VISIBLE AND INCREASING
  → RGB565 packing is correct, bpp assumption is correct.

SOME BANDS DARK OR OUT OF ORDER
  → Note which band numbers break. The RGB565 values printed
    above will help identify the bit pattern that fails.

BANDS LOOK CORRECT BUT SHIFTED/MISALIGNED
  → Stride mismatch (check TA results).
    """)


def tc_round_trip():
    before("TC: ROUND-TRIP — write gradient row, read it back",
           """
Writes one row of gradient data to /dev/fb1, then reads it back.
Compares written vs read bytes to check for kernel transformations.
           """)

    row_buf = bytearray()
    for x in range(FB_WIDTH):
        r = x * 255 // (FB_WIDTH - 1)
        row_buf += _px(r, 0, 0)

    row_bytes = len(row_buf)
    print(f"  Row buffer: {row_bytes} bytes ({row_bytes // FB_BPP} pixels × {FB_BPP} bpp)")

    with open(FB_PATH, 'r+b') as fb:
        fb.seek(0)
        fb.write(row_buf)

    with open(FB_PATH, 'rb') as fb:
        fb.seek(0)
        readback = fb.read(row_bytes)

    if readback == bytes(row_buf):
        print("  ✓ Round-trip MATCH — bytes read back identically.")
    else:
        mismatches = sum(1 for a, b in zip(row_buf, readback) if a != b)
        print(f"  ✗ MISMATCH — {mismatches} bytes differ out of {row_bytes}")

    print(f"\n  First 20 pixels (written → readback):")
    for px_i in range(min(20, FB_WIDTH)):
        offset = px_i * FB_BPP
        w = row_buf[offset:offset + FB_BPP].hex()
        r = readback[offset:offset + FB_BPP].hex()
        match = "✓" if w == r else "✗"
        print(f"    px[{px_i:3d}]: wrote={w}  read={r}  {match}")

    after("""
ROUND-TRIP MATCH
  → The framebuffer stores our bytes as-is. The issue is in
    how the panel interprets them (color format, byte order).

MISMATCH
  → The kernel is transforming pixel data. This means our
    assumed color format (RGB565 little-endian) may be wrong.
    Check TA output for the actual rgba bit layout.
    """)


def td_solid_midred():
    before("TD: SOLID MID-RED — uniform r=128 fill",
           """
Fills entire screen with a single mid-range red (r=128, g=0, b=0).
Should be a uniform dark red. Any banding or variation means the
framebuffer is not interpreting even solid data correctly.
           """)
    fill(0, 0, FB_WIDTH - 1, FB_HEIGHT - 1, _px(128, 0, 0))
    after("""
UNIFORM DARK RED everywhere
  → Solid fills are fine, problem is specific to varying values.

VISIBLE BANDING OR PATCHES
  → Something more fundamental is wrong (stride, bpp, or palette).
    """)


def te_byte_order():
    before("TE: BYTE ORDER — little-endian vs big-endian gradient",
           """
Left half:  red gradient packed LITTLE-ENDIAN (struct '<H') — current code
Right half: red gradient packed BIG-ENDIAN (struct '>H')

One half should show a smooth black→red gradient.
The other will show banding/wrapping artifacts.
The smooth half tells us the correct byte order.
           """)
    half = FB_WIDTH // 2  # 160
    buf = bytearray()
    for y in range(FB_HEIGHT):
        for x in range(FB_WIDTH):
            # Same red value for both halves at this x position
            # Map each half independently: 0→half = full gradient range
            if x < half:
                r = x * 255 // (half - 1)
                rgb565 = ((r & 0xF8) << 8)  # only red, g=0 b=0
                buf += struct.pack('<H', rgb565)  # little-endian
            else:
                r = (x - half) * 255 // (half - 1)
                rgb565 = ((r & 0xF8) << 8)
                buf += struct.pack('>H', rgb565)  # big-endian

    with open(FB_PATH, 'r+b') as fb:
        fb.seek(0)
        fb.write(buf)

    after("""
LEFT HALF SMOOTH, RIGHT HALF BROKEN
  → Framebuffer expects little-endian. nonstd=1 means something else here.

RIGHT HALF SMOOTH, LEFT HALF BROKEN
  → Framebuffer expects big-endian. Fix _px() to use '>H' instead of '<H'.
  → This also means app/display.py needs the same fix.

BOTH BROKEN
  → The issue is not byte order. Bring results back for further analysis.

BOTH LOOK THE SAME
  → Unlikely, but would mean the red channel doesn't span the byte boundary.
    """)


def tf_r5_wedge():
    before("TF: R5 WEDGE — all 32 red values, one band each",
           """
32 vertical bands, each 10px wide (32 × 10 = 320).
Band 0 = R5=0 (black), Band 31 = R5=31 (full red).
Each band should be monotonically brighter left to right.

Count carefully from left to right. Note any bands that are
DARKER than the one to their left. Write down the band numbers
that break monotonicity.
           """)
    clear()

    band_w = FB_WIDTH // 32  # = 10
    print(f"  {'Band':>4}  {'R5':>3}  {'RGB565':>6}  {'Bytes':>6}  Cols")
    print(f"  {'─' * 44}")

    for r5 in range(32):
        rgb565 = r5 << 11  # red only, G=0 B=0
        pixel = struct.pack('<H', rgb565)

        x0 = r5 * band_w
        x1 = x0 + band_w - 1

        print(f"  {r5:4d}  {r5:3d}  0x{rgb565:04X}  {pixel.hex():>6}  {x0}–{x1}")
        fill(x0, 0, x1, FB_HEIGHT - 1, pixel)

    after("""
ALL 32 BANDS MONOTONICALLY INCREASING
  → Red channel is working correctly. The original gradient code
    had a bug. (Unlikely given TB results, but possible.)

BANDS WRAP OR CYCLE (brightness goes up, down, up, down)
  → Note EXACTLY which band numbers mark the transitions:
    - Which band is the FIRST peak (brightest before first dip)?
    - Which band is the FIRST valley (darkest after first peak)?
    - How many complete cycles can you see?
  → This tells us which bits are being interpreted differently.

EXAMPLE: If brightness peaks at band 7 (R5=0b00111) and drops at
band 8 (R5=0b01000), that means bit 3 is being subtracted instead
of added, suggesting a bit-reversal or ones-complement issue.
    """)


def tg_g6_wedge():
    before("TG: G6 WEDGE — all 64 green values, 5px bands",
           """
64 vertical bands, each 5px wide (64 × 5 = 320).
Band 0 = G6=0 (black), Band 63 = G6=63 (full green).

Same drill: note any bands that break monotonicity.
The bands will be narrow (5px) so look carefully.
           """)
    clear()

    band_w = FB_WIDTH // 64  # = 5
    print(f"  {'Band':>4}  {'G6':>3}  {'RGB565':>6}  {'Bytes':>6}  Cols")
    print(f"  {'─' * 44}")

    for g6 in range(64):
        rgb565 = g6 << 5  # green only, R=0 B=0
        pixel = struct.pack('<H', rgb565)

        x0 = g6 * band_w
        x1 = x0 + band_w - 1

        # Only print every 8th to avoid flooding the terminal
        if g6 % 8 == 0 or g6 == 63:
            print(f"  {g6:4d}  {g6:3d}  0x{rgb565:04X}  {pixel.hex():>6}  {x0}–{x1}")

        fill(x0, 0, x1, FB_HEIGHT - 1, pixel)

    after("""
ALL 64 BANDS MONOTONICALLY INCREASING
  → Green channel is fine. Issue may be red-specific.

BANDS WRAP/CYCLE SIMILARLY TO RED (TF)
  → Both channels have the same problem. Likely a COLMOD or
    SPI transfer format issue in the fbtft driver.

BANDS WRAP/CYCLE DIFFERENTLY FROM RED
  → The wrapping pattern difference tells us whether the issue
    is per-channel or related to byte boundaries.

Note: Green straddles the byte boundary in RGB565 (bits 5–10).
If the driver byte-swaps before SPI, the green bits get split
differently. This is why green is a useful comparison.
    """)


def th_spi_config():
    before("TH: SPI CONFIG — read driver's SPI settings",
           """
Reads SPI configuration from sysfs and the spidev interface.
Checks bit order (MSB-first vs LSB-first) and SPI mode.
           """)

    # Check sysfs for fb1's SPI device
    print("  --- sysfs SPI info ---")
    for path in sorted(glob.glob('/sys/bus/spi/devices/spi*')):
        name = path.split('/')[-1]
        bits = {}
        for attr in ['modalias', 'driver_override']:
            fpath = os.path.join(path, attr)
            try:
                with open(fpath) as f:
                    bits[attr] = f.read().strip()
            except (OSError, IOError):
                pass
        print(f"  {name}: {bits}")

    # Read the fbtft driver's SPI mode from the module
    # The SPI_LSB_FIRST flag is mode bit 3 (0x08)
    print()
    print("  --- SPI mode flags ---")
    print("  SPI_CPHA      = 0x01 (clock phase)")
    print("  SPI_CPOL      = 0x02 (clock polarity)")
    print("  SPI_LSB_FIRST = 0x08 (bit order)")
    print()

    # Try reading the spi mode from the device
    for path in sorted(glob.glob('/sys/bus/spi/devices/spi0.*/spi_mode')):
        try:
            with open(path) as f:
                mode_str = f.read().strip()
            # Could be hex or decimal
            if mode_str.startswith('0x'):
                mode = int(mode_str, 16)
            else:
                mode = int(mode_str)
            lsb = "YES — LSB_FIRST" if (mode & 0x08) else "no — MSB_FIRST"
            print(f"  {path}: mode=0x{mode:02X}  LSB_FIRST={lsb}")
        except (OSError, IOError, ValueError) as e:
            print(f"  {path}: error reading: {e}")

    # Also check via dmesg for fbtft init messages
    print()
    print("  --- dmesg fbtft lines ---")
    result = subprocess.run(['dmesg'], capture_output=True, text=True)
    for line in result.stdout.splitlines():
        if 'fbtft' in line.lower() or 'ili9486' in line.lower() or 'fb1' in line.lower():
            print(f"  {line.strip()}")

    after("""
CHECK FOR:
  SPI mode with LSB_FIRST (0x08) flag set
    → If set, bits within each byte are reversed on the wire.
    → This would explain the wrapped gradient perfectly.

  dmesg showing fbtft init parameters
    → Look for any mention of buswidth, bpp, or txbuflen.

  If LSB_FIRST is NOT set, the bit reversal may be happening
  inside the fbtft driver's data conversion (e.g. RGB565 → RGB666
  expansion). Check dmesg for the actual pixel format being used.
    """)


def _reverse_bits(b):
    """Reverse bit order within a single byte."""
    result = 0
    for i in range(8):
        result = (result << 1) | (b & 1)
        b >>= 1
    return result


# Pre-build lookup table for speed
_BITREV = bytes(_reverse_bits(i) for i in range(256))
_BITREV_TABLE = _BITREV   # alias used by direct-SPI tests


def ti_bitrev_gradient():
    before("TI: BIT-REVERSED GRADIENT — compensate for potential bit reversal",
           """
Same red gradient as T6, but with all bits within each byte
reversed before writing to the framebuffer.

If the display pipeline reverses bits, this pre-reversal will
cancel it out and produce a SMOOTH gradient.

Top half: normal gradient (same as T6 — expect wrapped/broken)
Bottom half: bit-reversed gradient (expect smooth IF hypothesis is correct)
           """)

    half_h = FB_HEIGHT // 2
    buf = bytearray()

    for y in range(FB_HEIGHT):
        for x in range(FB_WIDTH):
            r = x * 255 // (FB_WIDTH - 1)
            rgb565 = ((r & 0xF8) << 8)  # red only
            lo = rgb565 & 0xFF
            hi = (rgb565 >> 8) & 0xFF

            if y < half_h:
                # Top half: normal (same as T6)
                buf.append(lo)
                buf.append(hi)
            else:
                # Bottom half: bit-reversed bytes
                buf.append(_BITREV[lo])
                buf.append(_BITREV[hi])

    with open(FB_PATH, 'r+b') as fb:
        fb.seek(0)
        fb.write(buf)

    after("""
TOP HALF BROKEN, BOTTOM HALF SMOOTH
  → CONFIRMED: bits are being reversed in the pipeline.
  → The fix is to pre-reverse bits, OR find the fbtft/SPI setting
    that's causing the reversal and disable it.

BOTH HALVES BROKEN (differently)
  → Not a simple bit-reversal. The issue is more complex.
    Bring both patterns back for analysis.

BOTH HALVES LOOK THE SAME
  → The reversal is not at the byte level. Could be at the
    16-bit word level or something else.

TOP HALF SMOOTH, BOTTOM HALF BROKEN
  → Our original code was correct all along and the wrapping
    seen in TF/TG was a visual misread. (Unlikely but possible.)
    """)


def tj_driver_info():
    before("TJ: DRIVER INFO — fbtft module and device parameters",
           """
Reads all available fbtft driver configuration from sysfs.
Looking for gamma tables, pixel format, and transformation settings.
           """)

    # Module parameters
    print("  --- fbtft module parameters ---")
    for path in sorted(glob.glob('/sys/module/fbtft/parameters/*')):
        name = os.path.basename(path)
        try:
            with open(path) as f:
                val = f.read().strip()
            print(f"  {name} = {val}")
        except (OSError, IOError) as e:
            print(f"  {name}: {e}")

    # fb_ili9486 module parameters
    print()
    print("  --- fb_ili9486 module parameters ---")
    for path in sorted(glob.glob('/sys/module/fb_ili9486/parameters/*')):
        name = os.path.basename(path)
        try:
            with open(path) as f:
                val = f.read().strip()
            print(f"  {name} = {val}")
        except (OSError, IOError) as e:
            print(f"  {name}: {e}")

    # Device attributes under fb1
    print()
    print("  --- /sys/class/graphics/fb1/ ---")
    for path in sorted(glob.glob('/sys/class/graphics/fb1/*')):
        name = os.path.basename(path)
        if os.path.isfile(path):
            try:
                with open(path) as f:
                    val = f.read().strip()
                # Truncate long values
                if len(val) > 200:
                    val = val[:200] + '...'
                print(f"  {name} = {val}")
            except (OSError, IOError):
                pass

    # The gamma curve specifically
    print()
    print("  --- Gamma curve ---")
    gamma_path = '/sys/class/graphics/fb1/device/gamma'
    if not os.path.exists(gamma_path):
        gamma_path = '/sys/bus/spi/devices/spi0.0/gamma'
    try:
        with open(gamma_path) as f:
            gamma = f.read().strip()
        print(f"  gamma = {gamma}")
    except (OSError, IOError):
        print("  (gamma file not found at expected paths)")
        # Search more broadly
        result = subprocess.run(['find', '/sys', '-name', 'gamma', '-path', '*fb*'],
                                capture_output=True, text=True, timeout=5)
        if result.stdout.strip():
            for p in result.stdout.strip().splitlines():
                try:
                    with open(p) as f:
                        print(f"  {p} = {f.read().strip()}")
                except:
                    pass
        else:
            print("  (no gamma files found under /sys/*fb*)")

    after("""
KEY THINGS TO LOOK FOR:

  gamma = <values>
    → fbtft writes these to the ILI9486's gamma registers (0xE0/0xE1).
    → A broken gamma curve could remap brightness non-monotonically.
    → Compare against the values in our init sequence.

  Any parameter mentioning: format, bpp, pixel, colmod, nonstd
    → Tells us what format conversion fbtft does before SPI transfer.

  buswidth = 8
    → Already confirmed. Panel uses 8-bit SPI.
    → But does fbtft send 2 or 3 bytes per pixel over SPI?
    """)


def tk_gamma_bypass():
    before("TK: GAMMA BYPASS — attempt to set linear gamma",
           """
Tries to set a linear (identity) gamma curve on the ILI9486 panel
via sysfs, then re-runs the red gradient test.

If the gradient becomes smooth, the gamma table was the problem.
           """)

    # Try writing identity gamma via sysfs
    gamma_paths = [
        '/sys/class/graphics/fb1/device/gamma',
        '/sys/bus/spi/devices/spi0.0/gamma',
    ]

    wrote_gamma = False
    for gamma_path in gamma_paths:
        if os.path.exists(gamma_path):
            # ILI9486 gamma registers are 15 values each (PGAMCTRL / NGAMCTRL)
            # Try a "neutral" gamma: all zeros (may not work, but worth trying)
            # Also try the documented default values
            identity = "00 04 08 0C 10 14 18 1C 20 24 28 2C 30 34 38"
            try:
                # First read current value
                with open(gamma_path) as f:
                    current = f.read().strip()
                print(f"  Current gamma: {current}")
                print(f"  Path: {gamma_path}")

                # Try to write (may need root)
                with open(gamma_path, 'w') as f:
                    f.write(identity)
                print(f"  Wrote identity gamma: {identity}")
                wrote_gamma = True

                # Read back
                with open(gamma_path) as f:
                    after_write = f.read().strip()
                print(f"  Readback: {after_write}")
                break
            except (OSError, IOError, PermissionError) as e:
                print(f"  Could not write gamma: {e}")
                print(f"  (may need: sudo chmod 666 {gamma_path})")

    if not wrote_gamma:
        print("  Could not find or write gamma sysfs file.")
        print("  Proceeding with gradient test using current gamma.")

    # Now run a gradient
    print()
    print("  Writing red gradient...")
    buf = bytearray()
    for y in range(FB_HEIGHT):
        for x in range(FB_WIDTH):
            r = x * 255 // (FB_WIDTH - 1)
            buf += _px(r, 0, 0)
    with open(FB_PATH, 'r+b') as fb:
        fb.seek(0)
        fb.write(buf)

    after("""
GRADIENT IS NOW SMOOTH
  → The fbtft gamma table was causing the wrapping.
  → Fix: set appropriate gamma in the dtoverlay config or module params.

GRADIENT IS STILL BROKEN (same as before)
  → Gamma is not the cause. The issue is in the pixel format conversion.

GRADIENT CHANGED BUT STILL NOT RIGHT
  → Gamma is involved but the identity values we used weren't correct.
  → Bring the results back for further tuning.
    """)


def tl_snoop_spi():
    before("TL: SNOOP — check fbtft's pixel format conversion",
           """
Checks how fbtft converts framebuffer pixels before SPI transfer.
This is a configuration/code analysis test, not a visual test.
           """)

    # Check what COLMOD the driver sets
    # We can look at the init sequence in the kernel module
    print("  --- Checking fbtft init sequence ---")
    result = subprocess.run(
        ['modinfo', 'fb_ili9486'],
        capture_output=True, text=True
    )
    print(f"  modinfo fb_ili9486:")
    for line in result.stdout.strip().splitlines():
        print(f"    {line}")

    # Check fbtft's write function to understand format conversion
    # The key question: does fbtft convert RGB565 to RGB666 before sending?
    print()
    print("  --- Checking nonstd interpretation ---")
    print(f"  fbset reports: nonstd 1")
    print(f"  In fbtft, nonstd=1 typically means:")
    print(f"    - Framebuffer stores RGB565 (16-bit)")
    print(f"    - Driver converts to RGB666 (18-bit, 3 bytes/pixel) for SPI")
    print(f"    - OR driver sends RGB565 as-is (2 bytes/pixel) over SPI")
    print()

    # Check if there's a txbuflen or similar
    print("  --- txbuf info ---")
    for attr in ['device/txbuflen', 'device/fps', 'device/rotate',
                 'device/buswidth', 'device/debug']:
        path = f'/sys/class/graphics/fb1/{attr}'
        try:
            with open(path) as f:
                val = f.read().strip()
            print(f"  {attr} = {val}")
        except (OSError, IOError):
            pass

    # THE CRITICAL CHECK: Look at fbtft source for write_vmem
    # The function fbtft_write_vmem16_bus8 does the actual conversion
    print()
    print("  --- Checking for fbtft source (write_vmem function) ---")
    # Check if source is available on the system
    src_paths = [
        '/usr/src/linux-source-*/drivers/staging/fbtft/fbtft-bus.c',
        '/lib/modules/*/build/drivers/staging/fbtft/fbtft-bus.c',
    ]
    found_src = False
    for pattern in src_paths:
        for path in glob.glob(pattern):
            found_src = True
            print(f"  Found: {path}")
            # Try to grep for the write function
            result = subprocess.run(
                ['grep', '-n', r'write_vmem\|swab\|swap\|RGB565\|RGB666\|nonstd',
                 path],
                capture_output=True, text=True
            )
            if result.stdout:
                for line in result.stdout.strip().splitlines()[:20]:
                    print(f"    {line}")

    if not found_src:
        print("  Kernel source not installed on device.")
        print("  Checking online: the fbtft_write_vmem16_bus8 function in")
        print("  drivers/staging/fbtft/fbtft-bus.c is what converts pixels.")
        print()
        print("  Key question: does it call swab16() or otherwise byte-swap")
        print("  the RGB565 data before sending? And does it expand to 3 bytes?")

    after("""
This test produces diagnostic OUTPUT, not a visual result.
Share the full terminal output with Tim for analysis.

THE KEY QUESTION this test tries to answer:
  When fbtft reads our RGB565 pixel from the framebuffer,
  what bytes does it actually send over SPI to the panel?

If it sends 2 bytes (RGB565): the panel must be in COLMOD=0x55
If it sends 3 bytes (RGB666): the panel must be in COLMOD=0x66
  AND the RGB565→RGB666 conversion must be correct.

A broken conversion (e.g. sending the RGB565 bytes as-is in a
3-byte format without proper bit shifting) would produce exactly
the kind of brightness wrapping we're seeing.
    """)


def t6_gradient():
    before("T6: GRADIENT — smooth red sweep left to right",
           f"""
Writes a red gradient row by row:
  x = 0   → black   (r=0)
  x = {FB_WIDTH - 1} → full red (r=255)

Every row is identical. If the gradient is smooth, the
framebuffer→panel mapping is correct and banding-free.
           """)
    buf = bytearray()
    for y in range(FB_HEIGHT):
        for x in range(FB_WIDTH):
            r = x * 255 // (FB_WIDTH - 1)
            buf += _px(r, 0, 0)
    with open(FB_PATH, 'r+b') as fb:
        fb.seek(0)
        fb.write(buf)
    after("""
SMOOTH gradient (black on one edge → red on the other)
  → Framebuffer maps cleanly to the display. No banding.

REPEATING gradient or DIAGONAL BANDS
  → Scan-line mismatch between framebuffer and panel.
  → Try a different rotate= value in the dtoverlay.
    """)


# ── Shared direct-SPI helpers ──────────────────────────────────────────────────

_spi_panel = None


def _get_spi():
    """Get or create a direct SPI connection to the panel."""
    global _spi_panel
    if _spi_panel is not None:
        return _spi_panel

    try:
        import spidev as _spidev
        import lgpio as _lgpio
    except ImportError:
        return None

    spi = _spidev.SpiDev()
    spi.open(0, 0)
    spi.max_speed_hz = 16_000_000
    spi.mode = 0

    gpio = _lgpio.gpiochip_open(0)
    _lgpio.gpio_claim_output(gpio, 24)   # DC
    _lgpio.gpio_claim_output(gpio, 25)   # RST

    _spi_panel = (spi, gpio)
    return _spi_panel


def _spi_cmd(c, *data):
    """Send command byte (DC low), then optional data bytes (DC high)."""
    spi, gpio = _get_spi()
    import lgpio as _lgpio
    _lgpio.gpio_write(gpio, 24, 0)
    spi.xfer2([c])
    if data:
        _lgpio.gpio_write(gpio, 24, 1)
        spi.xfer2(list(data))


def _spi_data(buf):
    """Send raw data bytes with DC high."""
    spi, gpio = _get_spi()
    import lgpio as _lgpio
    _lgpio.gpio_write(gpio, 24, 1)
    buf = bytes(buf)
    for i in range(0, len(buf), 4096):
        spi.writebytes2(buf[i:i+4096])


def _spi_reset():
    """Hardware reset the panel."""
    _, gpio = _get_spi()
    import lgpio as _lgpio
    import time
    _lgpio.gpio_write(gpio, 25, 1)
    time.sleep(0.01)
    _lgpio.gpio_write(gpio, 25, 0)
    time.sleep(0.10)
    _lgpio.gpio_write(gpio, 25, 1)
    time.sleep(0.12)


def _spi_init_panel(colmod=0x66, gamma=True):
    """Full panel init via direct SPI. If gamma=False, skip gamma registers."""
    import time

    _spi_reset()
    _spi_cmd(0xB0, 0x00)          # Interface Mode Control
    _spi_cmd(0x11)                 # Sleep Out
    time.sleep(0.25)
    _spi_cmd(0x3A, colmod)         # COLMOD
    _spi_cmd(0x36, 0x48)           # MADCTL: MX + BGR

    if gamma:
        # Standard gamma from kernel fb_ili9486 driver ("PiScreen" values)
        _spi_cmd(0xE0, 0x0F,0x1F,0x1C,0x0C,0x0F,0x08,0x48,0x98,
                       0x37,0x0A,0x13,0x04,0x11,0x0D,0x00)
        _spi_cmd(0xE1, 0x0F,0x32,0x2E,0x0B,0x0D,0x05,0x47,0x75,
                       0x37,0x06,0x10,0x03,0x24,0x20,0x00)
        _spi_cmd(0xE2, 0x0F,0x32,0x2E,0x0B,0x0D,0x05,0x47,0x75,
                       0x37,0x06,0x10,0x03,0x24,0x20,0x00)
    # else: skip gamma entirely — use panel's power-on defaults

    _spi_cmd(0xC2, 0x44)          # Power Control 3
    _spi_cmd(0xC5, 0x00,0x00,0x00,0x00)  # VCOM
    _spi_cmd(0x11)                 # Sleep Out (again)
    _spi_cmd(0x29)                 # Display On


def _spi_send_gradient_rgb666():
    """Send a red gradient as RGB666 (3 bytes/pixel), full screen 320x480."""
    _spi_cmd(0x2A, 0x00,0x00, 0x01,0x3F)  # cols 0-319
    _spi_cmd(0x2B, 0x00,0x00, 0x01,0xDF)  # rows 0-479
    _spi_cmd(0x2C)                          # Memory Write

    buf = bytearray()
    for y in range(480):
        for col in range(320):
            r = (col * 252 // 319) & 0xFC
            buf.extend([r, 0x00, 0x00])
    _spi_data(buf)


def tm_direct_spi_gradient():
    before("TM: DIRECT SPI — RGB666 gradient bypassing fbtft",
           """
This test bypasses the framebuffer entirely and talks directly to the
ILI9486 panel via SPI, sending pixel data as RGB666 (3 bytes/pixel).

If this produces a SMOOTH gradient, the ILI9486L hypothesis is confirmed:
the panel requires RGB666 and the fbtft driver is wrongly sending RGB565.

NOTE: This will take over the display from fbtft temporarily.
After this test, fbtft may need a service restart to resume.
           """)

    try:
        import spidev as _spidev
        import lgpio as _lgpio
    except ImportError:
        print("  spidev/lgpio not available — skipping direct SPI test")
        after("Could not run — spidev/lgpio not available.")
        return

    PIN_DC  = 24
    PIN_RST = 25

    spi = _spidev.SpiDev()
    spi.open(0, 0)
    spi.max_speed_hz = 16_000_000
    spi.mode = 0

    gpio = _lgpio.gpiochip_open(0)
    _lgpio.gpio_claim_output(gpio, PIN_DC)

    def cmd(c, *data):
        _lgpio.gpio_write(gpio, PIN_DC, 0)
        spi.xfer2([c])
        if data:
            _lgpio.gpio_write(gpio, PIN_DC, 1)
            spi.xfer2(list(data))

    def send_data(buf):
        _lgpio.gpio_write(gpio, PIN_DC, 1)
        buf = bytes(buf)
        for i in range(0, len(buf), 4096):
            spi.writebytes2(buf[i:i+4096])

    # Set COLMOD to 0x66 (RGB666, 18-bit, 3 bytes per pixel)
    cmd(0x3A, 0x66)

    # Set MADCTL (same as fbtft uses)
    # fbtft's set_var sends MADCTL based on rotation + BGR
    # For rotate=0 with BGR: MADCTL = 0x08 | 0x40 = 0x48 (MX + BGR)
    # But fbtft may set this differently. Keep default from init.
    # Actually just set it explicitly:
    cmd(0x36, 0x48)

    # Set window: full screen 320x480
    cmd(0x2A, 0x00, 0x00, 0x01, 0x3F)  # columns 0-319
    cmd(0x2B, 0x00, 0x00, 0x01, 0xDF)  # rows 0-479

    # Memory write
    cmd(0x2C)

    # Build gradient: red sweep across 320 columns, 3 bytes per pixel
    buf = bytearray()
    for y in range(480):
        for x in range(320):
            r = x * 252 // 319  # scale to 0-252, keeping top 6 bits
            r = r & 0xFC        # mask to 6-bit aligned
            buf.extend([r, 0x00, 0x00])  # R, G, B in RGB666

    print(f"  Sending {len(buf)} bytes ({len(buf) // 3} pixels × 3 bpp)")
    send_data(buf)

    # Clean up SPI (but leave display showing the result)
    spi.close()
    _lgpio.gpiochip_close(gpio)

    after("""
SMOOTH RED GRADIENT (dark left → bright right)
  → CONFIRMED: The panel is ILI9486L and requires RGB666 (3 bytes/pixel).
  → The fbtft fb_ili9486 driver is sending RGB565 (2 bytes/pixel) which
    the panel misinterprets, causing the wrapped gradient.

STILL BROKEN
  → The hypothesis is wrong. Something else is going on.

NOTE: After this test, fbtft will have lost control of the COLMD setting.
Run `sudo systemctl restart receipt-printer` or reboot to restore fbtft.
    """)


def tn_no_gamma():
    before("TN: NO GAMMA — full reinit without gamma registers, then gradient",
           """
Does a HARDWARE RESET of the panel, full reinit with COLMOD=0x66,
but SKIPS the gamma register writes (0xE0, 0xE1, 0xE2).

The panel will use its power-on default gamma curve instead of the
"PiScreen" values from the kernel driver.

Then sends a red gradient via direct SPI as RGB666.

NOTE: This completely takes over from fbtft. Reboot to restore.
           """)

    if _get_spi() is None:
        print("  spidev/lgpio not available — skipping")
        after("Could not run.")
        return

    print("  Hardware reset + full init WITHOUT gamma...")
    _spi_init_panel(colmod=0x66, gamma=False)

    print("  Sending red gradient (RGB666, 3 bpp)...")
    _spi_send_gradient_rgb666()

    after("""
SMOOTH GRADIENT
  → CONFIRMED: The "PiScreen" gamma values are wrong for this panel.
  → Fix: either skip gamma in our init, or find correct values for
    the Waveshare panel.

STILL WRAPPED/BROKEN (same as before)
  → Gamma is NOT the cause. The panel's default gamma has the same
    problem, or the issue is elsewhere (VCOM, power control, etc).
  → Proceed to Test O.

DIFFERENT KIND OF BROKEN (different wrap pattern, different colors)
  → Gamma is involved but the default isn't right either.
  → We'll need to find correct gamma values for this specific panel.
    """)


def to_identity_gamma():
    before("TO: WAVESHARE GAMMA — reinit with Waveshare's own gamma values",
           """
Does a HARDWARE RESET, full reinit with COLMOD=0x66, using gamma
values from Waveshare's own example code for this display instead
of the kernel driver's "PiScreen" values.

Then sends a red gradient via direct SPI.
           """)

    if _get_spi() is None:
        print("  spidev/lgpio not available — skipping")
        after("Could not run.")
        return

    import time
    print("  Hardware reset + full init with Waveshare gamma...")
    _spi_reset()

    _spi_cmd(0xB0, 0x00)
    _spi_cmd(0x11)
    time.sleep(0.25)
    _spi_cmd(0x3A, 0x66)     # COLMOD = RGB666
    _spi_cmd(0x36, 0x48)     # MADCTL: MX + BGR

    # Waveshare example gamma values (from their LCD-show scripts)
    # These differ from the kernel driver's PiScreen values
    _spi_cmd(0xE0, 0x00,0x03,0x09,0x08,0x16,0x0A,0x3F,0x78,
                   0x4C,0x09,0x0A,0x08,0x16,0x1A,0x0F)
    _spi_cmd(0xE1, 0x00,0x16,0x19,0x03,0x0F,0x05,0x32,0x45,
                   0x46,0x04,0x0E,0x0D,0x35,0x37,0x0F)

    # Zero out Digital Gamma 2 (0xE2) — not all displays use it
    _spi_cmd(0xE2, 0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,
                   0x00,0x00,0x00,0x00,0x00,0x00,0x00)

    _spi_cmd(0xC0, 0x17,0x15)        # Power Control 1 (Waveshare values)
    _spi_cmd(0xC1, 0x41)             # Power Control 2
    _spi_cmd(0xC5, 0x00,0x12,0x80)   # VCOM (Waveshare values)
    _spi_cmd(0x11)
    _spi_cmd(0x29)

    print("  Sending red gradient (RGB666, 3 bpp)...")
    _spi_send_gradient_rgb666()

    after("""
SMOOTH GRADIENT
  → The Waveshare gamma values work. Use these in our init sequence.

STILL WRAPPED/BROKEN (same pattern)
  → Gamma alone cannot fix this. The issue may be more fundamental.
    Report back for further analysis.

BETTER BUT NOT PERFECT
  → We're on the right track. The gamma values need further tuning.
    """)


def tp_minimal_init():
    before("TP: MINIMAL INIT — bare minimum init, then gradient",
           """
Hardware reset, then ONLY: Sleep Out, COLMOD=0x66, Display On.
No gamma, no power control, no VCOM, no MADCTL.

This uses the panel's absolute factory defaults for everything
except pixel format. The gradient direction may be different.
           """)

    if _get_spi() is None:
        print("  spidev/lgpio not available — skipping")
        after("Could not run.")
        return

    import time
    print("  Hardware reset + MINIMAL init...")
    _spi_reset()
    _spi_cmd(0x11)          # Sleep Out
    time.sleep(0.25)
    _spi_cmd(0x3A, 0x66)    # COLMOD = RGB666
    _spi_cmd(0x29)          # Display On
    time.sleep(0.05)

    print("  Sending red gradient (RGB666, 3 bpp)...")
    _spi_send_gradient_rgb666()

    after("""
SMOOTH GRADIENT (possibly mirrored/rotated)
  → The panel's factory defaults work. One of our register writes
    (gamma, power, VCOM, or MADCTL) is causing the problem.
  → Next step: add registers back one at a time to find the culprit.

STILL WRAPPED/BROKEN
  → The panel itself has this behavior out of the box.
  → This would suggest a hardware issue, or that COLMOD=0x66 doesn't
    actually select RGB666 on this panel variant.
  → Try COLMOD=0x55 in this minimal init to test RGB565.
    """)


def tq_rgb565_minimal():
    before("TQ: RGB565 MINIMAL — bare minimum init with COLMOD=0x55, 2 bpp",
           """
Hardware reset, then ONLY: Sleep Out, COLMOD=0x55, Display On.
Sends gradient as RGB565 big-endian (2 bytes per pixel).

If this produces a smooth gradient, the panel wants RGB565 after all.
           """)

    if _get_spi() is None:
        print("  spidev/lgpio not available — skipping")
        after("Could not run.")
        return

    import time
    print("  Hardware reset + MINIMAL init with COLMOD=0x55...")
    _spi_reset()
    _spi_cmd(0x11)          # Sleep Out
    time.sleep(0.25)
    _spi_cmd(0x3A, 0x55)    # COLMOD = RGB565
    _spi_cmd(0x29)          # Display On
    time.sleep(0.05)

    # Set window: full screen
    _spi_cmd(0x2A, 0x00,0x00, 0x01,0x3F)  # cols 0-319
    _spi_cmd(0x2B, 0x00,0x00, 0x01,0xDF)  # rows 0-479
    _spi_cmd(0x2C)

    # Build gradient as RGB565 big-endian
    buf = bytearray()
    for y in range(480):
        for col in range(320):
            r5 = col * 31 // 319
            rgb565 = r5 << 11   # red only
            buf += struct.pack('>H', rgb565)  # big-endian for SPI

    print(f"  Sending {len(buf)} bytes ({len(buf) // 2} pixels × 2 bpp)")
    _spi_data(buf)

    after("""
SMOOTH GRADIENT (colour may be blue without MADCTL BGR bit)
  → Panel accepts RGB565 over SPI! The format was right all along.
  → The RGB666 (3 bpp) tests were failing because of format mismatch.

STILL WRAPPED
  → Panel wraps regardless of pixel format. Proceed to Test R.
    """)


def tr_transfer_function():
    before("TR: TRANSFER FUNCTION — 16 discrete brightness blocks",
           """
Minimal init (COLMOD=0x66), then displays a 4×4 grid of blocks.
Each block is a solid fill with a specific red value.

The blocks are arranged left→right, top→bottom in order of
INCREASING red byte value. Number them 0–15 from top-left to
bottom-right.

For each block, note the PERCEIVED BRIGHTNESS on a scale of
0 (black) to 10 (brightest red you see).

This maps the exact input→brightness transfer function.
           """)

    if _get_spi() is None:
        print("  spidev/lgpio not available — skipping")
        after("Could not run.")
        return

    import time
    print("  Hardware reset + minimal init...")
    _spi_reset()
    _spi_cmd(0x11)
    time.sleep(0.25)
    _spi_cmd(0x3A, 0x66)    # RGB666
    _spi_cmd(0x29)
    time.sleep(0.05)

    # 16 red values spanning 0-252 (full 6-bit range for RGB666)
    red_values = [
        0x00, 0x10, 0x20, 0x30,
        0x40, 0x50, 0x60, 0x70,
        0x80, 0x90, 0xA0, 0xB0,
        0xC0, 0xD0, 0xE0, 0xFC,
    ]

    # Grid: 4 columns × 4 rows
    # Each block: 80 × 120 pixels (4×80=320, 4×120=480)
    block_w = 80
    block_h = 120
    cols_grid = 4

    print(f"\n  Block  Red    Hex    Grid position")
    print(f"  {'─' * 45}")
    for i, rv in enumerate(red_values):
        gc = i % cols_grid
        gr = i // cols_grid
        print(f"  {i:5d}  {rv:3d}  0x{rv:02X}    col {gc} row {gr}")

    # Build full framebuffer
    _spi_cmd(0x2A, 0x00,0x00, 0x01,0x3F)
    _spi_cmd(0x2B, 0x00,0x00, 0x01,0xDF)
    _spi_cmd(0x2C)

    buf = bytearray()
    for y in range(480):
        for x in range(320):
            grid_col = x // block_w
            grid_row = y // block_h
            block_idx = grid_row * cols_grid + grid_col
            if block_idx < len(red_values):
                rv = red_values[block_idx]
            else:
                rv = 0
            buf.extend([rv, 0x00, 0x00])

    _spi_data(buf)

    after("""
For each block (0–15), rate the brightness from 0 (black) to 10
(brightest). Write them down like:

  Block 0 (0x00): _
  Block 1 (0x10): _
  Block 2 (0x20): _
  ... etc ...
  Block 15 (0xFC): _

KEY PATTERNS TO LOOK FOR:

MONOTONICALLY INCREASING (each block brighter than the last)
  → The solid blocks work fine. The gradient issue is about TRANSITIONS
    between adjacent pixels, not about absolute values. This would
    point to some kind of spatial dithering or pixel interaction issue.

NON-MONOTONIC (brightness goes up and down)
  → Note exactly where brightness peaks and dips. This maps the
    broken transfer function directly.

The results will tell us whether the issue is in VALUE INTERPRETATION
(each pixel's brightness is wrong) or SPATIAL INTERACTION (pixels
affect each other when values vary).
    """)


def ts_bitrev_direct():
    before("TS: BIT-REVERSED DIRECT SPI — gradient with reversed pixel bits",
           """
Hardware reset, minimal init (COLMOD=0x66), then sends a red gradient
where every PIXEL DATA byte has its bits reversed before SPI transfer.

Commands and their parameters are sent NORMALLY (not reversed).

Top half: normal pixel bytes (same as TP — expect wrapped)
Bottom half: bit-reversed pixel bytes (expect smooth IF bit order is wrong)
           """)

    if _get_spi() is None:
        print("  spidev/lgpio not available — skipping")
        after("Could not run.")
        return

    import time
    print("  Hardware reset + minimal init...")
    _spi_reset()
    _spi_cmd(0x11)
    time.sleep(0.25)
    _spi_cmd(0x3A, 0x66)
    _spi_cmd(0x29)
    time.sleep(0.05)

    _spi_cmd(0x2A, 0x00,0x00, 0x01,0x3F)
    _spi_cmd(0x2B, 0x00,0x00, 0x01,0xDF)
    _spi_cmd(0x2C)

    half_h = 240  # 480 / 2

    buf = bytearray()
    for y in range(480):
        for col in range(320):
            r = (col * 252 // 319) & 0xFC
            if y < half_h:
                # Top half: normal bytes
                buf.extend([r, 0x00, 0x00])
            else:
                # Bottom half: bit-reversed bytes
                buf.extend([_BITREV_TABLE[r], 0x00, 0x00])

    print(f"  Sending {len(buf)} bytes...")
    print(f"  Top half: normal, Bottom half: bit-reversed")
    _spi_data(buf)

    after("""
TOP BROKEN, BOTTOM SMOOTH
  → The panel expects LSB-first bit order for pixel data!
  → Fix: reverse bits in every pixel byte before sending.
  → OR: configure SPI for LSB-first mode.

BOTH BROKEN (same pattern)
  → Simple full-byte bit reversal isn't the answer. Try Test T.

TOP BROKEN, BOTTOM DIFFERENTLY BROKEN
  → Partial bit reordering. Report both patterns.

BOTH SMOOTH (unlikely)
  → Something changed between tests. Try again.
    """)


def tt_spi_modes():
    before("TT: SPI MODES — test all 4 SPI clock modes",
           """
Tests SPI modes 0, 1, 2, and 3 in sequence. For each mode:
  - Full hardware reset and minimal init
  - Sends a simple test pattern: left half red (0xFC,0,0),
    right half green (0,0xFC,0)

Note which mode(s) show the correct colors and clean edges.
Currently using mode 0.
           """)

    if _get_spi() is None:
        print("  spidev/lgpio not available — skipping")
        after("Could not run.")
        return

    spi, gpio = _get_spi()
    import time

    for mode in [0, 1, 2, 3]:
        wait(f"TT sub-test: SPI mode {mode}\n"
             f"    Left half should be red, right half green.\n"
             f"    Note: does the display show anything? Correct colors?")

        spi.mode = mode

        _spi_reset()
        _spi_cmd(0x11)
        time.sleep(0.25)
        _spi_cmd(0x3A, 0x66)
        _spi_cmd(0x36, 0x48)   # MADCTL for correct color mapping
        _spi_cmd(0x29)
        time.sleep(0.05)

        _spi_cmd(0x2A, 0x00,0x00, 0x01,0x3F)
        _spi_cmd(0x2B, 0x00,0x00, 0x01,0xDF)
        _spi_cmd(0x2C)

        half_w = 160  # 320 / 2
        buf = bytearray()
        for y in range(480):
            for x in range(320):
                if x < half_w:
                    buf.extend([0xFC, 0x00, 0x00])  # red
                else:
                    buf.extend([0x00, 0xFC, 0x00])  # green

        _spi_data(buf)

    # Restore mode 0
    spi.mode = 0

    after("""
For each SPI mode, note:
  1. Did the display show anything at all?
  2. Were the colors correct (red left, green right)?
  3. Was the boundary between red and green sharp?

If modes 0 and 3 both work (common), or modes 1 and 2 both work,
that's normal — those pairs sample on the same clock edge.

If ONLY a non-zero mode works, that changes our SPI configuration.
    """)


def tu_transfer_bitrev():
    before("TU: TRANSFER FUNCTION (bit-reversed) — 16 blocks, reversed bits",
           """
Same as Test TR, but all pixel data bytes are bit-reversed before sending.
If the SPI path reverses bits, this pre-reversal should produce
monotonically increasing brightness blocks.

Rate each block 0-15 on the same brightness scale as TR.
           """)

    if _get_spi() is None:
        print("  spidev/lgpio not available — skipping")
        after("Could not run.")
        return

    import time
    print("  Hardware reset + minimal init...")
    _spi_reset()
    _spi_cmd(0x11)
    time.sleep(0.25)
    _spi_cmd(0x3A, 0x66)
    _spi_cmd(0x36, 0x48)
    _spi_cmd(0x29)
    time.sleep(0.05)

    red_values = [
        0x00, 0x10, 0x20, 0x30,
        0x40, 0x50, 0x60, 0x70,
        0x80, 0x90, 0xA0, 0xB0,
        0xC0, 0xD0, 0xE0, 0xFC,
    ]

    block_w = 80
    block_h = 120

    print(f"\n  Block  Red    Hex    Reversed  RevHex")
    print(f"  {'─' * 50}")
    for i, rv in enumerate(red_values):
        rev = _BITREV_TABLE[rv]
        print(f"  {i:5d}  {rv:3d}  0x{rv:02X}    {rev:3d}     0x{rev:02X}")

    _spi_cmd(0x2A, 0x00,0x00, 0x01,0x3F)
    _spi_cmd(0x2B, 0x00,0x00, 0x01,0xDF)
    _spi_cmd(0x2C)

    buf = bytearray()
    for y in range(480):
        for x in range(320):
            grid_col = x // block_w
            grid_row = y // block_h
            block_idx = grid_row * 4 + grid_col
            if block_idx < len(red_values):
                rv = red_values[block_idx]
            else:
                rv = 0
            # BIT-REVERSE the red value before sending
            buf.extend([_BITREV_TABLE[rv], 0x00, 0x00])

    _spi_data(buf)

    after("""
Rate each block's brightness 0-15, same as TR:

  Block 0: _    Block 4: _    Block 8:  _    Block 12: _
  Block 1: _    Block 5: _    Block 9:  _    Block 13: _
  Block 2: _    Block 6: _    Block 10: _    Block 14: _
  Block 3: _    Block 7: _    Block 11: _    Block 15: _

MONOTONICALLY INCREASING (0,1,2,3,4,5,6,...,15)
  → CONFIRMED: The SPI bus sends LSB-first but panel expects MSB-first.
  → Fix: bit-reverse all pixel bytes, or set SPI to LSB_FIRST mode.

STILL NON-MONOTONIC
  → The reordering isn't simple bit reversal. Report the pattern.
    """)


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


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    # if not os.path.exists(FB_PATH):
    #     print(f"ERROR: {FB_PATH} not found.")
    #     print("Make sure the fbtft dtoverlay is active and the Pi has rebooted.")
    #     sys.exit(1)

    # print("=" * W)
    # print("  ILI9486 Framebuffer Diagnostic")
    # print(f"  Device : {FB_PATH}")
    # print(f"  Assumed: {FB_WIDTH} × {FB_HEIGHT}, RGB565")
    # print("=" * W)
    # print("Follow the on-screen prompts.\n")

    try:
        if '--gamma-diag' in sys.argv:
            tn_no_gamma()
            to_identity_gamma()
            tp_minimal_init()
            tq_rgb565_minimal()
            tr_transfer_function()
            ts_bitrev_direct()
            tt_spi_modes()
            tu_transfer_bitrev()
            tv_padded_gradient()
        elif '--gradient-diag' in sys.argv:
            # ta_fbset()
            # tb_step_wedge()
            # tc_round_trip()
            # td_solid_midred()
            # te_byte_order()
            # tf_r5_wedge()
            # tg_g6_wedge()
            # th_spi_config()
            # ti_bitrev_gradient()
            # tj_driver_info()
            # tk_gamma_bypass()
            # tl_snoop_spi()
            # t6_gradient()
            tm_direct_spi_gradient()
        else:
            # t1_alive()
            # t2_row_zero()
            # t3_col_zero()
            # t4_origin()
            # t5_midpoint()
            # ta_fbset()
            # tb_step_wedge()
            # tc_round_trip()
            # td_solid_midred()
            # te_byte_order()
            # tf_r5_wedge()
            # tg_g6_wedge()
            # th_spi_config()
            # ti_bitrev_gradient()
            # tj_driver_info()
            # tk_gamma_bypass()
            # tl_snoop_spi()
            # t6_gradient()
            tm_direct_spi_gradient()
        print("\n=== All tests complete ===")
    except KeyboardInterrupt:
        print("\nAborted.")


if __name__ == '__main__':
    main()
