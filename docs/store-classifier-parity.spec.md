# Store classifier parity — the shapes the counters don't know

**Status:** design-of-record · **Cycle:** `fix/store-classifier-parity` · **Target:** v0.4.31 (patch)

## 1. Context

A `dream` pass on 2026-09-14 completed to a clean exit 0 and produced a record whose drift
counters were **wrong in four fields** and whose Phase-5 remediation docket named **three
things that must never be deleted**. Nothing failed; every gate that ran passed.

Root-caused here: **two classifiers in the store-honesty path each know fewer fact shapes than
the store actually holds.** Neither is a counting bug — both are predicates whose acceptance
set is narrower than the set of legitimate inputs, so the error is structural and every
downstream consumer inherits it identically.

This is the same family as the cycle-A audit (*"every gate is narrower than the rule it is
believed to enforce"*), but the failure direction differs: cycle A's gates failed **clean**
(a false pass), these fail **noisy and destructive** (manufactured findings plus a deletion
recommendation).

## 2. Root cause A — the archive classifier's link floor

`memory_status._is_archive_index_text` decides *"is this a store-root `.md` an archive index
(a pointer list) or a fact?"* by two tests: **no fact frontmatter**, then **at least three
`](stem.md)` links**.

The live archive doc has **two**. It therefore falls through the second test, is classified as
a **fact**, and `archive_docs` comes back **empty**.

### 2.1 The four corrupted counters

Measured on the live store, with the single misclassification corrected:

| `health.schema_drift` field | recorded | true | why |
| --- | --- | --- | --- |
| `missing_node_type` | 2 | 1 | the archive doc has no frontmatter, so it counts as a fact missing `node_type` |
| `index_mismatch` | 4 | 1 | `archive_docs == []` does double damage: the archive is itself a fact with no index pointer, **and** `placed_fact_names` never unions its link targets, so the two facts whose pointers live in the archive also read as unplaced (3 of the 4) |
| `advisory_no_scope` | 17 | 16 | same file, counted as a fact lacking `scope` |
| `advisory_no_origin` | 2 | 1 | same file, counted as a fact lacking `originSessionId` |

`drift_findings` — the AC#1 "clean store" gate — reads **6**. Correcting the archive
misclassification alone takes it to **2**; root cause B (§3) takes it to the **1** genuine finding.
Both readings are measured, not derived: the `true` column is the live store on a tree carrying the
archive arm alone, one tree per process.

### 2.2 The destructive direction

`remediation_triage` Stage A is labelled, in its own docstring, *"TRUE orphans (unindexed AND
unreferenced — dead weight; **evict OR re-index**)"*. Measured on the live store, one tree per run:

| stage | pre-fix | fixed |
| --- | --- | --- |
| `A_orphans` | `['<the fact whose pointer lives in the archive>', 'SHIPPED']` — **2** | `[]` — **0** |
| `R_referenced` | `['<fact A>', '<fact B>']` — **2** | `['<fact A>', '<fact B>', '<the fact whose pointer lives in the archive>']` — **3** |

**The archive itself is a Stage-A candidate — and so is one of the two facts whose pointers live in
it.** `SHIPPED.md`, whose entire purpose is to hold the pointers that keep archived facts *reachable*,
is flagged dead weight to **evict OR re-index**; and that fact reads unindexed **and** unreferenced
precisely because the archive was never recognized as a reference surface, so it is named as safely
evictable while the archive that references it is named for deletion alongside it. The **second**
archived fact escapes Stage A by accident, never by design: a `[[wikilink]]` from a surviving fact
reaches it, so it lands in `R_referenced` instead — the docket's single rescue is a property of an
unrelated edge, not of the archive. This is the
finding that makes the cycle necessary: the defect is not a miscount, it is a recommendation to
destroy memory, emitted on a pass that reported success.

The fixed column is **empty**, not shortened — with the archive recognized, the stage has nothing
left to name.

`keep_core` is understated by the same cause (32 → 33).

### 2.3 Why the ≥3 floor was accepted, and why that is now overridden

The floor is a **recorded, deliberate decision**, not an oversight. The budget-ladder spec
carries it in its own words: the miss-detector's recall *"is bounded by `_is_archive_index`'s
≥3-link recognition … Undercount direction; SHIPPED.md-style archives exceed 3 links almost
immediately in practice. The shared classifier is NOT loosened (it guards the evict path —
blast radius)."*

