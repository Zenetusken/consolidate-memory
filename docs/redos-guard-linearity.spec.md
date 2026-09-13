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

### §2.3 Separation from pre-fix code

Each instance's fix is a bounded quantifier. Reverting it restores O(n²). Owning mutant idle CPU vs.
shipped, at the sizes the guard uses:

| payload @ n | shipped idle | shipped **loaded** (`S*`) | weakest owning mutant (idle) | separation |
| --- | --- | --- | --- | --- |
| dotted @ 24 000 | 0.0344 | 0.0627 | M-R5 (URI-creds open) 1.097 | 17.5× |
| alnum @ 48 000 | 0.1389 | 0.7718 | M-R3 (inner run open) 16.215 | 21.0× |
| authz @ 24 000 | 0.0058 | 0.0094 | M-R6 (authz sandwich open) 8.364 | 890× |

### §2.4 The eyJ arm's window is EMPTY

Reverting the JWT arm's three caps (`{8,2000}`/`{8,4000}`/`{6,200}` → `{8,}`) gives, idle CPU:

| n | pre-fix | shipped | separation |
| --- | --- | --- | --- |
| 2 000 | 0.0119 | 0.0118 | 1.00× |
| 8 000 | 0.1208 | 0.0660 | 1.83× |
| 32 000 | 1.6648 | 0.2822 | 5.90× |

**This is not a narrow window; it is an empty one, and it can be shown so.** The arm's cost is
`occurrences × sweep`, and the sweep is capped, so the achievable separation is only `≈ n / cap`.
Substituting the load factor: at n = 32 000 the shipped scan reaches `0.2822 × 5.8 ≈ 1.64s` under
load while the pre-fix scan measures **1.66s** idle — they cross there, exactly where the model
predicts. At the guard's own candidate size, n = 24 000, the shipped scan under load (**1.20s**)
already *exceeds* the pre-fix scan measured idle (**0.94s**). No threshold exists to place.

At n = 48 000 separation finally reaches 8.6× — the largest payload whose shipped cost is
affordable, and still well under the admission rule below. Whatever the size, the enforceable
property is the caps themselves, so that is what the guard asserts (§4).

### §2.5 A third axis: interpreter version

§3's bounds carry an allowance for a slower **machine**. Version is a separate axis, and it is the
one that matters most here: the runner that actually failed was **3.8**, the oldest in the matrix.
Measured by exec'ing the committed guard block verbatim against the shipped pattern under each
locally available interpreter, one at a time on a quiet box:

| payload @ n | 3.10.12 | 3.11.15 | 3.12.13 | 3.13.15 | 3.14.6 | spread | bound | worst margin |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| dotted @ 24 000 | **0.044** | 0.037 | 0.039 | 0.037 | 0.031 | 1.42× | 0.26 | **5.9×** |
| alnum @ 48 000 | 0.139 | 0.135 | **0.134** | 0.123 | 0.113 | 1.23× | 3.54 | 25.5× |
| authz @ 24 000 | 0.006 | 0.006 | 0.007 | 0.006 | 0.005 | 1.40× | 0.28 | 40.0× |
| the structural pin | pass | pass | pass | pass | pass | — | — | — |

Two things follow. **Older is slower** — 3.10 owns the worst reading on two of the three payloads
and 3.14 the best on all three — so the axis leans in the safe direction for the 3.8 runner this
patch exists for, rather than against it. And the spread across the whole supported range is
**≤1.42×**, about a third of the 4.2× allowance the tightest bound carries: version alone cannot
consume that margin, though version *and* a slower box together could, which is the trade R1 names.

The structural pin is flat across all five **by construction**, and that is the point of choosing a
source pin over a behavioural one: it reads `pattern` — a string — and the interpreter decides only
what that string *does*, never what it *says*. No `re` engine difference can move it.

**Recorded gap.** 3.8, 3.9 and macOS are not installable here, so the evidence for the two oldest
runners is the CI matrix, not this table.

## §3 The admission rule

Stated so that every bound is *derived* rather than chosen:

> A payload is admitted only if `sqrt(M / S*) ≥ 4`, where `S*` is the worst shipped CPU time over 5
> trials under the standard stress load and `M` is the **weakest** owning mutant's idle CPU time.
> The bound is then placed at their **geometric mean**, `sqrt(S* × M)`.

The geometric mean splits a total separation of `k` into two equal margins of `sqrt(k)`, so neither
side is the accidental weak one. The rule reduces to "both margins ≥ 2×", and it makes the two
failure directions symmetric and explicit:

- **False red** if a runner is slower than `sqrt(M/S*)` relative to this box — the `S*` side.
- **False green** if a regression is milder than `sqrt(M/S*)` — the `M` side.

A payload that cannot clear 4 is not admitted at any size. That is what §2.4 refuses for the eyJ arm.

## §4 The guard

Three behavioural checks, one per admitted payload, and one structural check for the eyJ arm. Each
timing check interpolates its measured value into the check NAME, so a failure is self-diagnosing
without re-instrumenting:

