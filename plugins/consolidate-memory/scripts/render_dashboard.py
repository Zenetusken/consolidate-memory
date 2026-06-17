#!/usr/bin/env python3
"""Render a consolidate-memory CYCLE RECORD (JSON) into a consistent dashboard.

The skill workflow accumulates a small JSON record of what the pass actually did
(see SKILL.md "Output: the cycle record"); this script renders it deterministically
so the report has a fixed skeleton but data-driven content. Sections with no data
collapse to "(none)". The outcome banner is derived from the write counts, so the
headline reflects the cycle — a no-op pass and a heavy pass look different at a glance.

Layout principles (keep the report coherent, low cognitive load):
  • ONE consistent column grid per section — labels and values align vertically.
  • ONE unit for the always-loaded gauge (estimated tokens) + a visual budget bar.
  • Secondary detail (reasons, citations, basis) is dimmed and on a consistent line.
  • RULES, never boxed right-borders — so it never misaligns across terminals or when
    the agent relays it inside a markdown code block.

Color is OPT-IN and auto-gated: on only when stdout is a TTY and `NO_COLOR` is unset
(override with `--color=always|never`). It auto-disables when captured (the agent
relays this in markdown), piped, or on a dumb terminal — and it is always REDUNDANT
with the glyphs (✓ ⚠ ✗), never the sole carrier of meaning. So old terminals and the
agent-relay path get clean plain text; humans running it live get color.

Usage: python3 render_dashboard.py [--color=auto|always|never] [--ascii] CYCLE_RECORD.json
       python3 render_dashboard.py --demo     # preview with a built-in sample record
       (--ascii = no-Unicode fallback for older/non-UTF8 terminals; or pipe JSON on stdin)
"""

from __future__ import annotations

import json
import os
import re
import sys
from typing import Any, Mapping, cast

import memory_status as ms  # sibling script — reuse the canonical tier bands (derive, don't duplicate)
# The cycle-record CONTRACT (v0.1.6) lives in memory_status; reference it as ms.CycleRecord
# (the type render() consumes + _demo_record() produces), so this consumer and the producer
# agree on ONE definition and mypy flags any cross-module disagreement.

W = 60  # dashboard rule width

# Strip terminal control bytes from any model/record-derived string before printing.
# The cycle record is produced upstream (by the model); a stray ESC / C0/C1 byte in a
# fact name, reason, citation, or node label would otherwise be emitted verbatim and
# could inject terminal escape sequences. \t and \n are preserved; everything else in
# the C0/DEL/C1 ranges becomes U+FFFD. This is the model→presentation safety boundary.
# NB: this runs on record-derived text; our OWN color codes (added after) are trusted.
_CTRL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]")


def _clean(s: object) -> str:
    return _CTRL.sub("�", str(s))


# ── color (opt-in, auto-gated, always redundant with glyphs) ────────────────────
_COLOR = False  # set in main(); stays False for library/test calls → plain output
_CODES = {"reset": "\x1b[0m", "bold": "\x1b[1m", "dim": "\x1b[2m",
          "red": "\x1b[31m", "green": "\x1b[32m", "yellow": "\x1b[33m", "cyan": "\x1b[36m"}

# ── ASCII fallback (opt-in --ascii, for non-UTF8 / older terminals) ──────────────
_ASCII = False  # set in main(); when on, the FINAL rendered string is translated to ASCII.
# Each glyph → a SINGLE ASCII char, so column alignment (computed on plain text) is preserved — a
# multi-char map like →"->" would shift columns and is forbidden. This table is for READABILITY;
# a width-preserving `.encode("ascii","replace")` catch-all in render() GUARANTEES pure-ASCII output
# for anything NOT listed (incl. `_clean`'s U+FFFD replacement char + any future glyph), so the set
# can't silently drift. Applied as the LAST step only, so the default Unicode output stays identical.
_GLYPH_ASCII = str.maketrans({
    "█": "#", "░": ":", "━": "=", "─": "-", "✦": "*", "⚠": "!", "✓": "+", "✗": "x",
    "◀": "<", "↓": "v", "⟳": "@", "→": ">", "·": ".", "•": "*",
    "≈": "~", "↑": "^", "−": "-", "…": ".", "↔": "-", "—": "-",   # emitted but earlier-missed (Gate-2)
})


