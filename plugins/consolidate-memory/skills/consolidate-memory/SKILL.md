---
name: consolidate-memory
description: >-
  Consolidate this project's durable memory — the agent equivalent of sleep-time
  memory consolidation. Reads recent session work + git history, verifies every
  candidate fact against the LIVE codebase, and reconciles BOTH memory stores (the
  repo's MEMORY.md/AGENTS.md/CLAUDE.md and Claude's private per-project
  auto-memory), correcting or pruning stale entries. A deliberate, write-heavy
  checkpoint — invoke ONLY when the user explicitly asks to consolidate / reconcile
  / checkpoint / "settle" / "save what you learned" / "dream" their memory, or
  "what should I remember from this?", usually after a substantial session or when
  memory feels stale or self-contradictory. Do NOT trigger on other senses of
  "memory": RAM/VRAM/GPU memory, an embedding or style cache, a `memory_limit`
  setting, a database, a casual "remember to do X" aside, or a plain session recap
  with no intent to persist.
---

# Consolidate Memory

A deliberate pass that turns the fluid experience of a work session into **verified,
durable facts** — and keeps the project's two memory stores accurate and
non-contradictory. It's the agent analogue of what sleep does to memory: replay
recent experience, keep what's true and useful, discard what isn't. Where Claude Code's built-in
Auto Dream consolidates each project in place, this pass adds the two things it doesn't —
**verification against the live code** and a **cross-project** shared store.

The defining idea is below: Claude Code loads memory into context in **tiers**, so a
consolidation pass is really an act of **curating what loads, when, and at what cost** —
not just tidying a flat store. The exact paths, formats, and recipes live in
**`references/harness-map.md`** — read it in Phase 0 and whenever you need a detail.
Don't restate it from memory; the substrate drifts, so re-confirm it (see "verify your
own context" below).

## How your memory actually loads (the model everything here optimizes)

The product of a consolidation pass is not tidy files — it is **correct,
well-budgeted context loading**. A fact only helps a future session if it reaches
that session's context, and every fact that loads costs tokens and frames your
attention. Claude Code loads memory in three tiers, and each fact belongs in the
one that fits how often it's needed:

1. **Always-loaded (deterministic — paid every single session):** `CLAUDE.md` and
   the auto-memory **`MEMORY.md` index** are injected into context on every session.
   This is the most expensive, most powerful tier. A stale or wrong line here taxes
   and misleads *every* future turn. Treat it as scarce: only facts that frame the
   whole project earn a permanent slot, and they must be lean and exactly right.
   The two files differ in **who owns them**: the auto-memory index is Claude's to
   curate freely; `CLAUDE.md` is the user's hand-authored, committed, team-shared
   instructions — write it as a *guest*, not an owner (see Phase 4).
   Confirm what's actually injected by looking at your own context block — currently
   that's `CLAUDE.md` + the auto-memory `MEMORY.md` index (NOT repo `AGENTS.md` or
   repo `MEMORY.md`), but verify rather than assume.

2. **Recall key — the always-loaded hook that triggers an on-demand read:** a fact's
   *body* is NOT auto-injected by relevance — Claude Code has no ambient "surface it
   when it matches" mechanism (the official docs: topic-file bodies "are not loaded at
   startup; Claude reads them on demand"). What loads every session is the fact's
   one-line **index entry**, built from its `description:`. So the `description:` is a
   **recall key, not a summary** — write it as the cue that, sitting in the
   always-loaded index, makes a future session decide to *read* this fact. A weak
   description hook leaves a true, useful fact invisible: nothing tells the agent to
   open it. This lever has no equivalent in a single-store, per-project consolidator like Auto Dream; use it well.

3. **On-demand (you read them when relevant):** repo `AGENTS.md` / `MEMORY.md` and
   the fact-file *bodies*. These are not auto-injected, so they don't tax every
   session — optimize them for completeness and accuracy for the team/yourself, with
   less leanness pressure than tier 1.

Two physical stores back these tiers (see `references/harness-map.md` for the slug
rule + frontmatter schema): **repo-committed docs** (`MEMORY.md`/`AGENTS.md`/
`CLAUDE.md`, shared, in git) and **private auto-memory** (`~/.claude/projects/
<slug>/memory/`, per-user, not in git). Reconciling them — and never duplicating a
fact across them — is core; but place each fact by its **tier** (how it loads), not
just its store.

**Cross-project (the global tier).** Some facts aren't project-specific — user
preferences, environment gotchas, stack-general patterns (e.g. a `gh pr edit` env
bug, a typed-stubs preference, RAG/GPU lessons reusable across same-stack
projects). Those get a **`scope`**: `project-local`, `stack-general`, or
`user-global`. Cross-scope facts live canonically in a **global store**
`~/.claude/memory/`. But recall is **slug-scoped** — a project only auto-recalls its
*own* store — so global facts must be **replicated** into each project's store to
surface there (they don't auto-cross). `sync_global.py` does that replication; the
phases below call it. (Renaming a project dir changes its slug and **orphans** its
old auto-memory — another reason the canonical copy lives in the slug-independent
global store.) See `references/harness-map.md` § "cross-project". **Phase 2 decides each
fact's scope by a hard cascade** (Gate 0 → `project-local` · Gate 1 → `stack-general` ·
Gate 2 → `user-global`), keyed on whether a fact's dependency is *fleet-constant* (the
user's substrate — can be global) or *fleet-varying* (a per-project stack — at most
`stack-general`).

## Why this is its own ritual (and not automatic)

Consolidation **writes** memory that the team and every future session rely on, and
it costs real work (git history, verification fan-out). So it runs only when
explicitly requested — never opportunistically mid-task. The payoff compounds: a
right fact in the always-loaded tier silently sharpens every future session; a wrong
one silently degrades it. That asymmetry is why **verification is the heart of this
skill**, and why facts that load deterministically get the harshest scrutiny.

## Workflow

Work the phases in order. Phases 0–3 are read-only investigation; Phase 4 is the
first write, and you **show the user the proposed consolidation before writing it**
(report-then-apply) so a consolidation pass never silently churns committed docs.

### Rigor modes — scale ceremony to pass magnitude

Not every pass deserves the same machinery. `memory_status.py` computes a **suggested
rigor tier** from an early magnitude signal — `magnitude = git_commits +
session_candidates` (both *flows*: work done *this* cycle). It is a **HINT, not a gate**,
and is **derived from the magnitude** (never a stored label that could drift): in Phase 2
you set the curated `session_candidates` — itself your judgment entering the magnitude —
and the tier follows. You may still run heavier or lighter ceremony than the tier implies,
with explicit rationale; that override shows up in what you verify/record, not a mutated label.

- **LIGHT** (magnitude ≤ 2): verify inline; minimal ceremony.
- **SUBSTANTIAL** (3–7): fan out parallel verification subagents (Phase 3) and require a
  **2-source check** for anything bound for the always-loaded tier; run the
  re-verify-stale + GC sweep (Phase 5).
