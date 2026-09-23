# Producer/consumer parity — design-of-record

> **Reading the citations.** Every `file:line` below is **`3ada6c7`-numbered**. Resolve it against
> that commit — `git show 3ada6c7:<path>` — and **never against the working tree**, which will move
> them. All measurements were taken on that revision.
>
> **What this document covers.** Three defects measured during the 2026-09-23 dream pass. They are
> one arc because they are one shape: **a derived artifact or a consumer disagreeing with the thing
> that produced it**. §2.1–2.3 is D1 (PR 1); §2.4–2.5 is D2 + D3 (PR 2). Each section states which
> PR ships it.

---

## §1 Context (measured)

### D1 — the secrets firewall refuses ordinary prose, and freezes derived artifacts

`_looks_secret` (`plugins/consolidate-memory/scripts/memory_status.py:1299`) is
`bool(_SECRET.search(text)) or _entropy_blob(text)`. `_SECRET` (`:1116`) is a multi-arm alternation
compiled `re.I | re.X` (`:1229`). **Three fact bodies are refused today with no credential present.** They live in the **private
memory store** (`~/.claude/projects/<slug>/memory/`), so they are named here **without a
`path:line` coordinate** — a repo-relative citation to a private artifact cannot resolve at any
revision, and this repo's own citation gate (`v0.4.37` pin 7b) reddens on one. The line numbers are
stated as prose for that reason; they are coordinates in the private copy, not in this tree.

| private fact | measured span (line no. in the private copy) | arm |
|---|---|---|
| the roadmap fact | `the 2026-09-15 audit-pass sections,` (25) | CLI-flag |
| the distill plan fact | `entropy-vs-secret firewall` (65) | CLI-flag |
| the diffs-prose fact | `` `ms.INDEX_TOKEN_BUDGET = 1600` `` (55) | `[:=]` main |

Reproduce: `python3 -c "from memory_status import _looks_secret; print(_looks_secret(open(P).read()))"`
for each path; all three return `True`.

**Four consequences, escalating.** (1) `cm local rebuild-index` fails **closed** — measured
`{'ok': False, 'plan': True, 'error': 'invalid or unreadable facts…'}` with all three listed under
`invalid`. (2) `prepare_local_fact` (`local_ingress.py:149`) refuses the bodies, which are
**already-admitted content being relocated** — its own error text names the correct route
("reword the body, not the flag"). (3) **The second-order defect, and the reason this is a bug
rather than a preference:** the always-loaded index pointer is *derived* from `description:` by
`local_ingress._pointer` (`:68`), and both write paths (`local update`, `_rebuild_plan` `:451`)
route through `prepare_local_fact`. So a refused fact's cue **cannot be regenerated at all**.
Measured: `consolidate-memory-roadmap`'s body reads **v0.4.40** while its `MEMORY.md` pointer still
reads **v0.4.34** — frozen across six releases. Nothing compares body to cue, so the staleness has
no reporter. (4) `_scrub_commit_log` (`memory_status.py:3103`) gates on the same predicate, so a
matching commit subject is redacted in the Phase-0 report.

**The recursion, reproduced twice in one pass.** The fact documenting this
(`secret-arm-prose-false-positive`) was itself refused when the correction was written into it —
once when the correction quoted the triggering spans verbatim, and again when a rewording
introduced a fresh one. Its body already states the constraint: *"this fact cannot reproduce its
own trigger… which is why each instance above is described by shape rather than quoted."*

**Deviation note (for review).** The approved scope glossed D1's value narrowing as "compound…
(prefix **or** suffix)". On analysis the correct discriminator is **suffix only**; see §2.2. This
is a deliberate narrowing of the approved change, in the safer direction, and is called out here
rather than silently applied.

### D2 — the demotion docket names candidates the gate refuses

Reproduced back-to-back, nothing intervening:

```
memory_status.py --json                     → demotion.surfaced = [5 stems]
memory_status.py --justify-demotion <those> → "not a current demotion candidate: (all four) (pass --force)"
```

