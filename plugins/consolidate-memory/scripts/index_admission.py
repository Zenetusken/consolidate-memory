#!/usr/bin/env python3
"""Exact native MEMORY.md admission: line AND byte caps with reserve.

Token estimates stay observability. The safety boundary is the UTF-8 text Claude
will actually load (200 lines or 25 KB, whichever first). A ~15% reserve keeps
plugin/native metadata from landing on the cliff.
"""
from __future__ import annotations

import re

NATIVE_INDEX_CAP_BYTES = 25 * 1024
NATIVE_INDEX_CAP_LINES = 200
RESERVE = 0.15
ARCHIVE_INDEX_CAP_BYTES = 1024 * 1024
ARCHIVE_INDEX_CAP_LINES = 10000
_POINTER_TARGET_RE = re.compile(r"\]\(([^)]+)\)")

# ── the pointer rule: ONE home for each half ────────────────────────────────────────────────────
# A store document answers "which facts do I place?" by two rules that used to be re-spelled in
# five modules, and the copies disagreed. They live here now, and every reader calls them.
_POINTER_REGION_END = re.compile(r"(?m)^(?:---\s*$|## )")


def pointer_region(text: str) -> str:
    """The HEADER REGION of a store document — the only part that may carry placements.

    A store index is not always a pure list. `SHIPPED.md` is a pointer block followed by hundreds
    of lines of prose quoted from the roadmap, and a *quoted* list item in that prose is not a
    placement: two facts read as ARCHIVED for months purely because their names appear inside a
    quotation (`docs/periphery-parity.spec.md:587` records this as §2.3's residual).

    The region ends at the first `---` rule or the first `## ` heading, whichever comes first —
    the same "whichever comes first" derivation `tests/docs_links.py::_spec_header_end` uses, so
    there is one boundary idiom rather than two. A pure pointer list (`MEMORY.md`) has neither and
    is returned whole, so it is unaffected.
    """
    t = text or ""
    m = _POINTER_REGION_END.search(t)
    return t[:m.start()] if m else t


def pointer_lines(text: str) -> list:
    """Every POINTER LINE of a document: ROLE and REGION applied, target or not.

    ROLE: an anchor counts only when its line is a pointer line (stripped text begins `- [`), so
    prose that merely *quotes* the pointer shape places nothing. `tests/smoke.py` (P10) already
    pins this for the archive path — the classifier is deliberately broader than the extractor —
    and this is that rule, made available to every reader rather than one.

    REGION: only `pointer_region` is read.

    This is the PRIMITIVE, and it returns LINES rather than targets because `archive_index` needs
    the role-passing lines whose target does not parse — it reports those as invalid syntax. The
    two questions ("what lines are pointers?" and "which facts do they place?") therefore get one
    implementation each, rather than one implementation and a near-copy that drifts.
    """
    return [s for s in (ln.strip() for ln in pointer_region(text).splitlines())
            if s.startswith("- [")]


def pointer_targets(text: str) -> list:
    """The pointer TARGETS a document places — the ONE derivation, for every reader.

    Derived from `pointer_lines`, so role and region have exactly one implementation. Returns
    stems in document order, duplicates included; callers that need a set or a duplicate report
    do that themselves — `archive_index` is the one that must, because a duplicate is a refusal
    it has to name rather than a set it can collapse.
    """
    out: list = []
    for s in pointer_lines(text):
        m = _POINTER_TARGET_RE.search(s)
        if not m:
            continue
        raw = m.group(1).strip()
        out.append(raw[:-3] if raw.endswith(".md") else raw)
    return out


def line_limit_with_reserve(reserve: float = RESERVE) -> int:
    return int(NATIVE_INDEX_CAP_LINES * (1.0 - reserve))


def byte_limit_with_reserve(reserve: float = RESERVE) -> int:
    return int(NATIVE_INDEX_CAP_BYTES * (1.0 - reserve))


def count_lines(text: str) -> int:
    if not text:
        return 0
    return len(text.splitlines())


def count_bytes(text: str) -> int:
    return len(text.encode("utf-8"))


