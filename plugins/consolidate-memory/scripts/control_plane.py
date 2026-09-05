#!/usr/bin/env python3
"""SQLite control plane + fcntl locks + operation journal.

Markdown remains the source of fact content (outside plugin data). This module
is rebuildable operational state: registry, edges, revisions, tombstones,
journal, aggregates, migration. New journal rows store hashes and recovery
paths, not fact bodies (ADR 017). Stdlib sqlite3 only.
"""
from __future__ import annotations

import calendar
import errno
import hashlib
import json
import os
import sqlite3
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterator, Optional, Tuple

from store_context import StoreContext, WriteRefused, plugin_data_dir, config_root

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
CREATE TABLE IF NOT EXISTS migration_state (
    key TEXT PRIMARY KEY,
    value TEXT
);
CREATE TABLE IF NOT EXISTS project_aliases (
    alias_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS conflicts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fact_stem TEXT,
    project_id TEXT,
    action TEXT,
    local_hash TEXT,
    canonical_hash TEXT,
    created_at TEXT,
    resolved TEXT,
    domain_id TEXT DEFAULT '',
    fact_id TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS domains (
    domain_id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    updated_at TEXT
);
CREATE TABLE IF NOT EXISTS project_usage_windows (
    project_id TEXT NOT NULL,
    cycle_id TEXT NOT NULL,
    sequence INTEGER NOT NULL,
    started_at TEXT NOT NULL,
    probative INTEGER NOT NULL,
    PRIMARY KEY (project_id, cycle_id),
    UNIQUE (project_id, sequence)
);
CREATE TABLE IF NOT EXISTS native_store_grants (
    normalized_path TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    adopted_nonempty INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS groups (
    group_id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    domain_id TEXT NOT NULL,
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS group_members (
    group_id TEXT NOT NULL,
    project_id TEXT NOT NULL,
    granted_at TEXT,
    PRIMARY KEY (group_id, project_id)
);
CREATE INDEX IF NOT EXISTS idx_facts_domain_stem ON facts(domain_id, stem);
CREATE INDEX IF NOT EXISTS idx_holders_project ON holders(project_id);
CREATE INDEX IF NOT EXISTS idx_tombstones_domain ON tombstones(domain_id);
"""

JOURNAL_STEPS = (
    "lock_domain",
    "lock_projects",
    "record_revisions",
    "journal_start",
    "prepare_temps",
    "verify_unchanged",
    "after_trash",
    "after_dests",
    "publish",
    "commit_registry",
    "cleanup_pending",
    "journal_complete",
)
JOURNAL_CLEANUP_PENDING = "committed-cleanup-pending"
# v4: drop the dormant hook-sketch tables (usage_events/workflow_sketches).
# v5: the group-scopes layer — groups + group_members (v0.4.10 spec).
REGISTRY_USER_VERSION = 5
JOURNAL_USER_VERSION = 1
JOURNAL_RECEIPT_DAYS = 90
# v0.4.0 review: receipt-collapse bounds PAYLOAD size, never ROW count — a row
# cap deletes the oldest terminal (complete/abandoned) rows when exceeded, run
# from journal_cleanup (the one locked place both DBs are open).
JOURNAL_MAX_ROWS = 50_000
JOURNAL_TABLES = frozenset({"journal", "journal_metadata"})
JOURNAL_BLOCKING = frozenset({"failed", "conflicted"})
# Filesystem preimages for these statuses are live complete-old state.
# cm journal cleanup must not unlink them.
JOURNAL_HOLD_FS = frozenset({"pending", "failed", "conflicted"})
DOMAIN_LIFECYCLE_KINDS = frozenset({
    "domain-deleting", "domain-deleted", "purge-domain", "purge-all-plugin-data",
    "domain-transition", "purge-resume", "purge-cancel",
})
JOURNAL_BODY_KEYS = ("text", "body", "old_text", "bytes_b64", "old_bytes_b64")
RECOVERY_TTL_SEC = 24 * 60 * 60

class CrashSimulated(RuntimeError):
    """Test-only: mutation stopped after a named journal step."""


ABSENT = "ABSENT"
MARKER_FILE = ".consolidation-state.json"


@dataclass(frozen=True)
class FileSnapshot:
    """Plan-time bytes of one path. Missing paths are ABSENT, never inferred later."""

    path: Path
    exists: bool
    data: Optional[bytes]
    sha256: str
    mode: Optional[int]


def read_snapshot(path: Path) -> FileSnapshot:
    """Read path once. Missing → exists=False, sha256=ABSENT. Unreadable → WriteRefused."""
    try:
        data = path.read_bytes()
        mode = path.stat().st_mode & 0o7777
    except FileNotFoundError:
        return FileSnapshot(path=path, exists=False, data=None, sha256=ABSENT, mode=None)
    except OSError as e:
        raise WriteRefused("cannot snapshot %s: %s" % (path, e.__class__.__name__))
    return FileSnapshot(
        path=path,
        exists=True,
        data=data,
        sha256=hashlib.sha256(data).hexdigest(),
        mode=mode,
    )


def fsync_dir(path: Path) -> None:
    """fsync a directory so the rename/unlink is durable across a process crash."""
    flags = os.O_RDONLY
    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY
    try:
        fd = os.open(str(path), flags)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def atomic_write_bytes(path: Path, data: bytes, *, mode: int = 0o600) -> str:
    """Write `data` via tmp+replace, fsync file and parent dir. Returns sha256."""
    path.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(data).hexdigest()
    tmp = path.with_name(path.name + ".tmp-" + uuid.uuid4().hex[:12])
    fd = os.open(str(tmp), os.O_CREAT | os.O_EXCL | os.O_WRONLY, mode)
    try:
        try:
            _write_fully(fd, data)
        finally:
            os.close(fd)
        try:
            os.chmod(str(tmp), mode)
        except OSError:
            pass
        os.replace(str(tmp), str(path))
        fsync_dir(path.parent)
    except Exception:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise
    return digest


def update_project_state(ctx: StoreContext, mutator: Callable,
                         no_mint: bool = False) -> dict:
    """Merge native `.consolidation-state.json` under the project lock.

    `mutator(state: dict, snap: FileSnapshot) -> dict`. Missing marker → empty
    object (callers that require an existing marker raise WriteRefused).
    `no_mint` (v0.4.2 L3 review): a missing marker is a NO-OP instead of a
    fresh write — the check and the snapshot read share the same locked
    section, closing the TOCTOU where an absent store got minted between a
    caller's is_file() guard and this function's write.
    Returns {status: changed|noop, revision, state, changed}.

    v0.4.0 review: the hash-CAS `expected_revision` branch was dead (no caller
    ever passed it) — serialization under the flock is the actual safety, so
    the dead param is removed rather than left as an untested promise.
    """
    marker = ctx.native_memory_dir / MARKER_FILE
    require_interprocess_lock()
    locks = acquire_mutation_locks(ctx, [ctx.project_id])
    try:
        snap = read_snapshot(marker)
        if snap.exists:
            try:
                parsed = json.loads((snap.data or b"").decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
                raise WriteRefused("unreadable marker")
            if not isinstance(parsed, dict):
                raise WriteRefused("marker is not an object")
            state = parsed
        elif no_mint:
            return {"status": "noop", "revision": "", "state": {}, "changed": False}
        else:
            state = {}
        new_state = mutator(dict(state), snap)
        if not isinstance(new_state, dict):
            raise WriteRefused("marker mutator must return an object")
        text = json.dumps(new_state, indent=2) + "\n"
        data = text.encode("utf-8")
        new_hash = hashlib.sha256(data).hexdigest()
        if snap.exists and snap.data == data:
            return {"status": "noop", "revision": snap.sha256,
                    "state": new_state, "changed": False}
        ctx.native_memory_dir.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(str(ctx.native_memory_dir), 0o700)
        except OSError:
            pass
        atomic_write_bytes(marker, data)
        return {"status": "changed", "revision": new_hash,
                "state": new_state, "changed": True}
    finally:
        release_locks(locks)


def record_usage_window(ctx: StoreContext, *, cycle_id: str, started_at: str,
                        probative: bool) -> dict:
    """Idempotent insert of one persisted cycle's usage window. Returns sequence."""
    cid = str(cycle_id or "").strip()
    if not cid:
        raise WriteRefused("usage window requires a cycle_id")
    started = str(started_at or "").strip() or cid
    conn = connect(db_path(ctx))
    try:
        row = conn.execute(
            "SELECT sequence FROM project_usage_windows "
            "WHERE project_id=? AND cycle_id=?",
            (ctx.project_id, cid),
        ).fetchone()
        if row is not None:
            return {"sequence": int(row["sequence"]), "inserted": False,
                    "cycle_id": cid}
        # v0.4.0 review (R128 concurrency): SELECT-MAX-then-INSERT raced two
        # concurrent recorders (both read the same MAX → UNIQUE(project_id,
        # sequence) violated → the loser's window silently dropped, delaying
        # refire past five). Retry on contention instead of dropping the window.
        for _attempt in range(5):
            cur = conn.execute(
                "SELECT COALESCE(MAX(sequence), 0) AS m FROM project_usage_windows "
                "WHERE project_id=?",
                (ctx.project_id,),
            ).fetchone()
            seq = int(cur["m"] if cur is not None else 0) + 1
            try:
                conn.execute(
                    "INSERT INTO project_usage_windows("
                    "project_id, cycle_id, sequence, started_at, probative) "
                    "VALUES (?,?,?,?,?)",
                    (ctx.project_id, cid, seq, started, 1 if probative else 0),
                )
                conn.commit()
                return {"sequence": seq, "inserted": True, "cycle_id": cid}
            except sqlite3.IntegrityError:
                conn.rollback()
                # review fix: the PK clash (UNIQUE project_id+cycle_id) means a
                # concurrent persist of the SAME cycle already recorded it — return
                # the existing sequence (the idempotent-return contract) instead of
                # burning all five attempts into a WriteRefused
                row = conn.execute(
                    "SELECT sequence FROM project_usage_windows "
                    "WHERE project_id=? AND cycle_id=?",
                    (ctx.project_id, cid)).fetchone()
                if row is not None:
                    return {"sequence": int(row["sequence"]), "inserted": False,
                            "cycle_id": cid}
            except sqlite3.OperationalError:
                # a busy DB is contention, not corruption — roll back and retry
                conn.rollback()
        raise WriteRefused("usage-window sequence contention (5 attempts)")
    finally:
        conn.close()


def usage_window_clock(ctx: StoreContext) -> dict:
    """Monotonic usage-window clock for this project. Empty if no registry."""
    empty: dict = {"sequence": 0, "probative": 0, "starts": [], "rows": []}
    conn = connect_if_exists(db_path(ctx))
    if conn is None:
        return empty
    try:
        try:
            rows = conn.execute(
                "SELECT sequence, started_at, probative FROM project_usage_windows "
                "WHERE project_id=? ORDER BY sequence",
                (ctx.project_id,),
            ).fetchall()
        except sqlite3.OperationalError:
            return empty
        out_rows = [dict(r) for r in rows]
        seq = max((int(r["sequence"]) for r in out_rows), default=0)
        starts: list = []
        n_prob = 0
        for r in out_rows:
            if int(r.get("probative") or 0):
                n_prob += 1
                ts = str(r.get("started_at") or "")
                try:
                    from memory_status import _parse_ts
                    dt = _parse_ts(ts)
                    if dt is not None:
                        starts.append(dt.timestamp())
                except Exception:
                    pass
        return {"sequence": seq, "probative": n_prob, "starts": starts,
                "rows": out_rows}
    finally:
        conn.close()


def count_probative_after(ctx: StoreContext, sequence: int) -> "Optional[int]":
    conn = connect_if_exists(db_path(ctx))
    if conn is None:
        # review fix: returning 0 here minted a real int that the sequence branch of
        # _justify_remaining consumed as "zero later probative windows" — a stamp on a
        # registry-less store then suppressed FOREVER (sequence+n_after=0 wins every
        # time and the at-fallback is unreachable). None engages the fallback.
        return None
    try:
        try:
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM project_usage_windows "
                "WHERE project_id=? AND sequence>? AND probative=1",
                (ctx.project_id, int(sequence)),
            ).fetchone()
        except sqlite3.OperationalError:
            return 0
        return int(row["n"] if row is not None else 0)
    finally:
        conn.close()


REGISTRY_OP_KINDS = frozenset({
    "project_upsert", "project_domain_change", "fact_upsert", "fact_status_change",
    "fact_delete", "holder_upsert", "holder_delete", "tombstone_upsert",
    "tombstone_delete", "conflict_upsert", "conflict_resolve", "migration_state_set",
    "project_alias", "project_rebind", "domain_status_set",
    "group_upsert", "group_delete", "group_member_add", "group_member_remove",
})


def db_path(ctx: Optional[StoreContext] = None, environ: Optional[dict] = None) -> Path:
    if ctx is not None:
        return ctx.plugin_data_dir / "control.sqlite"
    return plugin_data_dir(environ=environ) / "control.sqlite"


def journal_db_path(ctx: Optional[StoreContext] = None, environ: Optional[dict] = None) -> Path:
    if ctx is not None:
        return ctx.plugin_data_dir / "journal.sqlite"
    return plugin_data_dir(environ=environ) / "journal.sqlite"


JOURNAL_ONLY_SQL = """
CREATE TABLE IF NOT EXISTS journal (
    op_id TEXT PRIMARY KEY,
    kind TEXT,
    payload TEXT,
    step TEXT,
    status TEXT,
    created_at TEXT,
    completed_at TEXT
);
CREATE TABLE IF NOT EXISTS journal_metadata (
    key TEXT PRIMARY KEY,
    value TEXT
);
CREATE INDEX IF NOT EXISTS idx_journal_created_op ON journal(created_at, op_id);
"""


def connect_base(path: Path) -> sqlite3.Connection:
    """Open SQLite with WAL/FK/chmod. No DDL, no schema lock."""
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(str(path.parent), 0o700)
    except OSError:
        pass
    conn = sqlite3.connect(str(path))
    try:
        os.chmod(str(path), 0o600)
    except OSError:
        pass
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        conn.execute("PRAGMA journal_mode=WAL")
    except sqlite3.Error:
        pass
    return conn


def _schema_lock_for(db_path: Path) -> "FileLock":
    return FileLock(db_path.parent / "locks" / "schema.lock")


def _sqlite_user_version(conn: sqlite3.Connection) -> int:
    row = conn.execute("PRAGMA user_version").fetchone()
    return int(row[0] if row is not None else 0)


def _set_user_version(conn: sqlite3.Connection, n: int) -> None:
    conn.execute("PRAGMA user_version = %d" % int(n))
    conn.commit()


def _has_registry_tables(conn: sqlite3.Connection) -> bool:
    names = {str(r[0]) for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    return "projects" in names and "facts" in names and "holders" in names


def connect_registry(path: Path) -> sqlite3.Connection:
    """Writable control.sqlite: schema lock → user_version → one migration."""
    path = Path(path)
    lock = _schema_lock_for(path)
    lock.acquire()
    try:
        conn = connect_base(path)
        ver = _sqlite_user_version(conn)
        if ver > REGISTRY_USER_VERSION:
            conn.close()
            raise WriteRefused(
                "control.sqlite schema version %s is newer than this plugin (%s)"
                % (ver, REGISTRY_USER_VERSION))
        if ver < REGISTRY_USER_VERSION:
            if ver == 0 and not _has_registry_tables(conn):
                conn.executescript(SCHEMA_SQL)
            _migrate_schema(conn)
            _ingest_json_grants(conn, path.parent)
            _set_user_version(conn, REGISTRY_USER_VERSION)
        return conn
    finally:
        lock.release()


def connect(path: Path) -> sqlite3.Connection:
    """Registry connection (backward-compatible name)."""
    return connect_registry(path)


def connect_journal(ctx: Optional[StoreContext] = None,
                    environ: Optional[dict] = None) -> sqlite3.Connection:
    """journal.sqlite: journal + journal_metadata only. Never registry DDL."""
    path = journal_db_path(ctx, environ)
    lock = _schema_lock_for(path)
    lock.acquire()
    try:
        conn = connect_base(path)
        conn.executescript(JOURNAL_ONLY_SQL)
        _migrate_journal_schema(conn)
        ver = _sqlite_user_version(conn)
        if ver > JOURNAL_USER_VERSION:
            # Pre-split code ran connect() (registry DDL + user_version) on this
            # file. Ignore leftover registry tables; keep serving the journal.
            if "journal" not in journal_table_names(conn):
                conn.close()
                raise WriteRefused(
                    "journal.sqlite schema version %s is newer than this plugin (%s)"
                    % (ver, JOURNAL_USER_VERSION))
            return conn
        if ver < JOURNAL_USER_VERSION:
            _set_user_version(conn, JOURNAL_USER_VERSION)
        return conn
    finally:
        lock.release()


def journal_table_names(conn: sqlite3.Connection) -> set:
    return {str(r[0]) for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' "
        "AND name NOT LIKE 'sqlite_%'")}


def _migrate_journal_schema(conn: sqlite3.Connection) -> None:
    # v0.4.0 (v3→v4): pre-split journal.sqlite files ran the full registry DDL
    # and may physically carry the dormant hook-sketch tables — drop them here
    # too (idempotent; this runs on every journal open).
    conn.execute("DROP TABLE IF EXISTS usage_events")
    conn.execute("DROP TABLE IF EXISTS workflow_sketches")
    cols = {str(r[1]) for r in conn.execute("PRAGMA table_info(journal)").fetchall()}
    if cols and "completed_at" not in cols:
        conn.execute("ALTER TABLE journal ADD COLUMN completed_at TEXT")
        conn.commit()
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_journal_status_created "
        "ON journal(status, created_at)")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_journal_created_op "
        "ON journal(created_at, op_id)")
    conn.commit()


