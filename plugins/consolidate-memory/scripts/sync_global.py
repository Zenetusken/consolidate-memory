#!/usr/bin/env python3
"""Cross-project memory: replicate relevant GLOBAL facts into a project's store.

Claude Code recall is slug-scoped (a project only auto-recalls its OWN
~/.claude/projects/<slug>/memory/). So cross-project facts can't just live in a
global store and be expected to surface elsewhere — they must be REPLICATED into
each project's store. This is the engine for that:

  --list PROJECT_DIR   show which global facts are relevant + present/missing (read-only)
  --pull PROJECT_DIR   copy missing relevant global facts into the project's store. AUTO-HOLDS (M1) any
                       new-global pull that would push the always-loaded index past the HARD CEILING
                       (INDEX_CEILING_TOKENS ≈3840 est tok — v0.1.66 Phase B; the over-TARGET amber band
                       no longer holds, so verified knowledge flows until the real harm boundary; the
                       target gate/standing-justify are a separate, untouched signal). STALE mirrors
                       always refresh. Reports `held N` — shrink below the ceiling to receive. Every
                       written pointer is fat-hook-LINTED (> HOOK_TOKEN_WARN est tok → stderr warning
                       naming the canonical description; never truncated). (additive; marks copies with
                       `global_ref:` so they re-sync)
  --pull --allow-net-grow  override the guard — pull even past the ceiling
  --pull --evict=FACT  EVICT-TO-RECEIVE (v0.1.41; accounting-truth rebuild v0.1.73 — see
                       docs/evict-accounting-truth.spec.md): free one low-value project-AUTHORED pointer (FACT)
                       so a HELD global can land — net-neutral, so M1's budget stays enforced. The release valve
                       for a chronically-full store. `freed` is MEASURED from the store's real MEMORY.md line
                       (never derived from frontmatter), and the swap gate is an A/B replay of the actual pull
                       plan. Refuses: a managed MIRROR (self-defeating — the live canonical re-pulls the same
                       pass; the lever for mirrors is the GLOBAL store), an orphaning evict (inbound [[links]]),
                       an unindexed evict (no real index line — frees nothing), and a GAINLESS one (the replayed
                       plan lands no additional held global). A plain `--pull` with anything held prints the
                       authored candidates.
  --promote PROJECT_DIR LOCAL_FACT [CANON_NAME] [--prefer-canonical] [--repoint]
                       hand a project-authored local fact UP to the canonical global store and
                       convert the origin's copy into a managed mirror (the local→canonical
                       promotion hand-off; never leaves a dup/orphan — see promote()). A RECONCILE
                       onto an existing canonical REFUSES if the local's body differs (M2 — would
                       silently discard it); --prefer-canonical keeps the canonical, drops the local
                       body (the dedup intent). stack-general stacks: must be DETECTABLE (M4).
  --harvest PROJECT_DIR  (v0.1.79) capture EVERY node's organic fact-read windows from its transcripts into
                       the plugin-data ledger (fleet-usage.jsonl, 0o600) BEFORE rotation destroys them —
                       never the canonical Markdown plane. Usage capture was dream-gated per node (measured:
                       1/3 nodes reporting). Watermarked + idempotent; reads-only (no miss classification);
                       --utility surfaces the harvested evidence, source-labeled, for nodes with no own-log usage.
  --staleness PROJECT_DIR  (v0.1.80) READ-ONLY absorption-lag sweep over ALL project stores (beacon
                       Stage A): per node — last-dream marker age, MISSING relevant globals (never
                       absorbed), content-stale mirrors, usage/harvest coverage. Scope basis honest per
                       node (full relevance only for the trigger; others user-global-only, labeled).
  --workflows PROJECT_DIR  (v0.1.83, W-B) READ-ONLY fleet workflow evidence: join every node's LATEST
                       W-A distill rows (top/top_chains/used, persisted since v0.1.82) by exact template
                       string — breadth (>=2 nodes) is the workflow analog of the cascade's G2.3 witness;
                       + head-signature near-join hints, the Skill-adoption view, the cross-node verdict
                       lineage (fleet-wide decline-dedup), and the user-level artifact inventory. Evidence
                       for the Phase-5 distill gate; judgment stays with the model (report-then-apply).
  --utility PROJECT_DIR  (v0.1.67, Phase C) READ-ONLY fleet usage evidence: per-canonical organic reads
                       aggregated across every node's cycle log (mirror-attributed; same-stem locals
                       report as shadow, never attributed) + fleet_tax = pointer×holders against the
                       warn-only GLOBAL_FLEET_TAX_ADVISORY. The gc lever's evidence table — judgment
                       stays content-gated, never auto-gc. --json for machine capture.

Relevance: `scope: user-global` facts apply to every project; `scope: stack-general`
facts apply only if their `stacks:` intersect the project's detected stacks. Project
stacks are inferred from REAL USAGE — declared dependencies, actual imports, and marker
dirs/files (NOT doc-mentions; v0.1.16).

The consolidate-memory skill calls --pull in Phase 1 (bring global facts down) and
writes new global-scope facts up to the global store in Phase 4.
"""

from __future__ import annotations

import uuid
import ast
import hashlib
import math
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# est_tokens lives in memory_status (the measurement script); reuse it rather than
# re-deriving the heuristic. The sibling resolves because a script's own directory is
# on sys.path[0] at runtime; both live in the plugin's scripts/ dir.
import _ui  # sibling script: the shared visual vocabulary (color / rule / kv / glyphs)
from memory_status import (_is_archive_index_text, _is_mirror, _parse_ts, _sane, est_tokens, slug_for,
                           _frontmatter, _valid_uuid,
                           INDEX_TOKEN_BUDGET, INDEX_CEILING_TOKENS, HOOK_TOKEN_WARN,
                           _REGISTRAR_BLOCKED_CAP, _is_distinctive_template,
                           _NETWORK_FACT_CAP, _NETWORK_HOLDER_CAP, _NETWORK_INCIDENCE_BYTES,
                           _network_incidence_bytes,
                           _is_fleet_proposal_row,
                           distill_history, extract_wikilinks, resolve_wikilink, usage_history,
                           _write_private)

# Tests may assign `sync_global.GLOBAL = <fixture>` (often a dir NOT named `memory`).
# Production always uses config_root()/memory so CLAUDE_CONFIG_DIR cannot leak a
# personal canonical into a work profile (ADR 002).
GLOBAL = Path.home() / ".claude" / "memory"
_IMPORT_HOME = Path.home()


def global_store() -> Path:
    """Canonical Markdown dir: config_root/memory (honours CLAUDE_CONFIG_DIR / HOME).

    Tests may assign `sync_global.GLOBAL = <fixture>`. Honor a fixture that is NOT the
    process-home default (`Path.home()/.claude/memory`) so a patched dir named `memory`
    still wins, and a CLAUDE_CONFIG_DIR profile cannot leak into the personal store.
    """
    from store_context import config_root
    live = config_root() / "memory"
    g = globals().get("GLOBAL")
    if isinstance(g, Path):
        home_canon = Path.home() / ".claude" / "memory"
        try:
            if g.resolve() != home_canon.resolve():
                return g
        except OSError:
            if g != home_canon:
                return g
    return live


def _projects_root() -> Path:
    """Claude projects directory via StoreContext config_root (honours CLAUDE_CONFIG_DIR)."""
    from store_context import config_root
    return config_root() / "projects"


def _path_key(p: Path) -> str:
    try:
        return str(p.resolve())
    except OSError:
        return str(p)


def _registry_project_rows() -> list:
    """Read-only: registered projects from the control plane, if the DB exists.

    Does not CREATE the DB (fleet readers must not mint control.sqlite).
    """
    try:
        from control_plane import connect_if_exists, db_path, iter_registered_projects
        conn = connect_if_exists(db_path())
        if conn is None:
            return []
        try:
            return iter_registered_projects(conn)
        finally:
            conn.close()
    except Exception:
        return []


_FIXTURE_MARKER = ".cm-fixture"
# R2 (v0.4.2): PINNED known-stale slug patterns — machine-independent substrings (never paths,
# never usernames): the tmpdir-derived slug family (`-tmp-…`, every bench/hermetic fixture) and
# the dream-beta-tester fixture repo paths (`.claude/dream-beta-tester/fixtures/gate-repo`
# and `.dream-beta-test/gate-repo`, wherever the home dir lives). The PRIMARY mechanism is the
# .cm-fixture marker (ancestor walk); this list covers pre-existing unmarked dirs.
# Review fix: slug_for (M3+) replaces dots with dashes, so the CURRENT-shape legacy
# fixture dirs are dash-slugs — the dot-bearing patterns only match obsolete pre-M3
# dirs. Both forms are listed.
_FIXTURE_SLUG_PATTERNS = ("-tmp-",
                          ".claude-dream-beta-tester-fixtures-gate-repo",
                          ".dream-beta-test-gate-repo",
                          "-dream-beta-tester-fixtures-gate-repo",
                          "-dream-beta-test-gate-repo")


def _is_fixture_store(p: Path) -> bool:
    """R2 (v0.4.2): a synthetic fixture store pollutes fleet analytics (holder/staleness/
    network counts) — detect and skip. Primary: a `.cm-fixture` marker in ANY ancestor
    (fixture generators write it at the fake-home root or the slug dir). Fallback: the
    pinned slug patterns. Read-only; an OSError anywhere degrades to the pattern check."""
    try:
        cur: "Path | None" = p
        hops = 0
        while cur is not None and hops < 6:
            if (cur / _FIXTURE_MARKER).is_file():
                return True
            if cur.parent == cur:
                break
            cur = cur.parent
            hops += 1
    except OSError:
        pass
    name = p.parent.name   # the slug dir
    return any(_pat in name for _pat in _FIXTURE_SLUG_PATTERNS)


def iter_native_stores(*, allow_fixture_paths: bool = False) -> "list[Path]":
    """Default `projects/*/memory` UNION registry `native_memory_dir`.

    Custom autoMemoryDirectory stores are invisible to a projects-tree walk;
    they appear here once a project has transacted (upsert_project persisted
    native_memory_dir + session_dir).

    R2 (v0.4.2): fixture stores are EXCLUDED (marker or pinned slug patterns) —
    a dim stderr line keeps the exclusion visible in the consumer's output.
    `allow_fixture_paths=True` lifts the exclusion — the HERMETIC smoke
    fixtures only (every /tmp-derived slug matches the -tmp- pattern, so a
    fleet fixture would otherwise enumerate zero sibling stores; MED-2)."""
    _skip_fixture = not allow_fixture_paths
    seen: set = set()
    out: list = []
    skipped = 0

    def add(p: Path) -> None:
        nonlocal skipped
        if not p.is_dir():
            return
        key = _path_key(p)
        if key in seen:
            return
        seen.add(key)
        if _skip_fixture and _is_fixture_store(p):
            skipped += 1
            return
        out.append(p)

    base = _projects_root()
    if base.is_dir():
        try:
            kids = sorted(base.iterdir())
        except OSError:
            kids = []
        for proj in kids:
            add(proj / "memory")
    for rec in _registry_project_rows():
        raw = rec.get("native_memory_dir") or ""
        if raw:
            add(Path(raw))
    if skipped:
        print(_ui.c(f"  ⏭ skipped {skipped} fixture store(s) (.cm-fixture marker / "
                    f"known fixture slug) — excluded from fleet analytics", "dim"),
              file=sys.stderr)
    return out


def session_dir_for_store(store: Path) -> Path:
    """Transcript dir for a native store: default layout parent, else registry session_dir."""
    try:
        p = store.resolve()
    except OSError:
        p = store
    if p.name == "memory" and p.parent.parent.name == "projects":
        return p.parent
    want = _path_key(p)
    for rec in _registry_project_rows():
        raw = rec.get("native_memory_dir") or ""
        if not raw:
            continue
        if _path_key(Path(raw)) == want:
            sd = rec.get("session_dir") or ""
            if sd:
                return Path(sd)
            break
    return p.parent

# v0.1.67 (Phase C): the global store's fleet-tax ADVISORY — a warn-only ceiling on Σ(pointer_tok ×
# holders) over all canonicals: the per-session always-loaded cost the global store imposes across the
# fleet (each holder node pays each mirror's pointer line every session). Derivation (the
# HOOK_TOKEN_WARN / INDEX_TOKEN_BUDGET measured-derivation precedent): MEASURED 2026-07-05 — 26
# canonicals, Σ fleet_tax = 3283 est tok (0 unheld) — + ~50% headroom, rounded. UPPER-BOUND basis:
# `holders` is provenance, which accrues dead edges (--gc reports them, never auto-prunes), so the
# figure over-counts toward safety. NEVER a block or a hold — a hard fleet gate would be a new
# load-bearing mechanism needing its own oracle-grade gate review (spec §Deferred beyond Phase C).
GLOBAL_FLEET_TAX_ADVISORY = 5000


def _safe_read_text(path: Path) -> "str | None":
    """The store-scan convention, factored ONCE (v0.1.69 Gate-2a review: the pattern had been
    hand-copied at three call sites and a fourth — `_orphans` — was left unguarded because
    copy-paste doesn't propagate a fix). A concurrent gc/chmod/delete between `glob` and `read`
    must not abort the whole scan; every fact-body-in-a-loop reader shares this ONE fallible read."""
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def _nonglobal_wikilinks(text: str, global_dir: Path, exclude: str = "") -> list[str]:
    """v0.1.25: the `[[wikilink]]` targets in `text` that are NOT global canonicals — so they DANGLE in every
    mirror of a promoted fact (a global fact's links travel with it into every project). Excludes code-span
    dotted refs (e.g. `[[tool.mypy.overrides]]`, a TOML table) + `exclude` (a self-reference). A global fact
    should link only to OTHER global facts; a project-local link dead-ends in every mirror. Sorted + de-duped.
    Surfaced by `promote` (found via a job-applicator dream — 3 such links dangled fleet-wide)."""
    return sorted({w for w in re.findall(r"\[\[([^\]]+)\]\]", text)
                   if "." not in w and w != exclude and not (global_dir / f"{w}.md").exists()})


# Real-usage stack detection (v0.1.16): a stack counts ONLY on a REAL signal — a DECLARED dependency
# (pyproject), an ACTUAL import (*.py), or a real marker dir/file — NEVER a doc-mention. The old
# prose-keyword model false-matched a stdlib plugin's README ("rag", "scraper") into rag/playwright,
# collapsing the stack-general tier toward universal. Two EXACT-token sets per stack: DISTRIBUTION
# names (matched against parsed pyproject dep names) + MODULE names (matched against import statements).
# Exact membership, never substring — so `sentence-transformers` (rag) is never read as `transformers`.
_STACK_DEPS = {   # PEP 503-normalized DISTRIBUTION names → stack
    "mypy": {"mypy"},
    "rag": {"lancedb", "faiss", "faiss-cpu", "faiss-gpu", "sentence-transformers", "chromadb", "rerankers"},
    "gpu": {"torch", "torchvision", "torchaudio", "open-clip-torch", "vllm"},
    "playwright": {"playwright", "playwright-stealth"},
    "pdf": {"pypdfium2", "pymupdf", "pdfplumber", "pdf2image", "pdfminer-six"},  # v0.1.17: PDF-lib gotchas (pdfium thread-unsafety) bind cross-project
}
_STACK_IMPORTS = {   # top-level MODULE names (as imported) → stack
    "rag": {"lancedb", "faiss", "sentence_transformers", "chromadb"},
    "gpu": {"torch", "torchvision", "open_clip", "vllm"},
    "playwright": {"playwright"},
    "pdf": {"pypdfium2", "fitz", "pdfplumber", "pdf2image", "pdfminer"},  # pymupdf imports as `fitz`; pdfminer.six as `pdfminer`
}
# M4 (v0.1.39): the CLOSED set of stacks detect_stacks can ever emit — the maps' KEYS plus the three special
# markers (python always; mypy via [tool.mypy]; claude-code via .claude/). promote() validates a stack-general
# fact's `stacks:` against THIS, so a tag detect_stacks can never produce (a typo, or a real-but-undetectable
# stack like 'release'/'ci-cd') is refused, not written as a canonical that matches NO project (fleet-dead).
_DETECTABLE_STACKS = set(_STACK_DEPS) | set(_STACK_IMPORTS) | {"python", "mypy", "claude-code"}
_PYPROJECT_CAP = 65536   # bytes read from pyproject (config is small; bound the read)
_PY_SCAN_CAP = 400       # max *.py files scanned for imports (bound cost on large repos)


_SAFE_NAME = r"[A-Za-z0-9._-]+"  # the documented kebab/snake charset for fact + project names
# Stems that name a store's always-loaded INDEX, never a fact. `_safe_stem` accepts them (they are
# valid filenames), so promote() must reject them explicitly — writing a fact to `<store>/MEMORY.md`
# would clobber the index every session loads. (`.`/`..` are neutralized by the `.md` suffix, which
# keeps the write inside the store; `MEMORY` is the one stem that collides with a real, load-bearing file.)
_RESERVED_STEMS = {"MEMORY"}


def _is_reserved_stem(name: str) -> bool:
    """True iff `name` collides with a reserved index name — case-INSENSITIVE. v0.1.70 Gate-2a:
    an exact-string `name in _RESERVED_STEMS` check lets a case-variant ('memory', 'Memory') sail
    straight through on a case-insensitive filesystem — macOS (APFS/HFS+ default) primarily; the
    README's Windows path is WSL, whose Linux-side filesystem is case-sensitive by default, so this
    guards against an odd case-insensitive mount there rather than the common case — where it
    resolves to the SAME file as the real, load-bearing MEMORY.md — the exact self-clobber
    class this guard exists to close, reached via a one-character case change. Shared by promote()'s
    guard and run()'s --evict= guard so a future change to _RESERVED_STEMS (or this comparison)
    can't drift between the two call sites, as the two independent hand-written copies already had."""
    return name.upper() in {s.upper() for s in _RESERVED_STEMS}


def _safe_stem(stem: str) -> bool:
    """True iff a fact stem is safe to use as a filename AND to interpolate into the
    always-loaded index. Rejects markdown/link-injection payloads in a crafted name."""
    from identifiers import FACT_STEM_MAX_BYTES, FACT_STEM_MAX_CHARS
    if not re.fullmatch(_SAFE_NAME, stem or ""):
        return False
    return len(stem) <= FACT_STEM_MAX_CHARS and len(stem.encode("utf-8")) <= FACT_STEM_MAX_BYTES


def _sanitize_token(s: str) -> str:
    """Collapse anything outside the safe charset to '-'. For values written into the
    SHARED global store (e.g. a project basename in `projects:`); also neutralizes any
    regex backreference (`\\1`) before such a value reaches an re.sub replacement."""
    return re.sub(r"[^A-Za-z0-9._-]", "-", s or "")


def project_store(project_dir: Path) -> Path:
    """Native auto-memory dir via the authoritative StoreContext resolver (ADR 002)."""
    from store_context import resolve_store
    return resolve_store(project_dir).native_memory_dir


def _atomic_write_text(path: Path, text: str, encoding: str = "utf-8") -> None:
    """Overwrite `path` ATOMICALLY (v0.1.71, Track D-1) — write to a temp sibling then
    `os.replace()` (same directory, so the rename stays on one filesystem; atomic on
    POSIX and Windows since Python 3.3). A concurrent reader always sees either the
    fully-old or fully-new content, never a partial write. Use for GLOBAL-store
    overwrites specifically (the shared store multiple projects' dreams can write to
    around the same time) — NOT for a create-or-detect-collision write, which needs
    `os.link`'s exclusivity instead (see `_create_exclusive` / `promote()`). Like
    `_create_exclusive`, never leaks its temp sibling — a failed write/replace still
    propagates (no masking), but cleans up the partial temp first."""
    tmp = path.with_suffix(path.suffix + f".tmp-{uuid.uuid4().hex[:12]}")
    try:
        tmp.write_text(text, encoding=encoding)
        os.replace(tmp, path)   # on success this consumes tmp — the finally's unlink no-ops
    finally:
        tmp.unlink(missing_ok=True)


def _create_exclusive(path: Path, text: str, encoding: str = "utf-8") -> bool:
    """Create `path` with `text` IFF it doesn't already exist — True if THIS call created
    it, False if something else already occupies `path` (left completely untouched).
    v0.1.71 (Track D-2b): writes the FULL content to a temp sibling first, then
    `os.link`s it into place — existence and content become visible together in one
    atomic step. Deliberately NOT `open(path, O_CREAT|O_EXCL)` + write + close: that
    creates `path` EMPTY first and fills it as a separate step, so a concurrent reader
    could observe a torn (empty) file in between — exactly the window `_atomic_write_text`
    exists to close, reopened here if that primitive were used instead. Always cleans up
    its own temp file (success or collision), never leaks one."""
    tmp = path.with_suffix(path.suffix + f".tmp-{uuid.uuid4().hex[:12]}")
    try:
        tmp.write_text(text, encoding=encoding)  # v0.1.71 Gate-2a: moved INSIDE try — a failure
        os.link(str(tmp), str(path))             # here (disk-full etc.) used to skip the finally,
        return True                              # leaving a partial/empty temp sibling behind.
    except FileExistsError:
        return False
    finally:
        tmp.unlink(missing_ok=True)


def _read_capped(p: Path, cap: int = _PYPROJECT_CAP) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="replace")[:cap]
    except OSError:
        return ""


def _strip_toml_comments(text: str) -> str:
    """Drop `#` comments STRING-AWARE — a `#` inside a quoted TOML value (a trailing `# note`, a URL
    fragment) is NOT a comment. Per-line (pyproject dep arrays don't use multiline triple-quoted strings)."""
    out = []
    for line in text.splitlines():
        buf: list[str] = []
        quote = ""
        for ch in line:
            if quote:
                buf.append(ch)
                if ch == quote:
                    quote = ""
            elif ch in ("'", '"'):
                quote = ch
                buf.append(ch)
            elif ch == "#":
                break
            else:
                buf.append(ch)
        out.append("".join(buf))
    return "\n".join(out)


def _norm_dep(name: str) -> str:
    """PEP 503 normalization: lowercase + runs of [-_.] → single '-'."""
    return re.sub(r"[-_.]+", "-", name.strip().lower())


def _names_in_array(block: str) -> set[str]:
    """Leading distribution names of the quoted ITEMS in a TOML dependency array body. Matches each
    FULL quoted string (so a quote INSIDE an item — e.g. an env marker `... == 'linux'` — isn't read as
    its own dep), then takes the item's leading PEP-508 name."""
    names: set[str] = set()
    for q in re.finditer(r'"([^"]*)"' + r"|'([^']*)'", block):
        item = q.group(1) if q.group(1) is not None else (q.group(2) or "")
        m = re.match(r"\s*([A-Za-z0-9][A-Za-z0-9._-]*)", item)
        if m:
            names.add(_norm_dep(m.group(1)))
    return names


def _match_bracket(text: str, i: int) -> int:
    """`text[i]` is '['. Return the index just past its MATCHING ']' — QUOTE- and NEST-aware, so an
    extra inside a dep string (`"uvicorn[standard]"`) can't close the array early."""
    depth, quote = 0, ""
    while i < len(text):
        ch = text[i]
        if quote:
            if ch == quote:
                quote = ""
        elif ch in ("'", '"'):
            quote = ch
        elif ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return len(text)


def _arrays_under(text: str, header_re: str) -> set[str]:
    """Dep names from every `… = [ … ]` array whose `=` is matched by `header_re` (a regex ending just
    before the value); the array's bounds are found via _match_bracket (extras-safe, not a greedy `]`)."""
    names: set[str] = set()
    for m in re.finditer(header_re, text):
        ob = text.find("[", m.end())
        if ob != -1:
            names |= _names_in_array(text[ob:_match_bracket(text, ob)])
    return names


def _dep_names_from_text(pyproject_text: str) -> set[str]:
    """Parse normalized DIRECT dependency names from pyproject.toml TEXT — PEP 621 `dependencies` +
    `[project.optional-dependencies]`, PEP 735 `[dependency-groups]`, and poetry `[tool.poetry…dependencies]`
    tables. Comments stripped string-aware; array bounds extras-safe. Pure (text → names) so it is
    unit-testable without a filesystem. Stdlib-only (no `tomllib` — that needs 3.11+; this plugin's floor is 3.8)."""
    text = _strip_toml_comments(pyproject_text)
    names: set[str] = set()
    for sec in re.finditer(r"(?ms)^\[project\](.*?)(?=^\[|\Z)", text):          # PEP 621 main — ONLY under [project]
        names |= _arrays_under(sec.group(1), r"(?m)^\s*dependencies\s*=\s*(?=\[)")
    for sec in re.finditer(r"(?ms)^\[(?:project\.optional-dependencies|dependency-groups)[^\]]*\](.*?)(?=^\[|\Z)", text):
        names |= _arrays_under(sec.group(1), r"=\s*(?=\[)")                    # arrays inside those tables
    for sec in re.finditer(r"(?ms)^\[tool\.poetry(?:\.group\.[^\]]+)?\.(?:dev-)?dependencies\](.*?)(?=^\[|\Z)", text):
        for km in re.finditer(r"(?m)^\s*([A-Za-z0-9][A-Za-z0-9._-]*)\s*=", sec.group(1)):  # poetry table keys (+ legacy dev-)
            names.add(_norm_dep(km.group(1)))
    # v0.1.76 (audit): poetry DOTTED subtables — `[tool.poetry.dependencies.torch]` declares torch as a
    # header, not a key, so the key-scan above never saw it (a legitimate, if uncommon, poetry form).
    for m in re.finditer(r"(?m)^\[tool\.poetry(?:\.group\.[^\]]+)?\.(?:dev-)?dependencies\.([A-Za-z0-9._-]+)\]", text):
        names.add(_norm_dep(m.group(1)))
    return names


def _pyproject_dep_names(project_dir: Path) -> set[str]:
    """DIRECT dependency names declared in a project's pyproject.toml (LOCKFILES NOT read — they carry
    transitive deps → over-detection)."""
    p = project_dir / "pyproject.toml"
    return _dep_names_from_text(_read_capped(p)) if p.exists() else set()


_PY_SKIP_DIRS = {".venv", "venv", ".git", "node_modules", "__pycache__", "build", "dist", ".mypy_cache", ".tox", ".ruff_cache"}


def _imports_in_source(src: str) -> set[str]:
    """Top-level modules IMPORTED in Python source, via `ast` — so an `import x` inside a docstring or a
    string literal does NOT count (it isn't a real import). Relative imports (`from . import …`) are
    skipped (intra-package, no external-stack signal). Returns an empty set on unparseable source."""
    try:
        tree = ast.parse(src)
    except (SyntaxError, ValueError):
        return set()
    mods: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                mods.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            mods.add(node.module.split(".")[0])
    return mods


def _scan_py(project_dir: Path) -> tuple[set[str], int, bool]:
    """One pruned, capped walk of the project tree → (top-level module names actually imported [ast-based],
    count of .py files seen, whether a real claude-code marker [`.claude/` dir or a `SKILL.md`] exists).
    Past the .py cap we keep WALKING (so a late/nested marker is still found) but stop PARSING files."""
    mods: set[str] = set()
    n = 0
    claude = False
    capped = False
    for root, dirs, files in os.walk(project_dir):
        if ".claude" in dirs:
            claude = True
        dirs[:] = [d for d in dirs if d not in _PY_SKIP_DIRS]
        for fn in files:
            if fn == "SKILL.md":
                claude = True
            if capped or not fn.endswith(".py"):
                continue
            n += 1
            if n > _PY_SCAN_CAP:
                capped = True
                continue
            mods |= _imports_in_source(_read_capped(Path(root) / fn, 524288))
    return mods, n, claude


def detect_stacks(project_dir: Path) -> set[str]:
    """Detect a project's stacks from REAL USAGE — declared deps, actual imports, and real marker
    dirs/files — NOT doc-mentions (v0.1.16; see references/harness-map.md). Lockfiles are excluded
    (transitive deps over-detect). `is_relevant` matches `stack-general` facts against this, so
    precision here is what keeps the middle tier meaningful: a `stack-general:[rag]` fact must bind real
    RAG projects, not any repo whose README merely says "rag"."""
    found: set[str] = set()
    mods, n_py, has_claude = _scan_py(project_dir)
    if (project_dir / "pyproject.toml").exists() or n_py:
        found.add("python")
    deps = _pyproject_dep_names(project_dir)
    for stack, names in _STACK_DEPS.items():
        if deps & names:
            found.add(stack)
    # v0.1.76 (audit): all four DOCUMENTED mypy config locations — pyproject [tool.mypy], mypy.ini,
    # .mypy.ini, setup.cfg [mypy] (mypy.readthedocs.io/en/stable/config_file.html). The first two
    # alone under-detected the stack on .mypy.ini/setup.cfg projects (this fleet is mypy-heavy).
    if (re.search(r"(?m)^\s*\[tool\.mypy\]", _strip_toml_comments(_read_capped(project_dir / "pyproject.toml")))
            or (project_dir / "mypy.ini").exists() or (project_dir / ".mypy.ini").exists()
            or re.search(r"(?m)^\[mypy\]\s*$", _read_capped(project_dir / "setup.cfg"))):
        found.add("mypy")
    for stack, names in _STACK_IMPORTS.items():
        if mods & names:
            found.add(stack)
    if has_claude:
        found.add("claude-code")
    return found


def _domain_fact_dirs() -> list:
    """Named-domain fact dirs only. Leftover ~/.claude/memory is migrate-inventory."""
    domain_dirs: list = []
    try:
        from store_context import config_root
        droot = config_root() / "consolidate-memory" / "domains"
        if droot.is_dir():
            seen: set = set()
            for d in sorted(droot.iterdir()):
                fd = d / "facts"
                try:
                    if not fd.is_dir():
                        continue
                    key = str(fd.resolve())
                except OSError:
                    continue
                if key in seen:
                    continue
                seen.add(key)
                domain_dirs.append(fd)
    except OSError:
        pass
    return domain_dirs


def _records_from_dir(gdir: Path, recs: list, seen: set) -> None:
    """Append (stem, fm, text, path) for one facts dir. Reserved stems skipped."""
    from domain_policy import fact_domain
    if not gdir.exists():
        return
    for f in sorted(gdir.glob("*.md")):
        if f.name == "MEMORY.md" or _is_reserved_stem(f.stem):
            continue
        if not _safe_stem(f.stem):
            continue
        text = _safe_read_text(f)
        if text is None:
            continue
        fm = _frontmatter(text)
        if str(fm.get("status") or "") in ("tombstoned", "superseded", "expired"):
            continue
        key = (fact_domain(fm) or "legacy", f.stem)
        if key in seen:
            continue
        seen.add(key)
        recs.append((f.stem, fm, text, f))


def _all_domain_records() -> list:
    """Admin enumerator (ADR 015 --all-domains): every named domain dir.

    Never leftover ~/.claude/memory. Tests that patched GLOBAL still see that dir.
    """
    recs: list = []
    seen: set = set()
    dirs = _domain_fact_dirs()
    for d in dirs:
        _records_from_dir(d, recs, seen)
    if _global_is_fixture():
        g = global_store()
        try:
            keys = {str(d.resolve()) for d in dirs}
            same = str(g.resolve()) in keys
        except OSError:
            same = False
        if not same:
            _records_from_dir(g, recs, seen)
    return recs


def iter_admissible_facts(ctx) -> list:
    """Facts this StoreContext may pull. Named-domain files only (ADR 008).

    Unenrolled / unhealthy registry → empty. Untagged legacy is not pullable.
    Hermetic tests that patch GLOBAL treat that dir as the current domain store.
    """
    return [(s, fm, t) for s, fm, t, _p in _admissible_records(ctx)]


_MAN_ROWS_STASH: dict = {"ddir": "", "rows": None, "reason": ""}
"""P3 (v0.4.2): the manifest rows loaded by the LAST _admissible_records call in this
process — run() consumes it so one pull parses the facts manifest ONCE (it used to
re-ensure after iter_admissible_facts and parse the 10k-row JSON a second time)."""


_PROJECT_MEMBERSHIPS_CACHE: dict = {}


def _project_memberships(ctx, *, refresh: bool = False) -> set:
    """The group slugs ctx.project_id belongs to (group-scopes spec §5-C).
    Read-only registry lookup; degrade-to-empty on a missing/unmigrated
    registry (the spec's one-cycle skew bound). Cached per project+registry;
    `refresh=True` bypasses the cache — the gc mutate's in-lock re-verify must
    see a membership re-grant that landed between scan and lock (review 3)."""
    try:
        from control_plane import connect_if_exists as _cife_m, db_path as _dbp_m
        _rp = _dbp_m(ctx)
        _ck = (str(_rp), ctx.project_id)
        if not refresh and _ck in _PROJECT_MEMBERSHIPS_CACHE:
            return set(_PROJECT_MEMBERSHIPS_CACHE[_ck])
        out: set = set()
        _mc = _cife_m(_rp)
        if _mc is not None:
            try:
                for r in _mc.execute(
                        "SELECT g.name FROM groups g JOIN group_members m "
                        "ON m.group_id=g.group_id WHERE m.project_id=?",
                        (ctx.project_id,)).fetchall():
                    out.add(str(r["name"]))
            except Exception:
                out = set()   # pre-migration schema: degrade-to-empty
            finally:
                _mc.close()
        if not refresh:
            _PROJECT_MEMBERSHIPS_CACHE[_ck] = frozenset(out)
        return out
    except Exception:
        return set()


_GROUP_CREATED_CACHE: dict = {}


def _group_created_at(ctx, *, refresh: bool = False) -> dict:
    """name → created_at for every group (group-lifecycle spec §2.3). Degrade-
    to-empty on a missing registry; cached keyed by the registry path + a
    groups-table fingerprint (count+max-created) so hermetic recreations
    never serve stale rows. `refresh=True` bypasses the cache — the gc
    mutate's in-lock re-verify must see a recreated group (review 3)."""
    try:
        from control_plane import connect_if_exists as _cife_gc, db_path as _dbp_gc
        _rp = _dbp_gc(ctx)
        _cc = _cife_gc(_rp)
        if _cc is None:
            return {}
        try:
            _fp = _cc.execute("SELECT COUNT(*) AS n, COALESCE(MAX(created_at),'') AS m "
                              "FROM groups").fetchone()
            _ck = (str(_rp), int(_fp["n"]), str(_fp["m"]))
            if not refresh and _ck in _GROUP_CREATED_CACHE:
                return dict(_GROUP_CREATED_CACHE[_ck])
            out = {str(r["name"]): str(r["created_at"] or "")
                   for r in _cc.execute("SELECT name, created_at FROM groups").fetchall()}
            if not refresh:
                _GROUP_CREATED_CACHE[_ck] = dict(out)
            return out
        except Exception:
            return {}
        finally:
            _cc.close()
    except Exception:
        return {}


