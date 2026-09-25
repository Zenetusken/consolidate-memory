# Marker-coordinate truth — design-of-record

> **Reading the citations.** Every `file:line` below is **`29cdfb33`-numbered**. Resolve it against
> that commit — `git show 29cdfb33:<path>` — and **never against the working tree**, which has moved
> them.
>
> **Re-measuring any number here.** Use `git grep -n <pat> -- ':/'`. A bare `git grep` with no
> pathspec is scoped to the **CWD**, and a pathspec like `-- plugins/…` resolves relative to the CWD
> too — so run from `scripts/` it searches `scripts/plugins/…`, matches nothing, and exits **0 and
> silent**. That zero is not evidence. Three separate absence-readings cost this design real work:
> the CWD-scoped grep (it understated §C5's blast radius by hiding two test lines), a `head -20`
> that truncated a probe into looking empty, and a full-phrase search that failed because the phrase
> **wraps a line boundary** in the source (`store_context.py:1078-1079`). **Search the fragment, or
> strip the seams; never conclude absence from a normalized source search.**
>
> ⚠ **A `git` pathspec is not a shell glob — in both directions.** `*` **matches `/`**, so
> `git ls-files -- 'docs/*.md'` is already recursive (**82**). And `**` is **not special without
> `:(glob)`** — it is another `*`, crossing `/` like the first. What a pathspec constrains is a
> **depth FLOOR**, `NF ≥ (slashes in the pattern) + 1`: every `/` past the literal prefix needs a real
> path segment to meet it. So `'docs/**/*.md'` reads *"`docs/`, then **≥1 more segment**, then
> `*.md`"* → **24** — a plausible-looking number, **wrong by 58**, from the matcher that *looks* the
> most careful. Measured, and it is a floor, not a level: `plugins/**/*.md` → **19** at depths **4, 5
> and 6**; `plugins/*/*/*.md` → 19 while `plugins/*/*/*/*.md` → **5**, exactly the `NF≥5` census (3 at
> 5 + 2 at 6) — the count collapsing the moment the pattern demands a `/` the path does not have. The
> **24** *coincides* with "one level" only because `docs/` holds no `.md` past **NF=3** (58 · 24 ·
> **0**). `:(glob)` is the only recursive spelling — `':(glob)docs/**/*.md'` → **82**.
>
> ⚠ **This revision re-derived its citations rather than transcribing them.** The first cut carried
> **13 wrong `file:line` pointers** out of ~75 — a quote sitting outside its own cited span
> (§C4, §C6, `_parse_ts`), a count whose census named a different population (§4's "56", §5's
> "three", "five"), and a pin cited at a line inside **another pin's block** (§3). A coordinate
> written from a reading pass is **memory, not measurement** — which is this document's own thesis,
> applied to itself.

> ⚑ **Revision note — the design was REFUTED and REPLACED at the first review round.** If you hold an
> earlier revision (`d54d8cea…`, 562 lines), **§2.1 is not the same design**: it admitted a stamp by
> **ownership** (`state.commit == record.commit`) and now admits it by **file identity**
> (`state.timestamp != record.before_timestamp`). Both rejected forms are recorded with their
> refutations in §2.1 — ownership *by* that round's finding, confirmed first-party. Anything you read
> about `_parse_ts` on the admission path, about a *short-hex* ceiling, or about four
> `before_timestamp` spellings being **refused**, describes the dead revision. ⚠ **A finding is bound
> to the revision its hashes name**: re-derive against *this* text, and if a finding was true only of
> the ownership form, say so rather than re-filing it.
> **This revision:** the sha256 on the next line, computed over this file **with that one line
> deleted** — a hash cannot cover its own digits, so the delete-the-stamp recipe is what makes it
> checkable at all. Verify with
> `command grep -v '^> \*\*sha256:' docs/marker-coordinate-truth.spec.md | sha256sum`.
> **Untracked**, so it is a *detector*, not a recoverable coordinate: a report citing it can be
> checked against a file, and nothing on disk can reconstruct the file from it.
> **sha256:** `7caac64c39408636578b53a23f76a6671d84ca63549842c33b152a6838cac3d4` · **1276 lines**, `wc -l` over the **whole file** (the recipe body — the file with this line deleted — is **1275** — name the operand, or the count is the half that drifts: the stamp before this one still read *1252*, and the edits after a stamp are invisible to it) · stamped **last** — every edit after it un-binds the round — and this stamp is **ONE line by construction**: the recipe deletes by line PREFIX, so a wrapped stamp's tail survives into the very body it hashes, which is how the first attempt at this stamp came out self-referential
> this hash names, so re-stamp as the final act before dispatching a review, never mid-edit.
> **What this revision changes** (vs. `aa57f259…`): the **pathspec rule** in the block above — the
> stamped cut claimed `**` matches "**exactly one** directory level", refuted by measurement (it is a
> depth **floor**, `NF ≥ slashes + 1`); §C1's mtime instant (**`17:49:47.736Z`**, never the local
> digits wearing a `Z`) plus its **provenance tier** (testimony — `preflight.run_and_cache`
> demonstrably rewrites the witness file, so the reading is no longer re-derivable); §3 row 1's
> **per-key scope** (a rejected stamp fills **nothing** into `timestamp`; the `commit` is a separate
> fill); §5's completed interpreter bound (both measured arms, `_stale_since` as a **second site**,
> and R1c's widening of reach); §2.1 R1c's **shared-coercion** provenance; and §2.5's
> **behavior-neutrality** measurement (the one live comparison's `rg` is this run's
> `_provisional_rigor(ctx)`, never a stored record).
> The **predecessor's** delta (vs. the pre-stamp cut) was: the R1c mechanism (**coerce, never
> blank** — the first cut's "blanked" was *measured* to re-open the incident on R1c's own target
> input), §5's bound (**ownership, not self-consistency**), §3 row 5's observable (the **value**, not
> the type — it was satisfiable by the defect), and **13 wrong `file:line` pointers** re-derived
> against HEAD.
> ⚑ **Round binding.** The first review round was dispatched against the **previous** revision,
> `a56dacc413e98549f3405ecafb69d2586ca6b4f5ace3561282bff749a09baa1b`, which **predates** the
> two-route correction to the admission vocabulary (§2.1's arm table, §3's pin guidance, §5's
> ceiling, Acceptance). That text is frozen byte-for-byte at **`/tmp/cm-spec-a56dacc4.md`**, where
> the recipe above verifies unchanged. **The copy is the only recovery**: an untracked artifact's
> hash names bytes nothing on disk can reconstruct, so a round worth auditing is worth freezing
> before the next edit — which is the operational form of *a finding is bound to the revision its
> hashes name*.
> ⚠ **The second round (rev4) was dispatched mid-edit and its revisions were NOT frozen.** It read
> `91479e82…` at 771 lines and re-anchored to `fcd36eb2…` at 814 as the file moved beneath it; those
> bytes are now **unrecoverable**, so a `file:line` in that round's report cannot be resolved against
> any text. Its findings survived anyway — adjudication is **first-party against HEAD**, and every one
> was re-derived from the source rather than from the report. ⚠ **And note the operand split:** a
> reader's `sha256sum` of the **raw** file and this note's stamp (the **recipe** — stamp line deleted)
> are **two different operands and never comparable.** That alone explains a hash disagreement that
> looks like a content disagreement; **state the convention whenever a hash is quoted.**

**Status: SHIPPED (v0.4.41)** — verified against `CHANGELOG.md` §v0.4.41, which names this spec. ⚠ This arm needed no citation: the header named a TARGET RELEASE that had already shipped.

> **Drafting-era status — never revisited after the arc closed.** Preserved VERBATIM (the class is now gated by `tests/docs_links.check_spec_status`):
>
> **Status: revised for review.** Target release: **v0.4.41 (patch)** — it adds no `CycleRecord`
> field, removes and renames no flag, and leaves legacy records rendering (§4, Contract impact). It
> makes `--persist` exit **5** on a stamp it currently accepts; that exit is already the documented
> arm for that state (§2.1).

This spec closes the defect class that produced the 2026-09-21 cycle incident: **the persist
identity is a coordinate the record does not own.** One repair is load-bearing (§2.1); the rest are
operand and naming repairs found while tracing it.

## §1 Context (measured)

### C1 — the incident

A dream pass ended with `--persist` **rc=0 and no log line**; the operator hand-fixed the marker,
and the same cycle then produced **two** lines. The chain is fully traced:

1. `memory_status.seed_record` (`memory_status.py:3535-3537`) seeds the record's marker with
   `commit = ctx["head"]` (**filled**) and `timestamp = ""` (**empty** — *"stamp at write time in
   Phase 5"*), beside `before_commit`/`before_timestamp`, the **previous** cycle's pair.
2. `reconcile_marker` (`memory_status.py:2197-2221`) fills empty fields from
   `<store>/.consolidation-state.json`. Its `commit` fill is `_valid_sha`-gated; its `timestamp`
   fill is **ungated and unconditional** — and the source **says so**, in as many words: *"the
   timestamp fills unconditionally"* (`:2215-2217`, the `v0.4.21 (D1, amend-3 R3)` comment). So this
   is not an oversight hidden in code — it is a **written-down asymmetry** whose consequence
   (mixed-epoch coordinates) was not foreseen. That makes the comment itself a repair site: R1a
   falsifies it (§2.1 R1e).
3. The pass had not re-stamped, so the state file still held the **previous** cycle's pair,
   `2b07ce345dd6578e073599f0ac8c93ec43fd17a0 / 2026-09-15T14:16:11.649Z` — which is itself the
   previous cycle's own log line: **1-based line 23** of the project-id-keyed
   `.consolidation-log.jsonl`, the rung `cycle_log_read_paths` reads *last*. Identified by content,
   not by index: it is the **only** line in that log whose marker pair **is** the pair the state file
   holds. **Measured at the incident, and deliberately not re-derived since:** `stat` gave
   `2026-09-21 13:49:47.736 -0400` — a **local** reading, whose UTC instant is
   `2026-09-21T17:49:47.736Z` — **unchanged across the whole incident**, which independently
   confirms *"the pass had not re-stamped."* ⚠ **The interval is the evidence, so the zone is
   load-bearing:** 17:49:47Z is **53m52s** before the `18:43:39Z` persist — the "54 minutes" this
   incident is described by elsewhere in this arc — where the local digits wearing a `Z` (an
   earlier cut of this line read `2026-09-21T13:49:47Z`) would place it ~5h before, contradicting
   the item making the claim. ⚠ **Do not re-derive this mtime, and do not read it as still true.**
   The state file has writers besides a stamp: `preflight.py:489`'s `run_and_cache` (*"ONE
   writer"*) merges its verdict cache through `control_plane.update_project_state`, rewriting the
   file and moving its mtime while leaving `commit`/`timestamp` alone. Measured at HEAD: a
   **fresh inode**, birth == mtime `2026-09-21T22:49:03Z`. The durable half of this witness is the
   **content**: the pair is still on disk.
4. Filling that timestamp onto this cycle's **seeded** commit minted the chimera — this cycle's
   coordinate wearing the previous cycle's time, a coordinate that never existed — **and it is still
   on disk: 1-based line 24**, marker `29cdfb336d1894… / 2026-09-15T14:16:11.649Z`, `entries` **2**,
   no `dream` key. **Its fingerprint is measurable: `timestamp == before_timestamp` is `True` on line
   24 and on no other line of *either* log.** That is the fill's signature rather than a coincidence —
   the seed writes `before_timestamp = ctx["last_ts"]` (`:3536`) and `ctx["last_ts"]` is read from
   that same state field (`:3070`), so an admitted stamp re-appears as the record's own baseline.
   **This measurement is C2's premise, verified.** (Index convention: 1-based, matching the cycle
   display numbering — `dashboard.sections.js:433` `'Dream '+(index+1)`, `:438` `[i+1,`.) Line 24 is
   the **S1** target; the hand-fixed re-run is line 25 (`…/ 2026-09-21T18:43:39.729Z`, `entries` 10,
   `dream` present), the strict superset — so one cycle now wears two identities.
5. `render_dashboard._persist` dedups on the **pair** (`:1577`) and keys the usage clock on the same
   pair (`:1613`). Two runs of one cycle mint the same chimera ⇒ the clean run is suppressed as
   `"duplicate"` ⇒ **exit 0, no log line** — verbatim the failure `reconcile_marker`'s own docstring
   (`:2199-2202`) says it was written to prevent. ⚠ **The suppression is what makes this expensive
   rather than untidy: the second run reports success.**

