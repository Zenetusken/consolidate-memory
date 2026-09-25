# Refusal/verdict parity — design-of-record

**Status: SHIPPED (vv0.4.37)** — verified against `CHANGELOG.md` §vv0.4.37, which names this spec. ⚠ The retired line stated a DONE-state and an unfinished one at once — the contradiction the A1 arm was written for. (This annotation is itself worded around the detector's vocabulary: an earlier draft's own words matched it.)

> **Drafting-era status — never revisited after the arc closed.** Preserved VERBATIM:
>
> **Status: implemented on `fix/refusal-verdict-parity` — awaiting `/code-review` and the PR.** Base
> revision `e5cce77` (main @ v0.4.34). The acceptance table's measured cells are the implementation's;
> the pre-fix / live / mutation runs are recorded in the PR, not here (§Verification). Target release
> **v0.4.35** unless the open policy question in §RC-3b resolves to a renamed public key, in which
> case **v0.5.0** (see §Risks) — that question is still open and the decision is the user's.

**Provenance.** The approved plan `~/.claude/plans/<slug>.md`
root-caused the roadmap's recorded tail after v0.4.34 and split it into two PRs. **F1** (this spec)
is the data-integrity half — RC-1…RC-4. **F2** (RC-5, RC-6: the identity-from-ambient surface and
the prose-with-no-carrier families) is a separate spec and a separate PR. Every defect below was
measured on `e5cce77`; the plan's own claims were re-measured while writing this spec and **three
were corrected** — they open the amend ledger, because a design-of-record that silently inherits a
wrong number is the defect class this cycle exists to fix.

**The class.** One shape, eight sites: **a surface re-derives meaning from a representation that
cannot distinguish the cases it is consumed as distinguishing.** A refusal is spelled the same way
as an absence (RC-1); a fault is spelled the same way as an empty store (RC-1a); an unanswerable
question is spelled the same way as a negative verdict (RC-1c); one enumeration is counted three
different ways — 3, 4 and 5 — across six sites (RC-3).

**Rule of engagement.** Every behavioral fix lands with a check that **FAILS on the pre-fix code**,
and its RED count is measured on the triple (restored code, fixture, harness) at implementation
time — never asserted from this document. Two inherited rules apply with force:

- A check that fires on a state the producer writes **deliberately** is a **false-positive class,
  not a refinement.** That is the standard which dropped three drafted clauses before implementation
  and a fourth after plan approval in `docs/record-duty-presence.spec.md` §2.6, and RC-4 is held to
  it below.
- A pin whose fixture samples only values where the old and new matchers **agree** cannot
  discriminate the defect it is meant to catch. The first drafting added *"§RC-3 shows this is true
  of **every** existing outcome pin — which is why RC-3 survived to be found by reading rather than
  by a red gate."* **Both halves are false, and the counterexample is the reverse** (amend ledger,
  revision 6 finding 28): one existing check samples the disagreement region exactly, and RC-3
  survived *because that check records the pre-fix label as its expected value*. A general rule
  stated correctly, then attached to a census that was never taken, is this document's most
  repeated error.

**How to read the citations.** Every `file:line` below is **`e5cce77`-numbered**. Resolve it against
the base commit — `git show e5cce77:<file> | sed -n '<N>p'` — and **never against the branch tree**,
which is the trap: most of these coordinates address the **pre-fix** code that this spec's own fix
replaces, so the branch's first commit already moved them. RC-3 cites `memory_status.py:830` for the
3-element matcher — which is what that line holds at `e5cce77`; on the branch tree the same number
lands on an unrelated `return`, and finding 47's rule (*quote the phrase; a line number is not a
handle*) is why the phrase travels with the coordinate here. So: a coordinate that does not resolve on
the merged tree is **expected**, and one that does not resolve on `e5cce77` is a defect in this
document.

## Scope

| ID | Finding | File(s) | Class |
|---|---|---|---|
| RC-1a | a missing/unreadable before-snapshot degrades to `before = {}`, so every store file reads as *created* — a fabricated whole-store diff, exit 0. **One sink**: the sibling `--diffs` sink was already repaired for this exact class (`:2894`) and refuses instead | `memory_status.py:4824` (`:4885` repaired) | P1 fabrication |
| RC-1b | a recognized value-taking flag with a missing value leaves the variable at the value meaning *"not supplied"*, so a malformed command is read as an absent one — a fabrication (`--audit`, `--before`), a mis-keyed sidecar (`--diffs`), a silent no-op (`--into`, `--snooze-until`) | `memory_status.py:4665`, `:4671`, `:4748` | P1 failure-honesty |
| RC-1c | `_rebuild_plan` treats a fact it could not **evaluate** as one it decided to **remove** — against its own stated invariant | `local_ingress.py:574`, `:593`, `:601-602` | P1 data loss |
| RC-1d | `local_archive`'s firewall refusal shares one error string with "not a fact" | `local_ingress.py:159-160`, `:387` | P2 failure-honesty |
| RC-2 | `--audit`'s dedup tests identity on the **last row only** and writes no supersession, so its two branches fail in opposite directions | `memory_status.py:4844-4866` | P1 record integrity |
| RC-3 | **one** action vocabulary counted **three** different ways across **six** sites — 3, 3, 4, 4, 5, plus one declaration of 5 | `memory_status.py:830`, `dashboard.template.html:1045`, `:1517`, `tests/dashboard_browser.py:423`, `render_dashboard.py:128`, `memory_status.py:80` | P1 coherence |
| RC-3b | `would_readd_archived_pointers` holds the *declined* re-adds — the name asserts the intent the value refuses — and its companion key is a public report surface | `local_ingress.py:609-610` | P3 naming + policy |
| RC-4 | two seeded duties lack a machine-visible carrier — resolved by measurement to **three** gate rows: the `entries`-vs-`audit` contradiction (narrowed), and `demotion.verdict` at two severities | `memory_status.py:4186-4200` | P2 coherence |

---

## RC-1a — a fault must not degrade into a verdict

**Current.** Two sinks parse a before-snapshot with the same three lines, and **only one of them
still has the defect**:

```python
4824        before = json.loads(Path(audit_before).read_text(encoding="utf-8")) if audit_before else {}
4825    except (OSError, json.JSONDecodeError):
4826        before = {}      # --audit's sink: FABRICATES
...
4885        before = json.loads(Path(diffs_before).read_text(encoding="utf-8")) if diffs_before else {}
4886    except (OSError, json.JSONDecodeError):
4887        before = {}      # --diffs's sink: refused one frame down
```

`before = {}` is not a neutral default: `audit_diff` reads it as **an empty store**, so every file
present afterwards reads as *created*. Measured live 2026-09-15: a fabricated `+572,437 tok` row,
**exit 0**, archived as a real row and rendered by every downstream surface.

**The repo has already settled this class once, for a different input — which is why RC-1 is a
generalisation rather than a new rule.** `docs/audit-hygiene-remediation.spec.md:19` records **A4**,
*"`_run` swallows git failure silently (broken git ≡ empty repo)"*, and the shipped fix writes the
rule the whole ID generalises (`memory_status.py:2543-2549`, quoted verbatim):

> *"a missing/broken/timed-out git must be distinguishable from a clean repo with no new commits, or
> the dream silently under-scopes ("NOTHING TO CONSOLIDATE" on a git failure would mask the failure).
> Degrade stays (`""`), now labeled."*

So A4 is RC-1 **closed** for the git input, and its shape is the one every face below must reach: the
degrade is *kept*, and a label ends its indistinguishability. (Note the tier-3 drift RC-6 exists to
fix, met here in the wild — A4's own cited coordinate, `:1263-1270`, now lands on `_is_mirror`; the
label moved to `:2543`.)

**Three arms were then executed against a hermetic pre-fix tree, and the emitted rows are
byte-identical.** `--audit <nonexistent>`, `--audit <a snapshot that is `{}`>`, and bare `--audit`
each exit **0** with empty stderr and write the same row —

```json
{"commit": "", "timestamp": "", "memory": {"created": 3, "modified": 0, "deleted": 0, "token_delta": 136},
 …, "operations": ["MEMORY.md", "ok-fact.md", "sec-probe.md", "repo_doc/README.md"]}
```

— with **no distinguishing detail anywhere in it**. "Cannot be distinguished" therefore does not rest
on a reader's judgment about which fields *look* similar: there is no byte to compare. The row is
also not empty — `created: 3` is a live fabricated count naming three real files, which is what makes
this a data-integrity defect rather than a cosmetic one. And note what the row asserts about itself:
`timestamp: ""` and `commit: ""` are the *same values* an unborn-HEAD repo legitimately produces
(RC-2), so the fabricated row is not merely indistinguishable from a first-ever audit — it is
indistinguishable from a *legitimate* row by a shape the producer really emits.

**The `--diffs` sink is already repaired, and its own comment names the defect.** `capture_diffs`
(`:2893-2898`) refuses an empty snapshot explicitly:

```python
2893    bsnap = before if isinstance(before, dict) else {}
2894    if not bsnap:
2895        return {}   # no before snapshot → NOTHING to diff against; return empty rather than fabricate every
2896                    # change as a whole-file 'created' (the render-chain audit measured exactly that lie, and
2897                    # it bypassed the size_capped guard too). The CLI turns this into a visible skip.
```

so the sink's `if not diffs and not before:` (`:4903`) prints its skip and writes nothing. **An
earlier drafting of this section called RC-1a "two sinks sharing one shape" and claimed
`capture_diffs` read `{}` as an empty store. That was false**, and it was falsified by execution
rather than by argument (amend ledger, revision 4).

**That makes RC-1a a *completion* rather than a new rule, which is the stronger position.** The repo
found this class once already — the comment above records that the render-chain audit *"measured
exactly that lie"* — and repaired it at one of the two siblings. The other still fabricates.
**An invariant is only as strong as its weakest enforcement site**, so a repair at one of two
identical sites is not a repair.

**Change.** The sibling `--diffs` path already states the required form one flag over, at its own
sink — fault plus remedy on stderr:

```python
4898        if not str(marker.get("timestamp", "")).strip():
4899            print("--diffs: skipped (cycle unstamped and no state-file stamp — run --stamp-marker first)", file=sys.stderr)
```

Generalize *this* shape rather than inventing one. The three arms separate as:

| Arm | Today | Required |
|---|---|---|
| flag absent | `before = {}` | unchanged: no snapshot is not a fault, and `:4904`'s existing notice still fires for `--diffs` |
| flag present, value missing | `before = {}` (silent) | **usage error, exit 2** — RC-1b |
| flag present, file unreadable / absent / invalid JSON | `before = {}` (fabrication) | named fault + the remedy (`run --snapshot` first), **non-zero exit**, and **no row written** |

The table is the **`--audit` sink**, which is where the fabrication lives. The same three arms at the
`--diffs` sink land on `capture_diffs`'s refusal (`:2894`) and write no fabricated diff, so RC-1a's
fabrication blast radius is **one** sink — and the other sink is cited as the *precedent* for the
shape the fix generalizes, not as a co-defendant.

**The second face is not fabrication but reach, and the `--diffs` sink has it too.** Its two reads
sit *ahead* of the `try` that promises this sink never crashes a dream, and each is narrower than the
contract the paragraph above credits it with:

- Both parse with `except (OSError, json.JSONDecodeError)` (`:4886`; the same two-member tuple at
  `:4825`), and `read_text` raises **`UnicodeDecodeError`** on a non-UTF-8 snapshot — a `ValueError`,
  not a `JSONDecodeError`. The input that reaches this arm is one this repo already writes:
  `tests/simulate_accumulation.py`'s fixture. Enumerating two members of the *"this file will not
  become JSON"* class left the third reaching the CLI as a **traceback** — a fault reported as a
  crash, which is the one outcome the arm exists to prevent. The class is `ValueError`, and the two
  members are what it was mistaken for.
- The cycle record's read (`:4889`) had **no fault arm at all**: `cyc = {}`, then — in the runs that
  reach the write, which the next sentence measures — the sidecar is
  keyed `diff_key(marker, "")` (`:4908`) — a key carrying no session segment. **The first drafting
  called that an orphan, and the reader falsifies it**: `read_diffs` probes
  `commit__ts__S<session>` first and `commit__ts` second and registers the payload under **every**
  probed key, so the base key is claimed through its legacy fallback rather than orphaned — §Risks
  carries what it resolves *to*, which is the narrower claim. Measured, and the two arms differ: on a stamped
  store with a real before-snapshot the run **writes that base-keyed sidecar and prints nothing**, and with no
  stamp it does not write but blames an absent stamp and prescribes `--stamp-marker` — a remedy for
  a fault that had not happened. Both arms are one defect: the sink had no representation for *"the
  input you named cannot be read."* `capture_diffs` refusing one frame down does not reach this,
  because the input that is wrong is the **key**, not the before-snapshot.

And the skip message was **one sentence for four causes**. Only the *flag-absent* arm may say
*"no before snapshot — Phase 0 `--snapshot` wasn't run"*; a named path that could not be read, and a
path holding a legitimately **empty** store snapshot, are different causes with different remedies,
and both wore it — so a store that is genuinely empty was told to re-run a phase it had already run,
which is **an instrument's fault and its verdict sharing one message**, with the *verdict* side here
being a true fact about a different situation. The repair states each cause as itself rather than
widening one sentence to cover four.

**The class was wider than the two sites this drafting found, and the sweep that closed it is part of
the repair.** `read_text(encoding="utf-8")` raises `UnicodeDecodeError` at *every* site that decodes a
file this tooling did not itself write, so `(OSError, json.JSONDecodeError)` does not name a class with
two members — it names two members of a larger one. Re-sweeping the file rather than re-reading the two
sites above found two more, both at base and both reachable from an ordinary command line:

- **The `--into` pre-read** (`:4837`), whose `except` names the same short tuple. Measured pre-fix:
  **rc 1 and a raw traceback out of `main()`** — the exact outcome the arm's own comment says it exists
  to prevent. It now reads `(OSError, ValueError)` and falls back to `_mrk = {}`, which is that arm's
  own *"no marker recoverable"* value; the marker is then reconciled from the stamped state file on the
  next line, so the tolerance costs nothing the arm was relying on. The operator-facing message for this
  fault comes from the **inject** sink one step later (`--into: skipped`), not from this pre-read: what
  this repair buys is that the run *reaches* it, and the acceptance note below asserts it that way
  rather than claiming a message this site does not print.
- **The mutation-log scan** inside the `--audit` dedup (`:4851`, tuple at `:4855`), which reads every
  candidate log in the fleet and died the same way on the first non-UTF-8 one — measured pre-fix, rc 1
  from the `read_text` inside the scan. It now `continue`s a candidate it cannot read. That is the safe
  direction **here** by the block's own rule stated a few lines below it — *the log's safe direction is
  to APPEND* — and the reason is asymmetric rather than convenient: a candidate the scan cannot read can
  only **withhold** a `_dup`/`supersedes` verdict, never manufacture one.

**And the container test neither sink had at base.** Valid JSON is not automatically a snapshot:
`[1, 2, 3]` is **truthy**, so it cleared the empty-snapshot test above untouched and reached
`capture_diffs` as the `before` tree. This paragraph first read that `--audit` *"has refused this
container all along"*; **the base blob falsifies it, and the truth is worse.** At `e5cce77` the
`--audit` sink did not refuse a non-dict — it **coerced** it (`before if isinstance(before, dict) else
{}`, `:4827`), silently substituting the very `{}` that fabricates the whole-store diff. So the two
sinks did not differ by a missing test; they differed by a coercion *in the sink this section credits
with protecting the other*. The container refusal (`isinstance(_b, dict)`, live `:5077`) is this PR's,
added with the same pass that gives `--diffs` the matching test one sink over.

The measurement is therefore the same at both sinks in kind and different in degree. `--diffs`,
**measured pre-fix: exit 0, stderr EMPTY, and the WRITE arm taken** — a sidecar produced whose every
line is a comparison against a list, with nothing anywhere saying the operand was not a snapshot.
`--audit`, pre-fix: the coercion to `{}` reaches `audit_diff` and reports every store file as
**created**, which is RC-1a's signature defect arriving through the container rather than through an
unreadable path. A refusal also changes the run's *shape* and not only its message: with `before = {}`
the skip ladder's `not diffs and not before` arm is reached, so `--diffs` now prints the fault and
writes nothing, where pre-fix it wrote.

**The container test's limit, stated because the paragraph above invites an overclaim.** `isinstance(x,
dict)` refuses a *list*, a *string*, a *number* — containers that can **never** be a snapshot. It does not
refuse a dict that merely *fails* to be one, and **it cannot**: `audit_snapshot` returns `{}` for a
legitimately empty store (measured on an empty project: `sorted(snap.keys()) == []`), so the empty snapshot
and a hand-written `{"foo": 1}` are the same container carrying the same keys. A shape test strict enough to
reject the second — requiring a `files` key, say — rejects the first, which is the legitimate-empty input
this section already promises is *named as empty* rather than refused. Measured on `audit_diff` directly:
`{"foo": 1}`, `{"files": "nonsense"}` and `{"files": {"a": "notadict"}}` each report every store file as
**created** — the same fabrication through a third shape — and the last of them also invents a phantom
`deleted` op for the key `files` itself, because the rollup walks whatever the dict happens to hold.

**Recorded as an open finding rather than closed here, with the reason it is not closed.** Unlike the array
it has no container-level discriminator; the honest repair is a *provenance* one — the sink knows the path
`--snapshot` printed, or the snapshot carries a format stamp — and both are design decisions this PR does
not make unilaterally. Carrying it as an open item is the disposition §Risks already gives the `--diffs`
base-key reattribution, and for the same reason: the class is real, the repair is out of this pass's scope,
and a reader who assumes the `isinstance` test closed the class has been told otherwise here.

**Two further faces the container pass had to take, both found by review of the paragraphs above.**

*The branch ORDER was itself a defect.* The `--diffs` container test was written as an `elif` behind the
emptiness test, and `[]` and `null` are **falsy** — so both matched `if diffs_before and not before:` and
were told they held *"an empty snapshot — every store file legitimately reads as new"*. That is a
malformed input wearing a benign state's sentence, the same fault-and-verdict collision RC-1d is about,
one branch earlier. Container first, emptiness second: `isinstance` is the only test that separates them,
because it is the only one the falsy non-dicts fail. **Measured 2026-09-18**, both trees: `[]` and `null`
now print the container sentence; a genuine `{}` still prints the empty-snapshot sentence, which is the
arm that keeps the reorder from swallowing a legitimate input.

*The sibling load in the same block had the same hole.* `--diffs` reads a CYCLE RECORD as well as a
`before` tree, and an int/string/list/`null` record is valid JSON — so the read *succeeds*, the value
reaches `cyc.get("session", "")` at the sidecar-keying site, and the block's blanket `except Exception`
converts it into `--diffs: skipped ('int' object has no attribute 'get')`: a raw Python exception string
where the sibling names the fault and its remedy. **Pre-fix MEASURED on the base tree**, and the reason it
hid from an earlier reading: the *"cycle unstamped"* early return diverts a non-dict record, so it is
reachable only when the state file carries a stamp and `reconcile_marker` therefore supplies one — the
fixture must stamp first, or the pin measures nothing. Coerced to `{}` rather than refused outright,
which is what the read-failure arm above already documents for this sink: the sidecar still lands, keyed
without its session segment, and skipping a capture the operator asked for would be a larger behaviour
change than the fault warrants.

**Acceptance (pre-fix RED).**
- `--audit` pointed at a nonexistent path exits non-zero, prints the remedy, and writes **no** row to
  `.consolidate-mutation-log.jsonl`. Pre-fix: exits 0 and appends a row whose created count equals
  the whole store.
- `--audit` pointed at a file containing invalid JSON behaves identically — that arm is caught today
  and is equally silent.
- **A regression guard, not a pin** — `--diffs --before <nonexistent>` writes no sidecar claiming
  every file changed. It is green on the pre-fix tree as well, because `capture_diffs`'s refusal
  already precedes the sink's own **write decision** — the sink parses both of its inputs first
  (`:4885`, `:4889`) and calls `capture_diffs` after (`:4902`), so the refusal arrives at the branch
  that decides whether to write rather than at the parse — and it therefore discriminates nothing
  about the defect; it is kept because the fix *widens that sink's parse*, and the one thing a
  widened parse can do is remove the sibling's protection while appearing to extend it.
- The absent-flag arm is unchanged (a regression check, not a fix).
- The parse's own scope is pinned rather than the sink's: a non-UTF-8 `--before` and a non-UTF-8
  `--audit` snapshot each produce a **named fault and a non-zero exit**, never a traceback. Pre-fix
  both reach the CLI as `UnicodeDecodeError` — measured on a file written by
  `tests/simulate_accumulation.py`, not synthesised for the check.
- An unreadable **cycle record** `--diffs` **names the fault** — the state the paragraph above calls
  the wrong *key* rather than the wrong snapshot. This is the pin, and it needs no precondition: the
  sentence prints where the fault is detected, ahead of both skips below it, so it fires with no
  state-file stamp and with an empty `{}` before-snapshot alike (measured 2026-09-18 with each
  precondition removed in turn). The fixture nonetheless carries **both** — a stamped state file and
  a real non-empty before-snapshot — and they are load-bearing for the **write** conjunct beside this
  pin, not for this one: diverted to either skip, that run writes nothing on *either* revision — and
  the write conjunct, being an **equality on the sidecar list**, then becomes **unsatisfiable** and
  reds on the branch as well as pre-fix, one red per variant (measured 2026-09-18 by building each
  single-precondition tree in turn: 2103 passed, 1 failed, the red being that guard in both —
  on the 2,104-check suite this branch ships, a count belonging to the triple). So the
  preconditions are what make it **passable**, not merely non-vacuous; this paragraph first said the
  comparison "goes green on both trees", borrowing the quiet that a **differencing** conjunct would
  have — one that asserts an *absence*, or compares two revisions to each other, is satisfied by the
  very state that starves it. An **equality to a value** is the opposite: it fails loudly when its
  data is missing. So "the conjunct is green on both trees" diagnoses the assertion's shape, and
  cannot be inferred from the fixture alone. Pre-fix
  `cyc = {}` is taken in silence and reported through the
  same success line as a good record, so the run says nothing about the one input it could not read.
- **And in the fixture's own run the measurement still lands**, keyed at the legacy base key — a
  regression guard, green on the
  pre-fix tree too, where the run wrote that same key silently. The scope is that run and not the
  arm: a skip firing beside the fault means nothing lands at all (§Risks), which is why this
  conjunct carries both preconditions. It is split from the pin rather than
  conjoined with it because a conjunction is never covered by covering its operands separately, and it
  exists so that a later fix cannot turn the named fault into a dropped sidecar. Writing is never
  worse than not writing, and is the only record at all whenever no sessioned sibling covers the
  marker — the pre-fix case the fallback exists for; where one does cover it, §Risks records that the
  base key is **reattributed** rather than merely mispositioned — the fault cycle's modal can render
  *the sibling's* diff — and why the fallback is out of this
  fix's scope. The exit stays `0` on the distinction §Risks draws below: the
  sidecar's *content* is a true diff of real files, so nothing here is fabricated — unlike `--audit`'s
  empty-snapshot arm, which refuses with a non-zero exit rather than print a number it could not
  compute.
- **The two further sites of the same short enumeration — swept, not spotted.** A non-UTF-8 `--into`
  record and a non-UTF-8 mutation log each exit 0 with **no traceback**. Measured pre-fix on the same
  fixture: **rc 1 and a raw `UnicodeDecodeError` out of `main()`** in both, the first from the `--into`
  pre-read (`:4837`) and the second from the `read_text` inside the dedup scan (`:4851`). Both pins
  assert the **absence** of a traceback, which is the assertion shape that can be satisfied
  **vacuously**, so each is recorded with its pre-fix verdict rather than counted on its own: the
  absence is *false* pre-fix, which is what makes it discriminating rather than merely true. The
  operator-facing **message** is attributed to the sink that actually prints it — `--into: skipped`
  comes from the inject step, not from the pre-read this repair widens — and the pin asserts it there
  instead of crediting the pre-read with a sentence it never emits. The mutation-log pin asserts the
  run's own output and **not** `_rows_rbA()`: that helper reads the log as UTF-8 and would raise on the
  very bytes the pin plants, which is a fixture that cannot fail for its stated reason.
- **The control the widened `except` requires** — the same flag pair with a READABLE record still exits
  0 and injects. This is the only one of the new checks green on **both** revisions: a guard by
  construction, kept because widening an `except` is exactly the edit that can convert a working path
  into a silent skip.
- **A `--before` holding a JSON array is refused, not diffed against** — pre-fix exit 0, stderr EMPTY,
  write arm taken. Asserted **two-sidedly** (the named fault *and* the absence of the sidecar line),
  because the message conjunct alone would also be satisfied by a run that printed it and wrote anyway.
- **The same array at `--audit` is refused** — the third route to that sink, and the clearest evidence
  that the two container arms are one defect rather than two: at base this sink did not refuse a
  non-dict, it **coerced** it to `{}`, which *is* the fabrication arm. The check asserts the exit and
  the fault's name; it deliberately does not count log rows, because a sibling pin in the same fixture
  plants non-UTF-8 bytes in that log and any helper that reads it as UTF-8 would raise.

## RC-1b — a recognized flag with a missing value is a usage error

**Current.** Seven guard sites accept a value only when the next token does not begin with `-`:

```
4665  --audit             4671  --diffs / --before / --into
4702  the four _argpaths flags        4726  --stamp-marker      4748  --snooze-until
```

so a trailing `--audit` yields `""`, which every sink reads as *flag not supplied*. The model
already exists in-file, twice, and the family should be made to behave like it:

```python
4726        if _si + 1 < len(argv) and not argv[_si + 1].startswith("-"):
4727            commit = argv[_si + 1]
4728        if not commit:
4729            print("stamp-marker: pass --stamp-marker COMMIT", file=sys.stderr)
4730            return 2
```

**The precise rule — and it is sharper than "the value becomes `""`".** Each flag is initialized to
the value that means *"not supplied"* — `""` for most, `None` for `--snooze-until`
(`:4745`). A failed guard assigns **nothing**, so the variable keeps that initial value, and the
sink cannot tell *"you omitted the flag"* from *"your command was malformed."* A flag is therefore
safe **if and only if some site downstream re-distinguishes the two** — which three of them do:

| Flag | Initial value | Guard fails → | Downstream behaviour |
|---|---|---|---|
| `--audit` | `""` (`:4662`) | stays `""` | `:4824` → `before = {}` → **every store file reads as created**. The same sink is reached by a *fourth* state the `startswith` predicate also admits — the flag present with an **empty** value (`--audit ""`) — which is why this row's fix has two predicates rather than one (acceptance list below) |
| `--before` | `""` (`:4667`) | stays `""` | `:4885` → `before = {}` → `capture_diffs:2894` refuses and `:4903` prints its skip, so **nothing is fabricated**. But that message reads *"no before snapshot — Phase 0 `--snapshot` wasn't run"*, and **it was never true for any cause that reached it**: a malformed command is not an omitted flag, and a path that was named but could not be read is a third cause again. **An instrument's fault and its verdict sharing one message**, one severity below the rest — and the scope is the whole arm, not the malformed-command case this row was first written for. **The legitimate-`{}` cause is the one that makes it a P1-adjacent honesty defect rather than a wording nit**: an empty store snapshot is a *correct* input, and the sentence told its operator to re-run a phase that had run and succeeded |
| `--diffs` | `""` (`:4667`) | stays `""` | `:4889` → `cyc = {}` → `cyc.get("session","")` is `""`, so — **given a readable `--before`** — the sidecar is keyed `diff_key(marker, "")` (`:4908`), **a diff written under a key that does not match the cycle it came from**; with no before-snapshot the skip fires and nothing is keyed at all, so the before-operand is what decides whether this row describes a write or a no-op. The refusal at `:4898-4899` (condition, then message) is only reached when the state file is *also* unstamped, so the protection is conditional, not structural. **Worth naming**: this sink's own read is what RC-1a's second face repairs — with a fault stated for the unreadable record, an empty `cyc` and an unread one stop being the same value |
| `--into` | `""` (`:4667`) | stays `""` | `:4832` and `:4869` are both `if audit_into:` → the audit block is **never injected, and nothing says so**: both fault notices live *inside* the block that never runs (`:4877`, `:4879`), as does the success line (`:4875`). `:4876`'s own comment reads *"can't inject; tell the user (don't silently no-op)"* — the empty value defeats that stated intent through the very `if` that implements it. Silent |
| `--snooze-until` | **`None`** (`:4745`) | stays **`None`** | `:2148 if snooze_until is not None:` is **false**, so it writes *nothing* — a silent no-op, **not** an empty timestamp. The flag is accepted and ignored |

**Five flags, and three exemptions with a stated reason** — this is where a blanket guard over the
whole family would have become a false-positive class:

| Exempt | Why |
|---|---|
| `--stamp-marker` | initial `""` (`:4724`), but `:4728 if not commit:` **re-distinguishes** the two cases and exits 2 — the model the rest should follow |
| `--justify-demotion` / `--justify-defrag` | take **zero or more** stems plus an optional trailing positional directory; zero stems is *already* a usage error one layer down (`run_justify_demotion:2196-2198` → `main:4708-4710` exits 2). A parse-time guard would move the same verdict earlier for no gain while risking a legitimate call shape |
| `--standing-justify-facts` / `--standing-justify-tokens` | parsed as `int()` inside a `try/except (IndexError, ValueError)` that already exits 2 (`:4733-4744`) |

The blast radius differs across the five — a fabrication, a mis-keyed sidecar, a silent no-op, and a
fault reported under a remedy that names a different cause — but the **defect is one**: the parse
leaves the same value it would have left had the flag been absent.

**Change.** One guard, placed after the unknown-flag loop (`:4657-4661`) so `--jsoon` still reports
as unknown, and before the `_argpaths` computation (`:4695`) so a malformed `--into` cannot
contribute a positional:

```python
# v0.4.35 (RC-1b): a recognized value-taking flag whose value is MISSING is a usage error.
# The `not argv[i+1].startswith("-")` predicates below cannot express this: they accept the
# flag and assign nothing, leaving the variable at the value meaning "flag not supplied" — so
# a malformed command is read as an absent one. `--stamp-marker` already re-distinguishes the
# two and returns 2 (:4728); this generalizes that verdict to the five flags whose sinks
# cannot tell the difference, and each of which fails differently (see the scope table).
_VALUE_FLAGS = ("--audit", "--before", "--diffs", "--into", "--snooze-until")
for _f in _VALUE_FLAGS:
    for _vi, _vtok in enumerate(argv):
        if _vtok == _f and (_vi + 1 >= len(argv) or argv[_vi + 1].startswith("-")
                            or argv[_vi + 1] == ""):
            print(f"{_f[2:]}: {_f} needs a value", file=sys.stderr)
            return 2