The counter-justify route the cycle record prescribes cannot be applied to 4 of the 5 facts it
names; the only printed remedy is `--force`, labelled *administrative repair*. This is the repo's
own `a-refusals-remedy-must-move-its-operand` class.

### D3 — a body-only edit silently inflates the always-loaded tier

`local_ingress._pointer` re-derives the index line from `description:` on every write. A stored
line a human had tightened below the derivation is **re-inflated by any edit to the body**.
Measured three times in one pass: **+62 est tok** across five facts
(`weakest-enforcement-site-wins` 38→60), then **+31** across two more
(`gate-coverage-is-its-match-set` 33→58). Nothing compares old cue to new, and the cost lands on
the tier paid every session. This was also the explanation for a validator advisory (a
`budget.index.after_tokens` vs scripted-audit delta disagreement) that read like a script bug.

### Not a defect — recorded so it is not re-opened

The `budget.index.after_tokens` vs `--audit` delta disagreement **resolved itself**: the audit had
run before later store writes and the budget re-measured after. Re-running `--audit` last, as the
skill's ordering requires, cleared it. No code change.

---

## §2 Design

### §2.1 D1a — the CLI-flag arm's dash must *introduce* a flag *(PR 1)*

**Root cause.** The arm's signal is a bare leading dash (`:1150-1176`), justified in-source as
*"ordinary prose essentially never spells `-password`"*. That holds for the alternation members the
comment was written against — `li_at`, `cf_clearance` — and fails for the short common nouns it was
generalized to (`pass`, `secret`, `token`, `cred`), which are ordinary English as a **compound's
final element**. Both measured instances have the dash preceded by a **word character**
(`audit-pass`, `vs-secret`): the dash is a hyphen *inside* a compound, not a flag introducer.

**Change.** Prefix the arm with a negative lookbehind:

```
-(?<![A-Za-z0-9_])(?:li_at|cf_clearance|password|passwd|pwd|pass(?:phrase)?|cred(?:ential)?s?|…)\b[= ]…
```

This is the direction the recording fact already names, and it closes **only** this arm — which is
why D1b is a separate change and not a substitute for it.

**Recall cost: NOT none — and an earlier revision of this section said it was.** MEASURED on the
pre-fix tree: the lookbehind also removes the CLI arm's **space-delimited sub-arm for any single
dash preceded by a word character**, so `redis-password hunter2value`,
`api-token abc123def456` and `db-password correcthorsebattery` were each flagged at `3ada6c7` and
are clean on the shipping tree — and **no other arm covers them** (the main arm requires `[:=]`;
`_entropy_blob` is False on each). The shape is *structurally identical* to the false positive it
shares its form with (`audit-pass sections,`), so this arm cannot separate them. It is therefore a
second **accepted gap**, recorded in `_SECRET`'s own comment block and pinned. That the claim was
wrong is itself the corpus lesson: every pinned case was `[:=]`-delimited, so the corpus could not
express the shape D1a would lose — `gate-coverage-is-its-match-set`, one level up.

### §2.2 D1b — a compound-id constant assignment is not a keyword credential *(PR 1)*

