# The firewall's linearity guard — design-of-record

**Status: implemented.** Target release: **v0.4.28 (patch)** — the ReDoS guard in `tests/smoke.py`
is re-based on measurement: a CPU clock, bounds derived from a stated admission rule, and **two**
checks for the one instance no timing bound can cover — a behavioural one, and an exact-text
assertion of the arm (§4.1).

> **What changed after this document first shipped.** The eyJ half went to adversarial review and
> came back **six** one-token evasions of a single design: A′/B′/C (three ways past a `re.X`-unaware
> text scan), D (a `|` that was a character-class *member*), F1 (a `|` inside a group) and F2 (a `]`
> in first class position). Each restored the full blowup with the pin reading **green**. The
> conclusion was not a seventh rule — it was that a scan returning a *verdict* about linearity is
> undecidable in practice, since a pattern can be catastrophic with every quantifier bounded (N1).
> The pin now asserts the arm's **text**, which is decidable and makes scanner bugs fail **safe**.
> §4.1 carries the full history and the 22-case matrix; §5 gap 1 and §8 carry what the new design
> does *not* cover. The behavioural check is the one piece the first revision did not have.
>
> **One more correction, made during this rewrite.** An earlier draft of §4.1 listed the
> nested-bounded mutant among the things the behavioural check *catches*. Re-running the matrix
> falsified it: that check **hangs** on it, and because it runs first, the exact-text pin's verdict
> is never reached in a real run. It is caught by the job timeout. Recorded at both sites rather
> than quietly dropped — the claim had been written from the design's intent instead of from the
> measurement, which is the defect class this cycle exists to fix.

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
   top of that range. A runner 2.3× slower trips it, which is what CI did. **Both figures are
   wall-clock, because that is the clock the old guard read** — and that qualifier is load-bearing
   rather than pedantic: §2.2 measures the same scan inflating **17.7×** on wall against **5.8×** on
   CPU under load, so "2.3× slower" is a far smaller ask of a *machine* than it sounds. The new
   bound's margins are CPU-clock, and §8 states the machine allowance in its own units.

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
Measured by timing the **same scan the guard performs** — `ms._SECRET.search` on the guard's own
payloads at the guard's own sizes (`"a1b2-c3d4." * 2400`, `"x" * 47980 + "password" + "y" * 12`,
`"authorization" + " " * 23987`), bracketed in `process_time()` exactly as the block brackets it —
seven trials per interpreter across **two passes**, taking each interpreter's **floor**. The last
row is not timed at all: it is the verdict of exec'ing the committed guard block **verbatim** (the
slice §9's recipe takes), which is how all five checks were separately confirmed to pass, at their
real bounds, under all five interpreters:

| payload @ n | 3.10.12 | 3.11.15 | 3.12.13 | 3.13.15 | 3.14.6 | spread |
| --- | --- | --- | --- | --- | --- | --- |
| dotted @ 24 000 | 0.0343 | 0.0373 | **0.0387** | 0.0341 | 0.0333 | 1.16× |
| alnum @ 48 000 | **0.1391** | 0.1293 | 0.1294 | 0.1229 | 0.1118 | 1.24× |
| authz @ 24 000 | 0.0058 | 0.0060 | **0.0068** | 0.0058 | 0.0055 | 1.24× |
| the behavioural eyJ check | pass | pass | pass | pass | pass | — |
| the exact-text pin | pass | pass | pass | pass | pass | — |

(Worst reading per payload in bold.) **This table carries readings and the spread only** — the
bounds live in §3.1 (derivation) and §4 (the guard), and are deliberately not restated here. That
is not a style preference: the first version of this subsection *did* restate them, and the §3.1
re-derivation moved the bounds without moving this table, leaving a second copy of every bound and
a margin argument computed from the stale ones. One table is how the drift happened; not keeping
two is how it stays fixed.

