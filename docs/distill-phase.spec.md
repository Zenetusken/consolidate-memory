# Spec — distill: a workflow-recurrence PHASE in the dream sequence (distill stage 2, the MVP)

Status: SHIPPED v0.1.51 (gate-1 spec-review: report-then-apply + blast-radius SOUND; 1 blocker [normalization vs.
measured forms] + 5 gaps fixed, re-measured. gate-2 code-review: no blockers, safety SOUND; 2 minors fixed —
test-teeth on the firewall assert + quote-before-split — 1 commented) · PATCH · scope: `distill_scan.py` + a
distill PHASE in `SKILL.md` + smoke pins + `cm distill` · the LOCAL-distill stage of the distill arc.

## Context + the two locked decisions

The distill arc's **stage 2**. Where the dream consolidates FACTS into memory, **distill detects repeated
WORKFLOW patterns and PROPOSES a durable artifact** (a command / skill) — report-then-apply.

- **Integration (user-decided):** distill is a **PHASE of the regular dream sequence, in the SAME skill
  package — NOT a separate skill / command / download** (frictionless, one package; overrides the MiMo-style
  separate-`/distill` default).
- **Measure-first DONE** (the advisor's falsifiable test, run on cm's OWN transcripts — the gated release cycle
  ran ~4× this session): the release cycle's steps recur verbatim ≥12× (`smoke.py` 36× · `release.sh` 22× ·
  `gh pr create` 13× · `mypy` 12× · `git checkout -b` 15×) → **premise validated.** Design lessons baked in
  below: strip the `cd <repo>` prefix; **recurring COMMANDS are the signal** (naive tool-SEQUENCE n-grams
  surface the generic edit-loop, not the workflow); **the script surfaces recurrence DATA, the model recognizes
  the workflow + proposes.** "Create nothing is valid + expected."

## Mechanism

### A. `distill_scan.py` — the within-project recurrence scan (new stdlib script)

A LIVE within-project scan (NO persisted tally → D1 stays deferred). REUSES `extract_signals`'s helpers
(`slug_for`, `_norm`, `_looks_secret`, `_window_transcripts`) — do NOT re-implement transcript-reading or the
firewall (the reimplementation-pin / schema-funnel discipline).

- **Input:** a project dir → slug → `~/.claude/projects/<slug>/*.jsonl`.
- **Window:** the project's RECENT transcripts — deliberately BROADER than the dream's `marker..HEAD` (workflow
  recurrence needs multiple work-episodes; a 1-2-session dream window is too thin). Default: a recent window
  (`--since`, default ~30 days back, MiMo-aligned); falls back to all if younger.
- **Extract:** assistant `tool_use` **Bash commands** (the measured signal; other tools deferred). Parse
  `message.role=="assistant"` → `content[].type=="tool_use"`, `name=="Bash"`, `input.command`.
- **Firewall FIRST (on `_norm`, NOT the template transform — GAP-6):** skip any command where
  `_looks_secret(_norm(cmd)[:_PROBE_CAP])`. `_norm` collapses newlines (correct for secret-scanning) — so the
  TEMPLATE normalization below is distill_scan's OWN transform on the RAW multi-line command (it NEEDS the
  newlines to segment). A new source widens the firewall surface; scrub at ingest. The stored `sample` is the
  **already-firewall-screened** command (never a re-fetched raw one).
