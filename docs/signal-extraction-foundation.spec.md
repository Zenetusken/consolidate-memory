# Spec — signal-extraction foundation: 2 channel-precision sharpeners (distill stage 1)

Status: SHIPPED v0.1.50 (gate-1 spec-review: no blockers, both prototyped, 4 gaps folded in; gate-2 code-review:
no blockers, 8/8 PASS — the one MINOR [hex/clock over-merge asymmetry] fixed + pinned) · PATCH · scope:
`extract_signals.py` + smoke pins · the FOUNDATION stage of the distill arc.

## Context

The `signal-extraction-discovery` (5-lens, measure-first) partitioned every candidate into build-now / defer /
kill against a 3-part bar: ship only if **MEASURED-real AND non-redundant with the existing 3 sources + git AND
zero new firewall surface.** The decisive result: **SHARPEN channels already parsed; don't add sources** — every
new-source candidate failed (file-hotspots = git-derivable; command source = 87% `cd` + 5% firewall-trip +
already-covered by the error channel). This spec ships the **2 unanimous** sharpeners. The discovery's 3rd
build-now item (a literal-salience nudge) is **deferred here** (below), per the skeptic lens + anti-bloat.

## The 2 changes (both sharpen a channel already parsed → NO new source → NO new firewall surface)

### 1. Teammate-message `_NOISE` anchor (the agent-coordination prose wrapper)

