#!/usr/bin/env python3
"""Dream beta-harness — the invariant ORACLE for the consolidate-memory skill (v2).

A reusable, any-repo regression oracle. It runs the skill's own READ-ONLY scripts
(`memory_status.py`, `sync_global.py`, `render_dashboard.py`) from a CLEAN subprocess
pinned to the target repo, cross-checks their outputs against each other and against
the live memory store, and asserts a small set of GENERAL invariant FAMILIES (SPEC
§4.1). Each family is a structural predicate over the full output + store, so it fires
on a NOVEL violation no one hand-wrote a field check for — not a hardcode of the field
that broke last time.

This is CONSUMER / beta-tester tooling. It lives OUTSIDE the skill
(`~/.claude/dream-beta-tester/`) and NEVER patches it.

Design (rebuilt from the v0.1.19 D-specific prototype, which was scaffolding):
  * DISCOVERY is portable + version-aware: env → --skill → broadened plugin-cache glob
    (`~/.claude/plugins/**/consolidate-memory/**/scripts/`) + the dev-checkout pattern,
    selecting the MAX version (parsed from the plugin.json manifest or the `<version>`
    path segment). The prototype's glob missed the real install and `sorted()[0]` picked
    the OLDEST version.
  * CWD-CONTAMINATION is closed: the resolved ABSOLUTE repo path is passed POSITIONALLY
    to every script (cwd is only a backstop). This is the literal D1/D2 contamination
    root cause the harness exists to prevent.
  * An ABSENT store is a first-class VALID clean outcome (store_absent), NOT a hard exit.
    The hard error is reserved for "skill scripts not found".
  * The skill's OWN pure helpers (`resolve_wikilink`, `_is_archive_index`,
    `index_fact_names`, `est_tokens`, `_LINK_RE`) are IMPORTED from the discovered
    (version-pinned) scripts dir, so the oracle's semantics match the version under test
    instead of drifting from a re-implementation.

Families (each ⊇ ≥1 catalog defect, but defined by the PRINCIPLE):
  * ground_truth_consistency  — a declared QUANTITY REGISTRY: each quantity pinned to ONE
                                definition + one extractor per surface; assert present
                                extractors agree + track the artifact (⊇ D1, D2, D11).
  * cycle_identity            — the cycle record's project == the target repo; its budget
                                matches the trigger node (⊇ the D1/D2 retraction root cause).
  * recommendation_coherence  — the skill's ACTUALLY-RENDERED recommendation never offers a
                                net-grow backfill under an active no-net-grow gate (⊇ D3).
  * safe_suggestion           — RECOMPUTE evict-orphans (skill triage A-stage) and FAIL if
                                any has >0 [[wikilink]] in-degree from an INDEXED fact, using
                                the skill's own resolve_wikilink (⊇ D4).
  * closure_reachability      — a PRUNE lever that can't reach budget must present the
                                prune-then-justify hint; dangling links flagged (⊇ D5, D10).
  * calibration               — a durable over-budget gate with no achievable resolution and
                                no standing-justify offer; an index-relief triage led by
                                zero-index-relief items (⊇ D6, D7, D8, D11) — WARN/advisory.

Every family returns ZERO-OR-MORE Result findings. Missing inputs → SKIP-with-reason,
never crash. The verdict basis for v0.1.21: D1/D2 CLEAR (PASS), D3/D5/D9/D10 PASS (the
skill fixed them — re-firing a fixed defect is itself an ORACLE bug), D4 RUNS via the
recompute and PASSES on clean Doc_Flo. Each PASS is tied to the FIXED behavior (the
rendered "do NOT backfill" clause / `reaches_budget` field / the prune-then-justify hint),
NOT the raw over-budget condition — so a genuine regression actually flips it.

Usage:
    python3 beta_checks.py [--repo DIR] [--store DIR] [--skill DIR] [--json]
      --repo   the repo whose dream we test (default: cwd) — sets the slug
      --store  memory store dir (default: ~/.claude/projects/<slug>/memory)
      --skill  consolidate-memory scripts dir (default: discovered, version-max)
      --json   emit the structured result as JSON (default: human summary)

Exit code: 1 if any FAIL, else 0. Scripts-not-found → 2.
"""
from __future__ import annotations

import argparse
import glob
import importlib
import json
import os
import re
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Any, Callable

# ─────────────────────────────── discovery (any-repo, version-aware) ───────────────────────────────

# A consolidate-memory script set we MUST be able to drive (the scripts-only floor).
_REQUIRED_SCRIPTS = ("memory_status.py", "sync_global.py", "render_dashboard.py")

_VER_SEG_RE = re.compile(r"(?:^|[^0-9])(\d+)\.(\d+)\.(\d+)(?:[^0-9]|$)")


def slug_for(repo: Path) -> str:
    """Claude Code project slug: the absolute path with EVERY non-alphanumeric char → '-' (case kept).

    Mirrors the skill's own `memory_status.slug_for` rule (v0.1.40 M3: re.sub(r'[^A-Za-z0-9]', '-', ...))
    so the oracle resolves the SAME store the skill does (see claude-code-memory-is-slug-scoped). We
    re-implement it (rather than import) only so discovery can run before the skill is found; once found,
    the skill's identical rule governs everything downstream. MUST stay in lockstep with the skill's rule.
    """
    return re.sub(r"[^A-Za-z0-9]", "-", str(repo.resolve()))


def default_store(repo: Path) -> Path:
    return Path.home() / ".claude" / "projects" / slug_for(repo) / "memory"


def _version_tuple(text: str) -> tuple[int, int, int]:
    """Parse a dotted MAJOR.MINOR.PATCH out of `text` → an orderable tuple; (-1,-1,-1) if none.

    Used to rank candidate skill installs by version. A dev checkout has no `<version>` path
    segment, so its version is read from the plugin.json manifest instead (see `_skill_version`)
    and threaded through this same comparator.
    """
    m = _VER_SEG_RE.search(text)
    if not m:
        return (-1, -1, -1)
    return (int(m.group(1)), int(m.group(2)), int(m.group(3)))


def _skill_version(scripts_dir: Path) -> str:
    """The version stamp for a discovered scripts dir.

    Order: the plugin manifest `<plugin-root>/.claude-plugin/plugin.json` ('version' key) —
    authoritative for BOTH a dev checkout (→ 0.1.21) and a cache install (→ its own number);
    else the `<version>` path segment of a cache install (`…/consolidate-memory/0.1.19/scripts`);
    else 'unknown'. Mirrors PORTABILITY P-4 / SPEC §8 so the report stamps the version UNDER TEST.
    """
    manifest = scripts_dir.parent / ".claude-plugin" / "plugin.json"
    try:
        if manifest.is_file():
            v = json.loads(manifest.read_text(encoding="utf-8")).get("version")
            if isinstance(v, str) and v.strip():
                return v.strip()
    except (OSError, json.JSONDecodeError):
        pass
    # cache layout: …/consolidate-memory/<version>/scripts → parent.name is <version>
    seg = scripts_dir.parent.name
    if _VER_SEG_RE.search(seg):
        return seg
    return "unknown"


def _candidate_dirs() -> list[Path]:
    """All plausible consolidate-memory scripts dirs across the known install roots.

    Broadened past the prototype (which missed the real cache install because a `<version>`
    dir sits between `consolidate-memory/` and `scripts/`, and string-`sorted()` picked the
    OLDEST): glob the plugin cache AND the dev checkout, then keep dirs that actually hold all
    the required scripts. De-duplicated (the dev `**` can match the nested
    `consolidate-memory/plugins/consolidate-memory` twice).
    """
    pats = [
        str(Path.home() / ".claude" / "plugins" / "**" / "consolidate-memory" / "**" / "scripts" / "memory_status.py"),
        str(Path.home() / "project" / "**" / "consolidate-memory" / "**" / "scripts" / "memory_status.py"),
        # keep the prototype's flatter dev pattern too (a checkout without the plugins/ nesting)
        str(Path.home() / "project" / "**" / "consolidate-memory" / "scripts" / "memory_status.py"),
    ]
    seen: set[Path] = set()
    out: list[Path] = []
    for pat in pats:
        for hit in glob.glob(pat, recursive=True):
            d = Path(hit).resolve().parent
            if d in seen:
                continue
            if all((d / s).is_file() for s in _REQUIRED_SCRIPTS):
                seen.add(d)
                out.append(d)
    return out


