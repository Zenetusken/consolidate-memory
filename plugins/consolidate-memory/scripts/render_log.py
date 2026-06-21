#!/usr/bin/env python3
"""v0.1.34: the LEAN log-audit view — the 3rd renderer of the SAME cycle log.

ASCII dashboard (`render_dashboard`) = ONE cycle · HTML archive (`render_html`) = all cycles, rich · THIS = all
cycles, lean-tabular. `cm log [DIR] [-n N] [--json]` prints a dense per-dream table (or the raw records) over
`<store>/.consolidation-log.jsonl`, so a maintainer can audit any project's dream history without hand-parsing
JSONL or opening a browser. Reuses `read_history`/`_store_for` (render_html — the SAME log reader + slug
resolution `cm report` uses, so the two agree on which store) + `_ui` (color/rule vocabulary) — coherent + DRY.

Stdlib-only; ships IN the plugin (cm execs it by path from $S; the sibling imports below resolve only from the
scripts dir). The SKILL never calls it — it's the maintainer audit lens, fleet-reachable via the PATH-installed cm.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter

import _ui  # sibling: shared visual vocabulary (color / rule / width)
from render_html import _store_for, read_history  # the SAME log reader + slug resolution cm report uses


def _d(rec: dict, *path: str) -> object:
    """Defensive nested get — a legacy/sparse record yields None (never a KeyError)."""
    cur: object = rec
    for k in path:
        cur = cur.get(k) if isinstance(cur, dict) else None
    return cur


def _n(x: object) -> int:
    """Defensive int via the shared _ui.num (object → float → int; bad input → 0)."""
    return int(_ui.num(x))


def _row(rec: dict) -> list:
    """One dense audit row from a cycle record — all fields defensively read (legacy-safe)."""
    when = str(_d(rec, "marker", "timestamp") or "—").replace("T", " ")[:16]
    commit = str(_d(rec, "marker", "commit") or "—")[:10]
    rigor = str(_d(rec, "rigor", "applied") or "—")
    ib, ia = _n(_d(rec, "budget", "index", "before_tokens")), _n(_d(rec, "budget", "index", "after_tokens"))
    rb, ra = _n(_d(rec, "budget", "recall_facts", "before")), _n(_d(rec, "budget", "recall_facts", "after"))
    ents = [e for e in (rec.get("entries") or []) if isinstance(e, dict)]
    code = " ".join(f"{n}{a}" for a, n in sorted(Counter(str(e.get("action", "?"))[:1] for e in ents).items())) or "—"
    cr, mo, de = (_n(_d(rec, "audit", "memory", "created")), _n(_d(rec, "audit", "memory", "modified")),
                  _n(_d(rec, "audit", "memory", "deleted")))
    return [when, commit, rigor, f"{ia} ({ia - ib:+d})", f"{ra} ({ra - rb:+d})", code, f"+{cr} ~{mo} -{de}"]


_HEAD = ["WHEN", "MARKER", "RIGOR", "INDEX (Δ)", "RECALL (Δ)", "ENTRIES", "AUDIT"]


def render(recent: list, total: int, project: str) -> str:
    """Pure: a cycle-record list (newest-first) → the table string. Exercised by the smoke test."""
    rows = [_row(r) for r in recent]
    w = [max(len(_HEAD[i]), max((len(r[i]) for r in rows), default=0)) for i in range(len(_HEAD))]

    def fmt(cells: list) -> str:
        return "  ".join(str(c).ljust(w[i]) for i, c in enumerate(cells))

    out = [_ui.rule(),
           "  " + _ui.c(f"✦ DREAM LOG · {project} · {len(recent)} of {total} shown", "cyan"),
           _ui.rule(),
           "  " + _ui.c(fmt(_HEAD), "dim")]
    out += ["  " + fmt(r) for r in rows]
    return "\n".join(out)


def main(argv: list) -> int:
    ap = argparse.ArgumentParser(description="lean per-dream audit table over a project's .consolidation-log.jsonl (the 3rd log view)")
    ap.add_argument("--store", help="the auto-memory dir (the .consolidation-log.jsonl source)")
    ap.add_argument("--project", help="project dir → derive its store via the slug (default: CWD)")
    ap.add_argument("-n", type=int, default=12, help="show the last N dreams (default 12; 0 = all)")
    ap.add_argument("--json", action="store_true", help="emit the last N raw cycle records as a JSON array (for piping/jq)")
    args = ap.parse_args(argv)

    store = _store_for(args.store, args.project if args.project is not None else ".")
    hist = read_history(store)                                   # oldest-first; malformed lines already skipped
    recent = (hist[-args.n:] if args.n > 0 else hist)[::-1]      # newest-first, capped AFTER the sort

    if args.json:
        print(json.dumps(recent, indent=2))
        return 0
    if not recent:
        print(f"cm log: no dreams logged yet ({store or 'no store resolved'})", file=sys.stderr)
        return 0

    _ui.set_modes(color=_ui.color_enabled(argv, sys.stdout), ascii="--ascii" in argv, width=_ui.resolve_width(argv, sys.stdout))
    project = str(recent[0].get("project") or (store.parent.name if store else "?"))
    print(_ui.ascii_translate(render(recent, len(hist), project)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
