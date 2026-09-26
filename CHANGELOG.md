# Changelog

All notable changes to **consolidate-memory** are documented here. This project
follows [Semantic Versioning](https://semver.org/) (pre-1.0: minor versions may make
breaking changes). Installed plugins auto-update at Claude Code startup when this
version changes on `main`.

## [0.4.70] — 2026-09-26

**Patch — R5's sibling, in two writers.** The security review of v0.4.68 closed with a LOW it had
not been asked for and that v0.4.68 did not touch: while `apply_pointer` was being fixed to stop it
rewriting a line its own reader does not count as a pointer, **the two writers that DELETE a
pointer kept the bare-substring form**. `local_forget` and `local_archive` each dropped ANY line
containing `](stem.md)` — so a prose line that merely *quotes* the pointer shape was deleted from
the always-loaded index by an ordinary archive or forget. MEASURED on the review's fixture: **two
lines removed where one was intended.**

⚠ The reason this is a release and not a nit is the shape, not the size. R5's own claim is that
**the read rule and the write rule are the same rule** — and in v0.4.69 that was true of one writer
and false of two, which is the weakest-enforcement-site pattern this store keeps paying for. The
repair is therefore **one helper both writers call** (`_drop_pointer_lines`), not two edits: two
copies of a rule is exactly how a second spelling gets acquired. Scope is the reader's own
`pointer_lines`, so a line the reader cannot see as a placement is never deleted for being one.

⚠ **Found by a review that was pointed at a different question**, and named in the same report that
found the quadratic: the LOW was recorded as "pre-existing, not in the diff". It is the class the
release it was reported against was *about*, one writer over.

Measured, same harness bytes, markers verified at 0:
```
pre-fix  (local_ingress at v0.4.69) : 2375 passed, 1 failed   — R8, exactly
post-fix (v0.4.70)                 : 2376 passed, 0 failed
```
`R8` is a PIN — red pre-fix, green post-fix. Design of record: `security/findings-2026-09-25-v0468-review.md`
(local, gitignored).

## [0.4.69] — 2026-09-26

**Patch — a quadratic the release made fixable, and the enumeration §4 was waiting on.** Three
follow-ups to v0.4.68, all found by adversarial passes run against it.

**A security review found the pointer scan is QUADRATIC on an unterminated `](` run** — the regex
`\]\(([^)]+)\)` sweeps to end-of-line and backtracks one character per start position. MEASURED:
3.4–4.9× per doubling, extrapolating to **~38 minutes** of uninterruptible CPU for a 1 MiB document
(`ARCHIVE_INDEX_CAP_BYTES`), on a path with no timeout, reached from every store `*.md` classified as
an archive. ⚠ **v0.4.68 did not introduce it and in fact NARROWED it** — the role filter skips the
regex on non-pointer lines, and the old whole-text scan had a wider input set. What v0.4.68 did was
give the rule **one home**, which is exactly where a single guard closes the class at every reader.

Fixed by making the scan **linear** rather than by capping length: a cap would make an archive over it
place **NOTHING**, and a placement is load-bearing — its facts would report UNPLACED and the rebuild
would re-add their pointers. The blowup is an artefact of backtracking, not of the language. Measured
after: equivalence **IDENTICAL** to the retired regex over **7,274 live store lines** and 14
adversarial shapes; on the reported input, **0.000010s against the regex's 7.54s**. The now-dead regex
is deleted, and a REGRESSION GUARD (R7) holds the line with an absolute 0.1s bar that separates by
~750,000× — it cannot redden pre-fix, since the symbol is new, so it is labelled a guard and not a pin.

**The enumeration §4 left open was then produced, and it is sharper than expected.** The roadmap's
"8 pointers (~400 tok)" cluster cannot be enumerated — a size and a token figure, **zero membership,
anywhere**. ⚠ Worse: the figure is **non-identifying**. In a store whose pointers average ~50 est tok,
"8 pointers (~400 tok)" is what *any* size-8 draw costs — **93.15 % of all 8-subsets fall in
[360, 440] tok**. It could not have failed to match, so it corroborated nothing. Relief is real
(~360–402 est tok, 47–52 % of the 774-tok overage); no cheap metric recovers the cluster **as a set**
(best F1 0.182). ⚠ **But `body_tfidf` decisively separates a true DUPLICATE from it** — the store's one
verifiable duplicate ranks **#1 of 3655 at 0.4931** against the cluster's 28 intra-pairs topping out at
**0.2942**, a 1.68× gap. That is a threshold that CAN fail, which is what §4 lacked. The detector is
therefore buildable **as a duplicate finder, not a cluster finder**; it is still not built.

**And the v0.4.68 spec's own STATUS was stale** — it said the skill amendment was NOT implemented
while #275 had shipped it. A released document asserting a shipped thing is unshipped is the class the
spec-status gate exists to catch one level down: the gate reads whether a spec declares a LIVE status,
not whether the declaration is still true. Now states SHIPPED, and names what remains open.

⚠ Two open items are RECORDED rather than closed, in `security/` (local, gitignored):
`findings-2026-09-25.md` re-triages dream-beta-tester's 3 confirmed pentest findings from 2026-07-06
and finds **all three still open** (2 High, 1 Medium, each reproduced live) — unfixed deliberately,
because `maintainer/ci_check.sh` does not exercise `snapshot.py`/`beta_checks.py`, so a fix there needs
its own regression arm and its own cycle.

## [0.4.68] — 2026-09-25

**Patch — the pointer's ROLE and REGION, and a fleet blast radius measured at one store.** No
cycle-record, CLI or manifest surface moves; legacy records still render. The store answered *"which
facts does this document place?"* with `_LINK_RE`, a bare `](stem.md)` match over a file's whole
TEXT, which cannot tell a pointer from prose that quotes one.

⚠ **THE FIRST CUT WAS WRONG AND ITS OWN ADVERSARIAL REVIEW FALSIFIED IT.** R3 terminated the region
at "the first `---` **or** the first `## `, whichever comes first", justified as reusing
`docs_links._spec_header_end`'s idiom so the repo would carry one boundary idiom rather than two. The
reasoning cites a lesson this repo has paid for twice — *a boundary is a property of the FIELD* — and
applied it backwards: one idiom **per field** is the rule. A spec's header is preamble prose where
`## ` terminates it; an archive's headings are **organizational** and its pointers live **beneath**
them. The fleet scan that "confirmed" the change had modelled **one of the rule's two disjuncts**, so
it could not see the class the other one broke — a second store's archive is `# Title` + preamble +
`## <date>` sections with 63 pointer lines underneath and no `---` at all, and the clause took its
**57 archived placements to 0** and drove its drift count **4 → 61**. This repo's own `SHIPPED.md`
never exposed it (`---` at 18, first `## ` at 20): it survived on **marker ordering luck**. Removed.
A document with no `---` is read WHOLE — fail-open, so no store can lose a placement it had.

Two further review findings corrected the design rather than the code. **Two readers the plan listed
as "must converge" must NOT**: `_is_archive_index_text` is a classifier whose breadth P10 pins, and
`ref_stems` asks *"is this fact reachable anywhere?"* — narrowing it would **unprotect** facts from
eviction. A rule correct for placement is wrong there, and the difference is which way the error
costs. And **§4's merge NO-GO is narrowed**: it concluded "no signal" and "would require embeddings",
but a stdlib token TF-IDF ranks the store's one verifiable duplicate **#1 of 3655** where the probe's
metric ranks it 2981st — stdlib-only, so not excluded by the very zero-dependency rule the old
sentence invoked to close the question. The detector question is re-opened; the `SKILL.md` amendment
ships as an **interim** measure, not a destination.

Also withdrawn: §4's cap-bounded cue series (623→50, 377→56, 170→58). Two reviewers could not
reproduce it under either in-tree renderer, and its SIGN — a shorter cue costing more tokens — is
forbidden by `est_tokens`' monotonicity. And the fleet denominator: `3529 stores` counted
**directories**, of which 3524 hold zero `.md` files; the effective fleet is 29 populated dirs / 619
documents / 28 archives, and **two stores hold an archive-shaped document at all**. One of two, not
one of 3529 — the same bump, but only the first is what was measured.

Corrected in the tree: `index_admission` gains `pointer_region` / `pointer_lines` / `pointer_targets`
(one home per half of the rule); `archive_index` and `index_fact_names` derive from them;
`extract_signals._tier_sets` converges (⚠ measured INERT on the live store — indexed 90→90, archived
1→1 — because the two quoted stems were already restored by hand and the tier sets subtract
`indexed`; it prevents the class recurring and does not repair a live misclassification);
`apply_pointer` gains R5 — it matched by bare substring, so a write could rewrite a line its own
reader does not count as a pointer, report success, and leave the fact unplaced, invisible to
`admit_write` because it measures SIZE and the write is size-neutral.

Measured on three trees, same harness bytes, markers verified at 0 — R3b is a PIN against the
INTERMEDIATE revision and a CONTROL against `f0b8767`:

```
f0b8767  pre-fix       2372 passed,  2 failed    R2 x  R3 x  R3b ok  R4 ok
81a197b  intermediate  2373 passed,  1 failed    R2 ok R3 ok R3b x   R4 ok
b1e7fec  post-fix      2374 passed,  0 failed
```

⚠ The genericity pin did NOT catch a bare project name in a code comment — its matcher covers
`/home/<name>` and `-home-<name>-` forms. Removed by hand: a gate proves only what its matcher can
see. Design of record: `docs/pointer-role-and-merge-lever.spec.md`.

## [0.4.67] — 2026-09-25

**Patch — three behaviours mutation testing found unwitnessed.** Each mutation left the suite at
**2365 / 0** before these arms existed, so each could be reverted with CI green.

Two things fell out that matter more than the arms:

- ⚠ **One of the reported gaps is not a gap.** "Deleting the cap term from the `min`" is an
  **EQUIVALENT mutation**: `_note` comes from `range(min(_hd, _n))` with default `_n`, so `_note <= _n`
  always and `min(_hd, _note)` agrees with `min(_hd, _note, _n)` on **0 of 58** specs. It is green by
  **equivalence**, not by gap — and a report that conflates the two asks for an arm that cannot exist.
  Only the cap that **binds** (120 → 10⁹) is asserted.
- ⚠ **My first mutation harness was void and read as a result.** I copied the trees without `.git`,
  so three `.git`-dependent citation pins failed **identically for all six mutations** — one number
  for six different inputs. Caught by that sameness. The pins' own text calls it a fault, not a
  verdict. Redone with `.git` preserved; the redo parses each mutated source before trusting it.

**Added — three GUARDs** (green on both trees; their only witness is the mutation they name):

| arm | mutation it catches | measured |
|---|---|---|
| **O7** | the status **window** unbound to the bare cap — only the target scan's use of the region was witnessed | `_win = lines[:CAP]` → **O7 reds** |
| **O8** | the **cap** 120 → 10⁹ (must not examine a declaration past line 120) | **O8 reds** |
| **O9** | re-adding `and not spec_done(stated)` — **the exact defect v0.4.63 closed**, where a done-token exempted a header stating "implemented and REVIEWED … awaiting merge" | **O9 reds** |

⚠ **Still open, and it is the harder half:** two further mutations resist a fixture designed so far —
**M2** (the note term off by one, `k` → `k+1`) and **M4** (the two-arm `elif` → `if`). Both concern the
boundary's *side* and the arms' *relationship* rather than either arm's matching, and neither is
witnessed. Named here, not implied.

Measured: `tests/smoke.py` **2368 / 0** · `docs_links` **52** · `mypy` 0 in 42.

### The comment density cut (folded in — never a separate release)

⚠ **Why folded:** the version bump was mine, not a user-visible change. This work is comments
in `tests/`, which the plugin never runs, so tagging it separately would ship a release that
does nothing. Folded rather than tagged — and the folded release is numbered **0.4.67**, the
next clean step from `v0.4.66`, because the number I first gave it (0.4.67) skipped one.

**Patch — the comment density cut.** No behaviour change: smoke stays **2365 / 0** and `docs_links`
stays **52**, measured identical rather than assumed.

⚠ **The framing matters, because the obvious one is wrong.** *"An earlier draft said X"* is this
repo's **house idiom** for recording why a check is shaped as it is — a dozen pre-existing sites use
it, and they are not the problem. What was wrong was **density**: the v0.4.61–66 blocks carried a
self-correction on nearly every sentence, where the house form is reserved for decisions worth
keeping. The worst offenders were a **53-line docstring over a 5-line body** (now 22) and a
**12-line tombstone for a deleted check** (now 3).

**Removed:** ~46 lines of narration the CHANGELOG already carries — the blow-by-blow of how each
correction was arrived at, and every "an earlier version of this line said…" whose fact is already
stated in the release notes.

**Kept:** every measured figure, every PIN / CONTROL / GUARD label, the invariant each helper
enforces, and every correction the CHANGELOG does **not** already carry.

⚠ **Not finished.** Nine sites still carry the dense form, mostly in shipped check **labels** where
the string is output rather than commentary. Recorded, not implied.

Measured: `tests/smoke.py` **2365 / 0** · `docs_links` **52**, 0 errors · `mypy` 0 in 42.

## [0.4.66] — 2026-09-25

**Patch — the boundary anchored on a phrase the sweep itself writes into the live header.**

Found by following v0.4.65's own recommendation to check whether `_SPEC_PROVENANCE_QUOTE` really is
consulted in one place. It is not — and the audit turned up a live defect on the way.

- ⚠ **The provenance boundary matched the phrase, not the quote.** The sweep this boundary exists to
  fence off writes its own **correction sentence into the live header** — *"⚠ The drafting-era status
  survived because no gate re-read it"* — so `_spec_header_end` cut the region at the sweep's own
  feedback rather than at the preserved blockquote. MEASURED on the corpus: **four** specs
  (`body-defragmentation`, `completion-driven-archiving`, `cross-domain-index-refresh`,
  `group-lifecycle-completion`) ended their region at lines **3/3/9/5** instead of at their `## `
  headings (**5/5/11/8**) — a **latent false negative**, since any pre-shipping clause in the lost
  continuation was invisible. The boundary now requires a **blockquote** line, which is exact: the
  marker the sweep writes is `> **Drafting-era status — …**`, and its live sentences are never quoted.
  ⚠ This is **v0.4.63's own recorded lesson — "the sweep writes prose into the header the gate reads,
  so its own annotation must be written around the detector's vocabulary" — broken by the sweep that
  recorded it.**
- **PIN:** O6. Reverting the anchor to the phrase-only form reads **2364 / 1** — the single red is O6 —
  against **2365 / 0** anchored. ⚠ No other check in the suite discriminates it, which is why four
  review rounds passed over it.

⚠ **Still open, and named rather than implied:** the five behaviours mutation testing found
unwitnessed in v0.4.65 (unbinding the status window, the boundary's side, the cap term, the two-arm
`elif`, the forbidden `spec_done` guard), and the comment-prose cut. Neither is in this release.

Measured: `tests/smoke.py` **2365 / 0** · `docs_links` **52** spec status lines, 0 errors · `mypy` 0 in 42.

## [0.4.65] — 2026-09-25

**Patch — the findings the v0.4.64 review agents were holding, and a released figure that was wrong.**

The v0.4.64 review fan-out lost six agents' findings to a **delivery budget**: the harness caps a whole
agent drain at **16,000 characters SHARED** across every agent completing together, and caps each string
inside a structured result at **256**. Six agents finished within six minutes and the first one's payload
consumed the pot. Re-queried with file-based delivery — full findings to disk, a three-field reply — they
returned in full: **six agents, six replies, all under 350 characters, zero truncation.**

### Fixed

- ⚠ **A performance regression v0.4.64 introduced.** `_spec_header_end` collapsed to a `min` of three
  `next(...)` calls — an idiom a review lens suggested, adopted after proving equivalence **by result**.
  By result it was identical. By **cost** it was not: both scans ran unbounded, so a spec whose heading
  sits at line 8 still had every line searched for a provenance note. MEASURED: **15,074** provenance
  searches over the corpus against **968** bounded — in a gate that runs in CI, against specs up to
  **3,646** lines. Both scans are now bounded; **0 of 58 results differ**.
- ⚠ **The released v0.4.64 entry understated its own suite by one** — it said 2364 where `435ccb5`
  reports **2365**. The figure was written before the review round that ADDED a check, and never re-read.
- **A check that added no coverage**: the "O3 control" was **byte-identical to the v0.4.63 A4 pin's
  fixture**. Removed, and the D6 constant re-bumped.
- **Eight claims** in the v0.4.64 prose that outran their operands — including one sentence that flipped
  **three times**, where both of my versions *and* a reviewer's "correction" were wrong because all three
  measured a **neighbour** of the operand the claim turns on (`_pending` is False for every spec in the
  arm's population; the `named` citation set was irrelevant to it).

### ⚠ Recorded, not closed

Mutation testing found **five behaviours no check witnesses** — the suite stays green with each one
changed: unbinding the status **window** (only the *target scan*'s use of the region is pinned);
the boundary's **side** (off-by-one on the note term); the **cap** term (deleting it, or 120 → 10⁹);
the two-arm **`elif`** → `if`; and re-adding the `spec_done` guard the source forbids. **Two thirds of
what v0.4.64 changed is unwitnessed.** Named here rather than left as an implication that something
covers it.

Measured: `tests/smoke.py` **2364 / 0** · `docs_links` **52** spec status lines · `mypy` 0 in 42 files.

## [0.4.64] — 2026-09-25

**Patch — the target arm's OPERAND, and three claims its code does not support.** All four were found by
the 2026-09-25 dream pass *verifying* v0.4.63's new status gate against the live tree, and every one is
the class v0.4.63 was **about** — a surface asserting more than its operands support — re-committed
inside the release that closed the class.

### `tests/docs_links.py` — the operand

`check_spec_status`'s target-release arm computed its set from raw `lines[:_SPEC_PREAMBLE_CAP]`. Two
independent over-reaches lived on that one line:

- **No provenance boundary.** `_SPEC_PROVENANCE_QUOTE` bounds the status *locator* and the *statement
  join*; this **third reader of the same field** had no cut at all. v0.4.62's note says the provenance
  note "now bounds the STATEMENT JOIN too, not only the locator" — the arm added at v0.4.63 was never
  given one.
- **No preamble bound.** The status arms use `min(first '## ', cap)`; this used the bare cap, so it read
  up to 120 lines of **body**.

⚠ **MEASURED on the live corpus: the region bound removes the target for 12 of the 17 target-bearing
specs** — the arm was reading preserved *history* as the header's own target for most of its population.
⚠ **Precisely: 11 of the 12 sit on `>`-marked lines of the blockquote; the 12th**
(`env-preflight.spec.md:15`) **is an UNMARKED continuation of the same preserved sentence** — the wrap
dropped its `>`, so the retired line's tail reads as ordinary text. (This entry first said all 12 were
"inside the blockquote", which a review lens measured false. The case is also the design's own
argument: a boundary anchored on `>` prefixes would MISS it, which is why it is anchored on the
provenance NOTE.) It fires on none today because **`_pending` is False** for every one of them —
headers the sweep already corrected to `SHIPPED (vX)`, so no arm has anything to catch. The first
draft of this entry said that, and it was RIGHT.

⚠ **AND THIS SENTENCE FLIPPED THREE TIMES — that is the real finding here.** (2) A review lens
reported the opposite: *"all 5 are already cited, so the CITATION arm preempts this one; the zero is
STRUCTURAL, it is the `elif`"* — and it was adopted into this entry. It is **false**: `if _pending and
named` needs `_pending` TOO, so a cited-but-settled header preempts nothing. The lens measured
**citedness**, observed a correlated fact, and mis-attributed the cause. (3) A second lens measured
the operand that actually decides it — `_pending` is **False for all 5** — restoring the first draft.
⚠ **I propagated (2) having checked `named` and never `_pending`** — the *same* incomplete operand as
the finding I adopted. That is `a-reviewers-correction-is-an-unaudited-claim`, committed twice against
the very claim this release is about. The lesson is not "trust the third measurement": it is
**measure the operand the claim turns on** — and both of us measured a neighbour of it.

⚠ **AND THE CAUSALITY, which is the sharper finding.** The operand was **correct when the arm was
authored**. At `f0a4b75` — the commit before it — `docs/asserted-support.spec.md:7` read
``Target release **v0.4.61 (patch)**`` **in the live header**. `24e2ea8` then added the arm *and* swept
that header in the same commit, moving that exact line into the `>` blockquote. So the arm was dead on
arrival **for its own two motivating instances**: `_targets` is now empty for both, and no `_pending`
value can revive them. **The sweep moved the lines the arm reads.** A repair can invalidate its own
instrument, and here it did so within a single commit — which is why the arm's remaining population
(5 — ⚠ **a measurement, not a mechanically-asserted figure**; an earlier draft of this entry said
"asserted by a new CONTROL", which no check does — see the note on the CONTROL below) is a *different*
population from the one that justified building it.

After the fix the arm keeps a live region-population of **5** (17 = 12 + 5). ⚠ **That 5 is a prose
figure with no mechanical guard** — an earlier draft of this entry said "asserted rather than assumed"
and a review lens measured that false: the new CONTROL asserts a *fixture*, not the corpus count.
Stated here as a dated measurement, which is what it is.

The repair is **one derivation**: `_spec_header_end(lines)` bounds the heading, the cap and the note
together, and all three readers take `lines[:that]`. **A boundary is a property of the FIELD, not of the
reader that happened to observe the defect** — this file has now paid for that twice, and the helper's
docstring says so.

### Three more claims the code does not support

- ⚠ **The arm's own rationale was false, in the present tense.** Two comments asserted the instance specs
  are named *"NOWHERE in CHANGELOG.md — the citation OPERAND hides them, not the matcher"*. True when
  written (`24e2ea8`); **false one commit later**, when `e0a8970` — a **descendant** of that commit — swept
  the headers and added both citations. All 17 target-bearing specs are named there and the arm fires on
  **zero**. The repair invalidated its own diagnosis. Corrected on every surface it appears on —
  **enumerated, not counted**, because the count has been wrong twice: its own clause in this entry,
  the A5 clause beside it, `docs_links.py`'s `_SPEC_TARGET_RELEASE` comment, `smoke.py`'s A4
  pin-block comment, that pin's **check label** (user-visible), and the SKILL blurb above. Two are
  user-visible; each now states the fact historically, and the rationale is kept, not deleted.
  ⚠ **This sentence said "five" in the first pass and MISSED `smoke.py`'s A4 comment**, then said
  "six" and was off again — the note asserting the repair was itself over-claiming, the same defect
  one layer up. **A count is a claim; an enumeration is a list.**
- **`:1004-1006` claimed a suppression never implemented** — *"an UNSHIPPED target anywhere in the preamble
  suppresses the arm"*. The code filters to targets that HAVE shipped, so a header naming both a shipped
  and an unshipped target **fires**. Corrected to match the code, keeping the gate recall-biased.
- **A control's comment claimed a conjunct its assertion omitted** (`checked == 1`), and the A4 pin bound
  its denominator and never read it. Both now assert what they claim.

### Measured

- `tests/smoke.py` **2365 passed / 0 failed** — ⚠ **CORRECTED at v0.4.65.** This line said **2364**,
  because the figure was written after the release's first commit and this entry's own review round
  then ADDED O5, taking the suite to 2365 — the number was never re-read after the edit that moved it.
  Re-measured on the released revision `435ccb5`: **2365 passed, 0 failed**. A count belongs to the
  revision it was measured on, and this one was carried. On a **FULL COPY** of the pre-fix tree with only
  `docs_links.py` restored — `git checkout -f`, **markers verified at 0 BEFORE measuring** (the void-run
  defect recorded at v0.4.63) — **2362 / 2**, the two reds being exactly the two new pins: O1 (the
  provenance boundary) and O2 (the preamble bound). Both assert **silence**, so they redden pre-fix **by
  VALUE**. The new CONTROL (the arm still fires on a shipped target in the real preamble) and the new
  GUARD (the per-line locator's bound is a no-op — 0 of 52) are green on **both** trees, and are labelled
  CONTROL and GUARD rather than pins.
- ⚠ **The statement JOIN's region bound (added here after review) is a no-op on the live corpus too**
  — **0 of the 26** note-carrying specs change behaviour, `checked` holds at 52 — but it closes a
  *reachable* hole: pre-fix, a region ending `**Status:** SHIPPED (v0.1.0).` followed by a
  provenance line carrying `awaiting review` **fired**, quoting a clause the region deliberately
  excludes, because `_cut2` truncates at the provenance phrase and keeps whatever precedes it on
  that line. It is a GUARD, not a pin.
- `tests/docs_links.py` green at **52** spec status lines — **unchanged**, measured before the edit and
  re-measured after rather than carried. ⚠ **CORRECTED at v0.4.65:** this line said *"a mid-line
  provenance note would have made the line-index cut stricter than the char-index cut it replaces;
  none exists"* — and **"none exists" is false as measured: 26 specs carry a provenance phrase with a
  prefix, 4 of them with a non-markup prefix.** The shape is *established*, not absent. The
  denominator holds at 52 for a narrower reason: none of those 26 pairs the note with a declaration on
  the SAME line, which is the condition that would actually drop a spec. Recorded rather than quietly
  re-worded, because "the thing that would break this does not exist" is the claim most worth
  measuring and this one was not.
- `validate_manifests` · `simulate_accumulation` · `mypy` 0 issues in 42 files.

⚠ **Two of the four defects have no observable** — both are comment corrections — so they carry no pin.
That is stated rather than papered over with an assertion that reads prose, which would rot in exactly the
way the claims it tested did.

## [0.4.63] — 2026-09-25

**Patch — the recorded-open docket, closed.** Items earlier cycles wrote down rather than fixed, plus FIVE
holes the status gate this cycle shipped turns out to have had all along — and ⚠ three of the DOCKET's own
entries were wrong when recorded, which is the roadmap's standing warning earning its place again.

### The gate's five holes (`tests/docs_links.py` → `check_spec_status`)

`check_spec_status` shipped at v0.4.61 and was corrected twice at v0.4.62. It had four more.

- **A1 — DONE-WINS**, and the live instance is this release's own predecessor. The classifier EXEMPTED any
  statement containing a done-token, so a header asserting BOTH states passed:
  `docs/asserted-support.spec.md` read *"implemented and REVIEWED … awaiting merge"* and **survived two
  merges**, because "implemented" excused it. `spec_done` now only SELECTS THE MESSAGE. ⚠ Positional ranking
  ("last clause wins") was simulated and **MEASURED producing a false negative**, because
  `network-graph-interaction`'s unfinished clause is followed by a later shipped one.
- **A2 — the mention fallback** now requires the LABEL shape (`status` + colon). Measured: the
  deletion-mutation leaks drop 7 → 1 while keeping the mid-sentence declaration it exists for. And the
  provenance note now bounds the **statement join** too, not only the locator — v0.4.62 applied it to one
  and left the other, so the correction text the sweep itself writes was parsed as a header's own status.
- **A3 — four headers stated a vetting state the alternative list never matched**: *"revised for review"*,
  *"design-of-record"*, *"ready to ship"*. Widened **with** A4, because the target-release arm is what keeps
  a spec legitimately aiming at a FUTURE release silent. ⚠ `draft` is no longer a bare alternative: with it
  bare, `index-usage-and-budget-ladder` fired on prose (*"a code-review-skill gate on the draft"*) for a
  header whose status is *"Phase A/B/C SHIPPED"* — it now needs a CLAIM CONTEXT.
- **A4 — the arm that needs NO CITATION.** A header naming `Target release: vX.Y.Z` where vX.Y.Z already
  shipped is decidable without one. ⚠ Its first cut carried a `spec_done` guard — **A1's hole
  re-committed inside the arm written to close it.**
  ⚠ **CORRECTED at v0.4.64 — two claims here were false as written.** This entry said the two instances
  are named *"NOWHERE in CHANGELOG.md — the citation OPERAND hid them, not the matcher"*. That was TRUE
  when the arm was written (`24e2ea8`) and **false one commit later**: `e0a8970` (a DESCENDANT) swept the
  headers and added both citations. Re-measured: all 17 target-bearing specs are named there and the arm
  fires on **zero**. Its OPERAND was also narrower than intended — it read raw `lines[:120]`, so **12 of
  the 17** targets it saw came from the preserved drafting-era blockquote rather than the live header
  (fixed in v0.4.64; the arm keeps 5 live specs). The text above is preserved as the reasoning of record,
  not deleted.
- **A5 — the search region is the PREAMBLE** (before the first `## ` heading), not a fixed 40 lines:
  `marker-coordinate-truth.spec.md` declares its status at line 84 and its header runs to 93.
  ⚠ **CORRECTED at v0.4.64:** this was true of the STATUS reader only. A4's target scan was never
  preamble-bounded — it used the bare 120-line cap — so "the search region is the PREAMBLE" described one
  arm and was false of the other that shipped in the same release.

⚠ And the statement cap went **3 → 6**: at three lines, `asserted-support`'s wrapped *"awaiting merge"* fell
outside the join and the header read as settled — the very instance A1 exists for.

**8 headers swept**, each preserving its retired line VERBATIM. `docs_links` examined **51 → 52**.

### ⚠ A new lesson, measured FOUR times while implementing this

**The sweep writes prose INTO the header the gate reads, so its own annotation must be written around the
detector's vocabulary.** *"a pending one"* and *"a design-of-record sentence"* both became findings against
the matcher that had just been widened — the second against the vocabulary added in the same session. An
audit for it is recorded; re-run it after every sweep.

### Measured

- smoke **2360 passed, 0 failed** (was 2345; +15 checks). Pre-fix tree (`f0a4b75` + the SAME suite):
  **2353 passed, 7 failed** — the seven pins red (A1·A2·A3·A4·A5·B3·B4), each for the reason it
  names, with **all six CONTROLS green on BOTH trees** and B2's guard green on both, as its label says.
- `docs_links` green at **52** status lines; **12 required strings across 2 files** (was 7, README-only).
  manifests v0.4.63 · sim · mypy 0 issues in 42 files.
- ⚠ **A measured-once-then-corrected near-miss, recorded because it is the class this release is
  about:** the first both-tree run reported the pins GREEN pre-fix. The pre-fix build had used
  `git checkout origin/main` on a copy carrying the branch's uncommitted edits — it printed **"Aborting"**
  and left the tree unchanged, so both sides were the same tree. Re-done with `-f` and the markers
  verified at 0 before measuring.

### Workstream B — the recorded code items

- **B1 — the `_served` type hole, wider than the record said.** `facts_manifest` now raises a named
  `UnclassifiedReason(AssertionError)` **at all three sites** (`_mint`, `_served`, `_miss`) — the
  type-agnostic pin shape sat at `_mint`'s check too, so naming the class at one site would have left the
  hole live at the weakest. A subclass keeps every `except AssertionError` working. Measured on three
  isolated trees: post-fix green; the recorded `ValueError` mutation **RED** (the old pin was green on it);
  pre-fix RED without crashing. ⚠ It is a **GUARD, not a PIN** by this repo's rule — its pre-fix red is
  still KEY-ABSENCE — and it is labelled so.
- **B2 — `try_acquire` is genuinely not closable, and the recorded reason was incomplete.** *"Cannot be
  closed without reintroducing the `blocking=` keyword"* names ONE design's cost. The blocker is the
  **signature**: `acquire`'s body *waits*, so every route through the override pays — wait; or pass a
  parameter the override may not declare (`TypeError` at *its* call site); or probe/release/re-enter, which
  makes "never waits" false in a race window that is separately pinned. The one design that does not route
  through it (detect an acquire-only override and raise) is named and **refused**, because it would refuse
  a logging-only override at a site the subclass never declared — trading a silent skip for a wrong
  refusal. **Zero behaviour change**; the caveat now sits on the method its caller reads, and a GUARD is
  reported that witnesses the bypass by mutation.
- **B3 — the census was 8, not 5, and the record contradicted itself.** Its own paragraph reads "4 parsers /
  8 silently-accepted choices" and then "The remaining four (`cm journal` ×3, `cm group` ×2)" — 3+2=5
  against its own total of 8. Decomposed by `(parser, subcommand, ignored-positional)`: `data` 9 (one guard
  covers all nine) · `local` 2 · `canonical` 1 (all guarded since v0.4.57) · `journal` **3** ·
  `group` **5** — `project` is read by `add`/`remove` ONLY, so `create`/`delete`/`show`/`list` drop it, and
  `list` drops `name_or_group` too. **8 were unguarded.** ⚠ The record's *reason* for exempting them held and
  was measured (plugin-data is global; `cmd_group` hardcodes its ctx) — so the guards rest on the class rule
  the shipped ones state in their own comments, not on severity.
  ⚠⚠ **AND THE METHOD IS THE FINDING.** The re-derivation's FIRST cut reproduced the recorded 5 exactly:
  a census bug reading `('a','b') in cmd` instead of `cmd in ('a','b')` misread `if cmd in ("add","remove")`
  as unconditional and attributed its `args.project` read to every still-live choice — out came "group ×2,
  journal ×3", the record's figure to the digit. **A defect that lands on the number you were told is why
  the number needed re-deriving at all.** The fixed instrument (argparse introspection + AST reachability,
  descending into the wrapping `try:`, resolving `cmd = args.<x>_cmd` aliases) agrees on all 8, and does
  NOT flag the three v0.4.57-guarded parsers — which is the sanity check that its notion of "closed" lines
  up with the shipped guards.
  ⚠ And its blind spot caught the author's own guard: the new `group` guard read both positionals through a
  **variable key** (`getattr(args, k, None)` in a comprehension), which no static census can name, so the
  post-fix audit reported 5 sites still open while the behaviour was correct. A guard written defensively in
  a way the audit for its class cannot see is one that gets re-filed as open forever; it now reads literals.
- **B4 — the wrapped-anchor class, live at a site the record never named.** The v0.4.57 item named
  `CLAUDE.md:32-33` and **that span was never an instance of the class it cited** — measured contiguous at
  v0.4.57, at v0.4.62 and today; the live one sat at `:20-21` the whole time. **The record's boundary was
  read rather than measured.** That token is now one unbroken span, and `check_contiguity` gained an
  explicit **per-file needle map** (never a glob) with new needles for `CLAUDE.md` — because re-using the
  README's seven adds **zero** coverage there (0 of the 7 occur in that file, measured) and would have read
  as coverage while being vacuous. `docs_links` reports **12 required strings across 2 files** (was 7,
  README-only); a wrapped needle REDS the new arm and a deleted one REDS presence, partitioning cleanly.
- **B5 — the unread binding, made to carry.** `_why_ov52` is now read in its check's predicate
  (`and _why_ov52 == "oversize"`). Measured green on both trees, so it stays a GUARD — but it is UNIQUELY
  discriminating: the mutation "rename the token AND declare it in `_ENSURE_REASONS`" leaves every producer
  pin green and reddens this conjunct alone. The file's own precedent agrees — the sibling kill-switch
  check reads `_why_ks == "kill-switch"`, with a comment saying why the structural pin cannot see it.


## [0.4.62] — 2026-09-25

**Patch — corrections to v0.4.61, found by its own review round after it shipped.** Every one is an
instance of the class v0.4.61 was about: a surface asserting more than its operands support.

### The figurable number

v0.4.61's entry, its `SKILL.md` summary and its design-of-record all reported the RC-2 projection as
**`1940 → False`**. The PIN asserts **1992**, and 1992 is what the fixture produces (a 29-char evicted
line → `est_tokens` 8; 2000 − 8 = 1992). 1940 was the value from the RETIRED per-line-sum relief,
carried forward when the pin was updated. ⚠ A release whose thesis is *asserted support* shipped an
unreproducible figure on three surfaces — and the figure was contradicted by the pin the surfaces cite.

### The gate read the wrong line

`_SPEC_STATUS_LINE` took the FIRST line in its window containing the word `status` — which can be a
PROSE MENTION above the real declaration. MEASURED on `docs/1.0-preflight.spec.md`: it matched line 5
(`… call reads. Status per item: ✓ certified …`) and never the `**STATUS (2026-09-24): …**` at line 8
that `LIVE_DOCS` reads — so the gate counted the file as EXAMINED while inspecting a sentence, and
rewriting line 8 to DRAFT would have left it green. The matcher now ranks a DECLARATION above a mention.

⚠ **That fix moved the census a THIRD time, and the third move is the interesting one.** The count went
13 (line-anchored) → 14 (word anywhere) → **13** (declaration ranked first), because the widened form
had been reading `env-preflight.spec.md`'s first line and missing the “Shipped in v0.4.16” four lines
below it. **One of the 14 sweeps was therefore unnecessary** — `env-preflight` was never stale. Nothing
was lost (its drafting-era text is preserved verbatim), and the count is now stated with the instrument
that produced it. A gate's number is a property of its matcher.

### Three more, each a claim its operand could not carry

- The suppressed relay in `seed_record` used `.get(k, DEFAULT)`: `reaches_budget` defaulted **True** —
  the OPTIMISTIC direction on the very field that SELECTS a rendered remedy, which is RC-2's own thesis
  re-committed inside RC-2's own relay — and the counts defaulted 0. Now **presence-gated per key**, so
  a value the triage never supplied is absent rather than asserted. (The `mirror_share` half of this
  was fixed in the same round; the rest was not.)
- `_remediation_section`'s new fall-through gated on `stages` while `render_dashboard` gates on
  `candidates_surfaced` — two renderers of one block disagreeing about what “the triage ran” means, and
  the tail's hard subscripts (`rem['keep_core']` et al.) would `KeyError` on a record-shaped dict. One
  predicate now opens the block, and the tail is presence-gated so it stops where its data stops.
- A code comment justified the relay as serving “the DASHBOARD, which CLAUDE.md names as the end-user
  deliverable”. **CLAUDE.md makes no such claim**: the artifact SKILL.md Phase 5 points an END USER at
  is `dashboards/index.html`. Corrected there and in the entry.

⚠ **Standing lesson (new):** the same class bit this release's own MEASUREMENT twice — two throwaway
scripts of mine re-implemented the gate's window-slice and disagreed with it (13 vs 14). **Measure with
the instrument, not a copy of it**; the copy diverges exactly where the rule is subtle.

### ⚠ Three more, from the same round's second drain — including one VISIBLE in the shipped output

- **The remedy contradicted its own header, in the released artifact.** On a standing-justified store the
  report printed `✓ … STANDING-JUSTIFIED` at the top and then **"prune the safe candidates, THEN
  standing-justify the residual"** at the bottom — instructing the operator to do what the header says is
  already done. On an OVER-CEILING store it is worse: the residual is still over the ceiling, so the
  sentence names a standing-justification the ceiling line three rows up **forbids**. Both renderers now
  carry a standing-aware remedy ("the target gate is OFF — the binding constraint is the CEILING"), and the
  layer-2 pin asserts its PRESENCE *and* the prune sentence's ABSENCE, so the contradiction cannot return
  as a passing render.
- **The sweep's own convention was a trap for the gate that reads it.** The v0.4.61 sweep preserves each
  retired line inside a blockquote beginning `**Drafting-era status — never revisited after the arc
  closed.**` — which matches the gate's PRE-shipping vocabulary through "Drafting". So in any swept spec,
  deleting the live declaration (the cheap fix the gate's own message invites) would make the fallback
  land on the PRESERVED line and RED **quoting history as the header's own status**. Measured: 0 misfires
  today, i.e. the pass rested entirely on the live line happening to precede the quote. The provenance note
  is now a **BOUNDARY**, not a filter — excluding it by text is not enough, because the quote's *second*
  line (`> Status: draft → …`) is declaration-SHAPED.
- **The validator's own index omitted its new gate.** `tests/docs_links.py`'s module docstring enumerates
  invariants 1–10; `check_spec_status` shipped as an eleventh with no entry, so a maintainer asking "does
  any gate read a spec's status?" read a contract that mentions no status axis — the very enumeration
  §RC-4 leans on. Entry 11 added.

⚠ **And a residual, measured rather than implied:** with the trap closed, a corpus-wide probe (remove
every `Status…`-leading line, then ask what the fallback finds) still leaks on **2 of 50 specs** —
`completion-driven-archiving.spec.md` (a continuation of the deleted declaration) and
`index-usage-and-budget-ladder.spec.md` (a genuine "Phase C status note"). Left live and recorded in the
gate's docstring rather than narrowed, because narrowing would drop the MID-SENTENCE shape that caught a
real file.

### ⚠ And two more from the same drain — one of them a FALSE CLAIM THIS ENTRY'S OWN FIX INTRODUCED

- **The archive pointed at a list no record can contain.** The v0.4.62 sentence added to
  `dashboard.template.html` ended *"— the staged list is in this cycle's record below"*, and a late lens
  measured that **no record can carry one**: `seed_record` relays `lever`/`candidates_*`/`projected_*`/
  `reaches_budget`/`over_ceiling`/`mirror_share` and never `stages` (the only `"stages"` writes in the file
  are the triage's own return and `_remediation_section`'s reads). So the END-USER surface pointed the
  reader at something that does not exist — **a false claim in shipped copy, written by the fix whose
  whole subject is claims that outrun their operands.** The pointer is removed: the count and the lever
  are what the record can support, and the staged NAMES are the dream report's job (it reads the live ctx,
  which does have them).
- **A cross-plugin effect, named rather than left to be discovered.** `dream-beta-tester`'s
  `_skill_triage` guarded on `rem.get("stages")` with a comment promising *"if it suppressed
  (standing-justified) … there are no stages"*. RC-1 invalidated the first half **without a line of that
  plugin being touched**: a standing-justified store that is ALSO over the hard ceiling now gets its
  stages built, so the function returns a dict where its comment promised `None`, and the beta oracle's D4
  leg emits a PASS row for a store class it previously said nothing about. The new behaviour is INTENDED —
  such a store genuinely has prunable candidates — but a consumer changed by a producer's edit is exactly
  the thing a comment should say out loud.

### Measured

- smoke **2345 passed, 0 failed**; the pre-fix tree with the same pins reads **2333 passed, 12 failed**.
- `docs_links` green (51 status lines). manifests · sim · mypy 0 issues in 42 files.
- 1343 browser checks; the committed preview regenerated.

## [0.4.61] — 2026-09-24

**Patch — asserted support: four surfaces that asserted a verdict their operands did not support. ⚠ The
first of them manufactured a WRONG CONCLUSION inside the very pass that found it.**

### RC-1 — the hard ceiling's instrument was suppressed with the gate

`memory_status.py`'s standing-justified branch built no `stages`, and `_remediation_section` returned from
the suppression branch *before* the staging loop. v0.1.21 suppressed the triage on standing-justify
deliberately; v0.1.66 then added the hard ceiling as a **sibling signal** and hardened its **line** against
that suppression — with a comment promising suppression "never hides it" — while leaving the **stages the
line points to** behind the same early return. So an over-ceiling store was told **"shrink to receive"** and
shown no candidates. ⚠ An empty candidate list reads as the verdict *"nothing is prunable."*

**MEASURED, and it is why this entry exists.** `--triage` on this store printed two blocks and no stages.
The 2026-09-24 dream pass recorded from that absence that *"there is no lesson-free relief; the ceiling's
only consequence is a held test fixture"* — **a conclusion produced by the defect, in the pass that found
it.** With the stages restored: **2 tracker/status + 6 dated/oversized** candidates, and a full prune frees
**3991 → 3587 tok — under the 3840 ceiling.** The ceiling *is* locally satisfiable here.

The ceiling boolean is now hoisted above the branch — a **pure move**; it still does not enter the
`required`/standing-justify computation — and the stages are built when `over_ceiling`, with the VERDICT
still the suppression's (`required` stays `False`). ⚠ The cost is paid only by a store that is BOTH
standing-justified AND over the ceiling, which is precisely the store whose ceiling line was unactionable.

### RC-2 — `projected_index` never computed what it declared

`Remediation` has declared `projected_index` as *"est index tokens after evicting the candidates"* and
`reaches_budget` as *"can a full prune of the candidates reach budget?"* since v0.1.18. The implementation
computed `keep_core × _LEAN_HOOK_TOK` — the keep core re-indexed at an assumed lean cost — which is
**neither** quantity. ⚠ Not a badly-tuned constant: the **wrong quantity**, at roughly half the writer (the
constant read 30 against the 58.3 tok/pointer this store's own archive had already recorded). And
`reaches_budget` **selects a rendered remedy** (`render_dashboard.py`), so the model printed the `prune`
advice the D5 clause exists to replace with prune-THEN-justify.

MEASURED: the model computed `keep_core(1) × 30 = 30` → `reaches_budget True`; the measured computation
gives **1992 → False** (⚠ CORRECTED after release: this said 1940 — the value from the retired
per-line-sum relief — while the PIN already asserted 1992. Caught by a late review lens that
re-derived it from the fixture the entry cites rather than from the entry.) They disagree on the verdict. `_LEAN_HOOK_TOK` is **deleted, not retuned** — the
relief is now the evicted candidates' own pointer-line costs, read from the index, and an unreadable index
frees **nothing** (the pessimistic direction, so a store we could not scan is never told a prune will reach
budget).

### RC-3 / RC-4 — a status claim outside every matcher

`LIVE_DOCS` is a **version-currency** set. A spec's STATUS is a different axis and was in **no** set, so a
drafting-era header survived every check: four did, for months, with the suite green, and the survey that
followed found **14**. `tests/docs_links.py` gains `check_spec_status` — a `docs/*.spec.md` whose header
states a pre-shipping state while `CHANGELOG.md` names it inside a `## [X.Y.Z]` release section is a RED.
⚠ The rule is **versioned on purpose**: its first form ("cited anywhere in CHANGELOG") was **circular**,
the same signal serving as the rule's input and as the evidence that the work had landed. It fires on
exactly 13 release-named, of 16 pre-shipping — ⚠ and this number moved TWICE, once per matcher fix, which
is why it is stated with the instrument that produced it (see the review round below).

14 headers are swept — ⚠ one more than the 13 the shipped matcher finds, because `env-preflight.spec.md`
already said "Shipped in v0.4.16" and the narrower matcher could not read that far. Fixing the matcher
changed the census; the extra sweep was harmless and nothing was lost. ⚠ Two claims from the v0.4.60 checkpoint PR are corrected: its **commit message**
says FOUR where a census finds 14 — a commit message is immutable, so the correction lands on the readable
surfaces — and **three** spec notes said *"nothing reads a spec's own header"*, where the true and narrower
statement is that no gate read a spec's status **WORD** (`docs/1.0-preflight.spec.md` IS in `LIVE_DOCS`, and
its status line IS read, for a version token).

### ⚠ The review round — six findings against this fix, all patched

A `/code-review` over the committed revision produced 11 findings. The substantive ones are fixed here,
and each is an instance of the class this entry is about.

1. ⚠ **RC-1 stopped at the live-ctx layer.** `seed_record`'s standing-justified arm relayed no `stages`
   and no `candidates_surfaced`, and `render_dashboard` guards its OWN renderer on that key — so the
   DASHBOARD still printed *"shrink to receive"* over an empty space. ⚠ The first draft of this item
   attributed the claim to `CLAUDE.md`, which does NOT make it — the artifact SKILL.md Phase 5 points an
   END USER at is `dashboards/index.html`, the HTML archive, and the repair had not reached that either.
   Three surfaces now carry it: the terminal report, the ASCII dashboard, and the archive template
   (`dashboard.template.html`, 1343 browser checks green). ⚠ And the D5 remedy is keyed on the LEVER,
   not on the operand alone — gating it on `reaches_budget is False` printed prune advice directly under
   a line reporting `lever JUSTIFY`.
2. ⚠ **The new gate's matcher was narrower than its own claim.** `_SPEC_STATUS_LINE` was anchored on
   `status` STARTING a line, so `docs/cm-commands-onboarding.spec.md:3` — status mid-line, NAMED in
   CHANGELOG §0.4.8 — was invisible, and two specs that state a status as a TITLE had no `status` word
   to find at all. The census is **16 pre-shipping headers, 14 release-named** (not 13), and 14 are swept.
3. ⚠ **…and `_SPEC_DONE` was negation-blind**, matched over a 60-char slice while PRE saw the whole line.
   *"awaiting approval; nothing shipped yet"* and *"drafted, unimplemented"* were exempted by the very
   words stating the defect — a silent false negative on a coverage gate. Both predicates now see ONE string.
4. ⚠ **The first sweep DELETED content.** It truncated each drafting-era status line at 120 chars, and
   `fleet-topology-ui.spec.md`'s carried a stated residual-risk disclosure (*"pixel-identical rests on
   string-presence pins over unexecuted JS…"*) — absent from the tree until a lens re-read it against
   `main`. The sweep now preserves the region VERBATIM as a blockquote.
5. ⚠ **`projected_index`'s relief summed per-line `est_tokens`.** That function rounds up PER CALL, so N
   summed estimates exceed the block they describe — an OPTIMISTIC bias on the one operand that selects
   the D5 remedy, and the opposite of the direction the docstring promised. The relief is now one
   `est_tokens` over the JOINED evicted lines, the same measure the index total was taken with.
6. **Hygiene:** the pointer-line scan was a second walk of the same list (now one pass feeding both
   consumers); the `stages` guard added to the suppressed arm was not mirrored on the gate-active arm,
   which still subscripted `rem["stages"]`; and consumer prose in
   `docs/index-usage-and-budget-ladder.spec.md` and the beta oracle still described the retired model.

⚠ **And two the review did not have to make, because this release's own design-of-record made them
against itself:** its Risks block carried the PRE-fix draft of the ceiling conclusion, and a *"One
builder, not two"* paragraph described a helper that was never added. Both are corrected in place with
the correction visible rather than silently edited.

### Measured

- smoke **2343 passed, 0 failed** (was 2332; +11 checks). Pre-fix tree, same pins: **2333 passed, 10
  failed** — every new PIN red, the RC-1 CONTROL green on BOTH trees, totals line present and D6 reached.
  ⚠ The RC-4 arm pair reds on BOTH trees BY ABSENCE (`check_spec_status` does not exist pre-fix) — the
  shape the v0.4.40 pin established for this validator, stated rather than glossed as a control.
- `docs_links` green, with **51 spec status lines** now in its denominator; on the un-swept corpus the
  shipped matcher is RED on 14. ⚠ The first draft of this line said 45 — the number the RETIRED narrow
  matcher produced, carried forward instead of re-measured. No revision of the corpus yields it.
- ⚠ The new pins route through a new `_ms61` helper because two symbols they call **do not exist pre-fix**
  (`_index_after_prune`, and `remediation_triage`'s `pointer_line_tokens=`). Unguarded they raised at
  **module scope** and took the whole run with them — no totals line, D6 never reached. That is the
  crash-class this repo has now met five times, and the guard caught it *before* the pins shipped.

## [0.4.60] — 2026-09-24

**Patch — F3, the last residual the v0.4.59 review left open: a mutation of the suite's subject could
CRASH the run where a red belongs, and the pin that was supposed to catch it could never be reached.**

### The defect, root-caused

The v0.4.59 pin asserts that the reason guard **accepts both vocabularies**. Its motivating mutation —
narrow `_KNOWN_REASONS` — should redden it. Instead the run **died at `smoke.py:23747`** with **no
totals line and D6 never reached**: `ensure` raises, and that raise escaped **module scope** from an
*unrelated* check (the v0.4.45 kill-switch guard, whose `ensure` call sat in a `try/finally` with no
`except`). The pin's claim was not weak — it was **unreachable**, and the thing blocking it was nine
thousand lines away.

### ⚠ The sweep mattered more than the line

The reviewer named one site. There were **six `ensure` calls in the suite and FIVE were unguarded** —
so fixing the named line would have left the class standing. That is the sibling-parity failure this
repo has a standing lesson about, and v0.4.59 had *just* shipped a fix for its other half in
`preflight.py`.

All five now route through one shared **`_ens59`** wrapper that turns a raise into a **value** the
callers assert on. ⚠ Not swallowed: the raise is **returned**, so a mutation still **reddens**. The
two failure modes this rules out are opposite and both silent-in-the-wrong-direction — a **crash**
where a red belongs (the shipped defect) and a **green** where a red belongs (what a swallow would
have bought).

### Two defects inside this fix, both found by running the mutation rather than reading it

1. **`NameError`.** The wrapper was first placed beside `_fm44` — at line 23619, while its first call
   site is at 14297, in a 26,000-line script that executes top-to-bottom. The clean run died
   instantly. It now sits with the shared helpers and imports lazily, so it depends on **no**
   module-level name's position.
2. ⚠ **A local variant that caught a SUBSET.** A pre-existing local helper (`_ens45`) caught only
   `TypeError`, and was left in place as "already handled" — so the F3 run **still died at that
   line**, after every other site was routed. A local copy of a shared helper that catches less than
   the shared one is the divergence class this repo keeps closing; it is **deleted**, collapsed into
   `_ens59`, whose `TypeError` arm preserves its shape.

### Measured

| | |
|---|---|
| clean run | **2332 passed, 0 failed** |
| the F3 mutation | was: **crash**, no totals, D6 absent → now: **2329 passed, 3 failed**, totals present, **D6 reached** |
| the three reds | the kill-switch guard, the v0.4.59 reason pin (F3's goal), and the read-only-caller pin — no collateral |

⚠ This failure class — a mutation that CRASHES the suite instead of reddening it — has now appeared
**four times** on this project, twice in code written to close it. Each instance was found by
executing a mutation; none was visible to a passing suite, because a suite that never crashes looks
exactly like a suite whose subject never breaks.

## [0.4.59] — 2026-09-24

**Patch — the remaining open items, each with the measurement that named its repair.** Two were
shipped *recorded open* by v0.4.57 rather than quietly closed. ⚠ **The third was not open at all**:
the citation-binding gate had already shipped at v0.4.37, and this release's first cut built a
duplicate of it before an exploration pass caught the premise. That correction is item 3 below,
and it is the more useful half of this entry.

1. **The reason classification gets a RUNTIME half** — `facts_manifest.py`. The pin enumerates the
   AST **spellings** `_mint("<literal>")` / `return x, "<literal>"`, so a reason minted through a
   **name** — `return None, _NEW_TOKEN` — passed every check while circulating an unclassified
   reason (MEASURED: all ten v0.4.57 checks green, while the literal-form control reddened).
   ⚠ **No wider scan can close that**: a `Name` in the return position is
   AST-indistinguishable from `load()`'s legitimate passthrough, which is why the pin enumerates
   literals at all. The producer can see the value and the scanner cannot, so the validation now
   sits at a **single exit** — `ensure` wraps an inner function and validates what comes back —
   membership at every `ensure` return. ⚠ It accepts **both** vocabularies — `ensure` passes
   `load()`'s reasons through, so a guard keyed on `_ENSURE_REASONS` alone would redden on correct
   trees.


   ⚠ **Two review findings landed on this fix before it held, and both were about TOTALITY**
   rather than behaviour. **(1)** The first cut called the validator from **four individual
   returns** — totality by *convention*; a lens measured that a NEW return, or an existing one
   edited to drop the call, escaped with the suite green at 2331/0. **(2)** The wrapper that fixed
   that left an **importable bypass**: the inner sat at module level, so calling it directly
   returned an unvalidated reason and nothing noticed (the structural pin inspected `ensure`'s
   returns, never call sites). The inner is now a **CLOSURE** — a name that cannot be imported
   cannot be called, so the bypass is inexpressible rather than merely undetected.
   ⚠ And the pin written to guard that property **reddened on its own author**: `ast.walk(ensure)`
   descends into the nested function, so it counted the inner's six returns as `ensure`'s. It now
   counts OWN returns. That is the FIFTH instrument in this one patch to break on a refactor of the
   same function — every one asserting a property of a SHAPE rather than of a VALUE, which is
   precisely why the half that held is the half that reads values.
2. **Two `preflight.py` sites stopped MANUFACTURING VERDICTS.** Unlike the `control_plane` sites
   fixed in v0.4.57 (where the failure mode was a *silent cleanup*), these turned a faulted
   `LOCK_UN` into a *finding*, because each wrapped the acquire and the unlock in ONE `try`.
   MEASURED: the held-lock advisory reported **"1 HELD lock file(s) — another process holds the
   plane; wait or investigate"** for a directory nobody held, and `probe_sqlite_roundtrip` reported
   **`fail`** with the remedy *"Check disk space/permissions"*. Now **only the acquire decides**;
   the unlock is cleanup. ⚠ Swallowing it is safe for the reason a review lens measured on the
   sibling fix: `os.close(fd)` / the `with` close releases the flock via `close(2)` regardless.

3. ⚠ **The citation-resolution gate was ALREADY SHIPPED, and this release's first cut built a
   DUPLICATE of it.** The item was recorded open — *"the citation-binding gate designed in
   `prose-tied-to-the-tree.spec.md` remains unshipped"* — and an exploration agent repeated it
   (*"no resolver in `tests/`"*). **Both were false.** The gate has run since **v0.4.37** as
   `tests/smoke.py` pins 6/7a/7b/8/9 — visible in this very repo's suite output, which prints
   `v0.4.37 pin 7b … 25 of 25 citing docs resolved` on every run — and `CHANGELOG.md` records it
   as shipped, with `ci.yml`'s `fetch-depth: 0` commented *"REQUIRED … smoke.py's citation gate
   resolves every…"*.

   ⚠ **A second implementation is the divergence class this repo keeps closing**, so the duplicate
   was reverted rather than shipped alongside. The lesson is the one this whole docket has been
   teaching: an item recorded as open is a HYPOTHESIS, and a hypothesis about *absence* needs the
   same measurement as any other — I checked that no resolver existed in `tests/docs_links.py`,
   and read that as no resolver existing.

   ⚠ Worth stating what the shipped gate does and does not do, since the duplicate was built on a
   belief about that too: it resolves each citing doc against the revision the doc **declares**
   (range-checked, a range's END included, disambiguated by line-fit) — so it verifies **range,
   not content**, and would **not** have caught the citation v0.4.57 repaired by hand. The
   v0.4.57 entry's own note that this *"remains unshipped, so one unbound citation was fixed by
   hand"* is corrected here rather than left standing.
Suite: **2332 passed, 0 failed**; `mypy`, `docs_links`, `manifests`, accumulation sim green.

## [0.4.58] — 2026-09-24

**Patch — two defects in v0.4.57's own final check, both found by the review round that was still
reporting when 0.4.57 merged. Shipped as a correction rather than folded into that tag.**

The check was added *specifically* to close a coverage gap — v0.4.57's beacon pin asserted only
`rc == 0` and a time bound, which a payload-**dropping** regression satisfies perfectly. It shipped
with two defects of its own, both the class it was written to close:

1. **It crashed the pre-fix suite at module scope.** No `guard` around `_read_stdin_bounded`, which
   does not exist on the pre-fix tree — so instead of reddening, the run died with `AttributeError`:
   **2292 check lines, rc=1, NO TOTALS LINE, D6 never ran, 37 checks lost.** ⚠ That is the *exact*
   defect the sibling walk-pin had, **fixed one commit earlier and reintroduced here**. A pin that
   crashes a pre-fix run is not a pin; it is a lost counter. Now `getattr`-guarded, so a pre-fix tree
   yields a clean **red** — which by the v0.4.45 precedent makes it a **GUARD**, not the PIN it was
   labelled, and the label is corrected.
2. **It was blind to the constant it claimed to guard.** The call passed a **hard-coded `1.0`** while
   production reads `_STDIN_DEADLINE_S` — so the mutation its own comment names as its reason to
   exist (`1.0 → 0.01`, a 35× tighter window) left **all ten v0.4.57 checks green**. The gap was
   still open. ⚠ A literal standing in for a declaration is the same shape as the residual recorded
   in that very commit; the check now reads the module constant, so the window is its **subject**.

**Verified by that mutation**, not by reading the code: with the shipped window the 0.45 s payload is
read; with `0.01` it is dropped — so the check finally discriminates the thing it is named for.

Minor, same site: the late-writer thread's write is now `OSError`-guarded, so a failure path cannot
emit a stray traceback onto the verdict's channel.

Suite: **2329 passed, 0 failed**; `mypy`, `docs_links`, `manifests` green.

## [0.4.57] — 2026-09-24

**Patch — the open-items docket, closed. Every item was VERIFIED against the live tree before it was
touched, and three of the fourteen turned out to be already fixed — a docket carried across fourteen
releases is a hypothesis, not a work list.**

The docket came from three sources: the roadmap memory (stamped v0.4.42), the v0.4.56 review round, and
two items a lens found while re-measuring the beacon. Verification was delegated per cluster and each
verdict is a measurement, not a reading.

### Already fixed (no change made, and that is the finding)

| Item | Fixed by |
|---|---|
| `SECURITY.md` ↔ `release.yml` contradiction on provenance/SBOM/SHA256SUMS | `1412e72` (v0.4.37) + a live pin tying the prose to the upload line |
| the duplicated `which is why` / stray `...` comment scar in `render_html.py` | `ff94a73` |
| `AGENTS.md`'s plugin row reading a stale version | fixed during the v0.4.4x line |
| **`render_html` identity misattribution** — the "quiet arm" | `475af7b` (v0.4.36) |

⚠ **The identity item is the one worth reading.** It is fixed by closing the INPUT, not the guard: the
shipped Phase-5 invocation now passes `--project "$(pwd)"`, `Path.cwd()` is no longer an identity
source, and `_resolve_identity` refuses rather than guesses. The recorded lesson — *"a truthiness guard
that only fires on DEGRADATION is structurally blind to MISATTRIBUTION"* — is **still literally true of
that guard** and always will be; it simply cannot be reached any more. A future re-opening of the
identity source re-creates the silent arm behind a guard that still will not fire. Recorded, not built
against: hardening a display guard for an unreachable input is building ahead of evidence.

### Fixed here

1. **`try_acquire` bypassed an `acquire` override's policy** — `control_plane.py`. ⚠ **Not closed, and
   cannot be**: closing it needs the `blocking=` keyword whose breakage is the reason `try_acquire`
   exists at all. What changed is that the convention is now a **pinned contract** rather than a
   comment: `_take` is the single flock path and the ONE policy hook, so a subclass narrowing
   acquisition there is consulted on **both** public forms. A reviewer reproduced the hole in both
   outcomes (free → `True`, busy → `False`, override consulted **zero** times); the subclass census
   confirms exactly two `class .*FileLock` definitions on the PRE-fix tree (the base and the suite's
   `_Boom`), none in production, and no dynamic subclassing. ⚠ A lens caught this sentence counting
   the wrong tree: **this PR adds a third** (`_Policy57`, the `_take` pin below), so the count was
   false the moment the entry shipped — a self-refuting census inside the item that ships it.
2. **`release_locks` could strand locks** — `control_plane.py`. `except ImportError` beside `flock`
   caught only that class, so an `OSError` out of `LOCK_UN` propagated out of a **cleanup path** and
   aborted the LIFO walk. ⚠ A review lens measured this and found the note here **understated** it:
   not one lock stranded but **two** — the domain lock *and* the **global** lock, the fleet-wide one
   every writer blocks on — and the escaping cleanup exception **replaced** the acquire error, so the
   caller was told the wrong cause. Post-fix all locks free and the caller sees the original error.
   Fixed at both enforcement sites — the primitive raises for no `flock`/`close` failure, and the
   walk steps past a failing release — because the invariant is "a rollback frees everything it
   took", and fixing only the primitive leaves it hostage to any future lock type that can raise.
   ⚠ The primitive's catch is `ImportError`/`OSError`, which is *every* failure `flock`/`close`
   produce on a valid fd — **not** a bare "never raises": a `ValueError` out of `fileno()` would
   still escape, no route in this tree reaches it, and the docstring says so rather than over-claiming.
3. **`cm doctor` could not name its own skipped cache write** — `cm_ops.py`. Its `run_and_cache` call
   sat in **statement position**, so the reason token returned since v0.4.56 was discarded: the one
   decline site that could not explain a cold cache, on the command the preflight note sends users to.
   Now `--verbose` names it, and the sentence comes from **one constructor**
   (`preflight.cache_skip_note`) shared with `cm status`, so the two sites cannot drift into
   disagreeing about what the same cause means.
4. **An unguarded `_mp.stat()` aborted the suite before a control could redden** — `tests/smoke.py`.
   The expression sat ~10,500 lines upstream of the v0.4.56b control, so the "never rebuild" mutation
   — the very mutation that control names — killed the run with `FileNotFoundError` and **no totals
   line**, taking the self-counting D6 pin with it. A check expression must be **TOTAL**: it evaluates
   to `False`, it does not raise.
5. **`warn_unenrolled_share`'s docstring promised more than the code keeps** — `store_context.py`. It
   said the warning prints "ONCE per store"; since the v0.4.56 try-write it is once per store **once
   the flag can be written**. Under contention it prints again — the documented safe direction, but a
   docstring stating a stronger guarantee than the code is the defect.
6. **`lock-busy` had no classifier** — `facts_manifest.py`. The v0.4.45 pin reads reasons off
   `_miss(...)` calls **inside `load()`**, so a token **minted in `ensure`** was structurally invisible
   to it: a fifth consumer could read it as durable with nothing catching that. The first cut of this
   module's own comment said the token is "deliberately in neither tuple" — true, and not enough. Not
   being **mis**-classified is not the same as being **classified**. `_ENSURE_REASONS` is the second
   vocabulary, it names each token's **transience**, and `_mint` enforces membership at the producer
   exactly as `_miss` does for `load()`.
7. **`cm data facts-refresh <DIR>` acted on the CWD** — `cm_ops.py`. The `show` positional is
   meaningful for exactly one `data_cmd` and was **silently accepted** for every other, so a trailing
   PATH bound to it, `--project` stayed at `.`, and the command did the wrong thing to the wrong store
   while looking like it worked — it misdirected a reviewer's own first measurement onto domain
   `unknown`. Now a usage error at **exit 2** naming the spelling that works (`--project`), because a
   refusal must carry the remedy its caller actually needs.
8. **`session_beacon.py` read stdin to EOF** — `json.load(fp)` is `loads(fp.read())`, so an OPEN pipe
   with no writer blocked **indefinitely with no output**, which on a release whose theme is locks
   reads as a **lock wait** — the wrong diagnosis of the right symptom. Now a bounded read
   (`select` + `os.read`, stop at a deadline). ⚠ The shape that isolates it is a pipe passed as
   `stdin=`; `sleep N | python3 X` does **not**, because the pipeline makes the *shell* wait for
   `sleep` — a confound this patch paid for once.
   ⚠ **Two corrections the second lens forced, both in this patch's own claims.** (i) The first cut
   said this "lands on the `cm beacon` debug path" — it does **not**: the `cm` wrapper is
   byte-identical and already redirects (`exec python3 session_beacon.py </dev/null`), measured at
   rc=0 / 0.055 s on the **pre-fix** tree. The exposure is a **direct script invocation**. (ii) The
   bound is a **trade, not a free win**: the first cut's 0.35 s window DROPPED a payload written at
   t = 0.40–0.60 s (0/3, 1/3, 0/3 across reps) and truncated one straddling the deadline mid-JSON,
   swallowing the error into `{}` — and a dropped payload is **indistinguishable from "no stdin"**,
   so it is silent by construction. The window is now **1.0 s**, sized to the hook's own 2 s budget;
   the residual is stated, not hidden.
9. **An unbound citation** — `docs/budget-trajectory-early-warning.spec.md`. The beacon's gate cite
   `session_beacon.py:84-86` was correct at the doc's CREATION revision (`633b2fb`) and was **missed by
   the `1d20166` sweep** that re-anchored **68 lines of that very file** and contains **zero**
   `session_beacon` occurrences in its diff — so it mis-aimed under both coordinate systems, for two
   different reasons. Now a **greppable anchor** (`if not missing and not stale:`), the durable form
   this repo prescribes, with the history recorded at the reading note. ⚠ The prose analysis in
   `prose-tied-to-the-tree.spec.md` § Family 4 — *"binding is the entire repair"* — is **not gated** — ⚠ **CORRECTED in v0.4.59: it WAS gated**, since v0.4.37, as
   `tests/smoke.py` pins 6/7a/7b/8/9. The belief that it was unshipped is what made v0.4.59's first
   cut build a duplicate of it; the cite below was still fixed by hand, but because the existing gate
   verifies RANGE and not content, not because no gate existed.
10. **A `cwd-invariance` claim that was false, in `render_html.py`** — the comment named TWO fields
    falling back to the cwd template (`registry_state`, `plugin_data_dir`) and concluded invariance;
    `store_context_from_registry` falls back on **FOUR** (`project_root`, `session_dir`, `project_id`,
    `display_name`). Corrected, and the correction names all four **by name** rather than by line
    number.
11. **A wrapped anchor in `CLAUDE.md`** — the inline span `` `claude plugin validate
    ./plugins/consolidate-memory --strict` `` spanned a line break, so a contiguous grep returned
    **0**. A one-line token move makes it greppable. ⚠ The contiguity gate (`check_contiguity`) exists
    and is **README-scoped**; extending it to the always-loaded files is a scope decision with a
    measured population behind it (382–534 wrapped spans across `docs/`, matcher- and scope-dependent),
    so it is deliberately not widened here.

### ⚠ Found by the review, and fixed here: the positional class has SIBLINGS

The `cm data` fix above was one parser. A lens swept every `add_subparsers` block and found **4
parsers / 8 silently-accepted choices** — each uses a flat `choices=[...]` sharing ONE set of
positionals, so a positional is accepted for every choice and read by only some. `cm project show`
is correct (its positional is meaningful for all its choices), so the defect is **per-parser** and a
CLI-wide fix is not available.

The worst is strictly worse than what this entry led with — a **wrong-project WRITE**, measured:

```
cwd=projA(alpha)   cm local rebuild-index <projB> --apply --confirm rebuild-local-index
  rc=0   projA/MEMORY.md  bba5e93c -> 2d46da45   <-- REWRITTEN (the WRONG project)
         projB/MEMORY.md  4c3e28a0 -> 4c3e28a0   <-- untouched (the NAMED project)
```

`cm local rebuild-index|migrate-schema` and `cm canonical catalog` now refuse a stray exactly as
`cm data` does (exit 2, naming `--project`). The remaining four (`cm journal` ×3, `cm group` ×2)
cost only an ignored argument — plugin-data is global and `cmd_group` hardcodes its ctx — so they are
**recorded, not guarded**: a guard there would be noise without a wrong subject to prevent.

⚠ **And a THIRD enforcement site of the `LOCK_UN` class, untouched.** `preflight.py` bypasses
`FileLock` with raw `flock`, so `_take` never reaches it — and there the failure mode is worse than a
silent cleanup: it is a **manufactured verdict**. A faulted `LOCK_UN` becomes a false
*"N HELD lock file(s) — another process holds the plane; wait or investigate"* advisory, and the
sqlite probe reports a false `fail` with a disk-space remedy. Measured on both trees. This patch
justified itself by that exact rarity and fixed the two sites where it is silent; these two are
recorded as open, because a verdict-shaped fault is a different repair from a cleanup-shaped one.

### Measured

⚠ **Every `lock-busy`/`Transient` consumer was censused** by a review lens rather than assumed:
`cache_skipped` has exactly **one** consumer, `"lock-busy"` has **three** (all now gating on it
explicitly), and `try_acquire` has exactly **two** call sites. No other site maps a transient cause
onto a durable verdict.

Suite: **2329 passed, 0 failed** (was 2319). `mypy`, `docs_links`, `manifests` and the accumulation sim
all green.

## [0.4.56] — 2026-09-24

**Patch — `cm status` no longer hangs waiting for a writer. This is the defect 0.4.54 claimed to fix
and did not — and 0.4.56's own first cut repeated the mistake in a smaller way, which is recorded
below rather than quietly amended.**

### The defect, root-caused by stack dump

```
control_plane.py:1402  FileLock.acquire          -> fcntl.flock(fd, LOCK_EX)   [BLOCKING]
control_plane.py:1457  acquire_mutation_locks
control_plane.py:258   update_project_state
preflight.py:500       run_and_cache
preflight.py:578       run_for_project
memory_status.py:5663  main
```

Run `cm sync` in one terminal and `cm status` in another and the second **hangs indefinitely** —
the command a user reaches for to see what is going on is the one a running write blocks.

**Trigger condition, measured both ways:** it blocked **iff the preflight cache was cold** — no
`preflight` block with a UTC `at` younger than `preflight.FRESH_TTL_S` (3600 s). A fresh cache
returned early (`preflight.py:566-573`) and took **no lock**, which is why the hang needs *both* a
cold cache and a concurrent writer, and why it survived so long.

### The fix — the cache write TRIES instead of waiting

The write caches a verdict `run_for_project` has **already computed and is about to return**; the
verdict reaches the caller and `ctx["preflight"]` reaches the record either way. A cache that cannot
get the lock is skipped, not waited for.

- **`FileLock.try_acquire()`** — a new, additive method returning `True`/`False`; `acquire()` keeps
  its **exact original signature** and still waits. ⚠ This is a correction *within* the release: the
  first cut added a `blocking=` keyword to `acquire` instead, and that broke the class's
  substitutability — a subclass overriding `acquire(self)` raises `TypeError` the moment a caller
  passes the keyword, i.e. at the *call site*, arbitrarily far from the override that caused it.
  This repo's own smoke fixture hit it immediately (mypy's override check caught the subclass, which
  then had to be widened **and** had to accept the keyword without forwarding it, because forwarding
  is a `TypeError` on the other tree). A new method breaks nobody: a subclass that never heard of it
  inherits correct behaviour. **`LockBusy`** (kept distinct from `WriteRefused`: this means *try
  later*, that means *never*) is raised by `acquire_mutation_locks(..., blocking=False)` and by
  `_take(wait=False)` beneath it; the no-`fcntl` path is unchanged in **both** forms — it still
  refuses via `require_interprocess_lock` rather than silently succeeding because waiting was not
  needed.
- `acquire_mutation_locks(..., blocking=True)`, `update_project_state(..., blocking=True)` — threaded.
  ⚠ **No new cleanup was needed**: the existing `except Exception: release_locks(locks); raise`
  already frees a partly-acquired set, so declining on the *global* lock leaves the *domain* lock
  free. A unit pin holds that property rather than trusting it.
- `preflight.run_and_cache` — tries, returns a **reason token** (`""` = written) instead of a bool,
  so the caller can tell *lock-busy* from *the write failed*. `run_for_project` carries it as the
  additive `cache_skipped` key.
- **`--verbose`** names the skip (`preflight: cache not written (lock-busy) — the verdict is
  unaffected`). Silent by default: the command succeeded and the cache is an optimization — the
  no-silence rule this arc enforces is about **refusals and faults**, not about declining one. ⚠
  `--verbose` is the first verbosity flag here and is **mode-neutral**, so it is deliberately NOT in
  the read-only-mode exclusion list that decides *which modes write*.

### ⚠ The frame the first cut MISSED — the facts-manifest rebuild

**The preflight cache was not the only `global.lock` taker on a read command, and this release's
first cut asserted that it was.** `cm status` still hung. Second stack dump, same method:

```
facts_manifest.py:436  _rebuild_locked      -> fcntl.flock(fd, LOCK_EX)   [BLOCKING]
facts_manifest.py:436  ensure
sync_global.py:861     _admissible_records
sync_global.py:1165    iter_canonicals
memory_status.py:3702  build_context
memory_status.py:5646  main
```

The trigger is a **second** cold-cache condition, independent of the first: an **enrolled** project
whose **facts manifest** is cold, with `global.lock` held. The fix is the same discipline at the
same kind of site — the rebuild protects a *cache*, so it **tries and never waits**:
`_rebuild_locked` calls `try_acquire()` and returns `(None, "lock-busy")` on contention, and the
caller falls back to the full enumeration the cache exists to skip. Every `ensure` caller already
had that fallback.

⚠ `"lock-busy"` is deliberately in **neither** `_REBUILDABLE` nor `_NONREBUILDABLE`: those two
tuples classify the reasons `load()` returns, and this token has a producer in `ensure`. Filing it
among them would repeat the defect that removed `"rebuild-failed"` — a member whose producer lives
somewhere else.

⚠ **Why nothing caught it, stated precisely:** every v0.4.56 pin used an **unenrolled** fixture, so
`ctx.canonical_domain_dir.is_dir()` was false and `_admissible_records` skipped the manifest
entirely. The suite was fully green while the defect survived. A fixture that cannot reach the
branch is not a weak pin — it is a pin about a different code path.

Measured on that fixture, this release vs. the first cut:

| | first cut | here |
|---|---|---|
| `global.lock` held, cold manifest, drained for 25 s | **rc 124 (hung)** | **rc 0 / 0.15 s** |
| manifest written, contended | — | **no** (declined) |
| manifest written, uncontended | — | **yes** (warmed) |

The last row is the one that separates this repair from 0.4.54's: `may_rebuild=False` also stopped
the hang, by **never rebuilding at all** — which is what cost ~100× on every read. This declines the
*wait*, not the *write*.

### ⚠⚠ And a THIRD taker — found by a census of the wrong set

**After fixing the second site I enumerated every `.acquire()` in the tree, classified all six, and
declared the read path clean. That was the wrong instrument.** A review lens instrumented
`FileLock._take`/`try_acquire` and swept **22 read commands** under a held `global.lock`; it found
one more, and — usefully — the boundary of the set: **zero** blocking takes anywhere else.

```
store_context.py:98  warn_unenrolled_share -> update_project_state(blocking=True, the default)
  <- control_plane.py:270 -> acquire_mutation_locks -> glob.acquire() -> flock(LOCK_EX)
  reached by render_html.py:803 (`cm report`) and sync_global.py:1934 (`cm sync --list`)
```

`store_context.py:98` contains **no `.acquire()` at all** — it calls `update_project_state(...)` and
the blocking happens four frames down. A grep of the primitive answers *"where is the lock **taken**?"*;
the question was *"what is **reachable** from a read command?"*. Precondition: an **unenrolled**
project whose native marker exists — which a plain `cm status` mints — plus a concurrent writer.
Measured by that lens: `cm report` rc 124 and `cm sync --list` rc 124 at 10 s. Re-measured here
after the fix, each against its own uncontended control rather than against a constant:
**`cm sync --list` rc 0 / 0.08 s** (was rc 124), and **`cm report`'s rc is UNCHANGED by the lock**
(contended 0.06 s / uncontended 0.08 s, both rc 1 — this fixture's report genuinely returns 1, so
"it did not time out" would have been satisfied by a command that had started failing).

The fix is one keyword: the write records the *once* flag — a cache of a decision
`is_unenrolled_share` has already made — so it takes `blocking=False`, and the `except Exception`
already there routes `LockBusy` to the documented safe direction (*print the warning again*; a lost
once-flag costs a repeated line, a wait costs the command).

⚠ **The miss, not the site, is the lesson.** Two successive sole-claims — "the only lock on a read
command", then "all six sites, read path clean" — were both answered by an instrument that could not
see the complement they asserted about.

### ⚠ What the review round corrected in this release's own work

Two independent lenses reviewed the committed revision. Three findings fixed above; these are the
corrections to **this patch's own instruments**, which is where the arc keeps finding its real
defects:

- **A PIN of ours was a GUARD wearing the wrong name.** The LEAK check (does a give-up on the
  *global* lock release the *domain* lock already taken?) reddened pre-fix — but because its **probe
  called `try_acquire()`**, which does not exist on the revision before this one. It failed for its
  instrument's absence *while naming the property*. Re-probed with a version-agnostic raw `flock`,
  the domain lock **is free** on that tree: the rollback already worked, so the check is green on
  both and is a GUARD by definition. NINTH mislabelling on the arc; the probe is now
  version-agnostic and the label is honest.
- **`try_acquire` is NOT a full substitute for an `acquire` override**, and the first cut of its
  docstring said it was. It reaches `_take` directly, so a subclass that overrides `acquire` — this
  repo's own `_Boom` is one — has its **policy silently skipped** for the try path:
  `Boom.acquire()` raises on `global.lock`, `Boom.try_acquire()` returns `True` for the same lock.
  The TypeError half of substitutability is genuinely fixed (no caller hands a subclass a keyword it
  does not declare); the policy half is not, and cannot be without re-introducing the keyword. It is
  now **stated** in `_take`'s docstring as a hole rather than claimed away.
- ⚠⚠ **One of our own pins HUNG THE SUITE, which is worse than failing.** The `facts-refresh` check
  drove the probe **in-process** while the parent held `global.lock` — and `flock` has no
  same-process deadlock detection, so a second fd of the same file blocks **forever**. On this
  branch it passed (the rebuild now tries rather than waits); on both `18c79f4` and `main` the suite
  **froze at check 2286 with no totals line**. Every sibling in those blocks already shelled out
  under an explicit timeout; this one broke the pattern, and the cost was not a red check but the
  entire pre-fix measurement — a hanging pin takes the self-counting D6 counter down with it. Now a
  subprocess under a 30 s timeout, so pre-fix it is a clean 124 the counter survives.
- **A tenth mislabelling, of the ninth's exact shape.** The `v0.4.56b` `--verbose` check was labelled
  GUARD "sharing the pin's precondition" — a lens measured it **RED** on the revision preceding this
  one, which by the rule accepted one round earlier makes it a **third arm of that PIN** (the census
  is 3 PINs + 1 CONTROL, not 2 + 1 + 1 GUARD). Its stated mechanism was wrong too, in the same way
  the LEAK pin's had been one revision before: "pre-fix it reddens as the hang's rc 124" is true of
  `18c79f4` only — on this branch's own predecessor the red is *purely the note's absence* (rc 0),
  and on `main` it is rc 2 (`unknown flag: --verbose`). A parenthetical naming one of three reds is
  a claim about the tree you happened to measure.
- **A control's named mutation cannot be observed through the suite.** The `v0.4.56b` control is
  hand-discriminated (manifest 0→1 normally, 0→0 under a never-rebuild mutation), but that mutation
  aborts the run ~10,500 lines upstream at an unguarded `_mp.stat()`, so the suite never reaches the
  control to show it. The abort site predates this patch; it is flagged, not fixed here.

Confirmed sound by the same lenses: **no fd leak** on any `try_acquire` path (200 consecutive busy
tries → fd delta 0; the no-`fcntl` path raises rather than returning `False`), and the rollback
across six lock combinations — with one **pre-existing** residual they labelled as not this patch's
(`release_locks`' LIFO walk can strand locks if `LOCK_UN` raises).

### Deliberately unchanged

The three other `update_project_state` callers in `memory_status` (`:2327`, `:2560`, `:2664` —
`--stamp-marker`, `--justify-demotion`, `--justify-defrag`) are **write** commands and still **wait**:
a CONTROL asserts they are killed by the timeout rather than completing. `session_beacon.py` takes no
locks at all and reads the cache read-only, so it is untouched.

⚠ **Known cost, stated rather than discovered:** on a store whose windows never let the lock
through, the preflight cache stays cold and the checks re-run each time (the verdict is unaffected;
only the cache misses). `--verbose` makes that visible; it is not silent-by-accident.

⚠ **One decline site still cannot name its own skip, and it is deliberately left that way for now.**
`cm_ops.py`'s `cm doctor` call discards `run_and_cache`'s token, and `doctor` has no `--verbose`
(measured on this revision: with the lock held the token is `lock-busy` and `doctor`'s stderr is
empty at rc 0). This is a **silence, not a wrong verdict** — nothing false reaches the operator, and
the preflight verdict itself is unaffected — which is why it is recorded rather than fixed here.
Adding a verbosity flag to `doctor` is a new CLI surface with its own review; smuggling it into this
patch would be the larger error. ⚠ What makes it worth naming anyway: `doctor` is the command the
preflight note itself points users at, so the one place a user is sent to diagnose a cold cache is
the one place that cannot say the cache was skipped.

Measured both ways: against this release's **first cut** (the tree that fixed only the preflight
cache) — **2312 passed / 3 failed**, the three failures being *exactly* the new PINs below and
nothing else; here **2315 / 0**. The suite's pre-fix corpus needs a real `.git`: an archived tree
without one reddens the v0.4.37 history pins for the fixture's sake, not the code's.

## [0.4.55] — 2026-09-24

**Patch — 0.4.54's headline change is REVERTED. It did not do what it claimed, and it cost ~100×.**

The two review lenses that had not reported when 0.4.54 shipped came back afterwards. One of them
refuted the change this release was named after, by measurement.

1. **`may_rebuild=False` on Phase 0 is undone.** 0.4.54's entry says *"The lock is off the path
   entirely now"* and SKILL said *"a plain `cm status` cannot BLOCK on the global lock"*. Both are
   **false**:
   - **The wait only MOVED.** With `global.lock` held by another process, `cm status` still times
     out — re-derived here at **rc=124 after 20 s** — blocking at
     `preflight.run_for_project` → `control_plane.acquire_mutation_locks` → `glob.acquire()`,
     which is **unconditional** on every report/`--json` run. Pre-fix, `ensure`'s lock was a
     *second, conditional* acquisition; the unconditional one was always there and still is.
   - **The cost did not end.** *"while the cache is cold"* had no exit, because nothing routine on
     the read-only path rebuilds the manifest any more. MEASURED on a 3000-fact / 6.17 MB store:
     pre-fix `3.98 s` then `0.055 / 0.054 / 0.081 s` (manifest written); post-fix
     `6.52 / 6.25 / 6.48 / 6.46 s` with the manifest **never written** — **~100× the pre-fix
     steady state** — because Phase 0 pays **two** enumerations per run (the two callers never
     share a result; 6000 `_safe_read_text` calls for 3000 files).
   - **And it silenced a fault**: the oversize refusal — the one case the notice exists for —
     printed twice pre-fix and **nothing** post-fix, because `may_write=False` returns before the
     refusal can speak.
   A change that does not deliver its benefit, costs 100×, and hides a fault is a bad trade. ⚠ The
   lock-wait is a **pre-flight** property; it belongs fixed in `preflight`, not by starving the
   cache. That is the follow-up, recorded rather than papered over.

2. **Four fixes from the same round's other lens**, all in 0.4.54's own work:
   - the pull-refusal pin's span began at `if _werr:`, so neutering the **read** left it green —
     the arm's name claims *"READS its own refusal AND exits non-zero"* and only the second half
     was covered. Mutation-verified now (neutering the assignment reddens it).
   - a pre-fix parenthetical claimed *"the message printed and rc stayed 0"* — measured false;
     `main`'s `cm_ops` already returned 1, and what the coverage lens found green was the absence
     of a check, not a wrong exit code. Relabelled as key-absence.
   - the warrant's authoritative statement named **two** conjuncts where the code compares
     **three**; `st_ctime_ns` — the one that catches a restored-mtime edit — was the omitted one.
   - `CHANGELOG`/`SKILL` said *"a pin"* where the arm's own label and the D6 tier say **GUARD**.

## [0.4.54] — 2026-09-24

**Patch — six open items closed: three measured, two derived, one defect the review found in my own
earlier guard.**

1. **Phase 0 stops reaching the manifest rebuild.** `build_context`'s two enumerators now pass
   `may_rebuild=False`, threaded through `facts_for_context` and `iter_canonicals`. SKILL declares
   *"Phases 0, 2, and 3 are read-only investigation"*, and the hazard the review named is not the
   write but the **wait**: `ensure` rebuilds under `global.lock`, so a plain `memory_status` /
   `cm status` could block on a concurrent `cm sync`.
   ⚠ **REVERTED IN 0.4.55 — see that entry.** "The lock is off the path entirely now" was FALSE:
   the wait only MOVED, to `preflight`'s unconditional acquisition, and `cm status` still times out
   with `global.lock` held. The change bought nothing measurable and cost ~100× on a large store,
   so it was undone rather than kept for its stated reason.
   ⚠ **Measured, not judged** — which is what this item lacked. Phase 0 already writes: a bare
   `--json` run creates `locks/{global,domain-*,project-*}.lock` and `.consolidation-state.json`.
   So the claim is not that the phase is otherwise write-free; it is that the manifest is the one
   write that *can* be avoided, at the cost of a full enumeration while the cache is cold.
   Verified after the change: **no manifest written**, warm Phase-0 wall time **0.15 s**.

2. **`cm data facts-refresh` now has its EXIT CODE pinned** — the last of the six coverage holes.
   Factored as `_facts_refresh_probe` so the code is reachable without enrolling a project. A
   coverage lens measured that deleting the `return 1` left both suites green: the documented repair
   printing "did NOT rebuild" and exiting **0**, reporting success on a cache that can never
   rebuild. ⚠ The healthy arm was first written with a REAL fact because of a BUG the review then
   found and this same patch fixed: `ensure` read a successful empty rebuild (`files: []`) as
   falsy → `rebuild-failed`, so a zero-fact domain exited 1 for the wrong reason. **Stated in the
   past tense deliberately** — the review fixed the mechanism, and a present-tense sentence here
   would assert a property the code no longer has. A PIN now covers the empty case directly.

3. **The cached row's TWO-PART warrant is now stated, and its other half pinned.** A review lens
   asked whether `load()` re-derives `secret`; it does not, and *"an identity match is the whole
   warrant"* is true of **`load()`** and false of the **system**: the warrant is *(predicate
   unchanged)* ∧ *(file unchanged)* — the first enforced in `load`, the second in
   `sync_global._consider_fast`, because only the consumer holds the `DirEntry` stat that makes the
   warm path warm. ⚠ Re-deriving `secret` is **not** the repair: every row field comes from the
   same read, so checking one means re-reading, which is the cache. What was missing is the
   statement (now `load`'s docstring) and a **GUARD** on the half that is easy to lose — the word
   is deliberate: the stats check shipped WITH the manifest, so the arm cannot redden pre-fix, and
   the arm's own label and the D6 tier say GUARD. ⚠ An earlier cut of THIS sentence said "a pin",
   which the review flagged as the label drifting from the thing it describes.

4. **A defect the review found in my own earlier guard.** `_execute_pull_writes` returns an `error`
   key when it declines to write without a revision precondition — and the caller read only
   `pulled`/`refreshed`/`fat`. So `cm sync --pull --allow-net-grow`, **one of the two remedies the
   ceiling hold's own message prints**, reported `pulled 0 · refreshed 0` and exited **0**: a
   swallowed refusal, indistinguishable to a script from "nothing to do". The stderr line named the
   repair; nothing carried it to the exit code. This is the item I listed as *"never drove it
   end-to-end"* — driving it is what found it.

5. **`v0.4.45`'s CHANGELOG attributed a comment to the wrong release.** It cited *"the previous
   patch's own comment"*; `git log -S` plus `git tag --contains` put the comment in `e868ecd`, which
   ships in **v0.4.45** itself. DERIVED, not adopted from the lens.

**Review round (two lenses returned before merge; both found real defects, most in code THIS
patch added):**

- **A permanent FALSE RED in `_facts_refresh_probe`** — the helper this patch introduced. `ensure`'s
  `if rows:` read a *successful empty* rebuild as failure (`build()` returns `[]`, the manifest is
  written as `{"files": []}`, and `{}` is falsy), so `cm data facts-refresh` reported permanent,
  **unclearable** failure with a **blank cause** on the state every project is in right after
  `cm project enroll`. Found independently by two lenses. Fixed at the root and in the probe;
  `rebuild-failed` removed from `_NONREBUILDABLE` as now genuinely dead.
- **`cross_project_allowed` conflated a FAULT with a VERDICT at three sites.** An unenrolled
  project is supported; an unhealthy registry is a fault, and both make the same predicate false.
  The pull printed one message for both and returned **0** (measured: a corrupt `control.sqlite`
  → `('corrupt', 'file is not a database')`, rc 0); `--harvest` was the twin; `gc` went further and
  asserted *"present but empty (no canonical facts)"* — a definite claim about the store's
  **contents** the code never established. All three name the cause now; the fault exits 2.
- **A crash spelled as an entitlement verdict, driving a DELETE.** `_classify_frozen`'s
  `except Exception: admitted = False` fell through to `("not-entitled", …)`, which `gc()` prints
  as *"member removed / not admitted"* and **deletes** under `--gc --apply`. "Could not tell" is
  not a licence to delete: it leaves the mirror alone and names the fault.
- **A fabricated dangling count.** `_gdirs`'s swallow published a number the instrument could not
  compute — measured, a resolvable `[[sharedfact]]` link went 0 → 1 dangling and `maintenance.work`
  False → True. The fault is now recorded and carried through the TypedDict and the seed, because
  `dangling: 0` alone cannot be told from a clean store.

6. **"four frames down" was off by one in two of four sites.** Counted: `main`(0) →
   `iter_admissible_facts`(1) → `_admissible_records`(2) → **`ensure`(3)** → `_rebuild_locked`(4).
   ⚠ **Corrected:** the first pass claimed `facts_manifest.py`'s copy "names the *write* and is
   correct" — it does not. Its own parenthetical terminates at `ensure` (frame 3) while the
   sentence says four, so **all three** named sites were off by one, and the site declared correct
   was the one not re-read. Its line number was also stale (`:387` → the sentence had moved). Both
   fixed, and the citations now use greppable phrases instead of line numbers, because a citation
   inside the file it cites goes stale on the next edit to that file. Both now say three and name the fourth explicitly.

## [0.4.53] — 2026-09-24

**Patch — the beacon's fault path gets the behavioural arm 0.4.52 shipped without.**

0.4.52 added three coverage guards and **stated rather than faked** that one of them — the beacon's
fault path — had only a **structural** arm: it asserted the call and the sentence's source, and
could not prove the sentence fired. I built the behavioural fixture and measured that
`_store_gaps` returned `(0, 0)` for it, so `beacon_line` short-circuited at
`if not missing and not stale: return ""` and any assertion would have read an empty string.

⚠ **The fixture turned out to need no padding at all, and that is the point.** The v0.4.10 sibling
pin has to pad its index to *one token under the ceiling* to observe `held` at all. Here the fault
supplies that condition for free: an unreadable index seeds `INDEX_CEILING_TOKENS + 1`, so **every**
admitted item is ceiling-held. What the fixture did need was a fact that survives `is_relevant` +
`admit_cross_project` — a list-universal canonical admitted through a granted group.

The arm is now behavioural and carries a **CONTROL**: the same fact under a *readable*, empty index
is **not** held, so the arm measures the fault rather than a fixture that is permanently over the
ceiling.

⚠ **And it is a GUARD verified by MUTATION, not a PIN** — the routing shipped in v0.4.46, so **no
shipped revision lacks it** and no revision-based pre-fix measurement can redden this. The two
conjuncts were each mutation-tested **separately**, one fresh copy apiece: reverting the seed alone
→ 1 red; dropping `_fault` alone → 1 red. A two-conjunct assertion whose halves are not
individually checked is how a vacuous half hides, and this arc has already shipped one CONTROL
whose second half passed pre-fix by construction.

## [0.4.52] — 2026-09-24

**Patch — the coverage holes a mutation lens found: three behaviours shipped in 0.4.46–0.4.49 whose
MUTATION left both suites green, and the archive check that was reading its own comment.**

A coverage lens did not read the code — it **mutated** it, one behaviour at a time, against a fresh
copy, and reported every change that left `smoke` (2289) and `browser` (1340) both green. Three
were real:

1. **The beacon's `_pull_index_seed` routing** — reverting `_idx_seed` to `est_tokens(idx_text)`
   passed. Every existing beacon pin runs on a **readable** index, where the two expressions are
   *identical*, so none could distinguish them: the same blind spot the pull's own wiring had.
   Measured consequence on a faulted index: `seed 3841 → 4`, so `held` empties and the line
   advertises a pull the ceiling would refuse.
2. **Both consumers of `_index_revision`** — `if _idx_err:` → `if False:` at the pull restores the
   exact v0.4.49 crash (uncaught `PermissionError`), and the gc's `return 1` is a verdict nothing
   reads. The helper was pinned; **neither call site was**.
3. **The oversize refusal's stderr notice** — removing the `print` passed. It is the sole place the
   offending file can be named, and without it the operator gets a permanently cold cache
   (measured 1.3 ms → ~1.4 s per call on a 300-fact store **holding one 5 MiB fact** — the file
   whose full read is the cost; the same store without it enumerates in ~40 ms) with no lead.

Plus the archive's `sections.js` exemption, which had **no test at all** — and the check written to
provide one failed twice, for two different reasons worth recording:

- `document.body.textContent` includes the bundles **inlined as JS**, so the first cut found the
  phrase *inside the comment explaining it* — this repo's own *"a text check reads prose about its
  subject"* trap, committed while writing a check about that very family.
- `#store-evidence` never carries the phrase at all (measured: it lives only inside the
  `<script>`). The observable is `#store-checks`'s **state chip**, which is what a reader sees.

⚠ All three smoke arms are **GUARDs, not pins** — every one is green on **both** trees, because the
behaviours already shipped and were simply never checked. An earlier cut labelled them PINs; the
pre-fix run falsified that. Their value is that **reverting** each behaviour now reddens, which
nothing did before. Measured: 2301 / 0 on both trees, and the D6 total reconciles on both.

## [0.4.51] — 2026-09-24

**Patch — the fault's POSITIVE verdicts, and four claims in the tests that measurement falsified.**

v0.4.45 stated a named exception for `prune_pressure`: *"falsy can only SUPPRESS an alarm, never
raise one."* A review lens executed it and showed the rationale was **stretched too far**. It holds
for `prune_pressure` **as an alarm**. It does not hold for what its falsy value *manufactures*
downstream — and a manufactured verdict is not a suppressed alarm.

1. **`NO-OP` is a positive assertion, and the fault created it.** The Phase-0 banner reads
   `tag = tier if (gc or prune_pressure) else "NO-OP"`, and `NO-OP` means *"reviewed, nothing
   changed"* — not the absence of an alarm. MEASURED: 3 facts + a 1504-tok index → banner `LIGHT`
   with `remediation.required True`; the **same** store with `MEMORY.md` a directory → banner
   **`NO-OP`**, `maintenance.work False`, `required` ABSENT — while the report's own STORES row
   three lines below said UNMEASURABLE. An unmeasured store has exactly one thing to do, so it now
   gets its own red tag (`FIX INDEX`) and `maintenance.work` counts the fault as work — that leaf
   is what a **script** reads.

2. **An unreadable fact body was scored as a fact MISSING its metadata.** `except OSError: text =
   ""` made an empty body, and an empty body is a **content claim**. MEASURED: one mode-000 fact
   carrying `node_type`, `scope` and `originSessionId` reported `missing_node_type` 0→1,
   `advisory_no_scope` 0→1, `advisory_no_origin` 0→1 — a drift finding the dashboard and the
   archive both render, and which steers the **backfill advisory into a WRITE** on a file nobody
   read. Skipped now, and counted as `unreadable_facts`.

3. **The dashboard printed a manufactured `index↔file` count** beside its own UNMEASURABLE row: an
   index nobody could open names nothing, so every fact reads as un-indexed. The archive already
   exempted this on exactly that argument; the dashboard did not, so **one of the two renderers was
   wrong**.

4. **`cm log` used `bool()` where every sibling renderer coerces.** `bool("false")` is `True`, so a
   MEASURED index whose leaf arrived as the string `"false"` printed `UNMEAS.` — in the file whose
   header promises *"all fields defensively read"*, on a model-authored record.

Also fixed: the nested-`CLAUDE.md` row still **vanished** on a fault (v0.4.50 made the hierarchy
*return* `unreadable`; the report and dashboard rows are gated on the very numbers an unreadable
file zeroes — the consumers had to read it); a comment claiming a `getattr(rd, "_unmeasurable", …)`
guard **that does not exist in the file**; a CONTROL whose second half passes pre-fix *vacuously*
(the call raised `TypeError` before it could write); a sibling PIN whose "healthy" half measured a
file the fixture had not created yet, so it tested *absent* ≠ *faulted* rather than *readable* ≠
*faulted*; and a D6 ledger term describing an arm differently from the check it counts.

Measured both ways: against the released 0.4.50 — 2295 passed / 3 failed; here 2298 / 0. Totals
reconcile at 2298.

## [0.4.50] — 2026-09-24

**Patch — the remainder of the adversarial run: five ways an unanswerable question was spent as an
answer, and the identity's last incidental barrier.**

Every item below is the same defect the previous four patches were about, found at a site none of
them had censused.

1. **The identity's protection was INCIDENTAL, not structural.** `load()` serves any row whose
   `secret_pred` matches, with no independent check of `secret` — so a truncated row with a valid
   identity is served end-to-end. What protected existing installs is that every pre-fix writer's
   identity happened to differ *for other reasons*: unstated, untested, and gone the moment the
   identity stabilises. `_READ_CAP` is now part of the payload, because **how much of each file the
   predicate sees is part of the predicate** — a row built under one cap is not evidence about
   another.

2. **`_is_archive_index`'s `except OSError: return False` spent "could not classify" as "is a
   fact."** MEASURED: `MEMORY.md` + one real fact + `adir.md/` gave `fact_files` length 2, which
   `seed_record` wrote out as `recall_facts.before/after`, and `schema_drift` reported
   `missing_node_type: 1` — a drift finding manufactured by a directory. A two-valued predicate
   cannot say *"could not tell"*; `classify_store_doc` now returns `archive` / `fact` /
   `unclassifiable`, and the third is counted as neither and **named**.

3. **`claude_md_hierarchy` swallowed the same condition**, so an unreadable `CLAUDE.md` vanished
   from the chain *and* from `total_files` — and the report's row is gated on those numbers, so an
   unreadable file that was the only one removed the whole row. It now returns `unreadable`.

4. **The nine consumer defaults.** `memory_status` states the rule at the producer — *"never
   `.get(k, False)` … A KeyError names the site; `False` hides it"* — and then did the opposite at
   **nine** consumer sites, every one defaulting to **healthy**. Latent, because the producer
   plain-indexes too; but the invariant lived at the producer, not at the consumers the comment
   claims enforce it. All nine index directly now, and a structural pin holds them there.

5. **`ensure`'s classification had a silent default.** A reason absent from both tuples still
   rebuilt — safe by direction, silent by construction. Every mint now goes through `_miss`, which
   **raises naming an undeclared reason** instead of letting it acquire `global.lock`.

6. **Two operator-facing messages named the wrong fault.** The post-state refresh said *"no
   MEMORY.md in the store"* when the file was there but unreadable — sending the operator after an
   absence. And `--evict` said a fact *"has no pointer line in the live index"* when the index
   could not be read at all; that message **is** the ceiling hold's own printed remedy, so acting
   on it means picking a different fact for a reason that is not true.

Measured both ways: against the released 0.4.49 — 2288 passed / 6 failed; here 2294 / 0. Totals
reconcile at 2294.

## [0.4.49] — 2026-09-24

**Patch — the archive's KPI strip, and the third site of the EACCES family.**

1. **The end-user archive's KPI strip and index meter.** `unmeasurable` reached the archive's
   **meter** in 0.4.46 but not its **KPI**, nor `idxTok` — the reader behind both the trajectory
   and the `idxTok(CUR)==null` block. So an index nobody could read still rendered a confident
   green `0% · index vs target · 0 / 1500` on the tile a reader scans first, and the trajectory
   forecast a breach from the failed read's zero. `idxTok` now returns `null` for an unmeasurable
   record, so `carryFwd` **carries the last real measurement forward**, and the `null` block — the
   one that **wins**, repainting both the KPI and `#m-index` hundreds of lines later — now tells
   *"could not be READ"* apart from *"not captured"*. Those are two different facts pointing at two
   different places: the **store** versus the **record**. ⚠ Handled in the block that wins rather
   than in the KPI builder, where an arm would have been silently overwritten.

2. **`gc` refused to write without a revision precondition.** The third site of the family
   `measure_or_fault` documents — *"`Path.exists` itself re-raises anything outside
   ENOENT/ENOTDIR/EBADF/ELOOP — EACCES among them"*: `is_file()` does not follow from `exists()`,
   and the hash reads bytes. It now uses the same `_index_revision` helper as the pull path and
   refuses by exit code rather than proceeding precondition-less.

⚠ **Both were found only because a lens tested the FIXTURE, not the code**: it mutated the
archive's `"fault"` meter sentinel to `false` and **both suites stayed green**, because no fixture
carried an `unmeasurable` key anywhere. The browser suite now builds a faulted page from the
sample record — a flag, not an extra cycle, since `#sel=N` is hardcoded at 22 sites with `7` as the
last cycle — giving the third state a behavioural arm (1340 checks, up from 1336).

## [0.4.48] — 2026-09-24

**Patch — a live firewall leak, a permanently-cold cache, and a crash on the escape path.**

1. **The commit-subject firewall's cap applied to the SCAN and not to the EMIT — a live leak.**
   `_scrub_commit_log` scanned `subject[:_COMMIT_SUBJECT_CAP]` and then appended the **whole** line
   in the `else`. So the firewall got **weaker the longer the subject grew**: MEASURED on the
   released 0.4.47, the same credential was redacted behind 100 filler characters and emitted
   **verbatim** behind 5,000 — `_looks_secret(subject[:4000])` `False` while
   `_looks_secret(subject)` `True`, with the credential present in the output of every Phase-0
   report. Emitting text you refused to *scan* is the defect; the cap now bounds both sides, and
   the truncation is marked so it stays auditable. This was the one Phase-2 source with a
   secrets-firewall pass, and it was bypassable by padding — against CLAUDE.md's *"don't weaken
   that"*.

2. **One oversize fact made the facts-manifest permanently cold, silently, and the documented
   repair restated a promise it could not keep.** `ensure` fails open past `_READ_CAP` and a failed
   rebuild writes nothing, so a domain holding one 5 MiB fact never rebuilt: MEASURED, a 300-fact
   store went from ~1.3 ms to ~1.4 s **every** call, forever, while `cm data facts-refresh`
   reported that it "rebuilds lazily on next read". The refusal now names the offending file on
   stderr, and `facts-refresh` **probes** the rebuild and reports the OUTCOME — exiting non-zero
   when it could not — instead of printing an intent.

3. **`cm sync --pull --allow-net-grow` died with an uncaught `PermissionError`.** `Path.exists()`
   re-raises anything outside `ENOENT/ENOTDIR/EBADF/ELOOP` (EACCES among them) and `read_bytes`
   raises on a mode-000 file, so an index that cannot be read took the write path out with a
   traceback — on one of the two remedies the ceiling hold **itself prints**. The read is now
   factored as `_index_revision`, guarded on both sides, and a revision that cannot be READ is a
   precondition that cannot be HONOURED: it refuses by name rather than writing without one.

⚠ Items 1 and 3 are the same escape `measure_or_fault` documents in its own docstring — *"`Path.exists`
itself re-raises anything outside ENOENT/ENOTDIR/EBADF/ELOOP — EACCES among them"* — reproduced at
two call sites written by the same hand in the same cycle. A documented trap is not a guarded one.

## [0.4.47] — 2026-09-24

**Patch — a crash 0.4.46 introduced, and four claims 0.4.46's own batch made about itself.**

1. **`Path.exists()` re-raises EACCES, and the new call site did not inherit the guard.** 0.4.46's
   `_pull_index_seed` reads `raw = _safe_read_text(idxp)` (which *swallows* `OSError`) and then
   `idxp.exists()` — which re-raises anything outside `ENOENT/ENOTDIR/EBADF/ELOOP`, **EACCES
   included**. So an index that cannot be read but whose `exists()` re-raises (a symlink into a
   non-traversable directory) raised **out of `cm sync`**: the call sits outside every `try` and
   outside the enrollment gate, so a plain `cm sync` **LIST** hit it. Measured `PermissionError` on
   3.8 and 3.12. ⚠ `measure_or_fault`'s docstring documents this exact escape and guards it; this
   call site — written by the same hand in the same cycle — did not. Cannot-tell is now spent as
   the fault, the safe direction. One true PIN, red on the released 0.4.46.

2. **A false guard comment, and a suite that ABORTED at the revision three comments name.**
   0.4.46 asserted "`_NONREBUILDABLE` needs no guard: it exists on both trees" — **false**; it
   lands in `e868ecd`, *after* `8db50a6`, the PR base three comments in that batch cite as their
   measurement. Against `8db50a6` the unguarded name raised `AttributeError` **at module scope**
   and the run died at check #2251: **23 of 28 new checks never executed**, including the D6
   surface pin, whose entire purpose is that an orphaned section cannot print green and which
   cannot help when the crash precedes it. So those three `8db50a6` citations cannot have come
   from a suite run at that revision. The guard is applied to both operands now.

3. **Four more self-descriptions corrected.** Two arms labelled PIN/CONTROL reddened pre-fix for
   **key-absence**, not for their stated claims — the same mislabelling 0.4.46 corrected three
   times elsewhere in the same block; both are GUARDs now, with the disclosure. A third described
   a directory fixture as "`is_file()` is true", which is false twice over (`is_file` does not
   follow from `exists`, and it is false for a directory) and contradicts the same batch's own
   comment a hundred lines above. And two coverage holes a mutation lens found are now closed:
   moving `kill-switch` between the classification tuples kept the structural totality pin green
   while **defeating the operator's kill switch**, and reverting `_pull_index_seed`'s **call site**
   kept the whole suite green while the net-grow hold flipped ON → OFF.

⚠ Items 2–3 are all the same shape: **a claim in the diff about the diff, falsified by running
it.** Three adversarial lenses found them after 0.4.46 shipped. The census has to be mechanical.

## [0.4.46] — 2026-09-24

**Patch — the two surfaces 0.4.45 left open, both named in its own carried-forward list.**

1. **The beacon's `held` advisory was the second site of the `_pull_index_seed` defect.** 0.4.45
   extracted the three-state read and routed `sync_global.run()` through it; `session_beacon`'s
   `beacon_line` kept `_safe_read_text(...) or ""` and failed **twice** from one unreadable index:
   seeding `0` made `held` come back `0`, so the line **advertised a pull the ceiling would
   refuse** — the exact harm its own note records, one paragraph above — and the same zero emptied
   `line_cost`, which drops every STALE-mirror item at the `elif cost_old and …`. Both halves of
   the payload were built from a failed read. It now reads through the shared helper, and the line
   says the headroom and stale tally are UNKNOWN rather than printing confident zeros.

2. **The HTML archive's remaining two meters.** 0.4.45 wired the archive's **index** meter and
   claimed the archive "says so"; the project-`CLAUDE.md` meter still drew a green
   `0% · 0/4.0k Within budget` from the fault's zeros, and the global row **vanished** — its
   visibility test was `truthy(gcm.present)`, which is `bytes > 0`, false for a failed read, so
   `#m-global` stayed at `display:none`. That is the vanishing-row harm this cycle headlines, on
   the surface an end user actually opens. Both now branch on the third state, and the global
   row's test is `present || unmeasurable`.

⚠ Both are the *same* defect class 0.4.45 was about — a value produced by a failed read spent as a
measurement — surviving in a caller the patch did not census. Two adversarial lenses found them
**after** 0.4.45's own review round had passed, which is the argument for the census being
mechanical rather than remembered.

**Still open** (unchanged by this patch, all measured): `_scrub_commit_log` scans the first 4 000
chars but emits the uncapped line, so a credential past char 4 000 of a long commit subject reaches
the model on every Phase-0 report (pre-existing since v0.1.70) · one >4 MiB fact disables the
manifest for its domain permanently with no operator signal and no working remedy · the pull's
refusal prints remedies that cannot clear it, one of which dies with an uncaught `PermissionError`
· `load()` serves any row whose identity matches with no independent `secret` check · the archive's
KPI and trajectory cells · `claude_md_hierarchy`'s swallowed `OSError` · an unclassifiable `*.md`
directory counted as a fact.

## [0.4.45] — 2026-09-23

**Patch — an operand that EXISTS but cannot be READ is a third state, all the way to the decision
layer; and a manifest read cap that was silently truncating the secrets firewall.**

The whole cycle is one defect class: **a value produced by a failed read being spent as a
measurement.** `store_local_index` returned `(0, 0, 0)` both for an empty store and for one whose
`MEMORY.md` could not be opened, and every consumer compared the bare number to a budget — so an
unreadable store answered "under budget" at every site that renders, decides, or gates.

1. **The fault reaches the DECISION layer, not just the record.** ⚠ Corrected after an adversarial
   review lens measured the shipped claim as false: `index_reading` carries the three states at its
   two call sites, both of them DISPLAY (`--triage` and the schema-drift advisory), and the report's
   index row and project-`CLAUDE.md` row — which the first cut of this entry did not count — now
   carry it too. The three gate sites (`prune_pressure`'s index arm, `remediation.required`,
   `over_ceiling`) deliberately do **not**: all three are falsy on a fault, which can only SUPPRESS
   an alarm and never raise one, and `prune_pressure`'s remedy ("you MUST prune") is the wrong
   answer for a file that cannot be read. They are now NAMED exceptions in the code rather than
   bare comparisons, and the fault reaches the operator through `--triage` instead. Detailed
   because the earlier sentence here — "no consumer can reach a default that spells UNKNOWN as
   healthy" — was stronger than the payload. `--triage` printed its green
   `✓ index under budget (0/1500 tok) — nothing to remediate` — verbatim the string THIS cycle's
   own comment named as the defect it was fixing — on the very surface SKILL Phase 5 reads
   to decide whether a pass runs HEAVY; `remediation.required` never fired, so the mandatory
   hard-stop went quiet; and the schema-drift advisory offered `backfill`, **the one action the
   no-net-grow gate forbids**, keyed on a budget comparison that read `0 > 1500` from a file it
   could not open. One shared expression (`index_reading` → `over`/`under`/`unmeasurable`) now
   carries the three states, so no consumer can reach a default that spells UNKNOWN as healthy.

2. **The manifest's read cap was a firewall bypass, not a truncation.** `build()` classified the
   first 4 MiB of each fact while the fallback reads the whole file and the warm-pull path
   deliberately skips its own re-scan. Measured on a 4,800,090-byte fact whose credential sits in
   the tail: `_looks_secret(whole)` is `True`, the cached row said `secret: False`, and the gate
   `if r.get("secret"): return` therefore did **not** return — so the fact was admitted
   cross-project into context. A file past the cap now **fails open** to full enumeration, which is
   the module's own stated posture ("can slow you down but never serves wrong facts").
   ⚠ Two honest limits, both from the adversarial round. (a) The committed fixture is **4,200,094**
   bytes; the 4,800,090 in the first cut of this entry was an uncommitted draft fixture, i.e. a
   re-derivable-by-hand number stated as measured. The mechanism was re-verified at the committed
   size. (b) The fail-open closes the **writer** side only. `load()` serves any row whose stored
   `secret_pred` matches, with no independent check of `secret`, so a pre-existing truncated row
   would still be admitted — what prevents that today is that every pre-fix writer has a DIFFERENT
   identity, which is incidental and untested rather than designed.

3. **The fault's sibling operands, and a row that VANISHED.** The project and user-global
   `CLAUDE.md` gauges had no fault field, and the global one's only unreadable signal was a stderr
   line: its `present` is `bytes > 0`, which a *failed* read reports as `False`, so every renderer
   **skipped the row** — the one operand that loads in every session of every project simply
   stopped being reported, which is worse than a wrong number because a missing row is
   indistinguishable from a row never warranted. Both budget blocks carry `unmeasurable` now; the
   Phase-0 report prints a red row instead of dropping one (for the project `CLAUDE.md` too, which
   the first cut of this patch missed while correcting its siblings); and the dashboard and the
   `cm log` table say so rather than drawing a full-green `0% · 0/1500`. ⚠ The HTML archive is
   wired for the **index** only — its project-`CLAUDE.md` meter and the global row's
   `present`-gated visibility still read the fault as a value. That is carried forward, not
   claimed, and an adversarial lens measured the earlier sentence here as false.

4. **The SessionStart beacon's read-only contract held one call deep.** `session_beacon` chose
   `load()` over `ensure()` deliberately, with a comment saying why — and was still defeated four
   frames down, because `iter_admissible_facts` → `_admissible_records` → `facts_manifest.ensure`
   rebuilds **under `global.lock`** for a missing or stale manifest. A hook documented as read-only,
   with a 2s budget, could take a lock held by a concurrent `cm sync`. `may_write` / `may_rebuild`
   now sit at the decision site, and a structural pin asserts the read-only caller asks.

5. **The pull's index seed: the same unknown, where it costs a WRITE.** `_safe_read_text` collapses
   ABSENT and UNREADABLE into `None` — right for the scan it was factored from, wrong for a gate:
   seeding `0` for an unreadable index reads as "nowhere near the ceiling", which **switches off the
   M1 hold** and lets a pull grow a store nobody could measure. Absent still seeds the truth;
   unreadable now seeds past the ceiling.

6. **The post-state refresh wrote two leaves from a fresh read and left the third at its seed.**
   `unmeasurable` qualified `after_tokens`/`over` but was not re-written with them, and the skip
   guard is `is_file()` — true for a mode-000 index — so an index Phase 0 read cleanly and which
   became unreadable by persist time wrote a healthy post-state over a failed read.

7. **The archive reader's read-failure posture diverged from the rebuild's.** `_archive_doc_paths`
   skipped an unreadable — or non-regular — store doc with a bare `continue`, so a doc that could
   not be *classified* was spent as "not an archive index": the upsert concluded the stem was never
   archived and **re-added a pointer an archive owns**, undoing an eviction. `_rebuild_plan` reports
   the same two conditions and fails closed; the readers now agree, the refusal is named, and it is
   clearable by repairing the store.

8. **The firewall identity's COMPLETENESS claim, made true.** `secret_pred` hashed `_SECRET`'s
   pattern *and* flags but `_BLOB`'s pattern alone; `<source-unavailable:…>` was a constant, so on a
   source-less install a body-only repair never moved the identity (measured: unchanged across an
   edit that flips `_looks_secret` on a source-present install). Both flag sets are hashed, and
   `__code__.co_code` is hashed beside `getsource` — always available, so it covers the frozen case
   `getsource` cannot, while `getsource` covers the constant-only edit `co_code` cannot.

Also: `except (OSError, TypeError)` around `getsource` missed `SyntaxError` from `getblock`, making
the marker fallback unreachable in exactly the mid-edit case it exists for; `_NONREBUILDABLE`'s
"classified by CONSTRUCTION" was an overstatement (totality is by *default*); two v0.4.44 comments
had been silently inverted by v0.4.45; and three comments claiming a sharing between
`_archive_doc_paths`/`_placements_from` and `_rebuild_plan` described a refactor that was never
done.

## [0.4.44] — 2026-09-23

**Patch — the three open items from the 0.4.42/0.4.43 arc: an archived fact's eviction survives a
body edit, a cached firewall verdict can no longer outlive the predicate that made it, and an
unreadable store degrades instead of crashing the report.**

1. **A body-only upsert no longer re-adds an archived fact's pointer.** `local_upsert` read only
   the fact file and `MEMORY.md`, never an archive doc — so after `cm local archive STEM` moved
   STEM's pointer out of the always-loaded index, a later bodied edit found no `](stem.md)` line,
   took `apply_pointer`'s append branch, and silently undid the eviction. `_rebuild_plan` has had a
   rule for exactly this harm (and a pin) since v0.4.32; the upsert path never got it. The check
   reuses the SAME reader (`index_admission.archive_index`, through the same
   `_is_archive_index_text` classifier) — a second archive reader is the divergence class this repo
   keeps closing. The body still updates and the disposition is **named**, in an additive
   `archived_placement` key: an archive is undone deliberately, never as a side effect of an edit.

2. **A cached `secret` verdict is bound to the PREDICATE that produced it.** The manifest's
   documented invalidation rides the transact choke point, which unlinks on a published or deleted
   PATH — and a firewall change moves no file, so every cached verdict survived the repair, on
   exactly the rows a repair never touches (the ones whose bytes do not change). Each row now
   carries `secret_pred`, a hash **derived from the predicate's own source**, and `load` fails open
   to a rebuild when it does not match. Derived, never a hand-kept version constant: forgetting to
   bump such a constant IS the defect, restated.

3. **A store the tool cannot read degrades instead of raising — and a GATE input that cannot be
   read is NAMED rather than absorbed.** `_measure` guarded with `exists()`, which a DIRECTORY and
   a mode-000 file both satisfy, so `read_text` raised `IsADirectoryError` / `PermissionError` out
   of the report path. The inline block this replaced carried both guards; routing through
   `_measure` dropped them. ⚠ Degrading alone was NOT sufficient and would have traded a loud
   crash for a silent false pass: `budget.claude_md.over` is `tokens > budget`, so an unreadable
   `CLAUDE.md` reading 0 renders as `over=False` and the over-budget warning VANISHES.
   `measure_or_fault` therefore returns the value **and** whether the operand existed but could
   not be measured, the three gauge operands use it, and a fault is named on stderr — while
   `_measure` keeps its value-only form for callers that merely display the figure (the store
   index, which is what the crash was reported against). Absent and unreadable are different
   facts and no longer share one number.
 `_measure` guarded with
   `exists()`, which a DIRECTORY and a mode-000 file both satisfy, so `read_text` raised
   `IsADirectoryError` / `PermissionError` out of the report path. The inline block this replaced
   carried both guards; routing through `_measure` dropped them. Refusing an OPERAND is a
   different posture (v0.4.41 R2 does that at the positional pool) and is left alone.

`tests/smoke.py` gains **9 checks tagged v0.4.44** — three pins with four controls — each RED on
`783cbde`.

**The explicit half of item 2** is `cm data facts-refresh` — it unlinks the manifest (or
`--all` for every domain) so the next load rebuilds, reusing `facts_manifest.invalidate_all` rather
than growing a second invalidator. The automatic half already covers a predicate change; this is
the lever for what that identity cannot see — a hand-edited store, a restored manifest.

**MEASURED, both trees.** Shipping: **2247 passed, 0 failed**. `783cbde` plus this patch's pins:
**2232 passed, 13 failed** — 7 v0.4.44 reds and the 6 preflight-beacon artifacts that redden in
every bare worktree measured this session. Running that measurement found **three defects in the
pins themselves**, each crashing the suite pre-fix from module scope by calling a symbol that does
not exist there; all three are guarded, and it is the third occurrence of that trap on this arc —
the first one a measurement rather than a review caught.

## [0.4.43] — 2026-09-23

**Patch — the review round that followed 0.4.42 found six defects in it, three of them regressions
introduced by its own fixes. This is the repair pass, each fix reproduced before it landed.**

1. **`--force` was a silent no-op.** `wf` — an operand of the WRITE path's own suppression test —
   was initialised to `0` ABOVE the `if not force:` branch and assigned from the builder only
   INSIDE it. So `--force`, the only remedy the refusal message prints, judged that test against
   zero: the stamp the remedy exists to move was never moved, the stem re-nagged every dream, and
   the command returned `ok: true` with an empty `stamped`. MEASURED. The vector is now built
   once, above the branch, and one source feeds both the gate and the write.
2. **The justify CLI reported a count it never measured.** The same `wf = 0` reached the
   early-error returns, so a store whose log held 39 probative windows printed `windows_full: 0`.
   The value is now derived from the same vector on every path, and a builder fault degrades to
   the log's own aggregate — a measured count, never a fabricated zero.
3. **`cm local rebuild-index --apply` re-inflated tightened cues.** The D3 keep reached the
   rebuild's EVALUABLE branch only; the D1c route — reachable exactly for facts whose body the
   firewall refuses, and living ONLY in the rebuild — still derived unconditionally (MEASURED
   +25 est tok per refused fact). So the single write that heals a frozen cue was also the one
   that re-inflated the tightened ones, in the same pass. The route now takes the keep's
   operands, with controls asserting it did not become a bypass.
4. **Two prose repairs.** The `0.4.42` section claimed **18** checks; the shipped suite has
   **28** — a pre-review-round figure the round outgrew. And three new prose sites named private
   memory-fact slugs, which resolve to nothing for any reader of this public tree; each is now
   stated inline, and the measured span is described rather than named.

⚠ **A known, unfixed surface, stated rather than discovered later:** routing the justify CLI
through `store_local_index` means an index that is a DIRECTORY or mode-000 degrades through the
new fallback rather than raising, but the same read is unguarded for the report path — a surface
that has existed since v0.4.30, not a regression here.

## [0.4.42] — 2026-09-23

**Patch — three defects a dream pass measured in its OWN tooling: a secrets-firewall false
positive and the index cue it froze, a demotion docket that named candidates its own gate
refused, and a body-only edit that silently inflated the always-loaded tier. No `CycleRecord`
field, CLI flag, or manifest contract changes.**

One shape, three instances: **a derived artifact or a consumer disagreeing with the thing that
produced it** — a firewall verdict against a body's real content, a docket against the gate that
reads it, an index cue against its own cost. Design-of-record:
`docs/producer-consumer-parity.spec.md`. Ships as two PRs.

1. **The CLI-flag arm's dash must INTRODUCE a flag.** Its signal is a bare leading dash, and its
   keyword alternation ends in short common English nouns (`pass`, `secret`, `token`, `cred`)
   that are ordinary English as a compound's **final element**. Both measured false positives
   have the dash preceded by a **word character** — `audit-pass`, `vs-secret` — i.e. a hyphen
   inside a compound, not a flag introducer. A negative lookbehind closes both with **no recall
   loss**: a real flag's dash follows start-of-string or whitespace.

2. **A compound-id constant assignment is not a keyword credential.** In
   `ms.INDEX_TOKEN_BUDGET = 1600`, `token` matches as the **middle segment** of a SCREAMING_SNAKE
   identifier, and the value gate's digit branch admits a bare integer. The match is now declined
   when the value is 4–7 characters **and** purely numeric **and** a `[_.-]` segment **follows**
   the keyword. Suffix-only, not "prefix or suffix": a prefix-only match is the env-var shape
   (`MY_TOKEN=1234`), which is a real secret worth catching. This is an **accepted gap** in the
   sense `_entropy_blob`'s docstring already establishes — *"the firewall favors fewer false
   positives on ordinary commit prose… Widening it is a product decision, not a fix."* It is
   documented in `_SECRET`'s comment and pinned in the accepted-gap block.

3. **Why (1) and (2) were a BUG and not a preference.** The always-loaded index pointer is
   **derived** from `description:` by `local_ingress._pointer`, and every pointer-producing path
   ran `prepare_local_fact`, which validates the **whole body** — so a firewall verdict on a body
   blocked an unrelated concern. Measured on the maintainer's own store: a fact whose BODY read
   **v0.4.40** while the `MEMORY.md` pointer derived from it still read **v0.4.34** — frozen
   across six releases, because no write path could regenerate the cue and nothing compared body
   to cue. (The fact is private and uncommitted, so the span is described rather than named: a
   slug from that store is a citation no reader of this tree can resolve.) `_pointer_from_clean_description` now derives the cue when the body is
   refused **by the firewall** and the description is clean; `_rebuild_plan` uses it instead of
   failing closed, reporting the fact in a new **additive** `body_refused` key. It admits no
   BODY — a secret in a body still blocks every content write. The recursion is worth recording:
   the fact documenting this was itself refused when the correction was written into it, **twice
   in one pass**, because its own trigger is prose.

4. **The demotion docket and the demotion gate now read ONE input builder.** They used to
   assemble their inputs separately: the Phase-0 report overrode `windows_full`/`window_starts`
   from `usage_window_clock(ctx)` and derived `index_names` from the real index, while
   `run_justify_demotion` passed `usage_history()`'s own values and `index_names = {p.stem for p
   in facts}` — **every** fact file, indexed or not. Isolating each input showed `index_names`
   moves `eligible` (11→8) but **not** the candidate set, while `hist` **changes the set**:
   measured `usage_history().windows_full` = **39** against the clock's `probative` = **23**, and
   the clock's field is the one `demotion_candidates`' docstring means. Harm: the report's
   `demotion.surfaced` named stems the gate then refused as *"not a current demotion candidate"*,
   whose only printed remedy was `--force` (labelled administrative repair) — the counter-justify
   route the cycle record prescribes could not be applied to the facts it named.
   `demotion_inputs(ctx)` is now the single source for both.

5. **A body-only edit no longer inflates the always-loaded tier.** `local_ingress._pointer`
   re-derived the cue on every write, so a line a human had tightened below what `_fit_hook`
   produces was **re-inflated by any edit to the body** — measured **+62 est tok across five
   facts** in one pass, then **+31 across two more**, all of it on the tier paid every session,
   with nothing comparing the old cue to the new one. The cue is a function of `description:`
   alone, so it is now re-derived **only when that field moved**; the comparison is on the
   description, never on the lines, because comparing lines cannot tell *"the description
   changed"* from *"someone tightened the cue"* — and a moved description is exactly the
   frozen-cue repair (3) exists for.

`tests/smoke.py` gains **28 checks tagged v0.4.42** across the two PRs — MEASURED on the
committed tree (the D6 surface constant's own breakdown adds `+ 22` D1-family and `+ 6`
D2/D3 = 28); an earlier draft of this entry said 18, a pre-review-round figure the round's
pins outgrew and which a reviewer auditing the released suite could not reconcile. **MEASURED, not
asserted:** on a `git worktree` of `3ada6c7` carrying this release's pins, the suite reads
`2202 passed, 14 failed` for PR 1's pins and the shipping tree reads green; the pre-fix reds are
enumerated in the spec's §3 with each check's kind (PIN vs **GUARD** — a check that cannot fail
on pre-fix code is labelled a guard, not counted as a pin). Two pre-existing `RC-1c` checks were
**re-aimed, not deleted**: one asserted the fixture *"really does trip the firewall"* using
`` Use `--token <value>` `` — the false positive itself, so curing that shape cured the fixture's
trigger — and the other's fact now takes route (3), so its description was made dirty to keep it
in the `invalid` case that route declines.

⚠ **A ceiling this does not close:** `facts_manifest` caches a `secret` verdict per canonical row
keyed on mtime/size/ctime/body_hash, so a predicate fix does **not** clear a cached verdict
unless the file's bytes change. It does not affect the three facts here — they are *local* facts
and that manifest is canonical-tier — but a canonical that trips will need an explicit
invalidation, and there is no such path today.

## [0.4.41] — 2026-09-21

**Patch — a dream pass that reported success while appending nothing, and five smaller
coordinate defects in the same tool. Two guards, one split message, one renamed token;
no `CycleRecord` field, CLI flag, or manifest contract changes.**

A pass ended with `render_dashboard --persist` exiting **0 and appending no line**, and then —
after a hand-fix — appending **two** lines for one cycle. Both symptoms have one root: the
identity key `(marker.commit, marker.timestamp)`.

1. **A stamp must have MOVED before it is copied into the record.** `seed_record` seeds
   `marker.commit` **filled** and `marker.timestamp` **empty** ("stamp at write time in Phase 5"),
   beside `before_commit`/`before_timestamp` — the previous cycle's pair. `reconcile_marker` fills
   the empty `timestamp` from `.consolidation-state.json`, and that fill was **ungated** while the
   `commit` fill beside it was `_valid_sha`-checked. A pass that had not re-stamped therefore wrote
   **this cycle's commit wearing the last cycle's time** — a coordinate that never existed — and
   because `_persist` dedups on that pair and keys the usage clock on it, two runs of one cycle
   minted the same chimera, the clean run was suppressed as a `"duplicate"`, and the cycle ended
   **exit 0 with no log line**. The fix site records what that means: it is *"the exact failure
   this function's own docstring says v0.4.1 was written to prevent."*
   The fill is now admitted only when the record carries no `before_timestamp` (the first-run case,
   vacuous) **or** the state's stamp differs from the record's own `before_timestamp` — **string
   identity, no parsing** — because the incident's condition was **equality**, not "older", and a
   lexical ISO comparison is unsound across a fractional-seconds boundary. A refused stamp fills
   **neither** field (`stamp_project_marker` writes the pair together), and the file's timestamp
   must now be parseable ISO before it is copied, mirroring the gate `commit` already had. A stale
   stamp reaches `_persist`'s existing unstamped arm → **exit 5** with the re-stamp remedy named,
   on a path already pinned end-to-end. A silently wrong coordinate became a loud refusal.

2. **`--audit` refuses a store-shaped operand, and refuses an impossible census.**
   `audit_snapshot` derives three roots from the positional, so a memory store handed in as
   `PROJECT_DIR` resolved all three empty and every entry read as *deleted* — a confident bogus
   census, injected into the record and rendered. The positional was unvalidated besides:
   `resolve_store` is deliberately non-strict, so a wrong operand resolved to a **phantom slug**
   and the audit then `mkdir -p`'d that phantom's operational directory. Two guards, both at the
   positional pool so one insertion covers every arm — the store-shaped operand is refused in
   `sync_global`'s established message shape, and a **non-empty snapshot whose roots all resolve
   empty** is refused as an instrument fault rather than reported as a census. That second rule is
   the inverted-guard shape: it fires on the script-computed condition rather than on a heuristic
   about the result, so a genuinely all-deleted census with resolving roots still passes.

3. **The disagreement diagnostic names both operands instead of presuming which is wrong.**
   `budget.index.after_tokens contradicts the scripted audit (…)` asserted a fault it could not
   establish: both sides are script-computed, so a disagreement is a fact about one of two
   computations, not a verdict on the record. The message now names both and their provenance and
   blames neither. The `contradicts the scripted audit` phrase is deliberately retained — a test
   selects warnings by it, and dropping it would turn that selector into a filter matching nothing,
   which is a false green.

4. **The archive's exit-1 arm stops sharing one sentence between a fault and a verdict.** Given a
   project dir, `render_html.py` exited 1 with *"no dreams to render — run a dream first"* when the
   real fault was the **operand** — the log was not empty. The two conditions now carry distinct,
   operand-naming messages, and `--store` is still never silently defaulted: the ownership guard
   admits a `project_path` only when it verifies, so a guessed default would be a new way to render
   the wrong store.

5. **`prune_reason` stops calling the target rung "budget".** `prune_pressure` returned
   `"index-over-budget"` when the index passed the **1500 target**, while `INDEX_CEILING_TOKENS`
   (3840) is the second, independent rung reported separately as `remediation.over_ceiling`. One
   record therefore carried `prune_reason: "index-over-budget"` beside `over_ceiling: false` — with
   "budget" being the one word the ladder reserves for the whole two-rung ladder. The token is now
   `index-over-target`, and the two sites that carried it as twin bare literals share one named
   constant, so the producer and the reporting predicate cannot drift. Naming only, no behavior.

6. **A comment stops claiming a consumer that does not exist.** `_ui.py`'s wide-glyph range was
   described as shared with "the arc-completeness check". `arc_completeness` never reads it — it
   decides the exit-4 gate on presence, count and string-ness only, and a glyph rule there would
   fail an arc over its typography. The range has exactly one consumer: `render_dashboard`'s
   advisory beat flag, which changes no verdict and no exit code. The code was already honest and
   only the prose over-stated, so the prose is what changed.

`tests/smoke.py` gains **11 checks tagged v0.4.41**, each labeled a pin or a regression guard —
the guards kept out of the pin count precisely because they pass on both trees.

## [0.4.40] — 2026-09-21

**Patch — the release's version/date pair gets a gate, and four documents stop describing a
release tool that no longer exists.**

A release moves two things together: the version, and the date printed beside it. `release.sh`'s
old bump moved the version and left the date behind, and nothing read the date — so a live doc
could state the current version while still carrying a date the CHANGELOG contradicted. The bump
is hand-authored now, which makes the pair need a gate *more* than before rather than less: a
person typing a version is exactly as likely to leave its date behind as a script was.

1. **`tests/docs_links.py` checks the date a currency statement pairs with its version.**
   `check_currency_dates` runs *from* the existing first-`vX.Y.Z` walk rather than getting a
   sweep of its own — that loop already has the claim's line in hand, and a second sweep would
   be a second copy of the rule. A doc that dates its statement must carry the CHANGELOG's date
   for the version it names. The gate reports that as a **pair** — *"2 of 2 dated statements
   checked"* — and the pair is the instrument rather than a flourish: the first number counts
   comparisons **performed**, so a skipped statement shows as one number falling while the other
   holds, and a single count could not separate *"nothing was dated"* from *"everything dated
   was skipped"*. The **failing** path prints it too, and has to: a skipped statement forces a
   red run, so a readout that existed only beside the ✓ could never have shown the fall it
   describes. Scope is the claim's own physical line, deliberately: the
   spec's ops-HOLD line carries a **historical** `v0.4.2` beside a `2026-08-31` date while the
   CHANGELOG dates `0.4.2` at `2026-09-03`, so a file-wide sweep would redden a correct tree.
   The blind spot that buys — a reflow separating a version from its date — is recorded in the
   function and is the one arm the mutation harness still measures green, visible as `1 of 1`
   where an untouched tree reads `2 of 2`.

2. **An undated release section is refused, not tolerated.** `check_changelog_dated` closes a
   hole the check above cannot close from inside: `changelog_date` returns `None` both for a
   version the CHANGELOG never dated and for one it never mentions, and on `None` the date axis
   **skips** every statement it was about to compare, with every other check still green. Measured, the state is reachable and is the state this repository releases from: a
   CHANGELOG whose top section reads `— UNRELEASED` with real notes passed `--stage`, passed
   `--finalize`, and shipped — nothing stamped the heading, and nothing required it: the
   convention had no producer anywhere in the tooling. The discriminator is `plugin.json` —
   the manifest's version has to be a version the CHANGELOG dates — which is the same pair the
   release harness verifies, so the gate reds exactly when shipping would be wrong and stays
   green mid-cycle, when the next section sits undated above a manifest still naming the
   shipped release.

3. **Three false descriptions of the release tool, repaired.** The first spans four documents:
   `CLAUDE.md`, `AGENTS.md`, `docs/1.0-preflight.spec.md` and `.github/workflows/release.yml`
   described `--stage` as bumping `plugin.json`, committing `release: vX.Y.Z`, pushing
   `release/vX.Y.Z` and opening a release PR, with a *"pre-bump preferred … `--stage` is a
   no-op"* fallback and a release PR as the last-minute-bump escape. None of that is true:
   `--stage` **verifies, never authors** — it asserts the hand-bumped `plugin.json` already
   equals the CHANGELOG version, refuses otherwise, and runs the validators. No gate reads this
   prose, which is why that description drifted: the tool changed in a gitignored file, and the
   committed docs did not follow. Two more instances of the same class were still wrong. Three
   further homes — `CLAUDE.md`, `AGENTS.md` and `release.yml` — said `--finalize` runs its
   validators on *"the revision being tagged"* when they read the **working tree**, which the
   tool names and compares against the commit being tagged, warning when the two differ; that
   one did not drift, it shipped false in the commit that added the validators. And `CLAUDE.md`
   credited `--stage` with a **tag** guard it never runs on the documented path — the check sits
   only in the branch that exits 1 regardless. `--stage` guards the clean tree; `--finalize`
   guards the tag.

4. **Three coverage gaps on the release path, closed.** The first two are the same gap in two
   places: `docs_links.py` ran in `ci.yml` and **nowhere else** — the `release.yml` verify job ran
   smoke, the accumulation sim and the manifest validator, and `./release.sh --finalize` ran no
   validator at all, so the one path that *tags and ships* validated no bytes. Both now run it, and
   neither call repeats `ci.yml`: that job judges the PR's **head**, and the tag goes on the
   **merge commit**, which a conflict resolution or an "Update branch" can change after CI last
   said green. The third is a claim with no reader: `plugins/dream-beta-tester/docs/STATUS.md:1`
   states `dream-beta-tester v0.1.8`, and the doc was in neither `DOCS` nor `LIVE_DOCS` — both
   measured 0 — so its links went unchecked and its version unread. It cannot simply join the
   currency sweep either, which is keyed to *this* plugin's manifest: the sibling's own `v0.1.8`
   and the `v0.1.85` it cites as provenance are both "wrong" against `0.4.40`. So
   `check_plugin_status_docs` pairs each discovered `plugins/*/` manifest with the `docs/STATUS.md`
   beside it — discovered the way the plugin-table rows are, so a third plugin is covered the day
   it lands — and the boundary is stated rather than implied: one site, the doc's opening line,
   the way the badge and the table are one site each.

Evidence: the date gate caught a real defect before it ever shipped — the `v0.4.39` bump left
both paired dates at `2026-09-19` against a `## [0.4.39] — 2026-09-20` section, and it was the
only instrument that could: `ci.yml` runs the committed `docs_links.py`, which was blind to
dates. Six mutation arms run on a copy of this tree — one is a no-mutation control, and one edits
both live sites in a single arm: the leave-behind drives the gate red on each live pair, one
error apiece (the two-site arm reports their sum) while the version axis stays green throughout,
the `— UNRELEASED` window and a broken heading matcher each drive it red through the guard — both
were green blind spots before it existed — and the reflow remains the single recorded blind spot,
green at `1 of 1`. The arms are separated by the pair each red now prints: a real date divergence
leaves the axis running (`2 of 2 dated statements checked`), a disabled one reads `0 of 2`. That
discrimination was previously unprintable — the pair went out only beside the ✓, and
`checked != eligible` is reachable ONLY in a red run — so every red reported no counts at all,
and the failing path now carries it too, as a parenthesized aside rather than a `- ` line. Three
in-tree pins in `tests/smoke.py` cover the axis: the first pair reads `check_currency_dates`'
return directly and is RED against the pre-arc `docs_links.py`, where it does not exist; the third
drives `main()` down its failure path and reads its stdout. Each is measured as a contrast, not
asserted: an earlier gate restored into a `cp -a` copy of the tree, `diff -rq` showing the copy
and the original differ in exactly one file, and the two runs differing by exactly the pins that
are red. Two further pins cover item 4's sibling header and fail the same way — RED *by absence*,
since a gate that predates `check_plugin_status_docs` cannot run it, which the arm reports as the
`AttributeError` it is rather than as a traceback out of the suite.

## [0.4.39] — 2026-09-20

**Patch — one defect on two arms: the dream read a project's transcripts from the STORE's slug only, so
a session launched in a SUBDIRECTORY of the project root was invisible to it.**

Claude Code keys the STORE to the nearest `.git` ancestor but the TRANSCRIPT to the cwd, so a session
started in `<root>/sub` writes to `<store-slug>-sub` while the store's own slug holds only the sessions
started at the root. Measured instance: a session that did a full day's work under `~/project/Gats`
(store at `-home-you-project/memory`, transcripts at `-home-you-project-Gats`) reported `0 surfaced ·
(no transcript)` — a structural blind spot read as a quiet session. The counting-only pre-flight agreed
with it, which is why the wrong number went unquestioned for a whole cycle.

1. **`extract_signals._window_transcripts` admits the subdirectory slugs — confirmed, never guessed.**
   Candidates come from a slug PREFIX (`<store-slug>-*`), which is necessary and not sufficient: a
   same-prefix sibling (`Gats-old` for `Gats`) and a nested repo (whose own `.git` gives it its own
   store) both share it. Each candidate is therefore admitted only when a transcript's own `cwd`
   confirms membership — the test mirrors CC's rule exactly, including its reliance on `.git`
   EXISTENCE rather than validity, because running a validator CC does not run would admit transcripts
   it files elsewhere and drop ones it files here. A candidate outside the window is dropped without
   being opened, and `project_root=None` preserves the original single-directory behavior.

2. **The narration arm reads the same pool.** `dream_procedure.judge` and `render_dashboard`'s
   narration detector resolve their transcript pool through the same window, so NAR/EXT were blind to
   exactly the sessions the extractor was; both now take the store's `project_root` and pool the
   subdirectory sessions too. Fixture callers that pass nothing keep the single-directory pool.

Evidence: `tests/smoke.py` v0.4.39 — 10 pins, deliberately including the two shapes a prefix alone
would wrongly admit, plus the `project_root=None` no-regression default on both helpers.

## [0.4.38] — 2026-09-19

**Patch — two defects, each closed by the one repair its class allows: a splice artifact repaired
by deleting the DUPLICATE, and a rule that was false in three places repaired by naming its real
boundary rather than by adding rows until a false universal came true.**

Two comments sharing no root cause, chartered together because the first rides code v0.4.36
introduces. Design and evidence: `docs/comment-and-registry-truth.spec.md`.

1. **A doubled clause is repaired by deleting the duplicate, not the connective.** One comment
   line in `render_html.py` ended on `…, which is why` and the next opened on `…which is why the
   rendered identity is cwd-invariant` — **two overlapping copies of one clause**, so reading
   either line alone looks almost right. The tail is the connective the sentence needs; the head
   is the copy, so the repair removes `...which is why ` and nothing else. ⚠ Diagnosing the first
   line's `, which is why` as *dangling* is a verdict read off the wrong instrument — a clause
   whose consequent sits on the next line is what a **wrap** is — and that diagnosis drives a
   repair that leaves behind the very consequent-less sentence this item exists to remove. The
   clause is PR A's own new code, which is why it rides a later release instead of re-opening A's
   measured gate. **No check**: nothing here verifies that a comment parses as prose, and
   inventing a gate for a class observed once would be the same defect in a new place. Its only
   observable is that the doubled clause is absent.

2. **The `DOCS` registry states one rule in its header and a different one inside, and neither was
   true of the list.** The header's `Templates are included because…` sentence states its own
   exception, so it is scoped; the interior comment (`Every doc the README links to`) stated a
   **false universal** and named no exception. MEASURED over the README's markdown link targets:
   **12** `.md` files, of which **four were absent from the list** and all four exist — so those
   four are added. The interior comment's false universal is not restated but **replaced by the
   entry's own justification**: the clause a restatement would have carried (`the criterion this
   list actually applies`) is a **rule**, and a rule stated below the header that already states
   one puts the list's criterion in **two places** — the defect this item removes, rebuilt by its
   own repair. So the criterion moved **into** the header, which now also carries the principle's
   second inclusion (*the design record a reader is handed off to*), and the comment keeps only
   the measured fact and the entry's reason. ⚠ **The false rule had a SOURCE, and correcting the
   restatement left it standing.** The interior comment did not invent its universal — it *cited*
   one, naming its authority in the same sentence (`the docstring's promise is "…"`), and that
   authority is the file's own invariant 2, which states the checked set as *every other doc a
   reader lands on from the README*. One rule, three homes — the header (over-claiming about ONE
   entry), the interior comment (corrected here), and the docstring: **the origin, corrected in the same
   edit**, because a reader who fixed only the comment from the text in front of them would
   regenerate it from the sentence it cites. Invariant 2 is now scoped to the set the check
   actually walks and names the two docs its old form silently excluded (`CLAUDE.md`,
   `plugins/dream-beta-tester/docs/SPEC-A.md`), which the list's own boundary note had already
   measured. ⚠ The four entries a reader might reach for *instead* —
   the list entries with **no** README arrival — are a **different** set of four, and conflating
   them drives a wrong repair: three are the GitHub templates the header's own sentence covers,
   and the fourth is the design record that made the header false about **one** member — the entry
   the header's second inclusion now names. ⚠ **No closure rule describes this list** — a
   2-hop spec is listed while two other 2-hop docs are not — so the header now states the
   principle **with its exclusions named**, and the list's measured edge is recorded after it,
   because a rule that does not name its exclusions is a universal again one edit later.
   **A REGRESSION GUARD, not a pin** — each added entry's links already resolve, so no check added
   here can fail on pre-fix code. What it buys is that the four docs' own outbound links enter the
   check. MEASURED: gate green, checked files **14 → 18**.

3. **The release turned its audit on its own shipped text, and six claims were false — four of
   them this branch's.** Every numeral was re-derived from the tree with its matcher named, and
   every repair **edits the claim it falsifies** rather than annotating below it. ⚠ **Two are
   figures that lost their operand, and the distinction between them is the item.** Part 2's
   derivation paragraph states `16` reached, ten held and **14** entries, all true at this branch's
   base `9585b10`, where they yield the `4` the paragraph derives. The head reads **18** entries
   holding **14** — the four additions land — and the difference is still `4`, so the figures are
   **bound to the base rather than recomputed**: the head's numerals are a different derivation of
   the same invariant, and swapping them in would have replaced correct content with correct-looking
   content about operands that no longer produce it. The Defect-2 diagnosis is bound the same way
   for a sharper reason — it is a **pre-repair** diagnosis in the present tense, its coordinates are
   the base's numbering, and its clause `no comment in the file accounts for it` is false from the
   repair onward, because the header's second inclusion names precisely that entry. ⚠ **The
   registry's own docstring was the third, and it is this item's defect one register up.** Invariant
   2 said two docs *a reader does land on* from the README are absent — **arrival** vocabulary over
   a **link-graph** measurement — while the README also links the **directory** `docs/adr`, holding
   **24** documents that no `.md`-filtered walk can represent and which are neither entries of the
   list nor instances of any exclusion class the header names. The operand is now stated, the
   directory and its documents are named as the arrival the words invite, and the file's own header
   rule (*neither depth nor a link is the membership rule*) is what made the mismatch findable: **a
   file that states its criterion and then reports a count from a different one is this item's
   defect arriving in the registry's own docstring.** ⚠ **The fourth is a PREDECESSOR's, and this
   release falsifies it rather than merely finding it** — the citation check's bare-form census
   reads *MEASURED … at this revision … Of `81` scanned … `49` carry neither*, and the document this
   release ships is walked, so the same walk returns **82** and **50** while its other two cells and
   its citation total hold. The binding is restated as the **corpus** rather than a revision, and
   the superseded pair is named so that a reader who remembers `81 / 49` can tell a moved operand
   from a broken matcher. ⚠ **A fifth was repaired alongside it, and the two differ in kind: the
   census moved because this branch moved it, while the docstring quoting the pre-fix workflow
   comment's wrap was false before this branch existed.** It is corrected here because the file is
   open for the census anyway and because the correction is one word — the quote is of a file's
   **bytes**, the file carries **ten** spaces after the `#` where the docstring wrote three, and
   this registry itself names the three-space form as a rejected draft. What that quote is *about* —
   the wrap, and the `#` marker the faulty join leaves behind — is unaffected, which is why the
   repair is to the quotation's fidelity and not to its claim. ⚠ **The sixth is the registry's, one
   home above the third, and it is the header's own exclusion list.** The appositive under
   *destinations that are not reader-facing documents* listed **`LICENSE`**, and `LICENSE` **is** a
   reader-facing document — it arrives from the README as a markdown target **twice** (`:391`,
   `:395`). So the list was false about **one of its own members**, which is item 2's test turned on
   the header that states the rule; the member was **cut** rather than the clause reworded, because
   the class the clause excludes is defined by reader-facing-ness, and `LICENSE` fails that
   definition instead of sitting outside it. ⚠ **The destination the clause does reach is a
   directory, and reaching it is all it does** — `docs/adr` is not a document, so the clause covers
   the destination and says **nothing** about the `24` documents behind it. A directory's scope is
   not its contents' scope, and the file's own practice is the proof: `docs/` is likewise a
   directory, is likewise linked from `CONTRIBUTING.md`, and five of its `82` tracked documents are
   listed. ⚠ **Two docket entries were refuted by the artifact's own adjacent text** and are
   recorded as refuted rather than silently dropped: a `CHANGELOG` clause read as an attribution is
   a **conditional perfect** naming the clause the repair deliberately did *not* write, and a
   mention census read as an unscoped universal states its operand in the same sentence-group.

**No check added or removed; D6 unchanged at 2177.** Verification: `smoke 2177 passed / 0 failed`
· `docs_links rc=0` (**18 files link-checked**, 7 required strings unbroken) · `sim rc=0` ·
`mypy rc=0` · `manifests rc=0`.

## [0.4.37] — 2026-09-19

**Patch — prose stops asserting what nothing ties to the tree. Where v0.4.36 tied an identity to its
subject, this ties an assertion to its subject: give it a producer, gate it, or label it a guard.**

The second of the two cycles staged under the F2 charter — the half that reads the *world* wrong.
Five families were docketed; **three closed, two were refuted as posed and are recorded as refuted
rather than quietly dropped.** Design and evidence: `docs/prose-tied-to-the-tree.spec.md`.

1. **A figure stops being hand-derived — it cites its producer.** `docs/index-usage-and-budget-ladder.spec.md`
   stated three fleet positions, and the byte figures **reconstruct from two different operands in
   one sentence** (node 1 needs 25,000, node 2 needs 25,600) while the document's own fixture asserted
   `cliff_pct == 24` for the very inputs the prose called 25%. A **second** bad figure was found by
   re-measure: the closing sentence named the *ceiling* axis (0.6 × 200 = 120 lines) where the cliff
   is 200. The root cause is not sloppiness — the producer rounds 25 KB as 25×1024 and *documents*
   the shift as immaterial to an 80% alarm, which is sound for an alarm and exactly enough to move
   23.98 → 24.55. A producer already existed, so the spec now **cites** it instead of restating its
   output, and the dated duplicate collapses to one home.

2. **`cm`'s usage block is gated against its parser.** The heredoc advertised
   `[--plan|--apply --confirm rebuild-local-index]`, and the shared `local` subparser declares no
   `--plan` at all — MEASURED, `./cm local rebuild-index --plan` exits **2** with *"unrecognized
   arguments: --plan"*, so the advertised flag was unusable rather than merely undocumented. The
   obvious gate had a hole (the existing doc-flag sweep **carves `cm_ops.py` out** and reads only
   bash-fenced blocks, while the heredoc is in neither), so this one reads the heredoc directly.

3. **The packaging prose is corrected at BOTH sites, and the reason is that they lie in opposite
   directions.** `release.yml` over-claimed *"attaches all three"*; `SECURITY.md` put provenance
   *to the Release* and omitted `SHA256SUMS` entirely. Ground truth: **two** assets are attached
   (`sbom.spdx.json`, `SHA256SUMS`) and provenance reaches a verifier through the **attestations
   API**, not as an asset. **The one item the two pages agree on is the false one**, so cross-reading
   them reinforces the error — which is why fixing one site alone leaves the defect alive.

4. **The citation rule is made enforceable — REFUTED as posed, and the refutation is the
   deliverable.** The docket claimed stale citations; measured, six hand-read samples were **all in
   range** — every line number resolves cleanly, which is why no check could ever have found them.
   One is not drift but **inversion**: a doc reports that `CLAUDE.md` claims *"byte-pinned copies"*
   while `CLAUDE.md` now says the opposite. The adopted rule — *a `file:line` is legitimate iff the
   doc declares the revision its coordinates resolve on* — is therefore shipped as **binding plus a
   resolution check**, with the phrase half **refuted by measurement**: over 494 citations, **313
   (63%)** carry no extractable identifier on their citing line, so a corpus-wide phrase gate would
   fire on correct content. The census that motivated the docket is itself an instance of the class
   it measures: three reasonable matchers over one tree returned a **1.66× spread**, so the
   deliverable is **the matcher, stated**, not the number. The check's own reach is now **printed
   rather than inferred**: `_CITE47` requires the citation to sit in its own backticks, so a bare
   `foo.py:12` in running prose is invisible to every arm. MEASURED over 81 scanned docs, the
   corpus splits four ways — 14 backticked-only · 9 carrying both · **9 bare-only, 59 citations** ·
   49 neither — and the label names the **bare-only 9**, which are exactly the docs `_CITE47`
   cannot reach. The wider read an unguarded census would take (bare form over *every* doc)
   measures 18 docs / 135 citations, and using it would have **overstated the gap by precisely the
   population the check already covers**: its 18 supersets the 9 with the 9 docs carrying both.

5. **The wrapped anchors — REFUTED as posed; shipped as a REGRESSION GUARD.**
   `CLAUDE.md:32-33` contains a phrase a contiguous `grep -c` returns **0** for, because the source
   wraps it. The contiguity requirement arrives WITH the anchor rule, and the pre-fix reader shows why
   it had to: `check_required_strings` matched its needles literally, so a wrap did fail it — as
   *`README.md no longer mentions '<needle>'`*, a verdict naming the wrong defect for a phrase still
   present one line down. **An anchor that wraps is not greppable, therefore not an anchor.** A ninth
   `docs_links` check matches a needle across a wrap by interleaving `\s*` through it and reading the
   **raw** file —
   normalizing the haystack instead would delete the very neighbours its boundaries read. It **cannot
   fail on pre-fix code**, so by this repo's own rule it is labelled a guard, never a pin.

6. **The release's own new content was itself reviewed, and the defects found in it are fixed here
   rather than shipped.** The opening round found three; each later round — adjudicating the previous
   round's own docket — found more, **most of them in this release's own new prose and labels**,
   which is the cleanest evidence that the rule is a rule rather than a theme. ⚠ **No count is
   claimed here**, and that is deliberate rather than coy: a count in this position was falsified by
   the very next round, twice. The rounds are enumerated below in the order they landed. (a) The D6 ledger's provenance note carried a **superseded numeral**:
   it read *"RED on 18 of `fbfe07e`'s citing docs"*, the pre-widening figure — the spec beside it
   records *"`18 of 19` became `20 of 21` when it was widened"*, and the check's own printed label
   says *"reddens the other 20"*. The ledger contradicted both. (b) An **unguarded `read_text`** in
   the docket loop sat *before* D6, so deleting a single docket doc aborted the suite with a
   `FileNotFoundError` and **D6 never ran** — the *"an orphaned section can never print green"*
   guarantee defeated upstream of the counter that guarantees it. It now reports a verdict
   (`no such doc`) and D6 still evaluates; **mutation-verified: 2177 passed / 0 failed with the doc,
   2176 / 1 without it.** (c) Pin 9's reach is **the whole bound corpus, 23 of 23**, and it is
   **printed, not inferred**. Two rounds were needed to get there. The first disclosed that **21 of
   the 23** asserted and two were skipped in silence: a reading note authored as a bold paragraph
   rather than a blockquote returned its token line alone, so the walk found no `git show` to
   compare — and the label explained that gap with a reason **false at both revisions**, since the
   one bound pre-fix doc *does* carry a `git show e5cce77`, one line beneath a token opening `**H`
   rather than `>`. The second round then **widened the walk** itself, from a `>`-delimited block to
   a blank-line-delimited one — a blockquote is a special case of the latter, not a different rule —
   and MEASURED **2 docs vacuous under the old rule against 0 under this one**, with **0
   disagreements either way**. The two docs were therefore not merely *disclosed* as unreachable;
   they were **reachable**, and the guard now asserts on every doc it binds. (d) Pin 4's **third-site
   coordinate pointed at the claimed text at no revision**: it named `CHANGELOG.md:2495-2496` as a
   third place asserting the false packaging claim, and that resolves to a `## [0.4.5]` heading at
   this revision and to older-release journal prose on the base — while the cited passage is
   **byte-identical at both**. A CHANGELOG grows from the top, so a coordinate into one is decay
   rather than a handle; it is now named by **phrase**, per this repo's own `v0.4.25` rule, and the
   label records the measurement that forbids a line number returning. (e) The spec **misquoted the
   measurement it cites**: two sentences said the helper's docstring measures a flatten into
   `Run the/cm-syncverb`, which is the flatten of nothing — whitespace-removed it reads
   `Runthe/cm-syncverb`, because the space inside `Run the` dies with the break. The *conclusion*
   survives (the needle's neighbours are word characters under either string), so this was a
   misquote of a cited source and not a false claim — corrected at both sites rather than argued
   away. (f) And the reach comment itself, first drafted for item 4, **paired one population's doc
   count with another's citation count** — 18 docs / 135 citations against the printed 9 / 59. It
   was caught by running the check and comparing the two figures, which is the whole argument for
   printing a reach instead of inferring one. (g) The spec's **row 7 quoted its own subject wrongly,
   and the misquote made the row argue itself out of its own example**: it called the second
   `SKILL.md` *"the beta-tester's **vendored** copy"*, while the canary directory under
   `fixtures/canary-v0.1.19/` vendors **no `SKILL.md` at all** (six `.py` files, `README.md`,
   `SHA256SUMS`) — the second file is the beta-tester's **own** skill. The distinction is
   load-bearing, not pedantic: **EXCLUDED** is that row's verdict for a vendored copy, so a vendored
   second file could not have produced the ambiguity the row reports. The row named it correctly one
   clause later, so the document disagreed with itself. (h) **The needle registry is delimited by
   punctuation *on at least one side*, not by punctuation** — the qualifier was already in the
   sentence while the head clause over-claimed, and MEASURED **2 of the 7** needles (`/cm-connect`,
   `/cm-share`) carry a SPACE as the right neighbour at every occurrence, so the head clause was
   false of them. Corrected at both sites — the helper's docstring and the spec — to the form the
   argument actually rests on. (i) **A reading note declared a coordinate convention its own document
   does not keep, and this one misdirects the reader.** `render-declaration-parity.spec.md`'s note —
   added by this release — read *"every `file:line` below is `1d97f54`-numbered"*. Measured:
   `render_dashboard.py:1249` is `def _persist(...)` at `1d97f54` but `_shown_b = min(len(_blocked),
   _REG_BLOCKED_CAP)` at `60a03b4`, and `smoke.py:4451` is an unrelated comment at the base but the
   `_ceilRecB` fixture at `60a03b4` — and `60a03b4` is a **descendant** of the declared base, so
   following the note lands the reader on unrelated content rather than a near-miss. The note's
   stated exception was too narrow (it named bare *identifier anchors* as the shipped-tree system,
   when a shipped-describing **sentence** may cite a coordinate too); the discriminator is now the
   **sentence**, not the citation form, with both instances hand-verified and **no count asserted** —
   the automatic screen flags nine more but keys on ordinary words like `rem` and `over`, so that
   figure is a screen and not a verdict. (j) The spec's row 9 referred to *"the label"* in a table
   that **has a `label` column** whose own row-9 value is `**GUARD**`; it now names the **message**
   the check emits, which is the surface that actually changed. (k) **A second adversarial round was
   delegated against the frozen branch, and its six findings were adjudicated by re-measurement rather
   than accepted on delivery — five confirmed and repaired, one refuted, and the refutation is the one
   worth keeping.** A sweep reported `render-declaration-parity.spec.md`'s `render_dashboard.py`
   coordinate as stale; it is exactly what the citing sentence claims the **shipped** line shows, and
   that document's reading note declares and hand-verifies a shipped-tree coordinate class the sweep
   had not read. The five repairs share this release's shape — **a claim about the tree that its own
   document already contradicted.** (1) `deep-field-theme.spec.md`'s note declared *every* `file:line`
   below `e15ac3e`-numbered, and two are not: that commit **inserted six CSS lines** in
   `dashboard.template.html`, shifting every coordinate ≥125 by `+6`, and the doc was edited *inside*
   the commit that moved it. MEASURED at `e15ac3e` — `:246`/`:375` hold `.core{fill:var(--accent)}` and
   `#net-groups{display:block…}`, while the two rules the sentence is about (both
   `#network-blk .domain-count,.project-meta`, one `--faint` and the later one `--ink2`) sit at
   `:252`/`:381` — and the note now carves out the one coordinate belonging to a later pass's own
   reading. (2) `_DOCKET47`'s scope claimed its **five** dockets were *"the corpus's ONLY docs whose
   base revision is DERIVABLE"*: a universal over an unestablished class, since **23** of the 81 docs
   under `docs/**/*.md` (`_CANON47`'s own scan, recursive) carry a `` **`X`-numbered** `` note, and
   **seven** of them have a fixing commit whose subject
   phrase is derived and measured unique. Two were added (`dbt-truth-restoration` → `6ac5380`,
   `signal-pipeline-hardening` → `ceaccc0`), each with **one** child, the fix itself — as do two of
   the other five, while the remaining three have two (the fix and the merge that brought it in,
   PRs #222/#230/#228) and there the needle is what picks the fix. Six numeral sites moved with the
   scope, the check's own printed message among them. (3) The spec's stated **two-part rule** still
   carried the phrase half its own row 7 refutes by measurement; what PR B adopts is the resolution
   half, and it now says so where the rule is stated rather than only where it was refuted. (4) Item 5
   above said the ninth check *"normalizes whitespace before matching"* — the draft the helper's own
   docstring records as **measured wrong**: it interleaves `\s*` through the needle and reads the
   **raw** file, because flattening the haystack deletes the neighbours its boundaries read. (5)
   `refusal-verdict-parity.spec.md` asserted that *"on every commit of the branch"* line 830 holds
   `ACTION_WRITES`; measured, it holds an unrelated `return` at both branch heads, and `ACTION_WRITES`
   is what it holds at the doc's **declared base** `e5cce77` — a true statement about the base, in a
   sentence that asserted it of the branch. (l) **Pin 4's ground truth stated a property of its own
   matcher that the matcher did not have — in three homes at once.** The upload line's filename list
   was read from **plainly** flattened workflow text, and the code comment, the check's printed label
   and the spec's row 4 all justified that with one clause: *"so a commented-out upload cannot still
   supply its filenames."* MEASURED 2026-09-19 with the live upload line commented out, the pattern
   matches it under **both** normalizations — `search` carries no `^` anchor, so a leading `#` is just
   another character, and `_uncomment37` **keeps** the line, dropping only the marker. The pin would
   therefore have gone on asserting the prose against a line the workflow no longer runs: a green
   verdict about a dead line, which is this release's defect class arriving in the release's own gate.
   The read now **drops the comment lines** — which is what makes the clause true — and it asserts
   there is exactly **one live** upload line, the same defect's second half, since a first-match read
   of an unasserted set is a partial census wearing a whole one's clothes. Measured in all three
   directions rather than argued: live → `count=1`, green; commented out → `count=0`, **red**;
   duplicated → `count=2`, **red**. The new conjunct also holds on pre-fix code, so it cannot flip
   the pin's RED. (m) **A reading note carved one coordinate out of its binding and named no revision
   for it** — `deep-field-theme.spec.md`'s note, the surface (k)(1) repaired, whose exception read
   *"the reading that pass took on the tree it ran against"* and left the reader to go find that tree.
   There is none to find: MEASURED, that number resolves to a different line at each of four
   revisions — `#network-blk .hierarchy-branch.grant-edge` at `v0.4.23`, the reduced-motion `@media`
   block at `v0.4.24`, `.record-detail{…}` at `e15ac3e^`, `.arch-tools select{…}` at `e15ac3e` —
   because the pass read a **working tree no commit preserves**. The note now names that tier
   (testimony, quoted as it was read) rather than dressing the number as a citation, and its
   **self-coordinate** into the same document is replaced by the heading it points at: a line number
   into a document that grows is the very decay that note warns about. (n) **A green `smoke` count is
   not a green gate** — the release says so, and then this round paid for it. Pin 10 is uncommitted
   work, and when the full gate was finally taken on the tree that *contains* it, `mypy` failed on
   that pin's accumulator, `Need type annotation for "_sw47"`. Its only write is
   `setdefault(...).append(...)`, a return mypy cannot infer a value type from — unlike the sibling
   accumulators it was modelled on, which write with a plain `.append` and need no hint. So the Gate
   line below is stated for **one** revision, all five legs taken on that same content. (o) **The
   abort class (b) opened was closed the only way a class closes — by asking its question instead of
   enumerating its members**, and the answer is a criterion now stated in the block's own preamble so
   the next editor checks it rather than re-derives it: **a read is GUARDED iff this block is the
   FIRST STRICT reader of its input.** Three reads are therefore deliberately left raw — `cm`,
   `release.yml` and `SECURITY.md` are each read strictly and unconditionally far earlier in the same
   file, so a guard here would print a verdict the suite can never reach. The four this block IS
   first to read carry one now: the ladder spec (nothing else reads it at all), the docket docs and
   `docs/**/*.md` (whose earlier reader is TOLERANT — `errors="replace"` — and so is not a reader of
   the same *inputs*), and the workflow glob, which owns `ci.yml` and every workflow that is not
   `release.yml`. ⚠ **At one of those sites an unguarded read is not an abort but a GREEN:** a
   workflow the glob cannot decode never enters the mapping, so pin 10's anti-vacuity clause would be
   satisfied by the two known runners and the check would pass over a directory it had stopped
   reading. MEASURED with three mutations, one per guard, on a tree that is otherwise this content —
   the ladder spec removed, then a docket doc and `ci.yml` each replaced by a directory — the suite
   prints **2172 passed / 5 failed** with **D6 evaluated**: pins 1 and 2 carry the new input clause,
   pin 8 its FAULT with its own scope, pin 10 the file it could not read, pin 6 asserts the
   unreadable doc rather than dropping it, and nothing aborts. Two further repairs are not about
   guards at all. **A fault's scope now travels with the fault:** pin 8's fault arms do not reach
   equally far, so one clause cannot be true of all of them, and the scope is set at each arm rather
   than computed once from `not _log47` — which answered a question about whether a LOG existed as if
   it were one about whether the walk FINISHED. And **the resolution rule was described as CONTENT
   while the predicate compares a line COUNT** — the spec's rule statement, its row-7 detail and the
   check's own comment all said *content*, no cited line's text is ever read, and the row's own
   parenthetical had defined it line-fit all along, so the document contradicted itself and the
   correction reached the rule statement last. (p) **The contiguity helper's own needle space was the
   one position its join could not reach** — `re.escape(" ")` is a backslash-space, a LITERAL space,
   so the `\s*` separators tolerated a dropped or doubled space *between* characters while the
   character that IS a space still demanded one exactly there. MEASURED, a space-bearing needle set
   against wrapped text reads ABSENT: `check_required_strings` reported a present string as gone
   **and** `check_contiguity` — the arm that owns exactly that shape — stayed silent,
   so the pair's claimed partition broke with no message at all, in the direction that reads as a
   clean run. Whitespace inside a needle is now mapped rather than escaped. (q) **The `/code-review`
   stage was run**, in the shape the sibling release used: four lenses over a clean clone, each told
   to treat its own findings as hypotheses to verify before reporting them. Three delivered reports;
   the fourth — `cr-b-pins` — **executed and delivered nothing**, which is recorded as a statement
   about DELIVERY rather than about execution, since this cycle has published each of those two
   errors in turn. Adjudicating at the head rather than at the binding, every finding in those
   reports is either **repaired** or **refuted by measurement**, and the refutations carry the
   lesson. A `release.yml` finding reached **independently by two lenses** describes the BASE's
   state as the head's: `fetch-depth` occurs **zero** times at `fbfe07e` and is present in the very
   job the finding names, so the defect is real, it is caught by pin 10, and the fix and the check
   rode the same commit. Every report's own head-status line used a `rev-parse <rev>:<path>`
   comparison, which answers *did this file change* and not *is the defect in it*. The second
   refutation is sharper still, because it is the one no blob test can ever see: a finding can cite
   a line that **is** byte-identical while the read AROUND it changed — the continuation-line blind
   spot's matcher is unchanged to the byte, its loop now carries its anchor across continuations,
   and the report's own "widened" experiment reproduces the SHIPPED read exactly. MEASURED with a
   mutation placing `--domains` on a continuation line and nowhere else: **2176 passed, 1 failed**,
   pin 3 the **only** red, D6 evaluated — while the pre-fix read prints `unaccepted: none` on the
   same text. **And one defect was found here rather than by any lens, in the table that says what
   the checks ARE:** row 10 was committed with a prose fragment for a first cell, the paragraph
   below it resuming mid-sentence. Repaired, and swept for siblings — one site.

⚠ **This release adds the suite's first check that reads the tree's own git history**, so **every
workflow that runs the suite** sets `fetch-depth: 0` — `ci.yml` on both of its jobs, and
`release.yml`'s `verify`, the one such job the first cut left at the default depth. That gap is
material rather than tidy, and it is this release's own defect arriving in its own harness: the
comment recording the dependency named the file in front of its author, and `verify`'s stake is
categorically higher — `provenance` declares `needs: verify`, so a red there does not warn, it
cancels the release. Pin 10 asserts the class now rather than the instance. A shallow clone makes
two of these checks report **verdicts about the
corpus** rather than name a missing input — measured, an archive tree and a `--depth 1` clone are
indistinguishable: the fault arm advises deepening a clone that does not exist, and the verdict arm
prints *"0 failing"* from an instrument that cannot read. **The third is repaired here rather than
disclosed:** the history arm used to call the one correctly bound docket BAD, and it now claims its
two faults — a tree that cannot be asked for its own history, by the command's own **return code**,
and a **shallow clone whose truncation actually BIT**, the one shape a return code cannot see — and
on either it fails naming the INSTRUMENT (`this clone is SHALLOW`) instead of reporting on
documents. MEASURED on a `--depth 1` clone: **2174 passed / 3 failed**, pin 8 RED with that fault
message.

   (r) **A final pass over the pins' own predicates, and every defect it found was one shape — an
   instrument reading something other than its subject.** (i) **Pin 10's predicate was satisfied by the
   comment beside it.** The check tested whether the job's text contained the string `fetch-depth: 0`,
   and the same commit that added the remedy also added a seven-line comment NAMING the remedy — so the
   explanatory prose satisfied the check, and a mutation deleting the `with:` block would have gone
   green on it. It now requires a **line declaring the key** (`^\s*fetch-depth:\s*0\s*(?:#.*)?$`), which
   a whole-line comment cannot match because its `#` sits exactly where the key would, while a key
   carrying a trailing comment still does. MEASURED: `ci.yml`'s comment line `False` and its key `True`;
   `release.yml`'s comment `False` and its key `True`. The glob was `.yml`-only while `*.yaml` is
   equally legal to Actions; widened — recorded as closing a **latent** hole, since the repo carries no
   `.yaml` workflow today. (ii) **Pin 4 read its prose through a sliding anchor.** Splitting on
   `provenance:` and then on `on:` does not go empty when the `provenance:` comment that OPENS the prose
   is deleted: the anchor re-binds to the `provenance:` **job name** and cuts at `runs-on:`, returning
   the YAML fragment `name: provenance + SBOM `. Truthy — so a fault and an absence shared one
   representation, and the check answered a missing subject with a verdict about `SECURITY.md`'s prose.
   The anchor is now asserted and scoped to the workflow header, and a missing subject is a **FAULT that
   states no verdict**, the arm pin 8 already established. MEASURED as a pair on one tree and one
   mutation — the header prose deleted, the tabulation unmoved and only the report changed: pre-repair
   **`2176 / 1`**, pin 4 the single red, reading *"unnamed `['sha256sums']`, count-claims none"*, a
   verdict computed FROM the absent subject; post-repair the same **`2176 / 1`**, reading *"FAULT —
   release.yml's header carries NO `provenance:` prose block, so this read has no SUBJECT"*, and the
   derived list is withheld rather than prefixed to it. (iii) **The spec's own numerals, re-measured
   with their matchers now stated.** Its `git` census read *36 / exactly four resolve against `ROOT` /
   the other 32*; under the matcher — the argv[0] literal `"git"` — the head reads **39 / five / 34**
   and the base `fbfe07e` reads **34 / 0**, so PR B adds five invocations and every one of them reads
   `ROOT`, and the set is named by a greppable anchor rather than by a line list. The paragraph
   recording what the instrument repair moved still carried *45 / 37+8* as a live figure, superseded by
   pin 10's addition; it now states which correction it is about, and the reconciliation
   (`2131 + 45 = 2176`, `2131 + 46 = 2177`) makes pin 10 precisely the one red that separates them. The
   `DOCS` bullet held a base-bound **79** against a live **81** — the **+2 being exactly the two specs
   this stack adds**, one per PR. (iv) **The `DOCS` decision that spec asked to have recorded is
   recorded, and it is NOT to add it:** README does not mention this document, so it is not
   README-reachable, and **its own outbound links are therefore not link-checked by the gate it
   describes**. (v) **`check_contiguity`'s justification said "Named per needle" and named four of
   seven** — a universal asserted over a fraction of its own set. All seven are named now, and the
   partition the sentence states (**5 both-sides / 2 space-right**) reproduces member by member.
   (vi) **And row 10 was still outside the checks table**, a blank line above it splitting the table in
   two — the same row that this release first committed with a prose fragment for a first cell. **Both
   are one defect: a row the reader's parser cannot reach.** No check was added or removed; the
   self-counting pin is unchanged at **2177**.

Gate: smoke **2177** passed / 0 failed · docs_links · sim · mypy (42 source files) · manifests.

## [0.4.36] — 2026-09-19

**Patch — an identity stops being taken from the room. The archive's masthead was read from whatever
directory the process happened to be standing in, while the archive series it was stamped into was
read from the store it was handed.**

The first of the two cycles staged under the F2 charter — the half that reads the *world* wrong.
Design and evidence: `docs/identity-from-the-input.spec.md`.

1. **RC-5 — a masthead must be derived from the archive it stamps.** `render_html.py` resolved the
   archive *series* from `--store` and the *identity* from `Path.cwd()`, so the shipped dream path —
   which passes **only** `--store` — stamped every archive with the identity of whatever directory the
   process was launched from. Measured on the pre-fix tree, calling `resolve_store` from three cwds:
   this repo yields `personal / enrolled / allowed`, while `/tmp` and a home directory that is not a
   project (`/home/you`) yield `unknown / false / false` — and **no cwd raises**. Driven end-to-end with the same `--store`, the
   same cycle record and `--out` to a temp dir, the two runs differ (215535 vs 215536 bytes) with
   `generated_at` identical, so the difference is the embedded identity and nothing else. There is no
   guard to fool: the wrong value is non-empty, correctly shaped and schema-valid, and the renderer
   draws it. **The identity is now recovered from its subject** — the registry row whose
   `native_memory_dir` is that store, then the store's own marker
   (`.consolidation-state.json` → `project_path`), then a guarded `cwd` — and a candidate is admitted
   only if it **both round-trips and is project-derived**, so nothing resolving through a user-,
   managed- or settings-scoped override can name the subject. Nothing verifies ⇒ the render refuses,
   naming the flag that resolves it.

2. **RC-5a — a fault stops being spelled like an absence.** The same block sat inside a bare
   `except Exception: pass`, so a resolution *fault* and an *absence* were the same `{}`. The
   resolution is lifted out; only the advisory warning stays wrapped. **The scope is stated rather
   than implied: this arm is LATENT, and the fix converts exactly one behavior.** An AST census finds
   **zero `raise` statements** in `resolve_store`, `_merge_settings`, `identity_snapshot` and
   `warn_unenrolled_share`, and six hostile cwds (a garbage `.git` file, a `.git` symlink to nowhere,
   a malformed `settings.json`, a nonexistent dir, a dangling `gitfile:`, a plain dir) each returned a
   context without raising — so what the blanket catch could actually reach is the **import**, and
   removing it means a **broken plugin install now exits 1 rather than silently rendering `{}`**.
   That lands on the neither-flag arm, so it is a **listed** behavior change rather than one left for
   the implementer to discover.

3. **RC-5b — two inputs that must agree, compared nothing.** `--store S --project P` was accepted
   with no check that `S` is `P`'s store. Measured live: `--store <temp store> --project <repo>`
   returned **rc=0**, no refusal, and an archive stamped `personal / enrolled / allowed` rendering the
   temp store. The pair now verifies agreement through the sole-authority constructor
   (`resolve_store`, ADR 002), and a mismatch is a refusal rather than a silent preference for one.

4. **RC-5c — the same misdirection WROTE.** This is the row that makes the defect outlive the render:
   `warn_unenrolled_share` was called with the cwd-derived context, so it set `_warned_unenrolled` in
   the **cwd project's** state file — and because that flag is a one-shot gate, it **silently
   suppressed the cwd project's future warnings**. A display defect that persists as durable state.
   **Two sites, and the row is a census whose matcher is the warn, not the cwd:** counting `cwd()`
   sites would count cwd *reads*, most of which are correct. There are **nine** call sites of
   `warn_unenrolled_share` in the tree, of which **two** derive their context from a directory while
   the same call names its subject by argument — `render_html.py:415` and `render_dashboard.py:1936`.
   The other seven pass a `ctx` already resolved from their own subject. Naming both is not
   decoration: a cell naming one would be read as *"there is one"* — and the second site is
   `render_dashboard.py`, the very module this fix adopts as its precedent, where the hardened call
   and the unhardened one sit twenty lines apart.

5. **Five refusal arms, and two faults do not share a message.** The recovery refuses when a store
   belongs to no registered project, when it belongs to a *different* project than the one named, when
   the named pair disagrees, and when the **registry itself cannot be read** — and that last arm
   deliberately does *not* wear the unenrolled arm's remedy, because telling a reader to enroll a
   project that is already enrolled is the fault-as-verdict collapse v0.4.35 closed, one layer down.
   A corrupt registry is the arm that reaches it: SQLite opens lazily, so a garbage-byte database
   returns a **live connection** and fails only at first query, as a `DatabaseError`, which is the
   **parent** of the `OperationalError` its callers catch.
   **The fifth arm is this release's one contract addition, and it is the same rule applied one fault
   further out:** a subject whose store path **cannot be canonicalized at all** — a NUL arriving
   through a settings redirect. It is not a miss. A miss says *nothing names this store*; this says
   *nothing could be **tested***, because the one operand every source is compared against was
   unusable. Printing the miss's line for it hands the reader a remedy that **faults identically**
   (`--project` is governed by the same redirect), so the fault gets its own arm, its own message and
   its own remedy — *check `autoMemoryDirectory` in your settings*. Measured pre-fix: rc 0, an archive
   shipped with an **empty** masthead.

6. **The shipped path names its subject — and that naming is what creates the CHECK, not a second
   name.** `SKILL.md` now passes `--project "$(pwd)"` beside `--store`. ⚠ **Measured: on its own the
   flag is a tautology** — `$(pwd)` *is* the directory the renderer already infers, and the two forms
   render **byte-identical** output whenever the pair agrees. What it buys is the **agreement
   check**: a `--store` transcribed from another project is now a refusal that **names the pair**
   (`is not the store for …`), where the old form's refusal misdiagnosed the same command as
   *"belongs to no registered project — pass `--project`"*. **And the pair is not guaranteed to
   agree:** for a non-git project rendered from a subdirectory it refuses deliberately (measured,
   rc 1), since there is no repo root to resolve through — there, run from the project root.

7. **RC-5d — a stored value that cannot be RESOLVED was resolved anyway.** Three defects, one line
   each, in two files, all reachable from the same mistake: `Path.resolve()` raises
   `ValueError: embedded null byte` on a NUL, and **`ValueError` is neither `OSError` nor
   `sqlite3.Error`**, so it escaped both files' guards as an uncaught traceback.
   - **The marker vector.** `json.loads` **accepts** an escaped NUL, so a garbled marker still
     PARSES while the resolve raises — and the raise landed outside the parse's own `except`, so the
     documented degrade to source 3 never ran. Measured: the same store renders rc 0 with no marker,
     exit 1 with a NUL in one, from every cwd.
   - **The registry vector, which is broader.** `rows_for_store` resolved **every** row and ran
     **first**, so one corrupt row took down every `--store` invocation rather than only its own —
     which is why the repair is in `control_plane` and not at the call site.
   - **And the relative-value arm, sharpest because it needs no corruption at all:**
     `Path(raw).resolve()` on a **relative** stored value anchors the match to the **process cwd**,
     so which row the lookup returns — and so the identity the archive wears — depends on where the
     render ran. Measured on one registry with one `--store` from two cwds: a store owned by charlie
     was stamped with **atlas's** identity. RC-5 reproduced inside RC-5's own repair.
   The guard names `(OSError, ValueError)` specifically; `except Exception` was **rejected**, since a
   fault and an absence sharing one representation is RC-1's exact mechanism. Stored values are now
   compared **absolute-only**, which is the contract `store_context` already writes.
8. **RC-5e — the truncated install, and the dependency that was left unwrapped.** `render_html.py`
   guards three shipping-class dependencies that live in the same directory, under a rule its own
   comment states: a truncated install *"must degrade with the same one-line message, **never a
   traceback**"*. Two of them followed it; the `from store_context import …` did not — it was the one
   thing RC-5a's removal of `except Exception: pass` left bare. **Measured, and there are three
   states, not two:** on `fbfe07e` the removal renders at **rc=0 with empty stderr** (the blanket
   catch turned a fault into an absence and shipped an empty masthead); with that catch gone it
   raised an **uncaught `ModuleNotFoundError`**; it now degrades with its siblings' one line. Only
   `ImportError` is caught — a fault *inside* `store_context` is not a truncated install, and must
   not go to the reader wearing that remedy.
9. **RC-5f — the managed-policy route, which nothing drove.** `_merge_settings` applies **four**
   settings scopes; the redirect pins drove three. `policy` (`managed-settings.json`) is the highest-
   precedence scope and the one whose own docstring says it **may name an explicit absolute dir** —
   i.e. exactly the constant the predicate's second conjunct exists to refuse. **A one-line widening
   of `_project_derived` to admit it is caught by pin 19 and by nothing else — MEASURED: 2165 passed
   / 1 failed, and that failure is pin 19** — where before that pin existed the same widening left
   the whole suite green (2146 passed / 0 failed) while the render stamped the **room's** identity
   (`domain_id: unknown`, `cross_project_allowed: false`)
   onto an enrolled subject's store at rc=0. Pin 19 is the **instance** rather than a table over the
   predicate's constant, and that is the finding's own shape: a predicate edited to admit a *name* is
   caught only by a check that *drives* that name.

**Pins and the exit-code rule.** Each fix's pin **fails on pre-fix code**; checks that cannot are
labelled GUARD rather than PIN. **62 new checks, measured 2026-09-19 by running the branch's own
suite against a `fbfe07e` tree: 2129 passed / 37 failed there, and 2166 passed / 0 failed here** —
the same total on both (2166), which is what makes the two runs comparable. **34 of the 37 failures
carry `(PIN` in their own label** — ⚠ **and the count is stated
over *that* matcher, because the label has three spellings:** `(PIN)` × 17, `(PIN, site 1 of 2)` × 5,
and `(PIN — …)` × 11. A reader who greps the **bare literal `(PIN)`** returns **17** and undercounts
by half, which is the failure mode this entry's own subject is about — a census believed because its
matcher was never named. Over the right matcher the taxonomy is enforced by the
run rather than asserted by this entry: a reader who wants to audit the split can read it off
the failures instead of counting the greys. ⚠ **The other three are stated exceptions rather than
pins:** pin 19's PRECONDITION, which is red on `fbfe07e` *because it asserts the fixture* — the field
it reads (`mem_dir_source`) is introduced by this change, so the fixture cannot even be established
there — and pin 27's CONTROL and its REGRESSION GUARD, which are red there because the **subject is
absent** rather than for the properties they assert. Each red pins no behaviour, and each label says
so; a reader totalling the split should not count them among the pins. ⚠ **The increment is the sharp
form of the same evidence, and it is read per round:** the two checks round 1 added are *exactly* the
two that joined the red set (17 + 2 = 19), and the three that cannot flip — one GUARD, two
PRECONDITIONs — stayed green on both trees. **Round 2 added six checks and moved the red count by
ONE (19 → 20) — and that is the honest reading, not a shortfall:** three are PRECONDITIONs by
construction, and of the three that discriminate, **two are green on `fbfe07e` for the same reason
they are green there for every other source-2/3 check — the base tree never consults the marker or
the registry at all.** Their discrimination is proved against a tree where it *can* be, which is the
**pre-repair revert**: both repairs textually undone → 2143 passed / **exactly 15, 16 and 17
failed**; repaired → 2146 / 0. A round that added a check which could not discriminate on *any* tree
would show a smaller increment than its check count under *both* measurements, which is the one way
to tell a pin from a ceremony. **Round 3 added four and moved the red count by THREE (20 → 23)**, the
missing one being pin 18's GUARD — regression cover for a rule that already held on `fbfe07e`, so it
has no red to contribute; the round also brings the one stated non-pin failure above.
**Round 4 added thirteen and moved the red count by ELEVEN (23 → 34)** — the twelve checks of pins
20–26 plus one GUARD inside pin 3 — and the two that cannot flip are named here rather than left to be
re-derived: **pin 24's PRECONDITION**, green on `fbfe07e` *on purpose*, because its job is to
attribute that pin's red to the arm rather than to a fixture that failed to build, and **pin 3's
GUARD**, which measures `_restore36`'s promise to leave the shared registry as found and so has no
pre-fix state to be red against. That GUARD is not decoration: **removing the `chmod` it guards turns
it red and nothing else** (measured: 2165 passed / 1 failed), which is the only available way to show
a guard is not vacuous, since by this repo's own rule no PIN may cover it. **The identity pin
renders **one
store under two cwds** and requires the
embedded `identity` payload **byte-identical** — pre-fix the two runs differ in exactly that payload.
RC-5c's pin cannot use the rendered archive at all: its observable is the **flag written into the
subject's state file**, a side effect scoped to the subject, measured RED pre-fix with the flag
landing in the cwd's store and leaving `--store`'s untouched. The unrecoverable-store and
disagreement arms are pinned on exit 1 *plus* their named message, and the registry-fault arm on
**not** producing the unenrolled arm's message, since that separation is the arm's whole point.
The **25** checks green on both trees are not filler, and the split is exact rather than
approximate: **10 GUARD, 14 PRECONDITION, 1 CONTROL — and not one PIN.** That is the taxonomy proved
as an identity rather than described: every check in this release that *can* flip does, and every
check that does not is *labelled* as one that cannot. **The two that matter most run the opposite way
from every pin, so a predicate tightened past the design turns them red while every pin above is
still greening:** a **symlinked** store paired with its **own** project (a legitimate pair a one-sided
compare refuses), and a **project-scoped, contained** `autoMemoryDirectory` (which must still recover)
— each must still render. ⚠ Both are GUARDs, and the reason is worth reading rather than counting:
neither can fail on `fbfe07e`, because pre-fix the render succeeds there too — stamped with the
**wrong** identity. They guard against **over**-tightening, which is the direction a suite built
entirely of pins cannot see.

**A misdiagnosis the fix itself introduced, found by self-review and repaired.** Handing
`render_html` a `--store` that **does not exist** and nothing else reported *"belongs to no
registered project"* and advised passing `--project <its dir>` — a **registration** fault, about a
path that is not there, with a remedy naming a directory that does not exist. Pre-fix the same
command exited 0 and rendered, so this was **new**, and it read **two different ways depending on a
flag with nothing to do with the mistake**: with `--project` present the pairing branch already
tested the path and said *"does not exist"*; without it, control fell past every source to the
unenrolled arm. The repair dispatches the message on whether the path exists **after every recovery
source has run, never before them** — the position is the whole design, because the same test placed
first would refuse two invocations this release deliberately supports: a store **deleted since
enrolment** (recovered from its registry row, which is a stored key) and a store **the cwd derives**
(a project that has not dreamed yet). Both were measured rendering rc 0 after the repair. The
absent-path remedy names **both** routes, since the two situations are indistinguishable from the
input and one clause alone would misdiagnose the other.

10. **The registry scan is bounded at the target end — and the bound sits *after* the query on
    purpose.** The design-of-record left one finding open: `rows_for_store` resolved **every** row to
    answer about one, with its cost **unmeasured**. Measured now: **~16 µs/row**, and the 340-row live
    registry → **5.4 ms** (10k → 0.15 s; 100k → 1.5 s). The resolve loop's *share* of the function is
    deliberately **not** stated as a constant, because it is a property of the **registry** rather than
    of the function — an earlier draft of this entry pinned it at **89-92%** and costed 340 rows at
    **7.9 ms**, and neither re-measured: the two figures did not even multiply (340 × 16 µs = 5.4 ms,
    not 7.9). **No repair that speeds the loop is sound** — an index or a `WHERE` prefilter would speed
    the SELECT, the smaller half, and is unsound on its own terms anyway, since a non-canonical stored
    value can still **resolve onto** the target (only `resolve()` sees that, and the loop may not stop
    at a first hit because `native_memory_dir` carries no `UNIQUE`); `os.path.realpath` is **1.4×–2.0×
    faster** (measured over five fixtures, so the ratio belongs to the path) and still **not
    swappable**, because it *returns* a symlink loop's path where `resolve()` raises the error
    `safe_resolve` converts. So the
    one available win is a **bound**: an unusable store yields `target is None`, and this returns `[]`
    whatever the registry holds. ⚠ **It is a CORRECTNESS bound, not only a cost one, and an earlier
    draft of this entry got that wrong** by claiming *no row can equal `None`*, so that the scan was
    *determined by the argument*. A **resolvable** row does fail the comparison against `None`, since
    no path equals it; but a row whose OWN value is unresolvable resolves to `None` too, and
    `None == None` **admits** it — measured with the bound removed, one NUL-bearing row comes back for
    a NUL-bearing `--store`, stamping a corrupt row's identity onto an archive. That is this cycle's own
    defect shape arriving inside its repair, and it is why the bound is required rather than merely
    cheap. ⚠ **Hoisting that bound above the
    `conn.execute` is the one placement that is wrong**, and it was measured rather than argued: the
    query is this function's only **fault channel** (`classify_registry` verifies tables and never
    columns), so skipping it reports a registry **fault** as an **absence** — `fault ≡ absence`, this
    cycle's own mechanism, sending the reader to re-enroll a project that is already enrolled. The
    bound consequently trades the query's cost, on a rare input, for that signal. Two single-variable
    mutations carry it, each producing a different single red, **both re-run and reproduced** on the
    constructed A-only tree: bound **deleted** → the **pin** alone (2165 passed / 1 failed); bound
    **hoisted** → the **regression guard** alone (2165 / 1). **Not operator-visible** — nothing behaves
    differently, and the work skipped was work whose answer the argument had already fixed.

**An operator can observe:** an archive render whose subject cannot be named now exits non-zero and
writes nothing, where it previously rendered a wrong identity under a clean exit 0; a store that is
named but disagrees with its `--project` is now refused rather than half-honored; a broken plugin
install now exits 1 rather than rendering an empty masthead (RC-5a); and a single corrupt value in
the registry no longer takes the render down (RC-5d) — it is skipped, the way a key that cannot be
compared should be, instead of escaping as an uncaught `ValueError` from a row with nothing to do
with the store. The cost is named: a refusal
stalls the render where it used to complete with a wrong masthead, and a stalled render is
recoverable in one command.

## [0.4.35] — 2026-09-18

**Patch — a refusal stops being spelled like a verdict. Eight faces, one root cause: a surface
re-derives meaning from something other than the data that produced it, and the value it invents is
the one that reads as a clean result.**

The first of the two cycles staged from the 2026-09-14 audit — the data-integrity half. The surfaces
that read the *world* wrong (identity taken from the ambient context, prose asserting what nothing
ties to the tree) are chartered separately. Design and evidence:
`docs/refusal-verdict-parity.spec.md`.

1. **RC-1a — a fault must not degrade into a verdict.** `--audit` read an unreadable, absent or
   invalid-JSON snapshot as `before = {}`, and `audit_diff` then reported **every store file as
   created** — measured live on 2026-09-15 as a fabricated `+572,437 tok`, **exit 0**, archived as a
   real row and rendered by every downstream surface. A missing or unreadable snapshot is now a
   **named fault with a named remedy, a non-zero exit, and no row written**, extending the sibling
   `--diffs` path's existing idiom rather than inventing a second one. The same arm had a second
   face: `--diffs` printed **one sentence for four causes**, so a *named* path that could not be read
   and a legitimately **empty** store snapshot both wore the remedy for an omitted flag — a store
   that was correctly empty was told to re-run a phase that had already run and succeeded. Each cause
   now states itself. The third face is in the rebuild's archive pass: a store-root doc **no loop
   could read** is named and fails the plan closed, because an unreadable placement record cannot be
   told from an absent one.

2. **RC-1b — a recognized flag with a missing value is a usage error.** Five value-taking flags
   parsed `--flag <value>` by looking one token ahead and accepting it **only if it did not start
   with `-`**. A missing value therefore left the variable at the value meaning *"flag not supplied"*,
   so a malformed command was read as an absent one — the flag accepted, nothing assigned, and each
   sink failing differently. `--stamp-marker` already re-distinguished the two and exited 2; that
   verdict is now the general rule across the five flags whose sinks cannot tell the difference, and
   it is applied to **every** occurrence rather than the first — the parse reads only the first, so
   `--before <valid> --before` (bare, trailing) would have satisfied a first-occurrence guard while
   the malformed flag went unreported. **The same guard needed a second predicate**, because a flag
   present with an explicitly **empty** value is neither *missing* nor *absent*: `--audit ""` — a
   shell variable that expanded to nothing — carried `"".startswith("-")` as `False`, so it was
   admitted and reached RC-1a's `before = {}` arm through the plainest route of all. Measured at
   exit 0 with a summary reading `claude_md: created 1024, token_delta 4075886` where the same
   fixture's real snapshot reads 0/0; it now exits 2 like every other missing value.
   **The same arm sat at three more sites, and the class is closed here rather than one site of it:**
   v0.4.29's `_VALUE_FLAGS` guards in `distill_scan.py` (6 flags), `extract_signals.py` (4) and
   `sync_global.py` (`--into`, by two routes — `--into ""` and the equals form `--into=`) test a
   value's **presence**, never its **emptiness** — `i + 1 >= len(argv)` admits `""`, because an empty
   token *is* a token, so an unset shell variable reached every one of them. Measured 2026-09-18 with
   each site run three ways (flag omitted / flag with an empty value / flag with a real value) under a
   hermetic `HOME`: the empty arm was **byte-identical to the omitted arm**, and differed from the
   real-value arm every script already instruments (`distill_scan` prints its injection,
   `extract_signals` a scope warning, `sync_global` reaches its read/write arm). All three now exit 2
   naming the flag. `sync_global`'s guard is scoped to the `--registrar` branch by measurement rather
   than by convenience — outside it the flag is never consumed, and the script already warns it is
   ignored (on the pre-fix tree too), so a parse-time guard would fire where the flag is *correctly*
   ignored. The one arm that already did — `sync_global`'s bare trailing `--into` — is kept by
   a GUARD and not counted as a pin, because the pre-fix tree measures **12 reds and not 13**.

3. **RC-1c — unevaluated is not a removal verdict.** `_rebuild_plan` argued the safe direction
   twice in its own comments — *"it may never REMOVE a live one"*, *"reading a refusal as 'no
   entries' can only re-add, never delete"* — and then treated a fact it could not **evaluate** as one
   it had decided to **remove**: the stem never entered `planned`, so `would_remove` named it and the
   apply physically dropped its pointer. The reachable danger is the false positive: a firewall
   refusal on a live fact's body de-indexed that fact, through a line two comment blocks above
   forbid it. The plan now gains the stems it could not evaluate and **retains their existing pointer
   line verbatim** from the already-pinned index snapshot. **Operator-visible change:** a stem that
   used to disappear from the index now stays — `--skip-invalid`'s `omitted` means *"left in place,
   unverified"* rather than *"removed"*.

4. **RC-1d — one string cannot carry two causes.** An archive refusal used one message for both *"not
   a fact"* and *"secret-shaped"*, so the operator could not tell which admission rule fired.

5. **RC-2 — the guard must test what it claims.** `--audit`'s dedup comment promised it would not
   *"double-append an indistinguishable duplicate"*; the code tested `(commit, timestamp)` **identity**
   and only against the **last** row. So a same-stamp correction was dropped and a false row was
   permanent, while a *different* stamp appended a contradiction with equal standing and no marker.
   The guard now scans every row and writes a `supersedes` field when a later run corrects an earlier
   one. Measured on the shipped fleet before the change: 105 mutation rows across 13 logs, 73 of them
   carrying an **empty** commit — the arm the identity test skipped outright.

6. **RC-3 — one vocabulary, one matcher.** `outcome_of` counted a 3-element subset of the action
   vocabulary while the panel rendered from the *same record* tallied all five, so one record printed
   `= 5 reconciled` **directly above** `NO-OP PASS · reviewed, nothing changed`. Both now read one
   declared vocabulary, and a smoke check counts the sites so a sixth cannot appear unmatcher'd.

7. **RC-3b — a name must not invert its value.** `would_readd_archived_pointers` held the re-adds the
   plan had **declined**. Renamed `would_keep_archived_pointers`, so the operator's one interface
   stops naming the opposite of what it reports.

8. **RC-4 — two duties gain a carrier.** A seed's `entries: []` was indistinguishable from a
   decided-nothing pass, and an absent `demotion.verdict` rendered as silence — *"ran and justified
   both"* and *"never ran"* as the same bytes. Both are now rows in the **existing** record-duty
   table, held to the same standard as the three shipped in v0.4.33: a clause that fires on a state
   the producer writes **deliberately** is a false-positive class, not a refinement, so each row
   abstains on the legitimate classes and is pinned against them.

**Pins and the exit-code rule.** 71 new checks. Each fix's pin **fails on pre-fix code**; checks that
cannot (they are green pre-fix by construction) are labelled GUARD rather than PIN, and the
distinction is asserted rather than claimed — several were split into a PIN and a GUARD precisely
because a conjunction is never covered by covering its operands separately. The `--audit` refusal
takes a **non-zero exit** while the `--diffs` sibling keeps its `0`, and the difference is stated
rather than left to be rediscovered: `--diffs`' skip is a routine stamping state under its standing
rule that a diff-capture failure must never crash a dream, whereas every `--audit` arm here is a
**fabrication**. The cost is named in the spec — a non-zero exit stalls the pass rather than
completing it with a bad row, and a stalled step is recoverable in one command.

**Two behavioral changes an operator can observe:** a stem the rebuild could not evaluate now keeps
its index pointer (item 3), and a named-but-unreadable `--audit` snapshot now exits non-zero and
writes nothing where it previously wrote a fabricated row (item 1).

## [0.4.34] — 2026-09-17

**Patch — the renderer stops deciding what a record means by reading its labels. Five fixes, one
root cause: a surface re-derives meaning from a *label* instead of from the data that produced it,
and the label is the only thing anything checks.**

The second of two cycles staged from the 2026-09-14 audit. Design and evidence:
`docs/render-declaration-parity.spec.md`.

1. **The remediation verdict was a 3-way lookup over a 4-dimensional outcome.** The panel's note was
   `.get(lever, "")` — a dictionary keyed on the *routing label* — while the outcome space is
   `(lever, candidates_surfaced, pruned, achieved_index, reaches_budget)`. Three measured
   consequences: the skill's own **sanctioned** prune-then-justify state rendered the
   `prune can't reach budget → …` remedy *and* the `⚠ gate fired but not acted on` alarm at once
   (a sanction beside an alarm for one state); **rewriting one label swapped the verdict**, so
   `lever=prune` and `lever=justify` rendered opposite notes from byte-identical data; and
   `"justified — nothing safely prunable (see entries[])"` rendered whether or not candidates had
   been surfaced — which is precisely the claim the surfaced count would falsify. The verdict is now
   derived from the data, and `lever` keeps only the section header, where it is a *routing* decision.

   **Two user-visible wordings move, and the third does not.** `"mirror-dominated — global demote/GC
   lever, not a local prune"` now **names the operand** (`mirror-dominated (90.0% of index tokens) —
   …`) and fires on `mirror_share > 0.5` rather than on `lever == "gc"`, so it reads as an advisory
   about *where to act* and no longer suppresses the local-prune advice by label. `"justified —
   nothing safely prunable"` is **gone**, replaced by three sentences that state what the record
   actually says — `⚠ gate fired but not acted on — surface candidates + prune-or-justify` /
   `0 candidates surfaced — record the justification, or re-triage` / `no candidate count recorded —
   whether the gate was actionable is not answerable from this record`. `"gate fired but not acted
   on"` keeps its **exact** wording; only its *reachability* narrows, because the remedy and the
   absent-count arms now take precedence. The dropped phrasing was asserting a fact about the store
   (nothing *is* prunable) that no field in the record carries.

   **The share moved to `.1%` in the same repair, and the reason is a collision.** `.0%` rendered a
   share of `0.5025` as `"50%"` — the **boundary's own numeral** — so a store that *exceeded*
   `_MIRROR_DOMINATED` printed identically to one that merely met it, discarding the distinction the
   routing immediately above it had just used. The example in this item reads `90.0%` for that reason.

2. **The remedy and the success are one decision.** `prune can't reach budget → …` and
   `✓ gate resolved by rebuild-lean` were separate `if`s, so `achieved_index=900, reaches_budget=False`
   drew a sanction and a success in the same panel. The remedy now fires only when the lean path did
   not resolve.

3. **`… +N more blocked` was a false total.** The count comes from the record
   (`workflow_proposals.n_blocked`, the script's full-join count) while the rows come from the local
   display list — two different sources. An all-`generic-cli` window sets `n_blocked: 30` while
   persisting no displayable rows, so the panel printed `… +30 more blocked` with **zero rows drawn**
   and, two lines later, `0 fleet-candidates — the honest cold state`, denying the count it had just
   asserted. The HTML archive already branched on it and emitted a **counts-only breakdown**; the
   ASCII renderer was the outlier, and now ports that shape — carrying the JS's clamp, so
   `{n_blocked: 10, n_generic: 30}` prints no `single-node` term rather than a negative one. The
   cold-state line is suppressed whenever the record counts blocked rows.

   **The port deliberately does not carry the JS's *guard*, only its output.** The HTML branches on
   `!board`, which asks *"was anything at all drawn"* — the right question there, because its
   counts-only branch **assigns** the board (the guard keeps the breakdown from clobbering the cards)
   and the blocked count is stated separately in a `reg-counts` header. The ASCII branch **appends**
   and has no such header, so what it must ask is *"were the count's own rows drawn"*. Carrying
   `!board` across left the false tail on a shape `sync_global`'s own persist rule builds — one
   persisted fleet row beside twenty counted `generic-cli` rows records `n_blocked: 20` and persists
   no blocked row, so a card *is* drawn and the guard goes quiet. **A guard's condition has to name
   the claim it guards, not the shape of the port it came from.**

4. **A default that fires only on ABSENT cannot see an empty string.** `_clean(x.get(k, "?"))` leaves
   `""` rendering as a hole — the same defect as a missing key, invisible to every reader. Eleven
   sites in the renderer took the repair (the `or` idiom the file already uses for
   `_clean(_e.get("name") or "?")`), and a **census** pin now asserts the population *and* the
   verdict: 12 sites match the form, 0 unguarded. Both numbers are asserted together on purpose —
   dropping a default *removes* a site, which moves the population while leaving the unguarded count
   at 0, so a verdict-only check would go quiet exactly where it should shout. (Of the 12: eleven
   were repaired here, and `identity.domain_id` was already guarded before this cycle — which is
   where the idiom was copied from.) Two further sites spell the same defect a **different** way —
   the marker's `commit`/`timestamp` guard `None` explicitly and then pass `""` — so they are not in
   that census's population at all; they are pinned behaviourally instead. The census's own stated
   limit is that it cannot see an *empty* default (`get(k, "")`), which is excluded by construction.

5. **Two declaration drifts, in opposite directions — and which side moves is decided by the
   *reader*.** `identity.domain_lifecycle` was emitted by `store_context.identity_snapshot`
   (unconditionally, via `getattr`) and the HTML archive renders it, yet it was declared on neither
   `Identity` nor `SKILL.md`: the two declarations agreed with each other and both were wrong about
   the code. `audit.window` was the mirror image — declared in both, read by the archive as a
   property access (`audit.window`) and rendered as an "Observation window" row, and never written by
   any producer, because a grep for `"window"` cannot see a property access. The declaration was
   brought to the producer for the first, the producer to the declaration for the second, and the
   committed archive preview now shows a **true** observation window for the first time. Those are
   the suite's first **forward-direction** pins (producer ⊆ declaration); every earlier shape pin
   compared `SKILL.md` to the TypedDict, so a producer and a declaration could agree while both
   disagreed with the code — which is exactly where these two lived.

   Relatedly, `tests/smoke.py`'s nested-shape loop claimed the two documented carve-outs were "the
   ONLY un-pinned shapes". That was false: **seven** shapes had a `SKILL.md` block and a TypedDict
   and were pinned by neither (`Narration`, `DomainEntry`, `UniversalFact`, `GroupLink`,
   `NetworkCapture`, `StackEdgeFacts`, `FactHolding`). They were in perfect key agreement, so this
   was a **coverage claim that was wrong**, not a drift that had been hidden; all seven are enrolled,
   and the claim is now bounded by its two real structural limits (depth ≤ 2, and the
   SKILL↔TypedDict direction) rather than asserted.

**Verification.** Twenty-eight new checks — **eighteen pins**, **nine guards**, and **one regression
guard** — taking the suite to **2017 checks**. Every pin was mutation-verified against pre-fix trees
built with `git archive` (never `git worktree add`, one process per tree): reverting the renderer
alone reds **exactly** the sixteen render pins plus the rewritten v0.1.35 arm; re-injecting the
producer drift reds **exactly** E4-a, E4-b, and the `SKILL↔TypedDict` `Identity` arm — **three**, not
the two an earlier draft of this entry recorded, because the declaration and its schema block are two
surfaces that necessarily move together and only one of them was counted. The one existing check this
cycle deliberately turns from green to red is v0.1.35's "still over budget" arm, which asserted the ⚠
for the state the skill sanctions — that assertion *was* the defect, so the check is rewritten rather
than deleted.

**Two of the eighteen pins came from a second review pass over this cycle's *own* repairs, and both
findings were the cycle's subject arriving inside a fix.** The first cut of the E1 repair closed **one
of eight** cells: the panel's summary line composes four numeric operands and `_num` renders **absent**
and **blank** alike as `0`, so each operand has two not-carried forms — and the cut guarded one
operand, in one form, at one site. The first cut of the E2 repair carried the JS guard across, as
above. **Neither was visible to the suite: it read 2008 passed / 0 failed on the revision carrying
both.** That is the finding, not an aside — the pins sampled the values the fixes moved *to* and never
the values they moved *away from*. So both were repaired in **code** (a `_recorded` helper applied per
operand; a guard condition that names its claim), and **E1-e** and **E2-c** were added to sample the
sets that were missed. Because the harness moved, all six mutation trees were rebuilt and re-measured;
that re-run also caught a **build** error rather than a count — one tree had been assembled from a
sibling's edited file, so it was the union by construction and its recorded number belonged to a
different tree. The spec now defines every tree by its **edit set**, since `diff -rq` reports which
*files* differ and never which *edits*.

**Three of the eighteen pins came from a third review pass, and the pass's most useful result was
that two of its own new checks were mislabelled.** The three are **E1-f** (the remedy and the `✓` are
one decision), **E1-i** (the no-`budget` fallback read a literal `1200` no producer writes, so a
record comfortably under the real budget was told the gate had gone unmet) and **E2-f** (the port
carried the HTML's `− n_day_spread` term across after dropping the guard that made it a no-op, so a
30-row count rendered a 20-row line). Each is bound by a mutant that restores exactly the one edit it
guards and reds **exactly** that check and nothing else — a one-to-one map, which is the strongest
form the repo's pin rule takes.

The two mislabelled checks are the finding worth keeping. **E1-g** shipped as `(GUARD)`, "pre-fix code
passes it too"; measured on the true pre-fix pair it is **red**, and red on a *different conjunct* than
the `0 <` bound its name carries — that conjunct belongs to E1-e's repair. **E1-h** shipped as `(PIN)`;
measured it is **green** on pre-fix code and red in exactly one of the four (renderer, producer) cells,
the one where a fixed renderer meets a rounded producer — because the pre-fix renderer read the `lever`
the routing had just written and so could not see the operand at all. The defect it pins was *masked by
exactly the confusion the cycle removes*, which is why it cannot be a pin on pre-fix code and must not
be labelled one. Both labels now state the measurement. A tier token in a check name is a claim, and
this cycle's whole subject is claims nobody re-checks.

**That class turned up a third time, on seven rows that were not new.** The E5 seven were moved into a
loop of their own because the loop they were added to stamps **every** label it prints
`(v0.1.12 full nested pin)` — so seven checks introduced in **v0.4.34**, and deliberately built as
**guards**, were printed as v0.1.12 **pins**. The file already contradicted itself twice: the comment
above those rows calls them GUARDs, and so does the suite's own D6 accounting. Only the printed line
was wrong, which is exactly the surface a reader counts. They now carry `(GUARD)` and the revision
that added them. The check **count** is unchanged — this was a label repair, not a check change, and
saying so is the point: the suite still reports 2017.

It was found by a census whose **own regex was narrower than its claim** — the third instrument of
that shape in this pass, after E1-b's normalizer and the red-set extractor that keyed on a summary
field that does not exist. The census looked for a tier token *first* in the parenthetical, so it read
E1-e and E3-b's `(CENSUS PIN)` as "no tier", so it reported a pin count **two short** of what this
entry claims — the two rows it cannot see are exactly the two it misreads. The claim was right and
the census was wrong — the same shape as the seven rows it was built to check.

The same pass measured the sweep §3.1 had quoted as testimony: the 324-state cross-product is now
stated with its axes, and the repair's claim is stronger than "the bad states are gone" — on the fixed
tree **no** state emits two verdict lines, where pre-fix 18 emitted a remedy beside a success and 72
emitted two or more.

The regression guard is this cycle's own debt, called out as such: the first cut of the E3 repair
moved the node row's `[:18]` slice onto its fallback literal, silently un-truncating the column, and
no other check noticed — including the E3 census, which reads exactly that expression's *source form*
and passed on the broken revision. A check that cannot fail pre-fix is a guard rather than a pin; it
is labelled with the revision it *is* red on (the intermediate one) instead of implying pre-fix, and
it is aimed at the render's **output**, which is where the defect was visible at all.

**A fourth pass then ran over this cycle with two lenses, and it found ten defects — not one of them a
fabricated figure.** Every one is the class this cycle names: a correct number or fact paired with the
**wrong operand**, or an enumeration that no longer covers what it names. Twelve prose sites across six
files, and **three live-code repairs**, one of which is the only part of this cycle a user sees in the
archive.

**The archive's evidence tree spelled a share as its full binary expansion.** `dashboard.sections.js`'s
`capturedTree` ended in a bare `String(v)`, so the one leaf a record genuinely carries as a ratio
shipped into a `<dl>` of small integers as `0.49975012493753124` — while the ASCII twin spells every
number with `_g` (`f"{n:g}"`, six significant digits). The two views disagreed on exactly the kind of
figure this cycle's parity claims are about, and nothing renders both, so nothing could see it. The
repair is `Number(v.toPrecision(6))`, `_g`'s **byte-exact** JS twin, with integers excluded
deliberately: `toPrecision` renders `1234567` as `"1.23457e+6"` where `_g` gives `1.23457e+06` — the
same digits, a different spelling, and a second divergence introduced by the fix for the first.
`v!==Math.floor(v)` is the **ES5** spelling, because the file is ES5 throughout. The check that pins it
samples a value with a long expansion, and that is what makes it a **pin** rather than a guard: `0.5`
would have agreed with itself on both revisions.

The other two live repairs are the `.1%` share above and a **duplicated key**: the mutation-log row
wrote `{"window": AUDIT_WINDOW, …, **diff}` after this cycle had given `audit_diff` that same key, so
`**diff` won a merge in which both sides held the same constant — byte-identical either way, which is
precisely why no reader could see that one fact had grown two sources. **The correction that matters
most is the one the ledger had already certified.** Revision 13 recorded that this cycle's `ci.yml`
comment "states only what was measured here". It did not: the comment said `-eo pipefail` "aborts at
1", a mechanism no run produced, since the probe returns **7** (pipefail yields the rightmost non-zero
stage's own status) and the `1` belongs to Python's exit code. Revision 13 had that `rc 7` in its own
table and wrote a comment naming a different number anyway — **an audit that certifies a comment is
an assertion about a surface the audit did not run.**

**The same shape appeared once more, and it is the finding worth keeping.** The renderer's comment
on the cold state's three conjuncts said "**measured**, deleting `and not _anch` changes the render
for the third state and deleting `and not _cands` changes it for candidates beside an explicit
`n_blocked: 0`". Revision 13 had run both deletions and recorded — accurately — that they leave the
suite **green**. It measured the **suite counts only**. No render probe appears anywhere in the
record, so what Revision 13 established was that the two conjuncts are **unwitnessed**, never that
they are **live** — and a rule nobody checks that also does nothing is dead code, two readings with
opposite remedies. Both halves are now measured, one process per tree: each deletion does move the
render, in exactly the state the comment names, while the all-clear state renders the line in all
three trees — so each injection's change is attributable to its own conjunct and not to a broken
fixture — and only `_n_blocked`'s deletion leaves a check red. **The claim was true in every clause
and had no measurement behind it. It has one now.**

**The measurement was rebuilt, because the triple moved.** Seven files: `dashboard.sections.js`,
`memory_status.py` and `render_dashboard.py` live; `tests/smoke.py` (comments and one label),
`tests/dashboard_fixture.py` (a key order and a comment) and `tests/dashboard_browser.py` (the new
check) as harness; and `ci.yml`, outside the triple. The 13-tree batch was re-run end to end and the
red sets compared as **identities, not counts** — a count says how many moved, a probe says which —
and all 13 trees red the same identities, `75 = 75`. The E1-i2 counterfactual was re-measured against
the revision its label names. This pass added no smoke check, so the suite still reports **2017**; the
browser suite gains the pin above. Two of the corrections are mine to own: the F1 comment's first
draft claimed the new check "cannot fail on the pre-fix revision" while deliberately sampling the one
value where the two formatters disagree (found by injection, not by re-reading the sentence), and a
drafted correction to the spec's own `0 of 104` was **withdrawn on the measurement** — the same
literal appears at two sites, one false and one true, and the true one stays. Two sites sharing a
literal is an argument for deriving each figure where it is used, not for trusting a
search-and-replace.

## [0.4.33] — 2026-09-17

**Patch — a pass that left a gating seeded duty unfilled now fails at the terminal render instead of
rendering as silence. The persist gate gains a PRESENCE family, and exit 3 gains a second
meaning.**

The last cycle staged from the 2026-09-14 audit. A real `dream` persisted a cycle record carrying
**four unmet duties, every one of which drew a blank field**: an empty `session`, an empty
`rigor.applied`, an `achieved_recall` absent beside a present `achieved_index`, and an
`entries[].action` of `added` contradicting the row's own reason. Nothing caught them, and the
auditor's diagnosis is the design: **every cross-block clause in `validate_cycle_record` is of the
form *"two values that both exist must agree"*** — so an unfilled duty is **vacuously satisfied**,
undetectable **by construction**. No number of clauses in that shape closes the class. Design and
evidence: `docs/record-duty-presence.spec.md`.

1. **A new presence predicate, and it is PERSIST-GATE ONLY.** `memory_status.duty_gaps` returns the
   fired clauses from a module-level table, each carrying its own label, detail, remedy and
   severity; `render_dashboard --persist` renders them in a new panel and routes the gating ones
   through exit 3. It is deliberately **not** folded into `procedure_integrity`: that predicate is
   read **per archived cycle** by `render_html`'s embed, which stamps `_integrity` into the payload
   the HTML masthead, the assessment row and the adverse block all render — narrowing it in place
   would have retro-flagged every past record with a blank `session`, forever, under a tooltip
   naming a different cause. The new gate rides the `judged` boundary instead, so **no archived
   record and no seed/preview render can trip it**: blast radius is structurally zero.

2. **The era gate is "present and holding nothing", never "absent".** A record that never had the
   key is a different thing, and abstaining on it is what keeps the clause off the archive. So
   `{"project": "p"}` is silent while `{"session": ""}` fires, and a wrong-typed **non-empty** value
   (`session: 123`) abstains — a mistyped scalar is the container gate's territory, and a presence
   clause that also reported it would double-report another gate's job while claiming to be about
   presence.

3. **Three clauses shipped; three were dropped on measurement.** The gate is `session`
   present-and-blank (**warn — reported, never gates**), `rigor.applied` present-and-blank, and a
   **partially filled** Phase-5 progress trio (`pruned` / `achieved_index` / `achieved_recall` —
   the audited shape). The trio test reads the **contract**: untouched or wholly filled abstain,
   everything between fires, and *filled* means each key holding a value. Its first cut tested a
   key **count**, which a model satisfies by writing three keys and leaving one blank — three keys,
   two facts, and the clause abstains on exactly the shape it was built for. Dropped: a
   `lever`↔`candidates_surfaced`
   biconditional whose converse is false and which is script-vs-script besides; an
   `entries[].action` vs `audit.memory.created` clause with no sound biconditional
   (`audit.memory` is a per-store rollup while `entries[].files` spans all three stores); and a
   `remediation` half-seed clause that measured **0/99** on genuine records in every one of its
   forms, catches none of the audited defects, and — unlike the three that shipped — has **no
   producer path at all**. Their first-drafted form fired on **11 records of the legitimate
   standing-justified seed** (24 of the 34 remediation blocks in the population are that shape).
   `session` is warn-only because `SKILL.md` forbids *fabricated* session ids while the seed says
   to fill it "when known": gating it would resolve that conflict in favour of fabrication.

4. **Exit 3 acquires a second meaning, and the duty arm runs AFTER the arc arm — but the
   procedure-integrity arm before them both still pre-empts.** A record with a duty gap **and** a
   4/6 arc must exit 4 — putting the duty arm first would exit 3 on it, mask the
   arc diagnostic entirely, and route the model into a Phase-3 loop whose remedy does not apply to
   the defect. The rule is scoped to that arm on purpose: "exit 3 must never pre-empt exit 4" is
   **false** of the code, and measurably so — a lazy-skip beside a 4/6 arc exits 3 today, by design
   since v0.1.44. The exit-3 cue branches on which check fired, so a duty gap is answered with
   "fill this field", not "run the verification fan-out". Every enumeration of exit 3 was updated
   with it — `SKILL.md`'s version blurb, its Phase-5 exit-code key and its procedure-integrity
   scope note, `harness-map.md`'s record-side-gates list and persist key, `AGENTS.md`'s phase list,
   and `render_dashboard`'s own exit-code comment. `SKILL.md`'s Phase-5 key also **gains the arm
   order**, because the key's list is a *set*: the same paragraph claimed "arc+unstamped → 4, then
   5 on the re-render" since v0.4.1, and the measured order is unstamped → 5 **first** (the status
   check sits before every record-side gate).

5. **The validator's docstring said "two" value-contradiction checks while more than a dozen had
   accumulated — and the list under that sentence was itself incomplete.** It now enumerates them,
   every row re-derived by an AST census of the function rather than by counting prose, and states
   the family boundary the next reader needs: container-type and value-**wrong** clauses live
   in `validate_cycle_record`, **presence** clauses live in `duty_gaps`. The clauses missing
   from the old list were added; the fix was to complete it, not to soften its claim to be the
   census.

   **So was the corrected count, which is the finding worth keeping.** The census shipped as
   "fifteen rows" and omitted `network.fact_holdings` holder resolution — a *membership* row, the
   same kind the loose "value-contradiction" name hides, and the second time in one cycle that a
   count of this list read as complete while a row sat outside it. Both the docstring and the spec
   table now carry **sixteen rows over 22 warning sites** with a per-row site count, and the count
   is no longer a claim in prose at all: a smoke check AST-parses the function, splits its warning
   sites into shape and value, and reds when the body grows a far-side clause the docstring does
   not name. It reads **three surfaces of that one census** — the body's 22 value sites, the
   docstring's 16 rows, and the spec table's 16 rows summing to 22 sites — plus each surface's
   **11 disagree / 4 membership / 1 absent-dup split**, and follows bare-name calls to a **fixpoint
   over the call graph**, so a clause delegated to a helper counts at any depth. A second check
   guards the instrument's *coverage*: it enumerates every way to write the `warnings` binding and
   reds if any is not the one form the census can follow, because a clause added by
   `warnings.extend([...])` — or written through a helper that renames its parameter — adds a
   far-side site with **every count unmoved**. The reconciliation pair is verified by injecting
   **thirteen** directions on the shipped revision — **twelve RED**: a dropped docstring row, a
   docstring row retagged, the docstring's *legend* retagged, a spec table row retagged, a spec
   `Sites` value edited, a new far-side `append`, delegation at depth 1, delegation at depth 2,
   `extend`, `+=`, item assignment, and a hand-off to a helper that renames its parameter — and
   **one GREEN**: a second case folded into an *existing* `append`, which is the pin's one named
   open limit, stated in the check's own label rather than left to be rediscovered. The third
   census pin covers the direction those thirteen share: a clause worded in *container* language
   lands among the sites the docstring does not enumerate, so the reconciliation count cannot move
   while the raw total does.

**Twenty-three** new smoke checks: eight predicate pins (each firing half conjoined with its
abstention half), five gate pins that fail on pre-fix code (a complete arc with a gap exited 0; so
did the trio's evasion shape; and the three-clause fixture is the only clause count where the
panel's subtitle and its row loop can disagree, which is where a subset-drawing defect was
measured), **two parse pins** added by the review of this cycle's own pin rather than of the code it
reads — the helper now requires the anchored sentence to appear **exactly once**, because a record
whose `project` reproduces that sentence verbatim and self-consistently was measured defeating a
sentence-anchored parse and reporting success for a panel it never saw, and it bounds the capture to
`\d{1,4}`, because an unbounded one let a 4301-digit run raise through `int()` and abort the whole
suite after 705 printed checks (704 ✓ + 1 ✗), leaving 1284 unrun — three labelled **guard** checks for the ordering and gate boundaries, a pin on the
warn-only path (exit 0 *with* the panel, and a cue that no longer says "persist clean" over a
printed ⚠), three census pins reconciling the validator's docstring, its body and the spec's table
— including one on the body's raw write surface, so a clause worded in container language cannot
land outside every assertion — and one check that pins a
**named open hole** rather than a correctness property — an unappendable cycle log exits 0 with the
duty panel already on screen — so that closing the hole forces an update here and in the spec
instead of letting its shape change silently.

**The guards are verified by INJECTION, not by a pre-fix revert.** Only one of the three passes
pre-fix (the preview render, whose condition is an absence); the other two assert the new panel's
presence, so a revert reds them for a reason that is not the property each one guards — the check
text says so rather than letting a green run imply a RED. Measured on this revision, each injected
defect reds **exactly** the check(s) that guard it and nothing else: the predicate restored to its
first-cut key count → the two evasion pins; the duty arm moved before the arc arm → the ordering
guard; `judged` dropped from the panel block → the two gate guards; the severity wire dropped →
the warn-only pin; and the row loop truncated to `gaps[:2]` → the three-clause pin. The two parse
pins are measured the same way, by **single-property** reverts of the helper: restoring
`search`-based first-match-wins → the uniqueness pin alone, and restoring an unbounded `\d+` → the
totality pin alone, reddening *without* aborting because the uniqueness rule catches what the bound
no longer refuses. Reverting both is what aborts.

## [0.4.32] — 2026-09-14

**Patch — the periphery kept its own copies of rules the store already states, so `cm local
rebuild-index` silently undid `cm local archive`, and `--justify-demotion` crashed on the second
run against an unenrolled store.**

The last cycle staged from the 2026-09-14 audit. Its defects share a shape rather than a
mechanism — **a local rule narrower than the canonical one** — which is the same shape v0.4.31
fixed two layers in. The repairs are the constructive form of the repo's weakest-enforcement-site
rule: delete the second site rather than keep two sites in step by discipline. Design and
evidence: `docs/periphery-parity.spec.md`.

1. **`cm local rebuild-index` honors placement — in both directions.** A fact file does not
   record its own *placement* — placement is recorded only by which pointer doc holds the
   pointer — so a rebuild that globs fact files alone treated every archived fact as unplaced and
   wrote its pointer back into `MEMORY.md`, silently undoing the eviction `cm local archive` had
   just performed. Measured on the live store: **2** re-adds — both **completed arcs**, whose
   pointers belong in the on-demand archive the store keeps for exactly that; the two relocations
   relieved **111 est tok** and **0 durable**. The rule is no longer re-derived — the rebuild asks
   what the index places (the canonical `_LINK_RE` over its **pinned** snapshot of `MEMORY.md`;
   `memory_status.index_fact_names` asks the same question, but re-reads the file from disk and so
   re-opens the window the pin exists to close) and what the archive owns
   (`index_admission.archive_index`) — and the direction is deliberately the one that **cannot
   delete**: the plan may decline to re-add an archived pointer, never remove a live one, so a
   stem sitting in both docs is kept. Plan mode now **names** the prevented re-adds *and the doc
   that claimed each one*, and the archive doc enters the plan's snapshot map, because the plan
   reads its contents and the apply transaction must verify the revision it planned against.

   The second direction was found by review of this change and fixed before release. The first
   revision computed *what an archive owns* with a predicate built for a different question
   (`placed_fact_names`, correctly lenient for the drift check it serves), and v0.4.31's loosened
   classifier makes **any** frontmatter-less store-root `*.md` carrying one link an archive — so a
   working-notes file that merely *mentioned* a fact suppressed that fact's pointer from the
   rebuilt index, and the plan reported the omission as an intentional eviction. Measured on
   fixtures: the fact dropped out of `included` while the report named a `cm local archive` that
   never ran, and on the smallest fixture an **empty rebuilt index reporting `ok: true`**. The
   repair reads the archive's own pointer lines — the exact extraction `local_archive` gates its
   own writes on — and where a doc is nonetheless indistinguishable from an archive, the report
   now names it instead of vouching for it. Measured fleet-wide before choosing: **2** archives
   among the store roots and **0** verdict changes under the rejected alternative — re-measured the
   same day at a larger root count and still **0** — so this closes a class with no live instance
   rather than repairing observed damage. The root total is the one figure that does **not**
   reproduce, and its drift is the apparatus's: this cycle's own verification arms mint store
   directories, so it read 437, then 444, then 446 while the archive count and the zero held at
   every reading. Only the stable figures are load-bearing.

   **A third direction, found by review of the guard itself.** Walking every store-root `*.md` to
   classify it means reading it, and that read *raises* on an unreadable path — so the discovery
   loop is guarded, or one unreadable doc aborts the command with a raw message instead of the
   structured `ok: false` + `unreadable` report the fact loop builds. That guard's first form
   **skipped** the unreadable doc, on the theory that skipping hands it back to the fact loop,
   where the store-scan convention already lives. The theory is false for exactly one filename:
   the fact loop excludes `("MEMORY.md", "SHIPPED.md")` **by name**, so an unreadable `SHIPPED.md`
   — the canonical archive doc, the one name this rule is about — was seen by neither loop.
   `archived` then came out empty and the plan re-added every pointer that doc owns while
   reporting `ok: true` and an empty `unreadable`: the original defect, silent, and invisible in
   the one report an operator reads. Measured, one value from the guard's own fixture: an
   unreadable `locked.md` gave `ok: false` / `unreadable: ['locked']`, an unreadable `SHIPPED.md`
   gave `ok: true` / `unreadable: []`. The repair routes the candidate into the same `unreadable`
   report, which fails the plan closed through the **existing** predicate — `--apply` refuses with
   "index unchanged" and `--skip-invalid` stays the operator's explicit escape. The pin asserts the
   write, not the label, because the re-add is the damage. Left alone deliberately: an unreadable
   `MEMORY.md` still aborts, since the rebuild's whole output *is* that file and aborting fails
   **closed** — the two look alike at the call site and are opposite in direction.
2. **`--justify-demotion` survives a registry-less store.** `control_plane.count_probative_after`
   returns `None` *deliberately* when no registry exists — its comment records that a `0` there
   once suppressed a stamp **forever** — and `_justify_remaining` tolerates it. Its caller did not,
   so `int(None)` raised `TypeError` straight through `run_justify_demotion`. Reproduced on the
   production entry point against an **unenrolled** store (a documented, supported state): the
   **first** run succeeds and writes the stamp, and the **second** dies — so the store does not
   merely fail on a cold start, it acquires the very stamp that makes every later run crash. The
   clock's `None` now reaches the documented fallback — which is not one outcome but whatever that
   fallback judges: `already-justified` when no window start postdates the stamp (the measured
   case), a fresh stamp once enough later windows have accrued.

The same pass **extended the SKILL↔TypedDict pin from key names to scalar types**, because the
block could state a type the code did not have: measured *forward*, with `verification.confirmed`
rewritten `0 → "NOT-AN-INT"` against a `confirmed: int` annotation, the suite reported **1952
passed, 0 failed**. That check is a **guard, not a pin** — at HEAD the block and the TypedDicts
agree, so no revert has anything to fail against, and a documentation check's evidence is a forward
mutation of the artifact it reads. (mypy cannot see it by construction: its inputs are the `.py`
sources, and `SKILL.md` is not among them.)

A recorded number was re-derived, and the first two attempts at replacing it were **wrong in a way
that inverted the conclusion**. The staged plan gave the rendered archive as 1,465,823 chars at 55
cycles, extrapolating to ~3.2 MB at the 120-cycle cap. Re-derived: the file is **1,514,984 chars**,
the embedded payload is **1,301,208 chars (85.9%)** and the static shell is **213,776 chars
(14.1%)** — so the payload dominates, and the plan's ~3.2 MB figure is **reinstated** rather than
withdrawn (a file-size extrapolation gives 3.25 MB, the payload-plus-shell form 3.0 MB). The
closure is exact: `_load_template()` is 213,791 chars, the `/*__CM_DATA__*/` placeholder it
replaces is 15, and 213,791 − 15 + 1,301,208 = 1,514,984 byte for byte. What went wrong twice is
worth stating because it is a general trap: the payload was measured as
`len(_safe_embed(assemble_cycles({}, history)))`, an expression that measures neither half —
`assemble_cycles` returns a **`(cycles, total)` tuple**, not the dict the template receives, and
`history` came from the **native log alone** (30 records of the **56** that
`iter_store_cycle_log` merges across three paths). The missing 26 records carry the `diffs`,
`identity` and `budgets` blocks, so the payload read 5× small and the shell 6× large. Naming the
encoder was not enough; the **object** encoded had to be named too. Nothing changed:
`_ARCHIVE_CAP` already bounds growth, and this is a documentation correction.

**A version claim no gate could see, now pinned.** `AGENTS.md`'s plugin table restates each
manifest's version, and the docs gate read neither: its `v`-prefixed sweep needs a `v` the cell
does not have, its currency matcher takes the first match per doc, and a table cell is not the
first match of anything. Measured: the cell read **`0.4.27` at every release from v0.4.28 through
v0.4.31** — four versions, every gate green on each, because none of them reads a table cell — and
rewriting it to `9.9.9` was green too, so it was not merely stale, it was **unpinned**. `tests/docs_links.py` gains `check_plugin_table` (rows matched by
manifest, not by shape, and a manifest with no row is an error rather than a silence), and the
cell is corrected. The same pass corrects two docstring claims in that file that measurement
falsified — the sweep does **not** close "the version-sweep class", and its inline rationale cited
as a bare-matcher mis-fire the one bare site a bare rule gets right — and replaces `AGENTS.md`'s
dev-loop `1795 assertions` figure, stale by 157 (`1795` at v0.4.28 where it was still true, `1952`
at v0.4.31) and stale by construction, with a pointer to the census constant that is printed on
every run.

**Verification.** 14 new checks (`tests/smoke.py` census `1773 + 45 + 125 + 9 + 14`) — **9 pins and
5 guards**. Re-derived on **five** arms, one tree per process, one harness for all five (`smoke.py`
sha256 `033a3a7b…`, verified identical in every arm, and re-verified after the pin labels were
corrected — a label is not a condition, and that third harness revision moved no count, so the
sha quoted is the later one): pre-fix `1056dd1` **1958 passed, 8 failed**
(P1, P4, P5, P6, P9, P11, P13, P13b) · intermediate `c45aa0f` **1960 passed, 6 failed** (P8, P9,
P11, P12, P13, P13b) · intermediate `5072833` **1963 passed, 3 failed** (P12, P13, P13b) · the
branch's own prior commit `4490dd8` **1964 passed, 2 failed** (**P13, P13b**) · fixed
**1966 passed, 0 failed**. The
multi-arm shape is the point: a single-arm matrix would have certified the second-direction defect
as fixed, because that pin is green pre-fix for a reason unrelated to the rule under test — and the
`5072833` arm isolates the one defect review found *in the fix itself*, an unguarded store-root read
that aborted `cm local rebuild-index` on an unreadable file instead of failing closed. That one is
guarded rather than pinned, and the arm is how the guard is shown non-vacuous. Guards are verified
**forward**, since no revert can fail them — restoring the retired ≥3-link floor turns **1955
passed, 11 failed** (including the guard that exists to notice exactly that; P13/P13b correctly stay
green, which is their scope stated as a measurement), and corrupting the
`SKILL.md` block's scalar types still leaves the pre-extension harness at **1952 passed, 0 failed**.
The fourth arm is the one worth reading: `4490dd8` was this branch's head until the guard fix
landed, and re-read as a mutation arm its suite is green on P1–P12 and red on exactly P13 and P13b —
the cleanest statement that those two pin *that* fix and nothing else. The cycle's own
premise was re-checked against the tree rather than against the plan that proposed it: the staged
plan asserted a constraint — *"the tempting fix is a no-op, because `_is_archive_index_text` floors
at ≥3 links"* — that v0.4.31 had already removed, and carrying it would have routed the fix around
a wall that no longer stood. Every live figure is re-measured, and each **names the surface it came
from** rather than implying one: `cm local rebuild-index --json` for the plan, `_rebuild_plan` for
the two rows the CLI report does not carry (`future`, and `snaps` — the latter holds `FileSnapshot`
objects), and a hermetic-HOME reproduction for the double run.

**Not in this release — the same rule, still unfixed elsewhere.** This cycle fixed the periphery
sites that were in its frame and left the rest, because a cycle that widens as it runs is a cycle
whose spec stops describing its diff. These are **named, anchored, and reproducible by reading one
line**, not "known issues":

- **`local_migrate_schema` skips archives by name** (`local_ingress.py`, the
  `f.name in ("MEMORY.md", "SHIPPED.md")` guard in its glob). Two consequences, both wrong: a
  store-root archive named anything else is fed to `prepare_local_fact(..., inject=True)`, so
  `--apply` **rewrites an archive as if it were a fact**; and a genuine fact whose stem is
  `SHIPPED` is silently never migrated. `SHIPPED` is not in `identifiers.RESERVED_STEMS`, so that
  stem is legal.
- **`run_justify_demotion`'s candidate glob skips by the same name** (`memory_status.py`), and
  builds `idx_names` from the same list — so a second archive's stem can be stamped **durably** in
  `.consolidation-state.json` as though it were a fact. The package already states the content-
  based form of this rule (`sync_global.py`'s `archive_stems`, built with
  `_is_archive_index_text`), so the fix is a two-site diff against an existing pattern, not a
  design question.
- **The archive's name is hand-written at four skip sites, and it is not a reserved stem.**
  `local_archive` constructs the archive path itself (the canonical definition), but
  `_rebuild_plan`'s fact scan, `local_migrate_schema`'s glob, and `run_justify_demotion`'s two
  globs each restate the literal `"SHIPPED.md"` by hand, with no shared constant behind them —
  while `sync_global` classifies archives by **content**. The reserved-stem set is itself one of
  the second copies — `identifiers.RESERVED_STEMS` and `sync_global._RESERVED_STEMS` are two
  literals holding the same one name, so a fix that updates only the first leaves the second
  behind. The inconsistency is reachable, not theoretical: neither set holds `SHIPPED`, so
  `validate_fact_stem("SHIPPED")` is **accepted** and `cm local upsert SHIPPED` writes the very
  file the rebuild then hides by name — and a case-variant (`shipped.md`) resolves to the same
  file on a case-insensitive filesystem, which is the self-clobber class `_is_reserved_stem`'s
  docstring was written for and guards for `MEMORY` only. Recorded rather than fixed here because
  the fix changes which stems a store accepts, and a cycle that widens as it runs is a cycle whose
  spec stops describing its diff.
- **`apply_demotion_justify` mints `n_after = 0`** on its `elif` arm — the exact value the
  deliberate-`None` comment in `count_probative_after` records as having suppressed a stamp
  forever. This cycle fixed the `None` path and left the sibling.
- **A text-level `_LINK_RE.findall` can match across a newline** (`[^)]+` includes `\n`), so a
  target split over two lines is seen by a text scan and missed by a per-line one. Measured: **0**
  such matches across every store-root doc on the fleet (**547** at re-measurement), so this is
  latent, not observed.
- **Two more store-scan reads raise instead of reporting**, the same convention this cycle had to
  repair in its own new loop. `local_ingress._rebuild_plan`'s read of `MEMORY.md` itself, and
  `local_ingress.local_migrate_schema`'s read inside its fact glob, are both unguarded against
  the `WriteRefused` that `control_plane.read_snapshot` raises on an unreadable path — so an
  unreadable file aborts the command with a raw message where the store-scan convention (`skip
  unreadable, never abort`) says to report it. Pre-existing, and left standing for the same reason
  as the by-name skips above: the cycle fixed the site it touched and records the others rather
  than widening mid-flight. `_orphans()` was recorded as the fourth such site; these are the
  fifth and sixth.
- **Three verbatim copies of the `](stem.md)` anchor survive** outside the two this cycle
  consolidated: the anchor→cost maps in `session_beacon.py` and `sync_global.py` (the same map
  hoisted twice, each with its own `re.search` over a line) and the mirror-pointer attribution in
  `sync_global.py`. All three are inert for the same measured reason the retired copy was — **0**
  live index lines carry two pointers — so this is a consistency finding, not a live bug, and both
  modules already import from `memory_status`, so the consolidation is free. `memory_status`'s
  `run_justify_defrag` glob is the defrag sibling of the by-name skip above.
- **The archive-placed stems are keyed on the archive's LINK TEXT, the skip on the FILE STEM.**
  The two are equal only because the single production writer constructs its pointer from a bare
  stem; `sync_global._pointer_line` is the one constructor that can emit a namespaced anchor, and
  no production path points it at an archive doc. So an archive entry whose link text differs
  from its target's stem is reachable only by hand-editing, and the rebuild silently re-adds that
  fact — the archive is correctly recognised and pinned, but the skip misses. Latent, and named
  here as an unfixed coupling rather than a live defect.
- **A pointer written as `](stem)` without `.md` is still a grammar split.** `index_admission`'s
  `apply_pointer` accepts both forms; `memory_status._LINK_RE` sees only the `.md` one, so a
  bare-form pointer list is an archive to the writer and prose to the classifier. Pre-existing at
  both ends, and unobserved on the fleet.
- **No check writes a rebuilt index that contains an archived stem.** Every placement pin reads
  the plan (`included`/`future`), which is verbatim what the apply arm writes, so the assertion is
  faithful — but the apply path itself is exercised only by a pre-existing check whose fixture has
  no archive, so a regression in the write half would not be caught by this cycle's pins.
- **`CHANGELOG`'s top heading and `plugin.json` are unpinned by every PR-time gate.** Nothing in
  the repository compares them (the docs sweep never reads the heading; the manifest validator
  never opens the CHANGELOG), and the CI step that does compare them runs on tag push, i.e. after
  the merge. The sanctioned path is safe — the release harness reads its target version *from* the
  heading — so this is a defense-in-depth gap worth one step, not a hole in the release path.
- **The fleet network capture** (the one observability block still hand-pasted rather than
  script-injected, whose beta capture is not enforced) and **the post-persist correction path**
  (the detector fires to stderr and cannot stop the write) remain root-caused and unscheduled from
  the audit that opened this cycle.

Two items this cycle **closes** rather than carries: `AGENTS.md`'s unpinned table cell (above) and
`docs/index-usage-and-budget-ladder.spec.md`'s falsified ≥3-link justification, corrected in
v0.4.31 — recorded here so the staged plan's item is not silently dropped.

## [0.4.31] — 2026-09-14

**Patch — two store-honesty classifiers knew fewer fact shapes than the store holds, so a clean pass
reported four wrong `schema_drift` counts and a remediation docket that named live memory for
deletion.**

The third cycle to land from the 2026-09-14 `dream` audit, closing the two faces that corrupt what a
pass *reports*. The failure direction is the **opposite** of the audit's teeth cycle: those gates
failed *clean* (a false pass); these fail *noisy and destructive* — manufactured findings, plus a
deletion recommendation, emitted on a pass that exited 0. Design and evidence:
`docs/store-classifier-parity.spec.md`.

1. **An archive index is now recognized by the ABSENCE of fact frontmatter plus the PRESENCE of a
   pointer — not by a `≥3`-link threshold.** `_is_archive_index_text` floored at three `](stem.md)`
   links, so an archive doc below that floor was classified as a **fact**, and two consequences
   followed. The archive's own missing frontmatter entered `schema_drift` as a fact's drift — four
   fields overstated (`missing_node_type` 2→1, `index_mismatch` 4→1, `advisory_no_scope` 17→16,
   `advisory_no_origin` 2→1), which alone takes `drift_findings` **6 → 2**; the second root cause
   above takes it to the **1** genuine finding — and, because `archive_docs` came back empty,
   `remediation_triage`'s Stage A, whose own docstring reads *"TRUE orphans … dead weight; **evict OR
   re-index**"*, named **the archive itself**, and — because the archive was never recognized as a
   reference surface — one of the two facts it points at. Acting on that docket deletes the archive
   and the fact whose only pointer it held; post-fix the stage is empty. (The second archived fact
   escaped by accident: a `[[wikilink]]` from a surviving fact reaches it, so it landed in the
   *referenced* stage instead — a rescue by an unrelated edge, never by the archive.)
2. **A LocalFactV1 fact no longer counts as native-schema drift.** `schema_drift` already exempted a
   mirror's stamp block; it did not exempt the second documented contract that legitimately lives in a
   native store — `local_ingress`'s `LocalFactV1`, whose reserved keys exclude `node_type` and
   `originSessionId` *by construction* (the contract does not reserve them; it does not forbid them
   either, and in practice **most marker-carrying files carry them anyway**, since `local_ingress`
   passes non-reserved keys through — which is exactly why the exemption keys on the marker and not
   on the absence of native keys). One live fact was reported as corruption. The exemption keys
   on the contract's own version marker (`local_schema_version`), exactly as a mirror is detected by
   its stamp — not on guessing at key shapes, and not on "fewer findings", so a native fact that
   genuinely lost its frontmatter still reports.

The `≥3` floor was a **recorded decision**, and it is superseded rather than quietly dropped:
`docs/index-usage-and-budget-ladder.spec.md` now carries the measurement that overrode it. Its
justification — *"SHIPPED.md-style archives exceed 3 links almost immediately in practice"* — was
false for the store this product dogfoods (2 links, 536 bytes), and its stated blast radius named one
harmless consequence while omitting both above. The floor also **inverted**: a verdict keyed to entry
count reclassifies an archive as a fact when the archive *shrinks*, which is how the v0.1.76 audit fix
for this exact file had gone silently inert. The residual bound is now a **0-pointer** frontmatter-less
file, which stays a fact and keeps reporting rather than being silently absorbed. The loosening's own
radius is **measured, not assumed**: fleet-wide it changes the predicate's verdict on five files — this
store's archive, plus four domain stores whose `MEMORY.md` carries a single link — and those four never
reach a decision, because every store-root consumer drops `MEMORY.md` **by name** before consulting the
classifier. The change is safe because of those guards, not because `≥1` and `≥2` agree; at the
predicate level they do not.

No consumer logic changed: `remediation_triage`, `placed_fact_names` and every downstream reader are
untouched, because all four corrections follow from the two predicates. Patching the counters
individually would have left the misclassification intact at every other consumer.

**Verification.** 9 new checks in `tests/smoke.py` (census `1773 + 45 + 125 + 9`) — **7 pins and 2
guards**. Re-derived against the pre-fix tree: **1945 passed, 7 failed** (all seven pins), against
**1952 passed, 0 failed** on the fixed tree; both guards pass on *both* revisions, which is what makes
them controls rather than pins. Building the matrix caught a defect in its own pins: one referenced a
helper the fix introduces, so on the pre-fix tree it raised `AttributeError` and **aborted the
harness** instead of failing — taking the evidence for every later check down with it. A pin's
precondition must be satisfiable on the tree it is supposed to fail on, so that pin now states its
claim through a symbol both revisions have. Review found two more pins that did not pin what they
claimed, both fixed here. The shrink-invariance pin called the text **helper** while production calls
the path **classifier**, which adds a 64-byte head read the helper never exercises — so a read-shape
dependence reintroduced there went unmeasured. And **nothing sampled a one-pointer archive** — the
boundary the floor actually moved *to* — so an edit moving it to `≥2` would have kept every check green
while re-opening this release's entire defect class. The suite now samples the floor at 0, 1, 2 and 20.
A third finding was a label rather than a pin: the LocalFactV1 check claimed *"NO native-schema drift"*
while reading two of the four drift counters, so its label now names the two it reads.

**Not in this release.** Two faces of the same root-cause pass remain staged: the fleet network
capture, which is the only observability block still hand-pasted into the record rather than
script-injected, and the post-persist correction path for a record whose claims fail verification (the
detector fires to stderr and cannot stop the write, and `_persist`'s `(commit, timestamp)`
idempotence then leaves a correction no route into the log). Both are root-caused; neither ships here.

## [0.4.30] — 2026-09-14

**Patch — a persisted record's post-state is measured at persist time instead of mirrored from its
own before-state, and a duplicate re-render now heals the whole record into the cycle file.**

The second cycle of the 2026-09-14 `dream` audit. `memory_status.seed_record` wrote a whole family of
`after` leaves from the **same** Phase-0 `ctx` read that produces the `before` leaves, so
`before == after` **by construction** and nothing owned the after-half — the only refresh path was a
prose instruction naming three of the keys, and nothing verified it. Measured on the live store: the
newest record read `1746 / 1746` where the store actually held **1694**, and its `after_bytes=7161`
described a size `MEMORY.md` **never had**. Design and evidence: `docs/record-post-state.spec.md`.

Three changes are user-visible. None of them changes the cycle-record schema, so legacy records still
render and no consumer needs a migration.

1. **A persisted record's `after`-side figures now describe the store at persist time.** The terminal
   `render_dashboard.py --persist` re-takes every store-local measurement — `budget.index.*`,
   `budget.recall_facts.after`, the six store-local `health.schema_drift` fields, and exactly one leaf
   outside `budget`: `remediation.over_ceiling`, which is a store-derived comparison rather than one of
   that block's triage verdicts (those are untouched) — so the same pass can log different `after_*`
   values than it did before this release. That is the fix, and it is also a change in what the
   archived record says. Two consequences are visible in what gets *rendered*: the budget gauge can no
   longer pair a fresh token count with a retired threshold (14 of this store's 55 records carry the
   superseded `1200`), and a red HARD CEILING alarm can no longer outlive the over-ceiling index it was
   raised for. The refresh is bounded to that key set (a record's model-authored blocks, its `before`
   halves and its `marker` are never written), it runs only when persisting — a seed/preview render
   still shows the one honest BEFORE state the product produces — and it **never blocks**: if any
   measurement fails, the record keeps its authored values and one line goes to stderr. The HTML
   archive's two budget constants (`INDEX_TOKEN_BUDGET`, `CLAUDE_MD_TOKEN_BUDGET`) also became live
   references into `memory_status` in this pass: they were unpinned hardcoded copies of a value that
   module owns, so a retune would have silently left the archive metering off a threshold nothing
   else held. That one changes no rendered number — the copies agreed on the day they were written,
   which is exactly why nothing noticed they were copies.
2. **A duplicate re-render now heals the whole record, not just the narration verdict.** When a pass
   re-renders at a `(commit, timestamp)` pair already in the log, a corrected `budget`/`health` now
   reaches the cycle file — the file `render_html`'s `assemble_cycles` prefers. The log does not grow
   (idempotence is unchanged), and the row count can *fall*: the heal stamps a file whose
   `marker.timestamp` was empty, so a dream the archive was embedding **twice** now appears once.
3. **One new warning on the record validator** (stderr; like every warning there, it never blocks).
   `budget.index`'s token delta must equal the `token_delta` on the audit's own row for `MEMORY.md` —
   both operands are already in the record, so the check is pure and zero-I/O. It fires at render time
   on the record being rendered, which is the only moment a correction is still possible. Measured
   over the archive: **6 of the 31** records whose operands are checkable, **5 of which predate this
   pass**; the other 24 are not checkable and stay silent rather than passing.

**Verification.** 23 new checks in `tests/smoke.py` (census `1773 + 45 + 125`) — **11 pins and 12
guards**, where every pin is re-derived to fail on pre-fix code by running the suite inside a
`git archive HEAD` tree, and each guard is labeled with the revision it *does* move on. The mutation
matrix is in `docs/record-post-state.spec.md` §3; building it is what caught one of the checks
asserting the right thing about the wrong subject, and running the five checks added by the last
review round caught two more — a fixture that never reached the arm it was written for, and an
assertion on a warning *count* that passed on a revision which warned from the wrong arm. The 23rd
came from auditing the branch's own claims, and it is the only one of the 23 whose subject is a
*check* rather than the product: a v0.1.66 check **named** "a live reference, not a hardcoded copy"
while its condition compared values, which a copy passes. Reference-ness is a property of the source,
so the new pin parses `render_html`'s AST — and the equality half, widened to all three constants,
stays beside it as the drift half, proven separate by a mutation that prints ✓ on one and ✗ on the
other.

**Not in this release.** The stale `AGENTS.md` version cell and the three structural blinds in
`tests/docs_links.py` are split off by decision (spec §6) and ship separately. `tests/docs_links.py`
exits 0 on this tree **because of** that blind spot, not because the docs surface is current.

## [0.4.29] — 2026-09-13

**Patch — the dream passes' gates mean what they claim: the checked set cannot shrink, an empty
narration is a gap, the extractor anchor anchors on execution, every documented invocation runs,
and an unknown flag is a usage error on the four lax scripts and `cm`.**

A full audit of the `dream` pass found **one structural defect**: every gate was
narrower than the rule it was believed to enforce, and each failed in the **clean** direction. The
**six** faces of it that sit on the dream's own gates are enumerated **C1–C6** in
`docs/dream-teeth-coverage.spec.md`, and all six are closed here; the audit's remainder is staged
behind this release. The
severest is measured rather than inferred — a record whose every narration slot is `*`, scanned
against a transcript containing **zero** text blocks, returned `NAR verdict: VERIFIED` /
`7/7 narrated · extract_signals.py executed in-window`. The teeth that exist to guarantee the dream
narrated its beats certified an empty narration, and the spec they implement says the opposite in
two places, with *Uncertain → fire* as its own tie-break.

**The new failure modes are user-visible, so they are listed explicitly.** Everything below is a
gate that was *supposed* to fire; a pass that previously exited 0 with a fabricated or absent
narration will now exit non-zero. Nothing changes the cycle-record schema, so legacy records still
render and no downstream consumer needs a migration.

1. **A non-string or blank beat or stanza now fails the dream arc** (exit 4, naming the index).
   `arc_completeness` counted `len(beats)` and `str()`-coerced `sleep`/`wake`, so `beats: [null]*6`
   and `sleep: [1]` were "arc complete" while the dashboard green-checked `✓ 6/6 beats`. By the
   spec's own precedence rule the record-side arc owns the render, so a malformed-beat record that
   used to show a narration gap panel now shows the arc panel instead — the one item here that
   could be mistaken for a loss, and it is the intended precedence.
2. **A stanza that normalizes to empty is now a narration gap** (exit 4), not a silent pass.
   `_gaps` did `if not needle: continue`, so `"*"`, `"***"` and `"> "` left the check while staying
   in the numerator — a label count wearing a coverage claim's clothes.
3. **The checked set cannot shrink.** A beat that is `null` or `{}` used to *leave* the set rather
   than fail it, and with the set empty the verdict fell through to `missing == [] and accounted` —
   `verified`. A present-but-unusable stanza now enters the set and fails.
4. **An emptied dream block now carries a `narration` block reading `failed`**, where it carried
   none. This is the case that made the archive's documented *"absence means pre-feature"* read
   false: `None` (no dream block, the legacy carve-out) and `[]` (a dream block with nothing usable)
   were collapsed into one state. The two are now distinguishable, and only `None` is a carve-out.
5. **A dreamless record carrying any post-mandate key now fails the arc at `--persist`** (exit 4).
   Deleting the `dream` key bypassed both arms. Records carry no version stamp, so legacy-vs-skipped
   is decided structurally: **seven** keys were introduced strictly after the v0.1.54 arc mandate —
   `usage` · `demotion` · `distill` · `workflow_proposals` · `identity` · `narration` · `preflight`
   (`_POST_ARC_KEYS`) — so a record carrying any of them cannot be a pre-mandate artifact.
   Measured over the 55-record archive, this narrows exactly **one** record — a genuine
   fully-skipped arc, whose neighbours on both sides carry a dream block *and* those keys.
   The archive, the standalone render and the validator keep the old default, so no archived
   display retro-flips. The `--persist` render's own **⚠ arc panel** does assert the strict rule —
   it rides the same `judged` flag as the exit beside it — while the permissive ✓/✗ DREAM ARC row
   on that same screen is a different call site and keeps the default.
6. **The extractor anchor now anchors on execution.** Its docstring already claimed this; the
   implementation was a regex matching the token across any whitespace. So `echo python3
   …/extract_signals.py --json`, `python3 -c "open('…')"`, `python3 -m py_compile …`,
   `grep`/`cat`/`sed` against the script, and a heredoc *being written* to a file were all
   accounted as "the extractor ran". It now unfolds line-continuations, splits on unquoted
   top-level separators, tokenizes, and asks whether the interpreter actually runs the script.
   Measured against the 14 legitimate forms the old anchor handled: **all preserved**.
7. **An unknown flag is a usage error (exit 2) on `extract_signals`, `memory_status`, `preflight`,
   `render_dashboard` and `cm`.** Previously each skipped the token, mis-slotted it, or forwarded
   it, so `memory_status --jsoon .` printed a full report and `preflight --jsoon` preflighted a
   project directory named `--jsoon`. The rejections include:
   - **`--persist=DIR`** — today exits 0 while silently degrading a judged terminal render to an
     unjudged preview, because `judged` keys on the parse, not the meaning;
   - **`--persist ""`** — the falsy-persist hole: no gate, no exit, exit 0 reading as persisted;
   - **`--persist <dir that does not exist>`** — now exit 2 where it exited 0 with a `skipping log`
     notice, i.e. every terminal gate skipped under cover of a clean exit;
   - **`-h`/`--help`** on the four scripts, three of which exited **0 doing something else
     entirely** (an extraction of CWD, a status report, a preflight of a dir named `-h`);
   - **a bare `--width`**, which no script consumes — `_ui.resolve_width` matches `startswith
     ("--width=")` only, so blessing it would bless a silent no-op. `distill_scan.py`, the
     precedent, already rejects it.
   `cm`'s `-h`/`--help`/`help` are **unchanged** (a dispatcher with a real help arm is the
   deliberate asymmetry), and `cm <unknown>` now exits **2 with usage on stderr** instead of
   returning the last command's status — 0 — and reading as success.
8. **A *relative* `--persist` now works**, landing on its absolute twin's slot, where it previously
   crashed with an `IdentifierRefused: invalid project id ''` traceback. The one item here that
   makes a previously fatal call succeed.
9. **The documented commands are repaired across `commands/*.md` (8 files) and `SKILL.md`** — the
   bash blocks had malformed invocations: a quote opened before `${CLAUDE_PLUGIN_ROOT}` and closed
   nowhere, unquoted `<…>` placeholders that bash reads as **redirections**, and compound commands
   that silently ran only their first part. Every documented invocation now parses and runs. The
   suite pins this with three arms — `bash -n` per block *and* per line, no unquoted placeholder,
   and every flag a script's own parser defines — because a syntax-only gate passes six lines of
   `cm-domain.md` while every one of them is wrong.

**The flag arm judges more than it did, and getting there took three oracles.** Its predecessors
each answered a narrower question than *"is this flag defined"*: a scrape of `--flag` literals out
of the script's **source** (a flag named only in a comment counted as defined); `"unknown flag" in
stderr`, which fires on the five custom strict parsers and **nothing else** — measured, **25 of 35**
pairs were silently blessed; and the exit code alone — **20 of 35** defined flags exit 2 when passed
without their value. The oracle that replaced them runs the script with a flag and again with one
character of it mutated, collapsing every flag-shaped token so that a usage banner listing legal
flags cannot be mistaken for recognition. Three things fell out of building it: the arm read
**physical** lines, so every flag past a backslash wrap was skipped — including `--persist`, the
skill's most load-bearing flag — and assembling continuations moves its subject from 35 to **45**
pairs; and the probes ran against the **live** store, appending to the real ops journal, so they now
run in a throwaway HOME/config/plugin-data tree. **23** pairs are carved out by name (`cm_ops.py` 9,
`sync_global.py` 14) leaving **22** judged across 7 scripts, and each carve-out is self-justifying:
it names a token its own usage prints as accepted that the lone oracle calls undefined, so repairing
either parser turns the pin RED until the carve-out is removed.

**Two counts that look like one.** The documentation repair covers **77** command lines
(`commands/*.md` + `SKILL.md`) if you are counting the population the malformation census was taken
over, and **87** if you count all ten documented files, which is what the pin's subject is — the pin's
floor is set at 77 for a different reason (an empty glob must not pass every arm). Both are correct
counts of different subjects, they sit in the same file, and they are `77` and `87` rather than
"about eighty". The repair is also measured to change **no** line counts (47 / 77 / 87, identical
pre-fix and post-fix), so it was an in-place rewrite and nothing was dropped in the doing.

Also in this release: the narration reason's numerator is now coverage rather than a label count;
`render_html`'s and the validator's use of the arc predicate are unchanged by design; and the
`_ui` visual vocabulary is enforced at its source (`distill_scan.py`) as well as at its copies.

## [0.4.28] — 2026-09-13

**Patch — the firewall's ReDoS guard is re-based on measurement: a CPU clock, a bound derived from a
stated rule, and a structural pin for the one arm no timing bound can reach.**

The v0.4.27 release PR came back **six red**. Triaged by job *conclusion* rather than by the checks
table, it was **one** real failure — `test (python 3.8)` — plus five siblings GitHub **cancelled**
under the matrix's implicit `fail-fast`. Re-running the identical commit gave 13/13 green.

**The guard was the defect, and two causes are now measured.** It bracketed its scan in
`time.time()` — WALL time — so every descheduling landed directly in the reading: the JWT payload,
the one that flaked, inflates **17.7×** under load on wall against **5.8×** on
`time.process_time()` over the identical scan. And its 2.0s bound left 2.2× over that payload
(0.891s here), not the "deliberately loose … ~0.005-0.19s" headroom its comment claimed — the JWT
payload is 4.7× the top of that range, so a 2.3× slower runner trips it, which is what CI did.
(Both figures are **wall-clock**, because that is the clock the old guard read — and the qualifier
matters: over the identical scan, load inflates wall 17.7× against CPU's 5.8×, so "2.3× slower" asks
far less of a *machine* than it sounds. The new bound's margins are CPU-clock.)

The bound is now **derived, not chosen**: a payload is admitted only if each side's margin
`sqrt(M/S*) ≥ 2`, where `S*` is the worst shipped CPU time under a standard stress load and `M` is
the **weakest** owning mutant's idle CPU time; the bound then sits at their geometric mean, so the
two margins are equal **by construction** and the rule reduces to exactly "both margins ≥ 2×". (It
was written as `≥ 4` while making that same claim — which cannot hold, since `sqrt(M/S*)` *is* the
margin — and the slip disqualified two payloads that satisfied the 2× intent.) `S*` is a worst case
over a distribution, so it is measured **worst-of-three-batches × seven trials**: read once, dotted
gives 0.0627 against 0.2360 across batches, and a bound derived from it would have left only
**1.10×** against a reproducible reading — thinner than the 2.2× that made the original guard flake.

- **The ratio design was measured and dropped.** `t(4n)/t(n)` was the first design — attractive
  because it cancels machine speed — but it cancels only a *uniform* scale factor: under load the
  shipped ratio's tail reaches **10.34** while the weakest mutant reads **11.21**, overlapping
  distributions. Absolute separation at the same payloads is **4.6×–883×**.
- **The JWT arm cannot be pinned by time at all.** Its blowup is `occurrences × sweep` with `sweep`
  capped, so separation grows only `~0.37 × (n/cap)` — the bare `n/cap` model over-predicts by
  ~2.8× — and by n=24000 the shipped scan *under load* (1.20s) already exceeds the pre-fix scan
  measured *idle* (0.94s). The rule divides mutant *idle* by shipped *loaded*, which at n=48000 is a
  margin of **1.16×** against the 2× floor. The window is empty, not narrow — so the guard pins the
  arm's **source text** instead. It took three review rounds and **six** one-token evasions to land
  there, and the endpoint is a behavioural check plus a pin that asserts the arm *is* the shipped
  text, byte for byte. Both are load-bearing, and the matrix is what says so: the behavioural check
  measures **294–298×** separation on the ambiguous shapes, and the pin catches rows the behavioural
  check is measurably blind to. "Would either have read green forever while pinning nothing?" was
  asked of both, with measurements rather than intent — a check that advertises coverage it does not
  have is worse than no check.
- **The pin v0.4.27 shipped was evadable three ways, each a one-token edit.** It scanned the source
  with `re.search(r"eyJ[^|\n]*")` and split on the first `#` — a naive scan that does not model
  `re.X`, and all three evasions live in exactly that gap: a **newline** after `eyJ` (whitespace is
  insignificant to the engine but fatal to `[^|\n]*`, and at 105 lines this pattern's house style is
  to wrap), a **`(?#…)` group** there, or a mention of `eyJ` in an **earlier arm's comment**, which
  makes the scan pin the comment and never examine the arm. Each restores the full blowup with the
  pin reading green. The replacement strips `re.X` comments the way the *engine* does — unescaped,
  outside a character class, plus `(?#…)` groups — before splitting the alternation, and requires
  exactly one arm to carry the anchor. Measured: the old predicate reads PASS (evaded) on all three;
  the new one trips on all three.
- **Then a fourth, fifth and sixth — and the pattern in them is the finding.** The class-aware fix
  above still **discarded its class tracking at the split**, so a `|` that was a *member* of a class
  split the arm anyway: `[A-Za-z|_]` — a class whose third member happens to be a pipe — cut the arm
  at 36 characters and left the open quantifier `[A-Za-z0-9_-]*` in the **discarded tail**, past the
  truncation. Review found two more at other syntax sites: a `|` inside a **group**, and a `]` in
  **first** class position, which CPython reads as a literal member rather than a close. The in-class
  pipe is the worst regression in the whole cycle's evidence — **225× the shipped scan at n=1500,
  1604× at n=6000**, growing faster than quadratically — and it is squarely *inside* the scope the
  pin claims. The shipped pattern carries **0** in-class pipes, so no verdict on real code was ever
  wrong; the holes are reachable only by mutation, which is exactly why they survived a cycle *about*
  this defect class. Six rounds, six different unmodelled syntax rules, six false passes. That is not
  a bug tail, it is a **wrong design** — and the next bullet is why.
- **The pin now asserts the arm's TEXT, and that is decidable.** A scan that reads an arm and returns
  a *verdict* about linearity cannot be made correct: `eyJ(?:[A-Za-z0-9_-]{8,2000}){8,4000}` is
  catastrophic with **every quantifier bounded**, so no scan of the source can decide the property,
  and every hole in such a scan is a false pass. Asserting the text is decidable, and it makes the
  scanner's own bugs fail **safe**: a missed comment, a missed class close, or a `|` split in the
  wrong place can only produce a string that **differs** from the literal. A false pass now requires
  the branch to be byte-identical to the shipped branch. Exactness also subsumes what the previous
  half did one property at a time — the open-quantifier scan, the three-cap substring test, cap
  order, cap adjacency, charset edits, appended groups — and the class **fold** is gone with it: a
  fold is a lossy reading, and `[A-Za-z0-9_-]` folded to `C` is indistinguishable from `[a-z]`.
  **Depth is deliberately not tracked**, and that is measured rather than assumed: the whole
  alternation is wrapped in `(?:…`, so every branch sits at depth 1 and a depth-0 split collapses all
  48 into one 12 868-char arm, which trips on the shipped pattern.
- **22 cases, of which six are the ones the previous pin could not see.** Against the pinned
  revision `c8f4012`, **six rows read PASS there and trip here**: a starred group before the capped
  segment, a `]`-first class, the **three caps permuted** between segments, a **widened cap hidden
  behind a comment mention**, newline + a starred group, and the nested-bounded mutant. Two of those
  are not evasions at all but plain errors the old pin could not express: the caps are a *set* to a
  test that checks each one is present, and a permutation keeps every member; and a comment mention
  ahead of the arm reintroduces the third evasion — so the previous revision's "widening is now
  caught" claim held only for a widening that nothing else was hiding behind. Every mutation asserts
  its edit applied **and** that the subject was the full pattern: an edit assert alone does not catch
  a wrong *subject*, since `SEG.replace(SEG, X)` legitimately applies. And each evasion token is
  tested **twice** — alone (which must PASS: a newline after `eyJ` is insignificant under `re.X`, so
  demanding a trip there would be demanding a false alarm) and paired with a restored blowup (which
  must trip). They are compound evasions; testing only the first half had passed for coverage.
- **Five checks now — three behavioural and two for the eyJ arm — each failing on a *measured*
  revert.** Every mutant has a named detector, and the eyJ mutant is caught by the pin **alone**,
  with the behavioural check measured **inert** on it rather than merely silent (1.00×/1.00×/0.95×
  separation on the other three payloads too). Pre-fix figures are interpolated into the check names,
  so a failure is self-diagnosing, and a dead clock fails too (`0.0 < dt`) rather than making every
  bound vacuously green.
- **One limit recorded, and one former limit closed.** Every payload is a non-matching probe — a
  matching probe was built and measured *non-discriminating* (3.59s pre-fix against 3.93s shipped),
  because the two versions scan it by different routes. The former limit, **cap widening**
  (`{8,2000}` → `{8,9000}` grows the sweep 4.5× while leaving every quantifier bounded), is now
  caught by exactness — and closed in two constructions the older "all three literals are present"
  test accepted, a widening behind a comment mention and a **permuted** cap set. That costs a
  false-positive mode worth naming: any edit to that arm now fails the check until the text is
  re-measured, including a legitimate **re-tune** of a cap. That is the intended prompt — the spec
  requires a re-measurement for any cap change — but a reader should know the failure may mean "the
  cap moved" rather than "the cap is open". The limit that remains is **scope, and now only scope**:
  the pin examines the anchor's branch *by construction*, so an open quantifier in a different arm,
  or in a new **sibling** branch, has no structural detector — only the behavioural payloads, and
  only if that branch blows up on one. This gap got *narrower* this cycle rather than wider: the
  revision before it read "a pin's coverage is bounded by its extraction, and an extraction is a
  parser; this one was a parser with a hole in it", and exactness removes that failure mode, because
  there is no reach left to get wrong — only a comparison.
- **One failure mode is recorded as unbounded, and the backstop is the job rather than the code.**
  The behavioural check's mutant family contains an **exponential** member (N1 — two nested bounded
  quantifiers, which blew a 20s cap at k=200), and no stdlib `re` timeout exists to interrupt a
  running search. A subprocess with a timeout would bound it and was **rejected**: it would put the
  spec's slice-and-exec re-derivation out of reach for one check, and every mechanism added to this
  guard so far has become a hole. Instead ci.yml's `test` job gained `timeout-minutes: 15` — it had
  none while its siblings carried 10 — which is ~18× the job's **measured** 50s, so it cannot flake.
  The failure *mode* is safe either way: a mutant the check cannot finish reading is a RED job, never
  a green check. **And a claim about N1 did not survive re-measurement**: an earlier draft of the
  spec listed the nested-bounded family among the things the behavioural check *catches*. It hangs on
  it — and because it runs first, the pin's verdict is never reached in a real run. Corrected at both
  sites; the claim had been written from the design's intent rather than from the measurement.
- **`SECURITY.md` corrected for the third time on this same bullet** — v0.1.12 had replaced "linear
  (no nested quantifiers)" with a disjointness argument it recorded as "same property, accurate
  wording", and that argument is exactly what the four v0.1.70 instances falsified. The third
  correction nearly repeated the error in the opposite direction: the draft asserted "the regexes are
  built from bounded quantifiers, and that is the actual defense" — a **new universal that the same
  pattern falsifies**, since a comment-stripped scan finds **20 unbounded quantifiers** in live arms
  (`\s*`, `\S+`, `\S{8,}`, the vendor-key arms). The bounded property holds **at the four
  instances**, not of the regex. Two further claims fell in the same sweep: `facts_manifest.py`
  *does* cap its fact-body read (4 MiB at `os.read`) — only `sync_global.py`'s shared
  `_safe_read_text` is uncapped, which is pointed given that helper was factored out precisely
  because "copy-paste doesn't propagate a fix". And the draft said the guard proves linearity; it
  asserts a CPU-time bound, which is a different and weaker claim, now stated as such.
- **The JWT arm's bounding comment moved back under its own arm** — a later pattern insertion had
  displaced it so its rationale visually attached to the dotted-token arm — and its figures
  corrected: re-measured **0.012s/0.12s/1.66s** at n=2000/8000/32000, where it had recorded
  0.001/0.02/0.33, i.e. 12×/6×/5× low. Its "~16x per 4x" *shape* was right and its 128000-char
  claim re-verified true, so both are kept.

Design-of-record: [docs/redos-guard-linearity.spec.md](docs/redos-guard-linearity.spec.md) — the
measurement tables, the admission rule with its corrected arithmetic and the `S*` measurement
method, the empty-window proof stated in the rule's own quantities, the coverage matrix with its
recorded gaps *and* the one this cycle closed, the rejected alternatives (the ratio; a behavioral
eyJ pin at n=96000, which does not clear the rule **at all** rather than merely costing an ~84s
failure time; a uniform `n`; a subprocess timeout), and a runnable recipe so every
number is re-derivable rather than testimony — including the pin's **22 cases**, each asserting its
mutation applied *and* its subject before the verdict is read, and the **six `c8f4012`-evaded rows**,
whose evidence is a comparison between two revisions rather than a reading.

**Verification.** **1795** smoke checks (0 failed — census `1750 + 45`, up from `origin/main`'s
`1750 + 43` by **+2**: the v0.4.27 `.dim` guard pin, and this cycle's behavioural eyJ check; the
exact-text pin *replaced* the structural check already there, so it costs no slot), with
`docs_links`, `simulate_accumulation`, `mypy` and the manifest validator green. The guard block
itself was exec'd verbatim — the spec's own recipe — under all five local interpreters: **5/5 green
on 3.10.12, 3.11.15, 3.12.13, 3.13.15 and 3.14.6**. **One** other wall-clock stopwatch exists in the suite — the
commit-subject cap check, ~21× headroom, and load-bearing rather than merely loose (remove the cap
and it reads 8.19s against its 2.0s bound). It is flagged as a follow-up in the spec rather than
silently re-based inside a patch. An earlier draft of this entry said there were two such guards; on
inspection neither of the others is a stopwatch at all — the stacks-cache check compares a stored
timestamp's *age*, and the archive bound counts **characters** — so neither has a clock to switch.

**The interpreter axis was re-measured during release preparation, and a claim did not survive it.**
§2.5's table had been read *one sample per interpreter* — the same defect §3.1 corrects for `S*`,
on a different axis: a second pass moved 3.13's alnum reading by **72%**. Re-measured as a floor over
seven trials × two passes, the spread is **1.24×** rather than 1.42×, and the **"older is slower"**
claim the earlier draft leaned on is gone: the worst reading falls on 3.12.13 for two of the three
payloads, which is neither the oldest nor the newest interpreter here. That claim existed to argue
the axis leans the right way for the 3.8 runner this patch is *for*, so it is **given up rather than
reworded** — the version axis cannot be extrapolated from these five interpreters to 3.8 at all. What
is bounded is the observed spread among the interpreters that exist on this box; 3.8's evidence
remains the CI matrix, which is where the flake was observed in the first place. (Because a ratio
divides two noisy readings and independent noise *adds* in a ratio rather than cancelling, the
tabulated spread is stated as an upper bound on the version effect, not a precise factor.)

## [0.4.27] — 2026-09-13

**Patch — the network map's closed loop: the anchor marks what you clicked, the hover cue stops
repainting it, and the graph gains a way out.**

Reported as *"every click is incoherent; we cannot navigate it or get any information out of any
of the nodes."* Five defects had compounded into one property: **the map answered a question the
user had not asked, then gave them no way to leave.** All five came from `b665ffc` (v0.4.18) and
none was ever asserted against, because the pins that named them asserted a consequence the
broken code also produced.

- **The anchor marked the wrong node.** `data-current` was wired to `truthy(n.raw.trigger)` — the
  *fleet capture trigger* — so clicking `atlas-web` left `atlas-api` stroked, tinted and labelled
  **"This project"** while the heading named the project actually selected.
- **Three same-specificity cascade rules fought.** `[data-current="true"] rect`, `.selected rect`
  and `:hover/:focus rect` are all (1,2,1), so source order decided — and the hover rule, being
  last, won: its `fill:var(--paper2)` **repainted the anchor exactly while the pointer was on it**,
  and on a **selected** node it overwrote both halves of the mark. (Measured in `deepfield`: the
  anchor's `--data` stroke and 1.8px width held — its plate moved, not its mark — while a selected
  node lost `--tint-accent` and `--accent` both.) This was **theme-independent**. An earlier draft
  of this entry said the two shipped palettes ordered these rules oppositely, so one theme was
  coherent and the other broken; that cannot happen. The palettes are `:root[data-theme=…]` token
  blocks of ~430 characters containing no `.net-node` rule at all, and a token-only theme mechanism
  cannot reorder rules — every theme was broken in exactly the same way.
- **Focus was stolen on every draw.** `focus()`'s unconditional `.network-root` `.focus()` ran
  *after* `draw()`'s own `[data-key]` restore and clobbered it; the root's handler is `reset()`,
  so **the next Enter undid the activation**. It is now a fallback that fires only when a control
  *had* focus and nothing inherited it — enforced once, at the redraw, because **two** controls
  are wiped by the very activation they carry: a fact button (`inspect()` rewrites `#net-detail`)
  and the trail's own back-control (`draw()` empties `#net-breadcrumbs`). Only the first passes
  through `focus()`, so the fallback's original home covered the activation someone had noticed
  and missed its sibling.
- **No position and no way back.** `#net-breadcrumbs` was created and cleared but never written —
  `b665ffc` deleted the writer — while its CSS sat intact and idle.
- **Focused views rendered no summary at all**, because `inspect()` rewrites `#net-detail` on
  every draw and destroys the template's seeded text.

**The fix is smaller than it first looked, and measuring that first is the point.** An earlier
draft proposed marking the rendered members; the premise was false. `matching` is
`selectedNodes()` *filtered*, never widened, so **no view can render a node the selection does not
contain** — and marking the rendered members would only say "these are the things you can see".
The one genuine 1-of-N distinction is anchor vs. members, and that mark already existed, wired to
the wrong predicate. Correcting the predicate touches neither `selectedNodes()` nor the render
filters, so **no rendered set changes**: the checks that assert a view renders an exact node set
are green and none of them was edited by this pass.

Alongside the fixes: a **position trail** (`Captured fleet › kind › label`, one control back), a
**selection summary** of at most four paired rows that respects absence ≠ emptiness and never
renders a bare `0`, and a **link out** to the complete record via `reveal()` — newly exported
from `dashboard.sections.js` and guarded on capability, so a bundle without it renders *no* link
rather than a dead one. The legend is now **updated rather than replaced**, so the template's dot
markup is wired instead of orphaned — while `#net-leg-stack`, which shipped `hidden` and was read
and unhidden by nothing, is removed rather than kept as the same fossil under a new name.

Three smaller corrections ride along, all of them strings or regions that had stopped matching
what they governed: the detail region's seeded text promised *"a project **or connection**"* when
connections have no handler; the controls group's `aria-label` still said *"Highlight network
membership"* for a control the group no longer contains; and the inner `.network-explanation`
`aria-live` doubled every announcement with the `#net-detail` live region that already contains
it, including on pager clicks that changed nothing.

**Verification.** 1331 browser checks (0 failed) and 1794 smoke checks (0 failed), with
`docs_links`, `simulate_accumulation`, `mypy` and the manifest validator green. The browser figure
is the shipped tree's, and there are five measured points behind it: **1213** before this pass,
**1264** as the pass committed it, **1309** after the review round, **1329** after the re-audit
round, **1331** as it ships — each one
that tree's own suite run against that tree's own scripts. An earlier draft of this block said
1266, which was wrong.
Fifteen mutation runs: 12 of 13 in the browser suite and 2 of 2 in `smoke.py` went **red for the
defect they claim to guard**. Two of those pins had to be debugged before they could be believed, because **a
vacuous pin reads exactly like a passing one**: the hover pin passed *with the defect in place*
(the anchor was still focused from the click that opened the view, and both rule families bundle the
cue as `:hover, :focus` in one rule, so the "rest" reading was already repainted), and the first draft
of the `.dim` guard listed three literal class spellings — exactly the match-set bug of the pin it
replaced, walked through by a mutation. Neither is in the shipped suite in that form.

A third vacuity turned up in the review round's own work, and is worth naming because it is the
*quietest* of the three: the focused legend pin read the note's text and the keys' count and
hiddenness, but never that the legend itself was on screen — and in a focused view the keys are
hidden **by design**, so no clause about them can distinguish "keys hidden, legend shown" from
"legend hidden". Hiding the whole legend passed it. The pin now asserts the container's visibility,
and the mutation that isolates it — hiding the container only in non-fleet views, since hiding it
outright is caught earlier by the fleet check — turns this pin **red first**, aborting the suite at
check 235. Repaired at the source in `tests/dashboard_browser.py`, so it ships corrected.

The one run that did *not* go red is reported rather than dropped: restoring the **positional**
node focus key breaks no check at all, because the fixture leaves the anchor at the same index in
the fleet and in the project view, so both schemes land on the same node and the suite cannot tell
them apart. The stable key is still the right key — a positional index surviving a repaint lands
focus on a *different* project — but that claim is **uncovered**, and saying so is the point.

**The review round found two defects this pass had introduced.** The first: the trail's
back-control stranded focus on `<body>`. This entry added the control, wrote the invariant it
broke, and wrote the reasoning that hid it — *"the crumb cannot be a focus-restore target, so it
needs none"* — which is true and irrelevant, because the question is what the redraw does to the
focus it holds. Fixed by moving the repair to the redraw, which covers both controls without
touching either. The second: the new crumb had **no hover and no press feedback in any theme** —
it is styled by a `(2,0,1)` selector in the shared control group, which beats the generic
`button:hover` fallback at `(1,1,1)`, so its states had to be declared by name and were not. The
only way back to the fleet looked inert under the pointer. Both now measured: focus lands inside
the widget, and the crumb changes colour, background and border on hover and on press in all five
themes.

The same round found the summary check had a ceiling but no floor: a summary that never rendered
read `0` rows, `0==0` passed, and the check was green against the very defect it was written for.
Both now have pins that go red for them, and the fix for the first cost the second its old comment
— which had called the fact button *"the one activation with no successor"*.

**Six of the holes the round recorded are now closed, each with the mutation that closed it.** The
legend's dot keys can no longer be hidden in every view (mutation: `hidden=true` unconditionally —
1 check red); they can no longer be left showing in a focused view, where the mark they explain
cannot be drawn (mutation: the assignment deleted — 5 red, one per theme); the trail is asserted
for all three focused kinds, not just the project view (mutation: the writer's branch collapsed to
one label — 2 red). The summary's own existence is now asserted in the views it renders in
(mutation: the rows are never built — **13 red from that one edit**, 8 of them the new existence
clause, 4 `concise_network`'s floor, 1 the absence-semantics pin). Three independent pins seeing
one reversion is the property the pin discipline asks for, and it is the one the round could not
previously claim: the clause is red on pre-pass code, not on an invented defect.

**The overflow half needed a different instrument, and the template says why.** `.network-surface`
is `overflow:hidden`, so a map surface that blows out is *clipped* rather than scrolled: forcing
`#net-detail` to `calc(100vw + 240px)` leaves it 1680px wide while the surface reports `clientWidth`
1206 against `scrollWidth` 1706, and nothing reaches `documentElement.scrollWidth` — which is all
the suite's page-overflow idiom reads, so every check in that family stays green against it. The
`report_layout` clause that compares element edges to the surface's padded box caught it at all
four widths, and now runs in the focused pass too, because it was blind in exactly the view where
the new surfaces render. The Range-walk clause beside it is immune to the same clip by
construction — it compares layout geometry, not scroll extents.

**The text-in-box selector list lost three of its five new members to measurement.** A box only
overflows if it is constrained, and both a grid `auto` track and a flex item floor at min-content:
given a 600-character unbreakable token with the wrap rule removed, `.network-summary dt`, the
trail and the legend note each *grew* to fit it (129→3900, 109→3900, 554→3600) — text past their
own box is unreachable, so a check on them could never fail. They were replaced by the constrained
containers that own them, whose boxes held at 1154 while the same token ran 2746–3046 past the
right edge. Recorded here because "the selector is in the list" is not the same claim as "the
selector can fail", and only the second is worth shipping.

**Six claims corrected where measurement contradicted them**, each caught by the round rather than
by a user: `rendered ≡ selected` (it is a subset, strict whenever a domain is collapsed — seven
nodes render as three); the anchor's resting stroke width (1.8px, not the 2.6px hover width);
`M3 fails at deepfield specifically` (it fails in all five — the loop's first theme was read as the
only one); the pre-pass suite size (`1213`, not `1257`); `bytes` for a character count; and a claim
to have *removed* two `.selected[data-current]` rules that never existed at any revision — the
pass added `:not()` guards to two different rules instead. A seventh, `the five anti-duplication
pins stay green untouched`, named a set that could not be identified; it now names the checks.

**Two claims corrected where measurement contradicted them**, recorded rather than silently
restated: `.node-name`/`.node-meta` are CSS with **no emitter** (the live classes are
`project-label` and `project-meta`, whose fill resolves to `--ink2`, not `--faint`), so the `.dim`
contrast table's magnitudes are testimony and must be re-derived — only the split's *direction*
survives; and base Nocturne's node **fill** declarations are shadowed dead code in every theme, so
the anchor is marked by stroke only — resting at 1.8px `--data` against an ordinary node's 1.1px
`--rule2` (2.6px is the hover width every node takes) — judged legible.

**Archive embed budget, measured:** 285,411 → **308,659** **characters**, against a P4 pin
**re-based from 300 KiB to 320 KiB** in this cycle. The gate bounds `len(_html_p4)`, so these are
characters, not file bytes — the two are not interchangeable here, and this entry said "bytes"
until the review round caught it. The previously recorded headroom of 21,789 reproduces exactly,
and the re-base is a measurement rather than a concession: at `1864f68` the same fixture rendered
**307,050** — **150 characters** of headroom, so the pin sat one comment from red — and the cycle's
later rounds then spent it (**6,642** for the re-audit round, **1,609** for the code-review round
that followed, which took the archive **1,459 over**). Trimming the comments to fit was the
alternative and was rejected on the measurement: they correct two claims review had just found
false. The pin's actual subject is the trim, which is worth **292,162** characters — admit the
fixture's two junk keys back into the whitelist and the same render is **600,821** — so 320 KiB
restores the ~19–21 KiB working margin 0.4.24 shipped with while still sitting 273,141 characters
below a junk-untrimmed render. The review round's own share was 2,771 characters — 1,689 in the
redraw's focus repair, 770 in the crumb's missing hover and active states, 297 in the comment
repair that replaced the theme-dependence story with the measured one, and 15 in the wording fix
that corrected a cascade-order claim naming the wrong pair of rules — and the whole cycle's cost,
**23,248 characters, is more than the headroom it started with**. Full trail, with every
intermediate tree named: the spec's §4.5.

**The bytes-versus-characters slip recurred in the sentence that recorded it** — in
`tests/smoke.py`'s pin comment and in the spec's §4.5, whose first draft summed the two files'
**byte** deltas (+460 template, +1,151 `network.js`) to +1,611 and presented it as the archive's
growth. The archive grew by **1,609**: the template's added comment carries one em dash, three
bytes and one character, so its byte count leads its character count by exactly the 2 the sum was
too large by. Caught by re-measuring the two endpoints (307,050 and 308,659) against the per-file
**character** deltas (+458, +1,151), which agree to the character — the check that makes the
figure re-derivable rather than remembered. Fixing the word did not fix the arithmetic under it.

**That last figure is measured on a tree no one had built.** The review round's repairs were
authored in two places — the JavaScript in a pristine copy of the commit, the template in the
working tree — so no single tree held the whole delta, and the assembled state had never been
through any gate: the live suite ran against live-template + pre-review JS, the pristine suite
against pre-review template + review JS, and the two together are not the shipped artifact. An
assembled tree is now built and gated before the commit rather than after it.

**A re-audit round turned on the escape hatch itself, and found one vacuous pin in its own work.**
Seven mutations, each the pre-fix form of one mechanism, run on a non-fatal copy of the harness so
one run exposes every red: **15 red across the seven**, on a baseline of 1326 checks — and re-run in
full against the suite as it ships once the guard arm's three checks existed. Every count
reproduces there except one, and the exception earned its own paragraph below: M20 restores the
`Held by` row, the code-review round rewrote that row, and the re-targeted mutation reds **three**
where it red previously two. **A mutation is identified by the code it restores** — editing the
target silently redefines the mutation — so its count was re-measured rather than carried. The anchor
reversion — this pass's central fix — is caught by **four** checks where the pass's own mutation
recorded one. That is not a pin that weakened; it is fixture shape. A pin can only separate two
predicates on a fixture where they disagree, and the pass's fixtures were built so that the two
anchor predicates **coincided**.

**The vacuous pin was the round's own, and it is the quiet kind.** The focus-repair block asserted
three controls each hand focus back to themselves after a redraw, but it resized to a *fixed* width
inside the loop — and `resize()` waits for the map to reach the new width, so from the second
iteration on the wait returned immediately, no redraw ran, the control was never destroyed, and the
assertion stayed green **against the very defect it exists for**. Only the first of the three went
red under the mutant. The target width now alternates, every iteration forces a real redraw, and
all three go red.

**Three of the round's four guards can only be verified by introducing the defect.**
They assert the network's HTML controls show a focus ring when focus arrives by keyboard. That ring
predates this pass, so no reversion can redden them — and the first two attempts reddened
**nothing**, because the edit went on the rule that *reads* as the control's own. A
`document.styleSheets` walk over the focused record link shows the ring is supplied by the
app-wide `#app button:focus-visible`: the network-scoped rules lose on equal specificity and
earlier source order, the same tie-break that decides the anchor's hover bump, one selector pair
over. Appending `outline:none` *after* the winning rule reddens exactly those three checks and
nothing else. The first placement is not a gap in the guards — it is a defect that never took
effect, which measures nothing about the guard.

**One mutation looked right and proved nothing.** Its first anchor reversion edited only the
*fleet* arm of the predicate, and the paged-anchor pins stayed green — which was first read as a
gap in them, and was not: the pre-fix anchor had **no project arm at all**, so reverting half of a
repair is not reverting the repair, and the pins that stayed green were never asked the question.
Restored whole, the same predicate reddens four, those two among them. Recorded because the wrong
reading was one step away — *"the paged-anchor pins do not catch the anchor reversion"* would have
been written about pins that catch it.

**Two residuals the round leaves uncovered, said out loud rather than rounded off.** The anchor is
still hidden without the legend saying so when the domain is collapsed or the anchor is paged away
— one-directional, uncovered by any pin; and the positional `legacy:`/duplicate-sid focus-key
fallback stays unasserted, for the reason this entry already gives.

**A count the record carries was being reported as one it lacks.** The summary rows route every
value through a two-shape vocabulary — `Not captured` for a field the snapshot never recorded,
`None recorded` for a measured empty — and a value that is *present but not a count* is neither.
`countText()` collapsed that third case to `Not captured`, so a persisted `members_n` of `"2"`
rendered as an absence claim about data the record plainly carries. It is reachable rather than
theoretical: `validate_cycle_record` warns on a wrong-typed key and never blocks, so the record
renders. The repair is the rule the block above it already stated — an unexpected value renders as
itself — and it restores a second property on the way: the zero test now reads the **parsed**
number, so a `"0"` is `None recorded` rather than a bare zero on screen. The `Held by` clause was
corrected in the same pass for the same reason: it said **"shown on the map"**, and the count it
prints is the *selection* — `selectedNodes()` is what the capture resolved, while the map draws one
page per expanded domain and nothing for a collapsed one. The words named a measurement the value
does not make. Both fixes are pinned by reversion: reverting `countText()` alone reds exactly one
check, and reverting the whole `Held by` row reds three, the other two being the label and the
resolved-versus-listed count.

**The preview banner's splice was bounded by an accident, and the check that claimed to gate it
could not fail.** `tests/dashboard_fixture.py` labels the generated preview by splicing a
`sample-notice` div after `<body>`, and `docs/previews/nocturne/index.html` is committed — so a
splice in the wrong place ships. `<body>` is not unique in the built page: the network bundle's own
focus-repair comment carries two of them, so the splice was bounded to the first occurrence. That
worked only by emission order (the bundles are written after the tag), and a `<body>` literal
emitted **before** it — a script or style block added to the head — would have taken the splice
while a count of one still reported success. Measured two-sided on the built HTML with such a
literal inserted in the head: the first-occurrence splice puts the notice **inside the head
script**, 35 characters before the real tag, and the head-anchored `^</head>\n<body>$` splice puts
it at the tag. The fixture now anchors on that boundary and **asserts it matched exactly once**, so
a template that stops emitting the shape fails at generation instead of splicing somewhere a reader
cannot see. The docs gate's companion check — counting `class="sample-notice"` in the committed
artifact — was **deleted rather than reworded**: given the render assert and the byte-compare
beside it, a committed artifact *is* a render, so the count is one by construction and the check
was reachable in no run at all while reading as coverage. Its hole (a render failure surfacing as a
traceback instead of a gate error) is closed where the enforcing assert lives. **Test
infrastructure only** — no shipped code, cycle-record or manifest change.

**A pre-existing smoke flake was root-caused and fixed rather than re-run away.** CI reddened on
`d9ade6e` (`1792 passed, 2 failed`) and then went **green on a re-run of the identical commit** —
non-determinism, not the diff. `_proj23` (`tests/smoke.py`) selected its temp store with
`if name in str(f)` over a glob of every state file under `HOME`; the store slug is derived from
the project path and **embeds the temp dir name**, so whenever the random suffix contains the
2-character fixture name (`pa`/`pb`/`pc`) every store matches, `_mine[0]` is whichever the glob
yielded first, and the fixture writes its population into a **neighbouring** project's store —
whose shape (three equal-sized facts, no outlier) makes `defrag_candidates` return `[]` and that
project's checks fail. Measured at **2.1% wrong-pick per name**; reproduced deterministically under
a colliding `TMPDIR`, where the old filter returns three matches with a neighbour's store first
against exactly one for the slug match. **Test infrastructure only** — no shipped code, no
cycle-record or manifest change — and the `assert _mine` is kept so a future layout change fails
loud rather than mispicking silently.

**A value that is not the shape the code assumes, reported as though it were — twice more.** The
review round above fixed one instance of that class in `countText()`. A parallel fan-out then found
two siblings in the same file:

- **`listText()` joined a list of objects.** `join(', ')` stringifies each element, so an
  array-of-objects group list rendered `'[object Object], [object Object]'` — the output the rule
  eight lines above it forbids in words, and the output the pin beside it was **named** for while
  testing a shape that cannot produce it. The guard belongs on the join, not the stringify: a
  non-empty array never reaches `fieldText()` at all.
- **The fact focus key fell back to a name, which is not unique.** `data-key` was
  `'fact:'+(fact_id||name)`, while the same expression computes `duplicate` to decide whether the
  *label* needs a domain prefix — the code admitting names repeat while the key assumed they do
  not. The redraw's restore takes the **first** match, so two same-named facts left a keyboard user
  on the wrong one, their next Enter opening a record they did not choose. The key now
  disambiguates exactly where the label does — identity, then index — the shape `normalize()`
  already uses for node keys.

Both are reachable only through the name fallback — a foreign or hand-edited record, since the
shipped producer always writes `fact_id` — so neither is a shipped-producer defect. Each ships with
a mutation that reverts it: **M23** (`listText()`) and **M24** (the key), **1 red each**, and each
is the *first* failure in its run. The second is why this round has a pin where the budget item
above did not: reverting the key fix with the pin absent left all 1332 checks green — **a fix
nothing holds is a claim, not a fix.** The browser suite went **1331 → 1334**; two are the pins and
the third is a *preview render* (`render without errors: focus-duplicate-keys.html#sel=0`), because
a new `fixture()` writes a new preview and the suite renders every fixture it finds. Recorded
because the arithmetic is +2 and the suite says +3.

**The fan-out's verdicts are dated, and triage is the work.** Seven of its findings were refuted by
the tree they were aimed at — most were measured on `1864f68`, the revision *before* the fixes they
reported. Each refutation is a measurement: `countText()` and the `Held by` clause quoted as live
both quote source that no longer exists; the preview-splice check that was "still open" was deleted
in the same commit; the legend's 7px gap was real but had already been repaired, by the very
`e15ac3e` change whose comment describes the descendant match the finding reports; and two
`file:line` spec citations reported drifted are part of a set the spec no longer contains at all —
counted, `[a-zA-Z_0-9]+\.(js|py|html|md|json):[0-9]` → **0 hits**. §4.9 records the triage. The
lesson is not that the fan-out was wrong to run — it found both of the real defects above — but
that **a verdict is a claim about one revision**, and re-reviewing a tree that has already moved
reports the past.

The archive grew **308,659 → 309,802** characters — measured at both endpoints, not reasoned from
the diff — nearly all of it the two fixes' comments, leaving **17,878** of the 320 KiB bound.

Design-of-record: `docs/network-graph-interaction.spec.md`.

## [0.4.26] — 2026-09-12

**Patch — the cross-domain mirror index refresh: one root cause, two legs, four sites on the
write/accounting dependency — plus the `--gc` dead-probe.**

`_mirror_key(ctx_domain, fact_domain, stem)` returns the bare stem for a same-domain fact
and `f"{fdom}--{stem}"` for a cross-domain one, and that single value is **both** the
fact's filename and its index anchor. Four sites on that dependency derived a different
quantity — the bare stem — and got it wrong, in two directions:

- **Leg A, the write path.** `apply_pointer` matches `]({stem}.md)`, so a namespaced href
  never matched the bare stem it was passed. Every cross-domain refresh **appended** a
  duplicate index line instead of replacing in place — and on a MISSING delivery it
  **evicted a same-stem native pointer**, deleting a local fact from the always-loaded
  index while its file survived on disk. The line count did not move, which is why the
  first draft of the spec read the whole delivery path as unaffected. Both write sites
  (the plan loop and the execute loop) now pass the same anchored value; they must agree
  or the executed write diverges from the planned one.
- **Leg B, the read path.** Both cost maps are keyed by the link *target* (the namespaced
  anchor) and were looked up by the bare stem, so `cost_old` pinned at `0`. One confusion
  made two failures: the MISSING arm booked a **full line** (`cost_new - 0`) for a refresh
  where only the replaced delta applies, holding pulls the index had room for, and the
  STALE arm's `elif cost_old and …` went falsy — the item was **never built at all**, out
  of the projection rather than merely mis-costed. Pre-fix the first error was invisible
  precisely because it was accidentally right: the writer really did append a full line.
  Fixing the matcher alone flips that append into a replace and moves the write underneath
  the unchanged model — measured on the §1 fixture, **+27 tok booked against a real +4** —
  which is why the writer and its accounting model ship as one change.

Two findings from the adversarial review round, both on the read side:

- **The `--gc` dead-probe asked the wrong question.** It classified a mirror as dead by
  testing for a file keyed by the bare canonical stem; for a live cross-domain mirror that
  file cannot exist, so a **live** mirror was reported dead. The probe now derives the key
  the way the writer does, and an *uncomputable* key (a `--` ambiguity) is treated as
  unknown rather than dead — that arm must not guess.
- **A phantom refresh delta, introduced by the first cut of the Leg B fix.** Anchoring
  `cost_old` while leaving `cost_new` bare made the two differ by the anchor text for an
  **in-sync** cross-domain mirror, firing the STALE branch for a mirror that needed no
  refresh. The condition was not even drift-gated: the anchor adds ≥3 chars, which moves
  `ceil(chars/4)` on a line of pointer length, so the phantom row was the **steady state**
  for every cross-domain mirror carrying an index line. Its delta is **negative**, and
  `_plan_pull` *adds* deltas — so it **relieved** the running index and **under-stated**
  `held`, advertising a missing fact as absorbable that a real `--pull` holds: the same
  divergence class the fix exists to close, re-created by half of it. Both costs now derive
  from one key computed once, so they cannot be derived from different quantities.

**Eleven checks, all measured rather than asserted.** Ten in the v0.4.10 groups fixture and
one in the v0.1.81 near-ceiling beacon fixture — `held` is only observable near the
ceiling, which is why the phantom-delta check cannot live with the others. Six of the eight
in the fix commit fail on pre-fix code; the other two are **guards**, marked as such
because `apply_pointer` and `_mirror_key`'s same-domain arm are unchanged by the fix and
neither *can* fail pre-fix. The gc-DEAD probe (#9) is discriminating too: reverted to the
bare canonical stem, it fails as that run's **only** failure (1777
passed, 1 failed) — which is the placement its first draft needed, since a later fixture's
same-stem native silenced it (§9.1, failure 5). The phantom-delta check discriminates the **half-fixed** state
and nothing else — green on both the fully-fixed and the original pre-fix trees — and its
boundary is measured: the index is padded so the missing fact is held by exactly one token,
and the relief a bare `cost_new` would grant is computed off the two real pointer lines and
asserted positive. **The run side's `cost_new` was the one field nothing read**: the only
assertion on the planner's item tuple was `cost_old` (index 3), so the half-fixed state had
a detector on the beacon's projected cost and none on the run's. The review named both sites
and both were fixed in this branch — but only one was pinned, and only a mutation round
could show it. The new check reads index 2 against the cost of the line the run actually
**wrote** (not a re-derivation), pinning the plan/execute agreement itself; the run-side
revert alone leaves it the suite's **only** failure (1777 passed, 1 failed), and with the
check absent every other one is green under that revert. The suite-total anti-rot constant
moves `1740+27` → `1750+28`.

**Blast radius, measured:** 14 namespaced mirrors across 11 projects, 0 duplicated stems
across 21 indexes, 0 dead index pointers, 0 same-stem collisions fleet-wide — the fleet is
undamaged and the defect is latent, not absent. Repair of an already-damaged store is
refresh-gated and does not cover every shape; §10 of the spec scopes what a single command
can and cannot collapse.

**A third finding, from the same round's pin work — the index line's own sanitizer had an
unguarded interpolation.** `_pointer_line` builds every pointer line, and `local_ingress`'s
sibling writer calls it *"the global injection sanitizer"* in its own docstring. It
interpolates three values from a possibly-crafted store: `name` is fenced upstream
(`_safe_stem`, whose docstring names exactly this threat, and which both row sources apply),
`description` is sanitized in-function — and `scope` was interpolated **raw**, so a crafted
`scope: evil](http://x)` rendered a live markdown link into the always-loaded index line, on 10
of `_pointer_line`'s 12 live call sites (the two inside `canonical_ingress.upsert` sit
downstream of that writer's own scope refusal, so a bad scope cannot reach them). The suffix is
now keyed to the canonical vocabulary (`fact_schema.SCOPES`) and rendered **from the
vocabulary, never from the field**, so it cannot carry anything but a known literal; a
non-vocabulary value is **dropped**, not sanitized — it has no meaning to show. A non-string
YAML value (`scope: [x]`) is a no-op too: pre-fix it rendered `[['user-global']]` into the
line, and the `str(...)` the fix applies before `.strip()` is what keeps the fix's OWN shape
from raising `AttributeError` there instead. `local_ingress`'s sibling writer already did both:
renders from vocabulary, and refuses a bad scope at write time. Four checks; reverted to the
raw interpolation, the suite reddens **exactly those four and nothing else**
(`1789 passed, 4 failed` against `1793 passed, 0 failed` fixed) — the hole had no detector at
all before this branch. The fourth pins the INVARIANT rather than a fixture, because the first
three could not carry the universal their names claimed: an admission widened to a prefix match
(`startswith`) satisfied every one of their fixtures and passed all 1792 checks while
restoring the live link for `scope: user-global](http://x)`; it is now that mutant's sole
detector. The suite-total anti-rot constant moves `1750+39` → `1750+43`.

**A fourth finding, from the same round's pin work — two numbers in the record had rotted.**
Three places said the always-namespacing mutant "kills the suite at `smoke.py:4962`" and that
this was "thousands of checks" before `#8`: the spec's two `#8` paragraphs and the `#8` comment
in `tests/smoke.py`. The mutant was re-run rather than trusted — it does die where they say, at
the `canon-x` fixture's read-back of its own canonical, so `#8` never executes — but the number
held only in the tree it was written in: at `e2a3048` the read-back is at `smoke.py:5085`, +123
as the branch grew, and 983 checks complete at the fixture against 1554 by the time `#8`'s
check begins — **571** checks, not thousands, in a suite of 1793. So the line numbers are
replaced by the target itself (the fixture's own read-back expression, with its hit count
stated), and the quantity by the two check positions that produced it — because a stale line
number fails *silently*, still resolving, just to the wrong line.

The design-of-record, with the review's corrections to its own claims, is
`docs/cross-domain-index-refresh.spec.md`. No CLI flag moved, no schema or manifest
changed, and legacy stores are unaffected → **patch**.

## [0.4.25] — 2026-09-11

**Patch — the post-release audit of the Deep Field chapter, and the gate holes it found.**

Docs, this record, and the test suite only. No script behaviour changed, no CLI flag moved, and no
palette value, CSS rule or routing geometry was touched — the template's md5 is byte-identical
across the whole change. Under the versioning policy that is a patch; the release exists mainly so
the corrections have a version of their own rather than living only in a tag that is already cut.

Four adversarial review lenses ran against v0.4.24 after it was tagged. Several findings were
verified defects in **shipped text** — this chapter's own thesis is that docs drift silently, and
its own docs were carrying false claims — and the rest were holes in the gate the chapter added.
Every disputed number was settled by measuring the current tree, never by adjudicating between the
reports.

- **Four more shipped statements were false, and are now measured.** `README.md` listed Claude
  Code's native Auto-Memory as **required**; it is a supported *skip* (`preflight.py` returns
  `skip`, exit 0). `.github/dependabot.yml` claimed the four pinned actions are "the only
  third-party code this repository executes" — two unpinned `install` commands run in CI, which
  made a supply-chain claim false in the one file whose entire subject is supply chain.
  `CONTRIBUTING.md` said "CI runs all of them" of six commands; the sixth (`./cm status`) has no
  CI equivalent. And `CHANGELOG.md` claimed the pre-paint whitelist normalizes `dark` — it does
  not, and deliberately so: `read()` and `apply()` normalize, while the whitelist only filters.

- **The record corrected, three times.** The design-of-record's first draft overstated what
  was measured, and later rounds found worse. **The embedded-archive figure was wrong**
  (270,056 B / ~36 KB claimed) **and so was the unit:** the gate bounds `len(_html_p4)` — a
  CHARACTER count, against `300 * 1024` — and the shell is dense with multi-byte glyphs, so
  bytes and characters are not interchangeable here. Measured on the tree: 276,454 characters
  before, 285,411 after, leaving **21,789 (= 21.28 KiB)** of headroom, down from 30.0 KiB. A
  first re-derivation from file sizes got this wrong precisely by mixing the two units; only
  measuring the shipping tree settled it. The "after" figure itself moved twice after the
  release was cut (285,063 → 285,084 → 285,411) with no CSS change — comments count, because
  comments ship. **The dichromacy table was optimistic:** re-measured
  CIEDE2000 separations for the `ok`/`warn`/`crit` triple are, normal 27.5→24.8, deuteranopia
  2.9→6.0, protanopia 5.5→7.3 (Nocturne→Deep Field). Deep Field separates the triple better
  under both dichromacies, but 6.0 is not a large deutan separation and the spec says so under
  "Known limit, stated plainly" rather than re-paletting — which would have invalidated the
  freshly regenerated art and both gates. The design does not rest on hue: every verdict
  carries its words. The simulation's own published *collapse* constants are withdrawn: the
  sim was never committed, and an independent reimplementation could not recover them across
  28 configurations, so the spec now states the property and the direction instead of quoting
  absolutes it cannot reproduce. **And the `.dim` table was wrong on both axes** — scoped to
  `--ink`/`--ink2` while the rule dims *every* text child (the binding case is `--faint` on
  `.node-meta`), and modelled over `--paper` when `.network-surface` puts `--paper2` behind
  `<svg id="net">`. Correct inputs, wrong frame, and the number reproduced perfectly either way
  — which is precisely why it survived a first round of checking.
- **The spec's `file:line` citations were re-anchored — and the re-anchor did not hold, so they
  are gone.** The design-of-record's authority is "verified by measurement, not by reading", so
  its citations are load-bearing. Re-measuring them against the tree they actually ship in found
  that the corrected numbers were right for the tree they were *computed* in and wrong for the
  tree they were *committed to*: the same commit's `.dim` comment rewrite is five lines longer
  than the text it replaced, displacing every template citation below it by five, and the new
  smoke checks displaced every smoke citation below them by 128. Of the seven, the palette
  range was genuinely mis-ended (it stopped mid-Light and omitted `auto`) and that correction
  stands in substance. The diagnostic that guided the pass — **everything at or below
  `dashboard.template.html:211` still exact, several above it short by exactly one line** — was a
  real pattern that had already been read correctly: the released stylesheet really had gained
  exactly one line. But a +1 is only the right correction while the file stays still, and it did
  not: the toggle-cycle range was seven short rather than one, so a +1 left it wrong, and the
  citations and the edit that moved the file travelled in the same commit. Every citation in the
  spec now names its target instead — a check's name, a function, a literal — and §11 records
  why, because this is the chapter's own lesson one level down: a value kept in sync by hand
  drifts, and a stale line number fails *silently*, still resolving, just to the wrong line.
  Kept from the review: smoke pins `NocturneNetwork` by that literal only, not
  `NocturneSections`, which the §9 sentence had implied it covered.
- **Three more gate holes closed — and one was found by a mutant surviving.** The suite now
  carries five post-review RC-90 checks, all mutation-verified. The last two came from the
  browser gate's blind side: RC-90's 9×3 matrix is mostly hypothetical (only **5 of its 27
  cells** are a pair any rule actually ships, and `--paper` on `--data` / `--ink` fall outside
  it entirely), so the suite now reads the **real** `color`/`background` rule pairs out of the
  template and checks those — 7 distinct hex-on-hex pairs, worst `--data` on `--paper2` at
  Light, **5.32**. It is stated in the source that this adds no coverage *today* (all 7 are a
  matrix cell or its transpose, and contrast is symmetric); it is there for the pair that is
  not — two semantic tokens, e.g. `--warn` on `--ink`, have no cell in either direction.
  The third check exists because the pin **failed its own mutant**: it pins a *set*, the
  template's 15 pair occurrences collapse to 7 pairs, and hardcoding one of three `--ink` on
  `--card` rules left smoke at **1766/0** — a colour that has left the theme system and that
  **no other gate sees**, which is measured rather than reasoned: with the mutant applied, the
  **full browser suite was also 1213/0**, five themes and all. It is not blind because the copied
  value matches everywhere (under Light it visibly does not) — `visual_hierarchy` walks a fixed
  selector list and this rule is not on it. So the stylesheet is now pinned to naming tokens only,
  with the five deliberate theme-*independent* literals allowlisted by count **and reason**, so a
  sixth has to be a decision somebody writes down.
- **…and the check reproached itself before it ever shipped.** Its first version scanned for
  `#hex`, and this stylesheet also writes colours as `rgba()`: `.modal-bg{background:rgba(0,5,14,.82)}`
  is a colour that pattern cannot see — the same blind spot the check exists to close,
  reproduced inside the fix for it. It now scans **every notation a stylesheet can name a colour
  in** (hex, `rgb()`/`rgba()`, `hsl()`, named-as-a-whole-value), with four further mutants run to
  prove it: `rgba(12,23,39,.9)` and `color:red` were both invisible and are both caught now,
  a rule writing `background-color: var(--card)` stays green, and so does the hex case.
  `hsl()` and named colours measure 0 today and are scanned anyway — the cost is one alternation,
  and the failure mode of omitting them is a gate that reports green on a hardcoded colour.

Smoke **1767**/0 (+5 post-review checks, each one mutation-verified), mypy clean in 42 files, sim,
manifests, docs gate green, browser **1213**, CI 13/13 on the audit's merge commit.

## [0.4.24] — 2026-09-11

**Patch — the archive gets an instrument panel, the README gets a value proposition
(`docs/deep-field-theme.spec.md`).**

Presentation only: no script behaviour changed, no CLI flag moved, no cycle-record key
added or renamed, every legacy archive still renders — hence a patch. The one piece of
returning-user state that touches this release is a theme preference, and it resolves
forward rather than breaking (below).

- **Deep Field is a fifth theme and the new default.** Bare `:root` was Nocturne; it is
  now Deep Field — a near-black observatory field (`--paper:#04070e`) with hairline
  structure, a reticle brand mark, and a 19-token palette where colour is reserved for
  data, never atmosphere. Nocturne is preserved verbatim behind
  `:root[data-theme="nocturne"]` and stays selectable; Original, Light, and System are
  untouched. A saved `cm-theme="dark"` normalizes to `deepfield` in `read()` and `apply()`,
  so an existing user lands on the new default instead of a value the toggle no longer cycles
  through. The pre-paint whitelist deliberately does **not** normalize it — it omits the value
  entirely, because stamping `data-theme="dark"` would set an attribute no palette block
  matches, which is the exact one-frame flash the script exists to prevent. The star-field
  texture lives on
  the HTML wrapper, **never** inside `<svg id="net">` — `dashboard.network.js` shrinks the
  viewBox from `getBBox()`, which includes descendants, and a backdrop `<rect>` there
  would zero the margin the browser suite's `gap>=15 && gap<=40` assertion requires.
- **Two contrast gates, both green.** Deep Field had to clear smoke's RC-90 (9 foregrounds
  × 3 surfaces × 6 palette blocks) *and* the browser suite's `visual_hierarchy`, which
  composites against the real background chain including the node plate
  (`#network-blk .net-node rect{fill:var(--card)}`) — so `--card` is load-bearing for both.
  Worst Deep Field pair is **5.21** (`ghost` on `card`), more headroom than the shipped
  Original theme's 4.57.
- **The dimmed-node rule was improved, and is labelled latent — not "fixed".** The old
  `.net-node.dim{opacity:.26}` dimmed plate and label together; uniform opacity compresses
  contrast toward the backdrop, and no single value clears 4.5:1 (at `.60` it is still
  3.64) because the mechanism is the problem. The rule now splits — plate `.5`, label `.82`,
  taking the worst case from **1.44** to **3.72**. It does *not* reach 4.5. The measurement
  counts **every** text child the rule dims — `--faint` on `.node-meta` is the binding case,
  not `--ink`/`--ink2` — and composites the plate over `--paper2`, which is what
  `.network-surface` actually puts behind `<svg id="net">`. **But nothing applies `.dim`:** the
  string is in neither JS bundle, and the one path that applies `.selected` (the group view)
  marks every node it renders. So the change is real and unreachable, and the template comment
  says so rather than claiming a live improvement. The near-miss is recorded with it: the
  first attempt (group `.5` + text `.82`) measured **1.86** — *worse than the `.26` it
  replaced* (1.44) — because a group's opacity renders its subtree offscreen and fades the
  result, so the child multiplies (`.5 × .82 = .41`). Do not "simplify" it back onto the
  group, and do not read it as AA-clean if it is ever revived.
- **README restructured end to end**: a badge row, an emoji-per-section TOC carried through
  to the headings, the value proposition leading with the cost removed rather than the
  mechanism, a comparison against Claude Code's native Auto Dream, a five-row theme table,
  `[!WARNING]` callouts on legacy-data migration and lazy revocation, and every relative
  link and manual anchor resolving (the two orphaned anchors are now wired up).
  `docs/assets/network-topology.svg` is rebuilt as an honest topology — labelled zone
  bands, bridge nodes with **drawn** edges for the narrowing (`api-contract`) and
  cross-domain (`release-kit`) cases, a visibly *severed* node for the unenrolled project —
  replacing a card grid with letter badges and no edges at all. GitHub renders it as an
  `<img>`, so it is static by construction: no script, no animation, no fetched fonts.
- **The art is generated now, not hand-cropped.** Nothing in the repo produced
  `docs/assets/*`; the PNGs and the network SVG were one-off exports, which is why a theme
  change used to mean manual re-cropping. `tests/dashboard_browser.py --capture` writes
  them to `--out` for inspection and promotion (never straight into `docs/assets/` — the CI
  browser job must not rewrite tracked files), rendering in Deep Field from a live page and
  inlining each node's computed style, because the live SVG is styled by CSS classes and
  the README *links* it rather than embedding it — at the far end nothing would define
  those classes. The colours it exports are hex, and that is the correct output rather than
  a compromise: the file is consumed as an `<img>`, a document with no stylesheet context,
  so a `var(--data)` there has nothing to resolve against. What stops it going
  palette-baked *again* is that the asset is **generated** — a re-palette is a re-export,
  not a hand-edit — not that it avoids literal colours.
- **A docs gate, and a release that keeps it green.** `tests/docs_links.py` (zero-dep, same
  style as smoke) asserts badge ↔ `plugin.json`, every relative link target exists, manual
  anchors balance in both directions, the smoke-pinned workflow strings survive a
  restructure, and every theme in the toggle has a row in the README table — scoped to the
  table's first cell, so a passing mention in another row cannot satisfy the contract. It
  runs as its own CI job (the workflow is now **8** jobs, not 7) because docs drift is
  version- and OS-independent. The gate would have failed on every release as planned —
  `release.sh` bumped only `plugin.json` and never touched the README — so the bump now
  moves the badge URL *and* its alt text in the same commit, writing neither file unless
  both shapes matched (a half-applied bump is the exact drift the gate hunts).
- **Scaffolding**: `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md` (Contributor Covenant 2.1),
  `.github/PULL_REQUEST_TEMPLATE.md`, issue forms for bug/feature,
  `.github/CODEOWNERS` (the trust-boundary and secrets-firewall scripts named explicitly),
  and `.github/dependabot.yml` — `github-actions` only, because a stale action major is how
  a CI job quietly stops being a gate, and there is deliberately no pip ecosystem to watch.

Smoke **1762**/0, mypy clean in 42 files, sim, manifests, docs gate green, browser **1213**
(+105: the fifth theme × four widths).

**This entry was revised after its release.** Four adversarial review lenses ran against the
tagged v0.4.24 and found verified defects in shipped text — including figures in this entry. The
numbers here are the measured ones; what was wrong, why, and everything else the review turned up
are recorded under **[0.4.25]** below, which is also where the gate work that followed lives.

## [0.4.23] — 2026-09-07

**Patch — the defrag detector flags flow, not stock (the footnote polish).**

Two dream-session footnotes root-caused (`docs/defrag-flow-and-emoji-index.spec.md`
— advisor + adversarial review-to-zero, amend-1/2):

- **P1 — the defrag re-nag:** `defrag_candidates` flagged every fact with a body
  > 2.5× the store median — a structural property of any roadmap, so a KEEP'd doc
  re-nagged every dream. The `--justify-defrag` watermark (`defrag_justify` in the
  state file, REFRESH semantics — never the demotion skip-if-present no-op, which
  would re-anchor the very re-nag) quiets a justified stem until it genuinely
  grows (+40 tokens AND +25%, malformed entries fail open); the Phase-0 report
  shows the watermark line independent of the candidate count; `--force` is the
  post-curation re-anchor repair. The justify collectors stop at an existing
  directory — the demotion sibling's trailing-project-dir swallow, same class.
- **P2 — the emoji flag names its beat:** `⚠ emoji in beat(s): 3` (1-based, the
  archive's Passage numbering).
- **P3 — the debrief discipline:** claims about the rendered archive are verified
  against the rendered file (the log line is attempt-scoped).

Smoke 1762/0 (+13 pins — 8 discriminating vs the merge-base, 5 semantic regression guards), mypy clean, sim, manifests, browser 1108.

## [0.4.22] — 2026-09-06

**Patch — the unverifiable tally names its claims (the alert-carrier defect).**

The dream's dashboard rendered `⚠ 1 unverifiable` with no surface naming the claim
(`docs/unverifiable-carrier.spec.md` — advisor + review-to-zero, amend-1/2): the
verification tally was a count with no named carrier in the contract. Four layers:

- **The SKILL mandate (bidirectional):** every claim judged unverifiable is
  tallied AND gets one entries[] row (`skipped` when dropped, `reconciled` when
  kept with approval) whose `name` names the claim and whose `reason` begins the
  canonical `unverifiable:` token (the `extractor-skip:` precedent).
- **The validator binding:** `validate_cycle_record` warns when the tally and the
  marked rows disagree in either direction — a count with no/unequal rows, or
  marked rows without a tally — container/scalar-guarded under the never-raises
  contract (junk shapes skip the check).
- **Both dashboards name the claims at the ⚠:** the ASCII `VERIFIED` line and the
  HTML assess/KPI surfaces join the marked rows' names after the count
  (cap-with-counter); the legacy bare-count fallback stays byte-identical, and the
  KPI sub-label escapes each joined name.
- **The browser fixture's skipped row gains the token** — the validate-assert
  over all 8 history cycles stays green, and the row doubles as the name-pin
  vehicle for both renderers.

Smoke 1749/0 (+9 pins), mypy clean, sim, manifests, browser 1108.

## [0.4.21] — 2026-09-06

**Patch — the defect sweep (six measured defects from the dream session, root-caused and pinned).**

- **D1 — the marker could be stamped with a literal placeholder and silently ignored.**
  Two dreams ran `--stamp-marker HEAD` with the literal arg; the stamp wrote the string
  "HEAD" verbatim (no validation), and the next read's `_valid_sha` guard silently
  cleared it → the first-consolidation fallback mis-scoped the whole pass. The stamp
  now RESOLVES its argument (`rev-parse --verify <arg>^{commit}` — bare `rev-parse`
  echoes any 40-hex without an object-DB lookup, the dead-SHA door), stamps the honest
  `commit: ""` + timestamp on a no-git/unborn-HEAD store (a refusal would exit-5 every
  no-git dream — the persist gate is timestamp-only), and REFUSES only unresolvable
  args in commit-ful repos (the state file stays byte-identical). The read now WARNS
  when it silently clears a non-empty invalid commit.
- **D2 — the demotion verdict could contradict the scripted block.** The validator now
  flags a verdict whose probative-count phrase contradicts `windows_observed`, and the
  SKILL binds the verdict's numbers to the block's own fields.
- **D3 — the SKILL command template glued an argument into the quoted script path**
  (copying it verbatim failed). Fixed + a smoke pin that no command line glues an arg
  inside the quotes.
- **D5 — the distill scan's counts lived only in capped list lengths.** The `scanned`
  block now carries the TRUE filtered pre-cap `n_recurring`/`n_chains`; the injection
  and the report's scale line use them (the capped lengths stay the output cap), the
  validator's "impossible count" backstop is dropped (the count is script-truth), and
  the SKILL names the exact fields to read — the class where the record's numbers and
  the model's verdict contradicted each other is closed.
- **D6 — the suite's exact-count pin.** An orphaned section (the double print/exit
  class) can never print green again: the final count is pinned exactly.

D4 (beat reuse) is a documented authorship ceiling, no code. Design-of-record:
`docs/defect-sweep-v0421.spec.md` (advisor + review-to-zero, amend-1/2/3 — the final
sweep's R1–R5 closed: the doc-wide quote-close pin, the mandate-format verdict
digits, the reconcile_marker gate, the resolution cwd + 40-hex belt, the dual-count
over-cap fixture). Backward-compatible → patch. Suite **1739** · browser **1105** ·
sim / manifests / mypy green.

## [0.4.20] — 2026-09-06

**Patch — the network capture teeth (the skipped fleet capture is no longer silent).**

The first dream judged by the v0.4.19 gates exposed the capture-side gap: Phase-5
step 4's `--tokens --fleet` capture never ran in the pass, the record persisted
with no `network` block, and the archive stacked "No project nodes captured for
this view" on "Network details were not captured for this dream" — absence read
as fleet disconnection, with no teeth anywhere.

- **NET — the persist-side advisory.** A dream-bearing record whose `network`
  block has no `nodes` list (absent OR present-without-nodes — the ONE predicate
  the panel, the beta oracle, and the archive's note ladder share: the producer
  always emits nodes) gets a loud NETWORK CAPTURE MISSING panel at the terminal
  `--persist` — advisory only, no exit change (the capture is an enrichment of a
  completed dream; the exit key stays frozen). Suppressed on a maintenance/
  bootstrap pivot (its scope excludes the capture by design) with the
  string-coercion discipline, and on the dreamless legacy carve-out.
- **The `network_capture` beta-oracle family** — the fourth member of the
  skipped-by-scope set (`_maintenance_pivoted`), on the `_latest_capture_check`
  scaffold (min_version 0.4.13, the `--fleet` mandate floor); the WARN's actual
  string branches (era caveat tail for an absent block, a corruption tail for a
  present nodes-less one). The frozen A1 fixture pin re-baselined to 2 named
  expected WARNs.
- **Archive readability** — on an absent block the network panel collapses to the
  not-captured note alone (map, controls, legend, and detail all hide); a
  present-but-empty capture keeps the chrome with the honest empty-fleet text.
  Absence ≠ emptiness, and each renders alone.

Design-of-record: `docs/network-capture-teeth.spec.md` (advisor + review-to-zero,
amend-1/2). Backward-compatible → patch. Suite **1729** · browser **1105** · sim /
manifests / mypy green · beta gate 0 FAIL (2 by-design advisories).

## [0.4.19] — 2026-09-06

**Patch — the narration teeth (conversation-truth verification at the terminal `--persist`).**

The v0.4.1 persist gates are record-side: they read what the record says about
itself. A post-dream audit measured the class they cannot see — the dream block
filled at record-fill instead of narrated in the session, and Phase 2's extractor
never run with no skip note. `dream_procedure.py` adds the ground truth the terminal
render can actually read: the dream's own session transcript.

- **NAR — narration verification.** The `dream.sleep` stanza + the six `dream.beats`
  entries must each appear verbatim-normalized in an ASSISTANT TEXT BLOCK of the
  transcript window (anchored on the record's Phase-0-seeded
  `marker.before_timestamp` — never the persist-time state file). The match domain
  is text blocks only — never tool inputs or their echoed results (the record-fill
  Write/Edit carries the whole dream block), never thinking blocks. Gaps → a loud
  CONVERSATION-TRUTH GAPS panel naming each missing text + its first ~15 words,
  `narration.verdict: "failed"` on the log line, **exit 4**. A gap re-reads the
  window once (~500 ms) before firing — the flush-race guard.
- **EXT — extractor accountability.** The window must contain an executed
  `extract_signals.py` in the Phase-2 form (`--json` or the human table; `--recalls`
  does not count — the match is anchored on execution, so grep/sed targets, `$(…)`
  substitutions, and prose mentions never count) or an `entries[]` reason beginning
  with the canonical `extractor-skip:` marker + a why (the SKILL now defines that
  fixed token). Neither → **exit 3**.
- **The honest degrade.** A missing/unreadable transcript (zero kept window lines)
  degrades both arms loudly — the CONVERSATION-TRUTH UNVERIFIABLE panel,
  `narration.verdict: "degraded"`, no exit change — never a hard block. Every judged
  persist writes the additive `narration` block pre-append (verified | degraded |
  failed; absence on a log line = pre-feature), riding the full schema lockstep.
  Legacy/dreamless records stay outside both arms.
- **The beta oracle** gains the `narration_capture` family: the latest-record block
  check on the `_latest_capture_check` scaffold plus hermetic detector self-test legs
  (a fabricated-beat pair must FAIL the detector; the skip-note must pass).

Known ceilings documented in harness-map.md: the check verifies presence of
narration text and calls — conversation-truth, not performed-truth — and exact
containment assumes verbatim mirroring (a rewording model false-fires cheaply;
narrate + re-render in the same window). Design-of-record:
`docs/dream-narration-teeth.spec.md`.

Backward-compatible → patch. Suite **1712** · browser **1101** · sim / concurrency /
manifests / mypy green.

## [0.4.18] — 2026-09-05

**Patch — the Nocturne QA rework + the v0.4.17 audit residuals.**

**The Nocturne archive polish:** the report sections' narration reworked — the
`countLabel` singular/plural helper (a one-window dormant pass reads "1 window",
never "1 windows"), the honest "not captured" language replacing the fabricated
dormant fallbacks (the SKILL's verdict contract is the single source), the
captured-evidence note chain for every record class (older snapshot / not captured
/ partial — keyed on real truncation signals, never absent keys), the diff-modal's
`capturedDiff()` migration, and the browser suite grown 320 → **1101 checks** (the
narration-order pin, the hostile-string round-trips, the sparse-workflow fixture,
the header-geometry golden pins).

**The v0.4.17 shipped-state audit residuals** (two audit passes + the per-PR
review): the spec's drifted line citations refreshed, the preflight STATUS date
swept, the codeql.yml comment corrected to the live config, the roadmap's
formatting blemish fixed, and the doc counts swept to the tree truth.

Backward-compatible → patch. Suite **1688** · browser **1101** · sim / concurrency /
manifests / mypy green.

## [0.4.17] — 2026-09-05

**Patch — the captured-network truth layer + the v0.4.16 audit residuals.**

**Network identity / fact-holdings incidence:** the fleet feed now captures physical
holder identities — `NetworkNode.display_name`, `FactHolding`, and `NetworkCapture`
(emitted/held counts, unresolved identities, read-failures, conservatively measured
per-capture caps) — so the HTML network view reconstructs who actually holds each
shared fact, with the captured-evidence inspector, the explicit absence contract, and
legacy records rendering through an honest "not captured" note. The template's JS is
split into bundled modules (`dashboard.network.js` / `dashboard.sections.js`, inlined
at render with a case-insensitive `</script`-seam guard and exactly-once markers — the
single offline artifact is retained); `render_html` degrades gracefully when a bundle
is missing. New standalone suite `tests/network_identity.py` + 320 browser checks +
the header-geometry golden fixture.

**The v0.4.16 shipped-state audit residuals** (two audit passes + the per-PR review):
the mode-gate keys on the read-only flags alone (`--triage --json` no longer mints the
native plane); the no-sqlite3 beacon-silence pin and the non-list-`fails` absence pin
landed; the spec gained amend-4; AGENTS.md's plugin-table row and assertion count
swept; the capture chips use the numeric fallback for partial records; the incidence
byte-cap conservatism documented.

Backward-compatible → patch. Suite **1689 assertions** · browser **320** · sim /
concurrency / manifests / mypy green.

## [0.4.16] — 2026-09-05

**Patch — the environment pre-flight.** A new `preflight.py` answers the deployment
questions deterministically: 14 checks — Python 3.8+, POSIX/fcntl (win32/cygwin fail
closed per ADR 016), the `sqlite3` stdlib module, the SQLite ≥ 3.24 UPSERT floor, a
real-schema + flock round-trip inside the plugin-data dir, plugin self-integrity, the
native memory dir (skipped when auto-memory is disabled — native Auto-Memory is NOT a
prerequisite), git presence/repo/shallow (warn-only degradations per the shipped
policy), `python3` on PATH, TMPDIR writability with a free-space floor, transcript
inventory, and a synthetic store-resolution check for the brokenest environment. Exit
0 = clean, **2 = any FAIL**; `--json` emits the envelope.

- **Surfaces:** `cm doctor` embeds the PRE-FLIGHT table (+ rc 2 on FAIL); a resolution
  failure (EACCES config root, or a no-sqlite3 interpreter) now yields a verdict
  instead of a traceback. The SessionStart beacon prints ONE line when a fresh FAIL
  verdict is cached (warns/pass/stale → silent; never quieted by snooze;
  disabled-auto-memory stays silent). Phase 0 seeds the record's `preflight` block
  (record-producing modes only — read-only modes stay write-free) and renders a red
  line when fails were recorded.
- **Honest boundary:** a no-sqlite3 environment is itself a resolution failure — it
  reaches the sentinel verdict via doctor/Phase 0, but the beacon cannot cover it (no
  resolved ctx → no cache); stated, not solved.
- **The gated arc:** spec (`docs/env-preflight.spec.md`) → advisor (11 findings) →
  adversarial review-to-zero (11 findings, incl. the F1 reachability contradiction
  re-folded to the one-writer routing) → implementation → per-PR review (8 findings) —
  every finding fixed + pinned (the suite grew 1620 → **1660 assertions**, incl. the
  PYTHONPATH-shim sabotage runs and the cache-reachability proofs).

Backward-compatible → patch (additive script + additive record/state/dict keys; legacy
records render).

## [0.4.15] — 2026-09-05

**Patch — the version-sweep hotfix.** The 0.4.14 Nocturne release updated `plugin.json`, the CHANGELOG, and AGENTS.md's CI paragraph, but left several current-version statements behind. This release completes the sweep to the shipping version: the CLAUDE.md banner, AGENTS.md's "verified against the live tree" line, the SKILL.md banner, harness-map's lead line, the README's current-release blurb, and the 1.0-preflight STATUS line.

Doc-only. No cycle-record schema, store policy, canonical writer, command, or hook contract changes. Backward-compatible → patch.

## [0.4.14] — 2026-09-05

**Patch — Nocturne, a memory observatory.** The HTML summary now leads with the
project's context outlook, evidence, and shared-memory network on a midnight-blue
canvas. The theme control also offers **Original**, preserving the previous dark
espresso palette, plus Light and System modes. Preferences persist locally; print
stays legible and reduced-motion settings are respected.

- **A network you can read:** domain lanes show trust boundaries, selected group
  routes show permission, and shared-fact edges show captured holdings. Project
  inspection and complete captured-data tables preserve details beyond the bounded
  16-node diagram. Missing measurements are explicit, and legacy records still render.
- **Evidence stays accessible:** all existing observation panes remain, with a full
  embedded-record inspector. Workflow lists reset between cycles, partial records
  retain recorded problems, mobile archives retain every column, and diff dialogs
  support keyboard focus and return.
- **A clearer entry point:** the README explains practical value before mechanics;
  a complete multi-domain network guide covers enrollment, group grants, sharing,
  inspection, revocation, and migration. Synthetic HTML, screenshots, and SVGs make
  the design reviewable without exposing personal memory.
- **Browser regression coverage:** Chromium exercises themes, data completeness,
  archive navigation, sparse and legacy records, network bounds, accessibility,
  and narrow screens in a separate development-only CI job. The runtime and core
  test matrix remain Python stdlib-only.

No cycle-record schema, store policy, canonical writer, or command contract changes.
Backward-compatible → patch.

## [0.4.13] — 2026-09-04

**Patch** — two arcs, one release cycle.

**The round-2 dogfood's hermeticity fix:** the v0.4.0 registry-index smoke
section ran against the REAL plugin-data registry (HOME was not redirected),
so every suite run minted a `regproj` enrollment row into the operator's
fleet registry — the measured origin of the 315-row residue — and the
section's "fresh DB" pins were vacuous (they asserted indexes the real
registry already had). The section now runs under the hermetic HOME+GLOBAL
swap, and a pin asserts the real registry gains ZERO rows from a suite run
(the fleet registry verified at 11 enrolled / 0 residue across repeated
runs). The round-2 dogfood also re-verified the full 0.4.12 surface live.

**The fleet-topology UI** (design-of-record
`docs/fleet-topology-ui.spec.md`, amend-3 — deep-dive → advisor → adversarial
review-to-zero → per-PR review, finder re-verified; 1619 assertions): the
HTML archive's Shared-Consciousness view draws ALL topology layers on one
diagram, key-gated on `basis_scope: "fleet"` — tinted domain arcs (the
VLAN/trust-boundary layer), dashed group hulls (the routed links), a
universal-baseline chip strip with honest partial-holder counts, fleet-wide
differential chords naming their binding facts, and a 16-node ring bound.
The feed: `--tokens --fleet` emits the whole-installation node set
(disk-first, registry-overlaid for domain/group attribution), per-node
`domain`/`groups`/`sid`, label disambiguation (the sid is the collision-proof
join key), `domains`/`universal_facts`/`group_links`/`stack_edge_facts` —
with `--fleet` scoping group links to the trigger's own groups (the
share-safe archive basis) and `--fleet=full` for the operator's complete
view. Bare `--tokens` stays byte-shaped; legacy records render
pixel-identically; the demo, ASCII line, SKILL schema, and validator updated
in lockstep. Plus the repeated-window hotfix: `render_html`'s auto-open is
now globally bounded per archive (a changing-anchor re-render loop can no
longer spawn a window per iteration), `CM_NO_OPEN=1` is the kill-switch,
and no TEST may open a browser (the suite's own render probe had been
spawning a window every run). Backward-compatible → patch.

## [0.4.12] — 2026-09-04

**Patch** — the 0.4.11 fleet dogfood's five live findings, all fixed + pinned
(1603 assertions):

- **The cross-domain holder fid** — `_holder_labels` resolved registry holders
  under the CONTEXT's domain, so a group-bridged fact reported 1 holder where
  10 existed, and `--network --all-domains` passed no ctx at all (0 minds
  holding 4 live canonicals). Holders now resolve under the FACT's domain, and
  the all-domains lens resolves a ctx for the registry (Markdown `projects:`
  stays the migration-only fallback). Measured live: `python-ruff-mypy-gate`
  now reports its true 10 holders.
- **The registry-only de-registration surface** — 315 enrolled rows left by a
  registration test had NO local store and were unreachable through any CLI
  (`unenroll` resolves from a path). `cm project unenroll --project-id PID…`
  (one flag, many ids, plan-first, `--confirm unenroll-registry`, one journaled
  transact with a holder sweep — `holder_delete` gains the symmetric
  project-wide wildcard). The fleet's 315 residue rows were de-registered
  through it; the census now reads the real 11.
- **The move/unenroll clean-vs-edited** — a move quarantined EVERY mirror
  whose canonical the destination domain lacks (verbatim replicas, measured
  live), and a namespaced mirror missed its canonical through the bare
  file-name lookup. The revoke now compares against the mirror's OWN canonical
  (fact `name` + `canonical_domain`, the group-revoke precedent).
- **`move-domain`'s documented form** — the flag-first help form failed
  argparse; the `cm` help is now positional-first with the true confirm phrase
  (`move-<from>-to-<name>`).

Design note: the dogfood also verified the full 0.4.11 lifecycle end-to-end on
the live fleet (scratch group create → add → narrowed delivery → populated
refusal → plan-first citation → delete → recreate → stale refusal → `--repoint`
→ teardown; a repo moved personal↔tools with clean mirror revoke/re-pull; the
leftover `admins` group deleted). Backward-compatible → patch.

## [0.4.11] — 2026-09-04

**Patch** — group-lifecycle completion: the three gaps the 0.4.10 fleet
dogfood named. `cm group delete` exists (refuses a populated group — naming
the member project ids — and prints the citation count across every enrolled
domain before deleting; the delete is journaled). The recreation guard gains
its re-confirm affordance: `--repoint` on `cm canonical upsert` and
`sync_global.py --promote` explicitly authorizes `recipients:` that predate
the current group identity and force-restamps `content_modified` to now (the
durable re-confirmation; the error names the flag). The pull side of the
guard ships: delivery withholds **per-recipient** (a member of a FRESH cited
group still receives the fact), a stamp-less edit re-delivers without the
flag, and gc is **re-sourced** — a withheld fact's stranded mirror renders
FROZEN with a reason token (dropped-stack / guard-stale / not-entitled),
`gc --apply` deletes it clean or quarantines a locally-edited copy, and the
orphan branch's blind-delete is replaced by the mirror's own lineage-stamp
clean-vs-edited test. Design-of-record:
`docs/group-lifecycle-completion.spec.md` (advisor + adversarial
review-to-zero + a per-PR review round; 1573 smoke assertions, the pull-guard
pins verified to fail on pre-fix code). Backward-compatible → patch.

## [0.4.10] — 2026-09-04

**Patch** — the group-scopes layer: the routed-link tier above the domain. An
operator-granted **group** is a recipient set that a canonical's optional
`recipients:` targets to **narrow** delivery — to two repos, or across domains
(the governed successor to the v0.2.1 A→B sharing). Cross-domain mirrors get
namespaced `{domain}--{stem}` keys with record-derived provenance; the pull
path, beacon, GC, and revoke are membership-aware (a removed member's clean
mirrors are deleted, edited ones quarantined); a recreated group name is a
fresh identity — facts predating it refuse to re-point. Commands: `cm group
create/add/remove/list/show` + `/cm-group`, and `/cm-share` asks whether to
deliver to a group or the whole domain (the narrowing is printed verbatim).
The fleet's two measured cases resolve: one cross-domain group for the
universal plan-mode preference, one retired duplicate ruff/mypy gate.
Design-of-record: `docs/group-scopes.spec.md` (advisor + adversarial
review-to-zero + a per-PR review round; 1549 smoke assertions). Backward-
compatible → patch.

## [0.4.9] — 2026-09-04

**Patch** — the fleet-dogfood hotfix: `/cm-connect`'s absorb step now harvests
usage windows from BOTH repos (the shipped wizard pulled the other repo but
harvested only the invoking one — harvest is idempotent and its purpose is
fleet-wide evidence before transcript rotation, so the omission was a real
evidence gap). The full 0.4.8 fleet dogfood connected 11 nodes with 0
out-of-sync holders. Backward-compatible → patch.

## [0.4.8] — 2026-09-04

**Patch** — the onboarding command surface: a fresh-user dogfood measured the
cross-project setup friction (five CLI incantations for what should be three
words), so the marketplace gains four commands — `/cm-connect` (the two-repo
wizard: surveyed, operator-confirmed grants, an optional first shared fact,
absorption both ways, the network payoff), `/cm-share` (one verified fact from
one sentence, report-then-apply, no-verify-no-write), `/cm-sync` (absorb now),
`/cm-network` (read-only fleet views) — and the SessionStart beacon gains an
unenrolled advisory (participating stores only; the count is registry truth,
excluding purge-window domains; a statement, never a directive). The README's
cross-project section consolidates to the single workflow, and the shipped
`cm-domain.md` examples are fixed (the flags-first forms failed argparse —
`/cm-domain` now works verbatim). Design-of-record:
`docs/cm-commands-onboarding.spec.md` (advisor + adversarial review-to-zero).
Backward-compatible → patch.

## [0.4.7] — 2026-09-03

**Patch** — the cross-project audit release: a four-agent audit of the
cross-project layer plus an adversarial PR review, every finding fixed and
smoke-pinned. The inactive-mirror ack never clobbers a project-authored file
at a replacement stem; a canonical upsert without `--origin` keeps the
holder's three-way base through the journal replay (the holder's own untouched
mirror is no longer misclassified as a local edit on the next pull); edits to
unknown metadata keys enter the conflict classifier's semantic payload; GC
re-verifies frozen mirrors under the mutation lock and reports what it
actually deleted; the harvest ledger dedups concurrent window rows; resolved
conflicts and the quarantine pen age out on the recovery TTL (quarantine had
no GC at all); a demotion stamp near a saturated log tail fails open instead
of suppressing forever; `compact_jsonl` preserves the fleet ledger's 0o600;
the SessionStart beacon reads the facts manifest without writing; a
prefix-less dream Bash call still opens the dream-arc span. The README is
restructured for the approaching 1.0 — onboarding-first with a cross-project
quick-start, version archaeology moved here. 1518 smoke assertions. No
memory-plane behavior changes.

## [0.4.6] — 2026-09-03

**Patch** — the archive display pass: the HTML archive now exposes its own
contract data — the distill block renders the top chains and the skill-usage
tally beside the top commands, the registrar board renders the unjudged
evidence cards, a split-naming counts-only note, and the decline lineage, and
the This Pass header carries the outcome + decision count like the other five
section headers. No memory-plane behavior changes.

## [0.4.5] — 2026-09-03

**Patch** — the issue-closeout release: of the 25-issue board, 22 were verified
fixed by shipped commits; **#151 closes here**, and the remaining code/doc legs
of **#152** (SHA256SUMS + the required-checks doc bullet) and **#153** (the
POSIX-only declaration) land here — their operator legs (ruleset settings,
1.0 qualification evidence) are what actually close those two. Changes: the
HTML archive's distill top-commands move from the header into a proper body
list (the L2 renderer hotfix), CI gains the capacity bench corner (measured,
not gated) and the missing 15th concurrency scenario (compaction under a high
baseline never drops a racing writer's row), the release pipeline gains
SHA256SUMS beside the SBOM (self-verified via `sha256sum -c`), and the 1.0
preflight declares POSIX-only (ADR 016). No memory-plane behavior changes.

## [0.4.4] — 2026-09-03

**Patch** — docs sync: the current-engineering-release statements (CLAUDE.md/AGENTS.md
headers, the SKILL banner, harness-map, README's release blurbs + known-limitations
header, the 1.0-preflight STATUS line) are swept to 0.4.4 — fixing the one-behind
state 0.4.3 shipped (its sweep landed pre-bump at 0.4.2). Also: the preflight ops-HOLD
residual list is de-staled (signed tags · SBOM/provenance publisher · the PR-only main
ruleset — three of the five named blockers, shipped), and AGENTS.md's smoke-assertion
count is corrected to the live gate (≈1505). No behavior changes.

## [0.4.3] — 2026-09-03

**Patch** — post-0.4.2 documentation sync: the current-engineering-release
statements (CLAUDE.md/AGENTS.md headers, the SKILL banner, harness-map, README's
release blurbs + known-limitations header, and the 1.0-preflight STATUS line) are
swept to 0.4.2. No behavior changes.

## [0.4.2] — 2026-09-03

**Patch** — the production-readiness + polish + performance pass: the stacks cache moves
onto every sync path, the journal scale stack collapses to single passes, the warm-pull
margin widens at 10k canonicals, and the archive embed gets a budget — plus two store-honesty
fixes (stranded globals, fixture stores), the QA oracle's persist-gate teeth, the release
workflow's provenance/validate/signed-tag coverage, and a help/docs/renderer coherence sweep.

### Performance —

- **Stacks cache on the pull path.** `run`/`--gc`/`--promote` consult the beacon's
  state-file stacks cache before re-running `detect_stacks` — the full-project walk re-paid
  on every sync path measured 337ms here (2003ms documented worst). The `--staleness`
  non-trigger rows already read the state-file cache directly (v0.1.81); the trigger row's
  `detect_stacks` stays live. A `(mtime_ns, size)` stamp over the marker files
  `detect_stacks` actually reads invalidates on change; a 7-day TTL bounds the stamp's blind
  spot (`.py`-content changes are not statted) and an expired cache re-arms on the next pull;
  `CM_RESCAN_STACKS=1` forces a rescan. A fresh no-change pull skips the cache write entirely.
- **Journal scale.** `redact_journal_payloads` dirty-flags each row (one dump per changed
  row, not two per row — the sort_keys equality check was ~14s of pure waste at 1M);
  `compact_journal` runs one merged pass (age hoisted, one UPDATE per changed row, VACUUM
  only when anything was rewritten); `journal_cleanup` reuses the under-lock orphan scan.
  `cm data export` prints a progress line and reports the redacted row count.
- **Warm-pull margin.** Run-local relevance/admit memoization, one read-only connection for
  holder-base lookups per pull, and an in-sync fast path that skips rebuilding the mirror
  text when the stamps and semantic hash already match (the same conditions the
  facts-manifest fast path trusts). C=10k no-change pull 523-673ms → ~350ms measured.
- **Archive embed budget.** `render_html` assembles the cycle series once per render,
  embeds only the newest 20 dreams' diff sidecars, and trims embedded records to the keys
  the dashboard reads — the worst-case archive at the 120-cycle cap drops ~12MB → <4MB.

### Fixed —

- **Stranded-global advisory:** an authored (non-mirror) `user-global`/`stack-general` fact
  with no canonical counterpart now surfaces as a schema-drift advisory with the remediation
  wording ("re-scope / demote, or promote to a canonical") — advisory, never counted as drift.
- **Fixture-store exclusion:** known beta-fixture stores (marker-file `.cm-fixture` or a
  pinned stale-slug match) are excluded from the native-store enumeration with a visible
  "skipped N fixture store(s)" line — fleet analytics no longer count synthetic stores as
  live nodes.
- **Oracle persist-gate family (`CHK-PERSIST-GATE`):** the QA oracle now DRIVES the v0.4.1
  terminal gates — a short-arc seed + `--persist` must exit 4 with exactly one log line,
  the re-render must re-fire exit 4 without a second line, and an unstamped seed must exit 5.
- **Journal cap wired:** `compact_journal` now enforces `JOURNAL_MAX_ROWS` (it previously
  passed `max_rows=0` — the advertised cap was dormant on the compact path).
- **Release teeth:** the tag-triggered workflow verifies the tag signature (committed public
  key), re-runs the strict plugin/marketplace validates, and publishes build provenance +
  an SPDX SBOM to the GitHub Release; `release.sh --finalize` signs tags and refuses without
  `user.signingkey`.
- **Help/docs sweep:** `cm` help gained the missing subcommands and the required
  `--confirm` phrases (following the documented enroll/migrate/purge/import commands
  verbatim previously only dry-ran); the SKILL/harness-map/warning texts carry the confirm
  phrases; version headers swept to 0.4.1+; the SKILL banner names the exit-3/4/5 terminal
  contract.
- **`--diffs` mandatory before WAKE:** the archive now surfaces an honest "no diffs
  captured" row for a dream whose `--diffs` step was missed; the unenrolled warning prints
  once per store (first-seen flag) instead of on every dream/archive/pull — `cm doctor`
  stays loud.
- **Top-commands render:** the persisted `distill.top` evidence rows render in BOTH
  dashboards (top-3 `template ×N Nd`) — the capture has existed since v0.1.82 but no
  renderer consumed it.
- **Outcome vocabulary:** one shared `outcome_of` across the ASCII dashboard, the HTML
  archive (injected at embed time), and a new OUTCOME column in `cm log` — the three views
  no longer drift on maintenance/light wording.

## [0.4.1] — 2026-09-02

**Patch** — the dream-arc and marker contracts gained teeth at the terminal boundary
(the 2026-09-02 dogfood self-healed a 4/6-beat arc that persisted with exit 0 and an
unstamped cycle that silently skipped its persist); the schema-drift detector stops
counting managed mirrors as drift.

### Fixed —

- **Dream-arc completeness gate.** `render_dashboard --persist` now exits **4** after
  persisting on a PRESENT-but-incomplete arc (sleep/wake empty or ≠ 6 beats) with a
  loud ⚠ DREAM ARC INCOMPLETE panel — the single `memory_status.arc_completeness`
  predicate also drives the dashboard's ✓/✗ presence line, the validator warning, and
  the render_html WAKE-cue gate ("backfill before waking"). A record with no `dream`
  block keeps exit 0 (legacy/preview). The beta oracle's CHK-DREAM-ARC tightens to
  `== 6` (stays ADVISORY; the 0.4.1 boundary is named). Reverses the spec's
  "style never fails a dream" choice — recorded in dream-arc-contract.spec.md.
- **Unstamped-cycle teeth.** `--persist`/`--diffs`/`--audit` auto-mirror an empty
  `marker.commit`/`timestamp` from the stamped state file (`reconcile_marker` —
  a non-empty value stands, junk never raises); the reconciled payload lands in the
  log AND the cycle file (the split-brain heal — the archive no longer embeds the
  dream twice). A still-unstamped terminal persist exits **5** with a loud panel;
  "persist clean" now fires only on a real append, and the render prints the exact
  `persist → <path>` line.
- **Drift mirror exclusion.** `schema_drift` skips managed mirrors (their stamp
  block replaces `node_type`), keeping mirror stems in the index-symmetric diff —
  the first pulled mirror in the dogfood store no longer reads as drift.

## [0.4.0] — 2026-09-01

**Minor** — the sole-authority release (ADR 023): SQLite is the single authority for
holders/topology, grants, and migration state; the frontmatter/link/catalog pipeline is
consolidated; dormant infrastructure is removed. Behavioral contracts change —
Markdown `projects:` is migration input / frozen display, never an operational authority.

- **SQLite-only holder/topology (#142).** `_holder_labels` is tri-state: registry
  unavailable → Markdown fallback (migration input); authoritative zero never
  resurrects Markdown provenance; `--gc --edges --apply` prunes the `holders` table
  only — canonical bodies stay byte-verbatim.
- **Grants in SQLite (#145).** `native_store_grants` (one owner per normalized path,
  `--adopt` for a nonempty destination, mutations under `locks/global.lock`, 0700);
  `cm project grants|grant-native|revoke-native|transfer-native`; `store-grants.json`
  is dual-read migration inventory with a one-shot ingest.
- **Migration state consolidation (#146).** Every active kept-existing disposition
  enters the catalog overlay — a stale/missing pointer is repaired on apply.
- **Parser/catalog/link consolidation (#149).** Canonical dependency targets must be
  `CLASS_ACTIVE`; every pointer/catalog line is generated through a typed renderer;
  duplicate reserved frontmatter keys are refused; `replacement_id` is validated
  (self and cycles refused).
- **Capabilities:** marker-file signature caching (`capability-cache.json`, 0600) +
  monorepo workspace detection (pnpm-workspace/go.work/lerna/nx).
- **Databases:** `holders(project_id)`, `facts(domain_id, stem)`,
  `tombstones(domain_id)`, `journal(status, created_at)` indexes; `cm doctor` surfaces
  `PRAGMA integrity_check`.
- **Performance (Phase 5):** a derived facts-manifest cache takes canonical
  reads off the beacon/pull hot paths (per-domain JSON rows; invalidation at the
  transact choke point; `CM_FACTS_MANIFEST=0` kill-switch) — SessionStart beacon
  4,989→1,024 ms and no-change pull 5,828→531 ms at C=10k. Journal inventory is
  keyset-paginated (`--limit`/`--after`, bounded default 200) — a 1M-row journal
  renders one page, never a 1M-line dump.
- **Testing gaps:** a dedicated `tests/concurrency.py` suite (fork + barrier
  harness) and crash-injection pins close the 15-scenario concurrency/crash
  audit (editor races, grant races, rollback faults, reactivation propagation,
  compaction-proof justification clock).
- **Removed dead compatibility:** `fact_id_for`, `_prune_holders`/`drop_holders_text`,
  and the dormant hook-sketch infrastructure (`hook_sketches.py` deleted; the extractor
  no longer sketches; the dormant `usage_events`/`workflow_sketches` registry tables are
  dropped by a user_version 3→4 migration — see ADR 024).
- **`cm data import`** (tar.gz restore from `cm data export`, path-escape refused) with
  a round-trip pin.
- **CLI errors** under `--json` emit a machine-readable envelope
  `{"ok": false, "error": … , "code": 2}` with exit 2.

## [0.3.7] — 2026-09-01

Patch on 0.3.6. First dogfood of v0.3.6: counter-justify never quieted the
cadence fact (model stamped the displayed `Nw`, not store `windows_full`),
and `cm local` reused the global 88-char `[]()` sanitizer as the always-loaded
hook. Public **1.0 stays HOLD**.

### Fixed — domain and canonical lifecycle (Phase 3 / P0-1, P1-1, P1-2, P1-8)

- **Domain purge unenrolls in the same transact** that marks `deleted`. Former
  members are local-only and can enroll elsewhere. `StoreContext.domain_lifecycle`
  gates `cross_project_allowed`. `cm data purge-status|purge-resume|purge-cancel`.
- **`reconcile_inactive_mirrors`.** Tombstoned, superseded, expired, and
  missing-inactive canonicals leave receiving indexes on the next pull.
  Supersession installs the replacement first.
- **Tombstone stubs cannot be reactivated.** `cm canonical resurrect STEM --file`
  runs the full upsert pipeline. Reactivate is expired/superseded with a real body.
- **All-plugin-data purge** uses an external fence under
  `consolidate-memory-purge/` and resumes until every intended path is absent.

### Fixed — journal terminal cleanup (Phase 2 / P0-2, P0-3, P1-4, P1-5, P1-9)

- **`committed-cleanup-pending`.** After registry COMMIT the journal is not
  `complete` until trash, recovery blobs, and temps are deleted and verified
  gone. Cleanup returns `{deleted, missing, errors}` and never swallows
  `OSError`. `cm journal cleanup` retries leftovers and scavenges only
  orphan/terminal artifacts — never pending/failed/conflicted trash.
- **`journal.sqlite` is journal-only.** `connect_base` / `connect_registry` /
  `connect_journal`; `locks/schema.lock` + `PRAGMA user_version`. Temps are
  `{name}.tmp-{op_id}`, never PID.
- **Abandon/rollback.** Abandon refuses while trash/recovery remains unless
  `--accept-fs`. Rollback of a post-commit op is refused. Compact collapses
  90-day-old complete/abandoned rows to receipts.
- **Snapshot-then-transform** for canonical status (no bless-new-hash).

### Fixed — demotion counter-justify (O1, R128-1, R128-2)

- **`--justify-demotion STEM` script-writes the stamp** under the project
  lock (`update_project_state` CAS). Phase 5 no longer hand-merges JSON.
  The writer records the monotonic SQLite `sequence` (not rolling
  `windows_full`). Re-justifying a still-suppressed stem is a no-op so a
  daily re-stamp cannot reset the clock. Default: only current demotion
  candidates (`--force` is repair).
- **JSONL compaction cannot prolong a stamp.** `project_usage_windows` is
  the clock; refire after five later *probative* sequences. Legacy
  `{windows, at}` still counts window_starts after `at`.
- **All marker writers share the CAS API:** `cm marker stamp|standing-justify|snooze`,
  stacks-cache, demotion justify. Concurrent writers preserve both changes.
- **Phase 0 `justified: stem (re-fires at Nw · K to go)`.** Eligible stems
  and veto tallies are separate lines, so a justified fact is not readable
  as "this eligible row is already justified."

### Fixed — LocalFactV1 and local writer invariants (R128-3–R128-8)

- **LocalFactV1:** `cm local upsert` injects `local_schema_version`,
  `scope: project-local`, status, sensitivity, timestamps; refuses any other
  scope and duplicate reserved keys. `cm local migrate-schema` normalizes
  legacy files.
- **Plan-time snapshots:** missing dest/index is `ABSENT`; a file created
  during the operation is refused, not overwritten.
- **`SHIPPED.md` uses `archive_index`** (10k lines / 1 MiB), not the
  always-loaded 200-line/25KB cliff.
- **`rebuild-index` is plan-first and fail-closed.** Invalid/unreadable
  facts leave MEMORY.md unchanged unless `--skip-invalid` enumerates them.
- **Dotted stems are link targets** (periods kept; 96-char / 180-byte cap).
  Code-span stripping remains the TOML defense.
- **Local fat-hook diagnostics** name the native fact path, not
  `~/.claude/memory/`.

### Fixed — local pointer is a recall key (I1, I2)

- **`cm local` no longer aliases `_pointer_line`.** Globals keep the
  injection sanitizer (strip `[]()`, 88-char). Local pointers keep `()`,
  strip `[]`, word-boundary truncate so the **whole line** is ≤
  `HOOK_TOKEN_WARN`, and pass frontmatter `scope` so `[project-local]`
  appears. Rebuild uses `_pointer_line` for mirrors and `_pointer` for
  locals. The fact body's `description:` stays the full recall key.

### Fixed — KEEP vs justify (I3)

- Standing ops policy without KEEP tokens is the counter-justify path.
  `_KEEP_RE` is unchanged (sufficient-not-necessary; widening it over-vetoes).

### Fixed — UX noise

- **GC copy:** empty canonicals and no leftover mirrors → "nothing to
  reclaim", not Probe G's mass-wipe wording. Leftover mirrors with no live
  canonicals still refuse.
- **Stale-all:** when every fact is stale and the last dream is <24h, Phase 0
  prints count + age instead of dumping every stem. `_stale_since` is
  unchanged (Phase 3 still gets the list).
- **Bare `[[link]]`:** placeholder targets (`link`/`name`/`wikilink`/…) hint
  that format examples belong in backticks.

## [0.3.6] — 2026-09-01

Patch on 0.3.5. First dogfood of `cm local upsert` on the v0.3.5 dream: hook-lint
parity and inline-code link-strip parity with the health helper. Public **1.0 stays HOLD**.

### Fixed — local writer dogfood (D1, D2)

- **`cm local` index pointers use `_pointer_line`.** A long `description:` is no
  longer copied verbatim into `MEMORY.md` (the first v0.3.5 dogfood upsert wrote a
  ~190-tok fat hook into the always-loaded index). Same 88-char sanitizing truncate
  + `_fat_hook_warning` as `--pull` and canonical origin mirrors. The fact body
  keeps the full recall key.
- **`link_targets` uses `extract_wikilinks`.** Backticked / fenced `[[…]]`
  (format-example placeholders, TOML `[[tool.mypy.overrides]]`) are not dangling
  links. The writer's validator matches `dangling_links` (D10). A real
  `[[missing]]` still refuses.

## [0.3.5] — 2026-09-01

Patch on 0.3.4. Remaining P0 authorization, journal-retention, and fleet-purge
gaps. Public **1.0 stays HOLD**.

### Fixed — StoreContext authorization (P0-1, P0-2)

- Project/local `autoMemoryDirectory` may be the exact current-project native
  store, a directory inside the current project tree that is not a protected
  config-root path, or a dedicated namespace recorded by
  `cm project grant-native --path PATH`. Another project's
  `projects/<slot>/memory`, domain canonicals, plugin-data, and any other
  config-root path are refused without that operator grant.
- `$HOME` as a git root no longer treats `~/.claude/settings.json` as
  repository-controlled project settings.
- Linked-worktree and submodule Git dirs require a relationship, not a path
  shape: no `.git` symlink, worktree `gitdir` backlink, commondir containment,
  and submodule modules-relative path match. Attacker/victim fixtures cover
  worktree admin dirs, `.git` symlinks, and nested `modules/` pointers.

### Fixed — journal bodies and complete-old (P0-3–P0-7)

- New journal rows never store fact text. `cm journal compact` redacts
  historical `text` / `bytes_b64` from completed rows and expires recovery
  blobs (`0600`, TTL, overwrite-then-unlink). `cm data export` archives a
  redacted journal copy. CLI: `cm journal inventory|show|retry|rollback|abandon|compact`.
- Destination snapshots record original mode; restore verifies hash, mode,
  containment, and existence/absence. Registry postconditions are proven
  before file publication; a failure is `conflicted`, not a mixed FS+DB state.

### Fixed — P1 correctness and architectural drift

- **`--resurrect` includes `tombstone_delete` + `fact_status_change`** in the
  same migrate-apply transaction (only when the stem is actually tombstoned).
- **Migration finalize** verifies every disposition (`migrated` /
  `kept-existing` / `excluded` / `replaced`) from an immutable
  `migrate-manifest.json` (frozen `migration_id`): path, hash, v3 class,
  domain, registry row, and catalog pointer for active facts. `keep-existing`
  validates a real v3 canonical. Revisions use `semantic_hash`.
- **Read-time v3 classification:** valid-active-v3 | valid-inactive-v3 |
  legacy-migration | invalid. Ordinary pull replicates only valid active v3
  (`fact_id` must match the stable id; timestamps must be real calendar
  datetimes; applies tokens are grammar-limited). Unversioned fixture GLOBAL
  facts remain test-only.
- **Catalog and link lookup** use the opening-frontmatter codec. Links to
  invalid/inactive v3 targets are refused.
- **Canonical upsert** accepts only `scope: stack-general|user-global` and
  `status: active`, with detectable applies/stacks for stack-general.
  Lifecycle: `cm canonical forget|supersede|expire|reactivate`.
- **SQLite holders** are the topology/fleet-tax source. `apply_provenance`
  strips Markdown `projects:` instead of appending display names.
- **Conflict rows** upsert inside the pull transact; unique open
  `(fact_stem, project_id, domain_id)`.
- **`resolve_store` is read-only.** Remote URL is not part of `project_id`.
  Alias writes happen only via `cm project rebind`.
- **Applicability is three-state** (match / no-match / unknown). Detector
  failure holds gated facts.
- **`cm local upsert|update|archive|forget|rebuild-index`** journals
  fact+pointer writes with the same secret, admission, and codec checks.
- **Hook sketches** are documented as experimental / out of contract.
- **Ops logs key off project_id** when known; export uses the SQLite backup
  API (WAL-safe) and streams members under an ops lock; `cm data compact`
  holds that lock around relocate + JSONL compact + journal compact. Export
  restoration (open restored SQLite) is smoke-tested.

### Fixed — forget ack and fleet purge (P0-8, P0-9)

- Domain purge marks `deleting` under every enrolled project's lock, builds
  StoreContexts from registry rows (recorded `project_id` + native store, never
  native-as-root), revokes or quarantines every mirror, verifies pointers are
  gone, then deletes canonicals and marks `deleted` in the same coordinator
  transact. `all-plugin-data` does the same revoke pass before `rmtree`.
  Pull/upsert/forget already refuse a deleting domain; `transact` now does too.

Existing 0.3.4 installs keep working. Backward-compatible ⇒ **patch**.

## [0.3.4] — 2026-09-01

Patch on 0.3.3. One enumerator for ordinary fleet ops, journal complete-old,
StoreContext identity, fleet forget-ack, and domain purge maintenance.
Public **1.0 stays HOLD**.

### Fixed — one enumerator

- **Ordinary ops use `_admissible_records` / `iter_canonicals` only.**
  `global_facts` / `_canonical_dirs` are gone. `--all-domains` walks named domain
  dirs, never leftover `~/.claude/memory`. Unenrolled `facts_for_context` is empty.
  `beacon_line` does not default to leftover GLOBAL. `_orphans` does not scan
  GLOBAL when `canon` is omitted.
- **Dead writers removed.** `_ensure_index_pointer`, `_remove_index_pointer`, and
  `_record_provenance` are gone. Pull/promote already journal through `transact`.
- **`preserve_canonical` reads only the domain dest.** Missing dest is refused;
  leftover GLOBAL is not a stand-in. Enroll lookup does not fall through unknown-pool
  or leftover memory.
- **Harvest ledger is plugin-data only.** Leftover `~/.claude/memory/.fleet-usage.jsonl`
  is not a standing dual-read.
- **New journal payloads carry `registry_ops` only** (empty holders/facts/tombstones
  tuples). Recover still applies an old pending payload that has tuples.

### Fixed — journal complete-old (ADR 017)

- **Deletes rename to same-dir trash**, then dests publish, then registry
  COMMIT, then trash is unlinked. A later delete failure restores earlier
  trash. `EXDEV` fails closed.
- **Dest snapshots are recovery files**, not `bytes_b64` in new journal
  rows. Restore only when the dest still has the published hash; a
  concurrent edit is quarantined. If quarantine cannot move the occupant,
  restore refuses rather than `os.replace` over user bytes.
- **Create-mode uses `os.link`** (no empty visible inode). No-hardlink FS
  falls back to in-process `O_EXCL`+write without the empty-unlink recover
  heuristic.
- **`recover_pending` applies registry ops before file publication** and
  COMMITs after. Source drift becomes `conflicted`. A matching trash file
  for a journaled delete is not treated as source drift. Historical
  `bytes_b64` rows still restore.

### Fixed — StoreContext identity (ADR 018)

- Worktree/submodule Git dirs require a **gitdir backlink** and commondir
  containment. A `.git` symlink is not Git.
- Project/local `autoMemoryDirectory` may be inside the project tree or
  exactly this project's default native store — not another
  `projects/<slot>/memory`.

### Fixed — forget ack, resurrect, purge (ADR 019)

- Forget is **lazy tombstone-acknowledgment**: the next `--pull` or
  `--gc --apply` in another project deletes a clean mirror or quarantines
  an edited one. GC no longer treats tombstone Markdown as a live stem.
- `--resurrect` issues `tombstone_delete` in the same apply transaction.
- Domain purge sets `deleting` first; pull/upsert/forget refuse. Revoke
  keeps the recorded `project_id` when `resolve_store` would disagree.
- Catalog generation reads **opening frontmatter only**. Capability
  detection failure holds gated facts.

`cm migrate --inventory` remains the only reader of leftover `~/.claude/memory`
(ADR 013). Existing 0.3.3 installs keep working. Old `journal.sqlite` rows may
still contain forgotten bodies until a later compact. Backward-compatible ⇒
**patch**.

## [0.3.3] — 2026-09-01

Patch on the 0.3.0 secure-default (plus 0.3.1 recover/UI and 0.3.2 health-row).
Adversarial review of v0.1.91→v0.3.2 found remaining P0–P2 holes in dual-read
pull, enroll keep-path, journal crash windows, the migrate stage machine,
StoreContext git identity, and dashboard honesty. Public **1.0 stays HOLD**.

### Fixed — dual-read pull, enroll keep-path, dry-run sqlite

- **Ordinary `--pull` / `--list` / beacon never live-read `~/.claude/memory`.**
  `_admissible_records` walks that tree only when tests patched `GLOBAL` to a
  fixture dir. Tagged leftovers (`domain: personal`) are migrate-inventory, not
  fleet share. `_canonical_dirs` comment matches `--finalize` (not `--apply`).
- **Enroll/move-domain keep-path does not trust mirror `domain:`.** Keep only
  when a dest-domain canonical exists on disk and three-way says in-sync.
  Spoofed `domain:` is revoked/quarantined.
- **Dry-run enroll does not mint `control.sqlite`.** Plan/show uses
  `connect_if_exists`; `connect()` runs only after `--apply --confirm`.

### Fixed — journal crash windows + temps

- **Dest publish then delete mismatch is complete-old.** `transact` snapshots
  dest preimages, restores them on delete mismatch, and marks the journal
  `failed` (not `pending`). Recover of `failed` is a no-op. Crash step
  `after_dests` covers the window Probe AE hid.
- **`recover_pending` never uses the journal DB as the registry.** Missing
  `ctx` / `registry_conn` with `registry_ops` leaves the op pending.
- **Pull recover failures are rc≠0.** Empty v3 source hashes are illegal.
- **Create-mode `after_create` empty dest retries.** Size-0 dest + live tmp
  unlinks and re-`O_EXCL`s; foreign bytes stay `bad`.
- **Temps are 0600 + fsync** at `prepare_temps` (`O_EXCL`, fail-closed fsync).

### Fixed — migrate stage machine

- **Finalize is terminal.** Apply after `enforced` / `finalized` is rc=2 and
  does not reset `finalized`. Rollback after finalize is refused and needs
  `--confirm migrate-rollback`. `--apply` and `--rollback` together refuse.
- **`--keep unknown-pool` survives inventory refresh.** Resolved collisions
  keep the chosen origin; apply copies that body. Reviewed sha256 is not
  clobbered by a later live hash.
- **Finalize requires dest existence + digest.** Missing dest is rc=2, mode
  stays dual-read. Rollback file is deleted inside the finalize transact.
- **Migrate apply refuses a tombstoned dest stem** unless `--resurrect`.

### Fixed — StoreContext, schema, GC, STALE, harvest, export, HTML

- **`gitdir:` / `commondir` are contained.** A nested `.git` file pointing at
  another project's `.git` does not steal its native store. Submodule gitfiles
  (`super/.git/modules/<name>`) use the working tree, not `super`. Worktrees
  still share the main-repo store.
- **Empty `autoMemoryDirectory` vs a live default slug store is disagreement**
  (`write_allowed` false). Candidates always include `slug_for(git_root)/memory`.
- **Project/local `autoMemoryDirectory` must stay under `config_root` or the
  project tree.** An escaped path is not native (`write_allowed` false). User
  and managed settings may still name an explicit absolute dir.
- **Pull / GC / holder lookups never fall back to leftover `~/.claude/memory`.**
  Same-stem leftovers are migrate-inventory, not canonical truth. `--gc --edges`
  liveness is `(domain, stem)`.
- **`git remote add origin` keeps enrollment.** Lookup by
  `(profile_id, git_common_dir)` + `project_aliases`; hash formula unchanged.
- **Nested YAML `applies:` is refused** (column-0 `applies` and `applies.any`).
- **Invalid v3 canonicals are not GC-orphaned.** Pull still skips them.
- **STALE does not clobber a non-mirror.** Harvest/`--utility` join by
  `fact_id` or `(domain_id, stem)`, never bare stem across domains. Export
  archives the same bytes it hashed (`TarInfo` + `BytesIO`).
- **HTML honesty:** rigor derives `suggested_tier` when `applied` is empty;
  unverifiable/eligible (not dropped/unused); `prettyNode` has no `home-drei`;
  git_range `-N` → `recent N (no marker)`; meters use the cycle's
  `budget_tokens`; dream view does not invent identity from live; over-budget
  unindexed is not ⚠ schema drift; caption gates on tally>0.
- **SKILL Phase 5 dangling** uses `canonical_domain_dir`, not
  `sync_global.global_store()`.

Existing 0.3.2 installs keep working. Backward-compatible ⇒ **patch**.

## [0.3.2] — 2026-09-01

### Fixed — HTML Verification & health row

Dogfood of the 0.3.1 archive: a pass with 8 dangling wikilinks rendered as two
rows (`dangling` / `wikilinks`) with only three names listed.

- Health-row labels are `max-content` + nowrap so a long name list cannot
  squeeze `dangling wikilinks` onto a second line. Names wrap in the result
  column.
- `clipNames` lists up to 8 stems and always emits `+N more` when truncated
  (the silent `slice(0,3)` is gone).
- Usage reads **organic** and names dream-procedure exclusions, so `0 reads`
  next to `8 confirmed` is not a contradiction (verification is grep/git;
  usage is transcript body-reads).
- Index mismatch with pointers-ok reads **not in the index** (not
  `index↔file`, which looked like broken pointers).

Existing 0.3.1 installs keep working. Backward-compatible ⇒ **patch**.

## [0.3.1] — 2026-09-01

Patch on the 0.3.0 secure-default. The trust boundary does not change
(unenrolled is still local-only). Recover and the secondary mutation paths
fail closed, and the HTML/ASCII dashboards finally show domain, enrollment,
registry health, and open conflicts.

### Fixed — journal recover, delete fail-closed, migrate/repair isolation

- **Recover re-verifies sources.** `recover_pending` re-checks journaled
  source hashes before publishing a replace-mode dest. A dest that changed
  after `prepare_temps` (a concurrent local edit) is refused; the journal is
  not marked `complete`. Destinations that already match the recorded sha256
  are treated as published (crash-idempotent).
- **Deletes fail closed.** `_apply_deletes` errors (does not unlink) when the
  preimage is empty or the live file is unreadable. A mismatch still does not
  delete.
- **Registry ops before dest publish.** `prevalidate_registry_ops` refuses
  unknown or malformed typed ops before any file change. `transact` applies
  registry ops, then verifies sources, then publishes, then deletes, then
  COMMITs. `tombstone_delete` is a first-class journal op. Conflict rows
  carry `domain_id` / `fact_id`.
- **Repair-mirror stays in the current domain.** No fallback to
  `<config>/memory`. Schema-v3 canonicals are validated; a work-tagged
  legacy file cannot restamp a personal project's native store.
- **Migrate apply is contained and one-shot.** Sources must sit under the
  approved roots (`<config>/memory` and `domains/unknown/facts`); a second
  `--apply` refuses until rollback or finalize. Rollback is all-or-nothing
  (no partial restore of an edited dest). Plan and rollback files are
  journal destinations. Finalize checks dest hashes against the rollback
  record.
- **Purge uses the saved native path** (`store_override=native`) instead of
  guessing `native.parent.parent`. All-plugin-data `rmtree` no longer uses
  `ignore_errors=True`.
- **Catalogs list only `status: active`.** Tombstoned, superseded, and
  expired facts are omitted. Schema-v3 files are validated on pull.
  `applies_*` must be flow-lists (`[...]`), not scalars. Tombstone markdown
  emits the ADR 011 key set.

### Added — cycle-record identity, HTML/ASCII enrollment observability

- **`identity` on the cycle record** (additive TypedDict). Phase-0 seed
  snapshots `domain_id`, `enrolled`, `registry_state`,
  `cross_project_allowed`, and the open-conflict count. No filesystem
  paths — the HTML archive is often shared. Pre-0.3 records omit the key;
  HTML falls back to live identity at render. SKILL schema block is pinned.
- **ASCII dashboard** prints an `IDENTITY` line (domain · enrolled, or
  `LOCAL-ONLY`; registry health and open conflicts when they fire).
- **HTML archive** masthead shows the same identity. Unenrolled / registry /
  conflict banners sit at the top. Cross-project movement (pulled /
  promoted / refreshed / held / gc) is a chip strip in the Shared
  Consciousness section — enrolled silence stays collapsed; unenrolled
  with no movement is one quiet line.

### Docs

README: upgrading from v0.1.x → v0.3.0 (trust-boundary table +
migrate-then-enroll order) and the v0.3.1 install / dashboard identity
line. Public 1.0 stays HOLD.

Existing 0.3.0 installs keep working (additive cycle-record key,
fail-closed fixes). Backward-compatible ⇒ **patch**.

## [0.3.0] — 2026-09-01

### Breaking — unenrolled is local-only (ADR 008)

- **`unknown` is a local-only sentinel.** Unenrolled projects cannot create or
  pull cross-project canonicals. Enroll into a named domain (`personal`
  recommended). `domains/unknown/facts` and legacy `~/.claude/memory` are
  migration inputs. v0.2.1 unenrolled A→B sharing is gone.
- **`enroll` refuses a silent domain switch.** Use `cm project move-domain --to`.
  Enroll / move / unenroll revoke managed mirrors not admitted in the destination.
- **Cross-domain `authorized_pairs` is unsupported** (ignored).
- **Public 1.0 remains HOLD.**

### Added — ADRs 008–016, identity types, admin commands

- ADRs 008–016 freeze the 0.3.0 contract (local-only unknown, registry health,
  journal v3 dest-verify-before-delete, schema v3 codec, domain transition,
  staged migration, Phase-1 sync exception, current-domain reports, POSIX mutation).
- `identity.CanonicalRef` + `StoreContext.registry_state` /
  `cross_project_allowed`.
- Packaged `/cm-doctor`, `/cm-domain`, `/cm-data`.
- `fact_schema.py` restricted codec (name==stem, domain match, enums).
- Staged migrate (ADR 013): inventory → assign/exclude → apply (named domains only;
  refuses unresolved facts; no `legacy-unassigned` stamp) → rollback (hash-aware) →
  finalize (sets `enforced`). Dual-read remains until finalize.
- `cm data export` writes a tar.gz + sha256 manifest. `cm data purge --scope`
  (`managed-mirrors` | `project-ops` | `domain-canonicals` | `all-plugin-data`)
  never deletes Claude's native Auto Memory.

### Added — unenrolled-share warning, registry classification

- Loud `UNENROLLED LOCAL-ONLY` warning on `cm doctor`, `--list` /
  `--pull` / `--promote`, `canonical upsert` / `forget`, and dashboard persist/HTML
  renders when the project is not enrolled.
- `classify_registry()` / `assert_mutation_allowed()`: a present but
  locked / corrupt / unreadable / incompatible `control.sqlite` refuses enroll,
  unenroll, migrate apply/rollback, forget, upsert, resolve, repair-mirror, GC
  `--apply`, and purge. An *absent* registry still allows first write (it will be
  created). `cm doctor` prints `registry_state`.

### Fixed — read-only SQLite, unknown tombstones, catalog-on-forget

- **`connect_if_exists` is actually read-only.** It no longer calls `connect()`
  (which mkdir'd, ran `SCHEMA_SQL`, and enabled WAL). URI `mode=ro`; schema
  upgrades stay on the writable `connect()` path. `--list`, `cm conflicts`,
  migrate `--plan`, and doctor cannot mint or migrate the DB.
- **Unknown-domain tombstone lookup uses `domain_id="unknown"`.** A forget in
  `work` no longer blocks an unenrolled upsert of the same stem (and an unenrolled
  forget now actually prevents resurrection).
- **`forget` regenerates the domain catalog in the same `transact`**, so a
  tombstoned fact's pointer does not linger in `MEMORY.md`.
- **Journal dest-verify-before-delete (ADR 010).** `_publish_temps` no longer
  unlinks origins when a dest hash mismatches. `expected_revisions` may not be
  `None` for a file that influenced the plan (pull records plan-time hashes).
  Recovery COMMITs the registry before marking the journal complete, and
  refuses to complete a replay whose `upsert` returned `ok: false`.
- **Hook-sketch persistence is off by default** (`CM_HOOK_SKETCHES=1` to enable).
- **`upsert_project` no longer clobbers stored capabilities with `[]`.**
- **`--gc --apply` journals through v3** (dest-verify-before-delete) and requires
  enrollment. `forget` deletes holder rows in the same transact.
- **Canonical upsert injects `name:`/`domain:`** from the stem and StoreContext
  before schema validation (promote rename no longer hard-refuses).

- **Domain transitions are one journal v3 transact** (enroll / move-domain /
  unenroll): registry change + revoke of unadmitted mirrors. Locally edited
  mirrors are quarantined under `native/quarantine/`, never deleted. CLI is
  dry-run unless `--apply` (TTY also requires `--confirm enroll-<domain>` /
  `move-<from>-to-<to>` / `unenroll-<domain>`). `rebind` aliases a moved
  git-common-dir onto the enrolled `project_id`.
- **Ordinary fleet reports are current-domain only** (`--list`/`--tokens`/
  `--network`/`--utility`/`--staleness`/`--workflows`/`--harvest`/`--gc`).
  `--network --all-domains` is the admin view.
- **Holder-table `base_revision` is the three-way base** (mirror frontmatter is
  not trusted). Pull re-classifies under lock. Mirrors stamp `canonical_fact_id`
  + `canonical_domain`. Nested `applies.any` is refused.
- **Forget revokes this project's managed mirror** in the same transact.
  Migrate `--validate` / `--resolve-collision` exist; rollback journals through
  v3. Retention no longer advertises an unimplemented 12-month aggregate window.
- Unenrolled `--pull` is a no-op before `connect()`; unenrolled `--promote`
  refuses before `domains/unknown/facts` is created. `iter_canonicals` is the
  typed enumerator. Harvest rows carry `domain_id` + `fact_id`. Journal recovery
  applies `registry_ops` even when there are no dest temps. Capability user
  overrides (`capability-overrides.json`) are honored on pull. `cm project show`
  is read-only (does not mint sqlite). `cm data purge` is plan-first (`--apply`
  + confirmation phrase). Export tar members match the sha256 manifest. SKILL /
  harness-map no longer instruct writing live `~/.claude/memory/` as the canonical
  plane.
- Pull `MISSING` will not overwrite a local file that appeared after classify.
  Domain-transition recovery matches this project plus origin/dest domain (not a
  later enrollment). Forget/GC journal `holder_delete`. `resolve` / `repair-mirror`
  / migrate `--apply` require enrollment. `--workflows` / `--staleness` / `--network`
  without `--all-domains` stay current-domain.
- macOS smoke slug pins no longer assume `/home/...` survives `Path.resolve()`
  (symlink/autofs on GH `macos-latest`).
- **Journal v3 typed ops fail closed** (unknown `op` is `WriteRefused`;
  `project_upsert` / `project_rebind` are first-class). Delete preimage mismatch
  aborts the journal (not `complete`). `mode=create` uses exclusive create.
  First-enroll crash recovery recreates the project row.
- **Domain-transition classify is under the lock** (ADR 012). Dry-run is
  advisory; `--apply` rereads + three-way classifies with the holder table.
  Collision-safe quarantine names: `native/quarantine/<stem>.<utc>.md`.
- **Migrate dest collision / rollback bytes.** Existing dest refuses unless
  `--on-existing keep-existing|replace-with-migrated|exclude`. `--keep legacy`
  clears collisions when the primary origin is kept. Rollback restores prior
  dest bytes, catalogs, and fact rows. Apply uses the same schema codec as
  upsert (ADR 011 required fields). Catalog `generate_catalog(..., overlay=)`
  sees staged temps.
- **Untagged legacy is not ordinarily pullable** into a named domain. Pull
  uses `applies_from_fm` (`applies_any` / `applies_all` / `applies_exclude`);
  nested `applies.*` refuses that fact. Schema-v3 mirrors with a missing
  holder row quarantine (no frontmatter fallback).
- **Forget** three-way classifies this project's mirror (quarantine a local
  edit; no `holder_delete *` while other stores still have files). Domain /
  all-plugin-data purge revokes managed mirrors first. `--apply` always
  requires `--confirm PHRASE` (TTY or not), including `cm data compact`.
- **Recovery is per-op atomic.** A failing registry op rolls back earlier
  ops in that pending entry. `mode=create` treats a dest that already has the
  expected hash as published (crash-idempotent). MISSING pull uses `ABSENT` +
  `create`. Migrate apply pins reviewed source hashes; rollback restores
  catalogs and fact rows under lock. Domain purge aborts if any revoke fails
  and journals canonical deletion. Resolve/repair emit `holder_upsert` +
  `conflict_resolve`. Schema v3 writer requires the ADR 011 key set.

Docs (README, SECURITY, SKILL, harness-map, CLAUDE, AGENTS, preflight, `cm` help)
describe **0.3.0 behavior**: unenrolled is local-only, Phase-1 `--pull` is the
documented enrolled-domain exception to "Phases 0–3 are read-only", `/cm-*` for
marketplace users, `./cm` maintainer-only. POSIX mutation is fail-closed (no
unlocked Windows fallback). Behavior break vs v0.2.1 unenrolled sharing is a
**minor** bump under the pre-1.0 policy (`0.2.1 → 0.3.0`). Public 1.0 HOLD.
`plugin.json` is **0.3.0**. Installed plugins auto-update at next Claude Code
startup once this version is on `main`.

**Residual HOLD (not this release):** signed SBOM/provenance publisher
(committed `release.yml` is the verify-on-tag gate); native-Windows mutation
(POSIX fail-closed is the contract); soak of a **copy** of a real 0.2.1
unknown-sharing fleet.

## [0.2.1] — 2026-08-31

### Fixed — unenrolled sharing, tombstone domain keys, enroll-only grant

- **Unenrolled A→B sharing.** `iter_admissible_facts` always scans
  `ctx.canonical_domain_dir` (including `domains/unknown/facts`). Upsert/promote of
  an unenrolled project now pull into other unenrolled projects; tests drive
  upsert-then-pull, not a planted `~/.claude/memory` file.
- **Tombstones are `(domain_id, stem)`.** Forgetting `deploy` in `work` no longer
  makes `personal` `deploy` irrelevant on pull.
- **Admission domain is enroll-only.** `CM_DOMAIN`, managed-settings, user
  `settings.json`, and `domain.json` request a domain; they do not grant one.
  `domain_id` comes only from registry `status=enrolled`.

Docs name **v0.2.0** (SKILL / CLAUDE / README / harness-map). Public 1.0 stays HOLD.
Backward-compatible with v0.2.0 installs ⇒ **patch**.

## [0.2.0] — 2026-08-31

Cross-project hardening: StoreContext, domain isolation, a SQLite control plane,
and a sole canonical writer. This is the first **minor** bump since v0.1.1 —
install-breaking on purpose (pre-1.0). Public 1.0 stays HOLD.

### Added — StoreContext, domains, control plane, canonical writer (PR #116)

- **`StoreContext` is the only native/canonical path constructor** (ADR 002).
  Profiles, worktrees, nested git dirs, `CLAUDE_CONFIG_DIR`,
  `CLAUDE_CODE_PROJECT_DIR_NAME`, `autoMemoryDirectory`, and disabled auto-memory
  resolve in one place. `cm doctor` prints the resolved native, canonical,
  control-plane, profile, domain, and project identities (twice-run equal).
- **Trust domains.** Canonical facts live under
  `<config>/consolidate-memory/domains/<domain>/facts`. `user-global` is
  domain-global, not installation-global. ADRs 001–007 freeze the contract.
- **Operator enrollment is the grant.** `cm project enroll --domain NAME` /
  `show` / `unenroll` maps a stable project id to a validated domain. Repository
  `.claude/settings.json` may *request* a domain; it never grants one. Unknown /
  unenrolled projects receive zero domain-tagged facts (untagged legacy still
  dual-reads).
- **SQLite control plane** under plugin-data: project registry, holders,
  tombstones, conflicts, and a durable **journal** (`journal.sqlite` separate from
  `control.sqlite`). Cross-store writes take domain then project locks, prepare
  temps, verify, publish, then COMMIT the registry.
- **Three-way mirrors** classify refresh / stop-local / restamp / conflict /
  quarantine and never silently overwrite a local edit.
- **`cm canonical upsert` is the sole canonical writer** (schema, domain policy,
  links, generated catalog, tombstones). `--promote` delegates to it.
- **Exact native 200-line / 25KB admission** on a project's `MEMORY.md` (not the
  generated global catalog).
- **Maintainer CLI:** `cm doctor` / `conflicts` / `resolve` / `repair-mirror` /
  `canonical` / `migrate` / `data` / `forget` / `project`. Operational logs live
  in plugin-data; the native plane stays facts-only.
- **Empty-set judgment** (ADR 001): an empty scripted set emits the one-liner
  verdict and does not open a content walk; scans still run.

### Changed — identity, admission, legacy store

- **Project id omits domain** so enroll does not mint a new id. Domain is a
  registry attribute.
- **Facts are `(domain_id, stem)`**, not a global bare stem. Same-name facts in
  two domains stay distinct and pull only into the matching domain.
- **Legacy `~/.claude/memory` is a read-only migration source**, not a second live
  canonical namespace. Upsert / promote write the domain dir only.
- **`--pull` enumerates `iter_admissible_facts(ctx)`** and rescans the canonical
  body for policy (including nested `domain` / `sensitivity`).
- **`confidential` never replicates except same-domain.** No dual-read exception.
  Untagged confidential is denied.

### Fixed — PR #116 review + remaining P0 blockers

- **Managed settings win.** StoreContext merges user → project → local →
  `--settings`, then `managed-settings.json` last. A policy `autoMemoryDirectory`
  or `autoMemoryEnabled: false` is no longer overwritten by a lower file.
- **`--list` is actually read-only.** It does not mint `control.sqlite`.
- **Migrate `--apply` stamps `domain: legacy-unassigned`**, journals the copy, and
  lets domain dirs win on stem. `--plan` does not mint the DB.
- **Phase 0 / beacon / compact follow StoreContext.** Compact/purge key
  `ops/<slot>/`, not SHA `project_id`.
- **Identifiers cannot escape managed roots.** `validate_domain_id` /
  `validate_fact_stem` / `validate_project_id` / `safe_child` on enroll, resolve,
  repair-mirror, forget, and purge. `../` and absolute ids are refused.
- **Journal is crash-consistent.** Locks then recover; origin profile/domain/project
  stored on every op; dest **sha256** is the success predicate (existence is not);
  registry COMMIT only after dest hashes publish; source-verify failure rolls back
  the registry. Recover of a domain-A op from a domain-B command does not complete
  against B and does not abandon A's pending row. Missing POSIX flock refuses
  mutation instead of locking as a no-op.
- **Promote / evict do not delete origin unless the exact future native index
  (line AND byte) is admitted.** Admission-refused upsert/evict leaves the origin
  file.
- **Forget tombstones omit the previous body** (`deleted_revision_hash` only).
  Generated catalogs skip `status: tombstoned`.
- **Locks unwind on acquire failure.** `repair-mirror` `assert_writable`s.

Public 1.0 stays HOLD. Cycle-record TypedDicts and the SKILL schema JSON block are
unchanged. Schema-v2 codec, nested `applies`, migrate review/assign, capability
registry, workflow-sketch consumption, real export, and a Windows flock backend
remain deferred (fail-closed flock is enough).

Existing 0.1.x cycle records still render. Domain isolation, enrollment, and the
legacy store becoming read-only are the install break ⇒ **minor**.

## [0.1.91] — 2026-08-30

### Improved — Shared Consciousness draws the sharing topology

The archive graph used to be a cost star: a spoke if a project held *any* shared
mirror, a number equal to *every* fact in that store. That read as a complete
fleet of equals. Shared consciousness has three layers, and the graph now says so.

- **Everyone-holds vs this-stack.** `--tokens` splits mixed `shared` into
  `universal` (user-global, the baseline every project is meant to absorb) and
  `stack` (stack-general, facts only some repos share), plus compact
  `stack_edges` (pairwise this-stack intersections). `shared` is unchanged for
  older records.
- **The HTML graph is dream-centric and differential.** Rust center is this
  project. Lines are this-stack overlap — the baseline is named, never drawn as
  an all-to-all star. Peer chords appear only when two others share *more with
  each other than with you*, bowed around the rim so they never cut the hub.
  Same-stack minds sit in a contiguous arc. A baseline-only satellite is dim,
  not a blank circle. Hover splits the count
  (`9 this-stack · 21 baseline · 125 in this store`). Caption: *Numbers are
  this-stack facts; lines are what some share.*
- **Older cycles stay honest.** Pre-split records keep the old star and say so
  — renderers do not invent live topology at paint time.

`--network` (logical provenance minds) was already this split; the archive now
matches it on the physical `--tokens` node set. Schema trio moved together
(TypedDicts + SKILL block + C5 pin).

### Improved — registrar decline-anchors stay fleet-scoped

A fleet proposal is a distinctive command that actually recurs on ≥2 nodes with
min-d ≥ 2. The blocked sample (generic CLI, single-node distinctive, day-spread)
is evidence, not a docket.

- Decline-anchors attach only from declined **fleet-candidate** rows (plus
  distill `proposed … declined`). A declined `mypy` or `python3 tests/smoke.py`
  on one node does not poison the next consult.
- `--into` persists fleet-candidates and a capped distinctive day-spread
  sample; generic-cli / single-node stay as `n_*` counts. Re-consult strips
  awaiting/declined from a non-fleet row; out-of-window declined fleet-candidates
  are kept.
- The model writes `awaiting-confirmation | confirmed | declined` only on
  fleet-candidate rows. `validate_cycle_record` warns otherwise. Spec D-7 /
  SKILL Phase-5 consult match.

1025/1025 smoke, mypy clean. Additive throughout (`universal` / `stack` /
`stack_edges` on `network`; `_is_fleet_proposal_row`). Legacy cycle records
render. Existing installs keep working ⇒ patch.

## [0.1.90] — 2026-08-30

### Improved — the registrar recognizes real fleet workflows

W-C shipped a working join. This release teaches it the difference between *command-class
co-occurrence* and a *workflow worth packaging* — so a fleet-wide proposal is something a
future session would actually want as a command or skill.

- **Distinctive gate.** Ordinary `git`/`gh` never clear fleet placement. Interpreters
  (`python3`, `bash`, …) only count with a script path (`python3 tests/smoke.py` yes;
  `python3 --json` no). A chain is distinctive if any side is. Live fleet (8 of 12 nodes
  reporting): **0 fleet-candidates** — the honest cold-distinctive state, not a miss.
  `blocked: generic-cli` is the frequent, correct disposition.
- **Shared over days, not the loudest node.** Fleet `d` is the **min** of per-node
  day-spreads. A 3-day node can no longer carry a one-day partner (`min(3,1)=1` →
  `blocked: day-spread`). Both sides must themselves have `d ≥ 2`.
- **Decline lineage closes.** Anchors attach from
  `workflow_proposals.candidates[].disposition == declined` (the channel the dream
  actually writes) as well as distill `proposed … declined`. Generic CLI declines do
  not pollute the set, so the next dream will not re-ask about `git add`.
- **Script-truth counts.** `--into` records `n_generic` / `n_day_spread` beside the
  existing n_*; blocked persist prefers the interesting near-join. Mechanical
  `distinctive` is additive on every row. Missing model disposition stays
  `fleet-candidate` / `blocked:*` — never inferred as `awaiting-confirmation`.

The HTML archive matches that honesty: the section is **across projects**, cards are
**named proposals only** (`awaiting` / `confirmed` / declined-with-a-name), evidence
shows `on A and B · 3d · ×44`, day-spread is its own line, and “nothing is created
until you confirm” appears only when the dream actually left something awaiting.
Mechanical co-occurrence of `git add` is not a docket.

`docs/wc-registrar.spec.md` v0.4. SKILL Phase-5 consult + schema block moved with the
TypedDicts (C5 pin). `cm workflows --registrar --into` documents the injection.

### Improved — the archive’s two-rung budget, end to end

The always-loaded index has two rungs (1500 target · 3840 ceiling). The archive now
says so: lead and KPI print exact tokens, the axis labels `target` / `ceiling`,
standing-justified over-target is not an “over budget” alarm, and trajectory projects
to the right rung. Genuine `after_tokens=0` is data (an emptied index is not a missing
key). Escape closes the diff modal. In-page hash changes re-route without reload.

1004/1004 smoke, mypy clean. Additive throughout (`mechanical.distinctive`,
`n_generic`, `n_day_spread`; `d=min` is a gate tightening, not a schema break; legacy
records render). Existing installs keep working ⇒ patch.

## [0.1.89] — 2026-08-30

### Fixed — two 0.1.88 render-chain regressions (user-reported, root-caused, pinned)

- **Registrar overflow.** The new registrar panel had reused the LEDGER's `.row` grid
  (96px 1fr auto) inside the narrow verdict container — the grid can't shrink, so long
  chain-candidate lines pushed every row right off the page. The panel now uses its OWN
  `.reg-row` layout (flex + wrap + `overflow-wrap:anywhere`) and caps the blocked rows at
  8 with a "+N more — see the consult" tail (fleet-candidates always render first). The
  ASCII renderer caps identically (parity).
- **Repeated browser pop.** `render_html` opened a new tab on EVERY invocation — the
  dream's re-render flow (patches, re-renders, `cm report`) popped the dashboard
  repeatedly mid-pass. A per-store open marker now allows ONE open per (archive, anchor)
  per 3 minutes; back-to-back re-renders write the file silently, and a deliberate later
  re-open still opens. (`_should_open` is a pure, smoke-pinned function.)

Backward-compatible throughout (presentation-only; 973/973 smoke, mypy clean, sim holds).

## [0.1.88] — 2026-08-30

### Fixed — the render chain, end to end (a 4-reviewer presentation-layer audit)

The dream's final step (ASCII dashboard · HTML archive · diff sidecars · `cm log`) was
audited against a real corpus-repo dream; every confirmed finding below was measured
first, then fixed + smoke-pinned (959 → 967 checks).

- **Blockers.** `render_dashboard` crashed on a non-dict `entries[]` item (the validator
  checked the container, never its items — both fixed); `render_log` crashed on a
  well-formed non-dict log line / non-list entries.
- **The embedded-JSON seam.** The python-side `_safe_embed` escape was already correct —
  but the template's own comment mis-credited `esc()` as the load-bearing guard, and a
  parse failure degraded to `DATA={}` with raw JSON leaking onto the page. The comment
  now names the real guard, and a parse failure surfaces a visible "archive data
  corrupted" error instead of silent degradation.
- **The registrar finally renders.** `workflow_proposals` (v0.1.87/W-C) was schema'd,
  validated, and injected — but had NO render surface in any view. Both renderers now
  show the Tier-2 consult: candidates + dispositions + decline-anchors, and a
  distill-era record without the key renders "registrar not consulted" (the SKILL's
  "absent = a visible decision" contract, actually visible).
- **HTML parity with the ASCII dashboard.** The archive gained the usage-telemetry row
  (reads/transcripts/mentions), the remediation-gate row (a standing-justified record no
  longer reads "gate active" — the meter honors `standing_justified` as an amber status
  line), fleet totals in the network panel, and the browser tab now titles itself after
  the dreamed repo, not the plugin.
- **Honest empty states.** The network panel no longer asserts "no shared-memory network
  yet" when the record carries fleet totals but no node rows; the ASCII "(no nodes…)"
  line keys off all-zero totals, not list emptiness.
- **Model-slip coercion.** JSON-string `"false"` flags no longer flip warnings on
  (`_flag` at every flag boundary); stored `null`s never print as `None`;
  `carryFwd` distinguishes a genuine 0 from a missing key (a zero-index line was being
  silently replaced with the previous cycle's value).
- **Placeholder-token cleanup.** Scope tags render as `proj`/`global`/`stack`, never
  `<proj>`/`<->` (the angle brackets read as unrendered template holes); the
  markerless first-dream `-20` lookback sentinel renders "recent 20 (no marker)";
  `⚠ 0 unverifiable` and `~ 0 corrected` lose their glyphs on zeros; `1 chains` and the
  unlabeled recall-facts delta are fixed; long entry reasons now wrap instead of
  overflowing the grid; the outcome banner wraps when a derived outcome can't fit the
  line.
- **Wide-glyph width.** Padding and wrapping measure DISPLAY columns (emoji/CJK = 2),
  so a 🍀-labelled node can't misalign the network table, the log table, or wrapped
  prose.
- **Dream-arc honesty.** The DREAM ARC ✓ now gates on arc completeness (6 = 5 phase
  beats + the surfacing line; a 4-beat arc shows `✗ 4/6`) and flags emoji inside
  non-bookend beats — the contract's bans, rendered.
- **Sidecar integrity.** `--diffs` with no before snapshot skips with a visible note
  instead of fabricating every change as a whole-file "created"; content lines starting
  `-- `/`++ ` are no longer dropped as file headers; the sidecar key gains a session
  suffix (same-HEAD same-second dreams can't clobber each other — legacy sidecars keep
  resolving via an alias); the mutation log rows carry their dream's identity and a
  re-run of `--audit` doesn't double-append; the observation glob is recursive (a nested
  fact dir is no longer invisible to snapshot/audit/diffs).
- **Template hygiene.** The rigor filter `<option>`s now escape like everything else;
  arrow keys can't reload a dream while the diff modal is open; the node graph caps at
  12 with an honest "of N" count; the >100% meter labels its overshoot.

Backward-compatible throughout (additive render paths, presentation-only; legacy
records render unchanged or better — the diff-sidecar key change is alias-compatible).

## [0.1.87] — 2026-08-29

### Added — W-C: the distill registrar's Tier-2 fleet-placement gates (W-C1 + W-C2)

The distill vertical's final stage ships its first two build stages
(docs/wc-registrar.spec.md v0.2 — 3-lens adversarially reviewed; the corrected evidence
census: 2/8 fleet nodes reporting W-A rows, 0 exact cross-node recurrences — the live input
exists, the join threshold is what's cold). The registrar proposes FLEET-WIDE workflow
artifacts from the W-A/W-B evidence, with the shipped Tier-1 local proposal path untouched:

- **`sync_global.py --workflows --registrar [--json] [--into SEED]`** — the Tier-2 MECHANICAL
  gate cascade over the W-B join: per candidate (templates AND chains) `fleet_recurrence`
  (≥2 real nodes) + `day_spread` (fleet d ≥ 2) → `fleet-candidate | blocked:*`. The
  model-judged legs (stable inputs · coverage · decline lineage) are LISTED, never
  engine-evaluated; READ-ONLY (exit 0/2); registered in the dispatch, usage string, and
  `cm` help.
- **`fleet_workflows` node_states** — `legacy` (no `top` key) / `instrumented_empty`
  (`top: []` counts as reporting) / `reporting`, distinct — the D-8 three-case honesty.
- **`distill_history` decline-anchor** — a DECLINED verdict now carries its own record's row
  snapshot, making the materially-new-evidence rule computable fleet-wide (D-2.5).
- **The SKILL Phase-5 registrar consult** (two-tier model): Tier-1 LOCAL proposals unchanged
  (a 5-episode single-node workflow stays legitimately proposable locally); Tier-2 fleet
  placement consults the mechanical gates first — a `fleet-candidate` is necessary, never
  sufficient; dispositions + genericized names are model writes only; the honest cold-join
  state renders `0 fleet-candidate(s)` (the engine's own wording), never invented breadth.
- **The `workflow_proposals` cycle-record block** (WorkflowProposal/WorkflowProposals
  TypedDicts, total=False) — evidence SCRIPT-INJECTED via `--registrar --into` (counts never
  hand-mirrored); the SKILL schema block moved together (the C5 smoke pin held); the runtime
  validator warns on wrong-container sub-keys.
- **Fixture + pins**: a hermetic 4-node fixture (shared / single-node / chain /
  day-spread-blocked / legacy / instrumented-empty / declined-anchor) + 8 pins — 950/950
  smoke, sim/manifests/mypy green, the 3-leg QA gate clean, the beta engine 0 FAIL on the tree.

Additive: a new read-only flag, an additive total=False record block, and SKILL wording that
regresses no shipped path — every existing install keeps working ⇒ patch. The live proposal
path stays inert until ≥1 exact cross-node recurrence (the evidence-pending clause).

## [0.1.86] — 2026-08-28

### Added — budget-trajectory early-warning: the index slope, projected honestly, with staleness attached

The ninth enhancement increment (docs/budget-trajectory-early-warning.spec.md). MEASURED
premise (read-only, 3-node live fleet probe): one node is 47% over its index target and climbing
+130.5 tok/cycle toward the hard ceiling with nothing surfacing it, while a flat-but-stale node
reads as healthy on slope alone. The Phase-0 report (memory_status.py) now attaches to the
existing STORES index gauge:

- A ported OLS slope (_ls_slope, degenerate-case-identical to the dashboard's lsSlope) fit over
  the last ≤4 logged budget.index.after_tokens cycles (the shared iter_cycle_log reader,
  carry-forwarded so a legacy/zero record can't fake a dip).
- Two-regime projection (budget_trajectory_advisory): a rising fit projects the cycle count to
  the next UNCROSSED threshold — the 1500 soft target when under, the 3840 hard ceiling when
  over (the dashboard only projects to the soft target, so an over-target climber's
  ceiling-breach was invisible). Reported as ~N dream(s) within a 60-cycle horizon, anchored on
  the LIVE index measurement, not the logged last point.
- Staleness rides alongside slope: a factual "last dream ~Nd ago" suffix distinguishes a flat
  healthy node from a flat stale one, computed via the pipeline's _parse_ts under a two-guard
  degradation invariant (a non-string or out-of-range marker drops only the age, never raises).
- Silence rule (no-nag): an under-target shrinking node renders nothing new; the over-target
  annotation folds onto the EXISTING gauge line (never a second "over target" sentence); the one
  new standalone line fires only for the under-target-rising early-warning case.

Additive, read-only, display-only: no new CLI flag, no persisted schema key, no
CycleRecord/Budget/IndexBudget change — every existing install keeps working ⇒ patch. (Also:
simplify the versioning-policy precedent in CLAUDE.md to point at this changelog, refresh the
dream-beta-tester QA note to v0.1.85, and genericize a maintainer path in the new spec.)

## [0.1.85] — 2026-07-11

### Added — mention-tier attribution: the hook channel finally measured (P3)
The eighth enhancement increment (`docs/mention-tier-attribution.spec.md`). The always-loaded
index HOOK is how memory mostly works — a fact's `description:` steers a session with the body
never Read — yet body Reads were the ONLY detector and the read volume is near-silent (~1 read
across 27 canonicals), so the demotion/gc loop could never corroborate that read-silence means
dormancy. MEASURED premise (read-only): **218 mention occurrences / 28 stems vs 132 reads / 17
stems — 13 stems mentioned but NEVER read.**

- **A second detector on the same transcripts**: `--recalls` now also counts fact stems NAMED in
  ASSISTANT text (a compiled word-boundary alternation, longest-first, cheap raw-line pre-filter).
  Conservative guards, all pinned: BINARY per (message, stem); a ≥4-distinct-stem message is an
  index dump → dropped; assistant-only (user pastes excluded); archive stems excluded; a
  degenerate-stem guard (≥12 chars or ≥2 hyphens); dream-span excluded (`split_dream_span`
  generalized to partition reads AND mentions — reads-only fixtures unaffected).
- **Its own channel** (additive `usage.mentions`/`mention_stems`), deliberately NOT folded into
  `per_fact` — that would break the `facts_read == len(per_fact)` probative-window rule and starve
  the demotion gate; `per_fact` stays reads-only. `usage_history` unions `mention_stems` (positive
  evidence never discarded, like misses); `fleet_utility` attributes a mention through a MIRROR
  (same gate as reads) and shows a `hook×N` column — a 0-reads canonical with hook activity reads
  as instrumented-but-active, not dormant.
- **DISPLAY-ONLY in v1**: no veto, no demotion consumption — a mention is corroborative evidence,
  never sole grounds (the pinned undercount bias). Live `--recalls` verified surfacing a mention
  where reads are 0.

Additive schema keys + additive `--json`/`--utility` surfaces; no existing meaning changes ⇒ patch.

## [0.1.84] — 2026-07-11

### Added — provenance liveness: the denominator finally tracks live topology (P4)
The seventh enhancement increment (`docs/provenance-liveness.spec.md`). MEASURED red baseline on
the live fleet: **16 of 76 provenance edges (21%) were ghosts** — exactly the two known dead test
fixtures — and **≈20% of the fleet tax was ghost-attributed**; every denominator consumer
(`fleet_tax` vs the advisory, `--utility`, `--network` minds, the gated graduation lane) was
drifting on corpses, the dead-edge report was single-project-scoped, and no prune lever existed.

- **One resolver** (`_slug_matches`, factored from the train-review-fixed `_mind_unresolved`,
  which now delegates) + **`_classify_edge`**: live (a matching store HOLDS the mirror — it pays
  the pointer tax) / stale (real store, dropped mirror — never prunable, self-identifying) /
  unresolved (zero matches — the ghost class, the ONLY prunable one) / ambiguous (multi-match or
  degenerate token — never prunable; a token we can't normalize is not provably a ghost).
- **`--utility`**: per-canonical `holders_live/stale/unresolved/ambiguous` (additive keys) +
  `fleet_tax_live` (pointer × LIVE holders) printed BESIDE the provenance upper bound — which
  stays the advisory's documented denominator (re-deriving the advisory is a separate reviewed
  change). Live at ship: ≈2664 live-basis vs ≈3420 provenance.
- **`--gc . --edges [--apply]`**: the fleet-wide ghost report (resolution attempts shown);
  `--apply` prunes ONLY unresolved tokens — atomic, body-untouched, and a wrong prune
  **self-heals** via `_record_provenance` on that project's next pull (pinned). Refuses when
  `~/.claude/projects` is absent (nothing claimable ≠ everything ghost). Upgrades, never
  violates, the reported-not-pruned rule: nothing automatic, the report is finally
  fleet-complete, the confirmed lever exists.
- Live acceptance (the spec's own stated test) ran clean: 59 live · 1 stale · 16 unresolved ·
  0 ambiguous — the ghosts exactly the two known fixtures, all three live nodes (incl. the
  underscore case) resolving correctly.

New flag + additive `--json` keys; nothing existing changes meaning ⇒ patch.

## [0.1.83] — 2026-07-10

### Added — the fleet workflows lens: breadth becomes computable (W-B)
The sixth enhancement increment (`docs/fleet-workflows.spec.md`), consuming W-A's rows. Before
this, "template X recurs in N nodes" — the strongest workflow-promotion evidence, the analog of
the cascade's G2.3 witness — was uncomputable, and the distill gate's decline-dedup read only the
current node's log (the same workflow could be re-proposed fresh from every project).

- **`sync_global.py --workflows [--json]`** (+ `cm workflows`, cued — Phase 5's distill gate now
  consults it): joins every log-holding node's LATEST W-A rows by exact template string
  (`memory_status.distill_history`, the `usage_history` twin; latest-record-per-node — the W-A
  overlapping-window trap honored, pinned with a stale-record fixture). Per template/chain:
  breadth, summed latest counts, max day-spread, per-node breakdown, `fleet` flag at ≥2 nodes
  (structural, nothing fitted).
- **Head-signature families** — near-join HINTS for same-tool-flag-drift; counts never merged
  (a merged count across distinct templates would be fabricated). Under-joining stays the safe
  direction.
- **Cross-node verdict LINEAGE** (a decline anywhere blocks a naive re-propose everywhere — the
  materially-new-evidence rule, finally fleet-checkable; live first run already renders four
  real historical dispositions) · **adoption panel** (W-A `used` summed latest-per-node; zero is
  absence of evidence, never disuse) · **inventory panel** (user-level skill/command names only —
  coverage judgment stays with the MODEL, content-gated).
- **Cold-start honesty**: the live first run reads `0/7 nodes reporting` — rows accrue per dream
  since v0.1.82; fleet absence is never inferred from missing instrumentation.

New read-only mode + a read-only log aggregator; no schema change ⇒ patch.

## [0.1.82] — 2026-07-10

### Added — distill-template persistence: the workflow vertical's Phase A (W-A)
The fifth enhancement increment (`docs/distill-template-persistence.spec.md`). Template-level
distill evidence was computed every dream and DISCARDED above the counts — the pre-Phase-A usage
mistake, byte for byte: transcripts rotate, so fleet aggregation ("this workflow recurs in 4 of 6
nodes" — the strongest promotion evidence, the workflow analog of G2.3), longitudinal recurrence,
and cross-node decline-dedup were impossible to ever build. W-B (`--workflows`) and W-C (the
registrar + adoption loop) were strictly blocked on this.

- **Additive `Distill` rows, script-truth only** (injected by the existing `--from`/`--into`
  path; never hand-authored — the `n_recurring: 47` lesson, row edition): `top` (≤12 `{t,n,d}`
  template rows), `top_chains` (≤8), `used` (≤12 `{a,n}`). Compact keys — the block rides every
  dream's log line forever. Validator length-backstops against the new
  `_DISTILL_PERSIST_CAP`/`_DISTILL_USED_CAP` mirrors (cross-module smoke-pinned, the
  `_DISTILL_CAPS` pattern).
- **Privacy boundary unchanged and pinned**: rows persist WITHOUT `sample` — raw command text
  stays display-only; templates are already the firewall-screened safe tier.
- **The `used` adoption tally** (new scan branch): Skill `tool_use` invocations by name,
  window-scoped by the same per-line instant rule as Bash — the denominator the W-C lifecycle
  quadrant needs (invoked + raw templates declining = a working distillation), accrued now or
  lost to rotation. Live first run: 6 real rows on this repo. Undercount bias pinned (a skill
  can fire without a Skill tool_use — zero invocations is never sole grounds).
- The overlapping-window consumer trap is designed against up front (harness-map: W-B must
  aggregate from the LATEST record per node; the persisted `window` proves coverage). The
  SKILL schema block + scan-contract pins updated in the same commit — both schema-pin smoke
  tests fired during implementation, exactly as the convention intends.

Additive `total=False` keys + additive scan `--json` key; legacy records render unchanged ⇒ patch.

## [0.1.81] — 2026-07-10

### Added — the SessionStart beacon: the absorption-rate lever (Stage B)
The fourth enhancement increment (`docs/session-beacon.spec.md`), shipped only after Stage A
measured its premise live (12/13 fleet stores behind; a real node 18d/11-missing) and after the
plugin hooks contract was verified against current docs, not memory: SessionStart stdout is
INJECTED INTO CONTEXT, the timeout is in seconds, matchers are per-source, and exit codes cannot
block.

- **`hooks/hooks.json`** — the plugin's FIRST hook component: SessionStart on `startup`+`resume`
  only (two explicit matcher entries; never `clear`/`compact` — those are mid-flow), 2s hard
  timeout, invoking **`scripts/session_beacon.py`**. Personal-scope installs enable it with the
  plugin install itself (no separate per-hook trust prompt is documented); enterprise
  `allowManagedHooksOnly` can disable it wholesale.
- **The beacon**: at most ONE factual line, only when THIS project's store is measurably behind —
  missing/content-stale counts via `_store_gaps` (the SAME predicate `--staleness` uses, factored
  shared so the two can never disagree), the M1 ceiling-held projection, and marker age. Silence
  rules: never-participated dirs (no `*.md` — random dirs must cost zero), in-sync stores,
  `beacon_snooze_until` (per-store, set only on an explicit user ask), absent/empty global store.
  Failure posture: empty stdout + stderr diagnostic + exit 0 (a best-effort advisory never
  injects a traceback nor renders an error notice). Advisory only — never pulls; dreams stay
  explicit-trigger-only. MEASURED ~40ms end-to-end against the 2s budget.
- **The stacks cache** (the beacon's measured prerequisite: `detect_stacks` costs 2003ms on the
  fleet's biggest repo): `--pull` merge-writes script-truth `stacks` + `project_path` into
  `.consolidation-state.json` at the moment detection actually ran — model-written marker keys
  preserved verbatim; a cache-write failure warns and degrades, never fails the pull.
  `--staleness` non-trigger rows upgrade to `cached stacks (as of last pull)` (the honest basis
  ladder: live → cached → user-global-only). SKILL Phase-5 step 5 gains the load-bearing MERGE
  rule (a wholesale state-file rewrite would wipe the script-owned keys until the next pull).
- v1 reach limits (documented): no subprocesses in the hook (the git-based dream-timing advisory
  stays in `cm status`); silent on never-participated dirs (discovery is `--staleness`'s job).

New plugin component (hooks) + a new script + additive state-file keys; `claude plugin validate
--strict` passes with the hooks file; smoke pins the full behavior battery incl. the sabotage
failure posture ⇒ patch.

Hardened by a two-lens review team before merge (core-correctness + hook-surface, both verdicts
MERGE-READY): the ceiling-held projection now calls `_plan_pull` itself — the reviewer's verified
divergence fixture (a stale pointer-drift delta made the hand-rolled loop advertise a pull the
real ceiling refused) is the new pin; the stacks-cache write is atomic (Track-D convention); the
emitted line names its own snooze escape and README documents the beacon + the auto-update
rollout (a context line appearing after an update is this feature); the index is split once
(O(relevant + index_bytes), stated bound); the portable manifest validator gained a hooks.json
shape check; `cm beacon` is the debug lens. Injection resistance and the ≤2s budget were
adversarially confirmed (crafted canonicals/state never reach the line; 500-canonical stress
stays sub-second).

## [0.1.80] — 2026-07-10

### Added — fleet staleness report: absorption lag, measured per node (beacon Stage A)
The third enhancement increment (`docs/fleet-staleness-report.spec.md`). The propagation model is
eventually-consistent by design, with a structural blind spot the audit's intent map flagged:
absorption latency is unbounded and NOTHING measured it — a lagging node by definition never runs
the only flows that report lag. First live run proved the premise immediately: a real node 18
days behind with 11 missing globals and 4 content-stale mirrors, previously invisible.

- **`sync_global.py --staleness [--json]`** (+ `cm staleness`): READ-ONLY sweep over ALL project
  stores (deliberately wider than mirror-holders — a zero-mirror store is the most starved). Per
  node: last-dream marker age (`(never dreamed)` null-safe), mirror/fact counts, MISSING relevant
  globals, content-stale mirrors (body-lineage hash, v0.1.78 — what lag harms is stale KNOWLEDGE;
  hook drift is `--pull`'s refresh job), own-log usage windows + harvest-ledger coverage.
- **Scope basis honest per node**: full relevance (live `detect_stacks`) only for the TRIGGER — a
  slug is not invertible to a project path, so other nodes are assessed on user-global canonicals
  only, each row labeled, never guessed. (Stage B's SKILL-written `stacks`/`project_path` state
  cache will upgrade non-trigger rows — deferred with the SessionStart beacon itself, which this
  observe-only report exists to prove or refute first.)
- Advisory only, uncued (a maintainer/observability lens like `--network`): a node absorbs on ITS
  next dream — nothing is ever auto-pulled from here.

New read-only mode; no schema change ⇒ patch.

Hardened by a two-lens review team before merge (staleness-core + seams/adversarial, both
verdicts MERGE-READY; the convergent top finding fixed): the TRIGGER row is now unconditional
(an absent/empty trigger store was silently omitted from its own report — the maximally-starved
case); a present-but-unreadable fact is neither missing nor stale (was over-reported missing);
`never_dreamed` keys on the same unparseable-age predicate the render and sort use (a malformed
marker no longer contradicts the aggregate); `behind` includes content-stale-only nodes; future
markers clamp to age 0; the relevance predicate delegates to `is_relevant` (no 4th hand copy);
the harvest ledger's append-atomicity claim made precise (PIPE_BUF — torn lines self-heal via
the guarded reader). Review pins added.

## [0.1.79] — 2026-07-10

### Added — fleet usage harvest: capture every node's windows before the transcripts rot (audit P1)
The second enhancement increment (`docs/fleet-usage-harvest.spec.md`). Usage capture was
dream-gated per node — `--recalls` runs only inside the triggering project's own dream — so a
project that never dreams NEVER contributes evidence, and its transcripts rotate away in weeks,
destroying the windows before they can be observed (live fleet: 1 of 3 mirror nodes reporting).
Red baseline: a node holding a mirror, a real organic `Read` in its transcript, no cycle log —
`fleet_utility` saw nothing.

- **`sync_global.py --harvest PROJECT_DIR`** (+ `cm harvest`, + a SKILL Phase-1 step after
  `--pull`): for every node (`_network_nodes()` ∪ trigger), scan its transcript dir with the
  EXACT `--recalls` machinery (`_window_transcripts` + `_recall_items` + `split_dream_span` —
  dream-span excluded; only Read file-paths and arc-marker presence leave the scan, no new
  privacy surface) and append one usage-shaped row per (node, window) to the shared ledger
  `~/.claude/memory/.fleet-usage.jsonl` — `O_APPEND|O_CREAT` at `0o600`, a dot-file invisible to
  `global_facts()`/`--pull`/every index (zero always-loaded tax).
- **Watermarked + idempotent**: re-runs append nothing; a subsequent harvest that finds no new
  reads emits NO row (an empty row per invocation would mint probative zero-read windows from
  re-running the tool — evidence must accrue from time passing). Window start = the oldest
  scanned transcript's mtime (a transcript's mtime is its END, so the claimed span only
  UNDER-states coverage); all stamps ceiled, start ≤ end always.
- **Consumption (v1 rule, deliberately conservative)**: `fleet_utility` merges harvested rows
  ONLY for nodes with no own-log usage at all — own-log strictly primary, no double-count.
  Source-labeled additive `--json` keys: per-canonical `harvested_reads`/`windows_harvested`,
  payload `nodes_harvested`; same mirror-gated attribution + shadow separation; window credit
  still gates on the evidence clock (v0.1.78). Deferred to the consumption release: miss/tier
  classification (needs the node's own Phase-0 snapshot), mixed-node interval merging, and the
  `cross_project.harvested` cycle-record key (instrument-before-policy).

No cycle-record schema change; the ledger is script-truth telemetry in the `--persist` class,
report-then-apply intact (every appended row is printed). New read-mostly mode + additive
`--json` keys ⇒ patch.

## [0.1.78] — 2026-07-10

### Added — evidence-clock stamps: zero-read windows that survive mirror refreshes (audit F9)
The first increment of the audit's enhancement program (`docs/evidence-clock-stamps.spec.md`).
Fleet zero-read evidence was mtime-gated, and a STALE refresh rewrites every holder's mirror —
so ANY canonical text delta, including a pure `description:` hook tweak, wiped the fleet's
accrued probative windows (measured red: 1 → 0 on a description-only edit). With
`_DEMOTION_MIN_WINDOWS = 3` and dreams at arc boundaries, an occasionally-edited canonical's
evidence could never converge. The clock granularity was wrong, not the instinct: "content
changed" (reset is right) is not "file mechanically rewritten" (evidence must persist).

- `_as_mirror` gains two script-owned stamps under the `metadata:` anchor —
  `global_ref_since:` (when this mirror's content-lineage began) and `global_ref_body:`
  (sha1-12 of the canonical BODY, the lineage key; body-only by design, so description/stacks/
  provenance tweaks don't reset it). `run()` computes the carry at classify time (`cur == want`
  keeps its exact in-sync shape — pinned: an immediate re-pull is in-sync, zero churn);
  `promote()` mints a fresh stamp (Probe K's byte-identical follow-up pull still holds).
- **Migration wave**: a pre-stamp mirror's first refresh seeds `since` from its OLD mtime — the
  fleet's existing evidence age is preserved, never restarted from zero — and RESULT reports
  `restamped N` (one-time upgrade, not churn). Pinned: the accrued window survives the upgrade.
- **Consumer**: `fleet_utility` counts windows against the stamp when present+parseable, else
  st_mtime (legacy fallback, undercount-safe; garbled stamps fail toward less evidence);
  per-canonical `fallback_nodes` (additive `--json` key) keeps evidence provenance visible.
  A DESCRIPTION edit now preserves windows; a BODY edit resets them — both pinned.
- `_frontmatter`'s metadata-child whitelist gains the two stamp keys (the ONE shared parser —
  producer carry and consumer clock read through it, no second parse path).

No cycle-record schema change; no policy change (every demotion veto and report-then-apply
posture untouched — this only makes negative evidence accrue truthfully). Additive frontmatter
keys + one additive `--json` key ⇒ patch.

Hardened by a three-lens review team (carry-correctness / seams / adversarial — all three
verdicts MERGE-READY) before merge: the stamp strip re-narrowed to the exact three keys (the
wide `global_ref` prefix ate folded-scalar `global_reference…` continuations — the v0.1.70
class); `restamped` now counts only true mtime-seeded migrations (not body-changed legacies,
not fallback-form mirrors whose stamp can never land); stamp seconds are CEILED, never floored
(a floored clock over-credited a same-second window against the pinned undercount bias);
`docs/index-usage-and-budget-ladder.spec.md` §C4 gained the supersession back-pointer. Every
review finding pinned in smoke.

## [0.1.77] — 2026-07-10

### Docs — drift sync to code truth (audit doc-code-contract findings)
- harness-map no longer calls `--promote` "**Atomic**" — the code's own docstring says *not
  crash-atomic* (an interrupted process can leave partial state; the canonical CREATE alone is
  exclusive per Track D-2b). Reworded to **single-shot**, with the completed-call guarantee stated
  precisely.
- harness-map's claude-code stack markers corrected to what `detect_stacks` actually checks
  (a real `.claude/` dir or a `SKILL.md` file — not "`.claude`, `skill`, `agents.md`").
- CLAUDE.md's script inventory line now lists the full sync_global surface
  (`--promote`/`--utility`/`--evict`/`--allow-net-grow`/`--apply` were missing).
- The generic usage string includes `--prefer-canonical` in the `--promote` synopsis (the
  promote-specific usage already did).
- Test hygiene: the M4 vocabulary pin `not ({"release","ci-cd"} <= _DETECTABLE_STACKS)` was a
  negated-subset that stayed green if EITHER element was missing — adding `release` alone (the
  exact regression it pins) would not have failed it. Now `isdisjoint` (per-element).

Docs + one usage string + one test assertion; no behavior change ⇒ patch.

## [0.1.76] — 2026-07-10

### Fixed — robustness batch (seven audit minors, each red-first: 7/7 pre-fix)
- **Holder-token round-trip** — `_holders` now parses the same token space `_sanitize_token`
  writes: a dot/dash-prefixed holder (`.claude`; the sanitized `-scope` from `@scope`) was silently
  shortened on read, so gc's dead-edge compare could never match such a project and
  `network()`/`--utility` displayed names provenance doesn't hold. gc's dead-edge compare now also
  runs in the sanitized space on both sides.
- **Clean refusal on no-hardlink filesystems** — `promote()`'s exclusive canonical create
  (`os.link`, Track D-2b) crashed with a raw `PermissionError`/`OSError` traceback on FAT/exFAT/
  some network mounts; it now refuses cleanly (rc=1, names the hardlink constraint, nothing
  written, no temp leak).
- **mypy stack: all four documented config locations** — `.mypy.ini` and `setup.cfg [mypy]` now
  detect the stack (was pyproject `[tool.mypy]` + `mypy.ini` only — under-detection on a
  mypy-heavy fleet).
- **Poetry dotted subtables** — `[tool.poetry.dependencies.torch]` declares the dep in the header,
  not a key; the key-scan never saw it. Now parsed (groups + legacy `dev-` forms included).
- **`--tokens` archive split** — `_node_tokens` counted archive-index docs (link-lists like a
  relocated `SHIPPED.md`) as recall facts, inflating `recall_tokens`/`facts` (measured live: a
  7.6k-tok archive doc on a real node). Now excluded via the same `_is_archive_index_text` rule
  memory_status's C1 split uses — single source, the two counters cannot drift.
- **`--network` minds liveness** — minds derive from provenance basenames, which accrue DEAD
  entries (two deleted test projects measured live); a mind with no plausible on-disk store now
  renders `name?` with a footnote. Display-only (conservative zero-match heuristic; ambiguity
  reads as live) — provenance stays reported-not-pruned.
- **`originSessionId` warn split** — the C3 replication warning fired on ABSENT ids, which
  harness-map's own schema rules define as legitimate for git/commit-derived facts (steady stderr
  noise on every pull); absence is now silent, present-but-invalid still warns.

No CLI/schema change; pins in the smoke v0.1.76 block (8 checks). Backward-compatible ⇒ patch.

## [0.1.75] — 2026-07-10

### Fixed — pull-side guards: the M4-bypass surface, the phantom-store guard, the frozen-mirror lifecycle (audit F5/F6/F7)
Three confirmed audit findings, all on the pull/read side; 3/3 repro probes ran RED pre-fix.

- **F7 — fleet-dead canonicals surfaced (the M4 bypass).** The `_DETECTABLE_STACKS` "refused, not
  written" guard lives only in `--promote`; the SKILL's documented Phase-4 NET-NEW path hand-writes
  canonicals directly, so a typo'd (`gpuu`) or undetectable (`release`) `stacks:` tag landed
  unvalidated — fleet-dead (`is_relevant` can never match it), silently, forever. Every dream's
  Phase-1 `--list`/`--pull` now warns `⚠ fleet-dead canonical` naming the bad tags and the three
  fixes (retag detectable / re-scope user-global / demote) — report-only, never a block. SKILL
  Phase-4 gains the validate-first instruction on the net-new path.
- **F5 — a typo'd PROJECT_DIR can no longer mint a phantom store.** `resolve()` is non-strict and
  `store.mkdir(parents=True)` obliges: `--pull /path/typo` returned rc=0, created a store under the
  bogus slug, mirrored every user-global fact into it, and wrote the bogus basename into every
  shared canonical's `projects:` provenance — pollution `--gc` can never reclaim (the phantom's
  mirrors "exist", so its edges are never dead). `_dispatch` now refuses every project-dir mode up
  front (rc=2), with defense-in-depth guards in `run()` and `gc()` for direct callers.
- **F6 — frozen mirrors get a lifecycle.** A project that drops a stack left its stack-general
  mirrors in a state nothing could see or fix: never refreshed (`irrelevant` short-circuits
  staleness), never gc'd (the canonical is alive), index pointer still taxing every session, and
  rendered byte-identical to a never-pulled irrelevant fact. Now: `run()` renders a distinct
  `frozen(mirror)` row + a summary note; `--gc` gains a FROZEN section (report-only by default) and
  `--gc --apply` reclaims them — **safe by construction** (a frozen mirror is a replica of a LIVE
  canonical; the stack's return simply re-pulls it — pinned as a round-trip test). Also folds in
  the gc guard-TOCTOU fix: ONE `global_facts()` snapshot now feeds the mass-delete safety guard,
  the orphan scan, the frozen scan, and the dead-edge report (`_orphans` gains an optional `canon`
  parameter), closing the window where a store emptying mid-gc made every mirror look orphaned.

New pins: smoke v0.1.75 block (7 checks incl. the frozen lifecycle round-trip) + sim Probe W (CLI
phantom guard, provenance-clean assertion). No schema change; `--gc --apply` now reclaims one
additional, loss-proof category (called out here loudly); everything else is refuse-direction or
report-only ⇒ patch.

## [0.1.74] — 2026-07-10

### Fixed — fence-boundary parity: `_as_mirror`/`_body` now agree with `_frontmatter` (audit finding #1)
The audit's one verified silent-data-corruption bug. `_frontmatter`/`_is_mirror` close a
frontmatter block on ANY line starting `---` (`^---\n(.*?)\n---`), but `_as_mirror` counted only
bare stripped `---` lines — so a fact whose close fence is `----`/`--- notes` parsed as relevant
and replicable, yet `_as_mirror` stayed "inside frontmatter" to EOF and its v0.1.70
frontmatter-scoped strips ATE every body line starting `projects:`/`global_ref:` — silent mirror
corruption via `--pull` (in every puller) and via `--promote` (the origin's OWN copy rewritten
corrupted), reading in-sync forever after. The stripped-line count also diverged the OTHER way: an
INDENTED `  ---` (e.g. a block-scalar continuation) is not a fence to the parser but closed
`_as_mirror` early, leaking canonical-only `projects:` provenance into every mirror — the exact
churn class the v0.1.26 root-fix closed, reopened. All five repro probes ran RED pre-fix
(5/5 defects present, pure-function fixtures) and are pinned green in-repo (the smoke v0.1.74 block).

- **`_as_mirror` fence parity**: OPEN = the exact first line `---` (what `^---\n` anchors);
  CLOSE = any later line whose RAW start is `---`; an indented `  ---` is never a fence. The
  `_is_mirror(_as_mirror(...))` round-trip and idempotence hold on the malformed-fence shapes
  (pinned). A pre-existing corrupted mirror in the wild self-heals: the corrected `want` differs
  → STALE → refreshed on the next pull.
- **`_body` close parity**: the close-fence line is consumed WHOLE (`----`/`--- tail`) and may sit
  at EOF with no trailing newline — pre-fix, a body-less fact's frontmatter was left unstripped,
  so two body-less facts with differing frontmatter compared UNEQUAL and promote's Guard-5
  spuriously refused a clean reconcile (M2 false negative in the refuse direction).

No CLI/schema change; both deltas are correctness on malformed-but-parser-valid input ⇒ patch.

## [0.1.73] — 2026-07-10

### Fixed — evict accounting truth: plan once, measure freed, refuse gainless (audit F1–F4)
A multi-agent end-to-end audit of the cross-project layer (independent finders + adversarial
verifiers, every finding reproduced in a HOME-sandboxed fixture) found four defects in the
`--pull`/`--evict` flow sharing one root: run() decided pull/hold in one place, the `--evict`
pre-scan re-decided against a STATIC index in another, and `freed` was DERIVED from frontmatter
instead of measured. All five repro probes ran RED against the pre-fix tree (5/5 defects present)
and flip green with this release — the measure-first gate. Design: `docs/evict-accounting-truth.spec.md`.

- **`run()` restructured classify → plan → execute.** A new pure `_plan_pull` replays the pull
  loop's accumulating index accounting ONCE, in iteration order; the write loop and the `--evict`
  gate both consume that single plan and can no longer diverge (F3, measured: the old static
  `held_pre` pre-scan let an evict pass its fit-check, the loop's accumulation re-held the target
  global, and an **authored fact — with no canonical to re-pull it — was destroyed for zero
  gain**). STALE-refresh pointer deltas now count toward later hold decisions (F4, measured: an
  untracked +22t refresh let a subsequent pull land the real index at ≈3862 > the 3840 ceiling).
- **`freed` is MEASURED from the live index line** (new pure `_index_line_cost`, `](stem.md)`
  anchor), never derived from `_pointer_line` (F2, measured both ways: an UNINDEXED evictee
  credited ~33 phantom tokens — `_remove_index_pointer`'s False return silently ignored — and the
  pull breached the hard ceiling at ≈3857; a fat HAND-WRITTEN 74t line was judged by its lean
  derived ~7t pointer and the best candidate refused). An unindexed evictee is now refused
  (frees nothing); a fat real line is credited honestly.
- **A managed MIRROR is refused as evictee** and the EVICT-TO-RECEIVE candidates table now offers
  **authored facts only**, each with its measured real-line cost (F1, measured: evicting a mirror
  of a live relevant canonical re-pulled it into the freed room the SAME pass — alphabetical order
  deciding — so the held global never landed; opposite order oscillates forever). The refusal
  routes to the real lever: demote/delete the canonical, then `--gc`.
- **The gain-gate is Guard-3 by construction**: an evict is accepted only when the A/B plan replay
  (with vs without the evict) demonstrably lands ≥1 additional held global; the refusal prints
  both plans. `_evict_frees_enough` is superseded and removed (an internal pure helper; its smoke
  pins are replaced by `_plan_pull`/`_index_line_cost` pins).
- **The evict happy path is now pinned IN-REPO** (sim Probe V/V2 + a six-check smoke block) — it
  previously had zero in-repo coverage (smoke.py conceded the E2E "ran green out-of-band"), which
  is exactly where the audit's majors were hiding. SKILL.md + harness-map ceiling prose updated to
  the gain-gate semantics.

CLI surface unchanged (`--pull --evict=FACT [--allow-net-grow]`); no schema change; every
behavior delta is refuse-direction or accounting-correctness. Backward-compatible ⇒ patch.

## [0.1.72] — 2026-07-09

### Fixed — the diff-modal's "any changed file must be observable" gap
A real dashboard screenshot showed the ledger's diff count under-reporting: a `CLAUDE.md`
edit and four index-line-only fact compressions were narrated in "Changes & Decisions"
with **no way to ever surface a diff for them**, because `capture_diffs` (v0.1.32) had a
hardcoded `store != "memory"` exclusion plus a `memory/MEMORY.md` carve-out treating the
index as pointer churn, not a real file change. Confirmed against the actual session's
own `/tmp` Phase-0 snapshot + `git diff` before touching anything.

- **`audit_snapshot`/`capture_diffs` now cover every tracked store** — memory facts, the
  `MEMORY.md` index, the CLAUDE.md hierarchy, and relocate-target repo docs. A
  claude_md/repo_doc file over `_DIFF_CONTENT_CAP_TOKENS` (8000; this repo's own
  CHANGELOG.md is 175KB) skips content-stashing to avoid bloating the Phase-0 `/tmp`
  snapshot every dream — `capture_diffs` flags it `size_capped` instead of emitting a
  misleadingly one-sided diff. Memory facts stay uncapped (always small).
- **`Entry.files: list[str]`** (additive, `total=False`) — the model now DECLARES which
  `audit_snapshot` label(s) an entry touched (`memory/x.md`, `memory/MEMORY.md`,
  `claude_md/CLAUDE.md`, …) when authoring it in Phase 5, so the dashboard links
  deterministically instead of guessing. An index-line-only correction lists
  `memory/MEMORY.md`; a correction touching both a fact body and the index lists both
  (the ledger renders one primary link plus a `+ <file>` chip per extra file). SKILL.md's
  Phase-5 entry-authoring instructions and cycle-record schema block updated together
  (the existing SKILL↔TypedDict smoke pin catches drift).
- A cycle record with no `files` field at all (every record logged before this version)
  degrades to the old name-match heuristic, now widened: an `auto-mem` entry with no
  diff for its own `memory/<name>.md` falls back to a shared `memory/MEMORY.md` diff if
  one exists; a `repo`-store entry auto-links the single unambiguous `claude_md/`or
  `repo_doc/` diff if there's exactly one candidate (never guesses when there's more
  than one — an unresolved entry stays a plain, honest label rather than risking a wrong
  link).
- The dashboard's "changed file with no narrated entry" safety-net row is unchanged in
  purpose but now fires far less often — with declared/heuristic linking absorbing most
  diffed files into their narrated row, an orphan `changed` row is now a genuine signal
  that the model's narration missed something, not a structural side-effect of the old
  memory-only scope.

Backward-compatible throughout (additive `total=False` schema key, legacy records still
render via the widened heuristic, no flag/CLI change) ⇒ patch.

## [0.1.71] — 2026-07-09

### Fixed — Track D: global-store write atomicity + seed-path hardening
The shared global store (`~/.claude/memory`) is the one place two different projects'
dreams can write concurrently. A Gate-1 spec (two single-agent review rounds, the second
of which caught a bug in the first's own proposed fix) scoped this to the actual threat
model — a single-user tool, not a hostile multi-tenant host — and explicitly rejected a
lock/mutex subsystem as disproportionate. Every fix is sabotage-verified (reverting it
flips its regression test red). See `docs/track-d-write-atomicity-seed-hardening.spec.md`.

- **D-1: atomic global-store writes** — the 2 real `GLOBAL`-store write sites
  (`promote()`'s canonical write, `_record_provenance()`'s two `projects:`-list writes)
  now route through a new `_atomic_write_text` (write-temp + `os.replace`, same-directory
  sibling so the rename never crosses filesystems). A concurrent reader sees fully-old or
  fully-new content, never a torn/partial canonical.
- **D-2b: the `promote()` create-create race** (found at Gate-1 review, worse than the
  audit's own finding) — two projects concurrently promoting different local facts onto
  the same NEW `canon_name` could silently clobber one another's canonical AND erase the
  loser's own local copy via the follow-on mirror write. A new `_create_exclusive`
  (write-temp + `os.link` — deliberately NOT `O_CREAT|O_EXCL` against the destination,
  which would create it empty-then-filled and reopen D-1's torn-read window) makes the
  create atomic-and-exclusive: the loser is refused with an explicit retry message
  (rc=1), never silently overwritten. A Probe K sub-test injects a concurrent
  canonical-create into a live `promote()` run to pin the integration end-to-end.
- **D-2: a documented accepted gap** — `_record_provenance()`'s read-modify-write of a
  canonical's `projects:` list is not mutually exclusive; a lost update (one provenance
  entry dropped, body untouched, self-healing on that project's next promote/pull) is
  accepted rather than fixed: a real lock needs `fcntl` (banned — no POSIX-only modules)
  or hand-rolled staleness detection (its own bug class). Documented in the docstring +
  `harness-map.md`'s cross-project model.
- **D-3: `--seed` write hardening** — the Phase-0 seed (which can hold recall-candidate
  fact text) now routes through the existing `_write_private` helper (owner-only 0o600,
  set atomically at creation) for consistency with `--snapshot`; it previously landed at
  the process's default, often world-readable, mode.
- **Gate-2a/2b follow-ups on the new primitives themselves** — a failed temp write no
  longer leaks a partial `.tmp<pid>` sibling (`_create_exclusive` at Gate-2a,
  `_atomic_write_text` parity at Gate-2b; errors still propagate, never masked), plus an
  unreachable leftover `return` removed.
- Also lands audit task #29's remaining two bare-`read_text` sites (`extract_signals.py`'s
  `_marker_ts`, `memory_status.py`'s state-file read) with explicit `encoding="utf-8"`;
  its other two were subsumed by D-1's refactor.

Backward-compatible throughout (no schema change, no flag/CLI change — a new refusal
path only where data was previously silently lost) ⇒ patch.

## [0.1.70] — 2026-07-07

### Fixed — DevSecOps pentest remediation: evict/mirror/git-argv hardening
A full-scope pentest pass (both plugins) confirmed 8 findings; every fix here is independently
reproduced against a real subprocess/sandbox (not just accepted from the pentest's own verifier
votes), and every regression test is sabotage-verified (reverting the fix flips it red).

- **`--evict=` path-traversal** — a crafted fact name could walk outside the project's own store
  and delete an arbitrary file; now runs through the same charset guard (`_safe_stem`) `promote()`
  already applies to `local_fact`/`canon_name`.
- **`--evict=MEMORY` (and case-variants) self-clobber** — the reserved-index check was case-SENSITIVE,
  so `--evict=memory`/`Memory` (and, separately, a global fact literally named `memory.md`) sailed
  through on a case-insensitive filesystem (macOS APFS/HFS+) and would `unlink()` + rebuild the
  project's own live `MEMORY.md`, dropping every previously-indexed pointer. Closed by a single
  shared `_is_reserved_stem()` predicate (case-insensitive), now used by every guard that used to
  hand-roll its own `f.name == "MEMORY.md"` / `_RESERVED_STEMS` check: `promote()`, the `--evict=`
  guard, `global_facts()`, `_orphans()` (the destructive path feeding `gc --apply`'s `unlink()`),
  `_inbound_links()`, `_node_tokens()`, `_network_nodes()`.
- **Mirror-anchor body injection** — `_as_mirror()`'s `global_ref:`/`metadata:` anchor checks now
  scope strictly to the frontmatter block (`dashes == 1`), so a crafted fact **body** can no longer
  masquerade as a mirror stamp.
- **`git check-ignore` argv injection** — a relocate target whose relative path starts with `-`
  used to reach `git check-ignore` as a bare positional arg (parsed as a flag); now separated with
  `--` so the path always reaches git as a path, never an option.

### Fixed — DevSecOps pentest remediation: the secrets firewall bundle
The firewall (`_looks_secret`/`_SECRET`/`_entropy_blob`) is now single-sourced in
`memory_status.py` (the dependency root — `extract_signals.py` imports it, mirroring the
pre-existing `_is_mirror` precedent) so `memory_status.py`'s own new git-commit-subject scan
(`_scrub_commit_log`) can use it — commit subjects reaching a rendered report or `--json` were
previously ungated, a stark asymmetry against the session-signal source, which was already
firewalled.

- **The confirmed bypass**: a keyword-less high-entropy value chunked into 3+ slash segments was
  exempted wholesale (an artifact of an old "≥3 slashes ⇒ it's a path" heuristic). Closed.
- **Four ReDoS instances** (ordinary `re.search`, catastrophic backtracking) — the compound-keyword
  arm's prefix/suffix quantifiers, the URI-creds arm, the JWT arm (via a repeated anchor with no
  periods), and the `authorization|bearer` arm's whitespace sandwich. Each confirmed by direct
  timing measurement (O(n²) pre-fix, linear post-fix) before and after, not just theorized; all four
  arms now carry bounded quantifiers.
- **Coverage gaps closed**: a Stripe webhook signing secret (`whsec_…`), and a CLI-flag-shaped
  keyword arm (`--password value`, `-li_at value`, `-cf_clearance value`, space- or `=`-delimited —
  previously only the `key=value`/`key: value` forms were covered).
- **False-positive fixes** (each independently reproduced, not accepted on the pentest's word):
  ordinary `keyword: <short word>` commit prose (`"token: bump TTL to 3600"`, `"secret: rotate the
  signing key"`) no longer reads as a leaked value; a versioned/dated path segment
  (`v0-1-68-index-lifecycle-…`) no longer reads as a digit-bearing secret; a deep `/`-path ending in
  an ALL-CAPS filename stem (this repo's own `.../SKILL.md`, `.../README.md` shape) no longer reads
  as a mixed-case token — `_entropy_blob` scopes both its mixed-case and digit signals to the same
  per-`/`,`-`,`_`,`.`-delimited token, rather than a whole-blob check that over-fired on this exact
  path shape.
- **Two residual gaps are accepted and documented, not chased further** (see `_entropy_blob`'s and
  `_SECRET`'s docstrings): a keyword-less secret chunked into segments each under the entropy floor,
  or split across segments that individually are single-cased but disagree with each other; and a
  short, no-digit, single-case weak password (`password=qwerty`) — indistinguishable in shape from
  an ordinary short English word in the same position. Tightening either reopens an ordinary-prose
  false positive on the other; the firewall favors fewer false positives on routine commit messages.
- A ~900,000-char commit subject is now capped (`_COMMIT_SUBJECT_CAP`) before it ever reaches the
  firewall regex.

### Fixed — Track D: CI Python floor + dashboard regression coverage
- **CI test matrix widened 3.10–3.13 → 3.8–3.13** (3.8/3.9 pinned to `ubuntu-22.04`, which can still
  provision them; 3.10+ stays on `ubuntu-latest`) — closes a long-standing gap between the
  documented "3.8+ stdlib-only" floor and what CI actually verified.
- **Two v0.1.68 dashboard fixes gained automated regression pins** in `tests/smoke.py` (a source-text
  check on `dashboard.template.html`'s CSS `background-repeat:no-repeat` and its verdict-tag
  classifier regex) — v0.1.68 shipped without them; a real layout/paint proof still isn't feasible
  headless (jsdom parses the DOM but computes no layout/paint), so pixel-level dashboard QA stays
  eye-judged, but a source-text reversion of either fix now trips red.
- Doc sync: README/CLAUDE.md's "validated on 3.10–3.13" claims corrected to 3.8–3.13 throughout.

Every fix above: no cycle-record schema key changed, no CLI flag removed/renamed, no
install/marketplace contract changed — legacy records render unchanged → **patch**.

## [0.1.69] — 2026-07-05

### Fixed — audit-hygiene remediation (Track A of the four-lens release-readiness audit)
Every behavioral fix landed red-first (a smoke check that FAILS on the pre-fix tree — 8 red gates
recorded on the PR), to the Gate-1-reviewed spec `docs/audit-hygiene-remediation.spec.md` (3
independent review rounds to zero inconsistencies).

- **Parsed-instant window compares in `extract_signals.py`** (`extract()` + `_recall_items()`) — the
  per-line `ts <= since` was a RAW-STRING compare, so an offset-bearing marker/`--since` (`+02:00`,
  `+0200`) against CC's `Z` stamps mis-ordered lexicographically and silently mis-windowed boundary
  sessions. Ported distill's v0.1.58 twin fix (`_parse_ts` instants; unparseable fails OPEN,
  recall-biased).
- **`cm extract`'s TTY report `_sane()`s signal text** at the presentation boundary — ESC survives
  `_norm` (it's Cc, not Cf), so repo-controlled error output could inject terminal escapes; `--json`
  stays raw-but-escaped (the bytes can BE the signal there).
- **Store-scan convention in `_node_tokens`/`_network_nodes`** — three unguarded `read_text` calls
  crashed `cm tokens`/`cm network`/the dream's Phase-5 network capture on a concurrent gc/chmod
  vanish; now skip-and-count-readable, per the module's own convention.
- **`_run` labels a git failure** (one stderr line per process, `_GIT_WARNED`) — a missing/broken/
  timed-out git was indistinguishable from a clean no-commit repo, silently under-scoping the dream
  to "NOTHING TO CONSOLIDATE".
- **Genericity: the maintainer username scrubbed** from the shipped `memory_status.py` docstring
  (slash AND dash-form slug) + public tests/docs, and a NEW smoke **genericity pin** (slash
  `/home/<name>` + slug `-home-<name>-`, allowlist you/u/x/d/nobody, restrictive name class) keeps
  any personal path out of the shipped/public tree permanently.
- **SKILL `--list` claim corrected** — `held` counts exist only under `--pull` (harness-map was
  already right); prose + inline comment aligned to the code, no behavior change.
- **Schema-pin hole closed** — `usage`, `usage.per_fact[0]`, `demotion` + explicit
  `audit.claude_md`/`audit.repo_doc` rows join the SKILL↔TypedDict pin loop (the two newest schema
  blocks looked pinned and weren't; the carve-out comment is exhaustive again).
- `.gitignore` gains `.ruff_cache/`.
- Fixes/tests/docs only — no schema key, no flag change; legacy records render unchanged → **patch**.

## [0.1.68] — 2026-07-05

### Fixed — the dashboard's masthead glow tiled down the whole page; the demotion panel's dormant verdict carried no tag
Reported live from a rendered dashboard screenshot (the same "look at the actual archive, not raw
JSON" discipline as v0.1.62/v0.1.64): the "02 Shared Consciousness" section showed an unrelated bright
patch bleeding through its middle, and the demotion sub-panel's "dormant" state read as bare italic
text beside distill's always-badged sibling panel.

- **`background-repeat:no-repeat`** on the masthead's `body` radial-gradient glow — `background:var(--paper)`
  (the shorthand) resets `background-repeat` to its initial `repeat` before `background-image` sets the
  700px-tall glow, so without an explicit `no-repeat` the browser tiled a fresh copy of it every ~700px
  down the entire page. Confirmed by pixel-sampling a headless render: before the fix, a second glow
  appeared mid-page wherever a section happened to land on that interval; after, it's a single instance
  that fades within ~300px of the masthead — exactly what the color values (`--glow` deliberately close
  to `--paper`) were designed for.
- **The demotion panel's verdict now parses the same leading-disposition-word grammar as distill's**
  (`dormant`/`demoted`/`justified`/`none`, mirroring distill's `created`/`proposed`/`nothing`) into a
  bordered `.tag` badge ahead of the prose — a dormant triage now reads `[DORMANT] 1 probative window …`,
  matching distill's `[NOTHING] the smoke→mypy…` rhythm, instead of unbadged italic text beside an
  always-badged sibling.
- Presentation-only — `dashboard.template.html`'s embedded CSS/JS; no cycle-record schema change, no
  new keys → **patch**.

## [0.1.67] — 2026-07-05

### Added — index-lifecycle Phase C: the utility policy (demotion triage · miss loop · fleet utility)
The policy leg that consumes Phase A's usage instrument — built to the code-review-skill-gated design
in `docs/index-usage-and-budget-ladder.spec.md` §Phase C (the spec gate verified 44 finder candidates
inline after the verifier fleet died on session limits; ~20 findings — including two policy-killing
evidence-gate defects in the draft — were folded in before a line of code was written). Ships
**DORMANT-AND-HONEST**: the instrument-before-policy pin is amended, not violated — a per-fact
evidence gate keeps the rank inert until real usage windows accrue (today: 1/3 on this repo, 0
elsewhere), the Phase-B ceiling's acceptance shape.

- **`usage_history` + `iter_cycle_log` (memory_status)** — longitudinal aggregation of the cycle
  log's script-truth `usage` blocks. Reads merge from EVERY window (positive evidence always vetoes);
  only full-fidelity, parseable windows are PROBATIVE for zero-read evidence (a 0-transcript window
  observed nothing; a cap-truncated one can't prove any fact unread; a store's first
  `"(no marker …)"` window is skipped, never fatal). `render_html.read_history` now delegates to the
  shared reader (single source).
- **`demotion_candidates` (the `*_candidates` family)** — PURE, ranks only, report-then-apply.
  Eligible iff PER-FACT: ≥ `_DEMOTION_MIN_WINDOWS` (3) zero-read probative windows (an edit restarts
  the fact's clock — nothing latches) ∧ indexed ∧ non-mirror ∧ 0 reads ever ∧ no KEEP-signal
  description (lessons stay, by design) ∧ never a logged miss ∧ not counter-justified
  (`demotion_justify` in the state file — a per-item delta-detector re-firing at
  +`_DEMOTION_JUSTIFY_REFIRE` (5) windows; malformed fails open toward surfacing). Ranked by hook
  cost, capped at `_DEMOTION_BOTTOM_K` (5); candidates carry indegree + nearest-description
  similarity (`SequenceMatcher`, `autojunk=False`, canonical pair order) as merge evidence; veto
  tallies surface in the report. Dispositions are `entries[]` rows — demote-to-archive / compress /
  merge-to-stub (NO deletion under this policy) / counter-justify.
- **The miss-detector** — `--recalls` classifies organic reads by tier **at WINDOW START** (the new
  `--before <snapshot>` reuses the Phase-0 snapshot, so a fact archived mid-pass is never
  misclassified); an archived-tier read = `usage.misses` (computed from the UNCAPPED tally) — a
  transcript-visible demotion error, rendered red, proposed for re-promotion, and a PERMANENT
  candidacy veto via the log. `inject_usage` also **strikes** any just-read stem from the seeded
  `demotion.surfaced` (current-window blindness closed deterministically, `demotion.struck`).
- **`sync_global --utility [--json]`** — READ-ONLY fleet usage evidence for the gc lever:
  per-canonical reads aggregated across every node's log with a **mirror check before attribution**
  (a same-stem never-pulled local reports as `shadow_reads`, never attributed) + `fleet_tax` =
  pointer × holders (0 for unheld; provenance stated as an upper bound) against the warn-only
  **`GLOBAL_FLEET_TAX_ADVISORY`** (5000 est tok — measured Σ 3283 + ~50% headroom, 2026-07-05).
  `promote()` prints the same advisory when the fleet total crosses it. Never a block, never auto-gc.
- **`_parse_ts` relocates to memory_status** (the dependency root; extract_signals/distill_scan
  re-import the SAME object — smoke-pinned identity) and **`_USAGE_FACT_CAP` rises 20 → 40** (the
  heaviest node measured 22 facts/window — permanently non-probative under the old cap; producer +
  mirror + pins move together, additive-safe).
- Contract: additive `usage.archive_reads`/`usage.misses` + the `demotion` block
  (`windows_observed`/`eligible`/`surfaced`/`struck`/`verdict` — no model-tallied disposition counts;
  entries[] stays the single source) + validator backstops; SKILL Phase-5 triage step (pinned BEFORE
  the final budget re-read) + Phase-4/step-2/step-5 prose + schema block + harness-map + `cm utility`
  synced. Legacy records render byte-identically on all three renderers (key-presence gated).
- Gates: smoke **680** (41 new Phase-C checks) · mypy clean · accumulation sim · manifests +
  `plugin validate --strict` · dream-beta-tester ci_check **0 FAIL** (live run — the target-gate
  oracles read fields Phase C never writes) · live G-C5: this repo seeds
  `demotion: {windows_observed: 1, eligible: 0}` and `--utility` reports 1/3 nodes, read-only.
- **Gated by an inline adversarial code review** (single no-swarm mode, user-directed; multiple finder
  angles over the full diff, every candidate verified against the live code before reporting). One
  confirmed medium: `--utility` credited a holding node's ENTIRE probative-window history to a
  freshly-pulled mirror — overstating zero-read evidence, the same fact-age defect the spec gate caught
  in C2, reproduced fleet-side; fixed by mtime-gating the per-canonical window count (a refresh resets
  the clock — undercount, the safe direction; live effect: 7/26 canonicals honestly dropped to
  "uninstrumented"). One confirmed low: transcript-derived stems (from `Read` file_paths) printed to
  the terminal unsanitized in the `--recalls` report + the strike's stderr line — now routed through
  `_sane` (the git-subject convention; also hardened Phase A's pre-existing per_fact print). Two nits
  (a silent non-dict `--before` fallback now warns; an unused tier-tuple unpack). Refuted: log
  double-count (the producer `_persist` is marker-idempotent).

## [0.1.66] — 2026-07-04

### Added — index-lifecycle Phase B: the HARD CEILING (a second, independent budget signal)
The budget ladder's real-harm rung, built to the 3-lens-gate-revised design in
`docs/index-usage-and-budget-ladder.spec.md` §Phase B (the original single-field re-key was found
load-bearing-broken at the spec gate — it would have silently stripped triage from the amber band,
flipped the maintenance pivot, and inverted dream-beta-tester's HIGH-severity `CHK-REM-SEED-CONTRACT`
release oracle; the shipped design is ADDITIVE instead, and all three stay byte-for-byte unaffected).

- **`INDEX_CEILING_FRACTION` (0.6) / `INDEX_CEILING_TOKENS` (≈3840 est tok)** — one canonical
  est-token threshold derived from the native 25KB byte cap (the line axis stays `cliff_pct`'s job).
  Structurally standing-justify-INDEPENDENT: the comparison never reads `standing_justify`, so there
  is no suppression to tune and no justify escape — over the ceiling, only shrinking satisfies.
- **M1 re-key to the ceiling** — `sync_global --pull`'s hold and the `--evict` fit-check now pass
  `INDEX_CEILING_TOKENS` at the call site (`_would_net_grow` gains a `budget` param whose target
  default preserves the pure contract the v0.1.38 smoke pins exercise). An over-TARGET (amber) store
  now RECEIVES verified knowledge; only a store past the real harm boundary holds. The target gate
  (`remediation.required`, triage levers, standing-justify, prune-pressure, maintenance pivot) is
  untouched and still keys to `INDEX_TOKEN_BUDGET`.
- **`remediation.over_ceiling`** — a sibling flag of `required` (additive, `total=False`; absent on
  healthy/legacy records), rendered red at all three gauges: the ASCII dashboard index gauge +
  remediation panel (both branches — suppression never hides it), the Phase-0/`cm status` report, and
  the HTML meter (net-new — the archive previously rendered no remediation state; also corrected the
  meter wording that called the *target* a "ceiling"). `budget.index.ceiling_tokens` carries the
  display value.
- **Write-time fat-hook lint** — `_fat_hook_warning` (pure, smoke-pinned): every pointer
  `sync_global` writes (pull, refresh, promote — one choke point) warns on stderr when it exceeds
  `HOOK_TOKEN_WARN`, naming the CANONICAL's description as the fix site; never truncates. `--pull`'s
  RESULT line counts them.
- Contract: 2 additive schema keys; SKILL schema block + the M1/hold prose sites + harness-map +
  `cm` help synced; legacy records render byte-identically (gated).
- **Gated by a max-effort code-review workflow** (independent finder angles + verify pass) after the
  initial implementation: found and fixed a real accounting bug (the fat-hook `RESULT` line double-
  counted/mislabeled a no-op STALE-mirror refresh as "written" — `_ensure_index_pointer`'s return value
  was discarded at the call site), refactored its root cause (the function now returns `(wrote, is_fat)`
  instead of forcing the caller to re-derive the lint from scratch), removed an unenforced-default drift
  risk (`_would_net_grow`/`_evict_frees_enough`'s `budget` param is now REQUIRED, no silent fallback to
  the pre-Phase-B target), and replaced a hardcoded constant mirror in `render_html.py` with a live
  reference to `memory_status.INDEX_CEILING_TOKENS` (the module was already imported).

## [0.1.65] — 2026-07-04

### Fixed — full doc sync to the v0.1.63/v0.1.64 state
An independent doc-audit agent (the same discipline as v0.1.56/v0.1.59) cross-checked README/CLAUDE.md/
SECURITY.md/harness-map.md/the Phase A spec doc/`cm`/`extract_signals.py` against the actual shipped
code. Found and fixed 4 confirmed drift points (5 targets checked out clean, incl. `harness-map.md`,
already synced in the v0.1.63 commit itself):

- `docs/index-usage-and-budget-ladder.spec.md`'s status header still read "DRAFT for review" and framed
  Phase A as a future proposal — it shipped. Corrected to state Phase A SHIPPED (v0.1.63), Phase B/C
  still the design to build against.
- `CLAUDE.md`'s versioning-precedent list stopped at v0.1.58, omitting the four already-*released*
  versions v0.1.59–v0.1.62 (v0.1.62 — the current `plugin.json` version — wasn't even in its own
  precedent list).
- `cm`'s help text for `cm extract` and `extract_signals.py`'s own module docstring both omitted the new
  `--recalls [--into SEED]` mode (works today via the dispatcher's transparent `"$@"` forwarding, but was
  invisible in both places a user would look for it).

Docs + one help-text/docstring line only, plugin behavior byte-identical → **patch**, same class as
v0.1.56/v0.1.59.

## [0.1.64] — 2026-07-04

### Fixed — SKILL.md: WAKE's own two lines duplicated each other (a second, adjacent defect to v0.1.62's)
Reported live from the RENDERED HTML archive (a screenshot, not the raw chat text): even after v0.1.62
ended the debrief's redundant second sign-off, WAKE's own bookend — the italic surfacing paragraph
*and* a separate bolded `☀️ **Awake.**` line — still duplicated each other. The archive renders them as
two separate sun-marked bullets: the exact shape v0.1.62 fixed one layer up, recurring one layer down
in the same contract. The surfacing paragraph already conveys emergence from the dream; a second,
content-free "Awake." line added nothing.

- **WAKE is now a single italic paragraph, full stop** — no trailing bolded line, ever, in any case
  (the true no-op's single dreamless line was already this shape and needed no change). The debrief's
  bold lead line (v0.1.62) is unchanged and remains the only thing that follows WAKE.
- Fixed at all three sites that stated the old two-line shape (the beats table, the debrief section's
  own framing sentence, and the Phase-5 step-7 echo) plus the `render_html.py` WAKE cue text shown to
  the model at the moment the beat is due — a duplicated rule that drifts is worse than one, so all
  four were updated in lockstep and smoke-pinned against re-drift.
- No cycle-record schema change (dream.wake is still one string; nothing new to inject) → **patch**,
  same class as v0.1.62.

## [0.1.63] — 2026-07-04

### Added — index-lifecycle Phase A: recall-usage instrumentation + hook/cliff telemetry (observe-only)
From the 2026-07-04 over-budget investigation (design: `docs/index-usage-and-budget-ladder.spec.md`):
the always-loaded index pins at ~100% of `INDEX_TOKEN_BUDGET` with every fact "merited" — merit was
only ever judged on content-truth, nothing measured whether a fact is ever *recalled*, hook cost was
unbounded (2 fat pointers = 17% of the whole budget, MEASURED), and the real failure boundary —
Claude Code's SILENT 25KB/200-line MEMORY.md truncation — was represented nowhere. Phase A adds the
instruments; **no behavior change** (no new gates, no changed thresholds — the budget-ladder
semantics are Phase B, separately specced).

- **`extract_signals.py --recalls [--json] [--into SEED]`** — organic fact-body recall tracking over
  the dream window: streams the window transcripts, collects `Read` tool events on store fact files,
  excludes dream-procedure reads by the CM_DREAM_ARC Bash-event line-span (whole-transcript exclusion
  measures 0 forever on a dream-heavy repo — MEASURED), and injects the script-truth `usage` block
  into the cycle-record seed (fails LOUD on a bad seed path — the distill `--into` contract). Pinned
  bias, stated everywhere it surfaces: **0 reads = absence of evidence, never evidence of no use**
  (retention + span-exclusion undercount).
- **Hook-cost telemetry** — `hook_stats` flags index pointer lines over `HOOK_TOKEN_WARN` (60 est
  tok); the Phase-0 report names the offenders; the seed carries `budget.index.fat_hooks` /
  `hook_max_tokens`; the dashboard gauge shows `hooks N>60t (max ≈…)`.
- **Cliff telemetry** — `cliff_pct` measures proximity to the harness-native truncation cap in the
  harness's own units (`NATIVE_INDEX_CAP_BYTES`/`NATIVE_INDEX_CAP_LINES`; exact bytes/lines, the
  chars/4 estimator deliberately not involved); report + dashboard render it on the index gauge and
  go red at `CLIFF_NEAR_FRACTION` (80% — silent data loss near).
- **Contract:** additive `usage` block + three additive `budget.index` keys (all `total=False` —
  legacy records render unchanged); `validate_cycle_record` gains the usage impossible-count backstop
  (`_USAGE_FACT_CAP`, smoke-pinned to the producer, the `_DISTILL_CAPS` shape); SKILL schema block +
  Phase-5 step + harness-map synced; `cm log` gains a READS column (em-dash on legacy records).

## [0.1.62] — 2026-07-04

### Fixed — SKILL.md: the dream's closing debrief was a double sign-off, not a single one
Reported directly from a live dream's own output: the WAKE bookend (`*☀️ …*` → `☀️ **Awake.**`)
was immediately followed by the debrief's own lead line, which SKILL.md instructed to carry
"outcome + one functional emoji" (e.g. 🌙) — three landing gestures in three lines (☀️ / ☀️ / 🌙)
reading as a redundant second sign-off stacked on the first, not one coherent close into a summary
card. This was a defect in the **contract itself** (both places SKILL.md stated the rule — the
dream-arc section and its Phase-5 step-7 echo — said the same thing), not a one-off authoring slip;
left alone, every future dream would reproduce it.

- **The debrief's lead line is now text-only, no emoji.** WAKE already performs the pass's one
  closing gesture; the debrief is the card that follows it, not a second landing. The lead line
  states the outcome banner in bold (e.g. **LIGHT PASS**) and nothing else.
- **The generic 🌙 "dream" section marker is retired** from the debrief's functional-emoji palette.
  The remaining emoji (🚀 ship · 📊 dashboard · ✓/⚠ status) stay, but only as in-body markers for a
  section that names something concrete — never as a whole-debrief decoration.
- Both instruction sites were fixed in lockstep (a duplicated rule that drifts is worse than one
  that's merely wrong); a new smoke pin asserts the old "outcome + one functional emoji" phrasing
  is gone and the new no-emoji-lead-line rule is present at both sites, so this can't silently
  regress.

Prose-only change to the skill's own operating instructions — no schema, `--json`, or script
behavior change; no effect on any persisted cycle record → patch. 597 smoke (+3) + mypy + sim +
manifests + `--strict` green.

## [0.1.61] — 2026-07-04

### Fixed — HTML dashboard: a structural rule for two-column alignment (v0.1.60 was incomplete)
v0.1.60 tightened the network graph's own frame, but that was a fix to *one chart's* box, not to the
*layout mechanism* — the actual defect. CSS Grid's `.cols` rows already stretch both columns to equal
height (the default `align-items:stretch`), but each column's content just sat at the natural height at
the TOP of that equal cell — so any two columns of differing content height (fewer meters vs. a legend +
caption; a compact chart vs. a taller one) left the shorter column's caption stranded near the top with a
dead gap below it, while the taller column's caption landed much lower. Visually this read as exactly what
it was: two independently-floating columns with no shared baseline — "loose," "free-form," not a coherent
grid. This was present in **all three** two-column sections (Longitudinal, Shared Consciousness, This
Pass), not just the one chart v0.1.60 touched.

**The fix is a dashboard-wide structural rule, not a per-chart patch:** every `.cols` column is now a flex
column (`.cols>div{display:flex;flex-direction:column}`), and its trailing metadata block — the legend +
caption, wrapped in a new `.meta` class — gets `margin-top:auto`. In a flex column, an auto top-margin
consumes all the leftover vertical space above it, which pins `.meta` to the bottom of the (grid-equalized)
column regardless of how tall the chart above it is. This holds for any content height and any viewport
width above the existing 760px stack-to-single-column breakpoint — it references no pixel value, no
computed geometry, no JS at all (unlike v0.1.60's viewBox-fit, which stays, since it solves a different,
narrower problem: how big the network graph renders within its own frame).

Applied to all three `.cols` sections, including the two JS-built columns in "This Pass" (audit/verify),
whose trailing `.cap` is now wrapped in `.meta` at construction time. DOM-verified: every column pair's
caption-bottom now lands at the identical pixel (`baseline_delta_px: 0`) across all three sections.

Template/CSS/JS only — no record schema, `--json`, or script-behavior change; legacy dreams render →
patch. 594 smoke + mypy + sim + manifests + `--strict` green.

## [0.1.60] — 2026-07-04

### Changed — HTML dashboard: the Shared Consciousness network chart's metadata is now coherent
In the "02 Shared Consciousness" section, the two charts presented their metadata inconsistently: the
left chart (the budget meters) kept its caption tight beneath it, while the right chart (the network
graph) had its legend + caption **detached into a lower band**, reading as a separate section rather than
part of the graph. Root cause: the network `<svg>` had a fixed `height:200px` but the graph draws small
and centered in a wide coordinate space, so ~47px of dead space pushed the legend/caption well below the
graph (the right metadata sat 87px lower than the left).
- The network SVG is now **fixed-height + auto-width** (`#net{height:154px;width:auto}`, overriding the
  global `svg{width:100%}`) and its **viewBox is fitted to the drawn node geometry** in JS — computed from
  the node positions/radii/labels (NOT `getBBox`, which throws/returns empty on a not-yet-visible archived
  dream section), so the box frames the graph tightly for ANY node count.
- The legend and caption are **centered under the centered graph** (`.legend.center` + new
  `.cap.center`), so the right chart is internally coherent (centered graph + centered metadata) the way
  the left is (left bars + left caption).

Result (DOM-verified in-browser): dead space around the graph 47px → ~10px, the legend now sits 24px
directly beneath the graph (was 46px + a detached band), and the metadata offset from the left chart 87px
→ 41px (the residual is just the graph being taller than two thin bars — the metadata is now attached to
its chart, which was the incoherence). Template/CSS/JS only — no record schema, `--json`, or script
behavior change; legacy dreams render (the fit is presentation-time) → patch. 594 smoke + mypy green;
verified via the actual DOM (screenshots render light, so layout was confirmed by measurement).

## [0.1.59] — 2026-07-04

### Docs — full sync to the v0.1.58 distill-hardening state
The v0.1.58 release brought its own plugin docs current (SKILL.md, harness-map.md), but the repo-root
maintainer/public docs lagged. An independent doc-staleness audit (all six docs cross-checked against the
shipped code) found the drift; fixed:
- **SECURITY.md** — the distill firewall description still documented the RETIRED v0.1.55 behavior
  ("screens every Bash command *before* templating, so a credential-shaped command is dropped"). Rewritten
  to the v0.1.58 firewall-AT-EMISSION model: a credential-shaped command still counts into its command-CLASS
  template (recurrence stays accurate) and into the `scanned.secrets_omitted` transparency counter, but its
  raw text never surfaces — the display `sample` becomes an omission label and every emitted template is
  screened on its `_norm`'d form (so a zero-width-split secret is caught) before it can be a row or chain
  endpoint. (The public security doc was the highest-value fix.)
- **CLAUDE.md** — the "Releasing" versioning-precedent list (ended at v0.1.55) extended through v0.1.58 with
  the additive keys spelled out; the layout table's `distill_scan.py` entry corrected (compound-command
  chains, not "`&&`-chains"; the `--into`/`--from` capture flags noted); the cycle-record-contract bullet's
  `validate_cycle_record` description extended for the v0.1.58 impossible-distill-count backstop (already
  documented in harness-map.md — CLAUDE.md was the odd one out).
- **README.md** — the architecture tree omitted `_ui.py` (pre-existing; every renderer imports it and
  CLAUDE.md's layout lists it) — added.

Docs-only, no plugin-runtime/schema/`--json` change (the published plugin under
`plugins/consolidate-memory/` is byte-identical to v0.1.58 apart from the version bump; legacy records
render) → patch. Gated by the standard battery (smoke + mypy + sim + manifests + `--strict`) via
`release.sh` + an independent doc-audit agent that verified SKILL.md, harness-map.md, PREFLIGHT.md, and the
`cm` help as already-current.

## [0.1.58] — 2026-07-04

### Fixed — distill hardening: closed noise classes, honest firewall, script-truth capture (the end-to-end audit arc)
A full business-logic audit of the distill vertical (three live corpora + a 27-case adversarial battery)
found the v0.1.55 "zero noise" acceptance had already rotted (~15% of this repo's top-40 rows were shell
syntax: `[ = ]` ×33, `}` ×16, `continue`/`exit 1` ×10 each, plus an `exit 1 → }` junk CHAIN), the literal
interpreter stoplist regenerating its false class under other spellings (`.venv/bin/python -` ×204 on a
sibling corpus), the reused firewall silently un-counting ~5% of commands as false positives with zero
transparency, and the ONE production distill record carrying a hand-mirrored, structurally-impossible
`n_recurring: 47` (hard cap: 40). Rebuilt per `docs/distill-hardening.spec.md` (two adversarial review
rounds, design + impl lenses; every load-bearing claim proven by execution):
- **Closed POSIX noise classes** — the keyword tables now cover the REST of shell syntax, not just loop
  keywords: test guards (`[`/`[[`/`test`), brace groups (`{` carries, `}` drops), control heads with args
  (`exit 1`/`break`/`continue`/`return`/`:`), env-manipulation (`set`/`trap`/`shopt`/…), assignment
  keywords (`export`/`declare`/… — drop-whole: they never carry a command, and prefix-stripping would
  open bare-name junk), `!` negation and `eval`/`exec` carriers (with an fd-plumbing guard: `exec 2>&1`),
  and a purely-numeric template screen. Unlike the verb stoplist, POSIX syntax is a finite set — this
  class of rot ends rather than shrinks.
- **Structural interpreter rule** — an inline-body carrier (`… <interp> -|-c|-e`) or bare interpreter is
  matched by token BASENAME on the post-truncation segment tokens, so any path (`/usr/bin/python3`,
  `.venv/bin/python`), any version (`python3.12`), and any runner (`uv run`, `docker run img`) is the
  same one-off class — while `git commit -q -F -` (×165 live) and `python -m pytest` survive, pinned.
- **Firewall at the EMISSION point** *(additive `scanned.secrets_omitted`; `commands` now includes
  flagged commands — ~+5% on the measured corpus)* — a credential-shaped command still counts into its
  class; what it can never do is surface raw text: its samples become an omission label (suppression
  keys off the ONE `_norm`-based flag — a zero-width-split secret is caught; a raw re-probe would miss
  it, pinned) and every emitted template is screened at a single choke-point covering rows AND chain
  endpoints. The predicate itself is untouched; ~5% recall returns, with the count made visible.
- **Script-truth capture: `distill_scan.py --into <seed>`** *(additive flags + additive
  `Distill.window`/`secrets_omitted` schema keys)* — the counts are now script-ONLY, injected by a
  sub-key MERGE that preserves model-authored judgment fields unless `--verdict`/`--proposed`/`--created`
  replace them (a provided list-flag replaces the whole list — idempotent); the SKILL's hand-mirror
  count instruction is DELETED (its absence is pinned), and `validate_cycle_record` gains an
  impossible-count backstop (warns above the scanner caps; caps mirrored under a cross-module smoke pin).
- **Window + CLI honesty** — a per-line `ts <= since` filter (a long-lived session file no longer leaks
  out-of-window lines into counts/day-spreads); `--since` validated at the CLI (exit 2 on garbage —
  which would otherwise lexicographically drop everything); a nonexistent project dir and genuinely
  unknown flags warn on stderr (`--sicne X` no longer silently scans a wrong dir as a 0-session result);
  `cm distill` help documents `--since`/`--into`.
- **Docs made true** — SKILL gate gains leg 6 (*not previously DECLINED* — read recent verdicts from the
  cycle log; new evidence, never a re-ask); chains wording corrected everywhere to `&&`/newline/`;`-glued
  (README ×2, SKILL, module doc); `harness-map.md` gains the missing distill section (scan contract,
  record block, `--into` recipe, acceptance recipe); the stale docstring residual claims rewritten
  honestly (`||` is ~16% of commands but low-HARM; `$()` mis-segmentation is nested-only; the single-`&`
  fusion, stoplisted-head pipelines, and control-terminator bridge chains are named as accepted
  residuals).

A high-effort workflow-backed code review (20 agents) then found 10 confirmed impl regressions in the
above, all fixed pre-merge:
- **The firewall screen probed the raw template, not the `_norm`'d one** — a zero-width-split credential
  that flagged the command could still leak into a template row; now screened through `_norm` (the
  security-critical fix), with a non-vacuous zero-width smoke pin.
- **The per-line window compared raw strings** — a local-offset or compact `--since` silently dropped
  in-window lines or zero-scanned the corpus; now compares parsed UTC **instants** via a shared
  `_parse_ts` (which also normalizes a `±HHMM` no-colon offset, ending the 3.10-vs-3.11 skew).
- **CLI honesty** — a trailing value-flag (its value lost) or a genuinely unknown flag is now a usage
  error (exit 2), judgment flags without `--into` warn loudly, and `main` **exits non-zero when an
  `--into` capture fails** (the deleted hand-mirror left no fallback, so a silent failure was
  unrecoverable).
- **`--from <scan.json>`** — the SKILL now scans ONCE, judges that output, and injects the SAVED scan,
  so the recorded counts are byte-identical to the judged evidence (no drift, no double scan).
- **Sample recovery** — a class first seen in a credential-shaped command now upgrades its display
  sample once a clean occurrence of the same class appears (was pinned to the omission label by arrival
  order).
- **Renderer parity** — `secrets_omitted` now shows on the ASCII DISTILL line and the HTML "This Pass"
  panel (the schema-cascade contract). NOTE: `scanned.commands` now **includes** firewall-flagged
  commands (~+5% vs v0.1.57), a deliberate cross-version value shift for transparency.

A SECOND workflow review (thoroughness pass over the fixes) then found 7 more, 5 fixed:
- **`inject_into` could crash on a partial `--from` scan** (a stale scan missing `secrets_omitted`/
  `window` KeyError'd instead of a clean exit) → defensive `.get()` defaults + a KeyError backstop.
- **The eval/exec fd-guard false-dropped digit-named tools** (`exec 7z …`, `eval 2to3 …`) → a precise
  fd-redirect match so only real redirects (`exec 2>&1`) drop.
- **`_parse_ts` was promoted into `extract_signals`** so the file-prune and the per-line window share ONE
  timestamp parser (the reimplementation-pin; a divergent copy let the `±HHMM`-offset prune silently
  no-op), plus a `_day_str` helper retires the now-dead `_day_of` inline copy and a doubled `seg.split()`.
- Two PLAUSIBLE findings accepted as consistent-by-design (a secret-only day counting toward the advisory
  `scanned.days`; a skipped `--into` leaving an absent block — already caught by the beta family + the
  non-zero exit).

Additive `--json`/schema keys (`window`, `secrets_omitted`) + additive flags (`--into`/`--from`/judgment)
+ stricter noise-dropping under an additive shape + SKILL/doc prose → patch. 594 smoke (+48) + mypy + sim
+ manifests + `claude plugin validate --strict` green (incl. a pin that the `secrets_omitted` count renders
on the ASCII + HTML dashboards — a review follow-up that also caught + fixed a `12.0`→`12` float format).
Live acceptance: this repo 40 rows + 20 chains
**zero junk** (was ~15%) with `secrets_omitted: 83` surfaced; the sibling Python corpus's top row is now
the real gate (`pytest -m unit` ×284/14d) with the `.venv/bin/python -`/`-c` false classes (×299) gone.

## [0.1.57] — 2026-07-03

### Changed — dashboard coherence + the quiet dream (design feedback from the first live v0.1.54–56 dream)
The first end-to-end dream on the new stack surfaced visual-design debt in the HTML archive and an
over-decorated dream voice. Both fixed; user-directed design, gated by a completed adversarial review round
(13/13 agents; 8 verified findings, all fixed pre-merge):
- **The quiet dream** *(contract change, SKILL + cues)* — the dream channel drops the blockquote (`> `) accent
  bar: plain italics alone mark the voice. Emojis now exist ONLY on the bookends — SLEEP opens `*💤 …*`, WAKE
  opens `*☀️ …*` — intermediate beats carry none. All six cue hints, the schematic, and the schema comments
  follow; the HTML dream panel normalizes LEGACY stanzas at display time (multi-emoji runs, bare ☀/☁ variants;
  an emoji-only legacy line is preserved rather than vanishing).
- **HTML dashboard, sections 01–03 re-aligned** — the two Longitudinal charts share one plot frame (equal
  heights, aligned tops); the rigor strip thins its gap/cycle labels by a skip factor when segments get narrow
  (with a collision guard so the forced last numeral never smears into its neighbor); the churn band's right
  axis restacked; Shared Consciousness gains a matching caption + de-centered legend; This Pass unifies both
  panels' lead/head/caption rhythm.
- **The distill verdict is readable** — its own full-width block (counts right-aligned in the header; the
  disposition as a tag — `created` green, `proposed` amber only while *awaiting* (a declined proposal renders
  neutral, resolved), `nothing` neutral; the explanation as a serif sentence). A disposition-only verdict
  shows its tag without the false "no verdict recorded" fallback. The ASCII dashboard renders the verdict in
  full on a wrapped continuation line (was a mid-word 60-char cut) with a 220-char runaway guard.
- Also: the verify panel's "N confirmed" is green only when N > 0; the emoji-strip regex writes its variation
  selector as an explicit `️` escape (no invisible source character).

Template/prose/presentation only — the record schema and every `--json` contract unchanged; legacy records
render (better) → patch. 546 smoke + mypy green; layout verified live in-browser (DOM + eyeball).

## [0.1.56] — 2026-07-03

### Docs — full sync to the v0.1.54 (dream-arc) + v0.1.55 (distill) feature set
Documentation-only, plus one cosmetic in-plugin fix; no runtime behavior change (legacy cycle records still
render, existing installs keep working):
- **SKILL.md** — the cycle-record schema *example* now shows the index budget as **1500** (was a stale
  `1200` — the v0.1.45 re-ground); the `--seed` already writes the real value at runtime, so this only
  corrects the documented example a model reads.
- **README** — the **distill** vertical (recurring-workflow → durable artifact, report-then-apply) and the
  **dream-arc voice** are described in Usage; the `cm` command list (`distill`/`report`/`log`) and the
  architecture script tree (`distill_scan`/`render_html`/`render_log`) are brought current; the example
  dashboard's index budget is corrected `1200 → 1500`.
- **CLAUDE.md** — `distill_scan.py` + `_ui.py` (with its `CM_DREAM_ARC` dream-cue) added to the layout; the
  versioning precedent extended through v0.1.55 (every version additive).
- **SECURITY.md** — records that `distill_scan.py` applies the **same** secrets firewall
  (`_looks_secret` before templating), so both transcript readers are covered.

All backward-compatible ⇒ patch. 544 smoke + mypy green.

## [0.1.55] — 2026-07-02

### Fixed — distill: clean signal, chain structure, captured verdict ("does nothing" no more)
The distill vertical (v0.1.51) measured broken on its richest corpus: 43% of commands collapsed into an
`echo` noise row ranked #1, the REAL command in every echo-led chain was never counted (a 4× undercount —
smoke 60 → 234), recurrence had no episode dimension, and the outcome left zero persistent trace — "ran and
correctly proposed nothing" was indistinguishable from "never ran". Rebuilt per
`docs/distill-signal-and-capture.spec.md` (two adversarial review rounds; the design lens PROVED two of its
findings by execution):
- **All-segment extraction, order-hardened** — every segment of a compound command templates (not just the
  first); heredoc BODIES strip FIRST (before quote-strip, which deleted the quoted tag — the proven B1
  defect; `<<-` included); `\`-continuations join; redirects truncate split-keep-head (no dangling `2` from
  `2>&1`, no leaked filenames); loop bodies keep their command (`do mypy $f` → `mypy` — the proven M2
  defect); a stoplist drops generic/investigation verbs + inline-interpreter false classes. A template
  counts once per command.
- **Day-spread + chains** *(additive `--json` keys)* — each row/chain carries `days` (the episode dimension:
  ×27 across 9 days is a workflow, ×27 in one hour is a loop; ranked by days then count, rank is a hint) and
  `chains` surfaces adjacent kept-segment bigrams with BRIDGE semantics (`a && echo ok && b` → `a → b`).
  Acceptance on the live corpus: zero noise rows; `smoke ×234/9d`, `./release.sh ×52/9d` clean; chains read
  like the actual workflow (`smoke → mypy ×105`, `git push → gh pr create ×30`).
- **The verdict is captured** *(additive schema)* — a `distill` block on the cycle record
  (`sessions`/`commands`/`n_recurring`/`n_chains`/`proposed`/`created`/`verdict`); the SKILL step now REQUIRES
  a one-line disposition verdict naming the top candidate and the gate leg that decided it (`nothing:
  <candidate> fails <leg>` — a bare "nothing" is non-compliant), with the double null-priming hedges
  ("usually proposes nothing" / "'Create nothing' is EXPECTED") deleted. Gated `DISTILL` dashboard line +
  archive line; a `distill_capture` LOW/WARN beta family (PASS iff the verdict is non-empty;
  `maintenance.pivoted` passes SKIP; unknown versions fail closed) — built on a new `_latest_capture_check`
  scaffold shared with `dream_arc_capture` (refactored onto it, behavior pinned by its existing cases).

Additive `--json` keys + additive `total=False` schema + SKILL prose + presence-gated renderer lines →
patch. 544 smoke (+52) + mypy green. TWO max-effort adversarial code-review rounds hardened the shell
normalizer pre-merge: round 2 fixed 12 clusters (env-prefix drop of `CM_DREAM_ARC=1 python3 …` — the
SKILL's own idiom; the post-heredoc glue; `&>` redirects; else/case-arm recovery); round 3 — the first to
run its verify pass to completion — closed the heredoc amputation for good (match only TERMINATED heredocs,
so a quoted or multi-line `<<` can never delete a following command), removed `$(…)` command substitutions
(a value, not a command — they leaked `… )` junk rows), made day-spread UTC-deterministic across machines,
and shed subshell parens. Live-corpus acceptance: 40 recurring rows + 20 chains, zero noise in either.

## [0.1.54] — 2026-07-01

### Fixed — the dream-arc contract: the persona that "does absolutely nothing" now has mechanics
The dream persona shipped twice as SKILL prose (v0.1.47 styling, v0.1.53 "bookends REQUIRED") and failed
twice in live use — plain procedural narration, at most a token gesture at the end. Root-caused (escape-hatch
wording · no output contract · load-time instruction for a write-time need · style and function sharing one
channel · an unsanctioned register) and rebuilt as a three-leg system (spec:
`docs/dream-arc-contract.spec.md`, two adversarial review rounds + a dedicated prose gate):
- **A pinned sequence contract** *(SKILL rewrite)* — SLEEP 💤 (first output on invocation) → a DREAM BEAT 🌙
  opening every phase → a one-line SURFACING before the plain Phase-4 proposal → WAKE ☀️ (+ `☀️ **Awake.**`)
  before the debrief. Format pinned to standout blockquote-italic (`> *🌙 …*`, 1–2 dream emojis); content
  improvised from each pass's real material; proportionality scales DEPTH, never presence. The "voice
  recedes" hedge and the defeatist "honest limit" coda are gone; the dreamy register is explicitly sanctioned.
- **Write-time cues** *(new, env-gated)* — every SKILL command line now carries `CM_DREAM_ARC=1`; the scripts
  answer with one-line `[dream-arc]` stderr reminders (`_ui.dream_cue`, which owns the authority prefix +
  never-echo suffix) at the exact moment a beat is due — the same deterministic-carrier move as v0.1.53's
  `--into`. Cues are phase-correct end-to-end: the plain read's cue is phase-neutral (it also serves Phase 5's
  final gauge re-read), `sync_global` cues only its dream-flow modes (never Phase-4 `--promote`), the
  `render_dashboard --persist` cue splits on procedure integrity (clean → *continue Phase 5*; exit-3 → *back
  to Phase-3*, never a wake), and the WAKE cue fires at `render_html` — the arc's true terminal boundary
  (after the mandatory archive open), not two steps early. stderr-only + stdout-only parsers keep every
  `--json` consumer, `cm`, the tests, and the beta oracle byte-identical; without the env var, nothing changes.
- **The dream is captured** *(additive schema)* — a `dream` block (`sleep`/`beats[]`/`wake`) on the cycle
  record, mirrored from the conversation (conversation first — filling the record instead of narrating is a
  defect). The ASCII dashboard gains a gated one-line `DREAM ARC ✓ sleep · N beats · wake` presence line; the
  HTML archive renders each dream's stanzas serif-italic in a new "The Dream" panel (esc()-guarded); the
  dream-beta-tester gains a LOW/WARN `dream_arc_capture` family (latest persisted record; SKIP-by-empty;
  pre-v0.1.54 caveat) so a skipped arc is a measured regression, not an anecdote.

Additive `total=False` schema key (legacy records render byte-identically), opt-in env var, SKILL prose →
patch. 492 smoke (+49) + mypy green; max-effort adversarial code-review round fixed 6 confirmed defect
clusters pre-merge (early-wake cue ordering, `str(None)` truthiness ×2, a fail-open version gate,
literal-`**` leakage in the archive panel, two wrong-phase cues).

## [0.1.53] — 2026-06-23

### Fixed — signal-pipeline hardening: the per-release defects a live v0.1.51 dream surfaced
A real dream run showed the signal pipeline was roughly half-noise (measured: 39 human signals / ~18 noise; 8
error signals / 0 durable gotchas) plus a hard crash — one lingering defect per recent release. Each
root-caused + fixed (spec: `docs/signal-pipeline-hardening.spec.md`):
- **Compound acks no longer masquerade as signal** *(v0.1.50)* — "Ship it please", "Yes ship it", "Let's
  continue" etc. were classified `statement`/score-1 (the anchored `_ACK` only matched a lone ack word). Now
  `_classify` checks markers FIRST, then a control-opener + length-bounded ack matcher demotes them to score-0
  (a marker-bearing turn like "yes, but **always** X" stays a preference; a long signal turn opening with
  "sure" is protected by the word-bound).
- **`[Image #N]` markers + pasted screenshot paths stripped** *(v0.1.50)* — leading attachment noise is removed
  to reveal the real instruction that follows (which `norm[:300]` had truncated off); a pure image-only /
  path-only turn becomes noise. (Quoted paths may contain spaces — the real screenshot case.)
- **Error channel cleaned of transient noise** *(v0.1.49)* — ruff lint/format, the model's own inline-script
  (`<stdin>`/`<string>`) tracebacks, and Claude-Code auto-mode classifier messages (denial / unavailable) are
  dropped as harness-artifact / transient noise. A genuine env error (a `ModuleNotFoundError` from `python3 -c
  "import x"`, `ruff: command not found`, an HTTP 401, a filesystem `PermissionError`) is still KEPT.
  **Reverses a v0.1.49 call:** classifier-denials were kept as "highest-signal"; they're now noise (a transient
  harness event, not a durable env gotcha — the real lesson is authored from session context).
- **`KeyError: 'audit'` crash fixed** *(v0.1.22 flow)* — `memory_status.py --audit <snapshot> --into <cycle>`
  now injects the audit block straight into the cycle record (deterministic; no model-improvised merge). The
  SKILL Phase-5 step uses it; absent `--into` it still prints the summary (backward-compatible).
- **Dream-arc styling un-hedged** *(v0.1.47)* — the opening + closing debrief are now REQUIRED bookends; the
  "function wins, voice recedes" hedge is scoped to the intermediate phase narration only (the model was
  generalizing it to the whole arc, so the voice evaporated in every dense pass).
- **Phase-2 `--json` schema documented** *(v0.1.48)* — the SKILL now states the keys (`counts.surfaced`, each
  signal's `signal_type`), so the orchestrator stops reading `kind`/top-level `surfaced` (both `None`).

All backward-compatible (the `--json` schema is unchanged, `--into` is additive, the rest is SKILL prose) →
patch. 443 smoke + mypy green; validated end-to-end on the real transcript that surfaced the defects.

## [0.1.52] — 2026-06-23

### Fixed — cross-store dangling-link resolution (the recurring 1–2 "broken wikilinks" every cycle)
Root-caused the dangling-link false positive that surfaced on **every** consolidation cycle. The detector
(`memory_status.dangling_links`) resolved each `[[target]]` against ONLY the single store it scanned, but the
memory graph is multi-store (project-local · global canonical · per-node mirrors) and cross-scope, so two
legitimate link shapes were mis-flagged — now distinguished:
- **`dangling_links(auto_mem, global_dir=…)`** resolves against **local ∪ the global canonical** (the only
  OTHER store a slug-scoped node can pull from — NOT fleet-wide). A `[[target]]` that is a real global fact
  pending mirror (a budget-HELD up-link) is **pending-pull, not dangling** (the M1 `held` count is the real
  signal) — this was the recurring false positive (a link flickered "dangling" for 4 cycles until its global
  target was finally pulled). A target absent from BOTH stores stays flagged: a real typo, OR a sibling-
  project-local DOWN-link genuinely unreachable here (correctly still surfaced).
- **Both fill sites widened together** — the Phase-0 `maintenance.dangling` seed AND the SKILL Phase-5
  `health.dangling_links` fill — so the two counts can't drift (smoke-pinned). `global_dir=None`/missing ⇒
  byte-identical legacy behavior (backward-compatible — hence a patch).
- DRY: the global-store path is now the `GLOBAL_STORE` module constant (cf. `sync_global.GLOBAL`).
- Tests: +3 (Class B resolved · Class A still flagged · backward-compat + global-absent) + 2 SKILL drift-pins
  + 1 cross-store isolation guard. Spec: `docs/dangling-cross-store-resolution.spec.md`.

## [0.1.51] — 2026-06-22

### Added — distill: a workflow-recurrence PHASE in the dream sequence (distill arc, stage 2 — the MVP)
The dream's **second vertical**: where it consolidates FACTS into memory, **distill** detects repeated WORKFLOW
patterns and PROPOSES a durable artifact (a command / skill) — report-then-apply. Inspired by MiMo-Code's
`/distill`, but **integrated as a PHASE of the regular dream** (one skill package, frictionless — the user's
call), not a separate skill/command. Measure-first validated the premise on cm's own transcripts (the gated
release cycle recurs ≥12×). Full design: `docs/distill-phase.spec.md`; plan: the `distill-feature-plan` memory.
- **`distill_scan.py` (new stdlib script)** — a LIVE within-project recurrence scan (NO persisted cross-dream
  tally → the D1 recurrence family stays deferred). Reuses `extract_signals`'s `_norm`/`_looks_secret`/
  `_window_transcripts` + `memory_status.slug_for` (no re-implementation). Extracts assistant `tool_use` Bash
  commands over a recent (~30-day) window — BROADER than the dream's `marker..HEAD`; firewall FIRST; then
  normalizes to a CLASS **template over MULTI-LINE input** (split on `\n`/`&&`/`;`, drop pure-`cd` + leading
  `VAR=` segments, heredoc→head, drop quoted/paths/branch/value args) and counts recurrence (`count≥2`, ranked).
  `--json` contract: `{window, scanned:{sessions,commands}, recurring:[{template,count,sample}]}` — DATA only
  (the model does the workflow-recognition + proposal). `cm distill [DIR]` added.
- **The distill PHASE (SKILL.md Phase 5 step 6; render renumbered to step 7).** The model RECOGNIZES a coherent
  repeated workflow from the templates (not a single generic verb), GATES it (≥2× + stable + repeatable + clear
  stopping + **not-already-covered** — inventory existing skills/commands first), and **PROPOSES the SMALLEST
  artifact** report-then-apply. **"Create nothing" is the common, expected outcome** on today's small fleet.
- **Safety (the highest-blast-radius feature — gate-reviewed SOUND):** the script CANNOT author (DATA only); the
  phase **NEVER auto-writes an executable artifact** — it presents the proposal **PLAIN/un-styled**, the human
  confirms, and a single confirmation authorizes **ONE named artifact** (not a suite). Proposed artifacts are
  **genericized** (no abs paths / machine names / personal values — the firewall catches credential-*shaped*
  values, not machine-specific ones). Known gap (acknowledged): an authored artifact lands outside the Phase-5
  `--audit` mutation trail, so it's named explicitly in the closing debrief.
- **Backward-compatible (PATCH):** additive new script + additive phase; **no `CycleRecord` schema/TypedDict/
  smoke-pin change** (the proposal is in-conversation, like Phase 4); no removed/renamed key/script/flag. +12
  smoke checks (the `_template` recall guard on REAL command forms — multi-line/heredoc/bare-cd/VAR=, branch
  grouping, push≠pull — + end-to-end scan recurrence/firewall/create-nothing/contract) → 406 passed, 0 failed.
- Gated: independent spec-review (report-then-apply + blast-radius SOUND; 1 BLOCKER [the `cd &&` strip was wrong
  for the 92%-multi-line channel] fixed + re-measured on real data, + 5 gaps folded in) + `/code-review`. mypy
  clean · sim ✓ · `claude plugin validate --strict` ✓ · dream-beta-test 0 FAIL.

## [0.1.50] — 2026-06-22

### Changed — signal-extraction foundation: 2 channel-precision sharpeners (distill stage 1)
A measure-first, 5-lens discovery (`docs/signal-extraction-foundation.spec.md` + the `distill-feature-plan`
memory) partitioned every signal-extraction enhancement against a 3-part bar — ship only if MEASURED-real AND
non-redundant with the existing 3 sources + git AND zero new firewall surface. The decisive result: **sharpen
channels already parsed; don't add sources** (every new-source candidate failed — file-hotspots = git-derivable;
a command/Bash source = 87% `cd` + 5% firewall-trip + already-covered by errors). This ships the 2 unanimous
sharpeners; both are PRECISION fixes to existing channels (no new source → no new firewall surface).
- **Teammate-message `_NOISE` anchor.** `_NOISE` caught the bare `<teammate-message` tag but MISSED the
  `Another Claude session sent a message:` prose wrapper (the prose precedes the tag, so the bare-tag arm never
  fired). Measured: **~49-55 such turns ≈ 7% of human turns leaked through as human feedback**, all carrying
  `scope_hint="user"` (predominantly the `preference` class) → they fed user-global facts. Anchoring the prose
  prefix drops them (agent coordination, not human intent). Verified 0 leaks remaining on real projects.
- **Error-channel dedup to a CLASS (`_error_key`).** The error channel deduped by EXACT text + capped at
  `MAX_ERRORS=8`, so byte-noise (exit codes, line numbers, temp paths, PIDs, timestamps) fragmented one error
  class into many rows and diluted the cap. `_error_key` keys by a normalized class: **head-extraction** (key
  from a `…Error/Exception/Warning:` head onward) drops the `Traceback … File "/…", line N` preamble + frames
  while PRESERVING the message, then only UNAMBIGUOUS byte-noise normalization (exit code / line number / ISO
  timestamp). Deliberately normalizes nothing whose value could be SIGNAL — **NO path→/PATH, NO blanket
  `\d{3,}`→N, NO bare-hex→HEX, NO bare-clock→TS** (the binary in `foocli: command not found`, `HTTP 404` vs
  `500`, a Windows HRESULT `0x80004005`, a slice `arr[10:20]` are signal, not noise — the byte-noise list is kept
  symmetric). `_dedup` gains an optional `key=` (default = exact text → human dedup UNCHANGED); errors dedup by
  `_error_key` before the cap. Normalization only — the cross-session recurrence MULTIPLIER is deferred (D1).
- **Deferred** (per the discovery + anti-bloat): the exact-form-literal salience nudge (modest measured benefit,
  heuristic FP risk, rarely binds — the skeptic lens recommended exactly these two); the D1 recurrence family;
  the D4 `/distill` workflow→artifact vertical.
- **Backward-compatible (PATCH):** signal schema unchanged (v0.1.48 canonical keyset untouched), no new source,
  no new firewall surface, no removed/renamed key/script/flag; `_dedup`'s default key preserves human behavior
  exactly; keys never alter the stored verbatim text (display unaffected). +7 smoke checks (the `_error_key`
  merge/separate recall guard incl. same-family-different-identifier, the foocli/barcli + hex/clock no-over-merge
  pins, + end-to-end drop/collapse) → 394 passed, 0 failed.
- Gated: independent spec-review (no blockers, both changes prototyped; 4 gaps folded in — dropped the
  over-merging path-strip, corrected the leak framing to ~49 all-scope=user, strengthened the recall-guard
  fixture) + `/code-review`. mypy clean · sim ✓ · `claude plugin validate --strict` ✓ · dream-beta-test 0 FAIL.

## [0.1.49] — 2026-06-22

### Changed — filter transient tool-protocol noise from the error-signal channel (+ cap)
`extract_signals.py` surfaces `is_error` tool-results as a Phase-2 gotcha source, but — unlike human turns
(which get a noise filter AND a cap) — the error channel got **neither**, flooding Phase-2 input with Claude's
own transient tool-usage mistakes. **Measured across the fleet** (12 projects, 57k transcript lines): of 186
non-secret error tool-results (77 unique), **~73% of raw / 52% unique are `<tool_use_error>`-wrapped** —
Claude's own tool-protocol retries (file-not-read, string-not-found), never an environment gotcha. Full
measurement + design: `docs/error-signal-noise-filter.spec.md`.
- **Drop `<tool_use_error>`-wrapped results** (`_ERROR_NOISE`, an `elif` after the secrets firewall so the
  firewall keeps precedence). It is the one error class that is high-volume, **harness-stable**, and
  **zero-false-drop** — a tool-usage error is never an env gotcha (those arrive as bash stderr / exit codes).
  Verified there is NO structural discriminator (protocol- and bash-errors share keys), so the content marker
  is the only signal (anchored to a LEADING wrapper, so an env error that merely quotes the marker mid-body is
  not false-dropped — zero recall loss vs unanchored, 136/136 fleet-wide; substrate-drift watch noted).
  Filtered errors increment `counts["noise"]`.
- **Cap surviving errors at `MAX_ERRORS` (8), AFTER the filter.** Errors are unranked (chronological, no score
  sort), so the cap is a **flood backstop, not a ranking**; running it post-filter avoids wasting cap slots on
  noise. (Honest limit: post-filter it can still clip a chronologically-late durable gotcha in a pathological
  flaky-loop session — the accepted cost; the cap rarely binds, ~37 survivors fleet-wide / 12 projects.)
- **Deliberately NOT filtered** (the over-reach avoided): inline-script tracebacks — a `python3 -c "import X"`
  → `ModuleNotFoundError` IS a durable "X isn't installed here" gotcha; lint substrings (rot + over-match); and
  the auto-mode-classifier **denials** (the highest-signal error class — redundancy with human turns resolves
  at fact-level dedup in Phase 2/4, never by dropping). The residual falls to the cap + the model's Phase-2 judgment.
- **Honest framing:** this is **context HYGIENE** (less transient noise in the input the model already curates),
  **NOT signal recovery** — no previously-missed gotchas are rescued (the durable yield is ~6–7 items fleet-wide).
  Note: `counts["noise"]` now also counts filtered errors (it has a single consumer — the `_report` summary line).
- **Backward-compatible (PATCH):** signal schema unchanged (the v0.1.48 canonical keyset is untouched); the
  output simply carries fewer noise rows + a bounded error count. No removed/renamed key, script, or flag.
  +7 smoke checks (drop / keep-env-gotcha / keep-denial / keyset-intact / cap-after-filter) → 387 passed, 0 failed.
- Gated: independent spec-review (no blockers, all 10 checks verified against source + a re-run of the
  measurement; 1 medium + 3 low gaps folded in) + `/code-review`. mypy clean · sim ✓ · `claude plugin validate
  --strict` ✓ · dream-beta-test gate 0 FAIL.

## [0.1.48] — 2026-06-22

### Fixed — uniform signal schema in `extract_signals.py` (the `[error|?|s?]` rows)
`extract_signals.py --json` (the Phase-2 session-signal extractor) emitted a NON-UNIFORM signal schema:
human-sourced signals carried `signal_type` + `score`, but **error-sourced signals did not** — so any consumer
reading those fields with a fallback (the user's ad-hoc one-liner `s.get('signal_type','?')`, and even the
script's own `_report`) rendered a literal `?`/`s?` on every error row. (These are extracted, marker-classified
session *signals* — `source · signal_type · scope_hint · score · text` — not embeddings; the `?` was purely a
missing-key artifact.) Full root-cause + design: `docs/signal-schema-uniformity.spec.md`.
- **Root cause (3 defects):** the five signal-append sites were free-form dict literals with nothing pinning a
  keyset, so two drifted — both **error** branches dropped `signal_type`+`score`, and the **omitted-secret
  summary label** dropped `score` (also `sessionId`/`ts`). The `--json` contract docstring never pinned the
  shape (it documented `scope`, not the emitted `scope_hint`, and omitted `score`), so nothing caught it.
- **Fix at altitude — one constructor, not three spot-patches.** A single `_signal(source, text, *,
  signal_type, score, scope_hint="-", sessionId="", ts="")` is now the ONE funnel every signal goes through;
  `signal_type` + `score` are **required keyword params**, so a future append site physically cannot reintroduce
  the bug. Errors now carry `signal_type="error"` (or `"omitted"` when redacted) + a **named `_NA_SCORE` (0)**
  sentinel — documented in the `--json` contract as N/A (non-human signals are never salience-ranked; they bypass
  `_classify` and are appended unranked, so the sentinel is display-only and `source`/`signal_type` disambiguate
  it from a low-salience human turn). The contract docstring is corrected to the true canonical keyset.
- **Durable pin:** a smoke invariant drives `extract()` over a fixture spanning all three classes (a scored human
  turn · an error `tool_result` · the redacted-secret omitted-summary label) and asserts EVERY signal carries the
  canonical keyset; `_CANONICAL_KEYS` is single-sourced FROM the constructor so the test and the emitted shape
  cannot drift. +5 smoke checks (380 passed, 0 failed).
- **Backward-compatible (PATCH):** purely additive (adds keys to error/label rows) — every existing consumer
  already uses `.get(…, fallback)`, and the change makes the code MATCH the documented `--json` contract (a
  bugfix, not a break). No removed/renamed key, script, or flag; cycle-record schema untouched.
- Gated: independent spec-review (zero blockers — all claims, line numbers, the blast radius, the bypass-`_classify`
  + append-order invariants, and the pre-fix test failure VERIFIED against source; 4 minor gaps folded in) +
  `/code-review`. mypy clean · sim ✓ · `claude plugin validate --strict` ✓ · dream-beta-test gate 0 FAIL.

## [0.1.47] — 2026-06-22

### Added — pin the DREAM-ARC styling (asleep → dreaming → waking) + mandatory HTML auto-open
Two end-of-dream behaviours that only some orchestrators reliably produced — the HTML dashboard auto-opening and a
structured session debrief — are now PINNED in the SKILL, and extended into a whole-pass DREAM ARC (a user-requested
vision): the orchestrator role-plays the consolidation as one dream — fall asleep → dream → wake. SKILL-prose only; the
auto-open already existed in code (`render_html` calls `webbrowser.open()` by default), so what was missing was the
instruction marking it MANDATORY + the debrief format + the arc voice. Full design: `docs/final-phase-debrief.spec.md`.
- **One single-source `### The dream arc` subsection** (after *Rigor modes*) pins the whole arc — opening, intermediate,
  closing, proportionality, the honest limit — so the phases POINT to it instead of restating it. This HARMONIZES the
  four previously-scattered "final message" directives into ONE protocol (a naive addition would have left the SKILL
  self-contradictory): the old absolutist "the output is not free-form prose / the render script is the single source of
  the final report" is REWORDED in place — the dashboard stays the single source of the *data* (don't re-tabulate the
  gauges), the dream now CLOSES with a debrief that *frames* it ("don't duplicate" ≠ "drop the numbers").
- **`render_html … --latest` = the MANDATORY closing action.** A cleanly-completing dream is not done until it runs (its
  auto-open is the post-dream payoff; never `--no-open` in a normal dream). Two carve-outs keep it coherent with the
  existing gates: it runs ONLY on a clean exit-0 `--persist` — NEVER right after an exit-3 procedure-integrity halt
  (which correctly stops to re-verify); and a true Phase-0 no-op never reaches Phase 5, so it has no dashboard / no path.
- **The debrief = pin PRINCIPLES, not a template** (a rigid skeleton makes debriefs go rote): a dream-framed reflective
  voice, visual hierarchy (lead line + bold-headed sections), dense/technical bullets, sparse FUNCTIONAL emojis, FRAMES
  (the non-obvious WHY + what was kept/pruned/verified) rather than duplicates the dashboard, always ends on the 📊 path.
  **Proportional to the OUTCOME BANNER, never the rigor tier** (true-no-op → a one-line stir, no path; no-op/maintenance/
  light → a line or two + path; substantial → the full debrief) — `_outcome()` tops at `SUBSTANTIAL PASS`, there is no
  `HEAVY` banner, so tiering on rigor would re-import the conflation the SKILL guards against.
- **The arc spans the pass:** an OPENING "going-to-sleep" role-play emitted AFTER the first `memory_status.py` read (so
  it's coherent with + scaled to what Phase 0 found) + a LIGHT dream-voice on the INTERMEDIATE phase narration —
  **functional clarity SACROSANCT** (which phase / what command / what result stay plain; when in doubt, function wins).
  **Phase 4 (report-then-apply) stays PLAIN** — fogging the irreversible `CLAUDE.md`-churn approval prompt is the one
  unrecoverable mistake.
- **Backward-compatible (PATCH):** SKILL-prose only — no code change (auto-open already existed), no cycle-record schema
  change (the smoke schema-pin is untouched: NO ` ```json ` fence added before the schema block), no removed/renamed
  script or flag.
- Gated: independent spec-review (2 rounds + a mid-flight scope expansion for the dream-vision → zero inconsistencies) +
  an independent SKILL self-consistency review (7/7 checks PASS: no surviving contradiction, all folded substance
  preserved, banner strings verified against `_outcome()`, generic / no identity leak). smoke 375/0 · mypy clean · sim ✓
  · `claude plugin validate --strict` ✓. Honest limit: an instruction raises the FLOOR (every orchestrator now gets the
  auto-open + a structured, scaled debrief); it cannot fully transfer the judgment that makes a *great* synthesis.

## [0.1.46] — 2026-06-22

### Added — body-defragmentation: curate bloated ACTIVE files (Cycle 2 of the harness-audit follow-up)
Cycle 1 (v0.1.45) archives whole COMPLETED facts (dated pointers → on-demand archive). This handles the orthogonal
case: a long-lived ACTIVE file (a roadmap/status doc) whose BODY has accreted completed/stale items. Measured: 2
bloated active files fleet-wide (the cm roadmap at ≈12.7× its store median; Doc-Flo `next_priorities` at ≈9.1×).
- **`defrag_candidates(fact_files, index_names, *, factor=2.5)` (memory_status.py) — a pure, budget-INDEPENDENT
  helper.** Surfaces INDEXED, non-mirror, NON-dated facts whose `body_tokens` exceeds `factor ×` the MEDIAN over that
  SAME population (self-consistent). Edge guards: returns `[]` on a <3-fact or degenerate (all-equal / non-positive)
  median. RANKS only — the model curates by CONTENT + the user confirms (no write path). DISJOINT from
  `archive_candidates` by the dated-stem gate (dated → pointer-archive; non-dated → body-defrag).
- **Phase 0 surfaces a `defrag? N` stdout advisory** (beside `archive?`; NOT in the cycle record → no schema change).
  **SKILL Phase 5 gains a body-defrag sub-phase** (runs every dream): curate the bloated file's BODY in place (the
  index pointer STAYS) — COLLAPSE detail verifiably redundant with git/CHANGELOG (READ + confirm BEFORE collapsing),
  RELOCATE still-useful-completed detail, KEEP active content + live lessons. **Propose-then-apply IN-CONVERSATION,
  never auto-trim** (the Phase-5 `--diffs` sidecar is the POST-write audit record, not the pre-apply gate). Higher-risk
  (intra-file): keep-on-doubt, relocate-over-delete.
- **Backward-compatible (PATCH):** no cycle-record schema change; no removed/renamed script or flag. +9
  `defrag_candidates` smoke checks (flag/spare/edge guards). Full design: `docs/body-defragmentation.spec.md`.
- Gated: independent spec-review (FAIL→PASS: median population pinned + ratios corrected, the `--diffs`-vs-real-gate
  citation fixed, CHANGELOG-verify operationalized, edge guards, remediation-C overlap documented) + a focused
  adversarial review (no correctness bugs; the relative-median ranking has design-inherent small-population edges —
  the model's content judgment is the net). smoke 375/0 · mypy clean · sim ✓.

## [0.1.45] — 2026-06-22

### Changed — completion-driven archiving + the index budget re-grounded in active-set demand
A harness audit flagged CM's `INDEX_TOKEN_BUDGET` (1200) as ~5× tighter than Claude Code's native always-loaded
truncation (200 lines OR 25 KB ≈ 6400 tok). Deeper measurement FLIPPED the diagnosis: the budget is ~right for the
ACTIVE/lesson-bearing set (real stores measured ~1056–1181 tok, all-active); the permanent over-budget churn was
COMPLETED arcs LINGERING in the index because archiving only fired UNDER budget pressure (the Phase-5 step-0 gate).
The fix decouples archiving from the budget gate. Full design + the empirical record: `docs/completion-driven-archiving.spec.md`.
- **`archive_candidates(fact_files, index_names)` (memory_status.py) — a pure, budget-INDEPENDENT helper.** Surfaces
  INDEXED, non-mirror facts with a dated `_YYYY_MM_DD` stem (the Auto-Dream/CM completed-arc convention), VETOing any
  whose CURATED frontmatter/description signals a live lesson (`_KEEP_RE`). It RANKS only — the model judges by content
  + the user confirms (no relocate path), like `remediation_triage`. Empirically tuned: a whole-body keyword scan
  collapsed recall to ~0 (completed research-docs use "never"/"must" in analysis), so the veto keys on the curated
  description; a dated fact whose lesson-nature is ONLY in its body relies on the model's Phase-5 judgment (documented limit).
- **Phase 0 surfaces an `archive? N` stdout advisory** (detect-and-offer; NOT written to the cycle record → no schema
  change). **SKILL Phase 5 gains a standing completion-driven archive step** that runs EVERY dream, independent of
  budget. **Phase 5 is reframed as an always-on staleness/defrag sweep; the over-budget remediation gate is now a
  BACKSTOP, not the trigger** (it still exists, tested, for genuine active-set overflow).
- **`INDEX_TOKEN_BUDGET` 1200 → 1500** (memory_status.py + render_html.py) — grounded in the measured active-set demand
  + ~25% growth headroom, NOT a fraction of native's 25 KB hard-truncation ceiling (the failure limit, not a target).
  `CLAUDE_MD_TOKEN_BUDGET` (4000 ≈ native's <200-line CLAUDE.md guidance) and `PRUNE_PRESSURE_FACTS` (40) unchanged.
- **Backward-compatible (PATCH):** no cycle-record schema change (legacy records carry their own `budget_tokens` and
  render unchanged); no removed/renamed script or flag. Tests: +8 `archive_candidates` smoke checks, the Probe-L
  over-budget fixture resized for 1500, the `_evict_frees_enough` test pinned to an explicit budget (decoupled from the moved constant).
- **Deferred on evidence:** an always-on DEEP re-verification rotation (+ a fleet-wide `last_verified` schema migration)
  was gated behind a staleness-rate probe → ~10 % SUBSTANTIVE drift over month-old facts (mostly recoverable
  file-relocation), too low to justify the schema cost. Body-defragmentation of bloated active files is the next cycle.

## [0.1.44] — 2026-06-22

### Added — procedure-integrity detector: the lazy-skip safeguard (the structural anti-rush forcing function)
The MEASURED failure (2026-06-22; full design `docs/dream-procedure-integrity.spec.md`): three consecutive dreams ran
**0/0/0 verification** while self-labeled SUBSTANTIAL/HEAVY — the orchestrator skipped the Phase-3 verification fan-out
and graded its own (skipped) effort. `rigor.applied` is self-reported (catches over-rigor, NOT under-rigor), so only a
human's eye caught it. This adds a DETECTOR at the one mandatory boundary a finishing dream always reaches: the terminal
`render_dashboard --persist`.
- **`procedure_integrity(record)` (memory_status.py) — a pure predicate.** FIRES iff
  `suggested_tier(git_commits, session_candidates) >= SUBSTANTIAL` **and** the verification tally
  (confirmed+corrected+unverifiable) `<= 0`. NON-CIRCULAR: it rests on script-SEEDED `git_commits` (a lazy-skip never
  touches it), NOT on the audited self-report (`rigor.applied`) and NOT on `mutation_ops` (a skipped Phase 5 also skips
  `--audit`, so that data may not exist — MEASURED: 11 mutation-log entries for 13 dreams, none of the 3 failures
  carrying an audit block). `applied` + audit op-count are corroboration/severity only. Legacy/non-conformant records
  (no `scope`/`verification`) NO-OP — never retroactively flagged; non-finite/junk values coerce to 0 (never raises).
- **The teeth (render_dashboard.py).** At `--persist` (the SKILL's terminal Phase-5 step) the render prints a loud
  **PROCEDURE INTEGRITY ⚠** panel, persists the firing record (so it's logged + archived), then **exits 3** — strict
  order print→persist→exit. GATED on `--persist`: a seed/preview render (0 candidates, 0/0/0 by construction) is the
  dream's BEFORE state and is never judged.
- **Archive (render_html.py + dashboard.template.html).** Each logged cycle carries an escaped `_integrity` verdict; the
  HTML flags it on the single-cycle banner + verification block + the archive-index row (the 3 historical failures now
  visibly marked in the longitudinal view).
- **Honest scope.** A DETECTOR at the mandatory boundary, NOT enforcement of phase invocation (nothing can make a
  stateless script force an LLM to run a phase). It catches the *lazy-skip* (0/0/0 on a substantial pass), NOT a diligent
  liar who types fake tallies.
GATED build (gated-spec-driven-change): an independent 3-lens spec review + advisor pressure-test + a fresh re-gate (all
FAIL→PASS), then an adversarial diff review (1 blocker — a non-finite-float crash in the coercion — FIXED, pinned, and
repro-verified). EMPIRICALLY VALIDATED: the predicate separates the 13 live records cleanly — fires on EXACTLY the 3
rushed passes (incl. the 11-commit/0-candidate one a candidate-only gate would miss), spares all 10 legit (every one
recorded tally>0, incl. the corrected 19/2/2 dream). **NO cycle-record-contract change** (reads existing
`scope`+`verification`; verdict derived, not stored) → the smoke pin is untouched. smoke 358/0 (+23 units: the 13-record
regression + the --persist-gate / seed-spared / legacy-no-op / NaN-safe / negative-tally pins) · mypy 16 · sim ✓ · blast
radius MEASURED (cm/tests/beta-tester all spared). **PATCH** (additive; legacy records still render; exit-3 fires only on
the failure condition, never on a legit/legacy/seed render).

## [0.1.43] — 2026-06-22

### Fixed — session-id discovery: window-aware extract_signals + originSessionId producer (pre-1.0 audit blocker #2)
Discovery read only the NEWEST-mtime transcript, not all sessions in the marker..HEAD window — so a fresh session
opened JUST to run dream HID the prior heavy session's intent (the killer case the on-disk read was meant to
defend). And originSessionId was validated/consumed but NEVER produced.
- **A — window-aware `extract_signals` (Phase-2-internal):** `_latest_transcript` → `_window_transcripts` — pool
  ALL `*.jsonl` in the window (mtime-prune only definitely-stale files; the per-line `since` does the exact
  scoping) through the SAME single per-line path, emitting each candidate's `sessionId` (mtime-prune TZ-corrected per
  Gate-2: Z-normalized + naive-marker-as-UTC, so it never wrongly drops a prior in-window session). **SECRETS FIREWALL
  preserved (the ship-gate):** one per-line scrub path fed from the pooled files — NO second read path; a smoke
  case pins the scrub across >1 pooled file (secret value absent). Pooled dedup; `max_n` caps the pooled set.
  CONTRACT change (internal-only consumer): `--json` `transcript` (single) → `transcripts` (list). ZERO
  SKILL-command change.
- **C — `originSessionId` producer:** the fact-write template (harness-map + SKILL Phase 4) now stamps it from the
  signal's `sessionId` (the MOTIVATING session — may be a PRIOR one), omitted for git-derived project facts —
  closing the producer gap the old "CC-INJECTED" wording wrongly presumed existed.
Bounded (git log already covers project facts; the loss was prior-session feedback/prefs — the durable
user-global slice). smoke 333/0 (incl. firewall + multi-session + mtime-prune units) · mypy 16. Meta-req HELD
(Phase-2-internal, no new command/manual step). **PATCH** (internal contract; no external consumer).

## [0.1.42] — 2026-06-22

### Added — cold-start bootstrap: the dream is NETWORK-AWARE on an empty store (pre-1.0 audit blocker #1)
The cold-start audit found a real gap — the HYBRID path: a fresh/dormant repo in an established fleet (EMPTY local
store + ~0 commits + a RICH cross-project network) hit the network-BLIND no-op STOP and exited before Phase 1,
never discovering the fleet's relevant facts. SKILL-only fix (the no-op STOP is a SKILL instruction, not
script-enforced; `global_store_facts` is already seeded; `--list` already does the `is_relevant` filter):
- **B3 — network-aware no-op rule:** STOP only when the local store is EMPTY *and* the network is empty
  (`cross_project.global_store_facts == 0`). An empty-store-but-rich-network repo PROCEEDS to a COLD-START
  BOOTSTRAP (Phase 1 `--list`→`--pull`, M1-bounded; Phase 5 health) — generalizing the v0.1.37 MAINTENANCE-pivot.
  Scoped to pull+health ONLY (no Phase-2/4 authoring — the genuine from-scratch case stays a STOP; never
  force-seeds). Graceful degradation: `--list` 0-relevant → honest no-op ("network checked · 0 relevant").
- **B1 — `--list` before `--pull`:** surface relevant/present/missing/held BEFORE the pull writes — legible
  enrichment, not a blind pull. Read-only, no code.
NARROWED by the audit verdict: a cloned-history repo has commits>0 → already bootstraps (first-consolidation), so
the gap is the empty-history/dormant repo only. Rejected B4 (selective-pull flag) + B5 (cold `--evict`) as
bolt-on/wrong-tool. SKILL-only · no schema change · meta-requirement HELD (hooks Phase 0→1, no new command). **PATCH.**

## [dream-beta-tester 0.1.6] — 2026-06-22

### Fixed — install-gate updates a STALE DBT-owned pre-push hook instead of refusing
The hook installer refused to overwrite ANY existing `pre-push`, so when the gate's stable location/slug moved,
a re-run left the OLD hook in place — it exec'd a frozen `~/.claude/dream-beta-tester/ci_check.sh` (old-slug
`beta_checks`) that FALSE-FAILED the M3 split-brain `CHK-QTY` on the `.`-bearing path, blocking a verified-clean
push (the cm v0.1.41 evict ship). Now install-gate detects a dream-beta-test-OWNED hook (by marker) and UPDATES
it to the cache-latest resolver (which survives plugin updates); a non-DBT hook is still never clobbered.

## [0.1.41] — 2026-06-22

### Added — evict-to-receive: the release valve for M1's hold (the budget ↔ cross-pollination tension)
M1 (v0.1.38) holds a new global on an over/near-budget store + surfaces the lever, but a chronically-full store
then HOLDS forever (the audit's "starves until it prunes" tension; Doc_Flo holds 5). `sync_global --pull
--evict=FACT` is the release valve: free ONE low-value local pointer so a held global can land — NET-NEUTRAL (a
swap, not a grow, so M1's budget stays enforced). It COMPLETES M1 (guard ↔ valve), doesn't compete with it.
- **Safe operator scalpel, report-then-apply (NEVER auto-eviction):** a plain `--pull` with anything held surfaces
  the held + the evictable pointers with RAW, UNORDERED metadata (scope · mirror? · cost) — explicitly NOT ranked
  (a staleness/mtime rank misleads: a foundational fact is untouched yet vital). The agent judges; `--evict`
  applies. Pre-checks BEFORE any delete (Guard-3 no-partial-state): the fact exists, has NO inbound `[[links]]`
  (`_inbound_links` — orphan-safety), held globals exist to receive, and the freed room FITS the smallest held
  (`_evict_frees_enough` — never delete for nothing).
- Factored `extract_wikilinks` — the SINGLE `[[...]]` extractor (`dangling_links` + the evict inbound-scan both
  call it; no 4th wikilink regex, per the v0.1.40 reimplementation-pin lesson).
- Gate-2 hardening (2 independent reviewers; core destructive guarantees confirmed sound): `--evict` now honors
  `--allow-net-grow` in its held pre-check (no gratuitous evict when the override makes nothing held); the
  surfacing read is OSError-safe (matches every other store scan); `--evict` requires `--pull` and rejects an
  empty `--evict=` at parse (a destructive flag never silently no-ops). install-gate hook-update is runtime-
  verified (the recurrence-guard fired on the real stale hook); a bash test for it is a noted gap.
- Verified: hermetic CLI E2E (happy · inbound-orphan refusal · too-small-fit refusal · the surfacing) + 6 smoke
  units on the pure guards. smoke 328/0 · mypy 16 · sim A–Q. **PATCH** (additive `--evict`; `--pull` unchanged).
- Deferred (separate, pre-existing): a pulled global linking a HELD global dangles (the dangling-detector is
  local-only) — not eviction-specific. This valve is a scalpel, NOT a cure: it does not auto-rank or "solve" the tension.

## [0.1.40] — 2026-06-22

### Fixed — M3: `slug_for` generalizes to all non-alphanumerics, fixing the dot-segment split-brain (audit MAJOR)
`slug_for` (memory_status) + `near_duplicate_slugs` + the dream-beta-tester's **four** slug reimplementations
(snapshot, beta_checks, render_beta_report, make_fixture) now map `[^A-Za-z0-9]` → `-` (was `[/_]`), matching
Claude Code's verified rule (`.claude` → `--claude`). A dot-segment project path (a dotfile dir like `~/.config`)
previously got a SPLIT-BRAIN store — two stores, neither recalling the other. Fleet slugs UNCHANGED (paths with
only `/ _ -`); +3 smoke units (dot→dash · fleet-identical · near-dup twin caught). **dbt 0.1.4 → 0.1.5.**
- BREAKING for a dot-segment project (re-slugs its store) — but no real fleet project is dot-segment (verified;
  only the harness's own gate fixtures are dot-path), so the blast radius is the test harness, re-pinned below.
- **Shipped as a MAINTAINER MIGRATION, not a routine gated release:** the pre-push gate's cache dbt + frozen
  v0.1.19 canary are old-slug, so they FALSE-FAIL a new-slug skill (CHK-QTY — the skill reads the new-slug store
  while the old-slug oracle reads the fixture → mismatch). PROVEN no real regression by running the gate at
  CONSISTENT new-slug (repo dbt + repo skill + fresh fixture): **oracle 0 FAIL · 16 PASS · CLEAN**. So the
  cache-dbt FAIL is a known false-positive → pushed `--no-verify`; `install-gate.sh` re-run post-merge re-pins
  fixture + canary at the new slug. smoke 321/0 · mypy 15.

## [dream-beta-tester 0.1.4] — 2026-06-22

### Fixed — M5: dream-beta-tester `restore()` no longer destroys data (audit MAJOR; dbt-only, cm UNCHANGED)
The harness's `restore()` (default `--test`) could DELETE a live store file: it unlinked any live store file
absent from the snapshot, AND capture SKIPPED unreadable files — so a present-but-unreadable PRE-RUN file was
deterministically deleted (constructible, no race; the concurrent-writer variant — another session's fact added
in the snapshot→restore window — was also exposed).
- **Fix (advisor-vetted): QUARANTINE, not delete.** `restore()` now MOVES an extra live file to a
  `reports/.restore-trash-<ts>/` dir instead of `unlink()` — a wrong roll-out is recoverable, and `--test`'s
  leave-no-trace still holds (the store reaches BEFORE exactly; the extra is out, in the harness's own area).
  Capture now RECORDS an unreadable file (`sha256=None`, no copy) so `restore()` PRESERVES it (never deleted,
  never overwritten). Quarantine subsumes the audit's gate/refuse/dry-run-default brainstorm — it removes the
  need to distinguish dream-added from concurrent/unreadable at all.
- Verified by a hermetic E2E (unreadable preserved · extra quarantined-not-destroyed · dream-add rolled out) +
  4 smoke units. smoke 318/0 · mypy 15. **dbt 0.1.3 → 0.1.4** (manual bump; `release.sh` releases cm only). The
  consolidate-memory scripts are UNCHANGED — this sails the cache gate (no slug/skill change).

## [0.1.39] — 2026-06-22

### Fixed — M2 + M4: two `promote()` pre-write guards (audit MAJORs)
- **M2 — `promote()` reconcile silently DISCARDED a re-framed local fact (data loss).** On reconcile (the canonical
  exists), `promote()` rewrites the origin as a mirror of the EXISTING canonical body — so a local carrying NEW
  re-framed content was destroyed with no trace, reported as benign success. A content-divergence guard (pure
  `_bodies_match()` — frontmatter-stripped via a leading-block-only regex so a body's own `---`/`***` rules
  survive, whitespace-normalized, strict) now REFUSES the reconcile when the local body differs ("merge into the
  canonical first") — or `--prefer-canonical` keeps the canonical + drops the local body (the genuine dedup intent,
  mirroring M1's `--allow-net-grow`). Covers BOTH sub-cases (rename + same-name).
- **M4 — `promote()` Guard-2 let an undetectable-stacks fact write a fleet-DEAD canonical.** A stack-general fact
  whose `stacks:` are non-empty but outside `detect_stacks`'s closed vocabulary (a typo, or a real-but-undetectable
  stack like `release`/`ci-cd`) wrote a canonical `is_relevant` matches for NO project. Guard-2 now validates
  `stacks ⊆ _DETECTABLE_STACKS` (block), beside the existing empty-set check.
- Both are pre-write guards (Guard-3's no-partial-state rule) in one `promote()` cycle. Verified by a hermetic E2E
  (M2 refuse + `--prefer-canonical` escape + M4 refuse + a detectable-stack negative control) + 5 smoke units on the
  pure helpers. Process: the audit is the spec → implement → Gate-2. smoke 313/0 · mypy 15 · manifests. **PATCH**
  (additive `--prefer-canonical` flag + `prefer_canonical` param; the guards refuse only what was already broken —
  data-loss / fleet-dead writes — valid promotes unaffected).

## [0.1.38] — 2026-06-22

### Fixed — M1: the over-budget net-grow guard (completes the v0.1.37 self-heal pivot; audit BLOCKER)
The adversarial cross-project audit found v0.1.37's `--refresh-only` guard **incomplete**: it was keyed on
`over_budget_not_justified` (= `remediation.required`), which **standing-justify SUPPRESSES** — so the most-over
stores (Doc_Flo, 230% over + standing-justified) were cued a PLAIN `--pull` that silently net-grew the gated
index (violating the tool's own v0.1.18 no-net-grow invariant), and the guard ran only on the no-op pivot, never
the normal Phase-1 `--pull`.
- **Fix (advisor-vetted): move the DECISION into `sync_global`** (the only place that knows the per-pull cost).
  `--pull` now AUTO-HOLDS a MISSING new-global pull that would *leave* the always-loaded index over
  `INDEX_TOKEN_BUDGET` (projected: `running_idx + the pointer's own cost`) — so it can't net-grow an over- OR
  **near**-budget index (the near-budget overshoot a model-read cue can't catch — the exact bug that bit
  consolidate-memory itself: 1153→1224). STALE mirror refreshes always run (bounded hook-delta).
- **The held-count is the LOUD lever:** `sync_global` reports `held N`, and the dashboard's CROSS-PROJECT section
  surfaces `⚠ held N — prune/justify to receive`. The most-relevant store *starves* until it prunes under budget
  (the audit's deepest tension) — now visible, not silent. Eviction (pull + evict a lower-value pointer) is post-1.0.
- Replaces the v0.1.37 `--refresh-only` with the always-on auto-hold + `--allow-net-grow` (the escape hatch).
  `sync_global._would_net_grow()` is the pure single-source guard; smoke pins cases 1/2/boundary/override + the
  held render. `cross_project.held` added to the cycle record (additive, `total=False`) + the nested SKILL↔TypedDict pin.
- Process: the audit served as M1's independent spec (Gate-1-equivalent); implement → Gate-2. +6 smoke units,
  smoke 308/0 · mypy 15 files · manifests. **PATCH** (additive cycle-record; the removed `--refresh-only` is
  gracefully ignored + superseded by the auto-hold — no install breaks).

## [0.1.37] — 2026-06-21

### Added — the no-op SELF-HEAL pivot: a no-op dream no longer exits with "nothing to do, bye"
A magnitude-0 dream (0 new commits) on a NON-EMPTY store is no longer a no-op — it is a **MAINTENANCE pass**:
the store may carry health debt (dangling links, stale records) and the cross-project tier may hold new
sibling-promoted facts to pull. The Phase-0 stop now fires ONLY for an EMPTY store; a non-empty store PIVOTS
into Phase 1 (`--pull` cross-node enrichment) + Phase 5 (health: dangling-fix / prune-or-justify),
report-then-apply. (Found by dogfooding: Doc_Flo carried 6 dangling links + a stale store a no-op kept skipping.)
- **Signal-driven, not prose** — `memory_status` emits a `maintenance` block (`dangling`,
  `over_budget_not_justified` = the dual-axis suppression result, `work`) + a Phase-0 PROCEED cue, so the pivot
  is cued by DATA (missing prose was the bug).
- **Read-only by default** (the safety posture) — `--pull` is proposed, and a new `sync_global --pull
  --refresh-only` mode refreshes stale mirrors but HOLDS BACK missing new globals (no index net-grow), the
  enforced gate the pivot uses when the index is over-budget-not-justified (honors the v0.1.18 no-net-grow
  invariant — enforced, not model discretion).
- **Single-source dangling** — a new `memory_status.dangling_links()` helper; Phase-0 maintenance, the Phase-5
  health fill, and the smoke test all call it, so the dangling count can't drift.
- **MAINTENANCE PASS banner** — `render_dashboard._outcome()` no longer renders a pivoted self-heal pass as the
  misleading NOTHING/NO-OP.
- **dream-beta-tester 0.1.3** — new `maintenance_pivot_coherence` family: a store with maintenance work MUST
  surface the Phase-0 pivot cue (the regression guard for the signal foundation).
- Gated: empirics → spec → Gate-1 independent review-to-zero (3 blockers folded — read-only pivot,
  steady-state trigger [dropped the perpetual-nag `stale_since_marker`], banner mechanism) → impl → Gate-2
  (`/code-review`, max effort). An impl-time empirical discovery (a live sibling-promoted global a no-op would
  miss) refined the PROCEED cue to fire on `commits==0` + non-empty, not just local work. **Gate-2 caught a real
  bug** — a held-back MISSING fact under `--refresh-only` still wrote PHANTOM provenance to the shared global
  canonical (`_record_provenance` fired on `status=="MISSING"`); fixed to exclude the held case — plus 6
  hardening fixes (the Phase-0 cue now emits the gated `--pull --refresh-only` command itself; `dangling_links`
  strips fenced code blocks too; `maintenance` added to the nested SKILL↔TypedDict pin + `validate_cycle_record`;
  the beta family reuses the captured render). +4 smoke units. smoke 302/0 · mypy 15 files · manifests. PATCH
  (additive; read-only pivot → no contract break).

## [0.1.36] — 2026-06-21

### Fixed (defensive hardening) — the remediation block gates on `required`, not mere presence
`render_dashboard` rendered the over-budget `REMEDIATION` block whenever a `remediation` object was present,
regardless of its `required` flag (`elif rem:`). A record carrying `remediation: {required: false}` — the
cycle-record schema's own DEFAULT — therefore rendered a spurious "over-budget gate" on a store that is UNDER
budget (a self-contradiction, the same class as the v0.1.35 `acted=pruned` bug, one branch up). Fix:
`elif rem and rem.get("required")`. **Not a live-dream regression** — a healthy dream's seed OMITS remediation
entirely (measured), and the over-budget triage sets `required: true` (so the safety gate still fires); the gap
was reachable only by a record following the schema default or a non-omitting producer. Found by dogfooding the
v0.1.35 dream.
- +2 regression smoke units (required=false → no block; required=true → block preserved).
- **dream-beta-tester 0.1.2:** new `remediation_render_coherence` family guarding BOTH renderer fixes (v0.1.35
  rebuild-lean-resolved, v0.1.36 required=false) AND the seed→renderer SAFETY contract — a real over-budget,
  non-justified store MUST seed `required: true`, else the v0.1.36 renderer would silently drop the gate.
  Verified: PASS on the fixed renderer, FAIL on the buggy cache 0.1.35, seed-contract FAILs a gate-dropping seed.
- **mypy.ini now covers `plugins/dream-beta-tester/scripts`** — a latent v0.1.35 `tgt`-type drift slipped
  because dbt was uncovered; now caught. smoke 298/0 · mypy · manifests. PATCH.

## [0.1.35] — 2026-06-21

### Fixed — remediation gate mislabeled "not acted on" after a rebuild-lean (beta-test-confirmed)
`render_dashboard` reported an over-budget remediation gate **resolved by a rebuild-lean** (re-indexing MEMORY.md
leaner — `pruned=0` but `achieved_index ≤ budget`) as `⚠ gate fired but not acted on — surface candidates +
prune-or-justify`, **while the always-loaded gauge showed the index UNDER budget** — a self-contradicting dashboard
that could prompt needless fact-eviction. Root cause: `render_dashboard.py`'s `acted = pruned` derived "acted on"
from facts-evicted ONLY, ignoring `achieved_index`; but the skill SANCTIONS rebuild-lean as a remediation action
(Phase 5 step 0: "prune … and/or rebuild the index lean"). Fix: `acted = pruned or (rebuild-lean brought the index
≤ budget)`, with a clear `✓ gate resolved by rebuild-lean — index back under budget, no eviction needed` note
replacing the false warning. A gate genuinely still over budget (or unacted) still warns correctly.
- Surfaced by the **dream-beta-tester**'s Coherence judgment lens — the deterministic oracle could not reach it
  (an under-budget store renders no remediation block) — and hit LIVE in this repo's own v0.1.34 dream.
- +2 regression smoke units (rebuild-lean-resolved → resolved; still-over → warns). smoke 296/0 · mypy · manifests. PATCH.

## [0.1.34] — 2026-06-21

### Added — `cm log`: the lean log-audit view (the 3rd renderer of the cycle log)
A dense, one-row-per-dream table over `<store>/.consolidation-log.jsonl` — audit any project's dream history
without hand-parsing JSONL or opening a browser. **One log, THREE views** now: ASCII dashboard (`render_dashboard`,
ONE cycle) · HTML archive (`render_html`, all cycles, rich) · **LOG (`render_log`, all cycles, lean-tabular)**.
- **`cm log [DIR] [-n N] [--json]`** — DIR defaults to CWD; fleet-reachable via the PATH-installed `cm` (v0.1.33).
  Columns: WHEN · MARKER · RIGOR · INDEX (Δ) · RECALL (Δ) · ENTRIES (by-action code) · AUDIT (+created ~modified
  -deleted). `--json` emits the last N raw cycle records (pipe to jq / any programmatic audit — the real "plug in").
- **New plugin renderer `scripts/render_log.py`** (stdlib, zero-dep) — **ships with the plugin/marketplace**;
  reuses the SAME `read_history` + `_store_for` (render_html) that `cm report` uses (so they agree on the store) +
  the `_ui` vocabulary. `-n` caps AFTER the newest-first sort. Legacy/sparse + empty-log + malformed-line safe.

### Internal
- `cm log` dispatch (dir-first; `-n`/`--json` pass through) + help; CLAUDE.md layout now lists all three renderers.
  +3 smoke units (table build, legacy-`{}`-safe, `read_history`-reuse). smoke 294/0 · mypy (10 files) · manifests. PATCH.

## [0.1.33] — 2026-06-21

### Fixed — the post-dream re-open instruction was wrong for plugin users
The SKILL told users to "re-open with `cm report`" — but `cm` is the **maintainer dev CLI**: it lives only in the
consolidate-memory repo, isn't on a plugin user's PATH, and CWD-defaults. So a plugin user in another repo (e.g.
job-applicator) has no `cm`, and running it from the consolidate-memory repo opens the WRONG repo's archive. The
dashboards were always correctly **isolated per-repo** (each `~/.claude/projects/<slug>/dashboards/index.html`
embeds only its own dreams — verified by parsing the embedded data); the defect was purely the instruction.
- Phase 5 now points end-users at the **self-contained file at the stable per-repo path** — that file IS the
  fleet-wide re-open (works from any repo) — and explicitly flags `cm report` as maintainer-only.
- `cm`'s own `--help` now notes it defaults to the CWD repo (pass another repo's path to view it) and that end
  users just open the `dashboards/index.html` file.

A convenient fleet-wide re-open command + the `cm log` audit dump remain **separate, deliberate features** (not
smuggled into this correctness fix).

### Internal
- SKILL Phase-5 re-open prose + `cm` help text only. No code/schema/flag change. smoke 291/0 · mypy · manifests. PATCH.

## [0.1.32] — 2026-06-21

### Added — diff-modal (interactivity cycle 2): click a changed memory fact → its before/after diff
The dream view now shows the **memory files changed that pass** as clickable chips (§04) → a **modal** rendering the
before/after **diff**. The diff data lives in a **persistent per-dream sidecar**
(`dashboards/diffs/<commit>__<timestamp>.json`), NOT in the cycle-record contract — revisitable from the archive,
no schema change.
- **Capture** (`memory_status.py --diffs <cycle> --before <snapshot>`, Phase 5 after `--persist`): extends the
  Phase-0 snapshot to stash before-content for the **memory store only** (the `MEMORY.md` index excluded — pointer
  churn, not a fact), then `difflib` per changed fact; one-sided create/delete handled; per-file line cap with
  "+N more". Best-effort (never crashes a dream). The snapshot + sidecar are `chmod 600` (they now hold fact bodies).
- **Embed**: `render_html` reads each embedded cycle's sidecar (keyed by the shared `diff_key`) into the
  self-contained HTML — offline, no fetch.
- **Modal**: +/- /hunk-colored diff; Esc / × / backdrop close. Every line through `esc()` — the load-bearing XSS
  guard on the first feature to render raw fact *bodies* (hostile-fixture verified inert).

### Internal
- New `--diffs` step + `capture_diffs`/`diff_key`/`_diff_lines`/`diffs_dir` (memory_status), `read_diffs` +
  `build_html(…, diffs)` (render_html, kept PURE), the modal (dashboard.template.html). +4 smoke units; data layer +
  modal JS-probe-verified (scoped/capped/one-sided; key sanitized; embed `</script>`-safe; modal opens/closes;
  hostile body inert). Gate-1 spec-review folded (1 HIGH clickable-surface → drive off the sidecar; safety/ordering/
  keying MEDs); independent Gate-2 re-audit. smoke 291/0 · mypy · manifests. PATCH (diff data OUTSIDE the contract).

## [0.1.31] — 2026-06-21

### Added — dashboard interactivity (cycle 1 of the interactivity arc; client-side, READ-ONLY)
Three intuitive interactions on the dashboard + archive — all pure client-side transforms of the already-embedded
data (no new data, no schema, no contract change — safe by construction, the user's "doesn't break anything
logically"):
- **Click-through + keyboard nav** — click any trajectory point, rigor dot, or archive row to open that dream;
  ← → step prev/next, Esc → archive (ignored while typing in a filter).
- **Archive filter & sort** — filter the dream ledger by rigor + sort by date / index tokens / writes (re-renders
  the LIST only; the embedded dreams stay the source of truth).
- **Focus & density** — collapse/expand any dashboard section + a compact/cozy density toggle, both persisted in
  localStorage.

### Internal
- All interactions live in dashboard.template.html (vanilla JS, zero-dep); navigation stays reload-with-param.
  +1 smoke unit; each interaction JS-probe-verified (rigor filter 7→6, sort ascending, click-through 21 points,
  keyboard #sel step, collapse + density toggles). smoke 287/0 · mypy · manifests. PATCH (additive, read-only).
  The diff-modal (persistent sidecar) is cycle 2.

## [0.1.30] — 2026-06-21

### Changed
- Dashboard KPI band ("numerical dash"): dropped the bottom hairline rule (top rule only) so the key indicators
  read as floating below the rule — a cleaner, un-boxed feel (review polish, completing v0.1.29's removal of the
  vertical cell-dividers + the centered network legend + the full-width Changes reason text). Pure CSS, no logic
  change.

### Internal
- **Versioning — PATCH:** a one-line cosmetic CSS change in dashboard.template.html. smoke 286/0 · mypy · manifests.

## [0.1.29] — 2026-06-21

### Added — per-repo dream ARCHIVE (browse + revisit every dashboard)
The HTML dashboard becomes a per-repo mini-site: ONE self-contained, zero-dep file embedding ALL logged cycles,
with two branded views sharing the v0.1.28 design system.
- **Archive index** — a per-repo ledger of every dream (when · outcome · rigor · index tokens · writes · commit),
  newest first, each row a link to that dream's dashboard.
- **Dream dashboard** — the full v0.1.28 telemetry for any selected dream, rendered as-of that pass (the repo
  identity is explicit in both views).
- **Navigation** — reload-with-param (`#sel=<i>`): a dream row, prev/next, or "← Archive" is a fresh load on the
  one tested render path (no in-place re-render). Keyed on `marker.timestamp` (unique); the commit hash is a
  display value + the `cm report <hash>` commit-prefix filter (latest on collision).
- **Stored + revisitable** — written to a stable `~/.claude/projects/<slug>/dashboards/index.html` (the dream and
  `cm report` write the SAME file). `cm report [DIR]` → the archive; `cm report <hash>` → a dream; Phase 5
  `--latest` → the just-completed dream's dashboard.

### Internal
- render_html: `assemble_cycles` (dedup-by-marker series builder, capped at the latest 120 with a visible note),
  `--select`/`--latest`, unified `_default_out`. Template: `#sel` routing + `showArchive`/`showDreamNav` +
  hashchange-reload + boot-once. +4 smoke units; the navigation JS-probe verified (`#sel=k` renders cycle k, not
  the latest). smoke 285/0 · mypy · manifests. PATCH (additive: new views/args + a per-repo `dashboards/` output).

## [0.1.28] — 2026-06-21

### Added — rich HTML observability dashboard ("dream telemetry")
A gorgeous, ZERO-dependency, self-contained HTML dashboard — the visual sibling of the ASCII report (one
cycle-record contract, two renderers). `render_html.py` (stdlib) injects the data inline (XSS / `</script>` /
attribute-quote-safe) into a BUNDLED template and auto-opens it via `webbrowser` (headless-safe — prints the
path if no browser). Offline + works out-of-the-box from the marketplace install.
- **Renders** the current cycle — **repo identity**, budget meters (index / CLAUDE.md), rigor, verification +
  health, the script-observed audit trail, the cross-project "shared-consciousness" network — AND longitudinal
  trends from `.consolidation-log`: the **index-budget trajectory** toward the ceiling with a least-squares
  projected-breach early-warning, recall-fact growth, per-cycle churn, and the rigor tier + dream cadence.
- **Editorial "field report" aesthetic**: warm light + warm-dark themes, auto-detected via `prefers-color-scheme`
  + a manual auto/light/dark toggle; refined serif/mono pairing; precise round-axis ink-on-paper hand-rolled SVG
  charts; one restrained accent.
- **Integration**: Phase 5 generates it after the ASCII render (auto-opens — the post-dream payoff);
  **`cm report [DIR]`** re-opens a project's latest. Coherent with the ASCII renderer (same record; key numbers
  asserted equal in smoke).

### Internal
- `render_html.py` + bundled `dashboard.template.html` (found via `__file__` → marketplace-cache-safe). +9 smoke
  units (coherence round-trip, XSS `</script>` + attribute-quote escaping, zero-external-deps, bundling,
  legacy/sparse render, malformed-log robustness, `_store_for`). smoke 282/0 · mypy · manifests. Independent
  re-audit (1 MED attribute-XSS found + fixed). Charts: least-squares budget slope, breach marker on the exact
  fractional crossing, round-number axes, canonical `CYCLES` series so all longitudinal charts agree; visual
  verified via browser screenshots + coordinate-free DOM probes.
- **Versioning — PATCH**: additive (new renderer + bundled template + `cm report` + SKILL Phase-5 hookup; no
  cycle-record schema change, no removed flag, no install break). The per-repo dream **archive** mini-site
  (browse history + `cm report <hash>`) is the next cycle (v0.1.29).

## [0.1.27] — 2026-06-21

### Added (SKILL doc — the archive-relocation remediation discipline; from the network audit)
The cross-project network audit found the dream ALREADY relocates completed/merged arcs out of the always-loaded
`MEMORY.md` index into an on-demand archive (`SHIPPED.md`) **by judgment** — Doc_Flo's `SHIPPED.md` cites the
v0.1.18 remediation, 57 facts archived — but the SKILL never documented it (the model improvised it correctly).
The deferred **mechanical "archive lever" (finding-B) is off the table**: the budget tier already exists (the
archive is off `INDEX_TOKEN_BUDGET`, on-demand) and judgment does the keep/archive split well; a mechanical lever
would automate a working process and add a silent recall-erosion risk. This codifies the proven discipline so
future dreams apply it consistently + safely.
- **Phase-5 remediation runbook gains an `archive` option** (PREFERRED, non-destructive — applied before
  prune/justify): relocate completed-arc pointers `MEMORY.md`→an on-demand archive index, keeping the fact body
  (recallable) and keeping lesson-bearing / NEGATIVE / active-state / directive pointers live **even if
  dated/"SHIPPED"**. The keep-vs-archive call is judgment with a SILENT failure mode (archive a live lesson →
  recall lost; the recall-tier analogue of CLAUDE.md enforcement-erosion) → conservative, propose-only,
  archive-then-justify the earned residual.
- NOT a routed `lever` (the script still routes prune/gc/justify) — a model disposition; **no code/schema change.**

### Internal
- SKILL.md prose only (Phase-5 remediation runbook). smoke 274/0 · mypy · manifests (json-pin unaffected — no
  schema change).
- **Versioning — PATCH:** additive SKILL guidance; no code, no schema, no lever-routing change.

## [0.1.26] — 2026-06-21

### Fixed (provenance-churn staleness — ROOT-fix; surfaced by the cross-project network audit)
The network audit found widespread "stale" mirrors after pulls. Root cause: the canonical `projects:`
provenance list was copied INTO every mirror, and it grows every time *any* project pulls a fact — so each
pull marked *all other* projects' mirrors stale, though the fact content was identical (perpetual cross-fleet
refresh churn + misleading "everything stale" dashboards; functionally harmless — recall content was always
correct).
- **`_as_mirror` no longer carries `projects:` into a mirror** (root-fix, not a comparison hack): provenance is
  CANONICAL-only bookkeeping — the synapse record `network()`/`_holders` read off the global store; nothing
  reads a mirror's provenance (verified across all scripts). A mirror now stays in-sync regardless of canonical
  holder-list growth. Frontmatter-scoped so a prose body line is never touched; the `_is_mirror(_as_mirror(…))`
  round-trip invariant holds.
- **One-time migration:** existing mirrors refresh once (provenance-stripped) on their next `--pull`/dream, then
  stay in-sync. Verified live: after the one-time refresh, a repeated `--pull` shows **0 refreshed** (churn gone).

### Internal
- `_as_mirror` frontmatter-scoped `projects:` strip + 1 smoke unit (strips FM `projects:`, preserves a body
  `projects:` prose line, round-trip + frontmatter validity hold). smoke 274/0 · sim · mypy · manifests.
- **Versioning — PATCH:** a behavioral fix to mirror content (mirrors drop canonical-only bookkeeping; the
  canonical's provenance is untouched; no cycle-record schema change, no removed flag; legacy mirrors self-migrate
  on the next pull).

## [0.1.25] — 2026-06-21

### Fixed (cross-project wikilink integrity — surfaced by a job-applicator dream pass; additive → patch)
A job-applicator dream flagged 3 dangling wikilinks inside *pulled mirrors* — all `[[wikilinks]]` in
global/stack-general canonicals pointing to **project-local facts of their origin project** (e.g.
`user-fleet-is-monostack-python`→`[[consolidate-memory-roadmap]]`/`[[governance-signal]]`,
`keyfigures-example-hallucination`→`[[contextual-retrieval-negative-2026-05-25]]`). A global fact's links travel
with it into every mirror, so a project-local link dead-ends in every *other* project (a fleet-wide latent defect).
- **`sync_global.py --promote` now WARNS** (non-blocking) when a fact being promoted carries `[[wikilinks]]` to
  non-global targets (`_nonglobal_wikilinks`) — a global fact should link only to other global facts. Prevents
  new fleet-wide dangling links at the source.
- The 3 existing canonicals were corrected — the project-local wikilinks converted to plain text (naming the
  origin project; they propagate to mirrors on each project's next `--pull`).
- SKILL: a note to avoid committing to the repo *while a dream runs* — a concurrent commit moves HEAD (the marker
  advances past it) and the Phase0→Phase5 audit window attributes it to the pass; the dream detects HEAD-moved +
  re-measures but can't fully disentangle it.

### Internal
- New `_nonglobal_wikilinks` helper + 1 smoke unit (flags project-local links; excludes global / self-ref /
  code-span `[[tool.mypy.overrides]]`). smoke 273/0 · sim · mypy · manifests.
- **Versioning — PATCH:** additive (a non-blocking promote warning + a helper + a SKILL note); no removed/renamed
  flag, no schema change. The audit concurrent-commit attribution + the marker-timing edge are accepted/documented
  honest gaps (the tool detects + flags them correctly), not engineered around — per the advisor's re-rank.

## [0.1.24] — 2026-06-20

### Added (CLAUDE.md MUTATION — the dream can now tidy committed CLAUDE.md, gated + audited; additive → patch)
Part two of the CLAUDE.md arc, riding the v0.1.22 recorder. The dream may relocate / compress / prune the
committed, team-shared CLAUDE.md hierarchy — **gated per-change, report-then-apply, never auto.**
- **The directive STAYS; relocate only the ELABORATION.** CLAUDE.md is always-loaded (enforced every session); a
  committed doc is on-demand (enforced only if a pointer cues a read). Relocating a *binding directive* silently
  erodes enforcement — invisible in a content diff. So a relocate SPLITS a heavy section: keep the directive + a
  pointer in CLAUDE.md, move the rationale/examples to a committed doc. A mechanical **normative-marker backstop**
  (`_has_normative_marker`, RFC-2119 / imperatives) flags a directive in the moving chunk — the guarantee the
  byte-conservation check can't give (the bytes still land). `--sections` surfaces heavy sections (mechanical; the
  directive-vs-elaboration judgment stays with the model).
- **Committed-target firewall.** `valid_relocate_target` accepts a target ONLY if it's in-repo AND not under
  `~/.claude` AND not git-ignored (fail-closed) — relocating into the private store or a gitignored dir is silent
  team data loss. Existing committed targets only; a missing target is PROPOSED for the human to create (the dream
  never imposes repo structure, never creates a `CLAUDE.md`).
- **Conservation self-check.** The audit snapshot extends to the relocate-target tree (`repo_doc`); the Phase-5
  `--audit` flags a CLAUDE.md drop with no matching target growth (a lost relocate vs a real move) — matched
  per-op, not per-store-netted. `compress` is a high-scrutiny exception (before/after verbatim); `prune` only a
  *descriptive* line whose referenced code is grep-confirmed gone (a *normative* line always proposes — the human
  owns the staleness call).

### Internal
- New `_has_normative_marker` / `valid_relocate_target` / `claude_md_sections` / `--sections`; `audit_snapshot`
  extends to `repo_doc`; `audit_diff` gains the `conservation` self-check; the `Audit` block gains `repo_doc` +
  `conservation` (additive `total=False`; co-edit across TypedDict + SKILL json + smoke pin + render). The Phase-4
  guest-rule shifts to "guest WITH permission to tidy, on the record" (both SKILL sites reconciled).
- Probe Q (normative backstop · firewall gitignored/private/outside/escape · sections · relocate-conserves vs
  eviction-flags-loss) + 2 smoke units. smoke 272/0 · sim · mypy · manifests.
- **Versioning — PATCH:** an additive capability + additive audit fields (legacy records render); no removed/renamed
  flag, no install/manifest break. finding-B (memory-index archive budget tier) → a later cycle.

## [0.1.23] — 2026-06-20

### Fixed (memory-index residuals from the dream beta-harness WARNs on v0.1.22; additive → patch)
The dream beta-harness confirmed the v0.1.20/21 fixes (D1–D5, D7 FAIL→PASS against git history) and left two
advisory WARNs — both verified live + closed here (orthogonal to the CLAUDE.md arc):
- **D6 — the standing-justify now re-fires on index-TOKEN growth, not just fact-count.** The v0.1.21 suppress
  predicate keyed on fact-count alone, so hook bloat (tokens up, facts flat) past a justified baseline stayed
  silently suppressed — blind to the exact axis the budget polices. The gate now suppresses ONLY when BOTH
  fact-count ≤ baseline+Δ AND index tokens ≤ baseline_tokens × 1.25 (`_STANDING_JUSTIFY_TOKEN_FACTOR`); either
  axis growing — or no valid token baseline — re-fires. Fails OPEN like the fact-axis. The marker already
  persists `index_tokens` (since v0.1.21), so no schema change.
- **D10 — archive-index docs + MEMORY.md are now valid wikilink targets.** memex's "dangling" links were mostly
  false positives: `[[SHIPPED]]` points at the real `SHIPPED.md` archive but was flagged because the check saw
  fact-stems only. `valid_link_targets(auto_mem)` returns every `*.md` stem (facts + archive docs + `MEMORY`);
  the Phase-5 dangling check + `resolve_wikilink` resolve against it, so `[[SHIPPED]]`/`[[MEMORY]]` aren't
  false-flagged. (The bulk of the rest — code-span `[[...]]`, paths — is the model's SKILL-instructed
  code-span-stripping job; the genuinely drifted few still surface for a dream's judgment.)

### Internal
- New `_standing_baseline_tokens` + `_STANDING_JUSTIFY_TOKEN_FACTOR` + `valid_link_targets`; a two-axis suppress
  predicate; SKILL dangling-check prose. NO cycle-record change (the token baseline lives in the marker; the
  surface text is static prose — no co-edit).
- Probe P (token-axis fires on bloat · fact-axis still fires independently · zero/missing token baseline fail-open
  · archive/index resolve) + 2 smoke units. (Probe N's marker got a generous token baseline to isolate the
  fact-axis it tests.) smoke 269/0 · sim · mypy · manifests.
- **Versioning — PATCH:** additive helper + a behavioral tightening (the gate fires more accurately on token
  bloat — the safe direction); no removed/renamed flag, no schema change. The CLAUDE.md mutation → v0.1.24.

## [0.1.22] — 2026-06-20

### Added (CLAUDE.md-arc FOUNDATION — whole-hierarchy measurement + deterministic mutation audit trail; additive → patch)
The CLAUDE.md-optimization arc is SPLIT (advisor sequencing): v0.1.22 ships the read-only / low-risk foundation;
the actual CLAUDE.md mutation (relocate/compress/prune) rides this recorder in v0.1.23.
- **Whole-hierarchy CLAUDE.md measurement (read-only).** Empirics: memex's `src/memex/CLAUDE.md` (~34k tok) +
  `src/memex/webui/CLAUDE.md` (~16k) mean a session in `webui/` pays **~54k tok of CLAUDE.md every turn** —
  invisible to the tool, which measured only the root file (vs `CLAUDE_MD_TOKEN_BUDGET=4000`). `claude_md_hierarchy`
  now finds every CLAUDE.md (root + nested, excl vendored/VCS) and reports the **worst-case root→leaf path** ("a
  session in `<dir>` pays ~Nk/turn") in the Phase-0 report + the dashboard. **Detect-and-report only — NOT wired
  into the memory-index gate** (different subsystem).
- **Deterministic, script-emitted mutation audit trail.** `memory_status.py --snapshot` (Phase 0) writes a
  per-slug content-hash snapshot of the memory store + CLAUDE.md hierarchy; `--audit <snapshot>` (Phase 5) diffs
  it, appends a per-operation record (created/modified/deleted + token deltas) to `.mutation-log.jsonl`, and fills
  the cycle record's new `audit` block. This is the script-OBSERVED counterpart to the model-narrated `entries[]`
  — they should agree; a divergence is a signal. **Honest gap:** the Phase0→Phase5 window attributes any change in
  the span to the pass. Covers the memory writes every cycle already does — the dogfood that proves the recorder
  before v0.1.23 turns on CLAUDE.md mutation.

### Internal
- New helpers `claude_md_hierarchy` / `audit_snapshot` / `audit_diff` / `audit_snapshot_path` + `--snapshot` /
  `--audit` modes. Cycle record gains `budget.claude_md_hierarchy` + a top-level `audit` block (5 new TypedDicts;
  the contract co-edit lands across the TypedDicts + SKILL `​```json` + the smoke nested-pin + `seed_record` + the
  renderer + `validate_cycle_record`'s dict-type guard).
- `.gitignore` now also guards `.mutation-log.jsonl` + `.consolidation-log.jsonl` (PUBLIC-repo defense-in-depth;
  the store is also out-of-tree).
- Probe O (hierarchy worst-path · audit created/modified/deleted via content-hash · unchanged ≠ op · infra
  excluded · measuring is read-only) + 3 smoke units. smoke 264/0 · sim · mypy · manifests.
- **Versioning — PATCH:** additive (read-only measure + a new audit subsystem; new flags; `total=False` blocks);
  no removed/renamed flag; NO CLAUDE.md mutation (that's v0.1.23); legacy records render. The mutation arc →
  v0.1.23; finding-B + the token-axis wire-up stay backlogged.

## [0.1.21] — 2026-06-20

### Fixed (v0.1.19 first-party beta defect catalog — 9 root-cause fixes; additive → patch)
A second memex beta (106 facts, index 231% over) filed an 11-defect catalog; all verified empirically.
**D1/D2 were the `/tmp/cycle.json` collision already fixed in v0.1.20** (the "render reads the wrong node"
hypothesis was REFUTED — the gauge reads `budget.index`; a concurrent dream clobbered the shared seed → the
Doc_Flo render showed consolidate-memory's 885/2256). D3–D11 are fixed here at root-cause; the archive-index
BUDGET TIER (finding B) stays in the CLAUDE.md arc (no double budget model).

- **Standing-justify-as-delta-detector (D3·D5·D6·D7·D11) — the cluster root.** The fixed 1200-tok index budget is
  unreachable for a mature lean store (105 facts × ~20-tok floor = 2100; even a max prune = 2160 > 1200), so the
  gate fired every pass and re-litigated the same triage. Rather than scale the budget (which would defeat the
  v0.1.18 gate — a bloated large store would get a budget that hides the bloat; earned-vs-bloat is irreducibly
  content-aware), a **standing-justify**: the operator confirms the density is earned once
  (`standing_justify: {facts, index_tokens, at}` in the marker) and the gate is SUPPRESSED until fact-count grows
  by Δ (10) — a delta-detector that keeps the teeth (fires on NEW density) while killing alarm fatigue. **Fails
  OPEN** — a garbage/legacy marker → gate fires (suppression requires a valid baseline). `reaches_budget` (D5):
  when a full prune can't reach budget the lever is prune-the-safe-THEN-standing-justify the residual, not a clean
  achievable "prune." Gate-aware drift (D3/D11): over budget, the index↔file gap is INTENTIONAL — no "backfill"
  offer (it net-grows under the no-net-grow gate); backfill stays legit UNDER budget.
- **Wikilink-aware orphan reachability (D4 — SAFETY).** `resolve_wikilink` resolves a `[[target]]` across
  slug-drift (date-suffix, dash↔underscore; EXACT-only, ambiguous→skip — never substring). A fact `[[wikilinked]]`
  from another fact now folds into `reference_stems`, so the A-stage no longer flags it a safe-evict orphan
  (evicting would dangle the live link — e.g. `form_table_research`/`grounding_gate_overrefusal` on memex, both
  wikilinked from indexed facts). Extends the v0.1.19 C2 surfaces (CLAUDE.md + archive) with the auto-memory
  wikilink surface.
- **Presentation + defensive (D8/D9/D10 · D1/D2-class).** D8: the remediation surface leads with the INDEX-RELIEF
  stages (B/C/R — what moves the gated index); TRUE orphans (disk-only, 0 index relief) render LAST. D9: the
  Phase-0 RIGOR line annotates an active over-budget gate (HEAVY-equivalent hard-stop) so "LIGHT" doesn't
  undersell a gated pass. D10: dangling-wikilink health uses `resolve_wikilink` to suggest the drifted target.
  D1/D2 defensive: the dashboard warns when `budget.index` and the trigger network-node grossly diverge (>1.5×) —
  catches the wrong-budget class beyond v0.1.20's per-slug seed fix.

### Internal
- The `Remediation` block gains `standing_justified`/`baseline_facts`/`reaches_budget` (additive `total=False`);
  the typed contract co-edit (TypedDict + SKILL `​```json` + smoke pin + `seed_record` + the renderer) lands
  together. `memory_status.py` gains `--seed`-independent helpers `resolve_wikilink` + `_standing_baseline`.
- Probe N (standing-justify suppress-within-Δ / fire-past-Δ / fail-open · D4 wikilink→R · D5/D8 · resolve_wikilink
  drift) + 2 smoke units. smoke 259/0 · sim · mypy · manifests.
- **Versioning — PATCH:** additive (a new optional marker field, helpers, flags, gate-aware framing, presentation,
  a render warning); no removed/renamed flag; legacy records render. The CLAUDE.md-optimization arc → v0.1.22.

## [0.1.20] — 2026-06-20

### Fixed (cycle-record temp-path collision across concurrent dreams; additive → patch)
- **The dream's cycle-record temp path is now PER-SLUG, not the shared `/tmp/cycle.json`.** SKILL.md hardcoded
  `/tmp/cycle.json` for the Phase-0 seed + Phase-5 render, so two project dreams running concurrently collided:
  during a consolidate-memory dogfood dream, a **memex dream in another session clobbered the shared file**
  between seed and render → the dashboard grafted memex's scope/remediation onto consolidate-memory's entries
  and persisted a "franken-record" to the calibration log. (Caught by the dogfood + measure-don't-assert —
  "105 reviewed / gate fired" is impossible for a 16-fact under-budget store.)
  - **`memory_status.py --seed`** (new) writes the seed to `cycle_seed_path(slug)` =
    `<tmpdir>/cm-cycle-<slug>.json` (deterministic, per-project) and prints the path; SKILL.md Phase 0 now uses
    `--seed` and references that path through the phases + the render. `--json` (stdout) is unchanged for
    ad-hoc / `cm seed` use.
  - Per-slug kills the cross-PROJECT collision (the observed case); same-project concurrent dreams (degenerate)
    would still share a path — acceptable.

### Internal
- +1 smoke unit (`cycle_seed_path` per-slug + deterministic, not the shared path). smoke 257/0 · sim · mypy ·
  manifests.
- **Versioning — PATCH:** additive (a new flag + helper + SKILL prose); `--json` kept (no removed flag); no
  cycle-record schema change. The CLAUDE.md-optimization arc renumbers to v0.1.21.

## [0.1.19] — 2026-06-20

### Fixed (v0.1.18 first-party beta findings — multi-surface orphan safety; additive → patch)
- **C1 (SAFETY) — never treat an archive-index doc as a fact.** A relocated archive (`SHIPPED.md`, a
  link-list) was globbed as a fact; its stem matched the tracker regex → the triage advised "evict" = nuking
  the archive. `build_context` now detects archive-index docs (`_is_archive_index`: a link-list `*.md` with no
  fact frontmatter) and excludes them from `fact_files`. (Surfaced by verifying the beta pass against memex's
  real store — it was NOT in the report.)
- **C2 (SAFETY) — multi-surface orphan check.** The "unindexed → evict" check read only `MEMORY.md`; 23/61
  flagged orphans were referenced in CLAUDE.md prose → "evict" would dangle the committed guest file. The
  triage now gathers `reference_stems` from all always-loaded surfaces — CLAUDE.md prose (bare-stem) +
  archive-index link-targets — and reclassifies a referenced-but-unindexed fact to a new **R (referenced)**
  stage (de-link the surface FIRST; counts toward keep, re-indexed by the lean rebuild), never a blind evict.
- **E (defensive)** — a 0-token index read while facts exist (a write-truncate race) would clear the
  over-budget gate; `build_context` now re-reads once to settle it (a persistent 0 is a genuine all-unindexed
  drift, flagged by schema_drift, not "under budget").
- **F (polish)** — the redundant `prune-pressure (index-over-budget)` line is suppressed when the REMEDIATION
  gate renders (a `many-facts` prune-pressure still prints); the triage output labels `projected_recall` as
  recall-body hygiene, SEPARATE from the index-pointer relief.
- **G (polish)** — `seed_record` omits `pruned`/`achieved_*` (model-filled in Phase 5); the dashboard renders
  their absence as "pending Phase 5", not a misleading ≈0.
- **H (polish)** — documented the `extract_signals --json` contract (`counts.surfaced` + `signals`; no
  top-level `surfaced`/`candidates`).

### Deferred (the beta's DESIGN findings → the CLAUDE.md-optimization arc)
A (a first-class `relocate` lever + split index-pointer vs recall-body projections), B (an archive-index
budget tier so a mature store can be *genuinely* under budget, not perpetually justified), and D (model
CLAUDE.md as a second always-loaded index for dedup) share that arc's design space — tracked in the roadmap.

### Internal
- New `_is_archive_index`; `remediation_triage` gains a defaulted `reference_stems` param + the **R** stage.
  Probe M (hermetic): archive-exclude · referenced→R-not-A · true-orphan→A · seed-omits-achieved · 0-index-safe.
  +2 smoke units. smoke 256/0 · sim A–M · mypy · manifests.
- **Versioning — PATCH:** bug/safety/polish, backward-compatible (defaulted param, no removed flag/script,
  the `Remediation` typed block unchanged, seed omission `total=False`-safe, legacy records render).

## [0.1.18] — 2026-06-20

### Added (inherited-backlog remediation — the prune finally has teeth; additive → patch)
- **Remediation triage + an over-budget GATE.** The app prevented *incremental* bloat (budget ⚠ +
  `prune_pressure`) but couldn't REMEDIATE a backlog inherited from Claude Code's Auto-Dream (unbounded
  append, no index discipline) — observed on a real store: 110 facts, index 5.5× budget, 30 unindexed
  orphans, and a dream that fired `prune_pressure` yet *grew* the index. v0.1.18 adds:
  - **`remediation_triage` (`memory_status.py`)** — for an over-budget index, a PURE classifier ranks local
    prune candidates into cost-ordered stages: **A** unindexed orphans (unrecallable dead weight), **B**
    tracker/status (transient), **C** dated/oversized (content-review) — vs the durable-keep core, with a
    projected lean rebuild. Surfaced in Phase 0 + a new `memory_status.py --triage` view. Empirics showed a
    name/date heuristic mis-classifies durability, so the triage **RANKS/surfaces; it never decides** — the
    model judges content, the user confirms.
  - **The over-budget gate (the teeth)** — the previously HEAVY-only hard-stop now applies at ANY tier when
    the index is already over budget: a pass may not net-grow it, and must **prune-or-justify**. ROUTED by
    the mirror-vs-local attribution: `prune` (local-dominated), `gc` (mirror-dominated >50% — a local prune
    is futile), or `justify` (nothing safely prunable — no deadlock).
  - **Never auto-deletes** (hard invariant): the classifier is pure/no-delete; prunes route through the model
    + the user's confirm (the existing "surface deletions you didn't author" rule).
- A cycle-record `remediation` block (additive `total=False`; legacy records still render) + the dashboard
  renders it — a gate that fired-but-was-unacted stays visible.

### Internal
- New `Remediation` TypedDict via the four-place contract co-edit (TypedDict + SKILL schema block +
  `CycleRecord` + the smoke nested schema-pin). **Probe L** (hermetic) builds an Auto-Dream-style bloated
  store and asserts the A/B/C staging, the lever routing (prune/gc/justify), the never-delete invariant, and
  no-false-alarm on a healthy store. +4 smoke units. smoke 254/0 · sim A–L · mypy · manifests.
- **Versioning — PATCH:** additive (a new analysis + a new guard + prose); no removed/renamed flag/script,
  no manifest change; the cycle-record block is additive `total=False`; the gate only changes behavior for
  already-over-budget stores. (empirics → spec → Gate-1 → meta-test → Gate-2.)

## [0.1.17] — 2026-06-20

### Fixed (cross-project reachability — `slug_for` now matches Claude Code's slug normalization)
- **`slug_for` maps both `/` AND `_` to `-`** (was `/` only), matching Claude Code's real project-slug
  rule. Verified on disk: a session with cwd `…/Doc_Flo` is logged by CC under slug `…-Doc-Flo` (hyphen),
  but the old `/`-only `slug_for` computed `…-Doc_Flo` (underscore). So for ANY underscore-named project,
  replicated cross-project facts (`--pull`/`--promote`) landed in a slug the project NEVER recalls — the
  middle tier was silently unreachable there. This is the root-cause reachability fix.
  - The same `/`-only bug existed in **`extract_signals.py`** (Phase-2 transcript lookup) — the extractor
    found no transcripts for an underscore project. Both now route through the single `slug_for` (DRY).
  - **No regression for non-underscore projects:** `re.sub(r"[/_]","-",p) ≡ p.replace("/","-")` with no
    underscore; case preserved (`Doc-Flo`, not lowercased).
  - **Honest limit:** verified on disk only for `/` and `_` (no other-char example exists); a `.`/space
    could diverge further and would NOT be caught by `near_duplicate_slugs` (collapses only `_`/case) — an
    accepted, documented residual risk. Corrected the `claude-code-memory-is-slug-scoped` fact +
    `harness-map.md` (the earlier "a rename changed the slug" framing was wrong — it was the `_`→`-` mismatch).

### Added
- **A `pdf` stack for `detect_stacks`** (dist `{pypdfium2, pymupdf, pdfplumber, pdf2image, pdfminer-six}` /
  module `{pypdfium2, fitz, pdfplumber, pdf2image, pdfminer}`) — so genuinely cross-project PDF-library
  gotchas (e.g. pdfium thread-unsafety) can be `stack-general:[pdf]` and bind the fleet's PDF projects.
  Real-usage gated like every stack (declared dep / real import, never a doc-mention; exact-token).

### Internal
- +6 smoke checks (slug `/`+`_`→`-` with case preserved + a no-underscore regression guard; pdf dep/import
  detection, exact-token disjointness, `is_relevant(stack-general:[pdf])`). `simulate_accumulation.py`'s
  `_store` helper now uses the single `slug_for` (was a third copy of the rule). smoke 249/0 · sim · mypy.
- **Versioning — PATCH:** the deterministic policy's minor triggers are CONTRACT breaks (incompatible
  cycle-record schema, a removed/renamed script or CLI flag, a changed manifest) — the slug fix hits NONE.
  Non-underscore installs are byte-identical; underscore installs IMPROVE (unreachable → reachable) with
  reclaimable orphans (the upgrade note + the shipped near-dup detector handle the one-time migration).
  Matches the v0.1.16 precedent (which even added a CLI flag, still patch).

### Upgrade note (only if you have an underscore-named project dir)
After upgrading, that project's `--pull`/recall targets the correct (hyphen) slug; its **pre-v0.1.17 mirrors
sit under the old `…_…` slug**. Phase 0's near-duplicate-slug detector flags the split — reconcile toward the
slug CC actually uses (a transcript's recorded `cwd` → its on-disk slug dir is ground truth), then retire the
old-slug store. Non-underscore projects are unaffected.

## [0.1.16] — 2026-06-19

### Added (cross-project middle tier — real-usage stack detection + a local→canonical promotion path; additive, backward-compatible → patch)
- **Real-usage `detect_stacks`.** A project's stacks are now inferred from REAL USAGE, never a doc-mention:
  declared dependencies in `pyproject.toml` (PEP 621 `[project]` + optional-deps, PEP 735 dependency-groups,
  and poetry tables — matched as EXACT PEP 503-normalized dep-name tokens, so `sentence-transformers` is
  never read as `transformers`; comments stripped string-aware; extras-safe array parsing), actual `import`s
  in `*.py` (ast-based, so an `import` inside a docstring/string literal does not count), and real marker
  dirs/files (`.claude/`, a `SKILL.md` via bounded `rglob`). Lockfiles are excluded (transitive deps
  over-detect). This kills the old prose-keyword false-match — a stdlib repo whose README merely said
  "rag"/"scraper" used to inherit `rag`/`playwright` — so `is_relevant` binds a `stack-general:[rag]` fact
  only to projects that really depend on / import a RAG library. The middle tier is meaningful, not
  universal-or-nothing. (`_kw_hit` removed; the detection map keeps every stack — `python`/`mypy`/`rag`/
  `gpu`/`playwright`/`claude-code` — now real-usage-gated.)
- **`sync_global.py --promote PROJECT_DIR LOCAL_FACT [CANON_NAME]`** — the local→canonical hand-off
  symmetric to `--pull`. Hands a project-authored local fact UP to the canonical global store and converts
  the origin's own copy into a managed `global_ref:` mirror in one single-shot op (canonical write +
  provenance + origin-mirror + rename cleanup), so a completed call never leaves the dup/orphan a multi-step
  hand-done hand-off would (a stranded project-authored copy that `--gc` can't reclaim, shadowing or
  duplicating the canonical on the next `--pull`). `CANON_NAME` renames (`_`→`-` / drop a date) or dedups
  onto an existing canonical (whose content is **never overwritten** — only the origin is reconciled + the
  holder appended to provenance). Five refusal guards: an already-mirror fact, a non-replicable scope
  (must be `stack-general`/`user-global`), a `stack-general` fact with no `stacks:` (matches no project), a
  destination-clobber of a distinct local fact, and the reserved index name `MEMORY`. Exposed as `cm promote`.
- **Phase-0 promotion-candidate surface + Phase-1 promotion re-audit.** `memory_status.py` surfaces a
  "promote?" signal (authored, non-mirror, unscoped facts whose `type` leans cross-project — feedback/
  reference, capped); the SKILL gains a Phase-1 promotion re-audit symmetric to the existing user-global
  demotion re-audit — re-walk the scope cascade by CONTENT, gated **stricter** than demotion (it is the
  higher-blast-radius direction): conservative floor, a Phase-3 re-verify AND a point-in-time/supersession
  screen, dedup vs existing canonicals by content, a per-pass cap, detect-and-offer only. `_is_mirror`
  promoted to `memory_status` as the single shared definition (smoke-pinned), so the promotion surface and
  `sync_global` share one mirror-recognizer.

### Internal
- `_fact_stacks` extracted as the single `stacks:` parser shared by `is_relevant` + the promotion guards.
  New smoke coverage: the pyproject parser (PEP 621/735/poetry, extras-safe, string-aware comment strip),
  ast-based imports, exact-token stack maps, `is_relevant`, the `_is_mirror` single-source pin, the
  promotion-candidate seed filter, `_fact_stacks`, and the `promote` op surface. `simulate_accumulation.py`
  gains **Probe K** — a hermetic end-to-end of the `--promote` hand-off (create / rename / reconcile-dedup +
  all five refusal guards), asserting the load-bearing invariant that a follow-up `--pull` on the origin is
  `in-sync` (the mirror is already post-provenance), not a STALE rewrite. `references/harness-map.md` +
  SKILL Phase-1/Phase-4 updated to the real-usage detection + dual (demotion/promotion) re-audit model.
- **Patch, not minor:** no removed/renamed script or CLI flag (`--promote` is additive), no manifest or
  cycle-record schema change (legacy records still render). The patch-vs-minor guarantee holds because the
  global store has **0 `stack-general` facts today** — so no live mirror is re-routed by this release; the
  first such facts are created by a later curated promotion pass, after this version ships.

## [0.1.15] — 2026-06-18

### Added (output polish — hanging-indent wrapping + uniform width; additive, backward-compatible → patch)
- **Hanging-indent line wrapping.** Long lines no longer overflow past the banner — they word-wrap to
  the render width with a HANGING INDENT, so a continuation lines up under where its section's content
  began (a `kv` value continues under the value column; a `·` list item under its own text) instead of
  falling back to column 0. New ANSI-aware `_ui.wrap()` / `_ui.li()` measure VISIBLE width (escape codes
  don't count), never split an escape, re-open the active color across a break, and keep an over-long
  single token (a hash / path) whole.
- **Uniform, terminal-adaptive width.** The banner rule and the wrap right-edge now share one width W:
  it fills the terminal when stdout is a TTY (clamped to a readable [60, 100]); a pipe / captured output /
  test falls back to a fixed 60 so non-interactive output stays deterministic. A new `--width=N` overrides
  it on any reporting command and the dashboard.
- Applied across every output (`memory_status`, `sync_global` --list/--network/--tokens/--gc,
  `extract_signals`, and the `render_dashboard` reference) so the whole tool is symmetric on the sides.
  `--json` is untouched; `--ascii` still flattens to pure ASCII (now at the uniform width). The dense
  `--tokens` node table keeps its columns — its trigger marker drops to a hanging line only if it would
  overflow.

### Internal
- `render_dashboard` now imports `_ui.wrap` + `_ui.resolve_width` (its other primitives stay mirrored +
  smoke-pinned). Smoke renders its content assertions WIDE (so wrapping never splits a pinned substring)
  and adds 9 tests covering wrap fit/hang/ANSI-safety, `kv`/`li` wrapping, the ui↔rd wrap mirror, and
  width resolution.

## [0.1.14] — 2026-06-18

### Added (unified visual language across every output — additive, backward-compatible → patch)
- **`_ui.py` — one shared visual vocabulary.** Extracted the final dashboard's look — the `━` banner,
  bold-UPPERCASE `kv` section labels (which carry the hierarchy even in monochrome), budget `bar`s,
  glyphs, auto-gated color, and the `--ascii` fallback — into a new zero-dep, stdlib-only module that
  `memory_status`, `sync_global`, and `extract_signals` now import. Every human-facing report is
  visually coherent with `render_dashboard.py`'s reference (same banner, section style, glyph/color
  palette), each adapted to its own content. `render_dashboard.py` is **unchanged** — it stays the
  byte-pinned reference (37 output assertions + a determinism check); a new smoke **drift-pin** asserts
  `_ui` stays byte-identical to render's primitives, so the unified look can never silently diverge.
- **Restructured the dense reports for clear hierarchy + low cognitive load.** `memory_status`'s 15 flat
  `---` sections → 7 scannable ones (banner · SCOPE · RIGOR · STORES · SIGNALS · GLOBAL · SESSION · NEXT)
  with the per-fact inventory in aligned columns + always-loaded budget bars; `sync_global`
  (`--list`/`--network`/`--tokens`/`--gc`) and `extract_signals` likewise gain the banner + labeled
  sections + status glyphs (✓ in-sync · ↓ missing · ⟳ stale · ◀ trigger). Every datum the SKILL/agent
  parses mid-dream is preserved.
- **`--color` / `--ascii` on `memory_status`, `sync_global`, `extract_signals`** (matching the dashboard):
  `--color=never|always|auto` (default auto — OFF when piped/captured/non-TTY, so agent tool-calls and
  pipes stay clean plain text); `--ascii` flattens glyphs to a pure-ASCII fallback. `--json` output is
  untouched — no color/banner leaks into the machine contract.

### Fixed
- **`--ascii` now flattens every `sync_global` view.** `network`/`token_report`/`gc` printed glyphs
  directly, bypassing the ASCII fallback (would `UnicodeEncodeError` / render mojibake on a non-UTF8
  terminal — the exact case `--ascii` exists to serve); they now buffer and route through
  `ascii_translate` like the other reports.
- **A bare visual flag is never mis-read as a project dir.** `sync_global` and `extract_signals` didn't
  exclude `--color`/`--ascii`/`--no-color` from positional parsing, so e.g. `sync_global --pull --ascii`
  (dir omitted) treated `--ascii` as the project → a bogus slug it would have replicated mirrors INTO.
  Both now filter dash-flags from positionals (the pattern `memory_status` already used).

## [0.1.13] — 2026-06-18

### Changed (product repositioning — docs/messaging only, no code change → patch)
- **Repositioned around the two axes Auto Dream doesn't cover.** Claude Code is rolling out a built-in
  **Auto Dream** (per-project memory consolidation; auto-trigger + a `/dream` command — currently
  server-side-flagged/beta, not GA), which commoditizes the base "consolidate a project's memory"
  pitch. The README, `plugin.json` + `marketplace.json` descriptions, and SKILL framing now lead with
  what Auto Dream lacks: **cross-project shared memory** (the governed global store + promotion/
  demotion cascade) and **verification against the live code** (grep/file/`git log` — fact-checked, not
  transcript-merge), plus tiered context-budget accounting. Positioned honestly as the rigorous,
  fleet-wide **complement** to Auto Dream's per-project baseline. The `dream` trigger and
  all behavior are unchanged — the differentiators already exist in code; this aligns the messaging.

### Notes
- **Strategic context (see roadmap):** Auto Dream + `/dream` are **not yet GA** (server-side flag,
  beta) → a real first-mover window, but contested by public clones (`jl-cmd/claude-dream`,
  `grandamenium/dream-skill` — both per-project, neither code-verifying). Our durable edge is the two
  differentiators above. External / 1.0 / community-directory submission is the open decision this
  repositioning prepares for.

## [0.1.12] — 2026-06-18

### Changed (1.0-prep — docs/comment/test hardening; no behavior change → patch)
- **`memory_status.py`** — fixed a stale comment claiming cycle records "render and are discarded
  today; persisting them is a roadmap prerequisite." `--persist` shipped in v0.1.4 (this was the
  code-comment straggler from the v0.1.11 doc-sync, which corrected the same claim in the `.md` files).
- **`SECURITY.md`** — corrected the secrets-firewall ReDoS note: the regexes aren't literally "linear
  (no nested quantifiers)" — they have no *catastrophic backtracking* (each alphanumeric run and its
  required separator are disjoint) and input is capped at `_PROBE_CAP` = 4000 chars. Same property,
  accurate wording.
- **`tests/smoke.py`** — extended the SKILL↔TypedDict pin from 3 shapes (CycleRecord/Health/Marker) to
  **all nested shapes** (Scope, Rigor, Verification, Entry, Budget + 4 sub-dicts, CrossProject,
  Network + 2 sub-dicts), so SKILL.md's nested schema block can't silently drift from the code.

### Notes
- A **1.0-readiness review** (this session) found the contracts **1.0-safe** (additive-by-construction;
  no breaking change foreseeable in the backlog) and the polish 1.0-grade after these three fixes. The
  **1.0.0 tag is deliberately deferred** to the broader-discovery push, where its stability signal
  earns its keep. Docs + one comment + test coverage, zero runtime dep → **patch**.

## [0.1.11] — 2026-06-17

### Changed (docs + one stale code comment — no behavior change → patch)
- **Doc sync: reconcile the docs with the shipped state.** README now documents the v0.1.8
  **promotion cascade** (fleet-constant vs fleet-varying; Gate 0/1/2) + the v0.1.9 **demotion
  backstop** in the cross-project model, the v0.1.10 **dream-timing** nudge in Usage, and a
  NEURAL NETWORK line in the dashboard example. SKILL.md + harness-map.md: fixed a stale "cycle
  records are not persisted yet" claim that contradicted the shipped `--persist` (v0.1.4); dropped a
  stale "(planned)" tag on the now-shipped demotion re-audit; named the **G2.3** gate it backstops.
  Also re-characterized repo-root `memory/` as a gitignored placeholder (the global store decoupled to
  `~/.claude/memory`), added the dream-timing advisory to harness-map's Phase-0 catalog, and refreshed a
  stale `sync_global.py` comment + the versioning-precedent list.

## [0.1.10] — 2026-06-17

### Added
- **Dream-timing advisory — a no-nag Phase-0 nudge.** `memory_status.py` now surfaces a
  `💤 dream-timing` line (also via `cm status`) when commits have accrued **since the last dream** and
  cross the SUBSTANTIAL band — flagging a good consolidation boundary *before* compaction. Keyed on
  commits-since-marker + marker age (a coarse hint, not a gate — the count over-counts already-
  consolidated work). **Advisory only:** it never auto-fires a dream (explicit-trigger-only is a kept
  design value); silent below the band and on a first consolidation (no prior dream).

### Notes
- Operationalizes this session's dream-timing research (the ideal moment to consolidate is a work-arc
  boundary, before `/compact` degrades the model's curation). One pure, never-crash helper
  (`dream_timing_advisory` — tz-robust float-epoch age, no-marker guard) + a Phase-0 report line + a
  dev-loop note; **no cycle-record schema change, zero runtime dep** → **patch**. The complementary
  *curation-quality* longitudinal signal remains deferred (needs the cycle-log to accrue).

## [0.1.9] — 2026-06-17

### Added
- **Demotion backstop for the promotion cascade — a Phase-1 *content* re-audit (SKILL prose).** Each
  consolidation now re-walks the v0.1.8 promotion cascade over the existing `user-global` facts *by
  content* and surfaces any that would now route lower (e.g. a `mypy`- or release-gated fact →
  `stack-general`) as **detect-and-offer demotion candidates** — never auto-applied. This closes the
  governance loop: the "signal-checked-out" half that backstops Gate 3's deliberately-weak
  applicability gate.

### Changed
- **`extract_signals` is now run-or-justify-skip (Phase 2).** A pass must run the extractor (it reads
  the compaction-proof on-disk transcript) or record an explicit skip-justification — so a compacted
  session can't silently drop the feedback/gotcha signal.
- **Dashboard RIGOR line:** an overridden tier now reads `suggested → applied · override: <why>` (was
  a mislabeled `· applied: <why>` that duplicated the arrow).

### Notes
- **Empirics-first kill (recorded so it's never re-proposed):** the originally-planned *adoption-based*
  demotion-audit (flag a fact with few `projects:` holders) has **no valid signal** — `--pull`
  replicates every `user-global` fact into every project (`is_relevant → True`), so `holders` measures
  pull-activity, not fit (a mis-scoped fact and a universal one both reach all projects). The valid
  signal is content (re-walk the cascade); the longitudinal "stuck across N cycles" form is deferred
  until the per-project cycle-log accrues.
- SKILL prose + a 1-line render relabel; **no cycle-record schema change, no new mechanical detector,
  zero runtime dep**; legacy records still render (the relabel is cosmetic) → **patch**.

## [0.1.8] — 2026-06-17

### Changed
- **Promotion governance: a hard scope-decision cascade replaces the prose bar.** SKILL.md
  Phase 2 now routes each candidate fact to `project-local` / `stack-general` / `user-global`
  via a total, acyclic cascade (Gate 0 → Gate 1 → Gate 2's five hard gates **G2.1–G2.5**),
  keyed on a **fleet-CONSTANT substrate** (the user's OS/account, an always-present CLI like
  `gh`, the Claude Code harness — present in *all* projects → eligible for `user-global`) vs a
  **fleet-VARYING precondition** (a stack/tool/workflow in only *some* projects — `mypy`,
  release-cutting → at most `stack-general`). A `user-global`/`stack-general` promotion now
  records its **deciding gate + the concrete other project named for the applicability gate
  (G2.3)** in the entry's `reason`. Mirrored into `references/harness-map.md`.

### Notes
- Policy/prose change only — **no code, no cycle-record schema change, zero new runtime dep**;
  legacy records render unchanged → **patch**. The complementary **demotion-audit** (flag a
  `user-global` fact never adopted beyond its origin project, via the lagging `projects:`
  provenance) is the committed next cycle — it backstops G2.3, the deliberately weakest gate.

## [0.1.7] — 2026-06-17

### Added
- **`--ascii` dashboard fallback** for older / non-UTF8 terminals: `render_dashboard.py --ascii`
  translates the dashboard's Unicode glyphs to single ASCII chars (width-preserving, so column
  alignment holds), with a catch-all that **GUARANTEES pure-ASCII output** (`.isascii()`; any
  unmapped glyph → `?`). Opt-in — the default Unicode output is byte-identical.

### Changed
- **No-op passes no longer print a RIGOR line.** A true no-op (magnitude 0 + no entries) used to
  render `RIGOR LIGHT · magnitude 0` — an effort estimate on a do-nothing pass; it now collapses
  like the other empty sections. A pass with entries or magnitude > 0 is unchanged.
- **`extract_signals` noise filter** now drops `<task-notification>` / `<teammate-message>`
  envelopes (multi-agent / harness injections the dream meta-test surfaced as false "feedback") —
  a precision improvement to the Phase-2 signal; a human still curates candidates.

### Notes
- All three are additive / cosmetic; backward-compatible → patch.

## [0.1.6] — 2026-06-17

### Added
- **A typed cycle-record contract (`TypedDict`) — static, producer-side drift-catching.**
  The cycle record — the data contract between `memory_status.py` (seeds it), the workflow
  phases (fill it), and `render_dashboard.py` (renders it) — was an untyped dict whose 42-line
  shape was hand-maintained in THREE places (the seed ↔ the renderer ↔ `SKILL.md`'s schema
  block), the recurring source of drift/crash findings. `memory_status.py` now defines the
  whole shape as `TypedDict`s (`CycleRecord` + every nested shape, all `total=False`), and the
  producers/consumers are annotated (`seed_record`/`_provisional_rigor`/`schema_drift` →
  their types; `render`/`_demo_record` → `CycleRecord`). mypy now flags a drifted, renamed,
  extra, or wrong-typed key in the dict LITERALS this codebase emits — the main historical
  drift source. **Honest scope:** the static win is **producer-asymmetric** — `total=False`
  flags a mis-named key via subscript / in a literal, NOT on a `.get()` read, so render's
  defensive reads are covered by the runtime validator (below) + IDE hints, not mypy.
- **A warn-only runtime validator `validate_cycle_record(record) -> list[str]`** (in
  `memory_status.py`): pure, stdlib, NEVER raises. It surfaces the model-slip class behind the
  past crashes — a PRESENT key of the wrong CONTAINER type, at the ACTUAL nesting (incl.
  `health.slug_orphans` / `health.schema_drift`, which nest under `health`) — and is quiet on a
  missing key (a partial record is normal) and on correct types. `render_dashboard.py` runs it
  after parsing and prints any warning to **stderr** (`render_dashboard: cycle-record
  warning: …`), non-blocking.
- **A SKILL↔TypedDict sync test (smoke):** parses the `SKILL.md` cycle-record schema block and
  asserts its top-level key set == `CycleRecord.__annotations__` (and the nested `health` shape
  == `Health.__annotations__`), so the doc can't silently drift from the code — "single source
  for the CODE; `SKILL.md` kept aligned by this test." Added `outcome` (a real optional override
  render already supports) to the schema block so the two agree key-for-key.

### Changed
- **`render_dashboard.py` runs the validator** on the parsed record → warnings to stderr
  (the rendered dashboard on stdout stays **byte-identical** for a well-formed record). The
  read-only record helpers (`_outcome`/`_over`/`_network_section`/`_persist`) take
  `Mapping[str, Any]` (a TypedDict is assignable to a read-only Mapping — this also dissolved
  the old dual-budget-shape friction in `_over`); `_num` keeps `x: object` (guards `.get()`/
  `None` callers). `suggested_tier` widened to `(float, float)` (render coerces via `_num`).

### Notes
- **Zero new RUNTIME dependency.** `TypedDict` is stdlib (3.8+) and runtime-INVISIBLE (a
  TypedDict *is* a plain dict — no runtime cost, the model can still author the record as JSON
  mid-flight). mypy is a **dev-only** maintainer tool: a committed pragmatic `mypy.ini` at the
  repo root (outside `plugins/`, so it never ships) keeps `scripts/` + `tests/` clean WITHOUT
  `--strict` and WITHOUT disabling the TypedDict checks; it is NOT in the dep-free `smoke.py`
  gate. `.mypy_cache/` is gitignored.
- **The static win is producer-asymmetric** (framed honestly): strong on the seed/demo literals
  + cross-module type agreement, near-zero on render's `.get()` reads (those rely on the runtime
  validator + IDE hints).
- Backward-compatible: legacy cycle records still render byte-identically; the validator is
  warn-only and additive; runtime behavior is unchanged → **patch**.

## [0.1.5] — 2026-06-17

### Added
- **Phase-0 detection of slug-orphans + schema drift (detect / report / OFFER only).**
  `memory_status.py` now flags **slug-orphans** — a near-duplicate sibling slug under
  `~/.claude/projects/` (the rename-orphan signature, since a dir rename changes the slug
  and strands the old slug-scoped store), detected by `near_duplicate_slugs` (norm on
  `-`/`_`/case, excluding the slug itself, since `slug_for` is lossy) — and **schema
  drift**: a fact missing the documented `node_type`, a malformed `scope`/`originSessionId`,
  or an index↔file mismatch (`schema_drift` + `drift_findings`). Both are surfaced in the
  Phase-0 report + the cycle-record `health` block + the dashboard, and reconciliation /
  backfill is **offered**, never auto-applied (the model decides in Phase 4).
- **`--pull` warns on a canonical missing a valid `originSessionId`** — before replicating
  a `user-global`/`stack-general` canonical, `sync_global.py --pull` emits a stderr WARNING
  that the gap fans out to every mirror, and **still replicates** (warn, don't block).

### Notes
- **Detection only — no auto-mutation.** Phase 0 never merges, deletes, or backfills a
  store; it detects, reports, and offers. The `_frontmatter` parser was promoted to
  `memory_status.py` (the dependency root) and `sync_global.py` now imports it (single
  definition), gaining CRLF/BOM tolerance.
- **Absence is an advisory, not drift.** `scope`/`originSessionId` are skill-/Claude-Code-
  injected and store-dependent, so their mere absence is reported only as an optional
  backfill advisory (a separate line that may appear on an otherwise-clean store), never a
  drift finding.
- Backward-compatible: legacy cycle records (no `health.slug_orphans`/`schema_drift`) render
  byte-identically; the new keys + detection + warning are additive → **patch**.

## [0.1.4] — 2026-06-17

### Added
- **Realized-rigor capture + cycle-record persistence (the band-calibration apparatus).**
  The cycle record gains `rigor.applied` (the ceremony actually run) and
  `rigor.override_reason`; `render_dashboard.py --persist DIR` appends each rendered record
  (one JSON line) to `<store>/.consolidation-log.jsonl`, idempotently — so a project accrues
  magnitude→(applied, outcome) data a future band calibration can refit against. The
  *suggested* tier stays DERIVED at render (no-drift); `applied` is a stored decision, not
  derivable from magnitude.

### Changed
- **Dashboard `RIGOR` line** shows `suggested → applied · why` when the model overrode the
  magnitude-derived tier (and just the suggested tier otherwise — legacy records render
  unchanged).

### Notes
- **Bands `(2,7)` are KEPT, deliberately, as a coarse HINT — not recalibrated.** A
  sensitivity probe found magnitude agrees with a rich needed-rigor rubric on only ~half of
  passes: the deciding features (always-loaded-bound count, conflicts, prune-pressure) are
  LATE-known, so an EARLY magnitude proxy can't be precision-tuned (`prune_pressure` + the
  2-source rule cover the blind spots). `INDEX_TOKEN_BUDGET` is the binding prune lever
  (~20–27 real facts); `PRUNE_PRESSURE_FACTS` is a terse-pointer backstop.
- **Honest scope of the apparatus:** `applied` is **self-reported** — it catches OVER-rigor,
  not under-rigor; calibrating the dangerous (under-rigor) direction needs LONGITUDINAL
  miss-detection (a later pass finds what an earlier one missed), which the persisted log
  enables but which is future work. Never calibrate bands against the OUTCOME banner —
  mature passes are systematically high-magnitude/low-outcome, so it fails UNSAFE.
- Backward-compatible: legacy v0.1.3 cycle records (no `applied`) render unchanged; the new
  field + flag + log are additive.

## [0.1.3] — 2026-06-16

### Added
- **Pass-tier rigor modes.** `memory_status.py` computes a deterministic, testable
  **suggested rigor tier** (LIGHT / SUBSTANTIAL / HEAVY) from an early *flow* magnitude —
  `git_commits + curated session_candidates` — so ceremony scales with the pass: LIGHT
  verifies inline; SUBSTANTIAL fans out parallel verification + a 2-source check for any
  always-loaded-tier fact + the re-verify/GC sweep; HEAVY adds a completeness critic + a
  hard stop on an over-budget always-loaded write without an explicit prune. It is a HINT
  (the model finalizes it in Phase 2 and may override with rationale). New pure functions
  `suggested_tier()` / `prune_pressure()` + a `rigor` block in the cycle record (seed ↔
  SKILL schema ↔ renderer updated together).
- **Prune-pressure flag.** Set when the always-loaded index is over budget OR the store
  already holds ≥ a threshold of facts — forces prune-or-propose regardless of tier. This
  is the axis the cumulative *stock* (`memories_reviewed`) drives, kept deliberately
  separate from the magnitude tier.

### Changed
- **Dashboard** gains a `RIGOR` line (tier · phase · magnitude, plus a prune-pressure ⚠
  when set); **both the tier and the magnitude are derived from `scope`** at render, never
  stored — so the displayed tier can't drift from its own magnitude (the way `_outcome`
  derives from `entries`). The rigor tier (an input-side effort estimate) is a distinct
  quantity from the write-based outcome banner — a pass can read HEAVY rigor yet LIGHT outcome.

### Notes
- The magnitude is **flow, not stock**: `memories_reviewed` is excluded from the tier (a
  cumulative count would peg every mature project to HEAVY — confirmed against the live
  corpus). `session_candidates` is the **curated** candidate-fact count, not the raw
  extractor `surfaced`. The band cutoffs are **provisional, tunable defaults**, not yet
  empirically calibrated (the curated input was never recorded historically). The record
  exposes the magnitude + `phase` a future calibration could refit against — but cycle
  records aren't persisted yet (they render and are discarded), so persisting them is the
  prerequisite (roadmap).

## [0.1.2] — 2026-06-16

### Added
- **Network token attribution.** `sync_global.py --tokens` + the dashboard now report
  `mirror_index_tokens` — the share of each node's always-loaded index driven by
  replicated `global_ref:` cross-project mirrors — so a mirror-dominated over-budget
  index points at the right lever (demote/GC the canonical in the global store, not a
  futile local prune that just re-pulls).
- **User-global `CLAUDE.md` observability.** `memory_status.py` measures
  `~/.claude/CLAUDE.md` **read-only** and the dashboard shows it as a distinct
  "every project · read-only" line, so the per-session always-loaded cost isn't
  understated. The skill never writes that file.
- **`render_dashboard.py --demo`** — paste-free preview of the dashboard from a
  built-in sample record.
- **Auto-gated ANSI color** in the dashboard: on only when stdout is a TTY and
  `NO_COLOR` is unset (`--color=auto|always|never`); captured/piped output stays plain.

### Changed
- **Dashboard redesign** for readability: one coherent column grid, budget bars,
  UPPERCASE section anchors, dimmed in-row field labels (color only), self-labelling
  name-forward Changes rows (a skipped entry reads `· skipped <name>` — no stray `—`),
  and bracketed citations.
- **`CLAUDE.md` guest posture.** The skill defaults to *not* writing the project
  `CLAUDE.md` — facts route to auto-memory or `AGENTS.md`/`MEMORY.md`; only a genuine
  always-loaded *convention* earns a surgical, in-style line; never create or
  reorganize one; propose (don't perform) trims of user-authored lines. The user-global
  `~/.claude/CLAUDE.md` is strictly read-only.

### Fixed
- **Recall-tier accuracy.** Removed the claim (SKILL.md, harness-map.md, README.md)
  that fact bodies are auto-surfaced by `description:` match — Claude Code has no such
  ambient recall; bodies are read on-demand. Reframed: the `description:` is the
  always-loaded **index hook** that cues an on-demand read. Design unchanged
  (description-as-recall-key still correct; it *is* the hook).
- **Render hardening.** The dashboard now coerces every *model-authored* cycle-record
  value (`_num`/`_clean`) at the network + changes presentation boundary, matching the
  budget rows — a string/`null` numeric or wrong-typed `tier`/`store` can no longer
  crash `render()`. Schema block (`SKILL.md`) updated in lockstep with the seed +
  renderer (`budget.global_claude_md`, `network.*.mirror_index_tokens`).

## [0.1.1] — 2026-06-16

### Added
- `tests/validate_manifests.py` — zero-dependency manifest validator (schema, kebab-case
  names, relative source path, semver) usable anywhere Python runs (no `claude` CLI).

### Changed
- Release process: a local maintainer harness now cuts releases (version bump → validate
  → tag → GitHub Release). Updates reach users via the bumped `version` landing on `main`.
- The multi-agent DevSecOps pentest harness and its findings are now local-only
  maintainer artifacts (not published); `SECURITY.md` remains the public security record.

## [0.1.0] — 2026-06-16

First public release as a **Claude Code plugin**, distributed via a plugin marketplace.

### Added
- **Plugin packaging.** Installable with `/plugin marketplace add
  Zenetusken/consolidate-memory` + `/plugin install consolidate-memory@zenetusken-plugins`
  — no clone, no symlinks. Self-hosted marketplace (`.claude-plugin/marketplace.json`)
  with the plugin under `plugins/consolidate-memory/` (`.claude-plugin/plugin.json`).
  SKILL.md references its scripts via `${CLAUDE_PLUGIN_ROOT}`.
- **Network token observability.** `sync_global.py --tokens` + a dashboard
  "Neural network — token consumption (all nodes)" sub-section: per-node and total
  estimated (≈ chars/4) always-loaded + recall-pool token cost across the shared-memory
  network, plus what each cycle did in lifecycle terms on the triggering node.
- **Memory-lifecycle bounding.** Encoded always-loaded token budgets
  (`INDEX_TOKEN_BUDGET` / `CLAUDE_MD_TOKEN_BUDGET`) with an over-budget ⚠; orphan
  garbage collection (`sync_global.py --gc [--apply]`); index-pointer **upsert** so the
  always-loaded hook tracks the canonical; a re-verification signal for facts untouched
  since the marker.
- **DevSecOps security gate.** A reusable multi-agent white-hat pentest cycle (recon →
  parallel per-surface pentesters with loop-until-dry → 3-vote adversarial verification →
  severity-ranked go/no-go gate) gates each release. Final gate: PASS (0 High/Critical).
- `SECURITY.md` (threat model + enforced security properties + disclosure).

### Security
- Stdlib-only, no network, no `eval`/`exec`/`shell=True`; the only external process is
  read-only `git` invoked with a fixed argument list.
- **Argument-injection guard:** the commit SHA read from the on-disk state file is
  hex-validated before reaching `git` (`memory_status._valid_sha`).
- **Input bounding:** transcript turns are length-capped before regex classification
  (defense-in-depth); secrets firewall drops credential-shaped turns at retrieval.
- The personal `memory/` store is gitignored and excluded from the published plugin.

### Changed
- `install.sh` is now a **maintainer dev-install** (registers a local marketplace +
  installs the plugin) rather than a user-skill symlinker — the symlink model is retired
  because `${CLAUDE_PLUGIN_ROOT}` is only set when loading as a plugin.
- Docs (README, CLAUDE.md, harness-map) updated to the plugin layout.
