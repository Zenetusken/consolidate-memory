#!/usr/bin/env python3
"""Restricted stdlib fact-schema codec (ADR 011). Not a general YAML parser."""
from __future__ import annotations

import re
from typing import Optional

SCHEMA_VERSION = 3
SENSITIVITY = ("public", "internal", "confidential", "secret")
SCOPES = ("project-local", "stack-general", "user-global")
STATUSES = ("active", "superseded", "tombstoned", "expired")
_LIST_RE = re.compile(r"^\[(.*)\]$")
# Nested YAML applies.any is not representable in the flat frontmatter parser.
# Those keys must be migrated to applies_any / applies_all / applies_exclude
# (flow lists) or refused — never silently flattened.
_NESTED_APPLIES = ("applies.any", "applies.all", "applies.exclude")


def _parse_flow_list(raw: str) -> list:
    s = (raw or "").strip()
    m = _LIST_RE.match(s)
    if not m:
        if not s:
            return []
        return [s]
    inner = m.group(1).strip()
    if not inner:
        return []
    return [p.strip().strip("\"'") for p in inner.split(",") if p.strip()]


def format_flow_list(items: list) -> str:
    vals = [str(x).strip() for x in (items or []) if str(x).strip()]
    return "[" + ", ".join(vals) + "]"


def validate_canonical_frontmatter(fm: dict, *, stem: str, domain: str) -> Optional[str]:
    """Return an error string if a canonical is refused, else None.

    Writer-injected domain/name are checked against the path/context. Missing
    optional v3 fields are tolerated on read (migrate fills them); contradictory
    name/domain/stem, unknown enums, and nested applies.* keys are not.
    """
    for nested in _NESTED_APPLIES:
        if nested in fm and str(fm.get(nested) or "").strip():
            return (f"nested {nested} is refused (use applies_any/applies_all/"
                    "applies_exclude flow lists)")
    name = str(fm.get("name") or "").strip()
    if name and name != stem:
        return f"name {name!r} does not match stem {stem!r}"
    fdom = str(fm.get("domain") or "").strip()
    if fdom and domain and domain != "unknown" and fdom != domain:
        return f"fact domain {fdom!r} does not match writer domain {domain!r}"
    sens = str(fm.get("sensitivity") or "internal").strip().lower()
    if fm.get("sensitivity") and sens not in SENSITIVITY:
        return f"invalid sensitivity {sens!r}"
    scope = str(fm.get("scope") or "").strip()
    if scope and scope not in SCOPES:
        return f"invalid scope {scope!r}"
    status = str(fm.get("status") or "active").strip()
    if fm.get("status") and status not in STATUSES:
        return f"invalid status {status!r}"
    return None


def applies_from_fm(fm: dict) -> dict:
    """One-representation applies: flow-list any/all/exclude. Nested keys are errors."""
    for nested in _NESTED_APPLIES:
        if nested in fm and str(fm.get(nested) or "").strip():
            return {"any": [], "all": [], "exclude": [],
                    "error": f"nested {nested} refused"}
    return {
        "any": _parse_flow_list(str(fm.get("applies_any") or "")),
        "all": _parse_flow_list(str(fm.get("applies_all") or "")),
        "exclude": _parse_flow_list(str(fm.get("applies_exclude") or "")),
    }
