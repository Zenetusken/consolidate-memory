# Unverifiable-carrier — design-of-record

**Status: review-to-zero CLEAN (amend-2 verified) → implementation.**
Target release: **v0.4.22 (patch)** — one measured defect from the 2026-09-06 dream
session, root-caused at its source with a discriminating pin per layer.

## §1 The defect (root-caused, four layers)

**U1 — the dashboard alerts "⚠ 1 unverifiable" and cannot say what.** The dream's
persisted record carries `verification.unverifiable: 1` and the rendered dashboards
(ASCII + HTML) flag it in yellow — but NO surface names the claim, so the alert is a
loud pointer at nothing. The user reported it from the rendered HTML archive; the
investigation traced four layers, each real:

1. **Contract gap (the source).** SKILL.md Phase 3 (SKILL.md:672-677) says
   "unverifiable (drop, or keep only if explicitly marked unverified and the user
   wants it)" and "tally `verification.confirmed` / `corrected` / `unverifiable`" —
   but the entries[] action vocabulary (`added|corrected|deleted|reconciled|skipped`)
   has NO unverifiable carrier, there is no canonical marker token, and nothing binds
   the tally to named rows. A count with no named carrier is permitted by the contract.
2. **Record gap (this pass).** The persisted log line has
   `verification.unverifiable: 1` and NONE of its 9 entries names an unverifiable claim —
   the `archive-exposure-audits` disposition (the fan-out's B9 judgment: "unverifiable
   as preference, corroborated as code-effect") was never recorded. The omission was
   permitted by layer 1.
3. **Renderer gap (the user's complaint).** Both dashboards render the count only:
   ASCII `VERIFIED` line appends `⚠ 1 unverifiable` (render_dashboard.py:549-553, the
   `_unv` bit) — no name surface; HTML `assess()` pushes `v.unverifiable+' unverifiable
   claim(s)'` as a warn item (dashboard.sections.js:269) and the summary KPI's sub-label
   shows the bare count (dashboard.template.html:1096). Neither can render a name the
   record doesn't carry.
4. **Validator gap.** `validate_cycle_record` (memory_status.py:3283) checks the
   demotion verdict's digits against the scripted block (the v0.4.21 D2 three-pattern
   precedent at :3340-3362) but has no check for this count.

**The class (third occurrence).** The roadmap's `verdict-vs-script-truth` lesson names
it: a count rendered loudly with no named carrier. D2 bound the demotion verdict's
digits to the block's fields; D5 bound the distill verdict's counts to `scanned`; this
is the same family on the verification tally. The fix pattern the sweep already built
is the fix here: **the SKILL mandates the binding, the validator warns when the binding
is missing** (warn-only — a validator can never check semantic truth, only the binding).

## §2 The fix (patch-shaped — no new record keys)

**F1 — the canonical carrier (SKILL.md Phase 3).** The mandate is **bidirectional**
(advisor A3 — the reverse-mismatch warn rests on it): every claim you JUDGE
unverifiable is tallied in `verification.unverifiable`, AND every tallied claim gets
ONE entries[] row — action `skipped` (the claim was dropped) or `reconciled` (kept with
explicit user approval, per "only if explicitly marked unverified and the user wants
it") — whose `name` names the claim (the field the renderers join) and whose `reason`
begins the canonical token `unverifiable:` followed by a non-empty why, e.g.
`"unverifiable: user-behavior preference — corroborated code-effect leg only
(archive-exposure-audits)"`. Dropped claims ARE tallied (a drop is a verified outcome,
not a non-outcome). The token mirrors the `extractor-skip:` precedent (SKILL.md:587,
matched mechanically by the EXT gate at :1214 — a canonical token, never free-form
prose). The tally equals the marked-row count: one row per claim, one claim per row.

**F2 — the validator binding (memory_status.py).** In `validate_cycle_record`, beside
the demotion patterns: when `verification.unverifiable` is a present int > 0, warn
unless the marked-row count (entries whose reason begins `unverifiable:`) equals the
tally — and warn on the reverse mismatch too (marked rows without a tally, or a count
mismatch in either direction — the D2 contradiction pattern, warn-only stderr, never
blocks). Silent when the tally is absent/zero with no marked rows (pre-fix and legacy
records stay quiet on the absent side — the warn fires only on a present count or a
stray token). **Type-guarded (advisor A2 + review S1 — the never-raises contract,
memory_status.py:3287-3289):** the match is `isinstance(reason, str) and
reason.startswith("unverifiable:")` and the tally compare runs only when
`isinstance(unverifiable, int)` — junk scalars skip the binding check, the D2
isinstance-guard style (:3338/:3346/:3357) — AND the scan reuses the existing
container guards first (entries must be `isinstance(entries, list)` with per-item
`isinstance(e, dict)` — the :3310-3316 pattern; both bad shapes arrive in the wild,
per the validator's own messages at :3311 and :3313-3316). A None reason, a string
tally, a non-list entries, or a non-dict item degrades as today, never raises (the
validator runs at the top of the persist path, render_dashboard.py:1276-1277,
unguarded). The JS side mirrors it: `e.reason && String(e.reason).indexOf("unverifiable:")===0`
(a pageerror would fail the browser harness's render-without-errors check). **Legacy
acceptance (advisor A4):** records persisted before the mandate with a present count
warn on direct single-record re-render (unfixable by design — they are evidence, never
retro-edited); the archive path never re-validates (the validator's only callers are
render_dashboard.main() and tests — advisor A7, verified), so the archive never
mass-warns.

**F3 — the renderers name the claims at the ⚠.** The label format is **pinned**
(advisor A6): append ` — <names>` AFTER the existing count phrase, identically in all
three surfaces — the browser check dashboard_browser.py:181 asserts the substring
"1 unverifiable claim", so the count phrase must survive verbatim. ASCII: the
`VERIFIED` ⚠ bit appends the marked rows' `name` values — `⚠ 1 unverifiable —
archive-exposure-audits` — capped at 3 names + `+N more` (the cap-with-counter
pattern), falling back to the bare count when no marked rows exist (legacy records
render unchanged). Implementation note (advisor A5): `entries` is currently first
extracted at render_dashboard.py:597, AFTER the VERIFIED block (:547-554) — hoist the
extraction above it (`_lget(record, "entries")` is in scope); the `_ui.wrap` value
column wraps on word boundaries so a 3-name join fits at realistic name lengths, and
each name goes through `_clean`. HTML: both surfaces — `sections.js:269`'s assess warn
item gains the same joined names, and `template.html:1096`'s KPI sub-label gains them
(the same join, the same fallback). **The KPI sub-label join escapes (review S4):**
`kpi(n,k,d,cls)` escapes the key but injects the sub-label `d` raw — model-authored
names carry angle-bracket content (the render-chain audit's `"<proj>"` pin documents
it) — so each joined name goes through `esc()` before the KPI; the assess path is
already safe (evidenceButton → esc()). **Never pair the count with the word "dropped"**
(advisor A8): smoke.py:9799 pins that the template never labels unverifiable as
dropped — the label says what it is ("unverifiable"), not the disposition. **The A5
optional demo-token-row is DROPPED (review C2):** smoke.py:1063 pins `"—" not in
_demo` (the no-stray-em-dash pin) and the join's em-dash would fail it — the demo keeps
the honest bare-count fallback; the pins, not the demo, own the fixed shape.

**F4 — the pins (each discriminating on pre-fix code).**
- **The fixture fix rides F4 (advisor A1 — the blocker the validator change would
  create):** `tests/dashboard_fixture.py:89/93` gives the fixture's record
  `verification.unverifiable: 1` beside a `skipped` row ("cache-expiry-claim") whose
  reason lacks the token, and `dashboard_fixture.py:196-199` asserts
  `not ms.validate_cycle_record(cycle)` over all 8 history cycles —
  `dashboard_browser.py:32` runs `sample()` at startup, so F2's warn would raise
  AssertionError before the HTML pin ever renders. The fix: prefix that fixture row's
  reason with `unverifiable:` (it is already the canonical shape — tally 1, one
  skipped row) — and the fixture then doubles as the natural vehicle for the ASCII/HTML
  name pins.
- Validator pins (smoke, the v0.4.21 D2 pin style): a record with
  `verification.unverifiable: 1` and no marked entries → the new warning appears on
  stderr; the same record + one `unverifiable:` row → silent; a mismatch pair (2 marked
  rows, tally 1) → warns; **the stray-token arm (review S2)** — a record with the tally
  absent/zero but one marked row → warns (the reverse-mismatch direction gets its own
  pin, so an implementation gating the block on `unverifiable > 0` can't drop it);
  **the container guards (review S1)** — a non-list `entries` and a non-dict entry
  item must NOT raise (the never-raises contract).
- ASCII renderer pin (review C1 — the name-substring form was VACUOUS: pre-fix output
  already carries every entry's name in the CHANGES ledger at render_dashboard.py:607):
  the discriminating assertion is line-scoped to the VERIFIED block and asserts the
  contiguous joined form `— cache-expiry-claim` on the ⚠ line — pre-fix, that line
  renders the count alone.
- HTML browser pin (dashboard_browser.py, the archive harness): the assess warn item
  in `#dream-summary` for the same fixture record carries the name (the summary
  composition contains no entry names pre-fix — verified statically); pre-fix carries
  the bare "1 unverifiable claim" — and the existing :181 substring pin stays green
  (the count phrase survives verbatim).
- SKILL-text pin (review S3): TWO load-bearing fragments, one per direction — the
  tally-direction phrase AND `one entries[] row whose reason begins` + the
  `unverifiable:` token (a trivial reword of one half can't keep the pin green).
- The legacy-fallback pin (review S5): a legacy-shaped record (present count, no
  marked rows) renders the bare count through BOTH renderers — no names, no join —
  the byte-identical-legacy property has its own pin.
- The D6 exact-count bump: the suite's `passed + failed + 1 == 1740` constant moves
  with the new checks (an orphaned section can never print green).

**Out of scope (stated so the reviewer can't re-litigate):** `confirmed`/`corrected`
tallies get no carrier mandate — no warn fires on them, so the alert-carrier asymmetry
is the scope boundary; legacy records (pre-fix, like this dream's own log line) are not
retro-edited — the record IS the spec's evidence; no schema/TypedDict change, no
exit-key change, no beta-oracle family (the validator pins cover the class in smoke;
a beta family would re-test a warn the smoke already pins — not additive).

## §3 Ship shape

Feature branch → per-PR review → user merges → `release.sh` pre-bump (CHANGELOG
[0.4.22] first, plugin.json 0.4.21→0.4.22, the complete version sweep) →
`--expect patch --finalize`. Backward-compatible: an additive validator warning, a
renderer label enrichment with the legacy fallback, SKILL text. No record-schema
change, no exit-key change — patch under the versioning policy.

## Evidence ledger

Every citation is measured: the persisted log line (the hashed ops store
`~/.claude/plugins/data/consolidate-memory/ops/<project-id>/.consolidation-log.jsonl` —
the project-id from `cm doctor` — line 17 of 17) carries `verification: {confirmed: 24,
corrected: 2, unverifiable: 1}` with entries `[corrected×4, reconciled×4, skipped×1]` —
zero `unverifiable:` rows (the record gap; the skipped row is the unrelated
"CLAUDE.md TYPED-contract paragraph" entry — advisor A9). The project's native log has
two more pre-fix lines with present counts (lines 13-14, unverifiable 2 and 1, zero
token rows) — the legacy-re-render warn exposure the F2 acceptance names (advisor A4).
The fan-out's B9 verdict is the claim's identity ("unverifiable as preference,
corroborated as code-effect" on `archive-exposure-audits` — the same stem appears in
earlier log lines 7 and 9, consistent provenance); render_dashboard.py:549-553 renders
the ⚠ bit from `_unv` alone; dashboard.sections.js:269 pushes the bare count;
dashboard.template.html:1096 shows the bare count in the KPI sub-label; SKILL.md:672-677
is the tally mandate with no carrier; the D2 precedent lives at
memory_status.py:3340-3362; the `extractor-skip:` token precedent at SKILL.md:587 +
:1214. Verified-OK (advisor A7/A8): the validator's only callers are
render_dashboard.main() + tests, so the archive never mass-warns; render_log.py
renders no tally (token rows surface as `skipped` in its entries column — no change);
no third ⚠ renderer exists.

## Amend ledger

- **amend-3 (per-PR review, PR #213, 2026-09-06):** 1 confirmed + 2 suspected folded.
  P1 the stray-token arm now fires on an ABSENT tally too (the `elif _unv22 is None`
  arm — a marked row with no verification block/unverifiable key warns; a junk
  non-int scalar stays silent per the guard contract) + the absent-half pin (D6 →
  1740+9). P2 the HTML-side legacy-fallback pin now exists — the browser harness
  renders a token-stripped copy of the fixture record via `fixture()` and asserts the
  bare label (no names in #dream-summary). P3 the ASCII pin is now line-scoped to the
  VERIFIED block (the C1 mandate; the whole-render form was discriminating in practice
  but carried the fragility C1's scoping exists to remove). The reviewer verified the
  core mechanically: F1/F2/F3/F4 all conform, all 8 original pins fail pre-fix, the
  fixture's 8 cycles carry exactly tally-1/1-row, and the version sweep is complete
  with the historical tags untouched.
- **amend-2 (adversarial review-to-zero, 2026-09-06):** NOT clean — 2 confirmed + 5
  suspected, all folded. C1 the F4 ASCII name pin was VACUOUS (pre-fix output carries
  every entry name in the CHANGES ledger, render_dashboard.py:607) — the assertion is
  now line-scoped to the VERIFIED ⚠ line on the contiguous joined form
  `— cache-expiry-claim`. C2 the A5 optional demo-token-row is DROPPED — the join's
  em-dash fails smoke.py:1063's `"—" not in _demo` pin; the demo keeps the honest
  bare-count fallback. S1 the F2 scan reuses the container guards (list + per-item
  dict — the :3310-3316 pattern; both bad shapes arrive in the wild) and pins them.
  S2 the stray-token arm gets its own pin (a tally-absent record with a marked row
  warns — no implementation can gate the block on `unverifiable > 0` and stay green).
  S3 the SKILL-text pin prescribes TWO load-bearing fragments (one per mandate
  direction) + the token. S4 the KPI sub-label join escapes each name (the `kpi()` raw
  `d` slot; the render-chain audit documents angle-bracket content in model-authored
  names; the assess path is already esc'd). S5 the legacy-fallback pin renders a
  legacy-shaped record through BOTH renderers (bare count, no join). The evidence
  ledger itself verified 100% clean (every citation re-read against live code).
- **amend-1 (advisor pass, 2026-09-06):** 9 findings folded. A1 the F2 warn would break
  `dashboard_fixture.sample()`'s validate-assert over all 8 history cycles (the
  dashboard_browser harness runs it at startup) — the fixture's skipped row gains the
  token prefix and doubles as the name-pin vehicle. A2 the validator's first
  scalar/sub-field reads must be isinstance-guarded (the never-raises contract, :3287-
  3289; the D2 guard style) — junk reason/tally degrades, never raises; JS mirrors with
  `e.reason && String(e.reason).indexOf("unverifiable:")===0`. A3 the mandate is now
  bidirectional (judged → tallied AND tallied → one row; dropped claims ARE tallied) —
  the reverse-mismatch warn's credibility rests on it. A4 legacy acceptance sentence
  added (pre-fix present-count records warn on direct re-render; the archive never
  re-validates — caller inventory verified). A5 ASCII hoist note (entries extraction
  precedes the VERIFIED block) + the optional `_demo_record()` token row. A6 the label
  format is pinned to append ` — <names>` after the surviving count phrase (the
  :181 substring pin). A7 verified the validator runs only in render_dashboard.main()
  + tests — no archive mass-warn. A8 the label must never pair the count with "dropped"
  (smoke.py:9799 pins the template's non-dropped phrasing) + no third renderer surface
  exists (render_log.py has no tally; calibration aggregation legitimately drops
  names). A9 the evidence ledger names the exact hashed-ops path. (A5's optional
  demo-token-row was superseded by amend-2 C2 — dropped; the hoist note survives.)
