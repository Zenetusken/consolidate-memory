#!/usr/bin/env python3
"""Environment PRE-FLIGHT — deterministic no-happy-path detection for consolidate-memory.

Design-of-record: docs/env-preflight.spec.md (v0.4.16). The problem this exists for: the
plane's modules import ``sqlite3`` top-level (control_plane.py), so a Python built without
the module crashes every command with an ImportError traceback — before any friendly
output. This script reports the environment instead of dying of it.

Hard rules (the spec, amend-1/2):
- Stdlib-only, fully offline, < ~300ms.
- NO top-level import of ``control_plane``, ``sqlite3``, or ``store_context`` — the core
  promise is reporting a missing sqlite3, so all three enter lazily inside probes.
- 3.7-PARSEABLE syntax (no walrus, no positional-only params) — probe #1 must genuinely
  discriminate below the runtime floor (3.8); its FAIL branch is untestable in CI.
- Pure probe functions take injectable params so the smoke suite stubs failures in-process.
- Exit 0 = no fails, 2 = any fail. ``--json`` emits the envelope
  ``{ok, at, checks, notes}`` (per check: id/status/label/fix/detail).
- No CM_DREAM_ARC involvement, no dream cue.

Integration contracts:
- ``run_for_project`` — guarded resolve_store -> run_checks -> run_and_cache (freshness: a
  cached verdict younger than CACHE_TTL_S re-answers without re-probing; force=True
  re-probes — cm doctor forces).
- ``run_and_cache`` — ONE writer: ``control_plane.update_project_state`` mutator writing
  ``st["preflight"] = {"at", "fails": [ids], "warns": [ids]}``; never raises (BLE001).
  The no-sqlite3 environment never reaches it by construction (resolve_store raises first —
  the sentinel path is its channel; the beacon is silent there, documented boundary).
- ``cache_advisory`` — the SessionStart beacon's read-only consumer: fresh + fails -> one
  line; warns/pass/absent/stale/garbage -> ""; never raises.
"""
from __future__ import annotations

import importlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

CACHE_TTL_S = 7 * 86400  # the beacon's advisory freshness (mirrors _STACKS_TTL_S)
FRESH_TTL_S = 3600  # run_for_project re-answers from a cache younger than 1h
SQLITE_FLOOR = (3, 24, 0)  # UPSERT ON CONFLICT DO UPDATE needs SQLite >= 3.24
FREE_FLOOR_BYTES = 1024 * 1024  # the statvfs floor for tempdir/native-dir (>= 1MB)
PROBE_WRITE_BYTES = 64 * 1024  # the real write the tempdir probe performs

# The sibling .py set a healthy install carries (smoke asserts this constant against the
# live scripts/ listing — a renamed script fails the pin by design).
SIBLING_PY = frozenset([
    "calibration_report", "canonical_ingress", "capabilities", "cm_ops", "control_plane",
    "distill_scan", "domain_policy", "extract_signals", "fact_schema", "facts_manifest",
    "identifiers", "identity", "index_admission", "local_ingress", "memory_status",
    "mirror_conflict", "preflight", "render_dashboard", "render_html", "render_log",
    "retention", "session_beacon", "store_context", "sync_global", "_ui",
])

