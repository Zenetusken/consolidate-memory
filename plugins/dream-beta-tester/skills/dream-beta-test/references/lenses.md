# Judgment lenses — the dynamic detector

Apply each lens to **this** run's actual artifacts: the rendered dream dashboard, the oracle
JSON (`run_beta.py --json` / `beta_checks.py --json`), and the live memory store. The lens is
the constant question; the finding is whatever this run surfaces. A lens hit is a **suspicion**
— it earns a place in the report only after the reduction (SKILL.md step 4): a reproducible
check, or a quoted source-contradiction. Anything unreduced stays in §2b (unverified), never
counted as a defect.

The lenses overlap on purpose — a real defect usually trips several. Don't force a finding
into exactly one; record it once, under the lens that frames it most sharply.

## Consistency — do any two numbers/statements disagree?
The oracle already auto-checks every quantity in its registry. **You** hunt the ones it
doesn't know about: a count in the dream's prose that contradicts a gauge; "N facts" in one
section vs another; a recommendation naming a number the data doesn't support; the same metric
rendered two ways.
- *Reduce:* quote both surfaces showing the mismatch.

## Honesty — does every claim match reality?
The dashboard **claims** things (added N facts, budget after = X, marker advanced, pruned K).
Re-derive each against the live store: did a fact file actually appear/disappear? does the
budget track file bytes/4? did `.consolidation-state.json` advance to HEAD? The worst class is
an **unclaimed store mutation** — a changed `*.md` not reflected in the dashboard delta and
outside the known side-file allowlist (`.consolidation-state.json`, `.consolidation-log.jsonl`,
the per-slug cycle temp). That is dashboard dishonesty.
- *Reduce:* show the real store delta vs the claimed delta.

## Completeness — did the dream skip something the inputs implied?
The git range / session implied certain facts — did the dream capture them or silently drop
them? Did a phase SKIP (e.g. the signal extractor) without recording why? Did a candidate that
clearly belongs in the always-loaded tier get lost?
- *Reduce:* name the implied-but-absent item and where it should have appeared.

## Coherence — do the gates + recommendations make sense together?
Does an active gate contradict an offer (the D3 backfill-under-gate class is already a family,
but new variants appear)? Does the rigor tier match the ceremony actually run? Does an invoked
"lever" actually resolve the condition it's invoked for, or just name it?
- *Reduce:* quote the two clauses that don't cohere.

## Safety — would following any suggestion lose data or break a reference?
Every destructive suggestion (evict / delete / de-link / prune / restore) — does it target
something still referenced (an index pointer, a `[[wikilink]]` in-degree from an indexed fact)?
The oracle checks the orphan-evict case; you check the rest: a prune that drops a load-bearing
pointer, a restore that would clobber unrelated work, a de-link that strands a fact.
- *Reduce:* show the suggestion + the live reference it would break.

## Calibration — are the budgets/tiers/severities sane for THIS store?
A threshold structurally unreachable for a mature store (permanent over-budget → alarm
fatigue); a severity that over- or under-states the harm; a tier headlined LIGHT on a gated
pass. These are usually **WARN/advisory** design feedback, not hard defects — say so.
- *Reduce:* show the number vs the store's actual size and why the calibration misfires.

## Usability — is the report itself clear, or self-contradictory?
The dashboard is the human's artifact. Two sections disagreeing, a gauge that misleads at a
glance, a recommendation a human cannot act on, an outcome banner that fights the body.
- *Reduce:* quote the confusing or contradictory rendering.

---

## Crystallizing a confirmed class (SKILL.md step 6)

If a confirmed finding is a **novel, general** class — not an existing family, not a one-off —
add a family to `~/.claude/dream-beta-tester/beta_checks.py`:

- a `(Ctx) -> list[Result]` predicate that scans for the **principle**, not the specific field
  that broke (general-via-registry where a surface extractor is needed — render emits human
  text, so be honest that those are field-aware);
- tie its PASS to the **fixed behavior** (the rendered clause / the JSON field that the fix
  introduces), never to a raw condition that passes by accident, so a genuine regression
  actually flips it FAIL;
- it then re-tests every run, in any repo — the harness compounds.

Do **not** crystallize a one-off or a still-unconfirmed suspicion. The family registry is the
regression floor; it must stay trustworthy.