> ⚠ **The read path is a three-rung ladder, and only its last rung is live.** Measured
> (`retention.cycle_log_read_paths` → `[native, slot, pid]`, *"last wins"*): native **30** lines
> `2026-06-18 → 2026-08-31`, slot **4** lines `2026-09-01`, pid **25** lines `2026-09-01T20:59 →
> 2026-09-21`. All three exist; they are **chronologically contiguous and non-overlapping**, each
> dying where the next begins. So *"last wins"* and *"live"* coincide — but they are **different
> claims**, and reading rung 0 gives a confident **false negative**: it does not contain the
> before-stamp at all. That is not hypothetical — it made S1 read FALSE once already, which is why
> every index above is bound to a **content** mark.

### C2 — the fill cannot tell a source from a leftover

The function's contract is *"fill EMPTY commit/timestamp from the stamped marker FILE — the single
source."* A file that has not been re-stamped since the last cycle is **not** a source for this
cycle; it is the previous cycle's answer.

**Two premises this design rests on, stated because neither is self-evident and the first cut left
both implicit:**

- **`before_timestamp` *is* the state file's stamp.** `:3063` `last_commit = last_ts = ""`; `:3070`
  `last_commit, last_ts = st.get("commit", ""), st.get("timestamp", "")` — read **unconditionally**
  from `state_path = auto_mem / STATE_FILE`, with no log fallback; `:3281` `"last_ts": last_ts`;
  `:3536` seeds `before_timestamp = ctx["last_ts"]`. So the record's baseline and the file the fill
  reads are **the same field of the same file**, and `record.before_timestamp == state.timestamp`
  means nothing rewrote the file between seed and fill — the **identity** case, not a coincidence.
- **The commit half is *not* a second tooth for the timestamp half.** They descend from one writer
  (`stamp_project_marker`, `:2181-2183`) but they **split at the fill**: a state file holding
  `{"commit": "HEAD", "timestamp": T}` yields `{commit: "", timestamp: T}` — the timestamp is
  admitted and the commit refused by `_valid_sha`. Measured **identical on both trees**. §2.1's R1c
  owns this asymmetry; **R1d's third row** owns what a half-stamp costs `--audit` (a row whose identity
  is a lost coordinate).

The tooth the `commit` branch has and the `timestamp` branch lacks is therefore **not** freshness —
it is **provenance**: is this stamp *this cycle's*?

| field | today | what is missing |
| --- | --- | --- |
| `commit` | resolved at write (`:2172-2175`), `_valid_sha`-gated at fill (`:2218`) | — (has its tooth) |
| `timestamp` | copied verbatim, unconditionally | (a) **provenance** — has the file moved *since this cycle began*? (b) **type** — the tooth stringifies for its *test* and then copies the **raw object** |

### C3 — what did NOT happen (two retractions, recorded so they are not re-walked)

**C3a — `--persist` does *not* write before its gates.** The ordering is a documented, oracle-pinned
contract: `render_dashboard.py:2013-2020` states *"Strict order print → persist → exit"*, and the
beta oracle `plugins/dream-beta-tester/scripts/beta_checks.py` (`CHK-PERSIST-GATE`) asserts
`rc1 == 4 and n1 == 1` — *a short-arc record must PERSIST exactly one log line and exit 4*.
`tests/smoke.py:17174-17184` (F19B — ⚠ the exit-**3** pin; `:17161-17173` is F19A's *exit-4* pin)
likewise relies on an exit-3 run appending. The asymmetry observed in
the incident is C1's dedup, **not** the ordering. **No repair.**

**C3b — the demotion docket does *not* self-erase when a pass reads its own candidates.** The record
that carried the false claim is the evidence: its `demotion.surfaced` still holds **both** stems, its
`struck` key is **absent**, and its `usage.per_fact` is **empty** — the dream's reads were excluded
by `split_dream_span` from the organic panel, and the strike set is built from the same usage block,
so **nothing was struck** (`inject_usage`, `extract_signals.py:820-851`, *removes* a struck stem from
`surfaced`; both are still there). The exclusion is **symmetric**. The self-erasure that *is*
documented is the **mtime clock restart** on an edited candidate — deliberate, in a fact that carries
a standing *"do NOT `--force`"*.

**The record's authority for the false mechanism is a second defect.** It grounds the claim on
`demotion-gate-calibration-is-cadence`'s *"own thesis"* — but that fact's *"Self-erasing triage
(verified 2026-09-12)"* section describes the **clock restart** (`zrw = sum(1 for s in starts if s >=
mtimes[stem])`, where `mtimes[...]` is `f.stat().st_mtime` — `memory_status.py:2478`, compared at
`:2491`), a *different* mechanism. ⚠ Measured while correcting this: that fact's mtime is
**2026-09-12**, nine days before the incident, so **neither** named mechanism can explain the refusal.
A fact's authority is a citable surface; citing one for something it does not say is how a false
mechanism acquires standing it was never granted.

> ⚠ **A correction the durable log needs and cannot carry.** The cycle record's Phase-5 verdict
> asserts the false mechanism — *"The seed's surfaced pair was STRUCK by `extract_signals.inject_usage`
> … and `--justify-demotion` then refuses both"* — and cites `memory_status.py:188`, which is the
> `struck` **TypedDict declaration**, not the logic. The log is append-only; this spec's Context is
> where the correction lives so the next reader does not re-derive the claim. **A diagnosis recorded
> as a measurement is the same defect as a measurement recorded wrongly.**

### C4 — `--audit`'s positional is an unvalidated operand

`audit_snapshot(project_dir)` derives all three roots from the positional (`:2745-2811`). Given a
**store** dir, all three resolve empty and every snapshot entry reads as **deleted** — a confident
bogus census, injected into the record and rendered. The operand is unvalidated — the pool is
`:4924-4933`, and the line that consumes it is `:4934` (`project_dir = Path(pos[0]) if pos else
Path.cwd()`) — and `resolve_store` is **non-strict** (no `exists()`/`is_dir()` gate on `project_dir`;
the rule is stated outright at `sync_global.py:5269`, *"resolve() is non-strict"*), so a wrong
operand resolves to a **phantom slug**.

⚠ **The phantom is minted in the `--diffs` arm, not by `--audit`'s mkdir.** `memory_status.py:5169-5171`
(`_mlog.parent.mkdir`) resolves through `mutation_log_write_path` → `operational_dir(plugin_data /
"ops", key)`: it creates a **plugin-data** ops dir keyed by the phantom slot and nothing on the
native plane — measured with an isolated `HOME`, `~/.claude/projects/` did not exist at all. The site
that mints a native-plane tree under the phantom slug is **`:5343-5344`**, in the `--diffs` arm:
`_d = diffs_dir(project_dir)` (`:5343`) then `_d.mkdir(parents=True, exist_ok=True)` (`:5344`) →
`…/projects/<phantom-slug>/dashboards/diffs`. **A placement argument for "the phantom must not be
created" is an argument about `:5344`, and it must precede the `--diffs` arm too.**

**The precedent already exists, one module over, with the rationale written out**
(`sync_global.py:5268-5279`): *"a TYPO'D PROJECT_DIR must never mint a phantom store. resolve() is
non-strict, os.walk on a missing dir is silently empty, and --pull's store.mkdir would then create a
store under the bogus slug … Refuse EVERY project-dir mode up front."* The rule R2 copies is the one
`store_context.py:1075-1079` states as a producer's invariant: *"Never treats `native_memory_dir` as
a project root (that minted a different project id)."*

### C5 — `prune_reason` names the *target* rung "budget"

`prune_pressure` (`:807-816`) returns `"index-over-budget"` when the index exceeds
`INDEX_TOKEN_BUDGET` — the **1500 target** — while `INDEX_CEILING_TOKENS` (3840) is the second rung,
reported separately as `remediation.over_ceiling`. So one record carries
`prune_reason: "index-over-budget"` beside `over_ceiling: false`, and "budget" is the word the
ladder reserves for the *whole* two-rung ladder. **Measured cost:** this design's own triage
mis-read it, taking "over budget" for the ceiling. Blast radius (measured, `:/`-scoped): three sites
in one file — `:813` producer, `:4621` comment, `:4623` the only value-comparison; plus
`tests/smoke.py:235` (twice) and `:238`. Two frozen files are **not** touched — one by
construction, one by choice: the vendored `canary-v0.1.19` copy (byte-faithful to the tag,
SHA256SUMS-manifested) and `CHANGELOG.md:6058` (history; the log is not rewritten).

⚠ **There is no "declared set" of `prune_reason` values in the code.** The token is produced at
`:813`, compared at `:4623`, and printed elsewhere; `PRUNE_PRESSURE_FACTS` (`:787`) is a *count*, not
a set. Any check asserting "the token is drawn from the declared set" has no referent — see §3 row 12
for the form that actually flips.

### C6 — a comment names a consumer that does not exist

`_ui.py:165-166`: the wide-glyph range is *"exposed by name so the arc-completeness check and any
future content lint share ONE range"*. (`:164` is `_WIDE_RE = re.compile(…)`; the sentence spans
`:165-166`.) `arc_completeness` (`memory_status.py:4065-4113` — `def` at `:4065`, last statement at
`:4113`, blank lines to `:4115`, next `def` at `:4116`) never references `BEAT_EMOJI_RE`; the
range's only consumer is an **advisory render warning** (`render_dashboard.py:1239-1243`) that moves
no verdict and no exit code. Note the comment's two clauses have **different scopes** — the first
(the contract bans emoji in non-bookend beats) is a true claim about the SKILL-level contract; only
the second names a consumer.

## §2 Design

### 2.1 R1 — the stamp must qualify as a source (THE fix)

**R1a — admission asks whether the FILE has changed, not whether it is recent.** `reconcile_marker`
gains one predicate, and the loop gates **each key on its own tooth**:

```
def _admit_stamp(record, state) -> bool:
    stamp = str(state.get("timestamp") or "").strip()
    if not stamp:
        return False                                        # nothing to admit
    prev = str(record.get("before_timestamp") or "").strip()
    return not prev or stamp != prev                        # refuse the seeded pair itself

for k in ("commit", "timestamp"):
    if not str(out.get(k) or "").strip() and str(state.get(k) or "").strip():
        if k == "commit":
            if not _valid_sha(str(state.get(k))):           # unchanged from :2218
                continue
        elif not _admit_stamp(out, state):
            continue
        out[k] = str(state[k])                              # R1b — coerce, never copy the raw object