def connect_readonly(path: Path) -> sqlite3.Connection:
    """Open an existing control DB read-only. Never creates, never migrates.

    URI `mode=ro` is the actual guarantee — `connect_if_exists` used to call
    `connect()`, which mkdir'd, ran SCHEMA_SQL, and enabled WAL.
    """
    resolved = path.resolve()
    conn = sqlite3.connect(resolved.as_uri() + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def connect_if_exists(path: Path) -> Optional[sqlite3.Connection]:
    """Open the control plane only when the DB file already exists, read-only.

    Read-only entry points (`--list`, `cm conflicts`, migrate --plan, doctor)
    must not mint or migrate control.sqlite.
    """
    try:
        if not path.is_file():
            return None
    except OSError:
        return None
    try:
        return connect_readonly(path)
    except (sqlite3.Error, OSError):
        return None


def classify_registry(path: Path) -> Tuple[str, str]:
    """Return (state, error) without creating or migrating the file.

    States: absent | healthy | locked | corrupt | permission-denied | incompatible.
    """
    try:
        if not path.is_file():
            return "absent", ""
    except OSError as e:
        return "permission-denied", str(e)
    try:
        if not os.access(str(path), os.R_OK):
            return "permission-denied", "not readable"
    except OSError as e:
        return "permission-denied", str(e)
    try:
        conn = connect_readonly(path)
    except sqlite3.OperationalError as e:
        msg = str(e).lower()
        if "locked" in msg:
            return "locked", str(e)
        if "unable to open" in msg or "authorization" in msg or "denied" in msg:
            return "permission-denied", str(e)
        return "corrupt", str(e)
    except sqlite3.DatabaseError as e:
        return "corrupt", str(e)
    except OSError as e:
        err = getattr(e, "errno", None)
        if err in (13, 1):
            return "permission-denied", str(e)
        return "corrupt", str(e)
    try:
        tables = {str(r[0]) for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        conn.close()
    except sqlite3.Error as e:
        return "corrupt", str(e)
    needed = {"projects", "facts", "holders", "tombstones", "migration_state"}
    missing = needed - tables
    if missing:
        return "incompatible", "missing tables: " + ",".join(sorted(missing))
    return "healthy", ""


def assert_mutation_allowed(ctx: "StoreContext") -> None:
    """Refuse destructive ops when StoreContext is ambiguous or the registry is unhealthy.

    An absent registry is fine (first enroll/upsert will create it). A present but
    locked/corrupt/unreadable/incompatible control.sqlite is not a security decision
    we fail open on.
    """
    from store_context import WriteRefused, assert_writable
    assert_writable(ctx)
    path = db_path(ctx)
    state, err = classify_registry(path)
    if state in ("absent", "healthy"):
        return
    detail = f" ({err})" if err else ""
    raise WriteRefused(f"refusing mutation: registry is {state}{detail}")


def migration_mode_readonly(ctx: Optional[StoreContext] = None,
                            environ: Optional[dict] = None) -> str:
    """Read migration mode without creating the DB (default dual-read)."""
    path = db_path(ctx, environ)
    conn = connect_if_exists(path)
    if conn is None:
        return "dual-read"
    try:
        return get_migration_mode(conn)
    finally:
        conn.close()


def _migrate_schema(conn: sqlite3.Connection) -> None:
    """v3→v4 drops the dormant hook-sketch tables; earlier steps add columns.

    The DROP pair runs for every `ver < REGISTRY_USER_VERSION` DB — an existing
    install loses its empty `usage_events`/`workflow_sketches` tables, and a
    fresh DB never had them (SCHEMA_SQL no longer creates them), so the DROPs
    are no-ops there.
    """
    # v0.4.0 (v3→v4): the hook-sketch feature was removed — drop its dormant
    # tables on every existing install.
    conn.execute("DROP TABLE IF EXISTS usage_events")
    conn.execute("DROP TABLE IF EXISTS workflow_sketches")
    conn.commit()
    cols = {str(r[1]) for r in conn.execute("PRAGMA table_info(projects)").fetchall()}
    if "session_dir" not in cols:
        conn.execute("ALTER TABLE projects ADD COLUMN session_dir TEXT")
        conn.commit()
    conn.execute(
        "CREATE TABLE IF NOT EXISTS project_aliases ("
        "alias_id TEXT PRIMARY KEY, project_id TEXT NOT NULL)")
    conn.commit()
    conn.execute(
        "CREATE TABLE IF NOT EXISTS domains ("
        "domain_id TEXT PRIMARY KEY, status TEXT NOT NULL, updated_at TEXT)")
    conn.commit()
    ccols = {str(r[1]) for r in conn.execute("PRAGMA table_info(conflicts)").fetchall()}
    if "domain_id" not in ccols:
        conn.execute("ALTER TABLE conflicts ADD COLUMN domain_id TEXT DEFAULT ''")
    if "fact_id" not in ccols:
        conn.execute("ALTER TABLE conflicts ADD COLUMN fact_id TEXT DEFAULT ''")
    conn.commit()
    conn.execute("UPDATE conflicts SET domain_id='' WHERE domain_id IS NULL")
    conn.execute(
        "DELETE FROM conflicts WHERE resolved='' AND id NOT IN ("
        "SELECT id FROM (SELECT MAX(id) AS id FROM conflicts "
        "WHERE resolved='' GROUP BY fact_stem, project_id, "
        "COALESCE(domain_id,'')))")
    conn.commit()
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_conflicts_open "
        "ON conflicts(fact_stem, project_id, domain_id) WHERE resolved=''")
    conn.commit()
    conn.execute(
        "CREATE TABLE IF NOT EXISTS project_usage_windows ("
        "project_id TEXT NOT NULL, cycle_id TEXT NOT NULL, "
        "sequence INTEGER NOT NULL, started_at TEXT NOT NULL, "
        "probative INTEGER NOT NULL, "
        "PRIMARY KEY (project_id, cycle_id), "
        "UNIQUE (project_id, sequence))")
    conn.commit()
    conn.execute(
        "CREATE TABLE IF NOT EXISTS native_store_grants ("
        "normalized_path TEXT PRIMARY KEY, project_id TEXT NOT NULL, "
        "created_at TEXT NOT NULL, adopted_nonempty INTEGER NOT NULL)")
    conn.commit()
    # v4→v5: the group-scopes layer (v0.4.10 spec §3) — idempotent additive.
    conn.execute(
        "CREATE TABLE IF NOT EXISTS groups ("
        "group_id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE, "
        "domain_id TEXT NOT NULL, created_at TEXT)")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS group_members ("
        "group_id TEXT NOT NULL, project_id TEXT NOT NULL, granted_at TEXT, "
        "PRIMARY KEY (group_id, project_id))")
    conn.commit()
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_facts_domain_stem ON facts(domain_id, stem)")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_holders_project ON holders(project_id)")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_tombstones_domain ON tombstones(domain_id)")
    conn.commit()


