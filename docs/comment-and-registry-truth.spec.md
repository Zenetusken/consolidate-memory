# Comment truth, and a registry that contradicts its own rule

**PR C — v0.4.38.** A two-item hygiene PR, chartered by the user after PR B was frozen. Its subjects
are two **comments**: one that is not a sentence, and one that states a rule the list it sits inside
does not implement — in a file carrying two further comments on that same rule, **eleven lines above
it and five lines below**: the upper one over-claims about a single entry, the lower is accurate.

> **Reading note — this document carries NO `file:line` coordinate, and the reason is NARROWER than
> "neither subject exists at a revision".** That was the first draft of this note and it was **false**;
> the measurement is what corrected it. The truth is asymmetric:
>
> - **Subject 1** (the splice) is PR A's own new code. MEASURED: it is **absent at `fbfe07e`** and
>   **present from `475af7b` onward** — A's own v0.4.36 commit, and an ancestor of the head — so a
>   coordinate *can* name it. The first draft of this note said it "exists at **no committed
>   revision**"; that was true when written and false from `475af7b`, which is this cycle's
>   revision-binding lesson arriving in a reading note.
> - **Subject 2** (the registry comments) is **pre-existing** — present at the base revision at the
>   *same line number* the live tree shows, with the uncommitted diff touching it **0 times**. A
>   coordinate for it would resolve today.
>
> The document nonetheless cites by **greppable anchor** throughout — but after the correction the
> reason is a **choice, not a constraint**, and the difference is stated because the first draft got it
> wrong. A document carrying even one `file:line` must declare the revision its coordinates resolve on
> (the rule PR B's citation gate enforces), and binding to `fbfe07e` would print a revision beneath a
> document half of which that revision cannot show. **But `fbfe07e` is not the only base available: both
> subjects exist at `475af7b` and at the head, so a base *could* be declared.** What remains is the
> **house rule** — greppable anchors, never `file:line` — which this document follows on its own terms.
> The first draft's "cannot honestly declare a base" was true when written and dissolved at `475af7b`;
> ⚠ **and it was over-scoped even while it was true.** The rule it invokes governs **coordinate
> resolution** — a declared revision says *these coordinates resolve here* — and imposes nothing about a
> document's subject matter. The draft strengthened it into *every subject this document discusses must
> exist at that revision*, found one that did not, and concluded no base could be declared. **The
> convention survives, its stated necessity does not** — and the necessity was never one the rule
> supplied.
>
> ⚠ **"Throughout" is qualified by one form, and the qualifier is checked rather than promised.** The
> document cites the registry by bare ranges (`:73-74`, `:85-86`, `:91-92`) — line references with **no
> filename**, which resolve only against the code block quoted in place. They are not coordinates the
> rule speaks about, and the rule's own matchers say so: `_CITE47` requires a filename **carrying an
> extension** before the `:`, so it returns **0** for this document — as do `_CANON47` and the bare-form
> `_BARE47`. Measured against the matchers rather than inferred from a clean run: the two halves agree
> because the patterns cannot see the form this document uses. A bare range cannot slide against a
> revision — it names a position in a block the reader has in front of them. ⚠ **No count is stated, and
> that is deliberate**: a census of the document's own bare ranges is falsified by the next edit that
> names one, so any number here is accurate at its revision and stale at the next. The **form** is the
> claim; the tally is not.
>
> **This is a design-of-record, not a report.** The defects below are measured; the repairs are
> prospective.

---

## Why this is a separate PR rather than an edit to A or B

The splice is **in code PR A introduces**. Repairing it inside PR A would re-open gates already
measured green on a frozen revision — a gate result belongs to the revision it ran on, so an edit
re-opens it. The registry comments are not PR A's or PR B's, but the **file** is PR B's, so editing it
now re-opens PR B's gate for the same reason.

⚠ **The sequencing has an operational consequence, and its precondition has MOVED: the repairs below
must NOT be applied on any branch into which A and B have not merged.** The first draft said "while A
and B are uncommitted"; measured, both are now committed on their own branches and neither is merged,
so that wording describes a condition already satisfied — an expired rule that still reads as a live
one. They touch files those PRs own, and an undifferentiated `git add` would fold a
v0.4.38 change into a v0.4.36 or v0.4.37 commit — a release whose CHANGELOG does not describe it. There
is a sharper reason for the splice: repairing it early would make **PR C's own item 1 a change that
never shipped as a change**, since the repaired comment would ride PR A. The repair belongs to the
release that reports it.

---

## Defect 1 — the comment that is not a sentence

**The defect, verbatim.** The comment above the cwd-template construction in `render_html.py`'s
source-1 branch reads, across two of its lines:

```
# and the two fields no row carries (`registry_state`, `plugin_data_dir`), which is why
# ...which is why the rendered identity is cwd-invariant. The template still has to be
```

The first line's `, which is why` is the clause the sentence **needs** — its consequent is the head of
the second line, which is what a wrap is. Calling it *dangling* because a **line** ends there is a verdict
read off the wrong instrument, and it drives the wrong repair (below). The **duplicate** is the second
line's `...which is why `: an ellipsis-led re-opening of a clause the previous line already began. It is
not a typo — every word is a word the sentence wants. It is **two overlapping copies of one clause**,
which is why reading either line alone looks almost right.

**What it is.** A splice artifact: an earlier revision of the second line began the sentence, a later
edit rewrote the pair and reflowed them, and the tail of the first line and the head of the second were
both left behind.

MEASURED by a read that does not expire: **`475af7b` is the commit that added this clause** — A's own
(`v0.4.36 — RC-5: a masthead stops being read from the room`) — while `fbfe07e` does not contain it and
the head carries it at the same two lines. This is PR A's code, confirmed rather than assumed, which is
what makes the sequencing rule above apply. ⚠ The first draft measured this as *"2 of 2 added lines in
the uncommitted diff"* — true when taken, and meaningless once A committed. **`git log -S` is the
durable form of the same claim**: a working-tree diff answers about *now*, and a history read answers
about the tree. ⚠ **That retired reading was file-scoped, and the scope is load-bearing**: the same
pattern over the same range **unscoped** returns **25** added lines over `fbfe07e..475af7b` — A's
**38** over `fbfe07e..9585b10`, while the **scoped** arm reads **2** at both and
**1** at this branch's head, where item 1 has deleted exactly the copy. A re-runner who drops the
scope and lands on a nearby range concludes the measurement was wrong rather than that it was
narrow; one who keeps the scope but reads the head finds item 1's own observable rather than a
drift.

**The intended sentence**, recoverable from the parts: the template supplies only the environment and
the two fields no row carries, **and that is why** the rendered identity is cwd-invariant.

**The repair** deletes the duplicate and nothing else: drop the `...` **and** the copied
`which is why ` from the head of the second line, leaving the first line's `, which is why` — the one
whose consequent is the next line — in place, so the two lines read as the single continuous sentence
they were always meant to be.

⚠ **An earlier draft of this repair said to drop the first line's `which is why` as well, and that
reading is this item's own defect one layer down.** With both copies gone the lines read *"…the two
fields no row carries (`registry_state`, `plugin_data_dir`)"* followed by *"the rendered identity is
cwd-invariant"* — a noun phrase and an unconjoined clause, which is the consequent-less clause this item
exists to remove. **The counterexample is the intended sentence in the paragraph directly above**, which
requires a connective that repair deletes; a repair that cannot produce the sentence its own section
reconstructs is not that sentence's repair. It is Correction B's failure shape — *the over-claim
surviving its own repair, arriving in the repair proposal* — recurring in the other item, and it is
recorded rather than quietly fixed because the near-miss is the finding.

**No claim changes** — the surviving claim is already there and is true: source 1 recovers the identity
from the registry row, so the cwd template's contribution cannot move it.

⚠ **This defect is UNREACHABLE BY ANY CHECK, and the document says so rather than implying a pin
exists.** Nothing here verifies that a comment parses as prose, and nothing sensibly could: a grammar
check over comment text would be a new instrument with its own false-positive rate, aimed at a class of
defect observed **once**. By this repo's own rule a check that cannot fail on pre-fix code is a
**regression guard** — and a guard that guards nothing checkable is not a guard. **So item 1 is
editorial and carries no check.** Inventing a gate to make the row look symmetrical would be the same
defect in a new place.

---

## Defect 2 — a registry whose TWO stated rules are both false about its own entries

**`tests/docs_links.py`'s `DOCS` registry carries THREE comments** — the file is named here, not only in
the Verification block below, because the bare ranges that follow are unreadable without it. The first
draft of this section reported one comment; that omission was the error, and the corrected reading is
what follows.

```python
:73  # Docs a reader can arrive at from the README. Templates are included because a broken link
:74  # in an issue form is invisible until someone opens the form.
:75  DOCS = [
...
:85      # Every doc the README links to, so a dead link one hop out is still caught — the
:86      # docstring's promise is "every other doc a reader lands on from it".
:87      "docs/network-guide.md",
...
:91      # Reached from SECURITY.md, which is itself in this list — so the chain README →
:92      # SECURITY.md → spec is walked, and the spec's own outbound links are checked too.
:93      "docs/redos-guard-linearity.spec.md",
```

Read together they are mutually inconsistent, and the measurement says **which of them is true**:

- **`:85-86` — a false universal.** *Every* doc the README links to. Four of them are absent (below).
  It is also false about the group it directly heads: `docs/network-graph-interaction.spec.md` sits
  there and is not a README link.
- **`:73-74` — the header, over-claiming about ONE entry rather than two.** *Docs a reader can arrive at
  from the README.* Its own second sentence is a carve-out — *"Templates are included because a broken
  link in an issue form is invisible until someone opens the form"* — and it covers the template
  entries, which a contributor reaches by GitHub's own injection rather than by a link. So
  `.github/PULL_REQUEST_TEMPLATE.md` is **not** a counterexample to this header; it is the exception the
  header **states**. ⚠ The spec's first draft counted it, reasoning that it has 0 markdown-link hits
  anywhere — true, and a measurement of the wrong proposition: *no link reaches it* is not *a reader
  does not arrive*. The one entry the header fails to cover is
  `docs/network-graph-interaction.spec.md`, which is neither a README arrival, nor a template, nor the
  documented two-hop chain. **A header that states its exception is scoped; a header that states none is
  a universal** — which is exactly how `:85-86` fails.
- **`:91-92` — accurate**, and it is the only one that is: it describes a two-hop reach that the
  measurement confirms.

So the defect is not "a registry that fails to state its rule." **It is a list whose header and
interior state two different rules and satisfy neither** — `:73-74` over-claiming about one entry while
stating its template exception, `:85-86` over-claiming about four while stating none — with a third
comment, the only true one, supplying the counterexample that adjudicates between them.

### The measurement, part 1 — the README's links

Over the README's **true markdown link targets**, parsed as links rather than as backticked prose (the
distinction is load-bearing: the `MEMORY.md` hit a looser matcher reports is prose inside a table cell
and is *not* a link, verified at the `Always loaded` row), the README carries **12 distinct `.md`
files** as targets. Eight are in `DOCS`. **Four are absent**, and all four exist:

