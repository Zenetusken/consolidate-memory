# Record duty presence — design-of-record

**Status: implemented (revision 9) — shipped as v0.4.33.** Target release: **v0.4.33 (patch)** — an
added terminal-gate clause and a new panel; no schema, flag, or install-contract change. Revisions
4–9 were the adversarial passes and the `/code-review` round; the amend ledger at the foot records
what forced each.

This spec closes the OPEN 4b class: **a cycle record's seeded duties were never checked for being
filled.** It is the first of two staged cycles. Cycle E carries the renderer/declaration fixes
(its own spec, `docs/render-declaration-parity.spec.md`, is authored with that cycle; until then
the plan's scope for it is the design-of-record), including the two defects this cycle records but
does not schedule (§6).

Every number below was derived on branch `fix/record-duty-presence` at `2b07ce3`, the head of
`main` when the branch was cut — **except the population census (§3.1), which reads archived
session logs and so measures a FLEET, not a checkout.** A fleet is neither re-derivable from a
clone nor frozen, and during revision 3 (2026-09-17) that stopped being a caveat and became a
measurement: the census script, run twice hours apart on the same machine, returned **99** records
and then **100**, with two clause counts moving beside it. The difference was a single row written
by **this cycle's own test suite** — an instrument that contaminated itself while measuring — and
it exposed that the population's `ops/*` glob had always admitted a class of six test-scratch
directories, of which the single synthetic row the plan hand-excluded was one member. §3.1 states
the class, prints both columns, and keeps the drift as the evidence for why a prevalence number is
testimony. Every such number in this document is **testimony about a fleet at a timestamp**, and is
labelled that way where it appears.

---

## 1. The defect

A real `dream` pass persisted a cycle record carrying **four unmet duties, every one of which
rendered as silence**:

| Duty | What the record held | Why nothing caught it |
| --- | --- | --- |
| `session` | `""` | the renderer's `_clean(record.get("session", "?"))` defaults on **absent**, never on empty |
| `entries[1].action` | `"added"` | contradicted the row's own reason — no clause compared the two |
| `rigor.applied` | `""` | the field the magnitude→applied calibration exists to collect |
| `remediation.achieved_recall` | absent | absent **beside a present** `achieved_index` |

The four were found by audit rounds, hand-repaired, then healed into the archive.

The sharpest statement of the mechanism came from the contract auditor, and it is the thing this
cycle is built on: **`validate_cycle_record`'s cross-block clauses are all of the form *"two values
that both exist must agree"*.** A clause of that shape is **vacuously satisfied** when one operand
is missing — so an unfilled duty is not merely uncaught, it is uncaught **by construction**. No
amount of adding clauses in that shape closes the class.

The same shape recurs one level up. `procedure_integrity` fires iff
`tier >= SUBSTANTIAL` **and** `tally <= 0`; `arc_completeness` fires iff a *present* `dream` block
is incomplete. Both are correct and both abstain on absence — which is right for their rules, and
which is exactly why neither could see this record. The gap is not a missing check; it is a missing
*shape of check*.

**The rule this cycle adds to the module:** value-contradiction clauses and presence clauses are
different families and belong in different predicates (§2.1).

---

## 2. Design

### 2.1 The host, chosen by consumer census

The first draft of this design put the presence clauses **inside `procedure_integrity`**, on the
strength of its `(ok, reason, severity)` shape and its own legacy short-circuit. An adversarial
pass overturned it, and the reason is worth recording as a method:

> `render_html.py`'s `_embed_integrity` calls `ms.procedure_integrity` **for every archived cycle**
> and stamps a `_integrity` key into the embedded payload when it is not ok. That key is read by
> **three** consumers across two files: `dashboard.template.html`'s archive-list row, whose ⚠ badge
> carries the literal tooltip *"procedure integrity: verification skipped on a substantial-or-
> heavier pass"*; and `dashboard.sections.js`'s assessment row and its `<p class="adverse">` block,
> each of which prints the predicate's own `reason` string.

*(Revision 3 correction: this paragraph previously attributed the tooltip to the `.adverse` block.
It is the archive-list badge's — `sections.js`'s two consumers interpolate `_integrity.reason` and
carry no tooltip of their own. The correction sharpens the argument rather than softening it: the
archive-wide consumption is **three surfaces in two files**, and the run-time literal lives in a
file none of the predicate's own callers appear in — which is exactly the fact a consumer census
run over `grep -rn "procedure_integrity" plugins/ tests/` would have missed.)*

Narrowing that predicate in place would retro-flag **every archived record with an empty
`session`** under a tooltip naming a different cause. The repo had already learned this exact rule
and written it down — `arc_completeness`'s docstring says *"narrowing in place would retroactively
flip an ARCHIVED record's display … Only the persist gate passes True"* — and the first draft
quoted that sentence in one paragraph and violated it in the next.

**The check that catches this is a consumer census before a host is chosen**, and it is cheap:
`grep -rn "<predicate>" plugins/ tests/`. Nothing in the predicate's own body distinguishes a
persist-only predicate from an archive-wide one.

So the clauses get their own host:

```
memory_status.duty_gaps(record: object) -> list[DutyClause]
```

- **Pure**, never raises, **empty by default** — the `procedure_integrity` posture.
- Consumed by `render_dashboard` in exactly **two** places, both under the existing `judged` gate
  (the `persist_dir is not None` predicate that already separates a live terminal render from a
  seed/preview): the exit ladder (§2.3) and the panel (§2.4).
- `validate_cycle_record` is **not touched**. Its documented posture — *"deliberately QUIET on a
  missing key"* — stays true, every silence pin stays green, and the fixture's `validate_sample`
  assert (which gates `docs_links.py`, `dashboard_browser.py`, and regenerating the committed
  `docs/previews/`) is unaffected.
- `procedure_integrity` is **not touched**. No archived cycle gains a `_integrity` flag.

**The three families, stated once so the next reader does not re-make this cycle's error:**

| Family | Test | Lives in | Callers |
| --- | --- | --- | --- |
| container type | is a present key the right *shape*? | `validate_cycle_record` | stderr everywhere |
| **value wrong** — *disagree* · *membership* · *absent/dup* | is a present value *right*? — do two agree · is it one of a known set · is a required one missing or repeated | `validate_cycle_record` + `procedure_integrity` | stderr; the persist gate |
| **presence** | did the pass fill the field it seeded? | `duty_gaps` | **the persist gate only** |

Family 2 is named in full, not as *"value contradiction"*, for the reason §2.5 measures: the loose
name reads as the whole while excluding two of its three kinds, and it is the name under which
membership and identity rows have twice gone uncounted.

### 2.2 The clauses

Each clause is a row in a module-level table — data, not a chain of `if`s — so the renderer can
render each row's **own** words rather than a shared literal. The row type is a `NamedTuple`,
`DutyClause`, with **six** fields: `name` (the stable key, for pins), `label` (the field name the
panel prints), `detail` (what is wrong, **in this row's own words**), `remedy` (what the pass must
do about it), `severity` (`alert` ⇒ routes exit 3; `warn` ⇒ reported only), and `fires` (the
predicate).

`detail` is a field rather than a constant because the three clauses share a *shape* but not a
*cause* — an unfilled id, an unrecorded tier, a half-measured trio. One sentence describing all
three would reproduce this cycle's headline defect one layer up: **a fixed label standing where
derived data belongs.**

**The era gate is "the key is PRESENT and holds nothing."** A record that never had the key is a
different thing, and abstaining on it is what keeps the clause off the archive. Three shapes
implement that, and the distinction between them is load-bearing:

```python
def _duty_blank(v: object) -> bool:
    """A seeded duty is UNFILLED when the key is present and holds nothing: JSON null, or a
    string that is empty or whitespace-only."""
    return v is None or (isinstance(v, str) and not v.strip())
```

A **wrong-typed non-empty** value (`session: 123`) **abstains**. That is deliberate and is the
family boundary above: a mistyped scalar is `validate_cycle_record`'s container territory or
render's coercion boundary, and a presence clause that also reported it would double-report another
gate's job while claiming to be about presence. `procedure_integrity`'s docstring states the same
posture for its own operands (*"a mistyped operand still only abstains"*).

| # | name | fires iff | severity |
| --- | --- | --- | --- |
| A | `session` | the key is present and `_duty_blank` | **warn** |
| B | `rigor.applied` | `rigor` is a dict, the key is present, and `_duty_blank` | alert |
| C | `remediation` progress trio | `remediation` is a dict **and the trio is PARTIALLY filled** — the union below | alert |

**Why C is a contract test and not three separate clauses.** `SKILL.md`'s schema block declares the
three together, and the audited defect was a partial fill — a present `achieved_index` beside an
absent `achieved_recall`. A test of "both present must agree" cannot see it (the missing operand
makes it vacuous); a test of "each must be present" would newly fire on the **legitimate** "pending
Phase 5" state, which `render_dashboard`'s remediation section documents outright as the shape where
`pruned`/`achieved_*` are all absent. So C is **the contract itself**, written as the union of the
two ways the contract can be broken:

```python
present = sum(1 for k in _DUTY_TRIO if k in rem)         # keys written
filled  = sum(1 for k in _DUTY_TRIO if k in rem and not _duty_blank(rem[k]))   # keys holding a value
return not (present == 0 or filled == len(_DUTY_TRIO))   # abstain only on UNTOUCHED or WHOLLY FILLED
```

**"Together" is itself a two-operand contract, and each single-operand projection drops one.**
A **key** count misses `{"pruned": 3, "achieved_index": 402, "achieved_recall": ""}` — three keys,
two facts, the shape a pass reaches by emitting the block with a placeholder. A **value** count
misses `{"achieved_recall": ""}` — one key, no fact, which `_duty_blank`'s own reading calls
unfilled and which is the reading A and B apply to their own keys. Neither operand is the rule: the
trio must arrive *together*, and "together" has a writing half and a holding half. The predicate is
the union for the same reason `_duty_blank` reads `""` and `null` alike — **a field that renders as
nothing is not a filled field** — and which half a given record fails is not the clause's business.

*(Revision 3 — the shipped form is the union above; revision 2 shipped a **key count** with a
paragraph defending it. The adversarial pass found the corridor in `{"pruned": 3, "achieved_index":
402, "achieved_recall": ""}`, and the defence it replaced was false on its own evidence as well as
narrower than the rule. It read: "the sub-case is unreachable: the seed writes none of the three,
and the only producer that does is `distill_scan --into`, which parses a JSON number." Both halves
fail. `distill_scan --into` writes the **`distill`** block and never touches `remediation`; and the
seed's own comment states why — "OMIT pruned/achieved_* — the model fills them in Phase 5". The
trio's producer is **the pass** — a model writing the record — so *"can anything produce the shape
this fires on?"* has one honest answer for a model-authored block: yes, a model can, and the
audited defect is what that looks like. The fleet cannot choose between the three forms (all three
fire **6** of 99 records — §3.1 — so the `filled` operand changes nothing on the archive), but a
census of what has been written cannot speak for what can be written. This is the same *"can
anything produce it?"* test that dropped clause D (§2.6), applied where it belongs: to the shapes a
**model** can emit, not to the shapes the scripts have emitted so far.)*

**Why A does not gate.** `seed_record` writes `"session": "",  # fill with the session id when
known` while `SKILL.md` forbids *"fabricating session ids"*. Gating on A would resolve that
conflict **in favour of fabrication** — the wrong direction for a validator in a repo whose
diagnosed disease is self-reported fields. A is **reported, never enforced**: it prints in the
panel and changes no exit code. Its 20/94 prevalence (§3.1) says the duty was ignored through most
of the archive's history; that is a statement about the duty's signal quality, not a mandate to
force it.

**Why there is no `rigor.phase == "final"` conjunct.** It would have been a tempting belt-and-braces
era gate, and it is rejected on measurement and on principle. Measured: `phase != "final"` holds on
**0 of the 94 records carrying the key** (and 0 of 93 outside the scratch class — §3.1), so it buys
nothing. And it is itself a model self-report — the same
file's own prose says *"the model sets `phase='final'` in Phase 2"* — so gating on it would let one
omitted field silence the entire family. **The era gate is the record's shape, never a label the
record applies to itself.**

### 2.3 The exit ladder

The gate is the **persist gate only**, which is the ONE surface that knows the record was just
written by a live pass. It already computes that: `judged = persist_dir is not None`.

The duty arm is inserted into the existing ladder **after the arc arm**:

```
procedure_integrity  → not ok        → cue → exit 3     (unchanged, stays FIRST)
arc_completeness(enforce_post_arc=True) → not ok → cue → exit 4   (unchanged)
duty_gaps            → any alert     → cue → exit 3     (NEW)
narration arms                       → ... → exit 3/4  (unchanged, judge LAST)
```

**The ordering is a design decision, not an implementation detail.** The first draft put the duty
arm first. That would have made a record with a **gating** gap — a clause whose severity is `alert`,
`rigor.applied: ""` say — **and** a 4/6 arc exit 3, masking the arc diagnostic entirely and sending
the model back to Phase 3 with the wrong remedy, on a loop it could not exit by following the cue.
Ordering is by **check specificity**: a record-side structural failure outranks a record-side field
gap, and both outrank the conversation-side arms, which the existing comment already states as
*"the conversation-truth arms judge LAST"*.

*(Revision 9 — the witness above was `session: ""`, and that witness **cannot exhibit the reorder it
was cited for**: the arm gates on `severity == "alert"` while clause A is `warn`, so a session-only
gap exits **4** under *either* order — measured on both trees. The design's intent had been written
as a property of the code, which is the same slip this document records against its own revision 3.
The clause that can feel the reorder is an alert one, and this paragraph now names one; the comment
at the arm carries the same correction.)*

*(Revision 3 — this paragraph asserted *"Exit 3 must never pre-empt exit 4"* as a bare claim about
the code, and that is **false and measurably so**: the `procedure_integrity` arm sits five lines
above the arc arm, so a record carrying a lazy-skip **and** a 4/6 arc exits **3**, not 4. The rule
the shipped code actually holds is the scoped one — *this* arm, inserted **below** the arc arm, does
not pre-empt it. The universal was the design's intent written as the code's property, which is the
shape this whole cycle exists to close; the code was right and the sentence was wrong.)*

**The exit-3 cue branches on which check fired.** The existing arm hardcodes *"NOT over — the dream
pulls you back: narrate the return to Phase-3 verification dreamily"*, which is right for a
lazy-skip and wrong for a duty gap. A duty gap is repaired by **filling a field**, not by running a
verification fan-out; the cue must say so or it routes the model into a loop whose remedy does not
apply.

Exit 3 therefore gains a **second meaning**. Both are "the record is not fit to close", and the
panel and cue disambiguate them; the exit-code budget is small and the existing key is correct.
The key is a **SET of arms**, and the arm **ORDER** is a separate fact (§2.3's ladder) — an
enumeration that lists the key's meanings without the order is half the contract.

**Every enumeration of exit 3 is updated in the same change, and they are enumerated rather than
counted** — the same rule the docstring census in §2.5 applies to itself. By greppable anchor, not
by line: `render_dashboard.py`'s `--persist` ladder comment · `SKILL.md`'s Phase-5 exit-code key,
its version line, and its new Phase-5 record-duty paragraph · `harness-map.md`'s record-side-gates
line and its exit-code key · `AGENTS.md`'s terminal-gates line · `README.md`'s blurb ·
`dream_procedure.py`'s record-side-gates list · `CHANGELOG.md`'s new entry. Two specs gain a row
rather than a rewrite: `docs/dream-arc-contract.spec.md`'s cue table (the duty arm carries its own
cue, so it needs its own row) and `docs/dream-narration-teeth.spec.md`'s two-item list of the
record-side gates.

Sites that enumerate a **different** subject are deliberately left alone, and the distinction is
the reason this list is written out: `dream_procedure.py`'s EXT-arm note and `harness-map.md`'s EXT
row describe the narration module's own arms; `CHANGELOG.md`'s v0.1.44 entry and
`docs/final-phase-debrief.spec.md` use *"substantial pass"* as a historical/debrief phrase about a
past release. Widening those would be editing a true claim about one subject to mention another,
which is its own class of defect.

### 2.4 The panel

A new `_duty_gaps_section(record)`, rendered inside `render()`'s existing `if judged:` block beside
the three panels already there. It follows `_arc_gate_section`'s structure, and specifically its
rule that **the subtitle is DERIVED, not a literal**:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ⚠ RECORD DUTY GAPS   · 2 seeded duties the pass left unfilled
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    session — the pass never filled the id it seeded
      → fill session with this pass's id — or leave it
        blank when the id is genuinely unknown (SKILL
        forbids fabricating one); ADVISORY, never gates
    rigor.applied — the pass recorded no ceremony tier
      → record the tier the pass actually ran, then
        re-render
```

*(Verbatim output for a `session: ""` + `rigor.applied: ""` record at `judged=True`, ANSI stripped —
not a hand-drawn mock. A mock in a design-of-record is a claim no test reads.)*

- **There is no shared closing remedy line.** Each row prints its own `remedy`, because the three
  remedies are different actions (fill an id / record a tier / complete a trio) and a single
  sentence covering all three would be the defect described in §2.2, one layer up.
- The subtitle's count and the body's rows are derived from the fired rows — **and the count's
  OPERAND is the rows.** This bullet read exactly that sentence in revision 3, and the sentence was
  true of the rows and false of the count: the code printed `len(gaps)` (fired CLAUSES) under the
  words *"seeded field(s)"*, and for clause C the two differ by construction — the trio is **three
  fields** behind **one** clause. So the audited defect shape (`{"achieved_index": 100}`) rendered
  **"1 seeded field"** directly above a row naming three fields, two of them blank: the cycle's own
  subject — a derived number whose label names a different operand than the code uses — arriving in
  the cycle's own panel, one layer above the code it was written to fix. The count is now the
  **number of rows drawn** (a reader can verify it by counting them, which is the whole test of a
  derived count), the FIELD count is left where the fields are named, in the rows, and the wording
  says *duty* rather than *field*. Caught by the adversarial pass, not by the suite: the shipped
  pin for the A+B shape asserts a count, and that fixture fires two clauses over two fields, so
  **clauses == fields** there and the two operands are indistinguishable. The trio fixture is the
  one shipped shape where they disagree, and it is now pinned as the **relationship** — subtitle
  count equals rows drawn — rather than as two literals, so it holds against a reworded subtitle:
  with the field-count operand restored, the count reads *3* above a single row and the check reds —
  **exactly one check, and it is that one.** The pass total is deliberately not carried here: it
  belongs to the revision it ran on (base **1984**), and the suite's base has moved twice since;
  §4.4 carries the batch whose base is current.
- Per-row `label — detail` comes from the row's own `label` and `detail`, so a fired clause can
  never be described by another clause's words.
- `col` is red when any fired row is `alert`, yellow when only `warn` rows fired — so an
  A-only record renders the panel in yellow and still exits 0.

**No structural change to `_procedure_integrity_section`, and one word of its subtitle.** The
adversarial pass reported the subtitle and remedy as hardcoded — they are — and inferred they would
misframe a duty gap. That inference was **contingent on the wrong host**: with the clauses in their
own predicate and their own panel, the integrity panel never describes a duty gap. The colour-only
severity is correct for a two-valued alert/warn, and the remedy string names the fan-out the
predicate is about. **A hardcoded label is a defect only when it can be false** — so the label was
then tested against the predicate's firing condition rather than against its own prose.

The predicate fires iff `tier >= SUBSTANTIAL` **and** `tally <= 0` (`tally` =
`confirmed + corrected + unverifiable`). Read against that set, the subtitle was **false for a named
shape in two ways**, and the two have different resolutions:

- *"substantial pass"* was **narrow**: the predicate fires on `HEAVY` as well, and `HEAVY` is a
  reachable, ordinary magnitude. **Fixed** — the subtitle now reads *"substantial-or-heavier pass,
  zero verification recorded"*, which is true for every firing record's tier by construction.
  (This is the same repair the v0.4.33 docs pass applied to the honesty surfaces that paraphrased
  the predicate; the panel itself was one of them.)
- *"zero verification recorded"* is **loose on a negative tally**: `tally <= 0` includes `tally < 0`
  (`{"confirmed": -1}` sums below zero; so does `{"confirmed": 3, "corrected": -5}`), and the
  predicate's own docstring says the negative case is deliberate — *"a negative/junk tally can't
  dodge it"*. Fixed at the **predicate's `reason` string**, which is the canonical text this
  subtitle and the archive badge's tooltip both paraphrase, and therefore **not fixed in this
  cycle**: that string is stamped into archived payloads as `_integrity.reason` and rendered by all
  three archive-wide consumers, so editing it retro-flips archived display text — the exact harm
  §2.1 chose this host to avoid. Named in §5 with the reason, rather than left as an unstated
  overclaim in a sentence asserting the opposite.

So the honest form of the revision-2 claim is the scoped one: **the literal is true in every case a
producer reaches, and false on one junk shape whose repair is out of this cycle's blast radius.**
"A hardcoded label is a defect only when it can be false" survives — this one *can* be, which is why
one of its two halves moved.

### 2.5 The docstring census

`validate_cycle_record`'s docstring claims:

> *"Two checks sit on the far side of that line, each because the VALUES contradict one another
> rather than merely being mistyped: `demotion.verdict` (v0.4.21) and the index reconcile invariant
> (v0.4.30)."*

**The count is wrong, and has been for a long time.** Enumerated from the function body by AST
census — not by reading — the far side holds **sixteen** rows over **22** warning sites, in three
kinds. The `Sites` column is not decoration: it is the operand that makes the total checkable
instead of asserted, and it is what the first two attempts at this table both got wrong.

| Kind | Check | Sites | Since |
| --- | --- | --- | --- |
| **disagree** | `demotion.verdict` vs the scripted block (three patterns) | 3 | v0.4.21 |
| disagree | `demotion.surfaced` vs the rank cap | 1 | v0.1.67 |
| disagree | `distill.{top,top_chains,used}` vs the persist cap | 1 | v0.1.82 |
| disagree | `usage.per_fact` / `usage.misses` / `usage.mention_stems` vs the scanner caps | 3 | v0.1.63 / v0.1.67 / v0.1.85 |
| disagree | `network.fact_holdings` vs the incidence limits | 1 | v0.4.13 |
| disagree | `network.fact_holdings` vs the holder reference limit | 1 | v0.4.13 |
| disagree | `network.fact_holdings` `held_n` vs the emitted holder count | 1 | v0.4.13 |
| disagree | `network.capture` total vs emitted | 1 | v0.4.17 |
| disagree | the U1 unverifiable tally vs its named carriers, both directions | 3 | v0.4.22 |
| disagree | the index reconcile invariant | 1 | v0.4.30 |
| disagree | `dream` arc completeness vs the beats contract | 1 | v0.4.1, narrowed v0.4.29 |
| **membership** | `workflow_proposals.candidates[].disposition` is not a known value | 1 | v0.1.87 |
| membership | `…disposition` declared on a non-fleet-candidate | 1 | v0.1.87 |
| membership | `network.stack_edge_facts` names an unknown node label | 1 | v0.4.13 |
| membership | `network.fact_holdings` holder resolution — unknown or repeated | 1 | v0.4.13 |
| **absent/dup** | `network.fact_holdings` fact identity missing or duplicate | 1 | v0.4.13 |

**Three successive counts of this list were wrong, and the way each was wrong is the section's
point.** The docstring's original *"two"* was a guess that stayed put while thirteen clauses were
added beside it. Revision 2's table carried **ten** rows and called them "value-contradiction
checks" — the count wrong, and the *kind* wrong in the more instructive direction: the far side is
not co-extensive with "two values disagree". Three rows are **enum membership** and one carries a
**presence disjunct inside its own warning text** (*"has missing or duplicate fact identity"*); the
revision-2 table was the *disagree* subfamily presented as the whole.

**Then revision 3's own correction — the one written to fix exactly this — said "fifteen" and was
short a row again.** `network.fact_holdings`' holder resolution (a holder sid must resolve to a
captured node, and must not repeat) sits at the far side beside the identity row and was in neither
the table nor the docstring. It was found by re-deriving the census with the *site* as the unit
rather than the *warning text*: the row-grouping had been done by reading, and a reading groups by
what the rows look like, while the body emits by block. **The missing row is a MEMBERSHIP row —
again, precisely the kind the "value-contradiction" framing hides.** That is the same defect
recurring one layer out, twice, in the sentence written to prevent it: which is why the fix here is
not a third, more careful count.

**The fix is that the census is now executed.** `tests/smoke.py` AST-parses
`validate_cycle_record`, splits its `warnings.append` sites into SHAPE (family 1's descent rule —
*"is not a &lt;type&gt;"*, *"contains a non-dict item"*) and VALUE, and requires the docstring to
enumerate 16 rows against the body's 22 value sites. A new far-side clause reds the suite until the
docstring and this table grow with it, so *"the body is the census"* is enforced rather than
promised. The pin cannot say **which** row is missing — a count never can, and the docstring's own
text says so — only that the two numbers must move together. Docstring and table are therefore
**grouped by kind rather than walked in body order**, and the docstring no longer claims otherwise;
that claim was false when written, which is how a reader would have been sent looking for a
mismatch that was not there.

**An instrument is only as wide as its match set, and this one was widened five times.** The first
cut walked `validate_cycle_record`'s body for `warnings.append`. The five closed forms below are
attributed by **row** rather than by a count of what a pass measured — the count is testimony about
the PASS, while each row is checkable against the code. For the same reason **no row here claims how
its form was *noticed***: a discovery story is testimony about an afternoon, and it outlives the
afternoon exactly as a count does. Each row states the injection, the operands it moved on the
revision it ran against, and the branch that closes it — and every one of them was an injection
that left every surface green:

| evasion | before | now |
| --- | --- | --- |
| **delegation** — the clause lives in a helper the body calls | measured **GREEN**: a body walk cannot see a clause that lives elsewhere | the walk followed bare-name calls **one level deep**, which closed the injection as written and left the *class* open — body → `_h1` → `_h2` → `append` was **also measured GREEN**. It is now a **worklist fixpoint** over the call graph, so delegation counts at any depth; the closure measures 8 functions on the shipped module |
| **re-methoded mutation** — the clause is added by `warnings.extend([...])` | measured **GREEN**: only `.append` was matched, so the site existed and no count moved | `_followable` **whitelists the four positions the census can follow** — the `.append` call it counts, the empty-list init, the `return`, and a hand-off to a callee naming the parameter `warnings` — while `_refs` collects **every** `Name(id="warnings")` in the closure and reports the ones outside it. That count must be 0, and it is a **separate check** so its red is legible as itself rather than as a count that will not reconcile. **The inversion is what makes the set bounded**: "every way to write the binding" is unbounded — any construct that binds a name qualifies — whereas "every position a reference can occupy" is finite and answerable (§2.5, revision 9) |
| **renamed parameter** — the clause is written by a helper that calls its parameter `warns` | **GREEN, and still green in the count even now** — the closure walk follows the call, but `warns.append` binds to a name no `warnings` filter in the file can see | **RED via the whitelist only.** This is the honest shape of the fix: a hand-off is recognised only when the callee's parameter *at that position* is itself named `warnings`, so the unfollowable case is reported instead of assumed benign. Measured: `value=22` (the count pin unmoved) with `escapes=1` |
| **drifted legend** — the docstring's three `· KIND — gloss` lines, which *define* the tokens every count is keyed on, are retagged (`· MEMBERSHIP —` becomes `· DISAGREE —`) | **GREEN, every operand unmoved** — the legend is excluded from the row list by a **prefix test**, and a retag from one KIND token to another *preserves that prefix*, so the legend keeps dropping out of `_rows` exactly as a correct legend does and not one operand moves. The docstring then teaches that *disagree* means *membership*, while the row counts, the split and this table all still reconcile | the legend's token tuple is returned and asserted in order. A token **outside** the three is loud in whichever operand counts that surface — a **legend** retag stops matching the exclusion, lands in `_rows` and moves that count (measured: rows 16 → 17 with the legend short a token), while a **row** retag leaves `_rows` where it was and is caught only by the KIND split (measured: the split 11 → 10, rows 16). The two guard different directions; **the gloss after the token is read by nothing** — measured GREEN on both the legend and the spec table's prose column |
| **laundered receiver** — the clause is added through a **second name** for the list: `_w = warnings`, then `_w.append(...)` | measured **GREEN, every operand unmoved** — and measured on the *shipped* module at this cycle's own revision, not on a reconstruction: **nine operands unmoved, `1987 passed, 0 failed`**. The instrument is not *wrong* here, it is **narrow**: the enumeration filtered on the spelling `warnings`, so an append made through another name was at once (a) a write that enumeration could not name and (b) not a `warnings` write for the count whose whole job is to catch unnamed writes. Each filter was assuming the other would see it | the reference set is now **decided by the reader, not the writer**: `_refs` collects the reference wherever it occurs, and `_followable` decides from its **position** whether the census can follow it — so a reference through a second name is red because the *position* (a bare reference outside the four) is unfollowable, not because a write-form list happened to omit the spelling. Measured on **seventeen reference forms against both revisions**: the shipped census reads `escapes` **0** on nine of them where this one reads **1**, both read **1** on the other eight, and the unmodified module reads **0** on both (§4.4). The boundary is held by the **control**, not by the coverage: the **unmodified module reads `escapes` 0 on both revisions**, so the nine newly-red forms are the injected references and nothing else moved. What the whitelist *costs* is stated rather than hidden — a bare Subscript such as `warnings[0]` now reds too, where the shipped census read it `0`, because "derives a value *from* the list" is not a position the census can follow; the same is true of the two benign reads `if not warnings:` and `for _w in warnings:`. That is the safe direction (too wide is loud and inert, too narrow is silent), and it is the price of the set being bounded at all. `y = len(warnings)` reads **1** on both — **pre-existing** over-coverage, since `len` is a hand-off the module cannot follow; it is stated here because a reader who measures it *after* this change will otherwise attribute it to this change |

The re-methoded mutation row is the reason the whitelist is a count of *unrecognised* forms rather
than a list of known-bad ones: an enumeration of bad forms has the same defect as the walk it replaces — it is
only as wide as the author's imagination. The count is closed against everything that is not the
one form the census can follow, so a mutation form nobody anticipated fails **loudly** at the
whitelist — and *the laundering row is that sentence's own exception*, recorded because the claim as
first written was **"closed against every write to `warnings`"** while deciding what a `warnings`
write *was* by the spelling of the receiver's name. It over-counts in the other direction as well,
and deliberately: `y = len(warnings)` is a **read** of the list and still reads `escapes` **1**,
because the count is *"not the one followable form"*, not *"a write"*. Over-coverage is loud and
inert; a miss ships. What the census still cannot see is stated at the definition rather than left
to be rediscovered, and there are **three** such limits: **folding a new case into an existing
`.append` moves nothing** (no counting scheme can see it, though a *behavioural* fixture still
catches the cases it exercises); the SHAPE/VALUE classifier is a regex over the warning *text*; and
the gloss after a KIND token — on the docstring legend and on this table alike — is read by
nothing.

**Which forces a refinement of §2.1's family table, not just its count.** Family 3 is
*seeded-duty* presence — "did the pass fill the field it seeded?" — and the `fact_holdings` identity
row shows that **structural** presence at depth is a far-side row, not a `duty_gaps` clause: an
identity the block needs to be internally meaningful is a different question from a duty the pass
was handed and skipped. Stated precisely, because the loose form ("presence lives in `duty_gaps`")
is exactly the sentence that would send the next reader to the wrong host again:

> `validate_cycle_record` = *is a present value the right SHAPE / is a present value RIGHT* ·
> `duty_gaps` = *did the pass fill what it SEEDED*.

The fix, then, is to **enumerate rather than count**, and in the docstring itself to state the
boundary above, the DESCENT rule that generates the container row, and — because an enumeration
written from a function body drifts the moment the body grows — an explicit note that the container
list is *representative*, so the docstring's sentence never reads as a census it cannot be.

This is the same defect class as the cycle's headline, one level up: **a claim in a comment with no
test is a claim that drifts.** *"Two"* was true when written and stayed in the prose through
thirteen additions. The repo already has the rule — `render_dashboard.py`'s own `over_ceiling`
comment records *"an earlier draft named three, which is the number its author happened to know,
and a count is not a census until it has been counted."*

### 2.6 What was dropped, and on what evidence

The first draft carried six clauses. Three were dropped before implementation. Each drop is a
finding, not a simplification.

**The `lever` ↔ `candidates_surfaced` biconditional — dropped.** `lever = "gc" if share >
_MIRROR_DOMINATED else ("prune" if cands else "justify")` means `justify ⟹ zero candidates` holds
but its **converse does not**: the `gc` arm is taken regardless of `cands`. `tests/simulate_accumulation.py`
builds exactly that record by triaging one candidate list twice. Worse, for any record the script
produced, both operands come from **one dict literal** — so the clause is script-vs-script, can only
fire on a hand-edit, and catches none of the four audited defects.

**`entries[].action` vs `audit.memory.created` — dropped.** No sound biconditional exists.
`audit.memory` is a **per-store** content-hash rollup, while `entries[].files` spans all three
stores (`memory/…`, `claude_md/…`, `repo_doc/…`) and `entries[].store` is a third, unrelated axis.
An `added` row naming `claude_md/CLAUDE.md` moves a different store's counter, and
`tests/dashboard_fixture.py` contains exactly that row. The one real signal in the audited defect
was the **row's own reason** contradicting its **own action** — a model-phrase-vs-model-enum
contradiction that never touches `audit`. Recorded in §6.

**`remediation` half-seed (`required` and not `standing_justified`, `lever`/`candidates_surfaced`
absent) — dropped.** This one was dropped *after* the plan that carried it was approved, on
re-measurement, and the sequence is worth recording because the first number was wrong in a way
that would have shipped a false justification.

The clause as first drafted fired **13/100** on the fleet of the day, which looked like healthy
signal and motivated a `not standing_justified` guard that brought it to **1/100**. Re-deriving by
variant shows what the 12 were: **the legitimate suppressed block** — `required: False,
standing_justified: True`, which `seed_record` writes *deliberately* without a lever or a candidate
count (*"seed the lightweight suppressed block (no lever/triage to surface)"*). So the guard was
not a refinement; it removed a mostly-false-positive class.

**Re-measured 2026-09-17 on the drifted fleet (§3.1), the sequence reproduces in shape and not in
figures**, and the drift is worth reading rather than smoothing:

| Form | fires, 2026-09-17 |
| --- | --- |
| `lever`/`candidates_surfaced` **absent** — as first drafted, **no** SJ guard | **11** |
| the same **+** the `not standing_justified` guard — the form the plan carried | **0** |
| `lever` present-and-blank | **0** |
| `candidates_surfaced` present-and-null | **0** |
| either emptied | **0** |

All 11 of the drafted form's fires are `standing_justified` with `required` falsy, so the guard's
target is confirmed; the count moved 13 → 11 because the fleet moved, and the residual single fire is
**gone with the synthetic record it was**. The decision is untouched and in fact strengthened —
**every form now fires zero** — but revision 2's `all`/`genuine` column pair does not survive the
re-measurement intact, and the reason is worth more than the pair was. `genuine` was defined by
matching **one literal commit id**; §3.1 shows that row was one member of a **six-directory scratch
class**, and that the class is *live* — a test run appended to it mid-revision. The pair is therefore
replaced by a **named class** with both columns printed, so the operand choice is visible instead of
encoded in a filter that silently matches a string. A number whose operand has left the population is
not a number to keep re-quoting.

And it fails the same three tests that dropped the other two: it catches **none** of the four
audited defects; and its premise is **absence**, which unlike A/B/C carries **no era gate** — the
record cannot distinguish "the pass removed this" from "this record predates the field".

*(Revision 3 also retires a sentence here that claimed the clause had **"no producer path"**,
parenthesised as "the seed always writes both keys, and the Phase-5 refresh merges leaf-wise into
the existing block rather than replacing it, so nothing removes them". The parenthetical is false,
and its falseness is a better argument than the claim it supported: the seed's standing-justified
branch writes **neither** key — `record["remediation"] = {"required": False, "standing_justified":
True, "baseline_facts": …, "over_ceiling": …}` — which is precisely why the drafted clause fired on
it at all. And no Phase-5 refresh of `remediation` exists to merge into: `ctx["remediation"]` is
Phase 0's analysis, `seed_record` copies it, and the three progress keys are left to the model. The
surviving argument is the one that needed no producer census: **the same test that governs clause
C governs D** — D's firing shape is *absence*, whose producer is likewise a model-authored record,
but unlike C's it is absence of a **seeded** key, and the seed's own branch proves the absence is
normal. The decisive property is unchanged, and it is the sharpest one: **A and B have a producer
path** — `seed_record` writes `session: ""` and `_provisional_rigor` writes `applied: ""`, so a
skipping pass genuinely produces those shapes, while D's shape is what the seed writes when
everything is fine.)*

The decisive property, restated once because it is the whole reason D is not a clause: **a
firing shape the seed itself produces when nothing is wrong is not a defect signal.** A and B
survive it — the seed writes `session: ""` and `_provisional_rigor` writes `applied: ""` because a
pass has not yet reached the phase that fills them, and the `judged` gate is what tells a live pass
from a seed. D's shape is what the SJ branch writes *on a healthy store*, so the record cannot
tell the two apart at all, and no gate could.

---

## 3. Measurements

### 3.1 The population census

#### What this measures, and what it cannot

The census reads every `~/.claude/projects/*/memory/.consolidation-log.jsonl` and every
`~/.claude/plugins/data/consolidate-memory/ops/*/.consolidation-log.jsonl`, deduped on
`marker.(commit, timestamp)`. **Those are live session stores on the measuring machine, so this is
a fleet at a timestamp — not a checkout.** The script below is reproducible; its *output* is not,
and revision 2 was wrong to imply otherwise.

**The population includes the instrument's own scratch — and that is a class, not an exception.**
Measured composition of the raw 100 rows: **67** come from `~/.claude/projects/*/memory/` and **33**
sit under `ops/`, of which **six** are self-evidently test scratch — `h8`, `link_store`, `persist0`,
`relstore`, `tmp4lqb479m`, `valid` — one of them carrying
`marker = {"commit": "c", "timestamp": "t"}`. The plan hand-excluded a single synthetic row
(`marker.commit: "deadbeef"`) to publish its "0/99 genuine" figure. **That row was one member of this
class.** Excluding one instance by hand while leaving the class in place is the ad-hoc form of the
right fix, which is to name the class and report both columns.

**And the census moved while this revision was being written** — the cleanest evidence available for
why a prevalence number is testimony:

> Run early in revision 3, the script returned **99** records, A **20**, B **3**. Run again minutes
> later, on the same machine, the same script returned **100**, A **21**, B **4**. The difference is
> exactly one row: `ops/persist0`, whose log was appended at **07:44** by a run of **this cycle's own
> test suite**. That row fires A *and* B. The instrument contaminated itself while measuring — and it
> did so *because the cycle under test was running*.

Two framings, still not the same number:

- **Not a blast radius.** The gate is live-only (§2.3), so no archived record is ever re-judged and
  no archived display retro-flips. Blast radius is structurally **zero** — and it is structurally
  zero *because of the host choice*, not because the prevalence turned out low.
- **A prevalence estimate** — how often a past pass left this duty unfilled. This is the analogue
  of the `enforce_post_arc` *"1 of 55"* decision, taken on a measured number rather than a guess. The
  denominator below is the **94 records outside the scratch class**, because a fixture directory is
  not a pass; the raw column is printed beside it so the choice of operand is visible rather than
  buried in a filter.

| Clause | Raw (the glob as written) | **Prevalence (scratch excluded)** | Renders as |
| --- | --- | --- | --- |
| A `session` present-and-blank | 21/100 | **20/94** | warn — panel only, exits 0 |
| B `rigor.applied` present-and-blank | 4/100 | **3/94** | alert — exit 3 |
| C trio partially filled (a key count) | 6/100 | **6/94** | alert — exit 3 |
| C, measured as the shipped union form | 6/100 | **6/94** | — (identical on this fleet: it cannot choose) |
| `rigor.phase != "final"` (rejected conjunct, §2.2) | 0 of 94 carrying the key | 0 of 93 | — |

Supporting counts are **identical on both sides** — the six scratch rows carry no `remediation` block
at all, so the contamination reaches exactly two numerators and no supporting figure: **34** records
carry a `remediation` block, **24** of those are standing-justified, **11** of the 24 lack
`lever`/`candidates_surfaced` (the set §2.6's pre-guard row measures), and **16** carry all three
progress keys.

Re-derivation script — the one that produced the table, not a sketch of it:

```python
import glob, json, os

# The scratch class, named rather than filtered by a literal: these ops/ subdirectories are the
# test harness's own working dirs, not projects. A fixture is not a pass, so a fidelity figure
# should not count one — but the RAW column is printed beside it so the operand choice is visible.
SCRATCH = {"h8", "link_store", "persist0", "relstore", "tmp4lqb479m", "valid"}

def blank(v):
    return v is None or (isinstance(v, str) and not v.strip())

rows, seen = [], set()
for pat in (os.path.expanduser("~/.claude/projects/*/memory/.consolidation-log.jsonl"),
            os.path.expanduser("~/.claude/plugins/data/consolidate-memory/ops/*/.consolidation-log.jsonl")):
    for path in sorted(glob.glob(pat)):
        try:
            fh = open(path, encoding="utf-8")
        except OSError:
            continue
        src = path.split("/ops/")[1].split("/")[0] if "/ops/" in path else "<projects>"
        with fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(r, dict):
                    continue
                m = r.get("marker") if isinstance(r.get("marker"), dict) else {}
                key = (m.get("commit"), m.get("timestamp"))
                if all(k is None for k in key) or key in seen:
                    continue
                seen.add(key)
                rows.append((src, r))

