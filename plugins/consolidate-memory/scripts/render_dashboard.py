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
from pathlib import Path
from typing import Any, Mapping, cast

import _ui  # sibling: shared visual vocabulary — wrap() + resolve_width() (other primitives mirrored below, smoke-pinned)
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


# v0.4.29 (spec §2.5): the shared visual vocabulary this script's main() must bless — the same
# five forms the sibling scripts' strict loops allow (`--ascii`/`--color`/`--no-color` handled here
# and in `_ui`, plus the two EQUALS-ONLY forms allowed at the *_startswith* test below). A bare
# `--width` is deliberately absent: `_ui.resolve_width` matches `startswith("--width=")` only, so
# blessing it would bless a silent no-op.
_VISUAL_FLAGS = ("--ascii", "--color", "--no-color")


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


# action -> (glyph, label, color) ; ordering controls display order.
# v0.4.35 (RC-3): the KEYS come from `ms.ACTION_VOCAB` — this table holds presentation only
# (glyph/label/colour), never the vocabulary itself. Spelling the five names here was how the
# panel came to count a superset of what the ladder beside it counted; the two now cannot
# diverge, because there is one list. Both directions of a divergence are the same fault — the
# declaration and this table disagreeing — and both are read by ONE census check in
# `tests/smoke.py`, the key set compared for equality in each direction.
_ACTION_PRESENTATION = {
    "added": ("+", "added", "green"),
    "corrected": ("~", "corrected", "yellow"),
    "deleted": ("−", "deleted", "red"),   # − minus sign
    "reconciled": ("=", "reconciled", "cyan"),
    "skipped": ("·", "skipped", "dim"),    # · middle dot
}


def _actions() -> dict:
    """The presentation rows for the DECLARED vocabulary, read at CALL time — never at import.

    A name `ACTION_VOCAB` declares with no row here is a real incompleteness, but it is one the
    panel survives: the **declaration is the truth and the row is cosmetic**, so the action renders
    under a neutral row (`?`, the name itself, dim) rather than being dropped or raising. Dropping it
    would make the panel's count line disagree with the declaration — RC-3's own defect — and raising
    is worse than both. This branch shipped both worse shapes first, and MEASURED 2026-09-18 on `tar`
    copies of this tree, neither of them yields a totals line: as a MODULE-SCOPE comprehension it
    raised `KeyError: 'archived'` at `tests/smoke.py:21` (this file is imported at that file's module
    scope), a traceback with no `✓`/`✗` at all; moved to a call-time raise, it aborted at the 83rd
    check — 82 printed, then `smoke.py:459`'s `rd.render(...)` raised. An abort is not a tally.

    So the incompleteness is caught where an editor actually looks — the census in `tests/smoke.py`
    asserts the two KEY SETS are equal against the raw table, so a synthesized row reds there as a
    counted failure and costs the suite nothing.
    """
    rows = dict(_ACTION_PRESENTATION)
    for name, _w in ms.ACTION_VOCAB:
        if name not in rows:
            rows[name] = ("?", name, "dim")
    return {name: rows[name] for name, _w in ms.ACTION_VOCAB}
# scope abbreviations for the compact columns
_SC = {"project-local": "proj", "stack-general": "stack", "user-global": "global"}


def _rule(ch: str = "━") -> str:
    return ch * W


def _kv(label: str, value: str) -> str:
    # Label is structural chrome → bold (when color on) + UPPERCASE (carries the
    # hierarchy in monochrome too); the value wraps to W with a HANGING INDENT under the
    # value column (12), so a long value stays inside the uniform width instead of overflowing.
    return f"  {_c(f'{label:<10}', 'bold')}{_ui.wrap(value, hang=12, width=W)}"


# v0.4.61 (RC-1): ONE home for the D5 remedy sentence. It now renders from TWO branches — the
# gate-active one, and the SUPPRESSED one whose ceiling line has no other way to name a remedy — and a
# sentence copied into two places is the divergence class this repo keeps closing.
_D5_REMEDY = ("prune can't reach budget → prune-safe-THEN-standing-justify the residual (earned density)")


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


def _recorded(m: Mapping[str, Any], key: str) -> bool:
    """True when `m` carries a MEASUREMENT under `key`.

    Presence is not the test. `_num` maps None/"" → 0.0, so a key that is PRESENT but holds
    nothing is indistinguishable, after coercion, from a recorded zero — and a panel line
    built on `key in m` renders the absent state as a measured `0`. `0` itself IS a
    measurement (a truthful zero is a result, and the audit that produced this cycle found
    exactly that distinction being lost: the record HOLDS nothing vs the record RECORDED 0).

    The blank test is `memory_status._duty_blank`, not a local re-spelling: it is the
    canonical "key present and holds nothing" predicate, and the sibling import above states
    the rule this file follows ("derive, don't duplicate"). A second copy is how the
    periphery-parity defects happened."""
    return key in m and not ms._duty_blank(m[key])


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
    if _flag(b.get("over")):
        return _c(f"  ⚠ OVER ≈{b.get('budget_tokens', '?')} tok BUDGET", "red")
    return ""


def _unmeasurable(b: Mapping[str, Any]) -> str:
    """The fault flag for a tier whose operand EXISTS but was not measurable (v0.4.45).

    A named sibling of `_over` rather than a branch inside it, because the two answer
    different questions and only one of them has an answer here: `_over` asks "is this over
    budget", and an unmeasured operand cannot be over or under anything — the 0 it would
    compare is not a measurement. v0.4.35's refusal-verdict parity ("a refusal must never be
    spelled like a verdict") applies one tier up: a store we could not READ must never be
    spelled like a store that is fine.

    A FUNCTION, and the callers suppress the gauge rather than printing this beside it —
    `_bar(0, 1500)` draws a full-green empty bar, so a ⚠ printed next to it reproduces the
    contradiction the `over_ceiling` splice exists to end (a red alarm on the same rendered
    line as the healthy gauge that denies it). One line, one claim.
    """
    if _flag(b.get("unmeasurable")):
        # Operand-NEUTRAL wording: this helper serves the index, the project CLAUDE.md and the
        # user-global CLAUDE.md, and naming one of them made the other two's rows read as though
        # the INDEX had failed. The caller's row label supplies the subject; this supplies the fact.
        return _c("  ⚠ UNMEASURABLE — exists but could not be read", "red")
    return ""


def _outcome(record: Mapping[str, Any]) -> str:
    # L4 (v0.4.2): the single source lives in memory_status.outcome_of — the banner, the log
    # column, and the HTML embed share ONE vocabulary (the v0.1.37 pivoted-maintenance carve-out
    # and the explicit `outcome` override are both inside it).
    return ms.outcome_of(record)


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
        return _clean(p.get("name", "?")) or "?", _clean(_SC.get(p.get("scope", ""), p.get("scope", "")))
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
    if "universal" in t or "stack" in t:
        out.append("    " + _c(f"{_g(t.get('universal', 0))} baseline · {_g(t.get('stack', 0))} this-stack "
                               "(everyone-holds vs facts only some share)", "dim"))

    shown = sorted(nodes, key=lambda d: -_num(d.get("always_loaded_tokens", 0)))
    cap = 12
    namew = min(max((_ui.disp_w(_clean(n.get("node", "?")) or "?") for n in shown[:cap]), default=4), 18)
    for n in shown[:cap]:
        # v0.4.34 (E3): the fallback goes INSIDE the slice. The first cut of this repair spliced
        # `or "?"` in BEFORE the subscript — `_clean(n.get("node", "?")) or "?"[:18]` — so `[:18]`
        # bound the LITERAL and not the name: a no-op, leaving a long node name unsliced while
        # `namew` stayed clamped to 18. This comment called that "appended `or "?"` to the whole
        # expression" until the fifth pass — which is the OTHER reconstruction, `(_clean(...) or
        # "?")[:18]`, and that one keeps the truncation and measures GREEN, so a reader rebuilding
        # from the prose would have concluded the claim was false. The truncation is part of the
        # value being defaulted, not of the default.
        #
        # Nothing downstream catches that: `namew` above is clamped to 18, and `pad` below is
        # `max(0, namew - disp_w(nm))`, which cannot go negative — so an over-long name gets the
        # SAME pad (0) as one that exactly fills the column, and simply overruns it. The row is
        # then exactly its excess wider than the column `namew` sized (measured: 26 → 36 columns
        # on a 28-column name). A clamp that saturates at the boundary is not a check on it.
        nm = (_clean(n.get("node", "?")) or "?")[:18]
        pad = " " * max(0, namew - _ui.disp_w(nm))
        star = _c("*", "cyan") if n.get("trigger") else " "
        mark = _c("  ◀ dream ran here", "cyan") if n.get("trigger") else ""
        share = f"{_g(n.get('shared', 0))} {_lbl('shared')}"
        if "universal" in n or "stack" in n:
            share += (f" · {_g(n.get('universal', 0))} {_lbl('baseline')} · "
                      f"{_g(n.get('stack', 0))} {_lbl('this-stack')}")
        out.append(f"    {star} {nm}{pad}  {_lbl('always')} ≈{_g(n.get('always_loaded_tokens', 0)):>5}  "
                   f"{_lbl('recall')} ≈{_g(n.get('recall_tokens', 0)):>7}  {_g(n.get('facts', 0)):>3} {_lbl('facts')} · "
                   f"{share}{mark}")
    if len(shown) > cap:
        out.append(f"      … +{len(shown) - cap} more node(s)")
    if not nodes:
        if al or rc:
            out.append("      (node rows not captured this pass — totals above are the fleet's)")
        else:
            out.append("      (no nodes hold shared facts yet)")
    # v0.4.13 fleet-topology layers — ONE honest line, key-gated (absent keys =
    # legacy record, no line; the pin at smoke keeps this honest).
    if net.get("basis_scope") == "fleet":
        _layers = []
        if isinstance(net.get("domains"), list) and net["domains"]:
            _layers.append(f"{len(net['domains'])} domain band(s)")
        if isinstance(net.get("group_links"), list) and net["group_links"]:
            _layers.append(f"{len(net['group_links'])} routed group(s)")
        if isinstance(net.get("universal_facts"), list) and net["universal_facts"]:
            _partials = sum(1 for u in net["universal_facts"]
                            if int(u.get("held") or 0) < int((_dget(net, "totals") or {}).get("nodes") or 0))
            _layers.append(f"{len(net['universal_facts'])} baseline fact(s)"
                           + (f" ({_partials} partial)" if _partials else ""))
        if _layers:
            out.append("    " + _c("topology: " + " · ".join(_layers), "dim"))

    # This cycle's lifecycle on the triggering node — derived, not hand-counted.
    entries = _lget(record, "entries")
    cnt = {k: sum(1 for e in entries if e.get("action") == k) for k in _actions()}
    parts = [f"{g} {cnt[k]} {lbl}" for k, (g, lbl, _col) in _actions().items() if cnt[k]]
    idx = _dget(_dget(record, "budget"), "index")
    xp = _dget(record, "cross_project")
    trig = _clean(net.get("trigger", "?")) or "?"
    # DOUBLE-SPACE join (not ' · ') — same reason as the Changes legend: the skip glyph
    # '·' must not read as a doubled dot beside a '·' separator.
    # v0.4.35 (RC-3): the fallback names the set this line actually TESTS — every name in
    # ACTION_VOCAB, not the write subset. It read "no writes" for a matcher that spans all five
    # actions, so the one string the line emits when it found nothing described a smaller
    # question than the one it asked.
    out.append(f"    {_lbl('this cycle on')} {trig}: " + ("  ".join(parts) if parts else "no actions recorded"))
    extras = []
    if "after_tokens" in idx:
        # ⚠ The unread index must not be summarised as a PAIR OF NUMBERS. "≈0 → ≈0 tok" is a
        # measured-looking claim built from a read that failed, and it is the shape this whole
        # line is scanned for. Say what happened instead.
        if _flag(idx.get("unmeasurable")):
            extras.append("always-loaded: UNMEASURABLE — the index exists but could not be read")
        else:
            extras.append(f"always-loaded ≈{idx.get('before_tokens', 0)} → ≈{idx.get('after_tokens', 0)} tok")
    if xp.get("gc_removed"):
        extras.append(f"gc {xp['gc_removed']} orphan(s)")
    if xp.get("refreshed"):
        extras.append(f"{xp['refreshed']} refreshed")
    if extras:
        out.append("      " + _c(" · ".join(extras), "dim"))
    return out


def _procedure_integrity_section(record: Mapping[str, Any]) -> list:
    """v0.1.44: the loud PROCEDURE INTEGRITY panel — the lazy-skip detector's user-visible teeth.
    Empty (no panel) when the verdict is ok. The CALLER gates this on --persist (only a completed,
    persisting dream is judged; a seed/preview render is the dream's BEFORE state, not a skip)."""
    ok, reason, severity = ms.procedure_integrity(record)
    if ok:
        return []
    col = "red" if severity == "alert" else "yellow"
    out = ["", _rule()]
    out.append("  " + _c("⚠ PROCEDURE INTEGRITY", "bold", col)
               + _c("   · substantial-or-heavier pass, zero verification recorded", "dim"))
    out.append(_rule())
    out.append("    " + _ui.wrap(_clean(reason), hang=4))
    out.append("    " + _c("→ run the Phase-3 verification fan-out, then re-render (a clean pass clears this ⚠ + exits 0)", "dim"))
    return out


