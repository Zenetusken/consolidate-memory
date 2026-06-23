# Spec — signal-pipeline hardening (v0.1.53): the noise + crash + dream-arc fixes

**Status:** DRAFT (gated, "fix everything" arc — the user's v0.1.51 live-run logs showed ~one lingering
defect per recent release).
**Bump:** PATCH (all backward-compatible — `--json` schema unchanged, new flag is additive, SKILL prose;
legacy cycle records still render, existing installs keep working).

## Ground truth (measured on job-applicator's real transcript, the screenshot window)

`extract_signals --json --since 2026-06-22T00:00 --max 80`: **39 human signals surfaced, ~18 pure noise**
(compound acks · `[Image #N]`-prefixed · path-only); **8 error signals, 0 durable gotchas** (4 lint/format,
1 inline-script traceback, 1 Claude-Code permission-denial, 2 test-debug tracebacks). The "statement" bucket
is a noise dump; the error channel is ~100% transient noise. Plus a hard crash (`KeyError: 'audit'`) and the
dream-arc styling barely manifests. Seven defects, each mapped to a recent release.

---

## Bug 1 — compound acks surface as signal *(v0.1.50 cluster)*

**Symptom:** "Ship it please", "Yes ship it", "Yes go ahead", "Let's continue", "Sure let's allow up to 50",
"Ship it and let's continue logically" → all classified `statement`/score-1 and surfaced as real candidates.
**Root cause:** `_ACK` (`extract_signals.py:170`) is anchored `^\s*(ack-word)\b[\s.!]*$` — it only matches a
turn that is *exactly* one ack word. Any trailing filler ("please", "and continue") escapes → falls through
to `statement`. Also `_classify` (`:232`) checks `_ACK` *before* `_MARKERS`.
**Fix:**
1. Reorder `_classify`: check `_MARKERS` **first**, then `_ACK`, then `statement`. So a marker-bearing turn
   ("yes, but **always** use X") is a `preference`, never swallowed by a broadened ack. (Markers are the
   higher-precision signal; an ack is the residual.)
2. Broaden `_ACK` to match a leading ack word **+ trailing filler** — ack-word, then only
   `(please|it|them|thanks?|and …|let's continue/proceed …|now|logically|structurally|the …)`-class filler to
   end. Add the user's frequent forms: `ship it`, `retry`, `continue`. Keep it anchored (`^…$`) so it matches
   *short control turns*, never a long turn that merely *starts* with "yes".
**Risk:** over-matching a real preference that opens with an ack word — mitigated by the reorder (markers win
first) + keeping the ack pattern anchored to short, filler-only tails. Tested both directions.

## Bug 2 — `[Image #N]` markers leak into surfaced text *(v0.1.50 cluster)*

**Symptom:** "[Image #1] Now the animation … is completely broken" surfaced verbatim with the marker.
**Root cause:** `_NOISE` (`:64`) matches `\[Image:` (colon) — the *old* `[Image: source: …]` form — NOT the
current `[Image #N]` harness prefix. And dropping the whole turn would lose real feedback that *follows* the
marker.
**Fix:** add `_strip_markers(text)` that removes leading `(\[Image[^\]]*\]\s*)+` (one or more) from a human
turn **before** classify/store. If nothing remains → count as noise (image-only turn). If text remains →
classify the stripped text (keep the real feedback, drop the marker). Do NOT widen `_NOISE` to drop the whole
turn (that loses signal).

## Bug 3 — path-only turns surface as statements *(v0.1.50 cluster)*

**Symptom:** "'/home/drei/Pictures/Screenshots/Screenshot from ….png' '/home/…'" surfaced as `statement`.
**Root cause:** no filter for a turn that is *only* pasted file path(s).
**Fix:** in the noise check, drop a turn that — after `_strip_markers` + whitespace — is **only** quoted/bare
absolute-path tokens (`^(['"]?\/\S+['"]?\s*)+$`). A turn that mentions a path *plus prose* is kept (only
path-ONLY is noise).

