# Spec — uniform signal schema in `extract_signals.py` (root-cause the `?`/`s?` rows)

Status: SHIPPED v0.1.48 (gate-1 spec-review: zero blockers, all claims verified against source, 4 minor gaps
folded in; gate-2 code-review: CLEAN — 0 issues, 8/8 focus PASS, SHIP) · PATCH · scope: `extract_signals.py` +
a smoke pin

## The problem (observed, user-reported)

`extract_signals.py --json` (the Phase-2 session-signal extractor) emits a **non-uniform** signal
schema. Human-sourced signals carry `signal_type` + `score`; **error-sourced signals do not.** So any
consumer that reads those fields with a fallback — the user's ad-hoc one-liner `s.get('signal_type','?')`
/ `s.get('score','?')`, and even the script's OWN `_report` (`s.get('signal_type','err')`) — renders a
literal `?`/`s?` on every error row. The user's screenshot: every `[error|?|s?]`.

These are extracted, marker-classified **session signals** (`source · signal_type · scope_hint · score ·
text`) — NOT embeddings; there are no vectors. The `?` is purely a **missing-key** artifact, not a
classification failure.

**Measured (not assumed)** — `extract()` over the live job-applicator-python window:

| source | keyset emitted |
|---|---|
| `human` | `[scope_hint, score, sessionId, signal_type, source, text, ts]` — **7 keys, complete** |
| `error` | `[scope_hint, sessionId, source, text, ts]` — **5 keys; missing `signal_type`, `score`** |

## Root cause (3 defects — the complete `?` inventory)

The five signal-append sites grew as **free-form dict literals** with nothing pinning a canonical keyset,
so two of them drifted:

