#!/usr/bin/env python3
"""Typed identity for domains, projects, facts, and canonical refs.

Bare stems are not a trust boundary. Ordinary fleet operations take a
StoreContext and enumerate CanonicalRef objects via
``sync_global.iter_canonicals`` (ADR 008 / 015).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from identifiers import (
    IdentifierRefused,
    validate_domain_id,
    validate_fact_stem,
    validate_project_id,
)

REGISTRY_ABSENT = "absent"
REGISTRY_HEALTHY = "healthy"
REGISTRY_LOCKED = "locked"
REGISTRY_CORRUPT = "corrupt"
REGISTRY_PERMISSION = "permission-denied"
REGISTRY_INCOMPATIBLE = "incompatible"
REGISTRY_STATES = (
    REGISTRY_ABSENT, REGISTRY_HEALTHY, REGISTRY_LOCKED,
    REGISTRY_CORRUPT, REGISTRY_PERMISSION, REGISTRY_INCOMPATIBLE,
)


def as_domain_id(raw: str, *, allow_unknown: bool = False) -> str:
    return validate_domain_id(raw, allow_unknown=allow_unknown)


def as_project_id(raw: str) -> str:
    return validate_project_id(raw)


def as_fact_id(raw: str) -> str:
    s = (raw or "").strip()
    if not s.startswith("f_") or len(s) < 10:
        raise IdentifierRefused(f"invalid fact id {raw!r}")
    return s


@dataclass(frozen=True)
class CanonicalRef:
    fact_id: str
    domain_id: str
    stem: str
    canonical_path: Path
    revision: str = ""
    sensitivity: str = "internal"
    scope: str = "user-global"

    @property
    def key(self) -> tuple:
        return (self.domain_id, self.stem)


def ref_from_path(path: Path, fm: dict, *, fact_id: str = "",
                  revision: str = "") -> CanonicalRef:
    stem = validate_fact_stem(path.stem)
    domain = str(fm.get("domain") or "").strip() or "unknown"
    if domain != "unknown":
        domain = validate_domain_id(domain)
    fid = fact_id or str(fm.get("fact_id") or "")
    if not fid:
        from control_plane import stable_fact_id
        fid = stable_fact_id(domain, stem)
    return CanonicalRef(
        fact_id=fid,
        domain_id=domain,
        stem=stem,
        canonical_path=path,
        revision=revision or str(fm.get("canonical_revision") or ""),
        sensitivity=str(fm.get("sensitivity") or "internal").strip().lower() or "internal",
        scope=str(fm.get("scope") or "user-global").strip() or "user-global",
    )
