# Identity from the input — design-of-record

**Status: implementation complete — every file this spec names has landed, and the pins are sourced.**
Base revision
`fbfe07e` (main @ v0.4.35). Every `file:line` below stays `fbfe07e`-numbered per the reading note below
(**How to read the citations**), so a coordinate that no longer resolves on the working tree is
**expected**, and a
script-side claim in this document is now a claim about **two** revisions at once. **Landed:**
`store_context.py` (+20 / −4 — the constant form and `mem_dir_source`; behaviour-neutral, measured
0 differences in 420 comparisons over 60 environment cells), `render_html.py` (the resolver, the four
refusal arms, and identity lifted out of `except Exception: pass`), `control_plane.py`
(`rows_for_store` + the full 8-column set), `render_dashboard.py` (RC-5c's second site, with the
marker-then-cwd order extracted into `_context_for_store` so it has one home), `SKILL.md` (the
shipped invocation now names its subject twice), and `tests/smoke.py` (**59 checks**: **34 measured
red on `fbfe07e`** — 33 `(PIN` plus one stated PRECONDITION exception — and 25 green on both,
**10 GUARD, 14 PRECONDITION, 1 CONTROL and not one PIN**, labelled as such in the check's own text;
both runs and the split are at *The measurement* below). ⚠ **The count and the red total moved at four
separate points after the first measurement** — the first from self-review rather than from a reviewer
(the Arm A
path fault and the two checks pinning the existence test's *position*, below), the next three from
later rounds closing their own findings. The count, the red total and the D6 constant all moved with
them, which is why they were re-measured rather than incremented, and why the superseded figures are
named at *The measurement* rather than deleted. The one thing this document anticipated as a **decision** but not as an
**implementation obligation**: `absent`'s routing to Arm A is settled below, but deciding it is not
the same as securing it — see the *two faults, one representation* paragraph under *The five refusal
arms*.
Target release **v0.4.36** (patch: additive — the shipped paths keep working; one hand-invocation
shape gains a refusal). F2's second half (RC-6, the prose-with-no-carrier families) is chartered
separately.

**Provenance.** The approved plan `~/.claude/plans/concurrent-enchanting-bengio.md` split the v0.4.35
audit's remaining tail into two PRs; this is **PR A = RC-5**. F1 (`docs/refusal-verdict-parity.spec.md`,
v0.4.35) closed the data-integrity half of one root cause — *a surface re-derives meaning from a label
instead of from the data that produced it*. This closes the half it left.

**The class.** **An assertion takes its source from something other than its subject.** `render_html`
renders a store handed to it as an **input**, and stamps that archive with an identity read from the
**process's cwd**. The archive's subject is the store; the masthead asks the room.

The invariant is narrower than "never read cwd", and the difference is the whole finding:

> **A defect exists when the subject is named by one argument and the identity is read from another.**
> A surface that defaults *both* to cwd is coherent — it names its subject and reads its identity from
> that same place. `memory_status [dir]` (`memory_status.py:4934`) and `build_context` (`:3032`) do
> exactly that, and are **correct**; `render_log` (`render_log.py:86`) resolves a store for *location*
> and takes its displayed project from **that store's records** (`:99`; its non-record fallback is
> `store.parent.name` — still the subject, not the room) — also correct.

