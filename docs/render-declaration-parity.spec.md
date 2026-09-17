# Render/declaration parity — design-of-record

**Status: revision 10 — a seventh pass: the code review adjudicated. One finding is a live code defect
and is FIXED here rather than recorded; the rest are prose, and every one is named in the ledger at the
end. `render_dashboard.py` moves for the first time since the third pass, so the whole mutation table
was re-derived rather than carried.** The fifth pass swept this
cycle's *pre-fix narratives* — every label claiming what a revision the tree no longer contains did —
executing each claim against `1d97f54`'s renderer rather than re-reading it. That pass then found,
with the lead's own fourth lens, that **the scope was the defect:** the selection matched with the
case-sensitive test `"Pre-fix" in label`, and the file spells the counterfactual both ways. Enumerated
structurally from the diff rather than matched, **eighteen** of this branch's twenty-one added labels
carry a claim about a non-HEAD revision, and the matcher reached **eight** — all three of the cycle's
GUARDs among the ten it never looked at. Executing all eighteen against the revision each names,
**seventeen hold and one is false** (E2-b); of the eight reached, three were false and five held.
The three: E1-c's (the fourth pass's finding 7, corrected earlier in the pass), E1-e's "seven of
the eight cells" (a count of a superseded eight-cell census, generalized to `Pre-fix` by a parenthesis
the pre-fix renderer never earned — measured, `1d97f54` leaves **0 of 12** green), and E3-c's `'→  @ '`
(`_ui.wrap` collapses the whitespace run, so the render was `'→ @'` and the two revisions differ only
by the `?`). The measured generation is bound to commit
**`7188c1a2cff1c51f59307ddb717cb54910a8783d`** (§4.3), the commit that froze the corrected triple,
because a document cannot bind itself to the commit that contains it.**
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

**Revision 5 turns the same lens on the fixes.** A second pass reviewed revision 4's *repairs*, and both
findings were the cycle's own subject arriving in the repair rather than in the defect (§2.6): **E1's
fix closed one cell of eight** (the scope as it stood then — the third pass grew the census to
twelve, §2.1), and **E2's fix carried the HTML's guard across when that guard answers a
different question**, leaving the false tail standing on a producer-reachable shape. Neither was visible
to the suite — it was **2008 / 0** on both revisions, because the pins sampled the values the fixes moved
*to* and never the ones they moved *away from*. So this revision **changes code, not only pins**: E1 gains
`_recorded` and a per-operand derivation, E2's guard condition changes, and two pins (**E1-e**, **E2-c**)
close the sampled sets. Because the harness moved, **every figure in §4.3's six-tree table was re-run**
— and the re-run caught a third thing: revision 4's `prefixE` count belonged to a **differently-built
tree** (§4.3).

**Revision 6 turns the lens on this document's accounting of itself, and finds no reopened defect —
which is the finding.** Four reviewers ran against the committed revision (its prose, its pins, the
**consumers** of the predicates it touches, and its logic). Every repair revision 5 made survived. What
did not survive was the **register**: a guard's printed label still carried a mechanism its own comment
three lines above had already falsified, a count and the list beneath it disagreed inside one sentence,
and a pin's own limit case was sampled by **nothing**. None of the three moved a check — the suite was
green on the revision carrying all of them — so all three are §3.6's class arriving for the third
**round in which this document's own register was caught in it**: after §1.3's "twice" gloss (revision
3) and the ledger's *ten* against twelve (revision 5) — **counting only rounds in which a COUNT in the
register was contradicted by the enumeration printed beside it.** That criterion is narrow on purpose,
because the broad one ("rounds where the register was the surface") does not exclude **revision 4**,
whose entry records two register-level catches of its own; under the broad reading revision 6 is the
**fourth**, not the third. *(Third-pass review, finding 4 — a REFUTATION, and the criterion is what
moved rather than the ordinal.)* The enumeration is stated because the ordinal is otherwise unreadable
— §3.6 numbers its own **witnesses** to four, and its fourth is a **revision-4** census, so "third"
and "fourth" are both correct here and neither is meaningful without its series. Revision **7** is the
**fourth** of the narrow series: §4.3's `memory_status.py` row counted *thirteen trees* at one hash
while the inventory printed in the same table holds **nine** and **four**. Now inside the register that
records it.
One code surface changes (a label, verified
**verdict-neutral** by comparing the red sets across revisions), §2.1's scope paragraph states an
invariant a reader would otherwise have to re-derive, and **one pin gains coverage** — E1-e's limit
case, the pre-pass seed its four operand rows route around by construction. **§4.3 now records
rev8**: the harness was edited mid-run again, so rev7 is a prediction and rev8 — a two-file swap on
rev7's preserved trees, with all ten mutant hashes asserted unchanged — is the measurement.

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
  needed"*. **18 of 324** states in the wider sweep do this (§3.1 states the sweep's axes, so the number
  is re-derivable). **0 of 12** rows in §3.1's own table can see it — that grid holds `achieved_index`
  **above** the budget on every row, which makes the `✓` branch unreachable throughout. The table's own
  **2 of 12** counts the *alarm* pair (a note beside the can't-reach remedy), one row-group over from
  this one; the two figures are not the same quantity and quoting either for the other was this
  document's fourth instance of its own defect.
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

Measured by AST census over **`1d97f54`**'s `render_dashboard.py` — the pre-fix parent, and the revision
**every anchor in this subsection resolves on**, because the E3 repair rewrote exactly these lines and
moved them. That binding is stated once here rather than per-table, because it is the thing a reader
re-deriving these numbers gets wrong first: `:650`, `:598`, `:631` and the rest name a file that no
longer contains them. The census: **12** sites of the form `_clean(x.get(<key>, <non-empty string>))`,
of which **1** already carries the correct idiom (`_clean(ident.get("domain_id", "unknown")) or
"unknown"`) and **11** do not. On the shipped tree the same census reads **12 / 0** — every site
guarded — and that post-fix pair is exactly what `tests/smoke.py`'s E3-b pin asserts, so the numbers
here and the pin's numbers describe **two revisions** rather than disagreeing. *(Fourth-pass review,
finding 8.)*

**The corrected idiom is not an invention — it is already in the same file, and it predates this
cycle, at nine sites in four syntactic positions.** Revision 3 said *seven sites, two forms*, which was
itself the failure mode this section describes: a census pattern narrower than its claim. Enumerated
exhaustively on `1d97f54`:

| Position | Form | Sites (on `1d97f54`), fallback `D` |
| --- | --- | --- |
| BoolOp inside `_clean` | `_clean(X.get(k) or D)` | **5** — `:650` `"?"` · `:721` `""` · `:722` `""` · `:1082` `""` · `:1120` `"?"` |
| BoolOp outside `_clean` | `_clean(X.get(k, D)) or D` | **1** — `:598` (the `domain_id` site), `"unknown"` |
| BoolOp nested in a `str()` | `_clean(str(X.get(k) or D))` | **2** — `:1038` `""`, `:1136` `""` |
| bare variable | `_clean(<var> or D)` | **1** — `:631`, no `.get` at all, `"?"` |

**Four of those nine instantiate the repair; five spell the same shape with `D = ""` and do not.**
`:598`, `:631`, `:650`, `:1120` carry a non-empty fallback, so `or` is what makes an empty string take
it — that is the cure. `:721`, `:722`, `:1038`, `:1082`, `:1136` carry `""`, so absent and empty both
render blank: behaviourally the deliberate-blank class the second table below already lists, reached
through a different spelling. The distinction is not pedantry — the sentence above cites the nine as
evidence that the idiom is **already in use**, and only four of them can serve as that evidence. *(The
five were measured on the fourth pass; the nine had been counted by shape, which is the same
narrow-pattern move this subsection is about.)* On the shipped tree the position splits **8 / 3**:
eight `or`-inside sites, of which `:657`, `:676` and `:1207` carry `"?"` and `:747`, `:748`, `:1125`,
`:1169`, `:1268` carry `""`.

The third position is the one every summary missed, **and it is invisible to an AST census that tests
"is the `_clean` argument a `BoolOp`"** — the argument there is a `Call`. That is the same narrow-pattern
failure as `par.op is ast.Or` (§3.6), arriving a third time **in §1.3's own narrow-*pattern* series** —
**enumerated here, because "a third time" is not derivable from a name** *(third-pass review, finding
5)*. Its members are the two patterns §3.6's "three failures, one shape" describes — **`par.op is
ast.Or`**, a pattern comparing an instance to a class, and **the wrong *attribute* of a node that does
exist** — together with the pattern below, **the `_clean` argument tested for being a `BoolOp` when it
is a `Call`**. All three **silently match nothing** and return a confident, wrong number. The series is
narrower than the census series §3.6 numbers to **four**, whose fourth member is this same §1.3 re-run
counted once in each — so the two ordinals are comparable only once each names its own.

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

The `"nothing safely prunable"` phrasing is dropped at **this** site rather than repaired: it asserts a
fact about the store (nothing *is* prunable) that no field carries. The replacement states what the
record actually says (`0 candidates surfaced`), which is the same discipline Cycle D applied when it
refused to let a clause infer presence from absence.

**Scope, because the phrase has a second home and "dropped" would be false of the tree without it.**
`memory_status.py`'s Phase-0 panel keeps those words in its own `lever`-keyed hint map
(`_remediation_section`), and the first draft of this paragraph read as though no copy survived.
Measured, that copy is **not a defect** — and the reason is a rule rather than a preference: **a surface
may key a claim on a label only when the label and the operands behind it are written by one expression
in one run.** `_remediation_section` is reached from exactly two call sites, both handing it
`ctx.get("remediation")`'s dict — one spelled inline (`memory_status.py:4593`), the other via a `rem`
bound one line above it (`:4787-4788`), so a reader who greps only the spelled form finds one site and
should not conclude the invariant covers half of it — the dict `remediation_triage` returned, whose
`lever`, `candidates` and unrounded `mirror_share` are
set from one expression, so a truthy `rem` always carries the operand and `lever == "prune"` cannot
outlive an empty candidate list. Under §2.4 that ends the question, the same way it ended it for
`_procedure_integrity_section`'s hardcoded subtitle.

`render_dashboard` is the opposite case by construction, and the population says so: it is **handed**
records, and over the archive **23 of 39 persisted remediation blocks carry `lever` and 0 carry
`mirror_share`** *(revision 7 corrected the denominator: it read `45`, a figure that reproduces under
no definition of the corpus, and the numerator's own corpus measures **39**. See §4.3's provenance
note.)*. The label without its operand is not an edge case there — it is every record that
exists. That is why the renderer makes no mirror claim on an absent operand, why `:3531`'s `isinstance`
guard is a belt to a brace rather than a live branch, and why the two surfaces are allowed to differ.
Writing the invariant down is what keeps the next reader from "aligning" the panel with the renderer, or
the renderer with the panel.

**(ii) The remedy line is gated on `not resolved_by_lean`.** The remedy (`:892`) and the resolved-by-lean
`✓` (`:894`) are separate `if`s, so for `achieved_index=900, reaches_budget=False` the panel emits a
sanction *and* a success. Fix: the remedy fires only when the lean path did **not** resolve. **Pinned by
E1-f, not by E1-a.** An earlier draft of this paragraph credited E1-a; measured, a mutant that reverts
this conjunct alone leaves E1-a **green** and reds E1-f and nothing else. E1-a holds `achieved_index`
*above* the budget, so the lean path never resolves there and the conjunct never binds — E1-f samples
the state where it does. The credit is worth correcting rather than quietly reassigning, because a pin
named for the wrong conjunct is a coverage claim that no reader re-checks.

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

**The census this fix's own first cut got wrong, because a fix that closes one cell reads as closed.**
The `↓` line composes **four** numeric operands — `candidates_surfaced`, `pruned`, `achieved_index`,
`projected_index` — and `_num` maps **absent** and **blank** to the same `0.0`, so each operand has
*two* not-carried forms that render as a measured zero. Four operands × two forms = **eight cells**
— the scope this repair was audited against, and **not** the scope that ships. The third pass SPLIT
the second of those forms: `blank` had counted `None` and `""` as one, and the shipped census walks
them as two, which is what grows four operands × two forms to × three = **twelve** cells. (`_e_missing`
is the loop's sentinel for "do not set the key at all" — a test MECHANISM, not a third form: an absent
key and an omitted one name the same state, and the eight-cell scope already counted it. This
paragraph said the third pass "added the key's **`omitted`** spelling as a third form", which is false
on its face — `omitted` ≡ `absent` — and is corrected in revision 11.) Counts
below are stated on the eight-cell scope that produced them and restated on the twelve where the two
differ.
The first cut of this repair closed **one**: it asked `"candidates_surfaced" not in rem` — inline, at
one site, for the **absent** form only — and left the other three operands reading `_num(… , 0)` and
the **blank** form falling straight through the membership test. The suite was green on both revisions
(2008/0 before the second pass, §4.3), which is the whole reason the gap survived a review round.
**E1-e** closes the other seven — **eleven of the twelve** the shipped census samples — and asserts
the **carried** spelling too; §2.6's general form — *a guard whose pattern is narrower than its
claim* — is what the census is for. Measured, the two revisions the census separates are not alike:
on `1d97f54` **all twelve** cells render a number the record never carried, and on `6368288` the
first cut leaves exactly **one** green (`candidates_surfaced` omitted).

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

- **no blocked row drawn (`_shown_b == 0`) and `n_blocked > 0`** → the counts-only breakdown,
  `N blocked — X generic-cli · Z single-node — counts-only by design…`.
- the `0 fleet-candidates — the honest cold state` line is **suppressed** whenever `n_blocked > 0`:
  it and the tail are two claims about one state, and they contradict.

**Three port details, each measured, each load-bearing.**

1. **Do NOT carry the JS's guard shape across — `!board` answers a different question.** `board` is
   non-empty when any card rendered, when the day-spread note fired, *or* when unjudged rows exist, so
   `!board` reads *"nothing at all was drawn"*. In the JS that is the right question, because its
   counts-only branch **assigns** `board` — the guard exists so the breakdown cannot clobber cards —
   and because the JS already states the blocked count in its own `reg-counts` header (`:147`). The
   ASCII branch **appends** and has no such header, so what it must ask is *"were the count's own rows
   drawn"* — `_shown_b == 0`. **The cycle's title is parity, and this is the one place where parity of
   the port would have been parity of the defect**: the first cut carried `!board` across as
   `len(_fleet) + _shown_b == 0` and left the false tail standing on exactly the state `sync_global`
   builds. A guard's condition has to name the claim it guards, not the shape of the port it came from.
   Disclosed as a deliberate divergence rather than smuggled as an equivalent.
2. **Carry both the clamp and the omission — but only the OMISSION is observable.** The JS's remainder is
   `Math.max(0, n_blocked − n_generic − n_day_spread)`, emitted only `if(bRest > 0)`. The port carries
   the **clamp** and the **omission**, and behind the omission the clamp is **unobservable**: at
   `{n_blocked:10, n_generic:30, candidates:[]}` the remainder is `-20` unclamped and `0` clamped, and
   **both fail `> 0`**, so the two render identically — byte for byte. The renderer's own site says so:
   `max(0, …)` is *"DEFENCE, not the mechanism … Measured — removing it moves no check"*. What *is*
   observable is the omission: an unomitted `bRest == 0` prints a `0 single-node` arm for a line whose
   only contract is to account for the total. So **§4.1's second fixture pins the emission test, not
   the `Math.max`** — a distinction this bullet originally inverted, and the inversion is this cycle's
   own class (a check whose stated subject is not what it tests) arriving in its design-of-record. What the port does **not** carry is the `n_day_spread`
   term — see bullet 3, whose subject turns out to be the arithmetic as well as the arm.
3. **OMIT the `single-day` arm, and say why here — and its ARITHMETIC goes with the arm.** The HTML
   cannot draw it — the arm is unreachable by construction (§3.2). Carrying it into the ASCII would
   give this renderer a line the other can never print, which is the opposite of parity. **The
   subtraction is a property of the arm, not of the remainder.** The JS can afford `− n_day_spread`
   only because `!board` makes that branch unreachable whenever the field is non-zero, so the term is a
   no-op in every state the JS can print. The ASCII guard is `_shown_b == 0`, which **is** reachable
   with a non-zero field — so the port dropped the guard that made the term dead while keeping the
   term. Measured: `{n_blocked: 30, n_generic: 10, n_day_spread: 20}` rendered `30 blocked — 10
   generic-cli`, ten rows short of its own total, with no third arm to account for them. Pinned by
   **E2-f**, whose `n_day_spread=0` arm is the non-vacuity half. **Do not "restore" it later without
   re-reading §3.2** — that instruction now covers the subtraction as well as the arm.

**F1 — the state the `!board`-shaped guard leaves standing, and it is producer-reachable.** `sync_global`
persists `_persist = _fleet_src + _spread_src[:_REGISTRAR_BLOCKED_CAP]` while counting
`block["n_blocked"] = sum(1 for c in candidates if c.get("disposition") != "fleet-candidate")` over the
**original** candidate list — so the count's denominator and the persisted display list are two
different sets. A window of one fleet-candidate plus twenty generic-cli rows therefore persists **one
row**, records `n_blocked: 20`, and persists **no blocked row at all** (§3.2 measures it by running
those three expressions verbatim). Under `!board` that state is invisible — a card *was* drawn, so
`board` is non-empty — the `elif` renders `+20 more blocked`, and there is no drawn row for the 20 to
be "more" than. `_shown_b == 0` fires the breakdown on exactly this shape. Pinned by **E2-c**, on the
fixture `{n_blocked: 20, n_generic: 20, n_fleet: 1, candidates:[one fleet row]}`.

**F1's prevalence is 0, and that is stated rather than omitted.** Measured over the 104-record archive:
35 records carry a `workflow_proposals` block, 28 of those count `n_blocked > 0`, **27** are the
empty-candidates form §1.2 describes — which the **first cut already fixed** — and **0** are F1. So
E2-c is not aimed at observed damage. It is aimed at a **condition that does not name its claim**,
which is this cycle's whole subject: `_rows_drawn == 0` asks *"is the candidate list empty"* while the
branch it guards asserts *"the count's own rows are not drawn"*, and the two come apart on a shape the
producer builds. A defect is not required to have already fired for its guard to be wrong; the
compensating requirement is that the fix be **argued from the code** (it is — above) and that its
prevalence be **reported** (it is — 0). Cycle D dropped a clause on a 0/99 measurement for a
*different* reason: that clause was **unsound** (its converse is false), not merely unobserved.

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
- `n_generic + n_day_spread > n_blocked` → the remainder **omitted** — this pins the emission test
  (`> 0`), **not** the `Math.max`: behind that test the clamped and unclamped values agree on every
  input (`-20` fails it exactly as `0` does), so no fixture can discriminate the clamp.

**That second bullet is a guard, and this is the only place it is said.** It cannot fail on pre-fix
code — pre-fix the line does not exist at all — so it is not a pin. What it catches is a *future* edit
that drops the `> 0` emission test while leaving the first fixture green. *(The clamp is not on this
list: removing it moves nothing, so it is guarded by no fixture and can be.)* §4.1's
row still reads **RED** because the *first* fixture is a genuine pin, so this guard half is invisible
in that table — unlike E3-d, whose whole check is a guard and therefore gets a row of its own with its
red named. Same species, bundled rather than split; disclosed here instead of left for a reader to
infer from a `-20 single-node` string that needs **both** the clamp and the emission test gone at
once — an edit this second fixture *would* catch, which is why the guard is stated rather than
assumed.

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
would conflate them. **They are hermetic by different means, and the earlier sentence "both land
inside smoke.py's existing `resolve_store` block" was true of neither.** E4-a opens its own
`TemporaryDirectory`, overrides `HOME` to it, and calls the real `resolve_store` on that path — so it
runs the constructor rather than a stand-in, and the `HOME` override is load-bearing rather than
decorative, because `resolve_store` falls back to `os.environ` when given no `environ` kwarg and would
otherwise read the maintainer's own config root. E4-b touches none of that: `audit_diff` is total on
`({}, {})` — it returns its five keys for empty snapshots — so that pin needs no fixture and no
environment at all. **Pin B's
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

### 2.6 The second-pass review, and the form its two findings share

A second adversarial pass ran against this document's **own revision-4 repairs** rather than against
the pre-fix code. It found two defects, both in the fixes:

- **E1's repair closed one cell of eight.** §2.1's first cut guarded `candidates_surfaced` for the
  **absent** form only, at one site, and left three other operands and the **blank** form reading
  `_num(…, 0)`. The census is four operands × two not-carried forms (§2.1); **one of eight** was
  closed. **E1-e** now pins all of them, plus the carried spelling — **twelve** cells at the shipped
  scope, because the third pass split that scope's single `blank` form into `None` and `""`.
- **E2's repair carried the HTML's guard across, and it guards a different claim.** The first cut
  keyed the counts-only breakdown on `len(_fleet) + _shown_b == 0` — the JS's `!board`, whose reason
  (an **assigning** branch, plus a `reg-counts` header that states the count) does not transfer to an
  **appending** branch with no header. The state it leaves standing is producer-reachable (§2.2 F1).
  The guard is now `_shown_b == 0`. **E2-c** pins both directions.

**One form, stated once.** Both are a **check whose pattern is narrower than its claim**: the
condition names something the author could *see* — a key's presence, the port's guard shape — while the
branch it guards asserts a proposition about the **data**. `"candidates_surfaced" not in rem` is a
membership test on one label; the claim is *"no operand was carried"*. `len(_fleet) + _shown_b == 0` is
a test of the candidate list's shape; the claim is *"the count's own rows are not drawn"*. In both
cases a `0`, or a member of a different set, satisfies the test while falsifying the claim.

**This extends §3.6's class from instruments to shipped guards.** §3.6 enumerates four census scripts
that silently matched the wrong thing (`par.op is ast.Or`; no plural tolerance; `.value.id` instead of
`.attr`; a test for `BoolOp` that cannot see an `or` nested in `str()`). Those were *measurement*
instruments. These two are **guards in the artifact**, which is worse: a census reports a number a
reader may check, while a guard **decides what the program prints**, and it does so on every run.

**Why a full review round passed over them: the pins did not sample the cells.** Two measurements,
taken together:

1. The suite read **2008 passed, 0 failed** on the revision carrying both defects — 2008 checks, none
   of them looking.
2. Under the **current** pins, the same renderer (`mutD`) reads **2008 passed, 2 failed**, and the two
   are **exactly** E1-e and E2-c (§4.3).

So of the 2008 checks that were green on the defective revision, **none** detects either defect: the
only two that do are the two added afterwards. That is not an inference from the first measurement —
it is the difference between the two, and it is why the second pass changed **code** rather than
reaching for a softer adjective. E1-d asserted **one** operand in **one** not-carried form; E2-a/E2-b's
fixtures carried **no fleet row**. This is `a-pins-coverage-is-the-values-and-path-it-samples` stated
as a measurement: the values a fix moves *away from* are the ones a pin must sample, and both first
cuts sampled only the values they moved *to*.

**What the second pass changed is the code, not the pin.** A narrower-than-its-claim guard is not
repaired by adding a check that fires on the old condition — that leaves the condition and pins the
symptom. So E1 gained `_recorded` and a per-operand derivation, and E2's guard condition changed.
**The consequence is a re-measurement obligation, and §4.3 discharges it**: the harness moved, so every
figure in the six-tree table was re-run, and the counts recorded for `prefixE` in revision 4 were shown
to belong to a **differently-built tree** (see §4.3's build note).

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
entries[])`. The unit is a **row** — all three of that row's cells carry the second line — not a cell;
the same quantity counted per cell is 72 of 324.

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

