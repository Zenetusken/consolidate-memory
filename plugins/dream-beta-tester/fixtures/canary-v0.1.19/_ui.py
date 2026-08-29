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
import re
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


def set_modes(color: bool = False, ascii: bool = False, width: int = 0) -> None:
    """Set the module-level color/ascii/width state once (from a script's main()). `width`
    sets the uniform render width W (the banner rule + the wrap right-edge); 0 leaves the
    default so the wrap stays uniform with the banner."""
    global _COLOR, _ASCII, W
    _COLOR, _ASCII = color, ascii
    if width:
        W = max(40, int(width))


def resolve_width(argv: list, stream: object) -> int:
    """Resolve the uniform render width. `--width=N` wins (manual override). Otherwise fill the
    terminal when stdout is a TTY — clamped to a readable [60, 100] so lines never get too long
    to scan or too narrow to hold a table. For a pipe / captured output / test (no TTY) fall back
    to the fixed default W, so non-interactive output stays deterministic AND uniform."""
    for a in argv:
        if a.startswith("--width="):
            try:
                return max(40, int(a.split("=", 1)[1]))
            except ValueError:
                pass
    isatty = getattr(stream, "isatty", None)
    if isatty and isatty():
        try:
            return max(60, min(os.get_terminal_size().columns, 100))
        except OSError:
            pass
    return W


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
    """A section line: BOLD UPPERCASE label (carries hierarchy even in monochrome) + value.
    The value is word-wrapped to W with a HANGING INDENT under the value column (12), so a long
    value continues aligned under itself instead of overflowing the right edge or wrapping to
    column 0."""
    return f"  {c(f'{label:<10}', 'bold')}{wrap(value, hang=12, width=W)}"


def li(text: str, indent: int = 4, bullet: str = "", bullet_color: str = "dim", width: int = 0) -> str:
    """A wrapped list item under a section: `<indent spaces><bullet> <text>`, with `text`
    HANGING-INDENTED under its own first character (a wrapped item lines up under itself, not
    back at column 0). `bullet=''` → a plain indented, wrapped line. ANSI-safe via wrap()."""
    pre = " " * indent + (c(bullet, bullet_color) + " " if bullet else "")
    hang = indent + (2 if bullet else 0)   # bullet (1 col) + its trailing space
    return pre + wrap(text, hang=hang, width=width)


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


_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def vis(s: str) -> int:
    """Visible column width — ANSI SGR escape sequences occupy no columns."""
    return len(_ANSI_RE.sub("", s))


def _active_sgr(s: str) -> str:
    """ALL SGR codes still OPEN at the end of `s` (concatenated), or '' if the last was a reset.
    Accumulates since the last reset so a STACKED span (e.g. c(x, 'bold', 'green') = TWO codes)
    re-opens FULLY on the next wrapped line — not just its final attribute — keeping a wrapped
    colored span fully colored."""
    opened: list = []
    for m in _ANSI_RE.finditer(s):
        if m.group() == CODES["reset"]:
            opened = []
        else:
            opened.append(m.group())
    return "".join(opened)


def wrap(value: str, hang: int = 0, width: int = 0) -> str:
    """Word-wrap `value` (which may contain ANSI color) so each line fits `width` (default W)
    VISIBLE columns, with continuation lines indented `hang` spaces — a HANGING INDENT that keeps
    wrapped text aligned under where its section's content began, instead of falling back to
    column 0. The first line is NOT indented (the caller's label/bullet prefix already occupies
    `hang`). ANSI-aware: measures visible width, never splits an escape, and re-opens the active
    color after each break. A single word wider than the budget is kept whole (it overflows
    rather than being chopped mid-token, so hashes/paths/bars stay intact)."""
    budget = max(8, (width or W) - hang)   # per-line content width after the hanging indent
    lines: list = []
    cur = ""
    for word in value.split():   # split() collapses whitespace runs + strips → clean prose wrap (no empty tokens, no stray trailing space at a break)
        cand = word if not cur else cur + " " + word
        if cur and vis(cand) > budget:
            opened = _active_sgr(cur)
            lines.append(cur + (CODES["reset"] if opened else ""))
            cur = opened + word
        else:
            cur = cand
    if cur:
        lines.append(cur)
    return ("\n" + " " * hang).join(lines)


def ascii_translate(s: str) -> str:
    """`--ascii` LAST step: translate glyphs to single ASCII chars (width-preserving), then
    encode-replace to GUARANTEE pure ASCII for anything unmapped. No-op unless ascii mode is on."""
    if not _ASCII:
        return s
    return s.translate(GLYPH_ASCII).encode("ascii", "replace").decode("ascii")