```

**…and scanning only `argv.index(_f)` would leave RC-1b's own defect standing in a duplicate
command.** An earlier drafting of the guard above read the first occurrence only — written the way
the existing parse works (`argv.index(_f)` at `:4670`, and at eight further sites) — so the *first*
occurrence wins and **any later one is silently ignored**. Measured on that shape, with a *readable*
`--before`: `--diffs <cycle.json> --before <valid.json> --before` (bare, trailing) exits 0, writes
its sidecar, and reports nothing — the malformed flag is invisible because the valid earlier
occurrence satisfied both the parse and the guard. (**The shipped PIN's operand is not this one.** It
passes `--before /x/b.json`, which is *unreadable*, so `before` degrades to `{}` on both trees and
neither writes a sidecar: the two sentences are true of different operands, and the pin's is named in
its own label. What the pin discriminates on is the exit code alone; the sidecar described here is
what the readable operand would have shown.) The guard must therefore iterate **every** occurrence of
every value flag and validate each one, not just the first. This is
RC-1b one layer down: the flag is *supplied and unvalued*, which is exactly the state the guard
exists to report, and an index-based read cannot see it. The trailing-duplicate case fabricates
nothing, so it is a **fault-honesty** case like `--before`'s own row rather than a fabrication one —
but it must be in the fix, because a fix that leaves the reported defect reachable through a legal
command line has not closed it.

**Acceptance (pre-fix RED).**
- For each of the five flags: invoking it with no value exits **2** and names the flag. Pre-fix each
  exits **0**. Four of the five additionally produce a *specific* wrong artifact — **measured pre-fix
  on a hermetic tree**, not inferred from the shared parse: `--audit` appends a mutation-log row
  reading `memory.created = <the whole store>`; `--diffs` (stamped store, valid `--before`) writes a
  sidecar whose key is missing its session segment; `--into` leaves the cycle record
  **byte-identical with empty stderr**, all three explanatory prints sitting inside the
  `if audit_into:` block; `--snooze-until`, **where the flag is honored** (a `--stamp-marker` is
  supplied), writes `beacon_snooze_until: ""` — the empty timestamp the row below says it does not
  produce. Without a stamp it writes no key at all, and that shape is not discriminating: a *real*
  value on that same line writes no key either.
  **The artifact is asserted for `--audit` only.** The five per-flag pins assert the exit code and the
  flag-naming message; the artifact-absence assertion is the **sixth** check, `--audit ""`, and its
  form is stdout-emptiness. A per-flag artifact assertion for the other four would be the stronger
  check; it is not what ships, and the difference between an acceptance claim and a description of one
  is the thing this paragraph exists to keep straight.
- **The fourth input state, and the plainest route into RC-1a's fabrication arm.** *Absent*,
  *present-with-no-value*, *present-with-an-EMPTY-value* and *present-and-valid* are four states, and
  the `startswith("-")` predicate alone folds the third into the first — `"".startswith("-")` is
  `False`, so the guard admitted it and the variable kept the value meaning "flag not supplied".
  A shell variable that expands to nothing is the ordinary way to reach it: the command SKILL.md
  ships passes `--audit <path>`, and an unset or empty expansion arrives as exactly this. Measured
  2026-09-18 **one fixture per arm** — the corrected instrument, after a first measurement ran both
  arms against one directory and let the first arm's mutation-log write move the second arm's
  baseline, and after a second instrument was discarded for letting a bare flag swallow the project
  path as its value — with the snapshot produced by the tool itself under the fixture HOME:
  `--audit ""` exits **0** and prints an audit summary whose `claude_md` block reads
  `created 1024, token_delta 4075886`, where the same fixture's real snapshot reads **0/0**; no fault
  is named, and on that arm **no row is archived** (the archived row the first instrument reported
  belonged to its own perturbed baseline). After the guard the command exits **2** with
  `audit: --audit needs a value`. Five pins, one per flag, plus a sixth asserting the **harm** rather
  than the mechanism — that the summary is not merely wrong but **absent**. Zero call sites pass an
  empty value to any of the five, so the extension removes no legitimate invocation.
- **The empty-token gap is a CLASS over four scripts, and all four close here.**
  The guard being extended is v0.4.29's `_VALUE_FLAGS` idiom, and that idiom tests a value's
  **presence**, never its **emptiness**: `if i + 1 >= len(argv)` admits `""`, because an empty token
  *is* a token. Measured 2026-09-18 with each site run three ways on a hermetic tree — flag omitted,
  flag with an empty value, flag with a real value — the same finding at every site: **the empty arm
  is byte-identical to the omitted arm**, and differs from the real-value arm, which each script
  already instruments. `distill_scan.py PROJ --into ""` → `rc 0`, 627 B stdout, 0 B stderr, identical
  to omitting the flag. `extract_signals.py PROJ --into ""` → `rc 0`, 631 B, 0 B, identical — where a
  real value adds 66 B of stderr (*"--into/--before apply to `--recalls` only — not captured"*).
  `sync_global.py --workflows --registrar PROJ --into ""` → `rc 0`, 255 B, 0 B, identical — where a
  named path reaches the registrar's read/write arm at all (measured with a nonexistent path: `rc 2`,
  *"registrar `--into` could not read/write …"*), an arm the empty value never reaches. So the
  recorded sibling rationale — the extractor's `--into` emptiness *"costs a file"*, and is therefore a
  lesser thing than `--persist`'s *"costs the gate"* — does not survive measurement of what an
  operator can **observe**: the empty arm is not a degraded success with a visible fallback, it is the
  absence spelled the same way. Two of the three carry a loud instrument for the real value that
  cannot fire for the empty one, which is `weakest-enforcement-site-wins` in its exact form: a repair
  is not durable while another site can restore the old state. **The census is 11 flags over 3 scripts
  (6 in `distill_scan.py`, 4 in `extract_signals.py`, 1 in `sync_global.py`) beyond the 5 this fix
  repairs in `memory_status.py`, and the fix shape is measured rather than assumed uniform: all three
  sites test `i + 1 >= len(argv)` and nothing else, and `distill_scan.py` and `extract_signals.py` each
  take the same **second predicate** — the dash conjunct added to that guard — while `sync_global.py`
  takes a **restructure** instead: its in-loop check is deleted, `_into` is bound to a sentinel, and the
  test moves after the loop (the distinction its own arm's GUARD label below rests on).
  `sync_global.py` carries two empty routes into **one
  variable** — `--into ""` through the guard at `:5295`, and the equals form `--into=` through
  `:5301`, whose `split("=", 1)[1]` yields `""` just as quietly — and both feed the single `_into`
  that `:5304` passes to `registrar_report`, so one consumer reads the emptiness either way. The
  equals route is not new ground: `:5301` carries the comment *"review fix: the equals form was
  silently ignored"*, so a **previous review of this exact flag closed the *ignored* half and left
  the *empty* half standing** — which is the class this spec exists to close, one layer down. Its
  separate `_VALUE_FLAGS` set at `:5243` is positional-disambiguation only, a *different* site doing a
  *different* job, not the arm to tighten. **That last claim is measured rather than judged**, because
  the boundary it draws is the one a reader reaches for first: a value-taking flag can also swallow
  the *next flag* rather than be empty (`--into --json` binds `_into = "--json"`), and at
  `sync_global.py` the fix does not clamp that. Measured 2026-09-18 —
  `--workflows --registrar --into --json <proj>` exits **2** with
  `error: registrar --into could not read/write --json: [Errno 2] No such file or directory: '--json'`
  on stderr and **0 bytes** on stdout — the OS error's own trailing `: '--json'` included, because it
  is the half that shows the flag-name-as-path reaching `open()`. So that route already lands on the
  honest arm and always did: a
  **non-empty** bogus value cannot decompile into "not supplied", and only `""` can.
  **The next-flag token is a per-script decision, and the measurement is what decides it.** At
  `distill_scan.py` and `extract_signals.py` the swallow is **silent**: `--since --into <seed>` binds
  `--since = "--into"`, the real `--into` never registers, and the run exits **0** with an empty
  stderr and no injection — a value never supplied, spelled a second way, and the same harm as the
  empty token. Both therefore take the dash conjunct, which `memory_status.py` has carried since
  v0.4.29; those two were the siblings still missing it. At `sync_global.py` the same swallow is
  **loud** (measured above), so its guard is deliberately left alone — clamping it would change a
  working arm to buy a uniformity the measurement does not support. The invariant is uniform across
  all four sites (*a value never supplied is never spelled as an absence*); the predicate is not,
  because at that one site the swallowed token is not spelled as an absence at all. **The
  maintainer's ruling is that all three ride this PR**, which is what closes the class rather than
  one site of it.
- **The eleven sibling flags, same acceptance as the five — twelve arms, one per flag and route.**
  **Nine of the twelve** exit **2** naming their flag where pre-fix they exit **0** with an empty
  stderr and output identical to omitting the flag — and for the four `distill_scan` *scalar* arms
  inside that nine, "identical" carries a clock: the run stamps its own `window` timestamp, so those
  arms agree with the omitted arm only within a run, while two runs of the *same* arm already differ
  by that field. Every other member of the nine is byte-identical outright, and each arm's own label
  says which of the two it is. `sync_global`'s equals route (`--into=`) is one of
  the twelve, and it is the only one whose pre-fix state was reached through a **different token
  shape** rather than a different token. **The three that do not fit that sentence are measured, and
  each fails it differently** — "each exits 2 … with an empty stderr" is an assertion where a
  description belongs: `distill_scan.py --proposed ""` and `--created ""` are LIST-valued, so pre-fix
  the empty token is *captured* (`proposed` becomes `[""]`; the unsupplied state is `[]`) and what
  changes is a downstream warning — rc 0 with **72 B of stderr**, not silence.
  `extract_signals.py --max ""` already exited **2** pre-fix, refused by its own `int()` parse
  (*"--max expects an integer, got ''"*); it is a pin, but on the MESSAGE conjunct alone.
  **Two arms therefore exited 2 before the fix, and only one of them is the restructure's guard.** The
  guard is `sync_global`'s bare trailing `--into`, whose usage-error site predates the change — a
  **guard on the restructure and not a pin**: the arm moved from inside the loop to after it, and the
  move is the only thing that could have lost it. It is labelled from the pre-fix run rather than from
  the author's intent,
  because *a check added by a fix may not fail on pre-fix code*, and a label is not a predicate — the
  two record different facts and the run is the one that decides which. The same rule governs the
  five `memory_status.py` arms above, where the flag-absent sink arm is a guard for the same reason.
- **The `sync_global` guard's SCOPE is a measured claim, and the measurement is why it is scoped
  where it is.** The guard sits inside the `--registrar` branch, so it does *not* fire for
  `--into ""` under plain `--workflows` — and it must not, because the flag is not consumed there:
  the script already **warns** that it is ignored. Measured 2026-09-18, one fixture per arm: the
  space-separated empty value (`--into ""`), the bare flag (`--into`, trailing) and a real path are
  byte-identical to **each other** (91 B of stderr apiece) and
  all three differ from the omitted arm by *exactly* that warning — on the pre-fix tree as well as
  this one, so the warning is not something this change introduced. **A fourth shape is not in that
  set, and the scope claim is about the three:** the equals form `--into=` emits **0 B** here, so
  outside `--registrar` it is byte-identical to *omitting* the flag — the very state this PR exists
  to remove, already present at the site the fix deliberately leaves alone. It is stated rather than
  repaired because the warning fires on a supplied *value*, and the equals form parses to no value
  at all: a parse question, not this guard's. Recorded here so the next reader does not measure the
  equals form, find silence, and conclude the three-form claim is false. The defect is therefore
  unreachable outside the registrar path, and a parse-time guard over the flag family would have
  fired where the script correctly ignores the flag — the false-positive class §2.6 names, which is
  the reason this one is branch-scoped rather than family-wide. **The warning is what that scope
  argument rests on**, and nothing else pins it, so it is pinned here: delete it and an `--into ""`
  outside `--registrar` goes silent, restoring the old state at the one site this fix deliberately
  does not cover.
- **Why `memory_status.py`'s empty `--into` is nonetheless the arm that carries the argument.** Not
  because its cost is larger — by the measurement above the three siblings cost the same silence —
  but because this sink states the intent the empty value defeats, in its own source: the injection
  block's `else` comment reads *"can't inject; tell the user (don't silently no-op)"* (`:4876`), and
  the two notices that would have said so (`:4877`, `:4879`) sit **inside** the block the empty value
  stops from running at all. The truthiness test that guards the injection is the same test that hides
  the fault. That is RC-1's shape (*an absence spelled as a result*) with the producer's own comment
  as the witness. Within `memory_status.py` the five flags are uniform in that respect and differ only
  in size: `--audit ""` reaches RC-1a's fabrication arm; `--diffs <cycle> --before ""` prints a remedy
  for a cause that did not happen, and `--diffs ""` with a valid `--before` over a stamped store keys a
  sidecar without its session segment — each of those two needs its **two-flag, fully-valid**
  invocation to be exhibited at all, since a lone `--diffs` is skipped before the write on either value
  and a lone `--before` is read by nothing; `--into ""` and `--snooze-until ""` no-op in silence. Splitting them by cost would carry each sink's semantics into
  the parse — the coupling RC-1 is about — and an empty value is never a legitimate value for any of
  the five.
- The fifth, `--before`, writes nothing wrong — its wrong artifact is the **message**:
  `--diffs --before` (bare) prints *"no before snapshot — Phase 0 `--snapshot` wasn't run"* and exits
  0. Its check therefore asserts on **stderr and exit code**, not on a file, and it is a
  **fault-honesty** case rather than a fabrication case. An earlier drafting of this spec mislabelled
  it as *"the same fabrication at the `--diffs` sink"* (amend ledger, revision 4).
- **That check asserts the message per cause, and the pre-fix message is wrong for each of them
  independently** — which is why it is several arms rather than one wording assertion. Only the
  **flag-absent** arm reaches the sink with the sentence intact, and there it is correct: no
  snapshot *is* absent, and *run `--snapshot` first* is the right remedy. The **malformed-command**
  arm never arrives — RC-1b exits 2 upstream, which is the whole point of that guard — and the two
  arms that do arrive are the ones the old sentence was false about: a named path that could not be
  read names the path and the failure class, and a path holding a **legitimately empty** store
  snapshot is named as empty. The last is the reason this is not merely a grammar fix: a correct
  input was receiving a remedy for a fault that had not happened. All three sink-side arms are
  pinned; the flag-absent one is a guard and the other two are pins.
- An in-family regression check: `--justify-demotion` with no stems still exits 2 **with the
  runner's message**, not the new one, proving the guard did not swallow a legitimate shape.
- **A duplicate flag whose *second* occurrence is bare** (`--diffs <cycle.json> --before <valid.json>
  --before`) exits **2**. Pre-fix it exits **0** and — on *this* operand, whose `--before` is readable
  — writes its sidecar, so this is a **pin** by the repo's test, not a regression guard. It carries a
  second duty worth naming: it separates a **complete** fix from a naive one, since an `argv.index`-based
  guard leaves this command exiting 0. A pin that reds both the pre-fix tree *and* a plausible-but-wrong
  fix is strictly better than one that reds only the former.
  **The shipped check samples a different operand** — `--before /x/b.json`, unreadable, *and* a `--diffs`
  record that does not exist either — so pre-fix it exits 0 and lands no sidecar, and its discrimination
  is the exit code alone. The two defects are not interchangeable, and the difference is worth stating
  because a label that named the wrong one would be this branch's own defect wearing a test's clothes:
  measured 2026-09-18 on the pre-fix tree, a missing cycle record diverts the run **first**
  (`cycle unstamped and no state-file stamp — run --stamp-marker first`), so the `before` value is never
  reasoned about — with a *readable* `--before` and that same missing record it still lands nothing. The
  readable `--before` above is what makes the sidecar claim *available*; what makes it *land* is a
  readable `--before` **and** a stamped cycle, and the check carries neither.
- **…and its sibling cell, so "complete" is tested on both conjuncts.** (`--diffs <cycle.json> --before
  <valid.json> --before ""`) — the second occurrence EMPTY rather than bare — also exits **2**, and is
  likewise a **pin**: measured 2026-09-18, pre-fix rc 0 with no stderr and a sidecar written. Its shipped
  operand is the one the arm above names, so the same correction carries: pre-fix it exits at the
  **cycle**-unstamped skip and no `before` skip is reached at all — and the empty-snapshot sentence is
  this branch's, so no pre-fix run can print it on any operand. The two arms are
  different diagonals of `{first, later} × {bare, empty}` and neither covers the other: the first
  exercises the **dash** conjunct at a later index, this one the **emptiness** conjunct there. A guard
  that iterates for the dash test and reads `argv.index()` for the emptiness test — the shape the
  parse itself uses, and a plausible half-fix — passes the first and fails this one. Sampling one cell
  and calling the class closed is the same over-claim the block's first draft carried.

## RC-1c — unevaluated is not a removal verdict

**Current.** `_rebuild_plan` states its own invariant twice:

```
518   # ... The rebuild may decline to RE-ADD an archived pointer; it may never
520   # REMOVE a live one, so a stem sitting in both docs stays.
540   # ... reading a refusal as "no entries" can only re-add, never delete.
```

and breaks it one screen later:

```
601   planned = {row["stem"] for row in included} | {row["stem"] for row in mirrors}
602   would_remove = sorted(existing_ptrs - planned)
```

Every refusal path `continue`s **before** `lines.append` — `:560` (`read_snapshot` raised), `:568`
(`UnicodeDecodeError`), `:574` (`IdentifierRefused`), `:593` (`prepare_local_fact` not ok) — so the
stem never enters `included`, `future` (`:600`) is built from `lines` alone, and the apply
transaction writes it. The stem is simultaneously *reported* in `would_remove_existing_pointers` and
*physically dropped*.

The archived-pointer case is the one the comments reason about, and there the asymmetry holds
(`admitted` is deliberately unread, `:536-540`). **Validation and the firewall are not that case.**
`prepare_local_fact` returns `{"ok": False}` for a real, admitted, live fact whenever
`validate_fact_stem` or `_looks_secret_fn()` refuses — and the firewall's false-positive arm is
recorded live in this store as reachable from ordinary prose. So a firewall false positive on a live
fact's body **de-indexes that fact**, through a line the comments above forbid.

**The pin cannot see it.** `tests/smoke.py:11806` is labelled *"drops only those pointers"*, but its
fixture's invalid file (`bad-rb.md`, contents `"not a fact"`) is genuinely not a fact, so the
assertion carrying the weight — `"](good-rb.md)" in _idx_skip` — names a **valid** stem and cannot
distinguish "drops only the invalid ones" from "drops anything it could not evaluate".

**A fifth `continue`, and it is not the only silent one — so the unevaluable set is not two lists.**
`:562-563` is `if not snap.exists: continue`, reached when `read_snapshot`
(`control_plane.py:179-185`) meets a `FileNotFoundError`. Unlike `:560`, `:568`, `:574` and `:593`
it appends to **no** list — but it is not alone in that, and the earlier drafting of this paragraph
said it was: `:513-514` is the same two-line guard in the archive-classification pass, equally
silent. Classifying all **twelve** `continue`s in `_rebuild_plan` (`:437-614`) by *what they
report* rather than by where they sit is what makes this path findable — two are name filters
(`:506`, `:553`), one is a dedup for a file the first pass already classified (`:555`), one is not
a skip at all (`:587` — the `_is_mirror` branch, which appends to `lines` and `mirrors` and *then*
continues, so the `continue` ends an iteration rather than discarding a file), **six** report
(`:512`, `:560`, `:568`, `:574`, `:580`, `:593`), and **two are silent unevaluables** (`:514`,
`:563` — both `if not snap.exists`). **The consumer rather than the guard is what separates them, and
what it separates is the HARM, not the verdict — both are defects.** `:514` feeds only the
archive-classification pass, so a file it skips is not recorded as an archive. An earlier draft read
that as safety — *"merely not recorded as an archive, and the safe direction there is to re-add"* —
and the reading fails in the way this document exists to catch: *not recorded as an archive* is also
what the classifier says about a doc that is **not** an archive, so the two states share a
representation and have opposite safe directions. The doc the pass could not read may be the
**placement record** whose pointer lines say which facts were evicted (`archive_index` in
`index_admission.py` is the canonical reader), and with it unread every one of those pointers is
re-added. That is `:563`'s loss reached with **no** flag and **no** operation, and with the report
agreeing the run was healthy. Measured on a hermetic store holding one valid fact whose pointer
`SHIPPED.md` records, pre-fix:

| stage | result |
|---|---|
| plan | **`ok: True`**, `unreadable: []` — every report list empty |
| apply, **no `--skip-invalid`** | **admitted** |
| `MEMORY.md` after | the evicted pointer is **back** |

The two arms differ in what a guard can know, not in what it costs to be wrong. `:563` sits in the
pass that builds `lines`, so its stem never enters `included` or `mirrors`, never reaches `planned`
(`:601`), and lands in `would_remove` (`:602`) as a removal nothing justified — and its stem is a
**fact** the pass could not read, which has a safe automatic action (carry its pointer, §Change).
`:514`'s doc might be a fact or the placement record, and **the guard cannot tell which**, so it
takes the direction that preserves both.
Both are deterministic rather than races: `glob("*.md")` at `:551` yields a **broken symlink**, and
`read_bytes()` follows it and raises. Measured on a hermetic store holding one valid fact plus a
dangling `ghost.md`, pre-fix:

| stage | result |
|---|---|
| plan | `would_remove_existing_pointers: ["ghost"]`, `invalid: []`, `unreadable: []` |
| apply, **no `--skip-invalid`** | **`ok: True`**, `omitted: []` |
| `MEMORY.md` after | the `ghost` pointer is gone; no report list ever named the stem |

`blocked` (`:632`) is computed from the two lists this path never enters, so the plan is not blocked
and the apply needs no flag — the same loss as the row above, reached with **less** gating and
**less** reporting. It is a stem the plan could not evaluate, so it belongs in the same repair, and
it additionally needs a report line of its own, because `--skip-invalid` is not on this path.

**Change.** `planned` becomes the set of stems whose pointer removal the plan can **justify**. A
stem the plan could not evaluate is not justified, so it enters neither `included`/`mirrors` nor
`would_remove`, and its **existing pointer line is carried through** into `future` — read from the
already-pinned `idx_snap` (the snapshot `expected` already verifies), never re-derived, so a
hand-edited line survives as the invariant requires.

Consequence for the flag: `--skip-invalid` keeps its name and its reporting role, but `omitted`
changes meaning from *"removed"* to *"left in place, unverified"*, and the report says so.
`--skip-invalid` remains the only route past a `blocked` plan (`:632`) — unchanged.

The archive pass's absent arm is repaired the same way, and it takes the other direction because it
has no safe automatic action. A store-root doc that **no loop read** is appended to `unreadable` —
the list `blocked` already reads, so the plan fails closed and the operator must either restore the
doc or say `--skip-invalid` explicitly. The set is taken from the loops' own record and not by
restating the fact loop's exclusion list: a path is unreadable-here only if neither loop read it, so
the rule cannot drift when that exclusion list changes. `SHIPPED.md` is the only name it excludes
today that the archive pass does not, which is why the two silent guards were invisible to each
other.

**Acceptance (pre-fix RED).**
- A fixture holding a **real, valid fact** with a live pointer, made unevaluable by tripping the
  firewall's false-positive arm: the plan reports it in neither `included` nor `would_remove`, and
  the rebuilt index **still carries its pointer**. Pre-fix: the pointer is dropped.
  **This fixture is not a proposal — it was built and executed against the pre-fix tree, and the
  physical index diff confirms the loss.** Scene: `sec-probe.md`, a fact valid on every other axis
  (stem validates, description present, name matches stem, scope project-local, not a mirror) with a
  live pointer in `MEMORY.md`, whose body is one sentence of ordinary prose —
  *"The body explains the not-a-secret mechanism that governs index rebuilds."* Measured pre-fix:

  | stage | result |
  |---|---|
  | `prepare_local_fact("sec-probe", …)` | `ok: False · error: secret-shaped content refused` |
  | plan | `would_remove_existing_pointers: ["sec-probe"]`, `invalid: [{stem: sec-probe, …}]` |
  | apply, `--skip-invalid` | **`ok: True`**, `omitted: ["sec-probe"]` |
  | `MEMORY.md` after | **the `sec-probe` pointer is gone**; the fact file still sits on disk, unindexed |

  The last two rows are the point of the row above them: the loss is not merely unreported, it is
  reported as **success**, and the artifact that proves it is the index diff rather than the report
  — a report agreeing with itself is what the whole spec is about.
- A second fixture pins the **silent** face: the same store shape with the fact file replaced by a
  **broken symlink**. Pre-fix — the plan lists it in `would_remove_existing_pointers` and in neither
  `invalid` nor `unreadable`, `--apply` succeeds **without** `--skip-invalid`, and the index loses
  the pointer (measured above). Post-fix: the pointer is carried through unchanged and the stem is
  reported as *left in place, unverified*.
- A third fixture pins the **archive pass's** face, which the two above do not reach because its doc
  is not a fact. Two arms on one store: with `SHIPPED.md` readable the rebuild declines the re-add
  and the evicted pointer stays out — the control, true on both revisions — and with the same doc a
  dangling symlink the plan is **`ok: False`** and `unreadable` names `SHIPPED`. Pre-fix: `ok: True`,
  `unreadable` empty, and the apply needs no flag (measured above). A third check runs the apply
  under the operator's explicit `--skip-invalid` and asserts the re-add **does** happen — it is what
  shows the block is load-bearing rather than decorative, and it too is true on both revisions.
- A fourth fixture pins the **carry's own selection**, which is where the first repair of this face
  went wrong. The carry exists so a hand-edited index line survives a rebuild. Its first predicate
  selected a line only when that line's **first** link was an unevaluable stem — while
  `existing_ptrs`, the set the same function differences against, is built with `_LINK_RE.findall`,
  i.e. **every** link on the line. The asymmetry is the defect: a stem named only as a *second* link
  on another stem's hand-edited line was never carried, so its `](stem.md)` token vanished from
  `future` while `planned` still held it and `would_remove` reported **no removal** at all. That is
  RC-1c's own harm re-entered through RC-1c's repair, and it lands on multi-pointer lines — which
  are hand-edits, which is the case this carry exists to serve.
  The reading is now the **wide** one (`findall`, matching how `existing_ptrs` is built), and the
  duplicate that reading used to cause is solved where it actually occurs: a carried line is
  VERBATIM, so the **re-derived** line for a stem the carried line already names is dropped and the
  hand-edit is the survivor. `included`/`mirrors` are left untouched, so `planned` does not move —
  the stem is still placed, by the carried line. `would_remove` is then computed **after** the carry
  and subtracts every stem the carried lines name, so the report cannot announce a removal the apply
  does not perform. The direction is the repo's own, stated in `_rebuild_plan`'s own comments: the
  rebuild "may decline to RE-ADD an archived pointer; it may never REMOVE a live one." A carried
  line that preserves a quoted token is cosmetic and recoverable; a dropped pointer is neither.
  The fixture is one store: an unevaluable stem whose line is a plain hand-edited pointer, a live
  stem whose line is hand-edited (display title, not the stem) and whose hook quotes the first
  stem's token, and a second unevaluable stem named ONLY as a second link on a third, evaluable
  stem's hand-edited line.
  **Three checks, and the discriminating conjunct is named per-conjunct** — a conjunct green on
  both revisions is a guard riding inside a pin, not evidence for it. (1) The first stem's line is
  carried verbatim, display text and all: its `future` conjunct reds pre-fix, where no carry exists
  and the pointer is dropped entirely. (2) The hand-edited line whose first link belongs to a
  different, evaluable stem is carried **and** that stem's re-derived line is dropped, so **that
  stem** is placed exactly once: reds pre-fix, where the hand-edit is absent from `future`
  altogether.
  (3) An unevaluable stem named ONLY as a second link keeps its token: reds pre-fix. Its `absent`
  conjunct is green on **both** trees — the row is keyed by the right stem either way — so it is a
  guard conjunct, not the pin.
  **The third check's assertion shape is itself load-bearing, and was wrong first.** `future` is a
  list, so a bare `"](stem.md)" in _lines` asks whether some line *equals* the token — false by
  construction, and false on the repaired tree too, where the carried line sits at `future[4]`. The
  claim is that the token survives **inside** a line, so the assertion must be a containment over
  the lines. The two sibling conjuncts above use whole-line equality correctly, because a verbatim
  carry *is* a whole line — which is exactly why this one's shape had to change with its operand.

**And the arm that fires is broad, and its own comment states a premise that fails for one of its
members — which is the root cause of RC-1c's reachability.** The trigger is not a credential. It is
`_SECRET`'s **bare-leading-dash alternative** (`:1097`), whose comment states its justification
(`:1098-1099`, quoted verbatim):

> *"a CLI-FLAG-shaped keyword (a leading `-`/`--` is the signal — **ordinary prose essentially never
> spells "-password"**)"*

**That premise is true of `-password` and false of `-pass`.** The alternative's keyword list is
`li_at|cf_clearance|password|passwd|pwd|pass(?:phrase)?|cred(?:ential)?s?|secret|token|api[_-]?key|
access[_-]?key|private[_-]?key` — a set whose members are mostly credential-only words, next to one
that is **also an ordinary English noun this skill uses as its central term**: a consolidate-memory
*pass*. The premise was checked against a representative member and generalised to the set. Measured,
minimal pairs, same keyword and same separator, varying only the following word:

| text | fires |
|---|---|
| `a per-pass snapshot here` (value 8) | **yes** — matched `-pass snapshot` |
| `a per-pass pointer here` (value 7) | no |
| `a per-pass v0-1-68 here` | **yes** — the value carries a digit |
| `a per-pass v2 here` | no |

what decides it is the alternative's own **value gate** — `(?=\S{8,}|(?=\S{4,})\S*\d)\S{4,}`
(`:1097`; rationale at `:1089-1091`) — written to spare `token: 3600` and so calibrated against the
**short** side. Eight characters is an **ordinary English word** (`handling`, `snapshot`, `mechanism`,
`narration`, `accounting`), so the threshold sits where prose is densest and fails on the long side
instead. The arm's own comment records an earlier instance of exactly this — *"`--secret flag to
enable debug logging` flagged the ordinary word 'flag' as a credential"* (`:1115-1116`) — and the
length gate was the fix. **It closed the short side and left the long side open**, which is the side
English occupies.

The consequence is that this repo's own vocabulary is in the firing set: `per-pass`, `cross-pass`,
`post-pass`, `pre-pass` all trip it (measured). A firewall arm whose false-positive population
includes the domain's most common compound is not a corner case for RC-1c — it is the case RC-1c
exists for, and it is why the acceptance row above uses prose rather than a synthetic payload.
- The v0.4.32 archived-pointer fixture (`tests/smoke.py:11817-11850`) is **unchanged** — the
  declined re-add still declines, and the stem in both docs still stays.
- `tests/smoke.py:11806` is **re-aimed**: its assertion must name a stem that was *evaluable and
  removed for a stated reason*, plus a second check naming an *unevaluable* stem and asserting its
  pointer survives. Its existing label becomes true only after this change.

### The carry's own deduction — a second silence, found by review of the repair above

**The repair introduced a defect of the class it repairs, and the class is the one this release is
named for.** `would_remove` reports what the apply DROPS, and a carried line is VERBATIM, so the key
subtracts `_named` — every stem a carried line places. That reasoning is correct. The error is that
`_named` and `_carry` are **not the same set**: `_carry` holds the unevaluable stems the carry exists
to protect, while `_named` additionally holds every OTHER stem sharing a carried line — and those may
be ordinary *decided* removals (`_remove_basis`) that merely sit beside an unevaluable one.
Subtracting them suppressed the removal from the report **and** performed no removal.

Measured 2026-09-18, two fixtures differing only in LINE LAYOUT with an identical dead-pointer stem:

| layout of the dead pointer | `would_remove` | pointer in `future` |
|---|---|---|
| on its own line | `['ghost']` | dropped |
| sharing a line with an unevaluable stem | `[]` | **retained** |

So one verdict was keyed to line layout, and in the retained case **nothing named the stem at all** —
the operator saw a dangling pointer with no list explaining it. On pristine base both stems were
dropped and reported; the v0.4.35 first cut kept the token but mis-reported `would_remove: ["ghost"]`;
this cut made report and apply agree *by removing the report*. That is the third time this release
has had to repair a silence rather than a wrong value, which is why the fix is a **carrier** rather
than a tighter subtraction.

**The repair keeps the retention and names it.** The line is still carried verbatim — re-deriving it
would destroy the hand-edit the carry exists to serve — and §2.3's own direction says retention is
the safe arm: a stale pointer is recoverable, its removal is not. What changes is that the stems
surviving against a justified removal get `would_keep_stale_pointers`, in the `would_keep_*` register
of its sibling, and the key rides the same wire shape as the other plan verdicts. It is
`_remove_basis & _named` computed once, so it is empty exactly when the carry is.

**Two checks, and the control is the half that matters.** ARM 1 is the shared-line fixture: it reds
pre-fix on the key's absence (`.get` is None) and asserts the honest-report half alongside
(`would_remove == []`). ARM 2 is the *same* ghost stem on a line of its own: dropped, reported as a
removal, retained-stale list **empty**. Without ARM 2 a key that merely mirrored `_remove_basis`
would satisfy ARM 1; the two arms differ only in the variable the defect keyed on.

**Two things the pair does *not* prove, said here rather than left for the next measurement.** ARM 1's
carried line places the carry-protected stem **first** (`- [Gone RKC](gone-rkc.md) — see also
](ghost-rkc.md)`), so it yields the same operands whether the link-reading matches *every* link on the
line or only the *leading* one — it does not pin the any-match reading, and a later tightening of that
reading would move this fixture without reding it. And on base `e5cce77` both arms read
`would_remove == ['ghost-*', 'gone-*']`, identical, because base has no carry and therefore no
layout-keyed difference at all: what the pair's power rests on is the **frozen-tree** operands, not
the pre-fix run. The one-line partition check that would close half of this —
`set(would_remove) | set(would_keep_stale_pointers) == _remove_basis`, the two disjoint — was
measured over eight fixtures and passes on all of them, but is **not** shipped: it reads a private
basis, and a check that reaches into a private name to test a public contract is the coupling this
PR is about. The invariant is recorded; the wire stays read through the public keys.

**One label in the RC-1c block above was over-claiming, and the review caught it.** The second check
said the re-derived stem's line is dropped "so it is placed exactly once" — measured, the carried
line still places every stem it names, and `gone-rbb` appears TWICE in that fixture's `future` (its
own carried line, plus the token quoted inside the hand-edited line, which is carried too). The
asserted count is `live-rbb`'s, the stem the re-derivation would have duplicated; a quoted token in a
preserved hand-edit is the cosmetic, recoverable survivor this carry is *for*. The label now says
that. **The same block's per-conjunct note was false**: it read that the `absent` conjunct is "TRUE on
both trees", and pristine base has no `absent` key at all, so `plan.get("absent")` is `None` and the
conjunct is FALSE there. Both corrections are edits to the labels, not additions of new prose.

## RC-1d — one string cannot carry two causes

**Current.** `prepare_local_fact:159-160` returns `{"ok": False, "error": "secret-shaped content
refused"}` for a firewall refusal, and the same `{"ok": False, "error": …}` channel carries "not a
fact". `local_archive:387` returns `prepared.get("error")` verbatim into that same channel, so an
operator cannot tell *"this is not a fact"* from *"this is a fact the firewall will not re-admit."*

The recorded cause for this item (*"inherits the firewall via `inject=True`"*) is **imprecise**:
`_looks_secret_fn()` runs at `:159-160`, before and independently of the flag — `inject=False`
refuses it too, and refuses many other facts besides.

**Change.** The refusal keeps its verdict; the message gains the distinguishing detail — which arm
refused, and for the firewall the remedy (this is a *relocation* of already-admitted content; the
route is the body, not the flag). No override is added in this cycle: an escape hatch is a policy
decision, and the honest step first is making the refusal legible.

**The dash arm's premise-failure is recorded and deliberately NOT repaired in F1 — and the ordering
is the reason, not the difficulty.** §RC-1c's measurement shows the arm is wrong about `pass`, and
narrowing its keyword list would be a small edit. It is still out of scope here, because it is a
**security tradeoff rather than a defect**: the arm exists to catch `--password hunter2`, and
excluding `pass` from it re-opens `--pass <value>` as a real evasion for a control whose whole job is
to refuse before content is written. F1's job is to stop a firewall refusal from being **destructive**;
once RC-1c lands, a false positive costs a fact its *verification*, not its *index entry*, and its
failure mode degrades from silent data loss to a legible skip. **Precision then becomes a quality
question instead of an integrity one** — which is the condition under which it can be decided on its
merits, with the FP/FN trade stated, the way the firewall's own docstring already decides its other
arms (*"a real tradeoff, not a bug to keep tuning"*). Doing it in F1 would mean changing a security
control and a data-loss path in one PR, and a regression in either would be attributed to the other.

**Acceptance (pre-fix RED).** The archived-firewall refusal's message names the firewall arm and is
distinguishable from the not-a-fact refusal; both remain `ok: False`.

**A second instance of the class, found by review of this PR's own diff — in the code the RC-3 repair
added.** The template loader's guard raised `"missing or duplicate action-vocabulary marker"` for BOTH
an absent marker and a duplicated one: two faults with different repairs (*restore it* vs *remove the
extra copy*), told apart by nothing, with the count that would distinguish them withheld. The bundle
marker one line below carried the identical sentence (`"missing or duplicate bundle marker: <file>"`)
and had for as long as it existed, so the new guard had copied a defect rather than a pattern. Both now
name their own cause, their own remedy, and the count they found.

**The catcher one layer up was the same defect wearing a remedy for a fault that had not happened.**
`_load_template`'s caller caught `(FileNotFoundError, ValueError)` together and reported both as
`"bundled JS module unavailable (…) — is the plugin install complete?"`. A `ValueError` from this
function is never a truncated install — it is the loader's own integrity refusal — so the sentence sent
the operator to reinstall a plugin that was installed correctly. The arms are now split: the missing-file
arm keeps the install remedy, the integrity arm reports the fault the loader already named.

**The pin is on the BUNDLE marker, not the vocabulary one, and that choice is the whole of its value.**
The vocabulary marker does not exist on the pre-fix tree, so a pin reaching for it would raise
`AttributeError` during fixture setup — an ERROR out of the suite, not a red — which is the failure mode
the loader's own comment warns about for a different reason. The bundle message exists on both trees, so
the assertion is available to be *about the change*: it requires the two arms to produce **different**
sentences, which is exactly what a two-cause string cannot do. **Measured 2026-09-18**: pre-fix both arms
raise the single string `missing or duplicate bundle marker: dashboard.network.js`, so the `!=` conjunct
is false; post-fix one reads `is ABSENT` and the other `appears 2 times`. The fixture points `_TEMPLATE`
at a temp copy with the bundles symlinked beside it and reads `_WRITE_ACTIONS_MARKER` defensively, so it
is a red on the base tree rather than a crash.

## RC-2 — the guard must test what it claims

**Current.** The dedup comment says a re-run *"must NOT double-append an indistinguishable
duplicate"*, and the predicate tests `(commit, timestamp)` equality — on **one row**:

```python
4851        _last = json.loads(_cand.read_text(encoding="utf-8").strip().rsplit("\n", 1)[-1])
4852        if (_last.get("commit"), _last.get("timestamp")) == _ident:
```

Two narrowings the recorded docket did not state, plus a third found while re-reading, all measured:

- `rsplit("\n", 1)[-1]` reads the **last row only**, so an older marker reappearing re-appends as new;
- `:4866` writes **no supersession field**, so with a *different* stamp two contradictory rows for
  one dream coexist with equal standing;
- **the guard and the comparison key on different things.** `:4846 if _ident[0]:` gates the entire
  dedup on `commit` being non-empty, while `:4852` compares the **pair** `(commit, timestamp)`. A
  dream record whose marker carries a timestamp but no commit — which `reconcile_marker` can
  legitimately produce — therefore skips the guard entirely and **appends on every run**. Three
  lines, two definitions of identity — **a guard's printed label is not the predicate it tests**,
  twice over.

**"Legitimately produce" is measured, not conceded on the producer's behalf.** The empty-commit
marker is not a hypothetical malformed input: an **unborn-HEAD** repository driven through the real
CLI (`--stamp-marker HEAD`) returns `{"ok": true}` and writes `{"commit": "", "timestamp": "…"}`.
The refusal is structural rather than incidental — `_valid_sha` (`:925-931`) is
`isinstance(s, str) and bool(re.fullmatch(r"[0-9a-fA-F]{7,40}", s))`, and `""` fails that regex, so
`reconcile_marker` (`:2159`) leaves the commit empty and `:4846 if _ident[0]:` then skips the dedup
for **every** run. Three runs produced three rows. A repository with no commits yet is an ordinary
first-day state, so the arm's population is not a corner: it is every project on the day it starts.

Both branches are wrong in opposite directions: same stamp ⇒ a correction is dropped and the false
row is permanent; different stamp ⇒ contradiction with no marker.

**Change.** Scan **every** row of every candidate log, and key the **guard** on `any(_ident)` rather
than `_ident[0]`. Then name two keys where the paragraph above used the one word *identity* for both —
which is how three adjacent lines came to test three different things:

- the **dedup** keys on the **pair** `(commit, timestamp)`: a row equal to it suppresses the append;
- the **supersession** relation keys on the **commit alone**, present and non-empty, because a row
  measuring that same commit under a *different* stamp is a later measurement of it, not a different
  cycle. The two keys cannot be collapsed into one: a guard keyed on the pair can never see that row,
  and a guard that suppressed on the commit alone would drop a genuine re-measurement.

So a new row for an already-measured commit carries `supersedes` = that earlier stamp, the most recent
when several exist — and what the field asserts is **order, not identity**: both rows measure that
commit, the later says so, and the earlier stays put, the log remaining append-only. An all-empty
identity names no cycle and suppresses nothing: the log's safe direction is to append. The
last-row-only read is deleted, not supplemented.

**Acceptance (pre-fix RED).**
- A log whose **first** row matches the current identity, followed by other rows: a re-run appends
  **nothing**. Pre-fix: appends a duplicate.
- Same cycle, changed timestamp: exactly one **new** row carrying `supersedes` = the old stamp, with
  the old row still present (the log stays append-only). Pre-fix: a new row with no supersession.
- A marker with a timestamp but an empty commit, re-run twice: the second run appends **nothing**.
  Pre-fix: it appends every time.

## RC-3 — one vocabulary, one matcher

**Current.** The schema declares five actions (`memory_status.py:80`). **Six** sites count them
against a NAMED subset — across **three** different subsets — and the *reason* for any subset is
stated nowhere:

| Consumer | Counts | Members |
|---|---|---|
| the schema (`memory_status.py:80`) | 5 declared | added, corrected, deleted, reconciled, skipped — with no matcher |
| `outcome_of` (`memory_status.py:830`) | **3** | added, corrected, deleted |
| `dashboard.template.html:1045` (`writeCount`) | **3** | the same three — a faithful copy of the line above |
| `dashboard.template.html:1517` (the entries tally) | **4** | added, corrected, deleted, **reconciled** |
| `tests/dashboard_browser.py:423` (the sort-value recomputation) | **4** | the same four — an independent agreement |
| `render_dashboard._ACTIONS` (`:128-134`) | **5** | all — the panel's count line, whose fallback is literally `"no writes"` |

**The census counts MATCHERS, and its first drafting counted FILES.** The template holds **two**
count sites, not one, and they do not agree with each other: `:1045`'s `writeCount` matches the
3-set because it was written to mirror `outcome_of` — the comment above it reads *"Align with
render_dashboard._outcome"* — while `:1517` matches the 4. A census that reads one site per file
therefore finds the template's **correct** site and misses its **incorrect** one, which is this
spec's own defect class one level up: a summary produced by a coarser unit than the data it
summarizes. `tests/dashboard_browser.py:423` is a third reader that had never been counted, and it
independently agrees with `:1517` — which is evidence *for* the 4-set over and above the SKILL.md
argument below. **The six-site census was re-taken mechanically for revision 7** — every site in
`plugins/`, `tests/` and the template whose unit is a **consumer that COUNTS** the vocabulary, **plus the
contract's own declaration** — row 1, the thing every other row is counted against and the only row
with no matcher at all, so a unit phrased as *counting consumers* alone does not reach it — matched
for any of the five action names — and it returns the same six, at the same matchers, so the
table above is now a measured count rather than a drafted one. The unit phrase is load-bearing rather
than decorative: the looser scope this sentence first stated — *every site matched for any of the five
action names* — does not reproduce the table's six under a plain reading, because it also returns a
prose comment (`render_dashboard.py:736`), two UI-text assertions (`tests/dashboard_browser.py`), and
fixture literals (`tests/smoke.py`) that compare on an action name without counting it. The table's
unit is *counting consumers* **plus that declaration**, and naming it is what makes the count
re-runnable — which is finding
37's own lesson turned on the sentence that reports it.
The re-take also produced the caution worth recording, because it is the failure mode a census has:
**a grep for the vocabulary finds sites by SPELLING, and two of the six are spelled differently.**
`tests/dashboard_browser.py:423` writes its set with single quotes (`('added','corrected',…)`) where
the template's two sites use double; `render_dashboard._ACTIONS` (`:128-134`, the 5-member row)
writes one member per LINE with the payload — glyph, label, colour — between the names. Measured on
the base tree, the two sweeps return different halves of the same table: keyed on the template's own
multi-name double-quoted spelling a grep reports **four** of the six, and made quote-agnostic but
still multi-name-per-line it reports **five** — the 5-set row is the one still missing. Only the unit
this section names, a *counting consumer*, reaches all six, and that is the argument for the unit
rather than a footnote to it. The unit is the *matcher*, and a matcher can be written more ways than
a reader anticipates — including with no name in it at all, which is the one shape the sweep above
cannot reach. That shape exists: the pooled sections bundle's `decisions()` tallies the entries by
`String(e.action)`, reaches the page through `_load_template`'s `_BUNDLES`, and lands in three
places — the "Decisions recorded" evidence button (`dashboard.sections.js:305`), the cycle-details
"Decisions" line (`:395`), and each activity row's aria-label (`:423`). It is a sentence rather than
a row because it names no subset at all — it counts every entry by whatever name that entry carries
— so it neither joins the three above nor contradicts them, and the table's six stay the six
*subsets*. The sweeps below do not return it and its count is not among theirs: a name match cannot
see a site that names nothing, which is why the method is named here as a name match rather than
left implied by the unit it reports under.

**The seventh hit is not a consumer, and the census's unit does not exclude it.** A sweep for the
3-set spelling also returns
`plugins/dream-beta-tester/fixtures/canary-v0.1.19/render_dashboard.py:223` — a genuine counting
matcher, textually identical to `memory_status.py:830`. The agreement is ancestry, not coincidence:
v0.1.19 kept the ladder in `render_dashboard._outcome` (that frozen file's `:216-234`), and L4 moved
it into the contract module — today's `render_dashboard.py:241-245` is a one-line delegation whose
comment records the move (*"L4 (v0.4.2): the single source lives in memory_status.outcome_of"*). The
canary's `memory_status.py:72` is the same story for site 1: byte-identical to today's `:80`. All **three**
twins are therefore the **pre-refactor spelling of sites 1, 2 and 6** — the third being the canary's
`render_dashboard.py:119-125` `_ACTIONS` dict, which no **line-scoped** multi-name spelling sweep
returns because each member sits on its own line with the payload between the names. The obstacle is
the line anchor and not distance: the `"added"`→`"corrected"` gap measures **23** characters, so a
matcher whose pattern may cross a newline reaches across it at any budget from 40 up (so the census's
own caution holds a second time: a sweep keyed on any multi-name spelling, whatever its quote style,
reports two of these three)
— which is why excluding them is
not a concession — they record what v0.1.19 shipped, they are vendored byte-faithful to that tag,
and manifested (`SHA256SUMS`, 5 entries, checked every run at `tests/smoke.py:7434-7437`) so they
cannot drift into agreeing with today by accident. Excluded as **frozen artifacts** rather than
read as sites: *counts the vocabulary* admits them and *live* is what refuses them — the unit phrase
is necessary, not sufficient. Named rather than dropped for two reasons: a census that silently
discards one of its own greppable hits is this spec's own defect one level up, and an ancestor is
not a second witness.

The disagreement is **visible in one payload**: for a record with `reviewed > 0` and five
`reconciled` entries, the panel prints `this cycle on <node>: = 5 reconciled` **directly above**
`NO-OP PASS · reviewed, nothing changed` — the ladder's `:840` guard (`writes == 0 and candidates
== 0 and git == 0 and reviewed == 0` → `NOTHING TO CONSOLIDATE`) means the *exact* banner depends on
the other three counts, but any of them being non-zero lands on the `NO-OP` arm at `:843`.
`outcome_of`'s own docstring calls itself "the SINGLE-SOURCE outcome vocabulary" — it is
single-source for three consumers and disagrees with the fourth.

**Which set is correct is already settled in the tree.** `reconciled` is a store **modification**:
SKILL.md describes it as a pointer relocation with an unchanged body (`:954`) and as "a load-tier
change, never a delete" (`:1062`). `skipped` is the opposite — "deliberately did not change"
(`:872`), "the fact stays, with a `skipped` row" (`:1068`). So the **write-set is the 4**, exactly
what the HTML template already matches and what the other two are wrong about.

**Change.** One declaration in the contract module, from which every consumer derives:

```python
# The cycle record's action vocabulary — ONE source for the `Entry` schema comment, the
# renderer's display table, the outcome ladder, and both of the template's count sites.
# True marks an action that MODIFIED the store: `reconciled` relocates a pointer or moves a
# fact's load tier (body unchanged — SKILL.md:954, :1062), while `skipped` is a deliberate
# non-change (SKILL.md:872, :1068). The ladder's "no writes" and the panel's count line must
# agree, so both read this tuple rather than restating a subset of it.
ACTION_VOCAB = (("added", True), ("corrected", True), ("deleted", True),
                ("reconciled", True), ("skipped", False))
```

`outcome_of` counts the `True` members; `render_dashboard._ACTIONS` keeps its glyphs and colours but
takes its keys from the declaration; the panel's fallback string is corrected to describe the set it
actually tested. `tests/dashboard_browser.py:423` already matches the `True` members and is
unchanged.

**The template gets ONE declaration, not two substituted arrays.** Both of its count sites are
rewritten to read a single emitted constant:

```js
var CM_WRITE_ACTIONS = /*__CM_WRITE_ACTIONS__*/;
```

substituted with `json.dumps([a for a, w in ACTION_VOCAB if w])`, and `writeCount` (`:1045`) and the
entries tally (`:1517`) both read it instead of their own literal arrays. One marker, one site — and
"single source" becomes structural in the template rather than two arrays kept in step by hand.

**One declaration reaches both sites — verified structurally, with one placement constraint the pin
cannot see.** Both count sites sit in the **same** `<script>` (`:925-1637`) and the **same** IIFE
(`:927`–`:1636`), so a single `var` at IIFE level is in scope for each; the two-array form was never
required by scoping. But `var` hoists the *binding*, not the value, and `outcomeOf` is first
**called** at `:1177` (`var lab=outcomeOf(CUR);`, inside the IIFE invoked on the line above). The
declaration must therefore be **assigned before `:1176` in source order**. The natural site is among
the IIFE-level declarations at `:928-936`, which already carry this exact idiom — `:935` is a single
comma-separated `var SEL, VIEW, selIdx, CUR, …`, so a declaration there is the file's own style
rather than an insertion. Placement *after* `:1176` leaves `CM_WRITE_ACTIONS` `undefined` at the
first call and throws on `.indexOf`. **That failure mode is invisible to the plain-text pin** —
the substituted marker is present and both sites do read the declaration, so the check is green while
the archive is broken — because the branch is unreachable in shipped output (measured above). It is
invisible to the browser fixtures as well: the rows-build that reads the declaration (`:1517`) runs
only inside `showArchive()`, and that function is **lazy** — defined at `:1493`, called from exactly
one site, `route()` (`:1558`) — so no IIFE-level placement can precede its first call (measured: the
declaration moved below `showArchive()`'s closing brace → **1336 browser checks passed**, rc 0, no
`FAIL` line). The ordering is guarded by neither check, and needs none for the reason the ladder
passage below establishes: nothing executes the ladder. The pin covers the substitution it claims,
and no more.

**What the fix's surfaces are pinned by — one check, and it is checkable rather than argued.** A
reviewer rebuilt this fix on the pre-fix tree and swept the suite for checks that touch its surfaces.
Exactly **one** is adjacent: `tests/smoke.py:2004-2008`, a source-form pin on `outcomeOf`'s rungs —
it asserts `if(w<=2) return "Light pass"`, `return "Substantial pass"`, and `Maintenance pass` by
spelling, and asserts `w>=4` is absent. It survives this fix by construction, and the construction
is verified, not asserted: `writeCount` is **defined** at `dashboard.template.html:1043` and
**called** from `outcomeOf` at `:1052`, while the rungs the pin greps are `:1053` and `:1056-1057`.
The fix rewrites `:1045`'s literal array — `:1043` is only the function line — and touches none of
them. So the pin's fire set is a **spelling** set rather than an edit-shape set: it reds on any edit
that changes those three exact fragments — a reflow of `:1053`, a space after the `if`, a quote change
— and on any edit that introduces the literal `w>=4` anywhere in the template, the last conjunct being
a negative spelling assertion. Of the edits *this* fix could make, the only member of that set is an
implementer who **inlines `writeCount` into `outcomeOf` or renames a rung**, which
is what a well-meaning simplification would look like.

The companion claim — that the fix has no *other* source-form pin to trip — is true **of `smoke.py`**,
and true there under **both** quote spellings: the name `writeCount` and the 3-set/4-set literals
occur **zero** times in that gate's **assertions**. The unit phrase is load-bearing and is stated
because the count is not zero for the file: the name occurs once more, quoted inside this fix's own
RC-3 diagnostic label, where it explains where the old spelling lived and asserts nothing. That is the
claim worth making, because `smoke.py` is the gate.
Within the census's scope, the sites that *do* carry the literals are §RC-3's census table above (six
rows, five of them matchers). The scope excludes the two tracked generated artifacts under
`docs/previews/nocturne/`, which carry the vocabulary too, as **output** rather than as consumers:
`index.html` is a rendered copy of the template — on the base render a multi-name sweep reaches
**three** of its lines (the `cm-data` blob's five names, `writeCount`'s 3-set, the entries tally's
4-set) and `writeCount` itself occurs **twice** — while `sample.json` holds it as **data**, one action
value per line and four of the five, which no multi-name sweep reaches at all. `write_preview`
regenerates both and `tests/docs_links.py` byte-compares them, so they are consequences of the fix
rather than sites it edits; naming them is what lets a re-run of the sweep reproduce the census rather
than argue with it. Those six are where the literals are counted — deliberately not re-derived here, because this
paragraph's first draft attempted exactly that re-derivation and came out **wrong in composition
while right in magnitude**: it reported five, but had silently substituted the **vendored** canary's
frozen copy for the shipped `render_dashboard._ACTIONS` (`:128-134`) — the 5-set it missed because
that dict writes each member *with its payload between the names*
(`"added": ("+", "added", "green"),`), so nothing that matches **within a single line** reaches across
it. The obstacle is the line anchor, not distance — the two names are **23** characters apart, well
inside any plausible proximity budget, and an unbounded `[\s\S]` pattern matches them outright. Two
cautions, both this section's: a count is only as wide as the method that took it, and the one site a
"which sites exist" sweep must not miss is the one the fix **derives** from.

**The substitution cannot ride `_BUNDLES`, and the existing exactly-once assertion cannot cover
it.** An earlier drafting of this paragraph claimed `_load_template`'s assertion
(`render_html.py:40`: `template.count(marker) != 1 → ValueError`) already covered the new marker.
It cannot. That assertion sits **inside** the loop over `_BUNDLES`, whose values are **filenames**
read at `:37` — so a marker whose replacement is a JSON literal has no file to read and cannot be a
member of that dict at all. The vocabulary therefore gets its own `replace`, with its own
exactly-once check, beside that loop rather than inside it. The check is not decoration:
`tests/smoke.py:13025` calls `rhtml._load_template()` **unguarded** to compute the `_EMBED_KEYS`
teeth pin, so a template whose marker count is not one raises `ValueError` **out of the suite** — no
totals line, exit 1 — rather than failing a check. The single-declaration form is what keeps the
count at one; substituting the array at each site separately would abort the suite instead of
reddening it.

**The route is not a preference — the alternative is blocked, and this is why.** `render_html` ships
an embed whitelist (`_EMBED_KEYS`, `:88-93`) *"audited against every `CUR.*` / `g(CUR, ...)` /
`g(c, ...)` / loop-var read in `dashboard.template.html`"*, with a smoke pin enforcing it and the
stated rule *"the template must not grow an unlisted read"* (`:87`). Embedding the vocabulary as a
new top-level **payload** key would grow exactly such a read and put the pin in tension with itself.
A marker substitution adds no `CUR.*` read at all — the JS sees a literal — so the whitelist and its
pin are untouched.

**And the idiom is already this repo's own, stated twice, in these two files.** `render_html.py:23`
imports `memory_status as ms` for *"the SINGLE-SOURCE procedure_integrity predicate (v0.1.44) —
derive, don't duplicate"*; `render_dashboard.py:38` imports it for *"the canonical tier bands
(derive, don't duplicate)"*. So RC-3 is not a missing abstraction — it is the one surface that
**violates a rule its own two files declare in their import comments**.

**One existing check samples the disagreement region exactly — and it asserts the pre-fix label.**
The first drafting of this paragraph claimed the opposite, and a pin-level review falsified it by
measurement. What is true: `_oc()` (`tests/smoke.py:205-210`) builds only `added` entries;
`_l4_matrix` (`:15120-15127`) uses `added` or `[]`; `tests/smoke.py:17782` sets an explicit `outcome`
override, which short-circuits the ladder before any count runs. Those three do sample the agreement
region.

**`tests/dashboard_fixture.py` does not.** Its base record carries `[added, corrected, skipped]`
(`:98-101`) and the splice copies `entries[0]` and re-labels the copy `reconciled` on the **last**
cycle (`:174-186`), so cycle 7 holds `added, reconciled, corrected, skipped` — and the 3-set count is
**2** (`added` + `corrected`), not 1. An earlier drafting counted only the `added` row and its
`reconciled` copy and so read the fixture as `1 → 2`, both `LIGHT PASS`; the `corrected` row present
in every cycle was omitted from the count. Measured across all eight cycles, one process per tree:

| sel | actions | pre-fix (3-set) | post-fix (4-set) | `outcome_of` |
|---|---|---|---|---|
| 0–6 | `added,added,corrected,skipped` | 3 | 3 | `SUBSTANTIAL PASS` both — agreement region |
| **7** | `added,reconciled,corrected,skipped` | **2** | **3** | **`LIGHT PASS` → `SUBSTANTIAL PASS`** |

Cycle 7 sits exactly on `writes <= 2` (`memory_status.py:845-848`), so the two revisions **straddle
the rung** rather than agreeing. The correct statement is therefore the inverse of the drafting's, and
a stronger one: the defect survived four release cycles **because the one existing check that samples
it records the pre-fix label as the expected value** — green before the fix, red after. **A pin can
encode the defect it exists to catch**, at fixture scale — not a coverage gap.

**Two CI gates go red, and no pin in `tests/smoke.py` does.** Measured on the same pair of trees as
the table above: `smoke.py` reports the **same totals line** on both, so the outcome pins this
section's census lists are all in the agreement region and the plan's "six pins move" is wrong in the
other direction from the drafting it corrected (§Risks item 3). That agreement was read on a harness
in which **no check distinguished the two trees at all**, which makes it an absence of coverage
rather than evidence of it; re-bound to the harness this branch ships, the same experiment — pre-fix
code with `:830`'s tuple as its only
widening — reads **2040 passed / 64 failed** against the unmodified pre-fix tree's **2035 / 69**.
Five checks move, all five are this branch's own RC-3 pins, and the widened matcher's red set is a
strict subset of the pre-fix one — so nothing outside those five moves, the plan's six included. The fixture feeds `_embed_integrity`
(`render_html.py:214-216`), which stamps cycle 7 into the built payload, so:

- **`tests/dashboard_browser.py:251`** — opens `#sel=7` (`:247`) and requires `LIGHT PASS` in
  `#dream-summary`, which renders the stamp verbatim. Reds. CI gate `ci.yml:154`. **Run, and green:
  1336 checks passed** on the fixed tree.
- **`tests/docs_links.py:427-431`** — byte-compares a fresh `dashboard_fixture.write_preview` render
  against the committed `docs/previews/nocturne/`; the committed `index.html` carries exactly one
  `LIGHT PASS`, as cycle 7's `_outcome` stamp. Reds. CI gate `ci.yml:123`. **Measured: rc 0 → rc 1**
  on the two trees, with the single failure naming the regeneration command.

**This is the one place where F1 is not green-by-construction, and it has a stated remedy.** The fix
must move the fixture's own expectation and **regenerate both committed preview files**
(`python3 tests/dashboard_fixture.py --out docs/previews/nocturne`), committing the result — a
generated-artifact update that is part of the change rather than an incidental diff. §Verification's
command list *runs* `docs_links.py` and so cannot be satisfied without it; the step is therefore in
the verification section rather than left to the implementer to discover from a red gate.

**Acceptance (pre-fix RED).** New checks sampling the **disagreement region** — `reconciled ≥ 1`
with the 3-set count at a rung boundary. The column values below are **measured, one process per
tree**, on `e5cce77` and on a copy of it with only `:830`'s tuple widened to the 4-set (the fix does
not exist yet, so the post-fix column cannot be read off any tree that ships).

| Fixture | Pre-fix | Required |
|---|---|---|
| `{reconciled: 1}` at `reviewed ≥ 1` | `NO-OP PASS · reviewed, nothing changed` | `LIGHT PASS` |
| `{added: 2, reconciled: 1}` | `LIGHT PASS` | `SUBSTANTIAL PASS` |
| `{reconciled: 1, skipped: 1}` | `NO-OP PASS` at `reviewed ≥ 1`; **`NOTHING TO CONSOLIDATE`** at all-zero | `LIGHT PASS` |
| **`{reconciled: 1}` at `reviewed: 0`, `candidates: 0`, `git: 0`** | **`NOTHING TO CONSOLIDATE`** | **`LIGHT PASS`** — a pin, in the region the paragraph below first called unpinnable |
| `{skipped: 3}` at `reviewed: 0` (all-zero) **and** at `reviewed: 1, candidates: 2, git: 2` | `NOTHING TO CONSOLIDATE` / `NO-OP PASS` | **identical on both revisions, at both readings** — regression guard, see below |
| the template's tally for `{reconciled: 2}` | 2 (already correct) | 2 — regression guard for the one *correct* consumer |

**The two `reviewed: 0` rows do not share a reason, and the drafting gave them one warrant that is
false twice over.** It read: *the `:840` guard short-circuits the ladder before any count runs, so a
`reviewed: 0` fixture returns the same label on both revisions and no fixture in that region can pin
RC-3.* `:840` is `if writes == 0 and candidates == 0 and git == 0 and reviewed == 0:` — its **first
conjunct is `writes`**, computed at `:830` — **ten lines above** the guard (eight statements: the
scope and maintenance blocks sit between, so "five lines" was an arithmetic error of its own, caught
by a reviewer). The guard does not run before the
count; it **consumes** it. Whether it fires is therefore a function of the matcher, exactly as every
rung below it is, and the measured rows above are the counterexamples: `{reconciled: 1}` at all-zero
flips `NOTHING TO CONSOLIDATE` → `LIGHT PASS`.

Two consequences the single-valued column was hiding:

- **A `reviewed: 0` fixture's pre-fix LABEL is reading-dependent; its pin/guard status is not.** The
  same `{reconciled: 1}` reads `NOTHING TO CONSOLIDATE` at all-zero and `NO-OP PASS · reviewed,
  nothing changed` with non-zero `candidates`/`git` — both measured on the pre-fix tree. What does
  **not** vary with the reading is *which one it is*: `{reconciled: 1}` is a **pin at both readings**,
  ending `LIGHT PASS` post-fix either way. The pin/guard split runs on the fixture's **actions**, not
  on the other three counts — which is exactly what the next bullet shows. An earlier drafting of
  this bullet got that backwards: it handed `{reconciled: 1}`'s sentence to the sibling fixture's
  behaviour, telling a reader a **pin** was stable on both revisions when it measurably moves. That
  is the direction this section's own rule calls the worse one, and it is the second consecutive
  mislabel of this same cell.
- **`{skipped: 3}` is a guard for an unrelated reason:** `skipped` is in **neither** write-set. Its
  count is 0 under both matchers, so its label is stable on both revisions *and* at both readings.
  That is a fact about the **action name**, not about the guard — which is why it was the one
  `reviewed: 0` fixture that happened to behave as the false warrant predicted.

The discriminating rule is not a boundary count but an **arm transition**: a fixture separates the
revisions exactly when the pair `(w3, w3 + r)` — the 3-set count and the 4-set count — lands in
**different ladder arms**. With the arms `w3 == 0` (`NOTHING TO CONSOLIDATE` / `NO-OP PASS`),
`1 ≤ w ≤ 2` (`LIGHT`), `w ≥ 3` (`SUBSTANTIAL`), that is:

> **`r ≥ 1` and `w3 ≤ 2` and (`w3 == 0` or `w3 + r ≥ 3`)** — and no truthy `outcome` on the record.

The first clause covers the 0-arm exit, the second the `writes <= 2` rung at `:844`. **This rule is
the third version written here and the first two were both wrong** — the drafting's *"straddles the
`writes == 0` boundary"* misses every flip across the `writes <= 2` rung, **including the table's own
row 2 and cycle 7, the flagship case of this section**; and the first correction,
`r ≥ 1 and (w3 == 0 or w3 + r ≥ 3)`, fires at `w3 ≥ 3` where both revisions are already
`SUBSTANTIAL` and nothing moves. The final form is **grid-tested, not argued**: 354 cells
(`w3, r ∈ 0..4` × two scope readings × `outcome` varied by **both presence and truth** × the
maintenance arm), **135 move**, and this form predicts all 135 and no others — **0 violations**.
Varying presence separately from truth is what makes the last clause checkable: **108 of 236**
present-and-falsy cells move, and **none of 59** truthy-override cells does, so the qualifier is
necessary *and* sufficient. The `outcome` exclusion is in the rule rather than in prose because
`:827-828` returns **before any count runs**, so a record carrying a truthy `outcome` straddles and
never moves; `maintenance.pivoted` (`:838`) needs no clause of its own because it is entered only on
`writes == 0` and therefore sits inside the `w3 == 0` case.

Keeping the `{skipped: 3}` row is still deliberate: it is the disagreement-region state
whose label must **not** move, and without it the table would imply that every fixture carrying
`reconciled` reddens. Its two columns are identical by construction, which is what makes it a guard
rather than a pin, and the row says so rather than leaving a reader to rediscover `:840`.

plus a coherence check that every **production** consumer reads the single declaration, extending the
existing `ms.outcome_of == rd._outcome` shape at `:15128-15130` to the template's declaration. The
scope word is load-bearing: `tests/dashboard_browser.py:423` is both a census row and a consumer, but
it is a **test-side literal** and stays unread — a check that reached into it would destroy what §RC-3
cites it for, an agreement *independent* of the declaration.

**The template's ladder is pinned STRUCTURALLY — and its unreachability is measured, not assumed.**
`outcomeOf` (`:1047-1057`) prefers the injected `_outcome` and reaches `writeCount`'s ladder only
when that is absent. `render_html._embed_integrity` (`:214-216`) stamps `_outcome` on **every**
cycle from `ms.outcome_of`, and every return path of `outcome_of` is non-empty (`:828` is
`str(record["outcome"]).upper()` on a value already tested truthy; the rest are literals). Every
browser fixture goes through `rh.build_html` (`tests/dashboard_browser.py:45-46`), so it carries the
stamp too. The ladder is therefore **unreachable in shipped output** — and a pre-v0.4.2 archive
ships its own frozen JS, so it cannot be reached there either. A behavioural pin would require a
fixture for a state no renderer produces.

What is pinned instead is the property the fix exists to establish: **the substituted template
contains exactly one action-vocabulary literal, and both count sites read the declaration** — a
plain-text check on `_load_template()`'s output, the same shape as the existing `_EMBED_KEYS` teeth
pin beside it. Its blind spot is stated rather than hidden: it cannot catch a JS-level mistake in
the ladder, because nothing executes that ladder. That is an acceptable limit *because* the
declaration, not the ladder, is what the fix makes single-source — and it is also why `:1045` is
repaired at all. Left alone, it would keep its faithful copy of the **old** 3-set, and the fix would
have created the divergence it exists to remove, in the one file that declares single-source as its
preference.

## RC-3b — a name must not invert its value

`would_readd_archived_pointers` (`local_ingress.py:609`) holds the re-adds the plan **declined** —
`:579` appends the stem immediately before `:580`'s `continue`. Its sibling
`would_remove_existing_pointers` names its value directly, so the operator's one interface reads
"I would do this" for the thing the plan refuses to do. The spec and the tests already name the
value correctly (*"the plan reports the **prevented** re-adds"*), so this is a **naming** defect and
not a wrong value: rename the key and its `would_readd_archived_sources` companion to say what they
hold, keeping the value, the report shape and the three v0.4.32 assertions that name the key — smoke's
`v0.4.32 P4`, `P9` and `P11` — in step. Naming those checks rather than their lines is deliberate:
this sentence first cited `tests/smoke.py:11847-11850`, which is correct on the base revision in the
*range* sense and wrong in the *reference* sense — those lines are `RC-1c`'s `would_remove` check, and
a `file:line` that resolves without supporting its claim is the same defect class this spec repairs
in RC-1d. A check label survives the next insertion; a line number does not.

**Resolved: renamed, total, and here is what it commits the release to.** The plan this spec
implements chose **rename** — `would_keep_archived_pointers` / `would_keep_archived_sources` — over
adding the corrected name alongside a deprecated old one. The two keys are `cm local rebuild-index
--json` output; the versioning policy makes a renamed *CLI flag* a **minor** and its PATCH formula
reads *"no removed/renamed key/script/flag"*, but that formula's **"key" is the cycle-record schema
key** (its CHANGELOG entries qualify it in the same sentence as `CycleRecord`/`TypedDict`) — a
`--json` **report** key has no precedent in the CHANGELOG either way. So the rename is made and the
consequence is stated rather than decided here: **a renamed report key is a changed output contract,
and the release that carries it should be authored as a minor (`v0.5.0`) unless the maintainer
records the opposite.** That is a one-line edit to the CHANGELOG section the release harness reads,
and it is named here — rather than discovered at release time — because this is the only F1 item
where the answer is not settled by the shipped tree.

The naming itself follows the family it joins: both `would_*` keys are the **plan's verdicts**, so
the value that declined a re-add reads as the verdict *"keep archived"* beside
`would_remove_existing_pointers` — the non-default direction in each case. The old name asserted the
default the plan refused, which is the whole defect.

**Two residuals, both recorded rather than repaired, with their reasons.**

- **`tests/smoke.py`'s three v0.4.32 assertions move with the key** (`P4`, `P9`, `P11`) and stay the
  pins they were: they assert the *presence* of the new key, so they red on a
  pre-fix tree for the rename's reason as well as for their original one. They cannot tell the chosen
  policy from its alternative — **all** of them assert presence, none exclusivity. The check that
  separates the two is the one added with the rename (v0.4.35 RC-3b, "the rename is TOTAL"), which
  asserts the superseded names are **absent**; it is red pre-fix, where both old names are present.
- **`docs/periphery-parity.spec.md` keeps the old spelling at all 12 sites, deliberately.** Its
  header binds it (line 3: `Cycle: fix/periphery-parity · Target: v0.4.32`), so its key names are
  correct *for the revision it records* — editing them would make it assert a v0.4.32 that never
  shipped, which is the opposite of a repair. This is the one stale-name site in F1 that is **not**
  a defect, and it is named here so a later sweep does not re-file it. The live-facing prose claim
  about these keys is this section, and it carries the new names.

## RC-4 — a duty carrier, held to the §2.6 standard

`docs/record-duty-presence.spec.md` dropped three drafted clauses before implementation and a fourth
after plan approval — the last because it fired on a state the producer writes **deliberately**. Two
duties were recorded as lacking a machine-visible carrier. Both were measured against that bar before
being written here; **measured 2026-09-17 on 99 deduped fleet records** (the §3.1 scratch class
excluded; identical counts at 119 raw and at no-dedup).

The outcome: **one drafting was unsound and is replaced, one is sound and carries a second class the
draft missed.** Both results are the §2.6 bar doing its job — in opposite directions.

### Clause X — `entries` — UNSOUND as drafted; a narrower form survives

**Why the draft fails, measured.** The conjunct *"while the record also shows scope activity"* is
satisfied **by the seed, by construction**: `scope.git_commits` is `len(ctx["commits"])` (`:3441`)
and `memories_reviewed` is `len(ctx["fact_files"])` (`:3443`) — both computed before the pass does
anything. The conjunct therefore does no work, and the draft reduces to *"entries present-and-empty"*,
which fires on `tests/smoke.py:213` (`_oc(0, 0, 0, 5)`) and `:15124` (`entries: []` with
`git_commits: 4`) — two literals the suite pins to `NO-OP PASS`. (The pin asserts a label
`outcome_of` computes *from* `entries` itself, so it is not independent evidence the state is
legitimate; the argument here rests on the **values** those records sample, not on the label they
carry.) That is the §2.6 error. A conjunct the producer always satisfies is not a narrowing.

**The narrowing that survives keys on a script-emitted operand instead:**

```python
e = record.get("entries")
if not isinstance(e, list) or e:    # absent | wrong-typed | non-empty → abstain
    return False
a = record.get("audit")
if not isinstance(a, dict):         # no audit trail → era/step gate → abstain
    return False
for s in ("memory", "claude_md", "repo_doc"):
    blk = a.get(s)
    if not isinstance(blk, dict):   # wrong-typed SUB-container → abstain, never raise
        continue
    for k in ("created", "modified", "deleted"):
        v = blk.get(k)
        # `bool` is an `int` SUBCLASS, so a JSON `true` is not a count — the idiom :3531-3534 already
        # uses for `mirror_share` (reasoning :3531-3533, code :3534). Without it a forged
        # `{"created": true}` fires an alert.
        if isinstance(v, int) and not isinstance(v, bool) and v > 0:
            return True
return False
```

**The container guard is not defensive padding — it is the family's stated contract, and the
first drafting of this predicate violated it.** `duty_gaps`'s own docstring (`:4204-4206`) promises
the predicate *"never raises **ON JSON-REACHABLE INPUT**"*, and that qualifier is measured rather
than hedged: the surrounding prose records that a `dict`/`str` **subclass** whose `get` or `strip`
raises takes the walk down, *"3 of 23 hostile inputs"*. Every sibling clause guards its own
container — `_duty_applied_fires:4156` (`isinstance(rg, dict)`), `_duty_trio_fires:4178-4179`
(`isinstance(rem, dict)`), `_duty_blank:4151` (`isinstance(v, str)`) — and `tests/smoke.py:3382`
pins the type-abstention behaviour (`_gapA({"session": 123}) == []`).

The form above `(a.get(s) or {}).get(k)` is a **null-guard wearing a type-guard's clothes**: `or`
substitutes on *falsiness*, not on *wrong type*, so `0` / `""` / `[]` / `null` / `{}` are replaced
and every **truthy non-dict** passes straight through to `.get`. Measured on the drafting as
originally written: `{"entries": [], "audit": {"memory": t}}` raises `AttributeError` for
`t` in `"not a dict"`, `["a"]`, `5`, and `true` — the last because JSON `true` is a Python `bool`,
which is an `int` subclass and so survives even a correct-looking intent. Since
`render_dashboard.py:1996` calls `ms.duty_gaps(record)` on the **persist** path, the failure mode is
a traceback at the terminal gate rather than a red check: the gate crashes instead of exiting
0/3/4. The guard is also why this clause must abstain rather than fire on a malformed sub-container
— a mistyped `audit` block is `validate_cycle_record`'s container territory, exactly as
`tests/smoke.py:3377-3379` reasons for clause A, and a clause that reported it would double-report
another gate's job.

**Why this operand, and not the two obvious alternatives.** `scope` counts what the pass **looked
at** — a nothing-changed pass still has commits, which is exactly why the draft fires on both pins.
`verification` fires on the same 1/99 but is a model self-report, and a self-report cannot gate the
duty to write one. `audit` is the script's own before/after **content-hash** diff, injected by
`--into` with **no model merge** (`:4869-4873`), so the model cannot forge it at all. `SKILL.md:1582`
names the pair the clause exists to reconcile: *"what this pass ACTUALLY changed (content-hash),
**cf. the model-narrated `entries[]`**."*

**Unforgeable is not the same property as attributable, and only one of them does the work here.**
The paragraph above establishes that the model cannot forge the operand — which is what disqualifies
a self-report from gating a duty. It does **not** establish that the operand describes *this pass*,
and the tree documents that it does not. The snapshot window spans Phase 0 to Phase 5, so anything
changing store bytes in between is attributed to the pass. `SKILL.md:1134-1136` states it plainly:
*"the snapshot window attributes ANY change between Phase 0 and now to this pass (an
interrupted/concurrent edit would mis-attribute) — don't over-trust it."* `audit_snapshot`
(`:2741-2744`) is deliberately broad — `memory/**/*.md` recursively, plus the CLAUDE.md hierarchy and
the relocate-target tree.

