# Changelog

All notable changes to **consolidate-memory** are documented here. This project
follows [Semantic Versioning](https://semver.org/) (pre-1.0: minor versions may make
breaking changes). Installed plugins auto-update at Claude Code startup when this
version changes on `main`.

## [0.1.53] — 2026-06-23

### Fixed — signal-pipeline hardening: the per-release defects a live v0.1.51 dream surfaced
A real dream run showed the signal pipeline was roughly half-noise (measured: 39 human signals / ~18 noise; 8
error signals / 0 durable gotchas) plus a hard crash — one lingering defect per recent release. Each
root-caused + fixed (spec: `docs/signal-pipeline-hardening.spec.md`):
- **Compound acks no longer masquerade as signal** *(v0.1.50)* — "Ship it please", "Yes ship it", "Let's
  continue" etc. were classified `statement`/score-1 (the anchored `_ACK` only matched a lone ack word). Now
  `_classify` checks markers FIRST, then a control-opener + length-bounded ack matcher demotes them to score-0
  (a marker-bearing turn like "yes, but **always** X" stays a preference; a long signal turn opening with
  "sure" is protected by the word-bound).
- **`[Image #N]` markers + pasted screenshot paths stripped** *(v0.1.50)* — leading attachment noise is removed
  to reveal the real instruction that follows (which `norm[:300]` had truncated off); a pure image-only /
  path-only turn becomes noise. (Quoted paths may contain spaces — the real screenshot case.)
- **Error channel cleaned of transient noise** *(v0.1.49)* — ruff lint/format, the model's own inline-script
  (`<stdin>`/`<string>`) tracebacks, and Claude-Code auto-mode classifier messages (denial / unavailable) are
  dropped as harness-artifact / transient noise. A genuine env error (a `ModuleNotFoundError` from `python3 -c
  "import x"`, `ruff: command not found`, an HTTP 401, a filesystem `PermissionError`) is still KEPT.
  **Reverses a v0.1.49 call:** classifier-denials were kept as "highest-signal"; they're now noise (a transient
  harness event, not a durable env gotcha — the real lesson is authored from session context).
- **`KeyError: 'audit'` crash fixed** *(v0.1.22 flow)* — `memory_status.py --audit <snapshot> --into <cycle>`
  now injects the audit block straight into the cycle record (deterministic; no model-improvised merge). The
  SKILL Phase-5 step uses it; absent `--into` it still prints the summary (backward-compatible).
- **Dream-arc styling un-hedged** *(v0.1.47)* — the opening + closing debrief are now REQUIRED bookends; the
  "function wins, voice recedes" hedge is scoped to the intermediate phase narration only (the model was
  generalizing it to the whole arc, so the voice evaporated in every dense pass).
- **Phase-2 `--json` schema documented** *(v0.1.48)* — the SKILL now states the keys (`counts.surfaced`, each
  signal's `signal_type`), so the orchestrator stops reading `kind`/top-level `surfaced` (both `None`).

All backward-compatible (the `--json` schema is unchanged, `--into` is additive, the rest is SKILL prose) →
patch. 443 smoke + mypy green; validated end-to-end on the real transcript that surfaced the defects.

## [0.1.52] — 2026-06-23

### Fixed — cross-store dangling-link resolution (the recurring 1–2 "broken wikilinks" every cycle)
Root-caused the dangling-link false positive that surfaced on **every** consolidation cycle. The detector
(`memory_status.dangling_links`) resolved each `[[target]]` against ONLY the single store it scanned, but the
memory graph is multi-store (project-local · global canonical · per-node mirrors) and cross-scope, so two
legitimate link shapes were mis-flagged — now distinguished:
- **`dangling_links(auto_mem, global_dir=…)`** resolves against **local ∪ the global canonical** (the only
  OTHER store a slug-scoped node can pull from — NOT fleet-wide). A `[[target]]` that is a real global fact
  pending mirror (a budget-HELD up-link) is **pending-pull, not dangling** (the M1 `held` count is the real
  signal) — this was the recurring false positive (a link flickered "dangling" for 4 cycles until its global
  target was finally pulled). A target absent from BOTH stores stays flagged: a real typo, OR a sibling-
  project-local DOWN-link genuinely unreachable here (correctly still surfaced).
- **Both fill sites widened together** — the Phase-0 `maintenance.dangling` seed AND the SKILL Phase-5
  `health.dangling_links` fill — so the two counts can't drift (smoke-pinned). `global_dir=None`/missing ⇒
  byte-identical legacy behavior (backward-compatible — hence a patch).
- DRY: the global-store path is now the `GLOBAL_STORE` module constant (cf. `sync_global.GLOBAL`).
- Tests: +3 (Class B resolved · Class A still flagged · backward-compat + global-absent) + 2 SKILL drift-pins
  + 1 cross-store isolation guard. Spec: `docs/dangling-cross-store-resolution.spec.md`.

## [0.1.51] — 2026-06-22

### Added — distill: a workflow-recurrence PHASE in the dream sequence (distill arc, stage 2 — the MVP)
The dream's **second vertical**: where it consolidates FACTS into memory, **distill** detects repeated WORKFLOW
patterns and PROPOSES a durable artifact (a command / skill) — report-then-apply. Inspired by MiMo-Code's
`/distill`, but **integrated as a PHASE of the regular dream** (one skill package, frictionless — the user's
call), not a separate skill/command. Measure-first validated the premise on cm's own transcripts (the gated
release cycle recurs ≥12×). Full design: `docs/distill-phase.spec.md`; plan: the `distill-feature-plan` memory.
- **`distill_scan.py` (new stdlib script)** — a LIVE within-project recurrence scan (NO persisted cross-dream
  tally → the D1 recurrence family stays deferred). Reuses `extract_signals`'s `_norm`/`_looks_secret`/
  `_window_transcripts` + `memory_status.slug_for` (no re-implementation). Extracts assistant `tool_use` Bash
  commands over a recent (~30-day) window — BROADER than the dream's `marker..HEAD`; firewall FIRST; then
  normalizes to a CLASS **template over MULTI-LINE input** (split on `\n`/`&&`/`;`, drop pure-`cd` + leading
  `VAR=` segments, heredoc→head, drop quoted/paths/branch/value args) and counts recurrence (`count≥2`, ranked).
  `--json` contract: `{window, scanned:{sessions,commands}, recurring:[{template,count,sample}]}` — DATA only
  (the model does the workflow-recognition + proposal). `cm distill [DIR]` added.
- **The distill PHASE (SKILL.md Phase 5 step 6; render renumbered to step 7).** The model RECOGNIZES a coherent
  repeated workflow from the templates (not a single generic verb), GATES it (≥2× + stable + repeatable + clear
  stopping + **not-already-covered** — inventory existing skills/commands first), and **PROPOSES the SMALLEST
  artifact** report-then-apply. **"Create nothing" is the common, expected outcome** on today's small fleet.
- **Safety (the highest-blast-radius feature — gate-reviewed SOUND):** the script CANNOT author (DATA only); the
  phase **NEVER auto-writes an executable artifact** — it presents the proposal **PLAIN/un-styled**, the human
  confirms, and a single confirmation authorizes **ONE named artifact** (not a suite). Proposed artifacts are
  **genericized** (no abs paths / machine names / personal values — the firewall catches credential-*shaped*
  values, not machine-specific ones). Known gap (acknowledged): an authored artifact lands outside the Phase-5
  `--audit` mutation trail, so it's named explicitly in the closing debrief.
- **Backward-compatible (PATCH):** additive new script + additive phase; **no `CycleRecord` schema/TypedDict/
  smoke-pin change** (the proposal is in-conversation, like Phase 4); no removed/renamed key/script/flag. +12
  smoke checks (the `_template` recall guard on REAL command forms — multi-line/heredoc/bare-cd/VAR=, branch
  grouping, push≠pull — + end-to-end scan recurrence/firewall/create-nothing/contract) → 406 passed, 0 failed.
- Gated: independent spec-review (report-then-apply + blast-radius SOUND; 1 BLOCKER [the `cd &&` strip was wrong
  for the 92%-multi-line channel] fixed + re-measured on real data, + 5 gaps folded in) + `/code-review`. mypy
  clean · sim ✓ · `claude plugin validate --strict` ✓ · dream-beta-test 0 FAIL.

## [0.1.50] — 2026-06-22

### Changed — signal-extraction foundation: 2 channel-precision sharpeners (distill stage 1)
A measure-first, 5-lens discovery (`docs/signal-extraction-foundation.spec.md` + the `distill-feature-plan`
memory) partitioned every signal-extraction enhancement against a 3-part bar — ship only if MEASURED-real AND
non-redundant with the existing 3 sources + git AND zero new firewall surface. The decisive result: **sharpen
channels already parsed; don't add sources** (every new-source candidate failed — file-hotspots = git-derivable;
a command/Bash source = 87% `cd` + 5% firewall-trip + already-covered by errors). This ships the 2 unanimous
sharpeners; both are PRECISION fixes to existing channels (no new source → no new firewall surface).
- **Teammate-message `_NOISE` anchor.** `_NOISE` caught the bare `<teammate-message` tag but MISSED the
  `Another Claude session sent a message:` prose wrapper (the prose precedes the tag, so the bare-tag arm never
  fired). Measured: **~49-55 such turns ≈ 7% of human turns leaked through as human feedback**, all carrying
  `scope_hint="user"` (predominantly the `preference` class) → they fed user-global facts. Anchoring the prose
  prefix drops them (agent coordination, not human intent). Verified 0 leaks remaining on real projects.
- **Error-channel dedup to a CLASS (`_error_key`).** The error channel deduped by EXACT text + capped at
  `MAX_ERRORS=8`, so byte-noise (exit codes, line numbers, temp paths, PIDs, timestamps) fragmented one error
  class into many rows and diluted the cap. `_error_key` keys by a normalized class: **head-extraction** (key
  from a `…Error/Exception/Warning:` head onward) drops the `Traceback … File "/…", line N` preamble + frames
  while PRESERVING the message, then only UNAMBIGUOUS byte-noise normalization (exit code / line number / ISO
  timestamp). Deliberately normalizes nothing whose value could be SIGNAL — **NO path→/PATH, NO blanket
  `\d{3,}`→N, NO bare-hex→HEX, NO bare-clock→TS** (the binary in `foocli: command not found`, `HTTP 404` vs
  `500`, a Windows HRESULT `0x80004005`, a slice `arr[10:20]` are signal, not noise — the byte-noise list is kept
  symmetric). `_dedup` gains an optional `key=` (default = exact text → human dedup UNCHANGED); errors dedup by
  `_error_key` before the cap. Normalization only — the cross-session recurrence MULTIPLIER is deferred (D1).
- **Deferred** (per the discovery + anti-bloat): the exact-form-literal salience nudge (modest measured benefit,
  heuristic FP risk, rarely binds — the skeptic lens recommended exactly these two); the D1 recurrence family;
  the D4 `/distill` workflow→artifact vertical.
- **Backward-compatible (PATCH):** signal schema unchanged (v0.1.48 canonical keyset untouched), no new source,
  no new firewall surface, no removed/renamed key/script/flag; `_dedup`'s default key preserves human behavior
  exactly; keys never alter the stored verbatim text (display unaffected). +7 smoke checks (the `_error_key`
  merge/separate recall guard incl. same-family-different-identifier, the foocli/barcli + hex/clock no-over-merge
  pins, + end-to-end drop/collapse) → 394 passed, 0 failed.
- Gated: independent spec-review (no blockers, both changes prototyped; 4 gaps folded in — dropped the
  over-merging path-strip, corrected the leak framing to ~49 all-scope=user, strengthened the recall-guard
  fixture) + `/code-review`. mypy clean · sim ✓ · `claude plugin validate --strict` ✓ · dream-beta-test 0 FAIL.

## [0.1.49] — 2026-06-22

### Changed — filter transient tool-protocol noise from the error-signal channel (+ cap)
`extract_signals.py` surfaces `is_error` tool-results as a Phase-2 gotcha source, but — unlike human turns
(which get a noise filter AND a cap) — the error channel got **neither**, flooding Phase-2 input with Claude's
own transient tool-usage mistakes. **Measured across the fleet** (12 projects, 57k transcript lines): of 186
non-secret error tool-results (77 unique), **~73% of raw / 52% unique are `<tool_use_error>`-wrapped** —
Claude's own tool-protocol retries (file-not-read, string-not-found), never an environment gotcha. Full
measurement + design: `docs/error-signal-noise-filter.spec.md`.
- **Drop `<tool_use_error>`-wrapped results** (`_ERROR_NOISE`, an `elif` after the secrets firewall so the
  firewall keeps precedence). It is the one error class that is high-volume, **harness-stable**, and
  **zero-false-drop** — a tool-usage error is never an env gotcha (those arrive as bash stderr / exit codes).
  Verified there is NO structural discriminator (protocol- and bash-errors share keys), so the content marker
  is the only signal (anchored to a LEADING wrapper, so an env error that merely quotes the marker mid-body is
  not false-dropped — zero recall loss vs unanchored, 136/136 fleet-wide; substrate-drift watch noted).
  Filtered errors increment `counts["noise"]`.
- **Cap surviving errors at `MAX_ERRORS` (8), AFTER the filter.** Errors are unranked (chronological, no score
  sort), so the cap is a **flood backstop, not a ranking**; running it post-filter avoids wasting cap slots on
  noise. (Honest limit: post-filter it can still clip a chronologically-late durable gotcha in a pathological
  flaky-loop session — the accepted cost; the cap rarely binds, ~37 survivors fleet-wide / 12 projects.)
- **Deliberately NOT filtered** (the over-reach avoided): inline-script tracebacks — a `python3 -c "import X"`
  → `ModuleNotFoundError` IS a durable "X isn't installed here" gotcha; lint substrings (rot + over-match); and
  the auto-mode-classifier **denials** (the highest-signal error class — redundancy with human turns resolves
  at fact-level dedup in Phase 2/4, never by dropping). The residual falls to the cap + the model's Phase-2 judgment.
- **Honest framing:** this is **context HYGIENE** (less transient noise in the input the model already curates),
  **NOT signal recovery** — no previously-missed gotchas are rescued (the durable yield is ~6–7 items fleet-wide).
  Note: `counts["noise"]` now also counts filtered errors (it has a single consumer — the `_report` summary line).
- **Backward-compatible (PATCH):** signal schema unchanged (the v0.1.48 canonical keyset is untouched); the
  output simply carries fewer noise rows + a bounded error count. No removed/renamed key, script, or flag.
  +7 smoke checks (drop / keep-env-gotcha / keep-denial / keyset-intact / cap-after-filter) → 387 passed, 0 failed.
- Gated: independent spec-review (no blockers, all 10 checks verified against source + a re-run of the
  measurement; 1 medium + 3 low gaps folded in) + `/code-review`. mypy clean · sim ✓ · `claude plugin validate
  --strict` ✓ · dream-beta-test gate 0 FAIL.

## [0.1.48] — 2026-06-22

