# 020. Project-state CAS and LocalFactV1

Status: Accepted
Extends: ADR 002, ADR 006, ADR 011

## Context

PR #128 script-wrote `demotion_justify` into `.consolidation-state.json` and
taught `cm local` a recall-key pointer. The rolling JSONL `windows_full` clock
can drop after 500-row / 90-day compaction, so `jw+5 > wf` suppresses a
justification forever. Several unlocked JSON writers still last-writer-win
the marker. `cm local` claimed the canonical codec but only checked
stem/secret/description, inferred create-vs-replace from a later
`Path.exists()`, admitted SHIPPED.md with the always-loaded cliff, and
silently dropped invalid facts on rebuild-index.

## Decision

1. **Usage-window clock** lives in SQLite `project_usage_windows` (monotonic
   per-project sequence, idempotent on cycle_id). Justification stamps
   `{sequence, at}` and refires after five later *probative* sequences.
   `{windows, at}` is a migration input via the timestamp path.
2. **One marker mutation API:** `update_project_state` (project flock, snapshot,
   mutator, CAS, fsync file+parent). Dream marker, stacks cache, snooze,
   standing justify, and demotion justify all use it. The skill invokes
   `--stamp-marker` / `--justify-demotion`; it does not hand-MERGE JSON.
   Default justify is candidate-gated (`--force` for repair).
3. **`FileSnapshot`** is the plan-time precondition for every writer path:
   existing → hash+mode, missing → `ABSENT`. Mutate-time `exists()` must not
   flip create→replace.
4. **LocalFactV1** is a distinct contract (`local_schema_version: 1`,
   `scope: project-local` only). Canonical v3 keys (`fact_id`, `domain`,
   `applies_*`) are not required. SHIPPED.md uses `archive_index` (operational
   cap). Rebuild-index is plan-first and fail-closed.
5. **Stems keep periods**, capped at 96 chars / 180 UTF-8 bytes.
   `link_targets` validates stems instead of dropping dotted names.

## Alternatives

- Drop periods from stems. Rejected: live stems such as `…_v2.1` exist.
- Reuse canonical v3 for locals. Rejected: locals are not domain facts.
- Keep rolling `windows_full` plus `at`. Rejected: the integer leg runs first
  and compaction makes it succeed forever.

## Consequences

Positive: compaction cannot prolong a justification; concurrent marker writers
preserve both changes; local archive can grow past the always-loaded cliff;
rebuild cannot silently drop recallability.

Negative: legacy locals need `cm local migrate-schema` before a strict
no-inject rebuild. Existing over-cap stems remain readable and fail new writes
until renamed.

## Revisit trigger

Reopen if SQLite is unavailable on a supported install, or if LocalFactV1 needs
applicability tokens.