Two real producers of such a change, and **the first is the pass's own routine step**: Phase 1's
`sync_global --pull` lands already-approved mirrors in the native store, after Phase 0's snapshot and
before Phase 5's audit. A concurrent writer (`cm sync` in another session) or a repo commit mid-dream
does the same.

**The consequence is stated rather than argued away, and it does not move the predicate.** In that
state `entries == []` and `audit.memory.created > 0`, so the clause fires. But the state it reports
is **true** — store bytes changed and the record explains none of them — and `SKILL.md:1134-1136`
already tells the model that this exact conjunction *"is a signal to investigate"*. The firing is
right; what would be wrong is the **remedy**. A `remedy` reading "write the `entries[]` row you owe"
misleads when the change was mechanical or concurrent, so the new clause's `remedy` string names
**both** possible causes and routes to the investigation the skill already prescribes. This is the
family's own posture: clause A's docstring accepts that it *"cannot tell a seed from a finished pass,
and must not try"* (`:4225-4230`). `DutyClause` carries `remedy` as a field (`:4186-4200`), so this
is one string, not a mechanism.

**The census cannot see this class, which is a limit of the census rather than a reassurance.** All
99 records are the maintainer's own fleet — single-writer by construction — so a concurrent-writer or
mid-dream-pull record cannot exist in it. The 1/99 count measures the *audited-defect* case only.
Recorded here because the unseen class is the one that would raise it.

