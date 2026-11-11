---
name: viral-ad-remix
description: Remake a proven viral short-form ad (TikTok / Reels / Shorts format) for your own mobile app with an AI video model, then fix what AI gets wrong — fake phone screens, mangled hands, broken lip-sync, dead air — and finish it with your real app recording, captions and an end card. Use when the user wants an app ad "like that viral video", asks to recreate/remake/copy an ad format for their app, or has an AI-generated ad whose phone screens, sync or pacing need repair. Covers reference discovery, cast character sheets (Codex or other image models), generation brief, shot analysis, phone-screen replacement with planar tracking, sync-safe assembly, and verification. Not for live-action shoots or long-form video.
---

# Viral ad remix

Turn a proven ad structure into an ad for the user's app. The AI model supplies people and places; **everything shown on a phone screen comes from the real app recording**; editing keeps every spoken line on the face that says it.

`$S` = `scripts/` in this skill's directory. Needs `ffmpeg`, Python 3 with `numpy pillow opencv-python-headless`, and for speech checks `mlx-whisper` (Apple Silicon) or `openai-whisper`. Record app footage with a screen recorder such as the `app-demo-recorder` skill (release build, real account, ad-free state).

Read `references/lessons.md` once before the first edit. It lists the failures this workflow is built to avoid.

## 0. Agree on the goal (one message)

Target audience (who actually stays in the app, not who you wish used it), channel (Meta / YouTube Shorts / TikTok), the one feature to show, and a credit budget. Senior audiences want slower pacing, bigger text, a peer on screen, and a concrete benefit (money, time). Do not start paid generation without a budget.

## 1. Find a reference that already works

```bash
python3 $S/find_reference_ads.py search --country KR --objective app_install --period 180 --order like
python3 $S/find_reference_ads.py search --country KR --keyword 앱테크 --lang ko
python3 $S/find_reference_ads.py download <id> <id> --out refs
```

Pick 4–30 s ads (recreate models accept that range) whose *structure* fits the feature: discovery → try → result → CTA. Likes are inflated by spend; compare within a search, not across. Reference videos are watermarked and belong to their advertisers: use them only as the structural source of a recreate job.

## 2. Cast the person (character sheet)

The recreate model needs a face to copy. If the user has no talent photos, generate one **character sheet per person** before any video credits are spent, and get the user's OK on it.

- **Who:** a peer of the target viewer (same age, region, job, clothes), ordinary rather than model-pretty, matching the reference's role (presenter, customer, neighbor).
- **Sheet:** one landscape image (about 1600x900), photorealistic, the same person and outfit in three views: front head-and-shoulders close-up, half body, full body; neutral light background, soft daylight. Hands relaxed and fully visible, five fingers each. No text, logos, watermarks or phone in hand.
- **Prompt skeleton:** "Photorealistic character reference sheet of ONE fictional <age> <nationality> <job> <gender>, <face/hair details>, wearing <outfit>. Three views side by side on a plain light background: front close-up, half body, full body. Natural skin texture, soft daylight. No text, no logos, no props."

Tools, cheapest first:

```bash
# Codex CLI image generation (included in a ChatGPT plan, no video credits)
codex exec --skip-git-repo-check --sandbox workspace-write -C cast \
  "Use your image generation tool to create ONE image: <prompt skeleton>. Save it as ./cast_<name>.png and print its path."
```

- Higgsfield (or another image API) through the agent's tools: `generate_image` with the same prompt, or its character-sheet workflow for a multi-view sheet. Costs credits; quote first.
- Any image model the user already pays for.

Open the image and check: one consistent face across views, natural hands, no text, no resemblance to a real or famous person. A fictional person must be disclosed as AI-generated where the platform or law requires it. Keep the sheet next to the brief: the recreate job gets it as the cast image.

## 3. Generate the remake

Prepare: the reference video, the character sheet from step 2, the app icon, and 1–2 real app screenshots.

Write the brief so the AI output is easy to repair:

