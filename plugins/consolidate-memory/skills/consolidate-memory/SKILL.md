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

**The HARD CEILING (v0.1.66, Phase B) — a SECOND, INDEPENDENT signal beside the target gate above, never a
re-key of it.** `INDEX_CEILING_TOKENS` (≈3840 est tok = 0.6 × the harness's native 25KB truncation cap;
`memory_status.py`) is the real-harm rung of the budget ladder: past it, `sync_global --pull` **M1-holds
ALL new pulls** and the evict gain-gate keys to it (v0.1.73: an A/B replay of the actual pull plan, with
`freed` MEASURED from the live index line — a mirror, an unindexed, or a gainless evict is refused;
see `docs/evict-accounting-truth.spec.md`) — while the over-TARGET amber band (1500..ceiling) now
**receives** verified knowledge freely. The ceiling is **structurally standing-justify-INDEPENDENT** (the
comparison never reads `standing_justify` — there is nothing to suppress and no justify escape; over the
ceiling, only shrinking satisfies). Everything in the v0.1.18 paragraph above — `required`, the triage
levers, standing-justify, prune-pressure, the maintenance pivot — is UNTOUCHED and still keys to the
target. Surfaced as `remediation.over_ceiling` + a red flag on every gauge (dashboard, Phase-0 report,
HTML archive). Design + the 3-lens gate that produced it: `docs/index-usage-and-budget-ladder.spec.md`.

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
enables but which remains future work. **One under-rigor case IS now caught (v0.1.44): the
lazy-skip** — a SUBSTANTIAL-or-larger-MAGNITUDE pass that records 0/0/0 verification trips the
**procedure-integrity detector** at the terminal `render_dashboard --persist` (a loud ⚠ panel +
exit 3 — see Phase 5). It rests on the script-derived magnitude (`git_commits`), not the
self-report, so it can't be graded away; it does NOT catch a diligent liar who types fake
tallies (same limit). This is the structural fix for the MEASURED 2026-06-22 failure (three
dreams ran 0/0/0 while self-labeled SUBSTANTIAL/HEAVY). See `docs/dream-procedure-integrity.spec.md`. And never calibrate the bands against the dashboard's
OUTCOME banner — mature passes are systematically high-magnitude / low-outcome, so fitting
`(magnitude, outcome)` fails UNSAFE (it biases toward LESS rigor). The rigor tier (an
*input*-based effort estimate) is a **distinct quantity** from the dashboard's outcome
banner (an *output*-based label from write counts): they share no scale, and a pass can
legitimately read "HEAVY" rigor yet "LIGHT" outcome (much to review, little durable to
write). The dashboard labels both so they never read as one number.

### The dream arc — fall asleep · dream the phases · wake

This skill IS a dream — the agent analogue of sleep-time consolidation — and the pass is
**performed as one**. You fall asleep as it begins, each phase is a movement of the same
dream, and you wake at the end. This sequence is a **contract, exactly as mandatory as
seeding the cycle record**: every beat fires on every pass, in order, in the pinned format
below. The dreamy first-person register is the CORRECT register for this skill — plain
procedural narration ("Phase 2: running extract_signals…") is the defect here, not the
safe choice. What varies run-to-run is each beat's *content*, improvised from THIS pass's
real material; what never varies is that the beats fire.

**Two channels.** Dream voice and functional reporting never share a channel:
- **Dream channel** — plain italic: every line `*…*`. The italics alone mark the voice —
  no blockquote, no accent bar. Emojis exist ONLY on the two bookends: the SLEEP block
  opens `*💤 …*` and the WAKE block `*☀️ …*`; every other dream line carries none.
- **Plain channel** — everything else: phase labels, commands, counts, findings, proposals,
  the debrief body. The plain channel must stand alone — complete and self-sufficient — so
  the dream never has to carry operational weight and never competes with it.
The two never compete for the same sentence, so you never choose between them: emit both,
every phase — the dream block above, the plain findings below.

**The beats.**

| Beat | When | Depth |
|---|---|---|
| **SLEEP 💤** | Your FIRST output on invocation, before the first tool call — falling asleep out of the session's just-finished work (fresh session, nothing in context → a neutral drift-off). Opens `*💤 …*` | 1–3 lines (short — the dream hasn't found anything yet; depth arrives with the beats) |
| **DREAM BEAT** | Opens EVERY phase's narration (0 locate · 1 network · 2 signals · 3 verify · 5 defrag/render): dream block first (plain italics, no emoji), that phase's plain findings below | 1–3 lines |
| **SURFACING** | Phase 4's single italic line (`*…*`, no emoji) — the dream thins to show the proposal. It ORIENTS only ("the pass surfaces to ask…"); it never editorializes what's proposed (this is the approval gate for irreversible writes) — then the proposal itself is delivered fully in the plain channel | 1 line |
| **WAKE ☀️** | After the terminal clean (exit-0) render + archive open, before the debrief: surfacing out of the dream — ONE italic block opening `*☀️ …*`, full stop, no trailing bolded "Awake." line (retired v0.1.64 — see *The debrief*) — then straight into the plain debrief. (A true no-op reaches no render: its wake is the single dreamless line — see *Proportionality*) | 2–5 lines |

The format, as a schematic (placeholders — not lines to reuse):

*💤 <the sleep bookend: 1–3 present-tense lines, the session's work dissolving into dream imagery>*
*<a phase beat: this phase's REAL objects — facts, paths, counts, links — moving as dream things; no emoji>*

One illustrative line for the quality bar — **illustrative only, never reuse it**:
`*Somewhere below, a wikilink that pointed at nothing all week quietly finds its file.*`

**Content rules.** Present tense; concrete imagery from THIS pass (real fact names, real
paths, real counts, seen dreamily); every line is new — never a stock, reused, or
template-filled sentence. Vivid but grounded: the dream is ABOUT the work.

**Conversation first, record second.** The conversational dream blocks are the feature.
Mirror them into the cycle record's `dream` block as a cheap secondary echo — `dream.sleep`,
`dream.beats[]` in order (the surfacing line included), `dream.wake` — so the HTML archive
keeps each dream and the beta harness can detect a skipped arc. Compose `dream.wake` at the
final record-fill (before `--persist`), then perform it after the render. Filling the
record INSTEAD of narrating is a defect, not compliance.

