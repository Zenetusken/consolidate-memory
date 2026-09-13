# The summary graph's closed loop (0.4.27 spec)

**Design-of-record for the network map's selection, navigation and escape.**
Status: implemented, mutation-verified, gates green — pending merge. Reverses the interaction
surface shipped by `b665ffc` (v0.4.18), which deleted three wirings and left the map a closed
loop.

Citations here are **greppable anchors**, not `file:line` — the v0.4.25 rule. Quote the anchor
into a grep and it resolves; line numbers rot within a release.

## 1. Context

**Reported:** *"every click on the graph is incoherent; we cannot navigate it or get any
information out of any of the nodes."* That read is accurate, and it resolves to five defects
that compounded into one user-visible property: **the map answered a question the user had not
asked, then gave them no way to leave.**

### 1.1 The correction that shrank the fix

An earlier draft of this work proposed marking the rendered members. That premise was **false**,
and measuring it first is why the change is smaller than it looked. In `dashboard.network.js`:

```js
var selected=selectedNodes(), matching=selected.filter(matches);
var domains=state.kind==='fleet'?model.domains:model.domains.filter(function(d){return selected.some(...d);});
```

`all ⊆ matching ⊆ selected`, and `matches` is the **search** predicate — true for everything when
the query is empty. The domains are derived **from** the selection, not the reverse. So
**rendered ≡ selected in every view**: the map is exactly its own selection, always.

Marking the rendered members is therefore degenerate in *every* view — it says "these are the
things you can see". The only genuine 1-of-N distinction the map can draw is **anchor vs.
members**, and that mark already existed as `[data-current="true"]`. It was wired to the wrong
predicate. Fixing the predicate touches neither `selectedNodes()` nor the render filters, so **no
rendered set changes**, and the five anti-duplication pins stay green untouched.

### 1.2 The five defects (each measured, not reasoned)

1. **The anchor marked the wrong node.** `data-current` was set from
   `truthy(n.raw.trigger)` — the *fleet capture trigger*. So clicking `atlas-web` left
   `atlas-api` stroked, tinted and labelled **"This project"**, while the heading named the
   project actually selected. In fact/group views the same mislabel applied.
2. **Three equal-specificity rules fought, and the palettes order them oppositely.**
   `[data-current="true"] rect`, `.selected rect` and `:hover/:focus rect` are
   same-specificity, so source order decides — and the two shipped palettes emit them in
   **opposite** order. Consequence: the same click behaved differently per theme, and in the
   theme that puts hover last the **hover cue repainted the anchor exactly while the pointer was
   on it**, erasing the mark at the moment of pointing.
3. **Focus was stolen on every draw.** `focus()` ended with an unconditional
   `.network-root` `.focus()`, and it runs *after* `draw()`'s own `[data-key]` restore — so it
   clobbered the restore and left focus on the root. The root's handler is `reset()`, so **the
   next Enter undid the activation**. The guard is now a *fallback*: it fires only when
   `activeElement` is `<body>`/`<html>`, the real stranded case (a fact button whose element
   `inspect()`'s `innerHTML` rewrite destroys). Not `!document.activeElement` — Chrome sets
   `activeElement` to `<body>`, never `null`.
4. **No position and no way back.** `#net-breadcrumbs` was created and cleared but never
   written; `b665ffc` deleted the writer. Its CSS was intact and idle.
5. **Focused views rendered no summary at all.** `inspect()` replaces `#net-detail`'s
   `innerHTML` on **every** draw, destroying the template's seeded instruction — so the
   explanation was assigned only in the project/fact/group branches and the fleet rendered an
   attribution span and nothing else.

Nothing led out of the loop: the interaction state is consumed only by its own redraw.

## 2. The changes

### 2.1 The anchor means what it says

`data-current` becomes the view's anchor node: fleet → the capture trigger (unchanged, correct
there); project → `n===state.value` (the fix); fact/group → **no node**, because neither view has
a node anchor and today's trigger mark is the same mislabel.

The relation text stops lying with it: in a project view the anchor reads `This project` and the
rest `Recorded connection` — not the previous `Select to explore`, which was false for things
already on screen.

The cascade is scoped so the states compose instead of overwriting: the hover/focus cue changes
`stroke-width` only and is restricted to `:not([data-current="true"])`, so `[data-current]` keeps
its `--data` stroke and `.selected` keeps its tint under the pointer while hover still answers.

### 2.2 Navigation

The trail is written in focused views only — `Captured fleet › kind › label` — with the leading
crumb a real activation target that returns to the fleet. It is deliberately **not** a
focus-restore target: `draw()` searches `svg.querySelectorAll('[data-key]')`, i.e. SVG-only, so
nothing outside `<svg id="net">` can ever be restored; the crumb carries its own `tabindex` via
`activate()` instead.

Node focus keys moved off the positional `'project:'+i` onto stable identity — a positional index
surviving a repaint lands focus on a *different* project.