## Bug 4 — the error channel is ~100% transient noise *(v0.1.49)*

**Symptom (8/8 noise):** ruff lint (`E501 Line too long`), ruff format (`Would reformat` / `All checks
passed!`), an inline-script traceback (`File "<stdin>"`), a Claude-Code permission denial, test-debug
tracebacks.
**Root cause:** `_ERROR_NOISE` (`:79`) filters only `<tool_use_error>`. v0.1.49 *deliberately* left lint
unfiltered ("a free-form match that rots"); but the live data shows the residual is ~all noise, and the user
explicitly wants it gone. The byte-noise-dedup keys lint per-file (`_error_key`) so 3 E501s in 3 files don't
collapse.
**Fix (precise, measured — not a blanket):**
1. **Claude-Code permission denials** — `^\s*Permission for this action was denied by the Claude Code` →
   harness artifact, identical class to `<tool_use_error>`, **zero** env signal. Filter. (lowest risk)
2. **Lint / format** — `^(\s*Exit code \d+\s*)?(===\s*)?ruff` · `\bE\d{3}\b.*\bLine too long\b` · `\bWould
   reformat\b` · `\bwould be reformatted\b` → transient style, never a durable env gotcha. (user-requested)
3. **Inline-script tracebacks that are the MODEL's own logic bug** — a traceback whose frame is
   `File "<stdin>"` or `File "<string>"` (a `python3 -c`/heredoc the model wrote) AND whose exception is
   NOT `ModuleNotFoundError`/`ImportError` (those ARE durable env facts — the v0.1.49 carve-out) → the model's
   transient mistake, not an env gotcha. Filter.
**Preserved:** a real bash/stderr env error (unwrapped exit codes, 401s, connection failures, a genuine
`ModuleNotFoundError` from `python3 -c "import x"`) still surfaces. `MAX_ERRORS` + `_error_key` unchanged
except: extend `_error_key` to also strip `--> path:line:col` lint locations so multi-file E-codes collapse
to one class IF any lint survives.
**Risk:** the lint/format patterns are the "rots" concern v0.1.49 flagged — kept precise (anchored to ruff's
stable output shape) and flagged for spec-review stress-testing. Each filter is a separate, independently
testable arm.

## Bug 5 — `KeyError: 'audit'` (the cycle record can't take the audit block) *(v0.1.22 flow, surfaced v0.1.51)*

**Symptom:** the model hand-rolled a merge of `--audit` stdout into the cycle JSON (`d["audit"][k]=…`) → crash
(the seed has no `audit` key).
**Root cause:** `memory_status.py --audit <snapshot>` (`:1945`) only **prints** the diff; the SKILL (`:729`)
tells the model to *manually* "paste that into the cycle record's `audit` block" → error-prone improvised
merge, every dream.
**Fix:** add `--into <cycle-json>` to the `--audit` path (mirrors the existing `--diffs <cycle-path>`
pattern): after computing `diff`, if `--into` given, load the cycle JSON, set `cyc["audit"] = diff`, write it
back (best-effort, never crash a dream — same try/except as the log append). SKILL Phase-5 step 5 changes
from "paste that in" to "run with `--into <the --seed path>`" — deterministic injection, no model merge, no
KeyError. (Defense-in-depth: the seed already declares `audit: Audit` in the TypedDict; `--into` populates it.)
**Risk:** none material — additive flag; absent `--into` = current print-only behavior (backward-compatible).

## Bug 6 — the dream-arc styling barely manifests *(v0.1.47)*

