#!/usr/bin/env python3
"""Regression arms for the three 2026-07-06 pentest findings this plugin left open.

⚠ WHY THIS FILE EXISTS. `maintainer/ci_check.sh` runs the deterministic oracle against the
**consolidate-memory** skill — it does not exercise `snapshot.py` or `beta_checks.py`. So a fix to
those files would ship with no arm that can fail, which is the defect class the parent repo keeps
paying for. These are the arms; `ci_check.sh` calls them.

⚠ EACH ARM IS A PIN WHERE IT CAN BE. Every one was measured RED against the pre-fix code and
GREEN after (see the resolution log in `security/findings-2026-09-25.md`), on a full copy, with
markers verified at 0 before measuring. F3's collision is made DETERMINISTIC by pinning
`time.time` — a same-second race left to chance would be a flake, and a flaky pin is not a pin.

Run: ``python3 maintainer/selftest_hardening.py`` → exit 0 all green, 1 on any failure.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPTS = HERE.parent / "scripts"

_TMP = Path(tempfile.mkdtemp(prefix="dbt-hardening-"))
os.environ["DREAM_BETA_REPORTS"] = str(_TMP / "reports")
(Path(os.environ["DREAM_BETA_REPORTS"])).mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(SCRIPTS))

import snapshot as S  # noqa: E402

_results: list[tuple[bool, str]] = []


def check(label: str, ok: bool) -> None:
    _results.append((bool(ok), label))


def _fixture(name: str) -> "tuple[Path, Path]":
    """A minimal (repo, store) pair under this run's temp root."""
    base = _TMP / name
    repo, store = base / "repo", base / "store"
    repo.mkdir(parents=True)
    store.mkdir(parents=True)
    (store / "fact.md").write_text("---\nname: fact\ndescription: d\n---\nbody\n", encoding="utf-8")
    return repo, store


def arm_f1_disclosure() -> None:
    """F1a — a repo-committed symlink must not be READ into the persisted snapshot."""
    repo, store = _fixture("f1a")
    outside = _TMP / "f1a-secret.txt"
    outside.write_text("AAA-OUTSIDE-REPO-SECRET", encoding="utf-8")
    os.symlink(outside, repo / "CLAUDE.md")

    man = S.snapshot(repo, store)
    snapdir = Path(man.snapshot_dir)
    copied = snapdir / "repo" / "CLAUDE.md"
    disclosed = copied.is_file() and "AAA-OUTSIDE-REPO-SECRET" in copied.read_text(encoding="utf-8")
    check("F1a (PIN): a symlinked repo doc is NOT followed into the snapshot — "
          "pre-fix the out-of-repo secret is copied verbatim into the persisted reports tree",
          not disclosed and "CLAUDE.md" not in man.repo_docs_present)


def arm_f1_write_through() -> None:
    """F1b — restore must not write THROUGH a retargeted symlink into an out-of-repo file."""
    repo, store = _fixture("f1b")
    victim = _TMP / "f1b-victim.txt"
    victim.write_text("BBB-PRECIOUS-USER-DATA", encoding="utf-8")
    link = repo / "CLAUDE.md"
    # ⚠ A REAL file at snapshot time. The first draft of this arm symlinked it BEFORE the
    # snapshot — which the F1a fix now skips, so `before.files` held no entry and restore had
    # nothing to write. That made the arm green for the wrong reason: it proved nothing about the
    # WRITE-THROUGH leg, only that an absent entry is not written. The finding's own precondition
    # is "the symlink present at RESTORE time", so the link is created between the two.
    link.write_text("AAA-SNAPSHOT-CONTENT", encoding="utf-8")
    man = S.snapshot(repo, store)
    link.unlink()
    os.symlink(victim, link)
    plan = S.restore(man, repo, store)

    clobbered = victim.read_text(encoding="utf-8") != "BBB-PRECIOUS-USER-DATA"
    refused = any("SYMLINK" in s for s in plan.skipped)
    check("F1b (PIN): restore REFUSES a symlinked destination rather than following it — "
          "pre-fix the out-of-repo victim is silently overwritten with snapshot content",
          not clobbered and refused)


