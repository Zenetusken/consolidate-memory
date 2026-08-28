# Budget-trajectory early-warning — the index slope, projected honestly, with staleness attached

**Status:** proposed — not yet implemented; this spec is the gate for that PR. **Scope:**
`memory_status.py` only (new `_ls_slope` + `budget_trajectory_advisory` functions, one call site
in `print_report`'s STORES section — a single invocation whose `(suffix, line)` output lands in
one of two places, never both: `suffix` folds into the EXISTING index gauge line, `line` is a new
standalone line used only for the early-warning branch). Read-only, per-node, adds no CLI flag and
no persisted schema key. Would be the next increment of the audit's enhancement program
(harness-native lens) — rides the existing `.consolidation-log.jsonl` `budget.index.after_tokens`
series the HTML dashboard already renders (`dashboard.template.html:432-442`) and the marker
plumbing `dream_timing_advisory` already reads (`memory_status.py:2144-2175`, `:1924`). Per
CLAUDE.md's versioning policy: a new function that annotates an existing report line (staleness
age, breach magnitude) and, only for the early-warning branch, adds one new report line — no
removed/renamed script or flag, no schema change, every existing install keeps working — additive
⇒ patch (decided later, at release time, from the reviewed CHANGELOG entry — not restated here as
a version number).

## The measured problem (live fleet probe, this session, read-only)

Ran the dashboard's own `lsSlope` closed-form OLS (`dashboard.template.html:433-434`), same
windowing (last ≤4 logged cycles), against the 3 real fleet nodes' `.consolidation-log.jsonl`
`budget.index.after_tokens` series:

- **consolidate-memory** (control): 24 cycles, current 1438 tok (target `INDEX_TOKEN_BUDGET`=1500,
  `memory_status.py:407`), slope −33.5 tok/cycle over the last 4 — healthy, actively shrinking;
  the index-lifecycle policy (v0.1.66–67) visibly working.
- **job-applicator-python**: 19 cycles, 2026-06-21→2026-07-04, current 2200 tok — already 47%
  OVER its 1500 target, and the uptrend is sustained across the ENTIRE 19-cycle history
  (596→2200), not a last-4-window artifact. Slope over the last 4: +130.5 tok/cycle. Projected
  against the NEXT uncrossed threshold — `INDEX_CEILING_TOKENS`=3840 (`memory_status.py:456`),
  the hard ceiling where `--pull` auto-holds new globals ("M1 holds all new pulls",
  `memory_status.py:2592-2593`) — that's `bf=(3840−2200)/130.5≈12.6` raw cycles to breach, which
  the shipped algorithm's `max(1,round(bf))` reports as **13** (not a tie case — `round(12.567)=13`
  unambiguously; the ~12.6 here is the raw pre-rounding figure, kept for the arithmetic trail, not
  the number the feature would actually print). Real, currently live risk;
  nothing today surfaces it outside a maintainer manually opening the HTML archive, whose own
  trajectory chart only ever projects toward the 1500 target and stops once already past it.
- **Doc-Flo**: the last 4 logged cycles share the same commit, across several same-day dream
  re-runs (commit `a2518667`, 2026-06-22) — no dream has run there in ~19 days. Currently 2761
  tok, 84% over its own 1500 target, un-remediated the whole time purely for lack of a run. A
  naive `lsSlope` read of that 4-point series is exactly 0.0 (four identical `after_tokens`
  values) — indistinguishable, on slope alone, from consolidate-memory's genuinely-earned
  flat/declining trend.

Confirms the roadmap's premise (a real, currently-relevant trend exists in the live fleet worth
surfacing), but the Doc-Flo/job-applicator-python contrast forces two corrections beyond the
roadmap's one-line "surface the index slope + projected breach":

1. **Staleness must ride alongside slope.** A flat reading means something different depending on
   whether it comes from a node that dreamed 0 days ago (evidence of health) or 19 days ago
   (absence of evidence). Reporting the bare slope number conflates the two.
2. **The new signal must attach to the existing over-target report, not duplicate it.** Doc-Flo is
   flat AND already 84% over its 1500 target — but `memory_status.py`'s STORES gauge (`:2584`) and
   REMEDIATION block (`:1983`, `:2490`) already report that fact unconditionally on every run,
   regardless of slope; a trend-only check (`n>=3`, `slope>0.5`) never independently re-derives
   it, and it shouldn't try to. The fix is to attach the two things that existing report is
   missing — the staleness age (correction 1) and, when computable, the ceiling-breach magnitude —
   onto that EXISTING line, rather than mint a second "over target" line beside it.

