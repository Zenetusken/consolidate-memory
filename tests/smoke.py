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
