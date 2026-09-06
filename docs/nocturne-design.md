# Nocturne: clear topology, accessible evidence

Nocturne is a self-contained, offline archive of recorded dreams. The four report
sections support progressive exploration: **dream summary → memory network →
memory activity → verification & health**, followed by the existing decision
ledger. The header remains the sole index-size and budget-projection chart.

The redesigned renderer preserves the original header graph markup, shared helpers,
calculations, and styles. Section navigation reflects the new order. Every figure
is captured evidence, not a live store query.

## Visual system

The midnight canvas, Glacier holdings, Iris permissions, restrained orbital mark,
and humanist system typography remain. Georgia italic belongs to captured dream
voice. Report sections use larger, heavier headings and conclusions, comfortable
body text, compact evidence labels, and quieter source notes. Status text has its
own emphasis and color; meaning remains explicit in words. Section spacing and
dividers separate the questions each section answers. The network uses Glacier
for observed holdings and Iris for permissions, with a short selection caption.
Report changes are scoped below the existing header and KPIs; the surrounding
toolbar controls share the control styling described below.

Narration, outcome text, captions, ledger explanations, and the activity inspector
use their section's available width. Section titles, metadata, and collapse
controls share a consistent alignment. The dream-summary columns are equal, and
the activity chart fills its container. Network search and View controls have
matching heights and stack on mobile. Mobile ledger rows put the action above the
lesson name; long names and evidence wrap within their containers.

Source notes identify the saved outcome, decision ledger, verification, or recall
observations behind each section. The network caption attributes its answer to
the saved dream snapshot. Recorded save times identify the dream, without implying
a fresh inspection of today's stores or a separate capture timestamp.

Nocturne, Original, Light, and System themes, reduced motion, print, archive
filters, density, keyboard navigation, and the accessible diff dialog remain.
No fonts, scripts, stylesheets, or data are fetched from the network.

### Controls and links

Controls share a coherent hierarchy across the archive toolbar and report sections.
The primary **Open this dream** action has a filled treatment; secondary actions,
selectors, and toolbar buttons use clear outlines. Inline evidence actions remain
close to their associated claim or filename, with an explicit visual affordance.
Expandable details have chevrons, distinct hover and expanded states, and generous
clickable rows. Section collapse indicators have visible frames. File actions pair
the filename with an explicit **View diff** label and resolve only to a captured
diff, including historical file references.

Control sizes, padding, radii, and interaction colors are consistent. Standalone
controls provide 44-pixel targets. Keyboard focus remains visible, disabled controls
cannot activate, and pointer clicks do not add unrelated selection boxes to the
graph. The control styling adapts to all four themes without changing the header
graph's own colors, geometry, or calculations.

Evidence actions expand and focus the appropriate detail. **Open this dream** opens
the selected report or returns to its summary when it is already open. **Archive**
and Escape return to the dream list for both query and fragment selection links.
The diff dialog keeps keyboard focus inside it, supports scrolling the diff with
the keyboard, and returns focus to its trigger when closed.

## Network exploration

A ranked SVG tree replaces domain containers and perimeter-routed pairwise edges.
Its initial root is the captured fleet. Every captured domain appears, including
an explicitly captured domain with no project rows. The triggering project's
domain starts expanded. Each domain has 12-project pages, and project search
reaches every captured project. No global first-16 cutoff remains.

A single **View** selector switches between the fleet, captured facts, and groups.
Selecting a canonical fact produces **fact → domain → physical holders**.
Selecting a group produces **group → domain → captured members**; permissions
never center on an arbitrary project. Only those members appear in the focused
group tree. Project names and their relationship labels appear on the map itself.
A compact caption explains the selection and its saved-snapshot basis.

The visible network consists of this map, project search, the View selector, and
the caption. When capture is incomplete, one brief note states the limitation.
There is no second holder list, technical inspector, project directory, token
accounting panel, or repeated statistics beneath the map. The existing page-level
**Inspect the complete captured cycle record** disclosure retains all original
network fields, including identities, capture counters, token estimates, registry
counts, and historical pairwise links.

Horizontal ranks use dedicated branch ports. A trunk is drawn once, junctions mark
its aggregate branches, and expanding a domain exposes the members. Each trunk
extends through both the root's port and every child branch, including a single
domain whose center differs from the root. Root connections have no visual gaps.
Rank labels distinguish the selected root, domains, and projects. Mobile changes
to a vertical tree with separate fleet and domain rails before labels and paging
controls become cramped. Text labels,
interaction names, and the selection caption accompany color. The SVG height
follows its rendered width and view box so sparse trees do not leave large blank
bands above and below their branches.

Pointer interactions show the chosen relationship without a focus rectangle around
an unrelated root. Keyboard navigation retains a visible focus indicator. Mobile
branches leave the root at its side so they stay clear of the fact or group name.
The gray fleet branches are labeled **Project organization**, distinct from
observed holdings and permission to receive.

