# Spec — completion-driven archiving (decouple archive from the over-budget gate)

Status: DRAFT (gate-1 review pending) · target: cm vNEXT (PATCH) · author cycle: 2026-06-22

## The measured problem (not the one the audit first named)

The 2026-06-22 harness audit flagged "CM's index budget (1200 tok) is ~5× tighter than
native's 25 KB — relax it." **Deeper measurement flipped that diagnosis:**

- **Active-set demand ≈ the current budget.** Real stores measured: `consolidate-memory`
  22 facts / **1181 tok** (all active — standing lessons + roadmap), `job-applicator-python`
  22 / **1056 tok** (all active). Both fit 1200; neither has an archive.
- **Doc-Flo's 230 %-over is completed-arc accumulation, not active content.** 107 facts:
  ~63 already archived to `SHIPPED.md`, ~21 genuinely active, and **~25 COMPLETED arcs still
  lingering in the always-loaded index** (≈ the entire overage).
- **Why they linger: archiving is BUDGET-triggered.** The SKILL places archiving inside
  Phase-5 step 0 — "the over-budget remediation GATE — when `remediation.required`."
  `remediation_triage()` returns `{}` while `index_tokens <= budget`. So a completed arc's
  pointer is only relocated to the on-demand archive *once the index is already over budget* —
  it sits in the always-loaded tier until then, and judgment-gating/standing-justify can leave
  it indefinitely.

**Native's 25 KB is a hard *truncation* limit, not a target.** Sizing the budget toward it
would just let completed-arc cruft accumulate in the always-loaded tier every session — the
low-value direction (native would not want a 25 KB index of done-work pointers either). The
"hidden 57 %" on Doc-Flo are mostly completed arcs that *should* be on-demand.

**Root cause:** the always-loaded index should equal the **active / lesson-bearing set**, but
the archive trigger is the *budget* (a symptom) instead of *arc completion* (the cause).

## Principle

The always-loaded `MEMORY.md` index holds the **active / lesson-bearing set**. A
completed / merged / superseded arc — whose durable lessons are already extracted into kept
facts — belongs in the **on-demand archive index** (`SHIPPED.md`, an `_is_archive_index`
link-list), not the always-loaded tier. Archiving is therefore **completion-driven** (runs
every dream, for completed arcs, regardless of budget), not budget-driven. The over-budget
remediation gate remains as a *separate escalation* for the rare case where the **active set
alone** exceeds budget.

