# Record post-state — design-of-record

> **Reading the citations.** Every `file:line` below is **`b63b474`-numbered**. Resolve it against
> that commit — `git show b63b474:<path>` — and **never against the working tree**, which has moved
> them.

**Status: revision 11 — for adversarial review** (2427 lines; revision 10 read 2266, revision 9 read
1965, revision 8 read 1941, revision 6 read 1657). Target release: **v0.4.30 (patch)** — a repair to
fields that were always meant to be measured; no schema, flag, or install-contract change.

This spec closes the record-honesty class the 2026-09-14 audit found: **a cycle record's post-state
was never owned by anything.** It is the second of three staged cycles; Cycle A (dream-teeth
coverage) landed as v0.4.29, and the index-periphery cycle is a separate spec on its own branch.
The fourth item the standing plan listed under this cycle — the stale `AGENTS.md` cell and the docs
gate that misses it — is **split off by decision** (§6), so this spec's scope is the post-state only.

Every measurement below was re-derived on branch `fix/record-post-state` at **`fa91254`**, the merge
commit of the v0.4.29 release — not carried from the audit. Where a figure is re-derivable only from
a live uncommitted store, that is stated as such.

**Revision 2 is a re-scope, not an edit.** Round 1 of adversarial review returned three independent
reports; two of them found, separately, that §2.2's key set was **derived by the wrong criterion**
and was therefore not closed under the measurement it rewrote. Chasing that finding to the source
dissolved the largest part of the design: the refresh does not need `build_context`, a project dir,
or any store→project walk at all, because **the `--persist` argument *is* the store handle** (§C7).
The Amend ledger records every finding and what it changed.

**Revision 3 folds in round 2, whose defining failure was carrying a measurement across an edit.**
Three of round 2's findings cited numbers that belonged to revisions which no longer existed — the cost
of re-stating a figure without re-deriving it, and the same discipline this repo already applies to a
pin's RED count. Every affected figure in §C3, §C8 and §C7 was re-measured rather than corrected by
argument; the results are in the Amend ledger. Round 2's highest-severity finding — the refresh can
fabricate an all-zero post-state — produces a **guard**, not a pin, which is why the pin count is
unchanged from revision 2.

**Revision 4 folds in round 2's surviving findings — and exists because round 3 proved the revision
boundary is real.** Round 3 attacked revision 3 and returned two CONFIRMED major findings; both were
**already fixed**, because the reviewers read the file at 990 lines while round 2's fold-in was still
running, and it is now past 1200. That is not a wasted round — a report bound to a superseded revision
is *evidence about the revision*, not about the defect, and finding that out is what the round was for.
**The consequence is a rule: a finding binds to the revision it measured**, exactly as a pin's RED
count binds to its triple. This spec cannot state its own digest — writing the hash in changes it — so
a revision is identified here by its round label and its line count, and the digest is circulated with
the review request out of band; a reader who wants certainty computes the file's own hash and compares.
The round-2 findings folded here are in the Amend ledger with their re-derivations, together with **two
claims that did not survive re-derivation**, recorded as refuted so they are not re-filed.

**Revision 5 folds the r3-claims round — six findings, all six live, none bound to a superseded
revision.** Five repaired enumerations and preconditions that had outrun their sets. The sixth is the
one that matters, and it is the **opposite of what this round first concluded**: §C3's central evidence
was briefly declared refuted on the strength of the archive, and re-measuring before folding showed
the claim was right and the refutation was the error — because **the newest record exists in two
divergent copies**, the log holding `1746 → 1746` and the `--cycle` file `1746 → 1694`. That is now
the section's finding rather than its retraction, and it yields the rule this revision adds to the
pins discipline: **a census binds to the artifact it read.** The round's own error is recorded in the
Amend ledger beside the finding it produced, because the error — quoting a number without naming which
of two copies it came from — is the exact class this cycle exists to close.

