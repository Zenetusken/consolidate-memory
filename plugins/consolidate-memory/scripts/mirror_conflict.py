#!/usr/bin/env python3
"""Three-way managed-mirror classifier. Pull must never silently overwrite a local edit."""
from __future__ import annotations

import hashlib
import re
from typing import Optional

VOLATILE_KEYS = (
    "modified", "mirrored_at", "projects", "last_used", "last_read", "usage",
    "global_ref_since", "content_modified", "verified_at", "last_observed_at",
    "mirrored_at", "holder", "base_revision", "canonical_revision",
    "canonical_fact_id", "canonical_domain",
    "group",
)

REFRESH = "refresh"
STOP_LOCAL = "stop-local"
RESTAMP = "restamp"
CONFLICT = "conflict"
QUARANTINE = "quarantine"
IN_SYNC = "in-sync"


def _frontmatter_span(text: str) -> tuple:
    """Real parsers — same body as global_ref_body / _body_hash (not split('---'))."""
    from memory_status import _frontmatter
    from sync_global import _body
    return _frontmatter(text), _body(text)


def _metadata_block_payload(text: str) -> str:
    """The metadata: block's non-volatile key/value pairs, indentation-normalized.

    `_frontmatter`'s indented-child flattening recognizes a FIXED key list, so a local
    edit to an UNKNOWN key inside `metadata:` never reached the semantic payload and
    the next pull silently discarded it. This captures every INDENTED `key: value`
    line of the raw block (volatile keys stripped) so sem(mirror) reflects the whole
    user-writable metadata block — indentation-insensitive, so writer-normalized
    mirrors still equal their canonical.

    The block ends at the first de-indented line (YAML) or the frontmatter-closing
    `---` — the writer's SYNTHESIZED anchor on a no-metadata canonical sits at the
    top with unindented keys after it, which must not read as block children.
    """
    pairs = []
    in_meta = False
    for ln in text.splitlines():
        s = ln.strip()
        if in_meta:
            if s.startswith("---") or (s and not ln.startswith((" ", "\t"))):
                break
            mm = re.match(r"^[ \t]*([A-Za-z0-9_.-]+):[ \t]*(.*)$", ln)
            if not mm:
                continue
            key, val = mm.group(1), mm.group(2).strip()
            kl = key.lower()
            if kl in VOLATILE_KEYS or kl.startswith("global_ref"):
                continue
            pairs.append(f"{kl}={val}")
        elif re.match(r"^metadata:[ \t]*$", ln):
            in_meta = True
    return "".join(p + "\n" for p in sorted(pairs))


def semantic_payload(text: str) -> str:
    """Fact content that participates in revision equality (volatile metadata stripped)."""
    fm, body = _frontmatter_span(text)
    keep = []
    for k in sorted(fm):
        kl = k.lower().lstrip("#").strip()
        if kl.startswith("#") or k.lstrip().startswith("#"):
            continue
        if kl in VOLATILE_KEYS or kl.startswith("global_ref"):
            continue
        # v0.4.2 P3: `_frontmatter` parses a `metadata:` BLOCK as an empty parent key with its
        # children flattened to top level (real content — e.g. `type:`) hashes via those children.
        # The bare anchor is not content, and hashing it made every mirror's semantic payload
        # differ from its canonical's by exactly that line — which structurally disabled the
        # manifest fast path (sem(mirror) could never equal sem(canonical)). Skip ONLY the empty
        # anchor; a scalar `metadata: <value>` still hashes.
        if kl == "metadata" and not str(fm[k] or ""):
            continue
        keep.append(f"{k}:{fm[k]}")
    return "\n".join(keep) + "\n--\n" + _metadata_block_payload(text) + body


def semantic_hash(text: str) -> str:
    return hashlib.sha256(semantic_payload(text).encode("utf-8")).hexdigest()[:16]


def body_hash(text: str) -> str:
    from sync_global import _body_hash
    return _body_hash(text)


