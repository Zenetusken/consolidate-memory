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

# --- token estimation (Fix A / observability) ---
check("tokens: empty is 0", ms.est_tokens("") == 0)
check("tokens: ceil(chars/4)", ms.est_tokens("abcdefgh") == 2 and ms.est_tokens("abcde") == 2)
check("tokens: monotonic", ms.est_tokens("a" * 100) > ms.est_tokens("a" * 10))
# the sibling import must resolve to the SAME function (catches path breakage at the gate)
check("tokens: sync_global reuses memory_status.est_tokens", sg.est_tokens is ms.est_tokens)

# --- Fix C: index pointer is now an upsert (pure line builder) ---
check("pointer: builds line with scope tag",
      sg._pointer_line("foo", {"description": "a hook", "scope": "user-global"})
      == "- [foo](foo.md) — a hook [user-global]")
check("pointer: truncates long description to a recall hook",
      sg._pointer_line("foo", {"description": "x" * 200}).count("…") == 1)

# --- Fix D: stack keyword matching is word-bounded, not substring ---
check("stacks: 'skill' does NOT match 'reskilling'", sg._kw_hit("a reskilling plan", "skill") is False)
check("stacks: 'skill' matches the word 'skill'", sg._kw_hit("this skill rocks", "skill") is True)
check("stacks: dotted '.claude' still matches", sg._kw_hit("see the .claude/ dir", ".claude") is True)
check("stacks: 'pytest' matches", sg._kw_hit("run pytest now", "pytest") is True)

# --- node label: hyphenated project name not mislabeled (slug is not invertible) ---
check("node label: keeps hyphenated tail, not 'memory'",
      sg._label_from_slug("-home-drei-project-consolidate-memory").endswith("consolidate-memory")
      and sg._label_from_slug("-home-drei-project-consolidate-memory") != "memory")
check("node label: de-prefixes leading dash on short slug",
      sg._label_from_slug("-a-b") == "a-b")

# --- Fix A render: budget overflow flag ---
check("render: over-budget flag shows ⚠", "OVER" in rd._over({"over": True, "budget_tokens": 1200}))
check("render: under budget is silent", rd._over({"over": False}) == "")

# --- observability: network sub-section is guarded + rendered ---
_net = {"basis": "≈ chars/4", "node_def": "stores", "trigger": "p",
        "nodes": [{"node": "p", "trigger": True, "always_loaded_tokens": 10,
                   "recall_tokens": 20, "facts": 2, "shared": 1}],
        "totals": {"nodes": 1, "always_loaded_tokens": 10, "recall_tokens": 20}}
check("render: network section appears when present",
      "Neural network" in rd.render({"project": "p", "session": "s", "scope": {},
                                      "entries": [], "network": _net}))
check("render: network section absent when no block (legacy/no-op safe)",
      "Neural network" not in rd.render({"project": "p", "session": "s", "scope": {}, "entries": []}))

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