- **HEAVY** (≥ 8): everything in SUBSTANTIAL **plus** a completeness critic ("what did we
  miss or mis-verify?") and a **hard stop** on any write that pushes the always-loaded
  tier over budget without an explicit prune.

**The over-budget remediation GATE (v0.1.18 — independent of tier).** When the always-loaded **index is
ALREADY over budget** (`remediation.required`), the HEAVY hard-stop applies at **ANY** tier: the pass may
**not net-grow** the over-budget index, and it must run the **remediation triage** (Phase 5) and act on it —
**prune-or-justify**. This is the teeth the advisory `prune_pressure` lacked (a real over-budget dream once
*grew* the index 5.5× over). The gate is **routed** by `remediation.lever`: `prune` (local-authored
overflow → triage + evict candidates), `gc` (mirror-dominated overflow → the global demote/GC lever; a local
prune is futile), or `justify` (over budget but nothing safely prunable → record an explicit justification,
never deadlock). It NEVER auto-deletes — the triage *offers*; you confirm (Safety rule).

A separate **prune-pressure** flag (set when the index is over budget OR the store
already holds ≥ a threshold of facts) forces **prune-or-propose this pass regardless of
tier** — a large store needs pruning even on a tiny pass. `memories_reviewed` drives
THIS, never the magnitude tier: it is a cumulative *stock*, so folding it into magnitude
would peg every mature project to HEAVY (the bug this design avoids).

The bands are **provisional, tunable defaults**, kept deliberately as a coarse HINT: a
sensitivity probe (v0.1.4) found magnitude agrees with a rich needed-rigor rubric on only
~half of passes — the features that truly decide rigor (always-loaded-bound count,
cross-store conflicts, prune-pressure) are known only LATE (Phase 2–3), so an EARLY
magnitude proxy can't be precision-tuned (`prune_pressure` + the always-loaded 2-source
rule cover its blind spots). So `(2,7)` is kept on that basis. v0.1.4 ships the apparatus to
make a real calibration POSSIBLE: the model records the realized `rigor.applied` (+
`override_reason` on an override), and Phase-5 `--persist` appends each rendered record to a
per-project `.consolidation-log.jsonl`, so magnitude→(applied, outcome) data finally accrues.
**Honest caveat:** `applied` is **self-reported** — it catches OVER-rigor (ran heavy, didn't
need it) but NOT under-rigor (ran light, missed something); the dangerous direction needs
LONGITUDINAL miss-detection (a later pass finds what an earlier one missed), which the log
enables but which remains future work. And never calibrate the bands against the dashboard's
OUTCOME banner — mature passes are systematically high-magnitude / low-outcome, so fitting
`(magnitude, outcome)` fails UNSAFE (it biases toward LESS rigor). The rigor tier (an
*input*-based effort estimate) is a **distinct quantity** from the dashboard's outcome
banner (an *output*-based label from write counts): they share no scale, and a pass can
legitimately read "HEAVY" rigor yet "LIGHT" outcome (much to review, little durable to
write). The dashboard labels both so they never read as one number.

### Phase 0 — Locate data + the high-water mark

