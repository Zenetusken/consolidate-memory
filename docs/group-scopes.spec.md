# Group scopes — the routed-link tier above the domain (v0.4.10 spec, amend-2)

**Design-of-record for operator-granted recipient groups.** Status: advisor
pass (11 findings) + adversarial review-to-zero (8 findings, 5 design attacks)
complete — all folded and re-verified green; SHIPPED in v0.4.10 (PR #192, with
the per-PR review round: 6 findings fixed and re-verified; the pull-side leg of
the recreation guard is the tracked fast-follow).

## 1. Context (measured, 2026-09-04)

The fleet segmentation into four isolated domains (`personal` / `docs` / `llm` /
`tools`) demonstrated the domain layer working exactly as designed — and measured
the two holes the user predicted:

- **Cross-domain facts have no home.** `advisor-pass-before-plan-approval` — a
  genuinely fleet-wide plan-mode preference — is invisible to 8 of 11 projects;
  giving it to them costs one canonical duplication per domain, forever.
- **No P2P / named-group link.** `python-ruff-mypy-gate` exists as TWO canonical
  copies (personal + tools) — the same stem in two domains, which the current
  stem-keyed mirror namespace cannot represent side by side (F2, below).

The domain remains the correct trust boundary (VLAN). What's missing is the
**routed link on top of it**: an operator-granted, journaled recipient set — the
governed successor to the v0.2.1 `authorized_pairs` layer, which v0.3.0 removed
because it was *self-service* (no grant, no journal, no admission). A group is
that layer with teeth.

## 2. The model

**Layer map:**

| Layer | Primitive | Routing |
|---|---|---|
| L0 | `project-local` | no replication |
| L1 | `stack-general` | content-routed (detected stacks) |
| **L1.5** | **`group` recipients** | **operator-declared recipient set — THIS spec** |
| L2 | `user-global` | broadcast to the fact's domain |

**Semantics (the narrowing principle):** `recipients: [<group>]` on a canonical
**narrows** its delivery, never widens it: on a `user-global` fact it delivers to
the group's members instead of the whole domain; on a `stack-general` fact it
delivers to members whose stacks also match (pure ANDs — F10 verified the
composition against `is_relevant`/`_fact_stacks`; `_plan_pull`/M1/holds key on
(name, status, cost) only, so ceiling accounting is untouched). A group may span
domains — that is the routed link between VLANs — but only the operator declares
it. The canonical's home is the authoring project's domain.

**P2P is a degenerate group** — a two-member group; no separate pair primitive.

**Confidentiality over the bridge (F5, ruled):** the group's operator grant IS
the confidentiality carrier — the admission override bypasses **only** the
domain-equality leg; `secret`-classified and `looks_secret` content is refused
on every path (unchanged), and a `confidential` fact crosses the bridge only to
explicit group members (the mirroring of the enrollment precedent, smoke-pinned).

## 3. Registry schema (additive)

```sql
CREATE TABLE IF NOT EXISTS groups (
    group_id    TEXT PRIMARY KEY,          -- 'g_<hash>' stable id
    name        TEXT NOT NULL UNIQUE,      -- operator-chosen slug (validate_group_slug)
    domain_id   TEXT NOT NULL,             -- the group's home domain (created there)
    created_at  TEXT
);
CREATE TABLE IF NOT EXISTS group_members (
    group_id    TEXT NOT NULL,
    project_id  TEXT NOT NULL,
    granted_at  TEXT,
    PRIMARY KEY (group_id, project_id)
);
```

**No `fact_recipients` table (F7).** `recipients:` is frontmatter-authoritative,
exactly like `scope:`/`stacks:` — the pull enumeration already holds each
canonical's frontmatter in hand, so the membership join
(`group_members` × project) + the parsed `recipients` token is free, and there
is no table to drift against the text (the ADR 023 precedent moved provenance
OFF markdown because it drifted; recipients does not need the reverse lesson).
A hand-removed `recipients:` line narrows delivery at the next pull by
construction.

**Journal op kinds (F8):** `group_upsert`, `group_delete`,
`group_member_add`, `group_member_remove` are added to `REGISTRY_OP_KINDS`
(control_plane.py:397-402) AND to the replay dispatcher (~1000-1080) in the same
commit — an op kind in only one of the two would leave an interrupted
`group_member_add` unrecoverable. Every group mutation rides the existing
`transact()` path.