`_NOISE` (L60-64) catches the bare `<teammate-message` tag, but NOT the **`Another Claude session sent a
message:` prose wrapper** that agent-to-agent coordination turns carry (the prose PRECEDES the
`<teammate-message` tag, so the bare-tag arm never fires — the `^` anchors on the prose). Measured: **~49-55
such turns ≈ 7% of real human turns leak through `_NOISE` and are ingested as human feedback** — and they all
carry `scope_hint="user"` (predominantly the `preference` class, ~9 `correction`), so **all of them feed
user-global facts**, not 2 (gate-1 corrected the discovery's narrower "2 correction" figure). This is agent
coordination, not human intent — exactly what `_NOISE` exists to drop.

**Change:** add `Another Claude session sent a message:` to the `_NOISE` alternation (one anchor). It runs in the
human branch's existing noise gate (L314); removes false rows, adds no source. `_NOISE` is `^\s*(…)` matched via
`.match()`, and the wrapper sits at the start of those turns, so the anchored alternative fires correctly.

### 2. Error-text normalization → dedup to an error CLASS

The error channel dedups by EXACT text (`_dedup` on `it["text"]`, L328-333); errors are stored verbatim
(`tn[:200]`, L301) then capped at `MAX_ERRORS=8` (v0.1.49). Byte-noise (`Exit code N`, line numbers, PIDs,
timestamps, paths, hex) **fragments ONE error class into many rows**, so the 8-cap surfaces near-duplicates and
dilutes the env-gotcha signal.

**Change:** dedup errors by a normalized CLASS key, keeping the first occurrence's verbatim text for display:
- Add `_error_key(text)`. Two steps, deliberately CONSERVATIVE to avoid over-merge:
  1. **Head-extraction (does the heavy lifting):** if a `\b\w+(?:Error|Exception|Warning):\s*…` head is present,
     key from the head onward — this drops the `Exit code 1 Traceback … File "/…", line N` preamble + frames
     (incl. their paths/line-numbers) so two runs of the same exception with different temp paths/line numbers
     collapse, while **preserving the message** (`No module named 'foo'` ≠ `'bar'`; `ModuleNotFoundError` ≠
     `PermissionError`).
  2. **Light byte-noise normalization** on the result: `(?i)exit code \d+`→`exit code N`, `(?i)line \d+`→`line N`,
     `0x[0-9a-f]+`→`HEX`, ISO / `hh:mm:ss` timestamps→`TS`. Then collapse whitespace + cap (~160).
- **GAP-2 — NO path→/PATH normalization and NO blanket `\d{3,}`→N** (both rejected by gate-1 as over-merge
  hazards): a greedy `/PATH` arm would merge `…/foocli: command not found` with `…/barcli` (the binary name is the
  signal), and a blanket int-strip would merge `HTTP 404` with `500`. Head-extraction already handles the
  traceback-path fragmentation, so path-stripping is both risky AND redundant — dropped.
- Parameterize `_dedup(items, key=…)` with `key=lambda it: it["text"]` as the DEFAULT (human dedup behavior
  UNCHANGED); dedup errors with `key=lambda it: _error_key(it["text"])` BEFORE the `[:MAX_ERRORS]` cap (L335).

Result: the 8 cap slots hold up to 8 DISTINCT error classes, not 8 fragments of one. **Normalization ONLY** — the
cross-session recurrence MULTIPLIER ("seen across ≥2 dreams") is the deferred D1 (a contract-touching cross-dream
tally; its own cycle).

## Deferred here (NOT built this cycle)

- **Exact-form-literal +1 salience nudge in `_classify`** (the discovery's 3rd build-now, flagged "WEAKEST —
  decide at spec"). **DEFER:** the measured benefit is modest (the ~111 literal-bearing turns are inflated by
  boilerplate that `_NOISE`/`_SKILL_PROMPT` already drop); it is a salience HEURISTIC with false-positive risk
  (a turn merely mentioning a `--flag` isn't necessarily memory-worthy); and it rarely changes survival
  (`max_n` default 30 rarely binds). Anti-bloat + measure-the-need: ship the 2 clean wins; revisit the nudge only
  with measured evidence that literal-bearing turns are under-surfaced. (The skeptic lens recommended exactly
  these two.)
- **D1 the recurrence family** + **D4 the `/distill` vertical** — the discovery's defer bucket; separate cycles.

## Contract impact → PATCH

Both changes are PRECISION improvements to EXISTING channels: signal schema unchanged (the v0.1.48 canonical
keyset is untouched), no new source, no new firewall surface, no removed/renamed key/script/flag. `_dedup`'s
default key preserves human-dedup behavior exactly. Backward-compatible ⇒ **PATCH** (v0.1.49 → v0.1.50).

## The pin — smoke tests (drive `extract()` over fixtures; reuse the v0.1.43/48/49 pattern)

- **Change 1:** a fixture human turn prefixed `Another Claude session sent a message: …` → asserted ABSENT from
  `signals` (counted noise), while a normal human turn in the same fixture survives.
- **Change 2 (the recall guard needs real teeth — GAP-1/GAP-2):**
  - **Merge:** ≥2 error tool-results of the SAME exception+message differing only in byte-noise (`Exit code 1
    Traceback … File "/a/b.py", line 5 … ModuleNotFoundError: No module named 'foo'` vs `Exit code 2 … line 99
    … 'foo'`) → COLLAPSE to ONE row.
  - **Different family (weak guard):** `ModuleNotFoundError: …` vs `PermissionError: …` → SEPARATE.
  - **Same family, different identifier (the STRONG guard — passes only if the message is preserved, GAP-1):**
    `No module named 'foo'` vs `No module named 'bar'` → MUST stay SEPARATE (a type-only key would wrongly merge
    these — this is the fixture that actually enforces the L41 promise).
  - **No-head over-merge guard (GAP-2):** `…/foocli: command not found` vs `…/barcli: command not found` → MUST
    stay SEPARATE (proves no greedy path-strip ate the binary name).
  - **Regression:** `_dedup` default-key behavior on human signals unchanged.

## Out of scope

No new source (the discovery killed all new-source candidates). No `_classify`/marker change (the literal nudge
is deferred). No cross-session state (D1). No change to the firewall, the `MAX_ERRORS` cap, or `_signal`.

## Gates + test plan

- **spec-review (gate-1):** both changes measured-real + zero-new-surface? `_error_key` collapses byte-noise but
  preserves distinct families (no over-merge)? Deferring #3 sound? `_dedup` parameterization preserves human behavior?
- **`/code-review` (gate-2):** the `_NOISE` anchor matches the wrapper; `_error_key` regexes correct + don't
  over-merge; `_dedup` key-fn preserves human dedup; firewall/order untouched; smoke pins have teeth.
- `python3 tests/smoke.py` green + `mypy` + `sim` + `claude plugin validate --strict` + dream-beta-test 0 FAIL.