Run the bundled helper (it derives paths, inventories both stores, and computes the
git range since the last consolidation — don't hand-derive these):

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/memory_status.py
```

It prints: the repo docs, the **user-global `~/.claude/CLAUDE.md`** (read-only — a
flat always-loaded cost in *every* project, never a write target), the private
auto-memory files, the transcript inventory (report only — **never bulk-read the
`.jsonl`; it can be tens of MB**), the last consolidation marker (`commit` +
`timestamp`), and `git log <marker>..HEAD`. If
there's no marker, treat this as the first consolidation and scope to the recent
git log + the current session.

**The no-op rule (v0.1.37 self-heal pivot · v0.1.42 cold-start bootstrap).** Report "Nothing to consolidate"
and STOP **only when the local store is EMPTY *AND* the cross-project network is empty** (`cross_project.
global_store_facts == 0`, from the `--seed`). TWO non-stop cases PROCEED past Phase 0:
- **MAINTENANCE pass** (NON-empty store, 0 commits): health debt (dangling/stale) + NEW sibling-promoted facts
  to pull → Phase 1 `sync_global --pull` (AUTO-HOLDS, M1, any new-global pull that would *leave* the index over
  budget — `held N`) + Phase 5 (health: dangling-fix / prune-or-justify).
- **COLD-START BOOTSTRAP** (EMPTY local store, ~0 commits, but `global_store_facts > 0` — a fresh/dormant repo in
  an established fleet): the network holds the user's OWN real facts, so do NOT STOP and "let it accumulate".
  PROCEED to a **bootstrap** — Phase 1 `sync_global --list .` **first** (surface which globals are RELEVANT — the
  real `is_relevant`/stack filter), **then** `--pull` (M1-bounded). Scope it to **pull + Phase-5 health ONLY** (an
  empty store has no session signal to consolidate — Phase-2/4 *authoring* is the genuine from-scratch case, which
  correctly stays a STOP; never fabricate/force-seed facts). **Graceful degradation:** if `--list` shows **0
  relevant** (network non-empty but all-irrelevant to this repo's stack/domain), it degrades to an HONEST no-op —
  the cross-project section reports "network checked · 0 relevant", NOT a hollow "bootstrapped".
Both PROCEED cases are signal-driven from Phase-0 data (the `maintenance` block / the seeded `global_store_facts`),
not a thing to remember. Set `maintenance.pivoted=true` when you run a maintenance/bootstrap pass; a pass that
writes no new facts renders a **MAINTENANCE PASS** banner (not a misleading NOTHING/NO-OP). The bootstrap's
`--pull` writes (mirrors + index pointers) render normally via `cross_project.pulled`. A TRUE no-op — empty local
store AND empty-or-all-irrelevant network — is the only case that ends at Phase 0. It also prints a
**provisional rigor tier** (from `git_commits`; finalized in Phase 2 once you curate
`session_candidates`), any
**prune-pressure** flag — see *Rigor modes* above — and (when commits have accrued since the last
dream) a **dream-timing advisory**: a no-nag nudge that this is a good consolidation boundary. It's
advisory only (the skill never auto-fires — see *Why this is its own ritual*); its prospective use is
via `cm status` *outside* a dream.

Phase 0 also **flags slug-orphans** (a near-duplicate sibling slug — the rename-orphan
signature, since a dir rename changes the slug and strands the old slug-scoped store)
and **schema drift** (a fact missing the documented `node_type`, a malformed
`scope`/`originSessionId`, or an index↔file mismatch) and **OFFERS** reconciliation /
backfill — but the model decides in Phase 4; Phase 0 never auto-applies. (Absence of the
injected `scope`/`originSessionId` is a separate *optional* backfill advisory, not drift —
see `references/harness-map.md`.)

Then **seed the cycle record** — the structured data that becomes the final
dashboard (see "Output" below). Re-run the helper with `--seed` to capture the
measured before-state (scope, before-budget, marker) into a working file you'll fill
in as you go:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/memory_status.py --seed   # writes a PER-PASS cycle file + prints its path
```

`--seed` writes the seed to a **per-slug** path under the temp dir (`cm-cycle-<slug>.json`) and **prints
it** — use THAT exact path through every phase and in the Phase-5 render. Do NOT use a shared
`/tmp/cycle.json`: a concurrent dream of another project would clobber it, grafting that project's
scope/remediation onto yours (v0.1.20 fix). The path is deterministic (slug-derived), so you can
reconstruct it in any later phase. (`--json` still streams the seed to stdout for ad-hoc/`cm seed` use.)
Add to that file through the phases (candidates, verification tallies, entries, after-budget, health) and
render it at the end. Set `session` to the active session id.

Then capture the **BEFORE audit snapshot** (v0.1.22) — a deterministic content-hash of the memory store +
the CLAUDE.md hierarchy, so Phase 5 can emit a script-OBSERVED mutation trail (not just your narrated
`entries[]`):

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/memory_status.py --snapshot   # writes a per-slug BEFORE snapshot + prints its path
```

Keep that path for Phase 5's `--audit`. (Phase 0 also now reports the **whole CLAUDE.md hierarchy** — the
nested files CC loads hierarchically, with a `worst_path` "a session in <dir> pays ~Nk/turn"; read-only,
detect-and-report — a heavy nested CLAUDE.md is a v0.1.23 optimization target, not a gate.)

### Phase 1 — Orient

Read fully: both `MEMORY.md`s (repo + auto-memory index), the auto-memory fact
files, and skim `AGENTS.md`/`CLAUDE.md` for the sections facts would land in — and,
for `CLAUDE.md`, note its existing structure and voice: you'll treat it as read-mostly
and conform to it, never restructure it (see Phase 4). Build a mental model of what's
already recorded so Phase 2 can dedup against it.

Then **pull relevant global facts** so this project recalls them and Phase 2 can
dedup against them too (cross-project step; safe + additive). **First `--list` (read-only), then `--pull`**
(v0.1.42, B1): the `--list` surfaces *which* globals are relevant + present/missing/held BEFORE `--pull` writes
them — so the enrichment is legible (you see the bootstrap/refresh picture + can reason about budget) instead of
a blind pull. On a COLD-START bootstrap (empty store, rich network — see the no-op rule) this `--list` is the
relevance filter that decides PROCEED-vs-honest-no-op; on a normal pass it's a cheap read that costs nothing:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/sync_global.py --list .   # surface relevant/present/missing/held (read-only)
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/sync_global.py --pull .   # then replicate (M1 auto-holds an over-budget pull)
```

This replicates any `user-global` (and stack-matching `stack-general`) facts from
`~/.claude/memory/` that are missing here, and **refreshes any stale mirrors** whose
canonical changed (the script writes both the fact file and its index pointer). It also **AUTO-HOLDS**
(M1) any new-global pull that would *leave* the always-loaded index over budget — reported as `held N`.
Read its output and record `cross_project.pulled` (newly replicated), `cross_project.refreshed`, **and
`cross_project.held`** (the `held N` count — new globals withheld to protect the over-budget index; the
dashboard renders it as the `⚠ held N — prune/justify to receive` lever) in the cycle record. If nothing
is missing/stale/held, no-op.

Then **re-audit the existing `user-global` facts — the backstop for the promotion cascade's weak
applicability gate (G2.3 — see Phase 2).** Read each canonical's **body** in `~/.claude/memory/` and
**re-walk the cascade by CONTENT**; any fact that would NOW route lower — e.g. its content carries a
*fleet-VARYING* precondition (`mypy`, "only when cutting a release") rather than the user's
*fleet-CONSTANT* substrate — is a **demotion candidate**. Judge by content, **NOT `holders`/adoption**
(every `user-global` fact `--pull`s into *every* project, so `holders` is pull-activity, not fit) and
**NOT `stacks:` tags** (a fact tagged `release` may be universal by content). These are
**detect-and-offer**: surface each in the Phase-4 report as one `entries[]` row (`action: reconciled`,
reason `"demotion candidate → would route to <scope>"`); on your confirmation, update that **same row
in place** to `corrected` (re-scope) or `deleted` (canonical delete + Phase-5 GC) — one fact, one
entry; a declined candidate stays `reconciled`. Never auto-demote.

Then re-audit **this project's own local store for PROMOTION — the symmetric, HIGHER-STAKES counterpart**
to the demotion pass. `memory_status.py` (Phase 0) surfaces a **"promote?"** signal listing **authored,
non-mirror, unscoped** facts whose `type` leans cross-project (feedback/reference) — a **weak seed, judged
by CONTENT, not the tag.** For each, **re-walk the Phase-2 cascade by content**: a fact gated only by the
user's *fleet-CONSTANT* substrate routes to `user-global`; one reusable on a *specific, narrow* same-stack
(a RAG/GPU technique lesson) routes to `stack-general`; anything project-specific stays put. **Promotion is
the higher-blast-radius direction** — a wrong/stale promotion replicates an always-loaded pointer into
*every* same-stack project and is undoable only by a global delete + fleet-wide GC — so gate it **stricter
than demotion**: the conservative floor (when in doubt, stay local) plus **two distinct screens** — (a) the
Phase-3 **re-verification** that the fact is still TRUE against the live tree, AND (b) a **point-in-time /
supersession screen** (a dated snapshot — "X SHIPPED 2026-05-27", a one-off A/B result — is NOT a durable
rule; check for a newer same-topic fact that supersedes it). Only durable, current lessons promote. **Dedup
against existing canonicals by CONTENT** (a differently-named local fact that restates a global one — e.g.
a local `validate-each-increment` vs the global `gated-spec-driven-change-workflow` — reconciles ONTO the
existing canonical via the rename/dedup path, never a second copy). **Cap/stage** the review (the feedback
seed first, technique facts a later pass) — never rubber-stamp a batch. These are **detect-and-offer**:
surface each as one `entries[]` row (`action: reconciled`, reason `"promotion candidate → would route to
<scope>"`); on your confirmation, set `scope`/`stacks` on the local fact and run the Phase-4 hand-off,
updating that **same row in place** to `corrected` (one fact, one entry; a declined candidate stays
`reconciled`). Never auto-promote.

### Phase 2 — Gather candidate claims (claims-first)

Produce a short, explicit list of **discrete candidate facts** — each a single
verifiable sentence. There are **three sources, and they map to different memory
types** — don't over-index on any one (a probe of this harness showed the human's
typed messages are <1% of the transcript and carry only the *feedback* slice; the
*project* facts live in git and in observed behavior the human never typed):

1. **`git log <marker>..HEAD`** (commit bodies) → **project facts** (what changed +
   why). The strongest, highest-precision source — it happened and it's in git.
   `memory_status.py` (Phase 0) already lists this range; read the commit bodies.
