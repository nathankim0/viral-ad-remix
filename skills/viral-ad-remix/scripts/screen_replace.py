#!/usr/bin/env python3
"""Replace the (AI-hallucinated) phone screen in a shot with your real app screen recording.

AI video models invent phone UIs: wrong numbers, wrong buttons, another app's design. Instead of zooming the shot
until the phone is out of frame, track the phone screen and paste the real recording onto it.

One command (recommended):
  auto SRC.mp4 START END APP OUT.mp4 [--work DIR] [--app-start S] [--blank x0,y0,x1,y1] [--key K --quad "x,y x,y x,y x,y"]
       extract -> find a key frame + screen corners automatically -> track the whole shot -> composite -> DIR/qa.png
       Always open DIR/key_preview.png and DIR/qa.png. If the auto quad is off, rerun with --key/--quad set by hand.
       START/END must stay inside ONE shot (2 frames inside each cut): tracking across a cut lands the screen on the wrong shot.

Manual steps (frame numbers are 0-based within the extracted shot):
  1. extract   SRC.mp4 START END FRAMES_DIR                 frames of one shot at the source fps
  2. preview   FRAMES_DIR KEY "x,y x,y x,y x,y" OUT.png     draw a corner quad (TL TR BR BL) on frame KEY, zoomed, to check it
  3. track     FRAMES_DIR KEY "x,y x,y x,y x,y" FIRST LAST QUADS.json
                planar tracking: optical flow on features inside the phone + RANSAC homography, forward and backward from KEY
  4. composite FRAMES_DIR QUADS.json APP OUT.mp4 [--app-start S] [--blank x0,y0,x1,y1 ...] [--grow 1.035]
                APP is an image, a directory of frames, or a video (sampled from --app-start at the shot fps).
                --blank paints white rectangles (APP pixel coords) over UI you must hide, e.g. an outdated banner.

Pick KEY as a sharp frame where the screen faces the camera; read the 4 screen corners off `preview` and adjust until
the quad sits exactly on the display area (inside the bezel). Frames outside FIRST..LAST are left untouched.
Fingers in front of the screen stay in front only if they are outside the quad; shots where fingers keep crossing
the screen (typing close-ups) cannot be composited cleanly: drop them.
"""
import argparse, glob, json, os, subprocess, sys, tempfile
import cv2, numpy as np


def parse_quad(s):
    return np.array([[float(v) for v in p.split(',')] for p in s.split()], np.float32)


def cmd_extract(a):
    os.makedirs(a.frames, exist_ok=True)
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', str(a.start), '-to', str(a.end), '-i', a.src, f'{a.frames}/%04d.png'], check=True)
    fs = frames_of(a.frames); prev = None
    for i, f in enumerate(fs):  # a shot boundary inside the range would put the screen onto the next shot: cut there
        g = cv2.resize(cv2.cvtColor(cv2.imread(f), cv2.COLOR_BGR2GRAY), (64, 114)).astype(np.float32)
        if prev is not None and np.mean(np.abs(g - prev)) > 35:
            for x in fs[i:]: os.remove(x)
            print(f'shot cut detected at frame {i}: dropped {len(fs) - i} frames after it', file=sys.stderr); break
        prev = g
    print(len(frames_of(a.frames)), 'frames ->', a.frames)


def frames_of(d):
    return sorted(glob.glob(f'{d}/*.png'))


