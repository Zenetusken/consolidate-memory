# 011. Fact schema v3 and authoritative mirror lineage

Status: Accepted
Supersedes: ADR 007's deferred nested-applies / schema-codec deferral

## Context

Canonical upsert permitted missing `name` / `domain` / `scope` / `sensitivity`
/ `status` / fact id / schema version, defaulting in memory without writing
defaults back. The frontmatter parser is flat and cannot implement nested
`applies.*`. Mirror classification trusted editable `base_revision` on the
mirror. Canonical `projects:` lists were rewritten as if authoritative
(ADR 004 said the registry is).

## Decision

A restricted stdlib codec (`fact_schema.py`), not a YAML parser. Required
fields:

```yaml
schema_version: 3
fact_id: f_...          # writer-injected
name: <stem>            # must equal filename stem
description: ...
domain: <enrolled domain>  # writer-injected
sensitivity: public|internal|confidential|secret
scope: project-local|stack-general|user-global
status: active|superseded|tombstoned|expired
applies_any: []
applies_all: []
applies_exclude: []
content_modified: RFC3339
last_observed_at: RFC3339
```

List syntax is flow `[a, b]`. Unknown keys are preserved but cannot skip
required fields. Nested `applies.any` in old files is migrated or refused.

Mirrors carry `canonical_fact_id`, `canonical_domain`, `base_revision`,
`canonical_revision`. Classification uses the **holder-table** base under
lock. Missing lineage → quarantine, not overwrite.

`projects:` on canonicals is a non-authoritative generated view (or omitted).
The holders table is the source.

## Alternatives

- **General YAML parser.** Rejected: zero-dep, attack surface.
- **Keep trusting mirror frontmatter.** Rejected: P0-4 companion.

## Consequences

Positive: a file cannot sit in `domains/work/facts/` while logically untagged.

Negative: existing canonicals need a migrate pass (ADR 013) before enforcement.

## Revisit trigger

Reopen if Claude requires a nested frontmatter key we cannot round-trip.
