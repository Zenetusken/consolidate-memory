#!/usr/bin/env python3
"""Bounded operational history in ${CLAUDE_PLUGIN_DATA}. Native plane stays facts-only."""
from __future__ import annotations

import uuid
import json
import os
import time
from pathlib import Path
from typing import Optional

EVENT_RETENTION_DAYS = 90
CYCLE_CAP = 500


def _now_epoch() -> float:
    return time.time()


def operational_dir(plugin_data: Path, project_id: str) -> Path:
    from identifiers import IdentifierRefused, safe_child, validate_project_id
    try:
        pid = validate_project_id(project_id)
    except IdentifierRefused:
        # slot-keyed logs use the Claude projects-slot, not p_<sha>
        pid = project_id
        if not pid or "/" in pid or "\\" in pid or pid in (".", "..") or "\x00" in pid:
            raise
    return safe_child(plugin_data / "ops", pid)


CYCLE_LOG_NAME = ".consolidation-log.jsonl"
MUTATION_LOG_NAME = ".mutation-log.jsonl"
FLEET_LEDGER_NAME = "fleet-usage.jsonl"


def _config_root_from_native(native_store: Path) -> Optional[Path]:
    """If `native_store` is <config>/projects/<slot>/memory, return <config>."""
    try:
        p = native_store.resolve()
    except OSError:
        p = native_store
    if p.name == "memory" and p.parent.parent.name == "projects":
        return p.parent.parent.parent
    return None


def _plugin_data_for_native(
    native_store: Path,
    environ: Optional[dict] = None,
    plugin_data: Optional[Path] = None,
) -> Path:
    if plugin_data is not None:
        return plugin_data
    from store_context import plugin_data_dir
    cfg = _config_root_from_native(native_store)
    return plugin_data_dir(cfg, environ) if cfg is not None else plugin_data_dir(environ=environ)


def _ops_slot(native_store: Path) -> str:
    return native_store.parent.name if native_store.name == "memory" else native_store.name


def _project_id_for_native(native_store: Path, plugin_data: Optional[Path] = None) -> str:
    """Registry project_id for this native store, else empty."""
    try:
        from control_plane import connect_if_exists
        pdata = plugin_data
        if pdata is None:
            from store_context import plugin_data_dir
            pdata = plugin_data_dir()
        conn = connect_if_exists(pdata / "control.sqlite")
        if conn is None:
            return ""
        try:
            want = str(native_store)
            try:
                want_r = str(native_store.resolve())
            except OSError:
                want_r = want
            rows = conn.execute(
                "SELECT project_id, native_memory_dir FROM projects"
            ).fetchall()
            for r in rows:
                got = str(r["native_memory_dir"] or "")
                if got in (want, want_r):
                    return str(r["project_id"] or "")
                try:
                    if str(Path(got).resolve()) == want_r:
                        return str(r["project_id"] or "")
                except OSError:
                    continue
            return ""
        finally:
            conn.close()
    except Exception:
        return ""


def _ops_key(native_store: Path, plugin_data: Optional[Path] = None,
             project_id: Optional[str] = None) -> str:
    pid = (project_id or "").strip() or _project_id_for_native(native_store, plugin_data)
    if pid:
        from identifiers import IdentifierRefused, validate_project_id
        try:
            return validate_project_id(pid)
        except IdentifierRefused:
            pass
    return _ops_slot(native_store)


def cycle_log_write_path(
    native_store: Path,
    environ: Optional[dict] = None,
    plugin_data: Optional[Path] = None,
    project_id: Optional[str] = None,
) -> Path:
    """Control-plane cycle log keyed by stable project_id when known."""
    pdata = _plugin_data_for_native(native_store, environ, plugin_data)
    return operational_dir(pdata, _ops_key(native_store, pdata, project_id)) / CYCLE_LOG_NAME


def cycle_log_read_paths(native_store: Path, environ: Optional[dict] = None,
                         plugin_data: Optional[Path] = None,
                         project_id: Optional[str] = None) -> list:
    """Legacy native, slot-keyed plugin-data, then project-id-keyed (last wins)."""
    pdata = _plugin_data_for_native(native_store, environ, plugin_data)
    slot_path = operational_dir(pdata, _ops_slot(native_store)) / CYCLE_LOG_NAME
    pid_path = cycle_log_write_path(native_store, environ, pdata, project_id)
    paths = [native_store / CYCLE_LOG_NAME, slot_path]
    if pid_path != slot_path:
        paths.append(pid_path)
    return paths


