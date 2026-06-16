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
import re
import sys

W = 66  # dashboard inner width

# Strip terminal control bytes from any model/record-derived string before printing.
# The cycle record is produced upstream (by the model); a stray ESC / C0/C1 byte in a
# fact name, reason, citation, or node label would otherwise be emitted verbatim and
# could inject terminal escape sequences. \t and \n are preserved; everything else in
# the C0/DEL/C1 ranges becomes U+FFFD. This is the model→presentation safety boundary.
_CTRL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]")


def _clean(s: object) -> str:
    return _CTRL.sub("�", str(s))

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


def _num(x: object) -> float:
    """Coerce a model-authored cycle-record value to a number. The record is produced
    upstream (by the model), so a budget field may arrive as a string like '10' or be
    absent; never let that raise mid-render."""
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def _delta(before: float, after: float, unit: str = "") -> str:
    before, after = _num(before), _num(after)
    arrow = "▲" if after > before else ("▼" if after < before else "=")
    d = after - before
    sign = f" ({'+' if d > 0 else ''}{d:g}{unit})" if d else ""
    return f"{before:g} → {after:g}{unit} {arrow}{sign}".rstrip()


def _over(b: dict) -> str:
    """A budget-overflow flag for an always-loaded tier line (Fix A). The seed
    (memory_status) sets `over` against the token ceiling; we just render the ⚠."""
    if b.get("over"):
        return f"  ⚠ OVER ≈{b.get('budget_tokens', '?')} tok BUDGET"
    return ""


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


def _network_section(record: dict, net: dict) -> list[str]:
    """The neural-network token sub-section: per-node ESTIMATED cost across every node,
    network totals, and what THIS cycle did (lifecycle) on the triggering node. Lifecycle
    counts are DERIVED from entries[] (single source of truth — never a parallel tally),
    token movement from the budget delta, GC/refresh from cross_project."""
    t = net.get("totals", {})
    nodes = net.get("nodes", [])
    out = ["", f"  Neural network — token consumption (all nodes)   basis: {_clean(net.get('basis', '?'))}"]
    out.append(f"    nodes: {t.get('nodes', len(nodes))} ({_clean(net.get('node_def', 'nodes'))}) · "
               f"triggering node: {_clean(net.get('trigger', '?'))}")
    out.append(f"    network total: ≈{t.get('always_loaded_tokens', 0)} always-loaded tok "
               f"(every node, every session) · ≈{t.get('recall_tokens', 0)} recall-pool tok")
    shown = sorted(nodes, key=lambda d: -d.get("always_loaded_tokens", 0))
    cap = 12
    for n in shown[:cap]:
        mark = "  ← trigger (dream ran here)" if n.get("trigger") else ""
        out.append(f"      {_clean(n.get('node', '?'))[:26]:<26} always ≈{n.get('always_loaded_tokens', 0):>5} · "
                   f"recall ≈{n.get('recall_tokens', 0):>6} · {n.get('facts', 0):>2} facts "
                   f"({n.get('shared', 0)} shared){mark}")
    if len(shown) > cap:
        out.append(f"      … +{len(shown) - cap} more node(s) not shown")
    if not nodes:
        out.append("      (no nodes hold shared facts yet)")

    # This cycle's lifecycle on the triggering node — derived, not hand-counted.
    entries = record.get("entries", [])
    cnt = {k: sum(1 for e in entries if e.get("action") == k) for k in _ACTIONS}
    parts = [f"{g} {cnt[k]} {lbl}" for k, (g, lbl) in _ACTIONS.items() if cnt[k]]
    idx = record.get("budget", {}).get("index", {})
    xp = record.get("cross_project", {})
    out.append(f"    this cycle's lifecycle on {_clean(net.get('trigger', '?'))} (the node dream ran on):")
    out.append("      " + (" · ".join(parts) if parts else "no writes"))
    al = ""
    if "after_tokens" in idx:
        al = (f"always-loaded ≈{idx.get('before_tokens', 0)} → ≈{idx.get('after_tokens', 0)} tok "
              f"({_delta(idx.get('before_tokens', 0), idx.get('after_tokens', 0))})")
    gc_n = xp.get("gc_removed", 0)
    rf_n = xp.get("refreshed", 0)
    extras = [s for s in (al,
                          f"GC reclaimed {gc_n} orphan(s)" if gc_n else "",
                          f"{rf_n} mirror(s) refreshed" if rf_n else "") if s]
    if extras:
        out.append("      " + " · ".join(extras))
    return out