**Root cause.** The `[:=]` arm's structure is `PREFIX? KEYWORD SUFFIX? ["']?\s*[:=]\s*["']?
VALUE \S+` (`:1116-1127`). In `ms.INDEX_TOKEN_BUDGET = 1600`, `token` matches as the **middle
segment** of a SCREAMING_SNAKE identifier (`PREFIX` = `INDEX_`, `SUFFIX` = `_BUDGET`), and the
value gate's digit branch — `(?=\S{4,})\S*\d`, added in v0.1.70 Gate-2a to stop `token: bump TTL to
3600` — admits the bare integer `1600`.

**Change.** Decline the match when **both** hold:

- the value is **4–7 characters and purely numeric**, and
- a `[_.-]`-joined **suffix segment follows the keyword**.

Implemented **inside the regex** — the suffix clause becomes an optional *named* group and the
value clause is selected by a conditional — so the grammar keeps **one** source of truth. *Rejected:
a Python-level post-filter*, which would need a second parser for the same grammar; this repo has
documented that as its already-bitten divergence class (`extract_signals`' comment at `:186`, and
the `_parse_ts` relocation note).

**Why suffix-only, not "prefix or suffix".** A **prefix-only** match is the env-var shape
(`MY_TOKEN=1234`) — a *real* secret worth catching. A **suffix** means the keyword is not the final
identifier segment (`TOKEN_BUDGET = 1600`), the code-constant shape. Suffix-only is strictly safer
(catches more) and still delivers both approved outcomes: `INDEX_TOKEN_BUDGET = 1600` clean,
`password=1234` caught (standalone keyword), `password=12345678` caught (8+ branch).

**This is an ACCEPTED GAP — and its class has now been stated wrongly TWICE, which is why the
shipped comment states it by SHAPE rather than by example.** Draft 1 said "4–7 characters and
purely numeric"; draft 2 widened it to "4–7 chars carrying a digit and no ASCII letter" and named
`TOKEN_KEY=12-345`, `token_v2=1.2.34`, `secret_v1=12_34`, `pwd_9=12.34` as declined. **Both were
wrong, and the second was wrong in the other direction**: the shipped predicate now FLAGS all four
of those (a recall *gain*, since they carry non-digit characters). What actually holds is a test on
the value's **leading run**: a compound-id value whose first 4–7 characters are digits and are not
followed by a word character is declined. It had to become a shape test rather than a letter test
because **both earlier formulations left the class only partly cured** — measured,
`{"INDEX_TOKEN_BUDGET":1600,"max":8}` stayed flagged, since the 8+ branch matched the whole
non-space run and never reached the numeric test at all. The tradeoff's posture is still
`_entropy_blob`'s (`memory_status.py:1254`): *"the firewall favors fewer false positives on
ordinary commit prose… This is a real tradeoff, not a bug to keep tuning."* **The lesson worth
keeping is not the predicate but the pattern: three successive statements of one measured class,
each written with confidence and each falsified by a sample the previous one had not taken.**

**Verified before implementation.** Applying both D1a and D1b to the real `_SECRET` and evaluating
all **28** pinned firewall case tuples flips **zero** verdicts. This check becomes a pin (§3).
**Correction, recorded because the first number was wrong:** an earlier draft said 43. That was an
*unscoped* AST harvest of every `(str, bool)` tuple in `tests/smoke.py`, which swept in seven
tuples from unrelated tables — the error-signal noise filter and a ruff-output block — and reported
them as "flips". Scoping the harvest to `for` loops whose body actually references `_looks_secret`
gives **28**, and the census is green. (The shipping pin reports **32**: the census re-derives its
population from the suite at run time, so adding the D1b boundary table grew the corpus it reads.
Both numbers are true of their moment, and the pin prints its own — a count that could not say
which revision it counted would be the defect this census exists to catch.) The over-inclusive
instrument is this repo's own
`gate-coverage-is-its-match-set` shape: a census is only as wide as its match set, and an unscoped
one reports its own sweep as a finding.

### §2.3 D1c — a refused body must not freeze its own cue *(PR 1)*

**Root cause.** The pointer is a function of `description:` **alone**, but `prepare_local_fact`
validates the **whole body**, and every pointer-producing path calls it. So the failure of one
concern (body safety) blocks an unrelated one (cue freshness).

**Change.** Add a **description-scoped refresh**: a path that derives the pointer from the
`description:` and validates **only that string** — the field the cue is actually a function of —
then writes the line. `_rebuild_plan` (`local_ingress.py:451`) uses it rather than failing closed.

**Why this is not a firewall weakening.** It never admits a *body*; it cannot write fact content.
A secret in a body still blocks every content write. What it removes is a coupling between two
unrelated concerns, and it is the durable half of the fix: any future prose false positive (English
is unbounded) would otherwise re-create the frozen-cue defect.

### §2.4 D2 — one input builder, two consumers *(PR 2)*

**Root cause, measured by isolating each input.** The report builds
`index_names = index_fact_names(index_path) - {archive stems}` (`memory_status.py:3244`) and
**overrides** `usage_hist["windows_full"]` and `["window_starts"]` from `usage_window_clock(ctx)`
(`:3382-3386`). `run_justify_demotion` (`:2347`) passes `index_names = {p.stem for p in facts}`
(`:2399`) and takes `hist` from `usage_history(mem)` **with no override**.

| varying input | effect on `demotion_candidates` |
|---|---|
| `index_names` 80 vs 76 | changes `eligible` (11→8), **not** the candidate set |
| **`hist`** — `windows_full` 40 vs 24, `starts` 40 vs 24 | **changes the candidate set** |

`usage_window_clock`'s field is literally named **`probative`** — the word
`demotion_candidates`' own docstring uses for the eligibility rule ("the probative windows
(`hist.window_starts`) whose epoch start ≥ the fact's st_mtime"). **So the justify path is the
wrong one:** it feeds the predicate a non-probative window set.

**Change.** Extract the report's clock-override block **and** the `index_names`/archive derivation
into **one shared builder**; both consumers call it. Single-source, per this repo's discipline —
not a second predicate.

**Open question for implementation:** which count is authoritative for the *dormancy gate*
(`wf < _DEMOTION_MIN_WINDOWS`) as well as the per-fact count. The builder must not adopt a third
meaning; the spec will record the answer.

### §2.5 D3 — re-derive the cue only when its input changed *(PR 2)*

**Change.** On write, compare the fact's `description:` against the one the stored pointer was
derived from; **re-derive only when it changed**, otherwise preserve the stored line verbatim.

**Composition with §2.3.** The two rules are complementary, not redundant: `local update` on the
roadmap changes its `description:` (v0.4.40 → v0.4.41), so §2.5 **re-derives** — that is the frozen
cue's repair — while §2.3 is what makes the write *possible at all* while the body is refused.

**Scope.** `_rebuild_plan` (`local_ingress.py:451`) re-derives every line from descriptions and
needs the same rule. `sync_global._pointer_line` (`sync_global.py:1362`) is a **different
constructor** for global mirrors — not in scope; do not conflate.

> **Revision note — the first implementation of this rule CEMENTED the defect it was written
> against, caught before merge.** As first stated (*"re-derive only when `description:` changed;
> otherwise preserve the stored line"*) the rule had **one** condition. But a cue goes stale
> *precisely* by its description changing **while the write path refuses the fact** — §2.3's own
> scenario — and at the next write `prev_desc` and `new_desc` are both the *current* description,
> so a keep keyed on that alone preserves the stale line **forever**. REPRODUCED on the roadmap's
> own case before fixing it: body `v0.4.40`, pointer `v0.4.34`, and the naive rule returns
> `v0.4.34`. One silent defect's repair becomes another silent defect's cause.
>
> **The fix is a SECOND condition, and both are load-bearing.** The keep now fires only when the
> stored line is **truncation-consistent** with the current description — its hook must be a
> prefix of the normalised description, compared case-folded, because `_pointer` derives the hook
> as a word-boundary prefix and the stores carry both cases (`a gate proves…` stored against
> `A gate proves…` derived). A tightened-but-current line passes, because it *is* such a prefix;
> a stale one does not, so **stale cues heal on their next write**.
>
> Credit, and a rule from this store: the trap was caught by the independent design review, and
> then **re-derived and reproduced here BEFORE being applied** — a reviewer's proposed
> replacement is itself an unaudited claim (`a-reviewers-correction-is-an-unaudited-claim`). The
> discriminating arm is pinned, so the trap cannot be re-entered silently.

---

## §3 Verification — the pin list

**MEASURED, not asserted.** Run on a `git worktree` of the pre-fix revision `3ada6c7` carrying
this branch's `tests/smoke.py`: **`2202 passed, 14 failed`**. The 14 are enumerated below. The
shipping tree reads **`2216 passed, 0 failed`**.

Every PIN must FAIL on `3ada6c7`; a check that cannot fail there is a **GUARD** and is labelled
one, because a pin green on both trees proves nothing.

| # | check | pre-fix | kind |
|---|---|---|---|
| P1 | `audit-pass sections` stays clean | **✗ RED** (was `True`) | PIN |
| P2 | `entropy-vs-secret firewall` stays clean | **✗ RED** (was `True`) | PIN |
| P3 | `ms.INDEX_TOKEN_BUDGET = 1600` stays clean | **✗ RED** (was `True`) | PIN |
| P4 | the no-flip census over the suite's own firewall tables | **✓ green** | **GUARD** |
| P5 | `MY_TOKEN=1234` still flagged | **✓ green** | **GUARD** |
| P6 | `password=1234`, `password=12345678` still flagged | **✓ green** | **GUARD** |
| P7 | D1c unit route: clean description → a cue | **✗ RED** (by absence) | PIN |
| P8 | D1c unit controls: dirty description / clean body → no cue | **✗ RED** (by absence) | PIN ×2 |
| P9 | D1c plan routing: fresh cue, no fail-closed | **✗ RED** | PIN |
| P10 | RC-1c carry GUARD, re-aimed at the surviving `invalid` route | **✗ RED** | PIN |
| P11 | D1c plan GUARD: fixture preconditions hold | **✓ green** | **GUARD** |
| P12 | `--json` `demotion.surfaced` ⊆ `--justify-demotion` accepted *(PR 2)* | — | PIN |
| P13 | a body-only `cm local update` leaves the index token count identical *(PR 2)* | — | PIN |

> **P4 is a GUARD, and an earlier draft of this table got it wrong.** That draft claimed the
> census "cannot pass while P1–P3 are red". Measured, it passes on both trees: it re-evaluates
> the corpus the suite ALREADY asserts, and that corpus is unchanged on the pre-fix tree. A
> check that cannot fail on pre-fix code is a guard by this repo's own rule, and the fix is to
> label it — not to invent a reason it reddens. The correction is recorded because the wrong
> version would have shipped a pin claim that no measurement supports.

**Two pre-existing checks stopped being true and were RE-AIMED, not deleted** — both are
consequences of this branch, and both are themselves evidence the fix works:
- `RC-1c (GUARD)` asserted the fixture body "really does trip the firewall". Its body was
  `` Use `--token <value>` `` — **the D1a false positive itself** — so curing that shape cured
  the fixture's trigger. Re-aimed to assert BOTH legs of the surviving `invalid` route
  (body refused *and* no clean cue to derive from), so a future cure of either reddens the
  guard instead of leaving the pin testing nothing.
- `RC-1c (PIN)`'s fact now takes D1c's route (fresh cue) rather than the carry, so the fixture's
  description was made dirty to keep it in `invalid` — which is exactly the case D1c declines.
  The pair is the design: **RC-1c keeps the carry for what cannot be derived; D1c derives what
  can.**

**ReDoS — mandatory, not optional.** Both D1 changes touch an arm whose linearity is
structurally pinned: `tests/smoke.py` asserts `len(_redos_jwt_arms) == 1 and _redos_jwt_arms[0]
== _redos_jwt_lit`, plus behavioural timing checks. The `[:=]` conditional adds an NFA branch.
**MEASURED: the suite is green on both trees for every linearity and timing check**, so no new
ambiguity was introduced — re-read `docs/redos-guard-linearity.spec.md` before touching this.

## §4 Ship shape

**Two PRs, one patch release `0.4.42`.**

- **PR 1** `firewall-precision-and-recovery` — §2.1, §2.2, §2.3; pins P1–P7.
- **PR 2** `demotion-parity-and-cue-stability` — §2.4, §2.5; pins P8–P9.

`plugin.json` is hand-bumped to `0.4.42` **on the PR 2 branch**, not PR 1, and the CHANGELOG
`## [0.4.42]` is authored with it. The pre-bump path applies (`release.sh --stage` verifies,
never authors); `--expect patch`.

