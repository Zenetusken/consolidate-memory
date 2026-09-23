#!/usr/bin/env python3
"""Transactional native-store writer: cm local upsert/update/archive/forget/rebuild-index.

Project-local facts are not domain canonicals. LocalFactV1 is a distinct contract
(not canonical schema v3): secret check, index admission, and journaled fact+pointer
publication share the canonical writer's *transaction* path, not its codec.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Optional

from store_context import StoreContext, WriteRefused, assert_writable

# Placeholder [[wikilink]] targets that almost always mean "I wrote a format example".
_PLACEHOLDER_LINK_TARGETS = frozenset({"link", "name", "wikilink", "stem", "target"})

LOCAL_SCHEMA_VERSION = 1
LOCAL_RESERVED = (
    "local_schema_version", "name", "description", "scope", "status",
    "sensitivity", "content_modified", "last_observed_at",
)
LOCAL_RESERVED_SET = frozenset(LOCAL_RESERVED)
LOCAL_SENSITIVITY = ("public", "internal", "confidential")
LOCAL_STATUSES = ("active", "superseded", "expired")
REBUILD_CONFIRM = "rebuild-local-index"
MIGRATE_CONFIRM = "migrate-local-schema"


def _looks_secret_fn():
    from memory_status import _looks_secret
    return _looks_secret


def _utc_now() -> str:
    from datetime import datetime, timezone
    dt = datetime.now(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S") + "Z"


def _fit_hook(prefix: str, desc: str, suffix: str, budget: int) -> str:
    """Word-boundary truncate so est_tokens(prefix + hook + suffix) ≤ budget."""
    from memory_status import est_tokens
    if est_tokens(prefix + desc + suffix) <= budget:
        return desc
    lo, hi = 0, len(desc)
    best_n = 0
    while lo <= hi:
        mid = (lo + hi) // 2
        if est_tokens(prefix + desc[:mid] + "…" + suffix) <= budget:
            best_n = mid
            lo = mid + 1
        else:
            hi = mid - 1
    if best_n <= 0:
        return "…"
    chunk = desc[:best_n].rstrip()
    sp = max(chunk.rfind(" "), chunk.rfind("\t"))
    if sp >= 1:
        chunk = chunk[:sp].rstrip()
    if not chunk:
        chunk = desc[:best_n].rstrip()
    return chunk + "…"


def _stored_pointer(idx_text: str, stem: str) -> "str | None":
    """The pointer LINE `MEMORY.md` currently holds for `stem`, or None.

    Requires the pointer SHAPE (`- [title](stem.md)…`), not merely a link target equal to the
    stem: a line that connects the stem but is not a pointer for it is a hand-edit, and the
    index's other readers already have to reason about those.
    """
    from memory_status import _LINK_RE
    for ln in idx_text.splitlines():
        m = _LINK_RE.search(ln)
        if m and m.group(1) == stem and ln.lstrip().startswith("- ["):
            return ln
    return None


def _cue_is_current(stored_line: str, stem: str, desc: str) -> bool:
    """Could `_pointer` have produced `stored_line` from `desc`?

    The second condition of the keep, and the one that stops it CEMENTING a stale cue.
    Comparing only the previous description is not enough, and the failure is not hypothetical:
    a cue whose description changed **while the write path was refusing it** (a firewall false
    positive) is stale exactly when the next write compares `prev_desc == new_desc` — both are
    the CURRENT description — so a keep keyed on that alone preserves the stale line forever.
    MEASURED on the roadmap's own case: body v0.4.40, pointer v0.4.34, and the naive rule keeps
    v0.4.34.

    The test is truncation-consistency: `_pointer` derives the hook by taking a WORD-BOUNDARY
    PREFIX of the normalised description (or all of it when it fits), so a line the constructor
    could have written has a hook that is a prefix of that normalisation. Case-folded, because
    the stores carry both (`a gate proves…` stored against `A gate proves…` derived) and the
    hook's own case is not a signal.
    """
    hook = stored_line
    for cut in (" [project-local]",):
        if hook.endswith(cut):
            hook = hook[: -len(cut)]
    pref = f"- [{stem}]({stem}.md) — "
    if not hook.startswith(pref):
        return False
    hook = hook[len(pref):].rstrip()
    # ⚠ The ellipsis must be read as the TRUNCATION MARKER before it is removed: stripping it
    # first makes the shape test above unreachable and the keep never fires on a real
    # truncation — measured, that turned every tightened cue back into a re-derivation.
    truncated = hook.endswith("…")
    if truncated:
        hook = hook[:-1].rstrip()
    if not hook:
        return False
    desc_n, hook_n = _norm_desc(desc), hook.casefold()
    # ⚠ `_fit_hook` emits EXACTLY two shapes: the whole description, or a WORD-BOUNDARY prefix
    # ending in `…`. A one-way `startswith` accepts strictly more than the constructor can
    # produce — a mid-word cut (`config` out of `configuration drift`), or a truncation carrying
    # no ellipsis — and both are cues `_pointer` provably cannot write, so accepting them
    # CEMENTS a stale cue whose old hook happens to prefix the current description. That is the
    # lock this function exists to prevent, reached through its own permissiveness.
    # ONE rule, in ONE coordinate system. `_fit_hook` emits either the whole description or a cut
    # at a WHITESPACE boundary, so a cue it could have written is a casefolded prefix that either
    # IS the whole description or is followed by a space.
    #   ⚠ Requiring EXACT equality on the untruncated arm was a regression: a human tightening
    #   carries no ellipsis at all (the marker is the constructor's, not the editor's), so the
    #   shape a person actually produces was being re-derived — the very +est-tok inflation this
    #   rule exists to stop. The marker is not the signal; PRODUCIBILITY is.
    #   ⚠ The boundary index must be read from the CASEFOLDED string. Indexing the original-case
    #   `desc_n` with the original-case `len(hook)` mixes two coordinate systems, and any
    #   description whose casefold changes length (`ß` → `ss`, `İ` → two codepoints) reads the
    #   wrong character and refuses a cue that is perfectly producible.
    desc_cf = desc_n.casefold()
    if not desc_cf.startswith(hook_n):
        return False
    _n = len(hook_n)
    return len(desc_cf) == _n or desc_cf[_n:_n + 1] == " "


def _pointer_or_stored(idx_text: str, prev_text: str, stem: str, desc: str) -> str:
    """v0.4.42 (D3): re-derive the cue only when it would actually change meaning.

    `_pointer` derives the line from `description:` alone, so the line is a FUNCTION of that
    field — and a write that leaves the field untouched should leave a hand-tightened line
    untouched. It did not, and the MEASURED harm was silent: a line a human had tightened below
    what `_fit_hook` produces was re-inflated by ANY edit to the body — **+62 est tok across
    five facts** in one pass, then **+31 across two more**, all of it landing on the tier paid
    every session, with nothing comparing the old cue to the new one.

    ⚠ TWO conditions, and BOTH are load-bearing. The first (the description did not move) is the
    one the harm suggested; the second (`_cue_is_current`) is what stops the first from becoming
    a LOCK: a cue goes stale precisely by its description changing while the write path refuses
    the fact, at which point the previous and current descriptions are the SAME string and a
    keep keyed on that alone would preserve the stale line forever — turning the repair for one
    silent defect into the cause of another. A keep that fires only on a truncation-consistent
    line heals those cues on their next write while still preserving a tightened one.
    """
    from memory_status import _frontmatter
    prev_desc = str(_frontmatter(prev_text).get("description") or "")
    if _norm_desc(prev_desc) == _norm_desc(desc):
        stored = _stored_pointer(idx_text, stem)
        if stored is not None and _cue_is_current(stored, stem, desc):
            return stored
    return _pointer(stem, desc, "project-local")


def _norm_desc(desc: str) -> str:
    """The ONE description normalisation for the local pointer constructor.

    `_pointer` derives a cue from `description:`; `_cue_is_current` asks whether a stored cue is
    one `_pointer` could have produced from a given description. Those two answers are only
    consistent while both sides normalise IDENTICALLY, so the normalisation lives here and both
    call it. ⚠ A first cut inlined a byte-identical copy at the second site, and the failure mode
    is silent in BOTH directions: a divergence that makes `_cue_is_current` answer wrongly
    either CEMENTS a stale cue (the lock its docstring warns about) or re-inflates a
    hand-tightened line (+62 est tok measured). No test could catch it, because both arms build
    their fixtures from the same literals. Same rule as `store_local_index`: remove the second
    site rather than keep two sites in step by discipline.
    """
    return " ".join(re.sub(r"[\x00-\x1f\x7f-\x9f\[\]]", " ",
                           (desc or "").strip().strip('"')).split())


def _pointer(stem: str, description: str, scope: str = "") -> str:
    """Always-loaded index line for a project-authored local fact.

    Not `_pointer_line`: that constructor is the global injection sanitizer
    (strips `[]()` and 88-char truncates, mid-token). Locals keep `()` so a
    recall cue like `(OPEN: 1.0 HOLD)` survives, strip `[]` (spoof `](url)`),
    word-boundary truncate so the WHOLE line is ≤ HOOK_TOKEN_WARN, and attach
    `[project-local]` when the fact is in-contract.
    """
    from memory_status import LOCAL_HOOK_TOKEN_WARN
    desc = _norm_desc(description)
    tag = "project-local" if (scope or "").strip().strip('"') in ("", "project-local") else ""
    suffix = f" [{tag}]" if tag else ""
    prefix = f"- [{stem}]({stem}.md) — "
    hook = _fit_hook(prefix, desc, suffix, LOCAL_HOOK_TOKEN_WARN)
    return prefix + hook + suffix


def _warn_fat_hook(ptr: str, stem: str, *, source_path: str = "") -> None:
    from sync_global import _fat_hook_warning
    lint = _fat_hook_warning(ptr, stem, source_kind="local",
                             source_path=source_path or (stem + ".md"))
    if lint:
        print(f"  {lint}", file=sys.stderr)


def _pointer_from_clean_description(stem: str, text: str, *,
                                    idx_text: str = "", prev_text: str = "") -> "str | None":
    """D1c: the index cue for a fact whose only refusal is the FIREWALL, or None.

    The cue is a function of `description:` ALONE (`_pointer`), but every pointer-producing
    path runs `prepare_local_fact`, which validates the WHOLE body — so a body refusal used
    to block an unrelated concern. Measured harm: one fact's body read
    six releases ahead of its `MEMORY.md` pointer, frozen because no write could regenerate
    the cue and nothing compared body to cue. (The fact is private, so it is described rather
    than named: a slug from the maintainer's store is not a citation this tree can resolve.)

    ⚠ **"ONLY refusal" is the load-bearing word, and the first cut of this function did not
    have it.** It gated on `_looks_secret(text)` — a fact about the DOCUMENT — while
    `prepare_local_fact` is first-refusal-wins and runs the firewall check FIRST, so a fact
    that was ALSO badly named, badly scoped, or carrying a duplicate key reported only the
    firewall. MEASURED against the shipped cut: `name: totally-different`, `scope:
    domain-global`, `status: retired`, `sensitivity: topsecret`, a duplicated `description:`
    key and `content_modified: yesterday` EACH produced a pointer when paired with a
    firewall-tripping body — every one of them filed as `included`, every one of them
    silently released from the plan's fail-closed handling. The docstring claimed "this is
    not a general bypass" and the claim was false.

    So the test is two-call: ask once (refused, and we do not care why), then ask again with
    the firewall off. The route fires only when the second call is CLEAN — i.e. the firewall
    was the only thing standing in the way. ⚠ It still never admits a BODY: the caller emits
    a cue derived from `description:`, and a secret in the description returns None here.

    ⚠ `prepared["error"]` is deliberately not consulted. The refusal's message is prose that
    may be reworded, and a guard's label is not its predicate; the operative question is
    answered by the second call, not by reading the first one's error string.
    """
    from memory_status import _frontmatter, _looks_secret
    from identifiers import IdentifierRefused, validate_fact_stem
    # ⚠ The stem is validated HERE, not inherited from the caller. `_pointer` sanitises only the
    # description, and this route builds an index line by concatenation — so without this check
    # the route's safety would be an unwritten precondition of its one call site, which is
    # `weakest-enforcement-site-wins` exactly. A second caller would inherit an unguarded
    # constructor. (Today's caller does pre-validate at `_rebuild_plan`, so this is a BELT: it
    # cannot change behaviour, and it makes the guard live at the site that needs it.)
    try:
        stem = validate_fact_stem(stem)
    except IdentifierRefused:
        return None
    if prepare_local_fact(stem, text).get("ok"):
        return None                      # nothing was refused — this is not the route
    lenient = prepare_local_fact(stem, text, check_secrets=False)
    if not lenient.get("ok"):
        return None                      # ANOTHER refusal is real; `invalid` keeps it
    desc = str(_frontmatter(text).get("description") or "").strip().strip('"')
    if not desc or _looks_secret(desc):
        return None                      # the cue's own input is dirty; nothing to derive
    # ⚠ When the caller can supply the index, the KEEP applies here too — a hand-tightened cue
    # is no less worth preserving because its body is refused, and this route is the only path
    # a firewall-refused fact's cue can take. Without it, the rebuild's one write both healed a
    # frozen cue and re-inflated every tightened one.
    if idx_text:
        return _pointer_or_stored(idx_text, prev_text or text, stem, desc)
    return _pointer(stem, desc, "project-local")



def _frontmatter_entries(text: str) -> list:
    """Opening-frontmatter (key, value) pairs in order. Last-wins is the caller's problem."""
    if text.startswith("\ufeff"):
        text = text[1:]
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    m = re.search(r"^---\n(.*?)\n---", text, re.S)
    if not m:
        return []
    out: list = []
    for line in m.group(1).splitlines():
        if ":" in line and not line.startswith((" ", "\t")):
            k, _, v = line.partition(":")
            out.append((k.strip(), v.strip()))
    return out


def _duplicate_reserved(text: str) -> Optional[str]:
    seen: set = set()
    for k, _v in _frontmatter_entries(text):
        if k in LOCAL_RESERVED_SET:
            if k in seen:
                return f"duplicate reserved key {k!r}"
            seen.add(k)
    return None


def _split_body(text: str) -> str:
    if text.startswith("\ufeff"):
        text = text[1:]
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    m = re.search(r"^---\n.*?\n---\n?", text, re.S)
    if not m:
        return text
    return text[m.end():]


def _render_local(fm: dict, body: str) -> str:
    lines = ["---"]
    for k in LOCAL_RESERVED:
        if k in fm and fm[k] is not None:
            lines.append(f"{k}: {fm[k]}")
    for k, v in fm.items():
        if k in LOCAL_RESERVED_SET:
            continue
        if v is None:
            continue
        lines.append(f"{k}: {v}")
    lines.append("---")
    body = body if body.endswith("\n") else body + "\n"
    if body and not body.startswith("\n") and not body.startswith("---"):
        pass
    return "\n".join(lines) + "\n" + body.lstrip("\n")


def prepare_local_fact(stem: str, text: str, *, now: Optional[str] = None,
                       inject: bool = True, check_secrets: bool = True) -> dict:
    """Normalize + validate LocalFactV1. Returns {ok, text, fm, error}.

    ⚠ `check_secrets=False` is a DIAGNOSTIC and nothing else — it answers *"is this fact valid
    apart from the firewall?"* and must never be used to ADMIT a fact (no write path passes
    False). It exists because this function is first-refusal-wins and the firewall check runs
    FIRST (below), so every other refusal is MASKED by a firewall refusal: a fact that is also
    badly named, badly scoped, or carrying a duplicate key reports only the firewall. A caller
    that needs to know whether the firewall was the ONLY refusal has to ask twice.
    """
    from fact_schema import _real_rfc3339
    from identifiers import IdentifierRefused, validate_fact_stem
    from memory_status import _frontmatter
    try:
        stem = validate_fact_stem(stem)
    except IdentifierRefused as e:
        return {"ok": False, "error": str(e), "text": text, "fm": {}}
    if check_secrets and _looks_secret_fn()(text):
        # v0.4.35 (RC-1d): name the ARM, and name the ROUTE. Every refusal below shares one
        # `{ok: False, error}` channel, so a caller — `local_archive` hands this string
        # straight to the operator, and `_rebuild_plan` files it as that fact's `error` —
        # could not tell "this is not a fact" from
        # "this is a fact the firewall will not re-admit". The two need different responses:
        # the first is a fact that was never valid, the second is valid content being
        # RELOCATED, and for it the flag is not the remedy — the arm reads the BODY, and
        # `_looks_secret_fn()` runs at this line, before and independently of `inject` below,
        # so `inject=True` does not bypass it (the recorded cause "inherits the firewall via
        # inject=True" names the wrong operand: it is the body, not the flag).
        return {"ok": False,
                "error": "secret-shaped content refused (arm: firewall — the BODY matches a "
                         "credential-shaped pattern; this content is already admitted and is "
                         "being relocated, so the route is to reword the body, not the flag)",
                "text": text, "fm": {}}
    dup = _duplicate_reserved(text)
    if dup:
        return {"ok": False, "error": dup, "text": text, "fm": {}}
    fm = dict(_frontmatter(text))
    desc = str(fm.get("description") or "").strip().strip('"')
    if not desc:
        return {"ok": False, "error": "description is required", "text": text, "fm": fm}
    name = str(fm.get("name") or "").strip()
    if name and name != stem:
        return {"ok": False, "error": f"name {name!r} does not match stem {stem!r}",
                "text": text, "fm": fm}
    scope = str(fm.get("scope") or "").strip().strip('"')
    if scope and scope != "project-local":
        return {"ok": False, "error": f"scope must be project-local, got {scope!r}",
                "text": text, "fm": fm}
    status = str(fm.get("status") or "").strip()
    if status and status not in LOCAL_STATUSES:
        return {"ok": False, "error": f"status must be {'|'.join(LOCAL_STATUSES)}",
                "text": text, "fm": fm}
    sens = str(fm.get("sensitivity") or "").strip().lower()
    if sens and sens not in LOCAL_SENSITIVITY:
        return {"ok": False, "error": f"sensitivity must be {'|'.join(LOCAL_SENSITIVITY)}",
                "text": text, "fm": fm}
    iso = now or _utc_now()
    if inject:
        fm["local_schema_version"] = str(LOCAL_SCHEMA_VERSION)
        fm["name"] = stem
        fm["description"] = desc
        fm["scope"] = "project-local"
        fm["status"] = status or "active"
        fm["sensitivity"] = sens or "internal"
        cm = str(fm.get("content_modified") or "").strip()
        lo = str(fm.get("last_observed_at") or "").strip()
        if cm and not _real_rfc3339(cm):
            return {"ok": False, "error": f"invalid content_modified {cm!r}",
                    "text": text, "fm": fm}
        if lo and not _real_rfc3339(lo):
            return {"ok": False, "error": f"invalid last_observed_at {lo!r}",
                    "text": text, "fm": fm}
        if not cm:
            fm["content_modified"] = iso
        if not lo:
            fm["last_observed_at"] = iso
        text = _render_local(fm, _split_body(text))
        fm = dict(_frontmatter(text))
    else:
        sv = str(fm.get("local_schema_version") or "").strip()
        if sv not in ("1", "v1"):
            return {"ok": False, "error": "missing local_schema_version: 1",
                    "text": text, "fm": fm}
        if str(fm.get("scope") or "").strip() != "project-local":
            return {"ok": False, "error": "scope must be project-local",
                    "text": text, "fm": fm}
        for ts_key in ("content_modified", "last_observed_at"):
            ts = str(fm.get(ts_key) or "").strip()
            if not _real_rfc3339(ts):
                return {"ok": False, "error": f"invalid {ts_key} {ts!r}",
                        "text": text, "fm": fm}
    return {"ok": True, "error": "", "text": text if text.endswith("\n") else text + "\n",
            "fm": fm}


def _validate_local(stem: str, text: str) -> Optional[str]:
    """Compatibility wrapper: error string or None. Injects LocalFactV1 defaults."""
    out = prepare_local_fact(stem, text, inject=True)
    return None if out.get("ok") else str(out.get("error") or "invalid local fact")


def _local_link_err(ctx: StoreContext, stem: str, text: str) -> Optional[str]:
    from canonical_ingress import link_targets
    native = ctx.native_memory_dir
    for target in link_targets(text):
        if target == stem:
            continue
        if not (native / f"{target}.md").is_file():
            err = f"dangling link [[{target}]]"
            if target.lower() in _PLACEHOLDER_LINK_TARGETS:
                err += " — format examples belong in backticks (`[[link]]`)"
            return err
    return None


def _expected_from_snap(snap) -> dict:
    return {str(snap.path): snap.sha256}


def local_upsert(ctx: StoreContext, stem: str, text: str, *,
                 create_only: bool = False) -> dict:
    """Create or replace a native fact file and its MEMORY.md pointer."""
    from control_plane import ABSENT, read_snapshot, transact
    from identifiers import IdentifierRefused, validate_fact_stem
    from index_admission import apply_pointer, project_index
    try:
        stem = validate_fact_stem(stem)
    except IdentifierRefused as e:
        return {"ok": False, "error": str(e)}
    assert_writable(ctx)
    prepared = prepare_local_fact(stem, text, inject=True)
    if not prepared.get("ok"):
        return {"ok": False, "error": prepared.get("error") or "invalid local fact"}
    text = prepared["text"]
    lerr = _local_link_err(ctx, stem, text)
    if lerr:
        return {"ok": False, "error": lerr}
    dest = ctx.native_memory_dir / f"{stem}.md"
    idxp = ctx.native_memory_dir / "MEMORY.md"
    dest_snap = read_snapshot(dest)
    idx_snap = read_snapshot(idxp)
    if dest_snap.exists:
        from sync_global import _is_mirror
        cur = (dest_snap.data or b"").decode("utf-8", errors="replace")
        if _is_mirror(cur):
            return {"ok": False, "error":
                    "managed mirror; use cm resolve / demote, not cm local"}
        if create_only:
            return {"ok": False, "error": "local fact already exists"}
    elif create_only:
        pass
    fm = prepared["fm"]
    # v0.4.42 (D3): the cue is a function of `description:` alone, so re-derive it only when
    # that field moved — otherwise a body-only edit re-inflates a hand-tightened line.
    _desc = str(fm.get("description") or stem)
    _prev_text = cur if dest_snap.exists else ""
    _prev_idx = (idx_snap.data or b"").decode("utf-8", errors="replace") if idx_snap.exists else ""
    ptr = _pointer_or_stored(_prev_idx, _prev_text, stem, _desc)
    # v0.4.44 (item 3): an archived placement is not re-added as a side effect of a body edit.
    _archived_placement = _placement_decline(ctx, stem, _prev_idx)
    _warn_fat_hook(ptr, stem, source_path=str(dest))
    expected = {}
    expected.update(_expected_from_snap(dest_snap))
    expected.update(_expected_from_snap(idx_snap))

    def mutate(conn, temps):
        del conn
        modes = {}
        extra = {}
        temps[str(dest)] = text
        if not dest_snap.exists:
            modes[str(dest)] = "create"
            extra[str(dest)] = ABSENT
        # v0.4.44 (item 3): MEMORY.md is left UNTOUCHED for an archived placement — no pointer,
        # no admission check (the index is not changing). The BODY still updates, so the operator
        # can edit an archived fact; only the eviction is protected.
        if not _archived_placement:
            if idx_snap.exists:
                idx = (idx_snap.data or b"").decode("utf-8", errors="replace")
            else:
                idx = "# Memory Index\n\n"
            future = apply_pointer(idx, ptr, stem)
            adm = project_index(future)
            if not adm["admitted"]:
                raise WriteRefused("index admission refused: " + adm["reason"])
            temps[str(idxp)] = future if future.endswith("\n") else future + "\n"
            if not idx_snap.exists:
                modes[str(idxp)] = "create"
                extra[str(idxp)] = ABSENT
        return {"stem": stem, "dest_modes": modes, "expected_revisions": extra,
                "archived_placement": _archived_placement}

    try:
        out = transact(ctx, "local-upsert", {"stem": stem}, mutate,
                       expected_revisions=expected or None)
        return {"ok": True, **(out.get("result") or {}), "op_id": out.get("op_id")}
    except WriteRefused as e:
        return {"ok": False, "error": str(e)}


def _archive_doc_paths(native: Path) -> list:
    """The store-root docs that CLASSIFY as archive indexes — the ONE selection rule.

    Skips `MEMORY.md` and anything under `/quarantine/`, exactly as the rebuild's scan does; a
    selection rule with two spellings is what makes two callers disagree about what "placed"
    means.
    """
    from memory_status import _is_archive_index_text
    try:
        files = sorted(native.glob("*.md"))
    except OSError:
        return []
    out: list = []
    for f in files:
        if f.name == "MEMORY.md" or "/quarantine/" in str(f):
            continue
        try:
            if not f.is_file():
                continue
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if _is_archive_index_text(text):
            out.append(f)
    return out


def _placements_from(paths) -> dict:
    """stem -> the archive doc NAMES placing it, over `paths` — the ONE extraction.

    Each caller supplies the doc paths (and, in the rebuild's case, reads them from its PINNED
    snapshots); this owns the `archive_index(...)["targets"]` walk so the rule has one spelling.
    Evidence-carrying by construction: the value names the doc that claimed the placement, which
    is what makes an assertion checkable rather than vouched for.
    """
    from index_admission import archive_index
    out: dict = {}
    for ap in paths:
        try:
            text = (ap.read_text(encoding="utf-8", errors="replace")
                    if isinstance(ap, Path) else str(ap[1]))
        except OSError:
            continue
        for stem in (archive_index(text).get("targets") or set()):
            out.setdefault(stem, []).append(Path(str(ap)).name)
    return out


def _placement_decline(ctx: StoreContext, stem: str, idx_text: str) -> list:
    """v0.4.44 (item 3): the archive docs placing `stem`, when `MEMORY.md` does not index it.

    Returns the doc NAMES (evidence, not a bare verdict) or `[]` — a NON-EMPTY return means the
    caller must NOT re-add the pointer.

    ⚠ The harm this exists for: `local_upsert` read only the fact file and `MEMORY.md`, so after
    `cm local archive STEM` moved STEM's pointer into an archive doc, any later body-only upsert
    found no `](stem.md)` line, took `apply_pointer`'s APPEND branch, and silently re-added the
    pointer — undoing the eviction as a side effect of editing a body. `_rebuild_plan` has had a
    rule for exactly this harm (and a pin) since v0.4.32; the upsert path never got it.

    ⚠ The reader is `index_admission.archive_index` — the SAME one `_rebuild_plan` uses, reached
    through the same `_is_archive_index_text` classifier. A second archive reader would be the
    divergence class this repo keeps closing, and the two sites must agree about what "placed"
    means or the docket and the writer disagree again.

    ⚠ Both negatives are load-bearing: a stem that IS currently indexed is an ordinary update
    (the caller keeps its pointer), and a stem no archive names was never archived — the check
    must not fire on either.
    """
    from memory_status import _LINK_RE
    # ⚠ "Currently indexed" must mean exactly what `_rebuild_plan` means by it: the rebuild's
    # `existing_ptrs` is `set(_LINK_RE.findall(idx_text))` — ANY `](stem.md)` occurrence — not
    # the pointer-SHAPE test `_stored_pointer` performs. Those are different sets, and using the
    # stricter one here would let this decline fire where the rebuild would not, which is the
    # divergence class this check was written to avoid. Same reader, same operand, same test.
    if stem in set(_LINK_RE.findall(idx_text)):
        return []                                   # currently indexed → this is an update
    # ⚠ The SCAN is shared with `_rebuild_plan`, not re-implemented. A first cut re-globbed the
    # store, re-classified and re-extracted here — and the two copies DISAGREED: the rebuild skips
    # `/quarantine/` and reads its pinned snapshots, this one did neither, so the upsert's notion
    # of "placed" could differ from the docket's on exactly the stores the rebuild's guards were
    # written for. That is the divergence class the check was added to close, reintroduced by the
    # check. One selection, one extraction, two callers.
    return _placements_from(_archive_doc_paths(ctx.native_memory_dir)).get(stem, [])


def local_forget(ctx: StoreContext, stem: str) -> dict:
    from control_plane import read_snapshot, transact
    from identifiers import IdentifierRefused, validate_fact_stem
    try:
        stem = validate_fact_stem(stem)
    except IdentifierRefused as e:
        return {"ok": False, "error": str(e)}
    assert_writable(ctx)
    dest = ctx.native_memory_dir / f"{stem}.md"
    idxp = ctx.native_memory_dir / "MEMORY.md"
    dest_snap = read_snapshot(dest)
    idx_snap = read_snapshot(idxp)
    if not dest_snap.exists:
        return {"ok": False, "error": "no such local fact"}
    from sync_global import _is_mirror
    if _is_mirror((dest_snap.data or b"").decode("utf-8", errors="replace")):
        return {"ok": False, "error":
                "managed mirror; use cm resolve / demote, not cm local"}
    expected = {}
    expected.update(_expected_from_snap(dest_snap))
    expected.update(_expected_from_snap(idx_snap))

    def mutate(conn, temps):
        del conn
        if idx_snap.exists:
            idx = (idx_snap.data or b"").decode("utf-8", errors="replace")
        else:
            idx = "# Memory Index\n"
        idx = "\n".join(ln for ln in idx.splitlines() if f"]({stem}.md)" not in ln)
        temps[str(idxp)] = idx.rstrip() + "\n"
        extra = {}
        modes = {}
        if not idx_snap.exists:
            from control_plane import ABSENT as _A
            modes[str(idxp)] = "create"
            extra[str(idxp)] = _A
        return {"stem": stem, "deletes": [{"path": str(dest),
                                           "preimage": dest_snap.sha256}],
                "dest_modes": modes, "expected_revisions": extra}

    try:
        out = transact(ctx, "local-forget", {"stem": stem}, mutate,
                       expected_revisions=expected or None)
        return {"ok": True, **(out.get("result") or {}), "op_id": out.get("op_id")}
    except WriteRefused as e:
        return {"ok": False, "error": str(e)}


def local_archive(ctx: StoreContext, stem: str) -> dict:
    """Move the always-loaded pointer MEMORY.md → SHIPPED.md; body stays."""
    from control_plane import ABSENT, read_snapshot, transact
    from identifiers import IdentifierRefused, validate_fact_stem
    from index_admission import apply_pointer, archive_index, project_index
    try:
        stem = validate_fact_stem(stem)
    except IdentifierRefused as e:
        return {"ok": False, "error": str(e)}
    assert_writable(ctx)
    dest = ctx.native_memory_dir / f"{stem}.md"
    idxp = ctx.native_memory_dir / "MEMORY.md"
    arch = ctx.native_memory_dir / "SHIPPED.md"
    dest_snap = read_snapshot(dest)
    if not dest_snap.exists:
        return {"ok": False, "error": "no such local fact"}
    from sync_global import _is_mirror
    body = (dest_snap.data or b"").decode("utf-8", errors="replace")
    if _is_mirror(body):
        return {"ok": False, "error":
                "managed mirror; use cm resolve / demote, not cm local"}
    prepared = prepare_local_fact(stem, body, inject=True)
    if not prepared.get("ok"):
        return {"ok": False, "error": prepared.get("error") or "invalid local fact"}
    fm = prepared["fm"]
    ptr = _pointer(stem, str(fm.get("description") or stem), "project-local")
    _warn_fat_hook(ptr, stem, source_path=str(dest))
    idx_snap = read_snapshot(idxp)
    arch_snap = read_snapshot(arch)
    expected = {}
    expected.update(_expected_from_snap(dest_snap))
    expected.update(_expected_from_snap(idx_snap))
    expected.update(_expected_from_snap(arch_snap))

    def mutate(conn, temps):
        del conn
        if idx_snap.exists:
            idx = (idx_snap.data or b"").decode("utf-8", errors="replace")
        else:
            idx = "# Memory Index\n"
        idx = "\n".join(ln for ln in idx.splitlines() if f"]({stem}.md)" not in ln)
        temps[str(idxp)] = idx.rstrip() + "\n"
        idx_adm = project_index(temps[str(idxp)])
        if not idx_adm["admitted"]:
            raise WriteRefused("index admission refused: " + idx_adm["reason"])
        if arch_snap.exists:
            at = (arch_snap.data or b"").decode("utf-8", errors="replace")
        else:
            at = "# Shipped\n\n"
        future = apply_pointer(at, ptr, stem)
        adm = archive_index(future)
        if not adm["admitted"]:
            raise WriteRefused("archive index admission refused: " + adm["reason"])
        temps[str(arch)] = future if future.endswith("\n") else future + "\n"
        modes = {}
        extra = {}
        if not arch_snap.exists:
            modes[str(arch)] = "create"
            extra[str(arch)] = ABSENT
        if not idx_snap.exists:
            modes[str(idxp)] = "create"
            extra[str(idxp)] = ABSENT
        return {"stem": stem, "dest_modes": modes, "expected_revisions": extra,
                "source_sha256": dest_snap.sha256}

    try:
        out = transact(ctx, "local-archive", {"stem": stem}, mutate,
                       expected_revisions=expected or None)
        return {"ok": True, **(out.get("result") or {}), "op_id": out.get("op_id")}
    except WriteRefused as e:
        return {"ok": False, "error": str(e)}


def _rebuild_plan(ctx: StoreContext) -> dict:
    """Scan native facts. Never writes. Pins every source hash.

    v0.4.32 (spec docs/periphery-parity.spec.md §2): a fact file does not record its own
    PLACEMENT — placement is recorded only by which pointer doc holds the pointer — so a
    rebuild that globs fact files alone re-adds every pointer `local_archive` moved to an
    archive doc, silently undoing the eviction.

    §2.3 — the SECOND half of that root cause. Which entries an archive OWNS is not restated
    here either: it is `index_admission.archive_index`, the extraction `local_archive`'s own
    write path gates its admission on. That matters because the two readings differ exactly
    where it hurts — the shared text rule classifies any frontmatter-less store-root `*.md`
    carrying ONE link as an archive (v0.4.31), so a prose doc that merely *mentions* a fact
    was read as placing it, and the mention suppressed the fact's pointer from the rebuilt
    index while the plan labelled it an intentional eviction. Reading the archive's pointer
    LINES is what makes an archive's own entries the unit of the rule.

    Earlier revisions hand-rolled the placement rule, the `](stem.md)` anchor, AND this
    extraction; all three second copies are gone. The anchor one was inert (no live index
    line carries two pointers), but a second copy of a canonical rule is a site the next
    reader has to re-adjudicate.
    """
    from control_plane import read_snapshot
    from identifiers import IdentifierRefused, validate_fact_stem
    from index_admission import archive_index
    from memory_status import _LINK_RE, _frontmatter, _is_archive_index_text
    from sync_global import _is_mirror, _pointer_line
    native = ctx.native_memory_dir
    idxp = native / "MEMORY.md"
    idx_snap = read_snapshot(idxp)
    included: list = []
    invalid: list = []
    # D1c: a fact whose BODY the firewall refuses but whose DESCRIPTION is clean. Its cue is
    # still derived (and so stays FRESH), and reported rather than silently routed — the
    # refusal is real and the operator must see it. It does NOT fail the plan closed: nothing
    # in the index is wrong, and failing closed here is what froze the roadmap's cue for six
    # releases. Distinct from `invalid`, which means "not evaluated at all".
    body_refused: list = []
    unreadable: list = []
    # A `*.md` the directory listing carries but the read reports ABSENT. A broken symlink is
    # the reachable form: `glob("*.md")` lists the name, `read_snapshot` follows the link,
    # finds nothing, and returns an absent snapshot — deterministic, not a race. Kept apart
    # from `unreadable` because nothing REFUSED the read; there is no error to report, which
    # is precisely why the plan had no entry for it and why the fact loop could `continue`
    # past it without a trace.
    absent: list = []
    mirrors: list = []
    keep_archived: list = []
    snaps: dict = {str(idxp): idx_snap}
    existing_ptrs: set = set()
    idx_text = ""
    if idx_snap.exists:
        idx_text = (idx_snap.data or b"").decode("utf-8", errors="replace")
        existing_ptrs = set(_LINK_RE.findall(idx_text))
    # Archive docs (SHIPPED.md and any sibling) — classified from the SNAPSHOT's own bytes,
    # via the shared text rule, so the rule and the revision pin below read ONE source: the
    # apply transaction verifies exactly the bytes this pass classified.
    #
    # GUARDED, and not for symmetry with the fact loop below. `read_snapshot` RAISES on an
    # unreadable path (`except OSError` → `WriteRefused`), so without a guard an unreadable
    # store-root doc — or a directory named `*.md` — aborts the whole command with a raw
    # message instead of the structured `ok: False` + `unreadable` report the fact loop builds.
    # The raise happens here, before that loop runs.
    #
    # The guard REPORTS; it does not merely skip. Handing the path back to the fact loop is what
    # the first revision did, and it is false for exactly one name: that loop skips
    # `("MEMORY.md", "SHIPPED.md")` BY NAME, so an unreadable `SHIPPED.md` — the canonical
    # archive doc, the one name this whole rule is about — is seen by NO loop. `archived` then
    # comes out empty and the plan re-adds every pointer that doc owns while reporting
    # `ok: True` and an empty `unreadable`: the defect this function exists to fix, silent, and
    # invisible in the one report an operator reads. The harm needs a doc that is BOTH excluded
    # from the fact loop AND consulted for placement, and `SHIPPED.md` is the only one: a
    # `/quarantine/` path is excluded from both loops deliberately, and a quarantined doc is not a
    # placement record, so nothing is re-added on its account. That is why the consequence is a
    # wrong write rather than a missing warning. Recording it
    # here fails the plan closed through the fact loop's own machinery (`blocked`), leaving
    # `--skip-invalid` as the operator's explicit escape — and `reported_unreadable` keeps the
    # entry single-homed, since the fact loop would otherwise report the same path again.
    archive_paths: set = set()
    reported_unreadable: set = set()
    # Store-root `*.md` entries this pass listed and could not READ. Recorded rather than
    # skipped; the block after the fact loop decides which of them no loop ever reports.
    absent_docs: list = []
    if native.is_dir():
        for f in sorted(native.glob("*.md")):
            if f.name == "MEMORY.md" or "/quarantine/" in str(f):
                continue
            try:
                snap = read_snapshot(f)
            except WriteRefused as e:
                unreadable.append({"stem": f.stem, "error": str(e)})
                reported_unreadable.add(str(f))
                continue
            if not snap.exists:
                absent_docs.append(str(f))
                continue
            if _is_archive_index_text((snap.data or b"").decode("utf-8", errors="replace")):
                archive_paths.add(str(f))
                snaps[str(f)] = snap
    # Conservative direction (§2.3): the stems an archive's own POINTER LINES name AND the
    # index does not. The rebuild may decline to RE-ADD an archived pointer; it may never
    # REMOVE a live one, so a stem sitting in both docs stays.
    #
    # Both operands come from the pinned SNAPSHOTS — `readd_sources` from the archive bytes
    # classified above, the subtracted set from `existing_ptrs`. Sourcing that second operand
    # from DISK instead (`index_fact_names(idxp)`, which asks the same question) costs a second
    # read of MEMORY.md and opens a window where a concurrent write makes the plan report one
    # stem as both a pointer to remove and a re-add to decline. Every input this verdict rests
    # on is a byte string whose sha256 the apply transaction verifies (`expected`, below).
    #
    # `readd_sources` carries the EVIDENCE alongside the verdict. A bare stem list asserts an
    # intentional `cm local archive` the operator cannot check, and a stray store-root doc is
    # exactly what makes that assertion false (§2.3's residual: a doc whose link is formatted
    # as a pointer line is structurally indistinguishable from a real archive, so the honest
    # move is to name the doc that claimed the placement rather than vouch for it).
    #
    # `targets` only — `admitted` is deliberately UNREAD here. The cap and the syntax check
    # govern an archive's WRITE path (local_archive gates on `admitted` before it appends); an
    # archive already on disk over its cap still records real placements, and honouring the
    # refusal would re-add exactly the pointers this rule exists to leave out. The asymmetry is
    # the safe direction for the same reason as `archived` itself: reading a refusal as "no
    # entries" can only re-add, never delete.
    archived: set = set()
    readd_sources: dict = {}
    if archive_paths:
        for ap in sorted(archive_paths):
            ap_text = (snaps[ap].data or b"").decode("utf-8", errors="replace")
            for stem in archive_index(ap_text)["targets"]:
                readd_sources.setdefault(stem, []).append(Path(ap).name)
        archived = set(readd_sources) - existing_ptrs
    lines = ["# Memory Index", ""]
    if native.is_dir():
        for f in sorted(native.glob("*.md")):
            if f.name in ("MEMORY.md", "SHIPPED.md") or "/quarantine/" in str(f):
                continue
            if str(f) in archive_paths or str(f) in reported_unreadable:
                continue
            try:
                snap = read_snapshot(f)
            except WriteRefused as e:
                unreadable.append({"stem": f.stem, "error": str(e)})
                continue
            snaps[str(f)] = snap
            if not snap.exists:
                absent.append({"stem": f.stem,
                               "error": "no file at read time (broken symlink, or "
                                        "removed while the pass ran)"})
                continue
            try:
                text = (snap.data or b"").decode("utf-8")
            except UnicodeDecodeError as e:
                unreadable.append({"stem": f.stem, "error": str(e)})
                continue
            try:
                validate_fact_stem(f.stem)
            except IdentifierRefused as e:
                invalid.append({"stem": f.stem, "error": str(e),
                                "sha256": snap.sha256})
                continue
            if f.stem in archived:
                # Placed by an archive on purpose. Declining to re-add IS the fix; naming it
                # is the other half — the plan reported only the REMOVE direction, so an
                # operator could not see the rebuild about to undo an eviction (§4).
                # v0.4.35 (RC-3b): the KEY is `would_keep_archived_pointers`. It read
                # `would_readd_…` — the plan's intent for exactly the re-adds it declines, so a
                # reader scanning the `would_*` family saw the opposite of the plan (the list
                # this stem lands in is the one a re-add would APPEAR in had the plan not
                # refused). Its sibling `would_remove_existing_pointers` names its own verdict;
                # this now does the same. The value, the report shape and the pins are unchanged.
                keep_archived.append(f.stem)
                continue
            if _is_mirror(text):
                fm = _frontmatter(text)
                ptr = _pointer_line(f.stem, fm)
                _warn_fat_hook(ptr, f.stem, source_path=str(f))
                lines.append(ptr)
                mirrors.append({"stem": f.stem, "sha256": snap.sha256})
                continue
            prepared = prepare_local_fact(f.stem, text, inject=True)
            if not prepared.get("ok"):
                # D1c: try the cue BEFORE failing closed. A firewall refusal is a verdict on
                # the BODY; the cue is a function of `description:` alone, so the two
                # concerns can separate — and when they do, deriving the cue is what keeps it
                # from freezing. `invalid` still catches every other refusal.
                # ⚠ The keep applies on THIS branch too, not only the evaluable one. The D1c
                # route is reachable exactly for facts whose body the firewall refuses, and a
                # hand-tightened cue is no less worth preserving because its body is: without
                # this, `cm local rebuild-index --apply` re-inflated the tightened cue of every
                # refused fact (MEASURED +25 est tok each) — and since this route lives ONLY in
                # the rebuild, the one write that heals a frozen cue was also the one that
                # re-inflated the tightened ones, in the same pass. The keep's operands are
                # already in scope: `idx_text` is the pinned snapshot, `text` the fact's bytes.
                desc_ptr = _pointer_from_clean_description(f.stem, text,
                                                           idx_text=idx_text, prev_text=text)
                if desc_ptr is not None:
                    _warn_fat_hook(desc_ptr, f.stem, source_path=str(f))
                    lines.append(desc_ptr)
                    included.append({"stem": f.stem, "sha256": snap.sha256})
                    body_refused.append({"stem": f.stem,
                                         "error": prepared.get("error") or "invalid",
                                         "sha256": snap.sha256})
                    continue
                invalid.append({"stem": f.stem,
                                "error": prepared.get("error") or "invalid",
                                "sha256": snap.sha256})
                continue
            fm = prepared["fm"]
            # v0.4.42 (D3): the rebuild needs the SAME keep, not just the D1c route. The
            # design-of-record says so ("`_rebuild_plan` … re-derives every line from
            # descriptions and needs the same rule") and the carry comment beside it states the
            # principle ("a hand-edited index line has to survive a rebuild") — honoured here
            # only for the UNEVALUABLE class. Without this, the documented repair re-derives
            # every hand-tightened cue, so `cm local rebuild-index --apply` silently undoes D3
            # for every evaluable fact — and since the D1c route lives ONLY here, the write that
            # heals one frozen cue re-inflates all the tightened ones in the same pass. The
            # operands are already in scope: `text` is the fact's own bytes, `idx_text` is the
            # pinned snapshot of the index being rebuilt.
            ptr = _pointer_or_stored(idx_text, text, f.stem,
                                     str(fm.get("description") or f.stem))
            _warn_fat_hook(ptr, f.stem, source_path=str(f))
            lines.append(ptr)
            included.append({"stem": f.stem, "sha256": snap.sha256})
    # An absent store-root `*.md` is an entry the PLACEMENT rule cannot read: any doc here may
    # be an archive (§2.3's residual — a stray doc whose link is formatted as a pointer line is
    # structurally indistinguishable from one), so a doc that is absent may have owned
    # placements the plan cannot recover. That is NOT the absent-FACT case the loop above
    # reports. A fact has a safe automatic action (carry its pointer, which is what keeps it
    # out of `would_remove`); a placement record has none, because the stems it owned are
    # unknowable — `archived` comes out empty for that doc, so EVERY pointer it owned is
    # re-added and the apply admits it with `ok: True` and every report list empty. That is
    # P13's harm signature verbatim — "the plan re-adds every pointer that doc owns while
    # reporting `ok: True` and an empty `unreadable`" — reached through the branch P13's own
    # fixture steps around, and needing no operation at all to fire.
    #
    # Which entries those are is taken from `snaps` rather than by restating the loop above's
    # exclusion list: a path lands here only if NO loop READ it, which is what "no loop
    # reported this one" means in the loops' own data. Today that is `SHIPPED.md` and nothing
    # else — the one store-root name the fact loop excludes that this pass does not, and the
    # name the whole archive rule is about. It fails the plan closed through the same `blocked`
    # machinery this pass's unreadable arm already uses, leaving `--skip-invalid` as the
    # operator's explicit escape.
    for _p in absent_docs:
        if _p in snaps:
            continue
        unreadable.append({
            "stem": Path(_p).stem,
            "error": "no file at read time (broken symlink, or removed while the pass ran); "
                     "this doc is a PLACEMENT record — with it unread, the pointers it owns "
                     "cannot be told from stale ones, and rebuilding re-adds every one of them"})

    # One question the plan has to answer before it can call any pointer a REMOVAL: could
    # this fact be evaluated at all? `invalid` and `unreadable` are refusals the operator
    # can read; `absent` is the same condition with no error attached to carry it, which is
    # why it had no list and the loop could skip it without a trace.
    #
    # Derived from those three lists rather than appended at each of the five `continue`s
    # that fill them, so a refusal that REPORTS cannot drift out of this set. The loop's
    # other skips are accounted for and do not belong here: the two name exclusions
    # (MEMORY.md, SHIPPED.md) name stems no pointer can reference, the archive/dedup
    # handoffs are already represented in `unreadable` or by the archive rule, and the
    # archived decline at `f.stem in archived` evaluated the file and simply refuses to
    # re-add it — a verdict, not a failure.
    unevaluated = ([r["stem"] for r in unreadable] + [r["stem"] for r in invalid]
                   + [r["stem"] for r in absent])
    # §2.3's invariant, applied to the OTHER direction. The comments above argue it for
    # archives — the rebuild may decline to re-add, never remove — and the same argument
    # binds harder here: `planned` is the set REMOVAL is differenced against, so a stem the
    # plan could not evaluate must enter it. A stale pointer is recoverable; its removal is
    # not, because the fact it named was never read. Pre-fix this read `existing_ptrs -
    # planned` with `planned` built from `included | mirrors` alone, so an unevaluable fact
    # was reported as a removal the plan had DECIDED, and the apply wrote that verdict.
    planned = ({row["stem"] for row in included} | {row["stem"] for row in mirrors}
               | set(unevaluated))
    _remove_basis = existing_ptrs - planned
    # Carry those stems' EXISTING pointer lines through, VERBATIM from the pinned index
    # snapshot. Never re-derived: there is no evaluable fact file to derive one from, and a
    # hand-edited index line has to survive a rebuild — the same reason `existing_ptrs`
    # reads `idx_snap` above rather than going back to disk. Order is the index's own, so the
    # carried lines keep their relative order; they follow the re-derived ones because
    # placement among THOSE is not recorded anywhere to consult.
    #
    # A line is carried when it names ANY stem in `_carry` — the `findall` reading, which is how
    # `existing_ptrs` itself was built at its `findall` site. The FIRST-match reading this
    # replaces could not see a `_carry` stem sitting behind a different stem's pointer, so such a
    # line was not carried at all: the stem stayed in `planned` and therefore never appeared in
    # `would_remove`, while its `](stem.md)` vanished from the rebuilt index. That is RC-1c's own
    # harm re-entered through RC-1c's repair — an unevaluable fact de-indexed with the plan
    # reporting nothing removed — and it landed on multi-pointer lines, which are hand-edits,
    # which is the case this carry exists to serve.
    #
    # Carrying by the any-match reading needs the duplicate that reading used to cause solved the
    # other way. A carried line is VERBATIM, so a stem it names that the rebuild ALSO re-derived
    # would land in `future` twice — once re-derived, once under the carried line. The re-derived
    # line for such a stem is therefore dropped and the hand-edited line is the survivor, while
    # `included`/`mirrors` are left untouched so `planned` does not move: the stem IS still
    # placed, by the carried line. Machine-written lines cannot reach that dedup (`_pointer_line`
    # strips `[]()` from the hook); hand-edited hooks are exactly what this carry preserves.
    # Requiring the display text to equal the stem is still rejected — it would drop
    # `- [My Title](stem.md)`, which a `startswith` test misses.
    #
    # `would_remove` is computed AFTER the carry, because a carried line preserves every stem it
    # names, and the key reports what the apply will DROP. Subtracting `_named` is what keeps the
    # two in step: without it a carried line could hold a pointer the plan also announced as
    # removed, and the report would claim a removal the apply does not perform.
    #
    # But `_named` and `_carry` are NOT the same set, and the difference is the whole of this
    # repair. `_carry` is what the carry exists to PROTECT — the unevaluable stems. `_named`
    # additionally holds every OTHER stem sharing a carried line, and those may be ordinary
    # decided removals (`_remove_basis`) that merely happen to sit beside an unevaluable one.
    # Subtracting them from `_remove_basis` would then suppress a removal the plan justified AND
    # perform no removal — a decided verdict turned into an unreported retention, with nothing
    # anywhere naming the stem. MEASURED 2026-09-18 (a peer's fixture, reproduced here): one dead
    # pointer is DROPPED and reported `would_remove: ['ghost']` when it sits alone, and silently
    # RETAINED with `would_remove: []` when the same token shares a line with an unevaluable
    # stem — the verdict keyed to line LAYOUT, which is the class this release exists to close.
    #
    # The line is still carried VERBATIM (re-deriving it would destroy the hand-edit the carry
    # serves), so retention is what actually happens and `would_remove` must keep saying so. What
    # was missing is the carrier: the stems that survive against a justified removal get their
    # own key. Retention is the safe direction — a stale pointer is recoverable, its removal is
    # not, which is §2.3's own argument — but the SILENCE was not, and this is the second time
    # this release has had to repair a silence rather than a wrong value.
    _carry = {s for s in unevaluated if s in existing_ptrs}
    _carried: list = []
    _named: set = set()
    if _carry:
        for _ln in idx_text.splitlines():
            _ls = _LINK_RE.findall(_ln)
            if any(s in _carry for s in _ls):
                _carried.append(_ln)
                _named |= set(_ls)
    would_remove = sorted(_remove_basis - _named)
    would_keep_stale = sorted(_remove_basis & _named)
    lines = [ln for ln in lines
             if (m := _LINK_RE.search(ln)) is None or m.group(1) not in _named]
    lines.extend(_carried)
    future = "\n".join(lines) + "\n"
    return {
        "included": included,
        "invalid": invalid,
        # D1c (additive): facts whose BODY the firewall refused but whose cue was still
        # derived. Reported rather than swallowed — the refusal is real, and a plan that
        # routed it silently would be the same class of silence this pass exists to remove.
        "body_refused": body_refused,
        "unreadable": unreadable,
        "absent": absent,
        "mirrors": mirrors,
        "would_remove_existing_pointers": would_remove,
        # v0.4.35 (RC-1c): a stale pointer whose removal the plan justified, retained anyway
        # because it shares a VERBATIM carried line. Named `would_keep_*` to sit with its
        # sibling below: both are the verdict that KEPT a pointer, and neither is a removal.
        "would_keep_stale_pointers": would_keep_stale,
        # v0.4.35 (RC-3b): renamed from `would_readd_archived_pointers` /
        # `would_readd_archived_sources`. Both `would_*` keys are the plan's own verdicts, and
        # these two hold the verdict that REFUSED the re-add — see the note at their fill site.
        "would_keep_archived_pointers": sorted(keep_archived),
        "would_keep_archived_sources": {s: readd_sources[s] for s in sorted(keep_archived)},
        "future": future,
        "snaps": snaps,
        "idx_snap": idx_snap,
    }


def local_rebuild_index(ctx: StoreContext, *, apply: bool = False,
                        skip_invalid: bool = False, confirm: str = "") -> dict:
    """Rebuild MEMORY.md from native fact files (skip quarantine / SHIPPED).

    Default is plan-only. `--apply` requires `--confirm rebuild-local-index`.
    Any invalid/unreadable fact fails closed unless skip_invalid=True — and so does a
    store-root doc no loop could read, because a doc may be the archive whose pointer lines
    record which facts were evicted (`_rebuild_plan`).

    A fact the plan could not evaluate — invalid, unreadable, or absent at read — keeps its
    EXISTING pointer line and is named in `omitted` ("left in place, unverified"); only a
    stem whose removal the plan justified is dropped. `absent` is the one family that does
    not fail the plan closed: nothing refused the read, so there is no error for the
    operator to act on, and the carried pointer is already the safe direction.
    """
    from control_plane import ABSENT, transact
    from index_admission import project_index
    assert_writable(ctx)
    plan = _rebuild_plan(ctx)
    report = {k: plan[k] for k in (
        "included", "invalid", "unreadable", "absent", "mirrors",
        "would_remove_existing_pointers", "would_keep_stale_pointers",
        "would_keep_archived_pointers",
        # v0.4.42 D1c: `_rebuild_plan` discloses a firewall-refused body here, and this tuple
        # is the ONLY operator-facing route — the plan dict itself is not returned. Omitting the
        # key made the plan's own comment ("Reported rather than swallowed — a plan that routed
        # it silently would be the same class of silence this pass exists to remove") false at
        # the consumer: the stem appeared as a bare entry in `included` and nothing anywhere
        # said its body had been refused. The disclosure has to reach the surface that reports
        # it, or it is not a disclosure.
        "body_refused",
        "would_keep_archived_sources")}
    blocked = bool(plan["invalid"] or plan["unreadable"]) and not skip_invalid
    if not apply:
        return {"ok": not blocked, "plan": True, "error":
                ("invalid or unreadable facts; pass --skip-invalid to carry their pointers "
                 "through, unverified"
                 if blocked else ""),
                **report}
    if confirm != REBUILD_CONFIRM:
        return {"ok": False, "error":
                f"rebuild-index --apply requires --confirm {REBUILD_CONFIRM}",
                **report}
    if blocked:
        return {"ok": False, "error":
                "invalid or unreadable facts; index unchanged",
                **report}
    # Every unevaluated stem is left in place with its existing pointer, so `omitted` names
    # the stems this run did NOT decide — "left in place, unverified", not "removed". It is
    # no longer gated on `skip_invalid`: the absent family is carried through on the plain
    # `--apply` route too, and reporting that only under `--skip-invalid` would be the same
    # silence one flag over. The key keeps its name (the report shape is a wire contract);
    # the meaning it now carries is the one both routes actually produce.
    omitted = sorted({r["stem"] for r in
                      plan["invalid"] + plan["unreadable"] + plan["absent"]})
    native = ctx.native_memory_dir
    idxp = native / "MEMORY.md"
    future = plan["future"]
    adm = project_index(future)
    if not adm["admitted"]:
        return {"ok": False, "error": "rebuild admission refused: " + adm["reason"],
                **report}
    idx_snap = plan["idx_snap"]
    expected = {str(idxp): idx_snap.sha256}
    for p, snap in plan["snaps"].items():
        expected[p] = snap.sha256

    def mutate(conn, temps):
        del conn
        temps[str(idxp)] = future
        modes = {}
        extra = {}
        if not idx_snap.exists:
            modes[str(idxp)] = "create"
            extra[str(idxp)] = ABSENT
        return {"rebuilt": True, "dest_modes": modes, "expected_revisions": extra,
                "omitted": omitted}

    try:
        out = transact(ctx, "local-rebuild-index", {"stem": "*"}, mutate,
                       expected_revisions=expected or None)
        return {"ok": True, **(out.get("result") or {}), "op_id": out.get("op_id"),
                "omitted": omitted, **report}
    except WriteRefused as e:
        return {"ok": False, "error": str(e), **report}


def local_migrate_schema(ctx: StoreContext, *, apply: bool = False,
                         confirm: str = "") -> dict:
    """Inject LocalFactV1 fields into legacy local facts. Plan-first."""
    from control_plane import read_snapshot, transact
    assert_writable(ctx)
    native = ctx.native_memory_dir
    planned: list = []
    invalid: list = []
    expected: dict = {}
    bodies: dict = {}
    if native.is_dir():
        from sync_global import _is_mirror
        for f in sorted(native.glob("*.md")):
            if f.name in ("MEMORY.md", "SHIPPED.md"):
                continue
            snap = read_snapshot(f)
            if not snap.exists:
                continue
            text = (snap.data or b"").decode("utf-8", errors="replace")
            if _is_mirror(text):
                continue
            prepared = prepare_local_fact(f.stem, text, inject=True)
            if not prepared.get("ok"):
                invalid.append({"stem": f.stem, "error": prepared.get("error")})
                continue
            new = prepared["text"]
            if new.encode("utf-8") == (snap.data or b""):
                continue
            planned.append({"stem": f.stem, "sha256": snap.sha256})
            expected[str(f)] = snap.sha256
            bodies[str(f)] = new
    report = {"planned": planned, "invalid": invalid}
    if not apply:
        return {"ok": not invalid, "plan": True, **report,
                "error": ("invalid facts; migrate refused" if invalid else "")}
    if confirm != MIGRATE_CONFIRM:
        return {"ok": False, "error":
                f"migrate-schema --apply requires --confirm {MIGRATE_CONFIRM}",
                **report}
    if invalid:
        return {"ok": False, "error": "invalid facts; migrate refused", **report}
    if not bodies:
        return {"ok": True, "migrated": 0, **report}

    def mutate(conn, temps):
        del conn
        temps.update(bodies)
        return {"migrated": len(bodies)}

    try:
        out = transact(ctx, "local-migrate-schema", {"stem": "*"}, mutate,
                       expected_revisions=expected)
        return {"ok": True, **(out.get("result") or {}), "op_id": out.get("op_id"),
                **report}
    except WriteRefused as e:
        return {"ok": False, "error": str(e), **report}
