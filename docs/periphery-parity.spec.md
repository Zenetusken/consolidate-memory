# Periphery parity — the second copies of a rule the store already states

**Status:** design-of-record · **Cycle:** `fix/periphery-parity` · **Target:** v0.4.32 (patch)

## 1. Context

v0.4.31 fixed two classifiers in the store-honesty path that knew fewer fact shapes than
the store holds. Both defects had the same shape: **a local rule narrower than the rule the
store actually states.** This cycle is the same shape again, one layer out — in the
periphery, where a consumer re-derives a rule that already exists, canonically, elsewhere
in the same package.

The sites, one frame:

| site | re-derives | canonical statement it ignores |
| --- | --- | --- |
| `local_ingress._rebuild_plan` | "which stems are *placed*" | `memory_status.placed_fact_names` |
| `local_ingress._rebuild_plan` | the `](stem.md)` link anchor | `memory_status._LINK_RE` |
| `local_ingress._rebuild_plan` | **what an archive OWNS** | `index_admission.archive_index` (§2.6) |
| `memory_status.apply_demotion_justify` | the usage clock's `None` tolerance | `memory_status._justify_remaining` |

The two functional instances are **not** the same defect: the first produces a wrong plan
(and, on apply, an un-archiving), the second raises an uncaught `TypeError`. They share a
cause and a fix method — make the periphery call the canonical rule instead of restating it
— and that is why they ride one cycle.

The fourth row is the same frame one turn tighter, and it was found by adversarial review of
**this cycle's own first revision** (§2.6) rather than by the audit that opened the cycle. The
first fix borrowed the canonical enumerator and then asked it a *different question* than the
question the store's own archive writer asks. Nothing at the call site could show that: the
expression read as a call into a canonical rule, and its error cost pointed the other way. It
is listed in the frame rather than appended as a footnote because it is precisely the defect
the frame names — a consumer restating a rule the store already states — and because a cycle
about second copies that shipped a third one would be evidence against its own thesis.

The repo already named this rule: *"an invariant is only as strong as its weakest
enforcement site."* v0.4.30 applied it in the constructive direction at
`memory_status.store_local_index` — *"the repair is to remove the second site rather than
keep two sites in step by discipline."* This cycle is that repair, applied to the sites that
were never collected.

## 2. Root cause A — the rebuild re-adds what the archive removed

`cm local archive` relocates a pointer MEMORY.md → SHIPPED.md; the body stays. The archive
is the store's only durable eviction mechanism, and it is deliberate: the pointer moves to
an on-demand doc that is off the always-loaded budget.

`cm local rebuild-index` regenerates MEMORY.md **from the fact files on disk**. Because a
fact file does not record its own placement — placement is recorded *only* by which pointer
doc holds the pointer — the rebuild cannot learn from the file that a fact was archived. It
treats every store-root `*.md` except `MEMORY.md` and `SHIPPED.md` (skipped **by name**) as
a fact to index.

So the rebuild re-adds every archived fact's pointer to MEMORY.md, and the eviction is
silently undone.

### 2.1 Measured

On the live store, through the production entry point (`cm local rebuild-index --json`):

| | |
| --- | --- |
| archived facts (pointers in `SHIPPED.md`) | **2** — `calibration-baseline-2026-08-29`, `agents-md-created-and-drift-findings` |
| neither present in `MEMORY.md` | confirmed (`in_MEMORY=0` for both) |
| both present in the plan's `included` | **yes** |
| re-adds the rebuild would write | **2** |

The two relocations relieved **111 est tok** (56 + 55) and **0 durable** — the plan's own
figure, and the reason the escape is worth closing rather than recording.

### 2.2 The premise moved in v0.4.31 — this is why the cycle was re-derived

The earlier plan for this work recorded a constraint that is **no longer true**: *"The
tempting fix — feed `archive_docs` in — is a no-op, because `_is_archive_index_text` floors
at ≥3 links and the live `SHIPPED.md` has 2."* It also recorded the standing decision
*"The shared classifier must not be loosened."*

v0.4.31 overturned that decision **with the measurement that falsified it**, and
`_is_archive_index` now recognizes an archive of any size ≥1 pointer. `archive_docs`
therefore resolves correctly, and the fix this plan had to route around is available
directly. Both of the plan's statements are superseded and neither is repeated here.

This is the ordinary consequence of staging cycles: a later cycle's *premise* can be moved
by an earlier cycle's landing. §7 makes the re-derivation explicit rather than assumed.

### 2.3 The conservative direction

The rule chosen is deliberately the one that **cannot delete**:

```
archived = ⋃ { archive_index(text_of(doc))["targets"] : doc ∈ archive_docs } − index_fact_names(idxp)
```

Both names are real and greppable: `index_admission.archive_index` and
`memory_status.index_fact_names`.

That is: stems an archive's own **pointer lines** name **and** MEMORY.md does not. A stem in
both docs is a live pointer the operator has (for whatever reason) in both — the rebuild keeps
it. The rebuild may **decline to re-add** an archived pointer; it may never **remove** a live
one.

This matters because `would_remove_existing_pointers` is the plan's existing deletion
surface. The new rule must not add to it. Measured on the live store: the two sets are
disjoint today (both archived stems measure `in_MEMORY=0`), so the conservative form and
the aggressive form agree on every current input — the direction is chosen for the inputs
that do not exist yet, not to change today's plan.

