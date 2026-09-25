# Dream-teeth coverage — design-of-record

> **Reading the citations.** Every `file:line` below is **`308e15b`-numbered**. Resolve it against
> that commit — `git show 308e15b:<path>` — and **never against the working tree**, which has moved
> them.

**Status: SHIPPED (v0.4.29)** — verified against `CHANGELOG.md` §v0.4.29, which names this spec.
> Drafting-era line, never revisited after the arc closed: Status: draft for adversarial review. Target release: v0.4.29 (patch) — additive
> (The class is now gated — `tests/docs_links.check_spec_status`.)
strictness on gates that were *supposed* to fire; no schema, flag, or install-contract change.

This spec closes the coverage class the `docs/dream-narration-teeth.spec.md` contract forbids and
its implementation nonetheless admits. It is the first of three staged cycles from the 2026-09-14
audit; the record-honesty and index-periphery cycles are separate specs on separate branches.

## §1 Context (measured)

The v0.4.19 contract states the rule twice — *"All checked texts must narrate — the contract has no
partial-arc allowance"* and *"a false clean is permanent and invisible (a fabricated record archived
as performed, poisoning record-side calibration)"* — and its own tie-break is *"Uncertain → fire,
loud and specific."* The implementation takes the one direction the spec forbids. **Measured on the
live tree, against `dream_procedure.judge`:**

```
record:  {"dream": {"sleep": "*", "beats": ["*"]*6, "wake": "w"}}
scan:    zero assistant text blocks; EXT accounted via a --json Bash call
→ verdict : VERIFIED
  reason  : "7/7 narrated · extract_signals.py executed in-window (Phase-2 form)"
  gaps    : []
```

Seven narration slots, no narration, certified. Three independent mechanisms produce it, and they
compose — which is why each must be closed:

**C1 — the checked set silently shrinks.** `dream_procedure._checked_texts` admits a stanza only
when `isinstance(x, str) and x.strip()`. A beat that is `null`, `{}` or a number does not *fail* the
check — it **leaves the set**. Measured: `beats: [null]*6` yields a checked set of exactly
`['sleep']`; `[{}]*6` the same; a mixed record yields `['sleep', 'beats[1]', 'beats[3]', 'beats[5]']`.
The denominator of the coverage claim is therefore under the record's control. The sharpest
consequence is not the all-empty case but the *mixed* one: a record with six `null` beats and a
narrated sleep — EXT accounted — is certified **`verified`, "1/1 narrated"**. One narration for a
seven-slot record, and the reason is true only of the set the record chose to present.

**C2 — the numerator counts labels, not coverage.** `judge`'s `_gaps` opens with
`if not needle: continue`. `normalize_beat_text('*')` is `''` (`_checked_texts`' own `strip("*")`),
so every `'*'` slot is skipped — while the reason string's numerator is `len(checked)`. The count
asserts coverage the check had just declined to perform. Measured: the `'*'` record returns
`7/7 narrated` **both** against a transcript with zero text blocks and against one that narrates the
sleep — the certification is unconditional, because all seven needles normalize to empty regardless
of what the transcript says.

**C3 — the arc gate cannot see a beat's type.** `memory_status.arc_completeness` counts
`len(beats)` and never inspects the entries; `sleep`/`wake` go through `str(v or "")`, so a truthy
non-string (`[1]`, `{"a": 1}`) reads present. Measured: a six-`null`-beat record returns
`(True, "")` — arc complete.

The spec's precedence pin already settles which gate should own a type check — **"record-arc wins"**
(arc, exit 4, fires before NAR, exit 3). A malformed beat is an **arc** defect.

**Two more escape hatches with the same shape, measured in the same pass:**

**C4 — the EXT anchor is a string shape, not an execution anchor.** `_INVOKE_RE`'s interpreter
prefix is `(?:^|[\s;&|])(?:python3|python)\s+` — *any whitespace*, not a command boundary. Four
non-invocations therefore certify Phase 2:

| command | accounted? |
| --- | --- |
| `echo python3 /x/extract_signals.py --json` | **yes** |
| `python3 -m py_compile /x/extract_signals.py` | **yes** |
| `python3 -c "open('/x/extract_signals.py')"` | **yes** |
| `python3 /x/extract_signals.py \` ↵ `  --recalls` | **yes** |

The last is the subtlest: `_SEG`'s second alternative (`\\\n`, a backslash-continuation) **is**
reachable in the lazy prefix `_SEG*?` by backtracking — that is why the path-split fixture at
`tests/smoke.py`'s `_CALL19`-adjacent pin passes — but **dead in the greedy tail `_SEG*`**: at a
backslash the engine takes alternative 1, the newline then matches neither alternative, and the
match ends. The `--recalls` that follows a continuation therefore lands *outside* `m.group(0)` and
the recall-only form — the mode the contract explicitly excludes — satisfies EXT.

**Which side of the token the continuation falls on decides the direction — and the first draft got
the consequence backwards.** Measured on three commands:

| command | `group(0)` | truncated? |
| --- | --- | --- |
| the path-split pin — continuation **before** the token, `--json` after | `python3 "…/scripts/\` ↵ `extract_signals.py" --json` | **no** — spans the whole command |
| the hole — continuation **after** the token | `python3 "…/extract_signals.py" \` | **yes** — the tail stops at the backslash |
| the `--recalls` pin — no continuation at all | the whole command, `--recalls` inside the match | n/a |

The asymmetry is structural, and the regex says why: `_SEG*?` is the **lazy prefix** and `_SEG*` the
**greedy tail**. A continuation *before* the token is reachable — the lazy prefix expands past the
backslash via alternative 2 to reach the required token. A continuation *after* it is not — the
greedy tail takes alternative 1 on the backslash, then the newline matches neither alternative and
the match ends.

So the path-split pin passes for the **opposite** reason to a truncation story, and the first
draft's sentence (*"passes because of this truncation … it asserts only that the match is not
`--recalls`, which truncation guarantees"*) was wrong twice over: **that pin's command contains no
`--recalls` at all**, so no `--recalls` guard is exercised by it, and its match is not truncated.
Counterfactual, measured: delete the `\\\n` alternative from `_SEG` outright and `finditer` returns
**zero** matches on the pin's command — the pin **fails**. It is load-bearing on the continuation
alternative being live, i.e. on the very mechanism the truncation story says it does not need.

The trailing `\\` in the *hole's* match is the bug: there, and only there, the form check reads a
command that was cut in half.

**C5 — an unknown flag is silently not a flag.** Four of the seven CLI entry points swallow an
unrecognized token; two of the four then treat it as a **path**. Measured on the live tree:

| invocation | exit | stderr |
| --- | --- | --- |
| `extract_signals.py --jsoon` | 0 | *(empty)* |
| `memory_status.py --jsoon` | 0 | *(empty)* |
| `preflight.py --jsoon` | 0 | *(empty)* |
| `render_dashboard.py --jsoon` | 1 | `cannot read cycle record: … '--jsoon'` |
| `distill_scan.py --jsoon` | 2 | `unknown flag: --jsoon` |
| `sync_global.py --jsoon` | 2 | *(usage)* |

`distill_scan.py` and `sync_global.py` already implement the pattern; the other five are the defect.
The consequence is not cosmetic — measured end-to-end against the real write plane
(`retention.cycle_log_write_path`), `render_dashboard --persist`:

| invocation | exit | log lines | stderr |
| --- | --- | --- | --- |
| `--persist DIR` (correct) | 0 | **1** | — |
| `--persit DIR` (typo) | 0 | **0** | *(empty)* |
| `--persist ""` | 0 | **0** | *(empty)* |
| `--persist <missing dir>` | 0 | **0** | `--persist dir not found` |

The skill's Phase-5 contract reads exit 0 as *persist clean* and proceeds. A single transposed letter
buys a dream that never persisted, reports clean, and says nothing — the same false-clean class, at
the one boundary every finishing dream crosses.

**C6 — an emptied dream is indistinguishable from a legacy one, at two gates.** The legacy carve-out
is implemented three times, and the second and third times with the wrong predicate. `_checked_texts`
already distinguishes the two cases correctly — `None` for "no dream block", `[]` for "a dream block
carrying nothing usable" — but neither caller reads the distinction: `dream_procedure.judge` tests
`if not checked:` and reports *"no dream block — a legacy record is outside both arms"*, and
`render_dashboard`'s narration gate tests the same value for truthiness. Measured, four shapes — a
dream block of `{}`, of `{"sleep": null, "beats": [null]*6}`, of `{"sleep": "  ", "beats": ["  "]*6}`,
and a record with no `dream` key at all — return the same `verified` verdict with the same legacy
reason. That is the label-not-predicate defect this cycle exists to close: a guard whose *message*
names one condition while its *test* names another.

The consequence lands on the archive. `render_dashboard` gates the **entire** narration check —
`judge`, the `narration` block, the exit arm — on that same truthiness, and `narration_block`'s own
docstring leans on the gate's meaning: *"absence on a log line then unambiguously means pre-feature."*
Measured, an emptied dream produces exactly that absence, so a reader of the archive cannot tell
*"this record predates the teeth"* from *"this record's dream was empty"* — and the inference they
will draw is the flattering one. The exit code is unchanged either way (the arc gate already fails an
emptied block, and both arms exit 4), so this is an **honesty** defect rather than a false-clean one;
it is fixed here because it is the same predicate at the same value, and fixing §2.2 without it would
leave the carve-out reading correctly in the predicate and wrongly in the reason.

**The one item that reverses a recorded decision.** `arc_completeness` opens with
`if not isinstance(record, dict) or "dream" not in record: return (True, "")` — so deleting one key
bypasses **both** NAR and EXT. This is not an oversight: `docs/dream-arc-contract.spec.md` records
it twice (*"a record with no `dream` block at all still exits 0 (legacy/preview)"*, *"a MISSING/emptied
block still does not fail — the missing-block posture here survives"*), naming the beta oracle's
`dream_arc_capture` WARN as the compensating control. That control exists and is real, but it is
**advisory (LOW/WARN), post-hoc, and lives in a separate, optional plugin** — thin cover for a hole
whose exploit is deleting a key from a file the recorder owns. §2.4 closes it without disturbing the
legacy carve-out the decision exists to protect.

**One residual, measured — and now closed rather than left loud.** `--persist <missing dir>` exits 0
today, and the first draft read that as the *loud* member of C5's family because it prints a
diagnostic naming the path. **That reading was wrong, and only re-measurement showed it.** The
diagnostic says *"dir not found, skipping log"* — about the **log**. What actually happens is that
`main` returns at `if status in ("no-dir", "io-error"): return 0` **before `procedure_integrity` or
`arc_completeness` is ever consulted**, so exits 3, 4 and 5 are all skipped — while `render()` has
already printed the panels that explain them. Measured on a stamped 2/6-beat record:

| invocation | exit | arc panel |
| --- | --- | --- |
| `--persist <real dir>` | **4** | prints |
| `--persist <missing dir>` | **0** | **prints** |
| `--persist ""` | **0** | **prints** |

So a path typo disables every terminal gate and still displays the violation. The repo holds *both*
postures for a typo'd directory and they are not equally applicable: `distill_scan.py` warns and
continues (`project dir does not exist`, exit 0, pinned in `tests/smoke.py`), which is right for a
**scan target** — an empty scan is recall-safe and claims nothing — while `sync_global.py` refuses
(`PROJECT_DIR … does not exist / is not a directory — refusing`, exit 2) precisely where a typo'd
path would **mint a phantom store**. A typo'd `--persist` dir is the second kind: the consequence is
not a smaller result but a *false clean*, blessing the record-side calibration this cycle exists to
protect. **Decision: refuse, exit 2**, matching `sync_global`. This **reverses the approved plan's
§5 line**, which chose the `distill_scan` posture before the gate-skip had been measured.

## §2 Design

### 2.1 One stanza predicate, three fields

The arc's completeness rule becomes: **a stanza is present iff it is a non-empty string.** One
predicate, shared by the gate and the render panel:

```python
def stanza_present(value: Any) -> bool:
    """A dream stanza is PRESENT iff it is a non-empty string — the type rule the arc gate and
    the render panel share. `str(v or "")` would read a list/dict/0 as present (the C3 hole)."""
    return isinstance(value, str) and bool(value.strip())
```

`arc_completeness` applies it to `sleep`, `wake`, and **each** `beats` entry. A wrong-typed or blank
beat fails the arc **naming its record index**, reusing the existing gap-naming style:

```
bits.append("beat(s) %s not a non-empty string" % ", ".join(str(i) for i in bad))
```

The JSON-null rule is preserved unchanged: `None` (and `""`, and any falsy value) reads absent, so
`sleep: null` still reports `sleep missing` exactly as before.

**The render panel must move with it.** `render_dashboard`'s ✓/✗ line takes its **beat** cell from
`arc_completeness` (`_full`) but computes the other two itself:
`_have = [bool(str(dr.get("sleep") or "").strip()), bool(str(dr.get("wake") or "").strip())]`. Left
alone, a `sleep: [1]` record would render `✓ sleep · ✗ 6/6 beats · ✓ wake` against a gate exiting 4
with `sleep missing`. `_have` is rebuilt on `stanza_present`.

The comment above that line is worth reading, because it shows the author saw the shape and stopped
one case short: *"`or ""` so a JSON-null stanza reads ✗ (absent), never a truthy `str(None)`."* The
hedge covers the JSON-null case — and only that one — while `str([1])` and `str({"a": 1})` sail
through as truthy. A guard built to defend against a *class* of truthy coercion, implemented against
one member of it, and read ever since as covering the class: the same defect as C1, one file over.

**Two more copies of the predicate exist, and the fix must decide about each.**

- **`plugins/dream-beta-tester/scripts/beta_checks.py`** carries its own `is_complete(dream)` —
  nearly verbatim, `str()` coercion and `len(beats) == 6` included. It is the QA oracle's
  `dream_arc_capture` family, and it runs against *archives* rather than a live persist. **Measured
  by extracting the function's own source and calling it** (the file defines *six* nested `is_complete`
  functions, one per family — extract by line, not by name): `[null]*6`, `[{}]*6` and `['*']*6` all
  return `complete=True` with narrated `sleep`/`wake`, and only a wrong **count** (5, 8) returns
  `False`. So the oracle certifies precisely the record class this cycle exists to catch. Its own
  comment sits one line above the hole — *"`or ""` — a JSON-null stanza must read ABSENT"* — the same
  hedge as the render panel's, worded twice, both stopping at the stanza and neither reaching a beat
  entry. Left alone,
  it keeps reporting arcs complete that the product now rejects — the oracle's verdict and the
  product's gate describing different contracts, which is precisely the "two matchers, each blind to
  what the other sees" failure. The tree already believes this cannot happen: `tests/smoke.py`'s pin
  block for this predicate is captioned *"the SINGLE completeness predicate … one definition, no
  reimplementation drift"* — a claim the file contradicts, unmeasured since it was written. **The
  oracle's copy takes the same type rule** (so its report describes the shipped contract) but **not**
  `enforce_post_arc` (which is persist-scoped; letting it reach the archive would retro-flag
  pre-v0.1.63 records the gate deliberately spares).
- **`plugins/dream-beta-tester/fixtures/canary-v0.1.19/memory_status.py`** is the vendored
  known-bad artifact — byte-faithful to the v0.1.19 tag, SHA256SUMS-manifested, and wrong *on
  purpose* so the oracle can prove it still catches a real defect. **It must not be touched**, and
  the SHA256SUMS entry makes that checkable rather than a matter of discipline.

The HTML archive is already correct **for the non-string class**, and needs nothing there:
`dashboard.sections.js`'s `passage()` guards on `typeof v !== 'string' || !v.trim()` — the type rule
§2.1 introduces, reached independently — and renders `null`/blank as *"Not captured"* and anything
else as `JSON.stringify(v)`. Pre-fix that makes the archive **stricter than the gate** — the HTML
shows `Not captured` on a record the arc calls complete. After §2.1 the two agree.

**It is not correct for the class §2.2 exists for, and the first draft's "needs nothing" rested on
an arm that does not cover its subject.** A *string* that normalizes to empty passes `v.trim()` and
takes the **prose** branch. Measured by executing the extracted `passage()`:

| input | what it hands `paragraph()` |
| --- | --- |
| `"*"` | `("VOICE", "*")` — a literal asterisk rendered as captured dream-voice |
| `"***"` | `("VOICE", "*")` |
| `"> "` | `("VOICE", "")` — a **blank** voice paragraph |
| `""` · `"   "` · `null` | `("note", "Passage 1: Not captured")` |
| `{}` · `0` | `("note", "Passage 1: {}" / ": 0")` |

So the archive is not "stricter than the gate" for the empty-normalizing class — it renders a
beat-styled line for a beat carrying no narration. This is the same hedge §2.1 criticizes in
`beta_checks.py`: stopping at the stanza and never reaching the content. §5 records it as a named
ceiling rather than a fix — the archive is a **display** surface, Cycle A's charter is the gates,
and the change would land in a third file with its own browser-check surface to re-baseline.

### 2.2 The checked set cannot shrink, and an empty needle is a gap

`_checked_texts` gains the rule its caller already assumes — *a stanza the record presents is judged*:

- A stanza whose key is **present** enters the set whether or not it is a string. A non-string is
  carried as an empty needle so it **fails**, rather than silently leaving the denominator.
- A stanza whose key is **absent** stays out of the set. The arc gate owns absence (its
  `have_sleep`/`have_wake` arms fire exit 4); the narration arm judges what is there to judge. This
  keeps pin (6)'s "record-arc wins" intact rather than double-reporting one absence in two panels.

`_gaps` then converts an empty normalized needle into a **named gap** — never a `continue`:

```python
if not needle:
    missing.append({"label": label,
                    "preview": "no narratable content (empty after normalize)"})
    continue
```

**Both callers must read the distinction `_checked_texts` already draws** (C6). The empty list now
has two meanings, and the fix makes the difference load-bearing, so neither site may keep collapsing
them:

```python
if checked is None:                      # judge's carry-out, replacing `if not checked:`
    return {"verdict": "verified",       # the legacy carve-out, reason kept verbatim
            "reason": "no dream block — a legacy record is outside both arms", ...}
if not checked:                          # a dream block that carries nothing usable
    return {"verdict": "failed",
            "reason": "dream block empty — no narratable stanza", ...}
```

and in `render_dashboard`, the narration gate becomes `if _dp._checked_texts(record) is not None:`.
That second change is what closes C6's archive consequence: an emptied dream now carries a
`narration` block reading `failed`, so *absence* on a log line means pre-feature again.

The `[]` arm returns **before** the scan — there is nothing to look for, and letting it fall through
would reach the `missing or not accounted` conjunction with `missing == []` and certify an empty
block as `verified`. F19I is the constraint that keeps this honest: its fixture carries no `dream`
key, so it still returns `None`, still skips both arms, and still writes no block.

With both arms in place the numerator is a count over slots that were **actually checked**, and no
separate edit is needed for that: on the `verified` path `missing` is empty by definition, so
`len(checked)` is simultaneously the denominator, the numerator, and the number of slots that
reached the check. `N/N narrated` stops being a label count wearing a coverage claim's clothes
because there is no longer a way to be in `checked` without being checked.

**"Correct by construction" was the first draft's over-claim, and the correction is measured.**
What the fix makes correct is the **membership** of the count. What is still *not* proven is
**attribution**: `_gaps` asks `any(needle in n for n in norms)` — substring containment of each
needle in one pooled list of blocks. Measured through `judge` with an accounting EXT fixture:

| fixture | verdict |
| --- | --- |
| 7 distinct needles, **one** block containing all seven | `verified` · `7/7 narrated` |
| 6 **identical** beats, one block reading `same` | `verified` · `7/7 narrated` |
| 3 blocks covering 7 slots between them | `verified` · `7/7 narrated` |

A dense narration that satisfies seven needles from one sentence *is* narrated in the sense this arm
implements, so this is not a false clean of §1's kind. But `N/N narrated` reads as N separate
mentions, and one block can be N — the arm proves **presence, not per-beat attribution**. §5 states
that as the ceiling rather than letting the numerator imply more than it measured. Requiring
distinct blocks would be a *stronger* rule than the contract this implements (*"All checked texts
must narrate"* is about which texts are checked, not how densely they are spread), which is why it
is bounded and named rather than adopted.

### 2.3 The execution anchor

The docstring's claim — *"anchored on EXECUTION"* — is made true by replacing the single regex with
the structure the claim names: **normalize the command, split it into top-level segments, tokenize
each, and ask whether the interpreter actually runs the script.**

1. **Normalize** first, in the order `distill_scan` pinned for the same job:
   - **Unfold** backslash-newline continuations, so a wrapped command is one segment;
   - **normalize a Windows drive path** (`C:\a\b` → `C:/a/b`) — posix `shlex` eats each `\` as an
     escape, so the `/` before the filename, the separator the token test depends on, is gone
     before the test can see it. Measured: without this the whole form was unaccounted;
   - **strip heredoc BODIES** — **imported from `distill_scan._strip_heredocs`**, not re-written
     here (two copies of one rule drifting apart is the defect class this cycle is about; the
     cross-script import is the established pattern, cf. `distill_scan`'s own `from memory_status
     import`). The rule is terminated-heredoc-only, and the **opener's** command line survives;
   - **strip `#` comments** — `#` opens a comment at the start of a word and outside quotes, so an
     apostrophe inside one (`# don't re-run this`) can no longer unbalance the tokenizer. That
     mattered: an unbalanced segment is *Uncertain → fire*, so the anchor was firing on a call that
     had fully executed.
2. **Split** on the unquoted top-level operators `;` `&&` `||` `|` `&` and newlines. A separator
   inside quotes is literal. **`&` is a token test, not a character split**: `&&` is matched first,
   and a bare `&` separates only when tokenization yields it as a token of its own — so the `&` in
   `python3 <tok> --json 2>&1` is part of the token `2>&1` and never splits. A naive character split
   would truncate that command to `python3 <tok> --json 2>` and lose a legitimate call.
3. **Tokenize** each segment with `shlex.split(..., posix=True)` — stdlib, and the only way to know
   what is a quoted payload rather than an argument. A segment that cannot be tokenized (unbalanced
   quotes) is **not** accounted: the contract's tie-break is *Uncertain → fire*.
4. **Decide**, on the token list: walk past
   - a leading prefix of `VAR=VALUE` env assignments (the SKILL's own Phase-2 form is
     `CM_DREAM_ARC=1 python3 …`);
   - the shell's **grouping / control prefixes** — `then` `do` `else` `{` `!` `eval` `(` — including
     the **`(`-FUSED** spelling `shlex` produces with `punctuation_chars` off, where `(python3`
     arrives as ONE token whose basename is not an interpreter. This set is a subset of
     `distill_scan._KW_PREFIX`; `exec` is deliberately **not** in it, because `exec` is a *wrapper*
     here and a bare prefix-skip would drop its flags;
   - **wrapper commands drawn from an explicit bounded set**, each with **its own argument
     grammar** — the flags that consume the next token as their value (`sudo -u root`,
     `nice -n 10`, `timeout -s KILL`) and the leading positional operands (`timeout 300 …`,
     `flock /tmp/l …`). Flags are consumed **before** the positionals: `timeout -s KILL 5 python3 …`
     has a value that is not flag-shaped, and a positionals-first walk would spend the slot on `-s`
     and read `KILL` as the command word.

   Then the next token's basename must be `python3` or `python`; the remainder must carry no `-c` and
   no `-m`; the remainder must carry no `--recalls` **argv element** (the recall-only mode is not the
   Phase-2 extract — carried over from the old substring test, restated as a token test because the
   segment is now the unit); and some remaining token must equal `extract_signals.py` or end with
   `/extract_signals.py`.

The `/` requirement is doing the same work the old `(?<![A-Za-z0-9_])` lookbehind did, which is why
`tests/test_extract_signals.py` and `tools/extract_signalsXpy` stay unaccounted: `endswith` demands
the separator, so a token merely *containing* the stem never satisfies it. (The `-m pytest` case is
rejected twice over — by `-m`, and by the missing separator.)

A cheap `if _EXTRACTOR_TOKEN not in segment` pre-filter keeps the tokenizer off the hot path.

Rejecting `-c`/`-m` is what makes the anchor an *execution* anchor: those two flags consume the
following token as **code** or as a **module name**, so a script path can only appear inside them as
a string, never as the thing python runs. Rejecting *any* whitespace before the interpreter is what
kills `echo python3 …`. Unfolding continuations first is what lets the whole segment (and therefore
`--recalls`, wherever it sits) be seen.

**Measured before adopting it.** The design was prototyped (unfold → split → `shlex.split` → decide,
exactly as above) and run over **16** cases: every form the existing EXT pin already asserts, plus
the four new holes, plus the chained forms. Result: **16/16**, and the prototype's verdict differs
from the shipped anchor on **exactly four** inputs — the four C4 holes, each flipping
accounted → unaccounted. Every pre-existing verdict **in that set** is preserved, including the two
that look most fragile: the path split *inside quotes* by a continuation stays **accounted**
(unfolding rejoins it, and its flags are `--json`), and
`python3 -m pytest tests/test_extract_signals.py` stays **unaccounted** (rejected by `-m`, and
independently by the missing `/` separator).

**Sixteen cases is a match set, not a proof — and eight more forms showed the prototype dropping work
the old regex did.** Measured against the shipped `_INVOKE_RE`, all of `env python3 <tok> --json`,
`env VAR=1 python3 …`, `time …`, `command …`, `nohup … &`, `sudo …`, `xargs -I{} …` and
`sleep 5 & python3 …` are accounted **today**; the first prototype made **all eight unaccounted** —
eight new exit-3 fires on legitimate calls. (The four C4 holes flipping the other way are the
*intended* diffs; a first count conflated the two directions and is corrected here.) Two causes, both
now fixed:

- the replaced prefix `(?:^|[\s;&|])(?:python3|python)\s+` anchored on **any whitespace or a bare
  `&`**, while the new separator list named `&&` and omitted `&`;
- a wrapper like `env` or `sudo` is neither a `VAR=VALUE` assignment nor the interpreter, so the walk
  stalled on it instead of reaching `python3`.

**The direction of error was stated backwards and is corrected here.** The first cut called the
loud-on-clean drop "the worse of the two". It is not, and the spec's own contract says so twice: the
tie-break is *Uncertain → fire*, and a false **clean** is *"permanent and invisible (a fabricated
record archived as performed)"* while a false **fire** is an exit 3 the model reads, reports, and
repairs by re-running the extractor plainly. The worse direction is the silent one, and the first cut
did not merely mislabel it — it **had one**: a heredoc *body* was segmented like any other line, so a
pass that only **wrote** the command into a file was credited. That is the hole §2.3 step 1's
imported heredoc strip closes, and it is the reason the repair is specified as *under-account rather
than over-account* everywhere the two conflict.