def _ingest_json_grants(conn: sqlite3.Connection, plugin_data: Path) -> None:
    """One-shot JSON → SQLite for native_store_grants (ADR 023)."""
    src = plugin_data / "store-grants.json"
    if not src.is_file():
        return
    try:
        data = json.loads(src.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return
    grants = data.get("grants") if isinstance(data, dict) else None
    if not isinstance(grants, list):
        return
    for g in grants:
        if not isinstance(g, dict):
            continue
        pid = str(g.get("project_id") or "").strip()
        raw = str(g.get("path") or "").strip()
        if not pid or not raw:
            continue
        try:
            key = str(Path(raw).resolve())
        except OSError:
            key = raw
        row = conn.execute(
            "SELECT project_id FROM native_store_grants WHERE normalized_path=?",
            (key,)).fetchone()
        if row is not None:
            continue
        conn.execute(
            "INSERT INTO native_store_grants(normalized_path, project_id, "
            "created_at, adopted_nonempty) VALUES (?,?,?,?)",
            (key, pid, str(g.get("created_at") or ""), 0))
    conn.commit()
    # v0.4.0 review: "one-shot" was not enforced — every later grant mutation
    # re-ingested the JSON and RESURRECTED a revoked row (revoke → unrelated
    # grant → "path already granted"). Consume the source so the SQLite table
    # is the only grant authority after the first ingest.
    try:
        src.rename(src.with_suffix(".json.ingested"))
    except OSError as e:
        # review fix: the silent pass left the JSON behind — the next unrelated
        # grant op re-ingested it and RESURRECTED a revoked row (a silent
        # access-control regression). Fail loud; the operator removes the file.
        raise WriteRefused(
            f"grant JSON ingest could not consume the source ({src}): {e} — "
            "move or remove it; leaving it in place would resurrect revoked grants") from e


def iter_registered_projects(conn: sqlite3.Connection) -> list:
    try:
        rows = conn.execute(
            "SELECT project_id, display_name, native_memory_dir, "
            "COALESCE(session_dir, '') AS session_dir, COALESCE(status, '') AS status, "
            "COALESCE(domain_id, '') AS domain_id "
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
        "capabilities=CASE WHEN excluded.capabilities IN ('[]', '', 'null') "
        "THEN projects.capabilities ELSE excluded.capabilities END, "
        "domain_id=CASE WHEN projects.status='enrolled' THEN projects.domain_id "
        "ELSE excluded.domain_id END, "
        "profile_id=excluded.profile_id, remote_fingerprint=excluded.remote_fingerprint",
        (ctx.project_id, ctx.display_name, str(ctx.project_root),
         str(ctx.git_common_dir) if ctx.git_common_dir else "",
         ctx.remote_fingerprint, ctx.profile_id, ctx.domain_id,
         str(ctx.native_memory_dir), str(ctx.session_dir), now, caps, "active"),
    )


def enrolled_domain(conn: sqlite3.Connection, project_id: str) -> Optional[str]:
    row = conn.execute(
        "SELECT domain_id FROM projects WHERE project_id=? AND status='enrolled'",
        (project_id,),
    ).fetchone()
    if row and str(row["domain_id"] or "").strip() and str(row["domain_id"]) != "unknown":
        return str(row["domain_id"])
    return None


def enroll_project(conn: sqlite3.Connection, ctx: StoreContext, domain: str) -> None:
    """Grant enrollment. Does not commit — the caller (transact or a test helper) does."""
    from identifiers import validate_domain_id
    from store_context import WriteRefused
    d = validate_domain_id(domain)
    life = domain_lifecycle(conn, d)
    if life in ("deleting", "deleted"):
        raise WriteRefused(
            "domain %s is %s; enroll in an active domain" % (d, life))
    current = enrolled_domain(conn, ctx.project_id)
    if current and current != d:
        raise WriteRefused(
            f"already enrolled in {current}; use `cm project move-domain --to {d}`")
    caps = None
    try:
        from capabilities import detect_capabilities, load_capability_overrides
        ov = load_capability_overrides(ctx.plugin_data_dir, ctx.project_id)
        caps = detect_capabilities(ctx.project_root, overrides=ov)
    except Exception:
        caps = None
    upsert_project(conn, ctx, capabilities=caps)
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    conn.execute(
        "UPDATE projects SET domain_id=?, status='enrolled', last_seen=? WHERE project_id=?",
        (d, now, ctx.project_id),
    )


def unenroll_project(conn: sqlite3.Connection, project_id: str) -> None:
    """Revoke enrollment. Does not commit — the caller does."""
    conn.execute(
        "UPDATE projects SET status='active', domain_id='unknown' WHERE project_id=?",
        (project_id,),
    )


def holder_base_revision(conn: sqlite3.Connection, fact_id: str, project_id: str) -> Optional[str]:
    """Authoritative three-way base (ADR 011). None if no holder row."""
    row = conn.execute(
        "SELECT base_revision FROM holders WHERE fact_id=? AND project_id=?",
        (fact_id, project_id),
    ).fetchone()
    if row and str(row["base_revision"] or "").strip():
        return str(row["base_revision"])
    return None


def record_project_alias(conn: sqlite3.Connection, alias_id: str, project_id: str) -> None:
    conn.execute(
        "INSERT INTO project_aliases(alias_id, project_id) VALUES (?,?) "
        "ON CONFLICT(alias_id) DO UPDATE SET project_id=excluded.project_id",
        (alias_id, project_id),
    )


def resolve_project_alias(conn: sqlite3.Connection, alias_id: str) -> Optional[str]:
    try:
        row = conn.execute(
            "SELECT project_id FROM project_aliases WHERE alias_id=?", (alias_id,)
        ).fetchone()
    except sqlite3.OperationalError:
        return None
    if row and str(row["project_id"] or "").strip():
        return str(row["project_id"])
    return None


def project_upsert_op(ctx: StoreContext, *, domain_id: str, status: str,
                      capabilities: Optional[list] = None) -> dict:
    """Typed journal op that can recreate the full projects row on recover."""
    return {
        "op": "project_upsert",
        "project_id": ctx.project_id,
        "profile_id": ctx.profile_id,
        "current_root": str(ctx.project_root),
        "git_common_dir": str(ctx.git_common_dir) if ctx.git_common_dir else "",
        "remote_fingerprint": ctx.remote_fingerprint,
        "native_memory_dir": str(ctx.native_memory_dir),
        "session_dir": str(ctx.session_dir),
        "display_name": ctx.display_name,
        "capabilities": list(capabilities or []),
        "domain_id": domain_id,
        "status": status,
    }


def prevalidate_registry_ops(ops: list) -> None:
    """Refuse unknown/malformed typed ops before any irreversible file change."""
    for op in ops or []:
        if not isinstance(op, dict):
            raise WriteRefused("registry_ops entry is not an object")
        kind = str(op.get("op") or "")
        if kind not in REGISTRY_OP_KINDS:
            raise WriteRefused("unknown registry_op: " + kind)
        if kind == "project_upsert" and not str(op.get("project_id") or ""):
            raise WriteRefused("project_upsert missing project_id")
        if kind == "project_rebind" and not str(op.get("project_id") or ""):
            raise WriteRefused("project_rebind missing project_id")
        if kind == "fact_upsert" and not str(op.get("fact_id") or ""):
            raise WriteRefused("fact_upsert missing fact_id")
        if kind == "tombstone_delete" and not (
                str(op.get("fact_id") or "") or str(op.get("domain_id") or "")):
            raise WriteRefused("tombstone_delete missing fact_id/domain_id")
        if kind in ("group_upsert", "group_delete") and not str(op.get("group_id") or ""):
            raise WriteRefused(f"{kind} missing group_id")
        if kind == "group_upsert" and not (
                str(op.get("name") or "") or str(op.get("domain_id") or "")):
            raise WriteRefused("group_upsert missing name/domain_id")
        if kind in ("group_member_add", "group_member_remove") and not (
                str(op.get("group_id") or "") or str(op.get("project_id") or "")):
            raise WriteRefused(f"{kind} missing group_id/project_id")


def apply_registry_ops(conn: sqlite3.Connection, ops: list) -> None:
    """Replay typed journal v3 registry_ops (ADR 010). Unknown kinds refuse."""
    prevalidate_registry_ops(ops)
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    for op in ops or []:
        if not isinstance(op, dict):
            raise WriteRefused("registry_ops entry is not an object")
        kind = str(op.get("op") or "")
        if kind not in REGISTRY_OP_KINDS:
            raise WriteRefused("unknown registry_op: " + kind)
        if kind == "project_upsert":
            pid = str(op.get("project_id") or "")
            if not pid:
                raise WriteRefused("project_upsert missing project_id")
            caps = op.get("capabilities")
            if isinstance(caps, list):
                caps_s = json.dumps(caps)
            else:
                caps_s = str(caps or "[]")
            conn.execute(
                "INSERT INTO projects(project_id, display_name, current_root, git_common_dir, "
                "remote_fingerprint, profile_id, domain_id, native_memory_dir, session_dir, "
                "last_seen, capabilities, status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?) "
                "ON CONFLICT(project_id) DO UPDATE SET display_name=excluded.display_name, "
                "current_root=excluded.current_root, git_common_dir=excluded.git_common_dir, "
                "remote_fingerprint=excluded.remote_fingerprint, profile_id=excluded.profile_id, "
                "domain_id=excluded.domain_id, native_memory_dir=excluded.native_memory_dir, "
                "session_dir=excluded.session_dir, last_seen=excluded.last_seen, "
                "capabilities=excluded.capabilities, status=excluded.status",
                (pid, str(op.get("display_name") or ""),
                 str(op.get("current_root") or ""), str(op.get("git_common_dir") or ""),
                 str(op.get("remote_fingerprint") or ""), str(op.get("profile_id") or ""),
                 str(op.get("domain_id") or "unknown"),
                 str(op.get("native_memory_dir") or ""), str(op.get("session_dir") or ""),
                 now, caps_s, str(op.get("status") or "active")))
        elif kind == "project_domain_change":
            pid = str(op.get("project_id") or "")
            cur = conn.execute(
                "UPDATE projects SET domain_id=?, status=? WHERE project_id=?",
                (str(op.get("domain_id") or "unknown"),
                 str(op.get("status") or "enrolled"), pid))
            if cur.rowcount != 1:
                raise WriteRefused(
                    "project_domain_change affected %s rows (need project_upsert first)"
                    % cur.rowcount)
        elif kind == "fact_upsert":
            conn.execute(
                "INSERT INTO facts(fact_id, stem, domain_id, canonical_path, revision, "
                "status, sensitivity) VALUES (?,?,?,?,?,?,?) "
                "ON CONFLICT(fact_id) DO UPDATE SET revision=excluded.revision, "
                "canonical_path=excluded.canonical_path, status=excluded.status, "
                "sensitivity=excluded.sensitivity, stem=excluded.stem, "
                "domain_id=excluded.domain_id",
                (str(op.get("fact_id") or ""), str(op.get("stem") or ""),
                 str(op.get("domain_id") or ""), str(op.get("canonical_path") or ""),
                 str(op.get("revision") or ""), str(op.get("status") or "active"),
                 str(op.get("sensitivity") or "internal")))
        elif kind == "fact_status_change":
            conn.execute("UPDATE facts SET status=? WHERE fact_id=?",
                         (str(op.get("status") or ""), str(op.get("fact_id") or "")))
        elif kind == "fact_delete":
            fid = str(op.get("fact_id") or "")
            if fid:
                conn.execute("DELETE FROM facts WHERE fact_id=?", (fid,))
                conn.execute("DELETE FROM holders WHERE fact_id=?", (fid,))
        elif kind == "holder_upsert":
            record_holder(conn, str(op.get("fact_id") or ""),
                          str(op.get("project_id") or ""),
                          str(op.get("base_revision") or ""),
                          str(op.get("canonical_revision") or ""),
                          str(op.get("semantic_hash") or ""))
        elif kind == "holder_delete":
            fid = str(op.get("fact_id") or "")
            pid = str(op.get("project_id") or "")
            if fid and pid == "*":
                conn.execute("DELETE FROM holders WHERE fact_id=?", (fid,))
            elif fid == "*" and pid:   # the registry-unenroll sweep: every row the project held
                conn.execute("DELETE FROM holders WHERE project_id=?", (pid,))
            elif fid and pid:
                conn.execute("DELETE FROM holders WHERE fact_id=? AND project_id=?",
                             (fid, pid))
        elif kind == "tombstone_upsert":
            write_tombstone(conn, str(op.get("fact_id") or ""), str(op.get("stem") or ""),
                            str(op.get("domain_id") or ""), str(op.get("reason") or ""),
                            str(op.get("replacement_id") or ""),
                            str(op.get("grace_until") or ""))
        elif kind == "tombstone_delete":
            fid = str(op.get("fact_id") or "")
            did = str(op.get("domain_id") or "")
            if fid:
                conn.execute("DELETE FROM tombstones WHERE fact_id=?", (fid,))
            elif did:
                conn.execute("DELETE FROM tombstones WHERE domain_id=?", (did,))
            else:
                raise WriteRefused("tombstone_delete missing fact_id/domain_id")
        elif kind == "conflict_upsert":
            record_conflict(conn, str(op.get("stem") or op.get("fact_stem") or ""),
                            str(op.get("project_id") or ""),
                            {"action": op.get("action"), "local": op.get("local_hash"),
                             "canonical": op.get("canonical_hash")},
                            domain_id=str(op.get("domain_id") or ""),
                            fact_id=str(op.get("fact_id") or ""))
        elif kind == "conflict_resolve":
            mark_conflict_resolved(
                conn, str(op.get("stem") or op.get("fact_stem") or ""),
                str(op.get("project_id") or ""),
                str(op.get("resolved") or "resolved"),
                domain_id=str(op.get("domain_id") or ""))
        elif kind == "project_alias":
            aid = str(op.get("alias_id") or "")
            pid = str(op.get("project_id") or "")
            if aid and pid:
                record_project_alias(conn, aid, pid)
        elif kind == "migration_state_set":
            set_migration_mode(conn, str(op.get("value") or op.get("mode") or "dual-read"))
        elif kind == "project_rebind":
            old = str(op.get("project_id") or "")
            retire = str(op.get("retire_id") or op.get("alias_id") or "")
            if not old:
                raise WriteRefused("project_rebind missing project_id")
            conn.execute(
                "UPDATE projects SET current_root=?, git_common_dir=?, "
                "native_memory_dir=?, session_dir=?, display_name=?, last_seen=? "
                "WHERE project_id=?",
                (str(op.get("current_root") or ""), str(op.get("git_common_dir") or ""),
                 str(op.get("native_memory_dir") or ""), str(op.get("session_dir") or ""),
                 str(op.get("display_name") or ""), now, old))
            if retire and retire != old:
                conn.execute("DELETE FROM projects WHERE project_id=?", (retire,))
                record_project_alias(conn, retire, old)
        elif kind == "domain_status_set":
            did = str(op.get("domain_id") or "")
            st = str(op.get("status") or "")
            if not did or st not in ("active", "deleting", "deleted"):
                raise WriteRefused("domain_status_set requires domain_id and "
                                   "status=active|deleting|deleted")
            conn.execute(
                "INSERT INTO domains(domain_id, status, updated_at) VALUES (?,?,?) "
                "ON CONFLICT(domain_id) DO UPDATE SET status=excluded.status, "
                "updated_at=excluded.updated_at",
                (did, st, now))
        elif kind == "group_upsert":
            conn.execute(
                "INSERT INTO groups(group_id, name, domain_id, created_at) "
                "VALUES (?,?,?,?) ON CONFLICT(group_id) DO UPDATE SET "
                "name=excluded.name, domain_id=excluded.domain_id, "
                "created_at=excluded.created_at",
                (str(op.get("group_id") or ""), str(op.get("name") or ""),
                 str(op.get("domain_id") or ""), str(op.get("created_at") or now)))
        elif kind == "group_delete":
            gid = str(op.get("group_id") or "")
            conn.execute("DELETE FROM group_members WHERE group_id=?", (gid,))
            conn.execute("DELETE FROM groups WHERE group_id=?", (gid,))
        elif kind == "group_member_add":
            conn.execute(
                "INSERT INTO group_members(group_id, project_id, granted_at) "
                "VALUES (?,?,?) ON CONFLICT(group_id, project_id) DO UPDATE SET "
                "granted_at=excluded.granted_at",
                (str(op.get("group_id") or ""), str(op.get("project_id") or ""),
                 str(op.get("granted_at") or now)))
        elif kind == "group_member_remove":
            conn.execute(
                "DELETE FROM group_members WHERE group_id=? AND project_id=?",
                (str(op.get("group_id") or ""), str(op.get("project_id") or "")))


def domain_lifecycle(conn: Optional[sqlite3.Connection], domain_id: str) -> str:
    """active | deleting | deleted. Missing row is active."""
    if conn is None or not domain_id:
        return "active"
    try:
        row = conn.execute(
            "SELECT status FROM domains WHERE domain_id=?", (domain_id,)
        ).fetchone()
    except sqlite3.Error:
        return "active"
    if row is None:
        return "active"
    return str(row["status"] or "active")


def assert_domain_writable(ctx: StoreContext) -> None:
    """Refuse cross-project writes while a domain is deleting (P0-9)."""
    did = str(getattr(ctx, "domain_id", "") or "")
    if not did or did == "unknown":
        return
    conn = connect_if_exists(db_path(ctx))
    if conn is None:
        return
    try:
        st = domain_lifecycle(conn, did)
    finally:
        conn.close()
    if st in ("deleting", "deleted"):
        raise WriteRefused(
            f"domain {did} is {st}; pull/promote/canonical writes are refused")


def assert_rebind_invariant(conn: sqlite3.Connection, old_id: str, retire_id: str) -> None:
    """Exactly one authoritative enrolled row; alias computed → old; computed gone."""
    if not old_id:
        raise WriteRefused("postcondition: rebind missing project_id")
    old = conn.execute(
        "SELECT status FROM projects WHERE project_id=?", (old_id,)
    ).fetchone()
    if old is None:
        raise WriteRefused("postcondition: rebind target row missing: " + old_id)
    if retire_id and retire_id != old_id:
        gone = conn.execute(
            "SELECT project_id FROM projects WHERE project_id=?", (retire_id,)
        ).fetchone()
        if gone is not None:
            raise WriteRefused("postcondition: rebind computed id still present")
        alias = conn.execute(
            "SELECT project_id FROM project_aliases WHERE alias_id=?", (retire_id,)
        ).fetchone()
        if alias is None or str(alias["project_id"] or "") != old_id:
            raise WriteRefused("postcondition: rebind alias missing or wrong")
    n = conn.execute(
        "SELECT COUNT(*) AS n FROM projects WHERE project_id IN (?, ?)",
        (old_id, retire_id or old_id),
    ).fetchone()["n"]
    if int(n) != 1:
        raise WriteRefused("postcondition: rebind must leave exactly one project row")


def assert_domain_has_no_enrolled(conn: sqlite3.Connection, domain_id: str) -> None:
    """domain.status==deleted ⇒ zero enrolled members (P0-1)."""
    n = conn.execute(
        "SELECT COUNT(*) AS n FROM projects WHERE domain_id=? AND status='enrolled'",
        (domain_id,),
    ).fetchone()["n"]
    if int(n) != 0:
        raise WriteRefused(
            "postcondition: domain %s is deleted but still has %s enrolled project(s)"
            % (domain_id, n))


def assert_enrolled(conn: sqlite3.Connection, project_id: str, domain_id: str) -> None:
    row = conn.execute(
        "SELECT status, domain_id FROM projects WHERE project_id=?", (project_id,)
    ).fetchone()
    if row is None:
        raise WriteRefused("postcondition: project row missing: " + project_id)
    if str(row["status"] or "") != "enrolled" or str(row["domain_id"] or "") != domain_id:
        raise WriteRefused(
            "postcondition: want enrolled/%s, have %s/%s"
            % (domain_id, row["status"], row["domain_id"]))


def require_interprocess_lock() -> None:
    try:
        import fcntl  # noqa: F401
    except ImportError:
        from store_context import WriteRefused
        raise WriteRefused(
            "cross-project mutation requires POSIX flock (fcntl); "
            "refusing rather than locking as a no-op")


class FileLock:
    def __init__(self, path: Path):
        self.path = path
        self._fd: Optional[Any] = None

    def acquire(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd = open(self.path, "a+")
        try:
            import fcntl
            fcntl.flock(fd.fileno(), fcntl.LOCK_EX)
        except ImportError:
            fd.close()
            require_interprocess_lock()
        except Exception:
            try:
                fd.close()
            except OSError:
                pass
            raise
        self._fd = fd

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


def acquire_mutation_locks(ctx: StoreContext, project_ids: list,
                           extra_domains: Optional[list] = None) -> list:
    """Domain lock(s) in sorted name order, then global, then project locks."""
    from identifiers import IdentifierRefused, safe_child, validate_domain_id, validate_project_id
    require_interprocess_lock()
    locks: list = []
    try:
        names = [ctx.domain_id or "unknown"]
        for extra in extra_domains or []:
            if extra and str(extra) not in names:
                names.append(str(extra))
        for raw in sorted(set(names)):
            dname = validate_domain_id(raw, allow_unknown=True)
            dlock = FileLock(safe_child(lock_dir(ctx), f"domain-{dname}.lock"))
            dlock.acquire()
            locks.append(dlock)
        glob = FileLock(lock_dir(ctx) / "global.lock")
        glob.acquire()
        locks.append(glob)
        for pid in sorted(set(project_ids)):
            try:
                validate_project_id(str(pid))
            except IdentifierRefused:
                raise
            pl = FileLock(safe_child(lock_dir(ctx), f"project-{pid}.lock"))
            pl.acquire()
            locks.append(pl)
        return locks
    except Exception:
        release_locks(locks)
        raise


def release_locks(locks: list) -> None:
    for lk in reversed(locks):
        lk.release()


def sanitize_journal_payload(payload: dict) -> dict:
    """Strip fact bodies from a journal payload. Hashes and paths remain."""
    if not isinstance(payload, dict):
        return {}
    out = dict(payload)
    for k in JOURNAL_BODY_KEYS:
        if k not in out:
            continue
        val = out.pop(k)
        if k == "text" and "text_sha256" not in out:
            if isinstance(val, str):
                out["text_sha256"] = hashlib.sha256(val.encode("utf-8")).hexdigest()
            elif isinstance(val, (bytes, bytearray)):
                out["text_sha256"] = hashlib.sha256(bytes(val)).hexdigest()
    pre: list = []
    for item in out.get("dest_preimages") or []:
        if not isinstance(item, dict):
            continue
        pre.append({
            "dest": item.get("dest"),
            "sha256": item.get("sha256"),
            "absent": item.get("absent"),
            "mode": item.get("mode"),
            "orig_mode": item.get("orig_mode"),
            "published_sha256": item.get("published_sha256"),
            "blob": item.get("blob") or "",
        })
    if "dest_preimages" in out:
        out["dest_preimages"] = pre
    pubs: list = []
    for item in out.get("publishes") or []:
        if not isinstance(item, dict):
            continue
        pubs.append({
            "tmp": item.get("tmp"),
            "dest": item.get("dest"),
            "sha256": item.get("sha256"),
            "mode": item.get("mode"),
        })
    if "publishes" in out:
        out["publishes"] = pubs
    return out


_PREIMAGE_KEYS = ("dest", "sha256", "absent", "mode", "orig_mode",
                  "published_sha256", "blob")
_PUBLISH_KEYS = ("tmp", "dest", "sha256", "mode")


def _sanitize_journal_changed(payload: dict) -> "tuple[dict, bool]":
    """sanitize_journal_payload + a dirty flag, computed in the construction pass
    (v0.4.2 P2): redact_journal_payloads used to re-serialize every row twice
    (json.dumps before and after) to test for a change — 2M dumps over a 1M-row
    journal. `changed` is True exactly when cleaning alters anything: a popped body
    key, a preimage/publish item that gains the whitelist keys or drops a non-dict
    item, or a non-empty preimage blob (the redact walk clears those). Receipt-only
    rows are unchanged → skipped."""
    # P2 review fix: a NON-DICT payload was normalized to {} and COUNTED by the old
    # dumps-equality test (sanitize maps it to {}) — the flag must match.
    if not isinstance(payload, dict):
        return {}, True
    cleaned = sanitize_journal_payload(payload)
    changed = any(k in payload for k in JOURNAL_BODY_KEYS)
    if not changed:
        for item in payload.get("dest_preimages") or []:
            # a truthy blob is cleared by the redact walk; a FALSY-but-non-str blob
            # (null/0/false/[]) is mapped to "" by sanitize — both are changes; only
            # a falsy STR blob ("") is a no-op (review fix: the bare truthiness test
            # missed the second class).
            if (not isinstance(item, dict)
                    or set(item) != set(_PREIMAGE_KEYS)
                    or bool(item.get("blob")) or not isinstance(item.get("blob"), str)):
                changed = True
                break
    if not changed:
        for item in payload.get("publishes") or []:
            if not isinstance(item, dict) or set(item) != set(_PUBLISH_KEYS):
                changed = True
                break
    for item in cleaned.get("dest_preimages") or []:
        if isinstance(item, dict):
            item["blob"] = ""
    return cleaned, changed


def _journal_put_payload(conn: sqlite3.Connection, op_id: str, payload: dict,
                         *, step: Optional[str] = None) -> None:
    blob = json.dumps(sanitize_journal_payload(payload), sort_keys=True)
    if step is not None:
        conn.execute("UPDATE journal SET payload=?, step=? WHERE op_id=?",
                     (blob, step, op_id))
    else:
        conn.execute("UPDATE journal SET payload=? WHERE op_id=?", (blob, op_id))
    conn.commit()


def journal_insert(conn: sqlite3.Connection, kind: str, payload: dict, step: str) -> str:
    op_id = "op_" + uuid.uuid4().hex[:16]
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    conn.execute(
        "INSERT INTO journal(op_id, kind, payload, step, status, created_at) "
        "VALUES (?,?,?,?,?,?)",
        (op_id, kind, json.dumps(sanitize_journal_payload(payload), sort_keys=True),
         step, "pending", now),
    )
    conn.commit()
    return op_id


def journal_step(conn: sqlite3.Connection, op_id: str, step: str, status: str = "pending") -> None:
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    cols = {str(r[1]) for r in conn.execute("PRAGMA table_info(journal)").fetchall()}
    if status in ("complete", "abandoned") and "completed_at" in cols:
        conn.execute(
            "UPDATE journal SET step=?, status=?, completed_at=COALESCE(completed_at, ?) "
            "WHERE op_id=?",
            (step, status, now, op_id))
    else:
        conn.execute("UPDATE journal SET step=?, status=? WHERE op_id=?",
                     (step, status, op_id))
    conn.commit()


def pending_ops(conn: sqlite3.Connection) -> list:
    rows = conn.execute(
        "SELECT op_id, kind, payload, step, status FROM journal "
        "WHERE status IN ('pending', ?)",
        (JOURNAL_CLEANUP_PENDING,),
    ).fetchall()
    return [dict(r) for r in rows]


def _file_hash(path: Path) -> Optional[str]:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def _write_fully(fd: int, data: bytes) -> None:
    """Write every byte; fsync fail-closed. One os.write() can be short."""
    view = memoryview(data)
    sent = 0
    while sent < len(view):
        n = os.write(fd, view[sent:])
        if n <= 0:
            raise OSError("short write")
        sent += n
    os.fsync(fd)


def _b64(data: bytes) -> str:
    import base64
    return base64.b64encode(data).decode("ascii")


def _unb64(s: str) -> Optional[bytes]:
    import base64
    if not s:
        return None
    try:
        return base64.b64decode(s.encode("ascii"), validate=True)
    except (ValueError, TypeError):
        return None


def _write_exclusive(path: Path, data: bytes) -> None:
    """Create `path` 0600 exclusive, write+fsync. Caller unlinks a leftover tmp."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        _write_fully(fd, data)
    finally:
        os.close(fd)


def _secure_unlink(path: Path) -> dict:
    """Overwrite then unlink a recovery blob. Never swallows the terminal error."""
    out: dict = {"path": str(path), "deleted": False, "error": ""}
    try:
        size = path.stat().st_size
        fd = os.open(str(path), os.O_WRONLY)
        try:
            remaining = size
            chunk = b"\x00" * min(65536, size if size > 0 else 1)
            while remaining > 0:
                n = os.write(fd, chunk if remaining >= len(chunk) else b"\x00" * remaining)
                if n <= 0:
                    break
                remaining -= n
            os.fsync(fd)
        finally:
            os.close(fd)
        path.unlink()
        try:
            fsync_dir(path.parent)
        except OSError:
            pass
        out["deleted"] = True
        return out
    except OSError as e:
        try:
            path.unlink()
            out["deleted"] = True
            return out
        except OSError as e2:
            out["error"] = e2.__class__.__name__ or e.__class__.__name__
            return out


def _recovery_dir(ctx: Optional[StoreContext], op_id: str) -> Path:
    root = ctx.plugin_data_dir if ctx is not None else plugin_data_dir()
    d = root / "recovery" / op_id
    d.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(str(d), 0o700)
    except OSError:
        pass
    now = time.time()
    meta = {
        "op_id": op_id,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
        "expires_at": time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                    time.gmtime(now + RECOVERY_TTL_SEC)),
    }
    mp = d / "meta.json"
    try:
        if not mp.is_file():
            mp.write_text(json.dumps(meta) + "\n", encoding="utf-8")
            os.chmod(str(mp), 0o600)
    except OSError:
        pass
    return d


def _cleanup_recovery(ctx: Optional[StoreContext], op_id: str) -> dict:
    """Remove recovery/<op-id>/. Structured result; never silent-success on error."""
    out: dict = {"deleted": [], "missing": [], "errors": []}
    root = ctx.plugin_data_dir if ctx is not None else plugin_data_dir()
    d = root / "recovery" / op_id
    if not d.is_dir():
        out["missing"].append(str(d))
        return out
    try:
        for p in list(d.iterdir()):
            if p.is_file():
                r = _secure_unlink(p)
                if r.get("deleted"):
                    out["deleted"].append(str(p))
                elif r.get("error"):
                    out["errors"].append({"path": str(p), "error": r["error"]})
                elif p.exists():
                    out["errors"].append({"path": str(p), "error": "still-present"})
        if not out["errors"]:
            try:
                d.rmdir()
                fsync_dir(d.parent)
            except OSError as e:
                if d.is_dir() and any(d.iterdir()):
                    out["errors"].append({"path": str(d), "error": e.__class__.__name__})
    except OSError as e:
        out["errors"].append({"path": str(d), "error": e.__class__.__name__})
    return out


def _dest_contained(dest: Path, parent: Path) -> bool:
    try:
        dest.resolve().relative_to(parent.resolve())
        return True
    except (ValueError, OSError):
        return False


def _quarantine_dest(dest: Path) -> Optional[Path]:
    """Move dest aside so compensation will not overwrite a concurrent edit."""
    if not dest.exists():
        return None
    qdir = dest.parent / "quarantine"
    try:
        qdir.mkdir(parents=True, exist_ok=True)
        os.chmod(str(qdir), 0o700)
    except OSError:
        return None
    ts = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    q = qdir / f"{dest.name}.{ts}"
    n = 0
    while q.exists():
        n += 1
        q = qdir / f"{dest.name}.{ts}.{n}"
    try:
        os.rename(str(dest), str(q))
        try:
            os.chmod(str(q), 0o600)
        except OSError:
            pass
    except OSError:
        return None
    return q


def _load_preimage_bytes(item: dict) -> Optional[bytes]:
    blob = str(item.get("blob") or "")
    if blob:
        try:
            return Path(blob).read_bytes()
        except OSError:
            return None
    b64 = str(item.get("bytes_b64") or "")
    if b64:
        return _unb64(b64)
    return None


def _snapshot_dest_preimages(publishes: list, *, recovery: Path,
                             op_id: str = "") -> list:
    """Snapshot dest bytes to recovery files — never into the journal payload."""
    out: list = []
    for i, item in enumerate(publishes):
        dest = Path(item.get("dest") or "")
        mode = str(item.get("mode") or "replace")
        published = str(item.get("sha256") or "")
        if not dest or str(dest) in (".", "/"):
            continue
        if dest.exists():
            try:
                raw = dest.read_bytes()
                orig_mode = dest.stat().st_mode & 0o777
            except OSError:
                raise WriteRefused("cannot snapshot dest (unreadable): " + str(dest))
            blob = recovery / f"dest-{i}.bin"
            blob.unlink(missing_ok=True)
            _write_exclusive(blob, raw)
            try:
                os.chmod(str(blob), 0o600)
            except OSError:
                pass
            out.append({
                "dest": str(dest),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "absent": False, "mode": mode, "blob": str(blob),
                "published_sha256": published,
                "orig_mode": orig_mode,
                "op_id": op_id,
            })
        else:
            out.append({
                "dest": str(dest), "sha256": ABSENT, "absent": True,
                "mode": mode, "blob": "", "published_sha256": published,
                "orig_mode": 0,
                "op_id": op_id,
            })
    return out


def _restore_dest_preimages(preimages: list,
                            publishes: Optional[list] = None) -> dict:
    """Restore dests only when they still hold the published hash (ADR 017).

    A dest the user edited after publish is quarantined, then the original
    snapshot is written back onto the now-free path. Never clobber newer bytes.
    Legacy journal rows with `bytes_b64` still restore.
    """
    published_map = {}
    for p in publishes or []:
        d = str(p.get("dest") or "")
        h = str(p.get("sha256") or "")
        if d and h:
            published_map[d] = h
    quarantined: list = []
    restored: list = []
    skipped: list = []
    for item in preimages or []:
        dest = Path(str(item.get("dest") or ""))
        if not dest or str(dest) in (".", "/"):
            continue
        parent = dest.parent
        published = str(item.get("published_sha256") or published_map.get(str(dest)) or "")
        orig = str(item.get("sha256") or "")
        absent = bool(item.get("absent") or orig == ABSENT)
        current = _file_hash(dest) if dest.exists() else None

        def _write_orig() -> None:
            raw = _load_preimage_bytes(item)
            if raw is None:
                raise WriteRefused("cannot restore dest (missing preimage): " + str(dest))
            tmp = _op_sidecar(dest, str(item.get("op_id") or "restore"), "restore")
            tmp.unlink(missing_ok=True)
            _write_exclusive(tmp, raw)
            os.replace(str(tmp), str(dest))
            try:
                fsync_dir(dest.parent)
            except OSError:
                pass
            want_mode = int(item.get("orig_mode") or 0o600)
            if want_mode:
                try:
                    os.chmod(str(dest), want_mode)
                except OSError:
                    pass
                got_mode = dest.stat().st_mode & 0o777
                if got_mode != want_mode:
                    raise WriteRefused("restored dest mode mismatch: " + str(dest))
            if orig and orig != ABSENT and _file_hash(dest) != orig:
                raise WriteRefused("restored dest hash mismatch: " + str(dest))
            if not _dest_contained(dest, parent):
                raise WriteRefused("restored dest escaped parent: " + str(dest))
            if not dest.exists():
                raise WriteRefused("restored dest missing: " + str(dest))

        if absent:
            if current is None:
                skipped.append(str(dest))
                continue
            if published and current == published:
                dest.unlink(missing_ok=True)
                if dest.exists():
                    raise WriteRefused("absent dest still present after restore: " + str(dest))
                restored.append(str(dest))
                continue
            q = _quarantine_dest(dest)
            if q is not None:
                quarantined.append(str(q))
            if dest.exists():
                raise WriteRefused(
                    "cannot restore dest (occupant not quarantined): " + str(dest))
            continue
        if current == orig:
            skipped.append(str(dest))
            continue
        if current is not None and current != published:
            q = _quarantine_dest(dest)
            if q is not None:
                quarantined.append(str(q))
            if dest.exists():
                raise WriteRefused(
                    "cannot restore dest (occupant not quarantined): " + str(dest))
        _write_orig()
        restored.append(str(dest))
    return {"restored": restored, "quarantined": quarantined, "skipped": skipped}


def _failed_owned_dests(conn: sqlite3.Connection) -> set:
    owned: set = set()
    try:
        rows = conn.execute(
            "SELECT payload FROM journal WHERE status IN ('failed', 'conflicted')"
        ).fetchall()
    except sqlite3.Error:
        return owned
    for row in rows:
        try:
            payload = json.loads(row["payload"] or "{}")
        except (ValueError, TypeError):
            continue
        if not payload.get("dests_mutated"):
            continue
        for item in payload.get("publishes") or []:
            d = str(item.get("dest") or "")
            if d:
                owned.add(d)
    return owned


def abandon_failed(conn: sqlite3.Connection, op_id: Optional[str] = None) -> int:
    """Mark failed/conflicted journal rows abandoned so a new overlapping transact may proceed."""
    if op_id:
        journal_step(conn, op_id, "abandoned", "abandoned")
        return 1
    rows = conn.execute(
        "SELECT op_id FROM journal WHERE status IN ('failed', 'conflicted')"
    ).fetchall()
    n = 0
    for row in rows:
        journal_step(conn, row["op_id"], "abandoned", "abandoned")
        n += 1
    return n


def journal_row(conn: sqlite3.Connection, op_id: str) -> Optional[dict]:
    row = conn.execute(
        "SELECT op_id, kind, payload, step, status, created_at FROM journal WHERE op_id=?",
        (op_id,),
    ).fetchone()
    return dict(row) if row is not None else None


def journal_inventory(conn: sqlite3.Connection, *, limit: int = 200,
                      after: str = "") -> "tuple[list, str | None]":
    """Keyset-paged journal listing (Phase-5 SLO: bounded at 1M rows).

    The sort key is `(created_at, op_id)` — second-resolution created_at, never
    updated after write, tie-broken by the immutable PK — so the keyset is
    stable across pages. `after` is the opaque cursor "<created_at>|<op_id>";
    returns (rows, next_after) with next_after None on the last page. Row dict
    shape is unchanged (op_id/kind/step/status/created_at/has_body/
    publishes/deletes).
    """
    limit = max(1, int(limit))
    after = str(after or "").strip()
    q = ("SELECT op_id, kind, step, status, created_at, payload FROM journal "
         "ORDER BY created_at, op_id LIMIT ?")
    params: list = [limit + 1]   # fetch one extra to detect a next page
    if after:
        parts = after.split("|", 1)
        if len(parts) == 2 and parts[0] and parts[1]:
            q = ("SELECT op_id, kind, step, status, created_at, payload FROM journal "
                 "WHERE (created_at, op_id) > (?, ?) "
                 "ORDER BY created_at, op_id LIMIT ?")
            params = [parts[0], parts[1], limit + 1]
    rows = conn.execute(q, params).fetchall()
    out: list = []
    for i, r in enumerate(rows):
        if i >= limit:
            break
        try:
            payload = json.loads(r["payload"] or "{}")
        except (ValueError, TypeError):
            payload = {}
        has_body = any(k in payload for k in JOURNAL_BODY_KEYS)
        for item in payload.get("dest_preimages") or []:
            if isinstance(item, dict) and item.get("bytes_b64"):
                has_body = True
        out.append({
            "op_id": r["op_id"], "kind": r["kind"], "step": r["step"],
            "status": r["status"], "created_at": r["created_at"],
            "has_body": has_body,
            "publishes": len(payload.get("publishes") or []),
            "deletes": len(payload.get("deletes") or []),
        })
    # cursor = the LAST RETURNED row's key (the `>` predicate resumes after it —
    # the extra fetched row is never dropped).
    next_after: "str | None" = None
    if len(rows) > limit and out:
        _last = out[-1]
        next_after = f"{_last['created_at']}|{_last['op_id']}"
    return out, next_after


def journal_count(conn: sqlite3.Connection) -> int:
    """Total journal rows (for the inventory footer / --json total)."""
    cur = conn.execute("SELECT COUNT(*) AS n FROM journal").fetchone()
    return int(cur["n"] or 0) if cur is not None else 0


def journal_show(conn: sqlite3.Connection, op_id: str) -> Optional[dict]:
    row = journal_row(conn, op_id)
    if row is None:
        return None
    try:
        payload = json.loads(row["payload"] or "{}")
    except (ValueError, TypeError):
        payload = {}
    row["payload"] = sanitize_journal_payload(payload)
    return row


def redact_journal_payloads(conn: sqlite3.Connection) -> int:
    """Replace durable fact bodies in completed/abandoned rows with hashes."""
    n = 0
    rows = conn.execute(
        "SELECT op_id, payload, status FROM journal"
    ).fetchall()
    for row in rows:
        status = str(row["status"] or "")
        if status not in ("complete", "abandoned"):
            continue
        try:
            payload = json.loads(row["payload"] or "{}")
        except (ValueError, TypeError):
            continue
        # v0.4.2 P2: the dirty flag replaces the per-row double json.dumps equality.
        cleaned, changed = _sanitize_journal_changed(payload)
        if not changed:
            continue
        conn.execute("UPDATE journal SET payload=? WHERE op_id=?",
                     (json.dumps(cleaned, sort_keys=True), row["op_id"]))
        n += 1
    conn.commit()
    return n


def expire_recovery(ctx: Optional[StoreContext], conn: sqlite3.Connection) -> int:
    if ctx is None:
        return 0
    root = ctx.plugin_data_dir / "recovery"
    if not root.is_dir():
        return 0
    live = {str(r["op_id"]): str(r["status"] or "")
            for r in conn.execute("SELECT op_id, status FROM journal").fetchall()}
    n = 0
    now = time.time()
    for d in list(root.iterdir()):
        if not d.is_dir():
            continue
        oid = d.name
        st = live.get(oid)
        if st in ("failed", "conflicted"):
            # v0.4.0 review: recovery material for a retryable op must not expire
            # while `journal retry` still offers restoration — keep it.
            continue
        expired = False
        meta_p = d / "meta.json"
        if meta_p.is_file():
            try:
                meta = json.loads(meta_p.read_text(encoding="utf-8"))
                exp = str((meta or {}).get("expires_at") or "")
                if exp:
                    expired = calendar.timegm(
                        time.strptime(exp, "%Y-%m-%dT%H:%M:%SZ")) < now
            except (ValueError, TypeError, OSError, OverflowError):
                expired = False
        keep_pending = st in ("pending", "failed", "conflicted", JOURNAL_CLEANUP_PENDING)
        if keep_pending and not expired:
            continue
        if st in ("complete", "abandoned") or st is None or (expired and not keep_pending):
            rec = _cleanup_recovery(ctx, oid)
            if not rec.get("errors"):
                n += 1
    return n


def _journal_age_days(row: dict) -> float:
    ts = str(row.get("completed_at") or row.get("created_at") or "")
    if not ts:
        return 0.0
    try:
        epoch = calendar.timegm(time.strptime(ts, "%Y-%m-%dT%H:%M:%SZ"))
    except (ValueError, TypeError, OverflowError):
        return 0.0
    return max(0.0, (time.time() - epoch) / 86400.0)


def _receipt_payload(row: dict, payload: dict) -> dict:
    ops = payload.get("registry_ops") or []
    digest = hashlib.sha256(
        json.dumps(ops, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:16]
    sources = []
    for s in payload.get("sources") or payload.get("expected_revisions") or []:
        if isinstance(s, dict):
            sources.append(str(s.get("sha256") or ""))
        elif isinstance(s, str):
            sources.append(s)
    dests = [str(p.get("sha256") or "") for p in (payload.get("publishes") or [])
             if isinstance(p, dict)]
    return {
        "receipt": True,
        "kind": row.get("kind"),
        "terminal_status": row.get("status"),
        "created_at": row.get("created_at"),
        "completed_at": row.get("completed_at") or "",
        "source_hashes": [h for h in sources if h],
        "dest_hashes": [h for h in dests if h],
        "registry_ops_digest": digest,
    }


def bound_journal_rows(conn: sqlite3.Connection, *, days: int = JOURNAL_RECEIPT_DAYS,
                       max_rows: int = 0) -> int:
    """Collapse old complete/abandoned rows to receipts; with max_rows, DELETE the
    oldest terminal rows beyond the cap. Never touch pending/failed/conflicted.

    The cap-delete counts 1 toward the return value (an operation count, not a
    deleted-row count) — a deliberate convention shared with _compact_pass (v0.4.2
    P2) so the compact result stays comparable across versions."""
    n = 0
    rows = conn.execute(
        "SELECT op_id, kind, payload, status, created_at, "
        "COALESCE(completed_at, '') AS completed_at FROM journal"
    ).fetchall()
    for row in rows:
        status = str(row["status"] or "")
        if status not in ("complete", "abandoned"):
            continue
        if _journal_age_days(dict(row)) < days:
            continue
        try:
            payload = json.loads(row["payload"] or "{}")
        except (ValueError, TypeError):
            payload = {}
        if isinstance(payload, dict) and payload.get("receipt"):
            continue
        receipt = _receipt_payload(dict(row), payload if isinstance(payload, dict) else {})
        conn.execute("UPDATE journal SET payload=? WHERE op_id=?",
                     (json.dumps(receipt, sort_keys=True), row["op_id"]))
        n += 1
    if max_rows and max_rows > 0:
        cur = conn.execute("SELECT COUNT(*) AS n FROM journal").fetchone()
        total = int(cur["n"] or 0) if cur is not None else 0
        if total > max_rows:
            conn.execute(
                "DELETE FROM journal WHERE op_id IN ("
                "SELECT op_id FROM journal WHERE status IN ('complete','abandoned') "
                "ORDER BY created_at LIMIT ?)",
                (total - max_rows,))
            n += 1
    if n:
        conn.commit()
    return n


def _compact_pass(conn: sqlite3.Connection, *, max_rows: int = 0) -> dict:
    """ONE merged walk over the journal (v0.4.2 P2): per terminal row, redact body
    content (dirty-flag) AND collapse age-eligible rows to receipts. The old
    compact_journal made two full scans (redact then bound) and each re-parsed the
    row's timestamps; age is hoisted into a per-row epoch computed in this single
    walk. One UPDATE per changed row. Counts match the old three-pass result
    exactly: a row that is BOTH redactable and receipt-collapsed counts in both.

    `max_rows` (the same cap bound_journal_rows applies): DELETE the oldest terminal
    rows beyond the cap — and count 1 toward `receipts` when the deletion ran (the
    historical bound_journal_rows convention: the cap-delete is one operation, not a
    deleted-row count — kept deliberately so the compact result stays comparable
    across versions)."""
    now_epoch = time.time()
    n_red = 0
    n_rec = 0
    total = 0
    rows = conn.execute(
        "SELECT op_id, kind, payload, status, created_at, "
        "COALESCE(completed_at, '') AS completed_at FROM journal"
    ).fetchall()
    for row in rows:
        total += 1
        status = str(row["status"] or "")
        if status not in ("complete", "abandoned"):
            continue
        try:
            payload = json.loads(row["payload"] or "{}")
        except (ValueError, TypeError):
            payload = {}
        if isinstance(payload, dict) and payload.get("receipt"):
            continue
        d = dict(row)
        ts = str(d.get("completed_at") or d.get("created_at") or "")
        age_days = 0.0
        if ts:
            try:
                age_days = max(0.0, (now_epoch - calendar.timegm(
                    time.strptime(ts, "%Y-%m-%dT%H:%M:%SZ"))) / 86400.0)
            except (ValueError, TypeError, OverflowError):
                age_days = 0.0
        cleaned, changed = _sanitize_journal_changed(payload)
        if age_days >= JOURNAL_RECEIPT_DAYS:
            conn.execute("UPDATE journal SET payload=? WHERE op_id=?",
                         (json.dumps(_receipt_payload(d, cleaned), sort_keys=True),
                          row["op_id"]))
            n_rec += 1
            if changed:
                n_red += 1
        elif changed:
            conn.execute("UPDATE journal SET payload=? WHERE op_id=?",
                         (json.dumps(cleaned, sort_keys=True), row["op_id"]))
            n_red += 1
    if max_rows and max_rows > 0 and total > max_rows:
        conn.execute(
            "DELETE FROM journal WHERE op_id IN ("
            "SELECT op_id FROM journal WHERE status IN ('complete','abandoned') "
            "ORDER BY created_at LIMIT ?)",
            (total - max_rows,))
        n_rec += 1
    if n_red or n_rec:
        conn.commit()
    return {"redacted": n_red, "receipts": n_rec}


def compact_journal(ctx: StoreContext) -> dict:
    require_interprocess_lock()
    locks = acquire_mutation_locks(ctx, [ctx.project_id])
    conn = connect_journal(ctx)
    try:
        # R4 (v0.4.2): the advertised cap is LIVE on the compact path — it used to pass
        # max_rows=0 (the cap was dormant: compact never deleted beyond-cap terminal rows).
        pass_r = _compact_pass(conn, max_rows=JOURNAL_MAX_ROWS)
        n_rec = expire_recovery(ctx, conn)
        # v0.4.2 P2: VACUUM only when the journal was actually rewritten (the old
        # unconditional VACUUM paid a full-file rebuild on every compact, even a no-op).
        if pass_r["redacted"] or pass_r["receipts"]:
            try:
                conn.execute("VACUUM")
            except sqlite3.Error:
                pass
        return {"ok": True, "redacted": pass_r["redacted"],
                "receipts": pass_r["receipts"], "recovery_expired": n_rec}
    finally:
        conn.close()
        release_locks(locks)


def _artifact_op_id(name: str) -> Optional[str]:
    """Best-effort op_id from `.cm-trash-OP-N` / `name.tmp-OP` / `name.restore-OP`."""
    if name.startswith(".cm-trash-"):
        rest = name[len(".cm-trash-"):]
        if not rest:
            return None
        op, sep, idx = rest.rpartition("-")
        if sep and idx.isdigit() and op:
            return op
        return rest
    for kind in (".tmp-", ".restore-"):
        if kind in name:
            tail = name.rsplit(kind, 1)[-1]
            return tail or None
    return None


def _iter_store_roots(ctx: StoreContext, *, all_stores: bool) -> list:
    roots = [ctx.native_memory_dir, ctx.canonical_domain_dir, ctx.plugin_data_dir]
    if all_stores:
        conn = connect_if_exists(db_path(ctx))
        if conn is not None:
            try:
                for r in conn.execute(
                        "SELECT native_memory_dir FROM projects").fetchall():
                    p = Path(str(r["native_memory_dir"] or ""))
                    if p:
                        roots.append(p)
            finally:
                conn.close()
        droot = ctx.config_root / "consolidate-memory" / "domains"
        if droot.is_dir():
            for d in droot.iterdir():
                facts = d / "facts"
                if facts.is_dir():
                    roots.append(facts)
    out: list = []
    seen: set = set()
    for p in roots:
        try:
            key = str(p.resolve())
        except OSError:
            key = str(p)
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
    return out


def _scavenge_artifact(name: str, live: dict) -> bool:
    """True when this sidecar is orphan/terminal. Never pending/failed/conflicted."""
    oid = _artifact_op_id(name)
    if not oid:
        return False
    st = live.get(oid)
    if st in JOURNAL_HOLD_FS:
        return False
    if st is None and not oid.startswith("op_") and not name.startswith(".cm-trash-"):
        return False
    return True


def scan_orphan_artifacts(ctx: StoreContext, *, all_stores: bool = False) -> dict:
    """Find leftover .cm-trash-*, recovery dirs, and op-id temps.

    Pending/failed/conflicted preimages are live complete-old state and are
    omitted — `cm journal cleanup` must not unlink them.
    """
    conn = connect_journal(ctx)
    try:
        live = {str(r["op_id"]): str(r["status"] or "")
                for r in conn.execute("SELECT op_id, status FROM journal").fetchall()}
        cleanup_pending = [
            oid for oid, st in live.items() if st == JOURNAL_CLEANUP_PENDING]
    finally:
        conn.close()
    trash: list = []
    temps: list = []
    recovery: list = []
    for root in _iter_store_roots(ctx, all_stores=all_stores):
        if not root.is_dir():
            continue
        try:
            for p in root.rglob("*"):
                name = p.name
                if not p.is_file():
                    continue
                if name.startswith(".cm-trash-"):
                    if _scavenge_artifact(name, live):
                        trash.append(str(p))
                elif ".tmp-" in name or ".restore-" in name:
                    if _scavenge_artifact(name, live):
                        temps.append(str(p))
        except OSError:
            continue
    rec_root = ctx.plugin_data_dir / "recovery"
    if rec_root.is_dir():
        for d in rec_root.iterdir():
            if d.is_dir():
                st = live.get(d.name)
                if st in ("complete", "abandoned") or st is None:
                    recovery.append(str(d))
    return {
        "cleanup_pending": cleanup_pending,
        "trash": trash,
        "temps": temps,
        "recovery": recovery,
    }


def journal_cleanup(ctx: StoreContext, *, apply: bool = False,
                    all_stores: bool = False) -> dict:
    """Retry committed-cleanup-pending and scavenge orphan trash/recovery."""
    require_interprocess_lock()
    if not apply:
        scan = scan_orphan_artifacts(ctx, all_stores=all_stores)
        return {"ok": True, "apply": False, **scan}
    locks = acquire_mutation_locks(ctx, [ctx.project_id])
    recovered: list = []
    errors: list = []
    jconn = connect_journal(ctx)
    rconn = connect(db_path(ctx))
    rconn.isolation_level = None
    try:
        recovered = recover_pending(jconn, ctx=ctx, registry_conn=rconn)
        # Re-scan under the mutation locks so we never unlink a concurrent
        # transact's complete-old trash from the pre-lock plan snapshot.
        scan2 = scan_orphan_artifacts(ctx, all_stores=all_stores)
        gone: set = set()   # paths that left the disk (unlinked, or already gone) — excluded from `remaining`
        for path_s in scan2.get("trash") or []:
            p = Path(path_s)
            if not p.exists():
                gone.add(path_s)
                continue
            try:
                p.unlink()
                fsync_dir(p.parent)
                gone.add(path_s)
            except OSError as e:
                errors.append({"path": path_s, "error": e.__class__.__name__})
        for path_s in scan2.get("temps") or []:
            p = Path(path_s)
            if not p.exists():
                gone.add(path_s)
                continue
            try:
                p.unlink()
                fsync_dir(p.parent)
                gone.add(path_s)
            except OSError as e:
                errors.append({"path": path_s, "error": e.__class__.__name__})
        rec_root = ctx.plugin_data_dir / "recovery"
        live: dict = {}
        if rec_root.is_dir():
            live = {str(r["op_id"]): str(r["status"] or "")
                    for r in jconn.execute("SELECT op_id, status FROM journal").fetchall()}
            for d in list(rec_root.iterdir()):
                if not d.is_dir():
                    continue
                st = live.get(d.name)
                if st in JOURNAL_HOLD_FS or st == JOURNAL_CLEANUP_PENDING:
                    continue
                rec = _cleanup_recovery(ctx, d.name)
                errors.extend(rec.get("errors") or [])
        # v0.4.2 P2: `remaining` is scan2 MINUS the paths that left the disk — the
        # old code ran a THIRD full orphan scan here (an rglob over every store).
        # Under the mutation locks nothing new can appear, so a failed unlink is the
        # only path that can survive into `remaining` (the honest post-cleanup
        # snapshot). Recovery dirs are re-listed directly (one iterdir — cheap — and
        # it must reflect the cleanups just performed).
        remaining = {
            "cleanup_pending": scan2.get("cleanup_pending") or [],
            "trash": [p for p in scan2.get("trash") or [] if p not in gone],
            "temps": [p for p in scan2.get("temps") or [] if p not in gone],
            "recovery": [str(d) for d in rec_root.iterdir()
                         if d.is_dir() and (live.get(d.name) in ("complete", "abandoned")
                                            or live.get(d.name) is None)]
            if rec_root.is_dir() else [],
        }
        # v0.4.0 review: a still-cleanup-pending op means a retry failed — `ok`
        # must say so (the old `not errors` silently reported success with work
        # left on the journal).
        cp_left = remaining.get("cleanup_pending") or []
        bound_journal_rows(jconn, max_rows=JOURNAL_MAX_ROWS)
        # review fix: quarantine/ (the mirror-conflict + failed-restore holding pen)
        # had no GC anywhere — unbounded pile-up. Age-cap it with the same TTL the
        # recovery dirs use; resolved conflicts also age out of the conflicts table
        # (independent of quarantine activity — one cutoff, both sweeps). Keyed on
        # created_at (the ISO detection timestamp record_conflict writes/refreshes):
        # `resolved` holds the human decision label (keep-canonical/fork-local/…),
        # which never compares against a cutoff.
        cutoff = time.time() - RECOVERY_TTL_SEC
        cutoff_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(cutoff))
        q_swept = _sweep_quarantine(ctx, cutoff)
        rconn.execute(
            "DELETE FROM conflicts WHERE resolved != '' AND created_at < ?",
            (cutoff_iso,))
        rconn.commit()
        return {"ok": bool(not errors and not cp_left), "apply": True,
                "recovered": recovered, "errors": errors,
                "remaining": remaining, "quarantine_swept": q_swept}
    finally:
        jconn.close()
        rconn.close()
        release_locks(locks)


def _sweep_quarantine(ctx: StoreContext, cutoff: float) -> int:
    """Age-cap the native quarantine/ holding pen (mirror-conflict + failed-restore
    files) — returns the number of files swept (0 when the dir does not exist). No
    code ever deleted from quarantine/ before this — unbounded pile-up
    (2026-09-03 audit)."""
    qdir = ctx.native_memory_dir / "quarantine"
    if not qdir.is_dir():
        return 0
    n = 0
    for p in qdir.iterdir():
        if not p.is_file():
            continue
        try:
            if p.stat().st_mtime < cutoff:
                p.unlink()
                n += 1
        except OSError:
            pass
    if not any(qdir.iterdir()):
        try:
            qdir.rmdir()
        except OSError:
            pass
    return n


def journal_rollback(ctx: StoreContext, op_id: str) -> dict:
    """Restore dests + trash for a non-complete op and mark abandoned."""
    require_interprocess_lock()
    locks = acquire_mutation_locks(ctx, [ctx.project_id])
    conn = connect_journal(ctx)
    try:
        row = journal_row(conn, op_id)
        if row is None:
            raise WriteRefused("unknown journal op: " + op_id)
        status = str(row["status"] or "")
        if status == "complete":
            raise WriteRefused("cannot rollback a complete journal op: " + op_id)
        if status == JOURNAL_CLEANUP_PENDING:
            raise WriteRefused(
                "cannot rollback after registry commit; use journal retry: "
                + op_id)
        step = str(row.get("step") or "")
        if step in ("after_dests", "publish", "commit_registry", "cleanup_pending",
                    "journal_complete"):
            raise WriteRefused(
                "cannot rollback after dests published; use journal retry: "
                + op_id)
        try:
            payload = json.loads(row["payload"] or "{}")
        except (ValueError, TypeError):
            payload = {}
        dest_out = _restore_dest_preimages(
            payload.get("dest_preimages") or [], payload.get("publishes") or [])
        trash_out = _restore_trash(payload.get("deletes") or [])
        if trash_out.get("errors"):
            raise WriteRefused(
                "restore failed; not abandoned: "
                + ", ".join(str(e.get("path") or e) for e in trash_out["errors"][:8]))
        leftover = [str(d.get("trash")) for d in (payload.get("deletes") or [])
                    if isinstance(d, dict) and d.get("trash")
                    and Path(str(d.get("trash"))).exists()]
        if leftover:
            raise WriteRefused(
                "restore left trash in place; not abandoned: " + leftover[0])
        journal_step(conn, op_id, "abandoned", "abandoned")
        _finish_sensitive_cleanup(ctx, op_id, payload)
        return {"ok": True, "op_id": op_id, "status": "abandoned",
                "restored": dest_out}
    finally:
        conn.close()
        release_locks(locks)


def journal_retry(ctx: StoreContext, op_id: str) -> dict:
    """Re-run recover for one pending/conflicted/failed op."""
    require_interprocess_lock()
    locks = acquire_mutation_locks(ctx, [ctx.project_id])
    jconn = connect_journal(ctx)
    rconn = connect(db_path(ctx))
    rconn.isolation_level = None
    try:
        row = journal_row(jconn, op_id)
        if row is None:
            raise WriteRefused("unknown journal op: " + op_id)
        status = str(row["status"] or "")
        if status == "complete":
            return {"ok": True, "op_id": op_id, "status": "complete", "recovered": []}
        if status == "abandoned":
            raise WriteRefused("cannot retry an abandoned journal op: " + op_id)
        if status in ("failed", "conflicted"):
            journal_step(jconn, op_id, row.get("step") or "pending", "pending")
        recovered = recover_pending(jconn, ctx=ctx, registry_conn=rconn, op_id=op_id)
        row2 = journal_row(jconn, op_id)
        return {"ok": True, "op_id": op_id,
                "status": str((row2 or {}).get("status") or ""),
                "recovered": recovered}
    finally:
        jconn.close()
        rconn.close()
        release_locks(locks)


def journal_abandon(ctx: StoreContext, op_id: str, *, accept_fs: bool = False) -> dict:
    """Mark abandoned without restoring files (operator accepts current FS).

    Refuses while transaction trash or recovery blobs are still present unless
    `--accept-fs` records that the operator verified the filesystem.
    """
    require_interprocess_lock()
    locks = acquire_mutation_locks(ctx, [ctx.project_id])
    conn = connect_journal(ctx)
    try:
        row = journal_row(conn, op_id)
        if row is None:
            raise WriteRefused("unknown journal op: " + op_id)
        status = str(row["status"] or "")
        if status == "complete":
            raise WriteRefused("cannot abandon a complete journal op: " + op_id)
        if status == JOURNAL_CLEANUP_PENDING:
            # v0.4.0 review: rollback refuses cleanup-pending; abandon must too —
            # the cleanup still owes work (trash/temps), so abandoning would record
            # a terminal status over an unfinished transaction.
            raise WriteRefused(
                "cannot abandon a cleanup-pending op — run journal retry first: "
                + op_id)
        try:
            payload = json.loads(row["payload"] or "{}")
        except (ValueError, TypeError):
            payload = {}
        trash_present = [
            str(d.get("trash")) for d in (payload.get("deletes") or [])
            if isinstance(d, dict) and d.get("trash")
            and Path(str(d.get("trash"))).exists()]
        rec_dir = ctx.plugin_data_dir / "recovery" / op_id
        rec_present = rec_dir.is_dir() and any(rec_dir.iterdir())
        if (trash_present or rec_present) and not accept_fs:
            raise WriteRefused(
                "trash/recovery still present; pass --accept-fs after verifying FS: "
                + (trash_present[0] if trash_present else str(rec_dir)))
        journal_step(conn, op_id, "abandoned", "abandoned")
        _finish_sensitive_cleanup(ctx, op_id, payload)
        return {"ok": True, "op_id": op_id, "status": "abandoned",
                "accepted_fs": accept_fs}
    finally:
        conn.close()
        release_locks(locks)


def _crash_publish(step: str) -> None:
    if os.environ.get("CM_CRASH_PUBLISH") == step:
        raise CrashSimulated(step)


def _publish_destinations(publishes: list) -> Tuple[int, list]:
    """Publish temps. `mode=create` is exclusive (no clobber). Idempotent.

    Returns (n_ok, bad_items). Destination existence is not success: when
    `sha256` is recorded, the dest bytes must match. A create dest that
    already has the expected hash is treated as already published (crash
    after same-dir hardlink, before temp unlink).
    """
    n = 0
    bad: list = []
    for item in publishes:
        tmp, dest = Path(item["tmp"]), Path(item["dest"])
        want = str(item.get("sha256") or "")
        mode = str(item.get("mode") or "replace")
        dest.parent.mkdir(parents=True, exist_ok=True)
        if mode == "create" and dest.exists() and want and _file_hash(dest) == want:
            tmp.unlink(missing_ok=True)
            try:
                os.chmod(str(dest), 0o600)
            except OSError:
                pass
            n += 1
            continue
        if tmp.exists():
            try:
                os.chmod(str(tmp), 0o600)
            except OSError:
                pass
            if mode == "create":
                # Same-dir hardlink: dest appears with full bytes or not at all.
                # Never create an empty visible inode (P0-7). No-hardlink FS
                # falls back to O_EXCL + full write in this process only — we
                # still never unlink a pre-existing empty dest on recover.
                linked = False
                try:
                    os.link(str(tmp), str(dest))
                    linked = True
                except FileExistsError:
                    if want and _file_hash(dest) == want:
                        tmp.unlink(missing_ok=True)
                        n += 1
                        continue
                    bad.append(item)
                    continue
                except OSError:
                    try:
                        data = tmp.read_bytes()
                        fd = os.open(str(dest), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                    except FileExistsError:
                        if want and _file_hash(dest) == want:
                            tmp.unlink(missing_ok=True)
                            n += 1
                            continue
                        bad.append(item)
                        continue
                    except OSError:
                        bad.append(item)
                        continue
                    try:
                        _write_fully(fd, data)
                    except OSError:
                        try:
                            os.close(fd)
                        except OSError:
                            pass
                        dest.unlink(missing_ok=True)
                        bad.append(item)
                        continue
                    os.close(fd)
                if linked:
                    _crash_publish("after_link")
                tmp.unlink(missing_ok=True)
            else:
                os.replace(str(tmp), str(dest))
                fsync_dir(dest.parent)
        if not dest.exists() or (want and _file_hash(dest) != want):
            bad.append(item)
            continue
        try:
            os.chmod(str(dest), 0o600)
        except OSError:
            pass
        n += 1
    return n, bad


def _op_id_safe(op_id: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in (op_id or "anon"))[:48]


def _op_sidecar(path: Path, op_id: str, kind: str) -> Path:
    """Same-directory sidecar named by op-id, never PID (PID reuse is a collision)."""
    return path.with_name(path.name + ".%s-%s" % (kind, _op_id_safe(op_id)))


def _trash_name(path: Path, op_id: str, i: int) -> Path:
    return path.parent / (".cm-trash-%s-%d" % (_op_id_safe(op_id), i))


def _restore_trash_records(records: list) -> dict:
    """Restore trash → dest. Structured; rename errors are not silent."""
    out: dict = {"restored": [], "missing": [], "errors": []}
    for rec in reversed(records):
        path = Path(str(rec.get("path") or ""))
        trash = Path(str(rec.get("trash") or ""))
        if not path or not trash:
            continue
        if not trash.exists():
            out["missing"].append(str(trash))
            continue
        if path.exists():
            q = _quarantine_dest(path)
            if q is None and path.exists():
                out["errors"].append({"path": str(path), "error": "occupied"})
                continue
        try:
            os.rename(str(trash), str(path))
            fsync_dir(path.parent)
            out["restored"].append(str(path))
        except OSError as e:
            out["errors"].append({"path": str(trash), "error": e.__class__.__name__})
    return out


def _restore_trash(deletes: Optional[list]) -> dict:
    recs = [d for d in (deletes or []) if isinstance(d, dict) and d.get("trash")]
    return _restore_trash_records(recs)


def _commit_trash(deletes: Optional[list]) -> dict:
    """Unlink transaction trash. Missing is ok; OSError is an error, never complete."""
    out: dict = {"deleted": [], "missing": [], "errors": []}
    for d in deletes or []:
        if not isinstance(d, dict):
            continue
        trash = Path(str(d.get("trash") or ""))
        if not trash:
            continue
        if not trash.exists():
            out["missing"].append(str(trash))
            continue
        try:
            trash.unlink()
            fsync_dir(trash.parent)
            if trash.exists():
                out["errors"].append({"path": str(trash), "error": "still-present"})
            else:
                out["deleted"].append(str(trash))
        except OSError as e:
            out["errors"].append({"path": str(trash), "error": e.__class__.__name__})
    return out


def _cleanup_temps(publishes: Optional[list]) -> dict:
    out: dict = {"deleted": [], "missing": [], "errors": []}
    for item in publishes or []:
        tmp = Path(str((item or {}).get("tmp") or ""))
        if not tmp:
            continue
        if not tmp.exists():
            out["missing"].append(str(tmp))
            continue
        try:
            tmp.unlink()
            fsync_dir(tmp.parent)
            out["deleted"].append(str(tmp))
        except OSError as e:
            out["errors"].append({"path": str(tmp), "error": e.__class__.__name__})
    return out


def _finish_sensitive_cleanup(ctx: Optional[StoreContext], op_id: str,
                              payload: dict) -> dict:
    """Delete trash, recovery blobs, and temps. Verify they are gone."""
    if os.environ.get("CM_CLEANUP_FAIL") == "1":
        return {"deleted": [], "missing": [], "errors": [
            {"path": "<injected>", "error": "EACCES"}]}
    trash = _commit_trash(payload.get("deletes") or [])
    if ctx is not None:
        rec = _cleanup_recovery(ctx, op_id)
    else:
        # v0.4.0 review: a missing StoreContext silently skipped recovery
        # cleanup (no error recorded → a caller could mark the row complete
        # with recovery blobs still on disk). Fail loud instead.
        rec = {"deleted": [], "missing": [], "errors": [
            {"path": "<recovery:" + str(op_id) + ">",
             "error": "no StoreContext — recovery cleanup skipped"}]}
    temps = _cleanup_temps(payload.get("publishes") or [])
    errors = list(trash.get("errors") or []) + list(rec.get("errors") or []) + list(
        temps.get("errors") or [])
    for d in payload.get("deletes") or []:
        if not isinstance(d, dict):
            continue
        p = Path(str(d.get("trash") or ""))
        if p and p.exists():
            errors.append({"path": str(p), "error": "still-present"})
    return {
        "deleted": list(trash.get("deleted") or []) + list(rec.get("deleted") or [])
        + list(temps.get("deleted") or []),
        "missing": list(trash.get("missing") or []) + list(rec.get("missing") or [])
        + list(temps.get("missing") or []),
        "errors": errors,
    }


def _apply_deletes(deletes: Optional[list], *, op_id: str = "") -> dict:
    """Rename delete targets to same-dir trash when the preimage still matches.

    Permanent unlink happens only in `_commit_trash` after registry COMMIT.
    Unreadable hashes and missing preimages on an existing file are errors
    (fail closed). A preimage mismatch does NOT trash. Partial rename rolls
    already-trashed entries back.
    """
    # v0.4.0 review: PID-based names are the exact convention this phase removed
    # (two processes can collide and an orphan is unattributable) — use a hash
    # name instead of resurrecting the PID fallback.
    oid = op_id or ("anon-" + hashlib.sha256(
        (os.getpid().to_bytes(4, "big") + int(time.time()).to_bytes(8, "big"))
    ).hexdigest()[:12])
    out: dict = {
        "deleted": [], "already_absent": [], "preimage_mismatch": [],
        "errors": [], "deletes": [],
    }
    items: list = []
    blocked = False
    for i, d in enumerate(deletes or []):
        if isinstance(d, dict):
            path = Path(str(d.get("path") or ""))
            pre = str(d.get("preimage") or d.get("sha256") or "")
            recorded = str(d.get("trash") or "")
        else:
            path = Path(d)
            pre = ""
            recorded = ""
        rec = {"path": str(path), "preimage": pre, "trash": recorded, "i": i}
        items.append(rec)
        if not path or str(path) in (".", "/"):
            out["errors"].append(str(path))
            blocked = True
            continue
        trash = Path(recorded) if recorded else _trash_name(path, oid, i)
        rec["trash"] = str(trash)
        if trash.is_file() and not path.exists():
            th = _file_hash(trash)
            if pre and th and th != pre:
                out["errors"].append(str(path))
                blocked = True
                continue
            out["deleted"].append(str(path))
            continue
        if not path.exists():
            out["already_absent"].append(str(path))
            rec["trash"] = recorded
            continue
        actual = _file_hash(path)
        if actual is None:
            out["errors"].append(str(path))
            blocked = True
            continue
        if not pre:
            out["errors"].append(str(path))
            blocked = True
            continue
        if actual != pre:
            out["preimage_mismatch"].append(str(path))
            blocked = True
            continue
    out["deletes"] = items
    if blocked:
        return out
    already = set(out["deleted"]) | set(out["already_absent"])
    renamed: list = []
    for rec in items:
        if rec["path"] in already:
            continue
        path = Path(rec["path"])
        trash = Path(rec.get("trash") or "")
        if not trash:
            continue
        try:
            if trash.exists():
                raise OSError(errno.EEXIST, "trash exists")
            os.rename(str(path), str(trash))
            try:
                os.chmod(str(trash), 0o600)
            except OSError:
                pass
            fsync_dir(path.parent)
            renamed.append(rec)
            out["deleted"].append(str(path))
        except OSError:
            _restore_trash_records(renamed)
            out["errors"].append(str(path))
            out["deleted"] = [s for s in out["deleted"] if s not in {r["path"] for r in renamed}]
            break
    out["deletes"] = items
    return out


def _dest_already_published(publishes: list) -> bool:
    """True when every journaled dest already has the recorded sha256."""
    if not publishes:
        return True
    for item in publishes:
        dest = Path(item.get("dest") or "")
        want = str(item.get("sha256") or "")
        if not want or not dest.exists() or _file_hash(dest) != want:
            return False
    return True


def _trashed_delete_matches(path_s: str, want: str, payload: dict,
                            op_id: str) -> bool:
    """True when this source is a journaled delete already in matching trash.

    After `after_trash` the original path is gone; its preimage lives in
    `.cm-trash-<op>-<n>`. That is not source drift.
    """
    deletes = payload.get("deletes") or []
    for i, d in enumerate(deletes or []):
        if isinstance(d, dict):
            p = str(d.get("path") or "")
            pre = str(d.get("preimage") or d.get("sha256") or "")
            trash_s = str(d.get("trash") or "")
        else:
            p = str(d)
            pre = ""
            trash_s = ""
        if p != path_s:
            continue
        trash = Path(trash_s) if trash_s else _trash_name(Path(p), op_id, i)
        if Path(p).exists() or not trash.is_file():
            return False
        th = _file_hash(trash)
        if want and th == want:
            return True
        if pre and th == pre:
            return True
        return False
    return False


def _journal_sources_ok(payload: dict, op_id: str = "") -> bool:
    """Re-check journaled source hashes before recovery publication.

    If every destination already has the expected hash, publication completed
    before the crash and a replaced source is not a conflict. A delete whose
    trash still matches the journaled preimage is complete-old of that path,
    not drift.
    """
    publishes = payload.get("publishes") or []
    if _dest_already_published(publishes):
        return True
    checks: list = []
    for s in payload.get("sources") or []:
        if isinstance(s, dict) and s.get("path"):
            checks.append((str(s["path"]), str(s.get("sha256") or "")))
    if not checks:
        expected = payload.get("expected_revisions") or {}
        if isinstance(expected, dict):
            checks = [(str(p), str(h)) for p, h in expected.items()]
    for path_s, want in checks:
        if _trashed_delete_matches(path_s, want, payload, op_id):
            continue
        if want == ABSENT:
            p = Path(path_s)
            if p.exists():
                return False
            continue
        if not want:
            return False
        actual = _file_hash(Path(path_s))
        if actual != want:
            return False
    return True


def _begin_registry(rconn: sqlite3.Connection) -> str:
    """Start a per-op registry transaction. Returns 'begin' or 'savepoint'."""
    try:
        rconn.execute("BEGIN IMMEDIATE")
        return "begin"
    except sqlite3.OperationalError:
        rconn.execute("SAVEPOINT cm_recover")
        return "savepoint"


def _commit_registry(rconn: sqlite3.Connection, how: str) -> None:
    if how == "savepoint":
        rconn.execute("RELEASE SAVEPOINT cm_recover")
    else:
        rconn.execute("COMMIT")


def _rollback_registry(rconn: sqlite3.Connection, how: str) -> None:
    try:
        if how == "savepoint":
            rconn.execute("ROLLBACK TO SAVEPOINT cm_recover")
            rconn.execute("RELEASE SAVEPOINT cm_recover")
        else:
            rconn.execute("ROLLBACK")
    except sqlite3.Error:
        pass


def _apply_journaled_tuples(rconn: sqlite3.Connection, payload: dict) -> None:
    for h in payload.get("holders") or []:
        record_holder(rconn, h[0], h[1], h[2], h[3], h[4])
    for f in payload.get("facts") or []:
        rconn.execute(
            "INSERT INTO facts(fact_id, stem, domain_id, canonical_path, revision, "
            "status, sensitivity) VALUES (?,?,?,?,?,?,?) "
            "ON CONFLICT(fact_id) DO UPDATE SET revision=excluded.revision, "
            "canonical_path=excluded.canonical_path, status=excluded.status, "
            "sensitivity=excluded.sensitivity",
            tuple(f),
        )
    for ts in payload.get("tombstones") or []:
        write_tombstone(rconn, *ts)


def _assert_registry_postconditions(rconn: sqlite3.Connection, payload: dict,
                                    stage: str = "pre") -> None:
    if os.environ.get("CM_FAIL_POSTCONDITION") == stage:
        raise WriteRefused("injected postcondition failure")
    for rop in payload.get("registry_ops") or []:
        if not isinstance(rop, dict):
            continue
        if (rop.get("op") in ("project_upsert", "project_domain_change")
                and str(rop.get("status") or "") == "enrolled"):
            assert_enrolled(rconn, str(rop.get("project_id") or ""),
                            str(rop.get("domain_id") or ""))
        if rop.get("op") == "project_rebind":
            assert_rebind_invariant(
                rconn, str(rop.get("project_id") or ""),
                str(rop.get("retire_id") or rop.get("alias_id") or ""))
        if (rop.get("op") == "domain_status_set"
                and str(rop.get("status") or "") == "deleted"):
            assert_domain_has_no_enrolled(rconn, str(rop.get("domain_id") or ""))


def recover_pending(conn: sqlite3.Connection, replay: Optional[Callable] = None,
                    ctx: Optional[StoreContext] = None,
                    registry_conn: Optional[sqlite3.Connection] = None,
                    op_id: Optional[str] = None) -> list:
    """Publish leftover temps, verify dest hashes, apply recorded registry rows.

    Replays a canonical-upsert only when the current StoreContext matches the
    operation's stored origin domain/project. A pending op with no temps that
    cannot be replayed is marked `abandoned`. A pending op whose origin does
    not match the current ctx is left pending (never completed against another
    store, never abandoned by a bystander command).
    """
    recovered = []
    own_rconn = False
    if registry_conn is not None:
        rconn = registry_conn
    elif ctx is not None:
        rconn = connect(db_path(ctx))
        own_rconn = True
    else:
        # Never use the journal DB as the registry (SCHEMA_SQL would mint
        # dummy facts/holders in journal.sqlite and mark complete).
        rconn = None
    try:
        for op in pending_ops(conn):
            if op_id and op["op_id"] != op_id:
                continue
            if str(op.get("status") or "") == JOURNAL_CLEANUP_PENDING:
                try:
                    payload_cp = json.loads(op["payload"] or "{}")
                except (ValueError, TypeError):
                    payload_cp = {}
                cleaned = _finish_sensitive_cleanup(ctx, str(op["op_id"]), payload_cp)
                if cleaned.get("errors"):
                    continue
                journal_step(conn, op["op_id"], "journal_complete", "complete")
                recovered.append(op["op_id"])
                continue
            payload = json.loads(op["payload"] or "{}")
            publishes = payload.get("publishes") or []
            deletes = payload.get("deletes") or []
            kind = str(op["kind"])
            origin_dom = str(payload.get("origin_domain_id") or "")
            origin_pid = str(payload.get("origin_project_id") or "")
            dest_dom = str(payload.get("dest") or "")
            alias_id = str(payload.get("alias") or "")
            old_id = str(payload.get("old") or "")
            if kind == "domain-transition":
                # Domain is the thing this op changes. Match this project and
                # either the origin or destination domain — never a foreign
                # project's pending enroll, and never an unenroll after the
                # operator has already enrolled elsewhere.
                domains = {d for d in (origin_dom, dest_dom) if d}
                ctx_matches = (
                    ctx is not None
                    and bool(origin_pid) and origin_pid == ctx.project_id
                    and ctx.domain_id in domains
                )
            elif kind == "project-rebind":
                ids = {i for i in (origin_pid, old_id, alias_id) if i}
                if ctx is not None and ctx.project_id not in ids and rconn is not None:
                    row = rconn.execute(
                        "SELECT project_id FROM project_aliases WHERE alias_id=?",
                        (origin_pid or alias_id,),
                    ).fetchone()
                    if row is not None:
                        ids.add(str(row["project_id"] or ""))
                ctx_matches = ctx is not None and ctx.project_id in ids
            else:
                ctx_matches = (
                    ctx is not None
                    and (not origin_dom or origin_dom == ctx.domain_id)
                    and (not origin_pid or origin_pid == ctx.project_id)
                )
            if (origin_dom or origin_pid) and ctx is None:
                continue
            if ctx is not None and (origin_dom or origin_pid) and not ctx_matches:
                continue
            has_reg = bool(payload.get("registry_ops") or payload.get("holders")
                           or payload.get("facts") or payload.get("tombstones"))
            if has_reg and rconn is None:
                continue
            if publishes or has_reg or deletes:
                try:
                    prevalidate_registry_ops(payload.get("registry_ops") or [])
                except WriteRefused:
                    continue
                if not _journal_sources_ok(payload, op_id=str(op["op_id"])):
                    _restore_trash(deletes)
                    journal_step(conn, op["op_id"],
                                 op.get("step") or "conflicted", "conflicted")
                    continue
                files_mutated = False
                how = None
                live_deletes = deletes
                try:
                    if rconn is not None and has_reg:
                        how = _begin_registry(rconn)
                        _apply_journaled_tuples(rconn, payload)
                        apply_registry_ops(rconn, payload.get("registry_ops") or [])
                        _assert_registry_postconditions(rconn, payload, stage="pre")
                        _assert_registry_postconditions(rconn, payload, stage="post")
                    del_out = _apply_deletes(deletes, op_id=op["op_id"])
                    live_deletes = del_out.get("deletes") or deletes
                    if del_out["deleted"]:
                        files_mutated = True
                    if del_out["preimage_mismatch"] or del_out["errors"]:
                        _restore_dest_preimages(
                            payload.get("dest_preimages") or [], publishes)
                        _restore_trash(live_deletes)
                        if how is not None and rconn is not None:
                            _rollback_registry(rconn, how)
                        journal_step(conn, op["op_id"], "failed", "failed")
                        continue
                    if publishes:
                        _n, bad = _publish_destinations(publishes)
                        del _n
                        files_mutated = True
                        if bad:
                            _restore_dest_preimages(
                                payload.get("dest_preimages") or [], publishes)
                            _restore_trash(live_deletes)
                            if how is not None and rconn is not None:
                                _rollback_registry(rconn, how)
                            journal_step(conn, op["op_id"], "failed", "failed")
                            continue
                    if rconn is not None and how is not None:
                        _commit_registry(rconn, how)
                        how = None
                    payload["deletes"] = live_deletes
                    _journal_put_payload(conn, op["op_id"], payload,
                                         step="cleanup_pending")
                    journal_step(conn, op["op_id"], "cleanup_pending",
                                 JOURNAL_CLEANUP_PENDING)
                    cleaned = _finish_sensitive_cleanup(
                        ctx, str(op["op_id"]), payload)
                    if cleaned.get("errors"):
                        continue
                    journal_step(conn, op["op_id"], "journal_complete", "complete")
                    recovered.append(op["op_id"])
                    if ctx is not None:
                        # Phase-5 closeout: crash-recovery republishes can write
                        # canonical files — invalidate like transact does.
                        try:
                            from facts_manifest import invalidate_for_paths
                            invalidate_for_paths(
                                ctx.plugin_data_dir,
                                [d.get("path") for d in
                                 (payload.get("deletes") or [])
                                 if isinstance(d, dict)] + [
                                    p.get("path") for p in publishes
                                    if isinstance(p, dict)])
                        except Exception:
                            pass
                except (WriteRefused, sqlite3.Error):
                    if files_mutated:
                        try:
                            _restore_dest_preimages(
                                payload.get("dest_preimages") or [], publishes)
                            _restore_trash(live_deletes)
                        except WriteRefused:
                            pass
                    journal_step(conn, op["op_id"], "conflicted", "conflicted")
                    if how is not None and rconn is not None:
                        _rollback_registry(rconn, how)
                    continue
                continue
            if replay is not None:
                replay(kind, payload, op["step"])
                if rconn is not None:
                    try:
                        rconn.commit()
                    except sqlite3.Error:
                        continue
                journal_step(conn, op["op_id"], "cleanup_pending",
                             JOURNAL_CLEANUP_PENDING)
                cleaned = _finish_sensitive_cleanup(
                    ctx, str(op["op_id"]), payload)
                if cleaned.get("errors"):
                    continue
                journal_step(conn, op["op_id"], "journal_complete", "complete")
                recovered.append(op["op_id"])
                continue
            replayable_upsert = bool(
                ctx_matches and payload.get("stem") and payload.get("text")
                and kind == "canonical-upsert")
            if replayable_upsert and ctx is not None:
                # Nested transact() would deadlock on flock (recover runs while
                # the caller may already hold mutation locks). Replay only via
                # leftover temps (publishes path above). Pre-temp crashes stay
                # pending → complete-old.
                continue
            journal_step(conn, op["op_id"], op.get("step") or "journal_start", "abandoned")
            recovered.append(op["op_id"])
        conn.commit()
        return recovered
    finally:
        if own_rconn and rconn is not None:
            try:
                rconn.close()
            except sqlite3.Error:
                pass


def transact(ctx: StoreContext, kind: str, payload: dict, mutate: Callable,
             *, extra_project_ids: Optional[list] = None,
             extra_domains: Optional[list] = None,
             crash_after: Optional[str] = None,
             expected_revisions: Optional[dict] = None,
             skip_recover: bool = False) -> dict:
    """JOURNAL_STEPS mutation. `crash_after=NAME` means the named step completed, then stop.

    Registry writes live on a second connection and COMMIT only after dest hashes
    are published. Journal rows (origin context + dest sha256) commit earlier so
    crash recovery can roll forward files without trusting dest existence.
    """
    import hashlib
    from store_context import WriteRefused
    assert_mutation_allowed(ctx)
    if kind not in DOMAIN_LIFECYCLE_KINDS:
        assert_domain_writable(ctx)
    require_interprocess_lock()
    crash = crash_after or os.environ.get("CM_CRASH_AFTER") or ""
    dbp = db_path(ctx)
    conn = connect_journal(ctx)
    rconn = connect(dbp)
    rconn.isolation_level = None
    recovered: list = []
    pids = [ctx.project_id] + list(extra_project_ids or [])
    locks = acquire_mutation_locks(ctx, pids, extra_domains=extra_domains)
    op_id: Optional[str] = None
    temps: dict = {}
    registry_committed = False
    try:
        def _maybe_crash(step: str) -> None:
            if crash == step:
                # After registry COMMIT the row is committed-cleanup-pending.
                # Do not clobber it back to pending or recovery would republish.
                if op_id and not registry_committed:
                    journal_step(conn, op_id, step, "pending")
                raise CrashSimulated(step)

        if not skip_recover:
            recovered = recover_pending(conn, ctx=ctx, registry_conn=rconn)
        _maybe_crash("lock_domain")
        _maybe_crash("lock_projects")
        snaps = {}
        for p, h in (expected_revisions or {}).items():
            if h == ABSENT:
                snaps[p] = ABSENT
                continue
            if not (isinstance(h, str) and len(h) >= 16):
                raise WriteRefused(
                    "expected hash required (None is illegal after classify): " + p)
            snaps[p] = h
        _maybe_crash("record_revisions")
        payload = dict(payload)
        payload.setdefault("origin_profile_id", ctx.profile_id)
        payload.setdefault("origin_domain_id", ctx.domain_id)
        payload.setdefault("origin_project_id", ctx.project_id)
        payload.setdefault("op_version", 3)
        payload.setdefault("origin_registry_state", getattr(ctx, "registry_state", ""))
        op_id = journal_insert(conn, kind, payload, "journal_start")
        _maybe_crash("journal_start")
        rconn.execute("BEGIN")
        upsert_project(rconn, ctx)
        result = mutate(rconn, temps)
        if not isinstance(result, dict):
            result = {"value": result}
        for p, h in (result.get("expected_revisions") or {}).items():
            if h == ABSENT:
                snaps[str(p)] = ABSENT
            elif isinstance(h, str) and len(h) >= 16:
                snaps[str(p)] = h
            elif isinstance(h, str):
                # review fix: the PARAMETER path refuses a short hash; the mutate-
                # returned path silently dropped it (fail-open). Refuse identically.
                raise WriteRefused(
                    f"mutate returned an invalid expected_revisions hash for {p} ({h!r})")
        deletes = list(result.get("deletes") or [])
        publishes = []
        for dest_s, content in temps.items():
            dest = Path(dest_s)
            dest.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(content, (bytes, bytearray)):
                data = bytes(content)
            else:
                text = content if str(content).endswith("\n") else str(content) + "\n"
                data = text.encode("utf-8")
            tmp = _op_sidecar(dest, op_id or "anon", "tmp")
            tmp.unlink(missing_ok=True)
            _write_exclusive(tmp, data)
            publishes.append({
                "tmp": str(tmp), "dest": str(dest),
                "sha256": hashlib.sha256(data).hexdigest(),
                "mode": str((result.get("dest_modes") or {}).get(dest_s) or "replace"),
            })
        payload["publishes"] = publishes
        norm_deletes: list = []
        for d in deletes:
            if isinstance(d, dict):
                path_s = str(d.get("path") or "")
                pre = str(d.get("preimage") or d.get("sha256") or "")
                if Path(path_s).exists() and not pre:
                    h = _file_hash(Path(path_s))
                    if not h:
                        rconn.execute("ROLLBACK")
                        raise WriteRefused("cannot hash delete preimage: " + path_s)
                    pre = h
                norm_deletes.append({"path": path_s, "preimage": pre})
            else:
                path_s = str(d)
                if Path(path_s).exists():
                    h = _file_hash(Path(path_s))
                    if not h:
                        rconn.execute("ROLLBACK")
                        raise WriteRefused("cannot hash delete preimage: " + path_s)
                    norm_deletes.append({"path": path_s, "preimage": h})
                else:
                    norm_deletes.append({"path": path_s, "preimage": ""})
        payload["deletes"] = norm_deletes
        payload["holders"] = []
        payload["facts"] = []
        payload["tombstones"] = []
        payload["registry_ops"] = list(result.get("registry_ops") or [])
        payload["sources"] = [{"path": p, "sha256": h} for p, h in snaps.items()]
        payload["expected_revisions"] = snaps
        rec_dir = _recovery_dir(ctx, op_id)
        try:
            payload["dest_preimages"] = _snapshot_dest_preimages(
                publishes, recovery=rec_dir, op_id=op_id or "")
        except WriteRefused:
            for item in publishes:
                Path(item["tmp"]).unlink(missing_ok=True)
            rconn.execute("ROLLBACK")
            raise
        try:
            prevalidate_registry_ops(payload.get("registry_ops") or [])
            apply_registry_ops(rconn, payload.get("registry_ops") or [])
            _assert_registry_postconditions(rconn, payload, stage="pre")
            _assert_registry_postconditions(rconn, payload, stage="post")
        except WriteRefused:
            for item in publishes:
                Path(item["tmp"]).unlink(missing_ok=True)
            rconn.execute("ROLLBACK")
            journal_step(conn, op_id, "conflicted", "conflicted")
            raise
        dest_set = {str(item["dest"]) for item in publishes}
        overlap = dest_set & _failed_owned_dests(conn)
        if overlap:
            for item in publishes:
                Path(item["tmp"]).unlink(missing_ok=True)
            rconn.execute("ROLLBACK")
            journal_step(conn, op_id, "abandoned", "abandoned")
            raise WriteRefused(
                "failed journal op owns dests; abandon_failed first: "
                + ", ".join(sorted(overlap)[:8]))
        _journal_put_payload(conn, op_id, payload, step="prepare_temps")
        _maybe_crash("prepare_temps")

        def _fail_after_persist(msg: str, *, restore: bool,
                                status: str = "failed") -> None:
            _restore_trash(payload.get("deletes") or [])
            if restore:
                payload["dests_mutated"] = True
                _journal_put_payload(conn, op_id, payload)
                _restore_dest_preimages(
                    payload.get("dest_preimages") or [], publishes)
            journal_step(conn, op_id, status, status)
            rconn.execute("ROLLBACK")
            raise WriteRefused(msg)

        for p, h in snaps.items():
            if h == ABSENT:
                if Path(p).exists():
                    _fail_after_persist("expected absent: " + p, restore=False)
                continue
            if _file_hash(Path(p)) != h:
                _fail_after_persist("source changed during transaction: " + p,
                                    restore=False)
        journal_step(conn, op_id, "verify_unchanged", "pending")
        _maybe_crash("verify_unchanged")
        del_out = _apply_deletes(payload["deletes"], op_id=op_id)
        if del_out["preimage_mismatch"] or del_out["errors"]:
            _fail_after_persist(
                "delete preimage mismatch; registry not committed: "
                + ", ".join(del_out["preimage_mismatch"] + del_out["errors"]),
                restore=False)
        payload["deletes"] = del_out.get("deletes") or payload["deletes"]
        _journal_put_payload(conn, op_id, payload, step="after_trash")
        _maybe_crash("after_trash")
        _n_ok, bad = _publish_destinations(publishes)
        del _n_ok
        journal_step(conn, op_id, "after_dests", "pending")
        _maybe_crash("after_dests")
        if bad:
            _fail_after_persist(
                "destination hash mismatch; deletes skipped: "
                + ", ".join(str(b.get("dest")) for b in bad), restore=True)
        for item in publishes:
            dest = Path(item["dest"])
            want = str(item.get("sha256") or "")
            if want and _file_hash(dest) != want:
                _fail_after_persist(
                    "file postcondition dest hash mismatch: " + str(dest),
                    restore=True)
        for d in payload["deletes"]:
            dp = Path(str(d.get("path") if isinstance(d, dict) else d))
            if dp.exists():
                _fail_after_persist(
                    "file postcondition delete still present: " + str(dp),
                    restore=True)
        journal_step(conn, op_id, "publish", "pending")
        _maybe_crash("publish")
        try:
            rconn.execute("COMMIT")
        except sqlite3.Error as e:
            _fail_after_persist(
                "registry commit failed: " + str(e), restore=True,
                status="conflicted")
        registry_committed = True
        journal_step(conn, op_id, "cleanup_pending", JOURNAL_CLEANUP_PENDING)
        _maybe_crash("commit_registry")
        _maybe_crash("cleanup_pending")
        cleaned = _finish_sensitive_cleanup(ctx, op_id, payload)
        if cleaned.get("errors"):
            raise WriteRefused(
                "committed cleanup pending: "
                + ", ".join(str(e.get("path") or e) for e in cleaned["errors"][:8]))
        journal_step(conn, op_id, "journal_complete", "complete")
        _maybe_crash("journal_complete")
        # Phase-5 closeout: canonical writes invalidate the facts manifest here —
        # after publish + COMMIT, still under the mutation locks, so a concurrent
        # rebuild cannot repersist pre-edit rows. Best-effort (a missed unlink
        # only costs one spurious full read — per-row freshness is the net).
        try:
            from facts_manifest import invalidate_for_paths
            invalidate_for_paths(
                ctx.plugin_data_dir,
                list((payload.get("publishes") or []) if isinstance(payload, dict)
                     else []) + [d.get("path") for d in (payload.get("deletes") or [])
                                 if isinstance(d, dict)])
        except Exception:
            pass
        return {"ok": True, "op_id": op_id, "recovered": recovered, "result": result,
                "expected_revisions": snaps, "cleanup": cleaned}
    except Exception:
        if not registry_committed:
            try:
                rconn.execute("ROLLBACK")
            except sqlite3.Error:
                pass
        raise
    finally:
        release_locks(locks)
        conn.close()
        rconn.close()


def stable_fact_id(domain: str, stem: str, schema_version: str = "2") -> str:
    from fact_schema import stable_fact_id as _sf
    return _sf(domain, stem, schema_version)


_RECORD_HOLDER_SQL = (
    "INSERT INTO holders(fact_id, project_id, base_revision, canonical_revision, semantic_hash) "
    "VALUES (?,?,?,?,?) ON CONFLICT(fact_id, project_id) DO UPDATE SET "
    "base_revision=excluded.base_revision, canonical_revision=excluded.canonical_revision, "
    "semantic_hash=excluded.semantic_hash"
)


def record_holders(conn: sqlite3.Connection, rows: "list[tuple]") -> None:
    """executemany form of record_holder — one statement for N rows. A 10k-canonical
    warm pull re-records every in-sync holder; N statements cost ~50ms of the pull
    (v0.4.2 P3 measured). `rows` is [(fact_id, project_id, base_rev, canon_rev, sem)]."""
    conn.executemany(_RECORD_HOLDER_SQL, rows)


def record_holder(conn: sqlite3.Connection, fact_id: str, project_id: str,
                  base_rev: str, canon_rev: str, sem: str) -> None:
    record_holders(conn, [(fact_id, project_id, base_rev, canon_rev, sem)])


def record_conflict(conn: sqlite3.Connection, stem: str, project_id: str, decision: dict,
                    domain_id: str = "", fact_id: str = "") -> None:
    """Insert or refresh the open conflict row for (stem, project, domain). Never duplicates."""
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    did = domain_id or ""
    fid = fact_id or ""
    row = conn.execute(
        "SELECT id FROM conflicts WHERE fact_stem=? AND project_id=? AND resolved='' "
        "AND COALESCE(domain_id,'')=?",
        (stem, project_id, did),
    ).fetchone()
    if row:
        conn.execute(
            "UPDATE conflicts SET action=?, local_hash=?, canonical_hash=?, created_at=?, "
            "domain_id=?, fact_id=? WHERE id=?",
            (decision.get("action"), decision.get("local"), decision.get("canonical"),
             now, did, fid, row["id"]),
        )
        return
    try:
        conn.execute(
            "INSERT INTO conflicts(fact_stem, project_id, action, local_hash, canonical_hash, "
            "created_at, resolved, domain_id, fact_id) VALUES (?,?,?,?,?,?,?,?,?)",
            (stem, project_id, decision.get("action"), decision.get("local"),
             decision.get("canonical"), now, "", did, fid),
        )
    except sqlite3.IntegrityError:
        conn.execute(
            "UPDATE conflicts SET action=?, local_hash=?, canonical_hash=?, created_at=?, "
            "fact_id=? WHERE fact_stem=? AND project_id=? AND resolved='' "
            "AND COALESCE(domain_id,'')=?",
            (decision.get("action"), decision.get("local"), decision.get("canonical"),
             now, fid, stem, project_id, did),
        )


def mark_conflict_resolved(conn: sqlite3.Connection, stem: str, project_id: str,
                           how: str, domain_id: str = "") -> int:
    if domain_id:
        cur = conn.execute(
            "UPDATE conflicts SET resolved=? WHERE fact_stem=? AND project_id=? "
            "AND resolved='' AND COALESCE(domain_id,'') IN ('', ?)",
            (how, stem, project_id, domain_id),
        )
    else:
        cur = conn.execute(
            "UPDATE conflicts SET resolved=? WHERE fact_stem=? AND project_id=? AND resolved=''",
            (how, stem, project_id),
        )
    return int(cur.rowcount or 0)


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