TRIO = ("pruned", "achieved_index", "achieved_recall")

def report(label, pop):
    A = sum(1 for _, r in pop if "session" in r and blank(r["session"]))
    B = sum(1 for _, r in pop if isinstance(r.get("rigor"), dict)
            and "applied" in r["rigor"] and blank(r["rigor"]["applied"]))
    rem = [r["remediation"] for _, r in pop if isinstance(r.get("remediation"), dict)]
    key_n = union = 0
    for d in rem:
        present = sum(1 for k in TRIO if k in d)                    # keys written
        filled = sum(1 for k in TRIO if k in d and not blank(d[k]))  # keys holding a value
        if 0 < present < 3:
            key_n += 1
        if not (present == 0 or filled == 3):                        # the SHIPPED union form
            union += 1
    # `rigor.phase` — the rejected conjunct's operand, printed so the table's last row is produced
    # by this script rather than by a separate probe (a figure the table cites and the script does
    # not compute is the same defect as a count no test reads, one layer out).
    ph = [r for _, r in pop if isinstance(r.get("rigor"), dict) and "phase" in r["rigor"]]
    print("%-18s N=%-4d A=%-3d B=%-3d C(key-count)=%-2d C(union)=%-2d remediation blocks=%d"
          " · phase present=%-3d phase!='final'=%d"
          % (label, len(pop), A, B, key_n, union, len(rem), len(ph),
             sum(1 for r in ph if r["rigor"]["phase"] != "final")))

