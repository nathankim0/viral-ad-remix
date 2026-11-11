#!/usr/bin/env python3
"""Assemble the final ad from a timeline JSON, keeping lip-sync exact and transitions freeze-free.

usage: assemble.py TIMELINE.json OUT.mp4 [--dry-run]

TIMELINE.json:
{
  "size": [720, 1280], "fps": 30,
  "inputs": {"ai": "recreate.mp4", "app": "app_recording.mp4", "B": "shotB_screen.mp4", "pop": "pop.mp4", "end": "end.png"},
  "segments": [
    {"input": "B",   "start": 0,     "end": 3.25},
    {"input": "app", "start": 7.40,  "end": 8.90, "vf": "crop=1080:2140:0:110,scale=646:1280,pad=720:1280:37:0:white"},
    {"input": "ai",  "start": 8.40,  "end": 10.50, "transition": 0.2},
    {"input": "ai",  "start": 17.46, "end": 19.00, "vf": "crop=220:391:178:30", "speed": 1.0},
    {"input": "pop", "start": 0,     "end": 3.0},
    {"input": "end", "duration": 3.15}
  ],
  "audio": [
    {"input": "ai", "start": 3.29, "end": 10.50},
    {"input": "ai", "start": 17.42, "end": 20.90},
    {"silence": 1.2},
    {"input": "ai", "start": 20.90, "end": 24.05}
  ],
  "overlays": [{"png": "hook.png", "start": 0, "end": 1.7}],
  "bgm": {"path": "bgm.wav", "volume": 0.35}
}

Rules this tool enforces, learned the hard way:
- Segment length = (end - start) / speed. Total video length must equal total audio length (checked), otherwise
  every later line drifts out of sync.
- "transition" (seconds, default 0) is a dissolve INTO the next segment. Its overlap is filled with REAL frames
  read past the segment's end (end + transition * speed), never with a frozen copy of the last frame, which reads
  as a stutter. Make sure those extra source frames still belong to the same shot (stay 2 frames inside a cut).
- Every segment is normalized to the same size, fps, SAR and timebase (1/fps) before xfade (mismatched timebases
  make ffmpeg refuse the graph).
- Images loop at the input with -loop 1 -framerate (looping inside the filter graph produces short clips).
- Image segments are padded to fill transitions, which is invisible for a static card.
"""
import argparse, json, subprocess, sys, tempfile


