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
  --promote PROJECT_DIR LOCAL_FACT [CANON_NAME] [--prefer-canonical]
                       hand a project-authored local fact UP to the canonical global store and
                       convert the origin's copy into a managed mirror (the local→canonical
                       promotion hand-off; never leaves a dup/orphan — see promote()). A RECONCILE
                       onto an existing canonical REFUSES if the local's body differs (M2 — would
                       silently discard it); --prefer-canonical keeps the canonical, drops the local
                       body (the dedup intent). stack-general stacks: must be DETECTABLE (M4).
  --harvest PROJECT_DIR  (v0.1.79) capture EVERY node's organic fact-read windows from its transcripts into
                       the shared append-only ledger (~/.claude/memory/.fleet-usage.jsonl, 0o600) BEFORE
                       rotation destroys them — usage capture was dream-gated per node (measured: 1/3 nodes
                       reporting). Watermarked + idempotent; reads-only (no miss classification); --utility
                       surfaces the harvested evidence, source-labeled, for nodes with no own-log usage.
  --staleness PROJECT_DIR  (v0.1.80) READ-ONLY absorption-lag sweep over ALL project stores (beacon
                       Stage A): per node — last-dream marker age, MISSING relevant globals (never
                       absorbed), content-stale mirrors, usage/harvest coverage. Scope basis honest per
                       node (full relevance only for the trigger; others user-global-only, labeled).
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
                           extract_wikilinks, resolve_wikilink, usage_history)

GLOBAL = Path.home() / ".claude" / "memory"

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
    return bool(re.fullmatch(_SAFE_NAME, stem or ""))


def _sanitize_token(s: str) -> str:
    """Collapse anything outside the safe charset to '-'. For values written into the
    SHARED global store (e.g. a project basename in `projects:`); also neutralizes any
    regex backreference (`\\1`) before such a value reaches an re.sub replacement."""
    return re.sub(r"[^A-Za-z0-9._-]", "-", s or "")


def project_store(project_dir: Path) -> Path:
    return Path.home() / ".claude" / "projects" / slug_for(project_dir) / "memory"


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
    tmp = path.with_suffix(path.suffix + f".tmp{os.getpid()}")
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
    tmp = path.with_suffix(path.suffix + f".tmp{os.getpid()}")
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


def global_facts() -> list[tuple[str, dict, str]]:
    facts: list[tuple[str, dict, str]] = []
    if not GLOBAL.exists():
        return facts
    for f in sorted(GLOBAL.glob("*.md")):
        if f.name == "MEMORY.md" or _is_reserved_stem(f.stem):
            # v0.1.70 Gate-2a (3rd pass): the exact-case check alone missed a global fact literally
            # named memory.md/Memory.md/etc — _safe_stem(f.stem) below happily accepts "memory" as a
            # valid kebab stem, so such a fact would be treated as an ordinary ingestible global and
            # later pulled/written to a project's store / "memory.md", colliding with the project's
            # own MEMORY.md on a case-insensitive filesystem (macOS). Reachable from data written by
            # promote() before ITS OWN case-insensitive guard existed (this same PR's earlier fix).
            continue
        # The stem becomes a filename AND is interpolated into each pulling project's
        # always-loaded index (`- [name](name.md) — …`). Reject any stem outside the
        # documented kebab-case charset so a crafted name can't inject markdown/links
        # into the tier-1 context of every project that pulls it.
        if not _safe_stem(f.stem):
            continue
        text = _safe_read_text(f)   # v0.1.69 Gate-2b follow-up: store-scan convention — a
        if text is None:            # concurrent gc/chmod on the GLOBAL store must not abort the scan
            continue
        facts.append((f.stem, _frontmatter(text), text))
    return facts


def _fact_stacks(fm: dict) -> set[str]:
    """A fact's declared `stacks:` tags as a lowercased-token set. Shared by relevance matching
    AND the promotion stacks-guard so the two parse `stacks:` identically (a stack-general fact is
    relevant — and promotable — iff this set is non-empty and intersects the project's stacks)."""
    return set(re.findall(r"[a-z0-9-]+", fm.get("stacks", "").lower()))


def is_relevant(fm: dict, stacks: set[str]) -> bool:
    scope = fm.get("scope", "")
    if scope == "user-global":
        return True
    if scope == "stack-general":
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


