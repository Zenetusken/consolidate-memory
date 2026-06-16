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
stacks are inferred from pyproject.toml + CLAUDE.md keywords.

The consolidate-memory skill calls --pull in Phase 1 (bring global facts down) and
writes new global-scope facts up to the global store in Phase 4.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

GLOBAL = Path.home() / ".claude" / "memory"
_STACK_KEYWORDS = {
    "python": ["python", "pyproject", "ruff", "pytest"],
    "mypy": ["mypy", "py.typed", "stubs"],
    "rag": ["rag", "embedding", "lancedb", "faiss", "vector", "retriev", "mxbai", "rerank"],
    "gpu": ["cuda", "vllm", "vram", "gpu", "torch"],
    "playwright": ["playwright", "scraper", "browser"],
    "claude-code": [".claude", "skill", "agents.md"],
}


def slug_for(project_dir: Path) -> str:
    return str(project_dir.resolve()).replace("/", "-")


def project_store(project_dir: Path) -> Path:
    return Path.home() / ".claude" / "projects" / slug_for(project_dir) / "memory"


def _frontmatter(text: str) -> dict:
    out: dict = {}
    m = re.search(r"^---\n(.*?)\n---", text, re.S)
    if not m:
        return out
    for line in m.group(1).splitlines():
        if ":" in line and not line.startswith(" "):
            k, _, v = line.partition(":")
            out[k.strip()] = v.strip()
        else:
            m2 = re.match(r"\s+(scope|stacks|type|projects):\s*(.+)", line)
            if m2:
                out[m2.group(1)] = m2.group(2).strip()
    return out


def detect_stacks(project_dir: Path) -> set[str]:
    blob = ""
    for name in ("pyproject.toml", "CLAUDE.md", "README.md"):
        p = project_dir / name
        if p.exists():
            blob += p.read_text(encoding="utf-8", errors="replace").lower()
    found = {s for s, kws in _STACK_KEYWORDS.items() if any(k in blob for k in kws)}
    return found


