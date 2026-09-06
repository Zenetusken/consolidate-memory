# Defect sweep — design-of-record

**Status: amend-2 folded (review-to-zero) → implementation.**
Target release: **v0.4.21 (patch)** — six measured defects from the 2026-09-06 dream session,
each root-caused at its source with a discriminating pin.

## §1 The six defects (each root-caused)

**D1 — the marker was stamped with a literal placeholder, and the read silently fell back.**
Two consecutive dreams ran the SKILL's Phase-5 command with the literal `<HEAD>` placeholder
(`--stamp-marker HEAD`). `stamp_project_marker` (memory_status.py:1984-1985) writes
`out["commit"] = str(commit)` with NO validation or resolution — the literal string "HEAD"
landed in `.consolidation-state.json` (verified: the file carried `"commit": "HEAD"`). The next
read's `_valid_sha` guard (memory_status.py:2735-2736) silently clears any non-SHA commit, so
the marker read as ABSENT — the 20-commit "first consolidation" lookback, the dream-timing
advisory gone, and every script-owned key the reader derives from the marker mis-scoped. The
marker was never deleted; it was stamped invalid and ignored silently. Fixes (amend-2 reworked —
the refusal shape is load-bearing): (a) the stamp RESOLVES its argument with
`git rev-parse --verify <arg>^{commit}` (bare `rev-parse` echoes any 40-hex WITHOUT an
object-DB lookup — the dead-SHA door; `--verify …^{commit}` checks), and the outcome branches:
a valid SHA passes through · a resolvable ref/HEAD resolves to the full SHA · **"not a git work
tree" (`rev-parse --is-inside-work-tree` ≠ "true") or "unborn HEAD" stamps `commit: ""` +
timestamp** (honest: the read already treats `""` as first-consolidation, and the persist gate
is TIMESTAMP-only — the stamp is the sole file-mint and a refusal there would exit-5 every
no-git dream forever) · **refusal (ok:false, file bytes unchanged) is reserved for git repos
WITH commits where the arg doesn't resolve**; the resolution runs with `cwd = project_dir`
(the dispatch's positional — the read path's own convention), NEVER the resolved store dir
(which can sit inside an unrelated repo), and the resolved output must fullmatch 40-hex before
writing (argv-injection belt-and-braces on the write path); the mint gate (`not commit` at
memory_status.py:1981) becomes `commit is None` so `""` can mint while snooze/justify-only
callers keep the refusal; (b) the read path warns on stderr ONLY when it silently clears a
NON-EMPTY invalid marker commit (`""` stays silent) — "marker.commit is not a valid SHA —
treating as first consolidation"; (c) BOTH `<HEAD>` surfaces are fixed: the SKILL's step-5 text
AND render_dashboard's exit-5 re-stamp hint (:1328-1330) name the resolved-SHA form. Pins:
stamp "HEAD" in a git-less temp dir → ok:true, file minted with `commit: ""` + timestamp;
a junk arg in a commit-ful repo → ok:false AND file bytes unchanged; a dead 40-hex arg in a
commit-ful repo → ok:false (the hex door closed); a valid SHA passes through unchanged; a
non-empty invalid committed marker → the stderr warning + the -20 fallback, `""` → silent;
the exit-5 hint pin (an unstamped-persist fixture asserts the stderr names the SHA form, never
`<HEAD>`); and `reconcile_marker`'s commit fill gains the SAME `_valid_sha` gate (timestamp fills
unconditionally) — it is a second unguarded reader of the state file (memory_status.py:2000-2018,
called from the persist path) that would copy a defect-era garbage commit into the record
marker, the archive, and the persist dedup key.

**D2 — the demotion verdict contradicted the scripted block.** The rendered dashboard showed
the script-seeded "12 probative usage window(s) accrued" directly above the model's verdict
"dormant — 0 probative windows" — an authored number contradicting script truth. The SKILL's
verdict instruction says "ONE sentence" but never binds its numbers to the scripted fields.
Fix: the SKILL's demotion-verdict instruction states the verdict MUST quote the block's own
fields ("dormant — observed N · eligible M", from `windows_observed`/`eligible`, never a
hand-invented count) — AND the source-level guard (amend-2 A7 + R2): `validate_cycle_record` warns on THREE
patterns — the measured `(\d+)\s+probative` ≠ `windows_observed`, AND the mandate's own digits:
`observed\s+(\d+)` must equal `windows_observed`, `eligible\s+(\d+)` must equal `eligible`
(each warn-only, silent when the phrase is absent — the mandate makes the check possible and
the check enforces the mandate). Known false-warn ceiling, accepted: a verdict quoting the
gate's "≥3 probative zero-read windows" threshold over a different `windows_observed` warns —
non-blocking stderr. Pins: the SKILL-text assertion AND the validator warnings on "0 probative"
over 12, on a mandate-format contradiction ("observed 5 · eligible 0" over 12/0) + silence on a
matching mandate-format verdict.

