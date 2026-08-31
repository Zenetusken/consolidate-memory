# Standing architecture — consolidate-memory

Recorded 2026-08-30 so later sessions do not re-elicit constraints or relitigate
settled boundaries. Procedure lives in
`plugins/consolidate-memory/skills/consolidate-memory/SKILL.md`; this file is the
constraint brief. New facts reopen a decision; vibes do not.

## Constraints

| Axis | Standing value |
|---|---|
| **Stage** | Pre-1.0. Product mechanism is mature (v0.1.91); go-external is HOLD pending a clean-machine walkthrough and a second human's fleet (`docs/1.0-preflight.spec.md`). |
| **Team** | Solo maintainer. One on-call surface. QA companion (`dream-beta-tester`) is the same person, consumer-only of the product plugin. |
| **Scale** | Local disk, per-session, one operator's fleet (order of ~12 project stores). Not a request-serving system. SessionStart budget is 2s fail-open. |
| **Runtime** | Python 3.8+ stdlib only. No pip, no network, no tokenizer. Must run anywhere Claude Code does. |
| **Reversal** | Cycle-record schema becomes a committed API at 1.0.0 (one-way). SKILL.md body is two-way (`/reload-plugins`). Global store format and plugin-not-skill install are high reversal. |
| **Quality bar** | Live-tree verification of every candidate. Report-then-apply before irreversible / always-loaded / global writes. Never skip a scan to save a turn. |

## Boring-technology budget

Spent on the differentiator (verification-first memory, scope cascade, cycle-record
contract, fleet governance). **Not** spent on orchestration frameworks, a datastore,
embeddings, or a conductor that "runs the phases." A `dream_conductor.py` was
considered and deferred (`docs/dream-procedure-integrity.spec.md` §Deferred to v2)
as ergonomics with no enforcement — a script cannot force the model to invoke it.

## Settled shape (do not relitigate without a new fact)

- **Plugin, not a user-skill.** `${CLAUDE_PLUGIN_ROOT}` and hooks exist only as a plugin.
- **Two physical stores + a replicated global.** Recall is slug-scoped; `~/.claude/memory`
  does not auto-surface. Canonicals replicate into per-slug stores as `global_ref:` mirrors.
- **Cycle record is the contract.** Model produces data; scripts render. TypedDicts +
  SKILL schema block + smoke pin move together.
- **Explicit `dream` only.** The one hook is a read-only SessionStart beacon (at most
  one advisory line). Never auto-pull, never auto-write memory.
- **Six phase *boundaries* stay.** 0–3 read-only → 4 first write (report-then-apply) →
  5 post-write measure. Collapsing 2+3 mixes claims with confirmation. Collapsing 4+5
  measures before the write. The 2026-06-22 lazy-skip was skipping Phase 3, not "too
  many names."
- **Accepted residuals (Track D / harness-map):** promote is not crash-atomic;
  concurrent `_record_provenance` can drop a `projects:` entry (self-heals);
  slug encoding is lossy (`/` and `_` → `-`); no lock on the global store.

## Empty-set rule (2026-08-30) — ADR 001

Pain was judgment beats on empty scans and reading every fact body every pass.
**Not** wall-clock of the stdlib scripts, and not the Phase-4 approval wait.

**Decision:** scans always run; judgment only when the scripted set is non-empty;
fact bodies are targeted, not a store-wide preload. Full text in SKILL.md
(*Empty-set rule*) and `docs/adr/001-empty-set-judgment.md`.

What still always runs: Phase-0 detectors, `--list`/`--pull`/`--harvest`,
`extract_signals`, Phase-3 verify, `--gc` report, `--recalls`, distill `--json`,
`--workflows` / `--registrar --into`, and content walks of every `user-global`
canonical, every `promote?` seed body, and every `archive?` / `defrag?` /
re-verify file when N>0. Phase-2 dedup is indexes + grep of candidate nouns +
Read of hits.

What does not: sequential Read of every local fact body "to orient"; a judgment
beat on `archive? 0`, `defrag? 0`, dormant demotion, `0 recurring · 0 chains`,
`fleet-candidates: 0`; walking `blocked: generic-cli` as a docket.

Rejected under the same constraint: skip harvest/distill on LIGHT (evidence rot);
cap the demotion re-audit (delayed over-promotion); auto-apply always-loaded or
global writes; a second `dream-fleet` skill (harvest would depend on the operator
remembering to run it).

## Open doors

- **1.0 schema freeze** — HOLD. Residuals are operator-evidence, not more mechanism.
  Do not grow committed-API surface until 1.0 ships or is deferred with a named trigger.
- **Script bundling** (`--seed`+`--snapshot` in one process, post-apply measure wrapper)
  — two-way ergonomics; not started. Does not change decisions.

## Consistency

If new code or a SKILL edit contradicts this file, flag the drift. Do not "optimize"
a dream by skipping a scan or a non-empty content walk.