def _recipients_stale_for(fm: dict, memberships: set, g_created: dict) -> bool:
    """The per-recipient recreation guard (group-lifecycle spec §2.3): True when
    the fact cites recipients this member belongs to, and EVERY one of those
    groups was created AFTER the fact's own content_modified (the stale-identity
    signal). A stamp-less fact passes; a fact with no intersecting recipients
    passes (delivery is not theirs)."""
    from fact_schema import _parse_flow_list  # noqa: F401 — deferred, like _admissible_records
    recips = set(_parse_flow_list(str(fm.get("recipients") or "")))
    inter = recips & memberships
    if not inter:
        return False
    stamp = str(fm.get("content_modified") or "")
    if not stamp:
        return False
    return all((g_created.get(g) or "") > stamp for g in inter)


def _admissible_records(ctx) -> list:
    """iter_admissible_facts plus the actual source path.

    Phase-5 closeout: the facts manifest (facts_manifest.py) serves fresh rows'
    fm/class/secret WITHOUT reading the body — `text` is None for those records
    (consumers that need the body/hash must consult the manifest or the fallback
    read). The manifest fails open: any anomaly → today's full enumeration.
    """
    if not getattr(ctx, "cross_project_allowed", False):
        return []
    from domain_policy import admit_cross_project, fact_domain
    from fact_schema import (CLASS_ACTIVE, CLASS_INVALID, CLASS_LEGACY,
                              _parse_flow_list, classify_canonical)
    from memory_status import _looks_secret
    mode = "dual-read"
    try:
        from control_plane import migration_mode_readonly
        mode = migration_mode_readonly(ctx)
    except Exception:
        mode = "dual-read"
    recs: list = []
    seen: set = set()
    ddir = ctx.canonical_domain_dir
    man_rows = None
    # P3: reset the stash FIRST — an early return must never leave a previous run's
    # rows visible to run() (stale manifest rows are safe to miss, never to reuse).
    _MAN_ROWS_STASH["ddir"] = ""
    _MAN_ROWS_STASH["rows"] = None
    _MAN_ROWS_STASH["reason"] = ""
    # Phase-5 closeout: _global_is_fixture/_hermetic_home hit Path.home() +
    # resolve() — 41% of a 10k-canonical pull when called per fact. Both are
    # env-derived and stable within one run: hoist them.
    _is_fixture_now = _global_is_fixture()
    _hermetic_now = _hermetic_home()
    if ddir.is_dir() and not _is_fixture_now:
        try:
            from facts_manifest import ensure as _fm_ensure
            man_rows, _man_reason = _fm_ensure(ddir, ctx.plugin_data_dir)
            _MAN_ROWS_STASH["ddir"] = str(ddir)
            _MAN_ROWS_STASH["rows"] = man_rows
            _MAN_ROWS_STASH["reason"] = _man_reason
        except Exception:
            man_rows = None

    memberships = _project_memberships(ctx)
    g_created = _group_created_at(ctx)

    def _consider(path: Path, *, untagged_only: bool) -> None:
        if path.name == "MEMORY.md" or _is_reserved_stem(path.stem) or not _safe_stem(path.stem):
            return
        text = _safe_read_text(path)
        if text is None:
            return
        fm = _frontmatter(text)
        st = str(fm.get("status") or "").strip()
        if st in ("tombstoned", "superseded", "expired"):
            return
        if untagged_only and fact_domain(fm):
            return
        if _looks_secret(text):
            return
        # pentest: validate against the ENUMERATION's home domain, never the file's
        # self-declared value — a crafted `domain:` in the frontmatter must not be
        # its own validator (self-consistent '../evil' would pass and reach the
        # mirror-write path). A misfiled fact fails closed, as it should.
        _cls = classify_canonical(text, stem=path.stem, domain=(ctx.domain_id or "unknown"))
        if _cls["class"] != CLASS_ACTIVE:
            # Production: only valid active v3 replicates. Hermetic tests that
            # patch GLOBAL still admit unversioned fixture facts.
            if _cls["class"] == CLASS_INVALID and not _global_is_fixture():
                print(f"  ⚠ invalid canonical skipped: {path.stem} "
                      f"({_cls.get('error')})", file=sys.stderr)
            if not (_global_is_fixture() and _cls["class"] == CLASS_LEGACY):
                return
        adm = dict(fm)
        adm["body"] = text
        if (_is_fixture_now or _hermetic_now) and not fact_domain(fm) and ctx.domain_id not in ("", "unknown"):
            adm["domain"] = ctx.domain_id
        if not admit_cross_project(ctx.domain_id, adm, migration_mode=mode,
                                   looks_secret=_looks_secret,
                                   memberships=memberships,
                                   group_recips=set(_parse_flow_list(
                                       str(fm.get("recipients") or "")))):
            return
        if _recipients_stale_for(fm, memberships, g_created):
            return
        key = (fact_domain(fm) or "legacy", path.stem)
        if key in seen:
            return
        seen.add(key)
        recs.append((path.stem, fm, text, path))

    def _consider_fast(ent_name: str, *, untagged_only: bool,
                       ent_stat: "os.stat_result | None" = None,
                       ent_path: str = "") -> None:
        """Manifest-served record: stat freshness gates the cached row; any
        mismatch/new file falls back to the full read. `ent_stat` is the
        scandir DirEntry's CACHED stat. P3 (v0.4.2): the hot loop passes the
        dirent NAME (+ its stored path string) and builds a Path ONLY on
        fallback — the 10k-file loop was constructing a Path + re-deriving
        stem/name per entry (the pathlib churn profile found in the warm-pull
        margin pass)."""
        _stem = ent_name[:-3]
        if (man_rows is None
                or ent_name == "MEMORY.md" or _is_reserved_stem(_stem)
                or not _safe_stem(_stem)):
            _consider(Path(ddir, ent_name), untagged_only=untagged_only)
            return
        r = man_rows.get(_stem)
        fresh = False
        if r is not None:
            try:
                st = ent_stat if ent_stat is not None else Path(ddir, ent_name).stat()
                fresh = (st.st_mtime_ns == int(r.get("mtime_ns") or -1)
                         and st.st_size == int(r.get("size") or -1)
                         and st.st_ctime_ns == int(r.get("ctime_ns") or -1))
            except OSError:
                fresh = False
        if r is None or not fresh:
            _consider(Path(ddir, ent_name), untagged_only=untagged_only)
            return
        fm = dict(r.get("fm") or {})
        # pentest: the manifest row's class was computed against the file's
        # self-declared domain — a crafted value is its own validator. A row whose
        # declared domain doesn't match the enumeration home falls back to the FULL
        # read path (whose classify now validates against the home).
        if fact_domain(fm) and fact_domain(fm) != (ctx.domain_id or ""):
            _consider(Path(ddir, ent_name), untagged_only=untagged_only)
            return
        if str(fm.get("status") or "").strip() in ("tombstoned", "superseded", "expired"):
            return
        if untagged_only and fact_domain(fm):
            return
        if r.get("secret"):
            return
        if r.get("class") != CLASS_ACTIVE:
            if r.get("class") == CLASS_INVALID:
                print(f"  ⚠ invalid canonical skipped: {_stem} "
                      f"({(r.get('fm') or {}).get('error')})", file=sys.stderr)
            return
        adm = dict(fm)
        adm["body"] = None
        if not fact_domain(fm) and ctx.domain_id not in ("", "unknown"):
            adm["domain"] = ctx.domain_id
        # P3: skip the admit-side secret re-scan for manifest rows — the row's `secret`
        # flag was computed on the FULL text at build time (a strictly stronger check
        # than admit's description+body blob) and this row is stat-fresh, so they cannot
        # disagree. The per-entry `_looks_secret(description)` re-run was ~10k regex
        # passes per warm pull.
        if not admit_cross_project(ctx.domain_id, adm, migration_mode=mode,
                                   memberships=memberships,
                                   group_recips=set(_parse_flow_list(
                                       str(fm.get("recipients") or "")))):
            return
        if _recipients_stale_for(fm, memberships, g_created):
            return
        key = (fact_domain(fm) or "legacy", _stem)
        if key in seen:
            return
        seen.add(key)
        recs.append((_stem, fm, None, ent_path or os.path.join(str(ddir), ent_name)))

    if ddir.is_dir():
        try:
            _entries = list(os.scandir(ddir))
        except OSError:
            _entries = []
        for _ent in sorted(_entries, key=lambda e: e.name):
            _consider_fast(_ent.name, untagged_only=False,
                           ent_stat=_ent.stat(follow_symlinks=False),
                           ent_path=_ent.path)
        del _entries
    # Production: ~/.claude/memory is migrate-inventory only (ADR 008/013).
    # Ordinary --pull/--list/beacon never live-read it — tagged leftovers
    # would otherwise absorb into every enrolled same-domain project.
    # Tests that assign sg.GLOBAL to a fixture dir still enumerate it.
    if _global_is_fixture():
        g = global_store()
        try:
            same = ddir.is_dir() and g.resolve() == ddir.resolve()
        except OSError:
            same = False
        if g.is_dir() and not same:
            for f in sorted(g.glob("*.md")):
                _consider(f, untagged_only=False)

    # v0.4.10 group-scopes: the bridge enumeration — the home domains of every
    # group this project belongs to, filtered to facts whose recipients
    # intersect the project's memberships. Foreign facts always carry their
    # text (no manifest fast path) and are seen-keyed by (domain, stem).
    if memberships:
        from control_plane import connect_if_exists as _cife_g, db_path as _dbp_g
        _gc = _cife_g(_dbp_g(ctx))
        _homes: set = set()
        if _gc is not None:
            try:
                _homes = {str(r["domain_id"]) for r in _gc.execute(
                    "SELECT DISTINCT g.domain_id FROM groups g JOIN group_members m "
                    "ON m.group_id=g.group_id WHERE m.project_id=?",
                    (ctx.project_id,)).fetchall()}
            except Exception:
                _homes = set()
            finally:
                _gc.close()
        for _sdom in sorted(_homes - {ctx.domain_id or ""}):
            _fdir = _source_facts_dir(ctx, _sdom)
            if not _fdir.is_dir():
                continue
            for _f in sorted(_fdir.glob("*.md")):
                if _f.name == "MEMORY.md":
                    continue
                # pentest HIGH: the bridge was the ONE enumeration arm with no
                # name/domain path-safety admission — a crafted stem (index
                # markdown injection) or a crafted `domain:` (mirror write outside
                # the store) sailed through. Same gates as _consider, home = _sdom.
                if _is_reserved_stem(_f.stem) or not _safe_stem(_f.stem):
                    continue
                _ft = _safe_read_text(_f)
                if _ft is None:
                    continue
                _fm_f = _frontmatter(_ft)
                if str(_fm_f.get("status") or "").strip() in ("tombstoned", "superseded", "expired"):
                    continue
                _recips_f = set(_parse_flow_list(str(_fm_f.get("recipients") or "")))
                if not (_recips_f & memberships):
                    continue
                if _recipients_stale_for(_fm_f, memberships, g_created):
                    continue
                _cls_f = classify_canonical(_ft, stem=_f.stem, domain=_sdom)
                if _cls_f["class"] != CLASS_ACTIVE and not (
                        _global_is_fixture() and _cls_f["class"] == CLASS_LEGACY):
                    continue
                if _looks_secret(_ft):
                    continue
                _key_f = (_sdom, _f.stem)
                if _key_f in seen:
                    continue
                seen.add(_key_f)
                recs.append((_f.stem, _fm_f, _ft, _f))
    return recs



def iter_canonical_stems_for_gc(ctx) -> set:
    """On-disk canonical stems in this domain (and fixture GLOBAL). Invalid v3
    files still count as live so their mirrors are not GC-orphaned."""
    stems: set = set()

    def _add(root: Path) -> None:
        if not root.is_dir():
            return
        for f in root.glob("*.md"):
            if f.name == "MEMORY.md" or _is_reserved_stem(f.stem) or not _safe_stem(f.stem):
                continue
            text = _safe_read_text(f)
            if text is None:
                stems.add(f.stem)
                continue
            from fact_schema import CLASS_LEGACY, classify_canonical
            _gcls = classify_canonical(text, stem=f.stem)
            if str((_gcls.get("fm") or {}).get("status") or "").strip() in (
                    "tombstoned", "superseded", "expired"):
                continue
            if _gcls["class"] == CLASS_LEGACY and not _global_is_fixture():
                stems.add(f.stem)
                continue
            stems.add(f.stem)

    _add(ctx.canonical_domain_dir)
    if _global_is_fixture():
        g = global_store()
        try:
            same = ctx.canonical_domain_dir.is_dir() and g.resolve() == ctx.canonical_domain_dir.resolve()
        except OSError:
            same = False
        if not same:
            _add(g)
    return stems


def _hermetic_home() -> bool:
    """True when tests redirected HOME away from the import-time home."""
    try:
        return Path.home().resolve() != _IMPORT_HOME.resolve()
    except OSError:
        return Path.home() != _IMPORT_HOME


def _global_is_fixture() -> bool:
    """True when tests patched GLOBAL away from Path.home()/.claude/memory."""
    g = globals().get("GLOBAL")
    if not isinstance(g, Path):
        return False
    live = Path.home() / ".claude" / "memory"
    try:
        return g.resolve() != live.resolve()
    except OSError:
        return g != live


def _canonical_path(ctx, name: str) -> Path:
    """Current-domain canonical file. Leftover ~/.claude/memory is never a
    production lookup (ADR 008/013); tests that patched GLOBAL still resolve."""
    p = Path(ctx.canonical_domain_dir) / f"{name}.md"
    try:
        if p.exists():
            return p
    except OSError:
        pass
    if _global_is_fixture():
        g = global_store() / f"{name}.md"
        try:
            if g.exists():
                return g
        except OSError:
            pass
    return p


def facts_for_context(ctx, *, all_domains: bool = False) -> list:
    """Ordinary fleet readers: current-domain Canonicals only (ADR 015)."""
    if all_domains:
        return [(s, fm, t) for s, fm, t, _p in _all_domain_records()]
    if getattr(ctx, "cross_project_allowed", False):
        return iter_admissible_facts(ctx)
    return []


def iter_canonicals(ctx, *, all_domains: bool = False) -> list:
    """Typed enumerator (ADR 008/015). Bare stems are not a trust boundary."""
    from identity import ref_from_path
    refs: list = []
    seen: set = set()
    recs = _all_domain_records() if all_domains else _admissible_records(ctx)
    for stem, fm, _text, path in recs:
        # P3: manifest-served recs carry the path STRING (built on fallback only);
        # the full-read path still carries a Path. Normalize here — off the hot path.
        ref = ref_from_path(Path(str(path)), fm,
                            fact_id=str(fm.get("fact_id") or ""),
                            revision=str(fm.get("canonical_revision") or ""))
        if ref.key in seen:
            continue
        seen.add(ref.key)
        refs.append(ref)
    return refs


def _same_domain_stores(ctx) -> list:
    """Native stores of projects enrolled in ctx.domain_id. Empty if local-only."""
    if not getattr(ctx, "cross_project_allowed", False):
        return []
    from control_plane import connect_if_exists, db_path, iter_registered_projects
    conn = connect_if_exists(db_path(ctx))
    if conn is None:
        return []
    out: list = []
    seen: set = set()
    try:
        for r in iter_registered_projects(conn):
            if str(r.get("domain_id") or "") != ctx.domain_id:
                continue
            nd = Path(str(r.get("native_memory_dir") or ""))
            try:
                key = str(nd.resolve())
            except OSError:
                key = str(nd)
            if key in seen or not nd.is_dir():
                continue
            seen.add(key)
            out.append(nd)
    finally:
        conn.close()
    return out


def _fact_stacks(fm: dict) -> set[str]:
    """A fact's declared `stacks:` tags as a lowercased-token set. Shared by relevance matching
    AND the promotion stacks-guard so the two parse `stacks:` identically (a stack-general fact is
    relevant — and promotable — iff this set is non-empty and intersects the project's stacks)."""
    return set(re.findall(r"[a-z0-9-]+", fm.get("stacks", "").lower()))


def _memo_fact_stacks(fm: dict, memo: dict) -> set[str]:
    """_fact_stacks with a run-local memo keyed on the RAW `stacks:` string (P3, v0.4.2) — a
    fleet's canonicals share stacks lines, and a 10k-canonical pull re-parsed them all per fact
    (plus a second parse in the fleet-dead warning loop). The returned set is SHARED — callers
    must never mutate it."""
    _key = str(fm.get("stacks") or "").lower()
    _got = memo.get(_key)
    if _got is None:
        _got = _fact_stacks(fm)
        memo[_key] = _got
    return _got


def is_relevant(fm: dict, stacks: set[str], *, stacks_memo: "dict | None" = None) -> bool:
    scope = fm.get("scope", "")
    if scope == "user-global":
        return True
    if scope == "stack-general":
        if stacks_memo is not None:
            return bool(_memo_fact_stacks(fm, stacks_memo) & stacks)
        return bool(_fact_stacks(fm) & stacks)
    return False


def _body_hash(text: str) -> str:
    """sha1-12 of the fact BODY (`_body` — frontmatter stripped): the mirror's content-LINEAGE key
    (v0.1.78, docs/evidence-clock-stamps.spec.md). BODY-only by design — a description/stacks/
    provenance tweak refreshes the mirror TEXT but is not new content, so it must not reset the
    fleet's zero-read evidence clock; a body change is, and must. Not a security boundary."""
    return hashlib.sha1(_body(text).encode("utf-8")).hexdigest()[:12]


