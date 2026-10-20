"""Draws assets/transcriber.ico (a white microphone on a blue disc).
Run once with the app's Python: python assets/make_icon.py"""
import os

from PIL import Image, ImageDraw

S = 1024  # drawn large, then scaled down so the edges stay smooth
img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(img)
d.ellipse((16, 16, S - 16, S - 16), fill=(47, 95, 208, 255))
white = (255, 255, 255, 255)
# capsule
d.rounded_rectangle((392, 170, 632, 600), radius=120, fill=white)
# cradle: a U-shaped arc around the lower half of the capsule
w = 52
d.arc((300, 330, 724, 720), start=0, end=180, fill=white, width=w)
d.rectangle((300, 470, 300 + w, 530), fill=white)
d.rectangle((724 - w, 470, 724, 530), fill=white)
# stem and base
d.rectangle((S // 2 - w // 2, 715, S // 2 + w // 2, 820), fill=white)
d.rounded_rectangle((372, 800, 652, 852), radius=26, fill=white)

out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "transcriber.ico")
img.resize((256, 256), Image.LANCZOS).save(
    out, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
img.resize((256, 256), Image.LANCZOS).save(out.replace(".ico", ".png"))
print(out)
