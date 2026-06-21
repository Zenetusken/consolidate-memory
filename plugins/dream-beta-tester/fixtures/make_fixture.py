#!/usr/bin/env python3
"""Generate the FROZEN gate fixture store for the dream beta-harness.

The continuous-QA gate must reliably exercise the families that catch the known regressions —
D3 (backfill offered under a no-net-grow gate) and D4 (an evict-stage that spares a
wikilink-reachable orphan). Both require a store that:
  * is OVER the always-loaded index budget (a dense MEMORY.md → the over-budget gate fires), and
  * holds UN-INDEXED facts (the backfill/triage set), one of which is reachable ONLY via a
    [[wikilink]] from an INDEXED fact (the orphan that must be R_referenced, never A_orphans).

A snapshot of a live store (e.g. Doc_Flo) would drift; this synthetic store is FROZEN and
regenerable, decoupled from any real project's memory. The skill derives the store from the
fixture REPO's slug, so we write to ~/.claude/projects/<slug>/memory and create the repo dir.

Usage:  python3 make_fixture.py [FIXTURE_REPO]   (default: <this dir>/gate-repo)
Idempotent: clears + rewrites the fixture store.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

N_INDEXED = 50          # dense pointers → comfortably over the 1200-tok index budget
N_UNINDEXED = 12        # the backfill/triage set
HOOK = ("a deliberately dense, information-rich pointer hook written to push the always-loaded "
        "index comfortably past the 1200-token budget so the over-budget remediation gate fires "
        "deterministically on every run, independent of any real project's memory — fact {i} of 50")


def slug_for(repo: Path) -> str:
    return re.sub(r"[/_]", "-", str(repo.resolve()))


def fm(name: str, desc: str) -> str:
    return f"---\nname: {name}\ndescription: {desc}\nmetadata:\n  node_type: memory\n  type: project\n---\n\n"


def main() -> int:
    repo = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).parent / "gate-repo")
    repo.mkdir(parents=True, exist_ok=True)
    (repo / "README.md").write_text(
        "# dream-beta-test gate fixture repo\n\nDummy repo. Its slug resolves the FROZEN synthetic "
        "store the continuous-QA gate runs against. Regenerate with `fixtures/make_fixture.py`.\n")
    store = Path.home() / ".claude" / "projects" / slug_for(repo) / "memory"
    store.mkdir(parents=True, exist_ok=True)
    for f in store.glob("*.md"):
        f.unlink()

    # 50 INDEXED facts; fact-01 wikilinks the orphan (makes it reachable from an indexed fact).
    for i in range(1, N_INDEXED + 1):
        name = f"fixture-fact-{i:02d}"
        body = fm(name, f"synthetic indexed fixture fact {i}") + ("lorem ipsum dolor sit amet " * 12)
        if i == 1:
            body += "\n\nThis indexed fact references [[fixture-orphan-linked]] — so that orphan is "
            body += "wikilink-reachable from an INDEXED fact and must be protected from eviction."
        (store / f"{name}.md").write_text(body)

    # The ORPHAN: un-indexed (no MEMORY.md pointer) but reachable via the [[wikilink]] above (→ D4).
    (store / "fixture-orphan-linked.md").write_text(
        fm("fixture-orphan-linked",
           "un-indexed fact reachable ONLY via a wikilink from an indexed fact — the evict-stage "
           "must route it to R_referenced (de-link-first), never A_orphans (evict)")
        + "The orphan. Reachable from [[fixture-fact-01]].")

    # Extra UN-INDEXED facts: the backfill/triage set (→ D3 needs un-indexed facts under the gate).
    for i in range(1, N_UNINDEXED + 1):
        (store / f"fixture-unindexed-{i:02d}.md").write_text(
            fm(f"fixture-unindexed-{i:02d}", f"un-indexed fixture fact {i} (backfill/triage set)")
            + f"Un-indexed fact {i}.")

    # DENSE index → over budget. Pointers cover only the 50 indexed facts (NOT the orphan/unindexed).
    lines = ["# Fixture memory index (synthetic — dream-beta-test gate fixture; FROZEN)\n"]
    for i in range(1, N_INDEXED + 1):
        lines.append(f"- [Fixture fact {i:02d}](fixture-fact-{i:02d}.md) — **{HOOK.format(i=i)}.**")
    (store / "MEMORY.md").write_text("\n".join(lines) + "\n")

    # Marker (for marker-delta / standing-justify-state reads).
    (store / ".consolidation-state.json").write_text(
        json.dumps({"commit": "fixturecommit0000000000000000000000000000", "timestamp": "2026-06-21T00:00:00Z"}))

    idx_bytes = (store / "MEMORY.md").stat().st_size
    print(f"fixture repo:  {repo}")
    print(f"fixture store: {store}")
    print(f"  {N_INDEXED} indexed + {N_UNINDEXED} un-indexed + 1 wikilink-orphan · "
          f"MEMORY.md {idx_bytes} B (≈{idx_bytes // 4} tok, budget 1200 → over)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