def cmd_preview(a):
    fs = frames_of(a.frames); im = cv2.imread(fs[a.key]); q = parse_quad(a.quad)
    cv2.polylines(im, [q.astype(np.int32)], True, (0, 0, 255), 1)
    x0, y0 = np.maximum(q.min(0) - 40, 0).astype(int); x1, y1 = (q.max(0) + 40).astype(int)
    crop = cv2.resize(im[y0:y1, x0:x1], None, fx=3, fy=3, interpolation=cv2.INTER_NEAREST)
    for gx in range((x0 // 20 + 1) * 20, x1, 20):  # grid in source pixel coordinates, labeled every 20 px
        cv2.line(crop, ((gx - x0) * 3, 0), ((gx - x0) * 3, crop.shape[0]), (0, 255, 255), 1); cv2.putText(crop, str(gx), ((gx - x0) * 3 + 2, 12), 0, 0.35, (0, 255, 255), 1)
    for gy in range((y0 // 20 + 1) * 20, y1, 20):
        cv2.line(crop, (0, (gy - y0) * 3), (crop.shape[1], (gy - y0) * 3), (0, 255, 255), 1); cv2.putText(crop, str(gy), (2, (gy - y0) * 3 - 2), 0, 0.35, (0, 255, 255), 1)
    cv2.polylines(crop, [((q - [x0, y0]) * 3).astype(np.int32)], True, (0, 0, 255), 2)
    cv2.imwrite(a.out, crop); print(a.out)


def cmd_track(a):
    fs = frames_of(a.frames); G = [cv2.cvtColor(cv2.imread(f), cv2.COLOR_BGR2GRAY) for f in fs]
    last = min(a.last, len(fs) - 1); Q = [None] * len(fs); Q[a.key] = parse_quad(a.quad)

    def step(src, dst):
        q = Q[src]; c = q.mean(0); big = c + (q - c) * 1.15
        mask = np.zeros_like(G[src]); cv2.fillConvexPoly(mask, big.astype(np.int32), 255)
        p0 = cv2.goodFeaturesToTrack(G[src], 400, 0.01, 4, mask=mask)
        if p0 is None: Q[dst] = q.copy(); return
        p1, st, _ = cv2.calcOpticalFlowPyrLK(G[src], G[dst], p0, None, winSize=(21, 21), maxLevel=3)
        pb, st2, _ = cv2.calcOpticalFlowPyrLK(G[dst], G[src], p1, None, winSize=(21, 21), maxLevel=3)
        ok = (st.ravel() == 1) & (st2.ravel() == 1) & (np.linalg.norm(p0 - pb, axis=2).ravel() < 1.5)
        if ok.sum() < 8:
            print('lost track at frame', dst, '- holding previous quad', file=sys.stderr); Q[dst] = q.copy(); return
        H, _ = cv2.findHomography(p0[ok], p1[ok], cv2.RANSAC, 2.0)
        Q[dst] = cv2.perspectiveTransform(q.reshape(-1, 1, 2), H).reshape(4, 2)

    for i in range(a.key + 1, last + 1): step(i - 1, i)
    for i in range(a.key - 1, a.first - 1, -1): step(i + 1, i)
    json.dump([q.tolist() if q is not None else None for q in Q], open(a.out, 'w'))
    print('tracked', sum(q is not None for q in Q), 'of', len(fs), 'frames ->', a.out)


def app_frames(a, n, shot_fps):
    if os.path.isdir(a.app):
        return [cv2.imread(p) for p in frames_of(a.app)]
    if a.app.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
        return [cv2.imread(a.app)]
    tmp = tempfile.mkdtemp()
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', str(a.app_start), '-i', a.app, '-vf', f'fps={shot_fps}',
                    '-frames:v', str(n), f'{tmp}/%04d.png'], check=True)
    return [cv2.imread(p) for p in frames_of(tmp)]


def cmd_composite(a):
    fs = frames_of(a.frames); Q = json.load(open(a.quads))
    A = np.array([np.array(q, np.float32).ravel() if q else [np.nan] * 8 for q in Q])
    sm = A.copy()  # light temporal smoothing against jitter
    for i in range(len(A)):
        if np.isnan(A[i, 0]): continue
        w = A[max(0, i - 2):i + 3]; w = w[~np.isnan(w[:, 0])]; sm[i] = w.mean(0)
    apps = app_frames(a, len(fs), a.fps)
    for b in a.blank:
        x0, y0, x1, y1 = map(int, b.split(','))
        for im in apps: im[y0:y1, x0:x1] = 255
    ah, aw = apps[0].shape[:2]; r = int(aw * 0.10)
    ms = np.zeros((ah, aw), np.uint8)
    cv2.rectangle(ms, (r, 0), (aw - r, ah), 255, -1); cv2.rectangle(ms, (0, r), (aw, ah - r), 255, -1)
    for c in [(r, r), (aw - r, r), (r, ah - r), (aw - r, ah - r)]: cv2.circle(ms, c, r, 255, -1)
    S = np.float32([[0, 0], [aw, 0], [aw, ah], [0, ah]])
    tmp = tempfile.mkdtemp()
    for i, f in enumerate(fs):
        im = cv2.imread(f)
        if not np.isnan(sm[i, 0]):
            app = apps[min(i, len(apps) - 1)]
            q = sm[i].reshape(4, 2); c = q.mean(0); dst = np.float32(c + (q - c) * a.grow)
            M = cv2.getPerspectiveTransform(S, dst); size = (im.shape[1], im.shape[0])
            warp = cv2.GaussianBlur(cv2.warpPerspective(app, M, size, flags=cv2.INTER_AREA).astype(np.float32), (0, 0), 0.5)
            m = cv2.GaussianBlur(cv2.warpPerspective(ms, M, size).astype(np.float32) / 255, (3, 3), 0)[..., None]
            om = (im * m).sum((0, 1)) / max(m.sum(), 1); am = (warp * m).sum((0, 1)) / max(m.sum(), 1)
            warp = np.clip(warp * (om.mean() / max(am.mean(), 1)) ** 0.5, 0, 255)  # match screen brightness
            im = (im * (1 - m) + (warp * (1 - a.glare) + im * a.glare) * m).astype(np.uint8)  # keep a little glare
        cv2.imwrite(f'{tmp}/{i:04d}.png', im)
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-framerate', str(a.fps), '-i', f'{tmp}/%04d.png', '-c:v', 'libx264',
                    '-crf', '16', '-pix_fmt', 'yuv420p', a.out], check=True)
    print(a.out)