2. **Session signal** → **feedback/preferences** (human turns) + **gotchas** (error
   tool-results). Don't read the raw transcript — run the extractor, which streams
   it, scopes to the marker, drops harness/skill noise, **omits credential-shaped
   turns** (secrets firewall at retrieval), and returns ranked, structured, scoped
   candidates:
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/extract_signals.py --json
   ```
   **Run it, or record why you didn't.** The extractor reads the compaction-proof *on-disk*
   transcript — exactly what a long/compacted session needs, since when your in-context view is the
   degraded source, your memory of the session is NOT a substitute. If you deliberately skip it,
   record an explicit skip-justification as an `entries[]` note (it always renders; `rigor.override_reason`
   only shows on a tier override, so it can't carry a no-override skip) so the skip is a visible
   decision, not a silent gap.
3. **Existing memory entries that look stale** — candidates for re-verification.
   `memory_status.py` (Phase 0) lists a **"Re-verification candidates"** section: facts
   untouched since the last consolidation marker (mtime ≤ marker), which may have
   silently gone stale. Treat them as re-verify candidates in Phase 3.

For each candidate also assign a **`scope`**: `project-local` (specific to this
repo's domain), `stack-general` (a pattern reusable on a *narrow* same-stack — e.g.
the typed-stubs/`mypy` preference), or `user-global` (a preference or environment fact
that holds across the user's whole fleet — e.g. the `gh pr edit` env gotcha). Scope is
independent of tier; it pre-stages cross-project sharing and sharpens "what belongs where."

**Scope is a fleet-wide cost lever** — a `user-global` fact replicates an always-loaded
index pointer into *every* project (G facts × P projects) — so decide it by a **hard
cascade, not vibes.** First the load-bearing distinction:
- **Fleet-CONSTANT substrate** — the user's OS/account, an always-present CLI (`gh`), the
  Claude Code harness itself: present in *all* their projects. A gotcha/behavior about it
  is `user-global` — it is **not** a disqualifying precondition.
- **Fleet-VARYING precondition** — a stack/tool/workflow in only *some* projects (`mypy`,
  `pytest`, "projects that cut releases"): scopes a fact to `stack-general`.

Judge by the fact's **content, not its `stacks:` tags**: a workflow for *any* substantial
change is fleet-constant (→ `user-global`) even if tagged `release`; a rule that applies
*only when cutting a release* is fleet-varying (→ `stack-general`). Same tags, different scope.

Then walk the cascade in order (it is total; the conservative floor is `project-local`):
1. **Gate 0 — project-specific?** about *this* repo's domain/code/history → `project-local`.
2. **Gate 1 — fleet-varying precondition?** Judge the fact's *content* dependency, not its
   `stacks:` tags. **First:** if the only dependency is the fleet-CONSTANT substrate (the
   harness/`claude-code`, `gh`, OS/account), it does **not** trip this gate → straight to
   Gate 2. **Otherwise**, if it holds only given a fleet-varying stack → `stack-general`,
   **iff** (S1) it names a *specific* such stack and (S2) holds for *all* projects on it
   (else → `project-local`).
3. **Gate 2 — `user-global`?** ONLY if ALL hold (any miss → `project-local`): **G2.1** no
   fleet-varying precondition (constant substrate exempt) · **G2.2** a user/env property,
   not a codebase one · **G2.3** you can name ≥1 *existing, different* project where it
   would apply (+ the mechanism) · **G2.4** not already in the always-loaded
   `~/.claude/CLAUDE.md`, nor re-derivable from each project's code/git · **G2.5** durable,
   not transient/churn-prone.

(Cost intuition behind Gate 1's carve-out: a `stack-general` fact on a *common* stack like
`claude-code` would behave like a second `user-global` tier — which is exactly why the
near-universal substrate routes to Gate 2, not `stack-general`.) When in doubt keep it local:
promoting later is cheap; un-promoting means a global delete + fleet-wide GC (Phase 4/5).

For each candidate, decide its **tier** (always-loaded / recall / on-demand — the
model above) and therefore its store and shape, and check whether it's already
recorded (dedup against Phase 1 — including across the two stores). Drop anything
the repo already records as code or git history; keep the non-obvious *why*. Be
especially stingy about proposing anything for the always-loaded tier — it must
earn its per-session cost.

→ **Cycle record:** set `scope.session_candidates` to the count of **curated, discrete
candidate facts** you carried into Phase 3 (after dedup — **not** the raw extractor
`surfaced` count, which includes every non-noise turn + error result and runs far
higher; feeding that in would over-state magnitude and peg the tier to HEAVY). Then set
`rigor.phase = "final"`. The rigor **tier is DERIVED** from `git_commits +
session_candidates` at render — you don't store a tier label (so it can't drift from its
magnitude); your curated `session_candidates` IS your judgment entering the magnitude. If
you choose heavier or lighter ceremony than the magnitude implies, do so with explicit
rationale — **record the ceremony you actually run in `rigor.applied`
(LIGHT/SUBSTANTIAL/HEAVY) and, when it differs from the suggested tier, why in
`rigor.override_reason`** (v0.1.4). The override also shows up in what you verify/record
(`verification.method`, `entries`), never a mutated suggested label (it's a hint, not a
gate). The helper already filled `git_commits` and `memories_reviewed`.

### Phase 3 — Verify (the heart; parallel)

Every candidate is verified against the **live tree** before it can land. **Scale the
verification to the rigor tier** (see *Rigor modes*): a LIGHT pass may verify inline; a
SUBSTANTIAL or HEAVY pass MUST fan out — spawn Explore / general-purpose subagents to
verify batches of claims concurrently (the parallel enhancement over a serial single-store pass),
and at SUBSTANTIAL+ give anything bound for the always-loaded tier a **2-source check**.
Hand each subagent the **specific claims** to check — never "read the transcript."

Verify with the recipes in `references/harness-map.md` § "verification recipes":
file/symbol existence (`grep`, `test -e`), claim-matches-current-code (read the
cited lines), decision-landed-in-git (`git log -S`), doc self-consistency (e.g. does
`AGENTS.md`'s test count match `pytest -q`?).

Be **recall-biased**: a claim that can't be verified is flagged, not silently kept.
Outcomes per claim: **confirmed** (lands), **stale/wrong** (correct it to the real
current state, cite it), **unverifiable** (drop, or keep only if explicitly marked
unverified and the user wants it).

→ **Cycle record:** tally `verification.confirmed` / `corrected` / `unverifiable`,
and set `verification.method` (`inline` or `subagents`).

### Phase 4 — Consolidate (report, then apply)

First, **present the proposed consolidation to the user**: what you'll add, correct,
or delete, in which **tier/store**, and why — a short diff-like summary. This matters
because Phase 4 writes committed docs and persistent memory; the user should see the
churn (and the per-session cost of anything headed for the always-loaded tier)
before it happens. **Call out any proposed `CLAUDE.md` edit explicitly** — it is
committed, team-shared, AND always-loaded, the widest blast radius of anything here;
make declining it the easy default. **Honor the rigor tier + prune-pressure** (see
*Rigor modes*): if `rigor.prune_pressure` is set, prune-or-propose this pass regardless
of tier; at **HEAVY**, do not apply any write that pushes the always-loaded tier over
budget without an explicit prune (hard stop — surface it and prune first). Then apply,
placing each fact in its tier and optimizing it for how that tier loads:

- **Always-loaded tier — two files, two very different dispositions:**
  - **Auto-memory `MEMORY.md` index** (Claude's own store — you own it; this is the
    real always-loaded write target): keep it lean — prune a low-value pointer when
    adding one. `memory_status.py` gates it against `INDEX_TOKEN_BUDGET`; the dashboard
    renders a ⚠ when `over`. If over budget, **first check what's driving the
    overflow** — `--tokens` and the dashboard attribute the index cost to
    mirror-vs-local (`mirror_index_tokens`). If it's **mirror-dominated** (replicated
    `global_ref:` cross-project facts), local pruning is *futile* — Phase 1's `--pull`
    re-creates a deleted mirror next cycle; the only effective lever is to
    **demote/delete the canonical in `~/.claude/memory/`**, then GC the orphans
    fleet-wide (Phase 5). Local pruning works only on **project-authored** pointers.
    The index holds *pointers only* (`- [Title](file.md) — hook`), never fact bodies.
  - **Repo `CLAUDE.md`** (user hand-authored, committed, team-shared — you are a **guest WITH permission to
    tidy, ON THE RECORD**, v0.1.24): you MAY relocate/compress/prune the CLAUDE.md hierarchy, but ONLY **gated
    per-change** (report-then-apply, explicit approval) and **audited** (the Phase-5 `--audit` recorder captures
    every change). The hard invariants:
    - **The DIRECTIVE always STAYS; relocate only the ELABORATION.** CLAUDE.md is always-loaded (enforced EVERY
      session); a committed doc is on-demand (enforced only if a pointer cues a read). Relocating a *binding
      directive* silently drops it a tier — **enforcement erosion**, invisible in a content diff. So a relocate
      SPLITS a heavy section: KEEP every directive (the binding rule) + add a one-line pointer in CLAUDE.md; MOVE
      the elaboration (rationale / examples / mechanics) to a committed doc. **NEVER relocate a directive.** Two
      checks, in order: (1) run `_has_normative_marker` on the chunk you intend to MOVE — a hit (MUST/NEVER/
      ALWAYS/SHALL/REQUIRED/DON'T) means it IS a directive, keep it. This marker is **SUFFICIENT, NOT NECESSARY**:
      a MISS does NOT license a relocate — the DOMINANT directive form is the **bare imperative** ("Keep src/
      pyright-clean", "Run the gate before pushing") which carries NO marker. (2) So you must AFFIRMATIVELY judge
      the chunk is non-binding *elaboration* before moving it; when unsure, keep it. `memory_status.py --sections`
      flags heavy sections + `has_directive` per section (MECHANICAL hint, same sufficient-not-necessary caveat —
      it does NOT decide the split). The per-change proposal MUST show: **directive-that-stays · the pointer ·
      elaboration-that-moves · the target doc** — the human-approved proposal is the ultimate guard; show it so
      enforcement-preservation is visible and rejectable.
    - **Relocate targets: EXISTING committed in-repo docs only.** Validate EVERY target with
      `memory_status.valid_relocate_target(path, project_dir)` (in-repo AND not `~/.claude` AND not gitignored —
      relocating into the private store or a gitignored dir is silent team data loss). No fitting target →
      PROPOSE creating one ("relocate to a new `docs/TYPING.md` — create it?") and let the HUMAN create/approve;
      never impose repo structure. **Never create a `CLAUDE.md`** where the repo has none.
    - **compress** (tighten normative prose) is a HIGH-SCRUTINY exception — a rewrite can silently drop a clause;
      explicit per-change approval, show before/after verbatim. **prune** only a *descriptive* line whose
      referenced code/file is grep-confirmed GONE; a *normative* line is NEVER pruned on your judgment — you
      PROPOSE, the human owns the "still wanted?" call (team intent isn't in the tree). Default
      relocate-not-delete.
    - Gated against `CLAUDE_MD_TOKEN_BUDGET` + the whole-hierarchy worst-path (Phase 0) — the relocate lever is
      how you cut an over-budget nested CLAUDE.md without eroding enforcement. The Phase-5 `--audit` conservation
      check flags any CLAUDE.md token drop without matching target growth — that's a relocate whose bytes didn't
      land OR an intended compress/prune; either way **verify it was deliberate** (it fires on authorized
      compress/prune too, by design — confirm, don't dismiss). Don't introduce drift-prone derived stats
      (test/module counts); update an existing such line only if you verified it here.
- **Recall tier** (auto-memory fact files): one fact per file with the frontmatter
  schema, and **invest in the `description:` as a recall key** — it becomes the
  always-loaded index hook, so phrase it as the task-context that should cue a future
  session to read this fact, not a terse summary, or the agent won't know to open it.
  Link related facts with `[[name]]`; pick the right `type`. Then add its one-line
  pointer to the index.
- **On-demand tier** (repo `AGENTS.md`/`MEMORY.md`, fact bodies): optimize for
  accuracy and completeness; these don't tax every session.
- **No cross-store duplication**: if a fact lives in the repo docs, an auto-memory
  entry should point at it, not restate it.
- **Global-scope facts** (`scope: stack-general` or `user-global`) — two paths:
  - **A NET-NEW fact discovered this session:** write the canonical copy to
    `~/.claude/memory/` with `scope`, `stacks: [...]`, and `projects: [...]` (provenance)
    in the frontmatter, add a line to `~/.claude/memory/MEMORY.md`, AND keep a project-store
    copy so it recalls *here* (recall is slug-scoped).
  - **PROMOTING a fact that already exists in this project's local store** (the Phase-1
    promotion re-audit): **don't hand-copy it** — first set `scope`/`stacks` on the local
    fact, then run the scripted hand-off, which writes the canonical, converts this project's
    local copy into a managed mirror, records provenance, and (on a rename) removes the
    old-named local file + its index pointer — so the promotion can never leave a
    duplicate/orphan:
    ```bash
    python3 ${CLAUDE_PLUGIN_ROOT}/scripts/sync_global.py --promote . LOCAL_FACT [CANON_NAME]
    ```
    Pass `CANON_NAME` to normalize the name (`_`→`-`, drop a date) or to **dedup** onto an
    existing canonical (never overwritten). You still **add the `~/.claude/memory/MEMORY.md`
    line** (the op leaves the global index to you — the single writer).
  Either way: other projects pick it up when they next run their own Phase-1 `--pull`; don't
  move a fact out of a project store that currently recalls it (the global copy is additive).
  Record each promotion in `cross_project.promoted` (name + scope), and in that entry's
  **`reason`** capture the **deciding gate + the concrete other project named for G2.3**
  (the promotion cascade — Phase 2), so the scope decision is auditable.
- **Cite** each new/changed entry with the commit SHA or session basename it came
  from, so a future pass can trace it.

→ **Cycle record:** append one object to `entries[]` for **every** decision — not
just writes but also `skipped` and `reconciled` ones, since "what I deliberately did
NOT record, and why" is part of the dashboard's signal. Each:
`{"action": "...", "tier": "...", "store": "...", "scope":
"project-local|stack-general|user-global", "name": "...", "reason": "...",
"citation": "..."}`. After writing, update `budget.*.after` (CLAUDE.md lines, index
lines/bytes, recall-fact count).

### Phase 5 — Prune, GC, verify, measure, update the marker, render

**At HEAVY, run a completeness critic first** (see *Rigor modes*): re-ask "what did we
miss or mis-verify?" — a fact the git range implies but no candidate captured, a claim
marked confirmed on thin evidence — and loop back one pass if it surfaces anything.

**0. Over-budget remediation (v0.1.18 GATE; v0.1.21 standing-justify) — when `remediation.required`.** If Phase 0
flagged the index OVER budget AND the gate is NOT standing-justified, it's a hard gate: you may not finish a pass
that net-grows it. (When `remediation.standing_justified` is true the gate is **SUPPRESSED** — the density was
judged earned at a baseline and the store hasn't grown by Δ since; nothing to do here.) Read the staged triage
(`memory_status.py --triage .`): the INDEX-RELIEF stages are **B** tracker/status (transient) + **C** dated/oversized
(content-review — RANKS, you JUDGE; may be PROMOTE candidates); **R** referenced (in CLAUDE.md / an archive / a
`[[wikilink]]` from another fact — NOT safe to evict; **de-link the surface FIRST**); **A** TRUE orphans (unindexed
AND unreferenced — disk-only, **0 index relief**). vs the durable-keep core. **Relieve NON-DESTRUCTIVELY first
(archive), then act on the routed `remediation.lever`:**
   - **archive (PREFERRED — non-destructive; the proven discipline, v0.1.27):** before pruning or justifying,
     RELOCATE the index pointers of **COMPLETED/MERGED arcs** — work that shipped AND whose durable lessons are
     ALREADY extracted into kept facts — out of the always-loaded `MEMORY.md` into an ON-DEMAND **archive index**
     (e.g. `SHIPPED.md`, an `_is_archive_index` link-list). The fact BODY stays (recallable via the archive); only
     the always-loaded INDEX pointer moves — and the archive is OFF the index budget (on-demand, not measured by
     `INDEX_TOKEN_BUDGET`), so this is the **budget-tier relief**: a lean always-loaded index with nothing lost.
     **The keep-vs-archive call is JUDGMENT with a SILENT failure mode** — archive a *live* lesson and it stops
     being recalled, with nothing to flag it (the recall-tier analogue of CLAUDE.md enforcement-erosion). So
     **KEEP in `MEMORY.md`** anything lesson-bearing, a NEGATIVE / "don't-retry" finding, active state, or a
     directive — **even if it's dated or says "SHIPPED"** (a `… SHIPPED 2026-05-31` pointer that is really a live
     SQL-oracle lesson STAYS). Archive ONLY a genuinely-completed arc; when in doubt, keep (or standing-justify).
     **Propose-then-apply — never auto-archive** (Safety rule): show the relocations + confirm. Record each as a
     `reconciled` `entries[]` row (pointer relocated `MEMORY.md`→archive; body unchanged). Then **archive-then-
     justify** the earned residual (the kept lessons/negatives that MUST stay always-loaded). (Not a routed
     `lever` — a disposition you apply under any lever; most relief comes from it on a mature shipped-heavy store.)
   - **prune** (local-dominated): surface the candidates, evict the confirmed ones (a `deleted` `entries[]` row
     each) and/or rebuild the index lean. **Never auto-delete** — the triage offers, you confirm. **If
     `reaches_budget` is false** (a full prune still exceeds budget — earned density), prune what's safely
     transient, THEN **standing-justify the residual** (below); do NOT force-evict durable density to chase an
     unreachable number.
   - **gc** (mirror-dominated, `mirror_index_tokens` > 50%): a local prune is futile (`--pull` re-creates
     mirrors) — use the global demote/GC lever (Phase-4 demote the canonical + step 2 GC), don't churn local.
   - **justify** (over budget, nothing safely prunable): record an explicit `entries[]` justification.
   - **Standing-justify (D6/D7) — on a `justify`, prune-then-justify, or archive-then-justify outcome:** persist
     the earned baseline so the gate STOPS re-litigating every pass. In the Phase-5 marker write (step 5), add
     `standing_justify: {"facts": <current fact-count>, "index_tokens": <current>, "at": "<iso>"}`. The next pass
     SUPPRESSES the gate until fact-count grows by Δ (the delta-detector re-fires on NEW density). NEVER
     standing-justify a store you could actually prune OR archive under budget — that hides real bloat.
   - **D3/D11 — do NOT "backfill" an over-budget index.** Phase 0's `index↔file` gap, when over budget, is
     INTENTIONAL (a mature store earns density by not indexing everything) — it is NOT drift to backfill (that
     net-grows under the gate). Backfill is legit only UNDER budget.
   Fill the cycle record's `remediation` block (`pruned`, `achieved_index`/`achieved_recall`).
1. Re-read both `MEMORY.md`s: remove duplicates (within and across stores), fix
   broken file/symbol references, drop entries no longer relevant.
2. **Garbage-collect orphaned mirrors.** A `user-global`/`stack-general` fact deleted
   from the canonical global store leaves dead mirrors in every project that pulled it
   — `--pull` can't reclaim them (it only iterates *live* globals). This is also the
   **budget-relief lever**: when an index is over budget because of replicated mirrors
   (Phase 4), the fix is to delete the *canonical* in `~/.claude/memory/` and then GC
   here (and the orphan clears in every other project on its next pass too). Report
   them, then apply (surface deletions per the safety rule before applying):
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/sync_global.py --gc .          # report
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/sync_global.py --gc . --apply  # reclaim
   ```
   GC only touches `global_ref:` mirror files, never project-authored facts. Record an
   `entries[]` row (`action: deleted`) per reclaimed orphan and set
   `cross_project.gc_removed` — but a mirror orphaned by **this** pass's own demotion already has
   its Phase-4 `deleted` row; don't re-record it (one fact, one entry). (Dead-edge provenance is
   reported, not auto-pruned.)