**Upgrade skew (F8 + review F6/E, pinned per path):** fresh DBs get the tables
via `SCHEMA_SQL`; existing DBs via an idempotent `_migrate_schema` entry (the
`native_store_grants` precedent) behind a `REGISTRY_USER_VERSION` 4→5 bump.
`connect_registry` (control_plane.py:476-497) is the only writable connect;
every read surface uses `connect_if_exists` (569-583, read-only, no migrate).
The concrete split, and only this split, is legal:
- **migrate-first**: `cm group` CLI ops (open via `connect_registry` before
  validating) and every transacting writer.
- **degrade-to-empty**: the five §5-C gate sites' pre-lock reads, the beacon
  (its never-writes contract forbids migrating inside the SessionStart hook),
  `cm group list/show`, staleness — and the writer paths' pre-transact
  ENUMERATION, which runs before the transact that migrates.
The skew window is bounded: the first transact after upgrade migrates, so at
most one run per path sees no group facts. Stated, not left as "either".

## 4. Canonical frontmatter

```yaml
recipients: [admins]        # OPTIONAL — group slugs; narrows delivery
```

- Validated at the single writer (`canonical_ingress.upsert`): every slug must
  resolve to an existing group **whose home domain is the fact's domain** (a
  fact may not target a group born in another domain — the bridge is declared by
  the group's membership, not by the fact). Unknown group → `WriteRefused`
  naming it. `confidential` + recipients targeting foreign members → allowed
  (F5 ruling) and smoke-pinned.
- `recipients` joins `_CANONICAL_RESERVED_KEYS` (duplicate keys refuse rather
  than last-wins). Tokens parse with the existing `_parse_flow_list`; slug
  grammar is `validate_group_slug` (identifiers.py — the `validate_domain_id`
  shape, its own reserved set, length caps; F11).
- Empty/absent `recipients:` → today's behavior, unchanged.
- **Recreation guard (review D):** group rows are keyed by immutable
  `group_id`, but canonical frontmatter joins by NAME — a deleted group's
  recreated name would silently re-point old facts' delivery at the new
  membership (a silent re-grant, the one outcome ADR 008 exists to prevent).
  The writer and the pull enumeration therefore compare the group's
  `created_at` against the canonical's `content_modified`: recipients that
  predate the current group refuse with "recipients [X] predates the current
  group (created <ts>) — re-confirm or re-point". Smoke-pinned.

## 5. The mechanism section — the blast radius, named (F1/F2/F3/F4/F6/F9)

"Admission all apply unchanged" is false; the following sites change, each
verifiable:

**A. Namespace (F2 + review F2).** Same-domain mirrors keep the bare-stem key — unchanged, backward-compatible. **Cross-domain group mirrors get a namespaced key
`{domain}--{stem}.md`** (file name + index anchor + `_plan_pull` keys +
`_store_gaps` + beacon naming + GC + evict + `_inbound_links` all derive from
the record's (domain, stem) pair). This is what lets `personal`'s and `tools`'s
`python-ruff-mypy-gate` coexist in one member store — the spec's own motivating
case. **The encoding is ambiguous (`a--b`+`c` collides with `a`+`b--c`), so the
fork is centralized: ONE `_mirror_key(domain, stem)` / `decode_key` pair is the
only constructor/decoder at every scan-side site, and it REFUSES a namespaced
key whose parts contain `--` (a clear error naming the collision; the operator
renames the domain or the stem).** An authored local fact can no longer
silently block a foreign mirror (separate keys; `present(local)` stays
untouched).

**B. Provenance derivation (F3 + review F4).** The pull write path currently derives
`fact_id`/`domain` stamps and canonical paths from `ctx.domain_id` at
sync_global.py:1856-1859, 2069-2075, 1817, 2064, 1232, ~1300 (and
`cm repair-mirror` refuses foreign domains, cm_ops.py:784-786). Every one of
these becomes **record-derived**: the enumeration record carries the source
facts dir + the canonical's real `fact_id`/`domain` (its frontmatter already
holds them). Correct stamps → the holder base records → the three-way
classifier sees the right canonical → refresh lands instead of freezing in
`QUARANTINE "missing holder lineage"`. **Mechanism note (review F4): the
`_mirror_plan_for_dest` "stamp reads" (cm_ops.py:69-77) do NOT read stamps —
`_frontmatter`'s indented-child flatten list (memory_status.py:1220-1222)
lacks `canonical_fact_id`/`canonical_domain`/`group`, so those reads always
return empty and the code falls back to top-level `domain` + computed id. The
flatten list gains those three keys (the `global_ref_since` precedent) — that
site is load-bearing and listed here.** The mirror additionally carries
`group: <slug>` stamps in its metadata block — **all recipient slugs of the
delivering canonical (review F8), threaded into `_as_mirror` from the
enumeration record on BOTH the create and the refresh paths** — and `group`
joins `VOLATILE_KEYS` (mirror_conflict.py:9-14) AND `_as_mirror`'s strip list
(sync_global.py:1069-1075) in the same commit (F9: a non-volatile mirror-only
stamp would make `sem(mirror) != sem(canonical)` forever — perpetual STALE
churn; smoke-pinned).

