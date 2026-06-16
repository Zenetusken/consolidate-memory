---
name: consolidate-memory
description: >-
  Consolidate this project's durable memory — the agent equivalent of sleep-time
  memory consolidation. Reads recent session work + git history, verifies every
  candidate fact against the LIVE codebase, and reconciles BOTH memory stores (the
  repo's MEMORY.md/AGENTS.md/CLAUDE.md and Claude's private per-project
  auto-memory), correcting or pruning stale entries. A deliberate, write-heavy
  checkpoint — invoke ONLY when the user explicitly asks to consolidate / reconcile
  / checkpoint / "settle" / "save what you learned" / "dream" their memory, or
  "what should I remember from this?", usually after a substantial session or when
  memory feels stale or self-contradictory. Do NOT trigger on other senses of
  "memory": RAM/VRAM/GPU memory, an embedding or style cache, a `memory_limit`
  setting, a database, a casual "remember to do X" aside, or a plain session recap
  with no intent to persist.
---

# Consolidate Memory

A deliberate pass that turns the fluid experience of a work session into **verified,
durable facts** — and keeps the project's two memory stores accurate and
non-contradictory. It's the agent analogue of what sleep does to memory: replay
recent experience, keep what's true and useful, discard what isn't.

This adapts the mimo harness's `/dream` command to Claude Code — but it is **not**
a path-swap of it. The defining difference is below: Claude Code loads memory into
context in tiers, and a consolidation pass is really an act of **curating what
loads, when, and at what cost** — a concept mimo's single flat store doesn't have.
The exact paths, formats, and recipes live in **`references/harness-map.md`** — read
it in Phase 0 and whenever you need a detail. Don't restate it from memory; the
substrate drifts, so re-confirm it (see "verify your own context" below).

## How your memory actually loads (the model everything here optimizes)

The product of a consolidation pass is not tidy files — it is **correct,
well-budgeted context loading**. A fact only helps a future session if it reaches
that session's context, and every fact that loads costs tokens and frames your
attention. Claude Code loads memory in three tiers, and each fact belongs in the
one that fits how often it's needed:

1. **Always-loaded (deterministic — paid every single session):** `CLAUDE.md` and
   the auto-memory **`MEMORY.md` index** are injected into context on every session.
   This is the most expensive, most powerful tier. A stale or wrong line here taxes
   and misleads *every* future turn. Treat it as scarce: only facts that frame the
   whole project earn a permanent slot, and they must be lean and exactly right.
   Confirm what's actually injected by looking at your own context block — currently
   that's `CLAUDE.md` + the auto-memory `MEMORY.md` index (NOT repo `AGENTS.md` or
   repo `MEMORY.md`), but verify rather than assume.

2. **Recall-loaded (non-deterministic — surfaced when relevant):** auto-memory
   **fact files** are pulled into a future session's context (inside a
   `<system-reminder>`) when their `description:` matches that session's task. So the
   `description:` is a **recall key, not a summary** — write it as the query you'd
   want it to match. A true, useful fact with a weak description is effectively
   invisible. This lever has no equivalent in single-store `/dream`; use it well.

3. **On-demand (you read them when relevant):** repo `AGENTS.md` / `MEMORY.md` and
   the fact-file *bodies*. These are not auto-injected, so they don't tax every
   session — optimize them for completeness and accuracy for the team/yourself, with
   less leanness pressure than tier 1.

Two physical stores back these tiers (see `references/harness-map.md` for the slug
rule + frontmatter schema): **repo-committed docs** (`MEMORY.md`/`AGENTS.md`/
`CLAUDE.md`, shared, in git) and **private auto-memory** (`~/.claude/projects/
<slug>/memory/`, per-user, not in git). Reconciling them — and never duplicating a
fact across them — is core; but place each fact by its **tier** (how it loads), not
just its store.