def _color_enabled(argv: list, stream: object) -> bool:
    """Resolve the color mode. `--color=never|always|auto` (or `--no-color`) wins;
    otherwise AUTO = stdout is a TTY and NO_COLOR is unset and TERM isn't 'dumb'. The
    AUTO gate is what makes color safe: when the agent runs this via a tool call (stdout
    captured, not a TTY) or it's piped/redirected, color silently turns off."""
    mode = "auto"
    for a in argv:
        if a == "--no-color":
            mode = "never"
        elif a == "--color":
            mode = "always"
        elif a.startswith("--color="):
            mode = a.split("=", 1)[1].strip().lower()
    if mode == "never":
        return False
    if mode == "always":
        return True
    if os.environ.get("NO_COLOR") is not None:
        return False
    if os.environ.get("TERM") == "dumb":
        return False
    isatty = getattr(stream, "isatty", None)
    return bool(isatty and isatty())


def _c(text: str, *codes: str) -> str:
    """Wrap `text` in ANSI codes iff color is enabled. No-op otherwise, so the same
    render path produces clean plain text when captured/piped/dumb."""
    if not _COLOR or not codes:
        return text
    return "".join(_CODES[c] for c in codes) + text + _CODES["reset"]


def _lbl(text: str, width: int = 0) -> str:
    """A DIM in-row field label (chrome), so the data values beside it visually pop when
    color is on. Padding is computed on the PLAIN text, so color codes never disturb
    column alignment; in monochrome this is just the plain (optionally padded) label —
    i.e. dimming changes nothing in the captured/markdown path."""
    s = f"{text:<{width}}" if width else text
    return _c(s, "dim")


# action -> (glyph, label, color) ; ordering controls display order
_ACTIONS = {
    "added": ("+", "added", "green"),
    "corrected": ("~", "corrected", "yellow"),
    "deleted": ("−", "deleted", "red"),   # − minus sign
    "reconciled": ("=", "reconciled", "cyan"),
    "skipped": ("·", "skipped", "dim"),    # · middle dot
}
# scope abbreviations for the compact columns
_SC = {"project-local": "proj", "stack-general": "stack", "user-global": "global"}


def _rule(ch: str = "━") -> str:
    return ch * W


def _kv(label: str, value: str) -> str:
    # Label is structural chrome → bold (when color on) + UPPERCASE (carries the
    # hierarchy in monochrome too); the value is the data and stays as-is.
    return f"  {_c(f'{label:<10}', 'bold')}{value}"


def _num(x: object) -> float:
    """Coerce a model-authored cycle-record value to a number. The record is produced
    upstream (by the model), so a budget field may arrive as a string like '10' or be
    absent; never let that raise mid-render."""
    try:
        # `x` is typed `object` ON PURPOSE — callers pass `.get()` results, None, str,
        # numbers — so float() needs a cast to typecheck. The try/except is the actual
        # runtime guard; cast is a compile-time no-op (the spec-prescribed shape, since
        # narrowing `x` to float|int|str would break the None/`.get()` callers).
        return float(cast(Any, x))
    except (TypeError, ValueError):
        return 0.0


def _dget(m: object, k: str) -> dict:
    """A dict sub-value of a model-authored record — or {} if the record/value is absent or the
    WRONG type. The container analog of _num/_clean: the model→presentation boundary never trusts
    a container's type either (a truthy non-dict `scope`/`health`/… must degrade, not crash)."""
    v = m.get(k) if isinstance(m, dict) else None
    return v if isinstance(v, dict) else {}


def _lget(m: object, k: str) -> list:
    """A list sub-value of a model-authored record — or [] if absent/wrong-type."""
    v = m.get(k) if isinstance(m, dict) else None
    return v if isinstance(v, list) else []


def _g(n: float) -> str:
    """Format a number without a trailing .0 (so 42.0 → '42')."""
    n = _num(n)
    return f"{n:g}"


def _flag(x: object) -> bool:
    """Coerce a model-authored boolean — it may arrive JSON-stringified ('false'/'true').
    Mirrors _num/_clean: the model→presentation boundary never trusts the raw type, so a
    stray '"false"' can't read as truthy and flip a flag on."""
    if isinstance(x, str):
        return x.strip().lower() in ("true", "1", "yes")
    return bool(x)


def _bar(used: object, budget: object, width: int = 10) -> str:
    """A fixed-width budget bar `[██░░░░░░░░]`, fill colored by headroom (redundant with
    the % and any ⚠). Empty string when there's no budget to gauge against."""
    u, b = _num(used), _num(budget)
    if b <= 0:
        return ""
    frac = u / b
    filled = int(round(min(max(frac, 0.0), 1.0) * width))
    body = "█" * filled + "░" * (width - filled)
    col = "red" if frac > 1.0 else ("yellow" if frac > 0.8 else "green")
    return "[" + _c(body, col) + "]"


