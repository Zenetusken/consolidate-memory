# Group lifecycle completion (v0.4.11 spec)

**Design-of-record for the three open items the 0.4.10 fleet dogfood named.**
Status: draft for advisor pass → adversarial review-to-zero → implementation.

## 1. Context (measured, 2026-09-04; amend-5 — + R-N1a) final)

The v0.4.10 fleet dogfood shipped the group layer and surfaced three gaps:

1. **`cm group delete` does not exist.** The leftover `admins` group (0 members,
   CLI-testing residue) cannot be removed — the registry op `group_delete`
   exists but no command reaches it. Deleting a group whose name is cited by
   live facts has a fail-closed consequence the command must surface, not
   hide: the facts' `recipients:` resolves to nobody → silent narrowing
   (acceptable per the review's D analysis, but it must be SAID).
2. **The recreation guard has no re-confirm affordance.** The guard fired
   correctly during the dogfood ("recipients: [fleet] predates the current
   group — re-confirm or re-point") but the CLI offers no gesture for
   re-confirming: the operator hand-bumped `content_modified`. The gesture
   must exist, be explicit, and be visible.
3. **The pull-side recreation guard is unshipped** (the tracked fast-follow):
   the writer refuses re-pointing, but a fact that PREDATES a recreated group
   (authored against the old identity) still DELIVERS to the new membership
   on pull. Delivery-time protection is the guard's other half.

## 2. The changes

### 2.1 `cm group delete <name> --apply --confirm delete-group-<name>`

- Journaled `group_delete` (the op kind already ships) + the membership rows
  cascade (the op does both). The members' group-fact mirrors are NOT revoked
  by delete — the facts' `recipients:` simply stops matching (silent
  narrowing); **the command prints the citation count first**: "N fact(s)
  cite this group (X, Y — they will deliver to nobody; re-point or forget
  them first)" — plan-first, delete on confirm.
- Refuses when the group has members: "remove M member(s) first
  (`cm group remove`)" — a populated group's deletion is a mass-revoke
  decision; deleting should be a deliberate two-step, never a cascade
  surprise. **The refusal prints the member project_ids (review 6):**
  add/remove address LOCAL stores by path; a registry-only (remote-machine)
  member cannot be removed through the CLI today — the ids make the dead-end
  visible, and the spec records the phantom-path convention (a local path
  for the remote project) as the documented workaround. Stated too: each
  `group remove`'s mirror revoke precedes and is independent of the delete
  decision — the two-step protects the delete, not the revoke.

### 2.2 The re-confirm affordance: `cm canonical upsert --repoint`

- `--repoint` explicitly authorizes `recipients:` that predate the current
  group identity. Without it the guard fires as today. With it, the writer
  accepts and re-stamps `content_modified` to now (the carve-out below —
  a body-changing write does this by convention, the flag makes it
  unconditional) — the re-confirmation becomes durable text, not a
  side-effect.
- The guard's error message names the flag: "…re-confirm (--repoint) or
  re-point".
- `/cm-share` passes `--repoint` automatically when the user confirms the
  narrowing against a group (the confirmation IS the re-confirmation) — the
  agent-driven path never needs the flag hand-typed.
- **`--repoint` force-restamps `content_modified` (review 2):** ADR 011
  keeps the stamp on metadata-only restamps, so a gate-only flag would leave
  the predating stamp on disk and the pull-side skip would withhold the
  re-confirmed fact forever. The repoint path is a named carve-out: when the
  authorization fired, the writer stamps `content_modified` to now regardless
  of body-change. Safe: the evidence clocks key on `body_hash`, never
  `content_modified` (sync_global.py:1996-2004).
- **`--promote` threads the authorization (advisor 3 / review 3):** promote()
  reaches the guard through the same `upsert` gate, so a Phase-4 re-scope of
  a predating local fact would hard-refuse with no gesture. `allow_repoint`
  threads promote → upsert AND `sync_global.py --promote` gains a `--repoint`
  flag — the surface the skill's Phase-4 actually invokes (the in-process
  param alone is dead code on the documented path). `cm resolve
  --promote-local` reaches the same guard (review N4): thread the flag there
  too, or its refusal message points at the `cm canonical upsert --repoint`
  workaround.

### 2.3 The pull-side recreation guard

- In the shared enumeration (`_admissible_records` — the single source for
  pull, the beacon, fleet_staleness, and gc: advisor 4; never a per-consumer
  re-admission), delivery withholds **per-recipient** (review B): a fact is
  skipped for a member only when the member's OWN cited groups are all
  recreated-after-the-stamp — a member of a FRESH cited group still receives
  it even if a sibling cited group is stale (whole-fact skip starved
  entitled members and then deleted their legitimate mirrors via the reclaim
  extension). The writer's whole-fact refusal stays as-is (there the TEXT is
  wrong, and the author fixes it). Applies to the bridge enumeration AND the
  same-domain narrowing path. A fact with no `content_modified` passes (the
  writer always stamps one); the stamp-less draft is a known pass — the
  guard's threat model is accidental re-pointing by well-meaning agents, not
  adversarial file tampering (review's strongest attack, failed; stated, not
  hidden).
- **Registry-degrade = guard-inert (advisor 4):** a registry the guard
  cannot read passes everything — a fail-closed skip on a lookup error would
  break hermetic/fixture pulls. The `created_at` map is HOISTED — one
  `SELECT name, created_at FROM groups` per enumeration (the
  `_project_memberships` pattern), fetched AT ENUMERATION TOP with the
  memberships read (the same-domain narrowing loop runs before the bridge
  block opens its conn — a fetch at the bridge's conn site arrives after
  the path that needs it first), and its process-global cache resets in
  hermetic pins.
