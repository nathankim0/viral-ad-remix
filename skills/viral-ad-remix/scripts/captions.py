#!/usr/bin/env python3
"""Render caption / hook / end-card overlays as transparent PNGs (no ffmpeg drawtext needed).

usage: captions.py SPEC.json OUT_DIR [--size 720x1280] [--font PATH]

SPEC.json is a list of items:
  {"id": "hook", "lines": ["이번 달 포인트,", "얼마나 쌓였을까?"], "y": 195, "size": 62, "style": "hook"}
  {"id": "c1", "lines": ["이걸로 미리", "확인할 수 있다고?"], "y": 900, "size": 42, "align": "right"}
  {"id": "end", "style": "endcard", "icon": "icon.png", "title": "AppName", "bg": "245,247,242"}
styles: "box" (default: white text on a dark rounded box), "hook" (white/yellow lines on a dark band), "endcard" (full frame).
align: center (default), left, right.

Keep captions out of the bottom ~20% and right edge where Reels/Shorts/Meta buttons sit, and never over the part of an
app screen the viewer must read. One sentence per caption, at most two lines. Fewer words beat more disclaimers stacked
on screen; put required notices where they are legible but small.
"""
import argparse, json, os
from PIL import Image, ImageDraw, ImageFont

FONTS = ['/System/Library/Fonts/AppleSDGothicNeo.ttc', '/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf',
         '/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc']


def font(path, size):
    for p in ([path] if path else []) + FONTS:
        if p and os.path.exists(p):
            try:
                return ImageFont.truetype(p, size, index=6 if p.endswith('AppleSDGothicNeo.ttc') else 0)
            except OSError:
                return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('spec'); ap.add_argument('out'); ap.add_argument('--size', default='720x1280'); ap.add_argument('--font')
    a = ap.parse_args(); W, H = map(int, a.size.split('x')); os.makedirs(a.out, exist_ok=True)
    for it in json.load(open(a.spec)):
        style = it.get('style', 'box')
        if style == 'endcard':
            bg = tuple(map(int, it.get('bg', '245,247,242').split(',')))
            img = Image.new('RGB', (W, H), bg); d = ImageDraw.Draw(img); s = int(W * 0.3)
            if it.get('icon'):
                ic = Image.open(it['icon']).convert('RGBA').resize((s, s)); m = Image.new('L', (s, s), 0)
                ImageDraw.Draw(m).rounded_rectangle([0, 0, s - 1, s - 1], radius=int(s * 0.23), fill=255)
                img.paste(ic, ((W - s) // 2, int(H * 0.34)), m)
            f = font(a.font, it.get('size', 76)); b = d.textbbox((0, 0), it.get('title', ''), font=f)
            d.text(((W - (b[2] - b[0])) // 2 - b[0], int(H * 0.34) + s + 40 - b[1]), it.get('title', ''), font=f, fill=(20, 60, 40))
            img.save(f"{a.out}/{it['id']}.png"); continue
        img = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
        f = font(a.font, it.get('size', 46)); lines = it['lines']; y = it.get('y', int(H * 0.67))
        bs = [d.textbbox((0, 0), l, font=f) for l in lines]; lh = max(b[3] - b[1] for b in bs) + 14
        bw = max(b[2] - b[0] for b in bs) + 40; bh = lh * len(lines) + 24
        align = it.get('align', 'center'); x0 = {'center': (W - bw) // 2, 'left': 28, 'right': W - 28 - bw}[align]
        if style == 'hook':
            x0, bw = 40, W - 80
        d.rounded_rectangle([x0, y, x0 + bw, y + bh], radius=24, fill=(0, 0, 0, 180))
        for i, (l, b) in enumerate(zip(lines, bs)):
            tx = x0 + (bw - (b[2] - b[0])) // 2 - b[0]
            colr = (255, 230, 0, 255) if style == 'hook' and i == len(lines) - 1 else (255, 255, 255, 255)
            d.text((tx, y + 20 + i * lh - b[1]), l, font=f, fill=colr, stroke_width=3 if style == 'hook' else 0, stroke_fill=(0, 0, 0, 255))
        img.save(f"{a.out}/{it['id']}.png")
        print(f"{a.out}/{it['id']}.png")


if __name__ == '__main__':
    main()
