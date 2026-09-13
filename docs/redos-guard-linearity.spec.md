# The firewall's linearity guard — design-of-record

**Status: implemented.** Target release: **v0.4.28 (patch)** — the ReDoS guard in `tests/smoke.py`
is re-based on measurement: a CPU clock, bounds derived from a stated admission rule, and a
structural pin for the one instance no timing bound can cover.

## §1 What was wrong

On 2026-09-13 the v0.4.27 release PR came back **six red**. Triaged by job *conclusion* — not by the
checks table — it was **one** real failure, `test (python 3.8)`, plus five siblings GitHub
**cancelled** under the matrix's implicit `fail-fast: true`. The one failure was this guard.

### §1.1 It was not a regression

Re-running the identical commit gave 13/13 green. The firewall's scan is linear on every payload the
guard carries (§2.1 is a straight 2.00× per doubling). The defect was in the **guard**, and raising
the bound would have hidden it: the guard was measuring something that could not discriminate.

### §1.2 Two causes, both measured

1. **The clock.** The guard bracketed its scan in `time.time()` — WALL time — so every descheduling
   landed directly in the reading. The JWT payload, the one that flaked, inflates **17.7×** under
   load on wall against **5.8×** on `time.process_time()` over the identical scan (§2.2).
2. **The margin.** Its 2.0s bound left 2.2× over that payload (0.891s measured here), not the
   "deliberately loose … ~0.005-0.19s" headroom its comment claimed — the JWT payload is 4.7× the
   top of that range. A runner 2.3× slower trips it, which is what CI did.

Neither cause is visible from the code. Both are visible in ten minutes of measurement, which is
what this document is: every number below was measured on the maintainer's box (24 cores,
CPython 3.12.13) with the machine verified quiet (`ps -eo pid,etimes,pcpu,args`) before each idle
run. §9 is the recipe.

### §1.3 The reasoning had already survived one correction

This is the **third** pass over the same `SECURITY.md` bullet, and the history is the point.
v0.1.12 corrected it from *"linear (no nested quantifiers)"* to *"no catastrophic backtracking —
each alphanumeric run and its required separator are disjoint, so there's no ambiguity to blow up"*,
and the changelog recorded that as **"same property, accurate wording."** It was not the same
property. The replacement claim was *checkable* and false, and v0.1.70's measurement falsified it
four times.

The lesson is not "someone was careless" — the disjointness argument is plausible, and it survived a
documentation review precisely because it reads like the right kind of argument. It is that a
security claim phrased as a *reason* rather than as a *measured bound* has nothing behind it: the
first version was unfalsifiable shorthand, the second was falsifiable and wrong. The replacement
states a number, its margin, and what it does not cover.

**And the third pass nearly failed the same way — which is why this subsection is kept.** The draft
that replaced the disjointness argument asserted *"the regexes are built from bounded quantifiers,
and that is the actual defense"*: another reason-shaped claim, over the same regex, and just as
checkable. It is false — the live pattern carries **20 unbounded quantifiers** in non-comment arms.
The corrected bullet says the narrower true thing (the quantifier that can sweep a separator-free
run is bounded, **at the four instances**) and attributes the rest of the pattern's linearity to
measurement rather than to argument. A claim about this regex has now been wrong twice, in the same
direction, and both times the tell was identical: it read like the right kind of argument. That is
the case for stating numbers and coverage limits even when — *especially* when — a reason would be
more persuasive.

Payload shapes, used throughout (`n` = payload length in chars):

| name | generator |
| --- | --- |
| `dotted` | `"a1b2-c3d4." * (n // 10)` — the original pentest PoC shape |
| `alnum` | `("x" * (n - 20)) + "password" + ("y" * 12)` — a separator-free run + trailing keyword |
| `jwt` | `"eyJ" * (n // 3)` — the repeated-anchor attack |
| `authz` | `"authorization" + (" " * (n - 13))` — the `\s*:?\s*` sandwich |

## §2 The measurements

### §2.1 The shipped scan is exactly linear

`time.process_time()`, idle, seconds. Every doubling costs 2.00× — the firewall is not the defect:

| n | dotted | alnum | jwt | authz |
| --- | --- | --- | --- | --- |
| 6 000 | 0.0086 | 0.0172 | 0.0475 | 0.0014 |
| 12 000 | 0.0171 | 0.0346 | 0.1011 | 0.0030 |
| 24 000 | 0.0344 | 0.0693 | 0.2084 | 0.0058 |
| 48 000 | 0.0686 | 0.1389 | 0.4238 | 0.0115 |
| 96 000 | 0.1372 | 0.2780 | 0.8514 | 0.0227 |

### §2.2 Wall time is the unstable clock

Standard stress load: 48 busy-loop spinners on 24 cores (2× oversubscription). Max over 5 trials:

| payload @ n | CPU idle → loaded | × | wall idle → loaded | × |
| --- | --- | --- | --- | --- |
| dotted @ 24 000 | 0.0344 → 0.0627 | 1.8 | 0.0343 → 0.1660 | 4.8 |
| alnum @ 24 000 | 0.0693 → 0.4126 | 5.9 | 0.0695 → 1.0161 | 14.6 |
| jwt @ 24 000 | 0.2084 → 1.2037 | 5.8 | 0.2088 → 2.4204 | 11.6 |
| jwt @ 48 000 | 0.4238 → 2.4374 | 5.8 | 0.4240 → 7.4996 | **17.7** |
| authz @ 24 000 | 0.0058 → 0.0094 | 1.6 | 0.0057 → 0.0273 | 4.8 |