Two independent reasons to overturn it:

1. **The stated justification is falsified by measurement.** The live archive sits at **2**
   links (536 bytes, two entries). "Exceed 3 links almost immediately in practice" is false
   for the store the product dogfoods, today.
2. **The recorded blast radius is incomplete.** The decision names one consequence — the
   miss-detector's recall, explicitly classified as *undercount direction*, i.e. safe. It does
   **not** name the drift-counter corruption (§2.1) or the triage docket (§2.2), which run the
   other way: they manufacture findings and recommend deletion. A recorded cost is only
   acceptable while its blast radius is accurate.

### 2.4 The fragility argument — the decisive one

The ≥3 floor makes archive-recognition a function of **how many entries the archive currently
holds**. So the guard inverts downward: an archive that *shrinks* — entries re-promoted,
facts GC'd, an arc closed — silently reclassifies as a fact and re-enters the eviction docket.

This is not hypothetical in this repo: `sync_global` carries a v0.1.76 audit fix whose comment
records the *same* file and the *same* misclassification at a larger size —
*"a live node's 7.6k-tok SHIPPED.md inflated `recall_tokens` + `facts`"*, repaired by routing
through the shared classifier. The **harm** was not the same then — it was recall-counter inflation,
not a deletion recommendation: one misclassification surfacing through two different consumers. That
repair worked while the archive was large. The archive has
since shrunk to 2 links, so the shared classifier now answers the opposite way and the v0.1.76
fix is **silently inert**.

A classifier whose verdict on one unchanged file flips when that file's *content shrinks* is
not a classifier. The count was never the right discriminator; **the absence of fact
frontmatter is**, and the link test only needs to establish that the file is a pointer list at
all.

## 3. Root cause B — the drift counter's schema set

Three frontmatter schemas legitimately live in a native store:

| schema | marker | author |
| --- | --- | --- |
| native auto-memory | `metadata.node_type` | Claude Code / the pass |
| mirror stamp | `metadata.global_ref` | `sync_global --pull` |
| **LocalFactV1** | `local_schema_version` | `cm local` / `local_ingress` |

`schema_drift` exempts the **mirror stamp** from its native-schema counters — the docstring
records the reason: a mirror's metadata block *"is the mirror-stamp block … never a drift
finding."* It does **not** exempt **LocalFactV1**, which is a *documented distinct contract*:
`local_ingress`'s module docstring says so in terms (*"LocalFactV1 is a distinct contract (not
canonical schema v3)"*), and its `LOCAL_RESERVED` tuple enumerates the reserved keys —
`node_type` and `originSessionId` are **not among them**, by construction.

So a legitimate LocalFactV1 fact is reported as schema drift. Measured: one file, contributing
`missing_node_type` and `advisory_no_origin`. With root cause A and B both fixed, the store's
`drift_findings` falls **6 → 1**, and the residual 1 is the one genuine finding.

The exemption is detectable by the contract's **own version marker**, exactly as `_is_mirror`
detects a mirror by its stamp — not by guessing at key shapes.

## 4. Changes

| Site | Change |
| --- | --- |
| `memory_status._is_archive_index_text` | The link test becomes a **presence** test (`≥1`) instead of a **threshold** (`≥3`). The frontmatter test is unchanged and still runs first — a fact is a fact because it carries frontmatter, so this arm is unreachable for any well-formed fact. Update the docstring to state the rule as a definition (a frontmatter-less file carrying a pointer is a pointer list) rather than as a tuned constant. |
| `memory_status.schema_drift` | Exempt **LocalFactV1** (frontmatter carrying `local_schema_version`) from the **native-schema** counters — `missing_node_type` and `advisory_no_origin`. Its presence is not drift; it is a different contract. Mirrors keep their existing exemption; `scope` is untouched (`LocalFactV1` requires it). |
| `docs/index-usage-and-budget-ladder.spec.md` | Correct the falsified justification (§2.3) and record the drift/triage consequences the original entry omitted. The decision text says the classifier *"is NOT loosened"*; it now is, and the entry must say so with the measurement that overrode it — a spec that keeps asserting a superseded decision is a defect of the same class as the code it describes. |
| `CHANGELOG.md` | Patch entry. A gate that newly fires (or newly stops firing wrongly) is user-visible. |