- **Mirror lifecycle (advisor 1-2 / review 1 — the mechanism RE-SOURCED):**
  a guard-skipped fact's EXISTING mirror must not sit invisible and
  unreclaimable. The frozen scan cannot see skipped facts through its
  admitted-only `canon_fm`, and the orphan classifier would mislabel the
  foreign geometry — so gc re-sources: for a mirror not in the admitted set,
  DECODE its key, test the canonical's DISK liveness via `_source_facts_dir`
  for the decoded home domain, and classify alive-but-inadmissible as
  **FROZEN with a carried reason token** — orphan yields to frozen whenever
  the canonical file is disk-alive (the foreign alive-canonical mirror never
  reaches the orphan branch). The reason token drives the render copy —
  `dropped-stack` / `guard-stale` (the fact predates the group) /
  `not-entitled` (member removed) — the hardcoded "dropped stack" copy is
  replaced with conditional text (review 5: the display must not lie).
  Reclaim signal (review N1): the FROZEN branch compares the mirror against
  the disk-alive canonical semantically (the revoke precedent's clean-vs-
  edited test, cm_ops.py:2132-2147). The ORPHAN branch has no canonical to
  compare — its signal is the mirror's own `global_ref_body` lineage stamp
  vs its current body hash (the carry-logic signal, sync_global.py:1996-
  2004): matching → clean → delete, diverging → quarantine. **This CHANGES
  the precedent's canonical-gone arm** (which blind-deletes today,
  cm_ops.py:2127-2128) — stated, not borrowed. Boundary, named: the
  body-hash test cannot see frontmatter-only edits on an orphan — accepted
  lossiness (such an edit goes with the clean verdict); the retention-erring
  property belongs to the QUARANTINE branch (a wrongly-quarantined clean
  orphan survives a re-run). A mirror with no `global_ref_body` (pre-v0.1.78,
  never refreshed) has no signal — defaults clean. Re-pulls after the cause
  clears (owner re-points / membership restored). This also closes the
  v0.4.10 remote-member gap.
- **In-lock re-verify re-sources (review N2):** the under-lock re-check
  re-runs the RE-SOURCED predicate (decode → disk-liveness → admissibility
  + relevance) for every class — the admitted-only `canon_fm` lookup would
  KeyError on guard-stale names inside the mutate, and a name whose cause
  cleared (an owner's --repoint landing between scan and lock) is skipped.
  The canonical files read for the frozen-branch semantic compare inside
  the mutate are pinned into `expected_revisions` (the flip is bounded —
  clean↔edited — but a mid-transact canonical change must not silently
  flip the verdict).
- **Self-heal corner (advisor 7, pinned):** a body edit that arrives
  stamp-less (the fresh-authoring convention) re-delivers WITHOUT
  `--repoint`; an edit carrying the old stamp is refused by the writer
  guard. Only the flag is the durable re-confirmation.

## 3. Invariants

- Single writer: `--repoint` changes the guard's gate inside
  `canonical_ingress.upsert` AND adds the named restamp carve-out
  (`content_modified` → now when the authorization fired — the evidence
  clocks key on `body_hash`, never on the stamp); the journaled transact is
  untouched. The populated-group refusal is an affordance, not an invariant
  (a replayed journal op cascades unconditionally, by design).
- Fail-closed: a deleted/recreated group's stale citations deliver to
  nobody — never to the wrong membership.
- Backward-compatible: new flag, new command, an enumeration skip on a
  previously-undetectable drift case (facts that would have mis-delivered —
  the guard removes a mis-delivery, which is a fix, not a break) → **patch**.

## 4. Verification (each pin fails on pre-fix code)

- `cm group delete` on an empty group: rows + memberships gone, journaled;
  on a populated group: refused naming the member count; the citation-count
  line prints for facts citing the name (including a legacy cross-domain
  citation).
- `upsert --repoint` accepts a predating recipients list; without it the
  guard still fires; the error names `--repoint`; the promote path carries
  the authorization through.
- The pull-side guard: a fact whose cited groups ALL postdate its stamp is
  NOT delivered to the member (neither bridge nor same-domain narrowing); a
  member of a FRESH cited group still receives it (per-recipient); a
  re-pointed fact delivers; **a guard-skipped fact's existing mirror renders
  FROZEN with its reason token and `gc --apply` reclaims it (clean deleted,
  edited quarantined — asserted on BOTH branches AND BOTH geometries: the
  bare-stem same-domain decode and the namespaced foreign decode, with the
  FROZEN label and non-orphan classification named in the fixture)** — the
  stranding pin;
  a stamp-less edited fact re-delivers (the self-heal pin); the PR-#194
  interplay pin is re-cast as an invariant toggle (a skipped fact's mirror
  present + a stale same-stem manifest row → the beacon stays silent,
  asserted with and without the skip — the naive pre-fix fixture cannot
  even construct the premise). The promote-repoint pin drives the CLI
  surface (`--promote --repoint`), not the in-process param.
- Full suite per round + one review agent per PR; the finder re-verifies.

## 5. Ship shape

Backward-compatible → **patch (0.4.11)**; cuts after `main` @ 6be1a7c
(PR #194, the beacon fix, is already merged — no wait required).
