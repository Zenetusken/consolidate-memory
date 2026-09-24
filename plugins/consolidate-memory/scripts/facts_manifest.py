#!/usr/bin/env python3
"""Derived facts-manifest cache for the canonical domain facts dir (Phase-5 closeout).

Markdown is the authority. This module is a REBUILDABLE cache of
(stem, mtime_ns, size, ctime_ns, body_hash, sem, class, secret, fm) per canonical
file, so readers (beacon, pull, gc, network, dream) validate by scandir stats and
read a body only when it changed or is absent. Any anomaly fails OPEN to full
enumeration — the cache can slow you down but never serves wrong facts.

Writer: invalidation rides the transact choke point (control_plane.transact +
recover_pending unlink the manifest for any published/deleted path under
domains/<d>/facts/); the few non-transact purge sites unlink explicitly. Rebuild
is lazy, double-checked, under locks/global.lock, written with atomic_write_bytes
(tmp+replace, fsync file+parent, 0600).
"""
from __future__ import annotations

import functools
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any, Optional

SCHEMA_VERSION = 1
KILL_SWITCH = "CM_FACTS_MANIFEST"

# The most of a fact file this cache will read. Named rather than inline so the refusal below and
# the read it guards cannot drift apart — and so the number has somewhere to state WHY it exists.
_READ_CAP = 4 * 1024 * 1024


class _Oversize(RuntimeError):
    """A facts file larger than `_READ_CAP`, so no verdict can be cached for it.

    ⚠ NOT an error to report to an operator and NOT a row to write: it is the signal to FAIL OPEN,
    which this module's docstring names as the posture for every anomaly it cannot classify
    ("can slow you down but never serves wrong facts"). Truncating instead would serve a wrong
    fact — a `secret: False` for a credential the prefix did not reach — and the consumer that
    matters (the warm pull) trusts the cached verdict and skips its own re-scan.
    """


def manifest_path(plugin_data_dir: Path, domain: str) -> Path:
    return Path(plugin_data_dir) / f"facts-manifest-{domain}.json"


def domain_from_path(path: Path) -> str:
    """The domain owning a canonical path: …/domains/<d>/facts/… → <d>. "" if none."""
    parts = list(Path(path).parts)
    for i in range(len(parts) - 2):
        if parts[i] == "domains" and parts[i + 2] == "facts":
            return parts[i + 1]
    return ""


def invalidate_for_paths(plugin_data_dir: Path, paths) -> int:
    """Unlink the manifest for every domain named by `paths`. Returns count."""
    n = 0
    seen: set = set()
    for p in paths or []:
        d = domain_from_path(Path(str(p)))
        if not d or d in seen:
            continue
        seen.add(d)
        try:
            manifest_path(plugin_data_dir, d).unlink(missing_ok=True)
            n += 1
        except OSError:
            pass
    return n


def invalidate_all(plugin_data_dir: Path) -> int:
    """Unlink every facts-manifest-*.json (used by the domains-root rmtree)."""
    n = 0
    pdir = Path(plugin_data_dir)
    try:
        for p in pdir.glob("facts-manifest-*.json"):
            try:
                p.unlink(missing_ok=True)
                n += 1
            except OSError:
                pass
    except OSError:
        pass
    return n


@functools.lru_cache(maxsize=8)
def _secret_pred_keyed(secret_pat: str, secret_flags: str, blob_pat: str, blob_flags: str,
                       seg_floor: str, read_cap: str, fn_bodies: "tuple[str, ...]") -> str:
    """The identity for one exact predicate INPUT VECTOR — memoised, and keyed on the vector.

    ⚠ Keyed, not argument-less. A bare `lru_cache` on `secret_pred()` would be correct in
    production (the running predicate is fixed at import) and would make the identity undetectable
    by the smoke pin that changes `_BLOB` mid-process to prove the hash MOVES — i.e. it would buy
    0.4 ms and destroy the only instrument that shows the identity tracks its inputs. Keying on
    the values keeps both: the collision is per distinct predicate, and two calls in one process
    with the same predicate still cost one hash.
    """
    parts = [secret_pat, secret_flags, blob_pat, blob_flags, seg_floor, read_cap, *fn_bodies]
    return hashlib.sha256("\x00".join(parts).encode("utf-8")).hexdigest()[:16]


