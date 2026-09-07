# Defrag flow-signal + emoji index — design-of-record

**Status: draft → advisor → review-to-zero → implementation.**
Target release: **v0.4.23 (patch)** — two measured defects from the 2026-09-07 dream
session's footnotes, each root-caused at its source with a discriminating pin.

## §1 The two defects (each root-caused)

**P1 — the defrag detector flags STOCK, not FLOW (the re-nag defect).**
`defrag_candidates` (memory_status.py:1613) surfaces every indexed, non-mirror,
non-dated fact whose `body_tokens > 2.5 ×` the population MEDIAN. A roadmap/status
doc is STRUCTURALLY the longest file in any store — the flag fires EVERY dream
regardless of whether the body moved. Measured: two consecutive dreams flagged
`consolidate-memory-roadmap` at 11.6× and 11.4×; the second pass's body growth was
the fresh v0.4.22 closeout itself (added ~3h before the flag) and the dream judged
KEEP both times — a no-op judgment the detector will demand forever, because it
measures size (a permanent property) where the signal is accretion (a change).
Root cause at the source: **the detector has no memory of its own past verdicts.**
The demotion triage solved the identical re-nag class with the justify stamp
(`apply_demotion_justify`, memory_status.py:1924 — the locked CAS merge, the model
never supplies the numbers). The fix is the same pattern, symmetrically.

**P2 — the emoji flag doesn't name the offending beat.**
The DREAM ARC line's emoji check (render_dashboard.py:932) is
`any(_ui.BEAT_EMOJI_RE.search(str(b)) for b in _beats)` — an `any()` that discards
WHICH beat matched, rendering "⚠ emoji in beat(s)" (the append at :933) with no
index. Measured this pass: the flag fired, the model hunted for the offender by
re-reading its own narration, fixed it, and the fresher-file rule (render_html.py:163)
landed the fix in the archive — the system worked, but the flag cost a manual
search it could have answered in the line itself.

**P3 — the debrief mis-claimed the archive (discipline, no code).** The closing
debrief asserted "the archive keeps the flagged original" — the archive actually
surfaced the healed beat (grep: 1 hit for the fixed text, 0 for the original). The
error: the claim was verified against the LOG line (attempt-scoped by design), not
the rendered artifact. The SKILL's debrief guidance gains one sentence.

## §2 The fix (patch-shaped — no schema/TypedDict change)

**F1 — the defrag justify baseline (memory_status.py + SKILL Phase 5).**
- The state file gains `defrag_justify: {stem: {body_tokens: int, at: iso}}` — the
  demotion_justify sibling: merged under the same locked CAS writer (the
  full-state mutator — advisor A5 verified unknown-key preservation at
  control_plane.py:240-289), preserving
  commit/timestamp/stacks/beacon_snooze_until/standing_justify/demotion_justify.