- Keep the reference's beats and pacing; replace cast, setting, product. Give the spoken lines verbatim, short, in the target language. Avoid testimonial phrasing ("I tried it and got…") unless it is true; prefer demonstration ("Let's calculate…").
- Ask for **no captions or on-screen text** (they come out garbled), and **no close-ups of hands typing on a phone** (hands look wrong and fingers cross the screen, which cannot be screen-replaced).
- Phone screens will be replaced, so ask for the phone held still and facing the camera.
- Quote the cost first; draft at the lowest resolution; one output at a time.

## 4. Map the AI output before touching it

```bash
python3 $S/analyze_source.py ai.mp4 work/ana        # shots, speech lines, contact sheet work/ana/shots.jpg
python3 $S/analyze_source.py ai.mp4 work/ana --no-speech --rms 17.2-17.6   # exact audio cut point near a line
```

Look at `shots.jpg`. Classify every shot: **keep** (people, places), **screen-replace** (a phone faces the camera), **drop** (hands typing, distorted faces, unreadable action). Note where each line is spoken and on which shot. Recognizer line starts are often 0.3–0.7 s early: confirm with `--rms` before cutting audio.

## 5. Put the real app on every phone

```bash
python3 $S/screen_replace.py auto ai.mp4 3.33 6.50 app.mp4 work/shotB.mp4 --work work/B --app-start 2.4
python3 $S/screen_replace.py auto ai.mp4 17.46 21.25 app.mp4 work/shotE.mp4 --work work/E --app-start 10.6 --blank 0,1740,1080,2020
```

`auto` extracts the shot (stopping at any cut inside the range), finds the key frame and screen corners, snaps them to the bezel, tracks the phone through the whole shot (planar tracking, both directions, through rotation), composites with matched brightness and a little glare, and writes `work/X/key_preview.png` (quad + pixel grid) and `work/X/qa.png` (original vs composite).

**Always open both images.** If the quad is off, read the corners off the grid and rerun with `--key K --quad "x,y x,y x,y x,y"` (TL TR BR BL, inner screen edge). Use START/END from the analysis' safe range. Match the app clip to the line: show the input screen while the person asks, the result while they react. Paint out outdated or private UI with `--blank` (app pixel coords).

## 6. Build the result moment and text

```bash
python3 $S/pop_highlight.py result_clip.mp4 x0,y0,x1,y1 work/pop.mp4 --blank 0,975,720,1145   # key number pops, glows, sparkles
python3 $S/captions.py captions.json work/caps     # hook, line captions, end card as PNGs
```

Text rules: a hook on the first frame (a question the viewer has), one caption per spoken line, max two lines, big, high contrast, out of the bottom 20% and right edge, never over app UI the viewer must read. Keep text to the minimum the user accepts; legally required notices stay but small. End card = app icon + name (+ CTA if the user wants it).

## 7. Assemble with sync intact

Write a timeline JSON (format in `scripts/assemble.py --help`) and run:

```bash
python3 $S/assemble.py timeline.json out.mp4
```

- Audio is the source's own audio, cut into segments; every shot with a talking face uses **the same source times for video and audio**. Over app screens, wide shots and the end card, a line can play as voice-over.
- Drop dead air (silences before lines, between shots) instead of speeding everything up.
- A person shot must move from its first frame: never freeze a face to fill time; to lengthen a reaction, slow-motion the silent part with frame interpolation (`minterpolate`) and feed it slightly more source than needed.
- Dissolves use real frames past the cut point; app screens may hard-cut.
- Video and audio totals must match (the tool refuses otherwise).

## 8. Verify like a picky viewer

```bash
python3 $S/verify.py out.mp4 --forbid ai.mp4:10.79-17.29 --person 0-3.2 --person 5.2-8.8 --sheet work/sheet.jpg
```

Then look at the sheet, read the transcript against your captions, and watch it once. Typical misses: a boundary frame from the next shot, a face that freezes for 4 frames, a line playing over the wrong face, fake UI at the edge of a replaced screen, text covering the app, the hook staying on screen over app UI. Fix and re-verify before showing the user.

## 9. Deliver

One folder: final mp4, the AI raw output, composites, timeline JSON, README with the timeline table, credits spent, and open risks (AI-person disclosure, testimonial wording, mispronounced brand name). When an independent review is wanted, hand a fresh-context reviewer the frame sheet, transcript and timeline, and tell it which structure to keep: a reviewer told only "make it compliant and faster" will delete the people and the app footage.
