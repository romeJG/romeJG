"""Crop source-prepped.png to the subject's bounding box, expanded to a square.

Usage: crop_subject.py <in.png> <out.png> [top_fraction]
top_fraction: keep only the top fraction of the subject bbox (e.g. 0.62 for
upper body) before squaring. Default 1.0 (full subject).
"""
import sys
import numpy as np
from PIL import Image

inp, out = sys.argv[1], sys.argv[2]
frac = float(sys.argv[3]) if len(sys.argv) > 3 else 1.0

im = Image.open(inp).convert("L")
a = np.array(im)
ys, xs = np.where(a < 245)  # non-white = subject
y0, y1, x0, x1 = ys.min(), ys.max(), xs.min(), xs.max()
y1 = y0 + int((y1 - y0) * frac)

# pad 3%, then expand the shorter side to make it square
h, w = y1 - y0, x1 - x0
pad = int(max(h, w) * 0.03)
y0, y1, x0, x1 = y0 - pad, y1 + pad, x0 - pad, x1 + pad
h, w = y1 - y0, x1 - x0
if h > w:
    cx = (x0 + x1) // 2
    x0, x1 = cx - h // 2, cx + h // 2
else:
    cy = (y0 + y1) // 2
    y0, y1 = cy - w // 2, cy + w // 2

side = max(y1 - y0, x1 - x0)
canvas = Image.new("L", (side, side), 255)
sx0, sy0 = max(0, x0), max(0, y0)
sx1, sy1 = min(a.shape[1], x1), min(a.shape[0], y1)
region = im.crop((sx0, sy0, sx1, sy1))
canvas.paste(region, (sx0 - x0, sy0 - y0))
canvas.save(out)
print("bbox", (x0, y0, x1, y1), "->", canvas.size)