def project_index(future_text: str, reserve: float = RESERVE) -> dict:
    """Build the exact future UTF-8 admission decision. PURE."""
    lines = count_lines(future_text)
    nbytes = count_bytes(future_text)
    lim_l = line_limit_with_reserve(reserve)
    lim_b = byte_limit_with_reserve(reserve)
    reasons = []
    if lines > lim_l:
        reasons.append(f"projected_lines {lines} > line_limit_with_reserve {lim_l}")
    if nbytes > lim_b:
        reasons.append(f"projected_bytes {nbytes} > byte_limit_with_reserve {lim_b}")
    # Native cliff (no reserve) — still refuse at the hard native caps.
    if lines > NATIVE_INDEX_CAP_LINES:
        reasons.append(f"projected_lines {lines} > native {NATIVE_INDEX_CAP_LINES}")
    if nbytes > NATIVE_INDEX_CAP_BYTES:
        reasons.append(f"projected_bytes {nbytes} > native {NATIVE_INDEX_CAP_BYTES}")
    return {
        "projected_lines": lines,
        "projected_bytes": nbytes,
        "line_limit": lim_l,
        "byte_limit": lim_b,
        "admitted": not reasons,
        "reason": "; ".join(reasons),
    }


def archive_index(future_text: str) -> dict:
    """On-demand archive (SHIPPED.md) admission. Not the always-loaded cliff.

    Enforces pointer syntax, unique contained stems, and a generous operational
    size cap. Does not apply INDEX_TOKEN_BUDGET or the 200-line/25KB native cliff.
    """
    from identifiers import IdentifierRefused, validate_fact_stem
    lines = count_lines(future_text)
    nbytes = count_bytes(future_text)
    reasons: list = []
    if lines > ARCHIVE_INDEX_CAP_LINES:
        reasons.append(
            f"projected_lines {lines} > archive line cap {ARCHIVE_INDEX_CAP_LINES}")
    if nbytes > ARCHIVE_INDEX_CAP_BYTES:
        reasons.append(
            f"projected_bytes {nbytes} > archive byte cap {ARCHIVE_INDEX_CAP_BYTES}")
    seen: set = set()
    targets: list = []
    for s in pointer_lines(future_text):   # ROLE + REGION, one home
        m = _POINTER_TARGET_RE.search(s)
        if not m:
            reasons.append("invalid pointer syntax: " + s[:80])
            continue
        raw = m.group(1).strip()
        stem = raw[:-3] if raw.endswith(".md") else raw
        try:
            stem = validate_fact_stem(stem)
        except IdentifierRefused as e:
            reasons.append("unsafe archive target: " + str(e))
            continue
        if stem in seen:
            reasons.append("duplicate archive target " + stem)
            continue
        seen.add(stem)
        targets.append(stem)
    return {
        "projected_lines": lines,
        "projected_bytes": nbytes,
        "targets": targets,
        "admitted": not reasons,
        "reason": "; ".join(reasons),
    }


def apply_pointer(current_text: str, pointer_line: str, stem: str) -> str:
    """Return the exact future index if `pointer_line` is the line for `stem`.

    R5 (v0.4.68): the READ rule and this WRITE rule are the SAME rule. This located the line to
    replace by bare substring — `f"]({stem}.md)" in ln` — with no shape test and no region, so a
    write could rewrite a line its own reader does not count as a pointer (a prose mention, say)
    and report success while the fact stayed unplaced. `admit_write` cannot catch that: it
    measures the index's SIZE, not whether the placement the write made is one the reader sees.
    A reader stricter than its writer is a silent data-loss shape, so both halves ask
    `pointer_lines`.

    The fallback inserts at the END OF THE REGION, not the end of the file — below a divider the
    reader is blind, and writing where your own reader cannot look is the same defect. For a pure
    pointer list (`MEMORY.md`) the region is the whole file, so this is byte-identical to the old
    append.
    """
    text = current_text if current_text else "# Memory Index\n\n"
    region = pointer_region(text)
    rest = text[len(region):]
    target, short = f"]({stem}.md)", f"]({stem})"
    replaced = False
    out = []
    for s in region.splitlines():
        if not replaced and s.strip().startswith("- [") and (target in s or short in s):
            out.append(pointer_line.rstrip("\n"))
            replaced = True
            continue
        out.append(s)
    if not replaced:
        if out and out[-1].strip():
            out.append("")
        out.append(pointer_line.rstrip("\n"))
    body = "\n".join(out) + "\n"
    future = body + rest if rest else body
    return future if future.endswith("\n") else future + "\n"


def admit_write(current_text: str, pointer_line: str, stem: str, reserve: float = RESERVE) -> dict:
    future = apply_pointer(current_text, pointer_line, stem)
    decision = project_index(future, reserve=reserve)
    decision["future_text"] = future
    return decision
