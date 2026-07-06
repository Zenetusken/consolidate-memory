#!/usr/bin/env python3
"""Dream beta-harness — the thin end-to-end RUNNER (SPEC §5, scripts-only default).

Wires the three deterministic core tools into one command per the spec's run flow:

    pre-flight ─▶ snapshot ─▶ oracle ─▶ (fresh rendered surface) ─▶ render ─▶ diff + offer-restore

This is the lean spine the build plan keeps for the CORE: it does NOT spawn the judgment
subagent (P4) and it does NOT run a full mutating dream (P5 / full-judgment is opt-in and
deferred). What it DOES do, on the critical path, is the one spine responsibility the gate
forbids deferring into the subagent — the §5.5 cheap, deterministic re-verification of every
oracle FAIL against a FRESHLY-captured rendered skill surface (passed to the renderer's
``--rendered`` so a quote that no longer matches is downgraded out of the confirmed group).

Flow (SPEC §5):
  1. **Pre-flight** — resolve the target repo (absolute), the Claude-Code slug + memory store,
     and discover the consolidate-memory scripts dir VERSION-AWARE (env → ``--skill`` →
     plugin-cache/dev glob, max version). Read the skill version for the report stamp. The ONE
     hard error is "skill scripts not found" (exit 2); an absent store is a valid clean outcome.
  2. **Snapshot** (``snapshot.py``) — content-hash the memory store + the repo's three
     always-loaded docs + the marker to ``reports/.snap-<ts>/`` (the BEFORE image).
  3. **Oracle** (``beta_checks.py --json``) — run the deterministic invariant families in a CLEAN
     child process pinned to the repo (it itself drives the read-only skill scripts). The repo is
     passed POSITIONALLY downstream (the D1/D2 contamination fix lives inside the oracle).
  4. **Fresh rendered surface** — INDEPENDENTLY re-capture the skill's human ``memory_status``
     report + ``--triage`` (the surfaces the rendered-quote re-grep asserts against). This is the
     measure-don't-assert step: we do NOT trust the oracle's own captured quote; we re-verify it
     against a surface we captured ourselves, on the critical path, even in scripts-only mode.
  5. **Render** (``render_beta_report.py``) — emit ``reports/<slug>__<cmver>__<ts>.md``: dashboard
     (verbatim, when a full-dream supplies one — deferred here), the 2a-VERIFIED / 2a-FLAGGED
     split, the cross-version RUN DELTA (auto-discovered prior report), and the version-stamped,
     coverage-qualified footer. The renderer re-greps each 2a-VERIFIED quote against the fresh
     surface from step 4.
  6. **Diff + offer-restore** — diff the BEFORE snapshot against the LIVE store (in scripts-only
     mode no mutating dream ran, so this verifies "no mutation occurred"; the apparatus is built
     now for the full-dream path + to catch an out-of-band mutation). Default-RESTORE in ``--test``
     (a beta-test leaves no trace); ``--real`` / ``--keep`` retains any writes.

Design choices (each load-bearing):
  * **Subprocess the child tools, import only their PURE helpers.** Each tool keeps its own
    exit-code contract (oracle: 2=scripts-not-found / 1=FAIL / 0=clean; renderer: 1=a confirmed
    2a-VERIFIED defect) and its own clean process — no ``argv`` / ``sys.exit`` entanglement. The
    runner imports ``beta_checks`` + ``snapshot`` ONLY for the slug / store / version-aware
    discovery / snapshot-diff-restore helpers, so there is a single source of truth for those and
    no re-derivation drift (the slug rule especially — see claude-code-memory-is-slug-scoped).
  * **The re-verification surface is captured FRESH here**, not reused from the oracle — that is
    the whole point of a re-grep (the oracle is a hypothesis too; the prototype shipped 3
    confident-wrong FAILs on clean data). It stays on the critical path in scripts-only mode.
  * **Scratch files live in the harness's own ``reports/.snap-<ts>/`` (or the system tmpdir)**,
    NEVER the project slug dir (which holds live session transcripts) — the P-5 snapshot-contract
    lesson. Every scratch file is unlinked in a ``finally``.

This is CONSUMER / beta-tester tooling. It lives as its own plugin
(``plugins/dream-beta-tester/``) and NEVER patches the skill it tests. Pure stdlib.

Usage:
    python3 run_beta.py [--repo DIR] [--store DIR] [--skill DIR]
                        [--test | --real] [--keep] [--reports-dir DIR]
                        [--no-restore] [--json] [-v]

      --repo DIR       the repo whose dream is beta-tested (default: cwd) — sets the slug.
      --store DIR      memory store dir (default: ~/.claude/projects/<slug>/memory).
      --skill DIR      consolidate-memory scripts dir (default: discovered, version-max).
      --test           pure beta-test: restore the store to its pre-run state afterward (DEFAULT).
      --real / --keep  retain any writes (no restore) — for an opt-in real consolidation.
      --no-restore     do not restore even in --test (inspect the post-run state); same as --keep.
      --reports-dir D  where reports + snapshots live (default: <this script>/reports).
      --json           emit a structured run summary as JSON (in addition to writing the report).
      -v/--verbose     stream the child tools' human output too.

Exit code: 1 if the run surfaced a CONFIRMED defect (a 2a-VERIFIED finding — the renderer's exit
code is authoritative), else 0. A pre-flight failure (skill not found / a child tool crash) → 2.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# The harness's own dir — the three core tools live here next to us.
_HARNESS_ROOT = Path(__file__).resolve().parent
if str(_HARNESS_ROOT) not in sys.path:
    sys.path.insert(0, str(_HARNESS_ROOT))

# Import ONLY the pure helpers (no main()) so the slug / store / discovery / snapshot apparatus has
# a single source of truth. A failure here is a hard environment error (the tools must be present).
import beta_checks as _bc  # noqa: E402  # pyright: ignore[reportMissingImports]  (runtime sibling import via sys.path)
import snapshot as _snap  # noqa: E402  # pyright: ignore[reportMissingImports]

_ORACLE = _HARNESS_ROOT / "beta_checks.py"
_RENDERER = _HARNESS_ROOT / "render_beta_report.py"
_SNAPSHOT = _HARNESS_ROOT / "snapshot.py"  # documented sibling; we use the imported helpers directly


# ─────────────────────────────── pre-flight ───────────────────────────────


@dataclass
class PreFlight:
    """The resolved run context — repo / slug / store / skill binding + version, for the run."""

    repo: Path
    slug: str
    store: Path
    store_present: bool
    skill: Path
    skill_version: str


def preflight(repo_arg: str, store_arg: str | None, skill_arg: str | None) -> PreFlight:
    """Resolve the repo + slug + store, and discover the skill scripts VERSION-AWARE.

    Raises SystemExit(2) — the ONE hard error — only when the consolidate-memory scripts can't be
    located at all (env → ``--skill`` → the broadened plugin-cache/dev glob, max version, all miss).
    An absent store is NOT an error: it is a valid never-dreamed-repo clean outcome carried through
    as ``store_present=False`` (the oracle + snapshot both treat it first-class).
    """
    repo = Path(repo_arg).expanduser().resolve()
    skill = _bc.discover_skill(skill_arg)
    if skill is None:
        print(
            "ERROR: could not locate consolidate-memory scripts "
            "(set $CONSOLIDATE_MEMORY_SCRIPTS, pass --skill, or install the plugin)",
            file=sys.stderr,
        )
        raise SystemExit(2)
    skill_version = _bc._skill_version(skill)
    store = Path(store_arg).expanduser().resolve() if store_arg else _bc.default_store(repo)
    return PreFlight(
        repo=repo,
        slug=_bc.slug_for(repo),
        store=store,
        store_present=store.is_dir(),
        skill=skill,
        skill_version=skill_version,
    )


# ─────────────────────────────── child-tool drivers ───────────────────────────────


def _run(cmd: list[str], *, capture: bool, stream: bool) -> tuple[int, str, str]:
    """Run a child tool. Returns (returncode, stdout, stderr). When ``stream`` and not ``capture``,
    the child's output goes straight to our stdout/stderr (the ``-v`` path); otherwise it is captured.
    Never raises on a non-zero exit — the caller decides what a failure means."""
    if capture:
        cap = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if stream:
            if cap.stdout:
                sys.stdout.write(cap.stdout)
            if cap.stderr:
                sys.stderr.write(cap.stderr)
        return cap.returncode, cap.stdout or "", cap.stderr or ""
    inherited = subprocess.run(cmd, check=False)  # output goes straight to our stdio
    return inherited.returncode, "", ""


def run_oracle(pf: PreFlight, oracle_json_path: Path, *, stream: bool) -> tuple[int, dict[str, Any]]:
    """Run ``beta_checks.py --json`` in a clean child process pinned to the repo/store/skill, persist
    its JSON to ``oracle_json_path`` (durable BEFORE the renderer runs), and return (rc, payload).

    The oracle's exit code is preserved (2 = scripts-not-found, 1 = a FAIL, 0 = clean). A non-2 exit
    with unparseable JSON is surfaced as a hard runner error — the renderer needs the payload.
    """
    cmd = [
        sys.executable,
        str(_ORACLE),
        "--repo", str(pf.repo),
        "--store", str(pf.store),
        "--skill", str(pf.skill),
        "--json",
    ]
    rc, stdout, stderr = _run(cmd, capture=True, stream=False)
    if stream and stderr:
        sys.stderr.write(stderr)
    if rc == 2:
        # scripts-not-found from inside the oracle (shouldn't happen — pre-flight found them — but honor it)
        sys.stderr.write(stderr or "oracle: consolidate-memory scripts not found\n")
        raise SystemExit(2)
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as e:
        sys.stderr.write(f"ERROR: oracle did not emit valid JSON (rc={rc}): {e}\n")
        if stderr:
            sys.stderr.write(stderr)
        raise SystemExit(2) from e
    oracle_json_path.write_text(stdout, encoding="utf-8")
    return rc, payload


def capture_rendered_surface(pf: PreFlight) -> str:
    """INDEPENDENTLY re-capture the skill's rendered surfaces for the §5.5 quote re-verification.

    Concatenates the human ``memory_status`` report and its ``--triage`` view (``--no-color
    --ascii``), driven from a CLEAN subprocess with the repo passed POSITIONALLY (cwd=repo as a
    backstop). The renderer re-greps each 2a-VERIFIED quote against THIS text — captured here, by us,
    not reused from the oracle — so a confirmed defect must survive a fresh observation of the skill's
    own words. Best-effort: a failed capture yields the partial text we got (the renderer then can't
    re-verify and discloses that in the footer); it never aborts the run.
    """
    py = sys.executable
    repo_arg = str(pf.repo)
    parts: list[str] = []
    for extra in (["--no-color", "--ascii"], ["--triage", "--no-color", "--ascii"]):
        cmd = [py, str(pf.skill / "memory_status.py"), repo_arg, *extra]
        try:
            out = subprocess.run(cmd, cwd=pf.repo, capture_output=True, text=True, timeout=120, check=False)
        except (OSError, subprocess.SubprocessError):
            continue
        if out.stdout:
            parts.append(out.stdout)
    return "\n".join(parts)


def run_renderer(
    pf: PreFlight,
    oracle_json_path: Path,
    rendered_path: Path | None,
    disposition_json_path: Path | None,
    reports_dir: Path,
    *,
    stream: bool,
) -> tuple[int, str]:
    """Render the report via ``render_beta_report.py --write`` and return (rc, report_path).

    Passes the oracle JSON, the freshly-captured rendered surface (for the on-critical-path quote
    re-grep), and a snapshot-disposition JSON for the footer. The prior report is AUTO-DISCOVERED by
    the renderer from ``--reports-dir`` (same slug, older version) — the cross-version RUN DELTA. The
    renderer's exit code (1 iff a 2a-VERIFIED confirmed defect shipped) is the run's authoritative
    verdict. ``--write`` prints the written report path to stdout.
    """
    cmd = [
        sys.executable,
        str(_RENDERER),
        "--oracle", str(oracle_json_path),
        "--reports-dir", str(reports_dir),
        "--write",
    ]
    if rendered_path is not None:
        cmd += ["--rendered", str(rendered_path)]
    if disposition_json_path is not None:
        cmd += ["--snapshot", str(disposition_json_path)]
    rc, stdout, stderr = _run(cmd, capture=True, stream=False)
    if stderr and stream:
        sys.stderr.write(stderr)
    report_path = stdout.strip().splitlines()[-1].strip() if stdout.strip() else ""
    if not report_path:
        sys.stderr.write(f"ERROR: renderer wrote no report path (rc={rc})\n")
        if stderr:
            sys.stderr.write(stderr)
        raise SystemExit(2)
    return rc, report_path


# ─────────────────────────────── snapshot diff + disposition ───────────────────────────────


def diff_against_live(before: "_snap.Manifest", pf: PreFlight) -> "_snap.DiffReport":
    """Diff the BEFORE snapshot against the current LIVE store/docs (no second snapshot).

    In scripts-only mode no mutating dream ran, so this should report zero changes — it verifies
    "no mutation occurred" (a coverage NOTE, not full signal; the full claim-vs-reality signal needs
    the full-dream path). It still catches any out-of-band mutation, and is the apparatus the
    full-dream path reuses verbatim.
    """
    live = _snap._live_manifest(pf.repo, pf.store)
    return _snap.diff(before, live, against_live=True)


def build_disposition(report: "_snap.DiffReport", restored: bool, restore_skipped_reason: str | None) -> dict[str, Any]:
    """A footer-ready snapshot/restore disposition dict for the renderer's ``--snapshot``.

    Mirrors the renderer's ``_snapshot_disposition`` contract: a ``disposition`` note + a ``changed``
    list (the files the run actually mutated). Discloses the scripts-only coverage limit and whether
    the store was restored.
    """
    changed = [f"{d.origin}/{d.name}" for d in report.deltas]
    unexpected = list(report.unexpected_store_mutations)
    if restored:
        disp = "store restored to pre-run state (default for a --test run)"
    elif restore_skipped_reason:
        disp = f"writes RETAINED ({restore_skipped_reason})"
    else:
        disp = "writes RETAINED (no restore)"
    note = (
        f"{disp}; before→live diff: {report.summary['total']} change(s), "
        f"{report.summary['unexpected_store']} unexpected store mutation(s)"
        + (f" [UNEXPECTED: {', '.join(unexpected)}]" if unexpected else "")
        + " — scripts-only mode ran no mutating dream, so this leg verifies 'no mutation occurred'"
    )
    return {"disposition": note, "changed": changed}


# ─────────────────────────────── main ───────────────────────────────


def _print_human_summary(
    pf: PreFlight,
    oracle: dict[str, Any],
    diff_report: "_snap.DiffReport",
    report_path: str,
    restored: bool,
    confirmed_defect: bool,
) -> None:
    s = oracle.get("summary", {})
    print(f"\n  DREAM BETA-TEST · {pf.repo.name}  (consolidate-memory v{pf.skill_version})")
    print(f"  repo:   {pf.repo}")
    print(f"  store:  {pf.store}" + ("" if pf.store_present else "   [ABSENT — never-dreamed repo, clean]"))
    print(f"  skill:  {pf.skill}")
    print(
        f"  oracle: {s.get('fail', 0)} FAIL · {s.get('warn', 0)} WARN · {s.get('pass', 0)} PASS · "
        f"{s.get('skip', 0)} SKIP  ({len(oracle.get('families_ran', []))} families ran, "
        f"{len(oracle.get('families_skipped', []))} skipped)"
    )
    ds = diff_report.summary
    print(
        f"  diff:   {ds['total']} change(s) before→live · {ds['unexpected_store']} unexpected store "
        f"mutation(s) · marker {'ADVANCED' if diff_report.marker.advanced else 'unchanged'}"
    )
    print(f"  restore:{' DONE (pre-run state)' if restored else ' SKIPPED (writes retained)'}")
    verdict = (
        "CONFIRMED defect(s) this run (2a-VERIFIED)"
        if confirmed_defect
        else ("CLEAN — never-dreamed repo" if oracle.get("store_absent") else "CLEAN of confirmed defects")
    )
    print(f"  verdict:{verdict}")
    print(f"  report: {report_path}\n")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Thin end-to-end runner for the dream beta-harness (SPEC §5, scripts-only default)."
    )
    ap.add_argument("--repo", default=os.getcwd(), help="repo whose dream is beta-tested (default: cwd)")
    ap.add_argument("--store", default=None, help="memory store dir (default: ~/.claude/projects/<slug>/memory)")
    ap.add_argument("--skill", default=None, help="consolidate-memory scripts dir (default: discovered, version-max)")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--test", action="store_true", help="pure beta-test: restore the store afterward (DEFAULT)")
    mode.add_argument("--real", action="store_true", help="retain writes (no restore) — opt-in real consolidation")
    ap.add_argument("--keep", action="store_true", help="retain writes (alias for --real's no-restore)")
    ap.add_argument("--no-restore", action="store_true", help="do not restore even in --test (inspect post-run state)")
    ap.add_argument("--reports-dir", default=None, help="reports + snapshots dir (default: <script dir>/reports)")
    ap.add_argument("--json", action="store_true", help="emit a structured run summary as JSON")
    ap.add_argument("-v", "--verbose", action="store_true", help="stream the child tools' output too")
    a = ap.parse_args(argv)

    # restore default: ON in --test (the default), OFF when --real/--keep/--no-restore is given.
    do_restore = not (a.real or a.keep or a.no_restore)

    # Reports default to a STABLE user dir (not the script/plugin dir): survives plugin updates and
    # gives the orchestrator a fixed `latest.json` path. Override via --reports-dir or $DREAM_BETA_REPORTS.
    _default_reports = Path(os.environ.get("DREAM_BETA_REPORTS") or (Path.home() / ".dream-beta-test" / "reports"))
    reports_dir = Path(a.reports_dir).expanduser().resolve() if a.reports_dir else _default_reports
    reports_dir.mkdir(parents=True, exist_ok=True)

    # ── 1. pre-flight ──
    pf = preflight(a.repo, a.store, a.skill)

    # scratch files: the harness tmpdir (NEVER the project slug dir). Unlinked in finally.
    scratch: list[Path] = []

    def _scratch(suffix: str) -> Path:
        fd, p = tempfile.mkstemp(prefix="cm-beta-run", suffix=suffix)
        os.close(fd)
        path = Path(p)
        scratch.append(path)
        return path

    confirmed_defect = False
    try:
        # ── 2. snapshot (BEFORE image) ──
        # Snapshots are written under reports_dir/.snap-<ts>/ by snapshot.snapshot (out=None default
        # targets snapshot.REPORTS_DIR; pass an explicit out under the chosen reports_dir to honor it).
        snap_out = reports_dir / f".snap-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}"
        before = _snap.snapshot(pf.repo, pf.store, out=snap_out)

        # ── 3. oracle (clean child process, JSON persisted before render) ──
        oracle_json = _scratch(".oracle.json")
        _, oracle_payload = run_oracle(pf, oracle_json, stream=a.verbose)

        # ── 4. fresh rendered surface for the on-critical-path quote re-verification ──
        rendered_text = capture_rendered_surface(pf)
        rendered_path: Path | None = None
        if rendered_text.strip():
            rendered_path = _scratch(".rendered.txt")
            rendered_path.write_text(rendered_text, encoding="utf-8")

        # ── 6a. diff before→live (scripts-only: expect no mutation) — needed for the disposition ──
        diff_report = diff_against_live(before, pf)

        # ── 6b. offer-restore: default-restore in --test; retain on --real/--keep/--no-restore ──
        restored = False
        restore_skipped_reason: str | None = None
        if do_restore:
            plan = _snap.restore(before, pf.repo, pf.store, dry_run=False)
            restored = not plan.skipped
            if plan.skipped:
                restore_skipped_reason = f"restore had {len(plan.skipped)} skipped op(s)"
        else:
            restore_skipped_reason = "--real/--keep/--no-restore" if (a.real or a.keep or a.no_restore) else None

        disposition_json = _scratch(".disposition.json")
        disposition_json.write_text(
            json.dumps(build_disposition(diff_report, restored, restore_skipped_reason)), encoding="utf-8"
        )

        # ── 5. render → reports/<slug>__<cmver>__<ts>.md (prior report auto-discovered) ──
        rc_render, report_path = run_renderer(
            pf, oracle_json, rendered_path, disposition_json, reports_dir, stream=a.verbose
        )
        confirmed_defect = rc_render == 1

        # ── output ──
        if a.json:
            summary = {
                "repo": str(pf.repo),
                "slug": pf.slug,
                "store": str(pf.store),
                "store_present": pf.store_present,
                "skill": str(pf.skill),
                "skill_version": pf.skill_version,
                "oracle_summary": oracle_payload.get("summary", {}),
                "families_ran": oracle_payload.get("families_ran", []),
                "families_skipped": oracle_payload.get("families_skipped", []),
                "diff_summary": diff_report.summary,
                "marker_advanced": diff_report.marker.advanced,
                "unexpected_store_mutations": diff_report.unexpected_store_mutations,
                "restored": restored,
                "rendered_reverified": rendered_path is not None,
                "confirmed_defect": confirmed_defect,
                "report_path": report_path,
                "snapshot_dir": before.snapshot_dir,
            }
            print(json.dumps(summary, indent=2))
        else:
            _print_human_summary(pf, oracle_payload, diff_report, report_path, restored, confirmed_defect)
    finally:
        for p in scratch:
            try:
                p.unlink()
            except OSError:
                pass

    return 1 if confirmed_defect else 0


if __name__ == "__main__":
    sys.exit(main())