def _duty_gaps_section(record: Mapping[str, Any]) -> list:
    """v0.4.33: the record-DUTY panel — the presence gate's user-visible teeth. Empty (no panel)
    when every duty the pass SEEDED was filled. The CALLER gates this on --persist, exactly like
    the two panels above it, and here that gate is the WHOLE era test: `duty_gaps` cannot tell a
    seed from a finished pass (the seed writes session:"" / applied:"" by design) and must not try
    to — see its docstring. Both panel and exit ride the same `judged` so they cannot disagree
    about WHICH RECORD is being judged.

    That is a claim about the era gate, NOT a claim that panel and exit can never desync — the
    first cut of this docstring made the stronger claim, the same one `_arc_gate_section`'s
    docstring was already corrected for, and it is false for the same reason. TWO arms return
    after this panel has printed (main prints the dashboard, THEN runs `_persist`):
      · `no-dir`/`io-error` — an unappendable log exits 0 a few lines below, so a gating duty
        renders "⚠ RECORD DUTY GAPS" beside a clean exit. Named open in spec §5 with the arc arm's
        identical hole; closing it changes the exit ladder, so it is carried, not fixed here.
      · the WARN-ONLY path — a gap whose every FIRED ROW is `warn` exits 0 by design (see
        `_DUTY_CLAUSES`: severity is per-row, and the `alert` rows returned 3 above), so the
        panel is the whole report. That one is intended, and the cue below says so in its own
        words rather than announcing a clean persist over a printed ⚠. Stated as the relation
        and not as a roster: this read *"clause A alone"*, which went false the moment a second
        row shipped at `warn` severity.

    Every word that NAMES the gap comes from the fired ROW (`label`, `detail`, `remedy`); the
    panel's FRAME — header, subtitle and `→` — is shared, which is what makes the per-row text
    the only place a generic sentence could hide. Every clause carries its OWN remedy in its own
    row, and one generic sentence standing in for the family would be the same defect this cycle
    exists to fix, one layer up: a fixed label standing where derived data belongs. (v0.4.35: this
    sentence used to ENUMERATE the remedies — "fill a session id / record a tier / complete a
    trio" — which made it a third statement of the clause count in shipped prose, false the moment
    the table grew. The enumeration is gone rather than extended: an inventory of a list that
    grows is a statement that has to be maintained, and the relation it was reaching for is the
    one written here — every row carries its own remedy — which is true at any size.)

    **The subtitle counts ROWS, and its wording now says so.** Its first cut read `%d seeded
    field(s)` over `len(gaps)` — and `len(gaps)` is fired CLAUSES, not fields. For clause C the two
    differ by construction: the trio is THREE fields, and the clause fires whenever they are not
    untouched-or-wholly-filled. So the audited defect shape (`{"achieved_index": 100}`) rendered
    "1 seeded field" directly above a row naming three fields, two of them blank — the count and the
    row beneath it disagreeing on screen. Both operands were defensible in isolation, which is what
    makes this worth recording rather than just patching: the defect was never the number, it was a
    LABEL naming one operand while the code used the other — this cycle's subject arriving in this
    cycle's own panel. The count is now the number of rows drawn (a reader can check it by counting
    them), and the FIELD count is left where the fields are actually named, in the rows."""
    gaps = ms.duty_gaps(record)
    if not gaps:
        return []
    col = "red" if any(g.severity == "alert" for g in gaps) else "yellow"
    out = ["", _rule()]
    out.append("  " + _c("⚠ RECORD DUTY GAPS", "bold", col)
               + _c("   · %d seeded dut%s the pass left unfilled"
                    % (len(gaps), "y" if len(gaps) == 1 else "ies"), "dim"))
    out.append(_rule())
    for g in gaps:
        out.append("    " + _ui.wrap(f"{g.label} — {g.detail}", hang=4))
        out.append("      " + _c(_ui.wrap("→ " + g.remedy, hang=8), "dim"))
    return out


def _arc_gate_section(record: Mapping[str, Any], enforce_post_arc: bool = False) -> list:
    """v0.4.1 (D1): the dream-arc gate's user-visible teeth — a PRESENT-but-incomplete arc
    (sleep/wake absent, != 6 beats, or a beat that is not a non-empty string) is loud here and
    exits 4 at the terminal --persist. Empty (no panel) when the arc is complete OR the record is
    dreamless (legacy/preview). The CALLER gates this on --persist, like the integrity panel.

    `enforce_post_arc` (v0.4.29; spec §2.4) rides in from the same `judged` gate as the exit-4 it
    explains: a panel that disagreed with the exit beside it would be worse than either. The
    desync is NOT impossible — the first cut of this docstring claimed it was, and the spec's own
    §2.4 records that claim as **measured false**. One path still desyncs and is named open in
    spec §5: `_persist` returning "io-error" (the cycle log cannot be appended) exits 0 at main's
    `no-dir`/`io-error` arm AFTER this panel has printed, so the screen says INCOMPLETE and the
    exit says clean. Measured end-to-end on a dreamless post-arc record with an unwritable log:
    panel printed, `cannot append to log: … Permission denied` on stderr, **exit 0**; the same
    record with a writable log exits **4**. Closing it changes the exit ladder, so it is carried
    as a named hole rather than fixed here."""
    arc_ok, arc_reason = ms.arc_completeness(record, enforce_post_arc=enforce_post_arc)
    if arc_ok:
        return []
    out = ["", _rule()]
    # The subtitle is DERIVED, not a literal: under `enforce_post_arc` the reason can be the
    # absent-block text, and a fixed "a present dream block must carry …" then asserts the very
    # rule the arm just exempted — measured, the panel printed both that headline and "dream
    # block absent" three lines apart, routing the operator to backfill a block that is not there.
    _sub = ("a present dream block must carry sleep + 6 beats + wake"
            if isinstance(record, dict) and "dream" in record
            else "no dream block, and this record's own keys date it after the arc mandate")
    out.append("  " + _c("⚠ DREAM ARC INCOMPLETE", "bold", "yellow")
               + _c("   · " + _sub, "dim"))
    out.append(_rule())
    out.append("    " + _ui.wrap(_clean(arc_reason), hang=4))
    # …and the REMEDY is derived from the same fact: an absent block is not a partial one, so
    # "backfill the missing beats" is the wrong instruction for it (there is nothing to backfill).
    _fix = ("→ backfill the missing beats (SLEEP · 5 phase beats + surfacing · WAKE), then re-render"
            if isinstance(record, dict) and "dream" in record
            else "→ the arc was skipped, so run it: the dream block was never written this pass")
    out.append("    " + _c(_fix + " — a complete arc clears this ⚠ + exits 0", "dim"))
    return out


def _narration_section(record: Mapping[str, Any], narration: Any,
                       enforce_post_arc: bool = False) -> list:
    """v0.4.19: the conversation-truth detector's panel (docs/dream-narration-teeth.spec.md).
    `narration` is the pre-print verdict dict or None (no --persist / dreamless legacy — no
    panel). SUPPRESSED when the record-side arc fails: the arc gate's own exit-4 panel + cue own
    that render (a contradictory NAR panel would double-report — pin (6) is a stdout contract,
    not just an exit contract). Verified = no panel; degraded = loud but honest (no exit change);
    failed = the gap names + first ~15 words so the backfill is targeted."""
    if narration is None or narration.get("verdict") == "verified":
        return []
    # The suppression test MUST use the same predicate as the panel and the exit above it
    # (spec §2.4's routing table): pin (6) is a no-contradictory-panel contract, so a NAR panel
    # firing beside a silent arc gate would break it in the one direction that reads as an
    # unqualified failure.
    arc_ok, _ = ms.arc_completeness(record, enforce_post_arc=enforce_post_arc)
    if not arc_ok:
        return []
    if narration.get("verdict") == "degraded":
        out = ["", _rule()]
        out.append("  " + _c("⚠ CONVERSATION-TRUTH UNVERIFIABLE", "bold", "yellow")
                   + _c("   · the transcript is unavailable — this pass was NOT narration-verified", "dim"))
        out.append(_rule())
        out.append("    " + _ui.wrap(_clean(narration.get("reason", "")), hang=4))
        out.append("    " + _c("→ the verdict is persisted on the record (nothing to fix — the honest degrade case)", "dim"))
        return out
    gaps = [g for g in (narration.get("gaps") or []) if isinstance(g, dict) and g.get("label")]
    # The header is per-arm: an EXT-only render (the single "extractor unaccounted" row) must
    # not misframe as a narration gap (review finding 8) — the stderr cue carries the remedy.
    if any(g.get("label") != "extractor unaccounted" for g in gaps):
        _sub = "dream text exists in the record but was never narrated in this session"
    else:
        _sub = "the Phase-2 extractor left no trace in this session"
    out = ["", _rule()]
    out.append("  " + _c("⚠ CONVERSATION-TRUTH GAPS", "bold", "red")
               + _c("   · " + _sub, "dim"))
    out.append(_rule())
    lines = []
    for g in gaps:
        label = _clean(g.get("label", ""))
        preview = _clean(g.get("preview", ""))
        lines.append(label + (f" — \"{preview}\"" if preview else ""))
    out.append("    " + _ui.wrap(" · ".join(lines), hang=4))
    out.append("    " + _c("→ narrate the missing beats in the conversation (or run the extractor / record the "
                          "extractor-skip: entry), then re-render — a narrated pass clears this ⚠", "dim"))
    return out


def _net_capture_section(record: Mapping[str, Any]) -> list:
    """v0.4.20: the NETWORK CAPTURE advisory (docs/network-capture-teeth.spec.md). Fires on a
    judged render when the record has a dream block (a full dream — the dreamless legacy
    carve-out extends) and `network.nodes` is NOT a list — absent OR present-without-nodes: the
    ONE predicate the panel, the beta oracle, and the archive's note ladder share (the producer
    always emits nodes, so a nodes-less block is never an honest capture and the terminal never
    reads it as one). Suppressed on a maintenance/bootstrap pivot (its scope excludes the
    capture BY DESIGN — mis-directing it would be a false positive on the most common no-op
    pass), with the string-coercion discipline (a model-authored `"false"` must not suppress).
    Advisory only — no exit change (the capture is an enrichment of a completed dream; the exit
    key stays frozen). The copy must avoid the phrase CONVERSATION-TRUTH (F19H's negative)."""
    if not isinstance(record.get("dream"), dict):
        return []
    m = _dget(record, "maintenance")
    pv = m.get("pivoted")
    if pv is True or str(pv).strip().lower() in ("true", "1"):
        return []
    if isinstance(_dget(record, "network").get("nodes"), list):
        return []
    out = ["", _rule()]
    out.append("  " + _c("⚠ NETWORK CAPTURE MISSING", "bold", "yellow")
               + _c("   · the fleet capture never ran or was not fully recorded", "dim"))
    out.append(_rule())
    out.append("    " + _ui.wrap(_clean(
        "run sync_global.py --tokens . --json --fleet and paste its full output into the "
        "record's network block, then re-render"), hang=4))
    return out


def _context_for_store(store: Any) -> Any:
    """v0.4.36: the StoreContext whose `native_memory_dir` IS `store` — or None.

    Extracted from `_narration_session_dir`, which has asked this question since v0.4.19 and has
    asked it correctly: the marker's script-owned `project_path` first, then cwd, each behind the
    ownership guard. What was NOT correct is the unenrolled-share warn below, which took
    `resolve_store(Path.cwd())` with no guard at all — so this is ONE HOME FOR THAT COPY, not for
    every copy. A third site, the usage-window clock, still resolves its own pair — cwd first, the
    marker as its fallback, and a skip branch neither caller here needs — and is deliberately left
    alone; its `v0.4.0 review (R128 clock liveness)` comment records why the guard is not optional,
    and that site's `except` already names `ValueError` beside `OSError`, the resolve-raise class
    the archive path had to be taught.

    Verification-only, like its caller: `resolve_store` answers "what does this DIRECTORY resolve
    to?", so a candidate is admitted only when the store it yields IS the store we were handed.

    Source 1 (the registry row) is deliberately not reproduced here, and NOT because it is inert:
    measured on a hermetic HOME, an un-enrolled project keeps its row (`status='active'`,
    `domain_id='unknown'`, `native_memory_dir` still this store), and `is_unenrolled_share` is
    `(not enrolled) or domain_id == "unknown"` — so the warn FIRES rather than returning early, and
    with no marker and a foreign cwd this helper answers None and that project loses one advisory
    (skipped loudly, never silently). A row is a STORED KEY, not a resolution: admitting it returns
    a context whose `session_dir` rests on a root nothing re-checked against the store — the
    mis-pooled transcripts `_narration_session_dir` forbids. Ask the directory, not the ledger. Its
    home is the registry lookup the archive path consumes.
    """
    from pathlib import Path as _P
    try:
        st_raw = (_P(str(store)) / ms.STATE_FILE).read_text(encoding="utf-8")
        st = json.loads(st_raw)
        pp = str(st.get("project_path") or "") if isinstance(st, dict) else ""
        if pp:
            from store_context import resolve_store as _rs_a
            _ctx_a = _rs_a(_P(str(pp)))
            # Ownership guard (the usage-clock fallback's precedent): a stale/migrated
            # project_path must NOT mis-pool the transcripts to the wrong project — only
            # return the context when the resolved store IS the store being persisted.
            if _ctx_a.native_memory_dir.resolve() == _P(str(store)).resolve():
                return _ctx_a
    except Exception:
        pass
    try:
        from store_context import resolve_store as _rs_b
        _ctx_c = _rs_b(_P.cwd())
        if _ctx_c.native_memory_dir.resolve() == _P(str(store)).resolve():
            return _ctx_c
    except Exception:
        pass
    return None


def _narration_session_dir(store: Any) -> Any:
    """v0.4.19: the transcript pool for the narration detector, resolved from the PERSISTED
    STORE's identity — NEVER ambient cwd (render_dashboard operates cross-cwd today; a
    wrong-store pool could satisfy NAR on a fabricated record with a byte-identical scripted
    beat — a cross-project false-clean in the forbidden direction). Order: (1) the store's own
    state file project_path → resolve_store (the script-owned anchor); (2) cwd resolves to THIS
    store (the usage-clock check's shape); (3) the default layout — the session pool is the
    native memory dir's parent (store_context: session_dir = cfg/projects/<slot>, native =
    session_dir/"memory"); (4) None → the caller degrades honestly."""
    from pathlib import Path as _P
    _ctx = _context_for_store(store)
    if _ctx is not None:
        return _ctx.session_dir
    try:
        _p_store = _P(str(store))
        if _p_store.name == "memory" and _p_store.parent.is_dir():
            return _p_store.parent
    except Exception:
        pass
    return None


def _narration_project_root(store: Any) -> Any:
    """v0.4.39: the store's project ROOT path — the second input the narration pool needs.

    `_narration_session_dir` resolves the SLUG dir, and `judge`'s window globs only that dir; but CC
    keys the transcript to the cwd while the store keys to the nearest `.git` ancestor, so a session
    started in a SUBDIRECTORY wrote to `-<store-slug>-sub` and no candidate could ever satisfy NAR on
    it (`extract_signals._subdir_transcripts` is the same repair on the extractor's arm). Deliberately
    a second `_context_for_store` call rather than a changed return contract: its sibling above has two
    load-bearing fallbacks (cwd-resolves-to-this-store, default layout) not worth re-plumbing for one
    optional argument. None → `judge` keeps the single-directory pool."""
    _ctx = _context_for_store(store)
    return getattr(_ctx, "project_root", None) if _ctx is not None else None


