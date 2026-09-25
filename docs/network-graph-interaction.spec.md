# The summary graph's closed loop (0.4.27 spec)

**Design-of-record for the network map's selection, navigation and escape.**
**Status: SHIPPED (v0.4.27)** — verified against `CHANGELOG.md` §v0.4.27, which names this spec. ⚠ The retired line stated a done-state AND an UNFINISHED one — ⚠ the two words of this very annotation would themselves match the detector, so it is worded around its own vocabulary; that contradiction release's A1 arm was written for.

> **Drafting-era status — never revisited after the arc closed.** Preserved VERBATIM:
>
> Status: implemented, mutation-verified, gates green — pending merge. Reverses the interaction
> surface shipped by `b665ffc` (v0.4.18), which deleted three wirings and left the map a closed
> loop.

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

`rendered ⊆ all ⊆ matching ⊆ selected`, and `matches` is the **search** predicate — true for
everything when the query is empty. The domains are derived **from** the selection, not the
reverse. So **no view can render a node the selection does not contain**.

The subset is *strict* in the default view, and an earlier draft of this section wrote `rendered ≡
selected` — a hedge dropped from a direction that is true. The render path collapses every domain
that is not expanded, and pages any domain holding more than twelve matching projects, so a
collapsed fleet renders fewer nodes than it holds: measured, the fixture's seven nodes render as
three until the collapsed domains are opened. The argument below needs the direction, not the
equality — every rendered node is a member, so no view can show a node the selection lacks, and
there is no complement on screen for a `.dim` rule to mark.

Marking the rendered members is therefore degenerate in *every* view — it says "these are the
things you can see". The only genuine 1-of-N distinction the map can draw is **anchor vs.
members**, and that mark already existed as `[data-current="true"]`. It was wired to the wrong
predicate. Fixing the predicate touches neither `selectedNodes()` nor the render filters, so **no
rendered set changes**: every check that asserts a view renders an exact node set — `overlapping
groups do not retain previous members`, `small focused view names both holders without unrelated
project totals`, `focused fact … leaves exact holder names on the graph`, and the pagination
checks — is green, and none of them was edited by this pass.

### 1.2 The five defects (each measured, not reasoned)

1. **The anchor marked the wrong node.** `data-current` was set from
   `truthy(n.raw.trigger)` — the *fleet capture trigger*. So clicking `atlas-web` left
   `atlas-api` stroked, tinted and labelled **"This project"**, while the heading named the
   project actually selected. In fact/group views the same mislabel applied.
2. **Three equal-specificity rules fought.** `[data-current="true"] rect`, `.selected rect` and
   `:hover/:focus rect` are all (1,2,1), so source order decides — and the hover rule, being last,
   wins: its `fill:var(--paper2)` **repainted the anchor exactly while the pointer was on it**,
   and on a **selected** node it overwrote both halves of the mark. (Measured in `deepfield`: the
   anchor's `--data` stroke and 1.8px width held — its plate moved, not its mark — while a selected
   node lost `--tint-accent` and `--accent` both.)

   **Corrected:** this bullet claimed the two shipped palettes emitted those rules in *opposite*
   order, so "the same click behaved differently per theme". That cannot happen. The palettes are
   the four `:root[data-theme=` blocks near the top of the template's `<style>` (`nocturne`,
   `original`, `light`, and the `prefers-color-scheme` `auto` — that literal is one hit per
   palette, four lines), ~430 characters each, and they
   contain **no `.net-node` rule at all** — they declare tokens, nothing else, and a token-only
   theme mechanism cannot reorder rules. Every node rule exists exactly once, in shared CSS: the
   anchor rule in each of the two scopes — `#network-blk .net-node[data-current="true"] rect` is a
   single line, while the un-scoped `.net-node[data-current="true"] rect` is two, one per scope,
   its own line and that scoped copy — so the order is identical in all five
   themes. The defect was real and **theme-independent**: every theme was broken in the same way.
3. **Focus was stolen on every draw.** `focus()` ended with an unconditional
   `.network-root` `.focus()`, and it runs *after* `draw()`'s own `[data-key]` restore — so it
   clobbered the restore and left focus on the root. The root's handler is `reset()`, so **the
   next Enter undid the activation**. The first fix narrowed it to a *fallback* — fire only when
   `activeElement` is `<body>`/`<html>`, the stranded case, and not on `!document.activeElement`,
   since Chrome sets `activeElement` to `<body>` and never `null` — but it placed that fallback
   **inside `focus()`**, which covers one of the two activations that need it and misses the
   sibling with the same shape. The review round caught that; the repair now lives in `draw()`
   (§2.6).
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
focus-restore target: `draw()` searches `svg.querySelectorAll('[data-key]')`, i.e. SVG-only — all
four key-holders (`root`, `domain:`, the node key, `page:`) are `<svg>` children — so nothing
outside `<svg id="net">` can ever be restored.

**That observation was true, and the conclusion drawn from it was false.** The first draft argued
the crumb needs no restore *because it cannot be a restore target*, and added that it "carries its
own `tabindex` via `activate()`" — which it does not: it is a native `<button>` built by
`button()`, focusable without `tabindex`, activating through `onclick` (so Enter synthesizes the
same click; one handler, not two). `activate()` is never called on it. "Not restorable" is not
"not destroyed": `draw()` empties `#net-breadcrumbs` on the very activation the crumb carries, so
the button is gone and focus lands on `<body>`. Being outside the SVG is precisely what made it
unreachable by the restore pass — and therefore precisely what made it strand. See §2.6.

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

### 2.6 The focus repair moves to the redraw

`draw()` ends with two steps that must not be conflated. `focusKey`, captured before
`svg.textContent=''`, identifies a control the redraw will **rebuild**, so the restore pass at the
tail can hand focus to its successor. But every `data-key` holder is an `<svg>` child, so that pass
describes SVG controls only. Two controls live *outside* `<svg id="net">` and are wiped by the very
activation they carry:

| Control | What destroys it |
| --- | --- |
| a fact button in `#net-detail` | `inspect()` replaces the region's `innerHTML` |
| the trail's back-control | `draw()` empties `#net-breadcrumbs` |

The second one shipped landing focus on `<body>`, because the repair sat in `focus()`, which only
the first one passes through. The repair therefore keys on a second captured fact — `hadFocus`,
true when a real control held focus *before* the redraw — and fires when nothing inherited it:

```js
if(hadFocus&&(document.activeElement===document.body||document.activeElement===document.documentElement))
  svg.querySelector('.network-root').focus({preventScroll:true});
```

`hadFocus` is the whole reason this can live in `draw()` at all: `<body>` is `activeElement` at the
initial paint too, so a bare check would have the map seize focus on every page load and on every
per-dream archive repaint. "A control *had* focus and nothing took it" is the stranded condition;
"nothing is focused" is not. `keepControl` — the flag that existed only to suppress the old
fallback on the `<select>` path — goes with it: the select is never rebuilt by `draw()`, so focus
never leaves it, and the guard answers the question the flag was standing in for.

## 3. Invariants

- **Rendered ⊆ selected — a subset, strict in the default view, never a superset.** No view can
  render a node the selection does not contain, so no complement is ever on screen for a `.dim`
  rule to mark and there is no "unselected" state to style. This is a stated invariant, not a lucky
  coincidence. **Corrected:** this line read `rendered ≡ selected`, which is false the moment a
  domain is collapsed — the fixture's seven nodes render as three until the collapsed domains are
  opened. §1.1 carries the derivation; the argument here needs the direction, not the equality.
- **`.selected` and `[data-current]` are mutually exclusive.** `.selected` is applied only by the
  group view; an anchor exists only for fleet (trigger) or project (`state.value`). A
  `.selected[data-current]` rule would therefore be dead on arrival, and **there is none**.
  **Corrected:** this bullet read *"two such rules were found and removed this pass"*, which is
  false — no such rule existed at any revision. The pass added `:not([data-current="true"])` guards
  to two rules that *did* exist — each on two lines, one per scope: the un-scoped
  `.net-node:not(.selected):not([data-current="true"])` hover/focus pair (a hit per `:hover` and
  `:focus` arm, so four occurrences over those two lines) and
  `.net-node.selected:not([data-current="true"])` (two occurrences) — plus a comment
  stating why the state cannot arise. The distinction is the point: "we removed a dead rule" and "we
  documented why one cannot exist" are different claims, and only the second is true.