3. Re-confirm every file path / function name you referenced still exists.
   → **Cycle record:** fill `health` — `index_pointers_ok`, any `broken` pointers,
   any `dangling_links` (`[[name]]` wikilinks pointing at no target file). **Use the SINGLE-SOURCE
   helper — `memory_status.dangling_links(auto_mem)`** (v0.1.37): it resolves every `[[name]]` against
   the FULL valid-target set (`valid_link_targets` — facts + archive-index docs like `SHIPPED.md` /
   `MEMORY`, so `[[SHIPPED]]`/`[[MEMORY]]` are REAL targets, NOT dangling — D10) with inline code spans
   stripped (`[[...]]` in backticks, e.g. TOML `[[tool.mypy.overrides]]`, is not a wikilink). **Phase-0
   `maintenance.dangling` calls the SAME helper**, so the two counts can't drift (the cycle-record-contract
   discipline). For each genuinely dangling `[[name]]`, try `memory_status.resolve_wikilink(name,
   valid_link_targets(auto_mem))` — it resolves slug-drift (`[[qwen-migration-research]]` →
   `qwen_migration_research_2026_05_26`); SUGGEST the drifted target as a fix and confirm before
   re-linking, never auto-rewrite (D10, v0.1.21).
4. **Measure the network's token cost** (the observability section). Capture per-node
   + total estimated token consumption across every node in the shared-memory network
   and paste it into the cycle record's `network` block verbatim:
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/sync_global.py --tokens . --json
   ```
   Also set `budget.*.after`/`after_tokens`/`over` from a final `memory_status.py` read
   so the always-loaded gauge and ⚠ reflect the post-write state.
5. **Update the high-water mark**: write `commit` (current `HEAD`) + ISO
   `timestamp` to `~/.claude/projects/<slug>/memory/.consolidation-state.json` so
   the next pass scopes correctly (stamp the timestamp at write time), and mirror
   that `timestamp` into the cycle record's `marker.timestamp`. **If the over-budget gate
   was JUSTIFIED this pass** (lever `justify` or prune-then-justify, step 0), ALSO write
   `standing_justify: {"facts": <current fact-count>, "index_tokens": <current>, "at": "<iso>"}`
   to the marker — the next pass SUPPRESSES the gate until the store grows by Δ (D6/D7, v0.1.21).
   Then **emit the deterministic mutation audit** (v0.1.22) — diff the post-write state against the Phase-0
   `--snapshot`:
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/memory_status.py --audit <the --snapshot path>
   ```
   It appends a per-operation record to `~/.claude/projects/<slug>/memory/.mutation-log.jsonl` (the durable,
   script-emitted trail) and prints the audit summary — paste that into the cycle record's `audit` block. This
   is the script-OBSERVED counterpart to your `entries[]` narration; they should AGREE — a divergence (a file
   changed that no entry mentions, or an entry with no file change) is a signal to investigate. HONEST GAP: the
   snapshot window attributes ANY change between Phase 0 and now to this pass (an interrupted/concurrent edit
   would mis-attribute) — don't over-trust it. Best avoided by **not committing to the repo while a dream runs**
   (a concurrent commit also moves HEAD → the marker advances past it; the dream detects HEAD-moved + re-measures,
   but can't fully disentangle a concurrent commit's files from its own). If HEAD moved, say so (cf. an audit op
   you didn't make = a concurrent commit, e.g. via `git log <before-marker>..HEAD`).
6. **Render the dashboard AND persist the record** — this is the skill's output (see below):
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/render_dashboard.py <the --seed path> \
       --persist ~/.claude/projects/<slug>/memory
   ```
   `--persist <store dir>` appends the rendered record (one JSON line) to
   `<store>/.consolidation-log.jsonl` — the per-project cycle log that accrues
   magnitude→(applied, outcome) data for a future band calibration. It is idempotent and
   **skips persisting an unstamped cycle** (the render still succeeds), so run it AFTER
   step 5 stamps `marker.timestamp`.
   The dashboard now includes a **"Neural network — token consumption (all nodes)"**
   sub-section: the per-node and total estimated token tax across the network, plus
   what *this* cycle did in lifecycle terms on the triggering node (the node `dream`
   ran on).

   Then **capture the per-memory-file diffs** (v0.1.32) for the dashboard's diff-modal — the
   before/after of each changed memory fact. This MUST run AFTER `--persist` (so
   `marker.timestamp` is stamped) and BEFORE `render_html` (so the dashboard embeds it):
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/memory_status.py --diffs <the --seed path> \
       --before <the --snapshot path>
   ```
   It writes a per-dream sidecar `dashboards/diffs/<commit>__<timestamp>.json` (memory store
   ONLY — the `MEMORY.md` index excluded; per-file diff capped; `chmod 600`, so fact bodies
   stay owner-only) that `render_html` reads to make each changed fact clickable in the dream
   view. Best-effort — skipped (never crashes a dream) if the cycle is unstamped or the
   snapshot is missing.

   Then generate the **rich HTML dashboard + dream ARCHIVE** — the visual sibling of the ASCII
   report (one cycle-record contract, two renderers): the same data plus the longitudinal
   index-budget trajectory, rendered into the per-repo archive mini-site.
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/render_html.py <the --seed path> \
       --store ~/.claude/projects/<slug>/memory --latest
   ```
   It writes a ZERO-dependency, self-contained `dashboards/index.html` (the whole per-repo
   archive of dreams in one file) and **auto-opens this dream's dashboard** (`--latest` →
   `#sel=<newest>`); headless-safe (no browser → prints the path; `--no-open` suppresses).
   This is the post-dream payoff. The dashboard is a **self-contained file at a STABLE per-repo path**
   — `~/.claude/projects/<slug>/dashboards/index.html`. **Present that exact path as the final message
   and tell the user they can re-open it any time by opening the file** (it holds the whole archive;
   navigate dreams in-page via the ledger/filenames). That file IS the fleet-wide re-open — it works from
   any repo. Do **NOT** tell an end-user to run `cm report`: that is a MAINTAINER dev CLI living only in
   the consolidate-memory repo (not on a plugin user's PATH, and it CWD-defaults), useful only when
   dogfooding this plugin from its own checkout. Present BOTH the ASCII dashboard (in-terminal) and the
   file path as the final message.

## Safety rules

These protect the stores from corruption and the user from leaks:

- **Secrets firewall.** Never copy credentials, tokens, API keys, or PII from a
  transcript or config file into ANY store (repo docs are committed; auto-memory
  persists). Record a pointer ("creds in `config.toml`, gitignored"), never a value.
  Note `extract_signals.py` scrubs only the **transcript** mechanically — candidates
  drawn from **git commit messages/bodies** (a Phase-2 source) are NOT auto-scrubbed,
  so apply the same firewall judgment to them by hand before recording.
- **Transcripts are read-only and large.** Report them; read only the tail if you
  must; never write to them or bulk-load them.
- **Surface deletions you didn't author.** Pruning your own stale entry is fine;
  before deleting a memory file or repo-doc fact you didn't write this pass, name it
  in the Phase 4 report and let the user confirm.
- **`CLAUDE.md` is the user's, not the store's — guest WITH permission to tidy, on the record (v0.1.24).** It's
  committed, team-shared, AND always-loaded (the widest blast radius of any store), and its conventions are
  *normative*, so verification can't confirm them. You MAY relocate/compress/prune the hierarchy, but ONLY gated
  per-change + audited, and under the Phase-4 invariants: **the directive always STAYS — relocate only the
  elaboration** (moving a binding directive to an on-demand doc silently erodes enforcement); **never create a
  `CLAUDE.md`** where none exists; **relocate to existing committed in-repo targets only** (`valid_relocate_target`
  — never the private store / a gitignored dir); compress is high-scrutiny; **propose** (never silently perform)
  any normative trim — the human owns the staleness call. Prefer auto-memory or `AGENTS.md`/`MEMORY.md` for new
  facts; reserve CLAUDE.md edits for tidying the always-loaded tier.
- **Two `CLAUDE.md`s, handled differently — never confuse them.** The conservative
  edits above apply ONLY to the **project** `<repo>/CLAUDE.md`. The **user-global**
  `~/.claude/CLAUDE.md` (loaded into *every* project, every session) is **strictly
  off-limits for writes** — it's personal, universal config, not a project store. The
  skill only **measures it read-only** (`memory_status.py`), surfacing it as a distinct
  "global · every project · read-only" line in the always-loaded budget so the
  per-session cost isn't understated. Measure it; never edit it.
- **Don't invent citations.** A `[commit]`/`[session]` tag must point at something
  real. No fabricated session ids.
- **Don't duplicate the codebase.** If git or the code already says it, don't
  memorialize it — capture the non-obvious why.

## Output: the cycle record → dashboard

The output is **not** free-form prose. It's a fixed dashboard whose content is
driven by what the pass actually did. You accumulate a small JSON **cycle record**
through the phases (seeded by `memory_status.py --json`), then render it with
`render_dashboard.py` — the model produces the data, the script produces the
presentation, so the report is consistent run-to-run but reflects this cycle (a
no-op pass and a heavy pass render visibly differently; empty sections collapse, and
the outcome banner is derived from the write counts).

The render script is the single source of the final report — don't hand-write a
summary alongside it.

### Cycle-record schema

```json
{
  "project": "repo-name",
  "session": "<active session id>",
  "scope": {"git_range": "abc..HEAD", "git_commits": 0,
            "session_candidates": 0, "memories_reviewed": 0},
  "rigor": {"phase": "provisional|final", "prune_pressure": false, "prune_reason": "",
            "applied": "", "override_reason": ""},
  "verification": {"confirmed": 0, "corrected": 0, "unverifiable": 0,
                   "method": "inline|subagents"},
  "entries": [
    {"action": "added|corrected|deleted|reconciled|skipped",
     "tier": "always-loaded|recall|on-demand|-",
     "store": "auto-mem|repo|-",
     "scope": "project-local|stack-general|user-global",
     "name": "<fact slug or short label>",
     "reason": "<why — esp. for skipped/deleted>",
     "citation": "<commit sha | session id | empty>"}
  ],
  "budget": {
    "claude_md": {"before": 0, "after": 0, "before_tokens": 0, "after_tokens": 0,
                  "budget_tokens": 4000, "over": false},
    "global_claude_md": {"present": false, "lines": 0, "tokens": 0,
                         "budget_tokens": 4000, "over": false},
    "index": {"before_lines": 0, "after_lines": 0, "before_bytes": 0, "after_bytes": 0,
              "before_tokens": 0, "after_tokens": 0, "budget_tokens": 1200, "over": false},
    "recall_facts": {"before": 0, "after": 0},
    "claude_md_hierarchy": {"files": [{"path": "CLAUDE.md", "tokens": 0}],
                            "worst_path": ".", "worst_path_tokens": 0, "total_files": 0}
  },
  "health": {"index_pointers_ok": true, "broken": [], "dangling_links": [],
             "slug_orphans": [], "schema_drift": {}},
  "cross_project": {
    "global_store_facts": 0,
    "pulled": [{"name": "...", "scope": "user-global"}],   "_pulled": "Phase 1: global → here",
    "promoted": [{"name": "...", "scope": "stack-general"}], "_promoted": "Phase 4: here → global",
    "refreshed": 0,
    "held": 0,   "_held": "v0.1.38 (M1): new-global pulls --pull HELD (would net-grow the over-budget index) — prune/justify to receive",
    "gc_removed": 0,   "_gc": "Phase 5: orphan mirrors reclaimed by sync_global --gc --apply"
  },
  "network": {
    "_": "Phase 5: paste sync_global.py --tokens . --json verbatim here (per-node token cost)",
    "basis": "≈ chars/4 (heuristic estimate, not a tokenizer)",
    "node_def": "project stores holding ≥1 shared fact",
    "trigger": "<this project>",
    "nodes": [{"node": "...", "trigger": false, "always_loaded_tokens": 0,
               "mirror_index_tokens": 0, "recall_tokens": 0, "facts": 0, "shared": 0}],
    "totals": {"nodes": 0, "always_loaded_tokens": 0,
               "mirror_index_tokens": 0, "recall_tokens": 0}
  },
  "remediation": {
    "_": "v0.1.18: present ONLY when the index is OVER budget (the GATE); absent on a healthy store. v0.1.21: when standing_justified the gate is SUPPRESSED (required=false) until fact-count grows by Δ. Seeded by Phase 0; pruned/achieved_* filled in Phase 5.",
    "required": false, "lever": "prune|gc|justify",
    "candidates_surfaced": 0, "pruned": 0,
    "projected_index": 0, "achieved_index": 0,
    "projected_recall": 0, "achieved_recall": 0,
    "standing_justified": false, "baseline_facts": 0, "reaches_budget": true
  },
  "maintenance": {
    "_": "v0.1.37/v0.1.42: the no-op SELF-HEAL pivot signal (seeded Phase 0, cheap/local). TWO PROCEED cases (NOT a no-op): a NON-EMPTY store with 0 commits = a MAINTENANCE pass; AND (v0.1.42) an EMPTY store + 0 commits + a non-empty network (cross_project.global_store_facts>0) = a COLD-START BOOTSTRAP — both PROCEED to Phase 1 --list→--pull (cross-node enrichment) + Phase 5 health. over_budget_not_justified = remediation.required (the dual-axis suppression result, not a fresh budget compare). Set pivoted=true in Phase 5 when you run either → drives the MAINTENANCE PASS banner.",
    "dangling": 0, "over_budget_not_justified": false, "work": false, "pivoted": false
  },
  "audit": {
    "_": "v0.1.22: DETERMINISTIC script-emitted mutation trail. Phase 0 `memory_status.py --snapshot` writes a per-slug BEFORE snapshot; Phase 5 `--audit <snapshot>` diffs, appends .mutation-log.jsonl, and fills this — what THIS pass ACTUALLY changed (content-hash), cf. the model-narrated entries[]. MEMORY.md modified = expected re-index churn.",
    "memory": {"created": 0, "modified": 0, "deleted": 0, "token_delta": 0},
    "claude_md": {"created": 0, "modified": 0, "deleted": 0, "token_delta": 0},
    "repo_doc": {"created": 0, "modified": 0, "deleted": 0, "token_delta": 0},
    "operations": [{"path": "memory/foo.md", "op": "modified", "token_delta": 0, "store": "memory"}],
    "conservation": {"claude_md_drop": 0, "repo_doc_growth": 0, "possible_loss": false},
    "window": "phase0..phase5"
  },
  "marker": {"before_commit": "<prev marker HEAD>", "before_timestamp": "<prev marker ISO>",
             "commit": "<HEAD>", "timestamp": "<ISO, stamped in Phase 5>"},
  "outcome": ""
}
```

`outcome` is an OPTIONAL explicit override of the derived banner — leave it empty (or
omit it) and the dashboard derives `NOTHING TO CONSOLIDATE` / `NO-OP PASS` / `LIGHT PASS`
/ `SUBSTANTIAL PASS` from the write counts; set it only to force a specific banner. (Its
presence here keeps this schema block key-for-key with the `CycleRecord` TypedDict, which
a smoke test enforces.)

The `budget.*.over` flags and token counts come from `memory_status.py` (it gates on
the `INDEX_TOKEN_BUDGET` / `CLAUDE_MD_TOKEN_BUDGET` ceilings); the dashboard renders a
⚠ when over. Token counts are **estimates** (≈ chars/4 — no tokenizer; zero-dep), so
present them as `≈`, never as exact. The `network` block is the
`sync_global.py --tokens . --json` output pasted in Phase 5; the dashboard derives the
"this cycle's lifecycle on the triggering node" line from `entries[]` + the budget
delta + `cross_project.gc_removed`/`refreshed` — so don't hand-maintain a parallel
count.

The dashboard derives its outcome banner (`NOTHING TO CONSOLIDATE` / `NO-OP PASS` /
`LIGHT PASS` / `SUBSTANTIAL PASS`) from the write counts unless you set an explicit
`outcome`. Keep entries honest — recording a `skipped` decision (and why) is as
valuable as recording a write.

The `rigor` block is **seeded provisional** by `memory_status.py` and **finalized in
Phase 2** (you set the curated `session_candidates` in `scope` and `phase: "final"`).
Both the **tier and the magnitude are derived from `scope`** at render — neither is
stored, so the label can never drift from its own magnitude. (A future band calibration
would filter to `phase: "final"` records and refit from the magnitude→outcome; the `--persist`
log (Phase 5) now accrues those records — a real refit still needs enough of them + longitudinal
miss-detection. See roadmap.) It is an early
effort *hint*, a distinct quantity from the write-based outcome banner (see *Rigor
modes*); the dashboard labels both so they never read as one number.

## A note on scope

This skill intentionally skips the skill-creator's formal eval/benchmark loop — its
output (consolidated memory) is judged by correctness and usefulness, which the
report + the user's eye assess better than assertions. If you ever want hard trigger
metrics, the skill-creator's description-optimizer can be pointed at this skill's
description later.