def _as_mirror(text: str, name: str, since: str = "", body_hash: str = "") -> str:
    """Return the global fact stamped as a managed mirror (`global_ref: <name>`),
    robustly — drop any existing global_ref, then insert one after `metadata:`.

    v0.1.78 (evidence-clock stamps): when `since`/`body_hash` are supplied, two sibling stamps
    ride the same metadata anchor — `global_ref_since:` (when this mirror's content-lineage
    began) and `global_ref_body:` (the sha1-12 lineage key). run()/promote() compute the carry;
    bare calls (tests, legacy paths) emit no stamps. The frontmatter-scoped strip covers the
    whole `global_ref` prefix so re-stamping stays idempotent; `_is_mirror` keys on
    `global_ref:` only, so the smoke-pinned round-trip is untouched. REACH LIMIT: the
    no-metadata-block fallback form (`# global_ref:` comment) carries no stamps — such a
    mirror stays on the consumer's mtime fallback clock.

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
        if dashes == 1 and s.startswith(("global_ref:", "global_ref_since:", "global_ref_body:")):
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
            if since:   # v0.1.78: the content-lineage clock (see docstring; caller computes the carry)
                out.append(f"  global_ref_since: {since}")
                out.append(f"  global_ref_body: {body_hash}")
            injected = True
    if not injected:  # no metadata block — stamp just inside the frontmatter
        for i, ln in enumerate(out):
            if ln.strip() == "---":
                out.insert(i + 1, f"# global_ref: {name}")
                break
    return "\n".join(out) + "\n"


def _pointer_line(name: str, fm: dict) -> str:
    """The canonical index pointer line for a fact (pure — testable). The `description`
    is the recall hook; it comes from a global fact (possibly crafted) and is written
    into the always-loaded index, so sanitize it: collapse control bytes/newlines to a
    space (a stray newline/ESC would break or inject into the index line), then truncate."""
    desc = fm.get("description", "").strip().strip('"')
    # Strip control bytes (line-break/ESC injection) AND markdown link/bracket chars so a
    # crafted description can't inject a link or a spoofed `](name.md)` target into the
    # always-loaded index line.
    desc = " ".join(re.sub(r"[\x00-\x1f\x7f-\x9f\[\]()]", " ", desc).split())
    hook = (desc[:88] + "…") if len(desc) > 88 else desc
    scope = fm.get("scope", "")
    return f"- [{name}]({name}.md) — {hook}" + (f" [{scope}]" if scope else "")


def _fat_hook_warning(pointer_line: str, name: str) -> str | None:
    """v0.1.66 (Phase B): the write-time fat-hook LINT — a warning string when a pointer line exceeds
    HOOK_TOKEN_WARN est tok, else None. PURE (smoke-pinned). Detection names the CANONICAL's description
    as the fix site (the pointer is derived from it, so a fat mirror hook taxes every node on every
    session); the line is NEVER truncated — a recall cue silently shortened is a recall cue silently
    broken (report-then-apply: the human tightens the canonical).

    HONEST REACH LIMIT: `_pointer_line`'s own 88-char description truncation caps its output well under
    HOOK_TOKEN_WARN for any realistic fact name (measured: a name needs to run ~65+ chars before the line
    crosses 60 est tok) — this lint mostly guards an extreme-name edge case for GLOBAL/mirror pointers.
    The fat hooks actually measured this session (116/141 tok) were project-authored LOCAL pointers the
    model hand-writes in Phase 4, a path this script never touches — SKILL.md's Phase-4 prose is the
    only guard there (the "≤ ~60 est tok" rule), not this function."""
    t = est_tokens(pointer_line)
    if t > HOOK_TOKEN_WARN:
        return (f"⚠ fat hook: '{name}' pointer ≈{t} tok > {HOOK_TOKEN_WARN} — tighten the CANONICAL's "
                f"description (~/.claude/memory/{name}.md); this line taxes every session on every node")
    return None


def _ensure_index_pointer(store: Path, name: str, fm: dict) -> tuple[bool, bool]:
    """UPSERT the pointer line in the project's MEMORY.md index (Fix C).

    The script owns this so a replicated fact is never left half-installed (file but no
    pointer) — AND so the ALWAYS-LOADED index hook never drifts from the canonical. The
    old version early-returned when any line for `name` existed, so a STALE refresh that
    changed the fact's `description` updated the body but left the index hook stale. Now:
    insert if absent, REWRITE if present-but-different, no-op if already correct.
    v0.1.66: every WRITE (insert or rewrite — the single choke point for --pull, refresh,
    AND --promote pointers) is fat-hook-linted to stderr; a no-op is not (nothing written).

    Returns `(wrote, is_fat)` — a CALLER that counts/reports fat hooks (e.g. run()'s RESULT
    line) MUST use `is_fat`, never re-derive it via a second `_pointer_line`/`_fat_hook_warning`
    call: this function already computes both internally to decide the stderr print, and a
    max-effort code-review workflow (2026-07-04) found the original discard-then-recompute
    shape at the ONE caller that needed it is exactly how a real accounting bug (a no-op
    refresh double-counted as a fresh "written" fat hook) got in — a second, independent
    computation of the same fact is a single-source-of-truth violation waiting to drift, not
    just here but at the NEXT caller that copies the old pattern instead of using this return."""
    idx = store / "MEMORY.md"
    content = _safe_read_text(idx) or "# Memory Index\n\n"   # store-scan convention (v0.1.69 Gate-2b)
    want = _pointer_line(name, fm)
    lint = _fat_hook_warning(want, name)
    lines = content.splitlines()
    anchor = f"]({name}.md)"  # the LINK TARGET, not a bare substring a description could spoof
    for i, ln in enumerate(lines):
        if anchor in ln:
            if ln.strip() == want.strip():
                return False, False  # already correct — no-op
            lines[i] = want  # refresh a drifted hook
            if lint:
                print(f"  {lint}", file=sys.stderr)
            idx.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
            return True, bool(lint)
    if lint:
        print(f"  {lint}", file=sys.stderr)
    idx.write_text(content.rstrip() + "\n" + want + "\n", encoding="utf-8")  # absent — append
    return True, bool(lint)


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
    (the same spoof-resistant rule _ensure_index_pointer/_remove_index_pointer use) — 0 when absent.
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
    --staleness to user-global-only (labeled), never fails the pull."""
    import json
    sp = store / ".consolidation-state.json"
    try:
        st: dict = {}
        raw = _safe_read_text(sp)
        if raw:
            try:
                _parsed = json.loads(raw)
                if isinstance(_parsed, dict):
                    st = _parsed
            except (ValueError, TypeError):
                st = {}   # unreadable state: still cache (readers tolerate the extra keys)
        st["stacks"] = sorted(stacks)
        st["project_path"] = str(project_dir)
        store.mkdir(parents=True, exist_ok=True)
        # PR-#94 review F3: atomic per the Track-D convention — a concurrently-starting session's
        # beacon must never read a torn state file (it would degrade the basis needlessly).
        _atomic_write_text(sp, json.dumps(st, indent=2) + "\n")
    except OSError as e:
        print(f"  ⚠ stacks-cache write skipped ({e.__class__.__name__}) — the session beacon "
              "degrades to user-global-only until the next pull", file=sys.stderr)


