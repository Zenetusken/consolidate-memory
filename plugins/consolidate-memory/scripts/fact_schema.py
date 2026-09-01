#!/usr/bin/env python3
"""Restricted stdlib fact-schema codec (ADR 011). Not a general YAML parser."""
from __future__ import annotations

import re
from typing import Optional

SCHEMA_VERSION = 3
SENSITIVITY = ("public", "internal", "confidential", "secret")
SCOPES = ("project-local", "stack-general", "user-global")
STATUSES = ("active", "superseded", "tombstoned", "expired")
REQUIRED_V3 = (
    "schema_version", "fact_id", "name", "description", "domain",
    "sensitivity", "scope", "status",
    "applies_any", "applies_all", "applies_exclude",
    "content_modified", "last_observed_at",
)
_FACT_ID_RE = re.compile(r"^f_[0-9a-f]{24}$")
_RFC3339_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$")
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

    Writer path (upsert / migrate apply) must present the full ADR 011 key set
    after inject. Nested applies.*, name/domain/stem contradictions, unknown
    enums, and missing required fields all refuse.
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
    for key in REQUIRED_V3:
        raw = fm.get(key)
        if raw is None or (isinstance(raw, str) and not raw.strip()):
            return f"missing required field {key}"
    sv = str(fm.get("schema_version") or "").strip()
    if sv not in ("3", "v3"):
        return f"invalid schema_version {sv!r}"
    fid = str(fm.get("fact_id") or "").strip()
    if not _FACT_ID_RE.match(fid):
        return f"invalid fact_id {fid!r}"
    sens = str(fm.get("sensitivity") or "").strip().lower()
    if sens not in SENSITIVITY:
        return f"invalid sensitivity {sens!r}"
    scope = str(fm.get("scope") or "").strip()
    if scope not in SCOPES:
        return f"invalid scope {scope!r}"
    status = str(fm.get("status") or "").strip()
    if status not in STATUSES:
        return f"invalid status {status!r}"
    for ts_key in ("content_modified", "last_observed_at"):
        ts = str(fm.get(ts_key) or "").strip()
        if not _RFC3339_RE.match(ts):
            return f"invalid {ts_key} {ts!r}"
    for k in ("applies_any", "applies_all", "applies_exclude"):
        raw = str(fm.get(k) or "").strip()
        if raw and not _LIST_RE.match(raw):
            return f"{k} must be a bracketed flow list"
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