def ffmpeg_major():
    out = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True).stdout.split()
    try:
        return int(out[2].split('.')[0].lstrip('n'))
    except Exception:
        return 7


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('timeline'); ap.add_argument('out'); ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args(); T = json.load(open(a.timeline))
    W, H = T.get('size', [720, 1280]); fps = T.get('fps', 30)
    norm = f'scale={W}:{H}:force_original_aspect_ratio=decrease:flags=lanczos,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:white,setsar=1,fps={fps},format=yuv420p,settb=1/{fps}'
    names = list(T['inputs']); idx = {n: i for i, n in enumerate(names)}
    is_img = {n: T['inputs'][n].lower().endswith(('.png', '.jpg', '.jpeg')) for n in names}
    segs = T['segments']; n = len(segs); g = []; lens = []
    for k, s in enumerate(segs):
        tr = s.get('transition', 0) if k < n - 1 else 0; sp = s.get('speed', 1.0)
        if is_img[s['input']]:
            L = s['duration']; chain = f"[{idx[s['input']]}:v]setpts=PTS-STARTPTS"
        else:
            L = (s['end'] - s['start']) / sp
            chain = f"[{idx[s['input']]}:v]trim={s['start']}:{s['end'] + tr * sp:.4f},setpts=(PTS-STARTPTS)/{sp}"
        if s.get('vf'): chain += ',' + s['vf']
        chain += f",{norm},tpad=stop_duration=1:stop_mode=clone,trim=duration={L + tr:.4f},setpts=N/{fps}/TB,settb=1/{fps}[s{k}]"
        g.append(chain); lens.append((L, tr))
    prev, off = 's0', 0.0
    for k in range(1, n):
        off += lens[k - 1][0]; tr = lens[k - 1][1]; out = f'x{k}' if k < n - 1 else 'vb'
        if tr > 0:
            g.append(f"[{prev}][s{k}]xfade=transition=fade:duration={tr}:offset={off:.4f},settb=1/{fps}[{out}]")
        else:
            g.append(f"[{prev}][s{k}]concat=n=2:v=1:a=0,settb=1/{fps}[{out}]")
        prev = out
    if n == 1: g.append('[s0]null[vb]')
    vtotal = sum(L for L, _ in lens)
    ov_base = len(names); prev = 'vb'
    for i, o in enumerate(T.get('overlays', [])):
        out = f'o{i}'; g.append(f"[{prev}][{ov_base + i}:v]overlay=0:0:enable='between(t,{o['start']},{o['end']})'[{out}]"); prev = out
    g.append(f'[{prev}]null[v]')
    aparts = []; atotal = 0.0
    for i, p in enumerate(T['audio']):
        if 'silence' in p:
            g.append(f"anullsrc=r=48000:cl=stereo,atrim=duration={p['silence']}[ap{i}]"); atotal += p['silence']
        else:
            g.append(f"[{idx[p['input']]}:a]atrim={p['start']}:{p['end']},asetpts=PTS-STARTPTS,aresample=48000,aformat=channel_layouts=stereo,afade=t=in:d=0.02[ap{i}]")
            atotal += p['end'] - p['start']
        aparts.append(f'[ap{i}]')
    g.append(''.join(aparts) + f"concat=n={len(aparts)}:v=0:a=1[voice]")
    extra = []
    if T.get('bgm'):
        b = T['bgm']; bi = ov_base + len(T.get('overlays', []))
        g.append(f"[{bi}:a]aresample=48000,aformat=channel_layouts=stereo,atrim=0:{atotal:.3f},asetpts=PTS-STARTPTS,volume={b.get('volume', 0.35)},afade=t=out:st={max(0, atotal - 0.9):.3f}:d=0.8[bgm]")
        g.append("[voice][bgm]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.9[a]"); extra = ['-stream_loop', '-1', '-i', b['path']]
    else:
        g.append('[voice]anull[a]')
    print(f'video {vtotal:.3f}s  audio {atotal:.3f}s')
    if abs(vtotal - atotal) > 0.05:
        sys.exit(f'length mismatch {vtotal - atotal:+.3f}s: fix segments/audio so they match (sync would drift)')
    cmd = ['ffmpeg', '-v', 'error', '-y']
    for nme in names:
        if is_img[nme]:
            dur = max(s['duration'] + s.get('transition', 0) for s in segs if s['input'] == nme) + 1
            cmd += ['-loop', '1', '-framerate', str(fps), '-t', f'{dur:.3f}', '-i', T['inputs'][nme]]
        else:
            cmd += ['-i', T['inputs'][nme]]
    for o in T.get('overlays', []):
        cmd += ['-loop', '1', '-framerate', str(fps), '-t', f'{vtotal + 1:.3f}', '-i', o['png']]
    cmd += extra
    gf = tempfile.NamedTemporaryFile('w', suffix='.txt', delete=False); gf.write(';'.join(g)); gf.close()
    cmd += (['-/filter_complex', gf.name] if ffmpeg_major() >= 7 else ['-filter_complex_script', gf.name])
    cmd += ['-map', '[v]', '-map', '[a]', '-c:v', 'libx264', '-crf', '18', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '160k',
            '-movflags', '+faststart', '-t', f'{vtotal:.3f}', a.out]
    if a.dry_run:
        print(' '.join(cmd)); print(open(gf.name).read()); return
    subprocess.run(cmd, check=True); print(a.out)


if __name__ == '__main__':
    main()
