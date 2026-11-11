#!/usr/bin/env python3
"""Make a key number on a real app screen pop: it lifts off the screen, grows to the center, glows, and sparkles.

usage: pop_highlight.py CLIP.mp4 X0,Y0,X1,Y1 OUT.mp4 [--to CX,CY] [--scale 2.0] [--duration 3.0] [--color 255,214,0] [--blank x0,y0,x1,y1]

CLIP is an already laid-out vertical clip (e.g. 720x1280) of a mostly static result screen.
The box X0,Y0,X1,Y1 (clip pixels) is cut from the first frame and animated as a frame-by-frame PNG overlay,
which works on any ffmpeg build (ffmpeg's time-varying scale expressions are not reliable across versions).
Timeline: 0.15 s pop start, 0.45 s ease-out with overshoot, then a gentle pulse; background dims, glow fades in,
sparkles blink from 0.5 s.
"""
import argparse, math, os, subprocess, tempfile
from PIL import Image, ImageDraw, ImageFilter


def ease(x):
    x = max(0.0, min(1.0, x)); return 1 - (1 - x) ** 3


def star(d, cx, cy, r, col):
    pts = []
    for i in range(8):
        ang = math.pi / 4 * i; rr = r if i % 2 == 0 else r * 0.28
        pts.append((cx + rr * math.cos(ang - math.pi / 2), cy + rr * math.sin(ang - math.pi / 2)))
    d.polygon(pts, fill=col)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('clip'); ap.add_argument('box'); ap.add_argument('out')
    ap.add_argument('--to'); ap.add_argument('--scale', type=float, default=2.0)
    ap.add_argument('--duration', type=float, default=3.0); ap.add_argument('--fps', type=int, default=30)
    ap.add_argument('--color', default='255,214,0')
    ap.add_argument('--blank', action='append', default=[], help='x0,y0,x1,y1 (clip px) painted white on every frame, e.g. an outdated banner')
    a = ap.parse_args()
    x0, y0, x1, y1 = map(int, a.box.split(',')); col = tuple(map(int, a.color.split(','))) + (255,)
    tmp = tempfile.mkdtemp()
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', a.clip, '-frames:v', '1', f'{tmp}/first.png'], check=True)
    first = Image.open(f'{tmp}/first.png').convert('RGBA'); W, H = first.size
    for b in a.blank:
        bx0, by0, bx1, by1 = map(int, b.split(',')); ImageDraw.Draw(first).rectangle([bx0, by0, bx1, by1], fill=(255, 255, 255, 255))
    region = first.crop((x0, y0, x1, y1)); rw, rh = region.size
    sx, sy = (x0 + x1) / 2, (y0 + y1) / 2
    tx, ty = map(float, a.to.split(',')) if a.to else (W / 2, sy + 0.04 * H)
    gw, gh = rw * a.scale + 70, rh * a.scale + 50
    glow = Image.new('RGBA', (W, H), (0, 0, 0, 0)); gd = ImageDraw.Draw(glow)
    gd.rounded_rectangle([tx - gw / 2 - 12, ty - gh / 2 - 12, tx + gw / 2 + 12, ty + gh / 2 + 12], radius=36, fill=col)
    glow = glow.filter(ImageFilter.GaussianBlur(18)); gd = ImageDraw.Draw(glow)
    gd.rounded_rectangle([tx - gw / 2, ty - gh / 2, tx + gw / 2, ty + gh / 2], radius=30, fill=(255, 255, 255, 255), outline=col, width=8)
    dim = Image.new('RGBA', (W, H), (0, 0, 0, 90))
    sparks = []
    for k in range(2):
        s = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(s)
        for j in range(5):
            ang = 2 * math.pi * (j / 5 + k * 0.1); rx, ry = gw / 2 + 25, gh / 2 + 25
            cx, cy = tx + rx * math.cos(ang), ty + ry * math.sin(ang); r = 24 if (j + k) % 2 == 0 else 16
            star(d, cx, cy, r, col); star(d, cx, cy, r * 0.5, (255, 255, 255, 255))
        sparks.append(s)
    n = int(a.duration * a.fps)
    for i in range(n):
        t = i / a.fps; fr = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        for img, al in ((dim, ease((t - 0.2) / 0.2)), (glow, ease((t - 0.3) / 0.2))):
            if al > 0:
                c = img.copy(); c.putalpha(c.getchannel('A').point(lambda v, al=al: int(v * al))); fr.alpha_composite(c)
        if t >= 0.15:
            p = ease((t - 0.15) / 0.3)
            over = 0.1 * math.sin(math.pi * min(1, max(0, (t - 0.3) / 0.25))) if t < 0.55 else 0
            pulse = 0.03 * math.sin(2 * math.pi * 1.4 * (t - 0.55)) if t >= 0.55 else 0
            k = 1 + (a.scale - 1) * p + over + pulse
            m = region.resize((max(1, int(rw * k)), max(1, int(rh * k))), Image.LANCZOS)
            fr.alpha_composite(m, (int(sx + (tx - sx) * p - m.width / 2), int(sy + (ty - sy) * p - m.height / 2)))
        if t >= 0.5: fr.alpha_composite(sparks[int(t / 0.15) % 2])
        fr.save(f'{tmp}/{i:04d}.png')
    boxes = ''
    for bx in a.blank:
        bx0, by0, bx1, by1 = map(int, bx.split(',')); boxes += f',drawbox=x={bx0}:y={by0}:w={bx1 - bx0}:h={by1 - by0}:color=white:t=fill'
    graph = f'[0:v]fps={a.fps}{boxes}[b];[b][1:v]overlay=0:0:eof_action=pass,trim=duration={a.duration},format=yuv420p[v]'
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', a.clip, '-framerate', str(a.fps), '-i', f'{tmp}/%04d.png', '-filter_complex', graph,
                    '-map', '[v]', '-an', '-c:v', 'libx264', '-crf', '18', a.out], check=True)
    print(a.out)


if __name__ == '__main__':
    main()