**Cross-project (the global tier).** Some facts aren't project-specific — user
preferences, environment gotchas, stack-general patterns (e.g. a `gh pr edit` env
bug, a typed-stubs preference, RAG/GPU lessons reusable across same-stack
projects). Those get a **`scope`**: `project-local`, `stack-general`, or
`user-global`. Cross-scope facts live canonically in a **global store**
`~/.claude/memory/`. But recall is **slug-scoped** — a project only auto-recalls its
*own* store — so global facts must be **replicated** into each project's store to
surface there (they don't auto-cross). `sync_global.py` does that replication; the
phases below call it. (Renaming a project dir changes its slug and **orphans** its
old auto-memory — another reason the canonical copy lives in the slug-independent
global store.) See `references/harness-map.md` § "cross-project".

## Why this is its own ritual (and not automatic)

Consolidation **writes** memory that the team and every future session rely on, and
it costs real work (git history, verification fan-out). So it runs only when
explicitly requested — never opportunistically mid-task. The payoff compounds: a
right fact in the always-loaded tier silently sharpens every future session; a wrong
one silently degrades it. That asymmetry is why **verification is the heart of this
skill**, and why facts that load deterministically get the harshest scrutiny.

## Workflow

Work the phases in order. Phases 0–3 are read-only investigation; Phase 4 is the
first write, and you **show the user the proposed consolidation before writing it**
(report-then-apply) so a consolidation pass never silently churns committed docs.

### Phase 0 — Locate data + the high-water mark

Run the bundled helper (it derives paths, inventories both stores, and computes the
git range since the last consolidation — don't hand-derive these):

```bash
python3 ~/.claude/skills/consolidate-memory/scripts/memory_status.py
```

It prints: the repo docs, the private auto-memory files, the transcript inventory
(report only — **never bulk-read the `.jsonl`; it can be tens of MB**), the last
consolidation marker (`commit` + `timestamp`), and `git log <marker>..HEAD`. If
there's no marker, treat this as the first consolidation and scope to the recent
git log + the current session. If both stores are empty and there's nothing new
since the marker, report "Nothing to consolidate" and stop.

Then **seed the cycle record** — the structured data that becomes the final
dashboard (see "Output" below). Re-run the helper with `--json` to capture the
measured before-state (scope, before-budget, marker) into a working file you'll fill
in as you go:

```bash
python3 ~/.claude/skills/consolidate-memory/scripts/memory_status.py --json > /tmp/cycle.json
```

You'll add to `/tmp/cycle.json` through the phases (candidates, verification tallies,
entries, after-budget, health) and render it at the end. Set `session` to the active
session id.

### Phase 1 — Orient

Read fully: both `MEMORY.md`s (repo + auto-memory index), the auto-memory fact
files, and skim `AGENTS.md`/`CLAUDE.md` for the sections facts would land in. Build
a mental model of what's already recorded so Phase 2 can dedup against it.

Then **pull relevant global facts** so this project recalls them and Phase 2 can
dedup against them too (cross-project step; safe + additive):

```bash
python3 ~/.claude/skills/consolidate-memory/scripts/sync_global.py --pull .
```

This replicates any `user-global` (and stack-matching `stack-general`) facts from
`~/.claude/memory/` that are missing here, and **refreshes any stale mirrors** whose
canonical changed (the script writes both the fact file and its index pointer). Read
its output and record `cross_project.pulled` (newly replicated) and
`cross_project.refreshed` in the cycle record. If nothing is missing/stale, no-op.

### Phase 2 — Gather candidate claims (claims-first)

Produce a short, explicit list of **discrete candidate facts** — each a single
verifiable sentence. There are **three sources, and they map to different memory
types** — don't over-index on any one (a probe of this harness showed the human's
typed messages are <1% of the transcript and carry only the *feedback* slice; the
*project* facts live in git and in observed behavior the human never typed):

1. **`git log <marker>..HEAD`** (commit bodies) → **project facts** (what changed +
   why). The strongest, highest-precision source — it happened and it's in git.
   `memory_status.py` (Phase 0) already lists this range; read the commit bodies.
2. **Session signal** → **feedback/preferences** (human turns) + **gotchas** (error
   tool-results). Don't read the raw transcript — run the extractor, which streams
   it, scopes to the marker, drops harness/skill noise, **omits credential-shaped
   turns** (secrets firewall at retrieval), and returns ranked, structured, scoped
   candidates:
   ```bash
   python3 ~/.claude/skills/consolidate-memory/scripts/extract_signals.py --json
   ```
3. **Existing memory entries that look stale** — candidates for re-verification.

