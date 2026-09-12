# Cross-domain mirror key — the bare stem where the namespaced key belongs

**Design-of-record for four sites on the write path and its accounting model — plus the
`--gc` dead-probe, the same root cause reached from a reporting surface.**
Status: drafted 2026-09-11 (UTC 09-12), adversarial review round 1 complete and folded.

## 1. Context (measured 2026-09-11)

`python-ruff-mypy-gate` — the cross-domain canonical that motivated group-scopes §1
— was reworded in its home domain (`tools`). The reword corrected a false universal:
the shipped description said "The user's Python repos gate quality before commits",
but `consolidate-memory` is a `python-repos` member whose gate is mypy-only, with no
ruff config and no `pyproject.toml` at all. The distinction cannot be carried by
`applies_*`: those tokens resolve against capabilities derived from `stacks:`
(`capabilities.py`), and every affected repo is `python`. So it had to be prose.

Three of the four writes landed correctly:

| layer | outcome |
|---|---|
| canonical (`domains/tools/facts/`) | ✅ new body, `fact_id` preserved |
| member mirror body | ✅ refreshed, `base_revision == canonical_revision` |
| member index line | ❌ **appended a second line; the stale one survived** |

The member's always-loaded index then read:

```
- [python-ruff-mypy-gate](tools--python-ruff-mypy-gate.md) — The user's Python repos gate quality …   ← STALE, false
- [python-ruff-mypy-gate](tools--python-ruff-mypy-gate.md) — job-applicator-python + agent-loop …    ← correct
```

The false claim sat **above** its correction, in the tier every session pays for.

## 2. The defect — one root cause, two legs

`_mirror_key(ctx_domain, fact_dom, stem)` (`sync_global.py:1208-1230`) returns the bare
`stem` for a same-domain fact and `f"{fdom}--{stem}"` for a cross-domain one, raising on
an unsafe domain or a `--` ambiguity. That namespaced value is the fact's **file key**
and its **index anchor**. Four sites on the write/accounting dependency derive a *different*
quantity from it and get the bare stem instead; the `--gc` dead-probe makes the same
substitution from a classification surface, and §7 treats it separately.

**Leg A — the matcher key (write path).**

```python
_j_key = _mirror_key(ctx.domain_id, _j_sdom, name)
planned = apply_pointer(planned, _pointer_line(name, fm, anchor=_j_key), name)
#                           ^ the line is BUILT from _j_key …      ^ … but MATCHED against name
```

`index_admission.apply_pointer(current_text, pointer_line, stem)` replaces the first
line containing `]({stem}.md)` and **appends** when no line matches
(`index_admission.py:111-128`). The written link is `](tools--python-ruff-mypy-gate.md)`,
which does **not** contain `](python-ruff-mypy-gate.md)`, so no line ever matches and
the append branch runs unconditionally. Reproduced against the real function:

| `stem` argument | result |
|---|---|
| `python-ruff-mypy-gate` (what the code passes) | duplicate: stale line retained, new line appended |
| `tools--python-ruff-mypy-gate` (the anchor it already computed) | correct in-place replacement |

**The strongest evidence that this is an oversight and not a design choice** sits *inside
the same loop body*, two lines above the execute-site defect (pre-fix tree):

```python
ptr_unchanged = any(
    f"]({_j_key}.md)" in ln and ln.strip() == ptr.strip()   # matches on the RIGHT key
    for ln in idx_text.splitlines())
future = apply_pointer(idx_text, ptr, name)                  # …and this one doesn't
```

**Leg B — the accounting key (read path).** The same confusion, at sites that never call
`apply_pointer`. Both cost maps are keyed by the **real link target parsed from the
index** (the namespaced anchor) and looked up by the **bare stem**:

```python
_line_cost_run[_m.group(1)] = est_tokens(_ln)     # key = "tools--python-ruff-mypy-gate"
....get(name, 0)                                  # lookup = "python-ruff-mypy-gate" → 0
```

`_plan_pull` charges a STALE refresh `cost_new - cost_old` and **always runs** it — the
`idx += cost_new - cost_old` line in `sync_global.py`, which occurs **once** in that file and
carries no gate — so a `cost_old` pinned at `0` books a full line where the real delta applies.
The gated arm is the MISSING one: its `delta = cost_new - cost_old` (also a single hit in that
file) routes through `_would_net_grow` and can *hold* the pull. That contrast is why the ungated
STALE arm is the one that matters here: an over-charge there meets no growth gate at all.
**Citing the two lines rather than the two `status` arms is deliberate** — `if status ==
"MISSING":` has a *second* arm in the execute loop, gated by file-presence and admission
instead, so a reader who greps the arm phrasing carries away the wrong gate. The beacon
(the `line_cost` build in `session_beacon.py`) builds the identical map and adds a sharper
failure:
`elif cost_old and cost_new != cost_old:` is falsy whenever `cost_old == 0`, so a
cross-domain STALE item is **never constructed**.

The three concrete instances share one signature — **the correct namespaced key is
computed within a line or two and used correctly for an adjacent purpose, while a derived
quantity falls back to the bare stem**:

| site | correct use (nearby) | wrong use |
|---|---|---|
| the execute-loop matcher, `sync_global.py` | `ptr_unchanged` matches `]({_j_key}.md)` | `apply_pointer(…, name)` |
| the `_line_cost_run` build, `sync_global.py` | the map is *keyed* by the full anchor, `re.search(r"\]\(([^)]+)\.md\)", …)` | `.get(name, 0)` |
| the `line_cost` lookup, `session_beacon.py` | `(store / f"{_bk}.md").exists()` | `line_cost.get(n, 0)` |

This is one unfinished refactor, not three typos: namespacing was applied to the
**identity uses** (filenames, existence checks — where a wrong key throws immediately)
and missed on the **derived quantities** (matcher keys, cost lookups — where a wrong key
returns a plausible `0` and stays silent).

**Same-domain is genuinely safe.** `_j_key == name` exactly when the canonical's `domain`
equals `ctx.domain_id` or is empty, and `_mirror_key`'s other exits *raise* rather than
return a differing key. Whitespace cannot defeat it (`_frontmatter` and `fact_domain`
both `.strip()`); case variance cannot either (`domain: Tools` would make
`_j_key != name`, but `fact_schema.validate_canonical_frontmatter` rejects `fdom != domain`
upstream, on every pull arm).

## 3. Trigger — every STALE refresh, not just a reword

The status classifier compares the **whole file text** (one hit in `sync_global.py` —
`status = "frozen(mirror)" if present and is_mirror else "irrelevant"`):
`in-sync` iff `cur == want`, else the three-way path. Because the mirrored body and its
revision stamps are part of `cur`, a **body-only** canonical edit produces STALE just as
a description change does.

So the append fires on *any* STALE refresh of a cross-domain mirror where admission
passes. `ptr_unchanged` (`ptr_unchanged = any(`, one hit in `sync_global.py`) does **not**
prevent it — its only use is gating a lint *warning* (`if lint and not ptr_unchanged:`); the
index write beside it is unconditional.

An earlier reading of this defect scoped it to "reword only", by assuming `ptr_unchanged`
guarded the write. It does not. The corrected trigger is broader and is what the
regression test must pin.

## 4. Corrections the review forced

Three claims in the first draft of this spec were wrong. All three are recorded here rather
than quietly edited, because the errors are the interesting part. (The paragraph said "two"
until review — (c) sits below it and was outside the count.)

**(a) "MISSING is unaffected" — FALSE.** The first draft argued that on first delivery
there is no line to replace, so the append branch is correct. There **is** a line to
replace: the member's own **native fact with the same stem**, whose pointer is a bare
`](stem.md)`. `apply_pointer` matches it, takes the *replace* branch, and the local
fact's index pointer is **deleted** — file intact, always-loaded entry gone. Reproduced
end-to-end through the real `run(<project>, pull=True)`, with attribution proven by
intercepting the call site (the plan- and execute-loop matchers in `sync_global.py`,
`namespaced_link=True`); the
spec's fix restores the local line and appends the mirror.

This fires at **delivery**, not just refresh, so it is the more reachable of the two
write-side symptoms. It is *latent in this fleet* only because the collision has not
occurred: a scan of all 21 project stores found **0 same-stem collisions** (no store
holds both `X.md` and `D--X.md`). The collision is nevertheless the *design case* for
namespacing — the whole point of `{domain}--{stem}` is to let a member keep its own fact
under a name a global also uses.

**(b) "each pin fails on pre-fix code" — over-claimed.** See §9; two of the draft's
verification bullets cannot fail pre-fix and are guards, not pins.

**(c) The census frame was too narrow.** The first draft framed the search as "all 7
`apply_pointer` callers". That frame structurally **cannot** see Leg B, which does not
call `apply_pointer` at all. A matcher-argument audit is not an accounting-key audit.