**The 324-state sweep, stated so it can be re-run.** The cross-product of `lever` ∈ {`gc`, `justify`,
`prune`} × `candidates_surfaced` ∈ {absent, 0, 5} × `pruned` ∈ {absent, 0, 2} × `reaches_budget` ∈
{absent, `False`, `True`} × `achieved_index` ∈ {absent, 0, 900, 1500} — 3·3·3·3·4 = **324**, at
`budget_tokens: 1200`, so 900 is under the budget and 1500 over. Measured on the pre-fix pair
(`1d97f54`, both scripts): **18** states emit the remedy beside the `✓`, and **72** emit two or more
verdict lines. On the fixed tree both are **0**. So the claim the repair earns is not "the 18 bad states
are gone" but the stronger *at most one verdict line per state, across all 324* — which is what
"one decision per state" has to mean if it means anything.

**And the sweep repeats the grid's error one dimension out.** `mirror_share` is not among the five axes
above, so "across all 324" is a claim about records that hold it **absent**. Nothing in the row exempts
it: `:981` emits the "mirror-dominated …" line from an `if` with no guard against any other branch, so
it co-renders with whatever the state already rendered. Most of that is *by design* and `:977` says so
in as many words — the mirror advisory is a claim about a different set than the local-prune verdict —
which is exactly why the repair here is a **scope**, not a count: a sweep that fixes a dimension while
reading as a statement about every record is the same error as the 12-cell grid eight lines up,
committed by the paragraph that diagnoses it. (The code review extended the cross-product along that
axis and found co-rendering where this sheet has none. Its figures are *its* measurement, on its own
definition of a verdict line, and are recorded as such rather than restated here: this revision's
reconstruction of that operand did not agree with the sheet's zero at an absent share either, and a
disagreement about a count is evidence about the count's definition.) The claim is scoped to what was
measured: **at most one verdict line per state, across all 324, at an absent `mirror_share`**.

The axes are named because the earlier revisions quoted these counts as **testimony**. No axis list
means no reader can re-run them, and a number that cannot be re-derived is not evidence — the same
discipline §4.3 applies to the mutation table, applied here to a sweep that had escaped it.

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

**The guard's two operands, measured against the producer.** The section above measures the *renderer*;
this measures whether the state it newly covers can be **built**. Running `sync_global`'s own three
expressions verbatim (§2.2 F1) over a 21-candidate window — one `fleet-candidate`, twenty
`blocked: generic-cli` — with `_REGISTRAR_BLOCKED_CAP = 8`:

```
PERSISTED rows        : 1 -> ['cmd-fleet']
n_blocked (record)    : 20
blocked rows PERSISTED: 0
```

One card drawn, twenty counted, zero blocked rows persisted — so `_shown_b == 0` while
`len(_fleet) + _shown_b == 1`. The first cut's guard, keyed on the latter, does not fire.

**And its prevalence, from the archive.** Deduped on `marker.(commit, timestamp)` over every
`~/.claude/projects/*/memory/.consolidation-log.jsonl` and every
`~/.claude/plugins/data/consolidate-memory/ops/*/.consolidation-log.jsonl`:

| Shape | Records |
| --- | --- |
| archived records, deduped | **104** |
| …carrying a `workflow_proposals` block | **35** |
| …with `n_blocked > 0` | **28** |
| …**empty** `candidates` **and** `n_blocked > 0` (§1.2's state, fixed by the first cut) | **27** |
| …**a fleet row persisted, zero blocked rows** (F1 — what E2-c adds) | **0** |

The single remaining record carries **8** drawn blocked rows under `n_blocked: 50` — the legitimate
tail case, and the real-world twin of E2-c's second fixture. **F1's 0 is reported, not hidden**: the
fix is argued from the persist rule, and the pin is a guard against a condition that names the wrong
set, so its value does not rest on prevalence. Quoting either figure later means re-deriving it —
the archive grows and neither number is carried across it.

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

  — is a display string whose provenance is **not** `audit["window"]`. Pre-fix it was a hardcoded
  literal that read nothing; post-fix (E4) it renders `ms.AUDIT_WINDOW`, so it reads the **constant**
  the producer also writes, not the record's key. That is the repair rather than a contradiction: the
  line states *this pass's* observation span, which is a property of the run, and the record's
  `audit.window` persists the same value so the **archive** can render it. One value, one home
  (`AUDIT_WINDOW`), two readers — the terminal panel takes it directly, the archive through the
  record. The pre-fix version could not say that, because the value had no home to share.

**The citation, corrected.** Revision 3 named *"the `.mutation-log.jsonl` row at `smoke.py:5972`, in
which the literal legitimately lives"*. Both halves are wrong: `smoke.py:5972` is
`_w79 = _jsonB.loads(_rows79[0])["window"]` over `plugin_data_dir()/"fleet-usage.jsonl"` — the
**fleet-usage ledger**, inside the v0.1.79 `--harvest` test (the same "harvest/history rows" the
sentence had already listed, so it was **counted twice**). And the literal `phase0..phase5` appears in
**no test file** — that part is right, and it stays right post-fix.

**But the enumeration was a pre-fix measurement, and the repair moved it.** Measured by grep on both
trees: pre-fix the literal was spelled in **three** files (`memory_status.py` — the log row;
`render_dashboard.py` — the display line; `SKILL.md` — the schema block), and the fixture carried a
*different* spelling, `"phase 0 → phase 5"`, which matched no producer either. Post-fix it is spelled
as **source** in **two** files: `memory_status.py`, as the single `AUDIT_WINDOW` definition, and
`SKILL.md`'s schema block. The other **four** readers — `audit_diff`'s return, the log row, the panel
line, and `tests/dashboard_fixture.py` — now spell the **constant**, so none of them can drift from it.
That is what one home buys, and a grep count stated without a revision cannot show it.

**Two scoping notes, because "spelled in two" is a count and a bare `grep -rl` returns five files.**
`docs/previews/nocturne/sample.json` and its twin `docs/previews/nocturne/index.html` also contain the literal, as **data** — they are a
committed *render* of the fixture record, so they carry the value the constant produced, which is what a
record is for; a preview is a reader's output, not a spelling site. The fifth is **this document**: the
paragraph you are reading spells the literal, so it is its own `grep` hit — the self-inclusion that also
makes an anchor quoted inside its own citation impossible to keep unique. And this paragraph read "the other
**three** readers" while listing four sites. The count and the list disagreed inside one sentence, which
is this cycle's failure mode in its smallest form, and it is recorded rather than quietly repaired
because the number is the part a reader skims.

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

So this section is not a confession but a rule with four independent witnesses behind it *(enumerated,
because two sentences below each call a different item "the fourth" — the four are **attempt one**,
**attempt two**, **attempt three**, and **§1.3's census re-run**, and all four are census failures; the
prose failure is a separate, fifth item and is not a census at all. Third-pass review, finding 5)*: **a
measurement returning a surprising number must be re-derived — and so must one returning a plausible
number.** The plan's `30` for the loop's distinct count was re-derived here and is wrong; its `7` for
the gap set was re-derived and is right; the only way to tell them apart was to run the census a
third time.

**The fifth item was not in a script at all — it was in the prose written beside a correct one.** *(It
is deliberately **not** numbered with the four above: they are all census failures, and this one was a
census that had been right since its first corrected run while the sentence beside it was wrong. The
rule the four witnesses establish covers it anyway — a number and the sentence describing it are two
claims.)*
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
| E1-e | **every** numeric operand the panel renders was actually **carried** by the record — and the limit case where it carries **none** of them | for each of the four operands × {omitted, `None`, `""`} → one identical "not recorded" panel carrying no fabricated `0`; **plus** the operand carried, asserting its value takes over; **plus** the pre-pass seed holding neither `pruned` nor `achieved_index` → the `pending Phase 5` verdict and no coerced `0`, and carrying `pruned` retires it | **RED** (1 of 12 cells green; 0 of 8 on the pre-fix renderer) | GREEN |
| E1-f | the sanction and the **success** are one decision | the **lean-resolvable** state (`pruned=0`, `achieved_index=900` **under** a 1200 budget, `reaches_budget=False`) → the `✓` present, the remedy **and** the ⚠ absent. Every other fixture in this family pairs that flag with an **over-budget** index, so `resolved_by_lean` was False everywhere and this conjunct never bound | **RED** | GREEN |
| E1-g | the `0 <` lower bound on `resolved_by_lean` | a **BLANK** `achieved_index` beside a **CARRIED** `pruned: 0` → `index: not recorded` and **not** `resolved by rebuild-lean` (a blank coerces to `0.0`, and `0.0 <= budget` resolves the gate) | **RED** | GREEN |
| E1-i | the panel's budget fallback is the **constant**, not a literal | a record with **no `budget` block** and `achieved_index: 1300` → `resolved by rebuild-lean`, **not** the ⚠. The renderer's `1200` literal was a threshold **no producer writes**, so the gate read as unmet against an invented one (E3's class: a default that is not the real value) | **RED** | GREEN |
| E2-a | `n_blocked > 0` with zero rows drawn → the counts-only breakdown, never a phantom tail | `render()` on the **two-part** fixture (§2.2) → exact breakdown string present, `+30 more blocked` absent | **RED** | GREEN |
| E2-b | `0 fleet-candidates` is suppressed when `n_blocked > 0` | same record → the cold-state line absent | **RED** | GREEN |
| E2-c | the counts-only guard keys on **blocked rows drawn**, not on an empty candidate list | one fleet-candidate + `n_blocked: 20`, no blocked row persisted → breakdown present, `+20 more blocked` absent; and 8 blocked rows drawn under a count of 30 → tail present, breakdown absent | **RED** | GREEN |
| E2-f | the blocked-rest term is the **record's own** count | an all-`generic-cli` window → the tail equals `n_blocked − generic-cli`; measured, an earlier draft re-subtracted `n_day_spread` and rendered `30 blocked — 10 generic-cli` for a 30-row count. The `n_day_spread: 0` arm is the **non-vacuity half** — it stays green under the subtraction mutant, which is what shows the repair removed a term rather than the whole line | **RED** | GREEN |
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

**E1-e's census has a fifth arm, and it is the one state the other four route around by
construction.** Each operand row keeps `pending` False on purpose — its siblings carry one of
`pruned`/`achieved_index` — so the **pre-pass seed**, the record holding *neither*, was asserted on by no
check in this suite: `pending Phase 5` appeared in no other assertion, and §3.1's measurement of row 1
was the only place it was exercised at all. It is **not** unrendered elsewhere — `_ceilRecB` and the
`over_ceiling: False` record are both pre-pass records and both render the verdict — but no check READS
it there. This sentence continued "so a refactor dropping the branch would leave the suite green" through
revision 9, and that is true only of the suite **without** the arm below — but the arm and the clause it
refutes entered in **one commit**, `bb52757` (revision 6), three lines apart in one bullet of that
revision's own ledger: the clause was refuted by its own ledger entry from the moment it existed, and
still reached the label a failure prints, the comment above it, and here, where it stood through
revision 9 as a claim about the suite *as shipped*. The injection pair measures both halves: branch deleted + arm → **E1-e
reds alone**; the *same* tree on the pre-arm harness → **green**. The gap is the missing ASSERTION, not
a missing render — and "missing" is the operative word, since with the arm in place nothing is missing.
Measured, not assumed: the arm was added, then verified by
**injecting the defect it guards** — `pending = not _recorded(rem, "achieved_index")`, an *over-broad*
condition that drops the `pruned` operand. That single edit reds **two** checks, and for two different
reasons that are both correct: E1-e's new arm, because a carried `pruned: 3` then reads as pending and
the verdict it should retire stays; and E1-g, because a *blank* `achieved_index` beside a carried
`pruned: 0` is exactly the state E1-g's label names ("`pruned` is carried, so `pending` is False and
the branch still runs on a coerced `0.0`") and the over-broad condition sends it down the other
branch. The arm asserts the carried spelling too, so a rename cannot satisfy it — the inversion
`a-complete-guard-inverts-its-question` asks for, applied to the census's own limit.

**Seventeen pins, one regression guard, and the guard is listed in the same table on purpose.**
E1-a…e, E1-f/-g/-i, E2-a/b/c/f and E3-a/c are behavioural (they drive the real renderer); E3-b and
E4-a/b are structural (they census the real producer). E3-a and E3-c are the behavioural witnesses for
the two repairs E3-b and its sibling census perform — the pairing is deliberate, because a count says
*how many* moved and a probe says *which*. The "Pre-fix" column is what keeps E3-d honest: it is the
one row that does not read **RED**, and naming that in the row itself is cheaper than a footnote
somebody skips. *(This paragraph read "**Eleven** pins, one guard" until revision 6 recounted the
table it introduces: **18** rows, **17** of them pins. The figure had survived two revisions that
each **added** rows to this table and updated the ledger's copy of the count — the sentence directly
above the table was the one place neither pass looked. See revision 6.)*

**Three of these were false pins as first drafted, and the corrections are load-bearing.**

- **E1-c needed its extraction named.** Comparing the **whole remediation block** it is **GREEN
  pre-fix** (the `↓ 0 …` vs `↓ 5 …` line already differs, so "notes differ" is satisfied). Restricted
  to the **note string** it is RED at every lever. Asserting **exact strings per arm** is what makes it
  a pin — and it closes a second hole, since an implementation that **swaps** the two verdicts also
  makes "they differ" true.
- **E1-b needed its set defined — and the set is a pair of *readings*, not a count.** A pair count
  quoted without its normalizer is testimony, and this document carried one. **Measured on
  `1d97f54`**, driving `rd.render()` over five `lever` values (`gc` · `justify` · `prune` ·
  key-absent · an unmapped `zzz`) at `candidates_surfaced=1`, `achieved_index=1500`:
  - At `pruned=0` the census is **10 pairs, 0 already equal, 10 differing** under E1-b's own
    normalizer. The earlier revision's *"7 differing lever pairs but **3 already equal** (`gc` vs
    absent, `gc` vs an unmapped label)"* is wrong in its count **and in every example it named** —
    none of those three pairs is equal. Re-read by dropping the whole `… · over-budget gate ·
    lever …` header line instead of the label token, the same census gives **1 equal, 9 differing**,
    and the single equal pair is **`absent` vs `unmapped`** — the two labels that emit *no note at
    all*. The pair that sentence was reaching for is the one that renders nothing twice, and `gc` is
    in neither half of it.
  - The two readings part company on exactly one axis, and it is worth naming because it bounds the
    normalizer: the header prints the label **uppercased** and prints **nothing** when the key is
    absent (`… · lever `, no `\w` for `lever \w+` to match), so *every* pair involving the absent
    label differs at a line the normalizer cannot reach. That is a **normalizer artifact, not a render
    difference** — which is why `pruned=2` reads **6 equal / 4 differ** raw and **10 equal / 0 differ**
    body, the 4 raw differences being precisely the 4 absent-pairs. `_e_nl` is therefore narrower than
    "the header's own label", and it can only ever produce a **false RED**, never a false green — the
    safe direction.
  - The conclusion this bullet defends survives, and is now **reading-independent**: driving the
    asserted `{prune, justify}` pair itself, it is RED at `pruned=0` and **GREEN at `pruned=1` and
    `pruned=2`** under *both* readings → a `pruned>0` fixture is not a pin. Under a whole-block
    reading it can **never** go GREEN, because §2.1 keeps `lever` in the header. A pin that can never
    pass is as broken as one that can never fail.
- **E1-b and E1-c share one fixture.** The earlier revision asserted **four** constraints on it; taken
  one at a time on `1d97f54`, **two are real, one is not a constraint at all, and one is true of one
  pin but false of the other**:
  - **`pruned=0` — real, and exactly so.** The asserted pair is RED here and GREEN at `pruned=1` and
    `pruned=2` under both readings (bullet above). This is the constraint that carries the pin.
  - **`achieved_index` above `budget_tokens` — real for E1-b**, by the mechanism the earlier draft
    named, which the measurement **confirms**: at `:887`
    `resolved_by_lean = (not pruned) and (0 < ai <= budget_tok)`, so an under-budget `achieved_index`
    takes the resolved branch and **the note really does not render**. Swept over
    `ai ∈ {absent, 0, 900, 1200, 1500, 2000}`, **E1-b's equality conjuncts go GREEN in exactly the
    under-budget nonzero band** (900, 1200) — two note-less panels compare equal, so the property the
    pin exists for is *unobservable* there. What keeps the check RED is its **non-vacuity guard**
    (`"mirror-dominated" in _e_b3`), which fires on the *absence of the panel content*. That guard is
    **load-bearing, not decoration**, and this is the third instance of the cycle's own conjunct
    pattern (E1-g, E2-f): red on pre-fix code for a conjunct other than the one the name carries.
  - **`reaches_budget` "absent or `True`" — not a constraint.** At `pruned=0` the asserted pair is RED
    for `reaches_budget` ∈ {absent, `True`, **and `False`**}. Measured; the value does not matter.
  - **"killing *both* pins pre-fix at once" — false of E1-c**, which is RED at **every** value of
    `achieved_index`, and for a *different conjunct set* in each band: over-budget via `k1` (the
    repaired `"0 candidates surfaced — …"` text is absent) and `k3` (the ⚠ renders), while under-budget
    it stays red via `k1` and `k2` because `k3` is **also** False — the same early branch that
    suppresses the note also suppresses the ⚠. Nothing about E1-c turns on `achieved_index`; that is
    the payoff of asserting **exact strings per arm** rather than a difference between arms.
  Both pins were measured RED pre-fix and GREEN post-fix on that fixture.

**E4-a was not *false* as drafted — it was not *hermetic*, which is the same defect one level down.**
`resolve_store` falls back to `os.environ` when given no `environ` kwarg, so the drafted pin resolved
the **maintainer's real** config root and let `identity_snapshot` read a real `control.sqlite` for its
`conflicts` sub-count. Every one of the suite's other `resolve_store` / `_enroll_personal` call sites
sets `HOME` to a temp dir **first**; this was the only one that did not. The verdict was never at risk
— that key is declared, and present-or-absent both satisfy `<=` — and that is precisely why it would
have shipped: a pin whose *inputs* depend on the machine it runs on is a pin that can only be trusted
on the machine it ran on, and the suite's own header promises hermeticity. Corrected by setting `HOME`
inside the `TemporaryDirectory` and restoring it in a `finally`.

**The normalization in E1-b was measured, not assumed.** A whole-render equality is only as strong as
what the normalizer strips, and a regex sub that strips too much makes the comparison vacuous. Measured
on both operand sets: each render is **17 lines**, each contains **exactly one** `lever {WORD}` match,
and the two renders differ in **exactly one** raw line — the panel header that carries the label. So
the normalization touches the header and nothing else — and because `_re34.sub` **replaces** the label
in place rather than deleting the line, the equality holds over **all seventeen** lines, the header
included in its normalized form. (Revisions 1–5 said "fifteen" and revision 6 said "sixteen": both are
counts of a *remainder*, and the pin compares no remainder — it compares the whole render. The digit
was corrected twice without the framing being re-derived, which is this section's failure at one
remove: a number carried on the strength of its being a number.)

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

**And RC-89's repair closed half a hole.** It removed the tautology, but the guard's *condition* was
still wrong, and RC-89's fixture cannot see that either — it draws blocked rows, so
`_shown_b > 0` and the two candidate conditions agree on it. **E2-c is the check that separates
them**, which is why it is a pin against the pre-fix revision *and* against the first cut: a repair
that removes a tautology and leaves the condition unexamined is a repair of the fixture, not of the
claim.

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

**The census that closes, and the two readings that do not.** The D6 constant moved by **27** for
this cycle, and the split is **17 pins** — 15 printed `(PIN)`, 2 printed `(CENSUS PIN)` (E1-e,
E3-b) — plus **9 guards** (the seven E5 rows, E1-h, E1-j) plus **1 regression guard** (E3-d). Every
tier token in that sentence is *printed by the harness*, so the census is re-derivable without this
document. Two readings that skip a step get a different total, and both are named here because this
cycle exists to catch exactly this shape:

- **A source-level census undercounts by six.** The seven E5 rows are **one** `check()` inside a
  `for`, so a `grep` over `tests/smoke.py` finds **21** citation-style labels where **27** checks
  execute. A reader who counts labels and checks the arithmetic against D6 finds a six-check gap
  that no edit accounts for.
- **E3-d prints `(GUARD)` where the census says "regression guard".** Not a contradiction to repair:
  a regression guard *is* a guard, so the printed token is a true **superset** of the census class
  and understates nothing a reader needs. The two are recorded separately because they are verified
  differently — a guard by **injecting** the defect it guards against, a regression guard by the
  **revision history** it already has (§4.1's E3-d row).

The E5 rows are the contrast that makes the second reading worth stating at all. Their label was
wrong in a way E3-d's is not: it printed **`(v0.1.12 full nested pin)`** on checks introduced in
**v0.4.34** and built as guards — a different revision *and* a different tier. A family name broader
than the census class is true; a provenance naming another release is false. Only the second is a
defect, and the census is what surfaced it.

**Each of the nine guards, and why it is not a pin.** The criterion is single and mechanical: a
check is a **guard** when it cannot fail on the pre-fix tree, and each of the nine fails that test
for one of two reasons — it **did not exist** pre-fix, or the defect it names was **invisible** to
the pre-fix code.

| Guard | Why it cannot red on pre-fix code | Injection that reds it |
| --- | --- | --- |
| the **seven E5 rows** | the checks do not exist pre-fix, and the seven shapes were in perfect key agreement — there was nothing for them to catch in the old tree | a key added to (or removed from) either side of any of the seven SKILL↔TypedDict pairs |
| **E1-h** | the pre-fix renderer read the `lever` the routing had just written, so it could not see the persisted operand **at all**. The defect is masked by exactly the confusion E1(iv) removes. Its redness needs a **fixed renderer meeting a rounded producer** — one of the four (renderer, producer) cells, and the only one that fails | a rounded `mirror_share` copy on the producer side (`1005/2000 = 0.5025` routes `gc` and rounds to exactly `0.5`, which fails the renderer's strict `>`) |
| **E1-j** | the suppressed sentence does not exist pre-fix, so pre-fix code passes it — and deleting the conjunct moves **no other check**, which is what makes it worth having | deleting `not mirror_dominated` from the verdict branch |

The band E1-h samples is **two-sided on purpose**: `999/2000` and `1000/2000` agree at and below the
boundary, so the repair cannot be a `>=` — that would move the disagreement to the other side rather
than remove it. A one-sided band would have accepted a wrong fix.

### 4.3 Mutation verification

Measured on the **uncommitted cycle tree** for the green control and on mutant trees built **from that
same tree**, one named edit set per mutant. The `git worktree add` prohibition still holds absolutely
(a linked worktree resolves the *main* project's identity, so the hermetic-`HOME` checks fail on it);
the earlier passes used `git archive 1d97f54 | tar -x` and the final pass copied the current tracked
working tree, which is the same discipline with the revision moved forward. **One process per tree**:
`sys.modules` caches the first import, so two trees compared in one process compare #1 against itself.
Every number below belongs to the **triple** (restored code, fixture, harness) and is not carried
across an edit. This section was re-measured **six** times because the sources it measures moved six
times — the harness was renamed mid-cycle (`_e_rec` → `_e34_rec`, see the collision note); the E3-d
fix landed in the renderer; E4-a's fixture gained a `HOME` override (a harness fix, §4.1); the E2-c
comment gained the archive-prevalence figures; the seven E5 rows were moved into a loop of their own
(§4.2); and the third pass edited the harness **again** — one added arm inside `E1-e`, plus two
rewritten labels — while the renderer took a comment-only edit. So the counts are stated *with* the
revision rather than as properties of "the pins". **The generation the table below is bound to is
named `rev8`, and its identity is a tuple of hashes rather than a sentence**: `tests/smoke.py` =
`74fbba783b19aa25`, `memory_status.py` = `51f460cf8aad3d18` and `tests/dashboard_fixture.py` =
`e5021dcbcc956772` across all thirteen trees, with `render_dashboard.py` = `dd41ac01a055de8b` in the
three trees carrying the current renderer and ten mutant hashes — unchanged from `rev7`'s — in the
other ten. The generation-by-generation tuple is the table under *"Then it moved a sixth time"*
below.

**The fifth re-measurement exists because a fingerprint caught what no count could, and the fingerprint
was on the one tree where a count is structurally blind.** The batch was run, in full, against trees
carrying the **fourth** harness — the E5 label repair landed *after* `build.py` had tarred the trees.
The check that found it was not any of the thirteen counts: it was hashing `tests/smoke.py` in the
`LIVE` tree against the working tree, which disagreed (`205c8659748e542d` vs `d9f3601d2e10b935`).
`LIVE` is exactly where a count **cannot** see the drift — the label repair changed no check's
verdict, so `LIVE` reads `2016 / 0` under both harnesses — and that is the general shape, not a
coincidence: **the member of the triple most likely to move without moving a count is the harness**,
because a harness edit that changes *what is printed* rather than *what is tested* is invisible to
every number the suite reports. The earlier passes' rule ("a mutant tree must be rebuilt whenever any
member of the triple moves") was already in this section; what the fingerprint adds is that the
**green control** needs it as much as the mutants, and that the instrument which catches it is a hash,
not a count.

The second run had a prediction, and it was made before the measurement: every tree reproduces its
count **and its red set** exactly, because a label change cannot move a verdict. The comparison is
made by **one** extractor run twice over two log directories, never by two extractors — two parsers
would leave the comparison itself unverified. *(`reds.py` reads `sys.argv[1]` for exactly this
reason.)* The result is recorded at the end of this section.

**The trees are defined by their EDIT SET, and that is a correction this pass had to make.**
The first version of this section defined them by revision ("both = HEAD"), and one of them was then
built wrong. `diff -rq` did not catch it — and could not: it reports **which files differ**, never
**which edits**, so a tree built with the wrong edit set inventories exactly as intended. Two of this
pass's three measurement errors were trees that were not the tree their name claimed. The definition
has to name the edits:

| Tree | Edit set (applied to the LIVE tree) |
| --- | --- |
| `LIVE` | none — the green control |
| `mutA` | `render_dashboard.py` ← `1d97f54` (this cycle's E1/E2/E3 fixes, and the review follow-ups to them) |
| `mutB` | the E4 drift re-injected **surgically**: the `Identity.domain_lifecycle` declaration removed, and `"window"` dropped from `audit_diff`'s return |
| `mutD` | `render_dashboard.py` ← `6368288` — the **committed revision**, i.e. the first cut the review found |
| `prefixE` | `mutA` + `mutB` |
| `mutE` | **both scripts ← `1d97f54`** — the true pre-fix pair, and the reference every "pre-fix" claim in this document is against |
| `R1f` … `R1j`, `R2f` | one surgical re-injection each — the defect the corresponding pin or guard names |
| `RC89` | `_shown_b = len(_blocked)` — the display cap removed, re-injecting the RC-89 tautology's repair |

**`mutE` was redefined, and the redefinition is the correction rather than a convenience.** The
previous version built it *forward* as "`prefixE` + the `mirror_share` declaration removed", which is
a tree no revision ever had: it reverted the producer's *declaration* while leaving its *body* — so it
red the `remediation` row for a reason (`mirror_share` undeclared) that the true pre-fix tree reds for
as well, but by construction rather than by history. `pre` in the earlier pass was this tree under a
different name, and the identity is now proven rather than asserted: both scripts byte-identical to
`1d97f54` (`rd=309e3df5b02a2ec7`, `ms=f3546bdd01014194`), and the red set reproduces the earlier
`pre` measurement exactly — **1996 passed / 20 failed**.

| Tree | Scripts | Passed | Failed | Reds |
| --- | --- | --- | --- | --- |
| **`LIVE` — green control** | both current | **2016** | **0** | — |
| **`mutA` — renderer reverted** | `render_dashboard.py` = `1d97f54` | 2000 | **16** | E1-a · E1-b · E1-c · E1-d · **E1-e** · E1-f · E1-g · E1-i · E2-a · E2-b · **E2-c** · E2-f · E3-a · E3-b · E3-c · the rewritten v0.1.35 arm |
| **`mutD` — the committed revision** | `render_dashboard.py` = `6368288` | 2011 | **5** | **E1-e · E1-g · E1-i · E2-c · E2-f** — exactly the pins whose repair is **uncommitted** |
| **`mutB` — E4 drift re-injected** | the two surgical edits above | 2013 | **3** | E4-a · E4-b · `SKILL↔TypedDict: schema-block identity == Identity` |
| **`prefixE` — both reverted** | `mutA` + `mutB` | 1997 | **19** | `mutA` ⊎ `mutB` — measured as sets, disjoint |
| **`mutE` — the true pre-fix tree** | both scripts = `1d97f54` | 1996 | **20** | `prefixE` ⊎ `SKILL↔TypedDict: schema-block remediation == Remediation` |
| **`R1f` … `R1j`, `R2f`** | one re-injection each | 2015 | **1** each | its own check, and nothing else — six-for-six |
| **`RC89` — the cap removed** | `_shown_b = len(_blocked)` | 2015 | **1** | the RC-89 display-cap arm |

The rows are named in full because **the two `SKILL↔TypedDict` reds are the ones that separate `mutB`
from `mutE`**, and a short label collapses them into one — see *the extractor threw information away*
below, where that collapse produced a wrong set from a right count.

*(Sources for this table: `tests/smoke.py` at `74fbba783b19aa25`, `render_dashboard.py` at
`dd41ac01a055de8b` where it is current, `memory_status.py` at `51f460cf8aad3d18`. See "The whole
table was re-measured once more" and "Then it moved a sixth time" below for why it moved three times
and what each move cost.)*

**The reds are compared as SETS, not as counts.** `prefixE == mutA | mutB` exactly and disjoint;
`mutE == prefixE | {the remediation row}`; `mutD ⊆ mutA` with `mutD`'s two reds inside it. This is
worth doing rather than reading off the numbers, because two of these counts are close enough that a
compensating swap — one check reddening while another goes green — would leave the count intact and
the property false. The counts say how many moved; only the set says *which*.

**`mutD` is the measurement that matters for this pass's review, and its count is the one this pass
predicted wrong.** It reds **5**, not 2: E1-e, E1-g, E1-i, E2-c, E2-f. The miss is in *my model of
the tree*, not in the tree — `mutD` **is** `HEAD`, the committed revision, so it reds every pin whose
repair is **uncommitted**, and by the third pass that set had grown from the two the second-pass
review provoked (E1-e, E2-c) to five, as the third pass's three new pins joined them. The earlier
sentence — *"exactly the two pins the review provoked"* — was true when E1-e and E2-c were the only
review-provoked pins, and reading it a pass later made a true statement look like a general one. Its
value is undiminished and sharper: **five named pins are red on the commit and green on the tree**,
with nothing else in the suite moving.

**`mutE` is not a fifth fix-set; it is the reference tree.** Both scripts at `1d97f54`, byte-identical,
and its **20** reds are the union of the two halves plus the remediation declaration row. The earlier
version of this section called that construction `prefixE` and built it *forward*; the identity `pre ≡
mutE` is now proven by hash rather than argued by count, which matters because **a passing count is
not a fingerprint** — the stale-tree paragraph below is the witness that two different trees can
report the same number.

**Every count above was predicted before it was measured, and the predictions found all three of this
pass's measurement errors.** Pass 1: `mutB` predicted **3**, measured **4** — the extra red was the
stale tree (below), not a property. Pass 2: all four matched. Pass 3: `prefixE` predicted **16**,
measured **15** — the missing red was the `mirror_share` row, which the tree could not produce
because it had been built with `mutB`'s edited file rather than the parent's. A prediction that
matches is weak evidence on its own — the property and the tree can both be wrong in the same
direction — so it is the **miss** that carries the information. Note the shape of pass 3's error: the
count was right for the *declared* construction and wrong for the *built* one, so the miss did not
say "the property is wrong"; it said "the tree is not the tree the sentence says". Adding the
**set** comparison above is the structural fix for that class, since a set inequality localizes the
disagreement to a named check instead of leaving a number one short.

**All seventeen pins red, and each mutant reds only its own half.** `mutA` reds the **15 render-side
pins** plus the rewritten v0.1.35 arm; `mutB` reds the **2 producer-side pins** plus the identity
declaration row; `mutE` reds their union plus the remediation row. The two halves are disjoint, and
`mutA` leaves E4-a/E4-b green while `mutB` leaves every render pin green. That isolation is the
measurement's point — a pin that reds under both mutants would be evidence that it is testing the
*build*, not the property. *(This read "All **thirteen** pins" until revision 6; the third pass added
four pins — E1-f, E1-g, E1-i, E2-f — and the sentence that counts them was not on the pass's list.)*

**The seven E5 rows are GREEN in every tree**, which is the measured confirmation of §2.5's
"guards, not pins" claim rather than a restatement of it: they do not exist pre-fix, and pre-fix the
seven shapes were in perfect key agreement, so there is nothing for them to catch in the old tree.
What they buy is that the next drift in any of the seven reds the suite instead of landing in the
blind spot the old comment asserted could not exist.

**E1-h and E1-j are green on the true pre-fix tree too, and that is a stronger statement than the E5
rows'.** For the seven, "green pre-fix" is nearly tautological — the checks did not exist there. For
these two the checks *do* run against `1d97f54`'s both scripts and pass, which is the guard criterion
discharged against the real pre-fix revision rather than against a story about it. The `mutE` row is
the evidence: **20 reds, neither of them among them.** Each is still red under its own re-injection
(`R1h`, `R1j`), so "guard" here means *cannot fail on pre-fix code*, not *cannot fail* — and the two
facts together are what §4.2's census table asserts.

**E3-d is green in all six trees too — and unlike the E5 rows, that is a *different* claim.** The
seven have no red anywhere in this cycle; E3-d has one, on the intermediate revision, which is why
its row in §4.1 does not read **RED** and why its label names that revision. Green here is not
"nothing to catch" — the guard's whole reason to exist is that the defect it catches *did* occur in
this cycle's own work, was caught by a human reading a diff, and would not have been caught by any
check in the suite as it then stood.

**E1-e and E2-c have the same status as E3-d, and came from the second pass's review rather than the
first pass's sweep.** Both are green wherever the renderer is current — `mutB` keeps the current
renderer and reds neither — and both are red in `mutD`, which is the revision they were written
against. Their labels name that revision, and the `mutD` row is the evidence for it.

**The measurement tooling then failed silently in exactly the way this cycle studies, and it is the
second such failure in one pass.** The red lists were first extracted with `grep '^ ✗'` — **one**
leading space — while the suite indents a failure line by **two**. `grep` matched nothing and printed
nothing, and in a shell log an empty list is indistinguishable from *"this tree has no reds"*. It was
caught only because the **count and the list disagreed**: the same tree printed `14 failed` directly
above an empty list. Corrected to `'^  ✗'`, and every list in this section was re-extracted with it.

**And it failed a third time, in the *other* direction — the extractor threw information away rather
than finding none.** Normalizing each red line to a short label with `sed 's/:.*//'` truncates at the
**first colon**, which is fine for the cycle's own labels (`v0.4.34 E1-e: …`) and destructive for the
two `SKILL↔TypedDict: schema-block <name> == <TypedDict>` rows — `identity` and `remediation` both
become `SKILL↔TypedDict`, so `mutE`'s red set came back **15 for a tree that printed 16**. The
consequence is not cosmetic: `mutE`'s entire claim is that it differs from `prefixE` by **exactly one
named row**, and the collapsed extractor reported `mutE − prefixE = ∅` — reproducing the very
"the tree is not the tree the sentence says" failure this section exists to record, from the
instrument rather than the build. Corrected to split on ` — ` and then on ` (`, which keeps
`schema-block remediation` and `schema-block identity` distinct. **Both extraction bugs were caught
the same way and only that way: the printed count and the extracted set disagreed.** A set compared
without also asserting `len(set) == reported_count` is an unverified set.

**The whole table was re-measured once more, for a comment-only harness edit, and the prediction was
that nothing would move.** Editing `tests/smoke.py`'s E2-c comment block (to add the prevalence
figures) changed a member of the triple, so the counts could no longer be carried — and Python
comments cannot change which checks run. Predicted **before** measuring: all six counts identical.
Measured with the harness at **`c5e9fd6cded55c6f`** and every tree **rebuilt from the current working
tree** rather than reused: the table above, reproduced exactly, with the set algebra holding
(`mutD ⊆ mutA`; `mutA ∩ mutB = ∅`; `prefixE = mutA ∪ mutB`; `mutE − prefixE` = that one row;
`prefixE − mutE` = ∅).

**Then it moved a fifth time, and this time the prediction was the thing under test.** The harness
moved for the E5 label repair, `build.py` was not re-run before `run.sh`, and the batch therefore
measured the fourth harness — caught by hashing `LIVE/tests/smoke.py`, never by a count (see the
opening of this section). The second run is the same thirteen trees rebuilt from the current tree,
and the prediction, recorded before it: **every count *and* every red set reproduces exactly.** Both
extracts come from one parser run over two log directories, so the comparison cannot be an artifact of
two differently-written readers. Measured: the two extracts are **byte-identical** — every count and
every red set, tree for tree — and all ten identity assertions the extractor prints hold unchanged:
the four set relations over the six main trees (`prefixE = mutA ∪ mutB` exactly and disjoint;
`mutD ⊆ mutA`; `mutE − prefixE` = the single `SKILL:remediation` row) and the six one-to-one `R1f` …
`R1j`/`R2f` checks, each a singleton naming its own check. The generation inventory confirms the
**mechanism** the prediction asserted, not only its outcome: the two runs differ in **one** member,
`tests/smoke.py` (`205c8659748e542d` → `d9f3601d2e10b935`), with every renderer and every
`memory_status.py` hash unchanged across all thirteen trees — so "nothing moved" is a claim about a
swap that provably moved nothing else.

**The rebuild discharged the inventory obligation, and it was worth doing rather than assuming.** Each
tree was fingerprinted by **edit set**, not by name: the renderer and `memory_status.py` hashes
against the two reference revisions, plus a direct assertion that each of the three surgical edits is
present or absent where its tree says. That mattered, because the trees this pass inherited sat in
directories whose names do **not** match this spec's — the second pass's `mutA` lived at a path called
`mutC`, and the first pass's `/tmp/mutA` is a different tree entirely. **The inventory is the identity;
the name is a label** — which is this cycle's thesis one level up, and the reason the check is a
fingerprint rather than a directory listing.

**Then it moved a sixth time, and this is the first move where the harness edit was *behavioural*
rather than cosmetic — which is what makes its prediction a test instead of a near-tautology.** The
third pass added one assertion arm (`_E_REM_PENDING`) **inside** the existing `E1-e` census pin — no
new `check()` call, so the census constant stays `2016` — and rewrote two labels (`E1-e`'s own, and
`E3-d`'s). The renderer moved too, comment-only. Both landed **after** `rev7`'s trees had been built,
so the batch then running was measuring a tree the working tree had already left; the instrument that
caught it was again a hash and not a count. `rev8` was built as a **two-file swap on `rev7`'s
preserved trees** — `cp -a rev7 rev8`, the frozen harness into all thirteen, the frozen renderer into
the three whose renderer hash equaled `rev7`'s — and that construction is **stronger than a rebuild
in exactly the one place that matters**: a rebuild can only *intend* that the mutation definitions did
not change, while the swap **asserts** it. The mutant inventory is the identity, so the swap cannot
silently alter a mutant; the only member that moved is the instrument.

| Member | `rev6` | `rev7` | `rev8` |
| --- | --- | --- | --- |
| `tests/smoke.py` — all thirteen trees | `205c8659748e542d` | `d9f3601d2e10b935` | **`74fbba783b19aa25`** |
| `render_dashboard.py` — `LIVE`, `mutB`, `R1h` | `929fd9c425f1c3ca` | `929fd9c425f1c3ca` | **`dd41ac01a055de8b`** |
| `render_dashboard.py` — the other ten trees | ten mutant hashes | **identical to `rev6`'s** | **identical to `rev7`'s** |
| `memory_status.py` — `LIVE`, `mutA`, `mutD`, `R1f`, `R1g`, `R1i`, `R1j`, `R2f`, `RC89` | `51f460cf8aad3d18` | `51f460cf8aad3d18` | `51f460cf8aad3d18` |
| `memory_status.py` — `mutB`, `prefixE`, `mutE`, `R1h` | four mutant hashes | **identical to `rev6`'s** | **identical to `rev7`'s** |
| `tests/dashboard_fixture.py` — all thirteen trees | `e5021dcbcc956772` | `e5021dcbcc956772` | `e5021dcbcc956772` |

`rev6`, `rev7` and `rev8` name three **generations of this batch**, not three revisions of the branch:
the hash tuple is the identity, and the names exist only so the prose can refer to it. The four
`identical` cells are the measured content of the two-file-swap claim rather than a restatement of
it — and they are also, in this cycle's own vocabulary, the whole difference between a name and an
inventory.

*(The generations narrated from here on — `rev9`, `rev10`, … — are **this narrative's history**, and
their counts stay as measured. The generation the branch **ships** is `rev16`, whose thirteen counts,
thirteen red sets, five injections and re-measured pair are in **Revision 12**. Carrying any count
from below forward is the error the section itself names: a count belongs to the triple.)*

**The `memory_status.py` row was FALSE until revision 7, and it is the sharpest instance of this
document's own class in the document.** It read *"all thirteen trees"* with one hash, as though the
member were uniform. Measured on the preserved trees, **nine** trees carry `51f460cf8aad3d18` and
**four are `memory_status` mutants** — `mutB` and `prefixE` at `16189d1e96812824`, `mutE` at
`f3546bdd01014194` (the hash this document *already* names at §4.1 as `1d97f54`'s pre-fix partner),
and `R1h` at `f7456e94f9b33aee`. The same four hashes are identical in `rev6`, `rev7` and `rev9`, so
nothing moved mid-run: the row was **wrong when it was written**, inherited from the batch's own
prediction file (*"`memory_status.py` … all 13 trees; unchanged from rev6/rev7"*) and never checked
against the trees — while every other cell in the table *was* hash-verified. That is the cycle's
thesis one level up: the instrument that catches a moved member is a hash, and here the hash was
replaced by an **inherited assumption** for exactly the row where four members had moved. The cost is
concrete rather than editorial — this table is the **reproduction recipe**, so a reader rebuilding
the thirteen trees from it would put the frozen `memory_status.py` into `mutB`, `prefixE`, `mutE` and
`R1h` and get four different verdicts. Corrected here, found by asserting `rev9`'s hashes per tree
rather than by re-reading the row. *(Revision 7; the same build's per-tree delta assertion is what
made it visible — `cp -a` plus a two-file overlay, with the overlay confirmed to be exactly two files.)*

**The seventh measurement, and the first whose delta is purely prose.** `tests/smoke.py` **is** a
triple member, so the two comment corrections above (H1 and N2) moved the harness —
`74fbba783b19aa25` → `84dc59cb7b68f263` — and the batch was re-taken as **`rev9`**, built as `cp -a
rev8 rev9` plus a **two-file overlay** (`tests/smoke.py` and this document), the copy being what
asserts the twelve mutation definitions did not change. Every count **and** every red set reproduces
`rev8` exactly, tree for tree:

| Tree | `rev9` | red set vs `rev8` | Tree | `rev9` | red set vs `rev8` |
| --- | --- | --- | --- | --- | --- |
| `LIVE` | 2016 / 0 | identical (0 reds) | `R1g` | 2015 / 1 | identical |
| `mutA` | 2000 / 16 | identical | `R1h` | 2015 / 1 | identical |
| `mutD` | 2011 / 5 | identical | `R1i` | 2015 / 1 | identical |
| `mutB` | 2013 / 3 | identical | `R1j` | 2015 / 1 | identical |
| `prefixE` | 1997 / 19 | identical | `R2f` | 2015 / 1 | identical |
| `mutE` | 1996 / 20 | identical | `RC89` | 2015 / 1 | identical |
| `R1f` | 2015 / 1 | identical | | | |

Each extraction asserts `len(set) == reported_failed_count`, **for both generations** — a red set
compared without that assertion is an unverified set, which is the extractor failure this section
records twice.

**The generation is bound to a COMMIT, because a hash written into a document cannot describe the
tree that is writing it.** The `rev9` trees carry content that was **uncommitted** when the batch ran,
so the four values above describe no commit that contains this paragraph — recording them *is* an
edit. They are recoverable from **`bb5275764e035a3b8952975f6f2d69452e2d8b8e`**, the commit that froze
the triple before this document was written, and that is verified by recovery rather than asserted:
`git archive bb5275764e… | tar -x`, then re-hashing the four members **out of the extracted tree**,
returns `dd41ac01a055de8b` · `51f460cf8aad3d18` · `e5021dcbcc956772` · `84dc59cb7b68f263` — the four
values this section names — plus `CHANGELOG.md` at `8fc7e495908a9997`, which `smoke.py` reads as part
of `_extra69` and which therefore belongs to the measured inputs even though it is not a triple
member. **The order is commit → run → record, and that is the whole point:** a document cannot bind
itself to the commit that contains it, so the run is bound to the one that *precedes* it and the
recovery path is exercised instead of assumed.

**The eighth measurement, and the second consecutive one whose delta is prose.** Three labels moved —
E1-c's, E1-e's and E3-c's — so `tests/smoke.py` went `84dc59cb7b68f263` → `eeeafdcd908cd186` and the
batch was re-taken as **`rev10`**, built the same way (`cp -a rev9 rev10` plus the two-file overlay).
Every count **and** every red set reproduces `rev9` exactly, tree for tree: `LIVE` 2016 / 0 · `mutA`
2000 / 16 · `mutD` 2011 / 5 · `mutB` 2013 / 3 · `prefixE` 1997 / 19 · `mutE` 1996 / 20 · `R1f`…`R1j`,
`R2f`, `RC89` 2015 / 1 each — and all thirteen extractions satisfy `len(set) == reported_failed_count`.

**This run's delta assertion is stronger than the seventh's, and deliberately so.** The seventh argued
from *reading* its diff ("two comment blocks … no statement added, removed or altered"). Here the
claim was made structural instead: `check()`'s **first argument** is the label, so an AST pass replaced
it with a placeholder and dumped the remainder of the module — **1793 `check()` call sites in both
revisions, exactly three labels differing, and the rest of the tree byte-identical.** The property
being claimed is "no assertion moved", so it is evaluated on the parse rather than on a reading.

**The two injections reproduce, and the red check's NAME survives the label edit.** Rebuilt against
`rev10`'s harness: `inj10_branch` = **2015 / 1**, the single red `v0.4.34 E1-e` — the runner's
extractor strips from the first ` (`, and the rewritten label still opens `v0.4.34 E1-e (CENSUS
PIN):` — and `inj10_branch_noarm` = **2016 / 0**, green. The green run's evidence is its count and the
prediction it matched; this section's instrument asymmetry stands, and `[set==reported: 0]` is still
not a result.

**A third extractor failure, and this one was mine.** Comparing the two generations, every red set
first read as *MOVED* while every count reproduced — which is the signature of a mismatched extractor,
not of a moved check, and it was: the re-check used `sed 's/:.*//'` where the shipped runner uses
`sed 's/ (.*//'`, so the same labels were normalized differently on the two sides and
`v0.4.34 E1-f (PIN)` was compared against `v0.4.34 E1-f`. Re-derived with the shipped extractor, all
thirteen are identical. The lesson is the one this section keeps re-learning: **a red-set comparison
is only as good as the agreement between its two extractors, and re-deriving one side is not a
comparison.**

**The generation is bound to `7188c1a2cff1c51f59307ddb717cb54910a8783d`**, the commit that froze the
triple, and verified by recovery rather than asserted: `git archive 7188c1a… | tar -x`, then
re-hashing the four members **out of the extracted tree**, returns `dd41ac01a055de8b` ·
`51f460cf8aad3d18` · `e5021dcbcc956772` · `eeeafdcd908cd186` — the four values this section names.

**The binding was re-proven after an amendment, and that is not a formality.** The first commit of
this triple carried a count in its *message* that had never been measured — "eighteen of the twenty
labels held", where the matcher reached **eight of the eighteen** labels carrying such a claim and
nineteen of the file's twenty-eight capital `Pre-fix` occurrences belong to earlier cycles and were
never read. That denominator is itself the defect: twenty-eight is 13% of the file's 210
case-insensitive spellings, and the sweep read exactly the denominator it quotes. The number is the cycle's own
defect class, in the commit message, which is why it was amended rather than left standing. Amending
rewrites the commit and therefore its SHA; the **tree** is untouched, so the four hashes above should
be unaffected — but "should be" is the argument this section refuses, so the recovery proof was
**re-run** against the new commit rather than carried across. It returns the same four values. A
commit message is not part of the triple, and that is exactly why it had to be measured separately.

**And the amended message still carries a number this section's census corrects.** It reads "the 20
outside §E1–E4 belong to earlier cycles and were NOT swept" — off by one. Enumerated from the diff: of
the 28 capital `Pre-fix` occurrences, **9** sit at or after the E1-a label through E4-b, and **19**
outside. The frozen message is *not* rewritten here — its SHA is the identity this section binds to, and
re-amending it would re-open the proof above — so the disagreement is recorded where a reader diffing
message against document will meet it, rather than left to be found. The class boundary is also not as
clean as the message implies in the other direction: one of the nine "inside" occurrences,
`'Pre-fix (and on the first cut of E1) seven of the eight cells'`, is a **quotation of a retired
label**, not a claim about the pre-fix renderer. "Inside §E1–E4" and "carries a claim about a non-HEAD
revision" are overlapping classes, not the same one.

**A generation's identity is the TRIPLE, and `docs/` is outside it on a measurement.** The identity is
`{render_dashboard.py, memory_status.py, tests/dashboard_fixture.py, tests/smoke.py}` per tree, all four
hashed and printed above. `docs/` is carried in the trees but excluded, because **nothing in the suite
reads it**: every `glob` in `smoke.py` runs over a temp tree, and this document's name appears in
`smoke.py` exactly once, in a comment at `:18394`. That exclusion is what lets this revision be written
*into* the measured generation without editing the thing being measured — the failure this section
records twice over — and its cost is bounded by the measurement rather than by convenience: a document
that could not be edited after the run could never record the run.

**The prediction, recorded before the batch, was that every count *and* every red set reproduces
exactly — and it did.** The `rev8` extract is byte-identical to `rev7`'s, tree for tree, and all ten
identity assertions hold unchanged, as they did across the fifth run. What that does and does not say
is worth separating, because the new
arm is not inert; it is inert *with respect to these thirteen trees*. The arm renders a record shape
(`{"lever": "prune"}`, carrying neither `pruned` nor `achieved_index`) that no fixture in this section
holds, so it can neither pass for a tree nor fail for one. A green suite therefore says only that the
arm did not *disturb* the table. Whether it **bites** is a different measurement, and it needs a
broken tree.

**The arm's own comment makes a claim, and the injections are what test it.** It reads: *"`pending
Phase 5` appears in no other check, so a refactor that dropped the branch would leave the suite
green."* — the two clauses the injections test. **The clause before them was false, and this revision
corrects it.** It read *"the pre-pass seed — the record carrying NEITHER — is rendered by this suite
nowhere else"*, and the suite renders it in two other checks: probed on the frozen tree, both
`smoke.py:4451`'s `_ceilRecB` (rendered `:4455`) and the `over_ceiling: False` record rendered at
`:4462` both print
`pruned/achieved pending Phase 5`. They are pre-pass records and they take the branch. What survives
is narrower in a way that matters: no check *reads* the line, so the gap is a missing **assertion**,
not a missing **render** — and a reader who believed the original clause would look for the coverage
hole in the wrong place. *(Third-pass review, finding H1. The E2-a fixture's rationale in
`tests/smoke.py` carried the same shape, and §2.2's fixture list with it — both corrected in this
revision, finding N2.)*

That is a claim about the suite **without** the arm, so testing it needs two trees differing
in exactly one member — and they were built that way, `diff -rq` confirming `tests/smoke.py` is the
only file that differs between them:

| Tree | Edit set | Predicted | Measured |
| --- | --- | --- | --- |
| `inj_branch` | `render_dashboard.py:955` — the `else:` arm that renders the pending verdict → `pass`; **`rev8`'s harness** | 2015 / 1, single red `E1-e` | **2015 / 1 — `E1-e`** |
| `inj_branch_noarm` | the same deletion; **`rev7`'s pre-arm harness** | **2016 / 0 — green** | **2016 / 0 — green** |

The pair is the measurement, not either run alone. `inj_branch` returning one red says the arm is
attached to the branch; `inj_branch_noarm` returning green says nothing else in the suite is — which
is exactly the comment's claim, and the counterfactual it names. Without the second run the first
would be equally consistent with an arm that merely duplicated a check that already existed. The red
set then discriminates the *mechanism*, not only the count: `E1-g` is **green** under the branch
deletion while the other injection reds it. That injection — `pending = not _recorded(rem,
"achieved_index")` at `:939`, dropping the `or _recorded(rem, "pruned")` clause — measured **2014 /
2**, reds `E1-e` and `E1-g`, and the mechanism is why they differ: `_recorded` treats a recorded `0`
as a measurement, so `E1-g`'s fixture (`pruned: 0` beside a blank `achieved_index`) has `pending`
`False`, which leaves `:939` untouched when `:955` is deleted — while the other injection flips that
very record INTO the pending state, where the `0 <` bound is never consulted and the assertion fails.
Two injections, two mechanisms, two red sets; a count alone would not have separated them. (The
`:_939` count is recorded here as *measured*, not predicted — no predicted value for it is on record,
which is the weaker form this section warns about. Its two reds are nevertheless attributable, since
`E1-g`'s label already names the dependency: the bound is what a `pending` flipped to `True` stops
consulting.)

**The pair was re-measured on the seventh harness, because a count belongs to the triple and one
member of the triple moved.** `rev9`'s `tests/smoke.py` carries two rewritten comment blocks and no
changed statement, so the prediction was that nothing moves — worth recording precisely because a
comment *cannot* move a check, which makes any movement evidence that the run is not describing the
tree it claims to. Both injections were rebuilt against `rev9`'s harness (`cp -a` from the `rev8`
pair plus an overlay, the copy being what asserts the one-line deletion is unchanged) and both
reproduce: `inj9_branch` **2015 / 1**, the single red `E1-e`; `inj9_branch_noarm` **2016 / 0 —
green**. The arm still bites, and the pre-arm harness still cannot see the deletion.

**And again on the eighth, for the same reason and with a stronger argument.** `rev10` moved the
harness a second time (three labels), so the pair was rebuilt against it: `inj10_branch` **2015 / 1**,
the single red `E1-e`; `inj10_branch_noarm` **2016 / 0 — green**. The `E1-e` *label* was one of the
three edited, so this run also checks that a relabelled check keeps the name the extractor reports —
it does, because the runner strips from the first ` (`. What makes the eighth's delta assertion
stronger is that it is no longer a reading: an AST pass replaced `check()`'s first argument (the
label) with a placeholder and dumped the rest of the module, giving **1793 call sites, three labels
differing, and everything else byte-identical.** "No assertion moved" is the property under test, and
it is now evaluated on the parse.

One asymmetry in the instrument, recorded because it is this cycle's own class. The assertion that
makes a red count *attributable* is `len(set(reds)) == reported_failed_count` — it is what separates
"one red" from "one red, and it is the one I named". On a **green** run the red set is empty, so the
assertion holds identically for every green outcome and certifies nothing; the green run's evidence
is its **count** (2016 — the census of the thirteen trees **as measured here**; `E1-i2`'s arrival
later moved the shipped census to **2017**, Revision 12) plus the prediction it matched, and the
set assertion contributes there only by not failing. A reader taking `[set==reported: 0]` as a
positive result would be trusting an instrument that cannot fail in that direction. *(The same
asymmetry appeared while writing this paragraph, in an ad-hoc re-check rather than the runner:
`grep -c .` on an empty file prints `0` **and** exits 1, so `$(grep -c … || echo 0)` yields `0\n0`
and a green tree reported a `MISMATCH` that did not exist. The shipped runner takes no fallback,
which is why it was right and the re-check was wrong.)*

**Counts are not fingerprints, and this pass has the witness.** The stale `/tmp/mutA` from the first
pass carries a **different harness** (the first cut's `smoke.py`, without E1-e/E2-c) and reports the
**same** `1998 passed` as the correct tree — because the stale one has 2 fewer checks and 2 fewer reds,
and the difference cancels exactly. A reader re-deriving this table by *count* alone would have
accepted the wrong tree. Only the set comparison and the edit-set inventory separate them, which is
why both are recorded here rather than the table alone.

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
the panel's window line, and the pre-fix `memory_status.py` defines no such name — so an `--persist`
subprocess
dies, a later era's fixture never gets its log file, and the suite **ERRORs out of the run entirely**
before reaching §4.1's pins. B was therefore built *forward*, by re-injecting exactly the two producer
keys on the current file, which is the drift the pin names. The general point: **a revert recipe that
assumes the two scripts are independently restorable is itself an unchecked claim** (E4 introduced a
new cross-module read — the class is old, `ms._REGISTRAR_BLOCKED_CAP` and `ms._MIRROR_DOMINATED` are
the same shape — but which symbols may be restored independently is revision-bound).

**Two things the counts do not mean.** `prefixE`'s red count is not "the number of pins": one of its
19 rows is a **pre-existing** `SKILL↔TypedDict` row and one is the rewritten v0.1.35 arm — the rest
are the 17 new pins. The pre-existing row reds because that tree reverts the *producer* while the
declaration and SKILL.md stay current — a half-state that cannot ship, and exactly why `mutB` is
reported separately rather than folded into it. (A second such row, `remediation`, arrives only with
`mutE`, since it needs the producer's *body* reverted and not just its two edited keys.) And the
**27**-check delta in the suite's D6 total is 27 `check()` calls, not 27 pins: **17** pins, **9**
guards, **1** regression guard — the census §4.2 closes on.

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
  still makes the forbidden claim is exactly the false-green this cycle keeps finding. **The second pass
showed that one witness was not enough**: the line composes **four** operands with **two** not-carried
forms each, E1-d sampled one cell of eight, and the suite read 2008/0 while seven cells rendered a
fabricated `0`. (Those figures are the **eight-cell** scope the second pass audited; the third pass
split that scope's single `blank` form into `None` and `""`, so the census that ships is **twelve** —
§2.1.)
**E1-e** now pins all twelve *and* the **carried** spelling, so nothing is satisfied by
silently renaming an operand. The residual is the census's own: an operand *added* to the line later is
uncovered until the table is extended — bounded by §2.1's note that the cell count is syntactic
(operands × not-carried forms), so extending it is mechanical rather than a re-derivation.
- **R8 — the E1 fix adds a key to the record, and the refresh does *not* merge it.** The first cut of
  this row said `mirror_share` reaches a pre-cycle record "only if the refresh path merges it —
  measured, that path does (`rem.update(scratch["remediation"])`)". **Measured, it does not.**
  `render_dashboard.py:1611` is the only `remediation` assignment that path makes, and it writes a
  one-key dict — `{"over_ceiling": il[2] > ms.INDEX_CEILING_TOKENS}`. The comment three lines above it
  states the rule (`required`/`standing_justified`/`lever`/`candidates_surfaced`/`pruned`/`achieved_*`
  "are NOT written here … which the refresh must not invent"), and `mirror_share` is absent from that
  list only because no refresh path writes it at all: its two writers are the triage's return
  (`memory_status.py:1651`) and the seed's copy (`:3532`), both live-triage. So the dichotomy was false
  in the direction that matters — a legacy record keeps `mirror_share` **absent whether or not it is
  refreshed**, and every pre-cycle record renders through row 2's data predicate with the operand
  absent, which is the correct legacy behaviour: no mirror claim is made, and none is dropped. The
  residual risk is not the merge but the row's half-hedge: "only if … measured, that path does" reads
  as a live path, and it describes one that was never built.
- **R9 — the E2 guard is now deliberately *narrower* than its port, and parity is the cycle's banner.**
  A future reader applying "port the HTML's branch" literally could restore `!board` — which is exactly
  what the first cut did. Three things stand against it: §2.2's detail 1 states the divergence and its
  reason; the code comment at the guard names the producer path that makes the difference reachable;
  and **E2-c** reds if the condition widens back (its first fixture is a card-drawing record). The
  residual risk is not the guard but the **sentence**: "parity" appears in this cycle's title and in
  the v0.1.89 changelog, and a reader who takes it as total will find one place where it is deliberately
  refused. That refusal is the finding, not an exception to it.
- **R10 — the `mutB`/`mutE` distinction rests on one row's label.** `mutE − prefixE` is exactly
  `SKILL↔TypedDict: schema-block remediation == Remediation`, and the extractor that produced the set
  merges it with the `identity` row unless it splits after the first colon (§4.3). The counts
  distinguish them (15 vs 16), so a future re-measurement that reports only counts would lose the
  distinction silently. Mitigation: §4.3 states `len(set) == reported_count` as an assertion rather
  than a convention.

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
- **The seven E5 rows' v0.1.12 provenance tag: parked as open, and the park went stale — closed here
  rather than carried.** This entry was written from the plan and left for "a cycle that is not
  mid-flight"; measured on the frozen tree, **every clause of it is false**. It said the seven joined
  the existing nested-shape loop and so print `… == NetworkCapture (v0.1.12 full nested pin)`;
  `tests/smoke.py:1692` is a **seven**-row loop of its own whose label reads
  `v0.4.34 E5 (GUARD): … the shape the v0.1.12 loop above could not see at all, added here as a GUARD
  against future drift`, and `tests/smoke.py:1639`'s v0.1.12 loop holds **34** rows. It said the label
  is shared by **41** labels; 41 was 34+7, the arithmetic of assuming they shared the loop, and
  `grep "full nested pin"` returns the v0.1.12 loop's own label (1680) plus the comment describing the
  split (1684) and nothing else. The tree states the split itself — *"given their OWN loop so their
  label can be TRUE … Inside the v0.1.12 loop above they inherited its `(v0.1.12 full nested pin)`
  tag, which is false twice over"* — and §4.1 already recounts it in the past tense. So the defect is
  closed. **The stale entry is kept as a finding rather than deleted**, because it is this cycle's own
  class arriving in the register that records the class: a claim about the tree written from the plan
  that produced the tree.

- **F3 is recorded, not fixed — and the discriminator is a measurement, not the cost.** The demotion
  panel is a **three-row ASCII/HTML divergence**, every row the ASCII being the weaker surface:
  `windows_observed` absent → ASCII prints **`0 probative window(s)`** where the HTML prints *"Usage
  windows not captured"*; `eligible` absent → ASCII prints the **`dormant`** verdict where the HTML
  prints *"Eligibility not captured"*; `verdict` absent-or-blank → ASCII prints **nothing** where the
  HTML prints *"Demotion verdict not captured."*. The HTML panel was deliberately upgraded (its
  v0.1.68 comment mirrors the distill panel's tag+prose grammar) and the ASCII was left behind — the
  **same outlier shape as E2, which this cycle did fix**. §2.4 separates them on the **operand**, not
  on the divergence: a coerced default is a defect when it produces a claim the data **contradicts**,
  and E2's `+30 more blocked` beside `0 fleet-candidates` contradicts itself inside one render of one
  record. Measured over the archive: **0 of 46** demotion blocks omit `windows_observed`; **0 of 46**
  omit `eligible`; **0 of 46** render a `dormant` line above an eligibility-asserting verdict — the
  one co-render that would be self-contradictory, and the reason `:877`'s
  `re.sub(r"^\s*eligible\s+\d+…")` exists at all; **5 of 46** carry an absent-or-blank verdict, which
  on the **ASCII** surface renders silence, and silence asserts nothing. *(The corpus, named because
  these figures are re-derivable only from the maintainer's local store and never from the repo: every
  `~/.claude/projects/*/memory/.consolidation-log.jsonl` plus every
  `~/.claude/plugins/data/consolidate-memory/ops/*/.consolidation-log.jsonl`, deduped on
  `marker.(commit, timestamp)` — **104 distinct records, 46 of them carrying a `demotion` block**. A
  reviewer who cannot reach that store should treat these as testimony, not as a derivation; a
  reviewer who can, re-counts them.)* Two corrections to that sentence, both from re-measuring it:
  the **5 are all `absent`** — the archive holds **0** empty-string and **0** whitespace-only verdicts,
  so "absent-or-blank" named a state the archive does not contain — and **silence is a fact about one
  renderer**, since the HTML twin *names* the state. Naming the surface is not pedantry here; the two
  renderers disagree about the third shape, below. The first two rows are unreachable from the
  producer as well: `_pi_int` maps absence to a real `0`, so a seeded block always carries both keys
  *present*.
- **The reachable half has no host yet, and the obvious one was rejected by a census.** The first cut
  of this entry routed it to Cycle D's `memory_status.duty_gaps` — "an unfilled duty should be named,
  and the predicate for that already exists". **Consumers say no, twice over.** `duty_gaps` is read at
  exactly two places: `_duty_gaps_section` (`render_dashboard.py:416`, itself called only at `:616`
  inside `if judged:`), and the exit-3 gate (`:1933`). `grep -rn duty_gaps` returns **zero** hits in
  `dashboard.sections.js`, `render_html.py` or `dashboard.template.html`, so a clause there is
  structurally invisible to the archive — the very surface the 5-of-46 was measured on. That is the
  host error this plan already made once — Cycle D's spec records it in its own host-error row
  (`docs/record-duty-presence.spec.md:1172`: the host was archive-wide, because `_embed_integrity`
  calls `procedure_integrity` per archived cycle; the answer was a persist-gate-only `duty_gaps`).
  It also
  contradicts the family's own predicate: `duty_gaps` is *did the pass fill what it **SEEDED***, and
  `memory_status.py:3539-3541` seeds `windows_observed`/`eligible`/`surfaced` — **not** `verdict`,
  which `SKILL.md:1606` calls "the ONE model sentence". `docs/record-duty-presence.spec.md:452-458`
  states the rule directly: a notion that is not seeded-then-unfilled is *"a far-side row, not a
  `duty_gaps` clause"*. So the remedy is **unassigned**, recorded with both rejections so the next
  cycle starts from the census rather than from the intuition that naming a duty belongs to the duty
  predicate.
- **A third verdict state is not a divergence but a shared defect, and the sentence above was false
  about it.** Probed on the frozen tree: `{"verdict": "   "}` renders `    verdict:    ` in ASCII — a
  dangling label with nothing after it — where *absent* and `""` both render no line at all. And the
  blank is not the only route: a verdict consisting **only** of the `eligible N` prefix that `:877`'s
  `sub` later strips — `"eligible 3"`, `"eligible 0"`, even `"  eligible   7  "` — passes `if _dv:`
  and renders `verdict:` with nothing after it too, so the presence test is narrower than the output
  it guards and this entry's own account of the mechanism was (`a-guards-label-is-not-its-predicate`,
  one level in). The HTML twin's `if(dvd)` takes the truthy path for the same input, so a blank verdict **suppresses the
  very fallback** ("Demotion verdict not captured.") written to name that state. Both surfaces key
  presence on **truthiness**, which is the test E3 spent this cycle replacing. `:874-875`'s
  `_clean(demo.get("verdict", ""))` followed by `if _dv:` is a **local re-spelling of the blank test**,
  and `_recorded`'s docstring says the blank test is `memory_status._duty_blank` *"not a local
  re-spelling: … A second copy is how the periphery-parity defects happened"* — while `_duty_blank`
  (`memory_status.py:4135-4144`) already answers this case correctly (`not v.strip()`). This is E3's
  own class at a site E3's census could not match: the matcher takes `dict.get` with a truthy
  **default**, and this site takes a falsy default and then guards with an explicit `if`. **Recorded
  rather than fixed, on the prevalence and not on the cost.** Measured: **0 of 46** — reachable by
  authorship (a model-emitted `verdict`, the same class as the hand-authored fixture block below) but
  never yet emitted — and the fix is one token per surface in two files, the second of which
  (`dashboard.sections.js`) is embedded **verbatim** in the committed `docs/previews/nocturne/index.html`
  (299,042 bytes; the whole JS file is a substring of it), so the edit is neither behaviour-identical nor free.
  It is the sibling of the `_num(k, 0)` note below: same census, same blind spot, one idiom over. It
  is also the one entry in this section whose disposition the maintainer may want to reverse at merge
  — the fix is small and the state is reachable — which is why it is stated rather than buried.
- **The `lever` header fabricates a routing label out of an absent one.** `:899`'s
  `str(rem.get('lever', '')).upper()` is a **coerced default**: `lever=""` renders a dangling
  `· lever `, and `lever=None` renders `· lever NONE` — a claim the record's own data contradicts,
  which is §2.4's rule sharpened (a coerced default is a defect only when it produces a claim the
  data contradicts), and this one does. The blank-aware form is one expression, and `_recorded`
  (`:193-205`) already answers exactly this case. **Recorded rather than fixed, on the prevalence.**
  Measured over the archive corpus: **39** remediation blocks, **9** of them reaching the `:899` arm,
  **9 of 9 carrying a present `lever`** — 0 of 9 here. There is no second witness to borrow: the
  archive's 46 `demotion` blocks are a **disjoint population**, and `Demotion` declares no `lever` key
  at all (`memory_status.py`), so the zero recorded for them elsewhere in this section is the
  whitespace-verdict predicate's — a different predicate, on a set that *cannot* carry this field. A
  borrowed denominator is not corroboration.
  Reachable by authorship, never yet authored. *(Third-pass review, finding N1.)*
- **A third-pass review finding the probe REFUTES, recorded so it is not re-filed.** The report was
  that E1-g's first conjunct (`"index: not recorded" in _e_g_blank`, `smoke.py:18625`) is satisfied by
  the *pending* arm's own `"projected index: not recorded"` (`:927`) rather than by the `:945` string
  it names, leaving only conjunct 3 to discriminate. The containment is real as a fact about the two
  literals, but the fixture never reaches `:927`: `_e_g_blank` carries `pruned: 0`, which `_recorded`
  reads as a MEASUREMENT, so `pending` is False and the branch is not taken. Probed on the frozen
  tree, the render reads `index: not recorded (projected: not recorded)` — the pending spelling is
  **absent**, and conjunct 1 is satisfied by the string it names. **Refuted, not applied** — verified
  before it was acted on, which is the standing rule for a peer report. *(Third-pass review,
  finding N3. Its siblings H1 and N2 were verified true and are fixed in this revision.)*
- **F3's unreachable rows have a visible witness, and it is uncontradicted — which is the whole
  point.** `tests/dashboard_fixture.py:121` is a hand-authored demotion block carrying `eligible: 0`
  and a verdict but **no** `windows_observed`; it is the record behind the committed `docs/previews/`,
  so the **state** that row renders from is not hypothetical — it is committed, nine times over (the
  record plus eight `history[]` entries). *(The ASCII row itself is not a committed artifact: the
  previews embed the record and render it through the **HTML** twin, which is the surface that handles
  the absence correctly.)* It is uncontradicted: the same
  record's verdict reads *"none: all indexed facts retain a useful recall cue"*, so `dormant` is the
  right branch and the synthesized `0` agrees with it. **Uncontradicted, therefore outside §2.4's
  defect class** — recorded with its witness, so a future reader can re-open it on a counterexample
  rather than on a principle.
- **The E3 census's matcher cannot see `_num(k, 0)`.** The census is syntactically derived and its
  matcher is `dict.get` with a truthy default; `_num(demo.get("eligible", 0))` spells the same
  absent-vs-recorded ambiguity through a **call's** default and is invisible to it. Population
  measured: **27** literal-default `_num(…)` sites in `render_dashboard.py`, **16** of them assigning
  to a name. Almost all are harmless — a count that is absent *is* zero for display — so the class is
  much narrower than its size suggests, which is why it is recorded rather than enumerated: the defect
  is not "the default exists" but "the default **selects a claim**", and the demotion panel is the one
  site where that measurement was taken. `gate-coverage-is-its-match-set`, one idiom over.

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
second guard spelling; the table is **twelve** rows. *(This read "ten" until revision 5 counted the
committed revision-4 table: twelve rows — E1-a…d, E2-a/b, E3-a…d, E4-a/b. A ledger figure is prose
like any other, and this one had never been counted; see revision 5 below.)* *(Revision 6 measured all
three of the claims above: the `pruned>0` half **survives**, and more strongly, since the asserted pair
is GREEN there under either reading; the `achieved_index` half is real for E1-b but *"kills **both**
pins"* is **false of E1-c**; and `reaches_budget`'s "absent or `True`" is not a constraint at all —
the pair is RED at `False` too. §4.1 carries the numbers.)*

*Process:* a second enforcement site (`beta_checks.py`'s `CHK-REM-RESOLVED`) is recorded in §4.2. And
the register's claim that one reviewer *"independently reproduced"* §1.3's table was **false** — it
reproduced the pattern, not the measurement. **Two reviewers agreeing is not two measurements when
they share the matcher**, which is `gate-coverage-is-its-match-set` one level up; that mis-credit is
what raised confidence in a wrong number.

**Revision 5** — **a second adversarial pass, aimed at revision 4's repairs rather than at the pre-fix
code.** Two findings, both the cycle's subject inside a fix (§2.6); both repaired in **code**, then
pinned, then re-measured.

- **E1's fix closed 1 of 8 cells.** The `↓` line composes four operands, each with an **absent** and a
  **blank** not-carried form, and `_num` maps both to `0.0`. The first cut asked
  `"candidates_surfaced" not in rem` — one operand, one form, one site. Fixed by `_recorded`
  (`key in m and not ms._duty_blank(m[key])`, reusing Cycle D's canonical blank predicate rather than
  re-spelling it), applied per operand in the panel and in the verdict arm. **E1-e** pinned all
  **eight** cells at the census as it then stood — §2.1 grew it to twelve in the third pass, and the
  label now reads twelve — *and* the carried spelling: the latter because without it a **renamed**
  operand would satisfy every silent row.
- **E2's fix carried the JS's `!board` guard across, and it guards a different claim.** In the JS the
  branch **assigns** `board` (the guard protects the cards) and the count is stated in a `reg-counts`
  header; the ASCII branch **appends** and has no header. Carried over as
  `len(_fleet) + _shown_b == 0`, it left the false tail on the shape `sync_global`'s persist rule
  builds: one persisted fleet row beside twenty counted generic-cli rows (F1, §2.2/§3.2). Guard is now
  `_shown_b == 0`; **E2-c** pins both directions, including a non-vacuity arm so the tail cannot be
  "fixed" by deletion.
- **F1's prevalence is 0 of 104, and it is reported.** The state E2-c newly covers does **not** occur in
  the archive; the 27 records that do occur are the empty-candidates form the **first cut already
  fixed**. The fix therefore rests on the **condition**, not on a count — argued from the persist rule,
  with the 0 printed rather than omitted (§3.2). *(Contrast Cycle D, which **dropped** a clause on a
  0/99 measurement: that clause was **unsound**, not merely unobserved.)*
- **A green suite was the evidence, not a comfort.** **2008 / 0** on the revision carrying both defects
  (`mutD` in §4.3) — E1-d sampled one operand in one form, and both E2 fixtures carried no fleet row.
  This is `a-pins-coverage-is-the-values-and-path-it-samples`: sample the values a fix moves **away
  from**.
- **The re-measurement caught a build error, not just a count.** Revision 4's `prefixE` row was built
  by copying `mutB`'s *edited* `memory_status.py` instead of the parent's, so the "union" tree was the
  union by construction and never removed `mirror_share`. §4.3 now defines every tree by its **edit
  set** — `diff -rq` reports which **files** differ, never which **edits**, so a wrongly-built tree
  inventories exactly as intended. `mutE` (the true union + the declaration removal) measures
  **1994 / 16**, and its passing count equals the number revision 4 recorded for `prefixE`, which is
  what identifies the old tree as the wholesale construction.
- **Two instrument failures, opposite in direction.** The red list was first extracted with a
  one-space indent (matching nothing — an empty list that reads as "no reds") and then with
  `sed 's/:.*//'` (**throwing away** the distinction between the two `SKILL↔TypedDict` rows, so
  `mutE` came back as 15 for a tree that printed 16). Both were caught only because the printed count
  and the extracted set disagreed; §4.3 now states that a set is unverified unless
  `len(set) == reported_count`.
- **The ledger's own figures were audited, and one was wrong.** Revision 4's entry said *"the table is
  ten"*; the committed revision-4 table has **twelve** rows. Corrected in place. That is
  `audit-the-diffs-prose` inside the register that records `audit-the-diffs-prose` — the same shape
  §3.6 names, surviving one revision longer than the figures it had already caught.
- **Every tree was rebuilt and fingerprinted by EDIT SET, not by name.** The `git worktree add`
  prohibition holds; the check that replaces it is an inventory (renderer and `memory_status.py`
  hashes against the two reference revisions, plus a direct assertion per surgical edit). It earned
  its keep: the second pass's `mutA` lived in a directory called `mutC`, and the first pass's stale
  `/tmp/mutA` reports the **same** `1998 passed` as the correct tree from a **different harness** —
  two fewer checks and two fewer reds canceling exactly. **Counts are not fingerprints.**

**Revision 6** — **a third pass, over revision 5's *record* rather than over its code.** Four lenses
were run against the committed revision: the document's own prose, its pins, the **consumers** of the
predicates it touches, and its logic. **Every defect revision 5 fixed survived** — no shipped repair
was reopened — and that is this revision's headline, because what did **not** survive was the
**accounting of them**: the findings below are claims about claims, and **not one of them moved a
single check's verdict** — the suite was green, at the same count, on the revision carrying all of
them. §3.6's class, arriving for the third **round in which this document's own register was caught in
it** — after §1.3's "twice" gloss (revision 3) and this ledger's *ten* against twelve (revision 5) —
now inside the register that records it (`audit-the-diffs-prose`). **The criterion is the narrow one
this document's preamble now states** (*a count contradicted by the enumeration printed beside it*), because the
broad reading does not exclude revision 4; revision **7** is that series' **fourth** member. *(Finding
4 of the third-pass review refuted this sentence as first written and the criterion, not the ordinal,
was corrected.)*

- **A guard's printed label still carried a mechanism its own comment had already falsified.** The
  E3-d label said an untruncated name *"collapses that row's padding to 0 and shears the table"* —
  three lines above a comment that had already corrected exactly that account. `pad` is
  `max(0, namew - disp_w(nm))` and is **0 on the fixed tree too**, so what the defect moves is the
  row's **width** (26 columns before `always` truncated, 36 whole — apart by the excess), not its
  padding. Re-measured independently in **two isolated processes** (§4.1), then fixed
  **label-only** — which is what makes its verdict-neutrality *checkable* rather than asserted: the
  red sets are identical before and after. The corrected label deliberately does **not** quote the
  withdrawn phrase contiguously; in a repository whose thesis is that printed labels get quoted as
  facts, a label that reproduces a falsified sentence in order to refute it is a grep hazard for the
  next reader, so it describes the correction and points at the note.
- **A count and its list disagreed inside one sentence.** §3.4 said the `phase0..phase5` literal is
  *"spelled in two"* files and then listed **three** readers, while a bare `grep -rl` returns
  **five** — the other two being `docs/previews/nocturne/{sample.json,index.html}`, a committed
  **render** of the fixture record and therefore data, not a source spelling. Both corrected, with the
  scoping stated: the count is of **source** spellings, and the disagreement between the count and the
  list is now named rather than silent. **§4.1's line arithmetic is likewise stated rather than
  counted** — each render is **17 lines**, exactly one raw line differs (the header), and after
  normalization the equality holds over **all seventeen**, because `_re34.sub` REPLACES the label in
  place rather than removing the line. The "remainder" framing was carried across six revisions and
  the digit corrected twice (fifteen → sixteen → here) before the framing itself was measured: the
  number had been re-derived from a form that was never the comparison the pin makes.
- **F2 is disposed as *not* a defect, and the invariant that separates it is now §2.1's.** The hint
  map in `memory_status.py` keys a claim on `lever`, which reads like this cycle's defect — but
  `_remediation_section` is reached only from `ctx.get("remediation")`, the dict `remediation_triage`
  returned, where `lever`, `candidates` and `mirror_share` are written by **one expression in one
  run**. That is the separating rule: **a surface may key a claim on a label only when the label and
  the operands behind it are written by one expression, in one run.** `render_dashboard` is *handed*
  records, and the archive measures the difference — **23 of 39** persisted remediation blocks carry
  `lever`, **0** carry `mirror_share`. *(Denominator corrected in revision 7 — see §2.1's note.)* The label without its operand is not an edge case there; it is
  every record that exists. So the renderer is the case, the producer is not, and the scope paragraph
  in §2.1 states it rather than leaving the next reader to re-derive it.
- **The pin census had a limit case, and nothing sampled it.** Every row of E1-e routes around the
  `pending Phase 5` branch **by construction** — each row's siblings deliberately carry `pruned` or
  `achieved_index` — so the one state the pre-pass seed actually produces had no sibling here that
  sampled it, and no other check **read** the line it renders: a refactor that dropped the branch
  would have left it green. *(Revision 7 corrects this sentence. It read "was rendered by this suite
  **nowhere else**", which is false — `_ceilRecB` and the `over_ceiling: False` fixture are both
  pre-pass records and both render the verdict; what no check does is assert it. The gap is the
  missing assertion, not a missing render. Finding H1, probed in §4.3.)* A fifth arm
  inside the existing check pins it in the same population+verdict shape as the rows, and adds **no**
  new `check()`, so the census constant does not move. Injection-verified: `pending = not
  _recorded(rem, "achieved_index")` reds **two** checks for **two different reasons** — E1-e's new arm,
  and E1-g, whose label names exactly this dependency. `a-complete-guard-inverts-its-question` on the
  pin side: the arm asserts the *verdict*, because the branch's absence is what a deletion produces.
- **A third measurement, and the same discipline caught the same class of error.** `tests/smoke.py`
  was edited **while rev7 was running**, moving a triple member mid-run exactly as this cycle's
  earlier `render_dashboard.py` edit did — so **rev7 is a prediction, not a measurement**, and §4.3
  records **rev8**. The trees were not rebuilt: rev8 is a **two-file swap** on rev7's preserved trees
  (the harness, and the comment-only renderer), with all **ten** mutant renderer hashes asserted
  **equal** to rev7's. The mutant inventory is the identity, so swapping the harness cannot silently
  alter a mutant — and the swap is what makes rev8 a measurement of the *frozen* tree while every
  mutation definition stays bit-for-bit the one rev7 and rev6 measured.

**This revision changes two shipped surfaces and no shipped behaviour.** The surfaces are the E3-d
label and `E1-e`'s own label — both strings the suite prints, neither read by anything. Everything
else is this document, §2.1's scope paragraph, and one added arm **inside** an existing pin — a
coverage repair for a branch that nothing in the suite was sampling, which is why it moves no check
count. *(Three counts were corrected in this pass, all of the class this revision records. Two were in
the preamble: it said "two pins gain coverage" where the ledger has **one** coverage bullet, and "the
scope paragraphs in §2.1" where §2.1 has **one**. The third is in this closing statement itself, which
said "one shipped surface" where §4.3 records **two** rewritten labels — E1-e's own and E3-d's. A
count disagreeing with the list beneath it is the **second** of the three findings this revision
records — *three of that entry's **five** bullets are findings; the other two are the F2
**disposition** and the third-measurement note, which is why "the three" and a five-bullet entry are
both correct. (Third-pass review, finding 3, reported the entry as printing four bullets and was
**wrong**; verified here, and the check was one command.)* — so each was corrected
rather than left standing in the register that announces the audit, and the prose was then swept
numeral by numeral rather than patched a third time.)*

**Revision 7** — **a fourth pass, over revision 6's own *prose*.** Three lenses were run against the
committed revision — its prose, its pins, and the consumers of the predicates it touches — and every
finding that survived verification shares one surface: **the cycle's own new sentences**, in the
harness and in this document, each asserting something the code or the trees do not do. Not one moved
a check, and each was found by **executing the claim** rather than by re-reading it.

- **H1 — a comment claimed a coverage hole that is a missing ASSERTION, not a missing render.** The
  arm's comment said the pre-pass seed *"is rendered by this suite nowhere else"*. Probed, it is
  rendered twice more — `smoke.py:4451`'s `_ceilRecB`, and the `over_ceiling: False` fixture rendered
  at `:4462` — and both print `pruned/achieved pending Phase 5`. What no other check does is **read**
  the line, which is exactly what the two injections measure, and they still do. The clause is
  corrected to say so, and §4.3 now quotes only the two clauses the injections test.
- **N2 — a fixture's stated rationale named an operand its fixture cannot discriminate.** E2-a's
  second fixture was said to catch the clamp (*"unclamped, the second fixture prints `-20
  single-node`"*). It cannot: `max(0, 10-30)` and `10-30` **both fail `> 0`**, so the two render
  identically — and the renderer's own site already said so. Two comments in one frozen revision
  contradicted each other, and **the wrong one was in the pin's rationale.** What the fixture does
  discriminate is the emission test — and the check's own *label* had that right while the comment
  eight lines above it had it wrong. Corrected in the comment, in §2.2's bullet 2, and in the fixture
  list; **this document carried the same false claim** and had to be corrected with it.
- **The §4.3 tree table's `memory_status.py` row was false, and that table is the reproduction
  recipe.** It read *"all thirteen trees"* at one hash. Measured on the preserved trees, **nine**
  carry `51f460cf8aad3d18` and **four are `memory_status` mutants** — `mutB`/`prefixE` at
  `16189d1e96812824`, `mutE` at `f3546bdd01014194` (the hash this document *already* names at §4.1 as
  `1d97f54`'s pre-fix partner), `R1h` at `f7456e94f9b33aee` — identically in `rev6`, `rev7` and
  `rev9`, so nothing moved mid-run and the row was **wrong when it was written**. It was inherited
  from the batch's own prediction file and never checked against the trees, while every other cell in
  that table *was* hash-verified. The instrument that catches a moved member is a hash; here the hash
  was replaced by an **inherited assumption** for exactly the row where four members had moved. A
  reader rebuilding the thirteen trees from that table would have put the frozen `memory_status.py`
  into four mutants and measured four different verdicts.
- **Two findings are recorded rather than fixed, and one is refuted.** The `lever` header's coerced
  default (**0 of 9** blocks reaching its arm) and the whitespace demotion verdict (**0 of 46**) are
  §6 entries carrying their measurements and their reversal conditions. The third — that E1-g's first
  conjunct is satisfied by the *pending* arm's text — **did not survive its own probe**: `_e_g_blank`
  carries `pruned: 0`, which `_recorded` reads as a MEASUREMENT, so the fixture never reaches the
  pending arm and the conjunct is satisfied by the string it names. Refuted, not applied, and
  recorded in §6 so it is not re-filed.
- **The seventh measurement.** `tests/smoke.py` **is** a triple member, so the two comment
  corrections moved the harness and the batch was re-run as **`rev9`** — `cp -a rev8 rev9` plus a
  **two-file overlay**, the copy being what asserts the twelve mutation definitions did not change.
  The identity is asserted over the **triple only**: `docs/` is excluded, on the measurement that
  nothing in the suite reads it (every `glob` in `smoke.py` runs over a temp tree, and this document's
  name appears once, in a comment) — which is also what lets this revision be written **into** the
  measured generation without editing the thing being measured. **All thirteen counts reproduce the
  prediction, all thirteen red sets are byte-identical to `rev8`'s, and
  `len(set(reds)) == reported_failed_count` holds for each** — so the comment-only delta is
  confirmed to be comment-only by measurement rather than by argument. The generation is **bound to
  `bb5275764e035a3b8952975f6f2d69452e2d8b8e`**, the commit that froze the triple before this document
  was written: the trees carry content that was uncommitted when they ran, so a document recording
  their hashes cannot also be the thing those hashes describe. The binding is proven by recovery —
  `git archive` the commit and re-hash the four members out of the extracted tree — not by inspection.
- **The branch-deletion pair was re-measured too, and the instrument has an asymmetry.** Both
  injections were rebuilt against `rev9`'s harness and reproduce (`2015 / 1`, red `E1-e`; `2016 / 0`,
  green). The asymmetry: `len(set(reds)) == reported_failed_count` is what makes a red count
  **attributable**, and on a green run the red set is empty, so it holds identically for every green
  outcome and certifies nothing. The green run's evidence is its count and the prediction it matched;
  the assertion contributes only by not failing. Recorded in §4.3 because a reader who took
  `[set==reported: 0]` as a positive result would be trusting an instrument that cannot fail in that
  direction — **the same shape as every finding in this entry**, arriving one level up, in the
  apparatus rather than in an artifact.

**No shipped behaviour changes in this revision.** Every edit is a comment, a paragraph, or a table
cell. The one code-adjacent change is that `tests/smoke.py`'s content moved — which is why the
measurement was re-taken rather than argued: the harness is a member of the triple, and the whole
point of §4.3's discipline is that a member's content is a hash, not a reassurance.

**Revision 8** — **a fifth pass, over this cycle's own pre-fix narratives.** The fourth pass audited
revision 6's prose for claims about the *code*; this one asked the narrower and sharper question its
finding 7 implied: **does each label's story about the pre-fix revision name a counterfactual that
revision can actually produce?** Every answer was obtained by driving `1d97f54`'s renderer — extracted
with `git archive 1d97f54 plugins/consolidate-memory/scripts | tar -x`, never a linked worktree — with
the fixture the label itself names. **Eight** labels were reached, and on that contracted scope five
survived and three did not, all three sharing one shape: **a number or a string that was true of some
other revision, stated as true of `Pre-fix`.** The contraction was itself the defect, found by the
lead's own fourth lens: the selection was the case-sensitive test `"Pre-fix" in label`, and the file
spells the counterfactual both ways — so **ten** of the eighteen labels in the class were never
executed at all, **all three GUARDs among them**. Executing all eighteen against the revision each
names leaves **seventeen holding and one false** (E2-b, below).

- **E1-e's label carried a count of a census that no longer exists.** "Pre-fix (and on the first cut
  of E1) seven of the eight cells rendered a number the record never carried." The census is **twelve**
  cells: the third pass split the eight-cell scope's single `blank` form into `None` and `""`, growing
  four operands × two forms to × three, and the digit was never moved. Measured against the shipped
  twelve, the two revisions the label conflated are not alike at all: **`1d97f54` leaves 0 of 12
  green** — every cell fabricates — while **`6368288` leaves exactly 1**, `candidates_surfaced`
  omitted, which is the seven-of-eight's real origin on the eight-cell scope. The parenthesis
  generalized one revision's result to both, and it generalized it in the direction that *understates*
  the defect. Three other sites carried the same stale eight — §2.1's "eight cells", §3.6's "one of
  eight … now pins all eight", and §4's pin-table cell "RED (1 of 8 cells green)" — and are corrected
  with it, on the measurement rather than by arithmetic.
- **E3-c's label quoted a string the renderer never emits.** "Pre-fix it rendered `'→  @ '`." It
  rendered `'→ @'`: `_ui.wrap` collapses the whitespace run, so the blank operands leave **no** gap,
  and the pre-fix render differs from the fixed one only by the two `?`. That makes the `?` the sole
  mark the defect leaves — a fact the corrected label now states, because a reader comparing the two
  renders by spacing would find them identical and conclude the pin was decorative.
- **E1-c's label was the fourth pass's finding 7**, corrected earlier in this pass and verified here
  by the same method: the pre-fix ⚠ is real, but the reassuring `justified — nothing safely prunable`
  string is reachable only through `lever="justify"`, which is not that fixture.

**The five that held, each by execution:** E1-a's two clauses for one state (the ⚠ and the remedy both
render on `1d97f54` for the sanctioned fixture), E1-b's lever-swapped verdict, E1-d's collapsed
absent-vs-zero pair (**the two renders are byte-identical** — "both collapsed" is exact, not
suggestive), E1-f's remedy beside a success (a different fixture from E1-a's, and the distinction
matters: `achieved_index = 900` is *under* the budget, so the ✓ renders and the ⚠ does not), and
E4-a's `domain_lifecycle`, emitted unconditionally by `getattr(ctx, "domain_lifecycle", "active")` and
declared nowhere.

**The eighth measurement.** Three of those corrections are labels, and `tests/smoke.py` **is** a triple
member, so the batch was re-taken as **`rev10`** (`cp -a rev9 rev10` plus the two-file overlay). All
thirteen counts and all thirteen red sets reproduce `rev9`, and both injections reproduce (`2015 / 1`,
red `E1-e`; `2016 / 0`, green). The delta assertion is **structural this time**: `check()`'s first
argument is the label, so an AST pass replaced it with a placeholder and dumped the module — 1793 call
sites, exactly three labels differing, everything else byte-identical. Both the counts and the
reasoning are in §4.3.

**Amending the freeze, and re-proving it.** The commit that first froze this triple carried an
**unmeasured count in its message** — "eighteen of the twenty" for a sweep that reached eight of the
eighteen labels carrying such a claim, the other nineteen of the file's twenty-eight capital `Pre-fix`
occurrences belonging to earlier cycles and never read.
That is this cycle's defect class arriving in the one artifact nobody diffs, so the commit was amended.
The tree is untouched by an amendment and the four hashes therefore *should* be unchanged — which is
the word this document does not accept — so the recovery proof was **re-run** against the new commit
and returns the same four values. The binding names
**`7188c1a2cff1c51f59307ddb717cb54910a8783d`**. A commit message is not a triple member, and that is
precisely why it needed its own measurement.

**No shipped behaviour changes in this revision.** Every edit is a label, a comment, or a paragraph of
this document. The one code-adjacent change is again that `tests/smoke.py`'s content moved — re-taken
rather than argued, for the same reason as the seventh: the harness is a member of the triple, and a
member's content is a hash.

**Revision 9** — **a sixth pass: the peer review adjudicated, and the audit's own selection audited.**
Three lenses (prose, pins, consumers) were run over revision 8's committed revision, and every finding
was re-measured here rather than applied — a peer finding is a hypothesis, and two of the six did not
survive contact with the tree.

- **The sweep's matcher was narrower than its claim, and the claim was the contract.** The selection
  was the case-sensitive test `"Pre-fix" in label`; the file spells the counterfactual both ways.
  Enumerated structurally from the diff instead of matched, **eighteen** of this branch's twenty-one
  added labels carry a claim about a non-HEAD revision and the matcher reached **eight**. All three
  GUARDs sit among the ten it never read — not a coincidence: a guard's entire justification *is* a
  counterfactual. `:309` and E2-a spell theirs in neither case, so a case-insensitive matcher would
  still have missed them; the only honest match set for this class is the diff, because `git diff`
  compares trees and cannot miss a spelling.
- **Executing all eighteen: seventeen hold, one is false.** E2-b quoted `'30 blocked'` as the pre-fix
  render; `1d97f54` prints `'… +30 more blocked'`, and `30 blocked` is the fixed form's own spelling.
  E3-d's claim is true but its stated derivation was not — the prose described `_clean(...)[:18] or
  "?"` (measures GREEN, width 26) where the code block showed `_clean(...) or "?"[:18]` (measures RED,
  width 36). The claim and the measurement both stand; the sentence was the defect, in the comment and
  in the label a failure prints (`weakest-enforcement-site-wins`, inside one check).
- **The contracted figure propagated through four sites, each citing the previous as evidence.**
  `:7`, two revision-8 entries, and the status body all rest on one case-sensitive census: capital
  `Pre-fix` is **28 of the file's 210 case-insensitive spellings**, and **nineteen** of those 28
  predate this branch — measured on the diff, not on the file. The denominator the audit quotes is the
  denominator it read: `gate-coverage-is-its-match-set` with the audit as its own subject.
- **Two findings were adjudicated rather than applied.** The `lever` header
  (`render_dashboard.py:899`) is a live coerced default, already recorded at §6 with its prevalence
  measured — *reachable by authorship, never yet authored* — so it **stays recorded**: this document
  reserves that reversal to the merge, and a code edit here would move a member of the triple for a
  state the corpus has never produced. And the demotion-corpus zero borrowed at §6 was measured on a
  population that **cannot** carry the field (`Demotion` declares no `lever` key), so it was never a
  second witness and no longer reads as one.

**No shipped behaviour changes in this revision either.** Every edit is a label, a comment, or a
paragraph of this document. `tests/smoke.py`'s content moved — `eeeafdcd908cd186` → `38d4835486d0db41`
— and the harness is a member of the triple, so the measurement was re-taken rather than argued. The
thirteen trees reproduce the eighth revision **exactly**: every red set byte-identical tree-for-tree,
`|set| == reported` on all thirteen, total red **70**. Both injections were re-run on the new harness
and returned as predicted: the branch-deletion reds **E1-e alone** (2015/1, set==reported), and the
*same injected tree* is **GREEN** on the pre-arm harness (2016/0). The arm bites, and nothing else
catches it. **(Revision 10 corrects this sentence.** It claimed the E1-e label was "now stated without
the half that was not" — and the label, the comment above it, and §4.1 all still carried the false half:
"a refactor dropping the branch would leave the suite green," which is true only of the suite *without*
the arm revision 6 added — the *same commit*, `bb52757`, that wrote the clause down. That it was
refuted by its own ledger entry from the start is the sharper version: there was never a revision on
which the clause was true of the suite as shipped. The removal was asserted one revision before it
happened, in the
ledger entry whose subject is a claim that outran its referent — the cycle's thesis, committed by the
cycle's own record of it. Corrected in revision 10, on all three surfaces.**)**

---

## Revision 10 — the seventh pass: the code review, adjudicated

Five review lenses ran against the frozen branch (`cr-impl`, `cr-pins`, `cr-consumers`, `cr-gates`,
`rev-prose`). Every finding was reproduced before it was acted on; a peer finding is a hypothesis, and
three did not survive contact. The ones that did are below, with the reason each was **fixed** or
**recorded** — because that split is the judgment this pass had to make, not a scheduling choice.

### Fixed: the threshold is a not-carried operand, and no census of printed operands could see it

`.get("budget_tokens", ms.INDEX_TOKEN_BUDGET)` names the right VALUE and keeps the wrong SHAPE. The
default fires only on **absent**, so a `budget_tokens` present and blank fell *past* the constant into
`_num(None)`/`_num("")` → `0.0`, and the lean test became `0 < achieved_index <= 0`. Probed on the
frozen renderer at `achieved_index: 1300` — the value the pin's own fixture carries, so this table is
reproducible from `tests/smoke.py` rather than from this sentence (§4's E1-i row states the same index;
an earlier draft of this ledger entry carried `1400`, which was the whole reason to write the index
down: a reader who re-ran it at `1400` would have got the same verdict and never learned the figure
described a different probe than the one that shipped) — against the real `INDEX_TOKEN_BUDGET` of 1500:

| how the threshold failed to arrive | verdict |
| --- | --- |
| `budget` block absent | ✓ gate resolved by rebuild-lean |
| `budget_tokens` key absent | ✓ gate resolved by rebuild-lean |
| key present, `None` | **⚠ gate fired but not acted on** |
| key present, `""` | **⚠ gate fired but not acted on** |
| key present, 1500 | ✓ gate resolved by rebuild-lean |

**Byte-identical numbers, opposite verdicts, decided only by HOW the threshold failed to be carried** —
the cycle's thesis, on the line whose own comment claimed the not-carried forms were closed. The census
in §3.6 could not reach it *structurally*: it samples four operands **printed** on the `↓` line, and the
threshold is only ever compared against. Fixed with `_recorded`, the idiom the same block already uses
two lines up, and pinned by **E1-i2** — the same fixture as E1-i with only the blank key added, so the
two are a matched pair one record apart. E1-i2 is **red on the unfixed renderer** (measured: 2015/2 with
the D6 constant stale, the second red being D6 itself) and green after. E1-i's own comment names the
reason it hid: its fixture supplies `budget_tokens: 1200` *explicitly* — the value the fallback literal
used — so no fixture could see the fallback disagree with itself.

### Fixed: the E2-b rule is three-operand, and its own prose denied one

`render_dashboard.py:1271-1277` read *"Keyed on `_n_blocked` (the record), **NOT** on `_anch` … (`_anch`
is in scope here and looks like the natural operand; it is not the right one.)"* and the condition
immediately below it reads `not _cands and not _anch and _n_blocked <= 0`. The check label carried the
same two-operand account. **The prose was the false surface, not the code.** All three sites now state
the rule that ships and what each operand is for. *(**Revision 11: only two of the three were edited
here** — the comment above the check in `tests/smoke.py` was not, and carried the same false account one
revision longer. It is repaired in revision 11; this sentence was true of two sites when written.)*
**Two** of the three conjuncts are unwitnessed and are labelled as such rather than left looking
defended: measured, deleting `and not _anch` leaves the suite green while changing the render for a
record carrying anchors, no blocked rows and no candidates, and deleting `and not _cands` leaves it green
while changing the render for candidates beside an explicit `n_blocked: 0`. Only `_n_blocked <= 0` is
defended — its deletion reds E2-b.

### Fixed: the 324-state sweep fixes a fifth dimension while reading as a universal

§1.2 diagnoses the 12-cell grid for *"silently fix[ing] a third dimension to one value … exactly the
defect this cycle exists to delete"* — and then answers it with a cross-product whose axis list contains
no `mirror_share`, and reads out *"at most one verdict line per state, across all 324"*. `:981` emits the
mirror line from an `if` with no guard against any other branch, so it co-renders by design (`:977` says
so). The claim is now **scoped to the domain that was measured**. The code review's own extension of the
axis is recorded as *its* measurement on *its* definition of a verdict line: this revision's
reconstruction of that operand disagreed with the sheet's zero at an absent share, and a disagreement
about a count is evidence about the count's definition, not about the number.

### Fixed: three prose sites and a ledger claimed a removal that had not happened

The E1-e label, the comment above it, and §4.1 all carried *"a refactor dropping the branch would leave
the suite green"* — true of the suite **without** the arm, false of the suite as shipped, from revision
**6** (the revision that added the arm — the *same* commit, `bb52757`, that wrote the clause down)
through revision 9. The Revision 9 ledger then claimed the false half
was "now stated without".
All four are corrected, and the ledger entry is **annotated rather than rewritten**, following
`ecab87f`'s own convention: a ledger records what a revision did, so a claim that was false *when
written* gets marked, not silently reconciled. Three smaller repairs ride the same pass: the pointer to
§4.2 that §4.1's E1-e paragraph carried (cited as `:1265`, which resolves to no state of this file — it
lived at `:1251` in the frozen commit; the correction it names is the E5 rows' provenance tag, not the
arm's label), "spliced `or "?"` in
**AFTER** the subscript" (the splice lands *before* the `[:18]`, so the sentence said the opposite of the
defect — on the label, in the third drafting of that sentence), and the frozen commit message's "the 20
outside §E1–E4", which enumerates to **19 outside / 9 inside**.

### Fixed: two figures in this pass's own record, found by re-reading it against the trees

Neither came from a review lens. Both were found reading this ledger against the artifacts it describes,
and both are one shape: **a figure whose referent had moved while the figure stayed put.**

**The propagation list mispaired two names with two numbers.** It read *"mutA/mutD/mutE/prefixE are
whole-region reverts (202/202/202/115 changed lines)"*. The multiset `202/202/202/115` is **correct**;
only the list ORDER was broken. Measured on rev11: `mutA 202 · mutE 202 · prefixE 202`, and `mutD 115`.
Read positionally — the only reading that sentence offers — it yields `mutD = 202` and `prefixE = 115`,
and the reader most likely to do it is the one asking *"did `prefixE` receive the fix?"*: they would read
115, conclude it was not a whole-region revert, and find this very propagation defective. Repaired by
naming each tree **with its own delta**, so recovering a fact no longer requires pairing two lists by
position. `audit-the-diffs-prose`, committed by the ledger that records the audit.

**The probe table's index.** The entry above stated `achieved_index: 1400`. The pin's fixture carries
`1300`, `tests/smoke.py`'s own comment beside that fixture says `1300`, and §4's E1-i row says `1300`.
This ledger was the lone outlier, and it is the surface least able to be re-derived. Corrected to the
figure a reader can recover **from the artifact rather than from the prose** — the same priority that
makes a pin's exact substring worth more than a verdict scan: a number carried in prose is testimony,
and a number carried in the fixture is reproducible.

**Two checks that came back "sound", recorded so they are not re-flagged.** `render_dashboard.py`'s E3
comment is **not** duplicated — a `sed` with two overlapping ranges printed line 299 twice and invented
the duplication. And E3-d's *"spliced `or "?"` in BEFORE the subscript"* is **correct**: the `or` term
sits at index 27 and the subscript at 33, the defect form emits the full 28-character node name while
the fixed form truncates to 18, and the `AFTER` it replaced was the error. The preposition `in` belongs
to the original and is the particle of "spliced in". Both were read as *phrasing* before they were read
as *claims* — `a-guards-label-is-not-its-predicate` in its prose form.

### Recorded, not fixed — and why this one and not the other

**`cr-impl` F3, the `mirror_share` type gate.** The renderer admits `bool` (`isinstance(share, (int,
float))`) where the producer explicitly rejects it (`memory_status.py:3531`, `and not
isinstance(..., bool)`), so a hand-set `true` renders *"mirror-dominated (100% of index tokens)"* —
asserting a measurement from a literal. It is **real and it is the same class as the fix above.** It is
recorded because of where the state can come from: `memory_status.py`'s own comment reasons about this
exact case and defends its side — *"a hand-set `true` would persist as 1.0 and read as mirror-dominated;
the producer never writes one"* — so the gap needs a **hand-edited record on disk**, the same
reachability class as `:899` and the `:874-879` pair that §6 already records. F1 was fixed and F3 was
not because F1's own comment claimed its contract was **closed** and the `_recorded` idiom that answers
it was two lines above: a code contradicting its own stated rule, versus a documented asymmetry. That
distinction, not severity, is the line.

**`cr-pins` F2, E3-c is one-sided.** The populated marker row is asserted by a presence test, so a
hardcoded `"?"` passes it. Recorded; the assertion shape is the finding, and it is the same
`a-pins-assertion-shape-sets-its-blind-spot` shape §4.3 already discusses.

### The propagation this pass discovered, which is a measurement about the harness

`mkrev.sh` overlays named files from the live worktree into **all thirteen** trees. For
`render_dashboard.py` that is a trap: it would stamp the fixed file onto every mutant and erase all ten
mutations. The rule that replaced it is not "which trees carry the anchor" but **is this line inside the
delta the tree's mutation defines**. Each tree is named below **with its own delta** rather than by
pairing a list of names against a list of numbers — the first draft of this sentence did exactly that
and mispaired two of the four (it read `mutD` as 202 and `prefixE` as 115; both are wrong, and the
numbers `202/202/202/115` are correct as a *multiset*, so nothing but the list ORDER was broken). A
reader asking "did `prefixE` receive the fix?" would have read 115, concluded it was not a whole-region
revert, and found this very propagation defective — `audit-the-diffs-prose` committed by the ledger that
records the audit. Measured on rev11: **mutA 202 · mutE 202 · prefixE 202** (whole-region reverts),
**mutD 115**, and **R1i 13**, the surgical revert of this very line. All five therefore already red
**E1-i** and keep their pre-fix `rd` byte-for-byte across rev11→rev12. The other seven trees carry the
fixed form and received the fix: had the five pre-fix trees been stamped with it instead, R1i's
one-check revert — the only revert whose named check is this line — would have gone green, and the
other four would have lost their mutations outright. Separately measured and recorded: the six surgical
reverts each carry a **9-line comment revert** at `:958-966` that is not their named mutation. It is inert — a comment moves no check — but it is a second, un-named delta in six trees, and
naming it is the point.

---

## Revision 11 — the eighth pass: the prose lens, and the repair that inverted its own sentence

The prose lens was re-run over revision 10's repairs, against the current worktree rather than against
the prose. It found that **the repair had inverted a true sentence**, that the pass's ledger claimed a
third repair it had not made, and that two timing claims named a revision which did not do the thing
attributed to it. All are the cycle's thesis arriving in the cycle's own text: a surface stating a rule
in prose while the code states it in a boolean, with nothing able to compare the two.

### The E2-b label stated the inverse of its own condition

Revision 10 rewrote the E2-b check label to *"…is **SUPPRESSED only when** the record counts no blocked
rows AND carries neither candidates nor decline-anchors, and is **still rendered when it carries any of
the three**"*. The condition it labels is `if not _cands and not _anch and _n_blocked <= 0:` — the
branch that **appends** the cold-state line. The line is therefore rendered iff all three operands are
clear, and the label said the opposite of **both** clauses. The pre-edit label — *"SUPPRESSED when the
record counts blocked rows and still rendered when it counts none"* — was **true**; the repair broke it.

The sharpest form is that the label contradicted **its own check's assertion**, and nothing in the
suite can catch that: `_e_2a` (`n_blocked=30`) asserts the line **absent** and `_e_2c` (all clear)
asserts it **present** — the reverse of each is what the label claimed. A label is prose; `check()`
prints it and asserts on the expression beside it. That is `a-guards-label-is-not-its-predicate`,
committed by the check written to repair a label/predicate mismatch.

### The third site was never edited, and the ledger said it was

`tests/smoke.py`'s comment **above** the E2-b check appears nowhere in this pass's diff (0 hits for its
text). It still read that keying on `_anch` *"would suppress the cold line for a record with anchors and
no blocked rows — a third state neither renderer has a rule for"* — while the renderer comment added in
the same pass states that `_anch` **is** the rule for that state. Two comments in the frozen revision
contradicting each other about one condition, which is the N2 shape. The ledger's *"All three sites now
state the rule that ships"* was true of two; it is annotated in place rather than rewritten.

### The unwitnessed count was one short, and the phrasing named the defended conjunct

The renderer comment said *"That last conjunct is UNWITNESSED"*. Measured with one scratch mutant per
conjunct: deleting `and not _anch` and deleting `and not _cands` each change the render for a state no
fixture builds, and each leaves **every** check green; deleting `_n_blocked <= 0` is the one that reds
**E2-b**. So **two** conjuncts are unwitnessed, and the singular pointed at the only one defended. The
revision-10 sentence in §4's E2-b ledger entry carried the same undercount.

### The timing claim, in three places rather than two

Three sentences dated the arm's addition to the revision that carried the false clause — §4.1's *"the
arm was added in that same revision"*, the revision-10 annotation's *"the arm this same revision
added"*, and the repair ledger's *"in the same revision that added the arm"*. All three are **right**,
and `git log -S` says why: **`bb52757`** is the sole introducer of both `_E_REM_PENDING` and the
*"would leave the suite green"* clause. The first draft of this paragraph recorded that commit as
revision **7** — a number taken *from this document* rather than derived from the commit, which is this
cycle's own defect committed by the paragraph reporting its measurement. The commit is revision **6**:
the arm is ledgered inside Revision 6's section, and `bb52757`'s message names the second *and third*
passes. The true statement is the stronger one — the clause and the arm that refutes it entered in
**one commit**, three lines apart in one bullet, so the clause was refuted by its **own ledger entry
from the moment it existed**. The label a failure printed claimed a gap its own revision had already
closed, and it did so on the revision that closed it.

### A citation that resolved to nothing, and the census it prompted

The repair ledger cited *"`:1265`'s pointer to §4.2"*. The pointer lived at `:1251` in the frozen commit
and exists at no line of the worktree. It is the same shape as the dangling-label defect the cycle
exists to fix, in the sentence recording the fix.

That prompted a **census of every `render_dashboard.py` line citation**, each checked against **both**
baselines the ledger can mean. The result is that every citation resolves — against one baseline or the
other — except one:

| Citation | worktree | `f175b8e` | resolves |
| --- | --- | --- | --- |
| `:899`, `:874-879` | ✓ | ✓ | both |
| `:977`, `:981` | ✓ | ✗ | worktree |
| `:1271-1277`, `:958-966` | ✗ | ✓ | frozen commit |
| `:878` *(the `sub`)* | ✗ | ✗ | **neither — the `sub` is at `:877` in every state** |

So the diagnosis is not a scatter of stale numbers: it is **one convention split down the middle of a
single ledger**, with one genuine miss inside it. `:878` is repaired to `:877`. The split is recorded
rather than mass-repaired — the v0.4.25 rule (greppable anchors over `file:line`) is the repair, and
applying it across this ledger is not this pass's work — but a reader now knows which file to open for
which line, which was the whole cost of the split.

### The census that bounded the class

A census over this branch's added lines, matched on polarity vocabulary (`SUPPRESS|only when|iff|fires
only|abstain|renders? when`), returned **four** sites. One is the E2-b label above; the other three are
accurate. The census is vocabulary-bounded — the limit `gate-coverage-is-its-match-set` names — so it
bounds this class rather than proving it empty, and it is recorded as a bound.

### What moved, measured

`render_dashboard.py` is **comment-only by AST equality** — both the comment-insensitive and the
string-folded dumps equal the frozen tree's. `tests/smoke.py` differs by comment plus **exactly one
string constant**, the E2-b label, with identical constant counts (19096 before and after), no change to
any assertion, no change to any call, and no change to the check count — so **D6's constant does not
move**. Both measured against **`/tmp/ce8/rev12/LIVE`**, the frozen tree, not against `HEAD`: revision
10's work is uncommitted, so `HEAD` is two revisions stale and comparing against it reports this pass's
edits and revision 10's together.

**This is the third consecutive revision whose subject is this document's own prose**, and each pass's
repairs produced the next pass's findings. The honest reading is not that the repairs are wrong but that
prose asserting a rule is not audited by re-reading it: the E2-b label survived a dedicated prose lens,
a re-write, and a ledger entry claiming it fixed, and was caught only when the sentence was compared
against the boolean it describes.

---

## Revision 12 — the ninth pass: the second code review's prose findings, adjudicated

**Where this pass begins is itself the first finding, because a reader cannot recover it from the
document.** Revision 11's ledger closes with its own *"What moved, measured"* and does not describe the
edits below. Those edits exist in **no frozen tree before this revision**: `rev12/LIVE`'s harness
(`62af8616…`) and `rev13/LIVE`'s (`e3c5a13e…`) both still carry the **false** `omitted` lineage, and the
correction appears only in the tree measured here. So they are this pass's work, and the pass is
numbered 12. *(The boundary is stated because picking it wrongly is how this document has mis-dated a
revision before — §4.1's arm, in revision 11.)*

**And drawing that boundary produced the pass's first finding, in the sentence that corrects this
cycle's thesis.** The repaired E1-e label dated its own correction *"corrected in revision 11"* — a
number taken from the ledger above rather than derived from the edit, which is this pass's. It now
reads **revision 12**. The document's own §4.1 paragraph had already named this exact failure for the
arm's date, one revision earlier; the sentence reporting a correction then committed it again. A number
in a ledger is a *label*, and the edit is the *data*.

### Fixed: the E1-j guard's label claimed a scope one branch wider than its conjunct

The guard's label read *"a mirror-dominated store is **not ALSO given the local-prune advice**"* — and
that is true of the row-4-6 verdict branch and false of its neighbour. The D5 remedy
(`reaches_budget is False and not resolved_by_lean`) is keyed on **neither the label nor the share**, so
it *co-renders* with the mirror line by design: one record, two lines, both correct. The suppression is
a property of one branch, and the label stated it as a property of the panel.

The sharpest form is that **the code at the site already said so** — `render_dashboard.py`'s own comment
reads *"it is a claim about a different **kind**, and it CO-RENDERS with this line, by design"* — while
the label paraphrased it as *"a different claim about a different **state**"*, which is the half that is
false. So this was not a missing guard: it was a **label that had drifted from the code it describes**,
and the repair had to make two moves, not one.

- The label now states the scope and the co-rendering.
- A **third conjunct** pins the co-rendering instead of leaving it unread: the same lever and share with
  `reaches_budget=False` (`_e_j_co`) must render the mirror line **and** the D5 remedy together. This is
  the only behavioural addition in the revision — and it adds **no `check()`**, so D6's constant does
  not move. `a-pins-assertion-shape-sets-its-blind-spot`: the first two conjuncts cover one branch each
  and leave the co-render — the thing the label was wrong about — unwitnessed.

### Fixed: the F2 comment's stated REASON was false, though the fix it described was real

The comment above the `_recorded` repair for `budget_tokens` read:

> *No census of the panel's operands could reach it: the four the census samples are PRINTED on the `↓`
> line and this one is only ever compared AGAINST.*

**"Only ever compared against" is false.** `_over()` prints this operand at
`render_dashboard.py:237` — `⚠ OVER ≈{b.get('budget_tokens', '?')} tok BUDGET` — one line below the `↓`
line and only when `over` is set. The true reason the census does not sample it is its **LOCUS**, not its
reachability: the census walks the four *measured* operands printed on the `↓` line, and this one prints
through a different function, on a different line, under a condition. *"The census could not reach it"*
is therefore true of **the census as written** and false of **the operand** — an extended census would
reach it. The distinction matters because the false version reads as a permanent, structural exclusion,
and a reader would not go looking for the printing site.

The repair is calibrated to the difference: it says the census *as written* misses it, names the LOCUS,
and records why the correct repair is not a census extension. That is `gate-coverage-is-its-match-set`
with the census as its own subject — the same shape revision 9 found in the audit's selection, arriving
this time in a comment *about* a census.

### Fixed: the `omitted` lineage was false on five surfaces, and the true history is a SPLIT

Five comment/label surfaces carried the lineage *"the third pass added the key's `omitted` spelling as a
third form"* — §2.1, §3.6, §4, revision 9's ledger, and the E1-e check label a failure prints. **It is
false on its face**: §2.1's own eight-cell account, written one revision earlier, spells the scope's two
forms as *"an **absent** and a **blank**"*. An absent key and an omitted one name the **same state**, and
the eight-cell scope already counted it.

What the third pass actually did was **split** the single `blank` form into `None` and `""` — four
operands × three spellings = **twelve** cells, from eight. And `_e_missing` is not a third form at all:
it is the census loop's sentinel meaning *"do not set the key"*, a **test mechanism**, and the reason a
reader could mistake it for a form is that the loop's triple *looks* like a form list.

Both halves are now stated. The five surfaces are: §2.1 (`:486`), §3.6 (`:768`), §4 (`:2002`), revision
9's ledger (`:2519`), and the E1-e check label a failure prints.

*(The census comment above the loop was **not** a carrier, and the contrast is the useful part: it names
the two ways — *absent* and *present-and-blank* — in exactly those terms, so a reader who took it as the
authority would never have arrived at a third form. What made the third form plausible is the LOOP under
it. `for _spell in (_e_missing, None, "")` walks a **triple**, and its first element is a sentinel
**named** `_e_missing`; a three-form list is therefore what the mechanism looks like even though the
prose beside it says two. That is the same shape as the rest of this cycle — the name was read instead of
the data — arriving on the one surface that was innocent of the error.)*

### Recorded, not fixed: two hand-edit-only operands whose repair is the coercion the presence test refuses

Both are reachable only by hand-editing a record; no producer can build them, and each repair would cost
more than the defect. They are recorded at the code site rather than left for a reader to derive.

| Operand | Renders | Why no producer reaches it |
| --- | --- | --- |
| `budget.index.budget_tokens` = `None` / `""` | `⚠ OVER ≈None tok BUDGET` — an absence occupying a measurement slot | `memory_status.py:3470-3471` writes `budget_tokens` and `over` **in one dict literal from one constant**, so the two cannot disagree there |
| the same key = a present, **non-blank, non-numeric** value (`True` / `False` / `"many"`) | `⚠ gate fired but not acted on` — where the absent and blank spellings of the same key render `✓ gate resolved by rebuild-lean` | same site; and the repair would be a **magnitude/type** test on this operand, which is the coercion `_recorded` exists to refuse |

The second row is the sharper one and it is a property of the test, not of the value: **`_recorded` is a
PRESENCE test** (`key in m and not ms._duty_blank(m[key])`), so a present, non-blank, non-numeric
threshold **passes** it and `_num` then coerces the value. Measured at `achieved_index: 1300`,
`budget_tokens` of `True`, `False` and `"many"` become `1.0` / `0.0` / `0.0`, the lean test
(`0 < ai <= budget_tok`) reads false, and each renders the alarm — while the **absent** and **blank**
spellings render `✓ gate resolved by rebuild-lean`, rescued by the constant the presence test falls back
to. The verdict therefore follows the *spelling* of a value that is never validated as a number: a
non-number the test **rejects** is rescued, and one it **admits** is compared. That is the fourth pass's
own split — absent vs blank — surviving one rung narrower, which is why a second presence test cannot
close it. The presence test closes the *blank* forms by design; it cannot close the *wrong-type* forms
without becoming the magnitude test it was written to replace.

*(Both rows are also the reason the F2 comment's repair is a **scoping** rather than a widening: the
census is a presence census, and extending it to the threshold would have to decide whether to admit
non-numeric values — which is precisely the question the panel's own idiom answers "no".)*

### The measurement, and a comparer that could not compare

Both mutable members of the triple moved again since the last measured generation, and each delta was
measured **before** the run rather than after: `tests/smoke.py` by 23 changed lines of which **8 are
non-comment** (two check-label strings and prose), `render_dashboard.py` by 18 changed lines of which
**0 are non-comment**. So no behaviour change was predicted anywhere, and the prediction — recorded in
a separate file before the run — was that **every count and every red set reproduces**.

**It did, all thirteen.** `LIVE` 2017 / 0 · `mutA` 2000 / 17 · `mutD` 2011 / 6 · `mutB` 2014 / 3 ·
`prefixE` 1997 / 20 · `mutE` 1996 / 21 · `R1f` `R1g` `R1h` `R1j` `R2f` `RC89` 2016 / 1 each · `R1i`
2015 / 2 — and **total red 75**, matching the prediction written before the run. The red **sets** are
not merely counted but checked: `mutD ⊆ mutA`; `mutA ∩ mutB = ∅`; `prefixE = mutA ∪ mutB` exactly, at
20 = 17 + 3; `mutE − prefixE` is the single `SKILL:remediation` row; `prefixE − mutE` is empty. And
`R1i`'s two reds are named — **E1-i *and* E1-i2** — because a region revert is not a single check.

The census constant is consistent in a way worth stating, since it is what lets D6 be D6: **every tree
executes exactly 2017 checks** (`passed + failed = 2017` in all thirteen), so D6 — which counts
executed checks rather than verdicts — is green in every tree and can never be any tree's second red.

**The propagation rule, and why a flat overlay would have been silent and fatal.**
`tests/smoke.py` is **tree-invariant** — one hash across all thirteen — so it is overlaid flat.
`render_dashboard.py` is **tree-variant** (nine distinct hashes: three shared groups plus seven
singletons, the healthy signature; `1` would be the flattening alarm and `13` the other one), so it is
patched **per tree**, with an AST dump compared before and after each patch. Measured: **8 APPLIED**
(LIVE, mutB, R1f, R1g, R1h, R1j, R2f, RC89), each **AST-inert** — the edit is proven comment-only *on
that tree*, not merely intended to be — and **5 SKIP** (mutA, mutD, prefixE, mutE, R1i), each of which
is **byte-identical to the previous generation**. The five are the mutations that *revert the very
region the comment sits in*, so the hunk has no context to land on; byte-identity is a **stronger**
statement than a patch, because it asserts the mutation is unmoved rather than arguing it. **0 BROKEN.**
A flat overlay here would have rewritten all thirteen trees with the live renderer: every mutation
definition destroyed, the batch silently thirteen copies of `LIVE`, and every "this mutant reds exactly
its own check" claim rendered vacuous — **and green**.

**The comparer could not compare, and it said the opposite of the truth.** Phase D previously compared
a snapshot text file against freshly extracted red sets. Its writer had changed to a space-padded
`printf` while its reader still grepped a **tab**-separated field, so the reader matched nothing and
*every* tree's extracted set came back empty; combined with a stale base it reported **all thirteen
trees CHANGED when the truth was that all thirteen were identical.** The failure was found by asking
what the empty set would look like if the instrument were the broken thing. The repair is one
extractor applied to **both** revisions' own `.log` files — so the comparison cannot be an artifact of
two differently-written readers — with a `<NO-LOG>` marker that no red set can equal, and explicit
guards for `FAILED > 0` and `AGREED == 0`. **The repaired comparer was validated on a known answer
before it was used**: rev13 vs rev14 reports 13/13 identical, and a `mutA`-vs-`LIVE` control still
sees the difference (17 reds against none). It then reported **13/13 identical, 0 moved, 0 unreadable**.

**The injections, five of them, each an operand deletion measured rather than argued.**

| Injection | Edit | Predicted | Measured |
| --- | --- | --- | --- |
| `inj13_branch` | the `else:` arm that renders the pending verdict → `pass` | 2016 / 1, red `E1-e` alone | **2016 / 1 — `E1-e`** |
| `inj13_branch_noarm` | the same deletion, the five-line `E1-e` arm removed from the harness | **2017 / 0 — green** | **2017 / 0 — green** |
| `inj13_anch` | `and not _anch` deleted | **2017 / 0 — green** | **2017 / 0 — green** |
| `inj13_cands` | `and not _cands` deleted | **2017 / 0 — green** | **2017 / 0 — green** |
| `inj13_nblocked` | `and _n_blocked <= 0` deleted | 2016 / 1, red `E2-b` alone | **2016 / 1 — `E2-b`** |

The first two are the pair that makes the arm's bite attributable: the biting run and the green run
differ in **exactly one thing**, the assertion. The middle two are the renderer comment's own claim
that two conjuncts are **unwitnessed** — measured, each moves no check, so the claim holds against the
shipped bytes rather than by argument. The last is the conjunct that comment claims **is** defended:
until this pass that sentence was the one operand claim in the comment resting on argument rather than
on a measured tree, and `_e_2a` (`n_blocked=30`, no candidates, no anchors) is why it bites — the two
surviving conjuncts are both true, so the line renders exactly where `E2-b` asserts its absence.

**And the pin's own counterfactual, run against the revision its label names.** The thirteen trees
test `E1-i2` against mutants that share the line, which is a **proxy**; the label names `f175b8e` — the
branch tip *before* the fix, and deliberately not the base `1d97f54` that the neighbouring `E1-i`
label names — so the pin was run there: `f175b8e`'s renderer with this revision's harness, **2016 / 1,
red `v0.4.34 E1-i2` alone**. E1-i stays **green** in that tree by design rather than by accident:
`_e_i_nobudget` carries no `budget` block at all, so it exercises the *fallback*, while this pin is
about the *absent key* — two spellings that a single fixture cannot both reach. The **same harness**
on the shipped renderer is green, which is the pin: the fix clears the red, not the harness.

**And the harness lost a tree between its build and its use.** `pref175` — the counterfactual the
E1-i2 label names — was built and asserted, and then did not exist when the run that needs it was
about to start. **No script in the harness deletes it**; the removal is unexplained, and it is
recorded rather than waved away. What matters is what it would have done: the followup script's
`cd "$PREF" && python3 tests/smoke.py` would have short-circuited, the count would have grepped empty,
and the script would have printed **"PREDICTION FAILED — re-read the label, do not adjust the
prediction"** for a tree that does not exist — a false alarm whose stated remedy points at the label,
which was never measured. That is the comparer's defect in a second instrument, caught this time
before it reported: the followup now asserts the tree's identity **first** (renderer equals
`f175b8e`'s, renderer does **not** equal the batch's, harness equals the batch's) and, on a mismatch,
exits **90** with *"HARNESS FAULT — NOT a verdict on the label … Do NOT re-read the label: nothing was
measured."* The two failure modes no longer share a message, and the fault path is verified by running
it against a tree that is not there.

### The pair, re-measured on the harness this revision ships

**§4.3's** re-measurement narrative stops at the **eighth** harness — its rows name `rev8`'s and
`rev7`'s harness explicitly, and the last paragraph in the sequence is *"And again on the eighth … so
the pair was rebuilt against it"* (`rev10`'s). **Every one of those rows is a historical measurement and
stays as it is.** What the section was missing is the pair on the harness that ships, and it now has
it — the two rows of the injection table above: the branch deletion at `2016 / 1`, red `E1-e` alone,
and the *same* tree on the harness minus that arm at `2017 / 0`, green.

The pair moved by exactly one on each side, and *why* is the whole content of this revision's
measurement discipline: the census constant was bumped `2016 → 2017` when **E1-i2** was added, and the
deleted arm is still the only thing that reads the pending line — so the biting run reds one check and
runs one more check, and the green run is **still green on the larger census**. A reader who carried
the old pair forward would have been reading `rev8`'s numbers as though they were the shipped one's;
the count is a property of the **triple**, and the harness is a member.

Two repairs follow, and both are to §4.3 rather than to this revision's own text:

- **A present-tense figure that is false of the revision that ships.** The sentence recording what a
  green run's evidence actually is — *"its count (2016, the census the thirteen trees report) plus the
  prediction it matched"* — is now scoped: 2016 is the census **as measured there**, and the
  parenthetical names the shipped census as 2017. Unscoped, a measurement's own commentary asserted a
  number the branch no longer has — the same defect as the labels, on the one surface nobody re-reads,
  because it is *about* correct past measurements rather than being one.
- **A forward pointer at the `rev8` table** naming the generation that ships (`rev16`) and saying its
  numbers are here, so the three historical generations cannot be carried forward as the current
  triple.

*(This passage's own first draft named §4.1 for a narrative that lives in §4.3 — a section number
taken from a task list rather than derived from the document, which is this revision's subject
arriving in the sentence that opens its measurement. §4.1's only `harness` mention is a summary clause
at `:1276` pointing forward into §4.3; every row and every ordinal is §4.3's. Recorded rather than
silently fixed, because a citation that resolves to the wrong section is what revision 11's citation
census was for.)*

### What moved, measured

| Member | Hash (first 16) | Trees |
| --- | --- | --- |
| `tests/smoke.py` | `a50d63358a99caf9` | **all thirteen** — one hash, the tree-invariant signature |
| `render_dashboard.py` | `86583fa9b86e13d2` | LIVE, mutB, R1h |
| | `309e3df5b02a2ec7` | mutA, prefixE, mutE |
| | `603283368a88fb26` · `e8d76ee72a171bf0` · `5795ea3a466ce3d2` · `18fe4d49e2b5fc2a` · `6b7724dae952b3e5` · `249a852a3ff6658b` · `a6ac3f5439b31185` | mutD · R1f · R1g · R1i · R1j · R2f · RC89 |
| `render_dashboard.py` — `pref175` | `dd41ac01a055de8b` | asserted **equal to `f175b8e`'s** and **not equal to the batch's** |

**Nine distinct `render_dashboard.py` hashes, one distinct `tests/smoke.py` hash, and one
`pref175`.** The counts are the point and so is the shape: `smoke` == 1 is what makes a flat overlay
correct, `rd` == 9 is what makes a flat overlay fatal, and the two together are the propagation rule
rather than a description of it.