def run(project_dir: Path, pull: bool, allow_net_grow: bool = False, evict: str | None = None) -> int:
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
    store = project_store(project_dir)
    stacks = detect_stacks(project_dir)
    facts = global_facts()
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
    seed_idx = est_tokens(idx_text)
    classified: list = []   # (name, fm, text, status, path, want, rel) — statuses FROZEN at scan time
    for name, fm, text in facts:
        rel = is_relevant(fm, stacks)
        path = store / f"{name}.md"
        present = path.exists()
        cur = (_safe_read_text(path) or "") if present else ""   # store-scan convention (v0.1.69 Gate-2b)
        is_mirror = present and _is_mirror(cur)
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
        want = _as_mirror(text, name, since=since, body_hash=new_hash)
        if _migrated and not _frontmatter(want).get("global_ref_since"):
            # PR-#91 adversarial F2a: a no-metadata-block mirror (the `# global_ref:` fallback form)
            # can never receive the stamp — without this, EVERY refresh of such a mirror reported
            # "restamped 1" forever while global_ref_since stayed absent. A migration that didn't
            # happen must not be reported as one; the mirror stays on the documented mtime fallback.
            _migrated = False
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
        elif cur == want:
            status = "in-sync"
        else:
            status = "STALE-mirror"  # canonical changed → must refresh
        if pull and status == "STALE-mirror" and _migrated:
            # counts ONLY the mtime-seeded migrations (PR-#91 review: the old not-yet-stamped gate also
            # counted a legacy mirror whose canonical BODY changed this same pass — branch 3, seeded from
            # NOW — making the RESULT's "seeded from each mirror's mtime" clause dishonest for that subset;
            # a body-changed legacy mirror is a genuine content refresh, reported as plain `refreshed`).
            restamped += 1
        classified.append((name, fm, text, status, path, want, rel))
    # v0.1.75 (audit F7 — the M4-bypass SURFACE): promote() refuses an undetectable `stacks:` tag, but the
    # SKILL's documented Phase-4 NET-NEW path hand-writes canonicals directly — a typo'd ('gpuu') or
    # real-but-undetectable ('release') tag lands unvalidated, and the canonical is FLEET-DEAD:
    # is_relevant can never match it to ANY project, silently, forever. Every dream's Phase 1 walks this
    # read path, so warn HERE (report-only, never a block) — the loop-native surface for the bypass.
    for _fn, _ffm, _t, _s, _p, _w, _r in classified:
        if _ffm.get("scope") == "stack-general":
            _fs = _fact_stacks(_ffm)
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
    items = [(name, status, est_tokens(_pointer_line(name, fm)), _index_line_cost(idx_text, name))
             for name, fm, _t, status, _p, _w, rel in classified if rel and status in ("MISSING", "STALE-mirror")]
    plan = _plan_pull(items, seed_idx, allow_net_grow, budget=INDEX_CEILING_TOKENS)
    # v0.1.41 → v0.1.73: --evict <fact> — the EVICT-TO-RECEIVE valve (the release for M1's hold),
    # rebuilt on measured accounting. Pre-checks BEFORE any delete (Guard-3 no-partial-state); the
    # swap gate is an A/B REPLAY of the actual pull plan, so acceptance and outcome cannot diverge
    # the way the old static held_pre pre-scan did. The agent NAMES the fact (report-then-apply).
    if pull and evict is not None:
        if not _safe_stem(evict):    # v0.1.70 security: same charset guard promote() applies to local_fact/canon_name
            print(f"evict: {evict!r} is not a safe fact name (must match {_SAFE_NAME!r}, no path separators) "
                  "— refusing", file=sys.stderr); return 1
        if _is_reserved_stem(evict):  # Gate-2a: the charset guard alone still let 'MEMORY' through —
            # store / 'MEMORY.md' IS the live index (_idxp above); unlink()'ing it and rebuilding from
            # scratch silently drops every previously-indexed pointer (mirrors AND project-authored
            # locals) with rc=0 and no error. Same reserved-name guard promote() already applies.
            print(f"evict: '{'/'.join(_RESERVED_STEMS)}' is a reserved index name, not a fact — refusing "
                  "(it would clobber the store's own always-loaded MEMORY.md index)", file=sys.stderr); return 1
        ep = store / f"{evict}.md"
        if not ep.exists():
            print(f"evict: no local fact '{evict}' in {store}", file=sys.stderr); return 1
        _ep_text = _safe_read_text(ep)   # v0.1.69 Gate-2b: TOCTOU since the ep.exists() check above —
        if _ep_text is None:              # a vanished evict target refuses cleanly, same as "not present"
            print(f"evict: '{evict}' vanished from {store} — refusing (nothing to evict)", file=sys.stderr); return 1
        if _is_mirror(_ep_text):
            # v0.1.73 (F1, measured): a mirror of a live relevant canonical re-pulls into the freed
            # room THIS same pass (or oscillates held forever) — a destructive op that gains nothing.
            print(f"evict: '{evict}' is a managed MIRROR (global_ref) — evicting it is self-defeating "
                  "(the live canonical re-pulls into the freed room this same pass). The lever for a "
                  "mirror is the GLOBAL store: demote/delete the canonical (then --gc --apply), or "
                  "tighten its description.", file=sys.stderr); return 1
        inbound = _inbound_links(store, evict)
        if inbound:
            print(f"evict: '{evict}' is [[linked]] by {inbound} — evicting it would ORPHAN those links. "
                  "Pick another fact, or de-link first.", file=sys.stderr); return 1
        if not plan["held"]:
            # under --allow-net-grow nothing is ever held → this refuses ("nothing to receive")
            # rather than a gratuitous delete-then-pull-all — the pre-v0.1.73 behavior, kept.
            print(f"evict: nothing is held (no past-the-ceiling MISSING globals) — evicting '{evict}' would free "
                  "room for NOTHING. There is no swap to make.", file=sys.stderr); return 1
        freed = _index_line_cost(idx_text, evict)   # MEASURED from the live index — never derived (F2)
        if freed == 0:
            print(f"evict: '{evict}' has no pointer line in the live index — evicting it frees NOTHING "
                  "(freed is MEASURED from MEMORY.md, never derived from frontmatter). Pick an indexed fact.",
                  file=sys.stderr); return 1
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
                  file=sys.stderr); return 1
        if displaced:
            # count strictly increased but the composition shifted — proceed, and say so honestly
            print(f"  ⚠ evict replan displaced {', '.join(displaced)} (freed room re-ordered the pulls; "
                  f"net {len(plan_evict['pull'])} land vs {len(plan['pull'])} without the evict)", file=sys.stderr)
        ep.unlink()
        _remove_index_pointer(store, evict)
        plan = plan_evict   # the gate approved THIS plan; the write loop below executes exactly it
        print(f"  ✓ evicted '{evict}' (~{freed} tok freed, measured) → lands: {', '.join(gain)}", file=sys.stderr)
    pulled_set = set(plan["pull"])
    held_facts: list = plan["held"]   # (name, cost) — drives the RESULT line + the evict-to-receive offer
    for name, fm, text, status, path, want, rel in classified:
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
            store.mkdir(parents=True, exist_ok=True)
            path.write_text(want, encoding="utf-8")
            # v0.1.66: count for the RESULT line ONLY when the pointer was actually WRITTEN this pass — a
            # STALE-mirror refresh whose BODY changed but whose derived pointer line didn't (description/
            # scope unchanged) makes _ensure_index_pointer correctly no-op (no stderr lint fired inside it).
            # Use its OWN returned (wrote, is_fat) — never re-derive via a second _pointer_line/
            # _fat_hook_warning call (a max-effort code-review workflow, 2026-07-04, found the original
            # discard-then-recompute shape here IS how a real accounting bug got in: it over-counted AND
            # mislabeled a no-op as "written"; a second finding flagged the recompute itself as the root
            # single-source-of-truth risk, refactored away by returning is_fat directly).
            _wrote, _is_fat = _ensure_index_pointer(store, name, fm)
            if _is_fat:
                fat += 1
            if status == "MISSING":
                pulled += 1
            else:
                refreshed += 1
        # record provenance for ANY fact this project now holds as a mirror (incl. already in-sync), so the
        # network graph reflects reality. EXCLUDE a HELD MISSING — it was NOT pulled, so the project does NOT
        # hold it; recording it would write a PHANTOM holder edge into the shared canonical (and lie in the graph).
        if pull and rel and status in ("MISSING", "STALE-mirror", "in-sync") and not held_this:
            _record_provenance(name, project_dir.name)  # this mind holds the fact
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
    _n_frozen = sum(1 for _n2, _f2, _t2, _s2, _p2, _w2, _r2 in classified if _s2 == "frozen(mirror)")
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
    return 0


