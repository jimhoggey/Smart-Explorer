"""Draw the Smart Explorer app icon and export .ico / .icns / .png / favicon.

A named slide: a light slide frame with a bold amber name-bar beneath it, on a
graphite panel. At 16-32px the stacked-slide hint behind is dropped so the
silhouette stays readable in the Windows taskbar.

Run: python scripts/make_icon.py
"""
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
S = 4  # supersample

PANEL_TOP, PANEL_BOT = (35, 39, 48), (21, 22, 26)
STACK, SLIDE, SIG = (86, 92, 104), (236, 237, 240), (255, 178, 36)


def draw(px, simple=False):
    n = 1024 * S
    grad = Image.new("RGB", (1, n))
    for y in range(n):
        t = y / (n - 1)
        grad.putpixel((0, y), tuple(round(a + (b - a) * t) for a, b in zip(PANEL_TOP, PANEL_BOT)))
    img = grad.resize((n, n))
    mask = Image.new("L", (n, n), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, n - 1, n - 1), radius=230 * S, fill=255)
    icon = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    icon.paste(img, (0, 0), mask)

    d = ImageDraw.Draw(icon)
    box = lambda a, b, c, e: (a * S, b * S, c * S, e * S)
    if not simple:
        d.rounded_rectangle(box(222, 176, 872, 542), radius=40 * S, fill=STACK)
    d.rounded_rectangle(box(176, 236, 826, 602), radius=40 * S, fill=SLIDE)
    d.rounded_rectangle(box(176, 712, 664, 848), radius=44 * S, fill=SIG)
    return icon.resize((px, px), Image.LANCZOS)


def main():
    ASSETS.mkdir(exist_ok=True)
    full = draw(1024)
    full.save(ASSETS / "icon.png")

    # Windows .ico — simplified art below 48px so the bar stays visible.
    # Pillow drops requested sizes larger than the base image, so save from the
    # biggest frame and supply every other size via append_images.
    px = (16, 24, 32, 48, 64, 128, 256)
    layers = {p: draw(p, simple=p < 48) for p in px}
    layers[256].save(ASSETS / "icon.ico", format="ICO", sizes=[(p, p) for p in px],
                     append_images=[layers[p] for p in px if p != 256])

    # macOS .icns via iconutil (macOS only; the committed file is reused on CI).
    if sys.platform == "darwin":
        iconset = ASSETS / "icon.iconset"
        iconset.mkdir(exist_ok=True)
        for base in (16, 32, 128, 256, 512):
            draw(base, simple=base < 48).save(iconset / ("icon_%dx%d.png" % (base, base)))
            draw(base * 2, simple=base * 2 < 48).save(iconset / ("icon_%dx%d@2x.png" % (base, base)))
        subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(ASSETS / "icon.icns")], check=True)

    (ROOT / "static" / "icon.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1024 1024">'
        '<rect width="1024" height="1024" rx="230" fill="#1b1e24"/>'
        '<rect x="222" y="176" width="650" height="366" rx="40" fill="#565c68"/>'
        '<rect x="176" y="236" width="650" height="366" rx="40" fill="#ecedf0"/>'
        '<rect x="176" y="712" width="488" height="136" rx="44" fill="#ffb224"/>'
        "</svg>\n", encoding="utf-8")
    print("wrote", ASSETS / "icon.ico", ASSETS / "icon.icns" if sys.platform == "darwin" else "")


if __name__ == "__main__":
    main()
