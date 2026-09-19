# Prose tied to the tree — the five RC-6 families (PR B, v0.4.37)

> **READING NOTE — the coordinates in this document resolve at `fbfe07e`** (main @ v0.4.35), and
> nowhere else — every `file:line` below is **`fbfe07e`-numbered**. A bare `file:line` here is a legitimate citation **only** under that binding; that is
> the rule this document exists to adopt (see *Family 4*), so it is the rule this document obeys
> first. **Resolve against the base commit** — `git show fbfe07e:<path> | sed -n '<N>p'` — and
> **never against the working tree.** A coordinate that does not resolve on the working tree is
> **expected** here, for a reason stronger than PR A's: this document's own repairs *change the lines
> it cites* (`:71`'s figures, `cm:71`'s usage block, both packaging-prose sites), so the working tree
> is precisely where a coordinate should be allowed to rot. One that does not resolve on `fbfe07e` is
> a **defect in this document**.
>
> **Quoting wrapped source.** A phrase spanning a source line break is not greppable contiguously
> (`wrapped-phrase-is-not-greppable`), so a quote that spans one is written with **`⏎`** marking the
> break and is *not* claimed to be a single contiguous string; **`…`** marks material **omitted** from
> a quote. The two marks are not interchangeable, since `⏎` asserts a break is *in* the source and `…`
> asserts something was *cut*. (Both are PR A's convention; Family 5 is why it is needed here.)
>
> **This document is a design-of-record, not a report.** PR A (`docs/identity-from-the-input.spec.md`)
> records work already measured and shipped in the tree; this one records the design for work not yet
> written. Its findings are measured; its repairs are prospective. Anything prospective is marked.
>
> ⚠ **This document uses TWO coordinate systems and the note above declares only one, so the other is
> stated here.** A bare **identifier anchor** — a check's own constant, such as `_CITE47`, `_ls47` or
> `_ws_tolerant` — names the **shipped** tree, not `fbfe07e`, and it *must*: that machinery is part of
> the change this document designs, so it does not exist at the base at all. MEASURED, with the matcher
> and scope stated because an unnamed count here is not a fact: over every backticked
> identifier-shaped token in this document, resolved by `git grep -w <token> fbfe07e
> -- tests/ plugins/`, exactly **four** are absent — `_CITE47`, `_ls47`, `_nlines47`, `_ws_tolerant` —
> and each is machinery this branch introduces. (The revision string is trivially absent too and is not
> an identifier anchor.) The **absent set is the claim and the denominator is not**: the token count
> moves with every edit to a draft, and this one has moved, so it is the matcher above rather than a
> total that makes the figure checkable. The two systems do
> not collide, because they answer different questions — a `file:line` into a **pre-existing** file
> resolves at `fbfe07e`, while an identifier that is *itself part of the fix* can only ever name the
> tree that carries the fix. Stating it is what stops the reading note above from being read as an
> authorisation it never gave: without this clause, "every coordinate resolves at `fbfe07e`" reads as a
> claim about `_CITE47` too, and it would be false. (The same clause, for the same reason, heads
> `docs/render-declaration-parity.spec.md` — a document whose fixture names have exactly this property.)

---

## The charter

F2 is one root cause in two halves. F1 (RC-1…RC-4, v0.4.35) closed the first half — *a surface
re-derives meaning from a **label** instead of from the data that produced it* — under the release
title *"a refusal stops being spelled like a verdict."*

RC-6 is the second half, and it is stated exactly:

> **An assertion takes its source from something other than its subject.**

The assertion is prose; its subject is **the tree**. Its source is the author's recollection at the
moment of writing. The two drift, and nothing in the repo notices, because prose is checked by
nothing. That is why this family cannot be repaired by care — care is what failed. Each of the five
families below gets one of exactly three repairs:

| family | repair | why that one |
| --- | --- | --- |
| 1 — the budget ladder | **give it a producer** | a producer already exists; the prose restates its output by hand |
| 2 — `cm`'s usage block | **a gate** | the surface is a CLI contract; the parser is the authority |
| 3 — the packaging prose | **a gate** | three sites: one over-claims, two mis-locate, and all three agree on the false item |
| 4 — the citations | **the rule, made enforceable** | the census reproduces only under a named matcher *and* scope; a count missing either is not a fact |
| 5 — the wrapped anchors | **a regression guard** | there is no live defect — the rule it protects does not exist yet |

---

## Before the findings: three times the measuring instrument was the defect

This is not an apology. It is the argument for the design, and it is stronger than any of the five
findings, because the failures are all **mine**, all in this family's own subject, and all inside one
measurement session.

1. **A scope error that looked exactly like a matcher effect — and that I filed as the plan's.**
   I measured the census over `docs/**/*.md` (**79** files) and read it against the plan's figures,
   which were taken at the plan's *declared* scope, `docs/*.md` (**55**). Reading 287/414/471 against
   284/410/471 I wrote *"the census does not reproduce"*, attributed it to the plan's matcher, and very
   nearly shipped it. **The plan's three figures reproduce to the digit on its own scope.** My matcher
   was never at fault; I had changed the operand under a label that still named the old one. Family 4
   keeps the finding and loses the accusation.
2. **A name I looked for instead of a body.** Verifying the `session_beacon.py` citation I grepped the
   cited range for `_cwd_from_stdin` and found it absent, and concluded the cited lines were the wrong
   function. They are not: the `def` is at `:81`, and a **function's body never repeats its own name**.
   The citation is correct. I had checked a label against a predicate.
3. **A quoted sentence read as data.** Measuring link-gate coverage I regexed `DOCS = […]` out of
   `tests/docs_links.py` and extracted `'every other doc a reader lands on from it'` as a *list element*.
   It is the tail of a **comment** *inside* the list literal — `tests/docs_links.py:85-86`, between two
   entries, not above the `DOCS = [` line — and my non-greedy pattern had spanned into it
   and my string-extractor had pulled a quoted phrase out of English prose. I nearly filed a defect
   that said the link gate names a sentence as a file. The gate's line interpolates `len(DOCS)`
   (`tests/docs_links.py:459`), and `DOCS` holds exactly 14 real entries (`:75`) — so it prints
   `14 files link-checked`.

Three errors, three different surfaces, one class: **I trusted a number my own instrument produced
without asking what it could see — and, in the first case, without asking what it was looking at.**
RC-6 says prose takes its source from something other than its subject; measurement takes its source
from something other than its *subject* too, unless the matcher **and the scope** are both stated. The rule below is what makes this checkable by a gate instead of by care — and the fact that it
caught its author three times *before a single finding survived* is the evidence.

---

## Family 1 — the budget ladder · **CONFIRMED** ✓ · *give it a producer*

### The sentence

`docs/index-usage-and-budget-ladder.spec.md:71` reports three fleet positions. Verbatim, with the
figures marked:

```
position: consolidate-memory 6,138 B / 27 ln = **25% / 14%** of the cliff; Doc-Flo 11,244 B / 46 ln =
**44% / 23%** of the cliff (CORRECTED 2026-07-04 spec-review gate — the original "107" was Doc-Flo's
*fact count*, mis-wired into the line-count slot; its real index is 46 lines, not 107); job-applicator
≈8.8 KB / ~38 ln = **35% / 19%**.
```

### The producer

`memory_status.py:918-923`, verbatim:

```python
def cliff_pct(index_bytes: int, index_lines: int) -> int:
    """v0.1.63 (Phase A): proximity to the harness-native index truncation cliff as a percent — the
    BINDING axis wins: max(bytes/25KB, lines/200). PURE; exact units by design (see the constants
    block: the cliff is the harness's cap, so it's measured in the harness's units, never
    est_tokens)."""
    return round(100 * max(index_bytes / NATIVE_INDEX_CAP_BYTES, index_lines / NATIVE_INDEX_CAP_LINES))
```

Its operands are shipped constants at `:719-720` — `NATIVE_INDEX_CAP_BYTES = 25 * 1024` (**25,600**) and
`NATIVE_INDEX_CAP_LINES = 200`. The binding axis wins, `max(...)`, and for all three nodes above the
binding axis is **bytes**.

### Measured — the shipped function, run on the sentence's own inputs

| node | bytes / lines | `cliff_pct` | sentence's byte figure | sentence's line figure | line axis (`100·l/200`) |
| --- | --- | --- | --- | --- | --- |
| consolidate-memory | 6,138 / 27 | **24** | 25% ✗ | 14% ✓ | 14 |
| Doc-Flo | 11,244 / 46 | **44** | 44% ✓ | 23% ✓ | 23 |
| job-applicator | ≈9,011 / 38 | **35** | 35% ✓ | 19% ✓ | 19 |

**Every figure is correct but one** — and that one is the finding: the byte figures reconstruct from
**two different denominators inside one sentence**. 6,138 reaches 25 only at a 25,000 divisor; 11,244
reaches 44 only at 25,600, the shipped constant. So the sentence is not uniformly off by a rounding
tolerance but **internally inconsistent**, and the shipped function agrees with two of its three
answers while disagreeing with the one carrying an exact input.

(The third node needed no correction: its `≈8.8 KB` reads as 9,011 B in the document's own units —
`25KB` is 25,600 there — and 9,011 B / 38 ln is exactly 35%. Reading it as decimal 8,800 is what
manufactures a 34, and that is the same operand-convention question as node 1's, one node over.)

### The document already contains the other answer

`docs/index-usage-and-budget-ladder.spec.md:324` — the same document's own gate criterion:

```
- **G-A3:** fixture: 6,138 B / 27 ln → `cliff_pct == 24`; red iff ≥ 80.
```

**6,138 B / 27 ln.** The exact inputs `:71` calls **25%**, the sentence's own gate asserts as **24**.
The gate is right and the prose is wrong, and the file has held both since the same edit. This is the
sharpest instance of the family in the corpus: *the document's verification criterion would fail the
document's own prose*, and no check noticed because nothing compares a spec's prose to its fixtures.

### A second bad figure — and the plan's derivation of it was itself unmeasured

`:75` closes the paragraph: *"no real fleet store is anywhere near the **120-line cliff axis**"*.

- The cliff axis in lines is **200** (`NATIVE_INDEX_CAP_LINES`); in bytes **25,600**.
- The near-threshold is `CLIFF_NEAR_FRACTION = 0.8` (`:721`), applied at `:4641` as
  `>= int(CLIFF_NEAR_FRACTION * 100)` — i.e. **80%**,
  which on the line axis is 160 *(derived here: 0.8 × 200; both operands shipped, the product is mine)*.
- **`120-line` occurs exactly once in the tree at `fbfe07e`** — on that line. Nothing names it. *(It
  occurs three more times in this document, which is the reason the claim is bound to a revision: a
  census recorded inside the artifact it covers can never equal the shipped tree.)*

The plan offered `120 = INDEX_CEILING_FRACTION × NATIVE_INDEX_CAP_LINES = 0.6 × 200`. `INDEX_CEILING_FRACTION = 0.6`
does exist (`:747`) — but `:748` applies it to **`NATIVE_INDEX_CAP_BYTES`**, producing
`INDEX_CEILING_TOKENS = 3840` **est tokens**, and says so in a trailing comment. `NATIVE_INDEX_CAP_LINES`
appears at exactly **two** sites in the module: its definition (`:720`) and its single use inside
`cliff_pct` (`:923`). It is never multiplied by a fraction. And `cliff_pct`'s own docstring refuses the
inversion — *"exact units by design (see the constants block: the cliff is the harness's cap, so it's
measured in the harness's units, never est_tokens)."*

So `0.6 × 200` is arithmetic **no shipped code performs**. It is a plausible provenance and I record it
as a **hypothesis, not a finding**: what is measured is that **120 is unaccounted for and is not the
cliff**. This is RC-6 committed by the plan that exists to fix RC-6 — prose asserting a fact about the
tree that nothing tied to the tree — and it is the reason the repair below is *"cite the producer"*
rather than *"correct the number"*. A corrected number is the same defect with a better value.

### The repair — and the operand ambiguity the document already documents

The hand-derivation is not sloppiness, and the tree says so. `:715-716` records the operand choice
deliberately:

> *"25KB is⏎# read as 25×1024; if the harness means 25,000 the shift is <2.5% (immaterial to an 80% alarm)."*

That is sound reasoning **for an alarm**. But `<2.5%` is precisely enough to move `23.98 → 24.55` —
**24 vs 25** — and the spec quotes a hand-derived percentage at a precision finer than the operand's
own documented ambiguity permits. The tolerance that is immaterial to an 80% alarm is *decisive* at
two significant figures. **The repair is to stop hand-deriving it.**

A producer already exists and already prints: `:4640` renders `cliff {_cp}% of native 25KB/200ln`, and
`:4646` prints the operands beside it (`{il} ln · {ib} by`). Any node's position is already produced by
its own report. So:

1. **`:71`'s fleet-position figures cite the producer** instead of restating its output by hand — the
   axes get named as the shipped constants (200 ln / 25,600 B), the derived percentages come from
   `cliff_pct`, and `:75`'s `120-line cliff axis` is replaced by the axis the code has.
2. **The dated operand note** at `:713-716` collapses to its one home, so the ambiguity is stated once.
3. **The `:324` contradiction is closed by construction**, not by editing one side: with `:71` citing
   `cliff_pct`, prose and fixture cannot disagree.

---

## Family 2 — `cm`'s usage block · **CONFIRMED** ✓ · *a gate*

`cm:71` (at `fbfe07e`), verbatim:

```
  cm local rebuild-index [--plan|--apply --confirm rebuild-local-index] [--skip-invalid]
```

The parser it describes — `cm_ops.py:3030`, `loc = sub.add_parser("local")` — takes **no `parents=`**,
and the declarations that follow are `local_cmd` (six choices), `stem`, `--file`, `--project`,
`--json`, `--apply`, `--skip-invalid`, `--confirm`. **There is no `--plan`.** The file's only `--plan`
arguments belong to other subcommands (`migrate`, `data`).

**Measured:** `./cm local rebuild-index --plan --project .` → **rc=2**,
`cm_ops: error: unrecognized arguments: --plan`. The advertised flag is not undocumented — it is
**unusable**. (rc taken from the command itself, not the pipeline's last stage.)

The plan-only rule the usage block gestures at lives in the implementation, not the parser:
`local_ingress.py:28` `REBUILD_CONFIRM = "rebuild-local-index"`, the `if not apply:` branch at `:797`
(with a sibling at `:883`), and the confirm check at `:803`. So the F2 repair is **the line, not the
behaviour**: the usage block should advertise the surface the parser actually has.

### No gate exists, and the obvious one has a hole

Nothing ties the usage block to the parser.

- The suite's only `build_parser()` parity pin covers `data compact --plan` / `data retention show` —
  **not `local`**.
- The `cm help` substring check never mentions `rebuild-index`.
- The repo's **"arm 3" doc-flag sweep deliberately carves the file out**: `tests/smoke.py:18526`
  `_ARM3_OUT29 = ("cm_ops.py", "sync_global.py")`. Its scan set is `commands/*.md` + `SKILL.md` +
  `README.md`, and it reads only ```` ```bash ```` fences — the `cm` heredoc is in neither.

So the new gate must cover the heredoc **and must not assume the existing sweep will catch it**. The
replacement is the one the file's own precedent supports: parse the usage block's advertised flags and
assert each one **is accepted by the parser** — the `build_parser()` parity idiom already used for
`data`, extended to `local`. A flag that the parser rejects is the exact defect, so the pin is a
**real pin**: on pre-fix code it goes red by construction.

---

## Family 3 — the packaging prose · **CONFIRMED** ✓ · *a gate*

Ground truth, `.github/workflows/release.yml`:

| line | what it does |
| --- | --- |
| `:88-93` | `actions/attest-build-provenance@v2` — publishes via the **attestations API**, *not* a release asset |
| `:122` | `gh release create "$TAG" --title "$TAG" --notes …` — passes `--notes` only |
| `:123` | `gh release upload "$TAG" sbom.spdx.json SHA256SUMS --clobber` — attaches **exactly two** |

(`gh release create`'s auto-generated "Source code" links are not assets.)

Both **live** prose coordinates hold (the third site, in `CHANGELOG.md`, is dated and out of scope —
see below), and **both phrases wrap** — so each is written with the `⏎` mark plus the
continuation line's leading run, which is source. `release.yml:12-14` claims the workflow
`` `attaches all⏎#          three` `` — the `#` comment marker *and the ten spaces after it* are in the
file, which is why `lstrip()` does not see them. `SECURITY.md:144-146` states that the project
`` `publishes **SLSA build provenance** plus a⏎  **stdlib-generated SPDX SBOM** to the GitHub Release` ``
— the break, the two spaces of list indent, *and* the emphasis markup are all source. In both cases a
contiguous `grep -c` for the phrase returns **0**.

That is Family 5's defect demonstrated on Family 3's own evidence: a quote that reads as contiguous
while its source wraps, inside the document that is fixing it. (This paragraph is where I found it —
my first draft of these two sentences quoted both phrases as flat strings, and both grepped to 0.)

⚠ **And the wrap does not only defeat `grep` — it can defeat a MATCHER, silently, in the direction
that reads as success.** Check 4's count arm flattens with `" ".join(t.split())`, which crosses the
newline but leaves the next line's leading `#` in place; against the pre-fix phrase it saw
`` `all # three` `` and reported **no count claim** — the same reading it gives a document that makes
no claim at all. What kept that off the docket was luck of construction: the *token* arm was red on
the same check, so a dead arm rode a live one. **A single-arm red is not evidence that the other arm
runs**, and the repair is not to note it — the prose is now read from comment-marker-stripped text,
and the count arm asserts its own extraction is non-empty so a fault cannot again print as an
absence.

They are *also* substantively wrong, which is the actual finding. As the ground-truth table above
establishes, the workflow attaches **two** assets and provenance does not reach the Release at all — so
`release.yml` **over-claims** and `SECURITY.md` **mis-locates provenance** *and* **omits SHA256SUMS**.

**There is a THIRD site, and it is the one that decides the shape of the repair.** `CHANGELOG.md:2495-2496`,
in the shipped `## [0.4.2]` entry, states that the workflow *"publishes build provenance + an SPDX SBOM
to the GitHub Release"* — the same mis-location as `SECURITY.md`, and the same omission of SHA256SUMS.
So the census is **three sites, not two**: one over-claims, and **two mis-locate provenance in the same
way**. On the one item all three are right — the SBOM reaches the Release — they agree; on the one item
all three are wrong — provenance does not — they also agree. **Unanimity is not evidence, and here it
runs entirely on the error**, so cross-reading any two of them *reinforces* it rather than catching it
and a one-site repair leaves it alive.

⚠ **But the third site is out of repair scope, and the exclusion is deliberate rather than convenient.**
A `CHANGELOG` entry is the dated record of a shipped release, not live documentation: it states what
v0.4.2 believed, and rewriting it would make the release record disagree with what actually shipped —
the same rule that keeps the pre-fix coordinates in this document's reading note aimed at `fbfe07e`.
The two **live** sites are repaired; the third is named here so the census is complete and so the next
reader who greps for the claim finds three, not two. The gate below therefore reads the two live sites
and **not** `CHANGELOG.md`, and that scope is stated rather than implied.

### The pin, and the reader that stops short

The plan's recorded `tests/smoke.py:15018-15021` holds a group-lifecycle test at `fbfe07e`. The upload
pin is the `v0.4.5 #152` check at **`tests/smoke.py:16097-16101`**, whose assertion line `:16101` carries
the literal two-filename string `'gh release upload "$TAG" sbom.spdx.json SHA256SUMS --clobber' in _wf_cs`
— it would go red if the attach line changed. That is the read to reuse. (The plan's own `:16096-16101`
was already correct at `fbfe07e`.)

The other `release.yml` reader, `_wf_r5` (`:14220`, asserting at `:14226`), pins only that `attest-build-provenance`
**exists** — never where its output goes. **Nothing currently tests the provenance destination**, which
is precisely the claim both prose sites get wrong. The new gate closes that: it asserts, from the
workflow text, that the prose's claim about *where provenance reaches a verifier* matches the action
that produces it and the upload line that attaches the two assets.

---

## Family 4 — the citations · **REFUTED as posed → reframed** · *the rule, made enforceable*

### The rule the corpus already demonstrates

> **A `file:line` is legitimate iff the doc declares the revision its coordinates resolve on;
> otherwise cite a greppable anchor.**

Three documents already comply, and binding them would be the near-miss this project has recorded
before: `refusal-verdict-parity.spec.md` binds every coordinate to a revision in a reading note;
`render-declaration-parity.spec.md` binds a subsection; `dream-teeth-coverage.spec.md` annotates
per-citation. **Sweeping those would destroy good provenance.**

### The census reproduces — once the matcher **and the scope** are named

Independently re-measured at `fbfe07e`. **A count has three coordinates — matcher, scope, revision —
and this section exists because I dropped the middle one and read the result as a finding.** All
three are given here.

| matcher (as a regex) | top-level `docs/*.md` (55) | recursive `docs/**/*.md` (79) |
| --- | --- | --- |
| `C` backticked explicit `` `[A-Za-z0-9_./-]+\.(py\|md\|json\|html\|sh\|yml):\d+(-\d+)?` `` | **284 / 19** | 287 / 20 |
| `A` bare `[A-Za-z0-9_./-]+\.(py\|md\|json\|html\|sh\|yml):\d+(-\d+)?` | **410 / 28** | 414 / 29 |
| `B` bare backticked `` `:\d+(-\d+)?` `` | **471 / 10** | 471 / 10 |

The plan recorded `C 284/19 · A 410/28 · B 471/10`, and declared its scope as **`docs/*.md`**.
**All three reproduce to the digit, at both coordinates, on that scope.** The plan is right and I was
wrong: my first table declared `docs/**/*.md` and then read the plan's top-level figures against it.
The mismatch I was about to file as the plan's error was my own undeclared operand — and with the two
scopes side by side the mechanism is mechanical: `A` gains 4 hits and `C` gains 3, each gaining one
file, from the **24** subdirectory docs the recursive scope admits. A citation census counts text, and
the scope decides which text exists. `B` — a bare `` `:N` `` — is scope-invariant, which is the one
place the old draft's instinct was sound.

**The finding survives the correction, and is sharper for it.** On a *fixed* scope the three matchers
still disagree by **1.66×** in hits and **2.8×** in file count — **C / A / B in both**: 284 / 410 / 471
hits and 19 / 28 / 10 files. The order is stated because an earlier revision wrote the file triple as
10 / 19 / 28 — B, C, A — under a hits triple in C, A, B, so one parenthesis carried two orderings and a
reader pairing them positionally read A as 10 files when the census table gives it 28. That
is the deliverable, and it can only be stated on a fixed scope:

> **A count is reproducible exactly in proportion to how little interpretation its matcher admits —
> and it is *meaningless* until its scope is named beside it.**

Neither half was visible while I was comparing two scopes at once, which is precisely the point: the
error that this family is about is not a wrong number, it is **a number whose subject was never
fixed**.

This is `refusal-verdict-parity.spec.md:2034`'s already-demonstrated discipline — that doc names its
regex, concedes its totals are *"method-dependent and revision-dependent"*, and scopes itself by the
one figure stable across every matcher. **That is the model to copy, not the number to chase.**

### The six, re-measured against revisions — and the premise was wrong

Six citations were read by hand and each **does** fail to carry its claimed phrase *at `fbfe07e`*. That
reading is correct, and it is not the finding. **Every one of the six resolves at a derivable
revision** — re-measured this window, one citation at a time, against the revision named beside it:

| citing doc (`:line`) | cites | resolves at | what is there | why *that* revision |
| --- | --- | --- | --- | --- |
| `track-c-ci-docs-hygiene.spec.md:25` | `CLAUDE.md:51` | `fcf82ca^` | `…render_dashboard keeps` **`byte-pinned copies`** | the doc is a **defect docket**, created *in* the commit that repaired its rows — so it describes the revision it was filed against |
| `budget-trajectory-early-warning.spec.md:259` | `session_beacon.py:84-86` | `633b2fb` | `if not missing and not stale:`⏎`    return ""` | the doc's creation commit — the "stale → silent" gate, exactly as claimed |
| `budget-trajectory-early-warning.spec.md:21` | `dashboard.template.html:433-434` | `633b2fb` | `function lsSlope(ys){…}` | the doc's creation commit |
| `index-usage-and-budget-ladder.spec.md:52` | `memory_status.py:663` | `80fee17` | `# /lesson-bearing set (measured ~1100-1200 tok)` | the doc's last commit. The sweep moved this cite `:322` → `:663` and was **one line short** at its own commit (`1d20166` has the text at **664**), landing correct at `80fee17` |
| `render-declaration-parity.spec.md:683` | `smoke.py:6668` | `1d97f54` | `int(_wp.get("n_generic") …) + int(_wp.get("n_day_spread") …) <= _n_b` | the revision **the doc itself declares** at `:173-176` — the reading note was never used |
| `audit-hygiene-remediation.spec.md:19` | `memory_status.py:1263-1270` | `6ac5380` | `_GIT_WARNED = False  # v0.1.69/A4: …` and `def _run(cmd, cwd) -> str:` | the doc's creation commit — and the comment carries the row's **own `A4` label** |

**Six for six.** Not one is a wrong citation. They are **unbound** citations: each is correct at a
revision that nothing in its document names, so a reader at `HEAD` sees the difference and calls it
error.

⚠ **The premise of this section was itself an instance of the family it describes.** *"Six citations
are stale"* is an assertion whose subject is the **tree** and whose source was a **HEAD-relative read
with each doc's revision dropped** — `RC-6`, committed by the review that exists to catch `RC-6`. The
tell is in the original phrasing: *"it is simply not what the citing sentence claims"* — true at
`fbfe07e`, and true of every historical document ever written. A citation with no declared revision is
**indistinguishable from a wrong one**, which is the defect; reading it at `HEAD` and reporting the
difference as error is the same defect, one layer up.

**A revision-bound range check catches none of these** — this sentence survives its own table, because
it is about *ranges*: every line number resolves cleanly, which is how a docket can report *"31 stale
citations"* while no check could ever have found one. **But the conclusion drawn from it does not
survive.** Binding is not "not enough"; **binding is the entire repair**, and these five rows are its
proof rather than its refutation: the only thing wrong with them is that no revision is named beside
them.

What binding *cannot* do is make a **declaration** trustworthy — a doc may name any SHA it likes. That
is the whole job the phrase gate has, and it is narrower than the plan gave it: the gate does not hunt
wrong citations; it stops a binding from being **vacuous**. Stated that way it also survives the
objection that killed the wider version — a gate that fires on correct content is a gate nobody reads.

### ⚠ The gate must not confuse a defect with its repair

Row 1 is not a drift. It is a **docket row reporting a defect** — the citing table entry says
CLAUDE.md's *"byte-pinned copies"* **overstates** a behavioral pin — and `CLAUDE.md` has since been
repaired: `byte-pinned` occurs **0×** in it, and `CLAUDE.md:78` at `fbfe07e` now reads *"drift-pinned …
(output equality, not literal source bytes)"*, which is the opposite.

So on a naive *"the claimed phrase must be present"* gate, **row 1 goes red on correct content**. The
absence is the repair, not the defect. This is F1's own release theme arriving one family over —
**a fault and a verdict must not share a message** — and here the shared message would be *"the phrase
is absent"*, which means both *"this claim was never true"* and *"this claim was true and has been
repaired."*

The design consequence, stated so the gate is not built wrong: the gate must read the citing sentence's
**grammatical stance** — a sentence reporting a repair (an overstatement, a correction, a superseded
form) asserts the *opposite* of a sentence asserting a fact, and is checked by asserting the **repaired**
phrase is present. A gate that cannot tell the two apart will fire on closed rows, and a gate that fires
on closed rows gets ignored, which is how it becomes a gate nobody reads.

### The two-part rule PR B adopts

1. **Bind** every doc that carries `file:line` coordinates to a git-derivable revision — in the doc's
   own reading note, the form `refusal-verdict-parity.spec.md` already uses.
2. **Gate** every citation by resolving it against its declared revision — the file exists there, and
   every line number it names, a range's END included, is in range, resolving by **content** where two
   files share a name. ⚠ **Not** by hunting for the phrase the citation travels with: that half is
   refuted by measurement in row 7 (34–63% of the corpus's 494 citations carry no identifier to check),
   and check 7 ships the resolution half alone.

Part 2 is what makes the family a *fix* rather than a formality, and it is what makes the bindings
**testable hypotheses** rather than assertions the check merely trusts.

> **A note on the binding census itself — the same lesson a third time, and this time it closes.** My
> predicate — *"does the doc contain a hex sha anywhere"* — **partitions** the `C` row above exactly:
> at the plan's scope, **200 cites bound across 8 docs, 84 unbound across 11** (200 + 84 = **284**, the
> `C` total, to the digit). The plan's stricter predicate — *"does the doc declare the revision its
> coordinates resolve on"* — reported **3 bound / 16 unbound**. **Both are over the same 19 documents**
> (8 + 11 = 3 + 16 = 19), so this is not a disagreement to be smoothed: a strict predicate is a
> **subset** of a loose one, and 3 ⊆ 8 is what a subset looks like. One population, two questions.
>
> The rule above adopts the plan's predicate, because that is the one the gate needs. The closure
> identity is recorded because it is what makes these numbers checkable by a later reader rather than
> merely quotable — and because the first draft's **`167 / 156` closed over nothing** (167 + 156 = 323,
> matching no census in this document). That it should have been caught before a reviewer caught it is
> the point: a number that partitions nothing was never a measurement of anything.

---

## Family 5 — the wrapped anchors · **REFUTED as posed** · *a regression guard*

### No check verifies a WRAPPABLE phrase

Measured — the complete `tests/docs_links.py` check inventory, eight checks:

`check_badge` `:160` · `check_links` `:186` · `check_anchors` `:211` · `check_required_strings` `:222` ·
`check_themes` `:247` · `check_version_statements` `:310` · `check_plugin_table` `:346` · `check_preview` `:395`

The only whole-file phrase matcher is `check_required_strings`, and its needles **cannot wrap**: it
matches with `rf"(?<![\w/-]){re.escape(needle)}(?![\w-])"`, where a literal space in the needle cannot
match a `\n`. `check_anchors` is README-only and structural (`<a id=…>` ↔ `<a href="#…">`). The
**three** `splitlines()` sites — `:297`, `:333`, `:371` — are line-oriented **by necessity**: each
walks a file line by line to parse a line-shaped structure, theme-table rows and plugin-table rows at
`:297` and `:371`, version statements at `:333`.

So the docket's *"every text scan is line-oriented"* describes the scans correctly and **misses the
point**: the line orientation is not the defect, because **there is no phrase check to orient**.

### The named instance is real

`CLAUDE.md:32-33` at `fbfe07e` contains the inline code span
`` `claude plugin validate⏎./plugins/consolidate-memory --strict` `` — the `⏎` marks the source line
break, per this document's reading note, between `validate` and `./plugins/consolidate-memory` — and a **contiguous**
`grep -c` for that phrase returns **0**. A wrapped phrase is not greppable. This is
`wrapped-phrase-is-not-greppable` stated over a live instance in this repo's own always-loaded file.

The wrap population is **matcher- and scope-dependent, so I give the regex and both scopes rather than
a description**:

| matcher | top-level `docs/*.md` (55) | recursive `docs/**/*.md` (79) |
| --- | --- | --- |
| broad `` `[^`]*?` `` under `re.S`, kept where the match contains a newline | 525 / 44 | **534 / 53** |
| strict single-backtick `` (?<!`)`([^`]*)`(?!`) `` | 380 / 36 | **382 / 38** |

