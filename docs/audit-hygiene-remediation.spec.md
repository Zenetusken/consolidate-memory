# Audit-hygiene remediation (Track A) — spec

**Provenance:** the 2026-07-05 four-lens release-readiness audit of the skillset @ v0.1.68
(docs-contract · scripts-runtime · packaging/tests · beta-tester lenses, every finding
confirmed at file:line against the live tree). This spec covers **Track A** — the
consolidate-memory hygiene fixes. Track B (dream-beta-tester truth restoration) and
Track C (CI + repo docs) ship as separate, file-disjoint PRs.

**Rule of engagement:** every behavioral fix lands with a smoke check that **FAILS on the
pre-fix code** (recorded in the PR), so each defect becomes a living regression gate.

## Scope

| ID | Finding | File(s) | Class |
|---|---|---|---|
| A1 | window filter compares timestamps as raw strings | `extract_signals.py:399,567` | P1 correctness |
| A2 | TTY report prints un-sanitized signal text (ANSI escape injection) | `extract_signals.py:507` | P2 security |
| A3 | per-fact `read_text` unguarded → OSError crash on vanish race | `sync_global.py:1066,1068,1104` | P2 robustness |
| A4 | `_run` swallows git failure silently (broken git ≡ empty repo) | `memory_status.py:1263-1270` | P2 failure-honesty |
| A5 | maintainer username in shipped/public files (slash + slug forms) | `memory_status.py:605-606`, `tests/smoke.py:347,474-479,1424,1426`, `docs/signal-pipeline-hardening.spec.md:49` | P2 genericity |
| A6 | SKILL overclaims `--list` shows "held" (contradicts code + harness-map) | `SKILL.md:385-391` | P2 doc-contract |
| A7 | schema pin omits `usage`/`demotion`/`usage.per_fact[0]` nests | `tests/smoke.py:817-849` | P2 drift-guard |
| A8 | `.gitignore` lacks `.ruff_cache/` | `.gitignore` | P3 hygiene |

## A1 — parsed-instant window compare (the P1)

**Current.** `extract()` (:399) and `_recall_items()` (:567) scope to the window with
`if since and ts and ts <= since: continue` — a **raw string** compare. `distill_scan.py:327-330`
was already fixed to compare parsed instants (`ts_dt <= since_dt`) for exactly this defect;
extract never got the twin fix. A `--since`/marker carrying a UTC offset (`+02:00`, or the
no-colon `+0200` that `_parse_ts` normalizes) against Claude Code's `Z` stamps makes
lexicographic order ≠ instant order → boundary sessions silently mis-included/dropped.
The default path (marker in CC `Z` format) is unaffected, which is why it hid.

**Change.** In both functions: parse the window once above the loop
(`since_dt = _parse_ts(since) if since else None`; `_parse_ts` is already imported, :43),
parse the line's `ts` inside, and compare instants:
`if since_dt and ts_dt and ts_dt <= since_dt: continue`. Semantics preserved: skip-if-≤,
and **fail-open** — an unparseable `ts` or `since` disables the filter for that
line/run (over-include, recall-biased) instead of garbage-filtering. Per-line parse cost is
noise next to the `json.loads` already paid per line (distill's lazy-memo shape is for its
multi-part inner loop; extract has one `ts` per line, so a direct parse matches).

**Acceptance.**
- New smoke checks (pre-fix **FAIL**): with `since = "2026-07-05T18:00:00+02:00"`
  (= `16:00Z`), a line stamped `2026-07-05T16:30:00Z` is **kept** (instant-after; the raw
  string compare wrongly drops it: `"2026-07-05T16:3…" < "2026-07-05T18:0…"`), and a line
  stamped `2026-07-05T15:30:00Z` is **dropped**. Mirrored for `_recall_items`.