**The payload that flaked on CI is the most wall-sensitive shape in the set.** That is the whole
argument for the clock change: `process_time()` charges the process only for time it actually ran,
so preemption enters the reading through second-order cache effects rather than directly.

**One row in this table was itself under-measured, and its siblings are the tell.** dotted reads
1.8× while alnum and jwt read 5.9× and 5.8× — the same kind of scan, on the same box, under the same
load, so a 3× lower inflation is not a property the payload can have. Re-measured it is **~6.9×**,
in line with its siblings. The usable generalization is: **an outlier inflation reading among
siblings means that reading is too low, not that the payload is unusually stable.** This is §3.1's
defect in miniature — a single low sample presenting as a tight, reassuring number — and it is why
§3.1 pins the *method* (worst of three batches) rather than accepting one batch's maximum.

### §2.3 Separation from pre-fix code

Each instance's fix is a bounded quantifier. Reverting it restores O(n²). Owning mutant idle CPU vs.
shipped, at the sizes the guard uses:

| payload @ n | shipped idle | shipped **loaded** (`S*`, worst of §3.1) | weakest owning mutant (idle) | margin `sqrt(M/S*)` |
| --- | --- | --- | --- | --- |
| dotted @ 24 000 | 0.0344 | **0.2360** | M-R5 (URI-creds open) 1.0966 | 2.16× |
| alnum @ 48 000 | 0.1389 | **0.9286** | M-R5 (URI-creds open) 10.5837 | 3.38× |
| authz @ 24 000 | 0.0058 | **0.0096** | M-R6 (authz sandwich open) 8.4735 | 29.7× |

The `S*` column is worst-of-three-batches (§3.1); the "separation" this table used to report was a
single-batch figure, which is the under-measurement §3.1 exists to prevent. Note also that the
weakest owning mutant is not always the one the payload was built for — M-R5 owns **two** of the
three, which is why the bound must key to the weakest *owner* rather than to a nominal pairing.

### §2.4 The eyJ arm's window is EMPTY

Reverting the JWT arm's three caps (`{8,2000}`/`{8,4000}`/`{6,200}` → `{8,}`) gives, idle CPU:

| n | pre-fix | shipped | separation |
| --- | --- | --- | --- |
| 2 000 | 0.0119 | 0.0118 | 1.00× |
| 8 000 | 0.1208 | 0.0660 | 1.83× |
| 32 000 | 1.6648 | 0.2822 | 5.90× |

**This is not a narrow window; it is an empty one, and it can be shown so.** The arm's cost is
`occurrences × sweep`, and the sweep is capped, so the achievable separation is only a constant
times `n / cap`. Measured, that constant is **≈ 0.37**, not 1: at n = 48 000 the model `n/cap`
predicts **24×** and the arm delivers **8.5×**, a 2.8× over-prediction. Ratios of measured
separation to `n/cap` run 0.46 / 0.40 / 0.38 / 0.37 / 0.36 across the sizes probed. The model is
still the right *shape* — separation grows linearly and is bounded by the cap — but quoting `n/cap`
as the achievable separation is optimistic by roughly 3×, which is the wrong direction for an
argument whose conclusion is "no bound fits".

Substituting the load factor: at n = 32 000 the shipped scan reaches `0.2822 × 5.8 ≈ 1.64s` under
load while the pre-fix scan measures **1.66s** idle — they cross there, where the model predicts. At
the guard's own candidate size, n = 24 000, the shipped scan under load (**1.20s**) already
*exceeds* the pre-fix scan measured idle (**0.94s**). No threshold exists to place.

**State the refusal in the rule's own quantities, though, because the idle-to-idle ratio is not what
§3 compares.** The separation column above is mutant-idle over shipped-*idle*; §3 divides mutant
idle by shipped-**loaded**. Measured at n = 48 000, the largest payload whose shipped cost is
affordable: shipped idle 0.4277, pre-fix idle 3.6213 (**8.5×** idle-to-idle), shipped loaded `S*` =
**2.7025** (inflation 6.32×). The rule's quantity is therefore `M/S* = 3.6213/2.7025 = 1.34`, giving
a margin of **1.16×** — against the 2× floor. Admission would need an idle-to-idle separation of
`4 × 6.32 = 25.3×`; the arm delivers 8.5×.

> **This comparison was wrong when the rule read `≥ 4`, and correcting the rule is what exposed it.**
> Under `≥ 4` the idle-to-idle ratio failed the bar too (`sqrt(8.5) = 2.9 < 4`), so quoting the wrong
> quantity happened to reach the right verdict and no one could tell. Under the corrected `≥ 2` the
> wrong comparison **passes** (`2.9 ≥ 2`), so an uncorrected §2.4 would now read as licence to admit
> the eyJ arm. The conclusion survives on the arithmetic, not on the sloppiness that used to
> coincide with it.

