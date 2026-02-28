import numpy as np
from PIL import Image

DISPLAY_WIDTH = 480
DISPLAY_HEIGHT = 320

def write_to_display(img):
    """Rotate and write a landscape PIL image to the portrait framebuffer"""
    rotated = img.transpose(Image.Transpose.ROTATE_90)
    pixels = np.frombuffer(rotated.tobytes(), dtype=np.uint8)
    r = pixels[0::3].astype(np.uint16)
    g = pixels[1::3].astype(np.uint16)
    b = pixels[2::3].astype(np.uint16)
    rgb565_data = ((b & 0xF8) << 8) | ((g & 0xFC) << 3) | (r >> 3)
    with open('/dev/fb1', 'wb') as fb:
        fb.write(rgb565_data.astype(np.uint16).tobytes())