### Fixed — uniform signal schema in `extract_signals.py` (the `[error|?|s?]` rows)
`extract_signals.py --json` (the Phase-2 session-signal extractor) emitted a NON-UNIFORM signal schema:
human-sourced signals carried `signal_type` + `score`, but **error-sourced signals did not** — so any consumer
reading those fields with a fallback (the user's ad-hoc one-liner `s.get('signal_type','?')`, and even the
script's own `_report`) rendered a literal `?`/`s?` on every error row. (These are extracted, marker-classified
session *signals* — `source · signal_type · scope_hint · score · text` — not embeddings; the `?` was purely a
missing-key artifact.) Full root-cause + design: `docs/signal-schema-uniformity.spec.md`.
- **Root cause (3 defects):** the five signal-append sites were free-form dict literals with nothing pinning a
  keyset, so two drifted — both **error** branches dropped `signal_type`+`score`, and the **omitted-secret
  summary label** dropped `score` (also `sessionId`/`ts`). The `--json` contract docstring never pinned the
  shape (it documented `scope`, not the emitted `scope_hint`, and omitted `score`), so nothing caught it.
- **Fix at altitude — one constructor, not three spot-patches.** A single `_signal(source, text, *,
  signal_type, score, scope_hint="-", sessionId="", ts="")` is now the ONE funnel every signal goes through;
  `signal_type` + `score` are **required keyword params**, so a future append site physically cannot reintroduce
  the bug. Errors now carry `signal_type="error"` (or `"omitted"` when redacted) + a **named `_NA_SCORE` (0)**
  sentinel — documented in the `--json` contract as N/A (non-human signals are never salience-ranked; they bypass
  `_classify` and are appended unranked, so the sentinel is display-only and `source`/`signal_type` disambiguate
  it from a low-salience human turn). The contract docstring is corrected to the true canonical keyset.
- **Durable pin:** a smoke invariant drives `extract()` over a fixture spanning all three classes (a scored human
  turn · an error `tool_result` · the redacted-secret omitted-summary label) and asserts EVERY signal carries the
  canonical keyset; `_CANONICAL_KEYS` is single-sourced FROM the constructor so the test and the emitted shape
  cannot drift. +5 smoke checks (380 passed, 0 failed).
- **Backward-compatible (PATCH):** purely additive (adds keys to error/label rows) — every existing consumer
  already uses `.get(…, fallback)`, and the change makes the code MATCH the documented `--json` contract (a
  bugfix, not a break). No removed/renamed key, script, or flag; cycle-record schema untouched.
- Gated: independent spec-review (zero blockers — all claims, line numbers, the blast radius, the bypass-`_classify`
  + append-order invariants, and the pre-fix test failure VERIFIED against source; 4 minor gaps folded in) +
  `/code-review`. mypy clean · sim ✓ · `claude plugin validate --strict` ✓ · dream-beta-test gate 0 FAIL.

## [0.1.47] — 2026-06-22

### Added — pin the DREAM-ARC styling (asleep → dreaming → waking) + mandatory HTML auto-open
Two end-of-dream behaviours that only some orchestrators reliably produced — the HTML dashboard auto-opening and a
structured session debrief — are now PINNED in the SKILL, and extended into a whole-pass DREAM ARC (a user-requested
vision): the orchestrator role-plays the consolidation as one dream — fall asleep → dream → wake. SKILL-prose only; the
auto-open already existed in code (`render_html` calls `webbrowser.open()` by default), so what was missing was the
instruction marking it MANDATORY + the debrief format + the arc voice. Full design: `docs/final-phase-debrief.spec.md`.
- **One single-source `### The dream arc` subsection** (after *Rigor modes*) pins the whole arc — opening, intermediate,
  closing, proportionality, the honest limit — so the phases POINT to it instead of restating it. This HARMONIZES the
  four previously-scattered "final message" directives into ONE protocol (a naive addition would have left the SKILL
  self-contradictory): the old absolutist "the output is not free-form prose / the render script is the single source of
  the final report" is REWORDED in place — the dashboard stays the single source of the *data* (don't re-tabulate the
  gauges), the dream now CLOSES with a debrief that *frames* it ("don't duplicate" ≠ "drop the numbers").
- **`render_html … --latest` = the MANDATORY closing action.** A cleanly-completing dream is not done until it runs (its
  auto-open is the post-dream payoff; never `--no-open` in a normal dream). Two carve-outs keep it coherent with the
  existing gates: it runs ONLY on a clean exit-0 `--persist` — NEVER right after an exit-3 procedure-integrity halt
  (which correctly stops to re-verify); and a true Phase-0 no-op never reaches Phase 5, so it has no dashboard / no path.
- **The debrief = pin PRINCIPLES, not a template** (a rigid skeleton makes debriefs go rote): a dream-framed reflective
  voice, visual hierarchy (lead line + bold-headed sections), dense/technical bullets, sparse FUNCTIONAL emojis, FRAMES
  (the non-obvious WHY + what was kept/pruned/verified) rather than duplicates the dashboard, always ends on the 📊 path.
  **Proportional to the OUTCOME BANNER, never the rigor tier** (true-no-op → a one-line stir, no path; no-op/maintenance/
  light → a line or two + path; substantial → the full debrief) — `_outcome()` tops at `SUBSTANTIAL PASS`, there is no
  `HEAVY` banner, so tiering on rigor would re-import the conflation the SKILL guards against.