```

**What the predicate is actually asking.** `reconcile_marker`'s contract is *"fill EMPTY
commit/timestamp from the stamped marker FILE — the single source."* A file is a source for **this**
cycle only if it has been **written since this cycle began** — and that is directly testable, because
`before_timestamp` **is that same file's timestamp as read at Phase 0** (`:3062` `state_path = auto_mem
/ STATE_FILE`; `:3070` reads it; `:3536` seeds it), while `reconcile_marker` reads that same file
(`ctx["auto_mem"]`). The two operands are therefore **one field of one file, at two moments** — a
change-detector, not two proxies for one fact. `stamp_project_marker` writes
`iso = timestamp or _utc_iso_now()` (`:2171`) and is the **sole** writer of the state file's
`timestamp` (its only sibling writers touch other keys — `sync_global.py:1726-1733`
`stacks`/`stacks_at`/`project_path`; `preflight.py:500` the verdict cache; `store_context.py:98`
`update_project_state(ctx, _mut, no_mint=True)` — ⚠ which writes **`_warned_unenrolled`** (`:92`),
*not* `project_path` (`project_path` has **0 hits** in that file; its writer is `sync_global.py:1732`,
inside the range named above); `memory_status.py:2301`/`:2405`
`demotion_justify`/`stamped`/`skipped`), so **every** write moves the value. Equality therefore means
*untouched since Phase 0* — which is precisely the incident.

⚠ **The precondition that sentence rests on, stated because nothing enforces it at the fill site.**
"One field of one file" holds only while `reconcile_marker`'s `store_dir` **is** the directory the
seed read from. It is a **carried** operand, not a derived one, and the two callers pass different
kinds of value. Measured: the SKILL passes the native store (`SKILL.md:1275-1277`,
`--persist "<native_memory_dir from Phase 0 / cm doctor>"`) and `_context_for_store`'s contract is
*"the StoreContext whose `native_memory_dir` IS `store` — or None"* (`render_dashboard.py:593-641`,
enforced by `native_memory_dir.resolve() == store.resolve()` at `:630`/`:637`) — **but that helper
serves only the unenrolled-share *warn*** at `:1992`, itself inside `try/except Exception: pass`.
The `_persist` call at `:2021` runs on any directory, and a `--persist <some-other-store>` reads
*that* store's state file. So the precondition is a documented convention, not an invariant.
**Both divergent outcomes are safe**, which is why this is a stated precondition rather than a new
repair: two different stores can hold equal stamps only by coincidence (both stamped inside one
millisecond), and if they do, the refusal is *correct* — that fill would have come from the wrong
file. Every other divergence lands on *not equal ⇒ admit* — **a comparison that concluded
"differs", not a vacuous arm** — which is today's behaviour. ⚠ But the predicate's **meaning**
degrades from a change-detector to a coincidence test,
and a reader who assumes the precondition will mis-state what equality proves. §5 carries the same
operand as a ceiling.

**Why string equality, and not a comparison.** Equality needs no parse, and that single choice removes
three failure modes at once:

- **No wedge.** A re-stamp writes a *new* `_utc_iso_now()`, so the printed remedy clears the refusal
  **with no assumption about HEAD**. (The one way a re-stamp can write an *equal* value — a collision
  — is measured and bounded in the residual below; it is not a wedge, and the distinction is that the
  remedy's operand is the very field the predicate reads.)
- **No interpreter dependence.** `_parse_ts` is off this path entirely, so F4's 3.10-vs-3.11
  `fromisoformat` split cannot move a persist verdict.
- **No magnitude comparison across a fractional-seconds boundary** — `"…11Z"` sorts *above*
  `"…11.649Z"` lexically, which is why a naive `>` on ISO strings is wrong.

**The two rejected forms, and why — measured, not argued.** Each looks *stronger* than equality, and
each fails on the axis the other survives:

1. ***Freshness* — admit only when `state.timestamp` is strictly newer than `before_timestamp`.** The
   tempting form, because it names the defect (*"too old"*). Refuted on four independent axes:
   (a) `:3081-3088` hardens `last_commit` — `if last_commit and not _valid_sha(last_commit): warn +
   last_commit = ""` — under a comment about *"a tampered/garbage state file"*, while **`last_ts` gets
   no validation and no warning three lines away**, so `before_timestamp` carries four spellings
   (absent, `""`, the SKILL's placeholder `"<prev marker ISO>"` at `SKILL.md:1660`, and junk) that all
   leave freshness with no usable comparison — ⚠ **the dead design's arm, since freshness *parsed***:
   under the live predicate the same four **split two ways** (absent/`""` → vacuous;
   placeholder/junk → compared-and-differs — see §2.1's arm table, and note this sentence contradicted
   the corrected vocabulary eight lines below); (b) because the second operand *is* the file, `state_ts > before_ts`
   degenerates into *"did the file advance mid-cycle"*, so an interleaved stamp from another session
   makes it **true for a stamp that is not this record's** — it can *assemble* a chimera, not merely
   fail to stop one; (c) **its remedy cannot clear its refusal** — measured end-to-end, a
   future-skewed `before_timestamp` exits 5, the printed remedy re-stamps the file to *now*, and the
   next `--persist` exits **5 again, forever**, because no re-stamp can beat a future baseline;
   (d) `_parse_ts` → `datetime.fromisoformat` is **interpreter-dependent** — `"20260921"`,
   `"20260101T1200"`, `"2026-W38-1"` return `None` on 3.10 and a `datetime` on 3.11–3.13, and CI runs
   both sides of that boundary.
   ⚠ Note what equality keeps from (a) and drops from (c)–(d): the four spellings all still resolve to
   *admit* — two by **vacuity** (absent, `""`), two by **difference** (placeholder, junk) — while
   **parsing — the source of both the wedge and the version split — is gone entirely.** Equality is
   the *subset* of freshness that needs no clock.

2. **⚑ *Ownership* — admit only when `state.commit == record.commit`.** This was this spec's design
   through its first review round, and it is **refuted**, by the very disqualifier the spec used on
   freshness. The two commits are taken from `git rev-parse HEAD` at **two different moments**:
   `record.commit` is frozen at seed time (`:3091` `head = _run(["git","rev-parse","HEAD"],
   project_dir)`; `:3537` `"commit": ctx["head"]`) and **nothing in the tree ever rewrites it**
   (census: `git grep -n 'marker\["commit"\]' -- ':/'` → **no hits**, rc=1), while `state.commit` is
   resolved at **stamp** time (`:2143`/`:2152` `--verify <commit>^{commit}`, reached from `:2172` —
   ⚠ `:2146`/`:2156` are the *unborn-HEAD* guard that shadows them, not the resolution). So an ordinary
   commit landing mid-pass makes them differ → **refuse**; and the printed remedy re-stamps to the
   *new* HEAD → **refuse again**, permanently. The input is not exotic: `SKILL.md:1157-1160` says
   *"Best avoided by **not committing to the repo while a dream runs** … If HEAD moved, say so"* — the
   environment is told to **report** a moved HEAD, never to refuse it.
   Two further scars: it compared two **independently-encoded** hex strings byte-for-byte, so `H0[:7]`
   and `H0.upper()` were refused although both name the same commit (`_valid_sha` *admits* 7–40 hex,
   so a short commit is not on a no-coordinate arm — it is on the comparison arm, where it fails); and
   it consulted the record's commit *at all*, which is what forced a special-case arm for records with
   no real coordinate.
   **A commit is not a per-cycle witness.** It repeats across cycles whenever the repo is idle, so an
   equality test on it cannot separate a fresh stamp from a leftover — which is exactly why freshness
   must be witnessed by the one field a stamp is guaranteed to move.

⚠ **This is the round's headline retraction.** The spec's own stated test for a repair is that **the
remedy must move the operand the predicate reads**. Ownership failed that test — on the same axis it
was used to disqualify freshness. That is the clearest evidence available that the test was written
down before it was applied.

**Every arm, against the measured table:**

| input (`record.timestamp` empty throughout, so the fill is entered) | verdict | note |
| --- | --- | --- |
| the incident — `before_timestamp = 2026-09-15T14:16:11.649Z`, file still holds that exact stamp | **refuse** | the fix: the file is untouched since Phase 0 |
| `before_timestamp` absent or `""` | **admit** | no baseline ⇒ nothing to compare (the first-run arm) |
| `before_timestamp` = the SKILL placeholder, junk, or a future skew | **admit** | a non-empty string that **cannot equal** the file's stamp — refusal needs equality; whether a parse happens is irrelevant either way |
| mid-cycle advance — another session stamped the file | **admit** | the file genuinely moved: the case ownership *refused* and freshness admitted for the wrong reason |
| healthy cycle — *this* pass re-stamped the file | **admit** | the ordinary case, unchanged from today |
| `record.timestamp` already non-empty | *(fill not entered)* | the outer guard at `:2214`; unchanged |
| no state file / non-dict / unreadable | **admit**, on an empty `state` | `:2206-2212` unchanged — the no-raise pin at `:3340-3353` still holds |

⚠ **The residual, stated rather than papered over:** equality is a **collision** test, so it can
refuse a stamp that is *fresh but byte-identical* to `before_timestamp`. That requires
`_utc_iso_now()` to return the same value twice — it truncates to milliseconds (`:2122`,
`f".{dt.microsecond // 1000:03d}Z"`) — so it is reachable only by two stamps inside one millisecond,
or by a caller passing an explicit `timestamp=` (exactly one such route exists: `cm_ops.py:1061`,
`cm marker stamp --commit SHA --timestamp X`).
Both are benign, and **neither is a wedge**: the first is an interleaved concurrent stamp, which is
the case a refusal is defensible for; the second writes a coordinate that genuinely did **not** move,
so refusing it is *correct* rather than a false refusal. **And the printed remedy clears every one of
them** — `--stamp-marker HEAD` (`:4979`) passes `commit=` and `standing_justify=`/`snooze_until=` but
**no explicit `timestamp=`**, so `iso = _utc_iso_now()` yields a new value on each invocation. That is
the measured difference from freshness, whose remedy re-stamps a field its predicate never reads.
A record whose `commit` is short, absent, or non-hex is *irrelevant* here rather than admitted
unconditionally: the predicate never consults the commit at all — which is why `:3346`/`:3349` and
P15 now stay green for **one** reason instead of three separate ones.

**R1b — the copy is a coercion, not an assignment.** The tooth validates `str(v)`; the copy was
`out[k] = state[k]`, the **raw object**. Measured: a state file holding a JSON **int** stamp
(`{"timestamp": 20260921}`) persists that int — into the log line and the cycle file — feeding
`cycle_id = f"{commit}|{ts}"` (`render_dashboard.py:1613`), `render_html._fill_timestamp`, and the
archive. `str()` was used as a **filter**, never as a coercion. `out[k] = str(state[k])` closes it.
(This is a *different home* from R1a's predicate: R1a decides **whether**, R1b decides **what type**.)

**R1c — the seed's asymmetry.** `:3070` reads `last_commit, last_ts` from the same JSON object;
`:3081-3088` then validates `last_commit` and **warns**, while `last_ts` passes through untouched.
⚠ **The two fields do not have the same motive, and the repair must not pretend they do.**
`_valid_sha` guards an **argument-injection** path — the commit is passed to `git` as an argv element,
so *"a value like `--output=…` would be read by git as an OPTION"* (`:3076-3079`). `last_ts` reaches
no subprocess; its consumers are the narration window anchor (`render_dashboard.py:1963`) and the
archive's **display** fill (`render_html.py:189`), so a junk `before_timestamp` lands in a rendered
fallback as a truthy string. The symmetric tooth is therefore a **type** check, not a grammar check:
`last_ts` is **coerced** to a `str` — `str(last_ts or "")`, the expression **both** of its own
consumers already apply at their first step (`render_dashboard.py:1963` verbatim;
`render_html.py:189` the same `str(... or "")` and then `.strip()` — the coercion is shared, the
strip is that site's own), and exactly R1b's concern
one layer up; it catches the JSON-**int** stamp (`{"timestamp": 20260921}`) that R1b exists to coerce.
⚠ **Not *blanked*** — the first cut said "blanked", and measurement shows the two spellings
**disagree on R1c's own target input**. A blanked baseline makes `prev == ""`, which lands on the
*vacuous-admit* arm and takes the file's possibly-stale stamp: with a JSON-int state stamp, KEEP (raw
int) → refuses ✓ while BLANK → admits ✗, re-minting the chimera. `or ""` is load-bearing —
`str(None)` is the truthy junk string `"None"`, a worse baseline than an absent one.
Deliberately **not** a `_parse_ts` grammar gate, and ⚠ **for a stronger reason than the first cut
gave.** The tempting move is to reach for the timestamp parser as the symmetric tooth to
`_valid_sha`. Measured on **Python 3.10.12**: `_parse_ts` **raises `AttributeError`** on a non-`str` —
`_parse_ts(20260921)` → *"'int' object has no attribute 'replace'"* — because `if not ts` passes a
truthy int through to `ts.replace(...)` at `:943`, which sits **outside** the `try` that guards only
`fromisoformat` (`:944-947`). So the parser the asymmetry seems to suggest is **not safe against the
exact input the asymmetry is about** (R1b's JSON int).
**And the asymmetry is one level deeper than "one field is hardened and the other is not":** the
hardening primitive that *exists* is documented crash-safe — `_valid_sha`'s docstring says
*"Non-strings … are invalid, NOT a crash — the guard must degrade to no-marker, never take the whole
run down (pentest)"* (`:967-968`) — while its natural timestamp analogue is **not**. Adding a
`_parse_ts` gate would therefore import a *crash* into the seed path in the name of symmetry: the
repair would be less safe than the hole it closes. A `str` type check has neither that hazard nor
§5's 3.10-vs-3.11 `fromisoformat` split.
Scope it honestly: **this is a display-identity repair, not part of the incident's closure.** R1a does
read the field — but only strips and string-compares it, so the **verdict is identical** whether the
seed keeps the raw value or **coerces** it: the predicate `str()`s *both* operands, so `20260921` and
`"20260921"` are compared in one form and give one verdict either way. Its pin is scoped to the seed's
output, never to `--persist`.
⚠ **That identity is exactly why it must not *blank*.** The first cut said "keeps or blanks it", and
that is **false on R1c's own target input**. Blanking does not preserve a baseline, it *removes* one —
and a non-`str` baseline is **not** a non-match. With a JSON-int state stamp, `str(20260921) ==
"20260921"` **matches** and correctly refuses, while a blanked `prev` lands on the *vacuous-admit* arm
and takes the file's possibly-stale stamp — the chimera. The two spellings agree on junk **strings**
(both non-match, both admit) and **disagree on the non-`str`**, which is the only input this repair is
about. **Coerce; never blank.** Measured both ways (§3 row 5).

**R1d — the three refusals must name their own cause.** R1a routes a **new** cause into arms whose
messages assert the **old** one:

| site | today's message | why it is now false |
| --- | --- | --- |
| `render_dashboard.py:2023-2024` | *"no marker.timestamp in the record **and no stamp in `.consolidation-state.json`**"* | the file may hold a stamp refused for *being the cycle's own baseline* — the panel asserts absence where the cause is refusal |
| `memory_status.py:5330` | *"--diffs: skipped (cycle unstamped **and no state-file stamp**)"*, then **`return 0`** | same false clause — and it is a **silent** loss at exit 0 |
| `memory_status.py:5104` (`--audit`) | *(writes a row)* | a row whose identity is a lost coordinate is a refusal recorded as a nameless row |

**R1e — and the source comment R1a falsifies.** `:2215-2217` says *"the timestamp fills
unconditionally."* Under R1a that sentence is **false**, and it sits three lines above the code it
describes — so leaving it is not a stale note but an actively misleading one, on the exact line the
next reader will consult to understand the predicate. Rewrite it to state the admission rule — the
timestamp fills only when the file has *moved since Phase 0* — and why the chimera is what that
refuses. ⚠ **This is the same class as R6, with the sign flipped:** R6 corrects a
comment that is *already* false; R1e corrects one the repair *makes* false. A diff's own prose is an
unaudited surface — the code change and the sentence describing it land in the same commit, and only
one of them is exercised by the suite.

⚠ **This is the repo's own named rule, in the same function, eight lines below the break.** The
neighbouring `--diffs` block (`:5335-5339`) says: *"A named path that could not be read … is a
different cause and used to wear this same sentence — a remedy naming a cause that did not happen.
**An instrument's fault and its verdict must not share one message: the reader of that line cannot
tell which one it got.**"* R1 reintroduces exactly that pattern; R1d removes it. **And the remedy
must clear the refusal** — under the identity predicate it does, on every route, because the remedy
writes a *new* `_utc_iso_now()` and the predicate reads exactly the field that remedy moves. That is
the test ownership failed, and it is worth stating plainly that it failed it on **its own** axis:
ownership's operand was a commit, and its remedy set that commit to a HEAD that had moved.

**Why exit 5, and why that is not a new contract.** A refused stamp leaves the record unstamped and
`_persist`'s existing arm fires — `if not ts: … return "unstamped"` (`render_dashboard.py:1570-1573`)
— which the exit ladder turns into **exit 5**. ⚠ **Caveat, corrected from the first cut:** reusing
the arm also reuses its *message*, and the arm's own coverage (`tests/smoke.py:3419-3426`) pins the
**no-state-file** cause. Inheritance of coverage is not inheritance of honesty — hence R1d.

**Blast radius — three callers, three *different* required outcomes.** The first cut measured this as
"zero across the suite" and named the sites without their consequences. They diverge:

| caller | today | under a refusal | required |
| --- | --- | --- | --- |
| `render_dashboard.py:1566` (`--persist`) | exit 5, no append | exit 5 | loud, cause-named (R1d) |
| `memory_status.py:5328` (`--diffs`) | writes the diff sidecar | **silent loss, `return 0`** | cause named on stderr; **`return 0` KEPT** — see R1d, applied |
| `memory_status.py:5104` (`--audit`) | row with full identity | **commit coordinate lost; `supersedes` dropped** | must not lose the coordinate (R1a's per-key gate) |

⚠ The third row is why the loop gates **per key**: gating both keys on one timestamp predicate is
what costs `--audit` its commit coordinate, and what silently drops the correction-pair relation
(`supersedes` is written only `if _supersedes:` — `:5173-5174` — and `""` is falsy).

**Suite blast radius — every fixture that can reach the fill, derived rather than recalled.** By name:
`:3346`, `:3349`, `:3351`, `:3353` — four calls, one block, all in `tests/smoke.py`. ⚠ A text matcher
returns **six** hits in that file; two are **comments** (`:3340`, `:19144`), which is how a census
reads prose about its subject. Through `_persist` → `_reconcile_marker`: `simulate_accumulation.py`
`:454`, `:455`, `:456`, `:460`, `:472`, `:479` and `smoke.py:8373`. **Every one** either omits
`before_timestamp` or already carries a non-empty `timestamp`. ⚠ `_wr19`'s 14 calls
(`:17163-17447`) **do** carry `before_timestamp` — they are unaffected because their `timestamp` is
non-empty, so the fill is never entered, not because the field is absent.

**No fixture in the repo has the incident's shape** — an empty `timestamp` beside a `before_timestamp`
holding **the state file's own value**. That absence is why the defect survived to production, and it
is why pin 1 is discriminating: it is the first occupant of that cell. P15 (`:19147-19167`) comes
closest, and it takes **two** lines to read it correctly: `:19153`
(`_blk15["marker"]["timestamp"] = ""`, *"every pre-heal write's shape"*) is what **enters** the fill,
while the seed at `:18946` — whose marker carries a *non-empty* timestamp — supplies the **absence**
of `before_timestamp` that routes it to the vacuous arm. ⚠ Naming `:18946` alone invites the
opposite reading, because that line by itself looks like a fill that never happens. Which is also
why pin 1's fixture must write the *same string* to both places, not merely a similarly-shaped one.
⚠ **Under the rejected ownership predicate the sentence above read differently** — it named a real
40-hex commit as the requirement, because that predicate compared commits. The requirement moved with
the predicate, and this is the kind of sentence a repair rewrites without re-reading: the *form* is
identical, only the operand changed.

⚠ **A fixture outside those doors has some of the conditions.** `tests/smoke.py:3003` feeds
`{"marker": {"commit": "c2", "timestamp": "", "before_timestamp": "t0"}}` to
`render_html.assemble_cycles`, under a check named *"no same-commit history → `before_timestamp`
fills the empty stamp"*. It is **not** a door into `reconcile_marker` — §5's first ceiling records
why that fill cannot mint an identity. Named here rather than left implicit, because an enumeration
that misses a member of its own class is the exact defect this section exists to avoid.

**Do not write `before_timestamp`.** Two consumers depend on the record's own seeded value: the
narration window anchor (`render_dashboard.py:1963`) and the archive's **display** fill
(`render_html.py:189` — display, not identity; see §5). R1 gates only the *fill*; the anchor stays
the record's own.
⚠ **Under the identity predicate this constraint is load-bearing, not merely compatible.** The two
operands are *one field of one file at two moments*, which holds **only while nothing rewrites
`before_timestamp` mid-pass**. Anything that moved it would break the change-detector: the predicate
would compare the file's current stamp against a baseline that no longer describes Phase 0, and both
its false arms open at once — a false **refuse** (a fresh stamp differing from a rewritten baseline)
and a false **admit** (a stale stamp equalling it). The constraint is what keeps the tuple
`(before_timestamp, state.timestamp)` a genuine two-sample reading rather than a self-comparison.
This is the exact hazard that made the *rejected* forms unsound from the other direction: freshness
had no writable operand at all, and ownership's operand was rewritten by the remedy itself.

**Untouched contracts.** *"A NON-empty value stands"* (the `if not str(out.get(k) or "").strip()`
guard still precedes both teeth) and *"NEVER raises"* (`_parse_ts` is off this path entirely now;
`str()` never raises; a non-dict marker still degrades to `{}`; the `isinstance(parsed, dict)` gate
at `:2209-2210` still absorbs a non-dict JSON root).

**R1d, applied — and the two places its own first cut could reproduce the defect.**

**One predicate, not two spellings.** The cause is returned by `_stamp_cause`
(`""` admitted · `STAMP_ABSENT` · `STAMP_OWN_BASELINE`), and `_admit_stamp` is its **boolean
projection** — so the comparison that *fills* and the sentence that *explains* a non-fill cannot
drift. A second spelled-out comparison at the message sites is precisely how *"no stamp in
`.consolidation-state.json`"* came to be printed for a file that holds one.

⚠ **An unclassified cause makes the clause `""`, and the arms must then assert LESS.** The first
cut degraded an unclassified cause to the **absence** clause, and a measurement caught it: a
first-run record (no `before_timestamp`) beside a state file holding a stamp has cause `""` — the
stamp is *admitted*, so nothing was refused — and printing "no stamp in the file" about that file
is a **false universal**, the exact class R1d exists to remove. *A fallback clause is still a
claim, and an unclassifiable cause has no honest one to make.* So the clause is conditional at the
panel and on `--diffs` (the line keeps its subject and says nothing false), and `--audit` prints
**no note** rather than an unnameable one.

⚠ **`--diffs` keeps `return 0`; the table's "must not be silent" means the MESSAGE.** Read as
"must exit nonzero" that cell would ask for a contract change this patch does not make: `--diffs`
is a dream-internal capture step whose ladder already skips four other causes at exit 0
(`tests/smoke.py:12684-12690`, itself labeled **GUARD**, asserts `rc == 0 and "skipped" in stderr`),
and its own `try` is documented *"a diff-capture failure must NEVER crash a dream"*. Making one of
five causes nonzero would also re-break the ladder's uniformity that RC-1a's repair established
(`docs/refusal-verdict-parity.spec.md` — which is `e5cce77`-numbered and quotes this line at its
old `:4899`; that quotation is history and is NOT updated, exactly as the v0.1.19 canary is not).
The defect the row **names** is the false clause; the cause is now named, so the loss is not silent.

**Measured** (`/tmp/probe-r1d.py`, Python 3.10.12, positive control refusing the incident pair):
both `--persist` causes exit **5**, the two clauses **differ**, and both still contain `UNSTAMPED`
— the substring the exit-5 pin matches on (`tests/smoke.py:3424-3426`). ⚠ That pin's fixture
(`:3421`) carries **no `before_timestamp`** beside a fresh dir, so it samples the **absent** cause
only; nothing in the suite samples the refusal cause's *message*, which is why the false clause
could sit there without reddening anything — the same inheritance-of-coverage gap §R1d names
above, now measured rather than argued.

### 2.2 R2 — refuse the wrong operand, and refuse the impossible census

**Each guard is placed by what its predicate READS — which is what the first cut got wrong.** It
enumerated `audit_snapshot`'s three CLI-reachable producers and handed both guards to each, concluding
"Guard 2 needs three sites". But that table counts producers of **one** operand, and Guard 2's
predicate names **two**. A guard can only stand where every operand it reads exists:

| `audit_snapshot` producer | reached from | has a before-operand? |
| --- | --- | --- |
| `:2935` (`after = audit_snapshot(project_dir)` in `capture_diffs`) | **`--diffs`**, `:5333` | **yes** — but a §5 ceiling, not a site |
| `:5047` (`audit_snapshot(project_dir)` written to the per-slug temp path) | `--snapshot`, `:5045-5048` | **no** — the arm mints the before-tree and nothing else |
| `:5085` (`audit_diff(before, audit_snapshot(project_dir))`) | `--audit` | **yes** |

**Guard 1's predicate names ONE operand (`project_dir`), so it goes where operands are pooled.** The
pool is `:4924-4933`; `:4934` consumes it (`project_dir = Path(pos[0]) if pos else Path.cwd()`). One
insertion immediately after `:4934` precedes **every** dispatch arm — including
`--justify-demotion`/`--justify-defrag` (`:4935`/`:4944`), which take the same operand — and all three
producers are downstream, so a single site covers every path.

1. **Refuse a store-shaped operand**, in `sync_global.py:5273-5277`'s exact *message shape* —
   `error: PROJECT_DIR <path> <condition> — refusing (<the concrete consequence>)`, stderr,
   `return 2`. The predicate is the tool's **own** ownership guard (`render_dashboard.py:627-630`,
   the comparison at `:630`): read the operand's `.consolidation-state.json`, take the
   script-written `project_path`, and ask whether `resolve_store(<that path>).native_memory_dir` **is**
   this directory. Not a new heuristic, and not "looks like a store" — it fires on ownership, which a
   project directory cannot exhibit. The consequence to name is the one this defect actually has: the
   census reads as all-deleted **and** `:5344` mints a native-plane tree under a phantom slug.

**Guard 2's predicate names TWO operands (`before` non-empty **and** `after` empty), so it can only
live where both exist** — implemented at `--audit` alone:

2. **Refuse the impossible census.** ⚠ **State the matcher: the implemented predicate is
   `before and not audit_snapshot(project_dir)` — the after-SNAPSHOT is EMPTY, not "the three roots
   resolve empty".** The two are not the same claim: `audit_snapshot` (`:2745-2801`) has no early
   `return {}`; it returns `snap`, which is falsy iff **no file from any of the three roots was
   added**. All-three-roots-dead is the *cause*; an empty snapshot is the *effect*, and a **partial**
   resolution — an operand that still resolves one root alive — yields a non-empty snapshot and is
   **not** caught. See §5.
   Note the two operands are **different objects** — the before side is a **file on disk**
   (`:2813-2815`: *"The BEFORE snapshot is UNTRUSTED (a stale/cross-version/hand-edited file on
   disk)"*), the after side is live — so the predicate is perfectly satisfiable, and a genuinely
   all-deleted census with resolving roots still passes. This is the *"a complete guard inverts its
   question"* shape: it fires on the objectively detectable condition rather than on a heuristic about
   the result.
   ⚠ **`--snapshot` is not a site, and no insertion inside it could fire.** That arm supplies no
   before-operand at all, so Guard 2's left conjunct is not false there — it is **undefined**. What
   covers its operand is Guard 1 at the pool, and the pin for that arm says so directly; it is the
   measurement that forced Guard 1 out of the `--audit` arm in the first place.
   ⚠ **`--diffs` is a CEILING rather than a site** — recorded in §5, not silently omitted. Its capture
   is wrapped in a pin-verified contract that a diff failure must **never** crash a dream (`:5332`,
   `except` at `:5348`), so a fatal `return 2` there would contradict the arm's own promise.
   ⚠ **Its SCOPE is "resolves to nothing", not "any wrong operand".** The residual, recorded not
   solved: `resolve_store` derives the store from the **git working-tree root**, not the operand, so a
   store-shaped operand *inside* a repo resolves its memory root to the real store — the predicate
   reads false and this guard does not fire, though the census is still wrong on the other two roots.
   Guard 1 is the one that covers that case.

The two phantom-minting sites are in **different arms** — `:5171` (a **plugin-data** ops dir,
cosmetic) is inside `--audit`; `:5344` (a **native-plane** tree under the phantom slug, the real one)
is inside `--diffs` — and the arms are **mutually exclusive**: `--audit` returns at `:5197` and
`:5198` is where `--diffs` is first tested. Ordering is therefore a claim **per arm**, and never
across them:

| arm | Guard 1 (pool) precedes | Guard 2 (`--audit`) precedes | phantom-minting site behind |
| --- | --- | --- | --- |
| `--snapshot` | `:5047` | **undefined** — no before-operand | none |
| `--audit` | `:5085` | `:5085` | `:5171` — behind **both** guards |
| `--diffs` | `:5333` | not applicable | `:5344` — behind Guard 1 **alone** |

The `--diffs` arm is consequently behind Guard 1 and **only** Guard 1, which is the whole reason Guard
1 had to be the one that moved to the pool rather than the guard that stayed in an arm.

### 2.3 R3 — a disagreement must name both operands

`:3985-3986` reports *"budget.index.after_tokens contradicts the scripted audit (after=…, before=…,
audit delta=…)"* — a cross-check that presumes **which** operand is at fault. In the incident the
record's field was right and the audit was the bogus side (an artifact of C4). Both sides are
script-computed, so a disagreement is a fact about one of two computations: **name both, with their
provenance, and stop ranking them.**

⚠ **Blast radius:** the message is a wrapped literal (`:3985-3986`) and `tests/smoke.py:18824`
selects these warnings by the substring `"contradicts the scripted audit"`. Keep the phrase or update
the selector together — dropping it silently turns that helper into a filter matching nothing, i.e.
a **false green**.

**The claim has FOUR homes, and the plan named one.** Repairing the message alone would have left
three live copies of the same attribution:

| # | Home (`29cdfb33`) | What it says | Disposition |
|---|---|---|---|
| 1 | `memory_status.py:3985-3986` | the message itself | repaired — keeps the selector phrase **and** the parenthetical, appends the provenance clause |
| 2 | `memory_status.py:3932-3938`, the false clause at **`:3936`** | *"a disagreement means the record **contradicts itself**"* — the same one-sided attribution, in the comment | repaired — two-computations framing + a §C4 pointer |
| 3 | `tests/smoke.py:18824` (the `_why30` selector) | the filter | **untouched** — the phrase is kept precisely so this stays a filter that matches something |
| 4 | `docs/record-post-state.spec.md:1172` | quotes the message verbatim, carrying the `1746` instance | **not edited** — a correctly-bound historical record; argued below |

⚠ **Home 2 is the one that would have been missed, and it is the worse of the two.** Home 1 *asserts*
nothing about fault — it prints two numbers and stops. A reader who wants to know **which** number is
wrong reads the comment beside it, and that comment answered confidently and wrongly. **The message
was the evidence; the comment was the verdict** — `a-fault-and-a-verdict-must-not-share-a-message`,
one layer down. Fixing only the message would have left the actual misattribution in place, in the
copy a maintainer is most likely to read.

**Home 4 is deliberately left alone.** `docs/record-post-state.spec.md` is the design-of-record for
the **v0.4.30 arc that authored this check**. It declares its own convention at `:3` (*"Every
`file:line` below is `b63b474`-numbered"*), and `:1172` prescribes the message form that arc's §2.4
specified. That prescription is **true of `b63b474`** and stays true — this arc *extends* the message;
it does not falsify the record of what that arc specified. The house pattern is the one already
applied to C3's D7 correction: **a past artifact states, the new spec carries the correction, the past
artifact is not rewritten.** The repo's own gates agree, and this was verified rather than assumed —
`tests/docs_links.py` binds a curated set of docs to **link resolvability** and (for `LIVE_DOCS`)
**version currency**, and the smoke citation check (`tests/smoke.py:22124-22168`) binds each `docs/*.md`
to its declared revision and validates that its `file:line` citations **resolve**. **Neither reads a
spec's prose for fidelity to a message string**, which is what makes an arc spec a record of its arc
rather than a live claim about today's code.

⚠ **What home 4 costs, stated rather than hidden:** `git grep -n 'contradicts the scripted audit'`
now returns **four** hits — the code, the selector, this spec, and that frozen quotation. A reader who
finds the fourth must not conclude the code is wrong. The alternative (editing a closed arc's
design-of-record so it agrees with a later arc) would destroy the one property that makes these specs
worth having: that they can be read as what was decided **then**.

⚠ **The parenthetical has two test homes, not one.** `tests/smoke.py:18831` (P1) asserts it with `in`,
and `:19189` (P16) asserts `f"(after={_K30}, before=1746, audit delta=-52)" in _seL30n` — which is a
**stderr** capture, the line `render_dashboard.py:1941` prints. So the added clause must not spell any
numeric `after=` pair: P16 also asserts `"after=1746" not in _seL30n`, and a clause that quoted the
seed's number would red it. Measured: a message built from a foreign seed carries no `after=1746`.

**Why row 12 is a PIN — and why it first read GUARD.** The premise is true; the conclusion drawn
from it was not, and the gap between them is the instructive part. The phrase the selector keys on
and the `(after=…, before=…, audit delta=…)` parenthetical **are** byte-identical before and after
this repair. But *"nothing observable flips"* does not follow: the clause that **follows** the
parenthetical is itself an observable, and this repair is what introduces it — so asserting its
presence reddens on `29cdfb33`. The genuinely uncoverable half is narrower, and is **stated rather
than tested**: an assertion that the message *lacks* the old attribution would have no referent,
because the old attribution lived in a surrounding **comment** and was never in the message at all.
⚠ MEASURED 2026-09-21 on the matched pair — one harness (`sha256 3523694d…`), pre-fix scripts taken
from `29cdfb33`, one process per tree: the check is **PRE ✗ / POST ✓**. §3's own rule ("a PIN fails
on the pre-fix tree; a GUARD cannot") therefore makes the row a PIN, and the check's *label* — never
its assertion — is what changed. The check was doing the right thing while its label claimed it
could not flip; a later edit re-wrapping this literal still drops the clause, and now reddens.

### 2.4 R4 — a fault and a verdict must not share a message

⚠ **The plan's repro is REFUTED by measurement, and the reachable arm is worse than the recorded one.**
The plan said *"given a project dir it exits 1 with 'no dreams to render…'"*. Six arms driven
in-process against an enrolled fixture store (`_Env73`'s construction — HOME redirected, project
enrolled, store at the slug path, because the identity resolver consults the registry and without the
enrollment every arm refuses for an unrelated cause):

| arm | operand | rc | stderr |
| --- | --- | --- | --- |
| A | `--store <REAL STORE>` | 0 | — (renders; 216239 B) |
| B | `--store <PROJECT DIR>` | 1 | `… belongs to no registered project — pass --project <its dir>` |
| C | `--project <PROJECT DIR>`, log absent | 1 | **the conflated sentence** |
| D | **no operand at all**, cwd = the project | 1 | **byte-identical to C** |
| E | no operand at all, cwd = the repo | 1 | the same sentence |
| F | `--store <empty dir>` | 1 | the v0.4.36 identity resolver refuses it a screen up |

Arm B **never reaches `:788`**: `store_context.py`'s identity resolver refuses a store-shaped operand
at `render_html.py:604` and names the operand while doing it. So the plan's own repro tests the
**argument parser**, not the message — the ⚠ the plan itself warns about two paragraphs later, turned
on the plan.

**The reachable defect is the no-operand arm.** With `store is None`, `read_history(None)` returns
`[]` at its **first line** — no path located, no file opened — yet the sentence asserted *"an empty
.consolidation-log"*. C and D are genuinely different conditions (one names a subject whose log is
absent; the other never named a subject at all) and produced the **same bytes**, so the sentence could
not be true of both. Its printed remedy ("run a dream first") is likewise the wrong repair for an
invocation that never named anything to dream about.

⚠ **The plan's second arm is UNREACHABLE, so it is absent rather than written.** *"no cycle found in
the log"* cannot occur: `assemble_cycles` keeps **every** dict row, so `cycles` is empty **iff** no
cycle-bearing row exists — which is arm C's condition, not a distinct one. There is no "rows read but
none assembled" state to give a message to.

**Repair.** The module already owns this doctrine: `_ARM_NO_PROJECT`/`_ARM_CLAIMED`/`_ARM_REGISTRY`/
`_ARM_MISMATCH`/`_ARM_NO_PATH` (`:394-403`) and `_REMEDY_ENT`/`_PROJECT`/`_PATH`/`_ENV` (`:404-406`)
exist so that *"a pin can assert WHICH arm fired without matching prose"*, in the convention
`<operand> <ANCHOR> — <REMEDY>`. The one arm that missed it now has it: `_ARM_NO_CYCLES` (*"has no
cycle record at"*) with `_REMEDY_DREAM`, and `_ARM_NO_STORE` (*"names no store to read"*) with
`_REMEDY_STORE`. `_log_paths_for(store)` renders the paths actually consulted — the
`retention.cycle_log_read_paths` **ladder** (`[native, slot, pid]`, last wins), not one hardcoded
path — falling back to `[store / ".consolidation-log.jsonl"]` if `retention` cannot be imported.
The `project_path` ownership check (`render_html.py:604`, `render_dashboard.py:621` — a
*store-belongs-to-project* test, unrelated to §2.1's marker predicate) is why `--store` is **not**
silently defaulted: it admits a `project_path` only when it verifies, so a guessed default would be a
new way to render the wrong store.

⚠ **The fault arm names its own negative**, because the sentence it replaces asserted exactly that:
*"so no cycle log was located and none was read (this is NOT a report that the log is empty)"*.

**Pin shape — the RC-1d precedent (`tests/smoke.py:12309-12349`).** Assert the two arms produce
**DIFFERENT** messages, *"which is exactly what a two-cause sentence cannot do"*, with the pre-fix
measurement stated inline. Post-fix attribute names are read through `getattr` with a sentinel: a bare
read would raise `AttributeError` and **ERROR** the suite instead of reddening one check — the same
defense RC-1d uses for `_WRITE_ACTIONS_MARKER`. ⚠ The fixture precondition is a **conjunct of the
check**, never an `assert` upstream of it: an `AssertionError` aborts the suite, and the D6 pin counts
only what reaches it — a changed fixture would take out every check below instead of reddening one.

**Measured verdict:** the two arms differ; each anchor present in its own arm; **neither** arm still
contains `empty .consolidation-log`; both controls rc=0 with a 216239 B render.

### 2.5 R5 — name the rung, not the ladder, and give the token ONE home

**The finding.** `prune_pressure` (`:807-816`) returned `"index-over-budget"` when
`ctx["index_lb"][2] > INDEX_TOKEN_BUDGET` — the condition measured at its one call site, `:829` —
i.e. the **1500 target rung**, while `INDEX_CEILING_TOKENS` (3840) is the *second, harder* rung,
surfaced separately as `remediation.over_ceiling`. So one live record can carry this `prune_reason`
beside `over_ceiling: false`, and "budget" is the one word the ladder reserves for the **whole
two-rung ladder**. (Measured cost: a mis-read made live during triage.) The token becomes
**`index-over-target`**.

**And the repair is not a rename alone — the token had TWO homes in one module.** It is PRODUCED at
`:813` and COMPARED at `:4623` (`print_report`'s suppression predicate, which decides whether to print
the redundant prune-pressure line). As twin bare literals that is a coupling that can only drift in
**silence**: a rename on one side leaves the suppression matching nothing, the redundant line quietly
reappears, and no check can see it. It is now **named** — `PRUNE_REASON_INDEX_OVER_TARGET` — and both
sites read the name. `render_dashboard.py:38` already states this module's own rule (*"reuse the
canonical tier bands (derive, don't duplicate)"*); this token was simply never held to it.

⚠ **Why the naming is part of the repair rather than scope creep.** The plan's row 8 was *"the
record's `prune_reason` token is drawn from the declared set"* — but §C5 records that **no declared
set exists**, which is what made that check vacuous. Naming the constant is what gives it a referent.

**Blast radius, re-measured with `git grep -- ':/'`** (⚠ a bare `git grep` is CWD-scoped, and exactly
that silent zero understated this token once). Live code: **three** sites, all `memory_status.py` —
the producer, the comment above the comparison, and the comparison itself. Tests: **two checks**
(`tests/smoke.py:235`/`:238`, in the `29cdfb33` numbering), now pinned to the new literal.
**Frozen, and verified untouched: two** — `CHANGELOG.md:6058` (history) and
`plugins/dream-beta-tester/fixtures/canary-v0.1.19/memory_status.py:270/1033/1035` (byte-faithful to
the v0.1.19 tag, SHA256SUMS-manifested; **checked** with `sha256sum -c` after the repair, not
assumed). **No prose site exists** — no doc, no `SKILL.md`, no `harness-map.md` entry quotes the
token; `harness-map.md:266` names the *function*, not its vocabulary. `render_dashboard.py:810`
prints the value *from the record* and carries no literal.

**Behavior-neutral, and the obvious counterexample is the one that fails — measured.** A record
persisted *before* the rename still carries the old token, so the natural worry is that it stops
matching the suppression and the redundant line prints again. It does not: the only *comparison* is
`print_report`'s, whose left side is `rg = _provisional_rigor(ctx)` (`memory_status.py:4733`) —
**this run's** ctx, never a stored record. ⚠ **Watch the two `rg`s**: same name, two modules, one
live (`memory_status.py`, compared) and one stored (`render_dashboard.py`, only displayed). The
rename's reachable effect is confined to records written *from here on*, where the producer writes
the new token.

⚠ **The test literals stay LITERAL.** Pinning the spelling *through* the constant would make the check
unable to redden on a rename — the one thing it pins — so `:235`/`:238` assert the string, and the
binding is checked separately (row 17).

### 2.6 R6 — correct the false description

Correct **only** `_ui.py:165-166`'s second clause (the named consumer), leaving the first (the
contract's emoji ban) alone. The code is already honest here and only the prose over-states, so the
repair is to a **false description**, not a code-to-promise inversion — and re-deriving a rule the
comment is not making would be its own defect.

**Both halves measured before editing, because the two clauses have different scopes.** The first is
**true**: the emoji ban is a **SKILL-level narration contract** (`SKILL.md` — *"Emojis exist ONLY on
the two bookends"*, with the phase beats, the SURFACING line and the DEBRIEF lead line each spelled
no-emoji) and the code enforces nothing there — so it stays. The second is **false**, and this census
is small enough to state exactly: `BEAT_EMOJI_RE` has **one** call site in the repo —
`render_dashboard.py:1239`, the **advisory** beat-index flag, which changes no verdict and no exit
code — beside its own definition at `_ui.py:167` and a frozen quotation in
`docs/defrag-flow-and-emoji-index.spec.md:25`. `arc_completeness` (`memory_status.py:4065-4092` in the
`29cdfb33` numbering) **never references it**: its rule is sleep/wake presence, the beats **count**,
and each entry being a non-empty string.

⚠ That last point is why the false clause is worth correcting rather than tolerating: it invites a
later editor to make it *true* by wiring the glyph range into `arc_completeness` — which **is** the
exit-4 persist gate, so a glyph rule there would fail an arc over its typography. The corrected
comment says so, and cites the narration contract without a line number (a `SKILL.md:NNN` deictic
would go stale the next time that file moves). ⚠ Confirmed safe to edit: no check reads `_ui.py`'s
source text — the drift pin at `tests/smoke.py:1767` compares **output**, not source bytes.

## §3 Verification — the pin list

Every pin must **fail on pre-fix code**; a check that cannot flip is a **regression guard**, labeled
and kept out of the pin count. **One process per tree** (`sys.modules` caches the first import).
⚠ **Two pre-fix trees were used, and they are not interchangeable — the method is named with each
result.** The predicate table below was measured on a **`git archive 29cdfb33`** tree. The
**check-level pair in §3.1** was measured the other way: a copy of the working tree with `scripts/`
reverted **per path** to `29cdfb33`, which leaves the harness at its final revision. A `git archive`
tree cannot do that — it would restore the *pre-fix* `tests/smoke.py` too, and the arc's own checks
do not exist there, so they could not be observed flipping at all.

⚠ **A RED in the measurement tree is a hypothesis about the tree before it is a fact about the code.**
Three environmental differences, all measured — and the first **cost this arc a false claim**, so it
is stated with its evidence rather than as a reassurance. (a) The tree is `.git`-less, and that is
**not free**: the citation family (`v0.4.37 pin 7a`, `7b`, and `pin 8`) resolves every citing doc's
declared revision against **the clone's own history**, so on an archive tree all three red — by
design, and their text says so: *"A FAULT, and NOT a verdict — this tree cannot be asked for its own
history (no readable `.git`)"*, remedy *"a FULL clone — `fetch-depth: 0` … never a doc edit"*. An
earlier revision of this paragraph asserted *"no check in that census needs the real repository"*, on
the strength of the two cwd-scoped `git log` calls (`:5407-5408`, `ms._run(["git","log"], Path("."))`)
being stubbed and every other `.git` belonging to a fixture the suite `git init`s itself. That is a
complete census of `smoke.py`'s git **calls** — and the citation family does not *call* git scoped to
the cwd, it asks the repository to answer for a revision, which is a different question with a
different answer. **The three reds are therefore a constant on BOTH arms** and carry no arc signal;
they are named here so the next reader subtracts three rather than re-deriving them. (b) The suite
carries **CPU-clock linearity guards**: two runs must never overlap, because contention can
manufacture a false RED but never a false GREEN. The error direction is one-way, which is exactly why
the process table is checked *before* a run rather than after. (c) The harness must be the **same
bytes** on both arms, so a difference is the mutation and not the instrument; the pair below states
its harness hash for that reason.

⚠ **And a pin's fixture must carry the inputs the predicate reads.** Under the identity predicate the
input that matters is **`before_timestamp`**, so the degradation runs the opposite way from the
rejected forms and is easy to miss: admission has **two** routes and only one is vacuous. A
baseline that is an **absent key** or `""` is the vacuous route (`not prev`). A baseline that is a
placeholder like `"t0"` (`smoke.py:3003`'s idiom) or junk is **a non-empty string that cannot equal
the file's stamp**, so it is admitted by the comparison route (`stamp != prev`). Either way a
refusal pin has nothing to refuse. **Pin 1's fixture must therefore set `before_timestamp` to the
exact string the state file holds** — one value written to two places, not two similarly-shaped
values. ⚠ The `commit` no longer participates at all, which is why P15's non-SHA `"v0430pin"` is now
irrelevant to this axis rather than a trap on it.

| # | claim | kind | fails pre-fix because |
| --- | --- | --- | --- |
| 1 | a stamp **equal to** `before_timestamp` fills **nothing into `timestamp`** — the file has not moved since Phase 0. ⚠ The `commit` is a **separate per-key fill** and is not gated here (row 11); only `timestamp` reads the stamp | **PIN** | pre-fix fills the previous cycle's time |
| 2 | a non-matching baseline still **fills**, by *both* routes: no baseline (absent, `""`) and a differing one (the SKILL placeholder, junk, future skew) | GUARD | green both trees; guards the **admit** side R1a must not close |
| 3 | a stamp **differing** from `before_timestamp` still fills — a genuine mid-cycle advance is admitted | GUARD | green both trees; **this is the row that pins the ownership refutation** (ownership would be RED here) |
| 4 | an int `state.timestamp` is stored as a **string** (R1b) | **PIN** | pre-fix stores the raw JSON int |
| 5 | the **seed** coerces a non-`str` `last_ts` (R1c) — the VALUE survives; it is **not** blanked | **PIN** | pre-fix `before_timestamp == 20260921` (raw int) → post-fix `== "20260921"`. ⚠ A pin asserting only *"it is a `str`"* is satisfied by `""` — i.e. by the defect |
| 6 | `--audit <snapshot.json> <store>` refuses, and mints nothing | **PIN** | pre-fix: rc=0, an all-deleted census, `:5344` mkdir |
| 7 | R4's two arms are distinguishable by message | **PIN** | pre-fix: one message, one exit |
| 8 | `prune_reason` carries `index-over-target` | **PIN** | pre-fix emits the old literal |
| 9 | a healthy cycle whose file carries the *previous* cycle's stamp still fills as today | GUARD | green both trees — guards over-refusal |
| 10 | a record with no `before_timestamp` still fills (`:3346`, `:3349`, P15) | GUARD | green both trees |
| 11 | a half-stamp source (`commit`, no timestamp) still fills the **commit** | GUARD | green both trees; guards against gating the pair on one predicate |
| 12 | the R3 message names both operands | **PIN** | pre-fix the added clause is absent, so the check reddens on `29cdfb33` — ⚠ this row read **GUARD** until the matched-pair run put it among the reds (see §2.3) |
| 13 | `reconcile_marker` still never raises on junk / non-dict / missing file | GUARD | already covered at `tests/smoke.py:3340-3353` |
| 14 | the **`--snapshot`** producer refuses the same store operand — the arm Guard 2 **cannot** reach | **PIN** | pre-fix: rc=0, a `{}` written to a phantom slug's temp path *and printed* |
| 15 | an operand resolving to **nothing** at all, against a non-empty `--before`, refuses as an **instrument fault** (Guard 2) | **PIN** | pre-fix: rc=0, every `--before` file reading DELETED |
| 16 | the same `--audit` against the **real project directory** is **NOT** refused (the control) | GUARD | green both trees; without it rows 14–15 are satisfied by a guard that refuses everything |
| 17 | the over-target token has **one home**: the producer and `print_report`'s suppression predicate read ONE name, not two literals | **PIN (structural)** | the binding is **absent** on `29cdfb33`, so the sentinel cannot match — ⚠ **not** evidence of the drift it guards (see below) |

⚠ **Two repairs carry no row, by construction.** R6 and R1e are **comment-only** corrections: their
observable is prose, and a text check whose haystack is prose about its own subject is not a pin (§C6)
— it can only ever assert that a string is present, never that the sentence is *true*. They therefore
ship **unpinned deliberately**, and are recorded here so the absence reads as a decision rather than
an omission.

**Ten PINs, seven GUARDs** (17 rows). ⚠ The count is stated because it is easy to get wrong by
reading: row 11 is a guard that *looks* like a pin, rows 3 and 9 are two distinct fixtures with
one verdict, row 12 is a pin that was *labeled* a guard until the matched-pair run measured it, and
row 17 is a pin that *behaves* like a guard. ⚠ **Every kind beside a row is a measurement, not a
reading** — this table's own count moved by one when the pair ran, which is the whole reason the
harness labels are checked against a pre-fix tree rather than against intent. ⚠ **Row 17's kind, stated plainly:** it
**does** flip on `29cdfb33` — because the binding does not exist there — so the rule at the top of
this section makes it a PIN, not a guard. But its flip is **structural**: it reddens on the absence of
a name, never on the drift it guards, and pre-fix code could not have expressed that drift (both
homes held the same literal, so there was nothing to disagree). Rows 7 and 8 — R4's two-arm split and
R5's renamed token — carry this arc's actual pre-fix evidence for those repairs. It is listed as a PIN with the caveat attached rather than miscounted as a
guard, because "a check that *cannot* flip" is the guard test and this one can. ⚠ Rows 14–15 were added when R2 was restructured — the first cut assigned Guard 2 to all
three `audit_snapshot` producers, which would have made rows 14 and 15 the same row and left the
`--snapshot` arm covered by nothing (# §2.2). Row 16 is not decoration: it is the **control** that
makes rows 14–15 evidence rather than a tautology, since a guard that refused every operand would
satisfy both.

⚠ **Measured evidence, with its triple named.** A 14-fixture table run at the predicate level —
`_valid_sha` **imported from the real module**, the pre-fix loop transcribed from `:2213-2220`, the
post-fix loop from the R1a block above — gives **2 flips and 12 guards**:

| fixture | pre-fix | post-fix | flips? |
| --- | --- | --- | --- |
| **F1 the incident** (`before_timestamp` = the file's own stamp) | fills the stale `2026-09-15T14:16:11.649Z` | **fills nothing into `timestamp`** (the `commit` is already seeded — the incident's shape) | ✅ **the pin** |
| **F9 a JSON-int stamp** (R1b) | stores the int `20260921` | stores `'20260921'` | ✅ **the pin** |
| F2–F6 (absent / `""` / placeholder / junk / future skew) | fills | fills | no |
| F7 mid-cycle advance · F8 healthy re-stamp | fills | fills | no |
| F11 invalid commit + fresh ts · F12 `H0[:7]` · F13 `H0.upper()` | fills | fills | no |
| F10 half-stamp source (fills the commit only) · F14 empty state | — | — | no |

⚠ **The triple, so the count is not carried:** the restored code is *my transcription* of the pre-fix
loop, not the function — this measures the **predicate**, and it says nothing about whether the loop
*reaches* it in the real call path. That is why pin 1 is not satisfied by F1: it must be driven
through `reconcile_marker` **in the mutation tree**, where the fixture also has to route past the
outer guard at `:2214`. The 12 guards are the useful half of this table — they are the shapes the
repair must **not** start refusing.
⚠ F12/F13 are pre-fix-invisible here *by construction*, and their real consequence is a §5 ceiling
rather than a repair — measured, because the old text asserted a bound without one.

### §3.1 The matched pair — the check-level ratchet (MEASURED 2026-09-21)

The table above measures R1's **predicate**. This is the second instrument — the whole suite against
two code trees carrying **one harness** — and it is what establishes each check's **kind**. It is
also what corrected rows 11 and 12.

- **The triple, named.** Harness: `tests/smoke.py` `sha256 3523694d4357b30b85a8ad5e3f48bd66269f67b5384eb03fe0974104962e3b10` (LITERAL —
  `sha256sum <file>`),
  **byte-identical on both arms** (verified, and stated because otherwise a difference could be the
  instrument). Pre-fix scripts: `29cdfb33`, restored **per path** over the four files the arc touched
  (`_ui.py`, `memory_status.py`, `render_dashboard.py`, `render_html.py`) — measured: **no script file
  was added or removed**, so the revert is complete rather than partial. Everything else — `docs/`,
  `plugin.json`, `CHANGELOG.md`, the harness — is the **final** tree on **both** sides, so the arms
  differ only by the arc's own script diff. Neither carries a `.git`, and the build excludes `__pycache__` so each arm compiles its own
  sources from scratch. ⚠ **A reader checking this with `diff -rq` must run it BEFORE the runs, or
  exclude caches** — the runs write per-arm `.pyc` files (34 on the 2026-09-21 rebuild) whose headers
  embed each arm's own path, so the post-run delta is the four sources *plus* those caches. The
  caches are derived from the sources — Python validates a `.pyc` against its own source, so using one
  is equivalent to compiling that source fresh — and cannot move a verdict.
- **The pair was run TWICE, and the second run is the one recorded above.** The first run's triple
  went stale the moment this arc's own label corrections edited `tests/smoke.py` — and a mutation count
  belongs to the triple, never carried across an edit to any of its legs. That run used harness
  `0352aeab860120d4517baceecb60bd6f6c523743c74fdf5827db2d596b2f0dce` and a *different* copy of this spec;
  the second rebuilt both arms from the shipped tree and used the bytes named above. **Both runs gave
  `2188 passed, 15 failed` / `2200 passed, 3 failed`.** ⚠ That agreement is a *measurement of the label
  edits*, not a reassurance about them: a label is a string passed to `check`, so moving `(GUARD` →
  `(PIN` on two rows cannot move a flip. It is stated because this is the pair that *found* that
  distinction, so its own evidence was re-taken rather than argued from an invariance premise —
  which is the same shape as the false reassurance (a) below, one layer up.
- **One process per tree**, the two runs **sequential** (the linearity guards), process table read
  before the launch.

| arm | result | reds |
| --- | --- | --- |
| PRE (`29cdfb33` scripts) | `2188 passed, 15 failed` · rc=1 | citation constant ×3 **+ 12 discriminating** |
| POST (final) | `2200 passed, 3 failed` · rc=1 | citation constant ×3 |

The **12 discriminating** reds are the two pre-existing `prune_pressure` checks whose expected token
R5 renamed (`tests/smoke.py:235` — in the check *name* **and** its expected tuple — and `:238`),
**plus all ten** `v0.4.41` PINs. The three citation reds appear on **both** arms and are subtracted
as an instrument constant (§3 preamble, (a)) — never counted as signal.

⇒ **Kind census at the check level: 10 PINs, 1 GUARD** among the eleven `v0.4.41` checks, the guard
being R2's control, measured green on both arms. Of the ten PINs, **eight were already labeled PIN**
and correct; **two were labeled GUARD and flipped anyway** — R1's admit table and R3. Both labels were
false in the **same** direction, and in both the **assertion was already right**, so the label was the
half corrected. ⚠ That direction is the point: a guard-label on a check that flips is the *safe*
error (it under-claims), but it is still a label that is not its predicate, and this table's own
count moved by one when the pair ran.

⚠ Row 3 is the one that keeps this table honest in *both* directions: it is
green on `29cdfb33`, so it does **not** pin the incident — it pins the **refutation**, asserting that a
genuine mid-cycle advance is admitted. Under the rejected ownership predicate that row would be RED,
which is exactly what refuted ownership; keeping it green is the standing evidence that the surviving
predicate does not re-acquire the wedge. ⚠ Row 11 is the second: also green on `29cdfb33` (the per-key
loop already fills the commit), it guards against *implementing* R1a by gating the pair on one
predicate, which costs `--audit` its commit coordinate. ⚠ **R3 (row 12) was the third, and this paragraph contradicted its own table until a
re-grep caught it after the second run.** It read that R3 *ships unpinned in effect*, its check
*green on both trees* — the opposite of the census six lines above, which already counts it among
the two labels that were false. The pair measures it **PRE ✗ / POST ✓** (§2.4). ⚠ The sentence is
*replaced rather than deleted* because it is this arc's own defect one layer up — a claim about a
check, left standing after the check's label was corrected, inside the document that records the
correction — and because deleting it outright would also delete the one true thing it gestured at:
the selector phrase `:18824` keys on and the `(after=…, before=…)` parenthetical **are**
byte-identical across the repair, so the flip is carried *entirely* by the clause this repair
**adds**, and a later edit that drops that clause still reddens. The coverage the stale sentence
said was missing does exist.

**Regression guards to keep green for R1:** `:3404` (the auto-mirror still reconciles an empty stamp
— note the `check` is at `:3408`; `:3403` is the state-file write above it), `:3412-3418` (the
idempotent duplicate re-render — the closest existing analogue to the incident), `:3419-3426` (no
state file → exit 5), the four at `:3346-3353`, and **P15 `:19147-19167`** — which reaches the fill
end-to-end through `_persist` and survives only because the record it re-reads carries **no
`before_timestamp` key at all**, landing it on the vacuous arm. ⚠ Two lines, two jobs: `:19153`
*enters* the fill (it blanks the timestamp); `:18946` supplies the *absence* (the seed never writes
`before_timestamp`, and no pass does — §2.1). ⚠ Named precisely, because the *reason* changed with
the predicate: P15's `"v0430pin"` commit is no longer what saves it — the predicate never reads the
commit.

## §4 Ship shape

One PR, one patch release. The four validators run in order, then the release harness's two phases
with a human merge between them. `plugin.json` is hand-bumped on the feature branch; `--stage`
**verifies, never authors**.

`docs_links.py` reads currency statements from `LIVE_DOCS` — an explicit curated list, never a glob,
with the criterion stated in its own source: *"Add a doc here only if its version statement goes
stale the moment a release lands."* ⚠ It is **not** a specs-exclusion list: it holds
`docs/1.0-preflight.spec.md`, a live checklist rather than a record of what became true. This spec is
the other kind — its "Target release: v0.4.41" is **provenance**, true forever — so it must **not**
be added. (Measured: the gate is green with this file present, and `live-doc statements` reads 6
either way.)

⚠ **This file is not in `DOCS` either**, so its own outbound markdown links are not walked. That is
the norm for specs — **5 of the 82** in `docs/` are listed (`tests/docs_links.py:114` states both
numbers in its own comment), each for a reader-facing reason the list records — and not an error.
Recorded rather than assumed, so the next editor does not read *"the docs gate is green"* as covering
this file. ⚠ An earlier cut said *"3 of the 56"* — a numerator omitting two of the five listed
entries, over a denominator that counts a different population entirely: **56 is the
`*.spec.md` count measured *on disk***, i.e. the census silently included **this very file**, the
artifact making the claim, in the figure used to argue about it. **A count whose census named a
different population than its claim** — and one whose population contained the claimant. (Measured:
`git ls-files docs | grep -c '\.md$'` → **82** tracked; `rglob('*.md')` → **83** on disk, the extra
being this untracked spec. That 1-file delta is the whole of the discrepancy, and it is why the
operand has to be named: *tracked* and *on disk* are two different populations.)

## §5 Known ceilings (documented, not solved)

- **A baseline that cannot match fills unconditionally — admission has a fail-open side, by design.**
  The predicate admits on **two** routes and only one is vacuous: **no baseline** (`not prev` —
  absent, `""`, whitespace; the genuine first run, where filling is correct) and **a baseline that
  differs** (the SKILL's `"<prev marker ISO>"` at `SKILL.md:1660`, junk, or a future-skewed value —
  all non-empty strings that cannot equal the file's stamp). The predicate **can** tell those apart
  (`bool(prev)`); what it must not do is *refuse* the second, and the reason is the remedy rather
  than the grammar: `before_timestamp` is a record field the tool never rewrites (§2.1), so a refusal
  keyed on it could never be cleared — the permanent wedge that killed *freshness* on its axis (c).
  Parsing would not help: a parse is exactly what R1a dropped, and R1c narrows only the *type* (a
  non-`str` `last_ts` is **coerced**, never blanked — see §2.1's R1c), not the grammar. ⚠ Stated as
  *"the predicate cannot distinguish them"* this ceiling would be false, and implementing it that way
  reintroduces the parser — including its non-`str` crash (R1c). **Bounded — but on the right
  reason**: both routes fill exactly as `29cdfb33` does, so no coordinate is *lost* — on the vacuous
  route none was established, and on the differing route the pair taken is at least **whole**, written
  together by `stamp_project_marker` rather than assembled from two epochs.
  ⚠ **Self-consistency is not ownership**, and the first cut's bound claimed the pair was *"the file's
  own"* — which is false. An **interleaved** stamp by a second pass in the same cycle is admitted
  identically by this predicate *and* by *freshness* (**measured**: both return True, so this is an
  axis on which the two designs do **not** differ). `_already_logged` (`render_dashboard.py:1520-1540`)
  compares the exact `(commit, timestamp)` pair across all three rungs and returns `"duplicate"`
  **before** appending (`:1578`), so the second pass can be suppressed ⇒ **exit 0, no line** — the
  incident's *observable*, reached with no stale stamp at all. R1a neither causes nor widens this (the
  ungated fill takes the same pair), and the trigger is narrow — a second pass stamping the file
  between this pass's Phase 0 and its persist — but an honest bound names ownership, not coherence.
  ⚠ **Note the register.** This ceiling is a **negative** claim: nothing in the code, the pins, or the
  suite can falsify it, which makes §5 the least-audited surface in the artifact. Two consecutive
  review rounds have now returned *"§5's bound is wrong, the design is not"*. Budget review for it.
  ⚠ Note what this ceiling **replaces**: the first cut's version was about the record's *commit* being
  short or non-hex. That case is no longer a ceiling at all — the predicate never reads the commit, so
  `H0[:7]` and `H0.upper()` are now simply irrelevant rather than refused.
- **The `commit` fill copies the state file's commit *verbatim*, so a short or uppercase commit
  cannot match a full-hex neighbour.** Measured (F12/F13): `_valid_sha` **admits** 7–40 hex and any
  case (`H0[:7]`, `H0.upper()` → both `True`), so the tooth passes them and `out[k] = str(state[k])`
  writes them as-is — the state file's *spelling* becomes the record's coordinate. Then
  `_same_dream` (`render_html.py:157-173`) opens with `ca != cb`, a raw byte comparison, so
  `"29cdfb3"` and `"29cdfb336d1894…"` name one commit and compare **unequal** → `False` → the pair is
  read as two dreams and the archive **double-embeds**. That is the same key defect as the hazard the
  `v0.4.1-fix (C1/C2)` note records at `:198-199` — ⚠ and note *where* it lives: it is
  `assemble_cycles`'s comment, **not** `_fill_timestamp`'s docstring, which is where a reader
  checking this citation will look first: *"a fill-then-dedup cascade could make a filled legacy row
  marker-identical to its neighbor and collapse two dreams"* — one identifier with more than one
  spelling, on a byte-equality key — running in the opposite direction.
  **Reachable only when the record's commit is empty** (else `:2214`'s guard skips the fill): a
  hand-authored record, or a no-git/unborn seed. The dream path fills `ctx["head"]` from `rev-parse`,
  so it is unaffected. **Pre-existing and unchanged by R1** — recorded so it is not re-derived as a
  bug of this repair, and because the first cut of this section stated the bound ("such a record has
  no commit coordinate to lose") without the measurement that shows what it *does* cost.
- **`_parse_ts`'s grammar is a property of the interpreter.** `fromisoformat` (`:945`; the version
  split it depends on is documented at `:926-927`, *"3.8–3.10 … 3.11 relaxed it"*) accepts 3-or-6
  fractional digits on 3.8–3.10 and any count on 3.11+, so `"…11.64912Z"` parses on 3.11+ and not on
  3.8–3.10. Measured on **3.10.12**: `"…11.64912Z"`, `"20260921"`, `"20260101T1200"` and
  `"2026-W38-1"` all → `None`. **Both arms measured now, at a consumer rather than the primitive** —
  `_stale_since([f], "20260921")` against a fact dated 2026-01-01: `[]` on **3.8.20**/**3.10.12**, the
  stem on **3.11.15**/**3.13.15** (the documented relaxation, confirmed). ⚠ **`_stale_since` is a
  SECOND site** of this dependence, not a consumer of `_parse_ts` — it calls `fromisoformat` itself
  (`:3441`), behind its own `isinstance` gate, so R1a removes the grammar from neither.
  ⚠ **R1c widens its reach**: a JSON *number* `timestamp` died at that gate on **every** interpreter
  (`[]`, invariant — all four measured); `str()` turns it into `"20260921"`, which is `[]` on ≤3.10
  and a **live cutoff** on 3.11+ — version-invariant input made version-divergent. Unrepaired by
  choice: the input is nonconforming state, and the promise (*"empty … if the timestamp can't be
  parsed"*) holds per-interpreter.
  ⚠ **And `_parse_ts` raises on a non-`str`** — `_parse_ts(20260921)` and `_parse_ts(['x'])` both
  `AttributeError` at `:943`, outside the `try` — so it is *not* the crash-safe classifier its
  sibling `_valid_sha` is documented to be. Recorded here because §2.1's R1c declines to reuse it
  for that reason, and a later reader who "restores symmetry" would reintroduce the crash. Reachability is low (`_utc_iso_now` emits
  exactly 3 digits, `:2120-2122`), and R1a **removes `_parse_ts` from the admission path**, so this
  cannot move a persist verdict. It can still move a *test* verdict — which is why §3 names the
  interpreter a pin is measured on.
- **`render_html._fill_timestamp` fills an empty stamp from `before_timestamp` — deliberately, and it
  cannot mint an identity.** Read alone (`:176-192`), it looks like R1's door left open: the same
  shape, the same ungated fill. It is not, and the reason is **position, not predicate** —
  `assemble_cycles` (`:195-231`) makes the append/replace decision and keys `by_commit` on **raw**
  markers, and only then fills. The `v0.4.1-fix (C1/C2)` note states the hazard that order closes:
  *"a fill-then-dedup cascade could make a filled legacy row marker-identical to its neighbor and
  collapse two dreams."* `_fill_timestamp` returns a copy, so the embedded series never mutates caller
  dicts. The chimera it can mint is **display-only**; every identity decision is upstream.
  (`_same_dream`'s commit-match-with-either-empty-ts rule is the same deliberate tolerance, and the
  same note names this incident's shape at `:199-201` — again in `assemble_cycles`, not in
  `_same_dream`: *"the stale unstamped `--cycle` file vs the repaired log line must never
  double-embed"*.) **Do not gate this site** — no input could make the gate matter, so its pin could
  never flip.
- **The split-brain heal (`render_dashboard.py:2060-2069`) reconciles a second time — and cannot
  disagree.** It reads the same `(marker, store_dir)` against the same state file, and `_heal` is
  reachable only after `_persist` already admitted a stamp. Measured both trees: the log line and the
  cycle file carry the same stamp in every fixture above. **Closed, not carried.**
- **The Phase-4 surfacing line's identity is invisible to the gate.** `arc_completeness` is exactly
  `have_sleep and have_wake and n == 6 and not bad` — no index, prefix, or emoji test. Any six
  non-empty strings pass, and moving the surfacing line to `beats[0]` changes no verdict in the repo,
  though `dream_procedure.py:341` states it is the last entry. Making it checkable needs a structural
  slot (a schema change ⇒ a minor bump), which "one patch release" excludes.
- **The state-file filename is declared four times** — *in live code*; the census is **six on disk**,
  the other two being the vendored `canary-v0.1.19` copies, excluded by the same frozen-artifact rule
  that keeps `CHANGELOG.md` out of R5's token sweep. Named because an unstated population is what makes
  a count unauditable (`memory_status.py:687` `STATE_FILE`,
  `control_plane.py:165` `MARKER_FILE`, `extract_signals.py:60` `STATE_FILE`, and
  `plugins/dream-beta-tester/scripts/snapshot.py:76` `MARKER_FILE: str = "…"`) and bypassed by raw
  literals at `render_dashboard.py:1597`, `session_beacon.py:111/175/299`,
  `sync_global.py:1712/1779/4704`, `preflight.py:536`. A rename would not reach them. ⚠ The fourth was
  missed by the obvious matcher (`STATE_FILE\s*=|MARKER_FILE\s*=`) because of its `: str` annotation.
- **`reconcile_marker`'s `store_dir` operand is carried, not derived.** Four call sites, **two** kinds
  of value — `ctx["auto_mem"]` (`memory_status.py:5104`, `:5328`) and the `--persist` dir
  (`render_dashboard.py:1566`, `:2064-2065`). Only the first kind is guaranteed inside the native
  store. ⚠ **R1 does not widen this, but it does *depend* on it** — §2.1's precondition. On the
  `--persist` path the operand is the argument, not a resolution, so the change-detector's two
  operands are one file only while the caller passes the store the seed read. Both divergent
  outcomes are safe (equal stamps across two stores coincide only within one millisecond, and that
  refusal is correct), so this is recorded as a precondition rather than repaired here.
- **`--help` is rejected on the four lax scripts** — deliberate and pinned (`tests/smoke.py:18357-18369`,
  pin 37, whose loop tuple has four names and whose comment says *"the four"* twice); rejecting
  loudly is the safe direction after the v0.4.29 defect where `-h` ran a full extraction. ⚠ Five
  scripts emit `unknown flag:`, but that is a **different matcher** and pin 37 does not cover it.
- **`retention.cycle_log_read_paths` is operand-sensitive** (3 paths under the store convention, 2
  under a project dir — the switch is `retention.py:131`). Latent: every live caller passes the
  native store. ⚠ It is also a **three-rung ladder read "last wins"**, so reading the first rung a
  human notices (the legacy native log) makes a true claim read false — measured once in this arc.
- **Guard 2's observable is the empty SNAPSHOT, not the dead roots — and a PARTIAL resolution
  escapes.** `audit_snapshot` (`:2745-2801`) has no early `return {}`: it returns `snap`, falsy iff
  **no file from any of the three roots was added**. So the guard fires on *all three roots
  contributing nothing*, which is strictly narrower than "the operand resolves to nothing". An
  operand that still resolves **one** root alive — a directory whose CLAUDE.md hierarchy exists but
  whose store and repo-doc roots do not — yields a non-empty snapshot, passes, and the census it
  produces is wrong by the other two roots. The predicate could be widened to test the roots
  individually, but that is a new instrument, not a repair of this one; recorded so the narrowing is
  a decision rather than an oversight.
- **The `{}`-before route is RC-1a's class by a SECOND route, and Guard 2 cannot see it.**
  `--snapshot` writes `json.dumps(audit_snapshot(project_dir), indent=2)` (`:5047`) and **prints the
  path** (`:5048`). Given an operand that resolves to nothing, that file's contents are the two bytes
  `{}` — and a later `--audit <that path> <real project>` admits it: the value is non-empty and the
  content parses to a `dict` (`:5079`), so `before = {}` and `audit_diff` reports **every project file
  as CREATED** (`:5053-5054` records exactly this fabrication, measured live as `+572,437 tok`).
  ⚠ RC-1b shut the arm RC-1a's own comment describes — the flag present with an **empty value** —
  which is a different operand: here the value is a perfectly good path naming a file that really
  exists. ⚠ And Guard 2 cannot fire, because its left conjunct is precisely the falsy `{}`. **The
  `before` conjunct is load-bearing in BOTH directions**: it is what keeps the refusal clearable
  against a legitimately emptied tree, and it is what leaves this route open. Guard 1 covers only a
  store-shaped operand, so an operand that is merely *wrong* — a bare directory, a sibling project —
  passes both guards at `--snapshot` and arms the next `--audit`.
- **`--diffs` is a ceiling rather than a site, and the reason is the arm's own contract.** Its
  `capture_diffs` is the third `audit_snapshot` producer *and* it does take a before-operand, so the
  §2.2 table's second column reads **yes** there. But the arm pins a capture failure to **exit 0 with
  a named skip** (`:5332`'s try-comment, `except` at `:5348`) — *"a diff-capture failure must NEVER
  crash a dream"* — so Guard 2's fatal `return 2` cannot be hosted there without contradicting the
  promise the arm already keeps. Guard 1 covers its operand instead. Recorded explicitly because a
  reader comparing the table to the code would otherwise find the one row whose placement rule has no
  site, and would have to guess whether it was an oversight or a ceiling. It is a ceiling.
- **Guard 1 at the pool runs on EVERY invocation, including a no-positional one.** The pool's
  consumer is `project_dir = Path(pos[0]) if pos else Path.cwd()` (`:4934`), so an invocation with no
  positional — `--json` run from a shell whose cwd happens to be inside a store — now refuses (rc=2)
  where it previously seeded a record against the phantom slug that cwd derives. That is the intended
  reading (a store is not a project, and the refusal's own remedy names the fix), and no fixture in
  the suite exercises it, so it is recorded as a **new refusal on the hot path** rather than as a
  measured regression. The false-positive control (row 16) samples the ordinary cases — a real
  project directory, and a directory with no marker at all — which is where a widened guard is most
  likely to break, and it is green.

## Contract impact

**None that forces a minor bump.** No `CycleRecord` field is added, removed, or renamed; no CLI flag
is removed or renamed; legacy records still render; an existing install keeps working. R1 makes
`--persist` exit **5** where it exited 0 — but only on a **defective** input: a record whose seeded
`before_timestamp` and the state file's current stamp are the *same value*, meaning the file never
advanced during this cycle. Exit 5 is the already-documented arm for exactly that state, and the
remedy it prints **clears it** (a re-stamp writes a new `_utc_iso_now()`). ⇒ **patch.**

## Acceptance

- A record whose `before_timestamp` **equals** the state file's stamp — the file untouched since
  Phase 0 — **cannot** reach a clean persist: it exits 5 with a cause-named remedy, and no line is
  appended. ⚠ Its **converse is equally required**, because a refusal that never clears is a wedge:
  a record whose file stamp genuinely *differs* persists, and so does one whose `before_timestamp` is
  absent or `""` (no baseline), or a placeholder or junk (a baseline that cannot match).
- A record whose stamp belongs to this cycle persists exactly as today; a record with no
  `before_timestamp` still fills; `--audit` keeps its commit coordinate on a half-stamp source.
- `--diffs` given such a record does not lose its sidecar **silently**.
- `--audit` given a store dir **refuses**, mints no directory (at `:5344` or `:5171`), and emits no
  census.
- `--persist`, `--diffs` and `--audit` each name the *cause* they actually hit.
- No check in the suite regresses; every PIN above is measured red on `29cdfb33` and green on the fix,
  on a **named interpreter**, with its fixture carrying the inputs the predicate reads.
