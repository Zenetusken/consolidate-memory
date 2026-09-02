#!/usr/bin/env python3
"""Validated identifiers and contained path joins.

Agent-generated CLI arguments are not a trusted boundary. Every domain, fact stem,
project id, and child path must pass these checks before it is interpolated into a
filesystem path or used as a trust-domain grant.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

# Operator-chosen domain names. "unknown" is the unenrolled sentinel, not a grant.
DOMAIN_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
FACT_STEM_RE = re.compile(r"^[A-Za-z0-9._-]+$")
FACT_STEM_MAX_CHARS = 96
FACT_STEM_MAX_BYTES = 180
PROJECT_ID_RE = re.compile(r"^p_[0-9a-f]{32}$")
RESERVED_DOMAINS = frozenset({
    "unknown", ".", "..", "memory", "locks", "ops", "journal", "con", "prn", "aux",
})
RESERVED_STEMS = frozenset({"MEMORY"})


class IdentifierRefused(ValueError):
    """Raised when an identifier is not a contained, grammar-valid id."""


def validate_domain_id(raw: str, *, allow_unknown: bool = False) -> str:
    s = (raw or "").strip()
    if allow_unknown and s in ("", "unknown"):
        return "unknown"
    if not s or s != s.lower():
        raise IdentifierRefused("domain must be lowercase [a-z0-9][a-z0-9_-]{0,63}")
    if s in RESERVED_DOMAINS:
        raise IdentifierRefused(f"reserved domain {s!r}")
    if "/" in s or "\\" in s or ".." in s or s.startswith("-"):
        raise IdentifierRefused("domain must not contain path components")
    if not DOMAIN_RE.fullmatch(s):
        raise IdentifierRefused(f"invalid domain {s!r}")
    return s


def validate_fact_stem(raw: str) -> str:
    s = (raw or "").strip()
    if not s or not FACT_STEM_RE.fullmatch(s) or s.upper() in RESERVED_STEMS:
        raise IdentifierRefused(f"unsafe or reserved stem {raw!r}")
    if "/" in s or "\\" in s or s in (".", ".."):
        raise IdentifierRefused(f"stem must not be a path {raw!r}")
    if len(s) > FACT_STEM_MAX_CHARS or len(s.encode("utf-8")) > FACT_STEM_MAX_BYTES:
        raise IdentifierRefused(
            f"stem exceeds {FACT_STEM_MAX_CHARS} chars / {FACT_STEM_MAX_BYTES} bytes")
    return s


def validate_project_id(raw: str) -> str:
    s = (raw or "").strip()
    if not PROJECT_ID_RE.fullmatch(s):
        raise IdentifierRefused(f"invalid project id {raw!r}")
    return s


def safe_child(root: Path, name: str) -> Path:
    """Join `name` under `root` and require the resolved path stay inside root.

    Rejects absolute names, parent traversal, NUL, and symlink escapes once
    the parent exists. The returned path may not exist yet.
    """
    if not name or "\x00" in name:
        raise IdentifierRefused("empty or NUL path component")
    n = Path(name)
    if n.is_absolute() or str(name).startswith("/") or str(name).startswith("\\"):
        raise IdentifierRefused(f"absolute child refused: {name!r}")
    if any(p in (".", "..") for p in n.parts):
        raise IdentifierRefused(f"path traversal refused: {name!r}")
    try:
        base = root.resolve()
    except OSError:
        base = root
    candidate = root / n
    try:
        resolved = candidate.resolve()
    except OSError:
        resolved = candidate
    try:
        resolved.relative_to(base)
    except ValueError:
        raise IdentifierRefused(f"path escapes root {base}: {name!r}")
    return candidate


def contained_under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except (ValueError, OSError):
        return False
