# The pointer's ROLE — and the merge lever's true shape

The store answers one question in five different places and gets a different answer in each:
*which facts does this document place?* The rule is currently "any `](stem.md)` anywhere in the
file's TEXT", which cannot tell a pointer from prose that quotes one. This document specifies the
fix, and reports on a second question the roadmap has carried open — the `merge?` detector — where
⚠ **the first conclusion was falsified in review and is now much narrower than "no".** §4 states
what survives and what does not; read it before quoting this document on that question.

Measured 2026-09-25/26 against the live store at `~/.claude/projects/<slug>/memory/` and the
tree at `f0b8767`, and re-measured after an adversarial review round (2026-09-26) that falsified two
of its claims.

**How to read the citations.** Every `file:line` below is **`f0b8767`-numbered**. Resolve it with
`git show f0b8767:<path>`; a coordinate that has moved since is a citation to re-derive, not to
correct here. A fact in the private memory store is named by stem and never given a path
coordinate — the store is not in this repository, so no revision can answer for it.

**STATUS (2026-09-26): the RULE and its reader convergence are IMPLEMENTED on
`fix/v0.4.68-pointer-role`, measured (§5), and have been through one adversarial review round — which
FALSIFIED two claims in this document (§3.2's boundary argument and §6's fleet measurement). Both are
corrected above, with the falsified forms kept visible. NOT implemented: §4's skill amendment, and
the named residuals in §6. Those are listed there rather than implied closed.**
Target release: **v0.4.68 (patch)**, on the corrected measurement (§6). ⚠ The operand is worth
stating precisely, because the first revision stated it as 3529 and the honest figure is far smaller:
**two stores in the fleet hold an archive-shaped document at all**, and exactly one of them changes.
"One of two" and "one of 3529" support the same bump, but only the first is what was measured, and a
denominator inflated 1764× is the kind of number that makes a small check look like a sweep.

## 1. The defect, measured

`memory_status.py:1396`

```python
_LINK_RE = re.compile(r"\]\(([^)]+)\.md\)")        # MEMORY.md pointer link target (stem)
```