def secret_pred() -> str:
    """A short identity for the FIREWALL PREDICATE that produced each row's `secret` verdict.

    v0.4.44 (item 4). The manifest serves a cached `secret` per canonical row, and its documented
    invalidation rides the transact choke point — which unlinks the manifest when a fact file is
    published or deleted. A change to the fireWALL changes no FILE, so nothing unlinked anything
    and every cached verdict survived the repair. The rows that matters for are exactly the ones
    whose bytes never change, i.e. precisely the ones a repair does not touch.

    ⚠ DERIVED, never hand-maintained — and COMPLETE over the predicate's inputs. An earlier cut
    hashed only `_SECRET`'s pattern and `_entropy_blob`'s body, which left the knobs this
    firewall's own repair history actually tunes OUTSIDE the identity: MEASURED, `_ENTROPY_SEG_FLOOR`
    8 -> 40 and a replaced `_BLOB` each left the hash byte-identical while changing which inputs
    `_entropy_blob` matches, and `_SECRET`'s `re.I | re.X` flags were invisible too.
    ⚠ That failure runs the DANGEROUS way, which is why it is worth this much text: the cached
    flag is the SOLE firewall gate on the warm-pull path (`sync_global` returns on
    `r.get("secret")` and deliberately SKIPS the admit-side re-scan), so a firewall STRENGTHENED
    after a manifest was built would leave stale `secret: False` rows being admitted cross-project
    into context — against CLAUDE.md's "Secrets firewall at retrieval … don't weaken that".
    A literal version constant would be the same defect restated: a second thing to remember.
    """
    import inspect
    from memory_status import (_BLOB, _ENTROPY_SEG_FLOOR, _SECRET, _entropy_blob, _looks_secret)
    # ⚠ BOTH flag sets, not just `_SECRET`'s. The identity claims COMPLETENESS over the
    # predicate's inputs, and hashing `_BLOB.pattern` without `_BLOB.flags` left the asymmetry
    # in the one place the claim is strongest: recompiling `_BLOB` with a flag leaves `.pattern`
    # byte-identical, so the hash would not move while the set it matches does. LATENT today —
    # `_BLOB`'s character class makes re.I/re.ASCII/re.M/re.S inert, so no flag both leaves the
    # pattern text intact and changes matching — but a coverage CLAIM is not allowed to be
    # stronger than its payload, which is the standard this file's own docstring polices.
    _bodies: list = []
    for _fn in (_looks_secret, _entropy_blob):
        # ⚠ TWO independent signals, because NEITHER is complete alone. `co_code` is always
        # available — it is the bytecode this process will actually EXECUTE, so it tracks the
        # predicate on a frozen/pyc-only install too — but a body edit that changes only a
        # CONSTANT moves the literal in `co_consts` without reshaping the bytecode, and it misses
        # that. `getsource` sees constants but does not exist when no source sits beside the
        # bytecode. Together they cover each other's blind spot; separately, either one leaves a
        # repair that fails to invalidate.
        _bodies.append(_fn.__code__.co_code.hex())
        try:
            _bodies.append(inspect.getsource(_fn))
        except (OSError, TypeError, SyntaxError):
            # ⚠ `SyntaxError` is NOT decoration, and `(OSError, TypeError)` was not enough.
            # `inspect.getsource` → `getblock` raises `IndentationError`/`TokenError`, both
            # `SyntaxError` subclasses, when the on-disk source no longer matches the running code
            # object's line range — i.e. exactly during a mid-edit or partially-written install.
            # Left uncaught, the marker fallback is SKIPPED and `secret_pred` raises out of the
            # whole identity. Contained today only because all four callers wrap it in a bare
            # `except Exception`; a caller that failed CLOSED on an identity error would turn a
            # transient source mismatch into a refused store. Caught here so the fallback is
            # reachable, which is what this arm is FOR.
            # ⚠ NOT a claim that a repair still invalidates here, which an earlier cut of this
            # comment made ("the identity still MOVES — the marker differs from real source") and
            # which is FALSE in the case that matters: on a PERSISTENTLY frozen install the marker
            # is a pure function of module and qualname, so a CONSTANT-only body repair of either
            # function yields the same identity and cached rows keep serving the old verdict —
            # running the dangerous way, on the path that skips the admit-side re-scan.
            # ⚠ And `co_code` above does NOT cover it either — an earlier cut of this comment said
            # it did, and a review lens measured otherwise: a CONSTANT-only body edit (e.g. adding
            # a character to `_entropy_blob`'s split set) leaves `co_code` byte-identical while the
            # verdict genuinely flips. So on a persistently source-less install the two signals'
            # blind spots COINCIDE exactly in the case this sentence names, and no constant-only
            # repair of either function invalidates. What the pair buys is: `co_code` catches
            # SHAPE changes without source, `getsource` catches CONSTANT changes with source.
            # Neither covers constant-only-without-source; that case is open and stated here
            # rather than fixed, because closing it needs the constants hashed from the code
            # object, and `co_consts` contains nested code objects whose repr is address-bearing
            # and therefore unstable across runs.
            _bodies.append(f"<source-unavailable:{_fn.__module__}.{_fn.__qualname__}>")
    # the memo is keyed on the VECTOR, so two calls in one process with the same predicate cost
    # one hash and a changed predicate still produces a different identity — see `_secret_pred_keyed`
    # ⚠ `_READ_CAP` IS PART OF THE PREDICATE, not a detail of the reader. It decides HOW MUCH of
    # each file `_looks_secret` ever sees, so two builds with different caps answer a different
    # question about the same bytes — and a row built under one is not evidence about the other.
    # MEASURED by a review lens: a 4 MiB-truncating build and a failing-open build produce
    # `secret: False` and a refusal respectively for the SAME file, and with the cap outside the
    # identity a cached truncated row was served end-to-end (the pull landed the fact, credential
    # and all). ⚠ What protected existing installs was that every pre-fix writer's identity
    # happened to differ for OTHER reasons — an incidental barrier, unstated and untested, which
    # the moment the identity stabilises would silently become no barrier at all. Hashing the cap
    # makes it structural: a change in how much is read invalidates the verdicts read under it.
    return _secret_pred_keyed(_SECRET.pattern, str(_SECRET.flags), _BLOB.pattern,
                              str(_BLOB.flags), str(_ENTROPY_SEG_FLOOR), str(_READ_CAP),
                              tuple(_bodies))


