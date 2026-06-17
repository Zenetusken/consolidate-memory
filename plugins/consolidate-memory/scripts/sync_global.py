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
from memory_status import _sane, est_tokens, slug_for, _frontmatter, _valid_uuid

GLOBAL = Path.home() / ".claude" / "memory"
_STACK_KEYWORDS = {
    "python": ["python", "pyproject", "ruff", "pytest"],
    "mypy": ["mypy", "py.typed", "stubs"],
    "rag": ["rag", "embedding", "lancedb", "faiss", "vector", "retriev", "mxbai", "rerank"],
    "gpu": ["cuda", "vllm", "vram", "gpu", "torch"],
    "playwright": ["playwright", "scraper", "browser"],
    "claude-code": [".claude", "skill", "agents.md"],
}


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
        print(f"  [{status:>14}] {name}  ({fm.get('scope', '?')})")
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
    print("=" * 72)
    print("NEURAL NETWORK — token consumption across all nodes")
    print("=" * 72)
    print(f"basis    : {net['basis']}")
    print(f"node def : {net['node_def']}")
    print(f"nodes    : {t['nodes']}  ·  triggering node: {net['trigger']}")
    print(f"TOTAL    : ≈{t['always_loaded_tokens']} always-loaded tok (paid every "
          f"session, every node) · ≈{t['recall_tokens']} recall-pool tok")
    mir = t.get("mirror_index_tokens", 0)
    if mir:
        pct = round(100 * mir / t["always_loaded_tokens"]) if t["always_loaded_tokens"] else 0
        print(f"           of the always-loaded tax, ≈{mir} tok ({pct}%) is mirror-driven "
              "— the lever is the GLOBAL store (demote/GC), NOT local prune")
    print()
    for n in sorted(net["nodes"], key=lambda d: -d["always_loaded_tokens"]):
        mark = " ← trigger (dream ran here)" if n["trigger"] else ""
        print(f"  {n['node'][:28]:<28} always ≈{n['always_loaded_tokens']:>5} "
              f"(≈{n.get('mirror_index_tokens', 0)} mirror) · "
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