**The floor — and not one reading per interpreter — is itself a finding.** A second pass through the
five moved 3.13's alnum reading from 0.1229 to 0.2115, a **72%** swing; that is §3.1's defect
appearing on a different axis, a single reading presenting as a tight number. And a *ratio* divides
two such readings, so independent noise does **not** cancel in it — it adds. The `spread` column is
therefore honestly read as **an upper bound on the version effect, not a precise factor**: the true
systematic difference is no larger than what is tabulated, and may be smaller. The arithmetic below
composes a deliberately pessimistic number.

**3.14.6 is fastest on all three payloads; the worst reading falls on 3.12.13 for two of the three
and on 3.10.12 for one.** There is **no age trend.** An earlier draft of this subsection reported
"older is slower", with 3.10 owning the worst reading on two payloads, and leaned on that to argue
the axis favours the 3.8 runner this patch exists for. Re-measured as a floor over trials rather
than as a single reading, it does not survive: 3.12.13 — this box's own reference interpreter, and
neither the oldest nor the newest — is the slowest on dotted and authz. The argument it supported has
to be given up with it, which is the honest cost: **the version axis cannot be extrapolated from
these five interpreters to 3.8 at all.** What is bounded here is the observed spread among the
interpreters that exist on this box, **≤1.24×**, and nothing beyond it. The evidence for 3.8 remains
the CI matrix — which is where the flake was observed in the first place.

**The spread is not free, and correcting §3's arithmetic is what makes that visible.** Version
composes with the admission margin rather than sitting beside it: dotted — the tightest bound, at
**2.16×** — would have `1.24×` of that consumed, leaving **1.74×** for box speed. The pre-correction
text called a `1.42×` spread "about a third of the 4.2× allowance", which was arithmetically true of
the pre-correction margin; the re-derivation made the cushion smaller, not the spread. Version *and*
a slower box together can therefore consume dotted's margin, which is the trade R1 names in §8.

One method note: these runs were taken with another process holding ~48% of a core, which is not the
quiet box §9 asks for. It does not corrupt them, for the reason §2.2 selects this clock — the reading
is per-process CPU, so a competitor costs second-order cache effects rather than direct descheduling.
Within-interpreter floor-to-ceiling spread was usually ≤2% but not always (3.10's dotted spanned
0.0343–0.0373, 8.7%, on the second pass), which is the same instability the floor rule absorbs.

The exact-text pin is flat across all five **by construction**, and that is the point of choosing a
source pin over a behavioural one: it reads `pattern` — a string — and the interpreter decides only
what that string *does*, never what it *says*. No `re` engine difference can move it, and unlike the
verdict-scan it replaced, no `re` engine *syntax* difference can move it either. The behavioural eyJ
check beside it is timed like the other three and passes under all five, but it carries the same
version exposure they do rather than the pin's structural immunity.

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

**Five checks.** Three behavioural, one per admitted payload; and **two** for the eyJ arm — a
behavioural one and an exact-text one (§4.1) — since v0.4.28, because the two see mutant families
neither can see alone. The census constant moves with it: `1750 + 45` = **1795**, up from
`origin/main`'s `1750 + 43` by **+2** — the v0.4.27 `.dim` guard pin, and this cycle's behavioural
eyJ check. The exact-text pin *replaced* the structural check that was already there, so it costs no
slot. (An earlier draft of the `docs/network-graph-interaction.spec.md` row read "unchanged (no
smoke pin was added)" against a four-check guard; the two constants refute it — the delta *is* the
pin.)

Each timing check interpolates its measured value into the check NAME, so a failure is
self-diagnosing without re-instrumenting:

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

### §4.1 The eyJ pin — the arm's text, asserted exactly

The eyJ arm's defense *is* its caps, so the guard asserts them directly. Since v0.4.28 it does so
**two ways**, on two axes that see disjoint mutant families:

| | what it asserts | what it is blind to |
| --- | --- | --- |
| **(1) behavioural** | the repeated-anchor payload (`"eyJ" × 600`, len 1800) stays under a derived bound | every mutation that is behaviourally **inert** at that payload |
| **(2) structural** | the arm's source text IS the shipped text, **verbatim** | a catastrophic **sibling branch** — outside its scope by construction |