Historical archives use their recorded domains, projects, and pairwise links.
When canonical identities are absent, the caption states that boundary. The
renderer never reconstructs history from current stores.

## Canonical identity and capture contract

Two local filenames can represent one canonical fact. The fleet emitter now joins
mirrors through canonical domain/name and stable fact identity. Legacy references
use the **holder's own domain**, never the triggering project's domain. Contradictory
stamps, scopes, references, or ambiguous namespace interpretations stay unresolved.
The shared frontmatter parser exposes the existing `global_ref` stamp to that join.

The optional fields are:

| Field | Meaning |
| --- | --- |
| `nodes[].display_name` | Readable registry label, separate from the stable `sid` and compatibility label |
| `fact_holdings[]` | Canonical `fact_id`, `name`, `domain`, `scope`, emitted `holder_sids`, exact pre-limit `held_n` |
| `capture` | Physical basis, group scope, exact total/emitted fact and holder-reference counts, incidence bytes, unresolved identities, and native fact-file read failures |
| `group_links[].facts_total` | Addressed canonical count before the existing eight-fact limit |

Unique fleet totals and compatibility pairwise intersections use canonical
identities. Token accounting, physical fact/mirror counts, existing field shapes,
CLI flags, and archived payloads remain compatible. Non-fleet emission retains its
existing shape. Physical presence, registry holder rows, permissions, and delivery
are separate measurements. In particular, `universal_facts[].held` is registry
evidence and can exceed the physically captured node count.

Incidence stops at **120 facts, 2,000 holder references, or 64 KiB JSON**, whichever
comes first. JSON byte accounting uses an ASCII-escaped representation including HTML delimiter escaping,
so the limit remains valid for non-ASCII and hostile labels. Trigger-associated facts come
first, then stack facts, then descending holder count, with stable identity as the
tie-breaker. The trigger's holder reference comes first within a fact. A final
partially captured fact retains its exact `held_n`; `capture` preserves all exact
pre-limit counts. Read-failure counts explicitly cover captured native fact files;
they do not claim that every absent store was successfully inspected.

The limits live in `memory_status.py` and are imported by the emitter. TypedDicts,
validation, the skill's example schema, and fictional fixtures move together.

Fleet coverage still means **captured stores holding shared mirrors plus the
triggering store**. Projects absent from this set are outside the capture basis;
they are never described as disconnected.

## Outcome and captured voice

The summary follows the existing header/KPIs and leads with the recorded outcome.
Confirmed claims, observed physical changes, decisions, and attention items link
to their evidence or the existing ledger. No new completion judgment is invented.

The complete dream reads in one column of italic paragraphs, ordered from sleep
through the captured passages to wake. Each passage appears once, fully visible,
without phase controls, repeated labels, or a second expanded copy. Paragraph
breaks and captured wording are preserved; surrounding Markdown emphasis and quote
markers are removed for display because the typography already supplies the voice.
Missing or malformed passages remain explicit in ordinary report typography. The
original record remains available unchanged in the raw-data inspector.

## Verification and health

Exceptions come first and link to four disclosures. The first three display their
own **Needs attention**, **Recorded clear**, **Partially captured**, or **Not
captured** state in the disclosure heading. A second row of status cards does not
repeat the same judgments. There is no combined health score.

1. **Verification evidence** — a concise account of confirmed, corrected, and
   unverifiable claims, the recorded method, and procedure-integrity findings.
2. **Store checks** — named checks and recorded failures, followed by preflight
   time and IDs. Detailed health, remediation, identity, and maintenance fields
   remain inside subordinate disclosures.
3. **Observed file changes** — changed filenames and diff access lead. Store
   accounting, the observation window, and conservation evidence remain available
   on expansion.
4. **Recall & workflow decisions** — readable recall observations and recorded
   verdicts lead into separate workflow, demotion, and cross-project disclosures.
   Complete command rows, chains, skill use, registrar states, and decline lineage
   stay reachable without dominating the initial view.

Only adverse or pending results open by default. Partial capture is clearly labeled
but does not open routine detail automatically. Preflight lists only its captured
timestamp and failure/warning IDs, without inventing individual check outcomes.
Unknown observations stay missing; actual zeroes stay zero. Complete evidence rows
remain available through native disclosures and the unchanged raw record.

## Memory activity

Two aligned timelines show decision counts and observed reads for all captured
dreams through the open dream. Both fit the section width without a horizontal
scrollbar or time-window controls. Labels become sparse as history grows, while
missing observations retain visible gaps. The same composition adapts to narrow
screens. A compact dream selector with **Previous / Next** controls provides exact
local selection even when a dense chart cannot give every cycle a large target.

Selecting a cycle updates a concise local summary without changing the archive
selection or shortening the chart. Additional detail retains exact
decision categories, observed file changes, fact-count change, verification, captured
rigor, and the usage window. **Open this dream** remains a separate archive
navigation action. Categories are preserved, including unfamiliar captured actions;
decisions are never called file writes, and activity does not infer productivity.
Missing observations remain gaps. A disclosed table preserves historical values,
timestamps, cadence, rigor, and each usage window. Overlapping windows are never
summed into a recall total.

