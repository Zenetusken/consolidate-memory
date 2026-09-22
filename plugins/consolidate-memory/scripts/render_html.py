#!/usr/bin/env python3
"""v0.1.28: render the cycle record + the longitudinal `.consolidation-log.jsonl` into a self-contained,
ZERO-dependency HTML observability dashboard ("dream telemetry") and open it in the browser.

The HTML sibling of `render_dashboard.py`'s ASCII output — the SAME cycle-record contract, a rich visual
presentation (one contract, two renderers). Stdlib only; the template is a BUNDLED asset found via `__file__`
so it works from the marketplace install cache; the data is embedded inline (XSS / `</script>`-break-out-proof)
so the HTML is fully self-contained + offline; the browser open is headless-safe (falls back to printing the
path, never crashes a dream).
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import tempfile
import typing
import webbrowser
from datetime import datetime, timezone
from pathlib import Path

import _ui  # sibling: dream_cue (v0.1.54 — the WAKE cue fires HERE, the arc's true terminal boundary)
import memory_status as ms  # sibling: the SINGLE-SOURCE procedure_integrity predicate (v0.1.44) — derive, don't duplicate

if typing.TYPE_CHECKING:
    # Type-only, and the narrowness is deliberate: `from __future__ import annotations` above makes
    # every annotation a string, so this import never executes and `store_context` stays a lazy
    # in-function import at its call sites (the file's existing idiom — the module is imported
    # inside the functions that need it, never at module scope). Writing the resolver's annotations
    # as `Any` instead would be the smaller diff and the wrong one: it would stop mypy checking
    # `resolution_source` and `mem_dir_source`, which are the two fields v0.4.36 adds and therefore
    # the two most likely to be misspelled — and a name not tied to what it claims is the exact
    # defect class this release closes. `object` (whom this replaces) at least kept the arity.
    from store_context import StoreContext

# The gorgeous HTML/CSS/vanilla-JS lives in a sibling BUNDLED template (a real editable asset, shipped under
# plugins/consolidate-memory/scripts/). Found via __file__ so it resolves from the installed plugin cache
# regardless of ${CLAUDE_PLUGIN_ROOT}. A single placeholder is replaced (NOT str.format — CSS/JS braces).
_TEMPLATE = Path(__file__).parent / "dashboard.template.html"
_BUNDLES = {"/*__CM_NETWORK__*/": "dashboard.network.js",
            "/*__CM_SECTIONS__*/": "dashboard.sections.js"}
# v0.4.35 (RC-3): the action vocabulary marker. Its substitution CANNOT ride `_BUNDLES` — that
# dict maps a marker to a FILENAME read just below, and this one's replacement is a JSON literal
# with no file to read, so it is not expressible as a member. It gets its own replace and its own
# exactly-once check beside that loop rather than inside it. The check is not decoration: smoke
# calls `_load_template()` UNGUARDED to compute the `_EMBED_KEYS` teeth pin, so a marker count
# other than one raises ValueError OUT OF THE SUITE (no totals line, exit 1) rather than failing
# a check — and the single-declaration form is what keeps that count at one.
_WRITE_ACTIONS_MARKER = "/*__CM_WRITE_ACTIONS__*/"


def _load_template() -> str:
    """Inline the shipped vanilla-JS modules, retaining a single offline artifact."""
    template = _TEMPLATE.read_text(encoding="utf-8")
    # Substituted from the declaration, so the template's two count sites cannot restate a
    # subset of it. First, against the pristine template — a marker that only a bundle could
    # have introduced is not a marker this check should be satisfied by.
    _marker_n = template.count(_WRITE_ACTIONS_MARKER)
    if _marker_n != 1:
        # ONE string cannot carry two causes (RC-1d, the same defect `local_archive`'s refusal
        # had): an ABSENT marker and a DUPLICATED one are different faults with different
        # repairs — restore it, or remove the extra copy — and the shipped sentence named both
        # while pointing at neither. The count is also the one thing a reader needs and the old
        # message withheld it.
        raise ValueError(
            "action-vocabulary marker %s in the render_html template (exactly one required) — "
            "%s" % ("is ABSENT" if _marker_n == 0 else "appears %d times" % _marker_n,
                    "restore it" if _marker_n == 0 else "remove the extra copy/copies"))
    template = template.replace(_WRITE_ACTIONS_MARKER,
                                json.dumps([a for a, w in ms.ACTION_VOCAB if w]))
    for marker, filename in _BUNDLES.items():
        source = (_TEMPLATE.parent / filename).read_text(encoding="utf-8")
        if "</script" in source.lower():
            raise ValueError("unsafe script-end sequence in " + filename)
        # Same split as the vocabulary marker above, and the same defect: this sentence named
        # BOTH an absent marker and a duplicated one in one string, so the reader could not tell
        # which fault they had, and the count they would need to tell was the one fact withheld.
        _bn = template.count(marker)
        if _bn != 1:
            raise ValueError(
                "bundle marker %s for %s (exactly one required) — %s"
                % ("is ABSENT" if _bn == 0 else "appears %d times" % _bn, filename,
                   "restore it" if _bn == 0 else "remove the extra copy/copies"))
        template = template.replace(marker, source)
    return template
_PLACEHOLDER = "/*__CM_DATA__*/"

# The budget constants are LIVE REFERENCES into `memory_status` — ONE definition, every reader, so a
# retune of the constant can never leave this module holding the retired number. That has been this
# module's stated preference since v0.1.66, when INDEX_CEILING_TOKENS became a reference because a
# literal mirror is "a needless, structurally-avoidable drift risk" a code-review workflow flagged
# (2026-07-04). The other two stayed hardcoded copies (1500 / 4000) only because they predate this
# module's `ms` import — and nothing pinned either pair. Fixed v0.4.30. Bound at IMPORT, like any
# module constant: a runtime rebinding of `ms.X` is NOT seen here, so a retune is pinned at the source
# (edit + re-import), never by monkeypatching this module's `ms`.
INDEX_TOKEN_BUDGET = ms.INDEX_TOKEN_BUDGET          # the always-loaded MEMORY.md index
CLAUDE_MD_TOKEN_BUDGET = ms.CLAUDE_MD_TOKEN_BUDGET  # the root CLAUDE.md
INDEX_CEILING_TOKENS = ms.INDEX_CEILING_TOKENS      # 0.6 × the native 25KB cap — the harm rung


def _safe_embed(data: dict) -> str:
    """JSON safe to embed inside `<script type="application/json">`: escape `<` `>` `&` to their \\uXXXX
    forms. `JSON.parse` restores them; the HTML parser never sees a real `<`, so a memory fact containing
    `</script>` (or any markup) can't break out of the tag — the load-bearing XSS guard."""
    return (json.dumps(data, ensure_ascii=False)
            .replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026"))


def read_history(store: Path | None) -> list:
    """The accrued cycle records from `<store>/.consolidation-log.jsonl` — the longitudinal series. Robust:
    a malformed line is skipped (a corrupt log must not break the dashboard), a missing log → [].
    v0.1.67 (Phase C): DELEGATES to ms.iter_cycle_log — the shared reader usage_history also uses, so the
    log line-parse has ONE definition (the single-source rule; a smoke pin guards the delegation).
    tail=None: render surfaces read ALL cycles, unchanged (_ARCHIVE_CAP bounds the embed downstream)."""
    if store is None:
        return []
    return ms.iter_store_cycle_log(Path(store), tail=None)


_ARCHIVE_CAP = 120   # embed at most the latest N cycles (bounded HTML size); a VISIBLE note flags any truncation
_DIFF_EMBED_CAP = 20   # P4 (v0.4.2): embed diff sidecars for only the newest N cycles — the modal
                       # is reachable from the newest dreams; the oldest 100 sidecars were pure weight

# P4 (v0.4.2 archive embed budget): the TOP-LEVEL record keys the bundled template's JS reads
# (audited against every CUR.* / g(CUR, ...) / g(c, ...) / loop-var read in dashboard.template.html).
# Full subtrees are kept — the v0.1.28 round-trip pin asserts budget.recall_facts.after survives
# embedding even though the JS never reads it. Everything else (registrar payloads, per-phase
# working data) is rendered nowhere and was most of a 120-cycle archive's weight. A smoke pin
# enforces this whitelist — the template must not grow an unlisted read.
_EMBED_KEYS = (
    "audit", "budget", "cross_project", "demotion", "distill", "dream",
    "entries", "health", "identity", "maintenance", "marker", "network",
    "outcome", "preflight", "project", "remediation", "rigor", "scope", "session",
    "usage", "verification", "workflow_proposals",
)


def _embed_cycle(c: object) -> object:
    """Trim a cycle record to _EMBED_KEYS (full subtrees). Non-dict entries pass through."""
    if not isinstance(c, dict):
        return c
    return {k: v for k, v in c.items() if k in _EMBED_KEYS}


def _marker(r: dict) -> tuple:
    """A dream's identity for dedup/selection. Timestamp is UNIQUE per dream; commit COLLIDES when dreams share a
    HEAD — so the (commit, timestamp) pair dedups and timestamp is the real key. Tolerates a non-dict `marker`
    (a corrupted log entry) so dedup/--select can't crash — mirrors the JS side's defensive accessor."""
    m = r.get("marker") if isinstance(r, dict) else None
    if not isinstance(m, dict):
        m = {}
    return (m.get("commit"), m.get("timestamp"))


def _same_dream(a: dict, b: dict) -> bool:
    """C2: dream identity for dedup. Same commit AND: both timestamps non-empty → equal stamps;
    EITHER timestamp empty → session equality when both carry a session (the same HEAD can hold
    two dreams, one unstamped — the archive already shows same-commit collisions, they must NOT
    collapse); either side lacks a session → raw _marker equality (an empty ts never equals a
    stamped one → keep both rows, conservative)."""
    ca, ta = _marker(a)
    cb, tb = _marker(b)
    if ca != cb:
        return False
    if str(ta or "").strip() and str(tb or "").strip():
        return ta == tb
    sa = str(a.get("session") or "").strip() if isinstance(a, dict) else ""
    sb = str(b.get("session") or "").strip() if isinstance(b, dict) else ""
    if sa and sb:
        return sa == sb
    return ta == tb


def _fill_timestamp(rec: dict, by_commit: dict, prev_ts: str) -> dict:
    """C1: an empty marker.timestamp must not embed (blank archive date, inverted 'newest' sort,
    dangling footer, `__nots` sidecar keys). Fill from (1) a same-commit history stamp whose SESSION
    matches, else (2) `prev_ts` — the chain-walk carrying the nearest earlier non-empty stamp so
    adjacent empty rows both fill. Returns a COPY when it fills — the embedded series never mutates
    caller dicts. No fill source → unchanged (the JS renders '—' and sorts the row last)."""
    m = rec.get("marker") if isinstance(rec, dict) else None
    if not isinstance(m, dict):
        return rec
    if str(m.get("timestamp") or "").strip():
        return rec
    ses = str(rec.get("session") or "").strip()
    fill = by_commit.get((str(m.get("commit") or "").strip(), ses), "") \
        or str(m.get("before_timestamp") or "").strip() or prev_ts
    if not fill:
        return rec
    return {**rec, "marker": {**m, "timestamp": fill}}


def assemble_cycles(record: dict, history: list) -> tuple:
    """The archive series: all logged cycles (oldest-first) + the current `record` dedup-appended if it is newer
    than the last logged entry (so the latest dream shows even before --persist). Returns (capped_cycles, total).
    v0.4.1-fix (C1/C2): DEDUP FIRST on RAW markers (a fill-then-dedup cascade could make a filled legacy row
    marker-identical to its neighbor and collapse two dreams), then fill empty timestamps for the survivors;
    `_same_dream` treats commit-match with either-empty-ts + matching session as the same dream (the stale
    unstamped --cycle file vs the repaired log line must never double-embed), preferring the stamped copy."""
    cycles = [c for c in history if isinstance(c, dict)] if isinstance(history, list) else []
    rec = record if isinstance(record, dict) else {}
    if rec and (not cycles or not _same_dream(cycles[-1], rec)):
        cycles.append(rec)
    elif rec and cycles:
        _lts = str(_marker(cycles[-1])[1] or "").strip()
        _rts = str(_marker(rec)[1] or "").strip()
        if _lts and _lts == _rts:
            cycles[-1] = rec    # same dream, same stamp — the current file is the fresher expression
                                # (a post-persist enrichment like the injected network block surfaces)
        elif not _lts and _rts:
            cycles[-1] = rec    # same dream: the stamped copy wins
    by_commit: dict = {}
    for c in cycles:
        m = c.get("marker") if isinstance(c, dict) else None
        if isinstance(m, dict):
            ts = str(m.get("timestamp") or "").strip()
            cm = str(m.get("commit") or "").strip()
            if ts and cm and (cm, str(c.get("session") or "").strip()) not in by_commit:
                by_commit[(cm, str(c.get("session") or "").strip())] = ts
    out: list = []
    prev_ts = ""
    for c in cycles:
        filled = _fill_timestamp(c, by_commit, prev_ts)
        out.append(filled)
        _m_out = filled.get("marker")
        if isinstance(_m_out, dict):    # a string marker (corrupted entry) never advances the walk
            prev_ts = str(_m_out.get("timestamp") or "").strip() or prev_ts
    total = len(out)
    return (out[-_ARCHIVE_CAP:] if total > _ARCHIVE_CAP else out), total


def build_html(record: dict, history: list, generated_at: str, diffs: "dict | None" = None,
               identity: "dict | None" = None,
               cycles: "list | None" = None, total: "int | None" = None) -> str:
    """Embed the ARCHIVE (all logged cycles, capped) + the repo identity into the bundled template; the JS reads
    `cycles`/`project`/`budgets`/`diffs`/`identity` and renders either the archive index or a single dream selected by URL
    `#sel=`. `diffs` (v0.1.32) maps a cycle's diff_key → its persisted memory diffs (the diff-modal); read by
    main() so build_html stays PURE w.r.t. inputs (a smoke test exercises it + asserts the embedded round-trip).
    `identity` (v0.3.0) is the LIVE StoreContext snapshot at render — the archive masthead; per-cycle
    `identity` on a record (seeded Phase 0) is this-pass truth when present.
    `cycles`/`total` (P4, v0.4.2): main() assembles the series ONCE (it needs the same list for
    read_diffs + #sel) — pass it in to skip the re-assembly; omitted, this assembles as before."""
    template = _load_template()
    if cycles is None:
        cycles, total = assemble_cycles(record, history)
    else:
        total = len(cycles) if total is None else total
    rec = record if isinstance(record, dict) else {}
    project = (rec.get("project") or (cycles[-1].get("project") if cycles else "")) or "dream"
    # v0.1.44: attach the procedure-integrity verdict per cycle (single-source ms.procedure_integrity),
    # ONLY when it fires (lean payload) — the JS surfaces an escaped ⚠ panel + archive badge from
    # `_integrity`. A shallow copy carries it into the embedded series without mutating the source dicts.
    def _embed_integrity(c: object) -> object:
        if not isinstance(c, dict):
            return c
        # L4 (v0.4.2): the single-source outcome label rides the embed (the template's
        # outcomeOf prefers it; the JS ladder stays as the legacy fallback)
        c = {**c, "_outcome": ms.outcome_of(c)}
        ok, reason, severity = ms.procedure_integrity(c)
        return c if ok else {**c, "_integrity": {"severity": severity, "reason": reason}}
    # P4: trim to the template's read-whitelist FIRST, then stamp integrity (which is itself rendered).
    cycles = [_embed_integrity(_embed_cycle(c)) for c in cycles]
    data = {
        "cycles": cycles,
        "project": project,
        "generated_at": generated_at,
        "budgets": {"index": INDEX_TOKEN_BUDGET, "claude_md": CLAUDE_MD_TOKEN_BUDGET,
                    "index_ceiling": INDEX_CEILING_TOKENS,   # v0.1.66 (Phase B): the hard ceiling, for the meter
                    "hook_warn": ms.HOOK_TOKEN_WARN,        # v0.3.0: fat-hook threshold, live (not a hardcoded copy)
                    "cliff_near": int(ms.CLIFF_NEAR_FRACTION * 100)},
        "total": total,
        "cap": _ARCHIVE_CAP,
        "diffs": diffs if isinstance(diffs, dict) else {},
        "identity": identity if isinstance(identity, dict) else {},
    }
    return template.replace(_PLACEHOLDER, _safe_embed(data))


def read_diffs(store: "Path | None", cycles: list) -> dict:
    """v0.1.32: load each embedded cycle's persisted diff sidecar (`dashboards/diffs/<diff_key>.json`), keyed by the
    SAME `diff_key` the capture used → the diff-modal payload. Best-effort: a missing/corrupt sidecar is skipped
    (legacy / pre-feature cycles simply have none, so their facts just aren't clickable).
    P4 (v0.4.2): capped to the newest _DIFF_EMBED_CAP cycles — the oldest sidecars were embedded
    but only reachable from dreams at the archive's tail."""
    if store is None:
        return {}
    from memory_status import diff_key
    ddir = Path(store).parent / "dashboards" / "diffs"
    if not ddir.exists():
        return {}
    if len(cycles) > _DIFF_EMBED_CAP:
        cycles = cycles[-_DIFF_EMBED_CAP:]
    out: dict = {}
    for c in cycles:
        marker = c.get("marker") if isinstance(c, dict) else {}
        session = str(c.get("session", "")) if isinstance(c, dict) else ""
        # probe the session-suffixed key (post-fix sidecars) AND the legacy unsuffixed base (pre-fix
        # sidecars must keep resolving — the alias maps both keys to the same payload). v0.4.1-fix:
        # filled cycles flip legacy UNSTAMPED keys (`__nots`) to the filled stamp — probe the raw
        # `commit__nots` forms too and register the payload under EVERY probed key, or an old
        # unstamped sidecar's modal silently orphans.
        keys = [diff_key(marker, session), diff_key(marker)]
        if isinstance(marker, dict) and str(marker.get("commit") or "").strip():
            _raw = {"commit": marker.get("commit"), "timestamp": ""}
            keys += [diff_key(_raw, session), diff_key(_raw)]
        for key in keys:
            if key in out or not (ddir / (key + ".json")).exists():
                continue
            try:
                d = json.loads((ddir / (key + ".json")).read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError, ValueError):
                continue
            if isinstance(d, dict):
                for alias in keys:    # register under EVERY probed key — the JS lookup computes the
                    out[alias] = d    # filled key while legacy lookups use the raw __nots form
                break
    return out


_OPEN_MARKER_NAME = ".last-open"
_OPEN_WINDOW_S = 180.0    # one open per (archive, anchor) per 3 minutes — kills the repeated-tab pop, keeps deliberate re-opens


def _open_recent(out: Path, frag: str, now_ts: float, marker_dir: Path,
                 window_s: float = _OPEN_WINDOW_S) -> bool:
    """RC-89/n4: was this (archive, anchor) opened within the window? PURE READ — a FAILED
    webbrowser.open must never have written the marker, or the next attempt is suppressed.

    v0.4.13 hotfix (the repeated-window incident): ALSO suppress on a GLOBAL
    per-archive key (any anchor). The per-anchor key alone could not stop a
    re-render loop whose anchor CHANGES each iteration (--latest while the log
    grows, or a Phase-5 retry after each persist-gate failure) — every
    iteration passed the exact-key check and opened a NEW browser window,
    ~5s apart, indefinitely. The global key bounds the class: at most one
    window per archive per window_s, whatever the anchor. The cost is
    deliberate --select re-opens within 3 minutes of a prior open — acceptable
    beside unbounded window spawning; the kill-switch below is the escape."""
    marker = marker_dir / _OPEN_MARKER_NAME
    key = f"{out.resolve()}::{frag}"
    gkey = f"{out.resolve()}::*"
    try:
        prev = json.loads(marker.read_text(encoding="utf-8"))
        if isinstance(prev, dict) and now_ts - float(prev.get("at", 0)) < window_s:
            if prev.get("key") == key or prev.get("gkey") == gkey:
                return True
    except (OSError, json.JSONDecodeError, ValueError):
        pass
    return False


def _mark_open(out: Path, frag: str, now_ts: float, marker_dir: Path) -> None:
    """RC-89/n4: record a SUCCESSFUL open (called only after webbrowser.open returned truthy).
    Best-effort — any failure = the next render just tries again."""
    try:
        marker_dir.mkdir(parents=True, exist_ok=True)
        (marker_dir / _OPEN_MARKER_NAME).write_text(
            json.dumps({"key": f"{out.resolve()}::{frag}",
                        "gkey": f"{out.resolve()}::*", "at": now_ts}), encoding="utf-8")
    except OSError:
        pass


def _default_out(record: dict, store: "Path | None") -> Path:
    """The stable per-repo output: `<store>/../dashboards/index.html` (so the dream AND `cm report` write the SAME
    revisitable file), else a per-project temp file. Never the memory store itself (that's facts only)."""
    if store is not None:
        d = Path(store).parent / "dashboards"
        d.mkdir(parents=True, exist_ok=True)
        return d / "index.html"
    proj = str(record.get("project", "dream")) if isinstance(record, dict) else "dream"
    safe = "".join(c if c.isalnum() or c in "-_" else "-" for c in proj) or "dream"
    return Path(tempfile.gettempdir()) / f"cm-dashboard-{safe}.html"


def _store_for(store: str | None, project: str | None) -> Path | None:
    """Resolve the auto-memory store: explicit --store, else derive it from --project via the canonical slug
    (the one place that rule lives — imported from memory_status so cm report and the dream agree)."""
    if store:
        return Path(store)
    if project:
        from memory_status import project_memory_dir   # DRY: StoreContext, not a hard-coded slug path
        return project_memory_dir(Path(project))
    return None


# ---- the identity resolver (v0.4.36) -----------------------------------------------------------
# An archive stamps an IDENTITY. Its subject is the store named by --store/--project; the directory
# the process happens to be standing in is not evidence about it. RC-5 was the archive asking the
# room. Each refusal below carries a distinct, stable anchor phrase, so a pin can assert WHICH arm
# fired without matching prose — a fault and a verdict must not share a message (v0.4.35's theme,
# one module over).
_ARM_NO_PROJECT = "belongs to no registered project"
_ARM_CLAIMED = "is claimed by"
_ARM_REGISTRY = "cannot read the control-plane registry"
_ARM_MISMATCH = "is not the store for"
_ARM_NO_PATH = "does not exist"
# A FIFTH arm, and it is the same rule that produced Arm C: two faults must not share one message.
# Arm A is a verdict about the REGISTRY ("no row names this store, and the room does not derive
# it"); when a configured store path cannot be resolved, no source could be tested at all, so Arm A
# is not merely unhelpful there — it is unearned, and its remedy (`--project`) faults identically.
_ARM_ENV = "resolves through an unusable store path"
_REMEDY_PROJECT = "pass --project <its dir>"
_REMEDY_PATH = "check the path"
_REMEDY_ENV = "check autoMemoryDirectory in your settings"
# v0.4.41 R4: the LAST pair of distinct conditions in this module still sharing one sentence. A
# VERDICT (a resolved store whose log holds no dream) and a FAULT (no store was ever named, so no
# log was located and none was read) arrived at the same string — and the string asserted the
# VERDICT's cause in both cases. Same rule as the five arms above, same reason: one anchor per arm,
# so a pin asserts WHICH arm fired without matching prose.
_ARM_NO_CYCLES = "has no cycle record at"
_ARM_NO_STORE = "names no store to read"
_REMEDY_STORE = "pass --store <auto-memory dir> or --project <dir>"
_REMEDY_DREAM = "run a dream first"


def _canon(p: Path) -> "Path | None":
    """Canonicalize `p`, or `None` when the path is unusable. The RULE lives in `store_context`.

    Kept as a named call site rather than inlined so the six places below read as one decision,
    and delegating rather than restating because this is exactly the defect class the release
    exists to close: a rule with a second copy is a rule that drifts. Measured across the
    interpreters this repo supports (3.8-3.13, the CI matrix's own range): a symlink loop raises
    `RuntimeError` on 3.8-3.12 and **does not raise at all** on 3.13, where it returns the loop
    path itself; a NUL raises `ValueError` on all of them; a working directory deleted under the
    process raises `FileNotFoundError`. RC-5's first cut named two of those three classes and
    applied them INSIDE the candidate loop only — so `--project`, `--store`, the cwd, and the
    comparison's own two operands were left bare, and removing the base tree's
    `except Exception: pass` did not turn them into the named refusal it was meant to become.
    It turned them into an uncaught traceback, at exactly the sites the fix did not reach:
    measured, all three classes, base rc=0 against worktree rc=1.
    """
    from store_context import safe_resolve   # lazy: main() owns store_context's ABSENCE as a
    return safe_resolve(p)                   # plugin-install fault, so a module-level import here
                                             # would raise before that guard could name it


def _shown(p: Path) -> str:
    """A path as it can be PRINTED. A NUL is legal inside a `Path` and illegal in a message.

    The refusal exists to be read, and a NUL in the argument is a byte the terminal silently drops —
    so the reader sees `/tmp/x y` and goes looking for a space that is not there.
    """
    return str(p).replace("\x00", "\\0")


def _log_paths_for(store: Path) -> str:
    """The path(s) `read_history` consults for this store, for naming in a refusal (R4).

    The cycle log is a LADDER, not one path (`retention.cycle_log_read_paths`: legacy native, then
    slot-keyed, then project-id-keyed — *last wins*), so a message naming a single path would name a
    file that may not be the one read — and the whole point of the arm is to let a reader check the
    place the tool actually looked.

    Cold path only, and the import is lazy for the same reason `_canon`'s is: `retention` is a
    shipping-class sibling with no truncated-install guard of its own, and a refusal that turned into
    an ImportError traceback would be the very defect it exists to report.
    """
    try:
        from retention import cycle_log_read_paths
        paths = [Path(p) for p in cycle_log_read_paths(Path(store))]
    except Exception:
        paths = [Path(store) / ".consolidation-log.jsonl"]
    return ", ".join(_shown(p) for p in paths)


def _project_derived(c: StoreContext) -> bool:
    """Is the candidate's store a FUNCTION of the candidate, or a CONSTANT?

    `resolve_store` is not injective: a global redirect maps every directory to one store, so a
    round-trip through it would "verify" any candidate and so evidence nothing. This conjunct is
    what turns the round-trip into a test rather than a formality.

    ⚠ Closed over NAMES only, and the asymmetry is the point. `resolution_source` is WHITELISTED,
    so a route that does not exist yet is refused rather than admitted; a denylist here defaults to
    ADMISSION and would already have missed `CLAUDE_CODE_PROJECT_DIR_NAME`, which never touches
    `autoMemoryDirectory` and so never consults the scope whitelist below either.
    """
    from store_context import PROJECT_DERIVED_SOURCES, PROJECT_LOCAL_SCOPES
    if c.resolution_source in PROJECT_DERIVED_SOURCES:      # default-git-root, default-path
        return True
    if c.resolution_source == "autoMemoryDirectory":
        return c.mem_dir_source in PROJECT_LOCAL_SCOPES
    return False


def _registry_row_for_store(store: Path) -> "tuple[dict | None, str]":
    """Source 1's lookup: the registry row that STORED this exact store path.

    A stored key rather than a re-derivation, so the row it returns is admitted WITHOUT
    `_project_derived`. The row records the store its project had; gating it on re-deriving that
    store from the row's root would refuse exactly the stale rows the registry is most useful for.

    Returns `(row, refusal)`. A miss is `(None, "")` — NOT a refusal: Arm A is a conjunction
    ("matches 0 rows AND every source-2/3 candidate fails"), so a store with no row must still get
    its own marker tried. Only Arm B (two rows claiming one store) and Arm C (a registry that
    cannot be read) refuse here.
    """
    from control_plane import classify_registry, connect_if_exists, db_path, rows_for_store
    db = db_path()
    state, err = classify_registry(db)
    if state == "absent":
        # Vacuously no rows: with no file, "no registered project names this store" is true of
        # every store, and the codebase's own doctrine says so — assert_mutation_allowed() returns
        # early on ("absent", "healthy"). Arm A is a CONJUNCTION, so this is not a refusal: it is
        # the miss that lets sources 2/3 have their turn, and only their failure makes it Arm A.
        # Returning here is also what keeps Arm C honest: connect_if_exists() returns None for an
        # absent file too, so without this branch `absent` would refuse with the FAULT's message.
        return None, ""
    if state != "healthy":
        # Arm C. The same string `cm doctor` prints — and now literally the same FORMATTER, not a
        # re-authoring of its format. This is reached exactly when no context could be resolved, so
        # there is no ctx to pass to `_registry_state_line`; `registry_state_text` is the half of it
        # that needs nothing but the classification. A second copy of the format was the defect v0.4.32
        # shipped a release about, and the two spellings describe ONE condition — so a reword in
        # either would have left `cm doctor` and this refusal describing one fault in two sentences.
        from store_context import registry_state_text as _rst
        return None, (f"{_ARM_REGISTRY} ({_rst(state, err)}) — {_REMEDY_PROJECT}")
    conn = connect_if_exists(db)
    if conn is None:
        # Table-check healthy, yet the file will not open — permission-denied arrives here when
        # classify_registry's read of the header succeeded by another route. A fault, not a miss.
        return None, f"{_ARM_REGISTRY} ({state}) — {_REMEDY_PROJECT}"
    try:
        rows = rows_for_store(conn, store)
    except sqlite3.Error as e:
        # classify_registry is TABLE-level and never COLUMN-level: a registry carrying all five
        # tables but a `projects` table missing a column classifies "healthy" while the scan
        # raises. Deliberately NOT swallowed — unlike iter_registered_projects' OperationalError
        # -> [], which would report a registry we could not read as Arm A and send the reader to
        # re-enroll a project that is already enrolled.
        return None, f"{_ARM_REGISTRY} ({state}: {e}) — {_REMEDY_PROJECT}"
    finally:
        conn.close()
    if len(rows) > 1:
        # `native_memory_dir` carries no UNIQUE constraint, so two rows can name one store.
        # Picking either would be a coin flip presented as a recovery.
        return None, (f"--store {store} {_ARM_CLAIMED} {len(rows)} registry rows "
                      f"— {_REMEDY_PROJECT}")
    return (rows[0] if rows else None), ""


def _refuse(msg: str) -> "StoreContext | None":
    """Name a refusal on stderr and return None — the resolver's ONLY failure channel.

    The resolver used to return `(ctx, refusal)` under the rule *"refusal == '' wins"*. The harm was
    not that a caller could print an empty message — it was guarded — but that TWO REPRESENTATIONS
    of one state (`''` for no-fault beside `None` for no-context) had to be kept in agreement by
    convention, and the convention was the only thing holding them together: mypy cannot narrow
    `ctx` from a `str` being empty, and neither can a reader. One sentinel, and it is `None`.

    ⚠ `_registry_row_for_store` still returns `(row, refusal)`, with `(None, "")` for a miss, and
    that is NOT this shape. It has three outcomes — miss, hit, fault — where the miss and the fault
    are genuinely different states rather than one state spelled twice, and every path that
    produces a fault produces a non-empty message, so the empty string never reaches here. The rule
    is about one state wearing two representations; there, two representations describe two states.
    """
    print(f"render_html: {msg}", file=sys.stderr)
    return None


def _resolve_identity(store: "Path | None", project: str | None) -> "StoreContext | None":
    """Derive the archive's identity from its SUBJECT — the context, or `None` after a named refusal.

    Three input shapes, one rule. `--project` names the subject outright; `--store` alone must have
    its subject RECOVERED; with neither, cwd IS the subject and there is nothing to verify it
    against — so that arm consults no recovery source, though it still opens the registry.
    """
    from store_context import resolve_store as _rs
    from store_context import store_context_from_registry as _sctx_from_row
    if project:
        proj_p = _canon(Path(project))
        if proj_p is None:
            # The named subject is itself unusable. Measured on the base tree this arm rendered at
            # rc=0 (a synthesized identity); with the blanket catch gone it raised straight out of
            # the resolver, once per class — `--project` on a symlink loop, and again on a NUL.
            return _refuse(f"--project {project} {_ARM_NO_PATH} — {_REMEDY_PATH}")
        ctx = _rs(proj_p)
        if store is not None:
            want, got = _canon(Path(store)), _canon(ctx.native_memory_dir)
            if got is None:
                # The PROJECT's own store is unusable, so the pair cannot be compared at all. Left
                # to fall into the mismatch arm below, this said `is not the store for` — true, in
                # the way a lucky guess is — and told the reader to re-run WITHOUT `--store`, which
                # is the very invocation that faults here. A pairing verdict for an environment
                # fault, with a remedy that reproduces it.
                return _refuse(f"--project {project} {_ARM_ENV} "
                               f"({_shown(ctx.native_memory_dir)}) — {_REMEDY_ENV}")
            if want is None or want != got:
                # RC-5b: two inputs that must agree, compared nothing. A silent preference for
                # either one is a wrong masthead with the right one in hand.
                if want is None or not Path(store).exists():
                    # A path fault must not wear a pairing fault's message: `is not the store for`
                    # would send the reader to check a pairing when the mistake is the path. Shares
                    # its wording with the `--store`-alone arm below — the same fault, one message.
                    return _refuse(f"--store {store} {_ARM_NO_PATH} — {_REMEDY_PATH}")
                return _refuse(f"--store {store} {_ARM_MISMATCH} {project} "
                               "— re-run without --store (it derives that from --project), "
                               "or pass a matching pair")
        return ctx
    if store is not None:
        store_p = Path(store)
        row, refusal = _registry_row_for_store(store_p)
        if refusal:
            return _refuse(refusal)
        if row is not None:
            # Source 1 recovers an IDENTITY DIRECTLY, unlike sources 2/3, which recover a candidate
            # that must then verify — so it is admitted without the gate. It passes the ROW to the
            # purpose-built producer rather than resolve_store(<the row's root>): the latter mints
            # a different project id (the defect that producer's docstring records) and re-derives
            # the very store the row already names. The cwd template supplies only the environment
            # and the two fields no row carries (`registry_state`, `plugin_data_dir`), which is why
            # the rendered identity is cwd-invariant. The template still has to be
            # BUILT from some directory, and `Path.cwd()` is unguarded at this site for the same
            # reason it is unguarded at the foot of this function — it is the call that raises, so
            # it cannot be an argument to a guard around `resolve()`.
            try:
                _tpl_dir = Path.cwd()
            except OSError:
                return _refuse(f"the working directory {_ARM_NO_PATH} — {_REMEDY_PATH}")
            _tpl = _canon(_tpl_dir)
            if _tpl is None:
                return _refuse(f"the working directory {_ARM_NO_PATH} — {_REMEDY_PATH}")
            return _sctx_from_row(row, template=_rs(_tpl))
        # Sources 2 and 3, each admitted ONLY because it verifies: the candidate's store must BE
        # this store AND be a function of the candidate rather than a global redirect's constant.
        # Source 2 is the store's OWN script-written marker — a move keeps its `project_path`
        # deriving here, a redirect voids it. Source 3 is the room, admissible only when it
        # verifies; the defect was never that the process has a cwd, but that the cwd was believed.
        cands: list = []
        try:
            st = json.loads((store_p / ms.STATE_FILE).read_text(encoding="utf-8"))
            pp = str(st.get("project_path") or "") if isinstance(st, dict) else ""
            if pp:
                cands.append(Path(pp))
        except (OSError, json.JSONDecodeError, ValueError):
            pass                    # no marker, or an unreadable/garbled one: try source 3 alone
        try:
            cands.append(Path.cwd())
        except OSError:
            # `Path.cwd()` itself raises `FileNotFoundError` when the directory the process stands
            # in has been deleted underneath it — the same OSError family the guard below admits.
            # Source 3 is then simply ABSENT as a source rather than fatal: a candidate that cannot
            # be resolved cannot verify, which is the rule this whole loop already runs on.
            pass
        target = _canon(store_p)
        if target is None:
            # The store cannot be canonicalized — a symlink loop, or a NUL — so no candidate can be
            # compared against it and no source can verify. This is NOT the existence test below
            # and does not sit where it sits: that one must come LAST, because a store that is
            # merely ABSENT is legitimately recoverable (source 1 via the stored row, source 3 via a
            # cwd that derives it). An UNUSABLE path is recoverable by neither, so it refuses here.
            return _refuse(f"--store {store} {_ARM_NO_PATH} — {_REMEDY_PATH}")
        bad_path = ""
        for cand in cands:
            try:
                c = _rs(cand)
            except (OSError, ValueError, RuntimeError):
                # A candidate that cannot be RESOLVED cannot VERIFY, so it fails here like any
                # other and the next source gets its turn — the same degrade the marker parse
                # above already promises for a garbled marker.
                #
                # ⚠ The marker's `project_path` is the reachable vector, and it splits "garbled"
                # in two: `json.loads` accepts an escaped NUL, so the file PARSES while
                # `Path.resolve()` raises `ValueError: embedded null byte`. That raise lands HERE,
                # outside the parse's own `except`, so before this guard a garbled marker did not
                # degrade to source 3 — it took the render down with an uncaught traceback.
                # Measured: a store whose own project renders rc=0 with NO marker exits 1 with a
                # NUL in one, from every cwd.
                #
                # Narrow on purpose: `except Exception` here would rebuild the
                # `except Exception: pass` that RC-1 exists to close — a fault and an absence
                # sharing one representation. These classes ARE path-unusable; anything else
                # should stay loud.
                continue
            cand_store = _canon(c.native_memory_dir)
            if cand_store is None:
                # ⚠ NOT a non-match — an UNUSABLE path. `resolve_store` declines to canonicalize a
                # NUL rather than raising (that is `_norm_path`'s policy, and the reason no
                # exception reaches the arm above), so the fault arrives here as a VALUE, and
                # `None != target` would quietly file it as "this candidate isn't the one".
                # Reporting that at the fall-through as Arm A sends the reader to pass `--project`
                # for a settings fault — and the `--project` run fails the same way, so the printed
                # remedy is a command that faults. `fault ≡ absence` is the RC-1 mechanism this
                # release exists to close; this is where it would have come back.
                bad_path = bad_path or _shown(c.native_memory_dir)
                continue
            if cand_store == target and _project_derived(c):
                return c
        # A MISS and a FAULT both land here, and they get different messages. Note that
        # `belongs to no registered project` is TRUE of both — with an absent path, nothing names
        # or derives it either, so the assertion is vacuously satisfied. Its defect is not falsity
        # but uselessness, in two parts: it is silent on the one fact the reader can act on (the
        # path is not there), and its remedy `--project <its dir>` points at a directory that does
        # not exist. Measured, it also made the SAME typo'd --store read `does not exist` when
        # --project was passed and a registration fault when it was not — so which message the
        # reader got depended on a flag with nothing to do with the mistake.
        #
        # ⚠ The existence test is LAST, after every source has had its turn, and the position is
        # the whole reason it is safe: source 1 recovers a store that was DELETED since enrolment
        # (the row is a stored key, and it still names the project), and source 3 admits an absent
        # store that the cwd DERIVES (a project that has not dreamed yet — the store is not created
        # until it does). Testing existence first would refuse both, breaking two legitimate
        # invocations to fix a message. Measured on this revision: both render rc=0.
        if not store_p.exists():
            return _refuse(f"--store {store} {_ARM_NO_PATH} — {_REMEDY_PATH}, "
                           f"or {_REMEDY_PROJECT}")
        if bad_path:
            # Every source that ran produced a store that cannot be resolved, so "no registered
            # project names this store" was never established — the sources could not be TESTED.
            # Fifth arm, ordered after the path test (which is about `--store` alone and stays
            # last-but-one) and before Arm A, whose verdict this would otherwise counterfeit.
            return _refuse(f"--store {store} {_ARM_ENV} ({bad_path}) — {_REMEDY_ENV}")
        return _refuse(f"--store {store} {_ARM_NO_PROJECT} — {_REMEDY_PROJECT}")
    # With neither flag the cwd IS the subject, so there is nothing to verify it against — but it
    # still has to BE. `Path.cwd()` raises `FileNotFoundError` for a directory deleted under the
    # process, and the base tree's blanket catch turned that into a rendered archive stamped with a
    # synthesized identity; without the catch it becomes a traceback. Neither is a refusal.
    # ⚠ `Path.cwd()` is called OUTSIDE `_canon` on purpose-of-necessity: it is the CALL that
    # raises, so it cannot be the argument to a guard that catches around `resolve()`.
    try:
        cwd_raw = Path.cwd()
    except OSError:
        return _refuse(f"the working directory {_ARM_NO_PATH} — {_REMEDY_PATH}")
    cwd_ctx = _canon(cwd_raw)
    if cwd_ctx is None:
        return _refuse(f"the working directory {_ARM_NO_PATH} — {_REMEDY_PATH}")
    return _rs(cwd_ctx)


def main(argv: list) -> int:
    ap = argparse.ArgumentParser(description="render the per-repo dream ARCHIVE (index + dashboards) as one self-contained HTML")
    ap.add_argument("cycle", nargs="?", help="cycle-record JSON path (memory_status.py --seed + filled); omit to render from the log")
    ap.add_argument("--store", help="the auto-memory dir (.consolidation-log.jsonl source — the archive series)")
    ap.add_argument("--project", help="project dir → derive its auto-memory store via the slug (alternative to --store)")
    ap.add_argument("--latest", action="store_true", help="open the most recent dream's dashboard (the post-dream payoff)")
    ap.add_argument("--select", help="open the dream whose marker commit starts with this hash (latest on collision)")
    ap.add_argument("--out", help="output HTML path (default: <store>/../dashboards/index.html, else a temp file)")
    ap.add_argument("--no-open", action="store_true", help="write the file but don't open a browser")
    args = ap.parse_args(argv)

    if not _TEMPLATE.exists():       # out-of-the-box guard: the bundled template must ship with the plugin
        print(f"render_html: bundled template missing at {_TEMPLATE} — is the plugin install complete?", file=sys.stderr)
        return 1
    # the JS bundles are the same shipping-class dependency — a truncated install must
    # degrade with the same one-line message, never a traceback (per-PR review M1).
    try:
        _load_template()
    except FileNotFoundError as e:
        print(f"render_html: bundled JS module missing ({e.filename}) — is the plugin install complete?",
              file=sys.stderr)
        return 1
    except ValueError as e:
        # A ValueError here is NOT a truncated install. It is `_load_template`'s own integrity
        # refusal — an unsafe script-end sequence in a bundle, or a marker count that is not one
        # — and each of those already names its fault AND its remedy. Reporting them under
        # "is the plugin install complete?" sent the reader to reinstall a plugin that was
        # installed correctly, which is two faults sharing one message: the same defect this
        # release exists to close, one layer up from the marker check that produced it.
        print(f"render_html: template integrity fault — {e}", file=sys.stderr)
        return 1

    # `store_context` is the same shipping-class dependency as the template and the JS bundles
    # above, in the same directory, and it gets the same one-line degrade. It did not, until now:
    # this import used to sit inside the blanket `except Exception: pass` that RC-5a removed, so a
    # truncated install rendered an empty masthead at exit 0; with that catch gone it raised an
    # uncaught ModuleNotFoundError instead — a traceback, which is exactly what the rule three
    # lines above forbids. Only ImportError is caught, for the reason `_load_template`'s ValueError
    # arm states: a fault INSIDE store_context is not a truncated install, and must not go to the
    # reader wearing that message.
    #
    # ⚠ The ORDER is the guard, not a style choice. `_store_for` used to run ABOVE this try, and its
    # `--project` branch imports `memory_status`, which imports `store_context` — so the arm the
    # guard exists for was reached before the guard could see it, and `--project` alone still
    # raised a ten-line traceback on a truncated install while `--store` degraded cleanly. That is
    # the shipped `cm report` path: all three of its branches pass `--project` and never `--store`.
    # Measured on BOTH trees (base rc=1 traceback, worktree rc=1 traceback) — which is what makes
    # it an unmet rule rather than a regression, and what made it invisible to a pin that drove
    # `--store` only.
    try:
        from store_context import (identity_snapshot as _id_html,
                                   warn_unenrolled_share as _w_html)
        store = _store_for(args.store, args.project)
    except ImportError as e:
        print(f"render_html: {e} — is the plugin install complete?", file=sys.stderr)
        return 1
    # The resolution is deliberately NOT wrapped. A fault and an absence must not share one
    # representation: under the old `except Exception: pass` both were `{}`, so a broken plugin
    # install rendered an empty masthead under a clean exit 0. Only the advisory warn below stays
    # wrapped, because its failure must not void an otherwise-correct render.
    # `None` means the refusal has ALREADY been named on stderr — there is nothing to print here,
    # and nothing that could print an empty message.
    _ctx_html = _resolve_identity(store, args.project)
    if _ctx_html is None:
        return 1
    live_identity: dict = _id_html(_ctx_html)
    try:
        # RC-5c: the warn must be handed the SUBJECT's context. Its `_warned_unenrolled` flag is a
        # ONE-SHOT gate, so a cwd-derived context writes it into the wrong project's state file and
        # silently suppresses that project's future warnings — a display defect that persists as
        # durable state.
        _w_html(_ctx_html)
    except Exception:
        pass
    history = read_history(store)
    record: dict = {}
    if args.cycle:
        try:
            record = json.loads(Path(args.cycle).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, ValueError) as e:
            print(f"render_html: cannot read cycle record {args.cycle!r}: {e}", file=sys.stderr)
            return 1

    cycles, _total = assemble_cycles(record, history)
    if not cycles:
        # v0.4.41 R4: ONE sentence, TWO conditions — and the sentence asserted the OTHER one's cause.
        # MEASURED 2026-09-21, the two arms byte-identical before this change:
        #   `--project <dir>` with a verified store whose log is absent → a true VERDICT about a real
        #   absence, remedy correct. `no operand at all` → `store` is None and `read_history(None)`
        #   returns `[]` at its FIRST line, so no path was located and no file was opened — yet the
        #   sentence asserted "an empty .consolidation-log" anyway. Its remedy ("run a dream first")
        #   is the wrong repair for an invocation that never named a subject, and the reader has no
        #   way to tell the two apart: neither arm names the store, and the fault arm names nothing
        #   at all *because there is nothing to name* — which is itself the report.
        # ⚠ `--store <project dir>` does NOT reach here. The v0.4.36 identity resolver refuses it one
        # screen up and names the operand (`belongs to no registered project`). Recorded because that
        # route is the one R4's plan named, and it is not this arm — measured, not reasoned.
        #
        # ⚠ Reachability, so the second arm is not read as a case that cannot happen: `assemble_cycles`
        # keeps every dict row, so `cycles` empty means NO cycle-bearing row was read — which is the
        # absent-log case and nothing else. There is deliberately no third arm for "rows read but
        # none assembled": it is unreachable, and an unreachable arm is a promise the code cannot
        # keep (the reason R4's second planned arm is absent rather than written).
        if store is None:
            print(f"render_html: this invocation {_ARM_NO_STORE} — neither --store nor --project "
                  f"was given, so no cycle log was located and none was read (this is NOT a report "
                  f"that the log is empty) — {_REMEDY_STORE}", file=sys.stderr)
        else:
            print(f"render_html: the store {_shown(store)} {_ARM_NO_CYCLES} "
                  f"{_log_paths_for(store)} — {_REMEDY_DREAM}", file=sys.stderr)
        return 1

    # which view to OPEN: a specific dream (#sel=i) or the archive index (no fragment). The JS reads #sel= on load.
    frag = ""
    if args.select:
        matches = [i for i, c in enumerate(cycles) if str(_marker(c)[0] or "").startswith(args.select)]   # _marker guards a non-dict marker
        if not matches:
            print(f"render_html: no embedded dream matches hash {args.select!r} (may be older than the latest {_ARCHIVE_CAP})", file=sys.stderr)
            return 1
        frag = f"#sel={matches[-1]}"          # cycles are oldest-first → the last match is the most recent timestamp
    elif args.latest:
        frag = f"#sel={len(cycles) - 1}"

    generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    # P4: the series is assembled ONCE here and passed through (build_html and read_diffs
    # both consume the same list — no re-assembly, no re-dedup).
    html = build_html(record, history, generated_at, read_diffs(store, cycles),
                      identity=live_identity, cycles=cycles, total=_total)
    out = Path(args.out) if args.out else _default_out(record, store)
    out.write_text(html, encoding="utf-8")

    opened = False
    # v0.4.13 hotfix: CM_NO_OPEN=1 is the operator kill-switch — a
    # headless/loop-bound render must NEVER open a browser window.
    if not args.no_open and not os.environ.get("CM_NO_OPEN"):
        try:                          # headless-safe: a missing/loopback browser must NEVER crash a dream
            _now = datetime.now(timezone.utc).timestamp()
            if _open_recent(out, frag, _now, out.parent):
                opened = True         # v0.1.89: this archive anchor is ALREADY open (back-to-back re-render) — not a failure
            else:
                opened = bool(webbrowser.open(out.resolve().as_uri() + frag))
                if opened:            # n4: mark AFTER a successful open — a failed headless open must
                    _mark_open(out, frag, _now, out.parent)   # never suppress the next attempt for the window
        except Exception:             # noqa: BLE001 - the whole point is don't-crash-on-open
            opened = False
    print(f"dashboard → {out}{frag}" + ("" if opened else "  · open this file in a browser" if not args.no_open else ""))
    # v0.1.54: the WAKE cue — this archive render/open is the SKILL's pinned wake point ("after the
    # terminal clean render + archive open"), the LAST scripted step of a completing dream.
    # v0.4.1 (D1): gated on arc completeness — waking over a short arc would perform the bookend
    # the gate just refused; backfill the beats first, then this cue says WAKE.
    arc_ok, arc_reason = ms.arc_completeness(record)
    if arc_ok:
        _ui.dream_cue("the archive is open — WAKE now: *☀️ 2–5 italic lines*, full stop (v0.1.64: no "
                      "trailing 'Awake.' line), then the plain debrief, 📊 path last")
    else:
        _ui.dream_cue(f"the archive is open but the arc is incomplete ({arc_reason}) — backfill "
                      "the missing beats and re-render before waking")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
