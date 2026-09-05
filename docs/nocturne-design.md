# Nocturne: a memory observatory

A presentation redesign for `consolidate-memory` v0.4.14. The design is implemented
in the bundled dashboard template and rendered with the existing Python renderer.
The example artifacts use fictional projects and synthetic cycle records, never a
personal memory store.

## The design direction

Memory needs two things to be useful later: a recognizable cue and evidence you can
return to. Nocturne uses an orbital recall mark, a midnight canvas, and a network
view whose structure explains where a lesson can travel. Charts and grants share a
visual language without pretending that a saved report is a live network monitor.

| Token | Value | Purpose |
| --- | --- | --- |
| Midnight | `#080f1b` | Main page background; most of the page remains dark and quiet |
| Deep blue | `#0c1727` / `#101e31` | Topology surface, domain containers, evidence sections |
| Cloud | `#e5eef5` | Primary text |
| Glacier | `#8fced6` | Observed shared-fact connections and active project |
| Iris | `#b3a6e4` | Group permissions, selected members, recall mark |
| Honey | `#e7bd78` | Attention and incomplete evidence |
| Rose / sage | `#f0a3a6` / `#9cd4b5` | Critical conditions / positive outcomes, always accompanied by text |

The theme control cycles through **Nocturne → Original → Light → System**. Original
retains all 19 color and tint tokens from the previous espresso dark palette. The
selection persists locally and applies before rendering; System follows the device
preference. Every mode prints with a light palette.

Typography uses locally available humanist system fonts (`Avenir Next`, `Segoe UI`,
Verdana, Arial). Monospace is reserved for commands and code. Georgia italic belongs
only to the captured dream narrative. No downloaded fonts or web requests are needed.

The main hierarchy is **project → context outlook → key measures → network →
history → verification and decisions → narrative**. The network gets one substantial
surface; the remainder uses readable sections and compact rows. This avoids a wall
of identical metric cards, decorative neon, fake activity, and perpetual animation.
The single chart trace on load and short group-selection transition answer actual
state changes; reduced-motion preferences disable both.

The initial plan considered a glowing central constellation. Source inspection
showed why that would be misleading: a hub can obscure domain membership and make a
group grant look like delivered data. The implemented SVG uses domain lanes and
explicit, selectable permission routes. The orbital motif stays in the brand mark;
the diagram spends its space on actual project labels and evidence.

## What inspection found

The old HTML was an editorial field report with warm paper/espresso themes, extensive
small monospace labels, and a small radial network beside the budget meters. Its
information depth was hard to discover. The README introduced architecture and a
comparison with another feature before making the practical value clear.

Live source and the baseline browser render also exposed presentation defects:

- The fleet painter dereferenced the first node even when no nodes were captured.
- Mobile archive rules hid index, write, and commit columns.
- The reset path hid workflow-chain and skill-usage containers; their render path
  populated them without restoring their visibility.
- Baseline chips lacked their own layout styling and visually ran together.
- The diff overlay did not manage keyboard focus or make the background inert.
- Sparse records could read as zero-cost, healthy results when measurements were absent.

These are corrected in the template. Store paths, admission policy, canonical writes,
cycle schema, log assembly, and the Python HTML renderer are unchanged.

## Preserve the evidence

Every pre-existing template element ID remains present. The existing calculation and
render paths remain for the following surfaces:

| Surface | Retained detail |
| --- | --- |
| Project identity | Domain/enrollment, registry health, conflicts, session, scope, generation time |
| Context outlook | Index history, target and ceiling, trajectory estimate, warnings |
| Indicators | Index percentage, recall facts, confirmed claims, effort, correction/unverifiable counts |
| History | Facts, writes by action, rigor categories, and inter-dream cadence |
| Budgets | Index, root/global `CLAUDE.md`, hierarchy cost, cliff/fat-hook detail |
| Cross-project movement | Pulls, promotions, refreshes, holds, GC, scope changes |
| Audit | Per-store and per-file mutations, token deltas, conservation warnings |
| Verification and health | Claims, pointer/link health, schema drift, orphans, maintenance, remediation |
| Usage | Organic reads, mentions, excluded procedure reads, archived-fact reads, top recalls |
| Workflows | Recurring commands, chains, skill use, verdicts, demotion, registrar candidates and decline lineage |
| Decisions | Entries, reasons, citations, declared files, unattributed observed diffs, capped-diff notices |
| Narrative and archive | Sleep/beats/wake, cycle selection, filtering, sorting, keyboard navigation |

The fleet view adds readable domain containers, full node names on inspection,
keyboard/touch inspection, group selection, and tables of every embedded node,
group, and edge. The diagram is bounded to 16 nodes; the complete **captured**
inventory remains available. Existing emitter caps are not widened. Legacy networks
use the retained legacy painter and expose their captured data below it.

A collapsed JSON inspector makes the complete embedded cycle accessible, including
fields omitted from abbreviated rows. It is an inspection surface, not a new data
source. Unavailable budget, audit, usage, and verification measurements are marked
explicitly; recorded problems remain visible. Domains can legitimately yield partial
fleet baseline counts.

## Artifacts and reproduction

