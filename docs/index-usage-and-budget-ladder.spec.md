# SPEC — index usage instrumentation + the budget ladder (Phase A/B of the index lifecycle)

**Status:** **Phase A SHIPPED** — merged to `main` as v0.1.63 (CHANGELOG'd 2026-07-04; released via
`release.sh` separately from this doc edit — see the CHANGELOG for the exact tag). Produced by the
2026-07-04 over-budget investigation (measured against the live fleet stores, the 19-record
`.consolidation-log.jsonl`, event-level transcript parsing, and primary sources; nothing below was
asserted from intuition). This spec covers **Phase A (instrument — no behavior change, SHIPPED)** and
**Phase B (budget semantics — small, additive, NOT YET BUILT)** — the design below for B is still the
target to build against. **Phase C (rank-under-budget demotion, the pruning protocol proper) is
deliberately NOT here** — it consumes Phase A's accrued data and gets its own spec once ~5–10 dreams of
usage data exist (§Deferred).
**Build shape:** two gated cycles/PRs (A then B — A's instrument validates independently; B's semantics
change behavior), each a **patch** per the deterministic-release-versioning policy. A shipped as PR #71;
B is open.

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
  position: consolidate-memory 6,138 B / 27 ln = **25% / 14%** of the cliff; Doc-Flo ≈11 KB / ~107 ln =
  **44% / 54%**; job-applicator ≈8.8 KB / ~38 ln = **35% / 19%**. All three nodes are over the 1500 soft
  target (100.3% / 184% / 147%).
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

## Phase B — the budget ladder (semantics; small behavior change)

One number becomes an explicit escalation ladder. Constants in `memory_status.py` (the dependency root;
`sync_global` already imports from it, `sync_global.py:48`):

```
rung                 threshold (this store today)          drives
─────────────────────────────────────────────────────────────────────────────────────────────
green                < 1500 est tok (target)               nothing — healthy
amber · over target  ≥ INDEX_TOKEN_BUDGET (1500)           prune_pressure (unchanged) · Phase-5 sweep ·
                                                           triage OFFERED · standing-justify quiets repeats
amber · SJ-refire    baseline +10 facts or ×1.25 tok       the triage conversation re-fires (unchanged)
RED · over ceiling   > INDEX_CEILING_FRACTION(0.6) of      the v0.1.18 HARD GATE (may-not-net-grow,
                     native caps: >15,360 B or >120 ln     prune-or-justify) · M1 hold · --evict valve
                     (display ≈3840 est tok)               — and standing-justify does NOT suppress here
RED · cliff-near     ≥ 80% of native caps                  loud data-loss warning (A3)
cliff                25 KB / 200 ln (harness)              silent truncation — never reachable if the
                                                           ladder works
```

**B1. Re-key the hard mechanisms to the ceiling.** `_should_hold` (`sync_global.py:405`) and
`_evict_frees_enough`'s default budget (`:431`) compare against the ceiling, not the target — both are
pure, already smoke-pinned functions; the re-key is the comparison constant. `remediation.required` (the
seed's gate flag) keys to over-ceiling. **Standing-justify re-scopes DOWN the ladder:** it continues to
quiet the *amber* band's repeat triage (its real function today) but can no longer suppress the
over-ceiling gate — over the ceiling, only shrinking satisfies (justification is not a defense against
data loss). `--allow-net-grow` and `--evict` keep their semantics against the new threshold.
Consequence, stated plainly: **the 2 currently-held globals land on the next `--pull`** (index → ≈1600
est tok, amber), and holds effectively stop firing fleet-wide until a node crosses ≈3840 est tok — that is
the intent: withholding verified knowledge is the harshest lever and now keys to the harm boundary.

**B2. Gauge honesty.** The index gauge renders the rung, not a binary: amber shows
`over target · justified` when standing-justified (today the gauge stays red while the remediation panel
says ✓ — the measured mixed-signal this investigation started from); red is reserved for over-ceiling /
cliff-near. `render_dashboard` (`_pass_budget_flag` + the gauge site) gains the remediation/rung context;
`render_html` mirrors. Legacy records (no `over_ceiling` key) render **byte-identically** to today
(smoke-pinned, the AC#5 pattern).

**B3. Hook lint at write time.** `sync_global --pull`/`--promote` warn (stderr + report line, never
truncate) when a written pointer (`_pointer_line`, `sync_global.py:365`) exceeds `HOOK_TOKEN_WARN`,
naming the **canonical's description** as the fix site (the pointer is derived from it; a fat mirror hook
taxes *every* node). SKILL.md Phase 4 gets the same rule for model-authored pointers ("the hook is a
distilled cue ≤ ~60 est tok; the `description:` stays the full recall key").

**B4. Schema.** `IndexBudget` gains `ceiling_tokens: int` (display ≈), `over_ceiling: bool`. The existing
`over` keeps its exact current meaning (over-*target*) — no key is renamed or removed; legacy records
carry no new keys and render as before.

## What Phase B does NOT do (scope fence)

No ranking, no demotion, no archive automation, no global-store budget, no change to verification, KEEP-
veto, archive/defrag candidate surfacing, prune-pressure, rigor tiers, or the procedure-integrity
detector. The justify lever still exists over the ceiling (a genuinely all-durable over-ceiling store
records its justification — but the gate re-fires every pass there; no standing suppression).

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
- **G-B1 (pure re-key):** `_should_hold(1504, 50)` → False (was True); `_should_hold(3800, 50)` → True;
  `_evict_frees_enough` default follows.
- **G-B2 (ladder rendering):** latest live record renders amber `over target · justified`, no red `⚠ OVER`;
  a synthetic over-ceiling record renders red + gate; a synthetic over-ceiling **standing-justified**
  record still renders the gate (SJ must not suppress it); legacy record byte-identical.
- **G-B3 (live acceptance, operator present):** next dream on this repo — `--pull` receives the 2 held
  facts (index ≈1600 est tok, amber, no hold), the Phase-5 sweep tightens the 2 fat hooks
  (report-then-apply as always) → index ≤ target, green, **28 facts indexed, zero knowledge lost**. That
  end state is the demonstration that the target was reachable without evicting anything — the
  investigation's central claim.
- **G-B4 (blast radius):** the accumulation sim keys gate-engagement to `ms.INDEX_TOKEN_BUDGET`
  (`simulate_accumulation.py:660,919` — its over-budget fixtures must be re-based to the rung they mean:
  triage fixtures to the target, gate/hold fixtures past the ceiling). The smoke `_evict_frees_enough`
  tests already pass explicit `budget=` args by design ("a fixture sized to the live constant silently
  breaks on a re-ground", `smoke.py:1162`) and survive unchanged — only default-parameter tests are new.
  Dream-beta-tester oracle checked for pinned over-budget semantics; `cm` help text and the harness-map
  budget section updated.

## Honest limits

- **Usage undercounts, by design and by environment**: retention windows, span over-exclusion, and any
  harness-side auto-recall that doesn't surface as a `Read` all bias low. Hence the §Design pin: 0 reads
  is weak evidence. Phase C carries the burden of corroboration.
- **The ceiling fraction (0.6) is a chosen safety margin, not a calibrated point** — sized so the worst
  measured intra-day ambient spike (+~5 KB, 2026-06-21) fits between ceiling and cliff. Tunable; the
  ladder structure, not the fraction, is the design.
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