## 5. Blast radius (measured 2026-09-11/12)

Cross-domain mirrors are the **entire** set of mirrors whose key is namespaced:

- **14 mirrors across 11 projects**, covering **2 canonicals** —
  `tools--python-ruff-mypy-gate` (6) and `personal--advisor-pass-before-plan-approval` (8).
- **0 duplicated stems** across 21 project indexes: the fleet's other mirrors have never
  gone STALE since delivery, so the append path has never run for them. They are latent,
  not immune — the first refresh of any of them fires it.
- **0 same-stem collisions** (§4a) across the same 21 stores, so the delivery-time
  pointer eviction has also never fired.
- **12 bare-keyed mirrors, and none of them stale in a real store.** A second scan
  (2026-09-12) re-keyed every mirror on disk with the current
  `_mirror_key(own_domain, canonical_domain, stem)` and compared the result with the file's
  actual name: the 14 namespaced mirrors reproduce exactly, 11 bare-keyed mirrors reproduce
  exactly (legitimate same-domain mirrors), and **1** bare-keyed mirror does not — in a
  *synthetic QA fixture store*, which is unenrolled and therefore cannot pull at all
  (local-only), so the delivery path cannot fire there. The 14 also reproduce §5's count
  above, which is what makes the method checkable. **0 dead index pointers** fleet-wide —
  §8.2's variant is not instantiated either.

**The fleet is undamaged right now.** The one duplicate this cycle produced was in the
authoring project, and `cm local rebuild-index` cleared it. That matters because repair
is refresh-gated (§10): a damaged store heals only on its next STALE event, which
requires a *further* canonical change. Zero live instances means the fix lands on a clean
fleet rather than leaving a repair backlog.

**Leg B is the live one.** Its effects are decision-bearing rather than cosmetic: the
same `items` list feeds both the hold decision and the `--evict` A/B gain-gate
(`plan = _plan_pull(items,` and `plan_evict = _plan_pull(items,`, `sync_global.py`).
Measured near the ceiling (341 filler lines,
`seed = 3788 tok`, `INDEX_CEILING_TOKENS = 3840`):

```
as the code computes it -> held=['some-new-global']  pull=[]
with the true delta     -> held=[]                   pull=['some-new-global']
```

i.e. a global the index has room for is reported HELD ("shrink to receive"). The beacon
is the mirror image — its `held` projection omits the cross-domain STALE delta entirely,
which is *verbatim* the F1 divergence `session_beacon.py:200-206` records as fixed ("a
hand-rolled MISSING-only loop OMITTED the STALE-refresh deltas `_plan_pull` counts"), and
the acceptance/outcome divergence `docs/evict-accounting-truth.spec.md` F3 rests on.

## 6. Why the suite was green

`docs/group-scopes.spec.md` §9 already asserts:

> a canonical change in the authoring domain REFRESHES the cross-domain mirror (no
> QUARANTINE freeze — F3) and the `group:` stamp does not restamp on a no-change
> refresh (F9 volatility);

That pin covers the **body** leg of the refresh and the stamp-volatility question. It
never asserts anything about the **index**, and nothing anywhere asserts the accounting
key. The gap is a missing assertion on a path the suite already exercises, not an
untested path.

## 7. The fix

Two tokens at each of the four sites on the **write/accounting dependency** — pass the
namespaced key where the bare stem is being used as a *derived* key. (A **fifth** site, the
`--gc` dead-probe, shares the root cause and is fixed here too; it derives a key the same way
but carries no accounting dependency, so it is not part of this section's leg argument, and
the census below lists it separately as `sync_global.py:3300`.)

```python
# write leg (matcher key)
_j_key = _mirror_key(ctx.domain_id, _j_sdom, name)
planned = apply_pointer(planned, _pointer_line(name, fm, anchor=_j_key), _j_key)

# read leg (accounting key)
items = [(name, status, est_tokens(_pointer_line(name, fm)),
          _line_cost_run.get(_mirror_key(ctx.domain_id, _sdom, name), 0))
         for …, fm, …, status, … in classified
         if rel and status in ("MISSING", "STALE-mirror")]
```

At the beacon's `line_cost` lookup this is a **reorder**, not an edit in place: `_bk` is
already computed, and used correctly by the `store / f"{_bk}.md"` probe one line *below*
where the lookup needs it, so the lookup must move above it (or call `_mirror_key(...)`
inline).

**Do not key the cost maps by bare stem instead.** `tools--foo` and `personal--foo` can
both be mirrored into one store, and collapsing them to `foo` collides exactly the case
namespacing exists to separate.

Backward-compatible by construction: same-domain mirrors have `_j_key == name`, so their
behaviour is bit-identical. No frontmatter, schema, or file-key change.

**Site census.** Every site that consumes a `](…)` index-target match — not merely the
`apply_pointer` callers. The frame was widened once in review, and this is the boundary it
settled on, stated so a reader can apply it to a site not listed here: **a key taken from the
store's own listing — `Path.stem` over a glob, or a name matched against the index — is always
right; a key taken from a registry or frontmatter fact *name* and consumed against a store that
can hold mirrors is the defect.** The boundary is necessary, not sufficient: a site inside it
can still be cleared upstream, and **three rows below are**, each by a mirror check that runs
before the key is used — the two evict filters and `_index_line_cost` (a mirror is refused as
an evict target), and `local_ingress`'s three entry points (each refuses a managed mirror
before writing). A fourth row sits **outside** the boundary rather than cleared inside it —
the demotion population, whose key is `f.stem` off the store's own glob, the "always right"
limb; its `not _is_mirror(…)` is a second and independent reason the row is safe, which is
why its gloss below names both.

The first draft's frame — "derives a key from a fact name and consumes it as a match target, a
lookup key, or a file path" — was **wider than its own table**. It named a file-path leg the
table carried in one row (the three writers that *take* their key from `_mirror_key`), and it
left four match sites unclaimed, because none of them derives its key from a fact name — plus
a fifth the draft never named at all: `apply_pointer`'s own matcher, the single site where a
key actually becomes a match target, which the census had recorded only through its callers.
The two rows that carry the argument are therefore **named rather than counted** — an ordinal
here reads as a table-row number, and neither of them is in the first two rows: **the matcher
itself** (`apply_pointer`, `index_admission.py`) and **the counter-example the whole fix turns
on** (the `ptr_unchanged` row). Each row names a **greppable anchor**, not a line number:

| site — greppable anchor | leg | affected |
|---|---|---|
| `apply_pointer(planned,` (plan-loop matcher) | A | **yes** |
| `apply_pointer(idx_text, ptr, _j_key)` (execute-loop matcher) | A | **yes** |
| `_line_cost_run.get(_j_key` (`_line_cost_run` lookup) | B | **yes** |
| `line_cost.get(_bk` (`line_cost` lookup, `session_beacon.py`) | B | **yes** |
| `store / f"{_g_mkey}.md"` (gc DEAD report) | A — identity use, not a matcher | **yes** — fixed here, pinned by §9 #9 |
| `f"]({stem}.md)" in ln or f"]({stem})" in ln` (**the matcher itself**, `apply_pointer` in `index_admission.py`) | A | **the matcher**, not a call site — the parameter *is* the key: every row above decides what it receives, and this is the only place a `](…)` target is actually compared. It also accepts the bare `]({stem})` form, which is why the namespaced-vs-bare miss is total on both spellings |
| `f"]({_j_key}.md)" in ln and ln.strip() == ptr.strip()` (`ptr_unchanged`) | — | no — **the counter-example**: the *same* `_mirror_key`-derived input the four `yes` sites take, consumed as the namespaced anchor. This is what the fix makes the other four agree with |
| `anchor = f"]({stem}.md)"` (`_index_line_cost`) | — | no — one caller passes an `--evict=` name, cleared by the upstream mirror refusal; the other an `f.stem` |
| `f"]({stem}.md)" in ln` (demotion `hook_tokens`, `memory_status.py`; an unrelated second hit in `index_admission.py`) | — | no — `stem` is `f.stem` off the store's own listing, and the population is filtered `not _is_mirror(…)` |
| `hook = f"]({stem}.md)"` (`migrate finalize` catalog check, `cm_ops.py`) | — | no — checked against a **canonical**-store catalog, where the namespaced form cannot arise |
| `f"]({evict_stem}.md)" not in ln` ×2 (plan + execute evict filters) | — | no |
| `f"]({name}.md)" not in ln` (gc strip) · `f"]({_k}.md)" not in ln`, `f"]({name})" not in ln` (`cm_ops` revoke + quarantine) | — | no |
| `apply_pointer(idx, ptr, stem)`, `apply_pointer(at, ptr, stem)`, `f"]({stem}.md)" not in ln` ×2 (`local_ingress.py` upsert / archive / forget) | — | no |
| `apply_pointer(catalog, pointer, stem)`, `apply_pointer(idx_text, ptr, stem)`, `apply_pointer(idx, ptr, rstem)`, `f"]({stem}.md)" not in ln` ×4 (`canonical_ingress.py` catalog writes) | — | no |
| `f"]({old}.md)" not in ln` (`old = origin_delete.stem`, `canonical_ingress.py` origin-delete arm) | — | no — a **native**-store stem against the native store's own index; see below |
| `ctx.canonical_domain_dir / f"{f.stem}.md"` (inactive-canonical sweep) | — | no — cleared by *unreachability*; see below |
| `path = store / f"{mkey}.md"` (the pull writer) · `store / f"{_gk}.md"` (`_store_gaps`) · `store / f"{_bk}.md"` (beacon mirror probe) | — | no — these **take** the key from `_mirror_key`; see below |