Whatever the size, the enforceable property is the caps themselves, so that is what the guard
asserts (§4).

### §2.5 A third axis: interpreter version

§3's bounds carry an allowance for a slower **machine**. Version is a separate axis, and it is the
one that matters most here: the runner that actually failed was **3.8**, the oldest in the matrix.
Measured by exec'ing the committed guard block verbatim against the shipped pattern under each
locally available interpreter, one at a time on a quiet box:

| payload @ n | 3.10.12 | 3.11.15 | 3.12.13 | 3.13.15 | 3.14.6 | spread |
| --- | --- | --- | --- | --- | --- | --- |
| dotted @ 24 000 | **0.044** | 0.037 | 0.039 | 0.037 | 0.031 | 1.42× |
| alnum @ 48 000 | **0.139** | 0.135 | 0.134 | 0.123 | 0.113 | 1.23× |
| authz @ 24 000 | 0.006 | 0.006 | **0.007** | 0.006 | 0.005 | 1.40× |
| the structural pin | pass | pass | pass | pass | pass | — |

(Worst reading per payload in bold.) **This table carries readings and the spread only** — the
bounds live in §3.1 (derivation) and §4 (the guard), and are deliberately not restated here. That
is not a style preference: the first version of this subsection *did* restate them, and the §3.1
re-derivation moved the bounds without moving this table, leaving a second copy of every bound and
a margin argument computed from the stale ones. One table is how the drift happened; not keeping
two is how it stays fixed.