def _ceil_iso(epoch: float) -> str:
    """Epoch → whole-second ISO, seconds CEILED (PR-#91 adversarial F3): a FLOORED stamp lets a
    window starting inside [floor(t), t) count where the raw float clock would not — over-crediting
    zero-read evidence against the pinned undercount bias. Ceiling keeps `window_start >= clock`
    strictly conservative (a window in the same second as the write never counts)."""
    return datetime.fromtimestamp(math.ceil(epoch), tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _now_iso() -> str:
    return _ceil_iso(datetime.now(timezone.utc).timestamp())


def _mtime_iso(path: Path) -> str:
    """The file's mtime as ISO — the migration seed for a pre-stamp mirror's lineage clock
    (the best clock we have; deliberately NOT now(), which would restart the fleet's evidence
    from zero). The OSError fallback IS now(): reachable only via a delete race after the caller
    already read the file, and it fails toward LESS evidence (undercount — the pinned safe bias),
    never toward inventing age. Seconds are ceiled — see _ceil_iso."""
    try:
        return _ceil_iso(path.stat().st_mtime)
    except OSError:
        return _now_iso()


def _source_facts_dir(ctx, sdom: str) -> Path:
    """The facts dir for a source domain (group-scopes: cross-domain canonicals
    live in THEIR domain's dir, not the pulling project's). Same-domain keeps
    the _canonical_path parity: hermetic tests that patched GLOBAL still resolve
    there (the fixture case), never the leftover ~/.claude/memory in production."""
    if not sdom or sdom == (getattr(ctx, "domain_id", "") or ""):
        p = Path(ctx.canonical_domain_dir)
        try:
            if not p.is_dir() and _global_is_fixture():
                return global_store()
        except OSError:
            pass
        return p
    return Path(ctx.canonical_domain_dir).resolve().parents[1] / sdom / "facts"


def _mirror_key(ctx_domain: str, fact_dom: str, stem: str) -> str:
    """The mirror FILE key for a canonical: the bare stem when the fact is
    same-domain (unchanged, backward-compatible), `{domain}--{stem}` when the
    canonical lives in another domain (group-scopes spec §5-A). Refuses the
    ambiguous encoding — if either part contains `--`, the namespaced form
    would collide with another split, so the operator must rename.

    pentest: also refuses an unsafe DOMAIN value (path separators / '..' / a
    leading dot) — a crafted frontmatter `domain:` would otherwise escape the
    store via Path normalization on the mirror write. Admission normally keeps
    such values out; this is the write-path's own fence."""
    fdom = fact_dom or ctx_domain or ""
    if fdom and fdom != (ctx_domain or "") and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", fdom):
        raise ValueError(
            f"unsafe domain in mirror key: {fdom!r} — the canonical's domain "
            "field must be a plain slug (no /, .., or leading dot)")
    if fdom == (ctx_domain or "") or not fdom:
        return stem
    if "--" in fdom or "--" in stem:
        raise ValueError(
            f"namespaced mirror key ambiguity: domain {fdom!r} / stem {stem!r} "
            "both may contain '--' — rename the domain or the stem")
    return f"{fdom}--{stem}"


def decode_key(key: str) -> tuple:
    """Split a mirror key into (domain, stem). Valid namespaced keys have
    exactly one `--` (the encoder refuses ambiguous parts); a bare stem
    decodes to ('', stem)."""
    if "--" not in key:
        return "", key
    fdom, _, stem = key.partition("--")
    return fdom, stem


def _as_mirror(text: str, name: str, since: str = "", body_hash: str = "",
               fact_id: str = "", domain: str = "", groups: list | None = None) -> str:
    """Return the global fact stamped as a managed mirror (`global_ref: <name>`),
    robustly — drop any existing global_ref, then insert one after `metadata:`.

    v0.1.78 (evidence-clock stamps): when `since`/`body_hash` are supplied, two sibling stamps
    ride the same metadata anchor — `global_ref_since:` (when this mirror's content-lineage
    began) and `global_ref_body:` (the sha1-12 lineage key). run()/promote() compute the carry;
    bare calls (tests, legacy paths) emit no stamps. The frontmatter-scoped strip covers the
    whole `global_ref` prefix so re-stamping stays idempotent; `_is_mirror` keys on
    `global_ref:` only, so the smoke-pinned round-trip is untouched. REACH LIMIT: the
    no-metadata-block fallback inserts a real `metadata:` block (never a `# global_ref:`
    first-line comment) so lineage stamps have a home.

    The metadata anchor must be a COLUMN-0 top-level key (mirroring `_is_mirror`'s
    `not ln[:1].isspace()` test). An INDENTED `  metadata:` is NOT a valid anchor: if it
    were, this would stamp `  global_ref:` somewhere `_is_mirror` doesn't recognize,
    producing an unrecognized/never-refreshed/GC-immune mirror (producer↔recognizer
    desync). Such input instead falls through to the column-0 `# global_ref:` stamp,
    which `_is_mirror` does recognize. The `_is_mirror(_as_mirror(...))` round-trip is a
    load-bearing invariant — see the smoke test."""
    if text.startswith("﻿"):     # strip a leading BOM so the written mirror begins with '---'
        text = text[1:]                # (else _is_mirror's ^--- anchor fails on our own output)
    out: list[str] = []
    injected = False
    dashes = 0                         # frontmatter = the span between the OPEN fence and the CLOSE fence
    for i, ln in enumerate(text.splitlines()):
        s = ln.strip()
        # v0.1.74 fence PARITY with _frontmatter/_is_mirror (`^---\n(.*?)\n---` — the ONE boundary rule):
        # the OPEN fence is the exact FIRST line '---'; the CLOSE is any later line whose RAW start is
        # '---' ('----', '--- notes' close there; an INDENTED '  ---' is NOT a fence). The old
        # bare-stripped-'---'-only count diverged from the parser BOTH ways (2026-07-10 audit finding #1,
        # measured): through a non-bare close it stayed "inside frontmatter" to EOF, so the dashes==1-scoped
        # strips below ATE every body line starting 'projects:'/'global_ref:' — silent mirror corruption on
        # --pull (every puller) and on --promote (the origin's OWN copy) — and an indented '---' closed it
        # EARLY, leaking canonical-only 'projects:' provenance into every mirror (the v0.1.26 churn class,
        # reopened). A pre-existing corrupted mirror self-heals: the corrected `want` differs → STALE → refresh.
        if dashes == 0:
            if i == 0 and ln == "---":
                dashes = 1
        elif dashes == 1 and ln.startswith("---"):
            dashes = 2
        # v0.1.70 Gate-2a: frontmatter-scoped (dashes == 1) — was unscoped, silently deleting ANY body
        # line starting with the literal text "global_ref:" (plausible in this self-documenting repo,
        # e.g. a note explaining the mirror mechanism itself). Both of THIS function's own legitimate
        # stamps (the metadata-child form and the post-opening-'---' fallback) land strictly within
        # dashes == 1, so scoping the strip the same way loses no correctness.
        if dashes == 1 and s.startswith(("global_ref:", "global_ref_since:", "global_ref_body:", "group:",
                                         "canonical_fact_id:", "canonical_domain:")):
            # drop any existing global_ref + stamp lines (re-stamped below). EXACT three keys, not the
            # bare "global_ref" prefix (PR-#91 adversarial review): the wide prefix re-ate what the
            # v0.1.70 narrowing protects — e.g. a folded-scalar description continuation line that
            # happens to begin "global_reference …" was silently dropped from the mirror's frontmatter.
            continue
        # v0.1.26 (provenance-churn root-fix): `projects:` is CANONICAL-ONLY bookkeeping (the synapse
        # record `network()`/`_holders` read off the global store). NEVER carry it into a mirror — else
        # every pull that grows a canonical's holder list marks all OTHER mirrors stale (cosmetic churn).
        # Frontmatter-scoped (dashes == 1) so a prose body line can never be stripped.
        if dashes == 1 and s.startswith("projects:"):
            continue
        out.append(ln)
        # v0.1.70 security: frontmatter-scoped (dashes == 1), exactly like the projects: strip above —
        # an unscoped scan lets a bare `metadata:` line in the BODY (prose, or crafted) steal the anchor,
        # stamping global_ref: outside the span _is_mirror() parses. That breaks this function's own
        # documented _is_mirror(_as_mirror(...)) round-trip invariant and produces a permanent,
        # un-refreshable, GC-immune mirror (never reclaimed, never updated).
        if not injected and dashes == 1 and not ln[:1].isspace() and s.rstrip(":") == "metadata":
            out.append(f"  global_ref: {name}")
            if fact_id:
                out.append(f"  canonical_fact_id: {fact_id}")
            if domain and domain != "unknown":
                out.append(f"  canonical_domain: {domain}")
            if groups:   # v0.4.10 group-scopes: ALL recipient slugs (volatile stamp —
                out.append("  group: " + ", ".join(str(g) for g in groups))
            if since:   # v0.1.78: the content-lineage clock (see docstring; caller computes the carry)
                out.append(f"  global_ref_since: {since}")
                out.append(f"  global_ref_body: {body_hash}")
            injected = True
    if not injected:  # no metadata block — insert one so lineage stamps have a home
        for i, ln in enumerate(out):
            if ln.strip() == "---":
                block = ["metadata:", f"  global_ref: {name}"]
                if fact_id:
                    block.append(f"  canonical_fact_id: {fact_id}")
                if domain and domain != "unknown":
                    block.append(f"  canonical_domain: {domain}")
                if groups:
                    block.append("  group: " + ", ".join(str(g) for g in groups))
                if since:
                    block.append(f"  global_ref_since: {since}")
                    block.append(f"  global_ref_body: {body_hash}")
                for j, b in enumerate(block):
                    out.insert(i + 1 + j, b)
                break
    return "\n".join(out) + "\n"


def _pointer_line(name: str, fm: dict, anchor: str = "") -> str:
    """The canonical index pointer line for a fact (pure — testable). The `description`
    is the recall hook; it comes from a global fact (possibly crafted) and is written
    into the always-loaded index, so sanitize it: collapse control bytes/newlines to a
    space (a stray newline/ESC would break or inject into the index line), then truncate."""
    desc = fm.get("description", "").strip().strip('"')
    # Strip control bytes (line-break/ESC injection) AND markdown link/bracket chars so a
    # crafted description can't inject a link or a spoofed `](name.md)` target into the
    # always-loaded index line.
    desc = " ".join(re.sub(r"[\x00-\x1f\x7f-\x9f\[\]()<>]", " ", desc).split())
    hook = (desc[:88] + "…") if len(desc) > 88 else desc
    scope = fm.get("scope", "")
    href = anchor or name
    return f"- [{name}]({href}.md) — {hook}" + (f" [{scope}]" if scope else "")


def _fat_hook_warning(pointer_line: str, name: str, *,
                      source_kind: str = "canonical",
                      source_path: "str | None" = None) -> str | None:
    """v0.1.66 (Phase B): the write-time fat-hook LINT — a warning string when a pointer line exceeds
    HOOK_TOKEN_WARN est tok, else None. PURE (smoke-pinned). The line is NEVER truncated — a recall
    cue silently shortened is a recall cue silently broken (report-then-apply).

    `source_kind` is `canonical` (tighten the domain canonical) or `local` (tighten this
    project's native fact). Do not name `~/.claude/memory/` for a local pointer.
    """
    t = est_tokens(pointer_line)
    if t <= HOOK_TOKEN_WARN:
        return None
    if source_kind == "local":
        loc = source_path or (name + ".md")
        return (f"⚠ fat hook: '{name}' pointer ≈{t} tok > {HOOK_TOKEN_WARN} — tighten the LOCAL "
                f"fact's description ({loc})")
    loc = source_path or ("canonical " + name + ".md")
    return (f"⚠ fat hook: '{name}' pointer ≈{t} tok > {HOOK_TOKEN_WARN} — tighten the CANONICAL's "
            f"description ({loc}); this line taxes every session on every node")


def _execute_pull_writes(ctx, store: Path, jobs: list, evict_stem: "str | None",
                         evict_path: "Path | None",
                         holder_token: str = "",
                         in_sync_names: "list | None" = None,
                         conflict_ops: "list | None" = None,
                         sem_by_name: "dict | None" = None) -> dict:
    """Publish pull bodies + index through transact (pointer-before-body for MISSING).

    `jobs` is [(name, fm, status, path, want), ...] already stamped. Evict unlinks
    AFTER dests publish so a crash-before-publish does not destroy the authored fact
    without landing the swap. Holders are recorded on the control plane INSIDE this
    transact (registry-authoritative). Markdown `projects:` is not rewritten.
    """
    from control_plane import (ABSENT as _ABS_PULL, CrashSimulated, record_holders,
                               stable_fact_id, transact)
    from index_admission import apply_pointer, project_index
    from mirror_conflict import semantic_hash as _sem_hold
    from store_context import WriteRefused

    in_sync_names = list(in_sync_names or [])
    conflict_ops = list(conflict_ops or [])
    _fm_by_name = {n: fm for n, fm, *_ in (jobs or [])}
    if not jobs and not evict_stem and not in_sync_names and not conflict_ops:
        return {"pulled": 0, "refreshed": 0, "fat": 0}
    idxp = store / "MEMORY.md"
    expected: dict = {}

    def _sha(p: Path) -> str:
        return hashlib.sha256(p.read_bytes()).hexdigest()

    if jobs or evict_stem:
        if idxp.exists():
            expected[str(idxp)] = _sha(idxp)
        for _n, _f, _s, path, _w in jobs:
            if path.exists():
                expected[str(path)] = _sha(path)
    landed: set = set()
    for name, _f, _s, _p, _w in jobs:
        landed.add(name)
    holder_names = [n for n in landed] + [n for n in in_sync_names if n not in landed]
    for name in holder_names:
        # Phase-5 closeout: a manifest-fresh canonical skips the full _sha
        # pre-read — the mutate below re-checks freshness under the lock and
        # degrades to a re-read on any change (a racing hand-write then yields
        # a one-edit-stale holder base, which classifies REFRESH next run).
        if (sem_by_name or {}).get(name, {}).get("mtime_ns") is not None:
            continue
        cp = _canonical_path(ctx, name)
        if cp.exists():
            expected[str(cp)] = _sha(cp)

    def mutate(conn, temps):
        idx_text = _safe_read_text(idxp) or "# Memory Index\n\n"
        deletes: list = []
        dest_modes: dict = {}
        expected_m: dict = {}
        pulled = refreshed = fat = 0
        recorded: list = []
        if (jobs or evict_stem) and not idxp.exists():
            dest_modes[str(idxp)] = "create"
            expected_m[str(idxp)] = _ABS_PULL
        planned = idx_text
        if evict_stem:
            planned = "\n".join(
                ln for ln in planned.splitlines() if f"]({evict_stem}.md)" not in ln
            ) + "\n"
        for name, fm, status, path, want in jobs:
            _j_sdom = str(fm.get("domain") or ctx.domain_id or "")
            _j_key = _mirror_key(ctx.domain_id, _j_sdom, name)
            planned = apply_pointer(planned, _pointer_line(name, fm, anchor=_j_key), name)
        plan_adm = project_index(planned)
        if evict_stem and not plan_adm["admitted"]:
            raise WriteRefused(
                "exact index admission refused; evict aborted: " + plan_adm["reason"])
        if evict_stem:
            # pentest (P0-4 parity): the in-lock re-verification every other
            # destructive arm performs — re-check the target under the lock and
            # pin its preimage, so a file that changed (or became a mirror)
            # between pre-lock validation and publication refuses the write.
            if evict_path is None or not evict_path.exists():
                raise WriteRefused("evict target vanished before the lock")
            _evt_now = _safe_read_text(evict_path)
            if _evt_now is None or _is_mirror(_evt_now):
                raise WriteRefused("evict target changed before the lock")
            expected_m[str(evict_path)] = _sha(evict_path)
            idx_text = "\n".join(
                ln for ln in idx_text.splitlines() if f"]({evict_stem}.md)" not in ln
            ) + "\n"
            if evict_path is not None:
                deletes.append(str(evict_path))
        for name, fm, status, path, want in jobs:
            _j_sdom = str(fm.get("domain") or ctx.domain_id or "")
            _j_key = _mirror_key(ctx.domain_id, _j_sdom, name)
            ptr = _pointer_line(name, fm, anchor=_j_key)
            lint = _fat_hook_warning(ptr, name)
            ptr_unchanged = any(
                f"]({_j_key}.md)" in ln and ln.strip() == ptr.strip()
                for ln in idx_text.splitlines())
            future = apply_pointer(idx_text, ptr, name)
            adm = project_index(future)
            if status == "MISSING":
                if path.exists():
                    # Appeared after pre-lock classify — never clobber a local file (P0-4).
                    continue
                if not adm["admitted"]:
                    print(f"  ⚠ index admission refused for '{name}': {adm['reason']}",
                          file=sys.stderr)
                    continue
                idx_text = future
                temps[str(path)] = want
                dest_modes[str(path)] = "create"
                expected_m[str(path)] = _ABS_PULL
                pulled += 1
                recorded.append(name)
                if lint:
                    print(f"  {lint}", file=sys.stderr)
                    fat += 1
            else:
                # Re-classify under lock: a local edit between pre-lock classify
                # and publication must never be overwritten (P0-4).
                cur_now = _safe_read_text(path) or ""
                if not cur_now or not _is_mirror(cur_now):
                    # Non-mirror / local body — STALE must not clobber.
                    continue
                if cur_now and _is_mirror(cur_now):
                    from mirror_conflict import (CONFLICT as _CFL, QUARANTINE as _QAR,
                                                 STOP_LOCAL as _STP, classify_mirror as _cml)
                    from control_plane import holder_base_revision as _hbr2, stable_fact_id as _sf2
                    _ws_dom = str(fm.get("domain") or ctx.domain_id or "")
                    _cfm = _frontmatter(cur_now)
                    _hb = _hbr2(conn, _sf2(_ws_dom, name), ctx.project_id)
                    if not _hb:
                        # bootstrap (F1): the first refresh after the provenance
                        # fix has no recorded holder base — the mirror's OWN
                        # canonical_revision is the revision it sits at.
                        _hb = str(_cfm.get("canonical_revision") or "") or None
                    _ct = _safe_read_text(_source_facts_dir(ctx, _ws_dom) / f"{name}.md") or ""
                    _v3lock = bool(_cfm.get("canonical_fact_id") or _cfm.get("schema_version"))
                    _act2 = _cml(cur_now, _ct, base_revision=_hb,
                                 allow_legacy_fallback=not _v3lock)["action"]
                    if _act2 in (_STP, _CFL, _QAR):
                        continue
                temps[str(path)] = want
                refreshed += 1
                recorded.append(name)
                if adm["admitted"]:
                    idx_text = future
                    if lint and not ptr_unchanged:
                        print(f"  {lint}", file=sys.stderr)
                        fat += 1
                else:
                    print(f"  ⚠ index admission refused for '{name}': {adm['reason']}",
                          file=sys.stderr)
        if jobs or evict_stem:
            temps[str(idxp)] = idx_text if idx_text.endswith("\n") else idx_text + "\n"
        hold_set = list(recorded)
        for n in in_sync_names:
            if n not in hold_set:
                hold_set.append(n)
        holders = []
        _hold_rows: list = []
        for name in hold_set:
            row = (sem_by_name or {}).get(name) or {}
            _hd_dom = str((_fm_by_name or {}).get(name, {}).get("domain")
                          or ctx.domain_id or "") if _fm_by_name else (ctx.domain_id or "")
            ctext: "str | None" = None
            if isinstance(row, dict) and row.get("mtime_ns") is not None:
                cp = _source_facts_dir(ctx, _hd_dom) / f"{name}.md"
                try:
                    stc = cp.stat()
                    if (stc.st_mtime_ns == int(row.get("mtime_ns") or -1)
                            and stc.st_size == int(row.get("size") or -1)
                            and stc.st_ctime_ns == int(row.get("ctime_ns") or -1)):
                        ctext = ""   # sentinel: manifest row still fresh → cached sem
                except OSError:
                    pass
            if ctext is None:
                ctext = _safe_read_text(_source_facts_dir(ctx, _hd_dom) / f"{name}.md")
                if ctext is None:
                    continue
            if ctext == "":
                rev = str(row.get("sem") or "")
            else:
                rev = _sem_hold(ctext)
            fid = stable_fact_id(_hd_dom, name)
            # P3: collect, then ONE executemany (N statements before — the warm pull's
            # holder re-record was ~50ms of the 10k-canonical run)
            _hold_rows.append((fid, ctx.project_id, rev, rev, rev))
            holders.append((fid, ctx.project_id, rev, rev, rev))
        if _hold_rows:
            record_holders(conn, _hold_rows)
        hold_ops = [
            {"op": "holder_upsert", "fact_id": h[0], "project_id": h[1],
             "base_revision": h[2], "canonical_revision": h[3], "semantic_hash": h[4]}
            for h in holders
        ] + list(conflict_ops)
        return {"pulled": pulled, "refreshed": refreshed, "fat": fat, "deletes": deletes,
                "holders": holders, "dest_modes": dest_modes,
                "expected_revisions": expected_m, "registry_ops": hold_ops}

    try:
        out = transact(ctx, "pull", {
            "project_id": ctx.project_id, "n": len(jobs),
            "stems": [j[0] for j in jobs],
        }, mutate, expected_revisions=expected)
        r = out.get("result") or {}
        return {"pulled": int(r.get("pulled") or 0), "refreshed": int(r.get("refreshed") or 0),
                "fat": int(r.get("fat") or 0)}
    except CrashSimulated:
        raise
    except WriteRefused as e:
        print(f"pull: transaction refused: {e}", file=sys.stderr)
        return {"pulled": 0, "refreshed": 0, "fat": 0, "error": str(e)}


def _would_net_grow(running_idx: int, pointer_cost: int, allow_net_grow: bool, budget: int) -> bool:
    """M1: True iff pulling a new fact (its pointer adds `pointer_cost` tokens) would LEAVE the always-loaded
    index over `budget` — the projected net-grow guard. `allow_net_grow` overrides. PURE — the primitive
    _plan_pull replays for every hold decision in run() (so smoke can pin all cases deterministically).

    v0.1.66 (Phase B): PRODUCTION call sites pass budget=INDEX_CEILING_TOKENS — the hold fires only past
    the HARD CEILING, no longer in the over-target amber band (verified knowledge flows until the real
    harm boundary; the target gate is a separate, untouched signal). `budget` is REQUIRED, no default
    (a max-effort code-review workflow, 2026-07-04, flagged the original `= INDEX_TOKEN_BUDGET` default
    as an unenforced drift risk: a future call site that forgot the `budget=` kwarg would silently
    resurrect the pre-Phase-B semantics — holding in the amber band again — with no test or type error
    catching it). The v0.1.38 smoke pins now pass `budget=INDEX_TOKEN_BUDGET` explicitly to exercise the
    same pure logic at the target threshold."""
    return (not allow_net_grow) and (running_idx + pointer_cost > budget)


def _inbound_links(store: Path, target: str) -> list[str]:
    """v0.1.41 (evict-to-receive safety): local fact stems whose body `[[links]]` to `target` — evicting `target`
    would ORPHAN them (the cascade --evict must refuse). Reuses extract_wikilinks (the SINGLE [[...]] extractor,
    code spans stripped) + resolve_wikilink (so a dash/underscore/date VARIANT link counts too — the safe bias).
    Excludes `target` itself + MEMORY.md (the pointer index holds no wikilinks). READ-ONLY."""
    out: list[str] = []
    if not store.is_dir():
        return out
    for f in sorted(store.glob("*.md")):
        if f.name == "MEMORY.md" or _is_reserved_stem(f.stem) or f.stem == target:
            continue
        body = _safe_read_text(f)   # store-scan convention (shared helper — v0.1.69 Gate-2b)
        if body is None:
            continue
        if any(resolve_wikilink(l, {target}) == target for l in extract_wikilinks(body)):
            out.append(f.stem)
    return out


def _index_line_cost(index_text: str, stem: str) -> int:
    """est-token cost of the REAL index line for `stem` — matched by its `](stem.md)` link anchor
    (the same spoof-resistant `](stem.md)` link-target rule apply_pointer uses) — 0 when absent.
    The evict valve's `freed` MUST come from here, never from a derived _pointer_line estimate
    (docs/evict-accounting-truth.spec.md F2, measured): a pointer-LESS fact once "freed" a phantom
    ~33t and the pull then breached the hard ceiling by real bytes, while a fat HAND-WRITTEN line
    (~74t real) was judged by its lean derived pointer (~7t) and the best candidate refused."""
    anchor = f"]({stem}.md)"
    for ln in index_text.splitlines():
        if anchor in ln:
            return est_tokens(ln)
    return 0


def _plan_pull(items: list, start_idx: int, allow_net_grow: bool, budget: int) -> dict:
    """Replay the pull loop's index accounting IN ITERATION ORDER — the single decision source
    BOTH run()'s write loop and the --evict A/B gain-gate consume (docs/evict-accounting-truth.spec.md
    F3/F4, measured): the old held_pre pre-scan evaluated each fact against the STATIC seeded index
    while the loop ACCUMULATED (same function, DIFFERENT argument — the trap the old "SAME predicate"
    comment papered over), so near the ceiling an evict could pass its fit-check yet land nothing.

    `items` = (name, status, cost_new, cost_old) for every RELEVANT MISSING/STALE-mirror fact in
    loop order; cost_old is the fact's REAL existing index line (_index_line_cost, usually 0 for
    MISSING). A MISSING pull grows the index by (cost_new - cost_old) unless that would net-grow
    past `budget` (→ HELD, at its full pointer cost for display); a STALE-mirror refresh ALWAYS
    runs and contributes its real pointer delta (F4: refresh deltas were previously untracked, so
    a later hold decision used a stale figure and breached the ceiling by a measured +22t).
    PURE (smoke-pinned). `budget` REQUIRED, no default (the _would_net_grow v0.1.66 drift-risk rule).
    Granularity note: the caller seeds start_idx from the WHOLE index file while deltas are
    per-line est_tokens — the known ceil-rounding mix (see _node_tokens), unchanged here.
    Returns {"pull": [names], "held": [(name, cost_new)], "end_idx": int}."""
    idx = start_idx
    pull: list = []
    held: list = []
    for name, status, cost_new, cost_old in items:
        if status == "MISSING":
            delta = cost_new - cost_old
            if _would_net_grow(idx, delta, allow_net_grow, budget=budget):
                held.append((name, cost_new))
            else:
                pull.append(name)
                idx += delta
        elif status == "STALE-mirror":
            idx += cost_new - cost_old
    return {"pull": pull, "held": held, "end_idx": idx}


def _write_stacks_cache(store: Path, project_dir: Path, stacks: set) -> None:
    """v0.1.81 (session-beacon Stage B, docs/session-beacon.spec.md): merge SCRIPT-TRUTH
    `stacks` + `project_path` into the store's .consolidation-state.json at --pull time —
    detect_stacks just ran (this is its freshest possible value), and the SessionStart beacon
    cannot afford to recompute it (MEASURED: 2003ms on the fleet's biggest repo vs the hook's
    2s budget; 144ms even on this repo). `project_path` is the honest slug→path inverse,
    recorded at the one moment it is authoritatively known (the lossy-slug rule: never guess
    it back). MERGE-write — every model-written key (timestamp/commit/standing_justify/
    demotion_justify) is preserved verbatim; best-effort: a failure degrades the beacon and
    --staleness to user-global-only (labeled), never fails the pull.
    v0.4.2 (P1): gains the `stacks_stamp`/`stacks_at` cache identity + an unchanged-value
    early return (a no-change pull re-pays nothing)."""
    import json as _json_wsc
    import time as _t_wsc
    from control_plane import update_project_state
    from store_context import WriteRefused, resolve_store
    try:
        ctx = resolve_store(project_dir)
        _sig = _stacks_signature(project_dir)
        try:
            _prev = _json_wsc.loads(
                (ctx.native_memory_dir / ".consolidation-state.json").read_text(encoding="utf-8"))
            # P1 review fix: the early return ALSO requires the cache to be FRESH — without
            # the TTL check, a stable project whose cache crossed the 7-day window never
            # re-armed (every sync path re-paid detect_stacks forever). A non-numeric
            # stacks_at raises ValueError → the write path below refreshes it.
            if isinstance(_prev, dict) \
                    and [str(s) for s in (_prev.get("stacks") or [])] == sorted(stacks) \
                    and _prev.get("stacks_stamp") == _sig \
                    and str(_prev.get("project_path") or "") == str(project_dir) \
                    and _t_wsc.time() - float(_prev.get("stacks_at") or 0) < _STACKS_TTL_S:
                return    # byte-identical AND fresh cache — skip the locked write entirely
        except (OSError, ValueError):
            pass

        def mutator(state: dict, snap: object) -> dict:
            del snap
            st = dict(state)
            st["stacks"] = sorted(stacks)
            st["stacks_stamp"] = _sig
            st["stacks_at"] = _t_wsc.time()
            st["project_path"] = str(project_dir)
            return st

        update_project_state(ctx, mutator)
    except (OSError, WriteRefused) as e:
        print(f"  ⚠ stacks-cache write skipped ({e.__class__.__name__}) — the session beacon "
              "degrades to user-global-only until the next pull", file=sys.stderr)


_STACKS_MARKER_FILES = ("pyproject.toml", "mypy.ini", ".mypy.ini", "setup.cfg", "SKILL.md")
_STACKS_TTL_S = 7 * 86400    # the stamp cannot see .py-content changes — bound the staleness


def _stacks_signature(project_dir: Path) -> list:
    """v0.4.2 (P1): the invalidation stamp — (name, mtime_ns, size) of the marker files
    detect_stacks actually reads (pyproject deps, the four mypy configs, SKILL.md). The
    .py-import walk and the .claude/ detection are deliberately NOT statted here (that
    would re-pay the scan) — the TTL bounds their staleness."""
    out = []
    for name in _STACKS_MARKER_FILES:
        p = project_dir / name
        try:
            st = p.stat()
            out.append([name, int(st.st_mtime_ns), int(st.st_size)])
        except OSError:
            continue
    return out


def stacks_with_cache(store: Path, project_dir: Path) -> "tuple[set[str], bool]":
    """v0.4.2 (P1): consult the beacon's stacks cache before re-running detect_stacks — the
    full-project walk + ast-parse re-paid on EVERY --pull/--list/--gc/--promote path
    measured 337ms here (2003ms documented worst), all of it wasted when the marker files
    haven't changed. (The --staleness NON-trigger rows already read the state-file cache
    directly since v0.1.81; the trigger row's detect_stacks stays live.) Returns
    (stacks, from_cache). Re-detects when: the cache is absent or not a list, the stamp
    differs, the TTL elapsed, CM_RESCAN_STACKS=1 is set, or the recorded project_path
    doesn't resolve here. A cache miss NEVER guesses — full rescan."""
    import json as _json_sc
    import time as _time_sc
    if os.environ.get("CM_RESCAN_STACKS") == "1":
        return detect_stacks(project_dir), False
    cached: "list | None" = None
    stamp: "list | None" = None
    at = 0.0
    path_ok = False
    try:
        raw = _safe_read_text(store / ".consolidation-state.json")
        if raw:
            st = _json_sc.loads(raw)
            if isinstance(st, dict):
                if isinstance(st.get("stacks"), list):
                    cached = [str(s) for s in st["stacks"]]
                if isinstance(st.get("stacks_stamp"), list):
                    stamp = st["stacks_stamp"]
                try:
                    at = float(st.get("stacks_at") or 0)
                except (TypeError, ValueError):
                    at = 0.0
                path_ok = str(st.get("project_path") or "").strip() == str(project_dir)
    except (OSError, ValueError):
        cached = stamp = None
    if cached is not None and path_ok and stamp == _stacks_signature(project_dir) \
            and (_time_sc.time() - at) < _STACKS_TTL_S:
        return set(cached), True
    return detect_stacks(project_dir), False


def run(project_dir: Path, pull: bool, allow_net_grow: bool = False, evict: str | None = None) -> int:
    from fact_schema import _parse_flow_list  # noqa: F401 — group-scopes recipients parsing
    # v0.1.38 (M1): the PROJECTED net-grow BACKSTOP. A MISSING fact = a NEW always-loaded index pointer (the
    # v0.1.18 blowup class); on --pull we HOLD it when it would push the index past the threshold
    # (running_idx + the pointer's own cost) — even on a NEAR-threshold store one pull would tip over (the
    # case a model-read cue MISSES: it can't know the per-pull cost; only this function, which both measures
    # the index AND writes, can). STALE refreshes ALWAYS run (a drifted hook is a correctness fix, bounded by
    # the ~88-char hook cap). The DECISION lives HERE, not in a Phase-0 cue, so it holds regardless of whether
    # any cue fired — finishing the v0.1.37 R1 mode (which had the enforcement but left the decision to the
    # model). Escape: --allow-net-grow. Supersedes --refresh-only.
    # v0.1.66 (Phase B): the threshold is the HARD CEILING (INDEX_CEILING_TOKENS), no longer the target
    # budget — an over-TARGET (amber) store now RECEIVES verified knowledge; only a store past the real
    # harm boundary holds. The target gate/standing-justify are a separate, untouched signal
    # (docs/index-usage-and-budget-ladder.spec.md §Phase B — the sibling-signal design).
    # v0.1.73 (accounting truth): the decision itself moved into _plan_pull — classify → plan → execute,
    # one accounting replay that both the write loop and the --evict gain-gate consume, with stale-refresh
    # deltas tracked and `freed` measured from the real index (docs/evict-accounting-truth.spec.md).
    project_dir = project_dir.resolve()
    if not project_dir.is_dir():
        # v0.1.75 defense-in-depth (audit F5) — the CLI choke is _dispatch's guard; direct callers get
        # the same refusal (a phantom store + bogus provenance must be unmintable from any entry point).
        print(f"error: project dir {project_dir} does not exist — refusing (phantom-store guard)", file=sys.stderr)
        return 2
    if pull and evict is not None:
        if not _safe_stem(evict):
            print(f"evict: {evict!r} is not a safe fact name (must match {_SAFE_NAME!r}, no path separators) "
                  "— refusing", file=sys.stderr)
            return 1
        if _is_reserved_stem(evict):
            print(f"evict: '{'/'.join(_RESERVED_STEMS)}' is a reserved index name, not a fact — refusing "
                  "(it would clobber the store's own always-loaded MEMORY.md index)", file=sys.stderr)
            return 1
    from store_context import resolve_store, warn_unenrolled_share, WriteRefused
    from domain_policy import admit_cross_project, fact_domain
    from mirror_conflict import (CONFLICT as _MC_CONFLICT, QUARANTINE as _MC_QUAR,
                                 REFRESH as _MC_REFRESH, RESTAMP as _MC_RESTAMP,
                                 STOP_LOCAL as _MC_STOP, classify_mirror)
    ctx = resolve_store(project_dir)
    _memberships_run: set = _project_memberships(ctx)
    warn_unenrolled_share(ctx)
    if pull:
        life = str(getattr(ctx, "domain_lifecycle", "active") or "active")
        if (ctx.enrolled and ctx.domain_id not in ("", "unknown")
                and life in ("deleting", "deleted")):
            print("pull: domain %s is %s; pull/promote/canonical writes are refused"
                  % (ctx.domain_id, life), file=sys.stderr)
            return 2
    if pull and not getattr(ctx, "cross_project_allowed", False):
        print("pull: local-only (unenrolled or unhealthy registry) — skipping",
              file=sys.stderr)
        return 0
    if pull and not ctx.auto_memory_enabled:
        print("pull: auto-memory is disabled — refusing writes (absence is not drift)", file=sys.stderr)
        return 2
    if pull and not ctx.write_allowed:
        print("pull: StoreContext writes fail closed: " + "; ".join(ctx.ambiguity), file=sys.stderr)
        return 2
    if pull:
        try:
            from control_plane import assert_domain_writable
            assert_domain_writable(ctx)
        except WriteRefused as e:
            print(f"pull: {e}", file=sys.stderr)
            return 2
    store = ctx.native_memory_dir
    mode = "dual-read"
    _tomb_keys: set = set()  # (domain_id, stem) — never a global stem set
    try:
        from control_plane import connect, connect_if_exists, db_path, get_migration_mode
        dbp = db_path(ctx)
        _cp = connect(dbp) if pull else connect_if_exists(dbp)
        if _cp is not None:
            mode = get_migration_mode(_cp)
            for _row in _cp.execute("SELECT stem, domain_id FROM tombstones").fetchall():
                _tomb_keys.add((str(_row["domain_id"] or ""), str(_row["stem"])))
            _cp.close()
    except Exception:
        pass
    stacks, _ = stacks_with_cache(store, project_dir)   # v0.4.2 (P1): cached unless markers moved
    from capabilities import (detect_capabilities, capability_tags,
                              parse_applies, load_capability_overrides)
    from fact_schema import applies_decision as _appl_dec
    _cap_degraded = False
    try:
        _ov = load_capability_overrides(ctx.plugin_data_dir, ctx.project_id)
        _cap_tags = capability_tags(detect_capabilities(
            project_dir, overrides=_ov, cache_dir=ctx.plugin_data_dir,
            project_id=ctx.project_id))
        _rel_tags = stacks | _cap_tags
    except Exception:
        _cap_degraded = True
        _cap_tags = set()
        _rel_tags = stacks
        print("pull: capability detection failed; holding applicability-gated facts",
              file=sys.stderr)
    facts = iter_admissible_facts(ctx)
    man_rows = None
    # P3: the enumeration above already loaded the manifest — consume its stash
    # (same ddir) instead of parsing the 10k-row JSON a second time. A different
    # ddir (or no stash) re-ensures exactly as before.
    if (ctx.canonical_domain_dir.is_dir() and not _global_is_fixture()
            and _MAN_ROWS_STASH.get("ddir") == str(ctx.canonical_domain_dir)):
        man_rows = _MAN_ROWS_STASH.get("rows")
    elif ctx.canonical_domain_dir.is_dir() and not _global_is_fixture():
        try:
            from facts_manifest import ensure as _fm_ensure_r
            man_rows, _man_reason_r = _fm_ensure_r(
                ctx.canonical_domain_dir, ctx.plugin_data_dir)
        except Exception:
            man_rows = None
    _plocks: list = []
    if pull:
        try:
            from control_plane import (acquire_mutation_locks, connect as _cpc,
                                       connect_journal as _cj, db_path as _cpd,
                                       recover_pending, release_locks)
            _locks = acquire_mutation_locks(ctx, [ctx.project_id])
            _jc = _reg = None
            try:
                _jc = _cj(ctx)
                _reg = _cpc(_cpd(ctx))
                recover_pending(_jc, ctx=ctx, registry_conn=_reg)
            finally:
                if _jc is not None:
                    _jc.close()
                if _reg is not None:
                    _reg.close()
                release_locks(_locks)
        except WriteRefused as e:
            print(f"pull: {e}", file=sys.stderr)
            return 2
        except Exception as e:
            print(f"pull: recover failed: {type(e).__name__}: {e}", file=sys.stderr)
            return 2
        from canonical_ingress import ack_tombstoned_mirrors
        _ack = ack_tombstoned_mirrors(ctx)
        if not _ack.get("ok"):
            print("pull: forget-ack refused: " + str(_ack.get("error") or ""),
                  file=sys.stderr)
            return 2

    def _done(rc: int) -> int:
        if _plocks:
            try:
                from control_plane import release_locks as _rl2
                _rl2(_plocks)
            except Exception:
                pass
        return rc
    out: list = []
    add = out.append
    title = "✦ CROSS-PROJECT · " + project_dir.name
    tag = "PULL" if pull else "LIST"
    gap = max(2, _ui.W - 2 - len(title) - len(tag))
    add(_ui.rule())
    add("  " + _ui.c("✦", "cyan") + title[1:] + " " * gap + _ui.c(tag, "bold"))
    add("  " + _ui.c(f"{slug_for(project_dir)} · store {'exists' if store.exists() else 'MISSING — created on pull'}", "dim"))
    add(_ui.rule())
    add("")
    add(_ui.kv("STACKS", (", ".join(sorted(stacks)) if stacks else _ui.c("(none detected)", "dim"))))
    if pull:
        _write_stacks_cache(store, project_dir, stacks)   # v0.1.81: the beacon's stacks cache (script-truth)

    glyphs = {"in-sync": ("✓", "green"), "MISSING": ("↓", "yellow"), "STALE-mirror": ("⟳", "yellow"),
              "present(local)": ("•", "cyan"), "irrelevant": ("·", "dim"), "frozen(mirror)": ("✻", "yellow")}
    rows: list = []
    relevant = pulled = refreshed = held = fat = 0   # fat: v0.1.66 — pointers written over HOOK_TOKEN_WARN
    restamped = 0   # v0.1.78: STALE refreshes of PRE-STAMP mirrors — the one-time evidence-clock migration wave
    # v0.1.73 (accounting truth — docs/evict-accounting-truth.spec.md): CLASSIFY first (no writes),
    # PLAN the index accounting ONCE via _plan_pull, THEN execute — the write loop consults plan
    # membership and never re-decides. Seed from the live index (store-scan convention, v0.1.69
    # Gate-2b); cost_old per stem is the REAL existing line (_index_line_cost), so a stale-refresh
    # delta and a line-without-file drift state both net honestly instead of slipping the ceiling.
    _idxp = store / "MEMORY.md"
    idx_text = _safe_read_text(_idxp) or "# Memory Index\n\n"
    _is_fixture_run = _global_is_fixture()
    _hermetic_run = _hermetic_home()
    _ddir_s = str(ctx.canonical_domain_dir)
    seed_idx = est_tokens(idx_text)
    # P3 (v0.4.2 warm-pull margin): run-local memos keyed on the RAW strings — a fleet's canonicals
    # share `stacks:`/`applies:` lines, and a 10k-canonical pull re-parses them all per fact. The
    # applies decision depends only on those raw fields plus the run-constant (_rel_tags,
    # _cap_degraded), so the memo key is exactly what parse_applies/applies_decision read.
    # `_hold_state` is ONE lazily-opened read-only registry conn for the loop's holder-base lookups
    # (today: a fresh connect per STALE-mirror item); any failure sets `dead` and every later lookup
    # degrades to None — the same behavior a per-item connect failure had. Never reused for the
    # write conn (the write path opens its own inside transact).
    _stacks_memo: dict = {}
    _appl_memo: dict = {}
    _hold_state: dict = {"conn": None, "dead": False}

    def _hold_base_for(fid_w: str):
        if _hold_state["dead"]:
            return None
        _conn_hb = _hold_state["conn"]
        if _conn_hb is None:
            try:
                from control_plane import connect_if_exists as _cife_h, db_path as _dbp_h
                _conn_hb = _cife_h(_dbp_h(ctx))
            except Exception:
                _hold_state["dead"] = True
                return None
            _hold_state["conn"] = _conn_hb
        if _conn_hb is None:
            return None
        try:
            from control_plane import holder_base_revision as _hbr
            return _hbr(_conn_hb, fid_w, ctx.project_id)
        except Exception:
            return None

    classified: list = []   # (name, fm, text, status, path, want, rel, _fast, _r_man, _rev_w)
                            # the last three are CARRIED per item — the pull-jobs loop below re-reads
                            # them per item, and a leftover local would pair an in-sync fact with the
                            # WRONG manifest row / semantic hash (the P3 carry fix, v0.4.2)
    conflict_ops: list = []
    try:
        for name, fm, text in facts:
            # v0.4.10 group-scopes: the record's SOURCE domain + mirror key —
            # cross-domain group facts get namespaced keys and record-derived
            # provenance everywhere below (spec §5-A/B).
            sdom = fact_domain(fm) or (ctx.domain_id or "")
            try:
                mkey = _mirror_key(ctx.domain_id, sdom, name)
            except ValueError as e:
                print(f"  pull: {e}", file=sys.stderr)
                continue
            _rec_groups = _parse_flow_list(str(fm.get("recipients") or ""))
            rel = is_relevant(fm, _rel_tags, stacks_memo=_stacks_memo)
            # P3: the applies-decision memo — keyed on the raw fields parse_applies reads
            # (including the nested-error keys and the stacks fallback); _rel_tags and
            # _cap_degraded are run-constants. The memo carries (decision, explicit-applies)
            # where the explicit flag tests the PARSED forms (the raw strings are the KEY
            # only — the schema-default `applies_any: []` literal parses EMPTY and must
            # not read as explicit gating).
            _raw_aa = str(fm.get("applies_any") or "")
            _raw_al = str(fm.get("applies_all") or "")
            _raw_ax = str(fm.get("applies_exclude") or "")
            _dec_key = (_raw_aa, _raw_al, _raw_ax,
                        str(fm.get("applies.any") or ""), str(fm.get("applies.all") or ""),
                        str(fm.get("applies.exclude") or ""), str(fm.get("stacks") or ""))
            _dec_hit = _appl_memo.get(_dec_key)
            if _dec_hit is None:
                _appl_parsed = parse_applies(fm)
                _dec_ap = _appl_dec(_appl_parsed, _rel_tags, degraded=_cap_degraded)
                # the EXPLICIT-applies flag tests the PARSED forms — the schema-default
                # literal `applies_any: []` is the raw string "[]" (non-empty raw, EMPTY
                # parsed): raw-presence testing made an ungated fleet-dead canonical read
                # as explicitly gated and replicate into every same-domain index (P3
                # review, MED).
                _expl = bool(_appl_parsed.get("any") or _appl_parsed.get("all")
                             or _appl_parsed.get("exclude"))
                _appl_memo[_dec_key] = (_dec_ap, _expl)
            else:
                _dec_ap, _expl = _dec_hit
            if _dec_ap == "unknown":
                rel = False
            elif _dec_ap == "no-match":
                rel = False
            elif _dec_ap == "match" and fm.get("scope") == "stack-general" and _expl:
                rel = True
            path = store / f"{mkey}.md"
            present = path.exists()
            cur = (_safe_read_text(path) or "") if present else ""   # store-scan convention (v0.1.69 Gate-2b)
            is_mirror = present and _is_mirror(cur)
            # Phase-5 closeout: the manifest-served in-sync fast path. `text is None`
            # means _admissible_records served a fresh manifest row — decide in-sync
            # from the mirror's stamps + the cached semantic hash (the SAME equality
            # classify_mirror trusts: semantic_payload equality). Any miss re-reads
            # the body and runs today's path verbatim (statuses bit-identical).
            _fast = False
            _cur_fm_f = None
            if text is None:
                _r_man = (man_rows or {}).get(name) if man_rows is not None else None
                if _r_man is not None and is_mirror:
                    _rfresh = False
                    try:
                        _stc_man = os.stat(os.path.join(
                            str(ctx.canonical_domain_dir), name + ".md"))
                        _rfresh = (_stc_man.st_mtime_ns == int(_r_man.get("mtime_ns") or -1)
                                   and _stc_man.st_size == int(_r_man.get("size") or -1)
                                   and _stc_man.st_ctime_ns == int(_r_man.get("ctime_ns") or -1))
                    except OSError:
                        _rfresh = False
                    if _rfresh:
                        from mirror_conflict import semantic_hash as _semh_fast
                        _cur_fm_f = _frontmatter(cur)
                        if (_cur_fm_f.get("global_ref_body") == _r_man.get("body_hash")
                                and str(_cur_fm_f.get("global_ref_since") or "")
                                and _parse_ts(str(_cur_fm_f.get("global_ref_since") or "")) is not None
                                and _semh_fast(cur) == _r_man.get("sem")):
                            _fast = True
                if not _fast and present:
                    # a present mirror's body is needed NOW (in-sync/want compare)
                    text = _safe_read_text(_source_facts_dir(ctx, sdom) / f"{name}.md")
                    if text is None:
                        rel = False
                        text = ""
                # Phase-5 closeout: a MISSING fact's body is needed only if the PLAN actually
                # pulls it — at 10k canonicals ~9.9k are held by the index cap, and reading them
                # all was the 5.8s pull. Defer the read to the pull_jobs construction (below).
            if _fast or (not text):
                new_hash = ""
                _rev_w = ""
                want = None if not _fast else ""
                # P3: reuse the fast-path's parse (the unconditional _frontmatter(cur)
                # here was the THIRD parse of the same mirror text per warm pull);
                # nothing downstream reads cur_fm in this arm.
                cur_fm = _cur_fm_f or {}
                since = ""
                _migrated = False
            else:
                # v0.1.78 evidence-clock carry (docs/evidence-clock-stamps.spec.md): same body as the current
                # mirror → CARRY its since (a description/stacks/provenance tweak refreshes the text without
                # wiping the fleet's accrued zero-read windows — the audit's F9 starvation, measured 1→0 on a
                # description-only edit); legacy/garbled stamps but same body → seed from the file's mtime
                # (the migration wave — never restart the fleet's evidence from zero); body genuinely changed
                # (or a fresh pull) → NEW lineage (old zero-reads don't indict new content).
                new_hash = _body_hash(text)
                _migrated = False   # took the mtime-seeded branch (the honest referent of `restamped` — review #91)
                if is_mirror:
                    cur_fm = _frontmatter(cur)
                    cur_since = str(cur_fm.get("global_ref_since", "") or "")
                    if cur_fm.get("global_ref_body", "") == new_hash and cur_since and _parse_ts(cur_since) is not None:
                        since = cur_since
                    elif _body_hash(cur) == new_hash:
                        since = _mtime_iso(path)
                        _migrated = True
                    else:
                        since = _now_iso()
                else:
                    cur_fm = {}
                    since = _now_iso()
                from control_plane import stable_fact_id as _sfid_w
                _fid_w = _sfid_w(sdom, name)
                want = _as_mirror(text, name, since=since, body_hash=new_hash,
                                  fact_id=_fid_w, domain=sdom,
                                  groups=_rec_groups)
                from mirror_conflict import semantic_hash as _semh_w, stamp_revisions as _stamp_w
                _rev_w = _semh_w(text)
                want = _stamp_w(want, _rev_w, _rev_w)
                if is_mirror:
                    _m_at = re.search(r"(?m)^[ \t]*mirrored_at:\s*(\S+)", cur)
                    _cur_m = _m_at.group(1) if _m_at else str(cur_fm.get("mirrored_at") or "")
                    if _cur_m and "mirrored_at:" not in want and "  global_ref:" in want:
                        want = want.replace("  global_ref:", f"  mirrored_at: {_cur_m}\n  global_ref:", 1)
                if "mirrored_at:" not in want and "  global_ref:" in want:
                    want = want.replace("  global_ref:", f"  mirrored_at: {_now_iso()}\n  global_ref:", 1)
                if _migrated and not _frontmatter(want).get("global_ref_since"):
                    # PR-#91 adversarial F2a: a no-metadata-block mirror (the `# global_ref:` fallback form)
                    # can never receive the stamp — without this, EVERY refresh of such a mirror reported
                    # "restamped 1" forever while global_ref_since stayed absent. A migration that didn't
                    # happen must not be reported as one; the mirror stays on the documented mtime fallback.
                    _migrated = False
            _fdom = sdom
            _adm_fm = dict(fm)
            if (_is_fixture_run or _hermetic_run) and not fact_domain(fm) and ctx.domain_id not in ("", "unknown"):
                _adm_fm["domain"] = ctx.domain_id
            if str(fm.get("status") or "") in ("tombstoned", "superseded", "expired") or (_fdom, name) in _tomb_keys:
                rel = False
            elif rel and not admit_cross_project(ctx.domain_id, _adm_fm, migration_mode=mode,
                                                memberships=_memberships_run,
                                                group_recips=set(_rec_groups)):
                rel = False
            if not rel:
                # v0.1.75 (audit F6): a PRESENT mirror whose canonical is alive but no longer relevant here
                # (a dropped stack) is FROZEN — never refreshed (this branch short-circuits staleness), never
                # gc'd as an orphan (canonical exists), still taxing the always-loaded index. Render it
                # DISTINCTLY (it used to read as a plain 'irrelevant', byte-identical to never-pulled) so the
                # operator can see it; the reclaim lever is --gc's FROZEN section (report + --apply).
                status = "frozen(mirror)" if present and is_mirror else "irrelevant"
            elif not present:
                status = "MISSING"
            elif not is_mirror:
                status = "present(local)"  # project-authored — never clobber
            elif _fast:
                status = "in-sync"
            elif cur == want:
                status = "in-sync"
            else:
                # Three-way (ADR 005/011): holder-table base under lock is authoritative.
                # Mirror frontmatter base_revision is not trusted.
                # P3: the lookup shares ONE lazily-opened read-only conn across the loop
                # (today: a fresh connect per STALE-mirror item — 10k canonicals × N stale).
                _hold_base = _hold_base_for(_fid_w)
                if not _hold_base:
                    # bootstrap (F1): a cross-domain mirror pulled before the
                    # provenance fix has no recorded holder base — its OWN
                    # canonical_revision is the revision it sits at.
                    _hold_base = str(cur_fm.get("canonical_revision") or "") or None
                _v3m = bool(cur_fm.get("canonical_fact_id") or cur_fm.get("schema_version"))
                _dec = classify_mirror(cur, text, base_revision=_hold_base,
                                       allow_legacy_fallback=not _v3m)
                _act = _dec["action"]
                if _act in (_MC_REFRESH, _MC_RESTAMP):
                    status = "STALE-mirror"
                elif _act == _MC_STOP:
                    status = "local-edit"
                elif _act == _MC_QUAR:
                    status = "quarantine"
                else:
                    status = "CONFLICT"
                if pull and _act in (_MC_STOP, _MC_CONFLICT, _MC_QUAR):
                    conflict_ops.append({
                        "op": "conflict_upsert",
                        "stem": name, "fact_stem": name,
                        "project_id": ctx.project_id,
                        "action": _act,
                        "local_hash": _dec.get("local"),
                        "canonical_hash": _dec.get("canonical"),
                        "domain_id": getattr(ctx, "domain_id", "") or "",
                        "fact_id": _fid_w,
                    })
            if pull and status == "STALE-mirror" and _migrated:
                # counts ONLY the mtime-seeded migrations (PR-#91 review: the old not-yet-stamped gate also
                # counted a legacy mirror whose canonical BODY changed this same pass — branch 3, seeded from
                # NOW — making the RESULT's "seeded from each mirror's mtime" clause dishonest for that subset;
                # a body-changed legacy mirror is a genuine content refresh, reported as plain `refreshed`).
                restamped += 1
            classified.append((name, fm, text, status, path, want, rel,
                               _fast, _r_man if _fast else None, _rev_w))
    finally:
        if _hold_state["conn"] is not None:
            _hold_state["conn"].close()
    # v0.1.75 (audit F7 — the M4-bypass SURFACE): promote() refuses an undetectable `stacks:` tag, but the
    # SKILL's documented Phase-4 NET-NEW path hand-writes canonicals directly — a typo'd ('gpuu') or
    # real-but-undetectable ('release') tag lands unvalidated, and the canonical is FLEET-DEAD:
    # is_relevant can never match it to ANY project, silently, forever. Every dream's Phase 1 walks this
    # read path, so warn HERE (report-only, never a block) — the loop-native surface for the bypass.
    for _fn, _ffm, _t, _s, _p, _w, _r, *_x in classified:
        if _ffm.get("scope") == "stack-general":
            _fs = _memo_fact_stacks(_ffm, _stacks_memo)
            _bad = sorted(_fs - _DETECTABLE_STACKS)
            if not (_fs & _DETECTABLE_STACKS):
                # NO detectable tag at all (empty, or all-undetectable) → genuinely fleet-dead
                _why = f"undetectable stack tag(s) {_bad}" if _bad else "NO `stacks:` tags at all"
                print(f"  ⚠ fleet-dead canonical: '{_fn}' is stack-general with {_why} — detect_stacks can "
                      f"never match it to any project. Retag with a detectable stack "
                      f"({sorted(_DETECTABLE_STACKS)}), re-scope user-global, or demote it "
                      f"(~/.claude/memory/{_fn}.md).", file=sys.stderr)
            elif _bad:
                # train-review F-B: MIXED tags (e.g. [python, fastpai]) are NOT fleet-dead — the fact
                # still matches via its detectable tag(s); the old blanket "can never match any
                # project" wording was false here. The undetectable tag is dead weight worth cleaning.
                print(f"  ⚠ undetectable stack tag(s) {_bad} on '{_fn}' — dead weight (the fact still "
                      f"matches via {sorted(_fs & _DETECTABLE_STACKS)}); clean the tags "
                      f"(~/.claude/memory/{_fn}.md).", file=sys.stderr)
    # Phase-5 closeout: hoist the anchor→cost map ONCE (the per-stem
    # _index_line_cost re-split the whole index every call — O(relevant ×
    # index_bytes); the beacon already hoists the same map).
    _line_cost_run: dict = {}
    for _ln in idx_text.splitlines():
        _m = re.search(r"\]\(([^)]+)\.md\)", _ln)
        if _m and _m.group(1) not in _line_cost_run:
            _line_cost_run[_m.group(1)] = est_tokens(_ln)
    items = [(name, status, est_tokens(_pointer_line(name, fm)), _line_cost_run.get(name, 0))
             for name, fm, _t, status, _p, _w, rel, *_x in classified
             if rel and status in ("MISSING", "STALE-mirror")]
    plan = _plan_pull(items, seed_idx, allow_net_grow, budget=INDEX_CEILING_TOKENS)
    # v0.1.41 → v0.1.73: --evict <fact> — the EVICT-TO-RECEIVE valve (the release for M1's hold),
    # rebuilt on measured accounting. Pre-checks BEFORE any delete (Guard-3 no-partial-state); the
    # swap gate is an A/B REPLAY of the actual pull plan, so acceptance and outcome cannot diverge
    # the way the old static held_pre pre-scan did. The agent NAMES the fact (report-then-apply).
    if pull and evict is not None:
        if not _safe_stem(evict):    # v0.1.70 security: same charset guard promote() applies to local_fact/canon_name
            print(f"evict: {evict!r} is not a safe fact name (must match {_SAFE_NAME!r}, no path separators) "
                  "— refusing", file=sys.stderr); return _done(1)
        if _is_reserved_stem(evict):  # Gate-2a: the charset guard alone still let 'MEMORY' through —
            # store / 'MEMORY.md' IS the live index (_idxp above); unlink()'ing it and rebuilding from
            # scratch silently drops every previously-indexed pointer (mirrors AND project-authored
            # locals) with rc=0 and no error. Same reserved-name guard promote() already applies.
            print(f"evict: '{'/'.join(_RESERVED_STEMS)}' is a reserved index name, not a fact — refusing "
                  "(it would clobber the store's own always-loaded MEMORY.md index)", file=sys.stderr); return _done(1)
        ep = store / f"{evict}.md"
        if not ep.exists():
            print(f"evict: no local fact '{evict}' in {store}", file=sys.stderr); return _done(1)
        _ep_text = _safe_read_text(ep)   # v0.1.69 Gate-2b: TOCTOU since the ep.exists() check above —
        if _ep_text is None:              # a vanished evict target refuses cleanly, same as "not present"
            print(f"evict: '{evict}' vanished from {store} — refusing (nothing to evict)", file=sys.stderr); return _done(1)
        if _is_mirror(_ep_text):
            # v0.1.73 (F1, measured): a mirror of a live relevant canonical re-pulls into the freed
            # room THIS same pass (or oscillates held forever) — a destructive op that gains nothing.
            print(f"evict: '{evict}' is a managed MIRROR (global_ref) — evicting it is self-defeating "
                  "(the live canonical re-pulls into the freed room this same pass). The lever for a "
                  "mirror is the GLOBAL store: demote/delete the canonical (then --gc --apply), or "
                  "tighten its description.", file=sys.stderr); return _done(1)
        inbound = _inbound_links(store, evict)
        if inbound:
            print(f"evict: '{evict}' is [[linked]] by {inbound} — evicting it would ORPHAN those links. "
                  "Pick another fact, or de-link first.", file=sys.stderr); return _done(1)
        if not plan["held"]:
            # under --allow-net-grow nothing is ever held → this refuses ("nothing to receive")
            # rather than a gratuitous delete-then-pull-all — the pre-v0.1.73 behavior, kept.
            print(f"evict: nothing is held (no past-the-ceiling MISSING globals) — evicting '{evict}' would free "
                  "room for NOTHING. There is no swap to make.", file=sys.stderr); return _done(1)
        freed = _index_line_cost(idx_text, evict)   # MEASURED from the live index — never derived (F2)
        if freed == 0:
            print(f"evict: '{evict}' has no pointer line in the live index — evicting it frees NOTHING "
                  "(freed is MEASURED from MEMORY.md, never derived from frontmatter). Pick an indexed fact.",
                  file=sys.stderr); return _done(1)
        plan_evict = _plan_pull(items, seed_idx - freed, allow_net_grow, budget=INDEX_CEILING_TOKENS)
        gain = [n for n in plan_evict["pull"] if n not in set(plan["pull"])]
        displaced = [n for n in plan["pull"] if n not in set(plan_evict["pull"])]
        if len(plan_evict["pull"]) <= len(plan["pull"]):
            # Guard-3 is a COUNT (train-review F-A, HIGH, verified E2E): the old set-difference test
            # accepted a LATERAL SWAP — freeing room let an alphabetically-earlier, larger-pointer
            # global jump into the plan and push a later, smaller one over the ceiling, so `gain` was
            # non-empty while the pull COUNT was unchanged (or lower) and the authored fact was
            # destroyed for zero net gain — the exact F3 harm this gate exists to refuse, re-admitted.
            # The destruction must land strictly MORE globals than no-evict would.
            _swap = (f" — a lateral swap (+{', '.join(gain)} / −{', '.join(displaced)}), not a gain"
                     if gain else "")
            print(f"evict: destroying '{evict}' (~{freed} tok measured) lands NO additional held global — "
                  f"the replayed plan pulls {len(plan_evict['pull'])} ({', '.join(plan_evict['pull']) or 'none'}) "
                  f"with the evict vs {len(plan['pull'])} ({', '.join(plan['pull']) or 'none'}) without{_swap}; "
                  f"held either way: {', '.join(n for n, _c in plan_evict['held'])}. "
                  "Refusing a destructive op that gains nothing — pick a larger-pointer fact.",
                  file=sys.stderr); return _done(1)
        if displaced:
            # count strictly increased but the composition shifted — proceed, and say so honestly
            print(f"  ⚠ evict replan displaced {', '.join(displaced)} (freed room re-ordered the pulls; "
                  f"net {len(plan_evict['pull'])} land vs {len(plan['pull'])} without the evict)", file=sys.stderr)
        _evict_stem = evict
        _evict_path = ep
        plan = plan_evict   # the gate approved THIS plan; transact below executes exactly it
        print(f"  ✓ evicted '{evict}' (~{freed} tok freed, measured) → lands: {', '.join(gain)}", file=sys.stderr)
    else:
        _evict_stem = None
        _evict_path = None
    pulled_set = set(plan["pull"])
    held_facts: list = plan["held"]   # (name, cost) — drives the RESULT line + the evict-to-receive offer
    pull_jobs: list = []
    in_sync_names: list = []
    _sem_map: dict = {}
    for name, fm, text, status, path, want, rel, _fast_i, _r_man_i, _rev_w_i in classified:
        sdom = str(fm.get("domain") or ctx.domain_id or "")   # per-record (group-scopes)
        g, col = glyphs.get(status, ("·", "dim"))
        rows.append(f"    {_ui.c(g, col)} {_ui.lbl(f'{status:<14}')}{name}  " + _ui.c(f"({fm.get('scope', '?')})", "dim"))
        if rel:
            relevant += 1
        # M1 → v0.1.73: the hold decision is the PLAN's (single source — _plan_pull replayed the loop's
        # own accumulating accounting; a relevant MISSING fact not in plan["pull"] was held there, past
        # the HARD CEILING). `held_this` gates BOTH the write-skip and the provenance record (a held
        # fact is NOT held by this project).
        held_this = pull and rel and status == "MISSING" and name not in pulled_set
        if held_this:
            held += 1  # past-the-ceiling net-grow → hold (shrink to receive, or --allow-net-grow) — v0.1.66
        elif pull and rel and status in ("MISSING", "STALE-mirror"):
            if want is None:
                # deferred MISSING body — read it now that the plan pulled it
                text = _safe_read_text(_source_facts_dir(ctx, sdom) / f"{name}.md")
                if text is None:
                    rows.append(f"    {_ui.c('↓', 'yellow')} {_ui.lbl(f'{status:<14}')}{name}  "
                                f"{_ui.c('(unreadable — skipped)', 'dim')}")
                    continue
                from control_plane import stable_fact_id as _sfid_d
                from mirror_conflict import semantic_hash as _semh_d, stamp_revisions as _stamp_d
                _rev_d = _semh_d(text)
                want = _stamp_d(_as_mirror(
                    text, name, since=_now_iso(), body_hash=_body_hash(text),
                    fact_id=_sfid_d(sdom, name), domain=sdom,
                    groups=_parse_flow_list(str(fm.get("recipients") or ""))),
                    _rev_d, _rev_d)
                if "mirrored_at:" not in want and "  global_ref:" in want:
                    want = want.replace("  global_ref:", f"  mirrored_at: {_now_iso()}\n  global_ref:", 1)
            # C3: a canonical with an INVALID originSessionId fans its gap out to every mirror this
            # replication creates. WARN (don't block — the fact is still useful); reuses the in-hand
            # `fm`, no extra I/O. v0.1.76 (audit): ABSENCE no longer warns — harness-map's schema
            # rules say a git/commit-derived fact legitimately OMITS originSessionId (absence is an
            # optional-backfill advisory, never drift), so the old warn-on-absent was steady stderr
            # noise on every replication of every legitimate git-derived canonical.
            _osid = fm.get("originSessionId", "")
            if _osid and not _valid_uuid(_osid):
                print(f"  ⚠ canonical {name} has an INVALID originSessionId ({_osid[:24]!r}) — the gap "
                      "fans out to every mirror", file=sys.stderr)
            pull_jobs.append((name, fm, status, path, want))
        if pull and rel and status == "in-sync" and not held_this:
            in_sync_names.append(name)
            _sem_map.setdefault(name, _r_man_i if _fast_i else {"sem": _rev_w_i or ""})
    if pull and (pull_jobs or _evict_stem or in_sync_names or conflict_ops):
        from control_plane import CrashSimulated as _CrashPull
        try:
            _w = _execute_pull_writes(ctx, store, pull_jobs, _evict_stem, _evict_path,
                                      holder_token=project_dir.name,
                                      in_sync_names=in_sync_names,
                                      conflict_ops=conflict_ops,
                                      sem_by_name=_sem_map)
        except _CrashPull:
            print("pull: crash-after journal step (pending op left for recover)", file=sys.stderr)
            return _done(1)
        pulled = int(_w.get("pulled") or 0)
        refreshed = int(_w.get("refreshed") or 0)
        fat = int(_w.get("fat") or 0)
    add(_ui.kv("FACTS", f"{len(facts)} global · {relevant} relevant to this project"))
    out.extend(rows)
    add("")
    held_note = f" · held {held} (would push the index past the HARD CEILING ≈{INDEX_CEILING_TOKENS} tok — shrink to receive, or --allow-net-grow)" if held else ""
    fat_note = f" · ⚠ {fat} fat hook(s) >{HOOK_TOKEN_WARN}t written (tighten the canonical descriptions)" if fat else ""
    restamp_note = (f" · restamped {restamped} (evidence-clock stamps added; lineage seeded from each "
                    "mirror's mtime — one-time upgrade wave, not churn)") if restamped else ""
    tail = (f"pulled {pulled} new · refreshed {refreshed} stale{held_note}{restamp_note}{fat_note} (index updated)" if pull
            else "run with --pull to replicate MISSING + refresh STALE mirrors here")
    add(_ui.kv("RESULT", tail))
    _n_frozen = sum(1 for _n2, _f2, _t2, _s2, _p2, _w2, _r2, *_x in classified if _s2 == "frozen(mirror)")
    if _n_frozen:
        add("  " + _ui.c(f"✻ {_n_frozen} frozen mirror(s) — canonical alive but IRRELEVANT here (a dropped "
                         "stack): never refreshed, still taxing the always-loaded index. --gc reports them; "
                         "--gc --apply reclaims (safe — re-pullable if the stack returns)", "yellow"))
    # v0.1.41 → v0.1.73: the EVICT-TO-RECEIVE offer (the report half of report-then-apply). When globals are
    # HELD, surface the held + the evictable AUTHORED pointers with RAW, UNORDERED metadata — NEVER ranked
    # (a staleness/mtime rank actively misleads: a foundational fact is untouched yet vital). Mirrors are
    # never offered (F1 — evicting one self-defeats; their lever is the GLOBAL store), and each candidate's
    # cost is MEASURED from its real index line post-write (F2 — a derived pointer estimate lied both ways).
    # The agent judges which to evict; --evict then applies it orphan-safe + gain-gated. A scalpel, not auto-eviction.
    if held and store.is_dir():
        add("")
        add("  " + _ui.c("EVICT-TO-RECEIVE", "bold") + _ui.c(f"   · {held} held — free ONE low-value pointer to land a held global (net-neutral)", "dim"))
        add("    held: " + _ui.c(", ".join(f"{n} (~{c}t)" for n, c in held_facts), "yellow"))
        add("    " + _ui.c("evictable AUTHORED pointers (raw metadata, UNORDERED — YOU judge value, never auto-ranked;", "dim"))
        add("    " + _ui.c(" mirrors are never offered — their lever is the GLOBAL store, not a local delete):", "dim"))
        _idx_now = _safe_read_text(_idxp) or ""   # re-read: the loop above just rewrote pointers
        for f in sorted(store.glob("*.md")):
            if f.name == "MEMORY.md" or _is_reserved_stem(f.stem):
                continue
            t = _safe_read_text(f)                # store-scan convention (a concurrent gc/chmod between
            if t is None or _is_mirror(t):        # glob+read must not abort the offer; mirrors refused as evictees
                continue
            ffm = _frontmatter(t)
            _lc = _index_line_cost(_idx_now, f.stem)
            add("      " + _ui.c(f"· {f.stem:<40} {ffm.get('scope', '?'):<14} "
                                 f"{f'~{_lc}t line (measured)' if _lc else 'unindexed (frees 0 — refused)'}", "dim"))
        add("    " + _ui.c("→ sync_global.py --pull --evict=<fact> .   (refuses a mirror, an orphaning, an unindexed, or a GAINLESS evict; never auto-deletes)", "dim"))
    print(_ui.ascii_translate("\n".join(out)))
    if _plocks:
        from control_plane import release_locks as _rl
        _rl(_plocks)
    return 0


def apply_provenance(text: str, project: str) -> str:
    """Strip canonical `projects:` (SQLite holders are authoritative, P1-6).

    `project` is accepted for call-site compatibility and ignored. Pull/promote
    still call this inside transact so leftover Markdown lists are removed.
    """
    del project
    if not str(text or "").startswith("---"):
        return text
    out: list = []
    dashes = 0
    for i, ln in enumerate(text.splitlines()):
        s = ln.strip()
        if dashes == 0 and i == 0 and ln == "---":
            dashes = 1
            out.append(ln)
            continue
        if dashes == 1 and ln.startswith("---"):
            dashes = 2
            out.append(ln)
            continue
        if dashes == 1 and s.startswith("projects:"):
            continue
        out.append(ln)
    return "\n".join(out) + ("\n" if text.endswith("\n") else "")


def _registry_holder_labels(ctx, stem: str, fact_dom: str = ""):
    """Tri-state: None = registry unavailable, [] = authoritative zero, [..] = labels.

    `fact_dom` is the FACT's own domain — the holders table stores the fid under
    the fact's domain at write time, and a cross-domain fact (group bridge) held
    from ctx's store would otherwise resolve under the WRONG fid (the fleet
    dogfood measured it: 1 holder reported where 10 existed)."""
    if ctx is None or not stem:
        return None
    try:
        from control_plane import connect_if_exists, db_path, stable_fact_id
        conn = connect_if_exists(db_path(ctx))
        if conn is None:
            return None
        try:
            fid = stable_fact_id(fact_dom or getattr(ctx, "domain_id", "") or "unknown", stem)
            rows = conn.execute(
                "SELECT COALESCE(p.display_name, h.project_id) AS label "
                "FROM holders h LEFT JOIN projects p ON p.project_id = h.project_id "
                "WHERE h.fact_id=?",
                (fid,),
            ).fetchall()
            out: list = []
            seen: set = set()
            for r in rows:
                lab = str(r["label"] or "").strip()
                if lab and lab not in seen:
                    seen.add(lab)
                    out.append(lab)
            return out
        finally:
            conn.close()
    except Exception:
        return None


def _holder_labels(fm: dict, *, stem: str = "", ctx=None) -> list:
    """SQLite is the sole operational holder authority (ADR 023).

    Unavailable registry → Markdown `projects:` as migration input only.
    Authoritative zero (`[]`) does not fall through to Markdown.
    """
    from domain_policy import fact_domain
    _fdom = fact_domain(fm) or (getattr(ctx, "domain_id", "") if ctx is not None else "")
    got = _registry_holder_labels(ctx, stem, _fdom)
    if got is None:
        return _holders(fm)
    return got


def _holders(fm: dict) -> list[str]:
    # v0.1.76 (audit): parse the SAME token space _sanitize_token WRITES. The old alnum-first-char
    # regex silently shortened a dot/dash-prefixed holder ('.claude' → 'claude'; the sanitized
    # '-scope' from '@scope' → 'scope'), so gc's dead-edge compare could never match such a project
    # and network()/--utility displayed a name provenance doesn't hold. Tokens must still carry ≥1
    # alnum (a bare '-'/'.' is separator noise, not a holder); single-character names still kept.
    return [t for t in re.findall(r"[A-Za-z0-9._-]+", fm.get("projects", ""))
            if any(c.isalnum() for c in t)]


def _slug_matches(name: str) -> "list[Path]":
    """v0.1.84 (P4, docs/provenance-liveness.spec.md): the STORE dirs under ~/.claude/projects
    that plausibly match a provenance basename — the honest partial inverse of the lossy slug.
    Normalize in SLUG space (every non-alnum → '-', the slug_for rule — the train-review F1
    lesson: _sanitize_token preserves '_'/'.' while slug dirs map them to '-', so Doc_Flo could
    never match its own store) and match by equality or '-'-suffix. Only dirs that actually HOLD
    a memory store count (a bare transcript dir is not a node). Degenerate token / no projects
    dir → [] with the CALLER deciding conservatively. The ONE resolver — _mind_unresolved and
    the P4 edge classifier both delegate here (a second copy is how the F1 bug happened).
    REACH LIMIT (PR-#97 review F2, accepted — the lossy slug's cost): the `-`-suffix match
    over-matches — a ghost token `memory` suffix-collides with a live `…-consolidate-memory`
    store. This only ADDS matches, so it can NEVER produce a false `unresolved` → never a wrong
    prune (the safe direction); its sole effect is `fleet_tax_live` crediting a ghost edge as live
    (advisory, printed beside — never replacing — the upper bound). Tightening it would break the
    load-bearing lossy inverse (holder `Doc_Flo` → `-…-Doc-Flo` NEEDS the suffix match), so this
    is left as an accepted reach limit, exactly like the slug's other documented lossy cases."""
    norm = re.sub(r"[^a-z0-9]", "-", name.lower())
    if not norm.strip("-."):
        return []
    out: list = []
    seen: set = set()

    def add(p: Path) -> None:
        if not p.is_dir():
            return
        key = _path_key(p)
        if key in seen:
            return
        seen.add(key)
        out.append(p)

    def slot_hit(slot: str) -> bool:
        s = slot.lower()
        return s == norm or s.endswith("-" + norm)

    base = _projects_root()
    if base.is_dir():
        try:
            kids = sorted(base.iterdir())
        except OSError:
            kids = []
        for d in kids:
            if slot_hit(d.name) and (d / "memory").is_dir():
                add(d / "memory")
    for rec in _registry_project_rows():
        native = Path(rec.get("native_memory_dir") or "")
        if not native:
            continue
        slot = Path(rec.get("session_dir") or "").name
        disp = re.sub(r"[^a-z0-9]", "-", str(rec.get("display_name") or "").lower())
        if slot_hit(slot) or disp == norm or disp.endswith("-" + norm):
            add(native)
    return out


def _mind_unresolved(name: str) -> bool:
    """v0.1.76 (audit): True iff NO slug dir plausibly matches this provenance basename.
    CONSERVATIVE: any match — including an ambiguous one — reads as resolved; a degenerate token
    also reads resolved (nothing claimable ≠ ghost). Display-only (the `?` glyph + footnote in
    network()); never a prune input. v0.1.84: delegates to _slug_matches (the ONE resolver; the
    prune-capable classifier is _classify_edge, stricter by design)."""
    if not re.sub(r"[^a-z0-9]", "-", name.lower()).strip("-."):
        return False   # degenerate token — nothing claimable; stay conservative
    return not _slug_matches(name)


def _classify_edge(holder: str, stem: str, domain_id: str = "") -> str:
    """v0.1.84 (P4): classify ONE provenance edge (holder token × canonical stem) —
      'live'       ≥1 matching store holds <stem>.md as a managed MIRROR (it pays the pointer tax);
      'stale'      exactly one match, mirror absent (real project, dropped mirror — NEVER prunable:
                   self-identifying, and _record_provenance re-adds on its next pull anyway);
      'unresolved' ZERO store matches — NO live memory STORE resolves (PR-#97 review F3: this means
                   store-DELETED, not merely project-renamed — a provenance holder had a store BY
                   CONSTRUCTION since run() mkdir's before _record_provenance, so no-store = deleted =
                   correctly dead); the ghost class, measured live at 21% of edges / 20% of fleet tax;
                   the ONLY prunable class, and only via the confirmed --gc --edges --apply;
      'ambiguous'  multiple matches, none holding (can't tell which store was meant), OR a
                   degenerate token (a token we can't even normalize is not PROVABLY a ghost) —
                   conservative, never prunable.
    `domain_id` scopes liveness to that domain's mirrors (same stem in another
    domain is not live for this canonical)."""
    if not re.sub(r"[^a-z0-9]", "-", holder.lower()).strip("-."):
        return "ambiguous"
    stores = _slug_matches(holder)
    if not stores:
        return "unresolved"
    holding = []
    want = str(domain_id or "").strip()
    for s in stores:
        t = _safe_read_text(s / f"{stem}.md")
        if t is None or not _is_mirror(t):
            continue
        if want:
            fm = _frontmatter(t)
            d = str(fm.get("canonical_domain") or fm.get("domain") or "").strip()
            if d and d != want:
                continue
        holding.append(s)
    if holding:
        return "live"
    return "stale" if len(stores) == 1 else "ambiguous"


def network(project_dir: "Path | None" = None, *, all_domains: bool = False) -> int:
    """Render the cross-project memory network — the 'shared consciousness' graph.

    Distinguishes the UNIVERSAL baseline (`user-global` facts every mind holds — a
    complete graph by definition, so uninformative as edges) from DIFFERENTIAL edges
    (`stack-general` facts that bind only the subset of projects whose stacks match).
    The differential edges are the meaningful topology; universal facts are a shared
    substrate listed separately, not drawn as trivial all-to-all edges.

    v0.1.76 (audit): minds derive from provenance basenames, which accrue DEAD entries
    (deleted test projects measured live in this fleet) — every count here silently
    included them. A mind with no plausible on-disk store now renders with a `?` and a
    footnote; the flag is display-only (see _mind_unresolved — report, never prune)."""
    if all_domains:
        facts = [(s, fm, t) for s, fm, t, _p in _all_domain_records()]
        # the fleet dogfood: all-domains passed ctx=None, so _holder_labels fell
        # back to the RETIRED Markdown `projects:` and reported 0 minds holding
        # 4 live canonicals. Resolve ANY enrolled ctx (cwd) — the registry's
        # holders table is global, the ctx only supplies the db path.
        try:
            from store_context import resolve_store as _rs_net
            _ctx_net = _rs_net(Path.cwd())
        except Exception:
            _ctx_net = None
    elif project_dir is None:
        facts = []
    else:
        from store_context import resolve_store as _rs_net
        _ctx_net = _rs_net(Path(project_dir))
        facts = facts_for_context(_ctx_net)
    _ctx_h = locals().get("_ctx_net")
    minds = sorted({p for n, fm, _ in facts for p in _holder_labels(fm, stem=n, ctx=_ctx_h)})
    universal = [(n, fm) for n, fm, _ in facts if fm.get("scope") == "user-global"]
    differential = [(n, fm) for n, fm, _ in facts if fm.get("scope") == "stack-general"]
    other = [(n, fm) for n, fm, _ in facts if fm.get("scope") not in ("user-global", "stack-general")]

    out: list = []
    title = "✦ SHARED CONSCIOUSNESS · cross-project memory"
    tag = f"{len(minds)} minds"
    gap = max(2, _ui.W - 2 - len(title) - len(tag))
    out.append(_ui.rule())
    out.append("  " + _ui.c("✦", "cyan") + title[1:] + " " * gap + _ui.c(tag, "bold"))
    _unres = {m for m in minds if _mind_unresolved(m)}
    out.append("  " + _ui.c(", ".join((m + "?" if m in _unres else m) for m in minds) or "(no projects yet)", "dim"))
    if _unres:
        out.append("  " + _ui.c(f"? = no matching store on disk ({len(_unres)}) — a deleted/renamed project's "
                                "dead provenance edge; counts below include it (report-only, never auto-pruned)", "yellow"))
    out.append(_ui.rule())
    out.append("")
    out.append(_ui.kv("MEMORIES", f"{len(facts)} shared · {len(universal)} universal · {len(differential)} differential"
               + (f" · {len(other)} other" if other else "")))

    # Universal substrate — held by every mind (a complete graph; listed, not drawn)
    out.append("")
    out.append(_ui.kv("UNIVERSAL", _ui.c("user-global — every mind holds these (the shared substrate)", "dim")))
    if universal:
        for n, fm in universal:
            held = len(_holder_labels(fm, stem=n, ctx=_ctx_h))
            flag = "" if held == len(minds) else f"  (only {held}/{len(minds)} so far)"
            out.append("    " + _ui.c("•", "cyan") + f" {n}" + _ui.c(flag, "dim"))
    else:
        out.append("    " + _ui.c("(none)", "dim"))

    # Differential edges — the meaningful topology (stack-general bindings)
    out.append("")
    out.append(_ui.kv("EDGES", _ui.c("stack-general — the bindings that carry real signal", "dim")))
    proj_diff: dict[str, set[str]] = {}
    for n, fm in differential:
        for pr in _holder_labels(fm, stem=n, ctx=_ctx_h):
            proj_diff.setdefault(pr, set()).add(n)
    edges = []
    for i, a in enumerate(minds):
        for b in minds[i + 1:]:
            shared = len(proj_diff.get(a, set()) & proj_diff.get(b, set()))
            if shared:
                edges.append((a, b, shared))
    if not edges:
        out.append("    " + _ui.c("(none yet — all memory is universal; edges form when stack-general", "dim"))
        out.append("    " + _ui.c(" facts spread to a SUBSET of same-stack projects)", "dim"))
    for a, b, w in sorted(edges, key=lambda e: -e[2]):
        out.append(f"    {a[:24]:>24} {_ui.c('●' + '━' * min(w, 20) + '●', 'cyan')} {b[:24]:<24} " + _ui.c(f"({w} shared)", "dim"))
    print(_ui.ascii_translate("\n".join(out)))
    return 0


# ── garbage collection: orphaned mirrors (Fix B) ───────────────────────────────
def _orphans(store: Path, canon: "set | None" = None,
              decode_names: bool = False, pair_keys: bool = False,
              local_domain: str = "") -> list[str]:
    """Mirror files (`global_ref:`) in this store whose CANONICAL no longer exists in
    the global store. These are the dead memory --pull can never reclaim (it only
    iterates LIVE globals), so they accrue forever — the leak Fix B closes.
    v0.1.75: gc() passes `canon` from iter_canonical_stems_for_gc, so the mass-delete
    safety guard and this scan see the SAME live-stem set. `canon=None` is empty
    (never leftover ~/.claude/memory)."""
    if canon is None:
        canon = set()
    out: list[str] = []
    if not store.exists():
        return out
    for f in store.glob("*.md"):
        if f.name == "MEMORY.md" or _is_reserved_stem(f.stem):
            continue
        text = _safe_read_text(f)    # v0.1.69/A3 (Gate-2a follow-up): store-scan convention — a
        if text is None:             # vanished/unreadable fact must not abort the orphan scan
            continue
        _eff_o: "str | tuple"
        if decode_names:
            _d_o, _s_o = decode_key(f.stem)
            # pentest: the mirror's own frontmatter carries the canonical's domain
            # + name — the decode fallback misreads a LEGAL '--'-bearing stem as
            # a namespaced key (live mirror → false orphan → deleted).
            try:
                _fm_o = _frontmatter(text)
                _cd_o = str(_fm_o.get("canonical_domain") or _fm_o.get("domain") or "").strip()
                _nm_o = str(_fm_o.get("name") or "").strip()
            except Exception:
                _cd_o = _nm_o = ""
            if pair_keys:
                _eff_o = ((_cd_o, _nm_o) if _cd_o and _nm_o
                          else (_d_o or local_domain, _s_o))
            else:
                _eff_o = _nm_o or _s_o
        else:
            _eff_o = f.stem
        if _is_mirror(text) and _eff_o not in canon:  # ONLY managed mirrors (frontmatter key)
            out.append(f.stem)
    return out


def _gc_edges(gfacts: list, apply: bool, project_dir: "Path | None" = None) -> int:
    """v0.1.84 (P4, docs/provenance-liveness.spec.md): the fleet-wide provenance-edge triage —
    the lever the single-project dead-edge report never had. Classifies EVERY edge; reports the
    UNRESOLVED (ghost) class with its resolution attempt shown; `--apply` prunes ONLY those
    tokens (stale/ambiguous are NEVER prunable — a renamed store also matches nothing, and a
    wrongly pruned edge self-heals via _record_provenance on that project's next pull, bounding
    the failure cost to a temporary undercount). This UPGRADES, not violates, the
    reported-not-pruned rule: still never automatic — the report is finally fleet-complete and
    the confirmed-apply lever exists. Measured at ship: 16/76 edges (21%) ghost."""
    if not (_projects_root()).is_dir():
        print("~/.claude/projects is absent — refusing --edges (nothing claimable ≠ everything ghost; "
              "the gc mass-delete guard's sibling).")
        return 0
    counts = {"live": 0, "stale": 0, "unresolved": 0, "ambiguous": 0}
    ghosts: dict = {}   # canonical stem -> [ghost holder tokens]
    from domain_policy import fact_domain as _fd_edges
    ctx_labels = None
    if project_dir is not None:
        from store_context import resolve_store as _rs_lab
        ctx_labels = _rs_lab(project_dir)
    for n, fm, _t in gfacts:
        _edom = _fd_edges(fm) or str(fm.get("domain") or "")
        for h in _holder_labels(fm, stem=n, ctx=ctx_labels):
            c = _classify_edge(h, n, _edom)
            counts[c] += 1
            if c == "unresolved":
                ghosts.setdefault(n, []).append(h)
    # PR-#97 review F1 (the real mass-prune blocker): the is_dir() guard above refuses only on
    # ABSENCE, but its "mass-delete guard's sibling" claim demands the COUNT parity gc() has — a
    # present-but-STORELESS projects tree (unmounted/moved store tree, partial restore, transcript-
    # only dirs) resolves EVERY holder to [] → every edge unresolved → --apply would write
    # `projects: []` on every canonical. Guard on the FACT that SOMETHING resolves: if edges exist
    # but NONE are live-or-stale (nothing points at a real store), that is indistinguishable from a
    # wiped/unmounted store tree — refuse, exactly as gc() refuses an empty global store.
    if sum(counts.values()) > 0 and counts["live"] + counts["stale"] == 0:
        print(f"refusing --edges: {counts['unresolved']} edge(s) and NOT ONE resolves to a live store "
              "under ~/.claude/projects — indistinguishable from an unmounted/moved store tree, not "
              "proof every project was deleted. (The gc mass-delete guard's true sibling: guard on "
              "the resolved COUNT, not mere dir existence.)")
        return 0
    out: list = []
    title = "✦ PROVENANCE EDGES · fleet-wide liveness triage"
    tag = "APPLY" if apply else "REPORT"
    gap = max(2, _ui.W - 2 - len(title) - len(tag))
    out.append(_ui.rule())
    out.append("  " + _ui.c("✦", "cyan") + title[1:] + " " * gap + _ui.c(tag, "bold" if apply else "dim"))
    out.append("  " + _ui.c("live = a matching store holds the mirror · stale/ambiguous NEVER prunable "
                            "(self-identifying / not provably ghost) · a wrong prune self-heals on that "
                            "project's next pull", "dim"))
    out.append(_ui.rule())
    out.append("")
    out.append(_ui.kv("EDGES", f"{sum(counts.values())} total · "
               + " · ".join(f"{v} {k}" for k, v in counts.items())))
    removed_total = 0
    if apply and ghosts:
        from store_context import WriteRefused as _WREdges, resolve_store as _rs_edges
        from control_plane import stable_fact_id as _fid_edges, transact as _tx_edges
        ctx_e = _rs_edges(project_dir) if project_dir is not None else None
        if ctx_e is None:
            print("gc --edges: no project context — refusing apply", file=sys.stderr)
            return 1
        expected_e: dict = {}

        def _canon_path(stem: str) -> "Path":
            return _canonical_path(ctx_e, stem)

        for n in ghosts:
            p = _canon_path(n)
            if p.exists():
                expected_e[str(p)] = hashlib.sha256(p.read_bytes()).hexdigest()

        def _mutate_edges(conn, temps):
            del temps
            removed = 0
            for n, hs in ghosts.items():
                fid = _fid_edges(ctx_e.domain_id, n)
                for h in hs:
                    # Delete by EITHER resolution shape: a registered project's
                    # display_name, or a raw project_id label (registry rows whose
                    # project row is gone — the ghost class itself). Markdown
                    # `projects:` is display/migration input only (ADR 023) — the
                    # canonical body is NEVER rewritten here.
                    cur = conn.execute(
                        "DELETE FROM holders WHERE fact_id=? AND (project_id=? "
                        "OR project_id IN (SELECT project_id FROM projects "
                        "WHERE display_name=?))",
                        (fid, h, h),
                    )
                    removed += int(cur.rowcount or 0)
            return {"removed": removed, "deletes": []}

        try:
            _tx = _tx_edges(ctx_e, "gc-edges", {"n": len(ghosts)}, _mutate_edges,
                            expected_revisions=expected_e)
            removed_total = int((_tx.get("result") or {}).get("removed") or 0)
        except _WREdges as e:
            print(f"gc --edges: transaction refused: {e}", file=sys.stderr)
            return 1
    if not ghosts:
        out.append("    " + _ui.c("· no unresolved (ghost) edges — provenance tracks live topology", "dim"))
    for n in sorted(ghosts):
        hs = sorted(set(ghosts[n]))
        if apply:
            out.append("    " + _ui.c("✓", "green") + f" {n}  " + _ui.c(f"pruned {', '.join(hs)} "
                       f"(holders table journaled; canonical body byte-verbatim)", "dim"))
        else:
            out.append("    " + _ui.c("⌀", "yellow") + f" {n}  " + _ui.c(f"ghost holder(s) {', '.join(hs)} "
                       "— 0 store matches under ~/.claude/projects (would prune)", "dim"))
    out.append("")
    tail = (f"pruned {removed_total} ghost token(s) — the live-basis fleet tax now matches topology" if apply
            else "run with --edges --apply to prune the ghosts (surface these to the user first)")
    out.append(_ui.kv("RESULT", tail))
    print(_ui.ascii_translate("\n".join(out)))
    return 0


def _mirror_identity(ctx, name: str, mirror_text: "str | None" = None) -> tuple:
    """(home_domain, fact_stem) for a mirror file — from the mirror's OWN
    frontmatter when readable (the writer stamps the canonical's domain + name;
    the decode fallback covers pre-stamp mirrors). The frontmatter reading
    resolves the '--' ambiguity: a LEGAL same-domain stem containing '--'
    (identifiers blesses it) decodes as a namespaced key, which made gc
    mis-classify its live mirror as an orphan (pentest Med 5/6)."""
    if mirror_text:
        try:
            _fm_i = _frontmatter(mirror_text)
            _cd = str(_fm_i.get("canonical_domain") or _fm_i.get("domain") or "").strip()
            _nm = str(_fm_i.get("name") or "").strip()
            if _cd and _nm and _safe_stem(_nm):
                return (_cd, _nm)
        except Exception:
            pass
    _d_i, _s_i = decode_key(name)
    return (_d_i or getattr(ctx, "domain_id", "") or "", _s_i)


def _mirror_canonical_path(ctx, name: str, mirror_text: "str | None" = None) -> "Path | None":
    """The disk path of a mirror's canonical for its IDENTITY home domain, or
    None when it is gone/tombstoned (group-lifecycle spec §2.3 — the re-source
    reads the canonical file itself, never the admitted-only gfacts snapshot).
    A tombstone holds no re-pullable content, so its mirror is orphaned."""
    _home_mc, _stem_mc = _mirror_identity(ctx, name, mirror_text)
    canon_p = _source_facts_dir(ctx, _home_mc) / f"{_stem_mc}.md"
    ctext = _safe_read_text(canon_p)
    if ctext is None:
        return None
    _c_fm_mc = _frontmatter(ctext)
    if str(_c_fm_mc.get("status") or "").strip() in ("tombstoned", "superseded", "expired"):
        return None
    return canon_p


def _classify_frozen(ctx, name: str, *, stacks: set, memberships: set,
                     g_created: dict, canon_p: "Path | None" = None,
                     mirror_text: "str | None" = None) -> "tuple | None":
    """(reason, canonical_path) when a mirror is FROZEN, else None. The re-sourced
    classifier (group-lifecycle spec §2.3): decode → disk-liveness → the
    enumeration's FULL predicate (admissibility + the recreation guard +
    relevance), with a carried reason token —
      dropped-stack  canonical alive, admitted, but irrelevant here
      guard-stale    canonical alive, the fact predates the group (the guard
                     withholds it — on the admitted path TOO: the bridge admits
                     a member of the recreated group, then the guard skips it)
      not-entitled   canonical alive, not admitted otherwise (member removed …)
    None = canonical gone (the ORPHAN branch owns it) or admitted-and-relevant
    again (nothing to reclaim). The reason token drives the gc render copy —
    the hardcoded "dropped stack" label must not lie (review 5)."""
    if canon_p is None:
        canon_p = _mirror_canonical_path(ctx, name, mirror_text)
    if canon_p is None:
        return None
    ctext = _safe_read_text(canon_p)
    if ctext is None:
        return None
    c_fm = _frontmatter(ctext)
    admitted = False
    try:
        from fact_schema import (CLASS_ACTIVE, CLASS_LEGACY, _parse_flow_list as _pfl_cf,
                                 classify_canonical)
        from domain_policy import admit_cross_project, fact_domain
        from memory_status import _looks_secret
        from control_plane import migration_mode_readonly
        home, _s_cf = _mirror_identity(ctx, name, mirror_text)
        # pentest: classify against the IDENTITY home, never the canonical's
        # self-declared domain (its own validator would pass a crafted value).
        _cls_cf = classify_canonical(ctext, stem=_s_cf, domain=home)
        _ok_cls = (_cls_cf["class"] == CLASS_ACTIVE
                   or (_global_is_fixture() and _cls_cf["class"] == CLASS_LEGACY))
        if not _ok_cls:
            # an invalid/legacy canonical stays LIVE by the stem-snapshot rule
            # (0.3.3): its mirror is neither orphaned nor frozen — the file
            # might be repaired, and the frozen mechanism is about DELIVERY
            # revocation, not content validity.
            return None
        if not _looks_secret(ctext):
            adm = dict(c_fm)
            adm["body"] = ctext
            if (_global_is_fixture() or _hermetic_home()) and not fact_domain(c_fm) \
                    and getattr(ctx, "domain_id", "") not in ("", "unknown"):
                adm["domain"] = ctx.domain_id
            try:
                _mode_cf = migration_mode_readonly(ctx)
            except Exception:
                _mode_cf = "dual-read"
            admitted = admit_cross_project(
                ctx.domain_id, adm, migration_mode=_mode_cf,
                looks_secret=_looks_secret, memberships=memberships,
                group_recips=set(_pfl_cf(str(c_fm.get("recipients") or ""))))
    except Exception:
        admitted = False
    if admitted:
        if _recipients_stale_for(c_fm, memberships, g_created):
            return ("guard-stale", canon_p)
        if is_relevant(c_fm, stacks):
            return None
        return ("dropped-stack", canon_p)
    if _recipients_stale_for(c_fm, memberships, g_created):
        return ("guard-stale", canon_p)
    return ("not-entitled", canon_p)


def gc(project_dir: Path, apply: bool, edges: bool = False) -> int:
    """Reclaim orphaned mirrors. Report-by-default; delete only with --apply, and
    NEVER touch a project-authored (non-`global_ref:`) fact, even on a name collision.

    v0.1.75 (audit F6): also reports/reclaims FROZEN mirrors — `global_ref:` files whose canonical is
    ALIVE but no longer relevant to this project (a dropped stack): --pull can't refresh them
    (irrelevant short-circuits), the orphan scan can't see them (the canonical exists), so they sat
    stale forever, still taxing the always-loaded index. Reclaim is safe by construction — a frozen
    mirror is a replica of a LIVE canonical, so if the stack returns (or detection flickered) the
    next --pull simply re-pulls it; no memory can be lost.

    Dead-edge provenance (a canonical that still exists but lists a project no longer
    holding it) is REPORTED only, not auto-pruned: absence-of-mirror is a weak signal
    (a renamed/moved store also 'holds nothing'), and stripping global state on it
    risks erasing real edges. The proven win is removing the orphan files.

    v0.4.11 (group-lifecycle §2.3): the frozen scan is RE-SOURCED — a mirror whose
    canonical is NOT in the admitted set is decoded, its canonical tested for DISK
    liveness, and classified with a carried reason token (dropped-stack / guard-stale
    / not-entitled). Orphan yields to frozen whenever the canonical file is disk-alive.
    The orphan branch no longer blind-deletes: the mirror's own global_ref_body
    lineage stamp vs its body hash decides clean-delete vs quarantine (edited work is
    kept under quarantine/)."""
    project_dir = project_dir.resolve()
    if not project_dir.is_dir():
        # v0.1.75 defense-in-depth (audit F5) — same phantom-store guard as run(); _dispatch is the CLI choke.
        print(f"error: project dir {project_dir} does not exist — refusing (phantom-store guard)", file=sys.stderr)
        return 2
    # SAFETY: an EMPTY canonical set makes EVERY mirror look orphaned → gc --apply would
    # delete them all. A global store that is absent OR present-but-empty (unmounted,
    # moved, not yet synced, or only the MEMORY.md index left) is NOT the same as "all
    # canonicals were deliberately deleted". Refuse in either case rather than risk wiping
    # re-pullable / last-surviving memory. (Guard on the FACT COUNT, not mere existence.)
    # v0.1.75: ONE live-stem snapshot — the guard, the orphan scan, the frozen scan, and the
    # dead-edge report all see the SAME store state (the audit's guard-TOCTOU: a store emptying
    # between the guard's read and a second scan read would have made every mirror look orphaned —
    # the exact mass-wipe the guard exists to prevent).
    from store_context import resolve_store as _rs_gc
    from store_context import WriteRefused as _WRGc
    _ctx_gc = _rs_gc(project_dir)
    if apply and not getattr(_ctx_gc, "cross_project_allowed", False):
        print("gc: --apply requires enrollment into a named domain "
              "(cm project enroll --domain NAME)", file=sys.stderr)
        return 2
    if getattr(_ctx_gc, "cross_project_allowed", False):
        gfacts = iter_admissible_facts(_ctx_gc)
    else:
        gfacts = []
    store = project_store(project_dir)
    if not gfacts:
        # Empty live canonicals + leftover managed mirrors = forget-then-GC (ADR 013).
        # Missing domain dir AND no mirrors = unmounted/absent, not "all deleted".
        has_mirrors = False
        if store.is_dir():
            for _mf in store.glob("*.md"):
                if _mf.name == "MEMORY.md" or _is_reserved_stem(_mf.stem):
                    continue
                _mt = _safe_read_text(_mf)
                if _mt is not None and _is_mirror(_mt):
                    has_mirrors = True
                    break
        def _has_canon_files(root: Path) -> bool:
            if not root.is_dir():
                return False
            return any(p.suffix == ".md" and p.name != "MEMORY.md" for p in root.glob("*.md"))
        live_canon = _has_canon_files(_ctx_gc.canonical_domain_dir)
        if not live_canon and _global_is_fixture():
            live_canon = _has_canon_files(global_store())
        # Unmounted/empty source + leftover mirrors = mass-wipe risk (Probe G).
        # Tombstones still sit as .md files, so forget-then-GC still proceeds.
        # Empty canonicals AND no leftover mirrors = nothing to reclaim (enrolled
        # empty-domain steady state) — fail-closed is right, mass-wipe wording is not.
        if not live_canon:
            if not has_mirrors:
                if getattr(_ctx_gc, "cross_project_allowed", False):
                    print(f"gc: domain {_ctx_gc.domain_id} has no canonicals and no leftover "
                          "mirrors — nothing to reclaim")
                else:
                    print("gc: no live canonicals and no leftover mirrors — nothing to reclaim")
                return 0
            why = ("no admissible canonicals" if getattr(_ctx_gc, "cross_project_allowed", False)
                   else ("absent" if not global_store().exists()
                         else "present but empty (no canonical facts)"))
            print(f"gc: {why} — refusing to GC "
                  "(cannot distinguish that from all-canonicals-deleted).")
            return 0
    if apply:
        from control_plane import assert_mutation_allowed
        try:
            assert_mutation_allowed(_ctx_gc)
        except _WRGc as e:
            print(f"gc: {e}", file=sys.stderr)
            return 2
        from canonical_ingress import ack_tombstoned_mirrors as _ack_gc
        _acked = _ack_gc(_ctx_gc)
        if not _acked.get("ok"):
            print("gc: forget-ack refused: " + str(_acked.get("error") or ""),
                  file=sys.stderr)
            return 2
    if edges:   # v0.1.84 (P4): fleet-wide edge triage — project_dir-independent, same snapshot
        return _gc_edges(gfacts, apply, project_dir)
    _local_stems = iter_canonical_stems_for_gc(_ctx_gc)
    _pair_canon = {(_ctx_gc.domain_id or "", n) for n in _local_stems}
    _pair_canon |= {(str(fm.get("domain") or _ctx_gc.domain_id or ""), n)
                    for n, fm, _ in gfacts}
    orphans = _orphans(store, canon=_pair_canon, decode_names=True,
                      pair_keys=True, local_domain=_ctx_gc.domain_id or "")
    # v0.1.75 (audit F6): FROZEN mirrors — see the docstring. Detected against the SAME snapshot.
    # 2026-09-03 audit: the frozen verdict DELETES files, so it must not trust the cached
    # stacks (a stale cache can classify a newly-relevant mirror as frozen and delete live
    # recall for up to the TTL). GC is rare — a fresh detect runs here, never the cache.
    stacks = detect_stacks(project_dir)
    _memberships_gc = _project_memberships(_ctx_gc)
    _g_created_gc = _group_created_at(_ctx_gc)
    frozen: "list[tuple]" = []
    if store.exists():
        for f in sorted(store.glob("*.md")):
            if f.name == "MEMORY.md" or _is_reserved_stem(f.stem):
                continue
            t = _safe_read_text(f)   # store-scan convention — a vanished file must not abort the scan
            if t is None or not _is_mirror(t):
                continue
            _ver_fz = _classify_frozen(_ctx_gc, f.stem, stacks=stacks,
                                       memberships=_memberships_gc,
                                       g_created=_g_created_gc, mirror_text=t)
            if _ver_fz is not None:
                frozen.append((f.stem, _ver_fz[0]))
    # orphan yields to frozen whenever the canonical is disk-alive (spec §2.3): the
    # classifier above already claimed those mirrors — the foreign alive-canonical
    # mirror never reaches the orphan branch.
    _frozen_names = {n for n, _r in frozen}
    orphans = [n for n in orphans if n not in _frozen_names]
    out: list = []
    title = "✦ GARBAGE COLLECT · orphaned mirrors"
    tag = "APPLY" if apply else "REPORT"
    gap = max(2, _ui.W - 2 - len(title) - len(tag))
    out.append(_ui.rule())
    out.append("  " + _ui.c("✦", "cyan") + title[1:] + " " * gap + _ui.c(tag, "bold" if apply else "dim"))
    out.append("  " + _ui.c(f"{project_dir.name} · {slug_for(project_dir)}", "dim"))
    out.append(_ui.rule())
    out.append("")
    out.append(_ui.kv("ORPHANS", f"{len(orphans)} mirror(s) whose canonical is gone"
               + ("" if orphans else "  " + _ui.c("· nothing to reclaim", "dim"))))
    removed = 0
    quarantined = 0
    _deleted_gc: set = set()
    _quar_gc: set = set()
    if apply and (orphans or frozen):
        from control_plane import transact, _file_hash as _fh_gc, stable_fact_id as _sf_gc
        idxp = store / "MEMORY.md"
        names = list(orphans) + [n for n, _r in frozen]
        expected: dict = {}
        if idxp.is_file():
            h = _fh_gc(idxp)
            if h:
                expected[str(idxp)] = h
        for name in names:
            p = store / f"{name}.md"
            if p.is_file():
                h = _fh_gc(p)
                if h:
                    expected[str(p)] = h

        def mutate(conn, temps):
            import time as _time_gc
            from mirror_conflict import semantic_hash as _sem_gc
            _idx_gc = _safe_read_text(idxp)
            idx = _idx_gc if _idx_gc is not None else "# Memory Index\n"
            deletes = []
            ops = []
            quar: list = []
            extra_expected: dict = {}
            # review 3: the re-sourced predicate re-reads the REGISTRY maps
            # too — a membership re-grant between scan and lock must skip the
            # now-deliverable mirror. Fresh reads are safe under the
            # interprocess lock (transacts serialize on it), and they're
            # HOISTED — the registry cannot change mid-transact, so one fresh
            # pair per op, not per name.
            _memberships_lk = _project_memberships(_ctx_gc, refresh=True)
            _g_created_lk = _group_created_at(_ctx_gc, refresh=True)
            for name in names:
                p = store / f"{name}.md"
                _t_gc = _safe_read_text(p)
                if _t_gc is None or not _is_mirror(_t_gc):
                    continue
                # in-lock re-verification RE-SOURCES (spec review N2): decode →
                # disk-liveness → admissibility + relevance, for EVERY class. A
                # name whose cause cleared (an owner's --repoint landed between
                # scan and lock) is skipped; a name whose canonical died under
                # the lock falls to the orphan arm.
                _cp_now = _mirror_canonical_path(_ctx_gc, name, _t_gc)
                _ver_gc = _classify_frozen(
                    _ctx_gc, name, stacks=stacks,
                    memberships=_memberships_lk,
                    g_created=_g_created_lk,
                    canon_p=_cp_now, mirror_text=_t_gc)
                if _ver_gc is None:
                    if _cp_now is not None:
                        continue      # admitted + relevant again — nothing to reclaim
                    # orphan arm (canonical gone): no canonical to compare — the
                    # mirror's own global_ref_body lineage stamp vs its current
                    # body hash (matching → clean → delete; diverging → the
                    # user's work → quarantine; no stamp — pre-v0.1.78, never
                    # refreshed — defaults clean).
                    _fm_gc = _frontmatter(_t_gc)
                    _stamp_gc = str(_fm_gc.get("global_ref_body") or "")
                    if _stamp_gc and _stamp_gc != _body_hash(_t_gc):
                        _qpath = store / "quarantine" / \
                            f"{name}.{_time_gc.strftime('%Y%m%dT%H%M%SZ', _time_gc.gmtime())}.md"
                        temps[str(_qpath)] = _t_gc
                        quar.append(name)
                else:
                    # frozen arm: clean-vs-edited against the disk-alive canonical
                    # (the revoke precedent's semantic compare). The canonical read
                    # is pinned into expected_revisions — a mid-transact canonical
                    # change must not silently flip the verdict (review N2).
                    _ctext_gc = _safe_read_text(_cp_now) or ""
                    try:
                        _edited = _sem_gc(_t_gc) != _sem_gc(_ctext_gc)
                    except Exception:
                        _edited = True
                    _h_cp = _fh_gc(_cp_now) if _cp_now.is_file() else ""
                    if _h_cp:
                        extra_expected[str(_cp_now)] = _h_cp
                    if _edited:
                        _qpath = store / "quarantine" / \
                            f"{name}.{_time_gc.strftime('%Y%m%dT%H%M%SZ', _time_gc.gmtime())}.md"
                        temps[str(_qpath)] = _t_gc
                        quar.append(name)
                deletes.append(str(p))
                idx = "\n".join(
                    ln for ln in idx.splitlines() if f"]({name}.md)" not in ln)
                _home_gc, _s_gc = _mirror_identity(_ctx_gc, name, _t_gc)
                fid = _sf_gc(_home_gc, _s_gc)
                conn.execute(
                    "DELETE FROM holders WHERE project_id=? AND fact_id=?",
                    (_ctx_gc.project_id, fid))
                ops.append({"op": "holder_delete", "fact_id": fid,
                            "project_id": _ctx_gc.project_id})
            temps[str(idxp)] = idx.rstrip() + "\n"
            return {"deletes": deletes, "removed": len(deletes) - len(quar),
                    "quarantined": quar, "registry_ops": ops,
                    "expected_revisions": extra_expected}

        try:
            # the in-lock re-verification may skip a name that changed between scan and
            # lock — the RESULT must report what the transact actually deleted, not the
            # scan lists (review fix: a skipped name over-stated the removal counts)
            _t_out = transact(_ctx_gc, "gc-apply",
                              {"orphans": list(orphans),
                               "frozen": [n for n, _r in frozen]},
                              mutate, expected_revisions=expected)
            _res_gc = _t_out.get("result") or {}
            _deleted_gc = {Path(str(p)).stem for p in (_res_gc.get("deletes") or [])}
            _quar_gc = set(_res_gc.get("quarantined") or [])
            removed = sum(1 for n in orphans if n in _deleted_gc and n not in _quar_gc)
            removed += sum(1 for n, _r in frozen if n in _deleted_gc and n not in _quar_gc)
            quarantined = len(_quar_gc)
        except _WRGc as e:
            print(f"gc: {e}", file=sys.stderr)
            return 2
    for name in orphans:
        if apply:
            if name in _quar_gc:
                out.append("    " + _ui.c("✻", "red") + f" quarantined {name}  " + _ui.c("(locally edited — kept under quarantine/)", "dim"))
            elif name in _deleted_gc:
                out.append("    " + _ui.c("✓", "green") + f" removed {name}  " + _ui.c("(file + index pointer)", "dim"))
            else:
                out.append("    " + _ui.c("·", "yellow") + f" {name}  " + _ui.c("(changed under lock — left in place)", "dim"))
        else:
            out.append("    " + _ui.c("·", "yellow") + f" {name}  " + _ui.c("(would remove file + index pointer)", "dim"))
    # v0.4.11: the reason token drives the copy — the hardcoded "dropped stack"
    # label would lie about guard-stale / not-entitled mirrors (review 5).
    _reason_copy = {
        "dropped-stack": "canonical alive but irrelevant here (dropped stack)",
        "guard-stale": "canonical alive but the fact predates the group it cites — re-point or re-confirm",
        "not-entitled": "canonical alive but this project is not entitled (member removed / not admitted)",
    }
    out.append(_ui.kv("FROZEN", f"{len(frozen)} mirror(s) whose canonical is ALIVE but not delivered here"
               + ("" if frozen else "  " + _ui.c("· none", "dim"))))
    for name, reason in frozen:
        _why = _reason_copy.get(reason, "canonical alive but not delivered here")
        if apply:
            if name in _quar_gc:
                out.append("    " + _ui.c("✻", "red") + f" quarantined {name}  " + _ui.c("(locally edited — kept under quarantine/)", "dim"))
            elif name in _deleted_gc:
                out.append("    " + _ui.c("✓", "green") + f" removed {name}  " + _ui.c(f"({_why}; re-pullable if the cause clears)", "dim"))
            else:
                out.append("    " + _ui.c("·", "yellow") + f" {name}  " + _ui.c("(changed under lock — left in place)", "dim"))
        else:
            out.append("    " + _ui.c("✻", "yellow") + f" {name}  " + _ui.c(f"(would remove file + index pointer; {_why} — canonical stays)", "dim"))
    tail = (f"removed {removed} mirror(s), quarantined {quarantined} (edited)" if apply
            else "run with --apply to delete (surface these to the user first)")
    out.append("")
    out.append(_ui.kv("RESULT", tail))
    # Dead-edge provenance, report-only (conservative — see docstring).
    if apply:
        print(_ui.ascii_translate("\n".join(out)))
        return 0
    dead = []
    for name, fm, _ in gfacts:
        for holder in _holder_labels(fm, stem=name, ctx=_ctx_gc):
            # we only know THIS project's store path; report if it's listed but absent.
            # v0.1.76: compare in the SANITIZED token space provenance is written in — a basename
            # _sanitize_token rewrites ('@scope' → '-scope') never equalled its raw self here.
            if holder == _sanitize_token(project_dir.name) and not (store / f"{name}.md").exists():
                dead.append(name)
    if dead:
        out.append("")
        out.append(_ui.kv("DEAD", _ui.c("canonical lists this project, but no mirror here (report only)", "dim")))
        for n in dead:
            out.append("    " + _ui.c("·", "dim") + f" {n}")
    print(_ui.ascii_translate("\n".join(out)))
    return 0


# ── promotion: hand a local fact UP to the canonical global store (v0.1.16) ─────
def _body(text: str) -> str:
    r"""The fact BODY — markdown AFTER the leading frontmatter block. Strips ONLY the first
    `^---\n…\n---` span (non-greedy, once) — NOT split('---'), since a body legitimately contains
    `---`/`***` horizontal rules. Trailing whitespace (per line + overall) is normalized so the M2
    compare ignores cosmetic drift. v0.1.74 close-fence PARITY with _frontmatter (audit): the close is
    the WHOLE first line starting '---' ('----'/'--- notes' close there too) and may sit at EOF with no
    trailing newline — the old `\n---\n`-exact close left a body-less fact's frontmatter unstripped, so
    two body-less facts with differing frontmatter compared UNEQUAL and promote's Guard-5 spuriously
    refused a clean reconcile."""
    if text.startswith("﻿"):       # strip a leading BOM (some editors add one) so the \A--- anchor holds
        text = text[1:]
    text = text.replace("\r\n", "\n").replace("\r", "\n")   # CRLF/CR (a model→file artifact) — match _frontmatter
    body = re.sub(r"\A---\n.*?\n---[^\n]*(?:\n|\Z)", "", text, count=1, flags=re.DOTALL)
    return "\n".join(ln.rstrip() for ln in body.splitlines()).strip()


def _bodies_match(a: str, b: str) -> bool:
    """M2 (v0.1.39): do two fact files carry the SAME body? Frontmatter legitimately differs on promote
    (scope/projects/global_ref), so compare BODIES only. STRICT — identical→True, any divergence→False: a
    false positive costs a manual merge, a false negative IS the silent data loss. PURE (smoke pins it)."""
    return _body(a) == _body(b)


def promote(project_dir: Path, local_fact: str, canon_name: str, prefer_canonical: bool = False,
             allow_repoint: bool = False) -> int:
    """Hand a project-authored LOCAL fact up to the canonical global store, then convert the
    origin's own copy into a managed mirror — the local→canonical hand-off the Phase-1 promotion
    re-audit drives. SINGLE-SHOT: one invocation does the full hand-off — write the canonical, record
    provenance, rewrite the origin copy as a mirror, and (on a rename) remove the old-named local file
    + its index pointer. That closes the gap a MULTI-STEP, hand-done hand-off leaves open: a forgotten
    conversion step strands a project-authored copy that `--gc` can never reclaim (a non-mirror), and on
    the next --pull it would either SHADOW the canonical (same name → `present(local)`, never refreshes)
    or DUPLICATE it (renamed → the canonical re-pulls as a second file). (It is not crash-atomic — an
    interrupted process can still leave a partial state — but a completed call never does. v0.1.71:
    the canonical CREATE itself is now exclusive — two processes racing to promote different local
    facts onto the same NEW canon_name can no longer silently clobber one another; the loser is
    refused and told to retry. That's a create-vs-create guard, not full multi-step atomicity — a
    crash mid-sequence between an already-successful create and the later mirror/index writes is
    still possible, same as before.)

    CANON_NAME defaults to LOCAL_FACT; pass it to RENAME on promote (normalize `_`→`-` / drop a
    date) or to DEDUP a local copy onto an existing canonical. An existing canonical is treated as
    AUTHORITATIVE and is never overwritten (other projects already mirror it) — that case is a
    RECONCILE: only the origin side (mirror + provenance + rename cleanup) runs.

    The model owns the re-scope (sets `scope`/`stacks` on the local fact in Phase 4) and the global
    MEMORY.md index line (as for any canonical); this op owns the file mechanics + the origin index.
    Writes the REAL global store, so it is exercised hermetically by simulate_accumulation.py
    (Probe K), never by smoke.py."""
    project_dir = project_dir.resolve()
    store = project_store(project_dir)
    if not _safe_stem(local_fact) or not _safe_stem(canon_name):
        print("promote: fact names must be kebab/snake-case (safe stems)", file=sys.stderr)
        return 2
    if _is_reserved_stem(local_fact) or _is_reserved_stem(canon_name):
        print(f"promote: '{'/'.join(_RESERVED_STEMS)}' is a reserved index name, not a fact — refusing "
              "(writing it would clobber a store's always-loaded MEMORY.md index)", file=sys.stderr)
        return 2
    src = store / f"{local_fact}.md"
    if not src.exists():
        print(f"promote: no local fact '{local_fact}' in {store}", file=sys.stderr)
        return 1
    local_text = src.read_text(encoding="utf-8", errors="replace")
    if _is_mirror(local_text):  # idempotency + safety guard: a mirror is already global
        print(f"promote: '{local_fact}' is already a managed mirror (already global) — nothing to promote",
              file=sys.stderr)
        return 1

    from store_context import resolve_store as _rs_prom, warn_unenrolled_share as _warn_prom
    _sctx = _rs_prom(project_dir)
    _warn_prom(_sctx)
    if not getattr(_sctx, "cross_project_allowed", False):
        print("promote: cross-project writes require enrollment into a named domain "
              "(cm project enroll --domain NAME --apply)", file=sys.stderr)
        return 2
    gdir = _sctx.canonical_domain_dir
    gdir.mkdir(parents=True, exist_ok=True)
    canon_path = gdir / f"{canon_name}.md"
    reconcile = canon_path.exists()  # an existing canonical is authoritative — never clobber it
    canon_existing = canon_path.read_text(encoding="utf-8", errors="replace") if reconcile else ""
    decide_fm = _frontmatter(canon_existing if reconcile else local_text)
    scope = decide_fm.get("scope", "")
    ctx = f"existing canonical '{canon_name}'" if reconcile else f"local fact '{local_fact}'"
    # Guard 1 — a promoted canonical must be REPLICABLE: scope ∈ {stack-general, user-global}.
    # A project-local/scopeless canonical is dead weight (is_relevant returns False for it).
    if scope not in ("stack-general", "user-global"):
        print(f"promote: {ctx} has scope '{scope or '(none)'}' — set scope: stack-general|user-global "
              "before promoting (a project-local/scopeless canonical never replicates)", file=sys.stderr)
        return 1
    # Guard 2 — a stack-general fact's `stacks:` must be NON-EMPTY *and* DETECTABLE. is_relevant intersects
    # them against detect_stacks's output, so an empty set OR a tag detect_stacks can NEVER emit (a typo, or a
    # real-but-undetectable stack like 'release'/'ci-cd') makes the canonical match NO project — a fleet-DEAD
    # write. M4 (v0.1.39) closes the undetectable half (the empty-set half was the original guard).
    if scope == "stack-general":
        _fs = _fact_stacks(decide_fm)
        if not _fs:
            print(f"promote: {ctx} is stack-general but declares no `stacks:` — it could match no project "
                  "(is_relevant needs a non-empty stacks intersection). Add stacks: [...] first.", file=sys.stderr)
            return 1
        _undet = _fs - _DETECTABLE_STACKS
        if _undet:
            print(f"promote: {ctx} declares stack(s) {sorted(_undet)} that detect_stacks can NEVER emit "
                  f"(detectable: {sorted(_DETECTABLE_STACKS)}) — the canonical would match NO project (fleet-dead). "
                  "Use a detectable stack, or scope user-global if it isn't stack-gated.", file=sys.stderr)
            return 1
    # Guard 3 — a RENAME/dedup whose destination name already holds a DISTINCT project-authored fact
    # would silently destroy it; run()'s `present(local)` rule is "never clobber" and promote must match
    # it. `samefile` excludes a case-only rename on a case-insensitive FS (`Foo`→`foo` is one file —
    # handled at the unlink below); a MIRROR already at the destination is a mirror of THIS canonical, so
    # refreshing it is safe (the reconcile/idempotent path). Checked BEFORE any write, so no partial state.
    dest = store / f"{canon_name}.md"
    if (canon_name != local_fact and dest.exists() and not src.samefile(dest)
            and not _is_mirror(dest.read_text(encoding="utf-8", errors="replace"))):
        print(f"promote: a different project-authored fact already occupies '{canon_name}' in this store — "
              "refusing (a rename here would overwrite it). Pick another CANON_NAME or reconcile by hand.",
              file=sys.stderr)
        return 1
    # Guard 4 (v0.1.25, WARN not block) — [[wikilinks]] to NON-global facts DANGLE in every mirror (a global
    # fact's links travel with it). Advisory: the promotion still proceeds, but convert them to plain text.
    _dangling = _nonglobal_wikilinks(local_text, gdir, exclude=canon_name)
    if _dangling:
        print("promote: NOTE — wikilink(s) to non-global facts will DANGLE in every mirror: "
              + ", ".join(f"[[{w}]]" for w in _dangling)
              + ". Convert to plain text — a global fact should link only to other global facts.", file=sys.stderr)

    # Guard 5 (M2, v0.1.39) — RECONCILE must not silently DISCARD the local's body. On reconcile the origin is
    # rewritten as a mirror of the EXISTING canonical (below), so a local carrying DIFFERENT body content (a
    # re-frame / an edit) would be destroyed with no trace. Refuse unless --prefer-canonical declares the
    # canonical authoritative (the dedup intent). Body-only compare (frontmatter legitimately differs); BEFORE
    # any write (Guard-3's no-partial-state rule). Hits BOTH sub-cases: rename (src.unlink) AND same-name (in place).
    if reconcile and not prefer_canonical and not _bodies_match(local_text, canon_existing):
        _what = f"rename onto '{canon_name}'" if canon_name != local_fact else f"update of '{canon_name}'"
        print(f"promote: the local fact's BODY differs from the existing canonical '{canon_name}' — this {_what} "
              "would DISCARD the local content (reconcile rewrites the origin as a mirror of the canonical). "
              "Either merge the local's body into the canonical first, then re-run; or pass --prefer-canonical "
              "to keep the canonical and drop the local body (the dedup intent).", file=sys.stderr)
        return 1

    # Sole writer: cm canonical upsert. CREATE uses create_only (Track D-2b race: concurrent
    # create refuses, origin untouched). RECONCILE uses preserve_canonical (never overwrite
    # the existing canonical body; origin conversion + record_holder still journaled).
    # Origin mirror, index pointer, and rename deletes happen INSIDE that transact — never
    # dest.write_text / _record_provenance after locks drop.
    from canonical_ingress import upsert as _upsert
    origin_delete = None
    renamed = canon_name != local_fact
    if renamed:
        try:
            same_origin = src.exists() and dest.exists() and src.samefile(dest)
        except OSError:
            same_origin = False
        if not same_origin:
            origin_delete = src
    if not reconcile:
        _up = _upsert(_sctx, canon_name, local_text, create_only=True,
                      origin_local=dest, origin_delete=origin_delete,
                      allow_repoint=allow_repoint)
    else:
        _up = _upsert(_sctx, canon_name, local_text, preserve_canonical=True,
                      origin_local=dest, origin_delete=origin_delete,
                      allow_repoint=allow_repoint)
    if not _up.get("ok"):
        print(f"promote: canonical upsert refused: {_up.get('error')}", file=sys.stderr)
        return 1
    if not canon_path.exists():
        print("promote: upsert ok but canonical missing — refusing", file=sys.stderr)
        return 1
    canon_text = canon_path.read_text(encoding="utf-8", errors="replace")
    fm = _frontmatter(canon_text)

    # Change-1↔Change-3 link: if the ORIGIN itself doesn't detect this stack-general fact's stack,
    # its own mirror reads `irrelevant` on the next --pull and freezes (never refreshes) — almost
    # always a mis-tag. WARN (the local recall still works + other matching projects pull the live
    # copy); don't refuse.
    if scope == "stack-general":
        origin_stacks, _ = stacks_with_cache(store, project_dir)   # v0.4.2 (P1): the advisory goes stale-tolerant
        if not (_fact_stacks(fm) & origin_stacks):
            print(f"  ⚠ origin {project_dir.name} does not detect stack(s) {sorted(_fact_stacks(fm))} "
                  f"(detected: {sorted(origin_stacks) or '∅'}) — its own mirror will read irrelevant "
                  "and won't refresh on --pull (likely a mis-tag)", file=sys.stderr)

    # v0.1.67 (Phase C): the fleet-tax ADVISORY — post-write script truth, WARN-only (never a block; a
    # hard fleet gate needs its own oracle-grade review). Each canonical's pointer taxes every holder
    # node's always-loaded index every session; surface when the fleet total crosses the advisory.
    _tot = sum(est_tokens(_pointer_line(n, f)) * len(_holders(f))
               for n, f, _ in facts_for_context(_sctx))
    if _tot > GLOBAL_FLEET_TAX_ADVISORY:
        _mine = est_tokens(_pointer_line(canon_name, fm)) * max(1, len(_holders(fm)))
        print(f"  ⚠ fleet-tax advisory: Σ pointer×holders ≈{_tot} tok > {GLOBAL_FLEET_TAX_ADVISORY} "
              f"(this canonical adds ≈{_mine}) — warn-only; `--utility` has the per-canonical evidence",
              file=sys.stderr)

    out: list = []
    title = "✦ PROMOTE · " + project_dir.name
    tag = "RECONCILE" if reconcile else "CREATE"
    gap = max(2, _ui.W - 2 - len(title) - len(tag))
    out.append(_ui.rule())
    out.append("  " + _ui.c("✦", "cyan") + title[1:] + " " * gap + _ui.c(tag, "bold"))
    out.append("  " + _ui.c(f"{local_fact} → {canon_name}  ({scope})", "dim"))
    out.append(_ui.rule())
    out.append("")
    out.append(_ui.kv("CANONICAL", f"{canon_name}.md · "
               + ("attached origin to existing canonical (not overwritten)" if reconcile
                  else "written to the global store")))
    out.append(_ui.kv("ORIGIN", "local copy rewritten as a managed mirror"
               + ("  · old-named file + index pointer removed (rename)" if renamed else "")))
    out.append(_ui.kv("PROVENANCE", f"{project_dir.name} recorded as a holder"))
    out.append("")
    out.append(_ui.kv("NEXT", _ui.c("catalog is generated by upsert; same-domain "
               "projects pick it up on their next --pull", "dim")))
    print(_ui.ascii_translate("\n".join(out)))
    return 0


# ── token observability: per-node cost across the neural network ────────────────
def _label_from_slug(slug: str) -> str:
    """Human label for a node from its slug dir. The slug is the abs path with '/' AND '_' → '-'
    (v0.1.17), so it is EVEN LESS invertible to a basename (a '-' could have been '/', '_', or a
    literal '-'); we do NOT guess a basename — `rsplit('-',1)[-1]` would mislabel any hyphenated project
    (…-consolidate-memory → 'memory'). De-prefix the leading '-' and keep the
    informative tail; unambiguous beats pretty for per-node attribution."""
    # _sane strips terminal control bytes: a node's slug comes from a filesystem dir name
    # that could carry an ANSI escape; this label is printed to the terminal in --tokens.
    s = _sane(slug.lstrip("-"))
    return s if len(s) <= 24 else "…" + s[-23:]


def _node_label(store: Path) -> str:
    return _label_from_slug(session_dir_for_store(store).name)


def _mirror_scope(stem: str, body: str, canon_scope: "dict[str, str] | None") -> str:
    """Scope of one managed mirror: the copy's own frontmatter first, then the canonical
    (a pre-scope mirror still classifies if the global store has the fact). Empty if
    neither is user-global/stack-general — counted in `shared` but not in the split."""
    sc = str(_frontmatter(body).get("scope") or "").strip().strip("\"'")
    if sc not in ("user-global", "stack-general"):
        sc = str((canon_scope or {}).get(stem) or "").strip().strip("\"'")
    return sc if sc in ("user-global", "stack-general") else ""


def _pairwise_stack_edges(by_node: dict) -> list:
    """Compact pairwise stack-general intersections among physical --tokens nodes.
    Labels are the same strings as `nodes[].node`. n=0 pairs are omitted; order is
    stable (weight desc, then names) so a cycle record diffs cleanly."""
    labels = sorted(by_node)
    out: list = []
    for i, a in enumerate(labels):
        sa = by_node.get(a) or set()
        for b in labels[i + 1:]:
            n = len(sa & (by_node.get(b) or set()))
            if n:
                out.append({"a": a, "b": b, "n": n})
    out.sort(key=lambda e: (-int(e["n"]), str(e["a"]), str(e["b"])))
    return out


def _classify_node(store: Path, canon_scope: "dict[str, str] | None" = None, *,
                   canonical_index: "dict | None" = None, holder_domain: str = "",
                   holdings: "dict | None" = None, diagnostics: "dict | None" = None,
                   sid: str = ""
                   ) -> "tuple[dict, set[str], set[str]]":
    """Per-node token cost + the stem sets that split `shared` into everyone-holds vs this-stack.

    Returns `(token_dict, universal_stems, stack_stems)`. The stem sets stay off the JSON
    (they're the input to `_pairwise_stack_edges`); the dict is what `--tokens` emits."""
    idx = store / "MEMORY.md"
    idx_text = _safe_read_text(idx) or ""    # store-scan convention: a vanished index reads as absent
    bodies: dict[str, str] = {}
    for f in store.glob("*.md"):
        if f.name == "MEMORY.md" or _is_reserved_stem(f.stem):
            continue
        body = _safe_read_text(f)             # store-scan convention (shared helper — v0.1.69 Gate-2a)
        if body is None and diagnostics is not None:
            diagnostics["read_failures"] += 1
        # v0.1.76 (audit): exclude ARCHIVE-INDEX docs (link-lists like SHIPPED.md — no frontmatter,
        # ≥3 links) — memory_status's own C1 fact/archive split, applied here too. They were counted
        # as recall facts (a live node's 7.6k-tok SHIPPED.md inflated recall_tokens + `facts`), so
        # --tokens over-reported any store using the archive convention. Same text-level rule
        # (_is_archive_index_text), single source — the two counters cannot drift.
        if body is not None and not _is_archive_index_text(body):
            bodies[f.stem] = body
    mirror_stems = {stem for stem, b in bodies.items() if _is_mirror(b)}
    uni_stems: set[str] = set()
    stk_stems: set[str] = set()
    for stem in mirror_stems:
        sc = _mirror_scope(stem, bodies[stem], canon_scope)
        identity = stem
        if canonical_index is not None:
            resolved = _physical_fact_identity(stem, bodies[stem], holder_domain, canonical_index)
            if resolved is None:
                if diagnostics is not None:
                    diagnostics["unresolved_identities"] += 1
                continue
            identity, fact = resolved
            sc = fact["scope"]
            if holdings is not None:
                holding = holdings.setdefault(identity, {**fact, "holders": set()})
                holding["holders"].add(sid)
        if sc == "user-global":
            uni_stems.add(identity)
        elif sc == "stack-general":
            stk_stems.add(identity)
    # Attribute the index pointer lines whose target fact (`](<stem>.md)`) is a mirror.
    # That is the fraction of the always-loaded tax the global store controls — what the
    # over-budget remedy must actually target. Estimate the matched lines as ONE blob (the
    # same way always_loaded estimates the whole file), NOT a per-line est_tokens sum: the
    # ceiling in est_tokens rounds each line up independently, so a per-line sum can exceed
    # the whole-file total and break the mirror ⊆ total invariant (and render >100%).
    mirror_lines = [ln for ln in idx_text.splitlines()
                    if (m := re.search(r"\]\(([^)]+)\.md\)", ln)) and m.group(1) in mirror_stems]
    mirror_index_tokens = est_tokens("\n".join(mirror_lines))
    return ({
        "always_loaded_tokens": est_tokens(idx_text),
        "mirror_index_tokens": mirror_index_tokens,
        "recall_tokens": sum(est_tokens(b) for b in bodies.values()),
        "facts": len(bodies),                 # readable facts only — a vanished file is not counted
        "shared": len(mirror_stems),
        "universal": len(uni_stems),
        "stack": len(stk_stems),
    }, uni_stems, stk_stems)


def _canonical_identity_index(records: list) -> dict:
    """An unambiguous canonical catalog. Duplicate/contradictory sources fail closed."""
    from fact_schema import stable_fact_id
    index: dict = {}
    for name, fm, _text, _path in records:
        domain = str(fm.get("domain") or "")
        scope = str(fm.get("scope") or "")
        if not domain or scope not in ("user-global", "stack-general"):
            continue
        key = (domain, name)
        fid = stable_fact_id(domain, name)
        row = {"fact_id": fid, "name": name, "domain": domain, "scope": scope}
        invalid = (key in index or fm.get("name", name) != name
                   or fm.get("fact_id", fid) != fid)
        index[key] = None if invalid else row
    return index


def _physical_fact_identity(stem: str, body: str, holder_domain: str, index: dict
                            ) -> "tuple | None":
    """Join physical mirrors using their own stamps/context, never the trigger's domain.

    Legacy '--' keys have two possible interpretations. Accept exactly one catalog
    identity; contradictory stamps and ambiguous keys never create graph edges.
    Local filenames are location, not identity (native and namespaced copies join).
    """
    fm = _frontmatter(body)
    domain = str(fm.get("canonical_domain") or fm.get("domain") or "")
    name = str(fm.get("name") or "")
    ref = str(fm.get("global_ref") or fm.get("# global_ref") or "")
    fid = str(fm.get("canonical_fact_id") or "")
    if (fm.get("canonical_domain") and fm.get("domain")
            and fm["canonical_domain"] != fm["domain"]):
        return None
    candidates = set()
    if domain and name:
        candidates.add((domain, name))
    else:
        key = ref or name or stem
        if domain or holder_domain not in ("", "unknown"):
            candidates.add((domain or holder_domain, key))
        decoded_domain, decoded_name = decode_key(key)
        if decoded_domain and (not domain or domain == decoded_domain):
            candidates.add((decoded_domain, decoded_name))
    matches = [index[k] for k in candidates if index.get(k) is not None]
    if len(matches) != 1:
        return None
    fact = matches[0]
    if fid and fid != fact["fact_id"]:
        return None
    if name and name != fact["name"]:
        return None
    if ref and ref not in (fact["name"], fact["domain"] + "--" + fact["name"]):
        return None
    scope = str(fm.get("scope") or "")
    if scope and scope != fact["scope"]:
        return None
    return fact["fact_id"], fact


def _bounded_fact_holdings(holdings: dict, trigger_sid: str) -> tuple:
    """Bound incidence alone to 120 facts / 2000 references / 64 KiB UTF-8 JSON.

    Exact counts precede limits. A final partial holder list keeps its exact held_n.
    Order is deterministic, prioritizing the trigger, stack scope, then popularity.
    """
    ordered = sorted(holdings.values(), key=lambda f: (
        trigger_sid not in f["holders"], f["scope"] != "stack-general",
        -len(f["holders"]), f["fact_id"]))
    rows: list = []
    refs = 0
    for fact in ordered[:_NETWORK_FACT_CAP]:
        holders = sorted(fact["holders"], key=lambda s: (s != trigger_sid, s))
        row = {k: fact[k] for k in ("fact_id", "name", "domain", "scope")}
        row.update(held_n=len(holders), holder_sids=holders[:max(0, _NETWORK_HOLDER_CAP-refs)])
        while row["holder_sids"] and _network_incidence_bytes(rows + [row]) > _NETWORK_INCIDENCE_BYTES:
            row["holder_sids"].pop()
        if not row["holder_sids"]:
            break
        rows.append(row)
        refs += len(row["holder_sids"])
        if len(row["holder_sids"]) < len(holders):
            break
    return rows, {"facts_total": len(holdings), "facts_emitted": len(rows),
                  "holder_refs_total": sum(len(f["holders"]) for f in holdings.values()),
                  "holder_refs_emitted": refs,
                  "incidence_bytes": _network_incidence_bytes(rows)}


def _fleet_display_names(ctx) -> dict:
    """Readable names are optional registry evidence, separate from store join keys."""
    try:
        from control_plane import connect_if_exists, db_path
        conn = connect_if_exists(db_path(ctx))
        if conn is None:
            return {}
        try:
            names: dict = {}
            for row in conn.execute("SELECT native_memory_dir, display_name FROM projects WHERE status='enrolled'"):
                if row["native_memory_dir"] and row["display_name"]:
                    key = str(Path(row["native_memory_dir"]).resolve())
                    names.setdefault(key, set()).add(str(row["display_name"]))
            return {k: next(iter(v)) for k, v in names.items() if len(v) == 1}
        finally:
            conn.close()
    except Exception:
        return {}


def _node_tokens(store: Path, canon_scope: "dict[str, str] | None" = None) -> dict:
    """ESTIMATED token cost of one node's auto-memory: the always-loaded index plus the
    recall-fact pool. Tokens are ≈ chars/4 (est_tokens) — an estimate, not exact.

    Also ATTRIBUTES the always-loaded index cost to mirror-vs-local pointers
    (`mirror_index_tokens`): the share of the per-session tax driven by replicated
    cross-project facts (`global_ref:` mirrors). This is the load-bearing signal when an
    index goes over budget — a mirror-dominated overflow's only effective lever is the
    canonical in the GLOBAL store (demote/delete + GC fleet-wide); LOCAL pruning is
    futile because `run()` re-pulls the mirror next cycle.

    `universal` / `stack` split `shared` by the mirror's scope (copy first, canonical
    fallback): everyone-holds vs this-stack. Project-local facts stay in `facts` only."""
    d, _, _ = _classify_node(store, canon_scope)
    return d


def _network_nodes(*, allow_fixture_paths: bool = False) -> list[Path]:
    """Network nodes = project memory stores holding ≥1 shared (`global_ref:`) mirror.

    This is the PHYSICAL, measurable node set (we have each store's path, so we can
    weigh its tokens). It deliberately differs from network()'s LOGICAL `minds` set
    (derived from provenance basenames, which can't be inverted to a store path) — the
    two views can diverge (names vs slugs); --network = topology, --tokens = cost."""
    nodes: list[Path] = []
    for store in iter_native_stores(allow_fixture_paths=allow_fixture_paths):
        has_mirror = False
        try:
            files = store.glob("*.md")
        except OSError:
            continue
        for f in files:
            if f.name == "MEMORY.md" or _is_reserved_stem(f.stem):
                continue
            body = _safe_read_text(f)         # store-scan convention (shared helper — v0.1.69 Gate-2a)
            if body is not None and _is_mirror(body):
                has_mirror = True
                break
        if has_mirror:
            nodes.append(store)
    return nodes


def _fleet_overlay(project_dir: Path) -> tuple:
    """(store-path → (domain, [project_ids]), trigger_memberships, all_group_names) —
    the registry attribution for the fleet basis (fleet-topology-ui spec §2.1):
    the disk-first node set gets its domain + group membership from the SQLite
    registry, keyed by each store's RESOLVED path. Degrades to empty on a
    missing/unhealthy registry (attribution is overlay, enumeration is disk)."""
    _overlay: dict = {}
    _trig_mem: set = set()
    _all_groups: list = []
    try:
        from store_context import resolve_store as _rs_fo
        from control_plane import connect_if_exists as _cife_fo, db_path as _dbp_fo
        _ctx_fo = _rs_fo(Path(project_dir))
        _conn = _cife_fo(_dbp_fo(_ctx_fo))
        if _conn is None:
            return _overlay, _trig_mem, _all_groups
        try:
            _rows = _conn.execute(
                "SELECT project_id, domain_id, native_memory_dir FROM projects "
                "WHERE status='enrolled'").fetchall()
            _mems = _conn.execute(
                "SELECT gm.project_id, g.name, g.domain_id FROM group_members gm "
                "JOIN groups g ON g.group_id = gm.group_id").fetchall()
            _trid = str(getattr(_ctx_fo, "project_id", "") or "")
            for r in _rows:
                _nm = str(r["native_memory_dir"] or "")
                if not _nm:
                    continue
                try:
                    _k = str(Path(_nm).expanduser().resolve())
                except OSError:
                    _k = _nm
                _dom_pids = _overlay.setdefault(_k, (str(r["domain_id"] or ""), []))
                if _dom_pids[0] != str(r["domain_id"] or ""):
                    _dom_pids = ("unknown", _dom_pids[1])
                    _overlay[_k] = _dom_pids
                _dom_pids[1].append(str(r["project_id"] or ""))
            for r in _mems:
                _g = str(r["name"] or "")
                if _g and _g not in [x[0] for x in _all_groups]:
                    _all_groups.append((_g, str(r["domain_id"] or "")))
                if str(r["project_id"] or "") == _trid:
                    _trig_mem.add(_g)
        finally:
            _conn.close()
    except Exception:
        _overlay = {}
        _trig_mem = set()
        _all_groups = []
    return _overlay, _trig_mem, _all_groups


def _registry_holder_count(ctx, stem: str, fact_dom: str) -> int:
    """DISTINCT holder projects for a canonical (review MED-1) — the honesty
    datum for universal_facts.held. Labels dedupe only for DISPLAY; the count
    must not merge two same-basename checkouts."""
    try:
        from control_plane import connect_if_exists as _cife_hc, db_path as _dbp_hc, \
            stable_fact_id as _sfid_hc
        _conn = _cife_hc(_dbp_hc(ctx))
        if _conn is None:
            return 0
        try:
            _fid = _sfid_hc(fact_dom or getattr(ctx, "domain_id", "") or "unknown", stem)
            _r = _conn.execute(
                "SELECT COUNT(DISTINCT h.project_id) AS n FROM holders h "
                "WHERE h.fact_id=?", (_fid,)).fetchone()
            return int(_r["n"]) if _r is not None else 0
        finally:
            _conn.close()
    except Exception:
        return 0


def _fleet_group_rows(project_dir: Path) -> dict:
    """group name → {home_domain, member_project_ids} — every operator-granted
    group (the routed-link layer). Degrades to {} without a registry."""
    out: dict = {}
    try:
        from store_context import resolve_store as _rs_fg
        from control_plane import connect_if_exists as _cife_fg, db_path as _dbp_fg
        _ctx_fg = _rs_fg(Path(project_dir))
        _conn = _cife_fg(_dbp_fg(_ctx_fg))
        if _conn is None:
            return out
        try:
            for r in _conn.execute(
                    "SELECT g.name, g.domain_id, gm.project_id FROM groups g "
                    "JOIN group_members gm ON gm.group_id = g.group_id").fetchall():
                _g = str(r["name"] or "")
                _row = out.setdefault(_g, {"home_domain": str(r["domain_id"] or ""),
                                           "member_project_ids": []})
                _row["member_project_ids"].append(str(r["project_id"] or ""))
        finally:
            _conn.close()
    except Exception:
        return {}
    return out


def _disambiguate_labels(nodes: list, sids: dict) -> None:
    """HIGH-1 (fleet-topology-ui spec): the 24-char truncated label is
    non-injective — two stores can collide on one label and silently merge.
    Colliding labels get a head suffix from THAT ROW'S OWN sid (review
    BLOCKS-1: the first-wins map gave every collider the same suffix, so the
    set stayed non-unique), extended while any collision remains."""
    counts: dict = {}
    for row in nodes:
        counts[str(row.get("node") or "")] = counts.get(str(row.get("node") or ""), 0) + 1
    for row in nodes:
        _lab = str(row.get("node") or "")
        if counts.get(_lab, 0) <= 1:
            continue
        _sid = str(row.get("sid") or "") or sids.get(_lab, "")   # the ROW's own sid
        # a short digest, not the head — two colliding sids often SHARE the
        # head (both "-home-you-…"), and the suffix must differ where the
        # sids do (review BLOCKS-1's follow-up; the pin caught the head form).
        _head = hashlib.sha1(_sid.encode("utf-8")).hexdigest()[:4]
        row["node"] = f"{_lab}·{_head}"
    # assert uniqueness (the spec's contract): extend the suffix while any
    # collision remains — pathological only, but the promise is unconditional.
    _again: dict = {}
    for row in nodes:
        _l2 = str(row.get("node") or "")
        _again[_l2] = _again.get(_l2, 0) + 1
    for row in nodes:
        _l2 = str(row.get("node") or "")
        if _again.get(_l2, 0) <= 1:
            continue
        _sid = str(row.get("sid") or "") or _l2
        row["node"] = f"{_l2}#{hashlib.sha1(_sid.encode('utf-8')).hexdigest()[:12]}"


def token_network(project_dir: Path, *, fleet: bool = False,
                  fleet_full: bool = False) -> dict:
    """Build the `network` block of the cycle record: per-node ESTIMATED token cost
    across every node in the shared-memory network, with the triggering node flagged.

    Also splits mixed `shared` into everyone-holds (`universal`) vs this-stack (`stack`)
    and emits compact `stack_edges` (pairwise stack-general intersections among these
    physical nodes). The HTML graph draws those edges; it does not invent topology
    from live disk at render time. `--network` remains the logical-provenance view
    (documented divergence: minds vs stores-with-mirrors).

    `fleet=True` (fleet-topology-ui spec §2.1) emits the FLEET basis: the
    whole-installation node set (disk-first, registry-overlaid) with per-node
    `domain`/`groups`/`sid`, `domains`, `universal_facts` (capped), `group_links`
    scoped to the TRIGGER's own groups (fleet_full widens to the operator's full
    set), `stack_edge_facts` (the drawn-chord set, capped), and
    `basis_scope: "fleet"`. The domain basis (fleet=False) is byte-shaped as
    before — the additive keys never touch it."""
    project_dir = project_dir.resolve()
    trigger_store = project_store(project_dir)
    from store_context import resolve_store as _rs_tok
    _ctx_tok = _rs_tok(project_dir)
    _holdings: dict = {}
    _diagnostics = {"unresolved_identities": 0, "read_failures": 0}
    _identity_index: dict = {}
    _display_names: dict = {}
    if fleet:
        _identity_index = _canonical_identity_index(_all_domain_records())
        _display_names = _fleet_display_names(_ctx_tok)
        canon_scope = {}
    else:
        canon_scope = {n: str(fm.get("scope") or "") for n, fm, _ in facts_for_context(_ctx_tok)}
    if fleet:
        _tok_nodes = list(_network_nodes(allow_fixture_paths=(
            _global_is_fixture() or _hermetic_home())))
        _overlay, _trig_mem, _all_groups = _fleet_overlay(project_dir)
        _group_rows = _fleet_group_rows(project_dir)
        _pid_groups: dict = {}
        for _g, _r in _group_rows.items():
            for _pid in _r["member_project_ids"]:
                _pid_groups.setdefault(_pid, []).append(_g)
    elif _global_is_fixture():
        _tok_nodes = list(_network_nodes())
    else:
        _tok_nodes = list(_same_domain_stores(_ctx_tok))
    if trigger_store.is_dir():
        try:
            _trig_k = str(trigger_store.resolve())
        except OSError:
            _trig_k = str(trigger_store)
        _have = set()
        for _s in _tok_nodes:
            try:
                _have.add(str(_s.resolve()))
            except OSError:
                _have.add(str(_s))
        if _trig_k not in _have:
            _tok_nodes.append(trigger_store)
    _collected = []   # (store, is_trigger, row, stk_stems, uni_stems, sid)
    nodes = []
    stack_by: dict = {}
    uni_all: set = set()
    stk_all: set = set()
    al_total = rc_total = mir_total = 0
    _label_sids: dict = {}
    for store in _tok_nodes:
        is_trigger = store.resolve() == trigger_store.resolve()
        label = _sane(project_dir.name) if is_trigger else _node_label(store)
        try:
            sid = session_dir_for_store(store).name
        except OSError:
            sid = label
        _store_key = str(store.resolve())
        _holder_domain = _overlay.get(_store_key, ("unknown", []))[0] if fleet else ""
        m, uni_stems, stk_stems = _classify_node(
            store, canon_scope, canonical_index=_identity_index if fleet else None,
            holder_domain=_holder_domain, holdings=_holdings if fleet else None,
            diagnostics=_diagnostics if fleet else None, sid=sid)
        _label_sids[label] = _label_sids.get(label) or sid
        row = {
            # _sane the trigger label too — it's the argv-supplied project_dir.name
            "node": label,
            "trigger": is_trigger,
            **m,
        }
        if fleet:
            try:
                _k = str(store.resolve())
            except OSError:
                _k = str(store)
            _dom, _pids = _overlay.get(_k, ("unknown", []))
            row["domain"] = _dom or "unknown"
            row["groups"] = sorted({g for _pid in _pids
                                    for g in _pid_groups.get(_pid, [])})
            row["sid"] = sid
            # display_name is ALWAYS present (the schema contract): a registry miss
            # degrades to the node label — never a missing key (macOS CI: the resolved
            # key form must match _fleet_display_names' resolve() both sides)
            row["display_name"] = _display_names.get(_store_key) or label
        _collected.append((store, is_trigger, row, stk_stems, sid))
        stack_by[label] = stk_stems
        uni_all |= uni_stems
        stk_all |= stk_stems
        al_total += m["always_loaded_tokens"]
        rc_total += m["recall_tokens"]
        mir_total += m["mirror_index_tokens"]
    if fleet:
        # review HIGH-1: the trigger must be FIRST — the painter draws the
        # first 16 rows with index 0 as the hub, and a trigger sliced away
        # would make a random peer the visual center.
        _collected.sort(key=lambda t: (not t[1], str(t[2].get("node") or "")))
        # HIGH-1: disambiguate colliding labels BEFORE the edge join keys are
        # built — two stores must never merge into one label in stack_edges.
        _disambiguate_labels([r for _, _, r, _, _ in _collected], _label_sids)
        stack_by = {r["node"]: stk for _, _, r, stk, _ in _collected}
    nodes = [r for _, _, r, _, _ in _collected]
    result = {
        "basis": "≈ chars/4 (heuristic estimate, not a tokenizer)",
        "node_def": "project stores holding ≥1 shared fact",
        "trigger": _sane(project_dir.name),
        "nodes": nodes,
        "stack_edges": _pairwise_stack_edges(stack_by),
        # mirror_index_tokens: the share of the always-loaded total controlled by the
        # GLOBAL store (replicated mirrors) — the lever for a mirror-dominated overflow.
        # universal/stack here are UNIQUE stems across the physical node set (not a sum —
        # summing would count the same baseline fact once per holder).
        "totals": {"nodes": len(nodes), "always_loaded_tokens": al_total,
                   "mirror_index_tokens": mir_total, "recall_tokens": rc_total,
                   "universal": len(uni_all), "stack": len(stk_all)},
    }
    if fleet:
        result["basis_scope"] = "fleet"
        result.update(_fleet_layers(project_dir, _ctx_tok, result, stack_by,
                                    _trig_mem, _all_groups, _group_rows,
                                    fleet_full=fleet_full))
        # Compatibility names remain readable; intersections above use stable ids.
        for edge in result["stack_edge_facts"]:
            edge["names"] = [_holdings[f]["name"] if f in _holdings else f for f in edge["names"]]
        trigger_sid = next((r["sid"] for r in nodes if r.get("trigger")), "")
        incidence, counts = _bounded_fact_holdings(_holdings, trigger_sid)
        result["fact_holdings"] = incidence
        result["capture"] = {"basis": "physical shared mirrors plus triggering store",
                             "group_scope": "all" if fleet_full else "trigger",
                             "read_failure_scope": "captured native fact files",
                             **counts, **_diagnostics}
    return result


def _fleet_layers(project_dir: Path, ctx, result: dict, stack_by: dict,
                  trig_mem: set, all_groups: list, group_rows: dict, *,
                  fleet_full: bool) -> dict:
    """The fleet basis' additive layers (fleet-topology-ui spec §2.1), all
    emission-side capped (§3 BLOCK-2)."""
    from fact_schema import _parse_flow_list as _pfl_fl
    _nodes = result["nodes"]
    _all_recs = _all_domain_records()
    # domains: the VLAN layer — names only; membership is DERIVED at render
    # time from the per-node `domain` attribution (the record stays DRY —
    # BLOCK-2's size budget; a members list would duplicate nodes[]).
    domains = [{"domain": d} for d in sorted({str(r.get("domain") or "unknown")
                                              for r in _nodes})]
    # universals: every user-global canonical with its holder count, PARTIALS
    # first (the honest "only 2/11 so far"), capped at 24.
    _uni_rows = []
    for n, fm, _t, _p in _all_recs:
        if str(fm.get("scope") or "") != "user-global":
            continue
        # review MED-1: count DISTINCT holder PROJECTS — _holder_labels
        # dedupes by display_name, so two same-basename checkouts holding one
        # canonical would read held=1 of 2 (the exact duplicate population
        # this layer exists to surface).
        _held = _registry_holder_count(ctx, n, str(fm.get("domain") or ""))
        _uni_rows.append({"name": n, "domain": str(fm.get("domain") or ""),
                          "held": _held})
    _uni_rows.sort(key=lambda u: (int(u["held"]), str(u["name"])))
    universal_facts = _uni_rows[:24]
    # stack_edge_facts: the DRAWN-chord set (S1 — the painter's deterministic
    # filter mirrored at emission), names capped at 5.
    _edges = _pairwise_stack_edges(stack_by)
    _label_to_stems = stack_by
    # review C: the trigger's FINAL label (post-disambiguation — a colliding
    # trigger row carries a digest suffix the raw `trigger` field lacks)
    _trig = next((str(r.get("node") or "") for r in _nodes if r.get("trigger")),
                 str(result.get("trigger") or ""))
    _spoke = {}
    for e in _edges:
        if e["a"] == _trig:
            _spoke[e["b"]] = int(e["n"])
        elif e["b"] == _trig:
            _spoke[e["a"]] = int(e["n"])
    # review MED-2: the painter draws chords only among the first 16 nodes
    # (the trigger first) — mirror that slice so the emitted set IS the
    # drawn-chord set, exactly the painter's preconditions.
    _drawn_labels = {str(r.get("node") or "") for r in _nodes[:16]}
    stack_edge_facts = []
    for e in _edges:
        if (e["a"] not in _drawn_labels or e["b"] not in _drawn_labels
                or e["a"] == _trig or e["b"] == _trig):
            continue
        _pn = int(e["n"])
        if _pn <= max(_spoke.get(e["a"], 0), _spoke.get(e["b"], 0)):
            continue
        _names = sorted((_label_to_stems.get(e["a"]) or set())
                        & (_label_to_stems.get(e["b"]) or set()))[:5]
        stack_edge_facts.append({"a": e["a"], "b": e["b"], "names": _names})
    # group_links: the routed-link layer — the trigger's own groups by default
    # (the share-safe archive basis), the operator's full set under fleet_full.
    _groups = sorted(trig_mem) if not fleet_full else sorted(
        {g for g, _d in all_groups})
    _recips_by_group: dict = {}
    for n, fm, _t, _p in _all_recs:
        for _g in _pfl_fl(str(fm.get("recipients") or "")):
            _recips_by_group.setdefault(_g, []).append(
                {"name": n, "domain": str(fm.get("domain") or "")})
    _links = []
    for _g in _groups:
        _row = group_rows.get(_g)
        if _row is None:
            continue
        # membership is DERIVED at render time from the per-node `groups`
        # attribution (the record stays DRY — BLOCK-2); the link carries the
        # routed FACTS, the layer's payload.
        _members_n = sum(1 for r in _nodes if _g in (r.get("groups") or []))
        _links.append({"group": _g, "home_domain": _row["home_domain"],
                       "members_n": _members_n,
                       "facts_total": len(_recips_by_group.get(_g) or []),
                       "facts": (_recips_by_group.get(_g) or [])[:8]})
    _links.sort(key=lambda L: int(L["members_n"]), reverse=True)
    group_links = _links[:6]
    return {"domains": domains, "universal_facts": universal_facts,
            "group_links": group_links, "stack_edge_facts": stack_edge_facts}


def token_report(project_dir: Path, as_json: bool, *, fleet: bool = False,
                 fleet_full: bool = False) -> int:
    import json
    net = token_network(project_dir, fleet=fleet, fleet_full=fleet_full)
    if as_json:
        print(json.dumps(net, indent=2))
        return 0
    t = net["totals"]
    out: list = []
    title = "✦ NEURAL NETWORK · token cost across all nodes"
    tag = f"{t['nodes']} nodes"
    gap = max(2, _ui.W - 2 - len(title) - len(tag))
    out.append(_ui.rule())
    out.append("  " + _ui.c("✦", "cyan") + title[1:] + " " * gap + _ui.c(tag, "bold"))
    out.append("  " + _ui.c(f"trigger: {net['trigger']} · {net['basis']}", "dim"))
    out.append(_ui.rule())
    out.append("")
    out.append(_ui.kv("TOTAL", f"≈{t['always_loaded_tokens']} always-loaded "
               + _ui.c("(paid every session, every node)", "dim") + f" · ≈{t['recall_tokens']} recall-pool"))
    mir = t.get("mirror_index_tokens", 0)
    if mir:
        pct = round(100 * mir / t["always_loaded_tokens"]) if t["always_loaded_tokens"] else 0
        out.append("    " + _ui.c(f"of which ≈{mir} ({pct}%) mirror-driven — lever is the GLOBAL store (demote/GC), NOT local prune", "dim"))
    if t.get("universal") is not None or t.get("stack") is not None:
        out.append("    " + _ui.c(f"{t.get('universal', 0)} baseline · {t.get('stack', 0)} this-stack "
                                 "(everyone-holds vs facts only some share — topology is --network)", "dim"))
    out.append("")
    out.append(_ui.kv("NODES", _ui.c("per-project always-loaded + recall-pool cost", "dim")))
    for n in sorted(net["nodes"], key=lambda d: -d["always_loaded_tokens"]):
        share = f"({n['shared']} shared"
        if n.get("universal") is not None or n.get("stack") is not None:
            share += f" · {n.get('universal', 0)} baseline · {n.get('stack', 0)} this-stack"
        share += ")"
        base = (f"    {_ui.lbl(n['node'][:24], 24)} always ≈{n['always_loaded_tokens']:>5} "
                + _ui.c(f"(≈{n.get('mirror_index_tokens', 0)} mirror)", "dim")
                + f" · recall ≈{n['recall_tokens']:>6} · {n['facts']:>2} facts "
                + _ui.c(share, "dim"))
        if n["trigger"]:  # keep the dense node columns intact — drop the mark to a hanging line only if it would overflow
            mk = _ui.c("◀ trigger", "cyan")
            base += "  " + mk if _ui.vis(base) + 11 <= _ui.W else "\n" + " " * 29 + mk
        out.append(base)
    if not net["nodes"]:
        out.append("  " + _ui.c("(no nodes hold shared facts yet — run --pull somewhere first)", "dim"))
    print(_ui.ascii_translate("\n".join(out)))
    return 0


# ── v0.1.83: fleet WORKFLOWS — the --utility twin over the W-A distill rows (W-B) ───────────────
def _log_nodes() -> "list[Path]":
    """Node set for the workflow lens: every project store holding a .consolidation-log.jsonl —
    deliberately NOT _network_nodes() (holding a MIRROR is orthogonal to having DREAMED; a node
    with distill evidence may hold no mirrors, and vice versa — the same documented-divergence
    discipline as _network_nodes vs network()'s logical minds)."""
    from retention import cycle_log_write_path as _clp
    out: list = []
    for store in iter_native_stores():
        if ((store / ".consolidation-log.jsonl").is_file()
                or _clp(store).is_file()):
            out.append(store)
    return out


def fleet_workflows(project_dir: Path) -> dict:
    """READ-ONLY fleet workflow evidence (docs/fleet-workflows.spec.md — W-B): join each node's
    LATEST W-A distill rows (distill_history — latest-record-per-node, the overlapping-window
    consumer trap designed against at W-A) by EXACT template string. Emits:
      templates/chains — per key: nodes (BREADTH, the workflow analog of the cascade's G2.3
        named-other-project witness — the first cascade leg with mechanical evidence), total n
        (sum of latest-window counts), fleet d = MIN of per-node day-spreads (a 3d+1d pair is
        1d — both sides must have spread; max would let the loudest node infect a one-shot
        partner), per-node breakdown. `fleet` flag = ≥2 distinct nodes (structural, like
        MIN_RECUR — nothing fitted).
      families — head-signature (first two template tokens) groupings across ≥2 nodes: a
        near-join HINT for same-tool-different-flags drift; counts NEVER merged (a merged count
        across distinct templates would be a fabricated number).
      used — the Skill-adoption tallies, summed latest-per-node (the W-C quadrant's numerator).
      verdicts — every node's distill disposition lineage (verdict/proposed/created) — what makes
        the SKILL's materially-new-evidence DECLINE rule checkable fleet-wide instead of per-node.
      inventory — the harness artifacts distillation would target: ~/.claude/skills/*/ names +
        ~/.claude/commands/*.md stems (existence + name only — coverage judgment stays with the
        MODEL, content-gated: a name match proves nothing about semantic coverage).
    Cold-start honesty: nodes_reporting counts nodes whose latest block carries rows (v0.1.82+);
    the report renders the denominator loudly — fleet absence is never inferred from missing
    instrumentation (the zero-reads bias, transposed). Decisions stay report-then-apply."""
    project_dir = project_dir.resolve()
    from store_context import resolve_store as _rs_wf
    _ctx_wf = _rs_wf(project_dir)
    if _global_is_fixture():
        stores = _log_nodes()
    elif getattr(_ctx_wf, "cross_project_allowed", False):
        allowed = {s.resolve() for s in _same_domain_stores(_ctx_wf)}
        stores = [s for s in _log_nodes() if s.resolve() in allowed]
    else:
        stores = []
    trig = project_store(project_dir)
    if trig.is_dir() and trig.resolve() not in {s.resolve() for s in stores}:
        stores.append(trig)
    tpl: dict = {}
    chains: dict = {}
    used: dict = {}
    verdicts: list = []
    proposal_declines: list = []
    nodes_reporting = 0
    node_states: list = []   # v0.1.87/W-C1 (D-8): legacy | instrumented_empty | reporting
    for store in stores:
        label = _node_label(store)
        hist = distill_history(store)
        for v in hist["verdicts"]:
            verdicts.append({"node": label, **v})
        for v in hist.get("proposal_declines") or []:
            proposal_declines.append({"node": label, **v})
        latest = hist["latest"]
        if not isinstance(latest, dict):
            node_states.append({"node": label, "state": "legacy"})
            continue
        _rows = (latest.get("top") or []) or (latest.get("top_chains") or []) or (latest.get("used") or [])
        if _rows:
            node_states.append({"node": label, "state": "reporting"})
        else:
            node_states.append({"node": label, "state": "instrumented_empty"})
        nodes_reporting += 1
        for r in latest.get("top", []):
            if not (isinstance(r, dict) and isinstance(r.get("t"), str) and r["t"]):
                continue
            e = tpl.setdefault(r["t"], {"nodes": [], "n": 0, "per_node": {}, "per_node_d": {}})
            if label not in e["nodes"]:
                e["nodes"].append(label)
            n = r.get("n", 0)
            n = n if isinstance(n, int) and not isinstance(n, bool) and n > 0 else 0
            d = r.get("d", 0)
            d = d if isinstance(d, int) and not isinstance(d, bool) and d > 0 else 0
            e["n"] += n
            e["per_node"][label] = n
            e["per_node_d"][label] = d
        for r in latest.get("top_chains", []) if isinstance(latest.get("top_chains"), list) else []:
            t = r.get("t") if isinstance(r, dict) else None
            if not (isinstance(t, list) and len(t) == 2 and all(isinstance(x, str) for x in t)):
                continue
            key = " → ".join(t)
            e = chains.setdefault(key, {"nodes": [], "n": 0, "per_node_d": {}})
            if label not in e["nodes"]:
                e["nodes"].append(label)
            n = r.get("n", 0)
            e["n"] += n if isinstance(n, int) and not isinstance(n, bool) and n > 0 else 0
            d = r.get("d", 0)
            d = d if isinstance(d, int) and not isinstance(d, bool) and d > 0 else 0
            e["per_node_d"][label] = d
        for r in latest.get("used", []) if isinstance(latest.get("used"), list) else []:
            if isinstance(r, dict) and isinstance(r.get("a"), str) and r["a"]:
                u = used.setdefault(r["a"], {"nodes": [], "n": 0})
                if label not in u["nodes"]:
                    u["nodes"].append(label)
                n = r.get("n", 0)
                u["n"] += n if isinstance(n, int) and not isinstance(n, bool) and n > 0 else 0
    families: dict = {}
    for t, e in tpl.items():
        head = " ".join(t.split()[:2])
        f = families.setdefault(head, {"templates": [], "nodes": set()})
        f["templates"].append(t)
        f["nodes"].update(e["nodes"])
    fam_out = [{"head": h, "templates": sorted(f["templates"]), "nodes": sorted(f["nodes"])}
               for h, f in families.items()
               if len(f["templates"]) >= 2 and len(f["nodes"]) >= 2]
    fam_out.sort(key=lambda f: (-len(f["nodes"]), f["head"]))

    def _min_d(per_node_d: dict) -> int:
        ds = [v for v in per_node_d.values()
              if isinstance(v, int) and not isinstance(v, bool) and v > 0]
        return min(ds) if ds else 0

    tpl_out = [{"template": t, "nodes": sorted(e["nodes"]), "n": e["n"], "d": _min_d(e["per_node_d"]),
                "per_node": e["per_node"], "per_node_d": e["per_node_d"],
                "fleet": len(e["nodes"]) >= 2} for t, e in tpl.items()]
    tpl_out.sort(key=lambda r: (-len(r["nodes"]), -r["d"], -r["n"], r["template"]))
    chain_out = [{"chain": k, "nodes": sorted(e["nodes"]), "n": e["n"], "d": _min_d(e["per_node_d"]),
                  "per_node_d": e["per_node_d"],
                  "fleet": len(e["nodes"]) >= 2} for k, e in chains.items()]
    chain_out.sort(key=lambda r: (-len(r["nodes"]), -r["d"], -r["n"], r["chain"]))
    used_out = [{"skill": k, "nodes": sorted(u["nodes"]), "n": u["n"]} for k, u in used.items()]
    used_out.sort(key=lambda r: (-r["n"], r["skill"]))
    inv: dict = {"skills": [], "commands": []}
    _sk_dir = Path.home() / ".claude" / "skills"
    if _sk_dir.is_dir():
        inv["skills"] = sorted(d.name for d in _sk_dir.iterdir()
                               if d.is_dir() and (d / "SKILL.md").is_file())
    _cmd_dir = Path.home() / ".claude" / "commands"
    if _cmd_dir.is_dir():
        inv["commands"] = sorted(f.stem for f in _cmd_dir.glob("*.md"))
    return {"nodes": len(stores), "nodes_reporting": nodes_reporting, "node_states": node_states,
            "templates": tpl_out, "chains": chain_out, "families": fam_out,
            "used": used_out, "verdicts": verdicts, "proposal_declines": proposal_declines,
            "inventory": inv}


def registrar_report(project_dir: Path, as_json: bool, into: "str | None" = None) -> int:
    """v0.1.87/W-C1 (docs/wc-registrar.spec.md): the registrar's Tier-2 MECHANICAL gate cascade
    over the W-B join — fleet-wide placement candidates and what blocks them.

    Per candidate (templates AND chains): distinctive = not ordinary git/gh / not a bare
    interpreter --flag; fleet_recurrence = ≥2 distinct nodes (structural); day_spread =
    fleet d ≥ 2 where fleet d is the MIN of per-node day-spreads (a 3d+1d pair is 1d —
    the loudest node cannot infect a one-shot partner). The MODEL-judged legs
    (stable inputs · coverage · decline lineage vs the decline-anchors) are LISTED, never
    evaluated — the engine never fabricates a model-leg verdict (no-failure-masking law).
    READ-ONLY: proposals stay report-then-apply; nothing here writes an artifact.

    Emits: {nodes, nodes_reporting, node_states (legacy|instrumented_empty|reporting — D-8),
            candidates: [{candidate, form, evidence:{nodes,d,n},
                          gates:{mechanical:{fleet_recurrence,day_spread,distinctive},
                                 model_judged:[...]}, disposition}],
            decline_anchors: [{node, verdict, top:[{t,n,d}], top_chains:[...]}] (D-2.5)}."""
    import json as _json
    project_dir = project_dir.resolve()
    if not project_dir.is_dir():
        print(f"error: project dir {project_dir} does not exist — refusing (phantom-store guard)", file=sys.stderr)
        return 2
    w = fleet_workflows(project_dir)
    model_legs = ["stable_inputs", "coverage", "decline_lineage"]
    candidates: list = []

    def _eval(nodes: list, d: int, candidate: str, form: str) -> "tuple[str, bool, bool, bool]":
        fleet = len(nodes) >= 2
        spread = d >= 2
        distinctive = _is_distinctive_template(candidate, form)
        # Mechanical flags stay independent (no-failure-masking). Disposition is the
        # first failing gate: generic-cli, then fleet-recurrence, then day-spread.
        if not distinctive:
            disp = "blocked: generic-cli"
        elif fleet and spread:
            disp = "fleet-candidate"
        elif not fleet:
            disp = "blocked: fleet-recurrence"
        else:
            disp = "blocked: day-spread"
        return disp, fleet, spread, distinctive

    for r in w["templates"]:
        disp, fleet, spread, distinctive = _eval(r["nodes"], r["d"], r["template"], "command")
        candidates.append({"candidate": r["template"], "form": "command",
                           "evidence": {"nodes": r["nodes"], "d": r["d"], "n": r["n"]},
                           "gates": {"mechanical": {"fleet_recurrence": fleet, "day_spread": spread,
                                                    "distinctive": distinctive},
                                     "model_judged": model_legs},
                           "disposition": disp})
    for r in w["chains"]:
        disp, fleet, spread, distinctive = _eval(r["nodes"], r["d"], r["chain"], "chain")
        candidates.append({"candidate": r["chain"], "form": "chain",
                           "evidence": {"nodes": r["nodes"], "d": r["d"], "n": r["n"]},
                           "gates": {"mechanical": {"fleet_recurrence": fleet, "day_spread": spread,
                                                    "distinctive": distinctive},
                                     "model_judged": model_legs},
                           "disposition": disp})
    candidates.sort(key=lambda c: (c["disposition"] != "fleet-candidate",
                                   -len(c["evidence"]["nodes"]), -c["evidence"]["d"],
                                   -c["evidence"]["n"], c["candidate"]))
    anchors: list = []
    seen_anch: set = set()
    for v in list(w["verdicts"]) + list(w.get("proposal_declines") or []):
        ev = v.get("decline_evidence")
        if not isinstance(ev, dict):
            continue
        def _row_t(r: object) -> object:
            t = r.get("t") if isinstance(r, dict) else r
            return tuple(t) if isinstance(t, list) else t
        key = (v.get("node"), v.get("verdict"),
               tuple(_row_t(r) for r in (ev.get("top") or []) + (ev.get("top_chains") or [])))
        if key in seen_anch:
            continue
        seen_anch.add(key)
        anchors.append({"node": v["node"], "verdict": v["verdict"],
                        "top": ev.get("top", []), "top_chains": ev.get("top_chains", [])})
    out = {"nodes": w["nodes"], "nodes_reporting": w["nodes_reporting"],
           "node_states": w["node_states"], "candidates": candidates,
           "decline_anchors": anchors}
    if into:
        # v0.1.87/W-C (D-7): SCRIPT-TRUTH injection — the mechanical evidence lands in the seed's
        # workflow_proposals block; the MODEL writes only disposition + genericized name + verdict
        # per row (counts are never hand-mirrored — the distill --from/--into discipline).
        import json as _json
        try:
            seed = _json.loads(Path(into).read_text(encoding="utf-8"))
            if not isinstance(seed, dict):
                print(f"error: seed {into} is not a JSON object — refusing (no partial injection)", file=sys.stderr)
                return 2
            block = seed.get("workflow_proposals")
            if not isinstance(block, dict):
                if "workflow_proposals" in seed:
                    # the validator would have warned on the wrong container — the injection
                    # pre-empts it; say so rather than silently dropping the old contents
                    print(f"warning: existing workflow_proposals is not a dict — replacing", file=sys.stderr)
                block = {}
            # MERGE on (candidate, form): a re-consult refreshes the script-truth evidence and
            # PRESERVES the model-written disposition/name per row (the split-ownership contract —
            # a wholesale replace would silently destroy confirmed/declined verdicts).
            # Persist ALL fleet-candidates + a capped DISTINCTIVE day-spread sample
            # (the near-join). Generic-cli and single-node rows are counts only —
            # persisting them invited the model to stamp declined on smoke.py.
            # n_* carry the full join sizes so the header stays honest.
            _old_rows = {(r.get("candidate"), r.get("form")): r
                         for r in block.get("candidates", []) if isinstance(r, dict)}
            _fleet_src = [c for c in candidates if c.get("disposition") == "fleet-candidate"]
            _spread_src = [c for c in candidates
                           if c.get("disposition") == "blocked: day-spread"
                           and (c.get("gates") or {}).get("mechanical", {}).get("distinctive") is True]
            _persist = _fleet_src + _spread_src[:_REGISTRAR_BLOCKED_CAP]
            _merged = []
            _kept = set()
            for c in _persist:
                _row = {"candidate": c["candidate"], "form": c["form"],
                        "evidence": c["evidence"], "mechanical": c["gates"]["mechanical"]}
                _key = (c["candidate"], c["form"])
                if _key in _old_rows:
                    _row = dict(_old_rows[_key])
                    _row.update({"evidence": c["evidence"], "mechanical": c["gates"]["mechanical"]})
                    # awaiting/declined belong only on a current fleet-candidate.
                    if c.get("disposition") != "fleet-candidate":
                        if str(_row.get("disposition") or "") in ("declined", "awaiting-confirmation"):
                            _row.pop("disposition", None)
                            if not str(_row.get("name") or "").strip():
                                _row.pop("name", None)
                _merged.append(_row)
                _kept.add(_key)
            # Keep model-finalized rows that left this window. confirmed always
            # (an artifact exists). declined only if it was a fleet-candidate.
            for _key, _old in _old_rows.items():
                if _key in _kept:
                    continue
                _od = str(_old.get("disposition") or "")
                if _od == "confirmed" or (_od == "declined" and _is_fleet_proposal_row(_old)):
                    _merged.append(dict(_old))
            block["candidates"] = _merged
            block["decline_anchors"] = anchors
            block["n_candidates"] = len(candidates)
            block["n_fleet"] = len(_fleet_src)
            block["n_blocked"] = sum(1 for c in candidates if c.get("disposition") != "fleet-candidate")
            block["n_generic"] = sum(1 for c in candidates
                                     if c.get("disposition") == "blocked: generic-cli")
            block["n_day_spread"] = sum(1 for c in candidates
                                        if c.get("disposition") == "blocked: day-spread")
            seed["workflow_proposals"] = block
            _write_private(Path(into), _json.dumps(seed, indent=2) + "\n")
        except (OSError, _json.JSONDecodeError, UnicodeDecodeError, ValueError, TypeError, KeyError) as e:
            print(f"error: registrar --into could not read/write {into}: {e}", file=sys.stderr)
            return 2
    if as_json:
        print(_json.dumps(out, indent=2))
        return 0
    print("\n  ✦ REGISTRAR · Tier-2 mechanical gates (fleet-wide placement candidates)")
    print(f"    {out['nodes_reporting']}/{out['nodes']} nodes reporting · "
          f"{len(candidates)} candidate(s) · {sum(1 for c in candidates if c['disposition'] == 'fleet-candidate')} fleet-candidate(s)")
    _st = "; ".join(f"{s['node']}:{s['state']}" for s in out["node_states"])
    print(f"    node states — {_st}")
    for c in candidates:
        _mk = "✓" if c["disposition"] == "fleet-candidate" else "✗"
        print(f"    {_mk} [{c['form']}] {c['candidate'][:64]} · "
              f"nodes={len(c['evidence']['nodes'])} d={c['evidence']['d']} · {c['disposition']}")
    for a in anchors:
        print(f"    ⚓ declined@{a['node']}: {a['verdict'][:50]}")
    print(f"    model-judged legs (never engine-evaluated): {', '.join(model_legs)}\n")
    return 0


def workflows_report(project_dir: Path, as_json: bool) -> int:
    """Render fleet_workflows — evidence + lineage + inventory; judgment stays with the model."""
    import json as _json
    project_dir = project_dir.resolve()
    if not project_dir.is_dir():
        print(f"error: project dir {project_dir} does not exist — refusing (phantom-store guard)", file=sys.stderr)
        return 2
    w = fleet_workflows(project_dir)
    if as_json:
        print(_json.dumps(w, indent=2))
        return 0
    out: list = []
    title = "✦ FLEET WORKFLOWS · recurring templates across nodes"
    tag = f"{w['nodes_reporting']}/{w['nodes']} nodes reporting"
    gap = max(2, _ui.W - 2 - len(title) - len(tag))
    out.append(_ui.rule())
    out.append("  " + _ui.c("✦", "cyan") + title[1:] + " " * gap + _ui.c(tag, "bold"))
    out.append("  " + _ui.c("evidence rows accrue per dream since v0.1.82 — a low denominator is "
                            "missing instrumentation, never fleet absence · latest-record-per-node "
                            "(overlapping windows never summed)", "dim"))
    out.append(_ui.rule())
    out.append("")
    fleet_rows = [r for r in w["templates"] if r["fleet"]]
    out.append(_ui.kv("FLEET", f"{len(fleet_rows)} template(s) recurring in ≥2 nodes · "
               f"{len(w['templates'])} distinct across the fleet"))
    for r in w["templates"][:20]:
        mark = _ui.c("◆", "cyan") if r["fleet"] else _ui.c("·", "dim")
        out.append(f"    {mark} {_ui.lbl(r['template'][:44], 44)} "
                   + _ui.c(f"×{r['n']} · {r['d']}d · {len(r['nodes'])} node(s): {', '.join(r['nodes'])[:40]}", "dim"))
    if w["chains"]:
        out.append("")
        out.append(_ui.kv("CHAINS", _ui.c("adjacent-step bigrams — a fleet chain IS a candidate workflow", "dim")))
        for r in w["chains"][:10]:
            mark = _ui.c("◆", "cyan") if r["fleet"] else _ui.c("·", "dim")
            out.append(f"    {mark} {_ui.lbl(r['chain'][:60], 60)} "
                       + _ui.c(f"×{r['n']} · {len(r['nodes'])} node(s)", "dim"))
    if w["families"]:
        out.append("")
        out.append(_ui.kv("FAMILIES", _ui.c("head-signature near-join HINTS (same tool, drifting flags) — "
                                            "counts never merged", "dim")))
        for f in w["families"][:6]:
            out.append(f"    ~ {_ui.lbl(f['head'][:40], 40)} "
                       + _ui.c(f"{len(f['templates'])} variant(s) across {len(f['nodes'])} node(s)", "dim"))
    if w["used"]:
        out.append("")
        out.append(_ui.kv("ADOPTION", _ui.c("Skill invocations, latest window per node — the W-C quadrant's "
                                            "numerator (0 is absence of evidence, never disuse)", "dim")))
        for r in w["used"][:10]:
            out.append(f"    · {_ui.lbl(r['skill'][:40], 40)} "
                       + _ui.c(f"×{r['n']} across {len(r['nodes'])} node(s)", "dim"))
    if w["verdicts"]:
        out.append("")
        out.append(_ui.kv("LINEAGE", _ui.c("distill dispositions across ALL nodes — a decline in one node "
                                           "blocks a naive re-propose from another (materially-new-evidence "
                                           "rule, now fleet-checkable)", "dim")))
        for v in w["verdicts"][-8:]:
            out.append("    " + _ui.c(f"[{v['node'][:20]}] ", "dim") + v["verdict"][:96])
    out.append("")
    out.append(_ui.kv("INVENTORY", _ui.c(f"user-level artifacts: {len(w['inventory']['skills'])} skill(s) · "
               f"{len(w['inventory']['commands'])} command(s) — coverage judgment stays with the MODEL "
               "(a name match proves nothing)", "dim")))
    print(_ui.ascii_translate("\n".join(out)))
    return 0


# ── v0.1.80: fleet STALENESS — absorption lag, measured per node (beacon Stage A) ────────────────
def _all_stores() -> "list[Path]":
    """EVERY project store under ~/.claude/projects holding ≥1 *.md — deliberately wider than
    _network_nodes() (mirror-holders): a store with ZERO mirrors is exactly the most starved node
    the staleness sweep exists to surface."""
    out: list = []
    for store in iter_native_stores():
        try:
            if any(store.glob("*.md")):
                out.append(store)
        except OSError:
            continue
    return out


def _store_gaps(store: Path, stacks: "set | None", gfacts: list, body_hashes: dict,
                *, domain_id: "str | None" = None,
                migration_mode: str = "dual-read",
                memberships: "set | None" = None) -> "tuple[int, int]":
    """(missing, content_stale) for ONE store against the given relevance basis — the SINGLE gap
    predicate shared by fleet_staleness (per node) and the SessionStart beacon (its own store);
    v0.1.81, factored so the two can never diverge. `stacks=None` → user-global-only (the honest
    no-cache basis). Same review-hardened edges as the staleness sweep: a PRESENT-but-unreadable
    file is neither missing nor stale (under-report, the pinned bias).

    When `domain_id` is set, facts `--pull` would deny (`admit_cross_project`) do not
    count as missing/stale — the beacon must not nag for unreplicable facts.
    """
    from domain_policy import admit_cross_project
    from fact_schema import _parse_flow_list as _pfl_gap
    _gap_memberships = memberships if memberships is not None else set()
    missing = stale = 0
    for n, fm, _text in gfacts:
        _gk = _mirror_key(domain_id or "unknown", str(fm.get("domain") or ""), n)
        if not is_relevant(fm, stacks if stacks is not None else set()):
            continue
        if domain_id is not None:
            _adm = dict(fm)
            if (_global_is_fixture() or _hermetic_home()) and not _adm.get("domain") and domain_id not in ("", "unknown"):
                _adm["domain"] = domain_id
            if not admit_cross_project(domain_id, _adm, migration_mode=migration_mode,
                                       memberships=_gap_memberships,
                                       group_recips=set(_pfl_gap(
                                           str(_adm.get("recipients") or "")))):
                continue
        p = store / f"{_gk}.md"
        if not p.exists():
            missing += 1
            continue
        cur = _safe_read_text(p)
        if cur is None:
            continue
        if _is_mirror(cur) and _body_hash(cur) != body_hashes[n]:
            stale += 1
    return missing, stale


def fleet_staleness(project_dir: Path) -> dict:
    """READ-ONLY absorption-lag sweep (docs/fleet-staleness-report.spec.md — the observe-only
    Stage A that must prove/refute the SessionStart beacon's premise). Per node: last-dream
    marker age, mirror/fact counts, MISSING relevant globals (never absorbed), content-stale
    mirrors (body-lineage hash vs the canonical — v0.1.78; hook drift is --pull's job, stale
    KNOWLEDGE is what lag harms), own-log usage windows + harvest-ledger coverage. Scope basis
    is HONEST per node: full relevance (live detect_stacks) only for the TRIGGER — a slug is
    not invertible to a project path, so other nodes are assessed on user-global canonicals
    only, labeled, never guessed (Stage B's state-file stacks cache upgrades this)."""
    import json as _json
    from store_context import resolve_store as _rs_stale
    from control_plane import migration_mode_readonly as _mm_stale
    project_dir = project_dir.resolve()
    trig_ctx = _rs_stale(project_dir)
    gfacts = facts_for_context(trig_ctx)
    trig_store = project_store(project_dir)
    trig_stacks = detect_stacks(project_dir)
    mode = _mm_stale(trig_ctx)
    domain_by_store: dict = {}
    for _row in _registry_project_rows():
        nd = str(_row.get("native_memory_dir") or "")
        if nd:
            domain_by_store[_path_key(Path(nd))] = str(_row.get("domain_id") or "unknown")
    ledger_nodes = {str(r.get("node", "")) for r in _ledger_rows()}
    now_ep = datetime.now(timezone.utc).timestamp()
    body_hashes = {n: _body_hash(t) for n, _fm, t in gfacts if t}
    if any(not _t for _n, _fm, _t in gfacts):
        try:
            from facts_manifest import ensure as _fm_ens_s
            _man_rows_s, _ = _fm_ens_s(trig_ctx.canonical_domain_dir,
                                       trig_ctx.plugin_data_dir)
            for _n, _fm, _t in gfacts:
                if not _t and _man_rows_s and _n in _man_rows_s:
                    body_hashes[_n] = _man_rows_s[_n].get("body_hash") or ""
        except Exception:
            pass
    for _n, _fm, _t in gfacts:
        if not _t and _n not in body_hashes:
            body_hashes[_n] = ""
    if _global_is_fixture():
        stores = _all_stores()
    elif getattr(trig_ctx, "cross_project_allowed", False):
        stores = _same_domain_stores(trig_ctx)
    else:
        stores = []
    if trig_store.resolve() not in {s.resolve() for s in stores}:
        # PR-#93 review F1 (two reviewers, convergent): the TRIGGER appears UNCONDITIONALLY — an
        # absent/empty trigger store is the maximally-starved row (never dreamed, absorbed nothing),
        # not an omission. The same force-append harvest()/fleet_utility already use; every relevant
        # canonical then counts MISSING via the not-exists check below.
        stores.append(trig_store)
    nodes: list = []
    for store in stores:
        is_trig = store.resolve() == trig_store.resolve()
        marker = ""
        cached_stacks: "set | None" = None
        raw_state = _safe_read_text(store / ".consolidation-state.json")
        if raw_state:
            try:
                _st = _json.loads(raw_state)
                if isinstance(_st, dict):
                    marker = str(_st.get("timestamp", "") or "")
                    if isinstance(_st.get("stacks"), list):
                        # v0.1.81: the --pull-written stacks cache (script-truth, as of the node's
                        # last pull) upgrades this non-trigger row to full-scope relevance — still
                        # never guessed (absent cache stays user-global-only, labeled).
                        cached_stacks = {str(x) for x in _st["stacks"]}
            except (ValueError, TypeError):
                marker = ""
        mdt = _parse_ts(marker) if marker else None
        # review F4 + v0.1.81: ONE gap predicate (_store_gaps — shared with the session beacon so
        # they can never diverge). Trigger → live stacks; non-trigger → the --pull-written cache
        # when present, else None (user-global-only, labeled — never guessed).
        if is_trig:
            _dom = trig_ctx.domain_id
        else:
            _dom = domain_by_store.get(_path_key(store)) or ""
            if not _dom or _dom == "unknown":
                # Unregistered stores are measured against THIS domain's
                # canonicals (absorption lag), not as unknown/local-only —
                # that filter would under-report every gap (admit_cross_project
                # never admits unknown).
                _dom = trig_ctx.domain_id if getattr(
                    trig_ctx, "cross_project_allowed", False) else "unknown"
        missing, stale = _store_gaps(
            store, trig_stacks if is_trig else cached_stacks, gfacts, body_hashes,
            domain_id=_dom, migration_mode=mode)
        m = _node_tokens(store) if store.is_dir() else {"facts": 0, "shared": 0}
        hist = usage_history(store)
        nodes.append({"node": _sane(project_dir.name) if is_trig else _node_label(store),
                      "trigger": is_trig,
                      "last_dream": marker,
                      # review F5: a FUTURE marker (clock skew / hand-edit) clamps to 0.0 — never a
                      # negative "dreamed -26472d ago"; the raw marker stays in last_dream for audit.
                      "age_days": (max(0.0, round((now_ep - mdt.timestamp()) / 86400, 1)) if mdt else None),
                      "facts": m["facts"], "mirrors": m["shared"],
                      "missing_globals": missing, "stale_mirrors": stale,
                      "scope_basis": ("full (live stacks)" if is_trig
                                      else ("cached stacks (as of last pull)" if cached_stacks is not None
                                            else "user-global only (no stacks cache)")),
                      "usage_windows": hist["windows_full"],
                      "harvested": store.parent.name in ledger_nodes})
    nodes.sort(key=lambda d: (-d["missing_globals"], -(d["age_days"] if d["age_days"] is not None else 1e9)))
    return {"nodes": nodes,
            # review F6: content-stale mirrors ARE lag — a node with 0 missing but stale knowledge
            # counts as behind (the sweep's other half). review F3: never_dreamed keys on age_days —
            # the SAME predicate the render and the sort use, so a present-but-UNPARSEABLE marker
            # reads as never-dreamed everywhere consistently instead of contradicting the aggregate.
            "behind": sum(1 for d in nodes if d["missing_globals"] or d["stale_mirrors"]),
            "never_dreamed": sum(1 for d in nodes if d["age_days"] is None)}


def staleness_report(project_dir: Path, as_json: bool) -> int:
    """Render fleet_staleness — the per-node absorption-lag table. Advisory only: a node absorbs
    on ITS next dream (never auto-pulled from here — report-then-apply and the dream-governance
    model own writes). Maintainer/observability lens outside dream flow (like --network): uncued."""
    import json as _json
    project_dir = project_dir.resolve()
    if not project_dir.is_dir():
        print(f"error: project dir {project_dir} does not exist — refusing (phantom-store guard)", file=sys.stderr)
        return 2
    s = fleet_staleness(project_dir)
    if as_json:
        print(_json.dumps(s, indent=2))
        return 0
    out: list = []
    title = "✦ FLEET STALENESS · absorption lag per node"
    tag = f"{s['behind']}/{len(s['nodes'])} behind"
    gap = max(2, _ui.W - 2 - len(title) - len(tag))
    out.append(_ui.rule())
    out.append("  " + _ui.c("✦", "cyan") + title[1:] + " " * gap + _ui.c(tag, "bold" if s["behind"] else "dim"))
    out.append("  " + _ui.c("eventual consistency's honesty debt, measured — a node absorbs on ITS next "
                            "dream; nothing is auto-pulled from here", "dim"))
    out.append(_ui.rule())
    out.append("")
    for d in s["nodes"]:
        age = ("never dreamed" if d["age_days"] is None else f"dreamed {d['age_days']:g}d ago")
        gapscol = (_ui.c(f"↓{d['missing_globals']} missing", "yellow") if d["missing_globals"]
                   else _ui.c("· 0 missing", "dim"))
        stalecol = (_ui.c(f" · ⟳{d['stale_mirrors']} content-stale", "yellow") if d["stale_mirrors"] else "")
        cover = f"windows {d['usage_windows']}" + (" · harvested" if d["harvested"] else "")
        mark = "  " + _ui.c("◀ trigger", "cyan") if d["trigger"] else ""
        out.append(f"    {_ui.lbl(d['node'][:24], 24)} {age:<18} {gapscol}{stalecol}  "
                   + _ui.c(f"{d['mirrors']} mirror(s)/{d['facts']} fact(s) · {cover} · {d['scope_basis']}", "dim") + mark)
    out.append("")
    out.append(_ui.kv("RESULT", f"{s['behind']} node(s) behind · {s['never_dreamed']} never dreamed — "
               "the lag lever is a dream ON that node (its Phase 1 pulls + harvests); Stage B's "
               "session beacon will surface this at session start"))
    print(_ui.ascii_translate("\n".join(out)))
    return 0


# ── v0.1.79: fleet usage HARVEST — capture non-dreaming nodes' windows before transcripts rot ────
_LEDGER_TAIL_CAP = 2000   # ledger rows read from the tail (~1 row/node/harvest — years of headroom)


def _ledger_path() -> Path:
    """Fleet usage ledger lives in plugin data (ADR 006), not the canonical Markdown plane."""
    from retention import fleet_ledger_write_path
    return fleet_ledger_write_path()


def _ledger_rows() -> list:
    """Guarded tail read of the shared harvest ledger (docs/fleet-usage-harvest.spec.md) —
    malformed lines skipped, never fatal. Plugin-data only (leftover
    ~/.claude/memory/.fleet-usage.jsonl is migrate-inventory, not a standing dual-read)."""
    import json
    rows: list = []
    text = _safe_read_text(_ledger_path())
    if text is None:
        return rows
    for ln in text.splitlines()[-_LEDGER_TAIL_CAP:]:
        try:
            o = json.loads(ln)
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(o, dict):
            rows.append(o)
            if len(rows) >= _LEDGER_TAIL_CAP:
                return rows[-_LEDGER_TAIL_CAP:]
    return rows


def _append_ledger(row: dict) -> None:
    """One-line O_APPEND|O_CREAT 0o600 append to plugin-data only (never the Markdown plane)."""
    import json
    line = (json.dumps(row) + "\n").encode("utf-8")
    path = _ledger_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(path), os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
    try:
        os.write(fd, line)
    finally:
        os.close(fd)


def _harvest_node(store: Path, watermark: str, by: str) -> "dict | None":
    """Scan ONE node's transcript dir for organic fact reads since `watermark` → a usage-shaped
    ledger row, or None when no transcript is newer (idempotent re-runs). Reuses the EXACT
    --recalls machinery (extract_signals) — only Read file-paths and arc-marker presence leave
    the scan, never message content, so no new privacy surface. Reads-only: no miss/tier
    classification (that needs the node's own Phase-0 window-start snapshot — a dreaming-node
    signal; spec §v1 reach limits). The window START is the oldest scanned transcript's mtime —
    a transcript's mtime is its END, so the claimed span only UNDER-states coverage (the pinned
    bias); the END is now."""
    from extract_signals import _USAGE_FACT_CAP, _recall_items, _window_transcripts, split_dream_span
    proj_root = session_dir_for_store(store)
    store_prefix = str(store) + "/"
    archive_stems = frozenset(
        f.stem for f in store.glob("*.md")
        if f.name != "MEMORY.md" and (t := _safe_read_text(f)) is not None and _is_archive_index_text(t))
    transcripts = _window_transcripts(proj_root, watermark)
    if not transcripts:
        return None
    reads: dict = {}
    excluded = 0
    for tr in transcripts:
        organic, dn = split_dream_span(_recall_items(tr, store_prefix, watermark, archive_stems))
        excluded += dn
        for r in organic:
            rec = reads.setdefault(r["stem"], {"reads": 0, "last": ""})
            rec["reads"] += 1
            rec["last"] = max(rec["last"], r["ts"] or "")
    if watermark and not reads and not excluded:
        # a SUBSEQUENT harvest that found nothing new (e.g. a transcript touched in the same second
        # as the last watermark — the per-line `since` filter is the correctness backstop behind the
        # mtime prune). Emitting an empty row here would mint a fresh probative zero-read window on
        # EVERY invocation — evidence must accrue from TIME passing, never from re-running the tool.
        # (The FIRST harvest's zero-read row is meaningful: a full-history zero-read window.)
        return None
    now_ep = datetime.now(timezone.utc).timestamp()
    now = _ceil_iso(now_ep)   # ceiled like every stamp — and the same format as the window START,
    try:                      # so start ≤ end always holds (a fresh transcript's ceiled mtime could
        start = watermark or _ceil_iso(min(min(t.stat().st_mtime for t in transcripts), now_ep))
    except OSError:           # otherwise land one second PAST a truncated `now`, inverting the window)
        start = now   # a transcript vanished mid-scan: claim a zero-width span (undercount-safe)
    per_fact = [{"name": k, "reads": v["reads"], "last": v["last"]}
                for k, v in sorted(reads.items(), key=lambda kv: (-kv[1]["reads"], kv[0]))][:_USAGE_FACT_CAP]
    return {"node": proj_root.name, "window": f"{start}..{now}", "transcripts": len(transcripts),
            "dream_excluded": excluded, "reads": sum(v["reads"] for v in reads.values()),
            "facts_read": len(reads), "per_fact": per_fact, "harvested_at": now, "by": by}


def _stamp_harvest_identity(row: dict, domain_id: str) -> dict:
    """Add domain_id + fact_id to harvest per_fact rows (ADR 015; stem remains)."""
    if not isinstance(row, dict):
        return row
    from control_plane import stable_fact_id
    dom = str(domain_id or "")
    row["domain_id"] = dom
    stamped = []
    for item in list(row.get("per_fact") or []):
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "")
        item = dict(item)
        item["domain_id"] = dom
        if name and dom:
            item["fact_id"] = stable_fact_id(dom, name)
        stamped.append(item)
    row["per_fact"] = stamped
    return row