**The same principle applies WITHIN a long-lived fact file.** An active status/roadmap file
accumulates completed/stale items in its BODY over time — `consolidate-memory-roadmap.md` is
~**7681 tok (~10× the store median)**, mostly shipped-version history. The body is *on-demand*
(not always-loaded), so this taxes **read-cost, accuracy, and signal-density** rather than the
always-loaded index directly — but curating it is squarely the consolidation mandate ("keep
what's true and useful, discard what isn't"), and it keeps files **accurate, up-to-date, and
near the store's typical length**. This is **body-defragmentation** (Mechanism 2). It is
distinct from pointer-archiving — that file is *active* (its pointer stays in the index); only
its body is curated. Higher-risk (intra-file judgment) → its own gated cycle.

**Two mechanisms, two cycles (risk-isolated):** Cycle 1 = completion-driven *pointer-archiving*
(below, the whole-completed-fact case + the budget re-ground). Cycle 2 = *body-defragmentation*
(the intra-file bloat case). One principle (the store holds active content; completed/stale is
curated out), sequenced so the higher-risk body-trim gets its own focused gate.

**Vision (baked in as PRINCIPLE, not machinery):** Phase 5 is an **always-on staleness/defrag
sweep** — cheap surface curation (completed-pointer archiving, body-defrag) runs *every dream,
across tiers, decoupled from capacity*; the over-budget remediation gate is a **backstop**, not
the trigger. This spec builds only the *measured* surface layer; deeper always-on re-verification
is gated on evidence (see Honest limits — measured 2026-06-22, deferred).

## Mechanism

### 1. New pure helper — `archive_candidates()` (memory_status.py)

Surfaces **INDEXED, non-mirror** facts that read as COMPLETED, regardless of budget:

```
archive_candidates(fact_files, index_names, *, reference_stems=None) -> list[dict]
```

- **Flag** an indexed fact iff its stem is dated (`_DATED_RE` — the Auto-Dream/CM `_YYYY_MM_DD`
  completed-arc convention). **(Implementation note, empirical:** an early body-completion-marker
  variant also flagged active files — `next_priorities`, live lessons — too noisy; the dated stem
  is the high-precision signal. A non-dated completed arc falls to the model's Phase-5 judgment.)
- **Never flag (KEEP signals — conservative):** a mirror (`_is_mirror`); a fact carrying a
  *lesson / negative / directive* marker (`NEVER|DON'T|DO NOT|don't retry|gotcha|footgun|
  always …` or an active-state/roadmap marker) — the SKILL's existing rule: *"a dated pointer
  that is really a live lesson STAYS"*. When the completion signal and a keep signal co-occur,
  **keep** (false-negative bias — a missed archive costs an extra always-loaded pointer; a
  wrong archive silently drops a live lesson, the worse failure).
- Returns ranked candidates `{stem, body_tokens, reason}` (reuse the C-stage shape). PURE,
  read-only, never raises (OSError → skip). This is a *surface*, not a decision — identical
  contract to `remediation_triage`: heuristics rank, the model judges content, the user confirms.

### 2. Phase-0 / status surface

`memory_status.py` reports an **"archive candidates: N"** **stdout** advisory line (printed like
the dream-timing nudge — NOT written to the cycle record, unlike slug-orphans/schema-drift which
ARE `health` keys) — N indexed pointers that look like completed arcs. Read-only; Phase 0 never mutates.

### 3. SKILL change (Phase 5) — a standing completion-driven archive step

Add a **standing archive step that runs EVERY dream** (not gated on `remediation.required`):
review `archive_candidates`, apply the keep-vs-archive JUDGMENT (the existing
silent-failure warning + KEEP signals above), **propose-then-apply** (Safety rule — never
auto-archive), relocate confirmed completed-arc pointers `MEMORY.md` → archive index, record
each as a `reconciled` `entries[]` row (pointer relocated; body unchanged — already the
pattern). The over-budget remediation gate (step 0) stays as the *escalation* for genuine
active-set overflow, and now rarely fires because proactive archiving keeps the index lean.

### 4. Budget — re-grounded, modest headroom

- `INDEX_TOKEN_BUDGET`: **1200 → 1500.** Basis (replacing the arbitrary 1200): the measured
  active-set demand (~1100–1200 across real stores) **+ ~25 % growth headroom** — so the
  always-loaded tier holds the active set comfortably without edge-flapping (`consolidate-memory`
  is at 98 % of 1200 today). Native's 25 KB (~6400 tok) is the far-above **hard-truncation
  ceiling**, NOT the sizing target. Re-document the constant's comment accordingly.
- `PRUNE_PRESSURE_FACTS = 40`: **keep** (re-document) — a terse-pointer backstop above the
  budget's fact-equivalent; with proactive archiving it rarely binds.
- `CLAUDE_MD_TOKEN_BUDGET = 4000` / `GLOBAL_… = 4000`: **keep** — already ≈ native's
  "target < 200 lines / ~16 KB" CLAUDE.md guidance (verified). No change.

## Mechanism 2 (Cycle 2) — body-defragmentation

Scoped here for direction + sequencing; the full detail gets its own spec + gate-1 when Cycle 2
opens. Distinct from Mechanism 1 (different detection, action, and risk).

- **Detection — `defrag_candidates()` (pure helper):** surface fact files whose **body is an
  outlier** — `body_tokens` above K× the store's *median* fact size (the roadmap at ~10× median
  is the canonical hit) AND/OR a high density of completed/dated items in the body (multiple
  `_DATED_RE` + body completion-marker hits). Ranked, conservative; the model judges. Surfaced as a
  Phase-0 advisory ("defrag candidates: N").
- **Action — Phase-5 sub-phase (model-judged, propose-then-apply):** for a flagged ACTIVE file,
  curate the BODY item-by-item:
  - **PRUNE** items whose detail is redundant with git/CHANGELOG (the SKILL's "don't duplicate
    what git/CHANGELOG records" — e.g. collapse per-version "vX.Y.Z shipped …" history into a
    one-line "vA–vB shipped" summary; the detail lives in the CHANGELOG, *verifiably*).
  - **RELOCATE** still-useful-but-completed detail to an archive doc (a roadmap-archive /
    `SHIPPED.md`) when worth keeping but not active.
  - **KEEP** active/forward content (OPEN items, current state, watch-list, live lessons /
    negative findings — the same KEEP signals as Mechanism 1).
  - Result: the file returns toward the store's typical length, kept accurate + forward-looking.
- **Risk — HIGHER than pointer-archiving** (intra-file trimming can drop an active item buried in
  a completed section, or lose a live lesson). Guards: conservative detection; **item-by-item
  model judgment**; **propose-then-apply showing the before/after diff** (the Phase-5 `--diffs`
  machinery already captures per-file diffs — reuse it as the confirmation surface); the
  pruned-because-redundant case is verifiable against git/CHANGELOG, lowering risk. **Never
  auto-trim.**
- **Dogfood first:** the `consolidate-memory-roadmap` itself is Cycle 2's first target (it has
  bloated this very session) — eat our own dog food before shipping the behavior generally.
