# Mention-tier attribution — instrument the hook channel (P3)

**Status:** shipped (this PR). **Scope:** `extract_signals.py` (`_recall_items` mention scan,
`split_dream_span` generalization, `recall_scan`) + the `Usage` schema/validator + `usage_history`
+ `fleet_utility`. The eighth increment of the audit's enhancement program (signal-sufficiency
lens, P3).

## The measured problem

The always-loaded index HOOK is the mechanism by which memory mostly works — a fact's one-line
`description:` sits in context every session and the agent acts on it, often WITHOUT ever Reading
the body. Body Reads were the ONLY detector, and the live read volume is near-silent (~1 organic
read across 27 canonicals). So the demotion/gc loop was correctly paralyzed: it could never
corroborate that read-silence means dormancy. **MEASURED premise (this repo, read-only): 218
mention occurrences across 28 distinct stems vs 132 reads across 17 — and 13 stems were mentioned
but NEVER read.** Those 13 are facts used purely through the hook, invisible to the read detector.

## Design — a second, more sensitive detector on the same transcripts

- **`_recall_items` gains a mention scan**: a compiled word-boundary alternation of the store's
  mentionable stems (built once in `recall_scan`, longest-first so a prefix stem can't shadow a
  longer one) run over ASSISTANT text blocks. A cheap raw-line regex pre-filter skips the majority
  of lines before any `json.loads`. Emits `{"kind": "mention", ...}` items.
- **Conservative guards, all pinned**: BINARY per (message, stem) — a rumination loop can't
  inflate; a single message naming ≥ `_MENTION_DUMP_GUARD` (4) distinct stems is an index-dump /
  triage listing → all its mentions dropped; assistant-authored text only (user pastes excluded);
  archive stems excluded (a named archived pointer is not a recall); a **degenerate-stem guard**
  (a stem must be ≥12 chars or have ≥2 hyphens — a short generic stem matches too loosely in
  prose). Dream-span excluded via the same `split_dream_span` (generalized to partition reads AND
  mentions; the dream procedure names stems constantly — exclusion is mandatory).
- **Its own channel, NOT per_fact**: `recall_scan` emits window `mentions: int` (distinct stems
  named, binary) + `mention_stems: list[str]` (capped). Deliberately NOT folded into `per_fact` —
  that would break usage_history's `facts_read == len(per_fact)` probative-window rule and starve
  the demotion gate. `per_fact` stays reads-only.
- **DISPLAY-ONLY in v1**: `usage_history` unions `mention_stems` across windows (positive evidence
  never discarded, like reads/misses); `fleet_utility` attributes a mention through a MIRROR only
  (same gate as reads) and emits a `mentions` column — a 0-reads canonical with hook activity
  reads as *instrumented-but-hook-active*, not dormant. NO veto, NO demotion consumption yet: a
  mention is corroborative evidence, never sole grounds (the pinned bias). Only after real windows
  show the measured mention rate does a vote on "any mention ever ⇒ demotion veto" happen — a
  one-line change at that time, never a fitted weight.

## Reach limits (documented)

A stem quoted from a fact BODY the agent just Read (a wikilink) co-occurs with in-context material
— the binary-per-window + ≥4-stem-dump guards bound it, and mentions are corroborative, never
sole grounds. A mention without a Skill/Read tool_use in some harness path stays invisible
(undercount, the pinned direction). No embedding/fuzzy matching — an exact identifier match is
deterministic, stdlib, auditable.

## Acceptance gates

1. `split_dream_span` partitions reads AND mentions by the arc span (reads-only fixtures
   unaffected — pinned); the detector's binary/dump-guard/user-excluded/degenerate-guard behavior
   (pinned end-to-end from a fixture transcript); `per_fact` stays reads-only (the probative
   invariant untouched).
2. `usage_history` unions `mention_stems`; the validator backstops an over-cap list;
   `fleet_utility` attributes a mention mirror-gated, display-only key.
3. Live `--recalls` on a real repo surfaces mentions where reads are 0 (verified).
4. Full gates: smoke + sim + mypy + manifests.