def global_facts() -> list[tuple[str, dict, str]]:
    facts = []
    if not GLOBAL.exists():
        return facts
    for f in sorted(GLOBAL.glob("*.md")):
        if f.name == "MEMORY.md":
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
    robustly — drop any existing global_ref, then insert one after `metadata:`."""
    lines = [ln for ln in text.splitlines() if not ln.strip().startswith("global_ref:")]
    out: list[str] = []
    injected = False
    for ln in lines:
        out.append(ln)
        if not injected and ln.strip().rstrip(":") == "metadata":
            out.append(f"  global_ref: {name}")
            injected = True
    if not injected:  # no metadata block — stamp just inside the frontmatter
        for i, ln in enumerate(out):
            if ln.strip() == "---":
                out.insert(i + 1, f"# global_ref: {name}")
                break
    return "\n".join(out) + "\n"


def _ensure_index_pointer(store: Path, name: str, fm: dict) -> bool:
    """Add a pointer line to the project's MEMORY.md index if absent. The script
    owns this so a replicated fact is never left half-installed (file but no pointer)."""
    idx = store / "MEMORY.md"
    content = idx.read_text(encoding="utf-8") if idx.exists() else "# Memory Index\n\n"
    if f"({name}.md)" in content:
        return False
    desc = fm.get("description", "").strip().strip('"')
    hook = (desc[:88] + "…") if len(desc) > 88 else desc
    scope = fm.get("scope", "")
    line = f"- [{name}]({name}.md) — {hook}" + (f" [{scope}]" if scope else "")
    idx.write_text(content.rstrip() + "\n" + line + "\n", encoding="utf-8")
    return True


def run(project_dir: Path, pull: bool) -> int:
    project_dir = project_dir.resolve()
    store = project_store(project_dir)
    stacks = detect_stacks(project_dir)
    facts = global_facts()
    print(f"project   : {project_dir.name}  (slug {slug_for(project_dir)})")
    print(f"stacks    : {sorted(stacks) or '(none detected)'}")
    print(f"store      : {store}  ({'exists' if store.exists() else 'MISSING — created on pull'})")
    print(f"global facts: {len(facts)}\n")
    relevant = pulled = refreshed = 0
    for name, fm, text in facts:
        rel = is_relevant(fm, stacks)
        path = store / f"{name}.md"
        present = path.exists()
        cur = path.read_text(encoding="utf-8") if present else ""
        is_mirror = present and "global_ref:" in cur
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
        print(f"  [{status:>14}] {name}  ({fm.get('scope', '?')})")
        if rel:
            relevant += 1
        if pull and rel and status in ("MISSING", "STALE-mirror"):
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
    tail = (f"pulled {pulled} new, refreshed {refreshed} stale (index updated)" if pull
            else "run with --pull to replicate MISSING + refresh STALE mirrors here")
    print(f"\nrelevant: {relevant} · {tail}")
    return 0


def _record_provenance(name: str, project: str) -> None:
    """Add `project` to the canonical fact's `projects:` list — the synapse record.

    As a fact propagates to more projects, its provenance grows; that list IS the
    cross-project network's edge set (which minds hold which memory)."""
    p = GLOBAL / f"{name}.md"
    if not p.exists():
        return
    text = p.read_text(encoding="utf-8")
    m = re.search(r"^(\s*projects:\s*)\[([^\]]*)\]\s*$", text, re.M)
    if m:
        items = [x.strip() for x in m.group(2).split(",") if x.strip()]
        if project in items:
            return
        items.append(project)
        p.write_text(text[: m.start()] + f"{m.group(1)}[{', '.join(items)}]" + text[m.end():])
    else:  # no projects line yet — add one after scope/node_type
        new = re.sub(r"(\n\s*(?:scope|node_type):.*\n)", rf"\1  projects: [{project}]\n", text, count=1)
        p.write_text(new)


def _holders(fm: dict) -> list[str]:
    return re.findall(r"[A-Za-z0-9][A-Za-z0-9_.-]+", fm.get("projects", ""))


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

    print("=" * 72)
    print("SHARED CONSCIOUSNESS — cross-project memory network")
    print("=" * 72)
    print(f"minds (projects) : {len(minds)}  —  {', '.join(minds) or '(none)'}")
    print(f"shared memories  : {len(facts)}  "
          f"({len(universal)} universal · {len(differential)} differential"
          + (f" · {len(other)} other" if other else "") + ")\n")

    # Universal substrate — held by every mind (a complete graph; listed, not drawn)
    print("  universal baseline (user-global — every mind holds these):")
    if universal:
        for n, fm in universal:
            held = len(_holders(fm))
            flag = "" if held == len(minds) else f"  (only {held}/{len(minds)} so far)"
            print(f"    • {n}{flag}")
    else:
        print("    (none)")

    # Differential edges — the meaningful topology (stack-general bindings)
    print("\n  differential edges (stack-general — the bindings that carry signal):")
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
        print("    (none yet — all current memory is universal; differential edges form")
        print("     when stack-general facts spread to a SUBSET of same-stack projects)")
    for a, b, w in sorted(edges, key=lambda e: -e[2]):
        print(f"    {a[:24]:>24} ●{'━' * min(w, 20)}● {b[:24]:<24} ({w} shared)")
    return 0


def main() -> int:
    args = sys.argv[1:]
    if args and args[0] == "--network":
        return network()
    if not args or args[0] not in ("--list", "--pull"):
        print("usage: sync_global.py --list|--pull PROJECT_DIR  |  --network", file=sys.stderr)
        return 2
    pull = args[0] == "--pull"
    project_dir = Path(args[1]) if len(args) > 1 else Path.cwd()
    return run(project_dir, pull)


if __name__ == "__main__":
    raise SystemExit(main())