| README link target (hop 1) | exists | in `DOCS` |
| --- | --- | --- |
| `plugins/dream-beta-tester/docs/SPEC.md` | yes | **no** |
| `plugins/dream-beta-tester/docs/CONTRACT.md` | yes | **no** |
| `plugins/consolidate-memory/skills/consolidate-memory/SKILL.md` | yes | **no** |
| `plugins/consolidate-memory/skills/consolidate-memory/references/harness-map.md` | yes | **no** |

**The charter named two of those four**, so the chartered fix as scoped would leave the coverage
short.

⚠ **The operand and the matcher are both stated, because the count is ambiguous one link wide and an
unnamed count is not a fact.** MATCHER: the README's inline-link destinations, the raw `](...)` form,
optional title dropped, classified on the destination string. It reads **29** in total, of which **13**
point at a `.md` across **12 distinct files** — one of the thirteen is
`docs/network-guide.md#migration-and-revocation`, a **fragment variant** of a file already counted. A
matcher keyed on `.md`-as-final-extension reports 12; one keyed on the path before `#` reports 12 files
from 13 hits. Both land on 12 files — written down because this is the shape of count that drifts
silently under a re-run with a different matcher.

**The other sixteen, enumerated to sum to their own total** — `13 + 16 = 29`, and the sixteen are
**3 + 2 + 11**: **three** image links, all three under `docs/assets/` (`nocturne-overview.png`,
`nocturne-network.svg`, `network-topology.svg`); **two external** `https://code.claude.com` targets (the
memory and plugins-reference pages); and **eleven** local non-`.md` — `scripts/*.py` ×4, `scripts/*.js`
×2, `scripts/dashboard.template.html`, the **preview** at `docs/previews/nocturne/index.html#sel=7`, the
**directory** `docs/adr`, and `LICENSE` appearing **twice**.