Neither fleet node's CURRENT state exercises the one branch this feature genuinely adds beyond
what's already reported: an UNDER-target index on a rising trend, projected to cross the 1500 soft
target — the literal "early" in "early-warning." consolidate-memory is under target but
flat/declining; job-applicator-python and Doc-Flo are already over target, where the STORES gauge
and REMEDIATION block already fire on every run today (see correction 2) — this feature's only
genuinely new output for those two is the ceiling-breach magnitude and the staleness suffix, not
the over-target fact itself.

However, replaying the exact ported algorithm (`_ls_slope` over the last ≤4 points, `n>=3`,
`cur<target`, `slope>0.5`, `round(bf)<=60`) against each node's FULL historical
`.consolidation-log.jsonl` series — not just its current-state snapshot — DOES exercise the
early-warning branch, repeatedly, for real nodes: consolidate-memory itself fires it at cycle 3
(cur=770, slope=124.0 → breach projected 6 cycles out) and again at cycle 16 (cur=1402,
slope=78.1 → breach projected ~1 cycle out; the index actually crossed 1500 at cycle 18 — the
projection was directionally correct, ~2 cycles out rather than the projected 1, a 1-cycle
undershoot on the exact horizon); job-applicator-python fires it similarly across cycles 3–11. So the early-warning branch
is NOT evidence-free — it has real historical firings, surfaced by the same read-only replay
method already used above — and gate 1d below is now built primarily from one of them
(consolidate-memory's own cycle-16 log, replayed against its own later history) rather than being
purely synthetic; see gate 1d.

## Design — per-node, read-only, reuses what Phase 0 already computes

- **Ported OLS, unchanged math.** `_ls_slope(ys: list[float]) -> float` in `memory_status.py`, a
  direct port of `lsSlope` (`dashboard.template.html:433-434`): with `k=len(ys)`, `sx=Σi`,
  `sy=Σys[i]`, `sxx=Σi²`, `sxy=Σi·ys[i]` over `i=0..k-1`, `slope = (k·sxy − sx·sy) / (k·sxx −
  sx²)`, returning `0.0` when `k<2` or the denominator is `0` — identical degenerate-case handling
  to the JS original.
- **Same windowing formula over the logged series — not the same underlying values as the
  dashboard's window.** `budget_trajectory_advisory(auto_mem: Path, cur_tokens: int, marker_ts:
  str) -> tuple[str | None, str | None]` builds `s` from `iter_cycle_log(auto_mem /
  ".consolidation-log.jsonl", tail=_LOG_TAIL_CAP)` — the exact shared-reader call already used
  twice in this file (`distill_history` at `memory_status.py:1294`, `usage_history` at `:1332`) —
  pulling `budget.index.after_tokens` per record, falling back to `before_tokens` then `0`
  (matching `idxTok()`, `dashboard.template.html:403`), and forward-filling any `≤0`/missing value
  from the previous point (the `carryFwd` behavior at `:420`, so a legacy or malformed record
  can't fake a zero dip). The slope fit windows to `s[-4:]` — the same "last ≤4 cycles" slice the
  dashboard computes at `dashboard.template.html:438` (`s.slice(Math.max(0,n-4))`, on the same
  line as the `// fit over the last ≤4 cycles` comment); the `n>=3` gate below uses the FULL
  series length, not the windowed slice, matching the ported code's own `n=s.length`. This is
  parity of the WINDOWING FORMULA only, not of the windowed values: `dashboard.template.html:414-
  418` builds its `CYCLES` array as `HIST` with the CURRENT pass appended (deduped by marker)
  BEFORE windowing, so in the dashboard's normal post-dream render the last-≤4 window usually
  already contains the live index reading as its final point. `s` here is built purely from
  `iter_cycle_log` — logged history only, never the live pass — so the new function's last-4 slope
  window is, in the NORMAL case (not just when the index changed since the last logged cycle
  closed), composed of different underlying points than the dashboard's own window. The live value
  anchors only the over-target/projection checks (next bullet), never the slope fit itself.
- **`cur` is LIVE, not logged** — one deliberate deviation from the ported chart. The dashboard
  has only the log, so its `cur = s[s.length-1]` (`:437`). `print_report` already holds a fresher
  number: the just-measured `ctx["index_lb"][2]` (`it`, STORES section, unpacked at
  `memory_status.py:2583` — `il, ib, it = ctx["index_lb"]`, one line below the `.exists()` guard at
  `:2582`). `budget_trajectory_advisory` takes `cur_tokens` as a parameter and anchors the over-target check
  and the breach projection on it, while the historical series still drives the slope fit. In the
  steady state the two agree (nothing but a dream writes the index); this only matters when the
  index changed since the last logged cycle closed.
