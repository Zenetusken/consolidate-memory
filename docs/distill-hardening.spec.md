# Distill — precision hardening, firewall transparency, deterministic capture (v0.1.58)

**Status:** draft → spec-review (design lens, impl lens) → implement.
**Scope:** the patch-sized arc from the 2026-07-03 end-to-end distill audit (measured on three live
corpora + a 27-case adversarial battery). LOCAL extraction precision/recall + capture integrity +
CLI/doc honesty ONLY — the `&`/`||` separator semantics, pipeline next-stage recall, the verdict
lifecycle across dreams, the persisted cross-dream tally (D1 family), and the cross-project tier
stay DEFERRED (each needs its own design round). The report-then-apply / never-auto-writes safety
is untouched and out of scope for change.

## 1 · Problem (measured, 2026-07-03)

The v0.1.55 rebuild works at its core (chains reconstruct the real gate pipelines on both rich
corpora; 546 smoke green; the one production verdict is contract-compliant). Four measured defect
classes remain:

| # | Evidence (live) | Number |
|---|---|---|
| F1 | Shell-syntax junk rows in this repo's top-40: `[ = ]` ×33 · `}` ×16 · `[ -z ]` ×13 · `continue` ×10 · `exit 1` ×10 · `[ -d ]` ×8 — plus the pure-junk chain `exit 1 → }` ×10 | **~15% of rows junk**; junk chain endpoints violate "a chain IS a candidate workflow" |
| F2 | The inline-interpreter false class regenerated on the job corpus: `.venv/bin/python -` ×204 (row #12) + `.venv/bin/python -c` ×95; battery: `python3.12 -c`, `uv run python -` all escape `_STOP_TPLS` | **×299 junk counts, 2 of top-14 rows** |
| F3 | Firewall drops on this repo: 83/1,683 commands (~5%) — classified: 48 `_entropy_blob` hits are false positives (long quoted `$HOME/…` tokens, timestamped backup dirnames, 40-hex SHAs), 35 keyword-arm hits are this repo's own firewall-fixture commands. distill's JSON has **no `secrets_omitted` counter** (extract has one) | **~5% of the corpus silently uncounted, zero transparency** |
| F4 | The ONE production distill block records `n_recurring: 47` — impossible (`MAX_RECUR_OUT = 40` since v0.1.51, git-verified; fill rule is `len(recurring)`). The hand-mirror failed on first production use | **capture integrity broken at n=1** |
| F7 | `scan()` has no per-line `ts <= since` filter (extract has one): the window is file-mtime-approximate; a long-lived session leaks out-of-window lines into counts/day-spreads. A garbage `--since` silently falls back to all-files while `window` reports the garbage | latent (measured 0 today — both files young) |
| F8 | `cm distill --sicne X` swallows the unknown flag and scans project dir `"X"` → a 0-session result indistinguishable from a real empty corpus; nonexistent dir → no warning; `--since` undocumented in `cm help` | silent-wrong-answer class |

Root cause shared by F1+F2: **enumerated literals standing in for structural classes.** The keyword
tables cover `do/then/else/done/fi/esac/for/while/if/case/elif/until` but not the rest of POSIX
syntax; `_STOP_TPLS` pins exact spellings (`python3 -`) of what is semantically "an interpreter fed
an inline body". Both rot as idioms shift — but both close: POSIX syntax is a finite set, and the
interpreter class is expressible as one structural rule.

## 2 · Design

### 2.1 F1 — close the POSIX-syntax noise classes (`distill_scan.py`)

Extend the keyword handling with the REMAINING closed classes, same two-class model as v0.1.55 M2
(prefix-strip what CARRIES a command; drop-whole what cannot):

- **DROP-WHOLE, control (even with args):** heads `exit` `break` `continue` `return` `:` —
  `exit 1`, `return 0` are control flow, never workflow rows.
- **DROP-WHOLE, test guards:** heads `[` `[[` `test` — `[ -d "$X" ]` is a condition, not a command.
  (Covers the `[ … ] || cmd` idiom too: the guard segment dies; the post-`||` text was already
  truncated at the pipe-split — unchanged.)
- **DROP-WHOLE, env-manipulation:** heads `set` `shopt` `trap` `unset` `umask` `ulimit` `shift` —
  script plumbing, never a recurring workflow class.
- **DROP-WHOLE, group closer:** bare `}` (join `_KW_DROP`).
- **PREFIX-STRIP, carriers:** `{` (brace-group opener: `{ real-tool run` → `real-tool run`),
  `!` (negation: the negated command still executes — `! deploy-check run` → `deploy-check run`;
  `! grep -q x` → `grep…` → stoplisted, correct), `eval` and `exec` (`exec gunicorn …` →
  `gunicorn …`; `eval "$(ssh-agent)"` → strips to empty → None).
- **DROP-WHOLE, assignment keywords (design-review F4 — simplified from prefix-strip):** `export`
  `local` `declare` `typeset` `readonly` — these NEVER carry a command (POSIX: names/assignments
  only), so drop the segment whole. This kills the measured value-retention (`export CM_FLAG=on`
  emitted a template carrying `on`) AND the residual junk class a prefix-strip would open
  (`export PATH` → a bare `PATH` row; `declare -A m` → a `-A m` row — proven by the design round).
- **`eval`/`exec` post-strip guard (design-review F4):** after the prefix-strip, a remainder whose
  first char is a digit or `<` is fd-redirect plumbing (`exec 3< file`, `exec 2>&1`), not a
  command → drop-whole.
- **Numeric-template screen (impl-review m6):** additionally drop any purely-numeric final
  template (`re.fullmatch(r"\d+", tpl)`) at the final gate — belt for whatever plumbing survives.

Mechanism: `{`/`!`/`eval`/`exec` join `_KW_PREFIX` (the existing while-loop consumes them,
possibly stacked: `! { real-tool run` works; eval/exec get the fd-plumbing guard above); ALL
drop-whole heads (control, test guards, env-manipulation, assignment keywords, `}`) join
`_KW_DROP` / `_KW_HEAD_DROP` stays condition-heads only. The cd/assignment gate keeps running
AFTER all prefix strips (the v0.1.55 K2 invariant). **Accepted residual (design-review F5,
documented in the docstring sweep — never silently extended):** the bridge-chain semantics now
also bridge ACROSS a dropped control terminator (`a && break && b` → chain `(a, b)` though `b` is
unreachable) — a contrived shape (control terminators end real commands) not worth a
drop-kind-aware chain break.

### 2.2 F2 — interpreter class rule (structural, not literal)

Add ONE structural check in `_seg_template`, running on the **post-truncation SEGMENT tokens**
(`seg.split()` after the redirect/pipe truncation, BEFORE the 5-token transform loop drops
absolute-path heads — impl-review MAJOR-1: on finalized template tokens the rule contradicts its
own `basename()`, since `/usr/bin/python3 -c` has already lost its head there and leaks a bare
`-c` junk row). `_STOP_TPLS`/`_STOP_HEADS` stay for cheap exact hits on the finalized template:

```
_INTERP = re.compile(r"^(?:python\d*(?:\.\d+)?|pypy\d?|node|deno|bun|ruby|perl|php|bash|sh|zsh|dash|ksh)$")
basename(t) = t.rsplit("/", 1)[-1]
drop if:  len(toks) == 1 and _INTERP.match(basename(toks[0]))          # bare interpreter, any path
      or  toks[-1] in {"-", "-c", "-e"} and len(toks) >= 2
          and _INTERP.match(basename(toks[-2]))                        # inline-body carrier, any path/runner
```

Covers the measured/battery escapes: `.venv/bin/python -` · `.venv/bin/python -c` · `python3.12 -c`
· `uv run python -` (toks[-2] = `python`) · `/usr/bin/env python3 -` · **`/usr/bin/python3 -c`**
(catchable only at the segment-token stage — see placement above) — while KEEPING the real
classes: `python3 tests/smoke.py`, `.venv/bin/python -m pytest -m unit` (toks[-1] = `unit`), and —
**regression-critical** — `git commit -q -F -` (toks[-2] = `-F`, not an interpreter) ×165 on the
job corpus. **Intent pinned (design-review F8):** the rule deliberately reaches an interpreter
under ANY runner — `docker run img python -c` / `ssh host python -c` are the same
one-off-inline-body false class as `uv run python -`; dropping them is intended, not collateral.

### 2.3 F3 — firewall moves to the EMISSION point (predicate untouched)

`_looks_secret` itself does not change (CLAUDE.md: never weaken the firewall). What changes is
WHAT a hit suppresses. Today a hit drops the whole command from the count — measured ~5% false
positives, invisible. The distill output is a 5-token CLASS template + one display sample; the
sample is the only surface that carries raw text. So:

- **A firewall hit no longer skips the command.** It increments a new `scanned.secrets_omitted`
  counter, and the command's templates/chains count normally — but any NEW template introduced by
  a flagged command gets the label `"(sample omitted — credential-shaped command)"` instead of a
  raw sample. (`setdefault` semantics unchanged: a template first seen in a clean command keeps
  its clean sample.) **Increment placement pinned (impl-review MAJOR-4):** `secrets_omitted += 1`
  happens AT the firewall-hit site — before `commands += 1` and before the all-noise `continue` —
  because the measured majority of flagged commands (bare `export SECRET=…` assignments, fixture
  echoes) are ALL-NOISE and would otherwise never be counted, defeating the transparency goal.
  `commands` includes flagged commands (they are scanned) — a cross-version value shift (~+5% on
  the measured corpus) called out in the CHANGELOG (design-review F7).
- **Suppression source pinned (design-review F3, proven divergence):** the sample suppression and
  the `secrets_omitted` increment are BOTH driven by the ONE command-level
  `_looks_secret(_norm(cmd)[:_PROBE_CAP])` flag — NEVER by re-probing the raw sample or template
  (a zero-width-split blob is caught by `_norm` but invisible to a raw-text re-probe; a naive
  `label if _looks_secret(sample)` impl would leak it). The template choke-point screen is an
  ADDITIONAL independent protection, not the suppression driver.
- **Persistence parity (design-review F7):** the `Distill` block gains additive
  `secrets_omitted: int` alongside `window`, injected by `--into` — firewall activity stays
  visible in the persisted record, not just the ephemeral scan JSON.
- **Template choke-point screen:** `_seg_template` returns None when `_looks_secret(tpl)` fires on
  the *emitted template string* — one screen covers rows AND chain endpoints (chains derive from
  kept templates). This closes the pre-existing theoretical path (a secret-shaped 2nd token
  entering a template when the raw-command probe missed it, e.g. past `_PROBE_CAP`) — the emitted
  surface is now screened *directly*, which is strictly stronger per emitted byte than the old
  drop-the-command rule.
- **Leak analysis (pinned):** emitted surfaces = template (screened above), sample (suppressed on
  hit), chains (template-derived). A secret the predicate misses is emitted no more than today
  (same predicate, now applied to the actual emission). Recall: ~5% of commands return to the
  tally.
- **Report/JSON:** `scanned` gains `secrets_omitted` (keyset pin updated); the human report shows
  `· N secret-shaped (samples omitted)` when nonzero. Module docstring + the v0.1.51
  "firewall FIRST" comment updated to "firewall gates the SAMPLE + the emitted template, not the
  count"; SKILL distill step notes samples may be omitted; the genericize rule is unchanged.

### 2.4 F4 — deterministic capture: `distill_scan.py --into <seed>`

The audit block solved exactly this with `memory_status --audit --into` (v0.1.53). Extend the
pattern:

- `--into <seed-path>`: after the scan, read-modify-write the cycle-record seed. **NOT the audit
  clobber idiom** (impl-review MAJOR-2: `--audit --into` does `_cyc["audit"] = diff` wholesale,
  correct for a 100%-script-owned block — a literal mirror here would DESTROY a model-authored
  verdict, the exact data-loss F4 exists to fix). The distill block is split-ownership, so the
  write is a **sub-key merge**, pinned:
  `d = record["distill"] if isinstance(record.get("distill"), dict) else {}` →
  `d.update(sessions/commands/n_recurring/n_chains/window/secrets_omitted)` → conditional
  judgment-flag writes → `record["distill"] = d`. Counts + **new additive `Distill.window: str` +
  `Distill.secrets_omitted: int`** are script-truth; pre-existing model-authored
  `proposed`/`created`/`verdict` are PRESERVED when the flags are absent.
- **Counts are script-ONLY (design-review MAJOR-F1 — this closes F4 rather than making it
  optional):** the SKILL's hand-mirror instruction ("`sessions`/`commands` from `scanned`,
  `n_recurring = len(recurring)`, …") is **DELETED**, replaced by the `--into` command — counts
  are never hand-authored; only the judgment fields may be (via flags, preferred, or by hand).
  A pin proves `--into` OVERWRITES a pre-seeded wrong `n_recurring` (the ×47 class cannot survive
  a scan).
- Optional judgment flags: `--verdict STR`, `--proposed NAME` (repeatable), `--created NAME`
  (repeatable). **A provided flag REPLACES that key (for the list flags: the flag-set replaces the
  whole list — idempotent on re-run, design-review F2); an absent flag PRESERVES what the seed
  holds** (impl-review m7 — no append ambiguity). Missing/corrupt/non-object seed → ONE stderr
  warning, the scan output still prints, exit 0 (mirrors the audit `--into` best-effort contract).
- **Ordering pinned in SKILL:** the `--into` call is the LAST write to the seed's `distill` block;
  the final record-fill must not rewrite that block by hand (the same clobber rule as the audit
  `--into`). Composability: `--into` + `--json` both allowed (stdout stays the scan JSON; the seed
  write is a side effect; a summary line goes to stderr, keeping stdout pure).
- Schema cascade per the house contract (impl-review m8 wording): add `window` to `ms.Distill`
  AND to SKILL.md's distill schema block — the existing smoke `("distill", …, ms.Distill)` pin
  auto-derives from `__annotations__` and ENFORCES the parity (the tuple itself needs no edit).
- **F4 is MITIGATED, not eliminated** (impl-review MAJOR-5): hand-fill stays legal, so a model can
  still write an impossible count. Backstop: `validate_cycle_record` gains a numeric warn —
  `distill.n_recurring`/`n_chains` exceeding the scanner caps (40/20) is impossible from a capped
  scan → warning. The caps are mirrored as local constants in `memory_status.py` (no import cycle
  — distill_scan imports FROM memory_status) with a cross-module smoke pin
  (`ms._DISTILL_CAPS == (ds.MAX_RECUR_OUT, ds.MAX_CHAIN_OUT)`) so they cannot drift.

### 2.5 F7/F8 — window + CLI honesty

- **Per-line window filter:** in `scan()`, read `ts` once per line and skip when
  `since and ts and ts <= since` — the EXACT lexicographic compare `extract()` uses (empty ts
  kept; `_day_of` now reads the same `ts` var). KEEP-safe **scoped to the formats Claude Code
  actually emits** (design-review F6, proven): transcript ts are UTC-`Z`, the default `--since`
  is `+00:00`; `Z` sorts above `+`/digits so an equal-instant boundary false-KEEPS (recall-safe),
  never false-skips; a non-UTC-offset ts is unreachable in real transcripts. `scanned.days` and
  per-row `days` become honest under long-lived session files.
- **`--since` is validated at the CLI:** unparseable ISO → one stderr line + exit 2 (mirrors
  extract's `--max` error style). This also forecloses the garbage-lexicographic hazard the
  per-line compare would otherwise inherit (`ts <= "banana"` drops everything). (Observed: the
  same latent hazard exists in `extract_signals --since`, which silently falls back — a DELIBERATE
  temporary divergence between the siblings, noted here per design-review F6; the extract sweep is
  out of scope.)
- **Silent-wrong-dir fixes:** a nonexistent `PROJECT_DIR` → stderr warning (scan proceeds, prints
  zeros — recall-safe + visible); an unknown `--flag` → stderr `ignoring unknown flag: …` with the
  KNOWN flags whitelisted (impl-review MAJOR-3 — the visual flags `--ascii` / `--color` /
  `--no-color` / `--color=*` / `--width=*` are consumed by `_ui.set_modes` from `sys.argv`, NOT
  unknown; the warning must cover only genuinely-unrecognized flags, plus the new value flags
  `--since/--into/--verdict/--proposed/--created` and `--json` are known). `cm` help line becomes
  `cm distill [DIR] [--since ISO] [--json]`.

### 2.6 Item 6 — SKILL / docs truth sweep

- **SKILL step 6, gate leg 6:** *"not previously DECLINED — read the last few `distill` verdicts
  from `<store>/.consolidation-log.jsonl` (tail the log); a previously-declined artifact needs
  materially NEW evidence (more episodes/days than when declined), not a re-ask."* (Prose-only;
  surfacing `last_distill` in the Phase-0 seed is DEFERRED — one more seed surface needs its own
  look.)
- **Wording fix:** chains are `&&`/newline/`;`-glued compound sub-steps — SKILL + module docstring
  + README line ~204 currently say "`&&`-glued" only.
- **`harness-map.md` gains a distill section** (currently ZERO mentions): scan `--json` contract,
  the `distill` record block schema (incl. `window`), the `--into` recipe, and the acceptance
  recipe (how to re-run the corpus scan + judge noise).
- **Docstring truth sweep** (`distill_scan.py` header): `||` residual re-justified as low-HARM
  (measured in 15.8% of commands — "low-frequency" is false; the harm is confined to fallback
  arms); the `$()` residual narrowed to NESTED substitutions only (round-3 removed the common
  case); ADD the honest residuals the audit measured: single-`&` fuses commands (deferred),
  stoplisted-head pipelines hide downstream tools (deferred), first case arm lost (existing).

### 2.7 Alternatives rejected / deferred

- **`&` and `||` as separators** — real (fusion measured; 15.8% `||` presence) but needs chain
  semantics design (`||` must be a chain BREAK, not a bridge — a fallback arm is not a workflow
  step). Deferred to its own round.
- **Pipeline next-stage recall** (31 live segments) — changes the "first pipe stage" contract;
  needs its own look at `xargs`/stdin-feed idioms. Deferred.
- **Verdict lifecycle across dreams** (proposed → confirmed/declined tracking; seed `last_distill`)
  — the S1 gate leg above is the cheap prose half; the mechanical half belongs to the deferred D1
  recurrence family. Do not build ahead.
- **`cm log` distill column** — the lean table stays lean; the verdict lives in `--json`, the
  dashboard, and the archive. Deferred until a real audit need shows.
- **Tuning `MIN_RECUR` / window / caps** — unchanged; the audit found the caps fine once noise
  dies.

## 3 · Compatibility & versioning

Additive JSON key (`scanned.secrets_omitted`), additive schema key (`Distill.window`), additive
flags (`--into`/`--verdict`/`--proposed`/`--created`), stricter noise-dropping + firewall-at-
emission are scanner *content* improvements under an additive shape; new stderr warnings; SKILL/
doc prose. The exact-set `scanned` keyset pin in smoke updates WITH this change (in-repo consumer
only; `cm` passes `--json` through). Legacy cycle records render byte-identically (`window` is
`total=False`). No renamed/removed key/script/flag ⇒ **patch**, `0.1.57 → 0.1.58`
(CHANGELOG-first; `release.sh --expect patch`).

## 4 · Test plan

1. **F1 unit table** (live-derived, one pin per class): `[ -d "$X" ] && real-tool run` →
   `real-tool run` only (no `[ -d ]` row, no junk chain endpoint); **the 3-segment bridge pin**
   (impl-review 9a — the 2-segment case passes vacuously): `[ -f x ] && alpha-tool run && beta-tool run`
   → `(["alpha-tool run", "beta-tool run"], [("alpha-tool run", "beta-tool run")])` (the dropped
   guard BRIDGES); `{ real-tool run; } 2>&1 | tee log`
   → `real-tool run` only (no `{`-fused head, no `}` row); `x-tool run && exit 1` / `&& continue`
   / `&& break` / `&& return 0` → control dropped; bare `}` line → dropped; `! grep -q pat f && add-thing run`
   → `add-thing run` only; `! deploy-check run` → `deploy-check run` (negation carries);
   `export CM_FLAG=on` → NO template (value-retention regression); `export PATH=$PATH:/x && real-tool run`
   → `real-tool run` only; `export PATH` / `readonly FOO` / `declare -A m` → dropped (assignment
   keywords drop-whole — the design-round F4 junk class); `set -euo pipefail\nreal-tool run`
   → `real-tool run` only; `eval "$(ssh-agent -s)"` → nothing; `exec gunicorn-run app` → `gunicorn-run app`;
   `exec 2>&1` → nothing and `exec 3< file` → nothing (fd-plumbing guard + numeric screen).
2. **F2 unit table:** `.venv/bin/python -` / `.venv/bin/python -c "x"` / `python3.12 -c "x"` /
   `uv run python - <<'PY'…PY` / `/usr/bin/env python3 -` / **`/usr/bin/python3 -c "x"`** (the
   abs-path head — proves the segment-token placement; today it leaks a bare `-c` row) → ALL
   dropped; SURVIVORS pinned: `python3 tests/smoke.py`, `.venv/bin/python -m pytest -m unit`,
   **`git commit -q -F -`** (the `-F -` false-positive guard).
3. **F3:** fixture transcript where a recurring command carries `AKIA…` → its class template IS
   counted, its `sample` is the omission label, `scanned.secrets_omitted == 1`, no raw secret
   anywhere in the JSON — **fixture ordering pinned** (impl-review m11): the flagged occurrence
   comes FIRST and exactly ONE of the ≥2 occurrences carries the secret (`setdefault` keeps the
   first sample; two flagged occurrences would make the count-pin 2); an ALL-NOISE flagged command
   (bare `export AWS_SECRET_ACCESS_KEY=…`) still increments `secrets_omitted` (impl-review 9c —
   guards MAJOR-4's placement) and is INCLUDED in `commands`; a template that ITSELF looks secret
   (`deploy-tool <40-char-blob>` as a synthetic seg) → `_seg_template` returns None (choke-point
   screen); a **suppression-source divergence pin** (design-review F3): a fixture whose secret is
   zero-width-SPLIT (caught by `_looks_secret(_norm(cmd))`, invisible to a raw-text re-probe) still
   gets the omission label + the increment — proving suppression keys off the `_norm` flag, not a
   sample re-probe; the v0.1.51 firewall pins stay green under the new semantics (`AWS_SECRET…`
   absent from templates+samples — now via the assignment-keyword drop + choke-point).
4. **F4:** `--into` on a seed WITHOUT `distill` → block created with counts + `window` +
   `secrets_omitted`; on a seed WITH model-authored `verdict` → verdict PRESERVED, counts
   overwritten — **including a pre-seeded WRONG `n_recurring: 47` → corrected to the scan truth**
   (design-review MAJOR-F1: positive proof the ×47 class cannot survive a scan); `--verdict/
   --proposed/--created` REPLACE their keys when provided (list flags replace the WHOLE list —
   idempotence pin: running `--into` twice yields the same block); other seed keys untouched;
   missing/corrupt seed → stderr warning + scan still prints + exit 0; stdout purity with
   `--json --into` (summary on stderr); `Distill.__annotations__` ↔ SKILL schema block pin
   extended with `window` + `secrets_omitted`; the validator numeric backstop warns on
   `n_recurring > 40` / `n_chains > 20` and the caps cross-module pin
   (`ms._DISTILL_CAPS == (ds.MAX_RECUR_OUT, ds.MAX_CHAIN_OUT)`) holds; SKILL pins: the hand-mirror
   count language is ABSENT (`n_recurring = len(` must not appear) and the `--into` command line
   is PRESENT.
5. **F7/F8:** a fresh-mtime fixture file containing an OLD-timestamp line → excluded from counts
   AND days; `--since garbage` → exit 2 + stderr; nonexistent project dir → stderr warning, exit 0,
   zero counts; unknown flag → stderr note that does NOT misfire on `--ascii`/`--color=…`
   (impl-review MAJOR-3 pin); `scanned` keyset pin = `{sessions, commands, days, secrets_omitted}`
   (updates smoke:1468 — the one existing hard-fail).
6. **Docs pins:** SKILL contains the gate-leg-6 anchor (`previously DECLINED`) + the `--into`
   command line; harness-map contains a `distill` section anchor; the stale docstring claims
   (`low-frequency`, un-narrowed `$()`) are ABSENT.
7. **Empirical acceptance (manual at implementation time):** re-scan this repo + job-applicator —
   target ZERO junk in rows AND chains on both (the F1/F2 classes specifically); re-run the
   27-case battery — every F1/F2 case now clean, every v0.1.55 pin unchanged.

## 5 · Edit list

| File | Change |
|---|---|
| `plugins/consolidate-memory/scripts/distill_scan.py` | §2.1 keyword/carrier classes · §2.2 interpreter rule · §2.3 emission firewall + `secrets_omitted` · §2.4 `--into`/judgment flags · §2.5 per-line window + CLI validation/warnings · §2.6 docstring sweep |
| `plugins/consolidate-memory/scripts/memory_status.py` | `Distill.window: str` + `Distill.secrets_omitted: int` (additive) · validator numeric backstop + `_DISTILL_CAPS` |
| `plugins/consolidate-memory/skills/consolidate-memory/SKILL.md` | step 6: gate leg 6, `--into` flow + ordering rule, **hand-mirror count language DELETED** (design-review MAJOR-F1), samples-omitted note, wording fix; schema block `distill.window`/`secrets_omitted` |
| `plugins/consolidate-memory/skills/consolidate-memory/references/harness-map.md` | NEW distill section |
| `cm` | help line `--since` |
| `README.md` | chains wording fix — BOTH stale sites (lines ~193 AND ~204, impl-review m10) |
| `tests/smoke.py` | §4 test blocks + keyset/schema pin updates |
| `CHANGELOG.md` | `## [0.1.58]` |

## 6 · Review log

**Round 1 — impl+tests lens (2026-07-03; the reviewer's stream stalled mid-delivery and the
verdict was extracted via SendMessage — the known stall-is-not-dead pattern):** verdict
APPROVE-WITH-CHANGES — 5 MAJOR + 6 MINOR, load-bearing traces PROVEN by execution against the
live scripts. Resolutions (all folded into §2/§4/§5 above):
1. MAJOR-1 — §2.2's "after the stoplist" placement contradicted its own `basename()` (template
   tokens have already dropped abs-path heads; `/usr/bin/python3 -c` → bare `-c` junk row, proven)
   → the rule is pinned to the post-truncation SEGMENT tokens, before the path-drop loop; the
   abs-path case joins the §4 pin table.
2. MAJOR-2 — "mirror the audit `--into`" invited a wholesale clobber (`_cyc["audit"] = diff`,
   proven at memory_status.py:2003) that would destroy a model verdict → the sub-key merge is now
   spelled out mechanically; the audit idiom is explicitly NOT the model.
3. MAJOR-3 — the unknown-flag warning would misfire on the legitimate visual flags (`--ascii` etc.
   are consumed by `_ui.set_modes` from sys.argv, proven) → known-flag whitelist pinned + a
   no-misfire pin in §4.
4. MAJOR-4 — `secrets_omitted` placement under-specified; the measured majority of flagged
   commands are ALL-NOISE (proven: the assignment gate returns None on `export SECRET=…`) and an
   increment placed at/after the all-noise `continue` never counts them → increment pinned at the
   firewall-hit site, before `commands += 1` and the all-noise continue; all-noise-secret pin
   added.
5. MAJOR-5 — "the mis-fill class dies" overclaimed (hand-fill stays legal) → reframed as
   MITIGATED + a validator numeric backstop (warn on counts exceeding the scanner caps, caps
   mirrored with a cross-module smoke pin).
6. m6 — `exec 2>&1` prefix-strips to a numeric junk template (proven) → purely-numeric template
   screen + pin.
7. m7 — repeatable-flag semantics + missing-seed behavior pinned (flag REPLACES, absence
   PRESERVES; corrupt/missing seed → stderr + exit 0).
8. m8 — schema-cascade wording fixed (the smoke tuple auto-derives from `__annotations__`; the
   edit is SKILL.md's schema block).
9. m9 — vacuous/missing pins fixed: 3-segment bridge-across-dropped-guard pin, all-noise-secret
   pin, commands-includes-flagged pin.
10. m10 — README has TWO stale "`&&`-chains" sites (193, 204) + the module docstring — all in §5.
11. m11 — F3 fixture ordering pinned (flagged occurrence FIRST, exactly one of ≥2).
Confirmed non-issues (proven by the reviewer): choke-point cost ~65ms/10k calls; the per-line
compare matches extract exactly; `Distill.window` needs no renderer change; no existing chain pin
breaks; the func-def guard is unaffected by `{` prefix-strip; the v0.1.51 firewall pin stays green.
Blast radius: smoke:1468 keyset pin is the ONE existing hard-fail; the SKILL schema block pin
(smoke:835) enforces the `window` parity.

**Round 2 — design+prose lens (2026-07-03; same stall-then-extract delivery):** verdict
APPROVE-WITH-CHANGES — 1 MAJOR + 7 MINOR; a faithful reimplementation of §2.1+§2.2 reproduced all
23 of §4's claimed outcomes; convergences with the impl round confirmed (interpreter placement,
--into merge, flag whitelist, secrets_omitted placement). Resolutions (all folded):
1. MAJOR F1 — "both paths legal" left F4 optionally-avoidable (proven: log record #16 carries the
   structurally-unreachable `n_recurring: 47`) → counts are script-ONLY via `--into`; the SKILL's
   hand-mirror count language is DELETED (with an absence pin), and a pin proves `--into`
   overwrites a pre-seeded wrong count.
2. F2 — list-flag merge semantics undefined → pinned: a provided flag-set REPLACES the whole list
   (idempotent); absent preserves.
3. F3 — a naive sample-re-probe impl would leak a zero-width-split secret (proven divergence:
   `_norm` catches it, raw re-probe doesn't) → suppression-source pinned to the one command-level
   `_norm` flag + a divergence fixture pin.
4. F4 — the spec's own prefix-strip for assignment keywords opened new junk (`export PATH` →
   `PATH` row, `declare -A m` → `-A m`; proven) → SIMPLIFIED to drop-whole (they never carry a
   command); `eval`/`exec` gain the fd-plumbing guard (`exec 3< file` → nothing).
5. F5 — bridge-chains across a dropped control terminator are semantically false
   (`a && break && b` → chain (a,b); proven, contrived-rare) → ACCEPTED RESIDUAL, documented in
   the docstring sweep, never silently extended.
6. F6 — "KEEP-safe" scoped to CC's real UTC-Z/`+00:00` formats (proven: equal-instant boundary
   false-KEEPS, never false-skips); the deliberate `--since` divergence from extract noted.
