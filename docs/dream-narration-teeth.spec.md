# Dream narration teeth — design-of-record

**Status: amend-3 folded (re-review round 2) → final re-review → implementation.**
Target release: **v0.4.19 (patch)** — additive detector + additive beta-oracle family; legacy records render.

## §1 Context (measured)

A post-dream audit (2026-09-06, the user-requested audit of the v0.4.18 LIGHT pass) measured a
contract violation class the harness's existing gates cannot see:

1. **The dream arc was fabricated at record-fill.** The persist gate (exit 4) counts the
   RECORD's `dream.beats` — self-reported data. The audited pass narrated 2 of 6 beats in the
   conversation and wrote all 6 into the record; the gate passed cleanly. The SKILL names this
   defect: "Filling the record INSTEAD of narrating is a defect, not compliance."
2. **Phase 2 was skipped silently.** The mandatory session-signal extractor never ran and no
   `entries[]` skip-justification was recorded — the SKILL's "Run it, or record why you didn't"
   rule has no teeth.
3. Corollaries measured in the same audit: the Phase-0 panel self-truncated (a `sed -n '1,30p'`
   hid the SIGNALS/detector rows), the Phase-1 re-audit verdicts never emitted, the distill
   verdict never narrated.

The existing persist gates are record-side: the procedure-integrity detector (exit 3, the
0/0/0-verification lazy-skip) and the arc-completeness gate (exit 4) both read the record. **The
conversation side is the missing ground truth** — and the conversation IS available to the
scripts: the dream's own session transcript (the same JSONL `extract_signals.py` already reads,
including at persist time, since the model's narration lines land in the transcript as they are
emitted).

## §2 Design — the conversation-truth detector

New detector module **`dream_procedure.py`** (stdlib-only, sibling of the render chain),
invoked by `render_dashboard --persist`'s judgment step (alongside the existing gates), and as a
new family in the beta oracle.

Inputs: the record's `dream` block + `entries[]`, the session id, and the transcript reader
(extract_signals' transcript-resolution machinery — reuse, don't duplicate).

**NAR — narration verification.** For each checked text — the sleep stanza (the `dream.sleep`
field) plus the six `beats` entries (the five phase beats and the surfacing line, the last beats
entry; the WAKE beat is post-persist and correctly unchecked) — the transcript's assistant
**text blocks** within the pass window must contain that text
(normalized: whitespace-collapsed, per-line `"> "` blockquote prefixes stripped BEFORE
collapsing, italics markers and surrounding asterisks stripped, trailing/unpaired asterisks
stripped, case preserved). The match domain is TEXT blocks ONLY (`content` blocks with
`type == "text"`): the NAR extraction is NEW — assistant-role lines only, `_human_text`'s block
filter is the pattern, not a callable precedent (extract_signals' own pipeline skips assistant
messages entirely); thinking blocks never count (a fabricator rehearses beat text in reasoning
before record-fill); never `tool_use.input`, never `tool_result`. This is the
load-bearing discrimination: the record-fill Write/Edit's tool_use input carries the full dream
block and its tool_result echoes the post-edit file content — both inside the window — so a
message-level matcher would find all six beats contained on the exact fabrication this detector
exists to catch. The contract says the record mirrors the performed narration, so exact-normalized
containment is the check; a beat present in the record but absent from the conversation's text
blocks = a fabricated beat. All checked texts must narrate — the contract has no partial-arc
allowance. The asymmetry argument settles the tolerance question: a false exit-4 is cheap and
self-healing (persist-then-exit — the record is already logged; narrate and re-render in the same
window), while a false clean is permanent and invisible (a fabricated record archived as
performed, poisoning record-side calibration) — measured on 12 passes where mirrors are
exact-or-absent, no paraphrase case. Uncertain → fire, loud and specific. Two guards: on any gap
the window is re-read once (~500 ms later) and the exit fires only if the second read confirms —
scoped to the sub-second same-message flush race; the 5-minute write-behind class (measured on
the subagent path) is NOT rescued by any in-call re-read and is handled like every other
false-positive class, by persist-then-re-render; and the gap panel names each missing checked
text (sleep by name, beats by record index 0–5) + its first ~15 words, so the backfill is
targeted, not just loud. Known property
(documented, not solved): exact containment assumes the mirroring model pastes verbatim — a
lightly-rewording model would false-fire, and this repo's 12-pass history is one model's
behavior; the pin suite documents the normalizer, harness-map.md documents the model-dependence.