**Why the anchors and not line numbers.** The first draft cited `file:line`, and the
displacement was measured, not feared: by the time this branch was reviewed, four of the five
`yes` rows and two of the six `no` rows **the draft then carried** no longer resolved to the
site they named — and
**every one of those six pointed short**, by 4, 4, 7, 20, 22 and 25 lines, never once past.
(Those two totals count the **draft's** table — 5 `yes` + 6 `no` — not the one below, which is
larger: the same commit that replaced the line numbers with anchors also added the
`origin-delete` row, completing the class. A reader counting the current table's `no` rows will
get a different number; that is the drift, not an error.)
The direction is the mechanism: the fix inserts lines *above* the sites it edits and leaves
the citation where it was. So **the commit that carries a citation is the commit that edits
the file it cites**, and a number's correctness depends on how many lines that same work
inserts above it. Every citation into a file this change does *not* edit — `local_ingress.py`,
`canonical_ingress.py`, `cm_ops.py`, `memory_status.py`, `index_admission.py` — resolved
exactly, which is the same finding from the other side.

It fails silently, too: a stale number still resolves, just to something else (`:1447`
landed on a comment, `:3195` on an `else:`). A greppable string has no such dependency.
Same lesson as §9's counts and the D6 constant, one level down — a value that must be kept
in sync by hand drifts; one that *is* the thing does not (`docs/deep-field-theme.spec.md`
§11).

**And a greppable string has an acceptance test — its hit count, not its uniqueness.** An
anchor quoted inside the citing sentence can never be unique, because the citation contains its
own anchor; but *not* being quoted is no licence either, since a collision need not be a
self-hit. So the rule runs one way only: **uniqueness may be claimed only after the hits have
been counted and found to be one — a quoted anchor can never be unique, and is therefore always
stated with its count and each hit named.** §9.1's footnote is the instance — it names its two
hits and says which is the note — and this paragraph is the rule that footnote was measuring
itself against.

Two parameters the rule leaves to the claim, and both belong in it: **the domain of the count**
(this file, the document, the tree) and **the revision counted at**. The census's own anchors
are the case in point — they are **table cells, not citing sentences**, so no part of the
quoted/unquoted carve reaches them and the count is the whole test. That is why the count must
name its domain, and the domain is not always the document: the plan-loop call's anchor has
**three** document hits (two fenced code blocks and the census row) and occurs in a script as
well. A fenced block counts like any
other text — `grep` does not know it is fenced — which is why a transcript reporting the count
of an anchor **it also quotes** can never report the number measured on the file containing it.
State the count in prose; do not restate the anchor beside it.

The rows marked `no` were cleared **by execution, not reading**, in review:
the evict filters cannot receive a namespaced stem (a mirror is refused as an evict
target — `_is_mirror(_ep_text)`, "is a managed MIRROR (global_ref)" — so `evict_stem` is
always a bare local stem); gc's strip and `cm group remove`'s revoke both build their key
from `f.stem` and match correctly; `local_ingress`'s three entry points
(`forget`/`archive`/`upsert`) all refuse a managed mirror before writing; the
`canonical_ingress` sites *listed above* operate inside one domain's catalog where the
namespaced form cannot arise (`ctx.canonical_domain_dir / f"{f.stem}.md"` does not, and is
treated separately below). The one `canonical_ingress` row that is **not** a catalog site —
`f"]({old}.md)" not in ln`, with `old = origin_delete.stem` — strips a line naming the file it
is about to delete out of the **destination's** index, not that file's own: the index it edits
is the one bound by that block's own `idxp = origin_local.parent / "MEMORY.md"`, while `old`
comes from a *separate* parameter (`origin_delete`, declared independently, and the code below
contemplates the two differing — `same_origin`, and the `if not same_origin:` arm that adds a
second delete). **The first draft read that as a cross-file identity; it is not one, and the
distinction is one the code makes on purpose.** The two parameters can differ as *files* and
never as *stores*: the only caller that passes `origin_delete` at all binds both sides off one
`store` — `src = store / f"{local_fact}.md"` and `dest = store / f"{canon_name}.md"`, consumed
as `origin_local=dest, origin_delete=src` — so the index bound by `idxp` is the index of the
very store `origin_delete` lives in, and `old` names a file that index is responsible for.
That is a self-identity at the level the argument needs (the *index*), reached through two
parameters that are distinct at a level it does not (the *file*). The outcome is
identical anyway, and for the reason the `local_ingress` rows share: both stems are bare native
stems — `Path.stem` of files in one project's native store, which no namespacing reaches.

**A correction to the first draft's rationale:** the `local_ingress` rows were justified
as "native store, no mirrors". That is false — the native store *does* hold mirrors. They
are safe for the reason just given: all three entry points refuse a managed mirror first.
A right conclusion resting on a wrong reason is the kind of thing that survives review
until someone relies on the reason.

**The last row is cleared by construction, not by a guard.** The pull writer's
`path = store / f"{mkey}.md"`, `_store_gaps`' `store / f"{_gk}.md"`, and the beacon's
`store / f"{_bk}.md"` all take their key *directly* from `_mirror_key` — they **are** the
writer's key use, so the file key and the index anchor agree because there is only ever one
value. They are listed because they are the same shape (one key consumed as both), and
because they are the three sites a future refactor would have to carry with it: the moment
the anchor stops being the file key, these are the first to break.

**One row is cleared by a different argument, and it is called out for that reason.**
`canonical_ingress.py:988` takes a **native-store** filename stem (`f.stem` — a mirror key
for a cross-domain mirror) and resolves it in *this domain's* catalog:
`ctx.canonical_domain_dir / f"{f.stem}.md"`. For a cross-domain mirror that path cannot
exist, and the `reg_status` lookup beside it is built under `WHERE domain_id=ctx.domain_id`
(`:960`), so it cannot hold either. Both halves of the arm are therefore **guaranteed
no-ops** — not correct, *unreachable*. It has never fired for a cross-domain mirror, and
making it fire means resolving the canonical from the mirror's own frontmatter, which is
the pair-key reconstruction `_orphans(..., pair_keys=True)` already performs (`:2711`).
That is a behavior change to a path nothing has ever exercised, with a blast radius nothing
has measured; it is deliberately **left to its own cycle** rather than folded in here. The
distinction is worth the ink because "no" with a reason that does not generalize is exactly
what F1's gap was made of: the census cleared a *class* on a claim that held for the rows
it had listed.

**The deferral's residual is a delay, not a leak** — stated so the next reader need not
re-derive the bound before trusting it. The dead-canonical case is what that sweep would have
collected, and it is also the case `_mirror_canonical_path` refuses to resolve: it returns
`None` when the canonical is absent *or* its status is `tombstoned`/`superseded`/`expired`
(inside `_mirror_canonical_path`), on the reasoning that a tombstone holds no re-pullable
content and so its mirror is orphaned. `_orphans` then scans against the same live-stem set
the mass-delete guard uses — `_local_stems`, built from `iter_canonical_stems_for_gc`
and widened by the facts pairs just below — so `--gc --apply` reclaims
precisely the mirrors the ack sweep would have. **One clause carries that guarantee for the
cross-domain shape, and it is worth naming**, because citing the container alone leaves the
claim reading safe after a change that would void it: the exclusion sits *inside* the
enumerator — the `if … .get("status") … in ("tombstoned", "superseded", "expired"):` guard
`continue`s on that status, which is what keeps the tombstone's own stem **out** of the live
set (delete that and the mirror stops reading as orphaned while this paragraph still reads
true).