- **The arc spans the pass:** an OPENING "going-to-sleep" role-play emitted AFTER the first `memory_status.py` read (so
  it's coherent with + scaled to what Phase 0 found) + a LIGHT dream-voice on the INTERMEDIATE phase narration —
  **functional clarity SACROSANCT** (which phase / what command / what result stay plain; when in doubt, function wins).
  **Phase 4 (report-then-apply) stays PLAIN** — fogging the irreversible `CLAUDE.md`-churn approval prompt is the one
  unrecoverable mistake.
- **Backward-compatible (PATCH):** SKILL-prose only — no code change (auto-open already existed), no cycle-record schema
  change (the smoke schema-pin is untouched: NO ` ```json ` fence added before the schema block), no removed/renamed
  script or flag.
- Gated: independent spec-review (2 rounds + a mid-flight scope expansion for the dream-vision → zero inconsistencies) +
  an independent SKILL self-consistency review (7/7 checks PASS: no surviving contradiction, all folded substance
  preserved, banner strings verified against `_outcome()`, generic / no identity leak). smoke 375/0 · mypy clean · sim ✓
  · `claude plugin validate --strict` ✓. Honest limit: an instruction raises the FLOOR (every orchestrator now gets the
  auto-open + a structured, scaled debrief); it cannot fully transfer the judgment that makes a *great* synthesis.

## [0.1.46] — 2026-06-22

### Added — body-defragmentation: curate bloated ACTIVE files (Cycle 2 of the harness-audit follow-up)
Cycle 1 (v0.1.45) archives whole COMPLETED facts (dated pointers → on-demand archive). This handles the orthogonal
case: a long-lived ACTIVE file (a roadmap/status doc) whose BODY has accreted completed/stale items. Measured: 2
bloated active files fleet-wide (the cm roadmap at ≈12.7× its store median; Doc-Flo `next_priorities` at ≈9.1×).
- **`defrag_candidates(fact_files, index_names, *, factor=2.5)` (memory_status.py) — a pure, budget-INDEPENDENT
  helper.** Surfaces INDEXED, non-mirror, NON-dated facts whose `body_tokens` exceeds `factor ×` the MEDIAN over that
  SAME population (self-consistent). Edge guards: returns `[]` on a <3-fact or degenerate (all-equal / non-positive)
  median. RANKS only — the model curates by CONTENT + the user confirms (no write path). DISJOINT from
  `archive_candidates` by the dated-stem gate (dated → pointer-archive; non-dated → body-defrag).
- **Phase 0 surfaces a `defrag? N` stdout advisory** (beside `archive?`; NOT in the cycle record → no schema change).
  **SKILL Phase 5 gains a body-defrag sub-phase** (runs every dream): curate the bloated file's BODY in place (the
  index pointer STAYS) — COLLAPSE detail verifiably redundant with git/CHANGELOG (READ + confirm BEFORE collapsing),
  RELOCATE still-useful-completed detail, KEEP active content + live lessons. **Propose-then-apply IN-CONVERSATION,
  never auto-trim** (the Phase-5 `--diffs` sidecar is the POST-write audit record, not the pre-apply gate). Higher-risk
  (intra-file): keep-on-doubt, relocate-over-delete.
- **Backward-compatible (PATCH):** no cycle-record schema change; no removed/renamed script or flag. +9
  `defrag_candidates` smoke checks (flag/spare/edge guards). Full design: `docs/body-defragmentation.spec.md`.
- Gated: independent spec-review (FAIL→PASS: median population pinned + ratios corrected, the `--diffs`-vs-real-gate
  citation fixed, CHANGELOG-verify operationalized, edge guards, remediation-C overlap documented) + a focused
  adversarial review (no correctness bugs; the relative-median ranking has design-inherent small-population edges —
  the model's content judgment is the net). smoke 375/0 · mypy clean · sim ✓.

## [0.1.45] — 2026-06-22

### Changed — completion-driven archiving + the index budget re-grounded in active-set demand
A harness audit flagged CM's `INDEX_TOKEN_BUDGET` (1200) as ~5× tighter than Claude Code's native always-loaded
truncation (200 lines OR 25 KB ≈ 6400 tok). Deeper measurement FLIPPED the diagnosis: the budget is ~right for the
ACTIVE/lesson-bearing set (real stores measured ~1056–1181 tok, all-active); the permanent over-budget churn was
COMPLETED arcs LINGERING in the index because archiving only fired UNDER budget pressure (the Phase-5 step-0 gate).
The fix decouples archiving from the budget gate. Full design + the empirical record: `docs/completion-driven-archiving.spec.md`.
- **`archive_candidates(fact_files, index_names)` (memory_status.py) — a pure, budget-INDEPENDENT helper.** Surfaces
  INDEXED, non-mirror facts with a dated `_YYYY_MM_DD` stem (the Auto-Dream/CM completed-arc convention), VETOing any
  whose CURATED frontmatter/description signals a live lesson (`_KEEP_RE`). It RANKS only — the model judges by content
  + the user confirms (no relocate path), like `remediation_triage`. Empirically tuned: a whole-body keyword scan
  collapsed recall to ~0 (completed research-docs use "never"/"must" in analysis), so the veto keys on the curated
  description; a dated fact whose lesson-nature is ONLY in its body relies on the model's Phase-5 judgment (documented limit).
- **Phase 0 surfaces an `archive? N` stdout advisory** (detect-and-offer; NOT written to the cycle record → no schema
  change). **SKILL Phase 5 gains a standing completion-driven archive step** that runs EVERY dream, independent of
  budget. **Phase 5 is reframed as an always-on staleness/defrag sweep; the over-budget remediation gate is now a
  BACKSTOP, not the trigger** (it still exists, tested, for genuine active-set overflow).
- **`INDEX_TOKEN_BUDGET` 1200 → 1500** (memory_status.py + render_html.py) — grounded in the measured active-set demand
  + ~25% growth headroom, NOT a fraction of native's 25 KB hard-truncation ceiling (the failure limit, not a target).
  `CLAUDE_MD_TOKEN_BUDGET` (4000 ≈ native's <200-line CLAUDE.md guidance) and `PRUNE_PRESSURE_FACTS` (40) unchanged.
- **Backward-compatible (PATCH):** no cycle-record schema change (legacy records carry their own `budget_tokens` and
  render unchanged); no removed/renamed script or flag. Tests: +8 `archive_candidates` smoke checks, the Probe-L
  over-budget fixture resized for 1500, the `_evict_frees_enough` test pinned to an explicit budget (decoupled from the moved constant).
- **Deferred on evidence:** an always-on DEEP re-verification rotation (+ a fleet-wide `last_verified` schema migration)
  was gated behind a staleness-rate probe → ~10 % SUBSTANTIVE drift over month-old facts (mostly recoverable
  file-relocation), too low to justify the schema cost. Body-defragmentation of bloated active files is the next cycle.

## [0.1.44] — 2026-06-22

### Added — procedure-integrity detector: the lazy-skip safeguard (the structural anti-rush forcing function)
The MEASURED failure (2026-06-22; full design `docs/dream-procedure-integrity.spec.md`): three consecutive dreams ran
**0/0/0 verification** while self-labeled SUBSTANTIAL/HEAVY — the orchestrator skipped the Phase-3 verification fan-out
and graded its own (skipped) effort. `rigor.applied` is self-reported (catches over-rigor, NOT under-rigor), so only a
human's eye caught it. This adds a DETECTOR at the one mandatory boundary a finishing dream always reaches: the terminal
`render_dashboard --persist`.
- **`procedure_integrity(record)` (memory_status.py) — a pure predicate.** FIRES iff
  `suggested_tier(git_commits, session_candidates) >= SUBSTANTIAL` **and** the verification tally
  (confirmed+corrected+unverifiable) `<= 0`. NON-CIRCULAR: it rests on script-SEEDED `git_commits` (a lazy-skip never
  touches it), NOT on the audited self-report (`rigor.applied`) and NOT on `mutation_ops` (a skipped Phase 5 also skips
  `--audit`, so that data may not exist — MEASURED: 11 mutation-log entries for 13 dreams, none of the 3 failures
  carrying an audit block). `applied` + audit op-count are corroboration/severity only. Legacy/non-conformant records
  (no `scope`/`verification`) NO-OP — never retroactively flagged; non-finite/junk values coerce to 0 (never raises).
- **The teeth (render_dashboard.py).** At `--persist` (the SKILL's terminal Phase-5 step) the render prints a loud
  **PROCEDURE INTEGRITY ⚠** panel, persists the firing record (so it's logged + archived), then **exits 3** — strict
  order print→persist→exit. GATED on `--persist`: a seed/preview render (0 candidates, 0/0/0 by construction) is the
  dream's BEFORE state and is never judged.
- **Archive (render_html.py + dashboard.template.html).** Each logged cycle carries an escaped `_integrity` verdict; the
  HTML flags it on the single-cycle banner + verification block + the archive-index row (the 3 historical failures now
  visibly marked in the longitudinal view).
- **Honest scope.** A DETECTOR at the mandatory boundary, NOT enforcement of phase invocation (nothing can make a
  stateless script force an LLM to run a phase). It catches the *lazy-skip* (0/0/0 on a substantial pass), NOT a diligent
  liar who types fake tallies.
GATED build (gated-spec-driven-change): an independent 3-lens spec review + advisor pressure-test + a fresh re-gate (all
FAIL→PASS), then an adversarial diff review (1 blocker — a non-finite-float crash in the coercion — FIXED, pinned, and
repro-verified). EMPIRICALLY VALIDATED: the predicate separates the 13 live records cleanly — fires on EXACTLY the 3
rushed passes (incl. the 11-commit/0-candidate one a candidate-only gate would miss), spares all 10 legit (every one
recorded tally>0, incl. the corrected 19/2/2 dream). **NO cycle-record-contract change** (reads existing
`scope`+`verification`; verdict derived, not stored) → the smoke pin is untouched. smoke 358/0 (+23 units: the 13-record
regression + the --persist-gate / seed-spared / legacy-no-op / NaN-safe / negative-tally pins) · mypy 16 · sim ✓ · blast
radius MEASURED (cm/tests/beta-tester all spared). **PATCH** (additive; legacy records still render; exit-3 fires only on
the failure condition, never on a legit/legacy/seed render).

## [0.1.43] — 2026-06-22

### Fixed — session-id discovery: window-aware extract_signals + originSessionId producer (pre-1.0 audit blocker #2)
Discovery read only the NEWEST-mtime transcript, not all sessions in the marker..HEAD window — so a fresh session
opened JUST to run dream HID the prior heavy session's intent (the killer case the on-disk read was meant to
defend). And originSessionId was validated/consumed but NEVER produced.
- **A — window-aware `extract_signals` (Phase-2-internal):** `_latest_transcript` → `_window_transcripts` — pool
  ALL `*.jsonl` in the window (mtime-prune only definitely-stale files; the per-line `since` does the exact
  scoping) through the SAME single per-line path, emitting each candidate's `sessionId` (mtime-prune TZ-corrected per
  Gate-2: Z-normalized + naive-marker-as-UTC, so it never wrongly drops a prior in-window session). **SECRETS FIREWALL
  preserved (the ship-gate):** one per-line scrub path fed from the pooled files — NO second read path; a smoke
  case pins the scrub across >1 pooled file (secret value absent). Pooled dedup; `max_n` caps the pooled set.
  CONTRACT change (internal-only consumer): `--json` `transcript` (single) → `transcripts` (list). ZERO
  SKILL-command change.
- **C — `originSessionId` producer:** the fact-write template (harness-map + SKILL Phase 4) now stamps it from the
  signal's `sessionId` (the MOTIVATING session — may be a PRIOR one), omitted for git-derived project facts —
  closing the producer gap the old "CC-INJECTED" wording wrongly presumed existed.
Bounded (git log already covers project facts; the loss was prior-session feedback/prefs — the durable
user-global slice). smoke 333/0 (incl. firewall + multi-session + mtime-prune units) · mypy 16. Meta-req HELD
(Phase-2-internal, no new command/manual step). **PATCH** (internal contract; no external consumer).

## [0.1.42] — 2026-06-22

### Added — cold-start bootstrap: the dream is NETWORK-AWARE on an empty store (pre-1.0 audit blocker #1)
The cold-start audit found a real gap — the HYBRID path: a fresh/dormant repo in an established fleet (EMPTY local
store + ~0 commits + a RICH cross-project network) hit the network-BLIND no-op STOP and exited before Phase 1,
never discovering the fleet's relevant facts. SKILL-only fix (the no-op STOP is a SKILL instruction, not
script-enforced; `global_store_facts` is already seeded; `--list` already does the `is_relevant` filter):
- **B3 — network-aware no-op rule:** STOP only when the local store is EMPTY *and* the network is empty
  (`cross_project.global_store_facts == 0`). An empty-store-but-rich-network repo PROCEEDS to a COLD-START
  BOOTSTRAP (Phase 1 `--list`→`--pull`, M1-bounded; Phase 5 health) — generalizing the v0.1.37 MAINTENANCE-pivot.
  Scoped to pull+health ONLY (no Phase-2/4 authoring — the genuine from-scratch case stays a STOP; never
  force-seeds). Graceful degradation: `--list` 0-relevant → honest no-op ("network checked · 0 relevant").
- **B1 — `--list` before `--pull`:** surface relevant/present/missing/held BEFORE the pull writes — legible
  enrichment, not a blind pull. Read-only, no code.
NARROWED by the audit verdict: a cloned-history repo has commits>0 → already bootstraps (first-consolidation), so
the gap is the empty-history/dormant repo only. Rejected B4 (selective-pull flag) + B5 (cold `--evict`) as
bolt-on/wrong-tool. SKILL-only · no schema change · meta-requirement HELD (hooks Phase 0→1, no new command). **PATCH.**

## [dream-beta-tester 0.1.6] — 2026-06-22

### Fixed — install-gate updates a STALE DBT-owned pre-push hook instead of refusing
The hook installer refused to overwrite ANY existing `pre-push`, so when the gate's stable location/slug moved,
a re-run left the OLD hook in place — it exec'd a frozen `~/.claude/dream-beta-tester/ci_check.sh` (old-slug
`beta_checks`) that FALSE-FAILED the M3 split-brain `CHK-QTY` on the `.`-bearing path, blocking a verified-clean
push (the cm v0.1.41 evict ship). Now install-gate detects a dream-beta-test-OWNED hook (by marker) and UPDATES
it to the cache-latest resolver (which survives plugin updates); a non-DBT hook is still never clobbered.

## [0.1.41] — 2026-06-22

### Added — evict-to-receive: the release valve for M1's hold (the budget ↔ cross-pollination tension)
M1 (v0.1.38) holds a new global on an over/near-budget store + surfaces the lever, but a chronically-full store
then HOLDS forever (the audit's "starves until it prunes" tension; Doc_Flo holds 5). `sync_global --pull
--evict=FACT` is the release valve: free ONE low-value local pointer so a held global can land — NET-NEUTRAL (a
swap, not a grow, so M1's budget stays enforced). It COMPLETES M1 (guard ↔ valve), doesn't compete with it.
- **Safe operator scalpel, report-then-apply (NEVER auto-eviction):** a plain `--pull` with anything held surfaces
  the held + the evictable pointers with RAW, UNORDERED metadata (scope · mirror? · cost) — explicitly NOT ranked
  (a staleness/mtime rank misleads: a foundational fact is untouched yet vital). The agent judges; `--evict`
  applies. Pre-checks BEFORE any delete (Guard-3 no-partial-state): the fact exists, has NO inbound `[[links]]`
  (`_inbound_links` — orphan-safety), held globals exist to receive, and the freed room FITS the smallest held
  (`_evict_frees_enough` — never delete for nothing).
- Factored `extract_wikilinks` — the SINGLE `[[...]]` extractor (`dangling_links` + the evict inbound-scan both
  call it; no 4th wikilink regex, per the v0.1.40 reimplementation-pin lesson).
- Gate-2 hardening (2 independent reviewers; core destructive guarantees confirmed sound): `--evict` now honors
  `--allow-net-grow` in its held pre-check (no gratuitous evict when the override makes nothing held); the
  surfacing read is OSError-safe (matches every other store scan); `--evict` requires `--pull` and rejects an
  empty `--evict=` at parse (a destructive flag never silently no-ops). install-gate hook-update is runtime-
  verified (the recurrence-guard fired on the real stale hook); a bash test for it is a noted gap.
- Verified: hermetic CLI E2E (happy · inbound-orphan refusal · too-small-fit refusal · the surfacing) + 6 smoke
  units on the pure guards. smoke 328/0 · mypy 16 · sim A–Q. **PATCH** (additive `--evict`; `--pull` unchanged).
- Deferred (separate, pre-existing): a pulled global linking a HELD global dangles (the dangling-detector is
  local-only) — not eviction-specific. This valve is a scalpel, NOT a cure: it does not auto-rank or "solve" the tension.

## [0.1.40] — 2026-06-22

### Fixed — M3: `slug_for` generalizes to all non-alphanumerics, fixing the dot-segment split-brain (audit MAJOR)
`slug_for` (memory_status) + `near_duplicate_slugs` + the dream-beta-tester's **four** slug reimplementations
(snapshot, beta_checks, render_beta_report, make_fixture) now map `[^A-Za-z0-9]` → `-` (was `[/_]`), matching
Claude Code's verified rule (`.claude` → `--claude`). A dot-segment project path (a dotfile dir like `~/.config`)
previously got a SPLIT-BRAIN store — two stores, neither recalling the other. Fleet slugs UNCHANGED (paths with
only `/ _ -`); +3 smoke units (dot→dash · fleet-identical · near-dup twin caught). **dbt 0.1.4 → 0.1.5.**
- BREAKING for a dot-segment project (re-slugs its store) — but no real fleet project is dot-segment (verified;
  only the harness's own gate fixtures are dot-path), so the blast radius is the test harness, re-pinned below.
- **Shipped as a MAINTAINER MIGRATION, not a routine gated release:** the pre-push gate's cache dbt + frozen
  v0.1.19 canary are old-slug, so they FALSE-FAIL a new-slug skill (CHK-QTY — the skill reads the new-slug store
  while the old-slug oracle reads the fixture → mismatch). PROVEN no real regression by running the gate at
  CONSISTENT new-slug (repo dbt + repo skill + fresh fixture): **oracle 0 FAIL · 16 PASS · CLEAN**. So the
  cache-dbt FAIL is a known false-positive → pushed `--no-verify`; `install-gate.sh` re-run post-merge re-pins
  fixture + canary at the new slug. smoke 321/0 · mypy 15.

## [dream-beta-tester 0.1.4] — 2026-06-22

### Fixed — M5: dream-beta-tester `restore()` no longer destroys data (audit MAJOR; dbt-only, cm UNCHANGED)
The harness's `restore()` (default `--test`) could DELETE a live store file: it unlinked any live store file
absent from the snapshot, AND capture SKIPPED unreadable files — so a present-but-unreadable PRE-RUN file was
deterministically deleted (constructible, no race; the concurrent-writer variant — another session's fact added
in the snapshot→restore window — was also exposed).
- **Fix (advisor-vetted): QUARANTINE, not delete.** `restore()` now MOVES an extra live file to a
  `reports/.restore-trash-<ts>/` dir instead of `unlink()` — a wrong roll-out is recoverable, and `--test`'s
  leave-no-trace still holds (the store reaches BEFORE exactly; the extra is out, in the harness's own area).
  Capture now RECORDS an unreadable file (`sha256=None`, no copy) so `restore()` PRESERVES it (never deleted,
  never overwritten). Quarantine subsumes the audit's gate/refuse/dry-run-default brainstorm — it removes the
  need to distinguish dream-added from concurrent/unreadable at all.
- Verified by a hermetic E2E (unreadable preserved · extra quarantined-not-destroyed · dream-add rolled out) +
  4 smoke units. smoke 318/0 · mypy 15. **dbt 0.1.3 → 0.1.4** (manual bump; `release.sh` releases cm only). The
  consolidate-memory scripts are UNCHANGED — this sails the cache gate (no slug/skill change).

## [0.1.39] — 2026-06-22

### Fixed — M2 + M4: two `promote()` pre-write guards (audit MAJORs)
- **M2 — `promote()` reconcile silently DISCARDED a re-framed local fact (data loss).** On reconcile (the canonical
  exists), `promote()` rewrites the origin as a mirror of the EXISTING canonical body — so a local carrying NEW
  re-framed content was destroyed with no trace, reported as benign success. A content-divergence guard (pure
  `_bodies_match()` — frontmatter-stripped via a leading-block-only regex so a body's own `---`/`***` rules
  survive, whitespace-normalized, strict) now REFUSES the reconcile when the local body differs ("merge into the
  canonical first") — or `--prefer-canonical` keeps the canonical + drops the local body (the genuine dedup intent,
  mirroring M1's `--allow-net-grow`). Covers BOTH sub-cases (rename + same-name).
- **M4 — `promote()` Guard-2 let an undetectable-stacks fact write a fleet-DEAD canonical.** A stack-general fact
  whose `stacks:` are non-empty but outside `detect_stacks`'s closed vocabulary (a typo, or a real-but-undetectable
  stack like `release`/`ci-cd`) wrote a canonical `is_relevant` matches for NO project. Guard-2 now validates
  `stacks ⊆ _DETECTABLE_STACKS` (block), beside the existing empty-set check.
- Both are pre-write guards (Guard-3's no-partial-state rule) in one `promote()` cycle. Verified by a hermetic E2E
  (M2 refuse + `--prefer-canonical` escape + M4 refuse + a detectable-stack negative control) + 5 smoke units on the
  pure helpers. Process: the audit is the spec → implement → Gate-2. smoke 313/0 · mypy 15 · manifests. **PATCH**
  (additive `--prefer-canonical` flag + `prefer_canonical` param; the guards refuse only what was already broken —
  data-loss / fleet-dead writes — valid promotes unaffected).

## [0.1.38] — 2026-06-22

### Fixed — M1: the over-budget net-grow guard (completes the v0.1.37 self-heal pivot; audit BLOCKER)
The adversarial cross-project audit found v0.1.37's `--refresh-only` guard **incomplete**: it was keyed on
`over_budget_not_justified` (= `remediation.required`), which **standing-justify SUPPRESSES** — so the most-over
stores (Doc_Flo, 230% over + standing-justified) were cued a PLAIN `--pull` that silently net-grew the gated
index (violating the tool's own v0.1.18 no-net-grow invariant), and the guard ran only on the no-op pivot, never
the normal Phase-1 `--pull`.
- **Fix (advisor-vetted): move the DECISION into `sync_global`** (the only place that knows the per-pull cost).
  `--pull` now AUTO-HOLDS a MISSING new-global pull that would *leave* the always-loaded index over
  `INDEX_TOKEN_BUDGET` (projected: `running_idx + the pointer's own cost`) — so it can't net-grow an over- OR
  **near**-budget index (the near-budget overshoot a model-read cue can't catch — the exact bug that bit
  consolidate-memory itself: 1153→1224). STALE mirror refreshes always run (bounded hook-delta).
- **The held-count is the LOUD lever:** `sync_global` reports `held N`, and the dashboard's CROSS-PROJECT section
  surfaces `⚠ held N — prune/justify to receive`. The most-relevant store *starves* until it prunes under budget
  (the audit's deepest tension) — now visible, not silent. Eviction (pull + evict a lower-value pointer) is post-1.0.
- Replaces the v0.1.37 `--refresh-only` with the always-on auto-hold + `--allow-net-grow` (the escape hatch).
  `sync_global._would_net_grow()` is the pure single-source guard; smoke pins cases 1/2/boundary/override + the
  held render. `cross_project.held` added to the cycle record (additive, `total=False`) + the nested SKILL↔TypedDict pin.
- Process: the audit served as M1's independent spec (Gate-1-equivalent); implement → Gate-2. +6 smoke units,
  smoke 308/0 · mypy 15 files · manifests. **PATCH** (additive cycle-record; the removed `--refresh-only` is
  gracefully ignored + superseded by the auto-hold — no install breaks).

## [0.1.37] — 2026-06-21

### Added — the no-op SELF-HEAL pivot: a no-op dream no longer exits with "nothing to do, bye"
A magnitude-0 dream (0 new commits) on a NON-EMPTY store is no longer a no-op — it is a **MAINTENANCE pass**:
the store may carry health debt (dangling links, stale records) and the cross-project tier may hold new
sibling-promoted facts to pull. The Phase-0 stop now fires ONLY for an EMPTY store; a non-empty store PIVOTS
into Phase 1 (`--pull` cross-node enrichment) + Phase 5 (health: dangling-fix / prune-or-justify),
report-then-apply. (Found by dogfooding: Doc_Flo carried 6 dangling links + a stale store a no-op kept skipping.)
- **Signal-driven, not prose** — `memory_status` emits a `maintenance` block (`dangling`,
  `over_budget_not_justified` = the dual-axis suppression result, `work`) + a Phase-0 PROCEED cue, so the pivot
  is cued by DATA (missing prose was the bug).
- **Read-only by default** (the safety posture) — `--pull` is proposed, and a new `sync_global --pull
  --refresh-only` mode refreshes stale mirrors but HOLDS BACK missing new globals (no index net-grow), the
  enforced gate the pivot uses when the index is over-budget-not-justified (honors the v0.1.18 no-net-grow
  invariant — enforced, not model discretion).
- **Single-source dangling** — a new `memory_status.dangling_links()` helper; Phase-0 maintenance, the Phase-5
  health fill, and the smoke test all call it, so the dangling count can't drift.
- **MAINTENANCE PASS banner** — `render_dashboard._outcome()` no longer renders a pivoted self-heal pass as the
  misleading NOTHING/NO-OP.
- **dream-beta-tester 0.1.3** — new `maintenance_pivot_coherence` family: a store with maintenance work MUST
  surface the Phase-0 pivot cue (the regression guard for the signal foundation).
- Gated: empirics → spec → Gate-1 independent review-to-zero (3 blockers folded — read-only pivot,
  steady-state trigger [dropped the perpetual-nag `stale_since_marker`], banner mechanism) → impl → Gate-2
  (`/code-review`, max effort). An impl-time empirical discovery (a live sibling-promoted global a no-op would
  miss) refined the PROCEED cue to fire on `commits==0` + non-empty, not just local work. **Gate-2 caught a real
  bug** — a held-back MISSING fact under `--refresh-only` still wrote PHANTOM provenance to the shared global
  canonical (`_record_provenance` fired on `status=="MISSING"`); fixed to exclude the held case — plus 6
  hardening fixes (the Phase-0 cue now emits the gated `--pull --refresh-only` command itself; `dangling_links`
  strips fenced code blocks too; `maintenance` added to the nested SKILL↔TypedDict pin + `validate_cycle_record`;
  the beta family reuses the captured render). +4 smoke units. smoke 302/0 · mypy 15 files · manifests. PATCH
  (additive; read-only pivot → no contract break).

## [0.1.36] — 2026-06-21

### Fixed (defensive hardening) — the remediation block gates on `required`, not mere presence
`render_dashboard` rendered the over-budget `REMEDIATION` block whenever a `remediation` object was present,
regardless of its `required` flag (`elif rem:`). A record carrying `remediation: {required: false}` — the
cycle-record schema's own DEFAULT — therefore rendered a spurious "over-budget gate" on a store that is UNDER
budget (a self-contradiction, the same class as the v0.1.35 `acted=pruned` bug, one branch up). Fix:
`elif rem and rem.get("required")`. **Not a live-dream regression** — a healthy dream's seed OMITS remediation
entirely (measured), and the over-budget triage sets `required: true` (so the safety gate still fires); the gap
was reachable only by a record following the schema default or a non-omitting producer. Found by dogfooding the
v0.1.35 dream.
- +2 regression smoke units (required=false → no block; required=true → block preserved).
- **dream-beta-tester 0.1.2:** new `remediation_render_coherence` family guarding BOTH renderer fixes (v0.1.35
  rebuild-lean-resolved, v0.1.36 required=false) AND the seed→renderer SAFETY contract — a real over-budget,
  non-justified store MUST seed `required: true`, else the v0.1.36 renderer would silently drop the gate.
  Verified: PASS on the fixed renderer, FAIL on the buggy cache 0.1.35, seed-contract FAILs a gate-dropping seed.
- **mypy.ini now covers `plugins/dream-beta-tester/scripts`** — a latent v0.1.35 `tgt`-type drift slipped
  because dbt was uncovered; now caught. smoke 298/0 · mypy · manifests. PATCH.

## [0.1.35] — 2026-06-21

### Fixed — remediation gate mislabeled "not acted on" after a rebuild-lean (beta-test-confirmed)
`render_dashboard` reported an over-budget remediation gate **resolved by a rebuild-lean** (re-indexing MEMORY.md
leaner — `pruned=0` but `achieved_index ≤ budget`) as `⚠ gate fired but not acted on — surface candidates +
prune-or-justify`, **while the always-loaded gauge showed the index UNDER budget** — a self-contradicting dashboard
that could prompt needless fact-eviction. Root cause: `render_dashboard.py:479` `acted = pruned` derived "acted on"
from facts-evicted ONLY, ignoring `achieved_index`; but the skill SANCTIONS rebuild-lean as a remediation action
(Phase 5 step 0: "prune … and/or rebuild the index lean"). Fix: `acted = pruned or (rebuild-lean brought the index
≤ budget)`, with a clear `✓ gate resolved by rebuild-lean — index back under budget, no eviction needed` note
replacing the false warning. A gate genuinely still over budget (or unacted) still warns correctly.
- Surfaced by the **dream-beta-tester**'s Coherence judgment lens — the deterministic oracle could not reach it
  (an under-budget store renders no remediation block) — and hit LIVE in this repo's own v0.1.34 dream.
- +2 regression smoke units (rebuild-lean-resolved → resolved; still-over → warns). smoke 296/0 · mypy · manifests. PATCH.

## [0.1.34] — 2026-06-21

### Added — `cm log`: the lean log-audit view (the 3rd renderer of the cycle log)
A dense, one-row-per-dream table over `<store>/.consolidation-log.jsonl` — audit any project's dream history
without hand-parsing JSONL or opening a browser. **One log, THREE views** now: ASCII dashboard (`render_dashboard`,
ONE cycle) · HTML archive (`render_html`, all cycles, rich) · **LOG (`render_log`, all cycles, lean-tabular)**.
- **`cm log [DIR] [-n N] [--json]`** — DIR defaults to CWD; fleet-reachable via the PATH-installed `cm` (v0.1.33).
  Columns: WHEN · MARKER · RIGOR · INDEX (Δ) · RECALL (Δ) · ENTRIES (by-action code) · AUDIT (+created ~modified
  -deleted). `--json` emits the last N raw cycle records (pipe to jq / any programmatic audit — the real "plug in").
- **New plugin renderer `scripts/render_log.py`** (stdlib, zero-dep) — **ships with the plugin/marketplace**;
  reuses the SAME `read_history` + `_store_for` (render_html) that `cm report` uses (so they agree on the store) +
  the `_ui` vocabulary. `-n` caps AFTER the newest-first sort. Legacy/sparse + empty-log + malformed-line safe.

### Internal
- `cm log` dispatch (dir-first; `-n`/`--json` pass through) + help; CLAUDE.md layout now lists all three renderers.
  +3 smoke units (table build, legacy-`{}`-safe, `read_history`-reuse). smoke 294/0 · mypy (10 files) · manifests. PATCH.

## [0.1.33] — 2026-06-21

### Fixed — the post-dream re-open instruction was wrong for plugin users
The SKILL told users to "re-open with `cm report`" — but `cm` is the **maintainer dev CLI**: it lives only in the
consolidate-memory repo, isn't on a plugin user's PATH, and CWD-defaults. So a plugin user in another repo (e.g.
job-applicator) has no `cm`, and running it from the consolidate-memory repo opens the WRONG repo's archive. The
dashboards were always correctly **isolated per-repo** (each `~/.claude/projects/<slug>/dashboards/index.html`
embeds only its own dreams — verified by parsing the embedded data); the defect was purely the instruction.
- Phase 5 now points end-users at the **self-contained file at the stable per-repo path** — that file IS the
  fleet-wide re-open (works from any repo) — and explicitly flags `cm report` as maintainer-only.
- `cm`'s own `--help` now notes it defaults to the CWD repo (pass another repo's path to view it) and that end
  users just open the `dashboards/index.html` file.

A convenient fleet-wide re-open command + the `cm log` audit dump remain **separate, deliberate features** (not
smuggled into this correctness fix).

### Internal
- SKILL Phase-5 re-open prose + `cm` help text only. No code/schema/flag change. smoke 291/0 · mypy · manifests. PATCH.

## [0.1.32] — 2026-06-21

### Added — diff-modal (interactivity cycle 2): click a changed memory fact → its before/after diff
The dream view now shows the **memory files changed that pass** as clickable chips (§04) → a **modal** rendering the
before/after **diff**. The diff data lives in a **persistent per-dream sidecar**
(`dashboards/diffs/<commit>__<timestamp>.json`), NOT in the cycle-record contract — revisitable from the archive,
no schema change.
- **Capture** (`memory_status.py --diffs <cycle> --before <snapshot>`, Phase 5 after `--persist`): extends the
  Phase-0 snapshot to stash before-content for the **memory store only** (the `MEMORY.md` index excluded — pointer
  churn, not a fact), then `difflib` per changed fact; one-sided create/delete handled; per-file line cap with
  "+N more". Best-effort (never crashes a dream). The snapshot + sidecar are `chmod 600` (they now hold fact bodies).
- **Embed**: `render_html` reads each embedded cycle's sidecar (keyed by the shared `diff_key`) into the
  self-contained HTML — offline, no fetch.
- **Modal**: +/- /hunk-colored diff; Esc / × / backdrop close. Every line through `esc()` — the load-bearing XSS
  guard on the first feature to render raw fact *bodies* (hostile-fixture verified inert).

### Internal
- New `--diffs` step + `capture_diffs`/`diff_key`/`_diff_lines`/`diffs_dir` (memory_status), `read_diffs` +
  `build_html(…, diffs)` (render_html, kept PURE), the modal (dashboard.template.html). +4 smoke units; data layer +
  modal JS-probe-verified (scoped/capped/one-sided; key sanitized; embed `</script>`-safe; modal opens/closes;
  hostile body inert). Gate-1 spec-review folded (1 HIGH clickable-surface → drive off the sidecar; safety/ordering/
  keying MEDs); independent Gate-2 re-audit. smoke 291/0 · mypy · manifests. PATCH (diff data OUTSIDE the contract).

## [0.1.31] — 2026-06-21

### Added — dashboard interactivity (cycle 1 of the interactivity arc; client-side, READ-ONLY)
Three intuitive interactions on the dashboard + archive — all pure client-side transforms of the already-embedded
data (no new data, no schema, no contract change — safe by construction, the user's "doesn't break anything
logically"):
- **Click-through + keyboard nav** — click any trajectory point, rigor dot, or archive row to open that dream;
  ← → step prev/next, Esc → archive (ignored while typing in a filter).
- **Archive filter & sort** — filter the dream ledger by rigor + sort by date / index tokens / writes (re-renders
  the LIST only; the embedded dreams stay the source of truth).
- **Focus & density** — collapse/expand any dashboard section + a compact/cozy density toggle, both persisted in
  localStorage.

### Internal
- All interactions live in dashboard.template.html (vanilla JS, zero-dep); navigation stays reload-with-param.
  +1 smoke unit; each interaction JS-probe-verified (rigor filter 7→6, sort ascending, click-through 21 points,
  keyboard #sel step, collapse + density toggles). smoke 287/0 · mypy · manifests. PATCH (additive, read-only).
  The diff-modal (persistent sidecar) is cycle 2.

## [0.1.30] — 2026-06-21

### Changed
- Dashboard KPI band ("numerical dash"): dropped the bottom hairline rule (top rule only) so the key indicators
  read as floating below the rule — a cleaner, un-boxed feel (review polish, completing v0.1.29's removal of the
  vertical cell-dividers + the centered network legend + the full-width Changes reason text). Pure CSS, no logic
  change.

### Internal
- **Versioning — PATCH:** a one-line cosmetic CSS change in dashboard.template.html. smoke 286/0 · mypy · manifests.

## [0.1.29] — 2026-06-21

### Added — per-repo dream ARCHIVE (browse + revisit every dashboard)
The HTML dashboard becomes a per-repo mini-site: ONE self-contained, zero-dep file embedding ALL logged cycles,
with two branded views sharing the v0.1.28 design system.
- **Archive index** — a per-repo ledger of every dream (when · outcome · rigor · index tokens · writes · commit),
  newest first, each row a link to that dream's dashboard.
- **Dream dashboard** — the full v0.1.28 telemetry for any selected dream, rendered as-of that pass (the repo
  identity is explicit in both views).
- **Navigation** — reload-with-param (`#sel=<i>`): a dream row, prev/next, or "← Archive" is a fresh load on the
  one tested render path (no in-place re-render). Keyed on `marker.timestamp` (unique); the commit hash is a
  display value + the `cm report <hash>` commit-prefix filter (latest on collision).
- **Stored + revisitable** — written to a stable `~/.claude/projects/<slug>/dashboards/index.html` (the dream and
  `cm report` write the SAME file). `cm report [DIR]` → the archive; `cm report <hash>` → a dream; Phase 5
  `--latest` → the just-completed dream's dashboard.

### Internal
- render_html: `assemble_cycles` (dedup-by-marker series builder, capped at the latest 120 with a visible note),
  `--select`/`--latest`, unified `_default_out`. Template: `#sel` routing + `showArchive`/`showDreamNav` +
  hashchange-reload + boot-once. +4 smoke units; the navigation JS-probe verified (`#sel=k` renders cycle k, not
  the latest). smoke 285/0 · mypy · manifests. PATCH (additive: new views/args + a per-repo `dashboards/` output).

## [0.1.28] — 2026-06-21

### Added — rich HTML observability dashboard ("dream telemetry")
A gorgeous, ZERO-dependency, self-contained HTML dashboard — the visual sibling of the ASCII report (one
cycle-record contract, two renderers). `render_html.py` (stdlib) injects the data inline (XSS / `</script>` /
attribute-quote-safe) into a BUNDLED template and auto-opens it via `webbrowser` (headless-safe — prints the
path if no browser). Offline + works out-of-the-box from the marketplace install.
- **Renders** the current cycle — **repo identity**, budget meters (index / CLAUDE.md), rigor, verification +
  health, the script-observed audit trail, the cross-project "shared-consciousness" network — AND longitudinal
  trends from `.consolidation-log`: the **index-budget trajectory** toward the ceiling with a least-squares
  projected-breach early-warning, recall-fact growth, per-cycle churn, and the rigor tier + dream cadence.
- **Editorial "field report" aesthetic**: warm light + warm-dark themes, auto-detected via `prefers-color-scheme`
  + a manual auto/light/dark toggle; refined serif/mono pairing; precise round-axis ink-on-paper hand-rolled SVG
  charts; one restrained accent.
- **Integration**: Phase 5 generates it after the ASCII render (auto-opens — the post-dream payoff);
  **`cm report [DIR]`** re-opens a project's latest. Coherent with the ASCII renderer (same record; key numbers
  asserted equal in smoke).

### Internal
- `render_html.py` + bundled `dashboard.template.html` (found via `__file__` → marketplace-cache-safe). +9 smoke
  units (coherence round-trip, XSS `</script>` + attribute-quote escaping, zero-external-deps, bundling,
  legacy/sparse render, malformed-log robustness, `_store_for`). smoke 282/0 · mypy · manifests. Independent
  re-audit (1 MED attribute-XSS found + fixed). Charts: least-squares budget slope, breach marker on the exact
  fractional crossing, round-number axes, canonical `CYCLES` series so all longitudinal charts agree; visual
  verified via browser screenshots + coordinate-free DOM probes.
- **Versioning — PATCH**: additive (new renderer + bundled template + `cm report` + SKILL Phase-5 hookup; no
  cycle-record schema change, no removed flag, no install break). The per-repo dream **archive** mini-site
  (browse history + `cm report <hash>`) is the next cycle (v0.1.29).

## [0.1.27] — 2026-06-21

### Added (SKILL doc — the archive-relocation remediation discipline; from the network audit)
The cross-project network audit found the dream ALREADY relocates completed/merged arcs out of the always-loaded
`MEMORY.md` index into an on-demand archive (`SHIPPED.md`) **by judgment** — Doc_Flo's `SHIPPED.md` cites the
v0.1.18 remediation, 57 facts archived — but the SKILL never documented it (the model improvised it correctly).
The deferred **mechanical "archive lever" (finding-B) is off the table**: the budget tier already exists (the
archive is off `INDEX_TOKEN_BUDGET`, on-demand) and judgment does the keep/archive split well; a mechanical lever
would automate a working process and add a silent recall-erosion risk. This codifies the proven discipline so
future dreams apply it consistently + safely.
- **Phase-5 remediation runbook gains an `archive` option** (PREFERRED, non-destructive — applied before
  prune/justify): relocate completed-arc pointers `MEMORY.md`→an on-demand archive index, keeping the fact body
  (recallable) and keeping lesson-bearing / NEGATIVE / active-state / directive pointers live **even if
  dated/"SHIPPED"**. The keep-vs-archive call is judgment with a SILENT failure mode (archive a live lesson →
  recall lost; the recall-tier analogue of CLAUDE.md enforcement-erosion) → conservative, propose-only,
  archive-then-justify the earned residual.
- NOT a routed `lever` (the script still routes prune/gc/justify) — a model disposition; **no code/schema change.**

### Internal
- SKILL.md prose only (Phase-5 remediation runbook). smoke 274/0 · mypy · manifests (json-pin unaffected — no
  schema change).
- **Versioning — PATCH:** additive SKILL guidance; no code, no schema, no lever-routing change.

## [0.1.26] — 2026-06-21

### Fixed (provenance-churn staleness — ROOT-fix; surfaced by the cross-project network audit)
The network audit found widespread "stale" mirrors after pulls. Root cause: the canonical `projects:`
provenance list was copied INTO every mirror, and it grows every time *any* project pulls a fact — so each
pull marked *all other* projects' mirrors stale, though the fact content was identical (perpetual cross-fleet
refresh churn + misleading "everything stale" dashboards; functionally harmless — recall content was always
correct).
- **`_as_mirror` no longer carries `projects:` into a mirror** (root-fix, not a comparison hack): provenance is
  CANONICAL-only bookkeeping — the synapse record `network()`/`_holders` read off the global store; nothing
  reads a mirror's provenance (verified across all scripts). A mirror now stays in-sync regardless of canonical
  holder-list growth. Frontmatter-scoped so a prose body line is never touched; the `_is_mirror(_as_mirror(…))`
  round-trip invariant holds.
- **One-time migration:** existing mirrors refresh once (provenance-stripped) on their next `--pull`/dream, then
  stay in-sync. Verified live: after the one-time refresh, a repeated `--pull` shows **0 refreshed** (churn gone).

### Internal
- `_as_mirror` frontmatter-scoped `projects:` strip + 1 smoke unit (strips FM `projects:`, preserves a body
  `projects:` prose line, round-trip + frontmatter validity hold). smoke 274/0 · sim · mypy · manifests.
- **Versioning — PATCH:** a behavioral fix to mirror content (mirrors drop canonical-only bookkeeping; the
  canonical's provenance is untouched; no cycle-record schema change, no removed flag; legacy mirrors self-migrate
  on the next pull).

## [0.1.25] — 2026-06-21

### Fixed (cross-project wikilink integrity — surfaced by a job-applicator dream pass; additive → patch)
A job-applicator dream flagged 3 dangling wikilinks inside *pulled mirrors* — all `[[wikilinks]]` in
global/stack-general canonicals pointing to **project-local facts of their origin project** (e.g.
`user-fleet-is-monostack-python`→`[[consolidate-memory-roadmap]]`/`[[governance-signal]]`,
`keyfigures-example-hallucination`→`[[contextual-retrieval-negative-2026-05-25]]`). A global fact's links travel
with it into every mirror, so a project-local link dead-ends in every *other* project (a fleet-wide latent defect).
- **`sync_global.py --promote` now WARNS** (non-blocking) when a fact being promoted carries `[[wikilinks]]` to
  non-global targets (`_nonglobal_wikilinks`) — a global fact should link only to other global facts. Prevents
  new fleet-wide dangling links at the source.
- The 3 existing canonicals were corrected — the project-local wikilinks converted to plain text (naming the
  origin project; they propagate to mirrors on each project's next `--pull`).
- SKILL: a note to avoid committing to the repo *while a dream runs* — a concurrent commit moves HEAD (the marker
  advances past it) and the Phase0→Phase5 audit window attributes it to the pass; the dream detects HEAD-moved +
  re-measures but can't fully disentangle it.

### Internal
- New `_nonglobal_wikilinks` helper + 1 smoke unit (flags project-local links; excludes global / self-ref /
  code-span `[[tool.mypy.overrides]]`). smoke 273/0 · sim · mypy · manifests.
- **Versioning — PATCH:** additive (a non-blocking promote warning + a helper + a SKILL note); no removed/renamed
  flag, no schema change. The audit concurrent-commit attribution + the marker-timing edge are accepted/documented
  honest gaps (the tool detects + flags them correctly), not engineered around — per the advisor's re-rank.

## [0.1.24] — 2026-06-20

### Added (CLAUDE.md MUTATION — the dream can now tidy committed CLAUDE.md, gated + audited; additive → patch)
Part two of the CLAUDE.md arc, riding the v0.1.22 recorder. The dream may relocate / compress / prune the
committed, team-shared CLAUDE.md hierarchy — **gated per-change, report-then-apply, never auto.**
- **The directive STAYS; relocate only the ELABORATION.** CLAUDE.md is always-loaded (enforced every session); a
  committed doc is on-demand (enforced only if a pointer cues a read). Relocating a *binding directive* silently
  erodes enforcement — invisible in a content diff. So a relocate SPLITS a heavy section: keep the directive + a
  pointer in CLAUDE.md, move the rationale/examples to a committed doc. A mechanical **normative-marker backstop**
  (`_has_normative_marker`, RFC-2119 / imperatives) flags a directive in the moving chunk — the guarantee the
  byte-conservation check can't give (the bytes still land). `--sections` surfaces heavy sections (mechanical; the
  directive-vs-elaboration judgment stays with the model).
- **Committed-target firewall.** `valid_relocate_target` accepts a target ONLY if it's in-repo AND not under
  `~/.claude` AND not git-ignored (fail-closed) — relocating into the private store or a gitignored dir is silent
  team data loss. Existing committed targets only; a missing target is PROPOSED for the human to create (the dream
  never imposes repo structure, never creates a `CLAUDE.md`).
- **Conservation self-check.** The audit snapshot extends to the relocate-target tree (`repo_doc`); the Phase-5
  `--audit` flags a CLAUDE.md drop with no matching target growth (a lost relocate vs a real move) — matched
  per-op, not per-store-netted. `compress` is a high-scrutiny exception (before/after verbatim); `prune` only a
  *descriptive* line whose referenced code is grep-confirmed gone (a *normative* line always proposes — the human
  owns the staleness call).

### Internal
- New `_has_normative_marker` / `valid_relocate_target` / `claude_md_sections` / `--sections`; `audit_snapshot`
  extends to `repo_doc`; `audit_diff` gains the `conservation` self-check; the `Audit` block gains `repo_doc` +
  `conservation` (additive `total=False`; co-edit across TypedDict + SKILL json + smoke pin + render). The Phase-4
  guest-rule shifts to "guest WITH permission to tidy, on the record" (both SKILL sites reconciled).
- Probe Q (normative backstop · firewall gitignored/private/outside/escape · sections · relocate-conserves vs
  eviction-flags-loss) + 2 smoke units. smoke 272/0 · sim · mypy · manifests.
- **Versioning — PATCH:** an additive capability + additive audit fields (legacy records render); no removed/renamed
  flag, no install/manifest break. finding-B (memory-index archive budget tier) → a later cycle.

## [0.1.23] — 2026-06-20

### Fixed (memory-index residuals from the dream beta-harness WARNs on v0.1.22; additive → patch)
The dream beta-harness confirmed the v0.1.20/21 fixes (D1–D5, D7 FAIL→PASS against git history) and left two
advisory WARNs — both verified live + closed here (orthogonal to the CLAUDE.md arc):
- **D6 — the standing-justify now re-fires on index-TOKEN growth, not just fact-count.** The v0.1.21 suppress
  predicate keyed on fact-count alone, so hook bloat (tokens up, facts flat) past a justified baseline stayed
  silently suppressed — blind to the exact axis the budget polices. The gate now suppresses ONLY when BOTH
  fact-count ≤ baseline+Δ AND index tokens ≤ baseline_tokens × 1.25 (`_STANDING_JUSTIFY_TOKEN_FACTOR`); either
  axis growing — or no valid token baseline — re-fires. Fails OPEN like the fact-axis. The marker already
  persists `index_tokens` (since v0.1.21), so no schema change.
- **D10 — archive-index docs + MEMORY.md are now valid wikilink targets.** memex's "dangling" links were mostly
  false positives: `[[SHIPPED]]` points at the real `SHIPPED.md` archive but was flagged because the check saw
  fact-stems only. `valid_link_targets(auto_mem)` returns every `*.md` stem (facts + archive docs + `MEMORY`);
  the Phase-5 dangling check + `resolve_wikilink` resolve against it, so `[[SHIPPED]]`/`[[MEMORY]]` aren't
  false-flagged. (The bulk of the rest — code-span `[[...]]`, paths — is the model's SKILL-instructed
  code-span-stripping job; the genuinely drifted few still surface for a dream's judgment.)

### Internal
- New `_standing_baseline_tokens` + `_STANDING_JUSTIFY_TOKEN_FACTOR` + `valid_link_targets`; a two-axis suppress
  predicate; SKILL dangling-check prose. NO cycle-record change (the token baseline lives in the marker; the
  surface text is static prose — no co-edit).
- Probe P (token-axis fires on bloat · fact-axis still fires independently · zero/missing token baseline fail-open
  · archive/index resolve) + 2 smoke units. (Probe N's marker got a generous token baseline to isolate the
  fact-axis it tests.) smoke 269/0 · sim · mypy · manifests.
- **Versioning — PATCH:** additive helper + a behavioral tightening (the gate fires more accurately on token
  bloat — the safe direction); no removed/renamed flag, no schema change. The CLAUDE.md mutation → v0.1.24.

## [0.1.22] — 2026-06-20

### Added (CLAUDE.md-arc FOUNDATION — whole-hierarchy measurement + deterministic mutation audit trail; additive → patch)
The CLAUDE.md-optimization arc is SPLIT (advisor sequencing): v0.1.22 ships the read-only / low-risk foundation;
the actual CLAUDE.md mutation (relocate/compress/prune) rides this recorder in v0.1.23.
- **Whole-hierarchy CLAUDE.md measurement (read-only).** Empirics: memex's `src/memex/CLAUDE.md` (~34k tok) +
  `src/memex/webui/CLAUDE.md` (~16k) mean a session in `webui/` pays **~54k tok of CLAUDE.md every turn** —
  invisible to the tool, which measured only the root file (vs `CLAUDE_MD_TOKEN_BUDGET=4000`). `claude_md_hierarchy`
  now finds every CLAUDE.md (root + nested, excl vendored/VCS) and reports the **worst-case root→leaf path** ("a
  session in `<dir>` pays ~Nk/turn") in the Phase-0 report + the dashboard. **Detect-and-report only — NOT wired
  into the memory-index gate** (different subsystem).
- **Deterministic, script-emitted mutation audit trail.** `memory_status.py --snapshot` (Phase 0) writes a
  per-slug content-hash snapshot of the memory store + CLAUDE.md hierarchy; `--audit <snapshot>` (Phase 5) diffs
  it, appends a per-operation record (created/modified/deleted + token deltas) to `.mutation-log.jsonl`, and fills
  the cycle record's new `audit` block. This is the script-OBSERVED counterpart to the model-narrated `entries[]`
  — they should agree; a divergence is a signal. **Honest gap:** the Phase0→Phase5 window attributes any change in
  the span to the pass. Covers the memory writes every cycle already does — the dogfood that proves the recorder
  before v0.1.23 turns on CLAUDE.md mutation.

### Internal
- New helpers `claude_md_hierarchy` / `audit_snapshot` / `audit_diff` / `audit_snapshot_path` + `--snapshot` /
  `--audit` modes. Cycle record gains `budget.claude_md_hierarchy` + a top-level `audit` block (5 new TypedDicts;
  the contract co-edit lands across the TypedDicts + SKILL `​```json` + the smoke nested-pin + `seed_record` + the
  renderer + `validate_cycle_record`'s dict-type guard).
- `.gitignore` now also guards `.mutation-log.jsonl` + `.consolidation-log.jsonl` (PUBLIC-repo defense-in-depth;
  the store is also out-of-tree).
- Probe O (hierarchy worst-path · audit created/modified/deleted via content-hash · unchanged ≠ op · infra
  excluded · measuring is read-only) + 3 smoke units. smoke 264/0 · sim · mypy · manifests.
- **Versioning — PATCH:** additive (read-only measure + a new audit subsystem; new flags; `total=False` blocks);
  no removed/renamed flag; NO CLAUDE.md mutation (that's v0.1.23); legacy records render. The mutation arc →
  v0.1.23; finding-B + the token-axis wire-up stay backlogged.

## [0.1.21] — 2026-06-20

### Fixed (v0.1.19 first-party beta defect catalog — 9 root-cause fixes; additive → patch)
A second memex beta (106 facts, index 231% over) filed an 11-defect catalog; all verified empirically.
**D1/D2 were the `/tmp/cycle.json` collision already fixed in v0.1.20** (the "render reads the wrong node"
hypothesis was REFUTED — the gauge reads `budget.index`; a concurrent dream clobbered the shared seed → the
Doc_Flo render showed consolidate-memory's 885/2256). D3–D11 are fixed here at root-cause; the archive-index
BUDGET TIER (finding B) stays in the CLAUDE.md arc (no double budget model).

- **Standing-justify-as-delta-detector (D3·D5·D6·D7·D11) — the cluster root.** The fixed 1200-tok index budget is
  unreachable for a mature lean store (105 facts × ~20-tok floor = 2100; even a max prune = 2160 > 1200), so the
  gate fired every pass and re-litigated the same triage. Rather than scale the budget (which would defeat the
  v0.1.18 gate — a bloated large store would get a budget that hides the bloat; earned-vs-bloat is irreducibly
  content-aware), a **standing-justify**: the operator confirms the density is earned once
  (`standing_justify: {facts, index_tokens, at}` in the marker) and the gate is SUPPRESSED until fact-count grows
  by Δ (10) — a delta-detector that keeps the teeth (fires on NEW density) while killing alarm fatigue. **Fails
  OPEN** — a garbage/legacy marker → gate fires (suppression requires a valid baseline). `reaches_budget` (D5):
  when a full prune can't reach budget the lever is prune-the-safe-THEN-standing-justify the residual, not a clean
  achievable "prune." Gate-aware drift (D3/D11): over budget, the index↔file gap is INTENTIONAL — no "backfill"
  offer (it net-grows under the no-net-grow gate); backfill stays legit UNDER budget.
- **Wikilink-aware orphan reachability (D4 — SAFETY).** `resolve_wikilink` resolves a `[[target]]` across
  slug-drift (date-suffix, dash↔underscore; EXACT-only, ambiguous→skip — never substring). A fact `[[wikilinked]]`
  from another fact now folds into `reference_stems`, so the A-stage no longer flags it a safe-evict orphan
  (evicting would dangle the live link — e.g. `form_table_research`/`grounding_gate_overrefusal` on memex, both
  wikilinked from indexed facts). Extends the v0.1.19 C2 surfaces (CLAUDE.md + archive) with the auto-memory
  wikilink surface.
- **Presentation + defensive (D8/D9/D10 · D1/D2-class).** D8: the remediation surface leads with the INDEX-RELIEF
  stages (B/C/R — what moves the gated index); TRUE orphans (disk-only, 0 index relief) render LAST. D9: the
  Phase-0 RIGOR line annotates an active over-budget gate (HEAVY-equivalent hard-stop) so "LIGHT" doesn't
  undersell a gated pass. D10: dangling-wikilink health uses `resolve_wikilink` to suggest the drifted target.
  D1/D2 defensive: the dashboard warns when `budget.index` and the trigger network-node grossly diverge (>1.5×) —
  catches the wrong-budget class beyond v0.1.20's per-slug seed fix.

### Internal
- The `Remediation` block gains `standing_justified`/`baseline_facts`/`reaches_budget` (additive `total=False`);
  the typed contract co-edit (TypedDict + SKILL `​```json` + smoke pin + `seed_record` + the renderer) lands
  together. `memory_status.py` gains `--seed`-independent helpers `resolve_wikilink` + `_standing_baseline`.
- Probe N (standing-justify suppress-within-Δ / fire-past-Δ / fail-open · D4 wikilink→R · D5/D8 · resolve_wikilink
  drift) + 2 smoke units. smoke 259/0 · sim · mypy · manifests.
- **Versioning — PATCH:** additive (a new optional marker field, helpers, flags, gate-aware framing, presentation,
  a render warning); no removed/renamed flag; legacy records render. The CLAUDE.md-optimization arc → v0.1.22.

## [0.1.20] — 2026-06-20

### Fixed (cycle-record temp-path collision across concurrent dreams; additive → patch)
- **The dream's cycle-record temp path is now PER-SLUG, not the shared `/tmp/cycle.json`.** SKILL.md hardcoded
  `/tmp/cycle.json` for the Phase-0 seed + Phase-5 render, so two project dreams running concurrently collided:
  during a consolidate-memory dogfood dream, a **memex dream in another session clobbered the shared file**
  between seed and render → the dashboard grafted memex's scope/remediation onto consolidate-memory's entries
  and persisted a "franken-record" to the calibration log. (Caught by the dogfood + measure-don't-assert —
  "105 reviewed / gate fired" is impossible for a 16-fact under-budget store.)
  - **`memory_status.py --seed`** (new) writes the seed to `cycle_seed_path(slug)` =
    `<tmpdir>/cm-cycle-<slug>.json` (deterministic, per-project) and prints the path; SKILL.md Phase 0 now uses
    `--seed` and references that path through the phases + the render. `--json` (stdout) is unchanged for
    ad-hoc / `cm seed` use.
  - Per-slug kills the cross-PROJECT collision (the observed case); same-project concurrent dreams (degenerate)
    would still share a path — acceptable.

### Internal
- +1 smoke unit (`cycle_seed_path` per-slug + deterministic, not the shared path). smoke 257/0 · sim · mypy ·
  manifests.
- **Versioning — PATCH:** additive (a new flag + helper + SKILL prose); `--json` kept (no removed flag); no
  cycle-record schema change. The CLAUDE.md-optimization arc renumbers to v0.1.21.

## [0.1.19] — 2026-06-20

### Fixed (v0.1.18 first-party beta findings — multi-surface orphan safety; additive → patch)
- **C1 (SAFETY) — never treat an archive-index doc as a fact.** A relocated archive (`SHIPPED.md`, a
  link-list) was globbed as a fact; its stem matched the tracker regex → the triage advised "evict" = nuking
  the archive. `build_context` now detects archive-index docs (`_is_archive_index`: a link-list `*.md` with no
  fact frontmatter) and excludes them from `fact_files`. (Surfaced by verifying the beta pass against memex's
  real store — it was NOT in the report.)
- **C2 (SAFETY) — multi-surface orphan check.** The "unindexed → evict" check read only `MEMORY.md`; 23/61
  flagged orphans were referenced in CLAUDE.md prose → "evict" would dangle the committed guest file. The
  triage now gathers `reference_stems` from all always-loaded surfaces — CLAUDE.md prose (bare-stem) +
  archive-index link-targets — and reclassifies a referenced-but-unindexed fact to a new **R (referenced)**
  stage (de-link the surface FIRST; counts toward keep, re-indexed by the lean rebuild), never a blind evict.
- **E (defensive)** — a 0-token index read while facts exist (a write-truncate race) would clear the
  over-budget gate; `build_context` now re-reads once to settle it (a persistent 0 is a genuine all-unindexed
  drift, flagged by schema_drift, not "under budget").
- **F (polish)** — the redundant `prune-pressure (index-over-budget)` line is suppressed when the REMEDIATION
  gate renders (a `many-facts` prune-pressure still prints); the triage output labels `projected_recall` as
  recall-body hygiene, SEPARATE from the index-pointer relief.
- **G (polish)** — `seed_record` omits `pruned`/`achieved_*` (model-filled in Phase 5); the dashboard renders
  their absence as "pending Phase 5", not a misleading ≈0.
- **H (polish)** — documented the `extract_signals --json` contract (`counts.surfaced` + `signals`; no
  top-level `surfaced`/`candidates`).

### Deferred (the beta's DESIGN findings → the CLAUDE.md-optimization arc)
A (a first-class `relocate` lever + split index-pointer vs recall-body projections), B (an archive-index
budget tier so a mature store can be *genuinely* under budget, not perpetually justified), and D (model
CLAUDE.md as a second always-loaded index for dedup) share that arc's design space — tracked in the roadmap.

### Internal
- New `_is_archive_index`; `remediation_triage` gains a defaulted `reference_stems` param + the **R** stage.
  Probe M (hermetic): archive-exclude · referenced→R-not-A · true-orphan→A · seed-omits-achieved · 0-index-safe.
  +2 smoke units. smoke 256/0 · sim A–M · mypy · manifests.
- **Versioning — PATCH:** bug/safety/polish, backward-compatible (defaulted param, no removed flag/script,
  the `Remediation` typed block unchanged, seed omission `total=False`-safe, legacy records render).

## [0.1.18] — 2026-06-20

### Added (inherited-backlog remediation — the prune finally has teeth; additive → patch)
- **Remediation triage + an over-budget GATE.** The app prevented *incremental* bloat (budget ⚠ +
  `prune_pressure`) but couldn't REMEDIATE a backlog inherited from Claude Code's Auto-Dream (unbounded
  append, no index discipline) — observed on a real store: 110 facts, index 5.5× budget, 30 unindexed
  orphans, and a dream that fired `prune_pressure` yet *grew* the index. v0.1.18 adds:
  - **`remediation_triage` (`memory_status.py`)** — for an over-budget index, a PURE classifier ranks local
    prune candidates into cost-ordered stages: **A** unindexed orphans (unrecallable dead weight), **B**
    tracker/status (transient), **C** dated/oversized (content-review) — vs the durable-keep core, with a
    projected lean rebuild. Surfaced in Phase 0 + a new `memory_status.py --triage` view. Empirics showed a
    name/date heuristic mis-classifies durability, so the triage **RANKS/surfaces; it never decides** — the
    model judges content, the user confirms.
  - **The over-budget gate (the teeth)** — the previously HEAVY-only hard-stop now applies at ANY tier when
    the index is already over budget: a pass may not net-grow it, and must **prune-or-justify**. ROUTED by
    the mirror-vs-local attribution: `prune` (local-dominated), `gc` (mirror-dominated >50% — a local prune
    is futile), or `justify` (nothing safely prunable — no deadlock).
  - **Never auto-deletes** (hard invariant): the classifier is pure/no-delete; prunes route through the model
    + the user's confirm (the existing "surface deletions you didn't author" rule).
- A cycle-record `remediation` block (additive `total=False`; legacy records still render) + the dashboard
  renders it — a gate that fired-but-was-unacted stays visible.

### Internal
- New `Remediation` TypedDict via the four-place contract co-edit (TypedDict + SKILL schema block +
  `CycleRecord` + the smoke nested schema-pin). **Probe L** (hermetic) builds an Auto-Dream-style bloated
  store and asserts the A/B/C staging, the lever routing (prune/gc/justify), the never-delete invariant, and
  no-false-alarm on a healthy store. +4 smoke units. smoke 254/0 · sim A–L · mypy · manifests.
- **Versioning — PATCH:** additive (a new analysis + a new guard + prose); no removed/renamed flag/script,
  no manifest change; the cycle-record block is additive `total=False`; the gate only changes behavior for
  already-over-budget stores. (empirics → spec → Gate-1 → meta-test → Gate-2.)

## [0.1.17] — 2026-06-20

### Fixed (cross-project reachability — `slug_for` now matches Claude Code's slug normalization)
- **`slug_for` maps both `/` AND `_` to `-`** (was `/` only), matching Claude Code's real project-slug
  rule. Verified on disk: a session with cwd `…/Doc_Flo` is logged by CC under slug `…-Doc-Flo` (hyphen),
  but the old `/`-only `slug_for` computed `…-Doc_Flo` (underscore). So for ANY underscore-named project,
  replicated cross-project facts (`--pull`/`--promote`) landed in a slug the project NEVER recalls — the
  middle tier was silently unreachable there. This is the root-cause reachability fix.
  - The same `/`-only bug existed in **`extract_signals.py`** (Phase-2 transcript lookup) — the extractor
    found no transcripts for an underscore project. Both now route through the single `slug_for` (DRY).
  - **No regression for non-underscore projects:** `re.sub(r"[/_]","-",p) ≡ p.replace("/","-")` with no
    underscore; case preserved (`Doc-Flo`, not lowercased).
  - **Honest limit:** verified on disk only for `/` and `_` (no other-char example exists); a `.`/space
    could diverge further and would NOT be caught by `near_duplicate_slugs` (collapses only `_`/case) — an
    accepted, documented residual risk. Corrected the `claude-code-memory-is-slug-scoped` fact +
    `harness-map.md` (the earlier "a rename changed the slug" framing was wrong — it was the `_`→`-` mismatch).

### Added
- **A `pdf` stack for `detect_stacks`** (dist `{pypdfium2, pymupdf, pdfplumber, pdf2image, pdfminer-six}` /
  module `{pypdfium2, fitz, pdfplumber, pdf2image, pdfminer}`) — so genuinely cross-project PDF-library
  gotchas (e.g. pdfium thread-unsafety) can be `stack-general:[pdf]` and bind the fleet's PDF projects.
  Real-usage gated like every stack (declared dep / real import, never a doc-mention; exact-token).

### Internal
- +6 smoke checks (slug `/`+`_`→`-` with case preserved + a no-underscore regression guard; pdf dep/import
  detection, exact-token disjointness, `is_relevant(stack-general:[pdf])`). `simulate_accumulation.py`'s
  `_store` helper now uses the single `slug_for` (was a third copy of the rule). smoke 249/0 · sim · mypy.
- **Versioning — PATCH:** the deterministic policy's minor triggers are CONTRACT breaks (incompatible
  cycle-record schema, a removed/renamed script or CLI flag, a changed manifest) — the slug fix hits NONE.
  Non-underscore installs are byte-identical; underscore installs IMPROVE (unreachable → reachable) with
  reclaimable orphans (the upgrade note + the shipped near-dup detector handle the one-time migration).
  Matches the v0.1.16 precedent (which even added a CLI flag, still patch).

### Upgrade note (only if you have an underscore-named project dir)
After upgrading, that project's `--pull`/recall targets the correct (hyphen) slug; its **pre-v0.1.17 mirrors
sit under the old `…_…` slug**. Phase 0's near-duplicate-slug detector flags the split — reconcile toward the
slug CC actually uses (a transcript's recorded `cwd` → its on-disk slug dir is ground truth), then retire the
old-slug store. Non-underscore projects are unaffected.

## [0.1.16] — 2026-06-19

### Added (cross-project middle tier — real-usage stack detection + a local→canonical promotion path; additive, backward-compatible → patch)
- **Real-usage `detect_stacks`.** A project's stacks are now inferred from REAL USAGE, never a doc-mention:
  declared dependencies in `pyproject.toml` (PEP 621 `[project]` + optional-deps, PEP 735 dependency-groups,
  and poetry tables — matched as EXACT PEP 503-normalized dep-name tokens, so `sentence-transformers` is
  never read as `transformers`; comments stripped string-aware; extras-safe array parsing), actual `import`s
  in `*.py` (ast-based, so an `import` inside a docstring/string literal does not count), and real marker
  dirs/files (`.claude/`, a `SKILL.md` via bounded `rglob`). Lockfiles are excluded (transitive deps
  over-detect). This kills the old prose-keyword false-match — a stdlib repo whose README merely said
  "rag"/"scraper" used to inherit `rag`/`playwright` — so `is_relevant` binds a `stack-general:[rag]` fact
  only to projects that really depend on / import a RAG library. The middle tier is meaningful, not
  universal-or-nothing. (`_kw_hit` removed; the detection map keeps every stack — `python`/`mypy`/`rag`/
  `gpu`/`playwright`/`claude-code` — now real-usage-gated.)
- **`sync_global.py --promote PROJECT_DIR LOCAL_FACT [CANON_NAME]`** — the local→canonical hand-off
  symmetric to `--pull`. Hands a project-authored local fact UP to the canonical global store and converts
  the origin's own copy into a managed `global_ref:` mirror in one single-shot op (canonical write +
  provenance + origin-mirror + rename cleanup), so a completed call never leaves the dup/orphan a multi-step
  hand-done hand-off would (a stranded project-authored copy that `--gc` can't reclaim, shadowing or
  duplicating the canonical on the next `--pull`). `CANON_NAME` renames (`_`→`-` / drop a date) or dedups
  onto an existing canonical (whose content is **never overwritten** — only the origin is reconciled + the
  holder appended to provenance). Five refusal guards: an already-mirror fact, a non-replicable scope
  (must be `stack-general`/`user-global`), a `stack-general` fact with no `stacks:` (matches no project), a
  destination-clobber of a distinct local fact, and the reserved index name `MEMORY`. Exposed as `cm promote`.
- **Phase-0 promotion-candidate surface + Phase-1 promotion re-audit.** `memory_status.py` surfaces a
  "promote?" signal (authored, non-mirror, unscoped facts whose `type` leans cross-project — feedback/
  reference, capped); the SKILL gains a Phase-1 promotion re-audit symmetric to the existing user-global
  demotion re-audit — re-walk the scope cascade by CONTENT, gated **stricter** than demotion (it is the
  higher-blast-radius direction): conservative floor, a Phase-3 re-verify AND a point-in-time/supersession
  screen, dedup vs existing canonicals by content, a per-pass cap, detect-and-offer only. `_is_mirror`
  promoted to `memory_status` as the single shared definition (smoke-pinned), so the promotion surface and
  `sync_global` share one mirror-recognizer.

### Internal
- `_fact_stacks` extracted as the single `stacks:` parser shared by `is_relevant` + the promotion guards.
  New smoke coverage: the pyproject parser (PEP 621/735/poetry, extras-safe, string-aware comment strip),
  ast-based imports, exact-token stack maps, `is_relevant`, the `_is_mirror` single-source pin, the
  promotion-candidate seed filter, `_fact_stacks`, and the `promote` op surface. `simulate_accumulation.py`
  gains **Probe K** — a hermetic end-to-end of the `--promote` hand-off (create / rename / reconcile-dedup +
  all five refusal guards), asserting the load-bearing invariant that a follow-up `--pull` on the origin is
  `in-sync` (the mirror is already post-provenance), not a STALE rewrite. `references/harness-map.md` +
  SKILL Phase-1/Phase-4 updated to the real-usage detection + dual (demotion/promotion) re-audit model.
- **Patch, not minor:** no removed/renamed script or CLI flag (`--promote` is additive), no manifest or
  cycle-record schema change (legacy records still render). The patch-vs-minor guarantee holds because the
  global store has **0 `stack-general` facts today** — so no live mirror is re-routed by this release; the
  first such facts are created by a later curated promotion pass, after this version ships.

## [0.1.15] — 2026-06-18

### Added (output polish — hanging-indent wrapping + uniform width; additive, backward-compatible → patch)
- **Hanging-indent line wrapping.** Long lines no longer overflow past the banner — they word-wrap to
  the render width with a HANGING INDENT, so a continuation lines up under where its section's content
  began (a `kv` value continues under the value column; a `·` list item under its own text) instead of
  falling back to column 0. New ANSI-aware `_ui.wrap()` / `_ui.li()` measure VISIBLE width (escape codes
  don't count), never split an escape, re-open the active color across a break, and keep an over-long
  single token (a hash / path) whole.
- **Uniform, terminal-adaptive width.** The banner rule and the wrap right-edge now share one width W:
  it fills the terminal when stdout is a TTY (clamped to a readable [60, 100]); a pipe / captured output /
  test falls back to a fixed 60 so non-interactive output stays deterministic. A new `--width=N` overrides
  it on any reporting command and the dashboard.
- Applied across every output (`memory_status`, `sync_global` --list/--network/--tokens/--gc,
  `extract_signals`, and the `render_dashboard` reference) so the whole tool is symmetric on the sides.
  `--json` is untouched; `--ascii` still flattens to pure ASCII (now at the uniform width). The dense
  `--tokens` node table keeps its columns — its trigger marker drops to a hanging line only if it would
  overflow.

### Internal
- `render_dashboard` now imports `_ui.wrap` + `_ui.resolve_width` (its other primitives stay mirrored +
  smoke-pinned). Smoke renders its content assertions WIDE (so wrapping never splits a pinned substring)
  and adds 9 tests covering wrap fit/hang/ANSI-safety, `kv`/`li` wrapping, the ui↔rd wrap mirror, and
  width resolution.

## [0.1.14] — 2026-06-18

### Added (unified visual language across every output — additive, backward-compatible → patch)
- **`_ui.py` — one shared visual vocabulary.** Extracted the final dashboard's look — the `━` banner,
  bold-UPPERCASE `kv` section labels (which carry the hierarchy even in monochrome), budget `bar`s,
  glyphs, auto-gated color, and the `--ascii` fallback — into a new zero-dep, stdlib-only module that
  `memory_status`, `sync_global`, and `extract_signals` now import. Every human-facing report is
  visually coherent with `render_dashboard.py`'s reference (same banner, section style, glyph/color
  palette), each adapted to its own content. `render_dashboard.py` is **unchanged** — it stays the
  byte-pinned reference (37 output assertions + a determinism check); a new smoke **drift-pin** asserts
  `_ui` stays byte-identical to render's primitives, so the unified look can never silently diverge.
- **Restructured the dense reports for clear hierarchy + low cognitive load.** `memory_status`'s 15 flat
  `---` sections → 7 scannable ones (banner · SCOPE · RIGOR · STORES · SIGNALS · GLOBAL · SESSION · NEXT)
  with the per-fact inventory in aligned columns + always-loaded budget bars; `sync_global`
  (`--list`/`--network`/`--tokens`/`--gc`) and `extract_signals` likewise gain the banner + labeled
  sections + status glyphs (✓ in-sync · ↓ missing · ⟳ stale · ◀ trigger). Every datum the SKILL/agent
  parses mid-dream is preserved.
- **`--color` / `--ascii` on `memory_status`, `sync_global`, `extract_signals`** (matching the dashboard):
  `--color=never|always|auto` (default auto — OFF when piped/captured/non-TTY, so agent tool-calls and
  pipes stay clean plain text); `--ascii` flattens glyphs to a pure-ASCII fallback. `--json` output is
  untouched — no color/banner leaks into the machine contract.

### Fixed
- **`--ascii` now flattens every `sync_global` view.** `network`/`token_report`/`gc` printed glyphs
  directly, bypassing the ASCII fallback (would `UnicodeEncodeError` / render mojibake on a non-UTF8
  terminal — the exact case `--ascii` exists to serve); they now buffer and route through
  `ascii_translate` like the other reports.
- **A bare visual flag is never mis-read as a project dir.** `sync_global` and `extract_signals` didn't
  exclude `--color`/`--ascii`/`--no-color` from positional parsing, so e.g. `sync_global --pull --ascii`
  (dir omitted) treated `--ascii` as the project → a bogus slug it would have replicated mirrors INTO.
  Both now filter dash-flags from positionals (the pattern `memory_status` already used).

## [0.1.13] — 2026-06-18

### Changed (product repositioning — docs/messaging only, no code change → patch)
- **Repositioned around the two axes Auto Dream doesn't cover.** Claude Code is rolling out a built-in
  **Auto Dream** (per-project memory consolidation; auto-trigger + a `/dream` command — currently
  server-side-flagged/beta, not GA), which commoditizes the base "consolidate a project's memory"
  pitch. The README, `plugin.json` + `marketplace.json` descriptions, and SKILL framing now lead with
  what Auto Dream lacks: **cross-project shared memory** (the governed global store + promotion/
  demotion cascade) and **verification against the live code** (grep/file/`git log` — fact-checked, not
  transcript-merge), plus tiered context-budget accounting. Positioned honestly as the rigorous,
  fleet-wide **complement** to Auto Dream's per-project baseline. The `dream` trigger and
  all behavior are unchanged — the differentiators already exist in code; this aligns the messaging.

### Notes
- **Strategic context (see roadmap):** Auto Dream + `/dream` are **not yet GA** (server-side flag,
  beta) → a real first-mover window, but contested by public clones (`jl-cmd/claude-dream`,
  `grandamenium/dream-skill` — both per-project, neither code-verifying). Our durable edge is the two
  differentiators above. External / 1.0 / community-directory submission is the open decision this
  repositioning prepares for.

## [0.1.12] — 2026-06-18

### Changed (1.0-prep — docs/comment/test hardening; no behavior change → patch)
- **`memory_status.py`** — fixed a stale comment claiming cycle records "render and are discarded
  today; persisting them is a roadmap prerequisite." `--persist` shipped in v0.1.4 (this was the
  code-comment straggler from the v0.1.11 doc-sync, which corrected the same claim in the `.md` files).
- **`SECURITY.md`** — corrected the secrets-firewall ReDoS note: the regexes aren't literally "linear
  (no nested quantifiers)" — they have no *catastrophic backtracking* (each alphanumeric run and its
  required separator are disjoint) and input is capped at `_PROBE_CAP` = 4000 chars. Same property,
  accurate wording.
- **`tests/smoke.py`** — extended the SKILL↔TypedDict pin from 3 shapes (CycleRecord/Health/Marker) to
  **all nested shapes** (Scope, Rigor, Verification, Entry, Budget + 4 sub-dicts, CrossProject,
  Network + 2 sub-dicts), so SKILL.md's nested schema block can't silently drift from the code.

### Notes
- A **1.0-readiness review** (this session) found the contracts **1.0-safe** (additive-by-construction;
  no breaking change foreseeable in the backlog) and the polish 1.0-grade after these three fixes. The
  **1.0.0 tag is deliberately deferred** to the broader-discovery push, where its stability signal
  earns its keep. Docs + one comment + test coverage, zero runtime dep → **patch**.

## [0.1.11] — 2026-06-17

### Changed (docs + one stale code comment — no behavior change → patch)
- **Doc sync: reconcile the docs with the shipped state.** README now documents the v0.1.8
  **promotion cascade** (fleet-constant vs fleet-varying; Gate 0/1/2) + the v0.1.9 **demotion
  backstop** in the cross-project model, the v0.1.10 **dream-timing** nudge in Usage, and a
  NEURAL NETWORK line in the dashboard example. SKILL.md + harness-map.md: fixed a stale "cycle
  records are not persisted yet" claim that contradicted the shipped `--persist` (v0.1.4); dropped a
  stale "(planned)" tag on the now-shipped demotion re-audit; named the **G2.3** gate it backstops.
  Also re-characterized repo-root `memory/` as a gitignored placeholder (the global store decoupled to
  `~/.claude/memory`), added the dream-timing advisory to harness-map's Phase-0 catalog, and refreshed a
  stale `sync_global.py` comment + the versioning-precedent list.

## [0.1.10] — 2026-06-17

### Added
- **Dream-timing advisory — a no-nag Phase-0 nudge.** `memory_status.py` now surfaces a
  `💤 dream-timing` line (also via `cm status`) when commits have accrued **since the last dream** and
  cross the SUBSTANTIAL band — flagging a good consolidation boundary *before* compaction. Keyed on
  commits-since-marker + marker age (a coarse hint, not a gate — the count over-counts already-
  consolidated work). **Advisory only:** it never auto-fires a dream (explicit-trigger-only is a kept
  design value); silent below the band and on a first consolidation (no prior dream).

### Notes
- Operationalizes this session's dream-timing research (the ideal moment to consolidate is a work-arc
  boundary, before `/compact` degrades the model's curation). One pure, never-crash helper
  (`dream_timing_advisory` — tz-robust float-epoch age, no-marker guard) + a Phase-0 report line + a
  dev-loop note; **no cycle-record schema change, zero runtime dep** → **patch**. The complementary
  *curation-quality* longitudinal signal remains deferred (needs the cycle-log to accrue).

## [0.1.9] — 2026-06-17

### Added
- **Demotion backstop for the promotion cascade — a Phase-1 *content* re-audit (SKILL prose).** Each
  consolidation now re-walks the v0.1.8 promotion cascade over the existing `user-global` facts *by
  content* and surfaces any that would now route lower (e.g. a `mypy`- or release-gated fact →
  `stack-general`) as **detect-and-offer demotion candidates** — never auto-applied. This closes the
  governance loop: the "signal-checked-out" half that backstops Gate 3's deliberately-weak
  applicability gate.

### Changed
- **`extract_signals` is now run-or-justify-skip (Phase 2).** A pass must run the extractor (it reads
  the compaction-proof on-disk transcript) or record an explicit skip-justification — so a compacted
  session can't silently drop the feedback/gotcha signal.
- **Dashboard RIGOR line:** an overridden tier now reads `suggested → applied · override: <why>` (was
  a mislabeled `· applied: <why>` that duplicated the arrow).

### Notes
- **Empirics-first kill (recorded so it's never re-proposed):** the originally-planned *adoption-based*
  demotion-audit (flag a fact with few `projects:` holders) has **no valid signal** — `--pull`
  replicates every `user-global` fact into every project (`is_relevant → True`), so `holders` measures
  pull-activity, not fit (a mis-scoped fact and a universal one both reach all projects). The valid
  signal is content (re-walk the cascade); the longitudinal "stuck across N cycles" form is deferred
  until the per-project cycle-log accrues.
- SKILL prose + a 1-line render relabel; **no cycle-record schema change, no new mechanical detector,
  zero runtime dep**; legacy records still render (the relabel is cosmetic) → **patch**.

## [0.1.8] — 2026-06-17

### Changed
- **Promotion governance: a hard scope-decision cascade replaces the prose bar.** SKILL.md
  Phase 2 now routes each candidate fact to `project-local` / `stack-general` / `user-global`
  via a total, acyclic cascade (Gate 0 → Gate 1 → Gate 2's five hard gates **G2.1–G2.5**),
  keyed on a **fleet-CONSTANT substrate** (the user's OS/account, an always-present CLI like
  `gh`, the Claude Code harness — present in *all* projects → eligible for `user-global`) vs a
  **fleet-VARYING precondition** (a stack/tool/workflow in only *some* projects — `mypy`,
  release-cutting → at most `stack-general`). A `user-global`/`stack-general` promotion now
  records its **deciding gate + the concrete other project named for the applicability gate
  (G2.3)** in the entry's `reason`. Mirrored into `references/harness-map.md`.

### Notes
- Policy/prose change only — **no code, no cycle-record schema change, zero new runtime dep**;
  legacy records render unchanged → **patch**. The complementary **demotion-audit** (flag a
  `user-global` fact never adopted beyond its origin project, via the lagging `projects:`
  provenance) is the committed next cycle — it backstops G2.3, the deliberately weakest gate.

## [0.1.7] — 2026-06-17

### Added
- **`--ascii` dashboard fallback** for older / non-UTF8 terminals: `render_dashboard.py --ascii`
  translates the dashboard's Unicode glyphs to single ASCII chars (width-preserving, so column
  alignment holds), with a catch-all that **GUARANTEES pure-ASCII output** (`.isascii()`; any
  unmapped glyph → `?`). Opt-in — the default Unicode output is byte-identical.

### Changed
- **No-op passes no longer print a RIGOR line.** A true no-op (magnitude 0 + no entries) used to
  render `RIGOR LIGHT · magnitude 0` — an effort estimate on a do-nothing pass; it now collapses
  like the other empty sections. A pass with entries or magnitude > 0 is unchanged.
- **`extract_signals` noise filter** now drops `<task-notification>` / `<teammate-message>`
  envelopes (multi-agent / harness injections the dream meta-test surfaced as false "feedback") —
  a precision improvement to the Phase-2 signal; a human still curates candidates.

### Notes
- All three are additive / cosmetic; backward-compatible → patch.

## [0.1.6] — 2026-06-17

### Added
- **A typed cycle-record contract (`TypedDict`) — static, producer-side drift-catching.**
  The cycle record — the data contract between `memory_status.py` (seeds it), the workflow
  phases (fill it), and `render_dashboard.py` (renders it) — was an untyped dict whose 42-line
  shape was hand-maintained in THREE places (the seed ↔ the renderer ↔ `SKILL.md`'s schema
  block), the recurring source of drift/crash findings. `memory_status.py` now defines the
  whole shape as `TypedDict`s (`CycleRecord` + every nested shape, all `total=False`), and the
  producers/consumers are annotated (`seed_record`/`_provisional_rigor`/`schema_drift` →
  their types; `render`/`_demo_record` → `CycleRecord`). mypy now flags a drifted, renamed,
  extra, or wrong-typed key in the dict LITERALS this codebase emits — the main historical
  drift source. **Honest scope:** the static win is **producer-asymmetric** — `total=False`
  flags a mis-named key via subscript / in a literal, NOT on a `.get()` read, so render's
  defensive reads are covered by the runtime validator (below) + IDE hints, not mypy.
- **A warn-only runtime validator `validate_cycle_record(record) -> list[str]`** (in
  `memory_status.py`): pure, stdlib, NEVER raises. It surfaces the model-slip class behind the
  past crashes — a PRESENT key of the wrong CONTAINER type, at the ACTUAL nesting (incl.
  `health.slug_orphans` / `health.schema_drift`, which nest under `health`) — and is quiet on a
  missing key (a partial record is normal) and on correct types. `render_dashboard.py` runs it
  after parsing and prints any warning to **stderr** (`render_dashboard: cycle-record
  warning: …`), non-blocking.
- **A SKILL↔TypedDict sync test (smoke):** parses the `SKILL.md` cycle-record schema block and
  asserts its top-level key set == `CycleRecord.__annotations__` (and the nested `health` shape
  == `Health.__annotations__`), so the doc can't silently drift from the code — "single source
  for the CODE; `SKILL.md` kept aligned by this test." Added `outcome` (a real optional override
  render already supports) to the schema block so the two agree key-for-key.

### Changed
- **`render_dashboard.py` runs the validator** on the parsed record → warnings to stderr
  (the rendered dashboard on stdout stays **byte-identical** for a well-formed record). The
  read-only record helpers (`_outcome`/`_over`/`_network_section`/`_persist`) take
  `Mapping[str, Any]` (a TypedDict is assignable to a read-only Mapping — this also dissolved
  the old dual-budget-shape friction in `_over`); `_num` keeps `x: object` (guards `.get()`/
  `None` callers). `suggested_tier` widened to `(float, float)` (render coerces via `_num`).

### Notes
- **Zero new RUNTIME dependency.** `TypedDict` is stdlib (3.8+) and runtime-INVISIBLE (a
  TypedDict *is* a plain dict — no runtime cost, the model can still author the record as JSON
  mid-flight). mypy is a **dev-only** maintainer tool: a committed pragmatic `mypy.ini` at the
  repo root (outside `plugins/`, so it never ships) keeps `scripts/` + `tests/` clean WITHOUT
  `--strict` and WITHOUT disabling the TypedDict checks; it is NOT in the dep-free `smoke.py`
  gate. `.mypy_cache/` is gitignored.
- **The static win is producer-asymmetric** (framed honestly): strong on the seed/demo literals
  + cross-module type agreement, near-zero on render's `.get()` reads (those rely on the runtime
  validator + IDE hints).
