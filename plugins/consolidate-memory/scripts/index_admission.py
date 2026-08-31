#!/usr/bin/env python3
"""Exact native MEMORY.md admission: line AND byte caps with reserve.

Token estimates stay observability. The safety boundary is the UTF-8 text Claude
will actually load (200 lines or 25 KB, whichever first). A ~15% reserve keeps
plugin/native metadata from landing on the cliff.
"""
from __future__ import annotations

NATIVE_INDEX_CAP_BYTES = 25 * 1024
NATIVE_INDEX_CAP_LINES = 200
RESERVE = 0.15


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


def apply_pointer(current_text: str, pointer_line: str, stem: str) -> str:
    """Return the exact future index if `pointer_line` is the line for `stem`."""
    text = current_text if current_text else "# Memory Index\n\n"
    lines = text.splitlines()
    replaced = False
    out = []
    for ln in lines:
        if f"]({stem}.md)" in ln or f"]({stem})" in ln:
            if not replaced:
                out.append(pointer_line.rstrip("\n"))
                replaced = True
            continue
        out.append(ln)
    if not replaced:
        if out and out[-1].strip():
            out.append("")
        out.append(pointer_line.rstrip("\n"))
    return "\n".join(out) + "\n"


def admit_write(current_text: str, pointer_line: str, stem: str, reserve: float = RESERVE) -> dict:
    future = apply_pointer(current_text, pointer_line, stem)
    decision = project_index(future, reserve=reserve)
    decision["future_text"] = future
    return decision