def harvest(project_dir: Path) -> int:
    """--harvest: for EVERY node (mirror-holding stores ∪ the trigger), capture organic fact-read
    windows from its transcripts into the shared ledger — closing the dream-gated capture hole
    (measured live: 1/3 nodes reporting; the others' evidence rotting unobserved, and a sandboxed
    red probe showed a real organic read invisible to fleet_utility). Watermarked per node,
    idempotent; every appended row is printed (legibility norm). docs/fleet-usage-harvest.spec.md."""
    project_dir = project_dir.resolve()
    if not project_dir.is_dir():
        print(f"error: project dir {project_dir} does not exist — refusing (phantom-store guard)", file=sys.stderr)
        return 2
    from store_context import resolve_store as _rs_h
    _hctx = _rs_h(project_dir)
    if not getattr(_hctx, "cross_project_allowed", False):
        print("harvest: local-only (unenrolled or unhealthy registry) — skipping",
              file=sys.stderr)
        return 0
    if _global_is_fixture():
        stores = _network_nodes()
    else:
        stores = _same_domain_stores(_hctx)
    trig = project_store(project_dir)
    if trig.is_dir() and trig.resolve() not in {s.resolve() for s in stores}:
        stores.append(trig)
    marks: dict = {}   # node slug -> (epoch, iso) of the max window END already harvested
    for r in _ledger_rows():
        node = str(r.get("node", ""))
        end = str(r.get("window", "")).split("..")[-1]
        dt = _parse_ts(end)
        if node and dt is not None and (node not in marks or dt.timestamp() > marks[node][0]):
            marks[node] = (dt.timestamp(), end)
    out: list = []
    title = "✦ FLEET HARVEST · usage windows from every node"
    tag = f"{len(stores)} node(s)"
    gap = max(2, _ui.W - 2 - len(title) - len(tag))
    out.append(_ui.rule())
    out.append("  " + _ui.c("✦", "cyan") + title[1:] + " " * gap + _ui.c(tag, "bold"))
    out.append("  " + _ui.c("reads-only capture via the --recalls machinery (dream-span excluded; no message "
                            "content leaves the scan)", "dim"))
    out.append(_ui.rule())
    out.append("")
    harvested = 0
    for store in stores:
        label = _node_label(store)
        row = _harvest_node(store, marks.get(session_dir_for_store(store).name, (0.0, ""))[1],
                            by=_sane(project_dir.name))
        if row is not None:
            row = _stamp_harvest_identity(row, _hctx.domain_id)
        if row is None:
            out.append("    " + _ui.c("·", "dim") + f" {label:<28} "
                       + _ui.c("up to date (no transcripts past the watermark)", "dim"))
            continue
        _append_ledger(row)
        harvested += 1
        out.append("    " + _ui.c("✓", "green") + f" {label:<28} "
                   + _ui.c(f"window {row['window']} · transcripts {row['transcripts']} · organic reads "
                           f"{row['reads']} on {row['facts_read']} fact(s) · dream-excluded {row['dream_excluded']}", "dim"))
    out.append("")
    out.append(_ui.kv("RESULT", f"harvested {harvested} node window(s) → {_ledger_path().name} "
               "(append-only, 0o600) · --utility surfaces them for nodes with no own-log usage"))
    print(_ui.ascii_translate("\n".join(out)))
    return 0