**D3 — the SKILL's command templates glue arguments into the quoted script path.** The shipped
Phase-0 blocks render `"${CLAUDE_PLUGIN_ROOT}/scripts/preflight.py ."` as ONE quoted token;
copying verbatim fails with `can't open file '…preflight.py .'` (measured, two releases shipped
it). Fix: split the arguments outside the quotes in every affected command line (amend-2 A4: the
class is 24 SITES — 23 bash-fenced lines whose quotes never close after `.py`, plus the prose
code span at SKILL.md:361, the measured `preflight.py ."` exemplar). The pin is DOCUMENT-WIDE
with NO fence parsing (a fence scope cannot see the prose span, and indented fences defeat
naive parsers): every `${CLAUDE_PLUGIN_ROOT}/scripts/<name>.py` occurrence must be immediately
followed by `"` — simulated: 24 hits on today's text, 0 after the mechanical close, 0 false
positives (the correct-convention exemplar exercises the OK form).

**D4 — beat reuse (the novelty ceiling, exercised).** The surfacing line and the distill
verdict were verbatim-reused across two passes; the v0.4.19 conversation-truth gates check
PRESENCE, not novelty — a documented ceiling (dream-narration-teeth.spec.md §5). Fix:
authorship discipline — no code change; the ceiling stays documented. The spec records the
disposition so the reviewer can't re-litigate it.

**D5 — the distill scan's `scanned` block lacks the counts, and the record's numbers
contradicted the model's verdict.** Root-caused by inversion: the scan JSON's `scanned` block
carries `commands`/`sessions` but NOT `n_recurring`/`n_chains`; the true counts live only as the
LENGTHS of the top-level `recurring`/`chains` lists (capped at `_DISTILL_CAPS` 40/20 — so past
the cap even the lengths undercount). The injection (distill_scan.py:456) writes the capped
lengths, so the RECORD and the dashboard carried the real 40/20 while the model — reading the
wrong field — authored "nothing: 0 recurring · 0 chains". The dashboard was right; the verdict
was wrong. Fixes (amend-2 A5/A8): (a) the scan emits the TRUE filtered pre-cap counts into
`scanned.n_recurring`/`scanned.n_chains` (counted AFTER the MIN_RECUR filter, BEFORE the
`[:MAX_*_OUT]` slice — the cap is an OUTPUT cap, never a count); (b) `inject_into` uses those
true counts with the defensive `.get` fallback to the capped list length for stale scans; (c)
the SKILL's distill step names the exact fields to read (the `scanned` block counts, never the
capped list lengths) AND the SKILL's own "nothing: 0 recurring · 0 chains" empty-set-rule
sentence is reworded to read from the scanned counts; (d) the `_report` header's scale line
shows the TRUE counts ("N template(s) · M chain(s)" from scanned, not the capped lengths);
(e) the validator's "impossible count" backstop — validate_cycle_record warns on
`n_recurring > 40` — is DROPPED in the same patch (the true count legitimately exceeds the
output cap; the hand-mirror class the backstop guarded died with the injection); (f) pins: a
scan fixture with > cap recurring templates AND > cap chains (both counts at ≥ MIN_RECUR) →
`scanned.n_recurring`/`scanned.n_chains` exact, the injected record's counts exact, and the
validator SILENT on the over-cap counts; a SKILL-text pin on the reworded empty-set sentence
naming `scanned.n_recurring`/`scanned.n_chains` (the D2 text-pin precedent).

**D6 — the suite has no count floor.** The v0.4.20 implementation cycle measured the class (a
second top-level print/exit orphaned 31 checks while the suite printed green) and recorded the
lesson but no pin. Fix (amend-2 A6): an EXACT-equality smoke assertion on the final count —
`passed + failed == 1729` with a bump-me-on-growth comment (verified env-stable on both trees;
an orphaned section flips it, and a legitimate growth forces the author to touch the pin —
the tighter contract beats a silently-satisfiable floor).

## Amend ledger