**EXT — extractor accountability.** The pass window must contain an executed `extract_signals.py`
invocation in the Phase-2 form (`--json` or the human table; `--recalls` does not count), OR an
`entries[]` row whose `reason` begins with the canonical skip marker **`extractor-skip:`**
followed by a non-empty why. The marker is defined by the SKILL change in this release (§3
Docs) — a fixed token, never free-form prose, because a prose matcher would false-exit-3
legitimate skips ("no candidates this cycle" wouldn't match). Absent both = an unaccounted
silent skip — but only in a window WITH content: the seam applies to EXT identically (zero
content after `since` ⇒ EXT degrades with NAR; a call cannot be verified in a window with no
content, and rotated-away evidence must not hard-block an otherwise-valid dream).

The match is anchored on **execution**, not the string: only `tool_use` records with
`name == "Bash"` whose `input.command` invokes `extract_signals.py` as a `python3` argv (the
token preceded by a `python3`/`python` invocation word) count — not `grep`/`sed`/`cat` targets,
not `$(…)` substitutions, not assistant-text mentions, not tool_result echoes (all measured in
the live transcript as non-invocations). Residual accepted and documented: a same-window dev
`--json` run satisfies EXT (the signal-gathering did run and its output could have entered the
pass) — a LOW false-clean, tolerable against the silent-skip class it closes. The SKILL's
`CM_DREAM_ARC=1` prefix cannot discriminate (measured: dev runs carry it too). EXT shares NAR's
flush fragility (a buffered Bash `tool_use` line can be missing at scan time → a false exit-3)
and self-heals identically: persist-then-re-render, where the extractor run now visibly precedes
the persist call.

**Window scoping.** The pass window = `since = marker.before_timestamp` **as seeded in the record
at Phase 0** (captured from the PRE-stamp state file) to the persist moment — tiled per store, so
the previous pass's narration is always outside the current window. The state file must NOT be
read for the anchor at persist time: Phase-5 step 5 re-stamps it with the current pass before
`--persist` runs, so a persist-time read yields since = now and an empty window on every real pass
(reconcile_marker never rewrites the record's seeded value). Measured stress case: rec11–rec14
ran within ~11 h in one session file with tight tiled windows, and rec4/5/6 share a byte-identical
surfacing beat without any leak. Reuse `extract_signals`' `_window_transcripts` verbatim (glob
`*.jsonl`, mtime-prune, per-line since filter, markerless→keep-all fail-open). The transcript pool
resolves from the record's session / the persist_dir store identity — NEVER ambient cwd:
`render_dashboard` operates cross-cwd today (the usage-clock fallback ladder), and a wrong-store
pool whose dream falls inside [since, now] would satisfy NAR on a fabricated record with a
byte-identical scripted beat — a cross-project false-clean in the forbidden direction. Documented
leak surfaces, accepted consciously: (a) a re-run after an exit-4/exit-3 sits inside the retry's
window — the failed attempt's narration can satisfy NAR on the retry; that is arguably "performed"
(it was narrated and mirrored before the gate fired) — and the retry's duplicate re-render
heals the cycle FILE's `narration` block when the recomputed verdict differs (the model cannot
heal a script-injected block; the log line stays attempt-scoped per F-2, and the archive's
fresher-file rule surfaces the healed verdict); (b) a missing state file at Phase 0 —
whether the first pass or a mid-life loss (cleanup, corruption, store migration; the measured
session file spans 9 days) — seeds `before_timestamp=""` and the keep-all fail-open; only a true
first pass has nothing prior to leak; mid-life loss plus surviving prior dreams (whose scripted
sleep/surfacing lines are byte-identical across passes) is the accepted residual. Cost budget: a
persist-time rescan of the live session file parses ~27.5k lines (measured); ~1–2 s is acceptable
for the terminal step — no caching, correctness first.