> **Corrected 2026-09-23, before either PR merged.** An earlier revision of this section put the
> bump on the PR 1 branch. That would have left `main` **red between the two merges**: the
> version and the CHANGELOG section are a pair, and `check_changelog_dated` asserts exactly that
> pair — `plugin.json` naming a version the CHANGELOG does not date is the state its own
> docstring says it closes. The bump belongs on the last PR of the arc, so the pair lands
> together.

## §5 Known ceilings (documented, not solved)

- **`facts_manifest` caches the verdict.** `facts_manifest.py:126` stores `"secret": bool(
  _looks_secret(text))` per canonical row, keyed on `mtime_ns`/`size`/`ctime_ns`/`body_hash`
  (`:118-122`), read by `sync_global.py:887`. A predicate fix therefore **does not clear a cached
  verdict** unless the file's bytes change. This is `weakest-enforcement-site-wins` §2 exactly. It
  does not affect the three D1 facts — they are *local* facts and this manifest is
  **canonical-tier** (`classify_canonical`) — but any canonical that trips will need an explicit
  cache invalidation, and no such path exists today.
- **The accepted gap in §2.2** is a real recall loss, deliberately taken.
- **Line-number anchors rot.** The pins cite behaviour, not coordinates, wherever possible.

## §6 Review round (PR 1) — what it found, and what it corrected here

