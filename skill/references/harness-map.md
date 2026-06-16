# Harness map — data sources, memory formats, verification recipes

Read this when you need the exact paths, file formats, or grep/git recipes for a
consolidation pass. The SKILL.md body covers the workflow; this is the lookup table.

## Lineage: mimo `/dream` → Claude Code

This skill adapts the mimo harness's `/dream` memory-consolidation command. The
concept is identical (read memory + trajectory, verify claims against the live
codebase, update/prune the memory store); the substrate differs:

| mimo `/dream` | Claude Code equivalent |
|---|---|
| `<DATA>/mimocode.db` (SQLite trajectory) | session transcripts `~/.claude/projects/<slug>/*.jsonl` (JSONL, large — never bulk-read) |
| single `<DATA>/memory/` (MEMORY.md, checkpoint.md, notes.md) | **two** stores — see below |
| `[ses_xxx]` session citation | a commit SHA, or the session `.jsonl` basename |
| serial claim verification | **parallel** fan-out via Explore / general-purpose subagents |

## The two memory stores

Claude Code splits memory across two places. Reconciling them — and keeping them
from contradicting each other — is the core enhancement over single-store `/dream`.

**1. Repo-committed docs (shared, in git):** `MEMORY.md`, `AGENTS.md`, `CLAUDE.md`
at the project root. These travel with the repo and the team reads them. `AGENTS.md`
is usually the architecture/gotchas source of truth; `MEMORY.md` a consolidated
snapshot; `CLAUDE.md` conventions. Edit them like code (they show up in `git diff`).

**2. Claude's private auto-memory (per-user, NOT in git):**
`~/.claude/projects/<slug>/memory/` where `<slug>` is the project's absolute path
with every `/` replaced by `-` (e.g. `/home/you/project/foo` →
`-home-you-project-foo`). Verify the slug rule with `ls ~/.claude/projects/`
rather than assuming it. Layout:
- `MEMORY.md` — the index, one line per fact: `- [Title](file.md) — hook`. Loaded
  into context every session. Never put fact bodies here.
- `<name>.md` fact files — one fact each, with frontmatter (match the EXISTING
  files exactly; confirm by reading one before writing — the live schema includes
  `node_type: memory`):
  ```markdown
  ---
  name: <short-kebab-case-slug>
  description: <the RECALL KEY — see below; not just a summary>
  metadata:
    node_type: memory
    type: user | feedback | project | reference
  ---

  <the fact. For feedback/project, follow with **Why:** and **How to apply:** lines.
  Link related memories with [[their-name]].>
  ```
  Types: `user` (who the user is), `feedback` (how to work — include the why),
  `project` (ongoing goals/constraints not derivable from code; absolute dates),
  `reference` (pointers to URLs/dashboards/tickets).

  **`description:` is a recall key, not a summary.** Fact files are pulled into a
  future session only when their `description:` matches that session's task (recall
  is relevance-matched, and the recalled fact arrives inside a `<system-reminder>`).
  So phrase the description as the *situation you'd want it to surface in* —
  include the concrete nouns a future task would mention. A true, useful fact with a
  vague description is effectively invisible.

## The three context-loading tiers

The two stores back three tiers that differ by HOW they reach a future session's
context. Place each fact by its tier, then optimize it for that tier:

1. **Always-loaded (deterministic, every session):** `CLAUDE.md` + the auto-memory
   `MEMORY.md` index. Confirm what's actually injected by inspecting your own context
   block (currently these two; NOT repo `AGENTS.md`/`MEMORY.md`). Most expensive —
   keep ruthlessly lean; only whole-project-framing facts earn a slot.
2. **Recall-loaded (non-deterministic):** auto-memory fact files, surfaced by
   `description:` match. Invest in the description (recall key) and `[[links]]`.
3. **On-demand (the agent reads them):** repo `AGENTS.md`/`MEMORY.md` + fact bodies.
   Not auto-injected — optimize for completeness, not per-session leanness.

**Operational state (not a fact):** `~/.claude/projects/<slug>/memory/.consolidation-state.json`
holds `{commit, timestamp}` — the high-water mark of the last consolidation. Read it
in Phase 0 (scope `git log <commit>..HEAD`); rewrite it in Phase 5.

## What belongs where

- A fact useful to **anyone** working the repo (architecture, a gotcha, a
  convention, a verified design decision) → repo docs (`AGENTS.md`/`MEMORY.md`).
- A fact about **the user, their preferences, your working relationship, or
  cross-session project context** not derivable from code → private auto-memory.
- **Never duplicate** the same fact in both stores. If it's in the repo docs, the
  auto-memory should at most point at it, not restate it. De-duplication across the
  two stores is the headline win of this skill — check the repo docs before adding
  anything to auto-memory.
