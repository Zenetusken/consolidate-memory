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
    from identifiers import validate_domain_id
    from store_context import WriteRefused
    d = validate_domain_id(domain)
    current = enrolled_domain(conn, ctx.project_id)
    if current and current != d:
        raise WriteRefused(
            f"already enrolled in {current}; use `cm project move-domain --to {d}`")
    upsert_project(conn, ctx)
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    conn.execute(
        "UPDATE projects SET domain_id=?, status='enrolled', last_seen=? WHERE project_id=?",
        (d, now, ctx.project_id),
    )
    conn.commit()


def unenroll_project(conn: sqlite3.Connection, project_id: str) -> None:
    conn.execute(
        "UPDATE projects SET status='active', domain_id='unknown' WHERE project_id=?",
        (project_id,),
    )
    conn.commit()


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


def acquire_mutation_locks(ctx: StoreContext, project_ids: list) -> list:
    """Domain lock, then project locks in sorted ID order. Returns acquired locks."""
    from identifiers import IdentifierRefused, safe_child, validate_domain_id, validate_project_id
    require_interprocess_lock()
    locks: list = []
    try:
        dname = validate_domain_id(ctx.domain_id or "unknown", allow_unknown=True)
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


def _publish_destinations(publishes: list) -> Tuple[int, list]:
    """os.replace leftover same-directory temps. Does NOT delete. Idempotent.

    Returns (n_ok, bad_items). Destination existence is not success: when
    `sha256` is recorded, the dest bytes must match.
    """
    n = 0
    bad: list = []
    for item in publishes:
        tmp, dest = Path(item["tmp"]), Path(item["dest"])
        want = str(item.get("sha256") or "")
        if tmp.exists():
            dest.parent.mkdir(parents=True, exist_ok=True)
            try:
                os.chmod(str(tmp), 0o600)
            except OSError:
                pass
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


def _apply_deletes(deletes: Optional[list]) -> None:
    """Delete only when a recorded preimage still matches (or no preimage given)."""
    for d in deletes or []:
        if isinstance(d, dict):
            path = Path(str(d.get("path") or ""))
            pre = str(d.get("preimage") or d.get("sha256") or "")
            if not path or str(path) in (".", "/"):
                continue
            if pre and _file_hash(path) not in (pre, None):
                continue
            path.unlink(missing_ok=True)
        else:
            Path(d).unlink(missing_ok=True)


def _publish_temps(publishes: list, deletes: Optional[list] = None) -> int:
    """Publish destinations, then delete only if every dest verified (ADR 010)."""
    n, bad = _publish_destinations(publishes)
    if bad:
        return n
    _apply_deletes(deletes)
    return n


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
            ctx_matches = (
                ctx is not None
                and (not origin_dom or origin_dom == ctx.domain_id)
                and (not origin_pid or origin_pid == ctx.project_id)
            )
            if ctx is not None and (origin_dom or origin_pid) and not ctx_matches:
                continue
            if publishes:
                _n, bad = _publish_destinations(publishes)
                del _n
                if bad:
                    continue
                _apply_deletes(deletes)
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
                try:
                    rconn.commit()
                except sqlite3.Error:
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
    locks = acquire_mutation_locks(ctx, pids)
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
            if not (isinstance(h, str) and len(h) >= 16):
                from store_context import WriteRefused as _WRHash
                raise _WRHash("expected hash required (None is illegal after classify): " + p)
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
            })
        payload["publishes"] = publishes
        payload["deletes"] = [
            {"path": d, "preimage": _file_hash(Path(d))} if isinstance(d, str) else d
            for d in deletes
        ]
        payload["holders"] = list(result.get("holders") or [])
        payload["facts"] = list(result.get("facts") or [])
        payload["tombstones"] = list(result.get("tombstones") or [])
        conn.execute("UPDATE journal SET payload=?, step=? WHERE op_id=?",
                     (json.dumps(payload, sort_keys=True), "prepare_temps", op_id))
        conn.commit()
        _maybe_crash("prepare_temps")
        for p, h in snaps.items():
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
        _apply_deletes(payload["deletes"])
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
