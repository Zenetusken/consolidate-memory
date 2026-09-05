# Environment pre-flight — design-of-record

**Status: advisor pass (11 findings, amend-1) + adversarial review-to-zero (11 findings, amend-2 —
1 HIGH · 5 MED · 5 LOW, all folded) + per-PR implementation review (8 findings — 3 MED · 5 LOW,
all fixed + pinned, amend-3) complete. Shipped in v0.4.16.**
Target release: **v0.4.16 (patch)** — additive script + additive record/state keys; legacy records render.

## §1 Context (measured)

Two deployment questions were raised against the live install path — a user inside Claude Code
installing via `/plugin marketplace add Zenetusken/consolidate-memory`:

1. **A Python built without the `sqlite3` stdlib module.** Measured: `control_plane.py:16`
   imports `sqlite3` **top-level** with no availability guard anywhere in `scripts/` — a missing
   module crashes every command with an ImportError traceback before any friendly output. The
   plugin is stdlib-only, so the dependency is the *module*, never a system `sqlite3` binary.
2. **Native memory / Auto-Dream features disabled.** Measured: they are **not a prerequisite** —
   the clean-room install simulation (2026-09-05) ran the full flow (registry bootstrap,
   enrollment, canonicals, pull, fleet lens, renderers) under a bare `CLAUDE_CONFIG_DIR` with no
   Claude Code running at all. But nothing today *proves* the relevant dirs are creatable before
   a write fails.

Additional measured no-happy paths folded in (the "be thorough" mandate):

- **Windows is fail-closed, not fail-friendly.** `require_interprocess_lock`
  (`control_plane.py:1248-1255`) raises `WriteRefused` on `fcntl` ImportError, and every
  registry/journal open takes `locks/schema.lock` — so native Windows dies on first bootstrap
  with a lock error instead of a guidance line. (ADR 016 already declares POSIX-only.)
- **SQL dialect floor.** The plane uses UPSERT `ON CONFLICT … DO UPDATE` (control_plane.py:820,
  832, 908, 1006, 1047, 1136, 1142, 1154, 2906, 3401, 3487; store_context.py:557) → SQLite ≥
  3.24.0. No CTE/RETURNING/JSON ops exist, so 3.24.0 is the true floor.
- **No-git already degrades, deliberately** (shipped policy): `source = "default-path"`
  (`store_context.py:908`), path-keyed uuid5 identity (`project_id_for`, 424-438),
  `memory_status._run` (2202-2222) labels git failure once and degrades scope to empty. The
  pre-flight must *surface* this, not re-litigate it: WARN, never FAIL.
- **Unwritable TMPDIR crashes Phase 0.** `memory_status.py --seed` writes the per-slug cycle
  file via `_write_private` (3911) with no try/except — a traceback, not a verdict. (This
  upgraded the check to FAIL.)
- **`${CLAUDE_PLUGIN_ROOT}` is shell-only.** An unset var kills hooks/commands in the shell
  before Python starts (`No such file or directory`) — the documented symlinked-skill gotcha. A
  truncated install must be reported as a verdict, not a shell error.
- **The beacon is budget-bound.** SessionStart hook timeout is 2s (`hooks.json`), and the
  beacon contract forbids live probes/subprocesses — the pre-flight verdict must be **cached**
  for the beacon (the `stacks` cache in `.consolidation-state.json` is the exact precedent,
  `sync_global.py:1673-1720`).