- Backward-compatible: legacy cycle records still render byte-identically; the validator is
  warn-only and additive; runtime behavior is unchanged → **patch**.

## [0.1.5] — 2026-06-17

### Added
- **Phase-0 detection of slug-orphans + schema drift (detect / report / OFFER only).**
  `memory_status.py` now flags **slug-orphans** — a near-duplicate sibling slug under
  `~/.claude/projects/` (the rename-orphan signature, since a dir rename changes the slug
  and strands the old slug-scoped store), detected by `near_duplicate_slugs` (norm on
  `-`/`_`/case, excluding the slug itself, since `slug_for` is lossy) — and **schema
  drift**: a fact missing the documented `node_type`, a malformed `scope`/`originSessionId`,
  or an index↔file mismatch (`schema_drift` + `drift_findings`). Both are surfaced in the
  Phase-0 report + the cycle-record `health` block + the dashboard, and reconciliation /
  backfill is **offered**, never auto-applied (the model decides in Phase 4).
- **`--pull` warns on a canonical missing a valid `originSessionId`** — before replicating
  a `user-global`/`stack-general` canonical, `sync_global.py --pull` emits a stderr WARNING
  that the gap fans out to every mirror, and **still replicates** (warn, don't block).

### Notes
- **Detection only — no auto-mutation.** Phase 0 never merges, deletes, or backfills a
  store; it detects, reports, and offers. The `_frontmatter` parser was promoted to
  `memory_status.py` (the dependency root) and `sync_global.py` now imports it (single
  definition), gaining CRLF/BOM tolerance.
- **Absence is an advisory, not drift.** `scope`/`originSessionId` are skill-/Claude-Code-
  injected and store-dependent, so their mere absence is reported only as an optional
  backfill advisory (a separate line that may appear on an otherwise-clean store), never a
  drift finding.
- Backward-compatible: legacy cycle records (no `health.slug_orphans`/`schema_drift`) render
  byte-identically; the new keys + detection + warning are additive → **patch**.

## [0.1.4] — 2026-06-17

### Added
- **Realized-rigor capture + cycle-record persistence (the band-calibration apparatus).**
  The cycle record gains `rigor.applied` (the ceremony actually run) and
  `rigor.override_reason`; `render_dashboard.py --persist DIR` appends each rendered record
  (one JSON line) to `<store>/.consolidation-log.jsonl`, idempotently — so a project accrues
  magnitude→(applied, outcome) data a future band calibration can refit against. The
  *suggested* tier stays DERIVED at render (no-drift); `applied` is a stored decision, not
  derivable from magnitude.

### Changed
- **Dashboard `RIGOR` line** shows `suggested → applied · why` when the model overrode the
  magnitude-derived tier (and just the suggested tier otherwise — legacy records render
  unchanged).

### Notes
- **Bands `(2,7)` are KEPT, deliberately, as a coarse HINT — not recalibrated.** A
  sensitivity probe found magnitude agrees with a rich needed-rigor rubric on only ~half of
  passes: the deciding features (always-loaded-bound count, conflicts, prune-pressure) are
  LATE-known, so an EARLY magnitude proxy can't be precision-tuned (`prune_pressure` + the
  2-source rule cover the blind spots). `INDEX_TOKEN_BUDGET` is the binding prune lever
  (~20–27 real facts); `PRUNE_PRESSURE_FACTS` is a terse-pointer backstop.