## Changes and decisions

Each ledger row leads with its recorded action, lesson name, and reason. Captured
diffs remain directly accessible from the lesson. A **Decision details** disclosure
holds the scope, tier, full citation, and declared files; the citation no longer
relies on a truncated label or pointer-only tooltip. Rows preserve their original
order and exact action categories.

Diffs without a corresponding narrated decision appear in a separate **Other
observed file changes** list. Its label distinguishes physical observations from
model decisions while keeping every captured diff reachable. Missing decisions and
missing diffs have explicit states. Mobile rows keep the action above the lesson
name, with long citations and filenames wrapping inside the section.

## Implementation and reproduction

- `dashboard.template.html`: stable header/archive infrastructure and section markup/styles.
- `dashboard.network.js`: network normalization, ranked layout, view selection, and captions.
- `dashboard.sections.js`: outcome, captured voice, health/evidence, and activity rendering.
- `render_html.py`: bundles both vanilla-JavaScript modules inline and safely embeds JSON.

The renderer resolves assets relative to its installed script directory, rejects
script-end sequences in a bundle, and requires each bundle marker exactly once.
There are no new runtime dependencies. The browser tools remain development-only.

```bash
python3 tests/dashboard_fixture.py --out /tmp/cm-preview
python3 tests/dashboard_browser.py --out /tmp/cm-browser
python3 tests/network_identity.py
python3 tests/smoke.py
python3 tests/simulate_accumulation.py
mypy --config-file mypy.ini
python3 tests/validate_manifests.py
python3 tests/concurrency.py
python3 tests/bench_phase5.py --quick --json /tmp/cm-bench.json
```

The browser suite checks the actual SVG for label collisions, coincident branches,
project-box intersections, and detours; exact membership; 125-project reachability;
320/390/768/1440px layouts in all themes; keyboard/diff/archive behavior; rich/sparse
navigation; malformed arcs; missing/zero observations; print; hostile text; and offline
operation. The frozen header geometry fixture was captured from v0.4.16 before the
redesign for ordinary, sparse, historical, over-target, and ceiling cases.

[Download the fictional archive](previews/nocturne/index.html) and open `#sel=7`.
Its companion JSON, screenshots, and SVG contain fictional data only. A supplied
personal archive is regenerated separately by replacing its presentation while
retaining its entire existing JSON payload and selection link; it is never
copied into this public repository.

## Local validation, 2026-09-05

Validation applies to the working tree based on `fad663f` (v0.4.17):

| Gate | Result |
| --- | --- |
| Smoke, including canonical identity regressions | 1,688 passed, 0 failed |
| Chromium | 1,101 passed, 0 failed |
| Lifecycle simulation | All properties through probe AG hold |
| mypy | No issues in 40 source files |
| Manifest checks | Portable checker and strict Claude CLI validation pass |
| CLI status | `cm status` passes |
| Concurrency | 15 passed, 0 failed |
| Quick capacity benchmark | Both SLOs pass; worst beacon p99 75.4 ms, no-change pull 144.5 ms; peak RSS 36,148 KB |

The browser matrix covers 320, 390, 768, and 1440 pixels in all four themes,
reduced motion, print, offline rendering, and hostile text. Activity cases include
47, 120, and 500 dreams: the chart fits without scrolling, missing observations
remain gaps, and every dream remains accessible through the selector and keyboard.
Evidence cases include pending workflows, missing-versus-zero values, full citations,
real diff destinations, long scrollable diffs, archive links, and rich/sparse
navigation. Control checks cover target sizes, hover/focus/disabled states, and
matching destinations rather than appearance alone.

The header graph is compared with the frozen v0.4.16 fixture for ordinary, sparse,
historical, over-target, and ceiling cases. The checks preserve its SVG geometry,
calculation blocks, and styles; screenshot comparisons account for page position
when navigation wrapping changes the surrounding layout.

Public previews and screenshots contain fictional data only. The regenerated
personal preview preserves all 47 captured cycles byte for byte, including its
original selection link. Desktop and mobile previews have been visually inspected.
Canonical-identity regressions retain coverage for differently named mirrors of
one fact, distinct domains, ambiguous identities, and bounded capture. These are
local validation results, not a release or hosted-CI claim.

## Separate follow-ups for the next PR

1. **Registry inventory:** include enrolled projects with no shared mirrors as a
   separately labeled population. Keep physical holdings, registry presence, and
   missing/unreadable stores distinguishable.
2. **Comprehensive archive-size policy:** replace quadratic compatibility edges
   and define a complete payload budget across incidence, nodes, groups, evidence,
   cycle count, and diff sidecars. This change bounds new incidence only; existing
   compatibility-edge and archive-size policies remain in force.