def order_quad(pts):
    pts = np.array(pts, np.float32).reshape(-1, 2); s = pts.sum(1); d = np.diff(pts, axis=1).ravel()
    return np.float32([pts[np.argmin(s)], pts[np.argmin(d)], pts[np.argmax(s)], pts[np.argmax(d)]])


def screen_candidates(im):
    """Phone-screen-like quads in one frame: bright low-saturation blobs at several thresholds + edge contours."""
    hsv = cv2.cvtColor(im, cv2.COLOR_BGR2HSV); H, W = im.shape[:2]; out = []
    vs = sorted(set([200, 175, 150, 125, 110, 95] + [int(np.percentile(hsv[..., 2], p)) for p in (25, 40, 55, 70)]))  # adaptive: backlit screens are dark
    masks = [((hsv[..., 2] > v) & (hsv[..., 1] < s)).astype(np.uint8) * 255 for v in vs for s in (45, 80, 110)]
    edges = cv2.dilate(cv2.Canny(cv2.GaussianBlur(cv2.cvtColor(im, cv2.COLOR_BGR2GRAY), (5, 5), 0), 40, 120), np.ones((3, 3), np.uint8))
    filled = np.zeros_like(edges); cs, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(filled, cs, -1, 255, -1); masks.append(filled)
    for m in masks:
        m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
        cs, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for c in cs:
            area = cv2.contourArea(c)
            if area < 0.004 * W * H or area > 0.25 * W * H: continue
            (cx, cy), (w, h), ang = cv2.minAreaRect(c); sh, lo = sorted([w, h])
            if lo == 0 or not (0.38 < sh / lo < 0.72): continue
            fill = area / (w * h)
            if fill < 0.75: continue
            hull = cv2.convexHull(c); q = None
            for eps in np.linspace(0.01, 0.08, 15):
                ap_ = cv2.approxPolyDP(hull, eps * cv2.arcLength(hull, True), True)
                if len(ap_) == 4: q = order_quad(ap_); break
            if q is None: q = order_quad(cv2.boxPoints(((cx, cy), (w, h), ang)))
            # texture inside a real screen (UI) vs a flat wall/sky
            mk = np.zeros(m.shape, np.uint8); cv2.fillConvexPoly(mk, q.astype(np.int32), 255)
            ring = cv2.dilate(mk, np.ones((9, 9), np.uint8)) - mk
            gray = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
            inside, bezel = gray[mk > 0].mean(), gray[ring > 0].mean()
            if inside - bezel < 15: continue            # a real screen sits inside a darker bezel
            tex = cv2.Laplacian(gray, cv2.CV_32F)[mk > 0].std()
            if tex < 8: continue                         # flat wall / sky / paper, not a UI
            out.append((fill * np.sqrt(area) * min(tex, 40) / 40 * min((inside - bezel) / 40, 1.5), q))
    return sorted(out, key=lambda t: -t[0])


def _line_intersect(p1, d1, p2, d2):
    A = np.array([d1, -d2]).T
    if abs(np.linalg.det(A)) < 1e-6: return None
    t = np.linalg.solve(A, p2 - p1); return p1 + t[0] * d1


