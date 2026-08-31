#!/usr/bin/env python3
"""SQLite control plane + fcntl locks + operation journal.

Markdown remains the source of fact content (outside plugin data). This module
is rebuildable operational state: registry, edges, revisions, tombstones,
journal, aggregates, migration. Stdlib sqlite3 only.
"""
from __future__ import annotations

import json
import os
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterator, Optional

from store_context import StoreContext, plugin_data_dir, config_root

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS projects (
    project_id TEXT PRIMARY KEY,
    display_name TEXT,
    current_root TEXT,
    git_common_dir TEXT,
    remote_fingerprint TEXT,
    profile_id TEXT,
    domain_id TEXT,
    native_memory_dir TEXT,
    session_dir TEXT,
    last_seen TEXT,
    capabilities TEXT,
    status TEXT
);
CREATE TABLE IF NOT EXISTS facts (
    fact_id TEXT PRIMARY KEY,
    stem TEXT,
    domain_id TEXT,
    canonical_path TEXT,
    revision TEXT,
    status TEXT,
    sensitivity TEXT
);
CREATE TABLE IF NOT EXISTS holders (
    fact_id TEXT,
    project_id TEXT,
    base_revision TEXT,
    canonical_revision TEXT,
    semantic_hash TEXT,
    PRIMARY KEY (fact_id, project_id)
);
CREATE TABLE IF NOT EXISTS tombstones (
    fact_id TEXT PRIMARY KEY,
    stem TEXT,
    domain_id TEXT,
    deleted_at TEXT,
    reason TEXT,
    replacement_id TEXT,
    grace_until TEXT
);
CREATE TABLE IF NOT EXISTS journal (
    op_id TEXT PRIMARY KEY,
    kind TEXT,
    payload TEXT,
    step TEXT,
    status TEXT,
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS usage_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT,
    day TEXT,
    sketch TEXT
);
CREATE TABLE IF NOT EXISTS workflow_sketches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT,
    day TEXT,
    sketch TEXT
);
CREATE TABLE IF NOT EXISTS migration_state (
    key TEXT PRIMARY KEY,
    value TEXT
);
CREATE TABLE IF NOT EXISTS authorized_pairs (
    src_domain TEXT,
    dst_domain TEXT,
    PRIMARY KEY (src_domain, dst_domain)
);
CREATE TABLE IF NOT EXISTS conflicts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fact_stem TEXT,
    project_id TEXT,
    action TEXT,
    local_hash TEXT,
    canonical_hash TEXT,
    created_at TEXT,
    resolved TEXT
);
"""

JOURNAL_STEPS = (
    "lock_domain",
    "lock_projects",
    "record_revisions",
    "journal_start",
    "prepare_temps",
    "verify_unchanged",
    "publish",
    "commit_registry",
    "journal_complete",
)


def db_path(ctx: Optional[StoreContext] = None, environ: Optional[dict] = None) -> Path:
    if ctx is not None:
        return ctx.plugin_data_dir / "control.sqlite"
    return plugin_data_dir(environ=environ) / "control.sqlite"


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA_SQL)
    _migrate_schema(conn)
    return conn


def _migrate_schema(conn: sqlite3.Connection) -> None:
    """Additive columns for DBs created before session_dir existed."""
    cols = {str(r[1]) for r in conn.execute("PRAGMA table_info(projects)").fetchall()}
    if "session_dir" not in cols:
        conn.execute("ALTER TABLE projects ADD COLUMN session_dir TEXT")
        conn.commit()


def iter_registered_projects(conn: sqlite3.Connection) -> list:
    try:
        rows = conn.execute(
            "SELECT project_id, display_name, native_memory_dir, "
            "COALESCE(session_dir, '') AS session_dir, COALESCE(status, '') AS status "
            "FROM projects"
        ).fetchall()
    except sqlite3.OperationalError:
        return []
    return [dict(r) for r in rows]


def get_migration_mode(conn: sqlite3.Connection) -> str:
    row = conn.execute("SELECT value FROM migration_state WHERE key='mode'").fetchone()
    if row and row["value"]:
        return str(row["value"])
    # Infer: if any tombstone/fact exists we're in whatever was written; else dual-read.
    return "dual-read"


def set_migration_mode(conn: sqlite3.Connection, mode: str) -> None:
    conn.execute(
        "INSERT INTO migration_state(key, value) VALUES('mode', ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (mode,),
    )


def upsert_project(conn: sqlite3.Connection, ctx: StoreContext, capabilities: Optional[list] = None) -> None:
    caps = json.dumps(capabilities or [])
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    conn.execute(
        "INSERT INTO projects(project_id, display_name, current_root, git_common_dir, "
        "remote_fingerprint, profile_id, domain_id, native_memory_dir, session_dir, last_seen, "
        "capabilities, status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(project_id) DO UPDATE SET display_name=excluded.display_name, "
        "current_root=excluded.current_root, git_common_dir=excluded.git_common_dir, "
        "native_memory_dir=excluded.native_memory_dir, session_dir=excluded.session_dir, "
        "last_seen=excluded.last_seen, "
        "capabilities=excluded.capabilities, domain_id=excluded.domain_id, "
        "profile_id=excluded.profile_id, remote_fingerprint=excluded.remote_fingerprint",
        (ctx.project_id, ctx.display_name, str(ctx.project_root),
         str(ctx.git_common_dir) if ctx.git_common_dir else "",
         ctx.remote_fingerprint, ctx.profile_id, ctx.domain_id,
         str(ctx.native_memory_dir), str(ctx.session_dir), now, caps, "active"),
    )


class FileLock:
    def __init__(self, path: Path):
        self.path = path
        self._fd: Optional[Any] = None

    def acquire(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd = open(self.path, "a+")
        self._fd = fd
        try:
            import fcntl
            fcntl.flock(fd.fileno(), fcntl.LOCK_EX)
        except ImportError:
            pass  # non-POSIX: best-effort (Phase 6 soak)

    def release(self) -> None:
        if self._fd is None:
            return
        try:
            import fcntl
            fcntl.flock(self._fd.fileno(), fcntl.LOCK_UN)
        except ImportError:
            pass
        try:
            self._fd.close()
        except OSError:
            pass
        self._fd = None

    def __enter__(self) -> "FileLock":
        self.acquire()
        return self

    def __exit__(self, *exc) -> None:
        self.release()


def lock_dir(ctx: StoreContext) -> Path:
    return ctx.plugin_data_dir / "locks"


def acquire_mutation_locks(ctx: StoreContext, project_ids: list) -> list:
    """Domain lock, then project locks in sorted ID order. Returns acquired locks."""
    locks = []
    dlock = FileLock(lock_dir(ctx) / f"domain-{ctx.domain_id or 'unknown'}.lock")
    dlock.acquire()
    locks.append(dlock)
    glob = FileLock(lock_dir(ctx) / "global.lock")
    glob.acquire()
    locks.append(glob)
    for pid in sorted(set(project_ids)):
        pl = FileLock(lock_dir(ctx) / f"project-{pid}.lock")
        pl.acquire()
        locks.append(pl)
    return locks


def release_locks(locks: list) -> None:
    for lk in reversed(locks):
        lk.release()


def journal_insert(conn: sqlite3.Connection, kind: str, payload: dict, step: str) -> str:
    op_id = "op_" + uuid.uuid4().hex[:16]
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    conn.execute(
        "INSERT INTO journal(op_id, kind, payload, step, status, created_at) "
        "VALUES (?,?,?,?,?,?)",
        (op_id, kind, json.dumps(payload, sort_keys=True), step, "pending", now),
    )
    conn.commit()
    return op_id


def journal_step(conn: sqlite3.Connection, op_id: str, step: str, status: str = "pending") -> None:
    conn.execute("UPDATE journal SET step=?, status=? WHERE op_id=?", (step, status, op_id))
    conn.commit()


def pending_ops(conn: sqlite3.Connection) -> list:
    rows = conn.execute(
        "SELECT op_id, kind, payload, step, status FROM journal WHERE status!='complete'"
    ).fetchall()
    return [dict(r) for r in rows]


def _file_hash(path: Path) -> Optional[str]:
    import hashlib
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def _publish_temps(publishes: list, deletes: Optional[list] = None) -> int:
    """os.replace leftover same-directory temps, then apply deletes. Idempotent."""
    n = 0
    for item in publishes:
        tmp, dest = Path(item["tmp"]), Path(item["dest"])
        if tmp.exists():
            dest.parent.mkdir(parents=True, exist_ok=True)
            os.replace(str(tmp), str(dest))
            n += 1
        elif dest.exists():
            n += 1  # already published
    for d in deletes or []:
        Path(d).unlink(missing_ok=True)
    return n


def recover_pending(conn: sqlite3.Connection, replay: Optional[Callable] = None,
                    ctx: Optional[StoreContext] = None) -> list:
    """Publish leftover temps (and deletes), then replay incomplete canonical upserts.

    Never marks complete until leftover temps have been published (or were already
    dest-present). A pending op with no temps and no replayable payload is completed
    only when there is nothing left to land — an early crash before prepare_temps.
    """
    recovered = []
    for op in pending_ops(conn):
        payload = json.loads(op["payload"] or "{}")
        publishes = payload.get("publishes") or []
        deletes = payload.get("deletes") or []
        if publishes:
            _publish_temps(publishes, deletes)
            missing = [item for item in publishes if not Path(item["dest"]).exists()]
            if missing:
                continue  # leave pending — dests did not land
        if replay is not None:
            replay(op["kind"], payload, op["step"])
        elif (ctx is not None and payload.get("stem") and payload.get("text")
              and str(op["kind"]) == "canonical-upsert"):
            from canonical_ingress import upsert
            origin = payload.get("origin") or ""
            origin_del = payload.get("origin_delete") or ""
            upsert(ctx, payload["stem"], payload["text"],
                   origin_local=Path(origin) if origin else None,
                   origin_delete=Path(origin_del) if origin_del else None,
                   preserve_canonical=bool(payload.get("preserve_canonical")),
                   create_only=bool(payload.get("create_only")),
                   skip_recover=True)
        journal_step(conn, op["op_id"], "journal_complete", "complete")
        recovered.append(op["op_id"])
    conn.commit()
    return recovered


def transact(ctx: StoreContext, kind: str, payload: dict, mutate: Callable,
             *, extra_project_ids: Optional[list] = None,
             crash_after: Optional[str] = None,
             expected_revisions: Optional[dict] = None,
             skip_recover: bool = False) -> dict:
    """JOURNAL_STEPS mutation. `crash_after=NAME` means the named step completed, then stop.

    `mutate(conn, temps)` fills temps[dest_path] = text and may return {"deletes": [path]}.
    This function writes same-directory temps, verifies expected_revisions hashes, os.replace,
    then applies deletes.
    """
    from store_context import WriteRefused, assert_writable
    assert_writable(ctx)
    crash = crash_after or os.environ.get("CM_CRASH_AFTER") or ""
    dbp = db_path(ctx)
    conn = connect(dbp)
    recovered: list = []
    if not skip_recover:
        recovered = recover_pending(conn, ctx=ctx)
    pids = [ctx.project_id] + list(extra_project_ids or [])
    locks = acquire_mutation_locks(ctx, pids)
    op_id: Optional[str] = None
    temps: dict = {}
    try:
        def _maybe_crash(step: str) -> None:
            if crash == step:
                if op_id:
                    journal_step(conn, op_id, step, "pending")
                raise CrashSimulated(step)

        _maybe_crash("lock_domain")
        _maybe_crash("lock_projects")
        snaps = {}
        for p in (expected_revisions or {}):
            snaps[p] = _file_hash(Path(p))
        _maybe_crash("record_revisions")
        op_id = journal_insert(conn, kind, payload, "journal_start")
        _maybe_crash("journal_start")
        upsert_project(conn, ctx)
        result = mutate(conn, temps)
        if not isinstance(result, dict):
            result = {"value": result}
        deletes = list(result.get("deletes") or [])
        publishes = []
        for dest_s, content in temps.items():
            dest = Path(dest_s)
            dest.parent.mkdir(parents=True, exist_ok=True)
            tmp = dest.with_suffix(dest.suffix + f".tmp{os.getpid()}")
            tmp.write_text(content if content.endswith("\n") else content + "\n", encoding="utf-8")
            publishes.append({"tmp": str(tmp), "dest": str(dest)})
        payload = dict(payload)
        payload["publishes"] = publishes
        payload["deletes"] = deletes
        conn.execute("UPDATE journal SET payload=?, step=? WHERE op_id=?",
                     (json.dumps(payload, sort_keys=True), "prepare_temps", op_id))
        conn.commit()
        _maybe_crash("prepare_temps")
        for p, h in snaps.items():
            if _file_hash(Path(p)) != h:
                for item in publishes:
                    Path(item["tmp"]).unlink(missing_ok=True)
                raise WriteRefused("source changed during transaction: " + p)
        journal_step(conn, op_id, "verify_unchanged", "pending")
        _maybe_crash("verify_unchanged")
        _publish_temps(publishes, deletes)
        journal_step(conn, op_id, "publish", "pending")
        _maybe_crash("publish")
        conn.commit()
        _maybe_crash("commit_registry")
        journal_step(conn, op_id, "journal_complete", "complete")
        _maybe_crash("journal_complete")
        return {"ok": True, "op_id": op_id, "recovered": recovered, "result": result,
                "expected_revisions": snaps}
    finally:
        release_locks(locks)
        conn.close()


class CrashSimulated(RuntimeError):
    """Test-only: mutation stopped after a named journal step."""


def fact_id_for(domain: str, stem: str) -> str:
    import hashlib
    return "f_" + hashlib.sha256(f"{SCHEMA_SQL[:1]}2|{domain}|{stem}".encode()).hexdigest()[:24]


# Stable fact IDs shouldn't depend on SCHEMA_SQL snippet — use schema version.
def stable_fact_id(domain: str, stem: str, schema_version: str = "2") -> str:
    import hashlib
    return "f_" + hashlib.sha256(f"{schema_version}|{domain}|{stem}".encode("utf-8")).hexdigest()[:24]


def record_holder(conn: sqlite3.Connection, fact_id: str, project_id: str,
                  base_rev: str, canon_rev: str, sem: str) -> None:
    conn.execute(
        "INSERT INTO holders(fact_id, project_id, base_revision, canonical_revision, semantic_hash) "
        "VALUES (?,?,?,?,?) ON CONFLICT(fact_id, project_id) DO UPDATE SET "
        "base_revision=excluded.base_revision, canonical_revision=excluded.canonical_revision, "
        "semantic_hash=excluded.semantic_hash",
        (fact_id, project_id, base_rev, canon_rev, sem),
    )


def record_conflict(conn: sqlite3.Connection, stem: str, project_id: str, decision: dict) -> None:
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    conn.execute(
        "INSERT INTO conflicts(fact_stem, project_id, action, local_hash, canonical_hash, "
        "created_at, resolved) VALUES (?,?,?,?,?,?,?)",
        (stem, project_id, decision.get("action"), decision.get("local"),
         decision.get("canonical"), now, ""),
    )


def list_conflicts(conn: sqlite3.Connection, project_id: Optional[str] = None) -> list:
    if project_id:
        rows = conn.execute(
            "SELECT * FROM conflicts WHERE resolved='' AND project_id=?", (project_id,)
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM conflicts WHERE resolved=''").fetchall()
    return [dict(r) for r in rows]


def write_tombstone(conn: sqlite3.Connection, fact_id: str, stem: str, domain: str,
                    reason: str, replacement_id: str = "", grace_until: str = "") -> None:
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    conn.execute(
        "INSERT INTO tombstones(fact_id, stem, domain_id, deleted_at, reason, "
        "replacement_id, grace_until) VALUES (?,?,?,?,?,?,?) "
        "ON CONFLICT(fact_id) DO UPDATE SET deleted_at=excluded.deleted_at, "
        "reason=excluded.reason, replacement_id=excluded.replacement_id, "
        "grace_until=excluded.grace_until",
        (fact_id, stem, domain, now, reason, replacement_id, grace_until),
    )
    conn.execute("UPDATE facts SET status='tombstoned' WHERE fact_id=?", (fact_id,))


def is_tombstoned(conn: sqlite3.Connection, stem: str, domain: str = "") -> bool:
    if domain:
        row = conn.execute(
            "SELECT 1 FROM tombstones WHERE stem=? AND domain_id=?", (stem, domain)
        ).fetchone()
    else:
        row = conn.execute("SELECT 1 FROM tombstones WHERE stem=?", (stem,)).fetchone()
    return row is not None
