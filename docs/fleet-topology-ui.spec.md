# Fleet topology UI (0.4.13 spec)

**Design-of-record for the HTML archive's shared-consciousness view: all topology
layers on one diagram, any fleet combination.**
Status: amend-3 (review BLOCK-1/2, HIGH-1..3, MED-1..4, LOW-1 folded) → implementation. Evidence ledger: every citation survived re-verification. Residual risk (LOW-1, stated): "pixel-identical" rests on string-presence pins over unexecuted JS — a shared-helper refactor could break legacy renders with all pins green; the painter's legacy branch is therefore left byte-untouched except the named gate additions, and the fleet path is a SEPARATE code block.

## 1. Context (measured, 2026-09-05; two deep-dive reports)

The user's read is right and wrong in one precise way: the archive's network
view **never had** a layered domain/P2P diagram — and it also **did** show a
richer fleet than it does today. Both facts are measured:

- The painter (`dashboard.template.html` §02, lines 973-1172) is **byte-identical
  to v0.2.1** except a `hasNet` guard. It always drew: this project (rust) at the
  hub, up to 12 peers on a ring, hub spokes + bowed peer chords (the differential
  stack layer), baseline-only satellites dimmed to `·`, three-tier caption. The
  "richness" came entirely from its **feed**.
- v0.3.0 (ADR 008 + commit 54b1140) deleted the feed: `token_network`'s node set
  went from `_network_nodes()` — **every** store on the machine holding ≥1 mirror,
  all domains — to `_same_domain_stores(ctx)` (current-domain only), and
  `canon_scope` from installation-wide `global_facts()` to `facts_for_context`.
  So the diagram degraded to a single-domain fragment with no cross-domain
  chords — while the painter sat unchanged. v0.4.0 then retired the Markdown
  `projects:` provenance (the old edge source) to SQLite holders, and v0.4.11
  shipped the "0 minds" all-domains regression (fixed in 0.4.12, now
  registry-sourced).
- The **group layer (v0.4.10) has no representation anywhere** — not in the
  record, not in the HTML, not in the ASCII. The operator can see domains only
  via the CLI lenses (`--network --all-domains`), groups only via `cm group
  list`, and no view shows the routed links (which group carries which fact
  across which domains).

**The record's data ceiling today** (`token_network`, sync_global.py:3625):
same-domain nodes with token/fact counts + same-domain `stack_edges`
`{a,b,n}` + totals. No per-node domain, no group membership, no edge type
beyond "pairwise stack intersection", no fact names. The richer logical view
(`sync_global.network()` — minds, per-fact universals with held counts,
differential edges, dead-mind flags) never reaches the record.

**Constraints that police the change** (the pin lattice):
- The cycle-record schema pins (smoke.py:1119-1135): every data-model key must
  exist in the TypedDicts (memory_status.py:292-325) AND the SKILL.md schema
  block — in lockstep.
- The embed guard (smoke.py:11603-11621): every top-level record key the
  template reads must be in `_EMBED_KEYS`.
- Verbatim template pins (smoke.py:2132-2155, 2260-2263): legacy captions, the
  fallback honesty strings, `ringOrder`/`bowCtrl`/`isBaseline`/`edgeN`
  presence. Legacy records must keep rendering through the existing paths.

## 2. The changes

### 2.1 The feed — `token_network` becomes fleet-complete and typed