def render(record: ms.CycleRecord, *, judged: bool = False, narration: Any = None) -> str:
    if not isinstance(record, dict):
        record = {}  # a non-dict record (JSON list/scalar from stdin) degrades — this is the runtime boundary
    out: list = []
    proj = _clean(record.get("project", "?")) or "?"
    ses = _clean(record.get("session", "?")) or "?"
    oc = _outcome(record)

    # Banner — a centered rule with the title left, outcome right. Padding is computed on
    # PLAIN text length, then color is applied, so codes never throw off the alignment.
    title = "✦ DREAM · consolidate-memory"
    out.append(_rule())
    if W - 2 - len(title) - len(oc) < 4:
        # A long derived outcome (e.g. MAINTENANCE PASS · self-heal / cross-node enrichment) cannot
        # share the banner line — the gap math floors at 2 and the line would overflow W. Put the
        # outcome on its own line instead of breaking the grid.
        out.append("  " + _c("✦", "cyan") + title[1:])
        out.append("  " + _outcome_colored(oc))
    else:
        out.append("  " + _c("✦", "cyan") + title[1:] + " " * max(2, W - 2 - len(title) - len(oc)) + _outcome_colored(oc))
    out.append("  " + _c(f"{proj} · session {ses}", "dim"))
    out.append(_rule())

    # v0.1.44: PROCEDURE INTEGRITY — the lazy-skip detector's panel, RIGHT after the banner so it's
    # unmissable. Gated on `judged` (set by main() iff --persist): only a completed, persisting dream
    # is judged — a seed/preview render (no --persist) is the BEFORE state and is never flagged.
    if judged:
        out += _procedure_integrity_section(record)
        out += _arc_gate_section(record, enforce_post_arc=True)
        out += _duty_gaps_section(record)
        out += _narration_section(record, narration, enforce_post_arc=True)
        out += _net_capture_section(record)

    # v0.3.0: domain / enrollment — the trust-boundary line the HTML masthead also
    # carries. Absent on pre-0.3 records (legacy render is byte-identical).
    ident = _dget(record, "identity")
    if ident:
        dom = _clean(ident.get("domain_id", "unknown")) or "unknown"
        enrolled = _flag(ident.get("enrolled"))
        xpa = _flag(ident.get("cross_project_allowed"))
        if enrolled and xpa and dom != "unknown":
            id_bits = [f"domain {dom}", "enrolled"]
        else:
            id_bits = [_c("LOCAL-ONLY", "yellow")]
        rs = _clean(ident.get("registry_state", ""))
        if rs and rs not in ("absent", "healthy"):
            id_bits.append(_c(f"registry {rs}", "red"))
        nconf = _num(ident.get("conflicts", 0))
        if nconf:
            id_bits.append(_c(f"{_g(nconf)} open conflict(s)", "yellow"))
        out.append(_kv("IDENTITY", " · ".join(id_bits)))

    # v0.4.16: environment pre-flight — one red line when fails were recorded (additive;
    # legacy records skip the block entirely).
    _pf16 = _dget(record, "preflight")
    if isinstance(_pf16, dict):
        _pf_fails = _pf16.get("fails")
        if isinstance(_pf_fails, list) and _pf_fails:
            out.append(_kv("PRE-FLIGHT",
                           _c("%d environment check(s) failed (%s) — run cm doctor for the fixes"
                              % (len(_pf_fails), ", ".join(str(x) for x in _pf_fails)), "red")))

    # Scope + Verification (aligned label column)
    s = _dget(record, "scope")
    out.append("")
    _gr = s.get("git_range")
    if isinstance(_gr, str) and _gr.startswith("-") and _gr[1:].isdigit():
        # memory_status's "-N" = the recent-N lookback a MARKERLESS first dream scopes to — an internal
        # convention that read like a broken range ("git -20"). Translate, don't leak the sentinel.
        _gr = f"recent {_gr[1:]} (no marker)"
    _gr = _clean(_gr or "?")
    out.append(_kv("SCOPE", f"git {_gr} · {_g(_num(s.get('git_commits', 0)))} commits · "
                            f"{_g(_num(s.get('session_candidates', 0)))} candidates · {_g(_num(s.get('memories_reviewed', 0)))} reviewed"))
    v = _dget(record, "verification")
    method = f"   {_c('[' + _clean(v['method']) + ']', 'dim')}" if v.get("method") else ""
    _conf, _corr, _unv = _num(v.get("confirmed")), _num(v.get("corrected")), _num(v.get("unverifiable"))
    bits = [f"{_c('✓', 'green')} {_g(_conf)} confirmed",
            f"{_c('~', 'yellow')} {_g(_corr)} corrected" if _corr else "0 corrected"]
    if _unv:
        # v0.4.22 (U1): the ⚠ names its claims — the marked rows' names join after the count
        # (cap-with-counter), falling back to the bare count when no marked rows exist (legacy
        # records render unchanged). Derived from _lget directly (module-scope; the CHANGES
        # extraction below runs later). The reason is bound to a variable first (mypy never
        # narrows a repeated method-call expression).
        _unv_names = []
        for _e in _lget(record, "entries"):
            if isinstance(_e, dict):
                _r = _e.get("reason")
                if isinstance(_r, str) and _r.startswith("unverifiable:"):
                    _unv_names.append(_clean(_e.get("name") or "?"))
        _unv_bit = f"{_c('⚠', 'yellow')} {_g(_unv)} unverifiable"
        if _unv_names:
            _unv_rest = len(_unv_names) - 3
            _unv_bit += " — " + ", ".join(_unv_names[:3]) + (f" +{_unv_rest} more" if _unv_rest > 0 else "")
        bits.append(_unv_bit)
    out.append(_kv("VERIFIED", " · ".join(bits) + method))

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
                applied_note = _c(f" · override: {reason}", "dim") if reason else ""
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
    entries = [e for e in _lget(record, "entries") if isinstance(e, dict)]
    if not entries:
        out.append("    (none)")
    else:
        for key, (glyph, label, gcol) in _actions().items():
            for e in [x for x in entries if x.get("action") == key]:
                # SELF-LABELLING rows: glyph + the action WORD + the memory name. Spelling
                # out the action ("added" / "skipped" / …) means a skipped entry is
                # obviously skipped — no glyph-only guessing — and there is NO placeholder
                # column, so an entry with no tier/store never shows a stray '—'.
                out.append(f"    {_c(glyph + ' ' + f'{label:<10}', gcol)} {_clean(e.get('name', '?')) or '?'}")
                # Detail line (dim, consistent order): where-it-landed · scope · why ·
                # [source]. Empty parts collapse, so it reads as prose with nothing to
                # misalign and never starts with a dash.
                # _clean (which str()s) is applied PER PART, before the join — a
                # non-string tier/store (model slip) would otherwise crash the join.
                where = "/".join(_clean(p) for p in (e.get("tier"), e.get("store")) if p and p != "-")
                scope = _clean(_SC.get(e.get("scope", ""), e.get("scope", "")))
                # Scope renders WITHOUT angle brackets: '<proj>' read like an unrendered template
                # token (the render-chain audit measured that reading) — and a literal '-' scope must
                # not wrap itself into '<->' (tier/store filter for '-' above; scope didn't).
                scope = scope if scope and scope != "-" else ""
                reason = _clean(e.get("reason") or "")
                cite = _clean(e.get("citation") or "")
                parts = [p for p in (where, scope, reason,
                                     f"[{cite}]" if cite else "") if p]
                if parts:
                    # Wrapped via _kv (hanging-indent, width-bounded) — the old raw append let a
                    # ~330-char reason run past W and break the one-column grid.
                    out.append(_kv("", _c(" · ".join(parts), "dim")))

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
        # ⚠ Same rule as the index gauge above: an UNMEASURED operand gets the fault, not a gauge.
        # `_bar(0, 4000)` draws a full-green empty bar and `note` would report a fabricated delta
        # from the fault's zeros — two false claims on the line whose whole job is to price the
        # tier that loads in every session.
        if _flag(cm.get("unmeasurable")):
            _brow("project CLAUDE.md", "?", _unmeasurable(cm).strip())
        else:
            at, bt = cm.get("after_tokens", 0), cm.get("budget_tokens", 0)
            dln = _num(cm.get("after", 0)) - _num(cm.get("before", 0))
            note = (f"  {'+' if dln >= 0 else ''}{_g(dln)} ln" if dln else "")
            _brow("project CLAUDE.md", f"≈{_g(at)}/{_g(bt)}", f"{_bar(at, bt)} {_pct(at, bt)}{note}{_over(cm)}")
    # ⚠ `present` is `bytes > 0`, which a FAILED read reports as False — so testing it alone made
    # an unreadable global CLAUDE.md render as though there were no global tier at all. That is the
    # worst available reading: a row that disappears is indistinguishable from a row that was
    # never warranted, and this is the one operand every session of every project pays.
    if _flag(gcm.get("unmeasurable")):
        _brow("global CLAUDE.md", "?", _unmeasurable(gcm).strip())
    elif gcm.get("present"):
        adv = _c("  ⚠ heavy — loads in every project", "yellow") if _flag(gcm.get("over")) else ""
        _brow("global CLAUDE.md", f"≈{_g(gcm.get('tokens', 0))}", f"read-only · every project{adv}")
    if idx:
        at, bt = idx.get("after_tokens", 0), idx.get("budget_tokens", 0)
        dln = _num(idx.get("after_lines", 0)) - _num(idx.get("before_lines", 0))
        note = (f"  {'+' if dln >= 0 else ''}{_g(dln)} ln" if dln else "")
        # v0.1.63 (Phase A): cliff + fat-hook telemetry on the gauge tail (keys absent on a legacy
        # record → tail unchanged). Thresholds come from ms (already imported for the record type).
        # v0.1.66 (Phase B): the hard-ceiling flag — ADDITIVE beside the target `_over(idx)` flag, never
        # replacing it; sourced from remediation.over_ceiling (absent on legacy records → tail unchanged).
        # v0.4.45: an UNMEASURED index has no gauge, so the fault REPLACES the whole tail rather than
        # qualifying it. Three leaves of that tail would each fabricate here: `_bar(0, 1500)` draws a
        # full-green empty bar, `_pct` prints "0%", and `note` reports a shrink by `before_lines` —
        # the fault's 0 read as a delta. One line, one claim.
        tail = _unmeasurable(idx) or f"{_bar(at, bt)} {_pct(at, bt)}{note}{_over(idx)}"
        if _flag(_dget(record, "remediation").get("over_ceiling")):
            tail += _c(f" ⚠ HARD CEILING ≈{_g(idx.get('ceiling_tokens', 0))}t — M1 holds new pulls", "red")
        _cp = _num(idx.get("cliff_pct", 0))
        if _cp:
            tail += _c(f" · cliff {_g(_cp)}%", "red" if _cp >= int(ms.CLIFF_NEAR_FRACTION * 100) else "dim")
        _fh = _num(idx.get("fat_hooks", 0))
        if _fh:
            tail += _c(f" · hooks {_g(_fh)}>{ms.HOOK_TOKEN_WARN}t (max ≈{_g(idx.get('hook_max_tokens', 0))})", "yellow")
        _brow("auto-mem index", f"≈{_g(at)}/{_g(bt)}", tail)
        # D1/D2 defensive (v0.1.21): the gauge sources budget.index; the TRIGGER network-node has the same
        # index (its always_loaded_tokens). A GROSS divergence = the wrong-budget class the /tmp/cycle.json
        # collision produced (885 vs 2771 = 3×). Advisory only, generous tolerance (>1.5×) → never false-warn.
        _trig = next((n for n in _lget(_dget(record, "network"), "nodes") if isinstance(n, dict) and n.get("trigger")), None)
        if _trig:
            _itok, _ntok = _num(at), _num(_trig.get("always_loaded_tokens", 0))
            if _itok and _ntok and max(_itok, _ntok) / max(1, min(_itok, _ntok)) > 1.5:
                out.append("    " + _c(f"⚠ budget sources disagree — gauge ≈{_g(_itok)} vs trigger node ≈{_g(_ntok)}: "
                                       "possible cycle-record collision (check the --seed path)", "red"))
    if rf:
        d = _num(rf.get("after", 0)) - _num(rf.get("before", 0))
        _brow("recall facts", _g(rf.get("after", 0)), (f"{'+' if d >= 0 else ''}{_g(d)} fact(s)" if d else ""))
    if not (cm or idx or rf or gcm.get("present")):
        out.append("    (unchanged)")
    # v0.1.22 (read-only): the WHOLE CLAUDE.md hierarchy. CC loads CLAUDE.md hierarchically, so the load-bearing
    # number is worst_path — a session in the heaviest subtree pays every ancestor CLAUDE.md every turn.
    hier = _dget(_dget(record, "budget"), "claude_md_hierarchy")
    _cmbud = _num(cm.get("budget_tokens", 0)) or 4000
    # ⚠ `or _hier_unread_d` — same gate, same zeroing numbers: see the report's note. A row that
    # VANISHES is indistinguishable from one never warranted.
    _hier_unread_d = _num(hier.get("unreadable_count", 0)) if hier else 0
    if hier and (_num(hier.get("total_files", 0)) > 1
                 or _num(hier.get("worst_path_tokens", 0)) > _cmbud or _hier_unread_d):
        wt, wp = _num(hier.get("worst_path_tokens", 0)), _clean(hier.get("worst_path", "?")) or "?"
        heavy = _c("  ⚠ heavy", "yellow") if wt > _cmbud else ""
        _brow("CLAUDE.md tree", f"≈{_g(wt)}", f"{_g(hier.get('total_files', 0))} files · a session in {wp} pays this/turn{heavy}")

    # v0.1.63 (Phase A): organic recall utility this window — script-injected by extract_signals
    # --recalls --into (docs/index-usage-and-budget-ladder.spec.md). Absent on a legacy record → the
    # section collapses. PINNED BIAS: 0 reads = absence of evidence (retention + span-exclusion
    # undercount), never "unused" — the renderer reports counts; it never editorializes zeros.
    usage = _dget(record, "usage")
    if usage:
        out.append("")
        out.append("  " + _c("USAGE", "bold")
                   + _c("   · organic fact recalls this window (dream-procedure reads excluded)", "dim"))
        _ment = usage.get("mentions", 0)
        _ment_s = (_c(f" · {_g(_ment)} hook mention(s)", "dim")) if _ment else ""
        out.append(f"    {_g(usage.get('reads', 0))} read(s) over {_g(usage.get('facts_read', 0))} fact(s)" + _ment_s
                   + (("  " + _c(f"· {_g(usage.get('archive_reads', 0))} archive read(s)", "dim"))
                      if usage.get("archive_reads") not in (None, "", 0) else "")
                   + "  " + _c(f"{_g(usage.get('transcripts', 0))} transcript(s) · "
                              # PR-#98 review F4: dream_excluded now counts reads AND mentions — the label
                              # must not say "read(s)" (was imprecise once mentions joined the span split).
                              f"{_g(usage.get('dream_excluded', 0))} dream-procedure recall(s) excluded", "dim"))
        _ufact = [f for f in _lget(usage, "per_fact") if isinstance(f, dict)]
        _utop = _ufact[:3]
        if _utop:
            out.append("    " + _c("top:", "dim") + " " + " · ".join(
                f"{_clean(f.get('name', '?')) or '?'} ×{_g(f.get('reads', 0))}" for f in _utop)
                + (_c(f"  +{len(_ufact) - 3} more", "dim") if len(_ufact) > 3 else ""))
        # v0.1.67 (Phase C): the MISS-DETECTOR line — an archived-tier fact read organically is a
        # demotion error, rendered LOUD (it is the policy's own error signal). Key-presence gated:
        # a legacy/miss-free record (no `misses` key / empty) renders byte-identically.
        _miss = [m for m in _lget(usage, "misses") if isinstance(m, str)]
        if _miss:
            out.append("    " + _c(f"⚠ demotion MISS: {len(_miss)} archived-tier fact(s) read organically "
                                   f"({_g(usage.get('archive_reads', 0))} read(s)) — " + ", ".join(_clean(m) for m in _miss)
                                   + " · re-promote to MEMORY.md", "red"))

    # v0.1.67 (Phase C): the demotion-triage block — dormant/eligible + surfaced/struck + the one model
    # verdict sentence. Disposition COUNTS deliberately do NOT render from here — they are entries[] rows
    # and stay entries[]-derived (single source; the distill hand-mirror lesson). Key-presence gated:
    # a legacy record (no `demotion` key) renders byte-identically.
    demo = _dget(record, "demotion")
    if demo:
        out.append("")
        out.append("  " + _c("DEMOTION", "bold")
                   + _c("   · rank-under-budget triage (evidence-gated; report-then-apply)", "dim"))
        _dw, _de = _num(demo.get("windows_observed", 0)), _num(demo.get("eligible", 0))
        if _de:
            _surf = [s for s in _lget(demo, "surfaced") if isinstance(s, str)]
            _stk = [s for s in _lget(demo, "struck") if isinstance(s, str)]
            line = f"    {_g(_de)} eligible over {_g(_dw)} probative window(s)"
            if _surf:
                line += "  " + _c("surfaced: " + ", ".join(_clean(s) for s in _surf), "yellow")
            out.append(line)
            if _stk:
                out.append("    " + _c("struck (read THIS window — never demote): " + ", ".join(_clean(s) for s in _stk), "dim"))
        else:
            out.append("    " + _c(f"dormant — {_g(_dw)} probative usage window(s) accrued (wakes per-fact as evidence accrues)", "dim"))
        _dv = _clean(demo.get("verdict", ""))
        if _dv:
            import re as _re41
            _dv = _re41.sub(r"^\s*eligible\s+\d+\s*(?:→|—|-)?\s*", "", _dv)
            out.append("    " + _c("verdict: ", "dim") + _dv)

    # Remediation gate (v0.1.18) — present ONLY when the index was over budget. Shows whether the gate was
    # ACTED on (pruned>0 / justified / gc) — a fired-but-unacted gate (pruned 0, lever prune) stays visible.
    rem = _dget(record, "remediation")
    # v0.1.66 (Phase B): the hard-ceiling line — renders in BOTH branches below (the ceiling is
    # standing-justify-INDEPENDENT; suppression of the target gate never hides it). Falsy/absent → nothing.
    _ceil_ln = ("    " + _c("⚠ HARD CEILING exceeded — M1 holds ALL new pulls; standing-justify does not "
                            "apply to the ceiling; shrink to receive", "red")) if rem.get("over_ceiling") else ""
    if rem and rem.get("standing_justified"):
        # v0.1.21 (D6/D7): over budget but the density is STANDING-JUSTIFIED — gate suppressed, no re-surface.
        out.append("")
        out.append("  " + _c("REMEDIATION", "bold") + _c("   · over-budget gate · STANDING-JUSTIFIED (suppressed)", "dim"))
        out.append(f"    {_c('✓', 'green')} density justified at baseline {_g(rem.get('baseline_facts', 0))} facts — gate suppressed until +Δ facts or index-token bloat")
        if _ceil_ln:
            out.append(_ceil_ln)
        # v0.4.61 (RC-1): ⚠ THE CEILING IS STANDING-JUSTIFY-INDEPENDENT, AND SO IS ITS INSTRUMENT.
        # The line above was hardened against the suppression long ago; the triage behind it was not,
        # so this branch printed "shrink to receive" and NOTHING else — and an empty candidate list
        # reads as the verdict "nothing is prunable". The producer relays the triage operands exactly
        # when the store is over the ceiling; render them here. ⚠ `candidates_surfaced` absent keeps
        # the short form, so a merely-suppressed store and every archived record are unchanged.
        if _recorded(rem, "candidates_surfaced"):
            _cj = _num(rem.get("candidates_surfaced", 0))
            out.append("    " + _c(f"{_g(_cj)} candidate(s) surfaced · lever "
                                   f"{str(rem.get('lever') or '-').upper()} · "
                                   + (f"projected index ≈{_g(_num(rem.get('projected_index', 0)))} tok"
                                      if _recorded(rem, "projected_index")
                                      else "projected index: not recorded"), "dim"))
            # v0.4.61 (review): ⚠ THE D5 REMEDY IS KEYED ON THE LEVER, NOT ONLY ON THE OPERAND — exactly
            # as `memory_status._remediation_section` keys it. Gating on `reaches_budget is False` ALONE
            # printed "prune can't reach budget → prune-then-justify" directly beneath a line reporting
            # `lever JUSTIFY · 0 candidate(s) surfaced`: two renderers of one record disagreeing three
            # lines apart, and the panel contradicting itself. RC-2 makes `reaches_budget` False whenever
            # the candidates cannot free nearly the whole index — the common mature-store case — so this
            # was newly reachable, not hypothetical.
            if str(rem.get("lever") or "") == "prune" and rem.get("reaches_budget") is False:
                out.append("    " + _c(_D5_REMEDY, "dim"))
    elif rem and rem.get("required"):
        # v0.1.36: gate on `required`, NOT mere presence — a healthy record may carry remediation={required:false}
        # (the schema default), which must NOT render an over-budget block (it did pre-v0.1.36: `elif rem:`). The
        # standing_justified branch above handles required=false+suppressed; an absent/required-false record → nothing.
        out.append("")
        out.append("  " + _c("REMEDIATION", "bold") + _c(f"   · over-budget gate · lever {str(rem.get('lever', '')).upper()}", "dim"))
        if _ceil_ln:
            out.append(_ceil_ln)
        # v0.4.34 (E1): the verdict is DERIVED from the data, never looked up by `lever`. `lever` is a
        # ROUTING label the producer picked; keying the verdict on it meant one rewritten field swapped the
        # panel's meaning (a `prune`→`justify` relabel turned the ⚠ alarm into "nothing safely prunable")
        # and the reassuring sentence rendered whether or not the data supported it. The outcome space is
        # (lever, candidates_surfaced, pruned, achieved_index, reaches_budget); the branches below walk it
        # in the order the code actually has, the pre-Phase-5 seed included.
        #
        # `candidates_surfaced` ABSENT is not zero: `_num` maps absent→0, so the line would assert a count
        # the record does not carry — E3's absent-vs-empty defect living inside E1's own fix. The file's own
        # idiom for the absent case is the "pending Phase 5" arm directly below (never `≈0`).
        #
        # v0.4.34 (E1, second pass): that first cut closed ONE cell of a class with EIGHT. The panel reads
        # four numeric operands (candidates_surfaced · pruned · achieved_index · projected_index) and each
        # can fail to be carried in two ways — the key ABSENT (`total=False` makes that legal) or the key
        # PRESENT and blank (`None`/`""`: the declaration says `int`, but `_num` accepts both and coerces
        # them to 0.0). All four rendered a fabricated measurement in the BLANK form (4 cells), and
        # `pruned` / `achieved_index` / `projected_index` did in the ABSENT form too (3 more) — seven,
        # on the very line the fix had just claimed to have repaired. An enumeration naming only two
        # of the three absent operands sums to six and reads as an arithmetic error; the numeral was
        # right and the list was short. `_recorded` is the presence test that closes them; a rendered
        # measurement now implies the record carried one.
        cand, pi = _num(rem.get("candidates_surfaced", 0)), _num(rem.get("projected_index", 0))
        cand_txt = (f"{_g(cand)} candidate(s) surfaced" if _recorded(rem, "candidates_surfaced")
                    else "candidates surfaced: not recorded")
        pi_paren = (f"(projected ≈{_g(pi)})" if _recorded(rem, "projected_index")
                    else "(projected: not recorded)")
        pi_flat = (f"projected index ≈{_g(pi)} tok" if _recorded(rem, "projected_index")
                   else "projected index: not recorded")
        # The default is the module CONSTANT, not a literal (third pass). It was `1200`, which is neither
        # `INDEX_TOKEN_BUDGET` (1500) nor any value the producer writes — the record's own budget block is
        # seeded from the constant at the Phase-0 writer. So on a record carrying no `budget` key the panel
        # compared `achieved_index` against a threshold that does not exist, and at `{pruned: 0,
        # achieved_index: 1300}` it rendered "⚠ gate fired but not acted on" for an index that is UNDER the
        # real budget. Same class as E3: a default that is not the real value asserts a measurement.
        #
        # Fourth pass: that fix named the right VALUE and left the wrong SHAPE. `.get(k, CONST)` still
        # fires only on ABSENT — the exact form this file already rejected for `candidates_surfaced` and
        # `pruned` two lines up — so a `budget_tokens` PRESENT and blank fell PAST the constant into
        # `_num(None)`/`_num("")` → 0.0, and the lean test became `0 < achieved_index <= 0`. Measured at
        # `achieved_index: 1300` against the real 1500: key ABSENT → "✓ gate resolved by rebuild-lean";
        # key present and `None` or `""` → "⚠ gate fired but not acted on". Byte-identical operands,
        # opposite verdicts, decided only by HOW the threshold failed to be carried. The panel's operand
        # census did not reach it, but the reason is its LOCUS, not its reachability: the census samples
        # the four MEASURED operands, which print on the `↓` line, while the threshold prints one line
        # down through `_over` and only when `over` is set. "The census could not reach it" is therefore
        # true of the census as written and false of the operand — an extended census would reach it.
        # RECORDED, not fixed: `_over` prints this threshold RAW, so a record hand-edited to carry
        # `None`/`""` renders "⚠ OVER ≈None tok BUDGET" — an absence occupying a measurement slot. No
        # producer can reach it (memory_status writes this key from a module constant, in the same
        # expression that sets `over`, so the two cannot disagree there), which is why it is recorded
        # here rather than repaired in this cycle. What `_recorded` DOES close is the LEAN comparison's
        # read of this key: a blank now falls back to the constant, so the blank spellings cannot move
        # THAT verdict. It cannot close `_over`, which never consults it — so the RAW print above stays
        # recorded rather than fixed, and the two readers of one key handle a blank differently by design.
        # RECORDED WITH IT, same reachability class and the same site: `_recorded` is a PRESENCE test, so
        # a present, non-blank, NON-NUMERIC threshold passes it and `_num` coerces the value instead.
        # Measured at `achieved_index: 1300`, `True` / `False` / `"many"` become 1.0 / 0.0 / 0.0, the lean
        # test reads false, and all three render "⚠ gate fired but not acted on" — while the ABSENT and
        # BLANK spellings render "✓ gate resolved by rebuild-lean". The fourth pass's split therefore
        # survives one rung narrower: a non-number the presence test REJECTS is rescued by the constant,
        # and a non-number it ADMITS is compared, so the verdict follows the spelling of a value that is
        # never validated as a number. Hand-edit-only for the same reason as the row above, and left
        # unrepaired because the repair is a magnitude/type test on this operand, which is the coercion
        # the presence test exists to refuse.
        _bix = _dget(_dget(record, "budget"), "index")
        budget_tok = (_num(_bix.get("budget_tokens")) if _recorded(_bix, "budget_tokens")
                      else ms.INDEX_TOKEN_BUDGET)
        # Row 1: the seed OMITS pruned/achieved_* (pre-pass) — "pending Phase 5" IS this state's verdict,
        # so no note is derived for it below. G (v0.1.18.x) renders absent as "pending", NOT ≈0 ("emptied").
        # Keyed on `_recorded`, so present-but-blank reads the SAME as absent: a record that filled neither
        # is in the pre-Phase-5 state whether it spelled that with a missing key or with a null.
        pending = not (_recorded(rem, "achieved_index") or _recorded(rem, "pruned"))
        resolved_by_lean = False
        acted: Any = 0
        if not pending:
            pruned, ai = _num(rem.get("pruned", 0)), _num(rem.get("achieved_index", 0))
            pruned_txt = f"{_g(pruned)} pruned" if _recorded(rem, "pruned") else "pruned: not recorded"
            ai_txt = f"index ≈{_g(ai)} tok" if _recorded(rem, "achieved_index") else "index: not recorded"
            out.append(f"    {_c('↓', 'yellow')} {cand_txt} · {pruned_txt} · {ai_txt} {pi_paren}")
            # v0.1.35: "acted on" is NOT eviction-only. A rebuild-lean (pruned=0) that brought the index back
            # UNDER budget RESOLVED the gate — the skill sanctions "prune … and/or rebuild the index lean"
            # (Phase 5 step 0). Was `acted = pruned`, which mislabeled a resolved gate "not acted on".
            # The `0 <` bound is load-bearing: `_num` maps absent/None/"" → 0.0, so it is what keeps an
            # ABSENT achieved_index from reading as "under budget" and silently resolving the gate.
            resolved_by_lean = (not pruned) and (0 < ai <= budget_tok)
            acted = pruned or resolved_by_lean
        else:
            out.append(f"    {_c('↓', 'yellow')} {cand_txt} · pruned/achieved pending Phase 5 · {pi_flat}")
        # The mirror claim is keyed on the OPERAND, not the label. It says WHERE to act (the global
        # demote/GC lever), which is a different kind of claim from whether the gate was acted on — so it
        # is emitted independently of `acted`. It is paired with `not mirror_dominated` in the ACTION
        # verdict below, because for a mirror-dominated store a local prune is exactly the advice the
        # routing calls futile.
        #
        # Scope, because the first draft of this comment said "SUPPRESSES the local-prune advisory" and
        # that is true of one branch and false of its neighbour: `not mirror_dominated` sits on the
        # row-4-6 verdict branch ONLY. The D5 remedy above (`reaches_budget is False and not
        # resolved_by_lean`) is keyed on neither the label nor the share — it is a claim about a
        # different state, and it CO-RENDERS with this line, by design.
        share = rem.get("mirror_share")
        mirror_dominated = isinstance(share, (int, float)) and share > ms._MIRROR_DOMINATED
        if mirror_dominated:
            # v0.4.34 (review): `.0%` rendered "50%" for a share of 0.5025 — the SAME numeral as the
            # non-dominated boundary `_MIRROR_DOMINATED` (0.5), so the display discarded the very
            # distinction the routing above it used. One decimal of a percent restores it: shares are
            # ratios of index-token counts (~1500 tokens), so they quantize at ~1/1500 = 0.00067 and
            # the first step above the boundary renders "50.1%", not "50.0%".
            out.append("    " + _c(f"mirror-dominated ({share:.1%} of index tokens) — global demote/GC lever, not a local prune", "dim"))
        # Row 3 / D5 (v0.1.21): a full prune can't reach budget. This remedy IS the state's verdict, so it
        # is gated on the lean path NOT having resolved (v0.4.34): remedy and ✓ are one decision, and
        # emitting both put a sanction beside a SUCCESS (18 of 324 states).
        if rem.get("reaches_budget") is False and not resolved_by_lean:
            out.append("    " + _c(_D5_REMEDY, "dim"))
        if resolved_by_lean:
            out.append("    " + _c("✓ gate resolved by rebuild-lean — index back under budget, no eviction needed", "green"))
        elif not acted and not pending and not mirror_dominated and rem.get("reaches_budget") is not False:
            # Rows 4-6 — the action verdict, keyed on `candidates_surfaced`: present-and-positive,
            # present-and-zero, and absent are three different states and get three different sentences.
            # Row 5 no longer claims "nothing safely prunable" (a fact about the STORE that no field
            # carries); it states what the record actually says.
            if not _recorded(rem, "candidates_surfaced"):
                out.append("    " + _c("no candidate count recorded — whether the gate was actionable is not answerable from this record", "dim"))
            elif cand > 0:
                out.append("    " + _c("⚠ gate fired but not acted on — surface candidates + prune-or-justify", "yellow"))
            else:
                out.append("    " + _c("0 candidates surfaced — record the justification, or re-triage", "dim"))

    # AUDIT (v0.1.22) — the DETERMINISTIC, script-observed mutation trail for THIS pass (a content-hash diff),
    # the counterpart to the model-narrated entries[]. Present only once Phase 5 fills it.
    aud = _dget(record, "audit")
    if aud:
        out.append("")
        out.append("  " + _c("AUDIT", "bold") + _c("   · files this pass changed (script-observed; cf. entries[])", "dim"))
        any_change = False
        for store in ("memory", "claude_md", "repo_doc"):
            s = _dget(aud, store)
            cr, md, dl = _num(s.get("created", 0)), _num(s.get("modified", 0)), _num(s.get("deleted", 0))
            if cr or md or dl:
                any_change = True
                td = _num(s.get("token_delta", 0))
                out.append(f"    {store:<10} +{_g(cr)} created · ~{_g(md)} modified · −{_g(dl)} deleted · {'+' if td >= 0 else ''}{_g(td)} tok")
        # v0.1.24: relocate conservation — a gross CLAUDE.md drop with little relocate-target growth = possible loss.
        cons = _dget(aud, "conservation")
        if cons.get("possible_loss"):
            out.append("    " + _c(f"⚠ possible lost relocate — CLAUDE.md −{_g(cons.get('claude_md_drop', 0))} tok but "
                                   f"targets only +{_g(cons.get('repo_doc_growth', 0))}: verify this was a prune, not a dropped move", "yellow"))
        if not any_change:
            out.append("    " + _c("no file mutations detected this pass", "dim"))
        out.append("    " + _c(f"window {ms.AUDIT_WINDOW} — any change in the span is attributed to this pass", "dim"))

    # Cross-project (global tier) — aligned direction | scope | name; counts on one line.
    xp = _dget(record, "cross_project")
    if xp:
        out.append("")
        gtotal = xp.get("global_store_facts")
        head = "  " + _c("CROSS-PROJECT", "bold") + _c("   · global tier", "dim")
        if gtotal is not None:
            head += _c(f" · domain canonicals: {gtotal} fact(s)", "dim")
        out.append(head)
        pulled = xp.get("pulled") or []
        promoted = xp.get("promoted") or []
        for p in pulled:
            nm, sc = _item(p)
            sc = sc if sc and sc != "-" else ""
            out.append(f"    {_c('↓', 'cyan')} {_lbl('pulled', 10)}{sc:<8} {nm}")
        for p in promoted:
            nm, sc = _item(p)
            sc = sc if sc and sc != "-" else ""
            out.append(f"    {_c('↑', 'green')} {_lbl('promoted', 10)}{sc:<8} {nm}")
        moved = []
        if xp.get("refreshed"):
            moved.append(f"⟳ {xp['refreshed']} mirror(s) refreshed")
        if xp.get("gc_removed"):
            moved.append(f"− {xp['gc_removed']} orphan(s) reclaimed")
        if moved:
            out.append("    " + _c(" · ".join(moved), "dim"))
        if xp.get("held"):  # v0.1.38 (M1): the LOUD lever — a new-global pull was HELD (index over budget); the
            # most-relevant store starves until it prunes, so surface it prominently, not buried in the dim line.
            out.append("    " + _c(f"⚠ held {xp['held']} cross-node fact(s) — index past the hard ceiling; shrink to receive", "yellow"))
        if not (pulled or promoted or moved or xp.get("held")):
            out.append("    " + _c("(no cross-project movement this pass)", "dim"))

    # Neural network — token consumption across all nodes (the observability ask).
    # Guarded: legacy/no-op records without a `network` block skip it.
    net = _dget(record, "network")
    if net:
        out.extend(_network_section(record, net))

    # Health
    h = _dget(record, "health")
    if h:
        ok = _flag(h.get("index_pointers_ok", True))
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
        # ⚠ `index_mismatch` is MANUFACTURED by an unreadable index — an index nobody could open
        # names NOTHING, so every fact on disk reads as un-indexed — and `dashboard.sections.js`
        # ALREADY exempts it on exactly that argument. This renderer did not, so the dashboard
        # printed `⚠ schema drift: … 2 index↔file` two lines under its own
        # `auto-mem index ⚠ UNMEASURABLE`, while the archive suppressed the same count. One of the
        # two was wrong and the archive's argument is the one that holds: a count that exists only
        # because of the read failure is not a finding about the store. MEASURED by a review lens.
        _idx_unm_dr = _flag(_dget(_dget(record, "budget"), "index").get("unmeasurable"))
        _drift_keys = ["missing_node_type", "malformed_scope", "malformed_origin"]
        if not _idx_unm_dr:
            _drift_keys.append("index_mismatch")
        _drift_n = sum(_num(sd.get(k, 0)) for k in _drift_keys)
        if _drift_n > 0:
            bits.append(_c(f"⚠ schema drift: {_g(sd.get('missing_node_type', 0))} missing node_type · "
                           f"{_g(sd.get('malformed_scope', 0))} malformed scope · "
                           f"{_g(sd.get('malformed_origin', 0))} malformed originSessionId"
                           + ("" if _idx_unm_dr else f" · {_g(sd.get('index_mismatch', 0))} index↔file")
                           + (" · ⚠ index unreadable — index↔file cannot be counted"
                              if _idx_unm_dr else ""), "yellow"))
        out.append("")
        out.append(_kv("HEALTH", " · ".join(bits)))

    # v0.1.54: dream-arc capture presence — gated on the key, so legacy records (and seeds,
    # which never carry `dream`) render byte-identically. One line: which beats were captured;
    # a partial arc shows its gaps (✗) honestly. The stanzas themselves live in the HTML archive.
    # _dget/_lget = the file's model-boundary idiom. The ✓/✗ reads the SHARED stanza predicate
    # (v0.4.29): the old `bool(str(v or "").strip())` covered the JSON-null case and ONLY that
    # one, so a `sleep: [1]` record rendered `✓ sleep` against a gate exiting 4 `sleep missing`.
    dr = _dget(record, "dream")
    if dr:
        _beats = _lget(dr, "beats")
        _nb = len(_beats)
        _have = [ms.stanza_present(dr.get("sleep")), ms.stanza_present(dr.get("wake"))]
        # v0.4.1 (D1): the ✓ now gates on the SINGLE arc-completeness predicate (the same one the
        # persist gate + WAKE cue consume) — one definition, or the dashboard could green-check
        # while the gate exits 4. The contract is 5 phase beats + the surfacing line (6 total).
        _full = ms.arc_completeness(record)[0]
        _bits = [
            (_c("✓", "green") if _have[0] else _c("✗", "yellow")) + " sleep",
            (_c("✓", "green") if _full else _c("✗", "yellow")) + f" {_g(_nb)}/6 beat" + ("" if _nb == 1 else "s"),
            (_c("✓", "green") if _have[1] else _c("✗", "yellow")) + " wake",
        ]
        _emoji_hits = [i + 1 for i, b in enumerate(_beats) if _ui.BEAT_EMOJI_RE.search(str(b))]
        if _emoji_hits:
            # v0.4.23 (P2): name the offending beat(s) — 1-based, matching the archive's
            # Passage numbering (the record's 0-based array stays the internal convention).
            _bits.append(_c("⚠ emoji in beat(s): " + ", ".join(str(i) for i in _emoji_hits)
                            + " — the arc bans them outside the bookends", "yellow"))
        out.append("")
        out.append(_kv("DREAM ARC", " · ".join(_bits)))

    # v0.1.55: distill-verdict capture presence — gated on the key (legacy/seed records render
    # byte-identically). The verdict is the payload; counts frame it. HTML shows the full verdict.
    di = _dget(record, "distill")
    if di:
        # v0.1.57: the verdict renders IN FULL on its own wrapped line (was truncated at 60 —
        # unreadable mid-word cuts); counts stay on the labeled line. _kv("") = a label-aligned
        # continuation line with the same hanging-indent wrap. A generous 220-char bound remains —
        # the verdict is MODEL-authored ("one sentence" is guidance, not validation), and an
        # unbounded multi-sentence slip would inflate the fixed-rhythm dashboard.
        _dv = _clean(str(di.get("verdict") or ""))
        if len(_dv) > 220:
            _dv = _dv[:219] + "…"
        # v0.1.58: surface the firewall-suppression count — the transparency the secrets_omitted counter
        # exists for (CLAUDE.md: a schema key must reach the renderer, not just the JSON). Gated on > 0.
        _so = _num(di.get("secrets_omitted", 0))
        _nc = _num(di.get("n_chains", 0))
        out.append("")
        out.append(_kv("DISTILL", f"{_g(_num(di.get('n_recurring', 0)))} recurring · "
                                  f"{_g(_nc)} chain" + ("" if _nc == 1 else "s")
                                  + (f" · {_c(_g(_so) + ' secret-shaped', 'yellow')}" if _so else "")
                                  + ("" if _dv else " · " + _c("✗ no verdict", "yellow"))))
        if _dv:
            out.append(_kv("", _c(_dv, "dim")))
        # L2 (v0.4.2): the top recurring commands — the same USAGE `top:` idiom, capped at 3
        # (`template ×N Nd`). Key-presence gated: a legacy record without `top` renders
        # byte-identically.
        _dtop_all = [t for t in _lget(di, "top") if isinstance(t, dict)]
        _dtop = _dtop_all[:3]
        if _dtop:
            out.append("    " + _c("top:", "dim") + " " + " · ".join(
                f"{_clean(t.get('t', '?')) or '?'} ×{_g(t.get('n', 0))} "
                f"{_g(t.get('d', 0))}d" for t in _dtop)
                + (_c(f"  +{len(_dtop_all) - 3} more", "dim") if len(_dtop_all) > 3 else ""))

    # v0.1.87/W-C (registrar): the Tier-2 consult's evidence gets a RENDER SURFACE (the render-chain
    # audit measured it had none — "absent = the registrar was not consulted, a visible decision" was
    # an INVISIBLE one). Key-present renders the injected block; a record whose distill RAN without the
    # key renders the not-consulted line; legacy records (no distill key at all) stay untouched.
    _wp = _dget(record, "workflow_proposals")
    if _wp or "distill" in record:
        out.append("")
        if _wp:
            out.append("  " + _c("REGISTRAR", "bold") + _c("   · Tier-2 fleet placement (the W-C consult)", "dim"))
            _cands = [c for c in _lget(_wp, "candidates") if isinstance(c, dict)]

            def _distinctive_row(c: dict) -> bool:
                m = _dget(c, "mechanical")
                if "distinctive" in m:
                    return _flag(m.get("distinctive"))
                return ms._is_distinctive_template(
                    str(c.get("candidate") or ""), str(c.get("form") or "command"))

            def _engine_disp(c: dict) -> str:
                raw = _clean(c.get("disposition") or "")
                if raw in ("awaiting-confirmation", "confirmed", "declined"):
                    return raw
                if raw.startswith("blocked") or raw == "fleet-candidate":
                    return raw
                m = _dget(c, "mechanical")
                fleet = _flag(m.get("fleet_recurrence"))
                spread = _flag(m.get("day_spread"))
                if not _distinctive_row(c):
                    return "blocked: generic-cli"
                if fleet and spread:
                    return "fleet-candidate"
                if not fleet:
                    return "blocked: fleet-recurrence"
                return "blocked: day-spread"

            def _blocked_pri(c: dict) -> int:
                d = _engine_disp(c)
                if d == "blocked: day-spread":
                    return 0
                if d == "blocked: fleet-recurrence":
                    return 1
                return 2

            _fleet = [c for c in _cands
                      if _distinctive_row(c)
                      and _flag(_dget(c, "mechanical").get("fleet_recurrence"))
                      and _flag(_dget(c, "mechanical").get("day_spread"))]
            _blocked = [c for c in _cands if c not in _fleet]
            _blocked.sort(key=_blocked_pri)
            _REG_BLOCKED_CAP = ms._REGISTRAR_BLOCKED_CAP
            _n_fleet = _num(_wp["n_fleet"]) if _wp.get("n_fleet") is not None else len(_fleet)
            _n_blocked = _num(_wp["n_blocked"]) if _wp.get("n_blocked") is not None else len(_blocked)
            if _fleet:
                out.append("    " + _c(f"{_g(_n_fleet)} fleet-candidate(s) first, blocked capped at {_REG_BLOCKED_CAP}:", "dim"))
            for c in _fleet + _blocked[:_REG_BLOCKED_CAP]:
                _ev = _dget(c, "evidence")
                _mech = _dget(c, "mechanical")
                _nm = _clean(c.get("name") or c.get("candidate") or "?")
                _nds = ", ".join(_clean(x) for x in _lget(_ev, "nodes"))
                _d = _num(_ev.get("d")); _n = _num(_ev.get("n"))
                _disp = _engine_disp(c)
                _gates = " · ".join(_clean(k).replace("_", "-") for k, gv in _mech.items() if _flag(gv))
                _l = f"    {_c('◈', 'cyan')} {_nm} [{_clean(c.get('form', '?')) or '?'}]"
                if _nds:
                    _l += f" — nodes {_nds} · d={_g(_d)} n={_g(_n)}"
                _l += f" — {_disp}" + (f" · gates {_gates}" if _gates else "")
                out.append(_l)
            _shown_b = min(len(_blocked), _REG_BLOCKED_CAP)
            # v0.4.34 (E2): the record's `n_blocked` and the LOCAL display list are two different
            # sources, so when the record counts blocked rows and the display list draws none, "+N more
            # blocked" degrades to a false total — `more` ("beyond what is displayed") collapses to the
            # whole count with nothing displayed for it to be beyond, and the cold-state line two lines
            # below then denied the count it had just asserted. The HTML twin branches on `!board` and
            # emits a counts-only breakdown instead; the ASCII was the outlier.
            #
            # The guard is `_shown_b == 0` — no BLOCKED row drawn — and NOT `len(_fleet) + _shown_b == 0`.
            # The first cut of this repair copied the JS's `!board` shape, which computes something else:
            # the JS's counts-only branch ASSIGNS the board, so its guard exists to avoid clobbering the
            # cards, and the JS additionally states the blocked count in its `reg-counts` header. The
            # ASCII branch APPENDS and has no such header, so carrying the JS's guard over left the false
            # tail exactly where the producer actually builds it: `sync_global` persists ALL fleet-
            # candidates plus a capped day-spread sample, while `n_blocked` counts EVERY non-fleet
            # disposition — so ONE fleet row beside 20 generic-cli rows persists a one-card display with
            # `n_blocked: 20` and no blocked row in it. A guard's condition has to name the claim it
            # guards, not the shape of the port it came from.
            if _n_blocked > 0 and _shown_b == 0:
                _b_parts = []
                _n_gen = _num(_wp.get("n_generic", 0))
                if _n_gen > 0:
                    _b_parts.append(f"{_g(_n_gen)} generic-cli")
                # The remainder is `n_blocked − n_generic`: NO day-spread subtraction. That is the third
                # pass's correction, and the reason is the cycle's own subject one level down. The JS
                # subtracts it — `Math.max(0, n_blocked − n_generic − n_day_spread)` — and can afford to,
                # because the JS can only reach this branch with `n_day_spread == 0`: at `:146` a non-zero
                # field makes `nSpread` truthy, `:181` grows `board`, and the `!board` guard goes false.
                # So in the HTML the subtraction is a **no-op in every state that can print**. The ASCII
                # guard reads a DIFFERENT operand and is not closed by that field: `_shown_b` counts the
                # persisted blocked ROWS, so `n_day_spread > 0` does not make it false — only drawing no
                # blocked row does. Say which states those are, because the loose reading ("reachable
                # with a non-zero field") invites the wrong one: the producer cannot build that pair
                # (`_eval` gives `blocked: day-spread` only to a distinctive fleet row, and `sync_global`
                # persists every distinctive day-spread row, so a non-zero count always implies a drawn
                # row). It is live exactly where a record carries the COUNT with no row beside it — an
                # authored shape, which is the E2-f fixture. Carrying the subtraction across dropped
                # `n_day_spread` rows out of a line whose whole contract is that its parts account for
                # the total.
                #
                # The JS's third ARM (`n_day_spread` -> "N single-day") stays unported — it is unreachable
                # in the HTML, and by PROOF rather than by sampling: `num(n_day_spread, default) > 0` makes
                # `nSpread` truthy at :146, which grows `board` at :181 and makes the `!board` guard at :194
                # false, so :197 is never evaluated. Swept over the JS's reachable input space (17 values³ ×
                # 3 fallbacks × 2 `named` × 2 `evRows` = 58,956 states, see the spec): the BREAKDOWN rendered
                # in 1156 of them and a `single-day` part in 0. Which number is which matters — 1156 counts
                # the states where the breakdown RENDERED, not the reachable space, and this comment read
                # "0 of 1156 reachable states" until the fifth pass, citing a subset as its own population.
                # But its ARITHMETIC goes with it: a dead arm's subtraction is not a live one's operand.
                #
                # `max(0, …)` is kept for parity with the JS, and it is DEFENCE, not the mechanism: the
                # `> 0` test below already makes a negative unrenderable (`-20 > 0` is false, exactly as
                # `0 > 0` is), so the clamp is unobservable. Measured — removing it moves no check.
                _b_rest = max(0, _n_blocked - _n_gen)
                if _b_rest > 0:
                    _b_parts.append(f"{_g(_b_rest)} single-node")
                out.append("    " + _c(
                    f"{_g(_n_blocked)} blocked" + (f" — {' · '.join(_b_parts)}" if _b_parts else "")
                    + " — counts-only by design (generic-cli / single-node are counts only)", "dim"))
            elif _n_blocked > _shown_b:
                out.append("    " + _c(f"… +{_g(_n_blocked - _shown_b)} more blocked — see the consult (cm workflows . --registrar)", "dim"))
            _anch = _lget(_wp, "decline_anchors")
            if _anch:
                out.append("    " + _c(f"{len(_anch)} decline-anchor(s) — a fleet decline blocks a naive re-propose", "dim"))
            _wv = _clean(str(_wp.get("verdict") or ""))
            if _wv:
                out.append(_kv("", _c(_wv, "dim")))
            # v0.4.34 (E2): the cold-state line is suppressed on THREE operands. The first draft of
            # this comment named one and explicitly disclaimed another — "Keyed on `_n_blocked` (the
            # record), NOT on `_anch` … it is not the right one" — sitting immediately above a
            # condition that reads `not _cands and not _anch and _n_blocked <= 0`. The PROSE was the
            # false surface, not the code, and the check label carried the same two-operand account.
            # What each operand is for: `_n_blocked` is the record's own count, and "0 fleet-
            # candidates" beside "30 blocked" is the contradiction this exists to remove; `_cands` is
            # what the sentence DENOTES, so a record carrying candidates cannot make a zero-breadth
            # claim at all; `_anch` covers the third state — anchors, no blocked rows, no candidates.
            # TWO of the three conjuncts are UNWITNESSED: measured, deleting `and not _anch` changes
            # the render for the third state and deleting `and not _cands` changes it for candidates
            # beside an explicit `n_blocked: 0`, and NEITHER leaves a check red. Only `_n_blocked <= 0`
            # is defended (its deletion reds E2-b). Live rules no check defends — recorded, not relied
            # on.
            if not _cands and not _anch and _n_blocked <= 0:
                out.append("    " + _c("0 fleet-candidates — the honest cold state (never invented breadth)", "dim"))
        else:
            out.append(_kv("REGISTRAR", _c("registrar not consulted this pass (Tier-2 fleet placement)", "dim")))

    # Marker
    m = _dget(record, "marker")
    if m:
        # v0.4.34 (E3): `is None` guards ABSENT and passes EMPTY — a marker with commit "" rendered a
        # hole where the "?" fallback was intended. Same defect as `x.get(k, D)`, different spelling, so
        # the site census (which needs a 2-arg `.get`) can never see it; the `or "?"` is the repair here.
        _mc = m.get("commit")
        _mc = "?" if _mc is None else (_clean(str(_mc)[:12]) or "?")
        _mt = m.get("timestamp")
        _mt = "?" if _mt is None else (_clean(str(_mt)) or "?")
        out.append(_kv("MARKER", _c(f"→ {_mc} @ {_mt}", "dim")))

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
        "identity": {"domain_id": "personal", "enrolled": True,
                     "registry_state": "healthy", "cross_project_allowed": True,
                     "conflicts": 0},
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
                          "refreshed": 1, "held": 0, "gc_removed": 2},
        "network": {"basis": "≈ chars/4", "node_def": "stores", "trigger": "acme-api",
                    "nodes": [
                        {"node": "acme-api", "trigger": True, "always_loaded_tokens": 278,
                         "mirror_index_tokens": 150, "recall_tokens": 1775, "facts": 12, "shared": 6,
                         "universal": 4, "stack": 2, "domain": "tools",
                         "groups": ["fleet"], "sid": "-home-you-acme-api"},
                        {"node": "Doc_Flo", "trigger": False, "always_loaded_tokens": 6183,
                         "mirror_index_tokens": 176, "recall_tokens": 207220, "facts": 104, "shared": 4,
                         "universal": 4, "stack": 2, "domain": "docs",
                         "groups": ["fleet"], "sid": "-home-you-Doc-Flo"}],
                    "stack_edges": [{"a": "acme-api", "b": "Doc_Flo", "n": 2}],
                    "totals": {"nodes": 2, "always_loaded_tokens": 6461,
                               "mirror_index_tokens": 326, "recall_tokens": 208995,
                               "universal": 4, "stack": 2},
                    "basis_scope": "fleet",
                    "domains": [{"domain": "docs"}, {"domain": "tools"}],
                    "universal_facts": [{"name": "advisor-pass", "domain": "personal", "held": 2},
                                        {"name": "docs-eval", "domain": "docs", "held": 1}],
                    "group_links": [{"group": "fleet", "home_domain": "personal", "members_n": 2,
                                     "facts": [{"name": "advisor-pass", "domain": "personal", "held": 2}]}]},
        "marker": {"commit": "b6d37b6e9f01", "timestamp": "2026-06-16T11:40:00Z"},
    }


