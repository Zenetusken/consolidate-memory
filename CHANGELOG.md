# Changelog

All notable changes to **consolidate-memory** are documented here. This project
follows [Semantic Versioning](https://semver.org/) (pre-1.0: minor versions may make
breaking changes). Installed plugins auto-update at Claude Code startup when this
version changes on `main`.

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