def _pct(used: object, budget: object) -> str:
    b = _num(budget)
    return "" if b <= 0 else f"{round(100 * _num(used) / b)}%"


def _over(b: Mapping[str, Any]) -> str:
    """The ACTIONABLE over-budget flag for a project always-loaded tier (CLAUDE.md /
    index): the seed (memory_status) sets `over` against the token ceiling. Distinct
    from the global CLAUDE.md's *advisory* 'heavy' note — this one means 'prune/propose'.
    Kept as a named helper because the smoke tests assert its contract directly.

    Param typed `Mapping[str, Any]` (read-only): a TypedDict IS assignable to a read-only
    Mapping (covariant), so BOTH the ClaudeMdBudget and IndexBudget sub-shapes flow in
    with no Union — which is what dissolves the old dual-budget-shape mypy friction."""
    if b.get("over"):
        return _c(f"  ⚠ OVER ≈{b.get('budget_tokens', '?')} tok BUDGET", "red")
    return ""


def _outcome(record: Mapping[str, Any]) -> str:
    # Read-only Mapping[str, Any]: a CycleRecord IS assignable to it (covariant), so the
    # render(record: CycleRecord) caller passes through with no error, and the demo /
    # json.loads paths work too. We only READ here.
    if record.get("outcome"):
        return str(record["outcome"]).upper()
    entries = _lget(record, "entries")
    writes = sum(1 for e in entries if e.get("action") in ("added", "corrected", "deleted"))
    scope = _dget(record, "scope")
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


def _outcome_colored(oc: str) -> str:
    if oc.startswith("SUBSTANTIAL"):
        return _c(oc, "bold", "green")
    if oc.startswith("LIGHT"):
        return _c(oc, "cyan")
    return _c(oc, "dim")


def _tier_colored(tier: str) -> str:
    """Color the rigor tier (redundant with the word, never the sole signal). HEAVY is
    rigor-only (bold yellow); LIGHT/SUBSTANTIAL/else delegate to `_outcome_colored` so the
    rigor line and the outcome banner share ONE palette and can't drift out of sync.
    `tier` is already _clean()'d by the caller, so a model slip (int/None) renders dim."""
    return _c(tier, "bold", "yellow") if tier.upper().startswith("HEAVY") else _outcome_colored(tier)


def _item(p: object) -> tuple:
    """(name, scope-abbrev) for a pulled/promoted entry (dict or bare string)."""
    if isinstance(p, dict):
        return _clean(p.get("name", "?")), _clean(_SC.get(p.get("scope", ""), p.get("scope", "")))
    return _clean(str(p)), ""


def _network_section(record: Mapping[str, Any], net: Mapping[str, Any]) -> list:
    """The neural-network token sub-section: per-node ESTIMATED cost across every node,
    network totals (with the mirror-driven share), and what THIS cycle did on the
    triggering node. Lifecycle counts are DERIVED from entries[] (single source of
    truth), token movement from the budget delta, GC/refresh from cross_project."""
    t = net.get("totals", {})
    nodes = net.get("nodes", [])
    # A cycle record is MODEL-authored, so a numeric field may arrive as a string ("6183")
    # or null. Coerce every network numeric through _num (the budget rows already do) —
    # otherwise the sort/arith/format below crashes the WHOLE render on a non-int.
    al = _num(t.get("always_loaded_tokens", 0))
    rc = _num(t.get("recall_tokens", 0))
    out = ["", "  " + _c("NEURAL NETWORK", "bold") + _c("   · token cost (≈ est., not a tokenizer)", "dim")]
    out.append(f"    {_lbl('network total')}   ≈{_g(al)} {_lbl('always-loaded')} · ≈{_g(rc)} {_lbl('recall-pool')}")
    mir = _num(t.get("mirror_index_tokens", 0))
    if mir:
        pct = round(100 * mir / al) if al else 0
        out.append("    " + _c(f"of which ≈{_g(mir)} ({pct}%) mirror-driven "
                                "(lever: global store demote/GC, not local prune)", "dim"))

    shown = sorted(nodes, key=lambda d: -_num(d.get("always_loaded_tokens", 0)))
    cap = 12
    namew = min(max((len(_clean(n.get("node", "?"))) for n in shown[:cap]), default=4), 18)
    for n in shown[:cap]:
        nm = _clean(n.get("node", "?"))[:18]
        star = _c("*", "cyan") if n.get("trigger") else " "
        mark = _c("  ◀ dream ran here", "cyan") if n.get("trigger") else ""
        out.append(f"    {star} {nm:<{namew}}  {_lbl('always')} ≈{_g(n.get('always_loaded_tokens', 0)):>5}  "
                   f"{_lbl('recall')} ≈{_g(n.get('recall_tokens', 0)):>7}  {_g(n.get('facts', 0)):>3} {_lbl('facts')} · "
                   f"{_g(n.get('shared', 0))} {_lbl('shared')}{mark}")
    if len(shown) > cap:
        out.append(f"      … +{len(shown) - cap} more node(s)")
    if not nodes:
        out.append("      (no nodes hold shared facts yet)")

    # This cycle's lifecycle on the triggering node — derived, not hand-counted.
    entries = _lget(record, "entries")
    cnt = {k: sum(1 for e in entries if e.get("action") == k) for k in _ACTIONS}
    parts = [f"{g} {cnt[k]} {lbl}" for k, (g, lbl, _col) in _ACTIONS.items() if cnt[k]]
    idx = _dget(_dget(record, "budget"), "index")
    xp = _dget(record, "cross_project")
    trig = _clean(net.get("trigger", "?"))
    # DOUBLE-SPACE join (not ' · ') — same reason as the Changes legend: the skip glyph
    # '·' must not read as a doubled dot beside a '·' separator.
    out.append(f"    {_lbl('this cycle on')} {trig}: " + ("  ".join(parts) if parts else "no writes"))
    extras = []
    if "after_tokens" in idx:
        extras.append(f"always-loaded ≈{idx.get('before_tokens', 0)} → ≈{idx.get('after_tokens', 0)} tok")
    if xp.get("gc_removed"):
        extras.append(f"gc {xp['gc_removed']} orphan(s)")
    if xp.get("refreshed"):
        extras.append(f"{xp['refreshed']} refreshed")
    if extras:
        out.append("      " + _c(" · ".join(extras), "dim"))
    return out