- **amend-4 (round-5, 2026-09-06):** the F2 fold's CODE half — `_DISTILL_CAPS` deleted (the smoke
  pin's deletion had landed alone), the four dangling cross-refs reworded, the TypedDict count
  comments now name `scanned.n_recurring`/`scanned.n_chains`. No behavior change; doc-truth
  hygiene. Also folded: the per-PR findings 1–4 (the SKILL's two `<HEAD>` cues rewritten + the
  D1(c) SKILL pin legs, the read-path warning fixture, the D2 SKILL-text pin, the hex-branch
  work-tree-first order).
- **amend-3 (final sweep, 2026-09-06):** R1–R5 fold-completeness gaps closed. R1 the D3 pin is
  DOCUMENT-WIDE (no fence parsing — the prose span at :361 is out of any fence) with the explicit
  next-char rule (`.py` must be immediately followed by `"`), simulated 24→0→0. R2 the validator
  adds the MANDATE patterns (observed/eligible digits) beside the probative one, with the
  accepted threshold false-warn ceiling. R3 the exit-5-hint pin + the `reconcile_marker`
  `_valid_sha` commit-fill gate (the second unguarded reader). R4 the resolution cwd clause
  (project_dir, never the store dir) + the 40-hex fullmatch belt. R5 the D5 pin covers
  n_chains too (both counts at ≥ MIN_RECUR past their caps) + the D5(c) SKILL-text pin.
- **amend-2 (adversarial review-to-zero, 2026-09-06):** NOT clean — 8 required amendments.
  A1 the unconditional refusal deadlocks no-git/unborn-HEAD dreams (the persist gate is
  TIMESTAMP-only and the stamp is the sole file-mint — refusal there exits 5 forever); folded —
  no-git/unborn stamp `commit: ""` + timestamp, refusal reserved for commit-ful repos, the
  mint gate becomes `commit is None`. A2 bare `rev-parse` never verifies a 40-hex arg (measured:
  it echoes any hex without an object-DB lookup — the dead-SHA door); folded —
  `--verify <arg>^{commit}`. A3 a second `<HEAD>` cue lives in render_dashboard.py:1328-1330
  (the exit-5 re-stamp hint) — folded into D1(c). A4 D3 is 24 sites with two INDENTED fences
  defeating naive parsing; the pin must FAIL on today's text — folded. A5 the true counts trip
  the validator's "impossible > cap" backstop — dropped in the same patch. A6 the floor must be
  EXACT-equality (env-stable 1729) with the bump discipline — folded. A7 D2 needs the
  source-level verdict-digit check (validate_cycle_record warns when the verdict's probative
  count contradicts `windows_observed`) — folded. A8 the SKILL's own "0 recurring · 0 chains"
  sentence + the `_report` scale line ride D5's fix — folded.
- **amend-1 (advisor pass, 2026-09-06 — inline, the advisor agent died on an account-balance
  error mid-pass; its partial finding salvaged):** (a) the D3 pin is FENCE-AWARE — fenced
  command blocks span lines, a flat per-line scan misreads them (the advisor's last finding);
  (b) verified: smoke has NO existing stamp pins — the v0.4.1 fixtures hand-write the state
  file, so D1's hardening breaks nothing and gains its own pins; (c) the no-git stamp-refusal
  is CONSISTENT with reality — a no-git store never had a working marker commit (the read
  silently cleared any string), so refusing an unresolvable commit names the truth instead of
  hiding it; (d) D5's true counts ARE available at the slice site (distill_scan.py:386-392 —
  the full sorted list exists before `[:MAX_RECUR_OUT]`), and `inject_into`'s defensive `.get`
  fallback to the capped list length preserves stale-scan back-compat.

## §2 Ship shape

Feature branch → per-PR review → user merges → `release.sh` pre-bump (CHANGELOG [0.4.21]
first, plugin.json 0.4.20→0.4.21, the complete sweep) → `--expect patch --finalize`.
Backward-compatible: stamp hardening (behavioral fix on a defect path), a scan-output
enrichment (additive keys), SKILL text, a render-side stderr warning, two pins. No
record-schema change, no exit-key change.

## Evidence ledger

Every citation is measured: the state file was read and carried `"commit": "HEAD"` verbatim;
stamp_project_marker's unvalidated `str(commit)` is at memory_status.py:1984-1985 and the
silent `_valid_sha` clear at :2735-2736; the dashboard render of the contradicting demotion
lines is in the persisted dream (#sel=49); the failed `'…preflight.py .'` invocation is in the
session; both scan files were inspected (top-level `recurring` 40 entries with real counts,
`scanned` without `n_recurring`); distill_scan.py:456 injects `len(d.get("recurring"))`; the
logged record carries `n_recurring: 40` beside the "0 recurring" verdict.
