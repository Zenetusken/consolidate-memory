#!/usr/bin/env python3
"""Emit the DETERMINISTIC result contract (`reports/latest.json`) the dream-plugin orchestrator
reads to self-heal a consolidate-memory release.

Reads a `beta_checks.py --json` oracle run on stdin + gate metadata as args, computes a single
`verdict`, extracts the FAILs as a machine-actionable list (each tied to a catalog `defect_ref`),
and writes a stable-path JSON. Prints the verdict to stdout; per-finding detail to stderr.

The orchestrator loop:
    run ci_check.sh  →  read reports/latest.json
    verdict == "clean"          → ship
    verdict == "regression"     → for each `actionable` finding: patch by `defect_ref`/`evidence`,
                                  re-run, re-read, repeat until clean
    verdict == "selftest_broken"→ the HARNESS is broken (not the release); escalate, do not patch the skill
    verdict == "harness_error"  → oracle produced no verdict; escalate

Usage:
    emit_result.py --version V --self-test-ok true|false --canary-fail N \\
                   --generated-at ISO --out PATH [--human-report PATH]   < oracle.json
A self-test-broken run passes no oracle on stdin (empty) — call with --self-test-ok false.
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any

_ACTIONABLE_FIELDS = ("id", "defect_ref", "severity", "title", "expected", "actual", "evidence", "site", "basis")


def _last_json_object(txt: str) -> dict[str, Any] | None:
    """The LAST TOP-LEVEL balanced {...} object in `txt`, or None — a small inline copy of
    beta_checks.py's `_last_json_object` (v0.1.7 Gate-2b-class fix, ported here at B2/Track B: the
    original `raw.find("{")` FIRST-brace parse is exactly the naive shape beta_checks.py's own
    docstring rejects — a stray leading `{` in a WARN title or log line would mis-land the parse).
    The two scripts deliberately share no import path (emit_result runs standalone, piped oracle
    JSON on stdin), so this is a small duplicated implementation, not a refactor into a shared module."""
    best: dict[str, Any] | None = None
    i = 0
    n = len(txt)
    while i < n:
        if txt[i] != "{":
            i += 1
            continue
        depth = 0
        in_str = False
        esc = False
        end = -1
        for j in range(i, n):
            ch = txt[j]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end = j
                    break
        if end == -1:
            i += 1
            continue
        try:
            obj = json.loads(txt[i : end + 1])
        except json.JSONDecodeError:
            obj = None
        if isinstance(obj, dict):
            best = obj
        i = end + 1
    return best


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", default="?")
    ap.add_argument("--self-test-ok", default="true")
    ap.add_argument("--canary-fail", default="?")
    ap.add_argument("--expected-ids", default="")   # v0.1.7/B6: comma-joined, additive — id-match self-test
    ap.add_argument("--detected-ids", default="")   # comma-joined FAIL ids the canary run actually produced
    ap.add_argument("--generated-at", default="")
    ap.add_argument("--out", required=True)
    ap.add_argument("--human-report", default="")
    a = ap.parse_args()

    raw = sys.stdin.read().strip()
    data: dict[str, Any] = _last_json_object(raw) or {} if raw else {}
    results: list[dict[str, Any]] = data.get("results", [])
    summary: dict[str, Any] = data.get("summary", {})
    # v0.1.7/B2(c): require the EXACT literal "true" — a typo/garbage/empty value now fails
    # toward distrust (selftest_broken), matching the guardrail's intent (fail-open toward "harness
    # broken" is safe; fail-open toward "harness OK" on garbage input is the wrong direction).
    st_ok = a.self_test_ok == "true"

    if not st_ok:
        verdict = "selftest_broken"
    elif not raw or not data or not results:
        verdict = "harness_error"
    elif summary.get("fail", 0) > 0:
        verdict = "regression"
    else:
        verdict = "clean"

    fails = [r for r in results if r.get("status") == "FAIL"]
    warns = [r for r in results if r.get("status") == "WARN"]
    actionable = [{k: r.get(k) for k in _ACTIONABLE_FIELDS} for r in fails]
    expected_ids = [x for x in a.expected_ids.split(",") if x]
    detected_ids = [x for x in a.detected_ids.split(",") if x]
    # Gate-2a (round 1) fixed the no-canary case: expected_ids=="" → "did not run", not a false proof.
    # Gate-2b found this was incomplete — st_ok was never checked, so the SELFTEST_BROKEN path (a
    # REAL canary that FAILED to detect) still asserted "proved detection", contradicting ok:false and
    # the verdict itself. st_ok is checked FIRST: broken beats "ran" beats "didn't run".
    if not st_ok:
        _self_test_meaning = (
            "the self-test FAILED — the oracle no longer detects the frozen known-bad BY IDENTITY "
            "(expected_ids ⊄ detected_ids); detection is BROKEN, this verdict is UNTRUSTWORTHY "
            "(do not ship on the strength of this run — see CONTRACT.md's selftest_broken guardrail)"
        )
    elif not expected_ids:
        _self_test_meaning = (
            "the self-test did not run — no canary was available to compare against (ok=true is the "
            "designed fail-open default for a MISSING canary, not a proof of detection; install-gate.sh "
            "populates the canary to enable the real watch-the-watcher check)"
        )
    else:
        _self_test_meaning = (
            "the oracle proved it can still DETECT the frozen known-bad BY IDENTITY "
            "(expected_ids ⊆ detected_ids), not merely a spurious FAIL count, before this verdict was trusted"
        )

    contract = {
        "schema": "dream-beta-test/result/v1",
        "generated_at": a.generated_at,
        "skill": "consolidate-memory",
        "version_under_test": a.version,
        "verdict": verdict,
        "ship_ok": verdict == "clean",
        "self_test": {
            "canary": "v0.1.19",
            "min_fail_expected": 2,   # v0.1.7/B6: now a reported DETAIL, not the gate — see expected/detected_ids
            "actual_fail": (int(a.canary_fail) if a.canary_fail.isdigit() else a.canary_fail),
            "expected_ids": expected_ids,
            "detected_ids": detected_ids,
            "ok": st_ok,
            "meaning": _self_test_meaning,
        },
        "summary": summary,
        "actionable": actionable,
        "findings": results,
        "fix_reference": "patch by `defect_ref` — see the dream-beta-tester plugin's "
                         "docs/STATUS.md fixed-vs-open table",
        "novel_class_note": "this is the DETERMINISTIC gate (known-defect families only); for NEW classes run "
                            "/dream-beta-test (the judgment-lens pass) and read its markdown report",
        "human_report": a.human_report,
        "exit_code": 1 if verdict == "regression" else 0,
    }
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump(contract, fh, indent=2)
        fh.write("\n")

    print(verdict)
    for r in fails:
        sys.stderr.write(f"  FAIL {r.get('id')} ({r.get('defect_ref', '')}) — {r.get('title', '')}\n")
    for r in warns:
        sys.stderr.write(f"  warn {r.get('id')} ({r.get('defect_ref', '')})\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
