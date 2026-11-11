# Lessons from a real remake

Each item cost at least one wasted render or a confused review. The workflow and scripts are built around them.

## Generation

- **AI invents phone screens.** A recreate model given app screenshots still drew another app's layout with a wrong amount (a different number than the voice said). Never ship an AI phone screen: replace it (`screen_replace.py`) or crop it out.
- **Hands typing on a phone look wrong** (extra knuckles, melted fingers) and fingers keep crossing the screen, so the screen cannot be replaced cleanly. Ask for no hand close-ups; drop them if they come anyway.
- **Garbled text.** Ask for no captions or on-screen text; add text in post.
- **Brand names get slurred** by AI voices (recognizers heard the app name as a different word). Plan to re-voice that line or show the name on screen.
- **Testimonial wording** ("I put in 3,000 and got…", laughing reaction) reads as a real user's review. With a fictional person this is a disclosure / false-testimonial risk in many markets. Prefer demonstration wording.
- **Recreate renders have no captions** and keep the reference's aspect and length; budget the full length.

## Editing

- **Cropping to hide a fake phone** makes the faces soft and "zoomed in"; viewers notice. Screen replacement keeps the original framing.
- **Moving a shot changes whose mouth says what.** A walking shot where she speaks a line was placed under a different line: lips moved with no sound, then the sound came later. Keep video and audio on the same source times for every talking shot.
- **Freezing a face** to fill the gap before a line reads as a stutter, even for 0.13 s. Cut the silence instead, or slow-motion the silent part with interpolation.
- **Frame interpolation runs out at the end** of a slowed clip (last frames repeat): give it extra source and trim.
- **A frame from the next shot** leaks in when a trim starts or ends exactly on a cut. Stay 2 frames inside.
- **Dissolves** filled with a cloned last frame look like a hitch. Use real frames from past the cut point.
- **Recognizer timings are early** (0.3–0.7 s). Cutting audio on them clips silence into the wrong place; use the RMS profile.
- **"Too fast" usually means bad time allocation**, not speed: the result screen got 1.9 s while a silent walk got 1.6 s of nothing.
- **Captions on top of app UI** hide what the ad is about. Keep the hook on the opening person shot only.
- **ffmpeg gotchas:** builds without freetype have no `drawtext` (render text as PNG); time-varying `scale` expressions are unreliable (animate with PNG sequences); xfade needs identical timebases; looping an image inside a filter graph yields short clips (loop at the input); `$VAR[label]` in zsh is an array subscript, so write filter graphs from Python.

## Screen replacement

- Per-frame detection of the bright screen jitters and misses frames (backlight, rotation). Detect once on a good frame, then **planar-track** (optical flow + RANSAC homography) both ways.
- Bright-region detection can lock onto a wall, sky or paper. A real screen sits inside a darker bezel and has UI texture: score for both.
- A screen's top often belongs to a darker status/header area and gets missed: snap each side to the longest **continuous** edge (bezel), not to the first dark row (text rows are dark too).
- Track from the shot's first frame: phones often rotate into view, and the fake UI is visible during the turn. Check every frame of the turn in the composite: when the phone is lifted from the waist and barely visible, tracking cannot follow it (see below).
- The highlighted number was cropped from the clip's first frame while the app was still changing tabs, so it showed a stale value. Pass `pop_highlight.py --at` with a time where the screen has settled, and read the number in the output.
- Tracking backward from the key frame through the moment a phone is raised left a screen floating beside the hand. Start the replaced clip once the screen faces the camera, and play the raise from the original (same source times for audio).
- A dimmed AI phone screen was too dark for automatic detection. Read the corners off `preview` and pass `--key` and `--quad`.
- A hook caption placed at a fixed top position (y≈195 of 1280) covered the speaker's face in a close framing. Find the face in the contact sheet first and put the hook on the chest or below it, where the line captions go.

## Review

- A fresh-context reviewer asked to "make it compliant and faster" removed the person and the real app footage and produced an explainer. Tell reviewers what to keep.
- Users notice: things that pause, things that are covered, things that don't match the voice. Check those first.
