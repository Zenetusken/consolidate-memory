# Spec — pin the DREAM-SEQUENCE styling (sleep → dream → wake) + mandatory HTML auto-open

Status: SHIPPED v0.1.47 (gate-1 spec-review: 2 rounds + scope expansion → zero inconsistencies; gate-2
self-consistency review: 7/7 PASS) · PATCH · SKILL-prose only, no code/schema change

## The problem (observed, user-reported)

These dream-sequence behaviours happen reliably *with this orchestrator* but **no other** orchestrator
reproduces them — currently *implicit*, not pinned. **The vision (user): the WHOLE pass is role-played as
a DREAM ARC — fall asleep → dream → wake — not merely a styled closing line:**

1. **The HTML dashboard auto-opens** at the end of a dream. **Already deterministic in CODE** —
   `render_html` calls `webbrowser.open()` by default (gated only by `--no-open`; headless-safe), and
   the SKILL invokes `render_html … --latest`. So an orchestrator that *doesn't* pop it open is
   **skipping the `render_html` step** — the SKILL never marks it emphatically MANDATORY.
2. **A structured session debrief** (a lead line + outcome, bold-headed sections, dense bullets,
   functional emojis, visual hierarchy, ending with the dashboard path). **Currently UNSPECIFIED** —
   the SKILL says only "present the ASCII dashboard + the path"; the narrative *format* is produced
   from the user's standing prefs ([[prefer-technical-dense-clean-output]]), never instructed.
3. **The whole-sequence dream STYLING (user-added):** an OPENING "going to sleep" role-play (creative,
   coherent with the prior work — an LLM call, not a canned line) + a light dream-VOICE on the
   INTERMEDIATE phase narration (the structured CLI progress the user watches as each phase runs) + the
   closing debrief — ONE coherent dream arc (asleep → dreaming → waking). Currently UNSPECIFIED.

Fix = **SKILL prose only.** The debrief is a model-produced narrative; a code "debrief generator"
would over-engineer it (the *measure-the-need-before-the-mechanism* lesson — the conductor/Stop-hook/
Layer-2 pattern). The need is "make it always happen + always structured + scaled," which an
instruction delivers.

## The real risk: FOUR competing final-message instructions

