#!/usr/bin/env python3
"""Zero-dependency smoke tests for the consolidate-memory scripts.

Run:  python3 tests/smoke.py   (exit 0 = all passed). No pytest required.
Tests pure functions only — no filesystem mutation, no network, no real memory.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "plugins" / "consolidate-memory" / "scripts"))

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

# --- hardening: SHA validation rejects argument-injection from a tampered state file ---
check("sha: accepts real hex sha", ms._valid_sha("b6d37b6") and ms._valid_sha("a" * 40))
check("sha: rejects git option injection", not ms._valid_sha("--output=/etc/passwd"))
check("sha: rejects empty / junk", not ms._valid_sha("") and not ms._valid_sha("HEAD; rm -rf"))

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

# --- rigor tier (v0.1.3): FLOW magnitude → tier; provisional/final; NO memories_reviewed ---
import inspect as _inspect  # noqa: E402
check("rigor: LIGHT at magnitude <= 2",
      ms.suggested_tier(2, 0) == "LIGHT" and ms.suggested_tier(0, 2) == "LIGHT" and ms.suggested_tier(1, 1) == "LIGHT")
check("rigor: SUBSTANTIAL 3..7",
      ms.suggested_tier(3, 0) == "SUBSTANTIAL" and ms.suggested_tier(4, 3) == "SUBSTANTIAL" and ms.suggested_tier(7, 0) == "SUBSTANTIAL")
check("rigor: HEAVY at >= 8", ms.suggested_tier(8, 0) == "HEAVY" and ms.suggested_tier(5, 5) == "HEAVY")
_ord = ms.TIER_ORDER  # canonical tier rank (single source in memory_status)
check("rigor: monotonic non-decreasing in magnitude",
      all(_ord[ms.suggested_tier(0, m)] <= _ord[ms.suggested_tier(0, m + 1)] for m in range(0, 20)))
# F1 regression guard: the magnitude axis is FLOW-only; the cumulative stock
# (memories_reviewed) must NOT be a parameter, or a mature store pegs every pass to HEAVY.
check("rigor: suggested_tier excludes memories_reviewed (F1 axis-separation guard)",
      "memories_reviewed" not in _inspect.signature(ms.suggested_tier).parameters
      and "reviewed" not in _inspect.signature(ms.suggested_tier).parameters)
# prune-pressure: the SEPARATE axis the stock drives
check("rigor: prune_pressure on index-over-budget", ms.prune_pressure(True, 0) == (True, "index-over-budget"))
check("rigor: prune_pressure on many-facts at threshold", ms.prune_pressure(False, ms.PRUNE_PRESSURE_FACTS) == (True, "many-facts"))
check("rigor: prune_pressure clear when small + under budget", ms.prune_pressure(False, ms.PRUNE_PRESSURE_FACTS - 1) == (False, ""))
check("rigor: index-over takes reason precedence over many-facts", ms.prune_pressure(True, 999)[1] == "index-over-budget")
# A10: no-marker first pass — git_range defaults to a recent-≤20 lookback, so a mature repo's
# FIRST consolidation reads HEAVY provisional purely from history depth (documented, advisory;
# the model finalizes in Phase 2). The seed rigor block is phase:provisional regardless.
check("rigor: no-marker 20-commit lookback → HEAVY provisional (A10)", ms.suggested_tier(20, 0) == "HEAVY")
check("rigor: provisional rigor block is phase:provisional, no stored tier (A10)",
      ms._provisional_rigor({"index_lb": (0, 0, 0), "fact_files": []})
      == {"phase": "provisional", "prune_pressure": False, "prune_reason": "",
          "applied": "", "override_reason": ""})
check("rigor: seed includes empty applied/override_reason, model fills in Phase 2/4 (v0.1.4)",
      ms._provisional_rigor({"index_lb": (0, 0, 0), "fact_files": []})["applied"] == ""
      and ms._provisional_rigor({"index_lb": (0, 0, 0), "fact_files": []})["override_reason"] == "")
# render: the RIGOR line shows a tier + magnitude BOTH DERIVED from scope (never stored)
_rrec = {"project": "p", "session": "s", "scope": {"git_commits": 6, "session_candidates": 9},
         "entries": [], "rigor": {"phase": "final", "prune_pressure": True, "prune_reason": "many-facts"}}
check("render: rigor line shows derived tier (6+9=15 → HEAVY)", "RIGOR" in rd.render(_rrec) and "HEAVY" in rd.render(_rrec))
check("render: rigor magnitude DERIVED from scope (6+9=15)", "magnitude 15" in rd.render(_rrec))
check("render: prune-pressure surfaced on the rigor line", "prune-pressure" in rd.render(_rrec))
check("render: legacy record without rigor omits the line (no crash)",
      "RIGOR" not in rd.render({"project": "p", "session": "s", "scope": {}, "entries": []}))
# A1 regression: the displayed tier is DERIVED from the magnitude, NEVER a stored label —
# a stale/contradictory stored suggested_tier must not reach the RIGOR line.
_drift = {"project": "p", "session": "s", "scope": {"git_commits": 8, "session_candidates": 7},
          "entries": [], "rigor": {"suggested_tier": "LIGHT", "phase": "final"}}  # stored LIGHT is a lie: mag=15
_drift_line = next((ln for ln in rd.render(_drift).splitlines() if "RIGOR" in ln), "")
check("render: tier DERIVED from magnitude, ignores a contradictory stored suggested_tier (A1)",
      "HEAVY" in _drift_line and "LIGHT" not in _drift_line)
# A2: a present-but-empty rigor {} still renders the derived line (presence, not truthiness)
check("render: empty rigor {} still shows the derived RIGOR line (A2)",
      "RIGOR" in rd.render({"project": "p", "session": "s", "scope": {"git_commits": 3, "session_candidates": 0},
                            "entries": [], "rigor": {}}))
# v0.1.4: the realized-rigor `applied` decision renders "suggested → applied · why" ONLY when it
# DIFFERS from the magnitude-derived suggested tier; absent/empty/equal renders unchanged (back-compat).
_app = {"project": "p", "session": "s", "scope": {"git_commits": 10, "session_candidates": 3},
        "entries": [], "rigor": {"phase": "final", "applied": "LIGHT",
                                 "override_reason": "already-consolidated flow"}}
_app_line = next((ln for ln in rd.render(_app).splitlines() if "RIGOR" in ln), "")
check("render: applied≠suggested shows 'HEAVY → LIGHT' (v0.1.4)",
      "HEAVY" in _app_line and "→" in _app_line and "LIGHT" in _app_line)
check("render: override_reason shown when applied differs (v0.1.4)", "already-consolidated flow" in _app_line)
_eq_line = next((ln for ln in rd.render({"project": "p", "session": "s",
                 "scope": {"git_commits": 10, "session_candidates": 3}, "entries": [],
                 "rigor": {"phase": "final", "applied": "HEAVY"}}).splitlines() if "RIGOR" in ln), "")
check("render: applied==suggested shows no arrow (v0.1.4)", "→" not in _eq_line and "HEAVY" in _eq_line)
check("render: empty applied → derived tier only, no arrow (v0.1.4)",
      "→" not in next((ln for ln in rd.render({"project": "p", "session": "s",
                       "scope": {"git_commits": 1, "session_candidates": 0}, "entries": [],
                       "rigor": {"phase": "final", "applied": ""}}).splitlines() if "RIGOR" in ln), ""))
check("render: non-string applied doesn't crash, renders the line (v0.1.4)",
      "RIGOR" in rd.render({"project": "p", "session": "s", "scope": {"git_commits": 1, "session_candidates": 0},
                            "entries": [], "rigor": {"applied": 5}}))
check("render: whitespace ' HEAVY ' applied is normalized → NO spurious 'X → X' arrow (v0.1.4)",
      "→" not in next((ln for ln in rd.render({"project": "p", "session": "s",
                       "scope": {"git_commits": 10, "session_candidates": 3}, "entries": [],
                       "rigor": {"applied": " HEAVY "}}).splitlines() if "RIGOR" in ln), ""))
check("render: unrecognized applied value → no arrow, suggested tier only (v0.1.4)",
      "→" not in next((ln for ln in rd.render({"project": "p", "session": "s",
                       "scope": {"git_commits": 10, "session_candidates": 3}, "entries": [],
                       "rigor": {"applied": "banana"}}).splitlines() if "RIGOR" in ln), ""))
check("render: case-insensitive applied 'light' still shows the override arrow (v0.1.4)",
      "→" in next((ln for ln in rd.render({"project": "p", "session": "s",
                   "scope": {"git_commits": 10, "session_candidates": 3}, "entries": [],
                   "rigor": {"applied": "light"}}).splitlines() if "RIGOR" in ln), ""))
# A5: a JSON-stringified 'false' prune_pressure must NOT trip the warning (_flag coercion)
check("render: stringized 'false' prune_pressure shows no warning (A5/_flag)",
      "prune-pressure" not in rd.render({"project": "p", "session": "s",
          "scope": {"git_commits": 1, "session_candidates": 0}, "entries": [],
          "rigor": {"phase": "final", "prune_pressure": "false"}}))
check("render: _flag coerces stringized booleans",
      rd._flag("false") is False and rd._flag("true") is True and rd._flag(True) is True and rd._flag("") is False)
# model-authored gnarly rigor (string/None/wrong-type) must not crash; tier still derived
_grig = {"project": "p", "session": "s", "scope": {"git_commits": "7", "session_candidates": None},
         "entries": [], "rigor": {"suggested_tier": 123, "phase": None,
                                   "prune_pressure": "yes", "prune_reason": None}}
_grig_out = rd.render(_grig)
check("render: gnarly rigor never crashes + derives tier (ignores stored 123)",
      isinstance(_grig_out, str) and "RIGOR" in _grig_out and "123" not in _grig_out)
check("demo: rigor tier shown in --demo preview", "RIGOR" in rd.render(rd._demo_record()))

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
check("retrieval: secret pattern hit (long token)", bool(es._looks_secret("AQ3D" + "x7Y2k9" * 9)))
# precision: long file paths / all-letter slugs must NOT be flagged (recall-preserving)
check("retrieval: long path NOT flagged",
      not es._looks_secret("/home/you/project/consolidate-memory/plugins/consolidate-memory/scripts/"))
check("retrieval: all-letter slug NOT flagged",
      not es._looks_secret("home-you-project-consolidate-memory-plugins-consolidate-memory"))
check("retrieval: OpenAI sk- key flagged", bool(es._looks_secret("sk-proj-" + "a1B2c3D4e5F6g7H8i9J0")))
check("retrieval: secret pattern hit (named)", bool(es._looks_secret("password = hunter2")))
check("retrieval: plain text not flagged", not es._looks_secret("fix the indeed scraper please"))
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
check("pointer: strips control bytes/newlines from the hook (no index injection)",
      "\n" not in sg._pointer_line("foo", {"description": "a\nb\x1b[31mc"}) and
      "\x1b" not in sg._pointer_line("foo", {"description": "a\nb\x1b[31mc"}))
# frontmatter parses folded/block scalars (description: >-) instead of storing ">-"
check("frontmatter: folds block scalar value",
      sg._frontmatter("---\nname: x\ndescription: >-\n  hello\n  world\nmetadata:\n  scope: user-global\n---\nb")["description"] == "hello world")
check("frontmatter: single-line value unchanged",
      sg._frontmatter("---\nname: x\ndescription: plain hook\n---\nb")["description"] == "plain hook")

# --- v0.1.5: orphan + drift detection (PURE helpers — strings/sets/dicts only; FS-touching
#     cases live in simulate_accumulation.py since smoke must not mutate the filesystem) ---
# _frontmatter is now PROMOTED to memory_status (single definition); sync_global imports it.
check("v0.1.5: sync_global._frontmatter IS memory_status._frontmatter (single definition)",
      sg._frontmatter is ms._frontmatter)
# _frontmatter tolerates a malformed file ({}), a CRLF file, and a BOM-prefixed file — and
# all healthy variants must still extract node_type (else schema_drift miscounts them).
check("frontmatter: malformed (no fence) returns {} (never raises)",
      ms._frontmatter("not frontmatter at all\njust text\n") == {})
_normal_fm = ms._frontmatter("---\nname: x\nmetadata:\n  node_type: memory\n---\nbody\n")
check("frontmatter: parses a normal block (node_type captured)", _normal_fm.get("node_type") == "memory")
check("frontmatter: CRLF file still extracts node_type (M3)",
      ms._frontmatter("---\r\nname: x\r\nmetadata:\r\n  node_type: memory\r\n---\r\nbody\r\n").get("node_type") == "memory")
check("frontmatter: BOM-prefixed file still extracts node_type (M3)",
      ms._frontmatter("﻿---\nname: x\nmetadata:\n  node_type: memory\n---\nbody\n").get("node_type") == "memory")
# _valid_uuid: a real 8-4-4-4-12 hex UUID accepted; truncated / garbage rejected.
check("uuid: accepts a real 8-4-4-4-12 UUID",
      ms._valid_uuid("1920c541-0f32-4b9d-8b0b-1da262a307b0"))
check("uuid: rejects truncated / garbage / non-string",
      not ms._valid_uuid("1920c541-0f32-4b9d-8b0b") and not ms._valid_uuid("not-a-uuid")
      and not ms._valid_uuid("") and not ms._valid_uuid(None))
# near_duplicate_slugs: flags '-'/'_'/case twins, ignores unrelated, NEVER flags itself (B2).
_slug = "-home-drei-project-Doc-Flo"
_sibs = ["-home-drei-project-Doc-Flo", "-home-drei-project-Doc_Flo",
         "-home-drei-project-doc-flo", "-home-drei-project-other"]
check("near-dup: flags '_' and case variants, excludes self + unrelated",
      ms.near_duplicate_slugs(_slug, _sibs)
      == ["-home-drei-project-Doc_Flo", "-home-drei-project-doc-flo"])
check("near-dup: a slug is never its own duplicate (B2 self-exclusion)",
      ms.near_duplicate_slugs(_slug, [_slug]) == [])
check("near-dup: no twins → empty list", ms.near_duplicate_slugs(_slug, ["-x", "-y-z"]) == [])
# drift_findings: dict → int; counts the four DRIFT fields, NOT the advisory absence-counts.
check("drift_findings: sums the four drift fields, ignores advisory absence",
      ms.drift_findings({"missing_node_type": 1, "malformed_scope": 2, "malformed_origin": 0,
                         "index_mismatch": 3, "advisory_no_scope": 99, "advisory_no_origin": 99}) == 6)
check("drift_findings: all-zero drift → 0 (defines 'clean' for AC#1)",
      ms.drift_findings({"missing_node_type": 0, "malformed_scope": 0, "malformed_origin": 0,
                         "index_mismatch": 0, "advisory_no_scope": 5, "advisory_no_origin": 5}) == 0)
check("drift_findings: tolerant of missing keys (.get default 0)", ms.drift_findings({}) == 0)
# render: HEALTH surfaces slug-orphan + schema-drift findings (presence-checked) ...
_h_orphan = rd.render({"project": "p", "session": "s", "scope": {}, "entries": [],
                       "health": {"index_pointers_ok": True, "slug_orphans": ["-home-x-Doc_Flo"],
                                  "schema_drift": {"missing_node_type": 2, "malformed_scope": 0,
                                                   "malformed_origin": 0, "index_mismatch": 3}}})
check("render: HEALTH shows slug-orphan twin name", "slug-orphan" in _h_orphan and "Doc_Flo" in _h_orphan)
check("render: HEALTH shows schema-drift counts when drift_findings > 0",
      "schema drift" in _h_orphan and "missing node_type" in _h_orphan)
# ... and a CLEAN store (no drift, advisory-only) shows NO drift ⚠ in HEALTH (AC#3)
_h_clean = rd.render({"project": "p", "session": "s", "scope": {}, "entries": [],
                      "health": {"index_pointers_ok": True, "slug_orphans": [],
                                 "schema_drift": {"missing_node_type": 0, "malformed_scope": 0,
                                                  "malformed_origin": 0, "index_mismatch": 0,
                                                  "advisory_no_scope": 9, "advisory_no_origin": 9}}})
check("render: clean store shows no drift/orphan ⚠ in HEALTH (AC#3)",
      "schema drift" not in _h_clean and "slug-orphan" not in _h_clean and "✓ all pointers resolve" in _h_clean)
# LEGACY record (no slug_orphans/schema_drift keys) must render BYTE-IDENTICALLY (AC#5).
_legacy = {"project": "p", "session": "s", "scope": {}, "entries": [],
           "health": {"index_pointers_ok": True, "broken": [], "dangling_links": []}}
import copy as _copy  # noqa: E402
_legacy_plus = _copy.deepcopy(_legacy)   # same record WITH the v0.1.5 keys present-but-empty
_legacy_plus["health"]["slug_orphans"] = []
_legacy_plus["health"]["schema_drift"] = {}
check("render: empty v0.1.5 keys render identically to a legacy record (AC#5 back-compat)",
      rd.render(_legacy) == rd.render(_legacy_plus))
check("render: legacy render is deterministic + non-mutating",
      rd.render(_legacy) == rd.render(_copy.deepcopy(_legacy)))
check("render: legacy health has no slug-orphan/schema-drift line (AC#5)",
      "slug-orphan" not in rd.render(_legacy) and "schema drift" not in rd.render(_legacy))
# model-authored health: a NON-numeric schema_drift value must NOT crash render (the
# _num/_clean/_flag never-crash invariant) — render coerces at the boundary, unlike the
# strict-int ms.drift_findings used by the seed/smoke with clean ints.
_gnarly_h = rd.render({"project": "p", "session": "s", "scope": {}, "entries": [],
                       "health": {"index_pointers_ok": True, "slug_orphans": None,
                                  "schema_drift": {"missing_node_type": "two", "index_mismatch": None}}})
check("render: non-numeric/None schema_drift never crashes render (model→presentation coercion)",
      isinstance(_gnarly_h, str) and "HEALTH" in _gnarly_h)
# Gate-2 F1: a TRUTHY non-dict schema_drift / non-list slug_orphans (model slip) must not crash —
# `or {}`/`or []` only catch FALSY values; the isinstance guards catch a truthy wrong-type.
_gnarly2 = rd.render({"project": "p", "session": "s", "scope": {}, "entries": [],
                      "health": {"index_pointers_ok": True, "slug_orphans": "Doc_Flo",
                                 "schema_drift": "2 missing node_type"}})
check("render: truthy non-dict schema_drift / non-list slug_orphans never crash render (Gate-2 F1)",
      isinstance(_gnarly2, str) and "HEALTH" in _gnarly2)

# --- Fix D: stack keyword matching is word-bounded, not substring ---
check("stacks: 'skill' does NOT match 'reskilling'", sg._kw_hit("a reskilling plan", "skill") is False)
check("stacks: 'skill' matches the word 'skill'", sg._kw_hit("this skill rocks", "skill") is True)
check("stacks: dotted '.claude' still matches", sg._kw_hit("see the .claude/ dir", ".claude") is True)
check("stacks: 'pytest' matches", sg._kw_hit("run pytest now", "pytest") is True)

# --- node label: hyphenated project name not mislabeled (slug is not invertible) ---
check("node label: keeps hyphenated tail, not 'memory'",
      sg._label_from_slug("-home-you-project-consolidate-memory").endswith("consolidate-memory")
      and sg._label_from_slug("-home-you-project-consolidate-memory") != "memory")
check("node label: de-prefixes leading dash on short slug",
      sg._label_from_slug("-a-b") == "a-b")
check("node label: strips terminal control bytes (--tokens print safety)",
      "\x1b" not in sg._label_from_slug("-home-you-ev\x1b[31mil"))

# --- pentest fix (High/Med): mirror detection is frontmatter-anchored, not substring ---
_mirror_meta = "---\nname: x\nmetadata:\n  node_type: memory\n  global_ref: x\n---\nbody\n"
_mirror_hash = "---\n# global_ref: x\nname: x\n---\nbody\n"
_prose = "---\nname: notes\n---\nThis note explains how global_ref: markers work in sync.\n"
_nofm = "a plain note mentioning global_ref: somewhere with no frontmatter\n"
check("mirror: detects metadata global_ref", sg._is_mirror(_mirror_meta) is True)
check("mirror: detects frontmatter-comment global_ref", sg._is_mirror(_mirror_hash) is True)
check("mirror: prose mention in BODY is NOT a mirror (GC-safety)", sg._is_mirror(_prose) is False)
check("mirror: no-frontmatter mention is NOT a mirror", sg._is_mirror(_nofm) is False)
check("mirror: round-trips _as_mirror output", sg._is_mirror(sg._as_mirror(_prose, "notes")) is True)
# PROPERTY: _is_mirror(_as_mirror(t, n)) must hold for ANY frontmatter shape — producer
# and recognizer must agree, or a stamped mirror becomes unrecognized (never refreshed,
# GC-immune). Includes adversarial shapes (indented metadata:, metadata inside a folded
# scalar) that previously desynced the two.
for _i, _fm in enumerate([
    "---\nname: a\nmetadata:\n  node_type: memory\n---\nbody\n",          # normal metadata block
    "---\nname: b\ndescription: just text\n---\nbody\n",                  # no metadata block
    "---\nname: c\n  metadata:\n  scope: user-global\n---\nbody\n",       # INDENTED metadata (adversarial)
    "---\ndescription: >-\n  folded\n  metadata:\n---\nbody\n",           # 'metadata:' inside a folded scalar
    "﻿---\nname: e\nmetadata:\n  node_type: memory\n---\nbody\n",     # leading BOM (Gate-2 F3)
]):
    check(f"mirror: round-trip property holds (shape {_i})",
          sg._is_mirror(sg._as_mirror(_fm, "x")) is True)

# --- pentest fix (High): secrets firewall covers credential-shaped ERROR output ---
check("firewall: catches bearer token in error text",
      bool(es._looks_secret("HTTP 401 WWW-Authenticate: Bearer " + "a" * 50)))
check("firewall: catches password= leak in error text",
      bool(es._looks_secret("FATAL: password authentication failed; password=s3cr3t-value")))

# --- re-gate fixes: structural mirror detection (H-3, folded-YAML false positive) ---
_folded = "---\nname: design-notes\ndescription: >-\n  notes about the\n  global_ref: marker\n---\nbody\n"
_evil_meta = "---\nname: x\nmetadata:\n  description: >-\n    global_ref: x\n---\nb\n"
check("mirror: folded-scalar continuation is NOT a mirror (H-3 GC-safety)", sg._is_mirror(_folded) is False)
check("mirror: deep-indent under metadata child is NOT a mirror", sg._is_mirror(_evil_meta) is False)
check("mirror: real metadata-child + col-0 stamp still detected",
      sg._is_mirror(_mirror_meta) and sg._is_mirror(_mirror_hash))

# --- re-gate fixes: firewall catches named provider key shapes (H-4) ---
# NB: provider-token fixtures are assembled by concatenation from obviously-fake parts,
# so no contiguous real-looking token literal exists in this source file (GitHub
# secret-scanning push protection matches source text, not runtime values). Each still
# matches the firewall regex SHAPE, which is all these tests assert.
for _name, _val, _want in [
    ("AWS AKIA", "AKIA" + "EXAMPLE0EXAMPLE0", True),                 # AKIA + 16
    ("Slack xoxb", "xoxb-" + "000000000-000000-fakefakefake", True),
    ("Stripe sk_live", "sk_" + "live_" + "0000example0000fake", True),
    ("GitHub ghp_", "ghp_" + "A" * 36, True),
    ("JWT", "eyJ" + "fakehead." + "eyJfakebody." + "fakesig", True),
    ("URI user:pass@", "postgres://user:" + "fakepw" + "@db.example.com/app", True),
    ("ordinary phrase", "please fix the scraper and run the tests", False),
]:
    check(f"firewall: {_name} -> {'flagged' if _want else 'clean'}", bool(es._looks_secret(_val)) is _want)

# --- re-gate fix (High): firewall catches the keyword as a SEGMENT of a compound id ---
for _name, _val, _want in [
    ("AWS_SECRET_ACCESS_KEY=", "AWS_SECRET_ACCESS_KEY=wJalrFakeKeyValueHere", True),
    ("SECRET_KEY=", "SECRET_KEY=django-insecure-q8z", True),
    ("client_secret_key=", "client_secret_key=ZmFrZXZhbHVl", True),
    ("MY_API_KEY=", "MY_API_KEY=abc123", True),
    ("tokenizer_x= (NOT a secret — token is a substring, not a segment)", "tokenizer_config=5", False),
    ("secretary= (NOT a secret)", "secretary_name=alice", False),
    ("pwd=", "pwd=Hunter2!", True),
    ("pass:", "pass: MyS3cret", True),
    ("creds:", "credentials: admin/hunter2", True),
    ("private_key=", "private_key=shortval123", True),
    ("passenger_count= (NOT a secret — pass is a substring)", "passenger_count=5", False),
]:
    check(f"firewall(compound): {_name} -> {'flagged' if _want else 'clean'}",
          bool(es._looks_secret(_val)) is _want)

# --- re-gate(2) fixes: entropy-blob handles '/' + all-alpha; keyword arm handles quotes ---
for _name, _val, _want in [
    # bare slash-bearing base64 (AWS-secret shape), mixed case, <3 slashes, no keyword
    ("bare slash-base64", "Wj0Alr/UtnFEMI" + "K7MdENgbPxRfiCyExampleKey99", True),
    # all-alphabetic mixed-case 48-char token (no digit, no slash)
    ("all-alpha mixed 48", "AbCdEf" * 8, True),
    # quoted-JSON credential (keyword arm must see through the quotes)
    ('JSON {"password":"x"}', '{"password": "hunter2longvalue"}', True),
    ('JSON {"api_key":"x"}', '{"api_key": "abc123def456"}', True),
    ('JSON {"client_secret":"x"}', '{"client_secret": "ZmFrZXZhbHVl"}', True),
    # precision still holds: a deep file path is NOT a secret
    ("deep path (>=3 slashes)", "/home/you/project/foo/bar/baz/qux/some_module.py", False),
]:
    check(f"firewall(redesign): {_name} -> {'flagged' if _want else 'clean'}",
          bool(es._looks_secret(_val)) is _want)

# --- re-gate(2) fix (Low): a `# global_ref:` comment NOT on the first frontmatter line
#     is not a mirror (so plain --pull never clobbers a hand-authored note) ---
check("mirror: # global_ref comment below the first line is NOT a mirror",
      sg._is_mirror("---\nname: notes\n# global_ref: x\n---\nbody\n") is False)
check("mirror: # global_ref stamp on the FIRST frontmatter line IS a mirror",
      sg._is_mirror("---\n# global_ref: notes\nname: notes\n---\nbody\n") is True)

# --- re-gate(2) fix (Low): memory_status sanitizes control bytes before printing ---
check("sane: strips ESC/control bytes from printed git text",
      "\x1b" not in ms._sane("feat: x\x1b[2J\x07") and ms._sane("plain msg") == "plain msg")

# --- re-gate(3) fix (Low): zero-width/Cf chars are stripped before scan+store ---
check("norm: strips zero-width (Cf) chars", es._norm("a\u200bb\u200dc") == "abc")
check("firewall: zero-width-split secret is caught after _norm",
      bool(es._looks_secret(es._norm("AKIA\u200bEXAMPLE0EXAMPLE0"))))

# --- re-gate fix (Low): pointer matching uses the link target, hook strips markdown ---
check("pointer: hook strips markdown link chars (no []() injection)",
      all(c not in sg._pointer_line("foo", {"description": "evil](http://x) link"}).split("—", 1)[1]
          for c in "[]()"))
check("stale-since: non-string marker does not crash (returns [])",
      ms._stale_since([], 1234567890) == [] and ms._stale_since([], None) == [])

# --- run-3 fixes: name/token hardening into the shared store + tier-1 index ---
check("name: safe kebab stem accepted", sg._safe_stem("gh-pr-edit-broken_v2.1"))
check("name: markdown-link injection stem rejected", sg._safe_stem("evil](http://x)") is False)
check("name: whitespace stem rejected", sg._safe_stem("a b") is False and sg._safe_stem("") is False)
check("token: project name sanitized (neutralizes backref + brackets)",
      sg._sanitize_token(r"proj\1]evil") == "proj-1-evil")
check("token: clean project name unchanged", sg._sanitize_token("home-you-project-foo") == "home-you-project-foo")

# --- re-gate fix: dashboard strips terminal control bytes (Low) ---
check("render: _clean strips ESC/control bytes", "\x1b" not in rd._clean("a\x1b[31mX") and rd._clean("a\x1b[31mX").endswith("[31mX"))
check("render: _clean preserves plain text", rd._clean("b6d37b6 fix_thing.py") == "b6d37b6 fix_thing.py")

# --- Fix A render: budget overflow flag ---
check("render: over-budget flag shows ⚠", "OVER" in rd._over({"over": True, "budget_tokens": 1200}))
check("render: under budget is silent", rd._over({"over": False}) == "")

# --- global CLAUDE.md: measured read-only, rendered as a distinct every-project line ---
_gcm = lambda present, over=False: rd.render({"project": "p", "session": "s", "scope": {}, "entries": [],
    "budget": {"global_claude_md": {"present": present, "tokens": 900, "over": over}}})
check("render: global CLAUDE.md shows as its own read-only line", "global CLAUDE.md" in _gcm(True))
check("render: global CLAUDE.md line is framed read-only/every-project", "read-only" in _gcm(True))
check("render: global CLAUDE.md absent → no line (safe)", "global CLAUDE.md" not in _gcm(False))
check("render: global CLAUDE.md ⚠ is advisory ('heavy'), not the actionable 'OVER' flag",
      "heavy" in _gcm(True, over=True) and "OVER" not in _gcm(True, over=True))
# the project file keeps its DISTINCT actionable flag — the two are handled differently
check("render: project CLAUDE.md keeps the actionable OVER flag",
      "OVER" in rd.render({"project": "p", "session": "s", "scope": {}, "entries": [],
          "budget": {"claude_md": {"before": 0, "after": 0, "over": True, "budget_tokens": 4000}}}))

# --- color: opt-in + AUTO-gated (the safety property: off unless a real TTY) ---
class _TTY:    # noqa: E306
    def isatty(self): return True
class _NoTTY:  # noqa: E306
    def isatty(self): return False
check("color: --color=never wins even on a TTY", rd._color_enabled(["--color=never"], _TTY()) is False)
check("color: --color=always wins even when captured", rd._color_enabled(["--color=always"], _NoTTY()) is True)
check("color: AUTO is OFF when captured/piped (agent-relay + pipe safe)", rd._color_enabled([], _NoTTY()) is False)
check("color: _c is a no-op while disabled (default)", rd._c("x", "red") == "x" and rd._COLOR is False)

# --- budget bars: pure, ASCII-grid-safe, fill ∝ usage ---
check("bar: ~30% fills 3/10", rd._bar(30, 100, 10).count("█") == 3 and rd._bar(30, 100, 10).count("░") == 7)
check("bar: over-budget fills fully (capped)", rd._bar(150, 100, 10).count("█") == 10)
check("bar: no budget → empty (nothing to gauge)", rd._bar(5, 0) == "")
check("pct: rounds to whole percent", rd._pct(30, 120) == "25%" and rd._pct(1, 0) == "")

# --- --demo: paste-free preview record renders the full dashboard ---
_demo = rd.render(rd._demo_record())
check("demo: renders the banner", "DREAM · consolidate-memory" in _demo)
check("demo: skipped entry is self-labelled (action word shown)", "skipped" in _demo)
check("demo: no stray em-dash placeholder anywhere (the skipped-row fix)", "—" not in _demo)
check("demo: includes the network section", "NEURAL NETWORK" in _demo)

# --- robustness: a MODEL-authored record (string/None numerics, non-str tier) must not
# crash render(). The cycle record is model-authored, so numbers can arrive as "6183"/null
# and a field can be the wrong type; every model->presentation boundary coerces via _num/_clean. ---
_gnarly = {"project": "p", "session": "s", "scope": {},
           "entries": [{"action": "added", "tier": 1, "store": "repo", "scope": "user-global",
                        "name": "x", "reason": "", "citation": ""}],
           "budget": {"claude_md": {"before": "0", "after": "1", "over": False},
                      "global_claude_md": {"present": True, "tokens": "2240", "over": False}},
           "network": {"basis": "x", "trigger": "p",
                       "nodes": [{"node": "n", "trigger": True, "always_loaded_tokens": "6183",
                                  "recall_tokens": None, "facts": "12", "shared": 1}],
                       "totals": {"nodes": 1, "always_loaded_tokens": "6461",
                                  "mirror_index_tokens": "326", "recall_tokens": 0}}}
check("render: model-authored string/None numerics + non-str tier never crash render",
      isinstance(rd.render(_gnarly), str) and "NEURAL NETWORK" in rd.render(_gnarly))

# --- observability: network sub-section is guarded + rendered ---
_net = {"basis": "≈ chars/4", "node_def": "stores", "trigger": "p",
        "nodes": [{"node": "p", "trigger": True, "always_loaded_tokens": 10,
                   "recall_tokens": 20, "facts": 2, "shared": 1}],
        "totals": {"nodes": 1, "always_loaded_tokens": 10, "recall_tokens": 20}}
check("render: network section appears when present",
      "NEURAL NETWORK" in rd.render({"project": "p", "session": "s", "scope": {},
                                      "entries": [], "network": _net}))
check("render: network section absent when no block (legacy/no-op safe)",
      "NEURAL NETWORK" not in rd.render({"project": "p", "session": "s", "scope": {}, "entries": []}))

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