7. F7 — the `commands` value shift (~+5%) goes in the CHANGELOG; `secrets_omitted` added to the
   persisted `Distill` block for capture parity (was ephemeral-only).
8. F8 — the interpreter rule reaching interpreters-under-any-runner (`docker run img python -c`)
   confirmed as INTENT, stated in §2.2.
Validated by the round: the interpreter regex survivors/drops (incl. `git commit -q -F -`), the
--into clobber-safety precedent (record #16's script audit block co-existing with hand blocks),
gate-leg-6's groundedness (the log DOES carry verdicts), patch versioning, and that §2.3 does not
weaken the firewall in spirit (drop-to-label preserved; the choke-point is strictly added).

**Round 3 — workflow-backed code review (high effort, 2026-07-03; 20 agents, one finder per angle +
independent verify-per-location):** 10 CONFIRMED findings on the IMPLEMENTATION (the spec was sound;
these are impl defects — several regressions the code introduced vs the spec's intent). All fixed +
re-gated (590 smoke, +8):
1. **[1] firewall weakening (the severe one, SECURITY).** The emission choke-point probed the RAW
   template (`_looks_secret(tpl)`), NOT `_norm(tpl)` — so a zero-width-split credential that flagged
   the command via `_norm` (driving sample suppression) still leaked into a template row/chain
   endpoint (reproduced live). §2.3's own text said "screens through `_looks_secret`" but the impl
   dropped the `_norm`. Fixed: `_looks_secret(_norm(tpl))`; a NON-VACUOUS zw-split smoke pin
   (letters-only blob that survives tokenisation and is invisible to a raw probe).
2. **[2] window compared raw strings, not instants.** `ts <= since` lexicographic against a
   `fromisoformat`-validated `--since` mis-orders a local-offset (`+05:30`) or 3.11-compact `--since`
   → silent data loss / full-corpus zero-scan. §2.5's "KEEP-safe" was scoped to CC's `Z` stamps but
   the `--since` INPUT wasn't constrained. Fixed: a shared `_parse_ts` (used by BOTH the window and
   day-bucketing) compares parsed UTC INSTANTS.
3. **[3] `--since` acceptance version-skewed** (a `+0000` no-colon offset parsed on 3.11, aborted on
   3.10). Folded into `_parse_ts`: a `±HHMM` offset is normalised to `±HH:MM` before `fromisoformat`.
4. **[4]/[7] a trailing/unknown flag was swallowed** (mislabelled "unknown", or its value became a
   wrong project dir at exit 0). Fixed: a value-flag missing its value, or a genuinely unknown flag,
   is a USAGE ERROR (exit 2) — consistent with garbage `--since`.
5. **[5] judgment flags without `--into` were silently discarded** → a loud stderr warning.
6. **[6] `main` returned 0 even when injection failed.** Because the hand-mirror fallback was DELETED
   (design MAJOR-F1), a failed `--into` is an unrecoverable capture loss — so this OVERRIDES the
   impl-round m7 "exit 0" pin: `main` now exits non-zero when `--into` was requested and failed. (The
   discrete SKILL step is not `&&`-chained to anything destructive, so a non-zero exit is safe.)
7. **[8] a flagged-FIRST template pinned the omission label forever** (setdefault), even when a later
   clean occurrence existed → the sample now UPGRADES to the clean one when a clean occurrence of the
   same class arrives.
8. **[9] the new `window`/`secrets_omitted` keys were invisible in the renderers** (CLAUDE.md's
   schema-cascade contract) → added `secrets_omitted` to the ASCII DISTILL line + the HTML "This Pass"
   counts (gated on > 0).
9. **[10] the `--into` re-scan could diverge from the judged scan** (the corpus shifts between the
   judgment scan and the capture re-scan) + double I/O → NEW `--from <scan.json>`: the SKILL saves ONE
   `--json` scan, judges it, and injects THAT file — the recorded counts are byte-identical to the
   judged ones, and the expensive scan runs once. (This ADDS to §2.4; the spec's re-scan flow is
   superseded by the single-scan flow.)
Two LOW duplication findings ([16]/[17]) were dropped under the report cap; both are deliberate
(the `inject_into` sub-key merge is intentionally NOT the audit wholesale-clobber; `_DISTILL_CAPS` is
a pinned mirror, not accidental drift). Refuted: none (all 20 candidates verified).

**Round 4 — SECOND workflow code review (high effort, 2026-07-03; 14 agents, verify-per-location; the
user asked for a thoroughness pass over the round-3 FIXES):** 7 distinct defects — 5 fixed, 2 accepted
as consistent-by-design:
1. **[0/1/2] (headline) `inject_into` KeyError on a partial `--from` scan.** The new `--from` gate
   accepts a dict with `scanned`/`recurring`/`chains` but `inject_into` direct-indexed `d["window"]` /
   `d["scanned"]["secrets_omitted"]` (absent from a stale pre-v0.1.58 scan) and its `except` omitted
   KeyError → uncaught crash + lost capture. Fixed: defensive `.get()` defaults (a partial-but-valid
   scan now works, `secrets_omitted`→0 / `window`→"(all)") + KeyError/TypeError in the backstop.
2. **[3] the eval/exec fd-guard false-dropped digit-NAMED tools** (`exec 7z x a.zip`, `eval 2to3 -w`
   → `([],[])` via the naive `seg[0].isdigit()`). Fixed: a precise `^(?:\d+)?[<>&]` fd-REDIRECT match —
   `7z`/`2to3` survive, `exec 2>&1`/`3< f`/`>log` still drop.
3. **[6] `_parse_ts` re-implemented `_window_transcripts`' inline parse** (the reimplementation-pin), so
   the `±HHMM`-offset robustness reached the per-line filter but NOT the file-prune (which no-op'd →
   opened all history). Fixed: `_parse_ts` PROMOTED into `extract_signals`, `_window_transcripts` routes
   through it, distill imports it — one parser, the two window mechanisms can't diverge.
4. **[7] `_day_of` went dead** (scan inlined its body). Fixed: a `_day_str(dt, raw)` helper both call
   (scan passes its already-parsed `ts_dt`, no re-parse), single source of the fallback expression.
5. **[8] doubled `seg.split()`** in the hot per-segment path → reuse `toks`.
- **[4] PLAUSIBLE (accepted, consistent-by-design):** a secret-only day now accrues to `scanned.days`.
  The old exclusion was a side-effect of dropping the whole flagged command; now that flagged commands
  COUNT (into `commands`/`secrets_omitted`), counting their active day is coherent — `days` is advisory.
- **[5] PLAUSIBLE (accepted, already covered):** a skipped `--into` leaves an absent block. Not a code
  defect — the validator can't warn on a legitimately-absent block (maintenance pivots skip distill);
  detectability already lives at the right layers (the `distill_capture` beta family PASSes only on a
  non-empty verdict; round-3 [6] made `--into` failure exit non-zero).
Refuted by the round's own verifier: 1 of 10 candidates. Re-gated: 592 smoke (+2), mypy + sim +
manifests + plugin-validate green; the two correctness fixes proven live.