- **Honest scope of the apparatus:** `applied` is **self-reported** — it catches OVER-rigor,
  not under-rigor; calibrating the dangerous (under-rigor) direction needs LONGITUDINAL
  miss-detection (a later pass finds what an earlier one missed), which the persisted log
  enables but which is future work. Never calibrate bands against the OUTCOME banner —
  mature passes are systematically high-magnitude/low-outcome, so it fails UNSAFE.
- Backward-compatible: legacy v0.1.3 cycle records (no `applied`) render unchanged; the new
  field + flag + log are additive.

## [0.1.3] — 2026-06-16

### Added
- **Pass-tier rigor modes.** `memory_status.py` computes a deterministic, testable
  **suggested rigor tier** (LIGHT / SUBSTANTIAL / HEAVY) from an early *flow* magnitude —
  `git_commits + curated session_candidates` — so ceremony scales with the pass: LIGHT
  verifies inline; SUBSTANTIAL fans out parallel verification + a 2-source check for any
  always-loaded-tier fact + the re-verify/GC sweep; HEAVY adds a completeness critic + a
  hard stop on an over-budget always-loaded write without an explicit prune. It is a HINT
  (the model finalizes it in Phase 2 and may override with rationale). New pure functions
  `suggested_tier()` / `prune_pressure()` + a `rigor` block in the cycle record (seed ↔
  SKILL schema ↔ renderer updated together).