Two things follow. **Older is slower** — 3.10 owns the worst reading on two of the three payloads
and 3.14 the best on all three — so the axis leans in the safe direction for the 3.8 runner this
patch exists for, rather than against it. That last step is an **extrapolation from the measured
trend, not a measurement**: 3.8 is not installable here (§2.5's recorded gap), so the evidence for
the runner this patch is *for* is the CI matrix, not this table. The spread across the whole
supported range, though, is measured: **≤1.42×**. It is a *ratio*, so §3.1's under-measurement
concern cancels in it — both ends move together — which is why this axis can be read from single
quiet runs while `S*` could not.

**The spread is not free, and correcting §3's arithmetic is what makes that visible.** Version
composes with the admission margin rather than sitting beside it: dotted — the tightest bound, at
**2.16×** — would have `1.42×` of that consumed by a 3.10-class interpreter, leaving **1.52×** for
box speed. The pre-correction text called the same 1.42× "about a third of the 4.2× allowance",
which was arithmetically true of the pre-correction margin; the re-derivation made the cushion
smaller, not the spread. Version *and* a slower box together can therefore consume dotted's margin,
which is the trade R1 names in §8.

The structural pin is flat across all five **by construction**, and that is the point of choosing a
source pin over a behavioural one: it reads `pattern` — a string — and the interpreter decides only
what that string *does*, never what it *says*. No `re` engine difference can move it.

**Recorded gap.** 3.8, 3.9 and macOS are not installable here, so the evidence for the two oldest
runners is the CI matrix, not this table.

## §3 The admission rule

Stated so that every bound is *derived* rather than chosen:

> A payload is admitted only if `sqrt(M / S*) ≥ 2`, where `S*` is the worst shipped CPU time
> observed under the standard stress load and `M` is the **weakest** owning mutant's idle CPU time.
> The bound is then placed at their **geometric mean**, `sqrt(S* × M)`.

The geometric mean splits a total separation of `k = M/S*` into two equal margins of `sqrt(k)`, so
neither side is the accidental weak one. **The margin on each side *is* `sqrt(M/S*)`** — that is the
whole of the rule — so "both margins ≥ 2×" and `sqrt(M/S*) ≥ 2` are the same statement, and the
threshold is set by the margin you are willing to defend, not chosen independently of it. It makes
the two failure directions symmetric and explicit:

- **False red** if a runner is slower than `sqrt(M/S*)` relative to this box — the `S*` side.
- **False green** if a regression is milder than `sqrt(M/S*)` — the `M` side.

A payload that cannot clear 2 is not admitted at any size. That is what §2.4 refuses for the eyJ arm.

> **This rule previously read `≥ 4` while claiming to reduce to "margins ≥ 2×".** Both cannot hold —
> `sqrt(M/S*) ≥ 4` demands **4×** margins, i.e. `M/S* ≥ 16`. The inconsistency was load-bearing:
> under a correctly measured `S*` it disqualified two of the three admitted payloads (dotted at
> 2.16× and alnum at 3.38×) *despite* both satisfying the 2× intent, which is how it was caught. The
> arithmetic is corrected here rather than the threshold raised, because 2× is the margin the guard
> actually needs and 4× would have forced payload sizes whose failure cost is not worth paying.

### §3.1 Measuring `S*` — worst-of-batches, not one sample

The rule's `S*` is a **worst case over a distribution**, and reading it once under-measures it: that
is the defect this whole patch exists to remove, and it is easy to reintroduce at the point of
derivation. Held under 48 spinners on 24 cores until `os.getloadavg()[0] ≥ 1.6 × nproc`, three
independent batches of seven trials, `max` over all 21 readings:

| payload @ n | recorded (1 batch × 5) | worst observed (3 × 7) | ratio |
| --- | --- | --- | --- |
| dotted @ 24 000 | 0.0627 | **0.2360** | 3.76× |
| alnum @ 48 000 | 0.7718 | **0.9286** | 1.20× |
| authz @ 24 000 | 0.0094 | **0.0096** | 1.02× |

The dotted payload is the one that moves, and it moves by 3.76× — enough to matter. Under the
recorded 0.0627 the derived bound was 0.26 and the margin against a *reproducible* reading fell to
**1.10×**, thinner than the 2.2× that made the original guard flake in the first place. Reproducing
the whole batch is the difference between a bound that holds and one that merely happened to.

**The control that says this is not box noise:** authz reproduced to 1.02× and alnum to 1.20×, so
the box is comparable to whatever produced the recorded figures. Dotted's 3.76× gap is a property
of the reading, not of the machine — it is the most preemption-sensitive of the three because its
scan is the shortest, so a single descheduling is a larger fraction of its total.

The re-derived bounds, at margins ≥2×:

| payload | `S*` (worst) | `M` (weakest owning mutant) | `sqrt(M/S*)` | bound | was |
| --- | --- | --- | --- | --- | --- |
| dotted @ 24 000 | 0.2360 | 1.0966 (M-R5) | 2.16× | **0.509** | 0.26 |
| alnum @ 48 000 | 0.9286 | 10.5837 (M-R5) | 3.38× | **3.135** | 3.54 |
| authz @ 24 000 | 0.0096 | 8.4735 (M-R6) | 29.7× | **0.285** | 0.28 |

Two of the three bounds move **up** (dotted most of all), which is the direction that buys back the
flake. All four mutants still fire against them (§5).

## §4 The guard

Three behavioural checks, one per admitted payload, and one structural check for the eyJ arm. Each
timing check interpolates its measured value into the check NAME, so a failure is self-diagnosing
without re-instrumenting:

| payload | n | bound | each side's margin | pre-fix cost (names the single-arm revert) |
| --- | --- | --- | --- | --- |
| dotted/dashed run | 24 000 | 0.509s | 2.16× | 7.17s (M-R4) |
| pure-alnum run + trailing keyword | 48 000 | 3.135s | 3.38× | 16.58s (M-R3) |
| authorization + padding spaces | 24 000 | 0.285s | 29.7× | 8.38s (M-R6) |

Two structural properties of the predicate, both load-bearing:

- **`0.0 < dt < bound`.** The lower half catches a **dead clock**: a `process_time()` that returned a
  constant would otherwise make every bound vacuously green. This is the same reasoning as the
  repo's "a pin is only a pin if it fails on pre-fix code" rule — a predicate that cannot be
  dissatisfied is not a check. Measured, this half is load-bearing rather than decorative: with
  `process_time` patched to a constant, all three checks report `dt=0.000` and **fail**, where the
  upper half alone would pass all three.
- **The failure is bounded by construction**, because the payloads are fixed — but the bound is the
  *slowest revert*, not the figure the check name interpolates. Each name carries its own arm's
  single revert (7.2s / 16.2s / 8.4s); reverting **every** instance at once costs more — measured
  M-ALL: dotted 8.190, alnum 26.670, authz 9.651, **44.51s** for the block. Still bounded, and the
  distinction matters because the interpolated number reads as a ceiling and is not one. There is
  deliberately **no** "hang backstop" claim: a post-hoc comparison cannot bound a runaway, because
  the runaway completes before it is evaluated.

### §4.1 The structural pin — two properties, and the label names both

The eyJ arm's defense *is* its caps, so the pin asserts them directly. It asserts **two** things,
and the check name says both, because a predicate and its label saying different things is the
defect class this document exists to correct:

1. **No open quantifier in the arm** — computed on a correctly-extracted arm.
2. **The three caps exactly as measured** — `{8,2000}`, `{8,4000}`, `{6,200}` present as literals.

**Why (1) needs its own extraction, not a scan.** The shipped version was
`re.search(r"eyJ[^|\n]*", pattern)` then `split("#", 1)[0]`. That is a naive text scan, and a naive
text scan does not model `re.X` — which is where all three of its evasions live. Each is a
**one-token** edit that restores the full blowup while the pin reads green:

| evasion | what it exploits | old pin |
| --- | --- | --- |
| **A′** a newline right after `eyJ` | whitespace is insignificant under `re.X`, so the arm is unchanged to the engine — but `[^|\n]*` stops at the newline and the arm is truncated to `eyJ` itself. The pattern is 105 lines, so wrapping is the house style, not an exotic edit. | PASS |
| **B′** a `(?#…)` group right after `eyJ` | the very next character is `#`, so `split("#", 1)[0]` truncates identically. | PASS |
| **C** a mention of `eyJ` in an **earlier arm's comment** | the scan finds *that* mention first and pins the comment, so the real arm is never examined at all. | PASS |

All three are failures of the same thing — stripping comments the way the engine does instead of
the way a text scan guesses. The replacement strips unescaped `#`-to-EOL outside a character class,
plus `(?#…)` groups, **before** splitting the alternation on `|`; it then requires **exactly one**
arm to contain the anchor. Every evasion collapses: A′ and C lose their truncation point, and B′'s
quantifiers become visible. Splitting correctly is the same fix, incidentally — a `|` inside a
comment or a character class is not an alternation either.

**Why (2) exists.** The quantifier pattern `[*+]|\{\d+,\}` matches `{8,}` but **not** `{8,2000}` —
deliberately, so a legitimate finite cap never reads as open. The cost is that **widening** a cap
(`{8,2000}` → `{8,9000}`) leaves every quantifier bounded while the sweep grows 4.5×, and (1) alone
accepts it. Requiring the caps as exact literals closes that. It also means a **re-tune** fires the
check, which is intended rather than tolerated: the spec requires a re-measurement for any cap
change, so the failure *is* the prompt. Loosening the check to silence that would remove the
coverage it was added for.

Other implementation notes that are not incidental:

- The scan runs on the **pattern source text**, not on input.
- Char classes collapse to `C` and escapes to `E` **first**. `[A-Za-z0-9_-]` contains a literal `-`
  and the arm's `\.` is an escape; a naive scan reports both as quantifier characters.
- The arm count is asserted, so the check fails — rather than silently passing — if the anchor moves
  and no arm (or more than one) is found.

**Validated, 12 cases, with a control.** Shipped and two legitimate reformats pass. The three
evasions trip — where the **old** predicate reads PASS on all three. Revert-all-three, a cap written
as `*`, as `+`, widening, re-tuning, and a new open quantifier placed in front of an intact cap all
trip. (Every variant asserts its edit applied before the pin is consulted: `str.replace` with a
non-matching needle silently does nothing, so an unasserted "mutation" re-tests the shipped pattern
and certifies a pin it never exercised. Four of an earlier draft's eleven cases were no-ops for
exactly this reason.)

**A probed negative worth recording.** The obvious way to smuggle an open quantifier past a text
scan is to exploit `re.X`, which ignores unescaped whitespace — so `{8, }` would read as `{8,}` to
the engine while carrying a space the matcher does not expect. Measured: it does not work. Python's
tokenizer decides `{8, }` is not a valid quantifier **before** verbose whitespace-skipping applies,
so the brace becomes a literal and the space is then dropped from that literal — the fragment
matches the text `A{2,}` and does **not** match a run of ten `A`s. `{8, }` is therefore literal text,
not an unbounded quantifier, and the matcher reporting no hit for it is correct rather than a miss.
Closing this out rather than adding a defensive strip keeps the pin's rule honest: it flags open
quantifiers, not brace-shaped literals.

## §5 Coverage — what each payload detects

Every mutant was built by reverting its fix in the pattern source, and each was then run through
**the committed guard block itself** — extracted verbatim from `tests/smoke.py` and exec'd against a
recompiled `_SECRET`, rather than through a re-implementation of its predicates. So each cell below
is the real check's own verdict, at the real payload sizes. Idle CPU, seconds:

| mutation (what it restores) | dotted @ 24 000 | alnum @ 48 000 | authz @ 24 000 | eyJ pin | fires |
| --- | --- | --- | --- | --- | --- |
| *control* (shipped) | 0.035 ✓ | 0.142 ✓ | 0.006 ✓ | passes | 0/4 |
| **M-R3** keyword inner run open (`{1,40}` → `+`) | 0.036 ✓ | **16.581 ✗** | 0.006 ✓ | passes | 1/4 |
| **M-R4** keyword repetition open (`{0,8}` → `*`) | **7.172 ✗** | 0.139 ✓ | 0.006 ✓ | passes | 1/4 |
| **M-R5** URI-creds open (`{0,20}` → `*`) | **1.089 ✗** | **10.645 ✗** | 0.006 ✓ | passes | 2/4 |
| **M-R6** authz sandwich open | 0.034 ✓ | 0.139 ✓ | **8.377 ✗** | passes | 1/4 |
| **M-R7** eyJ caps reverted | 0.035 ✓ | 0.140 ✓ | 0.006 ✓ | **FAIL** | 1/4 |

✓ = inside the bound, ✗ = over it. Re-run against the re-derived bounds (0.509 / 3.135 / 0.285);
the counts belong to the triple — restored code, payload, harness — so they are re-measured rather
than carried across the edit. **Every mutant is caught, and every check earns its place.** Each has
a named detector: M-R3 → alnum alone; M-R4 → dotted alone; M-R5 → dotted *and* alnum; M-R6 → authz
alone; **M-R7 → the structural pin alone** (it measures 1.00×/1.00×/0.95× separation on the other
three payloads — nothing else in the guard sees it). The three behavioural payloads therefore each
hold a mutant no other payload holds, and the structural pin holds the one no payload can.

The measured pre-fix figures also agree with the values the check names interpolate, to within ~2%:
7.172 vs 7.20 (dotted/M-R4), 16.581 vs 16.22 (alnum/M-R3), 8.377 vs 8.36 (authz/M-R6). The alnum
spread is the widest, which is expected — it is the longest scan, so it has the most to lose to a
descheduling — and it is why the names' figures are described as references rather than as ceilings.

**Sizes are load-bearing in this table.** M-R5's alnum reading is **2.682s at n = 24 000** — *under*
the 3.135s bound, so the mutant would go undetected — and **10.645s at the shipped n = 48 000**,
*over* it. A table that mixed the two sizes would report the wrong verdict for that cell, which is
exactly the error an earlier draft of this document made. The margin is also thinner than it looks:
at n = 24 000 the mutant escapes by only **17%**, so this row's size is not a comfortable choice
among equals but the smallest one that works.

### The recorded gaps

1. **The pin is scoped to the eyJ arm.** It examines that arm and nothing else, so an open
   quantifier introduced into a *different* arm is covered only insofar as a timing payload happens
   to detect it. That asymmetry is worth stating plainly, because §4.1's whole reason for existing
   is that no payload can see the eyJ arm — so the arm needing a structural pin is exactly the arm
   that has one, and every other arm has none. Mitigation: the three behavioural payloads are
   measured, so a regression large enough to matter generally lands in one of them. "Generally" is
   the honest word.
2. **Every payload is a non-matching probe.** A matching probe was built and measured —
   `"authorization" + K spaces + "A"*64` — and it does **not** discriminate: pre-fix 3.59s, shipped
   3.93s. Pre-fix the unbounded `\s*` matches it, and post-fix the capped `\s{0,20}` cannot span the
   run at all, so the two versions scan it by different routes at similar cost. Recorded with its
   numbers rather than quietly dropped.

**One gap this cycle closed, recorded because a removal is a claim too.** The pin formerly accepted
a **widened** cap — `{8,2000}` → `{8,9000}` grows the sweep 4.5× while leaving every quantifier
bounded, so §4.1's quantifier test passes it. Earlier drafts listed this here as uncovered, and the
check name carried `NOT covered: WIDENING a cap` to meet the reader at the site. Requiring the three
caps as exact literals closes it. The cost is a new false-positive mode: any re-tune of a cap now
fails the check until the figure is re-measured. That is the intended prompt — the spec requires a
re-measurement for any cap change — but it is a real change in the check's behaviour and belongs in
the record rather than in a release note.

## §6 Rejected alternatives

### §6.1 The ratio `t(4n) / t(n)` — rejected on measurement

This was the first design, and it is attractive because a ratio cancels machine speed. It cancels
only a **uniform** scale factor, and load inflation is not uniform:

- shipped ratio tail under load (interleaved, CPU clock, reps=9): **10.34**
- weakest mutant ratio: **11.21**

A 1.1× gap — overlapping distributions, so the assertion would have been a coin flip dressed as a
test. Absolute separation at the same sizes is **4.6×–883×** — the `M/S*` column behind §2.3's
margins — which is roughly **4× more headroom** than the ratio's 1.1×, not the ~25× an earlier draft
claimed from a pre-§3.1 `S*`. The margin is thinner than that draft implied; the conclusion is
unchanged, because 4× separation still discriminates where a 1.1× gap cannot. A ratio also cannot be
re-derived by a reader from a single measurement, while an absolute bound can.

### §6.2 A behavioural eyJ pin at n = 96 000 — rejected

Earlier drafts rejected this on **cost** — a 20s bound, a ~84s failure time, 4.9s of loaded runtime
added to every suite run. Correcting §3's arithmetic makes the rejection structural instead: it does
not clear the rule at all. The claim that it did (~17× separation, 4.1× margin) read the
**idle-to-idle** ratio — precisely the wrong quantity §2.4's blockquote is about — and it would have
*survived* the corrected `≥ 2` while meaning nothing.

Projected from the measured endpoints (§2.1's linear shipped cost, §2.4's quadratic pre-fix table,
load inflation held at its measured 6.32×), the rule's own quantity at n = 96 000 is
`M/S* ≈ 14.5 / 5.4 ≈ 2.7` — a margin of **~1.6×**, still under the 2× floor. Admission would need
roughly n ≈ 160 000, where the bound is ~19s and a single revert costs ~40s. That is an extrapolation
from measured endpoints and is labelled as one, because the alternative is another single reading
presenting as a tight number — the defect §3.1 exists to prevent.

### §6.3 A uniform n = 48 000 across all payloads — rejected

It works — a quadratic revert's cost grows faster in `n` than the linear shipped scan, so `M/S*`
rises with size and every payload clears the rule at 48 000 — but it raises authz's failure time
from 8.4s to **33.7s** for no gain. authz already carries the largest separation in the set
(**883×**, §2.3), so extra size buys it nothing it needs, and the cost lands entirely on the failure
mode, which is the one number a payload's size should be chosen to keep small. (The "5.9× / 4.6× /
42×" margins an earlier draft quoted here were computed against the pre-§3.1 `S*` and, for alnum,
against a non-weakest owner — the same two errors §3 and §3.1 correct, in a third place.)