That is a **1.40× spread** in spans (534 / 382) and **1.39×** in files (53 / 38) between two matchers
of the same family at a fixed scope — Family 4's lesson reaching Family 5. Both ratios are taken
*across the bolded recursive pair*; pairing `534` with `380` instead yields `1.41×`, which is what
comparing two scopes produces and is exactly the error this section now guards against. **The plan's recorded 590 reproduces under none of
these four cells**, and this time I checked the scope *before* saying so: two matchers × two scopes,
four reconstructions, the closest still **56 spans** away. That is a *tested* non-reproduction; the
first draft's was not, which is the whole reason Family 4 was rewritten. `CLAUDE.md` is not under
`docs/`, so the named instance is **outside** every cell — stated so the two are not conflated.

### Why this is a guard, not a pin

**There is no live defect.** Nothing today claims to verify a phrase, so nothing today is broken by a
wrap. The contiguity check becomes load-bearing **the moment PR B adopts greppable anchors**, because
**an anchor that wraps is not greppable, therefore not an anchor** — by the adopted rule, not by
preference.

It therefore cannot fail on pre-fix code, and by this repo's own rule — *a check added by a fix may not
fail on pre-fix code; that is a REGRESSION GUARD, not a pin* — it is **labelled a regression guard**.
Its job is to keep the anchor rule true once the rule exists. The repair is the **ninth** `docs_links`
check, and its matcher is stated here because an earlier draft of this sentence named a repair the code
does **not** perform: the check builds a whitespace-TOLERANT pattern over the **raw** file — the needle
re-escaped character by character and rejoined with `\s*` (tests/docs_links.py:`_ws_tolerant`) — so a
phrase split across a newline is findable **without the haystack ever being flattened**. ⚠ Flattening is
not an equivalent implementation, it is the opposite one, and that is measured in the helper's own
docstring: in prose the needle's flattened neighbours are word characters, so `` `Run the /cm- ``⏎`` sync verb` ``
with its whitespace removed reads `` `Runthe/cm-syncverb` `` — the space inside `Run the` dies with the break, so a
flatten is **not** "the break joined", which would leave the needle delimited by spaces — and against that
haystack **both** boundary lookarounds fail, a word character on each side: a wrapped needle then reads as
**absent**. It passed its own mutation test only because every needle in
`REQUIRED_IN_README` carries PUNCTUATION on **at least one** side in README, none having whitespace on
**both** — MEASURED: 5 of the 7 on both sides, while `/cm-connect` and `/cm-share` have a SPACE as the
right neighbour at every occurrence. ⚠ This clause used to read *"is delimited by PUNCTUATION … rather
than by whitespace"* outright, which is false of those two; the qualified form is the true one, and the
same correction is carried in the helper's own docstring: a fixture green for
an ambient reason.

