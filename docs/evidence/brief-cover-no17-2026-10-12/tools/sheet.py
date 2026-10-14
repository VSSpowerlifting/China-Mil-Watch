import sys
from pathlib import Path
from PIL import Image, ImageDraw
D = Path(sys.argv[1]); kind, w, scale = sys.argv[2], int(sys.argv[3]), float(sys.argv[4])
ims = [Image.open(D / f"{v}-{kind}-{w}.png").convert("RGB") for v in "ABC"]
ims = [i.resize((int(i.width*scale), int(i.height*scale))) for i in ims]
W = sum(i.width for i in ims) + 40; H = max(i.height for i in ims) + 30
s = Image.new("RGB", (W, H), "white"); x = 10; d = ImageDraw.Draw(s)
for v, i in zip("ABC", ims):
    s.paste(i, (x, 26)); d.text((x, 6), v, fill="black"); x += i.width + 10
s.save(D / f"sheet-{kind}-{w}.jpg", quality=85)
