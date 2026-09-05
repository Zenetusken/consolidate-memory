# Nocturne: clear topology, accessible evidence

Nocturne is a self-contained, offline archive of recorded dreams. The four report
sections support progressive exploration: **dream summary → memory network →
memory activity → verification & health**, followed by the existing decision
ledger. The header remains the sole index-size and budget-projection chart.

The redesigned renderer preserves its original header markup, shared helpers,
calculations, and styles. Section navigation reflects the new order. Every figure
is captured evidence, not a live store query.

## Visual system

The midnight canvas, Glacier holdings, Iris permissions, restrained orbital mark,
and humanist system typography remain. Georgia italic belongs to captured dream
voice. Nocturne, Original, Light, and System themes, reduced motion, print, archive
filters, density, keyboard navigation, and the accessible diff dialog remain.
No fonts, scripts, stylesheets, or data are fetched from the network.

## Network exploration

A ranked SVG tree replaces domain containers and perimeter-routed pairwise edges.
Its initial root is the captured fleet. Every captured domain appears, including
an explicitly captured domain with no project rows. The triggering project's
domain starts expanded. Each domain has 12-project pages, and search reaches every
captured project by its name, domain, or stable store identity. No global first-16
cutoff remains.

Selecting a project exposes its costs, captured facts, and recorded pairwise
connections. Selecting a canonical fact produces **fact → domain → physical
holders**. Selecting a group produces **group → domain → captured members**;
permissions never center on an arbitrary project. Only those members appear in
the focused group tree. Breadcrumbs and reset return to the fleet.

Horizontal ranks use dedicated branch ports. A trunk is drawn once, junctions mark
its aggregate branches, and expanding a domain exposes the members. Mobile changes
to a vertical tree with separate fleet and domain rails; the evidence inspector
moves below it. Text labels, interaction names, and explanatory evidence accompany
color. Native disclosures retain complete inventories, addressed group facts,
registry baseline counts, and every embedded network field.

Historical archives use their recorded domains, projects, and pairwise links.
When canonical identities are absent, the inspector states that boundary. The
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

The dream is one connected **Sleep → intermediate passages → Wake** sequence.
Both bookends stay visible. Intermediate passages are selectable, and **Read the
complete dream** retains every captured text passage in order. Canonical phase
labels require exactly six nonempty string beats; other sequences use numbered
beats. Missing bookends and passages are explicit. The original record remains
available unchanged in the raw-data inspector.

## Verification and health

Compact summaries distinguish claims, store integrity, and observed changes with
four explicit states: **Needs attention**, **Recorded clear**, **Partially
captured**, and **Not captured**. There is no combined health score. Exceptions
come first and link to the relevant disclosure:

1. **Verification evidence** — recorded judgments and procedure-integrity findings.
2. **Store checks** — pointers, links, drift, preflight time and IDs, remediation,
   identity/registry state, and maintenance evidence.
3. **Observed file changes** — the measurement window, per-store observations,
   every per-file operation with diff access, and conservation evidence.
4. **Recall & workflow decisions** — usage windows, procedure exclusions, misses,
   recurring commands/chains, skill use, demotion, registrar states, and decline lineage.

Adverse or pending disclosures open by default. Preflight lists only its captured
timestamp and failure/warning IDs, without inventing individual check outcomes.
Unknown observations stay missing; actual zeroes stay zero. Complete evidence rows
are reachable through native disclosures. Long movement and declared-file lists
have working expansion controls instead of inert `+N more` labels.

## Memory activity

The lower stock/effort charts become aligned decision activity and observed reads,
with a categorical ribbon for captured rigor. The default window is the latest 12
dreams ending at the selected dream; **12 / 24 / All captured** controls change it.
Exact action categories remain intact, including unfamiliar captured categories.
Decisions are never called file writes, and activity does not infer productivity.

Selecting a cycle updates a local inspector: outcome, decisions, observed mutations,
fact-count change, verification, reads, and usage window. **Open this dream** is a
separate archive navigation action. Missing reads and rigor remain gaps. A disclosed
table preserves fact counts, timestamps, cadence, and each usage window. Overlapping
windows are never summed into a misleading recall total.

## Implementation and reproduction

- `dashboard.template.html`: stable header/archive infrastructure and section markup/styles.
- `dashboard.network.js`: network normalization, ranked layout, selection, and inventory.
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
retaining its entire existing JSON payload and `#sel=45` selection; it is never
copied into this public repository.

## Local validation, 2026-09-05

Validated against the working tree based on `ad3771f` (v0.4.16):

| Gate | Result |
| --- | --- |
| Smoke, including canonical identity regressions | 1,686 passed, 0 failed |
| Chromium | 320 passed; no browser errors or external requests |
| Lifecycle simulation | All properties through probe AG hold |
| mypy | No issues in 40 source files |
| Manifest checks | Portable checker and strict Claude CLI validation pass |
| Concurrency | 15 passed, 0 failed |
| Quick capacity benchmark | Both SLOs pass; beacon p99 130.0 ms, no-change pull 213.6 ms |
| Header comparisons | Identical SVG geometry in all 20 case/viewport combinations |

The header markup, shared helpers, calculation blocks, and pre-existing CSS were
also compared directly with the pre-edit source. Header pixels match in all 20
comparisons when captured at the same whole-pixel origin. In the natural page flow,
16 match byte-for-byte; four at 320px have subpixel raster differences caused by
section-navigation wrapping. The graph's own geometry and styles are unchanged.

The supplied archive's embedded JSON is preserved **byte for byte**, with all 46
cycles and `#sel=45`. Both regenerated archives were visually inspected on desktop
and mobile, including the focused group view; they render offline without errors.
The live read-only fleet check resolves the previously split stack fact to one
identity with ten holders and reports zero unresolved identities or fact-file read
failures. These local results are not a release or hosted-CI claim.

## Separate follow-ups for the next PR

1. **Registry inventory:** include enrolled projects with no shared mirrors as a
   separately labeled population. Keep physical holdings, registry presence, and
   missing/unreadable stores distinguishable.
2. **Comprehensive archive-size policy:** replace quadratic compatibility edges
   and define a complete payload budget across incidence, nodes, groups, evidence,
   cycle count, and diff sidecars. This change bounds new incidence only; existing
   compatibility-edge and archive-size policies remain in force.