- Unparseable `ts` on a line → line kept (fail-open), no exception.
- Mixed aware/naive never raises: assert `_parse_ts` yields comparable (tz-aware) values
  for `Z`, `+HH:MM`, and `+HHMM` inputs *(R1 resolved at Gate-1: `_parse_ts`
  (memory_status.py:561-580) returns tz-aware-or-None for EVERY accepted shape — a naive
  parse is coerced to UTC before return — so the instant compare cannot raise TypeError)*.

## A2 — sanitize report text at the presentation boundary

**Current.** `_report()` prints each signal's `text` via `_ui.wrap(s["text"], hang=33)`
(:507) after only `_norm` (strips Cf; **not** C0/ESC). A repo whose tooling emits ANSI
sequences in an error tool-result reaches the terminal raw through `cm extract` →
terminal-escape injection from repo-controlled content. The `--json` path is safe
(`json.dumps` escapes control bytes) and must stay raw-but-escaped (the model may need
the bytes as signal).

**Change.** Presentation-boundary fix only, matching the codebase convention
(`memory_status._sane` / render `_clean` both strip C0/C1 at render time):
`_ui.wrap(_sane(s["text"]), hang=33)` — `_sane` is already imported (:43). No change to
stored signals or `--json` output.

**Acceptance.** New smoke check (pre-fix **FAIL**): a signal dict whose `text` contains
`"\x1b[31mred\x1b[0m"` rendered through `_report` (stdout captured) yields output with
**no `\x1b` byte** and still containing `red`; the same record through the `--json` path
keeps `signal_type`/`score` intact *(R2 resolved at Gate-1: `_sane`'s `_CTRL` class
`[\x00-\x08\x0b-\x1f\x7f-\x9f]` includes ESC 0x1b; tab/newline are preserved — post-fix
the text renders as `[31mred[0m`, escape-inert)*.

## A3 — store-scan convention for `_node_tokens` / `_network_nodes`

**Current.** Three reads miss the module's own "store-scan convention" (every sibling
scan guards OSError — e.g. the fleet-utility and evict scans): `idx.read_text` behind an
`exists()` TOCTOU (:1066), the `bodies` dict-comprehension (:1068), and `_is_mirror(f.read_text(…))`
inside `any(…)` (:1104). A fact deleted/chmod'd mid-scan (concurrent gc, another dream)
crashes `cm tokens`, `cm network`, and the dream's Phase-5 network capture.

**Change.** Rewrite the three sites to skip unreadable files per the convention
(try/except OSError → treat index as `""` / skip the fact / skip the candidate file),
with the standard one-line comment. Silent-skip is the correct degrade here: these are
advisory token *estimates*; excluding a vanished file is measurement, not fabrication.

**Acceptance.** New smoke checks (pre-fix **FAIL**): a tmp store containing a dangling
symlink `ghost.md` — `_node_tokens(store)` returns counts excluding it without raising;
`_network_nodes()` over a projects tree containing such a store neither raises nor
mis-drops the store when a *readable* mirror is also present. *(Gate-1 note: these two
checks gate :1068 and :1104; the :1066 `exists()`-then-read TOCTOU is bundled
belt-and-suspenders — a dangling `MEMORY.md` takes the safe `exists()==False` branch, so
no deterministic pre-fix-FAIL exists for that site and none is claimed.)*

## A4 — label the degraded git path

**Current.** `_run` (:1263-1270) returns `""` on `(OSError, SubprocessError)` with no
diagnostic: a missing/broken/timed-out `git` is indistinguishable from a clean repo with
no new commits → the dream silently under-scopes to "NOTHING TO CONSOLIDATE". Violates
the no-failure-masking law (degrade is fine; it must be **labeled**).

**Change.** On the except path, emit **one** stderr line per process (module-level
`_GIT_WARNED` flag; `_run` is called many times per pass — a missing git must not spam):
`memory_status: git unavailable (<ExcName>) — scope degraded to empty` → still return `""`.
stderr is the diagnostic channel per the stdout/stderr contract; `--json` stdout purity
is unaffected.

