#!/usr/bin/env python3
"""Trust-boundary policy: domain + sensitivity. Applicability is a different matcher.

`user-global` is domain-global, not installation-global. Unknown-domain projects
receive no domain-tagged cross-project facts. Cross-domain replication is denied
unless an explicit authorization pair exists. Secret bodies are never retained.
"""
from __future__ import annotations

import re
from typing import Any, Optional

SENSITIVITY = ("public", "internal", "confidential", "secret")
SAFE_POINTER_RE = re.compile(r"^(see|ref|pointer):\s+\S+", re.I)

# Dual-read: untagged legacy facts may still flow to unknown-domain projects.
# That is NOT an assignment to a universal domain (ADR 003 / 007).
MIGRATION_DUAL_READ = "dual-read"
MIGRATION_ENFORCED = "enforced"


def fact_domain(fm: dict) -> str:
    d = str(fm.get("domain") or "").strip()
    if d:
        return d
    return ""


def fact_sensitivity(fm: dict) -> str:
    s = str(fm.get("sensitivity") or "internal").strip().lower()
    return s if s in SENSITIVITY else "internal"


def is_secret_body(text: str, looks_secret) -> bool:
    """True if the body should be refused as a retained fact (safe pointer only)."""
    if looks_secret(text):
        return True
    return fact_sensitivity(_frontmatter_lite(text)) == "secret" and not SAFE_POINTER_RE.search(
        _body_lite(text))


def _frontmatter_lite(text: str) -> dict:
    # Tiny local parse so domain_policy stays import-light. Real frontmatter goes
    # through memory_status._frontmatter at the I/O boundary.
    out: dict = {}
    if not text.startswith("---"):
        return out
    parts = text.split("---", 2)
    if len(parts) < 3:
        return out
    for line in parts[1].splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            k, v = k.strip(), v.strip().strip("\"'")
            if k:
                out[k] = v
    return out


def _body_lite(text: str) -> str:
    if not text.startswith("---"):
        return text
    parts = text.split("---", 2)
    return parts[2] if len(parts) >= 3 else text


def admit_cross_project(project_domain: str, fm: dict, *,
                        migration_mode: str = MIGRATION_DUAL_READ,
                        authorized_pairs: Optional[set] = None,
                        looks_secret=None) -> bool:
    """May this project receive this canonical fact?

    Dual-read: untagged fact + unknown project → True (legacy probes).
    Tagged fact + unknown project → False.
    Cross-domain → False unless (src, dst) in authorized_pairs.
    Secret → False (never replicate a secret body).
    Confidential → only same domain.
    Enforced: untagged facts are not admitted (legacy-unassigned until reviewed).
    """
    pdom = (project_domain or "unknown").strip() or "unknown"
    fdom = fact_domain(fm)
    sens = fact_sensitivity(fm)
    if sens == "secret":
        return False
    if looks_secret is not None:
        blob = str(fm.get("description") or "") + "\n" + str(fm.get("body") or "")
        if blob.strip() and looks_secret(blob):
            return False
    auth = authorized_pairs or set()

    if pdom == "unknown":
        if fdom:
            return False
        return migration_mode != MIGRATION_ENFORCED

    if not fdom:
        return migration_mode != MIGRATION_ENFORCED

    if fdom != pdom:
        if (fdom, pdom) in auth:
            return sens != "confidential" and sens != "secret"
        return False
    return True


def secret_safe_pointer(description: str) -> str:
    desc = (description or "redacted").strip().splitlines()[0][:80]
    return f"see: [redacted secret — {desc}]\n"


def validate_write_policy(text: str, fm: dict, *, looks_secret, domain: str) -> Optional[str]:
    """Return an error string if a canonical/project write is refused, else None."""
    if looks_secret(text):
        return "secret-shaped body refused (retain a safe pointer only)"
    if fact_sensitivity(fm) == "secret" and not SAFE_POINTER_RE.search(_body_lite(text)):
        return "sensitivity=secret requires a safe pointer body, not the secret"
    fdom = fact_domain(fm)
    if fdom and domain and fdom != domain and domain != "unknown":
        return f"fact domain {fdom!r} does not match writer domain {domain!r}"
    if fact_sensitivity(fm) == "confidential" and domain == "unknown":
        return "confidential fact refused for unknown-domain writer"
    return None
