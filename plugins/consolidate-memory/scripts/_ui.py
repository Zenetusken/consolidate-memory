"""Shared visual vocabulary for the consolidate-memory script outputs.

ONE source of the look the final dashboard established — auto-gated color, the ━ rule, the
bold-UPPERCASE `kv` section line (which carries the hierarchy even in monochrome), budget
`bar`s, and the `--ascii` fallback — so every human-facing report (memory_status, sync_global,
extract_signals) is visually coherent with `render_dashboard.py`'s reference. Zero-dep, stdlib-only.

`render_dashboard.py` keeps its OWN copies of these primitives on purpose: it is the byte-pinned
reference (37 output assertions + a determinism check), so it stays untouched. A smoke **drift-pin**
asserts THIS module stays byte-identical to render's primitives, so the two can never diverge —
single-source coherence without risking the reference. The other scripts import from here.

Design restraint (match the reference): hierarchy comes from the bold-uppercase labels, NOT
decoration. One banner rule per report; `kv` lines; sparse glyphs/bars. Resist box-everything.
"""
from __future__ import annotations

import os
from typing import Any, cast

W = 60  # rule width (mirrors render_dashboard.W)

# ── color: opt-in, AUTO-gated, always redundant with glyphs/labels ───────────────
_COLOR = False  # set via set_modes(); stays False for library/test/piped calls → plain output
_ASCII = False  # set via set_modes(); when on, ascii_translate() flattens glyphs to ASCII
CODES = {"reset": "\x1b[0m", "bold": "\x1b[1m", "dim": "\x1b[2m",
         "red": "\x1b[31m", "green": "\x1b[32m", "yellow": "\x1b[33m", "cyan": "\x1b[36m"}

# ── ASCII fallback (--ascii): each glyph → a SINGLE ASCII char so column widths are preserved ──
GLYPH_ASCII = str.maketrans({
    "█": "#", "░": ":", "━": "=", "─": "-", "✦": "*", "⚠": "!", "✓": "+", "✗": "x",
    "◀": "<", "↓": "v", "⟳": "@", "→": ">", "·": ".", "•": "*",
    "≈": "~", "↑": "^", "−": "-", "…": ".", "↔": "-", "—": "-",
})


def color_enabled(argv: list, stream: object) -> bool:
    """Resolve the color mode. `--color=never|always|auto` (or `--no-color`) wins; otherwise
    AUTO = stdout is a TTY and NO_COLOR is unset and TERM isn't 'dumb'. The AUTO gate is what
    makes color safe: an agent tool call (stdout captured, not a TTY) or a pipe → color off."""
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


def set_modes(color: bool = False, ascii: bool = False) -> None:
    """Set the module-level color/ascii state once (from a script's main())."""
    global _COLOR, _ASCII
    _COLOR, _ASCII = color, ascii


def c(text: str, *codes: str) -> str:
    """Wrap `text` in ANSI codes iff color is enabled. No-op otherwise, so the same render
    path produces clean plain text when captured/piped/dumb."""
    if not _COLOR or not codes:
        return text
    return "".join(CODES[x] for x in codes) + text + CODES["reset"]


def lbl(text: str, width: int = 0) -> str:
    """A DIM in-row field label (chrome) so the data values beside it pop when color is on.
    Padding is computed on the PLAIN text, so color codes never disturb column alignment."""
    s = f"{text:<{width}}" if width else text
    return c(s, "dim")


def rule(ch: str = "━") -> str:
    return ch * W


def kv(label: str, value: str) -> str:
    """A section line: BOLD UPPERCASE label (carries hierarchy even in monochrome) + value."""
    return f"  {c(f'{label:<10}', 'bold')}{value}"


def num(x: object) -> float:
    """Coerce a maybe-string/None/absent value to a float; never raise (presentation boundary)."""
    try:
        return float(cast(Any, x))
    except (TypeError, ValueError):
        return 0.0


def bar(used: object, budget: object, width: int = 10) -> str:
    """A fixed-width budget bar `[██░░░░░░░░]`, fill colored by headroom (redundant with the %
    and any ⚠). Empty string when there's no budget to gauge against."""
    u, b = num(used), num(budget)
    if b <= 0:
        return ""
    frac = u / b
    filled = int(round(min(max(frac, 0.0), 1.0) * width))
    body = "█" * filled + "░" * (width - filled)
    col = "red" if frac > 1.0 else ("yellow" if frac > 0.8 else "green")
    return "[" + c(body, col) + "]"


def pct(used: object, budget: object) -> str:
    b = num(budget)
    return "" if b <= 0 else f"{round(100 * num(used) / b)}%"


def ascii_translate(s: str) -> str:
    """`--ascii` LAST step: translate glyphs to single ASCII chars (width-preserving), then
    encode-replace to GUARANTEE pure ASCII for anything unmapped. No-op unless ascii mode is on."""
    if not _ASCII:
        return s
    return s.translate(GLYPH_ASCII).encode("ascii", "replace").decode("ascii")