**Acceptance.** New smoke checks (pre-fix **FAIL**): with `subprocess.run` monkeypatched
to raise `FileNotFoundError`, `_run(["git","log"], tmp)` returns `""` AND stderr contains
`git unavailable`; a second call adds **no** second line (dedupe flag, reset explicitly in
the test); stdout stays empty.

## A5 — genericity scrub + a living genericity PIN

**Current.** The shipped `memory_status.py:605-606` docstring cites the maintainer's
real `/home/<user>/.claude/…` path AND its dash-form slug ``-home-<user>--claude-…``
(line 604 uses the correct `/home/you` placeholder — 605-606 slip, in BOTH forms);
`tests/smoke.py:347,1424,1426` (slash form), `tests/smoke.py:474-479` (slug form, the
`…-project-Doc-Flo` slug expectations) and `docs/signal-pipeline-hardening.spec.md:49`
(a real screenshot path) repeat the real username in public-but-unshipped files.
*(`<user>` is a deliberate placeholder for the actual username throughout this spec:
this file is itself a tracked `docs/` spec INSIDE the pin's scope, so it must never
carry the literal name — the same defect class it remediates. Angle brackets sit
outside both pin patterns' name character class by construction, so the placeholder is
pin-inert.)* The slug form matters: a slash-form-only scrub leaves :605-606 internally
inconsistent (a `/home/you/...` path cannot slug to `-home-<user>-...`) and a
slash-form-only grep false-greens while the username persists in dash form.

