# Network capture teeth — design-of-record

**Status: review-to-zero CLEAN (amend-2 verified) → implementation.**
Target release: **v0.4.20 (patch)** — additive advisory + additive beta-oracle family + a
UI readability fix; no record-schema change, no exit-key change.

## §1 Context (measured)

The first dream judged by the v0.4.19 conversation-truth gates exposed the capture-side gap:
the dream's archive rendered "Captured fleet / **No project nodes captured for this view**"
STACKED on "**Network details were not captured for this dream**" — two states at once, read
as total fleet disconnection.

Root cause, measured: Phase-5 step 4 mandates `sync_global.py --tokens . --json --fleet` pasted
verbatim into the record's `network` block; that step did not run in the pass, so the record
persisted with **no `network` key at all** — and nothing anywhere flags a skipped capture. The
block is optional by schema (pre-0.4.13 records legitimately omit it — the `--fleet` capture
mandate shipped in v0.4.13), so the omission persists silently; only the archive shows the
absence, and the terminal render says nothing. The renderer's behavior was honest in each state
— the defect is that the two states STACK (dashboard.network.js:146 paints the empty-fleet SVG
text whenever no blocks render, and :174 adds the not-captured note whenever `net.nodes` is not
an array — on an absent block BOTH fire; pre-change revision — the post-fix sites are :155 and
:183), and that a skipped capture has no teeth anywhere else
— on a FULL dream pass. One class is exempt by scope: a maintenance/bootstrap pivot runs
Phase 1 pull + Phase 5 health only (the SKILL's no-op rule), so its fleet capture is skipped BY
SCOPE, same class as the distill/usage/demotion steps — the pivot carve-out is part of the
design below (finding 1), not a gap.

Why this node mattered: the triggering store holds 2 shared-fact mirrors — the fleet is real,
and a capture run shows it (verified in the repair: 11 nodes, 3 universal + 1 stack fact). The
emptiness was the missing capture, not an empty fleet.

## §2 Design — three parts, no new gates

**1. NET — the persist-side capture advisory (render_dashboard, judged path).** When the record
has a `dream` block (the capture mandate applies to every full dream — the pivot carve-out
below applies under either gate width) and `network.nodes` is **not a list** — the block is
absent OR present without nodes, the ONE predicate shared across all three surfaces (the
producer always emits `nodes`; a nodes-less dict is a shape `token_network` never writes, and
the terminal's own network section would otherwise read it as an honest empty capture with no
advisory) — the judged render gains a yellow panel:

`⚠ NETWORK CAPTURE MISSING · the fleet capture never ran or was not fully recorded — run
sync_global.py --tokens . --json --fleet and paste its full output into the record's network block, then re-render`

**Suppressed on a pivot pass** — when `record["maintenance"]["pivoted"]` is truthy (with the
string-coercion discipline: a model-authored `"false"` string must not read as pivoted —
`_maintenance_pivoted`'s coercion is the precedent), the panel does not fire: the pivot's scope
excludes the capture BY DESIGN, and mis-directing it to run a skipped-by-scope step would be a
false positive on the most common no-op pass.

**No exit change** — the advisory is loud, never a gate. Rationale: the capture is an
enrichment of a COMPLETED dream (the post-persist re-render heals it — proven by the repair
this spec records; the heal covers the RENDER surfaces — the terminal panel and the archive —
while the log line stays attempt-scoped: `_persist` is idempotent on (commit, timestamp), so a
healed record re-renders as duplicate and appends nothing, and the beta family therefore
clears on the next FRESH persist, never on a heal re-render — its era tail carries the
recency caveat), not part of the dream-arc contract; the exit key stays frozen (3 =
procedure integrity, 4 = arc, 5 = unstamped — the beta `persist_gate` family pins those
semantics). The panel fires regardless of the record-side verdicts (a 4/6 arc that also
skipped the capture shows both panels — different defect classes, no double-report). Pre-0.4.13
dream-bearing records re-persisted by a current skill get the advisory too — correct: the skill
now running should capture. The panel copy must not contain the phrase "CONVERSATION-TRUTH"
(F19H's negative assertion).

**2. The `network_capture` beta-oracle family.** `beta_checks.py` gains the family on the
existing scaffold: `_latest_capture_check(block_key="network", min_version=(0, 4, 13))` — the
floor is 0.4.13 because the `--fleet` capture mandate shipped there (the fleet-topology feed);
0.4.17 was the display_name/sid truth layer, not the mandate. The family starts
`if _maintenance_pivoted(ctx): return []` — the FOURTH member of the distill/usage/demotion
skipped-by-scope set (the factored `_maintenance_pivoted` already names "all three"; the
pivot's capture skip is the same class — unlike narration, the network block is NOT written on
every judged persist). `is_complete = isinstance(block.get("nodes"), list)` — the producer
ALWAYS emits `nodes` (possibly `[]`); a nodes-less dict is a shape `token_network` never writes
and the ARCHIVE's note ladder keys its not-captured note on exactly this predicate
(`Array.isArray(net.nodes)`) — the oracle agrees with the archive and `validate_cycle_record`'s
nodes-not-a-list warning, never weaker than the archive (the panel uses the same predicate:
one predicate, three surfaces). A 0-node capture is a REAL capture (the honest
empty fleet) and PASSES. The WARN's `actual` string BRANCHES by state: an absent block carries
the era caveat tail (records carry no version and the scaffold gates the SKILL version, never
the record — a pre-0.4.13-era record under the current skill WARNs with a tail naming that era,
the dream_arc/narration caveat precedent); a PRESENT nodes-less block carries a corruption tail
("the block is present but its nodes are not a list — the producer always emits nodes") — the
era tail must never read over a present block. So the
frozen v0.1.8/A1 store fixture gains one expected WARN (its 2026-06-21 record predates the
mandate): the smoke fixture pin re-baselines from 1 to 2 named expected WARNs (CHK-NARRATION +
CHK-NETWORK-CAPTURE), still discriminating (any other noise flips the count).

**3. Archive readability (dashboard.network.js).** The two states never stack, at the WHOLE
panel level: when the block is ABSENT (`!Array.isArray(net.nodes)`) the network panel collapses
to the not-captured note alone — the SVG map, the search/view controls, the legend, and the
detail attribution are all hidden (they paint unconditionally today: the "Captured fleet" root
mark + rank labels in draw(), the controls, the "Projects are organized by domain" legend, the
"Saved with this dream" attribution — leaving them over a blank canvas is the same stacked read
one level up). When the block is PRESENT with 0 nodes, the empty-capture text shows (a
distinct, real state) and the not-captured note does not. Absence ≠ emptiness, and each renders
alone.

**Docs.** SKILL.md's Phase-5 step 4 gains one line naming the advisory + the family (the capture
mandate already exists — this names its teeth). CHANGELOG [0.4.20]. The roadmap's watch-item
(the silent-skip) closes with the ship.

## §3 Verification — the pin list

In-process / smoke:
- the persist panel: a dream-bearing record with no `network` key → the panel in stdout, exit
  UNCHANGED (exit 0 on an otherwise-clean record; exit 4 still 4 on a 4/6 arc that also lacks
  the block — the panels coexist, no double-report); a dream-bearing record with a PRESENT
  nodes-less `network` dict → the panel fires too (the one-predicate seam — the terminal would
  otherwise read a nodes-less block as an honest empty capture with no advisory); a dream-bearing
  record WITH a `network.nodes` list → no panel; a dreamless record → no panel (the legacy
  carve-out extended); a PIVOT
  record (maintenance.pivoted truthy — including the string `"true"` and a truthy `"false"`
  string reading as NOT pivoted) → no panel; the panel copy contains no
  "CONVERSATION-TRUTH" (F19H's negative survives).
- the beta family: absent block → WARN with the era caveat tail; block with nodes → PASS;
  block with `nodes: []` (the honest empty capture) → PASS; a nodes-less dict → WARN with the
  CORRUPTION tail (never the era tail — the actual-string branch); the latest record pivoted →
  family empty; pre-0.4.13 skill → family empty (the canary v0.1.19 still skips).
- the fixture re-baseline: the v0.1.8/A1 STORE fixture pin moves to 2 expected WARNs
  (CHK-NARRATION + CHK-NETWORK-CAPTURE named — any other noise still flips it).

Browser (tests/dashboard_browser.py):
- the absence fixture: the network panel collapses to the not-captured note alone — the SVG
  map, the search/view controls, the legend, and the detail attribution are all absent (the
  two states never stack, at any level).
- the empty-capture fixture in the REAL emission shape (`network` with `nodes: []`,
  `fact_holdings: []`, and zero capture counts — what `--tokens --fleet` actually writes):
  the empty-capture text renders, the not-captured line does not, and the older-snapshot
  caveat does NOT fire (absence ≠ emptiness, each renders alone).

## §4 Ship shape

Feature branch → per-PR review → user merges → `release.sh` pre-bump (CHANGELOG [0.4.20]
first, plugin.json 0.4.19→0.4.20, the complete sweep) → `--expect patch --finalize`.
Backward-compatible: additive advisory panel, additive family, a JS rendering fix; no
record-schema change (the checks read the existing `network` + `dream` blocks), no exit-key
change. The PANEL's gate is the dream block (a dreamless record is exempt, the legacy
carve-out extended) and pivot passes suppress it; the FAMILY carries no dream-block gate —
a dreamless latest line WARNs with the era tail by design (a pre-dream-era heuristic; the r20a
battery pins it), and a pivoted latest line skips the family. Version
honesty: records carry no version — the beta scaffold gates the SKILL version (pre-0.4.13
skills skip the family), while a pre-0.4.13-era record under the current skill WARNs with a
caveat tail naming its era + the recency caveat (the dream_arc/narration precedent; §3 pins it).

## Amend ledger

- **amend-2 (review-to-zero, 2026-09-06):** amend-1 verified clean; 2 MED + 2 LOW + 1 NIT.
  Folded: the one-predicate rule — `nodes` is a list gates the panel, the oracle, AND matches
  the archive's note ladder (a nodes-less dict never renders as honest-empty with no advisory —
  the seam the absent-key-only gate left); §1's pre-0.4.17 claim corrected to the 0.4.13 mandate
  floor + the terminal's silent skip named; the oracle-agreement claim corrected (the ARCHIVE,
  not the terminal's section, keys its note on the same predicate); the WARN actual-string
  branches (era tail for absent, corruption tail for a present nodes-less block); the
  gate-width rationale restated (the pivot carve-out applies under either gate). A same-round
  completion pass: the panel copy widened to both firing classes ("never ran or was not fully
  recorded" — a nodes-less block ran but lost its rows), `validate_cycle_record`'s
  nodes-not-a-list warning named beside the archive, and §3's one-predicate pin corrected to
  state the seam as measured (the terminal WOULD read a nodes-less block as honest-empty —
  that is why the panel fires). No BLOCK/HIGH; patch classification holds.
- **amend-1 (advisor pass, 2026-09-06):** 1 HIGH + 4 MED + 4 LOW. HIGH: the maintenance/pivot
  class was absent from both surfaces — pivots skip the fleet capture BY SCOPE (Phase 1 + Phase
  5 health only), so the family would false-WARN every pivot's latest record and the panel
  would mis-direct the pivot's own render; folded — the family joins the `_maintenance_pivoted`
  skip set (its fourth member) and the panel gains the string-coercion pivot suppression.
  MEDs folded: `is_complete` = nodes-is-a-list (the producer always emits nodes; the renderer
  already reads nodes-less as not-captured — oracle and renderer agree); the JS fix restated to
  the WHOLE-panel collapse (the SVG map, controls, legend, and attribution all hide on
  absence — the recommended option); the empty-capture browser fixture uses the REAL emission
  shape (bare `nodes: []` would fire the older-snapshot caveat); the version-gating
  contradiction fixed — the scaffold gates the SKILL version, never the record, so the era
  caveat tail is specified and §4's "exempt" claim corrected. LOWs folded: min_version
  (0,4,13) with the rationale (the `--fleet` mandate shipped there); the gate-width wording
  (dream-block, wider than the narration arms — deliberate); the no-exit-change defense
  verified (the frozen persist pins assert rc + substrings only — additive stdout breaks
  none, and F19H's negative constrains the panel copy); the fixture name corrected (the
  v0.1.8/A1 store fixture, not the cycle-probe).

## Evidence ledger

Every citation above is measured: the dream #sel=48 archive rendered both states stacked
(the user-reported paste); the seed record was verified to carry no `network` key at all
(python check against /tmp/cm-cycle-…json); the repair run produced the 11-node fleet capture
(3 universal + 1 stack fact); dashboard.network.js:146/:174 are the two stacking sites; the
beta scaffold's gating and the smoke fixture pin's current 1-expected-WARN baseline are the
code being extended (tests/smoke.py, the v0.1.8/A1 section).