- **Normalize to a TEMPLATE over MULTI-LINE input (BLOCKER-1 fix — re-measured).** The real channel is 92%
  MULTI-LINE `cd <repo>\n<realcmd>` (only ~0% the single-line `cd && ` join the first draft targeted). So:
  **split** the command into segments on **newline / `&&` / `;`**; **drop pure-`cd` segments AND leading
  `VAR=value` shell assignments** (both constant noise that otherwise rank #1); take the FIRST real segment; for
  a heredoc keep the head before `<<` (`python3 - <<'PY' …` → `python3 -`); drop quoted strings + the
  pipe/redirect tail; then template the head — program + subcommand(s) + flag-NAMES, dropping abs paths
  (`/home/…`, `~/…`), branch-likes (`feat/…`/`fix/…`), and numeric/value args. **Re-measured on cm (1362 cmds):
  cd-noise GONE, the release cycle surfaces cleanly** — `python3 tests/smoke.py` 55 · `git checkout -b` 30 ·
  `git push -u origin` 27 · `./release.sh --expect patch --confirm` 23 · `gh pr create --base main` 14 · `mypy`
  14 · `python3 tests/simulate_accumulation.py` 13. Grouping teeth: `git checkout -b feat/X`==`…/feat/Y`; `git
  push` ≠ `git pull`; a bare `cd /path` → NO template (dropped).
- **Recurrence:** count templates; keep `count >= 2`; rank by count.
- **Output (`--json`):** `{scanned:{sessions,commands}, recurring:[{template,count,sample}], window}` — the
  recurrence DATA only. **No proposal, no workflow-recognition** (that is the model's job in the phase). Stdlib-only.

### B. The distill PHASE in `SKILL.md` (integrated, report-then-apply)

- **Placement:** a new phase AFTER the memory consolidation (Phase 4 apply) and BEFORE the terminal Phase-5
  render — logically the dream's *second output* (artifacts vs facts). One cheap scan, late in the pass.
- **Flow:** run `distill_scan.py` → the model **REVIEWS** the recurring templates, **RECOGNIZES** coherent
  repeated workflows (e.g., the release cycle = `smoke`+`mypy`+`release.sh`+`gh pr`+`git checkout -b`/`push`
  recurring together), **CHECKS not-already-covered** (inventory existing skills/commands in the repo + the
  plugin + `~/.claude`), and **PROPOSES the SMALLEST artifact** (a command or skill) with evidence (the counts).
- **REPORT-THEN-APPLY, hard:** the model PRESENTS the proposal **PLAIN / un-styled** (the Phase-4 carve-out —
  never dream-voice an approval); it **NEVER auto-writes an executable artifact** (skill / command / subagent /
  `CLAUDE.md` rule). The human confirms; only then the model authors it — gated per-artifact, exactly like
  Phase 4's `CLAUDE.md` edits. (Public-plugin blast radius; the conductor/Stop-hook rejection applies —
  auto-authoring an always-on/executable artifact is the highest-blast-radius move.)
- **Confirmation authorizes ONE specific named artifact (GAP-4)** — the exact artifact shown in the proposal,
  NOT "proceed to build out the workflow." A single "yes" is never license to author a suite; re-propose each.
- **GENERICIZE the proposed artifact (GAP-2 — load-bearing for a PUBLIC plugin):** the firewall catches
  credential-*shaped* values, NOT machine-specific ones. So a proposed/authored artifact must carry **no
  absolute paths, no machine/host names, no personal account values** (the recurring `sample` may contain a
  `python3 /home/<you>/…` path or a personal flag — genericize it: relative paths, `<arg>` placeholders). Mirror
  the existing Safety-rule firewall judgment for git-derived candidates (SKILL.md ~L814-819).
- **Gating (MiMo's bar, adapted):** a workflow is a candidate ONLY if it occurred **≥2×** AND has stable
  inputs AND a repeatable procedure AND a clear output/stopping condition AND is **not already covered**. Never
  propose speculative / overlapping / overly-broad artifacts.
- **Announce the window (GAP-5):** distill scans a BROADER window than the dream's `marker..HEAD` (≈30 days,
  file-mtime-granular via `_window_transcripts`), so the phase states it sees commands beyond this dream's scope
  — otherwise the user is confused why distill "sees" out-of-scope work.
- **"Create nothing is valid + expected."** On a thin project or with no coherent repeated workflow, the phase
  proposes nothing — the common, correct outcome on today's small fleet (only cm / maybe job-applicator are rich
  enough). The phase is a cheap scan + a usually-empty proposal → frictionless.

