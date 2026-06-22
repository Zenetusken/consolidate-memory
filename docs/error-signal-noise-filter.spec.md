# Spec — filter transient tool-protocol noise from the error-signal channel (+ cap)

Status: gate-1 PASS (independent spec-review: no blockers, all 10 checks verified against source + a re-run of
the measurement; 1 medium + 3 low gaps folded in) · target: cm v0.1.49 (PATCH) · scope: `extract_signals.py` +
a smoke pin

## The problem (measured)

`extract_signals.py` surfaces `is_error` tool-results as a Phase-2 **gotcha source** (`SKILL.md:391`). But
unlike human turns — which get a noise filter (`_NOISE`/`_SKILL_PROMPT`) **and** a cap (`max_n`) — the error
channel gets **neither**: every non-secret `is_error` result becomes a signal (deduped, uncapped). The result
is that Phase-2 input is flooded with **Claude's own transient tool-usage mistakes**, not environment gotchas.

**Measured across the fleet** (12 projects, 57k transcript lines — `/tmp/measure_errors.py`, a one-off, not
shipped): **189 raw** error tool-results → **186 non-secret** (3 firewall-omitted) → **77 unique**. All
percentages below are over the non-secret base (raw 186 / unique 77). Composition (unique, approximate):
`<tool_use_error>`-wrapped tool-protocol errors **52% unique (73% of raw — the headline)**, inline-script
tracebacks ~14%, lint ~4%, bare/`ls`-dump exits + infra blips ~15%. The durable-gotcha archetype the channel
exists for (the `gh pr edit`-broken case) is **~6–7 items fleet-wide**, dominated by **auto-mode-classifier
denials** ("pause before X", "rm -rf denied", "Move to branch + open PR") + a couple of genuine tool/env
limits (the screenshot-viewport cap).

**Honest framing (carry into the PR + the user report — same discipline as v0.1.48):** this is **context
HYGIENE** — less transient noise in the Phase-2 input the model already curates — **NOT signal recovery.** We
are not rescuing missed gotchas (the model already reads error text + discards transients); we are removing
the bulk of the noise it has to wade through. The honest yield is "~73% of raw error volume was Claude's own
tool-protocol retries." Don't let anyone read this as "we now capture error gotchas we didn't before."

## Mechanism (L1 + cap — the principled core; NOT a maximal regex)

### 1. Drop `<tool_use_error>`-wrapped results (the one zero-false-drop class)

A `<tool_use_error>` wrapper is **Claude Code's own tool-protocol error** (`File has not been read yet`,
`String to replace not found`, `File has been modified since read`, `No task found with ID`, …). It is the
only class that is simultaneously: **high-volume** (52% unique / 73% raw), **harness-stable** (a fixed wrapper
the harness emits, not a free-form message), and **zero-false-drop** (a tool-usage error is *never* an
environment gotcha — env facts arrive as bash stderr / exit codes, never wrapped). Add an `_ERROR_NOISE`
check in the error branch (mirroring the human `_NOISE` step): if the normalized text matches a **leading**
`<tool_use_error>` wrapper (anchored `^\s*<tool_use_error>`), `counts["noise"] += 1` and skip — do not surface
it. **Anchored, not a bare substring:** the wrapper is always at the START of a tool-protocol error, so
anchoring won't false-drop an env error that merely *quotes* the marker mid-body (a real risk in this repo,
which processes transcripts containing the marker). Verified zero recall loss vs unanchored (136/136 fleet-wide).

**Discriminator note (verified, substrate-drift watch):** a protocol-error and a bash-error tool_result have
**identical** structural keys (`content, is_error, tool_use_id, type`) — the `<tool_use_error>` marker lives
in the `content` text, there is NO structural sub-type to match instead. So matching the content marker is the
only option; **if a future Claude Code adds a structural discriminator, prefer it** (the SKILL's own
"substrate drifts" rule). Match case-insensitively on the normalized text.

### 2. Cap surviving errors at `MAX_ERRORS` — AFTER the filter