⚠ **An earlier draft of this paragraph called the sixteen "measured rather than assumed" and then named
thirteen.** It wrote `LICENSE` once, took the preview without its fragment, and **omitted the two
external links entirely** — an exhaustive-sounding census whose members do not sum to its own total,
which is the class this document exists to catch, arriving in the census that establishes it. The three
images were also folded into a `docs/assets/ ×3` line as if that were a separate bucket, which is
exactly what made the draft's own arithmetic uncheckable.

A link into `scripts/` is covered by the import and test gates; an asset link by nothing a prose
registry could add.

### The measurement, part 2 — reachability, and the rule the list does NOT implement

MEASURED over the graph of markdown links between tracked `.md` files, resolved relative to the linking
file: **116 tracked `.md` files at B's head `9585b10` — this branch's base; only 16 are reachable from
the README at all.** Of those sixteen the list holds ten. The remaining six split cleanly:

⚠ **The tracked total carries its matcher and its revision, because the first draft's `113` carried
neither.** MATCHER: `git ls-tree -r --name-only <rev>`, filtered to `.md`. Measured across this stack:
**114** at the base `fbfe07e`, **115** at A's `faaa3c2`, **116** at `852ca9e`, **116** at B's head
`9585b10`, **which is this branch's base** — the `docs/` subset tracking it at 79 / 80 / 81 / 81.
⚠ **An earlier draft of this very paragraph over-corrected: it read "no revision yields 113" — a
universal over an unbounded space, derived from four samples.** Measured one revision further back,
`113` is exactly **`e5cce77`**'s count: the **F1 base**, superseded by `fbfe07e`. So `113` was never a
number about nothing — it was a census **carried forward across a base revision**, which is a sharper
diagnosis than the universal was, and the same failure mode as every stale numeral in this stack. The
figure in the sentence above is `9585b10`'s, and it is the one the 16 and the 10 are measured against.

