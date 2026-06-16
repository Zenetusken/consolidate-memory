# Memory-lifecycle audit — consolidate-memory

Audit of how the skill manages the *lifecycle* of memory across its context-loading
tiers, what self-optimization machinery exists, and what accumulation over time does
to context cost and file bloat. Evidence is reproducible:
`python3 tests/simulate_accumulation.py`.

**Status: audited → fixed at root.** The original audit found the skill had solid
**consistency** and **visibility** machinery but **no bounding machinery** — nothing in
code capped, garbage-collected, or measured the per-session token tax, and the most
expensive tier could silently drift from the facts it pointed to. Those gaps are now
closed in code (budget ceilings, orphan GC, index-hook upsert, token observability,
tighter stack matching, a re-verify signal). The simulation that *demonstrated* the
bloat now *characterizes the fixes*: each probe asserts the expected lifecycle property
and the run exits non-zero on regression. One property remains true **by design** —
the baseline still grows because pruning *which* facts to keep is a human-in-the-loop
judgment; the fixes make that growth visible, reclaimable, and coherent, not automatic.

---

## 1. Tier-by-tier survey (granular)

Three tiers, two physical stores. Surveyed by *how each reaches a future session's
context* and *what manages it over its life*.

### Tier 1 — Always-loaded (deterministic, paid every session)
- **What's in it:** `CLAUDE.md` (repo) + the auto-memory `MEMORY.md` *index*
  (`~/.claude/projects/<slug>/memory/MEMORY.md`). One pointer line per recall fact.
- **Cost model:** every byte is injected into *every* session, forever. This is the
  per-session token tax.
- **Lifecycle today:**
  - *Created/grown by:* the model in Phase 4, and **automatically by
    `sync_global.py::_ensure_index_pointer`** — every replicated global fact appends
    a pointer line. This is the load-bearing growth path and it is unbounded.
  - *Measured by:* `memory_status.py` (`index_lb` → lines/bytes), surfaced in the
    dashboard's "Always-loaded budget" gauge as a before→after delta.
  - *Bounded by:* **now encoded** (was nothing). SKILL.md promised "a stated budget";
    it is now real — `memory_status.py` gates the index and `CLAUDE.md` against
    `INDEX_TOKEN_BUDGET` / `CLAUDE_MD_TOKEN_BUDGET` (in estimated tokens), sets
    `budget.*.over`, and the dashboard renders ⚠. *(Originally: the grep
    `'budget|limit|ceiling|threshold|max_|[0-9]{2,}'` over `skill/scripts/` returned
    only the cycle-record data field, `--max`, and widths — no ceiling existed.)*
  - *Reclaimed by:* the model pruning lines in Phase 4 (a judgment call, kept human),
    **plus** `--gc` for orphaned mirror pointers (mechanical, now coded).

### Tier 2 — Recall-loaded (non-deterministic, surfaced on `description:` match)
- **What's in it:** auto-memory `<name>.md` fact files (bodies).
- **Cost model:** pulled into a session only when the `description:` recall key
  matches the task — so a weak description = invisible fact, a bloated store = more
  near-miss candidates competing for relevance.
- **Lifecycle today:**
  - *Created by:* model (Phase 4) and `sync_global.py --pull` (replicated global
    mirrors, stamped `global_ref:`).
  - *Refreshed by:* `--pull` detects `STALE-mirror` (canonical changed) and rewrites
    the body. Idempotent (`_as_mirror`). **Good.**
  - *Bounded / GC'd by:* `--gc` reclaims orphaned mirrors (was nothing; Probe B: 4→0).
    Net count still rises with genuinely-new facts — that prune stays a human call.
  - *Re-verified by:* `memory_status._stale_since` now flags facts untouched since the
    marker (mtime ≤ marker) as re-verification candidates (was nothing scheduled).

### Tier 3 — On-demand (read by the agent when relevant)
- **What's in it:** repo `AGENTS.md` / `MEMORY.md` + the fact-file *bodies*.
- **Cost model:** cheapest — not auto-injected, so bloat here doesn't tax every
  session; optimize for completeness.
- **Lifecycle today:** entirely model-managed in Phase 4/5. No script touches repo
  docs. This is the correct place for leniency and the audit finds no issue here.

### The global tier (cross-cutting — `scope`, not a 4th loading tier)
- `~/.claude/memory/` is the canonical home for `user-global` / `stack-general`
  facts; `--pull` replicates them *down* into each project's recall tier.