report("raw (the glob)", rows)
report("scratch-excluded", [(s, r) for s, r in rows if s not in SCRATCH])
```

Both C forms are printed on purpose: they agree on this fleet (6 = 6), and that agreement is the
evidence for §2.2's claim that the archive cannot choose between them. Both **populations** are
printed for the same reason — a single column would hide which operand produced the number, which is
the defect this whole revision is about.

### 3.2 The dropped clause's variant census

Measured on the same fleet as §3.1, and **the variant set is reproduced as §2.6's table rather
than as a second script** — a variant census whose only anchor is a `/tmp` path is a number no
later reader can check, and revision 2 cited exactly that. The forms, in words:

- **as first drafted**: `lever` **and** `candidates_surfaced` both absent — a pure absence test,
  with no `required` and no `standing_justified` operand at all;
- **as the plan carried it**: the same **plus** `required` truthy and `standing_justified` falsy;
- then the two key-emptiness forms and their union.

The revision-2 column pair (`all` / `genuine`) is gone with its operand: `genuine` existed to
exclude one synthetic record, and that record is no longer in the fleet (§3.1). A column that can
only be computed by remembering a row is not a measurement.

### 3.3 What the seed itself trips

`duty_gaps(seed_record(ctx))` **fires A and B** — the seed writes `session: ""` and
`_provisional_rigor` writes `applied: ""`, both by design. This is the single most important
consequence of the host choice and it is stated here rather than discovered in review:

> **The predicate cannot tell a seed from a finished pass, and must not try.** If it could, it would
> be reading a self-reported label (`rigor.phase`) to decide its own era — the trap §2.2 rejects.
> The `judged` gate is the entire protection, and it is sufficient because it is structural:
> `judged` is set by `main()` iff `--persist`, and no other caller of `duty_gaps` exists.

The first draft of this cycle proposed a pin asserting `duty_gaps(seed_record(ctx)) == []`. **That
pin is impossible** and its impossibility is the finding: it asserted the predicate abstain where
the predicate must fire, and would have been satisfied only by the label-reading era gate §2.2
rejects. It is replaced by three shipped checks that pin the fact from both sides rather than
wishing it away:

- **U7** — a fresh seed **does** trip the predicate (`["session", "applied"]`), so a later "make the
  predicate abstain on a seed" change has to argue with this design rather than quietly read
  `rigor.phase`;
- **G2** — a preview render (no `--persist`) of a gap record shows no panel and exits **0**;
- **G3** — `render(record, judged=False)` shows no panel where `judged=True` does.

The abstention direction needs no separate gate-level check: the pre-existing persist fixtures carry
no `session`, `rigor`, or `remediation` key at all and still exit 0 (§5 R4, measured), which is the
absent-vs-empty era gate exercised end-to-end through the very arm this cycle adds.

---

## 4. Pins

Per the repo rule, a "stays silent" assertion is **conjoined with a firing assertion inside the same
`check(...)`** — alone it passes pre-fix and is not a pin. **Twenty-three** checks ship, in seven
labelled groups — **U 8, P 5, X 2, G 3, W 1, H 1, C 3** — each check's own label naming its group; the
census constant in `tests/smoke.py` carries the same breakdown and is asserted against the reported
total, so a check that vanishes reds the suite. Revision 5 shipped nineteen of them; **P5** and
**C3** are revision 6's, and the amend ledger records what forced each — P5 by the **D1** mutation,
which showed the panel drawing a subset of the rows its own subtitle counts, and C3 by the
measurement that C1's taxonomy is blind to a clause worded in *shape* language. **X1** and **X2** are
revision 8's: unlike every other group here they pin the **parse** rather than the renderer, which is
the one surface a record can reach without the renderer being wrong at all.

**How the pre-fix column was obtained — measured first, and it is not what revision 2 said.** The
new harness run against the pre-fix scripts **does not report a set of red U checks; it aborts**.
Measured on a hybrid tree (`git archive 2b07ce3 | tar -x`, then the current `tests/smoke.py` over
it): **rc 1, 692 checks executed, then `AttributeError: module 'memory_status' has no attribute
'duty_gaps'` at `tests/smoke.py` line 3316, and no totals line printed at all.** The binding
`_gapA = ms.duty_gaps` is module-level, so the first reference kills the process and neither the U
group nor anything after it is ever evaluated. Revision 2's "all seven fail pre-fix on
`AttributeError`, a legitimate RED for a new predicate" described a per-check failure that does not
occur.

That changes what each group's pre-fix number *means*, so the method is named per group:

- the **P** group is a subprocess call, so its pre-fix value is observable from outside with the
  predicate absent — driven directly against the pre-fix renderer, all four fixtures exit **0** with
  no panel (§4.4);
- the **U** group cannot be measured by the revert at all, and its one genuinely pre-fixed check —
  the F1 evasion pin — is verified by **mutant C**, which restores the predicate's shipped-then-
  superseded key-count form. A cycle that changes its own predicate mid-flight has a real pre-fix
  revision for that change, and mutant C is it.

**U — the predicate, directly** (`ms.duty_gaps`, hand-built records).

| # | check | asserts |
| --- | --- | --- |
| U1 | duty A era gate | `{"session": ""}` fires; `{}`, `{"project": "p"}`, `{"session": "abc"}` do not |
| U2 | duty A is type-blind | `null` and `"   "` fire; `123` and `["a"]` abstain (§2.2) |
| U3 | duty B | `{"rigor": {"applied": ""}}` fires; `"LIGHT"`, `{}`, `{"applied": 5}` do not |
| U4 | duty C is the CONTRACT | 1-of-3 (the audited shape) and 2-of-3 fire; 0 keys (the documented "pending Phase 5" state) and 3-keys-3-values do not |
| U5 | **the F1 evasion** — the union's `filled` operand | three keys with one holding `""` fires; the same with `null` fires; `{"achieved_recall": ""}` alone fires; `{"pruned": "", "achieved_index": null}` fires; the **true zeros** `{0, 0, 0.0}` abstain, as does `{"over_ceiling": True}` |
| U6 | the seed shape | the standing-justified block fires nothing; `"junk"` / `None` / `[1]` fire nothing |
| U7 | severity | A yields `warn`; B and C each yield `alert` |
| U8 | the seed trips it (§3.3) | a fresh seed yields exactly `["session", "applied"]` — the design's central consequence pinned rather than left to be rediscovered |

U5 is the check that makes this cycle's own predicate falsifiable: it is written so that the
*pre-fix* form (a key count) provably fails it, which is what mutant C measures. It is also why the
casualty case is pinned in the same check — `{0, 0, 0.0}` is a *measurement*, not a blank, so a
repair that reached for numeric coercion instead of presence would red U5 from the other side.

**P — the gate**, `render_dashboard --persist` as a subprocess in the existing persist family, over
one shared persist dir and the existing record-writing helper.

| # | check | pre-fix |
| --- | --- | --- |
| P1 | a complete 6/6 arc with `session: ""` exits **3**; the panel names `session`, `rigor.applied` and its own count; the **stderr cue is the duty cue** and **`"Phase-3 verification dreamily"` is absent** (§2.3) | exit **0**, no panel → PIN |
| P2 | the same with `rigor.applied: ""` alone exits **3** | exit **0**, no panel → PIN |
| P3 | the same with a partially filled trio alone exits **3**, naming `remediation progress` | exit **0**, no panel → PIN |
| P4 | **the F1 evasion at the terminal**: three keys with `achieved_recall: ""` exits **3** with the panel and the duty cue | exit **0**, no panel → PIN (and RED under mutant C) |
| P5 | **all three clauses at once** — the only clause count where the subtitle's number and the row loop *can* differ: exits **3**, the subtitle reads `3 seeded duties the pass left unfilled`, and that number equals the rows actually drawn | exit **0**, no panel → PIN (and RED under **mutant E**, which draws `gaps[:2]`) |

**X — the parse's own contract** (revision 8). Both attack `_duty_panel43` from the two directions a
record-controlled string can reach it, and both were found by review against the **parse** rather
than against the renderer it reads — which is why §4's earlier tables could not have shown them. The
mutants below are named **XA/XB/XC** to keep them distinct from §4.4's A–E.

| # | check | pre-fix |
| --- | --- | --- |
| X1 | a record-controlled `project` carrying the panel's own subtitle sentence **verbatim and self-consistently** (the same number, the same three `→ ` rows) is **refused**: the parse returns `(-1, -1)`. The premise is asserted too — the anchored sentence appears in that output exactly **twice** | the parse reads the **banner** and returns `(3, 3)` — the *true* pair for a healthy panel, which is what made the defeat silent → PIN, **RED under mutant XA** |
| X2 | a record-controlled digit run past `int()`'s 4300-digit limit neither aborts the parse nor denies it the real panel: the parse still reads the panel's own **subtitle number** — asserted alone, never the pair, because the row count is P5's property and asserting it coupled this check to mutant E (§4.4) | **the call raises** — 705 printed checks (704 ✓ + 1 ✗), no totals line, 1284 never run — so the check cannot be evaluated at all → PIN, **RED under mutant XB** (as a refusal, not a panic) and **abort under XC** |

**G — the boundaries.** These guard defects **this design introduces**, so no pre-fix pin can exist
for them. But "guard" does not mean "passes pre-fix", and the difference was measured rather than
assumed (§4.4):

| # | check | guards | verified by |
| --- | --- | --- | --- |
| G1 | a duty gap **and** a 4/6 arc exits **4** with **both** panels, and the cue is the arc's | the §2.3 ordering (drafted duty-first, which exits 3 and masks the arc) | **injection**: duty-arm-before-arc-arm ⇒ rc 3, G1 RED |
| G2 | a **preview** render (no `--persist`) of a gap record shows no panel and exits **0** | the `judged` boundary in the display direction | **injection** (dropping `judged` reds it), *and* its assertion is true of pre-fix code |
| G3 | `render(record, judged=False)` shows no panel where `judged=True` does | the same boundary at the API level | **injection**: `judged` dropped from the panel block ⇒ RED |

**"Passes the pre-fix revert" needs a stricter reading than revision 2 gave it, because the revert
measurement does not exist for this cycle.** The pre-fix suite aborts at line 3316, so no v0.4.33
check — G2 included — is ever *evaluated* by a revert run; "G2 passes the revert" can only mean
**G2's assertion is true of pre-fix code**, and that was then measured directly rather than
inferred: driving the pre-fix renderer on a gap record without `--persist` returns **rc 0 with no
panel**. The same probe on G3's shape returns no panel **in either direction** (`judged=True` and
`judged=False` both absent), so G3's positive conjunct fails on pre-fix code — for the reason the
group's label already states, which is *not* the boundary it guards. Revision 2 and the shipped
check label both said "passes the pre-fix revert" without that distinction; the distinction is the
entire content of the claim.

**A guard's verification is the injection of its own defect**, which is the table's last column —
and it is the only test that distinguishes a guard that works from a guard that is merely green.
The exit direction of the `judged` boundary needs no separate check: the arm sits inside
`if persist_dir:`, so no non-persist render can reach it.

**W — the advisory path.** One check, pinning three wires at once, because a check that pins one
wire and lets the other two drift is how this class survives:

| # | check | pins |
| --- | --- | --- |
| W1 | `session: ""` alone (severity `warn`) exits **0** *with* the panel, `"ADVISORY duty gap"` is on stderr, `"persist clean"` is **not**, and the Phase-5 instruction is | (a) the severity→exit wire — without it, replacing the arm's `any(g.severity == "alert" …)` with a bare `if _gaps:` flips A-only from 0 to 3 and the suite stays green; (b) the cue's truth — a printed ⚠ beside the words *"persist clean"* is this cycle's own thesis one layer out, since SKILL defines the WAKE as rendering "only through a clean exit 0"; (c) that the advisory path still instructs, rather than going silent |

**H — a named hole, pinned so it cannot change shape silently.** The panel prints before `_persist`
runs, so an unappendable cycle log leaves a fired panel on screen and returns **0** at `main`'s
`no-dir`/`io-error` arm. It is a **desync between the display and the exit**, it is the arc arm's
documented behaviour reached through a new door, and it is recorded in §5 rather than fixed. The
check asserts the *current* shape deliberately: if a later cycle closes the hole, H1 reds and says
to update both this spec's §5 list and the check. Its setup is root-proof — a **directory** where
the log file must go, so the append raises `IsADirectoryError` with no `chmod` for a root runner to
defeat.

**C — the §2.5 census, pinned on the body rather than on its own prose.** The three checks in this
cycle that guard a *document* rather than shipped behaviour, and they exist because §2.5's subject
is a count that was wrong three times running. C1 reconciles the surfaces; C2 states the
instrument's **coverage**, because a census that reconciles perfectly while a clause sits outside
its match set reconciles within a set it never questioned — the failure mode of every version of
this count to date; C3 watches the raw **surface**, because C1's taxonomy is blind in exactly one
direction (a clause worded in *shape* language lands among the sites the docstring does not
enumerate, where no assertion reads it — measured **green**). Three checks rather than one because
their reds are different findings with different repairs: a count that will not reconcile is a
missing row, a whitelist red is a walk whose match set is too narrow, and a surface red is a clause
that arrived or left and needs classifying.

| # | check | pins |
| --- | --- | --- |
| C1 | **three surfaces of one census agree**: the body's **22** VALUE sites, the docstring's **16** `· KIND` rows, and §2.5's table — **16** rows summing to **22** `Sites` — each surface splitting **11 disagree / 4 membership / 1 absent-dup** | that all four numbers move together. It AST-parses `validate_cycle_record`, splits the `warnings.append` sites into SHAPE (*"is not a &lt;type&gt;"*, *"contains a non-dict item"* — family 1's descent rule) and VALUE, **follows bare-name calls to a fixpoint over the call graph** so a clause delegated to a helper counts at any depth, then parses §2.5's table out of the spec file. It **cannot name which row is missing** — a count never can, and the docstring says so — only that a far-side clause arrived without the list |
| C2 | **no reference to `warnings` escapes the census**: over the same closure, every reference occupies one of the four positions `_followable` whitelists — the `.append` call the census counts, the empty-list init, the `return`, or a hand-off whose callee names that parameter `warnings` at the matching position | that the census's coverage is *stated*, not assumed. The unit is the **REFERENCE, not the write**: `_refs` collects every `Name(id="warnings")` and `_followable` classifies it by **position**, so the count outside the whitelist must be **0**, and a re-methoded or renamed-parameter site reds **here** instead of leaving the count pin green over a clause it never saw (§2.5). The whitelist's cost is stated at its definition: a **benign read** — `if not warnings:`, `for _w in warnings:`, `warnings[0]` — is reported too, because a position the census cannot follow is red whether or not the reference writes. That is the safe direction; the opposite one is silent. It reports no location, only the count; and a widened existing `.append` is invisible to it, which is stated at the definition |
| C3 | **the far side's raw surface is 46** `warnings` writes in total — the **22** the docstring enumerates (C1's operand) and the **24** it does not | the twin of C1's blind direction, and it over-covers **on purpose**. C1 counts the enumerated 22, so *retagging* a value site into shape wording reds C1 (22 → 21) while *adding* a shape-worded clause is invisible to every other assertion. A pin that catches one direction and misses its twin is the shape this cycle exists for, so this watches the **surface**, not the taxonomy. It cannot see a count-preserving edit — a new case folded into an existing `append`, a widened guard, a conditionalised append — and that limit is stated at the definition rather than hidden |

**The label was wrong before the check was.** Revision 3's C1 said it reds *"until the docstring and
spec §2.5's table agree"* while **nothing read the spec at all** — a claim wider than its check, in
the check's own label, which is this cycle's defect class arriving inside its own fix. The same
adversarial pass measured a second evasion: a far-side clause moved into a **helper the body calls**
was **green**. Both are closed, and closing the second is what made the check a *reachability* walk
rather than a body walk.

Verified by injection in both directions and on all three surfaces, because a count-shaped check has
two ways to be vacuous and this one writes its census three times:

| injection | expected | measured |
| --- | --- | --- |
| drop the 16th row (the literal pre-fix state) | RED | **RED** |
| add an unlisted far-side clause to the body | RED | **RED** |
| add a **second** `warnings.append` — a new site | RED | **RED** |
| move a far-side clause into a **helper the body calls** | RED | **RED** — was **GREEN** |
| edit one `Sites` value in §2.5's table | RED | **RED** — was **unobservable** |
| retag a docstring row `DISAGREE`→`MEMBERSHIP` (11/4/1 → 10/5/1) | RED | **RED** |
| retag a spec table row likewise | RED | **RED** |
| **fold a new case into an EXISTING append** | RED | **GREEN — the open limit** |

**The last row is a hole in *granularity* — and C1 has exactly three, of which the classifier is
one and the unread gloss text is the other.** The check counts *sites*, so a far-side case added to a clause that already exists changes
no number it reads: reproduced, not theorised. Closing it means classifying *conditions* rather than
*sites*, and the structural classifier that would do it was tried and rejected (below). Both limits
ship **named** — in the check's own label, in its comment, and here — because a limit written down
has stopped being the thing this cycle audits: an *unstated* limit on a gate is a miss that renders
as silence, while a stated one is a bounded, reviewable cost. What bounds this one is the table
above: seven of its eight injections red, so the evasion is confined to one shape rather than to a
family of them.

It reads the file through `ast.get_source_segment`, not `ast.unparse`, which is 3.9+ and would break
the 3.8 CI leg.

**And its own limit, stated in the same breath — because a gate that fails quietly is this
cycle's subject and C1 is not exempt.** The SHAPE/VALUE split is a regex over the warning *text*,
so a far-side clause worded in shape language (*"… is not a list"*) is classified SHAPE and slips
past the count: a **silent** miss. The opposite error is **loud** — a container check worded
without the idiom (*"… must be dicts"*) counts as VALUE, reds the pin, and demands a row it does
not need. The asymmetry is the whole point: of C1's two errors, only the one that costs *coverage*
can ship unnoticed, so the limit is written down here rather than left to be rediscovered. All 24
SHAPE-classified sites were hand-checked against that claim on this revision and all 24 are family
1. A structural classifier was considered and rejected: `held_n is missing or below emitted
holders` is guarded by an `isinstance(int)`, so "is the append under an isinstance test" does not
separate the families either — it trades a silent miss for a different one.

### 4.4 The measurement behind the table

**Every number below was measured in one batch, on one revision.** **Five** mutant trees were rebuilt
from the shipping tree itself (not from an earlier copy) — each differing from it by **exactly one
edit**, verified by a whole-tree diff — and their suites were run in parallel. Four of the five are
the regression diagonal; the fifth restores **D1**, and its result *is* a finding rather than a check
on one.

**"One revision" is checkable, not asserted.** The batch wrapper sha256s the working tree before it
builds the mutants and after their suites finish, and refuses the result if the two disagree; both
sides of the last run — taken on the **committed** tree at **`7e756a2`**, after every prose
correction below — read **`30d13e3dff685f0e`** (**202** files, whole tree). The commit is named
because that is what makes the value *recoverable*: `git show 7e756a2` is the tree that produced it.
A re-fingerprint of the tip will still differ, because this spec lives inside `docs/` and writing
the number down changes it — the value identifies the *run*, which is the only thing it was ever
for. (The previous value, `6af3404a4d890d95`, describes the pre-revision-7 tree and is recorded as
**superseded, not wrong**.)

**It is testimony, not a derived number, and the fix itself is the reason.** The match set is drawn
around *everything in the tree*, not around *everything the suite reads*, so it deliberately includes
artifacts the harness never opens. Counted on this checkout: of the **202** files, **194** are
tracked — re-derivable by anyone who clones — and **8** are not, all of them gitignored
maintainer-only files that will never be in the repository (`release.sh`, five `security/**` documents
and workflows, `.claude/settings.local.json`, `PREFLIGHT.md`). **This spec is tracked**; what is true
of it is that a **clone of `main`** cannot see it yet, because the branch has not merged. So
`30d13e3dff685f0e` is **testimony** where the 194 are not: **what makes it good evidence — that
it is bound to this checkout — is exactly what stops anyone else re-deriving it.** Over-covering
is the safe direction for this gate (a
match set wider than the harness cannot miss a file, and all three of its earlier versions failed by
being **too narrow**), and the two directions of match-set error are not symmetric: too narrow is
**silent** (a file the suite reads can change while the gate reports a stable revision — the defect
this wrapper spent three versions on), while too wide is **loud and inert**. Only the first can ship
unnoticed, which is why the wrapper over-covers on purpose and says so here.

**What the number is for, kept separate from what it can bear.** Its job is to prove the mutants were
built from, and run against, *one* revision — not to be a citation for this document's own content.
For that narrower question the operative surface is smaller and **is** re-derivable: the mutant runs
read §2.5's table, the body's `warnings.append` sites, and the pin definitions in `tests/smoke.py`.
The hash below is taken over **the rows §2.5's table contributes to the census** — the operand set the
census actually counts — joined with newlines and sha256'd to its first 16 hex characters, and it reads
**61feebd6821b89b4**. Revision 5 hashed the *region* instead, and the difference is the whole lesson:
revision 5's own evasion table was added **into §2.5**, so the region grew 81 → 101 lines and the cited
value stopped reproducing against the file it ships beside, while the operand set — 16 rows, 22 sites,
the (11,4,1) split — was **identical on both sides**. The narrower hash covers exactly the claim, which
is why it survived the edit the wider one did not; unlike the fingerprint, anyone can recompute it
from the shipped file, on any machine, with no access to this checkout. It took **three** tries to
make the *fingerprint* honest: v1 covered `plugins/*/scripts` + `tests/` + `docs/`; v2 widened to the
whole plugin because the suite reads `SKILL.md`; both were *still* narrower than the harness, which
also reads `CHANGELOG.md`, `README.md`, `SECURITY.md`, `AGENTS.md`, `cm`, the marketplace manifest and
`.github/workflows/*.yml` — every one at the repo root, outside all three roots chosen. Each version
would have called a revision stable while a file the suite reads had changed, which is this cycle's own
defect wearing a build-tool costume: **a gate is only as wide as its match set.** The counts are
recorded because a mutation's RED count belongs to the **triple** (the restored code, the fixture, the
harness), so an inherited count is not evidence: the W group's own label had carried one ("flipped
A-only from 0 to 3, measured by review") and it was re-derived, not copied.

| tree | suite | reds |
| --- | --- | --- |
| **the shipping revision** | rc 0 — **1987 passed, 0 failed** | — |
| **`2b07ce3` (pre-fix revert)** | rc 1 — **the suite ABORTS** at `tests/smoke.py:3316` after **692 checks**, no totals line | *nothing is evaluated* — not the U group, not anything after it |
| **mutant A** — duty arm moved before the arc arm | rc 1 — 1986 passed, 1 failed | **G1** |
| **mutant B** — `judged` dropped from the panel block | rc 1 — 1985 passed, 2 failed | **G2, G3** |
| **mutant C** — the shipped key-count predicate restored | rc 1 — 1985 passed, 2 failed | **U5, P4** |
| **mutant D** — the severity wire dropped | rc 1 — 1986 passed, 1 failed | **W1** |
| **mutant E** — the panel draws `gaps[:2]` (**D1**) | rc 1 — 1986 passed, 1 failed | **the three-clause pin** — the check added for exactly this |

**These four mutants have now been rebuilt and re-run after every round of corrections, and the
diagonal has come back identical each time.** That is deliberate rather than incidental: a gate result
belongs to the revision it ran on, so instead of arguing that a docstring is inert, every mutant is
rebuilt from the corrected tree and the whole batch re-measured. The passing counts have moved with the
base at every round — 1986/1985/1985/1986 here, against 1983/1982/1982/1983 two revisions
ago — and **the reds have never moved at all**: A→G1, B→G2+G3, C→U5+P4, D→W1. The identity is the
stable part and the count is not, which is exactly the distinction `mutation-count-belongs-to-the-triple`
draws. It is also why this document keeps the earlier numbers rather than overwriting them: an
inherited count is not evidence, so the base it was measured against is kept beside it.

**Revision 8 re-ran the batch on the corrected tree and added three mutants of its own.** The base is
now **1989** — the two X checks — and the passing counts in the table above are kept rather than
overwritten, because each belongs to the tree it ran on. **Both batches below read
`d7320499b38e70d6` on both sides (202 files)**, so they describe one revision — the committed tree at
**`243331c`**, named for the same reason `7e756a2` is above, and this time the binding is **verified
rather than asserted**: `git archive 243331c` plus the eight gitignored maintainer artifacts re-hashes
to `d7320499b38e70d6` exactly, so that one commit recovers the run tree in full.

**The shipping revision differs from the run's by exactly one file: this one.** That is the
self-reference the earlier fingerprint names a section up, here turned into checkable arithmetic —
`git diff --stat 243331c HEAD` reads **one file, this document**, so the run's tree is recovered by
taking the tip and removing this document's revision-8 recording edits, and nothing else moved. (It
is checkable *because it is stated as a diff against a commit*; a bare number would not have been.)
A number written inside the set it covers can never equal the tree that carries the record, so the
**commit**, not the working tree, is what it is bound to; a reader re-deriving it checks out
`243331c` rather than the tip. This is also why the paragraph above says the value identifies the
*run*: keeping that true is the whole of the discipline, and the failure it prevents is a reader
measuring the tip, finding a different number, and concluding the batch record is false.

**The withdrawn fingerprint — no shipped-tree value is stated, and the omission is a correction.**
An earlier revision of this section read **`b8b43a5ed1f006f7`** here, described as the shipping tree.
It was measured, but on a working tree that was **still being edited**, in a state no commit froze —
so **no committed revision carries that number**, and a reader who checked out the tip to reproduce
it would find a different one and conclude the batch record was false. That is the exact failure the
paragraph above exists to prevent, arriving through the paragraph itself: the value was **testimony
wearing the grammar of a measurement**, and the credibility of the half that *was* verified (the
`243331c` binding) was doing the work the measurement should have done. The general form is worth
keeping: **a value read off a working tree is testimony even when the sentence carrying it looks
verified**, and no amount of correct reasoning beside it repairs that. The ordering that avoids it is
the one this cycle converged on — **commit the code → run the batch → record in a LATER commit** —
so the recorded value's referent is a commit, and the record can never be part of the set it
describes. What survives without a value is everything that mattered: the run's fingerprint, its
one-file distance from the tip, and the identity of the reds.

| tree | suite | reds |
| --- | --- | --- |
| **the shipping revision (revision 8)** | rc 0 — **1989 passed, 0 failed** | — |
| **A–E, re-run** | as in the table above, base moved 1987 → 1989 | unchanged: **A→G1 · B→G2+G3 · C→U5+P4 · D→W1 · E→the three-clause pin** |
| **mutant XA** — the uniqueness rule reverted (`search`), the bound kept | rc 1 — 1988 passed, 1 failed | **X1**, and nothing else |
| **mutant XB** — the bound reverted (`finditer` + `\d+`), uniqueness kept | rc 1 — 1988 passed, 1 failed | **X2**, and nothing else |
| **mutant XC** — both reverted (the committed helper) | rc 1 — **X1 reds, then the suite ABORTS** at `int()`; 705 printed checks (704 ✓ + 1 ✗), no totals line, 1284 never run | X1, then nothing after it is evaluated |

Each is a **single-property** revert — one edit against the shipping file, proven by whole-tree diff
— so the diagonal reads per property rather than per change, and the base has moved 1987 → 1989 while
**the reds still did not move at all**.

**And the batch earned its keep on the first run: it caught a coupling in X2 that reasoning had not.**
X2's first cut asserted the whole **pair** — `_duty_panel43(_so43) == (3, 3)` — which silently also
asserts the **row count**, and the row count is P5's property, not this check's. Under **mutant E**
(`gaps[:2]`) the real panel draws 3 rows' worth of subtitle over 2 rows, so X2 red alongside the
three-clause pin it has nothing to do with. That is precisely the repo's stated test for a check
measuring something other than what it claims — *"a check that reds under an unrelated mutant would be
measuring something other than what it claims"* — and it is the same failure mode §4.4 already
documents for the W group, arriving from the other direction. X2 now asserts the **subtitle number**
alone, the one operand this fixture isolates: the record's run contributes *no* match at all, so a
reading of `3` can only be the real panel's. Re-measured on the same fingerprint, **E reds exactly one
check again** and X2 keeps its own mutant.

**Mutant XB is the row worth reading twice.** It reds X2 *without aborting*, because the 4301-digit
banner **does** match `\d+` and the uniqueness rule then refuses it. The two defenses overlap: what
the bound buys is not that the suite survives — uniqueness already does that — but that the parse
**reads the real panel** instead of declining to read anything. Only **XC**, which removes both,
panics. Recorded because a future editor who removes the bound will watch X2 red for a reason its
label does not name, and that ambiguity is cheaper written down than rediscovered.

**Mutant E is a finding rather than a regression check, and it is listed here because its evidence is
this table.** The mutation makes `_duty_gaps_section` draw a *subset* of the rows its own subtitle
counts; the shipping suite passes it (rc 0, no reds) until the three-clause fixture added in revision
6, and reds the check written for it afterwards. **The check is therefore verified by the diagonal
rather than by the revert**, which is the same method the W group needed and for the same reason: a
check added by a fix cannot be shown to discriminate by a tree that predates the fix.

**Read the diagonal: every mutant reds exactly the check(s) written to catch it and nothing else.**
That is a *coverage* measurement, not merely a pin — it says no other check in the 1987 was
incidentally standing in for the property, and that the pin is not redundant. Neither of revision 6's
two new checks reds under any of the four regression mutants, which is the same statement for them: a
check that reds under an unrelated mutant would be measuring something other than what it claims.

**The revert row is why the injection column exists.** A pre-fix revert cannot verify *any* check in
this cycle, because it cannot reach one: the run dies at the first U check with an `AttributeError`
(the predicate does not exist on that tree). "Passes the pre-fix revert" therefore means **the
check's assertion is true of pre-fix code**, which for the two groups whose assertions a revert can
reach was measured by **driving the pre-fix renderer directly, not by running the suite**:

- **the P group** — all four fixtures (P1's gap, P2's applied-only, P3's partial trio, P4's F1
  evasion) against the `2b07ce3` renderer: **rc 0, no panel, on every one.** That is the evidence
  behind the P table's "exit 0, no panel → PIN", and it is the same fact as the audited defect: the
  record persisted clean and silent.
- **G2** — the same renderer on a gap record with **no** `--persist`: **rc 0, no panel**, so G2's
  assertion (an absence) holds of pre-fix code. **G3's** probe is the complement: no panel in
  *either* direction on pre-fix code, so its positive conjunct fails there — for the reason the
  group's label states, which is not the boundary it guards.

The complement is that **a guard whose defect is injected is verified more strongly than a pin**:
mutant A's test would be unobservable to any revert, since the ordering only matters when both arms
could fire, and a **6/6 arc has no arc arm for the duty arm to pre-empt** — which is also why mutant
A leaves the P group green.

**One measured consequence the W label does not claim.** Mutant D does not merely red W1; driving
it directly shows the advisory shape flipping **rc 0 → rc 3** *and losing its cue entirely* — the
exit-3 path has no duty cue (mutant D's `stderr` is empty where the shipped tree emits the advisory
cue). That is the display/exit desync of §5's io-error hole reached through a second door: a panel
on screen, a nonzero exit, and nothing telling the model why.

---

## 5. Risks and open items

**R1 — the gate newly exits 3 on a pass that previously exited 0.** That is the point, but it is a
user-visible behaviour change and gets an explicit `CHANGELOG` entry naming each clause. Structurally
mitigated: live-only plus present-but-empty means no legacy record and no seed/preview render can
trip it.

**R2 — A's 20/94 prevalence may mean the duty is decorative.** It is reported, never enforced, and
the reasoning is in this spec (§2.2) so a future reader can revisit it on fresh data rather than
re-deriving the argument. (The denominator moved with the fleet — §3.1.)

**R3 — the `judged` gate is the whole safety argument** (§3.3). If any other call site ever invokes
`duty_gaps`, the archive arm returns. The predicate's docstring states this; the display direction is
guarded by **G2 and G3** (the two `judged` checks), and the exit direction by the gate's position
inside `if persist_dir:`. *Revision 2 named "P13" here. No P13 ships in this cycle* — that name
belongs to v0.4.32 and v0.4.30, and a spec that cites a check by a number no cycle defines is the
same class of defect as a count no test reads.

**R4 — existing persist-path test records may carry a gap shape.** If a current pin's fixture has
`session: ""` or an empty `applied`, its expected exit changes from 0 to 3. That is the gate
working; the fixture is completed rather than the clause weakened, and any such occurrence is named
in the PR. Measured before implementation (§6).

**R5 — the panel's row rendering is new surface.** Its subtitle and rows are derived (§2.4); the
pin asserts exact substrings rather than a verdict scan, per the repo's
*exact-assertion-beats-verdict-scan* rule.

**Open, carried deliberately — three items, each pinned so it cannot change shape in silence:**

1. **The io-error hole** (H1's shape). The panel prints before `_persist` runs, so an unappendable
   cycle log leaves a fired panel on screen and returns **0**. A display/exit desync, reached
   through a new door — the arc arm's documented behaviour, inherited rather than introduced.
   §4.4 measures a **second** door into the same room: under mutant D the advisory shape exits **3**
   while the panel's own remedy line still reads *"ADVISORY, never gates"* — so it is the **panel and
   the exit** that disagree. *(Revision 9 — this sentence first read "and emits **no cue at all**, so
   the model sees a panel, a nonzero exit, and no reason", and that is **FALSE**: the mutation widens
   the arm's predicate, and the `dream_cue` call sits **inside** the widened block, so the gate cue
   fires — measured on `c48c762` vs mutant D, rc 0 with the advisory cue against rc 3 with the gate's
   "NOT over — the record carries an unmet duty: session". The real defect is sharper than the one
   claimed: the W1 pin exists to protect the advisory wording, and mutant D silently replaces it in
   the one shape where it matters. A further note on why the first claim was unfalsifiable as
   written — with `CM_DREAM_ARC` unset **neither** arm emits a cue, so under that reading the
   sentence would not have been mutant-D-specific at all.)*
2. **`achieved_recall`'s missing reader.** Outside SKILL prose it has **five** occurrences in the
   shipped plugin, re-derived 2026-09-17: **one** at the cut — its own `TypedDict` line
   (`memory_status.py:402`) — plus **four added by this cycle**, and every one of the four is a
   mention of the key's **name** (the trio constant, the remedy string, and two comments). No site
   reads its **value as a measurement**: the predicate asks only whether it is blank, and nothing
   renders or reports the number. `tests/simulate_accumulation.py` positively asserts the seed must
   *not* write it. Clause C enforces the trio **together**, which is SKILL's stated contract and the
   audited defect's actual shape; the missing reader is a separate defect, recorded in §6 — and it
   is worth noting that this cycle *added four mentions without adding a reader*, which is how a
   ghost field stays a ghost while looking increasingly referenced.
3. **The negative-tally loose reading** (§2.4). "Zero verification recorded" is loose on a negative
   tally — `{"confirmed": -1}` sums below zero and reads as a lazy-skip. The correct fix belongs at
   the predicate's `reason` string, which is stamped into **archived payloads**, so changing it
   re-writes history for records already on disk: out of this cycle's blast radius by the same
   archive-wide rule that chose the host (§3.3).

---

## 6. Recorded, not scheduled

- **`entries[].action` vs the row's own `reason`** (§2.6) — a model-phrase-vs-model-enum
  contradiction. Warn-only at best; it never touches `audit`.
- **`achieved_recall`'s missing reader** (§5) — a field the contract mandates, no consumer reads.
- **Cycle E's scope**, unchanged from the plan: the remediation note derived from data rather than
  `lever`; the ASCII registrar's `+N more blocked` parity with its HTML twin; the absent-vs-empty
  `session` default in the renderer; `Identity += domain_lifecycle` / `Audit −= window`; and the
  nested-pin coverage claim in `tests/smoke.py`, which names two carve-outs where exactly **seven**
  shapes are unpinned (`Entry` is enrolled; verified by enumerating the loop's rows against the
  module's TypedDicts).
- **`tests/dashboard_fixture.py`'s declaration drift** — its `identity` omits the always-emitted
  `domain_lifecycle`, its `audit` carries a `window` spelling no producer emits, and it has no
  `remediation`/`narration`/`maintenance`. Cycle D does **not** touch it: the fixture is clean under
  A/B/C (session filled, applied filled, no remediation block), and the drift is `Audit`/`Identity`
  declaration work that belongs with E4 where both sides move together.

---

## Amend ledger

**Revision 1** — first draft, written after the plan was approved and before implementation. Folds
the three findings that changed the design after approval, all surfaced to the user before this
revision was written:

| Finding | Change |
| --- | --- |
| The host was archive-wide (`_embed_integrity` calls `procedure_integrity` per archived cycle) | new `duty_gaps`, persist-gate only |
| Clause D's first-drafted form fired on the legitimate standing-justified seed (12 of its 13 fires) | guard added, then the clause dropped entirely on re-measurement |
| Exit 3 masked exit 4 | duty arm ordered after the arc arm |

Two further deltas from the approved plan, both reducing scope, recorded here rather than folded in
silently: `_procedure_integrity_section` is **not** changed (its hardcoded subtitle is true for its
own predicate — §2.4), and `tests/dashboard_fixture.py` is **not** changed (§6).

**Revision 2** — the spec re-read against the shipped code and the shipped harness, before
adversarial review. Four places where this document described the *draft* rather than the
*artifact*; all four were found by checking, not by re-reading:

| Finding | Change |
| --- | --- |
| §2.2 listed the row type as a five-field `NamedTuple`; the shipped `DutyClause` has **six** — `detail` was added so each clause speaks in its own words | §2.2 corrected, with the reason `detail` is a field rather than a constant |
| §2.4 showed a hand-drawn panel mock with a **shared closing remedy line**; the renderer prints each row's own remedy and has no shared line | replaced with **verbatim output** (ANSI-stripped). A mock in a design-of-record is a claim no test reads |
| §4 carried revision 1's numbering (P1–P13, including a P12 that was never shipped), and §3.3's "the correct guard is … P8 below" pointed at a *gate* pin | §4 restated as the thirteen shipped checks (U/P/G); §3.3's cross-reference corrected |
| **Two guards were labelled "passes pre-fix", and measurement says they do not.** Both assert the new panel's presence, so a pre-fix revert reds them for a reason that is not the property they guard | labels corrected to say how each guard *is* verified, and **§4.4 records the matrix** — the pre-fix revert plus two injected defects |

The fourth is the one worth keeping: a guard's printed label is not its condition, and the label is
what a later reader quotes as fact. The verification moved from *"revert the tree and see green"*,
which only an absence-shaped guard can pass, to **inject the defect the guard claims to catch** —
which is the only test that distinguishes a guard that works from a guard that is merely green.

**Revision 3** — the post-implementation pass. Every number in this document was re-derived from the
running system rather than carried, and the re-derivation found that most of revision 2's *claims*
were the same defect as the code it audits: **a description narrower than the thing described,
failing in the clean direction.** Twelve corrections:

| Finding | Change |
| --- | --- |
| §2.1 attributed the `procedure_integrity` tooltip to the `.adverse` block; the literal lives on the archive-list row's ⚠ badge, and `sections.js`'s two consumers interpolate `_integrity.reason` with **no** tooltip — so the consumption is **three surfaces in two files**, and the run-time literal is in a file none of the predicate's own callers appear in | §2.1 corrected, and it is the reason a consumer census over `grep -rn "procedure_integrity" plugins/ tests/` would have missed it |
| §2.2 documented a **key count** as the shipped predicate ("**the** checks … partially"), and reasoned about a corridor the key count actually has | §2.2 shows the shipped **union** (`present == 0 or filled == 3` abstains) and the two corridors each single-operand projection drops |
| §2.2 claimed the only producer of the trio writes all three, so a partial fill was unreachable | **False twice over** — `distill_scan --into` writes the `distill` block, and the seed's own comment says *"OMIT pruned/achieved_\* — the model fills them in Phase 5"*. Retired with the measurement (§2.6) |
| §2.3 asserted *"Exit 3 must never pre-empt exit 4"* as a bare claim about the code | **Measurably false**: the `procedure_integrity` arm sits five lines above the arc arm, so a record carrying a lazy-skip **and** a 4/6 arc exits 3. Replaced with the scoped rule ("this arm never pre-empts the arc arm") |
| §2.5's table said "value-contradiction checks" and carried ten rows — **the *disagree* subfamily presented as the whole** | restated as **sixteen rows over 22 sites** in three kinds (11 DISAGREE · 4 MEMBERSHIP · 1 ABSENT/DUP), and the family boundary in both the spec and the predicate's docstring now reads *"did the pass fill what it SEEDED"*, since family 3 is seeded-duty presence, **not presence in general**. **This correction was itself short a row** — see the row below, which is the same finding arriving twice |
| §2.6's prevalence table was measured on a population that has since moved — and §3.1's **own first re-run was superseded while this revision was being written**: 99 → 100 records, A 20 → 21, B 3 → 4, because a run of **this cycle's own test suite** appended to a scratch directory the census's glob admits. The plan's hand-excluded `deadbeef` row turns out to be **one of six** such directories | re-measured (drafted form **11** fires, **0** with the SJ guard, every key-emptiness form **0**); §3.1 names the scratch class, prints both columns, and keeps the mid-revision drift as the evidence for why a prevalence number is testimony |
| §4's pre-fix column claimed **all seven U checks fail pre-fix on an `AttributeError`**. Measured: the suite **aborts at `tests/smoke.py:3316` after 692 checks with no totals line** — so neither the U group nor anything after it is evaluated | §4 states the abort and gives the per-group method; §4.4's first row *is* the abort |
| §4 shipped **thirteen** checks and could not pin the advisory path, the severity wire, or the hole it intentionally leaves open | **twenty-one** — the W, H and C groups added, and then **P5** and **C3** forced by this revision's own two findings (the D1 mutation, and C1's one-directional blindness), and §4.4's matrix built from **five mutants rebuilt in one batch** on a fingerprint-verified frozen tree, because the W label's inherited count ("flipped A-only from 0 to 3, measured by review") is not evidence |
| §5 named a **P13** that no cycle defines (the name belongs to v0.4.32/v0.4.30) and a denominator the drift had already moved | R3 points at the two `judged` guards actually shipped; R2's denominator moves with §3.1; the open-items list gains the io-error hole, the warn-only arm's second door, and the negative-tally loose reading |
| §4.4's "every number was measured in one batch, on one revision" was an **assertion no artifact backed**. The wrapper that implements it needed **three** attempts to be honest — v1 fingerprinted `plugins/*/scripts`+`tests`+`docs`, v2 widened to the whole plugin for `SKILL.md`, and both still missed `CHANGELOG.md`/`README.md`/`AGENTS.md`/`cm`/the manifests/`.github/workflows` at the repo root, every one of which `smoke.py` reads | the fingerprint now covers the whole working tree (**201 files**), both sides of this run read **`34d0a07ce1d2ade7`**, and the batch **refuses to report** if they disagree. Each earlier version would have called a revision stable while a file the harness reads had changed — *a gate is only as wide as its match set* — so the three attempts are recorded rather than the last one alone |
| **C1 — the new census pin — fails quietly in one direction, like every gate this cycle audits.** Its SHAPE/VALUE split is a regex over the warning *text*, so a far-side clause worded in shape language evades the count | the limit is written into the pin's own comment and §4.4 rather than left to be rediscovered, together with the asymmetry that makes it tolerable (the opposite error is **loud**), and the note that a structural classifier was tried and rejected because `held_n is missing or below emitted holders` sits under an `isinstance(int)` too |
| **The revised §2.5 count was wrong too.** The correction that replaced *"two"* said **"fifteen"** and omitted `network.fact_holdings` holder resolution — a **MEMBERSHIP** row, again exactly the kind the framing hides. Found only by re-deriving with the **site** as the unit instead of the **warning text**: grouping by reading groups by what rows *look like*, while the body emits by *block* | the table gains a **`Sites` column** (22 total, so the count is auditable rather than asserted) and the 16th row; the docstring's row list is **completed and no longer claims body order** — it never had it, and a false ordering claim sends the next reader hunting a mismatch that is not there. **The census is now executed**: a smoke check AST-parses the function, splits SHAPE from VALUE sites, and reds if the body grows a far-side clause the docstring does not name — verified by injecting both the dropped row and an unlisted clause |
| **§4's parse pins rested on two claims their own code did not hold.** `_duty_panel43`'s comment asserted *"Both halves of the anchor are literals the record cannot write"* and *"a non-matching output is a FAIL here, never a ValueError out of the suite"* — the record **can** write a copy of the sentence into the banner above the panel, and a **matching** output was the one that raised | **twenty-three** — the two parse pins added, `finditer` + exactly-one (0 or 2+ matches both refuse) and `\d{1,4}` in place of `\d+`. Both findings came from review against the **parse** rather than the renderer it reads, which is why neither was visible from §4's own table; the measurements are in **Revision 8**, including the false universal left standing in Revision 7's `rsplit` row (*"the one span the panel itself writes"*) |

The through-line is the one this cycle exists to fix, one layer up: **a claim narrower than the
thing it describes fails in the clean direction.** A count that excludes the one row it cannot
explain reads as a census; a table that lists the *disagree* subfamily under a general heading reads
as the whole; a guard whose label says "passes pre-fix" reads as verified. None of these is a lie
anyone told — each is a description that stopped being true and kept being printed, which is exactly
what a duty rendering as an absent line is.

**Revision 4** — the adversarial pass, run against revision 3's shipped revision before
`/code-review`. Its findings arrived as claims about this document and were each re-measured before
being accepted — **six findings, four fixed and two recorded** — and three of the four were defects
**in C1's own coverage or labels**, which is the third time this cycle's error has recurred in the
sentence written to prevent it:

| Finding | Change |
| --- | --- |
| **C1's label named a surface no test read.** It claimed to red until the docstring *and §2.5's table* agreed, while the check parsed the docstring only | the check now parses §2.5's table out of the spec file; the label is true. Measured by editing one `Sites` value ⇒ **RED**, where before the injection was **unobservable** |
| **C1 was evaded by delegation.** A far-side clause moved into a helper the body calls was measured **GREEN** — a body walk cannot see a clause that lives somewhere else | the walk follows bare-name calls into this module's own functions; the same injection now ⇒ **RED** |
| **The docstring's own kind figure was wrong.** It said *"three MEMBERSHIP rows"* where the list holds four — in the very sentence listing what the "value-contradiction" framing had hidden from the last reader | corrected to *"the four MEMBERSHIP rows and the one ABSENT/DUP row"*, and the **11/4/1 split is now pinned**, from **both** surfaces (retag a docstring row ⇒ RED; retag a spec row ⇒ RED). An unpinned split is precisely how *"three"* survived as a wrong number |
| **The §4.4 fingerprint is testimony, not a derived number** — its match set deliberately includes gitignored maintainer-only artifacts, so no other clone can recompute it | §4.4 states the tier and the trade that produced it: over-covering is what makes the gate safe and what stops the value being re-derivable. Recorded, not narrowed — narrowing to *"what the suite reads"* would restore provenance by re-opening the **silent** direction all three earlier versions failed in |
| **Folding a far-side case into an EXISTING append evades C1** — reproduced GREEN | named as C1's open limit in the check's own label and comment and in §4, with what closing it would require and why the asymmetry makes the bound tolerable |

**On "reviewed to zero".** Four of the six were fixed; the two that were not are *recorded limits*
rather than open defects — the fingerprint's provenance tier (a property of the method, not a
failure of it) and C1's site-granularity hole (bounded, reproduced, and stated at the definition).
The pass also confirmed, by independent re-derivation, the figures the revision rests on: the
far-side census's 46 sites splitting 24 SHAPE / 22 VALUE onto 16 rows, with **no orphan row and no
uncovered site**, and all 24 SHAPE-classified sites genuinely family 1. Its closing verdict on the eight properties it
was asked to test: **six intact**, one holding only for the two injections claimed for it and no
more, and one holding only when scoped to the census delta — the branch's runtime changes being the
cycle's declared feature rather than an unremarked drift. (The pass's findings are reported here
without their own IDs on purpose: it labelled them `C1…C8`, which collides with this section's
census pin `C1`, and one label naming two things is how a reader ends up verifying the wrong one.)

**Revision 5** — the adversarial pass over revision 4, run against the shipped revision before
`/code-review` and asked to attack the *fix*, not the defect it fixes. **Both of the findings below were fixed**, and
both are the cycle's own subject arriving one layer up: **a thing that reports on itself
read as a report on something else.**

| Finding | Change |
| --- | --- |
| **The panel's subtitle counted CLAUSES and said FIELDS.** `len(gaps)` is fired clauses; clause C is three fields behind one clause — so the audited defect shape rendered **"1 seeded field"** above a row naming three fields, two blank. The panel whose whole job is to describe a gap was describing it with an operand its label did not name | the count is now the **rows drawn** and the wording says *duty* (§2.4). The shipped pin did not catch it and could not: its fixture fires clauses A+B, where clauses **==** fields, so the two operands are indistinguishable there. The trio fixture — the one shipped shape where they disagree — now pins the **relationship** (subtitle count == rows drawn) rather than two literals. Measured with the field-count operand restored: **the red is that check and exactly that check** — so the operand is covered by exactly one check and was covered by none. The pass total is not restated: it belongs to the triple (restored code, fixture, harness), and this document's own rule is that a count outliving any of the three is testimony wearing a measurement's clothes |
| **C1's delegation fix was short, and its own coverage claim was narrower than its walk.** "CLOSED" was true of the injection as written and false of the class: `body → _h1 → _h2 → append` was **GREEN** (depth 1 only), and a clause added by `warnings.extend([...])` was **GREEN** (only `.append` matched) | the walk is a **worklist fixpoint** over the call graph; a **whitelist** reports every write to `warnings` it cannot follow, as **C2**'s own count (§2.5, §4). Each closed form's own row in §2.5 carries the injection it was closed against and the operand that moves; the direction that is still GREEN — **a case folded into an *existing* `.append`** — remains open and is named at the definition rather than counted here |

**The census's fourth evasion was a retag that no operand could feel.** Retagging the docstring's
*legend* — the three `· KIND — gloss` lines that define the tokens every count in this document is
keyed on — moves **not one operand**, because the legend is excluded from `_rows` by a *prefix* test
and a retag from one KIND token to another preserves that prefix. The instrument therefore keeps
agreeing with itself while teaching a false definition: the docstring says *disagree* means
*membership*, and the row counts, the split and §2.5's table all still reconcile against each other.
That is what makes it worth tabling — the defect sits in the instrument's own vocabulary, the last
place a consistency check looks, which is the same reasoning that let a wrong count survive three
revisions of this document. The legend's token tuple is now returned and asserted in order.

**Consolidation, stated as a rule rather than a verdict.** Four of the FIVE evasions tabled in
§2.5 share a shape: **the injection was already passing when it was closed** — delegation at depth
2, the re-methoded mutation, the renamed parameter, and the laundered receiver. Each green was read
as *that injection is fine* rather than as *this instrument cannot see it*, which is the reading
that lets a form stay open for a whole cycle. **A green injection measures the injection, not the
instrument.** The fifth, the drifted legend, is the same failure located one level in — in the
instrument's own vocabulary rather than in its match set: a retag no operand can feel, because the
exclusion it must survive is a prefix test the retag preserves. The **three** remaining open limits
are stated at the definition: the SHAPE/VALUE classifier is a regex over warning text; the gloss
after a KIND token — on the legend and on §2.5's table alike — is read by nothing; and widening an
existing `.append` moves no count.

**Revision 6** — the adversarial pass over revision 5, run against the shipped revision before
`/code-review` and asked to attack the *fix*, plus the corrections its findings forced in the
revision-5 prose written to record the last set. **Every finding it confirmed is fixed below**, and
the recurring shape is again the cycle's own subject: **a relationship pinned only where its operands
cannot differ.**

**A note on attribution, because this document's own standard requires it.** The pass reported its
findings and was then asked a set of follow-up questions — the full parse answer, an injection list,
and a final count. **It did not return them**: it ran past the end of the revision, and the answers
never arrived. So the rows below are attributed **by row** rather than by a count of what the pass
measured, and where a number would have been testimony about the pass, this revision states the row
instead. That is not a weakening of the standard — it is the standard, applied to a reviewer: *a
count of a pass's own work outlives the pass*, which is the same reason this document re-derives its
own numbers rather than carrying them.

| Finding | Change |
| --- | --- |
| **The census constrained 22 of 46 sites, and the unconstrained 24 were the silent direction.** C1 asserted the VALUE bucket and said nothing about the rest of the write surface, so a clause worded as a *shape* check — `warnings.append("ooze is not a list")` — landed in the SHAPE bucket, which **no assertion read**. Measured GREEN, four ways, by the pass; reproduced here by injecting the same clause. This is the pin built to close four evasions missing a fifth, found not by an injection aimed at it but by **counting the surface the pin does not enumerate** | the census returns **`len(_all)` — the whole append surface, 46 — as a ninth operand**, and it is pinned by **its own `check(...)`, not as a C1 conjunct**. Measured in four directions: a VALUE-worded addition moves `value` **and** the surface (both red); a **SHAPE**-worded addition moves `value` not at all and now **reds the surface alone** — the silent direction is loud; retagging a value site into shape wording moves `value` 22 → 21 and leaves the surface at 46 (**C1 reds alone**). So **C1 owns the retag, the surface owns the addition**, and the two pins partition the directions with nothing left silent. That the surface is computed *inside* the census rather than re-walked is deliberate: a second walk is a second match set, and this cycle has spent three revisions on what happens when two of those disagree |
| **D1 — the panel counted CLAUSES where it drew ROWS, and every fixture fired at most two.** `for g in gaps[:2]:` injected into `_duty_gaps_section` **passes the whole suite** (measured on a tar copy: rc 0, no reds). The user-visible effect is the fixed defect reappearing inside its own fix: the panel renders *"3 seeded duties the pass left unfilled"* above **two** rows, the vanished row being the **remediation trio — the F1 clause itself** — and the exit stays **3**, so nothing signals it. *Cause:* the six fixtures fire A+B, A, B, trio, trio, A+B, so the relationship `subtitle == rows drawn` is only ever evaluated where `clauses <= 2`; the one assertion that reads a row count belongs to the trio fixture, which fires **one** clause | a seventh fixture firing **all three** clauses, with its own marker timestamp (`_already_logged` keys on the (commit, timestamp) pair, so reusing the trio's makes `_persist` return `"duplicate"`) and its own check. The docstring at `:379-388` **already promised** the count "is the number of rows drawn (a reader can check it by counting them)" — so this pins a claim that was already written, not a new one. The author had reasoned carefully about the *twin* pair (rows vs fields, and chose the trio fixture to separate them); `len(gaps)` vs *rows the loop draws* is a second, orthogonal pair no ≤2-clause fixture can reach |
| **`_duty_gaps_section`'s docstring stated a false universal.** *"Every visible word comes from the fired ROW (`label`, `detail`, `remedy`) — never a shared literal."* The panel's frame is shared by construction: the header `⚠ RECORD DUTY GAPS`, the subtitle template, the `→` prefix and `_rule()` | scoped to what the sentence is *about*: every word that **names** the gap comes from the row; the frame is shared, **which is what makes the per-row text the only place a generic sentence could hide**. Recorded rather than silently corrected because it is the same substitution this document audits — a claim about the part that varies, written as a claim about the whole — and the same audit found it twice more in the same hour (§2.5's drifting row, the limits paragraph) |
| **The open limit was stated too narrowly, in both surfaces.** Both this document and the pin's comment said the limit is *"folding a new case into an existing `.append` moves nothing."* Measured, the class is wider: **any count-preserving change to a site's condition or activation** — a folded predicate, a widened guard, a conditionalised append, a swapped condition | restated as **the census pins the site SET and the wording buckets; it does not pin a site's CONDITION**, with the measured pair that fixes the boundary: emptying the preflight loop's iterable (`("fails","warns")` → `()`, site count unmoved) **REDS** — *`preflight validator: preflight.fails/warns must be lists`*, a **behavioural** check predating this cycle — while folding a third key into it does not. So the census is blind to guard changes and the *suite* is blind only where no fixture exercises the affected case. The absolute ("the guards around those sites are not pinned at all") was **measured false** and is not imported |
| **The third open limit is the one nothing reads.** The census keys every count on KIND tokens, and the **gloss after a token** — on the docstring's legend lines and on §2.5's prose column alike — is read by nothing. Measured GREEN on both surfaces | named at the definition beside the other two, and the count of open limits corrected **two → three** in the two places that stated it (§2.5 and §5), so the document stops contradicting its own section. The retag moves no operand for a structural reason — the exclusion it must survive is a *prefix* test, which any token-to-token retag preserves — so the limit is one the census's own arithmetic cannot reach |
| **§2.5's attribution put a claim about the PASS where every neighbouring sentence is about the WALK.** *"The adversarial pass measured five evasions of the walk — four now closed, one open."* Read in place, that sentence attributes the closure of four forms to one reviewer's afternoon; and the number is testimony about a pass that a later reader cannot check | rewritten **by row rather than by count**: the table now carries each form's *injection*, the *operands it moves*, and the *branch that closes it* — each checkable against the code. The discovery stories are **dropped rather than re-attributed**, and by this document's own rule: a count of a pass's own work outlives the pass, and a story about an afternoon outlives the afternoon the same way. This is the fingerprint's tier correction one layer in, and it is the same reason this revision attributes its own findings by row (see the note above) |
| **The whitelist covers more than its own limit statement claimed.** The limit was written as though only the one followable form is covered | measured: `warnings.clear()` and `warnings *= 2` — two write forms outside the enumerated twelve — are **both caught** (`escapes` moves). The whitelist is closed against everything that is *not* the single followable form, and the two are cited as evidence. A limit statement that under-states its instrument sends the next reader to re-derive a bound that does not hold |
| **§4.4's counts were wrong, and `§3.1` was cited twice inside §4.4 for things §3.1 does not contain.** The tier paragraph read *"of the 201 files, 192 are tracked … and 9 are not … and one is this spec"*, cited as living in **§3.1** — and the paragraph above it placed the fingerprint in *"§3.1's third tier"*. §3.1 is **the population census**: it counts records, defines no tiers, and prints no file counts. A reorganisation moved both and updated neither reference | the dangling section cite is gone and the tier claim is stated where it is made rather than pointed at. On the counts: the spec is **tracked**, so it belongs in the tracked column — −1 untracked, +1 tracked, which is the whole of the first correction ("201 / 193 / 8"), and it touched only the split, leaving the total as the paragraph had it. Re-measured from the shipping tree and cross-checked against `git archive` at the branch tip against the untracked enumeration, the wrapper's own match set is **202 files — 194 tracked, 8 not** — one larger than that correction on both the total and the tracked row, with the 8 matching their prose exactly. §4.4 carries those values, derived by the same wrapper that produces the fingerprint, and **this row deliberately does not restate them**: a number copied into a ledger outlives the method that produced it, which is this row's own defect one degree up. The earlier figures — this row's two pairs, and the **201** in **Revision 3**'s fingerprint row above — are recorded as **superseded, not wrong**: the tree they described is not recoverable from this repo's history (the branch's first commits were reconstituted), so the difference between any of them and the measurement is **unattributable**, and calling it either a miscount or a changed tree would be a claim with no artifact behind it — the defect §4.4 exists to prevent. The provenance conclusion is unaffected, which is why the numbers are corrected rather than the paragraph rewritten |
| **§4.4's cited hash over-covered, and the edit proved it.** *"§2.5's region … hashes to `3b06c6344ae4f72a` on both sides"* — revision 5 added the evasion table **into §2.5**, which is the hashed region, so the value stopped reproducing against the file it ships beside (101 lines at `d9c52a3` — the revision the finding is bound to — and 81 at the pre-addition revision, which is not in this branch's history and so is **UNVERIFIABLE rather than wrong**. Neither is stated as a *"now"*: measured across the branch, the region runs 101 → 106 → 114 lines, which is why this row names commits rather than a present tense). The **claim** survived, because it was never about the region's bytes: the census reads the same 16 rows, 22 sites and (11,4,1) split from both revisions | the hash is taken over the **operand set** — the rows the census actually counts — and the method is stated so a reader can recompute it (join the counted rows, sha256, first 16 hex). The narrower hash is the **right width**: it covers exactly the claim, and it survived the edit the wider one did not. The third time this cycle has found a *match set wider than the thing it is evidence for* — the fingerprint's own three attempts are the first two |
| **The F1 measurement was stale twice over.** §2.4 and the revision-5 ledger both quoted **1983 passed / 1 failed**; on the frozen revision it is **1984 / 1**, because C2 was added after that run | both re-derived, and the count now carries the revision it belongs to. This is `mutation-count-belongs-to-the-triple` arriving in this document's own prose — the count belongs to the restored code, the fixture and the harness together, so a number that outlives any of the three is testimony wearing a measurement's clothes |

**On "reviewed to zero", stated the same way as last time.** The pass's findings were fixed where they
were defects and **recorded as bounded limits** where they are properties of the method; the
distinction is not a softening but the same one Revision 4 drew, and the three limits are now named
at the definition rather than left for the next reader to rediscover. What the revision adds is not a
claim that the instrument is complete — it is **the count of what it cannot see, printed beside it.**

**And the diagonal was rebuilt once more, because a gate result belongs to the revision it ran on.**
Four mutants rebuilt from the shipping tree (each differing from it by exactly one edit), plus a
fifth for D1 itself, whose suite result *is* the finding. Every passed count is **+3** over the
previous batch — the base moved 1984 → 1987 (+1 C2 already in the frozen tree, +2 for the surface
pin and D1's fixture) — and the **identities did not move at all**: A reds G1, B reds G2+G3, C reds
U5+P4, D reds W1. Neither new check reds under any of the four, which is the coverage measurement:
neither is incidentally standing in for a property another pin owns.

---

**Revision 7** — the adversarial pass over revision 6, and the **revision-binding correction it
forced on this document's own reading of it.** One of the pass's findings was already closed before
the pass reported it, and the instrument that says so is a hash.

**Every finding is bound to the revision it was measured on, and this one was measured on
`d9c52a3`.** The pass cited five blob hashes; all five resolve to `d9c52a3`, and the branch tip is
three commits past it:

```
6931b1a  docs(spec): section 4.4 cites the batch taken on the shipping tree
f0320db  docs(counts): this cycle ships twenty-one checks, not nineteen
0299ff8  docs(spec): revision 6 — the review's findings, and the two pins it forced   <- after d9c52a3
d9c52a3  feat(duty): a seeded duty left unfilled now fails the persist gate (0.4.33)  <- the pass's revision
```

Two of those three touch `tests/smoke.py`, and one of those also touches
`render_dashboard.py` — the two files the pass's findings are *about*. So the findings below are
recorded against `d9c52a3` and re-measured against the tip, and the difference between the two is
the first row. This is `a-green-gate-is-green-on-the-revision-it-ran` arriving in the review loop
itself: **a finding, like a gate, is a statement about one tree.**

| Finding | Change |
| --- | --- |
| **The forged slice already raises at the tip — and the pass is right about the revision it named.** The pass reported that the subtitle pin's `split("RECORD DUTY GAPS", 1)[1]` raises `ValueError` on a forged output | **true at `d9c52a3`, false at the tip.** The guard is `int(_tok43) if _tok43.isdigit() else -1`, added by `0299ff8` — a commit that landed *after* `d9c52a3` and *before* the report. Verified both ways against the code rather than resolved by seniority: the claim was re-measured on the revision the pass named, and it holds there. **A stale finding is not a wrong one**; this row exists so the next reader does not "fix" a defect that is already gone |
| **…and `rsplit` is not the repair it was proposed as.** The same report proposed `rsplit("RECORD DUTY GAPS", 1)` as the fix | the proposal **relocates** the forgery instead of removing it. `rsplit` reads the *last* occurrence, and the record-controlled region **below** the panel — `rigor.phase`, `override_reason`, the verified names, `CHANGES` — is denser than the banner above it. The shipped repair is a regex over the **header sentence**, which is the one span the panel itself writes. *Totality and aim are independent properties of a parse*: a slice can be provably total under a correct aim and still be anchored to the wrong text |
| **The census could not see a write made through a second name for the list.** `_w = warnings; _w.append(...)` was invisible to **both** counts: the append count filtered on `n.func.value.id == "warnings"`, and the escape count enumerated `Call` / `AugAssign` / `Store-Subscript` only | **confirmed at the tip by injection rather than accepted from the report**: the clause added through a second name leaves **nine operands unmoved** and the whole suite green — **`1987 passed, 0 failed`**. The escape count is now a **whitelist over reference POSITIONS** instead of an enumeration of write forms (`_refs` + `_followable`), because the enumeration was answering a question that has no closed form — "every construct that binds a name" — while positions do. Measured on **seventeen reference forms against both revisions**: nine read `0 → 1` (a `for` target, a `for` iterable, a walrus, a dict value, a `with … as`, a default argument, a load-Subscript, a comprehension source, a unary `not`), eight read `1 → 1`, and the unmodified module reads `0 → 0` — the control. The nine are not all writes: two are the harness's own **benign reads** (`if not warnings:`, `for _w in warnings:`) and one of the eight is the pre-existing `warnings.count` over-coverage §2.5 records. Both facts are stated rather than folded into a single count. §2.5's laundering row carries the measurement in full |

**Why the count of open limits did not move, and why that is not a bookkeeping convenience.** The
census was widened a **fifth** time, and the number of its *open* limits is still **three**. The
laundering was a **miss** — a write the instrument could not name — and a miss is *closable*, which
is what happened. The three that remain are limits of the **method** rather than holes in a match
set: no counting scheme can see a case folded into an existing `.append`; the SHAPE/VALUE classifier
is a regex over warning text; and the gloss after a KIND token is read by nothing. **A miss is fixed;
a limit is named.** Conflating the two is how *"reviewed to zero"* becomes a claim about arithmetic
rather than a claim about a method — and the five-row table in §2.5 now states, for each form, which
of the two it was.

**Revision 8** — the review's second pass, and the two findings are this document's own subject one
layer further in: **the parse reads a report and never asks whether it is the report it asked for.**
Both are against `tests/smoke.py` alone; the renderer is not implicated, and no defect ships in
`plugins/`.

Revision 7's row above ends: *"The shipped repair is a regex over the header sentence, which is the
one span the panel itself writes."* The first clause is true; the second is the false universal
hiding in it. The panel is the only **renderer** of that sentence, and the record can still write a
**copy** — `project` and `session` are printed verbatim into a banner *above* the panel. So narrowing
the anchor from the marker to the whole sentence **narrowed what matches and did not relocate the
anchor**: `re.search` is first-match-wins either way. Specificity and position are independent
properties of an anchor, and the prior revision improved one while claiming both.

| Finding | Change |
| --- | --- |
| **The anchor is record-writable, so first-match-wins reads the banner.** `project = "⚠ RECORD DUTY GAPS · 3 seeded duties the pass left unfilled" + "  · → e1 / e2 / e3"` reproduces the panel's sentence verbatim and self-consistently | **confirmed by injection, and it defeats the shipped parse.** The forged window carries the same number and the same three `→ ` rows, so `search` returns **(3, 3)** — *the true pair for a healthy panel*, which is exactly why the defeat is silent. Measured on a tree whose row loop is truncated to `gaps[:2]`: the real panel renders 3 over 2 (a FAIL) and the same forgery still returns (3, 3) — the pin reports success for a panel it never saw, and the defect ships. Uniqueness is now a **condition**, not an assumption: `finditer`, and 0 or 2+ matches both return `(-1, -1)` |
| **The capture was unbounded, so a record could abort the suite.** CPython refuses `int()` past 4300 digits, so `(\d+)` turned a forged banner into a suite ERROR instead of a failed check | **confirmed by independent reproduction.** `project = "⚠ RECORD DUTY GAPS · " + "9" * 4301 + " seeded duties the pass left unfilled"` raises `ValueError` at the parse — **705 printed checks (704 ✓ + 1 ✗), no totals line, EXIT 1, and 1284 checks never ran.** `\d{1,4}` refuses the run as a *match* instead, so the real panel is the only match. The bound cannot reject a legitimate render: the number is the rows drawn and `_DUTY_CLAUSES` is three |

**The two defenses overlap, and the measurement is narrower than it first looks.** Reverting the
bound *alone* reds the totality pin **without aborting** — the 4301-digit banner then matches, and the
uniqueness rule refuses it, `(-1, -1)` rather than a panic. So uniqueness alone also prevents the
abort; what the bound buys is that the parse **reads the real panel** rather than declining to read
anything. Only reverting **both** panics. Stated here because a future editor who removes the bound
will watch that check red for a reason its label does not name.

**What the new rule costs, stated rather than left to be found.** A record whose `project` carries the
sentence verbatim now makes the parse return `(-1, -1)`, i.e. it reds these pins. That is the
deliberate direction — **loud, not silent** — and it is the same trade the prior revision made when it
chose "a non-matching output is a FAIL" over a fallback. The alternative, `rsplit`, was rejected on
Revision 7's own reasoning: the record-controlled region **below** the panel is denser than the banner
above it, so relocating an anchor trades one writable window for a worse one.

**And the pin that carries these fixtures states its own limit.** `_duty_three_p`'s forgery
(`"RECORD DUTY GAPS · 7 → forged"`) carries neither the `⚠` glyph nor the sentence's tail, so the
shipped parse **cannot match it at all** — measured, one anchored match in that output against two
for the bare marker. Revision 6 described it as *"the FORGERY the parse must survive"*, which
overstated it: it is a **regression guard** against reverting to the marker-anchored first cut, and
that is the whole of what it proves about the parse. The forgery that defeats a sentence-anchored
parse is pinned by the two checks above, where it can be measured.

**The count is now twenty-three** — the twenty-one of Revision 7 plus the two parse pins, which are
`PIN`s in their own right rather than guards: the uniqueness check reds on the pre-fix helper, and the
totality check cannot even be evaluated there, because the call raises.

**Revision 9** — the `/code-review` round over Revision 8's shipped revision. Eight corrections over
three files, and the first is the **only one that changes behaviour**: every other row is a sentence
that had stopped being true, which is this document's own subject arriving at last against the one
surface it had not yet audited — **its own new comments, and the code comment written in Revision 7.**

| Finding | Change |
| --- | --- |
| **The escape census could not close the class it claimed to watch.** Revision 7's fix listed **five WRITE FORMS** (`Call`/`AugAssign`/`Store-Subscript`/binding assignments/`del`). A reference outside that list is not merely *unfollowed* — it is **uncollected**, so it contributes nothing to any operand: measured, nine forms (`for _w in (warnings,)`, `for _w in warnings`, `(_w := warnings)`, `{1: warnings}`, `with … as warnings`, `def f(_p=warnings)`, `warnings[:]`, a comprehension source, `not warnings`) left every count unmoved with **all nine census checks green at once** | **set-complement inversion — the fix is smaller than the thing it fixes.** `_mutations` (5 branches), `_unrecognised` and `_binds_the_list` (6 branches) are **deleted**; in their place `_refs` collects every `Name(id="warnings")` in the closure and `_followable` answers one bounded question — *is this reference in one of the four positions the census can follow?* The question is answerable where "enumerate every construct that binds a name" is not, and the inversion makes an unanticipated construct a member of the **red** rather than a member of **nothing** (§2.5, C2) |
| The inversion's **cost** would otherwise be discovered later as a defect | **measured and stated**: on **seventeen reference forms against both revisions**, nine read `escapes` `0 → 1`, eight read `1 → 1`, and the unmodified module reads `0 → 0`. Two of the nine are the harness's own **benign reads** (`if not warnings:`, `for _w in warnings:`) and a bare Subscript such as `warnings[0]` joins them — all three previously read `0`. That is the safe direction, and it is the price of the set being bounded at all. One of the eight is the same `warnings.count` **pre-existing** over-coverage Revision 7 already records, restated here so it is not attributed to the inversion |
| **The `b8b43a5ed1f006f7` shipped-tree fingerprint was withdrawn.** It was measured on a working tree that was **still being edited**, so no committed revision carried it — the value was testimony wearing the grammar of a measurement, and the credibility of the verified half (`243331c`) was doing the work the measurement should have done | the value is **gone**; what remains is checkable arithmetic — `git diff --stat 243331c HEAD` reads **one file, this document** — plus the lesson and the ordering that prevents it: **commit the code → run the batch → record in a later commit.** §4.4 carries the correction in full (*a value read off a working tree is testimony even when the sentence carrying it looks verified*) |
| **Revision 7's ordering rationale named a witness that cannot exhibit the defect.** *"a record with `session: ""` and a 4/6 arc would exit 3"* — but the arm gates on `severity == "alert"` and clause A is `warn`, so a session-only gap exits **4** under *either* order, measured on both trees. The design's intent was written as a property of the code | the witness is now an **alert** clause (`rigor.applied: ""`), in both the spec and the comment at the arm. This is the same slip this document records against its own revision 3, arriving a sixth time |
| **§5 R1's *"emits no cue at all"* was false.** Under mutant D a cue **is** emitted: the mutation widens the arm's predicate and the `dream_cue` call sits inside the widened block, so the **gate** cue fires where the advisory one should | replaced with the genuine desync — the **panel's own remedy line** still reads *"ADVISORY, never gates"* while the exit gates. The real defect is sharper than the claim: the W1 pin exists to protect the advisory wording, and mutant D silently replaces it in the one shape where it matters |
| **The exit-3 prose described the arm as broader than it is.** The docstrings said *"an unfilled record duty"* where the arm gates only on `severity == "alert"` — a superset, so a session-only gap exits **0** with a yellow panel | qualified to **"gating"** at the eight prose sites (`AGENTS.md`, `CHANGELOG.md`, `SKILL.md` ×3, `harness-map.md` ×2), matching the word `README.md` already used. No code change: `duty_gaps` is unchanged and clause A remains reported-never-enforced |
| **`duty_gaps`'s *"never raises"* was unqualified.** A `dict`/`str` **subclass** whose `__contains__`/`get`/`strip` raises takes the predicate down (3 of 23 hostile inputs) | qualified to **"never raises on JSON-reachable input"**, with the bound shown to be **inherited rather than new** — `arc_completeness` and `procedure_integrity` raise on the identical three, and none survives `json.loads`, the only way a record reaches either call site |
| **Three prose figures and two snapshot words.** *"704 checks printed"* (three sites, plus `CHANGELOG.md`) undercounts by one — the harness prints **704 ✓ + 1 ✗ = 705**; *"all five duty fixtures"* was true of the proposition but wrong about the file, which holds **nine** `v0433-duty-*` fixtures and calls the parse on four; *"the ONE shipped fixture where that operand is observable"* was false (**two** observation sites, one *reading* check); *"holds against a reworded subtitle"* was false on both halves; and the ledger's *"101 lines now"* named a present tense that the region has outgrown twice | re-derived and corrected, each with the measurement beside it. The *"reworded subtitle"* repair is the useful one: the pin **reds** on a reword, because the parse is anchored on that exact text — rewording and re-anchoring move together, which is the premise rather than a property |

**Nothing in `plugins/` changes behaviour in this revision except the prose qualifiers.** The
mechanism correction is confined to `tests/smoke.py`'s census; the renderer and the predicate are
unchanged, and the suite reads **1989 passed, 0 failed** at the corrected tip.

The through-line, one layer further in than Revision 8's: **a guard is only as wide as the set it
collects, and a set is only as honest as its ability to say what it cannot see.** Revision 7 made the
escape count *look* at more write forms while the class it was trying to close had no closed form at
all; the bounded question — *which positions can I follow?* — is what makes the red possible to state,
and stating the red is what lets the cost be measured instead of discovered.