**The check must count spans, never line parities.** This needs no measurement: a span count depends on
*where* the breaks fall, a parity count only on how many backticks precede each line end. The cheap
instrument — carry a cumulative backtick parity per line, keep the odd-ending lines, halve — is no span
count under any reading, and run exactly as that it reads **863** against **534** across `docs/**/*.md`
and **368** against **243** on `refusal-verdict-parity.spec.md`: it *over*-counts, because a stray
unbalanced backtick ends a line "inside" a span that never wraps, while a genuine three-line wrap
still lands near right by accident — which is why it can look correct on a small sample and is not.
Whoever re-derives Family 5's population re-derives it as a span match.

---

## The one rule PR B adopts

Every family above is the same rule applied to a different surface:

> **An assertion must be derivable from its subject, or gated so it cannot silently drift — and where it
> is gated, the gate names both the source and the matcher it reads.**

- Family 1 derives it: the subject is the store's index, and `cliff_pct` is the producer.
- Families 2 and 3 gate it: the subject is the parser and the workflow, and each gate reads that file.
- Family 4 binds it: the subject is a revision, and the gate resolves the coordinate against it.
- Family 5 protects the binding: an anchor that wraps cannot be resolved, so it cannot be an anchor.

---

## Scope and honest limits

- **This document's coordinates are bound to `fbfe07e`** and are legitimate only there. Every figure
  was re-measured in this window; none was inherited from the plan. **Where a plan figure did not
  reproduce, I re-measured it at the plan's own declared scope before recording the non-reproduction**
  — that is a precondition, not a courtesy. The single figure I had recorded as non-reproducing turned
  out to be **mine**, taken on a scope the plan had not used and I had not declared. What survives is
  `590` (the plan's wrap census), tested against four cells of two matchers × two scopes.
- **The repairs are prospective.** No code has been changed for PR B. The pins below are designed, not
  measured; each red-count is owed on the triple (restored code, fixture, harness) and is **not carried**
  from PR A or from the plan.
- **`DOCS` is an enumeration, not a glob** — `tests/docs_links.py` link-checks **14 named files** while
  `docs/**/*.md` holds **79**. That is coherent with its docstring (README-reachable docs), but it has a
  consequence PR B must state rather than discover: **a new spec's own outbound links are checked only if
  it is added to `DOCS`.** Whether PR B adds its spec is a decision to record, not a silent edit.
- **The `120` provenance is a hypothesis.** No shipped code computes `0.6 × 200`; the fraction that
  exists is applied to **bytes**. I record what is measured (120 is unaccounted for; the cliff is 200 ln
  / 25,600 B) and mark the derivation as such.
- **Family 4's census is matcher-, scope- and revision-dependent by construction.** Any count quoted
  from this document without its matcher is not a fact about the tree; it is a fact about a matcher.

---

## Verification

```
python3 tests/smoke.py && python3 tests/docs_links.py && python3 tests/simulate_accumulation.py
mypy --config-file mypy.ini && python3 tests/validate_manifests.py
```

Per defect, a check that **fails on pre-fix code**. Where a check cannot — it can only guard future
drift — it is **labelled a regression guard**, never called a pin. A RED count belongs to the triple
(restored code, fixture, harness) and is never carried across an edit.

Two-tree discipline: **never `git worktree add` a pre-fix tree** (a linked worktree inherits
the main project's identity through `commondir`, which fails hermetic-HOME checks) — **one process per
tree**. Overlay the **live** `tests/` onto the base scripts:
`ROOT = Path(__file__).resolve().parent.parent` makes that "new harness, old scripts", which is the
correct pre-fix experiment.

⚠ **And for THIS PR the base tree must be a `git clone` checked out at the base — not
`git archive <sha> | tar -x`.** The repo's established extraction is `git archive`, and it is correct
for every earlier spec because none of them added a check that reads **the tree under test's own**
history. **PR B is the first that does.** MEASURED over the **36** `git` invocations in `smoke.py`:
**exactly four** resolve against `ROOT` — `_ls47`, `_nlines47`, and pin 8's `log` / `rev-parse` — and
all four are PR B's own; the other **32** run against **self-contained temp repositories the fixture
builds itself** (`git init` at those sites, e.g. the `v0.4.21` git-less-stamp fixture), which no
extractor choice can affect. An archive tree carries **no `.git` at all**, so every one of those four
reads fails. ⚠ **But the CAUSE is wider than "no `.git`", and a third measurement corrects the framing
rather than the remedy:** a `git clone --depth 1` at the *same* revision — a real repository, with a
`.git` and no `commondir` — reproduces the left column of the table below **to the digit**: `2130 / 46`,
7a RED at `1 of 21 citing docs`, and 7b printing the *same* vacuous `0 failing`. An archive tree and a
shallow clone are therefore **indistinguishable to these four reads**, which is the sharper statement of
what they need: not a `.git`, but a repository that can **answer for the revision a doc declares** — and
a shallow CI clone is the case a reader is likelier to meet than an archive extract. The remedy is a
property rather than a command, and it is checked the same way the checks check it:
`git -C <base> cat-file -e <a declared revision>` must succeed before any figure from that tree is
trusted. A plain clone is safe by
the same rule that forbids the worktree: it has **no `commondir`** (measured), so there is no inherited
identity to trip the hermetic-HOME checks, and its `origin` is read by nothing in the suite (the sole
`origin` in `smoke.py` belongs to a self-contained temp-repo fixture).

**The failure mode is worth stating, because it is this family's thesis one layer down: the missing
repository did not announce itself as a missing input — it surfaced as verdicts about the corpus.**
Measured on the *same* `fbfe07e` content, the two extractors differing only in whether `.git` exists:

| | **can't answer for the declared revision** — `git archive` (no `.git`), **and `git clone --depth 1` (measured identical)** | `git clone` @ `fbfe07e` (full history) |
| --- | --- | --- |
| suite total | 2130 passed / **46** failed | **2131 passed / 45 failed** |
| pin 7a | **RED** — *"1 of 21 citing docs name a revision this clone cannot answer for"*, remedy `fetch-depth: 0` | **GREEN** |
| pin 7b | `0 of 21 citing docs resolved, 20 unbound, **0 failing**` | `1 of 21 resolved, 20 unbound, **2 failing**` |
| pin 8 | **RED, naming the INSTRUMENT** — *"⚠ A FAULT, and NOT a verdict — this clone is SHALLOW, so the needles may name commits it cannot see"* (**repaired**, see below; it read `refusal-verdict-parity: the needle matches **0** commits, not 1` before) | `refusal-verdict-parity -> e5cce77 = fb6cddf^` ✓ |

Two separate lies, and only the first is loud — **the third the repair closed rather than
recorded.** 7a reported a **fault in a verdict's register** — it
told the reader to deepen a clone that does not exist, which is precisely the conflation that check was
split out to prevent, arriving one layer up. 7b printed **`0 failing`** — a clean bill of health from an
instrument that could not read, the vacuous-green shape its own anti-vacuity clause exists to catch and
which the clause did catch, but on the *floor* rather than on the truth. **Pin 8 used to call the one
correctly bound docket `BAD`, and it is the arm this release repairs:** it now claims its two faults —
a tree that cannot be asked for its own history (by the command's **return code**, the idiom 7a already
uses) and a **shallow clone whose truncation actually BIT**, the one shape a return code cannot see,
since a shallow clone answers `rc=0` with a log that is merely short — and on either it FAILS naming
the instrument instead of reporting on documents. MEASURED on a `--depth 1` clone: **2173 passed / 3
failed**, pin 8 RED with that fault message, 7a and 7b failing exactly as tabulated above. A count is
not the damage here: `46` differs from `45` by one, and
the lies are invisible in the total. **So the correction below is not "the archive run was off by
one" — it is that the archive run's history-reading verdicts were never about `fbfe07e`.**

Any pin that invokes `render_html.py` carries `--no-open` (PR B adds none, but the discipline stands).

### The checks

**All nine rows are implemented and measured.** The two-tree run that measured them — `fbfe07e`
scripts + the branch harness, on the **clone-based** base tree the note above requires: **2131 passed /
45 failed**, against the branch's **2176 passed / 0 failed**. Both totals are **2176**, which is what
makes the pair comparable — and the 45 reds carry **37 `v0.4.36` labels and 8 `v0.4.37` labels, with 0
unlabelled**, so the split back to each PR is by label rather than by memory. **37 is PR A's own
count**, measured on a tree carrying only PR A's checks; PR B stacks on it and contributes the 8. A RED
count belongs to the triple and is never carried across an edit — these are re-measured, not inherited.

⚠ **What moved here, and what did not — the distinction is the measurement.** This paragraph first read
*2129 / 45* against *2174 / 0*. Re-measured after the instrument repair above, **the red count (45) and
both label counts (37 / 8) reproduce to the digit**, while the *total* moved by two — so the
correction is confined to the total, and the red-evidence the nine rows rest on never changed. **Which
two checks the total gained is deliberately NOT stated**: the recorded run's harness no longer exists,
so the delta is arithmetic rather than a measurement, and naming its members would be exactly the move
this family exists to stop — a fact about the tree sourced from something other than the tree. The
total is a fact about the harness and is stated with its revision; the per-row evidence is a fact about
`fbfe07e` and is unaffected.

⚠ **Check 7 is the suite's first history-reading check**, and that is a property of the claim rather
than an implementation detail: a bound citation's whole point is that it will *not* resolve on the live
tree, so the check must read `git show <sha>:<path>`. Its verdict therefore depends on **clone depth**
— `ci.yml` carries `fetch-depth: 0` for it — and it holds an **anti-vacuity clause** (`15 <= ran`),
because without it a shallow clone would skip every doc and print a green that measured nothing. A
missing revision **fails** rather than skipping: "this clone is too shallow" is a FAULT, and a fault
and a verdict must not share a message.

| # | check | family | label | flips on pre-fix code? |
| --- | --- | --- | --- | --- |
| 1 | `:71`'s figures equal `cliff_pct` on the same inputs | 1 | **PIN** | yes — 25 ≠ 24 |
| 2 | prose and G-A3's fixture cannot disagree | 1 | **PIN** | yes — today they do |
| 3 | every flag `cm`'s heredoc advertises is accepted by the parser | 2 | **PIN** | yes — `--plan` → rc=2 |
| 4 | the prose names exactly the assets the upload line carries, and no `all <N>` claim disagrees with that count | 3 | **PIN** | yes — **twice over**: the prose says three against the upload's two, *and* `SECURITY.md` never names `SHA256SUMS` at all. Ground truth is the **upload line's own filename list**, read from **plainly** flattened workflow text — so a commented-out upload cannot still supply its filenames; the prose is read from **comment-marker-stripped** text, because `" ".join(t.split())` crosses a newline but **not** the `#` leading the next line. The pre-fix phrase wraps as `` `attaches all` ``⏎`` `#          three` ``, so plain flattening made the count arm read **`none`** — and the token arm reddened anyway, hiding a dead arm behind a live one. The count arm therefore also requires a **non-empty** extraction: an absent claim and an unread one must not share a representation. ⚠ Stated limit: that arm's matcher is the literal `all <N>` wording, so an over-claim phrased otherwise evades it |
| 5 | the provenance destination the prose names is the action's | 3 | **PIN** | yes — currently untested. ⚠ The **limit is on the check**: the attestations-API destination is `actions/attest-build-provenance`'s own behaviour and is not decidable from the tree, so what is asserted is the **fail-safe half** — no prose clause carries both `provenance` and `GitHub Release`, and no provenance-shaped artifact rides the upload line. The clause split is on `[.;—]` and **not** the em dash alone, because the corrected comment is one dash-free run containing both terms |
| 6 | every citing doc declares the revision its coordinates resolve on | 4 | **PIN** | yes — **20** of the pre-fix corpus's **21** citing docs declare no revision at all, over the scope+matcher named under *"The census reproduces"* above (79 files scanned there; the citing 21 are those carrying a citation *under that matcher*). ⚠ Stated because *"unbound docs"* is **two predicates** and a gate that names neither is the defect class it gates: this row asserts docs with **no binding at all** (20 / 21), while a doc that *has* a binding can still carry individual cites that do not resolve — that second reading belongs to check 7, and they are deliberately separate rows so neither can mask the other. ⚠ These numerals are **matcher- and scope-bound and moved when the matcher did**: the family's own census section records `C 284/19 · A 410/28 · B 471/10` over the same tree, and this check's matcher is wider still (the `.js` extension, the en dash, comma-lists, and a range's END), so `18 of 19` became `20 of 21` when it was widened — a count missing either coordinate is not a fact about the tree |
| 7 | every citation resolves **at its doc's declared revision** — the file exists there and the line is in range, resolving by **content** where two files share a name | 4 | **PIN** | yes — **20 of the 21 citing docs declare no revision at all**, so the check has no revision to resolve against, and the anti-vacuity clause (`15 <= resolved`) fails on its own at `resolved = 1`. ⚠ **The floor is not the only arm, and saying so is a measurement rather than a reassurance:** the ONE pre-fix doc that *is* bound reddens it independently, with **2 ambiguous** cites — the bare `SKILL.md` cite at lines 64–66, where the cited line fits **both** the memory skill and the beta-tester's **own** skill file, so the content rule reports ambiguity where a name-only rule would have passed them. ⚠ This sentence read *"the beta-tester's vendored copy"* until it was measured, and the correction is load-bearing rather than pedantic: the canary directory under `fixtures/canary-v0.1.19/` vendors **no `SKILL.md` at all** (six `.py` files, `README.md`, `SHA256SUMS`), and a vendored copy is this row's own **EXCLUDED** verdict — so had the second file really been a vendored copy, the content rule would have excluded it and there would have been no ambiguity to report. The row would have argued itself out of its own example. ⚠ **Written as prose on purpose:** naming a broken coordinate *as* a `file:line` would make this sentence a citation of it, and the gate would then redden on the sentence rather than on its subject — the repair for a coordinate you are *showing* rather than *making* is an anchor. ⚠ **Reframed, and the reframing is the measurement.** This row previously read *"the cited line carries the **phrase** the sentence claims"*. That is not implementable at usable precision, and the measurement says so rather than the intuition: over the largest already-bound doc (`refusal-verdict-parity.spec.md`, 99 citations at its declared `e5cce77`), an automatic phrase extractor — the backticked identifiers in each citing line — finds **74 citations with no identifier to check at all**, and on the remaining 25 extracts phrases including the literal `` `True` `` and the word `` `operations` ``, of which **14 "fail"**. ⚠ **Re-measured CORPUS-WIDE, and it is the stronger form of the same finding:** over all **494** citations in `docs/**/*.md`, **313 (63%)** carry no extractable identifier on their citing line; widening the scope to the citing *sentence* and admitting quoted phrases still leaves **172 (34%)**. The two matchers disagree on the figure, as every count in this family does — and the **lower** of them is a third of the corpus. So the ~56% above is not an artifact of reading one document. A false-failure rate like that is a gate that fires on correct content, and by the rule stated above it is a gate nobody reads. **The phrase gate survives only where a doc supplies the phrase itself** — which is why the plan could supply six and not 284. ⚠ **Resolution is by CONTENT, not by name**, and that is itself a measured call: a bare `SKILL.md:NNN` matches TWO files (the memory skill's and the beta-tester's), and in the live corpus all **29** such cites fit **only** the memory skill, because the beta file is shorter than the cited line. ⚠ **And the rule is load-bearing rather than decorative — the pre-fix corpus is the counterexample:** 27 such cites there, of which the resolvable ones split **15 fit only the memory skill and 2 fit BOTH**. So "fit only" is a property of *this* corpus, not of the naming convention; the rule that carries it is that a citation resolves iff **exactly one** admissible file can *carry* it — "ambiguous by name" is not the verdict "ambiguous", and only the second fails. A third verdict is the canary under `fixtures/canary-v0.1.19/`, whose vendored copies are byte-faithful to another version: **EXCLUDED**, never ABSENT |
| 8 | a defect docket's binding is the **parent of the commit that fixed its rows** — re-derived from history, not trusted from the table | 4 | **PIN** | yes — pre-fix, **six of the seven dockets declare no binding at all**, so the rule has nothing to hold for them (the seventh, `refusal-verdict-parity`, is bound — it is the doc whose `fbfe07e` binding check 7's ambiguity arm reads). ⚠ **The table names SEVEN dockets and the first draft named two** — a universal over a class it had sampled a fraction of, which is the same defect one layer up. The other five were added only after each was **independently probed** and found to satisfy the rule (`binding == fixing_commit^`), because a row added on the strength of the first two's agreement would have been an assertion sourced from the author's expectation rather than from history. ⚠ **And the scope is a set of VERIFIED BINDINGS, never a class** — MEASURED 2026-09-19, when this row read *"the five dockets are the corpus's ONLY docs whose base revision is DERIVABLE"*: **22** of this repo's docs carry a `**`X`-numbered**` note, and only these seven have had a fixing commit's subject phrase derived and measured unique, so the row's own warning applies one layer up. The two added by that measurement, `dbt-truth-restoration` and `signal-pipeline-hardening`, bind to `6ac5380` and `ceaccc0`; unlike the other five their bindings have ONE child each, so the needle's work there is uniqueness rather than discrimination. ⚠ **The needle is now required to be UNIQUE in the log** (`len(hits) != 1` reddens): the loop took the *first* match, so a needle matching two commits silently bound the earlier one — a lookup that answers with the wrong row rather than with nothing. ⚠ **This row is not the one first designed.** It was specified as *"a repair-stance sentence asserts the repaired phrase"* — a phrase matcher, and row 7's measurement already refuted that class at ~56% false-failure. What survived is the part that is **re-derivable**: probing `audit-hygiene-remediation`'s A4 row across three revisions found the DEFECT at one (`except …: return ""`), its FIX at the next (`_GIT_WARNED`, `global _GIT_WARNED`), and an unrelated region at the third — so a docket binds to the revision its fix landed *against*, and the binding is checkable by two git commands any reader can re-run. The needle is a phrase from the **fixing commit's subject**, so the matcher reads history and never the document's prose, which is what keeps it out of the family it is checking |
| 9 | every string in `REQUIRED_IN_README` is present with **no whitespace inside it** — a wrapped one is not an anchor | 5 | **GUARD** | **no** — by this repo's own rule: no anchor rule existed before it, so it cannot fail on pre-fix code. ⚠ **Reframed twice, both times by measurement.** It was specified as *"whitespace-normalized phrase matching finds a wrapped phrase"*: (a) that is a **find-the-needle** assertion, and the subject that matters is the **registry**, because the reader that mattered matched `re.escape(needle)` over the RAW file and a needle containing a space stops matching the moment the source wraps it — ⚠ **and the two roles have since SWAPPED, which is the shipped shape**: `check_required_strings` now runs the whitespace-TOLERANT pattern (so its *"no longer mentions"* is true of genuine absence only), while the strict `re.escape` read is the first arm of THIS check. The pair is a true partition, asserted over a **seven-case table** carried inside the check (contiguous · table-wrapped · prose-wrapped · line-end-wrapped · stray-space, plus two CONTROLS — a longer token and genuine absence — that neither matcher may call a break), because the README fixture cannot reach every shape the guard must handle; (b) **normalizing whitespace to a single space cannot detect a wrap at all** for this registry, because every needle is space-free — `docs/network-guide.md` wrapped reads as `docs/network- guide.md`, which matches nothing. The shipped matcher instead interleaves the needle's re-escaped characters with `\s*` and reads the **RAW** file (tests/docs_links.py:`_ws_tolerant`), which finds a wrap **without the haystack ever being flattened** — and that is load-bearing rather than cosmetic, because the boundary lookarounds read neighbours that flattening deletes: the helper's own docstring measures it (a prose-wrapped needle — `` `Run the /cm- ``⏎`` sync verb` `` — with its whitespace removed reads `` `Runthe/cm-syncverb` ``, and **both** boundaries fail: a word character on each side, so a wrapped needle would read **ABSENT**, the exact false verdict this check exists to prevent). Mutation-verified, because a guard that has never fired is not a guard: wrapping BOTH of README's occurrences reddens it, and wrapping one does **not** — the raw reader still matches the other, so a mutation's effect belongs to the fixture as much as to the code. ⚠ **Scope: the registry, not the corpus, and the reason is the GUEST POSTURE.** `CLAUDE.md` lines 32–33 are the measured instance (`` `claude plugin validate ``⏎`` ./plugins/consolidate-memory --strict` ``) and are deliberately **out** of scope: the two-CLAUDE.md rule makes the *user-global* file the strictly-read-only half, so a bare `CLAUDE.md` anchor resolves to the PROJECT file — guest-WRITABLE, edited report-then-apply with each change gated. A gate that reddens on it would demand an edit this pass may not make **unilaterally**, not one it may never make; the two halves of the rule take different remedies (a proposal, versus silence). ⚠ **Scope: WHITESPACE breaks only** — the check's MESSAGE used to read *"contiguous"*, which claims every separator while the matcher reaches exactly one, and a break from anything else (a table-cell boundary, a soft hyphen, inline markup) is NOT covered. That boundary is stated rather than silent because the separator class is unbounded, and a guard that must be complete over an unbounded class has to INVERT rather than enumerate |