def mutation_log_write_path(
    native_store: Path,
    environ: Optional[dict] = None,
    plugin_data: Optional[Path] = None,
    project_id: Optional[str] = None,
) -> Path:
    """Control-plane mutation log keyed by stable project_id when known."""
    pdata = _plugin_data_for_native(native_store, environ, plugin_data)
    return operational_dir(pdata, _ops_key(native_store, pdata, project_id)) / MUTATION_LOG_NAME


def mutation_log_read_paths(native_store: Path, environ: Optional[dict] = None,
                            plugin_data: Optional[Path] = None,
                            project_id: Optional[str] = None) -> list:
    """Legacy native, slot-keyed plugin-data, then project-id-keyed (last wins)."""
    pdata = _plugin_data_for_native(native_store, environ, plugin_data)
    slot_path = operational_dir(pdata, _ops_slot(native_store)) / MUTATION_LOG_NAME
    pid_path = mutation_log_write_path(native_store, environ, pdata, project_id)
    paths = [native_store / MUTATION_LOG_NAME, slot_path]
    if pid_path != slot_path:
        paths.append(pid_path)
    return paths


def fleet_ledger_write_path(
    environ: Optional[dict] = None,
    plugin_data: Optional[Path] = None,
) -> Path:
    """Control-plane fleet usage ledger. The canonical Markdown plane must not receive this file."""
    if plugin_data is not None:
        return plugin_data / FLEET_LEDGER_NAME
    from store_context import plugin_data_dir
    return plugin_data_dir(environ=environ) / FLEET_LEDGER_NAME


def native_plane_forbidden_names() -> frozenset:
    return frozenset({
        ".fleet-usage.jsonl", ".consolidation-log.jsonl", ".mutation-log.jsonl",
        "control.sqlite", "locks",
    })


def native_plane_is_clean(native_dir: Path) -> bool:
    if not native_dir.is_dir():
        return True
    forbidden = native_plane_forbidden_names()
    for p in native_dir.iterdir():
        if p.name in forbidden:
            return False
        if p.name.endswith(".lock"):
            return False
        if p.name == "journal" and p.is_dir():
            return False
    return True


def reverse_tail_jsonl(path: Path, limit: int) -> list:
    """Streaming reverse-tail of a JSONL file. Does not split the whole file first."""
    if not path.is_file() or limit <= 0:
        return []
    rows: list = []
    try:
        size = path.stat().st_size
    except OSError:
        return []
    if size == 0:
        return []
    buf = b""
    chunk = 8192
    with path.open("rb") as fh:
        pos = size
        while pos > 0 and len(rows) < limit:
            read = min(chunk, pos)
            pos -= read
            fh.seek(pos)
            buf = fh.read(read) + buf
            while b"\n" in buf and len(rows) < limit:
                rest, _, buf = buf.rpartition(b"\n")
                line = rest if pos == 0 and not buf else rest
                # When rpartition, `rest` is before last nl of current buf... handle below
                parts = (buf + b"\n" + rest if False else None)
                if line.strip():
                    try:
                        rows.append(json.loads(line.decode("utf-8", "replace")))
                    except ValueError:
                        continue
                buf = rest
        if pos == 0 and buf.strip() and len(rows) < limit:
            try:
                rows.append(json.loads(buf.decode("utf-8", "replace")))
            except ValueError:
                pass
    rows.reverse()
    return rows[-limit:]


def _reverse_tail_lines(path: Path, limit: int) -> list:
    """Return last `limit` non-empty lines without loading the whole file as splitlines()."""
    if not path.is_file() or limit <= 0:
        return []
    try:
        size = path.stat().st_size
    except OSError:
        return []
    data: list = []
    buf = b""
    with path.open("rb") as fh:
        pos = size
        while pos > 0 and len(data) < limit:
            take = min(4096, pos)
            pos -= take
            fh.seek(pos)
            buf = fh.read(take) + buf
            while True:
                nl = buf.rfind(b"\n")
                if nl < 0:
                    break
                line = buf[nl + 1:]
                buf = buf[:nl]
                if line.strip():
                    data.append(line.decode("utf-8", "replace"))
                    if len(data) >= limit:
                        break
        if pos == 0 and buf.strip() and len(data) < limit:
            data.append(buf.decode("utf-8", "replace"))
    data.reverse()
    return data