- **One 1-of-N mark per view.** The anchor is the only node distinguished within its own view.
- **Absence and emptiness never collapse**, and a count never renders as a bare `0`.
- **Focus survives the activation that caused the redraw**, or lands on a real control — never
  stranded on `<body>`. Enforced **once, at the redraw** rather than per control (§2.6), because
  the condition is a property of what the redraw destroyed, not of which control was clicked.
  Guarded on `hadFocus`, so a redraw nobody was focused in — the initial paint, the archive's
  per-dream repaint — never seizes focus.

## 4. Verification

Every pin below was **mutation-verified**: the corresponding defect was restored, the suite was
re-run, and the named check went red. A pin that stayed green would be vacuous and worse than
none. Harness: revert-one-change, restore, match the expected failing check by its exact string.

### 4.1 Browser suite — 12 of 13 RED (M12 is the exception, and is §4.3)

| # | Defect restored | Check that failed |
| --- | --- | --- |
| M1 | anchor marks the capture trigger, as before | `a pointer click re-anchors the graph to the clicked project, not the capture trigger` |
| M2 | the redraw steals focus back to the root | `keyboard view selection reaches the final sharing group without losing select focus` |
| M3 | hover cue unscoped from the mark (both rule families) | `deepfield focused keeps the anchor mark under the pointer while still answering it` |
| M4 | the record link stops calling `reveal()` | `the record link opens the complete captured record and lands focus inside it` |
| M5 | the trail writer never runs | `the position trail names the focused view and offers exactly one way back` |
| M6 | a measured zero renders as a bare `0` | `an unshared project reports absence as absence rather than as a measured zero` |
| M9 | the summary grows a fifth row | `project selection keeps the selection summary to a handful of paired rows` |
| M10 | the summary regrows an accounting row | `project selection presents a map and brief context without debugging panels` |
| M11 | a `dt` is emitted without its `dd` | `group view keeps the selection summary to a handful of paired rows` |
| M12 | the node focus key reverts to the positional index | **nothing — see §4.3** |
| M13 | the redraw restores no focus at all | `keyboard activation reaches the activated project and keeps focus on that node` |
| M-D1 | the redraw stops repairing stranded focus (*the crumb's pre-fix shape*) | `the trail back-control hands focus to a control in the widget, not to body` |
| M-D2 | the selection summary `<dl>` is never built | `group view keeps the selection summary to a handful of paired rows` |
| M14 | the crumb's handler is inert (`button(…,function(){},…)`) | `the trail back-control returns to the fleet and leaves no trail behind` |

**M3 fails in all five themes, not one.** An earlier draft of this section recorded it as failing
"at `deepfield` specifically" — the draft's "the theme whose source order puts hover last", a
premise §1.2 already retires (no palette carries a `.net-node` rule for order to decide). That was
an artifact
of the runner, not a measurement: `check()` raises on the first failure and the theme loop starts
at `deepfield`, so the first theme tested is the only one a single run *can* report. Re-run with
the failure made non-fatal, the check goes red in `deepfield`, `nocturne`, `original`, `light` and
`auto` alike — five failures, one per theme. The mechanism recorded beside it was right (the cue
was unscoped, so it repainted the anchor's plate wherever it fired); the *specificity* was invented
by the harness. One-theme-only was the attractive story. The measurement says the hover cue
repainted the anchor in every palette the plugin ships.

**The runner aborts on the first failure, which is load-bearing for reading this table.** Each row
names the check that went red *first* for its defect, not the only check that can see it — several
defects trip more than one. And a row is silent about what the suite *cannot* see: with M1
restored, exactly **one** check in 225 goes red. The focused pass in the theme loop cannot tell the
two predicates apart, because it re-selects the fleet and then clicks
`.net-node[data-current="true"]` — under the old predicate that is the *trigger* project, so both
schemes mark the same node in that view. Same shape as M12 (§4.3): the fixture makes two
implementations coincide. M1's coverage is a single check, and that is the honest number **for this
round's suite** — the re-audit round's own pins take it to four (§4.7, M15), by adding the two
fixtures where the two predicates cannot coincide.

**M2's row names the `<select>` pin, not the node pin.** An unconditional focus at the redraw also
strips the select that drove the view change, and that check sits earlier in the suite, so it is
the first to fire — the mutation is caught either way. M13 is what exercises the node pin; M2 alone
would leave it looking untested. M-D1 and M-D2 are the review round's mutations (§4.6), and M-D1 is
the *same two lines* as M2 mutated the other way: M2 widens the repair to unconditional (focus
**theft**), M-D1 deletes it (focus **stranding**).

**M-D1 also reds `switching from keyboard to pointer removes the graph focus rectangle and strands
no focus on body`** — and that is that check's real teeth: the existence of the fallback, not the
guard on it. M2 does **not** kill it. Pre-fix, `focus()` focused the root in exactly that
situation, so the check was green *with the focus-theft defect in place*. A pin can be sound and
still not cover the defect its wording suggests; this one is sound and its row is M-D1.

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
  from the click that opened the view, and both rule families bundle the cue as `:hover, :focus` in
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

Two more came out of the review round. Neither is a defect in a pin; both changed what the table
above is allowed to claim.

- **The harness read a catch as a miss.** M2's mutation *was* caught — by a neighbouring pin that
  fires first — and a two-verdict runner (holds / vacuous) called it "vacuous", because its matcher
  was a substring test against one expected name. This is the `gate-coverage-is-its-match-set` trap
  one level up: the harness's own match set decided the verdict, not the gate. A mutation caught by
  a pin the entry did not predict is **caught**; folding that into "vacuous" is a falsehood told by
  the instrument. The runner now reports three states, and M2's expectation names the pin that
  actually fires.
- **M12 found a coverage gap, not a vacuous pin.** Restoring the positional focus key
  (`'project:'+i`) breaks **no** check. The fixture leaves the anchor at the same index in the fleet
  and in the project view, so the positional restore lands on the right node by coincidence and the
  suite cannot distinguish the two schemes at all. The stable key is still the correct key — a
  positional index surviving a repaint lands focus on a *different* project — but that claim is
  **uncovered**, and the honest place to record that is here, rather than in a table row implying a
  mutation proved it.

### 4.4 Gate results

**Every gate below was run on the tree that ships** — the worktree carrying all four rounds'
changes, which is the artifact. The *assembled* tree belongs to an earlier point in the story: the
review round's repairs were authored in two places, so until that round was assembled no tree on
disk *was* the artifact, and the gate table was written under that constraint (§4.5). Both halves
are one tree now, and the figures below are that tree's.

| Gate | Result |
| --- | --- |
| `tests/dashboard_browser.py` | **1334 passed, 0 failed** |
| `tests/smoke.py` | **1795 passed, 0 failed** — census constant `1750 + 45`, which is `origin/main`'s `1750 + 43` **+2**: the `.dim` guard pin this cycle wrote (§4.2's M7, the check `network: the .dim class keeps its claim`), plus the ReDoS guard's **behavioural** eyJ check added in v0.4.28 (the structural eyJ pin it sits beside *replaced* an existing check, so it costs no census slot). An earlier draft of this row read "unchanged (no smoke pin was added)", which the two constants refute — the delta *is* the pin |
| `tests/docs_links.py` | pass — the preview is regenerated on the ship tree *before* this gate, since a stale one fails it by design |
| `tests/simulate_accumulation.py` | "All lifecycle properties hold" |
| `mypy --config-file mypy.ini` | success — 42 files |
| `tests/validate_manifests.py` | "manifests valid (consolidate-memory v0.4.27)" |
| mutation harnesses | the pass's own runs: **12 of 13** browser RED, 2/2 smoke RED (M12's GREEN is §4.3). The review round adds four more browser groups, re-run against the final selector list — PV-2 **1/1**, PV-2b **5/5**, D4 **2/2**, D3 **13 from a single mutation** (8 existence + 4 floor + 1 absence, counted on a non-fatal harness — the shipped one aborts on the first red; §4.6), and D3b **4/4** against `report_layout` after its first prediction was measured wrong (§4.6). That run's baseline was **1309 checks, 0 failed** — so the new selector list is clean everywhere the suite reaches before any mutation is planted. The re-audit round (§4.7) adds **M15–M21**, every one a revert of pre-fix code: **15 RED across the seven** as the round first measured them on a **1326**-check baseline, and **16** re-run in full on the suite as it then shipped (**1331**) — the extra red is M20's, whose target the code-review round rewrote, so the mutation was re-targeted and re-measured rather than carried (§4.8). Its **guard arm** is a separate kind of run — the defect is *introduced*, not restored — and runs on that same suite: **3 RED**, the three focus-indicator guards and nothing else, against a control placement of the same edit that reds **0** (§4.7). The code-review round adds **M22** — `countText()` reverted alone, the rest of the row untouched — for **1 RED**, the count-shape pin (§4.8). The fan-out triage round (§4.9) adds **M23** — `listText()` reverted alone, the join left unguarded — for **1 RED**, the array-of-objects pin, and **M24** — the fact focus key reverted to its pre-fix name-only form — for **1 RED**, the duplicate-key pin. Both mutations revert *the round's own two fixes*, and both were run before either fix was believed. |