def _already_logged(path: str, commit: str, ts: str) -> bool:
    """True if `path` already has this (commit, timestamp). Junk lines skipped, never raise."""
    if not os.path.exists(path):
        return False
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    prev = json.loads(line)
                    pm = prev.get("marker") or {}
                    if (str(pm.get("commit", "")) == commit
                            and str(pm.get("timestamp", "")) == ts):
                        return True
                except (ValueError, AttributeError):
                    continue
    except OSError:
        return False
    return False


def _persist(record: Mapping[str, Any], dirpath: str) -> str:
    """Append the cycle record to the plugin-data cycle log (NOT the native memory dir).

    Native `MEMORY.md` / facts / mirrors stay facts-only (ADR 006). v0.4.1 (D2):
    reconciles an empty marker stamp from the stamped state file (the single source)
    BEFORE the unstamped refusal, appends the RECONCILED payload, and returns a
    status — "ok" (appended) | "duplicate" (already logged — the exit-4 loop-back
    re-render) | "unstamped" (empty timestamp even after reconcile) | "no-dir" |
    "io-error". Idempotent on (commit, timestamp).

    "no-dir" is unreachable from `main` (measured, v0.4.29): `main` refuses a `--persist` dir
    that does not exist at exit 2 BEFORE calling here, so `main`'s `no-dir`/`io-error` arm fires
    only for `io-error` today. It is kept rather than deleted because it is the only guard
    against the dir vanishing between `main`'s `isdir` and this call. Note it is NOT unpinned —
    a first cut of this docstring said so and was wrong: `tests/simulate_accumulation.py`'s
    Probe I calls this function with a NON-EXISTENT dir and asserts the skip, so deleting the
    arm fails the accumulation sim."""
    if not os.path.isdir(dirpath):
        print(f"render_dashboard: --persist dir not found, skipping log: {dirpath}", file=sys.stderr)
        return "no-dir"
    marker = _dget(record, "marker")  # tolerate a truthy non-dict marker (model slip) — never .get() on a str
    from pathlib import Path as _P
    from memory_status import reconcile_marker as _reconcile_marker
    marker = _reconcile_marker(marker, _P(dirpath))
    payload = dict(record)
    payload["marker"] = marker
    commit, ts = str(marker.get("commit", "")), str(marker.get("timestamp", ""))
    if not ts:
        print("render_dashboard: marker.timestamp empty after reconcile (unstamped cycle), "
              "skipping persist", file=sys.stderr)
        return "unstamped"
    from retention import cycle_log_read_paths, cycle_log_write_path
    store = _P(dirpath)
    for p in cycle_log_read_paths(store):
        if _already_logged(str(p), commit, ts):
            return "duplicate"
    logpath = cycle_log_write_path(store)
    try:
        logpath.parent.mkdir(parents=True, exist_ok=True)
        with open(logpath, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, ensure_ascii=False) + "\n")
        print(f"persist → {logpath}")
    except OSError as exc:
        print(f"render_dashboard: cannot append to log: {exc}", file=sys.stderr)
        return "io-error"
    try:
        from control_plane import record_usage_window
        from store_context import resolve_store
        ctx = resolve_store(_P.cwd())
        if ctx.native_memory_dir.resolve() != store.resolve():
            # v0.4.0 review (R128 clock liveness): a dream can render from a
            # different cwd — silently skipping would stall the usage-window
            # clock and freeze a justification at "suppressed forever". Fall
            # back to the marker's script-owned project_path instead.
            marker_p = store / ".consolidation-state.json"
            alt = None
            try:
                st = json.loads(marker_p.read_text(encoding="utf-8"))
                if isinstance(st, dict) and str(st.get("project_path") or ""):
                    from store_context import resolve_store as _rs_alt
                    alt_ctx = _rs_alt(_P(str(st["project_path"])))
                    if alt_ctx.native_memory_dir.resolve() == store.resolve():
                        alt = alt_ctx
            except (OSError, ValueError, TypeError):
                alt = None
            if alt is None:
                return "ok"    # appended; the clock path is skipped (cross-cwd, no fallback)
            ctx = alt
        raw_usage = record.get("usage")
        usage = raw_usage if isinstance(raw_usage, dict) else {}
        cycle_id = f"{commit}|{ts}"
        window = str(usage.get("window") or "")
        started = window.split("..", 1)[0].strip() or ts
        pf_raw = usage.get("per_fact")
        pf = pf_raw if isinstance(pf_raw, list) else []
        transcripts = 0
        facts_read = 0
        try:
            transcripts = int(usage.get("transcripts") or 0)
        except (TypeError, ValueError):
            transcripts = 0
        try:
            facts_read = int(usage.get("facts_read") or 0)
        except (TypeError, ValueError):
            facts_read = 0
        from memory_status import _parse_ts
        probative = (transcripts >= 1 and facts_read == len(pf)
                     and _parse_ts(started) is not None)
        record_usage_window(ctx, cycle_id=cycle_id, started_at=started,
                            probative=probative)
    except Exception as exc:
        print(f"render_dashboard: usage-window clock skipped ({exc.__class__.__name__})",
              file=sys.stderr)
    return "ok"