- CLI: `memory_status.py --justify-defrag STEM [STEM…] [PROJECT_DIR]` — the script
  READS the fact body and computes `body_tokens` itself (script-truth; the model
  never supplies a size — the demotion discipline). **Refresh semantics, NOT the
  demotion no-op (advisor A1):** a justify ALWAYS re-stamps the script-read current
  size — defrag has no suppression clock, so a skip-if-present rule would re-anchor
  the very re-nag P1 kills (KEEP at 800 → grows to 1050 → re-flagged → justify
  no-ops at 800 → re-flags forever). "Idempotent" means an unchanged body writes
  the same value. Default: only current baseline-aware candidates (`--force` is
  repair — including re-anchoring after a real curation, advisor A3's mitigation).
  **The CLI's candidate check and the Phase-0 report share ONE baseline-aware
  function (advisor A4 + review S1):** `run_justify_defrag`'s non-force branch
  calls the SAME baseline-aware `defrag_candidates` the report's ctx was built
  from — a stem the report just listed can never be refused. The demotion mirror's
  candidate pre-read (:2101-2125) is UNLOCKED (the flock is acquired inside
  `update_project_state`, control_plane.py:257-258) — the defrag sibling follows
  the same order with the race STATED: a concurrent curation between pre-read and
  merge stamps a stale baseline, harmless under refresh semantics (the next
  justify re-anchors).
- `defrag_candidates` gains a keyword-only `baseline: dict | None = None` (PURE —
  the caller passes the state's `defrag_justify`; backward-compatible with the
  smoke callers): a stem present in the baseline is flagged ONLY when the growth
  floors pass AND the stock test still holds (advisor A2 reading A — the change
  only QUIETS re-flagged stems, never widens the surface):
  `body_tokens - baseline_tokens >= 40` AND `body_tokens >= baseline_tokens * 1.25`
  AND `body_tokens > 2.5 × median`. Both floors are required: the ≥40-token floor
  guards tiny-file noise; the ≥1.25× floor guards huge-file routine churn (a huge
  file's +10% is churn, not accretion). An un-baselined stem flags as today (stock
  — the first encounter is a genuine judgment). **Watermark semantics, stated
  (advisor A3):** the stamp is the largest size ever judged KEEP; a curation that
  shrinks the body leaves the old watermark until the next justify (or `--force`)
  re-anchors — the direction errs QUIET (never noisy), accepted, and the
  justified-line shows the watermark so the state is visible. **Malformed-baseline
  fail-open (review S3):** a `defrag_justify[stem]` entry that is not
  `{body_tokens: int, at: str}` is dropped — the stem flags as un-baselined (the
  demotion reader's fail-open mirror, :2155-2161). **The geometric ratchet, stated
  (review S4):** because a KEEP re-anchors the watermark at the new peak, an
  always-KEEP'd doc re-surfaces at ×1.25-spaced sizes (7172 → +1793 → +2241 …),
  not linearly — the accepted price of killing the re-nag; the linear alternative
  IS the re-nag.
- SKILL Phase 5 defrag step: the counter-justify path — a KEEP judgment runs
  `--justify-defrag <stem>` (report-then-apply, a `skipped` entries[] row), so the
  detector quiets until the body genuinely grows — AND after a real curation that
  dropped the body under the line, re-anchor the watermark with `--force` (repair;
  review S2 — the SKILL sentence names it, so the stale-watermark quiet zone can't
  gate re-flag at 1.25× the pre-curation peak in silence). The Phase-0 report
  renders the justification state as its OWN line, independent of the candidate
  count (the demotion idiom — advisor A6; a fully-quiet store still shows the
  watermark).

**F2 — the emoji flag names the beat(s) (render_dashboard.py).**
`⚠ emoji in beat(s): 3 — the arc bans them outside the bookends` — the 1-based
index(es) of the matching beats, from an enumerate over `_beats` instead of the
`any()` (the checker has the list at :920/932). 1-based is the product choice:
every human surface numbers passages 1-based (the archive's "Passage N",
dashboard.sections.js:320) — the record's 0-based array and the NAR gate's "indexes
0–5" stay the internal convention (advisor A7: the split is accepted; the pin
beats[2]→"3" locks the mapping). Multiple hits join (`, `); the bare phrase stays
for zero (unreachable — the flag only renders on a hit).

**F3 — the debrief archive-claim sentence (SKILL.md).** In the Phase-5 step-7
debrief guidance: claims about what the rendered archive shows are verified against
the rendered file — the log line is attempt-scoped, and the fresher-file rule
(render_html.py:163) may surface the healed record in the archive.

## §3 Pins (each discriminating on pre-fix code)

**The defrag pins are SUBPROCESS-HERMETIC at the report/CLI level (review F2):**
the pure function gains a new `baseline` kwarg, so in-process pins would fail
pre-fix by TypeError — a suite CRASH (check() counts only falsy conditions), not a
clean ✗, and it masks every pin after it. The report-level pins fail pre-fix as
clean assertion mismatches instead (pre-fix ignores a planted `defrag_justify`
state key — the :2763-2774 read doesn't extract it, extra JSON keys don't error).

- **Defrag report pins (subprocess-hermetic, the D1 pattern):** (a) a planted
  baseline equal to the stem's current body → the stem is NOT in the report's
  defrag list (pre-fix: it IS — the 2.5×-median flag fires regardless; clean
  mismatch); (b) a planted baseline below a grown body (past the +40/+1.25 floors,
  still a stock outlier) → LISTED (post-fix semantic pin — pre-fix also lists;
  its role is the full-AND contract, documented); (b′) a hand-made baseline +25%
  below a stem grown but UNDER the 2.5×-median line → NOT listed (the reading-A
  pin, advisor A2 — the change only quiets). **The (b′) fixture's baseline entry
  is necessarily hand-made relative to the population (review F3, proved):** a
  legitimately minted baseline was a stock outlier at stamp time (ratio ≥ 2.5),
  and growth preserves ratio ≥ 3.125 — the only real-system path to reading-A's
  case is median accretion between stamp and re-check, so the pin's state is
  planted and the spec says so.
- **The stamp pin (subprocess-hermetic):** `--justify-defrag` on a fixture store
  writes `defrag_justify[stem].body_tokens` equal to the script-read size (pre-fix:
  the command doesn't exist — the state file never gains the key; clean
  mismatch), preserves commit/timestamp/stacks (a pre-planted `stacks` key
  survives the merge), AND the refresh pin (advisor A1): a second justify over a
  GROWN body re-stamps the new size (baseline 800 → body 1050 → stamp reads 1050)
  — the demotion no-op is NOT inherited. Malformed-baseline fail-open pin (review
  S3): a `defrag_justify[stem]` entry that isn't `{body_tokens: int, at: str}`
  drops the entry — the stem flags as un-baselined (the demotion reader's
  fail-open mirror, :2155-2161).
- **The report-line pin (review F4):** the subprocess report's human output shows
  the justification state (stem + watermark) even with `defrag? 0` — the A6 line
  can't be dropped with the suite green.
- **The emoji pin (render):** a record with an emoji in beats[2] renders
  "emoji in beat(s): 3" — pre-fix renders the bare "emoji in beat(s)" phrase (the
  index substring fails pre-fix; the existing :2460-2461 bare-phrase pin keeps
  matching — it is a prefix of the new message).
- **SKILL-text pin:** the justify-defrag sentence (behavioral, stable — and the
  existing CM_DREAM_ARC-prefix pin auto-vets the command line). The archive-claim
  sentence ships as prose WITHOUT a byte pin (advisor A8: it guards presence, not
  the discipline, and breaks on any legit debrief rewrite).
- **The D6 exact-count bump** with the new checks.

**Out of scope (stated so the reviewer can't re-litigate):** the defrag Δ constants
(40 / 1.25) are provisional defaults, tunable — not A/B-calibrated (the
rigor-bands lesson); the stock flag stays for un-baselined stems (first encounter
is a judgment, not a skip); `archive_candidates` re-nag is a WATCH-ITEM only, not
widened without measurement (advisor A9 — the KEEP-veto token already covers the
lesson case); no schema/TypedDict change; no exit-key change; the
log line stays attempt-scoped (P3 is a discipline fix, not a log rewrite).

## §4 Ship shape

Feature branch → per-PR review → user merges → `release.sh` pre-bump (CHANGELOG
[0.4.23] first, plugin.json 0.4.22→0.4.23, the complete sweep) →
`--expect patch --finalize`. Backward-compatible: an additive state-file key, a
detector filter that only QUIETS re-flagged stems, a renderer label enrichment,
SKILL text.

## Evidence ledger

Every citation is measured: the two consecutive dream reports flagged
`consolidate-memory-roadmap` at 11.6× (2026-09-06) and 11.4× (2026-09-07) with
KEEP verdicts both times; `defrag_candidates` is at memory_status.py:1613 (the
2.5×-median stock test); `apply_demotion_justify` at :1924 and the CLI at :2070
(the sibling pattern to mirror); the emoji `any()` flag is at
render_dashboard.py:932 (the bare-phrase append at :933); the fresher-file rule at render_html.py:163; the archive
grep is 1 hit "without its glyph" / 0 hits for the original emoji beat; the
mis-claim is this session's debrief footnote. Review-measured corroboration: the
live population median is 629 tok, the roadmap measures 7172 = 11.4× today (the
second flag value reproduces), and the archive carries both 11.6×/11.4× strings.

## Amend ledger

- **amend-2 (adversarial review-to-zero, 2026-09-07):** NOT clean — 4 confirmed +
  4 suspected, all folded. F1 the :933 citation corrected to :932 (the any()) +
  :933 (the append). F2 the defrag pins are now SUBPROCESS-HERMETIC at the
  report/CLI level — in-process baseline= calls would fail pre-fix by TypeError
  (a suite crash, not a clean ✗); the report-level pins fail pre-fix as clean
  assertion mismatches (a planted defrag_justify state key is ignored). F3 the
  (b′)-fixture hand-made-state is STATED with the proof (a legitimately minted
  baseline implies ratio ≥ 2.5; growth preserves ≥ 3.125 — only median accretion
  reaches reading-A's case). F4 the A6 report line gains its own subprocess pin.
  S1 the demotion pre-read's unlocked order is followed with the benign race
  STATED. S2 the SKILL sentence names the `--force` re-anchor after a real
  curation. S3 malformed-baseline fail-open (the demotion reader's mirror). S4
  the geometric ratchet stated (×1.25-spaced re-surfacing is the accepted price;
  the linear alternative IS the re-nag). Verified-OK: the A1 refresh cannot be
  CAS-rejected (the expected_revision branch died in v0.4.0, control_plane.py
  :252-254); the emoji suffix can't split a pinned substring (the suite renders at
  width 240); the bare-phrase pin at smoke.py:2460-2461 keeps matching (prefix of
  the new message); the P1 empirical claim reproduces on the live store; the
  scope honesty holds (state-file key, never a record key).
- **amend-1 (advisor pass, 2026-09-07):** 9 findings folded. A1 the justify
  REFRESHES (always re-stamps the script-read current size) — the demotion
  skip-if-suppressed rule is a suppression-CLOCK guard and defrag has no clock;
  inheriting it would re-anchor the very re-nag P1 kills. A2 the growth rule is
  pinned to reading A (growth floors AND the stock test — the change only QUIETS;
  a reading-B bypass would newly flag and contradict §4) + the huge-file rationale
  fixed (+10% is churn, not accretion — both floors required). A3 the watermark
  semantics stated: the stamp is the largest judged size; a curation leaves the old
  watermark (errs quiet, accepted) and `--force` is the re-anchor repair. A4 the
  CLI's candidate check and the report share ONE baseline-aware function (the
  demotion read-then-check-then-mutate order) — a report-listed stem can never be
  refused. A5 verified the CAS full-state mutator preserves the new key
  (control_plane.py:240-289). A6 the justified line renders unconditionally (the
  demotion idiom — a quiet store still shows the watermark). A7 the 1-based index
  is the product choice (the archive's Passage numbering; the record/NAR 0-based
  convention stays internal; the pin locks the mapping). A8 the archive-claim
  sentence ships without a byte pin (brittleness); the justify-defrag sentence is
  pinned (behavioral, prefix-pin auto-covered). A9 archive_candidates re-nag is a
  watch-item only — not widened without measurement.
