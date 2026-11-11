# Changelog

## Unreleased

## v0.2.1 (2026-11-11)

### Fixed

- Lessons: silence padded under a result animation reads as an audio dropout.

## v0.2.0 (2026-11-11)

### Added

- Workflow step 2, "Cast the person": generate and check a character sheet with Codex CLI image generation, Higgsfield, or another image model before spending video credits.

## v0.1.2 (2026-11-11)

### Fixed

- Captions: hook example and guidance no longer place the hook over the speaker's face.

## v0.1.1 (2026-11-11)

### Fixed

- `pop_highlight.py --at` picks the frame the number is cropped from, instead of the clip's first frame.
- Lessons: stale first frame in highlights, raising-phone tracking, dimmed screens.

## v0.1.0 (2026-11-11)

### Added

- `viral-ad-remix` skill: workflow from reference discovery through AI generation brief, shot analysis, phone-screen replacement, sync-safe assembly, and verification, plus `references/lessons.md` with the failures it is built to avoid.
- `find_reference_ads.py`: search and download top ads from TikTok Creative Center (unofficial endpoint) by country, objective, keyword, language.
- `analyze_source.py`: shot cuts with safe trim ranges, speech lines with word times, a labeled contact sheet, and a 50 ms loudness profile for exact audio cut points.
- `screen_replace.py`: one-command `auto` mode that finds the phone screen (bezel and UI-texture scoring), snaps the sides to continuous bezel edges, tracks the phone through the whole shot, composites the real app recording, stops at shot cuts, and writes key-frame and QA images; manual `preview` (with a pixel grid), `track`, `composite`, `qa` steps.
- `pop_highlight.py`: animated pop, glow and sparkles on a key number of a real app screen, rendered as a PNG sequence.
- `captions.py`: hook, caption, and end-card PNGs without ffmpeg drawtext.
- `assemble.py`: timeline JSON to final video with real-frame dissolves, per-segment speed and filters, overlays, audio segments, background music, and a video/audio length check.
- `verify.py`: forbidden-frame scan, frozen-person scan, loudness, transcript, and contact sheet.
- Claude Code plugin and marketplace manifests, Codex metadata, and `install.sh`.