# ⚠ The reasons `ensure` must not ACT on. An allow-list that silently defaults to "do not rebuild"
# is how `"predicate-changed"` came to be ignored: the cache could then never rebuild on exactly
# the change it exists to notice, so every pull and every SessionStart beacon fell back to full
# enumeration permanently, with a hand-run `cm data facts-refresh` as the only escape.
#
# ⚠ Totality here is by DEFAULT, not by ENUMERATION, and an earlier cut of this comment claimed
# the stronger thing ("a new reason must be classified by CONSTRUCTION"). The mechanism is
# `if reason not in _NONREBUILDABLE: rebuild` — an unlisted reason rebuilds, which is the safe
# direction, but nothing FORCES a new reason to be thought about, and no test can enumerate the
# reasons `load()` might one day return. The claim was also self-undermining in a smaller way:
# ⚠ (Historical, kept because the reasoning is the reason the tuple is short:) `"rebuild-failed"`
# was never in `load()`'s return set — `ensure` produced it itself once the
# rebuild has failed, and returns it WITHOUT re-entering the membership test — so a reader taking
# the tuple for an enumeration of `load()`'s outputs would find one of its two members unreachable
# and could reasonably conclude the other is decorative too. It is not: it is the whole reason the
# default may point this way.
# ⚠ `"rebuild-failed"` was a member and is now REMOVED as dead, not as wrong. It existed for
# `ensure`'s `if rows:` arm, which read a successful EMPTY rebuild as failure — and that arm is
# itself the bug (see `ensure`). With it gone, `_rebuild_locked` either returns rows (possibly
# empty) or raises, so `ensure` has no failure return left to classify. Keeping the token would
# have left a member no producer can mint: a reader auditing the tuple against `ensure`'s code
# would find nothing that emits it, which is the same "unreachable member" defect a review lens
# flagged in this tuple two patches ago — except then it was reachable-in-principle and now it
# would be reachable-not-at-all. A dead member is worse than a documented one.
_NONREBUILDABLE = (
    "kill-switch",      # the operator asked the cache to stand aside; rebuilding defeats it
)

# ⚠ The other half of the classification, ENUMERATED so it can be TESTED. `_NONREBUILDABLE` alone
# states only what `ensure` must not act on, and a reason absent from BOTH tuples still rebuilds —
# which is the safe default, but it means a NEW terminal reason in `load()` is classified silently
# by falling through rather than by anyone deciding. With both tuples present a smoke pin can
# enumerate the reason literals `load()` returns and require each to appear in exactly one, so a
# new one reddens until it is placed. A default is not a decision until something reads it.
_REBUILDABLE = (
    "absent", "unparseable", "schema", "domain-mismatch", "files-shape",
    "row-shape", "row-fields", "predicate-changed",
)