An adversarial `/code-review` round ran against PR 1's head. It filed 15 findings; two were
repaired while it ran (both flagged by it as "REPAIRED UNCOMMITTED, still live at head"), two it
refuted and dropped, and the remainder are dispositioned here. **The round's cost was earned by
its first two findings alone**, which were defects in this arc's own D1c:

1. **The D1c route's gate was a fact about the DOCUMENT, not about WHY the fact was refused.**
   `prepare_local_fact` is first-refusal-wins and runs the firewall check FIRST, so a fact that
   was *also* badly named, badly scoped, badly statused or badly sensed reported **only** the
   firewall — and the route fired on it, filing it as `included` and **silently releasing it from
   the plan's fail-closed handling**. MEASURED: `name: totally-different`, `scope: domain-global`,
   `status: retired`, `sensitivity: topsecret` each produced a pointer. The route's docstring
   claimed *"this is not a general bypass"* and the claim was false. Fixed by a **two-call** test
   (`prepare_local_fact(..., check_secrets=False)`), so the route fires only when the firewall is
   the **only** refusal; four masking pins now hold it.
2. **The D1c disclosure never reached an operator.** `local_rebuild_index` returns a fixed
   key-allowlist and the plan dict is not returned, so `body_refused` was invisible on the only
   route anyone uses — while the plan's own comment read *"Reported rather than swallowed"*.
   Fixed by adding the key. ⚠ It had also defeated a verification: a probe reading the CLI output
   **cannot distinguish "nothing was refused" from "the key never propagated"** — the observable
   could not carry the difference, and this document's author read it as the former.