- `scope ≠ tier`: a `user-global` fact is still a **recall-tier** fact in every
  project it lands in — and its pointer is an **always-loaded** line in every one of
  those projects. So one global fact's cost is multiplied by project count, in the
  most expensive tier. This is the bloat amplifier — now **measured** by `--tokens`,
  which sums the always-loaded tax across all nodes (§6).

---

## 2. Self-optimization machinery: present vs. absent

| Capability | Status | Where |
|---|---|---|
| Consistency: stale-mirror refresh tracks canonical | ✅ present | `sync_global.run` (`STALE-mirror`) |
| Idempotent mirror stamping / index pointer | ✅ present | `_as_mirror`, `_ensure_index_pointer` |
| Visibility: per-tier byte/line accounting | ✅ present | `memory_status.py`, dashboard budget gauge |
| Visibility: dangling-link / broken-pointer health check | ✅ present (model-driven, Phase 5) | SKILL.md health block |
| Secrets firewall at retrieval | ✅ present | `extract_signals._SECRET` |
| Index-hook coherence (pointer tracks canonical) | ✅ **fixed** | `_ensure_index_pointer` upsert (was early-return) |
| Budget ceiling on always-loaded tier (in est. tokens) | ✅ **fixed** | `INDEX_TOKEN_BUDGET` / `CLAUDE_MD_TOKEN_BUDGET`, `budget.*.over` + ⚠ |
| GC of orphaned mirrors | ✅ **fixed** | `sync_global.py --gc [--apply]` (`_orphans`) |
| Token observability across the network | ✅ **new** | `sync_global.py --tokens`, dashboard network sub-section |
| Tighter stack matching (no substring spread) | ✅ **fixed** | `_kw_hit` token-boundary match |
| Staleness / re-verification signal | ✅ **fixed** | `memory_status._stale_since` (mtime ≤ marker) |
| Provenance reclaim (drop dead edges) | ⚠️ **report-only** | `--gc` reports dead edges; auto-prune deferred (weak signal) |
| Automated dedup across stores | ❌ by design | model prose (Phase 5) — a judgment call, not mechanizable |

Originally every absent item was **bounding** machinery — that asymmetry was the
headline. The bounding machinery now exists in code; what remains model-driven (dedup,
*which* facts to prune) is genuine judgment, kept human-in-the-loop on purpose.

---

## 3. Findings → fixes (simulation evidence)

All reproduced by `tests/simulate_accumulation.py` (hermetic: runs the real CLI under
`HOME=<tmp>`, asserts no path escapes tmp before any write). The probes now assert the
*fixed* behavior; the run exits non-zero on regression.

### Code defects — fixed

**B — Orphaned mirrors after canonical deletion → `--gc`.**
*Found:* `run()` iterates only facts still in the global store, so a deleted
canonical's mirrors were never revisited (sim: 1 deletion → 4 orphans across 4
projects), each costing an always-loaded index line, with nothing to surface them.
*Fixed:* `sync_global.py --gc [--apply]` (`_orphans`) finds `global_ref:` files whose
canonical is gone and removes file + index pointer; report-by-default, `--apply` to
delete, never touches a project-authored fact. Sim Probe B: 4 orphans → **0** after GC.

**C — Index-hook drift on description change → upsert.**
*Found:* `_ensure_index_pointer` early-returned when the pointer line existed, so a
changed `description` refreshed the body but left the always-loaded index hook stale —
the most expensive tier silently drifting.
*Fixed:* the function now **upserts** — rewrites a drifted line, inserts if absent,
no-ops if already correct. Sim Probe C: body **and** hook both track the canonical.

### Design tensions — addressed or kept by design

**A — Unbounded, un-instrumented always-loaded growth → budget ceiling + observability.**
*Found:* the index grows **linearly at +244 B/cycle**, never shrinking. The teeth were
the **multiplier** (one `user-global` fact = one always-loaded line in *every* project)
and **invisibility** (the promised budget was never encoded).
*Addressed:* token ceilings (`INDEX_TOKEN_BUDGET` / `CLAUDE_MD_TOKEN_BUDGET`) now set
`budget.*.over` and the dashboard renders ⚠; `--tokens` measures the multiplied cost
across all nodes. The growth itself stays a human-in-the-loop prune (Probe A still
holds by design) — but it is now visible and reclaimable, not silent.