**How the suite grew — three measured points**, each one that tree's own suite run against that
tree's own scripts, which is the procedure that produced the pre-pass figure rather than a delta
off it:

| Tree | Checks | Failed |
| --- | --- | --- |
| `df2c1c5^` (pre-pass) | **1213** | 0 |
| `df2c1c5` (the pass as committed) | **1264** | 0 |
| `d9ade6e` (the review round) | **1309** | 0 |
| `1864f68` (the re-audit round) | **1329** | 0 |
| `e15ac3e` (the code-review round) | **1331** | 0 |
| as it ships (the fan-out triage round) | **1334** | 0 |

The pass added **6 `check(` sites** (196 → 202) for **+51 runtime checks**; the review round added
**7 sites** (202 → 209) for **+45**. Runtime exceeds the site count in both cases because several
sites sit inside loops. The review round's +45 decomposes exactly over its named sites — measured by
diffing the two runs' check-name multisets, not derived:

| Site | Runtime |
| --- | --- |
| `report_layout(theme+' focused')` — a new *call* of an existing six-check helper, ×5 themes | **+30** |
| `focused_fit` — five focused passes and three fact-view widths, net of the three `contained()` calls it replaced | **+5** |
| the focused legend pin, ×5 themes | **+5** |
| five one-shot pins: the fleet legend, both trail labels, both focus-handoff checks | **+5** |

The re-audit round added **10 sites** (209 → 219) for **+20**, and the two counts differ because two
of the new sites loop. Its ten new `check(` sites carry **15** runtime checks — two fire once per
focus-exit control (×3 each: the handoff and the focus indicator beside it), one fires once per
paged-anchor fixture (×2, in the existing `large`/`uneven` loop), and the other seven fire once.
The five new fixtures add the remaining **5**: `fixture()` calls `ready()`, which owns its own
`render without errors` check, so a new fixture is +1 before any assertion is written. Sites are
counted as occurrences of `check(`; the 209 in the review round's row is that same method, which is
why it reconciles with this one and not with a `^\s*check(` count (195 at that tree).

The code-review round that closes the cycle added **1 site** (219 → 220) for **+2**: its new pin
fires once, and the fixture that pin needs is one more `fixture()` call, which brings its own
`render without errors` check with it.

An earlier draft of this section said the pass counted "1266, +53". Both figures were wrong; the
measured values are **1264** and **+51**. The pre-pass **1213** was then re-measured the same way
rather than carried forward, because a wrong number had been sitting directly beside it.

### 4.5 Archive embed budget — measured, not reasoned

The P4 pin asserts `len(_html_p4) < 320 * 1024` — **re-based from `300 * 1024` this round**, and the
re-basing is itself a measurement rather than a judgment call. The pin counts *characters* of the
rendered archive and includes the shell (the template and both JS bundles are inlined verbatim,
comments and all), so every character added to a shipped file spends this budget. Measured against
the same 120-cycle fixture:

| Tree | Characters | Headroom under the new bound |
| --- | --- | --- |
| `df2c1c5^` (pre-fix) | 285,411 | 42,269 |
| `df2c1c5` (the pass as committed) | 297,637 | 30,043 |
| review round | 300,408 | 27,272 |
| `1864f68` (the re-audit round) | **307,050** | 20,630 — but **150** under the bound then in force |
| `e15ac3e` (this round's corrections) | **308,659** | 19,021 |
| as it ships (the fan-out triage round, §4.9) | **309,802** | 17,878 |

**Why the bound moved.** Under `300 * 1024` the headroom at `1864f68` was **150 characters**: the
commits before this round had already spent the margin, and this round's corrections (**+1,609
characters** — **458** in the template, **1,151** in `dashboard.network.js`) put the archive at
308,659, **1,459 over**. An earlier draft of this sentence read +1,611 (460 + 1,151), and the two
extra characters are the point: those are the two files' **byte** deltas, and the template's added
comment carries one em dash — three bytes, one character — so its byte count leads its character
count by exactly the 2 that the draft's sum was too large by. The archive is the arbiter, and it
says 1,609: 307,050 → 308,659, which is 458 + 1,151 to the character, the way it has to be when
both files are inlined verbatim. So the paragraph below, which read **1,609** while the sentence
above it read **1,611**, was right and the new figure was wrong — the recurrence of the exact
class the review round had already caught once in this cycle's budget paragraph, a **byte** figure
standing where a **character** figure was claimed. Fixing the word did not fix the arithmetic
underneath it, which is why the archive itself is quoted here rather than a sum of file sizes. The alternative was to trim comments until it fit, and that was rejected on the
measurement, not on taste: the text in question corrects two claims review had just found false
(§4.6), and a bound that would be satisfied by deleting documentation is measuring the wrong
quantity. The pin's actual subject is an order of magnitude larger — admit the fixture's two junk
keys (`junk_never_read`, `registrar_working`) back into the whitelist and the same render is
**600,821** characters, so the trim is worth **292,162** of them. At 320 KiB the bound restores the
~19–21 KiB working margin 0.4.24 shipped with (21,789) and still sits 273,141 characters below a
junk-untrimmed render, which is the regression it exists to catch.