- **The resolution-failure class (the brokenest environment).** Two measured raise classes
  (adversarial review, amend-2): an **EACCES config root** raises `PermissionError` out of
  `_merge_settings` (pathlib propagates at `store_context.py:695`, called from `resolve_store`)
  — and a **no-sqlite3 interpreter** raises `ImportError` at `store_context.py:870` (the
  mid-function `from control_plane import …`; control_plane's module body imports sqlite3 at
  `control_plane.py:16`). Today `cmd_doctor` (`cm_ops.py:755`, unwrapped) and Phase 0
  (`memory_status.py:3897`, unguarded) re-raise both as tracebacks before ANY pre-flight could
  print. (A config root that is a FILE does NOT raise — it resolves cleanly to a garbage native
  path, which probe #7's mkdir catches or which crashes at first write.) The design below must
  reach the resolution class or the feature diagnoses every environment except the one where
  the plugin is most broken — **with one honest boundary: the beacon cannot cover it** (the
  verdict cache needs a resolved ctx; a no-sqlite3 env never resolves). Stated, not solved.

## §2 Design — `scripts/preflight.py`

Stdlib-only. **No top-level import of `control_plane`, `sqlite3`, or `store_context`** — the
script's core promise is reporting a missing sqlite3 rather than dying of it. Pure probe
functions take injectable params (platform, version_info, which, importer, run) so the smoke
suite stubs failures in-process. Runtime budget < ~300ms, fully offline, no `CM_DREAM_ARC`
involvement, no `dream_cue`. **Syntax discipline (review F11): preflight.py must PARSE on 3.7**
(no walrus, no positional-only params, no 3.8-only syntax) so probe #1 genuinely discriminates
below the floor — its FAIL branch is untestable in CI (runtime floor is 3.8) and documented as
such.

Surface:

- `probe_*` — one pure function per check, returning
  `{"id", "status": pass|warn|fail|skip, "label", "fix", "detail"}`.
- `run_checks(env) -> {"ok", "at", "checks", "notes"}` — env is a namespace of injectables
  (including resolved paths + a `store_resolution_error` sentinel). **Sentinel-path probe
  policy (review F1c):** when resolution failed, run every **ctx-free probe** (#1-4, #8-13)
  alongside #14; only #5 (needs plugin_data_dir) and #7 (needs the native dir) skip. A
  no-sqlite3 env therefore shows **#3 FAIL with its fix line AND #14 with the ImportError
  detail** — the actionable line reaches the user.
- `run_for_project(project_dir)` — guarded `resolve_store` → `run_checks` → `run_and_cache`.
  **Freshness (advisor F4):** consults the cached verdict first and re-runs probes only when
  the cache is absent or older than **1h** (mirror the `sync_global.py:1697-1705` early-return);
  `cmd_doctor` always forces a fresh run. The human-report PRE-FLIGHT section renders from the
  cached verdict either way.
- `run_and_cache(ctx)` — **routes through the standard writer** (review F1/F2, amend-2):
  `update_project_state(ctx, mutator)` with the mutator doing
  `st["preflight"] = {"at": iso, "fails": [ids], "warns": [ids]}` — the one-writer law; silent-skip
  on `(OSError, WriteRefused)`. NEVER raises (BLE001). **The no-sqlite3 env never reaches the
  cache by construction** (`resolve_store` raises first, store_context.py:870) — the sentinel
  path is its channel; the beacon is silent there, documented as the resolution-failure
  boundary. **State-cache key shape (review F9):** `preflight = {"at": ISO, "fails": [check-ids],
  "warns": [check-ids]}`; `cache_advisory` treats any non-dict value or non-list `fails` as
  absent.
- `verdict_for_cache(result)`, `cache_advisory(state_path, ttl_s=7*86400)` — the beacon's
  read-only, absent/garbage-tolerant consumer (the session_beacon.py:171-184 pattern). Fresh +
  fails → one line; warns/pass/absent/stale → `""`. Never raises.
- `render_table(result)` via `_ui` (lazy import — a truncated install must still render). The
  table and the `--json` `preflight` key **exclude the volatile `at` timestamp** (advisor F4 —
  the twice-run doctor-equality pin must not break on run 1 vs run 2).
- `main(argv)` — `preflight.py [PROJECT_DIR] [--json]`; exit 0 = no fail, **2 = any fail**.

### Check matrix (fixed order = JSON output order; pins rely on it)

| # | id | probe | verdict | fix line |
|---|---|---|---|---|
| 1 | python-floor | `sys.version_info >= (3,8)` | FAIL | Install Python 3.8+ |
| 2 | posix | `sys.platform in ("win32", "cygwin")` → fail (cygwin's emulated flock over Win32 handles is unverified against the cross-process exclusion the registry assumes — advisor F9, hypothesis-labeled); else lazy `import fcntl` | FAIL | Linux/macOS/WSL — Windows mutation is fail-closed by design (ADR 016) |
| 3 | sqlite-module | lazy `import sqlite3` | FAIL | Rebuild Python with the sqlite3 stdlib module (no system binary needed) |
| 4 | sqlite-floor | `sqlite3.sqlite_version >= 3.24.0` | FAIL | The SQL dialect needs UPSERT (3.24+); use a newer bundled SQLite |
| 5 | sqlite-roundtrip | temp DB **in plugin_data_dir**: real `SCHEMA_SQL` + `_migrate_schema` + UPSERT insert/select/delete + a real `flock` acquire/release on a sibling `.lock` file (the lock primitive the plane is built on — advisor F7, the NFS/overlay-mount class); unlink (+ -wal/-shm); no WAL mode | FAIL (**skip if #3 or #4 fails** — one root cause, one FAIL row; advisor F5) | The real schema or flock can't execute here — check disk/permissions/filesystem (registry writes refuse on flock-less mounts) |
| 6 | plugin-self | `plugin.json` readable + sibling `.py` set present (constant asserted against the live `scripts/` listing in smoke) | FAIL | Reinstall via `/plugin marketplace add Zenetusken/consolidate-memory` |
| 7 | native-mem-dir | mkdir + temp-file probe + statvfs floor of the resolved native memory dir | FAIL when `auto_memory_enabled`; **skip when disabled** (native absence is a supported config per §1.2 — advisor F8) | `~/.claude` must be creatable/writable with free space — native Auto-Memory itself is NOT required |
| 8 | git-present | `shutil.which("git")` | WARN | Dreams degrade to empty scope without git (shipped policy) |
| 9 | git-repo | `rev-parse --is-inside-work-tree` (skip if #8 not pass) | WARN | Path-keyed identity; enroll from a git root for verification |
| 10 | git-shallow | `rev-parse --is-shallow-repository` (skip cascade) | WARN | Shallow clone limits history verification |
| 11 | python3-path | `shutil.which("python3")` | WARN | Slash commands invoke `python3` — add it to PATH. Reachability boundary (advisor F11): fires only when preflight runs under a non-`python3` interpreter; a truly python3-less PATH kills the hooks at the shell — out of this script's reach, stated not solved |
| 12 | tempdir | `os.statvfs` free-space floor (≥1MB, the cycle-seed size class) **and** a real 64KB temp write+unlink (advisor F6 — EACCES *or* ENOSPC kills the seed write) | FAIL | TMPDIR must be writable with ≥1MB free — Phase 0 writes its cycle seed there |
| 13 | transcripts | count `*.jsonl` in the session dir | pass-only | informational (N transcripts / fresh project) |
| 14 | store-resolution | synthetic — `resolve_store` raised (measured raise classes: EACCES PermissionError, no-sqlite3 ImportError) | FAIL | Resolver error: `<detail>` (dependent probes skip) |
| — | held-lock | a non-blocking flock attempt on `locks/*.lock` files | notes[] only | "N HELD lock file(s) — another process holds the plane" (lock FILES are the normal resting state — counting them nagged healthy stores; review F1) |

**Verdict policy:** FAIL = the product cannot function in this environment (crashes today with a
traceback or a bare refusal); WARN = an already-shipped, already-labeling degradation. Sub-3.8
interpreters get a SyntaxError before `python-floor` can run — a documented boundary, not a
silent case.

## §3 Integrations

1. **`cm_ops.cmd_doctor` (753-763)** — **wraps `_ctx(args.project)`** (cm_ops.py:755; review F3):
   a resolution raise falls through to `run_checks` with the `store_resolution_error` sentinel.
   **Mode/rc contract (review F5):** the sentinel path emits the preflight envelope as **JSON**
   in `--json` mode (stdout purity — smoke.py:2543-2545 pins single-dict stdout) and the human
   table + **exit 2** in text mode; otherwise `cmd_doctor` **returns 2 when the fresh verdict
   has any FAIL, 0 otherwise** — matching `preflight.py`'s own main. Normal path: lazy
   `preflight.run_and_cache(ctx)` (fresh, doctor forces freshness); text mode appends the
   PRE-FLIGHT section after `doctor_report`; `--json` mode adds the `preflight` key (no `at`).
   NOT inside `store_context.doctor_dict` — store_context stays preflight-free and the
   twice-run doctor pin stays byte-stable. `--repair-permissions` unchanged. Cost +~100-300ms
   (explicit command; timeouts tight). **The first doctor run mints the state file** (the
   mutator's mkdir + atomic write) — accepted and noted in cm-doctor.md (review F10; the cache
   write is the point).
2. **`session_beacon.py`** — reads the cached verdict only; **FAIL-only advisory** (warns would
   nag a benign, already-degrading condition every session): one line ≤60 est tok,
   `"consolidate-memory pre-flight: N environment check(s) failed (dreams will fail here) — run cm doctor for the fixes."`; warns/pass/absent/stale (>7d TTL) → silent; failure posture
   unchanged (silent + rc 0). **Placement + precedence (review F4, amend-2):** the verdict is
   read **between the `auto_memory_enabled` gate and the `cross_project_allowed` gate**
   (session_beacon.py:255-256) — disabled-auto-memory envs stay silent (unchanged); a fresh
   FAIL **supersedes** the unenrolled and behind advisories and is **NOT quieted by
   `beacon_snooze_until`** (env-broken is not absorption-nag — the docstring silence rules say
   so explicitly); total stdout stays ≤1 line in every co-state. The post-fix nag window is
   bounded by the next fresh run (dream Phase-0 re-probes past 1h) or the 7d TTL — accepted,
   pinned by the 8d-stale fixture.
3. **`memory_status.py`** — **wraps `build_context`** (review F3): a resolution raise falls
   through to the same sentinel path as doctor. **Mode contract (review F5):** in
   `--json`/`--seed` modes the sentinel emits the preflight **envelope as JSON** (no table, no
   cue; the cycle record is absent), preserving the stdout-purity contracts; in text mode the
   human table + exit 2. **Seeding is mode-gated (review F5):** the preflight runs + caches
   only on the record-producing/report modes (`--json`, `--seed`, the plain read) — read-only
   modes (`--triage`/`--sections`/`--snapshot`/`--diffs`/`--audit`) stay write-free and keep
   the audit path's "never the native plane" invariant. Otherwise `run_for_project` guarded
   (never breaks a dream);
   `record["preflight"]` **always seeded** ("ran and found nothing" honesty); the human report
   prints a PRE-FLIGHT section gated on **fails non-empty only** (review F6 — warns surface in
   the doctor table, the record's `preflight` key, and `--json`; a no-git dream must NOT gain a
   nag section).
4. **Schema lockstep (all five together — the law):** `Preflight` TypedDict (total=False:
   `at`, `fails`, `warns`) + `preflight` key in `CycleRecord` (memory_status.py:569-590) + the
   `validate_cycle_record` dict-key tuple (3183-3185) **plus is-a-list descents for
   `fails`/`warns`** (review F8, the dream.beats style at 3195-3199) + the SKILL.md schema fence
   + the smoke lockstep sweep (tests/smoke.py:1092-1162, top-level keyset equality + nested
   sweep).
5. **Renderers** — `render_dashboard.py`: one red line after IDENTITY when `fails` non-empty
   (presence-check; legacy records skip). `render_html.py`: `"preflight"` added to `_EMBED_KEYS`
   (70-75) — the embedded-record inspector shows the raw block; no template JS change.

## §4 Verification — the pin list

New `# ── v0.4.16: environment PRE-FLIGHT (docs/env-preflight.spec.md) ──` section; the
red-first-banner discipline (smoke.py:3959-3960): each pin documented as failing on pre-fix code.

In-process (stubbed injectables): sqlite-module importer stub → verdict not crash · sqlite-floor
3.20/3.24 boundary · roundtrip executes the LIVE schema (monkeypatched `SCHEMA_SQL` breaks it —
the drift discriminator) + fake-module `OperationalError` on ON CONFLICT (dialect proof) +
real-EACCES chmod-0o500 root-guarded (the 11308-11316 precedent) + flock-probe arm ·
posix platform param + `sys.modules["fcntl"] = None` (the 7841-7855 precedent) + the cygwin
branch · plugin-self bare dir vs real root + sibling-set equality against the live listing ·
git skip-cascade with which/run stubs (incl. a non-UTF-8 output stub under a C-locale env —
`errors="replace"` decode, the `memory_status._run` precedent at 2206-2208; advisor F10.4) ·
tempdir statvfs+64KB-write FAIL · native-mem-dir EACCES mkfile stub + disabled-auto-memory skip ·
sentinel-path probe policy (ctx-free probes run, #5/#7 skip).

Subprocess (hermetic HOME; the `_beacon81` env pattern at smoke.py:5138-5141): `preflight.py`
healthy → exit 0 + envelope shape (`ok/at/checks/notes`, per-check `id/status/label/fix`) ·
`TMPDIR` unwritable env → exit 2 + tempdir fail (real injection; no PATH-manipulation precedent
needed) · **#14 fixture = a chmod-0o000 config root** (root-guarded, the 11308-11316 style):
`cm doctor` → rc 2, the #14 row with the PermissionError text, **no traceback**; the same for
`memory_status.py --json` → single-dict stdout purity + rc 2 (review F3/F5) · **reachability
pins (review F1, amend-2):** (a) **sqlite-floor env** — sqlite3 present, version stubbed <3.24
→ `resolve_store` succeeds → `run_and_cache` writes the state file via the mutator; the beacon
subprocess then prints the one line; (b) **no-sqlite3 env** — `sys.modules["sqlite3"] = None` →
`resolve_store` raises ImportError → sentinel yields #3 FAIL + #14, no cache write, beacon
subprocess **SILENT** (the documented resolution-failure boundary — pinned as silence, never as
a false-green line).

Integration: doctor PRE-FLIGHT shape + twice-run equality (extends 7056-7063; `at` excluded) +
`--json` `preflight` key shape + rc 2-on-FAIL · beacon verdict pins in the 5122-5188 harness
(fails → exactly one line ≤60 tok; warns/pass/8d-stale/garbage/non-dict-fails → silent rc 0) +
**co-state fixtures** (review F4: preflight-FAIL-cached + behind → exactly the preflight line;
stale-cache + behind → exactly the behind line; FAIL + snooze-stamped → still the preflight
line; disabled-auto-memory + FAIL → silent) · cache merge-write (a model-owned key survives the
write; the state-key shape `{at, fails[], warns[]}`) · seed-embed (present with verdict; absent
on legacy) · **no-git Phase-0 human output byte-identical to pre-feature** (review F6's
discriminator) · **renderer pins** (review F10: `"preflight" in _EMBED_KEYS` extends the
11632/11647 whitelist sweep; dashboard red line exactly once when fails non-empty,
byte-identical output when empty/legacy) · lockstep sweep row + the is-a-list descents ·
genericity A5 on all new strings (fix lines use generic placeholders where examples appear) ·
**3.7-parseable discipline** (a compile check against a 3.7 grammar gate or a pinned
no-walrus/pos-only-param source scan; review F11).

## §5 Ship shape

Single feature branch → PR → user merges → `release.sh` pre-bump (CHANGELOG `[0.4.16]` entry
authored first; plugin.json 0.4.15→0.4.16; the complete version sweep) → `--expect patch
--finalize` (the harness hygiene closes the branch surface). Backward-compatible: additive
script + additive record/state/dict keys; legacy records render; no hook/manifest/command
contract changes. Doc sweep: SKILL.md (Phase-0 line + fence), harness-map.md (matrix + fix
lines + verdict policy + cache/TTL contract), README Requirements, cm-doctor.md + cm-connect.md
step 1 (incl. the doctor-mints-the-store note), CLAUDE.md/AGENTS.md layout, CHANGELOG.

## Evidence ledger

Every citation was verified against the live tree during the 2026-09-05 exploration (three
scouts + the design pass) and re-verified by the adversarial review (27/29 byte-accurate; the
two slips — cm_ops.py:756→755 and the 1505-1519 in-process vs 5138-5141 subprocess pattern —
corrected above). The clean-room install simulation (§1.2) is the 2026-09-05 deployment sanity
check. Advisor pass 2026-09-05: 11 findings (F1-F11), folded as amend-1. Adversarial review
2026-09-05: 11 findings (1 HIGH · 5 MED · 5 LOW), folded as amend-2 — the HIGH (F1's
direct-write reachability contradiction) re-folded to the one-writer routing; the reviewer's
strongest attack failed against the at-exclusion + fresh-run rendering rule.