def _record_provenance(name: str, project: str) -> None:
    """Add `project` to the canonical fact's `projects:` list — the synapse record.

    As a fact propagates to more projects, its provenance grows; that list IS the
    cross-project network's edge set (which minds hold which memory).

    v0.1.71 (Track D-2, accepted gap): this read-modify-write is NOT mutually exclusive
    across processes. Two concurrent promotes/pulls touching the SAME canonical can both
    read the list before either writes; the second (atomic, via `_atomic_write_text`)
    write can still overwrite the first's append, dropping one `projects:` entry. Left
    as a documented gap, not fixed with a lock: the window is milliseconds wide (fires at
    dream/arc boundaries, not continuously), the canonical's BODY is untouched, and the
    miss self-heals the next time the dropped project's own dream promotes/pulls again. A
    real fix needs either `fcntl` (banned — this repo's no-POSIX-only-modules guarantee)
    or a hand-rolled staleness-detecting lock (its own bug class) — disproportionate for
    an undercount-by-one on a non-load-bearing list. See
    docs/track-d-write-atomicity-seed-hardening.spec.md D-2."""
    p = GLOBAL / f"{name}.md"
    text = _safe_read_text(p)   # v0.1.69 Gate-2b: TOCTOU-tightened — a vanished canonical is
    if text is None:            # nothing to record provenance for (same as the old not-exists early-return)
        return
    # `project` is a directory basename written into a SHARED canonical's frontmatter.
    # Sanitize it to the safe charset before it ever lands there, so it can't smuggle
    # YAML/markdown into the shared store (and can't carry a regex backreference below).
    project = _sanitize_token(project)
    m = re.search(r"^(\s*projects:\s*)\[([^\]]*)\]\s*$", text, re.M)
    if m:
        items = [x.strip() for x in m.group(2).split(",") if x.strip()]
        if project in items:
            return
        items.append(project)
        _atomic_write_text(p, text[: m.start()] + f"{m.group(1)}[{', '.join(items)}]" + text[m.end():])
    else:  # no projects line yet — add one after scope/node_type. Use a replacement
        # FUNCTION (not an f-string template) so `project` is never scanned for `\1`-style
        # backreferences by re.sub.
        new = re.sub(r"(\n\s*(?:scope|node_type):.*\n)",
                     lambda mm: f"{mm.group(1)}  projects: [{project}]\n", text, count=1)
        _atomic_write_text(p, new)


def _holders(fm: dict) -> list[str]:
    # v0.1.76 (audit): parse the SAME token space _sanitize_token WRITES. The old alnum-first-char
    # regex silently shortened a dot/dash-prefixed holder ('.claude' → 'claude'; the sanitized
    # '-scope' from '@scope' → 'scope'), so gc's dead-edge compare could never match such a project
    # and network()/--utility displayed a name provenance doesn't hold. Tokens must still carry ≥1
    # alnum (a bare '-'/'.' is separator noise, not a holder); single-character names still kept.
    return [t for t in re.findall(r"[A-Za-z0-9._-]+", fm.get("projects", ""))
            if any(c.isalnum() for c in t)]


def _mind_unresolved(name: str) -> bool:
    """v0.1.76 (audit): True iff NO slug dir under ~/.claude/projects plausibly matches this
    provenance basename — the honest partial inverse of the lossy slug (sanitized-token endswith
    match). CONSERVATIVE direction: any match — including an ambiguous one — reads as resolved;
    only a zero-match mind is flagged. Display-only (a `?` glyph + footnote in network()); never a
    prune input — provenance stays reported-not-pruned (a renamed project also matches nothing).
    Train-review F1 (measured on the real fleet): normalize in SLUG space (every non-alnum → '-',
    the slug_for/near_duplicate_slugs rule) — the original _sanitize_token normalization PRESERVES
    '_'/'.' while slug dirs map them to '-', so a live underscore-named project (Doc_Flo) could
    never match its own on-disk store and was falsely flagged dead."""
    norm = re.sub(r"[^a-z0-9]", "-", name.lower())
    base = Path.home() / ".claude" / "projects"
    if not norm.strip("-.") or not base.is_dir():
        return False   # degenerate token / no projects dir → nothing claimable; stay conservative
    for d in base.iterdir():
        s = d.name.lower()
        if s == norm or s.endswith("-" + norm):
            return False
    return True


def network() -> int:
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
    facts = global_facts()
    minds = sorted({p for _, fm, _ in facts for p in _holders(fm)})
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
            held = len(_holders(fm))
            flag = "" if held == len(minds) else f"  (only {held}/{len(minds)} so far)"
            out.append("    " + _ui.c("•", "cyan") + f" {n}" + _ui.c(flag, "dim"))
    else:
        out.append("    " + _ui.c("(none)", "dim"))

    # Differential edges — the meaningful topology (stack-general bindings)
    out.append("")
    out.append(_ui.kv("EDGES", _ui.c("stack-general — the bindings that carry real signal", "dim")))
    proj_diff: dict[str, set[str]] = {}
    for n, fm in differential:
        for pr in _holders(fm):
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
def _remove_index_pointer(store: Path, name: str) -> bool:
    """Drop the pointer line for `name` from the project index. Returns True if removed."""
    idx = store / "MEMORY.md"
    _idx_text = _safe_read_text(idx)   # v0.1.69 Gate-2b: TOCTOU-tightened (was exists()-then-read)
    if _idx_text is None:
        return False
    lines = _idx_text.splitlines()
    kept = [ln for ln in lines if f"]({name}.md)" not in ln]  # match the link target, not a spoofable substring
    if len(kept) == len(lines):
        return False
    idx.write_text("\n".join(kept).rstrip() + "\n", encoding="utf-8")
    return True