def classify_mirror(local_text: str, canonical_text: str,
                    base_revision: Optional[str] = None,
                    allow_legacy_fallback: bool = True) -> dict:
    """Three-way decision. Never overwrite a divergent local body.

    Holder-table `base_revision` is authoritative (ADR 011). When
    `allow_legacy_fallback` is False, a missing holder base quarantines
    instead of trusting editable mirror frontmatter.
    """
    fm, _ = _frontmatter_span(local_text)
    local_sem = semantic_hash(local_text)
    canon_sem = semantic_hash(canonical_text)
    local_body = body_hash(local_text)
    canon_body = body_hash(canonical_text)
    base = (base_revision or "").strip() or None
    if base is None and allow_legacy_fallback:
        base = str(fm.get("base_revision") or "").strip() or None
    if base is None and not allow_legacy_fallback:
        return {"action": QUARANTINE, "reason": "missing holder lineage",
                "local": local_sem, "canonical": canon_sem, "base": None}
    ref_body = str(fm.get("global_ref_body") or "").strip() or None

    if not local_text.strip():
        return {"action": QUARANTINE, "reason": "empty local mirror",
                "local": local_sem, "canonical": canon_sem, "base": base}

    # Pre-v2 managed mirrors have no semantic base and may lack global_ref_body.
    # Refresh (historical behaviour) so existing STALE tests and unstamped
    # fleet mirrors keep updating; quarantine is for empty/corrupt files.

    if local_sem == canon_sem:
        return {"action": RESTAMP if local_text != canonical_text else IN_SYNC,
                "reason": "semantic match",
                "local": local_sem, "canonical": canon_sem, "base": base}

    if base:
        local_changed = local_sem != base
        canon_changed = canon_sem != base
        if not local_changed and canon_changed:
            return {"action": REFRESH, "reason": "canonical advanced, local at base",
                    "local": local_sem, "canonical": canon_sem, "base": base}
        if local_changed and not canon_changed:
            return {"action": STOP_LOCAL, "reason": "local edit, canonical at base",
                    "local": local_sem, "canonical": canon_sem, "base": base}
        if local_changed and canon_changed:
            if local_sem == canon_sem:
                return {"action": RESTAMP, "reason": "same resulting change",
                        "local": local_sem, "canonical": canon_sem, "base": base}
            return {"action": CONFLICT, "reason": "divergent simultaneous change",
                    "local": local_sem, "canonical": canon_sem, "base": base}
        return {"action": IN_SYNC, "reason": "all three equal",
                "local": local_sem, "canonical": canon_sem, "base": base}

    # Missing both semantic base and body-hash. Same BODY (Probe C description drift)
    # still refreshes. Divergent bodies cannot be three-wayed → quarantine, never overwrite.
    if not ref_body:
        if local_body == canon_body:
            return {"action": REFRESH, "reason": "legacy: same body, no revision base",
                    "local": local_sem, "canonical": canon_sem, "base": None}
        return {"action": QUARANTINE, "reason": "missing base_revision and global_ref_body",
                "local": local_sem, "canonical": canon_sem, "base": None}

    if local_body == ref_body and canon_body != ref_body:
        return {"action": REFRESH, "reason": "legacy: canonical body advanced",
                "local": local_sem, "canonical": canon_sem, "base": ref_body}
    if local_body != ref_body and canon_body == ref_body:
        return {"action": STOP_LOCAL, "reason": "legacy: local body edited",
                "local": local_sem, "canonical": canon_sem, "base": ref_body}
    if local_body != ref_body and canon_body != ref_body and local_body != canon_body:
        return {"action": CONFLICT, "reason": "legacy: divergent bodies",
                "local": local_sem, "canonical": canon_sem, "base": ref_body}
    # Body still at the last mirrored hash, semantic differs → canonical
    # frontmatter/description changed (Probe C). Refresh, don't restamp.
    if local_body == ref_body and local_sem != canon_sem:
        return {"action": REFRESH, "reason": "legacy: pointer/description drift, body at base",
                "local": local_sem, "canonical": canon_sem, "base": ref_body}
    if local_body == canon_body:
        return {"action": RESTAMP, "reason": "legacy: same body, metadata/desc drift",
                "local": local_sem, "canonical": canon_sem, "base": ref_body}
    return {"action": RESTAMP, "reason": "legacy: remainder",
            "local": local_sem, "canonical": canon_sem, "base": ref_body}


def stamp_revisions(mirror_text: str, base_rev: str, canon_rev: str) -> str:
    """Insert/replace base_revision and canonical_revision in frontmatter."""
    if not mirror_text.startswith("---"):
        return (f"---\nbase_revision: {base_rev}\ncanonical_revision: {canon_rev}\n---\n"
                + mirror_text)
    lines = mirror_text.splitlines()
    out = []
    dashes = 0
    seen_base = seen_canon = False
    for i, ln in enumerate(lines):
        s = ln.strip()
        if dashes == 0 and i == 0 and ln == "---":
            dashes = 1
            out.append(ln)
            continue
        if dashes == 1 and ln.startswith("---"):
            if not seen_base:
                out.append(f"  base_revision: {base_rev}")
            if not seen_canon:
                out.append(f"  canonical_revision: {canon_rev}")
            dashes = 2
            out.append(ln)
            continue
        if dashes == 1 and s.startswith("base_revision:"):
            out.append(f"  base_revision: {base_rev}" if ln[:1].isspace()
                       else f"base_revision: {base_rev}")
            seen_base = True
            continue
        if dashes == 1 and s.startswith("canonical_revision:"):
            out.append(f"  canonical_revision: {canon_rev}" if ln[:1].isspace()
                       else f"canonical_revision: {canon_rev}")
            seen_canon = True
            continue
        out.append(ln)
    return "\n".join(out) + ("\n" if mirror_text.endswith("\n") else "")
