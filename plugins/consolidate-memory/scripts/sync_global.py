#!/usr/bin/env python3
"""Cross-project memory: replicate relevant GLOBAL facts into a project's store.

Claude Code recall is slug-scoped (a project only auto-recalls its OWN
~/.claude/projects/<slug>/memory/). So cross-project facts can't just live in a
global store and be expected to surface elsewhere — they must be REPLICATED into
each project's store. This is the engine for that:

  --list PROJECT_DIR   show which global facts are relevant + present/missing (read-only)
  --pull PROJECT_DIR   copy missing relevant global facts into the project's store
                       (additive; marks copies with `global_ref:` so they re-sync)

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
from memory_status import _sane, est_tokens, slug_for, _frontmatter, _valid_uuid

GLOBAL = Path.home() / ".claude" / "memory"
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
}
_STACK_IMPORTS = {   # top-level MODULE names (as imported) → stack
    "rag": {"lancedb", "faiss", "sentence_transformers", "chromadb"},
    "gpu": {"torch", "torchvision", "open_clip", "vllm"},
    "playwright": {"playwright"},
}
_PYPROJECT_CAP = 65536   # bytes read from pyproject (config is small; bound the read)
_PY_SCAN_CAP = 400       # max *.py files scanned for imports (bound cost on large repos)


_SAFE_NAME = r"[A-Za-z0-9._-]+"  # the documented kebab/snake charset for fact + project names


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


def _is_mirror(text: str) -> bool:
    """True iff a fact is a MANAGED MIRROR — detected by the EXACT structured forms
    `_as_mirror` writes inside the frontmatter, NEVER a substring anywhere in the file:

      • a column-0 `# global_ref: <name>` comment stamp that is the FIRST frontmatter
        line (exactly where `_as_mirror` inserts it in the no-metadata-block case — a
        `# global_ref:` comment *elsewhere* in a hand-authored note must not count), or
      • a `  global_ref: <name>` line that is a DIRECT (2-space) child of a top-level
        `metadata:` key (where `_as_mirror` injects it).

    Parses frontmatter STRUCTURE, not the raw block: a regex over the raw text matches
    `global_ref:` on an indented *folded-scalar continuation line* (e.g. under a
    `description: >-`), which would misclassify a project-authored note — and GC would
    then DELETE it. Bias is to False on anything ambiguous: a missed mirror merely isn't
    reclaimed (safe), whereas a false positive destroys user memory (unsafe)."""
    if text.startswith("﻿"):     # tolerate a leading BOM (consistent with _frontmatter), else
        text = text[1:]                # the ^--- anchor fails and a BOM mirror reads as un-managed
    m = re.search(r"^---\n(.*?)\n---", text, re.S)
    if not m:
        return False
    top = None       # the current top-level frontmatter key
    first = True      # the col-0 stamp only counts as the FIRST non-blank frontmatter line
    for ln in m.group(1).splitlines():
        if not ln.strip():
            continue
        if first and re.match(r"#\s*global_ref:\s*\S", ln):       # col-0 stamp (first line only)
            return True
        first = False
        if not ln[:1].isspace():                                  # a top-level line
            mk = re.match(r"([^:#\s][^:]*):", ln)
            top = mk.group(1).strip() if mk else None
            continue
        # indented line: accept ONLY as a direct (exactly-2-space) child of metadata
        if top == "metadata" and re.match(r" {2}global_ref:\s*\S", ln):
            return True
    return False


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


def is_relevant(fm: dict, stacks: set[str]) -> bool:
    scope = fm.get("scope", "")
    if scope == "user-global":
        return True
    if scope == "stack-general":
        fact_stacks = set(re.findall(r"[a-z0-9-]+", fm.get("stacks", "").lower()))
        return bool(fact_stacks & stacks)
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
    lines = [ln for ln in text.splitlines() if not ln.strip().startswith("global_ref:")]
    out: list[str] = []
    injected = False
    for ln in lines:
        out.append(ln)
        if not injected and not ln[:1].isspace() and ln.strip().rstrip(":") == "metadata":
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


def _ensure_index_pointer(store: Path, name: str, fm: dict) -> bool:
    """UPSERT the pointer line in the project's MEMORY.md index (Fix C).

    The script owns this so a replicated fact is never left half-installed (file but no
    pointer) — AND so the ALWAYS-LOADED index hook never drifts from the canonical. The
    old version early-returned when any line for `name` existed, so a STALE refresh that
    changed the fact's `description` updated the body but left the index hook stale. Now:
    insert if absent, REWRITE if present-but-different, no-op if already correct."""
    idx = store / "MEMORY.md"
    content = idx.read_text(encoding="utf-8") if idx.exists() else "# Memory Index\n\n"
    want = _pointer_line(name, fm)
    lines = content.splitlines()
    anchor = f"]({name}.md)"  # the LINK TARGET, not a bare substring a description could spoof
    for i, ln in enumerate(lines):
        if anchor in ln:
            if ln.strip() == want.strip():
                return False  # already correct — no-op
            lines[i] = want  # refresh a drifted hook
            idx.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
            return True
    idx.write_text(content.rstrip() + "\n" + want + "\n", encoding="utf-8")  # absent — append
    return True


def run(project_dir: Path, pull: bool) -> int:
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
    relevant = pulled = refreshed = 0
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
        if pull and rel and status in ("MISSING", "STALE-mirror"):
            # C3: a canonical missing a valid originSessionId fans its gap out to every
            # mirror this replication creates. WARN (don't block — the fact is still
            # useful); reuses the in-hand `fm`, no extra I/O.
            if not _valid_uuid(fm.get("originSessionId", "")):
                print(f"  ⚠ canonical {name} lacks a valid originSessionId — the gap fans out to every mirror",
                      file=sys.stderr)
            store.mkdir(parents=True, exist_ok=True)
            path.write_text(want, encoding="utf-8")
            _ensure_index_pointer(store, name, fm)
            if status == "MISSING":
                pulled += 1
            else:
                refreshed += 1
        # record provenance for ANY fact this project now holds as a mirror
        # (incl. already in-sync), so the network graph reflects reality
        if pull and rel and status in ("MISSING", "STALE-mirror", "in-sync"):
            _record_provenance(name, project_dir.name)  # this mind holds the fact
    add(_ui.kv("FACTS", f"{len(facts)} global · {relevant} relevant to this project"))
    out.extend(rows)
    add("")
    tail = (f"pulled {pulled} new · refreshed {refreshed} stale (index updated)" if pull
            else "run with --pull to replicate MISSING + refresh STALE mirrors here")
    add(_ui.kv("RESULT", tail))
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


# ── token observability: per-node cost across the neural network ────────────────
def _label_from_slug(slug: str) -> str:
    """Human label for a node from its slug dir. The slug is the abs path with '/'→'-',
    NOT losslessly invertible to a basename (can't tell which '-' were '/'), so we do
    NOT guess a basename — `rsplit('-',1)[-1]` would mislabel any hyphenated project
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


def main() -> int:
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
    if args and args[0] == "--gc":
        return gc(project_dir, "--apply" in args)
    if not args or args[0] not in ("--list", "--pull"):
        print("usage: sync_global.py --list|--pull PROJECT_DIR | --gc [--apply] PROJECT_DIR "
              "| --tokens [--json] PROJECT_DIR | --network", file=sys.stderr)
        return 2
    return run(project_dir, args[0] == "--pull")


if __name__ == "__main__":
    raise SystemExit(main())