### §6.4 A matched-path payload for the keyword arm — not adopted

Measured and non-discriminating; see §5 gap 2.

## §7 The class finding — one other guard shares the clock (follow-up, not this patch)

This section previously reported that `tests/smoke.py` carries **two** other wall-clock guards, each
a one-line clock switch away from being fixed. Checked against the file, that is wrong in both
directions — and the error is the same shape as the ones this patch exists to fix: a claim about
code, written from memory of the code rather than from the code. Corrected here with measurements.

**One genuine sibling exists.** The commit-subject cap check — `_scrub_commit_log` on a
~900,000-char subject, bound 2.0s — brackets its work with `time.time()` exactly as the old firewall
guard did. Measured over 15 wall trials: 0.0929 / 0.0952 / 0.0968 (min / median / max), i.e. **~21×
headroom**. Loose, and the "23×" quoted here before was a single-batch figure of precisely the kind
§3.1 shows is unreliable. It has never flaked and it is **not** changed here — a patch correcting
one guard should not silently re-base another.

It is also **load-bearing**, which "genuinely loose" undersold: remove the cap and the same check
reads **8.19s** against its 2.0s bound. So it detects the regression it was written for rather than
passing vacuously, and its headroom is a budget for a slower runner, not slack.

**The other two are not wall-clock guards at all, so there is no clock to switch.**
- The stacks-cache check asserts `now - stacks_at < 60` — the **age of a stored timestamp**, i.e.
  calendar arithmetic. No interval of work is being timed. `process_time()` measures CPU consumed
  since an arbitrary per-process origin, not wall-clock epoch, so substituting it would compare a
  duration against an epoch and fail for reasons unrelated to the cache.