- **Tier honesty:** this optimizes the *on-demand* read-cost + accuracy + signal-density, NOT the
  always-loaded index directly (the pointer stays). Don't conflate its benefit with Mechanism 1's.

## Contract impact — NONE (→ PATCH)

- **No CycleRecord schema change.** Archiving records existing `entries[]` `reconciled` rows;
  the candidate count is a Phase-0 **stdout-only** advisory (printed, NEVER written to the cycle
  record — NOT a `health` key, which would be a pinned TypedDict field) — no new typed key,
  so the seed / renderer / TypedDicts / SKILL schema block / smoke pin are untouched.
- Legacy cycle records render unchanged. No removed/renamed script or flag. The budget constant
  changes *value* (1200→1500), not the schema. Backward-compatible ⇒ **PATCH** (release.sh
  derives the bump from the CHANGELOG).

## The load-bearing risk (what gate-1 must scrutinize)

The budget-trigger was an implicit **throttle**: archiving only happened under pressure, so a
mis-judged archive was rare. Making it proactive (every dream) **shifts weight onto the
keep-vs-archive judgment** — and archiving a *live* lesson silently drops it from recall (the
SILENT failure mode the SKILL already warns about). Mitigations, all required:
1. **The load-bearing guard is propose-then-apply + the reachable/reversible archive (#2–3),
   NOT the heuristic.** `archive_candidates`' KEEP signals are **sufficient-not-necessary** — a
   dated/SHIPPED-marked fact with no `NEVER/DON'T` marker (e.g. the SKILL's canonical "live
   SQL-oracle lesson that STAYS") WILL be flagged; the helper only RANKS, and the model must
   affirmatively judge each candidate is non-active before archiving. Completion-driven archiving
   makes candidates *surfaced unconditionally + judged every dream* — the fix is **surfacing, not
   a forcing function** (the relocation action stays propose-then-apply).
2. The decision stays **model-judged by content + propose-then-apply** (never auto-archive) —
   unchanged from today.
3. The archived body **stays on disk + reachable** via the archive index (`SHIPPED.md`); the
   `dangling_links`/`valid_link_targets` machinery already treats archive docs as real targets,
   so a relocated pointer doesn't dangle. Archiving is **reversible** (relocate the pointer back).

## Blast radius (measured)

- `remediation_triage` — UNCHANGED (still the over-budget escalation; its C-stage already uses
  `_DATED_RE`). The new helper is sibling logic, budget-independent.
- `beta_checks.py` (release gate) — **imports `memory_status` live** + reads the skill's own
  `remediation` fields → budget-number-agnostic; safe. Add a check for the proactive-archive
  surface (optional, cycle-end).
- `simulate_accumulation.py` — reads `INDEX_TOKEN_BUDGET` live. **Probe L's fixture index is
  ~1227 tok — BELOW the new 1500 → `over` goes False, triage returns `{}`, the probe COLLAPSES
  (it gates `release.sh`).** Fix: resize the Probe-L fixture above 1500 (bump its hook repetition
  `*3 → *4`); re-check the D6 probe's thin 1594-tok margin. **Add** a probe: a store of completed
  arcs UNDER budget still yields `archive_candidates` (the decoupling), an all-active store none.
- `smoke.py` — add `archive_candidates` unit checks (below). Verify nothing pins `1200`.
- Dashboard / render_html — mirror the 1200→1500 constant (`render_html.py` line 29). The
  "arcs archived this pass" is derivable from `entries[]`; no new field.

## Test plan (acceptance)

- **smoke** (`archive_candidates`): flags a dated/SHIPPED-marked indexed fact; **spares** an
  all-active store (cm/job-app → 0 candidates); **spares** a dated-but-lesson-bearing fact
  (KEEP signal wins — the silent-failure guard); spares mirrors; never raises on unreadable/
  malformed; an UNINDEXED dated fact is NOT a candidate (only indexed pointers cost always-loaded
  budget).
- **separation**: against Doc-Flo's live store, the helper flags the ~25 lingering completed
  arcs and spares the ~21 active (sample-verified, not pinned).
- **sim**: Probe L's fixture RESIZED above 1500 so over-budget triage still fires; the new
  under-budget completion-driven probe (above) passes.
- **budget**: 1500 is live across memory_status + render_html; cm/job-app sit < 80 % of it.
- **green gate**: smoke + mypy + sim + manifests + `plugin validate --strict` + beta-gate 0-FAIL.

## Honest limits / out of scope

- Heuristic completion-detection will mis-rank some facts (the C-stage already does) — that is
  WHY the model judges + the user confirms; the helper never auto-archives.
- A "diligent" wrong archive (model archives a live lesson the user confirms) is not prevented —
  same human-in-the-loop limit as every CM write; the conservative helper + the reachable archive
  (reversible) bound the cost.
- Auto-detecting a *superseded* fact (newer fact obsoletes an older one) is left to the existing
  Phase-1 dedup/supersession judgment; this spec adds only completion-driven *archiving*, not
  supersession detection.
- NOT changing `remediation_triage`, the over-budget gate, M1 held-pulls, or the lever routing —
  those stay for genuine active-set overflow.
- **Layer 2 (always-on DEEP re-verification rotation + a fleet-wide `last_verified` frontmatter
  schema) — DEFERRED on evidence.** A bounded staleness-rate probe (2026-06-22) measured ~**10 %
  SUBSTANTIVE** stale over month-old facts (one config-default drift; the rest recoverable
  file-relocation or resolved action-queues) — far too low to justify a minor-version,
  fleet-touching schema migration + rotation engine. Recorded as a watch-item.
- **The measured real failure mode is FILE-PATH DRIFT** (facts cite relocated files; symbols /
  behavior intact). The cheaper, better-targeted fix is a **path-existence health check +
  symbol-level fact-anchoring** — a candidate to scope/measure in a later cycle, NOT to reflexively
  build here.
```