def _refresh_post_state(record: "ms.CycleRecord", store: Path) -> None:
    """Re-take the store-local POST-state at the terminal persist.

    v0.4.30 (Cycle B — spec `docs/record-post-state.spec.md` §2). `memory_status.seed_record`
    seeds a whole family of `after` leaves from the SAME Phase-0 `ctx` read that produces the
    `before` leaves, so `before == after` by construction and NOTHING owned the after-side: the
    only refresh path was a prose instruction naming three of the keys. This is the script taking
    ownership of what it can measure from the store it is about to persist to.

    Call it ONLY when persisting. A seed/preview render IS the dream's BEFORE state — the one
    honest pre-state the product produces — so refreshing there would destroy it; the caller uses
    the same `persist_dir is not None` predicate that already distinguishes the two. Mutates
    `record` in place (the object `_persist` and the heal already share), and it must run BEFORE
    `validate_cycle_record`, or the reconcile invariant checks the unrefreshed seed and warns on
    every pass whose index moved — a check that is always red is a check nobody reads.

    Three rules, each a MECHANISM rather than an assurance:

      • NEVER BLOCKS. Any failure leaves `record` exactly as authored and warns on stderr. A
        measurement failure must not fabricate. Not `_ui.dream_cue`: that is gated on
        `CM_DREAM_ARC` and is invisible to `cm`, the tests and the beta harness by design — a
        refresh failure has to be loud, not suppressible.
      • ONE SPLICE. The complete leaf set is built in scratch dicts and written after the LAST
        measurement succeeds, so no leaf can be half-written. This matters because
        `validate_cycle_record` descends into `budget` for exactly TWO leaves — §2.4's reconcile
        invariant reads `budget.index`'s `before_tokens`/`after_tokens` — and NOT for the rest: a
        `budget.index` holding only SOME of its other leaves (`after_lines`, `after_bytes`,
        `cliff_pct`, `fat_hooks`, `hook_max_tokens`, `budget_tokens`, `ceiling_tokens`, `over`)
        renders with zero warnings and zero errors, every reader using `.get(k, default)` — a
        mixed-generation record persisting invisibly.
      • LEAF-WISE. A leaf is written only where its OWN parent mapping already exists; an absent
        container is a POLICY skip (silent — nothing is wrong), which is deliberately a different
        path from a failed measurement (which always warns). Creating a container would author
        state the record never had and newly draw a render row — a different change than
        correcting one.
    """
    # ── the policy skip, gated per PARENT mapping, never on `budget` as a whole ──────────────
    # The renderer gates the index gauge row on `if idx:` — `idx` being `budget.index`, the INNER
    # mapping — and its `(unchanged)` fallback on `if not (cm or idx or rf or …)`. So a record
    # carrying `budget.claude_md` WITHOUT `budget.index` is a shape the renderer treats as having
    # no index, and splicing into a newly created `budget["index"]` would author that block and
    # newly draw the row. The shape is type-legal (`Budget` is `total=False`) and `--persist`
    # consumes arbitrary JSON, so it is constructible; measured across the fleet it does not
    # occur, which makes this a precision rule rather than a live defect.
    b = _dget(record, "budget")
    h = _dget(record, "health")
    rem = _dget(record, "remediation")          # TOP-LEVEL, not `budget.remediation`
    idx = b.get("index") if isinstance(b.get("index"), dict) else None
    rf = b.get("recall_facts") if isinstance(b.get("recall_facts"), dict) else None
    sd = h.get("schema_drift") if isinstance(h.get("schema_drift"), dict) else None
    if idx is None and rf is None and sd is None:
        return

    # ── the precondition, asserted before any measurement ────────────────────────────────────
    # This is the one failure the never-blocks contract cannot catch by itself: every measurement
    # below returns a well-formed ZERO on an absent index and NONE of them raises — `_measure`
    # gives (0, 0, 0), `hook_stats("")` gives (0, 0, []), `cliff_pct(0, 0)` gives 0, and
    # `schema_drift([], set())` returns every field zero. Writing those beside the seed's true
    # `before_*` would fabricate a post-state that is CLEAN in the concealment direction, strictly
    # worse than the mirrored seed it replaces (which at least carried a real Phase-0 value).
    # It is asserted before the first scratch leaf is built, so no partial post-state can exist.
    #
    # The path comes from `store_local_index`'s OWN `index_path`, never rebuilt here. Two
    # expressions of one fact is the repo's weakest-enforcement-site rule at the exact site whose
    # docstring invokes it: a future rename of the index filename (or a store whose index is
    # discovered rather than fixed-name) would update the measurement and leave this guard behind,
    # and the guard would then pass on one file while `_measure` read another — writing
    # `after_tokens: 0` beside a true `before_*`, which is the fabrication this check exists to
    # prevent. Reading it back makes the guard and the measurement ONE expression by construction.
    #
    # EMPTINESS is deliberately NOT part of this. A zero-byte MEMORY.md is a real file and
    # (0, 0, 0) is a truthful measurement of it; the resulting large negative delta then trips the
    # reconcile invariant, so the record falsifies itself LOUDLY — the system working. Absence has
    # no truthful measurement; emptiness does.
    try:
        local = ms.store_local_index(store)
        if not local["index_path"].is_file():
            # ⚠ THE MESSAGE NAMED THE WRONG FAULT. `is_file()` is False for an ABSENT index AND for
            # one that is a DIRECTORY (or mode-000, or a dangling symlink) — and this said "no
            # MEMORY.md in the store" for all of them, sending the operator after an ABSENCE when
            # the file is sitting right there, unreadable. That is a fault spelled as an absence,
            # which is the one thing the third state exists to stop. The two are told apart here.
            _ip = local["index_path"]
            _why = ("no MEMORY.md in the store" if not _ip.exists()
                    else "MEMORY.md EXISTS but is not a readable file — its size is UNKNOWN, not "
                         "zero, and the post-state was NOT refreshed")
            print(f"render_dashboard: post-state refresh skipped ({_why})", file=sys.stderr)
            return
        il = local["index_lb"]
        hooks = local["index_hooks"]
        # Build EVERY scratch value first — the splice below is the only write.
        scratch: dict = {}
        if idx is not None:
            scratch["index"] = {
                "after_lines": il[0], "after_bytes": il[1], "after_tokens": il[2],
                "fat_hooks": hooks[0], "hook_max_tokens": hooks[1],
                "cliff_pct": local["index_cliff"],
                # The two POLICY constants, written in the same splice as the measurement they
                # qualify. `budget_tokens` is a seed-TIME SNAPSHOT of a module constant — measured,
                # 14 of this store's 55 records still carry the retired `1200` — so refreshing the
                # numerator alone paired a live measurement with an obsolete denominator, and the
                # gauge derives three values from the pair (`_bar`, `_pct`, `_over`): a recovered
                # store rendered a full red bar at 100% with no OVER flag, all on one line. The
                # HTML archive never had this defect, and for a reason this splice now shares: its
                # gauge takes both operands from the same record (`budget.index.after_tokens`
                # against `budget.index.budget_tokens`, each with a fallback), so wherever the key
                # is present the pair is contemporaneous — and this writes them together.
                "budget_tokens": ms.INDEX_TOKEN_BUDGET,
                "ceiling_tokens": ms.INDEX_CEILING_TOKENS,
                # The SAME comparison the over-budget warning below makes, so the warning and this
                # leaf cannot disagree by construction.
                "over": il[2] > ms.INDEX_TOKEN_BUDGET,
                # ⚠ RE-WRITTEN HERE, and it must be. `unmeasurable` qualifies the two leaves above
                # it, so leaving it to the seed couples the fault to a DIFFERENT read than the
                # number it describes — and the guard above is `is_file()`, which is TRUE for a
                # mode-000 index. So the harmful direction is reachable: an index Phase 0 read
                # cleanly and which then became unreadable writes `after_tokens: 0, over: false`
                # beside a stale `unmeasurable: false`, which is the healthy-store fabrication this
                # field exists to prevent. Written from `local` — the same dict `il` came from —
                # the fault and the measurement are one expression by construction, exactly as
                # `budget_tokens` above is paired with its numerator.
                "unmeasurable": bool(local["index_fault"]),
            }
            # The ceiling VERDICT rides along with the index it judges — `remediation` is the
            # top-level triage block, so LEAF-WISE holds: the parent exists or the leaf is not
            # written. `over_ceiling` is not a triage verdict despite its address: memory_status
            # defines it as `index_lb[2] > INDEX_CEILING_TOKENS`, structurally
            # standing-justify-independent ("there is nothing to suppress and no justify escape"),
            # computed from the very read above. Leaving it frozen is what let a red HARD CEILING
            # alarm outlive the over-ceiling index it was raised for, drawn on the same rendered
            # line as the healthy gauge that contradicted it. `required`/`standing_justified`/
            # `lever`/`candidates_surfaced`/`pruned`/`achieved_*` are NOT written here: those read
            # `standing_justify`, `baseline_facts` and fact-count growth, which are not store-local
            # measurements and which the refresh must not invent. Falsy is render-identical to
            # absent at ALL SIX record readers — the dashboard tail and the remediation panel
            # (`render_dashboard.py`), three in the archive (the remediation lead, the KPI, and the
            # gauge, in `dashboard.template.html`), and one in `dashboard.sections.js` — because
            # every one tests truthiness (`_flag`, `truthy`, or a bare `if`). So this leaf can only
            # ever correct the alarm, never newly draw one it should not. The count is
            # `grep -rn over_ceiling`'s: an earlier draft named three, which is the number its
            # author happened to know, and a count is not a census until it has been counted.
            if rem:
                scratch["remediation"] = {"over_ceiling": il[2] > ms.INDEX_CEILING_TOKENS}
        if rf is not None:
            scratch["recall_facts"] = {"after": len(local["fact_files"])}
        if sd is not None:
            # Six of the seven fields are store-local. The seventh is NOT: `canonical_stems`
            # comes from `ctx.canonical_domain_dir`, and obtaining that directory is a
            # project-keyed REGISTRY read (`resolve_store` takes the domain from the control
            # plane, or a git-root settings file, falling back to `domains/unknown/facts`).
            # Deriving it from the store would mean GUESSING — and the `unknown` fallback
            # resolves to a directory that does not exist, so `canonical_stems` becomes `set()`,
            # which is a different wrong answer rather than a safe one. So the field is PRESERVED
            # from the seed; it is not one of the under-reporters, so preserving it costs
            # nothing measured.
            drift = ms.schema_drift(local["fact_files"],
                                    ms.placed_fact_names(local["index_path"], local["archive_docs"]))
            drift_out: dict = dict(drift)
            # Preserved when the seed HAS it, and DROPPED when it does not — never authored as 0.
            # `schema_drift` returns all seven fields, and on the `canonical_stems=None` path taken
            # here the seventh is structurally zero: it was not measured, it cannot be. Writing
            # that 0 into a legacy-shaped block would put a measured-looking value on a field
            # nothing measured — LEAF-WISE's rule ("creating a container would author state the
            # record never had") applied one level down, to a leaf.
            if "advisory_stranded_globals" in sd:
                drift_out["advisory_stranded_globals"] = sd["advisory_stranded_globals"]
            else:
                drift_out.pop("advisory_stranded_globals", None)
            scratch["schema_drift"] = drift_out
    except Exception as exc:
        # NEVER BLOCKS. The record keeps its authored values, which is the honest outcome of a
        # measurement that did not happen.
        print(f"render_dashboard: post-state refresh skipped ({exc.__class__.__name__})",
              file=sys.stderr)
        return

    # ── the two conditions: WARN, then write the measurements anyway ─────────────────────────
    # An index over the target with no `remediation` block (nothing for the triage to defer to),
    # or a fresh `after_tokens` past the hard ceiling. Both operands are the LIVE constants, never
    # the record's own seeded fields: `budget.index.budget_tokens` is seed-derived and can be a
    # RETIRED constant (records here carry both `1200` and `1500`), so keying to it would compare
    # a fresh measurement against an obsolete budget and could warn over-budget while the same
    # pass wrote `over: False`. Keying both to the constants the refresh is about to write makes
    # the warning and the leaf the same comparison by construction.
    #
    # `remediation` is read from the TOP LEVEL of the record. It is a `CycleRecord` key, not a
    # `budget` sub-key — `budget` carries exactly `claude_md`, `global_claude_md`, `index`,
    # `recall_facts` and `claude_md_hierarchy`, so a guard reading `budget.remediation` is dead:
    # it warns on every over-target persist, the standing-justified store included, and tells the
    # operator its record "carries no remediation block" while one sits in the record.
    #
    # Suppressing the WRITE instead was considered and rejected: `over` is a MEASUREMENT, not a
    # verdict, so it must be written truthfully.
    if il[2] > ms.INDEX_TOKEN_BUDGET and not rem:
        _wtail = ("post-state written anyway" if idx is not None
                  else "no index block in the record — nothing written")
        print(f"render_dashboard: index is over budget ({il[2]} > {ms.INDEX_TOKEN_BUDGET} est tok) "
              f"and the record carries no remediation block — {_wtail}", file=sys.stderr)
    if il[2] > ms.INDEX_CEILING_TOKENS:
        print(f"render_dashboard: index is past the hard ceiling ({il[2]} > "
              f"{ms.INDEX_CEILING_TOKENS} est tok) — post-state written anyway", file=sys.stderr)

    # ── the splice: one write per parent mapping, after every measurement succeeded ───────────
    # Each scratch entry was built under the same `is not None` test that guards its write, and
    # reaching here means the whole measurement block ran to completion — so the entries and the
    # writes pair up exactly, and no leaf can be written on a path where a later measurement threw.
    if idx is not None:
        idx.update(scratch["index"])
    if rf is not None:
        rf.update(scratch["recall_facts"])
    if sd is not None:
        sd.update(scratch["schema_drift"])
    if "remediation" in scratch:
        rem.update(scratch["remediation"])


