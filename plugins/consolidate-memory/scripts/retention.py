#!/usr/bin/env python3
"""Bounded operational history in ${CLAUDE_PLUGIN_DATA}. Native plane stays facts-only."""
from __future__ import annotations

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


def cycle_log_write_path(
    native_store: Path,
    environ: Optional[dict] = None,
    plugin_data: Optional[Path] = None,
) -> Path:
    """Control-plane cycle log. The native plane must not receive this file."""
    pdata = _plugin_data_for_native(native_store, environ, plugin_data)
    return operational_dir(pdata, _ops_slot(native_store)) / CYCLE_LOG_NAME


def cycle_log_read_paths(native_store: Path, environ: Optional[dict] = None) -> list:
    """Legacy native first, plugin-data last (plugin-data wins on the same cycle key)."""
    return [native_store / CYCLE_LOG_NAME, cycle_log_write_path(native_store, environ)]


def mutation_log_write_path(
    native_store: Path,
    environ: Optional[dict] = None,
    plugin_data: Optional[Path] = None,
) -> Path:
    """Control-plane mutation log. The native plane must not receive this file."""
    pdata = _plugin_data_for_native(native_store, environ, plugin_data)
    return operational_dir(pdata, _ops_slot(native_store)) / MUTATION_LOG_NAME


def mutation_log_read_paths(native_store: Path, environ: Optional[dict] = None) -> list:
    """Legacy native first, plugin-data last."""
    return [native_store / MUTATION_LOG_NAME, mutation_log_write_path(native_store, environ)]


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

    `project_id` is accepted for call-site compatibility; cycle/mutation logs key off the
    native slot (same as persist / --audit), and the fleet ledger is plugin-data root.
    """
    del project_id
    dest_map = {
        ".consolidation-log.jsonl": cycle_log_write_path(native_dir, plugin_data=plugin_data),
        ".mutation-log.jsonl": mutation_log_write_path(native_dir, plugin_data=plugin_data),
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
    tmp = path.with_suffix(path.suffix + f".tmp{os.getpid()}")
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
        parent = facts_dir.parent
        if parent.name == domain_id:
            n += _purge_dir(parent)
    return {"ok": True, "purged_files": n, "domain_id": domain_id}


def export_ops(plugin_data: Path, dest: Path) -> dict:
    """Write a tar.gz of plugin-data plus a sha256 manifest (ADR 008/Stage 8).

    `dest` is the archive path (``.tar.gz`` appended if missing). The manifest
    lists relative path, size, and sha256 of every included file. Native Auto
    Memory is never included.
    """
    import hashlib
    import tarfile
    dest = Path(dest)
    suffixes = list(dest.suffixes)
    is_tar = dest.suffix == ".tgz" or suffixes[-2:] == [".tar", ".gz"]
    if not is_tar:
        dest = dest.with_name(dest.stem + ".tar.gz") if dest.suffix else dest.with_name(
            dest.name + ".tar.gz")
    dest.parent.mkdir(parents=True, exist_ok=True)
    files: list = []
    if plugin_data.exists():
        for p in plugin_data.rglob("*"):
            if not p.is_file():
                continue
            if p.suffix not in (".jsonl", ".json", ".sqlite", ".md"):
                continue
            rel = str(p.relative_to(plugin_data)).replace("\\", "/")
            raw = p.read_bytes()
            files.append({
                "path": rel,
                "bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
            })
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
        if plugin_data.exists():
            tar.add(str(plugin_data), arcname="plugin-data")
        tar.add(str(man_path), arcname="manifest.json")
    try:
        os.chmod(str(dest), 0o600)
    except OSError:
        pass
    return {"ok": True, "path": str(dest), "manifest": str(man_path),
            "n_files": len(files)}


def retention_show() -> dict:
    return {
        "events_days": EVENT_RETENTION_DAYS,
        "cycle_records_per_project": CYCLE_CAP,
        "permanent": ["confirmed facts", "explicit user decisions", "tombstones", "migration summaries"],
        "never": ["raw transcript text"],
        "note": "compact keeps the last CYCLE_CAP records and drops events older than EVENT_RETENTION_DAYS; no unimplemented monthly-aggregate window is advertised",
    }