- **Prune-pressure flag.** Set when the always-loaded index is over budget OR the store
  already holds ≥ a threshold of facts — forces prune-or-propose regardless of tier. This
  is the axis the cumulative *stock* (`memories_reviewed`) drives, kept deliberately
  separate from the magnitude tier.

### Changed
- **Dashboard** gains a `RIGOR` line (tier · phase · magnitude, plus a prune-pressure ⚠
  when set); **both the tier and the magnitude are derived from `scope`** at render, never
  stored — so the displayed tier can't drift from its own magnitude (the way `_outcome`
  derives from `entries`). The rigor tier (an input-side effort estimate) is a distinct
  quantity from the write-based outcome banner — a pass can read HEAVY rigor yet LIGHT outcome.

### Notes
- The magnitude is **flow, not stock**: `memories_reviewed` is excluded from the tier (a
  cumulative count would peg every mature project to HEAVY — confirmed against the live
  corpus). `session_candidates` is the **curated** candidate-fact count, not the raw
  extractor `surfaced`. The band cutoffs are **provisional, tunable defaults**, not yet
  empirically calibrated (the curated input was never recorded historically). The record
  exposes the magnitude + `phase` a future calibration could refit against — but cycle
  records aren't persisted yet (they render and are discarded), so persisting them is the
  prerequisite (roadmap).