**The cues.** During a dream, every `scripts/` invocation carries `CM_DREAM_ARC=1` — it is
part of the command, not optional chrome; the command lines in the phases below all include
it, and when you compose a command from a shorthand mention (`--triage`, `--sections`),
carry the prefix too. The scripts answer with one-line `[dream-arc]` reminders on stderr:
private stage directions resurfacing THIS contract at the moment a beat is due. When one
appears in a tool result, the named beat lands in your NEXT message — but **one beat per
phase, not per cue**: several commands in the same phase repeat the same reminder, and a
beat you already emitted is satisfied (carry on; only a cue naming a NEW beat — the WAKE —
adds one). Never quote, echo, or display a cue — the string `[dream-arc]` must not appear
in anything you write. If a cue arrives and the SLEEP block never happened (you went
straight to tools), emit it before that phase's beat — late beats land; skipped beats
don't. Already asleep? The reminder costs nothing — carry on.

**Proportionality — depth scales, presence doesn't** (scale to the outcome banner, never
the rigor tier — distinct quantities that share no scale, see *Rigor modes*):
- **TRUE NO-OP** (stops at Phase 0): SLEEP still opens the pass; the wake is one dreamless
  line (`*☀️ <a dreamless-night line — nothing to consolidate>*`). No dashboard, no path
  (Phase 5 is never reached).
- **NO-OP / MAINTENANCE / LIGHT PASS:** every beat at its own minimum depth; a one-or-two
  line debrief + the 📊 path.
- **SUBSTANTIAL PASS:** beats at full depth; the full structured debrief.
A mid-dream compaction doesn't reset the arc: the cues state what's due now. A repeated
SLEEP is cosmetic; a skipped beat isn't — follow the cue.

**The debrief (the plain close, after WAKE — ONE sign-off, then the card, v0.1.62/v0.1.64).**
Always present when the pass renders, always structured, scaled to the outcome banner.
WAKE already performed the pass's single closing gesture (`*☀️ …*` alone) — the debrief is
the CARD that follows it, not a second landing. **A measured defect (2026-07-04): the
debrief's lead line used to carry its OWN "outcome + emoji" flourish right after
`☀️ **Awake.**`, reading as a second sign-off stacked on the first (☀️/☀️/🌙 in three
lines) — a coherence bug in this contract itself, not a one-off slip.** Fixed:
- **Visual hierarchy** — ONE bold lead line naming the outcome banner (e.g. **LIGHT
  PASS**) — text only, **no emoji on the lead line**: WAKE already closed the dream, so a
  second emoji here would be a redundant third landing gesture. Bold-headed sections
  follow.
- **Dense + technical** — bullets with bold lead-ins, no filler; don't dumb the content
  down.
- **Functional, SPARSE emojis — IN THE BODY ONLY, never on the lead line.** A section
  marker earns its emoji by naming a SPECIFIC thing that section is about (🚀 ship ·
  📊 dashboard · ✓ / ⚠ status) — never a generic "this is a dream pass" decoration.
  (Retired: a bare 🌙 as a whole-debrief marker — it duplicated WAKE's ☀️ with no content
  of its own to mark.) In the dream channel, 💤/☀️ still mark only the sleep/wake
  bookends — unchanged.
- **FRAMES, doesn't DUPLICATE** — name the non-obvious WHY + what was KEPT / PRUNED /
  verified; the dashboard holds the gauges / counts / tallies. **"Don't duplicate" ≠ "drop
  the numbers":** cite a figure when it carries the point (e.g. "8443→2685 tok, all lessons
  kept"); just don't re-tabulate the gauge set in prose. (This is the real intent of
  *Output*'s "single source of the **data** report": don't re-tabulate the data — DO frame
  it.)
- **Always ends with the 📊 dashboard path** + the "re-open it any time by opening the
  file" note. (The true no-op produces no debrief and no path — it never reaches Phase 5.)

**A second, adjacent defect (2026-07-04, same day — caught live from the RENDERED HTML archive,
not the raw chat text, by the user).** Even after the v0.1.62 fix above, WAKE's own two lines —
the italic surfacing paragraph and the separate bolded `☀️ **Awake.**` — still duplicated EACH
OTHER: the archive renders them as two separate sun-marked bullets, the same redundant shape
v0.1.62 ended one layer up, just recurring one layer down. The surfacing paragraph already
conveys emergence from the dream; a second, content-free "Awake." line adds nothing —
"more elegant" without it, in the user's own words. **Fixed (v0.1.64): WAKE is now the single
italic paragraph, full stop — no trailing bolded line, ever, in ANY case including the true
no-op** (which was already single-line and needed no change). The debrief's bold lead line
(v0.1.62) is unchanged and remains the ONLY thing that follows WAKE.

### Phase 0 — Locate data + the high-water mark