def main() -> int:
    global _COLOR, _ASCII, W
    argv = sys.argv[1:]
    _COLOR = _color_enabled(argv, sys.stdout)
    _ASCII = "--ascii" in argv   # opt-in no-Unicode fallback (translated as render's last step)
    W = _ui.resolve_width(argv, sys.stdout)   # uniform width: fill the terminal (clamped [60,100]); --width=N override; fixed 60 for pipes/tests
    # Pass 1 — the flag surface, strictly (v0.4.29; spec §2.5). This script used to keep every
    # unrecognized `-`-token and let the filter below turn it into a RECORD PATH: `--persit DIR`
    # opened a file named `--persit` (exit 1, "cannot read cycle record"), and `--persist=DIR` —
    # the plausible typo, since the ecosystem accepts `=` for --color/--width/--evict/--into —
    # never set persist_dir at all, so `judged` was False and a stamped, arc-incomplete record
    # rendered as an UNJUDGED PREVIEW: exit 0, no gate, no trace. `-h` exited 1 the same way.
    # `--demo` is a real, live flag and is explicitly allowed — it is the one flag no
    # visual-flag list names, and a house-style copy would reject it.
    for _a in argv:
        if not _a.startswith("-"):
            continue
        if _a == "--persist" or _a == "--demo" or _a in _VISUAL_FLAGS \
                or _a.startswith(("--color=", "--width=")):
            continue
        print(f"unknown flag: {_a}", file=sys.stderr)
        return 2
    # --persist DIR (v0.1.4): pull the flag + its value out BEFORE positionals are taken, so
    # the cycle-record path isn't shadowed by '--persist' or its DIR (the filter below only
    # strips the --color/--demo chrome). Mirrors how --color is excluded — but consumes TWO
    # tokens (the flag and its separate value).
    persist_dir, pruned, i = None, [], 0
    while i < len(argv):
        if argv[i] == "--persist":
            # The value is checked for EMPTINESS and not merely for presence: `--persist ""`
            # made these two predicates disagree — `judged = persist_dir is not None` is True for
            # "", so the render was judged, while `if persist_dir:` is falsy, so the entire
            # print→persist→exit block (the 3/4/5 gates) never ran. It rendered a dashboard that
            # claims the dream is being judged and then judged nothing. Exit 2 is deliberately
            # STRICTER than the distill_scan --into precedent (which accepts ""), because --into's
            # emptiness costs a file and --persist's costs the gate.
            if i + 1 >= len(argv) or not argv[i + 1].strip():
                print("render_dashboard: --persist requires a directory argument", file=sys.stderr)
                return 2
            # os.path.abspath makes the relative and absolute spellings ONE input:
            # retention._ops_slot returns native_store.parent.name when the dir is NAMED `memory`
            # — so `Path("memory").parent.name` is `Path(".").name`, '' — and native_store.name
            # otherwise, so `Path(".").name` is '' as well. Both relative spellings therefore
            # yield an empty project id, which raises IdentifierRefused (measured: a 15-line
            # traceback on a directory that EXISTS).
            persist_dir = os.path.abspath(argv[i + 1])
            i += 2
            continue
        pruned.append(argv[i])
        i += 1
    argv = pruned
    if persist_dir is not None and "--demo" in argv:
        # `--demo --persist DIR` exited 0, persisted NOTHING and printed nothing: `--demo` builds
        # its record in-process, so the short-circuit below returned before the
        # print→persist→exit block and all three gates were skipped. Persisting a synthetic
        # record would be wrong, so the pair is refused rather than honoured — but refused
        # LOUDLY, because "exit 0, nothing persisted, no trace" is the false-clean shape this
        # cycle exists to close, and the caller asked for a persist. Distinct from `--demo`
        # alone, which stays a clean preview.
        print("render_dashboard: --demo renders a built-in record and cannot be combined with "
              "--persist — nothing would be persisted and no gate would run", file=sys.stderr)
        return 2
    if persist_dir is not None and not os.path.isdir(persist_dir):
        # A dir that parses but does not exist was turned into `no-dir` by _persist and then into
        # exit 0 by main — BEFORE either gate was consulted: the false-clean this cycle exists to
        # close, and the reason this check is here rather than in _persist (by then the judged
        # dashboard has already printed). Nothing is lost by refusing: the dir is only ever a
        # STORE HANDLE here, so a run that reached no-dir was never going to persist anything.
        print(f"render_dashboard: --persist dir not found: {persist_dir}", file=sys.stderr)
        return 2
    if "--demo" in argv:  # paste-free preview with a built-in record
        print(render(_demo_record()))
        return 0
    paths = [a for a in argv if not a.startswith("--color") and not a.startswith("--width") and a not in ("--no-color", "--demo", "--ascii")]
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
    # v0.4.30 (Cycle B — spec §2.1/§2.2/§2.3): the store-local POST-state is script-owned from
    # here on. Ordered BEFORE the validator on purpose — the reconcile invariant must check the
    # value the refresh JUST WROTE, or it checks the unrefreshed seed and warns on every pass
    # whose index moved (a check that is always red is a check nobody reads). Gated on
    # `persist_dir is not None`, the same predicate `judged` uses below, because a seed/preview
    # render IS the dream's BEFORE state and refreshing it would destroy the only honest
    # pre-state the product produces. Before the print, so the log and the display agree.
    if persist_dir is not None:
        _refresh_post_state(record, Path(persist_dir))
    # Warn-only structural validation (v0.1.6): surface a wrong-CONTAINER-type key (the
    # model-slip class behind the past crashes) on STDERR. NEVER blocks the render and
    # NEVER touches stdout — the rendered dashboard stays byte-identical.
    for w in ms.validate_cycle_record(record):
        print(f"render_dashboard: cycle-record warning: {w}", file=sys.stderr)
    # v0.4.19: the conversation-truth detector (docs/dream-narration-teeth.spec.md) — computed
    # BEFORE the single print: the exit-3/exit-4 renders return without a second print, so the
    # gap panel must be IN this print (compute-before-print; only the EXIT ladder below stays
    # ordered after the record-side checks). The verdict + the record's `narration` block are
    # attached here; _persist appends the payload, so the block rides the log line (absence on a
    # log line = pre-feature). Any failure of the detector itself never blocks a persist (the
    # preflight precedent: the machinery must not break a dream).
    narration = None
    if persist_dir:
        try:
            from pathlib import Path as _P
            import dream_procedure as _dp
            # v0.4.29 (spec §2.2): `is not None`, not truthiness. The empty LIST is a dream block
            # carrying nothing usable — it must be judged (and fails), or C6's class lands in the
            # archive: an emptied dream would carry no `narration` block, so ABSENCE on a log line
            # would stop meaning "pre-feature" and start meaning "nothing to see here".
            if _dp._checked_texts(record) is not None:
                _store = _P(persist_dir)
                # _dget returns dict SUBVALUES (a str before_timestamp would read as {}) — the
                # anchor is a plain .get on the marker dict (the spec's HIGH-class pin: the
                # window keys on the record's Phase-0-seeded value, never the state file).
                _since = str(_dget(record, "marker").get("before_timestamp") or "")
                _sess = _narration_session_dir(_store)
                _root = _narration_project_root(_store)
                if _sess is None:
                    narration = {"verdict": "degraded", "reason": "transcript unavailable",
                                 "gaps": [], "ext_unaccounted": False}
                else:
                    narration = _dp.judge(record, _sess, _since, project_root=_root)
                record["narration"] = cast(ms.Narration, _dp.narration_block(narration))
        except Exception as exc:
            print(f"render_dashboard: narration check skipped ({exc.__class__.__name__})",
                  file=sys.stderr)
    # `judged` only when persisting: a completed dream is judged by the PROCEDURE INTEGRITY detector;
    # a seed/preview render (no --persist) is the dream's BEFORE state (0 candidates, 0/0/0 by
    # construction) and must NOT be flagged. So the panel is gated here, matching the exit below.
    judged = persist_dir is not None
    print(render(record, judged=judged, narration=narration))
    if persist_dir:
        try:
            from pathlib import Path as _P
            from store_context import warn_unenrolled_share as _w_dash
            # RC-5c. The subject is named by --persist; cwd is not evidence about it. The tempting
            # repair — `resolve_store(Path(persist_dir))` — is the WRONG one, and §Design forbids
            # it: `persist_dir` is a STORE path while `resolve_store` takes a project DIRECTORY, so
            # it slugs the store back in as a root and answers with a PHANTOM (measured on a
            # hermetic HOME: pid p_e85b61ed… vs the project's p_1da1b0b2…, native != the store). The
            # warn would then fire for a project that does not exist and set its one-shot flag in a
            # store that does not exist, while the subject's own flag stays unset — and because that
            # flag is a ONE-SHOT gate, the subject's future warnings are silently suppressed.
            _ctx_dash = _context_for_store(_P(persist_dir))
            if _ctx_dash is None:
                # SKIP, and say so. A warn is advisory, so losing one costs a nag; a warn against a
                # phantom costs the nag AND the durable suppression above. The stderr line is
                # load-bearing — `fault ≡ absence` is the RC-1 mechanism F1 closed, and a silent
                # skip would reintroduce it here under a new spelling.
                #
                # ⚠ So the line must not assert a VERDICT either. It used to read "no project
                # resolves to the --persist store", and `None` is returned for two different
                # reasons: no source verified, and a source could not be ASKED (the helper's own
                # broad catches, plus a cwd deleted under the process). Measured: one store, two
                # runs — the subject's own project as cwd prints no line, the same render with a
                # deleted cwd prints "no project resolves", which was never established. Say what
                # was measured: the verification, not the world it failed to observe.
                print(f"render_dashboard: unenrolled-share check skipped — could not verify which "
                      f"project owns the --persist store {persist_dir}", file=sys.stderr)
            else:
                _w_dash(_ctx_dash)
        except Exception:
            pass
    if persist_dir:
        # Strict order print → persist → exit (v0.1.44; extended v0.4.1): the firing record MUST
        # be logged (it accrues for calibration + the archive), THEN the terminal --persist render
        # exits nonzero on a gate violation — the detector teeth at the one boundary a finishing
        # dream always hits. Exit codes: 0 clean · 3 procedure-integrity (re-verify) OR an unfilled
        # record duty the panel marks as GATING (v0.4.33 — fill the field; the panel and the cue name
        # which. Only a clause carrying severity "alert" gates, so a warn-only gap such as a blank
        # `session` draws the panel and still exits 0) · 4 dream-arc incomplete (backfill beats) ·
        # 5 unstamped (re-stamp the marker); 1/2 stay read/arg.
        status = _persist(record, persist_dir)
        if status == "unstamped":
            # R1d: this panel asserted ABSENCE — "no stamp in .consolidation-state.json" —
            # unconditionally. After R1a that clause is false whenever the file HOLDS a stamp the
            # pass refused for being the cycle's own baseline, and the reader cannot tell the two
            # states apart. So name the cause; when no cause can be named, assert LESS rather than
            # keep the false universal (the line still carries UNSTAMPED, which the exit-5 pin
            # matches on — `tests/smoke.py:3424-3426`).
            from memory_status import stamp_refusal_note as _stamp_note
            _clause = _stamp_note(_dget(record, "marker"), persist_dir)
            print("⚠ UNSTAMPED CYCLE · no marker.timestamp in the record%s"
                  % ((" — " + _clause) if _clause else ""), file=sys.stderr)
            print("  → run memory_status.py --stamp-marker HEAD (resolved to the SHA for you, "
                  "v0.4.21) and fill marker.timestamp, then re-render", file=sys.stderr)
            _ui.dream_cue("NOT persisted — the cycle is unstamped: run --stamp-marker HEAD "
                          "(resolved to the SHA for you, v0.4.21) and "
                          "fill marker.timestamp before re-rendering; WAKE only after the clean re-run")
            return 5
        if status in ("no-dir", "io-error"):
            # keep their stderr diagnostics (exit 0, no cue)
            return 0
        # Split-brain heal (v0.4.1): the log now carries the RECONCILED marker — write the same
        # payload back to the cycle file, or the archive embeds the dream twice (reconciled log
        # line vs unstamped cycle copy never dedup).
        _heal = status == "ok"
        if status == "duplicate" and paths:
            # v0.4.19 (review M1): the loop-back re-render (narrate + re-render after an
            # exit-3/exit-4) appends nothing — but the narration verdict is script-injected, so
            # the model CANNOT heal it in the cycle file. When the recomputed verdict differs
            # from the stored block, heal the file anyway (the log line stays attempt-scoped —
            # the spec's F-2: the block on the log line is that attempt's scan result; the
            # archive's fresher-file rule then surfaces the healed verdict).
            # v0.4.30 (Cycle B, spec §2.5): WIDENED from the verdict alone to the WHOLE record.
            # The branch's premise — "the current file is the fresher expression" — held only for
            # the one field it compared, so a correction to `budget`/`health` (which the §2.1
            # refresh now writes into the record) had no path to the cycle file at all, while
            # `assemble_cycles` prefers that file over the log. The flip direction is safe and
            # one-way: `_already_logged` keys on the (commit, timestamp) PAIR, so this branch
            # already forces both equal, and the widening can only turn append→replace (one row
            # instead of a double-embed), never the reverse.
            try:
                with open(paths[0], encoding="utf-8") as _fh:
                    _stored = json.loads(_fh.read())
                if _stored != record:
                    _heal = True
            except (OSError, ValueError):  # JSONDecodeError is a ValueError subclass
                pass
        if _heal and paths:
            try:
                from memory_status import reconcile_marker as _reconcile_wb
                _wb = dict(record)
                _wb["marker"] = _reconcile_wb(_dget(record, "marker"),
                                              __import__("pathlib").Path(persist_dir))
                with open(paths[0], "w", encoding="utf-8") as _fh:
                    _fh.write(json.dumps(_wb, ensure_ascii=False) + "\n")
            except OSError:
                pass
        # "ok" OR "duplicate": the record IS in the log (freshly, or already) — the gates judge it
        # either way (the exit-3/exit-4 re-render must re-exit its code, never a silent 0).
        ok, _reason, _sev = ms.procedure_integrity(record)
        # enforce_post_arc=True (v0.4.29; spec §2.4): this is the ONE surface that knows the
        # record was just written by a live pass, so a missing `dream` here is a SKIPPED arc, not
        # a legacy artifact. Every other consumer keeps the default — `_POST_ARC_KEYS` is
        # version-grounded, and narrowing in place would retro-flip an archived display.
        arc_ok, _arc_reason = ms.arc_completeness(record, enforce_post_arc=True)
        # v0.1.54/v0.4.1: the dream-arc cue SPLITS on the gate outcome. The exit-3 path keeps the
        # model IN the dream through the Phase-3 loop-back (waking here would contradict SKILL's
        # re-verify rule); exit-4 keeps it in the dream through the backfill loop; the clean path
        # does NOT cue a wake — two mandatory SKILL steps remain (--diffs, then the render_html
        # archive open); the WAKE cue fires there (render_html), at the arc's true terminal boundary.
        if not ok:
            _ui.dream_cue("NOT over — the dream pulls you back: narrate the return to Phase-3 "
                          "verification dreamily; WAKE only on the clean re-run")
            return 3
        if not arc_ok:
            _ui.dream_cue("NOT over — arc incomplete: backfill the missing beats "
                          "(SLEEP · 5 phase beats + surfacing · WAKE) and re-render")
            return 4
        # v0.4.33 (OPEN 4b): the RECORD-DUTY arm — a field the pass seeded and left unfilled. It
        # runs AFTER the arc arm, and that order is a design decision, not layout: a record with a
        # GATING gap (a clause whose severity is "alert" — `rigor.applied: ""`, say) AND a 4/6 arc
        # must exit 4, the arc diagnostic; putting the duty arm first would exit 3 on it and name
        # the wrong cause — the record's ARC is what is incomplete, and the duty cue's remedy
        # ("apply it and re-render") does not backfill a missing beat.
        # The witness is deliberately an ALERT clause, and NOT the `session: ""` record this comment
        # first named: the arm below gates on `severity == "alert"` while clause A is `warn`, so a
        # session-only gap cannot feel this reorder at all — it exits 4 under EITHER order, measured
        # on both trees. A warning that cannot exhibit the defect it is cited for is the same slip
        # the spec records against its own revision 3: the design's intent written as the code's
        # property.
        # Scope that rule to THIS ARM: "exit 3 must never pre-empt exit 4" is FALSE as a bare
        # claim about the code, and measurably so — a procedure violation beside a 4/6 arc exits
        # 3, five lines above. The procedure arm is first by design and predates this one (the
        # v0.1.44 lazy-skip outranks the arc cue; reordering it would break the shipped exit-3
        # key). Below, the EXT arm likewise outranks NAR's 4, by the same record-side-first rule.
        # The duty arm's own placement is the only load-bearing order here.
        # Ordering is by check SPECIFICITY: a record-side structural failure outranks a record-side
        # field gap, and both outrank the conversation-side arms below.
        _gaps = ms.duty_gaps(record)
        if any(g.severity == "alert" for g in _gaps):
            # The remedy normally lives in the PANEL's per-row remedy line (each clause's remedy
            # differs); this cue names the field and the exit, not a remedy of its own — the first
            # cut appended "(or record it as honestly unknown)", which is TRUE for clause A and
            # FALSE for C (the trio's sanctioned abstention is to write NONE of the three, not to
            # record one as unknown).
            _ui.dream_cue("NOT over — the record carries an unmet duty: %s; the panel above gives "
                          "each field's remedy — apply it and re-render; WAKE only on the clean re-run"
                          % ", ".join(g.label for g in _gaps))
            return 3
        # v0.4.19: the conversation-truth arms judge LAST — record-side verdicts own their
        # renders (a 4/6 record exits 4 with the record-side panel + cue; NAR never
        # double-reports). EXT unaccounted → exit 3 (the Phase-2 lazy-skip's silent cousin);
        # NAR gaps → exit 4 (the arc's conversation-side arm); both → 3 (the existing key).
        # Degraded/verified → no exit change.
        if narration is not None and narration.get("verdict") == "failed":
            if narration.get("ext_unaccounted"):
                _ui.dream_cue("NOT over — Phase 2 left no trace in the conversation: run "
                              "extract_signals.py (--json or the human table) or record an "
                              "extractor-skip: entry, then re-render; WAKE only on the clean re-run")
                return 3
            _ui.dream_cue("NOT over — the dream lives only in the record: narrate the missing "
                          "beats in the conversation (sleep · beats 0–5), then re-render; "
                          "WAKE only on the clean re-run")
            return 4
        if status == "ok":
            if _gaps:
                # WARN-ONLY gaps (every fired row is `warn` — every `alert` returned 3 above). Exit 0 here is
                # by design, but the word "clean" beside a PRINTED ⚠ RECORD DUTY GAPS panel is this
                # cycle's own thesis re-entering through the cue: a duty rendering as silence, one
                # layer out. (SKILL defines the WAKE as rendering "only through a clean exit 0", so
                # `clean` is a term of art here, not a synonym for exit 0.) Same Phase-5
                # instruction, true words.
                _ui.dream_cue("persisted — Phase 5 continues (--diffs, then render_html opens the "
                              "archive), but the record carries an ADVISORY duty gap the panel "
                              "names; fill it on a later pass if it can be known; WAKE comes after "
                              "Phase 5, not now")
            else:
                _ui.dream_cue("persist clean — Phase 5 continues (--diffs, then render_html opens the "
                              "archive); WAKE comes after that, not now")
        # duplicate of a clean record: silent — the idempotent re-render must never fake a
        # "persist clean" for an append that did not happen.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