- **Two-regime projection — the ceiling extension, forced by job-applicator-python's own
  numbers.** `dashboard.template.html:438` only ever projects toward `IDXB` (the 1500 soft
  target) and gates on `cur<IDXB` — once already over, it just shows "over budget," no
  projection. Correct for a chart headline, but it would leave job-applicator-python's real
  signal — 2200 tok, still climbing, heading for the hard-hold — unreported. So the ported formula
  targets whichever threshold hasn't been crossed yet: `target = INDEX_CEILING_TOKENS if
  cur_tokens > INDEX_TOKEN_BUDGET else INDEX_TOKEN_BUDGET` (both existing constants,
  `memory_status.py:407`/`:456` — no new constant; strict `>`, matching the over-target predicate
  fixed in the next bullet — NOT the dashboard's `>=`). Same gates as the original, just
  re-pointed: `n>=3`, `cur_tokens<target`, `slope>0.5`, `bf=(target-cur_tokens)/slope`, accepted
  only if `0<bf` and `round(bf)<=60` (else both `bf` and the breach count are discarded — the
  ported formula's own implausible-horizon cap), reported breach `=max(1,round(bf))`.
  **Rounding-semantics caveat (not exact parity at ties).** Python's `round()` is round-half-to-
  even (`round(2.5)==2`), while the JS reference's `Math.round()` rounds ties toward positive
  infinity (equivalent to away-from-zero only for the positive `bf` values this feature ever
  computes; e.g. `Math.round(-2.5)===-2`, not `-3`); the two disagree exactly when `bf` lands on an
  integer-plus-0.5 boundary — a measure-zero but real edge case, and one the advisory's own
  phrasing already hedges against (`~N dreams`, not an exact count). In the OVER-target regime this
  isn't actually a divergence FROM a JS behavior at all — it's new Python-only computation with no
  JS counterpart to diverge from, since `dashboard.template.html:438` gates the slope/projection
  computation itself on `cur<IDXB` and never computes a breach once already over target; "ported
  formula" above describes the shared `bf`/cap arithmetic this regime reuses, not a JS breach count
  that exists for it to match. In the UNDER-target early-warning regime (the one branch with a
  genuine JS analog) the tie divergence is real, and it is NOT caught by gate 2's `_ls_slope`
  parity pin — `_ls_slope` itself contains no `round()` call; the rounding happens one level up, in
  this function — so it is covered by its own dedicated gate instead (gate 6, below), which pins
  Python's `round()` tie behavior explicitly rather than asserting an exact formula-preserving
  parity that doesn't hold at that boundary. When `cur_tokens` is already over the soft target,
  this projection's cycle count is the ONLY new thing this feature reports there — the over-target
  fact itself is already reported elsewhere (see the next bullet).
- **Over-target reuses the existing signal; only the annotation is new (correction 2, revised).**
  `cur_tokens > INDEX_TOKEN_BUDGET` — strict greater-than, matching the STORES gauge's own `over`
  flag (`memory_status.py:2584`: `it > INDEX_TOKEN_BUDGET`) and the REMEDIATION gate (`:1983`,
  `:1989`: `index_lb[2] > INDEX_TOKEN_BUDGET`), NOT the dashboard's `>=` (`over:cur>=IDXB`,
  `dashboard.template.html:441` — a different file, a different operator; using it here would make
  the new output disagree with the existing gauge/REMEDIATION lines at exactly 1500 tokens, a
  self-contradictory pair of lines from one `print_report` run). This predicate is not new,
  though: `memory_status.py:2584`'s `⚠ OVER` badge on the STORES gauge line, and the full
  REMEDIATION block (`_remediation_section`, def at `:2471`, the "GATE active" line at `:2490-2491`,
  called unconditionally from `print_report` at `:2725`) ALREADY render an over-target state on
  every run whenever it's true —
  both fleet nodes in the measured probe (job-applicator-python, Doc-Flo) already trigger
  REMEDIATION today, on the current, unmodified codebase. So `budget_trajectory_advisory` does NOT
  re-render an "over target" sentence of its own — that would be a third independent rendering of
  the same boolean, with no justification for the duplication. Instead, when `cur_tokens >
  INDEX_TOKEN_BUDGET`, the function contributes only what those existing lines are missing: the
  staleness age (correction 1, below) and, when the two-regime projection above computed one, the
  ceiling-breach cycle count. Both fold into a short `suffix` string (see Call site) appended onto
  the EXISTING STORES gauge line, never a new, parallel line — so it can't be masked by a
  flat/degenerate trend read (Doc-Flo) without also being visibly attached to the line that's
  already showing.
- **Staleness rides along on every signal the function surfaces, whenever it's COMPUTABLE
  (correction 1, precise form).** Age-since-last-dream is computed via `_parse_ts(marker_ts)`
  (`memory_status.py:586` — the pipeline's one timestamp parser) against
  `datetime.now(timezone.utc)`, using the SAME `ctx["last_ts"]` marker `dream_timing_advisory`
  already consumes (`memory_status.py:1924`, `:2575`) — no new read of
  `.consolidation-state.json`. Two independent, unrelated crash sites exist along this path, and
  the fix is a **degradation invariant**, not an exception-tuple enumeration (an enumeration
  invites exactly the whack-a-mole that found both of these):
  **any malformed, non-string, unparseable, or out-of-range `marker_ts` → no age suffix, never
  raises.** Concretely, two guards, not one:
  - **Non-string marker (e.g. a hand-corrupted `.consolidation-state.json` with `"timestamp":
    12345`).** `_parse_ts`'s first executable line (`:598`, `ts.replace("Z", "+00:00")`) runs
    BEFORE its own internal try block — a non-string `marker_ts` raises `AttributeError` there
    (verified: `_parse_ts(12345)`, `_parse_ts(12345.6)`, `_parse_ts(True)`, `_parse_ts({"ts": "x"})`
    all raise it — a FALSY non-string (`{}`, `[]`, `0`) returns `None` instead, stopped by the
    `if not ts` guard at `:596-597` before `:598` is reached), which is in neither `_parse_ts`'s internal `(ValueError, TypeError)` guard
    (`:599-602`) nor a naive `(OSError, OverflowError, ValueError)` wrapper around the call. Guard:
    `isinstance(marker_ts, str) and marker_ts` BEFORE ever calling `_parse_ts` — the same
    precondition `dream_timing_advisory` already checks at `:2164`, reused here as a precondition,
    not inherited as a shared code path.
  - **Out-of-range string (e.g. `'9999-12-31T23:59:59-14:00'`).** Passes the isinstance guard and
    `_parse_ts`'s own `fromisoformat` parse, then raises `OverflowError: date value out of range`
    from its OWN later, unguarded call at `:605`, `dt.astimezone(timezone.utc)` — outside
    `_parse_ts`'s internal try/except entirely (empirically confirmed). Guard: wrap the
    `_parse_ts(marker_ts)` call itself in this function's own
    `try/except (OSError, OverflowError, ValueError)` — a new, narrower guard specific to this call
    site, NOT a reuse of `dream_timing_advisory`'s `:2171` guard (that guard wraps a structurally
    different, manual `datetime.fromisoformat(marker_ts...).timestamp()` computation, not a call
    into `_parse_ts`, and this function never calls into it).
  Both guards are required together — the isinstance check alone leaves the out-of-range-string
  case open; the try/except alone leaves the non-string case open (it fires before `_parse_ts`'s
  own try block is ever entered). Both degrade to no age suffix, same end-user-visible outcome as
  `dream_timing_advisory`'s own degrade path but reached via this function's own, independent
  mechanism. (The underlying `_parse_ts` gaps are preexisting and latent in the shared function
  itself, one `dream_timing_advisory` happens never to hit only because it never calls `_parse_ts`
  for this purpose — this spec works around both at the new call site rather than also patching
  `_parse_ts`, which is out of scope here.) Whenever the age IS computable and the function fires
  (see the silence rule below) it appends a factual "last dream ~Nd ago" suffix, never used to
  suppress or recolor the line, and deliberately with no invented "stale after N days" verdict —
  this repo's rigor-tier bands are the documented example of a threshold that must not be back-fit
  without a calibration log, and a fresh magic number here would repeat that. The reader — human or
  model — judges an over-target flag from a node last dreamed 19 days ago differently once the age
  is in front of them; the mechanism's only job is to never omit a COMPUTABLE age once a signal is
  already showing — a signal firing with the age genuinely uncomputable (a malformed marker) is not
  a violation of that invariant, it's the invariant's own explicitly-scoped edge (see gate 4, which
  now asserts this composed state directly rather than only the always-silent case). Correction 1
  does not require a line for a healthy node — it requires that whichever surface a signal reaches
  (the existing gauge line's `suffix` when over target, or the new early-warning `line` when not —
  see Call site) can't be mistaken for a fresher one (see the silence rule).
- **No new persisted schema key (deliberate).** Nothing here writes into `seed_record()`'s
  `Budget`/`IndexBudget` literal, so no `CycleRecord`/`Budget`/`IndexBudget` TypedDict change
  (`memory_status.py:106-119`, `:189-195`), no `render_dashboard.py` change, no `SKILL.md`
  schema-block change, and `validate_cycle_record` (`memory_status.py:2284`) has nothing new to
  check. Justification: (a) every input — the log series, the live index measurement, the marker
  timestamp — is already durable and re-derivable on demand from what Phase 0 already reads;
  persisting a redundant snapshot of a number one function call away buys no future capability.
  (b) the pre-1.0 cycle-record/`sync_global` surface is the one currently under consideration for
  a freeze — a display-only advisory has no reason to add a claim on it. If a later release wants
  this trend fleet-visible (e.g. folded into `sync_global.py --utility`), that's new scope with
  its own spec, not this one.
- **Call site.** `budget_trajectory_advisory` is defined immediately after `dream_timing_advisory`
  (`memory_status.py:2144-2175`) — same "pure, never-crash, ctx-value-in" shape — and called ONCE
  from the STORES section, right where the index gauge line is built. It returns a `(suffix,
  line)` pair: `suffix` (`str | None`) is folded directly into the SAME f-string that already
  builds `over + ceil + cliff` at `memory_status.py:2594-2595`, so an over-target node's
  staleness/breach annotation lands ON the line that already carries its `⚠ OVER`/`HARD CEILING`
  badges, never on a separate one; `line` (`str | None`) is a wholly new, independently-`add()`-ed
  line, rendered with the section's own `_ui.c`/`add` style (mirroring `dream_timing_advisory`'s
  own call at `:2575-2577`) alongside the existing `hooks:` sub-line (`:2596-2599`) — used ONLY for
  the early-warning branch (under target, rising trend, breach projected), the one case with no
  existing line to attach to. At most one of the two is non-`None` for any given node: being over
  target and being under-target-with-a-rising-trend are mutually exclusive by construction.
- **The silence rule: fire only on a real signal, exactly like `dream_timing_advisory`'s own
  `return None`.** `dream_timing_advisory` itself stays silent when there's nothing to advise
  (`if tier == "LIGHT": return None`, `memory_status.py:2161-2162`) even though it sits in the
  same report — matching that, not "always render," is what "no-nag" means here. Concretely:
  `suffix` is non-`None` IFF `cur_tokens > INDEX_TOKEN_BUDGET` AND (the staleness age is
  computable OR a ceiling-breach projection was computed) — the bare over-target boolean is NOT by
  itself sufficient, because the two things `suffix` exists to carry can both be unavailable at
  once: a project that's over target but has never run a dream (`has_marker` False → `marker_ts`
  empty → no age to report) combined with a log too short to project from (`n<3` → no breach
  computable) would satisfy `cur_tokens > INDEX_TOKEN_BUDGET` with nothing left to actually
  append, which the bare-boolean IFF would render as a dangling, content-free separator on the
  STORES gauge line rather than genuine new information. The tightened condition collapses that
  case to `None` instead, so `suffix` is never non-`None` with empty content — it decorates a line
  that was ALREADY going to render, and it never introduces a new over-target claim on its own, but
  it also never fires as an empty no-op. `line` is non-`None` IFF `cur_tokens <= INDEX_TOKEN_BUDGET`
  AND a breach projection was computed (`n>=3`, `cur_tokens<target`, `slope>0.5`, a valid `bf`) —
  the early-warning branch, the feature's one wholly new rendering surface. A node that is under
  its soft target with a flat or declining fit (consolidate-memory: 1438<1500, slope −33.5) gets
  BOTH `None` — silent, the healthy case costs nothing, same as the beacon's "0 missing AND 0
  stale → silent" gate (`session_beacon.py:84-86`). This also resolves correction 1 without an
  always-on line: a silent healthy node can never be confused with Doc-Flo, because nothing is
  presented for it to be confused with; a node whose existing gauge/REMEDIATION lines are already
  showing (over target) gets its staleness/breach `suffix` attached whenever there's something to
  attach, so it can't be mistaken for a fresher one either — and when neither age nor breach is
  available (see above), it falls back to silence rather than an empty decoration; gate 7 below
  pins that fallback explicitly.
- **Read-only, matching `session_beacon.py` exactly otherwise.** Never writes any file (log,
  state file, or index). A parse/read failure degrades exactly like `dream_timing_advisory`
  already does: `iter_cycle_log`'s existing malformed-line skip and this function's own
  `try/except` around `_parse_ts` (per the Staleness bullet above) never let a garbage or
  out-of-range `marker_ts` raise. Rendering `line` needs a guard, but that guard does not
  exist yet anywhere in `memory_status.py` today — `grep -n "if line\b"` over the file finds no
  such construct (the file's only `if line` hit, `:1633`, is an unrelated markdown-header check
  inside a different function) — so this PR WRITES a new `if line: add(...)` at the call site,
  mirroring the existing `if advisory: add(_ui.li(advisory))` pattern immediately above it at
  `:2576` (that guard covers `dream_timing_advisory`'s own, different return value — not this
  feature's — and isn't itself extended, only imitated); a plain `(suffix or "")` fold into the
  gauge f-string (for `suffix`), plus `print_report`'s no-exit-code-contract-beyond-"don't crash
  Phase 0" posture, are all unaffected.

## Alternatives rejected

A `sync_global.py --trajectory` fleet-wide sweep — rejected. Cross-project sweeping is exactly how
this problem was validated (a deliberate 3-node probe run this session), but that was a one-off
VALIDATION step, not the shipped shape: `sync_global.py` already owns every fleet-wide concern
(`--staleness`, `--utility`, `--harvest`, `--workflows`), and folding trajectory in duplicates the
same module-boundary precedent `docs/fleet-staleness-report.spec.md`'s own "Alternatives rejected"
already states in the opposite direction ("putting the sweep in `memory_status` is `sync_global`'s
exclusive competence") — a per-node trend read belongs in the per-node report for the identical
reason, run in reverse. A new `SessionStart` hook (the `session_beacon.py` pattern) — considered,
rejected: the beacon fires every session under a hard 2s budget with no subprocess allowed
(`hooks/hooks.json:9-10`, `session_beacon.py:12-18`) — right cadence for "is this store behind the
fleet," wrong cadence for a signal that only changes once per completed dream, and `print_report`
already assembles every input this needs for free (see Design). Persisting the slope/breach as a
new cycle-record field — considered, rejected; see Design. Calibrating a numeric "stale after N
days" verdict — rejected outright; no absorption/staleness calibration log exists yet to fit one
against.

## Out of scope (v1)

No fleet-wide aggregation anywhere in this feature — `sync_global.py` is untouched. No
blocking/gating behavior — this never sets `remediation.required`/`over_ceiling`, never holds a
pull, never fails a gate; the existing STORES `over`/`ceil` flags and `remediation` block
(`memory_status.py:2045`, `:2592-2593`) remain the sole enforcement path — AND, per the revised
Design above, the sole PRIMARY reporting surface for the over-target boolean too. This feature
only ever annotates that existing surface (staleness age, breach magnitude) or adds the separate
early-warning line; it never re-derives or re-states the over-target boolean itself. No new CLI
flag — the
check runs unconditionally as part of the default `print_report` path (silent unless it finds a
signal, per the silence rule); `--json` and `--triage` are untouched. No persisted schema key, no
`CycleRecord`/`Budget`/`IndexBudget` change, no
`render_dashboard.py` or `SKILL.md` schema-block change. No calendar-day staleness
threshold/verdict — only the raw age is reported, never a computed "stale" vs "fresh" judgment. No
non-index budget series (`claude_md`, `global_claude_md`, `recall_facts`) — v1 is `budget.index`
only, the one series the fleet probe actually measured and the one gated by a hard ceiling. No
projection beyond a 60-cycle horizon (the ported formula's own cap) and no attempt to project past
the hard ceiling once already over it (the existing `ceil` line already owns that state).

## Acceptance gates

1. Sandboxed fixture, four synthetic `.consolidation-log.jsonl` histories:
   (a) a shrinking, under-target series (consolidate-memory shape: 1438<1500, slope −33.5) —
   `budget_trajectory_advisory` returns `(None, None)`: silent, the healthy case renders nothing
   new.
   (b) a sustained-uptrend series already past `INDEX_TOKEN_BUDGET` (job-applicator-python shape:
   2200 tok, slope +130.5) — returns a non-`None` `suffix` (staleness age + the ceiling-breach
   cycle count) and `line=None`; the existing STORES gauge `⚠ OVER`/REMEDIATION block still
   carries the over-target claim itself, now with the new suffix attached to the gauge line, never
   a second independent "over target" sentence.
   (c) a flat, stale, over-target series (Doc-Flo shape — 4 identical logged `after_tokens` points,
   old marker) — returns a non-`None` `suffix` carrying ONLY the staleness age (no breach count —
   the flat slope fails `slope>0.5`) and `line=None`; the age is visibly attached to the existing
   gauge/REMEDIATION line, never presented as a freestanding claim, and never indistinguishable
   from fixture (a)'s silence.
   (d) a fixture FROZEN FROM a real historical replay, not a live read of one: the real
   cycle-3/cycle-16 numbers measured against consolidate-memory's own
   `~/.claude/projects/-home-drei-project-consolidate-memory/memory/.consolidation-log.jsonl`
   during this spec's design are transcribed into a synthetic, hand-authored, inline
   `.consolidation-log.jsonl` fixture — written the same way every other `.consolidation-log.jsonl`
   fixture in `tests/smoke.py` already is (roughly 15 existing sites, each a literal JSONL string
   passed to `.write_text(...)`; none of them reads a live personal store) — never a direct read
   of, or verbatim commit of, the maintainer's real store outside the repo (consistent with
   CLAUDE.md's "Never commit personal memory... only `memory/.gitkeep` belongs on the remote"; the
   real log lives outside the repo, is maintainer-machine-only, and keeps growing past cycle 16
   with every dream run, so a test that reads it directly would not exist on a fresh checkout or
   CI runner, and would silently drift as the log grows). The frozen fixture reproduces, as of its
   own cycle 16 (cur=1402, `n>=3`, last-≤4 slope=78.1, a valid `bf`, breach projected 1 cycle out):
   `cur_tokens<INDEX_TOKEN_BUDGET` and `slope>0.5` hold, so the function returns `suffix=None` and
   a non-`None` `line` — the feature's one wholly new, standalone report line, carrying the
   projected breach count and the staleness age together. This is a plain regression pin, not an
   accuracy-validation claim: given the fixed, frozen fixture, `_ls_slope`, the windowing, and the
   rounding are all deterministic, so the gate asserts the EXACT current breach count (1), not a
   tolerance band — a tolerance chosen after already knowing the one outcome it's tested against
   would only widen the window in which a future silent change to the slope/rounding/windowing
   math could drift undetected. Separately, and NOT part of this gate's pass/fail assertion, the
   real log's own subsequent history is noted for context: the index actually crossed
   `INDEX_TOKEN_BUDGET` at cycle 18, two cycles after the cycle-16 projection point — a single
   historical sample, which establishes nothing about real-world projection accuracy on its own (no
   mechanism is proposed here to accumulate further samples over time, unlike e.g. the demotion-gate's
   cadence-based calibration) and is recorded only as color, not as a tested tolerance (see "The
   measured problem" for the fuller replay, which also fires the branch at consolidate-memory cycle
   3 and across job-applicator-python cycles 3–11). A second, purely synthetic under-target/rising
   series (`cur_tokens<INDEX_TOKEN_BUDGET`, `n>=3`, `slope>0.5`, a valid `bf`) is kept alongside it
   to cover a projected-crossing shape the historical fixture doesn't happen to exercise (e.g. a
   horizon near the 60-cycle cap) — synthetic, but no longer the ONLY fixture evidencing this
   branch.
2. `_ls_slope` protected from silent drift by TWO mechanisms, not a live behavioral comparison —
   this project has no JS execution capability (zero-runtime-dependency/stdlib-only per CLAUDE.md;
   CI's only Node.js use is `npm install -g @anthropic-ai/claude-code` for `claude plugin
   validate`, never JS execution), so a same-process parity pin like `_ui.py`'s Python-vs-Python
   drift pin (both sides live, re-run every test) is not achievable here:
   (a) a STRUCTURAL SOURCE-TEXT pin on the literal `lsSlope` formula in
   `dashboard.template.html:433-434`, matching this file's own existing precedent for pinning JS
   in this exact template — the v0.1.68 Track D3 pins (`tests/smoke.py:3551-3568`), which assert
   via `_re.search(...)`/substring `in _tpl54` against the raw template TEXT, never by executing
   it;
   (b) an independently hand-computed numeric fixture table (several `ys` series worked out by
   hand, including the `k<2` and zero-denominator degenerate cases) checked against `_ls_slope`'s
   actual output — real behavioral coverage on the Python side, even though the JS side can only
   be pinned structurally.
   Residual weakness, stated explicitly rather than implied away: unlike the `_ui.py` pin, which
   re-executes both implementations every run and so cannot silently drift, mechanism (a) is a
   source-text match — if `lsSlope` is edited later without a synchronized update to the pinned
   string, the structural pin can go stale silently (it just stops matching, or, worse, keeps
   matching a still-textually-similar but behaviorally different formula) rather than catching a
   live behavioral divergence. This is an accepted, documented gap, not a claimed guarantee.
3. A fixture where `cur_tokens` (the live, freshly-measured value passed in from `print_report`)
   diverges materially from `s[-1]` (the historical series' own last logged point) — e.g. the
   index has grown past `INDEX_TOKEN_BUDGET` since the last logged dream closed, so the log's last
   point is still under target but the live measurement is over. Exercises the ONE place the
   design intentionally departs from the parity-pinned reference implementation (where `cur =
   s[s.length-1]`, self-consistent with the slope fit) — gate 2's `_ls_slope` pin never exercises
   this composed behavior, since it only pins the isolated OLS on a bare `ys` list. Expected: the
   over-target `suffix` reflects the LIVE `cur_tokens` (fires even though the logged series' last
   point alone would not have crossed the threshold); the slope itself still derives from the
   unmodified logged `s`, but the breach projection's magnitude (`bf=(target-cur_tokens)/slope`)
   is anchored on the LIVE `cur_tokens` in its numerator too — consistent with the "`cur` is LIVE"
   bullet above — never silently reconciled against `s[-1]`; the divergence is surfaced, not
   hidden.
4. Read-only under every input, asserted as the DEGRADATION INVARIANT stated in Design's Staleness
   bullet, and — critically — asserted on a FIRING series (not just the always-silent case), so the
   gate actually exercises the composed "signal fires, age omitted" state the invariant permits:
   - **4a — non-string marker on a firing series.** `marker_ts = 12345` (an `int`, e.g. from a
     hand-corrupted `.consolidation-state.json`) combined with a rising, under-target log (the
     gate-1d-shaped series). Expected: `isinstance(marker_ts, str) and marker_ts` fails before
     `_parse_ts` is ever called (no `AttributeError` from `.replace()` on a non-string), the early-
     warning `line` still fires with the breach content, and the age is simply absent from it — not
     a crash, not a silently-`None` `line`.
   - **4b — parseable-but-out-of-platform-range marker on a firing series.** A value like
     `9999-12-31T23:59:59-14:00` or `0001-01-01T00:00:00+14:00`, combined with the same firing
     series. Expected: `_parse_ts` parses the string successfully, then raises `OverflowError: date
     value out of range` from its own unguarded `dt.astimezone(timezone.utc)` call at `:605` — sitting
     OUTSIDE `_parse_ts`'s own `:599-602` try/except entirely — which this function's own dedicated
     `try/except (OSError, OverflowError, ValueError)` around the `_parse_ts(marker_ts)` call catches
     (per Design's Staleness bullet); `line` still fires with the breach content, age absent.
   - **4c — malformed/truncated log line.** Skipped per `iter_cycle_log`'s existing contract; no
     behavior change from what that shared reader already does.
   All three: no write to `.consolidation-log.jsonl`, `.consolidation-state.json`, or the index, and
   no uncaught exception propagates out of `print_report` — verified, not assumed, since 4a and 4b
   are two independently-reachable crash sites along the SAME `_parse_ts` call path, not one bug
   with two descriptions.
5. `seed_record()`'s output is byte-for-byte unaffected (no new key) — confirmed by the existing
   cycle-record smoke coverage, unchanged.
6. A tie-boundary fixture for the rounding-semantics caveat above: a synthetic series engineered so
   the under-target early-warning `bf` lands exactly on an integer-plus-0.5 value (e.g. `bf=2.5`) —
   pins Python's `round()` behavior at that exact tie (`round(2.5)==2`, reported breach `=2`)
   explicitly, documenting the divergence from the JS reference's `Math.round()`
   (`Math.round(2.5)===3`) rather than assuming parity holds there. This gate exists precisely
   because gate 2 doesn't cover it — `_ls_slope` itself contains no `round()` call, and the
   over-target ceiling-breach branch has no JS counterpart to pin against at all (see the
   Two-regime-projection caveat in Design) — so it's a pinned-known-divergence gate, not a parity
   gate: it catches a future accidental change to the rounding function, not a JS/Python mismatch
   that's expected to disappear.
7. A fixture for "over target + no marker + n<3": `cur_tokens > INDEX_TOKEN_BUDGET`,
   `has_marker=False` (so `marker_ts` is empty → no age computable), and a log short enough that
   `n<3` (no breach computable) — asserts `budget_trajectory_advisory` returns `suffix=None`, per
   the tightened silence-rule condition in Design (over-target alone is not sufficient; either age
   or breach must actually be computable), rather than an empty-content decoration on the STORES
   gauge line. None of fixtures 1a–1d exercises this combination, since each of them assumes either
   a marker or a log long enough to project from.
8. Full gates: smoke + sim + mypy + manifests.