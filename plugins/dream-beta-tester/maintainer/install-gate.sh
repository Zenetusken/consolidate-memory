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
  # M3-SLUG GRAFT (required since cm v0.1.40): the v0.1.19 canary computes the OLD slug
  # (re.sub(r'[/_]', ...)); the M3 harness uses re.sub(r'[^A-Za-z0-9]', ...). On a state path
  # containing a '.' (default ~/.dream-beta-test), the two DIVERGE → the un-grafted canary resolves a
  # DIFFERENT, empty store → reports 0 → spurious FAILs that coincidentally satisfy "≥2 FAIL" → a
  # FALSE-GREEN self-test (it can't actually prove detection). Graft ONLY the slug rule (NOT the
  # D3/D4 defect logic — the slug is not the defect) so the canary resolves the SAME fixture store
  # the M3 harness creates and exhibits its REAL backfill-under-gate / evict-orphan defects.
  # v0.1.69/B8: `sed -i 's/…/…/g'` (no backup-suffix arg) is GNU-only — BSD/macOS sed REQUIRES a
  # suffix arg (`sed -i ''`) and errors otherwise, silently leaving the canary un-grafted → the
  # exact false-green self-test this graft exists to prevent (STATUS.md's documented failure mode).
  # A portable tmp+mv loop works identically on GNU and BSD/macOS.
  for f in "$STATE/canary-v0.1.19/scripts"/*.py; do
    sed 's/re\.sub(r"\[\/_\]"/re.sub(r"[^A-Za-z0-9]"/g' "$f" > "$f.tmp" && mv "$f.tmp" "$f"
  done
  echo "    canary ✓  ($CSRC)  [M3-slug grafted]"
else
  echo "    NOTE: no cached consolidate-memory 0.1.19 found — the gate's self-test will SKIP."
  echo "          install a v0.1.19 cache once to enable watch-the-watcher; install-gate grafts the"
  echo "          M3 slug onto it automatically (v0.1.19 is old-slug, incompatible with v0.1.40's M3 rule)."
fi

echo "3/3 pre-push hook on $CM_REPO …"
HOOKS="$CM_REPO/.git/hooks"
if [ ! -d "$HOOKS" ]; then
  echo "    WARNING: $HOOKS not found — is $CM_REPO a git repo? Skipping hook install."
elif [ -e "$HOOKS/pre-push" ] && ! grep -q "dream-beta-test continuous-QA gate" "$HOOKS/pre-push" 2>/dev/null; then
  echo "    WARNING: $HOOKS/pre-push exists and is NOT a dream-beta-test hook — NOT overwriting (won't clobber yours)."
  echo "             To chain, add this line to it:"
  echo "             G=\"\$(ls -d \"\$HOME\"/.claude/plugins/cache/*/dream-beta-tester/*/maintainer/ci_check.sh 2>/dev/null | sort -V | tail -1)\"; [ -n \"\$G\" ] && \"\$G\""
else
  # No hook, OR a STALE dream-beta-test hook (marker matched) → (re)install the CURRENT one. v0.1.41 stale-hook
  # fix: the marker lets a re-run UPDATE its own hook after a location/slug move. The OLD hook exec'd a FROZEN
  # `~/.claude/dream-beta-tester/ci_check.sh` that went stale (old-slug) and FALSE-FAILED the M3 split-brain
  # CHK-QTY; this one resolves the cache-LATEST, surviving plugin updates. Without the marker check, install-gate
  # refused to overwrite and left the stale hook in place (the exact bug that blocked the v0.1.41 push).
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