| class | n/99 | fires |
|---|---|---|
| `entries` absent (legacy/partial) | 5 | 0 |
| `entries` non-empty | 93 | 0 |
| `entries == []` ∧ no `audit` block (incl. a fresh seed) | 0 | 0 |
| `entries == []` ∧ `audit` present, mutations **== 0** — the legitimate no-op class | 0 | 0 |
| `entries == []` ∧ `audit` present, mutations **> 0** | **1** | **1** |

Off-fleet and executed: both pinned literals → 0; a fresh seed → 0 (`audit` is null until Phase 5).

**The container guard does not move this census, and the warrant is monotonicity — not the run.** The
first drafting of this paragraph argued from the census having *run to completion over all 99*. That
premise is **not load-bearing**: a sweep that tolerated a raise would report a raising record as *no
fire* and complete anyway, so completion is silent on the raising class. The guard rests instead on a
property that holds input by input. `isinstance(blk, dict)` is **monotonic** over the old predicate:
where the old code substituted `(blk or {})`, a falsy non-dict was already read as an empty mapping
and fired nothing — the guard `continue`s and fires nothing; a real `dict` takes the identical path
in both. So for every input on which the old predicate had a **defined** value the new one returns
the same value. The fire-set is unchanged everywhere the census could see, and the guard adds only
abstention on inputs the old form had no value on at all.

