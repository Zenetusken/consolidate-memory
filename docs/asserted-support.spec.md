# Asserted support — design-of-record

**Status: implemented and REVIEWED — TWO rounds (11 + 15 findings; every substantive one patched,
each verified by measurement — see §The review round in the CHANGELOG entry). ⚠ Round 2 is the one
that matters: it measured that round 1's OWN fix was UNPINNED, which is this release's class turned
on its author. On `arc-0.4.61-dream-defects` — awaiting merge.** Base
revision `bb63015` (main @ v0.4.60). Target release **v0.4.61 (patch)** — every change is additive or a
correction; no install/marketplace/schema contract moves.

**Provenance.** The 2026-09-24 dream pass (the consolidation ritual, not a code session) surfaced five
findings. This spec covers the four that are REPO changes; the fifth (a private-store fact body that the
firewall refuses on relocation) is a store repair and ships in the store, not here.

> **Reading the citations.** Every `file:line` below is **`bb63015`-numbered**. Resolve it against
> that commit — `git show bb63015:<path>` — and **never against the working tree**, which has moved
> them.

**The class.** One shape, four sites: **a surface asserts a verdict its operands do not support.** A
remedy is printed with no candidates computed (RC-1); a budget is called reachable by a computation that
does not answer the question its own declaration asks (RC-2); a status claim is asserted in shipped prose
whose stated support does not carry it (RC-3); and a document class declares its own status while no
matcher reads it, so the declaration cannot contradict anything (RC-4).

⚠ **The shared tell is an ABSENCE that reads as an answer.** In RC-1 the absence is a candidate list, and
it reads as "nothing is prunable". In RC-2 it is a shortfall, and `reaches_budget: True` reads as "a prune
fixes this". In RC-3 the absence is an enumeration method, and four sightings read as a census. In RC-4
the absence is a reader, and a drafting-era line reads as current.

## Scope

| id | site | change |
|---|---|---|
| RC-1 | `memory_status.py` — the SJ branch + `_remediation_section` | the hard ceiling's relief candidates become computable while standing-justified |
| RC-2 | `memory_status.py` — `remediation_triage` | `projected_index` / `reaches_budget` become the quantity their declarations name |
| RC-3 | the v0.4.60 checkpoint PR's claims (commit message + THREE spec notes) | two claims corrected to what a stated matcher measures |
| RC-4 | `tests/docs_links.py` + 14 `docs/*.spec.md` headers | a gate over spec status lines, then the sweep it finds |

Out of scope: `seed` (a canonical whose deletion the auto-mode classifier denied as an unrequested
irreversible delete — it needs the user to name it).

⚠ **A correction to this section's own first draft, kept rather than quietly edited.** It read *"the
index's own over-ceiling position (measured below, and there is no lesson-free relief)"* — and **RC-1's
repair disproves it**: with the stages visible, the ceiling IS locally satisfiable (a full prune frees
3991 → 3587 tok). The clause inherited the dream's conclusion, and that conclusion was produced by the
defect this spec exists to fix. A spec that silently adopted the finding it refutes would be the same
error one level up.

## RC-1 — the ceiling's instrument is suppressed with the gate

**Measured.** On a store at 4008 est tok against a 3840 ceiling, `--triage .` printed exactly two blocks —
the standing-justify kv and the ceiling line — and **no staged candidates.**

**Root cause, two layers.** `remediation`'s standing-justified branch (`memory_status.py:3602-3606`)
constructs the dict without a `stages` key; only the `elif` branch (`:3610-3671`) builds them. And
`_remediation_section` (`:4994`) returns early on `standing_justified` (`:5006`), before the staging loop
(`:5018`) — so even if the key were present the renderer would not reach it.

⚠ **The layer that makes it a defect rather than a design choice.** v0.1.21 suppressed the triage when
standing-justified ("show the standing state, no triage") — deliberate. v0.1.66 then added the hard
ceiling as a **sibling signal** and hardened its *line* against that suppression, with a comment stating
the ceiling is "standing-justify-INDEPENDENT … so suppression of the target gate never hides it"
(`:4999-5005`). The line is indeed un-hidden. **The stages the line points to were never given the same
independence** — so the ceiling is visible while its remedy is not. A later feature added a promise to a
path that had deliberately removed the instrument.

**Fix.** Hoist the ceiling boolean above the branch (a pure move: it must NOT enter the
`required`/standing-justify computation, which the existing comment at `:3673` already requires and which
this preserves). Then, when `over_ceiling` holds, build the stages regardless of the suppression, and have
`_remediation_section` render them under the ceiling line.