### C. Out of scope (the MVP boundary — anti-bloat)

- **NO auto-authoring** (propose only; human confirms + the model writes on confirmation). The authoring-helper
  sub-skill is a FAST-FOLLOW only IF the proposal proves valuable.
- **NO persisted cross-dream/cross-project tally** (D1 — deferred; this is a LIVE within-project scan).
- **NO cycle-record / dashboard change** (the proposal is in-conversation, report-then-apply, like Phase 4) →
  **no `CycleRecord` schema / TypedDict / smoke-pin change** for the MVP (a dashboard "distill: N proposed/none"
  line is a fast-follow if wanted; it would touch the contract, so it's deferred).
- **KNOWN GAP — authored artifacts are outside the audit envelope (GAP-3, acknowledged, deferred):** a
  distill-authored skill/command (post-confirmation) lands in `skills/`/`commands/` (repo or `~/.claude`), which
  the Phase-5 `--audit` mutation trail (memory store + CLAUDE.md hierarchy only) and `render_dashboard --persist`
  do NOT cover — so it has no audit record. The MVP accepts this hole (artifacts are human-confirmed, so not
  silent); closing it (extend the audit envelope to authored artifacts) is a fast-follow, noted not fixed.
- **NO tool-SEQUENCE n-gram detection** (measured to surface edit-loop noise, not workflows — the model
  recognizes the workflow from the recurring commands).
- **Bash commands only** for the MVP (the measured signal); other tools later only if justified.

## Contract → PATCH

Additive: a new script + a new SKILL phase. **No `CycleRecord` schema change** (proposals are in-conversation),
no removed/renamed key/script/flag, existing installs + legacy cycle records keep working. Backward-compatible
⇒ **PATCH** (v0.1.50 → v0.1.51).

## The pin — smoke tests (`distill_scan.py`)

Fixtures MUST use the **real command forms** (multi-line `cd <repo>\n<realcmd>`, heredoc, bare-`cd`), NOT the
rare single-line `cd && ` join — else a green suite certifies a normalizer that breaks on the dominant 92%
multi-line channel (the BLOCKER-1 trap).
- **Surfaces a repeated workflow (multi-line form):** release-cycle commands ×3 as `cd <repo>\npython3
  tests/smoke.py` etc. → assert the recurring templates surface (count≥2), the `cd` line STRIPPED, ranked.
- **Bare-cd → NO template:** a standalone `cd /path` command → contributes NOTHING (not a `cd <path>` template).
- **Heredoc → head:** `cd <repo>\npython3 - <<'PY'\n…\nPY` → template `python3 -` (body dropped).
- **`VAR=` assignment dropped:** `cd <repo>\nS=plugins/...\npython3 $S/foo.py` → no `S=…` template; the
  `python3` command templated.
- **"Create nothing":** distinct one-off commands → `recurring == []` (nothing at count≥2).
- **Firewall:** a command carrying a secret → ABSENT from the output (scrubbed at ingest); the `sample` is the
  screened command.
- **Normalization teeth:** `git checkout -b feat/X` + `…/feat/Y` → ONE template (count 2); `git push` ≠ `git
  pull` (distinct); no template ever contains an abs path or the `cd` prefix.

## Gates + test plan

- **spec-review (gate-1):** is the normalization sound (cd-strip + templating, no over/under-merge)? the window
  right (broader than marker, firewall-scrubbed)? report-then-apply airtight (no auto-write path anywhere)? the
  MVP boundary correct (no contract change, no auto-author, no sequence n-grams)? the phase placement logical +
  efficient? reuse of `extract_signals` helpers (no reimplementation)?
- **`/code-review` (gate-2):** the scan script (firewall precedence, normalization correctness, recurrence,
  zero-dep, ReDoS) + the SKILL phase (report-then-apply, no auto-write, inventory-first, gating) + smoke teeth.
- `python3 tests/smoke.py` green + `mypy` + `sim` + `claude plugin validate --strict` + dream-beta-test 0 FAIL.
