import json, sys
from PIL import Image, ImageDraw, ImageOps
img = ImageOps.exif_transpose(Image.open(sys.argv[1])).convert("RGB"); d = ImageDraw.Draw(img)
px = json.load(open(sys.argv[2]))
col = lambda i: (255,255,0) if i < 35 else (255,128,0) if i < 40 else (0,255,255) if i < 68 else (255,0,255) if i < 90 else (0,255,0) if i < 95 else (255,255,255)
for k, (x, y) in px.items():
    i = int(k); d.ellipse([x-9, y-9, x+9, y+9], outline=col(i), width=3)
    if i % 5 == 0 or i in (97, 39, 67, 89, 94): d.text((x+11, y-7), str(i), fill=col(i))
img.save(sys.argv[3], quality=85)
