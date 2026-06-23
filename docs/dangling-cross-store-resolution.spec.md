# Spec — cross-store resolution for the dangling-link detector

**Status:** REVIEWED — ready to ship as v0.1.52 (spec-review to zero + 3-reviewer code-review, SHIP).
Track 2 of the "wikilinks recurrence" fix (Track 1 = the canonical de-link, already applied + verified).
**Bump:** PATCH (additive, backward-compatible — legacy call site + behavior preserved).

## Problem (measured)

`memory_status.dangling_links(auto_mem)` resolves every `[[target]]` against **only the single
store it is scanning** (`valid_link_targets(auto_mem)` = that one dir's `*.md` stems). But the
memory architecture is multi-store (project-local · global canonical `~/.claude/memory` ·
per-node mirrors) and cross-scope. Measured over `.consolidation-log.jsonl` cycles 11–16, this
produces a recurring **false-positive** class:

- **Class B — pending-pull up-link (false positive → fix this).** A fact links to a *real*
  user-global fact that is RELEVANT but budget-**held** (M1 near-budget) and so not-yet-mirrored
  into this node. The link dangles until the pull lands. Example:
  `cli-stdout-stderr-contract → [[typecheck-only-import-runtime-nameerror]]` dangled cycles 11–14,
  self-healed cycle 15 when the global fact was finally pulled. The target was valid the whole
  time — just not in the local store yet. Every intervening cycle paid a spurious "dangling" cue.

The contrasting class is a **true positive and MUST stay flagged**:

- **Class A — scope-incoherent down-link (true positive → leave flagged).** A user-global fact
  (mirrored everywhere) links DOWN to a project-local fact that lives in exactly one other node's
  store (`arc-end-qa → [[never-rm-job-applicator-state-dir-in-tests]]`). A project-local fact is
  **never pullable** into another node (recall is slug-scoped), so the link is genuinely
  unreachable from here. (Fixed separately in Track 1 by de-linking the canonical; the detector
  must still catch the *next* such down-link.)

## Change

`dangling_links(auto_mem: Path, global_dir: Path | None = None) -> list[str]`

When `global_dir` is provided **and exists**, the resolution set becomes
`valid_link_targets(auto_mem) | valid_link_targets(global_dir)`. A `[[target]]` present in the
**global canonical store** is *pending-pull* (it will mirror in on a future relevant `--pull`;
the M1 `held` count already surfaces unpulled relevants), so it is **not** counted as dangling.
A target absent from **both** local and global stems stays dangling — that set is exactly {a real
typo} ∪ {a sibling-project-local down-link}, both genuinely unreachable from this node.

**Callers — BOTH, or the false positive just migrates channels.** The dangling count is filled
in two places and SKILL.md guarantees they cannot drift (`SKILL.md:700` — "Phase-0
`maintenance.dangling` calls the SAME helper, so the two counts can't drift"). Both must pass
`global_dir = Path.home() / ".claude" / "memory"`:
1. **Phase-0 maintenance seed** — `memory_status.py:1307` `_dangling = dangling_links(auto_mem)`
   → `maintenance.dangling` (count).
2. **Phase-5 health fill** — the *model instruction* at `SKILL.md:696`
   (`dangling_links(auto_mem)` → fills `health.dangling_links`, the list rendered at
   `render_dashboard.py:596-601`). A Class B link is by definition **unfixable in Phase-5** (the
   target is a real global fact pending pull — nothing local to rewrite), so if `SKILL.md:696`
   keeps scanning local-only, the link survives remediation and renders on the dashboard even
   though `maintenance.dangling` dropped it. The Phase-5 **fix-suggestion** call at
   `SKILL.md:701-702` must likewise widen to
   `resolve_wikilink(name, valid_link_targets(auto_mem) | valid_link_targets(global_dir))`, else
   the model is told to propose a slug-drift fix for a clean pending-pull link (a phantom prompt).
   These are prose edits — no TypedDict/schema-pin friction (the smoke pin parses only the first
   `json` fence; this is Phase-5 narration).

## Why `local ∪ global`, not fleet-wide (sibling project stores)

Recall is **slug-scoped**: a project auto-recalls only its own store, and the only OTHER store it
can *pull from* is the global canonical. A sibling project's local store is never a pull source.
So a link to a sibling-project-local fact is dead-from-here and must stay flagged (the Class A
`never-rm` case). A fleet-wide resolver would falsely bless it as "exists somewhere" — papering
over a link a reader here cannot follow. `local ∪ global` is exactly "the stores this node can
recall-or-pull from."

**Load-bearing invariant Class A rests on:** the global canonical store holds **only**
user-global / stack-general facts — a project-local fact is **never** promoted into it
(enforced by `sync_global.promote`). So a sibling-project-local stem never appears in
`valid_link_targets(global_dir)`, and Class A stays flagged. If that invariant ever weakened,
the detector would go quiet on a real unreachable link; the Class A smoke test (test 2) is the
practical guard.

## Backward-compat

`global_dir` defaults to `None` ⇒ **identical to current behavior** (single-store resolution).
No existing caller is forced to change; legacy installs and the existing smoke fixture are
unaffected. This is why the bump is PATCH, not minor (no contract break, legacy records/behavior
intact per the versioning policy).

## Edge cases (considered)

- **Global store absent / empty (the common first-run path):** `memory_status.py:1307` passes
  `~/.claude/memory` **unconditionally**, and on a fresh machine that dir does not exist.
  `valid_link_targets` returns `set()` on a missing dir (`memory_status.py:448`), so the union
  collapses to the legacy local-only set — byte-identical to current behavior. Pinned by test 3.
- **`auto_mem == global_dir`** (a dangling check run *on* the global store itself): the union is
  idempotent (same stems). Not exercised by the Phase-0 caller (it runs on project stores), but
  harmless.
- **`resolve_wikilink` fuzzy-match now spans stores — intentional, not a risk.** This enables
  cross-store **date-drift healing** (local `[[typecheck-only-import-runtime-nameerror]]` resolves
  to a global `..._2026_05_28.md`), which is exactly what already resolves locally once the mirror
  is pulled — so cross-store resolution is just the post-pull steady state surfaced one step early.
  Accidental false-resolve risk stays negligible: `resolve_wikilink` requires a DISTINCTIVE base
  (≥12 chars) + exact-base equality, and an exact `in targets` hit short-circuits first.
- **`MEMORY.md` → stem `MEMORY` in the global targets:** a `[[MEMORY]]` ref resolves, consistent
  with the existing local behavior (`valid_link_targets` already includes it).

## Tests (smoke, zero-dep tmp fixtures)

1. **Class B fixed + backward-compat pinned (one fixture, two assertions):** a local store with
   `host.md` body `… [[only-in-global]] …`; a separate global dir containing `only-in-global.md`.
   - `dangling_links(local, global_dir=G)` → `[]` (pending-pull, resolved cross-store).
   - `dangling_links(local)` (no `global_dir`) → `["only-in-global"]` (legacy behavior unchanged).
2. **Class A stays a true positive:** a link to a stem present in **neither** store is flagged in
   **both** call modes (`global_dir=G` and `None`).
3. **Global-absent collapses to legacy (the first-run path):**
   `dangling_links(local, global_dir=<nonexistent path>) == dangling_links(local)`.

## Non-goals (scope discipline — advisor-flagged)

- **No new "pending-pull" field / report.** The M1 `held` count already signals an unpulled
  relevant global; a second channel is redundant surface.
- **No authoring-time down-link guard.** A guard that warns when a global/mirrored fact links
  DOWN to a project-local target is a worthwhile *additive follow-up*, not part of this change.
- **No fleet-wide (sibling-store) resolver** — see rationale above.

## Coexisting cross-store check (do NOT unify)

`sync_global.py:54 _nonglobal_wikilinks` already does a cross-store dangling check at **promotion**
time (`sync_global.py:874`), with deliberately different logic (`"." not in w` instead of
`extract_wikilinks`' fenced+inline stripping, no fuzzy `resolve_wikilink`, excludes `MEMORY`).
After this change there are two cross-store checks that answer **different questions**:
`_nonglobal_wikilinks` = "will promoting THIS fact strand `[[links]]` in every mirror?" vs.
`dangling_links` = "is this link reachable from THIS node?" They are not redundant — a future
maintainer must not "fix" one to match the other.

## Review outcome (3-reviewer code-review — SHIP, 0 confirmed correctness bugs)

The headline risk (a Class-B-only store reading `work=False` and skipping a needed Phase-1 pull)
was **REFUTED**: routing keys on `_noop_nonempty = len(commits)==0 and bool(fact_files)`, never the
dangling count, so a smaller count never skips the pull. Union logic, `global_dir=None` equivalence,
the chosen layer (call-site union, NOT inside `valid_link_targets`), the schema-pin, and the tests
all verified correct. Refinements applied from the review:

- **DRY:** the global-store path is now a module constant `memory_status.GLOBAL_STORE` (cf. the sibling
  `sync_global.GLOBAL`), referenced at all 4 sites (the new dangling caller + the `global_store_facts`
  seed ×2 + the network display) — no quadruplicated literal.
- **Drift-surface guard (closes the BLOCKER's residual):** two smoke pins assert SKILL.md's Phase-5
  prose still passes the cross-store args — `dangling_links(auto_mem, global_dir=` and
  `valid_link_targets(global_dir)` — so a future edit cannot silently drop one call site and
  reintroduce the Phase-0↔Phase-5 count drift.
- **Isolation guard (test 4):** a global-only dangling link (`[[global-ghost]]` living in the global
  store) must NOT leak into a local scan's output — `dangling_links` globs only `auto_mem`'s `*.md`
  for links; the global store contributes to the target SET only. Pins the invariant against a future
  "union the scan too" refactor that would surface other projects' dangling links here.
- **Hermetic test 3:** the missing-`global_dir` case uses a guaranteed-absent child of the test's own
  TemporaryDirectory, not an out-of-sandbox `/nonexistent` path.