### 2.3 The escape hatch

A compact selection summary renders in `#net-detail` as a `<dl>`, designed **to** the existing
`concise_network` guard rather than around it: that pin already forbids `details`/`table`/`pre`/
`.inspector-row`/`.network-holders`/`.network-members` and the removed inspector's label
vocabulary inside `#net-detail`, and a `<dl>` of readable selection rows collides with none of it.

Two content rules, both pre-existing and both enforced:

- **Absence ≠ emptiness.** `Not captured` is a field the snapshot never recorded; `None recorded`
  is a measured empty. The summary reads `raw` rather than the normalized node, because
  `normalize()` collapses an absent field to `'unknown'`/`[]` and would misreport absence as a
  captured value.
- **No zero ever renders.** A count is a number only when `> 0`, else `None recorded` — which
  satisfies the `'0 projects'` prohibition by construction rather than by wording luck.

A link leads out to the complete record. It reuses `reveal(id)` — the page's one "un-collapse,
open `<details>` ancestors, scroll, focus" routine — newly exported from
`dashboard.sections.js`, guarded on capability so a bundle without it renders **no link** rather
than a dead button. Styled `inspector-choice`, it inherits the ≥43.5px hit-area gate for free.

### 2.4 The legend is updated, not replaced

`inspect()` previously overwrote `#net-legend`'s children wholesale, orphaning the template's dot
markup. Since `data-current` is now load-bearing, the interpretation string says what the mark
means, and the template's dot keys are **wired** rather than deleted — `smoke.py` pins
`"this project</span>"` in the template source, and a pin on markup nothing renders is exactly
the fossil this pass exists to clear. The dots describe the fleet's node roles, so they hide in
focused views where no node is "this project".

One genuinely orphaned element was removed rather than wired: `#net-leg-stack` shipped `hidden`,
was read by nothing, and was unhidden by nothing — there was no behaviour to restore, so keeping
it would have been the same fossil under a new name.

### 2.5 Two strings that promised dead interactions

Both were corrected to describe what actually happens. `#net-detail`'s seeded text said *"Select
a project **or connection**"* — connections have no handler. And `#net-controls`'s `aria-label`
read *"Highlight network membership"*, which describes a control the group no longer contains; it
now names what is there (*"Network view and position"*).

## 3. Invariants

- **Rendered ≡ selected.** No view draws a complement, so there is nothing to dim and no
  "unselected" state to style. This is now a stated invariant, not a lucky coincidence.
- **`.selected` and `[data-current]` are mutually exclusive.** `.selected` is applied only by the
  group view; an anchor exists only for fleet (trigger) or project (`state.value`). **Any
  `.selected[data-current]` rule is dead on arrival** — two such rules were found and removed
  this pass, and their comments now state the invariant instead of pretending the state exists.
- **One 1-of-N mark per view.** The anchor is the only node distinguished within its own view.
- **Absence and emptiness never collapse**, and a count never renders as a bare `0`.
- **Focus survives the activation that caused the redraw**, or lands on a real control — never
  stranded on `<body>`.

## 4. Verification

Every pin below was **mutation-verified**: the corresponding defect was restored, the suite was
re-run, and the named check went red. A pin that stayed green would be vacuous and worse than
none. Harness: revert-one-change, restore, match the expected failing check by its exact string.

### 4.1 Browser suite — 9/9 RED

| # | Defect restored | Check that failed |
| --- | --- | --- |
| M1 | anchor marks the capture trigger, as before | `a pointer click re-anchors the graph to the clicked project, not the capture trigger` |
| M2 | `focus()` steals focus back to the root | `keyboard activation reaches the activated project and keeps focus on that node` |
| M3 | hover cue unscoped from the mark (both palettes) | `deepfield focused keeps the anchor mark under the pointer while still answering it` |
| M4 | the record link stops calling `reveal()` | `the record link opens the complete captured record and lands focus inside it` |
| M5 | the trail writer never runs | `the position trail names the focused view and offers exactly one way back` |
| M6 | a measured zero renders as a bare `0` | `an unshared project reports absence as absence rather than as a measured zero` |
| M9 | the summary grows a fifth row | `project selection keeps the selection summary to a handful of paired rows` |
| M10 | the summary regrows an accounting row | `project selection presents a map and brief context without debugging panels` |
| M11 | a `dt` is emitted without its `dd` | `group view keeps the selection summary to a handful of paired rows` |

**M3 fails at `deepfield` specifically** — the theme whose source order puts hover last. That is
the defect in one line: the same interaction was coherent in one shipped palette and broken in
the other.

### 4.2 Smoke pins — 2/2 RED

| # | Defect restored | Check that failed |
| --- | --- | --- |
| M7 | a bundle applies the `.dim` class | `network: the .dim class keeps its claim` |
| M8 | the pointer path is deleted from `activate()` | `network: the activation primitive wires a pointer path and a keyboard path onto a button` |