⚠ **Its provenance is claimed with a confidence the arithmetic does not support, and the measurement is
what says so.** `113` is `e5cce77`'s total **and** `fbfe07e`'s total with the root `README.md` dropped
(`114 - 1`) — and those are one equation, not two, because F1 added exactly one `.md` and the README is
exactly one `.md`. "Carried forward" is therefore one live reading and "the tracked set with its
traversal root removed" is another, and neither can be excluded. A provenance stated where two fit is
the same defect this paragraph is repairing, one layer in. What the sentence's own pair does settle is
which reading is **consistent**: the `16` counts the README, so a denominator that drops it is a unit
mismatch rather than a census — and that is why the figure written above is the total at `9585b10`,
the set the `16` is measured against.

| hop | `.md` reachable from README, absent from `DOCS` |
| --- | --- |
| **1** | `SKILL.md` · `references/harness-map.md` · `SPEC.md` · `CONTRACT.md` ← **the four above** |
| **2** | `CLAUDE.md` · `plugins/dream-beta-tester/docs/SPEC-A.md` |

⚠ **And FOUR `DOCS` entries are reachable by NO markdown link from the README at all** —
`.github/PULL_REQUEST_TEMPLATE.md`, `.github/ISSUE_TEMPLATE/bug.yml`,
`.github/ISSUE_TEMPLATE/feature.yml`, and `docs/network-graph-interaction.spec.md`. Checked against
every link form, not just the one the extractor sees. The two **issue forms carry no prose mention
anywhere in the tree** — a strictly stronger unreachability than the other two. Those two do surface as
backticked prose, and their mention sets are **measured rather than generalised** — operand: backticked
prose in tracked files, this document excluded as the one doing the counting — because they are not the
same size: `.github/PULL_REQUEST_TEMPLATE.md` is named in **two** (`CHANGELOG.md`, and
`check_links`' docstring in `tests/docs_links.py`), while `docs/network-graph-interaction.spec.md` is
named in **four** — `CHANGELOG.md`,
`deep-field-theme.spec.md`, `fleet-topology-ui.spec.md` and `redos-guard-linearity.spec.md`. A prose
mention is not an arrival either way: the reader must copy a path out of a sentence.

⚠ **The count is FOUR, and the first draft's "two" is repaired rather than annotated** — it is this
document's own under-count class arriving in the census that establishes it, the same shape as the
sixteen that named thirteen. It is derivable three ways, and the third needs no new instrument: the
graph reaches **16** tracked `.md` from the README, the list **holds ten** of them, and the list has
**14** entries — `14 - 10 = 4`. The independent read uses part 2's matcher (`ls-tree -r --name-only
<rev>` filtered to `.md`; edges by the raw inline-link form resolved relative to the linking file; BFS
from `README.md`) and names the same four.

⚠ **Two different fours live in this section, and conflating them yields a wrong repair.** The four
`README`-linked docs **absent from the list** (`SKILL.md`, `harness-map.md`, `SPEC.md`, `CONTRACT.md`)
are the ones the repair *adds*; the four list entries with **no README arrival** (this paragraph) are
the ones no addition can fix. Disjoint sets, same cardinality.

⚠ **Four entries have no markdown arrival, and only ONE of them leaves the header false.** The three
templates — the PR template and the two issue forms — are the exception `:73-74` states in its own
second sentence (*"Templates are included because a broken link in an issue form is invisible until
someone opens the form"*), which **names that class in words**: a contributor lands *in* each of them by
GitHub's own injection, which is an arrival with no link. So none of the three is a counterexample to a
header that states its own exception. `docs/network-graph-interaction.spec.md` is: it is in the list, it
is not a README link, it is neither template nor form, and no comment in the file accounts for it.
`:91-92`'s explicit two-hop justification for `redos-guard-linearity` is the one entry whose reach the
file actually documents.

**So no closure rule describes this list, and that is the finding.** It is a **hand-curated set** whose
membership is a judgment about reader-facing-ness — and it is not even the closure of one hop (four
1-hop docs are out, four unreachable docs are in), nor of two (a 2-hop spec is in, a 2-hop doc is out).

### The repair — four parts, and the comments are the load-bearing one

1. **State the list's actual principle, with its bound, in one place.** Not a closure — a curated set of
   **reader-facing documents a reader lands on**, explicitly including the GitHub templates a
   contributor lands *in* and, where a reader is handed off, the design record they are handed to. A
   rule that does not name its exclusions is a universal again one edit later; the exclusions are
   measured above.
   ⚠ **Appending the principle is not correcting the sentence it supersedes.** The first pass at this
   added the bound *below* an opening sentence that still asserted *a reader can arrive at from the
   README* — the one entry C4 measures it failing to cover — so the header then stated the false rule
   and its own denial in consecutive sentences, and MEASURED it still did: **0** markdown inlinks to
   `docs/network-graph-interaction.spec.md` (matcher: `](...)` destinations over every tracked `.md`,
   doc-relative). ⚠ **A correction appended beside the claim it corrects leaves both standing** — the
   same shape as item 4's finding (a restatement corrected while its source stood) and as item 2's
   recorded near-miss (a restatement that would have duplicated the header while the false line
   stood). Three instances inside one repair is why the rule is stated here rather than left to taste:
   **fix the line, don't append below it.**
2. **Correct or delete `:85-86` — and the repair takes the SECOND branch.** The correction branch is
   foreclosed by measurement, not by preference: the rule the comment would then state — the header's,
   scoped to the entries it heads — is still a rule stated **below** a header that already states one,
   which puts the list's criterion in **two places**, the defect this item removes rebuilt by its own
   repair. So the criterion moved **into** the header, which gained the second inclusion part 1
   requires, and the comment keeps only the measured fact and the entry's reason, **asserting no
   rule**. A false universal is not repaired by adding rows until it becomes true — that would drag the
   whole README closure (source files, assets, `LICENSE`) into a prose-link registry to satisfy a
   sentence that should not have been written.
   ⚠ **And do not "restate the header" — the first draft of this spec proposed exactly that, and
   `:73-74` already is that restatement.** Carrying it out would have **duplicated a correct comment
   while leaving the false one in place**: the over-claim surviving its own repair, arriving in the
   repair *proposal*. Recorded because the near-miss is the finding.
3. **Add the four 1-hop entries**, so the list and the header agree on the unambiguous class. Then
   **record `SPEC-A.md` and `CLAUDE.md` as the measured boundary** — a doc one hop past a doc being
   added, and a doc Claude loads automatically — so the next editor inherits the boundary rather than
   re-deriving it. The four entries with no markdown arrival split **three and one**: the three
   templates take **none** — the header already names their class in its own second sentence, above —
   while `docs/network-graph-interaction.spec.md` needs the justification nothing in the file currently
   gives it.
4. **Scope the module docstring's invariant 2 — the SOURCE of `:85-86`, not a separate finding.**
   `:85-86` did not invent its rule; it **cited** one, naming its authority inside the same sentence
   (`the docstring's promise is "…"`), and that authority is the second of the **eight** invariants
   the file opens with — which states the checked set as the README *and every other doc a reader
   lands on from it*. Correcting the comment therefore leaves the universal standing at its **origin**, one edit
   from being re-derived off the same sentence, which is how `:85-86` was written to begin with.
   Both counterexamples are already measured above (`CLAUDE.md`, `SPEC-A.md`), so this part adds no
   measurement — only the site and its repair: state the set the check actually walks (`DOCS`), and
   name the gap. The repair is the file's own idiom, which is invariant 6's: that invariant already
   declares its own narrowness, by naming the counterexample that sat in its own doc set.

