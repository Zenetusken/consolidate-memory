# Track D: global-store write atomicity + /tmp seed-path hardening — spec

**Provenance:** the 2026-07-05 four-lens audit's F-P2-7 (global-store write atomicity/
locking) and F-P2-8 (`/tmp` seed-path hardening), explicitly deferred to Track D by
`docs/audit-hygiene-remediation.spec.md`'s Non-goals ("`O_EXCL` would break the
deterministic re-seed the cycle contract relies on … needs a design pass").

**Threat model, stated up front (this scopes everything below):** consolidate-memory is
a single-user personal memory tool. The realistic concurrency case is the user running
Claude Code in more than one project at once, each independently dreaming and promoting
facts to the same shared global store (`~/.claude/memory`) within a similar window — not
a hostile multi-tenant host. Sized accordingly: fix what's cheap and unconditionally
correct; document, don't build subsystems for, what's rare and already recoverable.

## Scope

| ID | Finding | File(s) | Fix |
|---|---|---|---|
| D-1 | the 2 real `GLOBAL`-targeting writes aren't atomic (torn write visible to a concurrent reader) | `sync_global.py: promote()`'s canonical write, `_record_provenance()`'s 2 writes | write-temp + `os.replace()` |
| D-2 | two concurrent `_record_provenance()` calls on the same canonical can race (last-writer-wins on its `projects:` list) | `sync_global.py: _record_provenance()` | accept + document (recoverable) — no lock subsystem |
| D-2b | **(Gate-1 finding, not in the original audit)** two concurrent `promote()`s to the same NEW `canon_name` race check-then-act on `canon_path.exists()` — the loser's ENTIRE fact is silently destroyed in both stores, not just a dropped list entry | `sync_global.py: promote()` | `O_CREAT\|O_EXCL` at the actual write, abort-and-ask-to-retry on `EEXIST` |
| D-3 | `--seed`'s write is plain `write_text` (world-readable window), inconsistent with `--snapshot`'s already-hardened write | `memory_status.py: run()` | route through the existing `_write_private` |

