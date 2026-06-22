#!/usr/bin/env python3
"""Dream beta-harness — memory-store + always-loaded-doc SNAPSHOT / DIFF / RESTORE (SPEC §7).

The side-effect apparatus for the consolidate-memory beta-tester. A dream MUTATES the private
memory store (rewrites ``MEMORY.md``, edits/creates/prunes fact ``*.md``) and may touch the
repo's always-loaded docs; this module captures a cheap, content-hashed BEFORE image, computes
the deterministic mutation DELTA after a run (the half-(b) "claim-vs-reality" oracle leg), and
RESTORES the pre-dream state so a pure beta-test leaves no trace (the default in ``--test``).

What is snapshotted (SPEC §7):
  * the whole memory store dir  ``~/.claude/projects/<slug>/memory/``  — every regular file:
    the fact ``*.md``, the store-internal ``MEMORY.md`` index, AND the skill's derived side
    files (``.consolidation-state.json`` / ``.consolidation-log.jsonl`` / ``.mutation-log.jsonl``);
  * the repo's three always-loaded docs at the repo ROOT: ``MEMORY.md`` / ``AGENTS.md`` /
    ``CLAUDE.md``  (each captured iff present — most repos only have ``CLAUDE.md``);
  * the marker = ``.consolidation-state.json``'s ``commit`` / ``timestamp`` (the dream's advance
    signal), surfaced as a first-class field so ``diff`` reports the marker delta explicitly.

Design choices (each load-bearing):
  * **Namespaced by origin.** A snapshot stores files under ``store/<name>`` vs ``repo/<name>``
    so the store-internal ``MEMORY.md`` (the index) and a repo-root ``MEMORY.md`` (an
    always-loaded doc) — which COLLIDE on basename — never conflate in the manifest, the diff,
    or restore. ``store/`` is a flat mirror (the store has no managed sub-dirs).
  * **Snapshot dir = the harness's own ``reports/.snap-<ts>/``**, NEVER the project slug dir.
    The slug dir holds LIVE session transcripts (a ``*.jsonl`` per session); writing a snapshot
    or a scratch file there violates the very snapshot contract this module enforces (the P-5
    finding: the prototype leaked ``.beta_cycle.json`` into the slug dir).
  * **Content hash the run can't fake** (``sha256`` of the bytes). A re-index that rewrites
    ``MEMORY.md`` to byte-identical content is correctly NOT a mutation.
  * **Q4 allowlist** of expected derived side files (``.consolidation-state.json``,
    ``.consolidation-log.jsonl``, ``.mutation-log.jsonl``) — the VERIFIED skill writers. ``diff``
    TAGS each store-dir change ``allowed`` (a known derived-file write) vs ``unexpected`` (any
    other store mutation — the dashboard-dishonesty signal the claim-vs-reality family escalates
    to HIGH). The marker file is itself an allowed derived file; its delta is also surfaced
    separately as the marker advance.
  * **SKIP, never crash** (SPEC): an absent store / absent repo doc / missing snapshot dir is a
    first-class outcome, reported with a reason — not an exception.

This is CONSUMER / beta-tester tooling. It lives OUTSIDE the skill
(``~/.claude/dream-beta-tester/``) and NEVER patches it. Pure stdlib.

Usage:
    python3 snapshot.py snapshot [--repo DIR] [--store DIR] [--out DIR] [--json]
    python3 snapshot.py diff --before SNAPDIR [--after SNAPDIR | --repo DIR] [--json]
    python3 snapshot.py restore --before SNAPDIR [--repo DIR] [--store DIR] [--dry-run] [--json]

      snapshot  capture the store + repo docs to reports/.snap-<ts>/ (or --out); print the manifest.
      diff      compare a BEFORE snapshot to an AFTER snapshot (or the LIVE state via --repo/--store);
                emit added/removed/changed (by hash) + the marker delta + the allowed/unexpected tags.
      restore   write a BEFORE snapshot's files back over the live store + repo docs (default for a
                pure --test); --dry-run reports the planned writes/deletes without touching disk.

Exit code: ``diff`` → 1 iff any UNEXPECTED store mutation (dashboard-dishonesty), else 0.
``snapshot`` / ``restore`` → 0 on success, 2 on a hard failure (e.g. nothing to snapshot/restore).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

# ─────────────────────────────── constants ───────────────────────────────

#: The repo-root always-loaded docs (SPEC §7) — mirrors the skill's ``REPO_DOCS``.
REPO_DOCS: tuple[str, ...] = ("MEMORY.md", "AGENTS.md", "CLAUDE.md")

#: The dream's advance marker, inside the store. Carries ``commit`` / ``timestamp``.
MARKER_FILE: str = ".consolidation-state.json"

#: Q4 allowlist — the VERIFIED skill writers into the store dir (derived state, not facts).
#: A change to one of these is an EXPECTED side effect; any OTHER store mutation is unexpected
#: (the dashboard-dishonesty signal). ``.mutation-log.jsonl`` is the v0.1.22 audit-trail writer
#: (forward-compatible: absent at v0.1.21, harmless to allowlist).
DERIVED_SIDE_FILES: frozenset[str] = frozenset(
    {".consolidation-state.json", ".consolidation-log.jsonl", ".mutation-log.jsonl"}
)

#: Where snapshots live — a STABLE user dir (never the project slug dir, the P-5 lesson; and never
#: the plugin/script dir, so reports survive plugin updates). Override via $DREAM_BETA_REPORTS.
HARNESS_ROOT: Path = Path(__file__).resolve().parent
REPORTS_DIR: Path = Path(os.environ.get("DREAM_BETA_REPORTS") or (Path.home() / ".dream-beta-test" / "reports"))

#: Manifest schema version (bumped if the on-disk snapshot layout changes).
MANIFEST_VERSION: int = 1
MANIFEST_NAME: str = "manifest.json"

_SLUG_SUB = re.compile(r"[^A-Za-z0-9]")  # v0.1.40 (M3): match the skill's generalized slug rule (all non-alnum → '-')


# ─────────────────────────────── slug / store resolution ───────────────────────────────


def slug_for(repo: Path) -> str:
    """Claude Code project slug: the absolute path with EVERY non-alphanumeric char → ``-`` (case kept).

    Mirrors the skill's ``memory_status.slug_for`` (v0.1.40 M3: ``re.sub(r'[^A-Za-z0-9]', '-', ...)``) so the snapshot
    targets the SAME store the skill manages (see claude-code-memory-is-slug-scoped). Re-implemented
    rather than imported to keep this module skill-discovery-free.
    """
    return _SLUG_SUB.sub("-", str(repo.resolve()))


def default_store(repo: Path) -> Path:
    return Path.home() / ".claude" / "projects" / slug_for(repo) / "memory"


# ─────────────────────────────── hashing helpers ───────────────────────────────


def _sha256(path: Path) -> str | None:
    """The sha256 hex digest of ``path``'s bytes, or None if unreadable. Streamed (a store doc is
    small, but streaming keeps memory flat and never assumes a size)."""
    h = hashlib.sha256()
    try:
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(65536), b""):
                h.update(chunk)
    except OSError:
        return None
    return h.hexdigest()


def _read_marker(state_path: Path) -> dict[str, Any]:
    """Parse ``.consolidation-state.json`` → ``{commit, timestamp}`` (other keys preserved under
    ``extra``). A missing/garbled marker yields an empty record — never raises (SKIP-not-crash)."""
    try:
        raw = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError):
        return {}
    if not isinstance(raw, dict):
        return {}
    out: dict[str, Any] = {
        "commit": raw.get("commit", ""),
        "timestamp": raw.get("timestamp", ""),
    }
    extra = {k: v for k, v in raw.items() if k not in ("commit", "timestamp")}
    if extra:
        out["extra"] = extra
    return out


# ─────────────────────────────── data model ───────────────────────────────


@dataclass
class FileEntry:
    """One captured file in a snapshot manifest."""

    origin: str  # "store" | "repo"
    name: str  # basename (store) or repo-relative doc name (REPO_DOCS)
    rel: str  # path within the snapshot dir, e.g. "store/MEMORY.md" / "repo/CLAUDE.md"
    src: str  # absolute source path it was copied FROM (the restore target)
    sha256: str | None  # content hash; None = unreadable at capture (M5: recorded so restore PRESERVES it — never deletes a pre-run file it couldn't hash, never overwrites it with nothing)
    size: int  # bytes (-1 when unreadable at capture)
    derived: bool  # store-side: is this an allowlisted derived side file (vs a fact/index)?


@dataclass
class Manifest:
    """The snapshot record persisted as ``<snapdir>/manifest.json`` and returned by ``snapshot()``."""

    manifest_version: int
    created: str  # UTC ISO-8601, second precision
    repo: str
    store: str
    snapshot_dir: str
    store_present: bool
    repo_docs_present: list[str]  # which of REPO_DOCS existed at snapshot time
    marker: dict[str, Any]  # the .consolidation-state.json commit/timestamp (the advance signal)
    files: list[FileEntry]
    notes: list[str] = field(default_factory=list)


def _manifest_from_dict(d: dict[str, Any]) -> Manifest:
    """Rehydrate a Manifest from a loaded ``manifest.json`` (FileEntry list reconstructed)."""
    files = [FileEntry(**fe) for fe in d.get("files", [])]
    return Manifest(
        manifest_version=d.get("manifest_version", 0),
        created=d.get("created", ""),
        repo=d.get("repo", ""),
        store=d.get("store", ""),
        snapshot_dir=d.get("snapshot_dir", ""),
        store_present=d.get("store_present", False),
        repo_docs_present=d.get("repo_docs_present", []),
        marker=d.get("marker", {}),
        files=files,
        notes=d.get("notes", []),
    )


def load_manifest(snapdir: Path) -> Manifest:
    """Load ``<snapdir>/manifest.json`` → Manifest. Raises FileNotFoundError/ValueError on a bad
    snapshot dir (the caller turns that into a SKIP/exit-2 with a clear message)."""
    mpath = snapdir / MANIFEST_NAME
    data = json.loads(mpath.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{mpath} is not a JSON object")
    return _manifest_from_dict(data)


# ─────────────────────────────── SNAPSHOT ───────────────────────────────


def _ts() -> str:
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())


def snapshot(repo: Path, store: Path, out: Path | None = None) -> Manifest:
    """Capture the store + the repo's always-loaded docs + the marker to ``reports/.snap-<ts>/``.

    Copies every regular file in ``store`` (namespaced ``store/<name>``) and each present repo doc
    (namespaced ``repo/<name>``), recording a content hash + size for each and the marker
    commit/timestamp. An ABSENT store (a never-dreamed repo) or absent repo docs are first-class:
    the manifest records what existed and notes what didn't — it never raises. Returns the Manifest
    (also persisted as ``<snapdir>/manifest.json``).
    """
    repo = repo.resolve()
    store = store.resolve()
    snapdir = (out.resolve() if out else REPORTS_DIR / f".snap-{_ts()}")
    snapdir.mkdir(parents=True, exist_ok=True)

    notes: list[str] = []
    files: list[FileEntry] = []
    store_present = store.is_dir()

    # ── the memory store: a flat mirror of every regular file ──
    if store_present:
        store_dst = snapdir / "store"
        store_dst.mkdir(parents=True, exist_ok=True)
        for src in sorted(store.iterdir(), key=lambda p: p.name):
            if not src.is_file():
                continue  # the store has no managed sub-dirs; skip any stray dir/symlink-to-dir
            digest = _sha256(src)
            if digest is None:
                # M5 (v0.1.4): RECORD an unreadable pre-run file (no copy) instead of skipping it — so its
                # name ∈ snapshot_store_names → restore's delete-loop will NOT unlink it (it existed pre-run),
                # and the write-loop skips it (no snapshot copy → nothing to overwrite it with). Preserved, not lost.
                notes.append(f"store file unreadable, RECORDED-not-copied (preserved on restore): {src.name}")
                files.append(FileEntry(origin="store", name=src.name, rel=f"store/{src.name}",
                                       src=str(src), sha256=None, size=-1, derived=src.name in DERIVED_SIDE_FILES))
                continue
            dst = store_dst / src.name
            try:
                shutil.copy2(src, dst)
            except OSError as e:
                notes.append(f"store file copy failed ({src.name}): {type(e).__name__}: {e}")
                continue
            files.append(
                FileEntry(
                    origin="store",
                    name=src.name,
                    rel=f"store/{src.name}",
                    src=str(src),
                    sha256=digest,
                    size=src.stat().st_size,
                    derived=src.name in DERIVED_SIDE_FILES,
                )
            )
    else:
        notes.append(
            f"store {store} does not exist — never-dreamed repo (a valid CLEAN baseline, "
            "not a defect); store side of the snapshot is empty"
        )

    # ── the repo's always-loaded docs (each iff present) ──
    repo_docs_present: list[str] = []
    repo_dst = snapdir / "repo"
    for name in REPO_DOCS:
        src = repo / name
        if not src.is_file():
            continue
        digest = _sha256(src)
        if digest is None:
            notes.append(f"repo doc unreadable, skipped: {name}")
            continue
        repo_dst.mkdir(parents=True, exist_ok=True)
        dst = repo_dst / name
        try:
            shutil.copy2(src, dst)
        except OSError as e:
            notes.append(f"repo doc copy failed ({name}): {type(e).__name__}: {e}")
            continue
        repo_docs_present.append(name)
        files.append(
            FileEntry(
                origin="repo",
                name=name,
                rel=f"repo/{name}",
                src=str(src),
                sha256=digest,
                size=src.stat().st_size,
                derived=False,
            )
        )
    if not repo_docs_present:
        notes.append(f"no repo always-loaded docs ({'/'.join(REPO_DOCS)}) present at {repo}")

    marker = _read_marker(store / MARKER_FILE) if store_present else {}

    manifest = Manifest(
        manifest_version=MANIFEST_VERSION,
        created=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        repo=str(repo),
        store=str(store),
        snapshot_dir=str(snapdir),
        store_present=store_present,
        repo_docs_present=repo_docs_present,
        marker=marker,
        files=files,
        notes=notes,
    )
    _write_manifest(snapdir, manifest)
    return manifest


def _write_manifest(snapdir: Path, manifest: Manifest) -> None:
    (snapdir / MANIFEST_NAME).write_text(
        json.dumps(_manifest_to_dict(manifest), indent=2), encoding="utf-8"
    )


def _manifest_to_dict(manifest: Manifest) -> dict[str, Any]:
    d = asdict(manifest)
    # asdict already expands FileEntry dataclasses into dicts.
    return d


# ─────────────────────────────── DIFF ───────────────────────────────


@dataclass
class FileDelta:
    origin: str  # "store" | "repo"
    name: str
    op: str  # "created" | "deleted" | "modified"
    before_sha: str  # "" if absent before
    after_sha: str  # "" if absent after
    size_delta: int  # after_size - before_size (0 when one side absent uses the present size signed)
    classification: str  # "allowed" (derived side file) | "fact" | "index" | "repo_doc"
    expected: bool  # True iff this change is an allowlisted derived-file write (Q4)


@dataclass
class MarkerDelta:
    advanced: bool  # commit OR timestamp changed
    before: dict[str, Any]
    after: dict[str, Any]


@dataclass
class DiffReport:
    repo: str
    store: str
    before_dir: str
    after_dir: str  # "" when diffing against the LIVE state
    against_live: bool
    deltas: list[FileDelta]
    marker: MarkerDelta
    unexpected_store_mutations: list[str]  # names of store *.md / index changes NOT on the allowlist
    summary: dict[str, int]
    notes: list[str] = field(default_factory=list)


def _index_by_key(manifest: Manifest) -> dict[tuple[str, str], FileEntry]:
    """Map (origin, name) → FileEntry. The key namespaces store vs repo so a store ``MEMORY.md`` and
    a repo ``MEMORY.md`` never collide."""
    return {(fe.origin, fe.name): fe for fe in manifest.files}


def _live_manifest(repo: Path, store: Path) -> Manifest:
    """A *virtual* manifest of the CURRENT on-disk state (hashes only — no copy), so ``diff`` can
    compare a BEFORE snapshot against the live store/docs after a dream without a second snapshot dir.
    """
    repo = repo.resolve()
    store = store.resolve()
    files: list[FileEntry] = []
    store_present = store.is_dir()
    if store_present:
        for src in sorted(store.iterdir(), key=lambda p: p.name):
            if not src.is_file():
                continue
            digest = _sha256(src)
            if digest is None:
                continue
            files.append(
                FileEntry("store", src.name, f"store/{src.name}", str(src), digest,
                          src.stat().st_size, src.name in DERIVED_SIDE_FILES)
            )
    repo_docs_present: list[str] = []
    for name in REPO_DOCS:
        src = repo / name
        if not src.is_file():
            continue
        digest = _sha256(src)
        if digest is None:
            continue
        repo_docs_present.append(name)
        files.append(FileEntry("repo", name, f"repo/{name}", str(src), digest, src.stat().st_size, False))
    return Manifest(
        manifest_version=MANIFEST_VERSION,
        created=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        repo=str(repo), store=str(store), snapshot_dir="(live)",
        store_present=store_present, repo_docs_present=repo_docs_present,
        marker=_read_marker(store / MARKER_FILE) if store_present else {},
        files=files,
    )


def _classify(origin: str, name: str) -> tuple[str, bool]:
    """(classification, expected) for a store/repo file. ``expected`` is True only for the Q4
    allowlisted derived side files — every fact/index/repo-doc mutation is, by contrast, a *claimed*
    write the dashboard must account for (so it is NOT auto-expected here)."""
    if origin == "repo":
        return "repo_doc", False
    if name in DERIVED_SIDE_FILES:
        return "allowed", True
    if name == "MEMORY.md":
        return "index", False
    return "fact", False


def diff(before: Manifest, after: Manifest, *, against_live: bool = False) -> DiffReport:
    """The deterministic mutation set between two manifests (BEFORE vs AFTER, or BEFORE vs live).

    One delta per (origin, name) whose content hash CHANGED (created / deleted / modified); an
    unchanged file is NOT a delta. Each delta is classified + tagged ``expected`` per the Q4
    allowlist. ``unexpected_store_mutations`` collects the store ``*.md`` / index changes that are
    NOT allowlisted derived-file writes — exactly the silent-mutation set the claim-vs-reality family
    escalates to HIGH (dashboard dishonesty). The marker delta (commit/timestamp advance) is surfaced
    separately so the family can assert the dream advanced the marker.
    """
    bidx = _index_by_key(before)
    aidx = _index_by_key(after)
    deltas: list[FileDelta] = []
    unexpected: list[str] = []

    def _d(s: str | None) -> str:  # M5: coerce a recorded-unreadable hash (None) to a display token, so the
        return "(unreadable)" if s is None else s  # str-typed FileDelta fields never carry None

    for key in sorted(set(bidx) | set(aidx)):
        origin, name = key
        b = bidx.get(key)
        a = aidx.get(key)
        if b and a and b.sha256 == a.sha256:
            continue  # unchanged
        if b and a:
            op, before_sha, after_sha = "modified", _d(b.sha256), _d(a.sha256)
            size_delta = a.size - b.size
        elif a and not b:
            op, before_sha, after_sha = "created", "", _d(a.sha256)
            size_delta = a.size
        else:  # b and not a (the key came from bidx|aidx and we didn't `continue`, so b is set)
            assert b is not None
            op, before_sha, after_sha = "deleted", _d(b.sha256), ""
            size_delta = -b.size
        classification, expected = _classify(origin, name)
        deltas.append(
            FileDelta(origin=origin, name=name, op=op, before_sha=before_sha, after_sha=after_sha,
                      size_delta=size_delta, classification=classification, expected=expected)
        )
        if origin == "store" and not expected:
            unexpected.append(name)

    before_marker = before.marker or {}
    after_marker = after.marker or {}
    advanced = (
        before_marker.get("commit", "") != after_marker.get("commit", "")
        or before_marker.get("timestamp", "") != after_marker.get("timestamp", "")
    )
    marker = MarkerDelta(advanced=advanced, before=before_marker, after=after_marker)

    summary = {
        "total": len(deltas),
        "created": sum(d.op == "created" for d in deltas),
        "modified": sum(d.op == "modified" for d in deltas),
        "deleted": sum(d.op == "deleted" for d in deltas),
        "unexpected_store": len(unexpected),
        "marker_advanced": int(advanced),
    }
    notes: list[str] = []
    if not before.store_present and after.store_present:
        notes.append("store did not exist BEFORE but exists AFTER (first dream on this repo)")
    return DiffReport(
        repo=after.repo or before.repo,
        store=after.store or before.store,
        before_dir=before.snapshot_dir,
        after_dir="" if against_live else after.snapshot_dir,
        against_live=against_live,
        deltas=deltas,
        marker=marker,
        unexpected_store_mutations=unexpected,
        summary=summary,
        notes=notes,
    )


# ─────────────────────────────── RESTORE ───────────────────────────────


@dataclass
class RestorePlan:
    repo: str
    store: str
    before_dir: str
    dry_run: bool
    writes: list[str]  # "store/<name>" / "repo/<name>" to (over)write from the snapshot
    deletes: list[str]  # live store files NOT in the snapshot → QUARANTINED (moved to reports/.restore-trash-*, not deleted) to reach BEFORE
    skipped: list[str]  # planned ops that could not be carried out (with a reason), in non-dry runs
    notes: list[str] = field(default_factory=list)


def restore(before: Manifest, repo: Path, store: Path, *, dry_run: bool = False) -> RestorePlan:
    """Write a BEFORE snapshot's files back over the live store + repo docs, returning the plan.

    Reaches the recorded BEFORE state exactly: every captured file is (over)written from the snapshot,
    and any live STORE file absent from the snapshot is QUARANTINED (M5: moved to a ``reports/.restore-trash-*``
    dir, NOT deleted — a dream-created fact is rolled out of the store but never destroyed, since the store
    alone can't distinguish a dream-added file from a concurrent-session or unreadable-at-capture one). Repo
    docs are only (over)written, never removed — a snapshot that didn't capture a repo doc (it was absent)
    leaves the live tree's absence intact. ``--dry-run`` reports the plan without touching disk. Restore is
    the default disposition for a pure ``--test`` (a beta-test leaves no mutation); ``--keep`` skips it.
    """
    repo = repo.resolve()
    store = store.resolve()
    snapdir = Path(before.snapshot_dir)
    writes: list[str] = []
    deletes: list[str] = []
    skipped: list[str] = []
    notes: list[str] = []

    snapshot_store_names = {fe.name for fe in before.files if fe.origin == "store"}

    # ── (over)write every captured file back to its source location ──
    for fe in before.files:
        src = snapdir / fe.rel
        dst = Path(fe.src)
        if not src.is_file():
            skipped.append(f"{fe.rel} (snapshot copy missing)")
            continue
        writes.append(fe.rel)
        if dry_run:
            continue
        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
        except OSError as e:
            skipped.append(f"{fe.rel} → {dst}: {type(e).__name__}: {e}")

    # ── QUARANTINE (M5: not delete) live STORE files the snapshot didn't have — roll back dream-created facts
    # WITHOUT destroying anything. "Live file ∉ snapshot" is, from the store alone, indistinguishable between
    # dream-added / concurrent-session-added / unreadable-at-capture; quarantine (move to the harness's reports
    # area) makes a wrong move RECOVERABLE while still reaching the BEFORE state (the extras are out of the store).
    trash_dir = REPORTS_DIR / f".restore-trash-{int(time.time())}"
    if store.is_dir():
        for live in sorted(store.iterdir(), key=lambda p: p.name):
            if not live.is_file():
                continue
            if live.name not in snapshot_store_names:
                deletes.append(f"store/{live.name}")
                if dry_run:
                    continue
                try:
                    trash_dir.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(live), str(trash_dir / live.name))
                except OSError as e:
                    skipped.append(f"quarantine store/{live.name}: {type(e).__name__}: {e}")
        if not dry_run and trash_dir.is_dir():
            notes.append(f"quarantined {len(deletes)} extra store file(s) → {trash_dir} (recoverable, NOT deleted)")
    elif before.store_present:
        notes.append(f"store {store} vanished since the snapshot — recreating from the snapshot files")
        if not dry_run:
            store.mkdir(parents=True, exist_ok=True)

    if not before.files:
        notes.append("snapshot captured no files — nothing to restore")
    return RestorePlan(
        repo=str(repo), store=str(store), before_dir=str(snapdir), dry_run=dry_run,
        writes=writes, deletes=deletes, skipped=skipped, notes=notes,
    )


# ─────────────────────────────── CLI ───────────────────────────────


def _print_manifest_human(m: Manifest) -> None:
    n_store = sum(fe.origin == "store" for fe in m.files)
    n_repo = sum(fe.origin == "repo" for fe in m.files)
    print(f"\n  SNAPSHOT · {Path(m.repo).name}")
    print(f"  dir:   {m.snapshot_dir}")
    print(f"  store: {m.store}" + ("" if m.store_present else "   [ABSENT — never-dreamed repo]"))
    print(f"  files: {n_store} store + {n_repo} repo ({'/'.join(m.repo_docs_present) or 'no repo docs'})")
    if m.marker:
        print(f"  marker: commit={m.marker.get('commit', '')[:12] or '∅'}  ts={m.marker.get('timestamp', '') or '∅'}")
    else:
        print("  marker: (none — no .consolidation-state.json)")
    for note in m.notes:
        print(f"    · {note}")
    print()


def _print_diff_human(d: DiffReport) -> None:
    print(f"\n  DIFF · {Path(d.repo).name}   ({'BEFORE → live' if d.against_live else 'BEFORE → AFTER'})")
    print(f"  before: {d.before_dir}")
    if not d.against_live:
        print(f"  after:  {d.after_dir}")
    s = d.summary
    print(f"  {s['total']} change(s): {s['created']} created · {s['modified']} modified · {s['deleted']} deleted "
          f"· {s['unexpected_store']} UNEXPECTED store mutation(s)")
    mk = d.marker
    print(f"  marker: {'ADVANCED' if mk.advanced else 'unchanged'}"
          + (f"  ({mk.before.get('commit', '')[:8]}→{mk.after.get('commit', '')[:8]})" if mk.advanced else ""))
    for delta in d.deltas:
        flag = "       " if delta.expected else "  UNEXP "
        print(f"   {flag}[{delta.op:8}] {delta.origin}/{delta.name}  ({delta.classification}, "
              f"Δ{delta.size_delta:+d}B)")
    if d.unexpected_store_mutations:
        print(f"\n  ⚠ UNEXPECTED store mutations (not on the derived-file allowlist): "
              f"{', '.join(d.unexpected_store_mutations)}")
        print("    → these are claimed-vs-real candidates: a store *.md/index change is HIGH "
              "unless the dashboard entries[]/budget delta accounts for it.")
    for note in d.notes:
        print(f"    · {note}")
    print()


def _print_restore_human(p: RestorePlan) -> None:
    verb = "WOULD restore" if p.dry_run else "RESTORED"
    print(f"\n  {verb} · {Path(p.repo).name}")
    print(f"  from:  {p.before_dir}")
    print(f"  {len(p.writes)} write(s), {len(p.deletes)} delete(s)" + (f", {len(p.skipped)} skipped" if p.skipped else ""))
    for w in p.writes:
        print(f"     write  {w}")
    for d in p.deletes:
        print(f"     delete {d}")
    for sk in p.skipped:
        print(f"     SKIP   {sk}")
    for note in p.notes:
        print(f"    · {note}")
    print()


def _cmd_snapshot(a: argparse.Namespace) -> int:
    repo = Path(a.repo).expanduser().resolve()
    store = Path(a.store).expanduser().resolve() if a.store else default_store(repo)
    out = Path(a.out).expanduser() if a.out else None
    m = snapshot(repo, store, out)
    if a.json:
        print(json.dumps(_manifest_to_dict(m), indent=2))
    else:
        _print_manifest_human(m)
    return 0


def _load_before(path_str: str) -> Manifest:
    snapdir = Path(path_str).expanduser().resolve()
    return load_manifest(snapdir)


def _cmd_diff(a: argparse.Namespace) -> int:
    try:
        before = _load_before(a.before)
    except (OSError, ValueError, json.JSONDecodeError) as e:
        print(f"ERROR: cannot load --before snapshot {a.before}: {type(e).__name__}: {e}", file=sys.stderr)
        return 2
    if a.after:
        try:
            after = _load_before(a.after)
        except (OSError, ValueError, json.JSONDecodeError) as e:
            print(f"ERROR: cannot load --after snapshot {a.after}: {type(e).__name__}: {e}", file=sys.stderr)
            return 2
        report = diff(before, after, against_live=False)
    else:
        repo = Path(a.repo).expanduser().resolve() if a.repo else Path(before.repo)
        store = Path(a.store).expanduser().resolve() if a.store else Path(before.store)
        after = _live_manifest(repo, store)
        report = diff(before, after, against_live=True)
    if a.json:
        print(json.dumps(asdict(report), indent=2))
    else:
        _print_diff_human(report)
    return 1 if report.unexpected_store_mutations else 0


def _cmd_restore(a: argparse.Namespace) -> int:
    try:
        before = _load_before(a.before)
    except (OSError, ValueError, json.JSONDecodeError) as e:
        print(f"ERROR: cannot load --before snapshot {a.before}: {type(e).__name__}: {e}", file=sys.stderr)
        return 2
    repo = Path(a.repo).expanduser().resolve() if a.repo else Path(before.repo)
    store = Path(a.store).expanduser().resolve() if a.store else Path(before.store)
    plan = restore(before, repo, store, dry_run=a.dry_run)
    if a.json:
        print(json.dumps(asdict(plan), indent=2))
    else:
        _print_restore_human(plan)
    if plan.skipped and not a.dry_run:
        return 2
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Snapshot / diff / restore the consolidate-memory store + repo always-loaded docs (SPEC §7)."
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("snapshot", help="capture the store + repo docs to reports/.snap-<ts>/")
    sp.add_argument("--repo", default=Path.cwd(), help="repo whose store is snapshotted (default: cwd)")
    sp.add_argument("--store", default=None, help="memory store dir (default: ~/.claude/projects/<slug>/memory)")
    sp.add_argument("--out", default=None, help="snapshot dir (default: reports/.snap-<ts>/)")
    sp.add_argument("--json", action="store_true", help="emit the manifest as JSON")
    sp.set_defaults(func=_cmd_snapshot)

    dp = sub.add_parser("diff", help="compare a BEFORE snapshot to an AFTER snapshot or the live state")
    dp.add_argument("--before", required=True, help="the BEFORE snapshot dir")
    dp.add_argument("--after", default=None, help="the AFTER snapshot dir (omit → diff against live state)")
    dp.add_argument("--repo", default=None, help="repo (default: the BEFORE manifest's repo) — used when --after omitted")
    dp.add_argument("--store", default=None, help="store dir (default: the BEFORE manifest's store) — used when --after omitted")
    dp.add_argument("--json", action="store_true", help="emit the diff report as JSON")
    dp.set_defaults(func=_cmd_diff)

    rp = sub.add_parser("restore", help="write a BEFORE snapshot back over the live store + repo docs")
    rp.add_argument("--before", required=True, help="the BEFORE snapshot dir to restore")
    rp.add_argument("--repo", default=None, help="repo (default: the BEFORE manifest's repo)")
    rp.add_argument("--store", default=None, help="store dir (default: the BEFORE manifest's store)")
    rp.add_argument("--dry-run", action="store_true", help="report the planned writes/deletes without touching disk")
    rp.add_argument("--json", action="store_true", help="emit the restore plan as JSON")
    rp.set_defaults(func=_cmd_restore)

    a = ap.parse_args(argv)
    return int(a.func(a))


if __name__ == "__main__":
    sys.exit(main())
