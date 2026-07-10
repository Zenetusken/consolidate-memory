# Fleet usage harvest — capture every node's windows before the transcripts rot

**Status:** shipped (this PR). **Scope:** `sync_global.py` (`--harvest`, the shared ledger,
`fleet_utility` merge). The second increment of the audit's enhancement program
(signal-sufficiency lens, P1); rides the evidence-clock stamps
(`docs/evidence-clock-stamps.spec.md`), which make its windows durable.

## The measured problem

Usage capture is dream-gated per node: `extract_signals --recalls` runs only inside the
triggering project's own dream (Phase 5). Live fleet: **1 of 3 mirror nodes has ever emitted a
usage block**; the other nodes' windows are not merely zero, they are UNOBSERVED — and their
transcripts rotate away in weeks, destroying the evidence before it can ever be captured. Red
baseline (sandboxed): a node holding a mirror, with a real organic `Read` of it sitting in its
transcript and no cycle log — `fleet_utility` reports `reads=0, windows=0, nodes_reporting=0`.
No downstream statistic can recover windows that were never persisted; the demotion/gc evidence
base sits at its floor forever.

## Design

**`sync_global.py --harvest PROJECT_DIR`** — run from any node's dream (SKILL Phase 1, right
after `--pull`; also `cm harvest`). For each node in `_network_nodes()` ∪ the trigger store:

1. **Watermark**: the max window-END previously harvested for that node (from the ledger), else
   none → first harvest scans the node's full surviving transcript history (the whole point —
   capture before rotation). Re-runs are cheap idempotent no-ops (`_window_transcripts`' mtime
   prune + the watermark).
2. **Scan** with the EXACT `--recalls` machinery — `extract_signals._window_transcripts` +
   `_recall_items` + `split_dream_span` (dream-span exclusion included; only Read file-paths and
   arc-marker presence are extracted, never message content — no new privacy surface, and the
   secrets firewall isn't in this path because no content leaves the scan).
3. **Persist**: one usage-shaped row per (node, window) appended to the shared ledger
   `~/.claude/memory/.fleet-usage.jsonl` — `O_APPEND|O_CREAT` at `0o600` (single-line appends;
   the concurrency stance mirrors the documented D-2 accepted-gap philosophy: dream-boundary
   cadence, self-healing). A dot-file: structurally invisible to `global_facts()`'s `*.md` glob,
   to `--pull`, and to every index — zero always-loaded tax. Script-truth telemetry in the
   `render_dashboard --persist` class, not a memory-content write — report-then-apply intact,
   and the report prints every row it appends (legibility norm).
4. **Window honesty**: the row's window START is the oldest scanned transcript's mtime (a
   transcript's mtime is its END, so the claimed span can only UNDER-state coverage — the pinned
   bias); the END is now. A row whose `facts_read != len(per_fact)` (cap-truncated) is
   non-probative for zero-read evidence, same as own-log windows.

**Consumption (`fleet_utility`)** — v1 rule, deliberately conservative: harvested rows
contribute ONLY for nodes with **no own-log usage at all** (the exact coverage hole measured
live); a node with any own windows stays strictly own-log (no interval-overlap math, no
double-count risk). Per-canonical evidence stays source-labeled — additive `--json` keys
`harvested_reads` / `windows_harvested` per canonical and `nodes_harvested` in the payload —
never blended silently. The same mirror-check-before-attribution and shadow separation apply;
window credit still gates on the mirror's evidence clock (`global_ref_since`, mtime fallback).

**v1 reach limits (deliberate):** no miss/archive-tier classification (that requires the node's
own Phase-0 window-start snapshot — the exact hazard `--recalls --before` exists for; misses
stay a dreaming-node signal); no cycle-record key (the additive `cross_project.harvested`
capture belongs to the release where demotion actually consumes harvested evidence — the
instrument-before-policy staging, and the ledger itself is the durable record meanwhile);
own-log↔harvest interval merging for mixed nodes deferred to the same release.

## Alternatives rejected

"Make every project dream more often" — a wish, not a mechanism (cadence is user-owned).
Writing harvested blocks into each node's OWN cycle log — a cross-store write into a file that
node's own dream also writes; the shared ledger keeps single-writer-per-file discipline and
records who observed what. A background daemon/hook — violates the dream-boundary execution
model and the zero-deps austerity.

## Acceptance gates

1. RED (measured): the coverage hole above. GREEN: after one `--harvest`, the same fixture's
   canonical shows the harvested read; a second `--harvest` appends nothing (watermark).
2. `--utility` stays read-only over the project stores; the ledger is `0o600`; a garbage ledger
   line is skipped, never fatal; a node WITH own-log usage ignores its harvested rows (pinned).
3. Full gates: smoke + sim + mypy + manifests.
