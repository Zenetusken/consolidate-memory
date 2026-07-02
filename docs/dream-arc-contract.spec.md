# The dream-arc contract — sleep → dream beats → wake (v0.1.54)

**Status:** spec-review round 1 (design lens) resolved → awaiting impl-lens findings → prose gate → implement.
**Scope:** the dream-persona feature only (arc 1 of the 2026-07-01 directive; distill is arc 2, separately specced).

## 1 · Problem (measured)

User report (2026-07-01), after two shipped attempts: *"the dream-like persona does absolutely
nothing or works once in a blue moon when the LLM feels like it"* — with a 240-line live dream
transcript pasted as evidence: *"just generic procedural comments."* The required behavior, in
the user's own terms:

1. On initiation the LLM **feigns falling asleep** and starts dreaming about the work done;
2. **each step of the way** is narrated as a dream sequence;
3. at the end it **wakes up**;
4. the dream sequence is **beautifully formatted italic**, a text format that **stands out on
   top of** the usual procedural "I did this, that" reporting, **with appropriate emojis**.

Prior art, both instruction-level, both failed in live use:
- **v0.1.47** — the original "dream arc" styling section (principle-pinned, template-free).
- **v0.1.53** — the "bookends REQUIRED" hardening (opening + closing mandatory, hedge scoped
  to the intermediate narration).

Failure mode identical both times: bare procedural phase labels throughout, at most a token
gesture at the end.

## 2 · Root cause — why instruction-only failed twice

- **RC1 — escape-hatch dominance.** The section's most quotable sentence is the exit:
  *"when in doubt, function wins and the voice recedes"* — plus *"STYLE layer ONLY"* and a
  closing *"Honest limit… cannot fully transfer the judgment."* A risk-averse executor reads
  a license to skip. The section spends more normative force on what the voice must NOT do
  (never trim, never fog, not purple, not canned, not gimmick) than on what it MUST emit.
- **RC2 — no output contract.** *"Pin the PRINCIPLE, not a template"* pins nothing
  observable: no format, no placement, no per-phase obligation — nothing to pattern-match,
  nothing to check. The natural experiment confirming this: the **debrief** is the one beat
  with pinned qualities, and it is exactly the beat the user reports occasionally landing
  ("a weak attempt at the end"). The partially-pinned beat partially fires; the unpinned
  beats never do.