**Pre-fix to ship, the branch cost 23,248 characters — more than the 21,789 of headroom it started
with**, which is the whole reason the bound had to move. It splits the way the table does:
**12,226** for the pass proper (the `df2c1c5` row), **2,771** for the review round, **6,642** for
the re-audit round, and **1,609** for this round's corrections. (An earlier draft read "the pass
cost 14,685", borrowing the
table's word for the *commit* to name the whole effort — one word, two scopes, which is how the
number came to sit under the wrong label.) The review round's own share of 2,771
splits by file: **1,689** in the redraw's focus repair and the
comments around it (`dashboard.network.js`), **1,082** in the template — **770** for the R1 repair
and the comment corrections it forced, **297** for the R4 comment repair that replaced the
theme-dependence story with the measured one, and **15** for the wording fix that replaced a
cascade-order claim naming the wrong pair of rules. Each figure is the difference between two measured
trees, never a share of the total, and the R4 figure reconciles two independent measurements: +297
characters of comment, +297 characters of archive, because the fixture embeds the template verbatim.
The re-measurement above is what keeps this paragraph honest: the split of **2,771** is unchanged,
but the headline it was first written under (*"the whole review cost 14,997 — 68.8% of the previously
recorded headroom"*) measured the review round against a ship row that two later rounds then moved.
The pre-fix
figure reproduces the 21,789 recorded at v0.4.24 exactly, which is the corroboration that makes it
safe to carry: the two `df2c1c5` rows are re-derivable from blobs, the last two from the trees named
in them. All five numbers are re-derivable: the fixture is `smoke.py`'s P4 block, verbatim.

**A measurement hazard this table hides, because the numbers were taken on five different
trees.** `df2c1c5` carries the pass; the review round's repairs were authored in two places —
the JS in a pristine copy of that commit, the template in the working tree — so no single tree
held the whole delta while it was being developed. The review-round row is therefore measured on
an assembled tree (working-tree template + pristine JS), not on any tree that existed on disk
before it. Its size is not the sum of the other rows and should not be treated as one: it was
measured, and the sum only happens to agree because the fixture embeds both files verbatim.
The last two rows are not exposed to this: `1864f68` is a commit and the ship row is the live
worktree, not a composite of one file taken from each of two states.

**The same split is a gate hazard, and it was real:** through the whole review round the *assembled*
state — the review round's template fixes on top of the review round's JS fixes — had never been
run through any gate. Each half was gated on a tree that was not the artifact: the live suite (that
commit's own, **1264** checks) ran against live-template + pre-review JS, and the review suite ran
against pre-review template + review JS.

That second tree was recorded here as **1279** checks. It does not reproduce. Measured with the
final suite it reports **1309**, the same count as the assembled tree — the count turns out to be
template-independent: same suite file, different template digest, same 1309. The 30-check gap is
exactly what the theme-loop focused pass contributes, so 1279 was almost certainly taken before
that call was added: a stale figure standing as one half of a comparison that needs both halves
from one suite revision. It is the second number in this section to fail a re-measurement, which is
why the procedure here is *run the tree's own suite against the tree's own scripts* and never carry
a count forward from a neighbouring state.

The hazard itself survives the correction, and is sharper stated without the counting: **three
trees, all green, and none of them the artifact.** What decides is identity, not count — the ship
tree is the only one whose template digest is the live one *and* whose JS and suite digests are the
reviewed ones, and §4.4's final row is that tree.

### 4.6 The review round — two defects this spec's own text had already named

The pass went to adversarial review before release. One reviewer found real defects in code that
had passed every gate above. Both are worth recording in full, because in each case **the pass
supplied the premise of its own refutation** — the invariant was written down and then violated by
the same commit.

**D1 — the new back-control strands focus on `<body>`, which §3 forbids.** §3 states: *"Focus
survives the activation that caused the redraw, or lands on a real control — never stranded on
`<body>`."* The trail's back-control is a real control created by this pass, and it violated it.

The root cause is a misplacement, not a missing idea. The stranded-focus fallback from defect 3
existed and worked — for the **fact button** in `#net-detail`, whose element `inspect()`'s
`innerHTML` rewrite destroys. It was placed inside `focus()`, i.e. at an *activation site*, and
`focus()` is not on the back-control's path: the crumb's handler is `reset()` → `draw()` →
`crumbs.textContent=''`. Two activations with the identical shape (an activation whose own element
the redraw destroys), one covered, one not — the `weakest-enforcement-site-wins` shape, in code
written the same day. The repair is therefore **relocated to the redraw's tail** (§2.6), where the
destruction happens, and covers the fact button, the crumb, and any HTML control a later pass adds.
M-D1 restores the pre-fix shape (delete those two lines) and the new crumb check goes red.

`keepControl` — a parameter whose only job was to suppress the old fallback on the `<select>` path —
was deleted with the fallback. The select is never rebuilt by `draw()`, so focus never leaves it and
it never needed the exemption. It was a fossil of the fallback's placement, not of the contract.

**D2 — the summary check had a ceiling and no floor, and passed against its own defect.** The pin
read `summary_rows <= 4`. A `#net-detail` that renders *no* summary at all yields `0` rows, and
`0 <= 4` is true: the check was green against the very defect it was added to catch. It now reads
the bound off `#net`'s `data-kind` — **1..4 rows in a focused view, exactly 0 in the fleet** — which
is view-derived rather than label-derived, so no wording can move it. M-D2 (the `<dl>` is never
built) now goes red.

**A false universal, in the code and in the spec.** The fact-button comment read *"The one
activation with no successor"* — written before the crumb existed, and false the moment it did. The
spec's §2.2 asserted the crumb *"carries its own `tabindex` via `activate()`"*; `activate()` is
never called on it (it is a native `<button>` built by `button()`, focusable without a tabindex, and
Enter synthesises the same click — one handler, not two). The claim was never read off the code.
Both corrected in place. The pattern is `dropped-hedge-becomes-false-universal`: an accurate
statement about the *old* control was allowed to survive the addition of a second one.

#### Holes this round DID close, and the runs that prove it

Six pins were added after the round recorded these; a pin is claimed here only with the mutation
that turned it red.

| Pin | Mutation | Red |
| --- | --- | --- |
| the dot keys beside a fleet reading | `legendKeys.hidden=true` in every view | 1 |
| the dot keys dropped in a focused view | the `hidden` assignment deleted, so keys never hide | 5 (one per theme) |
| the trail reads its own kind | the writer's branch collapsed to `'Project'` | 2 |
| `focused_fit`'s existence clause | the summary's rows are never built | 8 |
| the summary's absence states | same mutation | 1 |
| `concise_network`'s D2 floor | same mutation | 4 |

The last three share one mutation, and that is the point: the pre-pass shape — a summary with no
rows — is reachable from a single edit, and three independent pins see it. **13 checks red in one
run at a measured 1309** — under a non-fatal copy of the harness; the shipped harness aborts on the
first of them, and the open holes below say what that costs and why it matters for any count
reported this way. The existence clause is therefore **red by reversion**, not by an
invented defect — the property the pin discipline requires, and the one the round could not
previously claim. (The mutation is `summary.forEach(...)` → `[].forEach(...)`, deliberately not
`if(summary.length){` → `if(false){`: the latter deletes the `<dl>` itself, and the suite's own
`concise_network` then throws on a zero-match locator at 78 checks, before either predicted group
runs. The mutation has to leave the subtree reachable and merely empty.)

**A vacuous pin, found by mutation and repaired.** The focused legend pin read the note's text and
the keys' count and hiddenness, but never that the legend itself was on screen. In a focused view
the keys are hidden *by design* (`legendKeys.hidden=state.kind!=='fleet'`), so every clause about them stays true
of a legend that is `display:none`: the pin could not tell "keys hidden, legend shown" from "legend
hidden". The repair adds `#net-legend` visibility as the pin's first clause.

Both directions are measured, and the isolating mutation had to be found before the second one meant
anything. Hiding the legend outright is caught at **check 14** by the *fleet* legend check — which
already carried a visibility clause on `.legend-keys`, because in the fleet view the keys are visible
and a clause about them covers the container too — and the shipped harness, aborting on the first
red, then never reaches the focused pass. The gap exists only in focused views, which is exactly
where no clause about a hidden element can reach it. Hiding the container only when
`state.kind!=='fleet'` — one added line at the site that already hides the keys — isolates it, and
there the repaired pin is the **first red**: 235 checks recorded, 1 red, and the red is the pin
itself, aborting the run at **check 235**. Vacuity demonstrated, repaired, and the repair shown to
catch the mutation the pin used to pass.

**The overflow half needed a different instrument, and the reason is in the template.**
`.network-surface` carries `overflow:hidden`, so a map surface that blows out is *clipped* rather
than scrolled: forcing `#net-detail{min-width:calc(100vw + 240px)}` leaves the element 1680px wide
while `.network-surface` reports `clientWidth` 1206 against `scrollWidth` 1706, and nothing reaches
`documentElement.scrollWidth`. Every check in the `contained()` family — the suite's whole
page-overflow idiom — stays green against it. What caught it was `report_layout`'s
surface-alignment clause, which compares element edges to the surface's padded box rather than to
page scroll, and it fired at all four widths (`net-detail` right edge 1823 against an expected 1297
at 1440). That clause now also runs in the focused pass, because it was blind in exactly the view
where the new surfaces render.

The text half of the same clause is immune to that clip by construction: it compares Range rects —
layout geometry — against the element's content box, so a clipped overflow is still measured.
*Which* selectors it walks was settled by measurement rather than by looking plausible.

**Three of the five obvious selectors were decoration, and came out.** A box only overflows if it
is constrained, and both a grid `auto` track and a flex item floor at min-content. Given a
600-character unbreakable token with the wrap rule removed, `.network-summary dt`, the trail and
`#net-legend-note` each *grew* to fit it — 129→3900, 109→3900, 554→3600 at 1440 — so text past
their own box is unreachable and a check on them could never fail. They were replaced by the
constrained containers that own them (`.network-summary`, `#net-controls`), whose boxes held at
1154 while the same token ran 2746–3046 past the right edge; a container's walk covers its
descendants' text, so the container carries the `dt`, the trail and the note. `.network-summary dd`
is kept on its own merit: its `minmax(0,1fr)` track has a 0 floor, which is precisely the
constraint the rule exists for. Every selector in the final list was confirmed to match a real
element in a live focused view at 1440/390/320.

#### Coverage holes this round still has NOT closed

Recorded rather than left implicit, because each is a place a future author could believe the suite
is watching and it is not:

- **The focused pass runs at 1440 only.** The `visual_hierarchy` / `controls_layout` /
  `report_layout` extension added by this pass iterates the theme loop but not the width loop, so
  the new surfaces are unmeasured at 390/768/320 *focused*. Relatedly, three of the four selectors
  the pass added to `visual_hierarchy`'s list match **0 elements** in the fleet, which is why the
  focused pass was needed and also why their fleet invocations assert nothing.
- **The crumb's hover and press feedback has no pin — and the obvious pin would not catch it.**
  **Corrected:** this bullet first read *"`.crumb-back` inherits **nothing**"*, and that was false.
  The pass added `#net-breadcrumbs button` to `controls_layout`'s hit-area group (the very kind of
  fixed selector list the bullet was invoking), and that group runs in the focused pass across all
  five themes — so the crumb's hit area **is** gated. What is ungated is the feedback the round
  actually found missing: `visual_hierarchy` reads **resting** computed styles, so a pin drawn from
  its list is green against a control with no `:hover` and no `:active` state — the defect that
  shipped. A pin that would catch it has to drive a real pointer and compare the hovered style. The
  record link `.network-record-link` is in the same position; it does inherit the generic
  `#network-blk button:hover`, because `#network-blk .inspector-choice` is `(1,1,0)` and loses to
  `(1,1,1)` — the specificity trap that made the crumb inert does not reach it.
- **CORRECTED — the `.crumb-back` absence is pinned; this entry claimed otherwise.**
  The check `the trail back-control returns to the fleet and leaves no trail behind`, added by this
  same round, asserts
  `#net-breadcrumbs button').count()==0` on the line immediately after the crumb click, and
  `button()` builds the crumb as `#net-breadcrumbs button.crumb-back` — so the fleet's crumb
  absence *is* gated, by the third clause of a check whose name speaks only of the trail. The
  entry read *"nothing asserts it is absent in the fleet view, only that the trail is empty
  there"* and was stale the moment it was written: the ledger was drafted against the suite as it
  stood before this round's own additions landed in it. The damaging direction is a future author
  who believes the ledger and *simplifies* that check to trail-emptiness alone, un-gating the property
  while all 1311 checks stay green. **The rule this earns: a coverage ledger written in the same
  change that closes the holes must be re-derived from the suite's final text, not from memory of
  what was still open when the drafting started.**
- **The `.dim` guard's own match set has two blind spots, and a false-positive mode.** Its regex
  catches `setAttribute('class','net-node dim')`, `classList.add("dim")` and
  `classList.add(String('dim'))`, but not a backtick literal, a concatenation (`'di'+'m'`), or a
  variable holding it. Latent only: both bundles use backticks exclusively inside `//` comment
  lines, so no composed form exists to evade it today. The other direction is that the same regex
  cannot tell code from **prose**: it matches any quoted run containing the bare word, so a comment
  reading *"the word 'dim' is reserved"* reddens a guard whose message claims a bundle named the
  class. Also latent — neither bundle quotes the word outside code — and recorded for the same
  reason as the blind spots: the pin's comment describes its match set, and a future author could
  read that description as exhaustive. The general shape is worth naming, because it recurs in
  both directions: **a gate proves only what its matcher can see** (`gate-coverage-is-its-match-set`),
  and a matcher loose enough to be robust is loose enough to be wrong.
- **No smoke pin names any new surface**, and the print check never runs with a focused view on
  screen.
- **The node focus key is uncovered** (§4.3, M12). **M1's coverage started at a single check**
  (§4.1) and stands at four after the re-audit round (§4.7, M15).
- **The anchor's presence is one-directional, and its residual is deliberate.** `rendered ⊆
  matching ⊆ selected` rules out marking a NON-member and says nothing about whether the anchor is
  on screen. The other direction is carried by the entry page and only there: a user who **pages
  away** from the anchor's page, or who **collapses the anchor's own domain**, hides it, and the
  anchor branch then matches nothing while the legend still reads *"The outlined node is the
  project you selected"*. That is a user-initiated hide with the same semantics fleet paging
  already has for the captured trigger, so it is a behaviour rather than a defect — but **no pin
  covers it**, and the two ways to reach it (a pager click, a domain collapse) are both one
  interaction away from the pinned path. Recorded because the entry-page pin makes the opposite
  claim look total.
- **The focus key falls back to position where the record supplies no identity.** `normalize()`
  keys nodes on the sid, but a capture with **no sids** and a capture with a **duplicated sid**
  both fall back to the positional index — the exact fragility the sid key was introduced to
  remove (§2.2). It is bounded rather than fixed: with no stable identity in the record there is
  nothing else to key on, and the duplicate case additionally keeps the two nodes distinct through
  that index. **Uncovered**: no fixture carries a sid-less capture or drives a repaint while
  focused on one of a duplicated pair's nodes, and a stale index surviving a cycle change would
  land focus on a different project. This is the node focus key's hole (§4.3, M12) seen from the
  other side.
  Both are correct changes the suite cannot currently distinguish from the defect they replaced.
- **The `#net-legend-note` clause is unguarded, and its failure mode is a crash rather than a red.**
  Both legend checks read `page.locator('#net-legend #net-legend-note').inner_text()` with no count
  guard (the fleet `the fleet legend shows its dot keys beside a fleet reading`, and the theme
  loop's `focused drops the fleet dot keys and keeps its own reading`, theme-prefixed at the call
  site) while the sibling `.legend-keys`
  clause is count-guarded at both — the same guard, one clause short. Measured: with the note absent
  `inner_text()` raises `TimeoutError`; with it duplicated it raises a strict-mode violation.
  Neither returns `False`, so
  neither reaches `check()`; the exception leaves it and kills the run, and every check already
  recorded still reads PASS in `browser-results.json`. The neighbouring comment's trap — "absence
  reads as hidden" — holds for boolean predicates such as `count()` and `is_hidden()` and does
  **not** hold for `inner_text()`, which is a different animal with a different failure mode. The
  same shape appears where `#net-detail .network-summary`'s text is assigned to `summary` two lines
  before the check that judges it, and where a `#net-detail [data-fact-id=…]` locator is clicked to
  mutate that summary without a prior count guard — an action on a locator that may match nothing.
- **The reversion-verifiability claim rests on a patched harness.** The D3 rows above came from a
  run whose `check()` had its `raise` replaced by `pass` (a mutation copy of the suite, not a repo
  file) — a legitimate
  way to see every red at once, and not what ships. Re-measured against the current ship suite, one
  mutation yields two different pictures: the **shipped** harness records **38** checks and stops,
  red on `group view keeps the selection summary to a handful of paired rows`, with `focused_fit`
  never firing; the **non-fatal** copy records all **1309** with **13** red, reproducing the recorded
  figure exactly. So the mutation *is* caught in the shipped gate — at check 38, by a neighbouring
  pin. What the shipped gate cannot show is the property the claim names, that `focused_fit`'s
  existence clauses are red by reversion. Any future table of reversion counts should name its
  harness: under the shipped one the count is always 1.
- **The legend is pinned in two of the four view kinds.** The only legend checks are the fleet
  `the fleet legend shows its dot keys beside a fleet reading` and the focused
  `focused drops the fleet dot keys and keeps its own reading` in the theme loop, which enters by
  clicking the fleet anchor and so lands on a **project** view. The legend renders in group and fact
  views too — `inspect()` sets the note's class and the keys' hiddenness unconditionally. The note's
  class is chosen by a nested ternary that begins `legendNote.className=state.kind==='group'` (one
  hit) and continues through the fleet and fallback arms on the same line; the keys are governed by
  `legendKeys.hidden=state.kind!=='fleet'` (one hit). Neither the keys nor the reading is pinned in
  either, so the `'group'` and `'fact'` arms can be mutated with nothing to catch it.
- **`focused_fit`'s existence half is DOM presence, not rendering.** The clause is
  `page.locator('#net-detail .network-summary > dt').count()>0`, which a `<dl>` carrying
  `display:none` or a zero height satisfies; the containment clause beside it then passes trivially,
  because a collapsed summary cannot overflow. The label claims more than the condition tests —
  `a-guards-label-is-not-its-predicate` in its pin form. The D3 mutation leaves the rows *absent*
  rather than *hidden*, so it does not expose this; a hidden-but-present mutation would.

Two properties of this list govern how it can be worked, so they are worth stating together:

- **A contrast or hit-area pin on a surface this pass CREATED cannot fail on pre-fix code** — the
  selector matches nothing there. Its mutation must *introduce* the defect (tint the crumb below
  AA, shrink the record link's box), not revert a change. `smoke.py`'s `.dim` guard is labelled on
  exactly this principle: it names its baseline, and the mutation that turns it red is the
  introduction of a dim-emitting site, which was run (M7).
- **…but the overflow hole could be made revert-verifiable for free, which is why it went first.**
  Pre-fix, a focused view rendered *no summary at all*, so an overflow pin that also asserts the
  summary is present (`dt` count > 0 before the containment check) is **red on pre-fix code** and
  green now — a revert-verifiable mutation rather than an invented defect. That is `focused_fit`
  as built, and the prediction held: D3 turned **8** of its existence clauses red, and took
  `concise_network`'s floor and the absence-semantics pin with them. The same reasoning put the
  trail's fact-view assertion second, for the same reason — pre-fix the trail was never written at
  all — and D4 confirms it. The general lesson, worth keeping: **prefer the pin whose reversion is
  the defect**, and design the assertion so it covers the reversion rather than only the failure
  mode you had in mind.

That list is the queue, not a wish list: it was measured clean where it says "unasserted" (no
overflow in 80 states, min contrast 7.19 over 40 readings against a 4.5 floor, hit areas ≥43.5 at
every width down to 320, long captured values held by `minmax(0,1fr)` + `overflow-wrap:anywhere`),
so these are gates to add, not defects to chase.

### 4.7 The re-audit round — the escape hatch measured, and one vacuous pin it exposed

The pass shipped a working exit from the graph and then had the *exit itself* re-audited. Seven
mutations, each the pre-fix form of one mechanism, run on a non-fatal copy of the harness so one
run exposes every red rather than the first. (An eighth run follows them: the guard arm, which
introduces a defect rather than restoring one, and therefore cannot sit in this table.) The round
first ran on a **1326**-check suite; the whole matrix was then **re-run against the shipped suite**
once the guard arm's three checks existed — first at **1329**, again at **1331** when the
code-review round landed, and a third time at **1334** after the fan-out triage round (§4.9).
Every count below reproduces on all three except M20's, for the reason the
row itself now carries: **a reversion is identified by the code it restores**, and the code-review
round rewrote the row M20 restores (§4.8).

| # | Mechanism restored to its pre-fix form | Checks RED |
| --- | --- | --- |
| M15 | the anchor marks the capture trigger in every view (`truthy(n.raw.trigger)`, no project arm) | **4** |
| M16 | the *fleet* anchor re-tests the trigger per node (`n===trigger` → `truthy(n.raw.trigger)` in that arm only) | **1** |
| M17 | the focus restore searches `svg.querySelectorAll('[data-key]')` — the pre-fix scope | **3** |
| M18 | `fieldText`/`listText` revert to the pre-fix pair | **2** |
| M19 | the `Shared facts` row reverts to two states **and** the explanation drops its `!unique` arm | **1** |
| M20 | the whole `Held by` row reverts to its pre-fix form — `drawn` counting `pf.holder_sids.length`, and the clause naming the map rather than the capture | **3** (2 as first run; re-targeted — §4.8) |
| M21 | a project view enters its anchor's domain on page 0 (the entry-page fix removed) | **2** |

**M15 more than doubles the coverage M1 was recorded as having.** §4.1's M1 row said its coverage
was "a single check, and that is the honest number", and it was — for the suite as it stood. The
re-audit's own pins now catch the same mutation: the paged-anchor pair reddens because its fixture
pages the anchor away, and the two-trigger pin because it is the one fixture where the two
predicates cannot coincide. **The lesson is about fixture shape, not pin count**: a pin can only
separate two predicates on a fixture where they disagree, and the pass's fixtures were built so
that they never did.

**A vacuous pin, found by mutation and repaired — the same failure §4.3 records, in a new place.**
The focus-repair block asserts three controls (the trail's back-control, the record link, and a
shared-fact button) each hand focus back to *themselves* after a redraw. It resized to a **fixed**
target width inside the loop. `resize()` waits for `#net`'s `data-viewport` to reach the new width,
so after the first iteration the width was already correct, the wait returned immediately, no
resize event fired, no redraw ran, and the control was never destroyed — leaving focus on it and
the assertion green **against the very defect it exists for**. Under M17, only the first of the
three went red. The repair alternates the target width, so every iteration forces a real redraw,
and M17 then reds all three. Nothing about the assertion was wrong; the *instrument* was inert,
which is the harder failure to see because the check's text stays true.

**Four of §4.7's thirteen assertions are GUARDs, and the source names each as one.** `a group list
the capture never recorded reads as not captured` cannot move under M18: pre-fix `listText()`
reported an absent list and a present non-array *identically*, so no revert separates them. What it
holds is the boundary the vocabulary rewrite could overshoot the other way — a rule rendering every
non-array as `None recorded` would call a field the capture never recorded a measured empty. It is
kept, and named, because a pin that cannot fail reads exactly like one that can (§4.3) and the next
author deserves to know which is which. The other three — the focus-indicator checks — are guards
for the same reason in a different place, and how they were verified is the next block.

**The guard arm: a mutation has to be planted where it wins.** A guard cannot be reddened by any
revert, so verifying one means *introducing* the defect instead. For the focus-indicator checks that
took two attempts, and the failed one is the finding:

| Placement of `outline:none` on the network button | Checks RED |
| --- | --- |
| a **new** `#network-blk button:focus-visible{outline:none}` planted beside the network's own focus rules | **0** |
| the same declaration appended **after** `#app button:focus-visible`, the rule that supplies the ring | **3** — exactly the three guards, nothing else |

Both rules are **(1,1,1)**, so source order decides — the anchor hover bump's tie-break, one
selector pair over (§5). Note too that the network has no scoped `button` focus rule to edit: its
`#network-blk [role="button"]:focus-visible` matches the SVG nodes, which carry the attribute, and
never a bare `<button>`, whose role is implicit. That absence *is* the mechanism — the ring has one
supplier, and it is app-wide. The first placement is not a gap in the guards; it is a mutation that
never became a defect, since the rule it planted already loses the cascade and its `outline:none`
is dead on arrival. It is recorded because *"the guards do not catch a suppressed outline"* was one
step away from being written about three checks that do.

**A mutation that looked right and proved nothing — and the reading it nearly produced.** The
fleet-arm reversion (M16) reddens exactly one check and leaves **both paged-anchor pins green**.
That was first read as a gap in those pins. It is not. The pre-fix anchor had **no project arm at
all**, so reverting only the fleet arm reverts half of a repair, and the pins that stayed green
were never asked the question. Restored whole as M15, the same predicate reddens four, those two
among them. The wrong reading is recorded because it was one step away: *"the paged-anchor pins do
not catch the anchor reversion"* would have been written about pins that catch it.

### 4.8 The code-review round — a count the record carries, reported as one it lacks

The last round before release turned on the selection summary itself. It found one defect and one
mis-worded clause in shipped behaviour, and — in the sentence that recorded the resulting budget
re-base — one recurrence of the byte-versus-character confusion the review round had already
caught once in this cycle (§4.5). None of the three was visible to any gate that was running, and
each is cheap to describe once measured.

**A present-but-not-a-count value is neither absent nor empty, and `countText()` said it was
absent.** The summary rows speak a two-shape vocabulary, stated at the head of the block that
carries it — `Not captured` for a field the capture never recorded, `None recorded` for a measured
empty, and, for anything else, the value rendered **as itself** (the block opening
`function fieldText(v){`, whose own `return typeof v==='object'?JSON.stringify(v):String(v);` is
that rule in code). A value that is *present but not a count* is the third case, and `countText()`
short-circuited it into `Not captured`: `count(v)===null` returned the absence string, so a
persisted `members_n` of `"2"` drew an absence claim about data the record plainly carries. This is
reachable, not theoretical: `validate_cycle_record` warns on a wrong-typed key at runtime and
**never blocks**, so such a record renders — the warning is not a gate. The repair reads the parse
once and branches on it, as this one line (verbatim, from the shipped bundle):

```js
function countText(v){if(v===undefined||v===null)return 'Not captured';var n=count(v);return n===null?fieldText(v):(n===0?'None recorded':String(n));}
```

which restores a second property on the way past: the zero test now reads the **parsed** number, so
`"0"` is `None recorded` rather than a bare zero on screen — the "no zero ever renders" rule holds
by construction instead of by the luck that no string-shaped zero had been tried.

**The `Held by` row named a measurement it does not make.** Its clause read *"shown on the map"*,
and the number beside it is the **selection**: `selectedNodes()` is what the capture *resolved*
(non-duplicate sids resolving to exactly one captured node), while the map draws one page per
expanded domain and nothing for a collapsed one. The rendered count is strictly smaller than the
selection in both of those reachable states, so the words claimed a comparison the value never
performs. It now says **"captured"**, which is what it counts. This is the same defect the round's
own pin had, one level up: the check could see the resolved-versus-listed difference (3 → 1) and
could never have seen a resolved-versus-rendered one, so the **words** were the thing that had to
give.

**Both are pinned by reversion, and the two mutations divide the work.** Reverting `countText()`
alone (**M22**) reds exactly **1** check — the count-shape pin — with the rest of the row
untouched, which is what proves that pin is sensitive to `countText`'s own predicate and not to the
row's shape. Reverting the whole row (**M20**, re-targeted) reds **3**: the count-shape pin plus
the two that hold the label and the resolved-versus-listed count. So M20's coverage contains M22's,
and M22 is kept because it *isolates* it — the count it produces answers a question M20 cannot ask,
which is *which* check holds this behaviour. Both were measured on the **1331**-check suite this
round shipped, in the same run as the rest of the matrix, whose closing line asserts that both
mutated sources were restored byte-identical.

**The budget sentence repeated the error it was recording.** §4.5's re-base paragraph first read
"+1,611 — 460 in the template, 1,151 in `dashboard.network.js`", which is the sum of the two files'
**byte** deltas presented as the archive's growth. The archive grew by **1,609 characters**. The
template's added comment carries one em dash — three bytes, one character — so its byte count leads
its character count by exactly the 2 the sum was too large by. Re-measuring both endpoints
(307,050 → 308,659) against the per-file **character** deltas (458 + 1,151) settles it to the
character, and that agreement is the property that makes the number re-derivable rather than
remembered: both files are inlined verbatim, so the parts must sum to the whole. The review round
had already caught this exact confusion once in this cycle's budget text — the word was fixed, the
arithmetic under it was not, which is the whole lesson.

**Out of scope here, recorded where it lives.** The same round found that the preview generator's
splice was bounded by emission order rather than by a rule, and that the docs gate's companion
check on it could not fail in any run; both are the CHANGELOG entry's, since neither touches a
shipped file.

### 4.9 The fan-out triage round — two more of the same shape, and a stale verdict is not a finding

A parallel review fan-out audited the shipped tree. Its verdicts arrive **against the revision
each was measured on**, and most of them were measured on `1864f68` — the tree *before* §4.8's
fixes — so the first work of this round was triage, not repair. Seven verdicts were refuted by the
tree they were aimed at, and each refutation is one measurement, not an argument:

- **`countText()`'s third shape** (§4.8's fix) and **the `Held by` clause** (§4.8's fix) were
  reported live; both quoted the *pre-fix* source (`return v===0?'None recorded'`, the literal
  `'shown on the map'`), which no longer exists. At HEAD the string survives only inside the two
  comments that explain why it was wrong.
- **The preview splice** (§4.8's CHANGELOG item) was reported as an open defect with its
  `tests/docs_links.py` check quoted; that check was deleted in the same commit.
- **The legend's 7px gap** was reported as introduced and unpinned. `df2c1c5` did introduce it —
  and `e15ac3e` had already repaired it with `.legend .legend-keys{gap:10px 20px}`, whose own
  comment names the descendant match the finding describes.
- **A fixture comment citing `template :918`** was reported stale; the comment no longer contains
  that citation, or any other.
- **Two spec `file:line` citations** were reported drifted. The spec now contains **zero**
  citations of that form — counted, `[a-zA-Z_0-9]+\.(js|py|html|md|json):[0-9]` → 0 hits — so the
  §4.8 repair had already re-anchored them.

**The two that survived are one defect shape, twice**: a value or a key that is *not the shape the
code assumes*, rendered or resolved as though it were. That is §4.8's `countText` defect, and the
round that fixed it fixed one instance of a class.

- **`listText()` joined a list of objects.** `join(', ')` stringifies each element, so an
  array-of-objects group list rendered `'[object Object], [object Object]'` — the exact output the
  rule 8 lines above it forbids in words, and the exact output the pin beside it was **named** for
  while testing a shape that cannot produce it. The guard belongs on the join, not on the
  stringify: a non-empty array never reaches `fieldText()` at all.
- **The fact focus key fell back to a name, which is not unique.** `data-key` was
  `'fact:'+(fact_id||name)`, and the same expression computes `duplicate` to decide whether the
  *label* needs a domain prefix — the code admitting names repeat while the key assumed they do
  not. The redraw's restore takes the **first** match, so two same-named facts meant the next Enter
  opened the other one. The key now disambiguates exactly where the label does — identity, then
  index — which is the shape `normalize()` already uses for node keys.

Both are reachable only through the name fallback (a foreign or hand-edited record: the shipped
producer always writes `fact_id`), which is the same reachability argument §4.8 used for the
count-shape fix, and neither is a shipped-producer defect.

| Mutation | Reverts | RED |
| --- | --- | --- |
| **M23** | `listText()` to its pre-fix join, the rest of the row untouched | **1** |
| **M24** | the fact focus key to its pre-fix name-only form | **1** |

Each reddens **exactly one** check and is the first failure in its run, so each isolates the
behaviour it names rather than corroborating it. Both were run **before the fix was believed**, and
the second is the reason this round has a pin where §4.8's budget item did not: reverting the key
fix with the pin absent left all **1332** checks green — a fix nothing holds is not a fix, it is a
claim. `M24`'s pin is built by seeding two entries from one real holder of the clicked node and
then changing exactly the two fields under test (same `name`, no `fact_id`).

**The check count moved 1331 → 1334, and the third is not a check anyone wrote.** Two come from
the two pins; the third is `render without errors: focus-duplicate-keys.html#sel=0`, because a new
`fixture()` call writes a new preview into the output directory and the suite renders every fixture
it finds there. Recorded because the arithmetic is otherwise +2 and the suite says +3 — and a count
that no longer matches its tree is a defect, not a rounding.

**The archive grew 1,143 characters, measured at both endpoints** — 308,659 → 309,802, re-derived
the way §4.5's own lesson insists rather than reasoned from the diff. Nearly all of it is the two
fixes' comments. Against the 320 KiB bound that leaves **17,878** characters, so the round spends
about a sixteenth of the headroom §4.5's re-base restored.

## 5. Deliberately not fixed (found by measurement, recorded rather than silently changed)

- **`.node-name` / `.node-meta` are emitted by nothing.** The live classes are `project-label`
  (`--ink`) and `project-meta`, whose fill resolves to `--ink2` — **not** `--faint`. The `.dim`
  contrast analysis, `deep-field-theme.spec.md`, and two CHANGELOG entries all name the dead
  pair. The template comment now carries a `⚠ RE-DERIVE BEFORE REVIVING` note; only the split's
  *direction* survives its own derivation, since every magnitude was counted against a text child
  that never renders.
- **Every unscoped `.net-node rect` rule this measurement reached is dead code — including the
  three this pass added.** The mechanism is about *competing declarations of one property*, not
  about elements: `#network-blk`-prefixed rules beat non-prefixed base rules on the ID in every
  theme, so wherever both families declare the same property the prefixed one wins, and the
  scoping half of this pass's cascade fix is delivered entirely by the prefixed family. Measured
  by reverting the unscoped family to its pre-pass form: **0 of 45 state cells change** (9 states
  × 5 themes). This was already recorded for the node *fill* declarations; the new fact is that
  the three declarations this pass wrote into that family — the `:not([data-current="true"])`
  guards on the hover cue, their `stroke-width` split, and `.net-node.selected:hover` — are inert
  for the same reason. They read as live to the next editor and are not.
  **The boundary matters, and an earlier draft of this bullet omitted it.** The 45 cells are built
  from fill, stroke and width — exactly the properties the three declarations compete on — so the
  measurement cannot reach a declaration with *no* prefixed competitor, and one exists:
  `.net-node rect,.net-node text{transition:opacity .18s ease}` declares `transition`, which no
  `#network-blk` rule re-declares, so it is outranked by nothing and its computed value is live in
  every theme. It is inert only in the weaker sense that nothing animates: the only rule that
  changes a node's opacity is `#network-blk .net-node.dim rect`, and nothing applies `.dim` (§5;
  the same unreachability the theme spec's contrast analysis rests on). Stated as a universal, the
  bullet licensed deleting a live declaration — which is the one edit a "this family is dead"
  paragraph invites.
- **The anchor is marked by stroke only, and the widths matter.** No fill distinction survives in
  any theme. The anchor rests at **1.8px** `--data`; an ordinary node rests at **1.1px**
  `--rule2`; **2.6px** is the hover/focus width *every* node takes — measured across
  default/nocturne/light. An earlier draft of this section and of the CHANGELOG gave 2.6px as the
  anchor's *resting* width: the number was read off the hover state. Judged legible on the rest
  widths — a brighter stroke, 0.7px thicker, plus three redundant textual cues. The hover bump
  survives only because the two same-specificity rules that decide it sit in the right source
  order (the template comment now says so). **CORRECTED: this read *"no gate here would catch a
  reorder, which is why the order is documented rather than left to look accidental."* A gate does
  catch it** — the theme-loop check `focused keeps the anchor mark under the pointer while still
  answering it` reads the anchor rect's `stroke-width` at rest and under
  the pointer in every theme and asserts they differ. Mutation-verified rather than argued: moving
  the `stroke-width:2.6` hover rule ahead of the anchor's `stroke-width:1.8` rest rule (**both
  (1,2,1)**; nothing else changed) reddens exactly that check on the first theme with
  `rest={'w':'1.8px'} hovered={'w':'1.8px'}`, against a green run's `1.8px → 2.6px` on all five.
  The other half of the same reading — `mark`, the fill+stroke pair — is equal on both sides of
  the mutation, which is why the check is two-sided: the order-independent half cannot carry the
  order-dependent one. The false claim was worse than a gap: it told the next editor the order was
  unprotected and must be preserved by comment alone, and a reviewer checking it would find the
  comment wrong about its own gate. Re-tinting a shipped surface would need its own contrast gates.
- **The network's HTML controls get their focus ring from an app-wide rule, not from the
  `#network-blk`-scoped ones.** Measured while mutation-verifying §4.7's focus-indicator guards: a
  `document.styleSheets` walk over the focused record link lists three matching rules, and the ring
  comes from `#app button:focus-visible` — the template's focus group — at the same **(1,1,1)** as
  `#network-blk button:focus-visible`, decided by **source order**. The scoped rule's
  `outline:none` is what makes it read as the authority; it loses. This is the hover bump's own
  tie-break one selector pair over, and it has the same practical edge: whoever mutation-tests that
  ring must plant the defect *after* the winning rule, or it never takes effect. The scoped rule is
  not dead in the way §5's unscoped `.net-node rect` family is — it is outranked by exactly one
  later rule that can be moved.
- **The record link lands coarsely.** `#record-json` is one `<pre>` holding the whole record, so
  the landing is top-of-blob, not the node's entry. Narrowing via a `Range` is deferred: it means
  re-serialising with matching indentation or string-searching `"sid": "…"`, and the pin
  discipline demands a deterministic assertion.
- **Two live regions over rewritten content — minimum taken, restructure deferred.** `#net-detail`
  is `role="status" aria-live="polite"` and the inner `.network-explanation` was a second one, so
  every draw announced itself twice — including pager clicks that changed nothing. The inner
  `aria-live` is **dropped** (shipped); the outer `role="status"` is retained. A full restructure
  — a live region wrapped around the selection name only — is deferred: it is a DOM change with
  layout consequences across 5 themes × 4 widths that no gate here can assert. Measured churn, for
  whoever takes it: ten viewport resizes at 20ms emit **81 mutation records** and **nine** full
  `#net-detail` child replacements; five keystrokes in the search box emit five more. This pass
  made each announcement **68% longer** (300 chars in the project view, from 179) and added a
  sixth button to the live region.
- **`el('net').hidden = …` never hides anything.** `SVGSVGElement` has no `hidden` IDL property, so
  the assignment creates an own data property and `display` stays `block`; only `#net-scroll`, a
  `<div>`, actually hides the map (`[hidden]{display:none!important}` does apply to SVG once the
  *attribute* exists, so `setAttribute` would work). Harmless today — the absent-network render
  hides via `#net-scroll` and the orphan SVG measures 0×0 — but it is dead code that reads as
  live, and it is the kind of line a future editor trusts.
- **`organization-key` is assigned with no rule behind it.** The fleet branch sets it;
  `permissions-key` and `holdings-key` each have a template rule, `organization-key` has zero
  occurrences in the template. Vocabulary that outlived its rule; no user-visible effect. Left
  alone rather than deleted, because deciding which of the three is the survivor is a naming
  question, not a bug fix.
- **A printed focused view keeps the record link and loses the trail.** `#net-breadcrumbs` lives
  inside `.map-controls`, which print CSS hides (`display:none!important`), while the summary and
  the record link are not hidden — so the printed page shows a button that reads as actionable and
  no way back. Measured at 390px in all five themes. No gate runs print with a focused view on
  screen. Cosmetic, but it is the only place the pass's new surfaces disagree about whether they
  are on paper.
- **A cross-cycle repaint still loses focus to `<body>`.** The archive's per-dream repaint
  re-renders the section from the template side, before `draw()` runs, so `hadFocus` is already
  false by the time the new repair could fire — the fix cannot reach that path, and the stable
  `data-key` cannot either (nothing survives to be matched). Pre-existing and template-side; the
  repair added here narrows the class without closing it.
- **Four low-severity naming gaps, recorded not fixed.** The anchor is not determinable from its
  accessible name; `#net-controls`'s `aria-label` omits the search box it contains; the legend's
  interpretation line is not announced on a view change (only `#net-detail` is live); and the
  empty-capture `#net-note` renders bare `0`s where the summary never does. Each is one string or
  one attribute; none is worth a DOM change before the next time these surfaces are opened.

## 6. Ship shape

A **patch** (`0.4.26 → 0.4.27`): a fix to a shipped artifact surface, backward-compatible, no
schema or CLI change. Per the release-coherence rule it ships immediately rather than batched.
Feature branch + PR; the maintainer reserves the merge.
