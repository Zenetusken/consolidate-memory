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


def _safe_embed(data: dict) -> str:
    """JSON safe to embed inside `<script type="application/json">`: escape `<` `>` `&` to their \\uXXXX
    forms. `JSON.parse` restores them; the HTML parser never sees a real `<`, so a memory fact containing
    `</script>` (or any markup) can't break out of the tag — the load-bearing XSS guard."""
    return (json.dumps(data, ensure_ascii=False)
            .replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026"))


def read_history(store: Path | None) -> list:
    """The accrued cycle records from `<store>/.consolidation-log.jsonl` — the longitudinal series. Robust:
    a malformed line is skipped (a corrupt log must not break the dashboard), a missing log → []."""
    if store is None:
        return []
    log = Path(store) / ".consolidation-log.jsonl"
    if not log.exists():
        return []
    out: list = []
    for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
        s = line.strip()
        if not s:
            continue
        try:
            out.append(json.loads(s))
        except (json.JSONDecodeError, ValueError):
            continue
    return out


_ARCHIVE_CAP = 120   # embed at most the latest N cycles (bounded HTML size); a VISIBLE note flags any truncation


def _marker(r: dict) -> tuple:
    """A dream's identity for dedup/selection. Timestamp is UNIQUE per dream; commit COLLIDES when dreams share a
    HEAD — so the (commit, timestamp) pair dedups and timestamp is the real key. Tolerates a non-dict `marker`
    (a corrupted log entry) so dedup/--select can't crash — mirrors the JS side's defensive accessor."""
    m = r.get("marker") if isinstance(r, dict) else None
    if not isinstance(m, dict):
        m = {}
    return (m.get("commit"), m.get("timestamp"))


def assemble_cycles(record: dict, history: list) -> tuple:
    """The archive series: all logged cycles (oldest-first) + the current `record` dedup-appended if it is newer
    than the last logged entry (so the latest dream shows even before --persist). Returns (capped_cycles, total)."""
    cycles = [c for c in history if isinstance(c, dict)] if isinstance(history, list) else []
    rec = record if isinstance(record, dict) else {}
    if rec and (not cycles or _marker(cycles[-1]) != _marker(rec)):
        cycles.append(rec)
    total = len(cycles)
    return (cycles[-_ARCHIVE_CAP:] if total > _ARCHIVE_CAP else cycles), total


def build_html(record: dict, history: list, generated_at: str, diffs: "dict | None" = None) -> str:
    """Embed the ARCHIVE (all logged cycles, capped) + the repo identity into the bundled template; the JS reads
    `cycles`/`project`/`budgets`/`diffs` and renders either the archive index or a single dream selected by URL
    `#sel=`. `diffs` (v0.1.32) maps a cycle's diff_key → its persisted memory diffs (the diff-modal); read by
    main() so build_html stays PURE w.r.t. inputs (a smoke test exercises it + asserts the embedded round-trip)."""
    template = _TEMPLATE.read_text(encoding="utf-8")
    cycles, total = assemble_cycles(record, history)
    rec = record if isinstance(record, dict) else {}
    project = (rec.get("project") or (cycles[-1].get("project") if cycles else "")) or "dream"
    # v0.1.44: attach the procedure-integrity verdict per cycle (single-source ms.procedure_integrity),
    # ONLY when it fires (lean payload) — the JS surfaces an escaped ⚠ panel + archive badge from
    # `_integrity`. A shallow copy carries it into the embedded series without mutating the source dicts.
    def _embed_integrity(c: object) -> object:
        if not isinstance(c, dict):
            return c
        ok, reason, severity = ms.procedure_integrity(c)
        return c if ok else {**c, "_integrity": {"severity": severity, "reason": reason}}
    cycles = [_embed_integrity(c) for c in cycles]
    data = {
        "cycles": cycles,
        "project": project,
        "generated_at": generated_at,
        "budgets": {"index": INDEX_TOKEN_BUDGET, "claude_md": CLAUDE_MD_TOKEN_BUDGET},
        "total": total,
        "cap": _ARCHIVE_CAP,
        "diffs": diffs if isinstance(diffs, dict) else {},
    }
    return template.replace(_PLACEHOLDER, _safe_embed(data))


def read_diffs(store: "Path | None", cycles: list) -> dict:
    """v0.1.32: load each embedded cycle's persisted diff sidecar (`dashboards/diffs/<diff_key>.json`), keyed by the
    SAME `diff_key` the capture used → the diff-modal payload. Best-effort: a missing/corrupt sidecar is skipped
    (legacy / pre-feature cycles simply have none, so their facts just aren't clickable)."""
    if store is None:
        return {}
    from memory_status import diff_key
    ddir = Path(store).parent / "dashboards" / "diffs"
    if not ddir.exists():
        return {}
    out: dict = {}
    for c in cycles:
        key = diff_key(c.get("marker") if isinstance(c, dict) else {})
        if key in out or not (ddir / (key + ".json")).exists():
            continue
        try:
            d = json.loads((ddir / (key + ".json")).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, ValueError):
            continue
        if isinstance(d, dict):
            out[key] = d
    return out


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
        from memory_status import slug_for   # DRY: the single slug rule
        return Path.home() / ".claude" / "projects" / slug_for(Path(project)) / "memory"
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
    html = build_html(record, history, generated_at, read_diffs(store, cycles))
    out = Path(args.out) if args.out else _default_out(record, store)
    out.write_text(html, encoding="utf-8")

    opened = False
    if not args.no_open:
        try:                          # headless-safe: a missing/loopback browser must NEVER crash a dream
            opened = webbrowser.open(out.resolve().as_uri() + frag)
        except Exception:             # noqa: BLE001 - the whole point is don't-crash-on-open
            opened = False
    print(f"dashboard → {out}{frag}" + ("" if opened else "  · open this file in a browser" if not args.no_open else ""))
    # v0.1.54: the WAKE cue — this archive render/open is the SKILL's pinned wake point ("after the
    # terminal clean render + archive open"), the LAST scripted step of a completing dream.
    _ui.dream_cue("the archive is open — WAKE now: *☀️ 2–5 italic lines*, full stop (v0.1.64: no "
                  "trailing 'Awake.' line), then the plain debrief, 📊 path last")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
