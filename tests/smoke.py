#!/usr/bin/env python3
"""Zero-dependency smoke tests for the consolidate-memory scripts.

Run:  python3 tests/smoke.py   (exit 0 = all passed). No pytest required.
Tests pure functions only — no filesystem mutation, no network, no real memory.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "skill" / "scripts"))

import extract_signals as es  # noqa: E402
import memory_status as ms  # noqa: E402
import render_dashboard as rd  # noqa: E402
import sync_global as sg  # noqa: E402

passed = failed = 0


def check(name: str, cond: bool) -> None:
    global passed, failed
    if cond:
        passed += 1
        print(f"  ✓ {name}")
    else:
        failed += 1
        print(f"  ✗ {name}")


# --- slug rule ---
check("slug: / -> -", ms.slug_for(Path("/home/you/project/foo")) == "-home-you-project-foo")

# --- dashboard outcome classification (data-driven banner) ---
def _oc(writes: int, cands: int, git: int, reviewed: int) -> str:
    entries = [{"action": "added"} for _ in range(writes)]
    return rd._outcome({"entries": entries,
                        "scope": {"session_candidates": cands, "git_commits": git,
                                  "memories_reviewed": reviewed}})


check("outcome: nothing", _oc(0, 0, 0, 0) == "NOTHING TO CONSOLIDATE")
check("outcome: no-op", _oc(0, 0, 0, 5).startswith("NO-OP"))
check("outcome: light", _oc(1, 1, 0, 1) == "LIGHT PASS")
check("outcome: substantial", _oc(4, 8, 12, 5) == "SUBSTANTIAL PASS")
check("dashboard renders banner", "DREAM · consolidate-memory" in
      rd.render({"project": "p", "session": "s", "scope": {}, "entries": []}))

# --- cross-project relevance ---
check("relevance: user-global everywhere", sg.is_relevant({"scope": "user-global"}, set()) is True)
check("relevance: stack-general needs match",
      sg.is_relevant({"scope": "stack-general", "stacks": "[rag, gpu]"}, {"web"}) is False)
check("relevance: stack-general matches",
      sg.is_relevant({"scope": "stack-general", "stacks": "[rag, gpu]"}, {"rag"}) is True)
check("relevance: project-local never global", sg.is_relevant({"scope": "project-local"}, {"rag"}) is False)

# --- mirror stamping is robust + idempotent ---
fact = "---\nname: x\nmetadata:\n  node_type: memory\n---\nbody\n"
mirror = sg._as_mirror(fact, "x")
check("mirror: injects global_ref", "global_ref: x" in mirror)
check("mirror: idempotent", sg._as_mirror(mirror, "x").count("global_ref: x") == 1)

# --- retrieval safety: secret omission + noise filtering ---
check("retrieval: secret pattern hit (long token)", bool(es._SECRET.search("AQED" + "a" * 60)))
check("retrieval: secret pattern hit (named)", bool(es._SECRET.search("password = hunter2")))
check("retrieval: plain text not flagged", not es._SECRET.search("fix the indeed scraper please"))
check("retrieval: noise drops command echo", bool(es._NOISE.match("<local-command-stdout>x</...>")))
check("retrieval: noise drops caveat", bool(es._NOISE.match("Caveat: messages below ...")))
check("retrieval: real turn not noise", not es._NOISE.match("Please fix this at the root with tests"))
_t, _scope, score = es._classify("Always validate at the root with tests")
check("retrieval: marker classified preference", _t == "preference" and score == 2)
check("retrieval: bare ack ranked lowest", es._classify("yes")[2] == 0)

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