def _orphans(store: Path, canon: "set[str] | None" = None) -> list[str]:
    """Mirror files (`global_ref:`) in this store whose CANONICAL no longer exists in
    the global store. These are the dead memory --pull can never reclaim (it only
    iterates LIVE globals), so they accrue forever — the leak Fix B closes.
    v0.1.75: gc() passes `canon` from its ONE global_facts() snapshot, so the mass-delete
    safety guard and this scan can never see different store states (the audit's guard-TOCTOU:
    a store emptying between the guard's read and a second read here would have made EVERY
    mirror look orphaned — the exact wipe the guard exists to prevent). Default None
    self-computes (direct/test callers keep working)."""
    if canon is None:
        canon = {n for n, _, _ in global_facts()}
    out: list[str] = []
    if not store.exists():
        return out
    for f in store.glob("*.md"):
        if f.name == "MEMORY.md" or _is_reserved_stem(f.stem):
            continue
        text = _safe_read_text(f)    # v0.1.69/A3 (Gate-2a follow-up): store-scan convention — a
        if text is None:             # vanished/unreadable fact must not abort the orphan scan
            continue
        if _is_mirror(text) and f.stem not in canon:  # ONLY managed mirrors (frontmatter key)
            out.append(f.stem)
    return out


def gc(project_dir: Path, apply: bool) -> int:
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
    risks erasing real edges. The proven win is removing the orphan files."""
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
    # v0.1.75: ONE global_facts() snapshot — the guard, the orphan scan, the frozen scan, and the
    # dead-edge report all see the SAME store state (the audit's guard-TOCTOU: a store emptying
    # between the guard's read and a second scan read would have made every mirror look orphaned —
    # the exact mass-wipe the guard exists to prevent).
    gfacts = global_facts() if GLOBAL.exists() else []
    if not gfacts:
        why = "absent" if not GLOBAL.exists() else "present but empty (no canonical facts)"
        print(f"global store {GLOBAL} is {why} — refusing to GC "
              "(cannot distinguish that from all-canonicals-deleted).")
        return 0
    store = project_store(project_dir)
    orphans = _orphans(store, canon={n for n, _, _ in gfacts})
    # v0.1.75 (audit F6): FROZEN mirrors — see the docstring. Detected against the SAME snapshot.
    stacks = detect_stacks(project_dir)
    canon_fm = {n: fm for n, fm, _ in gfacts}
    frozen: list = []
    if store.exists():
        for f in sorted(store.glob("*.md")):
            if f.name == "MEMORY.md" or _is_reserved_stem(f.stem) or f.stem not in canon_fm:
                continue
            t = _safe_read_text(f)   # store-scan convention — a vanished file must not abort the scan
            if t is not None and _is_mirror(t) and not is_relevant(canon_fm[f.stem], stacks):
                frozen.append(f.stem)
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
    for name in orphans:
        if apply:
            (store / f"{name}.md").unlink(missing_ok=True)
            _remove_index_pointer(store, name)
            removed += 1
            out.append("    " + _ui.c("✓", "green") + f" removed {name}  " + _ui.c("(file + index pointer)", "dim"))
        else:
            out.append("    " + _ui.c("·", "yellow") + f" {name}  " + _ui.c("(would remove file + index pointer)", "dim"))
    out.append(_ui.kv("FROZEN", f"{len(frozen)} mirror(s) whose canonical is ALIVE but irrelevant here (dropped stack)"
               + ("" if frozen else "  " + _ui.c("· none", "dim"))))
    removed_frozen = 0
    for name in frozen:
        if apply:
            (store / f"{name}.md").unlink(missing_ok=True)
            _remove_index_pointer(store, name)
            removed_frozen += 1
            out.append("    " + _ui.c("✓", "green") + f" removed {name}  " + _ui.c("(re-pullable if the stack returns)", "dim"))
        else:
            out.append("    " + _ui.c("✻", "yellow") + f" {name}  " + _ui.c("(would remove file + index pointer; re-pullable — canonical stays)", "dim"))
    tail = (f"removed {removed} orphan(s) + {removed_frozen} frozen" if apply
            else "run with --apply to delete (surface these to the user first)")
    out.append("")
    out.append(_ui.kv("RESULT", tail))
    # Dead-edge provenance, report-only (conservative — see docstring).
    if apply:
        print(_ui.ascii_translate("\n".join(out)))
        return 0
    dead = []
    for name, fm, _ in gfacts:
        for holder in _holders(fm):
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


def promote(project_dir: Path, local_fact: str, canon_name: str, prefer_canonical: bool = False) -> int:
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

    GLOBAL.mkdir(parents=True, exist_ok=True)
    canon_path = GLOBAL / f"{canon_name}.md"
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
    _dangling = _nonglobal_wikilinks(local_text, GLOBAL, exclude=canon_name)
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

    # Write the canonical from the (re-scoped) local fact — but NEVER overwrite an existing one.
    # v0.1.71 (Track D-2b): `reconcile` was computed from `canon_path.exists()` back at guard-setup
    # time — if a DIFFERENT process concurrently creates the SAME canon_name in the window since,
    # an unconditional write here would silently clobber it (and, via the mirror-write below, erase
    # the loser's own local copy too — this exact race, found at Gate-1 review, is why `reconcile`
    # can't just be trusted this many lines later). `_create_exclusive` closes it: False means
    # someone else's canonical won the race, untouched — refuse and ask the caller to retry (which
    # correctly reconciles against it, since `canon_path.exists()` is now true).
    if not reconcile:
        try:
            _created = _create_exclusive(canon_path, local_text)
        except OSError as _e:
            # v0.1.76 (audit): os.link raises EPERM/EOPNOTSUPP/ENOSYS on a no-hardlink filesystem
            # (FAT/exFAT, some network mounts) — that used to propagate as a raw traceback mid-promote.
            # Refuse CLEANLY instead: nothing has been written (the finally cleaned the temp), and the
            # race guard genuinely needs hardlink atomicity (see _create_exclusive — os.replace can't
            # detect "am I first", raw O_EXCL reopens the torn-read window Track D-1 closed).
            print(f"promote: cannot create the canonical atomically ({type(_e).__name__}: {_e}) — "
                  "commonly a filesystem without hardlink support (os.link, which the create-create "
                  "race guard needs), but check the error itself (e.g. ENOSPC is disk-full, not a "
                  "hardlink problem). Nothing was written.", file=sys.stderr)
            return 1
        if not _created:
            print(f"promote: another process just created the canonical '{canon_name}' concurrently — "
                  "refusing to risk a silent clobber. Re-run promote — it will now correctly "
                  "reconcile against the canonical that landed.", file=sys.stderr)
            return 1
    _record_provenance(canon_name, project_dir.name)
    canon_text = canon_path.read_text(encoding="utf-8", errors="replace")  # re-read POST-provenance
    fm = _frontmatter(canon_text)

    # Convert the origin's copy into a managed mirror of the POST-provenance canonical, so a later
    # --pull reports `in-sync` (not a spurious STALE-mirror refresh) and never re-creates a shadow.
    # v0.1.78: minted with a FRESH evidence-clock stamp (a just-promoted lineage begins now); the next
    # --pull carries it (same body hash), preserving the Probe-K byte-identical follow-up invariant.
    dest.write_text(_as_mirror(canon_text, canon_name, since=_now_iso(), body_hash=_body_hash(canon_text)),
                    encoding="utf-8")
    _ensure_index_pointer(store, canon_name, fm)
    renamed = canon_name != local_fact
    if renamed:  # the dup/orphan guard: drop the old-named project-authored file + its index pointer …
        _remove_index_pointer(store, local_fact)
        if src.exists() and not src.samefile(dest):  # … but NOT when src IS the freshly-written mirror
            src.unlink()                             # (a case-only rename on a case-insensitive FS)

    # Change-1↔Change-3 link: if the ORIGIN itself doesn't detect this stack-general fact's stack,
    # its own mirror reads `irrelevant` on the next --pull and freezes (never refreshes) — almost
    # always a mis-tag. WARN (the local recall still works + other matching projects pull the live
    # copy); don't refuse.
    if scope == "stack-general":
        origin_stacks = detect_stacks(project_dir)
        if not (_fact_stacks(fm) & origin_stacks):
            print(f"  ⚠ origin {project_dir.name} does not detect stack(s) {sorted(_fact_stacks(fm))} "
                  f"(detected: {sorted(origin_stacks) or '∅'}) — its own mirror will read irrelevant "
                  "and won't refresh on --pull (likely a mis-tag)", file=sys.stderr)

    # v0.1.67 (Phase C): the fleet-tax ADVISORY — post-write script truth, WARN-only (never a block; a
    # hard fleet gate needs its own oracle-grade review). Each canonical's pointer taxes every holder
    # node's always-loaded index every session; surface when the fleet total crosses the advisory.
    _tot = sum(est_tokens(_pointer_line(n, f)) * len(_holders(f)) for n, f, _ in global_facts())
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
    out.append(_ui.kv("NEXT", _ui.c("add the canonical's line to ~/.claude/memory/MEMORY.md; same-scope "
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
    return _label_from_slug(store.parent.name)


def _node_tokens(store: Path) -> dict:
    """ESTIMATED token cost of one node's auto-memory: the always-loaded index plus the
    recall-fact pool. Tokens are ≈ chars/4 (est_tokens) — an estimate, not exact.

    Also ATTRIBUTES the always-loaded index cost to mirror-vs-local pointers
    (`mirror_index_tokens`): the share of the per-session tax driven by replicated
    cross-project facts (`global_ref:` mirrors). This is the load-bearing signal when an
    index goes over budget — a mirror-dominated overflow's only effective lever is the
    canonical in the GLOBAL store (demote/delete + GC fleet-wide); LOCAL pruning is
    futile because `run()` re-pulls the mirror next cycle."""
    idx = store / "MEMORY.md"
    idx_text = _safe_read_text(idx) or ""    # store-scan convention: a vanished index reads as absent
    bodies: dict[str, str] = {}
    for f in store.glob("*.md"):
        if f.name == "MEMORY.md" or _is_reserved_stem(f.stem):
            continue
        body = _safe_read_text(f)             # store-scan convention (shared helper — v0.1.69 Gate-2a)
        # v0.1.76 (audit): exclude ARCHIVE-INDEX docs (link-lists like SHIPPED.md — no frontmatter,
        # ≥3 links) — memory_status's own C1 fact/archive split, applied here too. They were counted
        # as recall facts (a live node's 7.6k-tok SHIPPED.md inflated recall_tokens + `facts`), so
        # --tokens over-reported any store using the archive convention. Same text-level rule
        # (_is_archive_index_text), single source — the two counters cannot drift.
        if body is not None and not _is_archive_index_text(body):
            bodies[f.stem] = body
    mirror_stems = {stem for stem, b in bodies.items() if _is_mirror(b)}
    # Attribute the index pointer lines whose target fact (`](<stem>.md)`) is a mirror.
    # That is the fraction of the always-loaded tax the global store controls — what the
    # over-budget remedy must actually target. Estimate the matched lines as ONE blob (the
    # same way always_loaded estimates the whole file), NOT a per-line est_tokens sum: the
    # ceiling in est_tokens rounds each line up independently, so a per-line sum can exceed
    # the whole-file total and break the mirror ⊆ total invariant (and render >100%).
    mirror_lines = [ln for ln in idx_text.splitlines()
                    if (m := re.search(r"\]\(([^)]+)\.md\)", ln)) and m.group(1) in mirror_stems]
    mirror_index_tokens = est_tokens("\n".join(mirror_lines))
    return {
        "always_loaded_tokens": est_tokens(idx_text),
        "mirror_index_tokens": mirror_index_tokens,
        "recall_tokens": sum(est_tokens(b) for b in bodies.values()),
        "facts": len(bodies),                 # readable facts only — a vanished file is not counted
        "shared": len(mirror_stems),
    }


def _network_nodes() -> list[Path]:
    """Network nodes = project memory stores holding ≥1 shared (`global_ref:`) mirror.

    This is the PHYSICAL, measurable node set (we have each store's path, so we can
    weigh its tokens). It deliberately differs from network()'s LOGICAL `minds` set
    (derived from provenance basenames, which can't be inverted to a store path) — the
    two views can diverge (names vs slugs); --network = topology, --tokens = cost."""
    base = Path.home() / ".claude" / "projects"
    nodes: list[Path] = []
    if not base.exists():
        return nodes
    for proj in sorted(base.iterdir()):
        store = proj / "memory"
        if not store.is_dir():
            continue
        has_mirror = False
        for f in store.glob("*.md"):
            if f.name == "MEMORY.md" or _is_reserved_stem(f.stem):
                continue
            body = _safe_read_text(f)         # store-scan convention (shared helper — v0.1.69 Gate-2a)
            if body is not None and _is_mirror(body):
                has_mirror = True
                break
        if has_mirror:
            nodes.append(store)
    return nodes


def token_network(project_dir: Path) -> dict:
    """Build the `network` block of the cycle record: per-node ESTIMATED token cost
    across every node in the shared-memory network, with the triggering node flagged."""
    project_dir = project_dir.resolve()
    trigger_store = project_store(project_dir)
    nodes = []
    al_total = rc_total = mir_total = 0
    for store in _network_nodes():
        m = _node_tokens(store)
        is_trigger = store.resolve() == trigger_store.resolve()
        nodes.append({
            # _sane the trigger label too — it's the argv-supplied project_dir.name
            "node": _sane(project_dir.name) if is_trigger else _node_label(store),
            "trigger": is_trigger,
            **m,
        })
        al_total += m["always_loaded_tokens"]
        rc_total += m["recall_tokens"]
        mir_total += m["mirror_index_tokens"]
    return {
        "basis": "≈ chars/4 (heuristic estimate, not a tokenizer)",
        "node_def": "project stores holding ≥1 shared fact",
        "trigger": _sane(project_dir.name),
        "nodes": nodes,
        # mirror_index_tokens: the share of the always-loaded total controlled by the
        # GLOBAL store (replicated mirrors) — the lever for a mirror-dominated overflow.
        "totals": {"nodes": len(nodes), "always_loaded_tokens": al_total,
                   "mirror_index_tokens": mir_total, "recall_tokens": rc_total},
    }


def token_report(project_dir: Path, as_json: bool) -> int:
    import json
    net = token_network(project_dir)
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
    out.append("")
    out.append(_ui.kv("NODES", _ui.c("per-project always-loaded + recall-pool cost", "dim")))
    for n in sorted(net["nodes"], key=lambda d: -d["always_loaded_tokens"]):
        base = (f"    {_ui.lbl(n['node'][:24], 24)} always ≈{n['always_loaded_tokens']:>5} "
                + _ui.c(f"(≈{n.get('mirror_index_tokens', 0)} mirror)", "dim")
                + f" · recall ≈{n['recall_tokens']:>6} · {n['facts']:>2} facts "
                + _ui.c(f"({n['shared']} shared)", "dim"))
        if n["trigger"]:  # keep the dense node columns intact — drop the mark to a hanging line only if it would overflow
            mk = _ui.c("◀ trigger", "cyan")
            base += "  " + mk if _ui.vis(base) + 11 <= _ui.W else "\n" + " " * 29 + mk
        out.append(base)
    if not net["nodes"]:
        out.append("  " + _ui.c("(no nodes hold shared facts yet — run --pull somewhere first)", "dim"))
    print(_ui.ascii_translate("\n".join(out)))
    return 0


# ── v0.1.80: fleet STALENESS — absorption lag, measured per node (beacon Stage A) ────────────────
def _all_stores() -> "list[Path]":
    """EVERY project store under ~/.claude/projects holding ≥1 *.md — deliberately wider than
    _network_nodes() (mirror-holders): a store with ZERO mirrors is exactly the most starved node
    the staleness sweep exists to surface."""
    base = Path.home() / ".claude" / "projects"
    out: list = []
    if base.is_dir():
        for proj in sorted(base.iterdir()):
            store = proj / "memory"
            if store.is_dir() and any(store.glob("*.md")):
                out.append(store)
    return out


def _store_gaps(store: Path, stacks: "set | None", gfacts: list, body_hashes: dict) -> "tuple[int, int]":
    """(missing, content_stale) for ONE store against the given relevance basis — the SINGLE gap
    predicate shared by fleet_staleness (per node) and the SessionStart beacon (its own store);
    v0.1.81, factored so the two can never diverge. `stacks=None` → user-global-only (the honest
    no-cache basis). Same review-hardened edges as the staleness sweep: a PRESENT-but-unreadable
    file is neither missing nor stale (under-report, the pinned bias)."""
    missing = stale = 0
    for n, fm, _text in gfacts:
        if not is_relevant(fm, stacks if stacks is not None else set()):
            continue
        p = store / f"{n}.md"
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
    project_dir = project_dir.resolve()
    gfacts = global_facts()
    trig_store = project_store(project_dir)
    trig_stacks = detect_stacks(project_dir)
    ledger_nodes = {str(r.get("node", "")) for r in _ledger_rows()}
    now_ep = datetime.now(timezone.utc).timestamp()
    body_hashes = {n: _body_hash(t) for n, _fm, t in gfacts}
    stores = _all_stores()
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
        missing, stale = _store_gaps(store, trig_stacks if is_trig else cached_stacks, gfacts, body_hashes)
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
    return GLOBAL / ".fleet-usage.jsonl"


def _ledger_rows() -> list:
    """Guarded tail read of the shared harvest ledger (docs/fleet-usage-harvest.spec.md) —
    malformed lines skipped, never fatal. A dot-file in GLOBAL: structurally invisible to
    global_facts()'s *.md glob, to --pull, and to every index — zero always-loaded tax."""
    import json
    text = _safe_read_text(_ledger_path())
    if text is None:
        return []
    rows: list = []
    for ln in text.splitlines()[-_LEDGER_TAIL_CAP:]:
        try:
            o = json.loads(ln)
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(o, dict):
            rows.append(o)
    return rows


def _append_ledger(row: dict) -> None:
    """One-line O_APPEND|O_CREAT 0o600 append. Concurrency stance = the documented D-2
    accepted-gap philosophy (dream-boundary cadence). PR-#92 review precision: O_APPEND
    atomicity is only POSIX-guaranteed under PIPE_BUF (~4KB) and a fat 40-fact row can reach
    that, so a rare concurrent-dream append could tear a line — accepted, because the reader
    (_ledger_rows) skips unparseable lines and the next harvest re-covers the window
    (self-healing, same class as D-2). Script-truth telemetry in the render_dashboard
    --persist class, never a memory-content write."""
    import json
    GLOBAL.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(_ledger_path()), os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
    try:
        os.write(fd, (json.dumps(row) + "\n").encode("utf-8"))
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
    proj_root = store.parent
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
    stores = _network_nodes()
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
        row = _harvest_node(store, marks.get(store.parent.name, (0.0, ""))[1], by=_sane(project_dir.name))
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
    canon = {n: fm for n, fm, _ in global_facts()}
    stores = _network_nodes()
    trig = project_store(project_dir)
    if trig.is_dir() and trig.resolve() not in {s.resolve() for s in stores}:
        stores.append(trig)
    nodes_reporting = nodes_harvested = 0
    ledger_by_node: dict = {}
    for _lr in _ledger_rows():
        if isinstance(_lr.get("per_fact"), list):
            ledger_by_node.setdefault(str(_lr.get("node", "")), []).append(_lr)
    per: dict = {n: {"reads": 0, "windows": 0, "last": "", "_ep": None, "shadow": 0, "fallback": 0,
                     "h_reads": 0, "h_windows": 0} for n in canon}
    for store in stores:
        hist = usage_history(store)
        if hist["windows_full"] >= 1:
            nodes_reporting += 1
        # v0.1.79 (docs/fleet-usage-harvest.spec.md, the v1 rule): harvested ledger rows contribute
        # ONLY for a node with NO own-log usage at all — own-log strictly primary, no interval-overlap
        # math, no double-count risk (mixed-node merging is the consumption release's refinement).
        hrows: list = []
        if hist["windows_full"] == 0 and not hist["per_fact"]:
            hrows = ledger_by_node.get(store.parent.name, [])
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
                    if isinstance(pf, dict) and pf.get("name") == stem:
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
    total_tax = 0
    unheld: list = []
    for stem, fm in canon.items():
        pt = est_tokens(_pointer_line(stem, fm))
        holders = _holders(fm)
        tax = pt * len(holders)
        total_tax += tax
        e = {"name": stem, "scope": fm.get("scope", ""), "reads": per[stem]["reads"],
             "windows": per[stem]["windows"], "last": per[stem]["last"],
             "holders": len(holders), "pointer_tok": pt, "fleet_tax": tax}
        if per[stem]["shadow"]:
            e["shadow_reads"] = per[stem]["shadow"]
        if per[stem]["fallback"]:   # v0.1.78: evidence-provenance — holders still on the mtime clock
            e["fallback_nodes"] = per[stem]["fallback"]
        if per[stem]["h_reads"] or per[stem]["h_windows"]:   # v0.1.79: harvested, source-labeled
            e["harvested_reads"] = per[stem]["h_reads"]
            e["windows_harvested"] = per[stem]["h_windows"]
        if not holders:
            unheld.append(stem)
        entries.append(e)
    entries.sort(key=lambda e: (-e["fleet_tax"], e["name"]))
    return {"nodes": len(stores), "nodes_reporting": nodes_reporting, "nodes_harvested": nodes_harvested,
            "canonicals": entries,
            "total_fleet_tax": total_tax, "advisory": GLOBAL_FLEET_TAX_ADVISORY, "unheld": unheld}


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
                            "provenance UPPER bound (dead edges reported by --gc, never auto-pruned)"
                            + (f" · harvested ledger covers {u['nodes_harvested']} no-own-usage node(s)"
                               if u.get("nodes_harvested") else ""), "dim"))
    out.append(_ui.rule())
    out.append("")
    over = _ui.c("  ⚠ over advisory (warn-only — evidence for gc/demote judgment, never a gate)", "red") \
        if u["total_fleet_tax"] > u["advisory"] else ""
    out.append(_ui.kv("FLEET TAX", f"{_ui.bar(u['total_fleet_tax'], u['advisory'])} "
               + _ui.c(f"≈{u['total_fleet_tax']}/{u['advisory']} est tok · Σ pointer × holders over "
                       f"{len(u['canonicals'])} canonical(s)", "dim") + over))
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
        out.append(f"    {_ui.lbl(e['name'][:40], 40)} {e['fleet_tax']:>5}t "
                   + _ui.c(f"({e['pointer_tok']}t × {e['holders']})", "dim") + f"  {ev}{shadow}{harv}")
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
_CUED_MODES = ("--list", "--pull", "--gc", "--tokens", "--utility", "--harvest")


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
    pos = [a for a in args[1:] if not a.startswith("-")]
    project_dir = Path(pos[0]) if pos else Path.cwd()
    if args and args[0] == "--network":
        return network()
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
        return token_report(project_dir, "--json" in args)
    if args and args[0] == "--utility":   # v0.1.67 (Phase C): fleet usage evidence (READ-ONLY, like --list)
        return utility_report(project_dir, "--json" in args)
    if args and args[0] == "--harvest":   # v0.1.79: capture every node's usage windows into the shared ledger
        return harvest(project_dir)
    if args and args[0] == "--staleness":   # v0.1.80: READ-ONLY absorption-lag sweep (beacon Stage A)
        return staleness_report(project_dir, "--json" in args)
    if args and args[0] == "--gc":
        return gc(project_dir, "--apply" in args)
    if args and args[0] == "--promote":
        # --promote PROJECT_DIR LOCAL_FACT [CANON_NAME]  (CANON_NAME defaults to LOCAL_FACT)
        if len(pos) < 2:
            print("usage: sync_global.py --promote PROJECT_DIR LOCAL_FACT [CANON_NAME] [--prefer-canonical]", file=sys.stderr)
            return 2
        return promote(Path(pos[0]), pos[1], pos[2] if len(pos) >= 3 else pos[1], prefer_canonical="--prefer-canonical" in args)
    if not args or args[0] not in ("--list", "--pull"):
        print("usage: sync_global.py --list|--pull [--allow-net-grow] [--evict=FACT] PROJECT_DIR | --gc [--apply] PROJECT_DIR "
              "| --promote PROJECT_DIR LOCAL_FACT [CANON_NAME] [--prefer-canonical] | --tokens [--json] PROJECT_DIR "
              "| --utility [--json] PROJECT_DIR | --harvest PROJECT_DIR | --staleness [--json] PROJECT_DIR "
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
