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

class CrashSimulated(RuntimeError):
    """Test-only: mutation stopped after a named journal step."""


ABSENT = "ABSENT"
REGISTRY_OP_KINDS = frozenset({
    "project_upsert", "project_domain_change", "fact_upsert", "fact_status_change",
    "fact_delete", "holder_upsert", "holder_delete", "tombstone_upsert",
    "conflict_upsert", "conflict_resolve", "migration_state_set", "project_alias",
    "project_rebind",
})


def db_path(ctx: Optional[StoreContext] = None, environ: Optional[dict] = None) -> Path:
    if ctx is not None:
        return ctx.plugin_data_dir / "control.sqlite"
    return plugin_data_dir(environ=environ) / "control.sqlite"


def connect_journal(ctx: Optional[StoreContext] = None,
                    environ: Optional[dict] = None) -> sqlite3.Connection:
    conn = connect(journal_db_path(ctx, environ))
    conn.executescript(JOURNAL_ONLY_SQL)
    return conn


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
    created_at TEXT
);
"""


def connect(path: Path) -> sqlite3.Connection:
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
    conn.executescript(SCHEMA_SQL)
    _migrate_schema(conn)
    return conn


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
    """Additive columns for DBs created before session_dir existed."""
    cols = {str(r[1]) for r in conn.execute("PRAGMA table_info(projects)").fetchall()}
    if "session_dir" not in cols:
        conn.execute("ALTER TABLE projects ADD COLUMN session_dir TEXT")
        conn.commit()
    conn.execute(
        "CREATE TABLE IF NOT EXISTS project_aliases ("
        "alias_id TEXT PRIMARY KEY, project_id TEXT NOT NULL)")
    conn.commit()


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


def apply_registry_ops(conn: sqlite3.Connection, ops: list) -> None:
    """Replay typed journal v3 registry_ops (ADR 010). Unknown kinds refuse."""
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
            elif fid and pid:
                conn.execute("DELETE FROM holders WHERE fact_id=? AND project_id=?",
                             (fid, pid))
        elif kind == "tombstone_upsert":
            write_tombstone(conn, str(op.get("fact_id") or ""), str(op.get("stem") or ""),
                            str(op.get("domain_id") or ""), str(op.get("reason") or ""),
                            str(op.get("replacement_id") or ""),
                            str(op.get("grace_until") or ""))
        elif kind == "conflict_upsert":
            record_conflict(conn, str(op.get("stem") or op.get("fact_stem") or ""),
                            str(op.get("project_id") or ""),
                            {"action": op.get("action"), "local": op.get("local_hash"),
                             "canonical": op.get("canonical_hash")})
        elif kind == "conflict_resolve":
            conn.execute(
                "UPDATE conflicts SET resolved=? WHERE fact_stem=? AND project_id=? "
                "AND resolved=''",
                (str(op.get("resolved") or "resolved"),
                 str(op.get("stem") or op.get("fact_stem") or ""),
                 str(op.get("project_id") or "")))
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
        "SELECT op_id, kind, payload, step, status FROM journal WHERE status='pending'"
    ).fetchall()
    return [dict(r) for r in rows]


def _file_hash(path: Path) -> Optional[str]:
    import hashlib
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def _write_fully(fd: int, data: bytes) -> None:
    """Write every byte; fsync. One os.write() can be short."""
    view = memoryview(data)
    sent = 0
    while sent < len(view):
        n = os.write(fd, view[sent:])
        if n <= 0:
            raise OSError("short write")
        sent += n
    try:
        os.fsync(fd)
    except OSError:
        pass


def _crash_publish(step: str) -> None:
    if os.environ.get("CM_CRASH_PUBLISH") == step:
        raise CrashSimulated(step)


def _publish_destinations(publishes: list) -> Tuple[int, list]:
    """Publish temps. `mode=create` is exclusive (no clobber). Idempotent.

    Returns (n_ok, bad_items). Destination existence is not success: when
    `sha256` is recorded, the dest bytes must match. A create dest that
    already has the expected hash is treated as already published (crash
    after O_EXCL write, before temp unlink).
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
                data = tmp.read_bytes()
                try:
                    fd = os.open(str(dest), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                except FileExistsError:
                    if want and _file_hash(dest) == want:
                        tmp.unlink(missing_ok=True)
                        n += 1
                        continue
                    bad.append(item)
                    continue
                try:
                    _crash_publish("after_create")
                    _write_fully(fd, data)
                    _crash_publish("after_write")
                finally:
                    os.close(fd)
                _crash_publish("after_close")
                _crash_publish("before_unlink")
                tmp.unlink(missing_ok=True)
            else:
                os.replace(str(tmp), str(dest))
        if not dest.exists() or (want and _file_hash(dest) != want):
            bad.append(item)
            continue
        try:
            os.chmod(str(dest), 0o600)
        except OSError:
            pass
        n += 1
    return n, bad


def _apply_deletes(deletes: Optional[list]) -> dict:
    """Delete only when a recorded preimage still matches.

    A preimage mismatch does NOT delete and is reported so the caller can
    refuse to complete the journal (ADR 010).
    """
    out: dict = {"deleted": [], "already_absent": [], "preimage_mismatch": [], "errors": []}
    for d in deletes or []:
        if isinstance(d, dict):
            path = Path(str(d.get("path") or ""))
            pre = str(d.get("preimage") or d.get("sha256") or "")
            if not path or str(path) in (".", "/"):
                out["errors"].append(str(path))
                continue
            if not path.exists():
                out["already_absent"].append(str(path))
                continue
            if pre and _file_hash(path) not in (pre, None):
                out["preimage_mismatch"].append(str(path))
                continue
            try:
                path.unlink()
                out["deleted"].append(str(path))
            except OSError:
                out["errors"].append(str(path))
        else:
            path = Path(d)
            if not path.exists():
                out["already_absent"].append(str(path))
                continue
            try:
                path.unlink()
                out["deleted"].append(str(path))
            except OSError:
                out["errors"].append(str(path))
    return out


def _publish_temps(publishes: list, deletes: Optional[list] = None) -> int:
    """Publish destinations, then delete only if every dest verified (ADR 010)."""
    n, bad = _publish_destinations(publishes)
    if bad:
        return n
    _apply_deletes(deletes)
    return n


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


def _apply_legacy_registry_rows(rconn: sqlite3.Connection, payload: dict) -> None:
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


def _assert_registry_postconditions(rconn: sqlite3.Connection, payload: dict) -> None:
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


def recover_pending(conn: sqlite3.Connection, replay: Optional[Callable] = None,
                    ctx: Optional[StoreContext] = None,
                    registry_conn: Optional[sqlite3.Connection] = None) -> list:
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
        rconn = conn
    try:
        for op in pending_ops(conn):
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
                if ctx is not None and ctx.project_id not in ids:
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
            if ctx is not None and (origin_dom or origin_pid) and not ctx_matches:
                continue
            has_reg = bool(payload.get("registry_ops") or payload.get("holders")
                           or payload.get("facts") or payload.get("tombstones")
                           or deletes)
            if publishes or has_reg:
                if publishes:
                    _n, bad = _publish_destinations(publishes)
                    del _n
                    if bad:
                        continue
                del_out = _apply_deletes(deletes)
                if del_out["preimage_mismatch"] or del_out["errors"]:
                    continue
                how = _begin_registry(rconn)
                try:
                    _apply_legacy_registry_rows(rconn, payload)
                    apply_registry_ops(rconn, payload.get("registry_ops") or [])
                    _assert_registry_postconditions(rconn, payload)
                    _commit_registry(rconn, how)
                except (WriteRefused, sqlite3.Error):
                    _rollback_registry(rconn, how)
                    continue
                journal_step(conn, op["op_id"], "journal_complete", "complete")
                recovered.append(op["op_id"])
                continue
            if replay is not None:
                replay(kind, payload, op["step"])
                try:
                    rconn.commit()
                except sqlite3.Error:
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
        if own_rconn:
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
    require_interprocess_lock()
    crash = crash_after or os.environ.get("CM_CRASH_AFTER") or ""
    dbp = db_path(ctx)
    conn = connect(journal_db_path(ctx))
    conn.executescript(JOURNAL_ONLY_SQL)
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
                if op_id:
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
            elif isinstance(h, str) and (h == ABSENT or len(h) >= 16):
                snaps[str(p)] = h
        deletes = list(result.get("deletes") or [])
        publishes = []
        for dest_s, content in temps.items():
            dest = Path(dest_s)
            dest.parent.mkdir(parents=True, exist_ok=True)
            text = content if content.endswith("\n") else content + "\n"
            tmp = dest.with_suffix(dest.suffix + f".tmp{os.getpid()}")
            tmp.write_text(text, encoding="utf-8")
            publishes.append({
                "tmp": str(tmp), "dest": str(dest),
                "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                "mode": str((result.get("dest_modes") or {}).get(dest_s) or "replace"),
            })
        payload["publishes"] = publishes
        payload["deletes"] = [
            {"path": d, "preimage": _file_hash(Path(d))} if isinstance(d, str) else d
            for d in deletes
        ]
        payload["holders"] = list(result.get("holders") or [])
        payload["facts"] = list(result.get("facts") or [])
        payload["tombstones"] = list(result.get("tombstones") or [])
        payload["registry_ops"] = list(result.get("registry_ops") or [])
        payload["sources"] = [{"path": p, "sha256": h} for p, h in snaps.items()]
        payload["expected_revisions"] = snaps
        conn.execute("UPDATE journal SET payload=?, step=? WHERE op_id=?",
                     (json.dumps(payload, sort_keys=True), "prepare_temps", op_id))
        conn.commit()
        _maybe_crash("prepare_temps")
        for p, h in snaps.items():
            if h == ABSENT:
                if Path(p).exists():
                    for item in publishes:
                        Path(item["tmp"]).unlink(missing_ok=True)
                    rconn.execute("ROLLBACK")
                    raise WriteRefused("expected absent: " + p)
                continue
            if _file_hash(Path(p)) != h:
                for item in publishes:
                    Path(item["tmp"]).unlink(missing_ok=True)
                rconn.execute("ROLLBACK")
                raise WriteRefused("source changed during transaction: " + p)
        journal_step(conn, op_id, "verify_unchanged", "pending")
        _maybe_crash("verify_unchanged")
        _n_ok, bad = _publish_destinations(publishes)
        del _n_ok
        if bad:
            rconn.execute("ROLLBACK")
            raise WriteRefused("destination hash mismatch; deletes skipped: "
                               + ", ".join(str(b.get("dest")) for b in bad))
        del_out = _apply_deletes(payload["deletes"])
        if del_out["preimage_mismatch"] or del_out["errors"]:
            rconn.execute("ROLLBACK")
            raise WriteRefused(
                "delete preimage mismatch; registry not committed: "
                + ", ".join(del_out["preimage_mismatch"] + del_out["errors"]))
        for item in publishes:
            dest = Path(item["dest"])
            want = str(item.get("sha256") or "")
            if want and _file_hash(dest) != want:
                rconn.execute("ROLLBACK")
                raise WriteRefused("file postcondition dest hash mismatch: " + str(dest))
        for d in payload["deletes"]:
            dp = Path(str(d.get("path") if isinstance(d, dict) else d))
            if dp.exists():
                rconn.execute("ROLLBACK")
                raise WriteRefused("file postcondition delete still present: " + str(dp))
        try:
            apply_registry_ops(rconn, payload.get("registry_ops") or [])
            _assert_registry_postconditions(rconn, payload)
        except WriteRefused:
            rconn.execute("ROLLBACK")
            raise
        journal_step(conn, op_id, "publish", "pending")
        _maybe_crash("publish")
        rconn.execute("COMMIT")
        registry_committed = True
        _maybe_crash("commit_registry")
        journal_step(conn, op_id, "journal_complete", "complete")
        _maybe_crash("journal_complete")
        return {"ok": True, "op_id": op_id, "recovered": recovered, "result": result,
                "expected_revisions": snaps}
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
    """Insert or refresh the open conflict row for (stem, project). Never duplicates."""
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    row = conn.execute(
        "SELECT id FROM conflicts WHERE fact_stem=? AND project_id=? AND resolved=''",
        (stem, project_id),
    ).fetchone()
    if row:
        conn.execute(
            "UPDATE conflicts SET action=?, local_hash=?, canonical_hash=?, created_at=? "
            "WHERE id=?",
            (decision.get("action"), decision.get("local"), decision.get("canonical"),
             now, row["id"]),
        )
        return
    conn.execute(
        "INSERT INTO conflicts(fact_stem, project_id, action, local_hash, canonical_hash, "
        "created_at, resolved) VALUES (?,?,?,?,?,?,?)",
        (stem, project_id, decision.get("action"), decision.get("local"),
         decision.get("canonical"), now, ""),
    )


def mark_conflict_resolved(conn: sqlite3.Connection, stem: str, project_id: str,
                           how: str) -> int:
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