⚠ **One builder, not two — and this paragraph's first draft named a mechanism that was NOT shipped.**
It said the staging computation "moves into a single helper called from both branches". What was done is
narrower and better: the branch guard was widened to `_sj_suppressed and not _over_ceiling`, so the ONE
EXISTING builder runs on the ceiling path too and the verdict is re-stamped after it. **No helper was
added.** The outcome this paragraph demanded is honoured; the mechanism it named is not — and a reader
checking the spec against the code would have found no such helper, which is the same class this document
is about. (None is needed: the staging block is not a duplicated rule here, it is one block reached by two
guards — which is what "one builder" was asking for.)

⚠ **Why the cost is acceptable.** The staging scan reads every fact body. It is skipped today on the
*healthy* path (under budget, where `remediation_triage` short-circuits to `{}`). This change skips it on
the suppressed-and-under-ceiling path too — i.e. only a store that is BOTH standing-justified AND over the
hard ceiling pays, which is precisely the store whose ceiling line is currently unactionable.

**Pin.** With `standing_justified: True` and `over_ceiling: True` on a fixture, `_triage`-equivalent
output must contain a non-empty `stages` mapping AND `_remediation_section` must render at least one
staged line. Both conjuncts are required: the second is what the early return defeats, the first is what
the branch defeats, and a pin on either alone passes on the other's tree.

## RC-2 — `projected_index` does not compute what it declares

**Measured.** `_LEAN_HOOK_TOK = 30` (`:1653`). Live index: 3932 est tok over 79 pointer lines = **49.8
tok/pointer**; the store's own archived witness records **58.3** over a 35-row keep core. At the recorded
`keep=35`, the constant yields `projected_index = 1050` → `reaches_budget = True`; the measured
per-pointer cost yields 2040 → **False**. The two disagree about the same store.

**Root cause, stated precisely — the DECLARATION and the COMPUTATION differ.** The `Remediation`
TypedDict declares `projected_index: int  # est index tokens after evicting the candidates` and
`reaches_budget: bool  # can a full prune of the candidates reach budget?`. The implementation
(`:1832`, `:1835`) computes `keep_core * _LEAN_HOOK_TOK` — the keep core re-indexed at an assumed lean
cost. **That is not "after evicting the candidates", and it is not "a full prune of the candidates".** The
constant is not merely miscalibrated; it is the wrong quantity, and it is half again.

⚠ **The consequence is a rendered verdict, not a number.** `render_dashboard.py:1156` selects the D5
remedy sentence on `reaches_budget is False`. So an overstated `reaches_budget` prints the `prune` remedy
for a store that cannot reach budget by pruning — the remedy the D5 clause exists to replace. Same shape
as v0.4.34 (a verdict derived from the wrong operand), one layer down: there the operand was a label,
here it is a computation that never matched its own contract.

**Fix.** Measure the operands instead of modelling them. `remediation_triage` gains the pointer-line cost
per stem (the caller already scans the index text and already computes `mirror_index_tokens` from it — a
second scan of the same lines would be the single-enumerator violation). Then:

- `projected_index = index_tokens − Σ(pointer-line cost of the INDEXED candidates)` — literally "after
  evicting the candidates", which is what the field declares. A_orphans contribute 0 (unindexed).
- `reaches_budget = projected_index <= budget` — literally "can a full prune of the candidates reach
  budget?".

`_LEAN_HOOK_TOK` is then unused and is deleted, with the measurement recorded where the constant was, so
the next reader finds why it is gone rather than re-deriving it.

⚠ **Measured on both trees, on the v0.4.61 fixture** (the RC-2 triage pin in `tests/smoke.py`): with two
facts, one of them indexed and tracker-named, the model computed `keep_core(1) × 30 = 30` → `reaches_budget
True`; the measured computation yields **1992** → `False`. ⚠ This line said 1940 until a late review
lens re-derived it from the pin it CITES: the fixture's evicted line is 29 chars → `est_tokens` 8, and
2000 − 8 = 1992. 1940 was the value from the RETIRED per-line-sum relief, carried here after the pin
was updated — the release's own thesis, on the release's own measurement. They disagree on the
VERDICT — the field that
selects the rendered remedy. Pre-fix the suite reads `2333 passed, 10 failed`; post-fix `2343 passed, 0` (the count includes the three RC-4 pins below).

