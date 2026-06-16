#!/usr/bin/env python3
"""Render a consolidate-memory CYCLE RECORD (JSON) into a consistent dashboard.

The skill workflow accumulates a small JSON record of what the pass actually did
(see SKILL.md "Output: the cycle record"); this script renders it deterministically
so the report has a fixed skeleton but data-driven content. Sections with no data
collapse to "(none)". The outcome banner is derived from the write counts, so the
headline reflects the cycle — a no-op pass and a heavy pass look different at a glance.

Usage: python3 render_dashboard.py CYCLE_RECORD.json   (or pipe JSON on stdin)
"""

from __future__ import annotations

import json
import sys

W = 66  # dashboard inner width

# action -> (glyph, label) ; ordering controls display order
_ACTIONS = {
    "added": ("+", "added"),
    "corrected": ("~", "corrected"),
    "deleted": ("-", "deleted"),
    "reconciled": ("=", "reconciled"),
    "skipped": ("·", "skipped"),
}
# scope abbreviations for the compact columns
_SC = {"project-local": "proj", "stack-general": "stack", "user-global": "global"}


def _rule(ch: str = "─") -> str:
    return ch * W


def _kv(label: str, value: str) -> str:
    return f"  {label:<11}{value}"


def _delta(before: float, after: float, unit: str = "") -> str:
    arrow = "▲" if after > before else ("▼" if after < before else "=")
    d = after - before
    sign = f" ({'+' if d > 0 else ''}{d:g}{unit})" if d else ""
    return f"{before:g} → {after:g}{unit} {arrow}{sign}".rstrip()


def _outcome(record: dict) -> str:
    if record.get("outcome"):
        return str(record["outcome"]).upper()
    entries = record.get("entries", [])
    writes = sum(1 for e in entries if e.get("action") in ("added", "corrected", "deleted"))
    scope = record.get("scope", {})
    candidates = scope.get("session_candidates", 0) or 0
    git = scope.get("git_commits", 0) or 0
    reviewed = scope.get("memories_reviewed", 0) or 0
    if writes == 0 and candidates == 0 and git == 0 and reviewed == 0:
        return "NOTHING TO CONSOLIDATE"  # nothing even to examine
    if writes == 0:
        return "NO-OP PASS · reviewed, nothing changed"
    if writes <= 2:
        return "LIGHT PASS"
    return "SUBSTANTIAL PASS"