**D — Loose stack keywords spread `stack-general` ~universally → token-boundary match.**
*Found (engineered):* substring matching let `skill` match `reskilling`, so
`stack-general` facts spread wider than their stack.
*Fixed:* `_kw_hit` matches on token boundaries (non-alphanumeric edges, so dotted
keywords like `.claude` still work). Sim Probe D: a `reskilling`-only project no longer
inherits a `claude-code` fact, while a genuine `.claude` project still does. Genuinely
fleet-wide stacks (e.g. claude-code) stay broad **by design** — that is correct reach,
not spurious spread.

**E — No re-verification signal → mtime watershed.**
*Added:* `memory_status._stale_since` lists facts untouched since the marker (mtime ≤
marker timestamp) as re-verification candidates — a cheap staleness proxy needing no
per-fact `last_verified` field.

---

## 4. Fixes applied (all at root; zero-dependency, stdlib-only)

Each keeps the repo's conventions ("scripts produce presentation / model produces
data"); all covered by `tests/smoke.py` (pure functions) + `tests/simulate_accumulation.py`
(lifecycle properties).

1. **Index-hook upsert (C).** `_ensure_index_pointer` rewrites a drifted pointer line
   instead of early-returning. Pure `_pointer_line` factored out for smoke.
2. **Orphan GC (B).** `sync_global.py --gc [--apply]` removes mirror files whose
   canonical is gone + their index pointers; report-by-default; only `global_ref:`
   files; dead-edge provenance reported, not auto-pruned (absence-of-mirror too weak a
   signal to write global state on).
3. **Encoded budget (A).** `INDEX_TOKEN_BUDGET` / `CLAUDE_MD_TOKEN_BUDGET` in
   `memory_status.py`; `budget.*.over` flags; dashboard ⚠.
4. **Network token observability (the explicit ask).** `sync_global.py --tokens
   [--json]` measures per-node + total estimated token cost across the network;
   dashboard renders a "Neural network — token consumption (all nodes)" sub-section
   that also shows what *this* cycle did in lifecycle terms on the triggering node.
   See §6.
5. **Token-boundary stack matching (D).** `_kw_hit` replaces substring matching.
6. **Re-verification signal (E).** `_stale_since` flags facts untouched since the marker.

---

## 5. Observability — network-wide token consumption

The explicit deliverable: *exactly* (within an estimate) how many tokens the shared
memory costs across every node, and what a `dream` did to that cost on the node it ran
on. Implemented as `sync_global.py --tokens` + a dashboard sub-section.

- **Node set:** project memory stores holding ≥1 shared (`global_ref:`) mirror — the
  physical, *measurable* nodes (we have each store's path). This intentionally differs
  from `--network`'s logical `minds` set (provenance basenames, not invertible to a
  path): **`--network` = topology, `--tokens` = cost**; they can diverge (names vs
  slugs), and that seam is documented rather than papered over.
- **Per node:** always-loaded (index) tokens + recall-pool (fact-body) tokens + fact
  and shared-mirror counts. **Total:** summed across nodes — the always-loaded total is
  the per-session tax paid across the whole fleet.
- **Basis:** `est_tokens` ≈ `chars/4` (`memory_status.py`, reused by `sync_global` via
  sibling import). There is **no tokenizer** (zero-dep), so every figure is an estimate
  — rendered as `≈`, never "exact". This is the one honest limit of "exactly how much."
- **Cycle lifecycle on the triggering node:** the dashboard derives the
  added/corrected/deleted/reconciled/skipped counts from `entries[]` (single source of
  truth), the always-loaded token delta from the budget block, and GC/refresh counts
  from `cross_project` — so the "what the dream did" line can't disagree with the
  Changes table above it.

Live dogfood (`sync_global.py --tokens . --json` on this machine) found a real node
with **104 facts / ≈207k recall-pool tokens** — exactly the kind of latent bloat this
observability is meant to make impossible to miss.

---

## 6. Scope boundary (stated honestly)

The simulation exercises only the **script-driven** lifecycle — replication, GC, index/
token accounting, provenance. Deciding *which* facts to keep, prune, or dedup remains
**model prose** in SKILL.md, not code, so it is not simulated — and that is by design,
not a gap: it is genuine judgment, kept human-in-the-loop. What the fixes change is
that the mechanical failure modes around that judgment (silent drift, un-reclaimable
orphans, invisible per-session cost) are now bounded and observable in code, so the
human is pruning against a visible budget instead of an invisible one.

Token figures throughout are **estimates** (`≈ chars/4`); there is no tokenizer under
the zero-dependency constraint. They are stable and directionally exact — good for
budgeting and trend, not a substitute for a real token count.