**C. Admission + enumeration (F4 + review F7).** `admit_cross_project`
(domain_policy.py:66-95) hard-requires `fdom == pdom` — and it does so TWICE:
the confidential leg at line 88-89 returns before the general equality leg at
line 95. The membership override relaxes **both** equality checks (88-89 and
95) under the group gate — a `confidential` fact then crosses the bridge only
to explicit members per the F5 ruling. The override is gated on group
membership at these five gate sites — plus the enumeration grows from one
domain dir to N (per membership), each with its own facts-manifest record (the
single-ddir `_MAN_ROWS_STASH` logic in run() becomes per-record):
1. sync_global.py:734 `_consider` · 2. :793 `_consider_fast` ·
3. :1882 run()'s relevance re-admission · 4. session_beacon.py:202 ·
5. :3654 `_store_gaps`. `secret`/`looks_secret`/unknown/legacy rules unchanged.

**C2. The two remaining stem-keyed readers (review F3/F5), declared:**
`reconcile_inactive_mirrors` (canonical_ingress.py:886-1015) stays same-domain
— a cross-domain group fact's tombstone is NOT acked in member stores; GC
(with the membership-aware live set from §5-D) is the sole reclaim path for
withdrawn group mirrors. **Declared non-goal, not an accident.** Likewise
`_classify_edge` (sync_global.py:2298-2332) and `fleet_utility`/harvest joins
(:3996-4113, :4068-4077) remain domain-scoped: group-fact usage evidence is
**undercount-bounded** (foreign-member reads/windows don't join the foreign
canonical) and `gc --edges` may label a live cross-domain edge `stale` —
report-only, conservative direction, accepted for v0.4.10 and stated here.

**D. GC (F1).** The orphan predicate is stem-absent-from-the-LOCAL-domain
(`_orphans` sync_global.py:2430; `iter_canonical_stems_for_gc` :827-852) — a
live cross-domain group mirror would be deleted by `--gc --apply` and re-pulled
forever (delete-pull oscillation). The GC live-stem basis becomes the same
membership-aware admissible set `--pull` uses, and the mutate's holder fid comes
from the mirror's own `canonical_fact_id`/`canonical_domain` stamps (the
`_mirror_plan_for_dest` precedent, cm_ops.py:69-77). Smoke: a live cross-domain
mirror survives `gc --apply`; a truly orphaned group mirror is reclaimed.

**E. Revocation (F6 + review F1).** `cm group remove` models the enrollment revoke
(`_revoke_unadmitted_mirrors`, cm_ops.py:38-165): **clean managed mirrors are
deleted, locally-edited ones are quarantined** (timestamped, outside
`glob("*.md")`, GC-immune), journaled, holder cleanup by the mirror's own
stamps. The §5 "quarantine, never delete" wording was wrong about the
precedent — the precedent is delete-clean-quarantine-edited; group remove does
exactly that. **Namespaced names require a decode step in the planner (review
F1): every canonical lookup must decode the mirror key via `decode_key` to
`(canonical_domain, stem)` before resolving the canonical path — the naive
verbatim path resolves `{domain}--{stem}` to nothing, misclassifies the clean
mirror as a local edit, and QUARANTINES the very content the delete model
exists to withdraw (a confidentiality failure for group facts). The
cross-domain case is smoke-pinned.**

