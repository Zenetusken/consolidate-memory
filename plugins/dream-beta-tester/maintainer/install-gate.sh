#!/usr/bin/env bash
# One-time setup for the MAINTAINER continuous-QA gate (marketplace owner only; end users who just
# install the plugin use the /dream-beta-test skill and don't need this).
#
# It (1) generates the FROZEN fixture store, (2) populates the frozen known-bad canary from the
# plugin cache, and (3) installs a pre-push hook on the consolidate-memory repo that runs the gate
# against the version being pushed and BLOCKS a known-defect regression. The hook resolves the
# LATEST installed dream-beta-tester at fire time, so it survives plugin updates.
#
# Usage:  install-gate.sh [CONSOLIDATE_MEMORY_REPO]   (default: git toplevel, else ~/project/consolidate-memory)
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
PLUGIN="$(cd "$HERE/.." && pwd)"
STATE="${DREAM_BETA_STATE:-$HOME/.dream-beta-test}"
CM_REPO="${1:-$(git -C . rev-parse --show-toplevel 2>/dev/null || echo "$HOME/project/consolidate-memory")}"
mkdir -p "$STATE"

echo "1/3 fixture store (over-budget + wikilink-orphan → D3/D4) …"
python3 "$PLUGIN/fixtures/make_fixture.py" "$STATE/gate-repo"

echo "2/3 frozen known-bad canary …"
CSRC="$(ls -d "$HOME"/.claude/plugins/cache/*/consolidate-memory/0.1.19/scripts 2>/dev/null | head -1)"
if [ -n "$CSRC" ]; then
  rm -rf "$STATE/canary-v0.1.19"; mkdir -p "$STATE/canary-v0.1.19"
  cp -r "$CSRC" "$STATE/canary-v0.1.19/scripts"
  echo "    canary ✓  ($CSRC)"
else
  echo "    NOTE: no cached consolidate-memory 0.1.19 found — the gate's self-test will SKIP."
  echo "          install v0.1.19 once (any version predating the D3/D4 fixes) to enable watch-the-watcher."
fi

echo "3/3 pre-push hook on $CM_REPO …"
HOOKS="$CM_REPO/.git/hooks"
if [ ! -d "$HOOKS" ]; then
  echo "    WARNING: $HOOKS not found — is $CM_REPO a git repo? Skipping hook install."
elif [ -e "$HOOKS/pre-push" ]; then
  echo "    WARNING: $HOOKS/pre-push already exists — NOT overwriting."
  echo "             To chain, add this line to it:"
  echo "             G=\"\$(ls -d \"\$HOME\"/.claude/plugins/cache/*/dream-beta-tester/*/maintainer/ci_check.sh 2>/dev/null | sort -V | tail -1)\"; [ -n \"\$G\" ] && \"\$G\""
else
  cat > "$HOOKS/pre-push" <<'HOOK'
#!/bin/sh
# dream-beta-test continuous-QA gate — runs the LATEST installed dream-beta-tester (survives updates).
G="$(ls -d "$HOME"/.claude/plugins/cache/*/dream-beta-tester/*/maintainer/ci_check.sh 2>/dev/null | sort -V | tail -1)"
[ -n "$G" ] && exec "$G"
exit 0   # fail-open if the plugin isn't installed
HOOK
  chmod +x "$HOOKS/pre-push"
  echo "    hook ✓ → $HOOKS/pre-push"
fi

echo "done. state: $STATE  ·  test now: $PLUGIN/maintainer/ci_check.sh"