def reverse_tail_jsonl_lines(path: Path, limit: int) -> list:
    out = []
    for line in _reverse_tail_lines(path, limit):
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return out


def relocate_native_operational(native_dir: Path, plugin_data: Path, project_id: str) -> dict:
    """Move leftover plugin logs out of the native plane onto the control-plane write paths.

    Cycle/mutation logs key off the stable project_id when known.
    """
    dest_map = {
        ".consolidation-log.jsonl": cycle_log_write_path(
            native_dir, plugin_data=plugin_data, project_id=project_id),
        ".mutation-log.jsonl": mutation_log_write_path(
            native_dir, plugin_data=plugin_data, project_id=project_id),
        ".fleet-usage.jsonl": fleet_ledger_write_path(plugin_data=plugin_data),
    }
    moved: list = []
    dests: list = []
    for name, dest in dest_map.items():
        src = native_dir / name
        if not src.is_file():
            continue
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            data = src.read_bytes()
            with dest.open("ab") as fh:
                fh.write(data)
            src.unlink()
            moved.append(name)
            dests.append(str(dest))
        except OSError:
            continue
    return {"ok": True, "moved": moved, "dest": dests[0] if dests else str(plugin_data)}


def _with_ops_lock(plugin_data: Path):
    from control_plane import FileLock
    lock = FileLock(Path(plugin_data) / "locks" / "ops.lock")
    lock.acquire()
    return lock


def compact_jsonl(path: Path, *, keep: int, older_than_days: Optional[int] = None) -> dict:
    """Rewrite `path` keeping the last `keep` records (and dropping events older than N days)."""
    if not path.is_file():
        return {"ok": True, "kept": 0, "dropped": 0}
    # Bound: we only need the tail. If the file is huge, reverse-tail `keep` is enough.
    kept_rows = reverse_tail_jsonl_lines(path, keep)
    cutoff = None
    if older_than_days is not None:
        cutoff = _now_epoch() - older_than_days * 86400
    kept = []
    for row in kept_rows:
        if cutoff is not None:
            day = str(row.get("day") or row.get("ts") or "")
            # ISO date prefix
            try:
                if len(day) >= 10:
                    t = time.mktime(time.strptime(day[:10], "%Y-%m-%d"))
                    if t < cutoff:
                        continue
            except (ValueError, OverflowError):
                pass
        kept.append(row)
    tmp = path.with_suffix(path.suffix + f".tmp-{uuid.uuid4().hex[:12]}")
    with tmp.open("w", encoding="utf-8") as fh:
        for row in kept:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
    os.replace(tmp, path)
    return {"ok": True, "kept": len(kept), "dropped": max(0, len(kept_rows) - len(kept))}


def inventory(plugin_data: Path, canonical_root: Path, native_dir: Path) -> dict:
    def _size(p: Path) -> int:
        try:
            return p.stat().st_size if p.is_file() else sum(
                q.stat().st_size for q in p.rglob("*") if q.is_file())
        except OSError:
            return 0

    return {
        "control_plane": str(plugin_data),
        "control_plane_bytes": _size(plugin_data) if plugin_data.exists() else 0,
        "canonical": str(canonical_root),
        "canonical_bytes": _size(canonical_root) if canonical_root.exists() else 0,
        "native": str(native_dir),
        "native_bytes": _size(native_dir) if native_dir.exists() else 0,
        "native_clean": native_plane_is_clean(native_dir),
        "canonical_inside_plugin_data": _is_relative_to(canonical_root, plugin_data),
        "retention": {
            "events_days": EVENT_RETENTION_DAYS,
            "cycle_cap": CYCLE_CAP,
        },
    }


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except (ValueError, OSError):
        return False


def _purge_dir(d: Path) -> int:
    n = 0
    if not d.exists():
        return 0
    for p in d.rglob("*"):
        if p.is_file():
            p.unlink()
            n += 1
    try:
        d.rmdir()
    except OSError:
        pass
    return n


def purge_project(plugin_data: Path, project_id: str,
                  native_store: Optional[Path] = None) -> dict:
    """Delete operational logs for a project.

    Persist/audit write `ops/<slot>/` (Claude projects-slot). A leftover SHA
    `project_id` directory is also removed if present.
    """
    n = _purge_dir(operational_dir(plugin_data, project_id))
    if native_store is not None:
        slot = _ops_slot(native_store)
        if slot and slot != project_id:
            n += _purge_dir(operational_dir(plugin_data, slot))
    return {"ok": True, "purged_files": n, "project_id": project_id}