⚠ **The `SPEC-A.md` finding is why this section was rewritten twice.** The first repair was "add the
four"; measuring what those four *lead to* found `SPEC-A.md` (23 KB, linked from `SPEC.md`) sitting one
hop further — **the repair reproducing, one layer down, the under-coverage it was written to fix.** It
was caught only by asking what the added docs themselves link to, which is the check this document
recommends for any future edit to the list.

⚠ **Adding the four is a REGRESSION GUARD, not a pin** — by this repo's own rule, and MEASURED rather
than assumed: **all four hops currently resolve**, so no check added here can fail on pre-fix code. What
it buys is that those docs' **own outbound links** enter the check, so a dead link one hop further out
is caught. MEASURED with all four added: gate **green** (`rc = 0`), checked files **14 → 18**. ⚠ **The
count and the green certify different things, and the count is not the evidence.** `18` is `len(DOCS)` —
the list's own length, printed from `main()`'s f-string — so it is derivable from the list alone and says
nothing about whether the members exist. What says all eighteen were **read** is that the run printed at
all: a missing member goes to `err()` and `continue`s, and any run carrying an error prints the failure
block and **no count**. The guard's observable is therefore *green, with the denominator at 18*.

---

## Two findings, one PR — stated rather than implied

Two defects sharing **no** cause: a splice artifact in a code comment, and a registry whose two stated
rules are both false about its own entries. By this repo's rule *two findings are one defect iff one
repair closes both*, these are **two**. They ship together because the user chartered them as one
release — a reader looking for the single root cause here will not find one.