**Bonus overlap with task #29 (the standalone `encoding=` fix, not part of this spec):**
`_record_provenance()`'s 2 writes (`sync_global.py:741,747`) are on BOTH lists — they
currently omit `encoding=` (#29's finding) AND aren't atomic (D-1). `_atomic_write_text`'s
signature defaults `encoding="utf-8"`, so D-1's refactor closes the `encoding=` gap at
these 2 sites as a side effect; #29's remaining, actually-standalone scope after D-1 lands
is just `extract_signals.py:267` and `memory_status.py:1827` (2 sites, not 4). Land D-1
before #29 (or fold these 2 sites into D-1's own PR) so #29 doesn't touch lines D-1 is
about to rewrite out from under it.

## D-1 — atomic writes to the global store

**Current (verified against the actual call graph — corrected from an earlier draft of
this spec, which wrongly counted `_ensure_index_pointer`/`_remove_index_pointer`'s
writes as global; both always take `store = project_store(project_dir)`, a PROJECT's own
local store, in `run()`, `promote()`, and `gc()` alike — never `GLOBAL`).** `GLOBAL`
(`~/.claude/memory`) has no index file of its own; `global_facts()` scans it directly.
The only writes that land IN `GLOBAL` are:
- `promote()`'s canonical write: `canon_path.write_text(local_text, encoding="utf-8")`
  (`canon_path = GLOBAL / f"{canon_name}.md"`) — the one-time hand-off of a
  project-authored fact to canonical status.
- `_record_provenance()`'s two writes (`p = GLOBAL / f"{name}.md"`) — appending the
  calling project to the canonical's `projects:` frontmatter list, on every promote/pull
  that touches an existing canonical.

Both are bare `write_text(...)` — open+write+close as separate steps. A crash mid-write,
or a concurrent reader opening the file in that window, can observe a truncated/partial
canonical fact — the one file every mirroring project depends on for that fact's content.
(`promote()`'s own docstring already flags the multi-step sequence as "not
crash-atomic … but a completed call never does" leave partial state — this item hardens
the individual writes the sequence is built from; it doesn't change that framing.)

**Change.** Add one helper, `_atomic_write_text(path: Path, text: str, encoding: str =
"utf-8") -> None` in `sync_global.py`: write to a temp file in the **same directory**
(`path.with_suffix(path.suffix + f".tmp{os.getpid()}")`, so the later `os.replace` stays
on one filesystem — no cross-device rename failure), then `os.replace(tmp, path)`.
`os.replace` is atomic on POSIX and Windows (stdlib, since 3.3) — a concurrent reader
always sees either the fully-old or fully-new file, never a partial one. Route the two
`GLOBAL`-targeting writes above through it (`canon_path.write_text` in `promote()`, both
writes in `_record_provenance()`). Leave every other `write_text` in this file as-is —
they target a project's own local store, not the shared one, and are out of this item's
scope (`GLOBAL`-only, matching the audit finding's own title).

**Acceptance.** A sabotage-style test: interrupt `_atomic_write_text` after the temp
write but before `os.replace` (monkeypatch or a crafted failure) and confirm the
destination file is untouched (still holds the pre-write content, never a partial write).
A second test confirms normal operation still produces the expected final content.

## D-2 — the lost-update race (accepted, documented gap)

**Current.** Two concurrent operations touching the SAME canonical fact — e.g. two
different projects both promoting/pulling around the same fact at overlapping moments —
each go through `_record_provenance()`'s read-modify-write of that canonical's
`projects:` list. D-1 makes each individual write atomic, but the read-modify-write
*sequence* isn't mutually exclusive: the second writer can still compute its new
`projects:` list from a read that predates the first writer's append, and its
(atomic) write overwrites the first writer's addition — a dropped provenance entry (that
project silently undercounts as a holder of the fact).

**Why this is accepted, not fixed with a lock.** The window is milliseconds wide
(promotes/pulls fire at dream/arc boundaries, not continuously) and the failure is
narrow and non-corrupting: the canonical fact's BODY is untouched, only one entry in its
`projects:` provenance list is missed — that project still has a correct local mirror,
still functions identically; the only cost is `_holders()`/the network view briefly
undercounting one edge, self-correcting the next time that project's own dream promotes
or pulls again (a fresh `_record_provenance()` call re-adds it). A lock to close this
needs either OS advisory locking (`fcntl` — **banned** by this repo's own portability
guarantee, no POSIX-only modules) or a hand-rolled directory/sentinel lock with
staleness detection (how old counts as abandoned? a slow legitimate holder vs. a crashed
one? clock skew across two machines sharing a synced home dir?) — exactly the kind of
heuristic-guessing-game this repo already burned multiple Gate-2a rounds on for the
secrets firewall. Not worth it for a rare, self-healing race on a non-load-bearing list.

**Change.** None (code). Document the gap in `_record_provenance()`'s docstring and in
`harness-map.md`'s cross-project model section, so it isn't rediscovered as a surprise
later.

**Acceptance.** The docstring/doc language is present; no new test (there is no new
behavior to pin — this is a documented non-fix).

## D-2b — the `promote()` create-create race (Gate-1 finding: fix, don't accept)

**Current.** A single-agent Gate-1 review of this spec (before any code was written)
found a second, more severe race than D-2, missed by the original audit: `promote()`
line 973 checks `reconcile = canon_path.exists()`, but the actual write is 60 lines
later at line 1034-1035 (`if not reconcile: canon_path.write_text(local_text, ...)`) —
an unguarded check-then-act gap. If two DIFFERENT projects concurrently `promote()` two
DIFFERENT local facts to the same NEW `canon_name`, both processes read
`reconcile=False` (the canonical doesn't exist yet for either), both pass Guards 1-5
(Guard 5 — the body-mismatch refusal — only fires `if reconcile`, so it never engages
for either process here), and both reach the unconditional write: whichever runs last
silently wins, and the loser's fact is not just missing a provenance entry (D-2's case)
— **its entire body is gone**. Worse, line 1037 re-reads `canon_path` (now holding
whichever text won) and line 1042 rewrites the CALLING project's own local copy as a
mirror of that (possibly-not-theirs) content — the loser's original fact is erased from
**both** stores, silently, with no error and no partial-state indication. This is
exactly the silent-discard class Guard 5 exists to prevent, but Guard 5 is keyed on
`reconcile`, which this exact race guarantees is wrong for both processes.

**Why this is fixed, not accepted like D-2.** D-2's "no lock needed" reasoning doesn't
transfer: D-2 is a rare, self-healing, non-corrupting undercounts-by-one on a list.
D-2b is silent, total, unrecoverable data loss of a fact — a real violation of this
project's own no-silent-data-loss posture, not a cosmetic gap. And unlike D-2, closing
it does NOT require a lock or staleness detection: `O_CREAT|O_EXCL` on the canonical
create is a lock-free atomic primitive purpose-built for exactly this "am I the first
creator" question.

**Change.** Replace the unconditional write at line 1034-1035 with an atomic
create-exclusive attempt. (Gate-1 follow-up review caught a bug in this section's first
draft: attempting `O_CREAT|O_EXCL` directly against `canon_path` — write the fd, then
close — creates the destination EMPTY first and fills it as a separate step, reopening
the exact torn-read window D-1 was written to close, at the one call site D-1 names.
Fixed by writing the FULL content to a temp sibling first, THEN atomically linking it
into place — content and existence become visible together, in one step, to any
concurrent reader.)

```python
if not reconcile:
    tmp = canon_path.with_suffix(canon_path.suffix + f".tmp{os.getpid()}")
    tmp.write_text(local_text, encoding="utf-8")   # full content, NOT yet at canon_path
    try:
        os.link(str(tmp), str(canon_path))   # atomic: creates canon_path fully-formed,
                                              # or raises FileExistsError leaving it untouched
    except FileExistsError:
        print(f"promote: another process just created the canonical '{canon_name}' concurrently — "
              "refusing to risk a silent clobber. Re-run promote — it will now correctly "
              "reconcile against the canonical that landed.", file=sys.stderr)
        return 1
    finally:
        tmp.unlink(missing_ok=True)
```

Verified directly (not just accepted from review): `os.link` onto a non-existent
destination atomically creates it with the temp file's full content already in place —
no reader can ever observe an empty-then-filled window, since the inode's content was
complete before the link existed. `os.link` onto an EXISTING destination raises
`FileExistsError` with the destination's content completely untouched — confirmed by a
direct two-writer simulation (a "winner" links its content in, a "loser" then attempts
`os.link` onto the same path and gets `FileExistsError` while the winner's content is
provably unchanged afterward).

**Tradeoff, noted explicitly (not silently swapped):** `os.link` needs hardlink support
— POSIX-solid, but marginally less universal than `os.replace` (D-1's primitive), which
works on virtually any filesystem including ones without hardlink support. This is the
right call for D-2b specifically because it needs BOTH atomicity AND "am I first"
exclusivity together, which `os.replace` alone can't provide (unconditional clobber —
the exact bug this item exists to fix) and raw `O_EXCL` alone can't either (the
torn-read window above). D-1's plain `os.replace`-based `_atomic_write_text` remains the
right tool for its own two call sites (`_record_provenance`'s writes and any other
GLOBAL overwrite of an already-existing file), since those don't need create-exclusivity
— only D-2b's create-or-detect-collision case does.

This is the ONLY call site that changes. Deliberately NOT an early atomic claim at line
973 (the alternative considered and rejected): claiming there would mean Guards 1-5 can
still fail afterward, and 4 of their return points would then need to unlink the
just-claimed placeholder file before returning — real surgery across the guard
sequence, with its own risk of a forgotten cleanup path leaving an orphaned empty
canonical behind. Attempting the atomic create only at the existing write point keeps
the change to one call site: on the `EEXIST` path, NOTHING has been written yet by this
process (no canonical, no provenance, no mirror, no index change — verified fresh by
re-reading lines 932-1035: everything before the write is read-only or an idempotent
`mkdir(exist_ok=True)`; the only prior side effect is Guard 4's advisory stderr NOTE,
which is harmless) — the caller's local fact is completely untouched, so a clean
abort-and-retry is fully safe, and a retry takes the pre-existing, already-tested
reconcile path (`canon_path.exists()` now correctly evaluates `True`, Guard 5 correctly
engages — it was unreachable before, keyed on the stale `False` — and does the safe
thing by default: refuse with a clear message, never silently pick a side).

**Acceptance.** A test simulating the race directly — pre-create `canon_path` with
"winner" content AFTER the test computes what `reconcile` would see as absent (i.e.
create it in the window between `promote()`'s own `reconcile` check and its write; the
simplest harness is a `canon_path.write_text(...)` from the test itself, timed via a
monkeypatch on `os.link` that writes the file then calls through, or by pre-seeding
before invoking `promote()` with `reconcile` forced) — confirms: (a) the process refuses
with a clear stderr message and return code 1, (b) the project's own local fact (`src`)
is byte-identical to before the call — not converted to a mirror, not deleted, (c) the
pre-existing "winner" canonical content is untouched, (d) no `.tmp<pid>` file is left
behind (the `finally: tmp.unlink()` fires on both the success and `FileExistsError`
paths). Sabotage-verify: temporarily revert to the unconditional `write_text` and
confirm this test fails (observes the silent clobber) before the fix is in place.

## D-3 — `--seed` write hardening

**Current.** `memory_status.py`'s `run()`, the `--seed` branch:
`Path(path).write_text(json.dumps(seed_record(ctx), indent=2) + "\n", encoding="utf-8")`
— a plain write to a deterministic, world-writable-directory path
(`cycle_seed_path()`, under `tempfile.gettempdir()`). The sibling `--snapshot` branch,
writing to the same directory via `audit_snapshot_path()`, already goes through
`_write_private()` (owner-only 0o600, set atomically via `os.open`'s mode arg — no
write-then-chmod TOCTOU window). `--seed`'s inconsistency is the actual gap: a narrow
window where the cycle-seed file — which can hold recall-candidate fact text — is
briefly at the process's default umask-derived permissions (typically world-readable)
before nothing ever tightens it.

**Change.** Replace the `--seed` branch's `Path(path).write_text(...)` with
`_write_private(Path(path), json.dumps(seed_record(ctx), indent=2) + "\n")` — same
helper `--snapshot` already uses, so both temp-file writers share one hardened path
(single-source, avoids the two-copies-drift class this repo already guards against
elsewhere via the `_is_reserved_stem`/`slug_for` reimplementation-pin precedent).

**Non-goals for D-3 (deliberate):** no `$XDG_RUNTIME_DIR` fallback, no per-boot-suffix
naming. The symlink-attack threat `_write_private`'s O_CREAT (without O_EXCL) doesn't
fully close requires a hostile *other local user* pre-planting a symlink at the exact
deterministic path — the same class of threat this repo already downgraded elsewhere
this cycle (the pentest's `/tmp` predictable-path finding, folded into this same Track-D
item rather than fixed standalone) as disproportionate for a single-user tool. If this
ever needs closing, `O_NOFOLLOW` on the open call is the one-flag fix — not built here,
not needed at this threat level.

**Acceptance.** A new test asserting the `--seed`-written file's mode is `0o600` — no
existing test currently pins `_write_private`'s mode for EITHER `--seed` or `--snapshot`
(verified: `grep -n "_write_private\|0o600" tests/smoke.py` → 0 hits), so this adds the
first one; write it to cover both call sites, not just `--seed`, closing that pre-existing
gap too rather than adding a second single-purpose test alongside it.

## Non-goals (deliberate, whole spec)

- **A lock/mutex subsystem** for D-2 — see above; explicitly rejected as disproportionate
  to the threat and a fresh source of stale-detection bugs.
- **`$XDG_RUNTIME_DIR` / per-boot suffix** for D-3 — see above.
- **The `read_text`/`write_text` calls missing `encoding=`** (Track-D's other open item,
  task #29) — a separate, mechanical, non-design fix; lands standalone, no spec needed.
  2 of its original 4 sites (`sync_global.py:741,747`) are subsumed by D-1's refactor (see
  the Scope table's overlap note) — #29's real remaining scope is the other 2.
- **`_write_private` itself gaining atomic-rename** — out of scope; `_write_private`
  already closes the permission race it targets (TOCTOU on chmod), and its callers
  (`--snapshot`, now `--seed`) write once per process invocation with no concurrent-
  reader-of-the-same-path scenario analogous to the shared global store's — D-1's
  atomicity concern doesn't transfer to it in the same way. If that changes, revisit.

## Rollout

- Branch `fix/track-d-write-atomicity` off main.
- One PR, full body; merge reserved.
- `CHANGELOG.md` gains a new top section: D-1/D-2b/D-3 are backward-compatible
  robustness fixes (no schema key, no flag, no manifest change) ⇒ **patch** per the
  versioning policy. D-2 is docs-only.
- Gate 2a: sabotage-verify D-1's atomicity test, D-2b's race test, and D-3's mode test
  (each must fail red against the pre-fix code before its fix lands).