- **Node set = disk-first, registry-overlaid (advisor A1 — the only feed that
  honors every promise).** `_network_nodes()` (the v0.2.1 semantics: a walk of
  `iter_native_stores()` — the projects tree UNION registry `native_memory_dir`
  — filtered to stores holding ≥1 mirror on disk) is re-armed for production;
  the holders table alone cannot see pre-registry stores holding legacy
  mirrors, and disk alone lacks attribution. The registry overlay (via each
  store's path → `projects` row) supplies `domain`, `groups`, and the
  display-name label space. **Label space (A2):** every member/edge reference
  in the new keys resolves to the SAME node labels the nodes list carries
  (path-derived `_node_label`); a registry row whose store path doesn't
  resolve to an enumerated node is dropped from `group_links`/edge names,
  never re-keyed into a second label space. **Fixture mode (F1):** the
  disk-path branch under `_global_is_fixture()` is PRESERVED — the
  dream-beta-tester oracle's canary repos have no registry rows and must keep
  degrading to the disk enumeration exactly as today.
- **Per-node attribution** (additive keys, `total=False`-typed): `domain`
  (the node's enrolled domain id), `groups` (the operator-granted group names
  it belongs to), and `sid` (the full store slug — the collision-proof join
  key). **HIGH-1: the label space is non-injective** (24-char truncation of
  full-path slugs can merge two stores into one label — silently wrong
  topology). All NEW keys (`domains[].members`, `group_links[].members`,
  `stack_edge_facts`) reference `sid`s; the emitter guarantees label
  UNIQUENESS by disambiguating colliding display labels with a suffix from
  the dropped slug head; the renderer maps sid → display label. The existing
  `stack_edges {a,b,n}` stays label-keyed (byte-compat) and is emitted only
  over the disambiguated unique labels. Unenrolled stores holding legacy
  mirrors get `domain: "unknown"` — rendered DIMMED and unattributed
  (no group/domain chips; MED-4: their resurrection in shared archives is
  stated in §3, not silent).
- **Edge semantics, three kinds** (additive to the record, keyed by label so
  legacy readers ignore them):
  - `universal_facts`: `[{name, domain, held}]` — every user-global canonical,
    with its holder count (the every-mind baseline with its PARTIAL cases —
    the honest "only 2/11 so far" the CLI already prints).
  - `stack_edges`: unchanged shape `{a,b,n}` but now computed over the FULL
    node set (cross-domain chords return), plus `{a,b,names:[stems]}`? No —
    keep `{a,b,n}` byte-compatible and add a parallel `stack_edge_facts`:
    `[{a,b,names:[…]}]` so hover can name the binding facts.
  - `group_links`: `[{group, home_domain, members:[node…], facts:[{name,
    domain}]}]` — the routed-link layer: each operator-granted group, its
    members, and the canonicals whose `recipients:` cite it (the bridge's
    cross-domain carriers).
  - `domains`: `[{domain, members:[node…]}]` — the VLAN layer (nodes with no
    shared facts still appear here so the domain's membership is visible).
- **The emission surface (BLOCK-1 — the scoping contradiction is decided at
  the emitter).** `sync_global.py --tokens . --json` gains a `--fleet` flag
  (B2: a distinct name — `--all-domains` already means something else on
  `--network`). Bare `--tokens` stays the current-domain basis byte-shaped as
  today. `--fleet` emits the fleet node set with `group_links` scoped to the
  TRIGGER's own groups (the share-safe archive default — what this project's
  bridges can carry); `--fleet=full` adds the operator's complete group set
  (the user's "any fleet combination" view — one flag, documented in the
  schema `"_"` doc; the SKILL's Phase-5 line becomes `--fleet` and the doc
  notes the `=full` escape). §3 states exactly what each basis embeds — no
  "default" wording that never executes. MED-1: `--fleet` on any mode other
  than `--tokens` REFUSES (usage error, exit 2) — a flag must never silently
  no-op on a read-only or destructive mode.
- **TypedDicts + SKILL.md schema block** updated in lockstep (the pins make
  this mechanical and enforced).

### 2.2 The diagram — one view, all layers

The painter's proven geometry stays (hub + ring + bowed chords + baseline
dimming + seriation). New:

- **Geometry decision (C1, S5): domain ARCS, not horizontal bands, with a
  RING BOUND (HIGH-2).** The ring draws ≤ 16 nodes (the painter's legible
  geometry limit) with a "+N more" satellite node carrying the count; domain
  arcs derive from the drawn set. The domain palette cycles the template's
  4 tint vars (`--tint-ok/crit/accent/warn`) with a neutral fallback beyond
  4 — the arc LABEL carries the domain name regardless, so color is
  reinforcement, never the only signal. The
  ring's proven geometry (hub + seriated ring + bowed chords + auto-viewBox)
  survives; nodes partition the ring into contiguous per-domain arcs (tinted
  segment, labeled at the arc boundary, deterministic domain order) — the
  trust-boundary layer with the smallest rewrite risk. Band-internal order =
  the existing this-stack-affinity seriation, run per domain. An early probe
  with a synthetic 4-domain / 25-node record runs through the render chain
  as the FIRST implementation step, before any pins are written (C2: the
  viewBox growth is unbounded if bands stack vertically).
- **Group links.** Each `group_links` entry draws a dashed teal hull around
  its member nodes — crossing domain arcs IS the routed link — labeled with
  the group name; hover lists its facts (capped). Hulls cap at 6 with the
  overflow collapsing to legend rows (C3, the registrar's "+N more" idiom);
  single-domain groups render as a pill beside their arc. `group_links`
  covers the TRIGGER project's own groups by default (D1: the bridges that
  can carry this project's facts — the view that matters, and its exposure
  ≈ what this project could pull anyway); `--fleet` adds the operator's full
  group set when the flag is passed.
- **Universal baseline — an HTML chip strip, not SVG substrate (S2).** A
  row of per-fact chips below the SVG (name · held/M; partial holders gapped
  amber) delivers the honest substrate without viewBox surgery; capped at
  ~12 chips + "+N more", partial-holders first. Legacy records keep the
  caption-only path (the pinned strings survive). This also fixes the
  pre-existing honesty bug the advisor measured (F6): the split caption's
  "Everyone holds the same baseline" asserted equality even when universals
  are partial — the new layer shows the truth; the caption text is updated
  only on fleet-basis records.
- **Differential chords.** Unchanged mechanics, now fleet-wide (cross-domain
  chords return naturally); hover names the binding facts from
  `stack_edge_facts` — which the emitter restricts to the chords the painter
  WILL draw (S1: the deterministic `pn > max(spokeN[i],spokeN[j])` filter,
  computed at emission), names capped at 5 + "+N".
- **Node attribution.** Each node shows its domain color-chip + group
  membership glyphs (the `groups` list) in the hover.
