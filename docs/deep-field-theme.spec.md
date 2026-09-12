# Deep Field — design-of-record

**Status: implemented.** Target release: **v0.4.24 (patch)** — a new default colour theme
for the HTML archive, the visual system behind the README art, and the maintainer capture
path that keeps that art honest.

## §1 What was wrong

The summary screen was a competent admin panel: every element on one near-black canvas,
no elevation, no texture, no motion, and a KPI row floating on the void without a card
treatment. The product calls itself a memory *observatory*; the screen did not.

Two constraints shaped the fix, and both were discovered by reading the suite rather than
the stylesheet:

- **The dashboard is a 19-token design system.** Every colour resolves through `var(--paper)`,
  `var(--data)`, `var(--accent)`, … declared once per theme
  (`dashboard.template.html:11-46`). A re-palette is ~16 lines, not a rewrite.
- **Colour is gated twice, independently.** `tests/smoke.py:2102-2116` (RC-90) walks every
  palette-shaped block and requires 9 foregrounds × 3 surfaces ≥ 4.5:1.
  `tests/dashboard_browser.py:132-148` (`visual_hierarchy`) composites each element against
  its *real* background chain in a live browser — including the node plate
  (`#network-blk .net-node rect{fill:var(--card)}`), so `--card` is load-bearing for both.

## §2 The palette

Deep Field is the bare `:root` block — which is what makes it the default *and* keeps
`System` coherent (an OS-dark preference matches no `[data-theme]` block and falls through
to bare `:root`; System-dark therefore means Deep Field, not a missing palette).

```
color-scheme:dark
--paper:#04070e  --paper2:#080e18  --card:#0f1c2e  --rule:#1f3046  --rule2:#2c4059
--ink:#e9f1f8    --ink2:#b9c9da    --faint:#8296ad   --ghost:#7b90a6
--accent:#a999f5 --data:#63d3e8    --ok:#7fd8b8      --warn:#f0bd6a  --crit:#f58f7a
--glow:#0d1a33
--tint-ok:rgba(99,211,232,.08)      --tint-crit:rgba(245,143,122,.10)
--tint-accent:rgba(169,153,245,.09) --tint-warn:rgba(240,189,106,.10)
```

**Measured, both gates, all six palette-shaped blocks.** RC-90's worst pair per block
(recomputed over the shipped template):

| block | worst pair | fails |
| :--- | :--- | ---: |
| bare `:root` (Deep Field) | 5.21 (`ghost` on `card`) | 0 |
| `nocturne` | 6.40 (`ghost` on `card`) | 0 |
| `original` | 4.57 (`ghost` on `paper2`) | 0 |
| `light` | 4.75 (`ghost` on `paper2`) | 0 |
| `auto` (light) | 4.75 (`ghost` on `paper2`) | 0 |
| `@media print` | 5.32 (`ghost` on `paper2`) | 0 |

Deep Field becomes the *tightest* dark theme at 5.21 — above the shipped Original's 4.57,
so it raises the floor rather than lowering it. The regex finds 6 blocks against a `>= 5`
requirement, and every one carries all 12 colour keys plus the four `--tint-*` as `rgba(`.

Three values were chosen against measurements rather than taste:

- `--card:#0f1c2e` — surface-tier separation **1.18** against `--paper`. The first draft
  (`#0c1522`) measured 1.10, i.e. *flatter* than Nocturne's 1.14.
- `--rule:#1f3046` — hairline contrast 1.51 against `--paper`: visible without shouting.
- `--paper:#04070e` — near-black but not pure black, avoiding OLED smear on scroll.

### The semantic triple under dichromacy

`docs/nocturne-design.md` promises *"colour never carries a verdict alone."* That promise
is kept by the status **labels** (`Needs attention`, `Recorded clear`, `Partially captured`,
`Not captured`) shipped beside every colour-coded disclosure — not by colour separation.
The colour channel was measured anyway, with a Viénot-1999 dichromat simulation plus
CIEDE2000 (minimum pairwise ΔE00 within `ok`/`warn`/`crit`):

| vision | Nocturne (pre-0.4.24) | Deep Field |
| :--- | ---: | ---: |
| normal | 27.5 | 24.8 |
| deuteranopia | 2.9 | 6.0 |
| protanopia | 5.5 | 7.3 |

The simulation self-tests before reporting: the red/green pair collapses from ΔE00 86.6 to
10.2 under both simulated dichromacies, greys survive the projection unchanged, and the
LMS matrices round-trip to identity within 2e-5. Absolute values depend on the sim's
constants; the **direction of the comparison** is the result that drove the design.

**Known limit, stated plainly:** neither theme separates the triple well by colour alone
under red-green dichromacy, and Deep Field should not be described as *accessible* on the
strength of these numbers — it is measurably *better* than what it replaces, and the
enforced contract remains the text label. Any future palette work should treat raising
deuteranopic ΔE00 above ~15 as the open target; it was not reached here, and reaching it
means re-picking `ok`/`crit` hues away from their conventional green/red anchors.