**The second cut's residuals, measured, and all twelve closed.** The first §2.3 cut walked past
wrapper *keywords* but not their arguments, never stripped the shell's grouping prefixes or comments,
and did not touch drive paths. Run through `judge`'s own seam (`_ext29`), **12** legitimate Phase-2
forms were unaccounted — four unlisted wrappers (`timeout`, `nice`, `stdbuf`, `flock`) · their
positional operands (`timeout 300 …`, `flock /tmp/l …`) · their value flags (`nice -n 10`,
`sudo -u root`, `timeout -s KILL 5`) · a `(`-fused subshell · a `then`-led and a `do`-led segment ·
a `{ …; }` group · an apostrophe inside a `#` comment · a Windows backslash path. All 12 are
accounted by the grammar above, and **13 pins** (§3) cover them, each RED on pre-fix code
(measured: 1895 passed / 13 failed on the pre-fix tree, 1908 / 0 here).

**The corpus, re-derived against the FINAL anchor.** Across every transcript on this machine (946
JSONL files), **503** assistant Bash commands mention the extractor. The shipped regex accounts
**95**; the final anchor accounts **46**. The delta is **49 flips accounted → unaccounted and ZERO
the other way** — nothing new is credited. Classified by inspection: **46** are unambiguous
non-executions (10 heredoc/`cat >` *writes*, 25 scripts fed to `python3 -` on stdin where the token
is data, 6 `python3 -c` one-liners, 1 `grep`, 4 `cat > … <<'PY'` writes with a `cd` prefix). The
remaining **3** are shell-*function*-mediated calls (`probe … python3 $S/extract_signals.py …`,
where `probe(){ … "$@"; }` runs it) — the anchor cannot resolve a user-defined function, so it fires
loudly. That is the *Uncertain → fire* contract, not a regression, and §5 records it as a ceiling.
A specimen of how loose the shipped regex was: writing
`cat > /tmp/m3.py <<'EOF' … f"echo python3 {TOK} --json" …` to a file is accounted **by the regex**,
because it matches `python3 /x/extract_signals.py` inside a heredoc being *written*.

**Two baselines, two questions, and both are needed.** The 49-flip number compares the *shipped
regex* against the final anchor — it is the case for the whole §2.3 rewrite. Against the *first §2.3
cut* the corpus delta is **ZERO in both directions** (measured: 46 accounted before and after): the
12 forms above do not occur in this corpus at all. So the widening has no observed victim and no
observed regression, and the false fires it closes are **latent** — demonstrated synthetically and
pinned, not observed in the field. A match set could not have found either the 12 or the eight —
which is exactly why the corpus is corroboration rather than proof, and why every widening here
carries its own pin rather than resting on the corpus's silence.

### 2.4 The dream-absent carve-out, closed where it is enforceable

The carve-out is doing two jobs. **"A pre-v0.1.54 record is fine" must survive. "A modern record may
skip the arc" must not.** They are separable, because the record's *own shape* dates it.

`docs/dream-arc-contract.spec.md` supplies both halves of the discriminator: the block became
mandatory at **v0.1.54**, and *"records carry no plugin-version stamp"* — so the dating must be
structural. The criterion is **"a key introduced strictly after v0.1.54"**, and the first cut applied
it to **two** of the **seven** keys that satisfy it:

```python
# The dream block became MANDATORY at v0.1.54 (2026-07-01) — docs/dream-arc-contract.spec.md:
# "a latest record written by ≤ v0.1.53 legitimately lacks `dream`". Records carry no version
# stamp, so legacy-vs-skipped is decided structurally: each of these keys was introduced
# STRICTLY AFTER v0.1.54, so a record carrying any of them was written by a version that already
# required the arc — its missing `dream` is a SKIP, not a legacy artifact.
_POST_ARC_KEYS = ("usage", "demotion", "distill", "workflow_proposals", "identity",
                  "narration", "preflight")
```

| key | first tag containing its introducing commit |
| --- | --- |
| `distill` | v0.1.58 |
| `usage` | v0.1.63 |
| `demotion` | v0.1.67 |
| `workflow_proposals` | v0.1.87 |
| `identity` | v0.3.1 |
| `preflight` | v0.4.16 |
| `narration` | v0.4.19 |

Dated by `git log --reverse -S'record["<key>"]'` and the first tag containing that commit — **never
by CHANGELOG prose**, which matches the bare word in any sentence and dates `demotion` to v0.1.8,
eleven releases early. The first cut was *narrower than its own stated criterion, and
self-contradicting*: it excluded `distill` (v0.1.58), a key **older** than the `usage` (v0.1.63) it
already trusted. Two keys stay **out**, by the same rule: `audit` (v0.1.53, pre-mandate) and
`outcome` (v0.1.1) — and they are load-bearing exclusions, because 9 of this store's 17 dreamless
archive records carry one and are correctly carved out. Measured **inert** on both real populations:
the 55-cycle archive (0 newly firing) and the 69 records across 11 store logs (44 dreamless, 0 newly
firing).

`arc_completeness` gains **`enforce_post_arc: bool = False`**:

```python
if not isinstance(record, dict) or "dream" not in record:      # the guard the sketch must KEEP
    if (enforce_post_arc and isinstance(record, dict)
            and any(k in record for k in _POST_ARC_KEYS)):
        return (False, "dream block absent — the arc was skipped (a post-v0.1.54 record)")
    return (True, "")
```

**The `not isinstance(record, dict)` half of that guard is load-bearing and easy to lose.** The
existing pin asserts `arc_completeness("junk") == (True, "")` — a non-dict record is outside the
arc, exactly as a dreamless one is. Drop the isinstance test while adding the new arm and a bare
string becomes a candidate for `"dream" not in record` plus a substring match against
`_POST_ARC_KEYS`; `"usage" in "junk"` is `False` today only by luck of spelling. The `isinstance`
re-check inside the new arm is the belt to that suspender.

*(The approved plan named this parameter `require_dream`. That name overpromises: the parameter does
**not** require a dream block in the legacy case, and a name that misstates its predicate is the
defect class this whole cycle is about. The rename is deliberate.)*

**Scoped to exactly one surface.** `enforce_post_arc=True` is passed **only** inside
`render_dashboard`'s `judged`-gated render (the exit-4 gate and the two ⚠ panels). The first draft
justified this by saying they "already share that block and therefore cannot desync" — **measured
false**, and the reason it is false is itself one of this cycle's defects. The panels render under
`judged = persist_dir is not None`; the gates run in `main` under `if persist_dir:`. Those two tests
differ exactly when `persist_dir == ""` (not-`None`, but falsy), and `main` additionally returns
before the gates on a `no-dir`/`io-error` persist status. Both paths are measured in §1. So the
scoping does **not** rest on a shared block — it rests on the narrower and true claim that the
`--persist` render is the only surface that knows the record was *just written*, and on §2.5's new
usage errors removing the two conditions under which the block could desync. Every other consumer
keeps the default:

| consumer | strict? | why |
| --- | --- | --- |
| the persist-gate exit-4 | **yes** | the terminal render of a live pass — the only surface that knows the record was written now |
| `_arc_gate_section` ⚠ panel | **yes** | same block, `judged`-gated; a panel that disagreed with the exit it explains would be worse than either |
| `_narration_section` suppression | **yes** | must match the panel, or pin (6)'s no-contradictory-panel contract breaks |
| the render panel ✓/✗ | no | renders seeds and previews; the BEFORE state must survive |
| `render_html`'s WAKE cue | no | renders the archive, including historical records (`cm report`) |
| `validate_cycle_record`'s warning | no | not `--persist`-gated; runs on every render of any record |

**The ⚠ panel's routing is safe only *because* §2.5 closes both desync paths — say so, do not assume
it.** The table above routes `enforce_post_arc=True` into `_arc_gate_section` on the ground that the
panel is `judged`-gated, and implementing that literally has a consequence worth naming: on a render
where `judged` is true and the gates never ran, the panel would print *"dream block absent — the arc
was skipped"* on a run that exits **0**. That is the desync §1 measured, and it is the reason the two
§2.5 usage errors are **load-bearing for §2.4** rather than independent hardening: the empty-string
guard (pin 16) removes the `persist_dir == ""` half, and the missing-dir refusal (pin 35) removes the
`no-dir` half — so after §2.5 there is no reachable state where the panel speaks and the gate does
not. Stated explicitly because the alternative reading — "the panel and the gate share a block" — is
the sentence that was measured false, and a reader who reinfers it from the routing table would
re-derive the same wrong justification.

**Measured cost of the discrimination, against the 55-record union the archive embeds** (the log
plus its two plugin-data read paths, deduped on `(commit, timestamp)`):

- 17 records carry no `dream` block.
- A **blanket** "missing `dream` is incomplete" would newly fail **all 17**.
- The `_POST_ARC_KEYS` rule newly fails exactly **1**.

Choosing the criterion is the whole design decision, so the alternatives are measured rather than
argued. Of the 17 dreamless records:

| criterion | newly fails |
| --- | --- |
| blanket (any missing `dream`) | 17 |
| any of `audit`/`outcome`/`remediation`/`maintenance`/`network` | 17 |
| any of `audit`/`outcome`/`remediation`/`maintenance` | 14 |
| `audit` alone | 7 |
| **`_POST_ARC_KEYS` = `usage`/`demotion`** | **1** |

The two broad criteria are the interesting failures: each *admits every record it is asked about*,
because the keys it names appear throughout the June archive — so "newer-schema block" as a phrase
has no operational content until a key is chosen and dated. The rule that survives is the one whose
keys were introduced strictly **after** the mandate, which is a fact about the version record rather
than a fit to this data.

The single true positive comes with a sandwich. In chronological order:

```
2026-07-10T01:25   dream=dict     usage ✓ demotion ✓ distill ✓   ← predecessor
2026-07-11T15:51   dream=ABSENT   usage ✓ demotion ✓ distill ✓   ← the skip
2026-08-29T14:52   dream=dict     usage ✓ demotion ✓ distill ✓   ← successor
```

Its neighbours on both sides carry a dream block *and* both post-arc keys, so the record's missing
`dream` cannot be legacy shape — a version that writes `usage` and `demotion` also writes `dream`.
A genuine fully-skipped arc, and the rule's only hit. It also leaves the pinned legacy carve-out
fixture (`tests/smoke.py` F19I, carrying `project`/`session`/`scope`/`verification`/`marker` and none
of the post-arc keys) exiting 0. A counter-check confirms the rule cannot over-fire: **35** records
carry `usage` or `demotion` *with* a dream block, and the rule is gated on `"dream" not in record`,
so none of them is affected.

**Retro-compatibility of §2.1–2.3, across the same 55.** The §2.1 type check is the only change that
could flip a historical verdict, so it is measured directly: **0** of the 38 dict-dream records carry
a non-string or blank `sleep`, **0** carry a non-string or blank `wake`, **0** carry a non-string or
blank beat, and **0** carry a present string that normalizes to empty. Running the strict predicate
over the union gives **23** arc-complete records before and **23** after — a **0-record flip**. (The
15 non-complete records fail on the pre-existing `n == 6` arm: the union's beat counts are 6×23,
5×11, 4×3, 8×1.) The archive's 7 narration verdicts are all `verified`; nothing in §2.2's `_gaps`
change can move them, since each of those records narrates all seven.

### 2.5 Strict flags — the pattern `distill_scan.py` already pins

The contract is not new, but its precedent is **narrower and more mixed than "already pinned for two
scripts."** `tests/smoke.py` pins *exit 2 on an unknown flag* twice, and the two pins are not the same
pin: for `distill_scan.py` it pins the **message** (`unknown flag: --sicne`), and for
`calibration_report.py` it pins the **code alone** — that script gets the behavior free from
`argparse`, whose wording is `error: unrecognized arguments:`. So only one shape is **copyable**, and
it is `distill_scan.py`'s hand-rolled loop.

**The plan's second pattern source does not exist, and `sync_global.py` is not strict.** The plan
cited a `sync_global.py` `--fleet`/`--tokens` refusal — a rule that "a flag must never silently no-op
on another mode". Measured, there is no such refusal:

| invocation | exit | stderr |
| --- | --- | --- |
| `--list --evict=x .` | **2** | `evict: --evict requires --pull …` |
| `--list --fleet=personal .` | 0 | *(empty, modulo the unenrolled advisory)* |
| `--tokens --fleet=personal .` | 0 | *(empty)* |
| `--pull --tokens .` | 0 | *(empty)* |
| `--list` · `--tokens` · `--gc` `--jsoon .` | 0 | *(empty)* |
| `--jsoon .` (positional 0) | **2** | *(usage)* |

The one real mode guard is **`--evict`** — a flag this paragraph never named, and a guard against a
*destructive swap on the wrong mode*, not against an unknown token. `sync_global`'s unknown-flag
strictness is **positional-0 only**: move the flag one position right and it is silently accepted. So
it is not "already strict and unmodified", and the unknown-flag class is **unclosed in a fifth entry
point** — one the decided scope ("all five lax scripts + `cm`") does not cover. Left unfixed
deliberately and **named in §5**, because a cycle that quietly implies it closed a hole it did not
touch is the defect class it exists to fix.

