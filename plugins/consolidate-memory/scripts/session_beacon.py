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
  - unenrolled + store never participated       → silent (v0.4.8: the unenrolled advisory
    shares the never-participated gate above — a store that holds no fact pays nothing;
    a PARTICIPATING unenrolled store hears it until enrolled or snoozed)
  - state-file `beacon_snooze_until` in future  → silent (set on explicit user ask, per-store)
  - 0 missing AND 0 content-stale               → silent (in sync — the common case stays free)
"""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from memory_status import _parse_ts, est_tokens, INDEX_CEILING_TOKENS  # noqa: E402
from store_context import resolve_store  # noqa: E402 — native path via StoreContext (no subprocess)
from domain_policy import admit_cross_project  # noqa: E402
from sync_global import (_body_hash, _plan_pull, _pointer_line,  # noqa: E402
                         _safe_read_text, _store_gaps, is_relevant)


_HOOK_CACHE: dict | None = None


def _hook_from_stdin() -> dict:
    """SessionStart stdin JSON: cwd / session_id / transcript_path. Fail empty on error.

    Cached: stdin is a one-shot stream and both cwd + StoreContext need the same payload.
    """
    global _HOOK_CACHE
    if _HOOK_CACHE is not None:
        return _HOOK_CACHE
    try:
        if not sys.stdin.isatty():
            data = json.load(sys.stdin)
            if isinstance(data, dict):
                _HOOK_CACHE = data
                return _HOOK_CACHE
    except (ValueError, OSError):
        pass
    _HOOK_CACHE = {}
    return _HOOK_CACHE


def _cwd_from_stdin() -> str:
    """The hook's stdin JSON carries `cwd`; fall back to the process cwd (same value in the
    documented flow — the fallback covers a manual/debug invocation with no stdin)."""
    data = _hook_from_stdin()
    if isinstance(data.get("cwd"), str) and data["cwd"]:
        return data["cwd"]
    return os.getcwd()


def _unenrolled_advisory(ctx) -> int:
    """The unenrolled form of the behind-advisory (v0.4.8 cm-commands spec §3): an
    unenrolled project is the strongest case of "behind" — the user's enrolled
    domain(s) hold facts the store cannot reach. Fires only for a PARTICIPATING
    store (holds ≥1 *.md — beacon_line's own never-participated definition: the
    snooze stamp refuses a store with no state file, so an unparticipating store
    could never quiet the line) and derives N by pure SQL from the REGISTRY (an
    unenrolled ctx resolves domain_id='unknown', so its canonical_domain_dir is
    the wrong dir — no filesystem walk, no DB-name-to-path surface). Repeats
    until enrolled (the behind-advisory's semantics); beacon_snooze_until quiets
    it; silent on any failure (the no-failure-masking posture)."""
    store = ctx.native_memory_dir
    if not store.is_dir() or not any(store.glob("*.md")):
        return 0
    try:
        raw = _safe_read_text(store / ".consolidation-state.json")
        if raw:
            _st = json.loads(raw)
            if isinstance(_st, dict):
                snooze = _parse_ts(str(_st.get("beacon_snooze_until", "") or ""))
                if snooze is not None and snooze.timestamp() > datetime.now(timezone.utc).timestamp():
                    return 0
    except (ValueError, OSError):
        pass
    n = 0
    try:
        from control_plane import connect_if_exists, db_path
        conn = connect_if_exists(db_path(ctx))
        if conn is None:
            return 0
        try:
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM facts WHERE domain_id IN "
                "(SELECT DISTINCT domain_id FROM projects "
                " WHERE status='enrolled' AND domain_id!='unknown') "
                "AND status='active'").fetchone()
        finally:
            conn.close()
        n = int(row["n"]) if row is not None else 0
    except Exception:
        return 0
    if n <= 0:
        return 0
    print(f"Cross-project memory: {n} shared fact(s) not reachable here — "
          "this project is unenrolled; /cm-domain can enroll it.")
    return 0


def beacon_line(store: Path, *, domain_id: str = "unknown",
                migration_mode: str = "dual-read",
                gfacts: list | None = None,
                body_hashes: "dict | None" = None) -> str:
    """The at-most-one advisory line for `store` — '' when silent. PURE given the filesystem
    (smoke-pinned through both the silent and behind states)."""
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
    if body_hashes is None:
        body_hashes = {n: _body_hash(t) for n, _fm, t in gfacts if t}
    for _n, _fm, _t in gfacts:
        if not _t:
            body_hashes.setdefault(_n, "")
    missing, stale = _store_gaps(
        store, stacks, gfacts, body_hashes,
        domain_id=domain_id, migration_mode=migration_mode)
    if not missing and not stale:
        return ""
    # The M1 projection: how many of the missing would the HARD CEILING hold on a pull?
    # PR-#94 review F1 (verified divergence fixture): a hand-rolled MISSING-only loop OMITTED the
    # STALE-refresh deltas _plan_pull counts, so the beacon advertised a pull the ceiling would
    # refuse. One accounting replay, by law: build the SAME items shape and call _plan_pull.
    # STALE stands in as POINTER DRIFT (real index line ≠ derived pointer): a description-drifted
    # mirror carries exactly the refresh delta a real --pull applies; body-only staleness is
    # delta-0 (nothing to count). Reach note: a hand-edited index line under a genuinely in-sync
    # mirror counts a phantom delta — conservative direction (fewer advertised as absorbable).
    idx_text = _safe_read_text(store / "MEMORY.md") or ""
    # PR-#94 review F4: build the anchor→cost map ONCE — per-fact _index_line_cost re-split the
    # whole index every call (O(relevant × index_bytes); measured 4.5s only at a pathological
    # 500-fact × 4MB fixture, sub-ms at any ceiling-governed size — hoisted regardless, so the
    # bound is O(relevant + index_bytes) and the spec can state it).
    line_cost: dict = {}
    for _ln in idx_text.splitlines():
        _m = re.search(r"\]\(([^)]+)\.md\)", _ln)
        if _m and _m.group(1) not in line_cost:
            line_cost[_m.group(1)] = est_tokens(_ln)
    items = []
    for n, fm, _t in gfacts:
        if not is_relevant(fm, stacks if stacks is not None else set()):
            continue
        if not admit_cross_project(domain_id, fm, migration_mode=migration_mode):
            continue
        cost_new = est_tokens(_pointer_line(n, fm))
        cost_old = line_cost.get(n, 0)
        if not (store / f"{n}.md").exists():
            items.append((n, "MISSING", cost_new, cost_old))
        elif cost_old and cost_new != cost_old:
            items.append((n, "STALE-mirror", cost_new, cost_old))
    held = len(_plan_pull(items, est_tokens(idx_text), False, budget=INDEX_CEILING_TOKENS)["held"])
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
            + ". A consolidation pass (dream) on this project absorbs them; asking to snooze "
            "this reminder quiets it for this store.")


def main() -> int:
    try:
        hook = _hook_from_stdin()
        _cwd = hook.get("cwd")
        cwd = _cwd if isinstance(_cwd, str) and _cwd else os.getcwd()
        ctx = resolve_store(Path(str(cwd)).resolve(), hook=hook)
        if not ctx.auto_memory_enabled:
            return 0  # disabled auto-memory: absence is not drift (ADR 002)
        if not getattr(ctx, "cross_project_allowed", False):
            # v0.4.8 (cm-commands spec §3): unenrolled no longer means silent —
            # a participating store hears the unenrolled advisory while the
            # user's domain holds facts it cannot reach.
            return _unenrolled_advisory(ctx)
        from control_plane import migration_mode_readonly
        from sync_global import iter_admissible_facts
        _bh: "dict | None" = None
        try:
            # review fix: ensure() REBUILDS + WRITES the manifest when absent or
            # unparseable — inside the 2s hook budget, against the beacon's own
            # "never writes" contract. load() is the read-only form; a missing or
            # corrupt manifest degrades to the full-read fallback below, never a write.
            from facts_manifest import load as _fm_load_b
            _man_rows_b, _ = _fm_load_b(ctx.canonical_domain_dir,
                                        ctx.plugin_data_dir)
            if _man_rows_b:
                _bh = {n: (r.get("body_hash") or "")
                       for n, r in _man_rows_b.items()}
        except Exception:
            _bh = None
        _gf_b = iter_admissible_facts(ctx)
        if _bh is not None:
            # facts NEW since the manifest build are served by the full path
            # (text present) — fill their hashes so _store_gaps never KeyErrors.
            for _n_b, _fm_b, _t_b in _gf_b:
                if _n_b not in _bh and _t_b:
                    _bh[_n_b] = _body_hash(_t_b)
        line = beacon_line(
            ctx.native_memory_dir,
            domain_id=ctx.domain_id,
            migration_mode=migration_mode_readonly(ctx),
            gfacts=_gf_b,
            body_hashes=_bh,
        )
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