Errors are **unranked** (appended chronologically; no `score` sort — that's human-only). So the cap must run
**after** the noise filter, on the survivors: capping the *raw* list would waste cap slots on tool-protocol
noise. After `_dedup`, take `errors[:MAX_ERRORS]`. `MAX_ERRORS` is a named module constant (proposed **8** —
generous for a normal session given real gotchas are rare, but bounds a pathological flaky-loop session). It
is a **flood backstop, not a quality ranking** (no error salience exists). **Honest limit (not overstated):**
cap-after-filter is strictly better than capping raw, but NOT a guarantee — because §3 deliberately keeps the
other transient classes (inline tracebacks, lint, bare exits), a flaky-loop session can still fill the first
`MAX_ERRORS` survivor slots with transients and clip a chronologically-late durable gotcha (e.g. a denial that
fired near session end). That residual clip-risk is the accepted cost of "flood backstop, not ranking"; it
bites only when the cap binds, which is rare (post-filter fleet-wide survivors ≈ 37 across 12 projects —
per-dream a handful, so the cap almost never binds).

### 3. Do NOT add L2/L3 (the over-reach to avoid — explicitly out)

Measurement tempted a bigger regex; each fails a bar, so they are **rejected**:
- **Inline-script tracebacks** (`File "<stdin>"`/`"<string>"`) are NOT zero-false-drop: `python3 -c "import
  X"` → `ModuleNotFoundError` IS a durable env fact ("X isn't installed here") — the exact gotcha-class this
  channel exists for. Dropping it loses signal. **Keep them.**
- **Lint substrings** (`ruff`/`E501`/`mypy`) are a free-form match that rots as tools change and over-matches
  any error merely *mentioning* a linter. **Keep them.**
- Both buy only ~5–19% more drop on a channel the model already curates, at real maintenance + false-drop
  cost. The residual (tracebacks, lint, bare exits) falls to the **cap + the model's existing Phase-2
  judgment** — the right altitude.

### 4. Do NOT filter the classifier-denials

The auto-mode-classifier denials are the **highest-signal error class** (they reveal user boundaries + what
got blocked + why). They overlap the human-turn channel, but **redundancy resolves at the FACT level in
Phase 2/4 dedup — never by dropping the signal.** They must survive the filter (they carry no
`<tool_use_error>` marker, so L1 already keeps them — assert this in the test).

## The pin — a smoke test with teeth

Add a smoke invariant (reuse the v0.1.43/v0.1.48 fixture pattern: temp `HOME` + `extract()`). Fixture lines:
- a `<tool_use_error>` result → **DROPPED** (asserted absent from `signals`; `counts["noise"]` incremented),
- a bash `ModuleNotFoundError` inline-script error → **KEPT** (the explicit anti-over-drop guard — proves we
  did NOT take L2),
- a classifier-denial result → **KEPT** (highest-signal class survives),
- enough surviving errors to prove `MAX_ERRORS` caps the survivor list (a small `MAX_ERRORS` override or a
  fixture with > cap survivors), asserting the cap binds AFTER the filter.

## Contract impact → PATCH

The signal **schema is unchanged** (same canonical keyset from `_signal`); the output simply carries fewer
transient-noise rows + a bounded error count. No consumer relies on receiving *all* error results or an
uncapped list; `counts["errors"]` keeps its meaning (total `is_error` seen), filtered ones increment
`counts["noise"]` (transparency). This conflates error-protocol noise with human-harness noise in the **single**
consumer of `counts` — the human-readable `_report()` line (`extract_signals.py:350`, verified the only reader;
no cycle-record / dashboard / test reads this dict). That conflation is **intentional** — a dedicated
`errors_noise` key would gold-plate what this spec keeps minimal; just note it in the PR narrative. No
removed/renamed key, script, or flag. Backward-compatible ⇒ **PATCH** (v0.1.48 → v0.1.49).

## Out of scope

No change to the human-turn path, `_classify`, the secrets firewall, `_signal`/the canonical schema (v0.1.48),
or ranking. No L2/L3 filters (§3). No attempt to *classify* error gotchas (that's the model's Phase-2 job).

## Gates + test plan

- **spec-review (gate-1):** is L1 the right cut (vs L2/L3)? Is the cap correctly AFTER the filter + sized sanely?
  Are the classifier-denials + inline-tracebacks provably KEPT (no false-drop)? Is the honest framing accurate?
- **`/code-review` (gate-2):** the filter sits in the error branch — confirm (a) it runs on the normalized text
  (post-`_norm`, so list/str content both covered), (b) it does NOT touch the human path, (c) the cap is
  post-`_dedup` on survivors, (d) `counts` bookkeeping is consistent, (e) the firewall still precedes it.
- `python3 tests/smoke.py` green (incl. the new drop/keep/cap checks) · `mypy` clean · `sim ✓` · `plugin
  validate --strict` ✓ · dream-beta-test gate 0 FAIL.
