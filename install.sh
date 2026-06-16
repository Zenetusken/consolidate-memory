#!/usr/bin/env bash
# Maintainer DEV install for consolidate-memory.
#
# End users do NOT run this — they install the published plugin:
#   /plugin marketplace add Zenetusken/consolidate-memory
#   /plugin install consolidate-memory@zenetusken-plugins
#
# This script is for working ON the tool from this repo. It:
#   1. retires the legacy user-skill symlink (~/.claude/skills/consolidate-memory),
#      which no longer works now that SKILL.md uses ${CLAUDE_PLUGIN_ROOT} (only set
#      when the skill loads AS A PLUGIN);
#   2. registers this repo as a LOCAL plugin marketplace and installs the plugin, so
#      you dogfood the exact artifact users get;
#   3. (optional) symlinks the personal shared-memory store ~/.claude/memory -> repo
#      memory/ so the maintainer can version their own global store. Personal choice,
#      unrelated to distribution; skip with --no-memory-link.
#
#   ./install.sh                    dev-install (plugin + memory link)
#   ./install.sh --no-memory-link   plugin only
#   ./install.sh --uninstall        remove the plugin + legacy symlink (+ memory link)
set -euo pipefail

REPO="$(cd "$(dirname "$0")" && pwd)"
MARKETPLACE="zenetusken-plugins"
PLUGIN="consolidate-memory"
LEGACY_SKILL_LINK="$HOME/.claude/skills/consolidate-memory"
MEM_LINK="$HOME/.claude/memory"
stamp="$(date +%Y%m%d-%H%M%S)"

have_claude() { command -v claude >/dev/null 2>&1; }

retire_legacy_symlink() {
  if [ -L "$LEGACY_SKILL_LINK" ]; then
    rm "$LEGACY_SKILL_LINK"
    echo "retired legacy user-skill symlink: $LEGACY_SKILL_LINK"
  elif [ -e "$LEGACY_SKILL_LINK" ]; then
    # a REAL legacy skill dir (pre-plugin install) would also double-load — back it up
    mv "$LEGACY_SKILL_LINK" "$LEGACY_SKILL_LINK.bak.$stamp"
    echo "backed up legacy user-skill dir -> $LEGACY_SKILL_LINK.bak.$stamp"
  fi
}

uninstall() {
  retire_legacy_symlink
  if have_claude; then
    claude plugin uninstall "$PLUGIN" 2>/dev/null || true
    claude plugin marketplace remove "$MARKETPLACE" 2>/dev/null || true
    echo "removed plugin + marketplace (if present)"
  fi
  if [ -L "$MEM_LINK" ]; then rm "$MEM_LINK"; echo "removed memory symlink $MEM_LINK"; fi
  echo "Uninstalled. The repo ($REPO) and its memory/ are untouched."
  exit 0
}

[ "${1:-}" = "--uninstall" ] && uninstall

if ! have_claude; then
  echo "error: 'claude' CLI not found on PATH — install Claude Code first." >&2
  exit 1
fi

# 1 + 2: retire legacy symlink, register local marketplace, install plugin.
retire_legacy_symlink
echo "registering local marketplace from $REPO ..."
claude plugin marketplace add "$REPO" 2>/dev/null \
  || claude plugin marketplace update "$MARKETPLACE" 2>/dev/null || true
claude plugin install "$PLUGIN@$MARKETPLACE"
echo "installed $PLUGIN@$MARKETPLACE (run /reload-plugins in an open session)"

# 3: optional personal memory-store symlink (merge an existing real store first).
if [ "${1:-}" != "--no-memory-link" ]; then
  mkdir -p "$HOME/.claude" "$REPO/memory"
  if [ -e "$MEM_LINK" ] && [ ! -L "$MEM_LINK" ]; then
    cp -an "$MEM_LINK"/. "$REPO/memory"/ 2>/dev/null || true
    mv "$MEM_LINK" "$MEM_LINK.bak.$stamp"
    echo "merged + backed up existing ~/.claude/memory -> $MEM_LINK.bak.$stamp"
  fi
  ln -sfn "$REPO/memory" "$MEM_LINK"
  echo "linked personal memory store: $MEM_LINK -> $REPO/memory"
fi

echo ""
echo "✓ dev-installed as a plugin: $PLUGIN@$MARKETPLACE"
echo "  Run /reload-plugins (or restart the session), then say 'dream' in any project."
