# AGENTS.md

Instructions for any coding agent (Claude Code, Codex, others) working in this repository. `CLAUDE.md` is a symlink to this file; edit `AGENTS.md` only.

## What this repo is

An agent skill that remakes a proven viral short-form ad for the user's app with an AI video model, then repairs what the AI gets wrong: hallucinated phone screens (replaced with the real app recording by planar tracking), mangled hand close-ups, broken lip-sync, and dead air. It ships as a Claude Code plugin (this repo is its own marketplace) and as a plain skill folder that `install.sh` symlinks into `~/.claude/skills` and `~/.codex/skills`.

```text
skills/viral-ad-remix/SKILL.md                     workflow the agent follows
skills/viral-ad-remix/references/lessons.md        failures the workflow is built to avoid
skills/viral-ad-remix/scripts/find_reference_ads.py  TikTok Creative Center top-ads search and download
skills/viral-ad-remix/scripts/analyze_source.py    shot cuts, speech lines, contact sheet, loudness profile
skills/viral-ad-remix/scripts/screen_replace.py    find, track and replace phone screens (auto + manual steps)
skills/viral-ad-remix/scripts/pop_highlight.py     animated highlight of a key number on an app screen
skills/viral-ad-remix/scripts/captions.py          hook / caption / end-card PNGs
skills/viral-ad-remix/scripts/assemble.py          timeline JSON -> final video, sync-safe
skills/viral-ad-remix/scripts/verify.py            forbidden frames, frozen faces, transcript, contact sheet
skills/viral-ad-remix/agents/openai.yaml           Codex display metadata
.claude-plugin/plugin.json                         plugin manifest (version)
.claude-plugin/marketplace.json                    marketplace manifest (metadata.version)
install.sh                                         symlink installer for Claude Code and Codex
assets/banner.png                                  README banner
```

## Rules for every change

1. **Commit and push after every change.** One logical change per commit. Push to `main` right after committing. Do not leave work uncommitted at the end of a task.
2. **Release only for distribution changes.** A change is a distribution change when it alters what users install or how the skill behaves: `skills/`, `.claude-plugin/`, `install.sh`, or a changed install command. For these:
   - bump the version one step in `.claude-plugin/plugin.json` (`version`) and `.claude-plugin/marketplace.json` (`metadata.version`): patch for fixes and small tweaks, minor for new features, major for breaking changes
   - move the `Unreleased` notes in `CHANGELOG.md` under the new version
   - commit `Release vX.Y.Z`, push, then tag and release:
     ```bash
     git tag -a vX.Y.Z -m "vX.Y.Z"
     git push origin vX.Y.Z
     gh release create vX.Y.Z --title "vX.Y.Z" --notes-file <notes>
     ```
3. **Docs-only changes do not release.** README, AGENTS.md, images, comments, and typo fixes are committed and pushed with no version bump, tag, or release.
4. **Keep READMEs in sync.** Any change to `README.md` gets the same change in `README.ko.md`, and the reverse.
5. **Validate before committing** a distribution change: `claude plugin validate .` and `python3 -m py_compile skills/viral-ad-remix/scripts/*.py` must pass. When you change `screen_replace.py`, run `auto` on at least two real shots (one backlit, one where the phone rotates into view) and look at `key_preview.png` and `qa.png`. When you change `assemble.py`, check that video and audio lengths still match and run `verify.py` on the output.
6. **Never commit secrets or private information**: no tokens, employer or internal names, app names, screenshots or recordings from private projects, personal emails, or home paths. Test media stays outside the repo.

## Project rules

- Keep the skill app-agnostic. Examples use generic names (`app.mp4`, `AppName`), never a specific company's app.
- Every lesson added to `references/lessons.md` should come from an observed failure, stated as what happened and what to do instead.
- Scripts must run on stock Homebrew ffmpeg (no `drawtext`) and Python 3 with numpy, Pillow, OpenCV.
- Public commits use the author `nathankim0 <37360089+nathankim0@users.noreply.github.com>`.

## Commit messages

Imperative, short subject. Example: `Snap screen quads to continuous bezel edges`.
