# Harness map — data sources, memory formats, verification recipes

Read this when you need the exact paths, file formats, or grep/git recipes for a
consolidation pass. The SKILL.md body covers the workflow; this is the lookup table.

## The substrate at a glance

The pieces a consolidation pass works with on Claude Code:

| Concern | Where it lives |
|---|---|
| Trajectory (what happened this session) | session transcripts `~/.claude/projects/<slug>/*.jsonl` (JSONL, large — never bulk-read) |
| Durable memory | **two** stores — see below |
| Citation for a recorded fact | a commit SHA, or the session `.jsonl` basename |
| Claim verification | tier-scaled — LIGHT verifies inline; SUBSTANTIAL/HEAVY fan out via Explore / general-purpose subagents (see *Rigor modes*) |

## The two memory stores

Claude Code splits memory across two places. Reconciling them — and keeping them
from contradicting each other — is the core enhancement over single-store `/dream`.

**1. Repo-committed docs (shared, in git):** `MEMORY.md`, `AGENTS.md`, `CLAUDE.md`
at the project root. These travel with the repo and the team reads them. `AGENTS.md`
is usually the architecture/gotchas source of truth; `MEMORY.md` a consolidated
snapshot; `CLAUDE.md` conventions. Edit them like code (they show up in `git diff`).

