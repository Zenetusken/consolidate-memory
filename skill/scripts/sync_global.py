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

# est_tokens lives in memory_status (the measurement script); reuse it rather than
# re-deriving the heuristic. The sibling resolves because a script's own directory is
# on sys.path[0] at runtime, and stays a sibling through the skill/ symlink.
from memory_status import est_tokens

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


def _kw_hit(blob: str, kw: str) -> bool:
    """True if `kw` appears in `blob` as a whole token, not a substring (Fix D).

    Plain substring matching made loose keywords over-trigger: `skill` matched
    `reskilling`, so stack-general facts spread far wider than their stack. We bound
    matches with non-alphanumeric edges (so dotted keywords like `.claude` / `py.typed`
    still work, where `\\b` would misbehave around the dot)."""
    return re.search(rf"(?<![a-z0-9]){re.escape(kw)}(?![a-z0-9])", blob) is not None


def detect_stacks(project_dir: Path) -> set[str]:
    blob = ""
    for name in ("pyproject.toml", "CLAUDE.md", "README.md"):
        p = project_dir / name
        if p.exists():
            blob += p.read_text(encoding="utf-8", errors="replace").lower()
    found = {s for s, kws in _STACK_KEYWORDS.items() if any(_kw_hit(blob, k) for k in kws)}
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


def _pointer_line(name: str, fm: dict) -> str:
    """The canonical index pointer line for a fact (pure — testable). The `description`
    is the recall hook, truncated; the scope tag mirrors the index's existing style."""
    desc = fm.get("description", "").strip().strip('"')
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
    for i, ln in enumerate(lines):
        if f"({name}.md)" in ln:
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


# ── garbage collection: orphaned mirrors (Fix B) ───────────────────────────────
def _remove_index_pointer(store: Path, name: str) -> bool:
    """Drop the pointer line for `name` from the project index. Returns True if removed."""
    idx = store / "MEMORY.md"
    if not idx.exists():
        return False
    lines = idx.read_text(encoding="utf-8").splitlines()
    kept = [ln for ln in lines if f"({name}.md)" not in ln]
    if len(kept) == len(lines):
        return False
    idx.write_text("\n".join(kept).rstrip() + "\n", encoding="utf-8")
    return True


def _orphans(store: Path) -> list[str]:
    """Mirror files (`global_ref:`) in this store whose CANONICAL no longer exists in
    the global store. These are the dead memory --pull can never reclaim (it only
    iterates LIVE globals), so they accrue forever — the leak Fix B closes."""
    canon = {n for n, _, _ in global_facts()}
    out = []
    if not store.exists():
        return out
    for f in store.glob("*.md"):
        if f.name == "MEMORY.md":
            continue
        text = f.read_text(encoding="utf-8", errors="replace")
        if "global_ref:" in text and f.stem not in canon:  # ONLY managed mirrors
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
    store = project_store(project_dir)
    orphans = _orphans(store)
    print(f"project : {project_dir.name}  (slug {slug_for(project_dir)})")
    print(f"store   : {store}  ({'exists' if store.exists() else 'MISSING'})")
    print(f"orphans : {len(orphans)} mirror(s) whose canonical is gone\n")
    removed = 0
    for name in orphans:
        if apply:
            (store / f"{name}.md").unlink(missing_ok=True)
            _remove_index_pointer(store, name)
            removed += 1
            print(f"  [removed] {name}  (file + index pointer)")
        else:
            print(f"  [orphan ] {name}  (would remove file + index pointer)")
    tail = (f"removed {removed} orphan(s)" if apply
            else "run with --apply to delete (surface these to the user first)")
    print(f"\n{tail}")
    # Dead-edge provenance, report-only (conservative — see docstring).
    if apply:
        return 0
    dead = []
    for name, fm, _ in global_facts():
        for holder in _holders(fm):
            # we only know THIS project's store path; report if it's listed but absent
            if holder == project_dir.name and not (store / f"{name}.md").exists():
                dead.append(name)
    if dead:
        print("\ndead provenance edges (canonical lists this project, but no mirror here):")
        for n in dead:
            print(f"  • {n}  (report only — not auto-pruned)")
    return 0


# ── token observability: per-node cost across the neural network ────────────────
def _label_from_slug(slug: str) -> str:
    """Human label for a node from its slug dir. The slug is the abs path with '/'→'-',
    NOT losslessly invertible to a basename (can't tell which '-' were '/'), so we do
    NOT guess a basename — `rsplit('-',1)[-1]` would mislabel any hyphenated project
    (…-consolidate-memory → 'memory'). De-prefix the leading '-' and keep the
    informative tail; unambiguous beats pretty for per-node attribution."""
    s = slug.lstrip("-")
    return s if len(s) <= 24 else "…" + s[-23:]