- **Never** save what the repo already records (code structure, git history, a fix
  that's already a commit). Save the *non-obvious why*, not the diff.

## Verification recipes (Phase 3)

Every candidate fact is verified against the live tree before it lands. Claims are
small strings; verify each cheaply. Recall-biased: if a claim can't be verified,
flag it — don't silently keep it.

- **File/dir exists:** `test -e path && echo ok`
- **Symbol/function/flag exists:** `grep -rn "def the_function\|the_flag\|CONST" src/`
- **Claim matches current code (not stale):** read the cited lines; confirm the
  named behavior is still there (e.g. a memory says "X is headless" — grep the
  config default / the call site).
- **Decision landed in git:** `git log --oneline -S '<string>'` or
  `git log --oneline <marker>..HEAD -- <path>`
- **Doc claim self-consistency:** does `AGENTS.md`'s test count match
  `pytest -q`? Does a named module still exist?

Wrong/stale → correct it (cite the real current state). Unverifiable → drop it or
mark it explicitly as unverified. Never invent a citation.

## Secrets firewall

Transcripts and `config.toml`-style files contain raw secrets (this project's
`config.toml` holds a plaintext credential, gitignored). **Never** copy
credentials, tokens, API keys, or PII from a transcript or config into ANY memory
store — repo docs are committed and auto-memory persists. Record a *pointer*
("credentials live in `config.toml`, gitignored") not the value.

## Cross-project (the global tier)

Recall is **slug-scoped**: a project auto-recalls only its own
`~/.claude/projects/<slug>/memory/`. There is no verified global recall tier (the
harness even makes per-slug stores for non-project cwds). Two consequences shape the
cross-project model:

- **Renaming a project dir orphans its memory.** The slug is the path with `/`→`-`,
  so renaming `~/project/foo` → `~/project/bar` moves the store from slug
  `-home-you-project-foo` to an empty `-home-you-project-bar` — stranding every fact
  under the old slug. Canonical cross-project facts must live somewhere slug-independent.
- **Global facts don't auto-cross** — they must be replicated into each project's
  store to surface there.

**Model:** a global store `~/.claude/memory/` (same fact-file + index format) is the
canonical home for facts with `scope: stack-general` or `user-global`. Each global
fact carries extra frontmatter: `scope`, `stacks: [python, rag, gpu, mypy, …]`
(relevance matching), `projects: [...]` (provenance). `sync_global.py`:
- `--list PROJECT_DIR` — show relevant/present/missing (read-only).
- `--pull PROJECT_DIR` — replicate missing relevant global facts into that project's
  store (additive, marked `global_ref:` so they re-sync), AND refresh stale mirrors +
  **upsert** the always-loaded index pointer so its hook tracks the canonical's
  `description` (a changed description rewrites the index line, not just the body).
  user-global → every project; stack-general → only if `stacks` intersect the
  project's detected stacks. Stack keywords match on **token boundaries** (`_kw_hit`),
  not substrings — so `skill` no longer matches `reskilling` while `.claude` still
  matches `.claude/`.
- `--gc PROJECT_DIR [--apply]` — reclaim **orphaned mirrors**: `global_ref:` files
  whose canonical was deleted from the global store. `--pull` can never remove these
  (it only iterates live globals), so they accrue forever without GC. Report-only by
  default; `--apply` deletes the file + its index pointer. **Only** touches
  `global_ref:` mirrors — never a project-authored fact, even on a name collision.
  Dead-edge provenance (canonical lists a project that no longer holds the mirror) is
  reported, not auto-pruned (absence-of-mirror is too weak a signal to write global
  state on — a renamed store also "holds nothing").

### Token observability (the per-session tax, made visible)

- `--tokens PROJECT_DIR [--json]` — estimated token cost across the **neural network**.
  A node is a **project memory store holding ≥1 shared (`global_ref:`) mirror** — the
  physical, *measurable* node set (we have each store's path). This deliberately
  differs from `--network`'s logical `minds` set, which is derived from provenance
  *basenames* that can't be inverted to a store path: **`--network` = topology,
  `--tokens` = cost**, and the two can diverge (names vs slugs). Per node it reports
  always-loaded (index) + recall-pool (fact-body) tokens; the `--json` form is the
  cycle record's `network` block.
- **Tokens are estimates** (`est_tokens` ≈ `chars/4`, in `memory_status.py`; reused by
  `sync_global` via sibling import). There is no tokenizer — the zero-dep constraint
  rules one out. Always present token figures as `≈`, never as exact.
- **Always-loaded budget ceilings** live in `memory_status.py` as
  `INDEX_TOKEN_BUDGET` / `CLAUDE_MD_TOKEN_BUDGET` (heuristic, tunable). It sets
  `budget.*.over` when a tier exceeds its ceiling; the dashboard renders ⚠. This is the
  "stated budget" the always-loaded tier always implied but never encoded.
- **Re-verification signal:** `memory_status.py` lists facts untouched since the marker
  (mtime ≤ marker timestamp) as re-verification candidates — a cheap staleness proxy
  needing no per-fact `last_verified` field.

A fact's **scope ≠ its tier**. Scope = how widely it applies (project/stack/user);
tier = how it loads (always/recall/on-demand). A `user-global` fact is still a
recall-tier fact *in each project it's replicated to*. Peers that aren't CC projects
(e.g. a data vault of versioned processing artifacts, not CC sessions) can't
auto-participate — they'd need a separate adapter; deferred.

## Why claims-first, not transcript-first

The active transcript can be tens of MB. Never hand a subagent "read the
transcript." In Phase 2 extract a short list of discrete candidate claims (from the
two `MEMORY.md`s + `git log <marker>..HEAD` + at most the transcript *tail*), then
in Phase 3 fan out verification of *those specific claims*. Small inputs, cheap runs.