def render(record: dict) -> str:
    out: list[str] = []
    proj = _clean(record.get("project", "?"))
    ses = _clean(record.get("session", "?"))
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
            f"git {_clean(s.get('git_range', '?'))} ({s.get('git_commits', 0)} commits) · "
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
            + (f"  [{_clean(v['method'])}]" if v.get("method") else ""),
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
                where = _clean("/".join(p for p in (e.get("tier"), e.get("store")) if p and p != "-"))
                scope = _clean(_SC.get(e.get("scope", ""), e.get("scope", "")))
                scope_col = f"<{scope}>" if scope else ""
                cite = f"  [{_clean(e['citation'])}]" if e.get("citation") else ""
                out.append(
                    f"    {glyph} {label:<10} {scope_col:<8} {where or '—':<18} {_clean(e.get('name', '?'))}{cite}"
                )
                if e.get("reason"):
                    out.append(f"        — {_clean(e['reason'])}")

    # Always-loaded budget gauge (the per-session cost)
    b = record.get("budget", {})
    out.append("")
    out.append("  Always-loaded budget (per-session cost)")
    cm = b.get("claude_md", {})
    idx = b.get("index", {})
    rf = b.get("recall_facts", {})
    if cm:
        line = _delta(cm.get("before", 0), cm.get("after", 0), " ln")
        if "after_tokens" in cm:
            line += f"   (≈{cm.get('before_tokens', 0)} → ≈{cm.get('after_tokens', 0)} tok)"
        out.append(f"    CLAUDE.md       {line}{_over(cm)}")
    if idx:
        line = _delta(idx.get("before_lines", 0), idx.get("after_lines", 0), " ln")
        if "before_bytes" in idx or "after_bytes" in idx:
            line += f"   ({idx.get('before_bytes', 0)} → {idx.get('after_bytes', 0)} B"
            if "after_tokens" in idx:
                line += f", ≈{idx.get('before_tokens', 0)} → ≈{idx.get('after_tokens', 0)} tok"
            line += ")"
        out.append(f"    auto-mem index  {line}{_over(idx)}")
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
                nm = _clean(p.get("name", "?") if isinstance(p, dict) else str(p))
                sc = _clean(_SC.get(p.get("scope", ""), p.get("scope", "")) if isinstance(p, dict) else "")
                out.append(f"        {nm}" + (f"  <{sc}>" if sc else ""))
        if promoted:
            out.append("    ↑ promoted (here → global, now shareable)")
            for p in promoted:
                nm = _clean(p.get("name", "?") if isinstance(p, dict) else str(p))
                sc = _clean(_SC.get(p.get("scope", ""), p.get("scope", "")) if isinstance(p, dict) else "")
                out.append(f"        {nm}" + (f"  <{sc}>" if sc else ""))
        if refreshed:
            out.append(f"    ⟳ {refreshed} stale mirror(s) refreshed from canonical")
        if not (pulled or promoted or refreshed):
            out.append("    (no cross-project movement this pass)")

    # Neural network — token consumption across all nodes (the observability ask).
    # Guarded like cross_project: legacy/no-op records without a `network` block skip it.
    net = record.get("network")
    if net:
        out.extend(_network_section(record, net))

    # Health
    h = record.get("health", {})
    if h:
        ptr = "✓ all pointers resolve" if h.get("index_pointers_ok", True) else "✗ BROKEN pointers"
        broken = h.get("broken") or []
        dangling = h.get("dangling_links") or []
        bits = [ptr]
        if broken:
            bits.append(f"broken: {', '.join(_clean(b) for b in broken)}")
        if dangling:
            bits.append(f"{len(dangling)} dangling link(s): " + ", ".join(f"[[{_clean(d)}]]" for d in dangling))
        out.append("")
        out.append(_kv("Health", " · ".join(bits)))

    # Marker
    m = record.get("marker", {})
    if m:
        out.append(_kv("Marker", f"→ {_clean(str(m.get('commit', '?'))[:12])} @ {_clean(m.get('timestamp', '?'))}"))

    return "\n".join(out)


def main() -> int:
    try:
        if len(sys.argv) > 1:
            with open(sys.argv[1], encoding="utf-8") as fh:
                raw = fh.read()
        else:
            raw = sys.stdin.read()
    except OSError as exc:
        print(f"render_dashboard: cannot read cycle record: {exc}", file=sys.stderr)
        return 1
    try:
        record = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"render_dashboard: invalid cycle-record JSON: {exc}", file=sys.stderr)
        return 1
    print(render(record))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