**Corrections this round forced on the text above** — each was a claim, not a typo:

- **§2.1's "Recall cost: none" was FALSE** and is corrected in place with the measurement.
- **§2.2's gap class was too narrow** and is corrected in place.
- **The RC-1c re-aim reason recorded in §3 and in the PR-1 commit message is FALSE.** It said D1a
  cured the fixture's trigger. MEASURED: `` _looks_secret('Use `--token <value>` …') `` is `True`
  at `3ada6c7` **and** at head — the match's dash is preceded by a **backtick**, which D1a
  permits, so that fixture was never a D1a case. **Only D1c forced the re-aim.** A maintainer
  trusting the recorded reason would size D1a's blast radius wrongly, and might delete the guard
  that proves the body still trips. (The pin labels carry the same correction.)
- **§3's totals could not be reconciled with its own table** — `2202 passed, 14 failed` beside
  eight RED rows. The 14 counts the pre-fix run *as it stood at that moment*; the table lists the
  arms. Stated rather than silently re-based, because a claim whose stated support does not sum to
  it is this store's `a-claims-support-is-an-unaudited-claim`.
- **§4's pin assignments contradicted §3** (D1c's pins appear under PR 1's row while §4 assigned
  P8/P9 to PR 2). §3 is authoritative; D1c ships in PR 1.
- **The frozen-cue figure disagreed across surfaces** — the code and pins said the body read
  `v0.4.41`, this document said `v0.4.40`, and "six releases" is arithmetically consistent only
  with `v0.4.40`. Unified on `v0.4.40` / six.
