# 023. Sole authority per state kind (SQLite-only topology and grants)

**Status:** Accepted (v0.4.0).

## Context

The same state had two operational authorities: holder topology lived in both
Markdown `projects:` frontmatter and the SQLite `holders` table (reads fell back
to Markdown on any empty SQLite list, so authoritative zero resurrected stale
provenance); native-store grants lived in an unlocked `store-grants.json` RMW
cycle (revoke overwrote in place; the same path could be granted to two
projects); migration kept-existing dispositions missed the catalog overlay
except in the tombstone-resurrection branch; pointer/catalog lines were
hand-built in several places; a duplicate frontmatter key resolved last-wins.

## Decision

Exactly one authority per kind of state:

```text
fact content        → Markdown
project/domain data → control.sqlite
holders/revisions   → control.sqlite
grants/counters     → control.sqlite
operation state     → journal.sqlite
recovery bytes      → temporary recovery area
project marker      → one locked state API
```

- **Holders:** tri-state reads — `None` (registry unavailable) → Markdown
  `projects:` as *migration input*; `[]` → authoritative zero, never falls
  through to Markdown; `[…]` → SQLite labels. `--gc --edges --apply` writes the
  `holders` table only; canonical bodies are byte-verbatim. Markdown
  `projects:` is migration input / frozen display, never an operational
  authority.
- **Grants:** `native_store_grants` table, one owner per normalized path, all
  mutations under `locks/global.lock`; JSON is dual-read migration inventory
  with a one-shot ingest (single ingester in `control_plane`).
- **Migration:** every active kept-existing disposition enters the catalog
  overlay; finalize postconditions per disposition. Full single-source
  migration control state (plan/rollback/manifest JSONs folded into one
  journaled row) remains a follow-up — the shipped consolidation is the
  catalog-overlay repair plus the migration_id cross-check against the
  control.sqlite `migration_state` row.
- **Catalog/links/pointers:** every pointer/catalog line is generated through a
  typed renderer (`_pointer_line` / the local `_pointer` constructor); a
  canonical dependency target must be `CLASS_ACTIVE`; duplicate reserved
  frontmatter keys are refused; `replacement_id` is validated (self + cycles
  refused).

## Consequences

- Reads never resurrect Markdown provenance against an authoritative zero.
- Grant-vs-grant and grant-vs-revoke MUTATIONS are serialized by the lock;
  revoke is a row delete, not a file rewrite. Reads (`resolve_store`'s grant
  check, `cm project grants`) take no lock: they are tolerant snapshots — a
  concurrent revoke takes effect at the next mutation, and the write-time
  checks are the enforcement point.
- Display paths (`network()`, `fleet_utility`, `--gc --edges`) classify from
  SQLite; the Markdown line is provenance history only.
- Dead compatibility surface removed: `fact_id_for`, `_prune_holders` /
  `drop_holders_text`, and the dormant hook-sketch infrastructure — including
  its `usage_events`/`workflow_sketches` registry tables, dropped by the v4
  schema migration (see ADR 024).
