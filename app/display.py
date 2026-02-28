from PIL import Image, ImageDraw, ImageFont
import numpy as np

DISPLAY_WIDTH = 480
DISPLAY_HEIGHT = 320

def write_to_display(img):
    """Rotate and write a landscape PIL image to the portrait framebuffer"""
    rotated = img.rotate(90, expand=True)
    pixels = np.frombuffer(rotated.tobytes(), dtype=np.uint8)
    r = pixels[0::3].astype(np.uint16)
    g = pixels[1::3].astype(np.uint16)
    b = pixels[2::3].astype(np.uint16)
    rgb565_data = ((b & 0xF8) << 8) | ((g & 0xFC) << 3) | (r >> 3)
    with open('/dev/fb1', 'wb') as fb:
        fb.write(rgb565_data.astype(np.uint16).tobytes())

# Everything below here thinks in landscape - bliss
img = Image.new('RGB', (DISPLAY_WIDTH, DISPLAY_HEIGHT), color=(0, 0, 0))
draw = ImageDraw.Draw(img)

font = ImageFont.truetype("/usr/share/fonts/truetype/freefont/FreeSansBold.ttf", 24)

draw.rectangle([0, 0, 100, 60], fill=(255, 0, 0))
draw.rectangle([380, 260, 480, 320], fill=(0, 255, 0))
draw.text((10, 10), "TOP LEFT", font=font, fill=(255, 255, 255))
draw.text((350, 270), "BOT RIGHT", font=font, fill=(255, 255, 255))

write_to_display(img)