**Not changed, deliberately.** No change to `remediation_triage`'s stage logic, to
`placed_fact_names`, or to any consumer. All four corrections follow from the two predicates;
patching the counters individually would leave the misclassification intact at every other
consumer (`extract_signals`'s miss-detector, `sync_global`'s recall counters, the R-reference
set) — the weakest-enforcement-site rule.

## 5. Pins (each must fail on pre-fix code)

1. **Archive recognition at the boundary** — a fixture store whose archive doc has exactly
   **2** pointers is recognized as an archive: it is absent from `fact_files`, and its
   `stems` are absent from `missing_node_type`. Pre-fix this reports it as a fact.
2. **The docket** — `remediation_triage` on an over-budget fixture whose only archived facts
   live behind a 2-pointer archive returns them **not** in `A_orphans`. Pre-fix they appear
   there. This is the pin that encodes the harm rather than the count.
3. **Placement** — `placed_fact_names` unions a 2-pointer archive's targets, so
   `index_mismatch` is 0 for facts placed only in the archive. Pre-fix: 2.
4. **Shrink-invariance** — the same archive classified at 2 entries and at 20 entries returns
   the same verdict, asserted through `_is_archive_index` (the production path classifier, with
   its own 64-byte head read) and not only the text helper. This is the pin that forbids the
   class of defect from returning under a different constant.
5. **LocalFactV1** — a fact carrying `local_schema_version` and the `LOCAL_RESERVED` keys,
   with no `node_type`, contributes **0** to `missing_node_type`; an otherwise-identical file
   *without* `local_schema_version` still contributes 1. The pair is the discriminator: the
   second half is the control that proves the pin tests the marker and not merely "fewer
   findings."
6. **The link-less stray stays loud** — a frontmatter-less, link-less `.md` is still a fact
   and still reports `missing_node_type`. This is the §6 R2 boundary.
7. **The floor's own boundary** — a fixture archive carrying exactly **1** pointer is recognized,
   at both entry points. Pin 1 samples 2 pointers and pin 4 samples 2 and 20; **nothing sampled
   1**, which is the value the floor moved *to*, so an edit moving it to `≥2` would leave every
   check green while re-opening this cycle's whole defect class. Pre-fix this file is a fact.

On the pre-fix tree pins 1–4, 5's first half and 7 fail — **seven checks**, not six, because pin 1
is asserted twice (the archive is absent from `fact_files`, *and* its stems are absent from
`missing_node_type`). Pin 5's control and pin 6 hold on **both** revisions: controls, not pins.
Seven pins, two guards, nine checks.

## 6. Risks

- **R1 — a false archive classification hides a real fact.** The loosened arm absorbs a
  frontmatter-less file that carries a pointer. *Measured, not argued:* moving the floor from
  `≥3` to `≥1` changes the predicate's verdict on **five** files fleet-wide, not one — this
  store's `SHIPPED.md` (**2** links) and **four domain stores' `MEMORY.md`**
  (`domains/{docs,llm,personal,tools}/facts`, **1 link each**), which are facts under `≥3` and
  archives under `≥1`. Every other store-root file in the fleet already agreed: the one other
  archive doc (`Doc-Flo/memory/SHIPPED.md`, 63 links) sat above the old floor, and every project
  `MEMORY.md` measures 0 or ≥3 links. The change is still safe, but for a reason an earlier revision of this section
  got **wrong**: every store-root consumer **that reaches a decision** drops `MEMORY.md` **by name**
  before consulting the classifier — `memory_status.store_local_index` (the guard sits inside the
  glob comprehension), `extract_signals._tier_sets` (both branches: the snapshot label test, and the
  live-store file test), `sync_global`'s reserved-stem sites, and the further `stem != "MEMORY"`
  guards on `extract_signals`' read path and in `_mentionable`. No call site in the tree is
  name-free, so the four `MEMORY.md` reclassifications never reach a decision. Behaviour is stable because of those guards, **not** because `≥1` and `≥2` agree:
  at the predicate level they do not, on exactly those four files. One site carries no name
  guard — `extract_signals`' `archive_stems` comprehension — and it is inert for two
  independent reasons: no project store's `MEMORY.md` on this machine sits at 1–2 links (every
  one measures 0 or ≥3), and its only consumer re-excludes `MEMORY` by stem anyway. The
  direction also matters: the absorbed file must already have failed the frontmatter test, so
  the only thing that can be hidden is a file that is *already* malformed. Pin 6 keeps the
  link-less case reporting.
