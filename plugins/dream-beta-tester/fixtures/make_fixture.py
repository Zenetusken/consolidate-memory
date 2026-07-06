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
        make_fixture.py --help   prints this and exits — creates nothing
Idempotent: clears + rewrites the fixture store.
"""
from __future__ import annotations

import argparse
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
    # v0.1.40 (M3): match the skill's generalized slug rule (ALL non-alnum → '-'), not just [/_]; else the
    # fixture store lands at a different slug than the skill/oracle resolve → the gate sees an empty store.
    return re.sub(r"[^A-Za-z0-9]", "-", str(repo.resolve()))


def fm(name: str, desc: str) -> str:
    return f"---\nname: {name}\ndescription: {desc}\nmetadata:\n  node_type: memory\n  type: project\n---\n\n"


def main() -> int:
    # v0.1.69/B8: a bare `sys.argv[1]` used ANY flag (including `--help`) as a literal path —
    # the audit's live repro: `make_fixture.py --help` silently created `./--help/`. argparse's
    # built-in help action now intercepts --help/-h BEFORE the positional is ever touched
    # (prints usage, exits 0, creates nothing).
    # Gate-2a follow-up: __doc__ is None under -OO/PYTHONOPTIMIZE=2 (docstrings stripped) — a bare
    # __doc__.splitlines() crashed the fixture generator before argparse even ran in that environment.
    ap = argparse.ArgumentParser(
        description=(__doc__ or "Generate the FROZEN gate fixture store.").splitlines()[0])
    ap.add_argument("fixture_repo", nargs="?", default=str(Path(__file__).parent / "gate-repo"),
                    help="target fixture repo directory (default: <this dir>/gate-repo)")
    args = ap.parse_args()
    repo = Path(args.fixture_repo)
    repo.mkdir(parents=True, exist_ok=True)
    (repo / "README.md").write_text(
        "# dream-beta-test gate fixture repo\n\nDummy repo. Its slug resolves the FROZEN synthetic "
        "store the continuous-QA gate runs against. Regenerate with `fixtures/make_fixture.py`.\n",
        encoding="utf-8")
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
        (store / f"{name}.md").write_text(body, encoding="utf-8")

    # The ORPHAN: un-indexed (no MEMORY.md pointer) but reachable via the [[wikilink]] above (→ D4).
    (store / "fixture-orphan-linked.md").write_text(
        fm("fixture-orphan-linked",
           "un-indexed fact reachable ONLY via a wikilink from an indexed fact — the evict-stage "
           "must route it to R_referenced (de-link-first), never A_orphans (evict)")
        + "The orphan. Reachable from [[fixture-fact-01]].", encoding="utf-8")

    # Extra UN-INDEXED facts: the backfill/triage set (→ D3 needs un-indexed facts under the gate).
    for i in range(1, N_UNINDEXED + 1):
        (store / f"fixture-unindexed-{i:02d}.md").write_text(
            fm(f"fixture-unindexed-{i:02d}", f"un-indexed fixture fact {i} (backfill/triage set)")
            + f"Un-indexed fact {i}.", encoding="utf-8")

    # DENSE index → over budget. Pointers cover only the 50 indexed facts (NOT the orphan/unindexed).
    lines = ["# Fixture memory index (synthetic — dream-beta-test gate fixture; FROZEN)\n"]
    for i in range(1, N_INDEXED + 1):
        lines.append(f"- [Fixture fact {i:02d}](fixture-fact-{i:02d}.md) — **{HOOK.format(i=i)}.**")
    (store / "MEMORY.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    # Marker (for marker-delta / standing-justify-state reads).
    (store / ".consolidation-state.json").write_text(
        json.dumps({"commit": "fixturecommit0000000000000000000000000000", "timestamp": "2026-06-21T00:00:00Z"}),
        encoding="utf-8")

    # v0.1.69/B5: a persisted dream — WITHOUT this, dream_arc_capture/distill_capture return `[]` on
    # the empty-log guard (invisible to families_ran/families_skipped, not even a SKIP row), and
    # usage_capture/demotion_capture (below) can never fire at all. ONE current-shape record, honest
    # dormant/zero values throughout (this fixture has no real usage history) — a dot-file, invisible
    # to the `store.glob("*.md")` fact scan D3/D4 measure, so their known-bad proof is unaffected.
    _log_record = {
        "marker": {"commit": "fixturedreamcommit000000000000000000000", "timestamp": "2026-06-21T01:00:00Z"},
        "dream": {
            "sleep": "*💤 drifting into the fixture repo's memory...*",
            "beats": ["*🌙 Phase 0 — orienting to the fixture store...*"],
            "wake": "*☀️ waking — the fixture dream is complete.*",
        },
        "distill": {
            "sessions": 1, "commands": 1, "n_recurring": 0, "n_chains": 0, "window": "(all)",
            "secrets_omitted": 0, "proposed": [],
            "verdict": "nothing: no recurring workflow signal in this synthetic fixture",
        },
        "usage": {
            "window": "2026-06-20T00:00:00Z..2026-06-21T01:00:00Z", "transcripts": 0,
            "dream_excluded": 0, "reads": 0, "facts_read": 0, "per_fact": [],
            "archive_reads": 0, "misses": [],
        },
        "demotion": {
            "windows_observed": 0, "eligible": 0, "surfaced": [], "struck": [],
            "verdict": "dormant — 0 probative windows observed (fixture, honest baseline)",
        },
    }
    (store / ".consolidation-log.jsonl").write_text(json.dumps(_log_record) + "\n", encoding="utf-8")

    idx_bytes = (store / "MEMORY.md").stat().st_size
    print(f"fixture repo:  {repo}")
    print(f"fixture store: {store}")
    print(f"  {N_INDEXED} indexed + {N_UNINDEXED} un-indexed + 1 wikilink-orphan · "
          f"MEMORY.md {idx_bytes} B (≈{idx_bytes // 4} tok, budget 1200 → over)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
