## What this changes

<!-- One paragraph. What was wrong or missing, and what the change does about it. -->

## Why

<!-- The problem, not the patch. A reader who has never seen this code should be able to
     judge whether the change is the right shape without opening the diff. -->

## Gate results

<!-- Paste the actual last line of each gate you ran. "It passes" is not a result. -->

```
python3 tests/smoke.py                      ->
python3 tests/simulate_accumulation.py      ->
python3 tests/validate_manifests.py         ->
python3 tests/docs_links.py                 ->
mypy --config-file mypy.ini                 ->
python3 tests/dashboard_browser.py --out …  ->   (only if the template or a bundle changed)
```

## Reviewer notes

- [ ] Any new fact or claim in a document, comment, or this body is **checkable** — it cites
      a file and line, or a measurement, rather than asserting an adjective.
- [ ] No new runtime dependency (`plugins/consolidate-memory/scripts/` stays stdlib-only on
      Python 3.8+). `mypy` and Playwright remain dev-only.
- [ ] If the cycle-record shape changed, the seed, the renderer, the `TypedDict`s, and the
      `SKILL.md` schema block moved **together**.
- [ ] If a palette or contrast value changed, both contrast gates were re-run, and the
      measured numbers are in the description.
- [ ] No personal memory, credential, or machine-specific path is included.
      (This repository is public and ships none of the author's own facts.)

## Screenshots

<!-- If the rendered archive changed, include before/after at the width it matters. A claim
     about the rendered artifact should be verified against the rendered artifact. -->

---

See [CONTRIBUTING.md](../CONTRIBUTING.md) for the full gate list, and
[AGENTS.md](../AGENTS.md) for the repository's conventions.
