# Spec — body-defragmentation (curate bloated ACTIVE files) · Cycle 2

Status: DRAFT (gate-1 review pending) · target: cm vNEXT (PATCH) · follows Cycle 1 (completion-driven archiving)

## The measured problem

Cycle 1 archives whole *completed* facts (dated pointers → on-demand archive). This cycle
handles the orthogonal case: a long-lived **ACTIVE** file whose BODY has accumulated
completed/stale items over time. Measured (2026-06-22), body-size outliers (indexed,
non-mirror, NON-dated, body > 2.5× the median) — exactly **2 fleet-wide** (median taken over that
SAME population — indexed, non-mirror, non-dated `body_tokens` — for self-consistency/reproducibility):

- `consolidate-memory-roadmap` — **8004 tok, ≈12.7× the ~629-tok median**; ~13%+ of lines are
  explicit shipped-version history (`v0.1.x`/`SHIPPED`), whose detail is *redundant with the
  CHANGELOG + git* — plus more completed-arc detail the simple grep misses.
- Doc-Flo `next_priorities` — 8624 tok, **≈9.1× the ~950-tok median**.

A bloated active file is *on-demand* (not always-loaded), so this taxes **read-cost, accuracy,
and signal-density** (active content buried in completed history), not the always-loaded index
directly — but curating it is squarely the consolidation mandate ("keep what's true and useful,
discard what isn't"), and keeps files **accurate, up-to-date, and near the store's typical length.**

## Principle

An active file's BODY should hold **active / forward / lesson-bearing** content. A completed or
superseded item in the body is collapsed (if its detail is redundant with git/CHANGELOG) or
relocated (to an archive doc, if still worth keeping but not active). Distinct from Cycle 1: the
file is *active* (its index pointer STAYS); only its body is curated.

## Mechanism (light — mirrors Cycle 1's helper + SKILL pattern)

### 1. `defrag_candidates()` (pure helper, memory_status.py)

```
defrag_candidates(fact_files, index_names, *, factor=2.5) -> list[dict]
```
- Flag INDEXED, non-mirror, **NON-dated** (a dated fact is Cycle-1's pointer-archive domain, not
  body-defrag) facts whose `body_tokens` exceeds `factor ×` the **median `body_tokens` over that SAME
  population (indexed, non-mirror, non-dated) — self-consistent**. **Edge guards:** return `[]` when
  that population has <3 facts or a non-positive/degenerate (all-equal) median (no div-by-zero, no
  noise on a tiny/uniform store). Return `{stem, body_tokens, ratio}`, ranked by size. PURE,
  read-only, never raises. RANKS only — the model curates by content + the user confirms (no write
  path here), like `archive_candidates`.
- Conservative: a body-SIZE outlier is a structural signal (cheap, robust), not a content judgment
  — it surfaces "this file is unusually large"; WHAT to trim is the model's judgment.

### 2. Phase-0 stdout advisory

`memory_status.py` prints `defrag? N bloated active file(s) (≫ store median)` — detect-and-offer,
stdout only (NOT written to the cycle record → no schema change).

### 3. SKILL Phase-5 sub-phase (the always-on sweep gains a body-defrag step)

For each flagged ACTIVE file, the model curates the BODY **item-by-item**:
- **COLLAPSE** items whose detail is redundant with git/CHANGELOG — e.g. per-version "v0.1.x
  shipped …" history → a one-line "v0.1.A–v0.1.B shipped (see CHANGELOG)" summary. The detail is
  redundant with the CHANGELOG. **Operationalized: before collapsing, READ the CHANGELOG/git and
    CONFIRM the to-be-collapsed detail is actually present there** ("redundant" is verified, not
    assumed) — else KEEP or relocate, never collapse.
- **RELOCATE** still-useful-but-completed detail to an archive doc (a roadmap-archive / `SHIPPED.md`).
- **KEEP** active/forward content (OPEN items, current state, watch-list) and **live lessons /
  negative findings** (the same KEEP signals as Cycle 1).
- Result: the file returns toward the store's typical length, kept accurate + forward-looking.

## Safety — HIGHER risk than Cycle 1 (intra-file), so:

1. **Conservative detection** (a body-SIZE outlier, not a content guess) — `factor 2.5×` surfaced
   exactly 2 real files, no noise.
2. **Item-by-item MODEL judgment** — the helper says "this file is bloated," never "trim line N."
3. **Propose-then-apply IN-CONVERSATION, BEFORE writing** — show the proposed body edits + confirm
   (the same Safety-rule gate Cycle-1 archiving uses — SKILL Phase-4/Safety "show + confirm"),
   **never auto-trim**. The Phase-5 `--diffs` sidecar runs AFTER `--persist`, so it is the POST-write
   audit/dashboard record of the trim, NOT the pre-apply confirmation surface.
4. **Collapse only the verifiably-redundant** (detail present in git/CHANGELOG) — the lowest-risk
   trim; relocate (reversible) over delete when unsure; KEEP on any doubt.

## Dogfood first

The `consolidate-memory-roadmap` IS Cycle 2's first target (bloated this very session). Defrag it
as the worked example + the test case (measure before/after; the active content — OPEN items, watch-
list, the audit decisions, [[links]] — must survive; the v0.1.x shipped-history collapses).

## Contract impact — NONE (→ PATCH)

No cycle-record schema change: the defrag advisory is stdout-only; the curation records existing
`entries[]` `reconciled`/`corrected` rows + the `--diffs` sidecar. No new TypedDict key, no SKILL
schema-block change, no smoke-pin change. Legacy records render unchanged. Backward-compatible ⇒ PATCH.

## Test plan

- **smoke** (`defrag_candidates`): flags a bloated active fact (body ≫ median); spares a lean fact;
  spares a DATED fact (Cycle-1's domain); spares a mirror; spares an unindexed fact; never raises;
  the median is computed over the right population; and it returns `[]` on a <3-fact or
  all-equal-median store (the edge guards).
- **separation**: against the live stores, flags exactly the cm roadmap + Doc-Flo `next_priorities`,
  spares the rest (sample-verified).
- **dogfood**: the cm roadmap defrag — measured before/after token drop; assert the active content
  (OPEN/watch/decisions/links) survives by inspection (the `--diffs` review).
- **green gate**: smoke + mypy + sim + manifests + `plugin validate --strict` + beta-gate 0-FAIL.

## Honest limits / out of scope

- The body-curation is **model judgment**; the helper only surfaces the bloated file. A wrongly-
  trimmed active item is the risk — bounded by propose-then-apply + the diff + git-verifiability +
  relocate-over-delete. Same human-in-the-loop limit as every CM write.
- `factor 2.5×` is a tunable default (surfaced 2 real files cleanly); not a calibrated constant.
- NOT auto-collapsing — the model proposes, the user confirms. NOT touching dated facts (Cycle 1's
  pointer-archive handles those). NOT the deferred deep-reverify rotation (evidence: ~10% stale).
- **Overlap (benign, documented):** a bloated non-dated indexed fact may ALSO surface in
  `remediation_triage` stage-C (`_OVERSIZED_TOK` = 2500) **when over budget** — but both RANK-only
  (the model decides), so no conflict. The defrag advisory is **always-on**; remediation-C is
  **budget-gated**. No interaction with Cycle-1 `archive_candidates` (disjoint by the dated-stem gate).