ADVISORY_LINE = (
    "consolidate-memory pre-flight: %d environment check(s) failed "
    "(dreams will fail here) — run cm doctor for the fixes."
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _mk(status: str, cid: str, label: str, fix: str, detail: str = "") -> Dict[str, str]:
    return {"id": cid, "status": status, "label": label, "fix": fix, "detail": detail}


def _ver(v: Any) -> Optional[tuple]:
    try:
        return tuple(int(x) for x in str(v).split(".")[:3])
    except (TypeError, ValueError):
        return None


# ── probes (pure; injectable) ──────────────────────────────────────────────────────────

def probe_python_floor(version_info: Any = None) -> Dict[str, str]:
    vi = version_info if version_info is not None else sys.version_info
    v = _ver(".".join(str(x) for x in vi[:3]))
    if v is None or v < (3, 8, 0):
        return _mk("fail", "python-floor",
                   "Python 3.8+ required", "Install Python 3.8+ — older interpreters are unsupported.",
                   "running %s" % ".".join(str(x) for x in vi[:3]))
    return _mk("pass", "python-floor", "Python 3.8+", "")


def probe_posix(platform: str = "", importer: Callable = importlib.import_module) -> Dict[str, str]:
    plat = platform or sys.platform
    if plat in ("win32", "cygwin"):
        return _mk("fail", "posix",
                   "POSIX-only (ADR 016)",
                   "Run under Linux/macOS/WSL — Windows mutation is fail-closed by design.",
                   "platform %s" % plat)
    try:
        importer("fcntl")
        return _mk("pass", "posix", "POSIX + fcntl locks", "", "platform %s" % plat)
    except ImportError:
        return _mk("fail", "posix",
                   "fcntl unavailable",
                   "Registry locks need POSIX flock — use a Linux/macOS/WSL interpreter.",
                   "platform %s" % plat)


def probe_sqlite_module(importer: Callable = importlib.import_module) -> tuple:
    """(check, module-or-None) — the module rides along for the floor/roundtrip probes."""
    try:
        mod = importer("sqlite3")
        return (_mk("pass", "sqlite-module", "sqlite3 stdlib module present", ""), mod)
    except Exception as e:  # noqa: BLE001 — a broken build raising anything is still a verdict
        return (_mk("fail", "sqlite-module",
                    "Python build lacks a working sqlite3 stdlib module",
                    "Rebuild Python with sqlite3 support (no system sqlite3 binary is needed).",
                    "%s: %s" % (type(e).__name__, e)), None)


def probe_sqlite_floor(mod: Any = None) -> Dict[str, str]:
    if mod is None:
        return _mk("skip", "sqlite-floor", "sqlite3 unavailable", "")
    v = _ver(getattr(mod, "sqlite_version", ""))
    if v is None or v < SQLITE_FLOOR:
        return _mk("fail", "sqlite-floor",
                   "SQLite >= 3.24.0 required",
                   "The SQL dialect needs UPSERT (3.24+); use a Python whose bundled SQLite is newer.",
                   "bundled %s" % getattr(mod, "sqlite_version", "?"))
    return _mk("pass", "sqlite-floor", "SQLite >= 3.24.0", "",
               "bundled %s" % getattr(mod, "sqlite_version", ""))


def probe_sqlite_roundtrip(data_dir: Path, mod: Any, cp: Any, fcntl_mod: Any,
                           skip_reason: str = "") -> Dict[str, str]:
    """The real-schema proof: SCHEMA_SQL + _migrate_schema + a UPSERT insert/select/delete
    inside plugin_data_dir, plus a real flock acquire/release (the lock primitive the plane
    is built on). skip_reason carries the sqlite-module/floor cascade."""
    if skip_reason:
        return _mk("skip", "sqlite-roundtrip", "skipped", "", skip_reason)
    probe = data_dir / (".preflight-probe-" + uuid.uuid4().hex[:12])
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
        lock_p = data_dir / ".preflight-probe.lock"
        with open(str(lock_p), "a") as lf:
            fcntl_mod.flock(lf.fileno(), fcntl_mod.LOCK_EX)
            fcntl_mod.flock(lf.fileno(), fcntl_mod.LOCK_UN)
        try:
            os.unlink(str(lock_p))
        except OSError:
            pass
        con = mod.connect(str(probe))
        try:
            con.executescript(cp.SCHEMA_SQL)
            cp._migrate_schema(con)
            con.execute(
                "INSERT INTO projects (project_id, display_name) VALUES (?, ?) "
                "ON CONFLICT(project_id) DO UPDATE SET display_name=excluded.display_name",
                ("pf-probe", "probe"),
            )
            n = con.execute("SELECT COUNT(*) FROM projects WHERE project_id='pf-probe'").fetchone()[0]
            if n != 1:
                raise AssertionError("roundtrip count %r" % n)
            con.execute("DELETE FROM projects WHERE project_id='pf-probe'")
        finally:
            con.close()
        return _mk("pass", "sqlite-roundtrip",
                   "real schema + UPSERT + flock execute in plugin-data", "")
    except Exception as e:
        return _mk("fail", "sqlite-roundtrip",
                   "the real schema/flock cannot execute in plugin-data",
                   "Check disk space/permissions — registry writes refuse on flock-less mounts too.",
                   "%s: %s" % (type(e).__name__, e))
    finally:
        for suffix in ("", "-wal", "-shm"):
            try:
                os.unlink(str(probe) + suffix)
            except OSError:
                pass


def probe_plugin_self(root: Optional[Path] = None, sibling_set: Any = SIBLING_PY) -> Dict[str, str]:
    root = Path(root) if root is not None else Path(__file__).resolve().parent.parent
    manifest = root / ".claude-plugin" / "plugin.json"
    try:
        with open(str(manifest)) as f:
            json.load(f)
    except (OSError, ValueError):
        return _mk("fail", "plugin-self",
                   "plugin manifest unreadable",
                   "Reinstall: /plugin marketplace add Zenetusken/consolidate-memory.",
                   "missing %s" % manifest)
    missing = sorted(n for n in sibling_set if not (root / "scripts" / (n + ".py")).is_file())
    if missing:
        return _mk("fail", "plugin-self",
                   "plugin scripts truncated",
                   "Reinstall: /plugin marketplace add Zenetusken/consolidate-memory.",
                   "missing %s" % ", ".join(missing))
    return _mk("pass", "plugin-self", "plugin manifest + scripts intact", "")


def probe_native_mem_dir(path: Path, enabled: bool = True, statvfs: Callable = os.statvfs,
                         mkstemp: Callable = tempfile.mkstemp) -> Dict[str, str]:
    if not enabled:
        return _mk("skip", "native-mem-dir",
                   "native Auto-Memory disabled — supported config", "")
    try:
        path.mkdir(parents=True, exist_ok=True)
        st = statvfs(str(path))
        if st.f_bavail * st.f_frsize < FREE_FLOOR_BYTES:
            return _mk("fail", "native-mem-dir",
                       "native memory dir has no free space",
                       "Free >= 1MB in the native memory dir — facts persist there.",
                       "free %d bytes" % (st.f_bavail * st.f_frsize))
        fd, tmp = mkstemp(dir=str(path), prefix=".preflight-")
        try:
            os.write(fd, b"x")
        finally:
            os.close(fd)
            try:
                os.unlink(tmp)
            except OSError:
                pass
        return _mk("pass", "native-mem-dir",
                   "native memory dir creatable + writable",
                   "Native Auto-Memory itself is NOT required.", str(path))
    except OSError as e:
        return _mk("fail", "native-mem-dir",
                   "native memory dir unusable",
                   "The config home must be creatable/writable — native Auto-Memory itself is NOT required.",
                   str(e))


def probe_git_present(which: Callable = shutil.which) -> Dict[str, str]:
    if which("git"):
        return _mk("pass", "git-present", "git on PATH", "")
    return _mk("warn", "git-present",
               "git not found",
               "Dreams degrade to empty scope without git — install it (shipped policy).")


def probe_git_repo(project_dir: Path, run: Callable = subprocess.run, present: bool = True) -> Dict[str, str]:
    if not present:
        return _mk("skip", "git-repo", "skipped", "", "git absent")
    out = _git_ask(run, project_dir, "rev-parse", "--is-inside-work-tree")
    if out is None:
        return _mk("warn", "git-repo",
                   "not a git repository",
                   "Path-keyed identity here; enroll from a git root for verification.")
    if out.strip() == "true":
        return _mk("pass", "git-repo", "inside a git work tree", "")
    return _mk("warn", "git-repo",
               "not a git repository",
               "Path-keyed identity here; enroll from a git root for verification.")


def probe_git_shallow(project_dir: Path, run: Callable = subprocess.run,
                      present: bool = True, in_repo: bool = False) -> Dict[str, str]:
    if not present:
        return _mk("skip", "git-shallow", "skipped", "", "git absent")
    if not in_repo:
        return _mk("skip", "git-shallow", "skipped", "", "not a repository")
    out = _git_ask(run, project_dir, "rev-parse", "--is-shallow-repository")
    if out is not None and out.strip() == "true":
        return _mk("warn", "git-shallow",
                   "shallow clone",
                   "Shallow history limits verification — unshallow for the full pass.")
    return _mk("pass", "git-shallow", "full history", "")


def _git_ask(run: Callable, project_dir: Path, *argv: str) -> Optional[str]:
    try:
        p = run(["git", *argv], cwd=str(project_dir), capture_output=True, timeout=15)
        out = (p.stdout or b"").decode("utf-8", errors="replace")
    except Exception:  # noqa: BLE001 — a stubbed/injected run must never raise out of the probe
        return None
    return out


def probe_python3(which: Callable = shutil.which) -> Dict[str, str]:
    if which("python3"):
        return _mk("pass", "python3-path", "python3 on PATH", "")
    return _mk("warn", "python3-path",
               "python3 not on PATH",
               "Slash commands invoke python3 — add it to PATH. (Fires only when preflight "
               "runs under another interpreter; a python3-less shell kills the hooks first.)")


def probe_tempdir(gettempdir: Callable = tempfile.gettempdir,
                  statvfs: Callable = os.statvfs) -> Dict[str, str]:
    try:
        td = gettempdir()
        st = statvfs(td)
        if st.f_bavail * st.f_frsize < FREE_FLOOR_BYTES:
            return _mk("fail", "tempdir",
                       "TMPDIR has no free space",
                       "Set TMPDIR writable with >= 1MB free — Phase 0 writes its cycle seed there.",
                       "free %d bytes" % (st.f_bavail * st.f_frsize))
        fd, tmp = tempfile.mkstemp(dir=td, prefix=".preflight-")
        try:
            os.write(fd, b"x" * PROBE_WRITE_BYTES)
        finally:
            os.close(fd)
            try:
                os.unlink(tmp)
            except OSError:
                pass
        return _mk("pass", "tempdir", "TMPDIR writable with free space", "")
    except OSError as e:
        return _mk("fail", "tempdir",
                   "TMPDIR unusable",
                   "Set TMPDIR to a writable directory — Phase 0 writes its cycle seed there.",
                   str(e))


def probe_transcripts(transcript_dir: Optional[Path], resolution_failed: bool = False) -> Dict[str, str]:
    if resolution_failed:
        return _mk("pass", "transcripts", "transcript dir unknown",
                   "StoreContext resolution failed — no session dir resolved.", "")
    if transcript_dir is None or not Path(transcript_dir).is_dir():
        return _mk("pass", "transcripts", "no transcript dir yet",
                   "Fresh project — transcripts accrue with sessions.", "")
    n = len(list(Path(transcript_dir).glob("*.jsonl")))
    return _mk("pass", "transcripts", "%d transcript(s) in this session" % n, "")


def probe_store_resolution(error_text: str = "") -> Dict[str, str]:
    if error_text:
        return _mk("fail", "store-resolution",
                   "StoreContext resolution failed",
                   "Fix the config root and re-run — dependent probes are skipped.",
                   error_text)
    return _mk("pass", "store-resolution", "StoreContext resolved", "")


def stale_lock_note(lock_dir: Optional[Path], importer: Callable = importlib.import_module) -> Optional[str]:
    """Only a HELD lock is a finding (a non-blocking flock attempt that blocks). Lock FILES
    are the design's normal resting state (FileLock never unlinks) — counting them as stale
    made doctor output run-to-run nondeterministic and nagged healthy stores (review F1)."""
    if lock_dir is None or not Path(lock_dir).is_dir():
        return None
    try:
        fcntl_mod = importer("fcntl")
    except ImportError:
        return None
    held = 0
    for p in sorted(Path(lock_dir).glob("*.lock")):
        try:
            fd = os.open(str(p), os.O_RDWR | os.O_CREAT, 0o600)
        except OSError:
            continue
        try:
            fcntl_mod.flock(fd, fcntl_mod.LOCK_EX | fcntl_mod.LOCK_NB)
            fcntl_mod.flock(fd, fcntl_mod.LOCK_UN)
        except (OSError, BlockingIOError):
            held += 1
        finally:
            os.close(fd)
    if not held:
        return None
    return "%d HELD lock file(s) in %s — another process holds the plane; wait or investigate" % (
        held, lock_dir)


# ── orchestration ────────────────────────────────────────────────────────────────────────

def run_checks(env: Dict[str, Any]) -> Dict[str, Any]:
    """The full matrix in the fixed order (pins rely on it). env carries the injectables."""
    checks: List[Dict[str, str]] = []
    notes: List[str] = []

    importer = env.get("importer", importlib.import_module)
    which = env.get("which", shutil.which)
    run = env.get("run", subprocess.run)
    version_info = env.get("version_info", sys.version_info)
    platform = env.get("platform", "")
    gettempdir = env.get("gettempdir", tempfile.gettempdir)
    statvfs = env.get("statvfs", os.statvfs)

    checks.append(probe_python_floor(version_info))
    checks.append(probe_posix(platform, importer))
    sm_check, sqlite_mod = probe_sqlite_module(importer)
    checks.append(sm_check)
    floor_ok = False
    if sqlite_mod is not None:
        floor = probe_sqlite_floor(sqlite_mod)
        checks.append(floor)
        floor_ok = floor["status"] == "pass"
    else:
        checks.append(_mk("skip", "sqlite-floor", "skipped", "", "sqlite3 unavailable"))
    skip5 = "" if (sqlite_mod is not None and floor_ok) else "sqlite-module or sqlite-floor failed"
    if sqlite_mod is not None and floor_ok:
        cp = None
        try:
            cp = importer("control_plane")
        except ImportError:
            skip5 = "control_plane unimportable"
        try:
            fcntl_mod = importer("fcntl")
        except ImportError:
            fcntl_mod = None
            skip5 = "fcntl unavailable"
        data_dir = Path(env["plugin_data_dir"]) if env.get("plugin_data_dir") else None
        if cp is None or fcntl_mod is None or data_dir is None:
            checks.append(_mk("skip", "sqlite-roundtrip", "skipped", "", skip5))
        else:
            checks.append(probe_sqlite_roundtrip(data_dir, sqlite_mod, cp, fcntl_mod, skip5))
    else:
        checks.append(_mk("skip", "sqlite-roundtrip", "skipped", "", skip5))

    checks.append(probe_plugin_self(env.get("plugin_root")))
    resolution_failed = bool(env.get("store_resolution_error"))
    if resolution_failed:
        checks.append(_mk("skip", "native-mem-dir", "skipped", "", "resolution failed"))
    else:
        nmd = Path(env["native_memory_dir"]) if env.get("native_memory_dir") else None
        if nmd is None:
            checks.append(_mk("skip", "native-mem-dir", "skipped", "", "no native dir resolved"))
        else:
            checks.append(probe_native_mem_dir(nmd, bool(env.get("auto_memory_enabled", True)), statvfs))

    g_present = probe_git_present(which)
    checks.append(g_present)
    present = g_present["status"] == "pass"
    g_repo = probe_git_repo(Path(env["project_dir"]) if env.get("project_dir") else Path("."),
                            run, present)
    checks.append(g_repo)
    checks.append(probe_git_shallow(
        Path(env["project_dir"]) if env.get("project_dir") else Path("."),
        run, present, g_repo["status"] == "pass"))
    checks.append(probe_python3(which))
    checks.append(probe_tempdir(gettempdir, statvfs))
    checks.append(probe_transcripts(Path(env["transcript_dir"]) if env.get("transcript_dir") else None,
                                    resolution_failed))
    checks.append(probe_store_resolution(env.get("store_resolution_error", "")))

    note = stale_lock_note(Path(env["lock_dir"]) if env.get("lock_dir") else None)
    if note:
        notes.append(note)

    fails = [c["id"] for c in checks if c["status"] == "fail"]
    warns = [c["id"] for c in checks if c["status"] == "warn"]
    return {"ok": not fails, "at": _now_iso(), "checks": checks, "notes": notes,
            "fails": fails, "warns": warns}


def verdict_for_cache(result: Dict[str, Any]) -> Dict[str, Any]:
    return {"at": result.get("at", _now_iso()),
            "fails": list(result.get("fails") or []),
            "warns": list(result.get("warns") or [])}


def _read_state(state_path: Path) -> Dict[str, Any]:
    try:
        with open(str(state_path)) as f:
            st = json.load(f)
    except (OSError, ValueError):
        return {}
    return st if isinstance(st, dict) else {}


def _fresh_cached(state_path: Path, ttl_s: int = FRESH_TTL_S, now: float = time.time()) -> Optional[Dict[str, Any]]:
    """A cache-advisory-shaped verdict younger than ttl_s -> the fails/warns block, else None."""
    st = _read_state(state_path)
    pf = st.get("preflight")
    if not isinstance(pf, dict):
        return None
    fails = pf.get("fails")
    if not isinstance(fails, list):
        return None
    warns = pf.get("warns")
    if not isinstance(warns, list):
        warns = []
    try:
        at = datetime.fromisoformat(str(pf.get("at", "")))
    except ValueError:
        return None
    if at.tzinfo is None:
        at = at.replace(tzinfo=timezone.utc)
    if now - at.timestamp() > ttl_s:
        return None
    return {"at": pf.get("at", ""), "fails": [str(x) for x in fails],
            "warns": [str(x) for x in warns]}


def run_and_cache(ctx: Any, verdict: Dict[str, Any]) -> bool:
    """ONE writer: the update_project_state mutator (the sync_global stacks precedent).
    Never raises (BLE001); the no-sqlite3 env never reaches here by construction."""
    try:
        from control_plane import update_project_state

        def _mut(state: Dict[str, Any], snap: object) -> Dict[str, Any]:
            state = dict(state)
            state["preflight"] = dict(verdict)
            return state

        update_project_state(ctx, _mut)
        return True
    except Exception:
        return False


def _paths_from_ctx(ctx: Any) -> Dict[str, Any]:
    """Env paths from the resolved ctx — ctx's own mapping first (it carries session_dir
    and project_root, which doctor_dict omits), doctor_dict as the canonical fallback."""
    try:
        from store_context import doctor_dict
    except ImportError:
        d: Dict[str, Any] = {}
    else:
        try:
            d = doctor_dict(ctx)
        except Exception:
            d = {}
    def pick(key: str) -> Any:
        # StoreContext is an attribute object (no .get) — getattr first, doctor_dict
        # (the canonical key/value rows) as the fallback.
        v = getattr(ctx, key, None)
        if v is None:
            v = d.get(key)
        return v

    pdd = pick("plugin_data_dir")
    nmd = pick("native_memory_dir")
    return {
        "plugin_data_dir": pdd,
        "native_memory_dir": nmd,
        "transcript_dir": pick("session_dir"),
        "project_dir": pick("project_root"),
        "auto_memory_enabled": (pick("auto_memory_enabled")
                                if pick("auto_memory_enabled") is not None else True),
        "lock_dir": (Path(pdd) / "locks") if pdd else None,
        "state_path": (Path(nmd) / ".consolidation-state.json") if nmd else None,
    }


def safe_run_checks(env: Dict[str, Any]) -> Dict[str, Any]:
    """run_checks that can NEVER raise — an uncaged probe failure (review F3: a corrupt
    sqlite3 extension raising at import) still becomes a verdict, not a traceback."""
    try:
        return run_checks(env)
    except Exception as e:  # noqa: BLE001 — the tool exists to report broken environments
        return {"ok": False, "at": _now_iso(),
                "checks": [_mk("fail", "preflight-internal", "the pre-flight itself failed",
                               "Report this: the environment checker crashed where it must not.", str(e))],
                "notes": [], "fails": ["preflight-internal"], "warns": []}


def run_for_project(project_dir: Path, force: bool = False) -> Dict[str, Any]:
    """Guarded resolve_store -> run_checks -> run_and_cache. The BLE001 boundary: this
    function never raises — a resolution failure produces the sentinel verdict instead."""
    env: Dict[str, Any] = {"project_dir": str(project_dir)}
    ctx = None
    try:
        from store_context import resolve_store

        ctx = resolve_store(project_dir)
        paths = _paths_from_ctx(ctx)
        env.update(paths)
    except Exception as e:
        env["store_resolution_error"] = "%s: %s" % (type(e).__name__, e)

    if ctx is not None and not force:
        sp = env.get("state_path")
        cached = _fresh_cached(Path(sp)) if sp else None
        if cached is not None:
            return {"ok": not cached["fails"], "at": cached["at"], "checks": [],
                    "notes": [], "cached": True,
                    "fails": cached["fails"], "warns": cached["warns"]}

    result = safe_run_checks(env)
    if ctx is not None:
        sp = env.get("state_path")
        if sp is not None:
            run_and_cache(ctx, verdict_for_cache(result))
    return result


def cache_advisory(state_path: Path, ttl_s: int = CACHE_TTL_S, now: float = time.time()) -> str:
    """The SessionStart beacon's read-only consumer. Fresh + fails -> one line;
    warns/pass/absent/stale/garbage -> ''. Never raises."""
    try:
        cached = _fresh_cached(state_path, ttl_s, now)
    except Exception:
        return ""
    if cached is None or not cached["fails"]:
        return ""
    return ADVISORY_LINE % len(cached["fails"])


def render_table(result: Dict[str, Any]) -> str:
    try:
        import _ui
    except ImportError:
        ui = None
    else:
        ui = _ui
    glyph = {"pass": ("✓", "green"), "warn": ("⚠", "yellow"),
             "fail": ("✗", "red"), "skip": ("−", "dim")}
    lines: List[str] = []
    if ui is not None:
        lines.append(ui.rule())
        lines.append(ui.lbl("PRE-FLIGHT (v0.4.16)", 40))
        lines.append(ui.rule())
        for c in result.get("checks") or []:
            g, col = glyph.get(c["status"], ("?", "dim"))
            head = "%s %-18s %s" % (ui.c(g, col), c["id"], c["label"])
            lines.append(head)
            if c.get("detail"):
                lines.append(ui.li(c["detail"], indent=2))
            if c["status"] in ("fail", "warn") and c.get("fix"):
                lines.append(ui.li("fix: " + c["fix"], indent=2))
        for n in result.get("notes") or []:
            lines.append(ui.li(n, indent=2))
    else:
        lines.append("PRE-FLIGHT (v0.4.16)")
        for c in result.get("checks") or []:
            lines.append("  [%s] %-18s %s" % (c["status"], c["id"], c["label"]))
            if c.get("detail"):
                lines.append("      " + c["detail"])
            if c["status"] in ("fail", "warn") and c.get("fix"):
                lines.append("      fix: " + c["fix"])
    fails = result.get("fails") or []
    warns = result.get("warns") or []
    tail = "%d fail · %d warn · %d pass" % (len(fails), len(warns),
                                            len([c for c in result.get("checks") or []
                                                 if c["status"] == "pass"]))
    if ui is not None:
        lines.append(ui.li(tail, indent=0))
        lines.append(ui.rule())
    else:
        lines.append(tail)
    return "\n".join(lines) + "\n"


def main(argv: List[str]) -> int:
    args = list(argv)
    as_json = "--json" in args
    args = [a for a in args if a != "--json"]
    project_dir = Path(args[0]) if args else Path(".")
    result = run_for_project(project_dir, force=True)
    result = result if isinstance(result, dict) else safe_run_checks({"project_dir": str(project_dir)})
    if as_json:
        payload = {k: result[k] for k in ("ok", "at", "checks", "notes") if k in result}
        sys.stdout.write(json.dumps(payload, indent=2) + "\n")
    else:
        sys.stdout.write(render_table(result))
    return 2 if (result.get("fails")) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