def render(record: ms.CycleRecord) -> str:
    if not isinstance(record, dict):
        record = {}  # a non-dict record (JSON list/scalar from stdin) degrades — this is the runtime boundary
    out: list = []
    proj = _clean(record.get("project", "?"))
    ses = _clean(record.get("session", "?"))
    oc = _outcome(record)

    # Banner — a centered rule with the title left, outcome right. Padding is computed on
    # PLAIN text length, then color is applied, so codes never throw off the alignment.
    title = "✦ DREAM · consolidate-memory"
    gap = max(2, W - 2 - len(title) - len(oc))
    out.append(_rule())
    out.append("  " + _c("✦", "cyan") + title[1:] + " " * gap + _outcome_colored(oc))
    out.append("  " + _c(f"{proj} · session {ses}", "dim"))
    out.append(_rule())

    # Scope + Verification (aligned label column)
    s = _dget(record, "scope")
    out.append("")
    out.append(_kv("SCOPE", f"git {_clean(s.get('git_range', '?'))} · {_g(_num(s.get('git_commits', 0)))} commits · "
                            f"{_g(_num(s.get('session_candidates', 0)))} candidates · {_g(_num(s.get('memories_reviewed', 0)))} reviewed"))
    v = _dget(record, "verification")
    method = f"   {_c('[' + _clean(v['method']) + ']', 'dim')}" if v.get("method") else ""
    out.append(_kv("VERIFIED", f"{_c('✓', 'green')} {v.get('confirmed', 0)} confirmed · "
                               f"{_c('~', 'yellow')} {v.get('corrected', 0)} corrected · "
                               f"{_c('⚠', 'yellow')} {v.get('unverifiable', 0)} unverifiable{method}"))

    # Rigor tier (v0.1.3) — the EARLY predicted-effort HINT. BOTH the tier and the magnitude
    # are DERIVED here from `scope` (the tier via the same ms.suggested_tier the scripts use),
    # so the label can never contradict its own magnitude — there is NO stored tier to drift,
    # exactly as `_outcome` derives from `entries`. The stored `rigor` block carries `phase`,
    # the prune-pressure flag/reason, AND the realized-rigor `applied`/`override_reason`
    # decision (v0.1.4) — never the derivable suggested tier. Presence-checked (not truthiness)
    # so an empty
    # `rigor: {}` still shows the derived line; legacy records (no `rigor` key) skip it. The
    # tier is a DISTINCT quantity from the outcome banner (output-based, write counts).
    if "rigor" in record:
        gc, cand = _num(s.get("git_commits", 0)), _num(s.get("session_candidates", 0))
        # v0.1.7: a TRUE no-op (magnitude 0 AND no entries) carries no effort estimate — skip the
        # RIGOR line entirely (matches how other empty sections collapse), instead of printing
        # "RIGOR LIGHT · magnitude 0" on a do-nothing pass. A pass with entries OR magnitude > 0
        # still shows it.
        if (gc + cand) or _lget(record, "entries"):
            rg = _dget(record, "rigor")
            suggested = ms.suggested_tier(gc, cand)
            # `applied` (v0.1.4) is the ceremony the model ACTUALLY ran — a stored DECISION, not
            # derivable from magnitude. Render "suggested → applied · why" only when it differs;
            # absent/empty/equal renders the derived suggested tier exactly as before (back-compat).
            # normalize: strip + canonical-case, and honor ONLY a RECOGNIZED tier — a stray
            # ' HEAVY ' or a non-tier model slip must not render a spurious 'X → junk' override.
            applied = _clean(rg.get("applied", "")).strip().upper()
            if applied in ("LIGHT", "SUBSTANTIAL", "HEAVY") and applied != suggested.upper():
                tier = f"{_tier_colored(suggested)} → {_tier_colored(applied)}"
                reason = _clean(rg.get("override_reason", ""))
                applied_note = _c(f" · applied: {reason}", "dim") if reason else ""
            else:
                tier = _tier_colored(suggested)
                applied_note = ""
            detail = _c(f"· {_clean(rg.get('phase', ''))} · magnitude {_g(gc + cand)} "
                        f"({_g(gc)} commits + {_g(cand)} candidates)", "dim")
            pp = _c(f"  ⚠ prune-pressure ({_clean(rg.get('prune_reason', ''))})", "yellow") \
                if _flag(rg.get("prune_pressure")) else ""
            out.append(_kv("RIGOR", f"{tier} {detail}{applied_note}{pp}"))

    # Changes — glyph-coded (legend inline), aligned tier/store + scope columns; the
    # reason+citation move to a single dim sub-line so nothing floats after the name.
    out.append("")
    out.append("  " + _c("CHANGES", "bold"))
    entries = _lget(record, "entries")
    if not entries:
        out.append("    (none)")
    else:
        for key, (glyph, label, gcol) in _ACTIONS.items():
            for e in [x for x in entries if x.get("action") == key]:
                # SELF-LABELLING rows: glyph + the action WORD + the memory name. Spelling
                # out the action ("added" / "skipped" / …) means a skipped entry is
                # obviously skipped — no glyph-only guessing — and there is NO placeholder
                # column, so an entry with no tier/store never shows a stray '—'.
                out.append(f"    {_c(glyph + ' ' + f'{label:<10}', gcol)} {_clean(e.get('name', '?'))}")
                # Detail line (dim, consistent order): where-it-landed · scope · why ·
                # [source]. Empty parts collapse, so it reads as prose with nothing to
                # misalign and never starts with a dash.
                # _clean (which str()s) is applied PER PART, before the join — a
                # non-string tier/store (model slip) would otherwise crash the join.
                where = "/".join(_clean(p) for p in (e.get("tier"), e.get("store")) if p and p != "-")
                scope = _clean(_SC.get(e.get("scope", ""), e.get("scope", "")))
                reason = _clean(e.get("reason") or "")
                cite = _clean(e.get("citation") or "")
                parts = [p for p in (where, f"<{scope}>" if scope else "", reason,
                                     f"[{cite}]" if cite else "") if p]
                if parts:
                    out.append("        " + _c(" · ".join(parts), "dim"))

    # Always-loaded budget — ONE grid: label | value | bar/% or descriptor. One unit
    # (estimated tokens) for the gauge; line/fact deltas are a terse trailing note.
    b = _dget(record, "budget")
    cm = b.get("claude_md", {})
    gcm = b.get("global_claude_md", {})
    idx = b.get("index", {})
    rf = b.get("recall_facts", {})
    out.append("")
    out.append("  " + _c("ALWAYS-LOADED", "bold") + _c("   · paid every session", "dim"))
    lbl, val = 18, 12

    def _brow(label: str, value: str, tail: str) -> None:
        # Label dimmed (chrome), value left bright (the data you scan for).
        out.append(f"    {_lbl(label, lbl)}{value:<{val}} {tail}".rstrip())

    if cm:
        at, bt = cm.get("after_tokens", 0), cm.get("budget_tokens", 0)
        dln = _num(cm.get("after", 0)) - _num(cm.get("before", 0))
        note = (f"  {'+' if dln >= 0 else ''}{_g(dln)} ln" if dln else "")
        _brow("project CLAUDE.md", f"≈{_g(at)}/{_g(bt)}", f"{_bar(at, bt)} {_pct(at, bt)}{note}{_over(cm)}")
    if gcm.get("present"):
        adv = _c("  ⚠ heavy — loads in every project", "yellow") if gcm.get("over") else ""
        _brow("global CLAUDE.md", f"≈{_g(gcm.get('tokens', 0))}", f"read-only · every project{adv}")
    if idx:
        at, bt = idx.get("after_tokens", 0), idx.get("budget_tokens", 0)
        dln = _num(idx.get("after_lines", 0)) - _num(idx.get("before_lines", 0))
        note = (f"  {'+' if dln >= 0 else ''}{_g(dln)} ln" if dln else "")
        _brow("auto-mem index", f"≈{_g(at)}/{_g(bt)}", f"{_bar(at, bt)} {_pct(at, bt)}{note}{_over(idx)}")
    if rf:
        d = _num(rf.get("after", 0)) - _num(rf.get("before", 0))
        _brow("recall facts", _g(rf.get("after", 0)), (f"{'+' if d >= 0 else ''}{_g(d)}" if d else ""))
    if not (cm or idx or rf or gcm.get("present")):
        out.append("    (unchanged)")

    # Cross-project (global tier) — aligned direction | scope | name; counts on one line.
    xp = _dget(record, "cross_project")
    if xp:
        out.append("")
        gtotal = xp.get("global_store_facts")
        head = "  " + _c("CROSS-PROJECT", "bold") + _c("   · global tier", "dim")
        if gtotal is not None:
            head += _c(f" · ~/.claude/memory: {gtotal} fact(s)", "dim")
        out.append(head)
        pulled = xp.get("pulled") or []
        promoted = xp.get("promoted") or []
        for p in pulled:
            nm, sc = _item(p)
            out.append(f"    {_c('↓', 'cyan')} {_lbl('pulled', 10)}{('<' + sc + '>') if sc else '':<8} {nm}")
        for p in promoted:
            nm, sc = _item(p)
            out.append(f"    {_c('↑', 'green')} {_lbl('promoted', 10)}{('<' + sc + '>') if sc else '':<8} {nm}")
        moved = []
        if xp.get("refreshed"):
            moved.append(f"⟳ {xp['refreshed']} mirror(s) refreshed")
        if xp.get("gc_removed"):
            moved.append(f"− {xp['gc_removed']} orphan(s) reclaimed")
        if moved:
            out.append("    " + _c(" · ".join(moved), "dim"))
        if not (pulled or promoted or moved):
            out.append("    " + _c("(no cross-project movement this pass)", "dim"))

    # Neural network — token consumption across all nodes (the observability ask).
    # Guarded: legacy/no-op records without a `network` block skip it.
    net = _dget(record, "network")
    if net:
        out.extend(_network_section(record, net))

    # Health
    h = _dget(record, "health")
    if h:
        ok = h.get("index_pointers_ok", True)
        ptr = _c("✓ all pointers resolve", "green") if ok else _c("✗ BROKEN pointers", "red")
        broken = h.get("broken") or []
        dangling = h.get("dangling_links") or []
        bits = [ptr]
        if broken:
            bits.append(_c(f"broken: {', '.join(_clean(x) for x in broken)}", "red"))
        if dangling:
            bits.append(_c(f"{len(dangling)} dangling: " + ", ".join(f"[[{_clean(d)}]]" for d in dangling), "yellow"))
        # v0.1.5: slug-orphan / schema-drift findings (presence-checked, so legacy records
        # without these keys render byte-identically). slug_orphans is a list of twin slug
        # names; schema_drift is the C2 dict — surface a ⚠ only when a DRIFT finding exists.
        so = h.get("slug_orphans")
        so = so if isinstance(so, list) else []   # truthy non-list (model slip) → ignore, don't iterate chars
        if so:
            bits.append(_c(f"⚠ slug-orphan: {', '.join(_clean(x) for x in so)}", "yellow"))
        sd = h.get("schema_drift")
        sd = sd if isinstance(sd, dict) else {}    # truthy non-dict → ignore, don't crash on .get()
        # Coerce the four DRIFT fields via _num at the model→presentation boundary (like every
        # other render numeric) rather than ms.drift_findings' strict int(): the cycle record is
        # model-authored, so a field may arrive as a non-numeric string and must NOT crash
        # render() (the established _num/_clean/_flag invariant). ms.drift_findings keeps its
        # int()-based definition for its clean-int callers (seed + smoke).
        _drift_n = sum(_num(sd.get(k, 0)) for k in
                       ("missing_node_type", "malformed_scope", "malformed_origin", "index_mismatch"))
        if _drift_n > 0:
            bits.append(_c(f"⚠ schema drift: {_g(sd.get('missing_node_type', 0))} missing node_type · "
                           f"{_g(sd.get('malformed_scope', 0))} malformed scope · "
                           f"{_g(sd.get('malformed_origin', 0))} malformed originSessionId · "
                           f"{_g(sd.get('index_mismatch', 0))} index↔file", "yellow"))
        out.append("")
        out.append(_kv("HEALTH", " · ".join(bits)))

    # Marker
    m = _dget(record, "marker")
    if m:
        out.append(_kv("MARKER", _c(f"→ {_clean(str(m.get('commit', '?'))[:12])} @ {_clean(m.get('timestamp', '?'))}", "dim")))

    result = "\n".join(out)
    if _ASCII:   # --ascii (LAST step): translate for readability, then encode-replace to GUARANTEE
        # pure ASCII — each remaining non-ASCII codepoint → a single "?" (width-preserving), so an
        # unmapped/future glyph (or _clean's U+FFFD) can never leak Unicode to a non-UTF8 terminal.
        result = result.translate(_GLYPH_ASCII).encode("ascii", "replace").decode("ascii")
    return result