One function, `index_fact_names`, is applied to two files with **different contracts**.
`MEMORY.md` is a pure pointer list — its only non-pointer line is the `# Memory Index` title.
`SHIPPED.md` is a 550-line archive *document*: a 17-line header and pointer block, `---` at line
18, then long recovery sections quoted from the roadmap. Exactly **three** of its 550 lines are
pointer-shaped: line 15 is a real pointer, and lines 322 and 550 are **quoted list items inside
narrative prose**. ⚠ Named *by line* and deliberately NOT as `file:line`: this is a store document,
it lives outside this repository, and no revision can answer for it — so a coordinate shaped like a
citation would be resolved like one, fail, and be right to fail. (An adversarial reviewer flagged
the bare form as unresolvable and this document briefly "fixed" it into the citation shape. The
gate refused it. The reviewer's remedy was the defect.)

Two harms. ⚠ **Only the first was ever LIVE**, and this document's first revision said "both
reproduced this week" — an overstatement one adversarial reviewer caught, and it is worth being
exact about because the two harms have very different standing:

- **H1 — quoted prose conferred archive membership.** Because of `:322` and `:550`,
  `distill-feature-plan` and `arc-a-qa-harness-teeth-evidence` read as ARCHIVED for months although
  no archive operation ever placed them. Measured: `index_fact_names(SHIPPED.md)` returns 3 stems,
  of which only one is above the divider.
- **H2 — an example in prose became a fact. ⚠ NOT a live harm.** A header note added to
  `SHIPPED.md` quoted the
  pointer shape literally as its illustration; `_LINK_RE` counted the illustration and the store
  reported a phantom fact named `stem` — `DANGLING: ['stem']`, `placed 92` against `91` bodies.
  It was caught the same day the note that caused it was written and never reached a reader as a
  wrong answer. It is recorded because it is the defect's cleanest demonstration — prose became a
  fact with no other rule involved — not because anyone was misled by it.

**This is not an unknown defect.** `docs/periphery-parity.spec.md:587` records it as *"§2.3's
residual: a doc whose link is formatted as a pointer line is structurally indistinguishable from a
real archive"*, and defers it explicitly for scope — *"the honest fix is a new report key …, and a
report-contract addition needs its own pin and its own arm re-derivation."* That note concedes the
gap it leaves: *"this risk is that the classification path has no such naming."* This document
closes the residual at its source instead of naming it downstream.

**Its blast radius is not cosmetic.** `extract_signals._tier_sets` (`extract_signals.py:725`,
`:731`, `:740`) uses the same whole-text scan to decide whether a fact is **indexed or archived** —
and that tier drives the demotion policy and the miss detector. A single quoted line in an archive
document can therefore change a fact's tier, which is the input to a retention decision.

## 2. Requirements

- **R1 — one derivation.** There is exactly one definition of "the pointer targets of an index
  document", and every reader calls it. This file's own history is the reason: the store has paid
  repeatedly for a rule with two spellings that drift.
- **R2 — role.** An anchor counts only when its **line is a pointer line** (a line whose stripped
  text begins `- [`). An anchor mentioned mid-prose does not count.
- **R3 — region.** In an **archive** document, the pointer set is those above the first **`---`**
  rule. ⚠ **The `---` rule ONLY.** A `## ` heading was a terminator here in this document's first
  revision, and it was a real regression against a live store — §3.2 is the corrected argument and
  §6 carries the measured cost, because this requirement list is what an implementer reads first and
  it still prescribed the clause the code had to drop. A document with **no** `---` is read WHOLE,
  which is fail-open: it reproduces the behaviour that preceded this rule, so no store can lose a
  placement it previously had. `MEMORY.md` has no `---`, so its whole file is its header region and
  it is unaffected.
- **R4 — convergence, scoped by the QUESTION a reader asks.** Every reader that answers *"which
  facts does this document place?"* uses R1's derivation, with no local re-spelling. ⚠ This is
  NARROWER than this requirement's first draft, which named every site that touched the anchor.
  Two of those sites ask a different question and must NOT converge; converging them would be the
  defect rather than the fix. §3.3 records which is which, and the trigger that would make the
  remaining inert sites live.
- **R5 — read/write agreement.** The read rule and the write rule are the same rule. Today the read
  side is stricter than the write side, which locates a pointer line by bare substring.
- **R6 — no pin regressions.** The multi-pointer-line pins at `tests/smoke.py:12546-12640` stay
  green — ⚠ **that range contains THREE of them, not five**; the other two sit outside it and were
  named as five by this document without being re-counted. A pointer line may legitimately carry a
  second anchor; see §3.4.

## 3. Design

### 3.1 R2 is not a new rule — it is a decision already made and pinned; R3 is the missing half

**R2 is already the canonical reader's behaviour, deliberately, and pinned.** The shared reader
(`index_admission.archive_index`, `f0b8767:84-86`) skips any line that does not begin
`- [` after stripping, and `tests/smoke.py:13612` (P10) asserts exactly that on a prose fixture:

```python
_prose_pr = ("# Working notes\n\n"
             "Read [the baseline](mention-fact.md) before tuning anything.\n")
check("v0.4.32 P10 … the shared rule calls the prose doc an archive, and the extraction the fix
       reads takes zero targets from it",
      ms._is_archive_index_text(_prose_pr) is True
      and ia.archive_index(_prose_pr)["targets"] == [])
```

So the role rule exists, is tested, and the classifier is deliberately **broader** than the
extractor. **On R2 the work is convergence, not invention** — bringing `index_fact_names`,
`extract_signals`' tier reader and the rest onto the derivation the canonical reader already uses.
That is a smaller and safer change than adding a rule, and it is restoring a decision rather than
making one.

**R3 is missing, and the canonical reader is where it bites.** Measured on the live store:

```
archive_index(SHIPPED.md)["targets"]  →  3 stems
  :15   ABOVE the `---` divider (line 18)  ← a real pointer
  :322  BELOW the divider                  ← a quoted list item
  :550  BELOW the divider                  ← a quoted list item
```

The two quoted lines are *leading anchors on list-item lines*, so **no role rule can exclude
them** — not the line-scoped reading, not the stricter anchor-scoped one. R2 fixes H2; only R3
fixes H1, and the reader conferring the bad membership is the canonical one every placement
question already flows through.

### 3.2 The boundary idiom was reused — and REUSING IT WAS THE DEFECT

⚠ **This section argued the opposite in the first revision, and it was wrong. It is kept in its
corrected form because the error is the most instructive thing in this document.**

The first revision had R3 terminate the region at "the first `---` **or** the first `## `, whichever
comes first", justified as reusing `tests/docs_links.py::_spec_header_end`'s existing derivation so
that the repo would have one boundary idiom rather than two. The reasoning appeals to a lesson this
repo has paid for twice — **a boundary is a property of the FIELD, not of the reader that happened
to observe the defect** — and it applied that lesson wrongly. *One idiom per field* is the rule.
Spec files and archive indexes are **different fields**:

- A **spec file**'s header is preamble prose, and `## ` terminates it because everything after the
  first section is body. That is `_spec_header_end`'s contract, and it is correct FOR SPECS.
- An **archive index**'s headings are **organizational**, and its pointers live **beneath** them.
  `## ` terminates nothing.

Importing the disjunct across that line was not reuse; it was the same defect with a new spelling,
and the field paid for it immediately — see §6's measured regression. **R3 now reads the `---` rule
and nothing else.** A document with no `---` is returned whole, which is fail-open: it reproduces
the behaviour that preceded the rule, so no store can lose a placement it previously had.

The `---` is the archive's own divider — the only marker that means *machine list above, prose
below* — and it is the only one the rule may read. ⚠ And note the corroboration that this repo's own
`SHIPPED.md` did **not** expose the bug: its `---` is at line 18 and its first `## ` at line 20, so
it survived on **marker ordering luck**. A rule validated only against the document that motivated
it inherits that document's accidents.

### 3.3 The one home, and the readers that converge on it

⚠ **Coordinates.** Anything introduced by this change (`pointer_region`, `pointer_lines`,
`pointer_targets`) has **no `f0b8767` coordinate** — it did not exist there — so this document names
those symbols and never gives them a revision-numbered line. A coordinate that resolves to a blank
line is worse than no coordinate, because it looks checkable.

The preferred home is `index_admission`, which already owns `archive_index` (`f0b8767:64`)
— the reader every placement question is currently answered through, and the one
`local_ingress._rebuild_plan` already consults (`f0b8767:916` reads its `targets` — ⚠ this
document first cited `:896-903`, which is a COMMENT block in the same function; an adversarial
review caught it, which is the argument for resolving a coordinate before trusting it,
deliberately not its `admitted`).

**Keep `_LINK_RE` raw; compose, do not edit.** The anchor regex should stay a plain anchor matcher,
and the new derivation composes it with the role and region rules. Editing the regex would change
every consumer at once — including the ones that legitimately want any anchor — where composing
changes only the callers that mean "a pointer". This also keeps R5 honest: `apply_pointer`
(`index_admission.py:112-131`) currently locates the line to replace by bare substring with no shape
test, so **it must become role- and region-aware too**, or the read side will silently be the
stricter of the two and a write can place a pointer the reader will not see.

**Every site that touches the anchor, sorted by the question it asks — which is what decides
whether it converges.** The first draft of this table sorted by module and called them all
"readers that must converge". Measuring what each one is FOR split the list in two, and the
second half is not unfinished work — it is work that must not be done.

| site | the question it asks | verdict |
|---|---|---|
| `index_admission.archive_index` (`f0b8767:64`) | what does this doc place? | **converged** — is the rule's home |
| `memory_status.index_fact_names` (`f0b8767:1521` def; `:1528` the `_LINK_RE` use) | what does this doc place? | **converged** — delegates |
| `extract_signals._tier_sets` (`f0b8767:705` def; `:725`, `:731`, `:740`) | what does this doc place? | **converged** — measured inert, §6 |
| `index_admission.apply_pointer` (`f0b8767:111`) | where is the line to REPLACE? | **converged** — R5, below |
| `local_ingress._stored_pointer` (`f0b8767:68` def; `:78` the shape test) | where is the pointer LINE for this stem? | **residual** — inert |
| `local_ingress` `existing_ptrs` (`:653`, `:842`) | is this stem currently in MEMORY.md? | **residual** — inert, lockstep pair |
| `local_ingress` (`:1116`, `:1123`) | which lines carry the carried stems? | **residual** — inert |
| `sync_global.py` `:2374`, `:3816`; `session_beacon.py` `:298` | verbatim anchor copies | **residual** — inert |
| `memory_status._is_archive_index_text` (`f0b8767:1716` def; `:1736` the `_LINK_RE` use) | **is this doc an archive?** | **must NOT converge** |
| `build_context`'s `ref_stems` local (`f0b8767:3707`; the enclosing `def build_context` is `:3525`) | **is this fact reachable ANYWHERE?** | **must NOT converge** |

⚠ **The two "must NOT converge" rows are the finding, and both were on the first draft's
converge list.** They are not the placement question and their breadth is load-bearing:

- `_is_archive_index_text` is a **classifier**, and `tests/smoke.py` P10 pins it as deliberately
  BROADER than the extractor — it answers `True` for a doc from which `archive_index` takes zero
  targets. Converging it would red that pin and destroy the asymmetry the pin exists to record.
- `ref_stems` collects anchors from archive docs and CLAUDE.md prose so that *"a fact reachable
  there is NOT mis-flagged as a safe-evict orphan"*. Its own comment states the direction: it is
  a **protection**. Narrowing it does not make a reader more precise — it unprotects facts from
  eviction, moving them toward being pruned. A rule that is correct for placement is wrong here,
  and the difference is which way the error costs.

**The residuals are INERT, and the trigger that would wake them is one line.** Every one reads
`MEMORY.md` — a pure pointer list with no `---` and no `## ` — so `pointer_region` returns it whole
and its lines already pass the role test. R2/R3 are therefore **no-ops at those sites today**.
They stop being no-ops the moment `MEMORY.md` gains a divider or a prose line, which is exactly the
event this spec exists to make survivable: a future reader should not have to rediscover which
sites were converged and which were left. ⚠ Leaving them is a deliberate scope call, not an
oversight — each is a behavior-identical edit that would still have to be pinned, and a pin for a
no-op cannot be a PIN.

**The role-check precedents, re-measured.** `archive_index` uses `strip().startswith("- [")` and
`_stored_pointer` uses `lstrip().startswith("- [")`, differing only on indentation tolerance;
the write-side constructors emit at column 0. Those two are now the SAME rule where it matters
(`pointer_lines` strips), and `_stored_pointer`'s stricter `lstrip` remains as one of the named
residuals. `apply_pointer`'s substring match with **no shape test at all** — the fourth precedent,
and the one with a live failure mode — is closed by R5 below.

### 3.4 The reading that was rejected

Two readings were on the table: **(A) line-scoped** (every anchor on a pointer line counts) and
**(B) anchor-scoped** (only the leading anchor counts). **(B) is tidier and is rejected**: it reds
five existing pins, and those pins encode a real decision — a pointer line may legitimately carry a
second anchor. Adopting (B) would be changing a behaviour to satisfy a preference.

### 3.6 R5 — the write side, and why a stricter reader is a data-loss shape

`apply_pointer` located the line to replace by bare substring — `f"]({stem}.md)" in ln` — with no
shape test and no region. The read side was therefore stricter than the write side, and the
failure mode is not symmetric with the one in §1: a write could rewrite a line its own reader does
not count as a pointer (a prose mention), report success, and leave the fact **unplaced**.

`admit_write` cannot catch that. It measures the index's **size**, and the write it just made is
size-neutral — it replaced one line with one line. So the defect is invisible to the very check
guarding the write path, which is what makes it worth its own requirement rather than a footnote
to R1.

Both halves now ask `pointer_lines`. The fallback inserts at the **end of the region**, not the end
of the file: below a divider the reader is blind, and writing where your own reader cannot look is
the same defect one layer down. For a pure pointer list (`MEMORY.md`) the region is the whole file,
so this is **byte-identical** to the old append — which is why it required no pin of its own, and
the five `tests/smoke.py` multi-pointer-line pins are the evidence it changed nothing they assert.

### 3.5 The rebuild coupling, stated precisely

`_rebuild_plan` reads membership through the shared `archive_index` reader, so R1/R3 reach it for
free. What remains name-based is the **fact glob** (`f0b8767:922` — cited as `:918` in this
document's first revision, four lines off),
`if f.name in ("MEMORY.md", "SHIPPED.md") … continue`) — a different site answering a different
question ("is this file a fact?" not "what does this archive place?"). It is **named here and not
silently widened**; a new archive document added under a different name would be globbed as a fact,
and that is a separate, pre-existing residual.

## 4. The merge lever — a measurement that says NO, and what replaces it

The roadmap has carried an open item for weeks: the always-loaded index is **90 pointers / ≈4614 est
tok against a 3840 hard ceiling**, `sync_global --pull` M1-holds all new globals until it shrinks,
and the conclusion on record is that **fewer pointers is the only lever** — because the index cue is
**cap-bounded**, so compressing hooks cannot relieve it. ⚠ **That claim's evidence is WITHDRAWN.** An
earlier revision of this paragraph carried a measured series as its support — 623 chars → 50 tok;
377 → 56; 170 → 58 — and two independent adversarial reviewers could not reproduce it under either
in-tree renderer, one of them further noting that its SIGN (a shorter cue costing MORE tokens) is
forbidden outright by `est_tokens`' monotonicity. The qualitative claim is retained because it is
independently supported by the ceiling arithmetic in the same paragraph; the numbers are gone
because they were asserted, not re-derived.

The obvious next step was a `merge?` Phase-0 detector. **It was probed before being built, and it
has no signal.** Three independent signals, over the live store's 86 indexed non-mirror facts:

| signal | measurement | verdict |
|---|---|---|
| **description similarity** — the store's own `_DEMOTION_SIMILAR = 0.6`, `SequenceMatcher(autojunk=False)`, canonical arg order | across all **3,655** pairs the **maximum is 0.432**; median 0.205, mean 0.206. At 0.45 and 0.50: **zero pairs** | the threshold is never reached |
| **name prefix** | one group (`a-check-*`, 3 members) with **0 of 3** wikilinks between them, stating three unrelated claims. The roadmap's flagship pin/observable cluster does not appear — it splits across `a-pin` / `a-pins` | one specious group |
| **wikilink overlap** (Jaccard) | 38 pairs at ≥0.5 — driven by **hub co-citation**: `exact-assertion-beats-verdict-scan ~ mutation-count-belongs-to-the-triple` scores 0.83 on five shared links that are all hubs, and the top pair reaches **J = 1.00 from a single shared link** | measures shared references, not shared claims |

**The failure is structural, not incidental.** The facts' `description:` fields are engineered as
**distinct recall keys** — the store's core discipline — so text similarity is lowest exactly where
the store is best written. The citation graph is hub-dominated, so overlap is co-citation. And the
ratio does not track meaning where it does fire: at 0.40 it pairs `gate-coverage-is-its-match-set`
with `weakest-enforcement-site-wins`, which are unrelated claims sharing vocabulary.

**Conclusion — NARROWED, because the broad form was falsified in review.**

⚠ **This section first concluded that "the merge lever is a JUDGMENT lever, not a detection lever"
and that making it mechanical "would require semantic embeddings". Both are WITHDRAWN.** An
adversarial reviewer attacked the negative result by trying metrics the probe did not try, and found
one that works: **a stdlib token TF-IDF ranks the store's one verifiable duplicate #1 of 3655**,
where the probe's `SequenceMatcher` ranks it 2981st. Token TF-IDF is stdlib-only, so it is *not*
excluded by the zero-dependency rule — the sentence that closed the question invoked the very rule
that permits the answer. The same reviewer also failed to reproduce the probe's token figures under
one instrument (4367 by `len//4` where the ceiling is denominated in `est_tokens`, the same lines
being 4620) — a mixed-unit comparison, not a tuned one.

**What survives, and it is much smaller:** *these three signals, as specified — description
similarity at `_DEMOTION_SIMILAR`, name prefix, raw wikilink Jaccard — do not recover the roadmap's
pin/observable cluster.* That is a statement about three metrics, not about the existence of a
signal. ⚠ And even that is weaker than it reads: the roadmap names its cluster ("8 pointers (~400
tok)") but **never enumerates its members**, so "the cluster does not appear" is a claim about a set
nobody has written down. The reviewer reconstructed 8 facts / 419 est tok that satisfies the stated
size — the figure corroborates, the membership is unrecorded, and §4's original sentence therefore
rested on an operand it could not check.

**So the detector question is RE-OPENED, not settled.** A `merge?` detector is still **not built in
this release** — but as a scope decision, not on the evidence that one is impossible. The honest
statement of where this leaves the lever is: *three cheap signals were tried and failed; one cheap
signal (token TF-IDF) was found by a reviewer to have real recall; and the cluster that would
validate any of them has never been enumerated.* Whoever picks this up should enumerate the roadmap's
8 members FIRST — that is the ground truth every metric must be scored against, and without it each
candidate metric can only be argued about.

**What ships in its place, for now.** A `merge?` detector is **not built in v0.4.68**. Instead
`SKILL.md` is amended so that a pass which finds itself over the ceiling is **instructed to read the
index and propose merge clusters itself**, at the moment the judgment is needed. The current text
implies this and never says it; the lever has been named for weeks with nothing pointing at it.

⚠ **This amendment is now an INTERIM measure, not the destination §4 first claimed.** It was written
as the permanent replacement for a detector that was said to be impossible; on the corrected
evidence a detector is not ruled out. The amendment remains correct for this release — a human/model
judgment pass over the ceiling is strictly better than nothing, and it does not depend on any of the
falsified claims — but it should not be read as the answer. The answer is: enumerate the cluster,
then score metrics against it.

## 5. Evidence and provenance

- **The three-point measurement, and why there are three.** The four new checks were run on THREE
  trees, not two, because a correction landed between them and one check is defined against the
  revision that was corrected. Full copies, same `tests/smoke.py` bytes on every tree (sha256
  compared), markers verified at 0 before each run:

  | tree | result | R2 | R3 | R3b | R4 |
  |---|---|---|---|---|---|
  | `f0b8767` — pre-fix | **2372 passed, 2 failed** | ✗ | ✗ | ✓ | ✓ |
  | `81a197b` — the INTERMEDIATE | **2373 passed, 1 failed** | ✓ | ✓ | ✗ | ✓ |
  | working tree — post-fix | **2374 passed, 0 failed** | ✓ | ✓ | ✓ | ✓ |

  R2 and R3 are PINs against `f0b8767`. **R3b is a PIN against the INTERMEDIATE and a CONTROL
  against `f0b8767`** — green there because no region rule existed at all — the same shape
  `tests/smoke.py`'s v0.4.32 P8 uses. R4 is a CONTROL on all three. D6 (the self-counting pin)
  holds on all three, since the check COUNT is identical and only outcomes differ.
  ⚠ One tree had to be rebuilt mid-review: `git checkout -- <paths>` restores from the **INDEX**,
  so on a branch where the fix is already committed it restores the FIX, not the pre-fix code —
  and the run looks entirely plausible. The marker check is what caught it (7/5/4 occurrences where
  0 was required), which is the recorded `a-failed-checkout-compares-one-tree-to-itself` failure.
- The defect and the two harms: **measured** on the live store 2026-09-25/26 (`index_fact_names`,
  `placed_fact_names`, a `_LINK_RE` count over `SHIPPED.md`).
- The recorded residual: `docs/periphery-parity.spec.md:254`, `:479`, `:587`.
- The reader inventory and the four disagreeing precedents: a completed exploration of the tree at
  `f0b8767`, reporting file:line for every site named in §3.3.
- ⚠ **The merge NO-GO is independently corroborated.** A separate design pass ran its own probe and
  reached the same verdict without seeing this one's numbers: *"0 pairs at 0.6, noise below — NO-GO,
  don't build."* Two independent measurements agreeing is the strongest evidence in this document,
  and it is the reason §4 is a decision rather than a preference. Note the agreement covers the
  **description-similarity** signal; the prefix and link-overlap probes are this document's alone.
- The merge probe: three read-only scripts run over the live store, reusing the store's own
  primitives and constants (`_frontmatter`, `extract_wikilinks`, `resolve_wikilink`, `_is_mirror`,
  `_DEMOTION_SIMILAR`, `INDEX_CEILING_TOKENS`). The probe re-implements the *population walk*, and
  ⚠ **the reason this document gave for that was imprecise** — corrected here. It said the real
  `demotion_candidates` "caps its output to `_DEMOTION_BOTTOM_K` surfaced rows"; the cap bounds the
  *returned rows*, not the *population*. Measured: `eligible = 49`, `surfaced = 5`. The probe's own
  population is the **86 indexed non-mirror facts**, which no cap touches — so the walk is
  re-implemented because a merge detector must see the whole indexed population rather than the
  capped triage rows, not because the population is hidden. The reviewer confirmed the population is
  **right and revision-independent**; only the stated reason was wrong. The metric and thresholds
  themselves are reused.

## 6. Honest limits and open items

- ⚠ **Fleet blast radius — the claim as first written was FALSE, and an adversarial review falsified
  it. The corrected measurement is below; what it originally said is kept because the miss is the
  evidence.** It claimed *"3529 stores scanned, exactly ONE archive changes."* Two things were wrong.
  **(1) The denominator.** 3529 counted DIRECTORIES: of 3553 store dirs, **3524 hold zero `*.md`
  files** — empty dirs left by every session and fixture that ever ran. The effective fleet is **29
  populated dirs holding 619 documents**, of which **28 are archives**, and the number is not even
  stable while you scan it (concurrent sessions create dirs; it read 3541, 3547, 3553 minutes apart).
  The inflated figure carried the rhetorical weight of *"measured across the fleet, not assumed"*.
  **(2) The scan modelled ONE of R3's two boundary disjuncts.** It tested the `---` rule only, so it
  could not see the class that the `## ` rule broke — and the two classes have the same size. It
  missed a second store's `SHIPPED.md` (named here by shape and not by slug, which is a machine
  identity and not this repo's to publish), a store whose
  archive is `# Title` + preamble + `## <date>` sections with **63 pointer lines underneath and no
  `---` at all**: the `## ` clause sliced its region to the six-line preamble, took **57 archived
  placements to 0**, and drove its drift count **4 → 61** — the §2.3 residual reopened, in the
  direction *away* from the truth.
  **Corrected measurement (independent scan, instrument imported from the artifact, set-to-set,
  `_LINK_RE` extracted from the `f0b8767` blob rather than retyped):** with the `## ` clause removed,
  **4 documents change and exactly ONE of them is an archive** — this repo's own `SHIPPED.md`,
  losing exactly the two stems already restored by hand. The other **three are FACT documents**
  (`co_residence_modes_2026_05_27.md`, `consolidate-memory-roadmap.md`,
  `verify-deltas-against-committed-shas.md`), which is the same set §6's "wrong operand" note already
  records: they carry no archive frontmatter, `_is_archive_index` rejects them, and **no reader scans
  them**. **Stores whose indexed/archived tier pair changes: 0.**
  ⚠ The claim is therefore TRUE for the shipped rule — but it was written for a rule that was not
  shipped, and it was true of *that* rule only by not looking. A measurement that agrees with the
  conclusion it was gathered to support deserves the scepticism it got.
- **The version bump — patch, settled on that evidence.** `CLAUDE.md`'s policy asks whether an
  existing install BREAKS. No schema, CLI, or manifest surface moves; legacy cycle records still
  render; the one store whose answer changes changes it toward the truth. The earlier note calling
  this "arguably a minor" rested on the change being fleet-wide — the fleet scan is what settles it,
  and it settles it the other way.
- **`DOCS` in `tests/docs_links.py` — done.** This document is listed there (invariant 2), and the
  gate's own count is the evidence rather than this sentence: link-checked files moved **19 → 20**.
- **The tier reader — measured, and it is INERT on the live store.** §1 claims a quoted line *can*
  change a fact's tier, and that capability is real — but the live effect was measured rather than
  inferred: `_tier_sets(store, None)` returns **indexed 90 → 90, archived 1 → 1, zero lost, zero
  gained** on both trees. The reason is worth recording, because it is not luck: the two quoted
  stems had already been restored to `MEMORY.md` by hand, and the tier sets subtract `indexed`
  (`arch - indexed`), so `indexed` wins whether or not the archive is read correctly. ⚠ So this
  convergence prevents the class recurring; it does **not** repair a live misclassification, and a
  summary claiming it does would be overreading a no-op.
- **A wrong operand worth recording so nobody chases it.** A live scan finds **4 anchors that are
  mid-line rather than line-start** — and all four are in **fact bodies**, not index files:
  the store facts `consolidate-memory-roadmap` (two of them) and
  `verify-deltas-against-committed-shas` (two, the last quoting `](evil.md)` as the very threat it
  documents). ⚠ They are named by FACT, not by `file:line`: the store lives outside the repository,
  so a path coordinate for it resolves against no revision in the tree and the citation gate is
  right to refuse it. They are **inert**:
  `_is_archive_index` rejects anything carrying fact frontmatter, so no reader scans them. R2 changes
  nothing for them. They are named here because a naive "find the offenders" scan reports them as
  evidence of the defect, and they are not.
- **Two adjacent disagreements found while exploring, out of scope but unrecorded elsewhere.**
  (1) `_KEEP_RE`'s comment (`memory_status.py:1650`) says it is *"scanned over the WHOLE body"* while
  both call sites scan **narrower** haystacks — frontmatter at `:1928`, description-only at `:2908`.
  Comment and code disagree, and that is current behaviour. (2) `defrag_candidates` deliberately does
  **not** consult `_KEEP_RE` at all — its quieting mechanism is the v0.4.23 watermark — so the two
  list-family detectors answer "is this candidate real?" by different rules. Neither is touched by
  this spec; both want their own decision.
- **No longer open — the three verbatim copies were read.** An earlier draft of this list carried
  them as unverified. They are `sync_global.py:2374`, `sync_global.py:3816` and
  `session_beacon.py:298`, and all three read **`MEMORY.md`** — a pure pointer list with no divider
  and no prose — so R2 and R3 are no-ops for them today. That is why they sit in §3.3's residual
  rows rather than its converged ones; the reason is a measurement, not a deferral.
- ⚠ **A limitation the review added: 10 of 91 descriptions repeat within themselves.** The
  description-similarity probe compares `description:` fields pairwise, and a field that restates its
  own wording carries similarity a reader would not call a merge signal. This does not rescue the
  metric — the measured maximum (0.432) is far below the threshold either way — but it is part of why
  that metric is the wrong *instrument* for this question rather than merely badly tuned, and it was
  found by measuring the operand rather than by reasoning about it.
- **The evaluation is a snapshot.** The probe's figures belong to the store at 86 indexed facts on
  2026-09-26 and to the revision they were measured on. A later pass must re-measure rather than
  carry them.
