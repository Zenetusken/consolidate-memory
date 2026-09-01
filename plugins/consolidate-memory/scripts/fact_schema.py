#!/usr/bin/env python3
"""Restricted stdlib fact-schema codec (ADR 011). Not a general YAML parser."""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Optional

SCHEMA_VERSION = 3
SENSITIVITY = ("public", "internal", "confidential", "secret")
SCOPES = ("project-local", "stack-general", "user-global")
CANONICAL_SCOPES = ("stack-general", "user-global")
STATUSES = ("active", "superseded", "tombstoned", "expired")
REQUIRED_V3 = (
    "schema_version", "fact_id", "name", "description", "domain",
    "sensitivity", "scope", "status",
    "applies_any", "applies_all", "applies_exclude",
    "content_modified", "last_observed_at",
)
CLASS_ACTIVE = "valid-active-v3"
CLASS_INACTIVE = "valid-inactive-v3"
CLASS_LEGACY = "legacy-migration"
CLASS_INVALID = "invalid"
_FACT_ID_RE = re.compile(r"^f_[0-9a-f]{24}$")
_RFC3339_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$")
_LIST_RE = re.compile(r"^\[(.*)\]$")
_APPLY_TOKEN_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
MAX_APPLY_TOKENS = 16
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


def stable_fact_id(domain: str, stem: str, schema_version: str = "2") -> str:
    """Same formula as control_plane.stable_fact_id (schema v2 identity, v3 envelope)."""
    return "f_" + hashlib.sha256(
        f"{schema_version}|{domain}|{stem}".encode("utf-8")).hexdigest()[:24]


def _real_rfc3339(ts: str) -> bool:
    """Shape AND a real calendar datetime (rejects 2026-02-30, hour 25)."""
    s = (ts or "").strip()
    if not _RFC3339_RE.match(s):
        return False
    core = s
    if core.endswith("Z"):
        core = core[:-1]
    elif len(core) >= 6 and core[-6] in "+-" and core[-3] == ":":
        core = core[:-6]
    elif len(core) >= 5 and core[-5] in "+-":
        core = core[:-5]
    if "." in core:
        core = core.split(".", 1)[0]
    try:
        datetime.strptime(core, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
    except ValueError:
        return False
    return True


def validate_canonical_frontmatter(fm: dict, *, stem: str, domain: str) -> Optional[str]:
    """Return an error string if a canonical is refused, else None.

    Writer path (upsert / migrate apply) must present the full ADR 011 key set
    after inject. Nested applies.*, name/domain/stem contradictions, unknown
    enums, and missing required fields all refuse.
    """
    if "applies" in fm:
        return ("nested applies: mapping refused (use applies_any/applies_all/"
                "applies_exclude flow lists)")
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
    id_domain = str(fm.get("domain") or "").strip() or domain
    if id_domain and id_domain != "unknown":
        want = stable_fact_id(id_domain, stem)
        if fid != want:
            return f"fact_id {fid!r} does not match stable id for ({id_domain}, {stem})"
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
        if not _real_rfc3339(ts):
            return f"invalid {ts_key} {ts!r}"
    for k in ("applies_any", "applies_all", "applies_exclude"):
        raw = str(fm.get(k) or "").strip()
        if raw and not _LIST_RE.match(raw):
            return f"{k} must be a bracketed flow list"
        items = _parse_flow_list(raw)
        if len(items) > MAX_APPLY_TOKENS:
            return f"{k} has {len(items)} tokens (max {MAX_APPLY_TOKENS})"
        for tok in items:
            if not _APPLY_TOKEN_RE.fullmatch(tok.lower()):
                return f"{k} token {tok!r} is not a capability tag"
    return None


def classify_canonical(text: str, *, stem: str, domain: str = "") -> dict:
    """Exactly one class: valid-active-v3 | valid-inactive-v3 | legacy-migration | invalid."""
    from memory_status import _frontmatter
    fm = _frontmatter(text or "")
    sv = str(fm.get("schema_version") or "").strip()
    if sv not in ("3", "v3"):
        return {"class": CLASS_LEGACY, "fm": fm, "error": "unversioned or pre-v3"}
    err = validate_canonical_frontmatter(fm, stem=stem, domain=domain)
    if err:
        return {"class": CLASS_INVALID, "fm": fm, "error": err}
    status = str(fm.get("status") or "").strip()
    if status != "active":
        return {"class": CLASS_INACTIVE, "fm": fm, "error": ""}
    return {"class": CLASS_ACTIVE, "fm": fm, "error": ""}


def applies_decision(applies: dict, caps: set, *, degraded: bool = False) -> str:
    """Three-state: match | no-match | unknown. Degraded never silently matches."""
    if not isinstance(applies, dict) or applies.get("error"):
        return "unknown"
    gated = bool(applies.get("any") or applies.get("all") or applies.get("exclude"))
    if degraded and gated:
        return "unknown"
    if not applies or not gated:
        return "match"
    exclude = set(applies.get("exclude") or [])
    if exclude and (exclude & caps):
        return "no-match"
    all_ = set(applies.get("all") or [])
    if all_ and not all_.issubset(caps):
        return "no-match"
    any_ = set(applies.get("any") or [])
    if any_ and not (any_ & caps):
        return "no-match"
    return "match"


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