# ── v0.1.67 (Phase C): fleet utility — the gc lever's missing evidence ───────────────────────────
def fleet_utility(project_dir: Path) -> dict:
    """READ-ONLY: per-canonical usage evidence aggregated across every node's cycle log (usage_history —
    the same reader the demotion rank uses), joined with a MIRROR CHECK before attribution: a node's
    reads for stem X count toward canonical X only if the node's `X.md` is a managed mirror — a
    same-stem, never-pulled LOCAL fact (the `present(local)` shadow case run() already recognizes) is
    tallied as `shadow_reads`, never attributed (a spec-gate finding: stem equality alone lies).
    Per-canonical `windows` counts only the probative windows each holding MIRROR's content-lineage
    existed through (window start ≥ the mirror's `global_ref_since` stamp — v0.1.78, surviving
    refreshes; st_mtime fallback on unstamped mirrors — the demotion rank's fact-age rule, applied
    fleet-side; an inline adversarial review found the unconditional windows_full credit overstated
    zero-read evidence on freshly-pulled mirrors, and the 2026-07-10 audit found the mtime clock
    starved it the other way: any description tweak wiped the fleet's accrued windows). `fleet_tax = pointer_tok × len(holders)` — ZERO for an unheld canonical (nobody pays it; its
    would-be per-node cost is listed separately), on the stated provenance UPPER-BOUND basis. This is
    EVIDENCE for the model's gc/demote judgment (Phase-5 step 2, Phase-4 governance) — never an auto-gc
    input: scope/keep decisions stay CONTENT-gated (holders/adoption ≠ fit). JSON-safe (lists, never
    sets). docs/index-usage-and-budget-ladder.spec.md §Phase C4."""
    project_dir = project_dir.resolve()
    from store_context import resolve_store as _rs_util
    _ctx_util = _rs_util(project_dir)
    canon = {n: fm for n, fm, _ in facts_for_context(_ctx_util)}
    if _global_is_fixture():
        stores = _network_nodes()
    elif getattr(_ctx_util, "cross_project_allowed", False):
        stores = _same_domain_stores(_ctx_util)
    else:
        stores = []
    trig = project_store(project_dir)
    if trig.is_dir() and trig.resolve() not in {s.resolve() for s in stores}:
        if getattr(_ctx_util, "cross_project_allowed", False) or _global_is_fixture():
            stores.append(trig)
    nodes_reporting = nodes_harvested = 0
    ledger_by_node: dict = {}
    for _lr in _ledger_rows():
        if isinstance(_lr.get("per_fact"), list):
            ledger_by_node.setdefault(str(_lr.get("node", "")), []).append(_lr)
    per: dict = {n: {"reads": 0, "windows": 0, "last": "", "_ep": None, "shadow": 0, "fallback": 0,
                     "h_reads": 0, "h_windows": 0, "mentions": 0} for n in canon}
    for store in stores:
        hist = usage_history(store)
        if hist["windows_full"] >= 1:
            nodes_reporting += 1
        _mset = set(hist.get("mention_stems") or [])   # v0.1.85 (P3): stems named in this node's windows
        # v0.1.79 (docs/fleet-usage-harvest.spec.md, the v1 rule): harvested ledger rows contribute
        # ONLY for a node with NO own-log usage at all — own-log strictly primary, no interval-overlap
        # math, no double-count risk (mixed-node merging is the consumption release's refinement).
        hrows: list = []
        if hist["windows_full"] == 0 and not hist["per_fact"]:
            hrows = ledger_by_node.get(store.parent.name, [])
            # 2026-09-03 audit: concurrent harvests can append duplicate rows for the
            # same (node, window) — dedup by window-start before aggregation so the
            # probative evidence never double-counts
            _seen_win: set = set()
            _hrows_dedup = []
            for _hr in hrows:
                _wkey = str(_hr.get("window", "")).split("..")[0]
                if _wkey in _seen_win:
                    continue
                _seen_win.add(_wkey)
                _hrows_dedup.append(_hr)
            hrows = _hrows_dedup
        if hrows:
            nodes_harvested += 1
        for stem in canon:
            row = hist["per_fact"].get(stem)
            reads = row.get("reads", 0) if isinstance(row, dict) else 0
            reads = reads if isinstance(reads, int) and not isinstance(reads, bool) and reads > 0 else 0
            h_reads = 0
            h_last = ""
            for hr in hrows:
                for pf in hr.get("per_fact", []):
                    if not isinstance(pf, dict):
                        continue
                    _fid_want = ""
                    try:
                        from control_plane import stable_fact_id as _sf_ut
                        _fid_want = _sf_ut(_ctx_util.domain_id, stem)
                    except Exception:
                        _fid_want = ""
                    same = bool(_fid_want) and str(pf.get("fact_id") or "") == _fid_want
                    same = same or (
                        str(pf.get("domain_id") or "") == str(_ctx_util.domain_id or "")
                        and pf.get("name") == stem)
                    if not same:
                        continue
                    _hr = pf.get("reads", 0)
                    if isinstance(_hr, int) and not isinstance(_hr, bool) and _hr > 0:
                        h_reads += _hr
                        h_last = max(h_last, str(pf.get("last", "") or ""))
            p = store / f"{stem}.md"
            if not p.exists():
                continue
            try:
                text = p.read_text(encoding="utf-8", errors="replace")
                mt = p.stat().st_mtime
            except OSError:
                continue
            if not _is_mirror(text):
                if reads or h_reads:
                    per[stem]["shadow"] += reads + h_reads   # same-stem local — reported, never attributed
                continue
            if stem in _mset:   # v0.1.85 (P3): mention attributed only through a MIRROR, like reads —
                per[stem]["mentions"] += 1   # a node's hook fired for this canonical (display-only, +1/node)
            # Count only the probative windows the MIRROR's content-lineage existed through — the fact-age
            # rule (2026-07-05 review: crediting whole window history to a fresh mirror overstates
            # zero-read evidence). v0.1.78 (docs/evidence-clock-stamps.spec.md): the clock is the mirror's
            # `global_ref_since` stamp when present+parseable — it SURVIVES refreshes, so a description
            # tweak no longer wipes the fleet's accrued windows (the audit's F9 starvation: mtime-gated
            # windows measured 1→0 on a description-only edit; at real cadence the demotion evidence gate
            # could never converge for an occasionally-edited canonical). st_mtime is the legacy fallback
            # (unstamped mirror → pre-upgrade behavior; a garbled stamp fails toward less evidence).
            _since = str(_frontmatter(text).get("global_ref_since", "") or "")
            _sdt = _parse_ts(_since) if _since else None
            if _sdt is not None:
                clock = _sdt.timestamp()
            else:
                clock = mt
                per[stem]["fallback"] += 1
            per[stem]["windows"] += sum(1 for s in hist["window_starts"]
                                        if isinstance(s, (int, float)) and s >= clock)
            per[stem]["reads"] += reads
            ts = str((row or {}).get("last", "") or "") if isinstance(row, dict) else ""
            dt = _parse_ts(ts)
            if dt is not None and (per[stem]["_ep"] is None or dt.timestamp() > per[stem]["_ep"]):
                per[stem]["_ep"], per[stem]["last"] = dt.timestamp(), ts
            # v0.1.79: harvested evidence for this (no-own-usage) node — source-labeled, same
            # mirror-gated attribution; window credit still gates on the mirror's evidence clock,
            # and a cap-truncated row (facts_read != len(per_fact)) is non-probative, same as own-log.
            if h_reads:
                per[stem]["h_reads"] += h_reads
                _hdt = _parse_ts(h_last)
                if _hdt is not None and (per[stem]["_ep"] is None or _hdt.timestamp() > per[stem]["_ep"]):
                    per[stem]["_ep"], per[stem]["last"] = _hdt.timestamp(), h_last
            for hr in hrows:
                _ws = _parse_ts(str(hr.get("window", "")).split("..")[0])
                _tx = hr.get("transcripts", 0)
                if (_ws is not None and isinstance(_tx, int) and not isinstance(_tx, bool) and _tx >= 1
                        and hr.get("facts_read", -1) == len(hr.get("per_fact", []))
                        and _ws.timestamp() >= clock):
                    per[stem]["h_windows"] += 1
    entries: list = []
    total_tax = total_tax_live = 0
    unheld: list = []
    for stem, fm in canon.items():
        pt = est_tokens(_pointer_line(stem, fm))
        holders = _holder_labels(fm, stem=stem, ctx=_ctx_util)
        tax = pt * len(holders)
        total_tax += tax
        # v0.1.84 (P4): classify every edge — the provenance UPPER BOUND stays the advisory's
        # denominator (documented derivation, unchanged); fleet_tax_live (pointer × LIVE holders —
        # the stores actually paying the pointer) prints BESIDE it, never replacing it. Measured
        # at ship time: 20% of the provenance-basis tax was ghost-attributed.
        cls = {"live": 0, "stale": 0, "unresolved": 0, "ambiguous": 0}
        for h in holders:
            cls[_classify_edge(h, stem)] += 1
        tax_live = pt * cls["live"]
        total_tax_live += tax_live
        e = {"name": stem, "scope": fm.get("scope", ""), "reads": per[stem]["reads"],
             "windows": per[stem]["windows"], "last": per[stem]["last"],
             "holders": len(holders), "pointer_tok": pt, "fleet_tax": tax,
             "fleet_tax_live": tax_live}
        for _ck in ("live", "stale", "unresolved", "ambiguous"):
            if cls[_ck]:
                e[f"holders_{_ck}"] = cls[_ck]
        if per[stem]["shadow"]:
            e["shadow_reads"] = per[stem]["shadow"]
        if per[stem]["fallback"]:   # v0.1.78: evidence-provenance — holders still on the mtime clock
            e["fallback_nodes"] = per[stem]["fallback"]
        if per[stem]["h_reads"] or per[stem]["h_windows"]:   # v0.1.79: harvested, source-labeled
            e["harvested_reads"] = per[stem]["h_reads"]
            e["windows_harvested"] = per[stem]["h_windows"]
        if per[stem]["mentions"]:   # v0.1.85 (P3): hook-channel evidence, mirror-attributed nodes
            e["mentions"] = per[stem]["mentions"]
        if not holders:
            unheld.append(stem)
        entries.append(e)
    entries.sort(key=lambda e: (-e["fleet_tax"], e["name"]))
    return {"nodes": len(stores), "nodes_reporting": nodes_reporting, "nodes_harvested": nodes_harvested,
            "canonicals": entries,
            "total_fleet_tax": total_tax, "total_fleet_tax_live": total_tax_live,
            "advisory": GLOBAL_FLEET_TAX_ADVISORY, "unheld": unheld}