§2.6 records how the first revision of this rule got its *left operand* wrong, and why the
error cost inverts between the two readings: an archive reading that is too **wide** de-indexes
live memory, while one that is too **narrow** merely re-adds a pointer the operator had
archived. Both halves are needed — the difference against the index keeps the rule from
deleting, and the archive's own entries keep it from mislabelling.

`placed_fact_names`' own docstring already states the rule the rebuild was violating:

> *Completing an arc relocates the pointer MEMORY.md → SHIPPED.md and keeps the body (the
> always-loaded index = the active set). That is not index↔file drift.*

### 2.4 The snapshot-pin consequence

`_rebuild_plan` pins every source hash, and the apply path builds the transaction's
`expected` map from `plan["snaps"]` plus the index. Today `SHIPPED.md` is excluded from the
glob by name and so is **never snapshot-pinned** — nothing reads it. Once the plan reads
its contents, its revision must be verified in the same transaction as everything else, or
the plan can be built against a `SHIPPED.md` the apply never saw. The archive doc therefore
enters `snaps` like any other source.

### 2.5 The second anchor

`_rebuild_plan` builds `existing_ptrs` with a hand-rolled per-line first-match scan
(`re.search(r"\]\(([^)]+)\.md\)", ln)`) rather than the package's `_LINK_RE`. On a line
carrying two pointers only the first is seen.

Measured on the live `MEMORY.md`: **0** lines carry more than one pointer, so the divergence
is inert today. It is fixed here anyway — it is the same defect (a second, narrower copy of
a canonical rule) in the same function, and leaving it would leave the next reader to
rediscover which of the two is authoritative.

### 2.6 What an archive OWNS — the regression this cycle's own first revision shipped