For each candidate also assign a **`scope`**: `project-local` (specific to this
repo's domain), `stack-general` (a pattern reusable on same-stack projects), or
`user-global` (a preference or environment fact that holds everywhere — e.g. the
`gh pr edit` env gotcha, the typed-stubs preference). Scope is independent of tier;
it pre-stages cross-project sharing and sharpens "what belongs where" even today.

For each candidate, decide its **tier** (always-loaded / recall / on-demand — the
model above) and therefore its store and shape, and check whether it's already
recorded (dedup against Phase 1 — including across the two stores). Drop anything
the repo already records as code or git history; keep the non-obvious *why*. Be
especially stingy about proposing anything for the always-loaded tier — it must
earn its per-session cost.

→ **Cycle record:** set `scope.session_candidates` to the count of candidates you
surfaced from the session (the helper already filled `git_commits` and
`memories_reviewed`).

### Phase 3 — Verify (the heart; parallel)

Every candidate is verified against the **live tree** before it can land. Fan out:
spawn Explore / general-purpose subagents to verify batches of claims concurrently
(this is the parallel enhancement over serial `/dream`). Hand each subagent the
**specific claims** to check — never "read the transcript."

Verify with the recipes in `references/harness-map.md` § "verification recipes":
file/symbol existence (`grep`, `test -e`), claim-matches-current-code (read the
cited lines), decision-landed-in-git (`git log -S`), doc self-consistency (e.g. does
`AGENTS.md`'s test count match `pytest -q`?).

Be **recall-biased**: a claim that can't be verified is flagged, not silently kept.
Outcomes per claim: **confirmed** (lands), **stale/wrong** (correct it to the real
current state, cite it), **unverifiable** (drop, or keep only if explicitly marked
unverified and the user wants it).

→ **Cycle record:** tally `verification.confirmed` / `corrected` / `unverifiable`,
and set `verification.method` (`inline` or `subagents`).

### Phase 4 — Consolidate (report, then apply)

First, **present the proposed consolidation to the user**: what you'll add, correct,
or delete, in which **tier/store**, and why — a short diff-like summary. This matters
because Phase 4 writes committed docs and persistent memory; the user should see the
churn (and the per-session cost of anything headed for the always-loaded tier)
before it happens. Then apply, placing each fact in its tier and optimizing it for
how that tier loads:

- **Always-loaded tier** (`CLAUDE.md` + auto-memory `MEMORY.md` index): add only
  project-framing facts that pay their per-session rent. Keep both lean — prune a
  low-value line when adding one (the auto-memory index has a stated line/byte
  budget). The index holds *pointers only* (`- [Title](file.md) — hook`), never fact
  bodies. Update derived stats (test/module counts) only if you verified them here.
- **Recall tier** (auto-memory fact files): one fact per file with the frontmatter
  schema, and **invest in the `description:` as a recall key** — phrase it as the
  task-context you'd want it to surface in, not a terse summary, or it won't be
  recalled when it matters. Link related facts with `[[name]]`; pick the right
  `type`. Then add its one-line pointer to the index.
- **On-demand tier** (repo `AGENTS.md`/`MEMORY.md`, fact bodies): optimize for
  accuracy and completeness; these don't tax every session.
- **No cross-store duplication**: if a fact lives in the repo docs, an auto-memory
  entry should point at it, not restate it.
- **Global-scope facts** (`scope: stack-general` or `user-global`): write the
  canonical copy to `~/.claude/memory/` with `scope`, `stacks: [...]`, and `projects:
  [...]` (provenance) in the frontmatter, add a line to `~/.claude/memory/MEMORY.md`,
  AND keep a project-store copy so it recalls *here* (recall is slug-scoped). Other
  projects pick it up when they next run their own Phase-1 `--pull`. Don't move a
  fact out of a project store that currently recalls it — the global copy is additive.
  Record each promotion in `cross_project.promoted` (name + scope).
- **Cite** each new/changed entry with the commit SHA or session basename it came
  from, so a future pass can trace it.

→ **Cycle record:** append one object to `entries[]` for **every** decision — not
just writes but also `skipped` and `reconciled` ones, since "what I deliberately did
NOT record, and why" is part of the dashboard's signal. Each:
`{"action": "...", "tier": "...", "store": "...", "scope":
"project-local|stack-general|user-global", "name": "...", "reason": "...",
"citation": "..."}`. After writing, update `budget.*.after` (CLAUDE.md lines, index
lines/bytes, recall-fact count).

### Phase 5 — Prune, verify, update the marker, render

1. Re-read both `MEMORY.md`s: remove duplicates (within and across stores), fix
   broken file/symbol references, drop entries no longer relevant.
2. Re-confirm every file path / function name you referenced still exists.
   → **Cycle record:** fill `health` — `index_pointers_ok`, any `broken` pointers,
   any `dangling_links` (`[[name]]` wikilinks pointing at no target file). Strip
   inline code spans first: `[[...]]` inside backticks is NOT a wikilink (e.g. TOML
   `[[tool.mypy.overrides]]`) — don't flag those.
3. **Update the high-water mark**: write `commit` (current `HEAD`) + ISO
   `timestamp` to `~/.claude/projects/<slug>/memory/.consolidation-state.json` so
   the next pass scopes correctly (stamp the timestamp at write time), and mirror
   that `timestamp` into the cycle record's `marker.timestamp`.
4. **Render the dashboard** — this is the skill's output (see below):
   ```bash
   python3 ~/.claude/skills/consolidate-memory/scripts/render_dashboard.py /tmp/cycle.json
   ```
   Present the rendered dashboard to the user as the final message.

## Safety rules

These protect the stores from corruption and the user from leaks:

- **Secrets firewall.** Never copy credentials, tokens, API keys, or PII from a
  transcript or config file into ANY store (repo docs are committed; auto-memory
  persists). Record a pointer ("creds in `config.toml`, gitignored"), never a value.
- **Transcripts are read-only and large.** Report them; read only the tail if you
  must; never write to them or bulk-load them.
- **Surface deletions you didn't author.** Pruning your own stale entry is fine;
  before deleting a memory file or repo-doc fact you didn't write this pass, name it
  in the Phase 4 report and let the user confirm.
- **Don't invent citations.** A `[commit]`/`[session]` tag must point at something
  real. No fabricated session ids.
- **Don't duplicate the codebase.** If git or the code already says it, don't
  memorialize it — capture the non-obvious why.

## Output: the cycle record → dashboard

The output is **not** free-form prose. It's a fixed dashboard whose content is
driven by what the pass actually did. You accumulate a small JSON **cycle record**
through the phases (seeded by `memory_status.py --json`), then render it with
`render_dashboard.py` — the model produces the data, the script produces the
presentation, so the report is consistent run-to-run but reflects this cycle (a
no-op pass and a heavy pass render visibly differently; empty sections collapse, and
the outcome banner is derived from the write counts).

The render script is the single source of the final report — don't hand-write a
summary alongside it.

### Cycle-record schema

```json
{
  "project": "repo-name",
  "session": "<active session id>",
  "scope": {"git_range": "abc..HEAD", "git_commits": 0,
            "session_candidates": 0, "memories_reviewed": 0},
  "verification": {"confirmed": 0, "corrected": 0, "unverifiable": 0,
                   "method": "inline|subagents"},
  "entries": [
    {"action": "added|corrected|deleted|reconciled|skipped",
     "tier": "always-loaded|recall|on-demand|-",
     "store": "auto-mem|repo|-",
     "scope": "project-local|stack-general|user-global",
     "name": "<fact slug or short label>",
     "reason": "<why — esp. for skipped/deleted>",
     "citation": "<commit sha | session id | empty>"}
  ],
  "budget": {
    "claude_md": {"before": 0, "after": 0},
    "index": {"before_lines": 0, "after_lines": 0, "before_bytes": 0, "after_bytes": 0},
    "recall_facts": {"before": 0, "after": 0}
  },
  "health": {"index_pointers_ok": true, "broken": [], "dangling_links": []},
  "cross_project": {
    "global_store_facts": 0,
    "pulled": [{"name": "...", "scope": "user-global"}],   "_pulled": "Phase 1: global → here",
    "promoted": [{"name": "...", "scope": "stack-general"}], "_promoted": "Phase 4: here → global",
    "refreshed": 0
  },
  "marker": {"commit": "<HEAD>", "timestamp": "<ISO, stamped in Phase 5>"}
}
```

The dashboard derives its outcome banner (`NOTHING TO CONSOLIDATE` / `NO-OP PASS` /
`LIGHT PASS` / `SUBSTANTIAL PASS`) from the write counts unless you set an explicit
`outcome`. Keep entries honest — recording a `skipped` decision (and why) is as
valuable as recording a write.

## A note on scope

This skill intentionally skips the skill-creator's formal eval/benchmark loop — its
output (consolidated memory) is judged by correctness and usefulness, which the
report + the user's eye assess better than assertions. If you ever want hard trigger
metrics, the skill-creator's description-optimizer can be pointed at this skill's
description later.