**The draft also claimed a second carrier, and that carrier does not reach the cross-domain
case — saying it did was an over-claim.** `--gc --apply` does call `ack_tombstoned_mirrors`
itself before the orphan scan — but that name is a three-line back-compat alias for
`reconcile_inactive_mirrors` (signature, docstring, one `return`), and the
aliased body probes `ctx.canonical_domain_dir / f"{f.stem}.md"` with `reg_status` built under
`WHERE domain_id=?` (`ctx.domain_id`). A cross-domain mirror's file stem **is** its mirror key
(`tools--mag-pb`), so that probe resolves in *this* domain for a file that can only exist in
the foreign one — a miss by construction, and the registry lookup misses with it. Measured on
the real function against a store holding a cross-domain mirror of a tombstoned foreign
canonical: `{'ok': True, 'acked': 0}`, transaction never reached — while the same store plus a
same-domain tombstone pair acks `1` (the control that makes the null a discrimination), and
`_orphans()` on it returns both stems. So it is the no-op the census above already defers, not
a backstop: **read this clause as a hole, because a maintainer who takes it for a second
carrier will delete the exclusion above believing the call still covers it — which is the same
inversion, one level up.**

**And "never unreclaimable" is bounded by one more guard — but not the one the first draft
named.** gc refuses outright when the canonical dir holds **no `.md` files at all** and
leftover mirrors are present; the message it prints there ("cannot distinguish that from
all-canonicals-deleted") names the hazard correctly. Two corrections to the draft, pulling the
same claim narrower from opposite sides. (i) The predicate is **file presence, not
admissibility** — `_has_canon_files` tests `any(p.suffix == ".md" and p.name != "MEMORY.md")`
over the canonical domain dir (`_global_is_fixture()` falls back to the global store's, a
test-only arm). "No admissible canonicals" is only the *label*, and only on the
`cross_project_allowed` branch of the refusal; a domain full of ineligible-but-present
canonicals passes. (ii) The gloss ran **backwards**. The draft said a store whose every
canonical is *dead* reclaims nothing; the reverse is true, and the source says it in terms —
"Tombstones still sit as .md files, so forget-then-GC still proceeds." A tombstone keeps its
`.md` file, so an all-dead store **passes** this guard and gc reclaims normally. The bound is
therefore about *deletion*, not liveness: while any canonical file remains on disk — live or
tombstoned — gc runs. Only a domain whose canonical dir has been emptied of `.md` files
outright, mirrors still pointing into it, is refused, and that is the mass-wipe guard (Probe
G), not a liveness one. So the honest form of the claim is *a deferred reclaim, never an
unreclaimable one **while canonical files remain in the domain's canonical dir*** — and since
tombstones count as files, that is a weaker bound than "while a canonical is live". Left
un-run, they persist until someone runs gc.

## 8. Invariants — conserved, and changed

**Conserved.** Same-domain refresh: byte-identical index outcome (the `_j_key == name`
arm), measured pre-fix == post-fix. `apply_pointer`'s contract: unchanged — no matcher
change, so no new false-match surface. The `--` ambiguity refusal in `_mirror_key` is
untouched; this fix consumes its output rather than re-deriving it. The beacon's
`missing`/`stale` **counts** are unaffected (they come from `_store_gaps`, which keys
correctly on the mirror file key inside `_store_gaps`) — only its `held` projection
moves.

**Changed — and both changes are the point.**

1. **"MISSING only ever appends" was FALSE, and the fix makes it true.** The first draft
   asserted MISSING delivery was unaffected by the matcher change. It is affected, and in
   the *harmful* direction pre-fix. Measured against the real `apply_pointer` on the §4a
   collision shape (an index holding a native `](grp-fact.md)` line):

   | | native's own pointer | mirror's pointer | lines |
   |---|---|---|---|
   | pre-fix (bare matcher) | **gone — replaced** | present | 4 → 4 |
   | post-fix (anchored) | present | present | 4 → 6 |

   Pre-fix the delivery **evicted the member's own always-loaded pointer** — the file and
   its body survived on disk, but its index line was overwritten by the mirror's, and the
   line count did not change to show it. That is precisely why the first draft's
   "unchanged" reading looked safe: nothing in the diff grew. Post-fix the native's pointer
   survives untouched and the mirror appends its own. This is a **repair**, and it was the
   one leg of the defect that could silently reduce what a session loads.
   The honest cost of the repair: a colliding store now shows **two lines whose `[label]`
   is the same** (`[grp-fact](grp-fact.md)` beside `[grp-fact](personal--grp-fact.md)`).
   That is two distinct facts with two distinct hrefs, not a duplicate — but it reads as
   one, which is a cosmetic price the pre-fix behaviour was silently paying down by
   deleting one of them.
2. **The anti-question — "is there any input where the anchored matcher makes MISSING
   worse?"** Asked and answered by the review, and the answer is *one theoretical
   direction, not reachable in this fleet*. The anchored matcher can only ever **append
   where the bare matcher would have replaced**, so it can preserve a line the bare matcher
   would have consumed. The single input shape is a store carrying a **dead bare-stem
   line** — a line whose target file no longer exists, left from an era when the fact was
   native. Pre-fix, the delivery overwrote it (a correct outcome reached by accident, since
   the line pointed at nothing); post-fix it survives until `rebuild-index` clears it —
   which it does, because that command emits one `_pointer_line` per *file* from a glob, so
   a line whose file is gone is simply not regenerated (§10). Measured fleet input for this
   shape: **0 dead bare-stem lines** across all 23 stores (§5). So the reachable behaviour
   is unchanged, and the unreachable behaviour is a stale line that a supported repair
   removes.
   **One correction to the paragraph above, forced by measurement:** the claim holds for the
   *dead* variant only, and this is not the only member of the family. A **live** bare-keyed
   mirror whose canonical now lives in another domain behaves differently — the anchored
   matcher *appends* beside it, `rebuild-index` does **not** collapse the pair (it emits one
   line per *file*, and both files exist), and `--gc` reclaims neither. That variant is
   scoped, measured and costed in §10; it is not reachable in this fleet either, but the
   "a supported repair removes it" sentence is true only of the dead line this paragraph is
   about.
3. **The write's growth model changes, so the accounting model must move with it.**
   Measured against the real `apply_pointer` and the real `est_tokens`, on a named fixture
   — the §1 case: `python-ruff-mypy-gate`, ctx domain `python-repos`, canonical domain
   `tools`, its stale description reworded into the correction. One index line exists
   beforehand (28 tok); the line a refresh writes is 33 tok anchored, 31 un-anchored. Both
   reader arms are modelled, because they fail differently:

   | state | real index delta | MISSING arm books | err | STALE arm books | err |
   |---|---|---|---|---|---|
   | pre-fix | **+32** (append) | 31 — `cost_new - 0` | −1 | **0** — item dropped | **−32** |
   | matcher fixed, accounting NOT (the write-only state) | **+4** (replace) | **31** | **+27** | **0** — still dropped | **−4** |
   | **shipped** (both legs: anchored matcher + anchored lookup) | **+4** | 5 | +1 | 5 | +1 |

   The middle row is the state a write-only fix would have shipped — it is *not* this
   branch — and it is the measurement that forces the fourth site. Three things to read off
   the grid, and the third is the one this table omitted until review round 2:

   **The MISSING arm's pre-fix −1 is why Leg B was invisible.** `cost_new - 0` booked the
   whole line, and the writer really did append a whole line. A correct answer from a wrong
   model survives any amount of review that only checks the answer.

   **The write-only +27 is that same booking meeting a replace.** `cost_old` is looked up
   by the bare stem in an anchor-keyed map, so it is pinned at **0**; anchoring the matcher
   alone moves the write underneath an unchanged model. The magnitude is structural rather
   than tuned: the booking is a full line, and a full line has no ceiling.

   **The STALE arm's −32 is the worse error and the MISSING column cannot show it.**
   `elif cost_old and cost_new != cost_old` cannot fire while `cost_old` is pinned at 0, so
   a reworded refresh built **no item at all** — out of the projection entirely, not merely
   mis-costed. That is the arm the beacon runs.

   Anchoring the lookup collapses both columns at once. `cost_new - cost_old` now subtracts
   two lines for the *same* fact under the *same* anchor, which differ only in the hook —
   and `_pointer_line` truncates the hook at 88 chars (`sync_global.py:1350`), so a replayed
   refresh is bounded above by the hook's own weight (~22 tok) instead of by a whole line.
   The shipped row's residual is +1 here, the estimate's own rounding granularity,
   cross-checked by the review on a second fixture (real 0/booked 0, +7/+8, −2/−2 — ≤2 tok,
   in both directions). So **the four sites are one change, not two:** `_plan_pull` is a
   model of the writer, and shipping the writer without its model would create a fresh
   instance of the very defect class `evict-accounting-truth.spec.md` F3 exists to prevent.

## 9. Verification

A pin is only a pin if it **fails on pre-fix code**. That rule is stated as a test, not a
slogan.

**What was actually implemented — eleven checks: ten of them (#1–#9 and #11) across
`tests/smoke.py`'s v0.4.10 groups fixture, and #10 alone in the v0.1.81 near-ceiling beacon
fixture** (see failure 5 for why it cannot live with the others). The table is deliberately
narrower than the design intent below it: a spec that lists pins it did not write is the drift
this repo's gates exist to catch.

| # | pin | leg it covers | discriminates? |
|---|---|---|---|
| 1 | body-only refresh replaces in place (exactly one line) | A (both write legs) | ✅ fails pre-fix |
| 2 | reword refresh replaces in place **and** carries the new hook **and** the pre-line is gone | A (both write legs) | ✅ fails pre-fix |
| 3 | the pull planner books `cost_old > 0` for a cross-domain mirror | B (run) | ✅ fails pre-fix |
| 4 | **both** sync call sites pass the namespaced key (`.count(...) == 2`) | A (each leg separately) | ✅ fails pre-fix / single-leg |
| 5 | the beacon builds a STALE item with `cost_old > 0` | B (beacon) | ✅ fails pre-fix / beacon-only |
| 6 | the anchored key **spares** a same-stem native while the bare stem evicts it | A (contract) | ⚪ guard — passes pre-fix by construction |
| 7 | a **real MISSING delivery** into a same-stem collision preserves the native pointer | A (outcome, both legs) | ✅ fails pre-fix; measured |
| 8 | a **real same-domain refresh** stays replace-in-place at its original position | A (same-domain arm) | ⚪ guard — fails **alone** under the position mutant |
| 9 | the **gc report** does not call a LIVE cross-domain mirror dead (its probe uses the mirror key) | A (GC's dead-probe) | ✅ fails pre-fix; **placement is load-bearing** — §9.1, failure 5 |
| 10 | an **in-sync cross-domain mirror** books **no** phantom refresh delta — the held projection still ceiling-holds the missing fact | B (beacon, *both* legs at once) | ✅ on the **half-fixed** tree · ⚪ on the original pre-fix tree — §9.1, failure 6 |
| 11 | the pull planner books the **anchored** `cost_new` — exactly the cost of the line the run wrote | B (run — the *other* half of #10's axis) | ✅ fails on the **run-side half-fixed** tree, and **alone** — §9.1, failure 7 |

#6 and #8 are the two **guards** in the set, marked as such rather than counted as pins:
`apply_pointer` and `_mirror_key`'s same-domain arm are both unchanged by this fix, so
neither can fail pre-fix. They exist for the opposite direction — to fail when a *future*
change breaks an invariant this fix depends on. #6 pins the premise behind #4's
implication (that the anchored key cannot match a native's bare line); #8 pins the
same-domain arm the fix must leave alone. Both are mutant-verified, and §9.1 records a
claim about #8's mutant that measurement forced me to withdraw.

**#10 discriminates a state the other nine cannot see, and that is the whole reason it
exists.** It is green on the original pre-fix tree (where the bare lookup dropped the item
entirely rather than mis-costing it) and green on this branch — it fails only on the
**half-fixed** tree, `cost_old` anchored and `cost_new` left bare, which is exactly the
regression the first cut of this cycle's own fix introduced and the review caught. Without
it, re-applying the obvious half of §7's Leg B re-ships a defect with the entire suite
green. Its boundary is **measured, not chosen**: the index is padded so the missing fact is
held by exactly one token, and the relief a bare `cost_new` would grant is computed off the
two real pointer lines and asserted positive — so a future change that made the two costs
equal trips an assert instead of silently un-arming the pin.

**#11 is #10's other half, and it was the uncovered site.** The half-fixed tree failure 6
describes has two faces — the beacon's `cost_new` (one hit in `session_beacon.py`:
`_pointer_line(n, fm, anchor=_bk)`, covered by #10) and the run planner's (one hit in
`sync_global.py`: `est_tokens(_pointer_line(name, fm, anchor=_j_key))`, covered by nothing).
Both were **fixed** in
this branch; the finding that prompted the check is that only one of them was *pinned*, so
the axis had a single detector standing on half of it. Measured on the run-side revert alone
(the anchor dropped from the projected cost, `cost_old` left anchored): **#11 is the only
failing check in the entire suite** (1777 passed, 1 failed) — equivalently, with #11 absent
every one of the other 1777 checks is blind to it.

That blindness is a **field** gap, not a fixture gap, and the distinction is the reason it
survived a review round. The planner's item tuple is `(name, status, cost_new, cost_old)`,
and the only assertion on it read index **3**; a change to index **2** was invisible *by
position*. #4's lesson — count the calls, don't detect the key — has a counterpart here:
**assert the field, don't detect the tuple.** #11 reads index 2 against ground truth the run
itself produced, the line the writer actually wrote (`_cline2_gs[0]`, already pinned to
exactly one line by #2), rather than re-deriving the expected value from the same helper the
code calls. So it pins the plan/execute *agreement* — that the planner books the cost of the
line the writer writes — which is the contract this whole leg is about, and it stays true if
`_pointer_line`'s format ever changes.

- **Primary pin (#2) — reword refresh.** *Required, not optional:* the body-only form alone
  cannot distinguish "replaced in place" from "never written", so it would go green if the
  index write were skipped entirely (the `continue` at `:1482`/`:1529` on an admission
  refusal) while the store kept a stale pointer. #1 could not carry this alone.
- **Stale line cannot survive** is folded into #2 (`_pre_line_gs[0] not in _cidx2_gs`)
  rather than being its own check — it catches "appended and orphaned" rather than merely
  "exactly one line", and it is only implementable in the reword form.
- **Accounting pins (#3, #5)** discriminate the *defect* (pinned at `0` versus non-zero).
  They do **not** pin the exact booked delta against the real index delta; `> 0` is the
  assertion that separates the two behaviours, and it is what was measured failing pre-fix.
  Stating the stronger claim would overstate the pin.
- **The delta-equality form is still absent** and remains the honest gap in this set: no pin
  asserts the booked *delta* equals the real index delta (§8.3's growth-model table). #11
  pins one half of it exactly — the booked `cost_new` equals the line the writer wrote — but
  that is a plan/execute agreement, not the growth model: measured, the shipped tree still
  books **+1 against a real +4** on the §8.3 fixture, and nothing fails for it. What holds
  the four sites together today is that #3/#5 fail on a **write-only** fix, not that they
  measure the delta.

**Both designed pins are now implemented** (#7, #8), and both were verified the way §9.1's
first rule demands — against a revert of the specific site each covers, not of the change
as a whole.

- **#7 — MISSING preserves a same-stem native pointer (§4a, outcome level).** It runs the
  real pull: the member holds a native `grp-fact.md` of its own, the mirror is absent
  (classified `MISSING`), and the global arrives. Asserted: the native's `](grp-fact.md)`
  line **and** its label survive, *and* the mirror appends `](personal--grp-fact.md)`.
  Measured on the two write legs reverted to the bare stem: **#7 fails** (4 failures in
  that round, #1/#2/#4/#7). The failure reason was measured, not inferred — an instrumented
  run dumped the resulting index as
  `'# Memory Index\n\n\n\n- [grp-fact](personal--grp-fact.md) — d-reworded [user-global]\n'`:
  the native's line and its label are **gone**, which is §8.1's eviction reproduced through
  the real path rather than through a hand-passed key. This closes the gap the first pass
  named as the largest in the set.
- **#8 — same-domain refresh stays replace-in-place.** Also a real pull (the reworded
  canonical into its own domain), asserting the index keeps the same line count, the line
  carries the new hook **at its original index position**, the seeded neighbour is unmoved,
  and nothing namespaced appears. Its discriminating mutant is a **position** mutant, not a
  key mutant: `apply_pointer` rewritten to delete the matched line and append the new one
  at the end. Measured: **#8 is the only failing check in the entire suite** (1 failed,
  1774 passed) — while #1, #2 and #6 all stay green, because they assert presence and
  count, and this mutant preserves both. So #8 is not redundant: it is the suite's only
  detector for "the line moved", which chained across refreshes reorders the always-loaded
  tier.

**#8's reach, stated honestly.** It does **not** fail under the write-leg revert (it covers
the same-domain arm, which that revert does not touch) — measured, and correct. And the
mutation its first comment named — `_mirror_key` "simplified" into always namespacing — is
**not measurable through this pin at all**: that mutant kills the suite at `smoke.py:4962`,
a fixture reading back its own canonical, thousands of checks before this fixture runs. So
that direction is caught by gross failure rather than by #8, and the comment now claims only
the measured mutant. §9.1 records why this was worth chasing down.

**The one remaining gap is unchanged**: the exact-value form (`#3`/`#5` assert `> 0`, never
the booked delta *equals* the real index delta — §8.3's growth-model table).

### 9.1 A pin that does not discriminate — seven recorded failures in this cycle

The rule above ("fails on pre-fix code") was applied to every one of the draft's verification
bullets, and **three of them still passed green against an unfixed site**. A fourth observation
rather than a fourth member of that set: the **two guards §4(b) names** pass pre-fix by
construction rather than by failing to fail. All three are recorded because the rule as
stated is not strong enough to catch them, and because the third is the one a whole-change
revert structurally cannot see. The review added three more entries after that count was
written — **failure 5**, a fourth pin that passed green; **failure 6**, a regression no pin
could see at all; and **failure 7**, a whole field no pin read. **Three quantities are in play
here and none of them is either of the others**: the draft's **three** non-discriminating
bullets (a count of an uncommitted draft — recorded as prose, not re-derivable from any
blob), the **seven** failures this section numbers below, and the **eleven** checks §9's table
now holds. The title this section first carried counted the first and read as the third.

**Every count in this section is as of the revision it was measured at, and each tally names
its own total: `passed + failed` IS the suite size then.** The size grows with every check
added — `1767 → 1775 → 1777 → 1778` from `main`'s base to HEAD, the branch's three
check-adding commits carrying +8, +2 and +1 — so the durable claim is always the **failure
set** (which check failed, and whether it failed *alone*), never the count. A count quoted in
the present tense has been re-measured at the current revision; the ones in failures 1–6 carry
their total in the prose around them.

**The first version of that ladder was wrong in exactly the way the paragraph above warns
about.** It read `1772 → 1776 → 1777 → 1778`, and neither of its first two rungs is a
*committed* suite size — for two different reasons, which is why one diagnosis did not cover
both. 1776 is a `passed` field quoted where a size belongs (the 1777-check revision's size is
1777). 1772 carries **two** roles this cycle: the `passed` count of the six-failure write-side
mutant run — the **anchor-drop** one, both keys left correct and only the rendered line losing
its anchor (1772 + 6 = 1778; ✗ = #1 #2 #3 #5 #7 #11, so #4 stays green) — and the **suite
total** of the five-check working tree whose D6 literal is `1745 + 27`. As a rung in a size ladder it can only have meant the second — which
puts it in the same limb as the phantom `1746 + 27` rung below: a genuine size, measured on a
tree no revision carries. It also contradicted **Failure 5**'s note below — the paragraph
opening "One note for a reader arriving from `git log`" (grep that phrase: **two** hits, the
note and this citation of it, which is why the count is stated rather than the phrase called
unique; the anchor this sentence first carried, "failure 5's note", also hit twice and never
the note — itself, and §10's past-tense *mention* of it). That note says in terms that 1776 is
a clean run of no committed revision. The corrected rungs are the four committed D6 literals:
`1740 + 27` on `main`, then `1748 + 27`, `1750 + 27`, `1750 + 28`.

*(That reference was a line distance when this paragraph was written — "111 lines below" — and
it went stale within the same review round, because the fixes above it moved the target: the
same silent-short drift §7 measures for `file:line` citations. It is recorded here rather than
quietly patched because it is §10's rule on derived figures catching an author who had just
written it, and because the corrected number would have gone stale again on the next edit.
Name the anchor; the anchor is greppable and the number never was.)*

**Failure 1 — the tautology.** The first MISSING-leg pin called
`apply_pointer(text, line, "personal--grp-fact")` — *passing the correct key by hand*. The
function was never the defect; the caller's key is. So the pin passed on pre-fix code. It
was replaced by a **call-site spy** asserting the third argument the real call receives.

**Failure 2 — the shared-capture spy.** The beacon pin spies `_plan_pull` to capture the
`items` the beacon builds. It reused the run-side spy, which **overwrites** one shared
dict with the last call's arguments. The beacon's own fixed call contributes nothing when
cost_old is 0 — the `elif cost_old and …` drops the item — so on a beacon revert the dict
simply still held the **run side's** rows, and every conjunct of the check was satisfied by
the wrong call. Measured, with `session_beacon.py` reverted and `sync_global.py` left
fixed — on a **1772-check working tree** (D6 `1745 + 27`), a total no revision carries: the
only blob that does sits in a dropped stash, reachable from no ref (see §9.1's ladder note;
this is the same basis as its `1746 + 27` rung):

```
old pin shape  →  1772 passed, 0 failed     (beacon entirely unfixed, suite green)
new pin shape  →  1771 passed, 1 failed     (the beacon pin)
```

**A green with nothing to name is the weaker record.** The first line has no ✗ to separate it
from the half-fixed phantom green (§9.1 failure 6) that the same blob reaches when run as-is;
the second names its ✗, and that is what tells its `1771/1` apart from the count-clause ✗
failure 3 measures below. No blob carries the old pin shape — every blob holding that check's
text holds the beacon-private form — so the first line's green is not reproducible from one.

**Failure 3 — the sibling leg masks the regression (the site-1 hole).** This is the
important one. `apply_pointer` is called **twice per pull**, by two different legs inside
one function: the *plan* loop (`sync_global.py:1451`), whose result feeds only the
**admission** decision via `project_index(planned)`, and the *execute* loop (`:1483`),
which performs the actual index write. Every outcome-shaped pin in the file asserts on the
**written index** — and the execute loop's correct key produces a correct index regardless
of what the plan loop passed. So a revert of the plan loop alone was invisible — measured on a
pin set that predates the count clause this fix adds:

```
site-1-only revert (execute loop left fixed)  →  1772 passed, 0 failed
```

**The basis is the pin set, not the tree — and `1772` cannot express the difference.** The one
blob carrying D6 `1745 + 27` (the dropped stash) carries the count clause as executable code,
so on that blob the revert is **not** invisible: with it the run is **1771 passed, 1 failed**,
the single ✗ being the clause itself. The `1772/0` above belongs to the **pin set that predates
it** — same blob, a set without the clause, and a total that reads exactly like a clean run.
`1772 = 1767 + 5`, and *which* five is exactly what a total cannot say — the rule stated two
paragraphs above, applied to this row. The row records a **state**, never a tree.

Both write legs unfixed was caught — reverting the two `apply_pointer` call sites alone
leaves **1772 passed, 6 failed** at HEAD's 1778 (measured; a **different** six from the
anchor-drop run the ladder note above also calls six-failure: their `passed` fields collide at
`1772` while their failure sets do not — this one is #1 #2 #4 #5 #7 #11, the anchor-drop's is
#1 #2 #3 #5 #7 #11, so #3 and #4 swap. A total identifies a size, never a run). Exactly one
write leg unfixed was caught by **nothing in the draft's pin set** — and the plan loop's key
is not inert: with the bare stem its `planned` index carries the duplicate, so the admission
verdict is computed against a pessimistic model of a write that will not happen that way, and
a pull that should be admitted can be refused. The pin now asserts the anchored key appears
**once per leg** (`_stems_gs.count("personal--grp-fact") == 2`), and that closes the hole:
reverting the plan loop alone at HEAD leaves **1777 passed, 1 failed**, the sole ✗ being the
call-site assertion — so the axis this row called undetected is detected, by the check the row
itself prompted. Label the revision on such a claim: "nothing" was true of the draft's set and
false of HEAD's, and the two differ by exactly the clause that fixed it.

Two notes on getting *that* discriminator right, both from measurement:

- **Presence is not enough; count is.** "The anchored key appears" cannot see a single-leg
  revert, because one leg still supplies it.
- **"The bare stem is absent" would have been wrong** — the first attempted fix, and it
  failed on *correct* code. The spy also observes a legitimate bare-stem call: the
  canonical `upsert` in the same block writes a **same-domain** fact, where `_j_key == name`
  and the bare stem is the correct key. Measured call order, both legs fixed:
  `upsert:canonical_ingress.py:499 'grp-fact'` → `mutate:1451 'personal--grp-fact'` → `mutate:1483
  'personal--grp-fact'`. A discriminator that cannot distinguish "correct for a
  same-domain write" from "wrong for a cross-domain one" is not a discriminator.

Four rules follow, and all four are general:

- **Verify each pin against a revert of the specific site it covers, not of the change as
  a whole.** A whole-change revert is blunt in both directions: it fails checks for sites
  other than the ones they cover, and it cannot arm a check that only a *site-scoped*
  revert reaches. Measured at HEAD, the whole-change revert (both scripts back at `79077b9`)
  fails **8** of the eleven and leaves exactly three green — the two guards (#6, #8) and
  **#10**, which §9 records as failing on the half-fixed tree and nowhere else. Only the
  site-scoped reverts exposed failures 2 and 3.
- **Where one function calls the same primitive on two legs, the pin must count calls, not
  detect the key.** One leg supplying the right argument is indistinguishable from both
  doing so if the assertion is existential.
- **A spy writing to a shared capture must assert that it ran.** The beacon pin now uses a
  beacon-private dict and asserts it is non-empty, so a monkeypatch that silently fails to
  bind — the documented hazard, since `session_beacon.py:53` binds `_plan_pull` at module
  level while `sync_global.py:1393` re-reads `apply_pointer` on every call — fails loudly
  instead of passing on another caller's data.
- **A claimed mutant is a claim; run it.** Failure 4 is the case where the pin *was* honest
  and its justification was not — and the justification is what tells the next reader
  whether the check can be deleted.

**Failure 4 — the claim I did not measure (a comment, not a pin).** #8 shipped with a
comment naming its mutant: *"it fails if a future change simplifies `_mirror_key` into
ALWAYS namespacing."* That mutant was never run against this pin. Run now, it **cannot
reach it**: always-namespacing kills the suite at `smoke.py:4962` — a fixture reading back
its own canonical, thousands of checks before this fixture — so #8 never executes at all.
The stated justification was structurally unverifiable, and it sat in the exact place a
future reader looks to decide whether the check is load-bearing. The measured mutant
(`apply_pointer` rewritten to delete the matched line and append at the end) leaves #8 as
the suite's **only** failure, which is both true and a stronger claim than the withdrawn
one: #8 guards *placement*, not key derivation. Corrected in the comment and in the table.

All seven were found by **running a mutant to completion**, never by reading the pin — the
fourth not by a failing pin but by running a mutant its comment named and the suite never
reached, the sixth by tracing what *consumes* the number a finding changed rather than how
large the change was, and the seventh by running that mutant at the *other* site the same
finding had named. That is §6's rule (`f84135c`) holding again in this repo: *a gate reviewed by
reading it yields nothing — the gate is precisely the thing that looks correct.* Every fix
here is one conjunct — a `bool(...)`, a `.count(...) == 2` — which is the whole argument for
preferring the cheap structural assertion over the plausible-looking one.

**Failure 5 — the pin a later fixture disarmed (placement, not assertion).** #9 (the
gc-DEAD probe) was first written *after* #7 in the same groups fixture. It was measured
**vacuous twice**: it stayed green with its probe reverted to the bare stem. The first
repair attempt — injecting a `holders` row by SQL, on the theory that the probe's
precondition was unmet — changed nothing. Instrumentation then showed the precondition
**was** met (`holders=['pc','pa']`, `san='pc'`); the cause was found by grep, one line:
`_native_c_gs = _storec_gs / "grp-fact.md"`, planted by **#7's own setup** in the same
fixture. With a bare same-stem native on disk, *both* the correct and the reverted probe
find a file, so the check could not discriminate **in either direction**. Moving it
upstream of #7 and dropping the injection made it fail on the mutant as intended —
re-measured independently at the revision then shipping 1777 checks: **the gc check the sole
failure** (1776 passed, 1 failed), while the same revert with the check left in its pre-review
position is green (**1777 passed, 0 failed**). **Both arms were then reproduced again at
HEAD's 1778 checks** — the gc revert at **1777 passed, 1 failed** (#9 the sole failure)
against a `1778 passed, 0 failed` control, and the pre-review-position arm green at
**1778 passed, 0 failed** — so neither the discrimination nor the vacuity is an artifact of the revision it
was measured at. The vacuity is therefore reproducible on demand, not merely recorded.

One note for a reader arriving from `git log`: commit `b023d02`'s message carries "1774 passed,
2 failed" — 1776 — which is a clean run of **no** committed revision of this work: `b023d02`
itself ships 1777 checks (its own D6 literal is `1750 + 27`), and its parent is `dba2a49` — a
docs-only commit carrying `1748 + 27` = 1775, inherited from `ed4c67f`, *its* parent — so the
tree it descends from ships 1775. It was therefore taken on a tree one check above that 1775 —
*which* check, and whether it was temporary or simply an interim state of `b023d02`'s own
work, the message does not say, and nothing that survives settles it. That unresolvable basis
is the point, and it is the same working-tree-between-revisions basis that produced the phantom
`1746 + 27` rung below. The figures above are the reproducible form of that claim. The message
is published and cannot be amended, which is why the correction lives here.

The rule this yields is about position, not assertion: **a pin's power depends on the
fixture state at its execution point, and a neighbouring check's setup can silently consume
that state.** The assertion was right the whole time; it was simply standing downstream of
the evidence it needed. Neither re-reading the check nor re-running it in isolation could
have shown this — only reverting the site and watching the pin stay green.

**Failure 6 — the regression no pin could see (a half-applied fix).** The first cut of
§7's Leg B anchored `cost_old` in both readers and left `cost_new` on the bare stem. The
full suite was **green** on that tree. The finding was initially graded *low* on magnitude —
the two costs differ by the anchor text, ~2 tokens — and that grade was wrong for a reason
worth recording: the severity of a token count is not its magnitude but **what reads it**.
Tracing the consumers showed those 2 tokens flip the beacon's `elif cost_old and cost_new !=
cost_old` to **true for every in-sync cross-domain mirror whose domain is two or more
characters long**, because an un-anchored `cost_new` is systematically *lighter* than the
anchored line it is compared against — the anchor then adds ≥4 chars, which always crosses a
`ceil(chars/4)` boundary. A **one-character** domain is the sole exception the domain grammar
admits: the anchor adds exactly 3, and where the bare line's length ≡ 1 (mod 4) the count does
not move at all, so the comparison stays equal and no item is built. The quantifier was too
wide; the mechanism and the direction are not. That
builds a phantom STALE-mirror item whose delta is **negative**, and `_plan_pull` **adds**
deltas to the running index — so the phantom *relieves* the ceiling and books a MISSING fact
as absorbable that a real `--pull` holds. The beacon advertises a pull the run refuses: the
same divergence class the fix exists to close, re-created by half of it.

The repair is structural — both costs now derive from one `_bk`, computed first, so they
cannot be derived from different quantities — and #10 pins it at a **measured** one-token
boundary rather than a plausible one.

**Failure 7 — the field no pin read (failure 6's run-side twin).** #10 pinned the beacon's
`cost_new`; the run planner's stayed unread, and the asymmetry survived a review round for
the same reason a half-applied fix does — the check set *looked* complete. Mutant-measured,
the run-side revert alone (the anchor dropped from the projected cost, `cost_old` still
anchored) left the suite at **1777 passed, 0 failed** — at the 1777-check revision, before #11
existed: entirely green. (The same revert at HEAD's 1778 checks is 1777/1, #11 the sole
failure; the two figures are the same finding at two revisions, not a contradiction.) It was found by
running the mutant the review's own `cost_new` finding implies, at the **second** site that
finding named — the review listed both (`cost_old = line_cost.get(_bk, 0)` in
`session_beacon.py` and `_line_cost_run.get(_j_key` in `sync_global.py`)
and both were fixed in the branch, so only a mutation round could show that one of the two
had no detector behind it.

This is failure 3's shape one layer up. There, a sibling **leg** masked a regression because
another call site produced the correct outcome; here, a sibling **field** masked it because
another index of the same tuple carried the only assertion. Both were invisible to every
outcome-shaped pin, and both were found by reverting one thing at a time and watching.



Full suite per round: smoke / concurrency / simulate_accumulation / mypy / manifests /
browser / pre-push gate; one review agent per PR; the finder re-verifies every fix.

## 10. Ship shape

Additive and backward-compatible — no schema, manifest, or CLI change → **patch**.
CHANGELOG-first.

**Scope: five sites across two files, one PR — not splittable.** The four on the
write/accounting dependency are what forbid the split: the write-side fix alone degrades
the accounting it feeds (§8.2), so a write-only PR would ship a known new defect. The
fifth, the `--gc` dead-probe, is the same root cause reached from a reporting surface; it
rides along with the change rather than being depended upon by it. The dependency decides
the four.

**Repair of an already-damaged store.** The fix converges — `apply_pointer` replaces the
first match and drops the rest, so a store carrying a stale line *above* the correct one
heals to a single line in one refresh. Three limits, all honest:

- **Healing is refresh-gated.** The index temp is staged at exactly one site, the
  `temps[str(idxp)] = idx_text` write under the run-side `if jobs or evict_stem:`, and `jobs`
  is built only for `MISSING`/`STALE-mirror` (`pull_jobs.append(`, `sync_global.py`) — so an
  `in-sync` fact stages no index write and
  a damaged index stays damaged until the canonical next changes. Measured end-to-end: an
  in-sync re-pull leaves a hand-damaged index byte-identical; the next STALE refresh
  converges it to one line.
- **There is no duplicate-pointer detector on the always-loaded index.** Verified across every
  site that parses `](…)` index targets — `memory_status.py`'s `_LINK_RE` (four further sites
  in that module: two set builds, a `search` filter, and a match-count shape test — none
  comparing targets); its **one** importer,
  `extract_signals.py`, which `findall`s the same regex into **set arithmetic**, `arch -
  indexed` — a tier partition that structurally *cannot* see a duplicate, since two identical
  lines collapse to one element before any comparison could run; `index_admission.py`'s
  `_POINTER_TARGET_RE`, a generic `](…)`
  capture used per-target **inside `archive_index`** — never target-against-target *itself*;
  the one comparison of that kind is that same function's `seen` set, which the next sentence
  concedes — and the
  `re.search(r"\]\(([^)]+)\.md\)", …)` call in each of `local_ingress.py`,
  `session_beacon.py`, and `sync_global.py` (which has two: the cost-map build and the
  `mirror_stems` tally) — none compares
  targets against each other. The tree does hold duplicate detectors, and naming them with
  their scope is what makes this sweep checkable rather than asserted: `local_ingress`'s
  `_duplicate_reserved` and `memory_status.frontmatter_duplicate_reserved` both refuse a
  duplicate **reserved key** in frontmatter — a codec concern, never a pointer target. The one
  message that reads like a pointer detector, `archive_index`'s "duplicate archive target"
  (`index_admission.py:98`), governs `SHIPPED.md` — a different file, as its own docstring
  says. A duplicate pointer can therefore persist silently.
- **`cm local rebuild-index --apply --confirm rebuild-local-index` is the immediate
  repair** — it emits one `_pointer_line` per file from a glob, so N duplicate lines
  collapse to 1 regardless of anchors. It is compatible with the fix: it calls
  `_pointer_line(f.stem, fm)` with no anchor, so the mirror key *is* the href, which the
  fixed matcher matches. **Scope it as "per file", not "per canonical"** — that is exactly
  the seam the live-bare-keyed variant below falls through, where two *files* (not two lines
  for one file) yield two lines and nothing collapses. Read the two entries together; they
  are the same sentence read at two scopes.

**The suite-total pin must move in this PR.** `tests/smoke.py`'s D6 anti-rot check pins the
suite's own execution surface (`passed + failed + 1 == N + 28`) so an orphaned section can
never print green. It is a count of the full suite *including itself*, so adding the eleven
checks here without bumping it leaves smoke red — the pin is designed to fail loudly rather
than let the count drift. This change moves it **`1740 + 27` → `1750 + 28`**. The branch's
three check-adding commits carry it as `1748 + 27` (ed4c67f — #1–#8, the write leg and its
accounting, **+8**), `1750 + 27` (b023d02 — #9, the gc-DEAD probe, and #10, the phantom-delta
pin, +2) and `1750 + 28` (eb7f7a0 — #11, the run-side `cost_new` pin, +1).

The check count has a finer grouping than the history does — the first six, then #7/#8, then
#9/#10, then #11 — and an earlier draft of this paragraph quoted it as a ladder, with
`1746 + 27` as its second rung. **That literal existed in no commit**: the first six checks and
#7/#8 landed together in ed4c67f, so `git log -S'1746 + 27' -- tests/smoke.py` comes back
empty. The grouping is real but it is *authorship*, not history, and quoting it as a rung
sends a maintainer auditing the branch to a revision that never shipped. Quote the committed
literals.

**The rule covers derived figures, not only quoted literals, and that distinction is what let
three instances of one basis survive into the review round.** Besides the `1746 + 27` rung
above, failure 5's note compared the 1776 reported *in* `b023d02`'s message against "the 1775
checks that revision ships" (`b023d02` ships 1777), and failures 2 and 3 both date their
measurements to "the revision then shipping 1772 checks" — a total no *revision* carries: no
refs-reachable `smoke.py` blob was left unchecked, and a scan of the **object database**,
restricted to `smoke.py`, finds the D6 literal `1745 + 27` in exactly one blob — the dropped
stash `188a326`, reachable from no ref — which is precisely what makes it a working tree
rather than a revision. In each, a **sum observed in a run** was
**revision's name**. The quoted halves were all correct; only the comparison term was inferred,
which is why reading for wrong literals finds none of them — and why the rule is stated here as
the inference to refuse: *read a measurement's total as evidence of what the tree was, never of
what shipped.* **Only the sum is load-bearing** —
the split between the two addends is bookkeeping, and it is the total that must equal the
reported count (measured at HEAD: `1778 passed, 0 failed` against `1750 + 28`). #11 moved the
*second* addend because no check landed between #10 and it; a maintainer copying either
literal without the other reintroduces exactly the drift this pin exists to catch. Any future
addition to this spec's check set moves it again.

**The second member of §8.2's family — a *live* bare-keyed mirror — is the one input where
the anchored matcher is strictly less tidy. Measured, scoped, and not reachable here.**
§8.2's anti-question names the **dead** bare-stem line: a pointer whose target file is gone.
The other member of that family is a mirror file that **exists**, whose bare key was correct
when it was written, and whose canonical has since moved to another domain. Pre-fix and
post-fix, measured on a probe store carrying exactly that shape:

| after one refresh of the now-foreign canonical | pre-fix | post-fix |
|---|---|---|
| index lines | 1 — the stale bare line, href rewritten in place | **2** — the stale bare line survives, the anchored pointer appends beside it |
| mirror files for that canonical | **2** — the pre-existing `{bare}.md`, plus a fresh `{mkey}.md` (the delivery `path` is keyed by the mirror key at *both* revisions — `path = store / f"{mkey}.md"`, one hit in `sync_global.py`, untouched by this diff) | **2** — the same two files |

The index cell is the only one that moves, and the file cell is a correction review round 2
owes this table: pre-fix is **not** "one line, one file". The delivery path was already
mirror-keyed before this change, so it writes `{mkey}.md` in both revisions; what the bare
matcher did was overwrite the stale line **in place**, leaving the old `{bare}.md` an
**orphan** — on disk, unreferenced. Pre-fix is therefore one correct line beside one
orphan, and post-fix is two lines beside the same two files. The regression is **one line,
not one file**: the stale bare line survives the refresh and its correction appends below
it — §1's exact symptom, in the tier every session pays for. It is the reason the entry is
here rather than omitted. It cannot fire for a canonical that is *already* cross-domain (both
matchers agree there), and it is **not instantiated**: §5's re-key scan found exactly **one**
bare-keyed mirror in the fleet whose key no longer reproduces, and it sits in an *unenrolled*
synthetic QA fixture — local-only, so the delivery path cannot run there. **0 real nodes.**

**A correction owed about the repair path.** The intuitive claim — "`cm local
rebuild-index` clears it, same as the dead variant" — is **false for this shape**.
`_rebuild_plan` (`local_ingress.py:437`) globs `native.glob("*.md")` and emits one
`_pointer_line(f.stem, fm)` **per file**, so with both the bare-keyed mirror and the
namespaced one on disk it plans a line for each; it drops only lines whose target file is
gone (`would_remove_existing_pointers = existing_ptrs - planned`). `--gc` does not reclaim it
either, and for a reason worth naming: the scan that could take it, the `_orphans(...,
pair_keys=True)` call in `sync_global.py`, reconstructs the pair from the **mirror's own
frontmatter** (`canonical_domain` + `name`), not from its filename — so the stale bare-keyed
file resolves to the *live* canonical pair and is correctly classified as neither an orphan
nor FROZEN — `_classify_frozen` returns `None` for an admitted-and-relevant canonical, at the
arm `if is_relevant(c_fm, stacks):` (that arm, not a line number: the first draft cited
`:2907`, which is inside `_mirror_canonical_path`, the function *above* it). In other
words the file is not stale to the classifier; only its **filename and index line** are
stale. **No supported single command collapses this shape** — the repair is two steps
(delete the stale bare-keyed mirror file, then rebuild). Recorded because the simpler claim
is the one a future reader will assume.

**A hazard for the mutation testing this spec relies on:** reverting a site by editing a
script in place and then restoring it with `cp` can be silently defeated by **stale
bytecode** — CPython validates a `.pyc` on source mtime *and* size, so a restore landing in
the same second as a same-sized mutant leaves the mutant's code executing. Observed once in
this cycle (a post-restore run reported 5 failures that three subsequent runs did not
reproduce). Any mutation run should `find . -name __pycache__ -type d -exec rm -rf {} +`
first. Recorded because an unnoticed stale `.pyc` can as easily manufacture a *false
failure* as hide a real one, and §9.1's conclusions rest entirely on mutation readings.

Non-blocking and equally broken before and after: `validate_fact_stem("a--b")` succeeds
and `_mirror_key`'s same-domain arm returns `a--b` without the ambiguity refusal, so
`decode_key("a--b") == ("a", "b")` — a same-domain `--` stem can collide with another
domain's namespaced key. The fix neither causes nor worsens it, and its matcher is
strictly more precise than the bare stem it replaces. Recorded for a future cycle.
