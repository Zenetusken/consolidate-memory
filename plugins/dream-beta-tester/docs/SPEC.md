# Dream Beta-Harness — SPEC v0.1 (draft for review)

A reusable, any-repo harness that runs the **consolidate-memory dream** as a faithful
consumer, adversarially verifies it, and emits one structured report per run = the dream
dashboard **+** a versioned, severity-ranked defect catalog. The agent analogue of a
fuzz-tested regression suite for a skill we are only allowed to *consume*, never patch.

> **Provenance:** distilled from two live beta runs on Doc_Flo (the v0.1.19 catalog) +
> the oracle prototype that falsified two of those hand-diagnoses (D1/D2) on its first
> run — the proof that a deterministic oracle beats eyeballing one dashboard.

---

## 1. Goals & non-goals

**Goals**
- One command, any repo: snapshot → run dream → oracle → structured report → offer-restore.
- Deterministic, **repeatable** defect detection (no eyeball drift) that **grows** each run.
- Honest by construction: every reported defect is empirically re-verified before it ships
  (measure-don't-assert), and the harness checks the dream's *own claims vs reality*.
- Version-aware: each report is stamped with the consolidate-memory version under test, so
  fixed-vs-open defects are trackable across patches.

**Non-goals**
- Never patches / modifies the consolidate-memory skill (consumer-only directive).
- Not a replacement for the dream — it *drives* the real, unmodified skill.
- Does not live under `/home/drei/project/consolidate-memory/`.

---

## 2. Placement & portability  *(decided: user-global)*

```
~/.claude/dream-beta-tester/
  SPEC.md                 # this file
  beta_checks.py          # the ORACLE engine (built, proven)
  render_beta_report.py   # structured report renderer  [TODO]
  snapshot.py             # store/doc snapshot + diff + restore  [TODO]
  checks/                 # (optional) check modules if registry outgrows one file
  reports/                # per-run reports: <repo-slug>__<cmver>__<ts>.md
~/.claude/agents/dream-beta-tester.md   # the SUBAGENT (judgment spine)  [TODO]
~/.claude/skills/dream-beta-test/SKILL.md  # invokable entry (optional)  [TODO]
```

**Any-repo rules (hard):**
- Never hardcode a project path. Derive the slug with the skill's own rule
  (`abs path with '/' AND '_' → '-'`, case kept) → `~/.claude/projects/<slug>/memory`.
- **Always invoke the skill's scripts with `cwd = target repo`** and capture from a CLEAN
  subprocess. (This is the lesson from the D1/D2 retraction: a stray cwd / contaminated
  cycle.json silently seeded *another* project's budget. The oracle reconstructs from a
  clean `memory_status.py --json` precisely to avoid that.)
- Discover the skill scripts via `$CONSOLIDATE_MEMORY_SCRIPTS` → plugin-root glob → fail loud.

---

## 3. Architecture — 3 layers

```
            ┌──────────────────────── SPINE (judgment) ───────────────────────┐
  /dream-beta-test  →  dream-beta-tester subagent:
            snapshot ─▶ run dream (faithful consumer) ─▶ ORACLE ─▶ verify FAILs ─▶ render ─▶ offer-restore
            └──────────────────────────────┬───────────────────────────────────┘
                                           │ deterministic
                          ┌────────────────▼─────────────────┐
                          │  ORACLE  beta_checks.py           │  ◀ the engine
                          │  • cross-script consistency       │
                          │  • claim-vs-reality (snapshot Δ)  │
                          └────────────────┬─────────────────┘
                                           │
                          ┌────────────────▼─────────────────┐
                          │  RENDERER  render_beta_report.py  │  ◀ structured report
                          └──────────────────────────────────┘
```

- **Engine** (`beta_checks.py`): pure, deterministic. Runs the skill's read-only scripts,
  cross-checks them + the live store, emits structured JSON. No judgment.
- **Spine** (subagent + skill): the only layer with judgment. Runs the real dream, decides
  the dream's JUSTIFY/prune calls with sane defaults, **re-verifies every oracle FAIL against
  source before it ships** (the oracle can mis-encode too), and appends a new check when it
  finds a novel defect class. Authored/eval'd with **skill-creator**.
- **Renderer**: turns oracle JSON + the dream dashboard into the report. Same
  "model produces data, script renders" split the dream itself uses.

---

## 4. Detection — dynamic per-run, never overfit

> **Governing principle (user directive):** the harness must catch what *each* dream run
> surfaces, and **act + write the report accordingly** — NOT re-run a frozen checklist of the
> bugs we happened to catch on one run. So detection has two co-equal parts, and the encoded
> checks are the regression **floor**, not the ceiling. The v0.1.19 catalog (D1–D11) is a
> *motivating corpus*, never the limit of what we look for.

### 4.1 General invariant oracle (deterministic) — encode PRINCIPLES, not fields
Each invariant is a **general predicate** computed structurally over the full output + store,
so it fires on a *novel* violation no one hand-wrote a check for — not a hardcode of the field
that broke last time. Families (each generalizes ≥1 D-example, but is defined by the principle):

- **Ground-truth & internal consistency** — driven by a **declared quantity registry** (not
  magic auto-discovery: render emits human *text*, so a surface extractor is inherently
  field-aware — the prototype's `auto-mem index ≈N` regex is the honest reality). Each registry
  entry = a quantity + its extractor on every surface it appears:
  `{json: path, render: regex, network: path, artifact: file·bytes/4}`. The family runs all
  *present* extractors per quantity and asserts they (a) agree across surfaces [consistency]
  and (b) track the artifact [ground-truth]. **General via the registry** — adding a quantity
  is one line that then scans every surface — without pretending to discover unlabeled numbers.
  Catches D1/D2/the-885 + any future same-quantity disagreement. ⊇ D1, D2.
- **Cycle identity** — the cycle record's project == the target repo (the D1/D2 root cause).
- **Recommendation coherence** — no recommendation contradicts an active gate or another
  recommendation (generalize: "the skill never simultaneously forbids and proposes X"). ⊇ D3.
- **Safe-suggestion** — no destructive suggestion (evict/delete/de-link) targets a
  still-referenced fact (index pointer OR `[[wikilink]]` in-degree). ⊇ D4.
- **Closure/reachability** — every recommended action is actually *achievable* (a prune that
  reaches budget; a lever that resolves the flagged condition; a link with a resolvable
  target). ⊇ D5, D10.
- **Claim-vs-reality** (needs the snapshot Δ) — every dashboard claim matches the real store
  delta; no unclaimed mutation; marker advanced; `budget.after` matches live files. The half
  a human tester skips, where silent dishonesty hides.

Mechanics: a predicate = `(Ctx) -> [Result]` (returns *zero or more* findings, since a general
predicate can fire on many sites). `Result` = `family, severity, status, expected, actual,
evidence, site`. Can't gather inputs → **SKIP with a reason**, never crash. Adding a family is
rare; adding a *site* the family scans is automatic.

### 4.2 Dynamic adversarial review (the subagent — judgment) — SECONDARY, novel-class only
**Primacy (advisor fix #2):** the *deterministic* families (§4.1) carry the trustworthy
dynamic-detection weight — they are general, per-run, AND reliable. "Dynamic" must NOT mean
"judgment-heavy": un-anchored lens findings produce confident-wrong defects exactly like the
retracted D1/D2. So the lens layer is the **secondary** detector — its job is to surface
*novel classes* the families don't yet cover, and **every lens finding is QUARANTINED as
"judgment-flagged (unverified)" until it reduces to either (a) a reproducible deterministic
check or (b) a quoted source-contradiction.** Only then is it cataloged as a defect; otherwise
it ships as an explicitly-unverified observation. Each run, the subagent reads THIS run's
actual artifacts (full dream output + store before/after) and applies a **fixed rubric of
lenses** open-endedly — lenses constant, findings per-run:

| lens | asks |
|---|---|
| Consistency | do any two statements/numbers disagree? |
| Honesty | does every claim match reality? (re-derive against the store) |
| Completeness | did the dream skip/miss something the inputs implied? |
| Coherence | do the gates + recommendations make sense together? |
| Safety | would following any suggestion lose data / break a reference? |
| Calibration | are budgets/tiers/severities sane for THIS store, or alarm-fatigue? |
| Usability | is the report itself clear, or self-contradictory? |

Every candidate finding is **re-verified against source before it ships** (measure-don't-
assert — the oracle and the lens are both hypotheses; this is the discipline that retracted
D1/D2). A confirmed novel finding is reported THIS run AND *may* be crystallized into a new
general family (registry growth) — but the dynamic finding is the primary output, not a static
pass/fail.

### 4.3 Output is run-shaped
The detector emits **whatever this run surfaced** — a clean dream yields a clean report; a
buggy one yields its specific findings. Each finding is tagged `new | known(Dn) | regressed |
fixed` by diffing against the prior report for this repo at an older skill version. Nothing is
asserted that wasn't found+verified *this* run.

### 4.4 `--json` gap (portability note)
`memory_status.py --json` omits the orphan list the human output shows → the Safe-suggestion
family **recomputes** orphans from `store files − index pointers` + the wikilink graph rather
than parsing human text (portable, no brittleness).

---

## 5. The spine — run flow (the subagent)

1. **Pre-flight**: derive slug/store; discover skill scripts; read the skill VERSION
   (plugin manifest) for the report stamp.
2. **Snapshot** (`snapshot.py`): copy the memory store + repo `MEMORY.md/AGENTS.md/CLAUDE.md`
   to a temp; record file hashes + the marker.
3. **Run the dream**: faithful consumer. Phases 0–5. Judgment calls (JUSTIFY/prune) taken
   with documented sane defaults so the run is reproducible; all decisions captured.
4. **Oracle**: `beta_checks.py --json` with the before/after snapshot wired in for half (b).
5. **Verify**: for each FAIL/WARN, the subagent **re-derives against source** (the oracle is
   a hypothesis too) — quote the evidence, or downgrade/retract. New defect class → append a
   check (registry growth) + flag it in the report.
6. **Render**: `render_beta_report.py` → `reports/<slug>__<cmver>__<ts>.md`.
7. **Offer-restore**: present the snapshot diff; restore the store to pre-dream state unless
   the user wants to keep the consolidation. (Default to restore — a beta-test shouldn't
   leave mutations.)

---

## 6. The report — run-shaped, structured, every run

Fixed *structure*, fully **dynamic content** (driven by what this run surfaced — a clean dream
renders a clean report). Version-stamped. Sections:
1. **DREAM DASHBOARD** — the skill's own rendered output, verbatim (the consumer artifact).
2. **BETA FINDINGS** — *only what was found this run*, in **two structurally separate groups**
   (advisor fix #2 — never blur confirmed with suspected):
   - **(2a) Deterministically confirmed** — oracle-family failures + lens findings that reduced
     to a reproducible check or a quoted source-contradiction. `family · severity · site ·
     expected / actual / evidence`, lifecycle tag `new | known(Dn) | regressed | fixed`.
   - **(2b) Judgment-flagged (UNVERIFIED)** — lens observations not yet reduced to a check;
     shipped explicitly as hypotheses for human triage, never counted as defects.
3. **RUN DELTA** — vs. the prior report for this repo: what's newly broken, newly fixed, still
   open. This is the cross-version signal that makes the harness a regression gate.
Footer: counts, consolidate-memory version under test, snapshot/restore disposition.
Nothing in the report is asserted that wasn't found+verified this run; an empty FINDINGS
section is a valid, good outcome.

---

## 7. Snapshot / restore  *(decided: snapshot → run → diff → offer-restore)*

- Snapshot = the memory store dir + the three repo always-loaded docs + the marker file.
- Cheap (a few hundred KB); copy to `reports/.snap-<ts>/`.
- Diff drives half-(b) checks AND the restore offer.
- Restore is the default for a pure test; keep-writes is an explicit opt-in.

---

## 8. Versioning & defect lifecycle

- Read consolidate-memory's version from its plugin manifest; stamp every report + every
  `defect_ref`'s catalog entry.
- A defect's check flipping FAIL→PASS across versions = **fixed**; PASS→FAIL = **regressed**.
  The harness becomes the skill's external regression gate.
- The standalone `~/<...>-defects.md` catalog stays the human narrative; the oracle is the
  machine-checkable mirror.

---

## 9. Decisions already locked
- Placement: **user-global `~/.claude/`** (not a plugin, not under the skill).
- Side-effects: **snapshot → run → diff → offer-restore** (default restore).
- Engine-first proven; **spec before further build** (this doc).
- Spine authored via **skill-creator** (description-optimization + eval loop).

## 10. Build plan (phased, each gated)
**Sequencing discipline (advisor):** the cheap core — oracle (§4.1 families) + a thin runner +
the renderer — is ~all the value, and two manual runs already proved the concept. P4/P5
(subagent-spine, skill-creator authoring, snapshot apparatus) must **earn** their complexity at
their gate; don't let the spine become the tail wagging the harness. Stop at the simplest thing
that produces the run-shaped report.
- **P1** Engine: rebuild `beta_checks.py` around the **general invariant families** (§4.1) —
  esp. the auto-pairing internal-consistency + cycle-identity + safe-suggestion(recompute
  orphans) families — so detection is principle-based, not field-hardcoded. Validate on
  Doc_Flo that the families reproduce the confirmed D3/D5/D4 *and* correctly clear D1/D2; N≥2
  for stability. The prototype (D-specific checks) is scaffolding to be generalized, not kept.
- **P2** `snapshot.py` + the half-(b) claim-vs-reality checks.
- **P3** `render_beta_report.py` + the report schema.
- **P4** Spine: the `dream-beta-tester` subagent + `/dream-beta-test` entry (skill-creator);
  eval its triggering.
- **P5** Validate end-to-end on a SECOND repo (the any-repo proof) — e.g. the consolidate-
  memory project itself or job-applicator — and diff the two reports.

## 11. Open questions for review
- **Q1** Spine shape: a user-global **skill** that spawns the subagent, vs. the subagent
  invoked directly (Agent tool)? (Lean: a thin `/dream-beta-test` skill → spawns the agent.)
- **Q2** Does the beta-test run a FULL judgment dream, or a **scripts-only** dream (oracle on
  the deterministic layer) by default, with full-dream as an opt-in? (Lean: scripts-only
  default — cheaper, deterministic, covers most defects; full-dream opt-in for the judgment
  path.)
- **Q3** Restore default: always restore, or keep-writes when the dream had real new facts to
  consolidate? (Lean: always restore in `--test`; keep in `--real`.)
- **Q4** Should half-(b) treat a *silent* unclaimed mutation as HIGH (dashboard dishonesty)
  or could legitimate derived-file churn trip it? (Need an allowlist of expected side files:
  `.consolidation-state.json`, `.consolidation-log.jsonl`.)