⚠ **And the fix rewrote THIS DREAM'S OWN CONCLUSION.** With the stages finally visible (RC-1), `--triage`
on the live store reports **2 tracker/status + 6 dated/oversized** candidates, and a full prune frees
**3991 → 3587 tok — under the 3840 ceiling.** So the ceiling *is* locally satisfiable here, and the
2026-09-24 dream's finding that "there is no lesson-free relief; the ceiling's only consequence is a held
test fixture" was **produced by the RC-1 defect that same pass found**: an empty candidate list read as
the verdict "nothing is prunable", and I recorded it as a measurement. Stated here rather than quietly
dropped — it is the same shape as RC-1 itself, one level up.

**Pin.** For a fixture index with known per-line costs, `projected_index` must equal the index minus the
pruned lines' costs, and `reaches_budget` must follow from it. A second conjunct asserts the retired
constant is absent (a re-introduction is the defect returning).

## RC-3 — two claims in shipped prose whose stated support does not carry them

Both ship in the v0.4.60 checkpoint PR (`af0d88d`). Neither has runtime effect; both are claims.

**(a) "FOUR SPEC HEADERS" is a sighting, not a census.** ⚠ **The claim is in the COMMIT MESSAGE of
`af0d88d`, not in CHANGELOG prose** — that PR added no CHANGELOG entry at all ("docs/ is not part of the
plugin artifact"), which this spec's first draft got wrong and this line corrects. It enumerates four
`docs/*.spec.md` files that said DRAFT after their designs shipped. A census over the same corpus, with a
stated matcher, finds **sixteen**, 13 of them named inside a versioned release section (RC-4 — and see
that section for why this count moved once per matcher fix). The four
were read, not enumerated — the defect `a-sole-claim-needs-a-census-not-a-sighting` describes, committed
in the same PR that added that fact. A commit message is immutable, so the correction lands where the
claim is actually READ: the spec notes below, and the v0.4.61 entry.

**(b) "nothing reads a spec's own header" overclaims — and it appears in THREE spec notes, not four.**
`tests/docs_links.py` lists `docs/1.0-preflight.spec.md` in `LIVE_DOCS` (`:186`), and
`check_version_statements` reads that file's status line (`:8`) for a version token. The defensible
statement — the one that is TRUE — is narrower: **no check read a spec's status WORD** (`grep -rn "DRAFT"
tests/*.py plugins/*/scripts/*.py` → 0 hits). The claim generalized one line past its evidence.
⚠ `cross-domain-index-refresh.spec.md` does NOT carry it, which this spec's first draft asserted from a
count of the headers fixed yesterday rather than from a grep of the sentence — the same error, one level in.

**Fix.** Correct both, each naming its matcher and revision, and note that (a) cannot be corrected in
place. This repo's convention for a wrong released claim is to amend with the measurement stated (the
v0.4.35 and v0.4.54 entries each carry such a correction); a commit message is the one surface where
that is impossible, so the correction is carried by the readable surfaces and by the new entry.

## RC-4 — a status claim outside every matcher

**The blind spot.** `docs_links`' `LIVE_DOCS` (`tests/docs_links.py:180-187`) is a **version-currency**
set: six explicit entries, and membership means "this doc's version statement goes stale when a release
lands". A spec's *status* (DRAFT / SHIPPED / awaiting review) is a different axis and is in no set, so a
drafting-era line can survive every check — which is exactly how four headers survived months past their
release. The class is `gate-coverage-is-its-match-set`: a gate proves only what its matcher can see.

**The measured rule.** A `docs/*.spec.md` file whose header states a pre-shipping state **while
CHANGELOG.md names that file inside a `## [X.Y.Z]` release section** is a contradiction. Measured on the
**re-measured after a review lens falsified the first census.** That matcher was anchored on `status`
STARTING a line, so `docs/cm-commands-onboarding.spec.md:3` — `**Design-of-record for the five UX verbs…**
Status: draft…`, named in CHANGELOG §0.4.8 — was invisible to it, and two specs stating a status as a
TITLE (`— spec DRAFT`) carried no `status` word to find at all. Widened to the word anywhere in the first
40 lines plus the title form:

⚠ **Each row names the TREE it was measured on**, because the two differ and an earlier version of this
table mixed them (a late review lens caught it):

| population | PRE-sweep (`bb63015` docs + its CHANGELOG) | POST-sweep (this revision) | fires? |
|---|---|---|---|
| pre-shipping, named in a release section | **13** | **0** (all swept) | **yes** |
| pre-shipping, in no release section | 2 | 2 | no — the rule cannot adjudicate them |
| done/implemented (the control) | 36 | 49 | no — the rule does not constrain them |
| no status found at all | 7 | 7 | no |
| **status lines EXAMINED** (the ✓ denominator) | **51** | **51** | — |

Corpus: 58 specs, 163 release sections pre-sweep and 164 post — the extra section is this release's own.
⚠ The control row is not stable across the two because the SWEEP moves files out of the pre-shipping
population into it (13 + 36 = 49 post-sweep; pre-sweep's 13 were still pre-shipping).

⚠ **And this count moved TWICE, once per matcher fix — which is the finding, not a footnote.** The
first matcher (line-anchored on `status`) read 13; widening it to the word anywhere read 14; ranking a
DECLARATION above a prose mention reads 13 again, because the widened form had been reading
`env-preflight.spec.md`'s first line and missing the “Shipped in v0.4.16” four lines below it. **A gate's
number is a property of its matcher**, and every fix to one must re-measure it — which is why the
shipped claim is stated with its instrument rather than as a bare figure.

⚠ **And 14 is a FLOOR, not a ceiling.** The two unadjudicable headers are stale in the same way; the rule
simply has no versioned citation to contradict them. A gate's denominator is its matcher's reach — which
is the sentence immediately above, applied to this gate.

⚠ **Why the release-section requirement, and not "cited somewhere in CHANGELOG".** The first form of this
rule was measured as "referenced anywhere in CHANGELOG" and fired on 14 of 16 with 0 control failures
(13 of 16 under the retired narrow matcher, which is the count this paragraph carried until the fix) —
but that measurement was **circular**: the same signal served as the rule's input and as my evidence that
the work had landed. Restricting to text inside a `## [X.Y.Z]` section makes the signal versioned and
independent, and the 14th spec drops out on its own.

⚠ **The rule's honest limit, stated in the gate's own message.** A release section could cite a spec
*forward* ("staged for a later release"), which would fire on a legitimately-open spec. The message
therefore names both readings — stale header, or forward-looking citation — and the remedy (update the
header) is correct under either. This is a gate with a stated ceiling, not a proof.

**Fix.** A new check in `tests/docs_links.py`, over the same corpus, with a pin in `tests/smoke.py`
following the D6 self-counting constant. Then sweep the 14 headers to state what actually happened,
each citing the release that names it.

## Verification

- `python3 tests/smoke.py` — the D6 self-counting constant bumped for every added check; both-tree
  measurement for each new pin (a FULL COPY of the pre-fix tree, never `git archive`).
- `python3 tests/docs_links.py` must go RED on the un-swept corpus and GREEN after the sweep — the
  gate's own two-tree control.
- `python3 tests/validate_manifests.py`, `tests/simulate_accumulation.py`, `mypy --config-file mypy.ini`.
- RC-2's fix is checked against the live store, where the old and new computations are known to disagree.

## Risks

- **RC-1 adds cost to one path.** Only a store both standing-justified and over the ceiling pays; the
  alternative (leaving it) is a ceiling line that cannot be acted on. If the cost shows up, the correct
  lever is to make the stages lazy on `--triage`, never to re-suppress them.
- **RC-2 changes a field's meaning** while its NAME is unchanged. The declaration already said the new
  meaning, so consumers reading the declaration are unaffected; `memory_status.py:5035` renders it as
  "projected index relief", which this spec updates to name what it now is.
- **RC-4's rule can fire on a forward-looking citation.** Stated in the message; the remedy is the same
  either way. If it ever fires wrongly, the fix is to narrow the rule, never to silence the check.
- ⚠ **The index's over-ceiling position — CORRECTED, because this bullet's first draft asserted exactly
  what RC-2 retracts.** It read *"3991 > 3840 with no lesson-free relief"*. With RC-1's stages visible, a
  full prune of the **2 tracker/status + 6 dated/oversized** candidates frees **3991 → 3587 tok, under the
  3840 ceiling** — the ceiling IS locally satisfiable, and the residual over-TARGET density is what needs
  a standing-justification. Its numbers moved once RC-2 landed too, since `projected_index` is now the
  measured quantity rather than the modelled one. What remains a user decision is the deeper lever:
  merging near-duplicate pointers (the pin/observable cluster is 8 pointers, ≈400 tok).
