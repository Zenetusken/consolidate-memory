#!/usr/bin/env bash
# Install consolidate-memory into Claude Code by symlinking this repo's skill +
# shared-memory store into ~/.claude. Idempotent. Safe: backs up any real dir it
# would replace, and MERGES an existing real ~/.claude/memory into the repo first
# so no facts are lost.
#
#   ./install.sh            install / re-link
#   ./install.sh --uninstall   remove the symlinks (your repo + memory are untouched)
set -euo pipefail

REPO="$(cd "$(dirname "$0")" && pwd)"
SKILL_LINK="$HOME/.claude/skills/consolidate-memory"
MEM_LINK="$HOME/.claude/memory"
stamp="$(date +%Y%m%d-%H%M%S)"

uninstall() {
  for link in "$SKILL_LINK" "$MEM_LINK"; do
    if [ -L "$link" ]; then rm "$link"; echo "removed symlink $link"; fi
  done
  echo "Uninstalled. The repo ($REPO) and its memory/ are untouched."
  exit 0
}
[ "${1:-}" = "--uninstall" ] && uninstall

mkdir -p "$HOME/.claude/skills" "$REPO/memory"

# --- skill ---
if [ -e "$SKILL_LINK" ] && [ ! -L "$SKILL_LINK" ]; then
  mv "$SKILL_LINK" "$SKILL_LINK.bak.$stamp"
  echo "backed up existing skill dir -> $SKILL_LINK.bak.$stamp"
fi
ln -sfn "$REPO/skill" "$SKILL_LINK"

# --- shared memory (merge an existing real store in, then link) ---
if [ -e "$MEM_LINK" ] && [ ! -L "$MEM_LINK" ]; then
  cp -an "$MEM_LINK"/. "$REPO/memory"/ 2>/dev/null || true
  mv "$MEM_LINK" "$MEM_LINK.bak.$stamp"
  echo "merged + backed up existing ~/.claude/memory -> $MEM_LINK.bak.$stamp"
fi
ln -sfn "$REPO/memory" "$MEM_LINK"

echo ""
echo "✓ installed"
echo "  $SKILL_LINK -> $REPO/skill   (user-level → loads in EVERY project)"
echo "  $MEM_LINK -> $REPO/memory  (the shared-consciousness stream; gitignored)"
echo ""
echo "Next: run /reload in Claude Code, then say 'dream' (or 'consolidate my memory')"
echo "in any project. Run './cm network' to see the cross-project graph."