def arm_f2_discovery() -> None:
    """F2 — a self-declared version in an arbitrary clone must not win discovery."""
    import beta_checks as BC
    home = _TMP / "f2home"
    clone = home / "project" / "attacker" / "consolidate-memory"
    (clone / "scripts").mkdir(parents=True)
    (clone / ".claude-plugin").mkdir(parents=True)
    # ⚠ The FIRST draft of this arm stubbed three scripts it chose by hand, and passed pre-fix —
    # for the wrong reason. A candidate is filtered by `all((d/s).is_file() for s in
    # _REQUIRED_SCRIPTS)`, and the real list is ('memory_status.py', 'sync_global.py',
    # 'render_dashboard.py'). The hand-picked stubs failed THAT filter, so the clone was rejected
    # before the ranking this arm is about ever ran, and `picked != fake` held whether or not the
    # vulnerability existed. The fixture now derives from the constant the code reads — a fixture
    # that encodes its own copy of a predicate measures the copy, not the code.
    for s in BC._REQUIRED_SCRIPTS:
        (clone / "scripts" / s).write_text("# stub\n", encoding="utf-8")
    (clone / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"version": "99.99.99"}), encoding="utf-8")

    real_home = Path.home
    try:
        Path.home = staticmethod(lambda: home)          # type: ignore[assignment]
        picked = BC.discover_skill(None)
    finally:
        Path.home = real_home                           # type: ignore[assignment]

    fake = clone / "scripts"
    check("F2 (PIN): a clone's nested candidate does NOT win discovery on a self-declared "
          "version — pre-fix it satisfies the glob, passes the required-scripts filter, and "
          "wins max() at 99.99.99, then is subprocessed AND imported in-process",
          picked != fake)


def arm_f3_trash_collision() -> None:
    """F3 — two restores in the SAME SECOND must not destroy a quarantined file."""
    repo, store = _fixture("f3")
    (store / "fact.md").write_text("---\nname: fact\ndescription: d\n---\nv1\n", encoding="utf-8")
    man = S.snapshot(repo, store)

    # two live extras with DIFFERENT content, each quarantined by its own restore
    for content in ("FIRST-QUARANTINE-CONTENT", "SECOND-QUARANTINE-CONTENT"):
        (store / "extra.md").write_text(content, encoding="utf-8")
        # Pin the clock so both restores land in ONE epoch second — the collision's precondition.
        real_time = S.time.time
        try:
            S.time.time = lambda: 1790394005.0
            S.restore(man, repo, store)
        finally:
            S.time.time = real_time

    reports = Path(os.environ["DREAM_BETA_REPORTS"])
    surviving = set()
    for d in reports.glob(".restore-trash-*"):
        for f in d.iterdir():
            if f.is_file():
                surviving.add(f.read_text(encoding="utf-8"))
    check("F3 (PIN): both same-second quarantines survive — pre-fix one shared trash dir named "
          "by epoch second, and shutil.move renamed OVER the first file, destroying the only "
          "copy in the very mechanism whose purpose is recoverability",
          {"FIRST-QUARANTINE-CONTENT", "SECOND-QUARANTINE-CONTENT"} <= surviving)


def main() -> int:
    for arm in (arm_f1_disclosure, arm_f1_write_through, arm_f2_discovery, arm_f3_trash_collision):
        try:
            arm()
        except Exception as e:                    # a crash is a FAILED arm, never a skip
            check(f"{arm.__name__} RAISED {type(e).__name__}: {e}", False)
    failed = [lbl for ok, lbl in _results if not ok]
    for ok, lbl in _results:
        print(("  ✓ " if ok else "  ✗ ") + lbl)
    print(f"\n{len(_results) - len(failed)} passed, {len(failed)} failed")
    shutil.rmtree(_TMP, ignore_errors=True)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