**Revision 6 folds the mechanism lane — five findings, all five confirmed, and a lesson about which
text is worth attacking.** The lane filed against revision 3 and was re-checked against revision 5
rather than accepted or dismissed on the binding; every cited passage was located in the current text
and checked at the source, and all five survived **verbatim** — the intervening folds changed the
prose around them without touching a word of what they attack. Four of the five sit in text revision 5
itself added, which is the round's real yield: **a revision's new closure arguments are its least-tested
surface**, and this one closed six findings by writing fresh reasons, four of which outran the operand
they name. The five are the Out-list's umbrella (false for three of its ten members — the *second* time
that specific label misdescribed its own set), the `slug_orphans` level (the projects root is the
store's grandparent, and the real unavailability is identity, not distance), the container-absent skip
(keyed on `budget` while the row is gated on `budget.index`), condition 1's comparison against a
possibly-retired budget (14 of this store's 55 records carry the retired `1200`, 13 of those without a
`remediation` block), and §2.6's hierarchy residual (§5 deferred to §2.6 while §2.6 said the opposite).
All five are repairs to *stated reasons* or operand choices; none adds a check that flips on pre-fix
code, so the pin census holds at **17 items, 7 pins, 10 guards**. The lane's non-findings are recorded
in the Amend ledger as well — including the one claim it declined to file because it could not
substantiate it, which is the same discipline this file applies to its own drafts.

**Revision 10 folds the round-3 review — six findings, all six confirmed, all six in the code this
spec specifies.** Five of the six are fixed in `render_dashboard._refresh_post_state`; the sixth is a
claim about that function's own docstring. The round's finding, stated once: **the refresh was closed
under the leaves it rewrote and not under the relations between them.** Round 1's defect was a frozen
leaf beside a fresh one it is computed from (`after_bytes` vs `cliff_pct`), and the repair closed
*that* pair — but the closure was argued leaf by leaf, and a leaf can be a **comparison**: `over` is
`after_tokens > budget_tokens`, so refreshing the numerator alone paired a live measurement with a
seed-time snapshot of a module constant. Measured, `budget_tokens` takes two values across this
store's 55 records — `1200` on 14 of them, `1500` on the other 41. The same shape, one level further
out, produced the rest: `remediation.over_ceiling` (a **measurement** this spec had filed as a triage
verdict, on the strength of its container rather than its computation) was frozen at seed time and
never re-derived, so a de-bloated store rendered a red HARD CEILING alarm beside the healthy gauge
that contradicted it; the over-budget warning's guard read `budget.remediation`, a key **no writer in
the codebase produces**, making it dead and its message false on every over-target persist; the
`schema_drift` preservation branch fabricated `advisory_stranded_globals: 0` on a legacy-shaped seed,
authoring a measured-looking value for a field the `canonical_stems=None` path cannot measure; and
the precondition rebuilt `store / "MEMORY.md"` where `store_local_index` builds the same path a line
later — the repo's own weakest-enforcement-site rule, broken at the site whose docstring invokes it.
**The class the pins structurally could not see**: every one of the seventeen items tests a leaf's
**own** movement — *dyadic* — while four of these six exist only in a **triadic** relation, between
two leaves, or between a leaf and its reader, or between a leaf and the claim that it was measured. A
pin per leaf cannot falsify a claim about a pair, and that is a property of the pin *shape*, not of
how the pins were written. The five new items are therefore stated as relations, and they take the
census to **22 items, 10 pins, 12 guards**. **Two of the twelve guards now name revision 9 as a
measured referent** — the first time a guard points at a real revision rather than a hypothetical one
— because the implementation the first seventeen items certify was itself put through review. **Two
defects in round 3's own checks were found by running them rather than by reading them**, and both are
in the ledger: P19's fixture never cleared the warning's first operand (120 lines measured 1152, and
the arm it was supposed to exercise never fired), and P19's *original* form asserted a warning
**count** — which passed on revision 9, because a revision reading the operand off the wrong block
also fires exactly one warning, from the wrong arm. That is this repo's own recorded norm inverted by
its own item: **a count says how many moved; a probe says which.**

**Revision 11 audits this branch's own claims — and falsifies one of this file's own counts.** Every
claim this cycle added about its own code was followed to its source: each named count, each
enumeration, each "never / only / single / exactly N", and each check's **name set against its
condition**. **Nine failed, and no *executing* gate could have reached any of them.** Eight are claims
in text that nothing executes — A1 and A3 (the archive comment and its reader count), A4 (the skill
instruction), A5 (a check's *label*), A6 (this file's §5), and A7, A8 and A9, the three the sweep
found only once it was turned on the entry reporting it. **A2 is the one that is not text at all**: a
binding whose value *agreed* with its source, so only a check on the source's *shape* can see the gap
that a comment ("mirrors `memory_status`") was papering over. A
`render_dashboard` comment asserted the HTML archive "never had this defect because it meters from its
own constant": measured, the archive's gauge takes *both* of its operands from the record and uses the
constant only as a fallback. Two `render_html` constants were unpinned literal copies of
`memory_status`'s **in a module that already imports `ms`** — the same comment's own "mirrors
`memory_status`" was true as an intention and held by nothing. That comment's "all **three** readers"
is **six** — the same `grep -rn over_ceiling` census §5 now records. SKILL.md step 7's "the ONE budget
leaf the script does not own" is false twice over — `budget.global_claude_md.*` and
`budget.claude_md_hierarchy` are equally out of the script's reach — and false in the direction that
acts, since its reader is the model one step from authoring the value §2.3 forbids. And a check's label
claimed "*a live reference, not a hardcoded copy*" while its condition was `==`, which a copy passes on
the day it is written. A6 is this file's own: §5 recorded `over_ceiling` as having "exactly two
readers (the alarm line and `render_html`'s gauge)", and the census is **six sites in three files**.
**The spec's count was wrong in the direction that matters** — it was offered as the reason the repair
"cannot invent a display", and one unexamined reader is exactly what would let it. **The same sweep
confirms the neighbouring count it could have falsified**: `ceiling_tokens` reads at **one** site, the
`⚠ HARD CEILING` alarm. That pair is the only evidence that these numbers came from a census and not
from a prior — a method that lowers one number and leaves the next one standing.
**The last three came from turning the sweep on the ledger entry that reports them.** A7's probe, re-run
as worded, prints the *pre-fix* number on the repaired tree. A8's renumbering left two live `F5`s in the
prose it did not reach. A9 counted the A-list from the wrong end. A record of a sweep is a text
surface like any other, and this one had been held to none of the sweep's own rules — which is the
finding, because a ledger is exactly the document a reader trusts *instead of* re-running the census.
**Three of the nine are one gap seen from three sides.** A2 is the unpinned binding, A5 the check that
appeared to hold it, and A7 the evidence offered for the repair: because the constants' values
*agreed* on the day, the only things asserting they would keep agreeing were a comment ("mirrors
`memory_status`"), a check whose **name** claimed reference-ness while its **condition** compared
values, and a probe description that cannot tell the repaired tree from the unrepaired one. So its
repair is one structural thing — bind the three names to the one definition, pin that binding where
the property actually lives, in the source, and **state the probe in the form that discriminates**.
**Census: 23 items, 11 pins, 12 guards** — P23 added, the equality half replacing and widening
the v0.1.66 check it succeeds, so the census moves by exactly one. **None of the nine changes a rendered
byte on this tree**: the constants agreed on the day they were copied, which is precisely why nothing
noticed they were copies.

**Revision 9 audits the ledger rather than the claims.** Round 4's three lane reports were re-read
against this file, and every repair the ledger says the round made was re-derived at the text instead
of taken on the ledger's word — **all of them landed**, by direct grep of the repaired sentence in each
case. **Two entries did not reconcile, and both are in the accounting rather than in a claim about the
product.** The round-4 header attributed the container-absent-skip refutation to `r4-rev5`, while the
entry forty pages below attributes it to `r4-repairs` and gives `r4-rev5` a different first refutation;
the header now names the round's two and each lane's own. And the ledger's row for the WARN-input
sub-finding read *"the sentence was right"* without naming the sentence, while §C3 records the earlier
revision's gloss on that same subject as **false** — the two are different sentences, only one of them
is a claim about the WARN's input, and the row now states the measurement (`main` takes the record from
`paths[0]`/`sys.stdin` and feeds *that* to `validate_cycle_record`) and says which sentence survives.
The class is this spec's oldest one, one axis over: **an entry that does not name its referent is not a
record of a finding** — the same rule as V-3, applied to the ledger instead of to a census. **Pin census
unchanged: 17 items, 7 pins, 10 guards.** Both defects arrived from auditing the record that documents
round 4's product, which is the round's own thesis one level up.

**Revision 8 is revision 7 plus the two defects that writing the checks found** — §3's P9 patch point
and §3's P15 check itself, neither of which a lane could have caught, because a sentence that *sounds*
like a mechanism reads as one until something has to execute it, and a check that asserts the right
thing about the wrong subject passes on every revision. Both are in the round-4 ledger (its fifth and
sixth entries), and both were found by the mutation matrix rather than by a reading. Nothing else
moved: the pin census, the design, and every other check are revision 7's.

**Revision 7 folds three lanes run in parallel against revision 6 — 15 findings confirmed, 4 refuted —
and yields one rule and six defects found here rather than by a lane.** The lanes were given
**disjoint surfaces** rather than the same file read three ways: **`r4-sweep`** took internal
consistency (**8 confirmed**, every one of them a contradiction between two places in this file — P2's
row count, §C2's `health` mechanism, §C4's `≈0/4000`, the round-3 ledger title, §2.3's ceiling
universal, §5's `_over` operand, §5's "eight files", §C1's "token pair" noun), and reported a further
set **unsubstantiated** rather than filing it; **`r4-repairs`** re-checked the five §2.2/§2.3 repairs
the mechanism round produced (**3 confirmed, 2 refuted**), declining to file a denominator it could not
stand behind; **`r4-rev5`** re-derived §C3's central evidence end to end — **the finding confirmed, its
mechanism demonstrated, the census and the partition confirmed, two findings refuted** (a sub-finding
about the WARN's input, and §5's "historical six"), and two ledger rows flagged as log-only without
naming their artifact, which is V-3 in miniature. **The round's two refutations worth naming.** The
container-absent skip — `r4-repairs`' first — is not a live gap: `tests/dashboard_browser.py` pins it
*not* to fire, asserting the visible count of `#network-blk .budget-grid` is **0**, because the
template's `#m-index` writes land in permanently-`hidden` DOM — so the archive is evidence *for* the
repair, not against it. And §5's "historical six" is refuted by the WARN being **reader-independent**
of both the log union and the archive. **The rule is V-3: a figure that does not name its artifact is not a
measurement.** The r3-claims round established that for censuses; this round found **three more
figures** — §2.2's `recall_facts` margin and two §C3 ledger rows — that read the log union and the
archive as one number, so the rule binds the figures *inside* a named census as well as the census
itself. **The six self-found defects**: P15's precondition was **inverted** — the shape it named as its
precondition is the table's single *vacuous* row, and both earlier revisions had it backwards; §2.3
carried a paragraph describing the `ceiling_tokens` default for a line of code this revision no longer
has; §2.3 said the nine leaves live in "four mappings" where the seed writes three; **§3's P9 named a
patch point that does not exist** — *"the second of the nine measurements"* conflated nine **leaves**
with two **calls**, and the seven index leaves are one dict literal, so there is no second call to
patch; **§3's P15 was implemented as the wrong check** — the row-count *predicate*, which is P15's
stated precondition and is green on both trees, instead of the real heal the item's own text
specifies; and one of this
round's own edits put a real home path into a public-repo file, caught by an audit of my own text rather
than by any lane. **No finding of the fifteen, and none of the six, adds a check that flips on pre-fix
code**, so the pin census holds at **17 items, 7 pins, 10 guards** and §3's list is unchanged.

## §1 Context (measured)

`memory_status.seed_record(ctx)` builds the cycle-record seed — its docstring: *"The cycle-record
SEED — before-values + scope + provisional rigor, for render_dashboard.py."* For a whole family of
keys it writes the **post**-state from the same single Phase-0 `ctx` reading that produces the
**pre**-state.

### C1 — the after-side is the before-side, by construction

Six pairs, twelve keys, each `after` character-for-character the same subscript expression as its
sibling `before`:

| parent path | both sides seeded from |
| --- | --- |
| `budget.claude_md.{before,after}` | `ctx["repo"]["CLAUDE.md"][0]` |
| `budget.claude_md.{before_tokens,after_tokens}` | `ctx["repo"]["CLAUDE.md"][2]` |
| `budget.index.{before_lines,after_lines}` | `ctx["index_lb"][0]` |
| `budget.index.{before_bytes,after_bytes}` | `ctx["index_lb"][1]` |
| `budget.index.{before_tokens,after_tokens}` | `ctx["index_lb"][2]` |
| `budget.recall_facts.{before,after}` | `len(ctx["fact_files"])` |

`before == after` is not a stale value that happens to be wrong; it is **the only value that
expression can ever produce**. The adjacent `budget.global_claude_md` block carries an explicit
comment declaring the absence of this pattern to be intentional — *"USER-GLOBAL
~/.claude/CLAUDE.md — read-only / no before↔after (the skill never edits it)"* — so the codebase
already knows the distinction. `claude_md`, `index` and `recall_facts` just do not honor it.

**`marker` is NOT in this family and must never be swept in.** It carries `before_commit` /
`before_timestamp` against differently-named `commit` / `timestamp`, and those genuinely differ
(`ctx["last_commit"]` from the state file vs. `ctx["head"]` from `git rev-parse HEAD`). A naive
`before == after` value check would false-fire on every record.

**This is a claim about the seed, not about every record in the log — and the two must not be read as
contradicting.** §C3 measures what the newest record actually carries, which is an after-side partially
overwritten by the prose refresh. Both hold at once: the seed cannot *produce* a difference, so any
difference a record shows was written by something else — and the "something else" is the unverified
prose path this cycle replaces. **29 of the 55** embedded records carry an unequal `budget.index` pair —
at least one of the three `after_*` leaves differing from its `before` — so the overwrite is not rare
(26 equal; restricted to the **token** pair alone the partition is 28/27, the difference being one
record at `bytes 3110 → 3107` with `tok 758 → 758`). Measured at `fa91254`. §C3's contribution is
showing that the overwrite is **partial**,
stopping exactly at the instruction's coverage.

### C2 — a second, unconfounded defect: the block has no `before` twin to betray it

`maintenance` and `budget.claude_md_hierarchy` are seeded as **direct copies** of Phase-0 `ctx` values,
and `health.schema_drift` is a third — `"schema_drift": ctx["schema_drift"]` — with no `before`
counterpart and no filter, no subsetting. **`health` is not one of them, and an earlier revision said
it was.** The seed is `{"index_pointers_ok": True, "broken": [], "dangling_links": [],
"slug_orphans": [o["slug"] for o in ctx["slug_orphans"]], "schema_drift": ctx["schema_drift"]}`: one
`ctx` copy, three hard-coded constants, and a *projection* — which is a filter, in the exact words this
sentence denies. §5 already states the hard-coding correctly and the amend ledger repeats it, so the
universal here contradicted the same file twice; the *conclusion* (nothing refreshes these blocks)
survives either reading, which is why the repair scopes the mechanism rather than the finding.
Nothing refreshes them, so nothing in the artifact even *looks* wrong: `C1`'s fields at
least carry a `before` twin, so a reader has two numbers to compare — and the tell-tale is visible in
the newest record, whose `claude_md` pair reads `3986 → 3986` while its `index` pair reads
`1746 → 1694`. A frozen `health` block offers no such comparison and renders as a plausible number.

Measured against the live store, the newest record's `health.schema_drift` versus a fresh
`build_context`:

| field | logged | live | direction |
| --- | --- | --- | --- |
| `missing_node_type` | 0 | **2** | hides 2 |
| `index_mismatch` | 1 | **4** | hides 3 |
| `advisory_no_scope` | 11 | **16** | hides 5 |
| `advisory_no_origin` | 0 | **2** | hides 2 |
| `malformed_scope` / `malformed_origin` / `advisory_stranded_globals` | 0 | 0 | — |

**Four of seven fields under-report and not one over-reports.** That asymmetry is the whole point:
a merely *stale* snapshot would be free to under- or over-report depending on which way the store
moved. Every mismatch running toward concealment is what a frozen value looks like when the thing it
measures only accumulates findings.

`index_mismatch` can be bounded **without** the confound, from mtimes alone. Three of its four
offenders carry mtimes of `2026-08-29`, `2026-09-01` and `2026-09-02`, all earlier than the pass
floor (the previous record's marker, `2026-09-12T21:28:57Z`), so they were present and unchanged at
Phase 0 — a floor of **3** against a logged **1**.

**Pointed at the other three fields, that same bound refutes the universal that used to close this
paragraph.** The earlier text read *"for the other three fields every offender was created during the
pass"*. The counterexample is `quoted-anchor-cannot-be-unique.md` — an `advisory_no_scope` offender whose
mtime is `2026-09-12T20:00:00Z`, **1h29m before the floor**, so it was present and unchanged at Phase 0
and cannot have been created during the pass. Re-derived 2026-09-14 over every offender of all four
fields (operand: `ctx["fact_files"]`, the same list `build_context` feeds `schema_drift`), the shape is:
`index_mismatch` **3 of 4** pre-date the floor, `advisory_no_scope` **1 of 16**, `missing_node_type` and
`advisory_no_origin` **0 of 2** each. So the honest form is the weaker claim the measurement supports
rather than a universal — the floor argument carries `index_mismatch` on its own, and for the other three
the evidence is consistent with staleness without *excluding* a falsehood, which is what the clause after
it already conceded. The mtime bound was available and was pointed at one field in four; the repair is to
state what the one measurement shows, not to go looking for a stronger tool.

**The live column above is exact and needs no repair** — `build_context` re-run on 2026-09-14 returns
`missing_node_type 2`, `index_mismatch 4`, `advisory_no_scope 16`, `advisory_no_origin 2`, field for
field the table's live column, and its four `index_mismatch` offenders carry exactly the three stated
mtimes. Only the *universal* was wrong, not the census beneath it. (A first pass at this re-derivation
reported 17 / 3 / 3 and was itself wrong: it differenced the fact stems against `index_fact_names`, where
`build_context` passes `placed_fact_names`. The mislabelled-operand failure this spec is about is easy to
commit *while auditing this spec* — the count moved by exactly the one file whose placement differs.)

### C3 — CONFIRMED, and the record turns out to exist in two copies

An earlier revision of this section claimed the strongest available evidence: the newest record's
`budget.index` pair (`1746` / `1746` → delta **0**) contradicts its own `audit.operations[]` row
(`token_delta` **−52**), so *"the record disagrees with itself."* A revision between that one and this
one declared the claim **refuted** — it had read the archive, seen `1746 → 1694` (−52), and concluded
the mirrored pair "is in no artifact." **That refutation was wrong, and its error is the finding.**

The mirrored pair is in the artifact that matters most. The newest record exists in **two divergent
copies**, and they are one record — same marker `2026-09-14T00:36:54.397Z`, same commit `308e15bc`:

| copy | where | `before_tokens → after_tokens` | `before_bytes → after_bytes` | vs its own audit (`−52`) |
| --- | --- | --- | --- | --- |
| **the pid log** | `ops/p_e1decb8c…/.consolidation-log.jsonl`, line 21 | `1746` → **`1746`** (Δ **0**) | `7161` → **`7161`** | **contradicts** |
| **the file** | the `--cycle` record, as embedded in `dashboards/index.html` | `1746` → **`1694`** (Δ **−52**) | `7161` → **`6950`** | **agrees** |

Both halves of the original claim are therefore true and both halves of the refutation are false:
`1746/1746` exists (in the log), and `−52 = −52` also exists (in the file). The two numbers are
comparable on the merits — `audit_snapshot`'s inner `_add` labels the store's `**/*.md` glob as
`memory/…`, so `memory/MEMORY.md` **is** the auto-memory index, stamped with the same `est_tokens`
that produces `budget.index.*_tokens` — and the log's pair **is** internally inconsistent.

**Which copy is false is settled by a third artifact.** `render_html` writes a per-file diff sidecar
per dream; for this marker it records that the index moved, at `@@ -2,11 +2,9 @@`. So the file did
shrink, the audit's `−52` is right, and the log's `after_bytes = 7161` — *identical to its own
`before`* — is **false when written**. The log holds a mirrored Phase-0 read.

**The mechanism is at `assemble_cycles`, and it runs the opposite way from what §2.5 assumed.** Its
dedup prefers the passed-in record on stamp equality — `cycles[-1] = rec`, commented *"the current file
is the fresher expression."* So the archive is **correct** here, and only because file-wins happens to
be the right rule in this instance. C5's premise held that the *file* goes stale on a duplicate and
drags the log down with it. Measured, staleness ran the other way: the **file is fresh and the log is
stale**. The rule that saved the archive is the same rule that would bury a fresh log entry if the
direction ever flipped back — it is a coin-flip dressed as a preference, because nothing measures
which side is fresher.

**And the divergence is re-derivable as a census delta** — the sharpest form of this finding, because
it needs no argument about which copy a reader "should" consult:

```
                       checkable   consistent   CONTRADICT
  the log union        31          25           6
  the archive          31          26           5
```

**`the log union` is not the `the pid log` row above, and the two differ by 34 records.** The census
reads `iter_store_cycle_log(store)`, which unions `cycle_log_read_paths` — three files, deduped by
`(marker.commit, marker.timestamp)` — giving the **55-record** series; the pid log is a **21-line**
file, so a re-deriver who follows the nearer citation gets `31 > 21`, an impossible count. An earlier
revision used the bare word "the log" for both, three lines apart, in a section whose stated finding is
that a census which does not name its artifact is a coin-flip with a number attached. Named here, and
in the ledger rows below, for that reason.

Thirty-one checkable records in both, and the difference is **exactly one record** — the newest, the
only record whose two copies disagree on this invariant. The five contradictions common to both
artifacts predate this pass (`2026-08-29` … `2026-09-05`), so the pin remains a **legacy-tail** pin;
the sixth exists *only* in the log, and it is this pass's own record.

That matters because the log is the copy the tooling reads. `render_log.py` / `cm log` render the log.
**The reconcile WARN of §2.4 does not.** An earlier revision wrote that it "runs against the record as
loaded — which is the log's copy", and that is false in a way that inverts §2.4: `render_dashboard.main`
takes the record from `paths[0]` (`--cycle`/argv) or `sys.stdin.read()` and feeds *that* to
`validate_cycle_record` — the same copy the archive embeds, never a log line. Measured consequence: on
this very record the pin is **silent** in every surface that can reach it (the render-time copy is
`1746 → 1694` = `−52`, consistent), and the log's contradicting copy is read by `cm log` alone. §2.4
three pages on says exactly this — *"validates the record being rendered and never an archived one"* —
so the sentence contradicted its own section. What survives from it is the `render_log.py` half, which
is true and which is why the divergence is nonetheless worth repairing: a reader who opens `cm log`
sees the pair the archive does not show.

**The error is worth recording for its own sake, because it is this spec's recurring failure in a new
costume.** The claim was measured and the measurement was correct — of the archive. What failed was
that *"the record reads X"* was left **under-specified in the direction the whole cycle is about**:
when a record exists in more than one copy, a census that does not name its artifact is not a
measurement, it is a coin-flip with a number attached. The same rule the pins section already applies
to revisions — *a finding binds to the revision it measured* — applies one axis over: **a census binds
to the artifact it read.** (The route is also instructive: the false step was inferring "no artifact
contains it" from a search that had excluded `.jsonl` — the fourth appearance of a line-based filter
producing a false negative in this cycle, and the reason §3 states its normalization rather than
assuming it.)

**What this does to the cycle's premise is a sharpening, not a re-basing.** The defect is still that
the after-side is unowned. It is now additionally measured that the mandate's **coverage is partial
even where it does run** — the file's copy shows `index` and `recall_facts` refreshed while
`claude_md` reads `3986 → 3986` and `health.schema_drift` sits frozen at the seed's `0/1/11/0` against
a live `2/4/16/2`:

| pair | the file's copy, before → after | refreshed? |
| --- | --- | --- |
| `budget.index.*_tokens` | `1746` → `1694` | **yes** — and the delta matches the audit row to the token |
| `budget.recall_facts` | `31` → `33` | **yes** — and `33` is the count the live store held |
| `budget.claude_md.*_tokens` | `3986` → `3986` | **no** — or genuinely unchanged; the record cannot say which |
| `health.schema_drift` | frozen at `0/1/11/0` | **no** — live at that moment was `2/4/16/2` |

So the prose refresh **ran**, and stopped exactly where the instruction stops. That is C4's *"the
instruction names 3 tokens for 8 leaves"* observed in the artifact rather than inferred from the SKILL
text. `claude_md`'s `3986 → 3986` is the sharpest illustration of both problems at once: it is exactly
the value a Phase-0 copy would carry, and no reader can tell a measured no-change from a
never-measured.

The identity generalizes into a checkable invariant. Since `before_tokens` is a script-measured
Phase-0 read and the audit delta is a script-measured Phase-0→Phase-5 change to the same file:

> **`budget.index.after_tokens - budget.index.before_tokens == audit_delta(the index row)`**

Re-derived across all **55** unique archived records:

```
unique=55   with an index row=31   no such row=14   no audit block=10
              └─ consistent=25   contradict=6
```

Revising §2.4's design narrowed this census and the narrowing is deliberate. Round 1 proposed a
second arm — *"no index row ⇒ the index did not move ⇒ delta must be 0"* — which counted the 14
no-row records as "free" coverage. **The 14 are not coverage.** Every one of them is an unrefreshed
seed, so `after - before == 0` *identically*: the arm cannot fire on any of them, and the only
record it could ever fire on is a false positive (§5). **31 checkable, 6 contradict, 24 not
checkable** is the honest figure, and it is the one this spec carries.

The six contradictions are not one population:

```
2026-09-04T02:11:01   index=  +0   audit=  +4     ┐ exact zeros — the seed's mirrored read,
2026-09-04T17:34:44   index=  +0   audit= +58     │ never refreshed. The structural defect.
2026-09-05T19:51:52   index=  +0   audit= -59     │
2026-09-14T00:36:54   index=  +0   audit= -52     ┘
2026-08-29T23:33:51   index=+135   audit=+148     ┐ a hand-refresh, attempted and merely
2026-08-31T03:10:05   index=  -9   audit=  +2     ┘ imprecise. A different failure mode.
```

**Four of the six are exact zeros — but they are not the most recent four.** Ordered by timestamp, the
newest row-carrying records are `09-05T19:51` (delta **0**, contradicting), `09-12T01:19`
(**−35**, consistent), `09-12T21:28` (**−1298**, consistent), `09-14T00:36` (delta **0**,
contradicting). The two zeros are separated by two honest refreshes, so "the newest records are
zeros" is false and this spec does not claim it. Across all 31 row-carrying records there are
**seven** exact zeros, at positions 17, 12, 7, 6, 4, 3 and 0 counting back from the newest — and
**three of the seven are honest**, their audit delta is also 0 because the index genuinely did not
move between the snapshots. An exact zero is a signature only when the audit says the file moved; on
its own it means nothing.

The mirrored-read signature is independently visible in the sibling leaves the mandate never names.
Across the 31 row-carrying records, `budget.claude_md.*` is mirrored in **28** and
`budget.recall_facts` in **21** on the log union (**20** on the archive — one record's rf leaf reads
mirrored there and moved here):

```
cm-mirrored + rf-MOVED      n=10   consistent= 9
cm-MOVED    + rf-mirrored   n= 3   consistent= 3
cm-mirrored + rf-mirrored   n=18   consistent=13
cm-MOVED    + rf-MOVED      n= 0
```

The archive cross-tab — same 31 rows, the log union's counterpart — reads `11 / 3 / 17 / 0`. The
counts that move are `10 → 11` and `18 → 17`; `28` (the `claude_md` margin) and the zero row are
invariant across the two readings. The last row is the sharpest fact here: **no record has both
families moved.** `SKILL.md`'s step-4-tail
instruction names three keys, all in the `budget.*.after` family, and this is what a mandate that
names a subset looks like when it is actually followed. This is **corroboration, not the check** — the
check is the invariant above, which needs none of it — and it is stated as a population rather than a
narrative because the narrative version was the part that was wrong.

The two older contradiction rows show a model that *did* try to refresh by hand and got it slightly
wrong, which is what an unenforced prose mandate looks like in practice.

### C4 — nothing owns the after-state, and the mandate under-names it

The only refresh path is prose, and it is not where a reader would look. It lives at the **tail of
step 4**, not in the persist step:

> *"Finally set `budget.*.after`/`after_tokens`/`over` from a final `memory_status.py` read so the
> always-loaded gauge and ⚠ reflect the post-write state (AFTER any dispositions above)."*

A weaker twin sits in Phase 4 — *"update `budget.*.after` (CLAUDE.md lines, index lines/bytes,
recall-fact count)"* — which names one token plus three concepts. The step-4 tail names **three
tokens for an eight-leaf after-side**, and the miss is structural rather than a wording slip:
`budget.*.after` glob-matches `budget.claude_md.after` and `budget.recall_facts.after` only —
**there is no `budget.index.after` key** — so the instruction cannot reach
`budget.index.after_lines` / `after_bytes`, which are precisely the two keys `render_dashboard`
reads for its line delta:

```
dln = _num(idx.get("after_lines", 0)) - _num(idx.get("before_lines", 0))
```

Nothing verifies any of it. `render_dashboard.py` never recomputes or validates `budget.*.after`; it
reads with zero defaults, so a never-refreshed after-side renders as **its own before value — `≈3986/4000`**
with no warning, and
the `--persist` gates judge the dream arc, narration and procedure integrity only. **`≈0/4000` is not
the defect, and an earlier revision's version of this sentence was self-defeating**: the seed mirrors
before→after (`"after": ctx["repo"]["CLAUDE.md"][0]`), which is C1's whole premise, so a stale after-side
reads as a *plausible* number — that is the concealment. A zeroed gauge needs `after_tokens` absent or
zero while `budget_tokens` is present, a shape the seed never writes: measured over the 55, **0** records
carry an absent-or-zero `claude_md.after_tokens` and **0** an absent-or-zero `index.after_tokens`. The
`≈0` reading made the defect announce itself, which undercuts this section's thesis rather than
supporting it. `smoke.py` pins
other SKILL instruction prose by literal substring, so the mechanism exists — it simply was never
applied here. The nearest coverage anywhere is the QA companion's `ground_truth_consistency`, whose
declared quantity registry holds **two** rows with an artifact recomputation — `budget.index.after_tokens`
and `budget.recall_facts.after` — and which is not the shipped gate. The denominator this sentence
carried was **eight**, the refresh's leaf count at revision 1; it read **nine** through revisions 2–9
and reads **twelve** here, so the ratio has been getting *worse* — by the refresh growing, not by the
companion shrinking, which is the honest direction to record it in.

### C5 — the two sinks, and which one can carry a correction

`_persist(record, dirpath)` appends `payload = dict(record)` to the log, and the inlined heal block
in `main()` writes `dict(record)` back to the cycle file with exactly **one** key overwritten
(`marker`). Both receive **the same dict object** `record`.

So a refresh that mutates `record` in place rides both sinks with **no plumbing**. The narration
block is the existing precedent and its own comment states the rule: *"computed BEFORE the single
print … `_persist` appends the payload, so the block rides the log line."*

**On the duplicate path neither sink receives this run's values** — and this is the correction round
1 forced. `_persist` returns `"duplicate"` *before* its only `fh.write`, so a duplicate appends
nothing: the log line holds the **first** persist's values, not the re-render's. The cycle file
holds them too, unless it is healed. So on the exit-3/exit-4 loop-back — the one re-render that
follows a real write — **the printed dashboard is the only surface carrying the fresh measurement**,
and the heal (the file) is the only sink that *can* carry it back. That is a stronger argument for
widening the heal than round 1's, and it inverts round 1's stated hazard: the failure is *show truth
while logging stale*, not the reverse.

`_heal = status == "ok"`, and the `duplicate` branch re-reads `paths[0]` to compare exactly one
field — `_dget(_stored, "narration").get("verdict")`.

That interacts with `render_html.assemble_cycles`, which replaces the log's copy with the file's on
**stamp equality alone**:

```
if _lts and _lts == _rts:
    cycles[-1] = rec    # same dream, same stamp — the current file is the fresher expression
```

The comment claims freshness the code has no way to establish: there is no mtime, no content hash, no
schema version anywhere in scope. `assemble_cycles` receives neither the cycle file's path (held by
`render_html.main` as `args.cycle` and never threaded in) nor the store, and the `CycleRecord`
TypedDict carries **no version key at all** — deliberately, since every field is annotated additive
and *"legacy records render"*. So "the file is fresher" is not a property to *measure* here; it is a
property the **heal gate is supposed to maintain**, and does not.

### C6 — the write target, settled

An audit-time ambiguity resolved, because it decides which artifact this cycle measures.
`retention.cycle_log_write_path` resolves to `<plugin-data>/ops/<project-id>/.consolidation-log.jsonl`
(the **project-id-keyed** ops slot), while `cycle_log_read_paths` returns three paths and its own
docstring gives the precedence: *"Legacy native, slot-keyed plugin-data, then project-id-keyed (last
wins)."* The three hold 30 legacy + 4 slot-keyed + 21 project-id = **55 unique records**. The
native-store log is **legacy — read-only, never written**; the figures the audit measured came from
the live write target all along.

### C7 — the persist argument *is* the store handle

Round 1 designed the refresh around `build_context(project_dir)` and spent §2.3 recovering a
`project_dir` from the store. **The recovery is unnecessary, and its absence is why round 1 was
unimplementable.** Three measured facts:

- `main()` has no `store` variable. It has `persist_dir`, the `--persist DIR` string, and its own
  no-dir guard states the reason in the codebase's own words: *"the dir is only ever a STORE HANDLE
  here"*.
- `_persist(record, dirpath)` opens with `store = _P(dirpath)`, and the narration block twelve lines
  above the proposed seam already computes `_store = _P(persist_dir)` and passes it to
  `_narration_session_dir`.
- `build_context` itself sets `auto_mem = _ctx.native_memory_dir` and `index_path = auto_mem /
  "MEMORY.md"`. So `<persist_dir>/MEMORY.md` **is** the index the seed measured, reachable from the
  seam with zero wiring.

The store *is* the native memory dir, so measuring the store is measuring the thing this record is
about — ownership is exact, not guarded. This dissolves round 1's three project-dir findings at once:
the `project_path` walk (written only by `_write_stacks_cache`, which an unenrolled project's
`--pull` returns before reaching, so the refresh would have silently no-opped on exactly the records
that need it most); `StoreContext.project_root` being the git working-tree root rather than the
directory the seed measured; and an ownership guard that is store-scoped and would pass for two
projects sharing one slot.

**Cost, re-measured for the narrower design.** The store-local measurement set (one
`<store>/MEMORY.md` read, one `*.md` glob, `est_tokens`, `hook_stats`, `cliff_pct`, `placed_fact_names`,
`schema_drift`) ran on the live 37-fact store at **median 0.0017s user CPU** (N=5 samples under
`time.process_time`, **in each of five fresh processes** — an in-process repeat compares a run against
itself; per-process medians 0.0018 / 0.0018 / 0.0017 / 0.0017 / 0.0017, min 0.0017 / max 0.0029 across
all samples), at an index of **36 lines / 7739 bytes / 1889 est tok** — against `build_context`'s
**0.0272s** on the same store in the same session (per-process medians 0.0265 / 0.0272 / 0.0288), which
additionally shells two git subcommands, walks the CLAUDE.md hierarchy and opens the control plane. That
is **~16× cheaper**. It reads files; it writes none. `schema_drift`'s docstring states its own contract:
*"Pure; never raises."*

**Round 3 forced this paragraph to be re-derived, and the correction is upward.** Revision 3 recorded
median 0.0032 / min 0.0031 / max 0.0040 and derived **~9×** from that trio. The trio does not describe
the set the sentence names: on the stated operand the named set's **maximum** across five fresh processes
was 0.0029 — below the recorded *minimum* — so no sample of it was ever 0.0032. Two benign explanations
were tested and both fail: a **cold** first call measures 0.0025, and the set is warm-cache CPU-bound
reads, so `time.time` and `time.process_time` agree to 0.0001s and the clock is not the difference. A
*superset* of the named set (adding `index_fact_names`, a second `placed_fact_names` read, and the
per-fact token reads that a re-implementation of the whole store-local block would touch) reaches
**0.0020 median / 0.0033 max** — entering the recorded band only at its topmost sample, never at its
median and never at its minimum. The recorded trio is thus not a slower reading of the named set; it is
not reproducible from any set this design runs, and the ratio built on it inherited the error.

**The operand rule, restated so it catches this case.** An earlier draft of this paragraph explained the
0.0020 → 0.0032 move as the index growing (1694 → 1889 est tok). That explanation is **falsified**:
holding the operand at the stated 1889 tokens, the named set still measures 0.0017 — the *earlier*
figure, not the later one. Growth cannot move a number to a value the grown operand does not produce. The
rule the paragraph needs is therefore sharper than "carry the store's state": **a timing whose set is
named must be reproducible from that set**, or the name is doing no work and the next reader cannot tell
a slow measurement from a mislabelled one. Both operands are stated here with the store state, the clock,
and the process isolation they were taken under — and a reader who needs the figure should re-measure it
rather than quote it.

### C8 — the audit block's real shape, and why a matcher must key on the store field

The check's operand is a row in `audit.operations[]`. Round 1 keyed it on the literal
`"memory/MEMORY.md"`, which is production's spelling (`_add(f"memory/{f.relative_to(auto_mem)}", …)`)
but **not the only spelling in the tree**. Measured, `tests/dashboard_fixture.py` emits bare labels —
`{"path": "MEMORY.md", "store": "memory", "op": "modified", "token_delta": index_delta}`.

Round 1 justified the correction with a consequence that **does not exist under the shipped design**,
and the correction is worth keeping anyway — for a different reason. The retracted claim was that a
literal matcher "warns on 8 of 8 fixture records, trips `validate_sample`'s assert, and reddens two of
§4's gates." That is **arm 2's** number (no row ⇒ the delta must be 0), carried into a revision that
cut arm 2. Measured three ways on both corpora:

```
matcher                            fixture (8 rows)      live (55 rows)
exact "memory/MEMORY.md"           found 0  silent 8      31 found · 6 warn
basename == "MEMORY.md"            found 8  warn   0      31 found · 6 warn
normalize + exact + store          found 8  warn   0      31 found · 6 warn
```

**The fixture is eight rows, not nine.** `assemble_cycles` takes the history and *appends* the
passed-in record to it; the harness passes `record=history[-1]`, and `record is history[-1]` measures
**True** — the same object, not a copy. So the pre-fix rendering counted that row twice. The distinct
count is `len(history)` = **8**, and the "9" was the double-count of a single row. (This is the
record's own dedup behaving correctly — it dedups *logged* rows against the in-flight record, and
here they are literally one object — so the defect was in the number a reader would quote, never in
the renderer.)

The exact matcher does not warn on the fixture — it finds **nothing** there, and is silent on every
one of the eight rows. And it is **identical to both other matchers on all 55 live records**: not one
record distinguishes them. The divergence is confined to the fixture, which is precisely where the
check is tested.

**That is the argument, and it is a coverage argument, not a gate-protection one.** The fixture is the
check's only in-repo test surface, and P1–P5 all drive `validate_cycle_record` with fixture-shaped
audit rows. Under an exact-spelling matcher every one of them is silent — green for the wrong reason,
asserting nothing about a check that never fires on its own inputs. This is the recorded
`gate-coverage-is-its-match-set` failure: a gate proves only what its matcher can see. Production is
not the reason to normalize; **the tests are**.

The matcher is therefore three conjuncts, each load-bearing for a different case:

1. **Normalize one leading `memory/`, then require exactly `MEMORY.md`.** Conjunct 2 alone is
   insufficient: `memory/AA/MEMORY.md` has basename `MEMORY.md` and sorts **before** `memory/MEMORY.md`
   (`A` < `M`), so a first-match-wins name test silently reads the wrong file. Measured: no such file
   exists in the live store, so this is **latent, not live** — but it is silent when it happens, which
   is why the multiplicity rule below makes ambiguity an abstention rather than a guess.
2. **Accept `store` absent or `== "memory"`; reject any other value.** The row's `store` is written by
   `audit_diff` on every row and clamped to the closed set `("memory", "claude_md", "repo_doc")`. This
   conjunct is what excludes a *repo* `MEMORY.md` (`store == "repo_doc"`) — the only case in which
   conjuncts 1 and 3 alone would be wrong. It is **P4's** entire justification, and it is the one place
   the three candidate matchers above measurably differ.
3. **More than one surviving row → silent.** Ambiguity is not-checkable, never a first-match guess —
   the same abstention §2.4 already applies to missing operands.

The correction is corroborated rather than merely convenient: the fixture at
`tests/dashboard_fixture.py` asserts
`index_op["token_delta"] == budget["index"]["after_tokens"] - budget["index"]["before_tokens"]` — the
invariant §2.4 adds, already asserted by the repo's own sample. The fixture is not an obstacle the
check must tolerate; it is a second, independent statement of the same identity.

### C9 — a carried item that is a *second* root cause

`AGENTS.md:19` carries a plugin table whose `consolidate-memory` row reads `0.4.27` on a `0.4.29`
tree, and `tests/docs_links.py` **exits 0** on it (re-measured on `fa91254`). Three separate blinds
cover it, and two are deliberate:

- **Blind 1 — bare spelling.** `_CURRENCY = re.compile(r"\bv(\d+\.\d+\.\d+)\b")` makes a literal `v`
  mandatory, so a bare `0.4.27` can never match. The comment above it declares this deliberate: *"A
  literal `v` is what separates a currency statement from a version *mention*, and it is not
  cosmetic."* The stale cell is bare, so **both** blinds cover it and fixing either alone still
  misses it.
- **Blind 2 — first-match-wins.** The scan `break`s on the first match, so every later `vX.Y.Z` is
  discarded unexamined. The docstring states the convention outright: *"the FIRST `vX.Y.Z` in a live
  doc is its currency statement."*
- **Blind 3 — no verbatim stripping.** `check_version_statements` reads the file directly, unlike
  `check_links` / `check_anchors`, which call `strip_verbatim()`. So a `vX.Y.Z` inside an earlier
  fenced block is taken as the doc's currency statement — this one errs toward a false *positive*.

The cell has been stale for **two** releases: walking `AGENTS.md` across commits, the table cell and
the intro line moved together through `1864f68` (`0.4.27/0.4.27`), then `9696dfb` and `296a012` both
read `0.4.28/0.4.27`, and the v0.4.29 release commit reads `0.4.29/0.4.27` — two releases bumping
**only** the intro line while the gate stayed green. A live instance of the class the gate's own rule
claims to have closed.

**This is a different root cause from C1–C5** (a matcher narrower than its rule, not an unowned
post-state), and §6 explains why it should not ride this branch.

## §2 Design

The fix has one idea: **the script owns the post-state, and it owns exactly what it can measure from
the store it is persisting to.** A refresh runs once at the terminal persist; a WARN makes its output
independently checkable; the heal gate is widened so the corrected record reaches the file.

### 2.1 The seam, and why the gate is `persist_dir is not None`

Insert `_refresh_post_state(record, _P(persist_dir))` in `main()` **immediately before the
`validate_cycle_record` loop**, and gate it on the same predicate the code already uses to
distinguish a judged render from a preview:

```
judged = persist_dir is not None
```

Round 1 named the seam as *"immediately before `judged = persist_dir is not None`"* while also
constraining it to sit before the validator. Those are different places and the order is the
opposite of what that draft assumed — the narration block's `judged` line is **37 lines after** the
validator, so the refresh as written would have landed after it. Implemented literally it would have
made the new check read the unrefreshed seed and fire on 28 of the 31 row-carrying records, every
pass — verbatim the state §2.4 calls fatal. Three ordering constraints, each with a reason already
written in the file:

1. **Gated on `persist_dir is not None`, not on truthiness.** The existing comment is explicit that a
   seed/preview render *"is the dream's BEFORE state (0 candidates, 0/0/0 by construction) and must
   NOT be flagged."* That BEFORE state is the only honest pre-state the product produces; refreshing
   a preview would destroy it. The refresh shares `judged`'s predicate — it cannot "follow" a
   statement that binds it.
2. **Before the print.** The narration block's comment states the rule: *"compute-before-print."*
   Refreshing after the print would log truth while **showing** stale — a worse divergence than
   today's, which at least shows and logs the same thing wrong.
3. **Before `validate_cycle_record`.** This is what makes §2.4 an independent check rather than a
   tautology: the refresh derives the post-state by re-measuring the store, while the invariant
   derives it from the seeded `before` plus the audit delta. Two different paths over the same
   number — disagreement is then a real signal.

Mutate `record` **in place**. No plumbing is required: per C5 both `_persist` and the heal already
receive this object. This is the narration block's established pattern, not a new one.

### 2.2 The refreshed key set — store-local, and closed by shared operands

Round 1's set was derived by asking *which keys does the seed copy from `ctx`* — a syntactic
criterion — and it produced a set that was **not closed under the measurement it rewrote**. Two
reviewers found this independently and from different directions: it refreshed `after_bytes` while
leaving `cliff_pct` frozen, and `cliff_pct` is `cliff_pct(index_lb[1], index_lb[0])` — literally the
same two operands. The record would print `≈1512/1500 OVER … · cliff 30%` on one line, two
arithmetically linked values that cannot both be true: the C3 self-falsification class, introduced
by the repair.

**The criterion, stated so the set can be checked rather than trusted:** a key is refreshable iff it
is a pure function of a measurement the refresh can re-take **from the store it is about to persist
to**. That set is closed by construction — see *"One site, not two"* below, which is what makes
"by construction" literal rather than argued.

**In — the index family and the one leaf outside it, all from one read of `<store>/MEMORY.md`:**

| leaf | derived as |
| --- | --- |
| `budget.index.after_lines` · `after_bytes` · `after_tokens` | `_measure(<store>/MEMORY.md)` |
| `budget.index.fat_hooks` · `hook_max_tokens` | `hook_stats(text)` on the same text |
| `budget.index.cliff_pct` | `cliff_pct(_measure[1], _measure[0])` — the same two operands |
| `budget.index.over` | `after_tokens > INDEX_TOKEN_BUDGET` |
| `budget.index.budget_tokens` | `INDEX_TOKEN_BUDGET` — the comparison's own denominator |
| `budget.index.ceiling_tokens` | `INDEX_CEILING_TOKENS` — same, for the second rung |
| `remediation.over_ceiling` | `after_tokens > INDEX_CEILING_TOKENS` — the same read |

The last row is the only one **outside** `budget`, and it is in this table rather than in a list of its
own because the criterion that admits it is the same criterion that admits the rest — *is it a pure
function of a measurement the refresh can re-take from the store?* Its address differs; its
derivation does not. The row is also the table's one **cross-mapping** entry, which is why §2.3's
per-mapping skip guard has four names and not three.

`after_bytes` is refreshed even though it is written and never read (§5) — leaving one leaf of the
family unwritten would make the closure claim false.

**Round 3 added the last three, and the first two of them are this table's own defect one level up.**
Round 1's error was a *measured* leaf left frozen beside a measured leaf computed from it
(`after_bytes` vs `cliff_pct`). The set that repaired it was still not closed, because a refreshable
key need not be a *value* — it can be a **comparison**, and a comparison's second operand is as much
a leaf of the same block as its first. `over` is `after_tokens > budget_tokens`; rewriting the
numerator alone pairs a *fresh* measurement with a *seed-time snapshot of a module constant*, and
`budget_tokens` is genuinely a snapshot: no environment variable, settings key, or config path
overrides `INDEX_TOKEN_BUDGET` anywhere in the tree, so a record's copy of it can only record what
the constant happened to be the day the seed ran. Measured, it has been two values — **`1200` on 14
of this store's 55 records, `1500` on the other 41** — so a refresh that writes `over` against the
live constant while leaving `budget_tokens` at `1200` renders a gauge whose numerator and denominator
come from different budgets. The rule the table's header states is therefore tightened, not
extended: **a leaf is in iff every operand its refresh depends on is itself re-taken by the same
splice.** `budget_tokens` and `ceiling_tokens` are that closure made literal, and both are already
declared on `IndexBudget` (`total=False`, *"stored for display (the `budget_tokens` precedent)"*),
so writing them stays inside the schema the record was seeded from.

**`remediation.over_ceiling` is the third, and it is a reclassification rather than an addition.**
An earlier revision listed it in the Out-list below as a *triage verdict* — the flag "keyed to
`required`" — which is what its address suggests and what the container's name invites. The source
says otherwise in three places, and they agree: `memory_status.py` computes it as
`index_lb[2] > INDEX_CEILING_TOKENS`, a pure comparison of the same `_measure` read the rest of this
table uses; the constant behind it is documented as **structurally standing-justify-INDEPENDENT**
("the comparison never reads `standing_justify` — there is nothing to suppress and no justify
escape"), which is the property that separates a measurement from a verdict; and its own comment at
the assignment says the over-target triage and this flag are *"a SECOND, INDEPENDENT signal … never a
re-key of it."* `required` reads `standing_justify`, `baseline_facts` and fact-count growth — that
one is a verdict, and it stays out. So the split running through the Out-list bullet is not
`maintenance` vs `remediation` by container; it is **per leaf, by whether the computation reads
record state or store state**, and `over_ceiling` is on the store-state side of it. Writing it costs
nothing else: **every** reader renders it identically when absent or falsy — so the repair cannot
invent a display. The census is `grep -rn over_ceiling`'s, and it is **six sites in three files**:
the dashboard tail and the remediation panel in `render_dashboard`; the remediation lead, the KPI and
the gauge in `dashboard.template.html`; and the store-checks row in `dashboard.sections.js`. All six
test truthiness (`_flag`, `truthy`, or a bare `if`). An earlier revision said "exactly two readers
(the alarm line and `render_html`'s gauge)" — the number its author happened to know, and wrong in
the direction that matters here, because a single unexamined reader is exactly what would let this
write invent a display.

**One site, not two.** The index family is not re-implemented in the refresh; it is **shared** with
`build_context`. The distinction is load-bearing, because the seed's read of `<store>/MEMORY.md` is not
the single `_measure` call the table above implies. Measured at the seed: `index_lb =
_measure(index_path)`; then a **0-token re-read guard** — *"a 0-token index read WHILE facts exist is
anomalous (a write-truncate race) and would wrongly clear the over-budget gate — re-read ONCE to settle
it"* — which re-measures when `index_lb[2] == 0 and fact_files`; then a **second, independent read**
(`_index_text = index_path.read_text(…)`) whose text feeds `hook_stats`. Three behaviours, and a refresh
that re-implemented only the obvious one would write `after_tokens=0` in precisely the race the guard
was added to settle — a narrower sibling of §2.3's absent-index fabrication, and one no test would
catch.

So the refresh does not own this measurement. The seed's store-local block is **extracted into one
helper** that `build_context` and the refresh both call. Then *"closed by construction"* is literal:
one site means the two callers cannot diverge, and any future change to the guard reaches both. This is
the repo's own weakest-enforcement-site rule applied in the constructive direction — the repair is to
remove the second site rather than to keep the two in sync by discipline.

**In — the store-local siblings:** `budget.recall_facts.after` (the store's fact-file count, from
the same `*.md` glob) and `health.schema_drift` — with **one field preserved rather than recomputed**,
and the reason is a correction round 2 forced.

`schema_drift(fact_files, placed_fact_names(…), canonical_stems=…)` is *almost* store-local. Two of
its three arguments are: the glob, and the index's own pointers. The third is not. `canonical_stems`
comes from `ctx.canonical_domain_dir`, and **obtaining that directory is a project-keyed registry
read** — `resolve_store` takes the domain from the control-plane registry (`enrolled_domain(conn,
pid)`), or from a git-root settings file when the project is unenrolled, and falls back to
`domains/unknown/facts` when neither resolves. The glob is a directory read; the *path* is not.
Round 1's parenthetical — *"a directory glob, not a database read"* — named the glob and skipped the
lookup it depends on.

So the refresh recomputes `schema_drift`'s **six store-local fields** and **preserves
`advisory_stranded_globals` from the seed**. That is not a compromise: the preserved field is not
among C2's four under-reporters (`missing_node_type`, `index_mismatch`, `advisory_no_scope`,
`advisory_no_origin`), so the preservation costs nothing measured, while recomputation is exactly what
closes the drift C2 found. Deriving the domain from the store instead would mean *guessing* it — and
the `unknown` fallback resolves to a directory that does not exist, so `canonical_stems` becomes
`set()`, which is a different wrong answer rather than a safe one.

**Assignment is leaf-wise, and that is load-bearing.** A block-level splice is wrong in both
directions: `ctx` has no `health` key at all (a block splice raises `KeyError`, which §2.3's
never-blocks handler would swallow into a permanent silent no-op), and `maintenance` contains
`pivoted`, which the model authors in Phase 5 and which drives `outcome_of`'s "MAINTENANCE PASS"
label and suppresses the network-capture panel. The leaves are built as **four scratch dicts** —
`budget.index` (nine leaves), `budget.recall_facts` (one), `health.schema_drift` (its six recomputed
fields, the retained seventh riding along), and the top-level `remediation` (one) — and written only
after the last measurement succeeds. A **mapping** is the unit of assignment; a **leaf** is the unit
of the closure rule above, and the two counts differ because nine index leaves are one dict literal.

**Out — and each for a stated reason, not by omission:**

- **`budget.claude_md.*` and `budget.claude_md_hierarchy`.** These need the *repository* root, not
  the store — `claude_md` comes from `ctx["repo"]["CLAUDE.md"]` and the hierarchy from
  `claude_md_hierarchy(project_dir)`. Reachable only by reintroducing the project-dir recovery C7
  dissolves. **§5 ceiling.**
- **`health.slug_orphans`** needs the projects root — in the **default native layout** the store is
  `<config>/projects/<slot>/memory`, so that root is its **grandparent** (`config_root()/"projects"`;
  measured, `store.parent.parent` is that directory — `<store>/..` is the *slug* dir) — and then the
  slug identity and its siblings, from which the orphan scan is computed.
  **The layout qualifier is load-bearing, and an earlier revision stated the premise as a universal.**
  `resolve_store` sets the store from three sources, and only the first has that shape:
  `default_native = cfg / "projects" / project_slot / "memory"`; `custom`, from the
  `autoMemoryDirectory` setting, which is documented and multi-scope (ADR 002, `SECURITY.md`,
  `harness-map.md`) and for which `_merge_settings`' own docstring says *"user/managed may name an
  explicit absolute dir"*; and `override`, from `store_override` / `CM_STORE_OVERRIDE`, applied
  unconditionally. Measured under the override: store `<tmp>/relocated-mem`, `store.parent.parent`
  `<tmp>`, `config_root()/"projects"` `<config>/projects` — three different directories, none of them
  the store's grandparent.
  **In those layouts distance *is* the blocker**: there is no path from the store to `<cfg>/projects`
  at all, so "identity, not distance" is false in both terms, not merely mis-scoped.
  What survives is the bullet's real point — name the missing operand, not a level of distance — and
  the reason it gives, which is about a *reader*: stating it as a level invites one to check a
  directory up, find a slug dir, and conclude the reason was proximity. That is the reading round 1 got
  wrong in the `schema_drift` parenthetical. The repair is therefore to scope the premise, not to drop
  the operand rule.
- **`health.index_pointers_ok` / `broken` / `dangling_links`** are hard-coded constants in the seed.
  A refresh would have to invent the computation the seed never did. **§5 ceiling**, and the right
  repair is a real computation, not a refresh.
- **`maintenance.*` CUT-BY-CONTAINER, `remediation.*` CUT-BY-LEAF — and round 3 found that the second
  cut was one leaf too wide.** `maintenance.over_budget_not_justified` is documented in the contract
  itself as `= remediation.required` — *"the dual-axis suppression result; NOT a fresh budget
  compare"* — so it is a **triage verdict**, not a measurement, and the whole block is Out.
  `remediation` is different, and the earlier revision filed it with `maintenance` because the two are
  adjacent in the record and adjacent in the triage's own naming. Its members split: `required`,
  `standing_justified`, `lever`, `candidates_surfaced`, `pruned`, `achieved_*` are model-owned verdicts
  after Phase 5 and stay Out, while **`over_ceiling` is a store-state measurement** — the source
  computes it as `index_lb[2] > INDEX_CEILING_TOKENS` from the same read §2.2's table re-takes, and
  documents it as standing-justify-independent. It is therefore **In**, per the paragraph under the
  table. The rule the bullet now states is the one that decides it: **a container is not a class** —
  `maintenance` is Out entire because every member is a verdict, and `remediation` is the counterexample
  that proves the rule needs a leaf-level test rather than a container-level one. Writing a fresh
  `over` beside a frozen `over_budget_not_justified` remains a real state; §2.3 warns on the one
  direction of it that matters rather than papering over it.
- **`cross_project.global_store_facts`** is deliberate Phase-0 signal by the SKILL's own design, and
  the block's remaining keys are model-authored.
- **The pass's own record** (`entries`, `verification`, `audit`, `network`, `distill`, `usage`,
  `workflow_proposals`, `narration`, `dream`, `outcome`) — **out because each records the pass that
  ran, not because each is model-authored.** An earlier revision filed all ten under "every
  model-authored block," and the source falsifies that label for **five** of them: `audit` is injected
  by `memory_status.py --audit-into` (*"deterministically inject the audit block INTO the cycle record
  (no model merge)"*), `usage` by `extract_signals.inject_usage` (*"wholesale assignment (the whole
  block is script-produced; no model judgment fields to merge around, unlike distill's sub-key
  merge)"*), `workflow_proposals` by `sync_global.py` (`seed["workflow_proposals"] = block`),
  `narration` by `render_dashboard.py` (`record["narration"] = narration_block(narration)`), and
  `distill` by `distill_scan` (`record["distill"] = blk`).
  **`distill` is not one of the wholesale writers, and it was filed as one.** Its assignment is
  wholesale *of a merged block that keeps model-authored sub-keys* — the source's own word for it is
  **split-ownership**: *"A sub-key MERGE, deliberately NOT the audit `--into` wholesale assignment …
  counts/window/secrets_omitted overwrite; model-authored `proposed`/`created`/`verdict` are
  preserved."* An earlier revision quoted the `inject_usage` docstring **truncated at "around" with no
  ellipsis**, which is exactly the clause that draws the distinction the sentence then erased — an
  unmarked elision cannot be caught by a reader, which is why it is repaired by restoring the full
  sentence rather than by adding a caveat. The **set** is right and unchanged — a refresh would
  overwrite what the pass did with what a later read sees — but the reason must be the one that
  survives the source, which is the same reason the `demotion` / `identity` / `preflight` bullet below
  gives. That this is the *second* time this umbrella was found to misdescribe its own members is the
  argument for stating a checkable reason per member rather than a class label over all of them.
  **The `before` halves** are out too — pre-state by definition; writing them would destroy the only
  honest baseline and silently repair the very defect §2.4 detects. And **`marker`** is out for a
  second, load-bearing reason beyond this one: `_persist`'s idempotence is the stringified pair
  `(marker.commit, marker.timestamp)`, so leaving it untouched is what keeps `_already_logged`
  answering the same way before and after the refresh.
- **`demotion`, `identity`, `preflight` — script-seeded, and out for a reason stronger than
  authorship.** Round 1 filed all three under "model-authored," which is a mislabel round 2 caught at
  the source: `seed_record` writes each one **from `ctx`** — `ctx["demotion"]`'s triage counts,
  `identity_snapshot`, and the environment verdict the pre-flight produced. They are Out because each
  is a **snapshot of the pass that just ran**, and re-taking it at render time destroys the thing it
  recorded. `preflight` is the sharpest: refreshing it would overwrite *"the environment failed check
  X while this pass ran"* with the environment *now*, erasing the very failure the block exists to
  preserve. `demotion`'s triage window carries the same defect in weaker form (it also receives the
  model's Phase-5 `verdict`/`struck`), and `identity`'s enrollment stamp is what the record's
  `entries` were written against.
- **The remaining `ctx` reads — out by §2.2's criterion, which is narrower than "reads `ctx`."**
  `scope.memories_reviewed`, `scope.git_range` and `scope.git_commits` describe **what the pass
  covered**, not what the store holds; refreshing `memories_reviewed` would retroactively enlarge the
  pass's own coverage with the facts it created in Phase 4. `project` and `rigor` are not measurements
  (`_provisional_rigor` is superseded in Phase 2), `budget.global_claude_md.*` measures a file
  **outside the store** (`~/.claude/CLAUDE.md`, read-only by design), and the four seeded budget
  *constants* (`CLAUDE_MD_TOKEN_BUDGET`, `GLOBAL_CLAUDE_MD_TOKEN_BUDGET`, `INDEX_TOKEN_BUDGET`,
  `INDEX_CEILING_TOKENS`) are not measurements at all. Naming them is what makes the closure argument
  checkable rather than merely plausible.

The set is stated as a whitelist, not a blacklist — a future key added to the seed is *not* silently
refreshed — but a whitelist is only as good as its closure argument, which is why the criterion is
stated above rather than the list alone.

### 2.3 Never blocks — the contract, and its mechanism

A measurement failure must never fabricate. On **any** failure — an unreadable index, an import
error, an exception from any measurement — the refresh leaves `record` **exactly as authored**,
prints one line to stderr, and returns. It never raises, never returns a status, and never affects
the exit ladder (0/3/4/5 are decided by the gates that already own them; neither
`procedure_integrity` nor `arc_completeness` reads `budget` or `health`, verified).

The warning uses the file's existing idiom — a raw `print(…, file=sys.stderr)` prefixed
`"render_dashboard: "`, matching `render_dashboard: cycle-record warning: …` and
`render_dashboard: narration check skipped (…)`. It deliberately does **not** use `_ui.dream_cue`,
which is gated on `CM_DREAM_ARC` and is by design invisible to `cm`, the tests and the beta harness —
a refresh failure must be loud, not suppressible.

**All-or-nothing is a mechanism, not a property.** Round 1 asserted "partial application is
rejected" without saying how, and the mechanism matters because `validate_cycle_record` never
descends into `budget` — **verified directly**: a record carrying `budget.index = "not-a-dict"`
survives the validator with zero stderr. Round 1 offered that shape as proof the corruption renders
silently, and the citation named the wrong failure. `render` binds its sub-values with a bare
`b.get("index", {})`, and `_dget` guards **level 1 only**, so a present-but-wrong-typed value flows
through untouched to `idx.get(...)` and the render **raises `AttributeError`** — loud, not silent.
The silent case is the one a partial write actually produces, and it is the *dict* shape: a
`budget.index` holding only **some** of its leaves renders with zero warnings and zero errors,
because every reader of those leaves uses `.get(k, default)` with a default. That is a
mixed-generation record persisting invisibly — the exact class this cycle exists to prevent. The
refresh therefore **builds the complete leaf set in a scratch dict and splices it once**, after the
last measurement has succeeded. A wrapping handler makes the failure path a no-op on `record`, so no
leaf can be half-written.

**The splice is conditional on the container already existing — a policy, not a guard.** A record
carrying no `budget` block at all has no stale after-side to correct (the renderer reads
`idx = b.get("index", {})` and draws no row), so the refresh **skips it and says nothing**. Creating
the container instead would make the refresh *author* state the record never had and newly render
rows on a legacy record — a different change than correcting one.

**And the condition is keyed on the mapping the splice writes into, not on `budget`.** An earlier
revision keyed the policy on the outermost block, which is **one level too coarse**: `render_dashboard.
render` gates the index gauge row on `if idx:` — `idx` being `b.get("index", {})`, the *inner* mapping
— and draws its `(unchanged)` fallback on `if not (cm or idx or rf or gcm.get("present"))`. So a
record carrying `budget.claude_md` **without** `budget.index` is a shape the renderer treats as having
no index, and a splice into a newly created `budget["index"]` would author that block and newly draw
the row — precisely the outcome the paragraph above forbids. The shape is type-legal (`Budget` is
`total=False` and declares `index` beside the others) and `--persist` consumes arbitrary JSON from
`paths[0]`, so it is constructible; measured across 247 stores / 92 unique records it does **not**
occur (one record has no `budget` at all, none has `budget` without `index`), which makes this a
precision repair rather than a live defect. It is also the same leaf-wise rule §2.2 already states for
assignment — *"Assignment is leaf-wise, and that is load-bearing"* — applied to the skip: **create a
leaf only where its own parent mapping already exists**, for each of the **four** mappings the leaves
live in (`budget.index`, `budget.recall_facts`, `health.schema_drift`, and the top-level
`remediation`), not once for `budget`.
(An earlier revision said "four" and was corrected to *three*; round 3 restores four **by adding a
mapping, not by re-counting the old three**. The two are worth keeping apart, because the earlier
error was a miscount and this one is a new leaf: `remediation.over_ceiling` is written under a parent
outside `budget` entirely, so a guard that enumerated the three `budget`/`health` names would leave
it as the one leaf spliced unguarded. The count is spelled out here because the guard is per-mapping
and an off-by-one in it would silently create one.)

The consequence has to be stated because it collides with the contract above: an unconditional
`record["budget"]["index"][…]` raises `KeyError` on such a record, and the never-blocks handler would
swallow it into exactly the silent no-op §2.2 warns about, indistinguishable from *"the measurement
failed."* So the code keeps the two skips **apart** — an absent container is a policy skip (silent,
nothing is wrong), an exception from a measurement still warns — and a single `try` wrapping both
would lose the distinction.

**The refresh's precondition: `<store>/MEMORY.md` must exist.** This is the one failure the never-blocks
contract cannot catch by itself, because every measurement in §2.2 returns a well-formed **zero** on an
absent index and **none of them raises** — measured, `_measure(absent) -> (0, 0, 0)`,
`schema_drift([], set())` returns all seven fields zero, `hook_stats("") -> (0, 0, [])`,
`cliff_pct(0, 0) -> 0`. A refresh that ran anyway would write `after_tokens=0`, `over=False`,
`cliff_pct=0`, `recall_facts.after=0` and an all-zero `schema_drift` beside the seed's true `before_*`:
a fabricated post-state, **clean in the concealment direction**, and strictly worse than the mirrored
seed it replaces — the seed at least carried a real Phase-0 value.

Nothing upstream prevents it. `main` validates the `--persist` argument by non-emptiness and
`os.path.isdir` only, and `tests/smoke.py` hands bare `mkdir()` directories (`_pdir54`, `_p41`, `_p41b`)
to **ten** persist invocations. So the refresh asserts the precondition itself, and it asserts it
**first** — before any measurement, so that the scratch dict is never even partially built: if
`<store>/MEMORY.md` is absent or unreadable, warn and leave the record exactly as authored. That is
§2.3's existing path, which is already the right shape for *"I could not measure, so I did not write."*

Emptiness is deliberately **not** in the precondition. A zero-byte `MEMORY.md` is a real file and
`(0, 0, 0)` is a truthful measurement of it; the resulting large negative delta then trips §2.4's WARN,
which is the system working — the record falsifies itself **loudly**. Absence has no truthful
measurement; emptiness does.

**Two conditions are surfaced — and the refresh still writes.** If the fresh index is over
`INDEX_TOKEN_BUDGET` while the record carries **no** `remediation` block, or if the fresh `after_tokens`
exceeds `INDEX_CEILING_TOKENS`, the refresh warns **and then writes the measurements anyway**.

**Both operands are the live constants, not the record's own fields, and that is a repair.** An
earlier revision compared against `budget.index.budget_tokens` and the record's `ceiling_tokens` —
"the record's own" thresholds, which sounds more conservative and is the opposite. The record's field
is **seed-derived and can be a retired constant**: measured across this store's 55 records,
`budget.index.budget_tokens` takes exactly two values, **`1200` (14 records) and `1500` (41)**, while
`INDEX_TOKEN_BUDGET` is `1500` — so on those 14 records the condition would compare a *fresh*
measurement against an *obsolete* budget. The reachable consequence is a record that warns about an
over-budget index while the same pass writes `over: False`, since §2.2 defines that leaf as
`after_tokens > INDEX_TOKEN_BUDGET`. Condition 1 is reachable on them: **13 of the 14 carry no
`remediation` block**, so the "no banner to defer to" premise holds. (Across the wider fleet the peer
census is **21 of 92** stale-`1200` records without `remediation` — that is the reachability witness,
and it is the whole of it. An earlier revision added a second one, *"18 records sitting in the
`(1200, 1500]` band where the two operands disagree"*, and it does not survive re-derivation: **every
one of those 18 carries `budget_tokens == 1500`**, its own threshold *being* the live constant, so on
them the operands are identical and **cannot** disagree. The genuine disagreement set — record
threshold `1200` **and** `after_tokens` in `(1200, 1500]` — is **0 of 92** and **0 of 55**, with no
borderline cases: across all 29 stale-`1200` fleet records `after_tokens` is either ≤1191 or ≥2761, so
both operands read the same way. The clause also mis-stated its own emptiness — under the definition
that yields 18, this store holds **9**, not 0. The disagreement is therefore **constructible, not yet
observed**, which is the state the clause was written to rule out.) Keying both conditions to the constants the refresh is about to write makes the
warning and the leaf **the same comparison by construction**, which is what §2.3's own argument for
`over` requires. Condition 2 does not carry this defect *today* — `ceiling_tokens` is uniformly `3840`
across every record that carries it, no retired spelling in the population — but it is keyed to the
constant for the same reason, so a future re-basing of the ceiling cannot reopen it.

Round 2 caught the earlier version, which suppressed the write, and it was wrong for two independent
reasons:

- **Suppression punishes the store that needs the refresh most.** `INDEX_CEILING_TOKENS` is **3840**
  and `INDEX_TOKEN_BUDGET` is **1500**, so an index past the ceiling is *also* over target, so the
  Phase-0 triage fired, so `remediation` is truthy and **both** seed arms write `over_ceiling` (the
  standing-justified arm carries it "UNCHANGED by the suppression"). So on **every store this census
  covers** a state past the ceiling carries the banner — the exact opposite of the reason
  the earlier draft gave it ("absent precisely when this fires"). A store standing past the ceiling
  would have been unrefreshable on *every* pass, keeping its seed's `before` values as `after`
  forever: the defect this cycle exists to close, made permanent on the largest stores.
  **The universal form of that sentence is not established, and an earlier revision asserted it while
  the amend ledger records the mechanism lane's refusal to.** The reachable gap is real: condition 2
  compares a *fresh* read taken at persist time, while the banner was decided at Phase 0 from
  `ctx["index_lb"][2]`, and `remediation_triage` returns `{}` exactly when the index is within budget
  — so *"over target ⇒ banner"* holds for the Phase-0 read only. A pass that grows a sub-1500 index
  past 3840, or a `--persist` handle other than the store Phase 0 measured (§C7's own subject), fires
  the condition with no banner. **No such state was produced**: the fleet's largest index is 6481 and
  its single record above the ceiling is a *record* without a banner, not a *state* that fires the
  condition, since a fresh Phase 0 on that store would seed the banner from the same read. Recorded as
  scoped rather than refuted — the ledger entry and this bullet now say the same thing.
- **It re-created C3's self-falsification at the exact transition that flips the field.** `over` is a
  *measurement* — §2.2 defines it as `after_tokens > INDEX_TOKEN_BUDGET`, taken from the same read as
  `after_tokens` — not a verdict. Suppressing the write when a healthy store crosses the target
  mid-pass persists `over: False` beside a refreshed over-budget gauge, so the record contradicts
  itself on one rendered line. Writing `over: True` invents nothing.

**The split is not "verdicts vs measurements" by container — it is by what the computation reads, and
round 3 moved one leaf across it.** The refresh still does not invent a triage verdict:
`remediation.required` (which reads `standing_justify`, `baseline_facts` and fact-count growth),
`standing_justified`, `lever`, `candidates_surfaced`, `pruned` and `achieved_*` are all unwritten, and
`maintenance.*` entire with them. What the earlier revision got wrong is that it filed
`remediation.over_ceiling` with that group **on the strength of its container** — the flag "keyed to
`required`", as the draft put it. The source does not key it to `required`: it is
`index_lb[2] > INDEX_CEILING_TOKENS`, one comparison of one `_measure` read, and the constant it uses
is the one documented as structurally standing-justify-INDEPENDENT. It is therefore a *measurement*
in the same sense `over` is, and the honest split is now stated at the leaf: **a leaf is written iff
its computation reads the store; it is left alone iff its computation reads the record.** `required`
reads the record (the seed's `standing_justify`, the prior `baseline_facts`) — so the frozen
`over_budget_not_justified` and the fresh `over` *can* still disagree, and the warning above remains
the loud half of this design, purely additive, with no reachable state losing its refresh.

**F1 is why the reclassification is not bookkeeping.** A red HARD CEILING alarm beside a healthy gauge
is not a hypothetical: `over_ceiling` was frozen at seed time and never re-derived, so a store that
was de-bloated below the ceiling between the seed and the persist kept rendering the alarm its own
gauge contradicted, on the same line. Measured across the 55 archived records, the *conjunction* the
review's marginal implied — `over_ceiling: true` **and** `ceiling_tokens` absent — is **0 of 55**, so
the specific `≈0t` render is **constructible, not live**; what is live is the simpler and more common
shape, an alarm whose operand has moved since it was raised. Recording the measurement as
constructible rather than observed is the same discipline the condition-1 bullet above applies to its
own reachability witness.

**The record's `ceiling_tokens` IS read — and the earlier revision's claim that it "is never read" was
false against the source it described, not merely against a later one.** The single reader is the hard
ceiling alarm itself: `render_dashboard`'s tail appends
`⚠ HARD CEILING ≈{_g(idx.get('ceiling_tokens', 0))}t — M1 holds new pulls`, and that `.get(…, 0)` is
the very default this paragraph used to argue about — a *display* default, on the operand of the alarm,
one line under the `remediation.over_ceiling` flag the same block reads. Its only other mentions are
the `IndexBudget` declaration, the seed that fills it, and the ladder spec that introduced it; it
appears in no template, no `render_html`, no `render_log`, no calibration report — so *"never read"*
was not a narrow claim about comparison sites, it was the whole claim, and the alarm falsifies it.
The claim mattered because of what it licensed: an absent `ceiling_tokens` was argued to be harmless,
and the `≈0t` render — alarm raised, operand absent, sized at zero — is exactly what an absent operand
produces at that reader. Measured, the *conjunction* the reader needs to exhibit it, `over_ceiling:
true` **and** `ceiling_tokens` absent, is **0 of 55**, so the render is constructible and not live.
The census stays: **20 of the 55** archived records carry no `budget.index.ceiling_tokens`, and the 35
that do are uniformly `3840`, no retired spelling. Where the earlier revision ended by *deleting* the
read, this one **writes the leaf** (§2.2) — which is the repair that makes the census's question moot
for every record the refresh touches, without pretending the question was never asked.

### 2.4 The reconcile invariant — a WARN in `validate_cycle_record`

`validate_cycle_record(record) -> list[str]` gains one value-level cross-field check, following the
precedent already in the function (the `demotion.verdict` check parses numbers out of a narrative
string and warns on contradiction, and carries an explicit *"Known false-warn ceiling, accepted"*
note — this check copies that shape, including the ceiling). Its docstring says it *"does NOT check
scalar value types"*; that sentence is already falsified by the v0.4.21 `demotion.verdict` check and
is **folded in** by this change rather than left staler.

For a record where the operands are present and integer:

1. **Exactly one index row survives C8's matcher** → warn unless
   `after_tokens - before_tokens == row["token_delta"]`. A row whose `token_delta` is absent or not an
   integer is **not-checkable** — reading it as `0` would manufacture a contradiction out of a
   malformed row, which is this cycle's own failure class pointed the other way.
2. **Silent** — not-checkable rather than passing — when any of: no `audit` block; no `operations`
   list; a non-integer `before_tokens`/`after_tokens`; **no** surviving row; **more than one**
   surviving row; or a row whose `path` is absent, `null`, or not a string. The last case is not
   hypothetical: a naive matcher raises `AttributeError` on `{"path": null}`, **inside the
   validator**, which has no never-raises contract — so the abstention is what keeps a malformed row
   from taking down the render. Round 1's second arm (no row ⇒ delta must be 0) is **cut**; see C3.

Message form, naming the field and both numbers, in the style of the `demotion.verdict` check:
`budget.index.after_tokens contradicts the scripted audit (after=1746, before=1746, audit delta=-52)`.

Three properties make this the right pin. It is **pure and zero-I/O** — every operand is already in
the record. It is **warn-not-fail**, so it cannot newly fail a pass. And it is where it is needed:
`validate_cycle_record` has exactly **one production call site**,
`render_dashboard.py`'s `for w in ms.validate_cycle_record(record)`, which validates the record being
rendered and never an archived one — so this fires on the current record at render time, which is the
only moment a correction is still possible. The 6-of-31 historical rate is a **fidelity** figure, not
a runtime-noise figure.

**Ordering is load-bearing.** It must be called after §2.1's refresh, or it checks the unrefreshed
seed and warns on every pass whose index moved — a check that is always red is a check nobody reads.

### 2.5 The heal gate, widened — and the row-count correction

C5 established the coupling, corrected: on a duplicate the file stays stale **and so does the log**,
and `assemble_cycles` prefers the file. The plan's original remedy was to give `assemble_cycles` "a
real freshness signal." **That is the wrong end of the coupling.** No per-*line* signal exists to
give: no content hash on a log line, and no version key on `CycleRecord` — deliberately, since every
field is annotated additive. The honest statement is that *no per-line* signal exists, and that the
freshness intent in `assemble_cycles`' own docstring — *"dedup-appended if it is **newer** than the
last logged entry"* — predates any mechanism to establish it.

**And no file-level signal exists on this path either** — a correction to an earlier draft of this
paragraph, which claimed one sat "one line away in `render_html.main`." Measured: `render_html.py`
contains no `mtime`, no `getmtime`, and no `.stat(` at all. Nor is that a gap peculiar to this
module: the cycle-record path — writer, log reader, and renderer — carries no timestamp beyond
`marker.timestamp`, which is authored, not observed. The plugin *does* have an established
freshness idiom, just not here: `facts_manifest.build` records `mtime_ns`/`ctime_ns`/`body_hash` per
row, and `sync_global` decides staleness with `st.st_mtime_ns == int(row.get("mtime_ns") or -1)`.
That is the vocabulary a fix should reuse rather than reinvent — but it is an *uncommitted manifest
cache*, so it is a pattern to copy, not a signal already in hand. The distinction matters for the
remedy below: a fix that says "use the mtime that's already there" would have been a fix written
against a file that does not exist.

The invariant to restore is simpler and already asserted by the code's own comment — *the file is the
fresher expression*. Make it true: **widen the `duplicate` branch's comparison from
`narration.verdict` alone to the whole record.** The branch already re-reads `paths[0]` and compares;
the change is what it compares.

**Blast radius, corrected.** Round 1 claimed the widening "changes which content a row holds, never
**how many** rows exist." That is false, and the mechanism is worth stating because it is a second
defect the widening closes. The heal writes `_wb["marker"] = reconcile_marker(…)`, and
`reconcile_marker` fills an **empty** `marker.timestamp` from the state file. `assemble_cycles`
decides append-vs-replace by `_same_dream(cycles[-1], rec)`, whose deciding arm changes when the
stamp goes from empty to filled — measured, the same history and record yield **2 rows (unhealed
file) vs 1 row (healed file)**, i.e. the unhealed path double-embeds the dream, which is the exact
failure the heal's own docstring exists to prevent. The flip direction is safe and one-way:
`_already_logged` keys on the `(commit, timestamp)` **pair**, so the duplicate branch forces
`commit == commit` and `timestamp == timestamp`, and the widening can only turn append→replace
(fewer rows, removing a double-embed), never the reverse. Row **identity** via `#sel` is unaffected —
the archive addresses rows by their position in the embedded `ALL` array, which the display sort
carries rather than recomputes.

**R4 (from the plan) dissolves rather than being mitigated.** The concern was that a broader heal
might turn a clean duplicate into a spurious append. It cannot: the heal rewrites the cycle *file*
and never touches the log, and `_persist`'s `(commit, timestamp)` idempotence lives entirely on the
log side. The pin in §3 asserts this directly rather than arguing it.

### 2.6 The instruction corrects to the script

The step-4-tail instruction and its Phase-4 twin are rewritten to say what is now true: **the
post-state is script-owned and the model does not hand-maintain it.** Naming the leaves would be the
weaker fix — it would leave a prose mandate that a future key addition silently outgrows, and C4
measured exactly that failure once already. Because §2.2's set is store-local while `budget.claude_md`
is not, the instruction keeps a model duty **there** and says why — that one is the residual, and §5
records that it stays a Phase-0 value.

**`budget.claude_md_hierarchy` is not part of that residual, and an earlier revision wrongly said it
was.** It claimed the rewritten instruction "keeps a model duty" over both, but there is no duty to
keep: the step-4-tail mandate names `budget.*.after` / `after_tokens` / `over` — the `claude_md` half
— and `claude_md_hierarchy` has **no `after` key at all** (its `ClaudeMdHierarchy` shape is a `files`
list). Its single occurrence in `SKILL.md` is the schema example (*"claude_md_hierarchy": {"files":
[{"path": "CLAUDE.md", "tokens": 0}]"*), never an instruction. Its value comes from
`claude_md_hierarchy(project_dir)`, a repository-root walk that only a script can take. So §5's
scoping — the instruction "remains the only path for the **`claude_md` half**" — is the correct
statement, and §5's own sentence deferring to *"§2.6's correction saying so explicitly"* was deferring
to a section that said something else. Naming it as a residual would have been worse than untidy: it
would ask the model to keep current a value it cannot measure, which is the authored-state failure
§2.3 exists to forbid.

## §3 Verification — the pin list

Every pin must **fail on pre-fix code**. Per the standing discipline, a check that cannot flip on any
revision is a **regression guard**: it is labeled with the revision it *does* move on and kept **out**
of the pin count, because the pin count is what every downstream claim derives from. Round 1 listed
thirteen items and called all thirteen pins. The list is now **twenty-two items, ten pins, twelve
guards**: **P1, P2, P6, P7, P13, P15, P16, P18, P20, P21 fail on pre-fix code**, and the other twelve
are labeled below with the revision they *do* move on — **two of them with revision 9 as a measured
referent**, which is new.

**The claim above is measured, not asserted** — re-derived on the committed revision by running the
suite inside a `git archive HEAD` tree (one process per tree, since `sys.modules` caches the first
import), with two shims because `_refresh_post_state` and `store_local_index` do not exist before the
fix and a bare `AttributeError` would abort the block **before P13/P15/P16** — the three pins with
the most to say. Both shims model the pre-fix *behaviour* rather than the pre-fix code shape: a
no-op `_refresh_post_state` (a refresh that does nothing) and a `store_local_index` sentinel whose
cross-check clause reaches the same verdict the primary clause does. The result, `✓` = passed:

```
P1 ✗  P2 ✗  P3 ✓  P4 ✓  P5 ✓  P6 ✗  P7 ✗  P8 ✗  P9 ✗  P10 ✓  P11 ✗  P12 ✓  P13 ✗  P14 ✓  P15 ✗  P16 ✗  P17 ✗
P18 ✗  P19 ✗  P20 ✗  P21 ✗  P22 ✗
```

All **ten** pins move. The six green guards are green for the reason their labels give — their
referent is a revision that does not exist yet — and the four red ones (P8, P9, P11, P17) guard a
*machinery* the fix introduces, so on a tree without it they cannot pass: P8 and P17 miss their
warning line, and P9 and P11 miss the write. **This matrix is what caught P15 being wrong** (see the
ledger): an earlier cut of it asserted the row-count *predicate* below instead of a real heal, which
is green on **both** trees, and no reading of the check would have shown that.

**P18–P22 are red on a different path, and the difference is stated rather than smoothed over.** The
in-tree shim above works by grafting a no-op onto HEAD's `render_dashboard` — but it lives *inside*
`tests/smoke.py`, and the `git archive HEAD` tree runs **HEAD's own** `smoke.py`, which contains the
first seventeen items and not these five. So the matrix's second row was re-derived by a standalone
harness — one process per tree, same discipline — that asserts these five properties and only these
against HEAD's scripts, with `getattr(ms, "store_local_index", None)` standing in for the missing
symbol so P22 reports **its own** reason ("*`store_local_index` does not exist on this revision*")
rather than aborting the block and taking the per-item attribution with it. That harness is scratch,
not committed; what is committed is the five checks, and the property claimed of them — **each fails
on pre-fix code** — is what both rows measure.

**And the RED runs twice for these five, because revision 9 is where they were found.** Measured on
revision 9 *before* the repair landed: **1937 passed, 5 failed** — all five of them, each for its own
reason, which is the strongest available evidence that they are pins and not guards. After the repair:
**1942 passed, 0 failed**. A pin whose RED exists only against pre-fix code has been shown to be
*capable* of failing; one that is also RED against the revision that introduced the machinery has been
shown to be *necessary* for it.

**The invariant.**

- **P1 — the self-falsifying record warns.** Feed
  `{"budget": {"index": {"before_tokens": 1746, "after_tokens": 1746}}, "audit": {"operations":
  [{"path": "memory/MEMORY.md", "store": "memory", "op": "modified", "token_delta": -52}]}}` to
  `validate_cycle_record` and assert the new message. Pre-fix: silent. **PIN.**
- **P2 — the matcher finds the fixture's spelling.** The same record with the bare
  `{"path": "MEMORY.md", "store": "memory"}` must warn identically. Pre-fix: silent. **PIN** — the pin
  for C8, on **coverage** grounds: without it the check is invisible to every fixture-shaped input,
  which is to say to P1, P3 and P5 themselves. It is explicitly **not** a gate-protection pin —
  measured, no §4 gate reddens under the exact-spelling matcher, because that matcher finds 0 of the
  fixture's **8** index rows and goes silent rather than wrong. (The denominator is 8, not 9 — the
  fixture's `token_history` holds eight entries, one record each, and the harness passes
  `record=history[-1]` so `_same_dream` dedups the record against itself. §C8's table header and the
  amend ledger both already say 8 and both name the 9 as retired; this pin list was the one place the
  old denominator survived.)
- **P3 — a consistent record is silent.** Same shape with `after_tokens: 1694`. **GUARD** — green
  pre-fix by construction; it guards against the check becoming vacuously red, and its referent is
  any revision of the check itself.
- **P4 — a repo `MEMORY.md` is not the index.** `{"path": "MEMORY.md", "store": "repo_doc"}` with a
  nonzero delta must **not** satisfy arm 1. **GUARD** — it moves on C8's **variant 2** (basename +
  store-blind), the only one of the three measured candidates that gets this case wrong; no shipped
  revision has it. This guard is the sole justification for C8's store conjunct.
- **P5 — absence is not failure.** No `audit` block; `before_tokens` as a string; **and a junk row** —
  `{"path": null}`, a row with no `token_delta`, and two rows that both normalize to `MEMORY.md` — all
  silent, never raising. **GUARD** — its referent is a revision that adds the check **without** §2.4's
  three abstentions; on pre-fix code there is no check at all, so nothing can raise. The junk-row arm
  is the one with a live failure mode behind it: `{"path": null}` raises `AttributeError` in a naive
  matcher, **inside the validator**.

**The refresh pins need a store, not a bare dir.** §2.3's precondition means that `--persist` into an
empty directory now takes the leave-as-authored path — which is exactly what `tests/smoke.py`'s
existing persist helpers (`_pdir54`, `_p41`, `_p41b`) do. P6–P12 and P16 therefore **cannot reuse
them**: each must build a temp store holding a real `MEMORY.md` — plus a few fact files, for the
`schema_drift` and `recall_facts` leaves — before rendering. Stated once here because it is a property
of the fixture rather than of any one pin, and because the failure mode of getting it wrong is uniform:
every one of those pins goes green while testing nothing.

**The refresh.**

- **P6 — the refresh is real.** Render a record whose `after_tokens` is stale, persist, and assert
  the appended log line's `budget.index.after_tokens` equals a fresh store-local measurement.
  Pre-fix: the stale value is logged. **PIN.**
- **P7 — the closure.** `cliff_pct`, `fat_hooks` and `hook_max_tokens` on the appended line match
  the fresh read, so no two linked values on the gauge line can disagree. Pre-fix: silent (the keys
  are not refreshed at all). **PIN** — and it fails on round 1's key set, which is why it exists.
- **P8 — the refresh never blocks.** Force a measurement to raise (monkeypatch) and assert: exit
  code unchanged, record byte-identical to the authored input, one stderr line, no exception.
  **GUARD** — its referent is a revision that adds a refresh *without* the handler; on pre-fix code
  there is no refresh to fail, so only its stderr clause could move, which is not teeth.
- **P9 — no partial state.** Force the refresh's **last** measurement call to raise and assert every
  leaf is at its authored value — the direct pin for §2.3's mechanism. The refresh makes **two**
  injectable calls, not twelve: `ms.store_local_index` produces **nine** of §2.2's twelve leaves
  (seven index measurements, `recall_facts.after`, and `over_ceiling` — the last computed at the call
  site from `il[2]`, but from that call's return), `ms.schema_drift` one, and the remaining **two**
  (`budget_tokens`, `ceiling_tokens`) are module constants read directly — a third source, but not a
  fallible one, so it can neither throw nor be patched. *"The second of the nine measurements"* — the
  sentence that stood here — conflated leaves with calls in a way that names nothing injectable, and
  the count has since moved twice: nine **leaves**, **two calls**, and the nine index leaves are one
  dict literal, so no "second" exists to patch. **The position is the whole point, and only the last
  one has teeth**: a revision that assigns incrementally has already written the index and
  `recall_facts` leaves by the time `schema_drift` throws, so the record is left in exactly the
  half-state §2.3's ONE SPLICE forbids — while patching the *first* call throws before anything is
  measured and so passes such a revision **vacuously**. A block-level splice is **not** P9's to
  catch (every leaf would sit at its authored value under one); it is P11's, whose `health`-block
  members a replaced mapping cannot survive. **GUARD** — its referent is a revision that assigns
  incrementally.
- **P10 — the gate.** The same record rendered **without** `--persist` keeps its BEFORE state
  unchanged. **GUARD** — moves on a revision that widens the gate to previews.
- **P11 — the whitelist holds.** Assert every key in §2.2's Out-list is byte-identical across a
  refresh, `marker` first among them. **GUARD** — moves on a revision that block-splices.
- **P12 — idempotence survives.** `marker` is untouched by the refresh, so a second `--persist` at
  the same `(commit, timestamp)` still returns `"duplicate"` and appends nothing. **GUARD** — its
  referent is a revision whose refresh widens past §2.2's Out-list far enough to write `marker`; on
  the specified design that key is never touched, so only that widening could move it.

**The heal gate.**

- **P13 — a duplicate with a differing record heals.** Write a cycle file, persist, then re-render
  with a record differing beyond `narration.verdict`, and assert `paths[0]` converges. Pre-fix: the
  file is left stale. **PIN.**
- **P14 — and the log does not grow.** Assert `_already_logged` still reports the pair and the log's
  line count is unchanged — the direct guard for R4. **GUARD** — its referent is a revision whose
  heal appends on a duplicate rather than converging; R4 *is* that failure mode, which is why this is
  a guard and not a pin: on pre-fix code there is no correction to carry, so there is nothing for the
  log to grow from.
- **P15 — the double-embed case, and the fixture condition that makes it a pin at all.** The
  `unhealed file / healed file` pair from §2.5: assert the widened heal yields **one** row where the
  narrow heal yields two. **PIN** — it is the second defect the widening closes — **but only on a
  fixture where the logged record and the file-side record do not BOTH carry the same non-empty
  `session`**, and that precondition is stated as a *negation* deliberately: two earlier revisions
  each wrote it as a positive condition and each got it backwards — round 2 said "a fixture whose
  record carries **no `session`**" (not necessary, and not sufficient), and revision 6 said "a fixture
  whose file-side record carries a session **equal** to the logged record's", which is not a
  precondition for the pin at all but the **one shape that makes it vacuous**. The table below is what
  both sentence-writers were reading past: `logged S1 · file S1` is the single row that collapses
  before the heal, so healing it changes no row count. Re-derived on the
  live predicate 2026-09-14, all five shapes. `same` is `_same_dream(logged, file)` for the file in
  its **unhealed** state (empty `marker.timestamp`); `rows` is the length of `assemble_cycles(file,
  logged)`; the healed column is omitted because the heal fills the stamp and every row then reads
  `True / 1`:

  ```
  logged S1  ·  file S1     ->  True   collapsed  → 1 stale row  → P15 VACUOUS
  logged S1  ·  file S2     ->  False  appended   → 2 rows       → pin holds
  logged S1  ·  file NONE   ->  False  appended   → 2 rows       → pin holds
  logged NO-S · file S1     ->  False  appended   → 2 rows       → pin holds
  logged NO-S · file NONE   ->  False  appended   → 2 rows       → pin holds
  ```

  "No session" is **not necessary** — a file carrying a *different* session pins just as well — and
  it is **not sufficient** either, since it names one of the four pinning shapes while the single
  vacuous shape is session *equality*. Nor is the file side the whole condition: the logged record's
  own session is the other operand, which is why the `logged NO-S` rows read differently from
  `logged S1` against the same file. The mechanism is `_same_dream`'s fall-through: with the file's
  stamp empty, the both-stamped arm is skipped and control reaches the session arm, where two
  non-empty equal sessions collapse — and when either session is absent, control falls to raw
  `_marker` equality, where an empty stamp never equals a stamped one, so the row is appended. (The
  round-2 wording is the `dropped-hedge-becomes-false-universal` failure in miniature: a repair that
  correctly identified *one* vacuous shape, then promoted it to "only.") The shape is live rather
  than hypothetical: records lacking a session are in the archive today (measured 2026-09-14 —
  **10 of 67** unique on `(commit, timestamp)` across the fleet union, **4 of 30** in this project's
  own log). Both counts move as dreams land, so P15 asserts the *precondition* and never the census.
  **One operational consequence, learned by writing the check and worth stating because it is what
  makes the negation easy to violate in practice**: `rd._demo_record()` carries `session`, so every
  fixture derived from it — which is most of them — puts *both* sides in the vacuous row by default,
  and the check then reads `1 → 1` on **either** revision. The fixture must therefore *remove* the
  session from the file side (the log's line keeps run 1's), which reproduces
  `logged S1 · file NONE`. That the trap is reachable from the fixture the whole suite is built on
  is the strongest argument for stating the precondition as a negation rather than a description.

**Ordering.**

- **P16 — the invariant checks the refreshed value.** Run a persist render whose refresh produces an
  `after_tokens` that disagrees with the audit, and assert (a) the WARN fires **and** (b) the numbers
  in the message are the **refreshed** ones, not the seed's. Pre-fix: silent. **PIN** — and (b) is
  load-bearing: asserting only that a warning fires passes under *both* orderings, because the
  unrefreshed seed mis-matches the audit too. That was round 1's P13, and it had no teeth.
  **This pin carries a constructibility precondition the others do not**: the fixture's `MEMORY.md`
  must be **moved on disk** between the seed's read and the render, or `fresh == seed`, clause (b)
  holds under both orderings, and the pin is vacuous again — the same vacuity (b) exists to close. §5
  already names the one real state that moves the index between the two measurement times (a loop-back
  re-render against a previous attempt's audit block); construct **that**, rather than inventing a
  third state.

**The precondition.**

- **P17 — an absent index is not measured as zero.** `--persist` into a directory with no `MEMORY.md`,
  rendering a record whose `after_tokens` is a real value; assert the logged line carries the
  **authored** `after_tokens`, that `over` / `cliff_pct` / `recall_facts.after` are unchanged from the
  authored record, and that exactly one warning reached stderr. **GUARD** — its referent is a revision
  that adds the refresh *without* the precondition, which is precisely the revision §2.3's
  zero-fabrication describes, and the one this pin exists to prevent. On pre-fix code the record is
  left as authored too (there is no refresh at all), so only the stderr clause could move, which is not
  teeth.

**The pre-fix matrix, extended — and the class the first seventeen items structurally could not see.**
Every item above tests a leaf's **own** movement: *did `after_tokens` stop mirroring `before_tokens`?*
*Did the authored block survive?* That is a **dyadic** property — one leaf, before and after — and a pin
per leaf can falsify it and nothing else. **Four of round 3's six findings are triadic**: they exist
only in the relation *between* two leaves (`over` against its own denominator), or between a leaf and
its **reader** (`over_ceiling` against the gauge line that renders it), or between a leaf and the
**claim** that it was measured (`advisory_stranded_globals`). No set of per-leaf assertions over §2.2's
In-list can express "these two leaves moved to values that cannot both be true" — and that is not a
gap in how the pins were written, it is what the *shape* of a per-leaf pin excludes. The five items
below are therefore stated as relations, which is the only form in which their class is falsifiable.

- **P18 — the ceiling verdict is re-derived with the index it judges.** A record seeded
  `remediation = {"required": True, "lever": "prune", "over_ceiling": True}` over a store measuring
  below `INDEX_CEILING_TOKENS`, refreshed: assert `over_ceiling is False` **and** `required is True`
  (the verdict that reads record state must not move). Pre-fix: the seed's `True` survives — and on
  revision 9 too, which is the whole finding: the alarm outlives the index that raised it. **PIN.**
- **P19 — the guard's operand, one capture per arm.** A 200-line over-target `MEMORY.md` (measured
  3422 est tok), refreshed twice — once against a record whose **top-level** `remediation` is a
  standing-justified banner, once against a record carrying the **phantom** `budget["remediation"]` key
  no producer emits. Assert `[]` on the first and exactly one warning on the second. **GUARD** — its
  referent is **revision 9**, which read the operand off `budget`: measured there, the top-level arm
  warns and the phantom arm is suppressed, which is also exactly one warning, **from the wrong arm**.
  The item passed on revision 9 until the arms were split — *a count says how many moved, a probe says
  which*, the repo's own norm, hit by this file's own item.
- **P20 — the denominator is refreshed with the numerator.** Refresh a record authored with
  `budget_tokens: 1200, over: True` and assert `budget_tokens == INDEX_TOKEN_BUDGET`,
  `ceiling_tokens == INDEX_CEILING_TOKENS`, and `over == (after_tokens > budget_tokens)`. Pre-fix:
  `1200`, `None`, and a stale `over` — a gauge deriving `_bar`, `_pct` and `_over` from a live
  numerator over a retired threshold. **PIN.**
- **P21 — a leaf the refresh did not measure is not authored as a zero.** A record whose
  `health.schema_drift` is **legacy-shaped** (`{"missing_node_type": 3}` only) is refreshed: assert
  `missing_node_type == 2` (the measurement landed) and `"advisory_stranded_globals" not in` the block.
  Two clauses, two referents, and the item is RED on both: pre-fix fails the first (nothing is
  measured), **revision 9 fails the second** (the preserved-seed branch fabricated a `0` for a field
  the `canonical_stems=None` path cannot measure). **PIN.**
- **P22 — the guard and the measurement are one expression of the path.** `store_local_index` is
  monkeypatched to report an `index_path` that does not exist (while `<store>/MEMORY.md` does), which
  is the shape a future index rename produces; assert the record is **byte-identical** to the authored
  input and that exactly one skip line was printed. **GUARD** — its referent is **revision 9**, whose
  precondition rebuilt `store / "MEMORY.md"` beside the measurement's own path: with the two sites
  diverged the guard passes on the real file while `_measure` reads a different one, writing
  `after_tokens: 0` beside a true `before_*` — §2.3's fabrication, reached through the check that
  exists to prevent it.
- **P23 — "a live reference" is a property of the SOURCE, not of the value.** Parse `render_html.py`'s
  AST and assert that each of its three budget constants (`INDEX_TOKEN_BUDGET`,
  `CLAUDE_MD_TOKEN_BUDGET`, `INDEX_CEILING_TOKENS`) is assigned an **attribute of `ms`**, not a
  literal. **PIN** — RED on the pre-fix operands, which carried `1500` and `4000`; nothing else about
  the module changes, so the ✗ is the literals and only the literals. The equal-*value* half is a
  rewrite of the pre-existing v0.1.66 check rather than a new item (no census movement): widened from
  one constant to three, and relabeled — because that check's **label** read "a live reference, not a
  hardcoded copy" while its **condition** was `==`, which a literal copy passes on the day it is
  written. Measured rather than argued: on the mutated tree the equality half prints **✓** and only
  P23 goes red. Same shape as the other five repairs in this revision, one domain over — a check whose
  name asserts one property while its predicate tests another.

**Revision 9 as a referent is new, and it is a consequence of the review being adversarial rather than
anticipatory.** P19 and P22 name a revision that **exists and was measured**, where every earlier guard
names a hypothetical one ("a revision that adds the refresh *without* the precondition"). That is the
stronger label, and it was available only because the implementation the first seventeen items certify
was itself put through review: a guard whose referent is real has been observed to fail, not merely
argued to be capable of it.

**Smoke census.** The census constant moves only if checks are added; the pre-change figure was
`1750 + 45 + 125`, the revision-9 figure (seventeen items in) was `1767 + 45 + 125`, revision 10's
was **`1772 + 45 + 125`** (the five round-3 items, `+5` on the first addend and nothing else), and
this revision's is **`1773 + 45 + 125`** — P23, `+1` on the first addend. Each figure is re-derived
from a run, never carried: the constant is the full-suite total *including the census check itself*,
so a carried number is a check that certifies a count it did not produce. P23 is why the revision-11
figure is a run rather than an increment by hand: a check that replaces another moves nothing, and
only a run can say which of the two new clauses that is.

## §4 Ship shape

One PR, one branch (`fix/record-post-state`), landed as a **patch** (v0.4.30) — no schema, flag, or
install-contract change; legacy records still render and the new WARN never blocks.

**Scope is the post-state only.** The C9 item (`AGENTS.md:19`'s stale table cell and the three blinds
in `tests/docs_links.py`) is **not on this branch** — §6 records the split and its rationale. The
docs gate is still run below, because it is a gate on the tree this branch lands rather than a claim
about the cell. **It is expected to exit 0 both before and after this cycle, and that green is the
blind gate reporting** — the stale cell is still stale on this branch. Do not read a zero there as
evidence the docs surface is current; read §6.

**What this branch must also carry, because the release harness reads it.** Cycle A established the
pattern: the `## [0.4.30] — <date>` CHANGELOG section is authored **on this branch**, since
`release.sh` reads the target version from the top CHANGELOG section and refuses an unfilled stub.
Two things it must name, because they are user-visible even though the new WARN never blocks:

- **The post-state refresh changes what a persisted record reports.** A record's `after`-side figures
  now describe the store at persist time rather than at seed time, so the same pass can log
  different `after_*` values than it did before this release. That is the fix, and it is also a
  change in what the archived record says.
- **The heal widening changes what a duplicate re-render writes** — a corrected `budget`/`health`
  now reaches the cycle file, and `reconcile_marker` filling an empty stamp can change the row count
  (§2.5).

**Do not bump the live docs when you author the CHANGELOG.** `docs_links.py`'s badge check compares
README's badge against `plugin.json`, and its currency invariant compares each `LIVE_DOCS`
statement against `plugin.json` too — **neither reads the CHANGELOG**, and the CHANGELOG is not in
`LIVE_DOCS`. So the CHANGELOG section may lead the tree, but the badge, the six statements, and
`plugin.json` move together or not at all: bumping the docs to `0.4.30` ahead of `plugin.json` reds
the gate for no reason at the one moment it is least welcome.

Gates, all re-run at the committed revision:

```
python3 tests/smoke.py
python3 tests/docs_links.py
python3 tests/simulate_accumulation.py
mypy --config-file mypy.ini
python3 tests/validate_manifests.py
python3 tests/dashboard_browser.py --out /tmp/cm-browser
```

**End-to-end, the identity that fails today:** after a real `--persist`, assert the logged record's
`after_tokens` equals a fresh `memory_status.py --json` read on the same store. This is the
acceptance test; P1 is its offline form.

**Mutation-verify on the committed revision.** Every pin must fail on pre-fix code. Per the standing
discipline, a pin's RED count belongs to the triple (restored code, fixture, harness) and is never
carried across an edit. P2 and P7 additionally require the two spellings and the closed key set to be
exercised *together*, since each was found by a reviewer attacking the other's assumption.

## §5 Known ceilings (documented, not solved)

- **The invariant's timing precondition: a second measurement time.** The audit delta is Phase0→Phase5;
  the refreshed `after_tokens` is measured at the terminal render. The identity holds **only if
  nothing wrote the index between them**. That is the normal case — Phase 5 is the last writer and
  the terminal render follows — but a loop-back re-render after an exit 3/exit 4 re-renders against
  the *previous* attempt's audit block, and there the refresh is measuring a newer index than the
  audit saw. In that state the check suspects an **honest** record. This is a **false-positive**
  ceiling, and round 1 stated the opposite — that the failure direction is "a missed warning, never a
  false one." It is a genuine false warn, narrow and accepted, in the same shape as the
  `demotion.verdict` check's own *"Known false-warn ceiling, accepted"* note.
- **The two operands use different text transforms.** `_measure` reads
  `read_text(encoding="utf-8", errors="replace")` — universal-newline translation — while
  `audit_snapshot`'s `_add` uses `read_bytes().decode("utf-8", "replace")`, which preserves `\r`.
  The divergence is **absolute** — one byte per line break — so the two readers sit ≈`lines/4` tokens
  apart: **9 tokens** on the live index (1889 est tok, 36 lines), measured at **10 / 9 / 11 / 11 / 14
  / 19** after +1/+2/+5/+10/+20/+40 lines. Round 2 cited exactly those six numbers as `auditΔ −
  measureΔ`, and they are not that — the identity compares **deltas**, and a constant per-file offset
  cancels in a difference. What breaks the identity is the offset's **growth**, which is far smaller:
  `auditΔ − measureΔ` = **+1 / 0 / +2 / +2 / +5 / +10** over the same six edits.
  **The zero is the finding.** At +2 lines the identity *holds by rounding* while the operands are
  still 9 tokens apart from what the other reader would have reported — so on a CRLF store the check's
  verdict tracks the **size of the edit**, not the honesty of the store: small edits pass it, large
  ones fail it, and neither verdict is about the record. The LF control is exact (gap 0 at every size,
  the two readers agreeing to the token), which is what makes this latent rather than live. Recorded,
  not fixed: the repair is to converge two readers, which is its own change.
- **Cut arm: "no row ⇒ the index did not move."** The inference is sound except when the file was
  unreadable in **both** snapshots (`_add` returns on `OSError`, so a label can be absent for a
  reason other than an unchanged hash), and it is unsound across the two measurement times above. It
  was cut for a stronger reason: measured, all 14 records it would cover have `after == before`
  identically, so it cannot fire on any of them — its only reachable firing is the false positive.
  A related low-severity case survives for the arm that *did* ship: an `OSError` on the *after*
  snapshot fabricates a `deleted` op (`b and not a`), which would move the delta the check compares.
- **`claude_md.after` / `after_tokens` / `over` and `budget.claude_md_hierarchy` stay Phase-0
  values.** They need the repository root, which C7 shows the store handle cannot supply. So the
  measured C2 defect for the hierarchy measure is **not** repaired by this cycle, and the step-4-tail
  instruction that names `budget.*.after` remains the only path for the `claude_md` half — now with
  §2.6's correction saying so explicitly rather than by omission.
- **`budget.index.over` and `maintenance.over_budget_not_justified` disagree — and they already did,
  before this cycle.** Round 1 wrote that they "agree at seed time (both derive from the same Phase-0
  over-target test)"; that is **false at the source**. `seed_record` writes
  `"over": ctx["index_lb"][2] > INDEX_TOKEN_BUDGET` unconditionally, while
  `over_budget_not_justified` is `bool((remediation or {}).get("required"))` — and the TypedDict's own
  comment on that field reads *"the dual-axis suppression result; NOT a fresh budget compare."*
  Standing-justify is exactly the state where they come apart: the gate fired and was suppressed, so
  `required` is `False` while the index is over target. Measured on the live store, **8 of the 10**
  standing-justified records carry `over: True` beside `over_budget_not_justified: False`. So the
  refresh does not *create* this divergence — it makes a pre-existing one **visible**, because it
  moves the measurement and never the verdict, while §2.3's warning names the gap instead of
  suppressing the write that exposes it. Both readings are true at different times.
- **The renderer's budget-source advisory can now fire benignly.** `render_dashboard` compares the
  gauge against `network.trigger.always_loaded_tokens` — measured by `sync_global --tokens` at Phase
  1, before the pass writes the index — and above 1.5× prints *"budget sources disagree … possible
  cycle-record collision (check the --seed path)"*. The first time the refresh makes `after_tokens`
  honest, a pass that grew the index past 1.5× makes the **Phase-1 node** the stale side, so a
  pre-existing red advisory now names the wrong cause. The beta oracle pairs the same two quantities
  and grades the split HIGH, so the collision is detectable there — but its message is now ambiguous.
- **`after_bytes` is written and never read.** Repo-wide, `budget.index.after_bytes` has **no
  reader** — and the distinction between a writer and a reader is the whole claim, so it is drawn
  explicitly here. Measured over the whole tree, the **seven files** that contain the token at
  `fa91254` are all
  writers or transcribers, and none is a consumer: `memory_status.py` (two sites — the TypedDict
  declaration and the seed assignment); one fixture-builder keyword argument in
  `tests/dashboard_fixture.py`; two fixture *data* corpora (`tests/fixtures/dashboard-header-geometry.json`,
  `docs/previews/nocturne/sample.json`); the schema example in `SKILL.md`; the vendored
  `canary-v0.1.19/memory_status.py`; and the rendered preview page `docs/previews/nocturne/index.html`.
  **Seven files, eight sites, and the difference is the whole reason an earlier revision said
  "eight files" while listing seven** — and the *eighth* file exists only in the post-change tree:
  this cycle's own `_refresh_post_state` writes `"after_bytes": il[1]`, a writer the bullet's own
  next clause implies ("The refresh measures it anyway"). Stated against `fa91254` so the census is
  reproducible; counting the working tree gives eight, for a reason that is this cycle rather than the
  product. (An earlier draft of this bullet enumerated only three sites — the
  declaration, the seed, and "a test fixture" — which understated the corpus surface; the count was
  wrong, though the conclusion it supported was not, since none of the omitted sites reads the key
  either.) The nearest neighbour is instructive: `render_dashboard` *does* consume the sibling
  `after_lines`, in the delta at `idx.get("after_lines", 0) - idx.get("before_lines", 0)` — so the
  family is genuinely closed and one leaf of it is genuinely dead. The refresh measures it anyway,
  because leaving one leaf unwritten would make the closure claim false; but no gate depends on it
  and the spec does not claim one does.
- **`health.index_pointers_ok` is hard-coded `True`** in the seed, along with `broken: []` and
  `dangling_links: []`. Measured **currently correct** — the live index/`fact_files` symmetric
  difference is four stems, all file-only (unindexed), with zero index-only entries — so this is a
  latent defect (a constant cannot detect a regression), not a live falsehood. Out of scope here:
  **`ctx` has no `dangling_links` key at all** — round 1 wrote that it was `None`, and measured,
  `"dangling_links" in ctx` is `False` and the subscript raises `KeyError`. `build_context` computes
  only the *count*, into `maintenance.dangling`; the `list[str]` the round-1 sentence reached for is
  the seed's hard-coded `[]`, not a context value. The archive's JS requires all five health keys, so
  "refresh it" was never the right repair. It needs a real computation, and it is the same class as
  the index-periphery cycle.
- **`budget.index.budget_tokens` is read with FOUR different defaults — not two, and not the three
  round 1 recorded.** `0` in the gauge (`idx.get("budget_tokens", 0)`), `1200` in the remediation gate
  (`_dget(record, "budget").index.get(...)`), **`'?'`** in `_over` — the banner reads
  `b.get('budget_tokens', '?')` off the **tier** Mapping it is handed (`_over(cm)` / `_over(idx)`; its
  docstring: *"the ACTIONABLE over-budget flag for a project always-loaded tier"*), so a missing key
  on a *tier* measures
  `⚠ OVER ≈? tok BUDGET` (verified by calling `_over({"over": True})` directly). An earlier revision
  said the read was "off the whole budget Mapping", which would make `≈?` **universal** on every
  record with `over: true` — `budget` carries no `budget_tokens` key at all (its keys are `claude_md`,
  `global_claude_md`, `index`, `recall_facts`, `claude_md_hierarchy`), so the operand is what makes
  this a per-tier default rather than a defect in every store. The count of four is unaffected — the
  fourth is `1500` in the
  archive's JS (`num(BUD.index, 1500)`), the **live constant** `INDEX_TOKEN_BUDGET` threaded through
  `render_html`. The `'?'` is the sharpest of the four: the numeric defaults still print a number,
  while this one prints a placeholder into the one banner that means *prune or propose*, so a record
  with `over: true` and no `budget_tokens` advertises `≈?` at the exact moment an operator needs the
  number. The JS agrees with the seeded key, the Python `0` is the outlier, and there is one more
  place to converge than round 1 counted. **Round 3's write does not remove any of the four — it
  changes how often they are reached.** `budget_tokens` is now written as the live constant in the
  same splice as the measurement it qualifies, so a refreshed record's two numeric readers land on
  `1500` rather than on the record's snapshot; a *pre-existing* record keeps whatever its seed wrote,
  and the `0` / `1200` / `'?'` defaults still fire on the shapes that lack the key at all (the `'?'`
  one is off a **tier** Mapping, which the refresh never touches). The defect is unmoved because it is
  a read-side census, and a write-side repair cannot close one. Pre-existing, unrelated to post-state,
  and recorded rather than fixed to keep this cycle's diff auditable.
- **The historical six — five historical, one current.** **Five** of the six contradicting records
  predate this pass and will not be repaired by it — the refresh only affects records written from
  here on. They remain as measured evidence; the WARN will name them if anyone renders one. **The
  sixth is the newest record and it does not predate the pass**: it is this pass's own, and it now has
  a second life, existing in two divergent copies (§C3). An earlier revision called all six historical
  in the same bullet that named the sixth as the newest, and §C3 three sections earlier had already
  split them five-and-one — so the universal was the only thing in the file that disagreed. The
  number is artifact-bound like every other census here: it is six against the **log union**, five
  against the archive. **The WARN is reader-independent of both** — as §C3 now records, it validates
  the record being rendered, so it names a contradicting record only if one is re-rendered from its
  own file; the copy this bullet's count describes is the one `cm log` reads.

## §6 Carried item — split, decided

`AGENTS.md:19` and `tests/docs_links.py` (C9) were in the standing plan's Cycle B scope. **Decision
(2026-09-14): they do not ride this branch.** They are a **second root cause** — a matcher narrower
than its rule, not an unowned post-state — and §3's pin list does not cover them. They get their own
cycle, with the narrowing decision made explicitly. Three findings are the rationale:

1. **The value fix is trivial and independent.** Bumping the table cell needs nothing from this
   cycle, and shipping it here means the docs gate's redesign gates the post-state fix. The gate is
   **release-coupled** — `release.sh` runs `tests/docs_links.py` — so a redesign of it lands inside
   the release path either way.
2. **Blind 2 cannot be closed as literally stated, and the scope of the problem is larger than it
   looks.** "Compare every match instead of the first" would red the gate on **legitimate history**.
   Measured with `_CURRENCY.findall` per line across the six `LIVE_DOCS` entries, later `vX.Y.Z`
   matches number **183** — `AGENTS.md` 10 (8 distinct values), `CLAUDE.md` 10, `SKILL.md` **116**,
   `references/harness-map.md` 39, `docs/1.0-preflight.spec.md` 7, `README.md` 1 — every one a
   correct reference to a past release. The `\bv` convention exists precisely to separate a currency
   *statement* from a version *mention*, and the fix must narrow what counts as a claim. That is a
   design decision with its own review, not a matcher tweak.
   The obvious narrowing — check the plugin table's `Version` column — is mechanically
   implementable, but it is a **new, doc-specific** gate: `AGENTS.md` is the only `LIVE_DOCS` entry
   with a plugin table, so it closes neither blind as a class. Blind 1 still covers that cell unless
   the new matcher accepts a bare version, and Blind 2's first-match convention still governs the
   other five docs. Stating the alternative plainly matters more than implying it is the narrowing
   fix.
   **Blind 1 is not closable by accepting a bare version either, and that is measured.** Dropping the
   literal `v` from `_CURRENCY` turns the six docs' first-match picks into `CLAUDE.md` `1.0.0` (the
   versioning policy's major-release target, in prose), `SKILL.md` `127.0.0` (the loopback address in
   `python3 -m http.server --bind 127.0.0.1`), `docs/1.0-preflight.spec.md` `1.0.0` (the release the
   checklist certifies, named in its own opening line), `AGENTS.md` `0.4.27`, `README.md` `0.4.29`,
   and `references/harness-map.md` **nothing at all** — every one of that file's version tokens is
   `v`-prefixed, so a bare matcher finds no statement there and errors on the miss. Five of six red,
   and **only one of the five is about a version**: two are non-version triples, and the sixth is a
   miss rather than a mismatch. The `v` requirement is therefore **load-bearing for the gate's
   correctness, not a stylistic convention** — it is the only thing keeping an IP address and a
   future-release label from being read as currency statements. The gate's own docstring relies on
   exactly this ("the only way to trip a false positive is to mention a version *earlier* than the
   currency statement — write that mention without the `v`"). A fix that removes the `v` requirement
   does not narrow the gate; it replaces a blind gate with a wrong one.
3. **Blind 3 cuts the other way.** The missing `strip_verbatim()` produces false *positives*, so it
   is a correctness fix to a gate, not a coverage gap.

**What "carried" means here, precisely.** Not deferred in silence: **this section is the record, and
it ships with this PR.** The order is: land the post-state repair (this spec), then the docs gate as
its own cycle with the narrowing decision made explicitly. A recorded blind spot is a scheduled
defect — but scheduling it behind a decision is not the same as leaving it unrecorded.

**Two consequences of the split, stated so they are not discovered later:**

1. **`tests/docs_links.py` still runs as a gate on this branch, and exits 0.** That zero is the blind
   gate reporting, not a statement that the tree is current — `AGENTS.md:19` is stale here and stays
   stale until the docs cycle lands. §4 carries the same warning at the gate list, where a reader is
   likeliest to mistake the green for coverage.
2. **`release.sh` runs that gate inside the release path**, so the v0.4.30 release passes through the
   same blind check. Nothing in this cycle changes that, and nothing should pretend it does.

**What would make the split a mistake.** If the docs cycle never lands, the blind spot stops being
scheduled and becomes permanent — and the honest reading of this section would then be an excuse
rather than a plan. The cell's staleness is *measurable* (walk `AGENTS.md`'s table column against
`plugin.json`), so the next cycle has a concrete acceptance test and no new research to do.

## Evidence ledger

Every figure in §1 is re-derivable from the branch tip `fa91254` plus the live store, except where
noted.

| # | Claim | Provenance |
| --- | --- | --- |
| C1 | Six mirrored pairs, twelve keys, same subscript expression | Re-derivable from `seed_record`'s `budget` block |
| C1 | `marker` genuinely differs and must be excluded | Re-derivable from `seed_record`'s `marker` block |
| C2 | 4 of 7 drift fields under-report; zero over-report | Live store + `build_context`; re-derived |
| C2 | `index_mismatch` floor of 3, from mtimes vs. the pass floor | Live store mtimes; re-derived |
| C3 | The newest record exists in **two divergent copies**: the log reads `1746 → 1746` (contradicting its own audit's `−52`), the `--cycle` file reads `1746 → 1694` | Both artifacts, plus the `diffs/` sidecar proving the index moved; see §C3 |
| C3 | Same file, same estimator | `audit_snapshot`'s `_add` + `est_tokens` |
| C3 | 31 checkable / 6 contradict / 24 not checkable (**on the log**); 5 contradict on the archive | Re-derived over all 55 unique records, **per artifact** |
| C4 | The instruction names 3 tokens for 8 leaves | Re-derivable from the SKILL text |
| C5 | Both sinks receive the same dict object; a duplicate appends nothing | `_persist` + the heal block |
| C5 | `assemble_cycles` has no per-line freshness signal in scope | Re-derivable from the function body |
| C6 | Write path is the project-id ops slot; 55 unique records | Re-derivable by calling the retention constructors |
| C7 | `--persist DIR` is the store handle; `<store>/MEMORY.md` is the index | `_persist`, the no-dir comment, `build_context` |
| C7 | Store-local measurement: median 0.0017s user CPU (N=5, five fresh processes) at a 1889-token index; `build_context` 0.0272s → **~16×** | Timing re-derived on the live tree; both operands carry their clock and process isolation |
| C8 | The fixture emits bare labels; the fixture asserts the identity | `tests/dashboard_fixture.py` |
| C8 | Three matcher variants: 0/8 · 8/8 · 8/8 on the fixture (`record is history[-1]` → 8 distinct rows), **identical on all 55** live records | Re-derived over both corpora |
| C3 | 7 exact zeros of 31 **on the log union**, at positions 17/12/7/6/4/3/0 back from newest; 3 of the 7 honest | Re-derived from record timestamps + deltas; the archive reads **6** at positions 17/12/7/6/4/3 — position `0` dropping |
| C3 | Mirror cross-tab cm × rf = 10 / 3 / 18 / 0 over the 31 row-carrying records, **on the log union** | Re-derived from the same 31 records; the archive reads `11 / 3 / 17 / 0` — one rf leaf differs, the zero row does not |
| §2.3 | Every §2.2 measurement returns a well-formed zero on an absent index; none raises | Measured against the live tree |
| C9 | `docs_links.py` exits 0 on a stale cell, stale for two releases | Re-derived on `fa91254` + the commit walk |
| C9 | 183 later `vX.Y.Z` matches across the six `LIVE_DOCS` entries | Re-derived by `_CURRENCY.findall` per line |
| C9 | The cell moved at `1864f68`, then froze through `9696dfb`/`296a012`/v0.4.29 | The `AGENTS.md` commit walk |
| C9 | A bare-version matcher reds 5 of 6 live docs; only 1 of the 5 is about a version | Re-derived: each doc's first match under `\b\d+\.\d+\.\d+\b` |

Two figures are **live-store only** and cannot be re-derived from a blob: the drift counts in C2 (the
store is uncommitted by design) and the 55-record archive census (it lives under plugin-data). Both
are stated with the artifact they were measured on.

## Amend ledger

- **2026-09-14 — initial draft.** Authored from a re-derivation of the audit's Cycle B findings. Three
  corrections to the standing plan are folded in rather than appended, because each changes the
  design and not merely its prose: `_heal` is a local boolean, not a function; the refresh
  instruction lives at the tail of step 4, not in step 7; and the plan's `assemble_cycles` remedy is
  replaced by the wider heal gate because the freshness signal the plan called for does not exist to
  be added. The `AGENTS.md` / `docs_links.py` item is carried with a split recommendation (§6).
- **2026-09-14 — revision 2, after round 1 of adversarial review (three independent reports).** Each
  finding and what it changed:
  - **The key set was not closed** (two reviewers, independently). `cliff_pct`, `fat_hooks` and
    `hook_max_tokens` derive from the same read as `after_bytes`/`after_lines` and were absent from
    both lists, so a refreshed gauge would print arithmetically impossible pairs on one line.
    §2.2 now states a **criterion** and derives the closure from it.
  - **The seam contradicted its own constraint** (all three reviewers). §2.1's named seam sat 37
    lines *after* `validate_cycle_record`, which would have made the new check fire on 28 of 31
    records every pass. §2.1 now names the validator's own seam.
  - **The ordering pin could not fail** (round 1, F2). P16 now asserts the warning's **operands**.
  - **The invariant crosses two measurement times and the ceiling was stated backwards** (round 1,
    F3). §5 now records it as a false-positive ceiling, correctly.
  - **The matcher missed the in-tree second spelling** (two reviewers). Round 1 justified this with a
    consequence revision 3 measured as **false** (see below); the correction stands, but on *coverage*
    grounds rather than gate-reddening.
  - **The project-dir recovery did not exist for unenrolled projects** — `project_path` is written
    only by `_write_stacks_cache`, which `--pull` returns before reaching. Chasing it dissolved
    §2.3 entirely: the persist argument *is* the store handle (§C7).
  - **The `over` ↔ `remediation` identity, and the suppressed HARD CEILING banner.** §2.3 now warns
    on the damaging direction instead of writing an inconsistent block.
  - **"No partial state" had no mechanism.** §2.3 now specifies the scratch-dict single splice, with
    the measurement showing why it matters (`validate_cycle_record` never descends into `budget`).
  - **C5's duplicate premise was inverted.** Corrected, and it strengthens the heal argument.
  - **§2.5's blast radius was false.** The widened heal *can* change the row count, via
    `reconcile_marker` filling an empty stamp. Corrected, with P15 pinning the direction.
  - **The pin count was inflated.** Thirteen items were called pins; seven fail on pre-fix code. §3 now
    labels each guard with its referent revision and keeps it out of the count.
  - **Census restated.** Round 1's second arm counted 14 records it cannot fire on; the honest figure
    is 31 checkable / 6 contradict / 24 not checkable.
  - **§6 understated.** 183 later matches across `LIVE_DOCS`, not 10; the gate is release-coupled;
    and the table-column alternative closes neither blind as a class.
- **2026-09-14 — revision 3, after round 2 (three independent reports).** Round 2's defining feature is
  that **three findings attributed real numbers to revisions that no longer exist** — the cost of
  carrying a measurement across an edit. Each was re-measured against the shipped design; two came back
  smaller, one larger:
  - **§C3's "all of them the most recent four" was false** (round 2, F6). The four newest row-carrying
    records are `09-05T19:51` (zero), `09-12T01:19` (**−35**), `09-12T21:28` (**−1298**), `09-14T00:36`
    (zero). The true zero population is **7 of 31**, at positions 17/12/7/6/4/3/0, and **3 of the 7 are
    honest**. §C3 now states the population and a mirror cross-tab instead. The replacement population
    round 2 proposed was *also* wrong — it read `09-12T01:19` as refresh-marked when both of that
    record's families are mirrored — so the table is re-derived here rather than adopted.
  - **§C8's "warns on 8 of 8 and reddens two of §4's gates" was false** (round 2, F1). That is **arm
    2's** number, carried into a revision that cut arm 2. Measured: the exact matcher finds **0 of 8**
    fixture rows and is **silent**, and all three candidate matchers are **identical on all 55 live
    records**. The matcher correction survives on **coverage** grounds — the fixture is the check's only
    in-repo test surface — which is the stronger ground regardless. (Round 2 wrote "0 of 9" here; the
    fixture holds 8 distinct rows, since the harness passes `record=history[-1]` and `_same_dream`
    dedups the record against itself. The denominator was wrong in both rounds; the zero was not.)
  - **The refresh could fabricate an all-zero post-state** (round 2, confirmed at source; the round's
    highest-severity finding). Every measurement returns a well-formed zero on an absent index and none
    raises, so §2.3's never-blocks contract never fires; a bare `--persist` dir — which `tests/smoke.py`
    supplies to **ten** invocations — would log `after_tokens=0`, `over=False`, `cliff_pct=0` and an
    all-zero `schema_drift` beside a real `before`. §2.3 gains the `<store>/MEMORY.md` precondition,
    P17 guards it, and §3 states once that the refresh pins must build a real store.
  - **The matcher needed two more conjuncts and three abstentions** (round 2, F2, F3, F5). Normalizing
    one leading `memory/` and requiring exactly `MEMORY.md` closes a latent first-match-wins hole
    (`memory/AA/MEMORY.md` sorts first; **0** live occurrences); the `store` conjunct is P4's sole
    justification; and ambiguity, a non-integer `token_delta`, and `{"path": null}` are all
    not-checkable — the last because a naive matcher raises `AttributeError` **inside the validator**.
  - **P16's vacuity had a second door** (round 2, F4). Clause (b) also passes under both orderings if
    the fixture's index never moves, so the pin now states that it must move, and points at §5's
    existing loop-back state rather than inventing one.
  - **Pin census: 17 items, 7 pins, 10 guards.** The pin count is **unchanged** from revision 2 — no new
    check flips on pre-fix code — which is itself the finding: round 2's highest-severity issue produces
    a **guard**.
  - **The index measurement has three behaviours, not one** — found by this revision's own re-derivation,
    not by a reviewer. `build_context` reads `<store>/MEMORY.md` through `_measure`, re-reads under the
    **0-token write-truncate guard**, and reads a **third** time for `hook_stats`'s text. A refresh that
    re-implemented the obvious one would write `after_tokens=0` in the very race the guard was added to
    settle. §2.2 now requires the seed's store-local block to be **extracted into one shared helper**
    rather than re-implemented, which is what makes the closure claim literal.
  - **§C7's cost figures re-derived and re-stated with their operand.** The index grew during the cycle
    (1694 → 1889 est tok), moving the store-local median from 0.0020s to **0.0032s** against
    `build_context`'s 0.028s — **~9×**, not the 13× the round-1 draft implied. Both numbers now carry the
    index size they were taken at, since a figure that belongs to a live store cannot be compared across
    store states without it. **This entry is superseded by round 3** (see below): the growth explanation
    is falsified and the pair becomes 0.0017s / 0.0272s ≈ **~16×**. It is left standing, and annotated
    rather than rewritten, because it is the worked example of the very error round 3 names — a timing
    attributed to a cause it was never measured against.
- **2026-09-14 — the C9 split, decided rather than recommended.** §6's round-1 recommendation is now
  binding: `AGENTS.md:19` + `tests/docs_links.py` leave Cycle B for their own cycle, and
  `docs/record-post-state.spec.md` covers the post-state only. **No design element changes** — §6's
  three findings are carried forward verbatim as the rationale. What the decision *adds* is the part a
  recommendation leaves implicit: §4 now warns that `docs_links.py`'s expected zero on this branch is
  the blind gate reporting and not evidence of coverage, and §6 states the condition under which the
  split would turn out to have been wrong. The header's status line moves to revision 3, which the
  previous round's entry had not updated.
  Writing the decision produced one **new measurement**, which is folded into §6 and makes the
  rationale structural rather than merely sequential: **Blind 1 cannot be closed by accepting a bare
  version.** Re-running each live doc's first match under a bare `\d+\.\d+\.\d+` pattern reds **5 of
  6** — and only one of those five is about a version. `CLAUDE.md` picks `1.0.0` (its versioning
  policy's major target), `SKILL.md` picks `127.0.0` (a loopback address), `docs/1.0-preflight.spec.md`
  picks its own `1.0.0`, `AGENTS.md` picks the stale cell, `README.md` agrees, and
  `references/harness-map.md` matches **nothing** — every token there is `v`-prefixed, so a bare
  matcher reports a miss. The round-1 draft had this as "Blind 1 still covers that cell"; the
  measurement says the obvious repair for Blind 1 *creates* five failures, four of which are not
  coverage at all. §4 also gains the release deliverables this branch must carry and the
  CHANGELOG-versus-`plugin.json` sequencing constraint, both previously unstated.
  Re-deriving the §3 census while writing that decision also caught a **label outrunning its set** —
  the failure mode this repo has now hit from both directions: §3's preamble claimed all ten guards
  are "labeled below with the revision they *do* move on", but **three** (P5, P12, P14) named no
  referent at all. P14 compounded it by calling itself "the direct pin for R4" while carrying a
  `GUARD` label, which is a contradiction in terms under the discipline that separates them. All
  three now state their referent, and P14's clause reads "the direct **guard** for R4". The census
  itself re-derives clean: **17 items, 7 pins (P1, P2, P6, P7, P13, P15, P16), 10 guards, 0
  unlabeled**, and the preamble's explicit pin list equals the labeled set exactly. (Two parser
  artifacts on the way there were worth the reminder, and the first was twice corrected: the labels
  are spelled **both** `**PIN.**` and `**PIN**` — 4 and 5 respectively — so a census keyed on either
  spelling alone silently drops the other, which is how the first pass reported 4 pins of 7; and a
  phrase can wrap across a newline. Both times the measurement was wrong before the artifact was. A
  parser that agrees with the document by luck is not a check on it.)
- **2026-09-14 — round 2's findings, folded.** Eight arrived, all in the same family: a number or a
  citation that outran the set it described. Each was re-derived before folding, and two claims did
  not survive that.
  - **The CRLF figures were a measurement of the wrong operand.** Round 2 cited `+10, +9, +11, +11,
    +14, +19` for +1/+2/+5/+10/+20/+40 lines as `auditΔ − measureΔ`. Those are the *absolute* reader
    gap at each size (re-measured exactly: 10/9/11/11/14/19), and the identity compares **deltas** —
    a constant per-file offset cancels in a difference. Re-derived against the real readers on a
    file shaped like the live index, `auditΔ − measureΔ` is **+1 / 0 / +2 / +2 / +5 / +10**. §5 now
    cites the deltas, and the **zero at +2 lines** is stated as the finding: the identity holds by
    rounding while the operands are 9 tokens apart, so a CRLF store's verdict tracks the size of the
    edit. Round 1's earlier "13 vs 14 tokens" toy probe is superseded by this live-index shape (the
    LF control, gap 0 at every size, is what makes "latent, not live" measured rather than assumed).
  - **`budget.index.budget_tokens` is read with four defaults, not three.** `0` in the gauge, `1200`
    in the remediation gate, `1500` in the archive's JS — and **`'?'`** in `_over`, which reads the
    whole budget Mapping `b.get('budget_tokens', '?')`. Verified by calling it:
    `_over({"over": True})` → `⚠ OVER ≈? tok BUDGET`. That one is the sharpest, because it prints a
    placeholder into the banner that means *prune or propose*.
  - **§2.3's cited nested shape named the wrong failure.** Round 1 offered `budget.index =
    "not-a-dict"` as proof that the corruption renders silently. Measured: the validator passes it
    with zero stderr (that part is right, and is now stated as verified), but `render` **raises
    `AttributeError`** at `idx.get(...)` — because `render` binds sub-values with a bare
    `b.get("index", {})` and `_dget` guards **level 1 only**. The silent case is the *dict* shape —
    a `budget.index` holding only some of its leaves renders with zero warnings and zero errors —
    which is the case a partial write actually produces and therefore the stronger citation.
  - **Three Out-list gaps, and one mislabel.** `budget.global_claude_md.*`, `scope.*`, `project`,
    `rigor` and the four seeded budget constants read `ctx` but were in neither the In-set nor the
    Out-list; all four are now named, and the criterion is restated as §2.2's (*a pure function of a
    measurement re-takeable from the store*) rather than round 1's syntactic *reads `ctx`*, which is
    the weaker test that let them hide. **The mislabel is the better catch**: §2.2 filed `demotion`,
    `identity` and `preflight` under "every model-authored block," and `seed_record` writes all
    three **from `ctx`** (`ctx["demotion"]`'s triage counts, `identity_snapshot`, the pre-flight's
    own verdict). They are Out for a stronger reason than authorship — each is a snapshot of the
    pass that just ran, and `preflight` most sharply: refreshing it would overwrite *"the
    environment failed check X while this pass ran"* with the environment *now*, erasing the failure
    the block exists to preserve.
  - **P15's "Pre-fix: two" is fixture-conditional, and the fixture is part of the pin.** The
    row-count flip needs a record with **no `session`**: `assemble_cycles` appends when `_same_dream`
    is False, and with the file's stamp still empty that predicate falls through to its session arm.
    Verified at the predicate — `_same_dream(logged, unstamped-with-session)` → `True`,
    `_same_dream(logged, unstamped-no-session)` → `False`. A session-bearing fixture leaves the
    unhealed path at **one stale row** (C5's content defect, not a count defect) and P15 goes green
    on pre-fix code, i.e. vacuous. §3 now states the precondition and cites the shape as live — but
    as a **dated** census, never a bare count: the archive is the population, and it moved between
    the two rounds (round 2 measured 13 of 55; re-derived here, 10 of 67 across the fleet union and
    4 of 30 in this project's own log). A count over a growing set is part of the triple.
  - **The container-absent splice policy is now stated.** §2.3 raised the `KeyError` hazard to
    justify leaf-wise assignment but never settled what happens when the *container* is missing. A
    record with no `budget` block has no stale after-side to correct, so the refresh **skips it
    silently** — and the two skips must stay apart in the code, because an unconditional subscript
    would raise `KeyError` into the same never-blocks handler and become indistinguishable from
    "the measurement failed."
- **Two claims round 2 made that did not survive re-derivation, recorded so they are not re-filed.**
  - **§2.2's `index_pointers_ok` Out-reason is not false.** The finding held that "a refresh would
    have to invent the computation the seed never did" misdescribes the seed. It does not: the seed
    **hardcodes** `"index_pointers_ok": True, "broken": [], "dangling_links": []`, so there is no
    computation to refresh and the reason is exactly accurate. Not folded.
  - **No phrase was lost in the revision.** A line-based `grep -c` triage reported four of round 2's
    phrases surviving into the current text. Re-run whitespace-normalized, **all ten** survive — the
    apparent losses were prose wrapped across a newline. The triage was wrong, not the text; this is
    the third appearance of that artifact in this cycle, which is why §3's re-derivation section now
    names the normalization rather than assuming it.
- **2026-09-14 — round 3: two findings, both bound to a superseded revision, and the round's real product is the rule.**
  Round 3 reviewed revision 3 at 990 lines while the round-2 fold-in was still running; by the time the
  report landed the file had passed 1200 lines, so both findings are bound to text that no longer
  exists. Both are recorded here with their basis, because "refuted" and "already fixed" are different
  verdicts and only the second is a compliment to the reviewer.
  - **`schema-drift-operand-not-store-local`** — the target, §2.2's *"a directory glob, not a database
    read"*, was **already corrected** in this revision; it now survives only as a quotation of round 1's
    error, immediately followed by *"obtaining that directory is a project-keyed registry read … The
    glob is a directory read; the path is not."* The finding then enumerates four routes out, none of
    which the design takes: §2.2 takes a fifth — recompute `schema_drift`'s six store-local fields,
    **preserve `advisory_stranded_globals` from the seed**. Its sharpest objection (that passing
    `canonical_stems=None` writes a zero where the seed had the true count) is an objection to a route
    the spec explicitly rejects. **The preserve design was then checked on its merits rather than
    waved off**: at the source, `canonical_stems` appears in exactly **one** conditional, guarding
    **one** counter, and measured on the live 38-fact store the other six fields are byte-identical
    across `None`, `set()`, populated-real and populated-nonsense stems. Recomputing six and preserving
    the seventh is therefore coherent by construction, which is the claim §2.2 makes.
  - **`crossing-case-withholds-the-refreshable-leaf`** — this re-derives round 2's finding, already
    folded. Current §2.3 reads *"the refresh warns **and then writes the measurements anyway**"*, and
    the following sentence names the superseded design outright: *"Round 2 caught the earlier version,
    which suppressed the write, and it was wrong for two independent reasons."* That a second reviewer
    re-derived the same defect from the source is worth recording as evidence the fix is legible from
    the code, not merely asserted in the prose — but it is not a live finding.
  - **The round's product is the rule, and it is now in the header.** Two reviewers independently
    produced CONFIRMED major findings against a revision that had already been repaired. Neither report
    was wrong about the code it read; both were wrong about *which* code that was. So the header now
    states that a finding binds to the revision it measured, that this spec cannot state its own digest
    (writing the hash in changes it), and that a revision is identified by round label and line count
    with the digest circulated out of band. This is the pin discipline's own rule turned on the prose:
    the count belongs to the triple, and the finding belongs to the revision.
- **2026-09-14 — the r3-claims round: six findings, all six reproduced, and the largest one was found
  here.** Unlike the round above, every finding in this report was confirmed against the code before it
  was folded — none was taken on testimony, and none turned out to be bound to a dead revision. Five
  are repairs to enumerations and preconditions that had outrun their sets. The sixth is not a repair:
  it is a finding the round **reached and then got wrong on the way to getting it right**, and the
  round's own error is recorded with it, because the error is the same one the cycle is about.
  - **§C3 was wrongly refuted by this round, and re-deriving the refutation is what produced the
    round's best finding.** The sequence matters more than the verdict: a draft of this round declared
    the spec's central evidence **false** — the newest record reads `1746 → 1694`, Δ `−52`, equal to
    its audit, and `1746/1746` "exists in no artifact." Measured again before folding, **every part of
    that was wrong except the archive reading it started from.** The newest record exists in two
    divergent copies: the **log** reads `1746 → 1746` (contradicting its own audit's `−52`, and false —
    the `diffs/` sidecar proves the index moved), while the **`--cycle` file** reads `1746 → 1694`
    (agreeing with the audit). Same marker, same commit, one record, two answers. So the original C3
    was right about the log and the refutation was right about the file, and neither named its
    artifact. The finding that survives is strictly better than both: the divergence is
    **re-derivable as a one-record census delta** — 6 contradicting on the log, 5 on the archive, 31
    checkable either way — and the mechanism is at `assemble_cycles`' file-wins rule, which happens to
    be correct *here* while §2.5's premise assumed staleness ran the other way. **The failure mode is
    this spec's own subject in a new costume**: *"the record reads X"* was under-specified in exactly
    the dimension the cycle is about. The rule is now stated — **a census binds to the artifact it
    read** — and it is the pins discipline's *a finding binds to the revision it measured*, one axis
    over. (Route: a `.jsonl`-excluding search produced the "no artifact" inference, the fourth
    line-based false negative of this cycle.)
  - **The C7 cost pair re-derived a third time, and the correction is upward.** Round 2's growth
    explanation — 1694→1889 tokens moved the median 0.0020s→0.0032s — is **falsified**: both benign
    explanations were tested and refuted (a cold first call measures 0.0025s; `time.time` and
    `time.process_time` agree to 0.0001s), and a *superset* of the named set reaches 0.0020s median /
    0.0033s max. The recorded *minimum* 0.0031s exceeds the named set's measured *maximum* 0.0029s —
    the set could not have produced the figure. Re-measured in five fresh processes: median **0.0017s**
    user CPU against `build_context`'s **0.0272s**, i.e. **~16×**, not ~9×. The rule this installs is
    now stated in §C7 rather than assumed: *a timing whose set is named must be reproducible from that
    set* — which is the operand discipline the cycle already applies to counts, applied to a clock.
  - **§C2's "every offender was created during the pass" was a false universal, with a live
    counterexample.** `quoted-anchor-cannot-be-unique.md` carries mtime `2026-09-12T20:00:00Z`, **1h29m
    before** the pass floor `2026-09-12T21:28:57Z` — present and unchanged at Phase 0, contradicting
    the universal. Re-derived against the true operand (`ctx["fact_files"]`, not `index_fact_names`):
    `index_mismatch` **3 of 4** offend, `advisory_no_scope` **1 of 16**, `missing_node_type` and
    `advisory_no_origin` **0 of 2** each. The live column was already exact, so only the universal
    needed repair — the census beneath it was never wrong. The spec records the wrong-operand error
    explicitly (it yielded a bogus 17/3/3), because it is the failure class the spec is about.
  - **§2.5's mtime parenthetical was false, and the honest form is stronger than a deletion.** The text
    claimed a file-level mtime "does exist one line away in `render_html.main`." Measured: `render_html.py`
    contains no `mtime`, no `getmtime`, and no `.stat(` at all — the remedy would have been written
    against a file that does not exist. The replacement states what is true and useful instead: no
    timestamp exists anywhere on the cycle-record path beyond the authored `marker.timestamp`, **but**
    the plugin has an established freshness idiom (`facts_manifest`'s `mtime_ns`/`body_hash` rows,
    compared by `sync_global` with `st.st_mtime_ns == int(row.get("mtime_ns") or -1)`) — a pattern to
    reuse, not a signal in hand.
  - **The `after_bytes` enumeration was short; the claim it supported was not.** The bullet said the
    only occurrences are the TypedDict, the seed, and "a test fixture." Repo-wide there are **eight**
    files, all writers or transcribers — the two fixture corpora, the `SKILL.md` schema example, the
    vendored canary, and a rendered preview among them. The load-bearing half (**no reader**) survives
    and is now drawn explicitly against its sibling: `render_dashboard` *does* consume `after_lines` in
    `idx.get("after_lines", 0) - idx.get("before_lines", 0)`, so the family is genuinely closed and one
    leaf of it is genuinely dead.
  - **P15's precondition was wrong in three directions at once.** Stated as "only on a fixture whose
    record carries **no `session`**", it is neither necessary (a *different* session pins equally well)
    nor sufficient (a no-session file is one of four pinning shapes), and it omits the logged record's
    own session as the second operand. Re-derived on the live predicate across all five shapes, the
    vacuous case is exactly one: **file session == logged session**. This is the
    `dropped-hedge-becomes-false-universal` failure in miniature — a repair that found one vacuous
    shape and promoted it to "only" — and §3 now states the sufficient condition instead.
  - **§3's pin census: 17 items, 7 pins, 10 guards — unchanged.** Five of this round's six findings
    repaired prose or enumerations rather than checks, and the sixth (§C3) strengthened an argument
    without adding a check. No new check flips on pre-fix code, so the count does not move — and
    neither does the contradicting-record census, which re-derives at **six on the log and five on the
    archive** (§C3). Both are measurements, not pins; the earlier draft of this entry wrongly reported
    the census as moving six → five, which was the refutation's error propagating into the ledger.
- **2026-09-14 — the mechanism lane's report against revision 3, re-checked against revision 5: five
  findings, all five confirmed.** The report was bound to sha `185e170b` (1224 lines) while this file
  had moved to revision 5 (1514) — exactly the condition the header's rule exists for — so nothing was
  accepted or dismissed on the binding. Each cited passage was located in the current text and checked
  at the source: **all five survive verbatim**, meaning the intervening folds changed the surrounding
  prose but not one word of what the findings attack. Every one is a *reason* that outran its operand,
  and four sit in text this round added — the useful signal being that the round's new closure
  arguments were the least-tested surface in the file.
  - **The Out-list's "every model-authored block" umbrella is false for three of its ten members.**
    `audit` is injected by `--audit-into` (*"deterministically inject the audit block INTO the cycle
    record (no model merge)"*), `usage` by `extract_signals.inject_usage` (*"the whole block is
    script-produced"*), `distill` by `distill_scan`. The **set** was right — the refresh must not
    overwrite what the pass did — but the label was not, and this is the **second** time this specific
    umbrella misdescribed its own members (round 2 caught it for `demotion`/`identity`/`preflight`).
    The bullet now gives the reason that survives the source, which is the same one those three got.
  - **The `slug_orphans` Out-reason named the wrong level.** The projects root is the store's
    **grandparent** — measured, `store.parent.parent == config_root()/"projects"` — and the real
    unavailability is the *slug identity*, not the distance. Naming a distance invites a reader to look
    one directory up, find a slug dir, and conclude the reason was proximity: the same misreading that
    made the round-1 `schema_drift` parenthetical wrong, which is why the bullet now names the missing
    operand instead of a level.
  - **The container-absent skip was keyed on `budget` while the row is gated on `budget.index`.** The
    renderer gates the gauge row on `if idx:` and its `(unchanged)` fallback on
    `if not (cm or idx or rf or gcm.get("present"))`, so a record with `budget.claude_md` but no
    `budget.index` — type-legal, `Budget` being `total=False`, and `--persist` taking arbitrary JSON —
    would get that block authored and a row newly drawn: the outcome the policy's own rationale
    forbids. Across 247 stores / 92 unique records the shape does **not** occur (one record has no
    `budget` at all, none has `budget` without `index`), so this is a precision repair, not a live
    defect. The fix is the leaf-wise rule §2.2 already states for assignment, applied to the skip.
  - **Condition 1 compared a fresh measurement against the record's possibly-retired budget.** 14 of
    this store's 55 records carry the retired `1200` (41 carry the live `1500`), and **13 of the 14
    carry no `remediation` block**, so the condition is reachable on them; §2.2 defines the `over` leaf
    against the live `INDEX_TOKEN_BUDGET`, so the refresh could warn over-budget while writing
    `over: False` on the same line. Both conditions are now keyed to the constants the refresh is
    about to write, making the warning and the leaf the same comparison by construction. Condition 2
    does not carry the defect today (`ceiling_tokens` is uniformly `3840` across every record holding
    it) but is keyed the same way so a re-basing cannot reopen it. One number here is the peer's and is
    a **fleet** census, not mine — 21 of 92 stale-`1200` without `remediation`, 18 in the
    `(1200, 1500]` band — cited as such, because that band is empty in this store and only the fleet
    census shows the disagreement is *reachable* rather than merely constructible.
  - **§2.6 and §5 disagreed about the hierarchy residual.** §2.6 said the rewritten instruction "keeps
    a model duty" over `claude_md` **and** `claude_md_hierarchy`; §5 scoped the instruction to "the
    `claude_md` half" and called the hierarchy unrepaired. §5 is right: `claude_md_hierarchy` has no
    `after` key, and its only `SKILL.md` occurrence is the schema example. Worse than a contradiction,
    §5 **deferred** to §2.6 (*"now with §2.6's correction saying so explicitly"*) while §2.6 said the
    opposite. The residual is `budget.claude_md` alone — and naming the hierarchy would have asked the
    model to maintain a value it cannot measure, the authored-state failure §2.3 forbids.
  - **The lane's non-findings are recorded too**, two of them being measurements this spec now leans
    on. It could **not** refute P15's session precondition (reproduced at the predicate; its
    independent census 19 of 92 session-less records against this spec's 10 of 67 — different
    populations, same direction), nor §2.2's six-preserve-one split, nor §2.3's warn-and-write. It
    confirmed §5's CRLF mechanism at source in `_add`/`_measure` and — the useful half — replaced
    *assumed* latent with *measured* latent: across the fleet, 21 stores hold a `MEMORY.md` and **0
    contain a `\r` byte**, so no live store exercises the ceiling. And it declined to file a claim it
    could not substantiate (*"the ceiling condition can fire only where the banner is present"* is
    false as a universal), recording it as unsubstantiated rather than as a finding — the same
    discipline this file applies to its own drafts.
  - **Pin census unchanged: 17 items, 7 pins, 10 guards.** Five confirmed findings, five repairs to
    stated reasons and operand choices, no new check that flips on pre-fix code.
- **2026-09-14 — round 4: three lanes on disjoint surfaces, 15 confirmed / 4 refuted, and the round's real
  product is one rule and six defects no lane was looking for.** Round 4 changed the review process before
  it changed the file: the three lanes were scoped to **surfaces** — internal consistency, the mechanism
  round's own repairs, and §C3's central evidence — rather than to the same file read three times. That was
  a correction, not a convenience: rounds 2 and 3 both re-reported items the other had already reversed, and
  a lane given a surface finds the rest of the file only by luck. All three bound the same subject —
  revision 6, at the 1657-line digest circulated with the request — so for the first time this cycle a round
  had **one** verified subject instead of three approximations of one.
  - **`r4-sweep` — 8 confirmed, every one a contradiction between two places in this file.** **P2's 9**
    becomes **8** (eight `token_history` entries; the harness passes `record=history[-1]`, so `_same_dream`
    dedups the record against itself). **§C2's `health`** is not a third direct `ctx` copy: the seed builds it
    from **one** `ctx` copy (`schema_drift`), **three** hard-coded constants (`index_pointers_ok`, `broken`,
    `dangling_links`) and one projection (`slug_orphans`). **§C4's `≈0/4000`** describes a shape the seed
    never writes (`after_tokens` absent or zero beside a present `budget_tokens`) — measured **0 of 55** for
    both tiers — and the record in hand carries its own before value, `≈3986/4000`. **The round-3 ledger
    title** said "both refuted" where the entry's own body says *"'refuted' and 'already fixed' are different
    verdicts"* and revision 4's header says *"both were already fixed"*. **§2.3's ceiling universal** is
    scoped to the stores this census covers; the reachable gap it names (condition 2 compares a fresh
    persist-time read while the banner was decided at Phase 0 from `ctx["index_lb"][2]`) is §C7's own
    subject, and **no such state was produced** — recorded as *scoped*, not refuted. **§5's `_over`** takes
    the **tier** Mapping (`_over(cm)` / `_over(idx)`); `budget` carries no `budget_tokens` key at all, so the
    old reading would make `≈?` **universal**. **§5's "eight files"** is **seven** at `fa91254` — the eighth
    file exists only in the post-change tree, this cycle's own `"after_bytes": il[1]`. **§C1's "token pair"**
    named a partition the record set does not have: 29 of 55 unequal on the three-leaf pair, **28/27** on the
    token pair alone, the difference one record at `bytes 3110 → 3107` with `tok 758 → 758`.
  - **Its refuted list is as much a product as its findings.** The pin census **17 items / 7 pins / 10
    guards** is exact; §5's "8 of the 10 standing-justified" is exact (`remediation.standing_justified is
    True`); every §2.3 census reproduces to the digit (`{1200: 14, 1500: 41}`, 13 of the 14 stale-`1200`
    records without a `remediation` block, **20 of 55** without `ceiling_tokens`, `ceiling_tokens` uniformly
    `3840`); §C3's partition and all four fleet censuses are exact. Four further claims were reported
    **unsubstantiated** rather than filed — §2.3's ceiling universal as *false* (reported as the
    contradiction it is, never as falsity), §C2's schema-drift table, §5's `≈16×` ratio, and the CRLF census
    — the same discipline this file applies to its own drafts.
  - **`r4-repairs` — 3 confirmed, 2 refuted.** Confirmed: the `inject_usage` docstring was truncated
    **without a mark**, eliding the clause that classifies `distill` — and the set it hedged is **five**
    script-assigned blocks (`audit`, `usage`, `workflow_proposals`, `narration`, `distill`), with `distill`
    **split-ownership** rather than whole (`distill_scan.inject_into` is a sub-key merge that overwrites the
    counts and preserves model-authored `proposed`/`created`/`verdict`); §2.2's `slug_orphans` "grandparent"
    was a false universal, true of the default native layout alone — under `CM_STORE_OVERRIDE` the store,
    `store.parent.parent` and `config_root()/"projects"` are **three different directories, none of them the
    store's grandparent**; and §2.3's band, where **every one of the 18** carries `budget_tokens == 1500`,
    its own threshold, so they cannot disagree — the genuine disagreement set (record threshold `1200`
    *and* `after_tokens` in `(1200, 1500]`) is **0 of 92** and **0 of 55**, and across all 29 stale-`1200`
    fleet records `after_tokens` is ≤1191 or ≥2761. Refuted: the container-absent skip, which
    `tests/dashboard_browser.py` pins **not** to fire (visible `#network-blk .budget-grid` count `0`, the
    `#m-index` writes landing in permanently-`hidden` DOM — so the archive is evidence *for* the repair);
    and §2.6's residual, exact in both halves. The lane also declined to file the "247 stores" denominator
    as unsubstantiated.
  - **`r4-rev5` — the central evidence confirmed and demonstrated, and it is the cycle's strongest single
    result.** Log `1746 → 1746` against file `1746 → 1694`; `audit.operations[0].token_delta` `-52`; the
    `diffs/` sidecar hunk header `@@ -2,11 +2,9 @@`; the flattened diff differing in exactly **7** keys
    (four budget leaves, `cliff_pct 28→27`, `recall_facts.after 31→33`, `_outcome`). The mechanism was
    **demonstrated, not argued**: `_same_dream → True`, `assemble_cycles → 55`, and the census moving 6 → 5
    with the record folded. The census itself: log union **31 / 25 / 6**, archive **31 / 26 / 5**, the six
    contradicting markers `08-29T23:33`, `08-31T03:10`, `09-04T02:11`, `09-04T17:34`, `09-05T19:51`,
    `09-14T00:36`. The partition: **31 / 14 / 10 = 55**, all 14 row-less records with delta `{0}`. Refuted: a
    sub-finding about the WARN's input — and here **two** sentences are in play, which is why this row
    states the measurement rather than a bare verdict. §2.4's *"validates the record being rendered and
    never an archived one"* **stands**: `render_dashboard.main` takes the record from `paths[0]` /
    `sys.stdin` and feeds *that* to `validate_cycle_record`, so the WARN is reader-independent of both
    artifacts. The earlier revision's gloss on the same subject — *"runs against the record as loaded —
    which is the log's copy"* — does **not** stand, and §C3 records it as false. The round-4 verdict was
    taken against §2.4's sentence, so a reader who takes "the sentence" for the gloss would read this row
    as refuting a finding §C3 confirms; they are different sentences, and only one of them is a claim
    about the WARN's input. Refuted also: §5's "historical six", where the count is artifact-bound but
    **the WARN is reader-independent of both artifacts**.
  - **V-3 — a figure that does not name its artifact is not a measurement.** The r3-claims round bound this
    rule to *censuses*; this round found **three figures** still reading the log union and the archive as one
    number, so the rule now binds the figures **inside** a named census too. §2.2's `recall_facts` margin is
    **21** on the log union and **20** on the archive — the same 31 rows, one rf leaf away, with the
    `claude_md` margin **28** and the `cm-MOVED + rf-MOVED` row **0** invariant across both readings, the
    cross-tab moving `10 → 11` and `18 → 17`. §C3's zero census is **7** on the log union at positions
    `17/12/7/6/4/3/0` and **6** on the archive, position `0` dropping. Both are named in place now; the
    ledger rows carry the artifact in the claim column and the counterpart reading in the basis column.
  - **Four defects found here rather than by a lane — including one this round wrote.** P15's precondition
    was **inverted**: the shape it named as the precondition (the file-side record carrying the logged
    record's session) is the table's single **vacuous** row, and both earlier revisions had it backwards —
    round 2's "no `session`" is neither necessary nor sufficient, and revision 6's "session **equal** to the
    logged record's" is the one shape that makes every row read `True / 1`. It was found by disbelieving the
    table and then proving it: my first probe called `len()` on `assemble_cycles`, which returns
    `(cycles, total)` — a 2-tuple — so every shape printed `rows=2` and appeared to refute the table.
    Unpacked, **all five shapes reproduce the table exactly**: the table was right and the probe was wrong,
    which is the census rule one level down. §2.3 carried a paragraph describing the `ceiling_tokens`
    **default** for a line of code this revision no longer has — the record's `ceiling_tokens` is never read,
    so the 20 records lacking it need no default, and the paragraph is removed because it described code
    that is not there. §2.3 said the nine leaves live in "four mappings" where the seed writes **three**
    (`budget.index`, `budget.recall_facts`, `health.schema_drift`). And one of this round's **own** edits put
    a real home path into a public-repo file — caught by an audit of my own text, and repaired by reading the
    file's bytes rather than my paraphrase of them (the first repair failed on exactly that: an `old_string`
    written from what I had just typed, not from the file), after which a `grep` for any absolute home path
    in this file reads **0** — written without the literal, so the audit and the rule do not contradict each
    other in the same sentence.
  - **Pin census unchanged: 17 items, 7 pins, 10 guards.** Fifteen confirmed findings and five self-found
    defects, and not one of the twenty adds a check that flips on pre-fix code — every repair is to a
    stated reason, a figure's artifact, a precondition's shape, or a patch point that did not exist.
    §3's list is unchanged, which is this
    round's own claim to have been a fold and not a redesign.
    **The fifth arrived after the round closed, from writing the check rather than reading the file** —
    and that is the round's cleanest evidence for its own thesis: three lanes read §3's P9 sentence and
    all three passed it, because a sentence that *sounds* like a mechanism reads as one until something
    has to execute it.

- **2026-09-14 — revision 10, after the round-3 review (six findings, all six confirmed).** Every
  finding was verified **at the source before any edit**, not accepted on the review's word, and the
  verifications are the entry's substance because three of them changed the finding:
  - **F1 — `remediation.over_ceiling` was frozen at seed time.** Confirmed: `memory_status.py` writes
    it once, at the seed, from its Phase-0 read. The review's severity claim was a *conjunction* —
    `over_ceiling: true` **with** `ceiling_tokens` absent, rendering `⚠ HARD CEILING ≈0t` — and
    measured over the 55 records that conjunction is **0 of 55**, so the specific render is
    **constructible, not live**. Filed at the reduced severity with the reduction recorded, and
    repaired anyway on the merits: an alarm whose operand moved is a defect whether or not the
    archive happens to hold one today.
  - **F2 — the over-budget guard read `budget.remediation`.** Confirmed at the source, and this is
    the round's cleanest **dead guard**: `remediation` is a TOP-LEVEL `CycleRecord` key, and `budget`
    carries exactly `claude_md`, `global_claude_md`, `index`, `recall_facts`, `claude_md_hierarchy`,
    so no writer in the codebase produces the key the guard read. It warned on every over-target
    persist — including the standing-justified store, which is the designed steady state — and its
    message told the operator the record "carries no remediation block" while one sat in the record.
    Note the shape: this is **V-3's rule one level down**. A figure that does not name its artifact
    is not a measurement; a **guard that does not name its container** is not a guard.
  - **F3 — `over` re-keyed to the live constant while `budget_tokens` stayed a snapshot.** Confirmed,
    and the confirmation settled a question this spec had left open: no environment variable,
    settings key or config path overrides `INDEX_TOKEN_BUDGET` anywhere in the tree (`grep` over the
    four consumers), so a record's `budget_tokens` **can only be** a snapshot of a module constant at
    seed time. Measured, it has been two values: **`1200` on 14 of 55 records, `1500` on 41**. The
    repair closes the comparison rather than the leaf: both constants are now written in the same
    splice, so the warning and the gauge read one comparison by construction.
  - **F4 — `schema_drift`'s preservation branch fabricated `advisory_stranded_globals: 0`.** Confirmed:
    the branch preserved the seed's value *when the seed had the key*, and the refresh's
    `canonical_stems=None` path makes the seventh field **structurally zero** — so a legacy-shaped
    block got a `0` nothing measured. Repaired to preserve-or-**drop**, never author. This is
    LEAF-WISE's own rule one level down, which the spec had stated for containers and not applied to
    a leaf.
  - **F5 — the ONE-SPLICE docstring's claim that "`validate_cycle_record` never descends into
    `budget`" is falsified by this diff.** Confirmed, and it is **this spec's own defect**: §2.4's
    reconcile invariant reads `budget.index`'s `before_tokens`/`after_tokens`, so the validator
    descends into `budget` for exactly two leaves. The claim was load-bearing — it is why ONE SPLICE
    has to be atomic — so it is repaired by **narrowing it to the truth** (the validator descends for
    two leaves and not for the rest) rather than by deleting it; the paragraph now names the eight
    remaining index leaves by name, because the mixed-generation record it forbids is one the
    validator cannot see.
  - **F6 — the precondition rebuilt `store / "MEMORY.md"` instead of reading `store_local_index`'s own
    `index_path`.** Confirmed, and it is the repo's **weakest-enforcement-site** rule broken at the
    exact site whose docstring invokes it: two expressions of one fact, where a future index rename
    updates the measurement and leaves the guard behind, so the guard passes on one file while
    `_measure` reads another — writing `after_tokens: 0` beside a true `before_*`, which is the
    fabrication the precondition exists to prevent.
  - **`remediation.over_ceiling` reclassified: In, not Out — contradicting revision 9's stated
    design.** Three source citations, all agreeing: the assignment is `index_lb[2] >
    INDEX_CEILING_TOKENS` (a pure comparison of the refresh's own read); the constant is documented
    as structurally standing-justify-INDEPENDENT (*"the comparison never reads `standing_justify` —
    there is nothing to suppress and no justify escape"*); and its own comment calls it *"a SECOND,
    INDEPENDENT signal … never a re-key of it."* A **verdict** reads record state — `required` reads
    `standing_justify`, `baseline_facts`, fact-count growth — and those stay unwritten. So the split
    the Out-list states is now **per leaf, by what the computation reads**, with `maintenance.*` and
    the rest of `remediation` still Out entire. This is a **design change**, not a repair: revision
    9 said the refresh "must not invent the triage verdict — `remediation.required` and the
    `over_ceiling` flag keyed to it — and it still does not write those."
  - **§2.3's `ceiling_tokens` paragraph was false against the revision it described.** It claimed the
    record's `ceiling_tokens` "is never read". The reader is the alarm itself —
    `idx.get('ceiling_tokens', 0)` in `render_dashboard`'s tail — and that `.get(…, 0)` is the very
    default the paragraph argued about. Confirmed by grepping the symbol repo-wide: the only other
    mentions are the `IndexBudget` declaration, the seed, and the ladder spec. The paragraph is
    rewritten to state the reader, keep the census (**20 of 55** records lack the leaf; the 35 that
    hold it are uniformly `3840`), and record that this revision's repair is to **write** the leaf
    rather than to delete the read the earlier revision deleted. A claim about a reader is checkable
    by grepping the reader; this one was not grepped.
  - **Two defects in round 3's own checks, both found by running them rather than by reading them.**
    **(a)** P19's fixture never cleared the warning's first operand: the check's own message printed
    `1152 > 1500`, so the arm it was written to exercise never fired. Repaired to a 200-line index
    (measured 3422 est tok) with the precondition asserted *in the check itself* — the
    assert-the-fixture's-precondition habit earning its keep. **(b)** P19 in its original form
    asserted a warning **count**, and **passed on revision 9** — because a revision reading the
    operand off the wrong block also fires exactly one warning, from the wrong arm. Repaired by
    splitting into one stderr capture per arm with distinct assertions. This is the norm this repo
    already records — **a count says how many moved; a probe says which** — inverted by an item in
    this very file, which is the second time a round's own instrument has been the thing that was
    wrong.
  - **Pin census: 17 items / 7 pins / 10 guards → 22 items / 10 pins / 12 guards.** The five new
    items are red on pre-fix HEAD **and** red on revision 9, each for its own reason; the RED-on-9
    measurement (1937 passed, 5 failed) was taken **before** the repairs landed, so it is a
    measurement rather than a reconstruction. **P19 and P22 name revision 9 as a measured referent —
    the first guards in this spec whose referent is a real revision rather than a hypothetical one**,
    which is the strongest label available and one that only exists because the implementation was
    itself reviewed.
  - **The class, named once.** Every item from P1 to P17 tests a leaf's own movement: a **dyadic**
    property. Four of the six findings exist only in a **triadic** relation — between two leaves
    (`over` and its denominator), between a leaf and its reader (`over_ceiling` and the gauge line),
    or between a leaf and the claim that it was measured (`advisory_stranded_globals`). The gap is in
    the **shape** of a per-leaf pin, not in how these were written, and the five new items are
    therefore stated as relations. The round's own thesis, one level up: this file's review rounds
    have repeatedly found that a claim outruns its operand; round 3 found that a **closure argument**
    can outrun its own closure, because it was stated per leaf over a set whose members are not all
    leaves.

- **2026-09-14 — revision 11, the branch's own claims (nine, and the sweep is the method).** No
  reviewer filed this round. It is a pass over **what this cycle said about its own code**, because
  that is the one surface with no gate on it: a comment, a skill instruction and a check's *name* are
  all never executed, so only following each one to its source can falsify it. Six of the nine were
  repaired before this entry was written. **A6 was recorded and repaired in one revision; A7–A9 were
  found by holding *this entry* to the method it describes** — the one shape a self-audit's ledger
  cannot avoid, arriving three more times.
  Findings are labeled **A1–A9, not F1–F9**: the F-series belongs to the round-3 review entry above,
  and two live `F5`s in one file is the same ambiguity this revision exists to remove — a rule this
  entry's own prose broke, which is **A8**.
  - **The sweep's shape — four questions, the last two learned here.** Every added claim that names a
    **count, an enumeration, or a "never / only / single / ONE"**; every check asked *what would this
    print if its claim were false?* (A5's origin); every measurement offered as **evidence for a
    repair** asked whether it *distinguishes* the repaired tree from the unrepaired one (A7's origin —
    the question the first three could not reach, because the sentence was true of the tree it was
    written on); and finally **the entry read as a text surface in its own right**, since a ledger that
    names findings is the one document whose referents nothing else sweeps (A8, A9).
  - **A1 — the archive "never had this defect".** Falsified by reading
    `dashboard.template.html`'s gauge: it takes **both** operands from the record
    (`budget.index.after_tokens` against `budget.index.budget_tokens`), its constant only as the
    fallback. The repair is the reason, not the code, and the corrected reason is the sharper one:
    the pair is contemporaneous because the splice writes both together.
  - **A2 — two `render_html` constants that were unpinned literal copies** of `memory_status`'s, in a
    module that already imported `ms`. Not a prose defect but a claim nothing held: the comment said
    "mirrors `memory_status`", which is true as an intention and enforced by nothing. Repaired by
    making both a live reference, as `INDEX_CEILING_TOKENS` has been since v0.1.66 for this exact
    reason. **The probe found a drift, not an error** — with `ms.INDEX_TOKEN_BUDGET` rebound to `1600`
    *before* `render_html` is imported, `render_html` still read `1500` — and the drift is invisible
    in any output on the current tree, because the copies agreed on the day they were written. The
    timing is the whole discrimination, which is **A7**.
  - **A3 — "all three readers"** where `grep -rn over_ceiling` finds six, in three files, one of them
    (`dashboard.sections.js`) an enumeration that never reached it.
  - **A4 — SKILL.md's "the ONE budget leaf the script does not own."** False twice over
    (`budget.global_claude_md.*` and `budget.claude_md_hierarchy` are equally out of reach) and false
    in the direction that acts: its reader is the **model**, one step from authoring the value §2.3
    forbids. The only one of the nine whose reader is an actor rather than a reader, which is what
    makes a false count *actionable* rather than merely imprecise.
  - **A5 — a check whose label asserted one property while its condition tested another.** The v0.1.66
    check named "*a live reference, not a hardcoded copy*" and tested `==`. Found by asking each check
    the question above; for this one the answer was ✓, which is the whole finding. **Repaired as two
    checks, not one stronger one**, because the two properties live in different domains: the value
    (equality — a copy passes) and the source's shape (an AST read of what the name is bound to).
  - **A6 — this file's own count.** §5 recorded `over_ceiling` as having "exactly two readers (the
    alarm line and `render_html`'s gauge)". The census is **six sites in three files** — and the
    claim was load-bearing: it was offered as the reason the repair "cannot invent a display", where
    one unexamined reader is exactly what would let it. **All six test truthiness**, so falsy is
    render-identical to absent, which is the conclusion the paragraph needed and could not get from a
    count of two.
  - **A7 — this list's own evidence for A2, which does not re-derive.** It reports the probe as
    `rebinding ms.INDEX_TOKEN_BUDGET = 1600 left render_html at 1500` — the mutation without its
    **timing**, which is the entire discrimination. Measured, one process per cell: rebinding *before*
    the import reads **`1600`** on the repaired tree (the reference tracks its source) and **`1500`**
    on the pre-fix tree; rebinding *after* reads **`1500` on both**. So the sentence, re-run by the next
    reader on the repaired tree, prints the pre-fix number and reads as evidence that the repair is
    inert. The source comment beside the repaired lines already carried the distinction — *"a retune is
    pinned at the source (edit + re-import), never by monkeypatching this module's `ms`"* — and the
    bullet now does too. **A pin is only a pin if it fails on pre-fix code; evidence is only evidence
    if the two trees read differently**, and a probe that prints one number either way has a
    measurement's shape and a prior's content. It is why this bullet states the *cell* and not just
    the number.
  - **A8 — the rename reached the bullets and not the prose.** The findings were renamed F→A *because*
    "two live `F5`s in one file" is an ambiguity — and, four lines below that sentence, `F5` still
    named the check-label finding in the mutation bullet while `F1`–`F4`/`F2`/`F6` went on naming the
    rest in the chronology bullet. So the collision the rename removed from the headers survived in the
    entry documenting the removal. `grep -n '\bF[1-6]\b'` was the census: **every `F`-reference still
    naming a finding was stale**, and the only survivors were the two that talk *about* the rename.
    A rule applied to a list and not to the sentences citing the list removes the label and keeps the
    ambiguity — which is the defect A5 found one level down, in a check's name.
  - **A9 — ordinals, pointing at the wrong thing in three places.** The sweep's-shape bullet called the
    check-label question "the sixth's origin" — that is **A5**. The block introducing this revision used
    "the sixth" for **two different findings ten lines apart**: "The sixth is not text" named **A2**,
    "The sixth is this file's" named **A6**. And the control bullet below lets "the other four numbers"
    mean anything, when no set of four is enumerated anywhere near it. An ordinal is a pointer that
    re-points itself the moment the list it counts grows, and this list grew from the first pass's four
    to nine while the entry was being written. It is why the findings above carry ids — and the pattern
    in the three that rotted is that **each points at a list that is not on the page**: the ordinals
    that survive ("the first three" questions, "the second ✗") are the ones whose list is enumerated
    beside them.
  - **The one that held is the entry's control.** `ceiling_tokens` reads at **exactly one** site, the
    `⚠ HARD CEILING` alarm, checked in the same pass that falsified its neighbour. A method that
    lowers every number it meets is not a census; the pair is what makes the others measurements
    rather than recollections.
  - **Pin census: 22 items / 10 pins / 12 guards → 23 items / 11 pins / 12 guards**; the smoke
    constant `1772 + 45 + 125` → `1773 + 45 + 125`. P23's predicate is **source-level by necessity**:
    the property it asserts — this name is bound from `ms` — is invisible to any comparison of values,
    which is the defect that created it. The equality half is not a new item; it replaces and widens
    the v0.1.66 check it succeeds, which is why a revision adding one pin moves the census by exactly
    one.
  - **Mutation, recorded as the pair it is.** On a tree carrying the literals again: the equality half
    prints **✓** and P23 prints **✗** — `1941 passed, 2 failed`, the second ✗ being the census
    constant, which is how a suite fails when its surface moves and its census is still correct. The ✓
    is the finding rather than a surprise: it is **A5** reproduced in one line of output.
  - **Chronology, because it is the honest part.** A1–A4 came from the first pass; A5 arrived while
    auditing A2's repair, and A6 while writing this entry. A7–A9 arrived only afterwards, from running
    **the entry's own** claims through the sweep it had just run over everyone else's — so the title
    counts nine rather than the first pass's four, because the sweep was never one pass: it was the
    same question asked until the answers stopped arriving, **including the question asked of the entry
    that had just finished asking it.**