- **R2 — a store whose `MEMORY.md` carries no frontmatter and no links.** The loosened arm is a
  *presence* test, so a frontmatter-less, link-less `MEMORY.md` stays a fact; pin 6 is that
  boundary, and it is the whole of this risk. An earlier revision named a second instance that
  **does not exist**: that `extract_signals` calls the classifier on snapshot *content* "where
  no name is available". The name is available — `_tier_sets` tests `label == "memory/MEMORY.md"`
  in a branch **before** the classifier, and the labels are built from relative paths in
  `memory_status`, so `MEMORY.md` never reaches the classifier at that site. The real
  unguarded site is the `archive_stems` comprehension in R1. Corrected rather than deleted: a
  risk entry whose mechanism was never real is worse than no entry, because it reads as
  coverage.
- **R3 — the LocalFactV1 exemption could mask a genuine native fact that lost its frontmatter.**
  It cannot: the exemption keys on `local_schema_version`, which a native fact does not carry.
  A native fact missing `node_type` still reports. Pin 5's second half is this control.
- **R4 — retroactive archive display.** The archive's own drift panel re-renders with corrected
  numbers. This is the intended effect (the numbers were wrong), but it means an archived cycle
  displays differently after the fix. Recorded, not suppressed: the persisted log is
  append-only and is not rewritten; only freshly rendered views change.

## 7. Verification

```bash
python3 tests/smoke.py
python3 tests/simulate_accumulation.py
python3 tests/docs_links.py
python3 tests/validate_manifests.py
mypy --config-file mypy.ini
```

**Mutation-verify.** Each pin is re-run against the pre-fix tree and must fail there; the
counts belong to the triple (restored code, fixture, harness) and are re-derived on the fixed
revision, never carried. Measured on this revision's triple, one tree per process: pre-fix
**1945 passed, 7 failed** — the seven pins, with both guards green — against **1952 passed,
0 failed** on the fixed tree.

**Re-derive the live numbers, one tree per process.** Every figure in §2 is re-measured on the live
store across **three** trees — HEAD, the archive arm alone, and both arms — because the two root
causes move different fields and an intermediate value that is asserted rather than measured is not
evidence. Measured: `missing_node_type` 2 → 1 → **0** · `index_mismatch` 4 → 1 → **1** ·
`advisory_no_scope` 17 → 16 → **16** · `advisory_no_origin` 2 → 1 → **0** · `drift_findings`
6 → 2 → **1** · `keep_core` 32 → 33 → **33** · `archive_docs` `[]` → `['SHIPPED.md']` ·
`fact_files` 38 → 37 · Stage-A docket non-empty → **empty**.

**A scope warning that this spec earned the hard way.** The docket figures in an earlier revision of
§2.2 came from a hand-rebuilt counterfactual — the archive passed in explicitly — and were wrong in
both halves (four candidates falling to one, rather than two falling to none). The real
`remediation_triage` call gathers `reference_stems` from **three** update sites — archive link
targets, CLAUDE.md prose mentions, and D4 wikilinks between facts — and a reconstruction that
reproduces only the obvious one yields a different docket. (The index is *not* a fourth source: it
is a separate membership test inside `remediation_triage`, never an input to `reference_stems`.)
The numbers above come from `build_context`'s own context object, never a lookalike; and a probe
reading a key the context does not have (`ctx["health"]`, which is the *record's* grouping) returns
a silent zero, which is how a prior gets a measurement's shape.

An independent verifier, **having read this paragraph**, reproduced the error one level deeper: it
passed `ctx["index_names"]` where `schema_drift` actually receives
`placed_fact_names(index_path, archive_docs)`. On the fixed tree the wrong key yields an
`index_mismatch` of **3** against the true **1** — a plausible-looking number in the right range,
which is what makes this class hard to notice, and why the §2.1 mechanism was confirmed by the
*identity* of the names the archive arm removes (the archive itself plus its two link targets)
rather than by arithmetic alone.