**Degrade boundary (the honest case).** A transcript that is missing/unreadable (headless
runner, a harness that rotated it early) cannot be verified — the detector emits a LOUD warning
panel ("conversation-truth unverifiable — transcript unavailable") and proceeds; it does NOT
fabricate a pass (teeth-loss-never-clean: the absence is stated, never silent) and it does NOT
hard-block an otherwise-valid dream on a rotated log (a hard block would make every
headless/cleanup-rotated dream un-finishable; rotation is rare but real — the measured session
file spans 9 days). The seam is decidable, not ambiguous: any line the reused per-line filter
keeps within the window (`ts > since`, or ts-less/unparseable — the filter keeps those too, never
`≤ since`) ⇒ the pass's conversation exists ⇒ NAR fires on gaps (a fabricated pass always leaves
in-window content — the record-fill tool call itself); zero kept lines within the window ⇒
unverifiable ⇒ degrade. One unopenable pooled file is SKIPPED (the reused machinery's
skip-and-continue convention — a mid-scan chmod/gc race on one of several files must not degrade
an otherwise-verifiable window); unavailable means nothing could be READ at all. Only the
zero-content case degrades, and it degrades BOTH arms (see the EXT section). Stated AND persisted — on EVERY judged
persist, not just the degraded one: before the persist append, the record gains an additive
optional block — `narration: {"verdict": "verified" | "degraded" | "failed", ...}` (failed
carries the gap indexes; the arms' verdict is computed regardless of the record-side outcome —
`verified` when no gaps, and suppression affects only the panel and the exit ladder) — the block
on the log line is THAT attempt's scan result, so the
archive can render verified / degraded / failed per dream and the beta absent-block rule has a
single meaning: absence ⇒ pre-feature, which the min_version gate skips. Legacy records and
renderers ignore unknown keys (validate_cycle_record warns only on wrong-container types, never
blocks). Without the persisted verdict, a degraded pass would be indistinguishable from a
verified one forever. This is also a load-bearing keystone for every existing pin: the smoke
persist-gate fixtures are hermetic records with no `session` key under a temp HOME (an empty
transcript glob) — "no transcript" must DEGRADE (no exit change) or all six existing pins break;
that is a pinned contract, not an accident of the code path.