**`CLAUDE.md` is special — treat it as a guest, not an owner.** It is user
hand-authored, committed, team-shared, AND always-loaded — the widest blast radius of
any store — and its content is mostly *normative* (conventions/instructions) that
Phase-3 verification can't confirm against the tree. So default to NOT writing it:
route facts to auto-memory or `AGENTS.md`/`MEMORY.md`, and when a genuine always-loaded
convention truly belongs there, add a single surgical line in the file's own style.
Never create or reorganize one; propose (don't perform) any trim of its lines.

**There are TWO `CLAUDE.md`s, and they need different handling — don't conflate them:**
- **Project `<repo>/CLAUDE.md`** — committed, team-shared, loaded for *this* project.
  Guest-posture *writes* (the conservative edits above) apply here. Measured + budgeted
  against `CLAUDE_MD_TOKEN_BUDGET`; its ⚠ is *actionable* (propose a trim).
- **User-global `~/.claude/CLAUDE.md`** — personal, universal, loaded into *every*
  project, every session. **Strictly read-only**: `memory_status.py` measures it (its
  own `GLOBAL_CLAUDE_MD_TOKEN_BUDGET`) and the dashboard shows it as a distinct
  "global · every project · read-only" line so the always-loaded total isn't
  understated — but the skill **never writes it**. Its ⚠ is *advisory* (it loads
  everywhere), not a prune instruction. It is NOT the same as a `user-global`-*scope*
  fact: that's a recall-tier fact replicated via `~/.claude/memory/`; this is the
  always-loaded global instruction file, which the skill does not manage.

**2. Claude's private auto-memory (per-user, NOT in git):**
`~/.claude/projects/<slug>/memory/` where `<slug>` is the project's absolute path
with every `/` replaced by `-` (e.g. `/home/you/project/foo` →
`-home-you-project-foo`). Verify the slug rule with `ls ~/.claude/projects/`
rather than assuming it. Layout:
- `MEMORY.md` — the index, one line per fact: `- [Title](file.md) — hook`. Loaded
  into context every session. Never put fact bodies here.
- `<name>.md` fact files — one fact each, with frontmatter (match the EXISTING
  files exactly; confirm by reading one before writing — the live schema includes
  `node_type: memory`):
  ```markdown
  ---
  name: <short-kebab-case-slug>
  description: <the RECALL KEY — see below; not just a summary>
  metadata:
    node_type: memory
    type: user | feedback | project | reference
  ---

  <the fact. For feedback/project, follow with **Why:** and **How to apply:** lines.
  Link related memories with [[their-name]].>
  ```
  Types: `user` (who the user is), `feedback` (how to work — include the why),
  `project` (ongoing goals/constraints not derivable from code; absolute dates),
  `reference` (pointers to URLs/dashboards/tickets).

  **`description:` is a recall key, not a summary.** A fact's body is NOT auto-surfaced
  by relevance — Claude Code reads topic-file bodies on demand, not by matching. What
  is always-loaded is the fact's one-line index entry (its `description:`). So phrase
  the description as the *cue you'd want sitting in the always-loaded index* when a
  future task arises — include the concrete nouns that task would mention, so the agent
  knows to open the fact. A vague description hook leaves a true, useful fact unread.

## The three context-loading tiers

The two stores back three tiers that differ by HOW they reach a future session's
context. Place each fact by its tier, then optimize it for that tier:

1. **Always-loaded (deterministic, every session):** `CLAUDE.md` + the auto-memory
   `MEMORY.md` index. Confirm what's actually injected by inspecting your own context
   block (currently these two; NOT repo `AGENTS.md`/`MEMORY.md`). Most expensive —
   keep ruthlessly lean; only whole-project-framing facts earn a slot.
2. **Recall key (always-loaded index hook → on-demand read):** a fact body isn't
   auto-surfaced; its `description:` is the always-loaded index line that cues the
   agent to read it on demand. Invest in the description (recall key) and `[[links]]`.
3. **On-demand (the agent reads them):** repo `AGENTS.md`/`MEMORY.md` + fact bodies.
   Not auto-injected — optimize for completeness, not per-session leanness.

**Operational state (not a fact):** `~/.claude/projects/<slug>/memory/.consolidation-state.json`
holds `{commit, timestamp}` — the high-water mark of the last consolidation. Read it
in Phase 0 (scope `git log <commit>..HEAD`); rewrite it in Phase 5.

## What belongs where

- A fact useful to **anyone** working the repo (architecture, a gotcha, a verified
  design decision) → repo docs (`AGENTS.md`/`MEMORY.md`). A durable, project-wide
  *convention* that must steer every session is the rare thing that belongs in
  `CLAUDE.md` — added conservatively (the guest-posture note above).
- A fact about **the user, their preferences, your working relationship, or
  cross-session project context** not derivable from code → private auto-memory.
- **Never duplicate** the same fact in both stores. If it's in the repo docs, the
  auto-memory should at most point at it, not restate it. De-duplication across the
  two stores is the headline win of this skill — check the repo docs before adding
  anything to auto-memory.
- **Never** save what the repo already records (code structure, git history, a fix
  that's already a commit). Save the *non-obvious why*, not the diff.

## Rigor modes — scale ceremony to the pass's magnitude (Phase 0 hint, Phase 2 final)

`memory_status.py` computes a **suggested rigor tier** so a 1-fact pass and a 20-fact
pass don't get identical machinery. It is a deterministic, testable HINT — the model
finalizes it in Phase 2 and may override with rationale.

- **Signal = FLOW, not stock.** `magnitude = git_commits + session_candidates` — both
  count work done *this* cycle. `memories_reviewed` is **deliberately excluded**: it is a
  cumulative *stock* (the store's total fact count, which only grows), so folding it into
  magnitude would peg any mature project to HEAVY on every pass regardless of the actual
  work (confirmed empirically: across the live corpus the `git + reviewed` formula put
  *every* fact-producing session in HEAVY). `session_candidates` is the **curated**
  candidate-fact count (post-dedup), NOT the raw `extract_signals` `surfaced` count (which
  includes every non-noise turn + error result and runs far higher — feeding it in
  recreates the same collapse on the candidate axis).
- **Bands (provisional, tunable):** LIGHT ≤ 2 · SUBSTANTIAL 3–7 · HEAVY ≥ 8 —
  roadmap-inherited defaults, not yet empirically calibrated (the curated input was never
  recorded historically). The record exposes the magnitude (from `scope`) + `phase` that a
  future calibration could refit against — now that cycle records ARE persisted (the `--persist`
  log, Phase 5; they were render-and-discard before v0.1.4), a real refit still needs enough of
  them + longitudinal miss-detection. The pure
  functions `suggested_tier(git_commits, session_candidates)` and
  `prune_pressure(index_over, memories_reviewed)` live in `memory_status.py` (the renderer
  imports `suggested_tier` to DERIVE the displayed tier — see below).
- **Behaviors:** LIGHT = inline verify. SUBSTANTIAL = fan-out verification + a 2-source
  check for always-loaded-tier facts + the re-verify/GC sweep. HEAVY = + a completeness
  critic + a hard stop on an over-budget always-loaded write without an explicit prune.
- **Prune-pressure is a SEPARATE axis.** `index over budget OR memories_reviewed ≥
  PRUNE_PRESSURE_FACTS` forces prune-or-propose regardless of tier — a large store needs
  pruning even on a tiny pass. This is where the cumulative stock belongs.
- **Two phases; the suggested tier is DERIVED (not stored).** The cycle record stores
  `phase`, the prune-pressure flag/reason, and the realized-rigor `applied`/`override_reason`
  decision (v0.1.4) — never the derivable suggested tier. Phase 0 seeds `phase:
  "provisional"` (with no marker `git_commits` is a recent-≤20 lookback, so the tier is
  advisory). Phase 2 sets the curated `session_candidates` + `phase: "final"`. The renderer
  DERIVES the tier (and magnitude) from `scope` via `ms.suggested_tier`, so the displayed
  tier can never contradict its own magnitude — exactly how `_outcome` derives from
  `entries`. (`memory_status`'s Phase-0 *report* also prints a provisional tier as an
  operator hint — separate from the record.)
- **Distinct from the outcome banner.** The rigor tier is an *input*-side effort estimate;
  the dashboard's `LIGHT/SUBSTANTIAL PASS` banner is an *output*-side label from write
  counts. They share no scale (a pass can be HEAVY-rigor yet LIGHT-outcome). Both tier and
  magnitude are derived from `scope` at render, never stored — no parallel count to drift.
- **A coarse HINT by design + the apparatus to calibrate it (v0.1.4).** A sensitivity probe
  found magnitude matches a rich needed-rigor rubric only ~half the time — the deciding
  features (always-loaded-bound count, conflicts, prune-pressure) are LATE-known (Phase 2–3),
  so the EARLY magnitude proxy isn't precision-tunable; `(2,7)` is kept, with `prune_pressure`
  + the 2-source rule covering the blind spots. To enable a *data-grounded* future
  calibration, the model records the realized `rigor.applied`/`override_reason` and Phase-5
  `--persist DIR` appends each cycle record to `<store>/.consolidation-log.jsonl` (idempotent;
  skips persisting an unstamped cycle). LEVER NOTE: `INDEX_TOKEN_BUDGET` is the binding prune lever
  (~20–27 real facts); `PRUNE_PRESSURE_FACTS` is a terse-pointer backstop. CAVEAT: `applied`
  is self-reported (catches over-rigor only); under-rigor needs LONGITUDINAL miss-detection
  (future work), and the bands must NEVER be calibrated against the OUTCOME banner — it fails
  UNSAFE (mature passes are systematically high-magnitude/low-outcome).

## Verification recipes (Phase 3)

Every candidate fact is verified against the live tree before it lands. Claims are
small strings; verify each cheaply. Recall-biased: if a claim can't be verified,
flag it — don't silently keep it.

- **File/dir exists:** `test -e path && echo ok`
- **Symbol/function/flag exists:** `grep -rn "def the_function\|the_flag\|CONST" src/`
- **Claim matches current code (not stale):** read the cited lines; confirm the
  named behavior is still there (e.g. a memory says "X is headless" — grep the
  config default / the call site).
- **Decision landed in git:** `git log --oneline -S '<string>'` or
  `git log --oneline <marker>..HEAD -- <path>`
- **Doc claim self-consistency:** does `AGENTS.md`'s test count match
  `pytest -q`? Does a named module still exist?

Wrong/stale → correct it (cite the real current state). Unverifiable → drop it or
mark it explicitly as unverified. Never invent a citation.

**Normative content isn't tree-verifiable.** These recipes confirm *descriptive*
claims (a file/symbol/behavior exists). A `CLAUDE.md` *convention* ("prefer X", "always
run Y") has no tree fact to check — which is precisely why `CLAUDE.md` gets the
guest-posture treatment (write less, in-style, propose don't perform) instead of
leaning on verification it can't supply.

## Secrets firewall

Transcripts and `config.toml`-style files contain raw secrets (this project's
`config.toml` holds a plaintext credential, gitignored). **Never** copy
credentials, tokens, API keys, or PII from a transcript or config into ANY memory
store — repo docs are committed and auto-memory persists. Record a *pointer*
("credentials live in `config.toml`, gitignored") not the value.

## Cross-project (the global tier)

Recall is **slug-scoped**: a project auto-recalls only its own
`~/.claude/projects/<slug>/memory/`. There is no verified global recall tier (the
harness even makes per-slug stores for non-project cwds). Two consequences shape the
cross-project model:

- **Renaming a project dir orphans its memory.** The slug is the path with `/`→`-`,
  so renaming `~/project/foo` → `~/project/bar` moves the store from slug
  `-home-you-project-foo` to an empty `-home-you-project-bar` — stranding every fact
  under the old slug. Canonical cross-project facts must live somewhere slug-independent.
- **Global facts don't auto-cross** — they must be replicated into each project's
  store to surface there.

**Phase-0 detection (slug-orphans + schema drift) — detect/report/OFFER only, never
auto-mutated:**
- **Slug-orphans (near-duplicate slugs).** `slug_for` is **lossy** (`/`→`-`, so a
  `Doc-Flo` dir and a `Doc/Flo` path collide), making path-reconstruction ambiguous —
  so the robust rename-orphan signal is a **near-duplicate slug**: a sibling under
  `~/.claude/projects/` whose `norm()` (`s.replace("_","-").lower()`) equals this slug's,
  EXCLUDING the slug itself (a project never flags itself). `memory_status.near_duplicate_slugs`
  computes it; Phase 0 names each twin, flags which looks live (newest transcript/fact
  mtime), and offers a reconciliation hint (*merge toward newest mtime, NOT most files;
  land under the slug whose disk path exists*). Advisory — confirm before acting.
- **Schema drift vs. advisory absence — the fixed definition.** `node_type`/`type` are
  the only fields the documented fact schema (above) requires; `scope`/`originSessionId`
  are skill-/Claude-Code-**injected** and store-dependent, so their mere ABSENCE is noise,
  not drift. So **DRIFT** (always reported, `drift_findings > 0`) =
  - a fact **missing** the documented `node_type`,
  - a **present-but-malformed** `scope` (a `scope:` not in
    {`project-local`, `stack-general`, `user-global`}) or `originSessionId` (present but
    not a UUID — `_valid_uuid`), or
  - an **index↔file mismatch** (`stems △ index_names` — facts on disk with no index
    pointer, or pointers to no file; computed via the `](<stem>.md)` link anchor, NOT a
    naive line parse, so the `# Memory Index` header/blanks don't inflate it).

  Whereas a fact merely **lacking** `scope`/`originSessionId` is reported only as an
  **optional backfill advisory** (a separate line that MAY appear on an otherwise-clean
  store) — it is **NOT** a drift finding. `memory_status.schema_drift` returns both the
  drift counts and the advisory absence-counts.

**Dream-timing advisory (a Phase-0 report nudge, v0.1.10 — not a detection).**
`memory_status.dream_timing_advisory` emits a no-nag `💤 dream-timing` line when commits-since-marker
cross the SUBSTANTIAL band (and a marker exists) — flagging a good consolidation boundary before
compaction. Advisory only (never auto-fires; explicit-trigger-only); prospective use is via
`cm status`. Sibling to the provisional rigor tier + prune-pressure (the other Phase-0 report signals).

**Model:** a global store `~/.claude/memory/` (same fact-file + index format) is the
canonical home for facts with `scope: stack-general` or `user-global`. Each global
fact carries extra frontmatter: `scope`, `stacks: [python, rag, gpu, mypy, …]`
(relevance matching), `projects: [...]` (provenance). `sync_global.py`:
- `--list PROJECT_DIR` — show relevant/present/missing (read-only).
- `--pull PROJECT_DIR` — replicate missing relevant global facts into that project's
  store (additive, marked `global_ref:` so they re-sync), AND refresh stale mirrors +
  **upsert** the always-loaded index pointer so its hook tracks the canonical's
  `description` (a changed description rewrites the index line, not just the body).
  user-global → every project; stack-general → only if `stacks` intersect the
  project's detected stacks. Stack keywords match on **token boundaries** (`_kw_hit`),
  not substrings — so `skill` no longer matches `reskilling` while `.claude` still
  matches `.claude/`.
- `--gc PROJECT_DIR [--apply]` — reclaim **orphaned mirrors**: `global_ref:` files
  whose canonical was deleted from the global store. `--pull` can never remove these
  (it only iterates live globals), so they accrue forever without GC. Report-only by
  default; `--apply` deletes the file + its index pointer. **Only** touches
  `global_ref:` mirrors — never a project-authored fact, even on a name collision.
  Dead-edge provenance (canonical lists a project that no longer holds the mirror) is
  reported, not auto-pruned (absence-of-mirror is too weak a signal to write global
  state on — a renamed store also "holds nothing").

### Token observability (the per-session tax, made visible)

- `--tokens PROJECT_DIR [--json]` — estimated token cost across the **neural network**.
  A node is a **project memory store holding ≥1 shared (`global_ref:`) mirror** — the
  physical, *measurable* node set (we have each store's path). This deliberately
  differs from `--network`'s logical `minds` set, which is derived from provenance
  *basenames* that can't be inverted to a store path: **`--network` = topology,
  `--tokens` = cost**, and the two can diverge (names vs slugs). Per node it reports
  always-loaded (index) + recall-pool (fact-body) tokens; the `--json` form is the
  cycle record's `network` block.
- **Tokens are estimates** (`est_tokens` ≈ `chars/4`, in `memory_status.py`; reused by
  `sync_global` via sibling import). There is no tokenizer — the zero-dep constraint
  rules one out. Always present token figures as `≈`, never as exact.
- **Always-loaded budget ceilings** live in `memory_status.py` as
  `INDEX_TOKEN_BUDGET` / `CLAUDE_MD_TOKEN_BUDGET` (heuristic, tunable). It sets
  `budget.*.over` when a tier exceeds its ceiling; the dashboard renders ⚠. This is the
  "stated budget" the always-loaded tier always implied but never encoded.
- **Re-verification signal:** `memory_status.py` lists facts untouched since the marker
  (mtime ≤ marker timestamp) as re-verification candidates — a cheap staleness proxy
  needing no per-fact `last_verified` field.

A fact's **scope ≠ its tier**. Scope = how widely it applies (project/stack/user);
tier = how it loads (always/recall/on-demand). A `user-global` fact is still a
recall-tier fact *in each project it's replicated to*. Peers that aren't CC projects
(e.g. a data vault of versioned processing artifacts, not CC sessions) can't
auto-participate — they'd need a separate adapter; deferred.

### Scope is a fleet-wide cost multiplier — and the lever for relieving it

Each replicated fact adds an **always-loaded** index pointer to *every* project it
reaches. So global-scope facts are a per-session tax paid across the whole fleet:
- `user-global` → every project (G facts × P projects pointers fleet-wide).
- `stack-general` on a **common** stack → nearly as wide while *looking* scoped. The
  `claude-code` stack (`.claude`, `skill`, `agents.md`) matches almost every CC repo,
  so a `claude-code` stack-general fact behaves like a second user-global tier. Reserve
  `stack-general` for **narrow** stacks (`gpu`, `rag`, `playwright`).

**The promotion cascade (mirrors SKILL.md Phase 2).** Decide a fact's scope by the
fleet-**CONSTANT** vs fleet-**VARYING** distinction: a fact whose only dependency is the
user's *constant* substrate (OS/account, an always-present CLI like `gh`, the Claude Code
harness) can be `user-global`; one gated by a *fleet-varying* stack (present in only some
projects — `mypy`, release-cutting) is at most `stack-general`. Walk in order (total; floor
= `project-local`): **Gate 0** project-specific → `project-local`; **Gate 1** judge the fact's *content*, not its `stacks:` tags — a fleet-CONSTANT dependency
(the harness/`claude-code`, `gh`, OS) skips to Gate 2, while a fleet-varying precondition →
`stack-general` (S1 specific stack + S2 holds for all on it, else → `project-local`); **Gate 2** `user-global` only if ALL of — G2.1 no
fleet-varying precondition (constant substrate exempt), G2.2 a user/env (not codebase)
property, G2.3 ≥1 named existing other project it would apply to, G2.4 not already in
`~/.claude/CLAUDE.md` / not derivable, G2.5 durable. The applicability gate G2.3 is the
deliberately weakest gate — the **demotion re-audit (Phase 1, shipped)** backstops it: each pass
re-walks this cascade over existing `user-global` facts by content and offers demotion.

**The over-budget lever.** When a project's index trips the budget ⚠, attribute the
cost first: `--tokens` and the dashboard report `mirror_index_tokens` (the share driven
by replicated mirrors). If the overflow is **mirror-dominated**, *local* pruning is
futile — `--pull` re-creates a deleted mirror next cycle. The only effective fix is to
**demote/delete the canonical in `~/.claude/memory/`** (it stops replicating), then
`--gc --apply` to reclaim the orphans (here, and in every other project on its next
pass). Local pruning works only on **project-authored** index lines.

## Why claims-first, not transcript-first

The active transcript can be tens of MB. Never hand a subagent "read the
transcript." In Phase 2 extract a short list of discrete candidate claims (from the
two `MEMORY.md`s + `git log <marker>..HEAD` + at most the transcript *tail*), then
in Phase 3 verify *those specific claims* — inline on a LIGHT pass, fanned out at
SUBSTANTIAL+ (see *Rigor modes*). Small inputs, cheap runs.
