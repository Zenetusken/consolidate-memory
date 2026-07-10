#!/usr/bin/env python3
"""SessionStart beacon — a one-line, read-only absorption advisory (Stage B of the beacon track;
docs/session-beacon.spec.md). Runs as a plugin SessionStart hook (startup/resume): its stdout is
INJECTED INTO CLAUDE'S CONTEXT (the documented SessionStart exception), so it emits AT MOST ONE
FACTUAL line — and only when this project's store is measurably behind the fleet. It never pulls,
never writes, never blocks (SessionStart cannot block by contract).

The premise is MEASURED, not assumed (Stage A, `--staleness`, first live run): 12 of 13 fleet
stores behind on user-global absorption; one real node 18 days behind with 11 missing globals —
and a lagging node by definition never runs the flows that would tell anyone. This is the only
surface that changes the RATE at which the fleet absorbs (and, via the dreams it prompts,
produces) evidence.

Budget discipline (hooks.json enforces a 2s hard timeout): every input is a file read —
`detect_stacks` is NEVER run here (MEASURED 2003ms on the fleet's biggest repo; the --pull-written
`stacks` cache in .consolidation-state.json is the substitute, with an honest user-global-only
degradation when absent), and there are NO subprocesses (the git-based dream-timing advisory
stays in `cm status` — a documented v1 reach limit).

Failure posture (no-failure-masking, adapted to a context-injecting hook): any unexpected error →
NOTHING on stdout (a wrong advisory in every session is worse than none), a diagnostic on stderr
(invisible to Claude by contract; surfaces only in hook debug output), exit 0 (exit 2 would render
a user-facing error notice for what is a best-effort advisory).

Silence rules (no-nag, all deliberate):
  - the global store is absent/empty            → silent (nothing to absorb)
  - this project's store holds no *.md          → silent (never-participated dirs must cost 0 —
    the plugin is installed user-wide; discovery is --staleness's job, not every session's)
  - state-file `beacon_snooze_until` in future  → silent (set on explicit user ask, per-store)
  - 0 missing AND 0 content-stale               → silent (in sync — the common case stays free)
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from memory_status import _parse_ts, est_tokens, slug_for, INDEX_CEILING_TOKENS  # noqa: E402
from sync_global import (GLOBAL, _body_hash, _index_line_cost, _pointer_line, _safe_read_text,  # noqa: E402
                         _store_gaps, global_facts)


def _cwd_from_stdin() -> str:
    """The hook's stdin JSON carries `cwd`; fall back to the process cwd (same value in the
    documented flow — the fallback covers a manual/debug invocation with no stdin)."""
    try:
        if not sys.stdin.isatty():
            data = json.load(sys.stdin)
            if isinstance(data, dict) and isinstance(data.get("cwd"), str) and data["cwd"]:
                return data["cwd"]
    except (ValueError, OSError):
        pass
    return os.getcwd()


def beacon_line(store: Path) -> str:
    """The at-most-one advisory line for `store` — '' when silent. PURE given the filesystem
    (smoke-pinned through both the silent and behind states)."""
    gfacts = global_facts()
    if not gfacts:
        return ""
    if not store.is_dir() or not any(store.glob("*.md")):
        return ""
    st: dict = {}
    raw = _safe_read_text(store / ".consolidation-state.json")
    if raw:
        try:
            _p = json.loads(raw)
            if isinstance(_p, dict):
                st = _p
        except (ValueError, TypeError):
            st = {}
    snooze = _parse_ts(str(st.get("beacon_snooze_until", "") or ""))
    if snooze is not None and snooze.timestamp() > datetime.now(timezone.utc).timestamp():
        return ""
    cached = st.get("stacks")
    stacks = {str(x) for x in cached} if isinstance(cached, list) else None
    body_hashes = {n: _body_hash(t) for n, _fm, t in gfacts}
    missing, stale = _store_gaps(store, stacks, gfacts, body_hashes)
    if not missing and not stale:
        return ""
    # the M1 projection: how many of the missing would the HARD CEILING hold on a pull?
    idx_text = _safe_read_text(store / "MEMORY.md") or ""
    running = est_tokens(idx_text)
    held = 0
    fm_by = {n: fm for n, fm, _t in gfacts}
    from sync_global import is_relevant  # local: keep module import surface identical to _store_gaps
    for n, fm, _t in gfacts:
        if not is_relevant(fm, stacks if stacks is not None else set()) or (store / f"{n}.md").exists():
            continue
        cost = est_tokens(_pointer_line(n, fm)) - _index_line_cost(idx_text, n)
        if running + cost > INDEX_CEILING_TOKENS:
            held += 1
        else:
            running += cost
    mdt = _parse_ts(str(st.get("timestamp", "") or ""))
    age = ""
    if mdt is not None:
        d = max(0.0, (datetime.now(timezone.utc).timestamp() - mdt.timestamp()) / 86400)
        age = f"; last consolidation {d:.1f}d ago"
    basis = "" if stacks is not None else " (user-global scope only — no stacks cache yet)"
    parts = []
    if missing:
        parts.append(f"{missing} shared global fact(s) are not yet mirrored here"
                     + (f" ({held} would be ceiling-held)" if held else ""))
    if stale:
        parts.append(f"{stale} mirror(s) carry outdated content")
    return ("Cross-project memory: " + " and ".join(parts) + basis + age
            + ". A consolidation pass (dream) on this project absorbs them.")


def main() -> int:
    try:
        line = beacon_line(Path.home() / ".claude" / "projects" / slug_for(Path(_cwd_from_stdin()).resolve()) / "memory")
        if line:
            print(line)
        return 0
    except Exception as e:  # noqa: BLE001 — the one place a broad catch is the CONTRACT:
        # a context-injecting, best-effort advisory must never surface a traceback into every
        # session start; diagnostics go to stderr (hook debug only), stdout stays EMPTY.
        print(f"session_beacon: suppressed {type(e).__name__}: {e}", file=sys.stderr)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