## §3 Theme plumbing (three touch points)

1. **Pre-paint whitelist** (`dashboard.template.html:664-668`). Adds `deepfield` and
   `nocturne`. A saved `cm-theme="dark"` — the pre-0.4.24 default's storage value — is
   deliberately **absent** from the whitelist and is normalized to `deepfield` inside
   `apply()`: stamping `data-theme="dark"` would set an attribute no block matches, and the
   pre-paint script would then paint the legacy palette for one frame.
2. **Toggle cycle** (`dashboard.template.html:1396-1406`).
   `["deepfield","nocturne","original","light","auto"]` with icons
   `◉ ● ◒ ○ ◐`. Original's cycle neighbour is still Light, so the existing
   `'◒ Original'` / `'Switch to Light'` assertions hold unchanged.
3. **Print block** — **not edited**. Specificity already resolves it: `:root[data-theme]`
   is (0,2,0) and appears *later* in source than `:root[data-theme="nocturne"]`, so print
   wins the tie; bare `:root` (0,1,0) loses to the print rule's second selector at (0,2,0).
   Verified by rendering a print emulation in every theme, not by reasoning alone.

## §4 Atmosphere, and the structural rule that constrains it

`dashboard.network.js:158-159` measures `svg.getBBox()` and shrinks `#net`'s viewBox to the
drawn content plus a 24px margin; `tests/dashboard_browser.py:152` asserts that leftover gap
is 15–40px. `getBBox()` **includes descendants and their transforms.**

So the chapter carries two structural rules, written into the stylesheet rather than left
to memory:

- **Nothing is ever added inside `<svg id="net">`, and no SVG child is ever transformed.**
  A backdrop `<rect>` spanning the canvas forces the gap to 0 — a hard failure that would
  also permanently disable the shrink. Atmosphere therefore lives on HTML wrappers
  (`body::before`, `.network-surface`), and SVG children are only ever *faded*, never moved.
- **The star field must be its own rule.** `smoke.py:4315-4318` pins
  `background-image:radial-gradient(…var(--glow)…)` immediately followed by
  `background-repeat`, so the masthead gradient cannot be edited in place.

### A stylesheet hazard worth recording

Smoke discovers palettes with `:root[^{}]*\{([^{}]+)\}` — **any** `:root`-prefixed selector
with a declaration block is parsed as a theme, and the regex runs from the token to the next
brace. Two consequences, both now respected in source:

- Every `:root`-prefixed rule must carry all 12 colour keys and the four `--tint-*` values,
  or RC-90 treats it as a malformed palette. This is why the star-field's light-theme
  override is written `html[data-theme="light"] body::before`, not `:root[data-theme=…]`.
- **`:root` must never appear inside a CSS comment in this stylesheet** — the regex would
  latch onto the following rule and register a phantom, key-less palette. Hence the
  circumlocutions ("the root pseudo-class") throughout the chapter.

## §5 Motion

All of it lives inside `@media(prefers-reduced-motion:no-preference)`
(`dashboard.template.html:635-660`): a staggered `rise` on chrome → headline → measures →
sections, `node-in` fades for the constellation, and a `branch-draw` dash-on for topology
branches.

Two fill modes, chosen per effect, and the reason matters:

- **`backwards`** holds the start state through the stagger delay and then releases to the
  element's *natural* CSS state. Nothing is left hidden, so no reduced-motion reset is
  needed.
- **`forwards`** (the branches) is required because the un-animated state of a dashed path
  is `stroke-dashoffset == full length`, i.e. invisible; releasing would erase the branch
  the instant it finished drawing.

The trap this avoids: a `forwards` animation normally needs an explicit reset in the reduce
block (that is why `.draw{stroke-dashoffset:0}` exists at `dashboard.template.html:211`).
Because the branch rule keeps *both* its `stroke-dasharray` and its `animation` inside the
no-preference block, the declarations themselves are scoped out under reduce — the element
renders as an ordinary solid path and no reset is required. Verified by measurement, not by
reading: under `no-preference` the branch computes `{dasharray: '126px', dashoffset: '0px'}`;
under `reduce`, `{dasharray: 'none', dashoffset: '0px'}`.

Note the suite cannot see this class of defect — `getBBox()` ignores `stroke-dashoffset`, so
a hidden stroke is geometrically identical to a drawn one.

### The header chart is frozen in geometry, not in colour

`tests/dashboard_browser.py:620-627` pins `#traj`'s `inner_html()` byte-for-byte, but the
frozen fixture (`tests/fixtures/dashboard-header-geometry.json`) contains **zero hex** — only
class names and `fill="var(--data)"`. Those classes are variable-styled, so the chart
re-themes while its geometry stays untouchable. Frozen set: the `d` attributes,
`stroke-width`, the `--len` values, and `.draw` placement.

## §6 The `.dim` rule — corrected, and honestly latent

`.net-node.dim` is **never applied**: the string appears in neither JS bundle, and the one
path that applies `.selected` (the group view) marks *every* node it renders, so no candidate
for the rule exists. It is kept correct rather than deleted in case a selection affordance
revives it.