- **A — the two `error` branches omit `signal_type` AND `score`.** `extract_signals.py` L257-258 (the
  redacted-secret error) and L260-261 (the normal error) append `{source, ts, sessionId, scope_hint,
  text}` only. → every `[error|?|s?]`. (Errors correctly **bypass `_classify`** — env gotchas aren't
  human-classified — but that's *why* the keys must be set explicitly, not left absent.)
- **B — the omitted-secret SUMMARY label omits `score`** (also `sessionId`/`ts`). L303-304 appends
  `{source:"human", signal_type:"omitted", scope_hint:"-", text}`. → `[human|omitted|s?]` whenever a
  credential-shaped turn was redacted.
- **C — the `--json` contract docstring never pinned the shape (why it went unnoticed + no test caught
  it).** L199 documents each signal as `{source, signal_type, scope, sessionId, text, ...}` — it says
  `scope` (the code emits `scope_hint`) and omits `score` entirely. An inaccurate, incomplete contract
  is the latent cause; the field-adds (A/B) are symptoms.

**Blast radius (traced):** the ONLY code consumer of `signal_type`/`score`/`scope_hint` is
`extract_signals.py`'s own `_report` (L332), which already uses `.get(…, fallback)`; no consumer depends
on the keys being **absent**, and the score sort/surface logic (L300-301) runs on `human` **before**
errors are concatenated, so an error `score` cannot perturb ranking. The SKILL (Phase 2, L397) just runs
`--json` and the model reads it ad-hoc. No `dream-beta-tester`/`beta_checks` consumer reads the field.

## Mechanism (the fix — at altitude, not 3 spot-patches)

### 1. One constructor = the single funnel (fixes C structurally)

Patching the three drifted sites leaves the exact mechanism that let them drift (free-form literals).
Instead, funnel **every** signal through one constructor so the canonical keyset is a structural invariant
of signal creation:

```python
# Every emitted signal carries EXACTLY this keyset, so any --json consumer sees a value, never a
# missing key (the v0.1.48 "?" fix). The categorical fields signal_type + score are BOTH keyword-
# required (symmetric — gap-1) — a site CANNOT omit them; scope_hint/sessionId/ts default.
def _signal(source: str, text: str, *, signal_type: str, score: int,
            scope_hint: str = "-", sessionId: str = "", ts: str = "") -> dict:
    return {"source": source, "signal_type": signal_type, "scope_hint": scope_hint,
            "sessionId": sessionId, "ts": ts, "score": score, "text": text}
```

All five append sites (2 error · 2 human · 1 summary label) call `_signal(...)`. Because `signal_type`
and `score` are **required keyword parameters**, a future site physically cannot reintroduce the bug.

### 2. The values (semantic correctness at each site)

- **Normal error** (L260-261): `signal_type="error"`, `score=_NA_SCORE`, `scope_hint="env"`.
- **Redacted error** (L257-258): `signal_type="omitted"` (matches the human-omitted convention — it was
  redacted), `score=_NA_SCORE`, `scope_hint="-"`.
- **Human turns / redacted-human** (L283-284 / L278-280): unchanged values, now via `_signal(...)`.
- **Omitted-secret summary label** (L303-304): `score=-1` (the existing omitted sentinel — excluded from
  surfacing), `sessionId`/`ts` default to `""` (a synthetic row has no producing session — the honest value).

### 3. THE design decision — the error `score` sentinel (called out, not buried)

`signal_type="error"` is unambiguous. `score` is the real choice: errors have **no human salience** (they
bypass `_classify` and are appended unranked), so any score is a sentinel. Recommendation:

> **`_NA_SCORE = 0`** — a **named constant** (self-documenting at the use site) PLUS an explicit docstring
> sentence: *"`score` is human-turn salience (2 high · 1 med · 0 low · -1 omitted); non-human (`error`)
> signals carry `_NA_SCORE` (= 0) — N/A, never salience-ranked. `source`/`signal_type` disambiguate."*

Rationale: errors are always appended last regardless of score, and `source="error"` + `signal_type="error"`
mark them non-human, so `0` cannot mislead **in context**. The named constant + the docstring line are what
prevent it landing as an "unexplained 0" (the advisor's concern: a bare `0` conflates "N/A" with
"lowest-ranked human turn" for an external reader). **Alternative for spec-review:** a distinct out-of-band
sentinel (e.g. `-2 = N/A`) removes the conflation entirely at the cost of a magic value displayed as `s-2`.
Recommendation stands on `0`-named-constant + doc; flag if you disagree.

### 4. Correct the contract docstring (fixes C's documentation half)

Rewrite L197-202 to document the **canonical keyset** accurately: `{source, signal_type, scope_hint,
sessionId, ts, score, text}` (was `scope`; add `score`), with the score-semantics sentence from §3.

## The pin — an invariant test (the durable fix; field-adds aren't)

No test caught this; that is C's cost. Add a **smoke invariant** that drives `extract()` over a fixture
transcript and asserts **EVERY** signal carries the canonical keyset — reusing the existing v0.1.43
fixture pattern (smoke L1216-1237: temp `HOME` + `~/.claude/projects/<slug>/` + `.jsonl`). The fixture
must contain all three classes that previously drifted or could:

- a **clean human turn** (→ a scored human signal),
- a **credential-shaped turn** (→ `secrets_omitted ≥ 1` → the omitted-summary label, defect B),
- an **error `tool_result`** (`message.content=[{type:"tool_result", is_error:true, content:[…]}]`) → an
  error signal (defect A).

Assertion: `all(set(s) >= _CANONICAL_KEYS for s in r["signals"])` AND no `[*|?|*]` / `s?` would render
(i.e. `signal_type` and `score` present + non-`None` on every row). Pins the regression so "no `?`" stays
true. **Single-source the key set (gap-2):** derive `_CANONICAL_KEYS = frozenset(_signal("x", "y",
signal_type="z", score=0))` from the constructor itself, so the test's expected keyset and the constructor's
emitted keyset cannot drift apart (the repo's "a contract can't silently drift" convention). The fixture's
**summary-label row is included** in the iteration, so the `>= _CANONICAL_KEYS` form also catches B's full
gap (the label previously dropped `score` + `sessionId` + `ts`, not just one — gap-3).

## Contract impact → PATCH

Additive: adds `signal_type`/`score` to error rows and `score` to the summary label — every existing
consumer already uses `.get(…, fallback)`, and the change makes the code **match** the documented `--json`
contract (a bugfix, not a break). No removed/renamed key, script, or flag. Unrelated to the cycle-record
schema-pin (a different contract — untouched). Backward-compatible ⇒ **PATCH** (v0.1.47 → v0.1.48).

## Out of scope

No change to `_classify` (human-only), to error ranking/ordering (still appended last), to the secrets
firewall, or to the `_report`/display glyphs. No new signal sources. Not touching the cycle-record schema.

## Gates + test plan

- **spec-review (gate-1, the real gate):** is the root-cause inventory complete (are A/B the only `?`
  sources)? Is the constructor the right altitude (vs. spot-patches)? Is the error-`score` sentinel sound
  + documented? Does the invariant test actually exercise all three classes? Iterate to zero issues.
- **`/code-review` (gate-2):** the constructor refactor touches 5 sites — point it at (a) no behavioral
  change to human-signal values, (b) the firewall path intact (redacted error/human still omit the value),
  (c) every site routed through `_signal`, (d) the smoke invariant truly fails pre-fix / passes post-fix.
- `python3 tests/smoke.py` green (incl. the new invariant + the existing v0.1.43 extract tests) · `mypy`
  clean · `simulate_accumulation.py` ✓ · `claude plugin validate --strict` ✓ · dream-beta-test gate 0 FAIL.
