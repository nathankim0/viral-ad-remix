#!/usr/bin/env python3
"""Check a finished ad the way a picky viewer would, before showing it to anyone.

usage: verify.py FINAL.mp4 [--forbid SRC.mp4:START-END ...] [--person START-END ...] [--lang ko] [--sheet OUT.jpg]

--forbid   source ranges that must never appear at all (a hand close-up you cut, the frame across a shot boundary).
           Do not list shots you screen-replaced: only the phone differs, so whole frames still match. Check those with
           `screen_replace.py qa`.
           Every final frame is compared to those source frames (64x114 gray, mean abs diff < 6 = match).
--person   ranges of the FINAL video that show a person: no frozen run (>= 3 identical frames) is allowed there.
--sheet    contact sheet with one frame every 0.5 s, time-labeled, to look at yourself.
Also prints the transcript with word times (mlx-whisper / openai-whisper) so captions and lip-sync can be checked
line by line against the timeline, and loudness/peak.
Exit code 1 if a forbidden frame or a person freeze is found.
"""
import argparse, subprocess, sys
import numpy as np


def frames(path, w=64, h=114, ss=None, to=None):
    cmd = ['ffmpeg', '-v', 'error'] + (['-ss', str(ss), '-to', str(to)] if ss is not None else []) + ['-i', path, '-vf', f'scale={w}:{h},format=gray', '-f', 'rawvideo', '-']
    return np.frombuffer(subprocess.run(cmd, capture_output=True).stdout, np.uint8).reshape(-1, h, w).astype(np.float32)


def fps_of(path):
    n, d = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v', '-show_entries', 'stream=r_frame_rate', '-of', 'csv=p=0', path],
                          capture_output=True, text=True).stdout.strip().split('/')
    return float(n) / float(d)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('video'); ap.add_argument('--forbid', action='append', default=[]); ap.add_argument('--person', action='append', default=[])
    ap.add_argument('--lang', default='ko'); ap.add_argument('--sheet'); ap.add_argument('--no-speech', action='store_true')
    a = ap.parse_args(); bad = False
    F = frames(a.video); fps = fps_of(a.video)
    for spec in a.forbid:
        src, rng = spec.rsplit(':', 1); s0, s1 = map(float, rng.split('-'))
        ref = frames(src, ss=s0, to=s1)[::2]
        hits = [round(i / fps, 2) for i, f in enumerate(F) if np.min(np.mean(np.abs(ref - f), axis=(1, 2))) < 6]
        print(f'forbidden {spec}: {len(hits)} frames', hits[:10]); bad |= bool(hits)
    for rng in a.person:
        p0, p1 = map(float, rng.split('-')); i0, i1 = int(p0 * fps), int(p1 * fps)
        d = [np.mean(np.abs(F[i + 1] - F[i])) for i in range(i0, min(i1, len(F) - 1))]
        runs, r = [], 0
        for i, x in enumerate(d):
            r = r + 1 if x < 0.1 else 0
            if r == 3: runs.append(round((i0 + i - 2) / fps, 2))
        print(f'person {rng}: frozen runs at', runs or 'none'); bad |= bool(runs)
    lv = subprocess.run(['ffmpeg', '-i', a.video, '-af', 'ebur128=peak=true', '-f', 'null', '-'], capture_output=True, text=True).stderr
    for line in lv.splitlines()[-12:]:
        if 'I:' in line or 'Peak:' in line: print('loudness', line.strip())
    if not a.no_speech:
        try:
            import mlx_whisper as wh; r = wh.transcribe(a.video, path_or_hf_repo='mlx-community/whisper-large-v3-turbo', language=a.lang, word_timestamps=True)
        except ImportError:
            try:
                import whisper; r = whisper.load_model('large-v3-turbo').transcribe(a.video, language=a.lang, word_timestamps=True)
            except ImportError:
                r = None; print('no whisper installed; skipping transcript')
        if r:
            for s in r['segments']:
                print(f"{s['start']:6.2f}-{s['end']:6.2f}  {s['text'].strip()}")
    if a.sheet:
        from PIL import Image, ImageDraw
        tiles = []
        for k in range(int(len(F) / fps / 0.5) + 1):
            t = k * 0.5; p = a.sheet + '.tmp.png'
            subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', f'{t:.2f}', '-i', a.video, '-frames:v', '1', '-vf', 'scale=-1:360', p])
            try:
                im = Image.open(p).convert('RGB')
            except Exception:
                continue
            ImageDraw.Draw(im).rectangle([0, 0, 64, 22], fill='black'); ImageDraw.Draw(im).text((4, 5), f'{t:.1f}s', fill='yellow'); tiles.append(im)
        w, h = tiles[0].size; cols = 10
        sh = Image.new('RGB', (w * cols, h * ((len(tiles) + cols - 1) // cols)), 'white')
        for i, im in enumerate(tiles): sh.paste(im, ((i % cols) * w, (i // cols) * h))
        sh.save(a.sheet, quality=85); print('sheet', a.sheet)
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