# ⚠ The OTHER vocabulary, and it exists because the two tuples above classify only what `load()`
# returns. `ensure` MINTS terminal reasons of its own, and a token minted here had NO classifier:
# a review lens measured that `_miss`-AST enumeration is structurally blind to it, so a future
# consumer could read one as durable with nothing catching that. The first cut of this module's
# comment said the token is "deliberately in neither tuple" — which was true and not enough: not
# being mis-classified is not the same as being CLASSIFIED, and nothing forced a new mint to be
# thought about. Validated at the producer by `_mint`, exactly as `load()`'s are by `_miss`.
# ⚠ Each carries its TRANSIENCE, because that is the property consumers keep getting wrong:
# `lock-busy` clears itself (TRY LATER); `oversize` does not (the file must shrink).
_ENSURE_REASONS = (
    "rebuilt",      # success sentinel — the rebuild ran and its rows are the answer
    "lock-busy",    # TRANSIENT: another process holds the lock; the caller falls back and retries
    "oversize",     # PERMANENT until the file shrinks below _READ_CAP
)


def _mint(reason: str) -> "tuple[None, str]":
    """A terminal reason `ensure` MINTS, validated like `_miss` validates `load()`'s reasons."""
    if reason not in _ENSURE_REASONS:
        raise AssertionError(
            f"unclassified ensure reason {reason!r} — declare it in _ENSURE_REASONS (and say "
            f"whether it is transient) before `ensure` can return it")
    return None, reason


# ⚠ Every reason `ensure` may return, from BOTH vocabularies, and the union is the point: `ensure`
# passes `load()`'s reasons straight through as well as minting its own, so a guard keyed on
# `_ENSURE_REASONS` alone would redden on a perfectly correct tree. `""` is the success sentinel
# (rows were served from a healthy cache) — not a reason to rebuild, the ABSENCE of a refusal.
_KNOWN_REASONS = (frozenset(_ENSURE_REASONS) | frozenset(_REBUILDABLE)
                  | frozenset(_NONREBUILDABLE) | {""})


def _served(rows: Any, reason: str) -> "tuple[Any, str]":
    """`ensure`'s return, with the reason CLASSIFIED — the RUNTIME half of the classification.

    ⚠ This exists because the pin's half is a SCAN, and a scan cannot see value. `tests/smoke.py`
    enumerates the AST spellings `_mint("<literal>")` and `return x, "<literal>"`, so a reason
    minted through a NAME — `return None, _NEW_TOKEN` — passed every check while circulating an
    unclassified reason (MEASURED: all ten v0.4.57 checks green, while the literal-form control
    reddened). ⚠ No wider scan can close that: a `Name` in the return position is
    AST-INDISTINGUISHABLE from `load()`'s legitimate passthrough (`return None, reason`), which is
    why the pin enumerates literals at all. The PRODUCER can see the value, the scanner cannot —
    so the assertion lives here, where the decision that produced it is made.
    """
    if reason not in _KNOWN_REASONS:
        raise AssertionError(
            f"unclassified reason {reason!r} returned by ensure — mint it through `_mint` (and "
            f"declare it in `_ENSURE_REASONS`, saying whether it is transient), or it is not a "
            f"reason this cache may serve")
    return rows, reason