def _demo_record() -> ms.CycleRecord:
    """A representative cycle record for `--demo` — lets anyone preview the dashboard
    (and its color, in a TTY) without authoring or pasting JSON. Mirrors a substantial
    pass: an add, a correction, and a SKIPPED decision (so the skipped-row UI is visible)."""
    return {
        "project": "acme-api", "session": "a1b2c3d4",
        "scope": {"git_range": "9ed8d5c..HEAD", "git_commits": 7,
                  "session_candidates": 5, "memories_reviewed": 12},
        "rigor": {"phase": "final", "prune_pressure": False, "prune_reason": "",
                  "applied": "SUBSTANTIAL",  # suggested HEAVY (7+5=12) → applied SUBSTANTIAL (override)
                  "override_reason": "small curated set despite the commit volume"},
        "verification": {"confirmed": 6, "corrected": 2, "unverifiable": 1, "method": "subagents"},
        "entries": [
            {"action": "added", "tier": "recall", "store": "auto-mem", "scope": "project-local",
             "name": "retry-backoff-is-jittered",
             "reason": "non-obvious why behind the 250ms base", "citation": "9ed8d5c"},
            {"action": "corrected", "tier": "on-demand", "store": "repo", "scope": "project-local",
             "name": "AGENTS.md test count 88->103",
             "reason": "drifted since last pass", "citation": "pytest -q"},
            {"action": "skipped", "tier": "-", "store": "-", "scope": "project-local",
             "name": "rate-limit-value",
             "reason": "credential-shaped; firewall + pointer only", "citation": ""},
        ],
        "budget": {
            "claude_md": {"before": 40, "after": 41, "before_tokens": 1180,
                          "after_tokens": 1210, "budget_tokens": 4000, "over": False},
            "global_claude_md": {"present": True, "tokens": 2240,
                                 "budget_tokens": 4000, "over": False},
            "index": {"before_lines": 11, "after_lines": 13, "before_tokens": 226,
                      "after_tokens": 278, "budget_tokens": 1200, "over": False},
            "recall_facts": {"before": 10, "after": 12},
        },
        "health": {"index_pointers_ok": True, "broken": [],
                   "dangling_links": ["orphaned-link-name"]},
        "cross_project": {"global_store_facts": 9,
                          "pulled": [{"name": "gh-pr-edit-broken-in-env", "scope": "user-global"}],
                          "promoted": [{"name": "gh-pr-edit-broken-in-env", "scope": "user-global"}],
                          "refreshed": 1, "gc_removed": 2},
        "network": {"basis": "≈ chars/4", "node_def": "stores", "trigger": "acme-api",
                    "nodes": [
                        {"node": "acme-api", "trigger": True, "always_loaded_tokens": 278,
                         "mirror_index_tokens": 150, "recall_tokens": 1775, "facts": 12, "shared": 6},
                        {"node": "Doc_Flo", "trigger": False, "always_loaded_tokens": 6183,
                         "mirror_index_tokens": 176, "recall_tokens": 207220, "facts": 104, "shared": 4}],
                    "totals": {"nodes": 2, "always_loaded_tokens": 6461,
                               "mirror_index_tokens": 326, "recall_tokens": 208995}},
        "marker": {"commit": "b6d37b6e9f01", "timestamp": "2026-06-16T11:40:00Z"},
    }