## [0.1.2] — 2026-06-16

### Added
- **Network token attribution.** `sync_global.py --tokens` + the dashboard now report
  `mirror_index_tokens` — the share of each node's always-loaded index driven by
  replicated `global_ref:` cross-project mirrors — so a mirror-dominated over-budget
  index points at the right lever (demote/GC the canonical in the global store, not a
  futile local prune that just re-pulls).
- **User-global `CLAUDE.md` observability.** `memory_status.py` measures
  `~/.claude/CLAUDE.md` **read-only** and the dashboard shows it as a distinct
  "every project · read-only" line, so the per-session always-loaded cost isn't
  understated. The skill never writes that file.
- **`render_dashboard.py --demo`** — paste-free preview of the dashboard from a
  built-in sample record.
- **Auto-gated ANSI color** in the dashboard: on only when stdout is a TTY and
  `NO_COLOR` is unset (`--color=auto|always|never`); captured/piped output stays plain.

### Changed
- **Dashboard redesign** for readability: one coherent column grid, budget bars,
  UPPERCASE section anchors, dimmed in-row field labels (color only), self-labelling
  name-forward Changes rows (a skipped entry reads `· skipped <name>` — no stray `—`),
  and bracketed citations.
- **`CLAUDE.md` guest posture.** The skill defaults to *not* writing the project
  `CLAUDE.md` — facts route to auto-memory or `AGENTS.md`/`MEMORY.md`; only a genuine
  always-loaded *convention* earns a surgical, in-style line; never create or
  reorganize one; propose (don't perform) trims of user-authored lines. The user-global
  `~/.claude/CLAUDE.md` is strictly read-only.

### Fixed
- **Recall-tier accuracy.** Removed the claim (SKILL.md, harness-map.md, README.md)
  that fact bodies are auto-surfaced by `description:` match — Claude Code has no such
  ambient recall; bodies are read on-demand. Reframed: the `description:` is the
  always-loaded **index hook** that cues an on-demand read. Design unchanged
  (description-as-recall-key still correct; it *is* the hook).
- **Render hardening.** The dashboard now coerces every *model-authored* cycle-record
  value (`_num`/`_clean`) at the network + changes presentation boundary, matching the
  budget rows — a string/`null` numeric or wrong-typed `tier`/`store` can no longer
  crash `render()`. Schema block (`SKILL.md`) updated in lockstep with the seed +
  renderer (`budget.global_claude_md`, `network.*.mirror_index_tokens`).

## [0.1.1] — 2026-06-16

### Added
- `tests/validate_manifests.py` — zero-dependency manifest validator (schema, kebab-case
  names, relative source path, semver) usable anywhere Python runs (no `claude` CLI).

### Changed
- Release process: a local maintainer harness now cuts releases (version bump → validate
  → tag → GitHub Release). Updates reach users via the bumped `version` landing on `main`.
- The multi-agent DevSecOps pentest harness and its findings are now local-only
  maintainer artifacts (not published); `SECURITY.md` remains the public security record.

## [0.1.0] — 2026-06-16

First public release as a **Claude Code plugin**, distributed via a plugin marketplace.

### Added
- **Plugin packaging.** Installable with `/plugin marketplace add
  Zenetusken/consolidate-memory` + `/plugin install consolidate-memory@zenetusken-plugins`
  — no clone, no symlinks. Self-hosted marketplace (`.claude-plugin/marketplace.json`)
  with the plugin under `plugins/consolidate-memory/` (`.claude-plugin/plugin.json`).
  SKILL.md references its scripts via `${CLAUDE_PLUGIN_ROOT}`.
- **Network token observability.** `sync_global.py --tokens` + a dashboard
  "Neural network — token consumption (all nodes)" sub-section: per-node and total
  estimated (≈ chars/4) always-loaded + recall-pool token cost across the shared-memory
  network, plus what each cycle did in lifecycle terms on the triggering node.
- **Memory-lifecycle bounding.** Encoded always-loaded token budgets
  (`INDEX_TOKEN_BUDGET` / `CLAUDE_MD_TOKEN_BUDGET`) with an over-budget ⚠; orphan
  garbage collection (`sync_global.py --gc [--apply]`); index-pointer **upsert** so the
  always-loaded hook tracks the canonical; a re-verification signal for facts untouched
  since the marker.
- **DevSecOps security gate.** A reusable multi-agent white-hat pentest cycle (recon →
  parallel per-surface pentesters with loop-until-dry → 3-vote adversarial verification →
  severity-ranked go/no-go gate) gates each release. Final gate: PASS (0 High/Critical).
- `SECURITY.md` (threat model + enforced security properties + disclosure).

### Security
- Stdlib-only, no network, no `eval`/`exec`/`shell=True`; the only external process is
  read-only `git` invoked with a fixed argument list.
- **Argument-injection guard:** the commit SHA read from the on-disk state file is
  hex-validated before reaching `git` (`memory_status._valid_sha`).
- **Input bounding:** transcript turns are length-capped before regex classification
  (defense-in-depth); secrets firewall drops credential-shaped turns at retrieval.
- The personal `memory/` store is gitignored and excluded from the published plugin.

### Changed
- `install.sh` is now a **maintainer dev-install** (registers a local marketplace +
  installs the plugin) rather than a user-skill symlinker — the symlink model is retired
  because `${CLAUDE_PLUGIN_ROOT}` is only set when loading as a plugin.
- Docs (README, CLAUDE.md, harness-map) updated to the plugin layout.