def build(facts_dir: Path) -> "tuple[list, str]":
    """Enumerate + classify the facts dir once. Returns (rows, domain).

    Per file: open + read + fstat(fd) so the stats PIN the bytes the row was
    built from. Skips MEMORY.md and reserved/unsafe stems (the exact skip set of
    `_admissible_records`).
    """
    from fact_schema import classify_canonical
    from memory_status import _frontmatter, _looks_secret
    from mirror_conflict import semantic_hash
    from sync_global import _body_hash, _is_reserved_stem, _safe_stem
    # ⚠ computed on the FIRST ROW, never on entry. The identity costs a `getsource` plus a
    # `linecache` fill of `memory_status` (and, on a process that has not otherwise imported
    # `inspect`, ~20 ms of deferred import), and the two reaches that discard it are ordinary: a
    # domain with no facts dir, and a dir with no admissible facts. Both stamp no row, so both
    # paid in full for nothing. ⚠ `_secret_pred_keyed` memoises only the SHA256, NOT this
    # function — an earlier cut of this comment said "so this is once per process", and a review
    # lens measured the `inspect.getsource` still running on every call (5 calls: 22.8 / 0.41 /
    # 0.40 / 0.39 / 0.39 ms, against 0.004 ms for the memoised digest alone). So laziness saves
    # the ZERO-ROW reaches, which is what it was added for; a process that reads rows pays the
    # `getsource` per call, and only the hash is shared.
    _PRED = ""
    rows: list = []
    domain = Path(facts_dir).parent.name
    if not Path(facts_dir).is_dir():
        return rows, domain
    try:
        entries = list(os.scandir(facts_dir))
    except OSError:
        return rows, domain
    for ent in entries:
        if not ent.is_file(follow_symlinks=False):
            continue
        name = ent.name
        if not name.endswith(".md") or name == "MEMORY.md":
            continue
        stem = name[:-3]
        if _is_reserved_stem(stem) or not _safe_stem(stem):
            continue
        try:
            fd = os.open(ent.path, os.O_RDONLY)
        except OSError:
            continue
        try:
            st = os.fstat(fd)
            # ⚠ A file past the cap is REFUSED WHOLE, never truncated. `os.read` returns at most
            # the cap, so a longer file would be classified from its PREFIX — and the two callers
            # disagree about what they read: this cache would judge a prefix while the fallback
            # (`sync_global`'s full-text read) judges everything. MEASURED on a 4,800,090-byte
            # fact whose credential sits in the tail: `_looks_secret(whole)` is True, the cached
            # row says `secret: False`, and the warm-pull gate is `if r.get("secret"): return` —
            # so it does NOT return, and the fact is admitted cross-project into context without
            # the admit-side re-scan that path deliberately skips. That is a firewall BYPASS, not
            # a slow path, and it is the one direction CLAUDE.md forbids outright.
            if st.st_size > _READ_CAP:
                raise _Oversize(f"{ent.name}: {st.st_size} bytes > {_READ_CAP}")
            data = os.read(fd, _READ_CAP)
        except OSError:
            data = b""
            st = None
        finally:
            os.close(fd)
        if st is None:
            continue
        if not _PRED:
            _PRED = secret_pred()
        text = data.decode("utf-8", errors="replace")
        fm = _frontmatter(text)
        cls = classify_canonical(text, stem=stem, domain=domain)
        rows.append({
            "stem": stem,
            "mtime_ns": int(st.st_mtime_ns),
            "size": int(st.st_size),
            "ctime_ns": int(st.st_ctime_ns),
            "body_hash": _body_hash(text),
            "sem": semantic_hash(text),
            "class": cls.get("class") or "",
            "secret": bool(_looks_secret(text)),
            "secret_pred": _PRED,
            "fm": fm,
        })
    rows.sort(key=lambda r: r["stem"])
    return rows, domain


def _miss(reason: str) -> "tuple[None, str]":
    """A cache miss, with its REBUILDABILITY DECLARED AT THE PRODUCER — or refused.

    ⚠ The classification used to be a check (`reason not in _NONREBUILDABLE`) with an implicit
    default, so a NEW terminal reason was classified by FALLING THROUGH rather than by anyone
    deciding: safe by direction, silent by construction. Every `return None, <reason>` in `load`
    now goes through here, and an undeclared reason RAISES on its first call — at the producer,
    naming itself — instead of quietly acquiring `global.lock` and rebuilding.
    ⚠ Raised, not warned: a warning on a hot path is a line nobody reads, and this fires exactly
    once per reason (a developer's first run), never in production.
    """
    if reason not in _NONREBUILDABLE and reason not in _REBUILDABLE:
        raise AssertionError(
            f"unclassified cache-miss reason {reason!r} — declare it in _REBUILDABLE or "
            f"_NONREBUILDABLE before `ensure` can act on it")
    return None, reason