The SKILL has **four** scattered final-message statements; a naive new one makes it self-contradictory.
**Harmonize ALL of them IN PLACE into ONE protocol — REWORD the offending lines, do NOT just bolt on a
new section** (an added Phase-5 debrief that leaves the Output sentences intact stays self-contradictory):
- **L759 / L767** (Output §): "the output is **not** free-form prose… the render script is the single
  source of the final report — don't hand-write a summary alongside it." Origin (genesis commit
  8021c9d): the stronger stance — *the rendered dashboard IS the report; don't drift into ad-hoc prose*.
  **This spec softens it, deliberately (user-licensed) — and the fix REWORDS L759/L767 IN PLACE:** the
  dashboard stays the single source of the *data* report (don't re-tabulate its numbers in prose), but
  the dream now CLOSES with a structured **debrief** that *frames* it. (Reword them; don't silently reverse.)
- **L713** (Phase-5 step 6): "Present that exact path as the final message" — a SECOND "final message"
  directive in the SAME step as L718-719. Fold both into the one protocol.
- **L718–719** (Phase-5 step 6): "Present BOTH the ASCII dashboard (in-terminal) and the file path as
  the final message." → folded into the one protocol.

## Mechanism (SKILL edits, harmonized in place)

### A. `render_html` = the MANDATORY closing action (Phase-5 step 6)

Reword so it is unambiguously required: **a CLEANLY COMPLETING dream is NOT done until `render_html …
--latest` runs**; its `webbrowser.open()` auto-open is the post-dream payoff (headless degrades to
printing the path — the only non-open path); **never pass `--no-open` in a normal dream.** An
orchestrator that reaches a clean (exit-0) `--persist` and stops without `render_html` has not finished.
(SCOPE: this applies to any pass that REACHES Phase 5. A true Phase-0 no-op — NOTHING-TO-CONSOLIDATE —
never reaches Phase 5, so `render_html`/the path do NOT apply there; it ends with the one-line dream-touch
of §C. Mirror of the exit-3 carve-out: render_html is the close of a *completing* pass, not a universal law.)

**EXCEPTION — subordinate to the procedure-integrity gate (SKILL L674):** when the detector FIRES,
`render_dashboard --persist` **exits 3 and STOPPING there is correct by design** — go run the Phase-3
re-verify loop and re-render to exit 0 FIRST. `render_html` is mandatory ONLY on the clean COMPLETING
(exit-0) pass — NEVER right after an exit-3 `--persist` (doing so would paper over the very lazy-skip
the gate exists to catch). "Mandatory render_html" closes the dream; it does not override the gate.

### B. The session debrief = PIN PRINCIPLES, NOT A TEMPLATE (the subtle trap)

What the user values is *judgment* (a well-synthesized close), not a form filled in. A rigid
skeleton would make debriefs go rote and get *worse*. So "deterministic" here means **always present
+ always structured + scaled to the pass — NOT identical every time.** Spec the QUALITIES, then state
plainly *"judgment fills this; it is not a template":*
- **Dream-framed VOICE (the vision).** The skill IS a dream — the agent analogue of sleep: replay the
  session's actions / workflows, keep what's true, discard / defrag what's stale. The debrief reads as
  **emerging from that dream** — a reflective consolidation voice over what was replayed, kept, and
  pruned. **HARD CONSTRAINT (the user's, load-bearing): this is a STYLE layer ONLY — change the voice,
  NEVER sacrifice a detail or the density.** NOT purple prose, NOT gimmicky, NOT a cut to substance;
  the dense technical content (what changed + why + the verified facts + the path) is fully preserved —
  the dream framing rides *on top* of it, consistent with [[prefer-technical-dense-clean-output]]. Pin
  the PRINCIPLE (a dream-reflective voice), not a script; judgment renders it, scaled to the pass.
- **Visual hierarchy** — a lead line (outcome + one functional emoji), then bold-headed sections.
- **Dense + technical** ([[prefer-technical-dense-clean-output]]) — no filler; bullets with bold lead-ins.
- **Functional, SPARSE emojis** — status/section markers (🌙 dream · 🚀 ship · 📊 dashboard · ✓/⚠), not decoration.
- **FRAMES, doesn't DUPLICATE** — the narrative names the non-obvious WHY + what was KEPT / PRUNED /
  verified; the dashboard holds the gauges / counts / tallies. **"Don't duplicate" ≠ "drop the numbers":**
  cite a figure when it carries the point (e.g. "8443→2685 tok, all lessons kept"), just don't re-tabulate
  the whole gauge set in prose. (This honours L759/L767's real intent.)
- **ALWAYS ends with the 📊 dashboard path** + the "re-open any time by opening the file" note.

### C. Proportionality — scale to the outcome banner (the most important guard)

The debrief tiers to the dashboard's outcome banner so trivial passes don't get bloat:
- **TRUE NO-OP (NOTHING-TO-CONSOLIDATE — stops at Phase 0, never renders)** → a one-line dream-touch (a
  brief stir, "nothing to consolidate"), **NO dashboard, NO path** (the pass never reached Phase 5, so
  §A's mandatory `render_html` does NOT apply — distinct reachability class).
- **NO-OP / MAINTENANCE / LIGHT PASS (proceed to Phase 5, render)** → one or two lines + the 📊 path; the
  dream voice survives as a brief touch, NO section scaffolding.
- **SUBSTANTIAL PASS** → the full structured debrief.
Tier on the **OUTCOME BANNER ONLY**, never the rigor tier: the SKILL insists they are distinct quantities
that share no scale, and `_outcome()` tops out at **`SUBSTANTIAL PASS`** (there is NO `HEAVY` banner —
HEAVY is a *rigor* tier; tiering the debrief on it would re-import the exact conflation the SKILL guards
against). A NO-OP that emits a multi-section debrief is a defect, not the goal.

## D. The dream arc — opening (sleep) + intermediate (dreaming), not just the close

The same dream-framed VOICE + guardrails (§B) extend ACROSS the sequence, so the pass reads as ONE
coherent dream (asleep → dreaming → waking), not a styled last line:

- **Opening — "entering the dream" (the go-to-sleep role-play).** Emit it right **AFTER the first
  `memory_status.py` read** (NOT before — so it's coherent with + scalable to what Phase 0 actually found;
  magnitude/no-op status is unknown before that read): a BRIEF creative opening, the orchestrator coming
  off the session's work and settling into the consolidation dream. **Coherent with the work done**
  (reference it lightly), **creative** (LLM-generated, VARIES — not a canned line), **brief** (1–3 lines),
  **scaled** (a true no-op gets only a one-line stir, not a sleep-narrative; a substantial pass a fuller
  settling-in). PRINCIPLE not template; judgment writes it.
- **Intermediate — dream-VOICE on the phase narration.** The per-phase narration the user watches in the
  CLI (the investigation phases — Phase 0 locate · Phase 1 orient · Phase 2 gather · Phase 3 verify ·
  Phase 5 prune/defrag; the list is ILLUSTRATIVE, not exhaustive) carries a LIGHT dream-voice — the phases
  as the dream's movements (drifting the memory-scape, sifting truth from staleness, pruning / defragging).
  **HARD CONSTRAINT — functional clarity is SACROSANCT:** the user must still see, plainly, WHICH phase,
  WHAT command ran, and WHAT it found. The dream-voice is a light touch on the phase framing / transitions
  — it NEVER replaces or obscures the technical substance (commands, counts, results) the narration exists
  to surface. Style ON TOP of function, never instead of it; when in doubt here, **function wins and the
  voice recedes**.
- **CARVE-OUT — Phase 4 (report-then-apply) stays PLAIN, never dream-styled.** The proposed-consolidation
  diff + the explicit `CLAUDE.md`-edit call-out (the user's approval gate for committed, team-shared,
  always-loaded churn — SKILL L420-432) is the highest-clarity-stakes moment: fogging an approval prompt
  risks a mis-approved IRREVERSIBLE write. The dream-voice frames the *investigation* phases; the Phase-4
  approval prompt is presented plainly, un-styled. (An instance of "function wins" — named for the one
  phase where the cost of fogging is irreversible.)
- **Closing — the debrief = waking (§B / §C).** The structured debrief is the wake-from-the-dream synthesis.

**Shared guardrails (all three movements):** PRINCIPLE not template (varies, judgment-rendered) · SCALED
to the pass (a NO-OP gets a one-line stir, not a full role-play — §C) · style layer ONLY, **never sacrifice
functional clarity / detail / density** · not purple prose, not gimmicky ([[prefer-technical-dense-clean-output]]).
The INTERMEDIATE carries the sharpest risk (fogging the work-in-progress the user relies on) — it gets the
lightest touch.

## Contract impact — NONE (→ PATCH)

SKILL-prose only. No code change (`render_html` auto-open already exists). No cycle-record schema
change — the edits must NOT touch the `CycleRecord`/Output schema block (the smoke pin
`set(skill_schema)==CycleRecord.__annotations__` must stay green). No removed/renamed script or flag.
Backward-compatible ⇒ PATCH.

**Implementation guard (smoke-pin hazard):** add **no ` ```json ` fence** anywhere before the schema
block — the smoke pin does `_skill_text.index("```json")` on the FIRST fence (the Cycle-record schema
block, which sits AFTER the workflow phases). A json fence added in the opening/phase/debrief prose would
hijack the pin and break `tests/smoke.py` despite "no schema change". Prose / non-json fences only.

## Honest limit

A SKILL instruction **raises the floor** — every orchestrator now gets the auto-open + a structured,
scaled debrief. It **cannot fully transfer the judgment** that makes a *great* synthesis (that's model
capability, not instruction). This is a real improvement; don't oversell it as "every orchestrator now
produces this exact quality."

## Gates + test plan

- **spec-review is the real gate** (gate-1): does the edit HARMONIZE the three instructions (no
  surviving contradiction), pin principles (not a rigid template), scale to the outcome banner, and not
  contradict the Rigor/Output sections? Iterate to zero inconsistencies.
- **`/code-review` (gate-2) is low-yield on a prose diff** → point it at SKILL **self-consistency** +
  confirm the **smoke schema-pin is untouched** + `python3 tests/smoke.py` green (the SKILL schema block
  is unchanged) + `claude plugin validate --strict`.
- No new tests (no code surface). The behaviour is verified by the SKILL reading coherently end-to-end.

## Out of scope

No `render_debrief.py` / code generator (over-engineering). No change to `render_html`'s auto-open
(already correct). No new emoji/format config. Not touching the dashboard's data rendering.
