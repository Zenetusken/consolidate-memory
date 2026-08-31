# 007. Schema v2 and migration

Status: Accepted

## Context

Cross-project facts need domain, sensitivity, applies, status, stable IDs,
and revision fields the current frontmatter does not require. Native
`MEMORY.md` is truncated at 200 lines *or* 25 KB, whichever comes first; the
plugin's hard pull gate is an estimated-token ceiling derived from the byte
axis and does not fold the line axis in. A terse index can hit 200 lines
under the token ceiling. Unknown frontmatter and native `modified` must
survive rewrites. Existing installs have a populated `~/.claude/memory`.

A breaking control-plane + domain split would be a pre-1.0 **minor**
(`0.1.x` → `0.2.0`) *if shipped*. This branch does not ship 1.0 and does not
bump `plugin.json` to `1.0.0`. Cycle-record TypedDicts stay untouched unless
a v2 field actually lands on the cycle record (the SKILL pin still binds).

## Decision

Schema v2 is additive on Markdown facts and authoritative in the registry:

- `domain`, `sensitivity`, `applies`, `status`, `fact_id`, `base_revision` /
  `canonical_revision` (mirrors), distinct timestamps `content_modified` /
  `verified_at` / `mirrored_at` / `last_observed_at`.
- Native `modified` is preserved and excluded from semantic revision
  equality. Unknown frontmatter keys survive rewrite.
- Every prospective native `MEMORY.md` write builds the exact future UTF-8
  text and refuses unless `projected_lines <= line_limit_with_reserve` and
  `projected_bytes <= byte_limit_with_reserve` (reserve 15%; native caps 200
  and 25 KB). Token estimates stay observability.
- Link monotonicity is enforced at upsert/promote: project-local may link
  upward; capability-scoped may link to compatible or broader;
  domain-global only to domain-global or safe external; wider must not
  require narrower.
- `cm migrate --plan` is dry; `--apply` is reversible (journal + dual-read
  window). Dual-read: legacy `~/.claude/memory` plus domain dirs; after
  apply, domain dirs win and untagged legacy facts are not silently given a
  universal domain — they stay `legacy-unassigned` until reviewed.
- Capability detectors become an extensible registry (Node/TS, Go, Rust,
  JVM/.NET, Docker/K8s, Terraform/cloud, databases, CI/CD, build/test,
  OS/package-manager *classes*), with `applies.any` / `all` / `exclude`,
  evidence, confidence, detector version, observation time, and user
  overrides. Closed Python-centric stacks remain as one detector family.
- Operational history moves to `${CLAUDE_PLUGIN_DATA}` with bounded
  retention (events 90 days, latest 500 cycle records per project, daily
  aggregates 12 months; permanent: confirmed facts, user decisions,
  tombstones, migration summaries). Commands: `cm data inventory|compact|
  export|purge|retention`. Reads are reverse-tail or indexed SQLite, not
  full-file split-then-tail.
- Hook sketches are compact and contain no raw prompts or full tool
  results. Workflow promotion requires ≥2 projects, ≥2 days, repeated
  success, no unresolved decline, distinctiveness, and confirmation —
  unless the user explicitly requests the workflow.

## Alternatives

- **Big-bang cutover with a default `personal` domain.** Rejected: silent
  assignment (ADR 003).
- **Keep token-ceiling admission; report the 200-line cliff only.**
  Rejected: the cliff is the safety boundary Claude actually applies.
- **Embeddings / remote index as the v2 store.** Rejected: out of scope;
  Markdown + stdlib SQLite is the product.

## Consequences

Positive: native truncation cannot commit; migrate is reviewable; v2 fields
do not smash CycleRecord unless we add keys there (we don't in this branch).

Negative: dual-read lasts until operators finish migrate. Detector classes
are not an infinite catalog — missing ecosystems are user-override + new
detector files, not a completeness contest.

Neutral: plugin version stays `0.1.91` on this branch. 1.0 remains HOLD.
Shipping later is a minor under the pre-1.0 policy if the install contract
breaks, authored via CHANGELOG-first `release.sh`.

## Revisit trigger

Reopen if a v2 field must land on `CycleRecord` (update TypedDicts, SKILL
block, and smoke pin together), if native caps change, or if dual-read
duration on a real fleet exceeds one migrate window.
