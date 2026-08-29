#!/usr/bin/env python3
"""Generate the FROZEN contaminated cycle record the gate's cycle-probe self-test feeds to the
oracle (SPEC-A §D-3): the oracle must FAIL on it BY IDENTITY — CHK-CYCLE-PROJECT (foreign
project) + CHK-CYCLE-BUDGET (foreign budget vs the live trigger node) — or the gate reports
teeth-loss.

The record is built HERMETICALLY (a temp HOME; the second repo + store never touch the real
projects dir): a small honest store is generated, the SKILL's own ``memory_status --json`` is
run on it (so the record is always current-skill-shaped), then the record is contaminated —
``budget.index.after_tokens = 9999`` (Δ ≫ cycle_identity's ±max(50, 10%) tolerance against any
plausible fixture trigger node) — stamped (``_probe`` sentinel, verified by beta_checks before
use), and frozen to ``$DREAM_BETA_STATE/cycle-probe.json``.

Usage:  python3 make_cycle_probe.py [--skill DIR] [--out PATH]
        make_cycle_probe.py --help   prints this and exits — creates nothing
The fixture README documents regeneration; install-gate.sh runs it once, like the canary graft.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from pathlib import Path

CONTAMINANT_AFTER_TOKENS = 9999   # SPEC-A D-3: far beyond max(50, 0.10×ntok) for any real fixture
PROBE_SENTINEL = "cycle-probe-frozen-v1"


def _discover_skill(skill: str | None) -> Path | None:
    """Locate the consolidate-memory scripts dir: explicit flag → env → plugin cache (version-max).

    Version-ordered, NOT lexicographic — a string sort picks 0.1.9 over 0.1.19."""
    if skill:
        p = Path(skill).expanduser().resolve()
        return p if p.is_dir() else None
    env = os.environ.get("CONSOLIDATE_MEMORY_SCRIPTS")
    if env:
        p = Path(env).expanduser().resolve()
        return p if p.is_dir() else None
    cache = Path.home() / ".claude" / "plugins" / "cache"

    def _ver_key(p: Path) -> "tuple[int, ...]":
        parts = [x for x in p.parent.name.split(".") if x.isdigit()]
        return tuple(int(x) for x in parts) or (-1,)

    hits = list(cache.glob("*/consolidate-memory/*/scripts"))
    return max(hits, key=_ver_key) if hits else None


def main() -> int:
    ap = argparse.ArgumentParser(
        description=(__doc__ or "Generate the FROZEN contaminated cycle-probe record.").splitlines()[0])
    ap.add_argument("--skill", default=None, help="consolidate-memory scripts dir (default: discovered)")
    ap.add_argument("--out", default=None,
                    help="output path (default: $DREAM_BETA_STATE/cycle-probe.json, else "
                         "~/.dream-beta-test/cycle-probe.json)")
    a = ap.parse_args()

    skill = _discover_skill(a.skill)
    if skill is None:
        print("ERROR: could not locate consolidate-memory scripts "
              "(pass --skill or set $CONSOLIDATE_MEMORY_SCRIPTS)", file=sys.stderr)
        return 2

    state = Path(os.environ.get("DREAM_BETA_STATE", str(Path.home() / ".dream-beta-test")))
    out = Path(a.out).expanduser().resolve() if a.out else state / "cycle-probe.json"

    # Hermetic: the probe-other repo + store live under a temp HOME, discarded after the record is
    # captured — a regeneration must NEVER drop a synthetic store into the real projects dir.
    with tempfile.TemporaryDirectory(prefix="cm-cycle-probe-") as td:
        home = Path(td) / "home"
        home.mkdir()
        repo = Path(td) / "probe-other"
        repo.mkdir()
        (repo / "README.md").write_text(
            "# probe-other\n\nDummy second project — its cycle record is the FROZEN contaminant "
            "the gate's cycle-probe self-test feeds the oracle.\n", encoding="utf-8")
        # A small honest store at the REAL slug (the M3 rule over the temp repo's resolved path —
        # a hardcoded slug names a store memory_status never resolves, making the record
        # store-absent-shaped; measured by the mechanics review).
        store = home / ".claude" / "projects" / re.sub(r"[^A-Za-z0-9]", "-", str(repo.resolve())) / "memory"
        store.mkdir(parents=True)
        (store / "probe-other-fact.md").write_text(
            "---\nname: probe-other-fact\ndescription: the foreign project's honest fact\n"
            "metadata:\n  node_type: memory\n  type: project\n---\n\n"
            "Authored in probe-other — this record must NEVER match the gate-repo.\n",
            encoding="utf-8")
        (store / "MEMORY.md").write_text(
            "# probe-other index\n\n"
            "- [probe-other-fact](probe-other-fact.md) — the foreign project's index hook\n",
            encoding="utf-8")
        (store / ".consolidation-state.json").write_text(json.dumps({
            "commit": "probeothercommit00000000000000000000000",
            "timestamp": "2026-08-28T00:00:00Z"}), encoding="utf-8")

        env = dict(os.environ, HOME=str(home))
        env.pop("CLAUDE_PLUGIN_ROOT", None)
        import subprocess
        r = subprocess.run([sys.executable, str(skill / "memory_status.py"), str(repo), "--json"],
                           capture_output=True, text=True, env=env, timeout=120)
        if r.returncode != 0:
            print(f"ERROR: memory_status --json failed (rc={r.returncode}): {r.stderr.strip()[:300]}",
                  file=sys.stderr)
            return 1
        try:
            record = json.loads(r.stdout)
        except json.JSONDecodeError as e:
            print(f"ERROR: seed was not JSON: {e}", file=sys.stderr)
            return 1

        # The contaminant: a foreign budget far beyond tolerance, and the probe stamp the oracle
        # verifies before trusting the record.
        record.setdefault("budget", {}).setdefault("index", {})["after_tokens"] = CONTAMINANT_AFTER_TOKENS
        record["_probe"] = {"probe": True, "sentinel": PROBE_SENTINEL}

    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.name + f".tmp{os.getpid()}")
    tmp.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    os.chmod(tmp, 0o600)
    tmp.replace(out)   # atomic on POSIX
    print(out)
    print(f"  project={record.get('project')!r} · after_tokens={CONTAMINANT_AFTER_TOKENS} "
          f"(Δ ≫ tolerance vs any fixture trigger) · sentinel={PROBE_SENTINEL}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
