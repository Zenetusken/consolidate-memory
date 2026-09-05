#!/usr/bin/env python3
"""v0.1.28: render the cycle record + the longitudinal `.consolidation-log.jsonl` into a self-contained,
ZERO-dependency HTML observability dashboard ("dream telemetry") and open it in the browser.

The HTML sibling of `render_dashboard.py`'s ASCII output — the SAME cycle-record contract, a rich visual
presentation (one contract, two renderers). Stdlib only; the template is a BUNDLED asset found via `__file__`
so it works from the marketplace install cache; the data is embedded inline (XSS / `</script>`-break-out-proof)
so the HTML is fully self-contained + offline; the browser open is headless-safe (falls back to printing the
path, never crashes a dream).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import webbrowser
from datetime import datetime, timezone
from pathlib import Path

import _ui  # sibling: dream_cue (v0.1.54 — the WAKE cue fires HERE, the arc's true terminal boundary)
import memory_status as ms  # sibling: the SINGLE-SOURCE procedure_integrity predicate (v0.1.44) — derive, don't duplicate

# The gorgeous HTML/CSS/vanilla-JS lives in a sibling BUNDLED template (a real editable asset, shipped under
# plugins/consolidate-memory/scripts/). Found via __file__ so it resolves from the installed plugin cache
# regardless of ${CLAUDE_PLUGIN_ROOT}. A single placeholder is replaced (NOT str.format — CSS/JS braces).
_TEMPLATE = Path(__file__).parent / "dashboard.template.html"
_PLACEHOLDER = "/*__CM_DATA__*/"

INDEX_TOKEN_BUDGET = 1500       # mirrors memory_status.INDEX_TOKEN_BUDGET (the always-loaded MEMORY.md index)
CLAUDE_MD_TOKEN_BUDGET = 4000   # mirrors memory_status.CLAUDE_MD_TOKEN_BUDGET (the root CLAUDE.md)
# v0.1.66: a live REFERENCE, not a hardcoded copy like the two constants above — `ms` is already
# imported in this module (unlike when INDEX_TOKEN_BUDGET/CLAUDE_MD_TOKEN_BUDGET were first added), so
# a literal mirror here would be a needless, structurally-avoidable drift risk a code-review workflow
# flagged (2026-07-04): if INDEX_CEILING_FRACTION is ever retuned, this stays correct with no smoke pin
# to remember updating by hand.
INDEX_CEILING_TOKENS = ms.INDEX_CEILING_TOKENS


def _safe_embed(data: dict) -> str:
    """JSON safe to embed inside `<script type="application/json">`: escape `<` `>` `&` to their \\uXXXX
    forms. `JSON.parse` restores them; the HTML parser never sees a real `<`, so a memory fact containing
    `</script>` (or any markup) can't break out of the tag — the load-bearing XSS guard."""
    return (json.dumps(data, ensure_ascii=False)
            .replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026"))


def read_history(store: Path | None) -> list:
    """The accrued cycle records from `<store>/.consolidation-log.jsonl` — the longitudinal series. Robust:
    a malformed line is skipped (a corrupt log must not break the dashboard), a missing log → [].
    v0.1.67 (Phase C): DELEGATES to ms.iter_cycle_log — the shared reader usage_history also uses, so the
    log line-parse has ONE definition (the single-source rule; a smoke pin guards the delegation).
    tail=None: render surfaces read ALL cycles, unchanged (_ARCHIVE_CAP bounds the embed downstream)."""
    if store is None:
        return []
    return ms.iter_store_cycle_log(Path(store), tail=None)


_ARCHIVE_CAP = 120   # embed at most the latest N cycles (bounded HTML size); a VISIBLE note flags any truncation
_DIFF_EMBED_CAP = 20   # P4 (v0.4.2): embed diff sidecars for only the newest N cycles — the modal
                       # is reachable from the newest dreams; the oldest 100 sidecars were pure weight

# P4 (v0.4.2 archive embed budget): the TOP-LEVEL record keys the bundled template's JS reads
# (audited against every CUR.* / g(CUR, ...) / g(c, ...) / loop-var read in dashboard.template.html).
# Full subtrees are kept — the v0.1.28 round-trip pin asserts budget.recall_facts.after survives
# embedding even though the JS never reads it. Everything else (registrar payloads, per-phase
# working data) is rendered nowhere and was most of a 120-cycle archive's weight. A smoke pin
# enforces this whitelist — the template must not grow an unlisted read.
_EMBED_KEYS = (
    "audit", "budget", "cross_project", "demotion", "distill", "dream",
    "entries", "health", "identity", "maintenance", "marker", "network",
    "outcome", "preflight", "project", "remediation", "rigor", "scope", "session",
    "usage", "verification", "workflow_proposals",
)


def _embed_cycle(c: object) -> object:
    """Trim a cycle record to _EMBED_KEYS (full subtrees). Non-dict entries pass through."""
    if not isinstance(c, dict):
        return c
    return {k: v for k, v in c.items() if k in _EMBED_KEYS}


def _marker(r: dict) -> tuple:
    """A dream's identity for dedup/selection. Timestamp is UNIQUE per dream; commit COLLIDES when dreams share a
    HEAD — so the (commit, timestamp) pair dedups and timestamp is the real key. Tolerates a non-dict `marker`
    (a corrupted log entry) so dedup/--select can't crash — mirrors the JS side's defensive accessor."""
    m = r.get("marker") if isinstance(r, dict) else None
    if not isinstance(m, dict):
        m = {}
    return (m.get("commit"), m.get("timestamp"))


def _same_dream(a: dict, b: dict) -> bool:
    """C2: dream identity for dedup. Same commit AND: both timestamps non-empty → equal stamps;
    EITHER timestamp empty → session equality when both carry a session (the same HEAD can hold
    two dreams, one unstamped — the archive already shows same-commit collisions, they must NOT
    collapse); either side lacks a session → raw _marker equality (an empty ts never equals a
    stamped one → keep both rows, conservative)."""
    ca, ta = _marker(a)
    cb, tb = _marker(b)
    if ca != cb:
        return False
    if str(ta or "").strip() and str(tb or "").strip():
        return ta == tb
    sa = str(a.get("session") or "").strip() if isinstance(a, dict) else ""
    sb = str(b.get("session") or "").strip() if isinstance(b, dict) else ""
    if sa and sb:
        return sa == sb
    return ta == tb


def _fill_timestamp(rec: dict, by_commit: dict, prev_ts: str) -> dict:
    """C1: an empty marker.timestamp must not embed (blank archive date, inverted 'newest' sort,
    dangling footer, `__nots` sidecar keys). Fill from (1) a same-commit history stamp whose SESSION
    matches, else (2) `prev_ts` — the chain-walk carrying the nearest earlier non-empty stamp so
    adjacent empty rows both fill. Returns a COPY when it fills — the embedded series never mutates
    caller dicts. No fill source → unchanged (the JS renders '—' and sorts the row last)."""
    m = rec.get("marker") if isinstance(rec, dict) else None
    if not isinstance(m, dict):
        return rec
    if str(m.get("timestamp") or "").strip():
        return rec
    ses = str(rec.get("session") or "").strip()
    fill = by_commit.get((str(m.get("commit") or "").strip(), ses), "") \
        or str(m.get("before_timestamp") or "").strip() or prev_ts
    if not fill:
        return rec
    return {**rec, "marker": {**m, "timestamp": fill}}


def assemble_cycles(record: dict, history: list) -> tuple:
    """The archive series: all logged cycles (oldest-first) + the current `record` dedup-appended if it is newer
    than the last logged entry (so the latest dream shows even before --persist). Returns (capped_cycles, total).
    v0.4.1-fix (C1/C2): DEDUP FIRST on RAW markers (a fill-then-dedup cascade could make a filled legacy row
    marker-identical to its neighbor and collapse two dreams), then fill empty timestamps for the survivors;
    `_same_dream` treats commit-match with either-empty-ts + matching session as the same dream (the stale
    unstamped --cycle file vs the repaired log line must never double-embed), preferring the stamped copy."""
    cycles = [c for c in history if isinstance(c, dict)] if isinstance(history, list) else []
    rec = record if isinstance(record, dict) else {}
    if rec and (not cycles or not _same_dream(cycles[-1], rec)):
        cycles.append(rec)
    elif rec and cycles:
        _lts = str(_marker(cycles[-1])[1] or "").strip()
        _rts = str(_marker(rec)[1] or "").strip()
        if _lts and _lts == _rts:
            cycles[-1] = rec    # same dream, same stamp — the current file is the fresher expression
                                # (a post-persist enrichment like the injected network block surfaces)
        elif not _lts and _rts:
            cycles[-1] = rec    # same dream: the stamped copy wins
    by_commit: dict = {}
    for c in cycles:
        m = c.get("marker") if isinstance(c, dict) else None
        if isinstance(m, dict):
            ts = str(m.get("timestamp") or "").strip()
            cm = str(m.get("commit") or "").strip()
            if ts and cm and (cm, str(c.get("session") or "").strip()) not in by_commit:
                by_commit[(cm, str(c.get("session") or "").strip())] = ts
    out: list = []
    prev_ts = ""
    for c in cycles:
        filled = _fill_timestamp(c, by_commit, prev_ts)
        out.append(filled)
        _m_out = filled.get("marker")
        if isinstance(_m_out, dict):    # a string marker (corrupted entry) never advances the walk
            prev_ts = str(_m_out.get("timestamp") or "").strip() or prev_ts
    total = len(out)
    return (out[-_ARCHIVE_CAP:] if total > _ARCHIVE_CAP else out), total


def build_html(record: dict, history: list, generated_at: str, diffs: "dict | None" = None,
               identity: "dict | None" = None,
               cycles: "list | None" = None, total: "int | None" = None) -> str:
    """Embed the ARCHIVE (all logged cycles, capped) + the repo identity into the bundled template; the JS reads
    `cycles`/`project`/`budgets`/`diffs`/`identity` and renders either the archive index or a single dream selected by URL
    `#sel=`. `diffs` (v0.1.32) maps a cycle's diff_key → its persisted memory diffs (the diff-modal); read by
    main() so build_html stays PURE w.r.t. inputs (a smoke test exercises it + asserts the embedded round-trip).
    `identity` (v0.3.0) is the LIVE StoreContext snapshot at render — the archive masthead; per-cycle
    `identity` on a record (seeded Phase 0) is this-pass truth when present.
    `cycles`/`total` (P4, v0.4.2): main() assembles the series ONCE (it needs the same list for
    read_diffs + #sel) — pass it in to skip the re-assembly; omitted, this assembles as before."""
    template = _TEMPLATE.read_text(encoding="utf-8")
    if cycles is None:
        cycles, total = assemble_cycles(record, history)
    else:
        total = len(cycles) if total is None else total
    rec = record if isinstance(record, dict) else {}
    project = (rec.get("project") or (cycles[-1].get("project") if cycles else "")) or "dream"
    # v0.1.44: attach the procedure-integrity verdict per cycle (single-source ms.procedure_integrity),
    # ONLY when it fires (lean payload) — the JS surfaces an escaped ⚠ panel + archive badge from
    # `_integrity`. A shallow copy carries it into the embedded series without mutating the source dicts.
    def _embed_integrity(c: object) -> object:
        if not isinstance(c, dict):
            return c
        # L4 (v0.4.2): the single-source outcome label rides the embed (the template's
        # outcomeOf prefers it; the JS ladder stays as the legacy fallback)
        c = {**c, "_outcome": ms.outcome_of(c)}
        ok, reason, severity = ms.procedure_integrity(c)
        return c if ok else {**c, "_integrity": {"severity": severity, "reason": reason}}
    # P4: trim to the template's read-whitelist FIRST, then stamp integrity (which is itself rendered).
    cycles = [_embed_integrity(_embed_cycle(c)) for c in cycles]
    data = {
        "cycles": cycles,
        "project": project,
        "generated_at": generated_at,
        "budgets": {"index": INDEX_TOKEN_BUDGET, "claude_md": CLAUDE_MD_TOKEN_BUDGET,
                    "index_ceiling": INDEX_CEILING_TOKENS,   # v0.1.66 (Phase B): the hard ceiling, for the meter
                    "hook_warn": ms.HOOK_TOKEN_WARN,        # v0.3.0: fat-hook threshold, live (not a hardcoded copy)
                    "cliff_near": int(ms.CLIFF_NEAR_FRACTION * 100)},
        "total": total,
        "cap": _ARCHIVE_CAP,
        "diffs": diffs if isinstance(diffs, dict) else {},
        "identity": identity if isinstance(identity, dict) else {},
    }
    return template.replace(_PLACEHOLDER, _safe_embed(data))


def read_diffs(store: "Path | None", cycles: list) -> dict:
    """v0.1.32: load each embedded cycle's persisted diff sidecar (`dashboards/diffs/<diff_key>.json`), keyed by the
    SAME `diff_key` the capture used → the diff-modal payload. Best-effort: a missing/corrupt sidecar is skipped
    (legacy / pre-feature cycles simply have none, so their facts just aren't clickable).
    P4 (v0.4.2): capped to the newest _DIFF_EMBED_CAP cycles — the oldest sidecars were embedded
    but only reachable from dreams at the archive's tail."""
    if store is None:
        return {}
    from memory_status import diff_key
    ddir = Path(store).parent / "dashboards" / "diffs"
    if not ddir.exists():
        return {}
    if len(cycles) > _DIFF_EMBED_CAP:
        cycles = cycles[-_DIFF_EMBED_CAP:]
    out: dict = {}
    for c in cycles:
        marker = c.get("marker") if isinstance(c, dict) else {}
        session = str(c.get("session", "")) if isinstance(c, dict) else ""
        # probe the session-suffixed key (post-fix sidecars) AND the legacy unsuffixed base (pre-fix
        # sidecars must keep resolving — the alias maps both keys to the same payload). v0.4.1-fix:
        # filled cycles flip legacy UNSTAMPED keys (`__nots`) to the filled stamp — probe the raw
        # `commit__nots` forms too and register the payload under EVERY probed key, or an old
        # unstamped sidecar's modal silently orphans.
        keys = [diff_key(marker, session), diff_key(marker)]
        if isinstance(marker, dict) and str(marker.get("commit") or "").strip():
            _raw = {"commit": marker.get("commit"), "timestamp": ""}
            keys += [diff_key(_raw, session), diff_key(_raw)]
        for key in keys:
            if key in out or not (ddir / (key + ".json")).exists():
                continue
            try:
                d = json.loads((ddir / (key + ".json")).read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError, ValueError):
                continue
            if isinstance(d, dict):
                for alias in keys:    # register under EVERY probed key — the JS lookup computes the
                    out[alias] = d    # filled key while legacy lookups use the raw __nots form
                break
    return out


_OPEN_MARKER_NAME = ".last-open"
_OPEN_WINDOW_S = 180.0    # one open per (archive, anchor) per 3 minutes — kills the repeated-tab pop, keeps deliberate re-opens


def _open_recent(out: Path, frag: str, now_ts: float, marker_dir: Path,
                 window_s: float = _OPEN_WINDOW_S) -> bool:
    """RC-89/n4: was this (archive, anchor) opened within the window? PURE READ — a FAILED
    webbrowser.open must never have written the marker, or the next attempt is suppressed.

    v0.4.13 hotfix (the repeated-window incident): ALSO suppress on a GLOBAL
    per-archive key (any anchor). The per-anchor key alone could not stop a
    re-render loop whose anchor CHANGES each iteration (--latest while the log
    grows, or a Phase-5 retry after each persist-gate failure) — every
    iteration passed the exact-key check and opened a NEW browser window,
    ~5s apart, indefinitely. The global key bounds the class: at most one
    window per archive per window_s, whatever the anchor. The cost is
    deliberate --select re-opens within 3 minutes of a prior open — acceptable
    beside unbounded window spawning; the kill-switch below is the escape."""
    marker = marker_dir / _OPEN_MARKER_NAME
    key = f"{out.resolve()}::{frag}"
    gkey = f"{out.resolve()}::*"
    try:
        prev = json.loads(marker.read_text(encoding="utf-8"))
        if isinstance(prev, dict) and now_ts - float(prev.get("at", 0)) < window_s:
            if prev.get("key") == key or prev.get("gkey") == gkey:
                return True
    except (OSError, json.JSONDecodeError, ValueError):
        pass
    return False


def _mark_open(out: Path, frag: str, now_ts: float, marker_dir: Path) -> None:
    """RC-89/n4: record a SUCCESSFUL open (called only after webbrowser.open returned truthy).
    Best-effort — any failure = the next render just tries again."""
    try:
        marker_dir.mkdir(parents=True, exist_ok=True)
        (marker_dir / _OPEN_MARKER_NAME).write_text(
            json.dumps({"key": f"{out.resolve()}::{frag}",
                        "gkey": f"{out.resolve()}::*", "at": now_ts}), encoding="utf-8")
    except OSError:
        pass


def _default_out(record: dict, store: "Path | None") -> Path:
    """The stable per-repo output: `<store>/../dashboards/index.html` (so the dream AND `cm report` write the SAME
    revisitable file), else a per-project temp file. Never the memory store itself (that's facts only)."""
    if store is not None:
        d = Path(store).parent / "dashboards"
        d.mkdir(parents=True, exist_ok=True)
        return d / "index.html"
    proj = str(record.get("project", "dream")) if isinstance(record, dict) else "dream"
    safe = "".join(c if c.isalnum() or c in "-_" else "-" for c in proj) or "dream"
    return Path(tempfile.gettempdir()) / f"cm-dashboard-{safe}.html"


def _store_for(store: str | None, project: str | None) -> Path | None:
    """Resolve the auto-memory store: explicit --store, else derive it from --project via the canonical slug
    (the one place that rule lives — imported from memory_status so cm report and the dream agree)."""
    if store:
        return Path(store)
    if project:
        from memory_status import project_memory_dir   # DRY: StoreContext, not a hard-coded slug path
        return project_memory_dir(Path(project))
    return None


def main(argv: list) -> int:
    ap = argparse.ArgumentParser(description="render the per-repo dream ARCHIVE (index + dashboards) as one self-contained HTML")
    ap.add_argument("cycle", nargs="?", help="cycle-record JSON path (memory_status.py --seed + filled); omit to render from the log")
    ap.add_argument("--store", help="the auto-memory dir (.consolidation-log.jsonl source — the archive series)")
    ap.add_argument("--project", help="project dir → derive its auto-memory store via the slug (alternative to --store)")
    ap.add_argument("--latest", action="store_true", help="open the most recent dream's dashboard (the post-dream payoff)")
    ap.add_argument("--select", help="open the dream whose marker commit starts with this hash (latest on collision)")
    ap.add_argument("--out", help="output HTML path (default: <store>/../dashboards/index.html, else a temp file)")
    ap.add_argument("--no-open", action="store_true", help="write the file but don't open a browser")
    args = ap.parse_args(argv)

    if not _TEMPLATE.exists():       # out-of-the-box guard: the bundled template must ship with the plugin
        print(f"render_html: bundled template missing at {_TEMPLATE} — is the plugin install complete?", file=sys.stderr)
        return 1

    store = _store_for(args.store, args.project)
    live_identity: dict = {}
    try:
        from store_context import (identity_snapshot as _id_html,
                                   resolve_store as _rs_html,
                                   warn_unenrolled_share as _w_html)
        _proj = Path(args.project).resolve() if args.project else Path.cwd()
        _ctx_html = _rs_html(_proj)
        _w_html(_ctx_html)
        live_identity = _id_html(_ctx_html)
    except Exception:
        pass
    history = read_history(store)
    record: dict = {}
    if args.cycle:
        try:
            record = json.loads(Path(args.cycle).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, ValueError) as e:
            print(f"render_html: cannot read cycle record {args.cycle!r}: {e}", file=sys.stderr)
            return 1

    cycles, _total = assemble_cycles(record, history)
    if not cycles:
        print("render_html: no dreams to render — run a dream first (no cycle given + an empty .consolidation-log)", file=sys.stderr)
        return 1

    # which view to OPEN: a specific dream (#sel=i) or the archive index (no fragment). The JS reads #sel= on load.
    frag = ""
    if args.select:
        matches = [i for i, c in enumerate(cycles) if str(_marker(c)[0] or "").startswith(args.select)]   # _marker guards a non-dict marker
        if not matches:
            print(f"render_html: no embedded dream matches hash {args.select!r} (may be older than the latest {_ARCHIVE_CAP})", file=sys.stderr)
            return 1
        frag = f"#sel={matches[-1]}"          # cycles are oldest-first → the last match is the most recent timestamp
    elif args.latest:
        frag = f"#sel={len(cycles) - 1}"

    generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    # P4: the series is assembled ONCE here and passed through (build_html and read_diffs
    # both consume the same list — no re-assembly, no re-dedup).
    html = build_html(record, history, generated_at, read_diffs(store, cycles),
                      identity=live_identity, cycles=cycles, total=_total)
    out = Path(args.out) if args.out else _default_out(record, store)
    out.write_text(html, encoding="utf-8")

    opened = False
    # v0.4.13 hotfix: CM_NO_OPEN=1 is the operator kill-switch — a
    # headless/loop-bound render must NEVER open a browser window.
    if not args.no_open and not os.environ.get("CM_NO_OPEN"):
        try:                          # headless-safe: a missing/loopback browser must NEVER crash a dream
            _now = datetime.now(timezone.utc).timestamp()
            if _open_recent(out, frag, _now, out.parent):
                opened = True         # v0.1.89: this archive anchor is ALREADY open (back-to-back re-render) — not a failure
            else:
                opened = bool(webbrowser.open(out.resolve().as_uri() + frag))
                if opened:            # n4: mark AFTER a successful open — a failed headless open must
                    _mark_open(out, frag, _now, out.parent)   # never suppress the next attempt for the window
        except Exception:             # noqa: BLE001 - the whole point is don't-crash-on-open
            opened = False
    print(f"dashboard → {out}{frag}" + ("" if opened else "  · open this file in a browser" if not args.no_open else ""))
    # v0.1.54: the WAKE cue — this archive render/open is the SKILL's pinned wake point ("after the
    # terminal clean render + archive open"), the LAST scripted step of a completing dream.
    # v0.4.1 (D1): gated on arc completeness — waking over a short arc would perform the bookend
    # the gate just refused; backfill the beats first, then this cue says WAKE.
    arc_ok, arc_reason = ms.arc_completeness(record)
    if arc_ok:
        _ui.dream_cue("the archive is open — WAKE now: *☀️ 2–5 italic lines*, full stop (v0.1.64: no "
                      "trailing 'Awake.' line), then the plain debrief, 📊 path last")
    else:
        _ui.dream_cue(f"the archive is open but the arc is incomplete ({arc_reason}) — backfill "
                      "the missing beats and re-render before waking")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
