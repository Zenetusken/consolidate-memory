# Render/declaration parity — design-of-record

**Status: revision 4 — adversarial review complete; every blocker resolved and every number re-derived.**
Target release: **v0.4.34 (patch)** — five repairs across the ASCII renderer, the **producer**, the schema
declarations, and the pin that guards them. No cycle-record schema change an existing install can observe
as incompatible: both E4 edits move a key *into* the contract that the producer already emits, and both E1
producer edits are **additive** (`mirror_share`, `audit.window`), so every archived record still renders.

This is the **second of the two cycles** staged out of `OPEN 4b`. Cycle D shipped as v0.4.33 and closed
the *presence* half — a seeded duty left unfilled now fails the terminal persist gate. Cycle D **recorded**
the defects below and deliberately did not fix them; this document is their fix. The split is not
arbitrary: Cycle D's clauses fire on a record's *values*, while every defect here is a surface
**re-deriving meaning from a label instead of from the data that produced it**, and the label is the only
thing anyone checks.

**Revision 4 changes the cycle's shape, and that is the honest headline.** The cycle was staged as five
renderer/declaration-local repairs. Adversarial review found that **two of the five reach the producer**
(E1 gains a persisted `mirror_share`; E4(B) becomes "the producer emits `audit.window`" rather than "the
declaration drops it"), and that **E5 is not a drift repair at all** — its predicted drifts do not exist.
§3.6 records that this document's own census committed the defect it exists to describe.

## 1. The defect

Five sites, one shape. Each was reproduced by driving the real renderer on revision `1d97f54`, not read
off the source; §3 carries the method and the numbers.

### 1.1 E1 — the remediation note is a 3-way lookup over a 4-dimensional outcome

`render_dashboard.py` derives the over-budget remediation note from `(lever, acted)`:

```python
note = {"gc": "mirror-dominated — global demote/GC lever, not a local prune",
        "justify": "justified — nothing safely prunable (see entries[])",
        "prune": "⚠ gate fired but not acted on — surface candidates + prune-or-justify"}.get(str(rem.get("lever", "")), "")
```

while the outcome the reader needs is `(lever, candidates_surfaced, pruned, achieved_index, reaches_budget)`.
Three measured consequences, each reproduced by driving `rd.render()`:

- **It self-contradicts, and the `✓` pair is worse than the alarm pair.** The `reaches_budget is False`
  line and the resolved-by-lean `✓` line are **separate `if`s, not a chain**, so neither is reached by the
  `if/elif` above them. For one state the panel emits a **sanction beside a SUCCESS**:
  `achieved_index=900, reaches_budget=False` → the *"prune can't reach budget → prune-safe-THEN-standing-justify
  the residual"* remedy **and** *"✓ gate resolved by rebuild-lean — index back under budget, no eviction
  needed"*. **2 of 12** rows in §3.1's table do this; **18 of 324** states did in the wider sweep.
- **Rewriting one label swaps the verdict.** With byte-identical data, `lever=justify` renders
  *"justified — nothing safely prunable"* where `lever=prune` renders *"⚠ gate fired but not acted on"*.
  **6 of 12** truth-table rows change verdict when only `lever` is rewritten. This is the enforcement hole
  `weakest-enforcement-site-wins` names: the invariant is only as strong as the surface that can restore
  the old state, and one field rewrite is that surface.
- **The reassuring sentence can be false.** `candidates_surfaced` is read by **none** of the three notes.
  The note for `cand=0` and for `cand=5` is **byte-identical** — so *"nothing safely prunable"* is emitted
  for a record that surfaced five candidates. The claim is precisely the thing the data would have to
  support, and the data is never consulted.

**Scope: NOT ASCII-only, and revision 3 was wrong to say so.** The HTML archive carries none of these
three strings, so it has no equivalent *derivation* defect — but the record contains **no operand for the
mirror-vs-prune distinction**, so the ASCII renderer is structurally unable to tell a mirror-dominated
store from a locally-authored overflow. The `gc` verdict exists in the routing and nowhere in the data.
**E1 therefore gains a producer line** (§2.1), which is why the cycle is no longer renderer-local.

### 1.2 E2 — `+N more blocked` degrades to a false total, and the HTML twin already fixes it

The ASCII registrar draws `… +{_n_blocked - _shown_b} more blocked` where the two operands come from
**different sources**: `_n_blocked` from the **record** (`workflow_proposals.n_blocked`, the
producer's count) and `_shown_b` from the **local display list**. When `candidates[]` is empty and
`n_blocked: 30`, the panel prints `+30 more blocked` with **zero rows drawn** — `more` meaning
"beyond what is displayed" collapses to the whole total — and then prints
`0 fleet-candidates — the honest cold state (never invented breadth)` on the **very next line**.
Measured: both lines render.
The state is reachable by design, because `sync_global` computes the counts over the *original*
candidate list while persisting the *merged* one, so an all-blocked window yields exactly this.

**This one IS a parity defect, and the HTML already has the answer.** `dashboard.sections.js` branches
on `!board && num(WP.n_blocked,0)>0` and emits a **counts-only breakdown** instead of a phantom tail:

```javascript
if(!board && num(WP.n_blocked,0)>0){
  var bParts=[];
  if(num(WP.n_generic,0)>0) bParts.push(num(WP.n_generic,0)+" generic-cli");
  if(num(WP.n_day_spread,0)>0) bParts.push(num(WP.n_day_spread,0)+" single-day");   // ← DEAD, see below
  var bRest=Math.max(0,num(WP.n_blocked,0)-num(WP.n_generic,0)-num(WP.n_day_spread,0));
  if(bRest>0) bParts.push(bRest+" single-node");
```

The ASCII renderer is the outlier, and `n_generic`/`n_day_spread` are produced (`sync_global.py`) and
read by the HTML and by **no ASCII renderer** — the data is already in the record.

**The HTML's breakdown has a DEAD ARM, and porting it faithfully would import a line that cannot exist.**
`:146` sets `nSpread = num(WP.n_day_spread, <derived count>)`, and `:181` appends to `board` whenever
`nSpread` is truthy — which makes the `!board` guard at `:194` **false** in exactly the states where
`:197` could fire. Proof and measurement in §3.2. The `single-day` part is unreachable, so the ASCII port
must **omit** that arm, and §2.2 says why in the spec so the omission is not read as a bug.

**The existing pin cannot see the case it names.** `smoke.py`'s RC-89 check (*"the ASCII registrar caps
blocked rows at 8 + the '+N more' tail"*) builds its record with **no `n_blocked` key at all**, so
`_n_blocked` falls back to `len(_blocked)` and both operands share a source. The pin is green by
construction on the only case that can fail.

### 1.3 E3 — the absent-vs-empty default, at eleven sites

`_clean(record.get("session", "?"))` — `dict.get`'s default fires only on **absent**, so `session: ""`
renders a hole where the fallback was intended. `_clean` is `_CTRL.sub("�", str(s))`: it strips
control characters and does nothing else, so `""` survives intact.

Measured by AST census over `render_dashboard.py`: **12** sites of the form `_clean(x.get(<key>, <non-empty
string>))`, of which **1** already carries the correct idiom (`_clean(ident.get("domain_id", "unknown"))
or "unknown"`) and **11** do not.

**The corrected idiom is not an invention — it is already in the same file at nine sites, in four
syntactic positions.** Revision 3 said *seven sites, two forms*, which was itself the failure mode this
section describes: a census pattern narrower than its claim. Enumerated exhaustively:

| Position | Form | Sites |
| --- | --- | --- |
| BoolOp inside `_clean` | `_clean(X.get(k) or D)` | **5** — `:650`, `:721`, `:722`, `:1082`, `:1120` |
| BoolOp outside `_clean` | `_clean(X.get(k, D)) or D` | **1** — `:598` (the `domain_id` site) |
| BoolOp nested in a `str()` | `_clean(str(X.get(k) or D))` | **2** — `:1038`, `:1136` |
| bare variable | `_clean(<var> or D)` | **1** — `:631`, no `.get` at all |

The third position is the one every summary missed, **and it is invisible to an AST census that tests
"is the `_clean` argument a `BoolOp`"** — the argument there is a `Call`. That is the same narrow-pattern
failure as `par.op is ast.Or` (§3.6), arriving a third time.

**Scope of the census, corrected.** It counts one class, and the table below accounts for all **30**
`.get`-shaped `_clean` calls — **23** carrying a default plus **7** wrapped in `or` — with the other
**17** `_clean(...)` calls taking no `.get` at all. (Revision 3 printed *29 / 23 + 6 / eighteen*; see
§3.3 for why, and note the counts describe **47 call sites over 46 lines** — `:251` carries two calls,
so a line-based census under-counts by one.) The 11 unguarded sites are those whose default is a
**non-empty string** — the fallback was *intended* to fire and does not. The remaining `.get`-shaped
calls are a different question and are deliberately **not** touched:

| Form | Sites | Why it is not this defect |
| --- | --- | --- |
| `_clean(x.get(k, "?"-like))`, unguarded | **11** | the defect |
| `_clean(x.get(k, D)) or D` | 1 | already correct |
| `_clean(x.get(k)) or D` | 5 | already correct (fires on falsy) |
| `_clean(str(x.get(k) or D))` | 2 | already correct; the `or` sits inside `str()` |
| `_clean(<variable> or D)` | 1 | already correct; no `.get` involved (`:631`) |
| `_clean(x.get(k, ""))` | 9 | absent and empty *both* render blank; there is no non-empty `D` to apply, so `or D` is not the repair |
| `_clean(x.get(k, <expr>))` | 2 | a fallback chain — the default is computed, not a literal |

**A SECOND guard spelling carries the same defect and is outside this census.** `render_dashboard.py`:

```python
_mc = m.get("commit")
_mc = "?" if _mc is None else _clean(str(_mc)[:12])
```

`is None` guards **absent** and passes **empty**, so a marker with `commit: ""` renders a hole where `?`
was intended. Measured: `commit` absent → `MARKER → ?`; `commit ''` → `MARKER → @ 1000.0`. The same shape
repeats at the sibling `_mt`. **The census's pattern requires a `.get(k, <non-empty literal>)`, so it can
never see these, and §2.3's `or D` repair does not apply as written.** Reachability, honestly: **0 of 69**
live persisted markers carry an empty commit — but `_persist` runs `reconcile_marker`, which fills an
empty commit from the state file, so the log is post-reconcile and **is not evidence about the live
render**. Both sites are repaired in this cycle (§2.3); shipping a known instance of the very defect E3
addresses would be worse than a two-line extension.

The nine `_clean(x.get(k, ""))` sites are called out because they are the obvious over-reach: applying
`or "?"` to them would invent a placeholder where the renderer deliberately shows nothing. Whether any
of the nine *should* render `absent` rather than a blank is a real question — `registry_state`'s
producer emits the literal `"absent"` for exactly that state — but it is a **display decision per
site**, not this cycle's consistency repair.

Scope note: the plan that staged this cycle named five sites (`:515`, `:251`, `:280`, `:282`, `:322`).
Measured, it is **11**, and `:515` is not one of them — it wraps a literal string, not a `.get()`. The
plan's list was both short and mis-cited; §3.3 carries the corrected census.

### 1.4 E4 — two declaration-vs-producer drifts, in opposite directions

The cycle record has **three** descriptions of itself: SKILL.md's schema block, the `TypedDict`s in
`memory_status.py`, and the **producers** that actually write the record. The smoke pin compares
**one edge** — `set(skill_block) == set(TypedDict.__annotations__)` — so a pair can agree with each
other *and both disagree with the producer*. Two do.

**(A) `identity.domain_lifecycle` — emitted, never declared.** `store_context.identity_snapshot` is
the sole producer of the record's `identity` block (`memory_status.py` seeds it from
`identity_snapshot(_ctx)`). Its literal has **five** unconditional keys, the fifth being
`"domain_lifecycle": str(getattr(ctx, "domain_lifecycle", "active") or "active")`. `class Identity`
declares five keys too — but a *different* five: it carries `conflicts`, which the producer adds
best-effort at the end of the same function, and omits `domain_lifecycle`. SKILL.md's `identity`
block mirrors the TypedDict exactly, so the emitted key is undeclared on **both** surfaces and no
gate can see it.

**(B) `audit.window` — declared, never emitted.** `class Audit` declares `window: str` and SKILL.md's
`audit` block carries `"window": "phase0..phase5"`. No producer writes it: `audit_diff(before, after)`
returns **five** keys (`memory`, `claude_md`, `repo_doc`, `operations`, `conservation`) and the
record's block is assigned that bare dict — `_cyc["audit"] = diff`. The literal `"phase0..phase5"`
is **written** in exactly three places (`memory_status.py` — the `.mutation-log.jsonl` row that
*prepends* it to the same five; `render_dashboard.py` — a hardcoded display line; and SKILL.md), and
in **no** test file. §3.4 carries the corrected citation.

**The reader, and why revision 3's "no consumer" was wrong.** Revision 3 grepped the *quoted key*
(`audit["window"]`) and concluded nobody reads it. `dashboard.sections.js:356` reads it as a **JS
property access**:

```javascript
+'<details class="captured-details"><summary>File counts & observation window</summary>'+line('Observation window',audit.window)+accounting+'</details>'
```

A grep for `"window"` is structurally blind to `audit.window` — the matcher could not see the shape.
Confirmed in a real browser: a fixture record **with** `audit.window` renders the row
`['phase 0 → phase 5']`; a producer-shaped record (`rec["audit"] = ms.audit_diff({}, {})`, exactly what
`memory_status.py` writes) renders `['Not captured']`. So the live defect is the **opposite** of the one
revision 3 recorded: the archive has a **display whose producer never fills it**, and every real record
shows "Observation window — Not captured" while the committed preview shows a value only the *fixture*
invents.

Two forensics are worth keeping, because each is what makes the drift *invisible* rather than merely
present:

- `window: str` is **not** the only uncommented key in `class Audit` — measured, **four** keys are bare
  (`memory`, `claude_md`, `operations`, `window`); two carry inline dating comments (`repo_doc`,
  `conservation`). *Undatedness cannot single out `window`*, so revision 3's "the one key no maintainer
  revisited" forensic does not hold. What holds is narrower and still useful: `operations` and `window`
  are dateless, and neither is written by `audit_diff`.
- `tests/dashboard_fixture.py` writes a **third** spelling — `"window": "phase 0 → phase 5"` — inside
  a `def sample():` with **no return annotation**. `mypy` is configured to check `tests/`, but an
  untyped literal is `dict[str, Any]` to it, so `typeddict-unknown-key` never applies. That is why
  the fixture's drift survives every gate the repo has.

**The unifying rule, and revision 3 had it backwards.** Revision 3 justified (A) by the *absence* of a
reader and (B) by its presence, then reasoned in opposite directions. The absence premise is **false** —
the archive's generic `capturedTree` renders `domain_lifecycle` (§3.4). The correct rule does not depend
on absence at all:

> **The reader is the invariant.** Whichever of {producer, declaration} the reader's demand is missing
> from is the side that moves.
> **(A)** producer emits **+** the archive displays it ⟹ the **declaration** is the incomplete side. *Add it.*
> **(B)** declaration declares **+** the archive displays it ⟹ the **producer** is the incomplete side. *Add it.*

Both arms reach the same actions revision 3 chose — but (A) reached its action from a false premise, and
a reader who re-derives "no reader" from a `grep` (as revision 3 did) reaches the wrong one. Stating the
rule this way is what makes it derivable rather than lucky. **A generic key dump counts as a reader.**

**One correction to the plan's rationale, kept.** The plan justified "the producer is right" for (A) on the
grounds that *two doctor surfaces depend on it*. Measured, that is not so: `doctor_report` and
`doctor_dict` each independently `getattr(ctx, "domain_lifecycle", "active")` — neither reads
`identity_snapshot`'s output, so neither depends on the key's presence in the *record*. The conclusion
is unchanged, and the real reason is stronger: `ctx.domain_lifecycle` is a genuine `StoreContext`
field (default `"active"`, computed from `control_plane.domain_lifecycle()` at both construction
sites), so a snapshot of the store's identity is incomplete without it.

Independently confirmed in a second measurement pass, which also found the decisive reader: the
attribute gates behaviour. `sync_global`'s pull/promote path refuses on a `deleting`/`deleted` domain
via `life = str(getattr(ctx, "domain_lifecycle", "active") or "active")`. A field that can **refuse a
cross-project pull** is not a display detail — it is state, and the identity snapshot is the record's
only copy of it.

**A sixth identity key, and §1.4 must name it.** `identOf` (`dashboard.template.html`) also probes
`snap.unenrolled`. It is not an E4 drift — `unenrolled` is not part of `identity_snapshot`'s output — but
the archive's identity reader therefore tests **six** keys, and any future claim about "the keys the
archive reads" must be made against that list, not revision 3's five.

### 1.5 E5 — the pin's coverage claim is false, in two ways

The nested-shape pin loop in `tests/smoke.py` — the `for _nm, _obj, _td in [...]` over the SKILL
schema block — closes with a comment asserting that *"the two carve-outs above are now the ONLY
un-pinned shapes."* Measured, the loop is **34 rows over 32 distinct TypedDicts**, while
`memory_status.py` defines **43**. Of the eleven it does not cover, three are pinned elsewhere by name
(`CycleRecord`, `Health`, `Marker` — the top-level spot-checks and the scalar walker), one is the
comment's own documented carve-out (`SchemaDrift`, which the block never enumerates), and **seven**
have both a SKILL.md block and a TypedDict and are pinned by neither:

`Narration` · `DomainEntry` · `UniversalFact` · `GroupLink` · `NetworkCapture` · `StackEdgeFacts` ·
`FactHolding`

**All seven currently agree: the red count is 0 of 7 (§3.5).** So the comment is false about
*coverage*, not about correctness — the seven shapes it hides are today in perfect key agreement.
That falsifies the plan's prediction that extending the pin *"exposes drifts of the same class as
E4"*: there is no drift to fix, and E5 is a pure coverage repair, the cheapest of the five.

**The comment is false in a SECOND way, and revision 3 could not see it.** The seven above are the
**class-shaped** gaps at **depth ≤ 2** — that depth bound was implicit, and it hid four more:

| SKILL path (all **depth 3**) | Keys | Declared as | Documented? |
| --- | --- | --- | --- |
| `workflow_proposals.candidates[0].evidence` | `nodes`, `d`, `n` | `dict[str, Any]` | **no** |
| `workflow_proposals.candidates[0].mechanical` | `fleet_recurrence`, `day_spread`, `distinctive` | `dict[str, Any]` | **no** |
| `workflow_proposals.decline_anchors[0].top[0]` | `t`, `n`, `d` | `list` | **no** |
| `workflow_proposals.decline_anchors[0].top_chains[0]` | `t`, `n`, `d` | `list` | **no** |

The parents *are* pinned (`…candidates[0]`, `…decline_anchors[0]`), but the loop compares **that level's
keys only**, and the four are backed by bare `dict[str, Any]` / `list` — **there is no key set to
compare**. So they are not fixable by adding rows; they are a **third category**: inline sub-shapes this
mechanism structurally cannot reach. Revision 3's guess about which four existed was **inverted** — it
expected two documented carve-out positions; those are `SchemaDrift` (#1) and
`ForwardRef('list[dict]')` (#2), three *other* positions, both documented.

The false comment matters more than a drift would have. A comment that says *only two* is what stops
the next reader from looking — and §3.6 records that this same claim defeated **three** of this
document's own measurement attempts before the number was settled.

## 2. Design

### 2.1 E1 — derive the verdict from the data; keep `lever` as routing; persist the missing operand

**Two changes, and the second is why the cycle reaches the producer.**

**(i) The note stops being a lookup keyed on a label.** The decision is taken from the data, in the
order the outcome space actually has — including the branch `render_dashboard` already has and no
revision of this table mapped:

| # | Data state | Verdict |
| --- | --- | --- |
| 1 | `pruned` **and** `achieved_index` both **absent** | **`pending Phase 5`** — the existing `↓` detail line **is** the verdict; no note |
| 2 | `pruned > 0`, **or** the index came back under budget | **acted** — the existing `↓` / `✓` lines already say so; no note |
| 3 | `reaches_budget is False` | the remedy line **is** the verdict — emit no second note (this is the sanctioned prune-then-justify state) |
| 4 | `candidates_surfaced > 0` | ⚠ gate fired but not acted on — surface candidates + prune-or-justify |
| 5 | `candidates_surfaced == 0` | 0 candidates surfaced — record the justification, or re-triage |
| 6 | `candidates_surfaced` **absent** | no count asserted — the gating question is **not** answerable from this record |

Row 1 exists because `render_dashboard` has a dedicated branch for "neither key present" that emits
`pruned/achieved pending Phase 5` — without it the table claims an order the code does not have, and a
record with no `candidates_surfaced` would be told *"0 candidates surfaced"* directly beneath
*"pending Phase 5"*.

Rows 5 and 6 are separate on purpose. This cycle's E3 is *absent ≠ empty*, and a design that
resolved both to the same verdict would reintroduce that defect one section after describing it: a
record that never carried the field would be told it surfaced **zero** candidates, which is a claim
its data does not support. `0` is a measurement; `absent` is the lack of one.

**Row 2's predicate must be stated exactly, because the naive form is catastrophic.** `ai` comes from
`_num`, which maps absent/`None`/`""` → `0.0`, so the live guard at `:887` is

```
acted := ((rem.get("pruned") or 0) > 0
          or ((not pruned) and ("achieved_index" in rem) and 0 < ai <= budget_tok))
```

The `"achieved_index" in rem` conjunct is what keeps **absent** and **0** distinct. Swept over 324
states: the naive form (`pruned > 0 or ai <= budget_tok`) makes an absent `achieved_index` permanently
"acted" → **no note ever** — which is the script's own fresh over-budget record, since
`memory_status.py` writes neither key and `SKILL.md` seeds `"achieved_index": 0`. And it collapses
E1-c: both notes become `""` and tie.

`lever` is **not** removed from the panel: the section header already prints `lever {LEVER}`, which is
the routing decision the producer made, and it may keep a routing line. What it may no longer do is
**select the verdict** — the ⚠ must not appear or vanish because one routing **label** was rewritten.
(That phrasing is deliberate: E1-c *requires* `candidates_surfaced` 5→0 to swap the verdict, so the
invariant is about the label, not about "one field".)

The `"nothing safely prunable"` phrasing is dropped rather than repaired: it asserts a fact about the
store (nothing *is* prunable) that no field carries. The replacement states what the record actually
says (`0 candidates surfaced`), which is the same discipline Cycle D applied when it refused to let a
clause infer presence from absence.

**(ii) The remedy line is gated on `not resolved_by_lean`.** The remedy (`:892`) and the resolved-by-lean
`✓` (`:894`) are separate `if`s, so for `achieved_index=900, reaches_budget=False` the panel emits a
sanction *and* a success. Fix: the remedy fires only when the lean path did **not** resolve. This is
what makes E1-a a single-verdict pin rather than a two-line assertion.

**(iii) The `↓` detail line must respect absent-vs-zero.** Measured on the producer's own pre-pass seed
shape (`{required: True, lever: "prune"}`, no `pruned`/`achieved_index`):

```
↓ 0 candidate(s) surfaced · pruned/achieved pending Phase 5 · projected index ≈0 tok
⚠ gate fired but not acted on — surface candidates + prune-or-justify
```

`cand = _num(rem.get("candidates_surfaced", 0))` renders **absent as `0`** — so the line §2.1 exists to fix
tells the reader a count the record does not have, directly above the note. **The fix must cover the `↓`
line, and E1-d must assert the LINE, not only the note** — otherwise the pin certifies the note while the
artifact still makes the forbidden claim. The file's own idiom is already there: the absent
`pruned`/`achieved_*` arm prints `pending Phase 5` and never `≈0`.

**(iv) The mirror verdict needs an operand the record does not carry.** Measured: `lever = "gc" if share >
_MIRROR_DOMINATED else ("prune" if cands else "justify")` — `gc` routes **before** prune, so
`candidates_surfaced > 0` **co-occurs** with `gc`. With no `mirror_share` in the record:

| record | today | a data-derivation without the operand would give |
| --- | --- | --- |
| `gc, cand=5, pruned=0, rb=True` | `mirror-dominated — global demote/GC lever, not a local prune` | ⚠ *prune-or-justify* — **advice the routing says is futile** |
| `gc, cand=5, pruned=0, rb=False` | mirror note **+** remedy line | remedy only — the *"not a local prune"* clause **deleted** |

**So the fix persists `mirror_share`.** `memory_status.py` computes `share = mirror_index_tokens /
index_tokens` and writes `"mirror_share": round(share, 2)` into the triage dict — and then **drops it**
at the record writer. The line is added there. It survives the refresh path because that path **merges**
(`rem.update(scratch["remediation"])`).

**Why persist rather than read `network.totals`:** `network.totals` is a **FLEET** aggregate (summed per
node by the sync path), while `_MIRROR_DOMINATED = 0.5` is calibrated against the **STORE-LOCAL**
`share`. A fleet sum against a store-local threshold is the **wrong operand** — so persisting is not
merely the safer option, it is the only correct one.

**Consequences, stated plainly:** E1 now edits the **producer** (`memory_status.py`), **two declarations**
(`Remediation` + SKILL.md's `remediation` block), and **§2.4's table grows a third row**. E1-b survives as
the reason the mirror row keys on `mirror_share` — it varies only `lever` while `mirror_share` is fixed,
so keying the suppression on the label would *fail the cycle's own pin*.

**This fix REDs a currently-green check, and that check is the defect's own pin.** `smoke.py`'s
v0.1.35 "still over budget" arm builds `lever=prune, candidates_surfaced=1, pruned=0,
reaches_budget=False` — precisely the sanctioned prune-then-justify state — and asserts
`"not acted on" in render(...)`. The coherent behaviour makes that assertion false by design. The
check is **rewritten, not deleted** (§4.2): post-fix it asserts the remedy line present and the ⚠
absent, which is E1-a. Its sibling — the rebuild-lean arm asserting `"not acted on" not in ...` for
`reaches_budget=True` — is unaffected, because the resolved case still takes the `resolved_by_lean`
branch.

### 2.2 E2 — port the HTML's counts-only breakdown, minus its dead arm

Keep the `+N more` tail for the case it was written for (rows drawn, more exist). Add the HTML's
branch for the case where there is nothing to draw but the record says there is something to count:

- **rows drawn = 0 and `n_blocked > 0`** → the counts-only breakdown,
  `N blocked — X generic-cli · Z single-node — counts-only by design…`.
- the `0 fleet-candidates — the honest cold state` line is **suppressed** whenever `n_blocked > 0`:
  it and the tail are two claims about one state, and they contradict.

**Three port details, each measured, each load-bearing.**

1. **Match the JS guard exactly — it is `!board`, not "rows drawn = 0".** `board` is non-empty when any
   card rendered, when the day-spread note fired, *or* when unjudged rows exist. The cycle's title is
   parity; a deliberate widening smuggled in under it would be a second, unstated change.
2. **Carry the clamp.** The remainder is `Math.max(0, n_blocked − n_generic − n_day_spread)` and is
   emitted only `if(bRest > 0)`. Unclamped, `{n_blocked:10, n_generic:30, candidates:[]}` prints
   **`-20 single-node`**. Faithful porting means the **omission**, not the negative.
3. **OMIT the `single-day` arm, and say why here.** The HTML cannot draw it — the arm is unreachable by
   construction (§3.2). Carrying it into the ASCII would give this renderer a line the other can never
   print, which is the opposite of parity. **Do not "restore" it later without re-reading §3.2.**

**The counts-only note's own justification must change.** The JS sentence reads *"— counts-only by
design (samples are not persisted in the archive; the terminal consult shows them)."* Ported into the
**terminal**, that is false in a self-referential way: this renderer **is** the terminal consult, so it
sends the reader to the place they already are, for samples the ASCII never had either. The true reason
is SKILL.md's own: *"generic-cli / single-node are counts only."* **Cite that; do not port the archive
clause.**

**One implementation trap, recorded so it is not rediscovered as a bug — and stated the right way round.**
The registrar block defines its locals in an order that matters: `_n_blocked` (`:1114`), `_shown_b`
(`:1130`), the tail line (`:1131`), **`_anch` (`:1133`)**, then the cold-state line (`:1139`/`:1140`).
So the suppression at `:1139` must key on **`_n_blocked > 0`**, not on `_anch`. `_anch` is already in
scope there and looks like the natural operand, but **it describes a different set** —
`decline_anchors`, not blocked rows. Keying on it would suppress the cold-state line for a record that
has anchors and no blocked rows, which is a third state neither renderer has a rule for. *(Revision 3
said `_anch` was "defined after" the line; measured, it is defined **before** it. The trap is real, but
only for the set argument — the ordering clause was wrong and is deleted.)*

"Rows drawn" is computed as `len(_fleet) + _shown_b`, and both are in scope at `:1131`.

**The parity claim is pinned for the first time, and it needs two fixtures, not one.** The declared
fixture for E2-a is `{n_blocked:30, n_generic:30, candidates:[], decline_anchors:[]}`. With
`n_day_spread` absent and the remainder `30 − 30 − 0 = 0`, **two of the three count arms the line could
carry are never drawn** — so a pin on that fixture alone goes GREEN on an implementation that hardcodes
the generic-cli part. (After the dead-arm proof the line has two arms, not three, so the fixture must
exercise **both**:)

- `n_blocked: 30, n_generic: 12, n_day_spread` **absent**, `candidates: []` →
  the exact two-part string `12 generic-cli · 18 single-node`.
- `n_generic + n_day_spread > n_blocked` → the remainder **omitted, never negative** — this pins the
  `Math.max` semantics, not merely the arithmetic.

**That second bullet is a guard, and this is the only place it is said.** It cannot fail on pre-fix
code — pre-fix the line does not exist at all — so it is not a pin. What it catches is a *future* edit
that drops the `max(0, …)` or its `> 0` emission test while leaving the first fixture green. §4.1's
row still reads **RED** because the *first* fixture is a genuine pin, so this guard half is invisible
in that table — unlike E3-d, whose whole check is a guard and therefore gets a row of its own with its
red named. Same species, bundled rather than split; disclosed here instead of left for a reader to
infer from the fact that `-20 single-node` is not a pre-fix string.

The data is real — `n_day_spread` is declared in `memory_status.py` and written by `sync_global.py` —
so the fuller fixture is a real shape, not a synthetic one. **No existing check reads either renderer's
output**: `smoke.py:6668` asserts a *record* invariant (`n_generic + n_day_spread <= n_blocked`) and
`smoke.py:15111` asserts an HTML *source* string. Neither would move.

### 2.3 E3 — apply the idiom already in the file

`_clean(x.get(k, D))` → `_clean(x.get(k, D)) or D` at the **11** measured sites. Pure presentation.

**And repair the second guard spelling at both marker sites:**
`_mc = "?" if _mc is None else (_clean(str(_mc)[:12]) or "?")`, likewise `_mt`. §1.3 states why the
census cannot see these and why the log is not evidence about the live render.

### 2.4 E4 — add to both declarations, and move the producer

**Three edits, each made together across every surface it touches** — because a declaration edit alone
would break the existing pin, and a producer edit alone would leave the drift.

| Key | Edit | Why |
| --- | --- | --- |
| `identity.domain_lifecycle` | **add** to `class Identity` + SKILL.md's `identity` block | The field is real on `StoreContext`, emitted unconditionally, **and displayed**; the *declaration* is the incomplete side. |
| `audit.window` | **producer emits it** (`audit_diff`); declarations **unchanged** | The key is declared, the archive **reads it**, and no producer fills it. The **producer** is the incomplete side. |
| `Remediation.mirror_share` | **add** to the TypedDict + SKILL.md + the record writer | E1's operand (§2.1). Not an E4 drift; listed here because it is the same three-surface edit. |

**Why (B) is not "remove from both", and the reasoning is the cycle's own rule.** Three options were
costed:

| | Declarations | Producer | Reader | Verdict |
| --- | --- | --- | --- | --- |
| (a) remove from both | silent | silent | **still reads it** | a reader reading an undeclared key — **E4(A)'s defect mirrored**. Reject. |
| (c) remove both + delete the HTML row | silent | silent | deleted | three edits to delete a display, and the ASCII panel's hardcoded window line **still** claims the span unbacked. Reject. |
| **(b) producer emits** | keep (already right) | **adds the key** | renders a real value | **all surfaces agree, one producer edit.** Adopt. |

Purely additive on a `total=False` TypedDict for (A) and the `mirror_share` row, and producer-only for
(B) — so **every archived record still renders** and no install observes an incompatible schema. This
cycle's compatibility claim is discharged by construction rather than by testing.

**The pin: extend the declaration test from one edge to three.** The existing pin proves
`SKILL == TypedDict` — an edge that *cannot* fail for either defect, because in both cases the pair
agree with each other. The missing edge is **producer ↔ declaration**, and it is pinned by *calling*
the producer rather than by reading its source — two runtime pins, one per direction:

```python
set(sc.identity_snapshot(ctx)) <= set(ms.Identity.__annotations__)   # nothing undeclared is emitted
set(ms.Audit.__annotations__)  <= set(ms.audit_diff({}, {}))         # nothing declared is phantom
```

The directions are deliberately opposite, and that is the design: an **undeclared emission** and a
**phantom declaration** are different defects with different repairs, and one symmetric equality
would conflate them. Both land inside smoke.py's existing hermetic `resolve_store` block, so the pin
runs the real constructor on a temp project rather than a stand-in. `audit_diff` is total on
`({}, {})` — it returns its five keys for empty snapshots — so that pin needs no fixture. **Pin B's
pre-fix colour changes with this revision** (it is still RED, now because the producer omits a declared
key rather than because the declaration should drop it); §3.4 records both.

**The fixture moves, and it moves in the direction the decision implies.** `tests/dashboard_fixture.py`
is edited in the same change: its invented third `window` spelling is replaced by **the producer's real
value** (the key is now emitted, so the fixture must carry a producible one), and `domain_lifecycle` is
added to its identity literal. **These keys are NOT invisible** — §1.4 established that the archive
renders `window` as the "Observation window" row and `domain_lifecycle` inside "Identity & registry
state". So the correction is user-visible, not merely a byte change:

- the preview's **Observation window** row changes from the fixture's invented `phase 0 → phase 5` to
  the producer's real span — the first time that row has ever shown a true value;
- the preview gains a **`domain lifecycle`** field in its identity disclosure.

That fixture feeds `docs/previews/nocturne/index.html`, which *embeds* the record's JSON, and
`docs_links.py::check_preview` asserts the preview is byte-identical to a fresh render — so it must be
regenerated **deliberately** in the same PR, and the browser suite re-run against the new bytes. That
gate fails in the safe direction (a stale preview cannot pass), which is why the regeneration is
routine rather than risky.

### 2.5 E5 — make the claim true, then keep it true

Seven rows are added to the loop, one per gap shape, at the SKILL path each is spelled at
(`narration`, `network.domains[0]`, `network.universal_facts[0]`, `network.group_links[0]`,
`network.capture`, `network.stack_edge_facts[0]`, `network.fact_holdings[0]`). The comment is then
rewritten from a coverage *claim* into a statement of what the loop covers **and what it cannot**:

> Covers every nested shape the block enumerates **at depth ≤ 2** that has a TypedDict. Four depth-3
> inline sub-shapes (`…candidates[0].{evidence,mechanical}`, `…decline_anchors[0].{top[0],top_chains[0]}`)
> are backed by bare `dict[str, Any]` / `list` — **no key set exists to compare**, so this mechanism
> cannot reach them. `SchemaDrift` is not enumerated in the block. The producer→declaration direction is
> pinned separately, and only for the two shapes E4 touches.

That last clause is the honest boundary: after this cycle the loop covers SKILL↔TypedDict completely
for enumerable shapes at depth ≤ 2, but **the forward direction remains unpinned for 41 of the 43**.
Saying so in the comment is what stops the next reader from re-deriving a false *only two* out of a
green suite.

**These seven rows are GUARDS, not pins.** They cannot fail on pre-fix code — pre-fix they do not
exist — so calling them pins would be false (`a-check-added-by-a-fix-may-not-flip`). What they buy is
coverage: from this revision forward, a drift in any of the seven reds the suite. §3.5 states what they
would cost if they ever fired.

**A forward-direction pin, if ever added, must compare with `⊆`, never `==`.** Measured: six of the
seven producers emit **exactly** their annotation set, but `narration_block` emits `{verdict, reason}`
and adds `gaps` **only when non-empty** — legal under `total=False`, and an equality-form forward pin
would RED *falsely* on the one shape that is correct. This is written down **before** the check is
authored, because `==` is the form an author reaches for.

**The stop rule does not fire.** It triggered above ~8 shapes; measured, the gap set is 7 with a red
count of 0, so the whole remainder fits this cycle and no third cycle is staged. *(The cap is a
maintainer judgement recorded in the plan, not a constant in the tree.)*

## 3. Measurements

Every figure below was produced on revision `1d97f54` by the command shown, after the measurement
scripts were themselves corrected (§3.6).

### 3.1 E1 — the outcome-space truth table

`render_dashboard.render()` driven across `lever × candidates_surfaced × pruned × reaches_budget`,
recording which of the five verdict strings appears — 12 data rows × 3 labels.

| candidates | pruned | reaches_budget | `gc` | `justify` | `prune` |
| --- | --- | --- | --- | --- | --- |
| 0 | 0 | False | mirror-dominated **+** can't-reach | justified **+** can't-reach | ⚠ not acted **+** can't-reach |
| 0 | 0 | None | mirror-dominated | justified | ⚠ not acted |
| 0 | 0 | True | mirror-dominated | justified | ⚠ not acted |
| 0 | 2 | False | can't-reach | can't-reach | can't-reach |
| 0 | 2 | None | *(no note)* | *(no note)* | *(no note)* |
| 0 | 2 | True | *(no note)* | *(no note)* | *(no note)* |
| 5 | 0 | False | mirror-dominated **+** can't-reach | justified **+** can't-reach | ⚠ not acted **+** can't-reach |
| 5 | 0 | None | mirror-dominated | justified | ⚠ not acted |
| 5 | 0 | True | mirror-dominated | justified | ⚠ not acted |
| 5 | 2 | False | can't-reach | can't-reach | can't-reach |
| 5 | 2 | None | *(no note)* | *(no note)* | *(no note)* |
| 5 | 2 | True | *(no note)* | *(no note)* | *(no note)* |

Read the table two ways; both are the defect:

- **Down a row**, the data is identical and only `lever` differs — **6 of 12** rows change verdict.
- **Across the `candidates` columns**, the note is *invariant*: the `0` and `5` halves are identical,
  so `candidates_surfaced` is read by no note at all.

**2 of 12** rows emit two verdict lines for one state. Verified directly: the note string for `cand=0`
and `cand=5` at `lever=justify` is byte-identical — `justified — nothing safely prunable (see
entries[])`.

**THE GRID IS BLIND, AND THAT IS A FINDING ABOUT THE GRID.** This table holds `achieved_index` at a
value **above** `budget_tokens` on **every** row, so `resolved_by_lean` is false in all 12 and the `✓`
branch is **unreachable** throughout. **2 of 12** therefore describes the *alarm* pair only; the
sanction-beside-success pair (`achieved_index=900, reaches_budget=False`, §1.1) is **18 of 324** in the
wider sweep and appears **nowhere** above. Worse, the direction reverses with the held value: when
`0 < ai <= budget_tok` the whole table **collapses to 0 of 12** — every row resolves by lean and no note
renders at all. A 12-cell grid that silently fixes a third dimension to one value is exactly the defect
this cycle exists to delete, committed by the measurement that documents it. The replacement grid varies
`achieved_index` across {absent, 0, under-budget, over-budget} and is the honest instrument; §4.1's pins
are written against it.

### 3.2 E2 — the degenerate render, and the dead arm

One record, `workflow_proposals={"n_blocked": 30, "n_generic": 30, "candidates": [], "decline_anchors": []}`:

```
    … +30 more blocked — see the consult (cm workflows . --registrar)
    0 fleet-candidates — the honest cold state (never invented breadth)
```

Rows drawn in the registrar panel: **0**. Both lines render. The first is a tail with no head; the
second denies the count the first asserts.

**The dead arm, proven.** The HTML's breakdown looks like it can carry three parts. It can carry two:

```javascript
:146  var nSpread=num(WP.n_day_spread, wc.filter(…).length);   // = the field, else a derived count
:180  var board=named.map(cardHtml).join("");
:181  if(nSpread) board+='<div class="reg-more">'+nSpread+" showed up on more than one project…</div>";
:189  board+='<div class="reg-group">…unjudged…</div>';        // only if evRows.length
:194  if(!board && num(WP.n_blocked,0)>0){
:197      if(num(WP.n_day_spread,0)>0) bParts.push(num(WP.n_day_spread,0)+" single-day");
```

`:146` and `:197` read **the same field through the same coercion**, differing only in the default —
`num(x,d)` is `parseFloat` + `isFinite` (`dashboard.template.html`). Therefore:

> `num(WP.n_day_spread,0) > 0` ⟹ `nSpread` truthy ⟹ `board` non-empty at `:181` ⟹ `!board` **FALSE** at
> `:194` ⟹ **`:197` is never evaluated.**

**Measured, with `num` and the four guard expressions extracted verbatim**, over the reachable input space
(17 values³ × 3 fallbacks × 2 `named` × 2 `evRows`): the breakdown rendered in **1156 states** and a
`single-day` part appeared in **0**. The last assumption is closed — `board` is only ever **grown** before
the guard (`:180` assign, `:181`/`:189` append; the `:200` assign is *inside* the guarded block), verified
by listing all nine `board` occurrences in the file.

**So a fixture asserting `n_generic:12, n_day_spread:8` → `"… · 8 single-day · …"` is impossible to
satisfy**: with `n_day_spread:8` no breakdown renders at all. That exact string is producible by
**neither** renderer. §2.2's replacement fixtures are the producible two.

### 3.3 E3 — the site census

AST census (not a grep — a `BoolOp` is invisible to a textual search) over every `_clean(...)` in
`render_dashboard.py`: **12** sites of the pattern `_clean(x.get(<key>, <non-empty str literal>))`,
**1** guarded, **11** unguarded.

| Site | key | default |
| --- | --- | --- |
| `_clean(p.get("name", "?"))` | `name` | `?` |
| `_clean(n.get("node", "?"))` ×2 (the width probe and the row) | `node` | `?` |
| `_clean(net.get("trigger", "?"))` | `trigger` | `?` |
| `_clean(record.get("project", "?"))` | `project` | `?` |
| `_clean(record.get("session", "?"))` | `session` | `?` |
| `_clean(e.get("name", "?"))` | `name` | `?` |
| `_clean(hier.get("worst_path", "?"))` | `worst_path` | `?` |
| `_clean(f.get("name", "?"))` | `name` | `?` |
| `_clean(t.get("t", "?"))` | `t` | `?` |
| `_clean(c.get("form", "?"))` | `form` | `?` |
| `_clean(ident.get("domain_id", "unknown")) or "unknown"` | — | **already guarded** |

Reproduced: a record with `session` **absent** renders `p · session ?`; the same record with
`session: ""` renders `p · session` — the field is present, empty, and indistinguishable from a
rendering bug.

**The population the census counts is itself load-bearing, so the pin asserts it too.** Mutating one
repaired site back to a 1-arg `.get` leaves `0 unguarded` **still GREEN** — the site *leaves the
population*, so the count does not move:

```
census unguarded: 0  -> still GREEN — the census CANNOT see this regression
  session absent   -> 'p · session None'
  session empty    -> 'p · session'
```

This is `a-complete-guard-inverts-its-question`: the pattern whitelists the **forms** it expects rather
than the **positions** it collects. **Fix:** assert the collected count **alongside** the verdict —
post-repair the population is still **12** (all 11 repaired sites keep their 2-arg `.get`, plus the
already-guarded `:598`), so `population == 12 and unguarded == 0` catches a dropped default, while a
newly-added unguarded site is still caught by `unguarded == 0`.

**Output-neutral on the committed preview — for the ASCII render, which is what was measured.**
`_clean` is a module global, so it can be instrumented: during a full render of the preview fixture's
record and its history, `_clean` is called **598** times (68 on the record + 530 across the 8 history
rows) and receives the empty string **0** times. So the `or D` arm cannot fire on the fixture, and the
**ASCII** render of the fixture does not move.

**The preview argument needs a different instrument, and revision 3 cited the wrong one.**
`write_preview()` calls `render_dashboard._clean` **zero** times — the preview is built by
`render_html.build_html`, which has no `_clean` at all. So the 598/0 figure **cannot** establish that the
preview does not move; the conclusion is true, but the cited evidence does not support it. The structural
reason is separate and cheap: a different module with no `_clean` in its path. Both statements are kept,
each attached to what it actually proves.

### 3.4 E4 — the two producer edges, measured

Census over `memory_status.py` (AST): **43** TypedDicts defined. `identity_snapshot` is the sole
writer of the `identity` block (`memory_status.py` seeds it from it); `audit_diff` is the sole writer
of the `audit` block (`_cyc["audit"] = diff`). Both were **called**, not read:

| Pin | Producer call | Declared side | Pre-fix |
| --- | --- | --- | --- |
| A | `set(sc.identity_snapshot(sc.resolve_store(proj, environ=env)))` | `set(ms.Identity.__annotations__)` | **RED** — `domain_lifecycle` emitted, undeclared |
| B | `set(ms.audit_diff({}, {}))` | `set(ms.Audit.__annotations__)` | **RED** — `window` declared, never emitted |

Measured on the **real** `resolve_store` path in a hermetic temp project — the pin runs the
constructor, not a stand-in. Pin A returned exactly
`['cross_project_allowed', 'domain_id', 'domain_lifecycle', 'enrolled', 'registry_state']`; note
`conflicts` is legitimately absent, because a non-Git temp project has no control registry to read,
which is the documented "best-effort, omitted when unread" contract working. Both pins were then
re-evaluated against a simulated post-fix declaration and returned GREEN. **With this revision's
decision (§2.4), pin B's post-fix GREEN is reached by the producer emitting the key** — the pin's
*direction* is unchanged; only the repair changed.

**The reader, measured three ways — and revision 3's two claims were both false.**

- `dashboard.sections.js:356` reads `audit.window` as a property access and renders it as the
  "Observation window" row. Browser-confirmed: fixture record → `['phase 0 → phase 5']`;
  producer-shaped record → `['Not captured']`. **So there IS a consumer**, and the live defect is a
  display whose producer never fills it.
- The archive's identity disclosure renders `domain_lifecycle` too:
  `dashboard.sections.js:351` → `extra('Identity & registry state', c.identity)` → `:264` `extra` →
  `:256` `capturedTree` → `:261` `Object.keys(v).map(…)`. **A generic key dump**, so
  *"appears 0 times in the template and the sections bundle"* is false — a grep for the key name
  cannot see `Object.keys`.
- The panel line that *appears* to render `window` —

```
window phase0..phase5 — any change in the span is attributed to this pass
```

  — is a **hardcoded display string** that never reads the key. Provenance: it is a display claim
  matching the record's semantic window, **not** a rendering of `audit["window"]`.

**The citation, corrected.** Revision 3 named *"the `.mutation-log.jsonl` row at `smoke.py:5972`, in
which the literal legitimately lives"*. Both halves are wrong: `smoke.py:5972` is
`_w79 = _jsonB.loads(_rows79[0])["window"]` over `plugin_data_dir()/"fleet-usage.jsonl"` — the
**fleet-usage ledger**, inside the v0.1.79 `--harvest` test (the same "harvest/history rows" the
sentence had already listed, so it was **counted twice**). And the literal `phase0..phase5` appears in
**no test file**: `grep -rn 'phase0\.\.phase5' plugins/ tests/` returns only `memory_status.py`
(the log row), `render_dashboard.py` (the display line), and `SKILL.md`.

### 3.5 E5 — the coverage census, its red count, and the third corner

AST census (the loop's row→TypedDict mapping read from the AST, never from source text):

| Figure | Measured | Plan claimed |
| --- | --- | --- |
| TypedDicts defined in `memory_status.py` | **43** | 43 ✓ |
| pin-loop rows | **34** | 34 ✓ |
| distinct TypedDicts the loop covers | **32** | 30 ✗ |
| shapes with a block + a TypedDict, pinned by neither (depth ≤ 2) | **7** | 7 ✓ |
| depth-3 inline sub-shapes with **no comparable key set** | **4** | — |

The seven, with the loop's own comparison applied to each:

| Shape | SKILL path | Keys | Verdict |
| --- | --- | --- | --- |
| `Narration` | `narration` | 3 | **OK** |
| `DomainEntry` | `network.domains[0]` | 1 | **OK** |
| `UniversalFact` | `network.universal_facts[0]` | 3 | **OK** |
| `GroupLink` | `network.group_links[0]` | 5 | **OK** |
| `NetworkCapture` | `network.capture` | 10 | **OK** |
| `StackEdgeFacts` | `network.stack_edge_facts[0]` | 3 | **OK** |
| `FactHolding` | `network.fact_holdings[0]` | 6 | **OK** |

**Red count: 0 of 7.** The seven were spot-checked rather than trusted, because `DomainEntry` matching on
a single key is exactly the shape a false-OK takes: its block was printed and is genuinely
`{"domain": "personal"}` against `{'domain': str}`. **Suspicion checked and refuted:** the one-key shape
looks like the E4 failure where *both* declarations are wrong together and no declaration-vs-declaration
pin can see it — but the **producer** emits exactly `{"domain"}` (`sync_global.py`), so one annotation is
correct. *Narration*'s block carries a `_` doc key that the loop strips by design, and *NetworkCapture*
matches on all ten.

**The third corner, measured for the first time.** Every check above compares **SKILL ↔ TypedDict**.
Nobody had walked the edge that E4's two drifts actually lived on — the **producer**. Read directly:

| Shape | Producer | Emitted keys | vs declaration |
| --- | --- | --- | --- |
| `DomainEntry` | `sync_global.py` — `domains = [{"domain": d} for d in …]` | 1 | ✓ **exact** |
| `UniversalFact` | `_uni_rows.append({"name", "domain", "held"})` | 3 | ✓ **exact** |
| `GroupLink` | `_links.append({"group","home_domain","members_n","facts_total","facts"})` | 5 | ✓ **exact** |
| `StackEdgeFacts` | `stack_edge_facts.append({"a","b","names"})` | 3 | ✓ **exact** |
| `FactHolding` | `_bounded_fact_holdings` — `{k: fact[k] for k in ("fact_id","name","domain","scope")}` + `held_n` + `holder_sids` | 6 | ✓ **exact** |
| `NetworkCapture` | `{"basis","group_scope","read_failure_scope", **counts, **_diagnostics}` (3 + 5 + 2) | 10 | ✓ **exact** |
| `Narration` | `dream_procedure.narration_block` — `{"verdict","reason"}`, `+gaps` **iff non-empty** | 2 or 3 | ✓ **subset** |

**All seven agree, and six are exact.** So the plan's prediction is refuted a second time: extending the
pin exposes **no** drift, and the seven new rows are guards. **Note also that `network` has two producer
sites, not one** — `_fleet_layers` returns four keys and its **caller** adds `capture` and
`fact_holdings` — so a forward pin must name both.

### 3.6 The measurement scripts are themselves an audited surface

The E3 census was wrong on its first run and reported **0** guarded sites. Cause: the guard test was
written `par.op is ast.Or`, comparing an **instance** to a **class**, so it was never true — every
guarded site was counted as unguarded, including `domain_id`, whose `or "unknown"` is visible in the
line the census printed beside it. Corrected to `isinstance(par.op, ast.Or)`: **1** guarded, **11** not.

It is recorded here because it is this document's subject arriving at the instrument: a check is only
as wide as what it can see, and this one could see nothing. A reader who trusts a number must be able
to see the thing that produced it.

**E5's census then failed twice more before it was right.** Attempt one matched SKILL block keys to
TypedDict names *without plural tolerance*, so `universal_facts` could never equal `UniversalFact`,
`group_links` could never equal `GroupLink`, and `fact_holdings` could never equal `FactHolding`. It
buried the mismatches in an "unmatched" bucket and raised nothing. Attempt two fixed the matching but
took the TypedDict's name from the AST node's `.value.id` — which is `"ms"` — instead of `.attr`, so
all 34 rows resolved to one name: it reported `distinct TypedDicts: 1` and a gap set of **26**,
including shapes the loop demonstrably covers (*`scope`*, *`rigor`*). Attempt three, which reads
`.attr`, produced §3.5.

**Both attempted figures were re-run for this revision, and the results are not symmetric.** Attempt
two's **`26` reproduces exactly**, along with `distinct TypedDicts: 1`. Attempt one's figure **does not
reproduce** — and this revision will not print it as though it did. Its script was overwritten by
attempt two and survives nowhere, so its number is **testimony-only**, not re-derivable; a faithful
reconstruction of its stated method yields **21** gaps over 21 unmatched, not the figure recorded.

That asymmetry is the point, and it is `number-provenance-tiers` stated as a result: of the three
census attempts, exactly the two whose scripts survive can be re-derived, and the one whose script is
gone cannot. **A figure whose instrument has been overwritten is not a measurement, it is a memory** —
so §3.6 records the failure modes, which are what the reader needs, and drops the unreproducible number
rather than dignifying it with a citation.

Three failures, one shape. Attempt one is the E3 bug in a different costume — `par.op is ast.Or`
compares an instance to a class, and a normalized string that cannot equal its counterpart compares
nothing at all; both **silently match nothing** and both return a confident, wrong number. Attempt two
is a third variant: reading the wrong *attribute* of a node that does exist. And §1.3's census, re-run
for this revision, is a **fourth**: a pattern that tests whether the `_clean` argument *is* a `BoolOp`
cannot see the two sites where the `or` is nested inside a `str()` — so the idiom's site count was
reported as seven when it is nine.

So this section is not a confession but a rule with four independent witnesses behind it: **a
measurement returning a surprising number must be re-derived — and so must one returning a plausible
number.** The plan's `30` for the loop's distinct count was re-derived here and is wrong; its `7` for
the gap set was re-derived and is right; the only way to tell them apart was to run the census a
third time.

**The fourth failure was not in a script at all — it was in the prose written beside a correct one.**
E3's census has been right since its first corrected run: 12 sites of the pattern it names, 1 guarded,
11 unguarded, and §3.3 still reports exactly that. But the sentence introducing it said the correct
idiom was already in the file *"twice"*. It is there **nine** times, in four forms — and the census
never claimed otherwise, because it was measuring a different thing: the sites whose default is a
*non-empty string*. The number held; the gloss on it did not.

That is `audit-the-diffs-prose` arriving inside the document that exists to record it: a verified
figure and the sentence describing it are two separate claims, and only the first had been measured.
The corrective was to stop summarising and **classify** — which is how the file's fourth and fifth
`_clean` forms (nine `x.get(k, "")` sites and two fallback chains) got written down at all. They were
invisible only because the prose had already decided there were twelve.

And the correction itself was wrong twice. The first redraft said *six* `get`-sourced `or`-form sites,
from a count of six `_clean(... or ...)` calls without splitting them by source; splitting them shows
five read a `.get` and the sixth reads a bare variable. The second redraft said *seven sites, two
forms* — which was still short by two, because the census that produced it could not see the `str()`
nesting (§1.3). **Thirty `.get`-shaped calls, seven `or`-wrapped, nine idiom sites in four positions,
47 call sites over 46 lines** — every one of those five figures was wrong at least once in this
document's history, and each was caught only by re-deriving from an enumeration rather than trusting a
count.

## 4. Pins

A pin is listed only if it **fails on pre-fix code**. Anything that cannot is labelled a **guard** and
says so, per `a-check-added-by-a-fix-may-not-flip`.

### 4.1 The pins

| # | Pin | Mechanism | Pre-fix | Post-fix |
| --- | --- | --- | --- | --- |
| E1-a | the sanctioned prune-then-justify state emits **one** verdict, not a remedy *and* an alarm | `render()` on `lever=prune, cand=1, pruned=0, reaches_budget=False, achieved_index > budget` → remedy present, `not acted on` absent, `✓` absent | **RED** | GREEN |
| E1-b | rewriting only `lever` does not change the verdict | two records identical but for `lever` → the **whole render**, with the header's `lever {LEVER}` normalized to `lever X` by regex, is byte-identical — on **both** a plain operand set and a mirror-bearing one | **RED** | GREEN |
| E1-c | the note reads `candidates_surfaced` | `cand=0` vs `cand=5` at one lever → **exact expected strings per arm**, not merely "they differ" | **RED** | GREEN |
| E1-d | `candidates_surfaced` **absent** ≠ `candidates_surfaced == 0` | both driven through `render()` → absent emits `candidates surfaced: not recorded` **and not** `0 candidate(s) surfaced`, plus the `no candidate count recorded` verdict; the `== 0` arm emits the reverse | **RED** | GREEN |
| E2-a | `n_blocked > 0` with zero rows drawn → the counts-only breakdown, never a phantom tail | `render()` on the **two-part** fixture (§2.2) → exact breakdown string present, `+30 more blocked` absent | **RED** | GREEN |
| E2-b | `0 fleet-candidates` is suppressed when `n_blocked > 0` | same record → the cold-state line absent | **RED** | GREEN |
| E3-a | an empty-but-present `session` renders its fallback | `render()` on `session: ""` → `session ?` | **RED** | GREEN |
| E3-b | **every** `_clean(x.get(k, D))` site is guarded | AST census → **population == 12** *and* **0 unguarded** | **RED** (11) | GREEN |
| E3-c | an empty-but-present marker `commit` renders its fallback | `render()` on a marker with `commit: ""` → not a hole | **RED** | GREEN |
| E3-d | a node name longer than its 18-column field is still **truncated** | `render()` on a 28-column node name → the name is absent whole, its 18-column prefix present | **GREEN both** — red on the **intermediate** revision only | GREEN |
| E4-a | nothing undeclared is emitted | `set(identity_snapshot(ctx)) <= set(Identity.__annotations__)`, over a temp-`HOME` ctx | **RED** | GREEN |
| E4-b | nothing declared is phantom | `set(Audit.__annotations__) <= set(audit_diff({}, {}))` | **RED** | GREEN |

**E3-d is a regression guard this cycle's own sweep earned, and it is the exception the "Pre-fix"
column exists to make visible.** The first cut of the E3 repair appended `or "?"` to the **whole**
expression at the node row:

```
nm = _clean(n.get("node", "?")) or "?"[:18]        # the slice now binds to the LITERAL "?"
```

so `[:18]` stopped truncating the cleaned value and became a no-op on a one-character string. A
28-column node name then rendered whole, past a `namew` clamped to 18 eleven lines above, shearing
the table. **The first draft of this paragraph said the row's "padding collapsed to `0`", and a
probe falsified it** — `pad` is `max(0, namew - disp_w(nm))`, which cannot go negative, so `pad` is
`0` on the *fixed* tree too (it is `0` for any name that fills its column exactly). The correct
statement is the more interesting one: the clamp is **silent at its boundary**, so an over-long name
gets the same `pad` as one that fits and simply **overruns** — the row ends up exactly its excess
wider than the column `namew` sized. Measured: the pre-`always` segment is **26 columns** with the
name truncated to 18 and **36** with it whole, a delta of exactly the 10 columns the name exceeded
the clamp by. Both the shipped comment and this paragraph carried the false version; the correction
is in both, and it is the one edit in this cycle whose whole content is prose (proved
comment-only by AST equality, so no measured count moves). Measured
on the intermediate revision: `a-very-long-node-n` → `a-very-long-node-name-indeed`. The fix is to
move the fallback **inside** the slice, `(_clean(...) or "?")[:18]`, which is what the pre-fix code
did in the only way it could (it had no fallback). **Red on the intermediate revision, green on both
the pre-fix and the fixed tree** — so it is a guard by `a-check-added-by-a-fix-may-not-flip`, labelled
as one, and the label says which revision it is red on rather than implying pre-fix. It is aimed at
the render's **output**, not at the source form, and that aim is load-bearing: re-aimed at the source
it would red on the same bug for the wrong reason, since the E3-b census reads exactly that form and
**passed** on the broken revision. Which is the census's second stated limit: it can ask whether an
`or` wraps the call, and it cannot see that a *trailing operator* on the expression was captured by
the repair.

**Eleven pins, one guard, and the guard is listed in the same table on purpose.** E1-a/b/c/d and
E2-a/b, E3-a/c are behavioural (they drive the real renderer); E3-b and
E4-a/b are structural (they census the real producer). E3-a and E3-c are the behavioural witnesses for
the two repairs E3-b and its sibling census perform — the pairing is deliberate, because a count says
*how many* moved and a probe says *which*. The "Pre-fix" column is what keeps E3-d honest: it is the
one row that does not read **RED**, and naming that in the row itself is cheaper than a footnote
somebody skips.

**Three of these were false pins as first drafted, and the corrections are load-bearing.**

- **E1-c needed its extraction named.** Comparing the **whole remediation block** it is **GREEN
  pre-fix** (the `↓ 0 …` vs `↓ 5 …` line already differs, so "notes differ" is satisfied). Restricted
  to the **note string** it is RED at every lever. Asserting **exact strings per arm** is what makes it
  a pin — and it closes a second hole, since an implementation that **swaps** the two verdicts also
  makes "they differ" true.
- **E1-b needed its set defined.** `pruned=0` gives 7 differing lever pairs but **3 already equal**
  (`gc` vs absent, `gc` vs an unmapped label); `pruned=2` gives **all 10 pairs equal** → **GREEN
  pre-fix**, so a `pruned>0` fixture is not a pin. Under a whole-block reading it can **never** go
  GREEN, because §2.1 keeps `lever` in the header. A pin that can never pass is as broken as one that
  can never fail.
- **E1-b and E1-c share one fixture**, and it carries a constraint that must be written down:
  `pruned=0`, `reaches_budget` **absent or `True`**, lever pair `{prune, justify}`, and
  **`achieved_index` held ABOVE `budget_tokens`**. The last is not decoration: at `:887`
  `resolved_by_lean = (not pruned) and (0 < ai <= budget_tok)`, so an under-budget `achieved_index`
  takes the resolved branch and emits **no note at all**, killing **both** pins pre-fix at once.
  Both were measured RED pre-fix and GREEN post-fix on that single fixture.

**E4-a was not *false* as drafted — it was not *hermetic*, which is the same defect one level down.**
`resolve_store` falls back to `os.environ` when given no `environ` kwarg, so the drafted pin resolved
the **maintainer's real** config root and let `identity_snapshot` read a real `control.sqlite` for its
`conflicts` sub-count. Every one of the suite's other `resolve_store` / `_enroll_personal` call sites
sets `HOME` to a temp dir **first**; this was the only one that did not. The verdict was never at risk
— that key is declared, and present-or-absent both satisfy `<=` — and that is precisely why it would
have shipped: a pin whose *inputs* depend on the machine it runs on is a pin that can only be trusted
on the machine it ran on, and the suite's own header promises hermeticity. Corrected by setting `HOME`
inside the `TemporaryDirectory` and restoring it in a `finally`.

**E1-b is *one* pin with *two* operand sets, and the second was added during implementation.** The
drafted pin drove the `{prune, justify}` pair on a record whose `mirror_share` is **absent**, so the
mirror row never renders and the pre-fix lookup's `gc` entry is **unreachable** — the pin tested the
`prune`/`justify` leaves and left the third arm of the very 3-way lookup it exists to kill untested
(`a-pins-coverage-is-the-values-and-path-it-samples`: the value a fix moves *to* is the one most
likely to be left unpinned). A `mirror_share: 0.9` variant is therefore a **second conjunct inside
E1-b's check**, not a second pin — it shares the pin's assertion (whole-render equality under a lever
relabel) and differs only in which branch is walked, which is what a conjunct is for. The same check
carries a **non-vacuity guard** (`"REMEDIATION" in _e_b1`, `"mirror-dominated" in _e_b3`): two *empty*
panels also compare equal, and comparing nothing is not the property being asserted. The mirror
variant deliberately does **not** carry the can't-reach remedy (its `reaches_budget` is absent), so it
and E1-a sample different branches rather than restating one.

### 4.2 Guards, and the one existing check this cycle moves

**E5's seven rows are guards, not pins** — pre-fix they do not exist, so they cannot fail on pre-fix
code (§2.5). **RC-89's repair is a guard too.** Its fixture gains `n_blocked`, which changes its
verdict in neither tree; what it removes is a *tautology* — with no `n_blocked` key, `_n_blocked` fell
back to `len(_blocked)` and shared a source with `_shown_b`, so the check was green by construction on
the only case that can fail. Post-repair it exercises two independent operands, so a future break of
the cap reds it.

**The v0.1.35 "still over budget" arm is a pin that encodes the E1 defect**, and it is the one
existing check this cycle deliberately turns from green to red. It builds
`lever=prune, candidates_surfaced=1, pruned=0, reaches_budget=False` — precisely the sanctioned
prune-then-justify state — and asserts `"not acted on" in render(...)`. The fix makes that assertion
false by design, so the check is **rewritten, not deleted**: post-fix it asserts the remedy line
present and the ⚠ absent, which is E1-a. Its sibling — the rebuild-lean arm asserting
`"not acted on" not in ...` for `reaches_budget=True` — is unaffected, because the resolved case still
takes the `resolved_by_lean` branch, so the suite still distinguishes resolved from unresolved.

This is the case the repo's own rule names: a failure whose output matches the **old** literal means
the pin encoded the defect, and the repair is to fix the pin. It is recorded here rather than
discovered in CI.

**A SECOND enforcement site exists, and this cycle checked it.** `plugins/dream-beta-tester/scripts/
beta_checks.py` (`CHK-REM-RESOLVED`) independently subprocesses `render_dashboard.py` and asserts
`"not acted on" not in o2`, with a fixture at `achieved_index=900` against budget 1200. That arm stays
**PASS** post-fix — the remedy line is the thing being added there, not the ⚠ — so nothing breaks. By
`weakest-enforcement-site-wins` an invariant is only as strong as its weakest site, and this one was
**not in any revision of §4 or §5**; it is recorded so the next reader does not discover it in CI.
Relatedly, `tests/simulate_accumulation.py` asserts `tri["lever"] ∈ {prune, gc, justify}` — the
simulation keeps proving the routing *exists* while the renderer stops *surfacing* it. That is
intended, and it is the reason E1 needs `mirror_share` persisted rather than `lever` deleted.

### 4.3 Mutation verification

Measured on the **uncommitted cycle tree** for the green control and on trees built with
`git archive 1d97f54 | tar -x` (never `git worktree add` — a linked worktree resolves the *main*
project's identity) for the mutants. **One process per tree**: `sys.modules` caches the first import,
so two trees compared in one process compare #1 against itself. Every number below belongs to the
**triple** (restored code, fixture, harness) and is not carried across an edit. This section was
re-measured **three** times because the triple moved three times — the harness was renamed mid-cycle
(`_e_rec` → `_e34_rec`, see the collision note); the E3-d fix landed in the renderer; and E4-a's
fixture gained a `HOME` override (a harness fix, §4.1). So the counts are stated *with* the
revision rather than as properties of "the pins".

**The trees are inventoried by `diff` before every measurement, and that is not ceremony.**
`prefixE` = renderer HEAD, producer HEAD · `mutA` = renderer HEAD, producer current · `mutB` =
renderer current, producer current minus the two keys · `LIVE` = both current. Inventories are
recorded here because a tree named `mutB` stopped being `mutB` between its build and its measurement,
and the resulting number was perfectly plausible — see the snapshot finding below.

| Tree | Scripts | Passed | Failed | Reds |
| --- | --- | --- | --- | --- |
| **`LIVE` — green control** | both current | **2008** | **0** | — |
| **`mutA` — renderer reverted** | `render_dashboard.py` = HEAD | 1998 | **10** | E1-a · E1-b · E1-c · E1-d · E2-a · E2-b · E3-a · E3-b · E3-c · the rewritten v0.1.35 arm |
| **`mutB` — E4 producer drift re-injected** | `memory_status.py` minus the two producer keys | 2005 | **3** | E4-a · E4-b · the pre-existing `SKILL↔TypedDict identity` row |
| **`prefixE` — both reverted** | both = HEAD | 1994 | **14** | `mutA` ∪ `mutB`, plus the `SKILL↔TypedDict remediation` row (`mirror_share`) |

**Every count above was predicted before it was measured, and the predictions are what found both of
this pass's measurement errors.** On the first pass `mutB` was predicted at **3** and measured **4**;
the extra red was the stale tree (below), not a property. The table holds the second pass, where all
four matched. A prediction that matches is weak evidence on its own — the property and the tree can
both be wrong in the same direction — so it is the **miss** that carries the information.

**All eleven pins red, and each mutant reds only its own half.** `mutA` leaves E4-a/E4-b green;
`mutB` leaves every render pin green. That isolation is the measurement's point — a pin that reds
under both mutants would be evidence that it is testing the *build*, not the property.

**The seven E5 rows are GREEN in all four trees**, which is the measured confirmation of §2.5's
"guards, not pins" claim rather than a restatement of it: they do not exist pre-fix, and pre-fix the
seven shapes were in perfect key agreement, so there is nothing for them to catch in the old tree.
What they buy is that the next drift in any of the seven reds the suite instead of landing in the
blind spot the old comment asserted could not exist.

**E3-d is green in all four trees too — and unlike the E5 rows, that is a *different* claim.** The
seven have no red anywhere in this cycle; E3-d has one, on the intermediate revision, which is why
its row in §4.1 does not read **RED** and why its label names that revision. Green here is not
"nothing to catch" — the guard's whole reason to exist is that the defect it catches *did* occur in
this cycle's own work, was caught by a human reading a diff, and would not have been caught by any
check in the suite as it then stood.

**The measurement tooling then failed silently in exactly the way this cycle studies, and it is the
second such failure in one pass.** The red lists were first extracted with `grep '^ ✗'` — **one**
leading space — while the suite indents a failure line by **two**. `grep` matched nothing and printed
nothing, and in a shell log an empty list is indistinguishable from *"this tree has no reds"*. It was
caught only because the **count and the list disagreed**: the same tree printed `14 failed` directly
above an empty list. Corrected to `'^  ✗'`, and every list in this section was re-extracted with it.

The rule that catches both this and the stale tree is the same one, and it is not "read carefully":
**predict the count before measuring it.** A prediction that *matches* is weak evidence (the property
and the tree could both be wrong in the same direction); a prediction that **misses** is the signal,
and it is what found the stale tree. A red list with no count attached is unverified, and a count with
no predicted value is unfalsifiable — so both are recorded here together.

**A mutant tree is a snapshot, and the third one went stale — in the direction that hides.** Between
building the trees and measuring them, the E3-d fix landed in `render_dashboard.py`. `mutB` holds the
**current** renderer by construction, so it kept the pre-fix *intermediate* one and reported a
**fourth** red, E3-d, where the pin set predicts three. The red was genuine; the tree was not `mutB`
any more. What makes this worth a paragraph is the failure's shape: **a stale overlay that carries an
old bug produces an extra red, and an extra red reads as a more sensitive pin — never as a wrong
tree**. The drift is invisible in precisely the direction this cycle is about, and it was caught only
because the count was predicted before it was measured and then did not match. Rebuilt from the
current files and inventoried by `diff`, `mutB` reds exactly the predicted three. Two general rules
fall out: a mutant tree must be **rebuilt whenever any member of the triple moves**, and the
inventory — not the name — is what identifies the mutant.

**Mutant B is not "the file restored", and that is a finding, not a shortcut.** Reverting
`memory_status.py` alone produces an incoherent tree: the fixed renderer reads `ms.AUDIT_WINDOW` for
the panel's window line (`render_dashboard.py`, the only line spelling `phase0..phase5` outside its
own module), and the pre-fix `memory_status.py` defines no such name — so an `--persist` subprocess
dies, a later era's fixture never gets its log file, and the suite **ERRORs out of the run entirely**
before reaching §4.1's pins. B was therefore built *forward*, by re-injecting exactly the two producer
keys on the current file, which is the drift the pin names. The general point: **a revert recipe that
assumes the two scripts are independently restorable is itself an unchecked claim** (E4 introduced a
new cross-module read — the class is old, `ms._REGISTRAR_BLOCKED_CAP` and `ms._MIRROR_DOMINATED` are
the same shape — but which symbols may be restored independently is revision-bound).

**Two things the counts do not mean.** `prefixE`'s red count is not "the number of pins": two of its
rows are pre-existing `SKILL↔TypedDict` rows that red because that tree reverts the *producer* while
the declaration and SKILL.md stay current — a half-state that cannot ship, and exactly why `mutB` is
reported separately rather than folded into it. And the 19-check delta in the suite's D6 total is 19
`check()` calls, not 19 pins: **11** pins, **7** guards, **1** regression guard.

**A collision the harness rename surfaced (guard against the next one).** The drafted helper was
`_e_rec`; the suite already binds that name at *module* scope from a `with _Env73() as _e_rec:` in the
v0.2.2 era, and `mypy`'s `no-redef` caught it. Hoisting the new helper **above** that block would not
have been a rename — it would have **changed the `with` block's meaning**, silently rebinding a live
context manager. The comment block above cannot warn about this, because the leaked name comes from a
`with`, not a `def`; the only reason it was a rename instead of a subtle behavioural edit is that the
contract check reads module-level scope. Helper names in this suite are era-suffixed for that reason.

## 5. Risks and open items

- **R1 — E1 REDs a currently-green check, deliberately.** The v0.1.35 "still over budget" arm asserts
  the self-contradiction. The rewrite is part of the fix (§4.2) and the reason is stated here so the
  change cannot be mistaken for weakening a pin. Residual risk: low — the sibling arm proves the suite
  still separates the resolved case from the unresolved one.
- **R2 — E1 changes TWO user-visible strings, not three.** *"mirror-dominated"* and
  *"justified — nothing safely prunable"* are replaced by data-derived text. **`"gate fired but not
  acted on"` is unchanged** — §2.1 row 4 keeps it byte-identical; only its *reachability* narrows
  (rows 1–3 now take precedence). Mitigation: the CHANGELOG entry names the **two** replacement
  wordings. *(Revision 3 said three and would have shipped a wrong CHANGELOG line.)* **On the
  survivability axis:** `lever` is **not** printed by the durable HTML archive at all — measured,
  `grep -c lever dashboard.template.html dashboard.sections.js` → **0 / 0**. The ASCII section header
  is the only place in either renderer that shows it, and the standing-justified header shows none. So
  the routing distinction survives **only in the terminal consult**; the archive never carried it. That
  is the honest statement of what is lost, and it is narrower than "readers lose the gc/prune/justify
  distinction" — the archive's readers never had it.
- **R3 — E4's edits move the committed preview, visibly.** Not merely bytes: the preview's
  **Observation window** row changes from the fixture's invented `phase 0 → phase 5` to the producer's
  real span (the first time that row has ever shown a true value), and its identity disclosure gains a
  `domain lifecycle` field. `docs_links.py::check_preview` requires a deliberate regeneration in the
  same PR, and the browser suite must be re-run against the new bytes. *(Revision 3's "nothing renders
  either key" was false — §1.4, §3.4.)*
- **R4 — the stop rule.** **Retired by measurement.** The cap was ~8 gap shapes; the measured set is 7
  with a red count of 0, so no third cycle is staged and the remainder is not deferred. (The cap itself
  is a maintainer judgement from the plan, not a constant in the tree.)
- **R5 — E3 changes rendered output on real records.** Output-neutral on the fixture's **ASCII** render
  (measured: 598 `_clean` calls, 0 empty strings) but **not** on a live record carrying `session: ""` —
  which is the point. Any real store whose record has an empty-but-present field will render differently
  next pass.
- **R6 — the forward direction stays mostly unpinned.** After E5 the loop proves SKILL↔TypedDict for
  every enumerable shape at depth ≤ 2, but producer↔declaration is pinned for only the two shapes E4
  touches — **41 of 43 remain unpinned in that direction**, and that is exactly where E4's two drifts
  lived. Recorded as the honest boundary; not closed by this cycle.
- **R7 — E1's note is derived from four fields, all optional, and the arm most likely to be missed is
  `absent`.** §2.1 gives `candidates_surfaced == 0` and `absent` separate rows precisely so the fix does
  not reintroduce E3, **and that witness now exists**: **E1-d** (§4.1) asserts the `↓` **line**, not only
  the note — because the note and the line are two surfaces and a pin that certifies one while the other
  still makes the forbidden claim is exactly the false-green this cycle keeps finding.
- **R8 — the E1 fix adds a key to the record, and refresh merges.** `mirror_share` reaches a record
  written **before** this cycle only if the refresh path merges it — measured, that path does
  (`rem.update(scratch["remediation"])`), so a refreshed legacy record gains the key. A record that is
  never refreshed keeps rendering through row 2's data predicate with `mirror_share` absent, which is
  the correct legacy behaviour: no mirror claim is made, and none is dropped.

## 6. Recorded, not scheduled

Carried forward from the plan, plus what this measurement pass added. None of it is in scope.

**From the plan:**

- **`achieved_recall` is a write-only ghost.** ⚠ **STALE — measured false in this revision.**
  `grep -n achieved_recall memory_status.py` → **five** occurrences, one of which is a **live gate**:
  `_DUTY_TRIO = ("pruned", "achieved_index", "achieved_recall")`. The plan's "exactly one occurrence"
  was true before v0.4.33 and was not re-derived after Cycle D shipped. The *reader* question stands —
  no renderer reads the field — but the "ghost from both directions" pairing with E4(B) does not, and
  the note must say so rather than be carried forward as written.
- **`entries[].action` vs its row's own `reason`.** No sound biconditional exists against `audit`
  (different units, different axes), but the row's `reason` ("no new body fact") contradicted its own
  `action` (`"added"`) — a model-phrase-vs-model-enum contradiction that never touches `audit`.
- **The v0.4.13 false universal**, the two-site prose imprecision in `SECURITY.md` / `release.yml`,
  the driver's unattributed persist `rc=4`, and **1.0 HOLD**.

**Added by this pass:**

- **The archive DISPLAYS `domain_lifecycle`, and revision 3 said the opposite.** Corrected in §1.4/§3.4:
  `capturedTree` renders it generically, so this is **not** an archive-exposure gap and no display needs
  adding. *(Revision 3 recorded it as "embeds and displays nothing" — a grep for the key name cannot see
  `Object.keys`.)*
- **The `class Audit` "only uncommented key" forensic is false** — four keys are bare (`memory`,
  `claude_md`, `operations`, `window`). Recorded because the *forensic* was offered as a reason the
  drift is invisible; the real reason is the missing producer↔declaration edge, which R6 covers.
- **The forward direction is unpinned for 41 of 43 shapes** (R6), and §3.5 now measures the seven it
  *is* tractable for — all seven clean, six exactly. Both of E4's drifts were reachable *only* because
  nothing checked that edge; nothing now prevents a third.
- **Two pushed commit messages carry withdrawn figures** — `5cd91ff` (the withdrawn `195`) and
  `c48c762` (the withdrawn `b8b43a5ed1f006f7`, corrected forward by `e26d4c5` and by the Revision 9
  amend). Pushed history, deliberately not rewritten.
- **A `{required: False}` remediation block with `standing_justified` absent renders no REMEDIATION
  section at all** — the branch keys on `standing_justified`, not on `required`. Hit incidentally while
  verifying that §2.1's new first row cannot misfire on the standing-justified seed shape (it cannot:
  that shape takes an earlier branch, and its 24-of-100 prevalence means a mis-fire there would have
  been widespread). Not a parity defect; recorded.
- **E4's own fix made a `main()` key inert, in the same expression that emits it.** The mutation-log row
  is `json.dumps({"window": AUDIT_WINDOW, "commit": …, "timestamp": …, **diff})`. Pre-fix that literal
  `"window"` was **load-bearing** — `audit_diff` returned five keys and none of them was `window`. Post-fix
  `diff` carries it, and `**diff` comes **last**, so the literal's value is overwritten and can no longer
  be observed. Harmless today (both sides are the same constant, which is the point of the comment beside
  it), but it is a key whose value nothing can see — so an edit to *that* spelling would silently do
  nothing while looking authoritative. Recorded rather than fixed: the edit would be behaviour-identical
  and cost a full re-measure mid-freeze. The removal is one word, whenever a cycle is not in flight.
- **The seven E5 rows inherit a v0.1.12 provenance tag that is not theirs.** They joined the existing
  nested-shape loop, so their reds print
  `… == NetworkCapture (v0.1.12 full nested pin)` — a label that dates a row added in **v0.4.34**. The
  label is not read by anything (verified: no `grep` hits outside the loop), the shape and TypedDict it
  names are unambiguous, and the comment above the loop says "all seven now added below". So this is a
  provenance tag read as a *family* tag, not a coverage claim — which is why it is recorded rather
  than fixed: it is the same species as this cycle's thesis, one size smaller, and changing a string
  shared by 41 labels during a measurement freeze costs a full re-measure for no gate value. Left for a
  cycle that is not mid-flight.

## Amend ledger

**Revision 1** — first draft, written after the measurement pass and before implementation. E1/E2/E3
measured; E4/E5 marked pending.

**Revision 2** — E4 and E5 measured; the four pending placeholders replaced, §4/§5/§6 written. Four
findings changed the design rather than filling a blank:

- **E1 REDs an existing green check.** `smoke.py`'s v0.1.35 "still over budget" arm builds the very
  state the fix is about and asserts the self-contradiction. The pin encoded the defect, so the check
  is rewritten as part of the fix (§2.1, §4.2).
- **E1's own design nearly reintroduced E3.** The first §2.1 table resolved `candidates_surfaced`
  *absent* and `== 0` to one verdict — a false "0 candidates surfaced" for a record that never carried
  the field. Found by writing R7, fixed in the table, and the missing witness is named as `E1-d` rather
  than left silent.
- **E4's fixture edit moves the committed preview** even though neither key is rendered, because the
  preview embeds the record's JSON — measured, not assumed (R3).
- **E5's predicted drifts do not exist** — red count 0 of 7 — so E5 is a coverage repair, its seven
  rows are guards rather than pins, and the plan's "same class as E4" prediction is falsified here
  rather than in review.

The plan's `domain_lifecycle` rationale was also corrected (the doctor surfaces do not read
`identity_snapshot`'s output), and its `30` for the loop's distinct-TypedDict count re-measured to
**32**. §3.6 was extended: E5's census was wrong **twice** before it was right, both times silently.

**Revision 3** — self-audit of this document's own prose, prompted by the plan's citation of an idiom
the earlier draft had summarised rather than classified. §1.3's *"the corrected idiom is already in
the file twice"* is wrong: it is there at **seven** sites in two forms. The census figure was correct
throughout (12 / 1 / 11, unchanged), and the failure was in the sentence beside it — so §1.3 now
carries the full **four-form** table (11 defect sites · 7 already-correct · 9 `x.get(k, "")` sites ·
2 fallback chains) with an explicit statement of why the last two classes are **not** repaired here.
That classification found something the summary had hidden: nine sites where absent and empty both
render blank, so `or D` is not the repair and applying it blindly would invent placeholders. §3.6
records the failure mode — a verified number and the sentence describing it are two claims, and only
one had been measured.

**Revision 4** — **adversarial review to zero, then re-derivation of every figure.** Five reviewers
reported against revision 3 (`c82c3c40…`, 655 lines); all findings were reproduced before adoption, and
two of them overturned a *premise* rather than a value.

*Design changes:*

- **E1 reaches the producer.** The record carries no operand for the mirror-vs-prune distinction —
  `lever` is a label and `mirror_share` was computed and dropped. §2.1 now persists it, on the decisive
  ground that `network.totals` is a **fleet** aggregate against a **store-local** threshold. §2.4's
  table grows to three rows and E1 is no longer renderer-local.
- **E4(B) reversed.** Revision 3's "no consumer reads `audit["window"]`" came from grepping the
  *quoted* key; `dashboard.sections.js` reads it as a **property access**, browser-confirmed to render
  "Not captured" on every real record. The **producer** is the incomplete side, not the declaration.
- **E4's rule restated.** (A)'s "no reader" premise is also false — the archive's generic
  `capturedTree` renders `domain_lifecycle`. Both arms reach revision 3's actions, but from premises
  that do not survive; the rule is now *the reader is the invariant*, which is what makes the direction
  derivable instead of lucky.
- **§2.1 gained a first row.** `render_dashboard` has a dedicated "pending Phase 5" branch the table
  never mapped, so its claim to list the outcome space *in the order it actually has* was false.
- **E2 loses an arm and gains a guard.** The HTML's `single-day` part is **provably unreachable**
  (§3.2, 0 of 1156 states) — so the port omits it, and the fixture that would have asserted it was
  impossible to satisfy.

*Number corrections, every one re-derived from an enumeration rather than a count:*

- §1.3: **30** `.get`-shaped (23 + 7), **17** without, **47 call sites over 46 lines**, and the idiom
  present at **nine** sites in **four** positions — not 29 / 23 + 6 / eighteen, and not seven / two.
  The discrepancy was an operand error: a line-based census under-counts `:251`, and a pattern testing
  "the argument *is* a `BoolOp`" cannot see the `or` nested inside `str()`.
- §3.6: attempt two's `26` **reproduces**; attempt one's figure **does not** and is now recorded as
  testimony-only rather than printed as a measurement.
- §1.4: `window` is **one of four** bare keys in `class Audit`, not the only one.
- §6: `achieved_recall` has **five** occurrences and one is a live gate — the plan's note was stale.
- §3.6: a **fourth** census failure recorded (the `str()` nesting), bringing the section's witnesses
  from three to four.

*Pins:* three of the nine were false as drafted — E1-c needed its extraction named (whole-block is
GREEN pre-fix), E1-b needed its set defined (a `pruned>0` fixture is pre-GREEN; a whole-block reading
can never pass), and both must share a fixture holding `achieved_index` **above** budget, or an
under-budget value silently kills both. **E1-d** now asserts the `↓` **line**, and **E3-c** covers the
second guard spelling; the table is ten.

*Process:* a second enforcement site (`beta_checks.py`'s `CHK-REM-RESOLVED`) is recorded in §4.2. And
the register's claim that one reviewer *"independently reproduced"* §1.3's table was **false** — it
reproduced the pattern, not the measurement. **Two reviewers agreeing is not two measurements when
they share the matcher**, which is `gate-coverage-is-its-match-set` one level up; that mis-credit is
what raised confidence in a wrong number.