def utility_report(project_dir: Path, as_json: bool) -> int:
    """Render fleet_utility — the per-canonical evidence table + the fleet-tax gauge (warn-only)."""
    import json as _json
    u = fleet_utility(project_dir)
    if as_json:
        print(_json.dumps(u, indent=2))
        return 0
    out: list = []
    title = "✦ FLEET UTILITY · per-canonical usage evidence"
    tag = f"{u['nodes_reporting']}/{u['nodes']} nodes reporting"
    gap = max(2, _ui.W - 2 - len(title) - len(tag))
    out.append(_ui.rule())
    out.append("  " + _ui.c("✦", "cyan") + title[1:] + " " * gap + _ui.c(tag, "bold"))
    out.append("  " + _ui.c("usage exists only where post-v0.1.63 dreams ran --recalls; holders = "
                            "provenance UPPER bound (dead edges reported by --gc; --edges --apply prunes "
                            "only the provable ghosts)"
                            + (f" · harvested ledger covers {u['nodes_harvested']} no-own-usage node(s)"
                               if u.get("nodes_harvested") else ""), "dim"))
    out.append(_ui.rule())
    out.append("")
    over = _ui.c("  ⚠ over advisory (warn-only — evidence for gc/demote judgment, never a gate)", "red") \
        if u["total_fleet_tax"] > u["advisory"] else ""
    out.append(_ui.kv("FLEET TAX", f"{_ui.bar(u['total_fleet_tax'], u['advisory'])} "
               + _ui.c(f"≈{u['total_fleet_tax']}/{u['advisory']} est tok · Σ pointer × holders over "
                       f"{len(u['canonicals'])} canonical(s)", "dim") + over))
    if u.get("total_fleet_tax_live", u["total_fleet_tax"]) != u["total_fleet_tax"]:
        _ghost_tax = u["total_fleet_tax"] - u["total_fleet_tax_live"]
        out.append("    " + _ui.c(f"live-basis ≈{u['total_fleet_tax_live']} (≈{_ghost_tax} rides non-LIVE "
                                  "edges — ghosts/stale/ambiguous; `--gc . --edges` enumerates the ghosts, "
                                  "--apply prunes ONLY those)", "yellow"))
    out.append("")
    out.append(_ui.kv("CANON", _ui.c("fleet_tax desc · reads are MIRROR-attributed organic recalls "
                                     "across reporting nodes · windows = Σ probative windows each holding "
                                     "MIRROR's content-lineage existed through (global_ref_since-gated — "
                                     "survives refreshes; mtime fallback on unstamped mirrors)", "dim")))
    for e in u["canonicals"]:
        if e["windows"] and not e["reads"]:
            ev = _ui.c(f"0 reads/{e['windows']}w — unread where instrumented", "yellow")
        elif e["reads"]:
            ev = _ui.c(f"{e['reads']} read(s)/{e['windows']}w · last {str(e['last'])[:16]}", "green")
        else:
            ev = _ui.c("uninstrumented (0 probative windows on holders)", "dim")
        shadow = _ui.c(f" · shadow {e['shadow_reads']}", "yellow") if e.get("shadow_reads") else ""
        harv = (_ui.c(f" · +{e.get('harvested_reads', 0)}r/{e.get('windows_harvested', 0)}w harvested", "cyan")
                if (e.get("harvested_reads") or e.get("windows_harvested")) else "")
        # v0.1.85 (P3): the HOOK channel — named-without-a-read on N node(s). A canonical unread yet
        # MENTIONED is used via its always-loaded index hook (the layer's product) — display-only
        # corroboration; makes a 0-reads row read as "instrumented but hook-active", not dormant.
        ment = _ui.c(f" · hook×{e['mentions']}", "green") if e.get("mentions") else ""
        out.append(f"    {_ui.lbl(e['name'][:40], 40)} {e['fleet_tax']:>5}t "
                   + _ui.c(f"({e['pointer_tok']}t × {e['holders']})", "dim") + f"  {ev}{shadow}{harv}{ment}")
    if u["unheld"]:
        out.append("    " + _ui.c(f"unheld (0 fleet tax — nobody pays them yet): {', '.join(u['unheld'])}", "dim"))
    out.append("")
    out.append(_ui.kv("NEXT", _ui.c("a 0-reads/instrumented canonical is gc-lever EVIDENCE — judge its "
                                    "CONTENT before any demote (holders/adoption ≠ fit); never auto-gc", "dim")))
    print(_ui.ascii_translate("\n".join(out)))
    return 0


