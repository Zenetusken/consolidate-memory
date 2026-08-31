# 014. Phase-1 managed sync is the documented pre-Phase-4 exception

Status: Accepted

## Context

SKILL.md said Phases 0–3 are read-only and Phase 4 is the first write. Phase 1
then runs `--pull` and `--harvest`, writing mirrors, index pointers, and
usage ledgers. SECURITY.md claimed all writes appear in the Phase-4 report.
v0.2.2 Stage 0 documented the contradiction. This ADR freezes the intended
contract.

## Decision

Retain Phase-1 managed sync as the **sole** pre-Phase-4 fact mutation, only when:

- the project is enrolled and `cross_project_allowed`;
- `--list` has shown the exact plan first;
- only already-approved same-domain canonicals replicate;
- exact native index admission still applies;
- the writes appear in the Phase-5 mutation audit.

`--harvest` may write plugin-data usage ledgers under the same enrollment
gate (not native facts).

Authoring, forget, migrate, enroll/move/unenroll, GC `--apply`, and committed
docs stay report-then-apply (Phase 4 / explicit commands).

Unenrolled projects skip Phase-1 pull (local-only, ADR 008).

## Alternatives

- **Move pull to Phase 4.** Rejected: cold-start bootstrap and maintenance
  passes need mirrors before Phase-2 dedup.
- **Keep the "all writes are Phase 4" sentence.** Rejected: it is false.

## Consequences

Positive: SKILL, SECURITY, and the mutation audit agree.

Negative: a dream of an enrolled project still writes before the operator
sees the Phase-4 proposal — but only replicas of facts they already approved
in some other project's Phase 4.

## Revisit trigger

Reopen if operators demand an explicit confirm even for same-domain pull.