def render(record: dict) -> str:
    out: list[str] = []
    proj = record.get("project", "?")
    ses = record.get("session", "?")
    outcome = _outcome(record)

    # Banner — rule-based (no right border, so it never misaligns across terminals
    # regardless of glyph widths).
    out.append(_rule("━"))
    out.append(f"  DREAM · consolidate-memory     [ {outcome} ]")
    out.append(f"  {proj} · session {ses}")
    out.append(_rule("━"))

    # Scope
    s = record.get("scope", {})
    out.append("")
    out.append(
        _kv(
            "Scope",
            f"git {s.get('git_range', '?')} ({s.get('git_commits', 0)} commits) · "
            f"{s.get('session_candidates', 0)} session candidate(s) · "
            f"{s.get('memories_reviewed', 0)} memories reviewed",
        )
    )

    # Verification (the recall-biased core)
    v = record.get("verification", {})
    out.append(
        _kv(
            "Verified",
            f"✓ {v.get('confirmed', 0)} confirmed · ~ {v.get('corrected', 0)} corrected · "
            f"⚠ {v.get('unverifiable', 0)} unverifiable"
            + (f"  [{v['method']}]" if v.get("method") else ""),
        )
    )

    # Changes table (grouped by action order)
    out.append("")
    out.append("  Changes")
    entries = record.get("entries", [])
    if not entries:
        out.append("    (none)")
    else:
        for key in _ACTIONS:
            for e in [x for x in entries if x.get("action") == key]:
                glyph, label = _ACTIONS[key]
                where = "/".join(p for p in (e.get("tier"), e.get("store")) if p and p != "-")
                scope = _SC.get(e.get("scope", ""), e.get("scope", ""))
                scope_col = f"<{scope}>" if scope else ""
                cite = f"  [{e['citation']}]" if e.get("citation") else ""
                out.append(
                    f"    {glyph} {label:<10} {scope_col:<8} {where or '—':<18} {e.get('name', '?')}{cite}"
                )
                if e.get("reason"):
                    out.append(f"        — {e['reason']}")

    # Always-loaded budget gauge (the per-session cost)
    b = record.get("budget", {})
    out.append("")
    out.append("  Always-loaded budget (per-session cost)")
    cm = b.get("claude_md", {})
    idx = b.get("index", {})
    rf = b.get("recall_facts", {})
    if cm:
        out.append(f"    CLAUDE.md       {_delta(cm.get('before', 0), cm.get('after', 0), ' ln')}")
    if idx:
        line = _delta(idx.get("before_lines", 0), idx.get("after_lines", 0), " ln")
        if "before_bytes" in idx or "after_bytes" in idx:
            line += f"   ({idx.get('before_bytes', 0)} → {idx.get('after_bytes', 0)} B)"
        out.append(f"    auto-mem index  {line}")
    if rf:
        out.append(f"    recall facts    {_delta(rf.get('before', 0), rf.get('after', 0))}")
    if not (cm or idx or rf):
        out.append("    (unchanged)")

    # Cross-project (global tier) — what moved across the project boundary
    xp = record.get("cross_project", {})
    if xp:
        out.append("")
        gtotal = xp.get("global_store_facts")
        out.append("  Cross-project (global tier)"
                   + (f"   ~/.claude/memory: {gtotal} fact(s)" if gtotal is not None else ""))
        pulled = xp.get("pulled") or []
        promoted = xp.get("promoted") or []
        refreshed = xp.get("refreshed", 0)
        if pulled:
            out.append("    ↓ pulled (global → here, replicated for recall)")
            for p in pulled:
                nm = p.get("name", "?") if isinstance(p, dict) else str(p)
                sc = _SC.get(p.get("scope", ""), p.get("scope", "")) if isinstance(p, dict) else ""
                out.append(f"        {nm}" + (f"  <{sc}>" if sc else ""))
        if promoted:
            out.append("    ↑ promoted (here → global, now shareable)")
            for p in promoted:
                nm = p.get("name", "?") if isinstance(p, dict) else str(p)
                sc = _SC.get(p.get("scope", ""), p.get("scope", "")) if isinstance(p, dict) else ""
                out.append(f"        {nm}" + (f"  <{sc}>" if sc else ""))
        if refreshed:
            out.append(f"    ⟳ {refreshed} stale mirror(s) refreshed from canonical")
        if not (pulled or promoted or refreshed):
            out.append("    (no cross-project movement this pass)")

    # Health
    h = record.get("health", {})
    if h:
        ptr = "✓ all pointers resolve" if h.get("index_pointers_ok", True) else "✗ BROKEN pointers"
        broken = h.get("broken") or []
        dangling = h.get("dangling_links") or []
        bits = [ptr]
        if broken:
            bits.append(f"broken: {', '.join(broken)}")
        if dangling:
            bits.append(f"{len(dangling)} dangling link(s): " + ", ".join(f"[[{d}]]" for d in dangling))
        out.append("")
        out.append(_kv("Health", " · ".join(bits)))

    # Marker
    m = record.get("marker", {})
    if m:
        out.append(_kv("Marker", f"→ {str(m.get('commit', '?'))[:12]} @ {m.get('timestamp', '?')}"))

    return "\n".join(out)


def main() -> int:
    raw = open(sys.argv[1]).read() if len(sys.argv) > 1 else sys.stdin.read()
    try:
        record = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"render_dashboard: invalid cycle-record JSON: {exc}", file=sys.stderr)
        return 1
    print(render(record))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