- The archive bound is `len(_html_p4) < 320 * 1024` — a **character** count of the rendered output.
  Nothing on that path is timed at all, so there is neither a wall clock to replace nor headroom to
  report.

Recorded so the next person does not have to re-derive §2.2's inflation table to find that it
applies to exactly one other check.

**A second class finding — the same claim *shape*, verified rather than assumed.** Two more live
claims in the shipped tree are declared safe by *reason* rather than by measurement, which is exactly
what §1.3 condemns: `extract_signals.py`'s path-only matcher carries "Anchored, non-overlapping →
ReDoS-free" and its ack matcher "`.sub` + emptiness ⇒ ReDoS-free". A prior design-of-record
(`signal-pipeline-hardening.spec.md`) carries the older "no nested quantifiers" form as well, though
for a `_ACK_LEAD` shape that never shipped. So the shape was **measured**, not taken on trust.
**Both hold.** `_PATH_ONLY` — the only one with a failure-prone `$` — reads 2.00×/2.00×/1.99× per
doubling to 1.5M chars on a quoted-token run, and 2.05× at the top of the range out to 6.1M; on the
rival unquoted-token shape it is 2.0× to 384k, takes one ~1.7× step at 768k whose cause is not
identified, then returns to 2.0×, netting ~`n^1.17` over 384k→6.1M — not quadratic, and not
explained away either. `_ACK_VOCAB`/`_ACK_LEFTOVER` are an alternation of literals and a character
class. Both are then fed input capped at `_PROBE_CAP` = **4000** — over 150× below the smallest size
that showed the step, which is what makes the anomaly moot rather than merely small.