def _persist(record: Mapping[str, Any], dirpath: str) -> None:
    """Append the cycle record (one JSON line) to <dir>/.consolidation-log.jsonl so
    magnitude→(applied, outcome) data accrues for future band calibration (v0.1.4). The
    record's own `marker` stamps it — no wall-clock call here. Defensive at the model→file
    boundary (mirrors _num/_clean/_flag never-crash): skip if `dir` is absent (never create a
    stray dir); REFUSE on an empty marker.timestamp (an unstamped cycle would let two distinct
    passes at the same HEAD collide on a `(commit, '')` dedup key); IDEMPOTENT on
    (marker.commit, marker.timestamp), tolerating blank/unparseable lines in an existing log."""
    if not os.path.isdir(dirpath):
        print(f"render_dashboard: --persist dir not found, skipping log: {dirpath}", file=sys.stderr)
        return
    marker = _dget(record, "marker")  # tolerate a truthy non-dict marker (model slip) — never .get() on a str
    commit, ts = str(marker.get("commit", "")), str(marker.get("timestamp", ""))
    if not ts:
        print("render_dashboard: marker.timestamp empty (unstamped cycle), skipping persist", file=sys.stderr)
        return
    logpath = os.path.join(dirpath, ".consolidation-log.jsonl")
    if os.path.exists(logpath):
        try:
            # errors="replace": a non-UTF-8 byte (e.g. a partial write from a killed process)
            # must NOT raise UnicodeDecodeError mid-scan — it's a ValueError, not an OSError.
            with open(logpath, encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        prev = json.loads(line)
                        pm = prev.get("marker") or {}
                        already = (str(pm.get("commit", "")) == commit
                                   and str(pm.get("timestamp", "")) == ts)
                    except (ValueError, AttributeError):
                        # tolerate ANY junk line — bad JSON (ValueError), or valid-JSON-but-
                        # non-object / non-dict marker (.get → AttributeError). Never block logging.
                        continue
                    if already:
                        return  # already logged this cycle — idempotent
        except OSError as exc:
            print(f"render_dashboard: cannot read log, skipping persist: {exc}", file=sys.stderr)
            return
    try:
        with open(logpath, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError as exc:
        print(f"render_dashboard: cannot append to log: {exc}", file=sys.stderr)


def main() -> int:
    global _COLOR, _ASCII
    argv = sys.argv[1:]
    _COLOR = _color_enabled(argv, sys.stdout)
    _ASCII = "--ascii" in argv   # opt-in no-Unicode fallback (translated as render's last step)
    # --persist DIR (v0.1.4): pull the flag + its value out BEFORE positionals are taken, so
    # the cycle-record path isn't shadowed by '--persist' or its DIR (the blocklist below only
    # strips the --color/--demo chrome). Mirrors how --color is excluded — but consumes TWO
    # tokens (the flag and its separate value).
    persist_dir, pruned, i = None, [], 0
    while i < len(argv):
        if argv[i] == "--persist":
            if i + 1 >= len(argv):
                print("render_dashboard: --persist requires a directory argument", file=sys.stderr)
                return 2
            persist_dir = argv[i + 1]
            i += 2
            continue
        pruned.append(argv[i])
        i += 1
    argv = pruned
    if "--demo" in argv:  # paste-free preview with a built-in record
        print(render(_demo_record()))
        return 0
    paths = [a for a in argv if not a.startswith("--color") and a not in ("--no-color", "--demo", "--ascii")]
    try:
        if paths:
            with open(paths[0], encoding="utf-8") as fh:
                raw = fh.read()
        else:
            raw = sys.stdin.read()
    except OSError as exc:
        print(f"render_dashboard: cannot read cycle record: {exc}", file=sys.stderr)
        return 1
    try:
        # The record is MODEL-authored JSON; we cast to the contract at this trust
        # boundary (cast is a runtime no-op) so render() typechecks. The actual
        # structural check is the warn-only validator below — non-blocking, stderr only.
        record = cast(ms.CycleRecord, json.loads(raw))
    except json.JSONDecodeError as exc:
        print(f"render_dashboard: invalid cycle-record JSON: {exc}", file=sys.stderr)
        return 1
    # Warn-only structural validation (v0.1.6): surface a wrong-CONTAINER-type key (the
    # model-slip class behind the past crashes) on STDERR. NEVER blocks the render and
    # NEVER touches stdout — the rendered dashboard stays byte-identical.
    for w in ms.validate_cycle_record(record):
        print(f"render_dashboard: cycle-record warning: {w}", file=sys.stderr)
    print(render(record))
    if persist_dir:
        _persist(record, persist_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