def load(facts_dir: Path, plugin_data_dir: Path):
    """(rows_by_stem | None, reason). None = fail open (full enumeration).

    ⚠ WHAT A SERVED ROW WARRANTS — stated because a review lens asked the right question and the
    answer was nowhere written down. A row is served only under a TWO-PART warrant, and this
    function enforces exactly ONE half of it:

      * the PREDICATE is unchanged — `secret_pred` matches, enforced at the `secret_pred`
        comparison in this function; a foreign
        identity fails open to a rebuild, so a row can never be judged by a firewall other than
        the running one; and
      * the FILE is unchanged — `st_mtime_ns`, `st_size` **and `st_ctime_ns`** all match the row,
        enforced at the CONSUMER (`sync_global._consider_fast`), because only the consumer has the
        `DirEntry` stat that makes the warm path warm. ⚠ An earlier cut of this sentence named
        only the first two; a review lens measured that the code compares THREE, and the omission
        was not cosmetic — `st_ctime_ns` is the conjunct that catches a restored-mtime edit, so
        the authoritative statement of the warrant was dropping the one it most needs.

    ⚠ This is deliberately NOT an independent re-derivation of `secret` (or of `class`, `sem`,
    `fm`). Every field in the row comes from the SAME read, so re-checking one of them would mean
    re-reading the file — which is the cache. What the lens named as "an identity match is the
    whole warrant" is true OF THIS FUNCTION, and false of the system: the stats half lives one
    frame out. ⚠ The split is the risk — a second consumer that reads `load()` directly and skips
    the stats check would trust a stale row for a file that changed underneath it, and nothing in
    THIS function would notice. `_consider_fast` is pinned for exactly that reason.
    """
    if os.environ.get(KILL_SWITCH) == "0":
        return _miss("kill-switch")
    domain = Path(facts_dir).parent.name
    p = manifest_path(plugin_data_dir, domain)
    try:
        raw = p.read_text(encoding="utf-8")
    except OSError:
        return _miss("absent")
    try:
        doc = json.loads(raw)
    except (ValueError, TypeError):
        return _miss("unparseable")
    if not isinstance(doc, dict) or doc.get("schema_version") != SCHEMA_VERSION:
        return _miss("schema")
    if str(doc.get("domain") or "") != domain:
        return _miss("domain-mismatch")
    files = doc.get("files")
    if not isinstance(files, list):
        return _miss("files-shape")
    # ⚠ No rows to check ⇒ no verdicts to bind, so the identity is not computed at all. Same
    # reason as `build`'s lazy `_PRED`: `_rebuild_locked` legitimately writes `files: []` for a
    # missing facts dir, and every later load of that domain would otherwise hash ~16 KB of source
    # and compare it against nothing.
    if not files:
        return {}, ""
    _now = secret_pred()
    rows: dict = {}
    for r in files:
        if not isinstance(r, dict):
            return _miss("row-shape")
        stem = str(r.get("stem") or "").strip()
        fm = r.get("fm")
        if not stem or not isinstance(fm, dict):
            return _miss("row-fields")
        # ⚠ The verdict's PRODUCER must still be the one that produced it. A row from before a
        # firewall change carries a foreign `secret_pred`; serving it would keep a wrongly-flagged
        # canonical flagged (and withheld or GC'd) long after the predicate was repaired. Failing
        # open rebuilds — the module's stated posture ("can slow you down but never serves wrong
        # facts"), applied to the predicate half of "wrong" that the file keys could not see.
        if str(r.get("secret_pred") or "") != _now:
            return _miss("predicate-changed")
        rows[stem] = r
    return rows, ""


