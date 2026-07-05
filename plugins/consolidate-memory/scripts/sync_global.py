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
  --pull --evict=FACT  EVICT-TO-RECEIVE (v0.1.41): free one low-value local pointer (FACT) so a HELD global can
                       land — net-neutral, so M1's budget stays enforced. The release valve for a chronically-full
                       store. Refuses an orphaning evict (FACT has inbound [[links]]) or a too-small one (frees
                       less than the smallest held). A plain `--pull` with anything held prints the candidates.
  --promote PROJECT_DIR LOCAL_FACT [CANON_NAME] [--prefer-canonical]
                       hand a project-authored local fact UP to the canonical global store and
                       convert the origin's copy into a managed mirror (the local→canonical
                       promotion hand-off; never leaves a dup/orphan — see promote()). A RECONCILE
                       onto an existing canonical REFUSES if the local's body differs (M2 — would
                       silently discard it); --prefer-canonical keeps the canonical, drops the local
                       body (the dedup intent). stack-general stacks: must be DETECTABLE (M4).
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
import os
import re
import sys
from pathlib import Path

# est_tokens lives in memory_status (the measurement script); reuse it rather than
# re-deriving the heuristic. The sibling resolves because a script's own directory is
# on sys.path[0] at runtime; both live in the plugin's scripts/ dir.
import _ui  # sibling script: the shared visual vocabulary (color / rule / kv / glyphs)
from memory_status import (_is_mirror, _parse_ts, _sane, est_tokens, slug_for, _frontmatter, _valid_uuid,
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
    unit-testable without a filesystem. Stdlib-only (no `tomllib` — the plugin runs on 3.10)."""
    text = _strip_toml_comments(pyproject_text)
    names: set[str] = set()
    for sec in re.finditer(r"(?ms)^\[project\](.*?)(?=^\[|\Z)", text):          # PEP 621 main — ONLY under [project]
        names |= _arrays_under(sec.group(1), r"(?m)^\s*dependencies\s*=\s*(?=\[)")
    for sec in re.finditer(r"(?ms)^\[(?:project\.optional-dependencies|dependency-groups)[^\]]*\](.*?)(?=^\[|\Z)", text):
        names |= _arrays_under(sec.group(1), r"=\s*(?=\[)")                    # arrays inside those tables
    for sec in re.finditer(r"(?ms)^\[tool\.poetry(?:\.group\.[^\]]+)?\.(?:dev-)?dependencies\](.*?)(?=^\[|\Z)", text):
        for km in re.finditer(r"(?m)^\s*([A-Za-z0-9][A-Za-z0-9._-]*)\s*=", sec.group(1)):  # poetry table keys (+ legacy dev-)
            names.add(_norm_dep(km.group(1)))
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
    if re.search(r"(?m)^\s*\[tool\.mypy\]", _strip_toml_comments(_read_capped(project_dir / "pyproject.toml"))) or (project_dir / "mypy.ini").exists():
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
        if f.name == "MEMORY.md":
            continue
        # The stem becomes a filename AND is interpolated into each pulling project's
        # always-loaded index (`- [name](name.md) — …`). Reject any stem outside the
        # documented kebab-case charset so a crafted name can't inject markdown/links
        # into the tier-1 context of every project that pulls it.
        if not _safe_stem(f.stem):
            continue
        text = f.read_text(encoding="utf-8", errors="replace")
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


def _as_mirror(text: str, name: str) -> str:
    """Return the global fact stamped as a managed mirror (`global_ref: <name>`),
    robustly — drop any existing global_ref, then insert one after `metadata:`.

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
    dashes = 0                         # frontmatter = the span between the 1st and 2nd '---'
    for ln in text.splitlines():
        s = ln.strip()
        if s == "---":
            dashes += 1
        if s.startswith("global_ref:"):
            continue                   # drop any existing global_ref (re-stamped below)
        # v0.1.26 (provenance-churn root-fix): `projects:` is CANONICAL-ONLY bookkeeping (the synapse
        # record `network()`/`_holders` read off the global store). NEVER carry it into a mirror — else
        # every pull that grows a canonical's holder list marks all OTHER mirrors stale (cosmetic churn).
        # Frontmatter-scoped (dashes == 1) so a prose body line can never be stripped.
        if dashes == 1 and s.startswith("projects:"):
            continue
        out.append(ln)
        if not injected and not ln[:1].isspace() and s.rstrip(":") == "metadata":
            out.append(f"  global_ref: {name}")
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
    content = idx.read_text(encoding="utf-8") if idx.exists() else "# Memory Index\n\n"
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
    index over `budget` — the projected net-grow guard. `allow_net_grow` overrides. PURE + the single
    source for the hold decision in run() (so smoke can pin all cases deterministically).

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
        if f.name == "MEMORY.md" or f.stem == target:
            continue
        try:
            body = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if any(resolve_wikilink(l, {target}) == target for l in extract_wikilinks(body)):
            out.append(f.stem)
    return out


def _evict_frees_enough(running_idx: int, freed: int, held_costs: list, budget: int) -> bool:
    """v0.1.41 (evict-to-receive fit-check, no-partial-loss): would evicting a pointer that frees `freed` tokens
    make room for at least the SMALLEST held global? `(running_idx - freed) + min(held_costs) <= budget`. False ⇒
    the evict frees too little — REFUSE before deleting (Guard-3: never a destructive op that gains nothing).
    PURE (smoke-pinned). Caller ensures held_costs is non-empty (no held ⇒ nothing to receive ⇒ refuse earlier).
    `budget` is REQUIRED, no default — the same unenforced-drift-risk fix applied to `_would_net_grow`
    (v0.1.66); every real call site already passed it explicitly, so this only removes a silent fallback
    a future caller could accidentally rely on."""
    return bool(held_costs) and (running_idx - freed) + min(held_costs) <= budget


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
    project_dir = project_dir.resolve()
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

    glyphs = {"in-sync": ("✓", "green"), "MISSING": ("↓", "yellow"), "STALE-mirror": ("⟳", "yellow"),
              "present(local)": ("•", "cyan"), "irrelevant": ("·", "dim")}
    rows: list = []
    relevant = pulled = refreshed = held = fat = 0   # fat: v0.1.66 — pointers written over HOOK_TOKEN_WARN
    # M1: the running always-loaded index size (tokens). Each pulled MISSING fact grows it by its pointer's
    # cost; the guard below holds any pull that would push it over INDEX_TOKEN_BUDGET. Seed from the live index.
    _idxp = store / "MEMORY.md"
    running_idx = est_tokens(_idxp.read_text(encoding="utf-8", errors="replace")) if _idxp.exists() else est_tokens("# Memory Index\n\n")
    held_facts: list = []   # (name, cost) of relevant MISSING globals HELD this pass — drives the evict-to-receive offer
    # v0.1.41: --evict <fact> — the EVICT-TO-RECEIVE valve (the release for M1's hold). Free ONE low-value local
    # pointer so a held global can land; net-neutral, so M1's budget stays enforced. Pre-checks BEFORE any delete
    # (Guard-3 no-partial-state): the fact EXISTS, has NO inbound [[links]] (orphan-safety), held globals EXIST to
    # receive, and the freed room actually FITS the smallest held. The agent NAMES the fact (report-then-apply).
    if pull and evict is not None:
        ep = store / f"{evict}.md"
        if not ep.exists():
            print(f"evict: no local fact '{evict}' in {store}", file=sys.stderr); return 1
        inbound = _inbound_links(store, evict)
        if inbound:
            print(f"evict: '{evict}' is [[linked]] by {inbound} — evicting it would ORPHAN those links. "
                  "Pick another fact, or de-link first.", file=sys.stderr); return 1
        held_pre: list = []
        for n, fm, _ in facts:
            if is_relevant(fm, stacks) and not (store / f"{n}.md").exists():
                c = est_tokens(_pointer_line(n, fm))
                if _would_net_grow(running_idx, c, allow_net_grow, budget=INDEX_CEILING_TOKENS):   # SAME predicate
                    held_pre.append((n, c))                            # as the pull loop (Gate-2); under
                # --allow-net-grow nothing is held, so held_pre empties → the evict refuses ("nothing held")
                # rather than a gratuitous delete-then-pull-all.
        if not held_pre:
            print(f"evict: nothing is held (no past-the-ceiling MISSING globals) — evicting '{evict}' would free "
                  "room for NOTHING. There is no swap to make.", file=sys.stderr); return 1
        freed = est_tokens(_pointer_line(evict, _frontmatter(ep.read_text(encoding="utf-8", errors="replace"))))
        if not _evict_frees_enough(running_idx, freed, [c for _, c in held_pre], budget=INDEX_CEILING_TOKENS):
            print(f"evict: '{evict}' frees only ~{freed} tok — not enough to fit the smallest held global "
                  f"(~{min(c for _, c in held_pre)} tok at idx {running_idx}/{INDEX_CEILING_TOKENS} ceiling). "
                  "Pick a larger-pointer fact.", file=sys.stderr); return 1
        ep.unlink()
        _remove_index_pointer(store, evict)
        running_idx -= freed
        print(f"  ✓ evicted '{evict}' (~{freed} tok freed) → pulling held globals into the freed room", file=sys.stderr)
    for name, fm, text in facts:
        rel = is_relevant(fm, stacks)
        path = store / f"{name}.md"
        present = path.exists()
        cur = path.read_text(encoding="utf-8") if present else ""
        is_mirror = present and _is_mirror(cur)
        want = _as_mirror(text, name)
        if not rel:
            status = "irrelevant"
        elif not present:
            status = "MISSING"
        elif not is_mirror:
            status = "present(local)"  # project-authored — never clobber
        elif cur == want:
            status = "in-sync"
        else:
            status = "STALE-mirror"  # canonical changed → must refresh
        g, col = glyphs.get(status, ("·", "dim"))
        rows.append(f"    {_ui.c(g, col)} {_ui.lbl(f'{status:<14}')}{name}  " + _ui.c(f"({fm.get('scope', '?')})", "dim"))
        if rel:
            relevant += 1
        # M1: would PULLING this MISSING fact (a NEW index pointer) push the index past the HARD CEILING?
        # Cost it from the pointer line itself (the only honest per-pull figure). `held_this` gates BOTH the
        # write-skip and the provenance record (a held fact is NOT held by this project).
        cost = est_tokens(_pointer_line(name, fm)) if status == "MISSING" else 0
        held_this = (pull and rel and status == "MISSING"
                     and _would_net_grow(running_idx, cost, allow_net_grow, budget=INDEX_CEILING_TOKENS))
        if held_this:
            held += 1  # past-the-ceiling net-grow → hold (shrink to receive, or --allow-net-grow) — v0.1.66
            held_facts.append((name, cost))
        elif pull and rel and status in ("MISSING", "STALE-mirror"):
            # C3: a canonical missing a valid originSessionId fans its gap out to every
            # mirror this replication creates. WARN (don't block — the fact is still
            # useful); reuses the in-hand `fm`, no extra I/O.
            if not _valid_uuid(fm.get("originSessionId", "")):
                print(f"  ⚠ canonical {name} lacks a valid originSessionId — the gap fans out to every mirror",
                      file=sys.stderr)
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
                running_idx += cost          # the index just grew by this pointer — track it for the next guard
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
    tail = (f"pulled {pulled} new · refreshed {refreshed} stale{held_note}{fat_note} (index updated)" if pull
            else "run with --pull to replicate MISSING + refresh STALE mirrors here")
    add(_ui.kv("RESULT", tail))
    # v0.1.41: the EVICT-TO-RECEIVE offer (the report half of report-then-apply). When globals are HELD, surface
    # the held + the evictable local pointers with RAW, UNORDERED metadata (scope · mirror? · pointer-cost) —
    # NEVER ranked. A staleness/mtime rank actively misleads (a foundational fact is untouched yet vital), so the
    # agent judges which to evict; --evict then applies it orphan-safe + fit-checked. A safe scalpel, not auto-eviction.
    if held and store.is_dir():
        add("")
        add("  " + _ui.c("EVICT-TO-RECEIVE", "bold") + _ui.c(f"   · {held} held — free ONE low-value pointer to land a held global (net-neutral)", "dim"))
        add("    held: " + _ui.c(", ".join(f"{n} (~{c}t)" for n, c in held_facts), "yellow"))
        add("    " + _ui.c("evictable local pointers (raw metadata, UNORDERED — YOU judge value, never auto-ranked):", "dim"))
        for f in sorted(store.glob("*.md")):
            if f.name == "MEMORY.md":
                continue
            try:                                  # Gate-2: match the no-raise convention of every store scan
                t = f.read_text(encoding="utf-8", errors="replace")   # (a concurrent gc/chmod between glob+read
            except OSError:                       # must not abort the whole --pull after RESULT is built)
                continue
            ffm = _frontmatter(t)
            add("      " + _ui.c(f"· {f.stem:<40} {ffm.get('scope', '?'):<14} "
                                 f"{'mirror' if _is_mirror(t) else 'authored':<9} ~{est_tokens(_pointer_line(f.stem, ffm))}t", "dim"))
        add("    " + _ui.c("→ sync_global.py --pull --evict=<fact> .   (refuses an orphaning OR too-small evict; never auto-deletes)", "dim"))
    print(_ui.ascii_translate("\n".join(out)))
    return 0


def _record_provenance(name: str, project: str) -> None:
    """Add `project` to the canonical fact's `projects:` list — the synapse record.

    As a fact propagates to more projects, its provenance grows; that list IS the
    cross-project network's edge set (which minds hold which memory)."""
    p = GLOBAL / f"{name}.md"
    if not p.exists():
        return
    # `project` is a directory basename written into a SHARED canonical's frontmatter.
    # Sanitize it to the safe charset before it ever lands there, so it can't smuggle
    # YAML/markdown into the shared store (and can't carry a regex backreference below).
    project = _sanitize_token(project)
    text = p.read_text(encoding="utf-8")
    m = re.search(r"^(\s*projects:\s*)\[([^\]]*)\]\s*$", text, re.M)
    if m:
        items = [x.strip() for x in m.group(2).split(",") if x.strip()]
        if project in items:
            return
        items.append(project)
        p.write_text(text[: m.start()] + f"{m.group(1)}[{', '.join(items)}]" + text[m.end():])
    else:  # no projects line yet — add one after scope/node_type. Use a replacement
        # FUNCTION (not an f-string template) so `project` is never scanned for `\1`-style
        # backreferences by re.sub.
        new = re.sub(r"(\n\s*(?:scope|node_type):.*\n)",
                     lambda mm: f"{mm.group(1)}  projects: [{project}]\n", text, count=1)
        p.write_text(new)


def _holders(fm: dict) -> list[str]:
    # `*` not `+` so a single-character project name is not silently dropped.
    return re.findall(r"[A-Za-z0-9][A-Za-z0-9_.-]*", fm.get("projects", ""))


def network() -> int:
    """Render the cross-project memory network — the 'shared consciousness' graph.

    Distinguishes the UNIVERSAL baseline (`user-global` facts every mind holds — a
    complete graph by definition, so uninformative as edges) from DIFFERENTIAL edges
    (`stack-general` facts that bind only the subset of projects whose stacks match).
    The differential edges are the meaningful topology; universal facts are a shared
    substrate listed separately, not drawn as trivial all-to-all edges.
    """
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
    out.append("  " + _ui.c(", ".join(minds) or "(no projects yet)", "dim"))
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
    if not idx.exists():
        return False
    lines = idx.read_text(encoding="utf-8").splitlines()
    kept = [ln for ln in lines if f"]({name}.md)" not in ln]  # match the link target, not a spoofable substring
    if len(kept) == len(lines):
        return False
    idx.write_text("\n".join(kept).rstrip() + "\n", encoding="utf-8")
    return True


def _orphans(store: Path) -> list[str]:
    """Mirror files (`global_ref:`) in this store whose CANONICAL no longer exists in
    the global store. These are the dead memory --pull can never reclaim (it only
    iterates LIVE globals), so they accrue forever — the leak Fix B closes."""
    canon = {n for n, _, _ in global_facts()}
    out: list[str] = []
    if not store.exists():
        return out
    for f in store.glob("*.md"):
        if f.name == "MEMORY.md":
            continue
        text = f.read_text(encoding="utf-8", errors="replace")
        if _is_mirror(text) and f.stem not in canon:  # ONLY managed mirrors (frontmatter key)
            out.append(f.stem)
    return out


def gc(project_dir: Path, apply: bool) -> int:
    """Reclaim orphaned mirrors. Report-by-default; delete only with --apply, and
    NEVER touch a project-authored (non-`global_ref:`) fact, even on a name collision.

    Dead-edge provenance (a canonical that still exists but lists a project no longer
    holding it) is REPORTED only, not auto-pruned: absence-of-mirror is a weak signal
    (a renamed/moved store also 'holds nothing'), and stripping global state on it
    risks erasing real edges. The proven win is removing the orphan files."""
    project_dir = project_dir.resolve()
    # SAFETY: an EMPTY canonical set makes EVERY mirror look orphaned → gc --apply would
    # delete them all. A global store that is absent OR present-but-empty (unmounted,
    # moved, not yet synced, or only the MEMORY.md index left) is NOT the same as "all
    # canonicals were deliberately deleted". Refuse in either case rather than risk wiping
    # re-pullable / last-surviving memory. (Guard on the FACT COUNT, not mere existence.)
    if not GLOBAL.exists() or not global_facts():
        why = "absent" if not GLOBAL.exists() else "present but empty (no canonical facts)"
        print(f"global store {GLOBAL} is {why} — refusing to GC "
              "(cannot distinguish that from all-canonicals-deleted).")
        return 0
    store = project_store(project_dir)
    orphans = _orphans(store)
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
    tail = (f"removed {removed} orphan(s)" if apply
            else "run with --apply to delete (surface these to the user first)")
    out.append("")
    out.append(_ui.kv("RESULT", tail))
    # Dead-edge provenance, report-only (conservative — see docstring).
    if apply:
        print(_ui.ascii_translate("\n".join(out)))
        return 0
    dead = []
    for name, fm, _ in global_facts():
        for holder in _holders(fm):
            # we only know THIS project's store path; report if it's listed but absent
            if holder == project_dir.name and not (store / f"{name}.md").exists():
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
    r"""The fact BODY — markdown AFTER the leading frontmatter block. Strips ONLY the first `^---\n…\n---\n`
    span (non-greedy, once) — NOT split('---'), since a body legitimately contains `---`/`***` horizontal
    rules. Trailing whitespace (per line + overall) is normalized so the M2 compare ignores cosmetic drift."""
    if text.startswith("﻿"):       # strip a leading BOM (some editors add one) so the \A--- anchor holds
        text = text[1:]
    text = text.replace("\r\n", "\n").replace("\r", "\n")   # CRLF/CR (a model→file artifact) — match _frontmatter
    body = re.sub(r"\A---\n.*?\n---\n", "", text, count=1, flags=re.DOTALL)
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
    interrupted process can still leave a partial state — but a completed call never does.)

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
    if local_fact in _RESERVED_STEMS or canon_name in _RESERVED_STEMS:
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
    if not reconcile:
        canon_path.write_text(local_text, encoding="utf-8")
    _record_provenance(canon_name, project_dir.name)
    canon_text = canon_path.read_text(encoding="utf-8", errors="replace")  # re-read POST-provenance
    fm = _frontmatter(canon_text)

    # Convert the origin's copy into a managed mirror of the POST-provenance canonical, so a later
    # --pull reports `in-sync` (not a spurious STALE-mirror refresh) and never re-creates a shadow.
    dest.write_text(_as_mirror(canon_text, canon_name), encoding="utf-8")
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
    idx_text = idx.read_text(encoding="utf-8", errors="replace") if idx.exists() else ""
    facts = [f for f in store.glob("*.md") if f.name != "MEMORY.md"]
    bodies = {f.stem: f.read_text(encoding="utf-8", errors="replace") for f in facts}
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
        "facts": len(facts),
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
        has_mirror = any(
            _is_mirror(f.read_text(encoding="utf-8", errors="replace"))
            for f in store.glob("*.md") if f.name != "MEMORY.md"
        )
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