Checks 6–8 close the "31 stale citations" docket row, and **each flips on a different evidence set** —
which is what Family 4's own prose requires. Check 6 flips on the **absent bindings** (20 of the 21
citing docs declare no revision at all — a presence check on bindings, not on ranges); check 7 flips
from the other side (a declared revision that resolves, and citations that resolve against it — the
clause that stops a binding being vacuous) **and independently on two genuinely ambiguous citations
that the ONE already-bound doc's binding exposed**; and check 8 flips on neither of those, because it
asserts the third thing they cannot: that a binding is **re-derivable**. A constant that is plausible
passes checks 6 and 7 and fails only check 8.

⚠ **The three-claims split is the design, not redundancy.** *Named* (6), *true* (7), *derivable* (8)
are three independent failures with three different repairs — add the line, fix the number, find the
real commit — and any one of them can hold while the others do not.

⚠ **What changed, and why the section above had to be rewritten rather than patched.** The docket's
premise was *"six citations point at the wrong thing"*. Re-measured one revision at a time, all six are
right — at revisions nothing in their documents names. So **checks 6–7 no longer hunt wrong citations;
they make a declaration checkable**, which is the whole of what this family can honestly deliver. The
phrase hunt was the plan's answer to a defect that measurement removed, and it does not survive contact
with its own precision budget — the measurement is **row 7's** *"Reframed, and the reframing is the
measurement"*, where an automatic extractor leaves **34–63% of the corpus's 494 citations with no
identifier to check at all** — a third of it even under the most generous matcher.