- **The no-flip census's harvest skipped every two-tuple table** — 33 of 65 entries, including the
  16-row false-positive corpus and the three D1a rows §3 depends on. It read 32 and printed a
  number that read as the whole corpus. Now derives each loop's expected polarity from that loop's
  own assertion and reads **51**. This is `gate-coverage-is-its-match-set` recurring **inside the
  check written to honour it** — twice, in two drafts.
- **`(?=[^\s]*[A-Za-z])` was the only unbounded quantifier the change added** to a regex whose
  documented invariant is that every quantifier is bounded. Harmless by measurement (linear), but
  safe only by a non-local argument and uncovered by the structural ReDoS pin, which anchors the
  JWT arm alone. Rewritten to the bounded `(?=[^\s]{0,7}[A-Za-z])`.
- **The D1a lookbehind tests the wrong operand for compounds ending in punctuation** —
  `(audit)-pass sections,` is still refused. Recorded, **not fixed**: it is a narrower instance of
  the class D1a already accepts a gap on, and chasing it in a review round is the tuning the
  firewall's own docstring warns against.
- **Two findings were refuted and dropped**: stem injection into `MEMORY.md` (unreachable —
  `validate_fact_stem` refuses first, verified empirically) and a claimed narrowing from the
  suffix clause's `{0,8}` → `{1,8}` (language-identical; the group is still optional). Recorded
  because a dropped finding is a decision. **The refuted stem-injection case nevertheless left a
  real gap** — the route concatenated its `stem` unvalidated, making its safety an unwritten
  precondition of one call site — so the route now validates the stem itself.



**None.** No `CycleRecord` field, CLI flag, manifest contract, or marketplace change. The
`demotion_candidates` signature is unchanged; §2.4 changes only *who supplies its arguments*.

## Contract impact

**No `CycleRecord` field, CLI flag, manifest contract, or marketplace change.** The
`demotion_candidates` signature is unchanged (§2.4 changes only *who supplies its arguments*).

**Two ADDITIVE internal changes, stated because "none" would be a claim too strong to make:**
`_rebuild_plan`'s return dict gains `body_refused` (now propagated through
`local_reindex`'s report allowlist — §6 finding 2), and `prepare_local_fact` gains the keyword-only
`check_secrets` (§6 finding 1), which is a **diagnostic** and which no write path passes `False`
to. Both are backward-compatible; nothing that read these surfaces before reads them differently.

## Acceptance

1. `python3 tests/smoke.py` green, `simulate_accumulation.py` green, `mypy --config-file mypy.ini`
   rc=0, `validate_manifests.py` rc=0, `docs_links.py` rc=0.
2. Every pin P1–P9 measured RED on the pre-fix tree and green on the shipping tree.
3. End-to-end on the real store: `cm local rebuild-index .` prints `ok: True`; the roadmap's pointer
   reads v0.4.41; all three bodies round-trip through `cm local update` unchanged.
4. `--json`'s `demotion.surfaced` ⊆ `--justify-demotion`'s accepted set.
5. A body-only `cm local update` on a long-description fact leaves the index token count identical.

## Strongest attack that failed

*(Mandatory section — empty findings are a false green. To be completed by the adversarial spec
review; this revision records the attacks already run and refuted.)*

1. **"The lookbehind weakens the firewall."** Refuted by measurement: no pinned firewall case — all
   **28**, scope-verified — has a word character before the dash. A real flag's dash follows
   start-of-string or whitespace.
2. **"The D1b narrowing drops real credentials."** Partly true and *accepted*: a 4–7-digit
   pure-numeric value on a suffixed identifier is no longer flagged. Refuted as a *blocker* by the
   pinned corpus: no existing case carries that shape, `password=1234` and `password=12345678` both
   stay caught, and the firewall's own docstring already declares fewer-prose-false-positives the
   preferred direction.
3. **"A Python post-filter is simpler."** Refuted: it requires a second parser for the same
   grammar. Measured cost of the in-regex form is a re-run of the linearity pins.
4. **"D2 is the `index_names` difference."** Refuted by isolation — that input moves `eligible` but
   not the candidate set; `hist` is the set-changing input.