- [Self-contained HTML archive](previews/nocturne/index.html) — download and open it;
  append `#sel=7` for the latest illustrative cycle.
- [Nocturne network screenshot](assets/nocturne-dashboard.png).
- [Original dark-palette screenshot](assets/original-dashboard.png).
- [Exported runtime network SVG](assets/nocturne-network.svg).
- [README policy topology SVG](assets/network-topology.svg) — includes the local-only repo.
- [Brand banner](assets/nocturne-banner.svg).
- [Synthetic fixture source](../tests/dashboard_fixture.py).

```bash
python3 tests/dashboard_fixture.py --out /tmp/cm-preview
python3 tests/dashboard_browser.py --out /tmp/cm-browser
```

The second command needs Playwright and its Chromium binary **as development tools**.
It runs in a separate Chromium CI job and does not add dependencies to the plugin
or the stdlib-only CI gate. The test
launches a headless browser against local generated files, with no store reads or
cycle persistence.

## Validation

At this working-tree checkpoint:

| Gate | Result |
| --- | --- |
| Zero-dependency smoke suite | **1,620 passed, 0 failed** |
| Lifecycle accumulation simulation | **All lifecycle properties hold** |
| Mypy | **No issues in 38 source files** |
| Portable manifest checker | **Passed** |
| Claude CLI strict plugin validation | **Passed** |
| Real Chromium browser checks | **127 passed** |
| Original template IDs | **79 preserved; none removed** |
| Process-level concurrency | **15 passed, 0 failed** |
| Known-defect beta gate | **Clean; canary and cycle-probe self-tests passed** |
| Isolated network CLI walkthrough | **44 successful commands** |
| Isolated migration walkthrough | **18 checks passed: 15 successful commands and 3 expected refusals** |
| Relative document links and SVG XML | **46 links valid; all SVGs parse** |

Browser checks cover the complete record, legacy/sparse/local-only states, empty and
single-node fleets, a 25-node fleet, malicious text, ceiling/integrity warnings,
archive navigation/filter/sort, section and group controls, diff focus trapping and
restoration, Nocturne/Original/Light/System modes, reduced motion, print colors, and no external
requests. Layout is checked at 320, 390, 768, and 1440 pixels. All-pair SVG routes
are checked against unrelated node boxes across balanced and uneven 16-project
layouts. An independent review also exercised 2,332 observed and permission routes
across 30 layouts. Horizontal diagram and table scrolling preserves data at narrow widths. Screenshots were inspected in
addition to DOM assertions.

The old geometry/color source pins were updated to the new presentation. Original
also has an exact 19-token preservation assertion against the previous palette. Text and
semantic colors now have a **calculated 4.5:1 contrast check** against every theme's
main surfaces, instead of an assertion that particular historical hex values exist.
Single-domain visibility is also exercised in Chromium. The fixture validates its
own audit totals and history continuity, and compares its topology payload with
the real engine emitter using synthetic canonical records.

The CLI walkthrough exercised doctor, enrollment plans and grants, group creation and
membership, pull, topology inspection, conflicts, and member removal against disposable
projects under a separate `CLAUDE_CONFIG_DIR`. It did not author a fact or touch live
operator grants. Canonical authoring syntax was checked against the command source;
the placeholder draft is intentionally not executed. A separate isolated legacy-store
fixture exercised two-domain assignments, exclusion, validation, application, rollback,
reapplication, and finalization, including refusals for an unenrolled caller,
unresolved assignments, and rollback after finalization.

These are local checks, not a hosted CI or release certification. Browser behavior
was exercised in Chromium; Safari and Firefox were not tested. Token forecasts remain
heuristics from the original renderer, not measured savings or promises of recall.

## Research and source traceability

The README follows GitHub's recommendations to explain what a project does, why it
is useful, and how to get started. It uses repository-relative assets/links, restrained
alerts, a navigation scaffold, and a fenced Mermaid workflow. See
[About READMEs](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-readmes),
[GitHub formatting](https://docs.github.com/en/get-started/writing-on-github/getting-started-with-writing-and-formatting-on-github/basic-writing-and-formatting-syntax),
and [diagrams](https://docs.github.com/en/get-started/writing-on-github/working-with-advanced-formatting/creating-diagrams).

The dialog uses focus management and background inactivation alongside modal
semantics, as described in [MDN's aria-modal guidance](https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Reference/Attributes/aria-modal).
Motion respects the [prefers-reduced-motion media query](https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/At-rules/%40media/prefers-reduced-motion).

Product behavior was traced through the local [command workflows](../plugins/consolidate-memory/commands),
[delivery policy](../plugins/consolidate-memory/scripts/domain_policy.py),
[group operations](../plugins/consolidate-memory/scripts/cm_ops.py),
[stack relevance and topology emitter](../plugins/consolidate-memory/scripts/sync_global.py),
[cycle schema](../plugins/consolidate-memory/scripts/memory_status.py),
[HTML assembly](../plugins/consolidate-memory/scripts/render_html.py), and
[template](../plugins/consolidate-memory/scripts/dashboard.template.html).
The privacy copy distinguishes local scripts from reasoning through Claude Code's
configured model service; it no longer claims the entire agent session is offline.
