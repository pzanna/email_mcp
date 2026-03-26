#!/usr/bin/env python3
"""Generate a 512x512 envelope icon for the MCPB bundle."""

from PIL import Image, ImageDraw
import os

SIZE = 512
MARGIN = 60
BG_COLOR = (37, 99, 235)       # Blue-600
ENVELOPE_COLOR = (255, 255, 255)
FLAP_COLOR = (219, 234, 254)   # Blue-100

img = Image.new("RGBA", (SIZE, SIZE), BG_COLOR)
draw = ImageDraw.Draw(img)

# Envelope body rectangle
left = MARGIN
top = SIZE // 3
right = SIZE - MARGIN
bottom = SIZE - MARGIN
draw.rectangle([left, top, right, bottom], fill=ENVELOPE_COLOR, outline=ENVELOPE_COLOR)

# Envelope flap (triangle pointing down from top of body)
mid_x = SIZE // 2
flap_points = [(left, top), (right, top), (mid_x, top + (bottom - top) // 2)]
draw.polygon(flap_points, fill=FLAP_COLOR)

# Left diagonal line from top-left of body to centre
draw.line([(left, bottom), (mid_x, top + (bottom - top) // 2)], fill=(200, 220, 255), width=6)
# Right diagonal line from top-right of body to centre
draw.line([(right, bottom), (mid_x, top + (bottom - top) // 2)], fill=(200, 220, 255), width=6)

out_path = os.path.join(os.path.dirname(__file__), "icon.png")
img.save(out_path, "PNG")
print(f"Icon written to {out_path}")
