#!/usr/bin/env python3
"""The STANDING fleet-calibration report — arc C's repeatable maintainer instrument.

READ-ONLY aggregate over the fleet's persisted dream logs (`.consolidation-log.jsonl`):
the magnitude→band distribution, index-budget utilization, usage/miss signal, demotion
windows, pressure signals, and the miss-carrying-by-band table — the evidence the
band/budget refit waits for. Prints the CURRENT numbers plus the DELTA against the frozen
2026-08-29 baseline (the standing diff: one command decides whether the accrued data yet
justifies a refit — the refit itself stays GATED; this report never refits, never writes,
never mutates a store).

Safety: aggregates only — no memory content is ever printed. Synthetic stores
(fixture/gate-repo/scratchpad/-tmp-/probe slugs) are excluded by pattern; legacy and
malformed log lines are skipped per-row (poison-pill row isolation, never a whole-batch
abort). The baseline is a frozen constant in this file — the fleet's numbers as of the
first measurement; compare against it, don't edit it.

Usage:  python3 calibration_report.py [--json]
Exit:   0 clean · 2 usage error (an unknown flag is a usage error, never a silent ignore)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

# Frozen reference — the FIRST fleet measurement (2026-08-29). Compare against it; the
# standing-diff deltas accrue until the miss signal justifies the band/budget review.
BASELINE: dict[str, Any] = {
    "records": 54,
    "stores": {"consolidate-memory": 24, "job-applicator-python": 19, "Doc-Flo": 9, "beacon": 2},
    "magnitude": {"n": 54, "bands": {"LIGHT": 5, "SUBSTANTIAL": 20, "HEAVY": 29},
                  "median": 8, "p90": 28, "max": 130},
    "verification": {"confirmed": 384, "corrected": 60, "unverifiable": 3},
    "index": {"n": 54, "median": 1387, "p90": 2761, "max": 6481,
              "over_budget": 19, "over_ceiling": 1},
    "usage": {"windows": 5, "reads": 6, "facts_read": 5, "misses": 0},
    "demotion": {"windows_observed": 10, "eligible": 2, "surfaced": 2, "struck": 0},
    "pressure": {"recurring_workflow_records": 10, "remediation_required": 9, "prune_pressure": 20},
    "miss_by_band": {"LIGHT": 0, "SUBSTANTIAL": 0, "HEAVY": 0},
}

# Synthetic/scratch store slugs to exclude (measured inventory 2026-08-29).
_EXCLUDE_RE = re.compile(r"-tmp-|scratchpad|gate-repo|repro-|fixture-test|--dream-beta-test|probe-other",
                         re.IGNORECASE)

_INDEX_BUDGET = 1500
_INDEX_CEILING = 3840


def _get(rec: dict[str, Any], *path: str) -> Any:
    cur: Any = rec
    for p in path:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(p)
    return cur


def _store_name(slug: str) -> str:
    """-home-you-project-consolidate-memory → consolidate-memory (tail after -project-)."""
    parts = re.split(r"-project-", slug)
    return parts[-1] if len(parts) > 1 else slug


def discover_stores(base: Path) -> dict[str, list[dict[str, Any]]]:
    """{(display name): [parsed records]} over REAL stores only — excluded-slug stores and
    log-less stores skipped; malformed lines skipped per-row."""
    out: dict[str, list[dict[str, Any]]] = {}
    for proj in sorted(base.glob("*/memory")):
        slug = proj.parent.name
        if _EXCLUDE_RE.search(slug):
            continue
        log = proj / ".consolidation-log.jsonl"
        if not log.exists():
            continue
        recs: list[dict[str, Any]] = []
        for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue  # one malformed row must not abort the batch
            if isinstance(r, dict):
                recs.append(r)
        if recs:
            out[_store_name(slug)] = recs
    return out


def _pct(n: int, d: int) -> str:
    return f"{100 * n / max(1, d):.0f}%"


def aggregate(stores: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    records = [r for recs in stores.values() for r in recs]
    per_store = {name: len(recs) for name, recs in sorted(stores.items())}

    bands = {"LIGHT": 0, "SUBSTANTIAL": 0, "HEAVY": 0}
    mags: list[int] = []
    miss_by_band = {"LIGHT": 0, "SUBSTANTIAL": 0, "HEAVY": 0}
    conf = corr = unv = 0
    afters: list[int] = []
    windows = reads = facts_read = misses = 0
    dwin = delig = dsurf = dstruck = 0
    drecs = rem_required = pp = 0
    for r in records:
        gc = _get(r, "scope", "git_commits")
        sc = _get(r, "scope", "session_candidates")
        if isinstance(gc, int) and isinstance(sc, int):
            m = gc + sc
            mags.append(m)
            band = "LIGHT" if m <= 2 else ("SUBSTANTIAL" if m <= 7 else "HEAVY")
            bands[band] += 1
            if (_get(r, "usage") or {}).get("misses"):
                miss_by_band[band] += 1
        v = _get(r, "verification") or {}
        conf += v.get("confirmed", 0) or 0
        corr += v.get("corrected", 0) or 0
        unv += v.get("unverifiable", 0) or 0
        a = _get(r, "budget", "index", "after_tokens")
        if isinstance(a, int) and a > 0:
            afters.append(a)
        u = _get(r, "usage") or {}
        windows += 1 if u.get("window") else 0
        reads += u.get("reads", 0) or 0
        facts_read += u.get("facts_read", 0) or 0
        misses += len(u.get("misses") or [])
        d = _get(r, "demotion") or {}
        dwin += d.get("windows_observed", 0) or 0
        delig += d.get("eligible", 0) or 0
        dsurf += len(d.get("surfaced") or [])
        dstruck += len(d.get("struck") or [])
        if (_get(r, "distill") or {}).get("n_recurring", 0):
            drecs += 1
        if (_get(r, "remediation") or {}).get("required"):
            rem_required += 1
        if (_get(r, "rigor") or {}).get("prune_pressure") is True:
            pp += 1

    s_mags = sorted(mags) if mags else [0]
    s_aft = sorted(afters) if afters else [0]
    _p90m = s_mags[min(int(0.9 * len(s_mags)), len(s_mags) - 1)] if s_mags else 0
    _p90a = s_aft[min(int(0.9 * len(s_aft)), len(s_aft) - 1)] if s_aft else 0
    return {
        "records": len(records),
        "stores": per_store,
        "magnitude": {"n": len(mags), "bands": bands,
                      "median": s_mags[len(s_mags) // 2],
                      "p90": _p90m,
                      "max": s_mags[-1]},
        "verification": {"confirmed": conf, "corrected": corr, "unverifiable": unv},
        "index": {"n": len(s_aft), "median": s_aft[len(s_aft) // 2],
                  "p90": _p90a,
                  "max": s_aft[-1],
                  "over_budget": sum(1 for a in s_aft if a > _INDEX_BUDGET),
                  "over_ceiling": sum(1 for a in s_aft if a > _INDEX_CEILING)},
        "usage": {"windows": windows, "reads": reads, "facts_read": facts_read, "misses": misses},
        "demotion": {"windows_observed": dwin, "eligible": delig, "surfaced": dsurf, "struck": dstruck},
        "pressure": {"recurring_workflow_records": drecs, "remediation_required": rem_required,
                     "prune_pressure": pp},
        "miss_by_band": miss_by_band,
    }


def ledger_stat(base: Path) -> dict[str, Any]:
    lp = base / ".fleet-usage.jsonl"
    if not lp.exists():
        return {"lines": 0, "stale_since": "(absent)"}
    lines = sum(1 for _ in lp.read_text(encoding="utf-8", errors="replace").splitlines())
    return {"lines": lines, "stale_since": "(on disk)"}


def delta(cur: dict[str, Any], ref: dict[str, Any]) -> dict[str, Any]:
    """Standing diff: only the keys whose numbers MOVED since the frozen baseline."""
    out: dict[str, Any] = {}
    for k in sorted(set(cur) | set(ref)):
        c, r = cur.get(k), ref.get(k)
        if isinstance(c, dict) and isinstance(r, dict):
            sub = delta(c, r)
            if sub:
                out[k] = sub
        elif c != r:
            out[k] = {"baseline": r, "current": c}
    return out


def _human(cur: dict[str, Any], d: dict[str, Any], stores: dict[str, list[dict[str, Any]]],
           ledger: dict[str, Any]) -> None:
    m = cur["magnitude"]
    print("  CALIBRATION REPORT · fleet dream-log aggregate (read-only; refit stays gated)")
    print(f"  stores ({len(stores)}): " + ", ".join(f"{n}={len(r)}" for n, r in sorted(stores.items())))
    print(f"  records: {cur['records']}   (baseline {BASELINE['records']})")
    print(f"  magnitude: LIGHT {m['bands']['LIGHT']} ({_pct(m['bands']['LIGHT'], m['n'])}) · "
          f"SUBSTANTIAL {m['bands']['SUBSTANTIAL']} ({_pct(m['bands']['SUBSTANTIAL'], m['n'])}) · "
          f"HEAVY {m['bands']['HEAVY']} ({_pct(m['bands']['HEAVY'], m['n'])}) · median {m['median']} · "
          f"p90 {m['p90']} · max {m['max']}")
    i = cur["index"]
    print(f"  index: n={i['n']} · median {i['median']} (budget {_INDEX_BUDGET}) · "
          f"over-budget {i['over_budget']}/{i['n']} · over-ceiling {i['over_ceiling']}/{i['n']} · max {i['max']}")
    u = cur["usage"]
    print(f"  usage: windows {u['windows']}/{cur['records']} · reads {u['reads']} · "
          f"facts_read {u['facts_read']} · misses {u['misses']}")
    dm = cur["demotion"]
    print(f"  demotion: windows {dm['windows_observed']} · eligible {dm['eligible']} · "
          f"surfaced {dm['surfaced']} · struck {dm['struck']}")
    print(f"  miss_by_band: {cur['miss_by_band']} · ledger: {ledger['lines']} line(s), {ledger['stale_since']}")
    if u["misses"] == 0:
        print("  REFIT GATE: misses=0 — the band/budget refit signal has NOT arrived; keep waiting.")
    else:
        print(f"  REFIT GATE: {u['misses']} miss(es) accrued — the evidence gate has data; "
              "schedule the calibration review.")
    if d:
        print("  DELTA vs the 2026-08-29 baseline:")
        print(json.dumps(d, indent=2))
    else:
        print("  DELTA vs baseline: none — the fleet has not moved since the first measurement.")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Standing fleet-calibration report (read-only).")
    ap.add_argument("--json", action="store_true", help="emit structured JSON (current + baseline + delta)")
    a = ap.parse_args(argv)

    base = Path.home() / ".claude" / "projects"
    stores = discover_stores(base)
    cur = aggregate(stores)
    ledger = ledger_stat(Path.home() / ".claude" / "memory")
    d = delta(cur, BASELINE)

    if a.json:
        print(json.dumps({"current": cur, "baseline": BASELINE, "delta": d, "ledger": ledger,
                          "refit_gate": "wait" if cur["usage"]["misses"] == 0 else "review"},
                         indent=2))
    else:
        _human(cur, d, stores, ledger)
    return 0


if __name__ == "__main__":
    sys.exit(main())
