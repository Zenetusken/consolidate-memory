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

# The gorgeous HTML/CSS/vanilla-JS lives in a sibling BUNDLED template (a real editable asset, shipped under
# plugins/consolidate-memory/scripts/). Found via __file__ so it resolves from the installed plugin cache
# regardless of ${CLAUDE_PLUGIN_ROOT}. A single placeholder is replaced (NOT str.format — CSS/JS braces).
_TEMPLATE = Path(__file__).parent / "dashboard.template.html"
_PLACEHOLDER = "/*__CM_DATA__*/"

INDEX_TOKEN_BUDGET = 1200       # mirrors memory_status.INDEX_TOKEN_BUDGET (the always-loaded MEMORY.md index)
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


def build_html(record: dict, history: list, generated_at: str) -> str:
    """Assemble the data payload + inject it into the bundled template. PURE w.r.t. its inputs (only reads
    the template) so a smoke test can exercise it + assert the embedded round-trip + the XSS escaping. The
    JS in the template reads `current`/`history`/`budgets` and renders everything client-side."""
    template = _TEMPLATE.read_text(encoding="utf-8")
    data = {
        "current": record if isinstance(record, dict) else {},
        "history": history if isinstance(history, list) else [],
        "generated_at": generated_at,
        "budgets": {"index": INDEX_TOKEN_BUDGET, "claude_md": CLAUDE_MD_TOKEN_BUDGET},
    }
    return template.replace(_PLACEHOLDER, _safe_embed(data))


def _default_out(record: dict) -> Path:
    """A stable, re-openable per-project temp path (no store pollution; the audit globs `*.md`, never this)."""
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
    ap = argparse.ArgumentParser(description="render the cycle record into a self-contained HTML dashboard")
    ap.add_argument("cycle", nargs="?", help="cycle-record JSON path (memory_status.py --seed + filled); omit with --latest")
    ap.add_argument("--store", help="the auto-memory dir (.consolidation-log.jsonl source for the longitudinal view)")
    ap.add_argument("--project", help="project dir → derive its auto-memory store via the slug (alternative to --store)")
    ap.add_argument("--latest", action="store_true", help="render the most recent LOGGED cycle from the store (no cycle arg)")
    ap.add_argument("--out", help="output HTML path (default: a per-project temp file)")
    ap.add_argument("--no-open", action="store_true", help="write the file but don't open a browser")
    args = ap.parse_args(argv)

    if not _TEMPLATE.exists():       # out-of-the-box guard: the bundled template must ship with the plugin
        print(f"render_html: bundled template missing at {_TEMPLATE} — is the plugin install complete?", file=sys.stderr)
        return 1

    store = _store_for(args.store, args.project)
    history = read_history(store)
    if args.latest:                  # cm report: no cycle.json — render the most recent logged pass
        if not history:
            print("render_html: no .consolidation-log entries in the store yet — run a dream first", file=sys.stderr)
            return 1
        record = history[-1]
    elif args.cycle:
        try:
            record = json.loads(Path(args.cycle).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, ValueError) as e:
            print(f"render_html: cannot read cycle record {args.cycle!r}: {e}", file=sys.stderr)
            return 1
    else:
        print("render_html: provide a cycle-record JSON path, or --latest with --store/--project", file=sys.stderr)
        return 2

    generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    html = build_html(record, history, generated_at)

    out = Path(args.out) if args.out else _default_out(record)
    out.write_text(html, encoding="utf-8")

    opened = False
    if not args.no_open:
        try:                          # headless-safe: a missing/loopback browser must NEVER crash a dream
            opened = webbrowser.open(out.resolve().as_uri())
        except Exception:             # noqa: BLE001 - the whole point is don't-crash-on-open
            opened = False
    print(f"dashboard → {out}" + ("" if opened else "  · open this file in a browser" if not args.no_open else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