def purge_domain(plugin_data: Path, domain_id: str, conn,
                 facts_dir: Optional[Path] = None) -> dict:
    """Remove that domain's canonicals + registry rows. Does not touch other domains
    or native Auto Memory."""
    from identifiers import validate_domain_id
    domain_id = validate_domain_id(domain_id)
    rows = conn.execute(
        "SELECT project_id, native_memory_dir FROM projects WHERE domain_id=?",
        (domain_id,),
    ).fetchall()
    n = 0
    for r in rows:
        native = Path(r["native_memory_dir"]) if r["native_memory_dir"] else None
        n += purge_project(plugin_data, r["project_id"], native)["purged_files"]
    conn.execute(
        "DELETE FROM holders WHERE fact_id IN (SELECT fact_id FROM facts WHERE domain_id=?)",
        (domain_id,))
    conn.execute("DELETE FROM facts WHERE domain_id=?", (domain_id,))
    conn.execute("DELETE FROM tombstones WHERE domain_id=?", (domain_id,))
    conn.commit()
    if facts_dir is not None and facts_dir.is_dir():
        n += _purge_dir(facts_dir)
        # Phase-5 closeout: non-transact purge of the facts dir — unlink the
        # manifest explicitly.
        try:
            from facts_manifest import manifest_path
            manifest_path(plugin_data, domain_id).unlink(missing_ok=True)
        except Exception:
            pass
        parent = facts_dir.parent
        if parent.name == domain_id:
            n += _purge_dir(parent)
    return {"ok": True, "purged_files": n, "domain_id": domain_id}


def _sha256_file(path: Path) -> str:
    import hashlib
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _sqlite_snapshot_to(path: Path, dest: Path, *, redact_journal: bool = False) -> None:
    """Checkpointed SQLite backup (includes committed WAL state) written to dest."""
    import sqlite3
    src = sqlite3.connect(str(path))
    try:
        try:
            src.execute("PRAGMA wal_checkpoint(FULL)")
        except sqlite3.Error:
            pass
        dst = sqlite3.connect(str(dest))
        try:
            src.backup(dst)
            if redact_journal:
                dst.row_factory = sqlite3.Row
                from control_plane import redact_journal_payloads
                redact_journal_payloads(dst)
        finally:
            dst.close()
    finally:
        src.close()


def _sqlite_snapshot_bytes(path: Path, *, redact_journal: bool = False) -> bytes:
    """Checkpointed SQLite backup (includes committed WAL state)."""
    import tempfile
    fd, tmp = tempfile.mkstemp(suffix=".sqlite")
    os.close(fd)
    try:
        _sqlite_snapshot_to(path, Path(tmp), redact_journal=redact_journal)
        return Path(tmp).read_bytes()
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass


def export_ops(plugin_data: Path, dest: Path) -> dict:
    """Write a tar.gz of plugin-data plus a sha256 manifest (ADR 008/Stage 8).

    SQLite members are checkpointed backups (WAL-safe). Members are streamed
    into the archive. Native Auto Memory is never included.
    """
    import hashlib
    import io
    import tarfile
    import tempfile
    dest = Path(dest)
    suffixes = list(dest.suffixes)
    is_tar = dest.suffix == ".tgz" or suffixes[-2:] == [".tar", ".gz"]
    if not is_tar:
        dest = dest.with_name(dest.stem + ".tar.gz") if dest.suffix else dest.with_name(
            dest.name + ".tar.gz")
    dest.parent.mkdir(parents=True, exist_ok=True)
    files: list = []
    try:
        lock = _with_ops_lock(plugin_data)
    except Exception as e:
        return {"ok": False, "error": "ops lock: " + str(e)}
    snap_tmps: list = []
    try:
        staged: list = []  # (rel, path_to_read, nbytes, sha)
        if plugin_data.exists():
            for p in plugin_data.rglob("*"):
                if p.is_symlink() or not p.is_file():
                    continue
                if p.suffix not in (".jsonl", ".json", ".sqlite", ".md"):
                    continue
                rel = str(p.relative_to(plugin_data)).replace("\\", "/")
                if p.suffix == ".sqlite":
                    fd, tmp = tempfile.mkstemp(suffix=".sqlite")
                    os.close(fd)
                    tmp_p = Path(tmp)
                    snap_tmps.append(tmp_p)
                    _sqlite_snapshot_to(
                        p, tmp_p, redact_journal=(p.name == "journal.sqlite"))
                    src = tmp_p
                else:
                    src = p
                sha = _sha256_file(src)
                nbytes = src.stat().st_size
                files.append({"path": rel, "bytes": nbytes, "sha256": sha})
                staged.append((rel, src, nbytes, sha))
        manifest = {
            "exported_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "schema_version": 3,
            "plugin_data": str(plugin_data),
            "files": files,
        }
        man_path = dest.parent / (dest.name + ".manifest.json")
        man_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        try:
            os.chmod(str(man_path), 0o600)
        except OSError:
            pass
        with tarfile.open(dest, "w:gz") as tar:
            for rel, src, nbytes, _sha in staged:
                info = tarfile.TarInfo(name="plugin-data/" + rel)
                info.size = nbytes
                with src.open("rb") as fh:
                    tar.addfile(info, fh)
            man_raw = man_path.read_bytes()
            minfo = tarfile.TarInfo(name="manifest.json")
            minfo.size = len(man_raw)
            tar.addfile(minfo, io.BytesIO(man_raw))
        try:
            os.chmod(str(dest), 0o600)
        except OSError:
            pass
        return {"ok": True, "path": str(dest), "manifest": str(man_path),
                "n_files": len(files)}
    finally:
        for tmp_p in snap_tmps:
            try:
                tmp_p.unlink()
            except OSError:
                pass
        if lock is not None:
            lock.release()