The first correction was wrong, and the reason is a genuine CSS trap. Opacity on a **group**
renders the subtree offscreen and fades the result, so `.82` on a label inside a `.5` group
is an effective `.41` — the obvious "recede the plate, keep the label" implementation makes
the label dimmer than the rule it replaced. Measured worst-theme label contrast
(`--ink`/`--ink2` over its own plate over `--paper`, all four shipped palettes — `auto` is
Light byte-for-byte, verified token by token, so it is not a fifth; `@media print` is the
only other surface and differs from Light on five tokens. Undimmed baseline 7.63):

| rule | worst |
| :--- | ---: |
| `.net-node.dim{opacity:.26}` (pre-0.4.24) | 1.55 |
| `.net-node.dim{opacity:.5}` + `text{opacity:.82}` | 2.06 |
| `.net-node.dim rect{opacity:.5}` + `text{opacity:.82}` | **5.04** |

Only splitting onto the two elements clears 4.5. The value shipped is the split.

## §7 Reproducing the README art

Nothing in the repository generated `docs/assets/*`: the PNGs and `nocturne-network.svg`
were one-off exports, so any theme change meant hand-cropping. `tests/dashboard_browser.py
--capture` now re-exports all five from a live render.

- **It writes only into `--out`**, never into `docs/assets/`. A mode that wrote straight
  into the tree would make the CI browser job rewrite tracked files; promotion is a
  deliberate second step.
- **It captures in the default theme**, which is the whole of the re-palette.
- **It runs with `reduced_motion='reduce'`** — the reveal animations are scoped to
  no-preference, so this samples every element at its natural state instead of wherever
  the stagger happened to be. (The first attempt baked `opacity:0` onto rank labels.)
- **The SVG export is serialized, not screenshotted.** `outerHTML` omits `xmlns`, and a file
  opened directly parses as XML in no namespace — it renders as nothing (`natural: [0, 0]`).
  So the export gains `xmlns` plus `width`/`height` from the viewBox, walks ancestors for the
  first opaque background (the node surface is transparent; its colour lives on an ancestor,
  and the file is *linked* from the README rather than embedded, so it would otherwise sit on
  the viewer's white page as light-on-white), and converts computed `rgb()` to hex for
  readability. No palette mapping table is needed, because capturing in Deep Field already
  yields the right numbers.
- **The export is palette-baked, and that is correct here.** Nine distinct hexes in 66 places
  (`grep -o '#[0-9a-f]\{6\}' | sort -u | wc -l`). It cannot be otherwise: the file is loaded as
  an `<img>`, a document with no stylesheet context, so a `var(--data)` in it would resolve
  against nothing. Baking is safe *because the file is generated* — re-paletting is a
  re-export, not a hand-edit across 66 literals. Do not "fix" this by hand-writing variables
  into the export; that would break the render and reintroduce the hand-maintained drift the
  capture mode exists to end.

`docs/assets/original-dashboard.png` had zero references and was deleted.

## §8 Budget

`smoke.py:11632-11633` bounds the rendered archive at `300 * 1024`; `render_html.py` inlines the
template **plus both JS bundles**. The bounded quantity is `len(_html_p4)` — a CHARACTER count, not a
byte size, and the shell is dense with multi-byte glyphs, so the two are not interchangeable. Read
the bound as 307,200 units, never as a file size. Measured with smoke's own 120-cycle / 20-sidecar
fixture:

| | rendered archive (characters) | headroom |
| :--- | ---: | ---: |
| pre-0.4.24 | 276,454 | 30,746 = 30.0 KiB |
| 0.4.24 | 285,084 | **22,116 = 21.6 KiB** |

The Deep Field chapter costs **8,630 characters** of shell, which is the whole of the delta. 21.6 KiB
is comfortable but no longer generous — **a future theme chapter should budget against this
number**, and the bound is a smoke check, not a guideline.

## §9 What deliberately did not change

Frozen identifiers and contracts, none of them touched: `NocturneNetwork` / `NocturneSections`
(`smoke.py:13146`), `#traj`'s inner HTML, every `#net` routing class and its orthogonal
`M…H…V…` geometry, the 12-per-page paging, the `_EMBED_KEYS` read-whitelist (no new
`CUR.<key>` read was added), the cycle-record schema and its `TypedDict`s, and the Original
palette (`smoke.py:2117-2125` byte-pins it).

## §10 Verification

```bash
python3 tests/smoke.py                                    # 1762 checks, RC-90 + the size bound
python3 tests/dashboard_browser.py --out /tmp/cm-browser  # 5 themes × 4 widths + the second gate
python3 tests/docs_links.py                               # the gate this arc added
python3 tests/validate_manifests.py
mypy --config-file mypy.ini
python3 tests/simulate_accumulation.py
```

Manual, in the rendered output — the part assertions cannot cover: all five themes at
320 / 390 / 1440px plus print preview; the README SVGs opened as *images*, never read as
source; and the network with the group view selected.