# ── v0.1.67 (Phase C): fleet utility — the gc lever's missing evidence ───────────────────────────
def fleet_utility(project_dir: Path) -> dict:
    """READ-ONLY: per-canonical usage evidence aggregated across every node's cycle log (usage_history —
    the same reader the demotion rank uses), joined with a MIRROR CHECK before attribution: a node's
    reads for stem X count toward canonical X only if the node's `X.md` is a managed mirror — a
    same-stem, never-pulled LOCAL fact (the `present(local)` shadow case run() already recognizes) is
    tallied as `shadow_reads`, never attributed (a spec-gate finding: stem equality alone lies).
    Per-canonical `windows` counts only the probative windows each holding MIRROR existed through
    (window start ≥ mirror mtime — the demotion rank's fact-age rule, applied fleet-side; an inline
    adversarial review found the unconditional windows_full credit overstated zero-read evidence on
    freshly-pulled mirrors). `fleet_tax = pointer_tok × len(holders)` — ZERO for an unheld canonical (nobody pays it; its
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
    nodes_reporting = 0
    per: dict = {n: {"reads": 0, "windows": 0, "last": "", "_ep": None, "shadow": 0} for n in canon}
    for store in stores:
        hist = usage_history(store)
        if hist["windows_full"] >= 1:
            nodes_reporting += 1
        for stem in canon:
            row = hist["per_fact"].get(stem)
            reads = row.get("reads", 0) if isinstance(row, dict) else 0
            reads = reads if isinstance(reads, int) and not isinstance(reads, bool) and reads > 0 else 0
            p = store / f"{stem}.md"
            if not p.exists():
                continue
            try:
                text = p.read_text(encoding="utf-8", errors="replace")
                mt = p.stat().st_mtime
            except OSError:
                continue
            if not _is_mirror(text):
                if reads:
                    per[stem]["shadow"] += reads       # same-stem local — reported, never attributed
                continue
            # Count only the probative windows the MIRROR existed through (window start ≥ mirror mtime) —
            # crediting a node's whole window history to a freshly-pulled mirror would overstate its
            # zero-read evidence ("0 reads/10w" on a one-day-old mirror), the same per-fact fact-age rule
            # demotion_candidates applies locally (found by the inline adversarial review, 2026-07-05).
            # A refresh resets mtime → undercounts, the safe direction under the pinned bias.
            per[stem]["windows"] += sum(1 for s in hist["window_starts"]
                                        if isinstance(s, (int, float)) and s >= mt)
            per[stem]["reads"] += reads
            ts = str((row or {}).get("last", "") or "") if isinstance(row, dict) else ""
            dt = _parse_ts(ts)
            if dt is not None and (per[stem]["_ep"] is None or dt.timestamp() > per[stem]["_ep"]):
                per[stem]["_ep"], per[stem]["last"] = dt.timestamp(), ts
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
        if not holders:
            unheld.append(stem)
        entries.append(e)
    entries.sort(key=lambda e: (-e["fleet_tax"], e["name"]))
    return {"nodes": len(stores), "nodes_reporting": nodes_reporting, "canonicals": entries,
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
                            "provenance UPPER bound (dead edges reported by --gc, never auto-pruned)", "dim"))
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
                                     "MIRROR existed through (mtime-gated; a refresh resets the clock)", "dim")))
    for e in u["canonicals"]:
        if e["windows"] and not e["reads"]:
            ev = _ui.c(f"0 reads/{e['windows']}w — unread where instrumented", "yellow")
        elif e["reads"]:
            ev = _ui.c(f"{e['reads']} read(s)/{e['windows']}w · last {str(e['last'])[:16]}", "green")
        else:
            ev = _ui.c("uninstrumented (0 probative windows on holders)", "dim")
        shadow = _ui.c(f" · shadow {e['shadow_reads']}", "yellow") if e.get("shadow_reads") else ""
        out.append(f"    {_ui.lbl(e['name'][:40], 40)} {e['fleet_tax']:>5}t "
                   + _ui.c(f"({e['pointer_tok']}t × {e['holders']})", "dim") + f"  {ev}{shadow}")
    if u["unheld"]:
        out.append("    " + _ui.c(f"unheld (0 fleet tax — nobody pays them yet): {', '.join(u['unheld'])}", "dim"))
    out.append("")
    out.append(_ui.kv("NEXT", _ui.c("a 0-reads/instrumented canonical is gc-lever EVIDENCE — judge its "
                                    "CONTENT before any demote (holders/adoption ≠ fit); never auto-gc", "dim")))
    print(_ui.ascii_translate("\n".join(out)))
    return 0


# The dream-flow modes that carry a cross-project BEAT: --list/--pull (Phase 1) and --gc/--tokens/
# --utility (Phase 5; --utility is the gc lever's evidence view, v0.1.67). --promote runs in Phase 4's
# APPLY — the one phase whose contract deliberately excludes dream beats (only the plain proposal + the
# single SURFACING line) — and --network is a maintainer utility outside dream flow, so neither cues.
_CUED_MODES = ("--list", "--pull", "--gc", "--tokens", "--utility")


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
    if args and args[0] == "--tokens":
        return token_report(project_dir, "--json" in args)
    if args and args[0] == "--utility":   # v0.1.67 (Phase C): fleet usage evidence (READ-ONLY, like --list)
        return utility_report(project_dir, "--json" in args)
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
              "| --promote PROJECT_DIR LOCAL_FACT [CANON_NAME] | --tokens [--json] PROJECT_DIR "
              "| --utility [--json] PROJECT_DIR | --network", file=sys.stderr)
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