## 6. Command surface

- `cm group create <name> --domain <d> --apply --confirm create-group-<name>`
  (operator grant; slug validated before any phrase/stamp is built).
- `cm group add <group> <project> --apply --confirm add-group-<name>` /
  `cm group remove … --apply --confirm remove-group-<name>` — cross-domain
  membership allowed (the bridge is the point).
- `cm group list` / `cm group show <name>` (read-only; degrade-to-empty on a
  pre-migration registry, F8).
- `/cm-group` slash command (plan-first, mirroring `/cm-domain`).
- `/cm-share` extension: when groups exist, the confirmation step asks
  "share to a group or the whole domain?" — the draft then carries
  `recipients:` or not; the writer validates. **The confirmation prints the
  narrowing VERBATIM (review B): "delivery LIMITED to N members across X, Y;
  M same-domain projects STOP receiving it" — recipients narrow, never widen,
  and the exclusion is stated, never implied.**
- Name recreation (F11): a deleted group's name may be recreated; membership and
  audit rows are keyed by the immutable `group_id`, so a recreated name is a
  fresh identity, never a resurrection.

## 7. Invariants conserved

| Invariant | How |
|---|---|
| ADR 008 — grants are operator acts | create/add/remove are `--confirm`-gated, journaled, revocable; no self-join |
| v0.3.0 — no self-service A→B | the group IS the governed successor: grant rows + journal ops + delete-clean/quarantine-edited revoke |
| Single canonical writer | `recipients` validated + projected only in `canonical_ingress.upsert` |
| M1 ceiling / index admission | unchanged (F10: `_plan_pull` keys on name/status/cost only) |
| Secrets firewall | `secret`/`looks_secret` refused on every path, bridge or no bridge |
| Backward compatibility | same-domain stores, mirrors, pointers, and records untouched; new tables + optional key → **patch** |

## 8. Non-goals

- No self-service membership; no nested groups; no group content catalogs; no
  auto-inferred groups from stacks (that IS `stack-general`).

## 9. Verification (each pin fails on pre-fix code)

- group create/add/remove journal ops round-trip through `transact` recovery
  (both the whitelist and the dispatcher — F8);
- a `user-global` fact with `recipients:[g]` pulls ONLY to g's members; a
  same-domain non-member does NOT receive it;
- a cross-domain member receives the mirror under the `{domain}--{stem}` key
  with correct `canonical_fact_id`/`canonical_domain` stamps + the `group:`
  stamp, and **survives `gc --apply`** (F1);
- same-stem canonicals in two domains coexist in one member store (F2);
- a canonical change in the authoring domain REFRESHES the cross-domain mirror
  (no QUARANTINE freeze — F3) and the `group:` stamp does not restamp on a
  no-change refresh (F9 volatility);
- unknown-group `recipients:` → `WriteRefused` naming it; `confidential` +
  foreign recipients lands per the F5 ruling; duplicate `recipients:` key
  refuses;
- `cm group remove` deletes clean mirrors, quarantines locally-edited ones
  (F6) — INCLUDING the cross-domain namespaced case (decode-first, review F1);
- `_mirror_key`/`decode_key` refuse the ambiguous `--` encoding (review F2);
- the recreation guard fires: recipients predating a recreated group refuse
  (review D);
- `confidential` + foreign recipients lands per the F5 ruling through BOTH
  equality legs (review F7);
- the beacon counts a missing group-fact mirror; read paths degrade on a
  pre-migration registry;
- the `/cm-share` command names the group question; `cm group` CLI exists with
  confirm phrases.
Full suite per round: smoke / concurrency / simulate_accumulation / mypy /
manifests / bench --quick / pre-push gate / CI; one review agent per PR; the
finder re-verifies every fix.

## 10. Ship shape

Additive, backward-compatible → **patch** (v0.4.10), CHANGELOG-first. The
fleet's two measured cases then resolve without duplication: `advisor-pass`
gains one cross-domain group; one `python-ruff-mypy-gate` copy is retired.
