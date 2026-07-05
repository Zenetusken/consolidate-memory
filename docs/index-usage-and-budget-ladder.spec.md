# SPEC — index usage instrumentation + the budget ladder (Phase A/B/C of the index lifecycle)

**Status:** **Phase A SHIPPED** (`main`, v0.1.63, PR #71). **Phase B SHIPPED** (`main`, v0.1.66,
PR #75 — built to the 3-lens-gate-revised design below, then hardened by a max-effort code-review
workflow: 3 confirmed findings, all fixed pre-merge). **Phase C SPECCED** (2026-07-04, §Phase C below;
gated by the code-review skill on this spec before build, per the established gate discipline).
**Phase B REVISED** after an independent
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
**Build shape:** three gated cycles/PRs (A, then B, then C — A's instrument validates independently;
B's semantics add new behavior; C's policy consumes A's data). A shipped as PR #71 (patch). B shipped
as PR #75 (v0.1.66, patch — additive only; hardened by a max-effort code-review workflow). C, per the
deterministic-release-versioning policy, is also a **patch** — additive only (see §Phase C: new pure
functions, additive `total=False` schema keys, a new read-only sync mode, warn-only advisories; nothing
existing changes meaning).

**Phase C status note (2026-07-04):** the original §Deferred text said Phase C "gets its own spec once
~5–10 dreams of usage data exist." That precondition is **MEASURED unmet**: 20 logged cycles on this
repo, exactly ONE carries a `usage` block (2026-07-04T18:45 — 0 organic reads over 2 transcripts, 3
dream-procedure reads excluded), and no other fleet node has run a post-Phase-A dream at all. Rather
than wait (or fake the data — the rigor-bands lesson), §Phase C moves the precondition **from spec-time
to runtime**: the demotion rank carries an EVIDENCE GATE that keeps the policy structurally DORMANT
until enough full-fidelity usage windows accrue — the feature ships honest-and-inert on every real node
today (the same shape as Phase B's ceiling, which no real store can currently trip), and wakes only as
the data it needs actually exists.

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

## Phase C — the utility policy (rank-under-budget demotion · fleet utility · the miss-detector)

**What it closes.** Root cause #1 (no utility axis) got its *instrument* in Phase A; Phase C is the
*policy* that consumes it — plus the two evidence gaps §Deferred recorded: the gc lever's missing
fleet-wide utility evidence, and the global store's unmeasured fleet tax. The closed-loop miss-detector
makes the policy self-auditing — and it is exactly the **longitudinal miss-detection instrument** the
rigor-bands decision said real calibration requires (the calibration this repo deliberately refused to
fake with a synthetic A/B sweep). Phase C builds that instrument; the refit itself stays future work.

**Binding pins (from §Design principles, quoted as that section requires):** *"Zero reads ≠ zero use —
… Phase C must treat 0-reads as absence of evidence requiring corroboration (age, verification history,
redundancy), never as sole grounds to demote."* · *"Script-truth counts, never hand-authored."* ·
*"Never delete verified truth over budget; change its LOAD tier."* · *"The estimator stays chars/4 and
honest (`≈`)."* · *"Report-then-apply everywhere, unchanged. Nothing here auto-writes, auto-prunes, or
auto-demotes."* Every mechanism below is designed inside these five.

### C1. Longitudinal usage aggregation — `usage_history()` (memory_status.py)

The per-window `usage` blocks already persist forever in `<store>/.consolidation-log.jsonl` (written by
`render_dashboard --persist`; the live log verified above). A new reader aggregates them:

```python
def usage_history(auto_mem: Path) -> dict:
    # {"windows_full": int, "per_fact": {stem: {"reads": int, "last": iso}},
    #  "span_start": iso|"" , "miss_stems": frozenset}
```

- A logged cycle counts as a **full-fidelity window** iff its `usage` block is a dict with
  `transcripts ≥ 1` AND `facts_read == len(per_fact)` — a 0-transcript window observed nothing
  (retention gap), and a cap-truncated window (`facts_read > len(per_fact)`, possible past
  `_USAGE_FACT_CAP`) cannot prove any fact unread. Both are EXCLUDED from the evidence count
  (conservative by construction, per the pin).
- `per_fact` merges reads by sum, `last` by max, across counted windows. `span_start` = the `since`
  side of the OLDEST counted window's `window` string (unparseable ⇒ `""` ⇒ nothing is eligible — fail
  safe). `miss_stems` = the union of every logged `usage.misses` list (C3) — misses persist in the log
  even after the transcripts that revealed them rotate away.
- Malformed lines/blocks are skipped, never raised on (the store-scan convention). READ-ONLY.

### C2. The demotion rank — `demotion_candidates()` (memory_status.py; the `*_candidates` family)

PURE, RANKS only, same contract as `archive_candidates`/`defrag_candidates`/`remediation_triage`: the
script surfaces + the model judges content + the user confirms; **no write path**. A fact is
**eligible** only when ALL of the following hold (the evidence gate — the §Design pin made structural):

1. `windows_full ≥ _LIFECYCLE_MIN_WINDOWS` (**3**; a coarse, documented-tunable hint — the rigor-bands
   posture, NOT a calibrated point). Below it the whole rank is DORMANT (`eligible = 0` always).
2. The stem is **indexed** (`index_fact_names` — only an indexed pointer taxes the always-loaded tier;
   the `archive_candidates` precedent).
3. **Not a mirror** (`_is_mirror` — a mirror is GC's/the canonical's domain, `remediation_triage`
   precedent; its utility question is C4's, fleet-wide).
4. **0 recorded reads** across all counted windows (any read ⇒ never a candidate).
5. The fact **existed through the observed span**: `st_mtime ≤ span_start` (mtime is edit-time, so a
   recently-edited fact reads as new ⇒ excluded — undercounts eligibility, the safe direction).
6. **No KEEP-signal in the frontmatter description** (`_KEEP_RE` — the same veto, same
   sufficient-not-necessary caveat, as `archive_candidates`: a lesson/negative/directive STAYS; the
   demotion rank exists to find dead *reference/status* weight, not to relitigate lessons).
7. **Not in `miss_stems`** — a fact once demoted and then organically read from the archive (C3) is
   scarred: it proved live once; the rank never surfaces it again.
8. **Not suppressed by a live per-item counter-justify** (see dispositions): the state file's
   `lifecycle_justify[stem]` suppresses until `windows_full` grows by `_LIFECYCLE_JUSTIFY_REFIRE`
   (**5**) past the justification's recorded window count — the `standing_justify` delta-detector
   shape, per-item. A malformed entry does NOT suppress (surfacing is the safe direction here: the
   output is report-only — the exact INVERSE of `_standing_baseline`'s fail-open-to-FIRE, and for the
   same reason: err toward the human seeing it).

Eligible facts are ranked by **`hook_tokens` desc** — the fact's actual pointer-line cost in the live
index text (the measurable always-loaded relief its demotion frees; the `remediation_triage`
sort-by-cost precedent) — and capped at `_LIFECYCLE_BOTTOM_K` (**5**) surfaced. **Deliberately NOT an
ACT-R activation fit**: with eligibility already a binary evidence gate (0 reads × ≥3 windows ×
corroboration), a parameterized decay score would be uncalibratable fake-empirics today (the
rigor-bands lesson); "ACT-R-flavored" survives as the *shape* — evidence-of-disuse + cost — not as
fitted constants. Each candidate carries its evidence for the model's judgment: `stem`, `hook_tokens`,
`zero_read_windows`, `stale` (mtime ≤ marker — the existing re-verify signal), `indegree` (wikilink
in-degree — safe for archive-demotion since the BODY stays and `valid_link_targets` spans all `*.md`,
but load-bearing for a merge), and `similar`/`ratio` — the nearest same-store description by
`difflib.SequenceMatcher` ratio ≥ `_LIFECYCLE_SIMILAR` (**0.6**; stdlib, deterministic) — the
redundancy/merge evidence.

**Dispositions (model-judged in Phase 5, report-then-apply, recorded as `entries[]` rows per the
existing conventions):**
- **demote-to-archive** — the pointer moves `MEMORY.md` → an archive index (`SHIPPED.md` et al.); the
  BODY STAYS on disk (the never-delete pin: a load-tier change only). A `reconciled` row — the exact
  mechanics the completion-driven archive step already uses.
- **compress** — the hook is fat and the fact stays: tighten the `description:` (the fix site the
  fat-hook lint already names). A `corrected` row.
- **merge** — fold into its `similar` neighbor (dedup by content judgment; refuse on doubt). `deleted`
  + `corrected` rows.
- **counter-justify** — the fact stays as-is with a recorded reason (a `skipped` row), AND the Phase-5
  marker write adds `lifecycle_justify: {"<stem>": {"windows": <windows_full>, "at": "<iso>"}}` to
  `.consolidation-state.json` (the `standing_justify` write precedent) so the same candidate doesn't
  re-nag every dream (re-fires at +`_LIFECYCLE_JUSTIFY_REFIRE` windows).

### C3. The miss-detector — `--recalls` tier classification (extract_signals.py)

`recall_scan` already counts organic reads of every fact file; it just doesn't know the fact's TIER.
Post-classify each organic per-fact stem at scan time: **archived-tier** = a `](stem.md)` link-target
of an archive-index doc (`_is_archive_index` + `_LINK_RE`, both already imported/importable) AND not in
`index_fact_names(MEMORY.md)` (indexed wins when both). Two additive `usage` keys, script-truth like
the rest of the block: `archive_reads: int` (organic reads of archived-tier facts this window) and
`misses: list[str]` (the archived-tier stems read, sorted, capped at `_USAGE_FACT_CAP` — the existing
cap, validator-backstopped). **A miss is a transcript-visible demotion error**: the fact was moved out
of the always-loaded tier, and a session needed it anyway. The loop closes twice: the dashboard
surfaces it loud (C7), and `usage_history` folds it into `miss_stems` — permanently vetoing the stem
from future candidacy (C2.7) — while Phase 5 proposes RE-PROMOTING the pointer to `MEMORY.md`
(report-then-apply, a `reconciled` row). The span-exclusion classifier (`split_dream_span`) is
UNTOUCHED — a dream-procedure read of an archived fact is still not a miss.

### C4. Fleet utility — `sync_global.py --utility [--json]` (the gc lever's missing evidence)

A new READ-ONLY mode. Nodes = `_network_nodes()` ∪ the trigger store; per node, aggregate its log via
`usage_history` (imported from memory_status — the dependency root, the established import direction).
Join per **canonical** stem (`global_facts()` — a mirror keeps its canonical's stem by construction of
`--pull`): `reads` summed across nodes, `nodes_reporting` (nodes with ≥1 full-fidelity window),
`windows` summed, `last` (max ISO), `holders` (`_holders` provenance), `pointer_tok`
(`est_tokens(_pointer_line(name, fm))`), and `fleet_tax = pointer_tok × max(1, len(holders))` — the
per-session always-loaded cost this canonical imposes across the fleet. Report (canonicals sorted
fleet_tax desc, zero-read-everywhere flagged) + `--json`. This is **evidence for the model's gc/demote
judgment at Phase-5 step 2 and Phase-4 governance — never an auto-gc input**: scope/keep decisions stay
CONTENT-gated (the governance pin: holders/adoption ≠ fit; utility evidence informs the human-confirmed
judgment, it does not replace the cascade). Honesty figure printed in the header: `nodes_reporting /
nodes` — per-node usage exists only where post-Phase-A dreams have run `--recalls` (today: 1 node, 1
window, 0 reads — the mode ships as an instrument-coverage report first, an evidence table later).

### C5. The global-store fleet-tax advisory (a budget of its own, warn-only)

`GLOBAL_FLEET_TAX_ADVISORY` (sync_global.py, beside `GLOBAL`): an advisory ceiling on
`Σ fleet_tax` over all canonicals — the figure C4 computes. Derivation at build time, stated in the
code comment (the `HOOK_TOKEN_WARN`/`INDEX_TOKEN_BUDGET` measured-derivation precedent): measure the
live fleet's Σ fleet_tax, add ~50% headroom, round. Two warn-only surfaces: the `--utility` report
renders a gauge against it, and `promote()` prints an advisory line when the NEW canonical's marginal
fleet tax pushes the projected total past it (`this canonical adds ≈N tok × M holder(s) …`). **Never a
block, never a hold** — a hard fleet gate would be a new load-bearing mechanism needing its own
oracle-grade gate review (recorded in §Deferred beyond Phase C). No cycle-record change for C4/C5: the
`network` block already carries the per-node mirror attribution; the fleet-tax view is a report.

### C6. Contract changes (all additive, `total=False`)

- `Usage` gains `archive_reads: int` + `misses: list[str]` (script-injected by `--recalls` only).
- `CycleRecord` gains `lifecycle: Lifecycle`:
  ```python
  class Lifecycle(TypedDict, total=False):
      windows_observed: int   # script-seeded: usage_history windows_full
      eligible: int           # script-seeded: candidates past the evidence gate
      surfaced: list[str]     # script-seeded: bottom-K stems (≤ _LIFECYCLE_BOTTOM_K)
      demoted: int            # model, Phase 5: dispositions actually applied
      compressed: int
      merged: int
      justified: int
      verdict: str            # one sentence — "ran and proposed nothing" ≠ "never ran" (the distill precedent)
  ```
  Seeded by `seed_record` whenever the store exists (a DORMANT pass records `windows_observed`/`eligible: 0`
  honestly); disposition counts + `verdict` are model-filled in Phase 5.
- `validate_cycle_record`: `usage.misses` list-check + cap backstop (`_USAGE_FACT_CAP`); `lifecycle` in
  the top-level dict-check tuple; `lifecycle.surfaced` list-check + cap backstop (`_LIFECYCLE_BOTTOM_K`
  — producer and validator live in the SAME module here, so no cross-module mirror/smoke-pin is needed,
  unlike `_DISTILL_CAPS`/`_USAGE_FACT_CAP`).
- State file: `lifecycle_justify` (model-written in the Phase-5 marker write; read by a
  `_standing_baseline`-style guarded reader that treats malformed as not-suppressing — see C2.8 for why
  the fail direction inverts).
- SKILL.md schema block updated in the same change (the smoke pin forces it).

### C7. Surfaces

- **Phase-0 report / `cm status`:** SIGNALS gains a `demote?` line when `eligible > 0` (stems +
  evidence, beside `archive?`/`defrag?`); while DORMANT, one dim line — `usage evidence N/3 full
  windows — demotion policy dormant (accrues per-dream via --recalls)` — so the accrual is visible, not
  mysterious.
- **render_dashboard:** the USAGE section gains a red `⚠ demotion miss` line when `misses` is
  non-empty; a new LIFECYCLE line renders the block (dormant / eligible+surfaced / disposition counts +
  verdict). Legacy records (no `lifecycle`, no `misses` key) render **byte-identically** — key-presence
  gates, not `.get()` defaults (the degenerate-pass lesson, again).
- **render_html:** the per-dream detail gains the misses badge + the lifecycle verdict line (additive;
  legacy byte-identical). `render_log`: NO change (the READS column stands; lifecycle detail is
  dashboard territory — scope fence).
- **cm:** a `utility` subcommand (`sync_global --utility`); help lines for the new `--recalls` fields.
- **SKILL.md:** Phase 5 gains the lifecycle-triage step right after the `--recalls` capture (read the
  seeded block, judge each candidate by CONTENT — keep-on-doubt, the archive step's silent-failure
  language applies verbatim — apply dispositions report-then-apply, fill the block, re-promote any
  miss); step 2 (gc) points at `--utility` for the mirror-dominated lever's evidence; step 5's marker
  write documents `lifecycle_justify`; step 4's "that judgment is Phase C's" prose updates to point at
  the new step. Phase-4 governance: the promote advisory (C5) noted.
- **harness-map.md:** the three-tiers/budget section gains the lifecycle bullet (+the evidence gate),
  `--utility`, and the fleet-tax advisory.

## What Phase C does NOT do (scope fence)

**No existing mechanism changes meaning.** `remediation.*` (the target gate, triage levers,
standing-justify, `over_ceiling`), the M1 hold, the KEEP-veto, `archive_candidates`/`defrag_candidates`,
the `--recalls` span classifier, and every dream-beta-tester oracle input are UNTOUCHED — Phase C adds
siblings beside them, the Phase-B discipline. **No auto-writes anywhere**: scripts rank/aggregate/warn;
every disposition is model-judged + user-confirmed. **No fitted decay constants** (C2's rationale). **No
hard global-store gate** (C5 is warn-only). **`--utility` never writes** (read-only, like `--list`).
**0 reads is never sole grounds**: the evidence gate requires window sufficiency + fact-age + the
KEEP/miss/justify vetoes before a stem is even *surfaced*, and surfacing is still only a proposal.

## Empirical gates (Phase C — measure-don't-assert; each names its command + expected observation)

- **G-C1 (aggregator fidelity):** `usage_history` on THIS repo's live log → `windows_full == 1`,
  `per_fact == {}` (the measured state above). Synthetic log fixture: 3 windows — one full-fidelity, one
  `transcripts: 0`, one cap-truncated (`facts_read > len(per_fact)`) → `windows_full == 1`, only the
  full window's reads merged.
- **G-C2 (the evidence gate, every leg):** fixture store + history sweeps — <3 windows ⇒ `eligible == 0`
  regardless of everything else; ≥3 ⇒ eligible iff indexed ∧ non-mirror ∧ 0 reads ∧ mtime ≤ span_start ∧
  no description KEEP-marker ∧ not missed ∧ not justify-suppressed; each veto exercised independently;
  the justify suppression re-fires at exactly +`_LIFECYCLE_JUSTIFY_REFIRE`; a malformed justify entry
  does NOT suppress.
- **G-C3 (rank + cap):** eligible sorted by `hook_tokens` desc; ≤ `_LIFECYCLE_BOTTOM_K` surfaced; the
  validator backstop warns above the cap.
- **G-C4 (miss-detector):** synthetic transcript fixture — an organic `Read` of an archived-tier fact →
  `misses == [stem]`, `archive_reads == 1`; the SAME read inside the arc span → excluded (not a miss);
  an indexed fact's read → counted, NOT a miss; a stem linked from BOTH the index and an archive doc →
  indexed wins.
- **G-C5 (live dormancy + read-only):** on this repo today — the seed carries
  `lifecycle.windows_observed == 1`, `eligible == 0`; the report shows the DORMANT line;
  `--utility` runs against the live fleet with `nodes_reporting == 1` and **changes no store file**
  (hash the stores before/after).
- **G-C6 (contract):** `python3 tests/smoke.py` (SKILL-schema pin + the new cap backstops + the
  key-presence legacy-render pins) · `mypy --config-file mypy.ini` · `tests/validate_manifests.py` ·
  `claude plugin validate --strict` · `tests/simulate_accumulation.py`. A legacy record renders
  byte-identically on all three renderers.
- **G-C7 (oracle blast radius, by live run not inspection):** `plugins/dream-beta-tester/maintainer/
  ci_check.sh` against the built code → 0 FAIL (`CHK-REM-SEED-CONTRACT`/`CHK-BUDGET-CALIBRATION` read
  fields Phase C never writes — the G-B4 lesson: prove it by running the gate).
- **G-C8 (advisory derivation):** `GLOBAL_FLEET_TAX_ADVISORY`'s in-code comment reproduces the build-time
  measurement (`--utility --json` Σ fleet_tax) + the stated headroom — a documented derivation, not a
  smoke assertion (smoke is hermetic; it cannot read the live fleet).

## Honest limits (Phase C additions)

- **Everything inherits Phase A's undercount** — retention, span over-exclusion, invisible harness
  auto-recall — PLUS the per-window `per_fact` cap; full-fidelity window counting excludes truncated/
  empty windows (conservative both ways). The evidence gate is built ON an undercounting instrument,
  which is exactly why 0-reads alone never suffices.
- **A miss can itself be missed** (the revealing transcript can rotate before the next dream) — but a
  CAUGHT miss persists forever in the log's `usage.misses`, so the veto (C2.7) never forgets one.
- **Fleet utility sees only instrumented nodes** — `nodes_reporting` is printed precisely so the table
  can't be read as fleet truth when it's one node's telemetry.
- **The constants are coarse hints** (`_LIFECYCLE_MIN_WINDOWS`/`_BOTTOM_K`/`_JUSTIFY_REFIRE`/
  `_SIMILAR`, the advisory): documented tunable, uncalibrated by design — calibration is longitudinal,
  and Phase C is what CREATES its instrument (the miss loop). Do not A/B-sweep them (rigor-bands).
- **No real node can trip the rank today** (1/3 windows) — live acceptance is dormancy (G-C5) +
  synthetic fixtures (G-C2..4), the Phase-B/G-B3 acceptance shape.
- **`lifecycle_justify` lives in a mutable state file** — deleted/malformed ⇒ candidates re-surface
  (fail-open toward surfacing; report-only output makes that the safe direction).

## Deferred beyond Phase C (recorded so it isn't re-walked)

A HARD fleet-tax gate (needs its own oracle-grade gate review before it may block anything);
the rank-constant refit once the miss loop has accrued longitudinal data (the rigor-bands condition,
finally satisfiable); cross-node demotion coordination (demote-everywhere / archive-tier sync);
harness-side auto-recall visibility (if the harness ever exposes it, the undercount shrinks and the
evidence gate could tighten).
