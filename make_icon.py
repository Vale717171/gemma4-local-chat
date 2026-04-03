from PIL import Image, ImageDraw, ImageFont
import os, subprocess, struct, zlib

SIZE = 512

img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
draw = ImageDraw.Draw(img)

# Background circle with gradient effect (two overlapping ellipses)
draw.ellipse([0, 0, SIZE, SIZE], fill="#1a1a2e")
draw.ellipse([20, 20, SIZE-20, SIZE-20], fill="#16213e")

# Inner glow ring
draw.ellipse([40, 40, SIZE-40, SIZE-40], outline="#2563eb", width=6)

# Letter G
try:
    font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 260)
except:
    font = ImageFont.load_default()

text = "G"
bbox = draw.textbbox((0, 0), text, font=font)
tw = bbox[2] - bbox[0]
th = bbox[3] - bbox[1]
x = (SIZE - tw) // 2 - bbox[0]
y = (SIZE - th) // 2 - bbox[1] - 20

# Shadow
draw.text((x+4, y+4), text, font=font, fill=(0, 0, 0, 120))
# Main text
draw.text((x, y), text, font=font, fill="#60a5fa")

# Small "4" subscript
try:
    font_small = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 110)
except:
    font_small = font
draw.text((SIZE//2 + 90, SIZE//2 + 60), "4", font=font_small, fill="#93c5fd")

png_path = "/Users/valentinoricco/mlx-chat/icon.png"
img.save(png_path)

# Convert to icns via iconutil
iconset = "/tmp/gemma.iconset"
os.makedirs(iconset, exist_ok=True)
sizes = [16, 32, 64, 128, 256, 512]
for s in sizes:
    resized = img.resize((s, s), Image.LANCZOS)
    resized.save(f"{iconset}/icon_{s}x{s}.png")
    resized2 = img.resize((s*2, s*2), Image.LANCZOS)
    resized2.save(f"{iconset}/icon_{s}x{s}@2x.png")

icns_path = "/Users/valentinoricco/mlx-chat/icon.icns"
subprocess.run(["iconutil", "-c", "icns", iconset, "-o", icns_path], check=True)
print(f"Icon created: {icns_path}")
