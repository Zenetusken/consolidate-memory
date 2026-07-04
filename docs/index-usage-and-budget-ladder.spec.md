# SPEC — index usage instrumentation + the budget ladder (Phase A/B of the index lifecycle)

**Status:** **Phase A SHIPPED** (`main`, v0.1.63, PR #71). **Phase B REVISED** after an independent
3-lens spec-review gate (2026-07-04, this repo's own established precedent — see
`docs/dream-procedure-integrity.spec.md`) found the original B1 design load-bearing-broken: re-keying
the single field `remediation.required` from the target to the ceiling would have silently stopped
triage from firing in the amber band, flipped the maintenance-pass pivot for the whole amber band, AND
**inverted a HIGH-severity release-blocking oracle** in the sibling `dream-beta-tester` plugin's
pre-push gate (`CHK-REM-SEED-CONTRACT`) — meaning the original spec, if built as written, would have
blocked the next release the first time a store sat over-target-under-ceiling. Full findings + the
redesign rationale: §Phase B below is the POST-gate design; the original is not reproduced (superseded,
not historical — unlike Phase A's shipped record, nothing here shipped, so there is no split-decision
need to preserve the pre-gate text). The gate also found two dead-symbol references (`_should_hold`,
`_pass_budget_flag` — neither exists; real functions `_would_net_grow`/`_over()`) and a measurement
error in Phase A's own problem statement (Doc-Flo's cliff-line figure was mis-wired from its fact
count) — both fixed below.
**Build shape:** two gated cycles/PRs (A then B — A's instrument validates independently; B's semantics
add new behavior). A shipped as PR #71 (patch). B, per the deterministic-release-versioning policy, is
also a **patch** — additive only (see §Phase B's design; nothing existing changes meaning) — pending
implementation.

## The problem (MEASURED, not asserted)

The dashboard has shown `auto-mem index ≈1504/1500 [██████████] 100% ⚠ OVER` for three consecutive dreams
while the remediation panel shows `✓ density justified` — a permanently-red gauge above a green sign-off.
The operator correctly read this as "something is wrong in the system or the assumption." The measurements:

- **The steady state is by construction.** `INDEX_TOKEN_BUDGET = 1500` was derived as "measured active set
  (~1100–1200 tok) + ~25% headroom" (`memory_status.py:322`) — so a mature, healthy store converges to
  ~100% and pins there. Trajectory: 522 → 1504 est tok across 19 dreams / 17 days; **zero prunes in the
  last 11 dreams**; the last two ran `justify` → standing-justify (baseline 26 facts / 1504 tok).
- **"Everything is merited" is the deterministic output of the current protocol, not a finding.** Merit is
  judged **absolutely, per fact, in isolation** ("verified-true + lesson-bearing?"). LLM judges measured on
  absolute pass/fail over-accept — TPR ≈96%, **TNR <25%** (arXiv:2510.11822) — and `_KEEP_RE` vetoes any
  fact containing never/always/must/don't, i.e. *every well-written lesson*. On a store of true lessons the
  lever cascade (archive → KEEP-veto; gc → all canonicals content-fit; prune → nothing safely evictable)
  **terminates in `justify` every time**. The 2026-07-04T04:43 record shows the endpoint: script triage
  routed `gc` (mirror share 61% > `_MIRROR_DOMINATED`) and projected `reaches_budget=True` (keep_core ×
  `_LEAN_HOOK_TOK` ≈ 720 ≤ 1500), yet the recorded block says `justify` / `reaches_budget=false` — the
  merit-framed judgment overrode the script's own projection.
- **The over-target state already costs knowledge.** The M1 auto-hold (`sync_global.py:405`, keyed to
  `INDEX_TOKEN_BUDGET`) has withheld 2 relevant globals (`no-failure-masking-fallbacks` [user-global],
  `integration-test-loop-store-seam`) for 3 dreams — over a **0.3% overage of a heuristic soft target**.
- **The real failure boundary is elsewhere and is silent.** Claude Code hard-truncates: *"The first 200
  lines of MEMORY.md, or the first 25KB, whichever comes first, are loaded at the start of every
  conversation. Content beyond that threshold is not loaded"* (code.claude.com/docs/en/memory; verified
  2026-07-04). No relevance filtering — verbatim inclusion to the cap, then silent data loss. Fleet
  position: consolidate-memory 6,138 B / 27 ln = **25% / 14%** of the cliff; Doc-Flo 11,244 B / 46 ln =
  **44% / 23%** of the cliff (CORRECTED 2026-07-04 spec-review gate — the original "107" was Doc-Flo's
  *fact count*, mis-wired into the line-count slot; its real index is 46 lines, not 107); job-applicator
  ≈8.8 KB / ~38 ln = **35% / 19%**. All three nodes are over the 1500 soft target (100.3% / 184% / 147%),
  but **no real fleet store is anywhere near the 120-line cliff axis** — only synthetic QA fixtures are
  (see Phase B's Honest Limits).
- **Half the local overage is hook fat, not fact count.** Index lines average 57 est tok (mirrors 48,
  locals 83); the two fattest local hooks (`distill-feature-plan` 141, `consolidate-memory-roadmap` 116)
  are **17% of the whole budget in 2 lines** — status-content in the index, against the skill's own
  "pointers only" rule. 8 of 26 lines exceed 60 tok.
- **Utility is unmeasured — and the raw data evaporates.** Event-level transcript parsing (tool_use `Read`
  on fact files, dream sessions excluded) shows the recall tier *works* and is heavily skewed:
  job-applicator 59 organic reads over 22/37 facts; Doc-Flo 28 reads over **10/107 facts** (~90% never
  opened in the surviving window); consolidate-memory unmeasurable — only 3 transcripts survive, all
  dream-marked. Transcript retention is short: usage must be **accrued per-dream while the window is on
  disk** (exactly the `distill_scan` pattern) or it is lost. Today "merited" faces no utility
  counter-evidence because none is collected.

Context economics (research, applied): a ~1.5k-token block of high-signal, verified-true text has
effectively zero raw cost in a 200k–1M window (documented long-context failures are position / total-length
/ distractor effects — Lost in the Middle, RULER, NoLiMa, Chroma Context Rot); the costs that matter are
**distractor** (marginal never-used lines) and **staleness** (wrong lines misleading every session — already
covered by verification-first, this skill's strength). Anthropic's own memory-tool guidance recommends the
missing axis verbatim: *"Memory expiration: Periodically delete memory files that haven't been accessed in
a long time."* Every serious architecture caps the always-loaded tier by capacity/rank/reconciliation
(MemGPT pressure-eviction; Generative Agents recency×importance×relevance top-k under budget; Mem0
reconcile-vs-neighbors) — none by absolute per-item merit in isolation.

## Root cause (three, ranked)

1. **No utility axis.** Nothing records whether a fact is ever recalled, so the only questions the dream
   can ask are content-absolute — the protocol form that saturates. (Phase A fixes the *data*; Phase C
   uses it.)
2. **One number plays three roles.** 1500 is simultaneously curation target, hard gate trigger, and M1
   hold threshold — so a mature store sits permanently "in violation," the gate degenerates into a
   justify ritual, and the hold blocks verified knowledge at the softest rung. The real cliff (25 KB /
   200 ln, silent) is not represented anywhere. (Phase B fixes the *semantics*.)
3. **No per-line cost discipline.** Hooks are unbounded; nothing flags a 141-tok pointer. (Phase A
   detects; Phase B lints at write time.)

## Design principles

- **Instrument before policy.** Phase A adds observation only — zero behavior change, zero new gates. The
  demotion policy (Phase C) is specced only after real usage data accrues. No synthetic A/B calibration
  (the rigor-bands lesson): calibration is longitudinal, via the cycle log.
- **Zero reads ≠ zero use — pinned NOW.** Retention windows, the dream-span exclusion, and harness-side
  auto-recall (mechanism UNCONFIRMED in docs) all bias counts LOW. Phase C must treat 0-reads as *absence
  of evidence* requiring corroboration (age, verification history, redundancy), never as sole grounds to
  demote. This principle is part of this spec precisely so Phase C inherits it.
- **Script-truth counts, never hand-authored.** Usage counts enter the cycle record only via `--into`
  injection (the distill lesson: a hand-mirrored count already shipped an impossible value once).
- **Never delete verified truth over budget; change its LOAD tier.** All Phase-B/C levers move pointers
  between tiers or compress hooks; deletion remains the existing confirmed-prune path only.
- **The estimator stays chars/4 and honest (`≈`).** Cliff math uses exact `st_size` bytes and exact line
  counts (the units the harness caps in), not the estimator.
- **Report-then-apply everywhere, unchanged.** Nothing here auto-writes, auto-prunes, or auto-demotes.

## Phase A — instrument (no behavior change)

### A1. Recall tracking: `extract_signals.py --recalls`

New mode on the script that already owns transcript streaming and the marker window
(`_window_transcripts`, `extract_signals.py:293`; THE single timestamp parser):

```bash
CM_DREAM_ARC=1 python3 ${CLAUDE_PLUGIN_ROOT}/scripts/extract_signals.py --recalls [--json] [--into SEED]
```

**Mechanism.** For each window transcript, stream lines (never bulk-load); per line:
- record the line index of every Bash `tool_use` whose command contains `CM_DREAM_ARC` (the dream's
  scripted commands — the same marker the cues use);
- collect `Read` `tool_use` events whose `input.file_path` is under this project's auto-memory store,
  ends `.md`, and is not `MEMORY.md` (archive indexes like `SHIPPED.md` are excluded by the same
  `_is_archive_index` set used elsewhere); apply the per-event `since` filter (transcripts straddle the
  marker).

**Dream-span exclusion (the classifier):** within one transcript, a `Read` at line *i* is
**dream-procedure** iff `first_arc_line ≤ i ≤ last_arc_line` (first/last Bash-with-`CM_DREAM_ARC` in that
transcript); otherwise **organic**. Conservative by construction: a multi-dream session's inter-dream gap
is over-excluded (documented; safe direction given the §Design pin). Rationale for line-span over
per-transcript exclusion: on this repo all surviving transcripts contain dreams — whole-transcript
exclusion measures 0 forever (MEASURED); span-level recovers the non-dream portions.

**Output** (`--json`; human table without):
```json
{"window": "<sinceISO>..<nowISO>", "transcripts": 3, "dream_excluded": 104,
 "reads": 12, "facts_read": 5,
 "per_fact": [{"name": "gh-pr-edit-broken-in-env", "reads": 4, "last": "<ISO>"}]}
```
`per_fact` is **nonzero facts only**, sorted by reads desc, capped at `_USAGE_FACT_CAP = 20` (the zero set
is derivable at read time from the store — never stored). `--into SEED` injects this verbatim as the
record's new `usage` block (exit non-zero on an unwritable seed; warn if `--into` absent — both mirroring
the distill `--into` contract). Secrets surface: **none** — only file *paths* and counts are read from
events, never content.

**SKILL.md:** one Phase-5 step (beside the `--tokens` measure step): run `--recalls --into <seed>`; counts
are script-only. **Dashboard:** a small `USAGE` section (`reads N over M facts this window · top-3 by
name`; collapsed when the block is absent — legacy records render unchanged). `render_log.py` gains a
reads column (nullable for legacy rows).

### A2. Hook-cost telemetry

`memory_status.py` gains `HOOK_TOKEN_WARN = 60` (est tok per index pointer line; derived from the measured
distribution: fleet median ~48–57, the lean-rebuild model 30, the offenders 116/141). Phase-0 status
report lists lines over the threshold (count + top offenders with per-line est tok); the seed records
`budget.index.fat_hooks` (count) and `budget.index.hook_max_tokens`. Dashboard: append
`· hooks: N>60 (max ≈141)` to the index gauge line when `fat_hooks > 0`.

### A3. Cliff telemetry

New constants (measured claim, source quoted in code comment + harness-map):
```python
NATIVE_INDEX_CAP_BYTES = 25 * 1024   # docs: "first 25KB" — 1024-multiple assumed; if the harness means
                                     # 25,000 the ceiling shifts <2.5% (noted, immaterial)
NATIVE_INDEX_CAP_LINES = 200         # docs: "first 200 lines" — whichever binds FIRST; truncation is SILENT
```
Seed records `budget.index.cliff_pct = round(100 * max(bytes/CAP_BYTES, lines/CAP_LINES))` — exact units
(st_size bytes, real line count), estimator not involved. Gauge line shows `cliff 25%`; ≥ 80%
(`CLIFF_NEAR_FRACTION = 0.8`) renders red regardless of anything else (data loss imminent).

### A. Contract changes

`IndexBudget` (`memory_status.py:103`) gains `fat_hooks: int`, `hook_max_tokens: int`, `cliff_pct: int`;
`CycleRecord` gains `usage: Usage` with:
```python
class UsageFact(TypedDict, total=False):
    name: str; reads: int; last: str
class Usage(TypedDict, total=False):
    window: str; transcripts: int; dream_excluded: int
    reads: int; facts_read: int; per_fact: list[UsageFact]
```
All `total=False` additive (legacy records render). `validate_cycle_record` gains the impossible-count
backstop for `len(per_fact) > _USAGE_FACT_CAP`, with the cap **pinned cross-module to the producer** by a
smoke test (the `_DISTILL_CAPS` pattern, `memory_status.py:291`). SKILL.md schema block updated in the
same change (the existing smoke pin forces this). `render_html.py` mirrors any displayed constant as a
byte-pinned copy (its existing convention, `render_html.py:30`).

## Phase B — the budget ladder (semantics; ADDITIVE — nothing existing changes meaning)

**The gate-review pivot, stated once so every clause below is legible against it:** the original design
re-keyed ONE existing field (`remediation.required`) from the target to the ceiling. That field is not
free-standing — it is read by three other things that must NOT change meaning: the Phase-5 triage/
prune-pressure surfacing (fires at amber, per the ladder's own table), `maintenance.over_budget_not_
justified` (the no-commit maintenance-pass pivot, `memory_status.py:1447-1449`), and `dream-beta-tester`'s
`CHK-REM-SEED-CONTRACT` release-gating oracle (asserts over-target-non-SJ ⟹ `required is True` — a
HIGH-severity, push-blocking check). Re-keying `required` breaks all three at once. **The fix is not a
different threshold for the same field — it is a SECOND, INDEPENDENT signal for a SECOND, INDEPENDENT
concern:**

- **The existing amber signal (`remediation.required`, `remediation_triage()`, standing-justify) is
  UNTOUCHED** — same threshold (`INDEX_TOKEN_BUDGET`), same triage-at-amber behavior, same
  maintenance-pivot wiring, same oracle contract. Nothing here is Phase B's to edit.
- **A NEW hard ceiling check is ADDED alongside it** — its own constant, its own cycle-record field, its
  own SKILL prose, and (structurally, not by a documented exception) **never consults standing-justify at
  all** — it is defined the same way `_would_net_grow` already is today: a pure comparison with no SJ
  input. There is no "boundary where SJ stops suppressing" to place, because SJ was never wired to this
  check in the first place — mirroring how `_would_net_grow` (the REAL M1 hold predicate; see Dead
  symbols below) already ignores `standing_justify` entirely (`sync_global.py:404-408`, verified: it takes
  `(running_idx, pointer_cost, allow_net_grow)`, no SJ parameter).

```
rung                 threshold (this store today)          drives
─────────────────────────────────────────────────────────────────────────────────────────────
green                < 1500 est tok (target)               nothing — healthy
amber · over target  ≥ INDEX_TOKEN_BUDGET (1500)           UNCHANGED: prune_pressure · Phase-5 sweep ·
                                                           triage OFFERED · standing-justify quiets repeats
amber · SJ-refire    baseline +10 facts or ×1.25 tok       UNCHANGED: the triage conversation re-fires
RED · over ceiling   > INDEX_CEILING_TOKENS (≈3840,        NEW, independent hard gate: may-not-net-grow ·
                     derived from 0.6 × native caps —      M1 hold (re-keyed) · --evict valve. Structurally
                     see B1's single-source note)          SJ-independent (nothing to suppress; see above)
RED · cliff-near     ≥ 80% of native caps                  loud data-loss warning (Phase A, shipped)
cliff                25 KB / 200 ln (harness)              silent truncation — never reachable if the
                                                           ladder works
```

**B1. Dead symbols (gate-confirmed, all three lenses independently) — fix before anything else.**
`_should_hold` does not exist anywhere in the codebase; the real M1 hold predicate is
`_would_net_grow(running_idx, pointer_cost, allow_net_grow)` (`sync_global.py:404`, 3 required
positional args, no default — every real call site and smoke pin passes all three). `_pass_budget_flag`
does not exist; the real over-target gauge flag is `_over(b)` (`render_dashboard.py:202`, returns the red
`⚠ OVER` string when `b.get("over")`) — it is **shared** by both the index gauge (`:468`) and the
CLAUDE.md gauge (`:458`, which has no ceiling concept and must not gain one). Every reference below uses
the real names.

**B2. The new ceiling gate — a single-source token threshold, isolated from the byte/line cliff math.**
Add `INDEX_CEILING_TOKENS` as a **module-level constant in `memory_status.py`**, computed once from the
existing native caps (`round(INDEX_CEILING_FRACTION * min(NATIVE_INDEX_CAP_BYTES // 4,
NATIVE_INDEX_CAP_LINES_AS_TOKENS))` or an equivalent single deterministic formula — the point is ONE
canonical est-token number, not a live byte/line re-derivation at each comparison site, so `_would_net_
grow`, the new dashboard flag, and the new SKILL prose all compare the SAME value in the SAME unit
(closes the byte/line-vs-est-token mismatch the gate review found in the original B1). `_would_net_grow`
(`sync_global.py:408`) and `_evict_frees_enough`'s default (`:431`) take this constant via their EXISTING
parameter (no signature change — both already accept the threshold as an argument/default, so re-keying
is passing `INDEX_CEILING_TOKENS` instead of `INDEX_TOKEN_BUDGET` at the call site, not editing the
functions). New seed field: **`remediation.over_ceiling: bool`** — computed independently from
`index_lb[2] > INDEX_CEILING_TOKENS`, alongside (never inside) the existing `required`-setting branch in
`memory_status.py`'s remediation-dict construction (~`:1376-1388`) — it is a sibling assignment, not a
replacement. `--allow-net-grow` and `--evict` keep their semantics, now checked against
`INDEX_CEILING_TOKENS`. Consequence, honestly stated (corrected from the original, self-healed-stale
numbers): **no real fleet store is within reach of this gate today** (this project: 1406/3840 tok;
Doc-Flo: the largest real node, well under; job-applicator: under) — it is a backstop for a state none of
the three live nodes are in, which is the intended shape of a ceiling (see Honest Limits).

**B3. Gauge honesty — three renderers, not one, plus SKILL prose (a genuinely NEW addition, not an edit
to existing behavioral text).** `over_ceiling` renders alongside the existing `over` flag, never replacing
it, at all three sites that show the index budget: `render_dashboard.py`'s `_over(idx)` call (`:468`,
index gauge only — leave the CLAUDE.md call at `:458` untouched), `memory_status.py`'s own Phase-0/
`cm status` report (the gauge at `:1911/1917-1918`, the `_remediation_section` panel at `:1819`, the RIGOR
line at `:1892` — this is the operator's daily view via `cm status` outside a dream and must not keep
showing only the old signal), and `render_html.py` (which today renders NO remediation/rung state at all
— this is net-new work, not a mirror of an existing render). Legacy records (no `over_ceiling` key)
render **byte-identically** — gate this on **key presence** (`"over_ceiling" in idx`), not
`idx.get("over_ceiling")` (which defaults `False` and would silently pass a trivial/degenerate legacy
check instead of a real absence-check — the gate review's degenerate-pass-assertion finding). SKILL.md
gains NEW prose (not an edit to the existing Rigor-modes/Phase-5-step-0 text, which stays accurate as
written) documenting the additive ceiling gate: it fires independent of standing-justify, and the
existing over-target/justify language is unaffected by it.

**B4. Hook lint at write time (unchanged from the original design — no lens found an issue here).**
`sync_global --pull`/`--promote` warn (stderr + report line, never truncate) when a written pointer
(`_pointer_line`, `sync_global.py:365`) exceeds `HOOK_TOKEN_WARN`, naming the **canonical's description**
as the fix site (the pointer is derived from it; a fat mirror hook taxes *every* node). SKILL.md Phase 4
gets the same rule for model-authored pointers ("the hook is a distilled cue ≤ ~60 est tok; the
`description:` stays the full recall key").

**B5. Schema.** `IndexBudget` gains `ceiling_tokens: int` (the display value). `remediation` gains
`over_ceiling: bool` as a sibling of `required` (both `total=False`, additive). The existing `over` and
`required` keep their EXACT current meaning and computation — no key is renamed, removed, or re-derived;
legacy records carry no new keys and render as before.

## What Phase B does NOT do (scope fence)

No ranking, no demotion, no archive automation, no global-store budget, no change to verification, KEEP-
veto, archive/defrag candidate surfacing, prune-pressure, rigor tiers, or the procedure-integrity
detector. **No change whatsoever to `remediation.required`, `remediation_triage()`'s lever routing,
`maintenance.over_budget_not_justified`, or standing-justify's existing suppression of the amber band** —
all of that is the pre-existing, oracle-verified target-based gate, and Phase B adds a second, independent
signal beside it rather than touching it (this fence is itself a gate-review finding, not the original
design's — it exists specifically because the original draft crossed it). The over-ceiling gate has no
"justify" escape (unlike the target gate) precisely because it never had a "standing-justified" state to
escape from — it is a plain, always-live comparison, same shape as `_would_net_grow` today.

## Empirical gates (measure-don't-assert; each names its command + expected observation)

Phase A:
- **G-A1 (classifier fidelity):** run `--recalls` against the three live nodes; organic counts must be ≥
  the 2026-07-04 hand-probe per node (job-applicator ≥59 events/≥22 facts; Doc-Flo ≥28/≥10 — span-level
  exclusion is strictly narrower than the probe's whole-transcript exclusion), and consolidate-memory —
  0 under the probe by construction — must now report > 0 organic reads iff its dream transcripts contain
  non-dream-span fact reads (measure; either result is informative). Unit fixture: a synthetic transcript
  jsonl with reads before/inside/after an arc span → exact expected split.
- **G-A2:** against a frozen fixture index reproducing the live distribution: `fat_hooks == 8`,
  `hook_max_tokens == 141`.
- **G-A3:** fixture: 6,138 B / 27 ln → `cliff_pct == 24`; red iff ≥ 80.
- **G-A4 (contract):** `python3 tests/smoke.py` (incl. the SKILL-schema pin + the new `_USAGE_FACT_CAP`
  cross-module pin) · `mypy --config-file mypy.ini` · `tests/validate_manifests.py` ·
  `claude plugin validate --strict`. A legacy record renders byte-identically.
- **G-A5 (no behavior change):** diff the rendered dashboard of the latest live record before/after —
  identical except additive USAGE/gauge-suffix lines.

Phase B:
- **G-B1 (pure re-key, real names/arity):** `_would_net_grow(1504, 50, False)` → False under the OLD
  budget's math becoming irrelevant to this call — the actual pin is at the ceiling: `_would_net_grow(
  INDEX_CEILING_TOKENS - 40, 50, False)` → True (crosses); `_would_net_grow(INDEX_CEILING_TOKENS - 200,
  50, False)` → False (doesn't cross). `_evict_frees_enough`'s default follows the same re-key.
  **Existing smoke.py:303-310 hardcodes `_B38 = ms.INDEX_TOKEN_BUDGET` for `_would_net_grow` assertions —
  these are UNCHANGED calls to an UNCHANGED function at an UNCHANGED (target) threshold, since the
  re-keyed calls are NEW call sites passing `INDEX_CEILING_TOKENS` explicitly, not a change to what
  `INDEX_TOKEN_BUDGET`-keyed calls mean.** (Corrects the original G-B4, which wrongly implied these
  existing tests needed re-basing — they don't, because nothing about the target-keyed path changes.)
- **G-B2 (ladder rendering, 3 sites):** latest live record (currently green, 1406/1495 tok — see G-B3)
  renders unchanged at target-level; a synthetic over-ceiling fixture renders the NEW red flag at all
  three sites named in B3 (dashboard index gauge, `cm status`'s Phase-0 report, the HTML archive); the
  SAME fixture with `standing_justified: true` in its `remediation` block **still renders the new red
  flag** (trivially true by construction — `over_ceiling` never reads `standing_justified`, so there is
  no suppression path to test failing to suppress); a legacy record (no `over_ceiling` key) renders
  byte-identically, asserted via **key-presence**, not `.get()` default (closes the degenerate-pass trap
  the gate review found in the original G-B2).
- **G-B3 (synthetic acceptance — corrected from a live claim that gate-review measurement disproved).**
  The original G-B3 claimed the *next live dream* on this repo would demonstrate the ceiling gate's value
  (2 held facts landing, fat hooks shrinking). Gate-review measurement found this **already happened
  without Phase B** — a later dream (2026-07-04T18:45) independently tightened the fat hooks; this
  project's live index now sits at 1406→1495 tok (post-pull), green, zero fat hooks over 70 tok. No real
  fleet node is within reach of `INDEX_CEILING_TOKENS`. So live acceptance cannot validate this feature —
  build a **synthetic fixture** (a store engineered past 0.6× the native caps) and confirm: `--pull` HOLDS
  a new global there (unaffected by standing-justify, confirmed via a fixture with `standing_justify` set
  showing the SAME hold), `remediation.over_ceiling` is `True`, `remediation.required` is whatever the
  UNCHANGED target-based logic already says for that store (independent, may be True or False), and the
  dashboard/`cm status`/HTML all show the new red flag consistently.
- **G-B4 (blast radius, corrected).** `simulate_accumulation.py`'s existing fixtures at `:660,667,919`
  test the UNCHANGED target/standing-justify path (Probe L and Probe P respectively) and need **NO
  re-basing** — re-basing Probe P (an SJ-behavior test) past the ceiling, as the original G-B4 instructed,
  would have tested behavior Phase B does not touch, at a threshold Phase B does not move it to. Only
  **net-new** fixtures are needed, for the net-new ceiling gate. `tests/dream-beta-tester`'s
  `CHK-REM-SEED-CONTRACT` (severity HIGH, asserts over-target-non-SJ ⟹ `required is True`) and
  `CHK-BUDGET-CALIBRATION` are **unaffected by construction** (they read `remediation.required`/
  `budget.index.budget_tokens`, neither of which Phase B changes) — verify this holds post-build by
  running the beta-tester's own CI check (`plugins/dream-beta-tester/maintainer/ci_check.sh`) against the
  built code, not by inspecting the oracle's source (the gate review already did that; a live run is the
  actual proof). `cm` help text and the harness-map budget section gain the NEW ceiling-gate documentation
  (additive, not an edit to the existing target-gate passages).

## Honest limits

- **Usage undercounts, by design and by environment**: retention windows, span over-exclusion, and any
  harness-side auto-recall that doesn't surface as a `Read` all bias low. Hence the §Design pin: 0 reads
  is weak evidence. Phase C carries the burden of corroboration.
- **The ceiling fraction (0.6) is a chosen safety margin, not a calibrated point** — sized so the worst
  measured intra-day ambient spike (+~5 KB, 2026-06-21) fits between ceiling and cliff. Tunable; the
  ladder structure, not the fraction, is the design. **No real fleet store is within reach of it today**
  (largest live node well under `INDEX_CEILING_TOKENS`) — it is a backstop for a future state, not a
  current one; the QA-fixture repo in `dream-beta-tester` is the only store near it, and its position
  there (over vs. under, at the current 0.6) is presently incidental to how that fixture was originally
  sized (against the OLD 1200-era target, not this ceiling) — tightening the 0.6 fraction later should
  re-check that fixture's disposition explicitly, not assume it stays put.
- **The ceiling gate is deliberately NOT standing-justify-aware, by construction, not by a placed
  boundary.** The gate-review's original open question — "where should SJ stop suppressing?" — dissolves
  under this design: the ceiling check never reads `standing_justified` in the first place (same shape as
  `_would_net_grow` today), so there is nothing to suppress and no boundary to tune. If a future dream
  finds a genuinely earned-density store parked over the ceiling with nothing prunable, that is a Phase C
  problem (rank-under-budget demotion actually frees space) — Phase B's job is only to make the ceiling
  real, not to also invent a way around it.
- **chars/4 remains an estimate** (±20% vs a real tokenizer); all cliff math deliberately bypasses it.
- **A dream that never runs `--recalls` accrues no usage** — same class as skipping `--tokens`; the SKILL
  step + the `--into` injection make it cheap, and a missing `usage` block is visible in the log.

## Deferred to Phase C (recorded so it isn't re-walked)

Rank-under-budget demotion (ACT-R-flavored score: recall recency/frequency + last-verified + hook cost +
redundancy; bottom-K per-item dispositions: demote-to-archive / compress / merge / per-item
counter-justify), fleet-wide canonical utility aggregation via sync (the gc lever's missing evidence),
a global-store budget of its own, and the closed-loop miss-detector (an archive-demoted fact later read
from the archive is a transcript-visible demotion error — the same instrument audits its own policy).
Phase C's spec should quote this file's §Design pins as binding.