---

## Verification

```
python3 tests/smoke.py && python3 tests/docs_links.py && python3 tests/simulate_accumulation.py
mypy --config-file mypy.ini && python3 tests/validate_manifests.py
```

**Item 1 carries no check** (see above). Its only observable is that the doubled clause is absent.

**Item 2 carries a regression guard**, with the added-entry count as its observable: it must be `18`,
and the gate must stay green. A red means one of the four docs carries a dead outbound link — the guard
working on its first run.

⚠ **This document adds a `docs/**/*.md` file carrying no citation**, so PR B's citation gate counts one
more **scanned** doc and the same number of **citing** docs. MEASURED, not predicted: scanned moves
**81 → 82** and citing holds at **23**, with this file absent from the citing set. Stated because the
scanned total appears in a check's printed output, and an unexplained move in a printed denominator is
how a reader learns to distrust the number.

---

## The review round — five repairs, and two refutations the artifact's own text settles

**Stage 3's fresh round was dispatched on the shipped revision; the findings below were adjudicated at
the head `2492caa`** — not against the binding, because the branch moved once more under it. Each
was re-measured first-party rather than accepted on delivery, and each repair **edits the claim it
falsifies** rather than annotating below it, which is this branch's own item-1 rule.

⚠ **A peer finding is a hypothesis.** Two of this round's were refuted by the artifact's own text, and
both refutations are checkable rather than rhetorical — which is the only reason recording them earns
the space:

- **The registry's exclusion list omits `docs/adr` and should name it. REFUTED.** The header's
  exclusions read *destinations that are not reader-facing documents — source code, assets, the
  generated preview, `LICENSE` — are out of scope by design*: a **general clause with an exemplifying
  appositive**, not a closed enumeration. `docs/adr` is a **directory** — a destination that is not a
  document — so the clause covers it, and part 1's own enumeration already says so in as many words
  (*the **directory** `docs/adr`*). MEASURED, since the refutation turns on what the class holds:
  **24** `.md` files live there; the only markdown link into that directory anywhere in the tree is the
  README's one link to the directory itself; **no ADR is linked individually**; and **not one of the 24
  carries a single `](` markdown link of its own**. So the class adds no coverage the check could walk —
  and *a general rule that gives examples is not a list that failed to be exhaustive*, which the header
  says in the same breath as *CURATED* and *not the closure of the README's links*.
- **The note after the list restates the list's criterion, giving the rule a second home. REFUTED** —
  and the refutation is the docstring's own. Invariant 2 closes *the note after the list now carries the
  boundary instead*, so the note is a **delegated** home; and the header points at it in the very
  sentence that states the principle (*see the notes inside the list, and after it*). **Two independent
  delegations make it a designated carrier, not a duplicate.**

**Five findings were CONFIRMED, and every one is a binding rather than a value** — four here, one in the
CHANGELOG:

| # | where | what was false | the repair |
| --- | --- | --- | --- |
| 1 | the opening sentence | *states the rule correctly* about `:73-74`, which this document's own Defect 2 calls **over-claiming about ONE entry** | restated as what Defect 2 measures: the upper comment over-claims, the lower is accurate |
| 2 | the same sentence | *three lines below it* — the gap is **5**, under the convention its own sibling establishes (**11**, from `:73-74` to `:85-86`), and no pair of comments in the block is 3 apart | corrected to **five** |
| 3 | part 2's opening measurement and its two provenance notes | *this revision*, *the head* — bound to no revision, in a document that uses the same phrase for its own head elsewhere | bound at every site to **B's head `9585b10` — this branch's base** |
| 4 | part 2's mention census | *mentioned nowhere else in the tree at all* — a universal with no stated operand, while the registry's own list entries name both issue forms | scoped to **no prose mention anywhere in the tree**, the operand the pair beside it is measured under |
| 5 | the CHANGELOG's v0.4.38 item 2 | *four are absent from the list*, present tense — **0** are absent at the head, where all four were added | past tense |

⚠ **Finding 3's numerals were RIGHT and its label was wrong, and that is why the repair binds rather
than recomputes.** The figures — `116` tracked, `16` reachable, ten held, and the `14 - 10 = 4` that
follows — are correct **at `9585b10`**, and the `16` is the set the others are measured against. Swapping
in the head's would have replaced correct content with wrong content: the head reads **117** tracked, and
the increment is this document. **Binding the label is the whole repair.**

⚠ **The round's own instruments caught themselves, in the class this document exists to repair.** A
first read of the tracked total came from a compound command whose reported status is its **last
stage's**, so a `git grep` that never ran read as *no match*; and a first census of the registry's
entries counted `:85-86`'s quoted docstring promise — a **comment** — as a list entry. **A zero from an
instrument is a hypothesis about the instrument until its matcher and its working directory are
stated**, and this document's rule that an unnamed count is not a fact binds the instruments as much as
the claims.