def _node_label(store: Path) -> str:
    return _label_from_slug(store.parent.name)


def _node_tokens(store: Path) -> dict:
    """ESTIMATED token cost of one node's auto-memory: the always-loaded index plus the
    recall-fact pool. Tokens are ≈ chars/4 (est_tokens) — an estimate, not exact."""
    idx = store / "MEMORY.md"
    idx_text = idx.read_text(encoding="utf-8", errors="replace") if idx.exists() else ""
    facts = [f for f in store.glob("*.md") if f.name != "MEMORY.md"]
    bodies = [f.read_text(encoding="utf-8", errors="replace") for f in facts]
    shared = sum(1 for b in bodies if "global_ref:" in b)
    return {
        "always_loaded_tokens": est_tokens(idx_text),
        "recall_tokens": sum(est_tokens(b) for b in bodies),
        "facts": len(facts),
        "shared": shared,
    }


def _network_nodes() -> list[Path]:
    """Network nodes = project memory stores holding ≥1 shared (`global_ref:`) mirror.

    This is the PHYSICAL, measurable node set (we have each store's path, so we can
    weigh its tokens). It deliberately differs from network()'s LOGICAL `minds` set
    (derived from provenance basenames, which can't be inverted to a store path) — the
    two views can diverge (names vs slugs); --network = topology, --tokens = cost."""
    base = Path.home() / ".claude" / "projects"
    nodes = []
    if not base.exists():
        return nodes
    for proj in sorted(base.iterdir()):
        store = proj / "memory"
        if not store.is_dir():
            continue
        has_mirror = any(
            "global_ref:" in f.read_text(encoding="utf-8", errors="replace")
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
    al_total = rc_total = 0
    for store in _network_nodes():
        m = _node_tokens(store)
        is_trigger = store.resolve() == trigger_store.resolve()
        nodes.append({
            "node": project_dir.name if is_trigger else _node_label(store),
            "trigger": is_trigger,
            **m,
        })
        al_total += m["always_loaded_tokens"]
        rc_total += m["recall_tokens"]
    return {
        "basis": "≈ chars/4 (heuristic estimate, not a tokenizer)",
        "node_def": "project stores holding ≥1 shared fact",
        "trigger": project_dir.name,
        "nodes": nodes,
        "totals": {"nodes": len(nodes),
                   "always_loaded_tokens": al_total, "recall_tokens": rc_total},
    }


def token_report(project_dir: Path, as_json: bool) -> int:
    import json
    net = token_network(project_dir)
    if as_json:
        print(json.dumps(net, indent=2))
        return 0
    t = net["totals"]
    print("=" * 72)
    print("NEURAL NETWORK — token consumption across all nodes")
    print("=" * 72)
    print(f"basis    : {net['basis']}")
    print(f"node def : {net['node_def']}")
    print(f"nodes    : {t['nodes']}  ·  triggering node: {net['trigger']}")
    print(f"TOTAL    : ≈{t['always_loaded_tokens']} always-loaded tok (paid every "
          f"session, every node) · ≈{t['recall_tokens']} recall-pool tok\n")
    for n in sorted(net["nodes"], key=lambda d: -d["always_loaded_tokens"]):
        mark = " ← trigger (dream ran here)" if n["trigger"] else ""
        print(f"  {n['node'][:28]:<28} always ≈{n['always_loaded_tokens']:>5} · "
              f"recall ≈{n['recall_tokens']:>6} · {n['facts']:>2} facts "
              f"({n['shared']} shared){mark}")
    if not net["nodes"]:
        print("  (no nodes hold shared facts yet — run --pull somewhere first)")
    return 0


def main() -> int:
    args = sys.argv[1:]
    if args and args[0] == "--network":
        return network()
    if args and args[0] == "--tokens":
        as_json = "--json" in args
        rest = [a for a in args[1:] if a != "--json"]
        return token_report(Path(rest[0]) if rest else Path.cwd(), as_json)
    if args and args[0] == "--gc":
        apply = "--apply" in args
        rest = [a for a in args[1:] if a != "--apply"]
        return gc(Path(rest[0]) if rest else Path.cwd(), apply)
    if not args or args[0] not in ("--list", "--pull"):
        print("usage: sync_global.py --list|--pull PROJECT_DIR | --gc [--apply] PROJECT_DIR "
              "| --tokens [--json] PROJECT_DIR | --network", file=sys.stderr)
        return 2
    pull = args[0] == "--pull"
    project_dir = Path(args[1]) if len(args) > 1 else Path.cwd()
    return run(project_dir, pull)


if __name__ == "__main__":
    raise SystemExit(main())