**Why (2) is exactness, and not a verdict.** The v0.4.27 guard extracted the arm and scanned it for
open quantifiers — returning a *verdict* about the arm. Six review rounds each walked through that
scan, every one a **one-token** edit that restored the full blowup with the pin reading **green**:

| evasion | what it exploits | old pin |
| --- | --- | --- |
| **A′** a newline right after `eyJ` | whitespace is insignificant under `re.X`, so the arm is unchanged to the engine — but the naive `[^\|\n]*` stops at the newline and truncates the arm to `eyJ` itself. The pattern is 105 lines, so wrapping is the house style, not an exotic edit. | PASS |
| **B′** a `(?#…)` group right after `eyJ` | the very next character is `#`, so `split("#", 1)[0]` truncates identically. | PASS |
| **C** a mention of `eyJ` in an **earlier arm's comment** | the scan finds *that* mention first and pins the comment, so the real arm is never examined at all. | PASS |
| **D** a `\|` inside a character class | the scanner tracked classes — it had to, for the comment rule — and then **discarded the tracking at the split**, so `[A-Za-z\|_]` cut the arm at 36 chars and left `[A-Za-z0-9_-]*` in the **discarded tail**. | PASS |
| **F1** a `\|` inside a **group** | the same discard at a different syntax site: `eyJ(?:[A-Za-z0-9_-\|x])*…` splits at the in-group pipe and the open quantifier lands in the discarded fragment. | PASS |
| **F2** a `]` **first** in a class | CPython reads an unescaped `]` in first position as a literal MEMBER, so `eyJ[]\|A-Za-z0-9_-]*…` is one class carrying a `*` — but the scanner ended the class at that `]` and split at the now-exposed `\|`. | PASS |

A′, B′ and C are failures of the same thing — not stripping `re.X` the way the engine does. D was
the same failure at a second site, and F1/F2 at a third and fourth. Six rounds, six different
unmodelled syntax rules, six false PASSes. That is not a bug tail: it is a **wrong design**. A scan
that reads an arm and returns a *verdict* about linearity is undecidable in practice — (1) exists
because of `eyJ(?:[A-Za-z0-9_-]{8,2000}){8,4000}`, which is catastrophic with **every quantifier
bounded** — so such a scan will always have holes, and **every hole is a false PASS**.

Asserting the arm's **text** is decidable, and it makes the scanner's own bugs fail **safe**: a
missed comment, a missed class close, or a `|` split in the wrong place can only produce a string
that **differs** from the literal. A false PASS now requires the branch to be byte-identical to the
shipped branch. That is the property none of the six designs before it could state.

**Depth is deliberately not tracked, and that is measured rather than assumed.** The obvious repair
for D/F1/F2 is paren-depth tracking — split only at depth 0. Measured on the shipped pattern: the
whole alternation is wrapped in `(?:…`, so **every** branch sits at depth 1 and a depth-0 split
collapses all 48 into **one 12 868-char arm** — which trips on the shipped pattern. Splitting at
every `|` outside a class is what yields the branch; and with the text asserted verbatim, a split in
the wrong place no longer matters, because the fragment cannot *equal* the literal.

**What (2) does not cover.** `LIT|X` leaves `LIT` present as a `|`-delimited span, so the pin passes
while a new sibling branch `X` goes unexamined. That is §5's gap 1 in sharpened form: the pin's
scope is the anchor's branch **by construction**, and no scan of that shape can be widened to cover
the alternation without asserting the whole pattern — which would trade this hole for a false-alarm
surface across all 48 branches.

**Where (1) comes in.** (1) is the check that *can* see outside the branch, and it is also the
independent oracle on (2)'s scanner. Its division of labour is measured, not assumed, and it is
narrower than it first looks: a cap replaced by `*`, replaced by `+`, or deleted is **inert** at
that payload (`eyJ*` still matches, then the required `\.` fails at the first position), as is an
open quantifier appended to the arm's end (nothing follows it to backtrack against). Those rows are
(2)'s alone. What (1) catches is the **ambiguous** shapes — a starred group before the capped
segment, an open quantifier after one, a `]`-first class — measured at **2.91–2.95 s** against
0.0099 s shipped (**294–298×**).

