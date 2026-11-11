#!/usr/bin/env python3
"""Map an AI-generated (or any) ad video before you edit it: shot cuts, speech timing, and a labeled contact sheet.

usage: analyze_source.py VIDEO OUT_DIR [--scene 0.3] [--lang ko] [--no-speech] [--rms START-END]

Writes OUT_DIR/analysis.json and OUT_DIR/shots.jpg (first / middle / last frame of every shot, time-labeled).

Speech timing uses mlx-whisper (Apple Silicon) or openai-whisper if installed, with word timestamps.
Recognizer times are estimates: line starts are often 0.3-0.7 s EARLY and word boundaries are loose. Never cut audio
on them directly. Before cutting near a line, print the loudness profile with --rms START-END and cut in the last
quiet window before the rise (a louder tail of the previous shot can sit right before that dip).
"""
import argparse, json, os, re, subprocess, sys
import numpy as np


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def duration(path):
    return float(run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', path]).stdout)


def fps(path):
    n, d = run(['ffprobe', '-v', 'error', '-select_streams', 'v', '-show_entries', 'stream=r_frame_rate', '-of', 'csv=p=0', path]).stdout.strip().split('/')
    return float(n) / float(d)


def scene_cuts(path, thr):
    log = run(['ffmpeg', '-i', path, '-vf', f"select='gt(scene,{thr})',showinfo", '-f', 'null', '-']).stderr
    return [round(float(t), 3) for t in re.findall(r'pts_time:([\d.]+)', log)]


def audio_pcm(path, sr=16000):
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-vn', '-ac', '1', '-ar', str(sr), '-f', 's16le', '-'], capture_output=True).stdout
    return np.frombuffer(raw, np.int16).astype(np.float32), sr


def rms_db(x, sr, t0, t1, win=0.05):
    out = []
    for t in np.arange(t0, t1, win):
        seg = x[int(t * sr):int((t + win) * sr)]
        out.append((round(float(t), 2), 20 * np.log10(np.sqrt(np.mean(seg ** 2)) + 1e-9) if len(seg) else -120))
    return out


def transcribe(path, lang):
    try:
        import mlx_whisper
        return mlx_whisper.transcribe(path, path_or_hf_repo='mlx-community/whisper-large-v3-turbo', language=lang, word_timestamps=True)
    except ImportError:
        pass
    try:
        import whisper
        return whisper.load_model('large-v3-turbo').transcribe(path, language=lang, word_timestamps=True)
    except ImportError:
        print('no whisper installed: pip install mlx-whisper (Apple Silicon) or openai-whisper', file=sys.stderr)
        return None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('video'); ap.add_argument('out')
    ap.add_argument('--scene', type=float, default=0.3)
    ap.add_argument('--lang', default='ko')
    ap.add_argument('--no-speech', action='store_true')
    ap.add_argument('--rms', help='START-END: print a 50 ms loudness profile to pick an exact audio cut point')
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    dur, f = duration(a.video), fps(a.video)
    cuts = scene_cuts(a.video, a.scene)
    bounds = [0.0] + cuts + [dur]
    shots = [{'index': i, 'start': bounds[i], 'end': bounds[i + 1],
              'safe_start': round(bounds[i] + 2 / f, 3), 'safe_end': round(bounds[i + 1] - 2 / f, 3)}
             for i in range(len(bounds) - 1)]
    result = {'video': a.video, 'duration': dur, 'fps': f, 'shots': shots, 'lines': []}

    if not a.no_speech:
        r = transcribe(a.video, a.lang)
        if r:
            x, sr = audio_pcm(a.video)
            for s in r['segments']:
                words = [{'word': w['word'].strip(), 'start': round(w['start'], 2), 'end': round(w['end'], 2)} for w in s.get('words', [])]
                start = s['start']
                result['lines'].append({'text': s['text'].strip(), 'start': round(s['start'], 2), 'end': round(s['end'], 2), 'words': words})

    # contact sheet
    try:
        from PIL import Image, ImageDraw, ImageFont
        tiles = []
        for s in shots:
            for t in (s['safe_start'], (s['start'] + s['end']) / 2, s['safe_end']):
                p = os.path.join(a.out, '_t.png')
                subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', f'{max(0, t):.3f}', '-i', a.video, '-frames:v', '1', '-vf', 'scale=-1:320', p])
                im = Image.open(p).convert('RGB'); d = ImageDraw.Draw(im)
                d.rectangle([0, 0, im.width, 26], fill='black'); d.text((4, 5), f"shot {s['index']}  {t:.2f}s", fill='yellow')
                tiles.append(im)
        w, h = tiles[0].size; cols = 9
        sheet = Image.new('RGB', (w * cols, h * ((len(tiles) + cols - 1) // cols)), 'white')
        for i, im in enumerate(tiles):
            sheet.paste(im, ((i % cols) * w, (i // cols) * h))
        sheet.save(os.path.join(a.out, 'shots.jpg'), quality=85)
        os.remove(os.path.join(a.out, '_t.png'))
    except Exception as e:  # contact sheet is a convenience
        print('contact sheet skipped:', e, file=sys.stderr)

    json.dump(result, open(os.path.join(a.out, 'analysis.json'), 'w'), ensure_ascii=False, indent=2)
    for s in shots:
        print(f"shot {s['index']}: {s['start']:.2f}-{s['end']:.2f}s (safe {s['safe_start']:.2f}-{s['safe_end']:.2f})")
    for l in result['lines']:
        print(f"line {l['start']:.2f}-{l['end']:.2f}: {l['text']}")
    if a.rms:
        x, sr = audio_pcm(a.video); r0, r1 = map(float, a.rms.split('-'))
        for t, v in rms_db(x, sr, r0, r1):
            print(f'{t:6.2f} {v:5.0f} ' + '#' * int(max(0, v - 40) / 2))


if __name__ == '__main__':
    main()
