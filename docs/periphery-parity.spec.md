# Periphery parity — the second copies of a rule the store already states

**Status:** design-of-record · **Cycle:** `fix/periphery-parity` · **Target:** v0.4.32 (patch)

## 1. Context

v0.4.31 fixed two classifiers in the store-honesty path that knew fewer fact shapes than
the store holds. Both defects had the same shape: **a local rule narrower than the rule the
store actually states.** This cycle is the same shape again, one layer out — in the
periphery, where a consumer re-derives a rule that already exists, canonically, elsewhere
in the same package.

Two instances, one frame:

| site | re-derives | canonical statement it ignores |
| --- | --- | --- |
| `local_ingress._rebuild_plan` | "which stems are *placed*" | `memory_status.placed_fact_names` |
| `local_ingress._rebuild_plan` | the `](stem.md)` link anchor | `memory_status._LINK_RE` |
| `memory_status.apply_demotion_justify` | the usage clock's `None` tolerance | `memory_status._justify_remaining` |

The two functional instances are **not** the same defect: the first produces a wrong plan
(and, on apply, an un-archiving), the second raises an uncaught `TypeError`. They share a
cause and a fix method — make the periphery call the canonical rule instead of restating it
— and that is why they ride one cycle.

The repo already named this rule: *"an invariant is only as strong as its weakest
enforcement site."* v0.4.30 applied it in the constructive direction at
`memory_status.store_local_index` — *"the repair is to remove the second site rather than
keep two sites in step by discipline."* This cycle is that repair, applied to three sites
that were never collected.

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
archived = placed_fact_names(idxp, archive_docs) - index_fact_names(idxp)
```

That is: stems the archive places **and** MEMORY.md does not. A stem in both docs is a live
pointer the operator has (for whatever reason) in both — the rebuild keeps it. The rebuild
may **decline to re-add** an archived pointer; it may never **remove** a live one.

This matters because `would_remove_existing_pointers` is the plan's existing deletion
surface. The new rule must not add to it. Measured on the live store: the two sets are
disjoint today (both archived stems measure `in_MEMORY=0`), so the conservative form and
the aggressive form agree on every current input — the direction is chosen for the inputs
that do not exist yet, not to change today's plan.

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
| `local_ingress._rebuild_plan` | Discover archive docs (`_is_archive_index`) among store-root `*.md`; snapshot-pin each into `snaps`; compute `archived = placed_fact_names(idxp, archive_docs) - index_fact_names(idxp)` and exclude those stems from `included`. |
| `local_ingress._rebuild_plan` | Build `existing_ptrs` with the canonical `_LINK_RE` over the index **snapshot's** bytes — the anchor is reused, the snapshot provenance is kept (§2.5). |
| `local_ingress.local_rebuild_index` | Report the prevented re-adds under `would_readd_archived_pointers`, so the undo direction is visible where the operator looks. |
| `memory_status.apply_demotion_justify` | Tolerate `None` from `n_after_fn`, mirroring `_justify_remaining`: the stamp is judged by the fallback, not crashed into. |
| `tests/smoke.py` | A pin for §3 built on a **registry-less** store (the fixture the suite does not otherwise build), and a pin for §2. |
| `tests/smoke.py` | Extend the SKILL↔TypedDict block pin from key names to scalar types (§5, and see the note there on why this one cannot be a revert-pin). |
| `docs/index-usage-and-budget-ladder.spec.md` | Already corrected in v0.4.31 (the falsified ≥3 justification). Nothing left; recorded here so the plan's item is not silently dropped. |

**Not changed, deliberately.** `remediation_triage`, `placed_fact_names`, and
`index_fact_names` are untouched — this cycle consumes them. `local_archive` is untouched:
the relocation is correct, and the defect is that its sibling did not honor it.

**Recorded, not changed — the archive size.** The plan carried this as a re-derivable
number. It was re-derived and **did not reproduce**:

| figure | plan (recorded earlier) | measured this cycle |
| --- | --- | --- |
| `dashboards/index.html` | 1,465,823 chars at 55 cycles | **1,514,984 chars / 1,527,070 bytes at 30 embedded cycles** |
| embedded cycle payload (via `assemble_cycles`) | — | 253,020 bytes → **8,434 bytes/cycle** |
| extrapolation | ~3.2 MB at the cap | **~1.01 MB of embedded payload at `_ARCHIVE_CAP = 120`** |

More chars at *fewer* cycles contradicts the recorded per-cycle-growth premise: the
embedded cycle payload is ~17% of the file, so the static shell dominates, and the cap
bounds a payload an order of magnitude smaller than the file. Both readings are recorded;
the ~3.2 MB extrapolation is withdrawn rather than carried, since it does not follow from
either measurement. **Nothing is changed** — the cap already bounds growth, and this is a
documentation correction.

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

**Measured on the mutation matrix** (§7): pins 1, 4, 5 and 6 fail on pre-fix code. Pins 2, 3
and 7 are guards — they hold on both revisions.

**Pin 7 is a different kind of check, and calling it a pin would be false.** The
SKILL↔TypedDict block pin previously compared **key sets** only. Extending it to scalar types
cannot fail on pre-fix code — at HEAD the block and the TypedDicts agree, so a revert has
nothing to fail against. *A documentation pin's evidence must be a **forward** mutation of
the artifact it reads, not a reverse revert.* Measured forward: with the block corrupted to
`"confirmed": "NOT-AN-INT"` against a `confirmed: int` annotation, the suite reports
**1952 passed, 0 failed** — the drift was invisible at v0.4.31. The extended check fails on
that mutated block and passes on the real one, which is the evidence that makes it a check
rather than a restatement. (mypy cannot see it by construction: its inputs are the `.py`
sources and `SKILL.md` is not among them. `validate_cycle_record` checks container types,
never a scalar, and never reads the block.)

The rule's own reach had to be verified too, and the first draft of it was wrong in a way
worth recording: a walker that descends only through `Optional[...]`/`dict[...]` wrappers
visits **3** scalars in this block, because a directly `TypedDict`-typed key (the nested
schema blocks) carries no `__args__` — the descent silently does nothing and reads as a pass.
Using `typing.is_typeddict` as the discriminator, the walk visits **138**. A check whose
coverage is an order of magnitude below what it claims is the same defect this cycle is
about, so the census is stated here rather than left implicit.

## 6. Risks

- **R1 — a false archive classification could strand a live fact.** The rule reads
  `_is_archive_index`, whose own risk surface v0.4.31 measured (a floor of 1 pointer, five
  files fleet-wide change verdict, every decision-reaching consumer guards `MEMORY.md` by
  name). Here the blast radius is smaller in one direction and larger in another: the rule
  only ever *removes* a pointer from a **rebuilt** index, never from a live one, and the
  rebuild is plan-first and confirm-gated. But a store-root pointer doc that is not an
  archive would now suppress its targets from the rebuilt index. Pin 2 is the guard; the
  plan-mode diff is the reviewable surface.
- **R2 — the conservative rule can still surprise.** A fact whose pointer is only in the
  archive is *not* re-added even if the operator expected a full rebuild. That is the
  intended contract (the always-loaded index is the *active* set), and the new report key
  names it, but it is a behavior change for every store that has ever archived.
- **R3 — the `None` tolerance changes a suppression decision.** Tolerating `None` means the
  fallback path in `_justify_remaining` is used where the code previously crashed. The
  fallback is the *documented* one (it exists precisely so a registry-less store is not
  suppressed forever), so this is a return to the intended behavior — but the second run's
  verdict on a registry-less store changes from "crash" to "already-justified", which is a
  real behavior change and is stated in the CHANGELOG.
- **R4 — extending the block pin to scalars could fail on a legitimate shorthand.** The
  block is documentation with example values (`'phase': 'provisional|final'`,
  `'<active session id>'`). Any scalar check must accept the `a|b` and `'<placeholder>'`
  forms the block deliberately uses, or it will fail on the real tree. The check is written
  against the real block first and the mutated one second.

## 7. Verification

```bash
python3 tests/smoke.py
python3 tests/simulate_accumulation.py
python3 tests/docs_links.py
python3 tests/validate_manifests.py
mypy --config-file mypy.ini
```

**Mutation-verify — measured, one tree per process** (the two trees are never imported into
the same interpreter; `git archive HEAD | tar -x` extracts the pre-fix tree, and never
`git worktree add`, whose commondir resolves the main project identity and breaks the
hermetic-HOME fixture):

| tree | result | which checks moved |
| --- | --- | --- |
| pre-fix (`1056dd1`) + this branch's harness | **1955 passed, 4 failed** | exactly pins 1, 4, 5, 6 |
| fixed (this branch) | **1959 passed, 0 failed** | — |
| guards 2, 3, 7 | green on **both** | deliberately: a guard is a control, not a pin |

Pin 7 is verified **forward** (§5) because no revert can fail it. Counts belong to
the triple (restored code, fixture, harness) and are re-derived on the fixed revision,
never carried.

**Every number in this spec was re-derived on this branch's revision**, one tree per
process where two trees are compared:

| figure | value | how |
| --- | --- | --- |
| live re-adds | 2 | `cm local rebuild-index --json` (production entry point) |
| archived stems absent from MEMORY.md | 2 of 2 | direct read of both docs |
| multi-pointer lines in live `MEMORY.md` | 0 | `_LINK_RE`-equivalent scan |
| registry-less run 1 / run 2 | `ok`, then `TypeError` | `/tmp/justify_probe.py`, hermetic HOME |
| `control.sqlite` after both runs | absent | same probe |
| corrupted-block suite result | 1952 passed, 0 failed | scratch tree, `git archive` extraction |
| scalars visited by the block pin | 138 (was 3 with the naive walker) | instrumented walk |
| suite, pre-fix tree | 1955 passed, 4 failed | `git archive HEAD` extraction, one process |
| suite, fixed tree | 1959 passed, 0 failed | `python3 tests/smoke.py` |
| archive chars / embedded payload | 1,514,984 / 253,020 at 30 cycles | direct read + `assemble_cycles` |

**The premise re-derivation (§2.2) is itself the cycle's discipline check.** The earlier
plan asserted a constraint that v0.4.31 removed. Carrying a superseded premise into a spec
is the same defect class as a spec that keeps asserting a superseded decision — which is
exactly what v0.4.31 had to correct in the budget-ladder spec. This cycle checks its own
premise against the tree rather than against the plan that proposed it.

**End-to-end — measured on the live store through the production entry point**
(`cm local rebuild-index`, not the private helper), pre-fix vs fixed:

| figure | pre-fix | fixed |
| --- | --- | --- |
| `included` | 33 (both archived stems present) | 31 |
| rebuilt index pointers | 35 | 33 |
| archived pointer in the rebuilt index | yes, both | neither |
| `would_readd_archived_pointers` | key absent | 2 |
| `would_remove_existing_pointers` | 2 | 2 (unchanged) |
| `SHIPPED.md` in `snaps` | absent | present (39 → 40 entries) |

`would_remove` is unchanged in both directions — the rule operates on the *candidate* set,
so it can only decline to re-add. That asymmetry is the whole safety argument of §2.3, and
it is measured rather than asserted.