**N1 is the argument, not a coverage row — and the matrix says so.** The nested-bounded mutant
(`eyJ(?:[A-Za-z0-9_-]{8,2000}){8,4000}`, every quantifier bounded, exponential) is *why* a
verdict-scan is undecidable: no scan of the source can conclude "this arm is linear" while it
exists. It is **not** a thing (1) catches — measured, (1) **hangs** on it (it blew a 20 s cap at
k=200), and because (1) runs first in the block, the pin's verdict on that mutant is never reached
in a real run. The detection is the **job timeout**, which is a RED job. That is the failure mode
recorded as safe in §4.1's last paragraph, and it is the only honest description: on N1 the guard
does not return a verdict at all, it stops. (An earlier draft of this document listed "nested
bounded" among the things (1) catches. The matrix falsified that in the same run that produced the
table — the mutant's own row reads `hung`, not `TRIP`.)

**(1)'s failure time is not bounded, and that is recorded rather than papered over.** The three
table payloads are fixed runs, so a regression against them costs at most that mutant's own
measurement (≤16.2 s). (1)'s mutant family contains an **exponential** member — two nested bounded
quantifiers blew a 20 s cap at k=200 — and no stdlib `re` timeout exists to interrupt a running
search. The backstop is therefore the **job**: `timeout-minutes: 15` on ci.yml's `test` job, which
had none while its siblings carried 10. A subprocess with a timeout would bound it in-process and
was **rejected** (§6.5): it would put §9's slice-and-exec re-derivation out of reach for one check,
and every mechanism added to this guard so far has become a hole. The failure **mode** stays safe
either way — a mutant the check cannot finish reading is a RED job, never a green check.

**How bad the evasions were.** D, F1 and F2 are not narrow misses — they are the worst regressions
anywhere in this document, and they grow faster than quadratically. D, measured at its own sizes:

| mutant | n=1500 | n=3000 | n=6000 | per doubling | vs shipped |
| --- | --- | --- | --- | --- | --- |
| shipped scan | 0.0076s | 0.0208s | 0.0479s | 2.3–2.7× | — |
| `[A-Za-z\|_]` + open tail (D) | 1.7052s | 13.0803s | 76.8100s | 5.9–7.7× | **225× → 1604×** |

The shipped pattern is unaffected — **0** in-class pipes, checked — so this was a hole reachable only
by a mutation, never a wrong verdict on the code it guards. That is exactly why it survived a cycle
that was *about* this class of defect, and exactly the kind of hole a verdict-scan can never close.

The lesson is the one §1.3 records twice already, arriving a sixth time: **modelling a syntax partway
is worse than not modelling it at all.** Every one of the six evasions is a rule that was present,
correct, and applied at one site and not another — and the site that *was* modelled is what made the
unmodelled one read as covered.

**What exactness buys, precisely.** It does not make the scanner correct; it makes the scanner's
incorrectness **survivable**, which is the whole point:

- The scanner runs on the **pattern source text**, not on input.
- Classes and escapes are consumed as units, so `[A-Za-z0-9_-]`'s literal `-` and the arm's `\.` are
  never mistaken for quantifier characters — but unlike the design it replaces, a class is kept
  **verbatim**, not folded to `C`. A fold is a lossy reading, and the one thing this check must not
  do is read lossily: `[A-Za-z0-9_-]` and `[a-z]` fold to the same token, which would hide a charset
  edit — a real narrowing of the sweep that no timing payload can see.
- The arm **count** is asserted (`== 1`), so a moved anchor fails rather than silently passing.
- Every failure direction is the same direction. A missed comment, a missed class close, or a `|`
  split at the wrong site can only produce a string that **differs** from the literal — so a scanner
  bug reads **RED**, never green. This is the property the previous six designs could not state, and
  it is why the evasion cycle ends here rather than at the seventh round.

**Validated: 22 cases, and six of them are the ones the previous pin could not see.** Every variant
asserts its edit applied **and** that the subject was the full pattern before the pin is consulted:
`str.replace` with a non-matching needle silently does nothing, so an unasserted mutation re-tests
the shipped pattern and certifies a pin it never exercised — and an edit assert alone does not catch
a wrong *subject* either, since `SEG.replace(SEG, X)` legitimately applies. (Four of an earlier
draft's eleven cases were no-ops for the first reason, and four rows of the first matrix harness
were fragments for the second.)

| class | cases | verdict |
| --- | --- | --- |
| controls | shipped; two legitimate reformats; an **unrelated arm** edited (`glpat` cap 100 → 900) | PASS — no false alarms |
| the evasions, alone | A′ newline · B′ `(?#…)` · C earlier-comment mention | PASS — correct: alone they restore no blowup |
| the evasions, alone | D in-class `\|` · F1 in-group `\|` · F2 `]`-first class — **these two arrive with a blowup attached** | TRIP |
| tokens + a restored blowup | T1/T2/T3 each paired with a reverted cap, and T1 again with a starred group | TRIP |
| reversions | caps reverted (`{8,}`) · written as `*` · as `+` · deleted · a quantifier appended to the arm's end | TRIP |
| edits | **caps PERMUTED** · **cap WIDENED behind a comment mention** · a cap re-tuned · a new open quantifier before an intact cap · the anchor branch duplicated | TRIP |
| catastrophic | **N1 — two nested bounded quantifiers** | **(1) hangs; (2) TRIPs.** Caught by the job timeout — see below. |

Lining that matrix up against the pinned revision `c8f4012` — the state this cycle inherits — gives
the number that matters: **six rows read PASS there and TRIP here.** The starred group (F1), the
`]`-first class (F2), **the caps PERMUTED**, **a widened cap hidden behind a comment mention**,
newline + starred group, and N1. Two of those rows are not evasions at all but plain errors the old
pin could not express: the three caps are a *set* to a scan that checks each one is present, and a
permutation keeps every member; and a comment mention ahead of the arm reintroduces C — so the
"widening is covered" claim in the previous revision's own gap list was true only for a widening
that nothing else was hiding behind. That is the difference between a pin that checks for the
presence of the right tokens and one that checks for the right text.

**Each evasion token is tested twice, and the second half is the one that matters.** A′/B′/C *alone*
restore no blowup — a newline after `eyJ` is insignificant under `re.X`, so that mutant is
semantically the shipped pattern, and **PASS is the correct verdict for it**. They are **compound**
evasions: the token matters only paired with a restored blowup. A matrix that tested only the token
would demand a false alarm; one that tested only the blowup would never exercise the evasion at all.
Both halves are in the matrix, and an earlier draft of this validation had the first half and called
it coverage.

**A probed negative worth recording.** The obvious way to smuggle an open quantifier past a *text*
scan is to exploit `re.X`, which ignores unescaped whitespace — so `{8, }` would read as `{8,}` to
the engine while carrying a space the matcher does not expect. Measured: it does not work. Python's
tokenizer decides `{8, }` is not a valid quantifier **before** verbose whitespace-skipping applies,
so the brace becomes a literal and the space is then dropped from that literal — the fragment
matches the text `A{2,}` and does **not** match a run of ten `A`s. Under the exactness assertion the
question is moot in any case: `{8, }` is not the shipped text, so it fails on the comparison without
the scanner needing a rule about it at all. Recorded because the *reason* it is not a hole is what
makes exactness the right frame — the check no longer has to know which brace-shapes are quantifiers.

## §5 Coverage — what each payload detects

Every mutant was built by reverting its fix in the pattern source, and each was then run through
**the committed guard block itself** — extracted verbatim from `tests/smoke.py` and exec'd against a
recompiled `_SECRET`, rather than through a re-implementation of its predicates. So each cell below
is the real check's own verdict, at the real payload sizes. Idle CPU, seconds:

| mutation (what it restores) | dotted @ 24 000 | alnum @ 48 000 | authz @ 24 000 | eyJ (1) behav | eyJ (2) pin | fires |
| --- | --- | --- | --- | --- | --- | --- |
| *control* (shipped) | 0.035 ✓ | 0.142 ✓ | 0.006 ✓ | ✓ | ✓ | 0/5 |
| **M-R3** keyword inner run open (`{1,40}` → `+`) | 0.036 ✓ | **16.581 ✗** | 0.006 ✓ | ✓ | ✓ | 1/5 |
| **M-R4** keyword repetition open (`{0,8}` → `*`) | **7.172 ✗** | 0.139 ✓ | 0.006 ✓ | ✓ | ✓ | 1/5 |
| **M-R5** URI-creds open (`{0,20}` → `*`) | **1.089 ✗** | **10.645 ✗** | 0.006 ✓ | ✓ | ✓ | 2/5 |
| **M-R6** authz sandwich open | 0.034 ✓ | 0.139 ✓ | **8.377 ✗** | ✓ | ✓ | 1/5 |
| **M-R7** eyJ caps reverted | 0.035 ✓ | 0.140 ✓ | 0.006 ✓ | ✓ **(inert — measured)** | **✗** | 1/5 |

✓ = inside the bound, ✗ = over it. Re-run against the re-derived bounds (0.509 / 3.135 / 0.285);
the counts belong to the triple — restored code, payload, harness — so they are re-measured rather
than carried across the edit. **Every mutant is caught, and every check earns its place.** Each has
a named detector: M-R3 → alnum alone; M-R4 → dotted alone; M-R5 → dotted *and* alnum; M-R6 → authz
alone; **M-R7 → (2) alone**, and (1) is measured **inert** on it rather than merely silent (it
measures 1.00×/1.00×/0.95× separation on the other three payloads too — nothing else in the guard
sees it). The three behavioural payloads therefore each hold a mutant no other payload holds, and
(2) holds the one no payload can.

**The two eyJ checks are not redundant — but the argument is scope, not those matrix rows.** The
widening direction is measured: a cap widened behind a comment mention leaves (1) blind (§4.1's
matrix reads 1.2× at k=800) while (2) trips, so (2) earns its place. The other direction cannot be
shown by the F1/F2/T1 rows, and an earlier draft of this paragraph claimed it did: **those rows are
now caught by (2) as well**, so they show the *old* pin's blindness, not (1)'s necessity. (1)'s
necessity is a scope argument, and it is constructive rather than measured: (2) examines the anchor's
branch and nothing else **by construction**, so a blowup in a *sibling* branch — `LIT|X` leaves `LIT`
present as a `|`-delimited span — or in any other arm is invisible to it, while (1) sees it if that
branch blows up on the payload. Recorded as an argument rather than a row because it is not in the
matrix; stating which of the two it is, is the point.

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

1. **(2)'s scope is the anchor's branch BY CONSTRUCTION.** It examines that arm's text and nothing
   else. An open quantifier introduced into a *different* arm, or into a **new sibling** branch of
   the same alternation, is covered only insofar as (1) happens to detect it — and (1) detects it
   only if that branch blows up on the `"eyJ" × 600` payload. That asymmetry is worth stating
   plainly, because §4.1's whole reason for existing is that no payload can see the eyJ arm — so the
   arm needing a structural check is exactly the arm that has one, and every other arm has none.
   **This gap got narrower in v0.4.28 and the narrowing is a real change, not a rewording.** The
   previous revision read "a pin's coverage is bounded by its extraction, and an extraction is a
   parser; this one was a parser with a hole in it" — the in-class-pipe mutant was *inside* that
   scope and still went unexamined, because what failed was the *reach within* the scope. Exactness
   removes that failure mode: there is no reach to get wrong any more, only a comparison. What
   remains is scope alone, which is a boundary the design states rather than a bug it might have.
2. **Every payload is a non-matching probe.** A matching probe was built and measured —
   `"authorization" + K spaces + "A"*64` — and it does **not** discriminate: pre-fix 3.59s, shipped
   3.93s. Pre-fix the unbounded `\s*` matches it, and post-fix the capped `\s{0,20}` cannot span the
   run at all, so the two versions scan it by different routes at similar cost. Recorded with its
   numbers rather than quietly dropped.

**One gap this cycle closed, recorded because a removal is a claim too.** The pin formerly accepted
a **widened** cap — `{8,2000}` → `{8,9000}` grows the sweep 4.5× while leaving every quantifier
bounded, so the old quantifier test passed it. Earlier drafts listed this here as uncovered, and the
check name carried `NOT covered: WIDENING a cap` to meet the reader at the site. Exactness closes
it, and closes more than the previous revision claimed to: the matrix shows a widening is caught
**even when an earlier arm's comment mentions `eyJ`** — the exact construction that defeated the
verdict-scan's extraction — and so is a **permuted** set of caps, which satisfied the old
"all three literals present" test while moving the sweep from 4 000 to 200. The cost is a new
false-positive mode: any re-tune of a cap now fails the check until the figure is re-measured. That
is the intended prompt — the spec requires a re-measurement for any cap change — but it is a real
change in the check's behaviour and belongs in the record rather than in a release note.

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

### §6.5 A subprocess with a timeout, to bound (1)'s failure — rejected

The obvious way to bound the behavioural check's failure time is to run it in a child with a timeout,
since no stdlib `re` timeout exists to interrupt a running search (§4.1's last paragraph). **Rejected
on two grounds.**

The first is that it would cost more than it buys. (1) exists because it is the one check that sees
past (2)'s scope; the reason §9's recipe matters is that it re-derives the guard's verdicts from the
committed tree, exec'ing the real block against a recompiled `_SECRET`. A subprocess boundary puts
that check out of reach of the recipe for one check and not the others — so the recipe would report
the four remaining verdicts and a fourth green where there should be five, which is the exact failure
§9's own `assert len(out) == 5` was written to catch. Either the recipe loses a row or it grows a
second execution path, and a recipe with two paths is a recipe whose readers trust the wrong one.

The second is the record. **Every mechanism added to this guard so far has become a hole**: a
verdict-scan gained an extraction, the extraction gained a class rule, the class rule gained a split
and lost its state, and six one-token evasions came out of the gaps between them (§4.1). Adding
process management, signal handling and a timeout surface to a check whose *whole design premise* is
that it must fail safe, in order to convert a RED job into a slightly faster RED job, is the same
move again — a mechanism bought with a new failure surface to improve a case that is already
correct.

What was done instead: `timeout-minutes: 15` on ci.yml's `test` job, which had none while its
siblings carried 10. It bounds the same case at the level where the resource actually is — ~18× the
job's **measured** 50s, so it cannot flake — and it adds no code to the guard.

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
version axis separately at **≤1.24×**, and cannot be extended past the five interpreters installed
here — so the remainder is for a genuinely slower machine, the trade R1 names rather than a margin
that is free.

**It does not claim to detect cap widening any more — it now does, and that is a behaviour change
worth naming.** The exact-text pin requires the eyJ arm to *be* the shipped text (§4.1), which closes
the widening gap earlier drafts recorded as uncovered — and, measured, closes it in two constructions
the older "the three literals are present" test accepted: a widening hidden behind a comment mention,
and a **permuted** set of caps. The cost is that any legitimate edit to that arm now fails the check
until the text is re-measured — a **re-tune** of a cap, or a repair of the arm that works a different
way. That is intended, and it is a wider trip-wire than the previous revision's: a reader meeting
this check should know the failure may mean "the cap moved" rather than "the cap is open", and the
check name says so.

**It should not be read as covering the alternation.** The exact-text pin examines the anchor's
branch and nothing else, **by construction**; a new sibling branch is invisible to it, and the
behavioural check sees one only if it blows up on the eyJ payload (§5 gap 1). This is the one place
where v0.4.28's design is *narrower* than a reader might assume rather than wider, which is why it is
stated here as well as in §5.

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
              smoke.index("_redos_jwt_lit)") + len("_redos_jwt_lit)")]
out = []
exec(compile(block, "<guard>", "exec"),
     {"ms": types.SimpleNamespace(_SECRET=ms._SECRET),
      "check": lambda name, ok: out.append((name, ok))})
assert len(out) == 5, f"guard block yielded {len(out)} checks, expected 5"
for name, ok in out:
    print(f"{sys.version_info[:3]} {'PASS' if ok else 'FAIL'} {name[:70]}")
```

Re-measure `S*` and `M` on the tree you are shipping: both belong to the triple (the code, the
payload, the harness), never to this document. The `assert len(out) == 5` in snippet 4 is not
decoration — a block slice keyed on line-shaped markers fails by *silently* returning fewer checks,
and a recipe that reports four green checks where there are five has hidden a failure rather than
found one. (It read `4` until v0.4.28 added the behavioural eyJ check; the `.index()` end marker
moved with it, from the old pin's `not _redos_jwt_missing)` to `_redos_jwt_lit)`, which is the last
line of the block. Both were updated together precisely because only the assert would have caught
the marker going stale.)

## §10 Provenance of every number

| tier | what | how a reader checks it |
| --- | --- | --- |
| re-derivable from the committed tree | §2.1, §2.3 shipped columns, §2.4 pre-fix and shipped, §5 matrix, §4.1's **22** pin cases and the mutant table's per-doubling readings, §7's headroom and the two non-guards, the three bounds | §9's recipe, against the committed `_SECRET`; the mutant table by compiling the in-class-pipe pattern and timing it against the shipped scan; **the six `c8f4012`-evaded rows by running both pins against `git show c8f4012:tests/smoke.py`** — the only row class here whose evidence is a *comparison* between two revisions rather than a reading |
| **re-derivable only by rebuilding the harness** | §4.1's **22-case matrix, as a whole**, and §2.5's two new eyJ rows | The matrix's *cases* are fully specified in §4.1's table — which edit, at which syntax site, expecting which verdict — so a reader can reconstruct it; the harness that produced it is **not committed**, and is not in the tree. Stated as its own row rather than folded into the one above because that is the honest tier: the six `c8f4012` verdicts are checkable against two committed revisions, but the **count of 22** is checkable only by rebuilding the runner. (The two §2.5 rows are the exception inside this row: those come from §9's recipe verbatim and are tier 1.) |
| re-derivable from the committed tree, but only by re-running it | §4.1's N1 row: **(1) hangs, (2) trips** | exec the behavioural half alone against a pattern with two nested bounded quantifiers — it does not return within 20 s at k=200. The `(2)` verdict comes from running the pin slice **without** the behavioural check ahead of it, since in the real block the hang means (2) is never reached |
| re-derivable by scanning the pattern | the **20 unbounded quantifiers** in live arms (§8's companion in `SECURITY.md`) | strip `re.X` comments, collapse `[classes]`→`C` and `\x`→`E`, count `[*+]\|\{\d+,\}` — 22 raw, 20 after the collapse (2 are literal `+` inside classes) |
| re-derivable by reading a file | `SECURITY.md`'s cap-coverage claim: `facts_manifest.py` caps at 4 MiB, `sync_global.py` does not | `os.read(fd, 4 * 1024 * 1024)` versus an uncapped `path.read_text` in `_safe_read_text` |
| re-derivable given the interpreters | §2.5 | §9's recipe under each of 3.10–3.14, **floor** over 7 trials × 2 passes; requires all five installed |
| re-derivable only with the stress harness | §2.2, §3.1's `S*` column, §2.3's `S*` column | §9 plus 48 spinners, worst-of-3-batches; readings vary with core count |
| derived from rows above, not a fresh measurement | §6.1's 4.6×–883× and §6.3's clearance argument | divide §2.3's mutant column by its `S*` column; §6.3's monotonicity is §2.1's linear shipment against a quadratic revert |
| **extrapolated** from measured endpoints, labelled as such | §6.2's ~1.6× margin at n = 96 000, and the n ≈ 160 000 admission point | §2.1 (linear) + §2.4's table (quadratic) + §3.1's 6.32× inflation held constant — no reading exists at those sizes |
| measurement, not reproduced here | the CI flake itself (one red job, five cancelled) | `gh api repos/.../actions/runs/<id>/jobs` — job conclusions, never the checks table |

The CI flake is the only claim in this document that the maintainer cannot re-derive locally: it
was observed once, on a runner that is not this box, and its evidence is a workflow run. It is what
prompted the work; it is not what justifies the design. §2.2 stands on its own.