M8 is a **strengthening of an existing pin that was blind to it.** The old assertion was
`"function activate" in _TEMPLATE_SRC` — a substring that survives its own function being
gutted, so the deletion of `n.addEventListener('click',fn)` left it green.

### 4.3 Two pins that had to be debugged before they were believed

Both are recorded because the failure mode is silent — **a vacuous pin reads exactly like a
passing one.**

- **The hover pin passed with the defect in place.** Two causes: the anchor was still `:focus`ed
  from the click that opened the view, and both palettes bundle the cue as `:hover, :focus` in
  ONE rule, so the "rest" reading was already repainted; and the click had left the pointer on
  the graph. Fixed by parking the pointer (`page.mouse.move(0,0)`) **and** blurring
  (`#net-view` focus) before reading, then asserting two-sidedly — the mark holds **and** hover
  still answers on width, so deleting hover feedback outright cannot pass either.
- **The `.dim` guard's first draft had the same match-set bug as the pin it replaced.** It listed
  three literal spellings (`'dim'`, `"dim"`, `"net-node dim"`), and a mutation writing
  `class:'dim net-node'` walked through all three. The bundles compose class strings with `+`, so
  the token can land at either end of a literal. The match set is now "a quoted string containing
  `dim` as a whole word".

A third near-miss is worth recording: the first M9 mutation added a row labelled `Registry
baseline`, which the forbidden-labels check already rejects — so it went red, **by the wrong
pin**, proving nothing about the ceiling. It was rewritten with a calm label (`Last capture`) that
only the budget can catch.

### 4.4 Gate results

| Gate | Result |
| --- | --- |
| `tests/dashboard_browser.py` | **1264 passed, 0 failed** (was 1257; +7 = the new summary budget check at its seven call sites) |
| `tests/smoke.py` | **1794 passed, 0 failed** — census constant `1750 + 44` |
| `tests/docs_links.py` | pass — preview regenerated |
| mutation harnesses | 9/9 browser RED, 2/2 smoke RED |

### 4.5 Archive embed budget — measured, not reasoned

The P4 pin asserts `len(_html_p4) < 300 * 1024`. Measured against the same 120-cycle fixture:

| Tree | Bytes | Headroom | Share |
| --- | --- | --- | --- |
| `HEAD` (pre-fix) | 285,411 | **21,789** | 7.09% |
| this pass | 297,637 | **9,563** | 3.11% |

**This pass cost 12,226 characters — 56% of the previously recorded headroom.** The pin holds,
but the margin is now thin enough to be a constraint on the next template pass, and the
pre-fix figure reproduces the 21,789 recorded at v0.4.24 exactly. Both numbers are re-derivable:
the fixture is `smoke.py`'s P4 block, verbatim.

## 5. Deliberately not fixed (found by measurement, recorded rather than silently changed)

- **`.node-name` / `.node-meta` are emitted by nothing.** The live classes are `project-label`
  (`--ink`) and `project-meta`, whose fill resolves to `--ink2` — **not** `--faint`. The `.dim`
  contrast analysis, `deep-field-theme.spec.md`, and two CHANGELOG entries all name the dead
  pair. The template comment now carries a `⚠ RE-DERIVE BEFORE REVIVING` note; only the split's
  *direction* survives its own derivation, since every magnitude was counted against a text child
  that never renders.
- **Base Nocturne's node *fill* declarations are shadowed dead code.** `#network-blk`-prefixed
  rules are unscoped and beat non-prefixed base rules on the ID in every theme, so the anchor has
  no fill distinction — it is marked by **stroke only** (`--data` 2.6px vs `--rule2` 1.1px,
  measured across default/nocturne/light). Judged legible: a bright 2.6px stroke plus three
  redundant textual cues. Re-tinting a shipped surface would need its own contrast gates.
- **The record link lands coarsely.** `#record-json` is one `<pre>` holding the whole record, so
  the landing is top-of-blob, not the node's entry. Narrowing via a `Range` is deferred: it means
  re-serialising with matching indentation or string-searching `"sid": "…"`, and the pin
  discipline demands a deterministic assertion.
- **Two live regions over rewritten content — minimum taken, restructure deferred.** `#net-detail`
  is `role="status" aria-live="polite"` and the inner `.network-explanation` was a second one, so
  every draw announced itself twice — including pager clicks that changed nothing. The inner
  `aria-live` is **dropped** (shipped); the outer `role="status"` is retained. A full restructure
  — a live region wrapped around the selection name only — is deferred: it is a DOM change with
  layout consequences across 5 themes × 4 widths that no gate here can assert.

## 6. Ship shape

A **patch** (`0.4.26 → 0.4.27`): a fix to a shipped artifact surface, backward-compatible, no
schema or CLI change. Per the release-coherence rule it ships immediately rather than batched.
Feature branch + PR; the maintainer reserves the merge.