> **Scope of the claim.** Measured by census of the union matcher `\.cwd\(\)|getcwd\(\)` over
> `plugins/consolidate-memory/scripts/*.py` — **eleven sites in seven files**. ⚠ **The matcher must be
> receiver-agnostic, and this is the trap the census was written through once already.** `Path.cwd()`
> finds six of the eleven and silently misses `render_dashboard.py`'s three, which are spelled
> `_P.cwd()` against an aliased import (`from pathlib import Path as _P`, `:602`, `:1517`, `:1934` —
> the file aliases `Path` a fourth time at `:1905`, which binds no cwd site): a
> `Path.`-prefixed pattern is a hypothesis about a *binding*, not about a *call*. The eleven, each
> with what it is: **six** pair cwd with a subject named by that same fallback —
> `extract_signals.py:833`, `distill_scan.py:585`, `sync_global.py:5255`, `memory_status.py:4934`,
> and `session_beacon.py:87` and `:292` (the last two written `os.getcwd()`, reachable only through
> the beacon's stdin payload); **three** are `render_dashboard.py`'s — `:619` and `:1544` are the
> **guard-admitted** candidates that are this spec's source 3, and `:1936` is the warn, RC-5c's
> second site rather than an identity read; `sync_global.py:2664` is the near-miss recorded under
> *Adjacent, not in scope*; and one is the defect, `render_html.py:413`. So the precise claim is:
> **`render_html.py:413` is the only site where an argument names the subject and cwd supplies the
> identity** — not "the only incoherent site". The list is exhaustive rather than illustrative, so a
> reader can check the claim from it instead of taking it.

**Rule of engagement.** Every behavioral fix lands with a check that **FAILS on the pre-fix code**,
and its RED count is measured on the triple (restored code, fixture, harness) at implementation time
— never asserted from this document. A check that cannot fail on pre-fix code is a **regression
guard**, and is labelled one.

**The measurement, stated so it can be re-run rather than believed.** **2129 passed / 37 failed** with
the branch's `tests/smoke.py` against a `fbfe07e` tree, and **2166 passed / 0 failed** against the
branch — *the same total on both*, which is what makes the two runs comparable
and what the D6 constant independently attests. Reproduce with
`git archive fbfe07e | tar -x -C <dir> && cp tests/smoke.py <dir>/tests/ && python3 <dir>/tests/smoke.py`.
⚠ **The count belongs to the triple and was re-measured when the triple moved**, not carried: the
resolver was reshaped once during implementation (see *The five refusal arms*) and once more at
self-review (see *A fault that wore the wrong name*), a third time when the adversarial round's two
findings were closed (see *Round 3 — the two holes my own pins left*), and a fourth when the
`/code-review` round's were (see *Round 4*), and each edit changes the
restored code — a count measured before any of them describes a revision that no longer exists. The
superseded figures, newest first, are **46 checks, 2127·23 vs 2150·0**, **42 checks, 2126·20 vs
2146·0** (the state the F3 mutation
reading was taken against — `2146 passed / 0 failed`), **36 checks, 2121·19 vs 2140·0**, and
**31 checks, 2118·17 vs 2135·0**; the base side of each pair is by subtraction, because the total is
identical on both trees by construction — one harness file, two trees. They are named here rather
than deleted, because deleting them would hide that the triple
moved — and the current figure is the one to trust, since it is the only one that describes the code
that ships.
⚠ **And the labels are load-bearing rather than decorative — the run separates them.** Of the **34**
failures on the base tree, **33** carry `(PIN` in their own label, and the thirty-fourth is the one
**stated exception**: pin 19's PRECONDITION, which fails there *because it asserts the fixture* —
`mem_dir_source` is a field this change introduces, so on `fbfe07e` the fixture cannot even be
established. That is a red that pins nothing, and the label says so rather than letting a reader
totalling the split count it among the pins. **Not one** GUARD or CONTROL failed on either tree.
⚠ **`(PIN`, not `(PIN)` — the matcher is part of the number, and the literal undercounts by half.**
The label has three spellings and all three are PINs: `(PIN)` × 17, `(PIN, site 1 of 2)` × 5, and
`(PIN — …)` × 11, the em-dash form being the one round 4's pins use. Grepping the bare literal
returns **17 of 33** — which is this document's own subject committed by a census that never named
its matcher, and the reason the count is stated over the matcher rather than over the word.
**Invariant, and the reason the split is an identity rather than a summary:** all **25** checks green
on both trees are labelled GUARD (10), PRECONDITION (14) or CONTROL (1) — **zero PINs**. Every check
that can flip does, and every check that does not is labelled as one that cannot. So
the taxonomy asserted here is the taxonomy the suite enforces; a reader who doubts the split can read
it off the failures instead of counting the greys. ⚠ **The increment is the sharp form of the same
evidence:** a round that had added a check which could not discriminate would have shown a smaller
increment than its check count — which is the one way to tell a pin from a ceremony. It has held at
every round: round 1 added 2 checks and moved the red set by 2 (`17 → 19`); round 2 added 6 and moved
it by **1**; round 3 added 4 and moved it by **3**, the missing one being pin 18's GUARD, which is
regression cover for a rule that already held and so has no red to contribute.

**How to read the citations.** Every `file:line` below is **`fbfe07e`-numbered** — and *only*
`fbfe07e`-numbered: the branch tree and the base tree do **not** agree, because most of these
coordinates address the **pre-fix** code this spec's own fix replaces. MEASURED, over the citations
testable on both trees — **124** of them; the other 36 are excluded because their basename resolves to
**two** files on the live tree, one of them the canary-v0.1.19 vendored copy — **38 agree in line
content and 86 differ**. So resolve
against the base commit — `git show fbfe07e:<file> | sed -n '<N>p'` — and **never against the branch
tree**. A coordinate that does not resolve on the branch is **expected**; one that does not resolve on
`fbfe07e` is a defect in this document.

⚠ This note used to add *"and the tree at that revision is clean, so live coordinates and cited
coordinates agree today"*. The clause is deleted rather than qualified, because the measurement above
is what it needed and the measurement refutes it: the premise was about the **base** revision's
worktree and the conclusion was about the **branch**, and the two are different subjects. It also
contradicted the sentence three words later, which forbids resolving against the branch precisely
because it has moved. **One clean tree at the base implies nothing about the branch** — that is this
document's own family, in this document's own reading note.

**Quoting wrapped source.** A phrase that spans a source line break is not greppable contiguously
(`wrapped-phrase-is-not-greppable`). Where a quote below spans a break it is written with **`⏎`**
marking the break, and the quote is **not** claimed to be a single contiguous string. Material
**omitted** from a quote is marked **`…`** — the two marks are not interchangeable, since `⏎` asserts
that a break is *in* the source and `…` asserts that something was *cut*. Quotes are
**byte-faithful**: no markup is added *inside* quotation marks, so an identifier the prose backticks
is not backticked inside a quote unless the source is.

## Corrections to the approved plan

The plan was re-measured while writing this spec. Each entry below is a **plan position that
re-measurement changed** — a claim falsified, a risk closed, or an omission found. Only the first kind
is a contradiction, and appearing here is not itself evidence of one. This section is itself correction
prose, so it was re-audited independently after the first review round — see *Corrections to this
spec*, which follows.

1. **`tests/smoke.py:7579` is not a `render_html` site.** It is the `--store` argument line of a
   `run_beta.py` invocation (the beta-tester oracle: `--store` is declared at
   `plugins/dream-beta-tester/scripts/run_beta.py:609`). Dropped from the affected list.
2. **The two store constructors were never at risk of diverging.** `project_memory_dir` is a one-line
   delegate — `return resolve_store(project_dir).native_memory_dir` (`memory_status.py:2736-2737`).
   There is one authority, so no comparison is needed.
3. **`render_log.py` is not a sibling defect.** It resolves a store for *location* only
   (`render_log.py:86`) and takes its displayed project from that store's records (`:99`). Not in
   scope; left alone.
4. **The contract was missing an ambiguity arm.** `native_memory_dir` has **no `UNIQUE` constraint**
   (the `projects` table declares only `project_id TEXT PRIMARY KEY`, `control_plane.py:28`; the sole
   index is `sqlite_autoindex_projects_1`, the PK), so "exactly one owner" is emergent, not enforced.
   Added as **Arm B**.
5. **The registry-fault arm needs no new machinery.** `classify_registry` already computes the
   distinction into `ctx.registry_state` (`store_context.py:1025`); the design reads it rather than
   re-deriving it.
6. **RC-5c has a second site, so the plan's `render_html.py:415` was a census claim rather than a
   pointer.** `render_dashboard.py:1936` warns with the **cwd's** context on the `--persist` path,
   twenty lines below `:1917` handing the same function the subject it was told to persist — the same
   shape, the same one-line repair, and on the dream's **terminal `--persist`** rather than the
   archive path. Now in scope; see §Scope's census, which counts the warn's call sites (9) rather than
   cwd reads, because the latter is not a population that terminates at the offenders.
7. **PR A's file list is five, not the plan's three.** Beyond `render_html.py`, `control_plane.py` and
   `SKILL.md`: `store_context.py` (expose `mem_dir_source`, and lift `:926`'s containment tuple to a
   shared `PROJECT_LOCAL_SCOPES` — **no change to resolution**)
   and, from entry 6, `render_dashboard.py` (one line). Recorded explicitly so a reviewer diffing the
   branch against the plan does not read two unlisted files as scope creep; neither alters a
   resolution order, a CLI surface, or a rendered field.

## Corrections to this spec

An independent verification round found three claims **this document** made that are false. They are
recorded here because a design-of-record that silently inherits a wrong number is the defect class
this cycle exists to fix — and because two of the three were introduced *by this section*, while
claiming to correct the plan.

1. **The `:3245`/`:3249` "correction" was itself inverted — the plan was right.** `:3246` and `:3250`
   **are** the `_run54("render_html.py", …)` invocations; `:3245` is an `_out54 = …` assignment and
   `:3249` is the tail of the multi-line `check(...)` opening at `:3247`. The first draft of this
   spec asserted the opposite and must not be re-introduced.
2. **The census is `21` occurrences over `18` lines — neither is "nineteen".** A draft of this spec
   said "nineteen" and attributed a "four `native_memory_dir` mentions" figure to the plan; **the plan
   contains neither** (0 hits for "four"; its three `native_memory_dir` mentions are the `SKILL.md`
   quote and the `iter_registered_projects` note, none of them a census). So "nineteen" was this
   document's own error, not a correction of anything. Measured on `fbfe07e`:
   `grep -o … | wc -l` → 21, `grep -c` → 18. **The count is stated with its matcher and nothing
   more** — an earlier draft also classified the sites ("two of them reads"), and an independent
   census disputed the classification by enumerating nine sites the list omitted. That is the same
   matcher-dependence this project already records, so the classification is **dropped** rather than
   re-derived: the count is a grep result, and the design does not depend on the sites' kinds.
3. **"The one new function … has no equivalent" is false.** The lookup already exists as
   `retention.py:64 _project_id_for_native`. See *Design* — it is the precedent this design most
   needed to cite, and the reason it must not be reused.
4. **The first `_project_derived` was wrong, and wrong in this document's own defect class.** As
   written it was a **denylist over routes with a default of admission** — `store-override` out,
   `autoMemoryDirectory` scoped, everything else `return True` — which *admits routes that do not
   exist yet*, and a third constant assignment was already there: `CLAUDE_CODE_PROJECT_DIR_NAME`
   (`store_context.py:861-865`, `:920-922`) makes `default_native` a function of the environment, since
   `project_slot = slot_env or default_slot` discards the root-derived slot the moment the variable is
   set. The round-trip went vacuous for it exactly as for the two named routes, and the predicate
   admitted it — **RC-5's output produced inside the gate built to prevent it**, with a check that
   appears to have checked. The section above now inverts the enumeration, which fails
   closed over **names** — the value axis stays open and is pin 10's, per §Design's ⚠ — pin 10 carries
   the third instance as a fixture, and the two shared names are constants. The
   asymmetry is the finding: the `a-complete-guard-inverts-its-question` form **was** applied — to
   `mem_dir_source` — and not to the field the vacuity property actually lives in.

### Round 2 — the resolve-raise class, and four claims this change made about itself

A second verification round produced ten findings. Six are recorded here; the others are recorded **as
refutations**, because a ledger that logs only its hits teaches the next reader nothing about its
misses.

5. **A stored value that cannot be RESOLVED was resolved anyway — three defects, one line each, in two
   files.** `Path.resolve()` raises `ValueError: embedded null byte` on a NUL, and `ValueError` is
   neither `OSError` nor `sqlite3.Error`, so it escaped both files' deliberate guards as an **uncaught
   traceback**:
   - **`render_html.py`**'s candidate loop held `c = _rs(cand)` **outside** the marker parse's own
     `except`, so a marker carrying an escaped NUL — `json.loads` **accepts** the escape
     and decodes it to a raw `U+0000`, so the file
     PARSES while the resolve raises — did not degrade to source 3 as its comment promised. It took
     the render down from **every** cwd. Measured: the same store renders rc 0 with no marker, exit 1
     with a NUL in one.
   - **`control_plane.rows_for_store`** resolved **every** row and ran **first**, so one corrupt row
     took down every `--store` invocation rather than only its own — broader than the marker vector,
     which is why this repair belongs in `control_plane` and not at the call site.
   - **And the relative-value arm, sharpest because it needs no corruption at all:**
     `Path(raw).resolve()` on a RELATIVE stored value anchors the match to the **process cwd**, so
     which row the lookup returns — and so the identity the archive wears — depends on where the
     render ran. Measured on one registry, one `--store`, two cwds: a store owned by charlie was
     stamped with atlas's identity. **RC-5 reproduced inside RC-5's repair.** `native_memory_dir` is
     written ABSOLUTE by `store_context`, so the anchor was never the right one; the fix is
     absolute-only plus a skip.
   All three now guard `(OSError, ValueError)` specifically. `except Exception` was **rejected**: a
   fault and an absence sharing one representation is RC-1's exact mechanism. ⚠ **And this class was
   already anticipated in this tree** — the usage-window site catches
   `(OSError, ValueError, TypeError)` — so it is pre-existing in-tree evidence that the guard was
   known, and simply not applied where the same `resolve_store` call appears.
6. **The three-way measurement, because a repair's own pin can be green for the repair's reason.**
   The count that matters is the RED count per tree, which belongs to the triple (restored code,
   fixture, harness) and is never carried across an edit:

   | tree | passed | failed | which |
   |---|---|---|---|
   | pre-fix `fbfe07e` | 2126 | 20 | 20 pins incl. 17; **15/16 green** — the base never reads the marker or the registry there |
   | pre-repair (both repairs textually reverted) | 2143 | **3** | **exactly 15, 16, 17** |
   | repaired | 2146 | 0 | — |

   Every one of the 20 pre-fix failures carries `(PIN)`; **zero** GUARD, CONTROL or PRECONDITION
   failed. The label taxonomy is enforced by the run rather than asserted — and it is why 15 and 16
   are labelled GUARD, not PIN: by this repo's own rule a check added by a fix that cannot fail on
   pre-fix code is a **regression guard**.
7. **The `slug_for` collision finding is REFUTED, and the refutation is the useful half.** `slug_for`
   is non-injective, so `<src>/foo-bar` and `<src>/foo/bar` do collide onto one store — measured,
   confirmed. But the claim built on it, that the collision returns the ambient cwd to the driver's
   seat, is false: **sources 1 and 2 name the STORE**, so they are cwd-invariant by construction, and
   only source 3 can vary with cwd. Measured from all three cwds with a row naming the store:
   `example/True` from every one. The collision is a pre-existing `slug_for` property, **not** an
   RC-5 regression.
8. **A third copy of the order stood inside the docstring claiming it had one home.**
   `_context_for_store` said *"One question, one home: a second copy of this order is a second place
   RC-5 can be reintroduced"* — while the usage-window clock, 960 lines below in the same file, still
   resolved its own pair (cwd first, the marker as fallback, plus a skip branch neither caller here
   needs). The docstring now scopes the claim to **the unenrolled-share warn's copy** — the copy the
   extraction was actually for — and names the third site as deliberately left alone.
9. **`--project "$(pwd)"` does not mean what its own sentence said.** SKILL.md claimed the two flags
   agree *"by construction"*. Measured: `--project "$(pwd)"` renders **byte-identical output to no
   `--project` at all** in both agreeing cells — because `$(pwd)` IS the cwd the fallback already
   uses, so it adds no name, only the **check** — and the pair **disagrees for a non-git project
   rendered from a subdirectory** (rc 1, `is not the store for`), where the honest fix is to run from
   the project root rather than the printed remedy. The flag **is** load-bearing, for exactly the
   reason the paragraph was reaching for: with a `--store` from another project the new form refuses
   *naming the pair*, while the old form's refusal misdiagnoses it (`belongs to no registered
   project — pass --project`). The paragraph now says that, tautology included.
10. **Five coordinates in §Design's RC-5 passage named the right claim and the wrong line.** Found by
    reading every bare `:N` in the section against `fbfe07e`. The note at `:89-94` promises that a
    coordinate which fails to resolve is a defect — but **all five resolve**; they address a
    neighbouring line, which is the same distinction PR B's Family 4 turns on.

    | cited | claim | actually at `fbfe07e` | correct |
    |---|---|---|---|
    | `store_context.py:662-664` | the docstring forbidding the phantom call | `grant_covers`/`_path_contained` | `:1035-1036` |
    | `:604` | "reads the marker's `project_path`" | the marker *file* read | `:606` |
    | `:619` | "applies the ownership guard" | the *resolution* | `:620` |
    | `:1544` | "applies the ownership guard" | the *resolution* | `:1545` |
    | `:1540-1543` | "carries the comment" | `return "io-error"` | `:1546-1549` |

    `:619` and `:1544` are **one line early in the same direction** — the passage points at each
    `cwd → store` *resolution* and calls it the guard — while its own `:612-620` range (verified
    correct) shows the author knew the guard sits on the `if`. The quoted premise **wraps across the
    comment's first two lines** and so greps to 0; it is now carried by the anchor `v0.4.0 review
    (R128 clock liveness)`. And *"eight lines above the call it gets right"* is unverifiable —
    nothing is eight lines above `:1936` — so it was cut rather than restated. **Verified clean in
    the same pass**, so the census has a stated extent: `:612-620`, `:1936`, the six refusal-idiom
    sites, the whole `store_context.py` group, `cm_ops.py:304`/`:554`, `smoke.py:11576-11580`.

### Round 3 — the two holes my own pins left

An adversarial round raised eleven findings. **Two are defects in the change; the rest are defects in
this document and are corrected in place above.** The two are recorded here because they are the
sharper kind: neither is a bug in the repair, and both are **holes in the pins written to protect
it** — a check that cannot fail is not cover, however carefully it is worded.

1. **The truncated install had no pin, and the import was the one thing left unwrapped.**
   `render_html.py` guards three shipping-class dependencies that live in the same directory, and its
   own comment states the rule for them — a truncated install *"must degrade with the same one-line
   message, **never a traceback**"*. `:604-606` holds the template; `:609-623` holds the bundles; and
   `:626-627` held the **unwrapped** `from store_context import …`, whose neighbours' rule it did not
   follow. **Measured, three states:** on `fbfe07e` the removal renders at **rc=0 with empty stderr**
   — the blanket `except Exception: pass` RC-5a removed turned a fault into an absence and shipped an
   empty masthead; with that catch gone it raised an **uncaught `ModuleNotFoundError`**, a traceback;
   post-repair it degrades with the siblings' own one line. Only `ImportError` is caught, for the
   reason `_load_template`'s `ValueError` arm already records — a fault *inside* `store_context` is
   not a truncated install and must not wear that remedy. **Pin 18 is two checks, and they carry
   different labels because they read differently on the two trees:** the template and both bundles
   are **GUARDs** (green on both, so they pin nothing this change did), and `store_context` is the
   **PIN**. The three guard cells are not ceremony — a rule pinned only where it broke is pinned by
   an enumeration the author wrote, which is the trap this file's own pin block names.
2. **The managed-policy route was driven by nothing, and a one-line edit re-opened RC-5.**
   `_merge_settings` applies **four** settings scopes — `user`, `project`, `local`, `policy` — and
   pin 10 drove three. `policy` (`managed-settings.json`) is the one whose own docstring says it
   **may name an explicit absolute dir**, i.e. exactly the constant `_project_derived`'s second
   conjunct exists to refuse; it is also the highest-precedence scope, so it redirects *every*
   project. **Measured against a surgical mutation** (widening `_project_derived` to admit
   `mem_dir_source == "policy"`): the whole suite stays green — **2146 passed, 0 failed** — while the
   end-to-end cell renders again at **rc=0 wearing the ROOM's identity** (`domain_id: unknown`,
   `enrolled: false`, `cross_project_allowed: false`) on a store whose own project is enrolled
   `personal`; the unmutated control refuses with Arm A. **Pin 19 is the instance, not a table over
   the predicate's constant, and the reason is the finding's own shape:** a predicate edited to admit
   a *name* is caught only by a check that *drives* that name — the `return False` under every branch
   is reached by names the author never listed and by nothing else. The constant-level slip (adding
   `"policy"` to `PROJECT_LOCAL_SCOPES`) *is* red, but **collaterally**: its single failure is
   `review-1`'s containment check, which reads the *other* site that constant feeds, not this
   predicate — so a suite that happened to catch it was never testing it.

**Two lessons, both about pins rather than about code.** First, the fixture is part of the pin, and
its first draft here was wrong in a way that would have made the pin **vacuous**: it let the subject's
own registry row name the rendered store, so source 1 admitted the store ungated, `_project_derived`
was never consulted, and the cell rendered the *correct* identity **on the unmutated tree** — a green
check pinning nothing. It was caught by running the control first. Second, a precondition that
*raises* is not a reading: on the base tree, `mem_dir_source` does not exist, so an attribute access
took the entire suite down at the precondition and swallowed every reading after it, including that
pin's own. A precondition's job is to report that its fixture is not what it needs. **It is now red
on `fbfe07e` for exactly that reason, and its label says so** — otherwise a reader totalling the
two-tree split would count it among the pins.

### Round 4 — the arm nothing pinned, and three surfaces that read one class differently

The `/code-review` round on this change raised findings against the *restored* tree. The pins that
moved are recorded here. **One finding changed the contract — the fifth arm, above — and it is
recorded there as an addition rather than as a realisation of the plan;** the rest are pins, labels
and one shared-helper extraction, none of which alters what `render_html` promises a caller.

1. **Arm B was pinned by nothing, and no ledger in this document could have shown it.**
   `_ARM36_B` — the anchor for *"a `--store` claimed by ≥2 rows"* — occurred **once** in the whole
   harness: in the pin written to close the gap. **Before this round no pin drove B at all** — the
   arms with cover were A, C and D, and E gained its the moment it existed (pin 21). The reason the gap
   survived three review rounds is structural: the table above is a ledger of **anchors** (does this
   phrase occur in the shipped tree?), and *"is this arm exercised by a check?"* is a different
   ledger, over the harness instead of over `plugins/`. A document that keeps one and reads it as the
   other will certify coverage it never measured. Pin 24 closes it, and its **precondition is counted
   in SQL rather than by calling the function under test** — `rows_for_store` does not exist on
   `fbfe07e`, so a precondition phrased as `len(rows_for_store(...)) == 2` raises `AttributeError`
   inside a `with` block and takes the whole suite down, swallowing every reading after it. That is
   round 3's own lesson arriving a second time, in a new file position.
2. **The `resolve()` raise set is version-dependent, and the matrix was measured rather than assumed.**
   `safe_resolve`'s guard admits `(OSError, ValueError, RuntimeError)`, and no one of the three is
   redundant:

   | input | 3.10 / 3.11 / 3.12 | 3.13 |
   |---|---|---|
   | symlink loop | `RuntimeError` | **does not raise** — returns the loop path itself, whose `exists()` is `False` |
   | embedded NUL | `ValueError` | `ValueError` |
   | deleted cwd | `FileNotFoundError` | `FileNotFoundError` |

   Measured directly on four interpreters, one process each, on the revision that ships
   (`3.10.12` / `3.11.15` / `3.12.13` / `3.13.15`); the **3.8 and 3.9 columns are the CI matrix's
   claim, not a local reading**, since neither is installed here — stated because the difference
   between *"measured"* and *"the matrix says so"* is the whole subject of this document.

   The 3.13 row is the one that justifies a guard the earlier versions cannot exercise: **a fix for a
   version that does not raise is not dead code, it is the only thing standing between a loop path and
   a silent admission.** And the loop cell is where the class is visible at all — on 3.13 it arrives as
   a *value* (`exists()` false) that a naive `!=` files as "not the one", which is the same
   `fault ≡ absence` collapse the fifth arm exists to prevent, reached by a different door.
3. **One classification, three surfaces, two kinds of value — and the pin had to pick the right
   comparator.** The registry's classification is rendered in three places: `identity_snapshot`
   (`store_context.py:109-132`, the archive payload), `doctor_report` via `_registry_state_line`, and
   `render_html`'s Arm C. The first carries a **bare token** — deliberately, because the HTML template
   branches on it, and branches on it by **equality against the token**, in three distinct spellings:
   `id.registry_state!=="healthy"&&id.registry_state!=="absent"` (`dashboard.template.html:1070`),
   `rs!=="absent"&&rs!=="healthy"` (`:1085`), and — as the third, which is the one an equality-shaped
   grep misses — `rs==="healthy"||rs===""` (`:1043`), where the **empty string is admitted alongside
   `healthy`**. Any of the three is falsified by a value carrying `: err`. And
   `memory_status.py` types it as the closed set `absent | healthy | locked | corrupt |
   permission-denied | incompatible`. The other two carry a **sentence**: `state`, or `state: err`. So
   *"Arm C's string equals the snapshot's"* is false by design, and a pin written that way would have
   indicted correct code. Pin 25 therefore compares Arm C against **`doctor_report`** — the surface
   that shares its kind — and asserts three things at once: exactly one `registry_state:` line, that
   it is **not** the bare token, and that the sentence appears inside Arm C's stderr.
4. **And the reason two surfaces had to be compared at all is that they held two copies of one
   format.** `_registry_state_line` and Arm C each spelled `state: err` themselves. They are now one
   function, `store_context.registry_state_text`, with the two callers kept — which is the repair this
   repo's own v0.4.32 release is entirely about (*"two periphery sites each kept a SECOND copy of a
   rule the store already states canonically"*). The pin is what makes the extraction worth doing: an
   extraction with no shared assertion is a refactor, and the two spellings describe **one** condition,
   so a reword in either would leave a reader holding two sentences for one fault.
   ⚠ **The extraction is at two sites and the class is at three**, and the third is deliberately not
   folded in: the snapshot's bare token is consumed by a *branch*, not by a reader, and giving it the
   sentence would break the template. That distinction is the whole content of finding 3 above, and it
   is why the census that found the duplication had to be re-read before it could be acted on.

**The triple, measured — and the numbers belong to it, not to the change.** Two trees, **one process
each**, the live harness overlaid on base scripts (the overlay is the correct pre-fix experiment for a
reason the repo already records: `ROOT` is computed from `__file__`, so the overlay gives *new harness,
old scripts* rather than old-against-old):

| tree | passed | failed |
|---|---|---|
| live | **2166** | **0** |
| pre-fix `fbfe07e` scripts + live harness | **2129** | **37** |

**All 37 are `v0.4.36` checks** and nothing else moved — measured by counting the reds that are *not*
so labelled, which is **0**. Every one carries `(PIN)` except three: pin 19's precondition, red because
`mem_dir_source` does not exist there (§Round 3, lesson two), and pin 27's **CONTROL and its
REGRESSION GUARD**, which are red on this tree for the missing **subject** — `rows_for_store` is itself
added by this PR, so the attribute is absent and both fail on it — and *not* for the properties they
assert. That distinction is the whole of their labelling, and it is why neither is counted as a red for
the bound. Pin 24's **precondition is green**
— which is the part that matters, because it attributes pin 24's red to the arm rather than to a
fixture that failed to build. **Zero** reds arise from any other reason, so the label taxonomy is
enforced by the run rather than asserted here.

Two mutations, **both re-run against this final harness**, because a RED count belongs to the triple
and is never carried across an edit:

| mutation | RED | which |
|---|---|---|
| `_restore36`'s final `chmod` removed | **1** | pin 3's **GUARD** — the correct answer rather than a shortfall: no PIN may cover it (a check that cannot fail on pre-fix code is a guard by this repo's own rule), so the only available way to show the guard is not vacuous is to **reintroduce the defect it guards**, which is what this mutation does |
| the `--project` arm's `_canon` pair reverted to `Path(...).resolve()` | **2** | pins 20 and 21 — **both the `--store --project` cells and neither of the `--store`-alone cells** |

The second row is the discrimination evidence for the fifth arm, and it is stated as a *shape* rather
than as a count because the count alone would not show it: the mutation disables exactly one arm's
guard, and exactly the cells that reach that arm go red. The two cells that do **not** go red are the
control, and they are the reason this row is evidence rather than a red number.

**That first finding was closed in this change; two others were left open, and recording them as open
is the honest half of a ledger.** Each is stated at the strength it was actually established at, which
differs between them:

- **`store_context_from_registry`'s `project_id` fallback** is narrow-reachability, and **no pin
  drives it** — which by round 4's own lesson is a coverage statement, not a severity one: unexercised
  and unreachable are different claims, and only the second would make it harmless.
- **The shared recovery ladder was deferred by the maintainer, not closed.** The same three-source
  ladder is copied; the refactor that would collapse it is a real one and is deliberately not in this
  change.

⚠ **The third entry is gone from this list, and where it went is the point.** *"`rows_for_store` reads
every row to answer about one"* was recorded here with its **impact unmeasured** — structure readable
off the code, cost untimed. That measurement has since been taken and the one available repair is in,
so both now live in §Design as **the bound on `rows_for_store`'s scan**, where this entry's own
conclusion (*"not a missing index but a missing bound"*) is the thing being **designed** rather than a
thing being noted. Repaired in place rather than annotated: an open finding whose repair has landed is a
**stale claim**, and what stale claims cost is this document's whole subject. Its coordinate went the
same way, and the repair is worth naming because the failure is this document's own invariant: the
entry carried a `control_plane.py` line number for the scan, and that number resolves on `fbfe07e` to
**UPSERT SQL** — because the function it names is **added by this change** and has no base coordinate
to have. (The digits are not repeated here on purpose: writing them back would re-plant the very
citation the reading note says a document must not contain.) The replacement cites by greppable anchor.

Neither of the two left is a defect in this change's own rule; both are places the rule is repeated.
They are recorded here so that a later reader finds them in the design-of-record rather than
re-deriving them from a review thread — and so that *"left open"* can be audited as a list rather
than inferred from what a diff happens to contain.

## Scope

| ID | Finding | File | Class |
|---|---|---|---|
| RC-5 | the archive's identity is read from `Path.cwd()` while the subject is named by `--store` — a **well-formed, plausible, wrong** masthead that nothing downstream can distinguish from a right one | `render_html.py:413-416` | P1 misattribution |
| RC-5a | the same block is wrapped in `except Exception: pass`, so a resolution *fault* and an *absence* share one representation (`{}`) — **latent**, see below | `render_html.py:417-418` | P2 failure-honesty |
| RC-5b | `--store S --project P` is accepted with no agreement check, so `S` may be another project's store while the archive is stamped `P` | `render_html.py:407` | P1 misattribution |
| RC-5c | the same misdirected context **writes**: `warn_unenrolled_share` sets `_warned_unenrolled` in the **cwd** project's state file, and because that flag is a one-shot gate it **silently suppresses the cwd project's future warnings** — **two sites**, censused below | `render_html.py:415` **and** `render_dashboard.py:1936` → `store_context.py:70,86` | P1 state mutation |

**RC-5c is a class, and this row is a census — so its matcher is the warn, not the cwd.** Counting
`cwd()` sites would count cwd *reads*, and most are correct. The population is the **call sites of
`warn_unenrolled_share`** (`store_context.py:57`): **nine** in the tree
(`canonical_ingress.py:343,645,743,811,949`; `sync_global.py:1839,3393`; `render_html.py:415`;
`render_dashboard.py:1936`), of which **two** derive their context from a directory while the same
call names its subject by argument. The other seven pass a `ctx` already resolved from their own
subject. Naming both sites is not decoration: a File cell naming one would be read as *"there is
one"*. The second site is `render_dashboard.py` — the module §Design adopts as its **precedent** for
this fix, where the hardened call and the unhardened one sit twenty lines apart.

⚠ **Reach for the token and you get two thirds of the census, because the token is not always what
gets called.** Three of the nine are **aliased at the import** — `warn_unenrolled_share as _w_html`
(`render_html.py:412`), `... as _w_dash` (`render_dashboard.py:1935`), `... as _warn_prom`
(`sync_global.py:3391`) — and the call sites spell the alias: `_w_html(_ctx_html)` at `:415`,
`_w_dash(_rs_dash(_P.cwd()))` at `:1936`, `_warn_prom(_sctx)` at `:3393`. So
`grep -rn "warn_unenrolled_share("` returns **six** call sites (plus the `def`), and even the
undecorated token returns twelve lines that are six calls, **five** imports and a definition
(6 + 5 + 1 = 12 — the two plain imports are `canonical_ingress.py:18` and `sync_global.py:1832`). **Both
of the sites this section exists to name are among the three the grep cannot reach** — an earlier
draft said "one of the six and one of the three", which is false for *both* of them and contradicted
the sentence four lines above it: `render_html.py:415` and `render_dashboard.py:1936` are **both**
aliased, so **neither** is reachable by the undecorated token —
which is the same shape as the census above, in the same section, for the same reason: *the
population is the call, and a matcher built from a name is a hypothesis about a binding.*

## The measured defect

`store` (the archive series) comes from `--store`; `live_identity` (the masthead) comes from whatever
directory the process happens to be in. `:415` is the advisory warn call — the range cited above is
the whole block, not four identity reads:

```python
render_html.py:407   store = _store_for(args.store, args.project)
render_html.py:413       _proj = Path(args.project).resolve() if args.project else Path.cwd()
render_html.py:414       _ctx_html = _rs_html(_proj)          # ← identity from the ROOM
render_html.py:415       _w_html(_ctx_html)                   # ← and a WRITE from the room (RC-5c)
render_html.py:416       live_identity = _id_html(_ctx_html)
render_html.py:417   except Exception:
render_html.py:418       pass                                  # ← fault ≡ absence
```

Measured on `fbfe07e`, calling `resolve_store` from three cwds and reading `identity_snapshot`:

| cwd | `domain_id` | `enrolled` | `cross_project_allowed` |
|---|---|---|---|
| the repo | `personal` | `true` | `true` |
| `/tmp` | `unknown` | `false` | `false` |
| `/home/you` — a home directory that is not a project | `unknown` | `false` | `false` |

Driven end-to-end through `main()` — same `--store`, same cycle record, `--out` to a temp dir,
`webbrowser.open` stubbed — the two runs are **not byte-identical** (215535 vs 215536 bytes) with
`generated_at` identical, so the difference is the embedded identity and nothing else. **Neither run
raises** — so RC-5a is **latent, not live**, and this spec says so rather than claiming a fabrication
it did not measure. `RC-5b` is live too: `--store <temp store> --project <repo>` returns `rc=0`, no
refusal, an archive stamped `personal/true` rendering the temp store.

> **What RC-5a's fix actually converts.** An AST census finds **zero `raise` statements** in
> `resolve_store`, `_merge_settings`, `identity_snapshot` and `warn_unenrolled_share`, and six hostile
> cwds (a garbage `.git` file, a `.git` symlink to nowhere, a malformed `settings.json`, a nonexistent
> dir, a dangling `gitfile:`, a plain dir) each returned a context **without raising**. So the
> `except Exception` at `:417-418` cannot in practice be catching a *resolution* failure: the only
> thing it can catch is the **import** at `:410-412` (or a raise inside `warn_unenrolled_share`, which
> internally swallows its own write failures). Removing the blanket catch therefore converts exactly
> one behavior: **a broken plugin install now exits 1 rather than silently rendering `{}`** — and it
> does so on the **neither-flag** arm, which `tests/smoke.py:3246`/`:3250` assert exits 0. That is the
> honest direction (a broken install should not render a plausible archive), and it is a **listed**
> behavior change, added to the contract table rather than left for the implementer to discover.

**Why RC-5 is severe, and RC-5c why it is worse.** There is no guard to fool: the wrong value is
non-empty, correctly shaped, and schema-valid (`domain unknown / enrolled false` is a real state the
renderer draws), so nothing downstream — not the payload, not the browser view, not a schema check —
can tell it apart from a right one. And RC-5c turns a display defect into **durable state**: the
`_warned_unenrolled` flag is written into the cwd project's store and gates re-printing, so the
misdirection *persists* and suppresses a warning the user should still see.

The shipped dream path is affected, because it passes `--store` **and nothing else**:

```bash
SKILL.md:1427   CM_DREAM_ARC=1 python3 "${CLAUDE_PLUGIN_ROOT}/scripts/render_html.py" "<the --seed path>" \
SKILL.md:1428       --store "<native_memory_dir from Phase 0 / cm doctor>" --latest
```

`tests/smoke.py:2914` is the only other `render_html.py --store` site in the tree.

## The contract

| `--project` | `--store` | today | this spec |
|---|---|---|---|
| given | absent | identity from `--project` | **unchanged — already correct** |
| given | given | identity from `--project`, **unchecked** | identity from `--project`, **agreement verified** (RC-5b) |
| absent | given | identity from **`cwd`** ✗ | **recover the subject** — registry → the store's own marker → guarded `cwd`; nothing verifies ⇒ **refuse** |
| absent | absent | identity from `cwd` | **unchanged — here cwd *is* the subject** |

**Where the registry is consulted — a scoping condition, not an intent.** What the fix *adds* is a
**refusal** consult. Arms A/B/C guard `--store`-only; Arm D guards both-given, and it compares stores
through `resolve_store` without consulting the registry; Arm E is reached on the `--store` shapes
only, because it is a statement about *comparing a candidate against `--store`* and the other shapes
have no such operand. **The fix's three recovery sources — registry, marker, guarded `cwd` — are
consulted only on `--store`-without-`--project`**; the other three shapes consult no *recovery*
source. This matters because it is what keeps the neither-flag arm provably unaffected: `_run54`,
which drives `tests/smoke.py:3246` and `:3250`, reaches no refusal arm, so the table's Arm C wording
cannot refuse those runs.
⚠ **An earlier draft of this paragraph read *"two of the four shapes reach no shape-guarded refusal
arm (A–D)"*, and round 3 falsified it by shipping a guard for each:** `--project`-only now refuses an
unusable named subject (`render_html.py`'s `_ARM_NO_PATH`, the `--project` arm), and neither-flag
refuses an unusable working directory (`if cwd_ctx is None` — the cwd arm, whose second guard is
`except OSError`). Its conclusion survives; its premise does not. **That is the tell for this whole
document — a guarantee stated as *"no arm reaches here"* is a claim about the current arm list and
expires silently when the list grows, whereas a guarantee stated as *"this arm's operand is absent
from that fixture"* is re-checkable.** The restated claim, which is the one that was true all along,
is the second: `_run54`'s subject is a live temp directory, so neither cwd guard's operand is present
in it. The neither-flag arm is still reachable by some fixture; it is not reachable by *this* one,
and the difference is the whole of the guarantee. ⚠ The temp `HOME` those runs pin (`:3196`, `:3200`) is **not** what the guarantee rests
on, and must not be cited as if it were: `_run54`'s `env` pops only `CM_DREAM_ARC` (`:3199-3201`), so
a developer's `CLAUDE_CONFIG_DIR` (read *first*, `store_context.py:167-172`) or `CLAUDE_PLUGIN_DATA`
(`:175-182`, which relocates the registry outright) still reaches through, and a registry **can**
exist on that fresh home. Stated as a condition over the dispatch, the refusal is unreachable
whatever exists there.

**The registry is nonetheless *opened* on every shape, and saying so is the difference between a
scope and a false universal.** `resolve_store` reads it unconditionally — `classify_registry(_db)`
(`store_context.py:874`), then `if reg_state == "healthy":` → `connect_if_exists` (`:875-877`) and
`enrolled_domain` (`:882`, `:892`) — to derive `enrolled` and `domain_id` for **the cwd-side** identity
payload.
That read predates this fix and this fix does not change it. So the accurate sentence is *"the fix
consults the registry on one path"*, never *"the registry is consulted on one path"*. The distinction
is load-bearing rather than pedantic: an implementer who reads the absolute form could reasonably
promote the health check to a **blanket precondition over all four shapes** — which would refuse the
neither-flag arm on that fresh temp home, precisely the regression this paragraph exists to rule out.
Two incidental corroborations, both in §Design's favour: `resolve_store` already gates its own read on
`registry_state == "healthy"`, so *"read the field; do not re-derive"* is the house's existing move
rather than a new one; and its read is `try/finally` with **no `except`** (`:878-899`) — it does not
swallow, unlike the two precedents §Design declines to inherit.

**One behavior change is not an input shape.** Removing the blanket `except Exception` converts the
broken-install case for **every** row above, the neither-flag one included: where a failed import
currently renders a plausible `{}`-identity archive and exits 0, it will refuse and exit 1. See
*What RC-5a's fix actually converts* above.

The last row is load-bearing and must not be swept up by the refusal: `tests/smoke.py:3246` and
`:3250` run `render_html.py <cycle> --no-open --out <tmp>` through `_run54` with **neither** `--store`
nor `--project` — a single-cycle preview to a temp file (`_default_out`, `render_html.py:352-361`).
That is a feature, and with no project named there is nothing to derive an identity *from* but cwd.

### Why refusal is safe — and exactly what it costs

`enrolled` derives from `enrolled_domain` **in `resolve_store`** (`store_context.py:882`, `:892`) —
**a different producer from `store_context_from_registry`'s `status == "enrolled"` (`:1071`), and the
two disagree** (pin 1's ⚠ carries the measured table) — and it returns a domain only for a row that
is **both** `status='enrolled'` **and** carries a `domain_id` that is non-empty and not `"unknown"`
(`control_plane.py:848-855`). **An unenrolled project has no *enrolled* row** — so a contract of "a store
with no registry row ⇒ refuse" taken literally would refuse the dream path for every user who has
never enrolled. Measured: that is not the situation. `upsert_project` writes the literal `"active"`
in its VALUES tuple (`control_plane.py:844`) and its `ON CONFLICT SET` list never touches `status`,
so it is unconditional; the live registry holds **340 rows — 329 `active`, 11 `enrolled`**, of which
**327 carry a `-tmp` slug**. ⚠ **Here the matcher *is* the claim: 0 of the 340 stored paths contain the
substring `/tmp`.** The `tmp`-ness survives only in the slug encoding, because `slug_for` maps every
non-alphanumeric to `-` — a path under `/tmp/x/` records as `-tmp-x-`. A re-derivation by path grep
returns 0, so the figure is stated with its matcher precisely so a later reader does not file a **false
correction** against it. Mostly retired test projects. Recovery therefore works for unenrolled projects
too, and the refusal is about **the subject being unnameable**, not about enrolment.

**The real capability loss, stated plainly and then narrowed.** Against **registry alone**, a store
that no row names could no longer be rendered by `--store` alone — two populations: a project that has
never enrolled and never transacted, and a project whose store has moved (`project_rebind`,
`control_plane.py:1113-1127`: it `DELETE`s the retired `project_id` row, records an alias, and `UPDATE`s
the surviving row to the **new** store path, leaving the old store on disk unnamed). §Design's source 2
recovers **both** whenever the store's marker still **verifies** — its recorded `project_path` must
re-derive to this very store, which a move preserves (the old root still slugs to the old store) and a
redirect voids (that same root now derives to the redirect's target). What actually remains is **one**
population, and its membership test is the admission rule itself: **no source verifies** — no row, no
cwd that derives here, and either no marker or one that no longer does. That is
precisely the case that cannot be named without asking the caller. The remedy there is
`--project <its dir>`, which needs no registry at all, and the shipped path takes that remedy in the
same PR (§Design), so no shipped workflow loses anything.

⚠ **The `--project` remedy is not uniform across that population, and one member needs more than a
flag.** For a store whose project still derives to it — unenrolled, unpulled, rendered from an
unrelated cwd — the remedy works by construction: `--project <its dir>` resolves to *this* store and
Arm D is satisfied. A store **orphaned by a redirect** is the harder member: the redirect repointed
its owner's store elsewhere, so `--project <its old dir>` resolves to the *new* store and Arm D
refuses it, and so does every other shape — **while the environment still says the orphan belongs to
nobody.** That condition is the whole of it, and it is not a property of the code: an orphan is
renderable again as soon as some **source returns it** — a project's *resolution* returning it
(sources 2 and 3, which the table below measures per redirect), or a row's *stored key* naming it
(source 1, which needs no derivation at all).

**The routes are therefore not three remedies; they are one question asked of the precedence chain,
and the chain answers differently per redirect.** Each route works only by making some project's
*resolution* return the orphan — and whether it can is decided by where the redirect sits in
`resolve_store`'s assignment block (`store_context.py:908`…`:951`), never by the route's own shape.
Measured, one hermetic tree with one process per cell, the orphan being `P`'s own default store:

| redirect in force | a project-scope **declaration** naming it | **declaration + grant** |
|---|---|---|
| none (baseline) | admits — `source=autoMemoryDirectory`, `mem_dir_source='local'` | admits |
| user-scope `autoMemoryDirectory` (`<cfg>/settings.json`) | **admits** — local outranks user in the merge | admits |
| `CLAUDE_CODE_PROJECT_DIR_NAME` | **refused** — `source` stays the slot name; `:929-931` names the escape | **admits** |
| `CM_STORE_OVERRIDE` | refused — `source=store-override` | refused |
| policy (`<cfg>/managed-settings.json`) | refused — `mem_dir_source='policy'` | refused |

- **Unsetting the redirect** restores the default layout the orphan *is*, and is the one route with no
  condition — it is what makes the last two rows remediable at all.
- **A registry row naming it** (source 1) — a **different kind** of rescue, because it admits by
  **stored key** rather than by re-derivation: source 1's test is `row.native_memory_dir == --store`,
  so *no* project's resolution has to return the orphan for it to fire. What decides whether it can
  rescue a redirect-orphaned store is therefore **when the row was written** — `native_memory_dir` is
  written from a live context by `upsert_project` (`control_plane.py:844`) and rewritten by
  `cm project rebind` (`cm_ops.py:2881`), so a row written *under* the redirect names the redirect's
  target, while a **stale** row still names the orphan and **admits it**. That is the row §Design
  declines to gate source 1 with; gating the conjunct across all three sources would refuse exactly it.
  ⚠ **And it is where the two criteria for *"`P`'s store"* visibly disagree** — source 1's stored key
  against Arm D's environment assignment — so the `--project` remedy that helps every other orphan
  **refuses** here; Arm D's own remedy (*"drop one"*) is the way out.
- **A project-scope declaration, with or without a grant.** Both are the guard working, not a bypass:
  **these two** routes act by making the store *a function of some project root* again — the guard's
  own test — and source 1 above is the one that does not, by design rather than by accident. The two mechanisms are distinct and the table separates them —
  **`P/.claude/settings.local.json` naming `P`'s own default path** is admitted because
  `_project_local_mem_ok`'s **first** allowance is *"exact current-project native"*
  (`store_context.py:656`), checked **before** the containment and protected-config tests, so it
  short-circuits to `True`. The declaration is a **no-op** — it names the path the default layout
  already implies — but **local settings outrank user settings** in the merge chain (`:705-724`), so it
  *restores* the assignment by precedence rather than defeating anything. Measured: round-trip
  **true** ⇒ source 3 admits, and `--project P` now resolves to the orphan, so the documented remedy
  works as well.
  **A grant alone is inert** — measured: with no declaration in the merge there is no `custom` for it
  to admit, and every cell's resolution is the redirect's. `grant_covers` is consulted *inside*
  `if custom is not None` (`:923-925`), so the second column's middle rows are the grant **enabling a
  declaration that is otherwise an escape**, not a route of its own.
  **Another project adopting it** needs both, and the escape count is the mechanism in the output:
  the declaration in project `Q` (a different slug, so nothing short-circuits) leaves
  `resolve_store(Q)` on its **own** default store and appends **two** `ambiguity` entries (`:929-931`);
  after `write_store_grant(<pdata>, <Q's project_id>, <the orphan>, adopt=True)` the same call returns
  the orphan with `source=autoMemoryDirectory` and the `ambiguity` list **empty**. The grant writer
  **refuses a nonempty path without `--adopt`** (`store_context.py:533`), so adoption is an explicit
  operator act.
- **A refused declaration, which hands back the default — and the default *is* the orphan.** The escape
  rescue (`:929-938`) resets `native = default_native` whenever a project/local declaration fails
  containment, so a declaration naming an **unrelated, out-of-tree, un-granted** path is *refused*, and
  what `P`'s resolution then returns is `P`'s own default store, re-labelled `source='default-path'`.
  Measured under a user-scope redirect: the redirect alone resolves `P` to the redirect's target
  (`mds='user'`), and adding that declaration resolves `P` to **the orphan**, round-trip true and
  `_project_derived` true. So the orphan is renderable with the redirect **untouched**, no row, and
  **nothing naming it** — ⚠ *nothing names the **orphan***; the **declaration** is named, and this is
  the one route whose admitted context carries a **non-empty `ambiguity`**, because the escape rescue
  records the refusal (`store_context.py:929-931`) before falling back to the default. `ambiguity`
  gates **`write_allowed`** (`:987`), not admission, and no arm reads it — so a gate built on "refuse
  when `ambiguity` is non-empty" would close this route by mistake, and it would look like the
  conservative choice. Which is why the condition sentence above is the load-bearing one and a list
  of numbered routes is not: a route is anything that makes some resolution return the orphan, and the
  number of ways to do that is not the number of things a reader can be told to *do*.

⚠ **And the table is also where the two conjuncts separate — along a seam that is *not* the redirect
list.** Measured per family, with the candidate an unrelated directory and `--store` the redirect's
target: with **no** redirect the round-trip is the conjunct that discriminates — the resolver is
injective enough there that a foreign root's store is a *different path*, so the round-trip alone
refuses it, and deleting the round-trip admits an unrelated cwd. Under **every** redirect family —
`CM_STORE_OVERRIDE`, `CLAUDE_CODE_PROJECT_DIR_NAME`, policy, and `--settings` — the resolver is
*constant*: the round-trip is true for every candidate the moment `--store` is the redirected path,
so it evidences nothing, and the **predicate** is what refuses; deleting *it* admits. All four
families measure round-trip-**green** / predicate-**red** — which is pin 10's shape exactly, because
pin 10 is the assertion whose fixture is a redirect. So the assignment is **the round-trip carries the
un-redirected case and the predicate carries every redirected one**: each conjunct is load-bearing
*somewhere specific* rather than everywhere, which is what "both are load-bearing" has to mean for a
conjunction whose operands fail in different places.

So the honest edge is narrower than *"no remedy"* and sharper than *"any remedy"*: **the unremediable
set is exactly the redirects that cannot be outranked** — `CM_STORE_OVERRIDE`, assigned after every
settings scope, and policy, applied last *within* the merge — and for those the orphan is no project's
store, so there is no truth to stamp on its archive, and `--project` alone cannot supply one because
there is nothing for the two to agree on. The other two redirects are routable, and the table above
says how. This is stated rather than smoothed over because it is the honest edge of "refuse on a
miss" — and stating *which* redirects reach it, rather than "a redirect" in general, is the
difference between an edge and an over-claim.

> **Measured uniqueness — provenance tier: re-derivable only from an uncommitted state.** These are
> live-registry figures, not blob-derivable, so the **query** is given rather than the number alone.
> Run against the read-only connection (`control_plane.connect_readonly(db_path(ctx))`, or
> `sqlite3.connect(p.as_uri() + "?mode=ro", uri=True)`):
>
> ```sql
> SELECT status, native_memory_dir FROM projects;   -- 340 rows: 329 'active', 11 'enrolled'
> ```
>
> `native_memory_dir` carries **no `UNIQUE` constraint** (`control_plane.py:28`; the sole index is
> `sqlite_autoindex_projects_1`, the PK). All **340 are distinct** — and **340 remain distinct after
> resolution**, 0 collisions, so the resolved-path matching the design adopts introduces no ambiguity
> that raw matching did not already have. Single-owner is nonetheless an **emergent** property, not an
> enforced one. The recovery must therefore handle 0 / 1 / **N** rather than assume 1, and must refuse
> on N rather than take the first row — *taking a row is re-deriving a subject from something other
> than the subject*, which is RC-5 itself.
>
> ⚠ **This census is about the rows, and a row exists only for a project that has transacted or
> enrolled** — `upsert_project`'s callers are `enroll_project`, `transact` and `cm project` alone — so
> "0 collisions" is evidence about the *population that reached the registry*, never about the layout.
> **The collision the guard cannot refuse needs no row at all** (two roots sharing one slug), which is
> precisely why it went unmeasured: the figure is true, and it is the wrong figure for that question.

## Design

**The lookup already exists, and must not be reused.** `retention.py:64 _project_id_for_native` is a
store-path → `project_id` lookup. It scans unfiltered rows in Python (the house style), and it
**resolves both operands**:

```python
retention.py:82    rows = conn.execute("SELECT project_id, native_memory_dir FROM projects").fetchall()
retention.py:85        got = str(r["native_memory_dir"] or "")
retention.py:86        if got in (want, want_r):
retention.py:87            return str(r["project_id"] or "")
retention.py:88        try:
retention.py:89            if str(Path(got).resolve()) == want_r:
retention.py:90                return str(r["project_id"] or "")
retention.py:91        except OSError:
retention.py:92            continue
retention.py:96    except Exception:
retention.py:97        return ""
```

`:88` opens a `try` and `:91-92` guards it, so the resolved compare is **not** a second branch of the
`:86` `if` — a rendering that omits them depicts a two-arm `if` where the source has one test plus a
guard. Two statements of this function are load-bearing for §Design: the first-match `return` at
`:87`, and the collapse at `:96-97`.

It embodies **both behaviors this design forbids**: it returns the **first** match (the Arm-B
first-row rule) and it **collapses a registry fault into absence** (`return ""` — RC-5a's exact
class). It is also lossy for this purpose, returning a bare `project_id` rather than the full row
`store_context_from_registry` consumes. So the new code is a *sibling*, and this spec cites it as the
technique precedent — the scan and the two-sided resolve — while declining to inherit its two
defects. A second precedent does the same thing for a different consumer: `sync_global.py:3816`
selects the column and keys an overlay by `str(Path(_nm).expanduser().resolve())` (`:3823-3830`).

**The *recovery* precedent is one module over, and this design adopts it rather than inventing.** The
lookup above answers *"which project does this store path belong to?"* — not quite the question this
fix faces, which is *"I was handed a store; whose is it?"*. `render_dashboard.py` answers exactly that,
and has since v0.4.0. Its docstring states both the doctrine and the order:

> `render_dashboard.py:595-601` — *"STORE's identity — NEVER ambient cwd … Order: (1) the store's own⏎
> state file project_path → resolve_store (the script-owned anchor); (2) cwd resolves to THIS⏎
> store …; (3) the default layout …; (4) None → the caller degrades honestly."*

`:1545-1558` implements it, with the guard written out as a comment, and `:610-613` names the rule
*"the ownership guard"* and states its purpose — *"a stale/migrated `project_path` must NOT mis-pool
the transcripts to the wrong project — only return the pool when the resolved store IS the store being
persisted."* Two details are load-bearing here: the anchor's provenance, `render_dashboard.py:598`'s
*"script-owned"*, written by `sync_global.py:1732` (`st["project_path"] = str(project_dir)`) — and the
fact that `:619-620` applies the **same guard to cwd**, which is where this spec's source 3 comes from.
A sibling module already decided that an ambient directory is admissible *when it verifies*.

**Resolved-to-resolved is the house rule, and a one-sided compare is the outlier.** The population is
**native-store path compares and keys** — every site that asks *"is this the same store?"*, which is
**not** the raw `native_memory_dir` token census in §Corrections item 2: that one counts occurrences
of a *name* (`21` over `18` lines) and this one counts sites that resolve a *path*. The two coincide
at eighteen only by accident, and neither count is evidence for the other. The claim ranges over
**all** of this population, so it is stated as an invariant rather than as a total. **Three
attempts at a total produced three different numbers, each defensible**, because the number is a
function of the matcher and no matcher sees the class:

| matcher | what it sees | lines | native-store sites |
|---|---|---|---|
| **M0** — the literal pattern written out in the ⚠ below | the operator adjacent to `native_memory_dir` | **7** | **5** |
| **M1** — `.resolve()` co-occurring with a comparator on one line | everything that resolves and then compares | **24** | **14** |

Both run from the repo root over `plugins/consolidate-memory/scripts/`: **M0** is the pattern
reproduced verbatim in the ⚠ below; **M1** is
`grep -rnE "\.resolve\(\)" --include=*.py <that dir> | grep -E "==|!=| not in | in \{"`.

⚠ **The unit matters, and the two counts differ by it in both directions.** M0's seven lines are five
sites: `same_native_store`'s compare spans `store_context.py:1234-1235`, and the third line is its own
`def` — matched by the pattern's fourth alternative, which is a *name*. M1's twenty-four lines are
fourteen native-store sites: the other ten compare config roots, settings files, git dirs and
**canonical** domain dirs — real comparisons, not this class.

**And M0's five sites are a strict subset of M1's fourteen** — an earlier draft of this paragraph
called the two matchers incomparable, which the classification refutes: M1 sees every site M0 sees,
and nine more. The relationship is a widening, not two blind spots facing each other, and stating it
as incomparability would have implied M0 catches something M1 misses. What both **do** share is the
blind spot that matters: each is anchored on a *token* appearing on a *line*, so neither can see the
class's other three shapes — a compare whose operands were resolved earlier into locals and are
compared **by name** (`:980` `_norm_path(c) != chosen_key`; `:498`
`_grant_path_key(Path(raw)) == want`; `:3987` `_trig_k not in _have`), a lookup **key**
(`sync_global.py:3823-3830`), and — the shape that needed an AST pass to find at all, because neither
grep can reach it — **set membership against a resolved key**, where the compare's second operand is a
*set* rather than a path: `store_context.py:966-974` (the `seen`/`key` dedup over `candidates`, **inside
`resolve_store` itself**), `sync_global.py:1110-1123` (`_same_domain_stores`, keyed off the registry's
`native_memory_dir`), and `control_plane.py:2168-2178` (`_iter_store_roots`, which mixes native stores
with canonical and plugin-data roots and keys over all of them). **The union is what the claim ranges
over** — the fourteen plus those seven — **and the invariant holds over all of it: every one resolves,
on every operand it has**, including the resolver's own dedup. The only unresolved value in the picture is the one `resolve_store`
*returns* — which is the premise this section exists to establish, and the next paragraph's subject.

Enumerated as **exemplars by class, not as a census** — the difference is measured, not a hedge. The
four in `render_dashboard.py` (`:613`, `:620`, `:1545`, `:1557`); `store_context.py:632` (inside
`_protected_config_target`, one call below `:656`, comparing `custom.resolve()` against
`default_native.resolve()`) and its short-circuit sibling `:656`; the `_norm_path` compare at `:980`;
the grant-key compare at `:498`; `same_native_store` (`:1233-1235`) and the `retention.py` lookup that
resolves both operands; the lookup **key** at `sync_global.py:3823-3830`; `sync_global.py`'s
**trigger-node membership tests** — `:3997`, `:4701`, the four
`trig.resolve() not in {s.resolve() for s in stores}` sites (`:4259`, `:4693`, `:4933`, `:5003`, whose
set comprehension resolves every member), and the resolved-key membership at `:3987`; the
**resolved-key dict keys inside that same loop** — `:4003` → `:4004` and `:4018` → `:4021`, both
`str(store.resolve())` feeding `_overlay.get`; and the three **resolved-key dedups** —
`store_context.py:966-974` (`resolve_store`'s own `candidates` dedup), `sync_global.py:1110-1123`
(`_same_domain_stores`), `control_plane.py:2168-2178` (`_iter_store_roots`).

⚠ **The list cannot be closed by any stated matcher, and that is the measured reason it keeps
growing.** `:4003` sits **six lines below the named `:3997` — same `for store in _tok_nodes:` loop,
same local** — and the compare-shaped matcher that finds `:3997` cannot find it, because the resolve
there is an *assignment* (`_store_key = str(store.resolve())`) whose use is a line away, **by name**.
Measured: `grep -nE "\.resolve\(\)" sync_global.py | grep -E "==|!=|not in| in \{|\.get\("`
restricted to `:3985-4030` returns **one** line where the window holds **three** resolved
native-store uses. That is the census's own recorded shape — *"a compare whose operands were resolved
earlier into locals and are compared **by name**"*, the one that *"needed an AST pass to find at
all"* — so the shortfall is structural rather than careless: **a hand-list is a hypothesis about
which loops its author opened.** An earlier draft asserted "four … and all four resolve"; every
widening since has come by this mechanism — the recurrence is the finding, not the count.

**So the invariant is the claim, and the enumeration is the sample that argues for it.** The
invariant is cheap to *state* and expensive to *enumerate* precisely because it ranges over every
consumer — which is why the bounded question is its **dual**, and is the one worth auditing instead:
**where does an UNRESOLVED store path enter at all?** That set is small and closed: the registry
column (`control_plane.py:844` writes it, `store_context.py:1050` reads it), argv `--store`, and the
three retargeting knobs (`:901-905`, `:949-951`). It is the subject of the ⚠ in §Resolved-to-resolved,
and it is where a real gap could still live. A reader who wants to widen this paragraph should widen
*that* — by reading the entry points — rather than by adding names here.

⚠ **The tree is named, and it has to be — a bare basename is ambiguous here.** `render_dashboard.py`
and `sync_global.py` each resolve to **two** files, because
`plugins/dream-beta-tester/fixtures/canary-v0.1.19/` vendors byte-faithful copies whose line numbers
are deliberately another version's — and most of the sites above sit in those two files.

⚠ **Not by grep — and the pattern is written down because a reader will reach for it and be misled.**
From the repo root:
`grep -rn "native_memory_dir\s*==\|==\s*.*native_memory_dir\|native_memory_dir\.resolve\|same_native_store" --include=*.py plugins/consolidate-memory/scripts/ tests/`
matches **seven** lines in `scripts/`, which are the **five** sites M0 above counts (the four in
`render_dashboard.py`, plus `same_native_store`'s two-line compare and its `def`) — and misses **every
site in the enumeration above whose operands were resolved earlier or whose compare goes through a
helper** — the operator is never adjacent to `native_memory_dir` at those, because the compare goes
through `_grant_path_key` or `_norm_path`, or spells the other operand
`default_native`/`trigger_store`. On `tests/` it returns ten lines this census excludes — **seven**
*raw* `==` compares resolving nothing, **two** that are not compares at all, **one** that resolves both
operands. A match set that is neither a superset nor a subset of the sites it would be used to
describe is why the enumeration above names sites rather than patterns. (`tests/` is out of scope for
that same reason: a test asserts a store against a path it constructed itself — a different pattern
with a different justification, not a site this claim covers.)

| site | form |
|---|---|
| `store_context.py:1233-1235` `same_native_store` | `.resolve()` **both** |
| `store_context.py:185-189` `_norm_path` | a **helper**, not a comparison site — consumed at `:980` |
| `retention.py:85-90` `_project_id_for_native` | `.resolve()` **both** |
| `sync_global.py:3823-3830` | `.expanduser().resolve()` |

The reason is structural: `resolve_store` never resolves **the store path it returns**. It does resolve
its *input* (`:818-821` `start = start.resolve()`), so this is a claim about the return value, not a
loose way of saying the function resolves nothing — and the distinction is load-bearing, because the
whole rule below is about the returned path. `config_root` returns
`_home_dir(env) / ".claude"` unresolved (`store_context.py:167-172`) and
`default_native = session_dir / "memory"` (`:864-865`) inherits that. Measured through a symlinked
`HOME`:

```
native_memory_dir                       /tmp/rcvfy/link/.claude/…/memory   (UNresolved)
Path(store).resolve() == ctx.native     False   ← a one-sided compare REFUSES a legitimate pair
Path(store).resolve() == native.resolve() True  ← the two-sided form accepts it
same_native_store(…)                    True
```

**Both operands, in both places.** The same asymmetry bites the *recovery*: the column is written
unresolved (`control_plane.py:844` `str(ctx.native_memory_dir)`), so matching "by resolved path"
against a raw column finds **0 rows** for a symlinked store and reports Arm A for a store that *has*
a row. The comparison must resolve the argument **and** the column.

**The environment assigns the store; the check is against that assignment.** `--project` resolves to
`resolve_store(P).native_memory_dir`, and three supported knobs deliberately retarget what that is:
`autoMemoryDirectory` settings, `store_override`, and `CM_STORE_OVERRIDE`
(`store_context.py:901-905`, `:949-951` set `source = "store-override"; native = override`). This is
ADR 002's "managed settings win", not a bug — `CM_STORE_OVERRIDE` is an **exercised** knob, set at
`tests/smoke.py:18390` and documented in the env map at `:18383`. (A grep also finds the two
hermeticity pop lists, `:7811-7813` and `:8490-8493`, but those **pop** the variable as hermeticity
scrubbing; they are not exercises, and citing them would overstate the test coverage.) `cm doctor` prints the overridden value too, so the
two agree by construction. Arm D therefore forbids a `--store` that **no authority assigns to `P`**;
under an override, `--store X --project P` where `X` is the override is coherent, because in that
environment `X` *is* `P`'s store. The sentence this replaces was silent about the knob, which is the
part that had to be repaired.

**Two consequences survive that decision, and stating them is what keeps it from reading as a
dodge.** First, under a *process-local* override the archive is **not internally consistent**, and a
reader must not assume it is: the project **label** comes from the subject (`DATA.project`,
`dashboard.template.html:1503`, `:1510`), while the **domain/enrolment line** comes from the identity
payload (`identOf(null,true)` → `identLine`/`paintBanners`, `:1512-1514`) — which under an override
is `P`'s. The badge and the series can therefore describe different projects, because the redirect is
resolved **per process**: in another process, `X` **may** belong to a different project — **or to
none**. Both halves are load-bearing and the earlier *"in every other process, `X` is some other
project's store"* was false twice over: a scratch, backup, or shared directory belongs to no project
in any process, and where the redirect value *is* `P`'s own natural store — a plausible way to pin it,
since that is the path `cm doctor` prints — then `X` is `P`'s in every process. The consequence this
sentence carries (the badge and the series can disagree) needs only the weaker claim, so nothing is
lost by stating it. That is the operator's own assignment, so honouring it is right; presenting the
result as a self-consistent archive is not. Second, an accepted **cost**, stated rather than discovered: under an override,
`--store <P's own slug path>` is now refused even though on disk it *is* `P`'s store. The remedy —
drop `--store` — is one flag, so this is a **message-quality cost, not a capability loss**.

**`plugins/consolidate-memory/scripts/render_html.py`** — lift identity resolution out of the
`try/except Exception: pass` and give it its own resolver, called once from `main` in place of
`:407-418`.

- `--project` given → context from `resolve_store(Path(project).resolve())`. With `--store` also
  given, compare **resolved to resolved**; mismatch ⇒ refuse (RC-5b).
- `--store` only → **recover the subject** (below).
- neither → `resolve_store(Path.cwd())` — **unchanged**; this fix adds no *recovery* consult here,
  because cwd *is* the subject and there is nothing to verify it against. The registry is still
  **opened** on this shape as on every other — `resolve_store` does that unconditionally — so read
  this bullet as *"no recovery source"*, never as *"no registry read"* (§The contract).

### Recovering the subject from `--store`

**One rule, three sources, and the rule is what does the work.** A candidate is admitted only if it
**round-trips to the store being rendered** *and the round-trip discriminates*:

```python
_c = resolve_store(candidate)
_c.native_memory_dir.resolve() == store.resolve() and _project_derived(_c)
```

Sources are tried in this order; the first to verify wins. ⚠ **Both conjuncts gate sources 2 and 3
only.** Source 1 is a *stored key*, not a re-derivation: the row is matched on the **column it stored**
— `SELECT … FROM projects WHERE native_memory_dir = ?`, the filtered sibling of
`iter_registered_projects` (the `def` at `control_plane.py:796`, whose SELECT at `:799` is the row
shape this sibling clones) that §Design adds — while the round-trip
**re-derives** a store from a project root. The two disagree exactly where the registry is most
useful: a **stale** row, written before its store moved, still matches the store being rendered and
would be **refused** by the conjunct. Gating source 1 would therefore discard the registry's own
record of a store in order to re-test it against the layout that replaced it. And the row's context
carries `resolution_source="registry-row"` (`store_context.py:1097`), a label no whitelist admits, so
wiring the conjunct across all three sources would refuse every row and kill the primary recovery
outright.

⚠ **The round-trip alone is not sufficient, and the second conjunct is not decoration.** A guard can
only discriminate where the function it guards is **injective**, and `resolve_store` is not: under a
**global redirect** it maps *every* directory to the same store. **Four routes** do that, and the
first form of this predicate named only two:

- `CM_STORE_OVERRIDE` (`store_context.py:949-951`) — applied unconditionally, with no reset branch.
- `autoMemoryDirectory` from **user / managed / policy / `--settings`** scope (`:923-925`) — applied
  unconditionally unless the setting came from **project** or **local** scope; `:926`/`:932` is the
  only branch that resets it. `--settings`/`CLAUDE_CODE_SETTINGS` is a scope rather than a redirect
  kind, which is why it is easy to miss: `_apply("settings-flag", cli)` (`:726-734`) sets
  `mem_dir_source='settings-flag'`, measured — a fourth non-injective route that reads like a
  *config* knob and behaves like an override.
- **`CLAUDE_CODE_PROJECT_DIR_NAME`** (`:920-922`) — the instructive one, because it does not *look*
  like a redirect. `:861-865` reads `slot_env = env.get(...)`, then `default_slot = slug_for(root)`,
  then `project_slot = slot_env or default_slot`: when the variable is set, **`default_slot` is
  computed and discarded**, so `default_native` becomes a function of the environment and `root` never
  enters it. The knob reads as *"which project directory am I"* — a slot, not a store — and it is
  exactly as constant as an override.

With **any** of the four in force, `resolve_store(cwd).native_memory_dir == store` is true for every
cwd the moment `--store` is the redirected path. The guard cannot fail, so it evidences nothing, and
source 3 would admit cwd under the guard's blessing — RC-5 reproduced *with* a verification step that
looks like it checked.

⚠ **And the first form of `_project_derived` committed this cycle's own defect one field over, which is
why the code below **whitelists rather than denies**.** It **inverted** the question for `mem_dir_source` —
a closed set of settings scopes, where whitelisting excludes scopes that do not exist yet — and left
`resolution_source` a **denylist whose default is admission**, which *admits routes that do not exist
yet*. That asymmetry is precisely how `CLAUDE_CODE_PROJECT_DIR_NAME` walked in: it never touches
`autoMemoryDirectory`, so the correct whitelist was never consulted, and it was not one of the two
names in the denylist. `_project_derived` is the conjunct that makes the check a test, and the
fall-through is now `return False`:

```python
def _project_derived(c) -> bool:
    # A project-derived store path is a FUNCTION of the candidate; a global redirect makes it a
    # CONSTANT, and a constant cannot witness anything about the candidate it was read from.
    # WHITELIST over ROUTES. `resolution_source` names a route, and routes get added over time:
    # enumerating the ones that MAY PASS makes a newly NAMED route fail CLOSED, while enumerating
    # the ones that must fail admits it. That inversion is the repair — the denylist form let
    # CLAUDE_CODE_PROJECT_DIR_NAME through, because it is neither of the two names.
    # ⚠ CLOSED OVER NAMES ONLY: a route that wears a declared name while assigning a CONSTANT is
    # admitted here, and nothing in this module couples a label to the value assigned beside it.
    # That axis is the redirect pin's (extend its fixture with every new route), not this one's.
    if c.resolution_source in PROJECT_DERIVED_SOURCES:      # default-git-root, default-path
        return True
    if c.resolution_source == "autoMemoryDirectory":
        return c.mem_dir_source in PROJECT_LOCAL_SCOPES
    return False
```

**Three things about that block, because all three are load-bearing.** First, **asserting on a label is
admissible here only because the enumeration fails closed — closed over *names*.** A route wearing a
name nobody has declared is refused until someone declares it, and that asymmetry is the whole
difference from the form it replaces: a denylist fails silently in the dangerous direction.
⚠ **The qualifier is not pedantry; dropping it would over-promise.** `_project_derived` reads
`resolution_source`, and the *value* that name stands for is assigned by hand beside it at five
sites in `resolve_store` — `store_context.py:908-909`, `:921-922`, `:924-925`, `:932` with
`:934`/`:936`/`:938`, and `:950-951` — with nothing asserting the two agree. So the enumeration
closes the **name** axis (a new route with a new name is refused) and is **blind on the value
axis**: a route that wears a declared name while assigning a **constant** is admitted, and that is
the dangerous direction. **The value axis is pin 10's, not the predicate's** — its assertions are on
the refusal *outcome*, so a declared name over a constant goes red there whatever the name says.
And the consequence is a **duty, not a property**: **pin 10's family fixture must be extended with
every new route**, because the reader this paragraph would otherwise convince — that the whitelist
alone suffices — is exactly the reader who will not extend it when they add route six.

⚠ Second, **the predicate's reach is exactly one kind of context — which is what makes source 1's
exemption structural rather than a convention the next editor must remember.** The claim *"a label no
whitelist admits, so source 1 cannot be gated"* is only safe if no **other** context's label can
arrive at the predicate, so it is checked rather than assumed: `resolution_source` has exactly **two
producers** anywhere in `store_context.py` — `:1013` (`resolution_source=source`, inside the module's
**sole** `StoreContext(` constructor at `:1003`) and `:1097` (`"registry-row"`, inside
`store_context_from_registry`). That wrapper is called from **exactly three sites — `cm_ops.py:304`,
`cm_ops.py:554`, and `tests/smoke.py:11576`** — and **never from `resolve_store`** — so a context
produced by `resolve_store` cannot carry
`"registry-row"` at all, and one produced by the wrapper cannot carry an assignment-chain label. And
`_project_derived` reads **fields off the returned context** and is applied to no other input — it
takes no store argument, so there is no path by which it could be asked about a path rather than
about a resolution. **The two vocabularies therefore cannot meet.**

Third and last, **both names are shared constants, and the design has to earn that for the second one.**
`PROJECT_LOCAL_SCOPES` *is* the code's own containment tuple at `store_context.py:926`, and typing it
a second time here is the class the v0.4.32 periphery-parity patch closed — two sites keeping a second
copy of a rule the store already states canonically. It is defined once in `store_context.py` and
imported, so the predicate cannot drift from the containment rule without the two being edited apart.
⚠ **`PROJECT_DERIVED_SOURCES` was that same class in the first draft of this paragraph: its members
were a second spelling of the two literals assigned at `:908`.** So §Design changes `store_context.py`
once more, behaviour-neutrally — the two labels become module **names**, consumed at their assignment
sites, and the predicate imports the tuple rather than spelling them again:

```python
_SRC_GIT_ROOT = "default-git-root"          # the NAMES define the set, never the reverse
_SRC_DEFAULT_PATH = "default-path"
PROJECT_DERIVED_SOURCES = (_SRC_GIT_ROOT, _SRC_DEFAULT_PATH)
...
source = _SRC_GIT_ROOT if common is not None else _SRC_DEFAULT_PATH   # :908 — was two literals
...
source = _SRC_GIT_ROOT        # :936 — the reset inside the escape rescue
source = _SRC_DEFAULT_PATH    # :938
```

⚠ **The direction of that definition is the whole of it.** `_project_derived` consumes the tuple by
**membership**, for which order is meaningless; the assignment sites consume the `_SRC_*` **symbols**,
for which order is everything. Written the other way round — `PROJECT_DERIVED_SOURCES = (…)`, then
`_SRC_GIT_ROOT, _SRC_DEFAULT_PATH = PROJECT_DERIVED_SOURCES` — the same tuple is a *set* to one
consumer and a *positional list* to the others, and the literal is not alphabetical, so the
alphabetizing tidy a reviewer or linter will eventually reach for
(`("default-path", "default-git-root")`) silently swaps the two labels at `:908`/`:936`/`:938`.
Nothing catches it: the
predicate admits both names, pin 10 asserts *outcomes* and the outcomes are unchanged, and **no test
in the tree asserts either label** — `"default-git-root"` and `"default-path"` occur only at those
three sites, while `tests/smoke.py` asserts `"autoMemoryDirectory"` and `"registry-row"` and neither
of these. Its only visible effect would be `cm doctor`'s `resolution_source` line naming the wrong
route — a diagnostic lie, which is this spec's own defect class one field over. With the names
defining the set, that edit is a no-op, and asserting the constant's *values* is a **regression
guard** rather than a pin: it cannot run on pre-fix code at all, where the constant does not exist.

⚠ **The third label in that rescue stays a literal, and it must.** `CLAUDE_CODE_PROJECT_DIR_NAME`
(`:934`) is deliberately **not** a member — naming it here would read as membership in a set the
predicate admits. The **name-axis** drift that remains is one-directional and fail-closed: a route added to the
resolver without a label added here is **refused**, which is the over-refusal direction, and pin 10 is
what makes it visible.

> **A property probe was considered and declined, and the reason bounds the design.** The
> knob-agnostic form is
> `resolve_store(candidate).native_memory_dir != resolve_store(<fresh temp dir>).native_memory_dir`
> — genuinely stronger, since it would admit a future legitimate route with
> no edit and could not be fooled by a route nobody anticipated. It was declined because it buys that
> by **creating a directory and calling `resolve_store`** (which opens the registry unconditionally)
> from inside a render path, adding a failure surface to the very code whose job is to fail loudly.
> Since a new *legitimate* route means new code in the resolver anyway, requiring it to be declared
> here is a **feature**: it forces the question to be asked in review. Over the routes a reviewer is
> being asked to declare, the whitelist is not the weaker guard in the failure direction — both refuse
> a newly *named* route. ⚠ **But the sentence above concedes more than that, and the concession is the
> correct one**: the probe is value-based, so it also refuses an unanticipated **value** at a
> **declared** name — the one hole a name-based predicate cannot see, and the reason the value axis is
> pin 10's by outcome rather than the predicate's by construction.

It applies to **rows 2 and 3 only** — source 1 admits a *row*, never calling `resolve_store` on a
candidate, and a redirect is what makes many rows claim one path, so source 1 is already self-limiting
by Arm B. This is the code's own distinction, stated in `_merge_settings`' docstring
(`store_context.py:684-686`): *"Project/local paths must stay contained; user/managed may name an
explicit absolute dir."* A contained project-scoped setting still names a store that is a function of
the project and stays admissible; a user/managed one does not. **It costs one field and two
constants**: `mem_dir_source` is computed at `:855` and simply not exposed on `StoreContext`
(`:123-149`), while `resolution_source` (`:134`) and `store_override` (`:143`) are already there;
`:926`'s containment tuple is lifted to `PROJECT_LOCAL_SCOPES`, and `:908`'s two labels become the
`_SRC_*` names that `PROJECT_DERIVED_SOURCES` collects — so the predicate imports a set, and neither
a name nor the set is spelled twice (above).

| # | source | admitted because | covered when |
|---|---|---|---|
| 1 | **registry row(s)** whose `native_memory_dir` resolves to this store | it is the control plane's stored key for this exact path | the project has ever transacted or enrolled (`control_plane.py:844`) |
| 2 | the **store's own marker** — `.consolidation-state.json` → `project_path` → `resolve_store` | it is the store's own record of its owner, script-written (`sync_global.py:1732`) — *only because it **verifies***: the recorded `project_path` must re-derive to this very store | the marker still verifies — the store was `--pull`ed **and** its `project_path` still derives here (a move keeps that true; a redirect voids it) |
| 3 | **`cwd`** → `resolve_store` | *only because it is verified **and the verification discriminates***: cwd's store **is** this store, the path is a function of the project rather than a global redirect, and the derivation is injective at this candidate — that third condition is `slug_for`'s, and it is where the warrant has a stated bound (§Recovering) | you render from the project the store belongs to, or from a root that slugs with it |

**Nothing else is admitted, and the order is a preference, not a trust ranking** — source 3 is not
"less safe" than source 1; it is admitted under the identical guard. The order just tries the most
specific evidence first. If no source verifies, **refuse** (Arm A).

**Source 3 is a deliberate reversal of the plan's `cwd` row, and the guard is why it is safe.** The
plan marks *"identity from `cwd`"* ✗ on the `--store`-only row, and that mark is **right**: today cwd
is read **unconditionally**, so it supplies an identity whether or not it bears any relation to the
store. Under the guard the claim is different in kind — cwd is a *candidate whose derivation is
checked against the subject*, and one that does not round-trip is discarded rather than used. **The
defect was never that the process has a working directory; it is that the working directory was
believed.** The plan's ✗ is honoured by the guard, not waived by it.

**And that warrant is scoped, not absolute — and the scope has two edges, only one of which the guard
closes.** *"cwd is not an ambient guess"* needs the round-trip to **discriminate**, which needs the
resolver to be **injective at this candidate**. It fails that in two ways, and they are different in
kind:

- **A global redirect** makes the resolver *constant* — the round-trip is true for every cwd, so it
  carries the sentence nowhere; the `_project_derived` conjunct above is what refuses (§Why refusal is
  safe measures all four families round-trip-green / predicate-red).
- **A slug collision** makes it *non-injective at a point* — `slug_for` maps **every** non-alphanumeric
  to `-` (`memory_status.py:983`), so distinct roots can share one slug. Measured: `/…/a/b`, `/…/a-b`
  and `/…/a.b` all slug to `-…-a-b`, resolve to the **same** `native_memory_dir`, and carry three
  **distinct** `project_id`s. Here the predicate does **not** catch it — `default-path` is a member,
  and the colliding candidate's route is a legitimate one — so **both conjuncts are green for a
  candidate that is not the owner.**

So the honest form is: the guard makes cwd non-ambient wherever the store path is project-derived
**and the derivation is injective at that candidate**, and **refuses** it where the path is not
project-derived at all. At a collision nothing is missing that could be supplied: the two roots share
**one store on disk**, so there is no fact of the matter for a round-trip to witness — the check
certifies *path coincidence*, and the identity it stamps is a true name for a store the **layout** has
made plural. That is a bound on the layout rather than on this fix, and it is stated rather than
pinned because a pin must be able to fail: the design does not refuse at a collision, so there is
nothing there to assert red. §Design's ⚠ on the source table carries the same bound, and the collision
pair belongs in pin 10's fixture family as a **control** rather than as a tenth assertion. (The
layout's own split-brain detector is blind to exactly this case: `near_duplicate_slugs` **EXCLUDES
`slug` itself** (`memory_status.py:1446`, enforced `:1451`), and an exact collision *is* one slug.)
Stated without any of this, this very paragraph would be an assertion taking its warrant from
something other than its subject — the defect this spec exists to name, committed in the argument for
the fix.

**Registry rows still handle 0 / 1 / N, and N still refuses.** The guard admits a *candidate*, so two
resolved matches is a genuine ambiguity — the registry names two projects for one store — reported by
Arm B. Taking the first row is the `retention.py:87` defect.

**Two sources can verify and name different projects; the registry wins, and that is a choice rather
than a tie-break artefact.** It takes a store two projects can both call their own —
a **global redirect** retargets `native_memory_dir` for every project, and the row written under it
(`control_plane.py:844`) records it. ⚠ **Four routes reach that state** — the routes that make the
store constant, since a shared *path* is what a constant assignment produces: `CM_STORE_OVERRIDE`
(`store_context.py:949-951`); `autoMemoryDirectory` from **user/managed/policy/`--settings`** scope
(`:923-925`, which assigns `native = custom` unconditionally — `:926`'s containment reset is reachable
only from *project* or *local* scope; the `--settings` form is the one that reads like a config knob
and behaves like an override); and **`CLAUDE_CODE_PROJECT_DIR_NAME`** (`:920-922`, where every
project's row written under it records the identical `native_memory_dir`). A fixture author who took
the two original names as the set would not reach the third, let alone the fourth.
**Provenance: measured** — the constant-ness of all four was observed directly, each resolving a
*foreign* candidate to the redirect's target (§Why refusal is safe's per-family probe) — while the
enumeration itself is read from the assignment order at `:857-951`. ⚠ **And a fifth producer of a
shared path needs no redirect at all**: a **slug collision** puts two roots on one store with the
resolver untouched, and it reaches this state with **one** row whenever only one of the two has
transacted — so Arm B's row count cannot see it, and the tie-break described next is what resolves it.
Where exactly
*one* row claims this store and the
marker's `project_path` names another, the control plane's record is taken as authoritative: it is
the mapping the control plane maintains for this purpose, while the marker is a *cache the same
system writes* (`sync_global.py:1732`) — preferring it would let whichever of the two was written
first decide the identity. This is §The contract's scoping condition read strictly — source 2 exists
for what the registry **cannot** name — and §Design's *"the first to verify wins"* is what enforces it.

**What this buys over registry-only.** Two populations the registry cannot name are recovered anyway:
a store moved by `project_rebind` (its row now points at the **new** path, but its marker still names
its owner), and a project that never enrolled *and* never transacted but has been pulled at least once.
Both were booked as capability loss against a registry-only design; source 2 erases them. What remains
a true loss is narrower, and stated by its **admission condition** rather than by a list of absences: a
store **no source verifies** — no row, no cwd deriving here, and no marker that still does. That is
precisely the case that cannot be named without asking the caller, for which `--project <its dir>` is
the remedy for the member of it that still has a project. **`_project_derived` widens that loss by
exactly one population, deliberately:** a store named by **no row** and reachable *only* through a
**global redirect** — any of the four routes enumerated above, not just the user/managed one,
since they produce
the same constant — now refuses where today it renders with cwd's identity. That render was RC-5's
defect, not a capability — admitting it would mean keeping the wrong answer and adding a check that
appears to bless it. Under a redirect the store is shared by every project, so there is no single true
identity to recover; refusing and naming the remedy is the honest result. ⚠ **And for that population a
marker does not rescue it either, which is precisely why the predicate exists:** under a global
redirect `resolve_store(project_path)` returns the redirect's target for *every* `project_path`, so the
round-trip passes **vacuously** and a marker would "verify" whichever project you cared to name it
after.

**The advisory warn call must receive the recovered context.** `warn_unenrolled_share` is not
read-only: when the ctx is an unenrolled share and the marker file exists, it writes
`_warned_unenrolled` into `ctx.native_memory_dir / MARKER_FILE` (`store_context.py:70`, `:86`). Today
it receives the **cwd** ctx, which is RC-5c. After the change it must receive the **subject's**
context — the recovered row's when recovering, `--project`'s when given. This is a behavior change
and is stated as one: an unenrolled project's warning flag will from now on be set (or not) in the
project the archive is *about*.

**The same misdirection takes a lock in the wrong project.** The write path calls
`acquire_mutation_locks(ctx, [ctx.project_id])` (`control_plane.py:258`), so today **a render of A
takes a mutation lock on B's project.** That is the quieter half of RC-5c, and supplying the right ctx
corrects it for free. It is worth naming separately because unlike the flag it is a **strict
improvement**: no caller loses a guarantee it had, and B stops being locked by renders of A.

Back in `render_html.py`: only the **`warn_unenrolled_share` call's** failure stays wrapped. The
identity resolution is lifted out of the `try/except Exception: pass` entirely, so a resolution
failure becomes a named refusal, never `{}` — the fault/absence conflation RC-5a is about.

**`plugins/consolidate-memory/scripts/control_plane.py`** — add the lookup beside
`iter_registered_projects`, selecting the full column set `store_context_from_registry` consumes.
`_enrolled_rows` (`cm_ops.py:206`; its column list is a superset of what is consumed — it does select
`current_root`) and a test-side mirror at `tests/smoke.py:11570-11574` are the two existing statements
of that list. Filtering is in Python by **resolved** path on both sides (§Resolved-to-resolved) — the
same house style as `_iter_store_roots` (`control_plane.py:2149`) and `_project_id_for_native`
(`retention.py:64`), and the exact-match SQL optimisation is not worth its own failure mode.

⚠ **It must not swallow `sqlite3.Error`.** The house style it copies does
(`control_plane.py:804-805`), and for this caller that swallow *is* the A/C conflation
(§The five refusal arms): the registry can classify `healthy` while the scan still raises. Map the error to **Arm C**, carrying the
classified state — not to a zero-row result.

⚠ **Do not reuse `_enrolled_rows` or `iter_registered_projects`.** `_enrolled_rows` is
`WHERE status='enrolled'` (`cm_ops.py:209`) — reusing it would refuse every unenrolled user, the
regression this section exists to prevent. `iter_registered_projects` (`control_plane.py:796`) omits
`current_root` **and** `git_common_dir`; its `_col` helper returns `default=""` on a missing column
(`store_context.py:1040-1047`) and `:1060 root = Path(root_s) if root_s else template.project_root`
then takes the **template's** root — that is, the cwd's. RC-5 re-entering through its own repair.
(`git_s` degrades to `None` rather than the template's value, so `current_root` is the omission that
actually takes the root over; both are absent.)

**Identity comes from `store_context_from_registry`** (`store_context.py:1032`) — purpose-built,
already `resolution_source="registry-row"`, already consuming a `projects` row with `template=ctx`
(existing callers: `cm_ops.py:304`, `:554`; existing test: `tests/smoke.py:11576-11580`). Its
docstring records a prior defect worth heeding, quoted with its line break marked:

> "Uses the recorded project_id, native store, root, and domain. Never treats⏎ native_memory_dir as
> a project root (that minted a different project id)."

**Source 1 passes the row**, never `resolve_store(Path(store))` — that call would mint a different
project id, which is the defect the docstring records. Sources 2 and 3 are the opposite case and
*cannot* pass a row: they recover a project **directory** (from the marker, or from cwd), so they call
`resolve_store(<that dir>)` and then the guard compares its `native_memory_dir` against the store
being rendered. The distinction is the whole reason the guard is stated separately from the sources:
**source 1 recovers an identity directly and source 2/3 recover a candidate that must then verify.**

**`plugins/consolidate-memory/scripts/render_dashboard.py`** — RC-5c's second site, one line. On the
persist path the warn takes the **cwd's** context, twenty lines below the call that refuses to:

```python
render_dashboard.py:1912   _store = _P(persist_dir)                 # ← the SUBJECT, named by an argument
render_dashboard.py:1917   _sess  = _narration_session_dir(_store)  # ← hardened: store, never cwd
render_dashboard.py:1934   if persist_dir:
render_dashboard.py:1936       _w_dash(_rs_dash(_P.cwd()))          # ← RC-5c, under the same silent except
```

⚠ **The obvious repair is the wrong one, and §Design forbids it fourteen lines up.** The warn must
**not** be handed `_rs_dash(_P(persist_dir))`: `persist_dir` is a **store** path (`SKILL.md:1278` —
`--persist <store dir>`) while `resolve_store` takes a **project directory**, so that call feeds the
store back in as a root, slugs it, and answers with a **phantom** — measured on a hermetic `HOME`:

```
resolve_store(<project>)     native …/projects/-tmp-rcphantom-proj/memory            pid p_1da1b0b2…
resolve_store(<that STORE>)  native …/projects/-tmp-rcphantom-home--claude-projects
                                    --tmp-rcphantom-proj-memory/memory               pid p_e85b61ed…
                             native == the store passed in ?  False
                             pid    == the project's pid ?    False
```

So the warn would fire `UNENROLLED LOCAL-ONLY` for a project that does not exist and set the flag in a
store that does not exist, while the subject store's flag stays unset — **pin 7's assertion, red**. It
is the defect the `store_context_from_registry` docstring records (*"that minted a different project
id"*, `store_context.py:1035-1036`), and that call forbids by name one screen up.

**The repair is §Design's recovery applied to `persist_dir`, and it is not a substitution.** Sources
1/2/3 recover a *candidate that must then verify*; this file already implements both halves one
function up — `:604` reads the marker and `:606` pulls its `project_path`, while `:612-620` holds both
ownership guards. The
warn takes **the recovered subject context**, the same ctx the archive path would get. Where **no
source verifies**, it is **skipped** rather than fired against a phantom: a warn is advisory, so losing
it costs a nag, while a wrong subject costs a spurious nag *and* a write into a phantom store. The skip
prints to stderr — `fault ≡ absence` is the RC-1 mechanism this cycle exists to close.

**What makes this more than a stray site is that the same file hardened the
identical cwd→store form twice**: the guard sits on the `if` beneath each resolution — `:620` in
`_narration_session_dir`, `:1545` in the usage-window clock, whose marker fallback re-guards at
`:1557` — and the comment establishing the premise is `:1546-1549`, anchored `v0.4.0 review (R128
clock liveness)`: *"a dream can render from a different cwd — silently skipping would stall the
usage-window clock"*. That phrase **wraps across the comment's first two lines**, so the anchor greps
and the phrase does not — the reason this document cites anchors rather than quoting them. That is
exactly the situation `:1936` ignores. A hardened call is evidence its author knew the
hazard, so the unhardened sibling reads as an oversight rather than a different intent. It is also the
**more consequential** of the two sites in practice: `--persist` is the dream's **terminal render**,
so a foreign cwd is reachable here far more often than on the archive path. (⚠ **What `SKILL.md`
marks MANDATORY is the step that *follows* it, not this one:** `:1436-1437` says a cleanly completing
dream *"is not done until `render_html … --latest` runs"*, and makes that conditional on a clean
exit-0 `--persist` (`:1440-1443`).) On the common path cwd *is*
the project, so the fix is a no-op there and bites only cross-cwd — which is why pin 7 needs its own
run for this site rather than sharing the archive path's.

**`plugins/consolidate-memory/scripts/store_context.py`** — expose `mem_dir_source` on `StoreContext`
(the dataclass at `:123-149`): `_merge_settings` already returns it (`:855`) and `:691`/`:702-703`
already track it, so this is one field threaded through, **not** a change to `resolve_store`'s
resolution. **Plus two constants**: `:926`'s containment tuple `("project", "local")` becomes
`PROJECT_LOCAL_SCOPES`, and `:908`'s two labels — consumed again at `:936`/`:938` — become the
`_SRC_*` name pair that `PROJECT_DERIVED_SOURCES` collects; the **set** is what the predicate imports
and the **names** are what the assignment sites consume, so an alphabetized tidy of the tuple is a
no-op and neither can drift apart from the rule it names.
**The three label assignments (`:908`, `:936`, `:938`) are edited in spelling only** — each literal
becomes the constant's name, value-identical — and no branch and no return value of `resolve_store`
changes. **Measured, not asserted**: `resolve_store` was run over **60 environment cells** (three
roots — two git repos and one non-git directory — × `CM_STORE_OVERRIDE` on/off ×
`CLAUDE_CODE_PROJECT_DIR_NAME` on/off × five settings scopes: none/user/project/local/policy) in
**one process per tree**, comparing `native_memory_dir`, `resolution_source`, `domain_id`,
`enrolled`, `session_dir`, the `ambiguity` count and `project_id`: **0 differences in 420
comparisons**, with every edited site reached — the `:908` ternary through both labels (3 cells), the
lifted scope tuple through **both** its members (24 cells), and all three **reset** targets through
the escape arm (24 cells: `:936` from the two git roots, `:938` from the non-git one). A cell set
that never reached an edited branch would make the measurement vacuous, so the reach census is part
of the result — and it earned its place here: the matrix's **first run read the added field on the
pre-fix tree**, so every cell raised `AttributeError` and it compared nothing while still printing a
full column of differences. `local` is the fifth scope for that same reason: the four-scope set left
the tuple's second member unexercised. It is the only
edit in this PR to the shared substrate the other sites call *into* —
`render_html.py`, `render_dashboard.py` and the recovery itself all route through it — which is why
`_project_derived` is written to read **fields off the returned context** rather than to reimplement
any part of the resolution order.

**`SKILL.md:1427-1428`** — add `--project` so the shipped path names its subject instead of relying
on cwd. This is what makes the refusal arm free.

> **A note on what this makes possible.** `cm doctor` prints `native_memory_dir` as an absolute path
> (`doctor_report`), so the `--store` the model substitutes is **copied from script output**, not
> reconstructed from the slug — and the value it copies is `resolve_store(project).native_memory_dir`,
> which is *the identical function* `_store_for(None, project)` calls. The two therefore agree by
> construction, and **Arm D can only fire on a transcription slip.** Because this runs at the dream's
> **terminal `--persist`** (see §Design's RC-5c passage for what `SKILL.md:1436-1439` marks MANDATORY),
> a slip must not strand the reader: Arm D's remedy
> names the one-step fix — re-run **without `--store`**, which derives it from `--project` — rather
> than only naming the mismatch. The alternative (drop `--store` from the recipe entirely, so nothing
> is transcribed) is *more* in this release's spirit but changes the shipped recipe further than the
> approved plan; it is called out here for the reviewer rather than taken unilaterally.

### The bound on `rows_for_store`'s scan — and why it sits *after* the query

**The finding recorded as open, now measured and repaired rather than noted.** `rows_for_store`
resolved **every** row to answer about one: a full `SELECT … FROM projects` and then a per-row
`safe_resolve` in Python, because the comparison is between *resolved* paths and a `WHERE` cannot
express it. The earlier round could state only the structure; the cost is now measured, and **the
per-row resolve is the cost** — ~15-16 µs/row, the one figure stable across every size measured:

| rows | total, measured | per row |
|---|---|---|
| 340 (the live registry) | 5.4 ms | 15.7 µs |
| 10,000 | 0.15 s | 14.9 µs |
| 100,000 | 1.5 s | 15.1 µs |

⚠ **The loop's SHARE of the total is deliberately not stated, and that is a correction rather than a
style choice.** An earlier revision of this section pinned it at **89-92%** and costed the 340-row
registry at **7.9 ms**; neither reproduces, and the two figures contradict each other on their face —
`7.9 ms ÷ 340 = 23.2 µs/row`, against the `~16 µs/row` the same paragraph asserts. Nor is the share a
constant of the function: it is a property of the **registry**, since the `SELECT` is a larger fraction
of a large on-disk registry than of a small one, and it measures **99.9% loop** against a registry
whose query is free. What is stable is the per-row cost, so that is what is stated and what a
re-measurement should reproduce.

**No repair that speeds the loop is sound**, which is why the finding's own conclusion — *"not a
missing index but a missing bound"* — is the whole of the available win:

- An **index**, or a `WHERE native_memory_dir = ?` prefilter, would speed the QUERY and not the
  per-row resolve — the wrong half, whichever share the two halves happen to hold.
  It is also unsound on its own terms: a stored value that is not already canonical can still
  **resolve onto** the target, and only `resolve()` detects that. Nor may the loop stop at its first
  hit — `native_memory_dir` carries no `UNIQUE`, which is why the function returns a list and the
  caller must distinguish zero rows from two.
- **`os.path.realpath` is 1.80× faster** than `Path(p).resolve()` (8.93 vs 16.10 µs, measured) and is
  **not swappable**: it silently drops the `RuntimeError`/`ValueError` that `safe_resolve` exists to
  convert into *unusable* — and both inputs are measured, not hypothetical.

So the bound is the one available: **an unusable `store` yields `target is None`, and this returns `[]`
whatever the registry holds** — on that input the scan cannot change the result. ⚠ **And it is a
correctness bound, not only a cost one** — which an earlier revision of this section got wrong by
claiming that *no row can equal `None`*, so that *every row would be resolved only to fail the same
comparison*. A **resolvable** row does fail the comparison against `None`, because no path equals it;
but a row whose OWN value is unresolvable resolves to `None` too, and `None == None` **admits** it.
Measured with the bound removed: one NUL-bearing row comes back for a NUL-bearing `--store`, and a
corrupt row's identity is stamped onto the archive — RC-5's own shape, arriving inside RC-5's repair.
That the bound is *also* the cost win is a second reason to keep it, not the reason it is required.
(The target rule is `safe_resolve`, whose guard admits `(OSError, ValueError, RuntimeError)`; a NUL
raises on **every** supported interpreter, 3.8-3.13.)

⚠ **And it sits AFTER the query, which is the non-obvious half.** Hoisting it above `conn.execute`
reads as strictly better — it skips the query too — and it is tempting for a second reason: the edit
looks nearly free. ⚠ **It is not literally one line, and the difference is not pedantry**: `target` is
bound *below* the query, so moving the `if target is None: return []` alone raises `UnboundLocalError`
rather than hoisting anything. The two lines move together, which is what the tempting form of the
edit actually does. It is the one placement that is
wrong, and it was **measured rather than argued**: the query is this function's only **fault channel**.
`classify_registry` verifies tables and never columns — the function's own docstring states the premise
— so a registry can classify `healthy` while the SELECT raises. Hoisted, an unusable store returns
*before* that raise, the caller reads a **miss** where it should read a **fault**, and the reader is
sent to re-enroll a project that is already enrolled. That is `fault ≡ absence`, the mechanism v0.4.35
closed and the reason Arm C exists at all. The trade is a bare `SELECT` over the registry, on a rare
input, against that signal — and the signal wins.

**Two mutations, two different reds — which is why this needed two checks.** Deleting the bound and
hoisting it over the query are different defects aimed at the same line, and neither check can see the
other's:

| mutation (single-variable, nothing else changed) | result | the ONLY red |
|---|---|---|
| bound **deleted** | 2165 passed, 1 failed | the **pin** — no row was resolved |
| bound **hoisted** above the query | 2165 passed, 1 failed | the **regression guard** — the fault is masked |

The pin asserts the **loop** did not run, and never that the query did not — an exclusion that is
forced rather than stylistic: a pin asserting *"not queried"* would have **demanded** the hoist, the one
placement that converts a registry fault into an absence, and would have printed green while demanding
it. (That is not hypothetical — it is the pin this change wrote first, and the measurement is what
overturned it.) The instrument is a sentinel row whose `str()` records the touch, so it reads the loop
without a timing assertion; the control reads the same instrument `True` for a usable store, because a
pin asserting a **negative** on its own is satisfied by a function that resolves nothing at all. The
guard is labelled a guard by this repo's own rule — the **property it asserts** cannot fail on pre-fix
code, since pre-fix there is no bound to hoist. That is a claim about the property and not about the
check, and the next paragraph is the difference: the check itself *does* fail there.

⚠ **On `fbfe07e` this pin reports a FAILURE, not a red — and both are correct.** `rows_for_store` is
itself **added by this change**, so the base tree has no such attribute; an unguarded call raises
`AttributeError` and takes the whole suite down, swallowing every reading after it — the harm this
document already records for pin 24's precondition, arriving here on the pin itself. The lookup is
guarded, so the base tree now runs to completion at **2129 passed, 37 failed** with the whole red list
readable.

### The five refusal arms, and why they must not share a message

All five use `render_html`'s own shape — one line to stderr, `return 1` — as at `:387`, `:394`,
`:404`, `:425`, `:430`, `:438`. The *shape* is uniform; the *separator* is not: four of the six use
`—`, while `:425` uses `:` and `:438` uses `(`. The template is therefore
`print("render_html: <fault>" + <sep> + "<remedy>", file=sys.stderr)`, not an invariant em-dash.
Each arm carries a **distinct, stable anchor phrase** so a pin can assert which arm fired without
matching prose. **The property that claim needs is cross-arm distinctness, and the two are not the
same claim** — measured, because this round added an arm whose phrase is ordinary English and so
cannot satisfy the stronger one:

| anchor | in the shipped tree (`plugins/`) on `fbfe07e` | in render_html's own stderr |
|---|---|---|
| `belongs to no registered project` | **0** files | 1 message |
| `is claimed by` | **0** files | 1 message |
| `cannot read the control-plane registry` | **0** files | 1 message |
| `is not the store for` | **0** files | 1 message |
| `does not exist` (added this round) | **6** files, **16** occurrences | 1 message, in 2 contexts |
| `resolves through an unusable store path` (added this round) | **0** files | 1 message, in **2** contexts |

So the first four are **tree-unique**, the fifth is **not**, and the sixth — the one this round added,
which did not exist when the earlier draft was written — is again tree-unique, because it is a phrase
minted here rather than inherited. The earlier draft of this paragraph generalized from the four. `does not exist` ships across **six** files of the shipped tree —
`sync_global.py` (8 — **the matcher is the condition `if not project_dir.is_dir()` returning 2, and
each coordinate is that guard's `print` line**, which is this table's convention throughout. Six say
`(phantom-store guard)` verbatim: `:1821`, `:3020`, `:4378`, `:4531`, `:4767`, `:4920`. The two at
`:5264` and `:5274` are the same guard stated longhand — `:5274`'s own sentence names *"a typo'd path
would mint a phantom store under its slug"* — so the parenthetical greps to **6** where the condition
finds **8**, and quoting the label as the matcher would understate this census by two),
`render_dashboard.py` (4, all comments), `distill_scan.py` (1, its
`warning: project dir does not exist`), `control_plane.py` (1), and the beta-tester's `snapshot.py`
(1) and `beta_checks.py` (1), **16 in all**. **The pins are unaffected, and the
reason is scope rather than luck:** every one of them asserts against **`render_html`'s own stderr**,
and there the phrase occurs in exactly one message. That is the narrower property — *no message of
arm X contains arm Y's anchor* — and it holds for all six. The tree-wide grep was always a **proxy**
for it that happened to be cheap while the anchors were distinctive phrases; stating the proxy as the
requirement is what would have made this paragraph false the moment an anchor stopped being one.
(**Scope, stated because the column header above got this wrong once:** the figures are **`plugins/`**,
the shipped tree, and the whole repository is **81 occurrences in 22 files** — the difference being
`tests/` and the release docs, and *not* this document, which **does not exist at `fbfe07e`** at all;
an earlier draft claimed the extra occurrences were its own, which was false on its face. The count is
given per-file rather than as a total because a total would be a census of text recorded inside the
file it measures, and would be wrong by the next edit.)

| Arm | Trigger | Anchor phrase | Remedy named |
|---|---|---|---|
| A | **no candidate is admitted**: `--store` matches **0** rows (including when the registry is absent), and every source-2/3 candidate either fails the round-trip or fails `_project_derived` | `belongs to no registered project` — **or, if the path does not exist, `does not exist`** | `--project <its dir>` — plus `check the path` on the absent-path outcome |
| B | `--store` matches **≥2** rows | `is claimed by` | `--project <dir>` |
| C | registry present but **locked / corrupt / permission-denied / incompatible** | `cannot read the control-plane registry` | `--project <dir>` |
| D | `--store` disagrees with the store this environment assigns to `--project` | `is not the store for` | re-run **without `--store`** (it derives that from `--project`), or pass a matching pair |
| E | the subject resolves to a store path that **cannot be canonicalized** — so no candidate store can be compared against it and no source can be *tested* | `resolves through an unusable store path` | `check autoMemoryDirectory in your settings` |

**Arm A is still one trigger with one conjunction — it now has two outcomes, and the second was a
defect rather than a design.** The finding is below, because it was found by self-review after the
first measurement and it moved the restored code.

**Arm E is the same rule the other four already obey, applied to a fault that was not a fault of
naming.** The rule — *two faults must not share one message* — is what gave the registry its own arm
(C) rather than folding it into A, and it is what separates D from the absent-path outcome below. Arm
E is where that rule would have been broken next: a store path derived through a settings redirect
that `resolve_store` declines to canonicalize (a NUL) produces **zero admitted candidates**, which is
exactly the *shape* of an Arm A miss. The two are not one condition. A miss says *nothing names this
store*; the fault says *nothing could be **tested***, because the one operand every source is compared
against was unusable. Print A's line for it and the reader is told to pass `--project <its dir>` — a
command that fails the same way, since the redirect governs it too. This is `fault ≡ absence` arriving
one layer down from where the plan fenced it, and the ⚠ at the fall-through (`if cand_store is None`)
is where it is caught: `_canon` returns `None` rather than raising, so the fault arrives as a **value**
and `None != target` would file it as "this candidate isn't the one".

Honest scope, because this arm is the one addition this cycle that changes the documented contract:
**it was not in the approved plan's four-arm inventory.** The plan fixed the *set* of arms against the
recipe above, and E is derived from the recipe rather than from the plan. It is recorded here as an
addition, not as a realisation of the plan — an arm the plan did not list is a contract change, and a
contract change recorded as an implementation detail is how a design-of-record stops describing its
design.

⚠ **And the addition was surfaced for a veto rather than merged as an implementation detail: the
maintainer confirmed it on 2026-09-19, after the arm, its two sites and its rationale above were put
in front of them.** That sentence is the part of this record that outlives the arm. A contract change
is not made legitimate by being derived correctly from the design — it is made legitimate by being
**raised** — and the difference between *"this follows from the rule"* and *"this was agreed to"* is
the difference between an argument and a decision. The spec can only ever supply the first; the
review is what supplies the second, and it is recorded because a reader auditing the four-arm plan
against a five-arm tree needs to find the permission, not just the reasoning.

> **Arm A's remedy is verified in the one configuration where it looks least likely to work.** Under a
> global redirect every project resolves to the store, so the refusal above is reached with the store
> fully reachable — and `--project <its dir>`, which is what the arm tells the reader to do, **recovers
> correctly there**: `--project` takes its context from `resolve_store(P)` with no sources and no
> guard, and Arm D then compares that store against `--store`. Where the redirect makes them equal,
> the pair **agrees** and the archive renders `P`'s identity. The remedy is therefore correct in
> exactly the configuration that produced the refusal, not correct by convention.

> **Arm D must not mistake a path fault for a pairing fault.** `--store <typo> --project P` today
> exits 1 with `no dreams to render` (`render_html.py:429-431`); under Arm D it would report
> `is not the store for` — true, but aimed at the wrong mistake. Check that `--store` **exists**
> first and name that instead. (A `--store` naming the project's correct-but-absent store agrees with
> both sides the same way and falls through to the existing `no dreams to render`.)

### A fault that wore the wrong name — Arm A's absent-path outcome

> **Found by self-review, after the first measurement, by asking what the new code does to an input
> it was not designed around.** Measured on the implementation revision: `render_html <cycle>
> --store <a path that does not exist>` with **no** `--project` reported *`belongs to no registered
> project`* and told the reader to *`pass --project <its dir>`* — a registration fault, about a path
> that is not there, with a remedy naming a directory that does not exist. **Pre-fix the same command
> exited 0 and rendered**, so this was a new misdiagnosis, not an inherited one.
>
> ⚠ **"Wrong name" here does not mean the old phrase was false, and the distinction is what keeps
> the repair from being read as a correction.** *"belongs to no registered project"* is **vacuously
> true** of an absent path — nothing names it and nothing derives it, so the assertion holds. What
> was wrong is that it is **silent on the one fact the reader can act on** (the path is not there)
> while its remedy sends them to a directory that does not exist. A vacuous truth beside an
> unfollowable remedy is a misdiagnosis in practice and a tautology in form — and only the second
> reads as defensible from inside the code, which is why the finding survived the first measurement.
>
> **It is the Arm D principle one arm over, and the Arm D note above did not generalize because its
> fix was guarded by a flag.** `--project`'s presence is what turned the existence test on: with both
> flags the pairing branch checks `Path(store).exists()` and names the path fault; with `--store`
> alone, control fell past every source to Arm A. So **the same typo'd `--store` read two different
> ways depending on a flag with nothing to do with the mistake** — which is the F1 theme verbatim
> (`a-fault-and-a-verdict-must-not-share-a-message`), arriving in the arm whose whole purpose is to
> name the right fault.
>
> **The repair, and the position is the entire design.** Dispatch the message on `store_p.exists()`
> **after every source has run**, never before them:
>
> ```python
> for cand in cands:
>     …                          # admit a candidate that verifies; else keep trying (2 lines)
> if not store_p.exists():
>     return _refuse(f"--store {store} does not exist — check the path, or pass --project <its dir>")
> return _refuse(f"--store {store} belongs to no registered project — pass --project <its dir>")
> ```
>
> ⚠ **Abridged, and the abridgement is marked rather than silent** — this document's own convention
> (`…` marks what was cut) applies to code as much as to quotes. The shipped f-strings interpolate
> `_ARM_NO_PATH`, `_REMEDY_PATH` and `_REMEDY_PROJECT`; they are written out here so the message
> reads as the operator sees it. Nothing else is altered: the guard's position, its predicate and
> the two `_refuse` calls are the shipped ones.
>
> ⚠ **An existence test placed FIRST is the same predicate with the opposite meaning, and it is
> wrong.** Before the sources it asserts *"a renderable store must exist"* — and that assertion is
> **false of two invocations this design deliberately supports**, both measured on the fixed
> revision:
>
> | the invocation | why the store is legitimately absent | measured |
> |---|---|---|
> | a registry **ROW** names it | the store was **deleted since enrolment**; source 1 is a *stored key* and a deleted store is the case it exists for | **rc 0**, the ROW's identity |
> | the **cwd derives** it | a project that **has not dreamed yet** — the store is not created until it does | **rc 0**, the cwd-verified identity |
>
> After the sources the same test asserts only *"nothing recovered this, and the reason is the
> path"*, which is true whenever it is reached. **The two readings are distinguished by position
> alone** — the predicate, the variable and the file are identical — which is why both are pinned
> rather than left to the comment that explains them.
>
> **The remedy names both routes because both are real readings of this input**, and neither clause
> asserts anything false: the path may be a typo (`check the path`), or correct-but-passed-from-the-
> wrong-cwd, where `--project <its dir>` derives the absent store and then **agrees** with it. Prefer
> the two-clause remedy to the one-clause one here: `check the path` alone would misdiagnose the
> second reading in the opposite direction, and the arm's job is to name the fault, not to pick one
> of the two situations it cannot distinguish.

> **`absent` routes to Arm A, not Arm C, and the codebase's own doctrine is why.**
> `assert_mutation_allowed` (`control_plane.py:644-658`) states it outright — *"An absent registry is
> fine (first enroll/upsert will create it)"* — and returns early on `state in ("absent", "healthy")`.
> The reasoning is that Arm A's assertion is **vacuously true** on an absent registry: with no file
> there are no rows, so no store belongs to a registered project. Arm C's message is the one that
> would assert something **false**, and it earns its keep only where the registry **holds a row that
> would have named this store and we could not read it**. Routing absent to C would also make this
> spec's own Arm-A pin non-hermetic: a temp `HOME` with no `control.sqlite` *is* the fresh-install
> state **where `CLAUDE_CONFIG_DIR` and `CLAUDE_PLUGIN_DATA` are both unset** (the ⚠ in §Verification
> carries the detail), so the pin would be green on a developer machine and red on a clean CI runner —
> precisely the non-hermetic shape the restructure exists to remove.

> **Arms A and C must not collide.** `iter_registered_projects` swallows
> `sqlite3.OperationalError → []` (`control_plane.py:804-805`), and `connect_if_exists` returns `None`
> for absent and for unreadable and unopenable alike (`:589-597`). ⚠ **But not for *corrupt*, and that
> is the input this paragraph exists for.** SQLite opens **lazily** — `connect_readonly` never reads
> the file header — so for a DB of garbage bytes `connect_if_exists` returns a **live `Connection`**,
> and the failure lands only at the first **query**, as `DatabaseError: file is not a database`. The
> conflation is therefore *deferred* rather than avoided, and the **class** is what decides whether it
> lands: `DatabaseError` is the **parent** of `OperationalError`, so a lookup written
> `except sqlite3.OperationalError` lets a corrupt registry escape into Arm A — which is why §(c)'s
> prescription is `sqlite3.Error` and not its narrower sibling. Reusing either helper would report a
> **registry read fault** as *"this store belongs to no registered project"* — sending the reader to
> re-enroll a project that is already enrolled. This is the fault/verdict conflation **F1 shipped a release
> about**, one module over. The distinction is already computed upstream: `classify_registry` (`:600`)
> returns `absent | healthy | locked | corrupt | permission-denied | incompatible` (`:603`), surfaced
> as `ctx.registry_state`/`registry_error` (`store_context.py:146,148`). **Read the field; do not
> re-derive the classification.** Note that A, B and C share one **remedy** — A's table cell spells it
> `--project <its dir>` and B/C's `--project <dir>`, a cosmetic difference — the harm
> being prevented is a false *diagnosis*, not a wrong command. Arm C should carry that diagnosis
> verbatim, using the existing formatter `store_context.py:1110-1113 _registry_state_line(ctx)`
> (`state` or `state: err`) — the same string `cm doctor` prints — so the arm reads
> `cannot read the control-plane registry (locked: database is locked) — pass --project <dir>`.

> ⚠ **`registry_state == "healthy"` does not imply the recovery query can run — the health check is
> TABLE-level, never column-level.** `classify_registry` verifies only that five *tables* exist —
> `needed = {"projects", "facts", "holders", "tombstones", "migration_state"}` against
> `SELECT name FROM sqlite_master WHERE type='table'` (`control_plane.py:631-641`) — and checks no
> column at all. Measured: a registry carrying all five tables but a `projects` table without one
> column a full-column scan needs returns **`("healthy", "")`** while that scan raises
> `OperationalError: no such column: session_dir`. So the field is real but **coarser than this check
> requires**. Three things follow.
>
> **(a) Provenance tier — constructible, not observed.** That registry was *built* to measure this,
> not found: the only real registry on the authoring machine is `user_version=5` with the column
> present, and the conditional `ALTER TABLE projects ADD COLUMN session_dir TEXT` in `_migrate_schema`
> (`:687-690`) is **not** evidence that such DBs exist — it entered at the same commit as `SCHEMA_SQL`
> itself (`9e6a1ef`), so it is day-one belt-and-braces rather than a repair for a known state. The
> **level mismatch** is what the rule rests on, and the level mismatch is measured; the *instance* is
> not. The rule stands on (a) alone, which is why it is still a rule.
>
> **(b) This is pre-existing, not introduced.** `iter_registered_projects` runs the same failing
> SELECT against the same DB today — `SELECT … COALESCE(session_dir, '') …` at `:798-802`, whose
> `except sqlite3.OperationalError: return []` at `:804-805` silently yields an **empty fleet**. (Note
> the defence is aimed at the wrong failure: `COALESCE` handles a NULL *value* and cannot handle a
> missing *column*.) So the new lookup must not *inherit* this, and the rule of engagement holds — the
> fix repairs nothing it also causes.
>
> **(c) The technique precedent has the identical swallow.** `retention.py:96` is
> `except Exception: return ""` — the exact collapse named two paragraphs above. So "must not
> swallow" is doing real work against the house idiom *and* against the function this spec cites as
> its model, not just against style. If the new lookup inherits it, a registry it could not read is
> reported as **Arm A** — *"belongs to no registered project"* — which is F1's conflation again, one
> door over from the door the field closes. **The new lookup must not swallow:** map `sqlite3.Error`
> to **Arm C**, or let it propagate to the refusal. "Read the field" is necessary and not sufficient.

> ⚠ **Two faults sharing one representation reproduce the collision one layer down — deciding to
> route `absent` to Arm A does not achieve it.** The paragraph above settles the *decision*; securing
> it is a separate obligation, and the first implementation of this resolver got it wrong in a way no
> amount of reading the routing table would have caught. The shape was:
>
> ```python
> if state != "absent" and state != "healthy":
>     return None, arm_c(...)          # filtered the malignant case...
> conn = connect_if_exists(db)
> if conn is None:
>     return None, arm_c(...)          # ...and re-derived it from the same None
> ```
>
> The second branch is reached by **`absent` too**, because `connect_if_exists` returns `None` for an
> absent file and for an unopenable one alike — the very conflation called out two paragraphs up,
> arriving in the *repair* rather than in the inherited helper. The filter on line 1 is not a guard:
> it inspects the classification, and line 3 inspects a **different** representation of the same
> state that cannot distinguish them. **The repair is to return early on the benign case rather than
> to filter the malignant one** — `if state == "absent": return None, ""` *before* the connect, with
> the later branch tightened to `if state != "healthy"` so the `None` there means only "healthy by
> table-check yet unopenable", which is the fault it actually is. The general rule, and the reason
> this is recorded rather than silently fixed: **when two states share a sentinel, guarding the
> decision is not guarding the path — return the benign state out of the function before the sentinel
> is consulted.** This is also why the pins assert the *absence* of the other arm's anchor, not the
> presence of this one.

## Adjacent, not in scope

`sync_global.py:2664` computes `_ctx_net = _rs_net(Path.cwd())` inside `network(all_domains=True)`,
reachable as `--network --all-domains <dir>`, where the positional dir is parsed at `:5255` and then
silently ignored (`:5261-5262`), with the cwd context feeding `_holder_labels(…, ctx=_ctx_h)` display
attribution (`:2674`). It does **not** meet this spec's definition — no argument names that subject —
so it is not RC-5. It is recorded because it is the nearest second cwd→ctx site, and because a
**silently ignored positional argument** is a finding in its own right for the audit's tail.

**A corrupt registry degrades identity to an "unenrolled" *verdict* — F1's class, fenced rather than
fixed.** `resolve_store` gates its registry read on `reg_state == "healthy"` (`store_context.py:875`),
so under `corrupt` / `locked` / `permission-denied` / `incompatible` it neither raises nor refuses: it
**falls through** with `domain_id="unknown"`, `enrolled=False`, `cross_project_allowed=False`.
Measured on a corrupt-registry fixture, `classify_registry` → `('corrupt', 'file is not a database')`
while `resolve_store(P)` yields `domain_id 'unknown'`, `enrolled False`. The fault *does* reach the
page, in **two** rendered places. `identLine` (`dashboard.template.html:1068-1077`) appends
`" · registry " + state` for any state that is neither `healthy` nor `absent` (`:1070-1071`, emitted
at `:1075` in the local-only branch and `:1076` in the domain branch), so the archive's **primary**
identity line reads **`local-only · registry corrupt`**; `paintBanners` (`:1078-1090`, its registry
flag at `:1084-1086`) says the same in full. The leading token of the primary line is still
`local-only` — a *degraded* verdict rather than the *"we could not read the registry"* the state
actually carries — but the fault is not confined to a subordinate badge, and the wording repair has
two places to land rather than one. No arm guards this — Arm C's refusal is reachable only on the `--store`-only
shape — so **pin 3 cannot see it**, and it is **pre-existing**.

**Deliberately not fixed here, for blast radius.** Extending Arm C's refusal to the `--project` path
would refuse the shipped `cm report` path for every operator with a corrupt registry, converting a
degraded-but-working render into a hard failure. The narrow repair is a *wording* one in the template
— promote the badge when the primary line would otherwise assert non-enrolment — which belongs with
PR B's prose families, not with this contract change. **It does not touch recovery:** the guard
compares `native_memory_dir`, which is root/settings/override-derived and never registry-derived
(`store_context.py:909-951`, `:1005`), so under a corrupt registry sources 2 and 3 still recover the
**right project** and only the badge degrades.

**The same shape one field over: `conflicts` is a *rendered* field whose operand is source-dependent.**
`identity_snapshot` sets `out["conflicts"] = len(list_conflicts(conn, ctx.project_id))`
(`store_context.py:115`) whenever the registry opens, and the template paints it on the **primary**
surface — `dashboard.template.html:1047`, and the `flag warn` banner at `:1087-1088` reading *"N open
mirror conflicts — classify with `cm conflicts` before the next pull."* Its **operand** differs by
source: source 1 hands `store_context_from_registry` **the row**, so `ctx.project_id` is the control
plane's (alias-resolved, `store_context.py:878-880`), while sources 2 and 3 call `resolve_store(<dir>)`
whose `project_id` is minted from that directory by `project_id_for` (`:424` — the `def`; `:423` is the
blank line above it, which an earlier draft cited). Where the two disagree,
one store rendered through two sources reports **two different conflict counts** — no arm, no badge.
The spec already quotes the docstring naming this divergence: *"Never treats `native_memory_dir` as a
project root (that minted a different project id)."* Two honest qualifications: for a **git** project
`project_id_for` keys off `git_common`, which is stable across moves, so the two ids usually coincide
— divergence needs a non-git or moved-root project; and it is **pre-existing**, the three sources
merely making it reachable by more roads.

**Fenced rather than fixed, on the same reasoning as the fence above.** Unifying the two id
derivations changes `project_id_for`'s contract, not this render's, and it reaches every registry-keyed
surface (`--pull`, GC, the journal). What this PR owes is that the divergence be **known** and that no
pin be written as though the count were source-independent.

## A shipped design-of-record this fix falsifies — annotate it, don't leave it to rot

`docs/periphery-parity.spec.md:685` documents the **pre-fix** behavior *as design* and derives a
measured digit from it:

> "`render_html.main` takes identity from `--project`, falling back to `Path.cwd()` … Three cwds,
> three payloads, each correct for its operand: that is the strongest available statement that this
> digit is not a figure."

That spec uses the cwd-derived variation as the *argument* that its payload digit is render-time
state rather than a fixed number — it cites three payloads (the enrolled form, `unknown/false/false`
from a cwd outside any project, and a third from a cwd inside a *different* project) as evidence.
**After this fix all three operands collapse**: that store's owner is recoverable *from the store* —
it renders as enrolled, so §Design's sources name it — and `--store` alone therefore renders the
store's own identity in every one of the three cwds. The third payload is not merely reduced; it
becomes **unreachable by any shape**: with `--store` given, the identity now comes from the store
itself or from a `--project` that resolves *to* that store, so a foreign identity would need the two
to disagree — and a disagreeing pair is Arm D, which **refuses** rather than rendering one.
⚠ **The redirect is not a counterexample, and it is the shape most likely to be mistaken for one.**
There, every project resolves to the store, so the pair **agrees** and the archive renders
`--project`'s identity — but that is the *user's own declaration of the subject*, which
§The five refusal arms records as correct in exactly the configuration that produced the refusal,
not correct by convention. **Measured** on a hermetic `HOME` / `CLAUDE_CONFIG_DIR` /
`CLAUDE_PLUGIN_DATA` with `CM_STORE_OVERRIDE=S`: `resolve_store` returns `S` for project *A*, for
project *B* **and** for `S` itself — the agreement is total, and `resolution_source` reads
`store-override` for all three. ⚠ **And `project_id` still varies with the root** (`p_1b33b4…` /
`p_6e2448…` / `p_52a96b…`), which is what makes the second half of the sentence true: the redirect
freezes the *store* and leaves the *identity* a function of `--project`, so what renders is that
project's identity rather than the redirect's. **The arm RC-5 removes has no analogue under any
redirect**: an identity inferred from where the process happened to stand, which neither a
`--project` nor a redirect can supply.

So this change is a **companion edit**, not a side effect: `docs/periphery-parity.spec.md` gets an
annotation at that line recording that the three-operand argument was a property of the defect, and
that the digit now varies with *when* you render rather than with *how you address the store*. Left
unnamed, its evidence chain rots quietly — and a reader following it would be measuring a behavior
that no longer exists.

## Verification

```
python3 tests/smoke.py && python3 tests/docs_links.py && python3 tests/simulate_accumulation.py
mypy --config-file mypy.ini && python3 tests/validate_manifests.py
```

**All five green on the shipping revision (2026-09-19):** `smoke` 2163 passed / 0 failed,
`docs_links`, `simulate_accumulation`, `mypy` and `validate_manifests` each rc 0.
⚠ **And mypy is not ceremony here — it caught a defect in this change that the other four cannot see
by construction.** A helper's annotation read `Any`, which is never imported; under
`from __future__ import annotations` every annotation is a **string**, so the name is resolved by
nobody until something calls `typing.get_type_hints`, and the 2163-check suite ran **green** with the
error present. The gate is the only surface that reads the annotations, which is why it is a separate
step rather than folded into the suite. Repaired to `Path` — the precise type both call sites pass,
which is the better fix than importing `Any` would have been.

⚠ **Pinning `HOME` is NOT sufficient to control the registry — this is a trap that makes an "Arm A"
pin green for the wrong reason.** `config_root` reads **`CLAUDE_CONFIG_DIR` first** and only falls
back to `HOME/.claude` (`store_context.py:167-172`), and `plugin_data_dir` reads
**`CLAUDE_PLUGIN_DATA`**, which relocates the registry outright (`:175-182`). So a pin that does only
`os.environ["HOME"] = <tmp>` — the in-process pattern at `tests/smoke.py:2047`, `:2082`, `:2292` —
still reads the **developer's real config root and real registry** wherever either variable is set,
and can find a row for a store that has none. The repo already has the right helper and the right
list: `tests/smoke.py:7809-7817 _xp_env(home, extra)`, which pops `CLAUDE_CONFIG_DIR`,
`CLAUDE_CODE_PROJECT_DIR_NAME`, `CLAUDE_CODE_DISABLE_AUTO_MEMORY`, `CLAUDE_CODE_SETTINGS`,
`CM_STORE_OVERRIDE`, `CM_DOMAIN`, `CM_CRASH_AFTER` (`:8488-8493` is the in-process equivalent —
the `HOME` assignment plus the same seven-name pop, and it too omits `CLAUDE_PLUGIN_DATA`).
**`CLAUDE_PLUGIN_DATA` is in neither list and must be added for these pins.** Every pin below is a
claim about the *store's own* identity, so every pin below controls this environment: every shipped
pin builds `env` with `_xp_env` and adds `CLAUDE_PLUGIN_DATA` on top. (This paragraph anticipated
two kinds of pin, subprocess and in-process. **Only the subprocess kind shipped**, and the ⚠ under
*Pins* below records why — the same reason the named fixture changed.) The rule is
stated over the pins, not over an enumerated subset — a subset has to be re-derived every time the
list grows, and neither helper carries `CLAUDE_PLUGIN_DATA` today.

**Pins** (⚠ **fixture: NOT `tests/dashboard_fixture.py`, and the correction is the point.** This
section named that module — synthetic, *"Never reads a user's memory stores"*, it imports
`render_html as rh` at `:19` and already models the identity block with the producer's exact key order
at `:93` — and it is the **wrong** fixture for every pin below. That fixture builds **synthetic
in-process data**; these pins are claims about **which store a process resolves under a given
environment**, so what they need is a real registry, real project directories, and a **subprocess**
env. `dashboard_fixture.py` supplies none of the three, and driving it in-process would forbid the
pins outright: `Path.cwd()` can be patched but `HOME`, `CLAUDE_CONFIG_DIR`, `CLAUDE_PLUGIN_DATA` and
`CM_STORE_OVERRIDE` are read at process start, so an in-process pin **cannot witness** a
redirect-derived identity at all — which is the entire population pins 9, 10 and 11 are for. The
shipped fixture is therefore a hermetic temp tree (`HOME`, `CLAUDE_PLUGIN_DATA`, four real project
dirs, a real `control.sqlite`) with `render_html.py` invoked via `subprocess.run` under
`_xp_env(...)` **plus `CLAUDE_PLUGIN_DATA`** — the ⚠ immediately below — and the pin list is
`tests/smoke.py`'s `v0.4.36 pin N` checks — **59** of them, across the **26** pin numbers this cycle
reached, after round 2 added 15/16/17 (three PRECONDITION + three GUARD/PIN), round 3 added 18 and 19
(the truncated-install rule and the managed-policy route), and round 4 added 20–26 (the path-unusable
class, Arm B, the shared classification, and the dashboard's recovery skip — **12** checks) plus one
**GUARD** inside pin 3 that measures `_restore36`'s promise to leave the shared registry as found.
⚠ **The count is a census of a label, and the label is a string — so it is re-derivable and nothing
more.** A check whose label is spelled differently is invisible to it, which is why every claim about
coverage elsewhere in this document is stated over **the arm a check drives**, not over how many there
are.
**The same correction applies to the in-process pins this section prescribes below**: every pin here
is a subprocess pin, because every pin here is about an environment.):

⚠ **One precondition spans three pins, and it is derivable from a single axis — state it once, here.**
Every snapshot contrast below is carried by **what the varied row supplies** — never by the bare
existence of a `projects` row — and **the same row is not interchangeable between the two producers
that read it**: only one of them requires a supplied domain to be a *real* one (pin 1's ⚠ carries the
measured row-shape table).
**Which** row must carry what is not a list to memorize — it is derivable from **which column the
varied row feeds.** `resolve_store` learns a domain *only* through `enrolled_domain`, which gates on a
real one (`store_context.py:882`, `:892`; `control_plane.py:848-855`), so a row that is not
enrolled-with-a-real-domain is **invisible to it**, and the payload falls back to the unenrolled one
unless the single-sibling rescue below fires;
`store_context_from_registry` instead reads the domain straight off the row (`:1053`). So **enrollment
*with a real domain* is required for the contrast to exist exactly when the varied row feeds the cwd
column**, and a bare real domain suffices when it feeds only the recovered one — where enrollment buys
the three-key *width* rather than the contrast itself (pin 5's ⚠):
- pin **1** — the cwd *is* the store's project, so the store's row feeds the **cwd** column → enrolled
  *with* a real domain (three keys; `active` + a real domain is 0 there).
- pin **9** — the cwd's own row feeds the **cwd** column, because its `no row` binds the *store* and
  not the cwd → enrolled *with* a real domain; its fixture enrols it in `"example"`, which is why it
  measures correctly.
- pin **5** — the cwd does *not* resolve to `S`, so the store's row feeds only the **recovered**
  column, where a real domain suffices and enrollment merely buys the stronger three-key contrast.
  This rule is what pin 5's own ⚠ states as "**weaker, not vacuous**".
Pin 1's ⚠ carries the measurement and the row-shape table; pins 5 and 9 state only their own operand.

1. **The identity pin — a CLI pin, comparing the embedded payload, not whole files.** Two real
   `main()` runs, one store, two cwds; extract the `identity` sub-object from the rendered
   `id="cm-data"` payload and assert the two are **equal**. ⚠ **The fixture is part of the claim, and
   it decides which source this pin samples.** The store must carry a **registry row**: with no row
   and no marker the second run has nothing that verifies and **refuses** (pin 8), so the equality
   would be unsatisfiable — and with a row present, source 1 wins on *both* runs. ⚠ **The row is
   necessary and not sufficient.** The snapshot carries no path and no project id — only `domain_id`,
   `enrolled`, `registry_state`, `cross_project_allowed`, `domain_lifecycle` and a best-effort
   `conflicts` (`store_context.py:97-120`) — so an **equality** pin discriminates *only* if the two
   cwds' snapshots **differ**. Measured (2026-09-18, one process per cell): four cwds with no rows —
   two git projects, a plain directory, and this repo — snapshot to **one byte-identical dict**, so
   **two unenrolled cwds make the equality vacuously green on *both* trees**; a row'd project against
   an unenrolled one differs in `enrolled`, `domain_id` and `cross_project_allowed`. ⚠ **The row's
   *shape* decides whether it carries anything, the shape an ordinary transaction writes is the one
   that carries nothing — and *which* shapes carry anything is a question about a producer, of which
   this pin has two.**
   The **cwd-side** payload — the half that must differ for the equality to discriminate at all —
   comes from `resolve_store` (`render_html.py:413-414`), which sets `enrolled = True` **only when
   `enrolled_domain` returns a domain** (`store_context.py:882`, `:892`). The **recovered store-side**
   payload comes from `store_context_from_registry`, whose `enrolled` is `status == "enrolled"`
   (`:1071`) and whose `domain_id` is `_col("domain_id") or "unknown"` (`:1053`). Measured
   (2026-09-19, one fixture, both producers, one process per cell, fresh `HOME` and git repo per
   cell; keys differing from an unenrolled cwd):

   | row | `resolve_store` (cwd side) | `store_context_from_registry` (recovered side) |
   |---|---|---|
   | `enrolled` + a real domain | **3** | **3** |
   | `enrolled` + `unknown` | **0** | 1 (`enrolled`) |
   | `enrolled` + `''` | **0** | 1 (`enrolled`) |
   | `active` + `unknown` | 0 | 0 |
   | `active` + a real domain | **0** | 1 (`domain_id`) |

   ⚠ **So the prescription is narrower than "enroll it, *or* carry a real domain" — that disjunct is
   vacuous on the producer that governs this pin.** `active` + a real domain is **0 keys** under
   `resolve_store`, so a reader who registers a project and gives it a domain *without enrolling*
   builds exactly the fixture this ⚠ exists to prevent, and it reads green on both trees. **The row
   must `enroll` the project *with a real domain*.** `active`/`unknown` is exactly what
   `upsert_project` writes (`control_plane.py:825-844`, the `"active"` literal at `:844`), so a
   fixture that merely *registers* the project is vacuous on both producers.
   ⚠ **One rescue qualifies the zero rows, and it is narrow.** When `enrolled_domain` returns
   nothing, `resolve_store` re-queries for `status='enrolled' AND profile_id=? AND git_common_dir=?`
   and adopts a sibling's domain **if exactly one row matches** (`:883-892`). The cells above each
   used a fresh single-project repo, so none was rescued; a fixture whose project shares a git common
   dir with **exactly one** enrolled sibling *is*. Do not build one by accident and read the contrast
   as provenance. ⚠ And
   `registry_state` cannot carry that contrast: it flips `absent → healthy` for **every** cwd the
   moment a registry file exists, row or no row. This pin therefore
   asserts that **source 1's** identity is cwd-invariant; it does **not** exercise source 3, whose
   discriminator is pin 8, nor source 2, whose is pin 9. Naming the source is not decoration: the
   three sources must each be exercised by a pin that says which one it samples, or a later reader
   collapses them into one property and the coverage silently becomes single-source.
   ⚠ A whole-file comparison across two
   `main()` calls is a **second-boundary flake**: `generated_at` is
   `datetime.now(timezone.utc).isoformat(timespec="seconds")` (`render_html.py:444`), embedded at
   `:255` and rendered twice by the template (`dashboard.template.html:1184`, `:1506`). Measured:
   two `build_html` calls one second apart are **not** byte-identical. Comparing the sub-payload is
   timestamp-immune **and** tests the `main()` wiring the fix actually changes — which a `build_html`
   unit pin would not. (Pre-fix the two runs differ in the embedded identity and do not raise.)
2. **Arm A** — `--store` for a store with no registry row under a **temp `HOME` with no registry**:
   exit 1 + `belongs to no registered project`. Take the **shape** from the existing subprocess
   template at `tests/smoke.py:15978-15983` (`--project`, `--no-open`, pinned `HOME`, `CM_NO_OPEN=1`)
   — but **not its `env`**: that template builds `{**os.environ, "HOME": …}` with no pops, which the ⚠
   above establishes is *not* hermetic. Build `env` with `_xp_env` (`:7809-7817`) plus
   `CLAUDE_PLUGIN_DATA`. The template is a precedent for the invocation, not for the environment.
3. **Arm C** — a **present but unreadable** registry must **not** produce arm A's message.
   ⚠ **The natural reading of "present but unreadable" under-specifies the fixture, and one reading of
   it routes to Arm A instead.** `classify_registry`'s first check is a `path.is_file()` test that
   returns `absent` for anything else (`control_plane.py:606-607`) — and **a directory is not a
   file**, so a directory at the DB path classifies `absent` and `connect_if_exists` returns `None`
   (`:590-591`): measured `('absent', '')` — Arm A's shape exactly. The fixture must be a **file**
   that cannot be read — chmod-000 (`permission-denied`, measured), garbage bytes (`corrupt`,
   measured), or a locked DB — and it should assert the **classification** it produced, not only the
   message. The corrupt input carries a second trap of its own; §*Arms A and C must not collide*
   states it.
4. **Arm D** — mismatched `--store`/`--project`: exit 1 + `is not the store for`. It must **also**
   cover the **symlinked-store case** (§Resolved-to-resolved), and that one runs the **other way**: a
   one-sided compare gets it wrong by **refusing a legitimate pair**, so this conjunct asserts
   **`rc == 0` and a rendered archive**. Folded into the exit-1 family, the pin would encode the
   defect as expected behaviour (`a-pin-can-require-the-defect`).
5. **The source-1 pin** — `--store S` where `S` **is** named by a registry row, rendered from a cwd
   that does **not** resolve to `S`: the archive carries **the row's** identity, not cwd's. Pre-fix it
   carries cwd's. ⚠ This assertion is a **contrast**, so it inherits pin 1's precondition: the cwd's
   snapshot must *differ* from the row's. Measured, it does — a row'd project differs from an
   unenrolled one in `enrolled`, `domain_id` and `cross_project_allowed`, **provided the row is
   enrolled *with a real domain*** (pin 1's ⚠ carries the table; the default `active`/`unknown` row
   gives `differing keys: []`) — but
   two unenrolled cwds are byte-identical, so a fixture that omits the row **or registers it the
   ordinary way** makes **this** pin vacuous in pin 1's way.
   ⚠ **And this pin's contrast runs on the *recovered* producer, so pin 1's zero does not carry over
   to it.** The disjunction "*or* names a real domain" is vacuous on the **cwd** column pin 1 governs
   (`resolve_store`: 0 keys there); on the **recovered** column this pin contrasts *against*, the same
   row carries **`domain_id`** — 1 key, so a fixture built on that disjunct is **weaker, not
   vacuous**, and still goes red pre-fix, because the cwd side renders the **cwd's own** identity and
   never the row's — `domain_id: unknown` when the cwd is unenrolled, the cwd's own domain when it is
   enrolled in a different one. What requires *enrollment with a real domain* is the **three-key**
   claim above; the disjunct merely buys less.
   ⚠ **And "a cwd that does not resolve to `S`" is not the same as "a cwd that differs" — the natural
   way to build this fixture lands on the vacuous case.** A **sibling project enrolled in the same
   domain** is by construction a cwd that does not resolve to `S`; measured, an `alpha`-enrolled row
   on the store against an `alpha`-enrolled cwd yields **`diff_keys: []`**, because under
   `resolve_store` both sides carry `enrolled: true`, `domain_id: "alpha"` and the same
   `cross_project_allowed`. The cwd must be **unenrolled, or enrolled in a different domain** — the
   operand is the *domain*, not the path. So this pin is not "the cwd is a different directory"; it
   is a claim about the payload.
   This is the registry arm of the property pin 8 tests with no row and no marker.
6. **The root pin — a unit pin, and measured a REGRESSION GUARD rather than a pin.** The recovered
   context's `project_root` is the **row's**
   `current_root`, not the template's. This is the check that catches the `iter_registered_projects`
   trap, and it is the one a future refactor is most likely to break. ⚠ **Measured 2026-09-18: it is
   green on `fbfe07e` as well as on the branch** — the fix did not change
   `store_context_from_registry`, so there was no revision on which it *could* flip. By this repo's
   own rule (*a check added by a fix that cannot fail on pre-fix code is a regression guard, not a
   pin*) it may not be called a pin, and the shipped check says **GUARD** in its own label. That is
   not a demotion of its value: it catches RC-5 re-entering through its own repair, which is the
   failure mode a refactor is most likely to introduce. Labelled **unit** deliberately:
   `store_context_from_registry` `replace()`s 13 fields (`store_context.py:1081-1099`), so the
   recovered context inherits most of its shape from the cwd template — but the `replace()` **assigns**
   five of `identity_snapshot`'s inputs: `project_id` (hence `conflicts`), `domain_id`, `enrolled`,
   `domain_lifecycle` and `cross_project_allowed` (`:1086-1096`). ⚠ **Assigned is not independent, and
   the exception is load-bearing:** `cross_project_allowed` is *computed from* `template.registry_state`
   (`:1093-1096`), so `registry_state` reaches the snapshot **twice** — as its own key and through one
   of those five — and the count of **template-independent** inputs is **four**, not five. That leaves
   the conclusion below untouched (cwd-invariance holds: `registry_state` is registry-file-derived and
   moves for every cwd together — measured across four cwds in three registry states), but it yields a
   precondition none of these pins states: **pins 1 and 6 assert recovered-identity equality across two
   runs, which is safe only while both runs see the *same* registry state.** One `HOME` gives that; a
   fixture that creates or deletes the registry between run 1 and run 2 flips the recovered
   `cross_project_allowed` and would read as a fix defect. The inputs left entirely to the template are
   `registry_state` **and** `plugin_data_dir` — the second not inert: it is the base `identity_snapshot`
   opens `control.sqlite` under (`:112`), so it decides whether `conflicts` appears at all.
   Measured: recovering with a template taken from an **unrelated** directory yields A's
   identity exactly, differing from that template in `domain_id`, `enrolled` and
   `cross_project_allowed` — so the *rendered* identity is cwd-invariant, and it is invariant because
   the row replaces every per-project input rather than because one field happened to be
   HOME-derived. `display_name` appears **0** times in `dashboard.template.html`. The check therefore
   guards a field nothing currently renders, and is honest about being a guard against a future
   refactor rather than a witness to a rendered defect.
7. **The write pin (RC-5c) — one fixture, two sites, and the site is part of the assertion.** Run from
   an unenrolled project B with a marker file, against a store A: `render_html.py <cycle> --store <A>`
   must **not** set `_warned_unenrolled` in B, **and must set it in A**. Then run the **same** assertion
   again through the other RC-5c site, `render_dashboard.py <record> --persist <A>`. ⚠ The second site
   is its **own run**, never folded into the first: a fix that repaired `render_html.py` while leaving
   `render_dashboard.py:1936` on cwd would pass a pin that only exercised the archive path — and
   `--persist` is the dream's **terminal render** — §Design's RC-5c passage states which step
   `SKILL.md:1436-1439` actually marks MANDATORY — and it is reached from a foreign cwd often enough
   that the same module's own comment names that case as its premise, at `:1546-1549`, carried by its
   anchor `v0.4.0 review (R128 clock liveness)`. The
   design also names a third arm — `--store A --project A`, on both sites — and that one is **correct
   pre-fix** (with `--project` given, `:413`'s `_proj` already *is* A), so it is a **regression guard,
   not a pin**. Say which is which.
   ⚠ **Conjunct (b) — "and must set it in A" — is unsatisfiable unless A's own fixture supplies two
   things, and this pin states the marker requirement for B only.** `warn_unenrolled_share` returns
   **early** when `is_unenrolled_share(ctx)` is false (`store_context.py:66-67`), and that predicate is
   `not ctx.enrolled or ctx.domain_id == "unknown"` (`:53-54`); when it passes, the flag write is
   additionally gated on `ctx.native_memory_dir / MARKER_FILE` **already existing** (`:71`) under
   `no_mint=True` (`:86`), falling through to a bare print when it does not (`:91-93`). Measured on
   the recovered context: marker + unenrolled → flag written; **no marker → nothing written**; marker
   + an **enrolled** row → not written. So A must carry a state file **and** recover to an
   unenrolled-or-unknown-domain context — exactly the pair A gets by recovering through **source 2**,
   since `MARKER_FILE` *is* `.consolidation-state.json` (`control_plane.py:165`), the same file
   source 2 reads `project_path` from. A fixture that follows this pin literally and gives A no state
   file produces a conjunct that fails on **correct** code: unsatisfiable rather than vacuous, which
   indicts the precondition, not the fix.
8. **The guard pin — the sharpest discriminator in this list.** With **no registry row and no
   marker**, render `--store S` from two cwds: `S`'s own project dir, and an unrelated project dir.
   Pre-fix both exit 0, and the second archive carries the **unrelated** project's identity — ⚠ but
   in **this** fixture that fact is *not observable*: with no row, every cwd's snapshot is the one
   dict pin 1 measures, so `S`'s owner and the unrelated project render **the same payload**. The
   discriminator here is the **rc and the named fault**, never the identity — which is precisely why
   the ⚠ below asserts run two alone. Post-fix
   run one recovers from source 3 and carries `S`'s owner; run two has nothing that verifies and
   **refuses** (Arm A, exit 1). ⚠ Assert the **second** run on its own: the first is green pre-fix
   too, so a conjunction of the two would read green on both trees and discriminate nothing
   (`a-conjunct-green-on-both-trees-is-vacuous`). This is the pin for RC-5 proper.
9. **The marker pin (source 2)** — a store with **no registry row** but a marker naming a project
   whose `resolve_store` returns this store: renders that project's identity, not cwd's. This is the
   pin for the moved-store population the registry cannot name, and it is the half that makes §Design's
   narrowed capability loss a measured claim rather than an argument.
   ⚠ **As first written this pin was VACUOUS — and the repair belongs to the *fixture*, not to the
   observable.** The fixture is by construction a **no-row** store, and the first repair concluded from
   that *"every cwd's snapshot is the one dict pin 1 measures, so no assertion on the rendered archive
   can separate them."* ⚠ **That widens the constraint's scope: `no row` binds the *store*, not the
   *cwd*.** Measured (2026-09-19, own probe — one enrolled project `R` with a row, one unenrolled `Q`
   with none): the **pre-fix** payload, `R`'s, taken from the cwd, is
   `{enrolled: true, domain_id: "example", cross_project_allowed: true}`; the **post-fix** payload,
   `Q`'s, recovered by source 2, is the mirror image — `enrolled: false`, `domain_id: "unknown"`,
   `cross_project_allowed: false`. **Three keys differ, so the archive does separate them, and it goes
   RED pre-fix.** The fixture that works: `S` carries no row, its marker names an **unenrolled** `Q`
   with `resolve_store(Q) == S`, and the render runs from the cwd of an **enrolled** `R` whose own
   store is not `S`.
   ⚠ **Take the archive — it is not merely available, it is the only observable here that witnesses
   source 2 *specifically***, which `:1259-1261` demands of every pin in this list: `S` has no row
   (source 1 dead) and `resolve_store(R) ≠ S` (source 3 dead), so the marker is the only admitting
   source. The two fallbacks the first repair prescribed are both **source-agnostic** — the write site
   (pin 7's mechanism) witnesses the RC-5c write *relocation*, so a tree with source 2 broken but the
   write fixed stays green there, and the unit assertion is pin 6's shape, reached identically by
   source 1 through `store_context_from_registry`. Keep either as extra coverage; neither substitutes.
   Its **rc** does not discriminate, and that half of the finding stands: the marker is precisely what
   makes source 2 *verify*, so post-fix the run still exits 0 (measured pre-fix: rc 0). **The rc is not
   the discriminator here — the payload is.**
   ⚠ **And the fixture is not free:** `project_path` has exactly **one writer among the shipped
   scripts** — `sync_global.py:1732`, at `--pull` time (`st["project_path"] = str(project_dir)`, the
   slug→path inverse recorded at the one moment it is authoritatively known). It is *read* in seven
   places: five in the scripts (`render_dashboard.py:606`, `:1554`, `:1556`; `sync_global.py:1720`,
   `:1791`) and twice in the tests (`tests/smoke.py:6453`, `:16764`). ⚠ **Scope that count to a
   matcher, because it is method-dependent — an unnarrowed count is the very thing this paragraph
   exists to refuse:** `project_path` followed by an optional `]` then `=`/`:`, over `*.py` at
   `fbfe07e` — **21 hits: 3 writers, 7 readers, 11 comments, docstrings or check labels.** "One
   writer" is the *scripts'* count, not the tree's: the tests construct the key too, as marker
   literals (`tests/smoke.py:16758`'s `"keep-me"`, `:17225`'s `_wrong19`). So the fixture writes the
   marker deliberately; a test that
   assumes a marker is present because a store exists is assuming a field nothing has written.
   ⚠ **It samples the *verifying* case only, by construction** — that is the claim it carries. A
   marker whose `project_path` no
   longer derives here (a store orphaned by a redirect) is a **different population**, and it lands on
   pin 8's arm: no source admits it, and the refusal names `--project`.
10. **The redirect pin — the one that catches a guard that cannot fail.** ⚠ **Its fixture is the
   *family* of routes that make `resolve_store` constant, not the two this spec happens to name —
   and a pin written from the predicate's enumeration inherits the predicate's blind spot.** Three
   instances are proven and each is its own run: `CM_STORE_OVERRIDE`; `autoMemoryDirectory` from
   **user** scope; and **`CLAUDE_CODE_PROJECT_DIR_NAME`**, whose constancy is the least obvious (the
   value reads as a slot, but `:862-863`'s `slot_env or slug_for(root)` discards `root`). Each: with
   **no registry row and no marker**, render `--store <the redirected path>` from an unrelated cwd.
   Pre-fix it stamps that cwd's identity and exits 0; post-fix the round-trip **succeeds** while
   `_project_derived` is false, so nothing is admitted and it **refuses** (Arm A, exit 1). A genuine
   pin, and the only one here that **fails when the second conjunct is dropped while the first still
   passes** — precisely the mutation that reintroduces RC-5. The third instance is not decoration: it
   is the case the predicate's *first* form admitted, so a pin carrying only the other two would have
   stayed green over exactly the hole the whitelist was written to close.
   ⚠ **And the fixture's *absences* are as load-bearing as its store — "no registry row and no marker"
   is not the whole of the precondition.** Two of the three instances are **routable back** (§*Why
   refusal is safe*, measured): a bare project-scope declaration naming the orphan defeats a
   **user-scope** `autoMemoryDirectory`, and a declaration **plus** an operator grant defeats
   `CLAUDE_CODE_PROJECT_DIR_NAME`. So a fixture that happens to carry a project-local
   `autoMemoryDirectory` — or a grant left over from another pin in the same temp tree — routes the
   run onto the **admitting** arm, and the pin then reads green on **pre-fix** code as well: vacuous
   by `a-conjunct-green-on-both-trees-is-vacuous`, not merely weak. The fixture must therefore
   assert the absence of **both**, in the fixture rather than in the pin's prose, and the same three
   names the `_xp_env` rule already requires stay popped. `CM_STORE_OVERRIDE` and policy are the two
   instances this cannot happen to, which is exactly why it has to be stated: the constraint holds
   for the two instances whose redirects a declaration can outrank, and a fixture writer who reads
   only the override instance will not see it.
   ⚠ **Its sibling conjunct must be stated as what it is** — the **negative** one is the pin: the same
   `--store S` from a cwd **outside** the project under a **project-scoped, contained**
   `autoMemoryDirectory` must **not** verify and must **refuse**. The tempting positive phrasing
   ("…must still *recover*") discriminates **nothing**, because recovery means exit 0 with an archive
   and **pre-fix also exits 0 with an archive** — stamped with the wrong identity. It is a
   **regression guard**, never a pin — and it is specifically the conjunct that goes red when the
   predicate is tightened past the design, because that refusal is only reachable *after* the
   round-trip has already succeeded. The negative half cannot detect over-tightening at all: with an
   outside cwd the round-trip fails first, so it refuses whether the predicate is too tight or exactly
   right. Say which is which, per the standing rule.
11. **The tie-break pin — the only witness to the source *ordering*, and only of the row against the
   rest.** One store carrying **both** a registry row naming project *A* and a marker whose
   `project_path` names project *B*: render `--store <that store>` and assert the archive carries
   **A**'s identity — not `B`'s, and not cwd's. ⚠ **It is blind to the order *between* sources 2 and
   3** — swap those two and it stays green, because its fixture's cwd is not a candidate at all, so
   the marker is reached either way. A witness to *that* pair would need a fourth fixture shape (no
   row, a marker naming B, a cwd whose project names C); nothing in §Design turns on it beyond "most
   specific first", so the claim is narrowed rather than a pin added.
   ⚠ **Every other pin here is blind to this by construction** — pin 5's store carries only a row,
   pin 9's only a marker, pin 8's neither — so a one-line reorder that puts the **marker ahead of the
   row** keeps pins 1–10
   **green** while inverting *"the first to verify wins"*. That is what earns it a fixture rather than
   being a
   check built ahead of need: the fixture is not new surface, it is pins 5 and 9's already-mandated
   artifacts placed on **one** store in the same temp tree under the same `_xp_env` +
   `CLAUDE_PLUGIN_DATA` environment, and it witnesses a rule already written. It is a **pin** — pre-fix
   it is red, because cwd's identity is stamped — but red for pin 5's coarser reason, **not** for the
   ordering, so its discriminating power is over *future* reorders. State that plainly rather than let
   it read as a witness to a defect it does not witness.

12. **The path-fault pin (the Arm A fix), and the reason it is a SIBLING of pin 4 rather than a
   duplicate of it.** A `--store` naming a path that does not exist, passed with **no** `--project`:
   assert exit 1, that `does not exist` is named, and that `belongs to no registered project` is
   **absent**. ⚠ **Pin 4 already had a path-fault conjunct, and it did not cover this** — it passes
   `--project`, which is the one flag that makes the existence test run, so it witnessed the pairing
   branch's path fault and left the store-alone branch's registration fault live. **Both go red
   pre-fix** (the store-alone form exits 0 and renders), so the pair is two pins over one fault in
   two shapes, not one pin over two faults. That distinction is the whole finding: a pin covers the
   **call path** it takes, and pin 4's label named a fault its fixture could not reach alone.

13. **The absent-store recovery pin — a PIN, and it is a pin only because its discriminator is the
   IDENTITY.** A registry **row** naming a store that has since been **deleted**: `--store S` from an
   unrelated cwd must not merely render (pre-fix renders too) — it must carry the **row's** identity.
   This is the first half of the position claim, and it fails if the existence test moves **above
   source 1**. Its PRECONDITION asserts both that the store is really gone *and* that the row's
   `native_memory_dir` still names that exact path, since a row naming a different path would
   recover nothing and the pin would read red for a reason it does not describe.

14. **The absent-store derivation guard — a GUARD, and labelled one because the measurement says so.**
   An absent store that the **cwd derives**: a project that has not dreamed yet, since the store is
   not created until it does. Source 3 admits it by round-trip, and **both trees stamp the cwd's
   identity** — pre-fix because cwd is all it ever asked, post-fix because cwd *verified* — so nothing
   here can flip. It is the second half of the position claim, and it is worth a check precisely
   because pin 13 alone would leave the suite green with the existence test moved above **source 3**
   while refusing a legitimate invocation. Two halves of one claim landing on opposite sides of the
   pin/guard line is the ordinary case, not an inconsistency: **the line is drawn by what the
   measurement shows, and it was drawn twice here rather than once for the pair.**

⚠ **An existing source-text pin constrains every new pin above.** `tests/smoke.py:15918-15921`
asserts `_smoke_src_ft.count("--no-open") >= _smoke_src_ft.count('"render_html.py"')` over
`smoke.py`'s own text. Any new subprocess-style `"render_html.py"` string literal added here must
carry `--no-open` on that accounting, or this pre-existing check fails.

**A test that inverts rather than moves.** `tests/smoke.py:2914` calls
`main([cycle, "--store", <temp store>, "--out", ...])` and asserts `rc == 0`. It is not merely a test
that breaks — it is **the defect's own witness**: its store is a fresh temp dir with no registry row,
so post-fix it refuses on **every** machine, and pre-fix it is stamped with whatever the ambient
`HOME` resolves to (the repo's `personal/enrolled` on a developer machine). The fixture runs with the
**ambient** `HOME` — `smoke.py:2890-2919` contains no `HOME` override, the nearest being far outside
that range — so it has never been hermetic. Its stated purpose (a FAILED `webbrowser.open` writes no
marker, RC-89/n4) is unrelated to attribution, so it is **restructured** to render under a pinned
`HOME`, and its **old shape becomes arm A's pin** (pin 2). The fixture does not vanish; it inverts.

**Not a pin.** `tests/smoke.py:7579` is `run_beta.py --store`, not a `render_html` site. The vendored
canary `plugins/dream-beta-tester/fixtures/canary-v0.1.19/` was checked too: it contains **no
`render_html` invocation and no `render_html` module at all**, so the byte-faithful v0.1.19 skill
cannot be broken by this change.

**Existing pins that must still hold:** `tests/smoke.py:1938` pins `_store_for` for `--store` /
`--project` / neither — `_store_for` itself is **unchanged**, so it holds. `:3246`/`:3250` cover the
neither-flag arm above and must stay green **without edit** — guaranteed by the scoping condition in
§The contract, and by a property of the *dispatch* rather than of the environment: the fix's recovery
consult is reached only on `--store`-without-`--project`. Those runs do **open the registry** —
`resolve_store` always does — so *"they never open the registry"* would be false, and the distinction
is what stops this guarantee from being read as a blanket health-check precondition over all four
shapes.

⚠ **An earlier draft of that sentence read *"no refusal arm guards the neither-flag shape"*, and this
round falsified it by shipping the arm.** Two refusals now guard it (`except OSError` and
`if cwd_ctx is None`), both spellings of one condition: `Path.cwd()` raising `FileNotFoundError`
for a directory deleted under the process, and `_canon(cwd)` returning `None`. The guarantee survives
— but for a **better reason than the draft gave**, and the difference matters: it is not that nothing
guards this shape, it is that *the guard's operand is a live temp directory*. A claim of the form
*"no arm reaches here"* is falsified by the next arm; a claim of the form *"this arm's precondition is
absent from the fixture"* is re-checkable, and it is the one that was true all along. Pin 22 is the
instance that drove this home: it drives the **same three shapes** and shows the arm firing, so the
green cells and the red cell differ only in their subject, never in their dispatch.