| payload | n | bound | each side's margin | pre-fix cost (bounds the failure) |
| --- | --- | --- | --- | --- |
| dotted/dashed run | 24 000 | 0.26s | 4.2× | 7.20s (M-R4) |
| pure-alnum run + trailing keyword | 48 000 | 3.54s | 4.6× | 16.22s (M-R3) |
| authorization + padding spaces | 24 000 | 0.28s | 29.8× | 8.36s (M-R6) |

Two structural properties of the predicate, both load-bearing:

- **`0.0 < dt < bound`.** The lower half catches a **dead clock**: a `process_time()` that returned a
  constant would otherwise make every bound vacuously green. This is the same reasoning as the
  repo's "a pin is only a pin if it fails on pre-fix code" rule — a predicate that cannot be
  dissatisfied is not a check.
- **The failure is bounded by construction.** Payloads are fixed, so the worst case is the mutant's
  own scan (≤16.2s), never an unbounded wait. There is deliberately **no** "hang backstop" claim: a
  post-hoc comparison cannot bound a runaway, because the runaway completes before it is evaluated.

### §4.1 The structural pin

The eyJ arm is pinned by the property its caps encode — *every quantifier in that arm is bounded*.
Implementation notes that are not incidental:

- The scan runs on the **pattern source text**, not on input.
- Char classes collapse to `C` and escapes to `E` **first**. `[A-Za-z0-9_-]` contains a literal `-`
  and the arm's `\.` is an escape; a naive scan reports both as quantifier characters.
- The quantifier pattern is `[*+]|\{\d+,\}` — which matches `{8,}` but **not** `{8,2000}`, so
  widening a cap does not trip it (see §5, gap 1). Matching only open-ended forms is what keeps a
  legitimate finite cap from reading as a failure.
- `bool(_redos_jwt_arm)` is asserted too, so the check fails — rather than silently passing — if the
  anchor moves and the arm is no longer found.

Validated against three removal styles: reverting a cap to `{8,}` trips it, and so does writing the
same cap as `*` or as `+`.

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
| *control* (shipped) | 0.035 ✓ | 0.139 ✓ | 0.006 ✓ | passes | 0/4 |
| **M-R3** keyword inner run open (`{1,40}` → `+`) | 0.034 ✓ | **16.195 ✗** | 0.006 ✓ | passes | 1/4 |
| **M-R4** keyword repetition open (`{0,8}` → `*`) | **7.157 ✗** | 0.139 ✓ | 0.006 ✓ | passes | 1/4 |
| **M-R5** URI-creds open (`{0,20}` → `*`) | **1.077 ✗** | **10.569 ✗** | 0.006 ✓ | passes | 2/4 |
| **M-R6** authz sandwich open | 0.034 ✓ | 0.139 ✓ | **8.366 ✗** | passes | 1/4 |
| **M-R7** eyJ caps reverted | 0.034 ✓ | 0.139 ✓ | 0.006 ✓ | **FAIL** | 1/4 |

✓ = inside the bound, ✗ = over it. **Every mutant is caught, and every check earns its place.** Each
has a named detector: M-R3 → alnum alone; M-R4 → dotted alone; M-R5 → dotted *and* alnum; M-R6 →
authz alone; **M-R7 → the structural pin alone** (it measures 1.00×/1.00×/0.95× separation on the
other three payloads — nothing else in the guard sees it). The three behavioral payloads therefore
each hold a mutant no other payload holds, and the structural pin holds the one no payload can.

The measured pre-fix figures also confirm the check names' interpolated values to within 0.3%:
16.195 vs 16.22 (alnum/M-R3), 7.157 vs 7.20 (dotted/M-R4), 8.366 vs 8.36 (authz/M-R6).

**Sizes are load-bearing in this table.** M-R5's alnum reading is 2.715s at n = 24 000 — *under* the
3.54s bound — and 10.569s at the shipped n = 48 000, *over* it. A table that mixed the two sizes
would report the wrong verdict for that cell, which is exactly the error an earlier draft of this
document made.

### The two recorded gaps

1. **Widening a cap is caught by nothing.** Raising the JWT arm's `{8,2000}` to `{8,10000}` widens
   the sweep 5×; the structural pin accepts it (§4.1) and no timing bound can see it (§2.4). The
   guard's own check name says `NOT covered: WIDENING a cap`, so a reader meets the limit where the
   check is rather than only here.
2. **Every payload is a non-matching probe.** A matching probe was built and measured —
   `"authorization" + K spaces + "A"*64` — and it does **not** discriminate: pre-fix 3.59s, shipped
   3.93s. Pre-fix the unbounded `\s*` matches it, and post-fix the capped `\s{0,20}` cannot span the
   run at all, so the two versions scan it by different routes at similar cost. Recorded with its
   numbers rather than quietly dropped.

## §6 Rejected alternatives

### §6.1 The ratio `t(4n) / t(n)` — rejected on measurement

This was the first design, and it is attractive because a ratio cancels machine speed. It cancels
only a **uniform** scale factor, and load inflation is not uniform:

- shipped ratio tail under load (interleaved, CPU clock, reps=9): **10.34**
- weakest mutant ratio: **11.21**

A 1.1× gap — overlapping distributions, so the assertion would have been a coin flip dressed as a
test. Absolute CPU separation at the same sizes is 17×–890× (§2.3), roughly 25× more headroom. A
ratio also cannot be re-derived by a reader from a single measurement, while an absolute bound can.

### §6.2 A behavioural eyJ pin at n = 96 000 — rejected

It clears the admission rule (~17× separation, 4.1× margin) but needs a **20s** bound, which means a
**~84s** failure time, and adds 4.9s of loaded runtime to every suite run — to catch one mutant the
structural pin already catches at zero marginal cost. Buying a behavioural arm by making the
failure mode four times more expensive than the slowest one it already has is a bad trade.

### §6.3 A uniform n = 48 000 across all payloads — rejected

It works (margins 5.9× / 4.6× / 42×), but raises authz's failure time from 8.4s to **33.7s** for no
gain: authz's separation is 890×, so it needs no extra size to clear the rule.

### §6.4 A matched-path payload for the keyword arm — not adopted

Measured and non-discriminating; see §5 gap 2.

## §7 The class finding — three guards, one clock (follow-up, not this patch)

`tests/smoke.py` carries two other wall-clock guards: the commit-subject cap check (bound 2.0s,
23× headroom) and the archive one (bound 60s over a microsecond-scale gap). Both are genuinely loose
and neither has flaked. They are **not** changed here — a patch correcting one guard should not
silently re-base two others — but they share the defect's *cause*, and switching their clock is a
one-line change each. Recorded so the next person does not have to rediscover the wall-versus-CPU
inflation table in §2.2 in order to find out that it applies to them too.

## §8 What this guard does not claim

**It is a measured bound, not a proof of linearity.** Each bound sits **4.2×–29.8× above the worst
shipped reading measured under a load harsher than CI actually showed** (§2.2, §2.3). That
allowance is the explicit price of dropping the ratio, and it is the honest way to state it: a
runner more than 4.2× slower than this box, under that load, could trip the dotted check. The
alternative — a ratio — was measured and does not discriminate (§6.1). Both endpoints are given here
rather than left implicit, and the check names carry the margin so a failure is diagnosable at the
site.

The guard also does not detect cap widening (§5 gap 1), and it says so in the check name itself.

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
pat = ms._SECRET.pattern
arm = re.search(r"eyJ[^|\n]*", pat).group(0)
open_arm = (arm.replace("{8,2000}", "{8,}").replace("{8,4000}", "{8,}")
               .replace("{6,200}", "{6,}"))
assert open_arm != arm, "the pattern moved; re-derive this spec"
mutant = re.compile(pat.replace(arm, open_arm), re.I | re.X)

# 3. The bound, from the rule (§3): sqrt(S* * M), with S* the worst LOADED shipped
#    reading over 5 trials and M the WEAKEST owning mutant's IDLE reading.
S_loaded, M_idle = 0.0627, 1.097          # the dotted row of §2.3
assert (M_idle / S_loaded) ** 0.5 >= 4, "payload does not clear the admission rule"
print("bound =", (S_loaded * M_idle) ** 0.5)

# 4. Interpreter sensitivity (§2.5): exec the guard's OWN block, so what prints is the check's real
#    verdict at its real bound — not a re-implementation. Re-run under each interpreter.
import types
smoke = open("tests/smoke.py", encoding="utf-8").read()
block = smoke[smoke.index("# --- v0.1.70 security: ReDoS"):
              smoke.index("_redos_jwt_body))") + len("_redos_jwt_body))")]
out = []
exec(compile(block, "<guard>", "exec"),
     {"ms": types.SimpleNamespace(_SECRET=ms._SECRET),
      "check": lambda name, ok: out.append((name, ok))})
for name, ok in out:
    print(f"{sys.version_info[:3]} {'PASS' if ok else 'FAIL'} {name[:70]}")
```

Re-measure `S*` and `M` on the tree you are shipping: both belong to the triple (the code, the
payload, the harness), never to this document.

## §10 Provenance of every number

| tier | what | how a reader checks it |
| --- | --- | --- |
| re-derivable from the committed tree | §2.1, §2.3 shipped columns, §2.4 pre-fix and shipped, §5 matrix, the three bounds | §9's recipe, against the committed `_SECRET` |
| re-derivable given the interpreters | §2.5 | §9's recipe under each of 3.10–3.14; requires all five installed |
| re-derivable only with the stress harness | §2.2, the `S*` column of §2.3 | §9 plus 48 spinners; readings vary with core count |
| measurement, not reproduced here | the CI flake itself (one red job, five cancelled) | `gh api repos/.../actions/runs/<id>/jobs` — job conclusions, never the checks table |

The CI flake is the only claim in this document that the maintainer cannot re-derive locally: it
was observed once, on a runner that is not this box, and its evidence is a workflow run. It is what
prompted the work; it is not what justifies the design. §2.2 stands on its own.