**Symptom:** "totally absent save for a weak attempt at the end" — a token gesture, not the sleep→dream→wake
arc.
**Root cause (instruction, not just model-capability):** the dream-arc section (`SKILL.md:166-232`)
**over-hedges** — "functional clarity is SACROSANCT … **when in doubt, function wins and the voice
recedes**." Every real dream is dense + technical, so the model *always* resolves "in doubt → function wins"
→ the voice recedes in exactly the context it exists for. The hedge is self-defeating.
**Fix (instruction-level — honest about the limit):**
1. Make the **opening** (post-Phase-0) and the **closing debrief** voice **REQUIRED**, not hedged — they are
   LOW clarity-risk (they don't fog work-in-progress) and are the felt bookends of the arc. Lift them out of
   the "when in doubt, recede" rule.
2. Scope the "function wins, voice recedes" hedge to ONLY the **intermediate phase narration** (where it
   belongs — that's the high-clarity-stakes movement) and the Phase-4 carve-out (already plain).
3. Keep the "varied, not a template, not purple" principle + the honest-limit caveat (instruction raises the
   floor; can't fully transfer judgment).
**Risk:** it remains partly model-capability (the honest limit stands); this raises the floor by removing the
self-defeating hedge at the two safe points. No pipeline risk (prose). *If spec-review judges this too
subjective to bundle, it splits to its own follow-up — the other six are concrete.*

## Bug 7 — Phase-2 `--json` schema is undiscoverable *(v0.1.48)*

**Symptom:** the model inspected `--json` with `d.get('surfaced')` and `s.get('kind')` → both `None` (the
keys are `counts.surfaced` and `signal_type`); confusing `None ::` rows.
**Root cause:** SKILL Phase-2 (`:397`) shows `extract_signals.py --json` but not the output key schema; the
model guesses.
**Fix:** in SKILL Phase-2, state the key schema inline (`counts.surfaced`, each signal's `signal_type` /
`scope_hint` / `score` / `text`) AND note that the **human-readable** `extract_signals.py` (no `--json`) is
the right form for *eyeballing* (the `_report` table is already correct); `--json` is for machine capture.
**Risk:** none (doc only).

## Tests (smoke, zero-dep)

- **Bug 1:** "Ship it please" / "Yes ship it" / "Let's continue" / "Sure let's allow up to 50" → `ack`/score-0;
  "Yes, but always validate X" → `preference` (reorder proves markers win); a plain long statement → `statement`.
- **Bug 2:** "[Image #1] real text" → marker stripped, classified on "real text"; "[Image #1] [Image #2]" only
  → noise (counts.noise += 1, not surfaced).
- **Bug 3:** "'/home/x/a.png' '/home/x/b.png'" → noise; "see /home/x/a.png — it's broken" → surfaced (path+prose).
- **Bug 4:** each arm — permission-denial / ruff-lint / ruff-format / `<stdin>` non-import traceback → dropped
  (counts.noise); a real `ModuleNotFoundError` from `python3 -c` AND a bash 401/connection error → KEPT;
  multi-file E501 → one `_error_key` class.
- **Bug 5:** `dangling`-style helper test — `--audit … --into <cycle>` writes `cyc["audit"]`; absent `--into`
  leaves behavior unchanged. (Unit-test `audit_diff` injection without touching $HOME where possible.)
- **Bug 6/7:** SKILL prose pins — the opening/closing are stated as required; the Phase-2 schema keys appear.

## Non-goals

- No `--json` schema change (the keys are correct; bug 7 is discoverability).
- No deterministic/scripted dream-voice (conflicts with "varied, judgment-rendered"); bug 6 stays
  instruction-level.
- No new error *ranking* (errors stay unranked + capped); bug 4 is filtering, not scoring.
- The D1 cross-dream recurrence multiplier stays deferred.

---

## Review resolutions (spec-review #2 → zero)

**Bug 1 — authored logic (BLOCKER resolved; the operating point is "zero signal-turn false-positives,
catch the unambiguous short acks; long ack-ish turns stay `statement`/surfaced — the safe direction").**
- Reorder `_classify`: `_MARKERS` **first**, then ack, then `statement` (so a marker-bearing turn can never
  be demoted to ack — reviewer verified the 22 bare ack words trip no `_MARKERS`, so the reorder alone is
  zero-regression).
- Ack = exact single-word `_ACK` (unchanged) **OR** a **control-opener + short** turn:
  ```python
  _ACK_LEAD = re.compile(r"^\s*(yes|yep|ok(ay)?|sure|perfect|great|thanks?|thank you|ship it|go ahead|"
                         r"do it|proceed|continue|implement it|push|merge|retry|approve|next|dream|"
                         r"let'?s (go|continue|proceed|ship|do it|finish|wrap))\b", re.I)
  _ACK_MAX_WORDS = 7
  def _is_ack(text): return bool(_ACK.match(text)) or (bool(_ACK_LEAD.match(text)) and len(text.split()) <= _ACK_MAX_WORDS)
  ```
  Anchored alternation + a word-count bound ⇒ ReDoS-free (no nested quantifiers).
- **Pinned demote/keep table (the test oracle — real turns from the window):**
  - DEMOTE→ack: `Yes go ahead` · `Ship it please` · `Yes ship it` · `Retry please` · `Let's continue` ·
    `Sure let's allow up to 50` · `Implement it now` · `Ship it and let's continue logically` (6w).
  - KEEP (markers win, score 2): `Please make a second complete end-to-end sanity test…` (preference) ·
    `I want us now to focus on…` (constraint, "i want") · `Let's go with B6 now…` (decision, "go with").
  - KEEP as `statement` (score 1, surfaced — NOT demoted): `Let's add … a toggle in the search modal` ·
    `Well that's not exactly what I was proposing` · `Sure I'll live test it, give me a series of logical
    verification patterns` (13w — the word-bound protects it though it opens with "sure").
  - Accepted misses (stay `statement`, surface): long acks like `Yes ship it and follow up with the docs`
    (9w). Better to miss an ack than eat a signal.

**Bug 4 — three resolutions:**
- **Arm 1 broadened to the auto-mode-classifier FAMILY** (the live "temporarily unavailable… auto mode
  cannot determine the safety" message is the same harness-artifact class as the permission denial and
  survived the spec's arm 1): anchor on the specific phrasings
  `denied by the Claude Code auto mode classifier` · `auto mode cannot determine` ·
  `temporarily unavailable, so auto mode` — NOT a blanket "auto mode".
- **DROP the `_error_key` lint-location extension** — it's dead code (arm 2 filters lint before
  `_error_key` runs) and risks merging distinct codes (`E501`≠`E402`). `_error_key` unchanged.
- Arm 2 precision: keep `E\d{3}` **PAIRED** with `Line too long` (never standalone); anchor
  `Would reformat`/`would be reformatted` to a ruff context (line-start / `Exit code` / `ruff`
  co-occurrence), not free-floating — directly answers the v0.1.49 "rots" concern.
- All new arms slot into the **same post-firewall `elif` chain** (after `_looks_secret` at :324, alongside
  `_ERROR_NOISE` at :328) so a credential-shaped error is still OMITTED, never noise-dropped.

**Bug 5 — two mechanical details (verified against source):**
- The `--into <path>` value MUST be added to `_argpaths` (:~1900) or it's mis-read as the positional
  `project_dir`. (Smoke test asserts `project_dir` is NOT clobbered.)
- Write via `_write_private` (0o600 atomic — the cycle JSON holds fact bodies; mirrors `--diffs`/`--snapshot`),
  in a try/except that falls through to today's `print(json.dumps(diff))` on failure ⇒ strictly additive.

**Bug 2/3 — ordering made explicit:** strip leading `[Image…]` markers → run the firewall on the STORED text
(no leak) → the path-only check runs on the STRIPPED, capped `probe`; unix-absolute-path-only by design
(Windows/relative paths are a deliberate non-goal, not a bug).

**Bug 6 — ships HERE** (the hedge is one bullet, :190; localized edit; splitting would orphan a trivial
change). **Bug 7 — doc-only, confirmed.**

**Tests added:** (a) the Bug-1 demote/keep table above; (b) Bug-4 each arm incl. the auto-mode-unavailable
message dropped + a real `ModuleNotFoundError`/bash-401 KEPT; (c) `--audit --into` writes `cyc["audit"]` AND
`project_dir` not clobbered; (d) Bug-2/3 strip+path-only on the stripped probe. Baseline 412 → expect green.

**Bump stays PATCH** (reviewer ran the suite at 412, traced every affected fixture, no pin flips).

## Implementation refinements + empirical validation (measure-don't-assert)

- **v0.1.49 REVERSAL — classifier-denials are now NOISE, not "highest-signal".** v0.1.49 deliberately KEPT
  classifier-denials (with a smoke test pinning it). The user's real-run logs + spec-review #2 both treat them
  as noise, and on reflection a classifier denial is a *transient harness event*, not a durable env gotcha (the
  real lesson — e.g. never-rm — is authored from session context, not the denial row). Arm 1 drops the
  auto-mode-classifier FAMILY (denial + the model-unavailable message); the existing v0.1.49 test was flipped
  KEEP→DROP with a comment recording the reversal. A real filesystem `PermissionError: [Errno 13] Permission
  denied` is KEPT (arm 1 anchors on "denied by the **Claude Code auto mode classifier**", not bare "denied").
- **`_strip_markers` extended to leading QUOTED paths (not just `[Image #N]`).** Real screenshot pastes are
  `'/…/Screenshot from <date>.png' '/…' … THEN the actual instruction` — `norm[:300]` truncated the prose off
  the end, so the surfaced signal looked like path-noise but carried a real directive. Stripping the leading
  quoted-path run reveals the prose. A BARE leading path is left intact (may be the subject). `_PATH_ONLY`
  (quoted-with-spaces + bare) still drops a pure path-only turn.
- **Measured before→after on the screenshot window** (`--since 2026-06-22T00:00 --max 80`, job-applicator):
  error signals **8→3** (lint/format/auto-mode/inline-bug dropped; the 3 left are a real test failure, a bare
  exit-code, and the secret-omitted label), **0** `[Image]`-leak (was several), **0** path-leak, **12** acks
  correctly demoted to score-0 (were mis-scored as statements), and the formerly-path-noise turns now surface
  their prose. **443 smoke + mypy green.**

## Code-review round 2 (3-agent /code-review) — refinements

0 blockers; SHIP. Two correctness findings + precision/test polish folded in (449 smoke + mypy green):
- **`_is_ack` redesigned: whole-turn-vocab, not opener+length (CONFIRMED recall regression).** The ≤7-word
  control-opener rule demoted SHORT but signal-bearing turns ("proceed with the postgres migration", "yes the
  bug is in parser.py") to score-0. Replaced: an ack is now a turn whose ENTIRE content is ack-vocabulary
  (strip affirmations/control-verbs/filler → empty remainder). A content noun after the verb keeps it as
  `statement`. ("Sure let's allow up to 50" now correctly stays a statement — the "50" is a decision.) Re-measure:
  acks-demoted 12→10 (the 2 with content nouns are no longer demoted; no signal loss).
- **Error arm 3: drop only LOGIC-BUG exceptions, not "non-import" (PLAUSIBLE over-match).** A `<stdin>/<string>`
  traceback is the model's own inline bug only when its exception is a code-bug class (KeyError/NameError/…).
  A real env error from a `python3 -c` probe (a down-DB `OperationalError`) or a `.py` stack with an incidental
  `<string>` frame is KEPT. Re-measure: error signals 3→4 (one real env gotcha restored).
- **Precision/LOW:** dropped the bare `\bruff check\b` arm (it over-matched "FileNotFoundError: …ruff check…");
  `--audit --into` now prints a stderr skip on a non-dict cycle root (no silent no-op); SKILL says run `--into`
  LAST in step 5 (it read-modify-writes the seed).
- **Test rigor:** the bug-5 assertion now bites the `_argpaths` regression (asserts the mutation-log lands under
  the PROJECT slug); added the quoted-path-only→empty integration path + the env-error-KEEP cases (B/G).