def refine_quad(im, q):
    """Snap each side of a rough screen quad to the inner bezel edge.

    Bright-region detection often catches only part of a screen (a dark header, rows under the notch, backlight),
    which leaves hallucinated UI uncovered. For every side we search parallel lines (offset -10%..+55% of the
    screen size outward, rotated -6..+6 degrees) for a straight edge whose gradient is strong *continuously* along
    the side; UI text rows give broken edges and lose. The closest line scoring >= 80% of the best wins (the inner
    bezel edge comes before the outer one). Corners = intersections of the 4 lines. If the result is not convex,
    not phone-shaped (long/short 1.6-2.6), or its area is off (0.85-2.4x the seed), the seed is kept."""
    gray = cv2.GaussianBlur(cv2.cvtColor(im, cv2.COLOR_BGR2GRAY), (3, 3), 0).astype(np.float32); H, Wd = gray.shape
    gx, gy = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3), cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    q = order_quad(q); c = q.mean(0); lines = []
    def samp(img, pts):
        xs = np.clip(pts[:, 0], 0, Wd - 1).astype(int); ys = np.clip(pts[:, 1], 0, H - 1).astype(int); return img[ys, xs]
    for e in range(4):
        P, Q = q[e], q[(e + 1) % 4]; mid = (P + Q) / 2; d = (Q - P) / max(np.linalg.norm(Q - P), 1e-6)
        n = np.array([d[1], -d[0]], np.float32)
        if np.dot(mid - c, n) < 0: n = -n
        span = np.linalg.norm(q[(e + 2) % 4] - q[(e + 1) % 4]); L = np.linalg.norm(Q - P)
        cands = []
        for ang in np.radians(np.arange(-6, 6.1, 1.5)):
            R = np.array([[np.cos(ang), -np.sin(ang)], [np.sin(ang), np.cos(ang)]], np.float32); dd = R @ d; nn = np.array([dd[1], -dd[0]], np.float32)
            if np.dot(nn, n) < 0: nn = -nn
            for off in range(int(-0.1 * span), int(0.55 * span) + 1):
                m0 = mid + n * off; pts = m0 + np.outer(np.linspace(-0.4, 0.4, 40) * L, dd)
                g = np.abs(samp(gx, pts) * nn[0] + samp(gy, pts) * nn[1])
                cands.append(((g > 25).mean() * g.mean(), off, m0, dd))
        best = max(cands, key=lambda t: t[0])[0]
        pick = min((t for t in cands if t[0] >= 0.8 * best), key=lambda t: t[1])
        lines.append((pick[2], pick[3]))
    pts = [_line_intersect(lines[k][0], lines[k][1], lines[(k + 3) % 4][0], lines[(k + 3) % 4][1]) for k in range(4)]
    if any(p is None for p in pts): return q
    new = order_quad(np.array(pts)); sides = [np.linalg.norm(new[(k + 1) % 4] - new[k]) for k in range(4)]
    long_, short_ = (sides[1] + sides[3]) / 2, (sides[0] + sides[2]) / 2
    ratio = max(long_, short_) / max(min(long_, short_), 1e-6)
    area_ratio = cv2.contourArea(new) / max(cv2.contourArea(q), 1)
    if not cv2.isContourConvex(new.astype(np.int32).reshape(-1, 1, 2)) or not (1.6 <= ratio <= 2.6) or not (0.85 <= area_ratio <= 2.4):
        return q
    return new