So those claims are **true but unfalsifiable as written**: they would read identically if they were
false. That is why they were worth checking, and also why **this patch does not change them** — a
claim that survives its own measurement is not a defect, and rewording it would be cosmetic churn
inside a patch about a claim that did not survive one.

## §8 What this guard does not claim

**It is a measured bound, not a proof of linearity.** Each bound sits **2.16×–29.7× above the worst
shipped reading measured under a load harsher than CI actually showed** (§2.2, §2.3, §3.1). That
allowance is the explicit price of dropping the ratio, and it is the honest way to state it: a
runner more than **2.16×** slower than this box, under that load, could trip the dotted check. The
alternative — a ratio — was measured and does not discriminate (§6.1). Both endpoints are given here
rather than left implicit, and the check names carry the margin so a failure is diagnosable at the
site.

The tightest bound is dotted's, and it is deliberately the one to watch: 2.16× is the least
headroom in the set, so a slower runner or a heavier load shows up there first. §2.5 bounds the
version axis separately at ≤1.42× across the supported interpreters, which leaves the remainder for
a genuinely slower machine — the trade R1 names rather than a margin that is free.

**It does not claim to detect cap widening any more — it now does, and that is a behaviour change
worth naming.** The structural pin requires the eyJ arm's three caps as exact literals (§4.1), which
closes the widening gap earlier drafts recorded as uncovered. The cost is that a legitimate
**re-tune** of a cap now fails the check until the figure is re-measured. That is intended — the
spec requires a re-measurement for any cap change — but a reader meeting this check should know the
failure may mean "the cap moved" rather than "the cap is open", and the check name says so.

**It does not cover arms other than the eyJ arm** (§5 gap 1).

## §9 Measurement recipe

Every number in this document is re-derivable from the committed tree. Run with the box quiet, and
for the loaded column start 48 spinners (`nproc` = 24 here) before the measurement — the idle and
loaded readings must be taken from separate runs, never interleaved with each other's load.