def discover_skill(override: str | None) -> Path | None:
    """Locate the consolidate-memory scripts dir, version-aware.

    Order (each must hold all required scripts): $CONSOLIDATE_MEMORY_SCRIPTS → --skill → the
    broadened+dev glob, picking MAX version. Returns None only after EVERY root misses (the one
    case that warrants a hard error). An explicit override / env value is honored verbatim — the
    operator chose it.
    """
    for explicit in (override, os.environ.get("CONSOLIDATE_MEMORY_SCRIPTS")):
        if explicit:
            d = Path(explicit).expanduser().resolve()
            if all((d / s).is_file() for s in _REQUIRED_SCRIPTS):
                return d
    cands = _candidate_dirs()
    if not cands:
        return None
    # rank by version (manifest-or-segment); ties broken by mtime so a re-touched dev wins.
    return max(cands, key=lambda d: (_version_tuple(_skill_version(d)), d.stat().st_mtime))


def import_skill_module(scripts_dir: Path) -> ModuleType | None:
    """Import the discovered `memory_status` so the oracle reuses the skill's OWN pure helpers
    (`resolve_wikilink`, `_is_archive_index`, `index_fact_names`, `est_tokens`, `_LINK_RE`) at the
    version under test — fidelity over a drifting re-implementation. Best-effort: a failure (an
    incompatible/old module) degrades to None and the families fall back to local equivalents.
    """
    sd = str(scripts_dir)
    if sd not in sys.path:
        sys.path.insert(0, sd)
    try:
        mod = importlib.import_module("memory_status")
        # Make sure we got THIS dir's copy (another consolidate-memory may already be imported).
        if Path(getattr(mod, "__file__", "")).resolve().parent != scripts_dir:
            importlib.reload(mod)
        return mod
    except Exception:  # noqa: BLE001 — any import failure must degrade, not crash the oracle
        return None


# ─────────────────────────────── subprocess JSON (robust) ───────────────────────────────


def _run_json(cmd: list[str], cwd: Path) -> tuple[dict[str, Any], str | None]:
    """Run `cmd` (cwd=`cwd`) and parse its stdout JSON. Returns (obj, error_note).

    Robust per SPEC ("SKIP-with-reason, never crash"): a non-zero return code, a timeout, an OS
    error, or unparseable output yields ({}, note) so callers SKIP with the REAL reason. Parsing
    tries the WHOLE stdout first (the contract — these scripts emit pure JSON), then falls back to
    the LAST balanced {...} object (tolerating a stray leading log line), fixing the prototype's
    `txt.find('{')` (FIRST brace) bug that would crash on any leading '{'.
    """
    try:
        out = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=120, check=False)
    except (OSError, subprocess.SubprocessError) as e:
        return {}, f"{cmd[1] if len(cmd) > 1 else cmd[0]} failed to run: {type(e).__name__}: {e}"
    txt = (out.stdout or "").strip()
    if out.returncode != 0 and not txt:
        err = (out.stderr or "").strip().splitlines()
        return {}, f"exit {out.returncode}: {err[-1] if err else 'no output'}"
    if not txt:
        return {}, "empty stdout"
    try:
        obj = json.loads(txt)
        return (obj, None) if isinstance(obj, dict) else ({}, "top-level JSON is not an object")
    except json.JSONDecodeError:
        pass
    obj = _last_json_object(txt)
    if obj is not None:
        return obj, None
    return {}, "stdout was not parseable as JSON"


def _last_json_object(txt: str) -> dict[str, Any] | None:
    """The LAST TOP-LEVEL balanced {...} object in `txt`, or None.

    String/escape aware (a brace inside a JSON string can't unbalance the scan). Walks FORWARD and
    collects each top-level balanced `{...}` span (a `{` at depth 0), then returns the LAST one that
    parses to a dict. 'Top-level' is the key correctness property: a `{` that opens a NESTED object
    is consumed inside its parent's span and never starts its own candidate — so a leading non-JSON
    `{config}` log token is tried-and-rejected, and we land on the OUTERMOST record, not the deepest
    nested `{...}` (the bug a naive last-brace scan has). This is the fallback for the prototype's
    `txt.find('{')` (FIRST brace) crash on any leading-brace line.
    """
    best: dict[str, Any] | None = None
    i = 0
    n = len(txt)
    while i < n:
        if txt[i] != "{":
            i += 1
            continue
        depth = 0
        in_str = False
        esc = False
        end = -1
        for j in range(i, n):
            ch = txt[j]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end = j
                    break
        if end == -1:  # unbalanced from here to EOF — no top-level object starts at i
            i += 1
            continue
        try:
            obj = json.loads(txt[i : end + 1])
        except json.JSONDecodeError:
            obj = None
        if isinstance(obj, dict):
            best = obj  # keep the LAST parseable top-level object
        i = end + 1  # skip past this whole top-level span (its nested braces are not candidates)
    return best


def _run_text(cmd: list[str], cwd: Path) -> tuple[str, str | None]:
    """Run `cmd` and return (stdout, error_note). Never raises. Used for the RENDERED human reports
    that the recommendation/closure families grep for a quoted source-contradiction."""
    try:
        out = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=120, check=False)
    except (OSError, subprocess.SubprocessError) as e:
        return "", f"{cmd[1] if len(cmd) > 1 else cmd[0]} failed to run: {type(e).__name__}: {e}"
    return out.stdout or "", None


# ─────────────────────────────── context gathering ───────────────────────────────


@dataclass
class Ctx:
    repo: Path
    store: Path
    skill: Path
    skill_version: str
    store_present: bool
    ms: ModuleType | None  # the discovered memory_status module (skill's own helpers), or None
    status: dict[str, Any]  # memory_status.py <repo> --json (seed cycle record)
    network: dict[str, Any]  # sync_global.py --tokens <repo> --json
    render_text: str  # render_dashboard.py rendered from the (seed+network) record — DERIVED surface
    status_report_text: str  # memory_status.py <repo> (human report) — the ACTUALLY-EMITTED recommendation
    triage_text: str  # memory_status.py <repo> --triage (focused remediation view)
    file_bytes: dict[str, int]  # fact stem -> bytes  (archive-index docs excluded)
    file_chars: dict[str, int]  # fact stem -> utf-8 char count (for the skill's est_tokens ground-truth)
    fact_stems: set[str]  # archive-excluded fact stems (the recompute basis)
    index_targets: list[str]  # fact stems an index pointer points at (archive stems dropped)
    archive_stems: set[str]  # archive-index docs (SHIPPED.md et al.) — NOT facts
    wikilink_targets: dict[str, set[str]]  # RESOLVED target stem -> {referrer stems} (skill semantics)
    raw_wikilinks: set[str]  # every raw [[target]] seen (for dangling detection)
    log_records: list[dict[str, Any]] = field(default_factory=list)  # v0.1.54: parsed .consolidation-log.jsonl (persisted dreams, oldest-first)
    notes: list[str] = field(default_factory=list)


def _local_norm(s: str) -> str:
    """Fallback normalization (dash↔underscore, lowercased) — mirrors the skill's resolve_wikilink
    inner `_norm`. ONLY used if the skill module didn't import; otherwise the skill's
    resolve_wikilink governs and this isn't consulted for in-degree."""
    return re.sub(r"[-_]", "-", s).lower()