- **Every rendering change is KEY-GATED (HIGH-3 — the gate is NAMED).**
  The ONE canonical predicate is the top-level `basis_scope === "fleet"`
  string: the 12-node cap lift, every new layer, and the F6 caption-honesty
  branch all key on it — NEVER on `split`/`stack_edges` (pre-0.4.13 split
  records with >12 nodes must render pixel-identically). The split/legacy
  fork itself is proven safe (0-valued `universal`/`stack` keys make every
  emitter-produced record split) — the new branches are what must not ride
  it. A fleet record whose lists the model trimmed from the paste degrades
  to the domain-basis caption honestly (the painter's existing
  trimmed-paste fallback wording).
- **Legacy fallback is UNTOUCHED**: records without the new keys render
  exactly as today (the split/legacy branches and their verbatim pins stay).
  The pinned painter-comment strings ("baseline … never drawn as an
  all-to-all star", `stack_edges` present, `global_facts` absent, F5) stay
  in any rewritten block.

### 2.3 The ASCII dashboard

`render_dashboard._network_section` gains one honest line per new layer when
the keys exist (domains: N bands, groups: N routed links, universals: N
facts) — never before legacy keys are absent (the absent-block pin stays).

## 3. Invariants

- **Backward-compatible.** All new record keys are additive and
  `total=False`-typed; legacy records and legacy templates render identically
  (the verbatim pins enforce it), and every rendering change is key-gated.
  → **patch**, same 0.4.13 cycle as the held dogfood PR.
- **Registry-overlaid disk truth, never `projects:`.** The feed enumerates
  disk stores holding ≥1 mirror and overlays registry attribution; the
  retired Markdown provenance stays migration-only.
- **No invented topology.** The record captures what the enumeration
  measured at dream time; the renderer still never fabricates edges (the
  pinned comment survives).
- **Confidentiality, stated honestly (D1).** The record is SHARE-SAFE
  (identity_snapshot never embeds filesystem paths); the HTML archive is
  often shared. The fleet basis therefore adds into a shareable artifact:
  cross-domain node basenames, per-node domain/group attribution, and fact
  names. That is NEW in the record (operator-visible today via the CLI, but
  never before embedded). The mitigation is scoping: `group_links` covers
  the trigger's own groups by default; `universal_facts` names are accepted
  (stems are readable from the canonical dirs anyway); the spec records the
  trade explicitly rather than claiming "nothing new is exposed."
- **Bounded size at EMISSION, not render (BLOCK-2).** The record caps
  apply in the emitter: `universal_facts` ≤ 24 entries (partial-holders
  first) with `totals.universal` carrying the uncapped count;
  `stack_edge_facts` = the drawn-chord set (the painter's deterministic
  filter, S1 — mirroring its `i,j≠trig`, `drawn`, and fork preconditions)
  with ≤5 names each; `group_links` ≤ the trigger's 6 largest groups
  (members truncated to the node set). Fleet-basis record budget stated:
  ≤ ~6 KB so 120 cycles stay inside the 300 KB embed contract; the P4 size
  pin gains a fleet-scale synthetic cycle asserting it.

## 4. Verification (each pin fails on pre-fix code)

- The feed: a two-domain, two-group fleet fixture (hermetic) → the emitted
  record block has fleet-wide nodes with `domain`/`groups`, a cross-domain
  `stack_edge`, `group_links` naming the bridge fact, `universal_facts` with
  honest held counts; the current-domain basis (`--tokens` without the flag)
  stays byte-shaped as today.
- The diagram: the template's new layers render from the new keys; a legacy
  record renders through the untouched paths (existing verbatim pins re-run
  green); the new layer pins assert the band/group/unversal elements exist
  AND are key-gated (absent keys → absent elements, not errors).
- The schema lockstep: TypedDicts ↔ SKILL.md block (existing pin, extended).
- The embed guard: `network` stays whitelisted; no new top-level record key.
- Full suite + the render-chain pins + one review agent per PR; the finder
  re-verifies. **MED-2: the fleet fixture must NOT sit under /tmp** — the R2
  fixture-store exclusion matches every `/tmp`-derived slug (`-tmp-` is a
  substring of the full-path slug), so the fixture home is built at a
  clean-slug base (the test controls the dir name) or `_network_nodes`
  gains an `allow_fixture_paths=True` override the fixture passes;
  the beta oracle's subprocess flows are R2-excluded anyway (F1's wording
  corrected — fixture mode is in-process-only). `validate_cycle_record`
  gains NON-VACUOUS checks (MED-3): item-level dict shapes for the four
  lists, `universal_facts[].held ≤ totals.nodes`, and the strongest —
  every `members` entry and every edge-fact name RESOLVES to a
  `nodes[].sid` (A2/HIGH-1 enforced at runtime against emitter bugs and
  model hand-edits). The `--demo` record showcases the new layers (F3).

## 5. Ship shape

Backward-compatible → **patch (0.4.13)** — rides the held dogfood PR #197 in
the same release cycle (both PRs merge, one `--finalize`).
