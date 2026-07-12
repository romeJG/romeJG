"""
Prepare a portrait photo for clean ASCII conversion:
  1. remove the background (rembg) so the subject is isolated
  2. crop tightly to the subject's bounding box so empty sky/background
     doesn't waste rows of the fixed-size ascii grid
  3. boost LOCAL contrast (CLAHE) so a flatly-lit face gains highlights and
     shadows -- this is what turns a dark blob into a recognizable face
  4. composite the subject onto pure white so the background reads as blank
     (white -> spaces in the ascii ramp), then pad back to a square canvas
     so the downstream fixed-aspect character grid doesn't stretch it

Output: source-prepped.png (grayscale), consumed by make_ascii_svg.py.
Run once whenever the source photo changes; the ascii SVG itself is static.

    python scripts/prep_photo.py <input.jpg> [output.png]
"""
import os
import sys

import cv2
import numpy as np
from PIL import Image
from rembg import remove

HERE = os.path.dirname(os.path.abspath(__file__))
INP = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "..", "source-photo.jpg")
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "..", "source-prepped.png")

CROP_MARGIN = 0.06  # extra padding around the subject's bounding box, as a fraction of its size

# 1. cut out the subject
cut = remove(Image.open(INP).convert("RGBA"))
rgb = np.array(cut.convert("RGB"))
alpha = np.array(cut.split()[-1])                 # 0 = background

# 2. crop tightly to where the subject actually is
ys, xs = np.where(alpha > 12)
if len(xs) and len(ys):
    x0, x1 = int(xs.min()), int(xs.max())
    y0, y1 = int(ys.min()), int(ys.max())
    mx = int((x1 - x0) * CROP_MARGIN)
    my = int((y1 - y0) * CROP_MARGIN)
    x0 = max(0, x0 - mx)
    x1 = min(alpha.shape[1] - 1, x1 + mx)
    y0 = max(0, y0 - my)
    y1 = min(alpha.shape[0] - 1, y1 + my)
    rgb = rgb[y0:y1 + 1, x0:x1 + 1]
    alpha = alpha[y0:y1 + 1, x0:x1 + 1]

# 3. local-contrast the luminance (CLAHE)
gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
clahe = cv2.createCLAHE(clipLimit=3.4, tileGridSize=(8, 8))
gray = clahe.apply(gray)

# a touch of global lift so the face sits in the sparse end of the ramp
gray = cv2.convertScaleAbs(gray, alpha=1.15, beta=14)

# 4. paste onto white using the alpha mask (feathered a hair to avoid a halo)
mask = (alpha.astype(np.float32) / 255.0)
mask = cv2.GaussianBlur(mask, (0, 0), 1.0)
out = gray.astype(np.float32) * mask + 255.0 * (1.0 - mask)

# 5. pad back to a square canvas (centered) so the fixed-aspect ascii grid
# (100 cols x 53 rows at 8x15px cells) doesn't stretch the cropped subject
h, w = out.shape
side = max(h, w)
canvas = np.full((side, side), 255.0, dtype=np.float32)
top, left = (side - h) // 2, (side - w) // 2
canvas[top:top + h, left:left + w] = out
out = np.clip(canvas, 0, 255).astype(np.uint8)

Image.fromarray(out, mode="L").save(OUT)
print("wrote", OUT, out.shape)