# The dream-flow modes that carry a cross-project BEAT: --list/--pull/--harvest (Phase 1) and --gc/
# --tokens/--utility (Phase 5; --utility is the gc lever's evidence view, v0.1.67). --promote runs in
# Phase 4's APPLY — the one phase whose contract deliberately excludes dream beats (only the plain
# proposal + the single SURFACING line) — and --network/--staleness are maintainer/observability
# utilities outside dream flow, so none of those cue.
_CUED_MODES = ("--list", "--pull", "--gc", "--tokens", "--utility", "--harvest", "--workflows")


def main() -> int:
    rc = _dispatch()
    if rc == 0 and sys.argv[1:2] and sys.argv[1] in _CUED_MODES:
        # v0.1.54: ONE dream-arc cue per run (stderr, CM_DREAM_ARC-gated); a usage/error exit
        # doesn't cue — nothing ran that deserves a beat. See _ui.dream_cue.
        _ui.dream_cue("cross-project beat due — the other projects drifting through (plain italics, "
                      "no emoji) above the plain report")
    return rc


def _dispatch() -> int:
    args = sys.argv[1:]
    _ui.set_modes(color=_ui.color_enabled(args, sys.stdout), ascii="--ascii" in args, width=_ui.resolve_width(args, sys.stdout))
    # positional PROJECT_DIR — flags (--json/--apply/--color/--ascii/--no-color) excluded so a
    # bare visual flag is NEVER mis-read as the project dir (which --pull would replicate INTO).
    # Value-taking flags (--into SEED) must skip THEIR argument too — otherwise
    # `--workflows --registrar --into /tmp/seed.json` treats the seed path as PROJECT_DIR.
    _VALUE_FLAGS = {"--into"}
    pos = []
    _skip_val = False
    for a in args[1:]:
        if _skip_val:
            _skip_val = False
            continue
        if a in _VALUE_FLAGS:
            _skip_val = True
            continue
        if not a.startswith("-"):
            pos.append(a)
    project_dir = Path(pos[0]) if pos else Path.cwd()
    if ("--fleet" in args or "--fleet=full" in args) and args and args[0] != "--tokens":
        print("usage: --fleet/--fleet=full are --tokens-only flags — refusing "
              "(a flag must never silently no-op on another mode)", file=sys.stderr)
        return 2
    if args and args[0] == "--network":
        if "--all-domains" in args:
            return network(all_domains=True)
        if not project_dir.is_dir():
            print(f"error: PROJECT_DIR {project_dir} does not exist / is not a directory — refusing",
                  file=sys.stderr)
            return 2
        return network(project_dir)
    # v0.1.75 (audit F5): a TYPO'D PROJECT_DIR must never mint a phantom store. resolve() is non-strict,
    # os.walk on a missing dir is silently empty, and --pull's store.mkdir would then create a store under
    # the bogus slug AND write the bogus basename into every shared canonical's `projects:` provenance —
    # pollution --gc can never reclaim (the phantom's mirrors "exist", so its edges are never dead).
    # Refuse EVERY project-dir mode up front (--network above takes none).
    if not project_dir.is_dir():
        print(f"error: PROJECT_DIR {project_dir} does not exist / is not a directory — refusing "
              "(a typo'd path would mint a phantom store under its slug and write bogus provenance "
              "into every shared canonical)", file=sys.stderr)
        return 2
    if args and args[0] == "--tokens":
        _fleet_on = "--fleet" in args or "--fleet=full" in args
        return token_report(project_dir, "--json" in args, fleet=_fleet_on,
                            fleet_full="--fleet=full" in args)
    if args and args[0] == "--utility":   # v0.1.67 (Phase C): fleet usage evidence (READ-ONLY, like --list)
        return utility_report(project_dir, "--json" in args)
    if args and args[0] == "--harvest":   # v0.1.79: capture every node's usage windows into the shared ledger
        return harvest(project_dir)
    if args and args[0] == "--staleness":   # v0.1.80: READ-ONLY absorption-lag sweep (beacon Stage A)
        return staleness_report(project_dir, "--json" in args)
    if args and args[0] == "--workflows":   # v0.1.83 (W-B): READ-ONLY fleet workflow evidence lens
        # v0.1.87/W-C1: --registrar rides the SAME argv[1] cue (a conscious choice — the
        # cross-project beat fires on the consult too, exactly as for the bare lens)
        if "--registrar" in args:
            _into = None
            for _i2, _a in enumerate(args):
                if _a == "--into":
                    if _i2 + 1 >= len(args):
                        print("error: --into needs a SEED path (usage: --workflows --registrar --into <seed>)",
                              file=sys.stderr)
                        return 2
                    _into = args[_i2 + 1]
                    break
                if _a.startswith("--into="):   # review fix: the equals form was silently ignored
                    _into = _a.split("=", 1)[1]
                    break
            return registrar_report(project_dir, "--json" in args, into=_into)
        if "--into" in args:
            print("warning: --into without --registrar is ignored (the injection rides the registrar consult)",
                  file=sys.stderr)
        return workflows_report(project_dir, "--json" in args)
    if args and args[0] == "--gc":
        return gc(project_dir, "--apply" in args, edges="--edges" in args)
    if args and args[0] == "--promote":
        # --promote PROJECT_DIR LOCAL_FACT [CANON_NAME]  (CANON_NAME defaults to LOCAL_FACT)
        if len(pos) < 2:
            print("usage: sync_global.py --promote PROJECT_DIR LOCAL_FACT [CANON_NAME] [--prefer-canonical] [--repoint]", file=sys.stderr)
            return 2
        return promote(Path(pos[0]), pos[1], pos[2] if len(pos) >= 3 else pos[1],
                       prefer_canonical="--prefer-canonical" in args,
                       allow_repoint="--repoint" in args)
    if not args or args[0] not in ("--list", "--pull"):
        print("usage: sync_global.py --list|--pull [--allow-net-grow] [--evict=FACT] PROJECT_DIR | --gc [--edges] [--apply] PROJECT_DIR "
              "| --promote PROJECT_DIR LOCAL_FACT [CANON_NAME] [--prefer-canonical] | --tokens [--json] [--fleet|--fleet=full] PROJECT_DIR "
              "| --utility [--json] PROJECT_DIR | --harvest PROJECT_DIR | --staleness [--json] PROJECT_DIR "
              "| --workflows [--json] [--registrar] [--into SEED] PROJECT_DIR "
              "| --network", file=sys.stderr)
        return 2
    evict = next((a.split("=", 1)[1] for a in args if a.startswith("--evict=")), None)
    if evict is not None:                          # Gate-2: a destructive flag must not silently no-op
        if evict == "":
            print("evict: --evict= requires a fact name (e.g. --evict=stale-fact)", file=sys.stderr); return 2
        if args[0] != "--pull":
            print("evict: --evict requires --pull (it's a destructive swap, not a read-only --list)", file=sys.stderr); return 2
    return run(project_dir, args[0] == "--pull", allow_net_grow="--allow-net-grow" in args, evict=evict)


if __name__ == "__main__":
    raise SystemExit(main())