**That argument covers the container guard and stops there — `not isinstance(v, bool)` is a different
kind of change and needs its own warrant.** It is not a guard but a **narrowing of the fire-set**:
`{"created": true}` is JSON-reachable, the old predicate *fires* on it, and this one abstains. No
argument about raising speaks to it, and the census above reading 1/99 now rests on a **producer**
fact rather than on the run. That fact is provable rather than asserted: `audit_snapshot` builds the
rollup as a fresh literal of `int` zeros (`:2771`), touches it only through `roll[store][op] += 1`
(`:2800`) and `roll[store]["token_delta"] += delta` (`:2801`), and returns it directly into the
record (`:2815`) — it is never seeded from, nor re-read out of, parsed JSON. A `bool` therefore
cannot arise from any write path; only a hand-forged record can carry one, which is precisely the
input a gate should abstain on rather than alert from. The house idiom pairs the guard with this same
producer fact in one breath at `:3531-3534`: *"a hand-set `true` would persist as 1.0 … **the
producer never writes one**"*.

**Honest limit, stated rather than hidden.** The rollup cannot name *which* row was owed — only that the memory plane changed. The apparent weakness is `MEMORY.md`, which `SKILL.md:1582` calls *"expected re-index churn"*; but the audit is **content-hash** based, and a hash-equal file is **not an op at all** (`:2791`, `:2798` — *"unchanged (same hash) or both absent → not an op"*). So `MEMORY.md` appearing in `operations` means its **bytes genuinely changed**, which by `SKILL.md:871-873` owes a row. The churn is the clause working, not a false positive.

That distinction also rules out an apparently stronger predicate. Restricting the op scan to non-`MEMORY.md` paths still fires **1/99** on the fleet this clause was measured over, and the rows it keeps are **fact-body** paths rather than the index — which is what invites dropping the churn caveat and keying on content changes alone. (That fleet is the measuring session's own store and is not committed, so the count is this cycle's testimony rather than a committed artifact's; the argument below does not turn on its exact value, only on the fact that excluding the index removes no firing rows.) **That form would introduce a false negative**: a pointer-only reconciliation changes the index and no fact body, and a `reconciled` row is exactly what is owed there — so narrowing would trade a concern the hash test already dissolves for a miss on the action this spec exists to make counted. The store rollup stays.

### Clause Y — `demotion.verdict` — SOUND as drafted, plus a second class

**This is not a clause this spec invents; it is a mandate with no carrier.** `SKILL.md:1073-1074`
states it in almost the draft's own words: *"Fill `demotion.verdict` — ONE sentence, **always** (a
dormant/none verdict is still a verdict; 'ran and proposed nothing' must be distinguishable from
'never ran')."* And `:1053-1056` mandates the dormant case specifically: *"While `eligible: 0` the
policy is DORMANT (the evidence gate: … a fact needs ≥3 probative zero-read windows …) — record
`verdict: "dormant — N probative windows"` and move on (empty-set rule: that one-liner IS the
judgment …)."* The duty, the distinction and the required phrasing all already exist; only the
machine-visible carrier is missing.