Run the bundled helper (it derives paths, inventories both stores, and computes the
git range since the last consolidation — don't hand-derive these):

```bash
CM_DREAM_ARC=1 python3 ${CLAUDE_PLUGIN_ROOT}/scripts/memory_status.py
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
  to pull → Phase 1 `sync_global --pull` (AUTO-HOLDS, M1, any new-global pull that would push the index past
  the HARD CEILING — `held N`; v0.1.66: the over-target amber band no longer holds) + Phase 5 (health:
  dangling-fix / prune-or-justify).
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

**The first dream beat lands here.** The SLEEP block already opened the pass — it precedes the
first tool call (see *The dream arc*); if you reached this read without it, emit it now, before
the beat. With the read in hand, open Phase 0's narration with its dream beat (1–3
italic lines on what the read surfaced), then give the plain findings.

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
CM_DREAM_ARC=1 python3 ${CLAUDE_PLUGIN_ROOT}/scripts/memory_status.py --seed   # writes a PER-PASS cycle file + prints its path
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
CM_DREAM_ARC=1 python3 ${CLAUDE_PLUGIN_ROOT}/scripts/memory_status.py --snapshot   # writes a per-slug BEFORE snapshot + prints its path
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
(v0.1.42, B1): the `--list` surfaces *which* globals are relevant + present/missing BEFORE `--pull` writes
them — so the enrichment is legible (you see the bootstrap/refresh picture; hold/refresh counts appear on
`--pull`, which auto-holds any past-the-CEILING pull) instead of a blind pull. On a COLD-START bootstrap (empty store, rich network — see the no-op rule) this `--list` is the
relevance filter that decides PROCEED-vs-honest-no-op; on a normal pass it's a cheap read that costs nothing:

```bash
CM_DREAM_ARC=1 python3 ${CLAUDE_PLUGIN_ROOT}/scripts/sync_global.py --list .   # surface relevant/present/missing (read-only)
CM_DREAM_ARC=1 python3 ${CLAUDE_PLUGIN_ROOT}/scripts/sync_global.py --pull .   # then replicate (M1 auto-holds a past-the-CEILING pull)
```

This replicates any `user-global` (and stack-matching `stack-general`) facts from
`~/.claude/memory/` that are missing here, and **refreshes any stale mirrors** whose
canonical changed (the script writes both the fact file and its index pointer). It also **AUTO-HOLDS**
(M1) any new-global pull that would push the always-loaded index past the **HARD CEILING**
(`INDEX_CEILING_TOKENS` ≈3840 est tok — v0.1.66; an over-TARGET amber store now receives freely, since
withholding verified knowledge keys to the real harm boundary, not the curation target) — reported as
`held N`. Every written pointer is fat-hook-linted (>`HOOK_TOKEN_WARN` → a stderr warning naming the
canonical's description; never truncated). Read its output and record `cross_project.pulled` (newly
replicated), `cross_project.refreshed`, **and `cross_project.held`** (the `held N` count — new globals
withheld to protect a past-the-ceiling index; the dashboard renders it as the `⚠ held N — shrink to
receive` lever) in the cycle record. If nothing is missing/stale/held, no-op.

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
   v0.1.70: the `--oneline` commit SUBJECT list `memory_status.py` itself prints in the
   Phase-0 report now passes through the same secrets firewall as source #2 below (a
   credential-shaped subject is redacted to `(omitted: commit subject contained a
   credential-shaped value)`, SHA kept) — but that firewall covers ONLY that automated
   subject list, NOT the full commit BODIES this step has you read yourself (a raw
   `git log`/`git show` you run directly bypasses it entirely, unscrubbed). It is a
   mechanical backstop on one path, not a guarantee against every shape or every path.
   Never transcribe a commit subject OR body verbatim into a persisted fact if it looks
   credential-shaped to you; paraphrase the change instead.
2. **Session signal** → **feedback/preferences** (human turns) + **gotchas** (error
   tool-results). Don't read the raw transcript — run the extractor, which streams
   it, scopes to the marker, drops harness/skill noise, **omits credential-shaped
   turns** (secrets firewall at retrieval), and returns ranked, structured, scoped
   candidates:
   ```bash
   CM_DREAM_ARC=1 python3 ${CLAUDE_PLUGIN_ROOT}/scripts/extract_signals.py --json
   ```
   (For *eyeballing*, run it WITHOUT `--json` — the human-readable table is already formatted; reserve `--json`
   for machine capture. The `--json` shape is `{counts:{…, surfaced}, signals:[…]}` where each signal is
   `{source, signal_type, scope_hint, score, text}` — the type key is **`signal_type`** (not `kind`) and the
   count is **`counts.surfaced`** (not a top-level `surfaced`).) **Run it, or record why you didn't.** The extractor reads the compaction-proof *on-disk*
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

First, the **SURFACING beat** — one plain-italic line, the dream thinning to show the
proposal; it ORIENTS the transition, never editorializes the proposal's merits (see *The
dream arc*). Then **present the proposed consolidation to the user fully PLAIN**: what
you'll add, correct, or delete, in which **tier/store**, and why — a short diff-like
summary. This is the approval gate for irreversible, committed, always-loaded churn, and
fogging it is the one unrecoverable mistake — the proposal itself never carries the dream
voice (approvals live in the plain channel).
This matters because Phase 4 writes committed docs and persistent memory; the user should see the
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
  pointer to the index — **keep the pointer's hook a distilled cue ≤ ~60 est tok
  (`HOOK_TOKEN_WARN`, v0.1.66)**: the `description:` stays the full recall key, but the
  index LINE you write from it must not restate body content (a fat hook taxes every
  session; `sync_global` lints its own written pointers the same way — the measured
  offenders were 116/141-tok status-paragraphs-as-hooks). **Stamp `originSessionId` (v0.1.43) for a SESSION-DERIVED fact** — from the `sessionId`
  that `extract_signals` (Phase 2) now attaches to the signal this fact came from (the session that MOTIVATED it,
  which on a multi-session window may be a PRIOR session, NOT the active dream). OMIT it for a git/commit-derived
  project fact (no motivating session). This is the producer the schema always assumed but never had.
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
    CM_DREAM_ARC=1 python3 ${CLAUDE_PLUGIN_ROOT}/scripts/sync_global.py --promote . LOCAL_FACT [CANON_NAME]
    ```
    Pass `CANON_NAME` to normalize the name (`_`→`-`, drop a date) or to **dedup** onto an
    existing canonical (never overwritten). You still **add the `~/.claude/memory/MEMORY.md`
    line** (the op leaves the global index to you — the single writer). v0.1.67 (Phase C): the
    op prints a **fleet-tax advisory** (warn-only, never a block) when the fleet's total
    Σ pointer×holders crosses `GLOBAL_FLEET_TAX_ADVISORY` — every canonical taxes every holder
    node's always-loaded index every session; `--utility` has the per-canonical evidence table.
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
"citation": "...", "files": [...]}`. After writing, update `budget.*.after` (CLAUDE.md
lines, index lines/bytes, recall-fact count).

**`files` (v0.1.72) — declare, don't make the dashboard guess.** When an entry's action changed a
file `memory_status.py --diffs` tracks (a fact body, `MEMORY.md`, a `claude_md/*` file, a repo doc),
list its `audit_snapshot` label(s) — `memory/<slug>.md`, `memory/MEMORY.md`, `claude_md/CLAUDE.md`.
This is how the dashboard's diff-modal links that entry to its before/after — deterministically, from
what YOU state, not a name-match heuristic. An index-line-only compression (fact body untouched)
still touched `memory/MEMORY.md` — list it. A fact whose body AND its index line both changed lists
both. Omit `files` (or leave it empty) for a `skipped` entry or a `reconciled` one that only verified
(no edit made) — nothing tracked changed, so there's nothing to link.

### Phase 5 — Prune, GC, verify, measure, update the marker, render

**At HEAVY, run a completeness critic first** (see *Rigor modes*): re-ask "what did we
miss or mis-verify?" — a fact the git range implies but no candidate captured, a claim
marked confirmed on thin evidence — and loop back one pass if it surfaces anything.

**Phase 5 is an always-on staleness/defrag SWEEP — the consolidation mandate, run EVERY dream, not a budget
reaction.** Curating completed/stale content out of the active tier is the default each pass; the over-budget gate
(step 0) is a BACKSTOP, not the trigger.

**Completion-driven archive (runs EVERY dream, decoupled from budget — v0.1.x).** Phase 0 surfaces **`archive? N`**
candidates — indexed pointers with a dated `_YYYY_MM_DD` stem, already KEEP-vetoed for live lessons
(`archive_candidates`). Review them EVERY pass and PROACTIVELY archive the genuinely-completed ones — don't wait for
budget pressure to accumulate them: the always-loaded index should equal the **active / lesson-bearing set**, so a
completed/merged arc's pointer belongs in the on-demand archive the moment its durable lessons are extracted into kept
facts. Apply the SAME keep-vs-archive JUDGMENT, propose-then-apply, and `reconciled` `entries[]` recording as step 0's
archive disposition below — the **SILENT-failure guard holds**: a dated-but-LIVE lesson STAYS (the helper's KEEP-veto
is *sufficient-not-necessary*, so YOU judge each by content; the helper only RANKS, the user confirms). A
non-dated completed arc the helper won't surface — catch those by the same judgment. This is the primary
defragmentation that keeps the index lean; the over-budget gate below is what catches the rare case it doesn't.

**Body-defragmentation (runs EVERY dream — v0.1.x, Cycle 2).** Phase 0 also surfaces **`defrag? N`** bloated ACTIVE
files — indexed, non-mirror, NON-dated facts whose BODY is a size outlier (≫ the store median; `defrag_candidates`).
These are long-lived status/roadmap docs that have ACCRETED completed/stale items over time. Curate the BODY **in
place** (the index pointer STAYS — distinct from archiving a whole dated fact): **COLLAPSE** completed detail that is
redundant with git/CHANGELOG — but **READ the CHANGELOG/git and CONFIRM the detail is actually present there BEFORE
collapsing** (verified, not assumed; else KEEP or relocate); **RELOCATE** still-useful-completed detail to an archive
doc; **KEEP** active/forward content (OPEN items, current state, watch-list) and live lessons / negative findings.
**Propose-then-apply IN-CONVERSATION (show the body edits + confirm), never auto-trim** — the Phase-5 `--diffs` sidecar
is the POST-write audit record, NOT the pre-apply gate. Higher-risk than pointer-archiving (intra-file): keep-on-doubt,
relocate-over-delete. Goal — the file returns toward the store's typical length, kept accurate + forward-looking. Full
design: `docs/body-defragmentation.spec.md`.

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
   CM_DREAM_ARC=1 python3 ${CLAUDE_PLUGIN_ROOT}/scripts/sync_global.py --gc .          # report
   CM_DREAM_ARC=1 python3 ${CLAUDE_PLUGIN_ROOT}/scripts/sync_global.py --gc . --apply  # reclaim
   ```
   GC only touches `global_ref:` mirror files, never project-authored facts. Record an
   `entries[]` row (`action: deleted`) per reclaimed orphan and set
   `cross_project.gc_removed` — but a mirror orphaned by **this** pass's own demotion already has
   its Phase-4 `deleted` row; don't re-record it (one fact, one entry). (Dead-edge provenance is
   reported, not auto-pruned.) **When the step-0 lever routed `gc` (mirror-dominated), pull the
   fleet's usage EVIDENCE first** (v0.1.67, Phase C): `sync_global.py --utility .` aggregates each
   canonical's mirror-attributed organic reads across every node's cycle log + its fleet tax
   (pointer × holders, an upper bound) — a canonical unread everywhere it's instrumented is
   demote/gc *evidence*, but the decision stays CONTENT-gated (holders/adoption ≠ fit; judge the
   cascade, never auto-gc on numbers).
3. Re-confirm every file path / function name you referenced still exists.
   → **Cycle record:** fill `health` — `index_pointers_ok`, any `broken` pointers,
   any `dangling_links` (`[[name]]` wikilinks pointing at no target file). **Use the SINGLE-SOURCE
   helper — `memory_status.dangling_links(auto_mem, global_dir=Path.home()/".claude"/"memory")`** (v0.1.37;
   v0.1.52 cross-store): it resolves every `[[name]]` against the FULL valid-target set (`valid_link_targets`
   — facts + archive-index docs like `SHIPPED.md` / `MEMORY`, so `[[SHIPPED]]`/`[[MEMORY]]` are REAL targets,
   NOT dangling — D10) across **local ∪ the global canonical**, with inline code spans stripped (`[[...]]` in
   backticks, e.g. TOML `[[tool.mypy.overrides]]`, is not a wikilink). **Pass `global_dir`** so a pending-pull
   up-link to a budget-HELD global fact is NOT mis-flagged (a sibling-project-local DOWN-link still is —
   genuinely unreachable here). **Phase-0 `maintenance.dangling` calls the SAME helper with the SAME
   `global_dir`**, so the two counts can't drift (the cycle-record-contract discipline). For each genuinely
   dangling `[[name]]`, try `memory_status.resolve_wikilink(name, valid_link_targets(auto_mem) |
   valid_link_targets(global_dir))` — it resolves slug-drift (`[[qwen-migration-research]]` →
   `qwen_migration_research_2026_05_26`); SUGGEST the drifted target as a fix and confirm before
   re-linking, never auto-rewrite (D10, v0.1.21).
4. **Measure the network's token cost** (the observability section). Capture per-node
   + total estimated token consumption across every node in the shared-memory network
   and paste it into the cycle record's `network` block verbatim:
   ```bash
   CM_DREAM_ARC=1 python3 ${CLAUDE_PLUGIN_ROOT}/scripts/sync_global.py --tokens . --json
   ```
   Then **capture recall utility** (v0.1.63, Phase A — the usage instrument): scan the window's
   transcripts for ORGANIC fact-body reads (dream-procedure reads span-excluded) and inject the
   script-truth `usage` block into the seed — counts are script-only, never hand-authored. **Pass the
   Phase-0 `--snapshot` path as `--before`** (v0.1.67, Phase C): the miss-detector's archive-tier
   classification is judged against the WINDOW-START state, so a fact you archived earlier THIS pass
   (whose reads happened while it was still indexed) is never misclassified as a miss:
   ```bash
   CM_DREAM_ARC=1 python3 ${CLAUDE_PLUGIN_ROOT}/scripts/extract_signals.py --recalls --into <the --seed path> --before <the --snapshot path>
   ```
   Transcripts rotate quickly, so this per-dream capture is the ONLY way usage accrues. A fact showing
   0 reads is ABSENCE OF EVIDENCE (retention + span-exclusion undercount), never proof it's unused —
   never prune on it alone (that judgment is the DEMOTION TRIAGE below, with corroboration).
   **`usage.misses` non-empty = a DEMOTION ERROR caught red-handed**: an archived-tier fact was read
   organically this window — propose RE-PROMOTING its pointer to `MEMORY.md` (report-then-apply, a
   `reconciled` row); the log remembers the miss forever and it permanently vetoes that fact from
   future demotion candidacy.

   **Then the DEMOTION TRIAGE (v0.1.67, Phase C — run BEFORE the final budget re-read below, since
   dispositions mutate the index).** Phase 0 seeded `demotion` (windows_observed / eligible /
   surfaced, hook-cost ranked) and the `--recalls --into` you just ran STRUCK any surfaced stem read
   THIS window (`demotion.struck` — never demote those). While `eligible: 0` the policy is DORMANT
   (the evidence gate: a fact needs ≥3 probative zero-read windows + corroboration before it even
   surfaces) — record `verdict: "dormant — N probative windows"` and move on. When candidates
   remain: **judge each by CONTENT** — the keep-vs-archive judgment has a SILENT failure mode
   (an archived live lesson stops being recalled with nothing to flag it), so keep-on-doubt —
   then apply per-item dispositions, **report-then-apply, recorded as `entries[]` rows** (never
   tally counts into the record — entries[] is the single source):
   - **demote-to-archive**: the pointer moves `MEMORY.md` → an archive index (`SHIPPED.md` et al.);
     the BODY stays (a load-tier change, never a delete). A `reconciled` row.
   - **compress**: tighten the fact's `description:`/hook (the fat-hook fix site). A `corrected` row.
   - **merge**: fold distinct content into the surfaced `similar` neighbor (a `corrected` row), then
     rewrite the merged-out fact as a one-line `[[neighbor]]` redirect stub and demote its pointer
     (a `reconciled` row). NO deletion under this policy — removing the stub later is the normal
     confirmed-prune path.
   - **counter-justify**: the fact stays, with a `skipped` row recording why, AND step 5's marker
     write gains `demotion_justify` (below) so it doesn't re-nag every dream.
   Fill `demotion.verdict` — ONE sentence, always (a dormant/none verdict is still a verdict; "ran
   and proposed nothing" must be distinguishable from "never ran").
   Finally set `budget.*.after`/`after_tokens`/`over` from a final `memory_status.py` read
   so the always-loaded gauge and ⚠ reflect the post-write state (AFTER any dispositions above).
5. **Update the high-water mark**: write `commit` (current `HEAD`) + ISO
   `timestamp` to `~/.claude/projects/<slug>/memory/.consolidation-state.json` so
   the next pass scopes correctly (stamp the timestamp at write time), and mirror
   that `timestamp` into the cycle record's `marker.timestamp`. **If the over-budget gate
   was JUSTIFIED this pass** (lever `justify` or prune-then-justify, step 0), ALSO write
   `standing_justify: {"facts": <current fact-count>, "index_tokens": <current>, "at": "<iso>"}`
   to the marker — the next pass SUPPRESSES the gate until the store grows by Δ (D6/D7, v0.1.21).
   **If any demotion candidate was COUNTER-JUSTIFIED this pass** (step 4's triage, v0.1.67), ALSO
   merge into the marker's `demotion_justify` map:
   `demotion_justify: {"<stem>": {"windows": <demotion.windows_observed>, "at": "<iso>"}}` — the
   per-item delta-detector: that candidate stays suppressed until the store accrues 5 more probative
   usage windows (a malformed entry does NOT suppress — candidates fail open toward re-surfacing).
   Then **emit the deterministic mutation audit** (v0.1.22) — diff the post-write state against the Phase-0
   `--snapshot`:
   ```bash
   CM_DREAM_ARC=1 python3 ${CLAUDE_PLUGIN_ROOT}/scripts/memory_status.py --audit <the --snapshot path> --into <the --seed path>
   ```
   It appends a per-operation record to `~/.claude/projects/<slug>/memory/.mutation-log.jsonl` (the durable,
   script-emitted trail) AND `--into <the --seed path>` **injects the audit block straight into the cycle record**
   (v0.1.53 — deterministic; do NOT hand-merge the printed JSON into `d["audit"]`, which KeyErrors on a seed that
   lacks the key). **Run this LAST in step 5** — after stamping `marker.timestamp` above — since `--into`
   read-modify-writes the seed (a later seed write would clobber the injected audit). It also prints the summary;
   only if you omit `--into` (or its write fails) paste that printed summary into the cycle record's `audit`
   block. This
   is the script-OBSERVED counterpart to your `entries[]` narration; they should AGREE — a divergence (a file
   changed that no entry mentions, or an entry with no file change) is a signal to investigate. HONEST GAP: the
   snapshot window attributes ANY change between Phase 0 and now to this pass (an interrupted/concurrent edit
   would mis-attribute) — don't over-trust it. Best avoided by **not committing to the repo while a dream runs**
   (a concurrent commit also moves HEAD → the marker advances past it; the dream detects HEAD-moved + re-measures,
   but can't fully disentangle a concurrent commit's files from its own). If HEAD moved, say so (cf. an audit op
   you didn't make = a concurrent commit, e.g. via `git log <before-marker>..HEAD`).
6. **Distill — surface repeated WORKFLOWS → propose a durable artifact (report-then-apply).** The dream's
   SECOND vertical: where the steps above consolidate FACTS into memory, distill detects repeated workflow /
   tool-use patterns and proposes packaging the high-confidence ones into a reusable artifact (a command or
   skill). Run the scan ONCE and save it (so the same counts you judge are the counts captured — no
   second scan whose window has drifted):
   ```bash
   CM_DREAM_ARC=1 python3 ${CLAUDE_PLUGIN_ROOT}/scripts/distill_scan.py . --json > <the --scan path>
   ```
   (`<the --scan path>` = a temp file, e.g. the snapshot dir's sibling `distill-scan.json`.) Read it:
   It returns recurring Bash-command **templates** (`recurring`, count≥2, each with a `days` episode-spread)
   AND **chains** (`chains` — adjacent steps inside one compound command: the `&&`/newline/`;`-glued
   sub-steps of a workflow), over a RECENT window (~30 days — deliberately BROADER than this dream's
   `marker..HEAD`; **say so**, so the user isn't confused why distill sees commands from outside this
   dream's scope). Ranking is by day-spread then count — rank is a HINT, not truth (a same-day high-count
   workflow can still be real). Credential-shaped commands COUNT into their class but their `sample` is an
   omission label (`scanned.secrets_omitted` says how many) — never a raw secret. The script only COUNTS —
   you do the judgment:
   - **READ THE CHAINS FIRST — a chain IS a candidate workflow** (e.g. `smoke → mypy → sim` = a gate-check
     pipeline). Then **RECOGNIZE the multi-command arcs** from co-ranked rows (e.g. a release cycle =
     `release.sh`+`gh pr`+`git checkout -b`/`push` recurring across the same days) — chains capture the
     intra-command glue; the cross-command arc is yours to see.
   - **GATE (all must hold):** it occurred **≥2×** AND has stable inputs AND a repeatable procedure AND a clear
     output/stopping condition AND is **NOT already covered** — inventory existing skills/commands first (the
     repo, the plugin, `~/.claude`) so you EXTEND/REUSE, never duplicate — AND is **NOT previously DECLINED**:
     read the last few `distill` verdicts from `<store>/.consolidation-log.jsonl` (tail the log; each record's
     `distill.verdict` encodes the disposition) — a previously-declined artifact needs materially NEW evidence
     (more episodes/days than when it was declined), never a re-ask.
   - **PROPOSE the SMALLEST form** (prefer a command over a skill over a subagent; on-demand over always-loaded
     — the destination-layer is the bloat lever). "Create nothing" is a frequent and honorable **verdict** —
     but it is a verdict the GATE produces, never a default you reach for.
   - **THE VERDICT (required — a distill step without it is incomplete):** end the phase with ONE plain-channel
     line naming (a) the scan scale (`N recurring · M chains`), (b) the **top candidate you actually
     considered** (a template or chain, by name), and (c) the disposition: `created <X>` ·
     `proposed <X> — awaiting confirmation` · `proposed <X> — declined` · `nothing: <top candidate> fails
     <which gate leg>` (e.g. "nothing: the smoke→mypy→sim gate-chain — already covered by release.sh").
     A bare "nothing" with no named nearest-miss is non-compliant. **Then CAPTURE it — counts are
     script-only, never hand-authored** (a hand-mirrored count already shipped an impossible value once).
     Feed the SAVED scan straight into the seed with `--from` (no second scan — the injected counts are
     byte-identical to the ones you just judged):
     ```bash
     CM_DREAM_ARC=1 python3 ${CLAUDE_PLUGIN_ROOT}/scripts/distill_scan.py \
         --from <the --scan path> --into <the --seed path> \
         --verdict '<the one-liner>' [--proposed <X>]... [--created <X>]...
     ```
     It injects the script-truth `sessions`/`commands`/`n_recurring`/`n_chains`/`window`/`secrets_omitted`
     into the seed's `distill` block, writing your judgment fields from the flags (`created` = authored
     BEFORE `--persist` only — confirmation usually arrives later; the record is an honest snapshot, never
     retro-written; `verdict` = the one-liner, one sentence — both dashboards show it in full). It **exits
     non-zero if the seed can't be written** (a typo'd path is caught, not silently dropped) and warns if a
     `--verdict`/`--proposed`/`--created` is passed WITHOUT `--into`. This `--into` is the **LAST write to
     the `distill` block** — a later hand-edit of the seed must not touch that block (targeted edits to
     OTHER keys only, same rule as the audit `--into`).
   - **REPORT-THEN-APPLY — present the proposal PLAIN / un-styled (never dream-voice an approval) and NEVER
     auto-write an executable artifact.** Show the artifact you would create + the evidence (the counts); the
     user confirms; only then you author it. A single confirmation authorizes **ONE specific named artifact**
     (not "build out the workflow") — re-propose each. (Public-plugin blast radius; the conductor/Stop-hook were
     rejected for exactly this — auto-authoring an always-on/executable artifact is the highest-blast-radius move.)
   - **GENERICIZE before authoring (PUBLIC-plugin safety):** the firewall suppresses the *samples* of
     credential-shaped commands and screens every emitted template — but it does NOT catch machine-specific
     values: a proposed/authored artifact must carry **no absolute paths, host/machine names, or personal
     values** (a clean `sample` may still show `python3 /home/you/…`; use relative paths + `<arg>` placeholders).
   - **HONEST GAP:** an authored artifact lands in `skills/`/`commands/` (repo or `~/.claude`), OUTSIDE the
     Phase-5 `--audit` mutation trail (memory store + CLAUDE.md only) and the dashboard — so an authored artifact
     has no audit record; **name it explicitly in the closing debrief** and fold the verdict into the debrief.
7. **Render the dashboard AND persist the record** — this is the skill's output (see below):
   ```bash
   CM_DREAM_ARC=1 python3 ${CLAUDE_PLUGIN_ROOT}/scripts/render_dashboard.py <the --seed path> \
       --persist ~/.claude/projects/<slug>/memory
   ```
   `--persist <store dir>` appends the rendered record (one JSON line) to
   `<store>/.consolidation-log.jsonl` — the per-project cycle log that accrues
   magnitude→(applied, outcome) data for a future band calibration. It is idempotent and
   **skips persisting an unstamped cycle** (the render still succeeds), so run it AFTER
   step 5 stamps `marker.timestamp`.

   **Procedure-integrity gate (v0.1.44).** Because this terminal `--persist` is the one step
   every finishing dream runs, the render also JUDGES the completed dream here: if a
   SUBSTANTIAL-or-larger-MAGNITUDE pass recorded **0/0/0 verification** (the lazy-skip — you
   skipped the Phase-3 fan-out), it prints a loud **PROCEDURE INTEGRITY ⚠** panel, persists the
   record (so the failure is logged + shows in the archive), and then **exits 3**. That nonzero
   exit means THIS dream is incomplete — go run the Phase-3 verification fan-out, then re-render
   (a clean pass exits 0; THEN continue Phase 5 — `--diffs`, `render_html`). It is a DETECTOR (not a
   block — the dashboard prints first); a seed/preview render WITHOUT `--persist` is the BEFORE
   state and is never judged. **SCOPE (be honest about what it does NOT catch):** it catches the
   *measured* lazy-skip — a skipped **Phase-3** verification (0/0/0 on a substantial pass) — NOT the
   general "skipped a phase" class: a pass that DOES verify but skips the Phase-1 re-audits or the
   Phase-5 GC/stale-reverify records `tally>0` and is spared, and a diligent liar who types fake
   tallies defeats it. Rare false-positive: a substantial-commits pass with genuinely nothing
   memory-relevant to verify fires too — note it and proceed (the ⚠ is a signal, not a block).
   The dashboard now includes a **"Neural network — token consumption (all nodes)"**
   sub-section: the per-node and total estimated token tax across the network, plus
   what *this* cycle did in lifecycle terms on the triggering node (the node `dream`
   ran on).

   Then **capture the per-file diffs** (v0.1.32; every `audit_snapshot` store as of v0.1.72) for
   the dashboard's diff-modal — the before/after of each changed memory fact, the `MEMORY.md`
   index, the CLAUDE.md hierarchy, and relocate-target repo docs. This MUST run AFTER `--persist`
   (so `marker.timestamp` is stamped) and BEFORE `render_html` (so the dashboard embeds it):
   ```bash
   CM_DREAM_ARC=1 python3 ${CLAUDE_PLUGIN_ROOT}/scripts/memory_status.py --diffs <the --seed path> \
       --before <the --snapshot path>
   ```
   It writes a per-dream sidecar `dashboards/diffs/<commit>__<timestamp>.json` (per-file diff
   capped; `chmod 600`, so fact bodies stay owner-only) that `render_html` reads to make each
   changed file clickable in the dream view — a memory fact's own ledger row links inline; a
   changed `MEMORY.md`/CLAUDE.md/repo-doc has no per-entry name convention to match, so it's
   appended as its own `changed` row instead (nothing observed is ever silently dropped). A
   claude_md/repo_doc file too large to snapshot (`_DIFF_CONTENT_CAP_TOKENS`, memory facts are
   exempt — always small) still gets its op recorded, flagged `size_capped` instead of a
   misleading partial diff. Best-effort — skipped (never crashes a dream) if the cycle is
   unstamped or the snapshot is missing.

   Then generate the **rich HTML dashboard + dream ARCHIVE** — the visual sibling of the ASCII
   report (one cycle-record contract, two renderers): the same data plus the longitudinal
   index-budget trajectory, rendered into the per-repo archive mini-site.
   ```bash
   CM_DREAM_ARC=1 python3 ${CLAUDE_PLUGIN_ROOT}/scripts/render_html.py <the --seed path> \
       --store ~/.claude/projects/<slug>/memory --latest
   ```
   It writes a ZERO-dependency, self-contained `dashboards/index.html` (the whole per-repo
   archive of dreams in one file) and **auto-opens this dream's dashboard** (`--latest` →
   `#sel=<newest>`); headless-safe (no browser → prints the path; `--no-open` suppresses).
   This is the **post-dream payoff, and it is MANDATORY**: a cleanly completing dream is **not done
   until `render_html … --latest` runs.** Its `webbrowser.open()` auto-open is the whole point —
   **never pass `--no-open` in a normal dream** (headless degrades to printing the path, the only
   non-open path). Reaching a clean (exit-0) `--persist` and stopping *without* `render_html` means you
   have NOT finished. **Two carve-outs:** (1) it is mandatory only on the clean **exit-0** pass —
   **never run it right after an exit-3** `--persist` (that would paper over the very lazy-skip the
   integrity gate exists to catch; go re-verify and re-render to exit 0 FIRST — see the procedure-integrity
   gate above); (2) a **true Phase-0 no-op** never reaches Phase 5, so it has no dashboard and no path
   (see *The dream arc* → Proportionality).

   **Then WAKE — and only then debrief.** With the ASCII dashboard already printed in-terminal (the
   clean exit-0 `render_dashboard --persist` above) and the HTML auto-opened, emit the **WAKE block**
   — 2–5 italic lines surfacing out of the dream (`*☀️ …*`), full stop — no trailing bolded "Awake."
   line (v0.1.64; see *The dream arc* → *The debrief*) — straight into the debrief next (see
   *The dream arc*; `dream.wake` was already composed into the record at the final fill, before
   `--persist`). Then deliver the
   structured **session debrief** — qualities + proportionality pinned in *The dream arc*: ONE bold
   lead line naming the outcome banner (text only, no emoji — WAKE already closed the dream; see
   *The dream arc* → the debrief), bold-headed sections, dense bullets that **FRAME** the pass (the
   non-obvious WHY + what was KEPT / PRUNED / verified — and the **distill outcome**: any workflow artifact
   proposed / created, or nothing) rather than re-tabulate the dashboard's gauges,
   **scaled to the outcome banner** (a no-op / maintenance / light pass gets one or two lines + the path,
   NOT the full debrief). The debrief **ends on the 📊 dashboard path** — the self-contained file at the
   STABLE per-repo path `~/.claude/projects/<slug>/dashboards/index.html` — and tells the user they can
   **re-open it any time by opening that file** (it holds the whole archive; navigate dreams in-page via
   the ledger/filenames; it IS the fleet-wide re-open — works from any repo). Do **NOT** tell an end-user
   to run `cm report`: that is a MAINTAINER dev CLI living only in the consolidate-memory repo (not on a
   plugin user's PATH, and it CWD-defaults), useful only when dogfooding this plugin from its own checkout.

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

The **data** report is **not** free-form prose. It's a fixed dashboard whose content is
driven by what the pass actually did. You accumulate a small JSON **cycle record**
through the phases (seeded by `memory_status.py --json`), then render it with
`render_dashboard.py` — the model produces the data, the script produces the
presentation, so the report is consistent run-to-run but reflects this cycle (a
no-op pass and a heavy pass render visibly differently; empty sections collapse, and
the outcome banner is derived from the write counts).

The render script is the single source of the **data** report — the gauges, counts, and
tallies; **don't re-tabulate them in prose.** The dream's closing **debrief** (see *The dream
arc*) is the complementary half — it **FRAMES** the dashboard (the non-obvious WHY + what was
kept / pruned / verified) and cites a figure only when it carries the point (e.g. "8443→2685
tok, all lessons kept"). So: **frame the data, don't duplicate it — and don't drop the numbers
that carry meaning.** (The debrief is a structured synthesis, not the ad-hoc free-form prose
this once warned against; the dashboard remains the source of the figures.)

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
     "citation": "<commit sha | session id | empty>",
     "files": ["<audit_snapshot label(s) actually changed — memory/x.md | memory/MEMORY.md | claude_md/CLAUDE.md — empty if nothing tracked changed>"]}
  ],
  "budget": {
    "claude_md": {"before": 0, "after": 0, "before_tokens": 0, "after_tokens": 0,
                  "budget_tokens": 4000, "over": false},
    "global_claude_md": {"present": false, "lines": 0, "tokens": 0,
                         "budget_tokens": 4000, "over": false},
    "index": {"before_lines": 0, "after_lines": 0, "before_bytes": 0, "after_bytes": 0,
              "before_tokens": 0, "after_tokens": 0, "budget_tokens": 1500, "over": false,
              "fat_hooks": 0, "hook_max_tokens": 0, "cliff_pct": 0, "ceiling_tokens": 3840},
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
    "held": 0,   "_held": "v0.1.38 (M1): new-global pulls --pull HELD (v0.1.66: would push the index past the HARD CEILING) — shrink to receive",
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
    "_": "v0.1.18: present ONLY when the index is OVER budget (the GATE); absent on a healthy store. v0.1.21: when standing_justified the gate is SUPPRESSED (required=false) until fact-count grows by Δ. v0.1.66: over_ceiling is a SIBLING signal (the hard ceiling, SJ-independent) — never a re-key of required. Seeded by Phase 0; pruned/achieved_* filled in Phase 5.",
    "required": false, "lever": "prune|gc|justify",
    "candidates_surfaced": 0, "pruned": 0,
    "projected_index": 0, "achieved_index": 0,
    "projected_recall": 0, "achieved_recall": 0,
    "standing_justified": false, "baseline_facts": 0, "reaches_budget": true,
    "over_ceiling": false
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
  "dream": {"sleep": "<the SLEEP stanza, raw `*💤 …*` markdown — italics only, no blockquote>",
            "beats": ["<each phase's dream block, in order (surfacing line included)>"],
            "wake": "<the WAKE stanza — composed at this final fill, performed after the render>"},
  "distill": {"sessions": 0, "commands": 0, "n_recurring": 0, "n_chains": 0,
              "window": "<the scan window ISO, script-injected>", "secrets_omitted": 0,
              "proposed": [], "created": [],
              "verdict": "<one line: created X | proposed X — awaiting confirmation | proposed X — declined | nothing: <candidate> fails <gate leg>>"},
  "usage": {"_": "v0.1.63 (Phase A): script-injected by extract_signals --recalls --into (Phase 5) — organic fact-body Read events in the window, dream-span excluded; counts are script-only, never hand-authored. 0 reads = absence of evidence, never evidence of no use. v0.1.67 (Phase C): archive_reads/misses = the MISS-DETECTOR — organic reads of ARCHIVED-tier facts (tier judged at window start via --before <snapshot>); a miss is a demotion error: re-promote the pointer, and the log's misses permanently veto the stem from future candidacy.",
            "window": "<since..now ISO>", "transcripts": 0, "dream_excluded": 0,
            "reads": 0, "facts_read": 0,
            "per_fact": [{"name": "...", "reads": 0, "last": "<ISO>"}],
            "archive_reads": 0, "misses": []},
  "demotion": {"_": "v0.1.67 (Phase C): the rank-under-budget demotion triage. windows_observed/eligible/surfaced are SCRIPT-seeded (Phase 0, from the accrued usage log — the per-fact evidence gate keeps it DORMANT until ≥3 probative zero-read windows + corroboration); struck is SCRIPT-written by --recalls --into (surfaced stems read THIS window — never demote). Dispositions are entries[] rows (single source — no counts here); verdict is the ONE model sentence (a dormant/none verdict is still a verdict).",
               "windows_observed": 0, "eligible": 0,
               "surfaced": [], "struck": [],
               "verdict": "<one line: dormant — N probative windows | demoted X · justified Y | none: <top candidate> kept because …>"},
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
