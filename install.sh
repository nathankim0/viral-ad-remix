#!/usr/bin/env bash
# Link the skill into Claude Code and/or Codex so `git pull` in this repo updates it.
#   ./install.sh            # both
#   ./install.sh claude     # ~/.claude/skills only
#   ./install.sh codex      # ${CODEX_HOME:-~/.codex}/skills only
set -euo pipefail
src="$(cd "$(dirname "$0")" && pwd)/skills/viral-ad-remix"

link() {
  local dst="$1/viral-ad-remix"
  mkdir -p "$1"
  if [ -e "$dst" ] && [ ! -L "$dst" ]; then
    echo "$dst exists and is not a symlink; remove it first." >&2
    return 1
  fi
  ln -sfn "$src" "$dst"
  echo "Linked $dst -> $src"
}

case ${1:-all} in
  claude) link "$HOME/.claude/skills" ;;
  codex) link "${CODEX_HOME:-$HOME/.codex}/skills" ;;
  all)
    link "$HOME/.claude/skills"
    link "${CODEX_HOME:-$HOME/.codex}/skills"
    ;;
  *) echo "usage: $0 [claude|codex|all]" >&2; exit 1 ;;
esac

command -v ffmpeg >/dev/null || echo "Required: brew install ffmpeg"
python3 -c "import cv2, numpy, PIL" 2>/dev/null || echo "Required: pip3 install numpy pillow opencv-python-headless"
python3 -c "import mlx_whisper" 2>/dev/null || python3 -c "import whisper" 2>/dev/null || echo "Optional (speech checks): pip3 install mlx-whisper   # or openai-whisper"