**And the Empty-set rule, read correctly, is support for D and E rather than an excuse for an
empty `entries[]`.** `SKILL.md:215` names `demotion.eligible == 0` among its empty **scripted
detector sets**, and `:217-218` then requires: *"Emit the required one-liner verdict from those
counts, `--into` it where the phase says to, and proceed."* The rule blesses an empty *detector set*
and routes its judgment to a **block verdict** — it never mentions `entries[]`, so it cannot excuse
an empty one, and `:222-224` (*"Never skip the scan to save a turn … Empty is a result, not a
skip"*) means an empty set still owes its line. A drafting that cited this rule as licence for an
empty `entries[]` would be reading it backwards; that drafting is gone from this section.

**The era gate is the BLOCK, not the key — and this is the trap the family sets.** `:4238` states the
shipped family's rule: *"an ABSENT key never fires either."* That is right for `session` and
`applied`, single-key presence tests whose era *is* the key's arrival. It is **wrong for Y**, whose
era gate is the `demotion` block (`:3539-3544`, written iff `ctx["auto_mem"].exists()`). A
presence-gated form (`"verdict" in dm and blank(dm["verdict"])`) fires **0/99** — no producer ever
writes a blank verdict, so absence is the only failure mode and the predicate must be
**blank-or-absent**. Copying the family's rule verbatim into the existing table would ship a clause
that can never fire.

**Two rows, not one** — matching the family's per-row severity grain (A warn, B alert, C alert):

| Clause | Predicate | Census | Severity |
|---|---|---|---|
| **D** | `eligible > 0` ∧ blank-or-absent verdict | 1/99 | **alert** — the triage ran and its sentence is absent |
| **E** | block present ∧ `eligible == 0` ∧ blank-or-absent verdict | 4/99 | **warn** — a mandated one-liner missing, nothing at stake |

| class | n/99 | fires |
|---|---|---|
| no `demotion` key (legacy/partial) | 53 | — (era gate excludes) |
| `eligible > 0`, verdict filled | 20 | no |
| dormant (`eligible == 0`), verdict filled | 21 | no |
| `eligible > 0`, **no** verdict | **1** | **D** |
| dormant, **no** verdict | **4** | **E** |

**What E's warn severity buys, and why it is not alert.** E fires on a fresh seed whose store has no
accrued evidence — the same posture as clause **A**, and for the reason the family's own docstring
already sanctions (`:4225-4230`: *"this predicate fires on a fresh seed — it cannot tell a seed from
a finished pass, and must not try"*). `warn` does not change the exit code (`:4242`), so E is a panel
report exactly as A is.

**And D's firing is evidence-conditioned, which is the property that makes it safe.** The seed copies
the store-derived count verbatim (`:3543`), so D fires on a fresh seed **only if the store has ≥1
eligible fact**. It separates a seed from a finished pass **on the evidence clock** — without reading
`rigor.phase`, which `:4225-4230` forbids precisely because it is a model self-report.

**The one honest cost of the split:** at persist on a store with `eligible == 0`, a dormant pass that
skipped its mandated one-liner is covered by E (warn) but never escalates. Deliberate — nothing was
at stake — and it is why E is not alert.

**Measured value, stated plainly rather than argued away.** Both surviving clauses fire on **the same
single fleet record** — the one `docs/record-duty-presence.spec.md:14` names as its derivation head,
whose `duty_gaps` **already returns three gaps today** (`session`, `applied`, `trio`; the shipped gate
exits 3). So RC-4 buys *independent coverage of the class*, not new detection in the observed corpus:
a record could carry either gap without the others, which is the reason to have the clauses, but on
99 records of evidence the marginal detection is zero. Both facts are recorded here because a clause
justified by its class membership and a clause justified by its measured yield are different claims,
and only the first one is true.

**Change.** Three more rows in the **existing** `_DUTY_CLAUSES` (`memory_status.py:4186-4200`), which
today holds exactly three (`session` warn, `applied` alert, `trio` alert) and is consumed unchanged by
`duty_gaps` (`:4203`, `:4249`). No new mechanism, no new gate, no change to the persist exit codes:
`alert` still exits 3 (`:4242`), `warn` still does not. Each new row carries its own `fires(record)`
and severity, matching the family's grain. The one place a row **departs** from the family is the
absence rule — blank-or-absent, not present-and-blank (`:4238`) — and that departure is justified at
the point of use by the era gate having moved from the key to the block, so a reader comparing the
rows side by side meets the reason and not just the difference.

**Two decisions this section had left to the implementation are made here, because a design of
record that omits them would be handing the reader a choice it never examined.**

**(a) Clause X is `warn` — a severity every earlier revision of this section left unstated.** The
family's grain is not "how bad is the state" but **whether the gap has a closure the model honestly
controls**: A is warn because an unknown session id cannot be honestly written (SKILL forbids
fabricating one), while B and C are alert because the tier and the trio are measurements the pass has
just made. X has that closure in its *common* case — a pass that narrated nothing owes the row,
including a Phase-1 `--pull` landing, which `SKILL.md` already requires to appear in the mutation
audit — but none at all in the case this section spends three paragraphs on: a concurrent writer's
change, which the pass did not make and must not claim. A gate whose only honest exit is a
fabrication is the failure clause A's own docstring refuses, and `alert` would have bought nothing
measurable: on the one fleet record that fires X, the shipped gate exits 3 anyway through
`session`/`applied`/`trio`, so `warn` removes no gate from any observed record while `alert` would
stall every pass that pulls mirrors into a store it did not otherwise write. The cost is stated
rather than implied: a `--pull` that lands after the Phase-0 snapshot and is *not* narrated reaches
the panel and not the exit.

**(b) Both `demotion` rows abstain when `eligible` is absent or wrong-typed**, which is the shape
§Clause Y's closure paragraph names as the one that would re-open the class list. It is decided, not
deferred: `eligible == 0` is a CLAIM — "the evidence gate is closed" — that an absent count does not
make, a block missing its script-written count is a partial block, and a partial block is
`validate_cycle_record`'s container territory, exactly as clause A abstains on `session: 123`. The
narrowing is the same idiom the audit counts get (`isinstance(v, int) and not isinstance(v, bool)`),
warranted there by the producer writing `+= 1` and here by it writing `len()`. The cost is stated:
a dormant record that dropped the count is reported by nothing in this family.

**(c) Both `demotion` rows abstain during a maintenance/bootstrap pivot.** A third abstention, and it
is (b)'s sibling rather than a refinement of it: (b) covers a count the record does not carry, and
this covers a count it carries truthfully while the duty it belongs to was **never owed**. The pivot
is a state the producer writes **deliberately** — `maintenance.pivoted` marks a bounded
bootstrap/self-heal pass scoped to pull + health, which legitimately never runs the demotion triage.
The repo's binding rule for exactly this shape is `docs/record-duty-presence.spec.md` §2.6: *a
clause/check that fires on a state the producer writes DELIBERATELY is a false-positive class, not a
refinement*. A row that fired here would not be a tighter duty check; it would be a defect of its own,
and clause D would join the class the rest of this spec exists to close.

**The control cases are what make it a carve-out rather than a silence.** Measured against
`duty_gaps` directly on the working tree, 2026-09-18: `{"maintenance": {"pivoted": true}, "demotion":
{"windows_observed": 3, "eligible": 3, "surfaced": []}}` returns `[]`, while the same record with
**no** `maintenance` block, with `pivoted` absent, and with `pivoted: 0` each returns `["demotion"]`.
The carve-out is therefore scoped to the pivot and does not widen into "a demotion row that never
fires" — which is this shape's default failure mode, and the reason the three controls are recorded
here beside the case they qualify rather than in the test file alone.

**The predicate is a COERCION and not a truthiness test.** `"pivoted": "false"` is a **truthy
string** — the model-slip class `render_dashboard._flag` exists for — so a bare
`record["maintenance"].get("pivoted")` reads a NON-pivot pass as a pivot and silences all three
readers at once. The accepted spellings are the JSON boolean and its two string forms, exactly as the
oracle's `beta_checks._maintenance_pivoted` accepts them; anything else is NOT pivoted. Measured:
`{"pivoted": "false"}` with `eligible: 3` and no verdict still returns `["demotion"]`, and the same
record through `outcome_of` returns `NOTHING TO CONSOLIDATE` rather than `MAINTENANCE PASS`.

**One definition behind the three PYTHON readers** — `outcome_of`'s MAINTENANCE PASS rung and the
two `demotion` duty rows read the same `pivot_fired(record)`. That is the RC-3 repair's own rule
applied here in advance: the alternative is two spellings of "is this a pivot" that agree until the
day one of them is fixed, which is the defect this whole cycle is about. It is written as a named
helper for the same reason RC-3 hoisted `outcome_of` — a seam three readers can be pointed at is a
seam that can be *pinned*, and the mutation below is only possible to run because there is one site
to mutate.

**A fourth site exists, and the heading above had to lose its "three readers" to say so.** The
shipped template carries its own spelling of the same question:
`dashboard.template.html`'s `truthy` is `/^(true|1|yes)$/i` over a trimmed string, and
`outcomeOf`'s ladder reads `maintenance.pivoted` through it. `"yes"` is accepted THERE and rejected
by `pivot_fired`, so `{"pivoted": "yes"}` renders "Maintenance pass" in the JS ladder while
`outcome_of` returns `NOTHING TO CONSOLIDATE` — two spellings of one question, disagreeing on one
input, which is precisely the sentence this section uses to indict the class.

It is **latent, not live**, and the reason is worth stating rather than left as reassurance:
`outcomeOf` returns an injected `_outcome` first and a record's own `outcome` second, and only
reaches the ladder when it has NEITHER. `render_html` injects `_outcome`, so the shipped path never
gets there — the ladder is documented in its own comment as the legacy fallback for records embedded
before the injection existed. Nothing pins the JS coercion either: the smoke check for this family
drives `pivoted: True` only. So this is a **recorded residual, not a repair** — closing it means
either deriving the JS predicate from the Python one (as `CM_WRITE_ACTIONS` now is) or retiring the
ladder, and neither belongs in a patch whose subject is the Python sinks. It is named here so the
next reader does not have to rediscover it from a four-way grep.

**Measured by mutation on the otherwise-final tree, 2026-09-18.** Replacing the coercion with the
naive test (`bool(mt.get("pivoted")) if isinstance(mt, dict) else False`) yields **2102 passed / 2
failed** against the **2,104-check** harness whose `tests/smoke.py` sha256 is
`59f83fccee7122c16c0c25b4868e5bf7d79d50565d76c2263dee71be3a664cfa`, and the two reds are exactly the
two PINs written for this predicate — its `outcome_of` reader and its duty-clause reader. Both
labelled PIN, and that is a measured statement rather than a drafting one: the duty-clause arm
carried a GUARD label until this branch's own label audit ran, on the false premise that pre-fix it
"fires for its own reason". Pre-fix **no `demotion` clause exists to fire at all**, so that arm is
RED there and a PIN; the abstention arm beside it is the one that is green pre-fix, and that is the
one carrying the GUARD. All four numbers are one
measurement: the count belongs to the triple (mutated code, fixture, harness), the harness sha is
what makes the triple recoverable, and none of them is carried across an edit — which is the whole
reason the sha is stated and the total alone is not, since a count restated without its harness is
silently re-bound to whatever harness the reader happens to have.
**The shape of the red set is the finding, not the count:** a red set *contained in* the checks
written for the mutation means the suite can see this defect and only this defect; a larger one would
mean the naive test was load-bearing somewhere else and the coercion had quietly moved a second
behaviour — which is how a repair of this shape fails. The containment was re-confirmed on this
harness: the four checks added by the review round that followed this measurement stay GREEN under
the mutation, which is what containment means here.

**And what the mutation does NOT cover, stated because the paragraph above invites the overclaim.**
It tests the COERCION, not the CARVE-OUT: a carve-out that was too *wide* — abstaining on some
non-pivot state — would leave this mutation's red set unchanged. That direction is carried by the
three controls in the measurement above and by the duty table's own row census, not by any mutation,
and the distinction is the same one the RC-3 section draws between a check that observes a value and
a check that observes a decision.

**Three carrier updates the new rows make compulsory, none of them optional.** Adding a row edits a
contract that other surfaces *describe*, and this repo's recorded history is that an undescribed
contract drifts while every gate stays green:

- **`SKILL.md`'s record-duty section (`:1340-1353`) states the family rule and then enumerates the
  clauses with per-clause exit semantics** — `session` warn, `rigor.applied` exit 3, the trio exit 3.
  Three new rows leave that enumeration **false by omission**; worse, the family rule it states —
  *"A duty that is present and holding nothing (**never an absent key**: a partial record is normal,
  the phases fill it incrementally)"* — becomes **false as a universal** for clause E, which fires on
  an absent key *inside a present block*. The section must gain the new rows with their severities,
  and the absence rule must be qualified to *"an absent **block** never fires"* — which is what it
  was always about. The era gate moved from the key to the block for these rows; the prose has to
  move with it. This is the same obligation RC-4 inherits at `:4238`, only larger, because `SKILL.md`
  is the arbiter the rest of the plugin reads.
- **Four comments state the clause count as a fact, and each goes false the moment the table
  grows:** `tests/smoke.py:3507`, `:3612` (*"the number is the rows drawn, and `_DUTY_CLAUSES` is
  three"*), the same sentence in `docs/record-duty-presence.spec.md:1381`, and — **found by a
  re-census during implementation, not by the drafting** — `render_dashboard.py:416-417`, the
  duty panel's *own* docstring, which enumerated the family's remedies (*"fill a session id /
  record a tier / complete a trio … one generic sentence for all three"*). The drafting swept the
  module that DECLARES the clauses and the suite that reads them, and missed the module that
  RENDERS them; the site is named here rather than silently repaired because a carrier census that
  is short by one is the same defect this bullet exists to close. Its repair is by deletion rather
  than by re-numbering — an inventory of a growing list is a statement that must be maintained,
  so the enumeration was replaced by the relation it was reaching for (every row carries its own
  remedy), which holds at any size. The first two are live
  code comments read as current truth, and they are not incidental — they are the **stated reason** a
  `\d{1,4}` capture bound cannot reject a legitimate render, and it is that reason's *value* which
  moves. The repair is to state the **relation** instead of the number: the panel's count is bounded
  by `len(_DUTY_CLAUSES)`, a small constant the four-digit bound covers with orders of magnitude of
  headroom — true at three rows, at six, and at six hundred. **No pin is proposed for this**, because
  stating a bound rather than a size removes the drift instead of monitoring it, and no gate can read
  a comment anyway. The third site is a spec's **amend ledger** — a dated record of a past revision —
  and is deliberately left as written; rewriting a historical entry to match today's tree would
  falsify the record it exists to keep.
- **Two further comments state the clause SET rather than its size, and a size census cannot see
  them because they drift on a different event.** `render_dashboard.py:410` and `:2039` each
  described the warn-only path as *"clause A alone"* — a claim about **which** rows are `warn`,
  falsified not by the table growing but by a **severity changing**, i.e. by a second row shipping
  at `warn`, which is what this cycle's own RC-4 work does. A count reads *how many* rows; these
  read *which*, and the two fail apart: the four sites in the bullet above were all still true when
  these two had been false for a release. Both now state the **relation** — *"a gap whose every
  FIRED ROW is `warn`"* — which holds at any size and any severity distribution, and the repair is
  by deletion of the roster rather than by re-numbering it, for the reason given above. Recorded
  rather than silently repaired, and this is the **second consecutive re-census to find one**, which
  is the strongest evidence available that a carrier census is not a thing to be done once: the
  first found the module that RENDERS the clauses after sweeping the module that declares them and
  the suite that reads them, and this one found a site whose *drift event* the first sweep had no
  reason to model.
- **`_DUTY_CLAUSES` is bound to no prose by any pin.** A smoke check pins the SKILL **schema block**
  to `CycleRecord.__annotations__`, so those two cannot drift; nothing does that for the duty
  enumeration, which is why the first bullet is a manual obligation and why it would drift again.
  The Acceptance section adds the cheap structural guard that retires the risk.
- **`skills/consolidate-memory/SKILL.md:64-66` also enumerates clauses, and is deliberately left as
  written.** That paragraph
  is a per-release changelog: `:60` opens *"the v0.4.33 record-duty-presence patch"* and `:64-66`
  names the clauses **that patch** shipped. A later patch adding clauses does not falsify a sentence
  about an earlier one, and the paragraph's own growth mechanism is to append a new
  *"plus the vX.Y.Z … patch (…)"* entry — which RC-4 does. The distinction from `:1345-1352` is the
  whole point and is worth stating once: that enumeration describes the **current contract** with
  per-clause exit semantics and must be complete; this one describes **what a past release did** and
  must not be rewritten. The same rule already governs `docs/record-duty-presence.spec.md:1381` two
  bullets above. The review raised `:64-66` as a second gap; it is a second *site* of the same
  enumeration but not a second obligation, and the difference is datedness.

**Acceptance — four pins and four guards, by assertion shape.** RC-4 is the one ID in this spec whose
fix is *additive to a gate that had no such row*, so the repo's own rule applies and is quoted rather
than assumed: *a check added by a fix may not fail on pre-fix code — that is a regression guard, not a
pin.* Separating them explicitly:

| Check | Pre-fix behaviour | Status |
|---|---|---|
| `duty_gaps(the audited-defect record)` contains the `entries` gap | returns 3 gaps, none of them this one → **FAILS** | **PIN** |
| `duty_gaps(the audited-defect record)` contains the `demotion` gap (D) | returns 3 gaps, none of them this one → **FAILS** | **PIN** |
| Each clause abstains on its legitimate classes: **one synthetic record per class** — no `demotion` block, a dormant stamped verdict, non-empty `entries` — plus **both pinned literals** | passes vacuously (no clause exists to fire) | **regression guard** — *the classes, not the fleet*: see below |
| E **fires** on a dormant block with no verdict | clause E does not exist, so the gap list is `[]` and the fire-assertion is **FALSE** → **FAILS** | **PIN** |
| D **does not fire** on that same dormant block (severity separation — the two clauses partition the class rather than overlapping on it) | no clause exists to fire, so the abstention holds | **regression guard** — the split of the conjunction, so each half carries its own label |
| Every new clause **abstains** — never raises — on a record whose `audit` sub-containers are wrong-typed: `{"entries": [], "audit": {"memory": t}}` for `t` in `"not a dict"`, `["a"]`, `5`, `true`; and again on the **counts**, in three more arms: a well-typed container holding `{"created": true}`, and `demotion`'s `eligible` both **absent** (`{"windows_observed": 3, "surfaced": []}` — a partial block, whose `eligible == 0` a missing count cannot claim) and **wrong-typed** (`t` in `None`, `"2"`, `2.5`, `true`, `false`) | clause X does not exist, so `duty_gaps` returns `[]`: **passes** | **regression guard** — it reds the *buggy implementation*, not the pre-fix tree, and "the buggy implementation" is more than one mutation. **EVERY figure in this cell is the intermediate 2,054-check harness** — every total in it sums to that number (`713 + 1341`, `2053 + 1`, `2054 + 0`, `2023 + 31`) — and *not* the shipping 2,104; the harness is named here because a number whose triple is unnamed is the defect this cycle is about, and the reader who meets `2053` under a §Verification that says `2,104` should find the reason in the figure's own cell rather than conclude the spec contradicts itself. **Measured, and the measurement corrected this cell:** the `(a.get(s) or {})` form does raise `AttributeError` on all four inputs, but driving it through this check does not RED it — it **aborts the suite** (713 checks printed, no totals line, 1341 never run), which is the failure mode v0.4.33's own F2 finding recorded for the unbounded capture and fixed there by bounding it. So the guard calls its subject through a wrapper that turns a raise into a value; re-measured on the same mutated tree the run completes at `2053 passed, 1 failed`, the one RED being this check, naming the exception. **The `eligible` arms carry a second mutant, and it too is measured:** a string/float/null fails `isinstance(el, int)`, but JSON `true`/`false` PASS it and are stopped only by the `not isinstance(el, bool)` narrowing — without it `True > 0` fires D and `False == 0` fires E. Stripping that narrowing from both demotion predicates reds **this check and only this check** (`2053 passed, 1 failed`, named); the same mutant with the `eligible` conjuncts removed is the **control** at `2054 passed, 0 failed`, which is what shows the narrowing was unprotected before them. The extended guard stays a guard: on the pre-fix tree it measures `2023 passed, 31 failed` — bit-identical to the pre-extension run — so the added conjuncts are green pre-fix and the check count does not move |
| The `SKILL.md` duty section names every clause in `_DUTY_CLAUSES` | three names, three clauses: **passes** | **regression guard** — it reds the *un-updated document*, and it is the only thing that would catch the enumeration drifting a second time |
| A **concurrent-writer record** — `entries == []` and `audit.memory.created > 0`, the change landed between Phase 0 and Phase 5 by a `--pull`, a `cm sync` or a commit rather than by the pass — **fires** clause X | clause X does not exist, so `duty_gaps` returns `[]` and the fire-assertion is **FALSE** → **FAILS** | **PIN** — it pins the *documented* behaviour rather than the intended one, which is what makes the limit in §Clause X executable instead of asserted |

**"The classes, not the fleet" — an acceptance criterion may not name a population.** The first
drafting of the abstention row read *"the 53 no-`demotion` records, the 21 dormant-with-verdict, the
93 non-empty-`entries`"*, importing the census above straight into the check column. Those numbers are
a **census of the maintainer's stores at a timestamp**, and the one thing this cycle has already
measured about such a fleet is that it **moves** — `docs/record-duty-presence.spec.md` §3.1 records
its own instrument changing 99 → 100 mid-revision, *because its own test suite was running*. A check
that globbed those stores would be non-hermetic (it would pass or fail with whoever's fleet ran it),
unbuildable in CI, and — the sharper objection — **it would be a check on the wrong thing**: the
clauses' obligation is to abstain on the *classes*, and a class is a shape, not fifty-three paths. So
the guard is one synthetic record per class, and the census stays where it belongs, as the §2.6
evidence that the classes are populated in reality. This row is a regression guard rather than a pin
for the reason the paragraph above records, and it is labelled one so its green pre-fix status is not
counted as a RED.

**The substitution's soundness rests on a CLOSURE, and the closure is measured rather than assumed.**
Trading a fleet count for one synthetic record per class is legitimate exactly to the degree that the
class list is **closed** over the shapes the fleet actually holds — a fixture cannot discover an
unenumerated shape, so a class the taxonomy fails to name would be silently uncovered while the guard
stayed green. Re-taking both censuses (2026-09-18, the maintainer's stores, read-only):
**119 raw rows, 104 deduped**, and **zero records fall outside the five rows above** — no record
carries a non-dict `demotion`, and none carries a `demotion` block with `eligible` absent. The counts
themselves have **drifted** since the spec tabulated them — `no demotion` 53 → **58**, `entries
non-empty` 93 → **94**, with the dormant-with-verdict 21 unchanged — which is this finding's point
arriving a second time from a second timestamp: the population moves, the classes do not. Closure is a
property of a fleet **at a timestamp**, so it carries an expiry: **the class list is re-derived
whenever the producer changes**, and the named shape that would re-open it is `demotion` present with
`eligible` **absent** — a shape that exists in no record today, and one the code **already decides**.
`isinstance(el, int) and not isinstance(el, bool)` fails on an absent count, so D and E each
*abstain*; neither reads it as zero. An earlier drafting called this *"a shape clause E's predicate
(`eligible == 0`) does not say how to read"*, which is the reverse of what ships: the narrowing is the
same one the audit counts get, its cost is stated at the predicate, and the abstention is what the
wrong-typed and `bool` arms below already measure (re-measured for this revision — absent, `None`,
`"2"`, `2.5`, `true` and `false` all abstain, while `0` fires E and `2` fires D). So the expiry rests
on the shape becoming **reachable**, not on its semantics being undecided: an absent `eligible` is
silent **by decision**, and the thing to re-derive when the producer changes is the class list rather
than this reading.

**A count that depends on the UNIT is the error this section is about, so the unit is named and the
row is split.** Row 4 was a **conjunction** — *E fires* ∧ *D abstains* — and a suite implementing it
as two checks makes the tally **4 pins / 4 guards**, not 4/3. Rather than leave that as a footnote on
a number a PR body will quote, the row is split below, one row per assertion, so the table's rows and
the suite's checks are one-to-one and either reading gives the same count: the **firing** half is a
pin (the clause does not exist at `e5cce77`, so it cannot fire), the **abstention** half is a guard.
The tally is **four pins and four guards**, and it is reached by splitting the row rather than by
relabelling it — a conjunction whose operands land on opposite sides of the pin/guard line cannot be
labelled without first choosing a unit, and choosing the unit is the move that produced every wrong
count in this document.

**Four pins and four guards, and the dividing line is the check's ASSERTION SHAPE,
not the novelty of its subject.** The general warrant this paragraph first carried was *"a check
whose subject does not exist pre-fix cannot fail on pre-fix code"* — and it is **true only of a check
that asserts ABSTENTION**. A check that asserts **FIRING** fails on pre-fix code for exactly the
reason the warrant gives for passing: the clause is absent at `e5cce77`, so it does not fire, so the
fire-assertion is false. Two rows above were mislabelled by applying the abstention warrant to
fire-assertions — and one of them, the concurrent-writer row, stated both halves in one cell
(*"**fires** clause X | clause X does not exist: **passes**"*) without the contradiction being
noticed. All three counts were in play and **none of them was right**: the heading said one pin, the
paragraph below it said two, and the table's own cells — already carrying two fire-assertion rows
that must fail pre-fix — implied four.

So: **pins** are the two gap-list rows (each asserts a gap the pre-fix list cannot contain, so the
list is short by **two** at `e5cce77` — `_DUTY_CLAUSES` is `session`/`applied`/`trio` there, three
clauses against the six this fix leaves), the E/D
severity-separation row, and the concurrent-writer row — each fails on the pre-fix tree because a
clause it asserts about does not exist yet. **Guards** are the three abstention rows (legitimate
classes, wrong-typed containers, the `SKILL.md` enumeration): those genuinely pass when no clause
exists, which is what makes them guards rather than pins. All four pins read the **same predicate the
persist gate reads** — `duty_gaps` — so none of them is a check on a private reimplementation.

The guards are what keep the new rows from becoming a §2.6 false-positive class, and they are stated
as guards so their green pre-fix status is not miscounted as a pin's RED in the PR's counts. The
distinction is worth stating because it is easy to over-claim **in both directions**: calling a guard
a pin inflates this PR's RED counts with checks that never reddened, and calling a pin a guard
**erases a real RED** — which is the worse error, and the one made twice above.

## Risks and open items

- **RC-3b's release number** — the policy question above. It is the only item here that can move the
  release from patch to minor.
- **RC-1c's `omitted` re-meaning** is a *behavioral* change an operator can observe: a stem that used
  to disappear from the index now stays. That is the fix, but it belongs in the release notes.
- **RC-1a's exit code — resolved, and the resolution is a rule.** The `--diffs` sibling returns `0`
  on its refusal (`:4900`) under a stated reason: *"a diff-capture failure must NEVER crash a dream"*
  (`:4911`). RC-1a's arms are **fabrications**, not skips, so this spec requires non-zero for a named
  fault — and the two are not in conflict once the cases are separated:

  | Case | Frequency | Verdict |
  |---|---|---|
  | `--diffs` cycle unstamped (`:4898`) | routine — a dream that has not been stamped yet | **skip**, notice, exit 0 |
  | `--audit` snapshot path unreadable / absent / invalid JSON | operator error — Phase 0's `--snapshot` was not run, or the path is wrong | **fault**, remedy, non-zero, **no row written** |
  | `--diffs` cycle record unreadable | operator error — the wrong path, or a truncated record | **fault**, remedy, exit 0, keying degraded to the base key (nothing written if a **skip** row also fires) |
  | `--diffs` `before` empty or unreadable, or capture raised (`:4903`, `:4911`) | routine or operator error | **skip**, cause named, exit 0, nothing written |

  The rows are labelled by family because the coordinate alone does not say which arm a row belongs
  to, and the rule they share is the one to carry away: **exit non-zero iff the product the sink
  would emit is a fabrication.** `--audit` with an empty `before` computes every store file as
  `created` — its row *is* the `+572,437 tok` lie — so it refuses. `--diffs`' product, **when the
  run emits one**, is a true diff of real files, so nothing in it is fabricated, and the fault is
  carried by stderr and by the sidecar's key rather than by the exit; the caveat is load-bearing and
  not a hedge, because the row above already conditions the write on no skip firing. Neither family
  exits non-zero
  for a *skip*: there is no product to be wrong about, and on the `--diffs` side the empty-`before`
  arm cannot even reach the write, because `capture_diffs` returns `{}` for an empty snapshot rather
  than fabricate every change as a create.

  The cost is real and worth stating: `SKILL.md:1328` teaches the model that *"a clean pass exits 0;
  THEN continue Phase 5"*, and the shipped `--audit` invocation is a discrete Phase-5 step
  (`SKILL.md:1123`), so a non-zero here **stalls the pass rather than completing it with a bad row**.
  That is the intended trade: a stalled step is recoverable in one command, and a fabricated
  `+572,437 tok` row is permanent and is rendered by every downstream surface.
- **The base key costs MORE than a positional attribution — measured, and deliberately out of this
  fix's scope.** A sidecar keyed `diff_key(marker, "")` names no session, and `read_diffs` resolves it
  anyway: the reader probes `commit__ts__S<session>` first and `commit__ts` second (`:260`) and, on a
  successful load, registers the payload under **every** probed key (`:272-273`). The **key** is
  therefore claimed either way — the claim that the artifact was *orphaned* is what this section's
  first drafting got wrong, and correcting it is why `--diffs` names the fault and **does not
  divert** — it falls through to the write rather than dropping the sidecar, and the skip ladder
  below may still take it. **What that key resolves TO is narrower than the key's existence,
  and each correction here has overshot in a new direction.** Measured 2026-09-18 with the reader's
  `read_text` wrapped: the probe loop's `if key in out … continue` (`:265`) plus the
  register-under-every-probed-key step means the base alias is **rewritten by every cycle that
  loads**, so it ends holding the **last** loader's bytes — not the first's, as this bullet said
  before the instrument went in; and `keys` holds **four** entries (`:260-263`), not the two this
  bullet's first correction assumed. Two cases follow, and the second is where the outcome sentence
  this bullet first wrote went wrong. With **no sessioned sibling** covering the marker, the fault
  arm's own cycle is the only loader: its bytes are read and rendered under that cycle. **With a
  sessioned sibling present**, the sibling's payload takes the alias and whether the base-keyed
  **file is read** then turns on the order, which is why the first correction's "never read at all, in
  either processing order" was itself half wrong. A sibling loading first claims the alias, so the
  fault arm's base probe is skipped as already-in-`out` and the file is never read; the fault arm's
  cycle loading first **does** read it, and the sibling's later load overwrites the result —
  read-then-overwritten, not unread.
  **That dict is an intermediate, though, and this bullet first wrote its OUTCOME from it — a
  different operand from what a dream's modal shows.** The template looks up `commit__ts__S<session>`
  first and `commit__ts` second (`dashboard.template.html:1088`), and the register step writes the
  payload under **every** probed key — a cycle's **own** key among them, whenever that cycle is the
  one that loaded. Measured 2026-09-18 at the consumer, with payloads that name themselves: with one
  sessioned sibling the bytes render correctly **iff the fault cycle carries a session and loads
  first**, **nothing is registered for it** — its own key has no file to read (the write never makes
  one on this path, measured by wrapping `Path.exists` during `read_diffs`) and the base alias its
  fallback reaches is already claimed; where a **session-less** fault cycle loads first its base probe
  is unclaimed, so it does read and register — but every key it registers is one the sibling registers
  too, so the sibling's later load overwrites them all. Either way its modal resolves to the base
  alias — which the sibling's load has taken, and which for a **session-less** cycle *is* its first
  probe rather than a fallback, since `diffKey(marker, "")` returns the base key — so what a reader
  sees is *the sibling's* diff under this cycle. That is **reattribution,
  not shadowing**, and a control isolates the cause, because the write is the obvious suspect: with
  the fault sidecar **absent** the same substitution appears in the sibling-present case, so it is the
  fallback's and not the write's. Writing is therefore never worse than not writing **for the cycle
  that wrote it** — and strictly better in exactly five of the eight cases a session × order × sibling
  enumeration produces: with no sibling covering the marker (four cases: either session, either order)
  it renders this cycle's own diff instead of an **empty modal**, and with a sibling present a
  **sessioned** fault cycle loading first renders its own diff instead of the sibling's. That scope is
  load-bearing rather than hedging: the key is shared, so in the four states where a *covering* cycle
  has no sidecar of its own the write hands **that** cycle this arm's diff instead of an empty modal —
  the same reattribution, here caused by the write and not by the fallback the control isolates. The remaining three show the sibling's diff
  either way — including a session-less cycle loading first, which "loads first" alone predicts as
  strictly better and which measures equal. All of it is a property of the
  reader's legacy fallback — which predates this fix and exists so pre-fix sidecars keep resolving —
  and the fallback's `commit__ts__S<session>`-first probe is what makes the reattribution possible, so
  repairing it means changing the fallback's contract; that is left out deliberately rather than
  worked around silently.
- **Not in this spec, found while measuring it:** `memory_status.py:4867-4868` swallows an `OSError`
  from the mutation-log write with a bare `pass`, so a failed audit row is silently lost — the same
  RC-1 shape (a failure wearing an absence) at a third sink. The approved plan does not carry it;
  recorded here so it is a decision rather than an omission.
- **Not in this spec, and *pre-existing* — `SKILL.md` names a sidecar key shape the normal path never
  writes.** `SKILL.md:1390` documents the sidecar as `dashboards/diffs/<commit>__<timestamp>.json`, but
  `diff_key` appends `__<session>` whenever the cycle record carries one (`:2833`, base-numbered), so
  the key a normal Phase-5 run actually lands is `<commit>__<timestamp>__<session>.json`. The shape the
  doc names is the **fault arm's** key. Pre-existing rather than introduced here — the suffix and its
  own rationale are both present at the base (`:2826-2828`: the suffix exists because two dreams at the
  same head sharing a second *"would clobber each other's sidecar"*) — and it is RC-6's family, so it
  goes to the PR chartered to fix the form rather than being corrected ad hoc inside F1. The
  enumeration in the same paragraph (`SKILL.md:1397-1398`) **is** repaired here, because the arm set it
  describes changed with this fix: a named, non-skipping arm was added beside the two skips, and a
  sentence listing when the command skips no longer describes the command.
- **Not in this spec, and RC-6's family rather than RC-1's — a *pre-existing* count that names no
  revision.** Three sites in `tests/smoke.py` record the v0.4.33 parse-PIN abort as *"705 printed
  checks (704 ✓ + 1 ✗) … 1284 checks never ran"*: the `* TOTALITY.` bullet of the design comment, the
  `F2 — A BOUNDED CAPTURE` comment above the check, and the `v0.4.33 parse PIN (totality)` label
  itself. The parts close exactly (705 + 1284 = **1989**), so none of the three is *wrong* — but no
  site states its total, and the suite this branch ships is **2,104**, so a reader who subtracts the parts from
  today's count gets a contradiction out of three correct numbers — the argument does not need the
  figure to be *right*, only *current*, which is why it is stated as the shipping one. **A second, unresolved discrepancy
  makes the same point from the other side:** the same comment block reports a clean run as *"1987
  passed / 0 failed"*, and the D6 constant's own `passed + failed + 1` puts that revision's total at
  **1988**, one below the 1989 the abort measurement closes to. That gap is a one-check difference
  between two measurements taken at different points of the v0.4.33 cycle — the direction is not
  recoverable from the artifact, since the pin's `+1` and the abort point are both inferred — and it
  cannot be closed from the artifact at all, only by re-running the mutations, which is F2's to do or
  to decline. Held out of **this**
  PR on the same rule the RC-1a `713 + 1341` comment in this branch was repaired under: prose **this
  cycle authored** gets its total named, because unbacked new prose is a surface the diff that
  introduced it owns; pre-existing prose in RC-6's family belongs to the PR chartered to fix the form.
  Measured 2026-09-18 at `e5cce77`: the
  three sites are present on the base (the string `1284 checks never ran` occurs twice, `leaving 1284
  checks unrun` once), so this is a hand-off and not a regression this branch introduced.
- **This document is the largest carrier of the citation form F2.4 is chartered to replace, so the F2
  census has to include it** — otherwise that census repeats, in the other direction, the failure
  §RC-4's own carrier bullet records: *"a carrier census that is short by one is the same defect this
  bullet exists to close."* Measured with **the matcher stated, so the count can be re-run**:
  `[A-Za-z0-9_./-]+\.(py|md|json|html|sh|yml|toml):\d+(-\d+)?` finds **100 explicit `file:line`
  tokens (68 distinct)**, and a backticked `` `:N` ``/`` `:N-M` `` span finds **262 bare** ones that
  inherit their section's subject — **362 across 15 named files**. The totals are *method-dependent
  and revision-dependent*: an earlier matcher, over an earlier revision of this document, returned
  327 for the same two forms. Revision-dependence is structural rather than sloppiness — a census of
  **this** document's citations is invalidated by editing **this** document, which is the same
  self-recording-measurement trap §RC-6 records — so the stable figure to scope F2.4 by is the file
  count, **15** under every matcher tried, while the totals are the method's rather than the
  document's. All are `e5cce77`-bound and therefore resolvable (see the reading note above the Scope
  table), but **this PR edits eight of the fifteen cited files**, so on the branch — and on the merged
  tree — every coordinate into those eight addresses something else. The v0.4.25 rule (*greppable
  anchors, never `file:line`*) is the conversion F2.4 owns, together with the ninth `docs_links`
  contiguity check behind it.

## Verification

```
python3 tests/dashboard_fixture.py --out docs/previews/nocturne   # MUST precede docs_links.py — see below
python3 tests/smoke.py && python3 tests/docs_links.py && python3 tests/simulate_accumulation.py
python3 tests/dashboard_browser.py --out /tmp/cm-browser          # real DOM (CI gate ci.yml:154)
mypy --config-file mypy.ini && python3 tests/validate_manifests.py
```

**The first line is not optional and it is not a nicety.** RC-3 moves one fixture cycle across a rung
(§RC-3, measured), which moves the `_outcome` stamp embedded in the committed preview; `docs_links.py`
byte-compares that artifact (`:427-431`) and `dashboard_browser.py:251` reads the same stamp from it.
Without the regeneration, two CI gates red on a correct fix, and the failure message a reader meets —
*"docs/previews/nocturne/index.html is stale"* — names the artifact rather than the cause. Regenerate,
commit both files under `docs/previews/nocturne/`, and treat the diff in them as part of this change.

Each acceptance check is run against the **pre-fix revision** (`git archive e5cce77`), one process
per tree, and its RED count recorded in the PR — the count belongs to the triple (restored code,
fixture, harness) and is not restated here.

Standing workflow: this spec → adversarial review to zero → `/code-review` → PR.

## Amend ledger

**Revision 1** — first draft, written after the plan was approved and before implementation. Seven
claims were corrected against the tree while writing it: **three from the approved plan** (1–3) and
**four this spec had itself just made** (4–7). They are listed here rather than silently fixed
because **a design-of-record that inherits a wrong number is the defect class this cycle exists to
fix** — and because every one of them was a *claim about the code* that read plausibly and had never
been traced to the line that decides it:

1. the value-flag family is **seven guard sites covering ten flags, of which the hazard set is
   five**. The plan's "eight sites" is wrong, and its blanket "extend the idiom to the value-flag
   family" would have added a parse-time guard to `--justify-demotion`, whose zero-stem case is
   already a usage error with a better message (`run_justify_demotion:2196-2198`).
2. the `before = {}` degradation reaches **two** sinks, but they do **not** behave alike — and the
   first drafting of this item got the direction wrong. `--audit` **fabricates**; `--diffs --before`
   does **not**, because `capture_diffs:2893-2894` refuses an empty snapshot outright and `:4903`
   prints a skip. So RC-1a is `--audit`-specific for *fabrication*, and `--before`'s defect is
   **fault-honesty** instead — a malformed command reported under a remedy naming a different cause.
   The item was written from the two sinks' shared three lines of *parsing* and generalised to their
   *behaviour*; execution falsified it (amend ledger, revision 4 finding 16).
3. the plan listed six outcome pins as moving with RC-3. **None of the six moves; two checks in
   *other* suites red.** The count was wrong in both draftings, in opposite directions, and the third
   time is the measurement: a copy of the pre-fix tree with **only** `:830`'s tuple widened to the
   4-set produced **the same totals line as the pre-fix tree** on the harness then in hand — a
   harness in which **no check distinguished the two trees at all**, so that equality was an absence
   of coverage rather than evidence of agreement. Re-run on the harness this branch ships, the same
   experiment reads **2040 passed / 64 failed** against the unmodified pre-fix tree's **2035 / 69**:
   five checks move, all five are this branch's own RC-3 pins, and the widened matcher's red set is a
   strict subset of the pre-fix one — so the outcome pins the plan named sample the agreement region
   after all. What reds is
   `tests/docs_links.py` (**rc 0 → rc 1**, one failure: *"docs/previews/nocturne/index.html is stale —
   regenerate both with `python3 tests/dashboard_fixture.py --out docs/previews/nocturne"*), and
   `tests/dashboard_browser.py:251` reds for the same reason via the same fixture. The first drafting
   said "none moves" on a count that omitted the fixture's `corrected` row; the second said "two
   move" while naming sites that are **not** among the six. Both were falsified by running the
   fixture on two trees (amend ledger, revision 6 finding 28; revision 7 finding 35).

   Two limits on that measurement — and the **first has since been lifted by measurement while the
   second stands**. The run isolated the **matcher** change, and this paragraph first read that the
   real fix *"also adds the template declaration and the renderer's derivation, whose consequences
   this run cannot see."* A reviewer then rebuilt the fix on the pre-fix tree with **every**
   non-matcher surface §RC-3 describes — `ACTION_VOCAB` with `outcome_of` counting its `True`
   members, `render_dashboard._ACTIONS` derived from the declaration with keys and order preserved,
   the template's single declaration marker with **both** count sites reading it, and `render_html`
   substituting it under its own exactly-once check. Measured, one process per tree:
   `tests/smoke.py` the **same totals line as the pre-fix tree** — read on the harness then in hand,
   in which no check could see the rebuilt surfaces either — and `tests/docs_links.py` **rc 1** with
   the same single staleness failure. So those consequences
   **are** visible, and they are green. The limit narrows from *cannot be seen* to *seen on a
   surrogate build*, and it does not become *removed*: a model of the fix is not the fix, and the
   wider claim is not this paragraph's to make. The second limit **does not stand**:
   `dashboard_browser.py` **ran green: 1336 browser checks passed**, including *every transition
   completed without browser exceptions* and *archives run offline without external requests*, so
   the template's substituted vocabulary is exercised in a real DOM rather than read from
   `tests/dashboard_browser.py:247-251`. §Verification carries the preview regeneration as a
   required step.
4. **`--snooze-until` does not write an empty timestamp.** Its variable is initialized to `None`
   (`:4745`), not `""`, so a failed guard leaves `None` and `:2148`'s `is not None` test suppresses
   the write entirely — a silent no-op, not a corrupt value. The hazard is real; the consequence
   first written here was wrong, and it was caught by reading the parse to its sink rather than by
   reasoning from the neighboring flags.
5. **`--diffs` is a hazard, not an exemption.** The plan and this spec's first draft both treated
   `:4898` as protection; the refusal it belongs to is `:4898-4899` as a pair — the guard on the
   first line, the message on the second — and it is only reached when the state file is *also*
   unstamped, so a `--diffs` given a readable `--before` and an unreadable cycle record writes a
   sidecar keyed `diff_key(marker, "")` (`:4908`) — right content, wrong key. **The instance was
   corrected 2026-09-18, and the correction named the wrong operand**: this item first read *"a bare
   `--diffs` against a stamped store writes …"*, and the repair replaced it with *"a bare `--diffs`
   cannot reach the write at all"* — the same error one layer down. The `--diffs` value does not
   decide whether the write is reached; the **`--before` snapshot** does. With no `--before`, or an
   empty one, the snapshot is empty, `capture_diffs` returns `{}` and the skip fires (measured on the
   pre-fix tree: rc 0, `no before snapshot`, no sidecar written); with a readable `--before` supplied
   elsewhere on the line, a bare `--diffs` **does** reach the write and lands it at the base key —
   the row in §RC-1b's table, reachable from a legal command line. That is finding 16's implication
   seen from the other
   side, and the hazard itself is unchanged. The hazard set went from four to
   five. (The coordinate is quoted as the pair because a review finding asked for it: three sites
   attributed the *message* to `:4898`, which holds the condition, and one of them was this one.)
6. **RC-2 has a third branch.** `:4846 if _ident[0]:` gates the dedup on `commit` alone while `:4852`
   compares `(commit, timestamp)` — so a stamped marker with no commit appends on *every* run. Two
   definitions of identity in three lines, which the recorded docket did not mention.

7. **The renderer's dormant branch does not "legitimately carry no verdict."** This spec asserted
   that as the *reason Clause Y might be unsound*. `render_dashboard.py:878-882` sits at the same
   indentation as `:867`'s `if _de:` — outside the if/else — so the verdict renders in **both**
   branches, and the only reason there is no `else` is that there is no exempt branch. The false
   premise made Y look doubtful when it is the strongest clause in the spec: the duty is mandated at
   `SKILL.md:1073-1074` in almost the words this spec used to justify it.

Corrections 4–7 were each found by tracing a claim to the line that decides it, not by re-reading
the docket — which is the working rule this repo already carries for stored claims, applied here to
a document written minutes earlier. **Four of the seven were corrections to claims this spec itself
had just made**, which is the point: the discipline is not for other people's prose.

**RC-4's drafting, measured rather than argued.** The plan's F1.4 proposed "two more rows in the
existing table" and assumed both were sound. Measurement split them three ways: **X as drafted was
unsound** — its scope conjunct is satisfied by the seed by construction (`:3441`, `:3443`), so it
reduces to a form that fires on two literals pinned as legitimate — and was replaced by an
`audit`-keyed narrowing; **Y as drafted was sound**, and the doubt recorded against it rested on
correction 7; and Y carries a **second class** the draft missed (the dormant mandate at
`SKILL.md:1055`), which is why RC-4 lands three rows rather than two. The one property that separates
the surviving drafting from the failing one is worth naming: **the operand must be one the producer
cannot satisfy by merely having run.** `scope` records what the pass *looked at*; `audit` records
what it *changed*; only the second can witness a duty that is about changing something.

**Revision 2** — RC-4 resolved by measurement (2026-09-17; census reproduced from `main @ e5cce77`),
and four folds from reviewing that measurement back against the artifact:

8. **Clause X's churn caveat was weaker than written, and the stronger-looking fix is worse.** The
   draft hedged that `MEMORY.md` churn is *"expected re-index churn"*. The audit is **content-hash**
   based, so a hash-equal file is *not an op at all* (`:2791`, `:2798`) — a `MEMORY.md` entry in
   `operations` means its bytes actually changed, which owes a row. Meanwhile the narrower predicate
   that restricting the scan to non-`MEMORY.md` paths would permit (1/99, same fire count) **introduces
   a false negative** on pointer-only reconciliations. Both the caveat and the alternative were
   corrected against the operand's own semantics rather than a judgment call.
9. Three fidelity fixes, each because this repo treats quotes and dates as evidence: the `:1053-1056`
   quote now carries ellipses for its elisions; the census date reads `2026-09-17` to match
   `docs/record-duty-presence.spec.md`'s clock for the same fleet rather than reading as a one-day
   drift; and "two literals pinned as legitimate" became "two literals the suite pins to `NO-OP PASS`",
   since the pin asserts a label `outcome_of` computes *from* `entries` — reading it as independent
   blessing re-imports the circularity the clause is about.
10. **The Empty-set rule is support for D/E, not an excuse for an empty `entries[]`.** The superseded
   drafting cited it as licence for an empty `entries[]`. `SKILL.md:215` lists `demotion.eligible == 0`
   among its empty **detector sets** and `:217-218` requires the one-liner regardless, so the rule
   routes the judgment to a **block verdict** — it never mentions `entries[]`. Citing it backwards was
   the last surviving trace of the original, and it is now stated the right way round.

**Revision 3** — the adversarial design review folded to zero (2026-09-17). Every finding was
**re-verified here before being accepted**, and two were re-scoped by that verification: one narrowed
(the review's stated consequence is not reachable), one widened (a site the review did not name). A
fifth item was found while testing the other four.

11. **Clause X's predicate raised on a JSON-reachable record.** Reproduced on the drafting exactly as
    written: `{"entries": [], "audit": {"memory": t}}` raises `AttributeError` for `t` in
    `"not a dict"`, `["a"]`, `5`, and `true`. The mechanism is that `(a.get(s) or {})` guards against
    *falsiness*, not *wrong type* — so `0` / `""` / `[]` / `null` / `{}` are replaced and every
    **truthy non-dict** reaches `.get`. `true` is the sharpest case: JSON `true` is a Python `bool`,
    and `bool` is an `int` subclass, so it survives a naive `isinstance(..., int)` reading. Verified
    against the family's own practice (`:4156`, `:4178-4179`, `_duty_blank:4151`), its stated
    contract (`:4204-4206`, *"never raises **ON JSON-REACHABLE INPUT**"*, itself measured — *"3 of 23
    hostile inputs"*), and the sibling type-abstention pin at `tests/smoke.py:3382`. Fixed, and the
    fix additionally took the neighbouring `not isinstance(..., bool)` idiom from `:3532`, so a
    forged `{"created": true}` cannot fire an alert.
12. **The template holds TWO count sites, and the fix would have desynchronized the second.** The
    census counted **files** where the defect lives in **matchers**: `:1045`'s `writeCount` matches
    the 3-set precisely *because it mirrors `outcome_of`*, so a one-read-per-file census finds the
    template's correct site and misses its incorrect one — this spec's own defect class, one level
    up. The review raised the site; its stated consequence (**a live mis-render**) is **not
    reachable**, and that was checked rather than repeated: `_embed_integrity`
    (`render_html.py:214-216`) stamps `_outcome` on every cycle, every `outcome_of` return path is
    non-empty (`:828` is `str(x).upper()` on a value already tested truthy; the rest are literals),
    and every browser fixture goes through `rh.build_html`, so the ladder never executes. The real
    consequence is sharper: leaving `:1045` alone would make this fix **create** the divergence it
    exists to remove. The acceptance is therefore a **structural** pin with its blind spot stated,
    not a behavioural one over unreachable JS.
13. **The exactly-once assertion this draft appealed to cannot cover the new marker.** Confirmed by
    reading: `render_html.py:40`'s check sits **inside** the `_BUNDLES` loop, whose values are
    **filenames** read at `:37` — a marker replaced by a JSON literal has no file and cannot be a
    member. The mechanism is now specified with its own check beside that loop; and the reason the
    marker must occur exactly **once** is that `tests/smoke.py:13025` calls `_load_template()`
    **unguarded**, so a count of two raises `ValueError` **out of the suite** — no totals line —
    instead of failing a check. The single-declaration form is what keeps the count at one.
14. **RC-4's new rows contradict two shipped `SKILL.md` statements the draft never listed for
    update.** Confirmed: the enumeration at `:1345-1352` goes **false by omission**, and the family
    rule at `:1342-1343` (*"never an absent key"*) goes **false as a universal** for clause E, which
    fires on an absent key inside a present block. Both are now in the Change section, with the rule
    qualified to *"an absent **block** never fires"* — which is what it was always about.
15. **Three comments state the clause count as a fact, and RC-4 falsifies each.** Not raised by the
    review; found by following the count the new rows move. `tests/smoke.py:3507`, `:3612`, and
    `docs/record-duty-presence.spec.md:1381` all read *"the number is the rows drawn, and
    `_DUTY_CLAUSES` is three"* — and the first two are the **stated reason** a `\d{1,4}` capture
    bound cannot reject a legitimate render. The bound survives at six rows; its stated reason does
    not. Repaired by stating the **bound** instead of the **size**, which is drift-proof by
    construction rather than by monitoring. The third site is an **amend ledger** — a dated record of
    a past revision — and is deliberately left as written; editing a historical entry to match
    today's tree would falsify the record it exists to keep.

**Findings 11–14 are one shape, and so is 15 one level out.** Each is *a claim about a container,
checked against the container rather than its members*: 11 checked `audit`, 12 and 13 the template
file, 14 `_DUTY_CLAUSES`. 15 is the same move applied to a claim about a **count** — checked against
the table rather than against its readers. That the review's four findings and this pass's fifth are
the same shape is the useful part: the censuses in this document are what keep failing this way, and
each now names the unit it counts. It is also why the review's own two mis-scoped findings were
cheap to correct — re-scoping a claim is only possible if the claim names its operand, so a reviewer
citing `file:line` throughout made both directions of the correction available.

**Revision 4** — the execution review's findings folded (2026-09-17). This revision differs in kind
from 1–3: those corrected claims against a **reading** of the tree, this one against a **run** of it.
One finding falsified a claim in three places, and it is the reason the method exists.

16. **`--before` does not fabricate, and `capture_diffs` says so in its own comment.** The claim —
    in the §RC-1b hazard table, in amendment 2 below, and in §RC-1a's "Current" as *"`audit_diff`
    **and** `capture_diffs` read it as an empty store"* — was that both sinks degrade identically.
    `capture_diffs:2893-2898` refuses an empty snapshot outright, naming the defect it declines to
    commit (*"return empty rather than fabricate every change as a whole-file 'created' (the
    render-chain audit measured exactly that lie)"*), and the sink's `if not diffs and not before:`
    (`:4903`) prints a skip instead. Measured pre-fix: `--diffs --before` bare, and
    `--diffs … --before <nonexistent>`, both exit 0 with the skip message and **write no sidecar**.
    Three sites, one wrong claim, and it failed the way family resemblance always fails — the sinks
    share three lines of parsing, so the second sink's *behaviour* was inferred from the first's
    rather than read.
17. **RC-1a is therefore a completion, not a new rule**, and the corrected framing is stronger than
    the wrong one: the repo repaired this class once already, at one of two identical sites. That is
    **the same asymmetry — an invariant only as strong as its weakest enforcement site** — now cited
    as the justification rather than met as an embarrassment. `--before` stays in the hazard set on different grounds — a bare `--before` makes
    `--diffs` print *"Phase 0 `--snapshot` wasn't run"*, so a malformed command is reported under a
    remedy naming a **different cause**. A fault-honesty defect, not a fabrication.
18. **The `audit` operand is unforgeable but not attributable, and D4 is right that only one of the
    two had been established.** `SKILL.md:1134-1136` documents the window-attribution gap in the
    tree's own words, so a Phase-1 `--pull`, a concurrent `cm sync`, or a mid-dream commit lands
    store bytes the pass never decided. The predicate is **not** changed — the state reported is
    true, and SKILL already calls that conjunction *"a signal to investigate"*. What changes is the
    clause's **`remedy` string**, which now names both causes instead of instructing a row possibly
    owed by nobody. The census limit is stated in place: 99 single-writer records cannot contain the
    class, so 1/99 measures the audited-defect case only. D4 came back LOW and *"inherited, not
    introduced"*; this fold agrees on severity and disagrees on disposition — an inherited limit that
    a new clause newly gates is the new clause's to state.
19. **`skills/consolidate-memory/SKILL.md:64-66`'s enumeration is a dated changelog entry, not a
    current contract** — the
    review raised it as a second gap, and the correct disposition is the *opposite* of the first.
    `:60` opens *"the v0.4.33 record-duty-presence patch"*, so a later patch adding clauses does not
    falsify a sentence about an earlier one, and that paragraph grows by appending its own version
    entry — which RC-4 does. Left as written, with the distinguishing rule stated so the next author
    meets the reason rather than a bare omission. Same rule, same reasoning, as amendment 15's site.

**The two rounds found different things because they did different work.** The design review read
the spec against the tree and found four *structural* errors — containers checked against themselves.
The execution review ran the spec against a hermetic pre-fix tree and found one *behavioural* error
no amount of reading would have caught, because the wrong claim was about a function's behaviour
under a condition the reader never varied. Both were necessary, neither substitutes for the other,
and the falsification in 16 is the round's most valuable return precisely because it removed a false
claim rather than adding a true one.

**Revision 5** — the re-verification round folded (2026-09-17). Both reviewers re-checked their own
findings against the amended text and brought back **executed** results; every measurement below was
verified against the tree by this author before folding. What was found wrong in this pass was the
**warrant** rather than the claim — a more dangerous error, because a weak warrant reads exactly like
a strong one.

> **Correction, added by revision 6: the sentence that stood here claimed the *claims* of revisions
> 1–4 were "not found wrong" this time. That sentence was itself an overgeneralization from an
> incomplete sample — three reviewers had reported, the fourth had not, and the fourth found a false
> claim.** It is the same error shape as revision 5's own finding 27 (a premise checked against a
> representative member and generalized to the set), committed in the entry that records it. Left
> visible rather than edited away, because the recurrence is the instruction.

20. **My census argument rested on a premise that does not carry it.** §RC-4 argued that the
    container guard cannot move the 1/99 count *because the census ran to completion over all 99*.
    A reviewer attacked the premise and was right: a sweep that **tolerated** a raise would report a
    raising record as *no fire* and complete anyway, so completion is silent on precisely the class
    the guard addresses. The conclusion survives on a stronger basis — `isinstance(blk, dict)` is
    **monotonic** over the old predicate, returning the same value on every input where the old form
    had a defined value — and the amended text carries that instead. The old argument was not false,
    it was **non-load-bearing**, and the difference is invisible until someone tests the premise.
21. **…and the same paragraph silently claimed a second change it does not cover.**
    `not isinstance(v, bool)` is not a guard but a **narrowing of the fire-set** — `{"created":
    true}` fires pre-fix and abstains post-fix — so no argument about raising speaks to it. The
    census reading 1/99 now rests on a **producer** fact, verified here rather than taken:
    `audit_snapshot` builds the rollup as a fresh literal of `int` zeros (`:2771`), touches it only
    through `+= 1` (`:2800`) and `+= delta` (`:2801`), and returns it directly (`:2815`); it is never
    seeded from or re-read out of parsed JSON. The house idiom at `:3531-3534` pairs guard with
    producer in one breath — *"the producer never writes one"* — and the fold adopts that pairing.
22. **A citation named one line of a three-line comment.** The `bool` idiom is reasoning at
    `:3531-3533` with its code at `:3534`; the spec cited `:3532`. Corrected in both places. Minor,
    recorded because the same "a citation must name the thing a reader should open" rule caught a
    real error last revision and the nit is the same rule at low stakes.
23. **§RC-3's acceptance table disagreed with its own prose.** The prose states that the `:840`
    guard short-circuits the ladder before any count runs, so `{skipped: 3}` at `reviewed: 0` returns
    `NOTHING TO CONSOLIDATE` — **measured**, and not `NO-OP PASS`. The table listed the label without
    the qualifier, so a reader taking the table alone would build a `reviewed: 0` fixture and measure
    the wrong banner. The table now states its fixtures hold `reviewed ≥ 1`, carries the `reviewed: 0`
    row explicitly, and labels that row a **regression guard** — identical on both revisions by
    construction, because a check added by a fix may not fail on pre-fix code. This is this spec's own
    defect class one level up: a summary produced at a coarser grain than the data it summarizes.
24. **The single declaration has an ordering constraint the pin cannot see.** Verified structurally:
    both count sites share one `<script>` (`:925-1637`) and one IIFE (`:927`–`:1636`), so one
    IIFE-level `var` is in scope for each. But `var` hoists the binding, not the value, and
    `outcomeOf` is first **called** at `:1177` — so the declaration must be **assigned before
    `:1176`**, naturally among the IIFE-level declarations at `:928-936` (whose `:936` already uses
    the comma-`var` idiom). The plain-text substitution pin stays green on a mis-placed declaration
    — and so does every other check. This entry originally offered the browser fixtures as the second
    guardian; a reviewer refuted that by measurement (the declaration moved below `showArchive()`'s
    closing brace: **1336 browser checks passed**, rc 0, no `FAIL` line), and the reason is
    structural — the rows-build that reads the declaration runs only inside the **lazy**
    `showArchive()`, called from one site, so no IIFE-level placement can precede it. The ordering is
    covered by no check, and needs none, because nothing executes the ladder.
25. **Two acceptance rows were proposals; the reviewers made them reproductions.** RC-1c's
    firewall fixture was built and executed pre-fix — the arm tripped on **ordinary prose** in a fact
    valid in every other respect, the plan reported `would_remove_existing_pointers: ["sec-probe"]`,
    and the apply under `--skip-invalid` returned **`ok: true`** while de-indexing it. That last
    detail is now recorded because it raises the severity: the loss is reported as success, not
    merely unreported. RC-2's empty-commit arm was likewise driven through the real CLI on an
    **unborn-HEAD** repo (`{"ok": true}` → `{"commit": "", …}`, three runs → three rows), with the
    mechanism confirmed structurally: `_valid_sha` (`:925-931`) rejects `""`, so `reconcile_marker`
    (`:2159`) leaves it empty and `:4846 if _ident[0]:` skips the guard. RC-1a's three arms were
    shown **byte-identical** with empty stderr and exit 0 — I had written "cannot be distinguished";
    the measurement is that there is no byte to compare.
26. **The RC-4 clause split is now carried in the artifact.** A reviewer's D4 found the clause's
    severity LOW and *"inherited, not introduced"*; the fold agrees on severity and disagrees on
    disposition — an inherited limit that a new clause newly gates is the new clause's to state — and
    the `remedy` string now names both causes instead of instructing a row possibly owed by nobody.
27. **RC-1c's root cause is one word wide, and it is the arm's own stated premise.** Chasing the
    missing artifact (the physical index diff, which the report had truncated before) led past the
    reproduction to *why* the false positive is reachable. The bare-leading-dash alternative
    (`:1097`) justifies itself in its comment: *"a leading `-`/`--` is the signal — **ordinary prose
    essentially never spells "-password"**"* — a premise checked against a representative member of
    its keyword list and **generalised to the set**. It holds for `password` and fails for `pass`,
    which is also an ordinary English noun and this skill's central term; minimal pairs varying only
    the following word show the discriminator is the arm's own value gate
    (`(?=\S{8,}|(?=\S{4,})\S*\d)`, `:1097`), calibrated against credentials and therefore sitting
    exactly where English words are densest. The arm's comment records an earlier false positive from
    this same arm (`--secret flag …` → "flag", `:1115-1116`) fixed by that gate — so the gate closed
    the short side and left the long side open. Measured: `per-pass`, `cross-pass`, `post-pass`,
    `pre-pass` all fire. This is the deepest root cause in the document and it was found only by
    finishing the measurement instead of accepting the report.

**What revision 5's error kind was.** Revisions 1–3 had wrong claims; revision 4 had one wrong claim
falsified by execution. Revision 5 had **true claims with weak warrants**, and the failure mode is
specific: a warrant is written to persuade, so it is selected for *plausibility* while a claim is
selected for *truth*, and nothing in a re-reading distinguishes a premise that carries the argument
from one that merely accompanies it. The remedy is the one that caught it — **attack the premise**,
not the conclusion; the conclusion survived, and the argument did not.

**Revision 6** — the pin review's finding folded (2026-09-18). The last of four reviewers reported
after revision 5 was written, and it **falsified a claim** — which is the third error kind in this
ledger's sequence (wrong claim → weak warrant → wrong claim again), and it falsified revision 5's own
sentence that no claim had been found wrong. Verified here rather than taken: the fixture was run on
both revisions and the gates re-read.

28. **"No existing check can discriminate this defect" was false, and the true statement is
    stronger.** §RC-3 argued that every existing pin samples the agreement region, so the defect
    survived four release cycles because it was found by reading rather than by a red gate. In fact
    **one check samples the disagreement region exactly**: `tests/dashboard_fixture.py`'s cycle 7,
    whose entries are `added, reconciled, corrected, skipped`. The 3-set count is **2** — `added` +
    `corrected` — not 1: an earlier drafting counted only the spliced `added` row and its
    `reconciled` copy and omitted the `corrected` row the fixture carries in **every** cycle, so it
    read `1 → 2` ("both `LIGHT PASS`") where the measurement is `2 → 3`. Cycle 7 therefore sits on
    `writes <= 2` and **straddles the rung**: `LIGHT PASS` pre-fix, `SUBSTANTIAL PASS` post-fix.
    Measured across all eight cycles, one process per tree. The corrected conclusion is the inverse
    and the better one: the defect survived **because the one check that samples it records the
    pre-fix label as the expected value** — green before the fix, red after. **A pin can encode the
    defect it exists to catch**, at fixture scale, and it is a materially
    different fact about why this class of defect persists.
29. **Two CI gates red on a correct fix, and neither is in `tests/smoke.py`.** `_embed_integrity`
    (`render_html.py:214-216`) stamps cycle 7's outcome into the built payload, so
    `tests/dashboard_browser.py:251` (reads `#sel=7`'s summary, `:247`) and `tests/docs_links.py:427-431`
    (byte-compares a fresh render against the committed `docs/previews/nocturne/`, whose `index.html`
    carries exactly one `LIGHT PASS` as that stamp) both fail. The spec's §Verification *runs*
    `docs_links.py` and previously never mentioned the artifact, so a correct fix would have met two
    red gates whose message — *"docs/previews/nocturne/index.html is stale"* — names the artifact
    rather than the cause. §Verification now leads with the regeneration command and says why.
30. **RC-1b's own fix was reachable-around, found by the re-verification.** The reviewer noted in
    passing that a trailing bare duplicate (`--diffs X --before <valid> --before`) writes its sidecar
    silently; verified here — the parse is `argv.index(_f)` (`:4670`, plus eight further sites), so
    the first occurrence wins and later ones are ignored. A guard written against `argv.index`, as
    the spec's own pseudocode was, would leave the reported defect reachable through a legal command
    line. The guard now iterates every occurrence, and the acceptance table gains a pin that reds
    both the pre-fix tree **and** a plausible-but-wrong fix.

**What revision 6's error was, and why it is the most instructive one here.** The reviewer that
caught it was the one that reported last, and the claim it falsified was a **negative claim about
coverage** — *"no existing check can discriminate this"* — which is the class of claim this repo's own
memory names: *a pin's coverage is the VALUES it samples and the CALL PATH it takes*, and a negative
coverage claim is a **census**, not an observation. Revisions 1–4's errors were about code that was
read; this one was about code that was **counted**, and the count was off by a row that was present in
every sample. The lesson is the one the repo already writes down and this entry re-learns: a census
stated as a conclusion must name the unit it counted and the population it counted over, because
*"every existing pin samples the agreement region"* is only as good as the arithmetic inside it.

**Revision 7** — the pin review's **second** report folded (2026-09-18). The same reviewer that
produced revision 6 continued on the revised text and found two more, both verified here by
measurement before folding: the ladder fixtures were run on the pre-fix tree and on a copy with only
`:830`'s tuple widened — the fix does not exist yet, so a post-fix column cannot be read off any tree
that ships, and one process per tree was used for each.

31. **§RC-3's `reviewed: 0` warrant was false about the guard's own control flow.** It read: *the
    `:840` guard short-circuits the ladder **before any count runs**, so no fixture in that region can
    pin RC-3.* `:840` is `if writes == 0 and candidates == 0 and git == 0 and reviewed == 0:` — its
    **first conjunct is `writes`**, and `writes` is computed at `:830`, **ten lines** above the guard
    (the drafting said five — an arithmetic error in the sentence correcting an arithmetic error).
    The guard
    does not precede the count; it **consumes** it, so whether it fires depends on the matcher like
    every rung below it. Measured counterexample: `{reconciled: 1}` at `reviewed: 0, candidates: 0,
    git: 0` → `NOTHING TO CONSOLIDATE` pre-fix → `LIGHT PASS` post-fix — **a pin, in the region the
    spec had declared unpinnable.** The real reason `{skipped: 3}` happens to behave as the false
    warrant predicted is unrelated: `skipped` is in **neither** write-set (neither the 3 nor the 4),
    so its count is 0 under both matchers — a fact about the **action name**, not about the guard. The
    table also gained the reading-dependence the single-valued column had hidden: the same
    `{reconciled: 1}` reads `NOTHING TO CONSOLIDATE` at all-zero and `NO-OP PASS` with non-zero
    `candidates`/`git`, both measured pre-fix — while remaining a **pin at both readings**. Which
    one a fixture is turns on its ACTIONS (`skipped` is in neither write-set), not on the other three
    counts; an earlier drafting of this bullet said otherwise and handed `{reconciled: 1}`'s sentence
    to `{skipped: 3}`, describing a moving pin as stable. The
    rule put in its place took **three versions** (finding 38).
32. **§RC-4's pin/guard split contradicted itself, and the warrant that produced it was
    over-general.** The heading claimed *"only one of the three is a pin"* while the paragraph below
    it said *"the two genuine pins are the first two rows"*; neither matched the table, whose own
    cells already showed fire-assertions failing pre-fix. The cause is a warrant stated without a
    domain: *"a check whose subject does not exist pre-fix cannot fail on pre-fix code"* is **true
    only of a check that asserts ABSTENTION**. A check that asserts **FIRING** fails on pre-fix code
    for exactly the reason the warrant gave for passing — the clause is absent, so the
    fire-assertion is false. Applying the abstention warrant to fire-assertions mislabelled two rows,
    one of which stated both halves in a single cell (*"**fires** clause X | clause X does not exist:
    **passes**"*) without the contradiction being noticed across three revisions. Corrected by
    measurement: **four pins and four guards** (the table's own eight rows), and the miscount ran in
    the direction this repo's rule
    warns about — a pin mislabelled a guard **erases a real RED**, which is worse than inflating one.
33. **A falsified coverage claim survived revision 6 outside the section it was fixed in.** Finding
    28 corrected §RC-3's coverage story, but the identical claim stood unamended in the header's
    rule-of-engagement bullets — *"this is true of **every** existing outcome pin — which is why RC-3
    survived to be found by reading rather than by a red gate"*. Both halves are false and the truth
    is the inverse. **A repair is only as wide as the census of sites carrying the claim**, and here
    the site that needed it most was the one stating the rule the repair was made under.
34. **This document is itself a scanned artifact, and the repo's own gate caught what the author did
    not.** §Provenance quoted the plan's path with the maintainer's real home directory. The
    genericity pin (`tests/smoke.py:5196-5206`) scans `docs/**.md` and reddened the suite. Nothing in
    the review rounds had flagged it, because a reviewer reads a spec for *claims about the code* and
    this was a claim about *the author's filesystem* — the one kind of text a public repo's own gate
    is built to catch and a review is not. Genericity is checked by the harness, not by the reviewer,
    which is the division of labour working as designed; recorded here because the fix was a gate
    RED rather than a review finding, and future revisions of this file are subject to the same.
35. **The pin-count correction of revision 6 was itself uncounted, and the measurement inverts it
    again.** Finding 28 fixed the fixture's arithmetic but left §Risks item 3 asserting *"Two move,
    not none and not six"* — a **count of which pins move**, offered with the same confidence as the
    miscount it replaced, and never measured. Running the suite settles it: a copy of the pre-fix
    tree with only `:830`'s tuple widened to the 4-set gives `tests/smoke.py` **2040 passed / 64
    failed** against the unmodified tree's **2035 / 69** on the harness this branch ships — the five
    movers all being this branch's own RC-3 pins, and the widened matcher's red set a strict subset
    of the pre-fix one — so **none** of the six smoke pins the plan named moves;
    `tests/docs_links.py` goes **rc 0 → rc 1** with the one staleness failure; `dashboard_browser.py`,
    read rather than run for that measurement, has since run **green at 1336 checks**. So the plan was
    wrong in one direction, revision 6
    corrected it into a *different* wrong direction, and only execution produced the answer. This is
    the ledger's fourth error kind — not a wrong claim, a weak warrant, or a miscount, but a
    **correction that inherited the form of the error it replaced**: the shape *"N move, not none and
    not six"* reads like a measurement and is a guess with a number in it. The prompt that would have
    caught it is the one this repo already applies to fixes — *a count belongs to the triple* — and
    the spec applied it to the RED counts it owed implementation while exempting the one count it had
    already written.

36. **An acceptance criterion named a population instead of a class.** §RC-4's abstention row read
    *"the 53 no-`demotion` records, the 21 dormant-with-verdict, the 93 non-empty-`entries`"* —
    the revision-2 census copied straight into the check column. Those figures are a **fleet at a
    timestamp**, and the prior spec already records that fleet moving 99 → 100 mid-revision because
    its own suite was running (`docs/record-duty-presence.spec.md` §3.1). A check globbing those
    stores would be non-hermetic, unbuildable in CI, and a check on the wrong thing: the clauses owe
    abstention on **classes**, and a class is a shape, not fifty-three paths. The row now specifies
    one synthetic record per class and the census stays as §2.6 evidence that the classes are
    populated. Found while asking the census's *provenance* tier — not by review, and not by running
    anything.
37. **§RC-3's six-site matcher census was re-taken mechanically, and it holds — but the re-take is
    itself the lesson.** Independently re-derived for revision 7, the census returns the same six
    sites at the same matchers. What it also showed is how a census of this kind under-reports: **the
    unit is the matcher, and matchers are found by SPELLING.** `tests/dashboard_browser.py:423`
    writes its 4-set with single quotes where the template's two sites use double, so a sweep keyed
    on one spelling reports five and silently drops the independent agreement that is the 4-set's
    strongest evidence. This is finding 35's shape one level down — a count whose *method* was never
    stated, so its width was never checkable — and it is the second count in this revision that
    survived several review rounds because it looked like a table rather than like an arithmetic.
    The same under-report has a third instance with no spelling to key on at all: the pooled sections
    bundle's `decisions()` counts `String(e.action)` and names no action, so the unit reaches it and
    no sweep can — §RC-3's body states it now, and the re-take above is what missed it.

38. **The discriminating rule took three versions and the first two were wrong — which is the
    answer to the question revision 7 asked its reviewer.** The revision-7 drafting wrote *"a fixture
    discriminates exactly when its reconciliation count straddles the `writes == 0` boundary"*. The
    reviewer falsified it by sampling 24 cells: 9 flip **without** straddling that boundary, and the
    two most important are the section's own row 2 and cycle 7 — which cross the `writes <= 2` rung at
    `:844` instead. The reviewer's replacement, `r ≥ 1 and (w3 == 0 or w3 + r ≥ 3)`, was then
    grid-tested here rather than adopted: **16 of 109 cells violate it**, all at `w3 ≥ 3`, where both
    revisions are already `SUBSTANTIAL` and nothing moves however large `r` is. The third form —
    `r ≥ 1 and w3 ≤ 2 and (w3 == 0 or w3 + r ≥ 3)`, with the `outcome` override excluded — predicts
    all 27 moving cells and no others **on a grid sampling absence and truth but never
    present-and-falsy** — the blind spot §RC-3's 354-cell grid exists to close. So a rule about *which
    counts move* was itself a wrong count **twice**, and only a grid found it.
39. **I asked whether the seven findings were independent or one defect counted several ways, and the
    answer is "both" — but the merge I made of two of them was itself a count reached by grouping.**
    Five are independent (§RC-3's warrant, §RC-4's split, the header's surviving claim, the genericity
    path, the non-executable acceptance row). I then wrote that **33 and 35 are one defect**, and a
    reviewer falsified that with this repo's own test: *two findings are one defect iff ONE repair
    closes both.* 33's repair is the header bullets; 35's is §Risks item 3; neither closes the other.
    They share a **cause** — revision 6's fold did not reach its twin sites — and a cause is not a
    defect, because a ledger's unit is a finding-with-a-repair. Note the direction, since it is the
    same error shape as splitting a conjunction: **merging is a count too.** So: **seven independent
    findings**, of which **37 is a verification rather than a defect** (the census held; what it
    produced was a method caution, which belongs in §RC-3 where it now sits). Findings 38 and 39 are
    themselves the loop's evidence: 38 is finding 35's shape *inside the fold for finding 35*, and the
    corrections of §RC-3's warrant introduced **three** further number errors — *"five lines earlier"*
    for ten, *"shorter by an entry"* where `_DUTY_CLAUSES` is three clauses against six, and a relayed
    `<slug>` fix that was described before it was written. **Those three are quoted rather than cited
    by line number, and that is finding 40's own repair applied to this entry**: they were measured at
    `69bb3981`, and at the live revision their coordinates resolve to unrelated text — the third
    clause in particular read as *a fix is missing* when the fix is present and the suite green.
    Net: **seven genuine findings (31–37)** — the ledger is not inflated, but its growth rate is, and
    the reason is that every fold of a count-claim is itself written as a count-claim.

**What revision 7's error was.** Findings 31 and 32 are about **code two lines from text the section
had already quoted**: the census at the top of §RC-3 tabulates `:830`'s matcher, and the same section
then described `:840` as running *before* it. Both were written by pattern-matching on a recalled
shape — *a guard that gates a ladder must run first*, *a check for a thing that does not exist cannot
fail* — rather than by reading the guard or the check. The prompt that catches them is not a second
reading but a mechanical one: **substitute the numbers into every clause of a warrant that mentions a
specific line, and confirm the line's own text admits the direction claimed.** A warrant asserting
*order* is falsifiable by reading two lines; a warrant asserting *domain* is falsifiable by reading
one clause's assertion shape. Neither needed a tree.

**The revision's seven findings split by what caught them, and the split is the useful result.**
Exactly **two** (31, 32) were reachable by reading the text they were about. The other five each
required something to be *done*: a site census (33), the test suite (34), two trees run (35), a
provenance question asked of a number's tier (36), and a mechanical sweep for matchers (37). Four of
the five are **counts** — **of sites (33), of pins (35), of records (36), of matchers (37)**; the
fifth (34) is a gate reddening, an event rather than a count. Every one of the four had been
written in the confident register this document uses for measurement, in a document whose subject is
miscounting. The lesson is narrower than "verify more": **a count in prose reads as a measurement
whatever its provenance, so the only defence is that a count must name the method that produced it**
— the population, the unit, and the tree. Findings 35 and 37 are each a count that survived several
review rounds precisely because a table or a phrase makes a number look already-checked. **The
document was most wrong exactly where it sounded most measured.**

**The split classifies the defect, not its repair — and that distinction is where the loop's length
came from.** Finding 31 *is* a warrant about order, falsifiable by reading two lines, so the
paragraph above is right about it. But finding 31's **repair** — *"discriminates exactly when its
reconciliation count straddles the `writes == 0` boundary"* — was a count-shaped universal offered in
the same confident register, and it is **false on the section's own table**: `{added: 2,
reconciled: 1}` holds no straddle and moves. It survived until a grid falsified it (finding 38). So
the durable form of this lesson is not *"a direction error is cheap to catch"* but: **a repair
inherits none of the diagnosis of the defect it repairs.** A repaired claim is a **new** claim with
its own provenance, owed the same three things the original was denied — the population, the unit,
and the tree. Here the original was caught by reading and its replacement needed execution, which is
why one rule took three versions and only a 109-cell grid ended it.

**Revision 8** — the pin review's **final, narrowly-scoped** round folded (2026-09-18). The reviewer
was asked to verify three specific items and to report "clean" and stop otherwise; it returned four,
of which one was new and survived, two were already folded, and one was a method observation.

40. **A peer's findings arrived bound to a revision that no longer existed, and all three of its
    "still live" items were already folded.** The report was measured against **1431 lines /
    `69bb3981`** — a mid-batch revision from inside revision 7's own fold — while the live document
    was **1539 / `6d6be411`**. Its three live items were `:7`'s plan slug, `:612`'s "five lines
    earlier", and `:629`'s straddle rule; all three had been folded *after* that snapshot, and the
    live file reads `<slug>`, "ten lines above", and the arm-transition rule (§RC-3, finding 38
    above). The hazard is not the reviewer's — it can only measure what it reads, and it named the
    hash it read, which is precisely what made the mapping possible. It is that **a line number is
    not a handle**: one coordinate addresses different text in different revisions, so a finding is
    re-run against the live revision before it is acted on. This is the repo's own recorded rule —
    *a peer finding is bound to the revision its hashes name* — firing in the field, and it fired in
    the benign direction: three findings already closed, none wrongly re-folded.
41. **§Risks item 3's third error is in the opposite direction from its first two: it understated
    the measurement.** The paragraph read that the declaration surfaces' consequences *"this run
    cannot see."* A reviewer rebuilt them on the pre-fix tree and measured **`smoke.py` the same
    totals line as the pre-fix tree** — read on the harness then in hand, where no check could see
    the rebuilt surfaces — and **`docs_links.py` rc 1**, the same single failure — so the claim was
    *conservative*, and
    conservative in the same shape as its predecessors: an **unmeasured assertion about a
    measurement**, written in the register of one that had been made. That item has now been wrong
    three times — "none moves" on a count that omitted the fixture's `corrected` row (28), "two
    move" naming sites outside the six (35), and "cannot be seen" where it can be (41) — and the
    three share one defect rather than being three: **the claim about a measurement was never itself
    measured.** The fold keeps the limit as *seen on a surrogate* rather than deleting it, because
    the reviewer's tree models the fix and is not the fix.
42. **The closing classification was about the defect and not about its repair.** The paragraph
    splitting the seven findings by what caught them puts finding 31 — a warrant about **order** —
    in the reading-catches-it column, and it belongs there. But finding 31's *repair* was itself a
    count-shaped universal in the same confident register, false on the section's own table
    (`{added: 2, reconciled: 1}`), and it stood until a grid falsified it. So the split is right
    about defects and **silent about repairs**, and the silence is where the loop's length lived.
    Recorded rather than re-litigated: the general form is now a paragraph in the closing section,
    and it is this revision's one lesson about method rather than about this document.
43. **The fold for finding 37 contained another instance of finding 37's shape.** The sensitivity
    paragraph added under §RC-3 asserted the fix has *"no source-form pin of its own to trip"*, and
    the census behind that sentence was **single-spelling and single-file** while the sentence read
    suite-wide. Re-taken properly — both quote spellings, all of `tests/` and `plugins/` — the claim's
    true scope is the narrow and useful one (**zero** in `smoke.py`, the gate that matters), and the
    error surfaced alongside it: the sweep reported **five** literal sites, a count right in magnitude
    and **wrong in composition**, because it had substituted the *vendored* canary's frozen copy for
    the shipped `render_dashboard._ACTIONS` — the 5-set it could not reach because that dict writes
    **each member with its payload between the names**, so no **line-scoped** matcher spans it — the
    names are 23 characters apart and the obstacle is the line anchor, not distance. The miss was
    therefore precisely the site the fix **derives** from. The paragraph now cites §RC-3's census
    table rather than re-deriving it, which is this section's own remedy one level up. No count of
    how many times this shape has now occurred is offered here — that count is the trap itself, and
    the closing paragraph already states the general form. What is worth recording is the
    circumstance: the sentence was written as the *lesson* of that shape, by the same hand, in the
    same hour. **One further correction came from the check this document prescribes for exactly
    this class** — *substitute the numbers into every clause of a warrant that mentions a specific
    line, and confirm the line's own text admits the direction claimed* — run on the new paragraph:
    it cited the literal array at `:1043` where `:1043` is only `function writeCount(c){` and the
    array is at `:1045`. That is the first time in this cycle the prescribed prompt caught an error
    **before** a reviewer did, which is the only evidence here that the method transfers.

**Revision 9** — the pin review's fourth round, folded (2026-09-18). Measured at `086e74ad` and
re-verified here at the live revision before folding; every label claim below was re-run on the two
trees rather than argued, and every fleet figure re-taken rather than accepted. The report also
attacked two of revision 7's findings — **36 and 37 — and both attacks landed**: 36 asked for a
measurement it lacked (now supplied: the closure, 0 of 104 outside the taxonomy, dated), and 37's
method sentence did not reproduce under its own stated scope (now repaired by naming the unit).

44. **A bullet in the paragraph that REPLACED a false warrant described a pin as stable — the second
    consecutive mislabel of the same cell, and in the direction this section calls the worse one.**
    It read: *"The same `reviewed: 0` with non-zero `candidates`/`git` gives `NO-OP PASS` on **both**
    revisions."* Its antecedent, two lines above, is `{reconciled: 1}`; **measured on both trees, that
    fixture MOVES at that reading** — `NO-OP PASS` pre-fix → `LIGHT PASS` post-fix. The sentence is
    true only of the *next* bullet's `{skipped: 3}`, where it ceases to illustrate reading-dependence
    at all. A reader was told a pin was stable, which erases a RED. The bullet's own subject turns out
    to be two claims, and only one of them is reading-dependent: the pre-fix **label** is (`NOTHING TO
    CONSOLIDATE` at all-zero, `NO-OP PASS` at `reviewed ≥ 1`), while the **pin/guard status** is a
    function of the fixture's *actions* — `skipped` sits in neither write-set. Both halves are
    restated with their measurements, and the ledger twin of this sentence under entry 31 was
    corrected with it.
45. **The same table's row 3 carried an unqualified pre-fix label that is reading-dependent.** It read
    `{reconciled: 1, skipped: 1}` → `NO-OP PASS` with no scope; **at all-zero it is `NOTHING TO
    CONSOLIDATE`** (measured, pre-fix). Rows 1 and 4 state their scope and row 2 is scope-independent,
    so this was the one row whose reading had to be inferred — the same row-level defect already fixed
    once for row 5. Repaired by stating both readings, which is what makes the row re-runnable.
46. **The RC-4 tally was still stated two ways: `4/3` in the heading and the ledger, `4/4` in the body
    and the table.** The heading read *"four pins and three guards"* and ledger 32 read *"four pins,
    three guards"*, while §RC-4's body said *"four pins and four guards"* twice and the table's own
    **eight rows** are four labelled PIN and four labelled guard (counted mechanically, `:990-997`).
    The split paragraph explained the move from 4/3 to 4/4 and the heading did not follow — a count
    that failed to reach its twin sites, inside the revision whose finding 33 records exactly that
    failure. This is also the count my own round-4 message to the reviewer carried wrongly as 4/3.
47. **Ledger 39's coordinates resolved to unrelated text, and one clause was false rather than
    stale.** It cited `:612`, `:1383`, `:980` and `:7` — all measured at `69bb3981`, a revision that
    no longer existed — so at the live revision they point at a blank line, a different paragraph, and
    a table row. The third clause was sharper than drift: it said a relayed `<slug>` fix *"was
    described but never written into `:7`"*, and `<slug>` **is** written there, with the suite green —
    so a reader acting on the entry hunts a fix that is present. This is finding 40's own hazard (a
    line number is not a handle) occurring in the entry **printed immediately above it**. Repaired by
    quoting the phrases instead of citing coordinates, which is what finding 40 implies for every
    entry measured against a superseded revision.
48. **The closeout's count of counts had the right total and the wrong membership.** It read *"Four of
    the five are **counts** — of sites, of gates, of pins, of matchers"*, and those four units map to
    33, **34**, 35 and 37 — but the same sentence's own list calls 34 *"the test suite"*, and 34's
    defect is a gate reddening rather than a count, while **36's defect IS a count's unit** (a
    population named where a class was owed) and was omitted. Repaired by naming the members with
    their numbers, so the membership is checkable rather than inferred: **counts are 33, 35, 36 and
    37**, and 34 is the event. The document's own defect class, in the document's own summary of that
    class — the third occurrence inside this revision's own folds.

**Revision 10** — the outcome clause refuted at the consumer, and the last two check labels, folded
(2026-09-18). The read question and the outcome question were separated by instrumenting both layers
rather than either alone, and every payload below names itself so that *hidden* and *reattributed* are
distinguishable from output. The round's report also re-filed two `§Risks` premises — `:1439`, `:1445`,
`:1464` — that already carry their conditions, which is finding 40's rule in the benign direction again.

49. **The base-key outcome claim was written from an intermediate, and only a consumer-side measurement
    refutes it.** `§Risks`' base-key bullet — with its mirrors in `§RC-1a`, the `memory_status` design
    comment and the `RC-1a` GUARD label — said the fault arm's bytes *"never reach the reader however
    the order falls"*, read off `read_diffs`' returned dict. That dict is an **intermediate**; the
    reader is the template's own `diffKey(marker, session)`-then-`diffKey(marker)` chain
    (`dashboard.template.html:1088`). Because the register step fills **every** probed key (`:260-263`,
    `:272-273`), a sessioned cycle that loads first has its **own** key filled. Measured with payloads
    that name themselves: the bytes render under their own cycle **iff the fault cycle carries a
    session and loads first**. Where the sibling loads first the probes do all hit an already-claimed
    key; where a session-less fault cycle loads first they do not — it reads and registers, and the
    sibling's later load overwrites every key it registered. Either way the modal falls through to
    the base alias, which holds the **sibling's** payload — a real diff
    belonging to another dream rather than an empty modal, so the corrected word is **reattributed**,
    not shadowed. The control that fixes the cause is the sidecar's **absence**: the substitution
    appears without it, so the fallback produces it and not the write, which is what makes *"writing
    is never worse than not writing **for the cycle that wrote it**"* measured rather than assumed.
    (The scope was added by a later round: unscoped, the sentence is false for a *covering* cycle with
    no sidecar of its own, whose modal the write moves from empty to this arm's diff — a sibling
    finding, folded here rather than carried as a fresh entry.) Two check labels were false in the
    same round — the `RC-1a` GUARD's mirrored clause, and the `RC-1b` duplicate-flag PIN's *"(pre-fix:
    exit 0 and a sidecar is written)"*, whose own command line passes an unreadable `--before` and so
    writes nothing on either tree; the latter sat three lines from a paragraph the same fold had
    already conditioned, because each pass swept the sites it was handed rather than the claim.