def _is_archive_index_local(path: Path, link_re: re.Pattern[str]) -> bool:
    """Local fallback for the skill's `_is_archive_index`: a `*.md` with NO `---` frontmatter and
    ≥3 `](x.md)` links is an archive index (link-list), not a fact. Only used if the skill module
    is unavailable."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    if text.lstrip("﻿").lstrip().startswith("---"):
        return False
    return len(link_re.findall(text)) >= 3


def gather(repo: Path, store: Path, skill: Path, ms: ModuleType | None, skill_version: str) -> Ctx:
    """Build the Ctx by driving the skill's read-only scripts (repo passed POSITIONALLY to close
    the cwd-contamination vector) + reading the live store with the skill's own helpers."""
    py = sys.executable
    repo_arg = str(repo)

    status, status_err = _run_json([py, str(skill / "memory_status.py"), repo_arg, "--json"], cwd=repo)
    network, net_err = _run_json([py, str(skill / "sync_global.py"), "--tokens", repo_arg, "--json"], cwd=repo)
    status_report_text, _ = _run_text([py, str(skill / "memory_status.py"), repo_arg, "--no-color", "--ascii"], cwd=repo)
    triage_text, _ = _run_text([py, str(skill / "memory_status.py"), repo_arg, "--triage", "--no-color", "--ascii"], cwd=repo)

    notes: list[str] = []
    if status_err:
        notes.append(f"memory_status --json: {status_err}")
    if net_err:
        notes.append(f"sync_global --tokens --json: {net_err}")

    store_present = store.exists()

    # The skill's pointer-link anchor + archive-detector — IMPORTED so the oracle's view matches the
    # version under test. Fall back to local equivalents if absent. (est_tokens is reused directly from
    # ctx.ms inside the registry's artifact extractor, so it isn't bound here.)
    link_re: re.Pattern[str] = getattr(ms, "_LINK_RE", None) or re.compile(r"\]\(([^)]+)\.md\)")

    def is_archive(p: Path) -> bool:
        fn = getattr(ms, "_is_archive_index", None)
        return fn(p) if fn else _is_archive_index_local(p, link_re)

    file_bytes: dict[str, int] = {}
    file_chars: dict[str, int] = {}
    fact_stems: set[str] = set()
    archive_stems: set[str] = set()
    raw_wikilinks: set[str] = set()
    referrers: dict[str, set[str]] = {}  # target stem (raw, pre-resolve) -> {referrer stems}

    store_md = sorted(f for f in store.glob("*.md") if f.name != "MEMORY.md") if store_present else []
    # Split facts vs archive-index docs exactly as build_context does (so SHIPPED.md is not a fact).
    archive_docs = [f for f in store_md if is_archive(f)]
    archive_stems = {f.stem for f in archive_docs}
    fact_files = [f for f in store_md if f not in archive_docs]

    for f in fact_files:
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        fact_stems.add(f.stem)
        try:
            file_bytes[f.stem] = f.stat().st_size
        except OSError:
            file_bytes[f.stem] = len(text.encode("utf-8"))
        file_chars[f.stem] = len(text)
        body = re.sub(r"`[^`]*`", "", text)  # strip inline code spans so a fenced [[x]] doesn't count
        for tgt in re.findall(r"\[\[([^\]]+)\]\]", body):
            tgt = tgt.strip()
            raw_wikilinks.add(tgt)
            referrers.setdefault(tgt, set()).add(f.stem)

    index_md = store / "MEMORY.md"
    _index_fact_names: Callable[[Path], set[str]] | None = getattr(ms, "index_fact_names", None)
    if _index_fact_names is not None and store_present:
        index_targets = sorted(_index_fact_names(index_md) - archive_stems)
    else:
        idx_txt = index_md.read_text(encoding="utf-8", errors="replace") if index_md.exists() else ""
        index_targets = sorted(set(link_re.findall(idx_txt)) - archive_stems)

    # Resolve every wikilink target to an EXISTING fact stem with the skill's OWN resolve_wikilink
    # (exact → normalized → distinctive date-stripped base; ambiguous → skip), so wikilink in-degree
    # MATCHES what the skill folds into reference_stems. Fall back to a normalized-exact match.
    resolve = getattr(ms, "resolve_wikilink", None)
    wikilink_targets: dict[str, set[str]] = {}
    for raw_tgt, refs in referrers.items():
        if resolve is not None:
            resolved = resolve(raw_tgt, set(fact_stems))
        else:
            nt = _local_norm(raw_tgt)
            hits = [s for s in fact_stems if _local_norm(s) == nt]
            resolved = hits[0] if len(hits) == 1 else None
        if resolved:
            wikilink_targets.setdefault(resolved, set()).update(refs)

    # Render the dashboard from the seed record + spliced network (the DERIVED surface), driven from
    # the skill's own --seed temp file (NOT a dotfile in the live slug dir — PORTABILITY P-5). Cheap,
    # and we never write into managed state.
    render_text = ""
    if status:
        seed_path = network_seed_path = None
        try:
            import tempfile

            cycle = dict(status)
            if network:
                cycle["network"] = network
            cycle.setdefault("session", "beta-oracle")
            fd, seed_path = tempfile.mkstemp(prefix="cm-beta-cycle", suffix=".json")
            os.close(fd)
            Path(seed_path).write_text(json.dumps(cycle), encoding="utf-8")
            render_text, render_err = _run_text(
                [py, str(skill / "render_dashboard.py"), seed_path, "--no-color", "--ascii"], cwd=repo
            )
            if render_err:
                notes.append(f"render_dashboard: {render_err}")
        except OSError as e:
            notes.append(f"render setup failed: {type(e).__name__}: {e}")
        finally:
            for p in (seed_path, network_seed_path):
                if p:
                    try:
                        os.unlink(p)
                    except OSError:
                        pass

    # v0.1.54: the persisted-record channel — the consolidation log the dream's terminal --persist
    # appends to (same tolerant line-JSON read as render_html.read_history). The dream_arc_capture
    # family inspects the LATEST record; a corrupt line is skipped, a missing log stays [].
    log_records: list[dict[str, Any]] = []
    log_path = store / ".consolidation-log.jsonl"
    if store_present and log_path.exists():
        try:
            for line in log_path.read_text(encoding="utf-8", errors="replace").splitlines():
                s = line.strip()
                if not s:
                    continue
                try:
                    rec = json.loads(s)
                except (json.JSONDecodeError, ValueError):
                    continue
                if isinstance(rec, dict):
                    log_records.append(rec)
        except OSError as e:
            notes.append(f"consolidation-log read failed: {type(e).__name__}: {e}")

    return Ctx(
        repo=repo, store=store, skill=skill, skill_version=skill_version, store_present=store_present,
        ms=ms, status=status, network=network, render_text=render_text,
        status_report_text=status_report_text, triage_text=triage_text,
        file_bytes=file_bytes, file_chars=file_chars, fact_stems=fact_stems,
        index_targets=index_targets, archive_stems=archive_stems,
        wikilink_targets=wikilink_targets, raw_wikilinks=raw_wikilinks,
        log_records=log_records, notes=notes,
    )


# ─────────────────────────────── result model + family registry ───────────────────────────────


@dataclass
class Result:
    family: str  # the invariant family (SPEC §4.1)
    id: str  # stable check id (CHK-…)
    title: str
    severity: str  # HIGH | MED | LOW
    status: str  # PASS | FAIL | WARN | SKIP
    expected: str
    actual: str
    evidence: str
    site: str  # where it fired (a stem, a surface, a quantity)
    defect_ref: str  # e.g. "D1" (the motivating catalog item, for the lifecycle diff)
    basis: str  # "rendered" (quoted from a real human report) | "reconstructed" (--json proxy) | "structural"
    quote: str  # the literal quoted line from a rendered surface, when basis == "rendered" (else "")


# A family is `(Ctx) -> list[Result]` (zero or more findings). Adding a family is rare; adding a
# SITE a family scans is automatic.
FAMILIES: list[Callable[[Ctx], list[Result]]] = []


def family(fn: Callable[[Ctx], list[Result]]) -> Callable[[Ctx], list[Result]]:
    FAMILIES.append(fn)
    return fn


def _R(family_name: str, cid: str, title: str, severity: str, status: str, expected: str, actual: str,
       evidence: str, site: str, defect_ref: str, basis: str = "structural", quote: str = "") -> Result:
    return Result(family_name, cid, title, severity, status, expected, actual, evidence, site,
                  defect_ref, basis, quote)


# ── shared, corrected helpers (single definition; reused across families) ─────────────────────


def _trigger_node(ctx: Ctx) -> dict[str, Any] | None:
    """The sync_global node flagged trigger=True (the target repo's own node)."""
    nodes = ctx.network.get("nodes") or ctx.network.get("network", {}).get("nodes", [])
    trig = [n for n in nodes if n.get("trigger")]
    return trig[0] if trig else None


