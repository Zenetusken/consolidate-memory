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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", default="?")
    ap.add_argument("--self-test-ok", default="true")
    ap.add_argument("--canary-fail", default="?")
    ap.add_argument("--generated-at", default="")
    ap.add_argument("--out", required=True)
    ap.add_argument("--human-report", default="")
    a = ap.parse_args()

    raw = sys.stdin.read().strip()
    data: dict[str, Any] = {}
    if raw:
        try:
            data = json.loads(raw[raw.find("{"):])
        except (json.JSONDecodeError, ValueError):
            data = {}
    results: list[dict[str, Any]] = data.get("results", [])
    summary: dict[str, Any] = data.get("summary", {})
    st_ok = a.self_test_ok != "false"

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

    contract = {
        "schema": "dream-beta-test/result/v1",
        "generated_at": a.generated_at,
        "skill": "consolidate-memory",
        "version_under_test": a.version,
        "verdict": verdict,
        "ship_ok": verdict == "clean",
        "self_test": {
            "canary": "v0.1.19",
            "min_fail_expected": 2,
            "actual_fail": (int(a.canary_fail) if a.canary_fail.isdigit() else a.canary_fail),
            "ok": st_ok,
            "meaning": "the oracle proved it can still DETECT a frozen known-bad before this verdict was trusted",
        },
        "summary": summary,
        "actionable": actionable,
        "findings": results,
        "fix_reference": "patch by `defect_ref` — see ~/consolidate-memory-v0.1.19-defects.md and "
                         "~/.claude/dream-beta-tester/STATUS.md (fixed-vs-open table)",
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