Found by adversarial review of `c45aa0f` (this branch's first revision), reproduced
independently, and fixed before the PR. It is the frame's fourth row, and it is why §2.3's
left operand reads the way it does.

The first revision computed that operand with `placed_fact_names(idxp, archive_paths)`, whose
archive half is `index_fact_names(adoc)` — **every `](stem.md)` match anywhere in the doc's
text**. That is the correct reading for the question `placed_fact_names` asks (*"is this stem
placed, so that its missing index pointer is not drift?"*), where leniency costs a suppressed
warning. It is the wrong reading for the question the rebuild asks (*"should I omit this pointer
from the always-loaded index?"*), where a false positive **de-indexes live memory** and labels
the omission an intentional eviction. Borrowing a canonical predicate while silently changing
the question is the one failure mode a call site cannot show: the expression reads as a call
into a canonical rule, so the defect is invisible exactly where a reviewer looks.

§2.2's premise is what made it reachable. v0.4.31 loosened `_is_archive_index_text` to
"frontmatter-less + ONE link", so **any** store-root prose `*.md` carrying one link is now an
archive — including a working-notes file nobody meant as one. Measured at `c45aa0f`, on stores
whose only drift is a fact whose pointer is missing from `MEMORY.md` (the rebuild's own repair
case, and the reason anyone runs it):

| fixture | `included` | `would_readd_archived_pointers` | rebuilt index |
| --- | --- | --- | --- |
| a prose doc that MENTIONS the fact in a sentence | `['other-live']` — the fact is dropped | `['only-fact']` — a `cm local archive` that never ran | keeps `other-live` |
| a prose doc whose link sits on its own list item | `['other-live']` — dropped | `['only-fact']` | keeps `other-live` |
| the prose doc is the store's only other file | `[]` | `['only-fact']` | **zero pointers, `ok: True`** |

Two harms in one measurement. The **plan** silently declines to repair the missing pointer it
exists to repair, and the **report** asserts an eviction the operator cannot check. The third
row is the fail-open case: nothing is written, nothing is reported as wrong, and the rebuilt
index is empty. (Pre-fix this failed **closed** — the prose doc was not an archive there, so it
reached `prepare_local_fact` and came back `invalid` with `ok: False`. A file that fails closed
cannot be silently swallowed, which is why the intermediate revision is the one worth pinning
and the pre-fix tree is not.)

**The fix is the narrow reading** — the archive's own pointer entries, which is what
`index_admission.archive_index(text)["targets"]` extracts. It is not a new rule: it is the exact
extraction `local_archive`'s write path gates its own admission on (`archive_index(future)`
→ `["admitted"]`), so the rebuild now asks the archive the same question the archive's writer
already enforces. **`targets` only; `admitted` is deliberately unread.** The cap and the syntax
check govern the archive's *write* path — an archive already on disk over its cap still records
real placements, and honouring a refusal on read would re-add exactly the pointers this rule
exists to leave out. That asymmetry is the same safe direction as `archived` itself: reading a
refusal as "no entries" can only re-add, never delete.

**Considered and declined: tightening `_is_archive_index_text` to a pointer-LINE rule.** Measured
on the live fleet (2026-09-14) — **437** store roots holding **546** store-root `*.md`, of which
**26** are `MEMORY.md` (every decision-reaching consumer guards those by name) and exactly **2**
are archives the rule calls one — and **0** verdict changes under the tightening. So it buys
nothing for any store that exists, and it is the deciding number: the §2.6 class has **no live
instance**; the fixtures are its whole evidence, which is why the repair is a class closure
rather than a repair of observed damage. The scan is re-derivable with the root globs in §7 and
one predicate swap.
It would still move a predicate with four consumers, three of which (`schema_drift`,
`ref_stems`, `remediation_triage`) ask a different question and are correctly lenient there. The
defect is joint — a lenient classifier is right for those three, and the rebuild wrongly read
leniency as ownership — so the fix belongs on the reading side, where it costs nothing to the
three. The framing matters: a shared predicate loosened for one consumer is not evidence that the
next consumer may assume the strict form.

**Two of the four measured figures do not survive re-derivation, and the cause is the
measurement, not the fleet.** Re-running the §7 snippet gave **444** roots and **547** docs a few
hours later, then **446** roots on the next run — while **26** `MEMORY.md`, **2** archives and the
**0** were identical every time. Three readings in one afternoon, one number climbing and three
holding, and the climbing one is the apparatus's: **416 of the 446 roots have a slug derived from a
`/tmp` path** — the slug is the path, so `-tmp-…` is proof rather than inference, and it means a
test or verification run minted that store (`/tmp/mx/*`, `/tmp/fm`, `/tmp/mut-*`; any script run
that touches a store creates `~/.claude/projects/<slug>/memory/`). **387 carry today's mtime**,
and the census rose by two *between two runs of this audit itself*. The one extra doc is a
concurrent live session writing a fact. So the figures divide cleanly: `stores` and `docs` are
inflated by whatever measures them, while **26**, **2** and the **zero** are properties that held
across every reading. The snippet prints its own empty-root count so this is visible rather than
inferred — **420 of 446** roots hold no `*.md` at all. The *zero* is what carries the argument;
the counts are dated, and a fleet census that cannot state its own drift is a number pretending to
be a measurement.

**Residual, recorded rather than papered over.** A store-root doc whose link is *formatted as a
pointer line* (`- [x](x.md) — hook`) stays indistinguishable from a real archive entry: that is
the exact text `_pointer` writes, so no rule separates them without also refusing a genuine
two-entry `SHIPPED.md` — the v0.4.31 regression this cycle exists to protect. The decline
therefore stands, and the plan **names the doc that claimed the placement**
(`would_readd_archived_sources`) instead of vouching for it. Measured on that fixture:
`{'list-claimed': ['prose-list.md']}`. This converts an unverifiable claim into a checkable one —
the operator can see *what* is asserting a `cm local archive` and judge whether it is an archive
at all. It is pinned as a residual (P11), not as a fix.

## 3. Root cause B — the usage clock's `None` reaches an `int()` call

`control_plane.count_probative_after` returns `None` **deliberately** when the registry DB
does not exist, and its comment records why: a `0` there *"minted a real int that the
sequence branch of `_justify_remaining` consumed as 'zero later probative windows' — a stamp
on a registry-less store then suppressed FOREVER."* `_justify_remaining` tolerates `None`.

`apply_demotion_justify` does not:

```python
if jseq is not None and callable(n_after_fn):
    n_after = int(n_after_fn(jseq))
```

`run_justify_demotion` supplies `n_after_fn=lambda s: count_probative_after(ctx, int(s))`,
so on a registry-less store this is `int(None)`.

### 3.1 Reproduced on the production entry point

An **unenrolled** store — a documented, supported state, not a malformed one:

| run | result |
| --- | --- |
| 1 | `ok=True` — stamps `{'sequence': 0, 'windows': 0, 'at': …, 'until': 5}` |
| 2 | **`TypeError: int() argument must be a string, a bytes-like object or a real number, not 'NoneType'`** |

The traceback runs through `run_justify_demotion` → `update_project_state` → `mutator` →
`apply_demotion_justify`, and is **not caught** by either of the function's handlers (which
catch `WriteRefused` and `OSError`). `control.sqlite` measures `exists = False` both before
and after every run: nothing mints the registry, so this is deterministic, not a race.

The trigger is the second invocation. The first *succeeds* and writes a stamp — which is
what makes this worse than a crash on a cold store: the store acquires a `demotion_justify`
entry, and every subsequent `--justify-demotion` on it dies.

### 3.2 Why the harness could not have seen it

`count_probative_after`'s `None` **return** is pinned (`smoke.py`'s *"cross-project audit:
count_probative_after is None (not 0) with no registry"*). The **consumer** branch is not,
and cannot be, in any test built on the standard fixture: the fixture's enrollment helper
calls `control_plane.connect`, which *mints* `control.sqlite`. Every test store therefore
has a registry, the helper can never return `None` there, and the branch is unreachable
**in the harness** while being the ordinary case **in production**.

This is the inverse of the usual coverage gap. The fixture is too *provisioned* to
reproduce the defect; the fix is a pin that builds a store the harness never builds.

## 4. Changes

| Site | Change |
| --- | --- |
| `local_ingress._rebuild_plan` | Discover archive docs (`_is_archive_index_text` — the TEXT rule, run on the snapshot's own bytes, which is what lets the classification and the revision pin share one read) among store-root `*.md`; snapshot-pin each into `snaps`; compute `archived` as the union of `index_admission.archive_index(text)["targets"]` over those docs, minus the index's own pointer set from that same snapshot (`existing_ptrs`, **not** a second read of `MEMORY.md` from disk), and exclude those stems from `included` (§2.3, §2.6). The discovery read is guarded: `read_snapshot` raises `WriteRefused` on an unreadable path, and an unguarded raise there aborts the command before the fact loop's own guard — which is where the store-scan convention lives — can run. |
| `local_ingress._rebuild_plan` | Build `existing_ptrs` with the canonical `_LINK_RE` over the index **snapshot's** bytes — the anchor is reused, the snapshot provenance is kept (§2.5). |
| `local_ingress.local_rebuild_index` | Report the prevented re-adds under `would_readd_archived_pointers`, so the undo direction is visible where the operator looks. |
| `local_ingress.local_rebuild_index` | Report **which doc** claimed each prevented re-add under `would_readd_archived_sources` (§2.6 residual): the stem list alone is a claim the operator cannot check, and a stray store-root doc is exactly what makes it false. |
| `memory_status.apply_demotion_justify` | Tolerate `None` from `n_after_fn`, mirroring `_justify_remaining`: the stamp is judged by the fallback, not crashed into. |
| `tests/smoke.py` | Pins for §2 (P1–P5), for §3 (P6, on a **registry-less** store — the fixture the suite does not otherwise build), for §2.6 (P8–P11, two of them on the fixture that is the regression), and the block pin extended from key names to scalar types (P7, §5). |
| `tests/docs_links.py` | A new `check_plugin_table`: each `plugins/*/.claude-plugin/plugin.json` must have an AGENTS.md table row whose Version cell equals its manifest — one pinned site, in the idiom of `check_badge` (§4 note below). |
| `tests/docs_links.py` | Correct the invariant-6 docstring, which claimed the currency sweep closed "the version-sweep class … so a doc can no longer advertise a superseded version" — measured false, with the counterexample in this file's own doc set. The replacement states the three structural blinds and what the check actually guarantees. |
| `tests/docs_links.py` | Correct `_CURRENCY`'s inline rationale: it cited the README shields URL as a bare-matcher mis-fire, but that URL is the one bare site a bare rule gets **right** — and `check_badge` pins it regardless. The rule stands; the example was wrong. |
| `AGENTS.md` | The plugin table's Version cell: `0.4.27` → `0.4.32`. It is a current-version claim that no matcher could see (no `v`, not the doc's first `\bvX.Y.Z\b`, and a table cell besides) — measured stale through four releases and, by mutation, **unpinned**: rewriting it to `9.9.9` left all five gates green. |
| `AGENTS.md` | The dev-loop comment claimed `1795 assertions` — stale by 157 (`1795` at v0.4.28, where it was still true; `1952` at v0.4.31), and stale by construction: no gate reads it, and it drifts on every check added. Replaced by a pointer to where the count actually lives (`tests/smoke.py`'s own census constant, printed on every run) rather than by a fresh number that would rot the same way. |
| `docs/index-usage-and-budget-ladder.spec.md` | Already corrected in v0.4.31 (the falsified ≥3 justification). Nothing left; recorded here so the plan's item is not silently dropped. |

**Not changed, deliberately.** `remediation_triage`, `placed_fact_names`, and
`index_fact_names` are untouched — this cycle consumes them, and §2.6 records why the fix could
not be a change to `placed_fact_names` or to the classifier it shares. `local_archive` is
untouched: the relocation is correct, and the defect is that its sibling did not honor it.

**Recorded, not changed — the archive size.** The plan carried this as a re-derivable
number. Re-deriving it cost three attempts, and the first two were wrong in a way worth
recording, because they inverted the conclusion:

| figure | plan (recorded earlier) | measured this cycle |
| --- | --- | --- |
| `dashboards/index.html` | 1,465,823 chars at 55 cycles | **1,514,984 chars / 1,527,070 bytes** |
| records the archive renders from | — | **56**, merged from three log paths (below) |
| embedded cycle payload | — | **1,301,208 chars → 85.9% of the file** |
| static shell | — | **213,776 chars → 14.1%** (`_load_template()`, the HTML plus its JS bundles) |
| extrapolation at `_ARCHIVE_CAP = 120` | ~3.2 MB (of the file) | **~2.79 MB of payload → ~3.0 MB of file** |

The payload is the dominant term, not the shell — and the closure is exact, which is what makes
the split comfortable to state: `_load_template()` is 213,791 chars, the `/*__CM_DATA__*/`
placeholder it replaces is 15, and 213,791 − 15 + 1,301,208 = **1,514,984**, the file byte for
byte. Two earlier attempts at this row are withdrawn. The first used
`len(_safe_embed(assemble_cycles({}, history)))` — a plausible-looking expression that measures
neither half: `assemble_cycles` returns a **`(cycles, total)` tuple**, not the dict the template
receives, and `history` was read from the **native log alone**. That combination yields 249,484
chars (deterministic — re-measured twice), a **5.2× understatement**: no `diffs` sidecars, no
`identity`, no `budgets`. Subtracting it
from the file size attributed the difference to a "static shell" of 1,265,506 chars, which
manufactured the ~83.5% and with it the claim that a file-size extrapolation models the shell
rather than the archive. **The plan's ~3.2 MB figure is therefore reinstated, not withdrawn** (a
pure file-size extrapolation gives 3.25 MB; the payload-plus-shell form gives 3.0 MB, and they
agree because the payload is 86% of the file). The encoder still has to be named — an unnamed
encoder is a number that cannot be re-derived — but naming the encoder is not enough: the
**object** it encodes has to be named too, and that is the error this row records.

## 5. Pins

1. **The rebuild does not re-add an archived pointer** — a fixture store whose only archived
   fact's pointer lives in `SHIPPED.md`: `local_rebuild_index` in plan mode excludes it from
   `included`, and the rebuilt index contains no pointer to it. Pre-fix: `included`
   contains it.
2. **GUARD — a live fact is still indexed** — a fact whose pointer is in `MEMORY.md` remains
   in `included`. Holds on both revisions: this is the control that proves pin 1 tests
   placement and not "fewer facts."
3. **GUARD — the conservative direction** — a fact whose pointer is in **both** `MEMORY.md`
   and the archive is **kept** in the rebuilt index. Holds on both revisions, and it is what
   pins the §2.3 choice: an aggressive rule would drop it and this check would catch that.
4. **The plan reports the prevented re-adds** — `would_readd_archived_pointers` names the
   archived stems. Pre-fix: the key does not exist.
5. **The archive enters `snaps`** — the plan's snapshot map contains `SHIPPED.md`. Pre-fix:
   absent. This is the transactional half of §2.4 and fails pre-fix for the same reason.
6. **The registry-less double run** — on an unenrolled store, `run_justify_demotion` twice:
   the second run returns rather than raising, and reports the stem as already-justified.
   Pre-fix: `TypeError`.
7. **GUARD, forward-verified — the SKILL↔TypedDict block pin, extended from key names to scalar
   types.** Calling it a pin would be false. The block pin previously compared **key sets** only,
   and extending it to scalar types cannot fail on pre-fix code — at HEAD the block and the
   TypedDicts agree, so a revert has nothing to fail against. *A documentation pin's evidence must
   be a **forward** mutation of the artifact it reads, not a reverse revert.* Measured forward:
   with the block corrupted to `"confirmed": "NOT-AN-INT"` against a `confirmed: int` annotation,
   the suite reported **1952 passed, 0 failed** on the revision of the harness that did not yet
   read scalars — the drift was invisible there. The extended check fails on that mutated block
   and passes on the real one, which is the evidence that makes it a check rather than a
   restatement. (mypy cannot see it by construction: its inputs are the `.py` sources and
   `SKILL.md` is not among them. `validate_cycle_record` checks container types, never a scalar,
   and never reads the block.)

   The rule's own reach had to be verified too, and the first draft of it was wrong in a way
   worth recording: a walker that descends only through `Optional[...]`/`dict[...]` wrappers
   visits **3** scalars in this block, because a directly `TypedDict`-typed key (the nested
   schema blocks) carries no `__args__` — the descent silently does nothing and reads as a pass.
   Using `typing.is_typeddict` as the discriminator, the walk visits **138**. A check whose
   coverage is an order of magnitude below what it claims is the same defect this cycle is
   about, so the census is stated here rather than left implicit.

8. **A prose MENTION cannot suppress a fact** (§2.6) — a store whose only drift is a missing
   pointer, which a stray store-root prose doc happens to link: the fact stays in `included` and
   in the rebuilt index. Fails on the **intermediate** revision `c45aa0f`, where it was absent
   from both. It passes pre-fix for a different reason — see P10 — which is why it is labelled a
   pin against the intermediate revision and not against pre-fix.
9. **The plan does not label that repair an intentional eviction** — `would_readd_archived_pointers`
   is empty. Fails on **both** earlier revisions (intermediate: `['mention-fact']`; pre-fix: the
   key does not exist).
10. **GUARD — the fixture exercises the NARROWING, not the fact-file path** — the shared rule
    classifies the prose doc as an archive, and the extraction the fix reads takes zero targets
    from it. Green on all three arms by design, and verified **forward** instead (§7): a guard
    whose red is unreachable by revert has no revert to fail against. Without it, a later
    classifier change would leave P8 green for a reason it does not name.
11. **The residual, and the evidence that replaces the vouch** — a store-root doc whose link is
    *formatted as a pointer line* (`- [x](x.md) — hook`) is indistinguishable from a real archive
    entry, so the stem stays declined (§2.6); the plan then **names the doc that claimed it**,
    `would_readd_archived_sources == {'list-claimed': ['prose-list.md']}`. Fails on both earlier
    revisions (pre-fix re-added the stem; neither had the key). This pin exists so that closing
    the residual turns a check red and forces §2.6 to be re-adjudicated rather than quietly
    outgrown — a recorded blind spot that is not pinned is a scheduled defect.

**Measured on the mutation matrix**, one arm per revision and one process per tree (§7):

| arm | result | which checks moved |
| --- | --- | --- |
| pre-fix (`1056dd1`) + this branch's harness | **1958 passed, 6 failed** | P1, P4, P5, P6, P9, P11 |
| intermediate (`c45aa0f`) + this branch's harness | **1960 passed, 4 failed** | P8, P9, P11, **P12** |
| intermediate (`5072833`) + this branch's harness | **1963 passed, 1 failed** | **P12** |
| fixed (this branch) | **1964 passed, 0 failed** | — |

P2, P3, P7, P10 and P12 are **guards** — green on the pre-fix arm. P9 and P11 are red on both
earlier revisions; P8 is red only on the first intermediate one, which is the revision it exists
for. **P12 is red only on the two intermediate revisions**, which is the pair that introduced the
unguarded read it guards: the guard was earned by review of the fix, not by the defect the fix
targets, so the last two arms exist to show it is not vacuous and not a pin.

(Numbering above is stable, not positional: P8–P11 were added after the review round that found
§2.6, and P1–P7 keep the numbers they were measured under in the revisions cited throughout.)

## 6. Risks

- **R1 — a false archive classification could strand a live fact, and §2.6 narrows that surface
  from a class to a shape.** Before the §2.6 repair the risk was open: the shared text rule
  classifies *any* frontmatter-less store-root `*.md` carrying one link as an archive, so a prose
  doc that merely mentioned a fact suppressed its pointer from the rebuilt index and the plan
  called that an intentional eviction. Measured on fixtures, and measured fleet-wide as a
  **0-verdict-change** scan under the repair (§7). What survives is narrower and structural: a
  doc whose link is *formatted as a pointer line* (`- [x](x.md) — hook`) is indistinguishable
  from a real archive entry, so it still declines its target — now with the claiming doc named in
  `would_readd_archived_sources` (pin 11) rather than vouched for. Three further things bound
  the residual: the rule only ever removes a pointer from a **rebuilt** index, never a live one;
  the rebuild is plan-first and confirm-gated; and the error cost is asymmetric by design — an
  archive read too *wide* de-indexes live memory (visible, named, recoverable by re-adding),
  while too *narrow* merely re-adds an archived pointer (§2.3). Pin 2 is the guard on the
  direction that matters; the plan-mode diff is the reviewable surface.
- **R2 — the conservative rule can still surprise, and the report key is part of the contract.**
  A fact whose pointer is only in the archive is *not* re-added even if the operator expected a
  full rebuild. That is the intended contract (the always-loaded index is the *active* set), and
  the new report key names it, but it is a behavior change for every store that has ever
  archived. The key is **additive** — `would_readd_archived_pointers` and
  `would_readd_archived_sources` join `included`/`future`/`would_remove_existing_pointers`
  rather than replacing one, so a consumer that reads only the old keys sees no change and the
  release stays a patch.
- **R3 — the `None` tolerance changes a suppression decision, and the fallback's verdict is not
  a single outcome.** Tolerating `None` means the documented fallback in `_justify_remaining` is
  used where the code previously raised `TypeError` through `run_justify_demotion`. The fallback
  is the *intended* one (it exists precisely so a registry-less store is not suppressed
  forever), so the direction is right — but the honest statement of the change is not
  "crash → already-justified". With `n_after_seq` absent, control falls to the `at`-based legacy
  arm: the stamp's own timestamp is compared against the window starts **that postdate it**, so
  the second run reads `already-justified` when none do (the common case, and what pin 6
  measures) and writes a **fresh stamp** when enough later windows have accrued. A sentence
  claiming one outcome would be false for the other arm; the CHANGELOG states it as "a crash
  becomes whatever the documented fallback judges".
- **R4 — extending the block pin to scalars could fail on a legitimate shorthand.** The
  block is documentation with example values (`'phase': 'provisional|final'`,
  `'<active session id>'`). Any scalar check must accept the `a|b` and `'<placeholder>'`
  forms the block deliberately uses, or it will fail on the real tree. The check is written
  against the real block first and the mutated one second.
- **R5 — the new plugin-table gate can fail on a legitimate restructure.** `check_plugin_table`
  reads `AGENTS.md`'s second cell as a version claim, so reordering that table's columns, moving
  the table to another file, or adding a row for a plugin that does not exist yet each turn the
  gate red — all of them correct-by-intent edits. That is the accepted cost of closing an
  **unpinned** current-version site: at v0.4.31 the cell read `0.4.27` on a `0.4.32` tree and
  every gate was green, and a mutation to `9.9.9` was green too (§7). The gate fails *loudly and
  locally* with the file, line, stated value and manifest value, so the fix is a one-line edit;
  the alternative is a drift nothing can see. Its vacuity guard (`no manifests → error`) exists
  for the same reason — a check whose subject vanished must fail rather than shrink to nothing.
- **R6 — a stray frontmatter-less store-root doc is now ABSORBED, and no report key names it.**
  This is the one behavior change the cycle introduced that is *not* about archived pointers, and
  it is the flip side of the classification rule: a doc the shared text rule calls an archive is
  skipped by the fact loop before `prepare_local_fact` can refuse it. Pre-fix such a doc reached
  that call and came back `invalid`, which made the command **fail closed** and put the doc in
  front of the operator; post-fix it appears in no report bucket at all (`invalid`, `unreadable`,
  `omitted` and `would_readd_archived_*` are each silent, and it claims no stem) — so a rebuild
  that previously refused can now report `ok`. **Measured blast radius: none today** — a fleet
  scan finds 2 archives and both are `SHIPPED.md` carrying pointer lines, so the absorbed count is
  0 live. Recorded rather than fixed because the honest fix is a new report key
  (`archive_docs`, naming the docs classified as archives), and a report-contract addition needs
  its own pin and its own arm re-derivation. The §2.3 residual is the same shape seen from the
  other side: a doc whose link is *formatted as a pointer line* is structurally indistinguishable
  from a real archive, which is why the plan names the claiming doc on the decline path — this
  risk is that the *classification* path has no such naming.

## 7. Verification

**The gate set, on this branch's revision (all five green):**

```bash
python3 tests/smoke.py                      # 1964 passed, 0 failed
python3 tests/simulate_accumulation.py
python3 tests/docs_links.py                 # ✓ … 2 plugin-table rows …
python3 tests/validate_manifests.py         # ✓ manifests valid (consolidate-memory v0.4.32)
mypy --config-file mypy.ini                 # Success: no issues found in 42 source files
```

**Mutation-verify — three arms, one process per tree, one harness.** Each arm is a
`git archive <sha> | tar -x` extraction with **this branch's `tests/smoke.py` copied over it**,
so the only variable is the code under test. Never `git worktree add`: its commondir resolves the
main project identity and breaks the hermetic-`HOME` fixture. All four arms below were run with
the harness at `sha256 3e144293…` — the same file in every arm, verified by hash after copying,
because a stale overlay is invisible in a count. The counts belong to that triple; re-derive them
if the harness changes.

| arm | result | which checks moved |
| --- | --- | --- |
| pre-fix (`1056dd1`) | **1958 passed, 6 failed** | P1, P4, P5, P6, P9, P11 |
| intermediate (`c45aa0f`) | **1960 passed, 4 failed** | P8, P9, P11, P12 |
| intermediate (`5072833`) | **1963 passed, 1 failed** | P12 |
| fixed (this branch) | **1964 passed, 0 failed** | — |

P2, P3, P7, P10 and P12 are **guards** — green on the pre-fix arm by design. P9 and P11 are red on
both earlier revisions; P8 is red only on the first intermediate one, which is the revision it
exists for. The multi-arm shape is the point: **a single-arm matrix would have certified §2.6's
regression as a fix**, because P8 is green pre-fix for a reason that has nothing to do with the rule
under test (§5, P8/P9). The `5072833` arm earns its row the same way in the other direction — it
isolates the unguarded discovery read as the *only* thing left wrong at that revision, so P12's red
is attributable rather than incidental.

All four arms run the **same** harness: `tests/smoke.py` sha256 `f10d258c6b65bc8743bbd5e0e51fbab0c983975b222878bfe66c08225a2e25e1`,
verified identical in the working tree and every extracted arm before the runs.

**A guard has no revert to fail against, so its premise is verified forward.** Two arms:

| forward mutation | result | what it shows |
| --- | --- | --- |
| `_is_archive_index_text`'s floor restored to `>= 3` (`/tmp/fm`) | **1952 passed, 11 failed**: C1, C1b, C2, C3, C4, C7, P1, P4, P5, **P10**, P11 | P10 is load-bearing: it names the fixture's dependence on the classified-as-archive premise, and P8 stays **green** under this mutation — exactly the blindness P10 exists to catch |
| the `SKILL.md` schema block corrupted to `"confirmed": "NOT-AN-INT"` | **1952 passed, 0 failed** on the pre-scalar harness | the block pin's drift was invisible before this cycle; the extended check is red on the mutated block and green on the real one |
| `AGENTS.md`'s table cell, four ways (`0.4.27` / `9.9.9` / `not-a-version` / row deleted) | **rc 1, exactly one error line each** | each arm fails **only** on the new check; the unmutated control arm is green (rc 0), so the harness is faithful and the gate is not red for an unrelated reason. `9.9.9` is the one that matters — it was **green before this cycle**, so that cell moved from UNPINNED to PINNED |

(1952 is not a coincidence: it is this suite minus the eleven P8–P11 checks, i.e. the total the
block-pin arm was measured on before they existed.)

**Every figure this spec states is re-derived on this branch's revision** (2026-09-14), one tree
per process wherever two trees are compared — except the two it labels as **plan testimony** where
they appear (§2.1's `0 durable`, and §4's `plan (recorded earlier)` column): those have no artifact
to re-derive from, and the label is the honest form of that, not an exemption from the rule.
Rows that depend on the code under test were re-taken after the **last** code edit, not carried
across it — a count belongs to the triple of restored code, fixture and harness, so the
archived-discovery guard and the `existing_ptrs` operand were both in place when the mutation
matrix and the end-to-end rows below were measured. (The two fleet rows and the archive rows do
not read the changed function; they are dated where they appear.)

| figure | value | how |
| --- | --- | --- |
| registry-less run 1 / run 2 | `ok`, then `TypeError` | `/tmp/justify_probe.py`, hermetic HOME |
| `control.sqlite` after both runs | absent | same probe |
| scalars visited by the block pin | 138 (3 under the naive walker) | instrumented walk |
| fleet stores / store-root docs | 437 / 546 as first measured, **446 / 547 on re-run — the root count climbs every time an arm runs** (416 of 446 slugged from a `/tmp` path, 420 empty; §2.6) | the two root globs below, which now print the empty-root count |
| archives among them | 2 non-`MEMORY.md` | `_is_archive_index_text` per doc |
| verdict changes under the declined tightening | **0** | the same scan, pointer-line predicate swapped in |
| bare-matcher first picks | 6 docs: `CLAUDE.md`→`1.0.0`, `AGENTS.md`→`0.4.32`, `README.md`→`0.4.32`, `SKILL.md`→`127.0.0`, `harness-map.md`→none, `docs/1.0-preflight.spec.md`→`1.0.0` | `(?<!v)\d+\.\d+\.\d+`, first match per `LIVE_DOCS` entry |
| multi-pointer lines in live `MEMORY.md` | 0 | `_LINK_RE`-equivalent scan |
| live archive | 1,514,984 chars / 1,527,070 bytes | direct read of `dashboards/index.html` |
| records the archive renders from | **56** | `ms.iter_store_cycle_log` → `retention.cycle_log_read_paths`: **three** logs, not one |
| embedded cycle payload | 1,301,208 chars (85.9%) | `len(_safe_embed(d))` where `d` is the dict the template receives — **not** `assemble_cycles`' `(cycles, total)` tuple |
| static shell | 213,776 chars (14.1%) | `_load_template()`, minus the 15-char placeholder — the file closes exactly |
| payload at the 120-cycle cap | ≈2.79 MB of payload / ~3.0 MB of file | 23,236 × `_ARCHIVE_CAP`, plus the shell |
| live facts the firewall refuses | 3 (`ok: false`) | unrelated to this cycle; why the live plan is a refusal |

The archive rows are **recorded, not changed** — the plan's decision for this site. The record
count is the row that hid the error: `.consolidation-log.jsonl` holds **30** records and is the
*native legacy* source only, while `iter_store_cycle_log` merges **three** paths — that legacy
file (30), the plugin-data log keyed by slug (4), and the plugin-data log keyed by project id
`p_<hash>` (22) — for **56**, the number the archive actually embeds. Reading the first path and
calling it the source is what made the payload look small: the missing 26 records carry the
`diffs`, `identity` and `budgets` blocks, and a 5× understatement of the payload became a 6×
overstatement of the shell. Two method notes stand: the payload is measured with
`render_html._safe_embed`, the function that actually writes it (`json.dumps` defaults differ by
~2.2%, compact separators by ~3.0% the other way — an unnamed encoder is a number that cannot be
re-derived), and the **object** encoded must be named alongside the encoder, since measuring the
wrong one is how this row went wrong twice. (An earlier draft carried `1,465,823 chars at 55
cycles` from the planning document; the live file re-derives at `1,514,984` chars. The stale one
is dropped rather than reconciled — a number belonging to a measurement nobody can re-run is
testimony, and this spec carries only the re-derivable ones.)

The bare-matcher row is the reason the new plugin-table check exists: **four of those six picks
are not the document's current version** (two are not versions at all — `1.0.0` is the versioning
policy's example, `127.0.0` is a loopback address), which is the measured basis for §6 R5 and for
`docs_links.py`'s rewritten invariant 6. The six are stated as picks rather than paraphrased,
because a "blind spot" claim with no probe is the same unverifiable shape this cycle is about.

**The premise re-derivation (§2.2) is itself the cycle's discipline check.** The earlier
plan asserted a constraint that v0.4.31 removed. Carrying a superseded premise into a spec
is the same defect class as a spec that keeps asserting a superseded decision — which is
exactly what v0.4.31 had to correct in the budget-ladder spec. This cycle checks its own
premise against the tree rather than against the plan that proposed it.

**End-to-end — the live store, through the production entry point** (`cm local rebuild-index
--project <repo>`, not the private helper), pre-fix vs fixed. The fix's rows come from `--json`;
`future` and `snaps` are **not** in the CLI report (`snaps` holds `FileSnapshot` objects), so the
pointer counts and the `snaps` row come from `_rebuild_plan` in a one-tree probe, which is why
each is stated rather than left to read as a CLI figure:

| figure | pre-fix | fixed |
| --- | --- | --- |
| `included` | 33 (both archived stems present) | 31 |
| rebuilt index pointers (`future`) | 35 | 33 |
| archived pointer in the rebuilt index | yes, both | neither |
| `would_readd_archived_pointers` | key absent | 2 |
| `would_readd_archived_sources` | key absent | `{…'agents-md-created-and-drift-findings': ['SHIPPED.md'], 'calibration-baseline-2026-08-29': ['SHIPPED.md']}` |
| `would_remove_existing_pointers` | 2 | 2 (unchanged) |
| archive doc in `snaps` | absent (39 entries) | present (40 entries) |

`would_remove` is unchanged in both directions — the rule operates on the *candidate* set, so it
can only decline to re-add. That asymmetry is the whole safety argument of §2.3, and it is
measured rather than asserted. The live plan's `ok` is `false` on **both** revisions for a reason
that predates this cycle (three facts the retrieval firewall refuses), which is why the end-to-end
is measured in plan mode: it never writes, and the placement figures are still reported.

```bash
# The fleet scan behind §2.6 — re-runnable as written, but only TWO of its figures are stable.
# `stores` and `docs` grow every time a verification arm runs (each mints a store dir) and every
# time another session writes a fact, so the `empty` count is printed beside them: it is the
# number that moves, and seeing it move is how a reader knows the census is apparatus-inflated.
# Readings on 2026-09-14: 437 / 546 / 26 / 2 / 0, then 444 / 547 / 26 / 2 / 0, then
# 446 / 547 / 26 / 2 / 0 with 420 of 446 roots empty and 416 slugged from a /tmp path, then — on
# the revision this spec ships from — 483 / 547 / 26 / 2 / 0 with 457 of 483 empty. Only 26, 2 and
# 0 held across all four; `docs` settled at 547, and `stores`/`empty` moved together by 37, which
# is this cycle's own review arms. NOTE the denominators differ by scope, not by error: this scan
# globs the global domain store as well, so a scan over `~/.claude/projects/*/memory` alone
# legitimately reports fewer roots and fewer docs.
# The bare-matcher row above is one `(?<!v)\d+\.\d+\.\d+` search per LIVE_DOCS entry
# (tests/docs_links.py), and the archive row one `len(index_html.read_text())`.
python3 - <<'PY'
import glob, sys
from pathlib import Path
sys.path.insert(0, "plugins/consolidate-memory/scripts")
import memory_status as ms
roots = [Path(d) for pat in ("~/.claude/projects/*/memory",
                             "~/.claude/consolidate-memory/domains/*",
                             "~/.claude/consolidate-memory/domains/*/*",
                             "~/.claude/memory")
         for d in glob.glob(str(Path(pat).expanduser())) if Path(d).is_dir()]
docs = [f for r in roots for f in sorted(r.glob("*.md"))]
mem = [f for f in docs if f.name == "MEMORY.md"]
empty = [r for r in roots if not any(r.glob("*.md"))]
print("stores", len(roots), "| of which empty", len(empty),
      "| docs", len(docs), "| MEMORY.md", len(mem),
      "| archives", sum(ms._is_archive_index_text(f.read_text(encoding="utf-8", errors="replace"))
                          for f in docs if f.name != "MEMORY.md"))
PY
```