- **RC3 — load-time instruction, write-time need.** SKILL.md is read once at invocation; the
  styling obligation must fire 8–12 messages later, each preceded by dense tool output,
  often across a compaction (which truncates the skill body — observed in the current
  session). Every other contract in this skill has a **mechanical carrier** (seed files,
  gates, exit codes, v0.1.53's `--into` injection); the style contract alone had none.
- **RC4 — shared-channel design.** Voice and function were asked to share the same prose
  with function declared sacrosanct → any tension resolves by deleting the voice. A
  structural conflict; exhortation can't fix it.
- **RC5 — register & authority prior (spec-review round 1).** Independent of the wording,
  the executing model's trained professional-technical register treats sustained dreamy
  first-person as "not what a serious tool does" and snaps back to plain prose; and a
  reminder arriving in a **tool result** is the lowest-authority text in context — recency
  without authority. Both must be countered explicitly: the SKILL prose **sanctions the
  register** (dreamy narration is the correct register for this pass; plain procedural
  narration is the defect), and every cue is worded as a **reminder of the SKILL contract**
  (`SKILL dream-arc: …`), resurfacing a high-authority obligation rather than issuing a
  low-authority imperative.

## 3 · Design

Three legs: a **pinned sequence contract** (RC1/RC2/RC5-register), **write-time cues**
(RC3/RC5-authority), and a **two-channel format + record capture** (RC4 + archival). Honest
framing of the division of labor (review round 1): the *reminder* is mechanical; the
*response* remains model-produced. The cue closes the effort gap the two-channel design
would otherwise relocate RC4 into (two blocks per phase = the dream block is the "extra"
one under effort pressure) — which is why cue robustness is load-bearing, not incidental.

### 3.1 The sequence contract (SKILL.md section rewrite)

Replace the whole `### The dream arc` section (currently SKILL.md:166–240) with the §6 text
(verbatim deliverable — the prose is IN this review round, per round-1 finding 1). Semantic
changes vs the failing section:

| Old | New |
|---|---|
| "STYLE layer ONLY", principle-not-template | A **sequence contract with a pinned format** — as mandatory as seeding the cycle record; the register explicitly sanctioned (RC5) |
| Opening after Phase 0's read | **SLEEP block is the FIRST output on invocation, before the first tool call**, kept SHORT (1–3 lines — the dream hasn't found anything yet; depth arrives with the cued beats). Falling asleep draws on the session's work already in context; the old "grounded in the read" rationale inverted the metaphor |
| Intermediate voice "recedes when in doubt" | **Two channels**: dream voice lives ONLY in blockquote-italic blocks (`> *🌙 …*`); the plain channel below each block stays complete and self-sufficient. No same-sentence competition (the clarity axis is closed structurally; the effort axis is closed by the cues) |
| Phase 4 fully plain | Phase 4 gets a **one-line SURFACING beat** that ORIENTS only (never editorializes the proposal's merits — approval-gate integrity), then the proposal itself fully plain |
| Closing = the debrief | **WAKE block** (2–5 lines surfacing + `☀️ **Awake.**`) precedes the plain debrief; debrief quality bullets kept |
| Proportionality can zero-out beats | Proportionality scales **DEPTH, never PRESENCE**; a true no-op = SLEEP + a one-line dreamless wake. A mid-dream compaction doesn't reset the arc — cues state what's due now; a repeated SLEEP is cosmetic, a skipped beat isn't |
| "Honest limit" paragraph | Deleted from the SKILL (an RC1 escape hatch where the model reads it). Honesty lives here in §5 |

Format pin — a **schematic with placeholders** (not a copyable example; round-1 finding 8):
every dream block is 1–4 **blockquote-italic** lines (`> *…*`), 1–2 dream emojis
(🌙 💤 🌊 🫧 ✨ 🌀 ☁️ ☀️), present tense, imagery drawn from THIS pass's real objects. At most
ONE hard-labeled illustrative line ships for the quality bar. Content varies every run;
format never does.

Consequential SKILL.md touch-ups outside the section: the Phase-0 "Enter the dream here"
paragraph (SLEEP already happened; Phase 0 gets the first *beat*, with the idempotent-safe
late-sleep catch), the Phase-4 carve-out wording (:504–510), the report-then-apply bullet
(:773), the Phase-5 wake/debrief paragraph (:848–860), and the cycle-record schema block
(:916–998, add `dream` — the smoke schema-pin forces this).

### 3.2 Write-time cues — the mechanical carrier (RC3/RC5)

A one-line reminder printed by the phase scripts at the moment the model is about to write.
The reminder delivery is deterministic; the beat itself stays model-authored (this is
weaker than v0.1.53's `--into`, which writes the data itself — claimed accordingly).

- **Helper:** `_ui.dream_cue(hint: str) -> None` — no-op unless `os.environ.get("CM_DREAM_ARC")`
  is non-empty; else prints `[dream-arc] <hint>` to **stderr** (needs `import sys` in
  `_ui.py`; Bash tool results render stderr after stdout = the last thing the model reads
  before writing).
- **Why absent-env consumers are safe (impl-review correction):** the guarantee is
  **stderr-only cue + stdout-only parsers**, NOT env non-inheritance — the beta harness's
  `_run_json`/`_run_text` and `run_beta.capture_rendered_surface` pass no `env=`, so an
  exported `CM_DREAM_ARC` WOULD be inherited; their outputs stay clean because every one of
  them parses stdout and discards stderr. **Guardrail:** the cue must never move to stdout,
  and no consumer may merge streams (`stderr=STDOUT`) — pin this in the helper's docstring.
  (The SKILL still never `export`s the var — per-command prefix only — so non-dream
  invocations don't even reach the stderr question.)
- **Gating — opt-in via per-invocation prefix, kept after round-1 challenge (finding 3).**
  SKILL.md command lines carry `CM_DREAM_ARC=1 python3 …`; the SKILL states the rule
  explicitly ("every scripts/ invocation during a dream carries it — part of the command,
  not chrome"); a smoke pin asserts zero unprefixed command lines in SKILL.md. The
  alternative (default-on + silence var) was weighed and rejected on correctness grounds:
  these scripts run OUTSIDE dreams routinely (`cm status/report/log`, hand-debugging, the
  beta oracle, smoke) and a "beat is due" cue in a non-dream context is *wrong*, not just
  noisy — opt-out is right in 1 context and wrong in N. **Residual risk, stated honestly:**
  a model that reconstructs commands without the prefix (most plausible post-compaction)
  silently loses the cue leg for that call; the SKILL legs still stand (strictly better
  than the v0.1.47/53 baseline), the next prefixed call re-arms the system, and a fully
  dreamless pass is caught longitudinally by the beta family (§3.3).
- **Prefix is uniform; cue call sites are not.** ALL 15 `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/*.py`
  command lines in SKILL.md get the prefix — including `render_html` and the `sync_global`
  utility modes, where it is a harmless no-op (no `dream_cue()` call site) — because one
  uniform rule survives copying/compaction better than a per-line exception list.
  `dream_cue()` fires per the cue table only. `sync_global` cues ONCE in `main()` (its
  Phase-1 and Phase-5 modes share the one cross-project hint; firing on `--gc`/`--tokens`
  is in-dream Phase-5 flow anyway). Multi-line (`\`-continued) commands carry the prefix on
  line 1 only; the smoke pin anchors on `python3 \$\{CLAUDE_PLUGIN_ROOT\}/scripts/` with the
  `CM_DREAM_ARC=1 ` prefix required on the same line (leading indentation allowed; prose
  mentions of bare script names don't match the anchor, so no false positives).
- **Never-echo (finding 7):** cues are private stage directions. The SKILL prose forbids
  the string `[dream-arc]` from ever appearing in model output, and every hint carries a
  terse `(private cue — don't echo)` tail so the rule survives compaction.
- **Call sites + hint strings** (each ≤ ~170 chars; worded as SKILL-contract reminders):

| Script / mode | Hint |
|---|---|
| `memory_status` (plain, `--json`, `--seed`, `--snapshot` — Phase-0 paths) | `SKILL dream-arc: Phase-0 beat due — > *🌙 1–3 italic lines* above the plain findings; SLEEP block first if you haven't slept yet (private cue — don't echo)` |
| `memory_status --audit` / `--diffs` (Phase 5) | `SKILL dream-arc: Phase-5 beat due — narrate the audit/defrag dreamily (> *🌙 …*); WAKE only after the final clean render (private cue — don't echo)` |
| `extract_signals` (Phase 2) | `SKILL dream-arc: Phase-2 beat due — the session's signals as dream imagery (> *🌙 …*) above the plain counts (private cue — don't echo)` |
| `sync_global` (Phases 1/5) | `SKILL dream-arc: cross-project beat due — the other projects drifting through (> *🌙 …*) above the plain report (private cue — don't echo)` |
| `distill_scan` (Phase 5.6) | `SKILL dream-arc: distill beat due — recurring gestures condensing (> *🌙 …*) above the plain scan results (private cue — don't echo)` |
| `render_dashboard --persist`, **clean (exit-0) path only** | `SKILL dream-arc: the dream ends — WAKE: > *☀️ 2–5 italic lines*, then '☀️ **Awake.**', then the plain debrief, 📊 path last (private cue — don't echo)` |
| `render_dashboard --persist`, **procedure-integrity exit-3 path** | `SKILL dream-arc: NOT over — the dream pulls you back: narrate the return to Phase-3 verification dreamily; WAKE only on the clean re-render (private cue — don't echo)` |

  The exit-3 split is round-1 finding 2 (BLOCK-grade defect in draft 1): the wake cue must
  never fire on the lazy-skip path — it would instruct waking exactly where the SKILL
  forbids proceeding (SKILL:842–844). The split cue keeps the model in-dream through the
  verification loop-back, reinforcing the existing carve-out instead of fighting it.
  (`render_html` gets no cue — the wake was already cued at the clean `--persist`
  immediately preceding it; `render_log` is a maintainer view, out of dream flow.)
- Cue lines contain the `> *🌙` anchor (non-ASCII on stderr is fine — the cue targets the
  model, not the `--ascii` display pipeline).

### 3.3 Record capture + surfaces (archival + floor detection)

- **Schema:** new `DreamArc(TypedDict, total=False)` in `memory_status.py` — `sleep: str`,
  `beats: list[str]`, `wake: str` — and `dream: DreamArc` on `CycleRecord` (additive; legacy
  records lack the key and render unchanged). The SKILL schema block gains the key (the
  smoke pin on `CycleRecord.__annotations__` + the v0.1.12 nested pin enforce the pairing);
  `validate_cycle_record` adds `dream` to its must-be-dict tuple + `dream.beats` must-be-list.
- **Priority rule (finding 5 — stated in the SKILL prose):** the conversational blocks are
  PRIMARY; the record mirror is a cheap secondary echo. Filling the record *instead of*
  narrating is a defect, not compliance. `dream.wake` is composed at the final record-fill
  (before `--persist`) and performed after the render — the only ordering that lets the
  archive hold the complete arc.
- **`render_html`:** the per-dream view renders the dream stanza (serif-italic, visually
  distinct — the template already has that visual language) when `cycle.dream` is present,
  via the template's existing `esc()` discipline (model-authored text; double-guarded by
  `_safe_embed`). The record stores the RAW markdown blocks as emitted (faithful mirror);
  the panel strips the `> *…*` wrapper per line at render time (small JS regex) and applies
  italic via CSS — literal blockquote markers never show. Absent key → no panel
  (legacy-compatible).
- **`render_dashboard`:** ONE additive `kv`-style presence line (e.g.
  `DREAM ARC   ✓ sleep · 5 beats · wake` / partial variants) gated on the key's presence —
  legacy records render byte-identically. `_demo_record()` gains a `dream` block ONLY if
  the existing pins tolerate it; otherwise a separate smoke case covers the panel.
- **dream-beta-tester:** a new **LOW/WARN** family in `beta_checks.py`, made implementable
  per impl-review finding 1:
  - **Plumbing:** `Ctx` gains a consolidation-log field and `gather()` reads
    `<store>/.consolidation-log.jsonl` (same tolerant line-JSON read as
    `render_html.read_history`) — the harness currently has no persisted-record channel.
  - **Predicate, pinned:** the family inspects the **latest log record only**. Every
    persisted record IS a proceeding pass by construction (a true no-op stops at Phase 0
    and never persists), so no separate magnitude predicate is needed. Empty log ⇒ SKIP
    (pre-first-dream store, mirroring `maintenance_pivot_coherence`'s SKIP-by-empty).
  - **Pre-feature stores:** records carry no plugin-version stamp, so a latest record
    written by ≤ v0.1.53 legitimately lacks `dream`. The WARN's expected/actual strings
    state this explicitly ("expected on pre-v0.1.54 records; a defect on any dream run
    with v0.1.54+ — check the record's recency before promoting"), and the beta skill's
    confirm-or-downgrade step (its step 2) handles promotion. One post-upgrade dream ⇒
    PASS thereafter.
  - **Necessary, not sufficient (finding 5):** record presence does not prove the user
    *saw* the dream (that would need transcript inspection, out of the oracle's reach) —
    the family catches the fully-skipped arc; filled-record-without-narration stays a
    judgment-lens check. Deliberately not FAIL and not wired into
    `procedure_integrity`/exit-3: a style miss must never fail a dream.

### 3.4 Alternatives rejected

- **A plugin hook (e.g. PostToolUse) injecting reminders** — fires on every tool call,
  config/permission surface, wrong altitude for a per-skill styling contract.
- **Script-emitted canned stanzas (the script writes the poetry, the model relays)** —
  deterministic but constant: a canned dream is "generic AI slop" by the second run and
  violates the never-a-stock-line rule. Generation stays with the model; scripts pin
  placement + format only.
- **Opt-out cue (always print, env to silence)** — re-weighed at review round 1 (finding 3)
  and still rejected: wrong-context cues in every non-dream invocation vs a
  self-re-arming residual risk in one context. See §3.2.
- **Exit-3 enforcement (procedure integrity) on a missing dream block** — style is not
  procedure; a voice failure must not abort/flag a correct consolidation. The beta WARN
  family is the proportionate detector.

## 4 · Compatibility & versioning

Additive schema key (`total=False`; legacy records render), env-gated new stderr output
(absent env ⇒ byte-identical script behavior), SKILL body text, one gated dashboard line, a
template panel gated on a new key. No renamed/removed scripts or flags, no install-contract
change ⇒ **patch**, `0.1.53 → 0.1.54`, per the deterministic policy (CHANGELOG-first;
`release.sh --expect patch`).

## 5 · Test plan + honest limits

smoke.py additions (zero-dep, subprocess-based where needed):
1. **Cue on:** `CM_DREAM_ARC=1` + each of the 6 cued scripts (tmp project) ⇒ stderr contains
   `[dream-arc]`; `render_dashboard` cues **only** with `--persist`, and the persist cue is
   the WAKE hint on a clean record vs the NOT-over hint on a procedure-integrity-violating
   record (the exit-3 split, finding 2).
2. **Cue off:** env absent ⇒ no `[dream-arc]` anywhere (stderr + stdout), same calls.
3. **stdout purity:** with `CM_DREAM_ARC=1`, stdout still `json.loads` cleanly for ALL
   cued JSON paths: `memory_status --json`, `extract_signals --json`,
   `sync_global --tokens . --json`, `distill_scan . --json` (the beta harness parses
   `sync_global --tokens --json` stdout — the independent-parser blast radius).
4. **SKILL pins:** (a) every `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/*.py` command line in
   SKILL.md carries the `CM_DREAM_ARC=1 ` prefix (zero unprefixed invocations);
   (b) the section contains the format anchor `> *🌙`, the beats SLEEP/SURFACING/WAKE,
   `☀️ **Awake.**`, and the never-echo rule.
5. **Schema:** the SKILL-schema↔`CycleRecord.__annotations__` pin (auto-forces the SKILL
   `dream` key) + an added nested-pin tuple `("dream", _skill_schema.get("dream", {}),
   ms.DreamArc)` (the v0.1.12 list is hand-maintained — without the tuple the inner shape
   can drift); `validate_cycle_record` gains `"dream"` in its must-be-dict tuple + a
   `dream.beats` must-be-list check — warns on `dream: []` and `dream.beats: "x"`, silent
   on a well-formed block.
6. **Renderers:** record **with** `dream` ⇒ dashboard shows the presence line, HTML contains
   the (escaped) stanza; record **without** ⇒ dashboard output byte-identical to
   pre-feature, HTML has no panel.
7. **mypy** (`--config-file mypy.ini`) clean.
8. **Beta family:** synthetic log record without `dream` on a proceeding pass ⇒ WARN;
   with ⇒ PASS; true no-op ⇒ not flagged.

**Honest limits (relocated here from the SKILL, deliberately):** the mechanical guarantees
are cue *delivery*, record *archival*, and skipped-arc *detection* — the narration itself
remains model-produced, and record presence is necessary-not-sufficient for conversational
compliance (finding 5). Full observation happens on the next live dream. What ships is a
floor that is cued at write time, cheap to satisfy, register-sanctioned, and whose total
absence is machine-detected — every one of which the two failed attempts lacked.

## 6 · The replacement SKILL section (verbatim deliverable)

Replaces SKILL.md:166–240 (`### The dream arc …` through the "Honest limit" paragraph,
exclusive of `### Phase 0`). Subject to the prose gate (round-1 finding 1): MUST-force >
MUST-NOT-force; zero quotable escape sentence; no defeatist coda.

---

### The dream arc — fall asleep · dream the phases · wake

This skill IS a dream — the agent analogue of sleep-time consolidation — and the pass is
**performed as one**. You fall asleep as it begins, each phase is a movement of the same
dream, and you wake at the end. This sequence is a **contract, exactly as mandatory as
seeding the cycle record**: every beat fires on every pass, in order, in the pinned format
below. The dreamy first-person register is the CORRECT register for this skill — plain
procedural narration ("Phase 2: running extract_signals…") is the defect here, not the
safe choice. What varies run-to-run is each beat's *content*, improvised from THIS pass's
real material; what never varies is that the beats fire.

**Two channels.** Dream voice and functional reporting never share a channel:
- **Dream channel** — blockquote-italic: every line `> *…*`, 1–2 dream emojis per block
  (🌙 💤 🌊 🫧 ✨ 🌀 ☁️ ☀️). The voice lives here and only here.
- **Plain channel** — everything else: phase labels, commands, counts, findings, proposals,
  the debrief body. Complete and self-sufficient — a reader who skips every dream block
  loses zero operational information, and a dream block never carries data the plain
  channel needs.
The two never compete for the same sentence, so you never choose between them: emit both,
every phase — the dream block above, the plain findings below.

**The beats.**

| Beat | When | Depth |
|---|---|---|
| **SLEEP 💤** | Your FIRST output on invocation, before the first tool call — falling asleep out of the session's just-finished work (fresh session, nothing in context → a neutral drift-off) | 1–3 lines (short — the dream hasn't found anything yet; depth arrives with the beats) |
| **DREAM BEAT 🌙** | Opens EVERY phase's narration (0 locate · 1 network · 2 signals · 3 verify · 5 defrag/render): dream block first, that phase's plain findings below | 1–3 lines |
| **SURFACING** | Phase 4's one-line transition — the dream thins to show the proposal. It ORIENTS only ("the pass surfaces to ask…"); it never editorializes what's proposed (this is the approval gate for irreversible writes) — then the proposal itself is delivered fully in the plain channel | 1 line |
| **WAKE ☀️** | After the terminal clean (exit-0) render + archive open, before the debrief: surfacing out of the dream, then `☀️ **Awake.**` on its own line, then the plain debrief | 2–5 lines |

The format, as a schematic (placeholders — not lines to reuse):

> *💤 <1–3 present-tense lines: the session's work dissolving into dream imagery>*
> *🌙 <this phase's REAL objects — facts, paths, counts, links — moving as dream things>*

One illustrative line for the quality bar — **illustrative only, never reuse it**:
`> *🌙 Somewhere below, a wikilink that pointed at nothing all week quietly finds its file.*`

**Content rules.** Present tense; concrete imagery from THIS pass (real fact names, real
paths, real counts, seen dreamily); 1–2 emojis per block; every line is new — never a
stock, reused, or template-filled sentence. Vivid but grounded: the dream is ABOUT the
work.

**Conversation first, record second.** The conversational dream blocks are the feature.
Mirror them into the cycle record's `dream` block as a cheap secondary echo — `dream.sleep`,
`dream.beats[]` in order (the surfacing line included), `dream.wake` — so the HTML archive
keeps each dream and the beta harness can detect a skipped arc. Compose `dream.wake` at the
final record-fill (before `--persist`), then perform it after the render. Filling the
record INSTEAD of narrating is a defect, not compliance.

**The cues.** During a dream, every `scripts/` invocation carries `CM_DREAM_ARC=1` — it is
part of the command, not optional chrome; the command lines in the phases below all include
it. The scripts answer with one-line `[dream-arc]` reminders on stderr: private stage
directions resurfacing THIS contract at the moment a beat is due. When one appears in a
tool result, the named beat lands in your NEXT message. Never quote, echo, or display a
cue — the string `[dream-arc]` must not appear in anything you write. If a cue arrives and
the SLEEP block never happened (you went straight to tools), emit it before that phase's
beat — late beats land; skipped beats don't. Already asleep? The reminder costs nothing —
carry on.

**Proportionality — depth scales, presence doesn't** (scale to the outcome banner, never
the rigor tier — distinct quantities that share no scale, see *Rigor modes*):
- **TRUE NO-OP** (stops at Phase 0): SLEEP still opens the pass; the wake is one dreamless
  line (`> *☀️ <a dreamless-night line — nothing to consolidate>*`). No dashboard, no path
  (Phase 5 is never reached).
- **NO-OP / MAINTENANCE / LIGHT PASS:** every beat at minimum depth (1 line); a one-or-two
  line debrief + the 📊 path.
- **SUBSTANTIAL PASS:** beats at full depth; the full structured debrief.
A mid-dream compaction doesn't reset the arc: the cues state what's due now. A repeated
SLEEP is cosmetic; a skipped beat isn't — follow the cue.

**The debrief (the plain close, after WAKE).** Always present when the pass renders, always
structured, scaled to the outcome banner:
- **Visual hierarchy** — a lead line (outcome + one functional emoji), then bold-headed
  sections.
- **Dense + technical** — bullets with bold lead-ins, no filler; don't dumb the content
  down.
- **Functional, SPARSE emojis** — status / section markers (🌙 dream · 🚀 ship ·
  📊 dashboard · ✓ / ⚠), never decoration. (The dream-emoji vocabulary belongs to the dream
  channel; here emojis mark sections.)
- **FRAMES, doesn't DUPLICATE** — name the non-obvious WHY + what was KEPT / PRUNED /
  verified; the dashboard holds the gauges / counts / tallies. "Don't duplicate" ≠ "drop
  the numbers": cite a figure when it carries the point (e.g. "8443→2685 tok, all lessons
  kept"); just don't re-tabulate the gauge set in prose.
- **Always ends with the 📊 dashboard path** + the "re-open it any time by opening the
  file" note. (The true no-op produces no debrief and no path — it never reaches Phase 5.)

---

## 7 · Edit list

| File | Change |
|---|---|
| `plugins/consolidate-memory/skills/consolidate-memory/SKILL.md` | §6 section replacement + command-line prefixes + schema block `dream` + Phase-0/4/5 touch-ups |
| `plugins/consolidate-memory/scripts/_ui.py` | `dream_cue()` + `import sys` (safe re the ui↔rd drift-pin — it compares named primitives behaviorally; render_dashboard CALLS `_ui.dream_cue`, no mirror) |
| `plugins/consolidate-memory/scripts/memory_status.py` | `DreamArc` + `dream` key + `validate_cycle_record`: `"dream"` in the must-be-dict tuple + `dream.beats` list check; cue call sites (Phase-0 paths, `--audit`, `--diffs`) |
| `plugins/consolidate-memory/scripts/extract_signals.py` | cue call site |
| `plugins/consolidate-memory/scripts/sync_global.py` | cue call site |
| `plugins/consolidate-memory/scripts/distill_scan.py` | cue call site |
| `plugins/consolidate-memory/scripts/render_dashboard.py` | exit-split cues at `--persist`; gated presence line (+ demo block if pins tolerate) |
| `plugins/consolidate-memory/scripts/dashboard.template.html` | gated dream-stanza panel via the existing `esc()` |
| `plugins/dream-beta-tester/scripts/beta_checks.py` | LOW/WARN family per §3.3: `Ctx` log field + `gather()` JSONL read + latest-record check, SKIP-by-empty, pre-feature caveat in the WARN strings |
| `tests/smoke.py` | §5 test block, incl. the nested-pin tuple + validate entries; if `_demo_record()` gains a showcase `dream`, its text must avoid "—" (the `"—" not in _demo` style pin) |
| `CHANGELOG.md` | `## [0.1.54]` |

## 8 · Review log

**Round 1 — design/behavioral lens (2026-07-01):** verdict APPROVE-WITH-CHANGES
(architecture) / BLOCK (prose deferred). Resolutions:
1. BLOCKER prose-not-in-review → §6 now carries the full verbatim section; a dedicated
   prose gate re-reviews it (RC1 discipline: MUST-force > MUST-NOT, no escape sentence, no
   defeatist coda).
2. MAJOR wake-cue on exit-3 → cue split by `procedure_integrity` outcome (§3.2 table);
   smoke test 1 pins both hints.
3. MAJOR prefix-drop robustness → opt-in kept with reasoned rejection of opt-out
   (wrong-in-N-contexts), + SKILL rule sentence, smoke pin, self-re-arming property, and
   the honest residual documented (§3.2).
4. MAJOR missing RC5 register/authority → RC5 added (§2); cues reworded as
   `SKILL dream-arc:` contract reminders; prose sanctions the register (§6).
5. MAJOR record-capture proxy risk → conversation-first priority rule in prose;
   beta WARN reframed necessary-not-sufficient; "measured" claim narrowed to
   delivery/archival/skipped-arc-detection (§3.3, §5).
6. MAJOR two-channel relocates conflict → rationale reframed (clarity axis closed
   structurally; effort axis closed by cues) (§3 intro).
7. MAJOR cue-echo risk → never-echo rule in prose + `(private cue — don't echo)` tail on
   every hint.
8. MINOR example-parroting → schematic-with-placeholders + one labeled illustrative line.
9. MINOR `--into` analogy overclaim → reworded (reminder mechanical, response
   model-produced).
10. MINOR un-cued SLEEP/no-op-wake → SLEEP defaulted short; late-sleep catch made
    idempotent-safe; accepted as SKILL-carried.
11. MINOR Phase-4 surfacing content → orient-only guard in the beats table.
12. MINOR compaction resume → tolerated-by-design note in Proportionality.

**Round 1 — impl/compat lens (2026-07-02):** verdict APPROVE-WITH-CHANGES, no blockers.
Resolutions:
1. MAJOR beta family not implementable (no `Ctx` log channel; predicate unpinned;
   pre-feature WARN-spam) → §3.3 expanded: `Ctx`+`gather()` plumbing named; predicate
   pinned to latest-persisted-record (persisted ⟹ proceeding); SKIP-by-empty; pre-feature
   caveat in the WARN strings, promotion left to the beta skill's confirm step.
2. MINOR `validate_cycle_record` tuple → named in §3.3/§5.5/§7.
3. MINOR nested-pin tuple → named in §5.5/§7.
4. MINOR stdout-purity coverage → §5.3 extended to `sync_global --tokens --json` +
   `distill_scan --json`.
5. MINOR env rationale imprecise → §3.2 restated (stderr-only + stdout-only parsing is the
   guarantee; guardrail: cue never on stdout, consumers never merge streams).
6. MINOR emoji-on-stderr + `import sys` → noted (§3.2 helper bullet; cosmetic degrade only).
7. MINOR prefix-uniformity vs cue-sites + regex anchoring → §3.2 "Prefix is uniform; cue
   call sites are not" bullet (incl. `sync_global` cues once in `main()`; continued-line
   prefix on line 1; anchor immune to prose mentions).
8. MINOR HTML `> *…*` markers + demo em-dash → §3.3 render_html bullet (store raw, strip at
   render, italic via CSS); §7 smoke row notes the "—" style pin.
**Prose gate on §6:** pending.