def _grep_quote(text: str, pattern: str) -> str | None:
    """The first line of `text` matching `pattern` (case-insensitive), control-stripped + collapsed
    to one whitespace-run — the literal QUOTED evidence the report's 2a-VERIFIED bar demands. None
    if no match."""
    if not text:
        return None
    rx = re.compile(pattern, re.IGNORECASE)
    for raw in text.splitlines():
        if rx.search(raw):
            return re.sub(r"\s+", " ", re.sub(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]", "", raw)).strip()
    return None


def _unpointed_facts(ctx: Ctx) -> set[str]:
    """Archive-excluded fact stems with NO index pointer — RAW-vs-RAW (both sides un-normalized).

    This is the corrected d3/d4 basis: the skill's `schema_drift.index_mismatch` is
    `len(stems ^ index_names)` over raw stems, and the 11 hyphenated user-global facts ARE pointed
    in hyphenated form, so normalizing only ONE side (the prototype bug) inflates the count. Verified
    on Doc_Flo: raw−raw = 61 == the skill's index_mismatch.
    """
    return ctx.fact_stems - set(ctx.index_targets)


def _indexed_wikilink_indegree(ctx: Ctx, stem: str) -> set[str]:
    """Referrers of `stem` (via RESOLVED [[wikilinks]]) that are themselves INDEXED facts.

    The in-degree that makes a fact unsafe to evict (D4): evicting it would dangle a link from a
    fact the always-loaded index points at. Uses the skill's resolve_wikilink semantics (applied in
    gather), so it matches what the skill folds into reference_stems — no substring over-claim.
    """
    indexed = set(ctx.index_targets)
    return {r for r in ctx.wikilink_targets.get(stem, set()) if r in indexed}


def _skill_triage(ctx: Ctx) -> dict[str, Any] | None:
    """Re-run the skill's PURE remediation triage to read its ACTUAL staged candidates (the --json
    seed only surfaces a count, not the stages). Returns the full triage dict, or None if the skill
    module / store is unavailable or the index is under budget. This is what lets the safe-suggestion
    family check the skill's REAL evict (A-stage) set instead of a guessed orphan list.
    """
    ms = ctx.ms
    if ms is None or not ctx.store_present:
        return None
    build: Callable[[Path], dict[str, Any]] | None = getattr(ms, "build_context", None)
    triage: Callable[..., dict[str, Any]] | None = getattr(ms, "remediation_triage", None)
    if build is None or triage is None:
        return None
    try:
        bctx: dict[str, Any] = build(ctx.repo)
    except Exception:  # noqa: BLE001 — a build failure must SKIP, not crash
        return None
    rem = bctx.get("remediation") or {}
    # build_context already ran the full triage (incl. reference_stems with wikilink folding) when
    # over budget; if it suppressed (standing-justified) or stayed under budget, there are no stages.
    return rem if isinstance(rem, dict) and rem.get("stages") else None


# ─────────────────────────────── FAMILY 1: ground-truth & internal consistency ───────────────────


# The DECLARED QUANTITY REGISTRY. Each entry pins ONE quantity to ONE definition + one extractor per
# surface it legitimately appears on. CRITICAL (the D1 false-fail lesson): never cross-compare two
# DIFFERENT quantities that merely share a label. The three quantities below are deliberately SEPARATE
# (json/render/network all report 2926 for the index, 106 for recall facts, and node.facts=107 is a
# THIRD store-glob count that legitimately differs) — so each is its own registry row and they are
# NEVER asserted equal to each other.
#
# extractors: json (dotted path into the seed record) · render (regex group 1 on the rendered text) ·
# network (a function of the trigger node) · artifact (a ground-truth recompute from the store).


def _json_path(d: dict[str, Any], path: str) -> Any:
    cur: Any = d
    for part in path.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


def _render_int(text: str, pattern: str) -> int | None:
    m = re.search(pattern, text)
    return int(m.group(1)) if m else None


# Each registry entry: (quantity, severity, defect_ref, json_path, render_regex, network_fn, artifact_fn)
# network_fn / artifact_fn take Ctx and the trigger node and return an int-or-None.
def _artifact_index_tokens(ctx: Ctx) -> int | None:
    """Ground-truth always-loaded index tokens = the skill's est_tokens over the DECODED MEMORY.md
    text (NOT st_size//4): est_tokens = (len(decoded)+3)//4. The byte//4 proxy under-counts a
    non-ASCII (box-drawing/emoji) index — verified Δ≈50 on Doc_Flo's MEMORY.md, band-absorbed now but
    a heavier index would false-FAIL. So we recompute on the decoded text exactly as the skill does."""
    if not ctx.store_present:
        return None
    p = ctx.store / "MEMORY.md"
    if not p.exists():
        return 0
    est = getattr(ctx.ms, "est_tokens", lambda t: (len(t) + 3) // 4)
    try:
        return est(p.read_text(encoding="utf-8", errors="replace"))
    except OSError:
        return None


_REGISTRY: list[dict[str, Any]] = [
    {
        "quantity": "always_loaded_index_tokens",
        "severity": "HIGH",
        "defect_ref": "D2",
        "json_path": "budget.index.after_tokens",
        "render_regex": r"auto-mem index\s*[≈~]?\s*(\d+)\s*/\s*\d+",
        "network_fn": lambda ctx, node: (node or {}).get("always_loaded_tokens"),
        "artifact_fn": _artifact_index_tokens,
        "artifact_label": "MEMORY.md est_tokens(decoded)",
    },
    {
        "quantity": "recall_fact_count",
        "severity": "MED",
        "defect_ref": "D1",
        "json_path": "budget.recall_facts.after",
        "render_regex": r"recall facts\s+(\d+)",
        "network_fn": None,  # node.facts is a DIFFERENT (raw-glob) quantity — never cross-assert it here
        "artifact_fn": lambda ctx: len(ctx.fact_stems) if ctx.store_present else None,
        "artifact_label": "archive-excluded fact files",
    },
]


@family
def ground_truth_consistency(ctx: Ctx) -> list[Result]:
    """For each declared quantity, run all PRESENT extractors and assert they (a) agree across
    surfaces and (b) track the artifact ground-truth. ⊇ D1, D2, D11.

    PROVENANCE HONESTY (SPEC §4.1): in scripts-only mode render is driven FROM the same
    memory_status record, so json==render BY CONSTRUCTION — that agreement leg is an IDENTITY
    assertion, not independent corroboration. The real signal is the ARTIFACT ground-truth leg
    (recompute from the store) + the network leg (an INDEPENDENT script). A pure surface-agreement
    mismatch is reported as an identity/plumbing defect; the ground-truth mismatch is the substantive
    one. We never FAIL on a known definitional gap (e.g. recall_facts 106 vs node.facts 107) because
    those are SEPARATE registry rows.
    """
    out: list[Result] = []
    if not ctx.status and not ctx.store_present:
        return [_R("ground_truth", "CHK-QTY", "Quantity registry", "HIGH", "SKIP",
                   "at least one surface present", "no --json record and no store",
                   "could not gather any surface to cross-check", "-", "D2")]
    node = _trigger_node(ctx)
    for spec in _REGISTRY:
        q = spec["quantity"]
        surfaces: dict[str, int] = {}
        jp = _json_path(ctx.status, spec["json_path"])
        if isinstance(jp, int):
            surfaces["json"] = jp
        rv = _render_int(ctx.render_text, spec["render_regex"]) if ctx.render_text else None
        if rv is not None:
            surfaces["render"] = rv
        if spec["network_fn"] is not None:
            nv = spec["network_fn"](ctx, node)
            if isinstance(nv, int):
                surfaces["network"] = nv
        artifact = spec["artifact_fn"](ctx)

        if not surfaces and artifact is None:
            out.append(_R("ground_truth", f"CHK-QTY-{q}", f"Quantity '{q}' consistent + grounded",
                          spec["severity"], "SKIP", "≥1 extractor present",
                          "no surface or artifact extractor produced a value",
                          "all extractors absent for this quantity", q, spec["defect_ref"]))
            continue

        # (a) cross-surface agreement. In scripts-only mode render is driven FROM the json record, so
        # json↔render is an IDENTITY (plumbing), NOT independent corroboration — a split there is a real
        # render/plumbing bug but not the D1/D2 cross-script class. `network` is the one INDEPENDENT
        # script, so a json↔network split is the SEVERE (full-severity) contradiction — that is the
        # actual D1/D2 wrong-budget signature. We grade accordingly and disclose the identity caveat.
        surfaces_str = ", ".join(f"{k}={v}" for k, v in sorted(surfaces.items())) or "(none)"
        net_val = surfaces.get("network")
        non_net_vals = {v for k, v in surfaces.items() if k != "network"}
        if len(set(surfaces.values())) > 1:
            independent_split = net_val is not None and any(v != net_val for v in non_net_vals)
            sev = spec["severity"] if independent_split else "MED"
            reason = ("an INDEPENDENT script (sync_global) disagrees with the record — the D1/D2 "
                      "wrong-budget signature" if independent_split else
                      "render is derived from the json record, so this split is a render/plumbing identity bug")
            out.append(_R("ground_truth", f"CHK-QTY-{q}-AGREE", f"Quantity '{q}' agrees across surfaces",
                          sev, "FAIL",
                          f"all surfaces report one value for {q}",
                          f"surfaces disagree: {surfaces_str}",
                          reason, q, spec["defect_ref"], basis="reconstructed"))
        else:
            out.append(_R("ground_truth", f"CHK-QTY-{q}-AGREE", f"Quantity '{q}' agrees across surfaces",
                          "LOW", "PASS",
                          f"all surfaces report one value for {q}",
                          f"agree: {surfaces_str}",
                          "surfaces consistent (note: json↔render is an identity in scripts-only mode; "
                          "the independent leg is network)",
                          q, spec["defect_ref"]))

        # (b) ground-truth: the reported value tracks the recomputed artifact (the SUBSTANTIVE leg).
        if artifact is not None and surfaces:
            reported = surfaces.get("json", surfaces.get("network", next(iter(surfaces.values()))))
            tol = max(50, int(0.10 * artifact)) if q.endswith("tokens") else 0
            ok = abs(reported - artifact) <= tol
            out.append(_R("ground_truth", f"CHK-QTY-{q}-TRUTH", f"Quantity '{q}' tracks the store",
                          spec["severity"], "PASS" if ok else "FAIL",
                          f"reported {q} ≈ artifact {artifact} ({spec['artifact_label']})"
                          + (f" ±{tol}" if tol else ""),
                          f"reported={reported}, artifact={artifact}",
                          f"ground-truth recompute {spec['artifact_label']}={artifact}; reported={reported}; "
                          f"Δ={abs(reported - artifact)}",
                          q, spec["defect_ref"], basis="structural"))
    return out


# ─────────────────────────────── FAMILY 2: cycle identity ───────────────────────────────


@family
def cycle_identity(ctx: Ctx) -> list[Result]:
    """The cycle record's project == the target repo, and its index budget matches the trigger node.

    This is the catalog's single most important invariant (the D1/D2 RETRACTION root cause: a
    contaminated cycle.json carried ANOTHER project's budget). In scripts-only mode the seed is built
    FROM the target, so this is largely an IDENTITY assertion — its real teeth are the full-dream path,
    where a contaminated record (another project's project/budget) is the failure. We note that coverage
    limit on the finding.
    """
    if not ctx.status:
        return [_R("cycle_identity", "CHK-CYCLE-IDENTITY", "Cycle record identifies the target repo",
                   "HIGH", "SKIP", "a --json cycle seed", "no record",
                   "memory_status --json produced no record to identity-check", "-", "D1")]
    out: list[Result] = []
    proj = ctx.status.get("project")
    want = ctx.repo.resolve().name
    ok_proj = proj == want
    out.append(_R("cycle_identity", "CHK-CYCLE-PROJECT", "Cycle record project == target repo",
                  "HIGH", "PASS" if ok_proj else "FAIL",
                  f"project == '{want}'", f"project == '{proj}'",
                  f"the cycle record names project='{proj}'; target repo basename='{want}' "
                  "(scripts-only: identity by construction; the teeth are the full-dream contaminated-record case)",
                  "project", "D1"))

    # budget ↔ trigger node consistency (the contaminated-budget signature).
    node = _trigger_node(ctx)
    jtok = _json_path(ctx.status, "budget.index.after_tokens")
    if node is not None and isinstance(jtok, int):
        ntok = node.get("always_loaded_tokens")
        ok_bud = isinstance(ntok, int) and abs(jtok - ntok) <= max(50, int(0.10 * ntok))
        out.append(_R("cycle_identity", "CHK-CYCLE-BUDGET", "Cycle budget matches the trigger node",
                      "HIGH", "PASS" if ok_bud else "FAIL",
                      f"record index ≈ trigger node always-loaded ({ntok})",
                      f"record index={jtok}, trigger node={ntok}",
                      f"trigger node '{node.get('node')}' always_loaded_tokens={ntok}; record "
                      f"budget.index.after_tokens={jtok} (a split = a wrong-project/contaminated budget)",
                      "budget.index", "D1"))
    return out


# ─────────────────────────────── FAMILY 3: recommendation coherence ───────────────────────────────


@family
def recommendation_coherence(ctx: Ctx) -> list[Result]:
    """The skill never OFFERS a net-grow index backfill while an over-budget no-net-grow gate is
    active. ⊇ D3.

    Defined over the skill's ACTUALLY-EMITTED recommendation in its RENDERED human report (not a
    recomputed --json condition — the prototype's d3 false-failed on v0.1.21 by re-deriving "over AND
    unpointed>0", which stays 'contradictory' on a store the skill now correctly labels intentional).
    The gate-suppressed wording 'do NOT backfill — net-grows' reads as PASS; a literal 'offer backfill'
    co-occurring with an active gate is the FAIL, quoted from the report.
    """
    rem = ctx.status.get("remediation") or {}
    over = bool(rem.get("required"))
    text = ctx.status_report_text
    if not text:
        return [_R("recommendation_coherence", "CHK-GATE-BACKFILL", "No backfill offer under an active gate",
                   "HIGH", "SKIP", "the rendered status report", "could not capture memory_status output",
                   "no human report text to read the actual recommendation from", "-", "D3")]

    offer = _grep_quote(text, r"offer backfill")
    suppress = _grep_quote(text, r"do NOT backfill|INTENTIONAL, do NOT")
    n_unpointed = len(_unpointed_facts(ctx))

    if over and offer:
        return [_R("recommendation_coherence", "CHK-GATE-BACKFILL", "No backfill offer under an active gate",
                   "HIGH", "FAIL",
                   "over-budget gate ⇒ NO net-grow backfill offer",
                   f"gate active AND the report offers backfill ({n_unpointed} un-indexed facts)",
                   "the active over-budget gate co-occurs with a literal backfill offer in the same report",
                   "schema-drift line", "D3", basis="rendered", quote=offer)]

    if over and suppress:
        return [_R("recommendation_coherence", "CHK-GATE-BACKFILL", "No backfill offer under an active gate",
                   "HIGH", "PASS",
                   "over-budget gate ⇒ no net-grow backfill offer",
                   "gate active AND the report suppresses backfill (labels the un-indexed set intentional)",
                   f"the {n_unpointed} un-indexed facts are framed as intentional ('do NOT backfill — net-grows'), "
                   "not offered for net-grow under the gate",
                   "schema-drift line", "D3", basis="rendered", quote=suppress)]

    # Not over budget (backfill is legitimate), or no drift line at all → coherent by definition.
    return [_R("recommendation_coherence", "CHK-GATE-BACKFILL", "No backfill offer under an active gate",
               "HIGH", "PASS",
               "no contradiction between the gate and the backfill recommendation",
               f"gate_active={over}; backfill_offer={'yes' if offer else 'no'}",
               "no active-gate + net-grow-offer contradiction in the rendered report"
               + (f" (under budget → backfill legitimate; {n_unpointed} un-indexed)" if not over else ""),
               "schema-drift line", "D3", basis="rendered" if (offer or suppress) else "structural",
               quote=(offer or suppress or ""))]


# ─────────────────────────────── FAMILY 4: safe-suggestion (orphan recompute) ───────────────────────────────


@family
def safe_suggestion(ctx: Ctx) -> list[Result]:
    """No destructive 'evict' suggestion targets a still-referenced fact. ⊇ D4 (SPEC §4.4).

    Two complementary legs, both RECOMPUTING (never parsing human text):
      (1) The skill's REAL triage A-stage (TRUE-orphan → evict) is read via remediation_triage; any
          A-stage stem with >0 [[wikilink]] in-degree from an INDEXED fact is a FAIL (the skill should
          have protected it). On v0.1.21 this PASSES because the skill now folds resolved wikilink
          targets into reference_stems (D4 fixed in code) — so the check REGRESSION-guards that fix.
      (2) A skill-independent recompute: orphans := fact_stems − index_targets, flag any with indexed
          wikilink in-degree. This fires even if the triage isn't available, and documents WHICH facts
          the fix protects (here: form_table_research_2026_06_15, grounding_gate_overrefusal_2026_06_06).
    """
    out: list[Result] = []
    if not ctx.store_present:
        return [_R("safe_suggestion", "CHK-ORPHAN-LINKS", "Evict-orphans have 0 indexed-wikilink in-degree",
                   "MED", "SKIP", "a live store", "no store on disk",
                   "store absent — no orphans to recompute", "-", "D4")]

    # ── leg (1): the skill's ACTUAL evict (A-stage) set ──
    triage = _skill_triage(ctx)
    if triage is not None:
        a_stage = [c.get("stem") for c in triage.get("stages", {}).get("A_orphans", []) if c.get("stem")]
        offenders = []
        for stem in a_stage:
            ref = _indexed_wikilink_indegree(ctx, stem)
            if ref:
                offenders.append(f"{stem} ← {sorted(ref)}")
        if offenders:
            out.append(_R("safe_suggestion", "CHK-EVICT-STAGE", "Skill evict-stage spares wikilinked facts",
                          "MED", "FAIL",
                          "every A-stage (evict) orphan has 0 indexed-wikilink in-degree",
                          f"{len(offenders)} A-stage orphan(s) are wikilink-reachable from INDEXED facts",
                          "; ".join(offenders), "remediation A-stage", "D4", basis="reconstructed"))
        else:
            out.append(_R("safe_suggestion", "CHK-EVICT-STAGE", "Skill evict-stage spares wikilinked facts",
                          "MED", "PASS",
                          "every A-stage (evict) orphan has 0 indexed-wikilink in-degree",
                          f"A-stage has {len(a_stage)} orphan(s), none wikilink-reachable from indexed facts",
                          f"skill A_orphans={a_stage or '(empty)'}; the skill folds resolved wikilink targets "
                          "into reference_stems (D4 fixed) so reachable facts are routed to R_referenced, not A",
                          "remediation A-stage", "D4", basis="reconstructed"))

    # ── leg (2): skill-independent orphan recompute (regression-guard + provenance of the fix) ──
    orphans = _unpointed_facts(ctx)
    reachable = {s: _indexed_wikilink_indegree(ctx, s) for s in orphans}
    flagged = {s: r for s, r in reachable.items() if r}
    # This leg does NOT FAIL on its own (an un-indexed fact that is wikilink-reachable is exactly what
    # the skill PROTECTS via R_referenced) — it's the evidence the protection is needed. It only FAILs
    # if leg (1) is unavailable AND such a fact appears in a destructive suggestion; here we report it
    # as the PASS-with-evidence that the safety property holds.
    if flagged:
        sample = "; ".join(f"{s} ← {sorted(r)[:3]}" for s, r in sorted(flagged.items())[:6])
        out.append(_R("safe_suggestion", "CHK-ORPHAN-LINKS", "Wikilink-reachable un-indexed facts are NOT evicted",
                      "MED", "PASS",
                      "no un-indexed-but-wikilink-reachable fact is offered for eviction",
                      f"{len(flagged)} un-indexed fact(s) are wikilink-reachable from indexed facts — "
                      "must be R_referenced (de-link-first), never A_orphans (evict)",
                      sample, "orphan recompute", "D4", basis="structural"))
    else:
        out.append(_R("safe_suggestion", "CHK-ORPHAN-LINKS", "Wikilink-reachable un-indexed facts are NOT evicted",
                      "MED", "PASS",
                      "no un-indexed-but-wikilink-reachable fact present",
                      f"{len(orphans)} un-indexed fact(s); none reachable via an indexed-fact wikilink",
                      "no evict-safety hazard to guard this run", "orphan recompute", "D4"))
    return out


# ─────────────────────────────── FAMILY 5: closure / reachability ───────────────────────────────


@family
def closure_reachability(ctx: Ctx) -> list[Result]:
    """Every recommended action is achievable; dangling links are flagged. ⊇ D5, D10.

    D5: read remediation.reaches_budget from the --json record (the skill's OWN field, not a recomputed
    proj≤budget) — the prototype false-failed by testing raw 2280>1200. When lever=='prune' AND
    reaches_budget==False, the HONEST check is whether the rendered report PRESENTS the prune-then-justify
    hint (the skill already prints 'prune the safe candidates, THEN standing-justify the residual'); PASS
    iff that hint is present, FAIL only if a clean achievable 'prune' is presented with no such hint.

    D10: dangling [[wikilinks]] (targets resolving to no fact via the skill's resolve_wikilink) are
    surfaced; a resolvable slug-drift target is suggested only where resolve_wikilink would accept it
    (never an over-claimed substring match).
    """
    out: list[Result] = []
    rem = ctx.status.get("remediation") or {}

    # ── D5: prune reachability ──
    if rem.get("required") and rem.get("lever") == "prune":
        reaches = rem.get("reaches_budget")
        if reaches is False:
            hint = _grep_quote(ctx.status_report_text, r"prune.*THEN.*justif|prune-safe-THEN|can't reach budget")
            hint = hint or _grep_quote(ctx.triage_text, r"prune.*THEN.*justif|prune-safe-THEN|can't reach budget")
            if hint:
                out.append(_R("closure_reachability", "CHK-PRUNE-REACH", "Unreachable prune presents the hybrid hint",
                              "MED", "PASS",
                              "lever=prune & !reaches_budget ⇒ the report shows prune-then-standing-justify",
                              "the prune-then-justify hint is present",
                              "the skill flags the prune as unable to reach budget and routes to prune-the-safe-"
                              "THEN-standing-justify the residual (no clean achievable 'prune' claimed)",
                              "remediation hint", "D5", basis="rendered", quote=hint))
            else:
                out.append(_R("closure_reachability", "CHK-PRUNE-REACH", "Unreachable prune presents the hybrid hint",
                              "MED", "FAIL",
                              "lever=prune & !reaches_budget ⇒ present prune-then-standing-justify",
                              "lever=prune, reaches_budget=False, but no prune-then-justify hint in the report",
                              "a prune that cannot reach budget is presented as a clean achievable prune "
                              "with no hybrid/justify routing",
                              "remediation hint", "D5", basis="rendered"))
        elif reaches is True:
            out.append(_R("closure_reachability", "CHK-PRUNE-REACH", "PRUNE lever reaches budget",
                          "MED", "PASS",
                          "lever=prune & reaches_budget ⇒ the prune is genuinely achievable",
                          "reaches_budget=True", "the projected lean re-index lands within budget",
                          "remediation", "D5"))
        else:
            out.append(_R("closure_reachability", "CHK-PRUNE-REACH", "PRUNE lever reachability",
                          "MED", "SKIP", "reaches_budget present in the record",
                          f"reaches_budget={reaches!r}", "the record omits reaches_budget", "remediation", "D5"))
    else:
        out.append(_R("closure_reachability", "CHK-PRUNE-REACH", "PRUNE lever reachability",
                      "MED", "SKIP", "an active prune-lever gate",
                      f"required={rem.get('required')}, lever={rem.get('lever')}",
                      "no active prune gate this run", "remediation", "D5"))

    # ── D10: dangling wikilinks — resolve against the FULL valid-target set (facts + archive-index
    #    docs like [[SHIPPED]]/[[MEMORY]]), mirroring the skill's valid_link_targets. Resolving against
    #    archive-EXCLUDED fact_stems alone RE-FIRED the v0.1.23 D10 fix: it false-flagged [[SHIPPED]]
    #    as dangling though SHIPPED.md is a valid target the skill resolves (beta-tester self-bug,
    #    caught 2026-06-21 on Doc_Flo: 7 flagged → 6 once archive docs are honored). ──
    if ctx.store_present:
        resolve = getattr(ctx.ms, "resolve_wikilink", None)
        vlt = getattr(ctx.ms, "valid_link_targets", None)
        valid_targets = set(vlt(ctx.store)) if vlt is not None else {p.stem for p in ctx.store.glob("*.md")}
        dangling: list[str] = []
        suggestions: dict[str, str] = {}
        for raw in sorted(ctx.raw_wikilinks):
            if raw in valid_targets:
                tgt: str | None = raw   # direct hit — incl. archive-index docs ([[SHIPPED]]/[[MEMORY]] are real, D10)
            elif resolve is not None:
                tgt = resolve(raw, valid_targets)
            else:
                nt = _local_norm(raw)
                hits = [s for s in valid_targets if _local_norm(s) == nt]
                tgt = hits[0] if len(hits) == 1 else None
            if tgt is None:
                dangling.append(raw)
                # Suggest a target ONLY where resolve_wikilink itself would accept it against a
                # singleton candidate set (exact / normalized / distinctive date-stripped base) —
                # never a substring guess. This is deliberately conservative: the skill's own
                # resolver refuses ambiguous slug-drift, so the oracle must not over-claim a fix it
                # wouldn't make (the prototype's startswith/substring matcher did).
                if resolve is not None:
                    for cand in sorted(valid_targets):
                        if resolve(raw, {cand}) == cand:
                            suggestions[raw] = cand
                            break
        if dangling:
            shown = "; ".join(f"[[{d}]]" + (f"→{suggestions[d]}" if d in suggestions else "") for d in dangling[:8])
            out.append(_R("closure_reachability", "CHK-DANGLING", "Dangling wikilinks (assisted-fix where resolvable)",
                          "LOW", "WARN",
                          "0 dangling [[wikilinks]] (or all slug-resolvable)",
                          f"{len(dangling)} dangling; {len(suggestions)} have a resolve_wikilink-acceptable target",
                          shown + (f" (+{len(dangling) - 8} more)" if len(dangling) > 8 else ""),
                          "wikilink graph", "D10"))
        else:
            out.append(_R("closure_reachability", "CHK-DANGLING", "No dangling wikilinks",
                          "LOW", "PASS", "0 dangling [[wikilinks]]", "0 dangling",
                          "every [[wikilink]] resolves to an existing fact via the skill's resolve_wikilink",
                          "wikilink graph", "D10"))
    return out


# ─────────────────────────────── FAMILY 6: calibration (advisory) ───────────────────────────────


@family
def calibration(ctx: Ctx) -> list[Result]:
    """Sanity of budgets / triage targeting for THIS store — alarm-fatigue + zero-relief triage.
    ⊇ D6, D7, D8, D11. These complete the detection floor but are ADVISORY (WARN), per the SPEC's
    'secondary/quarantined' posture: a calibration opinion is weaker than a structural contradiction.
    """
    out: list[Result] = []
    rem = ctx.status.get("remediation") or {}
    if not ctx.status:
        return out

    # D7: a durable over-budget gate that can't reach budget should have / recommend a standing-justify
    # (the skill now persists one via .consolidation-state.json standing_justify). If reaches_budget is
    # False and the gate is NOT standing-justified, flag that a standing-justify is the durable resolution.
    if rem.get("required") and rem.get("reaches_budget") is False and not rem.get("standing_justified"):
        sj_hint = _grep_quote(ctx.status_report_text, r"standing-justif")
        out.append(_R("calibration", "CHK-STANDING-JUSTIFY", "Unreachable gate offers a durable standing-justify",
                      "LOW", "PASS" if sj_hint else "WARN",
                      "an unreachable-by-prune gate routes to a standing-justify (durable, not re-litigated)",
                      f"reaches_budget=False, standing_justified={rem.get('standing_justified')}, "
                      f"standing-justify hint {'present' if sj_hint else 'absent'} in the report",
                      (sj_hint or "no standing-justify resolution surfaced for a permanently-over-budget gate "
                       "(would re-litigate every pass — alarm fatigue)"),
                      "remediation", "D7", basis="rendered" if sj_hint else "structural", quote=sj_hint or ""))

    # D6: a permanently-over-budget gate is mis-calibrated alarm fatigue ONLY if it has NO achievable
    # resolution AT ALL. The verdict must match this check's own `expected` ("resolvable via prune OR
    # standing-justify") — the prior code WARNed on prune-unreachability alone, contradicting both that
    # clause and CHK-STANDING-JUSTIFY above (the dream-beta-test dogfood, 2026-06-21, reduced it to this
    # self-contradiction). v0.1.21+ resolves the gate via a durable standing-justify, so PASS when that
    # resolution is available; WARN only when neither prune NOR standing-justify resolves it (a genuine
    # dead-end / regression).
    if rem.get("required") and rem.get("reaches_budget") is False:
        proj = rem.get("projected_index")
        budget = _json_path(ctx.status, "budget.index.budget_tokens")
        sj_resolves = bool(rem.get("standing_justified")) or bool(
            _grep_quote(ctx.status_report_text, r"standing-justif"))
        out.append(_R("calibration", "CHK-BUDGET-CALIBRATION", "Over-budget gate has an achievable resolution",
                      "LOW", "PASS" if sj_resolves else "WARN",
                      "the over-budget gate is resolvable (prune reaches budget, or density is standing-justified)",
                      (f"prune can't reach (max-prune {proj} > budget {budget}) but standing-justify resolves the "
                       "gate — a durable, non-re-litigated resolution exists" if sj_resolves else
                       f"max-prune projection {proj} > budget {budget} AND no standing-justify — no achievable "
                       "resolution (mis-calibrated ceiling → alarm fatigue every pass)"),
                      "the fixed index budget can't be reached by prune on this mature store; v0.1.21+ resolves via "
                      "standing-justify (see CHK-STANDING-JUSTIFY) so the gate is not a dead-end — only a raw budget "
                      "number that earned density outgrows",
                      "budget.index", "D6", basis="rendered" if sj_resolves else "structural"))
    return out


@family
def remediation_render_coherence(ctx: Ctx) -> list[Result]:
    """The remediation block stays coherent with the cycle record. Guards two renderer fixes + the
    seed→renderer SAFETY contract:
      (1) v0.1.36 — the over-budget block renders only when remediation.required is truthy, NOT on mere
          presence; a record carrying {required:false} (the schema default) must render NO block.
      (2) v0.1.35 — a rebuild-lean-resolved gate (pruned=0, achieved_index<=budget) reads 'resolved',
          not 'gate fired but not acted on'.
      (3) seed contract (HIGH) — a REAL over-budget, non-justified store MUST seed required=True, else
          the v0.1.36 renderer (gating on `required`) would SILENTLY drop the over-budget safety gate.
    The render checks are field-aware (basis=rendered): they subprocess the skill's OWN render_dashboard
    from cwd=target repo, per the harness's clean-subprocess discipline."""
    import json as _json, os as _os, subprocess as _sp, sys as _sys, tempfile as _tf
    out: list[Result] = []
    rd = Path(ctx.skill) / "render_dashboard.py"

    def _probe(rem: dict[str, Any], after: int, over: bool) -> str | None:
        rec = {"project": "p", "session": "s", "scope": {}, "entries": [],
               "budget": {"index": {"after_tokens": after, "budget_tokens": 1200, "over": over}},
               "remediation": rem, "marker": {"commit": "probe", "timestamp": "2026-01-01T00:00:00Z"}}
        fd, p = _tf.mkstemp(suffix=".json")
        try:
            _os.write(fd, _json.dumps(rec).encode()); _os.close(fd)
            r = _sp.run([_sys.executable, str(rd), p, "--no-color"],
                        capture_output=True, text=True, timeout=30, cwd=str(ctx.repo))
            return r.stdout if r.returncode == 0 else None
        except Exception:  # noqa: BLE001 — a render failure SKIPs, never crashes the oracle
            return None
        finally:
            try:
                _os.unlink(p)
            except OSError:
                pass

    if rd.exists():
        # (1) v0.1.36 — required=false must render NO over-budget block
        o = _probe({"required": False}, 900, False)
        if o is None:
            out.append(_R("remediation_render_coherence", "CHK-REM-REQUIRED", "required=false → no over-budget block",
                          "MED", "SKIP", "no REMEDIATION block for required=false", "render unavailable",
                          "", "render_dashboard.py", "v0.1.36", "rendered"))
        else:
            spurious = "REMEDIATION" in o
            out.append(_R("remediation_render_coherence", "CHK-REM-REQUIRED", "required=false → no over-budget block",
                          "MED", "FAIL" if spurious else "PASS",
                          "no REMEDIATION block for a record with remediation.required=false",
                          "spurious over-budget block rendered" if spurious else "no block (correct)",
                          "the renderer must gate on `required`, not mere presence (schema default is required:false present)",
                          "render_dashboard.py", "v0.1.36", "rendered",
                          (_grep_quote(o, "REMEDIATION") or "") if spurious else ""))
        # (2) v0.1.35 — a rebuild-lean-resolved gate reads 'resolved', not 'not acted on'
        o2 = _probe({"required": True, "lever": "prune", "pruned": 0, "achieved_index": 900,
                     "candidates_surfaced": 1, "projected_index": 480, "reaches_budget": True}, 900, False)
        if o2 is None:
            out.append(_R("remediation_render_coherence", "CHK-REM-RESOLVED", "rebuild-lean-resolved → 'resolved'",
                          "MED", "SKIP", "resolved-by-rebuild-lean, not 'not acted on'", "render unavailable",
                          "", "render_dashboard.py", "v0.1.35", "rendered"))
        else:
            mislabeled = "not acted on" in o2
            out.append(_R("remediation_render_coherence", "CHK-REM-RESOLVED",
                          "rebuild-lean-resolved gate reads 'resolved', not 'not acted on'", "MED",
                          "FAIL" if mislabeled else "PASS",
                          "a gate resolved via rebuild-lean (pruned=0, achieved<=budget) reads as resolved",
                          "mislabeled 'gate fired but not acted on'" if mislabeled else "resolved (correct)",
                          "acted-on must include rebuild-lean resolution, not eviction only",
                          "render_dashboard.py", "v0.1.35", "rendered",
                          (_grep_quote(o2, "not acted on") or "") if mislabeled else ""))

    # (3) seed→renderer SAFETY contract — an over-budget, non-justified store MUST seed required=True
    rem = ctx.status.get("remediation") or {}
    if rem and not rem.get("standing_justified"):
        ok = rem.get("required") is True
        out.append(_R("remediation_render_coherence", "CHK-REM-SEED-CONTRACT",
                      "over-budget seed sets required=True (gate-firing contract)", "HIGH",
                      "PASS" if ok else "FAIL",
                      "an over-budget, non-justified store seeds remediation.required=True",
                      "required=True (the v0.1.36 renderer fires the gate)" if ok
                      else f"required={rem.get('required')!r} — the v0.1.36 renderer would DROP the gate",
                      "memory_status seed → render_dashboard gate-firing contract",
                      "memory_status.py", "v0.1.36", "structural"))
    return out


@family
def maintenance_pivot_coherence(ctx: Ctx) -> list[Result]:
    """v0.1.37: the no-op SELF-HEAL pivot CUE is surfaced. A store with maintenance work (dangling links
    / over-budget-not-justified) MUST render the Phase-0 MAINTENANCE cue, so a magnitude-0 dream is CUED
    to pivot (Phase 1 --pull + Phase 5 health) instead of exiting with "nothing to do". Deterministic:
    checks the cue is PRESENT in the skill's ALREADY-CAPTURED Phase-0 report (`ctx.status_report_text`, the
    same surface every other rendered-basis family reuses) — it CANNOT observe the model's pivot DECISION
    (m5), only that the signal foundation exists. Version-aware: a pre-v0.1.37 skill (no `maintenance`
    block in --json) is not-applicable → SKIP-by-empty."""
    out: list[Result] = []
    maint = (ctx.status.get("maintenance") if isinstance(ctx.status, dict) else None) or {}
    if not maint or not maint.get("work"):
        return out                              # pre-v0.1.37 skill, or no maintenance work → not applicable
    render = ctx.status_report_text or ""
    if not render:
        return out                              # no captured Phase-0 render (harness issue) → SKIP, not a false FAIL
    cued = "MAINTENANCE" in render
    out.append(_R("maintenance_pivot_coherence", "CHK-MAINT-CUE",
                  "maintenance work surfaces the Phase-0 pivot cue", "MED", "PASS" if cued else "FAIL",
                  "a store with maintenance.work renders the Phase-0 MAINTENANCE cue (the pivot signal)",
                  f"maintenance.work=true (dangling={maint.get('dangling', 0)}); Phase-0 cue {'present' if cued else 'ABSENT'}",
                  "memory_status Phase-0 render", "memory_status.py", "-", "rendered",
                  (_grep_quote(render, "MAINTENANCE") or "") if cued else ""))
    return out


@family
def dream_arc_capture(ctx: Ctx) -> list[Result]:
    """v0.1.54: the dream-arc CAPTURE exists on the latest persisted dream. The skill's dream-arc
    contract mirrors the conversational dream blocks (sleep · beats · wake) into the cycle record's
    `dream` block; every persisted record IS a proceeding pass by construction (a true no-op stops at
    Phase 0 and never persists), so a latest record missing the capture is a fully-skipped arc.
    ADVISORY (LOW / WARN, never FAIL): style is not procedure, and a record written by ≤ v0.1.53
    legitimately lacks the key (records carry no version stamp) — check the record's recency before
    promoting. Necessary-not-sufficient: presence cannot prove the user SAW the narration (that needs
    the transcript — a judgment-lens check); this family catches only the fully-skipped arc.
    Version-aware: a pre-v0.1.54 skill under test → SKIP-by-empty; no log yet → SKIP-by-empty."""
    out: list[Result] = []
    ver = tuple(int(x) for x in re.findall(r"\d+", ctx.skill_version or "")[:3])
    if ver and ver < (0, 1, 54):
        return out                              # skill under test predates the dream-arc capture → not applicable
    if not ctx.log_records:
        return out                              # no persisted dreams yet (pre-first-dream store) → not applicable
    latest = ctx.log_records[-1]
    _d = latest.get("dream")
    dream: dict[str, Any] = _d if isinstance(_d, dict) else {}
    _b = dream.get("beats")
    beats: list[Any] = _b if isinstance(_b, list) else []
    have_sleep = bool(str(dream.get("sleep", "")).strip())
    have_wake = bool(str(dream.get("wake", "")).strip())
    complete = have_sleep and have_wake and len(beats) > 0
    _m = latest.get("marker")
    m: dict[str, Any] = _m if isinstance(_m, dict) else {}
    out.append(_R("dream_arc_capture", "CHK-DREAM-ARC",
                  "latest persisted dream captured its dream arc (sleep · beats · wake)", "LOW",
                  "PASS" if complete else "WARN",
                  "a v0.1.54+ dream mirrors its conversational dream blocks into the record's `dream` block",
                  (f"sleep={'present' if have_sleep else 'MISSING'} · beats={len(beats)} · "
                   f"wake={'present' if have_wake else 'MISSING'}"
                   + ("" if complete else
                      " — expected on pre-v0.1.54 records; a defect on any dream run with v0.1.54+ "
                        "(check the record's recency before promoting)")),
                  "the persisted .consolidation-log.jsonl (latest record)",
                  f"log[-1] @ {m.get('timestamp') or 'unstamped'}", "v0.1.54", "structural"))
    return out


# ─────────────────────────────── run + report ───────────────────────────────


def run(ctx: Ctx) -> list[Result]:
    out: list[Result] = []
    for fn in FAMILIES:
        try:
            out.extend(fn(ctx))
        except Exception as e:  # noqa: BLE001 — an oracle bug must SKIP that family, not crash the run
            out.append(_R(fn.__name__, f"CHK-{fn.__name__.upper()}", fn.__doc__.splitlines()[0] if fn.__doc__ else fn.__name__,
                          "LOW", "SKIP", "the family runs", f"raised {type(e).__name__}: {e}",
                          "oracle-internal error in this family", "-", "-"))
    return out


def _summary(results: list[Result]) -> dict[str, int]:
    return {
        "total": len(results),
        "fail": sum(r.status == "FAIL" for r in results),
        "warn": sum(r.status == "WARN" for r in results),
        "pass": sum(r.status == "PASS" for r in results),
        "skip": sum(r.status == "SKIP" for r in results),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Dream beta-harness invariant oracle for consolidate-memory.")
    ap.add_argument("--repo", default=os.getcwd(), help="repo whose dream is tested (default: cwd)")
    ap.add_argument("--store", default=None, help="memory store dir (default: ~/.claude/projects/<slug>/memory)")
    ap.add_argument("--skill", default=None, help="consolidate-memory scripts dir (default: discovered, version-max)")
    ap.add_argument("--json", action="store_true", help="emit structured JSON (default: human summary)")
    a = ap.parse_args()

    repo = Path(a.repo).expanduser().resolve()
    skill = discover_skill(a.skill)
    if skill is None:
        # The ONE hard error: we cannot drive the skill at all. (An absent store is NOT this — see below.)
        print("ERROR: could not locate consolidate-memory scripts "
              "(set $CONSOLIDATE_MEMORY_SCRIPTS, pass --skill, or install the plugin)", file=sys.stderr)
        return 2

    skill_version = _skill_version(skill)
    ms = import_skill_module(skill)
    store = Path(a.store).expanduser().resolve() if a.store else default_store(repo)
    ctx = gather(repo, store, skill, ms, skill_version)

    results = run(ctx)
    families_ran = sorted({r.family for r in results if r.status != "SKIP"})
    families_skipped = sorted({r.family for r in results} - set(families_ran))
    summary = _summary(results)

    payload: dict[str, Any] = {
        "repo": str(repo),
        "store": str(store),
        "store_present": ctx.store_present,
        "skill": str(skill),
        "skill_version": skill_version,
        "summary": summary,
        "families_ran": families_ran,
        "families_skipped": families_skipped,
        "notes": ctx.notes,
        "results": [asdict(r) for r in results],
    }

    if not ctx.store_present:
        payload["store_absent"] = True
        payload["notes"] = ctx.notes + [
            f"store {store} does not exist — this is a never-dreamed repo (a valid CLEAN outcome, not a defect); "
            "store-dependent families SKIP"
        ]

    if a.json:
        print(json.dumps(payload, indent=2))
        return 1 if summary["fail"] else 0

    icon = {"PASS": "[PASS]", "FAIL": "[FAIL]", "WARN": "[WARN]", "SKIP": "[skip]"}
    print(f"\n  DREAM BETA ORACLE · {repo.name}  (consolidate-memory v{skill_version})")
    print(f"  store: {store}" + ("" if ctx.store_present else "   [ABSENT — never-dreamed repo, clean SKIP]"))
    print(f"  skill: {skill}")
    print(f"  {summary['fail']} FAIL · {summary['warn']} WARN · {summary['pass']} PASS · {summary['skip']} SKIP "
          f"({len(families_ran)} families ran, {len(families_skipped)} skipped)\n")
    order = {"FAIL": 0, "WARN": 1, "SKIP": 2, "PASS": 3}
    sev_order = {"HIGH": 0, "MED": 1, "LOW": 2}
    for r in sorted(results, key=lambda r: (order[r.status], sev_order.get(r.severity, 9), r.family)):
        print(f"  {icon[r.status]} [{r.severity:4}] {r.id:22} {r.defect_ref:3} {r.title}")
        if r.status in ("FAIL", "WARN"):
            print(f"          family:   {r.family}  ·  site: {r.site}  ·  basis: {r.basis}")
            print(f"          expected: {r.expected}")
            print(f"          actual:   {r.actual}")
            print(f"          evidence: {r.evidence}")
            if r.quote:
                print(f"          quote:    {r.quote!r}")
    if ctx.notes:
        print("\n  notes:")
        for n in ctx.notes:
            print(f"    · {n}")
    print()
    return 1 if summary["fail"] else 0


if __name__ == "__main__":
    sys.exit(main())