**Change.** Mechanical scrub of BOTH forms: slash `/home/<user>…` → `/home/you…` at the
five slash sites, AND slug ``-home-<user>…`` → ``-home-you…`` at `memory_status.py:606`
and `tests/smoke.py:474-479` (the smoke expectations at :347 update both sides of the
equality: `/home/you/project/Doc_Flo` ↔ `-home-you-project-Doc-Flo`; :1424/:1426 `cd`
paths don't affect expected outputs — the cd line is stripped/dropped by `_scan_cmd`).
**Plus a new smoke PIN** scanning every tracked `*.py`, `*.md`, `*.sh`, `*.html` under
`plugins/consolidate-memory/`, `tests/`, `docs/` with TWO patterns sharing one
allowed-set: slash `/home/<name>` and slug `-home-<name>-` (the slug regex catches the
dash form the slash regex structurally cannot), asserting every `<name>` ∈
{`you`, `u`, `x`, `d`, `nobody`} — the five generic placeholder forms actually in use
(Gate-1 enumeration: `/home/you` ×14 · `/home/x` ×14 · `/home/d` ×4 · `/home/u` ×3 ·
`/home/nobody` ×1 post-scrub). An allowlist is deliberate: introducing a NEW placeholder
requires consciously extending the pin, and any real username fails it.
*(Scope note: the pin deliberately excludes `plugins/dream-beta-tester/` — its
`SPEC.md:27` carries the same defect but is Track B's file; Track B widens the pin to
all of `plugins/` after its own scrub, and Track C adds `README.md` + `CLAUDE.md`
(both verified clean today), keeping the PRs file-disjoint.)*

**Acceptance.** Pin present and **FAILS on the pre-fix tree** (it sees the :605 slash
form; the slug form at :606/:474-479 is caught by the pin's slug pattern); post-scrub
suite green; the username grep — `grep -rn '<user>' plugins/consolidate-memory tests
docs` with the real name substituted — → **0 hits in any form** (the username grep, not
the path grep: no dash-form false green). This spec file itself is in scope and must
stay name-free.

## A6 — `--list` doc claim matches the code

**Current.** `SKILL.md:385` says `--list` surfaces "relevant + present/missing/**held**"
and :386 "can reason about budget"; :391's inline comment repeats "held". In
`sync_global.py` `held` increments only under `--pull` (`held_this = (pull and …)`), so
`--list` can never show it — and `harness-map.md:313` already states the truth
("relevant/present/missing (read-only)"). Latent P1: the moment the hard ceiling binds,
an agent trusting the doc pre-reasons from a preview that cannot exist.

**Change.** SKILL.md prose + inline comment only: drop "held" from both; reword :386 to
"you see the bootstrap/refresh picture; hold/refresh counts appear on `--pull`, which
auto-holds any past-the-CEILING pull". No code change (a `--list` held-preview is a
deliberate non-goal — it would need `run()` to simulate pull budgeting read-only).

**Acceptance.** `grep -n 'held' SKILL.md` shows no `--list`-attributed "held"; the
`--list`/`--pull` lines at :391-392 agree with `harness-map.md:313-314`; schema-block
untouched (the edit is prose-only, so the A7 pin is unaffected by A6).

## A7 — close the schema-pin hole

**Current.** The v0.1.12 pin loop (`tests/smoke.py:824-849`) enumerates 23 nested shapes;
its comment (:817) claims "ALL nested shapes" with two documented carve-outs — but
`usage` (v0.1.63), `usage.per_fact[0]`, and `demotion` (v0.1.67) are silently absent: the
two newest, highest-churn blocks look pinned and aren't.

**Change.** Add FIVE rows to the loop (after the `distill` row, :841): `("usage", …,
ms.Usage)`, `("usage.per_fact[0]", (…get("per_fact") or [{}])[0], ms.UsageFact)`,
`("demotion", …, ms.Demotion)` — plus `("audit.claude_md", …, ms.AuditStoreDelta)` and
`("audit.repo_doc", …, ms.AuditStoreDelta)` (Gate-1 found these two populated sub-dicts
were covered only TRANSITIVELY via the `audit.memory` row; explicit rows make the
exhaustiveness claim literally true). Correct the :817-821 comment so the remaining
carve-outs read exactly: SchemaDrift (renders as an empty `{}` placeholder) + the
pulled/promoted item dicts (untyped `list[dict]`) *(R3 resolved at Gate-1:
`Usage` :130-147 / `UsageFact` :123-127 / `Demotion` :150-161 exist with exactly the
SKILL block's key sets)*.

**Acceptance.** Suite green (no live drift — verified key-by-key in the audit); teeth
demonstrated by a sabotage run recorded in the PR (delete one `usage` key from a copy of
the parsed block → the new row fails). No behavioral pre-fix-FAIL exists for a
guard-addition; the sabotage run is the evidence standard here.

## A8 — `.gitignore` completeness

Add `.ruff_cache/` beside `.mypy_cache/` (ruff self-ignores today via its own internal
`.gitignore`; the repo's no-cruft stanza should not depend on a tool's self-discipline).

## Non-goals (deliberate, with reasons)

- **Global-store write atomicity/locking** (audit F-P2-7) and **`/tmp` seed-path
  hardening** (F-P2-8) → Track D: `O_EXCL` would break the *deterministic re-seed* the
  cycle contract relies on (the seed path is reused across dreams by design); needs a
  design pass (unlink-first vs `$XDG_RUNTIME_DIR` vs per-boot suffix), not a hygiene edit.
- **`--list` held-preview implementation** → doc is corrected instead (A6); the preview
  needs read-only pull simulation in `run()`.
- **Firewall residuals** (sub-40-char bare tokens · cross-turn splits · all-lowercase
  blobs) → documented recall-biased design; optional entropy arm tracked on the roadmap.
- **CI, README/CLAUDE.md, repo topics** → Track C. **All `plugins/dream-beta-tester/`
  files** → Track B.

## Rollout

- One PR (`fix/cm-audit-hygiene`), full-body per repo convention; merge reserved.
- `CHANGELOG.md` gains `## [0.1.69]`: every item above is a backward-compatible fix or
  test/doc tightening — no schema key, no flag change, legacy records render unchanged ⇒
  **patch** per the versioning policy (decide-in-order rule 3). `plugin.json` stays
  0.1.68 in the PR; `release.sh` sets 0.1.69 at release time from the CHANGELOG top
  section (the deterministic release contract).
- Gates: suites + mypy + `claude plugin validate --strict` green pre-PR; Gate 2a full
  `/code-review` on the diff; Gate 2b on the PR.