def ensure(facts_dir: Path, plugin_data_dir: Path, *, may_write: bool = True):
    """Load, or rebuild-under-lock when the cache needs it. (rows_by_stem | None, reason).

    ⚠ The rebuild NEVER WAITS for `global.lock`; a held lock returns `(None, "lock-busy")` and the
    caller falls back to a full read. See `_rebuild_locked`.

    ⚠ THE REASON IS VALIDATED AT THE SINGLE EXIT, and that is why this is a WRAPPER rather than a
    helper called from each return. The first cut put `_served(...)` on the four returns that
    happened to need it — totality by CONVENTION — and a review lens measured the consequence: a
    NEW return added to `ensure`, or an existing one edited to drop the call, still escapes, with
    the suite green at 2331/0 while `(None, 'totally-undeclared')` reached the caller. Wrapping
    makes it total by CONSTRUCTION: every path out of the inner function, including one nobody has
    written yet, passes the one check. That is the only shape that survives a future edit.
    ⚠ AND THE INNER IS A CLOSURE, not a module-level function. The first cut named it `_ensure_inner`
    at module level, which left an importable, obviously-named bypass — a review lens measured that
    calling it directly returns an unvalidated reason and that NOTHING in the suite notices (the
    structural pin inspects this function's returns, never call sites).
    ⚠ NO NAME TO IMPORT — and that is the exact claim, no stronger. The first cut of this sentence
    said the bypass was "INEXPRESSIBLE", which a review lens measured FALSE: the CODE is still
    reachable two ways. `types.FunctionType(code, ..., closure=...)` over `ensure.__code__.co_consts`
    (deliberate introspection, not a realistic edit), and — the one that matters — ATTACHING the
    inner as an attribute (`ensure.inner = _inner`), which is a one-line edit in this repo's OWN
    idiom: the suite already reaches into this module that way (`setattr(_fm44, "_READ_CAP", …)`).
    So: no name to import, and the v0.4.59 pin additionally asserts the inner is not attached.
    ⚠ Its side benefit, also measured: the mint literals stay inside THIS function's AST subtree, so
    the v0.4.57 scan reads them without being pointed at an inner name. That matcher had already
    broken twice on refactors of this function; the closure removes the target it had to track.
    """
    # ⚠ A NESTED function, not a module-level one, and that is the whole point. The first cut
    # made the inner a module-level `_ensure_inner`, which left an importable, obviously-named
    # bypass: calling it directly returns an unvalidated reason and NOTHING in the suite notices
    # (measured by a review lens — the structural pin inspects `ensure`'s returns, never call
    # sites). A closure has no name to import, so the bypass is not merely undetected but
    # INEXPRESSIBLE. ⚠ It also keeps the mint literals inside `ensure`'s own AST subtree, so the
    # v0.4.57 scan reads them without being pointed at an inner name — the spelling-bound matcher
    # had already broken twice on refactors of this function, and this removes its target to track.
    def _inner():
        """Load, or rebuild-under-lock when the cache needs it. (rows_by_stem | None, reason).

        ⚠ The rebuild NEVER WAITS for `global.lock`; a held lock returns `(None, "lock-busy")` and the
        caller falls back to a full read. See `_rebuild_locked`.

        `may_write=False` is the READ-ONLY form: a caller whose own contract forbids writing gets
        `(None, reason)` instead of a rebuild, so it degrades to its full-read fallback rather than
        taking `global.lock` and writing a manifest. The SessionStart beacon needs exactly this —
        CLAUDE.md documents it as read-only, its hook budget is 2s, and a concurrent `cm sync`
        holding `global.lock` would otherwise block it into that deadline.

        ⚠ The flag lives HERE, beside the decision it qualifies, and NOT in the callers. The beacon
        had already chosen `load()` — the read-only form — deliberately, with a comment saying so,
        and was still defeated, because the write came from a helper THREE frames down
        (`main` → `iter_admissible_facts` → `_admissible_records` → here) — and the WRITE one frame
        below that (`_rebuild_locked`, frame 4). ⚠ Counted, not estimated: this sentence said "four"
        while its own parenthetical terminated at `ensure`, which is frame 3, and an earlier pass
        fixed the two sibling sites and declared THIS one correct without re-reading it. A guard one
        call deep is not a
        guard on the call path; that is this repo's weakest-enforcement-site rule, and the v0.4.45
        inversion WIDENED the set of reasons that reach the rebuild (`predicate-changed` and
        `row-fields` were already read-only), which is what made a latent hole a live one.
        """
        rows, reason = load(facts_dir, plugin_data_dir)
        if rows is not None:
            return _served(rows, reason)
        if not may_write:
            return _served(None, reason)
        if reason not in _NONREBUILDABLE:
            try:
                rows, domain = _rebuild_locked(facts_dir, plugin_data_dir)
            except _Oversize as _e:
                # ⚠ FAIL OPEN, and never write. Nothing was written (the raise precedes the atomic
                # write), so every later call re-enumerates rather than serving the truncated verdict
                # — the safe direction, and the only one available: a row for this file cannot be
                # built correctly WITHOUT reading all of it, and reading all of it is what the cap
                # exists to avoid on the hook path.
                # ⚠ AND IT IS NOT SILENT. A refusal that names nothing leaves the operator with a
                # permanently-cold cache and no lead: measured, a 300-fact domain with ONE 5 MiB fact
                # went from 1.3 ms to ~1.4 s EVERY call, forever, with `cm data facts-refresh` — the
                # documented repair — cheerfully reporting that it "rebuilds lazily on next read".
                # This is the one place the offending file can be named, so it is named here.
                print(f"facts_manifest: refusing to cache {facts_dir} — {_e}; every read will "
                      f"re-enumerate in full until this file is shrunk below {_READ_CAP} bytes",
                      file=sys.stderr)
                return _mint("oversize")
            if rows is None:
                # DECLINED, not failed: another process holds `global.lock` (see `_rebuild_locked`).
                # Terminal — `ensure` does not retry, and every caller already has the full-read
                # fallback this cache exists to skip.
                # ⚠ `"lock-busy"` is deliberately in NEITHER `_REBUILDABLE` nor `_NONREBUILDABLE` —
                # those classify the reasons `load()` returns, and filing this among them would repeat
                # the defect that removed `"rebuild-failed"` (a member whose producer is elsewhere).
                # ⚠ But "not mis-filed" is not "classified": it is minted HERE, so it belongs to the
                # OTHER vocabulary, `_ENSURE_REASONS`, which names its TRANSIENCE — the property three
                # separate consumers each had to get right by hand before this existed.
                return _mint("lock-busy")
            # ⚠ `rows, "rebuilt"` UNCONDITIONALLY — never `if rows:`. `_rebuild_locked` returns a dict
            # on SUCCESS, and that dict is legitimately EMPTY for a domain with no facts: `build()`
            # returns `[]`, the manifest is written as `{"files": []}`, and the rebuild SUCCEEDED.
            # Reading `{}` as failure made `ensure` return `(None, "rebuild-failed")` for a successful
            # empty rebuild — so `cm data facts-refresh`, the DOCUMENTED REPAIR, reported permanent
            # failure with a BLANK cause on every freshly-enrolled domain, and no action could clear
            # it because a zero-fact domain can never produce rows. MEASURED by two review lenses,
            # independently, on this PR's own new helper.
            return _served(rows, "rebuilt")
        return _served(None, reason)

    return _served(*_inner())
