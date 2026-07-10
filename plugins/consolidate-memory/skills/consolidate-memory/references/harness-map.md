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
from contradicting each other — is something a single-store, per-project consolidator like Auto Dream doesn't address.

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
with both `/` AND `_` replaced by `-`, case preserved (e.g. `/home/you/project/Doc_Flo`
→ `-home-you-project-Doc-Flo`; v0.1.17 — CC normalizes underscores too, verified on disk).
The rule is verified ONLY for `/`+`_` (no other-char example exists); a `.`/space could
diverge further and would NOT be caught by `near_duplicate_slugs` (collapses only `_`/case)
— an accepted residual risk. Verify a concrete slug with `ls ~/.claude/projects/` (a
transcript's recorded `cwd` → its on-disk slug dir is ground truth). Layout:
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
    originSessionId: <v0.1.43 — for a SESSION-DERIVED fact, the sessionId of the session that MOTIVATED it
                      (NOT the active dream's session): use the `sessionId` extract_signals now attaches to the
                      signal this fact came from. OMIT for a git/commit-derived project fact (no motivating
                      session). This is the PRODUCER the old "CC-INJECTED" wording wrongly presumed existed.>
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
  is self-reported (catches over-rigor only); the LAZY-SKIP under-rigor case (SUBSTANTIAL+
  magnitude with 0/0/0 verification) is now caught by the v0.1.44 `procedure_integrity` detector at
  `render_dashboard --persist` (⚠ panel + exit 3; it rests on script-derived `git_commits`, not the
  self-report, so it can't be graded away — not a diligent-liar proof). The GENERAL under-rigor case
  still needs LONGITUDINAL miss-detection (future work), and the bands must NEVER be calibrated
  against the OUTCOME banner — it fails UNSAFE (mature passes are systematically high-magnitude/low-outcome).

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

## Distill (the second vertical — Phase 5 step 6)

Where the phases above consolidate **facts**, distill detects repeated **workflows** and
proposes packaging one into a durable artifact — report-then-apply, never auto-written.
`scripts/distill_scan.py` is the counter; the model is the judge; the cycle record is the
capture.

**The scan `--json` contract** (v0.1.55; `secrets_omitted` v0.1.58):

```json
{"window": "<ISO or (all)>",
 "scanned": {"sessions": 0, "commands": 0, "days": 0, "secrets_omitted": 0},
 "recurring": [{"template": "...", "count": 0, "days": 0, "sample": "..."}],
 "chains":    [{"templates": ["a", "b"], "count": 0, "days": 0}]}
```

`recurring` = normalized command CLASSES with `count ≥ 2`, ranked by (days, count),
capped at 40; `chains` = adjacent kept-segment bigrams inside ONE compound command
(`&&`/newline/`;`-glued sub-steps), capped at 20. `days` is the episode dimension —
×27 across 9 days is a workflow, ×27 in one hour is a loop; rank is a hint, not a
filter. A credential-shaped command still counts into its class, but its `sample` is an
omission label and every emitted template is firewall-screened (`secrets_omitted` is the
transparency counter). The window (~30 days, `--since` to override) is deliberately
broader than the dream's `marker..HEAD` — say so when reporting.

**The `distill` record block** (`Distill` TypedDict; all keys `total=False`):
`sessions`/`commands`/`n_recurring`/`n_chains`/`window`/`secrets_omitted` are
**script-only** — never hand-author counts (a hand-mirrored count once shipped an
impossible `n_recurring: 47` against a cap of 40; `validate_cycle_record` warns when a
count exceeds the scanner caps). Capture in ONE scan: save `--json` to a file, judge it,
then inject that SAVED scan so the recorded counts equal the judged ones —
`distill_scan.py --from <scan.json> --into <seed> --verdict '…' [--proposed X]
[--created X]`. The judgment fields (`proposed`/`created`/`verdict`) are the model's,
passed via the flags. `--into` is the LAST write to that block; it exits non-zero if the
seed can't be written (capture loss is never silent) and warns if a judgment flag is
passed without `--into`. The window filter compares parsed INSTANTS (a local-offset
`--since` is honored correctly, not lexicographically mis-ordered against CC's `Z`
stamps).

**Acceptance recipe** (after touching the scanner): run
`python3 scripts/distill_scan.py <repo> --json` against a rich corpus and judge the
output — zero shell-syntax rows (`[ … ]`, `{`/`}`, `exit`/`continue`), zero
interpreter-inline classes (`… python -c`), chains that read like the project's real
gate/release pipelines. The smoke suite pins each noise class; the live-corpus read is
the honesty check the pins can't give.

## Cross-project (the global tier)

Recall is **slug-scoped**: a project auto-recalls only its own
`~/.claude/projects/<slug>/memory/`. There is no verified global recall tier (the
harness even makes per-slug stores for non-project cwds). Two consequences shape the
cross-project model:

- **Renaming a project dir — OR an underscore in its name — orphans/splits its memory.**
  The slug is the path with `/` AND `_` → `-`, so renaming `~/project/foo` → `~/project/bar`
  strands every fact under the old slug; and an underscore dir (`Doc_Flo`) maps to a hyphen
  slug (`-Doc-Flo`) — the v0.1.17 `slug_for` fix matches CC here, but a pre-v0.1.17 store may
  sit under the wrong `…-Doc_Flo` slug. Canonical cross-project facts must live somewhere
  slug-independent.
- **Global facts don't auto-cross** — they must be replicated into each project's
  store to surface there.
- **Concurrent writes to the shared global store (v0.1.71, Track D).** Two different
  projects dreaming around the same time can both write to `~/.claude/memory`. Every
  individual write there is atomic (write-temp + `os.replace`/`os.link` — never a torn
  file visible mid-write), and `promote()`'s canonical CREATE is exclusive (two projects
  racing to promote onto the same new name: the loser is refused and told to retry, not
  silently clobbered). One narrower gap is accepted, not fixed: two concurrent
  `_record_provenance()` calls on the SAME existing canonical can still race their
  read-modify-write of its `projects:` list — a lost update is possible (one project's
  provenance entry silently dropped), self-healing the next time that project's own
  dream promotes/pulls again. See
  `docs/track-d-write-atomicity-seed-hardening.spec.md` for the full design + why a
  lock wasn't built for that residual case.

**Phase-0 detection (slug-orphans + schema drift) — detect/report/OFFER only, never
auto-mutated:**
- **Slug-orphans (near-duplicate slugs).** `slug_for` is **lossy** (`/` AND `_` → `-`, so
  `Doc-Flo`, `Doc_Flo`, and a `Doc/Flo` path all collide to one slug), making path-reconstruction ambiguous —
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
  project's detected stacks. Stacks are detected from **REAL USAGE** (v0.1.16) — declared
  dependencies in `pyproject.toml` (PEP 621 / PEP 735 / poetry, matched as EXACT dep-name
  tokens, so `sentence-transformers` is never read as `transformers`), actual `import`s in
  `*.py`, and real marker dirs/files (`.claude/`, a `SKILL.md`) — **never a doc-mention**.
  Lockfiles are excluded (transitive deps over-detect). So a stdlib plugin whose README merely
  says "rag"/"scraper" no longer false-matches `rag`/`playwright`; a `stack-general:[rag]` fact
  binds only projects that really depend on / import a RAG library.
- **The SessionStart beacon** (v0.1.81, `docs/session-beacon.spec.md` — the plugin's first HOOK
  component, `hooks/hooks.json` → `scripts/session_beacon.py`): at session start/resume, at most
  ONE factual line is injected into context when THIS project's store is measurably behind the
  fleet (missing/content-stale counts via the same `_store_gaps` predicate `--staleness` uses,
  M1 ceiling-held projection, marker age). Read-only, advisory-only (never pulls — dreams stay
  explicit-trigger-only), silent on never-participated dirs / in-sync stores / snooze
  (`beacon_snooze_until` state key, set on explicit user ask), and silent-with-exit-0 on any
  failure. Budget: no `detect_stacks` (measured 2s on a big repo — reads the `--pull`-written
  `stacks`/`project_path` state cache instead, degrading to user-global-only when absent), no
  subprocesses; measured ~40ms against the 2s hook timeout.
- `--staleness PROJECT_DIR [--json]` — (v0.1.80, `docs/fleet-staleness-report.spec.md`) READ-ONLY
  absorption-lag sweep over ALL project stores (wider than mirror-holders — a zero-mirror store is
  the most starved): per node, last-dream marker age, MISSING relevant globals, content-stale
  mirrors (body-lineage hash), usage/harvest coverage. Scope basis honest per node (full relevance
  only for the trigger — slugs aren't invertible; others assessed user-global-only, labeled).
  Maintainer/observability lens (`cm staleness`), uncued; the observe-only Stage A of the
  session-beacon track — never auto-pulls (a node absorbs on ITS next dream).
- `--harvest PROJECT_DIR` — (v0.1.79, `docs/fleet-usage-harvest.spec.md`) capture EVERY node's
  organic fact-read windows from its transcripts into the shared append-only ledger
  (`~/.claude/memory/.fleet-usage.jsonl`, 0o600) before rotation destroys them. Usage capture was
  dream-gated per node (measured: 1/3 nodes reporting, the rest unobserved). Watermarked per node,
  idempotent; reuses the `--recalls` scan machinery (dream-span excluded; only Read file-paths and
  arc-marker presence leave the scan). `--utility` surfaces harvested evidence — source-labeled,
  only for nodes with no own-log usage (own-log strictly primary in v1).
- `--gc PROJECT_DIR [--apply]` — reclaim **orphaned mirrors**: `global_ref:` files
  whose canonical was deleted from the global store. `--pull` can never remove these
  (it only iterates live globals), so they accrue forever without GC. v0.1.75 also
  reports/reclaims **frozen mirrors** — a mirror whose canonical is ALIVE but no longer
  relevant here (a dropped stack): `--pull` can't refresh it (irrelevant short-circuits)
  and the orphan scan can't see it (the canonical exists); reclaim is safe by construction
  (a replica of a live canonical — the next `--pull` re-pulls it if the stack returns).
  Report-only by default; `--apply` deletes the file + its index pointer. **Only** touches
  `global_ref:` mirrors — never a project-authored fact, even on a name collision.
  Dead-edge provenance (canonical lists a project that no longer holds the mirror) is
  reported, not auto-pruned (absence-of-mirror is too weak a signal to write global
  state on — a renamed store also "holds nothing").
- `--promote PROJECT_DIR LOCAL_FACT [CANON_NAME]` — hand a project-authored LOCAL fact
  UP to the canonical global store, then convert the origin's own copy into a managed
  mirror — the local→canonical direction symmetric to `--pull`, driven by the Phase-1
  promotion re-audit. **Single-shot** (deliberately NOT "atomic" — promote()'s own docstring
  says it is *not crash-atomic*; an interrupted process can leave partial state, though the
  canonical CREATE itself is exclusive per Track D-2b): one completed op writes the canonical,
  records provenance, rewrites the origin copy as a `global_ref:` mirror, and (on a rename)
  removes the old-named local file + its index pointer — so a COMPLETED promotion never leaves
  the dup or orphan a hand-done hand-off would (a left-behind project-authored copy is a
  non-mirror `--gc` never reclaims, and on the next `--pull` it shadows or duplicates the
  canonical).
  `CANON_NAME` defaults to `LOCAL_FACT`; pass it to RENAME (`_`→`-` / drop a date) or to
  DEDUP onto an existing canonical (whose CONTENT is **never overwritten** — only the
  origin side is reconciled, plus the origin is appended to the canonical's `projects:`
  provenance). It also refuses to clobber a DISTINCT project-authored fact already sitting
  at `CANON_NAME`, and the reserved index name `MEMORY`. Refuses a fact that is already a mirror, a non-replicable scope
  (must be `stack-general`/`user-global`), or a `stack-general` fact with no `stacks:`
  (it could match no project). The **model** owns the re-scope (sets `scope`/`stacks` on
  the local fact first) and the global `MEMORY.md` index line; the op owns the file
  mechanics + the origin's always-loaded index pointer.

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
- **The native truncation CLIFF + usage telemetry (v0.1.63, Phase A)** — distinct from the curation
  target above: Claude Code hard-truncates the index at load ("The first 200 lines of `MEMORY.md`, or
  the first 25KB, whichever comes first, are loaded at the start of every conversation" —
  code.claude.com/docs/en/memory, verified 2026-07-04; truncation is SILENT). Encoded as
  `NATIVE_INDEX_CAP_BYTES`/`NATIVE_INDEX_CAP_LINES` in `memory_status.py`; seeded as
  `budget.index.cliff_pct` (exact bytes/lines — `est_tokens` deliberately not involved); report +
  dashboard go red at `CLIFF_NEAR_FRACTION` (80%). Hook-cost telemetry rides the same seed
  (`fat_hooks`/`hook_max_tokens`, threshold `HOOK_TOKEN_WARN`); recall-utility telemetry is
  `extract_signals.py --recalls --into <seed>` → the `usage` block (organic fact-body reads,
  dream-span excluded; **0 reads = absence of evidence, never "unused"**). Design:
  `docs/index-usage-and-budget-ladder.spec.md`.
- **The HARD CEILING (v0.1.66, Phase B)** — the budget ladder's real-harm rung, a **second,
  independent signal** beside the target gate (never a re-key of `remediation.required`, whose
  target-keyed semantics the dream-beta-tester's `CHK-REM-SEED-CONTRACT` oracle pins):
  `INDEX_CEILING_FRACTION` (0.6) × the native 25KB byte cap → `INDEX_CEILING_TOKENS` (≈3840 est tok,
  ONE canonical est-token number — the line axis stays cliff_pct's job). Drives: the M1 pull-hold +
  the `--evict` gain-gate (`sync_global` passes it at the call site — v0.1.73: the gate is an A/B replay
  of the actual pull plan with `freed` MEASURED from the live index line, refusing a mirror/unindexed/
  gainless evict; the over-TARGET amber band still receives pulls freely) and the
  `remediation.over_ceiling` seed flag (a SIBLING of `required`,
  rendered red on the dashboard gauge, the Phase-0 report, and the HTML meter). **Structurally
  standing-justify-independent** — the comparison never reads `standing_justify`, so suppression
  can't hide it and there is no justify escape. Write-time fat-hook lint rides the same release
  (`_fat_hook_warning` in `sync_global` — every written pointer > `HOOK_TOKEN_WARN` warns on stderr,
  naming the canonical's description; never truncates). No real fleet store is near the ceiling
  today — it is a backstop, exercised by synthetic fixtures.
- **The DEMOTION TRIAGE + the miss loop (v0.1.67, Phase C)** — the policy leg that consumes Phase A's
  accrued data. `memory_status.usage_history` aggregates the cycle log's `usage` blocks (reads merge
  from EVERY window — positive evidence always vetoes; only full-fidelity, parseable windows are
  PROBATIVE for zero-read evidence); `demotion_candidates` is the `*_candidates`-family rank —
  eligible iff a fact has ≥ `_DEMOTION_MIN_WINDOWS` (3) per-fact zero-read probative windows AND is
  indexed, non-mirror, 0-reads-ever, non-KEEP-description, never-missed, and not counter-justified
  (`demotion_justify` in the state file, a per-item delta-detector re-firing at
  +`_DEMOTION_JUSTIFY_REFIRE` windows). Ranked by hook cost, capped at `_DEMOTION_BOTTOM_K`; seeded
  as the record's `demotion` block; DORMANT on every real node today. Dispositions
  (demote-to-archive / compress / merge-to-stub / counter-justify) are report-then-apply `entries[]`
  rows — NO deletion under this policy. The **miss-detector** closes the loop: `--recalls --before
  <snapshot>` classifies organic reads by WINDOW-START tier; an archived-tier read = `usage.misses`
  (a demotion error → re-promote; permanently vetoes future candidacy). `--recalls --into` also
  STRIKES just-read stems from the seeded `demotion.surfaced` (current-window blindness, closed
  deterministically). Fleet evidence: `sync_global --utility` (mirror-attributed per-canonical reads
  + `fleet_tax` = pointer × holders vs the warn-only `GLOBAL_FLEET_TAX_ADVISORY`) — the gc lever's
  evidence table; decisions stay content-gated. Fleet windows are gated on each mirror's
  **`global_ref_since` evidence-clock stamp** (v0.1.78, `docs/evidence-clock-stamps.spec.md`):
  carried across refreshes when the canonical's BODY is unchanged (a description tweak no longer
  wipes accrued zero-read windows — the starvation an audit measured), reset on a real body change
  (old zero-reads don't indict new content), mtime-fallback on unstamped mirrors. Design + the evidence-gate rationale:
  `docs/index-usage-and-budget-ladder.spec.md` §Phase C.
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
  `claude-code` stack (a real `.claude/` dir or a `SKILL.md` file — the only two markers
  `detect_stacks` actually checks) matches almost every CC repo,
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

**Two symmetric Phase-1 re-audits walk the cascade by CONTENT (detect-and-offer, never auto):**
- **Demotion** (over existing `user-global` canonicals) — a fact whose content now carries a
  fleet-VARYING precondition would route lower; offer to re-scope/delete it (backstops G2.3 above).
- **Promotion** (over a project's own authored, non-mirror local facts) — a local fact whose content
  is fleet-CONSTANT or stack-reusable should route UP. `memory_status.py` surfaces the seed
  (`_promotion_candidates`: authored facts that are unscoped, non-mirror, `type` ∈ {feedback,
  reference}; capped at `_PROMO_CAP`). Promotion
  is the **higher-blast-radius** direction (a wrong/stale promotion replicates an always-loaded pointer
  into every same-stack project, undoable only by a global delete + fleet GC), so gate it STRICTER:
  conservative floor, a Phase-3 re-verify AND a point-in-time/supersession screen (a dated snapshot is
  not a durable rule), dedup vs existing canonicals by content, and a per-pass cap. On confirm, the
  `sync_global.py --promote` op performs the hand-off (canonical write + origin→mirror + provenance +
  rename cleanup; see the op list above).

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