The contract the five sites
adopt: **an unknown flag is a usage error — exit 2, `unknown flag: <flag>` on stderr — and the visual
flags never misfire it.** The visual surface is exactly
`--ascii` · `--color` · `--no-color` · `--color=*` · `--width=*` — **five forms, two of them
equals-only, and no bare `--width`.** Writing that list as four bare words (the obvious reading, and
this spec's first draft) is wrong in both directions: it rejects `--color=always` and `--width=80`,
which the sibling scripts accept, and it *blesses* a bare `--width` that **no code path in the repo
consumes** — `_ui.resolve_width` matches `startswith("--width=")` only. A blessed-and-ignored flag is
precisely the silent no-op C5 exists to close, so the fix would have re-opened the defect it was
written to fix. The repo's own predecessor spec states the set correctly
(`docs/distill-hardening.spec.md`: *"the visual flags `--ascii` / `--color` / `--no-color` /
`--color=*` / `--width=*`"*); this section had drifted from it.

**The general rule the per-script lists are instances of — stated once, because §2.5's own trap
bullet invites an implementer to allow `=` broadly.** *A `--flag=value` token is an unknown flag
**unless that exact flag is on the script's equals-form allowance**. The allowance is per-script and
enumerated: `sync_global.py` (`--evict=`, `--into=`), and `_ui`'s global visual set (`--color=`,
`--width=`). `render_dashboard.py`'s `--persist` is **not** on it.* The rejection diagnostic echoes
the **whole token, path included** — `unknown flag: --persist=/home/you/store` — so a value
containing `=` is shown exactly as rejected rather than truncated at the first `=`.

| site | defect | fix |
| --- | --- | --- |
| `extract_signals.py`'s argv loop | `else: i += 1  # … + unknown flags` | unknown → `return 2` |
| `memory_status.py`'s `pos = [...]` comprehension | an unrecognized `-`-token is dropped from `pos` and from `_argpaths` — it vanishes | reject before the comprehension |
| `preflight.py`'s `args = [a for a in args if a != "--json"]` | `--jsoon` becomes `args[0]`, i.e. the **project dir** | reject before the positional |
| `render_dashboard.py`'s `paths = [...]` filter | an unknown flag becomes a **record path** | reject before the filter |
| `cm`'s `help|*)` case | an unknown subcommand prints usage and exits **0** | `help`/`-h`/`--help`/empty → usage, exit 0; anything else → stderr + exit 2 |

**The exemption list is per-script, and it is the whole risk.** A naive "token not in the known set →
reject" breaks *working* flags, so each script's allowance must be its **actual** surface, enumerated
at implementation time — never a house-style list copied between scripts. Five traps, each measured
on the live tree:

- **Equals forms are valid for some flags and only some.** `sync_global` matches
  `startswith("--evict=")` and `startswith("--into=")`; those two, plus `_ui`'s
  `--color=`/`--width=`, are the whole equals-allowance in the tree. A bare token-set comparison rejects all four while they are
  perfectly valid — and this is the trap the *pattern source itself* warns about, since
  `distill_scan.py`'s allowance line is exactly `a in _VISUAL_FLAGS or a.startswith(("--color=", "--width="))`.
  **The four are not uniformly formed, which is the deeper point.** `--evict` is equals-**only**
  (its parser reads `a.split("=", 1)[1] for a in args if a.startswith("--evict=")` and nothing else),
  while `--into` has **both** forms and `--width` is equals-only in the *opposite* direction — bare
  `--width` is parsed by no one, anywhere. So "this script takes a value flag, so allow bare and
  equals" is wrong three ways at once. Each of the three shapes is legitimate; only the per-script
  enumeration finds which flag is which. This class has already bitten once here: `sync_global.py`'s
  `--into=` branch carries the comment *"review fix: the equals form was silently ignored."*
- **`render_dashboard` has `--demo`** — a real, live flag (a paste-free preview) handled by the
  current pruning and named by no visual-flag list. Omit it from the allowance and strictness turns
  a working flag into `unknown flag: --demo`.
- **`memory_status`'s surface is by far the largest**: `--audit`, `--diffs`, `--before`, `--into`,
  `--json`, `--triage`, `--sections`, `--snapshot`, `--seed`, `--force`, `--stamp-marker`,
  `--justify-demotion`, `--justify-defrag`, `--standing-justify-facts`, `--standing-justify-tokens`,
  `--snooze-until`, plus the visual set. The `--justify-*` pair take a **variable-length** stem list,
  so the check must not assume fixed arity.
- **`cm`'s catch-all contains no exit statement at all.** Measured, `cm bogus` returns 0 because the
  help text is the last thing run and `cat` succeeded. The fix must **add** an explicit `exit 2`
  rather than alter an existing branch — and it is the one site where the current behavior is
  neither silent nor loud but *structurally* unowned.
- **A flag is not the same as a git passthrough.** Several scripts carry `--is-inside-work-tree`,
  `--oneline`, `--no-merges`, `--exclude-standard`, `--verify` as *subprocess* arguments. They appear
  as string literals in the same file and must not enter the allowance; the enumeration is "flags
  this script *parses*", taken from `main()`'s branch structure.
- **`_ui` parses `sys.argv`, not the pruned list — so its flags are invisible to a locally-derived
  allowance.** Every one of these scripts calls
  `_ui.set_modes(color=…, ascii="--ascii" in sys.argv, width=_ui.resolve_width(sys.argv[1:], …))`,
  reading the **raw** argv rather than the local, already-pruned `argv`. Two consequences: an
  allowlist built by grepping the script's *own* flag literals is **incomplete by construction**
  (it will omit `--ascii`/`--color`/`--no-color`/`--width=`), and a strictness check that rejects
  one of them breaks a feature whose parser lives in a different module and never sees the local
  list. The allowance must be the union of the script's `main()` flags and `_ui`'s global set.

  This is the trap that makes §2.5's enumeration *riskier than it looks*, and it is why the
  per-script exemption lists here are described as the pattern to copy rather than as the content:
  each script's real allowance is knowable only by reading `main()` **and** `_ui` together.

  **`preflight.py` is the case that shows why the rule is "what this script consumes," not "what it
  imports."** It **does** import and call `_ui` — `preflight.py`'s own `import _ui`, then
  `ui.rule()`, `ui.lbl()`, `ui.c()` in `render_table` — so a grep for `_ui` finds three call sites
  and suggests a visual surface. It has none: it never calls `set_modes`, `resolve_color` or
  `resolve_width`, so `--ascii`, `--color=*` and `--width=*` would all be **blessed and ignored**
  there. Its allowance is the empty set plus `--json`. A per-script list derived from *imports* would
  get preflight exactly backwards.

Five `--persist` surfaces join them. Four are silent today, and two of those do not merely skip a
write — they **disable the gate**:

- **`--persist ""` is not "a missing argument" — it is a truthiness split, and the first draft's
  description of it was wrong.** Measured on a stamped, arc-incomplete record, `--persist ""` exits
  **0** with the arc panel *rendering*, byte-identical to no flag: `judged = persist_dir is not None`
  is **True** for `""`, so the render is *judged*, while `if persist_dir:` is falsy, so the whole
  print→persist→exit block — the 3/4/5 gates included — never runs. That makes it **worse than the
  typo row below**, not milder: the dashboard renders a judged dashboard, which claims the dream is
  being judged, and then judges nothing.

  The precedent is *missing-token*, not empty-value, and it says something narrower than the first
  draft claimed: `distill_scan.py PROJ --into` (no token) → exit **2**, `--into requires a value`;
  `distill_scan.py PROJ --into ""` → exit **0**, empty stderr. So **`--persist ""` → exit 2 is
  deliberately stricter than the precedent it learns from**, and that is the right call here: the
  extractor's `--into` is an output path whose emptiness costs a file, while `--persist`'s emptiness
  costs the gate.
- **The flag must exist.** `--persit DIR` currently falls through to the positional filter, becomes
  a path, and no-ops the entire persist.
- **The equals form must be rejected — the rule the first draft left unstated.** `--persist=DIR`
  never sets `persist_dir`, so `judged = persist_dir is not None` is `False` and the record renders
  as an **unjudged preview**. Measured on the shipped argument order (`<record> --persist …`, exactly
  as `SKILL.md` invokes it) with a stamped, arc-incomplete record:

  | invocation | exit | arc gate |
  | --- | --- | --- |
  | `--persist DIR` | **4** | fires — the record reaches the arc arm |
  | `--persist=DIR` | **0** | never runs |
  | `--persit DIR` | **0** | never runs |
  | *(no flag — a real preview)* | **0** | never runs |

  The equals form and the typo are therefore indistinguishable from a preview, and the equals form is
  the more dangerous of the two because it is *plausible*: the ecosystem accepts `=` for `--color=`,
  `--width=`, `--evict=`, `--fleet=` and `--into=`. **The decision is to reject it** — any token that
  is not exactly `--persist` is a usage error, exit 2. Accepting the form would mean a second parse
  path inside the one predicate that decides whether the record is judged *at all*, and the failure
  mode of getting that path wrong is the silent-clean direction this cycle exists to close. The cost
  of rejecting is that a caller who typed `=` gets a loud exit 2 on a call that never worked; the R2
  census shows no live caller uses the equals form, so nothing breaks.
- **A dir that parses but does not exist must be refused, not skipped.** `--persist <missing>` reaches
  `_persist`'s `if not os.path.isdir(dirpath): return "no-dir"`, and `main` turns that into
  `return 0` **before either gate is consulted** — the false-clean measured in §1. Fixed to **exit 2**
  with `--persist dir not found: <dir>`, matching `sync_global.py`'s refusal of a typo'd
  `PROJECT_DIR`. Nothing is lost by refusing: the dir is only ever a **store handle** here —
  `_persist` writes to `cycle_log_write_path(store)`, the plugin-data plane — so a run that reached
  `no-dir` was never going to persist anything anyway.

- **A *relative* `--persist` dir crashes outright — and it is not the same case as a missing one.**
  Measured with an isolated HOME, on a directory that **exists**: `--persist memory` → exit **1** with
  a 15-line traceback ending `identifiers.IdentifierRefused: invalid project id ''`; identical for `.`
  and `./memory`; the absolute equivalents exit 0 with `persist → …`. Mechanism:
  `retention._ops_slot` returns `native_store.parent.name` when the dir is **named `memory`** (so
  `Path("memory").parent.name` is `Path(".").name`, `''`) and `native_store.name` otherwise (so
  `Path(".").name` is `''` too). The two relative spellings reach the empty id by **different
  branches**, and the empty id then fails the identifier validator. **Fold the fix in**: normalize the parsed
  value with `os.path.abspath` at the flag, so the relative and absolute spellings become **one
  input** and the relative form lands on the same slot as its absolute twin. A Python traceback is
  never an acceptable outcome for a valid directory, and pin 39 holds it.

- **`-h` / `--help` are rejected on the five, and the first draft left the question open.** Measured
  pre-fix, **not one** of them actually provides help:

  | script | `-h` pre-fix | what it actually did |
  | --- | --- | --- |
  | `extract_signals.py` | 0 | a **full extraction of CWD** |
  | `memory_status.py` | 0 | a full status report |
  | `preflight.py` | 0 | a preflight with project dir `-h` |
  | `render_dashboard.py` | 1 | `cannot read cycle record: '…-h'` |
  | `distill_scan.py` | 2 | already rejected — `unknown flag: -h`, a real flag allowance |
  | `sync_global.py` | 2 | already rejected — but **only because position 0 is its positional parser**: it prints `usage: sync_global.py --list\|--pull …`, not `unknown flag`. One position right, `--list -h .` exits **0** (measured), so this row is *not* a second pattern source. See §5 |

  So this is **not** an accidental-but-working affordance — it is the same mis-slot defect as
  `--jsoon`, and a user asking for help gets a silent extraction of their CWD instead. Both pattern
  sources already reject both spellings, so rejecting is the consistent choice; post-fix each is
  exit 2, `unknown flag: -h`. **`cm` keeps `-h`/`--help` → usage, exit 0** — it is a dispatcher with a
  real help arm, the asymmetry with the scripts is deliberate, and pin 24 pins it.
  `calibration_report.py` is untouched: `argparse` gives it `-h` for free and it is not one of the
  five.

- **`--` (end-of-options) is unstated in the draft and becomes an unknown flag.** Measured:
  `render_dashboard.py -- /dev/null` → exit 1 (`'--'` read as a record path) and `extract_signals.py
  -- .` → exit 0 (swallowed). No caller in the repo passes it (the doc sweep found none), so post-fix
  `unknown flag: --` is defensible — recorded here so the change is stated rather than discovered.

**The R2 landing gate is clear, by two independent sweeps.** A repo-wide census of every live
invocation site — `cm`'s 34 dispatch arms, `hooks/hooks.json`, `session_beacon.py`, `run_beta.py`,
`beta_checks.py`, the `dream-beta-tester` fixtures, `tests/smoke.py`'s three subprocess helpers and
their ~35 callers, CI, `SKILL.md`, `harness-map.md`, and **`commands/*.md`** — checked flag-by-flag
against each script's actual branch structure, twice, by different methods, found **no caller that
passes a flag its script does not define**. `commands/*.md` is the site the first sweep omitted, and
it is the one a *user* pastes from; adding it is what surfaced the defect below. The complete set of flags reaching the four lax scripts:

| site | flags | defined? |
| --- | --- | --- |
| `cm` (34 arms, forwarding `"$@"`) | pass-through — bounded by the scripts themselves | — |
| `beta_checks.py` — its `--no-color --ascii` child call | `--no-color --ascii` | ✓ |
| `beta_checks.py`, `run_beta.py` — the `--persist DIR` child calls | `--persist DIR` | ✓ |
| `beta_checks.py`, `run_beta.py` — the `--json`·`--triage` child calls | `--json` · `--triage` · `--no-color` · `--ascii` | ✓ |
| `run_beta.py` — the `--snapshot`·`--audit` child calls | `--snapshot` · `--json` · `--audit X --into Y` | ✓ |
| `make_cycle_probe.py` | `--json` | ✓ |
| `smoke.py` — the `_run19` helper (12 callers) | `--persist` ×11, one bare record path | ✓ |
| `smoke.py` — the `_run54` helper (16 callers) | `--persist` · `--json` · `--triage` · `--tokens` · `--list` | ✓ |
| `cm beacon` | **no arguments at all** | — |

**The site column is a file and a named call, not a `file:line`.** The census originally carried
line numbers, and by the time this spec closed **not one of them still located its call** —
`beta_checks.py:444` was `import tempfile`, `make_cycle_probe.py:102` was blank, `smoke.py:14955`
was the tail of a dict literal. None of that was a mistake at the time: the numbers were measured
at a revision, and every edit above them moved them. A line number is a citation that cannot
survive the file it cites; the *call* is the datum the census actually keyed on, and the helper
names (`_run19`, `_run54`) were already in the row. This is the same rule the rest of the spec
follows, and §4 records the measurement that made it non-optional — see the citation-drift note
there. The census's **claim** is untouched: no caller passes a flag its script does not define.

Every one is defined. `--snapshot`, `--audit`, `--into`, `--triage` are all in `memory_status`'s
surface; `--tokens`/`--list` land on `sync_global`, which is **outside the fix and only partially
strict** (positional 0 only — see the precedent paragraph above). The one site worth naming because
it looks like a risk and is not: `cm beacon` invokes `session_beacon.py` with **zero** arguments, so
no allowlist can affect it.

The independent sweep also confirmed the *mechanism* and corrected this spec's first draft: the five
sites fail in **three different ways**, not one — `memory_status` and `extract_signals` **skip** the
token; `render_dashboard` and `preflight` **mis-slot** it (as a candidate record path and as the
project dir respectively); and `cm` **forwards or drops** it depending on the subcommand. The first
draft grouped `render_dashboard` with the skippers while its own table two paragraphs above said the
token "becomes a record path" — and the prose is what an implementer reads for the fix shape, so the
mis-slot reading is the one that has to survive. A single repair shape would not have covered all
five, which is why §2.5 lists each site's defect separately rather than prescribing one patch.

**The live finding: the docs are not runnable, and it is not one file.** Adding `commands/*.md` to
the sweep is what surfaced it, and measuring it properly grew it twice — one line of one file, then
12 invocations in that file, then this census. Counted against the pre-fix revision (`git show
HEAD:…`, so the numbers are re-derivable), over `commands/*.md` + `SKILL.md`:

| | command lines | class A | class B | either | clean |
| --- | --- | --- | --- | --- | --- |
| `commands/*.md` (8 files, 12 blocks) | 47 | 47 | 14 | **47** | 0 |
| `SKILL.md` (21 blocks) | 30 | 0 | 14 | **14** | 16 |
| **total** | **77** | **47** | **28** | **61** | **16** |

**Every command line in the `commands/` surface is malformed.** The 16 clean lines are all in
`SKILL.md`. Two shapes, one root: the blocks are written to be *read*, and **nothing in the repo
ever ran them**.

- **Class A — the quote closes nowhere.** `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/x.py` with the `"`
  opening before the path and never closing; the author's intent was `"…/x.py" args` — interpolation
  quoted, arguments bare. **47 lines in 8 files** (`cm-connect` 12, `cm-data` 11, `cm-group` 10,
  `cm-domain` 6, `cm-network` 3, `cm-sync` 3, `cm-doctor` 1, `cm-share` 1). Two sub-shapes, and the
  second is the dangerous one:

  | sub-shape | `bash -n` | what a paste actually does |
  | --- | --- | --- |
  | odd quote count in the block | **fails**, rc 2, `unexpected end of file` | loud — nothing runs |
  | even count, quotes pairing *across lines* | **passes** | silent — two commands are swallowed into **one** string, so the second never runs |

  That second row is why a syntax gate alone is not enough. `cm-domain.md` is the specimen: 6 lines,
  6 quotes, `bash -n` **green**, and every line wrong.
- **Class B — the placeholder is an unquoted `<…>`.** **28 lines** (`SKILL.md` 14, `cm-group` 9,
  `cm-connect` 4, `cm-share` 1). `--persist <native_memory_dir from Phase 0>` is not a placeholder to
  bash: `<` is redirect-**in** and `>` is redirect-**out**, so the shell reads a file called
  `native_memory_dir`, passes `from Phase 0 …` as arguments, and truncates a file named after
  whatever follows. A **single-word** placeholder is the worse half — `<name>` parses cleanly and
  silently redirects stdin from a file called `name`. The one thing that looks like the defect and
  is not: `distill_scan.py … --json > "<the --scan path>"` in `SKILL.md` is a **genuine** output
  redirect and must survive the fix. The pin's rule is therefore *"a `<…>` placeholder is quoted"*,
  **not** *"no `<`/`>` characters"* — the second would fail correct code, and it did fail this
  spec's own first draft of the check (pin 40).

The repair is mechanical and confined to bash blocks — close the quote after the script path, quote
the placeholder — and touches no code. **The flag census is unaffected**: all 77 lines' flags are
defined by their scripts, checked per line, so this is purely a spelling repair and R2's conclusion
above stands.

This is a **quoting/placeholder** defect, not a flag-strictness one, so it is adjacent to Cycle A's
charter rather than inside it. It lands in this cycle anyway, for the reason R2 exists: a sweep whose
job is to guarantee no live invocation breaks cannot leave **the entire user-facing command surface
plus the runbook** already broken. The pin is §3 pin 40.

**A scope note, stated rather than buried.** This grew from "one file" to "nine". It is folded
because it is one defect class with one fix and one pin, and because leaving it would contradict the
sweep's own purpose — but it is the one item in Cycle A that the approved plan did not size, and
`amend-8` records the expansion.

## §3 Verification — the pin list

Every pin must **fail on pre-fix code**; the mutation matrix is re-run per §4. **Six in-scope pins
are exceptions, and they are labelled rather than left to look vacuous.** Pins **3**, **6**, **8**,
**9**, **15** and **20** are green before *and* after, because their whole content is that the fix
must **not** move what already worked — and the set grew as the pins were measured (`amend-9`
item 8 adds 29, 34, 40-arm-3 and pin 26's no-scan half). The count that matters is the measured
one, not this list: **63 of the 125 `v0.4.29` checks are green pre-fix** (§4), and every one of them
is a labelled regression arm — the six below are the pin-level seeds of that set:

| pin | why it cannot fail pre-fix |
| --- | --- |
| 3 | `normalize_beat_text('*') == ''` already holds — it documents the mechanism C2 rides on |
| 6 | explicitly "unchanged" — the pre-existing cases of pin (2) |
| 8 | every real form is already accounted (measured 14/14) |
| 9 | the `--recalls` SKILL form is already unaccounted |
| 15 | F19I already exits 0, with no panel and no `narration` block |
| 20 | the exit ladder is described as unchanged |

The survive-clauses *inside* pins 7, 12 and 13 (`grep`/`sed`/`cat`/`<tok>Xpy`/`$(…)`/text-block all
already unaccounted; "keeps its existing verdicts"; "in both modes") are the same class. Together
with pin 34 these form the **regression set** — the pins that catch an implementation which
over-narrows, which is precisely the failure the first §2.3 prototype had. Leaving them under a
header that claims the opposite is how a regression pin gets "fixed" by someone who thinks it is
broken. **The set is not one-directional** — §4 records the second kind, added by the F10 round: an
arm that is green pre-fix because the *rewrite* could drop an exclusion the shipped code had
(`--recalls`), which fails silently rather than loudly, and `env -i`, which moves on no measured
revision at all.

**In-process — the checked set and the coverage count**

1. `_checked_texts` no-shrink, **asserted on values, not just the count**: `beats: [null]*6` → **7**
   entries *and* the entries are the record's own strings with indexes preserved (`sleep` first, then
   `beats[i]` in record order); `[{}]*6` → 7; `[0]*6` → 7; a mixed null/real record → 7. (Pre-fix: 1
   and 4.) **The count alone is not the pin.** A `str()`-coercing `_checked_texts` also returns 7
   here and passes a count-only assertion — and then the record `{"sleep": 0, "beats": [0]*6}`
   against a transcript containing the character `0` returns **`verified` · `7/7 narrated`**
   (measured by swapping a coercing implementation in). The shipped implementation returns `[]` on
   that record and the fixed path yields `failed`. A pin that cannot tell those two apart is not
   pinning the rule.
2. A stanza whose key is absent stays out of the set (the arc gate's job), while a **present** stanza
   enters it whether or not it is a usable string. The measurable fact is the *return type* — `None`
   for "no dream block", `[]` for "a dream block carrying nothing usable" — not membership in a set
   (`{"dream": {}}` yields `[]`, so nothing is "in" it).
3. `normalize_beat_text('*') == ''` — documents the mechanism C2 rides on.
4. **The audit's reproduction, pinned as a negative**: the all-`'*'` record against a transcript with
   **zero** text blocks → verdict is **not** `verified`; the reason contains no `7/7 narrated`; the
   gaps name all seven slots.
5. An all-`'*'` record against a transcript that **does** narrate the beats → still `failed`. The
   reason is *not* that narration is missing — it is that all seven needles normalize to empty, so
   the record presents no text that could be narrated at all. (Pre-fix this case returns `verified`,
   `7/7 narrated`: measured, the all-`'*'` record is certified identically against a narrating
   transcript and an empty one, which is what makes it the sharper half of pin 4.)
6. Pin (2)'s existing cases are unchanged: 7-narrated → clean; 2-narrated → 5 named gaps; the
   surfacing line as the last beats entry; the TEXT-block domain negative (record-fill tool_use
   input + tool_result echo → gaps); thinking blocks never count.

**In-process — the execution anchor**

7. Each C4 non-invocation → unaccounted: `echo python3 <tok> --json`;
   `python3 -m py_compile <tok>`; `python3 -c "open('<tok>')"`; `<tok>` split from `--recalls` by a
   backslash-continuation; and `grep`/`sed`/`cat`/`<tok>Xpy`/`$(…)`/a text-block mention (existing).
8. Each real form → accounted: `python3 "<root>/scripts/<tok>" --json`;
   `CM_DREAM_ARC=1 python3 "<root>/scripts/<tok>" --json` (**the SKILL's own Phase-2 form**);
   the path split by a continuation with `--json` after it.
9. `CM_DREAM_ARC=1 python3 "<root>/scripts/<tok>" --recalls --into S --before B` → **unaccounted**
   (the SKILL's Phase-5 form — the recall-only mode).
10. A segment with unbalanced quotes → unaccounted (tokenizer failure is *Uncertain → fire*).

**In-process — the arc and the carve-out**

11. `stanza_present`: a non-empty string is present; `""`/`None`/`0`/`[]`/`{}`/`[1]`/`{"a":1}` are
    not.
12. `arc_completeness` type arms: `beats: [null]*6` and `[""]*6` with sleep+wake → incomplete,
    naming the indexes; `sleep: [1]` → incomplete, `sleep missing`; the complete-arc, 4-beat,
    missing-sleep, and `dream: "x"` malformed cases keep their existing verdicts.
13. `enforce_post_arc` matrix: a legacy dreamless record → `(True, "")` **with and without** the flag
    (this is the F19I fixture's shape — the carve-out survives); a dreamless record carrying `usage`
    → `(True, "")` by default, `(False, …)` strict; carrying `demotion` → same; a **post-arc record
    with a complete dream** → `(True, "")` in both modes.

**Subprocess — the persist surface**

14. A post-arc dreamless record at `--persist` → **exit 4** + the arc panel naming the skip.
15. F19I (legacy dreamless) at `--persist` → **exit 0**, no panel, no `narration` block — unchanged.
16. `--persist ""` → **exit 2**, `--persist requires a directory argument`.
17. `--persit DIR` (the typo) → **exit 2**, `unknown flag: --persit`, and **no line appended**.
18. A malformed beat end to end → **exit 4** naming the index.
19. An empty-normalizing stanza end to end → **exit 4** naming the gap. **Preconditions are part of
    the pin**: exit 4 requires the EXT arm to be **accounted** *and* a live transcript pool, so the
    fixture must carry an accounting `--json` call and a real session dir. Measured, the bare shape
    without them exits **0** as `degraded` (`transcript unavailable`) — which reads as the pin
    failing when the fixture is what is wrong. *(The approved plan said exit 3 here; that is wrong.
    `judge`'s NAR arm returns 4 — exit 3 is the EXT-unaccounted key. Measured against the exit ladder
    in `render_dashboard.main`.)*
20. The existing exit ladder is unchanged: clean → 0, procedure-integrity → 3, arc → 4,
    both-arms → 3, unstamped → 5.

**Interface — the other four entry points**

21. `extract_signals.py --jsoon` → exit 2 + `unknown flag: --jsoon`; `--ascii --json` → no error.
22. `memory_status.py --jsoon` → exit 2; `--json`/`--triage`/`--no-color`/`--ascii` unaffected.
23. `preflight.py --jsoon` → exit 2; `.`/`--json` unaffected.
24. `cm <unknown>` → exit 2 + usage on **stderr**; `cm`, `cm help`, `cm -h` → exit 0 + usage on
    stdout.

**Pre-existing pins that must survive untouched.** These are pinned today and sit directly in the
blast radius; the implementer should run them first, before writing anything new, and expect every
one to be green both before and after. Naming them is the point — the sweeps found them, and a
change that silently rewrites one of these is a regression wearing a fix's clothes.

| pin | asserts | why §2.1/§2.4 could break it |
| --- | --- | --- |
| `smoke.py` arc block | `arc_completeness({}) == (True, "")` | the dreamless carve-out — `enforce_post_arc` defaults false, so it holds |
| " | `arc_completeness("junk") == (True, "")` | a non-dict record must stay outside the arc (see §2.4's guard) |
| " | `arc_completeness({"dream": "x"}) == (False, "dream block malformed (not a dict)")` | an exact reason string — do not reword |
| " | `… {"beats": ["a"]*4 …} == (False, "4/6 beats")` | **exact reason string**: a four-valid-beat record must still read `4/6 beats`, so §2.1's bad-beat clause may only append when a beat is actually bad |
| " | `arc_completeness({"dream": {"beats": ["a"]*6, "wake": "w"}})[0] is False` | missing-sleep arm unchanged |
| `smoke.py` warn count | `warn == 2` for a fixture | `validate_cycle_record` is **not** made stricter here; if the count moves, something leaked |
| `smoke.py` F19C | `"7/7" in narration["reason"]` | a fully-narrated record must still count 7 — §2.2's gap rule fires only on an empty needle |
| `smoke.py` F19I | exit 0, no panel, no `narration` block | the legacy carve-out at the subprocess boundary |

**In-process — the carve-out's two predicates (C6, added in amend-2)**

Appended rather than interleaved so a reviewer who has already read pins 1–24 can see exactly what
the second round added.

25. `judge` verdict matrix, all four shapes against an accounting EXT fixture: a record with **no**
    `dream` key → `verified` / *"no dream block — a legacy record is outside both arms"* (verbatim,
    unchanged); `dream: {}` → `failed` / the empty-block reason; `dream: {"sleep": null,
    "beats": [null]*6}` → `failed`; `dream: {"sleep": "  ", "beats": ["  "]*6}` → `failed`.
    (Pre-fix, all four return the legacy reason — measured.)
26. The `[]` arm returns **before** the scan: assert `judge` on `dream: {}` never reaches the
    transcript, by passing a `scan_fn` that raises if called.
27. The narration gate: with `render_dashboard`'s `--persist`, an emptied-dream record now writes a
    `narration` block whose `verdict` is `failed` — where pre-fix it wrote **no** block at all.
    (Measured pre-fix: `_checked_texts` is falsy for all three emptied shapes, so the gate skips.)
28. F19I is unweakened by 25–27: the fixture with no `dream` key still exits 0, still shows no
    CONVERSATION-TRUTH panel, and still writes no `narration` block on the log line — the pin's
    existing assertion, re-run unchanged.
29. The anchor prototype against the **chained** forms, which the old single-regex anchor never had
    to handle: `python3 <tok> --json && echo done` → accounted (segment 1); `echo hi && python3 <tok>
    --recalls` → **unaccounted** (segment 2). Splitting must not let one segment's flags speak for
    another.

**Interface — the equals form and the per-script allowance (added in amend-5, from the adversarial
round)**

Pin 21–24 use only bare tokens, and the equals form turns out to be unpinned **repo-wide** — the
existing `smoke.py` visual-flag pin exercises `--ascii --json` and nothing else. So the shape F1
describes could be implemented backwards and fail no test. These four close that:

30. **The visual surface, at its source and at its copies.** Against `distill_scan.py` (the
    precedent): `--color=always` → not 2, `--width=80` → not 2, **bare `--width` → 2**. Then the
    same three inputs against each of the four fixed scripts, each matching *its own* allowance —
    for the three that call `set_modes`, all three forms survive; for preflight, see pin 32.
    This is the pin that makes "five forms, two of them equals-only" checkable rather than
    transcribable, and it must be run against `distill_scan.py` too, so a future edit that narrows
    the precedent is caught at the precedent.
31. **`--persist=DIR` → exit 2**, `unknown flag: --persist=…`, **no line appended**, and the record
    does **not** render as a preview: assert the run is distinguishable from the no-flag case. The
    pre-fix behavior this pin exists to kill — exit 0, no write, no gate — is the reason the pin must
    assert the *exit code* and the *log delta* together; either alone passes on the old code.
32. **`preflight.py`'s allowance is empty plus `--json`.** `--ascii`, `--color=always` and
    `--width=80` each → exit 2, while `.` and `--json` stay green. Pre-fix all five are 0, and a
    fix derived from a `_ui` grep would bless the three.
33. **The visual flags do not misfire on a *bare* call.** `render_dashboard.py <record> --ascii`,
    `--color`, `--no-color`, `--color=always` → exit 0 with no `unknown flag` on stderr. This is the
    regression pin for the over-strict direction: §2.5's whole risk is that a naive token-set check
    breaks a *working* flag, and pin 30 covers only the deliberate rejections.

**Interface — the anchor's compatibility surface and the persist refusal (added in amend-6, from the
adversarial round)**

Pin 34 is a **regression pin**, and is labelled as one because it violates the "must fail on pre-fix
code" rule on purpose: its whole content is that the fix must **not** change these verdicts. A pin
that only ever asserts the new behavior cannot catch an implementation that over-narrows — and that
is exactly what the first prototype did, to seven forms.

34. **The anchor preserves every accounted form it inherited** — the twelve measured above, run
    through `judge`'s EXT arm end to end, not just `_INVOKE_RE`: `env`/`time`/`command`/`nohup`/`sudo`
    /`xargs -I{}` wrappers, `sleep 5 & python3 …`, the `&&` second segment, the bare
    `CM_DREAM_ARC=1` form, and **`python3 <tok> --json 2>&1`** (the token-granularity test — a
    character split on `&` breaks this one, and nothing else in the list would notice). All must stay
    **accounted**; `echo python3 <tok> --json` must stay **unaccounted**. Run pre-fix and post-fix;
    both must be green.
35. **`--persist <missing dir>` → exit 2** with a message naming the path, and **no gate skipped
    under cover of a panel**. The second half is the pin: assert the exit code and the panel's
    presence *in the same run*, because the pre-fix defect is precisely exit 0 **with** a panel, so a
    pin asserting either alone passes on the old code. (This is the measured §1 table, pinned.)
36. **`--persist ""` → exit 2** — pin 16's case, re-asserted here because the fix for 35 shares its
    parse path; a fix that special-cases the empty string but lets a missing dir through, or the
    reverse, must fail one of the two.

**Interface — the flag-shape boundary, the per-script allowance, and the paths (added in amend-7)**

37. **`-h`/`--help` are rejected on the five and kept on `cm`.** Each of `extract_signals.py`,
    `memory_status.py`, `preflight.py`, `render_dashboard.py` → exit **2**, `unknown flag: -h` (and
    the same for `--help`), with **no side effect** — the pin must assert the *pre-fix behavior it
    kills* is gone, so for `extract_signals.py` and `memory_status.py` it asserts **no extraction and
    no status report was emitted**, not merely the exit code. Pre-fix, both exit 0 doing exactly
    that. `cm -h`, `cm --help`, `cm help` and bare `cm` → exit **0** with usage — pin 24's case,
    re-asserted here because the fix for the five is a flag-shape rule, and the cheapest wrong
    implementation of it reaches into `cm`'s real help arm.
38. **The allowance is "what this script parses", pinned by cross-script rejection.** Three arms, all
    exit 2 pre-fix-silent: `--demo` is legal on `render_dashboard` and must be **rejected** on the
    other four (it is the one *real* flag no visual-flag list names, so a house-style copy blesses
    it everywhere); `--audit`/`--into` are legal on `memory_status` and must be rejected on
    `render_dashboard`; and the **git passthroughs** — `--oneline`, `--no-merges`,
    `--exclude-standard`, `--is-inside-work-tree`, `--verify` — are string literals *in the same
    files* and must be rejected on every one of the five, because they are subprocess arguments and
    never appear in `main()`'s branch structure. Then the token-shape edge: `--` → exit **2**,
    `unknown flag: --`, on each of the five (measured pre-fix: `render_dashboard.py -- /dev/null`
    exits 1 with `cannot read cycle record: '--'`, `extract_signals.py -- .` exits 0, swallowed).
39. **A *relative* `--persist` lands on its absolute twin's slot.** `--persist memory` and
    `--persist "$PWD/memory"` → the **same** slot, the **same** log delta, and exit 0 — no
    traceback. Pre-fix the relative form exits **1** with `IdentifierRefused: invalid project id ''`
    (measured on an existing dir, isolated HOME). The pin asserts the *identity of the slot*, not
    just the exit code: a fix that merely catches the exception and exits 0 would pass a
    code-only assertion while leaving the two spellings on different slots, which is the actual
    defect.
40. **Every documented invocation is runnable — three arms, because one is not enough.** Over every
    bash block in `commands/*.md` **and `SKILL.md`** (77 command lines today):

    | arm | rule | what it catches | what it misses alone |
    | --- | --- | --- | --- |
    | 1 | `bash -n` on the whole block succeeds | class A's odd-quote sub-shape, and every class B | class A's **even**-quote sub-shape (quotes pairing across lines) — `cm-domain.md` passes, all 6 lines wrong |
    | 2 | **no unquoted `<…>`** (`(?<!")(<[^<>\n]*>)(?!")`) | class B, including the **single-word** `<name>` that parses cleanly while redirecting stdin | — |
    | 3 | each line's extracted argv: the script exists and **every flag it passes is defined by that script** | a flag added to a doc before the script has it | — |

    Arm 2's rule is *"a placeholder is quoted"*, **not** *"no `<`/`>`"*: arm 2's first draft was the
    latter and it flagged `SKILL.md`'s **genuine** `> "<the --scan path>"` redirect — the
    over-strict direction, and the same failure mode as pin 33. Measured both ways before adopting
    the rule: the genuine redirect is not flagged, `--pull <other-repo>` is. Pre-fix, arms 1–2 fail
    on **61 of 77 lines across 9 files**; a syntax-only gate passes `cm-domain.md`, `cm-group.md`
    and `SKILL.md` while every line of the first two is wrong. **Arm 3 is green pre-fix** (all 77
    lines' flags are defined today, measured per line) — it is the pin's *regression* arm, and it is
    labelled like pins 3/6/8/9/15/20/34 for the same reason: without it, the next flag added to a
    doc and not to its script is a defect nothing sees. *(Superseded by `amend-10` item 6: under the
    differential oracle arm 3 became **RED** pre-fix, and its label was corrected. This paragraph is
    left as the record of what amend-8 measured, not as a description of the shipped pin.)*

## §4 Ship shape

Branch `fix/dream-teeth-coverage` → adversarial review-to-zero (this spec) → `/code-review` → PR.
The user reserves the merge; the next cycle does not start until this one lands.

**Patch**, `0.4.28 → 0.4.29`: strictness on gates that were supposed to fire, with no schema, flag,
or install-contract change. Legacy records still render (every added parameter defaults to the
pre-fix behavior) and no live caller's flag usage changes (§2.5). The CHANGELOG states the new
failure modes explicitly, because a gate that newly fires **is** a user-visible behavior change:

1. a non-string/blank beat or stanza now fails the dream arc (exit 4, naming the index) — and, by
   precedence pin (6), **suppresses the NAR panel on that render**: the record-side arc owns it.
   A malformed-beat record that today shows a narration gap panel will instead show the arc panel;
   that is the intended precedence, and it is the one item here a user could mistake for a loss;
2. a stanza that normalizes to empty is now a narration gap (exit 4), not a silent pass;
3. an unknown flag is now a usage error (exit 2) on four scripts and `cm` — including
   **`--persist=DIR`**, which today exits 0 while silently degrading a judged terminal render to an
   unjudged preview, and including a bare **`--width`**, which no script consumes and which the
   precedent already rejects;
4. an **emptied** dream block now carries a `narration` block reading `failed`, where previously it
   carried none — visible to anything reading the log, including the archive;
5. a dreamless record carrying `usage` or `demotion` now fails the arc at `--persist` (exit 4) —
   the one intentional narrowing of a documented posture, measured at a single historical record.

6. **`--persist <dir that does not exist>` is now exit 2** where it was exit 0 — the one item here
   that changes the code of a call that previously exited *cleanly* while silently skipping every
   terminal gate. It reverses the approved plan's §5 line; §1 records the measurement that forced it.
7. **A *relative* `--persist` now works** (exit 0, on its absolute twin's slot) where it previously
   crashed with a 15-line `IdentifierRefused` traceback — the one item here that makes a previously
   *fatal* call succeed. Recorded because it is the inverse direction of every other entry;
8. **`-h`/`--help` are now exit 2 on four scripts** where three of them previously exited **0 doing
   something else entirely** (an extraction of CWD, a status report, a preflight of project dir
   `-h`). A user who typed `-h` wanted help and was silently given work; the new behavior is loud.
   `cm`'s `-h`/`--help` are unchanged;
9. **The documented commands are repaired across `commands/*.md` (8 files) and `SKILL.md`** — 61 of
   77 command lines were malformed. The user-visible change is that the commands run when pasted or
   followed: no more `python3: can't open file '…/x.py .'`, no more silent swallowing of every
   second command, no more `--persist` redirecting stdin from a file named `--persist`'s value. It
   is a docs fix riding a gate cycle, included because R2's job is that no live invocation breaks
   and this is the surface already broken.

Items 1–2, 5–8 change an exit code; 3 changes an argv contract; 4 changes what a log line contains;
9 changes docs and re-spells three pins whose assertions encoded the broken spelling (they required
the defect to pass — `amend-8` item 6). Nothing changes the cycle-record **schema**, so a legacy
record still renders and no downstream consumer needs a migration.

**Mutation matrix, re-run on the committed revision.** Every pin above is verified to fail on
pre-fix code. A pin that never moves on any revert is vacuous; the counts belong to the
**(restored code, fixture, harness)** triple and are re-derived here, never carried.

Measured 2026-09-14 against the build this spec ships. **The subject is a clone of the base commit
`308e15b`** — named by SHA and never as "HEAD", which moves with the branch and would silently turn
a re-run into a *post*-fix baseline — **byte-verified pre-fix on all seven changed product paths
(`cm` plus the six scripts: `dream_procedure` · `extract_signals` · `memory_status` · `preflight` ·
`render_dashboard` · `beta_checks`), running this branch's `smoke.py`** — not a `git worktree`, for
the reason below. ("Five" was this sentence's earlier number, and it was narrower than its own
claim: `git diff --stat 308e15b..HEAD -- 'plugins/**/scripts/*' cm` lists **seven** files, and the
driver reverts all seven in the `all_six` cluster.)

| tree | result |
| --- | --- |
| fixed (this branch) | **1920 passed, 0 failed** |
| pre-fix (every changed product file reverted to `308e15b`) | **1858 passed, 62 failed** |

`1858 + 62 = 1920`, and all **62** failures are `v0.4.29` checks — **0** failures anywhere else. The
pre-fix failure count therefore equals the genuine-pin count *exactly*: the 62 are precisely the
checks this cycle's diff moves, and the **63** further `v0.4.29` checks green on both trees are
precisely the labelled regression set (pins 3, 6, 8, 9, 15, 20, 29, 34, the F8 heredoc FEED, the F5
wrapper-with-bare-flag guards, the §2.2/§2.3/C2/C4/C6 negative arms, pin 42's second clause, and the
four non-flipping 10d/10e arms).
62 + 63 = 125 — the count the D6 census constant carries as its `+ 125`, verified as the
`v0.4.29`-labelled **runtime** check population (125 check lines carrying `v0.4.29` in the fixed
tree's output) rather than as whatever makes the arithmetic work. Nothing in the matrix is
unattributed.

**The regression set has two directions, and §3's preamble names only one of them.** That paragraph
describes it as *"the pins that catch an implementation which over-narrows"* — which is the **loud**
direction, a legitimate call losing its credit. The F10 round added a member of the other kind: the
`--recalls` case is green pre-fix not because the fix could over-narrow it but because the rewrite
could **drop an exclusion the shipped regex had** (`if "--recalls" in m.group(0): continue`), which
fails *silently* — the exact direction this cycle exists to close, reproduced in the instrument.
So the set is "checks whose only referent is a regression the fix itself could introduce", and
both directions belong to it. A green-pre-fix check is not evidence a fix was unnecessary; it is
evidence of which failure the check can still see — and for `--recalls` the answer is: only the
rewrite's, never the anchor's. It is a **port-fidelity guard**: it holds an old behaviour through a
translation that has no `group(0)` to read it from any more (§2.3). Measured three-column — anchor
`308e15b` unaccounted, first cut `2bad609` accounted (the exclusion lost), HEAD unaccounted again —
so it moved on the intermediate and cannot move on the anchor. `env -i` is the same class one step
further: it moves on **no** measured revision, and is kept as the boundary guard on the grammar's
no-value branch, which is one edit away from consuming `python3`.

**Per-cluster, and why the clusters are not a sum.** Every cluster's RED set is a **subset** of the
62, and their **union is exactly the 62** — so no pin is unattributed and none fires only in a
partial revert. The union is not the sum because pins are not one-per-file by construction: pin 38
asserts that a flag legal on ONE script is rejected on the others, so it moves on six clusters at
once (`cm`, `extract_signals`, `preflight`, `render_dashboard`, `arc_ms_rd`, `arc_dp_rd`); and
`pin 40 arm 3` appears in exactly two (`extract_signals`, `arc_ms_rd`).

**That union claim is only checkable against a defined check IDENTITY, and the printed label is not
one.** A RED line prints the check's label *with a dynamic tail appended*, naming the weakest site
the check found: pin 38 ends `· extract_signals.py accepted --demo` in one cluster and
`· render_dashboard.py accepted --audit` in another; pin 40 arm 3 ends `· --before is not a
extract_signals.py flag` against `… memory_status.py flag`. Keying a set comparison on that text
therefore measures *which file was reverted*, not *which check moved*: two naive attempts returned
**71** and then **65** for a union that is **62**, and the residual was always the same three checks
— the ones whose tail varies. The identity is the check's label as it prints in the **fixed** tree,
where it passes and carries no tail; a RED label is that identity plus its tail. Mapped that way,
every RED line in every cluster resolves to **exactly one** identity — 0 ambiguous, 0 unmapped,
across all ten — and each cluster's distinct-identity count equals its reported failure count. The
same defect as the `|DP| ∩ |RD|` note below, and as the cycle's own subject: a coarser key than the
question.

The driver's full-revert cluster is labelled `all_six` and reverts **seven** paths — the six Python
scripts *plus* the `cm` dispatcher. The label is the driver's and it is narrower than its
predicate, which is this cycle's own subject reproduced in the instrument built to detect it: an
earlier draft of this section recorded *"the six scripts reverted to `308e15b`"* as fact. The
counts below are keyed to the file list, never to the name. Measured spread over the eight
per-script clusters: **22 checks in one cluster, 26 in two, 11 in three, 3 in six** (22+26+11+3 =
62) — so no single cluster's count is the union, and the three checks that move in six clusters are
all pin 38's. The four pins the F10 round added all land in the *two-cluster* bucket (22 → 26),
which is the shape their arms predict: each is an attached-spelling or argv-position case judged at
the `dream_procedure` anchor, so it moves under `dream_procedure` and under `arc_dp_rd` and nowhere
else.

| cluster (files reverted) | passed / failed |
| --- | --- |
| fixed (none) | 1920 / 0 |
| `cm` | 1917 / 3 |
| `dream_procedure` | 1895 / 25 |
| `extract_signals` | 1912 / 8 |
| `preflight` | 1913 / 7 |
| `render_dashboard` | 1906 / 14 |
| `memory_status` + `render_dashboard` | 1891 / 29 |
| `dream_procedure` + `render_dashboard` | 1881 / 39 |
| `beta_checks` | 1920 / **0** |
| every changed product file (`cm` + the six scripts) | 1858 / 62 |
| every changed product file **except** `memory_status` | 1872 / 48 |

The `beta_checks` row is **0 by design, not by absence** — see item 11: the change there is a
compatibility shim whose branch is identical while `memory_status` stays fixed, so no single-file
mutation can move it. `memory_status` alone is not a cluster because it is not a coherent state:
reverting it alone crashes the suite (`TypeError: arc_completeness() got an unexpected keyword
argument 'enforce_post_arc'`) rather than reporting RED. **A crash is not a RED**, and the driver
prints it as such rather than letting it read as a clean zero.

**The counts are the TRIPLE's, not the pins'.** A mutation's RED count belongs to (the code it
restores, the fixture, the harness) together, so every number above was re-derived on the frozen
committed revision rather than carried. This is not rhetorical: the previous run of this matrix was
**invalidated mid-flight** — its driver copied the *working-tree* `tests/smoke.py` at each mutation,
so clusters that ran after an edit measured a different harness than the baseline, and the
uncommitted F9 fix made pin 42 RED even in the `beta_checks` cluster, where it has no cause. The
driver now takes the harness from the archive and **refuses to run against a dirty tree**, so the
flaw cannot silently return; it also counts RED as `'^  ✗ '` rather than any `✗` in the output, which
read 3 with zero failures (three `✗` sit inside *passing* labels — the v0.1.54 render checks assert
the glyph is printed). The anchor's own contribution is stated separately and more sharply in §2.3:
restoring only `dream_procedure.py` gives **1895 passed, 25 failed**, and the two sets are exactly
disjoint — `|DP| + |RD| = 25 + 14 = 39 = |arc_dp_rd|` with an empty intersection — so all 25 are the
anchor's own and not one of them needs a second file reverted. (An earlier draft of this sentence
claimed 14 of the then-21 also moved under `render_dashboard`. That came from grouping RED lines by
pin *number*, which pools the six distinct `C1` checks and the three distinct `pin 37` checks into
one label; keyed on the full label the intersection is empty. Same defect as the one this cycle
exists to close, in my own analysis: a coarser key than the question — and the same trap the union
test above sprang, where the *printed* label was the coarser key.)

**The matrix found its own instrument first.** The first three runs died mid-suite, each on a pin
that asserted on post-fix API without probing it (`amend-9` item 11). The fourth ran to completion
but reported **59** failures, 6 of them outside `v0.4.29` — all in the preflight-beacon region.
(Those are **that** run's numbers, on the revision then current — not the table's, which belong to
the triple frozen at `ce3e182`. Every count in this section names its revision for that reason.)
They were not pins. `git worktree add` writes a `.git` **file** (`gitdir: …/.git/worktrees/<name>`
— a linked worktree), and `store_context._common_from_gitdir` follows its `commondir` to the
**main** worktree, correctly, since a linked worktree *is* the same project. Inside the mutation
tree the product therefore resolved the project identity to the original repo's path while the
suite pinned state under `slug_for(ROOT)`; six checks that write a state file into a hermetic `HOME`
and assert the beacon's silence then failed on an identity mismatch, not on pre-fix code. Proven
environmental rather than mutational by running the **fixed** tree's `preflight.py` with
`cwd=/tmp/mut-tree`: it writes to the **main worktree's** slug too. The harness now
**clones** instead of linking a worktree (its own real `.git`, no `commondir`) and asserts the two
identities agree before the run. A red baseline is the dangerous direction — it lets an environment
failure wear a pin's clothes.

**Every `file:line` citation this spec's drafts carried was stale before it shipped, and that is a
measurement, not a stylistic preference.** The standing rule is *greppable anchors, never
`file:line`* (the v0.4.25 rule); the drafts carried 16. Two of them name a line in a file **this
branch edits**: the `distill_scan.py … --json > "<the --scan path>"` redirect sat at
`SKILL.md:1085` on the base commit `308e15b` and at **1090** from the branch's *first* commit
onward — so every commit on the branch cited a line that no longer held it, and nothing failed.
The census table fared worse. Re-checking its line numbers one by one at close: of six,
**four no longer located their call** — `beta_checks.py:444` was `import tempfile`,
`beta_checks.py:1571` a `def`, `make_cycle_probe.py:102` blank, `smoke.py:14955` the tail of a
dict literal — and two still did. None of that was wrong when written; it is what a line number
*is*: bound to a revision, and invalidated by any edit above it, silently, for every reader
thereafter. All of them are now anchors — the literal (`import _ui`), the helper name (`_run19`),
the quoted command — and the three evidence-ledger rows name the pin by its label instead. The
failure was not the drafting, it was the **genre**: a citation form with a known expiry date was
used for claims expected to outlive it.

**End-to-end, because this cycle changes what a pass does.** Run a real `dream` and confirm: a clean
pass still exits 0; a malformed beat exits 4 naming the index; an empty-normalizing stanza exits 4
naming the gap; a misspelled `--persist` exits 2 and appends nothing.

The gate arms are executed at the real subprocess boundary by the pins themselves (14, 15, 17, 18,
19, 27, 31, 35) and the clean pass by smoke's v0.4.19 F19 pins. What those bypass is the **operator
surface** — the `cm` wrapper, which is what a maintainer actually types — measured end to end:

| command | measured |
| --- | --- |
| `cm bogus` | rc 2, usage on **stderr**, 0 stdout lines |
| `cm --help` · `cm` bare | rc 0, 90 stdout lines, 0 stderr |
| `cm render --persit REC` | rc 2 · `unknown flag: --persit` |
| `cm render --persist ""` | rc 2 · `--persist requires a directory argument` |
| `cm render --persist /nope` | rc 2 · `dir not found: /nope` |
| `cm render --persist=DIR` | rc 2 · `unknown flag: --persist=DIR` |
| `cm render --width REC` (bare) | rc 2 · `unknown flag: --width` |
| `cm render --width=80 REC` | rc **0**, renders |
| `cm extract --jsoon .` | rc 2 · `unknown flag: --jsoon` |
| `cm doctor` · `cm status` | rc 0 · rc 0 (139 lines — the clean pass still exits 0) |

**The full gate set**, unchanged from the repo's dev loop — measured, sequentially, never
concurrently (the v0.4.28 story was a timing flake under load):

```bash
python3 tests/smoke.py                                    # 1908 passed, 0 failed
python3 tests/docs_links.py                               # ✓ badge + 6 live docs at v0.4.29
python3 tests/simulate_accumulation.py                    # green — all lifecycle properties hold
mypy --config-file mypy.ini                               # Success: no issues found in 42 files
python3 tests/validate_manifests.py                       # ✓ v0.4.29
python3 tests/dashboard_browser.py --out /tmp/cm-browser  # 1334 browser checks passed
```

**The genericity pin caught its author.** This file is inside the pin's scanned root (`docs/`,
`.md`), and the worktree-defect narrative above was first drafted naming the maintainer's real slug
in the `-home-<name>-` form — so the pin fired on this spec, mid-cycle, at `1887 passed, 1 failed`.
Repaired in the same commit, and by mechanism rather than by redaction: the literal became "the
**main worktree's** slug", which carries the reason instead of hiding the value. The pointed part is
the timing: the suite count above was first measured **before** this file's §4 was written, so the
leak sat in a tree that had already reported clean. Not a gate narrower than its rule — a gate
**older than its subject**. Same class, one remove.

**The repair then reproduced the pin's own ceiling — measured, and left open.** Both of the pin's
slug arms require a dash *after* the name, so a **bare** `home-<name>` matches neither: the first
draft of the paragraph above carried exactly that form, and `grep` found it while the pin did not.
The narrowing is nonetheless **right as it stands**, and the counterfactual measures why. Dropping
the trailing dash fires on 3 distinct names — and **2 of them are this product's own vocabulary**:
`home-domain` (the user's home domain, 2 sites) and `home-scoping` (the firewall's scoping
mechanism, 2 sites). The 4 legitimate hits include `CHANGELOG.md`'s historical record and the pin's
own assertion needle, neither of which a matcher has any business editing. A gate that fires on
`home-domain` is a gate that gets muted, which is worse than one that misses a bare occurrence.
Closing this properly needs a discriminator the pin deliberately lacks — a personal-name deny-list
*is* the leak it exists to prevent, and it would not generalise to the skill's users — so the blind
spot is **recorded, not closed**: a scheduled decision, not a silent one.

## §5 Known ceilings (documented, not solved)

- **Presence, not performance.** §2.3 makes the anchor an execution anchor, but only of the
  *command*: it cannot see whether the extractor's output entered the pass, nor distinguish a
  coordinated burst. This is `docs/dream-narration-teeth.spec.md` §5's ceiling, unchanged and
  unclaimed here.
- **`-X`/`-W`-style value flags are permissive.** The token is required to be *an argv element* of
  the interpreter's segment, so `python3 -X importtime <tok>` is accounted even though the script is
  not literally the first non-flag argument. This is the deliberate direction of error (§2.3's
  tokenizer rejects only the two flags that consume a *payload*); the alternative — enumerating
  python's value-taking flags — buys precision at the cost of a list that drifts with the
  interpreter.
- **`--persist <dir that exists but cannot be appended to>` still exits 0 and still skips the gates.**
  The missing-dir case is now refused (§1, §2.5), but `_persist`'s *other* failure status,
  `io-error` (permissions, full disk), reaches the same `return 0` before `procedure_integrity` and
  `arc_completeness` are consulted. Left open deliberately: the trigger is an **environment fault**
  rather than a typo, so a refusal would trade a silent clean for a hard stop on a degraded
  filesystem, and the livelock is real — a gate-failing record could never reach exit 0 without a
  writable log. Named here as measured-and-open so the next pass inherits a known hole instead of
  rediscovering it; closing it properly means deciding how the gates and the write failure compose,
  which is a bigger change than Cycle A's charter.
- **The wrapper set is a bounded, hand-written table** (`env` · `time` · `nohup` · `sudo` · `command` ·
  `exec` · `xargs` · `setsid` · `nice` · `stdbuf` · `ionice` · `timeout` · `flock`), each entry
  carrying its own argument grammar, with the same character as `_POST_ARC_KEYS`: it closes the
  measured class and it will not generalise to a wrapper nobody listed or a flag nobody modelled. A
  wrapper outside the list is unaccounted. That is *loud* — an exit-3 the model can see — which is
  why the table can stay short, and it is why the second cut's 12 dropped forms were a defect worth a
  cycle and not a cost worth accepting. The alternative, enumerating "any token that could precede an
  interpreter", is unbounded and would re-open `echo python3 …`.
- **A user-defined shell FUNCTION is unresolvable, and the corpus contains three.** Measured over the
  503 real commands (§2.3): `probe … python3 $S/extract_signals.py --json`, where
  `probe(){ … "$@"; }` runs it, is **unaccounted** — the anchor cannot follow a name it has no
  definition for, so it fires. This is *Uncertain → fire* working as contracted, and the alternative
  (resolving function bodies) means parsing a shell script, which is unbounded work for a gate whose
  job is to catch a *missing* call. Recorded because it is the one shape in the corpus where the
  anchor's verdict differs from ground truth, and a future pass should inherit it as known rather than
  rediscover it as a bug.
- **`_POST_ARC_KEYS` is a two-key list with a dated rationale.** It closes the hole for every record
  written since v0.1.63. A hypothetical record carrying *only* pre-v0.1.63 keys while skipping the
  arc is indistinguishable from a legacy one by construction — that is the price of dating an
  unstamped artifact structurally, and it is stated here rather than papered over.
- **The archive renders the empty-normalizing *string* class as narratable** (§2.1). The gate is now
  closed against `"*"`, `"***"` and `"> "` — `normalize_beat_text` empties all three and §2.2's gap
  rule fires — but `dashboard.sections.js`'s `unwrapped()` only strips a *matched pair* of `*`/`_`
  delimiters, so `"*"` and `"***"` survive it as a literal asterisk and are painted in the
  `dream-voice` class, and `"> "` becomes a **blank** voice paragraph. The non-string class is
  handled correctly there (`null`/`""`/`"   "` → *Not captured*; `{}`/`0` → their JSON form). So the
  archive is **not** stricter than the gate for this class, and a beat that now fails the arc would
  still *display* as captured dream-voice in an archived record. Left open deliberately: the archive
  is a display surface, Cycle A's charter is the gates, and the fix would land in a third file with
  its own browser-check baseline. It is bounded by the same measurement §1 carries — **0** records in
  the 55-record archive have a beat normalizing to empty — so the exposure is prospective, not
  historical.
- **The narration arm proves presence, not per-beat attribution** (§2.2). `_gaps` asks
  `any(needle in n for n in norms)` over one pooled list, so a single block satisfying all seven
  needles reads as `7/7 narrated` — measured, along with the six-identical-beats and three-blocks
  variants. A dense narration does satisfy the contract as written (*"All checked texts must
  narrate"* is about which texts are checked, not how densely they are spread), so this is not a
  false clean of §1's kind; what it is not is a per-beat mapping, and the numerator reads like one.
  Requiring distinct blocks would be a **stronger** rule than the contract implements — a new
  requirement smuggled in as a bug fix — so the ceiling is named instead of adopted.
- **`sync_global.py` is a fifth entry point with an unclosed unknown-flag class** (§2.5). Its
  strictness is **positional-0 only**: `--jsoon .` exits 2, but `--list --jsoon .` and
  `--tokens --jsoon .` both exit **0** with empty stderr — the token is silently accepted one
  position to the right. No `--fleet`/`--tokens` mode guard exists either (measured; the plan cited
  one). It is outside the decided scope ("all five lax scripts + `cm`"), so it is **left unfixed and
  named**, not quietly implied closed. The one real guard there is `--evict`, which protects a
  destructive swap on the wrong mode and is unrelated to unknown tokens.

## Evidence ledger

Every number above was measured on the pre-fix tree at `308e15b` unless marked otherwise.

| claim | how |
| --- | --- |
| the all-`'*'` record verifies | `dream_procedure.judge` with an injected `scan_fn` returning zero text blocks + one accounted `--json` Bash line |
| `_checked_texts` shrinks | the same function over `[null]*6`, `[{}]*6`, `[0]*6`, and a mixed record (sets of 1, 1, 1, 4) |
| C1's `1/1 narrated` | `judge` on six `null` beats + a narrated sleep, EXT accounted |
| C2 is unconditional | `judge` on the `'*'` record against **two** transcripts — empty, and narrating the sleep — both giving `7/7 narrated` |
| the four EXT holes | `_INVOKE_RE.finditer` over each command, printing `group(0)` — the continuation case matches `'…extract_signals.py \\'`, truncating `--recalls` out of the match |
| the `\\\n` asymmetry | read at the source: reachable by backtracking in the lazy prefix, unreachable in the greedy tail; both directions confirmed by the finditer output |
| the §2.3 prototype | the proposed unfold→split→`shlex`→decide anchor, run over 16 cases against the shipped anchor's verdicts; 16/16, differing on exactly the four C4 holes |
| the §2.3 compatibility table | **three** implementations — the shipped `_INVOKE_RE`, the pre-wrapper prototype, and the fixed one — over the same **14** forms, printing all three verdict columns. Shipped and fixed agree on all 14 except the four C4 holes; the pre-wrapper prototype diverges on **8** accounted-today forms |
| the panel/gate desync | `render_dashboard` on a stamped 2/6-beat record across `--persist <real>` / `<missing>` / `""` / `--persist=<dir>` / `--persit <dir>` / no flag: exit code + panel presence + log delta per run |
| C6's four-way collapse | `judge` over the four shapes; pre-fix all four return the legacy reason. Plus `bool(_checked_texts(rec))` for the three emptied shapes and the dreamless one — all `False`, which is the `render_dashboard` gate's skip condition |
| the flag table | each script run with `--jsoon`; exit code and stderr captured |
| the persist table | `render_dashboard --persist` against a temp store, log counted at `retention.cycle_log_write_path` (the plugin-data plane, not the native dir) |
| the 55-record census | `memory_status.iter_store_cycle_log` over `retention.cycle_log_read_paths` — 55 records, 17 dreamless, 0 malformed, 0 empty-normalizing, 7 `narration` verdicts (all `verified`) |
| the §2.1 type census | the same union walked for `type(sleep)`/`type(wake)` (both all `str`, 38/38), blank-or-non-string beats (0), and present-strings normalizing to empty (0) |
| the §2.1 flip count | the strict predicate vs `arc_completeness` over the 38 dict-dream records — 23 complete before, 23 after, **0** flips |
| the narrowing's 1 true positive | the same walk filtered on `_POST_ARC_KEYS`, plus the neighbouring records' key sets; and the over-fire counter-check (35 records carry a post-arc key *with* a dream block) |
| the criterion table | the five candidate predicates of §2.4 run over the same 17 dreamless records |
| the mandate date | `CHANGELOG.md`'s `[0.1.54]` (2026-07-01) section, plus the mandate itself from `docs/dream-arc-contract.spec.md` |
| each `_POST_ARC_KEYS` version | `git log --reverse --format=%H -S'record["<key>"]' -- <path>`, then the first tag containing that commit. **Not** CHANGELOG prose: it matches the bare word in any sentence and dates `demotion` to v0.1.8, eleven releases early |
| the widened tuple is inert | `arc_completeness` + the strict predicate over the 55-cycle archive (0 newly firing) and the 69 records across 11 store logs (44 dreamless, 0 newly firing) |
| the §2.3 F5 false fires | `judge` end to end (the `_ext29` seam) over the 12 forms; 12 unaccounted on the pre-fix tree, 12 accounted here |
| the §2.3 F8 silent hole | the same seam on `cat <<'EOF'` + the command in the body; **accounted** on the pre-fix tree, unaccounted here |
| the corpus, regex → final | two processes, one tree each: the shipped `_INVOKE_RE` rule and the final anchor, each emitting `A\|u` + the command for every assistant Bash command containing the token — 946 JSONL files, 503 rows, 95 vs 46 accounted, **49 flips one way and 0 the other** |
| the 49 flips classified | the row set printed and grouped by shape; 46 non-executions (10 heredoc/`cat >` writes, 25 `python3 -` stdin scripts, 6 `python3 -c`, 1 `grep`, 4 prefixed writes) and 3 shell-function-mediated calls, each then re-checked for a *direct* interpreter-led extractor segment — **0 found in all four** |
| the corpus, first cut → final | the same two-process diff against the first §2.3 cut: **0 flips either way** (46 accounted both sides), which is what makes the 12 forms latent rather than observed |
| the R2 sweep | every flag literal at every live call site, against each script's branch-set |
| the F19I fixture's shape | `tests/smoke.py` — `project`/`session`/`scope`/`verification`/`marker` only |

**Added in amend-7 (the fold after the second adversarial round).**

| claim | how |
| --- | --- |
| the C4 direction table | `_INVOKE_RE.finditer(...).group(0)` on three commands — the path-split pin's, the hole's, and the `--recalls` pin's — showing the first **not** truncated, the second truncated at `'…extract_signals.py \\'`, the third not applicable |
| the `\\\n` asymmetry, refuted the other way | delete the `\\\n` alternative from `_SEG` and re-run the pin's own command: `finditer` returns **zero** matches, so the pin **fails**. The pin passes *because of* the alternative, not in spite of it — which kills the first draft's claim that truncation is what makes it pass |
| the archive's string class | `dashboard.sections.js`'s `passage()` with `paragraph()` instrumented to log calls. `passage()` has **no return statement** — it appends to `arc` — so two earlier probes returned `undefined` for *every* input, valid ones included, and measured nothing. The logged `paragraph()` calls are the measurement: `"*"`→`("VOICE","*")`, `"***"`→`("VOICE","*")`, `"> "`→`("VOICE","")`, `""`/`"   "`/`null`→`("note","Passage 1: Not captured")`, `{}`/`0`→JSON |
| the membership table (§2.2) | `judge` with an accounting EXT fixture over three shapes: 7 distinct needles in **one** block, 6 identical beats, 3 blocks covering 7 slots — all three `verified · 7/7 narrated` |
| the value assertion (§3 pin 1) | a `str()`-coercing `_checked_texts` swapped in: it also returns 7 entries, so a **count-only** pin passes both the shipped and the coercing implementation, and the coercing one returns `verified · 7/7 narrated` on an all-numeric record against a transcript containing `0` |
| the pin-19 preconditions | the bare fixture (no accounting EXT call, no live session dir) exits **0** as `degraded (transcript unavailable)`, not 4 — so the pin's fixture is part of the pin |
| the corpus measurement (§2.3) — **SUPERSEDED by amend-8, kept as the record** | 908 JSONL files under the session dirs, 390 commands mentioning the extractor, 56 accounted by the shipped anchor, **15** of those flip to unaccounted under the fixed anchor — **all 15 false accounts** (heredocs and echoes), **0** genuine execution forms. This is a *corpus* measurement; the §2.3 14-form table is a *constructed-forms* measurement, and the two are not the same claim. Amend-8 re-ran it on a larger corpus (946 files) with the *final* anchor as the subject and found **three** of the flips are not false accounts at all — see §5's shell-function ceiling. The "all 15" clause above was true of the 15 it saw; the row is kept because a superseded measurement that agrees with its successor on the direction is evidence, and rewriting it would destroy that |
| the `-h`/`--help` table | each of the five run with `-h`; exit code plus what it actually did (see §2.5). Post-fix each is 2; `cm -h` stays 0 |
| the relative-`--persist` crash | isolated `HOME`, `--persist memory` on a directory that **exists** → exit 1, 15-line traceback ending `IdentifierRefused: invalid project id ''`; identical for `.` and `./memory`; absolute spellings exit 0. Mechanism read at the source: `retention._ops_slot` keys on `native_store.parent.name`, and `Path("memory").parent.name == ''` (measured) |
| the docs census (§2.5) | `git show HEAD:<file>` for all 8 `commands/*.md` + `SKILL.md`, bash blocks extracted, then per **command line**: class-A regex (unclosed quote after the script path) and class-B regex (unquoted `<…>`), plus `bash -n` per block. 77 lines, A=47, B=28, overlap=14 → **61 malformed, 16 clean (all in `SKILL.md`)**, 0 blocks failing after repair. Re-derivable from HEAD, so the number is not a recollection |
| the cm-connect.md specimen | verbatim, pre-fix: line 15 is *balanced* but is **one argument** — `python3: can't open file '…/preflight.py .'`, exit 2 — and `bash -n` fails on blocks **1 and 3** (rc 2, `syntax error near unexpected token`), while blocks **2 and 4** pass *only* because their quotes pair across lines |
| the flag census over the docs | every `--flag` on all 77 lines checked against its script's branch structure: **all defined** (including `--registrar` and `--workflows` on `sync_global`) — so the repair is spelling-only and R2's flag conclusion is untouched |
| arm 2's rule, measured both ways | the genuine redirect `python3 x.py . --json > "out.json"` is **not** flagged; `--pull <other-repo>` **is**. The first draft of arm 2 (`"no < or > in the line"`) flagged the genuine redirect — the over-strict direction, caught before adoption |
| the three defect-pinning pins | `python3 tests/smoke.py` after the doc repair: **3 failed**, all three asserting a raw broken literal — the `native_memory_dir` Phase-5 pin, the `cm-connect sequences positional-first` pin and the `/cm-group` confirm-phrase pin. Re-run after quote-normalizing the haystack: **1795 passed, 0 failed** — same total, so no check was added or lost |
| the sync_global table | `--list --evict=x` → 2; `--list --fleet=personal` · `--tokens --fleet=personal` · `--pull --tokens` · `--list`/`--tokens`/`--gc` `--jsoon` → 0, empty stderr; `--jsoon .` → 2 (usage). Positional-0 only — re-confirmed on `-h`, which is the row that makes the §2.5/§5 contradiction visible: `sync_global --list -h .` → **0** |
| the `-h`/`--help` mechanism split | `distill_scan.py -h` / `--help` → 2 with `unknown flag: …`; `sync_global.py -h` / `--help` → 2 with `usage: …`. Same exit code, **different mechanism** — the second is positional-0, so it is not a pattern source for the fix |
| the `--` measurement | `render_dashboard.py -- /dev/null` → exit **1**, `cannot read cycle record: '--'`; `extract_signals.py -- .` → exit **0**, swallowed. Measured **unpiped** — a first attempt piped through `head`, which made `$?` `head`'s status (0) and briefly recorded the wrong code for the first arm |
| the over-fire counter-check (§2.1) | the strict stanza predicate over the **string** class: `"*"`/`"***"`/`"> "` all normalize empty, so all three are now gaps — and the pinned pre-existing case `normalize_beat_text('*') == ''` is what identifies them, not a new rule |

**A fixture trap worth recording, because it silently inverts the result.** `judge` fails on
`missing or not accounted`, so a malformed EXT fixture does not merely lose the EXT arm — it forces
`failed` and **hides** whatever NAR found. The first attempt at the §1 headline used a plausible but
wrong line shape and returned `failed`, which reads as "the reproduction does not reproduce." The
real shape is nested three deep:

```python
{"message": {"role": "assistant",
             "content": [{"type": "tool_use", "name": "Bash",
                          "input": {"command": "<the command>"}}]}}
```

**A second trap, found by re-running rather than accepting the first answer.** The oracle row above
was first probed by walking `beta_checks.py`'s AST for `is_complete` and keeping the last match —
which is the **demotion** family's predicate, not the dream family's. Every dream shape then graded
`complete=False`, i.e. the oracle looked *stricter* than the product and the §2.1 claim read as
refuted. `beta_checks.py` defines **six** nested `is_complete` functions, one per check family, so
the name is not a key. The corrected probe extracts the function's **source** and calls it. Recorded
because it is the cycle's own thesis occurring inside the cycle's own instrumentation: a matcher
that is not the rule it is believed to be, failing in the direction that looks like a finding.

Anyone re-deriving these numbers must build that shape, or the headline appears falsified. Recorded
here because the failure mode is a false negative that looks like a refutation.

## Amend ledger

- **amend-1 (draft, 2026-09-14):** initial design-of-record. Carries the audit's measured
  reproduction, the five defect faces, the `enforce_post_arc` scoping (renamed from the plan's
  `require_dream`), the version-grounded `_POST_ARC_KEYS` discriminator with its 17-vs-1 measurement,
  the `stanza_present` predicate extended to `sleep`/`wake` (the plan scoped it to `beats` only; the
  render panel's independent `_have` would otherwise contradict the gate), and two corrections to the
  plan: pin 19's exit code (4, not 3) and the R2 sweep's completion inside this spec rather than
  after it.

- **amend-2 (draft, 2026-09-14, self-review before the adversarial round):** five changes, four of
  them forced by re-measurement and one a defect the first draft missed entirely.

  1. **A wrong number, corrected.** §2.4 said a blanket "missing `dream` fails" would newly fail
     **13** records. It fails **17** — all of them. The 13 belonged to a looser criterion the
     sentence did not name, and no criterion tried reproduces it (the table in §2.4 records what each
     one actually yields). The narrowed rule's **1** was re-derived and stands. A number whose
     criterion is not stated is not a measurement, and this draft now states, for each figure, the
     predicate that produced it.
  2. **C6, a defect the first draft missed.** The legacy carve-out is implemented three times and the
     second and third sites test the wrong predicate: `judge`'s `if not checked:` and
     `render_dashboard`'s narration gate both collapse *"no dream block"* (`None`) with *"a dream
     block carrying nothing usable"* (`[]`). Measured, four shapes produce the identical legacy
     verdict and the identical legacy reason, and none of the three emptied shapes gets a `narration`
     block — so the archive's documented *"absence means pre-feature"* inference is false for them.
     §2.2 now fixes all three sites; §3 gains pins 25–28. The exit code is unaffected (the arc gate
     already fails an emptied block and both arms exit 4), which is why this is an honesty defect
     rather than a false-clean one — and why the first draft, hunting exit codes, walked past it.
  3. **§2.3 was missing a rule its own pins depend on.** The step-4 decision list omitted the
     `--recalls` exclusion, which pins 7 and 9 assert. Restated as an **argv-token** test on the
     segment (the old substring test on `group(0)` no longer has a `group(0)` to read). The section
     now also records the prototype's result — 16/16, differing from the shipped anchor on exactly
     the four C4 holes — and states that `endswith("/" + tok)` carries the old lookbehind's work.
  4. **Pin 5's justification was wrong** (its asserted value was right, which is the dangerous
     combination). It claimed the all-`'*'` record fails because "the sleep slot alone cannot
     narrate". Measured, the record is certified `7/7 narrated` against a transcript that *does*
     narrate — the true reason is that all seven needles normalize to empty, so the record presents
     nothing narratable. The pin is amended, and pin 4's stronger half is recorded.
  5. **A fixture trap recorded in the evidence ledger.** The first attempt to reproduce §1's headline
     returned `failed` rather than `verified`, because a malformed EXT fixture forces the verdict
     through `missing or not accounted` and masks whatever NAR found. The correct three-deep line
     shape is now written down, since the failure mode is a false negative that reads as a
     refutation.

  Not changed, and re-verified rather than re-asserted: the §2.1 retro-compatibility claim (now
  measured as a 0-record flip over the union rather than inferred from a beat census), the
  `_POST_ARC_KEYS` scoping, and the exit-ladder claim in pin 19 — re-checked against
  `render_dashboard.main`, which confirms NAR gaps exit **4** and exit 3 is the EXT sub-arm.

- **amend-3 (draft, 2026-09-14, from the three reconnaissance sweeps):** six additions, all of them
  *sites and hazards*, none of them a change of decision. The sweeps were run as inputs, and they
  paid for themselves by finding things a decision-level review could not.

  1. **A second implementation of the predicate — and a comment claiming there is only one.**
     `beta_checks.py`'s `is_complete(dream)` duplicates `arc_completeness` nearly verbatim, `str()`
     coercion included, while `tests/smoke.py`'s pin block is captioned *"the SINGLE completeness
     predicate … one definition, no reimplementation drift."* The claim was unmeasured when written
     and is false now. §2.1 states which rule the oracle takes (the type rule, not
     `enforce_post_arc`) and why, and carries the measurement: the oracle returns `complete=True` for
     `[null]*6`, `[{}]*6` and `['*']*6`, failing only on a wrong beat **count**. A closed set —
     `is_complete` occurs six times in that file, one per family — which is why the probe extracts
     the source by line rather than by name.
  2. **The frozen canary must not move.** `canary-v0.1.19/memory_status.py` is a vendored known-bad
     artifact, byte-faithful to its tag and SHA256SUMS-manifested; it carries a third copy of the
     predicate that is *supposed* to stay wrong. §2.1 says so explicitly, because "fix every copy of
     the buggy predicate" is the obvious reading and the wrong one here.
  3. **`_ui` parses raw `sys.argv`.** So the visual flags live outside any locally-derived allowance,
     and an allowlist grepped from a script's own flag literals is incomplete by construction. This
     is §2.5's sharpest hazard and the reason its per-site table is labeled a pattern to copy rather
     than content to transcribe.
  4. **The non-dict guard in §2.4's sketch is load-bearing.** The existing pin asserts
     `arc_completeness("junk") == (True, "")`. The sketch now keeps the `isinstance` test in both
     places, and §3 carries a table of the pre-existing pins the change sits inside — including two
     **exact reason strings** (`4/6 beats`, `dream block malformed (not a dict)`) that a rewording
     would break silently.
  5. **The five sites fail three different ways.** `render_dashboard`/`memory_status`/`extract_signals`
     skip; `preflight` mis-slots; `cm` forwards or drops. §2.5 already treated them separately; the
     sweep is what turns that from caution into a measured fact.
  6. **The HTML archive already does the right thing.** `dashboard.sections.js`'s `passage()` guards
     on `typeof v !== 'string' || !v.trim()` — **the type rule §2.1 introduces, reached
     independently** — and its fallback names the gap for `null`/blank (`"Not captured"`) or
     JSON-dumps it. Run on the extracted function: `[null]*6` yields six `Passage N: Not captured`
     lines around a narrated sleep and wake, `[{}]*6` yields six `Passage N: {}`. So pre-fix the
     archive is stricter than the gate on every non-string beat, and **explicit** on exactly the
     headline shape — it displays a gap the gate calls complete. That is independent evidence the
     type rule belongs on the arc side, and it means the fix aligns two surfaces rather than
     inventing a rule.

  The R2 landing gate is re-stated in §2.5 against the sweep's full invocation table: **every flag
  reaching the four lax scripts is defined**, `cm beacon` passes none at all, and `--tokens`/`--list`
  land on `sync_global`, which is already strict and unmodified.

- **amend-4 (draft, 2026-09-14, self-review while the adversarial round runs):** three corrections,
  every one of them from *re-running* a claim that had been made by reading. Two sharpen amend-3's
  own items; the third corrects §2.5's opening.

  1. **The oracle claim, now measured.** amend-3 said `beta_checks.py`'s predicate "duplicates
     `arc_completeness` nearly verbatim, `str()` coercion included" — true, and far too weak. Running
     the extracted function: `[null]*6`, `[{}]*6` and `['*']*6` all return `complete=True` with
     narrated `sleep`/`wake`; only a wrong beat **count** returns `False`. The QA oracle certifies the
     exact record class this cycle exists to catch, and its own `or ""` comment sits one line above the
     hole. §2.1's bullet now carries the verdicts.
  2. **The archive claim, now measured.** amend-3 said `passage()` "renders a non-string beat as *'Not
     captured'*". It guards on `typeof v !== 'string' || !v.trim()` — the **type rule §2.1
     introduces** — and then branches: `null`/blank → `"Not captured"`, anything else →
     `JSON.stringify(v)`. Run on the extracted function, `[null]*6` prints six `Passage N: Not
     captured` lines; `[{}]*6` prints six `Passage N: {}`. So the archive is not merely honest, it
     applies the shipped rule — the strongest available evidence that the type rule is the intended
     contract rather than this spec's invention.
  3. **§2.5's precedent was over-claimed.** It said smoke "already asserts for two scripts: exit 2,
     `unknown flag: <flag>` on stderr". Smoke pins exit 2 twice, but only `distill_scan.py`'s pin
     covers the **message**; `calibration_report.py`'s pins the code alone because it inherits the
     behavior from `argparse` (`error: unrecognized arguments:`). And the plan's second pattern source,
     `sync_global.py`, turns out to be a different rule entirely — a mode-mismatch refusal. The
     section now names the one copyable shape (`distill_scan.py`'s hand-rolled loop) instead of
     gesturing at "two scripts". A precedent cited loosely is how a copied shape drifts from the one
     that was pinned.

- **amend-5 (draft, 2026-09-14, the adversarial round's first report):** two confirmed defects in
  §2.5, both on the axis the spec had not examined — **the form of a flag**, as distinct from its
  spelling. Both were independently re-measured here before being folded; one peer claim was
  corrected in the process, and one line of attack came back clean.

  1. **The visual surface was mis-transcribed, in both directions at once.** §2.5 wrote the
     exemption as four bare words (`--ascii`/`--color`/`--no-color`/`--width`). The real surface is
     `--ascii` · `--color` · `--no-color` · `--color=*` · `--width=*` — the two equals forms were
     missing and the bare `--width` was **invented**. The invented one is the dangerous half: no code
     path consumes bare `--width` (`_ui.resolve_width` matches `startswith("--width=")` only), so
     exempting it would add a silent no-op — the exact defect C5 exists to close, re-opened by C5's
     own fix. The repo's predecessor spec states the set correctly; this section had drifted from it.
     §2.5's *trap* list had it right, so the section contradicted itself.
  2. **A third `--persist` form, and it is the only one that disables the gate rather than the
     write.** `--persist=DIR` never sets `persist_dir`, so `judged = persist_dir is not None` is
     false and the record renders as an **unjudged preview**. Re-measured here on the shipped
     argument order with a stamped, arc-incomplete record: bare `--persist DIR` → exit **4**, the
     gate fires; `--persist=DIR` → exit **0**, and `--persit DIR` and the no-flag preview are both
     **0** as well. The equals form is the more dangerous of the two because it is *plausible* — the
     ecosystem takes `=` for `--color=`, `--width=`, `--evict=`, `--fleet=` and `--into=`. Decision:
     **reject**, exit 2, any token that is not exactly `--persist`; accepting would put a second
     parse path inside the one predicate that decides whether a record is judged at all, and the
     silent direction is the one this cycle exists to close. §2.5 now carries the measurement table
     and the reasoning, and the R2 census confirms no live caller uses the form.
  3. **A peer claim corrected rather than accepted.** The report's sub-point was that `preflight.py`
     "has no `_ui` call at all", so exempting `--ascii` there is moot. It **does** call `_ui` —
     `preflight.py`'s own `import _ui`, then `ui.rule()`, `ui.lbl()`, `ui.c()` — so a grep for `_ui`
     finds three hits and suggests a visual surface. The *conclusion* holds for a sharper reason: it
     never calls `set_modes`/`resolve_color`/`resolve_width`. §2.5 now says "what this script
     consumes, not what it imports", which is the rule that generalizes; "no `_ui` call" is the
     coincidence that would have misled the next reader in the opposite direction.
  4. **The equals-form axis has in-tree precedent, and it was worth sweeping.** `--evict` is
     equals-**only**, `--into` has both forms, and `--width` is equals-only in the opposite
     direction (bare parsed by nobody) — so "a value flag takes both forms" is wrong three ways.
     `sync_global.py`'s `--into=` branch carries the comment *"review fix: the equals form was
     silently ignored"*: this class has already cost one repair here.
  5. **Pins.** The equals form was **unpinned repo-wide** — the existing visual-flag pin exercises
     `--ascii --json` and nothing else — so §2.5's whole surface could have been implemented
     backwards and failed no test. §3 gains pins 30–33: the visual surface checked at the precedent
     *and* at its copies (including the bare-`--width` rejection), `--persist=DIR` asserted by exit
     code **and** log delta together (either alone passes on pre-fix code), preflight's empty
     allowance, and the over-strict-direction regression pin. §4's failure-mode list names
     `--persist=DIR` and bare `--width` explicitly.

  **Clean on this line of attack:** every live and documented `--evict` use is the equals form
  (`cm` documents `--evict=<fact>`; the parser accepts nothing else), so the asymmetry is benign in
  practice — no caller is silently mis-parsed. The R2 landing gate stays clear.

- **amend-6 (draft, 2026-09-14, the adversarial round's second report):** one BLOCKER and one MAJOR,
  both confirmed by independent re-measurement here, and both changing the *design* rather than the
  prose. One of them reverses an approved plan line — flagged to the maintainer and decided
  explicitly rather than absorbed.

  1. **BLOCKER — §2.4's scoping justification was false, and the hole it named is live.** The claim
     was that the exit-4 gate and the ⚠ panels "already share that block and therefore cannot
     desync". They do not: the panels render under `judged = persist_dir is not None`, the gates run
     in `main` under `if persist_dir:` — two tests that differ exactly when `persist_dir == ""` — and
     `main` returns **before either gate** on a `no-dir`/`io-error` persist status. Re-measured on a
     stamped 2/6-beat record: real dir → exit 4 **with** panel; missing dir → exit 0 **with the same
     panel**; `""` → exit 0 with the panel. So a path typo disables all three terminal gates while
     still displaying the violation. §2.4 now justifies the scoping on the true, narrower claim (the
     `--persist` render is the only surface that knows the record was just written) and points at the
     two usage errors that remove the desync conditions.
  2. **The residual becomes a refusal — reversing the plan's §5 line.** §1 had recorded
     `--persist <missing dir>` as the *loud* member of C5's family, on the strength of a diagnostic
     naming the path. That diagnostic is about the **log** and says nothing about the gates. The repo
     holds both postures for a typo'd directory: `distill_scan.py` warns and continues (right for a
     *scan target* — an empty scan claims nothing), `sync_global.py` refuses where a typo'd path
     would fabricate a store. A typo'd `--persist` is the second kind — the fabricated artifact is a
     *false clean*. **Decided: refuse, exit 2.** Put to the maintainer as an explicit three-way choice
     because it contradicts an approved plan line; §4 now lists it as the one item that changes the
     code of a call which previously exited cleanly. The other half of `_persist`'s failure surface,
     `io-error`, is **left open and named** in §5 (environment fault, not typo; refusing would risk a
     livelock on a degraded filesystem).
  3. **MAJOR — the new anchor was stricter than the regex it replaces, on seven forms.** The
     prototype's 16 cases were a match set, not a proof. Measured against the shipped `_INVOKE_RE`,
     `env`/`time`/`command`/`nohup`/`sudo`/`xargs -I{}` wrappers and `sleep 5 & python3 …` are all
     accounted today and were **all** made unaccounted by the first prototype — seven new exit-3
     fires on legitimate calls. Causes: the old prefix anchored on a bare `&` that the new separator
     list dropped, and the token walk stalled on a wrapper that is neither an assignment nor the
     interpreter. Fixed by restoring `&` at **token** granularity (so `2>&1` never splits) and adding
     a bounded wrapper set; all twelve measured forms now match the old verdicts, `echo` stays closed
     because it is not a wrapper, and the remaining residuals are all in the loud direction. §5
     records the list as bounded.
  4. **A pin that is deliberately exempt from the must-fail-on-pre-fix rule.** Pin 34 asserts the
     anchor's *inherited* verdicts — it is green before and after, by construction, because its
     content is that the fix must not change them. Labeled as such in §3 rather than left to look
     like a broken pin, since a suite of pins that only assert new behavior cannot catch an
     over-narrowing implementation, which is precisely the failure the first prototype had.

- **amend-7 (draft, 2026-09-14, the adversarial round's third report plus this pass's own sweep):**
  the largest fold of the cycle, and the one that adds the most new *measurement*. It corrects one
  claim this spec had made about its own pins, adds four pins, adds three named ceilings, and folds
  one live defect found in a surface the first sweep had omitted. One peer finding was **refuted**
  rather than folded.

  1. **The C4 justification was stated backwards, and the correction is the stronger claim.** §1
     said the existing path-split pin "passes because of this truncation, not in spite of it."
     Measured with a three-command `group(0)` table: the pin's own command is **not** truncated
     (the continuation falls in the *greedy tail*, which `_SEG*` absorbs), the hole's command **is**
     (its continuation falls in the *lazy prefix*'s reach and the regex stops at the backslash), and
     the `--recalls` pin is n/a because it contains no `--recalls`. The direction table replaces the
     sentence. **The counterfactual is what settles it**: delete the `\\\n` alternative from `_SEG`
     and `finditer` returns **zero** matches on the pin's command — the pin *fails*. So the pin
     passes **because of** the continuation support, and the first draft's sentence had the
     causality exactly inverted. A structural explanation (lazy prefix reachable by backtracking,
     greedy tail not) plus a measurement that flips the claim is the shape this cycle keeps
     producing: a plausible mechanism story that survives until someone deletes the mechanism.
  2. **§2.1's archive claim was right for one class and wrong for the other.** amend-3/amend-4
     concluded the archive is *stricter* than the gate, from `passage()`'s `typeof` guard. True —
     for the **non-string** class. For the **string** class it is the opposite: `unwrapped()` strips
     only a *matched pair* of delimiters, so `"*"` and `"***"` survive as a literal asterisk in the
     `dream-voice` class, and `"> "` becomes a **blank** voice paragraph. Measured by instrumenting
     `paragraph()` and logging every call: `"*"`→`("VOICE","*")`, `"***"`→`("VOICE","*")`,
     `"> "`→`("VOICE","")`, `""`/`"   "`/`null`→`("note","Passage 1: Not captured")`, `{}`/`0`→JSON.
     So "the archive already applies the rule §2.1 introduces" is now scoped to the class it was
     measured on, and the string class is a **named ceiling** in §5 — a beat that now fails the arc
     would still *display* as captured dream-voice.
  3. **The probe for (2) was wrong twice, and for the cycle's own reason.** `passage()` has **no
     return statement** — it appends to `arc` — so the first two probes returned `undefined` for
     *every* input, valid ones included, and measured nothing at all. Both were read as "the archive
     produces nothing," which is a finding-shaped result. This is the third instance of this cycle's
     thesis occurring inside the cycle's own instrumentation, which is why it is recorded rather than
     quietly fixed: a matcher that is not the rule it is believed to be.
  4. **"Correct by construction" was an over-claim; the correction is a measured table.** The fixed
     numerator is a count over slots **actually checked** — but membership is not **attribution**.
     `_gaps` asks `any(needle in n for n in norms)` over one pooled list, so measured through
     `judge`: seven distinct needles inside **one** block → `verified · 7/7 narrated`; six
     **identical** beats against one block reading `same` → same; three blocks covering seven slots
     → same. Not a false clean of §1's kind (a dense narration does narrate), but `N/N` reads like N
     separate mentions. §2.2's claim is scoped to membership and §5 carries the ceiling; requiring
     distinct blocks would be a **stronger** rule than the contract implements.
  5. **§2.3 gains a corpus measurement, which is a different instrument from the 14-form table.**
     908 JSONL session files, 390 commands mentioning the extractor, 56 accounted by the shipped
     anchor — and **15 of those 56 flip** to unaccounted under the fixed anchor. Every one of the 15
     is a **false account** (heredocs that *write* a script mentioning the token, and `echo` lines);
     **0** are genuine execution forms. The 14-form table is a *constructed-forms* measurement; this
     is a *corpus* measurement; the two are stated as separate claims rather than merged, because
     only the second can speak to what the fix costs in the wild.
  6. **The plan's second pattern source does not exist, and `sync_global.py` is not strict.** The
     plan cited a `sync_global.py` `--fleet`/`--tokens` refusal enforcing "a flag must never
     silently no-op on another mode". Measured, there is no such refusal: `--list --fleet=personal`,
     `--tokens --fleet=personal`, `--pull --tokens` and `--list`/`--tokens`/`--gc --jsoon .` all
     exit **0** with empty stderr, while `--jsoon .` (positional 0) exits 2. Its strictness is
     **positional-0 only**; the one real mode guard is `--evict`, which the paragraph never named
     and which protects a destructive swap rather than an unknown token. So §2.5 names one copyable
     precedent instead of two, and the unknown-flag class is **unclosed in a fifth entry point** —
     left unfixed (outside the decided scope) and **named in §5**, because a cycle that implies it
     closed a hole it did not touch is the defect class it exists to fix.
  7. **The equals-form rule is now stated once, generally.** A `--flag=value` token is an unknown
     flag **unless that exact flag is on the script's equals-form allowance**, which is per-script
     and enumerated (`sync_global.py`: `--evict=`, `--into=`; `_ui`'s global visual set: `--color=`,
     `--width=`). `render_dashboard.py`'s `--persist` is **not** on it. §2.5's own trap bullet
     invites an implementer to allow `=` broadly, so the rule needed to be a sentence rather than an
     inference from examples. The rejection diagnostic echoes the **whole token, path included**.
  8. **`--persist ""` is not a missing argument — it is a truthiness split, and it is the worst of
     the three.** The first draft had it as the mild sibling of the typo. Measured on a stamped,
     arc-incomplete record it exits **0** with the arc panel **rendering**, byte-identical to no
     flag: `judged = persist_dir is not None` is True for `""` so the render *claims to be judged*,
     while `if persist_dir:` is falsy so the entire print→persist→exit block — the 3/4/5 gates
     included — never runs. The precedent is *missing-token* (`--into` with no value → 2), not
     empty-value (`--into ""` → 0), and **`--persist ""` → 2 is deliberately stricter than its own
     precedent**, stated as such: the extractor's `--into` emptiness costs a file, `--persist`'s
     costs the gate.
  9. **A *relative* `--persist` is fatal today, and it is not the missing-dir case.** Measured with
     an isolated HOME on a directory that **exists**: `--persist memory` → exit **1** with a 15-line
     traceback ending `IdentifierRefused: invalid project id ''`; identical for `.` and `./memory`;
     the absolute spellings exit 0. Mechanism read at the source: `retention._ops_slot` keys a
     non-`memory` store dir by `native_store.parent.name`, which for a relative path is
     `Path(".").name == ''` (measured). **Folded in**: `os.path.abspath` at the flag, so the two
     spellings become one input and land on the same slot. This is the cycle's only change that
     makes a previously *fatal* call succeed, and §4 says so explicitly rather than listing it as
     one more refusal.
  10. **`-h`/`--help` are not an affordance on the five — measured, not one provides help.** Three of
      them exit **0** doing something else entirely: `extract_signals.py -h` runs a **full extraction
      of CWD**, `memory_status.py -h` a full status report, `preflight.py -h` a preflight with
      project dir `-h`; `render_dashboard.py -h` exits 1 with `cannot read cycle record: '…-h'`.
      Only `distill_scan.py` rejects both spellings **by flag**; `sync_global.py` returns the same
      exit 2 from its positional parser, which is a different mechanism that does not survive one
      position right (`--list -h .` → 0, measured). So the *copyable* precedent is one script, and
      rejecting is still the consistent choice for the same reason: this is the mis-slot defect as
      `--jsoon`, not an accidental-but-working feature. **`cm` keeps `-h`/`--help` → usage, exit 0**:
      it is a dispatcher with a real help arm, and pin 37 asserts both halves so the fix cannot
      reach into it.
  11. **`--` becomes an unknown flag, stated rather than discovered.** Measured:
      `render_dashboard.py -- /dev/null` → exit 1 with `'--'` read as a record path;
      `extract_signals.py -- .` → exit 0, swallowed. No caller in the repo passes it.
  12. **Three pin corrections, all from re-running rather than reading.** **Pin 1** asserted only
      the *count* (7); a `str()`-coercing `_checked_texts` also returns 7, so the pin passed on both
      the shipped and the coercing implementation — and the coercing one reports
      `verified · 7/7 narrated` on an all-numeric record against a transcript containing `0`. The
      pin now asserts the **values**. **Pin 19**'s exit-4 claim needs its **preconditions** to be
      part of the pin: without an accounting EXT call and a live session dir the fixture exits **0**
      as `degraded (transcript unavailable)`, which reads as the pin being broken when the *fixture*
      is what is wrong. **Pin 2**'s wording claimed a fact about set membership; the measurable fact
      is the **return type** (`None` vs `[]`) — `{"dream": {}}` yields `[]`, so nothing is "in" it.
  13. **Six in-scope pins cannot fail pre-fix, and are now labelled instead of left looking
      vacuous.** Pins **3, 6, 8, 9, 15, 20**, plus the survive-clauses inside **7, 12, 13**, assert
      that the fix must **not** move what already works — the same class as pin 34. Under a header
      that says every pin must fail on pre-fix code, an unlabelled green pin gets "fixed" by someone
      who thinks it is broken, and the over-narrowing direction is exactly what it catches.
  14. **A live defect in the site R2 had been omitting.** `commands/cm-connect.md` — the two-repo
      onboarding wizard, a surface a user pastes from — has **12 invocations and all 12 are
      malformed**: line 15 is balanced but is **one argument** (`python3: can't open file
      '…/preflight.py .'`, exit 2), and the other 11 have one `"` and no closing one. Of the file's
      four bash blocks, **2 fail `bash -n`** and the other 2 pass *only* because their quotes pair
      up across lines. It is a **quoting** defect, adjacent to Cycle A's charter rather than inside
      it; it lands here anyway, because R2's job is that no live invocation breaks and this is the
      one site already broken. Pin 40 must assert the **extracted argument count per invocation**,
      not the syntax check — a file whose every invocation is broken passes `bash -n`.
  15. **Four pins added (37–40)** covering the flag-**shape** boundary (`-h`/`--help`/`--`,
      measured pre-fix in three different wrong directions), the per-script allowance pinned by
      **cross-script rejection** (the one arm that catches a house-style list: `--demo` blessed off
      `render_dashboard`, `--audit` off `memory_status`, and the **git passthroughs**
      `--oneline`/`--no-merges`/`--exclude-standard`/`--is-inside-work-tree`/`--verify`, which are
      string literals *in the same files* and are not flags those scripts parse), the relative-`--persist`
      **slot identity** (a code-only assertion would pass a fix that catches the exception while
      leaving the two spellings on different slots — which is the actual defect), and the doc sweep.
  16. **One peer finding refuted, not folded.** A report listed as residues that §2.5 "presents bare
      `--width` as accepted" and that pins 30–33 "never exercise the equals forms". Neither holds in
      the current revision: §2.5 says *"five forms, two of them equals-only, and no bare
      `--width`"*, and pins 30/31/32/33 exercise `--color=always`, `--width=80` and `--persist=DIR`
      directly. The report reviewed a 962-line revision; the spec is past 1,100. Recorded because
      the correct disposition of a stale finding is to date it, not to re-fix what is already
      fixed — and because the same report **under**-reported the `cm-connect.md` defect (it found
      line 15; the defect repeats across all 12), which item 14 corrects.
  17. **Two ceilings named rather than fixed, and they are different in kind.** The archive's string
      class (item 2) is a **display** gap with **prospective** exposure — 0 of the 55 archived
      records have a beat normalizing to empty — and closing it means a third file with its own
      browser-check baseline. The attribution ceiling (item 4) is a **contract** boundary: the rule
      as written is about *which texts are checked*, and requiring distinct blocks would smuggle in
      a stronger rule as a bug fix. Both are stated with the measurement that bounds them.
  18. **The count in item 14 was itself an unmeasured number, and the fix caught it.** The spec said
      **13** invocations in four places. Counted, the file has **12** — re-measured three ways
      (block-by-block line count, per-line quote count, and `bash -n` per block: blocks **1 and 3**
      fail rc 2, blocks **2 and 4** pass only because their quotes pair across lines). The 13 came
      from generalizing one measured line to a file-wide claim, which is precisely the defect class
      this cycle exists to fix, occurring in the sentence describing the fix. Recorded rather than
      silently corrected: a spec whose thesis is "numbers are measurements, not recollections" does
      not get to carry a recollection, and the corrected row now names *which* blocks fail instead
      of only how many.

- **amend-8 (draft, 2026-09-14, from *fixing* amend-7's finding):** one scope expansion and one rule
  change, both discovered by repair rather than by review. This is the largest single change to
  Cycle A's size, and the only one the approved plan did not size at all.

  1. **SCOPE — the defect is 9 files, not 1, and 61 of 77 command lines, not 12.** amend-7 item 14
     recorded `cm-connect.md`. Repairing it meant running `bash -n` on the *family*, which found the
     same class A in all 8 `commands/*.md` and class B in `cm-group.md` and 6 blocks of `SKILL.md`.
     Measured from `git show HEAD:` — 47 class-A lines, 28 class-B lines, 14 overlapping, **61
     malformed, 16 clean** (all in `SKILL.md`). Every command line in the user-facing `commands/`
     surface is malformed. **Folded**, on the spec's own reasoning: one defect class, one mechanical
     fix confined to bash blocks, one pin, and R2's charter — *"no live invocation breaks"* — cannot
     be met while the runbook and the entire command surface are broken. The plan sized Cycle A
     without `commands/*.md` at all; the sweep added one file; the repair found nine. Flagged to the
     maintainer in the fold report as the one item that grew.
  2. **A rule the pin had wrong, caught by the pin's own first draft failing correct code.** Pin 40's
     placeholder arm was written as *"no `<`/`>` in the line"*, which flags `SKILL.md`'s
     **genuine** `distill_scan.py … --json > "<the --scan path>"` — an output redirect, correctly
     written. The rule is *"a `<…>` placeholder is quoted"*, and it is now measured **both ways**
     before adoption: the genuine redirect is not flagged, `--pull <other-repo>` is. This is exactly
     the over-strict direction pins 33/34 exist for, occurring in a pin written to catch the
     *under*-strict direction.
  3. **Pin 40 grew a third arm, and it is a regression arm.** Arms 1 (`bash -n`) and 2 (unquoted
     placeholder) alone would pass a doc that names a flag its script does not have. Arm 3 checks
     each line's flags against its script. It is **green pre-fix** — all 77 lines' flags are defined
     today, measured per line — so it is labelled with pins 3/6/8/9/15/20/34 as a *regression* arm
     rather than left to look like a pin that never fires. *(Superseded by `amend-10` items 2 and 6:
     the source scrape F2 named was replaced, backslash continuations moved the subject from 35 to
     45 pairs, and under the differential arm 3 is RED pre-fix. Left as the amend-8 record.)*
  4. **Two instrumentation errors, both the cycle's own thesis, both caught by contradiction rather
     than by inspection.** (a) The first census script reported `SKILL.md` as class-B = **0**, which
     contradicts the repair script that had just changed **20** placeholders in the same file; the
     corrected script reports **14 lines**. I did not establish why the first was wrong and am not
     recording a cause I did not verify — what is recorded is that the *number* was re-derived
     twice, agreed the second time, and was independently confirmed a third way
     (`HIT.findall` on the raw line, and `grep`). A measurement that disagrees with a measurement is
     the only reason either was questioned. (b) The same script's first version reported the
     pre-fix total as **62**; the corrected run gives **61** — and the 62 was written into §2.5
     before it was checked, i.e. the spec briefly carried an unmeasured number in the very paragraph
     describing a repair for unmeasured numbers. Both are the fourth and fifth instances of a
     matcher that is not the rule it is believed to be, and the first two that occurred inside the
     **measurement of a doc fix** rather than inside the product.
  5. **What is *not* claimed.** The repair fixes the **spelling** of the documented invocations; it
     does not audit whether each command's *semantics* are right, and it changes no script. The
     existing `tests/smoke.py` suite and `tests/docs_links.py` are both green after the edit
     (measured, not assumed), which is the check that the doc change did not disturb the
     SKILL↔TypedDict pin.
  6. **Three existing pins were passing *because* they pinned the defect — the sharpest instance of
     this cycle's thesis, found inside the cycle's own repair.** The doc repair failed smoke on
     exactly three checks, and all three failed by asserting the **raw broken spelling**:

     | pin | asserted | why it is a defect |
     | --- | --- | --- |
     | `SKILL Phase 5 … native_memory_dir` | `"--persist <native_memory_dir from Phase 0 / cm doctor>" in _p5_ac` | the literal it requires is the **redirect** shape — the pin cannot pass unless the doc is unrunnable |
     | `cm-connect sequences positional-first enrolls` | `"project enroll <other-repo> …" in _conn_bq` | same: bare `<other-repo>` is the broken form |
     | `/cm-group … confirm-phrase surface` | `"create-group-<name>" in _ctg_gs` (×4) | the phrase is split by the new quoting, and the assertion was written against the unquoted text |

     Each pin's **intent** is sound and is preserved — assert *where the path comes from*, assert
     the positional-first enroll shape, assert the four confirm phrases. What was wrong is that each
     made a **semantic** claim (*the doc says X*) with a **literal** instrument that happened to
     encode the defect. Repaired by quote-normalizing the haystack (`.replace('"', "")`) rather than
     by re-typing the literal, so a future quoting convention cannot re-break them — and so a *third*
     spelling cannot be pinned by accident. Note the direction: these pins did not fail to catch a
     bug, they **required** one. This is the repo's own `gate-coverage-is-its-match-set` law one
     level up: a pin proves what its matcher can see, and here the matcher could only see the
     broken form.
  7. **Suite state after the repair, measured.** `tests/smoke.py`: **1795 passed, 0 failed**, rc 0 —
     the same total as before, since three checks were re-spelled rather than added (the v0.4.21 D6
     surface constant is unchanged and still equals the reported count). `tests/docs_links.py`:
     green. Both re-run after the last edit, not before it.

- **amend-9 (draft, 2026-09-14, written by the implementation pass — every item is a thing the
  spec asserted that MEASURING the pins falsified):** eleven items. Six are pin-level corrections
  (1, 2, 3, 5, 6, 8), one is a record of a design decision rather than a correction (7: two pins
  add no check), one is a code defect the pins found (4), and three are measurements the cycle's
  own landing gates required (9: R2's invocation census, 10: the suite census constant, 11: §4's
  mutation matrix). The pattern worth
  naming: every one of them was found by *running the pin against both trees*, which is the only
  instrument that can tell a regression pin from a mislabelled one — and two of the six were
  **self-contradictions inside this spec** (§3's pin table disagreeing with §2.3's own
  measurement).

  1. **Pin 26's stated content is green on BOTH trees, so as written it was not a mutation pin.**
     It reads *"assert `judge` on `dream: {}` never reaches the transcript"*. Measured: the pre-fix
     `if not checked:` is a **truthiness** test, so `[]` returned early there too — it simply
     returned `verified` instead of `failed`. The pin now carries the verdict half as well
     (`failed` + the empty-block reason, with the no-scan half kept as the shape assertion). Both
     halves are load-bearing in different directions: the verdict half fails pre-fix, and the
     no-scan half catches a C6 rewrite that deletes the early return and lets the empty block reach
     `missing == [] and accounted`.

  2. **Pin 34's `echo` clause FLIPS, so it is not a regression clause.** §3 listed
     `echo python3 <tok> --json` under pin 34 as *"must stay unaccounted"* on both sides. Measured
     on the pre-fix tree: it is **accounted** — the shipped `_INVOKE_RE` anchors on
     `(?:^|[\s;&|])`, so any whitespace before the interpreter matches. It is one of the four C4
     *holes*, and §2.3 of this same spec says so in as many words (*"Rejecting any whitespace before
     the interpreter is what kills `echo python3 …`"*, and the corpus section counts it among the
     false accounts the new anchor correctly rejects). §3's table therefore contradicted §2.3.
     The clause is now pin 7's first case; pin 34 is the ten wrapper/operator forms, all measured
     accounted on both trees (10/10).

  3. **Pin 3's fourth case asserted a value the function does not return.** `normalize_beat_text`
     was pinned with `" > * *"` → `""`; measured it returns `"> *"` — the `> ` strip only fires on a
     line that *starts* with it, and the leading space defeats that. Dropped rather than repaired:
     the spec's claim is about the markers-only forms (`"*"`, `"***"`, `"> "`), all three of which
     measure `""`.

  4. **`_VISUAL_FLAGS` was a NameError in the shipped edit — found by a pin, on a path no other pin
     exercised.** `render_dashboard`'s new strict loop referenced a module constant that did not
     exist in that file, so *every* `--color`/`--ascii`/`--no-color` run of the script died with a
     `NameError`. Latent by construction: no pre-existing pin ever passed a visual flag to
     `render_dashboard`. Fixed, and pinned by 33 — which is the argument for 33 existing, recorded
     here as evidence rather than as a prediction.

  5. **Pin 13's render clause asserted the wrong surface.** It read *"the render panel keeps the
     default … so no archived record's display retro-flips"* and, in the first draft of the pin,
     was written against the `DREAM ARC` ✓/✗ display line. That line cannot observe the flag at all
     — it only renders for records that *have* a `dream` block, and the flag's arm only fires for
     records that do not. The observable difference is the `judged` **gate**: `render(record,
     judged=False)` for the skipped-arc record renders no panel, `judged=True` renders the strict
     one. The pin now asserts that pair, which is the scoping itself rather than a proxy for it, and
     fails pre-fix on the second half (pre-fix both are panel-free).

  6. **Pin 40's census and the pin's arms are different numbers, and only one of them is checkable
     at runtime.** §3 says *"arms 1–2 fail on 61 of 77 lines across 9 files"*. That 61 is the
     **union** of the two classes over the line census (class A ∪ class B, 47 + 28 − 14). The pin's
     arms count **per-arm**, over blocks *and* lines: arm 1 is red on **15 blocks and 56 command
     lines**, arm 2 on **28 lines**. Both figures are correct and they are not interchangeable — the
     61 belongs to the census table, the 15/56/28 belong to the pin. Written down because the two
     would otherwise be "reconciled" by someone adjusting whichever number they met second.

  7. **Two pins add no check, by design, and this is the record of it.** Pin 6 (pin 2's existing
     cases) and pin 20 (the exit ladder) are discharged by checks that already exist: the v0.4.19
     F19A/B/C/K subprocess pins and the v0.4.1 arc block. Pin 20's exit-ladder claim in particular
     is asserted across four existing pins, so adding a fifth would be a copy, not a pin.

  8. **Pins 6, 15, 20, 29, 34 and 40-arm-3 join 3/8/9 on the regression list, and the labels are
     the deliverable.** Two of them (26's no-scan half, 40 arm 3) were added in this pass; two
     (29, 34) were measured green pre-fix and labelled rather than left looking vacuous. The rule
     the label encodes: a regression pin's whole content is that the fix must not move what worked,
     so it can never satisfy "fails on pre-fix code" — a reader who applies that rule to it will
     "fix" the pin instead of the bug, which is the failure mode `amend-8` item 6 found three live
     instances of.

  9. **R2's invocation census — the cycle's named landing gate — is measured GREEN, and the
     instrument took three iterations to become trustworthy.** The gate asks whether any *live*
     caller passes a flag its script does not define. Recorded over the whole repo: **71 call
     sites** (11 to `extract_signals`, 9 to `memory_status`, 1 to `render_dashboard`, 2 to
     `distill_scan`, 22 to `sync_global`, 26 to `cm_ops`, 0 to the rest), every flag defined by
     its own script's parser. Two caveats, recorded rather than tidied: the total previously read
     **72**, which is not the sum of its own addends (they are 71 — a `number-provenance` slip
     inside the ledger that exists to catch them), and **the per-script figures are testimony, not
     a derivation** — re-implementing the two stated rules from this paragraph (the script token
     follows `python3`; argv cut at the first shell metacharacter) yields **133** invocations, not
     71, so the prose does not determine the instrument. The gate's *verdict* — "every flag
     defined by its own parser" — is what the cycle landed on and is unaffected; the count is a
     property of a matcher this paragraph does not pin. `hooks/hooks.json` passes none; CI runs only `tests/` plus
     `bench_phase5.py --quick --json` (not a strict script); `cm`'s arms forward `"$@"`, which is
     *user* argv, not a caller's flag. **The first draft of the census reported 9 scripts RED and
     all nine findings were artifacts** — it matched any `--flag` sharing a line with a script
     name, so a spec table reading *"`extract_signals.py --jsoon` → exit 2"* (a line that
     documents a REJECTION) became evidence that the flag was in use. Two rules fixed the match
     set, not the code: an invocation is a line where the script token follows `python3`, and only
     the script's OWN argv counts (cut at the first shell metacharacter). Recorded because this is
     `gate-coverage-is-its-match-set` reproduced on a *new* instrument inside the cycle that cites
     it — the census's 9 findings were as wrong as the gates the cycle exists to fix.
 10. **The suite census constant, and what it does NOT claim.** `tests/smoke.py`'s D6 self-count
     moves `1750 + 45` → `1750 + 45 + 93`: **1888 passed, 0 failed** on the fixed tree, measured
     after the constant was bumped (the constant equals the *reported* total, because
     `passed + failed + 1` is the pre-`check()` running count plus this pin itself). 93 is the
     number of checks this cycle ADDS; it is not the number of pins, because pins 6 and 20 add no
     check by design (item 7) and three existing checks were re-spelled rather than added
     (`amend-8` item 6). `amend-8` item 7's "1795 passed" is a historical record of the suite
     *before* this pass's pins existed, and is left exactly as written for that reason.
     *(`amend-10` carries the constant forward twice more: `+ 113` at the F2/F14 closure, then
     `+ 117` after pin 42 — **1912 passed, 0 failed** on the frozen revision. 93, 113 and 117 are
     three measurements of a growing quantity, each true of its own revision, and none of them is
     the current one except the last; the `117` is verified as `v0.4.29`-labelled check count
     directly, so the constant's last term is not merely "whatever makes the arithmetic work".)*
 11. **The mutation matrix found the HARNESS, not the product — three aborts, and then a wrong
     measurement.** This is §4's "every pin verified to fail on pre-fix code" step failing at its
     own job, so it is recorded rather than absorbed:
     - the suite ABORTED with `FileNotFoundError` at the `_st16.write_text` that follows the
       beacon's cached-FAIL check — a bare write into the store dir that **check** creates, so an
       expected RED became a crashed RUN and the matrix could not be collected at all (~90% in)
       and **before any v0.4.29 pin**, so the first matrix collected nothing. The check above it
       (`preflight subprocess: the floor env still CACHED the verdict`) asserts a file that the
       tested BEHAVIOR writes — so on pre-fix code that check goes correctly RED, the state dir is
       never created, and the next check's bare `write_text` then died on the missing parent. An
       expected RED became a crashed RUN. Fixed with `mkdir(parents=True, exist_ok=True)` guarded
       by the rule the fix encodes: *a check must never assume its predecessor passed.* A no-op on
       the green tree, so the census is unchanged and the red is preserved — now reportable.
     - the second abort was `AttributeError: module 'memory_status' has no attribute
       'stanza_present'` at the §2.1 pin. `stanza_present` does not exist pre-fix, and that pin's
       claim is precisely that the symbol exists as the shared type rule — so absence is a RED,
       never a crash. `_sp29 = getattr(ms, "stanza_present", None)` and the assertion now leads
       with `_sp29 is not None`.
     - the third was `TypeError: arc_completeness() got an unexpected keyword argument
       'enforce_post_arc'` at the §2.4 pin. This is the same class with a different signature: the
       §2.1 pin referenced a symbol that is **absent** pre-fix, the §2.4 pin a **new keyword on a
       function that exists**. Both abort the run where the pin owed a RED. It is closed by a
       signature probe, not a `try`/`except` — `_ARC29_STRICT = "enforce_post_arc" in
       inspect.signature(ms.arc_completeness).parameters`, with `_arc29()` returning
       `(None, "arc_completeness has no enforce_post_arc parameter")` when the parameter is
       missing. The distinction matters: a `try`/`except` would swallow a genuine fault inside the
       gate under test and convert it into the same RED as a pre-fix absence. **The general rule:
       a pin that asserts on post-fix API must PROBE that API, because the mutation matrix requires
       the pin to fail rather than crash.**
     - **The class was then audited rather than patched ad hoc, and no other instance exists.**
       The suite has no per-check exception isolation, so any unguarded reference to a post-fix
       symbol aborts a mutation run. Every other symbol the new pins touch — `judge`,
       `_checked_texts`, `normalize_beat_text`, `render`, `_narration_session_dir` — has a
       byte-identical signature on both trees (compared directly against `git show HEAD:`), and
       pins 19/27/39 do read `_last19()["narration"][…]`, which would `KeyError` or `IndexError` on
       a pre-fix log — but each leads with an exit-code clause that is already False pre-fix, and
       `and` short-circuits, so the subscript is never evaluated. That reasoning is why 19/27/39
       needed no guard; the next pin added in that shape will need the same check.
     - **The run that finally completed then measured the wrong thing.** With the aborts closed the
       suite finished and reported **59** failures, but only 53 were pins: 6 sat in the
       preflight-beacon region, which this cycle does not touch. The cause is a property of the
       mutation tree, not of the code under test — `git worktree add` creates a *linked* worktree,
       whose `.git` is a file naming `…/.git/worktrees/<name>`, and
       `store_context._common_from_gitdir` follows `commondir` back to the **main** worktree, by
       design: a linked worktree *is* the same project. So inside the mutation tree the product
       resolved the project identity to the original repo's path while the suite pinned state under
       `slug_for(ROOT)`, and six checks that write a state file into a hermetic `HOME` and assert
       the beacon's silence failed on that identity mismatch. Proved environmental rather than
       mutational by running the **fixed** tree's `preflight.py` with `cwd=/tmp/mut-tree`: it writes
       to the **main worktree's** slug too. The harness now clones rather than links
       (own real `.git`, no `commondir`) and asserts the two identities agree before the run, which
       is what makes §4's `1835 + 53 = 1888` with **0** non-`v0.4.29` failures a measurement rather
       than a coincidence.
     - **Why this belongs in a spec about teeth.** It is the cycle's own subject reproduced three
       times over in the instrument built to detect it: a gate narrower than the rule it is
       believed to enforce, failing in the quiet direction — "the suite ran" reading as "the suite
       verified" (twice, as a crash), and "the suite failed" reading as "the pin fired" (once, as a
       red baseline that could not attribute its own failures). Item 10's census is the *only*
       thing that would ever have caught a truncated run, and it sits at the file's last line,
       after everything that could truncate it.

**Added in amend-8 (the fold after the third adversarial round — the second `/code-review` pass).**

Four findings landed after amend-7, all in the same class: a gate narrower than the rule it is
believed to enforce, each failing in the **clean** direction. Every one is corrected above, and the
evidence for each is re-derived rather than carried.

| finding | what was measured | what changed |
| --- | --- | --- |
| **F4** — `_POST_ARC_KEYS` was narrower than its own stated criterion | the criterion admits **7** keys introduced strictly after v0.1.54; the tuple named **2**. The first cut even excluded `distill` (v0.1.58), a key *older* than the `usage` (v0.1.63) it already trusted — self-contradicting, not merely narrow | the tuple widened to 7, each key dated by `git log -S` + first containing tag (never CHANGELOG prose, which dates `demotion` to v0.1.8 — eleven releases early). Measured **inert** on both real populations: 0 newly firing across the 55-cycle archive and across 69 records / 44 dreamless in 11 store logs. `audit` (v0.1.53) and `outcome` (v0.1.1) stay out, and they are load-bearing exclusions — 9 of the archive's 17 dreamless records carry one |
| **F5** — the execution anchor's walk had no grammar | **12** legitimate Phase-2 forms were refused: four unlisted wrappers, their positional operands, their value flags, a `(`-fused subshell, a `then`-led and a `do`-led segment, a `{ …; }` group, an apostrophe in a `#` comment, a Windows drive path | `_WRAPPER_GRAMMAR` (flags-before-positionals, with each wrapper's value-consuming flags), `_PREFIX_TOKENS` + `_lead` for the fused spelling, `_strip_comments`, and a drive-path normalize in `_unfold`. 13 pins, all RED on pre-fix code |
| **F8** — the anchor's ONE silent hole, and the direction claim it contradicted | a heredoc **body** holding a complete command was segmented and **credited** — a pass that only *wrote* the command into a file passed the arm whose job is to prove it ran. The same comment block called the loud direction "the worse of the two"; the spec's own tie-break (*Uncertain → fire*) and its own words (*"a false clean is permanent and invisible"*) say the opposite | `_strip_heredocs` imported from `distill_scan` (verified import-safe; cross-script imports are the established pattern) and applied before segmentation; the direction paragraph corrected at the constant, in §2.3, and in the commit message |
| **F2 + F14** — a pin that scraped source text where pin 38 does not | pin 40 arm 3 read `--flag` literals out of **source text**, so a flag mentioned in a comment counted as defined; harmless **only** while no script had a dead flag, which is luck, not a contract — and pin 38 in the same file asserts the opposite rule | the scrape is **closed in amend-10**, and closing it took three more oracles — the replacement reintroduced the same class twice (a token-masking collision, then an in-scope test whose condition could never be satisfied). **F14 — five hand-maintained flag allowlists — remains OPEN**, and amend-10 says why the arm-3 work did not close it |

**Added in amend-10 (the F2/F14 closure — arm 3's third oracle, and the fourth time this cycle's
own defect class appeared inside the instrument built to detect it).**

F2 said arm 3's oracle was a source scrape. Replacing it took **three more oracles**, each narrower
than the claim it carried, and the last one's *soundness test* certified a property that is neither
necessary nor sufficient. Every number below is re-derived on the final harness; the counts moved,
which is why the triple's rule exists.

| | oracle | what it actually answered | how it failed |
| --- | --- | --- | --- |
| 1 | `_docflags29` — every `"--flag"` literal in the script's source | "does this string appear in this file" | a flag named only in a comment or an error string read as defined (F2). Correct by luck: measured **0** comment-only flags, so the hole was latent, not absent |
| 2 | `"unknown flag" in stderr` | "did this one particular string appear" | fires on the five custom strict parsers and **nothing else**. Measured: `cm_ops`, `sync_global`, `dashboard_browser`, `dashboard_fixture` never emit it, so **25 of 35** pairs were silently blessed — F2 recurring inside its own fix |
| 3 | the exit code alone | "did it exit 2" | a **defined** flag that takes a value exits 2 when passed without one. Measured over the 35 pairs: **20 of 35** defined flags exit 2 alone |
| 4 | the mutation differential — `script --f` vs `script --fx`, every flag-shaped token collapsed to `«F»` | *see below* | bounds its own reach at `_ARM3_OUT29` |

1. **The collapse is load-bearing, and the first cut of it was wrong.** Without collapsing, `unknown
   flag: --persist` and `unknown flag: --persistx` differ — which reads as *recognition* and blesses
   every undefined flag. The first cut masked only the probed token, so masking `--gc` also masked it
   inside a static usage banner that *lists the legal flags*; `--gc` and `--gcx` then looked
   distinguishable for a reason that had nothing to do with either flag. Masking every flag-shaped
   token fixes it: a banner naming the same legal flags in both runs collapses to the same string and
   cancels.

2. **Arm 3 was blind to every flag past a line wrap.** It tokenized per **physical** line, so `_py40`
   was `None` on a continuation line and every flag following a trailing `\` was skipped — including
   `--persist`, the skill's most load-bearing flag, plus `--seed` / `--before` / `--diffs` /
   `--stamp-marker` / `--standing-justify-tokens` / `--from` / `--into` / `--verdict` / `--latest` /
   `--store`. Assembling backslash continuations before tokenizing moves the subject from **35 to 45**
   distinct (script, flag) pairs. Arm 1 is line-scoped too, but the wrap does not hide anything from
   it: `bash -n` returns 0 for a trailing-backslash line *and* for a lone `--persist "x"` line, so its
   per-line check is nearly vacuous on continuations while remaining correct — a blind spot that
   cannot produce a false clean.

3. **Naming the token is neither necessary nor sufficient for the oracle to be sound**, and this is
   the finding that killed the test written to certify it. Measured on the two carve-out scripts:
   - `cm_ops.py` **does** name it — `cm_ops: error: unrecognized arguments: --domain`, identically
     for `--domain` and `--domainx` after the collapse — and is unsound anyway, because `--domain` is
     defined on the `project` **subparser** and a lone flag never reaches that table. All **9** of its
     documented pairs read as undefined. *So the differential is sound on a script that names nothing
     and unsound on a script that names everything.*
   - `sync_global.py` names nothing and is sound on **10 of its 14** pairs; the other **4**
     (`--apply`, `--into`, `--json`, `--registrar`) are false-REDs.

   The property that actually matters is not whether the refusal *text* mentions the token but whether
   it encodes *why* the parser refused. Neither script's does: `sync_global` answers every rejection
   with one constant **412-byte** banner, so a false-RED and a hard-RED are the same bytes. That is
   the measured justification for the script-level carve-out, and it replaces a claim that had been
   asserted in the label without being checked.

4. **The test written to police the oracle could not be satisfied, and then certified the wrong
   property.** The first cut read `_CANON29 in "".join(_sig29(script, _CANON29)[1:])` — searching
   output that `_sig29` had already collapsed, which rewrites the canonical token itself. Its
   condition is unreachable by construction, and it reported all **7** judged scripts as unsound.
   Repaired to read raw output it would have passed — while blessing `cm_ops`, which item 3 measures
   as unsound. Both halves are the cycle's own thesis: **a guard's label is not its predicate**, and a
   test that fires on the wrong thing is indistinguishable from a test that works until you check
   what it measured.

5. **The carve-out cannot be derived from the tree under test.** The tempting replacement — carve out
   any script whose own usage contradicts the oracle — is not available, and the reason generalizes:
   **a pin's control must be invariant under the mutation it detects.** On pre-fix code the five lax
   parsers reject *nothing*, so the differential already answers "undefined" for every token
   **including the ones their own banners declare**; a measured carve-out would therefore grow until
   it had swallowed precisely the RED this arm exists to report. The set is static for the same reason
   the census constant is. What *is* measured is the carve-out's **justification**: each carve-out
   names a **witness** — a token its own usage prints as accepted which the lone oracle calls
   undefined — so repairing either parser turns the witness green and the check RED, and the only way
   back is to delete the carve-out and let arm 3 judge the script. Verified by construction: swapping
   `cm_ops`'s witness to `--help`, which it *does* recognize, fires the check with `carve-out is
   stale`.

6. **Arm 3's character changed, so its label did** — and the label's first cut then claimed a *class*
   that measurement refutes. It was recorded in amend-8 as *"green pre-fix"*, under the then-current
   oracle; under the differential it is **RED pre-fix**. The first cut of the label said why: *"the
   lax parsers enforced no surface at all, so they answered a flag and its mutated twin identically."*
   That is true of two of them and **false of `render_dashboard`**, whose pre-fix parser already
   refused `--persist` with `requires a directory argument` while reading `--persistx` as a record
   path — two different answers, so the differential called the flag defined.

   Measured per pair, the whole pre-fix effect is **5 of the judged pairs**, all on the two parsers
   that genuinely consumed nothing: `--before` · `--into` · `--standing-justify-tokens` on
   `memory_status`, and `--before` · `--into` on `extract_signals`. **0** pairs read as undefined on
   both trees, so the arm is not vacuously green on the fixed one. That attribution is also what the
   mutation matrix independently shows: arm 3 is RED in the `extract_signals` and `arc_ms_rd`
   clusters and GREEN in the `render_dashboard` and `preflight` ones — which looked like a gap in the
   arm until the per-pair measurement explained it as the *pin working correctly*.

   The label now carries the measured attribution instead of the class claim, and the arm is still
   labelled RED pre-fix. Item 8 of amend-9's rule applies to the arms that earned it; this one no
   longer does. (This is the third time in this cycle that a claim written as prose in a label — as
   opposed to one asserted by the check's own predicate — turned out to be narrower than the class
   it named. Hence the correction, rather than leaving a true pin wearing a false explanation.)

7. **The probes were writing to the live store.** One arm-3 sweep appended a row to the real
   `<plugin-data>/ops/-tmp/.mutation-log.jsonl` and bumped `control.sqlite`'s WAL, because the probe
   ran with `cwd="/tmp"` and the ambient `HOME`. Worse, a draft of the docstring *claimed* isolation
   the code did not implement. The environment is now the resolvers' own inputs rather than a guess at
   them — `HOME` (`_home_dir`), `CLAUDE_CONFIG_DIR` (`config_root`), `CLAUDE_PLUGIN_DATA`
   (`plugin_data_dir`), `CM_STORE_OVERRIDE`, `CM_DOMAIN`, with `CLAUDE_CODE_SETTINGS` popped — and the
   throwaway root doubles as cwd. Cost, measured: every probe ≤ **0.14 s** (a refused argument fails
   before any work, so no Chromium is ever launched).

8. **Arm 3's reach is now stated rather than implied**: **45** distinct (script, flag) pairs across
   **9** scripts; **23** carved out by name (`cm_ops.py` 9, `sync_global.py` 14); **22 judged across 7
   scripts** — `dashboard_browser`, `dashboard_fixture`, `distill_scan`, `extract_signals`,
   `memory_status`, `render_dashboard`, `render_html`. Four documented scripts (`tests/smoke.py`,
   `simulate_accumulation.py`, `validate_manifests.py`, `preflight.py`) are invoked with **no flags at
   all** and so never enter the judged set — a script joins it only by contributing a flag pair, which
   also keeps the suite from probing its own path and re-running itself inside itself.

9. **F14 stays open, and deliberately.** The five hand-maintained flag allowlists are a real
   duplication (`_KNOWN_FLAGS` in `memory_status` consults its parser directly and cannot drift;
   `extract_signals`' `_VISUAL_FLAGS` if/elif chain can). Collapsing them into one shared helper in
   `_ui.py` is a **refactor of shipped parsers**, not a gate fix, and this cycle's mandate is that
   each gate mean what it claims. It is recorded as open rather than folded in at the close, where it
   would ship unmeasured.

10. **The arm-3 helpers were added under a name that already meant something else.** `tests/smoke.py`
    already had a `_run29` — the pin-30/37/38 runner, returning `(stdout, stderr, rc)` and taking a
    script **name**; the new probe helper took a `Path` and returned `(rc, stdout, stderr)`, the
    opposite order, under the same name in the same module scope. Nothing failed, because every
    earlier call executes before the second definition is reached, so the name silently means two
    things and which one you get depends on *where in the file you call from*. A reordering edit
    would have swapped the tuples at ~40 call sites with no test between them and the failure. Renamed
    `_proberun29`. Found by checking for collisions rather than by anything failing — which is the
    point: this class is invisible until someone moves a line, and the cycle's own instrument had two
    live instances of it.

11. **Three more findings closed, two deferred, and one now measured as already closed.** The
    deferrals from the review rounds are dispositioned rather than left implied:
    - **Closed — F6, the SKILL's stale gate contract.** `SKILL.md` still described the dream-arc gate
      as *"sleep or wake empty, or ≠ 6 beats"* and asserted *"a missing block escapes the gate by
      design (the beta WARN covers it next pass)"*. Both halves were falsified by this cycle: a
      non-string or blank **beat** now fails the arc, and a dreamless record carrying a post-v0.1.54
      key now fails it at `--persist`. The prose is corrected to the shipped rule, including the
      7-key `_POST_ARC_KEYS` list — which was itself first written from memory of amend-8's prose and
      corrected against the constant, the same *"read it, don't recall it"* rule as item 10.
    - **Closed — F9, `--demo --persist DIR`.** Measured pre-fix: **rc 0, 0 files persisted, 0 bytes
      of stderr**. `--demo` builds its record in-process, so its short-circuit returned before the
      print→persist→exit block and all three gates were skipped — the false-clean shape, on the one
      flag no visual-flag list names. It is now exit **2** naming the conflict, pinned by 42, with its
      second clause pinning that `--demo` alone is still a clean preview (a regression clause:
      green on both trees).
    - **Closed as a doc correction — F11.** `_persist`'s `"no-dir"` return is unreachable from
      `main`, which refuses a missing `--persist` dir at exit 2 first, and the **only** direct caller
      in the tests pre-creates its dir. No pin covers it. It is kept as the guard for a dir that
      vanishes between the two checks, and the docstring now says exactly that. The first draft of
      that docstring claimed a test exercised it; it did not, and the claim was removed rather than
      left standing — a documentation fix is still a claim, and this one was checked.
    - **Already closed — F10 and F12.** `dream_procedure` guards a non-dict `dream` (the empty *list*
      is read apart from the absent block, deliberate and recorded at the constant), and
      `beta_checks` now prefers `memory_status.stanza_present` when it exists and falls back to a
      local copy when it does not.
    - **Which is why the mutation matrix shows `beta_checks` moving ZERO checks** — measured on the
      frozen revision, `1912 passed, 0 failed`, identical to the baseline — and the explanation is
      the change's *shape*, not a second defect: it is a **compatibility shim**. On the fixed tree
      `hasattr(_ms, "stanza_present")` is True, so reverting `beta_checks` alone leaves the oracle
      reading the same symbol from the same place and nothing moves.

      Its effect can appear only where that symbol is **absent**, and the matrix does reach that
      state, by a cluster named for a different reason: `arc_ms_rd` reverts `memory_status` (and
      `render_dashboard`, for coherence) while leaving `beta_checks` FIXED, so the oracle takes its
      `_stanza_present_local` fallback — verified, pre-fix `memory_status.py` defines
      `stanza_present` **0** times against the fixed tree's 1. The first draft of this entry named
      `prefix_pre_fix` as the covering cluster, which is wrong in the direction that matters: that
      cluster reverts `beta_checks` while keeping `memory_status` fixed, so it exercises the
      *preferred* branch with a pre-fix oracle — the one combination that cannot reach the fallback.
      A change no single-file mutation can move is not dead code; it is a change whose subject is a
      *pair*, and the matrix has to be read at the granularity of the mutation, not the file.

**Why the corpus needed a second, different measurement.** Amend-7 compared the shipped **regex**
against the first anchor cut and reported 15 flips. That answers *"is replacing the regex right?"*
It does **not** answer *"is the anchor's walk right?"* — a different pair of subjects. Amend-8 ran
both comparisons separately: regex → final (503 rows, 95 → 46, **49 flips, 0 the other way**) and
first cut → final (**0 flips**). The second is the one that makes the 12 F5 forms **latent** rather
than observed, which is what §2.3 now says and what the first draft got wrong by asserting the corpus
as corroboration for a claim the corpus cannot see.

**The one number that changed meaning under scrutiny.** Amend-7's row said "all 15 are false
accounts". Amend-8, classifying all 49 by hand, found **3** that are not: shell-*function*-mediated
calls (`probe … python3 $S/extract_signals.py …`, where `probe(){ … "$@"; }` runs it). Each was
re-checked for a *direct* interpreter-led extractor segment — **zero found in all four commands** —
so the anchor's verdict is *Uncertain → fire* working as contracted, not a false fire and not a
regression. It is now §5's shell-function ceiling. The correction is recorded here rather than
quietly folded in because the original claim was stronger than its evidence: "all 15" was a
classification of 15 rows by pattern, and 3 of them were never opened.