def cmd_find(a):
    fs = frames_of(a.frames); best = (0, None, None)
    for i in range(0, len(fs), max(1, len(fs) // 24)):
        im = cv2.imread(fs[i]); c = screen_candidates(im)
        if c and c[0][0] > best[0]: best = (c[0][0], i, refine_quad(im, c[0][1]))
    if best[1] is None:
        raise SystemExit('no phone screen found automatically: pick KEY and corners by hand with `preview`')
    q = ' '.join(f'{x:.0f},{y:.0f}' for x, y in best[2])
    print(f'key frame {best[1]}  quad "{q}"  (score {best[0]:.1f})')
    if a.preview:
        a2 = argparse.Namespace(frames=a.frames, key=best[1], quad=q, out=a.preview); cmd_preview(a2)
    return best[1], q


def cmd_qa(a):
    fs = frames_of(a.frames); Q = json.load(open(a.quads)); comp = a.composite
    tmp = tempfile.mkdtemp(); subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', comp, f'{tmp}/%04d.png'], check=True)
    cf = frames_of(tmp); idx = [i for i, q in enumerate(Q) if q]; pick = [idx[int(k * (len(idx) - 1) / 5)] for k in range(6)] if idx else []
    tiles = []
    for i in pick:
        q = np.array(Q[i]); x0, y0 = np.maximum(q.min(0) - 30, 0).astype(int); x1, y1 = (q.max(0) + 30).astype(int)
        o = cv2.imread(fs[i])[y0:y1, x0:x1]; c = cv2.imread(cf[min(i, len(cf) - 1)])[y0:y1, x0:x1]
        t = np.hstack([o, c]); t = cv2.resize(t, (int(t.shape[1] * 300 / t.shape[0]), 300)); cv2.putText(t, str(i), (4, 20), 0, 0.6, (0, 255, 255), 2)
        tiles.append(t)
    w = max(t.shape[1] for t in tiles); tiles = [cv2.copyMakeBorder(t, 0, 0, 0, w - t.shape[1], cv2.BORDER_CONSTANT) for t in tiles]
    cv2.imwrite(a.out, np.vstack([np.hstack(tiles[:3]), np.hstack(tiles[3:6])]) if len(tiles) == 6 else np.vstack(tiles))
    print(a.out, '- left: original, right: composite. Check that no original screen pixels show at the edges and the quad never slides off the phone.')


def cmd_auto(a):
    os.makedirs(a.work, exist_ok=True); fr = os.path.join(a.work, 'frames')
    cmd_extract(argparse.Namespace(src=a.src, start=a.start, end=a.end, frames=fr))
    if a.key is not None and a.quad:
        key, q = a.key, a.quad
    else:
        key, q = cmd_find(argparse.Namespace(frames=fr, preview=os.path.join(a.work, 'key_preview.png')))
    n = len(frames_of(fr)); qj = os.path.join(a.work, 'quads.json')
    cmd_track(argparse.Namespace(frames=fr, key=key, quad=q, first=0, last=n - 1, out=qj))
    cmd_composite(argparse.Namespace(frames=fr, quads=qj, app=a.app, out=a.out, app_start=a.app_start, fps=a.fps,
                                     blank=a.blank, grow=a.grow, glare=a.glare))
    cmd_qa(argparse.Namespace(frames=fr, quads=qj, composite=a.out, out=os.path.join(a.work, 'qa.png')))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    e = sub.add_parser('extract'); e.add_argument('src'); e.add_argument('start', type=float); e.add_argument('end', type=float); e.add_argument('frames')
    p = sub.add_parser('preview'); p.add_argument('frames'); p.add_argument('key', type=int); p.add_argument('quad'); p.add_argument('out')
    t = sub.add_parser('track'); t.add_argument('frames'); t.add_argument('key', type=int); t.add_argument('quad')
    t.add_argument('first', type=int); t.add_argument('last', type=int); t.add_argument('out')
    c = sub.add_parser('composite'); c.add_argument('frames'); c.add_argument('quads'); c.add_argument('app'); c.add_argument('out')
    c.add_argument('--app-start', type=float, default=0.0); c.add_argument('--fps', type=float, default=24)
    c.add_argument('--blank', action='append', default=[]); c.add_argument('--grow', type=float, default=1.035)
    c.add_argument('--glare', type=float, default=0.07)
    f = sub.add_parser('find'); f.add_argument('frames'); f.add_argument('--preview')
    q = sub.add_parser('qa'); q.add_argument('frames'); q.add_argument('quads'); q.add_argument('composite'); q.add_argument('out')
    u = sub.add_parser('auto'); u.add_argument('src'); u.add_argument('start', type=float); u.add_argument('end', type=float)
    u.add_argument('app'); u.add_argument('out'); u.add_argument('--work', default='screen_work')
    u.add_argument('--key', type=int); u.add_argument('--quad'); u.add_argument('--app-start', type=float, default=0.0)
    u.add_argument('--fps', type=float, default=24); u.add_argument('--blank', action='append', default=[])
    u.add_argument('--grow', type=float, default=1.035); u.add_argument('--glare', type=float, default=0.07)
    a = ap.parse_args()
    {'extract': cmd_extract, 'preview': cmd_preview, 'track': cmd_track, 'composite': cmd_composite,
     'find': cmd_find, 'qa': cmd_qa, 'auto': cmd_auto}[a.cmd](a)


if __name__ == '__main__':
    main()