def import_ops(archive: Path, dest_plugin_data: Path) -> dict:
    """Extract an export_ops tar.gz into dest plugin-data. Path-escape refused.

    v0.4.0 review: the export's sha256 manifest was never CHECKED on import —
    a tampered/corrupt archive extracted as ok. When a manifest.json member
    exists, every extracted file is hashed against it; any mismatch (or an
    unlisted member) fails the import.
    """
    import hashlib as _hl
    import tarfile
    archive = Path(archive)
    dest_plugin_data = Path(dest_plugin_data)
    if not archive.is_file():
        return {"ok": False, "error": "archive not found"}
    n = 0
    dest_plugin_data.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(str(dest_plugin_data), 0o700)
    except OSError:
        pass
    want: dict = {}
    with tarfile.open(str(archive), "r:gz") as tar:
        man_m = None
        for m in tar.getmembers():
            if m.isfile() and str(m.name or "").replace("\\", "/") == "manifest.json":
                man_m = m
                break
        if man_m is not None:
            fh = tar.extractfile(man_m)
            try:
                man = json.loads(fh.read().decode("utf-8", "replace")) if fh else {}
            except (ValueError, TypeError):
                man = {}
            if not isinstance(man, dict):
                man = {}
            for f in man.get("files") or []:
                if isinstance(f, dict) and f.get("path") and f.get("sha256"):
                    want[str(f["path"])] = str(f["sha256"])
        for m in tar.getmembers():
            if not m.isfile():
                continue
            name = str(m.name or "").replace("\\", "/")
            if name == "manifest.json":
                continue
            if not name.startswith("plugin-data/"):
                continue
            rel = name[len("plugin-data/"):]
            parts = Path(rel).parts
            if not rel or ".." in parts or Path(rel).is_absolute():
                return {"ok": False, "error": "import path escape: " + name}
            dest = dest_plugin_data / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            fh = tar.extractfile(m)
            if fh is None:
                continue
            data = fh.read()
            if want and rel not in want:
                return {"ok": False, "error": "unlisted member in manifest: " + rel}
            if rel in want and _hl.sha256(data).hexdigest() != want[rel]:
                return {"ok": False, "error": "sha256 mismatch for " + rel}
            dest.write_bytes(data)
            try:
                os.chmod(str(dest), 0o600)
            except OSError:
                pass
            n += 1
    return {"ok": True, "n_files": n, "dest": str(dest_plugin_data),
            "verified_sha256": bool(want)}


def retention_show() -> dict:
    return {
        "events_days": EVENT_RETENTION_DAYS,
        "cycle_records_per_project": CYCLE_CAP,
        "permanent": ["confirmed facts", "explicit user decisions", "tombstones", "migration summaries"],
        "never": ["raw transcript text"],
        "note": "compact keeps the last CYCLE_CAP records and drops events older than EVENT_RETENTION_DAYS; no unimplemented monthly-aggregate window is advertised",
    }