**Exit-code integration.** NAR gaps → exit 4 (incomplete dream arc — the conversation-side arm
of the existing class). EXT unaccounted → exit 3 (procedure integrity — the Phase-2 lazy-skip's
silent cousin). Three integration traps are pinned: (a) **ordering** — all four verdicts and the panels'
visibility are computed BEFORE the single print (`render_dashboard` prints once, then persists,
then exits; the exit-3/exit-4 renders return without a second print, so a compute-after reading
of "run after the record-side checks" would lose the gap-naming panel on exactly the renders that
need it); the NAR gap panel is suppressed iff the record-side arc fails (pin (6)'s "no
contradictory NAR panel" is a stdout contract); only the EXIT ladder stays ordered after the
record-side checks, so same-render precedence stays 5 > 3 > 4 and a 4/6 record still exits 4 with
"4/6 beats" (NAR never double-reports on a record whose arc already fails); (b)
**cue split** — the fixed exit-3/exit-4 `dream_cue` stderr lines are record-side remedies; NAR
and EXT carry their OWN cue lines naming the conversation-side remedy (narrate the missing beats
in the window / run the extractor or record the `extractor-skip:` marker), because the cue is
what the model acts on; (c) **precedence** — both-violating → 3; arc+unstamped → 4 then 5 on
re-render (the existing key). The persist gates' panels name the missing beats and the extractor
gap specifically.

**Beta-oracle family.** `beta_checks.py` gains a `narration` family: same two checks, run from
the record + the fixture transcript; a fabricated-beat fixture (record with 6 beats, transcript
narrating 2) → FAIL; an unaccounted extractor → FAIL; the skip-note case → clean. The family
re-fires every QA run — the dynamic half of the harness catches regressions in the detector
itself. Honest scope: the fixtures cover the DETECTOR (hermetic record + transcript pairs), never
an individual rotated dream — nothing snapshots live transcripts at persist, so the oracle can
never re-check a specific past pass; per CONTRACT.md precedent the oracle must also treat an
ABSENT `narration` block in latest.json as teeth-loss — gated by the `_latest_capture_check`
scaffold (min_version + recency), or every pre-0.4.19 record and the frozen cycle_probe fixtures
fail the family forever.

## §3 Verification — the pin list

In-process: (1) the normalizer (whitespace/asterisk/`"> "`-prefix stripping — per-line prefixes
stripped BEFORE collapsing, so a wrapped blockquote beat matches; a line-wrapped or
trailing-asterisk-differing beat matches; a one-word drift fails: documents the
exact-containment decision); (2) the transcript scanner against hermetic fixture JSONLs —
7-narrated (sleep + 6 beats) → clean; 2-narrated → 5 named gaps with beat indexes; beat-text
mismatch → gap; the surfacing line counted as the last beats entry; sleep counted by name; the
TEXT-block domain — beats present only in tool_use inputs / tool_result echoes → gaps; thinking
blocks never count; (2a) the record-fill attack negative (the BLOCK-class pin) — a fixture whose
only copy of the beats lives in a record-fill Write/Edit tool_use input + its tool_result echo,
no text-block narration → all named gaps; (3) the EXT anchor — a `grep … extract_signals.py`
command, a text-block mention, and a tool_result echo → all unaccounted; `--recalls`-only →
unaccounted; `--json` → clean; (4) the skip-note marker — `reason` with marker + why → clean;
marker without a why → unaccounted; free-form prose → unaccounted; (5) the degrade keystone +
seam — a session-less record / empty session dir under `--persist` → loud panel, exit unchanged;
zero kept transcript lines after `since` → BOTH arms degrade, no exit-3 (the session-ful rotated
fixture — a rotated transcript cannot contain the extractor call either), while any kept line +
missing beats → fire; the six existing legacy pins ride on the degrade side, and their appended
records now gain the `narration: {"verdict": "degraded"}` block (expected-content updates where a
pin compares the appended JSONL); (6) precedence — a 4/6 record + empty transcript → exit 4 with
"4/6 beats", no contradictory NAR panel; record-arc wins; (7) the re-read retry — a gap present
on the first scan and filled on the second (a fixture that grows) → clean; (8) the record-anchor
pin (the HIGH-class pin) — the state file re-stamped past the narration but the record's seeded
`marker.before_timestamp` preceding it → beats found; (9) the store-identity pin — a cross-cwd
`--persist` resolves the pool from the record's session / persist_dir, not cwd.

Subprocess (the persist judgment): a seeded record + fixture transcript → exit 4 on fabricated
beats; exit 3 on the extractor gap; exit 0 on the clean pair; the panels name the exact gaps;
each arm's cue line appears only on its own arm's exit; the record-fill-attack fixture → exit 4
with all named gaps (the BLOCK-class pin end-to-end).

Beta oracle: the new family runs in the existing harness flow — the block-presence leg rides
`_latest_capture_check` and the detector self-test legs are hermetic in-memory record+transcript
pairs (§2's corrected scope: the fixtures cover the DETECTOR, never an individual rotated dream;
no make_fixture/make_cycle_probe change).

Docs: SKILL.md's persist-gate section gains the two arms + the degrade boundary; SKILL.md's
Phase-2 section defines the canonical skip marker (the exact `extractor-skip:` token + non-empty
why — the detector matches the marker, never prose); harness-map.md documents the detector, the
text-block domain, the record-anchor rule, the degrade seam, the model-dependence property, and
the coordinated-fabrication ceiling (§5); CHANGELOG [0.4.19].

## §4 Ship shape

Feature branch → per-PR review → user merges → `release.sh` pre-bump (CHANGELOG first,
plugin.json 0.4.18→0.4.19, the complete sweep) → `--expect patch --finalize`. Backward-
compatible: additive detector, additive family, one additive OPTIONAL top-level record block
(`narration`). Under this repo's lockstep definition that IS a schema change and must ride the
lockstep: the CycleRecord TypedDict + the SKILL.md schema fence (smoke C5 pins them key-for-key)
+ validate_cycle_record's key list move together. Legacy records and old renderers stay
unaffected (v0.4.16's additive `preflight` key is the precedent) — the patch classification
holds.

## §5 Known ceilings (documented, not solved)

The detector verifies *presence of text and calls* — conversation-truth, not performed-truth.
The strongest attack: **coordinated fabrication** — all six beats plus the sleep stanza emitted
in one compressed burst at record-fill time plus a pro-forma `--json | head` extractor call in
the final minute; NAR finds all seven contained, EXT finds the call, and the gate exits 0 on a
pass whose beats anchored no real phase work. Not hypothetical — every ingredient is measured: rec12 already carries beat-2
text and beat-4's opening contiguously in one assistant message; rec14 ran its only extractor
call 12 s before persist; and the whole class the detector targets is precisely "ceremony
performed in text, decoupled from tools." The gain is real: the bar moves from "lie in the
record" to "lie in the conversation" — the narration becomes the auditable artifact, and the
audit's phase-table method (tool evidence vs. claims) still catches the coordinated lie. A
partial discriminator — requiring each beat's text to be separated from the persist call by the
phase's own `CM_DREAM_ARC` tool activity (interleaving) — was weighed and deferred: it adds
ordering complexity for a class the beta lens already covers. Stated explicitly in
harness-map.md so conversation-truth never implies performed-truth.

## Evidence ledger

Every citation above is measured: the 2026-09-06 dream-pass audit (the phase table + the
HIGH/MEDIUM findings) is the direct evidence; the transcript at persist time was verified to
contain the narration lines (the audit read them); the exit-code key and the existing gates are
the code being extended.

## Amend ledger

- **amend-1 (advisor pass, 2026-09-05):** measurements reproduced on the live tree — rec14 = 2/6
  narrated (the audit's number), rec13 equally deficient one pass earlier (4 missing); mirrors
  exact-or-absent across all 12 measurable passes, no paraphrase case; the audited pass's only
  extractor call was `--recalls`, 12 s before persist; buffering measured on the subagent path
  (5 min unflushed). Folded: the normalizer extension (blockquote prefix + trailing asterisks),
  the ~500 ms re-read retry (flush race), the missing-beat index panel, the EXT execution anchor
  (grep/sed/text/tool_result non-invocations measured in the live transcript), the precise
  tiled-window rule (`since = marker.before_timestamp`, reuse `_window_transcripts`), the
  persisted `narration.verdict` degrade block, the corrected beta-oracle scope (fixtures cover
  the detector, never an individual rotated dream; absent-block = teeth-loss), the three
  exit-code integration traps (ordering, cue split, the no-transcript-degrade keystone), the
  canonical `extractor-skip:` marker moved into the SKILL change, and the coordinated-fabrication
  ceiling (§5). No BLOCKS; patch classification holds.
- **amend-2 (adversarial review-to-zero, 2026-09-05):** verdict MUST-BE-AMENDED — one BLOCK, one
  HIGH. BLOCK: NAR's match domain was unpinned — the record-fill Write/Edit tool_use input and
  its tool_result echo carry the full dream block inside the window, so a message-level matcher
  self-satisfies on the exact fabrication the detector targets; folded — text-blocks-only domain
  (`extract_signals._human_text` precedent) + pin (2a) the negative. HIGH: the window anchor
  "read from the state file" was wrong — Phase-5 step 5 re-stamps the state file before
  `--persist`, so a persist-time read yields since = now and an empty window on every real pass;
  folded — the anchor is the record's Phase-0-seeded `marker.before_timestamp`. Also folded:
  the degrade-vs-fire seam (any raw line after since ⇒ fire-on-gap; zero ⇒ degrade), the
  lockstep correction (§4's "no record-schema change" was false under smoke C5 — the additive
  `narration` block rides the full lockstep, patch classification holds), the
  compute-before-print / panel-suppression ordering, store-identity transcript-pool resolution
  (the cross-cwd false-clean), the retry scoped to the sub-second flush race (the 5-min class →
  persist-then-re-render), SLEEP as checked index 0, the beta absent-block gating on
  `_latest_capture_check`, and the two documented leaks (re-run inclusion, first-pass keep-all).
  Dismissed after verification: the EXT argv anchor (matches every SKILL command form), the
  exit-code/cue coexistence, 3.8 stdlib, fixture hermeticity, §5's deferral, the validator
  warn-only claim. Patch classification holds.
- **amend-3 (re-review round 2, 2026-09-06):** fold-check 11/11 landed; fresh pass found 3 MED +
  1 LOW + 4 NIT. Folded: F-1 the seam extends to EXT (zero content ⇒ BOTH arms degrade, no
  exit-3 — the session-ful rotated fixture pinned); F-2 every judged persist writes the
  `narration` block pre-append with verdict verified|degraded|failed (failed carries the gap
  indexes) — the block on the log line is that attempt's scan result, absence ⇒ pre-feature for
  the beta min_version gate; F-3 the sleep mislabel corrected — sleep is the record's separate
  `dream.sleep` field, the six `beats` entries keep their record indexes 0–5, pin (2) counts
  7-narrated/5-gaps, §5's burst emits sleep too; F-4 the keep-all leak widened to the mid-life
  state-file loss (accepted residual); F-5 the seam wording aligned with the reused filter's
  keep-semantics (ts-less lines are kept, never `≤ since`; open-failure ⇒ unavailable); F-6 the
  NAR extraction named NEW (assistant-role lines only; thinking blocks never count); F-7 the cost
  budget line (~27.5k lines, ~1–2 s, no caching); F-8 the normalizer order pinned (per-line
  prefixes before collapse) + the wrapped-quote pin case. BLOCK and HIGH classes remain closed.
  Final pass (2026-09-06): verdict CLEAN — all folds verified with behavioral pins; one optional
  NIT folded — the arms' verdict is computed regardless of the record-side outcome (verified when
  no gaps; suppression affects only the panel and the exit ladder).