⚠ **This sentence used to cite that measurement as a bare line number, and the repair is worth recording
because it is this PR's own rule turned on this PR.** A bare `` `:N` `` is the one citation form the
gate's matcher **cannot see at all** — `_CITE47` requires a `path.ext` before the colon, which is why
matcher `B` (471 hits, 10 files at `fbfe07e`) sits outside the census's reach entirely — so nothing ever
read the reference, and it was **mis-aimed from the moment it was written**: the line it named holds the
RED-count rule, not a precision budget, and no later edit ever contradicted it because no reader exists
to contradict it. **A coordinate the matcher cannot reach is not a weaker citation, it is an uncited
one** — and the repair for a self-reference is the same as for any other: an anchor, never a number,
because a document's own line numbers are the most volatile coordinates it has. The number is left out
of this paragraph on purpose: writing it here would make this sentence carry the very citation it is
repairing, which is how the earlier repair of an *illustrative* coordinate in this same document went
wrong before it was caught.

**One matcher constraint every remaining phrase check inherits** — check 8, and check 9's matcher.
A whitespace-TOLERANT pattern recovers a phrase wrapped at a space; it does *not* recover one wrapped across a
line whose continuation carries source characters. `memory_status.py:715-716` is a comment, so its
continuation opens `# ` — and the `#` is source, which is why the Family 1 quote above carries it.
Measured both ways: normalizing the phrase without the `#` misses, with it hits. So a quote spanning a
break must reproduce the continuation line's leading run — as both Family 3 quotes already do
(`:250-256`) — or the check returns a false RED on exactly the wrapped quotes it was added to find.

⚠ **And this is not hypothetical: it already happened once in this family, in check 4.** There the
matcher was the *consumer* of a wrapped phrase rather than the producer, and the failure ran the
opposite way — `" ".join(t.split())` left the `#` in place, the count arm read `all # three`, and it
reported **no claim** where a claim existed. A wrap that breaks a phrase produces a **false RED** in a
matcher reading for presence; the same wrap produces a **false GREEN** in a matcher reading for
absence. Both are the same bug, and the repair is the same: strip the marker, and never let an
extraction be empty without saying so.
