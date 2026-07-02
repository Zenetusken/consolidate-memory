# Distill — clean signal, chain structure, captured verdict (v0.1.55)

**Status:** draft → spec-review (design+prose lens, impl lens) → implement.
**Scope:** arc 2 of the 2026-07-01 directive ("The distill does nothing or is poorly
implemented"). LOCAL detection quality + capture + instruction only — the cross-project
tier and the persisted cross-dream tally stay DEFERRED per the standing plan; the
report-then-apply / never-auto-writes safety is untouched and out of scope for change.

## 1 · Problem (measured, 2026-07-02, on this repo's live corpus)

User verdict: *"The distill does nothing or is poorly implemented."* Measurement of the
shipped v0.1.51 scanner against the richest available corpus (this repo: 1 session file,
1,491 Bash commands over ~9 active days):

| Evidence | Number |
|---|---|
| Top template is the noise verb `echo` | ×636 — **43% of the corpus in one garbage row, ranked #1** |
| Second noise class `python3 -` (heredoc one-offs — 93 *distinct* scripts in one false class) | ×93 |
| The real gate-check `python3 tests/smoke.py` under first-segment-only templating | ×60 |
| The same command under all-segment templating (prototype) | **×234 — a 4× undercount** |
| Sessions seen (`scanned.sessions`) | 1 — `count≥2` gates nothing at this scale |
| Cycle-record `distill` field / dashboard line / archive trace | **none exist** |

The user's phrasing is exact: they cannot distinguish "ran and correctly proposed
nothing" from "never ran," because a distill outcome leaves **zero persistent trace**.

## 2 · Root causes

- **D1 — first-segment-only templating.** `_template()` returns the FIRST non-cd segment
  of a compound command. This user's dominant idiom is `echo "=== label ===" && <real
  command>` — so 43% of commands template to `echo`, and the *real* command in each chain
  is **never counted**. The code's own comment assumed "the real workflow recurs
  standalone" — measured false for this corpus.
- **D2 — flat rows, no structure.** Which segments *chain together* inside a compound
  command is discarded at extraction, yet "RECOGNIZE a coherent repeated workflow" is
  exactly what the SKILL asks the model to do. (Scope honesty, design-review m6: chains
  recover the `&&`-glued sub-steps — e.g. the gate-check pipeline — not the multi-call
  release arc, whose steps are separate Bash invocations; that recognition stays with
  the model, now fed by clean co-ranked rows.)
- **D3 — no capture (arc-1's disease).** No `distill` block on the cycle record, no
  dashboard line, no archive entry, no beta family. The SKILL says "fold the distill
  outcome into the debrief" — prose-only, invisible one dream later.
- **D4 — hedge-dominant instruction (arc-1's RC1).** The step primes the null outcome
  twice ("usually proposes nothing"; "'Create nothing' is a valid, EXPECTED outcome") and
  pins no checkable obligation for what a verdict must contain — the same
  rhetorical-balance failure the dream-arc prose gate just killed.
- **D5 — recurrence without episodes.** `count≥2` over a 1,491-command mono-session
  corpus is meaningless; the *episode* dimension (day spread) is discarded even though
  every transcript line carries a timestamp. ×27 across 9 days is a workflow; ×27 in one
  hour is a loop.
- **D6 — prototype-exposed noise classes** (surface only once D1 is fixed, so they are
  part of this spec, found empirically): (a) heredoc **bodies** template as segments
  (`print(f)` ×71, `do`/`done` ×72/62, `PY`, `import sys`); (b) `2>&1` survives
  quote-stripping and the `>`-split as a dangling `2` token (`./release.sh 2`); (c)
  `\`-continuation lines split into bogus segments (`--title \`).

## 3 · Design

### 3.1 Scanner (`distill_scan.py`) — clean all-segment signal + chains + day-spread

Extraction pipeline (order matters — B1 of the design review PROVED the draft order
defeated its own heredoc fix: quote-strip ran first and deleted the quoted tag, so
`<<'PY'` became `<<` and the heredoc matcher found nothing):
1. **Join continuations** (`\`+newline → space) — kills D6c.
2. **Strip heredoc bodies FIRST, on the joined raw text** — match
   `<<-?\s*['"]?TAG['"]?` (dash-heredoc included — design-review m4) and consume from
   the `<<` marker itself through the terminator line (or end-of-command if
   unterminated), leaving a clean head: `python3 - <<'PY' …body… PY` → `python3 -` —
   kills D6a. Consuming the marker is pinned (else a dangling `<<` token survives).
3. **Strip quoted strings** (the existing transform, now safe — tags are gone).
4. **Split into segments** on newline / `&&` / `;` and template **EVERY segment**
   (not just the first) — fixes D1 and the 4× undercount. A template counts **once per
   command** (a `smoke && smoke` retry isn't double recurrence).
5. **Truncate at redirects** — pinned as SPLIT-keep-head (`re.split(r"\s\d?>{1,2}", …)[0]`
   semantics), NOT `re.sub` of the operator (which would leave the target filename as a
   noise token: `cmd >> app.log` → `cmd  app.log` — design-review m1). The `\d?` consumes
   the `2` of `2>&1`, killing D6b.
6. **Keyword handling, two classes (design-review M2, proven):**
   - **PREFIX-STRIP** `do` / `then` — keyword-led segments that CARRY a command
     (`do mypy $f` → re-template the remainder → `mypy`); dropping them whole would
     reintroduce D1 inside every loop body.
   - **DROP-WHOLE** keyword-only / condition segments: `done fi esac else` and
     `for/while/if/case/elif`-headed segments (iterators/conditions, not commands).
7. **Stoplist** (drops a segment whose template head matches): generic verbs
   `echo printf ls pwd which type true sleep date touch mkdir`; investigation verbs
   `grep rg cat head tail wc sed awk find diff`; inline-interpreter false classes
   `python3 -` `python3 -c` `bash -c` `sh -c` (quote-strip collapses their bodies to an
   identical head — a false recurrence class). The stoplist gates what can BE a row;
   stoplisted segments never form rows or chain endpoints.
8. **Day-spread**: each matched line's `str(o.get("timestamp") or "")[:10]` (null-guarded,
   empties skipped) accrues into a per-template `days` set — fixes D5. Rank rows by
   `(len(days), count)` desc. Residual (design-review m3, accepted): a genuine same-day
   high-count workflow ranks low; all rows within the cap are still shown, and the SKILL
   tells the model rank is a hint, not truth.
9. **Chains**: adjacent kept-segment bigrams within one compound command
   (`a → b`, once per command, `a != b`), same day-spread + threshold + ranking, capped
   (`MAX_CHAIN_OUT = 20`). Chains capture the `&&`-glued sub-steps of a workflow — NOT
   the multi-Bash-call arc (branch/commit/push/PR are separate calls no chain links;
   design-review m6): the model recognizes the multi-call arc from co-ranked rows, with
   chains as the intra-step glue. Known residuals (accepted, low-frequency): `||` is not
   a separator (the fallback arm is dropped at the pipe-split); `;`/`&&` inside `$(...)`
   mis-segments.

**Function decomposition (impl-review MAJOR-1):** the shipped `_template(cmd)` (first
non-noise segment of the whole command) is retired. Replacement: a pure per-segment
`_seg_template(seg) -> str | None` (carries over the branch/abs-path/flag genericization
— the existing regression expectations retarget to it) + a command-level
`_scan_cmd(cmd) -> tuple[list[str], list[tuple[str, str]]]` returning (kept templates,
deduped once-per-command; adjacent kept-pair chains). `scan()` consumes `_scan_cmd`.
Day-spread reads `str(o.get("timestamp") or "")[:10]` from the SAME parsed line object
(null-guarded; empty days skipped — impl-review M-3).

JSON contract (additive keys; the SHAPE pins change with them): each `recurring` row
gains `"days": int`; new top-level `"chains": [{"templates": [a, b], "count": n,
"days": d}]`; `scanned` gains `"days": int` (distinct active days seen). The existing
exact-set shape pins (`smoke.py:1461–1462` — top-level keyset + `scanned` keyset) are
UPDATED to the new sets, and the v0.1.51 `_template` test block (`smoke.py:1415–1473`)
is REVISED to target `_seg_template`/`_scan_cmd` (impl-review MAJOR-1). The human
`_report` gains a CHAINS section. `MIN_RECUR`, the 30-day window, and `MAX_RECUR_OUT`
stay as shipped (measured adequate once noise dies); chains capped at `MAX_CHAIN_OUT = 20`.

**Chain semantics, pinned (impl-review MAJOR-2): filter-then-adjacent (bridge).**
Stoplisted segments are removed FIRST; chains are adjacent pairs over the KEPT sequence —
`a && echo ok && b` yields `(a, b)`. Rationale: the stoplisted middle is decoration (this
user's labeled-gate idiom), not a workflow boundary; break-at-noise semantics would
sever most real chains in the measured corpus. (Honesty: the prototype's numbers don't
discriminate bridge-vs-break — this rests on design intent, not the measurement.)

Prototype result on the live corpus (the acceptance shape): top rows
`python3 tests/smoke.py ×234/9d · simulate_accumulation ×126/9d · validate_manifests
×90/9d · gh pr merge ×62/9d · ./release.sh ×47/9d`; top chains `smoke → mypy ×105/7d ·
smoke → sim ×72/7d · mypy → validate_manifests ×40/6d · gh pr merge → git checkout main
×23/7d`. Zero `echo`/heredoc/keyword rows.

### 3.2 Capture — the distill verdict becomes visible (fixes D3)

- **Schema:** `Distill(TypedDict, total=False)` in `memory_status.py` — `sessions: int`,
  `commands: int`, `n_recurring: int`, `n_chains: int` (the `n_` prefix breaks the
  int-vs-list name collision with the scan JSON's `recurring`/`chains` LISTS —
  design-review m2; the fill rule is pinned as `len(scan.recurring)`/`len(scan.chains)`),
  `proposed: list[str]`, `created: list[str]`, `verdict: str` — and `distill: Distill`
  on `CycleRecord` (additive; legacy renders). Cascade per the house contract: SKILL
  schema block + nested smoke-pin tuple (`("distill", …, ms.Distill)`) +
  `validate_cycle_record` (`"distill"` in the must-be-dict tuple;
  `distill.proposed`/`distill.created` must-be-list checks, mirroring `dream.beats`).
- **Lifecycle at persist time (design-review M3):** report-then-apply means user
  confirmation usually arrives AFTER the step-7 `--persist`, so `created` is
  authored-before-persist ONLY (the rare interactive case) and the **`verdict` is the
  terminal carrier, required to encode disposition**: `created <X>` ·
  `proposed <X> — awaiting confirmation` · `proposed <X> — declined` ·
  `nothing: <top candidate> fails <gate leg>`. The record is an honest snapshot at
  persist time; an artifact authored post-confirmation in a later turn is named in the
  debrief (the existing honest-gap rule), not retro-written into the persisted record.
  `verdict` is ONE line, ≤~60 chars for the dashboard cell (the HTML shows it full —
  design-review m7).
- **Dashboard:** ONE gated `_kv("DISTILL", …)` line (presence-gated like DREAM ARC;
  `_dget`/`_lget` idiom; e.g. `14 recurring · 6 chains → proposed 0 · <verdict ≤60>`).
- **HTML archive:** one line in the "This Pass" panel (the audit/verify section), gated
  on `cycle.distill`, `esc()`-guarded.
- **Beta family:** `distill_capture` — LOW/WARN sibling of `dream_arc_capture`, built by
  EXTRACTING the shared scaffold into one helper (impl-review MAJOR-3, the
  reimplementation-pin discipline): `_latest_capture_check(ctx, *, block_key,
  min_version, is_complete, …)` owns the version gate (`_version_tuple` fail-closed),
  the empty-log SKIP, the `log_records[-1]` read, and the `_R` construction; BOTH
  families become thin calls (dream_arc_capture is refactored onto it — behavior pinned
  by the existing five smoke cases). `@family`-registered (impl-review M-1).
  Completeness predicate, pinned: PASS iff `distill.verdict` is a non-empty string (the
  verdict IS the contract's checkable core — a counts-only block without a verdict is a
  skipped judgment); else WARN. **Maintenance/bootstrap carve-out (impl-review M-2, made
  deterministic):** a record with `maintenance.pivoted == true` legitimately skipped the
  distill step (the pivot scopes the pass to pull + health) ⇒ SKIP, not WARN. Pre-feature
  caveat stays in the WARN strings; necessary-not-sufficient; never FAIL.

### 3.3 SKILL step rewrite (fixes D4) — the verdict contract

The five-leg gate **stays exactly as shipped** (it is correct protection; on this repo it
correctly rejects the top candidate — the gate-chain is already tooled by `release.sh`).
What changes is the rhetoric and the obligation:

- **Kill the double-nothing priming.** "usually proposes nothing" and "'Create nothing'
  is a valid, EXPECTED outcome" are deleted. Replacement framing: *"Create nothing" is a
  frequent and honorable VERDICT — but it is a verdict the gate produces, never a default
  you reach for.*
- **The verdict contract (the checkable obligation):** every distill phase MUST end with
  a one-line plain-channel verdict naming (a) the scan scale (`N recurring · M chains`),
  (b) the **top candidate considered** (a template or chain, by name), and (c) the
  outcome — `created <artifact>` / `proposed <artifact>` (await confirmation) / `nothing:
  <top candidate> fails <which gate leg>` (e.g. "nothing: the smoke→mypy→sim gate-chain —
  already covered by release.sh"). A bare "nothing" with no named nearest-miss is
  non-compliant. Chains are named as the workflow-recognition substrate ("a chain IS a
  candidate workflow; read the chains before the rows").
- **The fill rule:** mirror the verdict into `distill` on the cycle record
  (`sessions`/`commands`/`recurring`/`chains` from the scan JSON; `proposed`/`created`
  by name; `verdict` = the one-liner). Same conversation-first rule as the dream block.
- Unchanged: report-then-apply (NEVER auto-writes; one confirmation = ONE named
  artifact), the genericize firewall, the smallest-form preference, the honest gap
  (authored artifacts live outside the audit trail — named in the debrief).

### 3.4 Alternatives rejected

- **Persisted cross-dream tally / cross-project distill tier** — deferred by the standing
  plan (needs warm fleet nodes); this arc is local signal quality. Do not build ahead.
- **Cross-command temporal sequence mining** — compound-level bigrams already capture
  this user's `&&`-chaining idiom (measured); heavier mining waits for a measured need.
- **Tuning `MIN_RECUR`/window** — measured adequate once noise dies; day-spread ranking
  is the meaningful recurrence signal, not a higher bar.
- **Auto-authoring on high recurrence** — permanently rejected (public-plugin blast
  radius; the standing plan's conductor/Stop-hook precedent).

## 4 · Compatibility & versioning

Additive JSON keys (`days`, `chains`, `scanned.days`), additive `total=False` schema key
+ renderer lines gated on presence, SKILL prose, scanner *content* improvements under an
additive shape. The only "breakage" is internal: the exact-set shape pins and the
`_template` unit tests in smoke.py are part of THIS change set (impl-review MAJOR-1) —
no external consumer breaks (`cm` passes `--json` through; nothing else parses it). No
renamed/removed flags or scripts ⇒ **patch**, `0.1.54 → 0.1.55` (CHANGELOG-first;
`release.sh --expect patch`).

## 5 · Test plan

1. **`_seg_template`/`_scan_cmd` unit table** (pure, no FS): echo-led chain → real
   segments counted, `echo` row absent; heredoc body lines absent — pinned on a QUOTED
   tag (`python3 - <<'PY' …body with print(f)… PY` → exactly `python3 -`; the B1
   order-of-operations regression) and a dash-heredoc (`<<-EOF`); loop bodies keep their
   command (`for f in *.py; do mypy $f; done` → `mypy` counted; `for`/`done` absent —
   the M2 regression); `foo 2>&1 | tail` → `foo` (no dangling `2`);
   `cmd >> app.log` → `cmd` (no leaked filename — the m1 split-not-sub pin);
   `\`-continuation joins; stoplisted heads dropped; once-per-command dedup
   (`smoke && smoke` → count 1); branch-name + abs-path genericization unchanged
   (regression, retargeted from the retired `_template`).
2. **Chains (bridge semantics, per §3.1):** `a && b && c` → `(a,b)`, `(b,c)` once each;
   `a && echo x && b` → `(a,b)` IS produced (the stoplisted middle bridges — adjacency
   over KEPT segments); `a && a` → no self-chain.
3. **Day-spread:** synthetic two-day transcript → row `days == 2`; ranking prefers
   2-day ×2 over 1-day ×5.
4. **JSON contract:** `--json` parses; rows carry `days`; `chains` present (possibly
   empty); `scanned.days` present; stdout purity under `CM_DREAM_ARC=1` (cue on stderr —
   regression from v0.1.54).
5. **Schema cascade:** SKILL block ↔ `Distill.__annotations__` nested pin;
   `validate_cycle_record` warns on `distill: []` / `distill.proposed: "x"` /
   `distill.created: {}` (descending only into a dict `distill`, mirroring `dream.beats`
   — impl-review M-5), silent on well-formed; mypy clean.
6. **Renderers:** record with `distill` ⇒ dashboard DISTILL line + HTML line; without ⇒
   byte-identical legacy (no line).
7. **SKILL pins:** the verdict-contract anchors exist (`nothing:` + "which gate leg" /
   named-top-candidate phrasing, chains-first instruction); the deleted hedges
   ("usually proposes nothing", "EXPECTED outcome") are ABSENT from the file.
8. **Beta family:** 6-case — WARN (latest record without a `distill` block) / WARN
   (block present but empty `verdict`) / PASS (non-empty verdict) / SKIP
   (`maintenance.pivoted` latest) / SKIP (pre-0.1.55 or unknown version, fail-closed) /
   SKIP (empty log) — plus the dream_arc_capture regression suite still green after the
   shared-helper refactor.
9. **Empirical acceptance:** run the rebuilt scanner on this repo's live corpus —
   `echo`/heredoc/keyword rows absent, `smoke ×≥200` with multi-day spread, the
   gate-chain visible in chains. (Manual check at implementation time, mirrored by the
   unit table.)

## 6 · Edit list

| File | Change |
|---|---|
| `plugins/consolidate-memory/scripts/distill_scan.py` | extraction pipeline (§3.1: continuation-join, heredoc-body strip, all-segment, redirect-strip, stoplist, once-per-command, day-spread, chains) + `_report` CHAINS section |
| `plugins/consolidate-memory/scripts/memory_status.py` | `Distill` TypedDict + `distill` key + validator entries |
| `plugins/consolidate-memory/scripts/render_dashboard.py` | gated DISTILL line (`_dget`/`_lget`) |
| `plugins/consolidate-memory/scripts/dashboard.template.html` | gated distill line in "This Pass" (esc()) |
| `plugins/consolidate-memory/skills/consolidate-memory/SKILL.md` | distill step rewrite (§3.3) + schema block `distill` |
| `plugins/dream-beta-tester/scripts/beta_checks.py` | `_latest_capture_check` shared scaffold + `distill_capture` family + `dream_arc_capture` refactored onto it |
| `tests/smoke.py` | §5 test block + nested-pin tuple + REVISE the v0.1.51 distill block (1415–1473: `_seg_template`/`_scan_cmd` retarget, shape-pin keysets updated) |
| `CHANGELOG.md` | `## [0.1.55]` |

## 7 · Review log

**Round 1 — design+prose lens (2026-07-02, recovered from the agent transcript after a
mid-stream stall):** verdict APPROVE-WITH-CHANGES — 1 BLOCKER + 3 MAJOR + 7 MINOR, with
the two load-bearing claims verified by EXECUTION. Resolutions (all applied):
1. BLOCKER B1 — quote-strip before heredoc-strip deletes the quoted tag (`<<'PY'` →
   `<<`; proven by running the shipped regex), so bodies leaked → pipeline reordered:
   heredoc-body strip FIRST on joined raw (marker consumed, `<<-` included), then
   quote-strip; §5.1 pins the quoted-tag regression.
2. MAJOR M1 — chain-semantics contradiction → CONVERGENT with impl MAJOR-2; already
   resolved to filter-then-adjacent (bridge).
3. MAJOR M2 — keyword-headed segments dropped whole lose loop-body commands
   (`do mypy $f` → dropped; proven) → two-class keyword handling: PREFIX-STRIP
   `do`/`then`, DROP-WHOLE keyword-only/condition segments; §5.1 pins it.
4. MAJOR M3 — `created`/declined lifecycle collapse at persist time → lifecycle pinned:
   `created` = authored-before-persist only; `verdict` is the terminal carrier encoding
   disposition (awaiting-confirmation / declined / created / nothing+leg); post-persist
   authoring stays a debrief fact, never retro-written.
5. m1 redirect cut → pinned split-keep-head (not `re.sub`); §5.1 filename-leak case.
6. m2 int-vs-list collision → record fields renamed `n_recurring`/`n_chains` + `len()`
   fill rule.
7. m3 same-day burial → accepted residual; SKILL notes rank-is-a-hint.
8. m4 `||`/`$()`/`<<-` → `<<-` folded into B1; the others documented as accepted
   residuals (§3.1 step 9).
9. m5 maintenance false-WARN → CONVERGENT with impl M-2; already deterministic
   (`maintenance.pivoted` ⇒ SKIP).
10. m6 D2 oversell → D2 + §3.1 step 9 tightened (chains = intra-command glue; the
    multi-call arc stays model-recognized).
11. m7 verdict length → pinned (one line, ≤~60 dashboard, HTML full).

**Round 1 — impl lens (2026-07-02):** verdict APPROVE-WITH-CHANGES, 3 MAJOR + 5 MINOR,
no blockers. Resolutions (all applied):
1. MAJOR-1 omitted test-updates + misleading compat claim → §3.1 pins the
   `_seg_template`/`_scan_cmd` decomposition; §4 names the internal shape-pin/unit-test
   revisions as part of the change set; §6 smoke row lists the v0.1.51 block revision.
2. MAJOR-2 self-contradictory chain semantics → pinned **filter-then-adjacent (bridge)**
   (`a && echo ok && b` → `(a,b)`), with the honesty note that the prototype doesn't
   discriminate bridge-vs-break; §5 test 2 rewritten.
3. MAJOR-3 second near-copy vs shared helper → EXTRACT `_latest_capture_check`; both
   families become thin calls; dream_arc_capture behavior pinned by its existing cases.
4. M-1 `@family` registration + predicate → pinned; predicate UPGRADED beyond the
   suggestion: PASS iff `distill.verdict` non-empty (the verdict is the checkable core),
   not merely a non-empty dict.
5. M-2 maintenance-pass false-WARN → made deterministic: `maintenance.pivoted == true`
   ⇒ SKIP (not wording).
6. M-3 timestamp null-guard → §3.1.
7. M-4 case-count → §5 test 8 now 6-case.
8. M-5 validator descend-guard → §5 test 5.