```python
import re, time, sys
sys.path.insert(0, "plugins/consolidate-memory/scripts")
import memory_status as ms

SECS = lambda f: (lambda *a: (lambda t0: (f(*a), time.process_time() - t0)[1])(time.process_time()))

def measure(rx, s, trials=1):
    return max(SECS(rx.search)(s) for _ in range(trials))

# 1. Shipped linearity (§2.1): double n, the time must double.
for n in (6000, 12000, 24000, 48000, 96000):
    print(n, measure(ms._SECRET, "a1b2-c3d4." * (n // 10)))

# 2. A mutant: revert a fix in the pattern SOURCE, then recompile. The eyJ example (§2.4).
#    NOTE: build the mutant from the caps, never from re.search(r"eyJ[^|\n]*") — that naive scan is
#    what §4.1 replaces, and it also returns a COMMENT-STRIPPED arm that is not a substring of the
#    raw source, so pat.replace(arm, ...) would be a silent no-op. Assert every count.
pat = ms._SECRET.pattern
open_pat = pat
for cap in ("{8,2000}", "{8,4000}", "{6,200}"):     # §4.1's three, exactly as pinned
    assert open_pat.count(cap) == 1, f"{cap}: {open_pat.count(cap)} occurrences, expected 1"
    open_pat = open_pat.replace(cap, cap[:cap.index(",")] + ",}")   # {8,2000} -> {8,}
assert open_pat != pat, "the pattern moved; re-derive this spec"
mutant = re.compile(open_pat, re.I | re.X)

# 3. The bound, from the rule (§3): sqrt(S* * M), with S* the worst LOADED shipped reading —
#    worst-of-3-batches x 7 trials, not one sample (§3.1) — and M the WEAKEST owning mutant's
#    IDLE reading. The margin on each side IS sqrt(M/S*); the rule admits at >= 2.
S_loaded, M_idle = 0.2360, 1.0966         # the dotted row, §3.1 / §2.3
claim = (M_idle / S_loaded) ** 0.5
assert claim >= 2, f"payload does not clear the admission rule ({claim:.2f}x)"
print(f"each margin {claim:.2f}x -> bound = {(S_loaded * M_idle) ** 0.5:.3f}")

# 4. Interpreter sensitivity (§2.5): exec the guard's OWN block, so what prints is the check's real
#    verdict at its real bound — not a re-implementation. Re-run under each interpreter.
#    The end marker is the LAST LINE of the guard block; if that line changes, this slice silently
#    truncates or over-reads, so assert on the result rather than trusting the indices.
import types
smoke = open("tests/smoke.py", encoding="utf-8").read()
block = smoke[smoke.index("# --- v0.1.70 security: ReDoS"):
              smoke.index("not _redos_jwt_missing)") + len("not _redos_jwt_missing)")]
out = []
exec(compile(block, "<guard>", "exec"),
     {"ms": types.SimpleNamespace(_SECRET=ms._SECRET),
      "check": lambda name, ok: out.append((name, ok))})
assert len(out) == 4, f"guard block yielded {len(out)} checks, expected 4"
for name, ok in out:
    print(f"{sys.version_info[:3]} {'PASS' if ok else 'FAIL'} {name[:70]}")
```

Re-measure `S*` and `M` on the tree you are shipping: both belong to the triple (the code, the
payload, the harness), never to this document. The `assert len(out) == 4` in snippet 4 is not
decoration — a block slice keyed on line-shaped markers fails by *silently* returning fewer checks,
and a recipe that reports three green checks where there are four has hidden a failure rather than
found one.

## §10 Provenance of every number

| tier | what | how a reader checks it |
| --- | --- | --- |
| re-derivable from the committed tree | §2.1, §2.3 shipped columns, §2.4 pre-fix and shipped, §5 matrix, §4.1's 12 pin cases, §7's headroom and the two non-guards, the three bounds | §9's recipe, against the committed `_SECRET`; the pin cases by mutating the source with asserted counts |
| re-derivable by scanning the pattern | the **20 unbounded quantifiers** in live arms (§8's companion in `SECURITY.md`) | strip `re.X` comments, collapse `[classes]`→`C` and `\x`→`E`, count `[*+]\|\{\d+,\}` — 22 raw, 20 after the collapse (2 are literal `+` inside classes) |
| re-derivable by reading a file | `SECURITY.md`'s cap-coverage claim: `facts_manifest.py` caps at 4 MiB, `sync_global.py` does not | `os.read(fd, 4 * 1024 * 1024)` versus an uncapped `path.read_text` in `_safe_read_text` |
| re-derivable given the interpreters | §2.5 | §9's recipe under each of 3.10–3.14; requires all five installed |
| re-derivable only with the stress harness | §2.2, §3.1's `S*` column, §2.3's `S*` column | §9 plus 48 spinners, worst-of-3-batches; readings vary with core count |
| derived from rows above, not a fresh measurement | §6.1's 4.6×–883× and §6.3's clearance argument | divide §2.3's mutant column by its `S*` column; §6.3's monotonicity is §2.1's linear shipment against a quadratic revert |
| **extrapolated** from measured endpoints, labelled as such | §6.2's ~1.6× margin at n = 96 000, and the n ≈ 160 000 admission point | §2.1 (linear) + §2.4's table (quadratic) + §3.1's 6.32× inflation held constant — no reading exists at those sizes |
| measurement, not reproduced here | the CI flake itself (one red job, five cancelled) | `gh api repos/.../actions/runs/<id>/jobs` — job conclusions, never the checks table |

The CI flake is the only claim in this document that the maintainer cannot re-derive locally: it
was observed once, on a runner that is not this box, and its evidence is a workflow run. It is what
prompted the work; it is not what justifies the design. §2.2 stands on its own.