def _rebuild_locked(facts_dir: Path, plugin_data_dir: Path):
    """Rebuild the cache under `global.lock`, or DECLINE. `(rows | None, domain)`.

    ⚠ `rows is None` means the lock was held by another process and we did not wait. It is a
    THIRD state beside "rebuilt (possibly to zero rows)" and "raised", and the caller must test it
    with `is None` — a domain with no facts legitimately rebuilds to `{}`, which is falsy.

    ⚠ IT TRIES, IT NEVER WAITS, and that is unconditional — there is no flag. The lock serializes
    two concurrent REBUILDERS; it does not guard anything whose value depends on the wait. Losing
    the race costs a full enumeration for this call and leaves the cache to be warmed by whichever
    process holds it (or by the next uncontended read) — never a wrong row, because the fallback
    is the full read this cache exists to skip. Measured: with `global.lock` held, an ENROLLED
    project with a cold manifest made `cm status --json` hang past 10 s at exactly this line, while
    the whole command takes ~0.1 s uncontended. ⚠ This is the frame the v0.4.54 and v0.4.56 fixes
    each MISSED from opposite sides: 0.4.54 disabled the rebuild outright (`may_rebuild=False`,
    which cost ~100x on every read forever), and 0.4.56 fixed the preflight cache — a different
    `global.lock` taker — while claiming it was "the only lock on a read command". Both were
    claims about a SET, settled by finding one member. The stack dump is the instrument for a set
    question; this line is what it named.
    """
    from control_plane import FileLock, atomic_write_bytes
    domain = Path(facts_dir).parent.name
    pdir = Path(plugin_data_dir)
    pdir.mkdir(parents=True, exist_ok=True)
    lock = FileLock(pdir / "locks" / "global.lock")
    if not lock.try_acquire():
        return None, domain
    try:
        # double-checked: another reader may have rebuilt in the window between the `load()` that
        # sent us here and the acquire above. (It is NOT "while we waited" — we never wait.)
        rows, reason = load(facts_dir, pdir)
        if rows is not None:
            return rows, domain
        built, _d = build(facts_dir)
        doc = {"schema_version": SCHEMA_VERSION, "domain": domain,
               "files": built}
        atomic_write_bytes(manifest_path(pdir, domain),
                           (json.dumps(doc, indent=1) + "\n").encode("utf-8"),
                           mode=0o600)
        rows = {r["stem"]: r for r in built}
        return rows, domain
    finally:
        lock.release()
