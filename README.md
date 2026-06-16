# consolidate-memory

**Sleep-time memory consolidation for Claude Code agents — with a cross-project shared
consciousness.**

A deliberate, verifiable pass that turns the fluid experience of a work session into
*durable, fact-checked memory* — and keeps that memory accurate, lean, and shared
across every project you work in. It's the agent analogue of what sleep does for a
brain: replay recent experience, keep what's true and useful, discard the rest.

You invoke it by saying **`dream`** (or "consolidate my memory") in any project.

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  DREAM · consolidate-memory     [ LIGHT PASS ]
  my-project · session a1b2c3d
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Scope      git a1b2c3d..HEAD (0 commits) · 5 session candidate(s) · 8 memories reviewed
  Verified   ✓ 1 confirmed · ~ 0 corrected · ⚠ 0 unverifiable  [inline]
  Changes
    + added    <global> recall/global   claude-code-memory-is-slug-scoped
    · skipped  <proj>   —               session-workflow-requests  (control flow, not durable)
  Always-loaded budget   index 7→8 ln (905→1100 B) · recall facts 5→6
  Cross-project (global tier)   ~/.claude/memory: 4 facts
    ↑ promoted (here→global) claude-code-memory-is-slug-scoped <global>
  Health     ✓ all pointers resolve
  Marker     → a1b2c3def456 @ 2026-06-16T00:00Z
```

## Why

LLM agents forget everything between sessions except what's written to memory — and
most "memory" rots: it's never verified against the code, it duplicates what git
already records, it bloats the context budget, and it's trapped inside one project.
`consolidate-memory` fixes all four:

- **Verification is the heart.** Every candidate fact is checked against the *live*
  codebase (grep / file & symbol existence / `git log`) before it can land. A claim
  that can't be verified is dropped, not kept.
- **Context-budget aware.** It knows *how* Claude Code loads memory (below) and puts
  each fact in the tier that fits — keeping the always-loaded tier ruthlessly lean.
- **Cross-project shared consciousness.** Facts that generalize (preferences, env
  gotchas, stack patterns) flow into a global store and replicate into every project,
  so what you learn in one project sharpens all of them.
- **Honest, data-driven output.** A no-op pass and a heavy pass look different; the
  dashboard is rendered from a structured record of what the pass actually did.

## The model: three context-loading tiers

A fact only helps a future session if it actually reaches that session's context —
and everything that loads costs tokens. Claude Code loads memory in three tiers:

| Tier | What loads | Consolidation rule |
|---|---|---|
| **Always-loaded** | `CLAUDE.md` + the auto-memory `MEMORY.md` index, injected every session | scarce & expensive — only project-framing facts, kept lean and exactly right |
| **Recall** | auto-memory fact files, surfaced when their `description:` matches the task | the `description:` is a **recall key** — write it as the query you'd want to match |
| **On-demand** | repo docs + fact bodies, read when relevant | optimize for completeness, not per-session leanness |

The product of a pass isn't tidy files — it's *correct, well-budgeted context loading*.

## Cross-project shared consciousness

Claude Code recall is **slug-scoped**: a project only auto-recalls its own
`~/.claude/projects/<slug>/memory/`. So a global store alone wouldn't surface
anywhere. The fix:

- Facts get a **`scope`**: `project-local`, `stack-general`, or `user-global`.
- Cross-scope facts live canonically in a **global store** `~/.claude/memory/`.
- They're **replicated** into each project's store (so they actually recall there),
  and each fact's `projects:` provenance grows as it spreads — that provenance is the
  network's edge set.

`./cm network` renders the result:

```
SHARED CONSCIOUSNESS — cross-project memory network
  minds (projects) : 2  —  rag-pipeline, web-scraper
  shared memories  : 4 fact(s)
  topology (shared-memory edges):
            rag-pipeline   ●━━━━●   web-scraper    (4 shared)
```

## Install

```bash
git clone <this-repo> ~/project/consolidate-memory
cd ~/project/consolidate-memory
./install.sh        # symlinks the skill + shared memory into ~/.claude
```

`install.sh` is idempotent and safe (it backs up — and merges — any existing
`~/.claude/memory` rather than clobbering it). Then run `/reload` in Claude Code.
Because the skill is symlinked at the **user level**, it's available in *every*
project automatically.

## Usage

In any project, just say **`dream`** — or "consolidate my memory" / "what should I
remember from this?". The skill runs a 6-phase pass (locate → orient + pull globals →
gather candidates → verify → consolidate → render). You can also drive the pieces
directly:

```bash
./cm status            # Phase-0 context: stores, git range since last pass, marker
./cm extract           # curated session signal (human turns + error-gotchas, secrets omitted)
./cm pull .            # replicate relevant global facts into this project
./cm network           # the cross-project shared-memory graph
./cm render cycle.json # render a dashboard from a cycle record
```

## How retrieval works (and why it's safe)

A probe of real transcripts showed the signal is tiny and isolated, so retrieval is
**claims-first**, never "read the whole transcript" (they can be tens of MB):

- **git `marker..HEAD`** → *project* facts (what changed + why; highest precision).
- **human turns** (<1% of the transcript) → *feedback / preferences*.
- **error tool-results** (~1% of tool calls) → *gotchas* (env/tooling surprises).

`extract_signals.py` streams the transcript, **scopes to the last-consolidation
marker** (so a re-run is cheap), drops harness/skill noise, **omits credential-shaped
turns at the point of retrieval** (secrets firewall), ranks by signal, and returns
structured candidates. Nothing verbatim-secret ever reaches a memory file.

## Architecture

```
consolidate-memory/
├── skill/                       # the Claude Code skill (symlinked into ~/.claude/skills)
│   ├── SKILL.md                 # the 6-phase workflow + the loading-tier model
│   ├── references/harness-map.md# paths, fact schema, verification recipes, cross-project model
│   └── scripts/
│       ├── memory_status.py     # Phase 0: locate stores + git scope + cycle-record seed
│       ├── extract_signals.py   # Phase 2: curated, secret-safe session signal
│       ├── sync_global.py       # cross-project: replicate + provenance + --network
│       └── render_dashboard.py  # the data-driven dashboard
├── memory/                      # the shared-consciousness store (GITIGNORED — local only)
├── cm                           # one-entry CLI over the scripts
├── install.sh                   # symlink installer (idempotent, safe)
└── tests/smoke.py               # zero-dependency smoke tests
```

## Privacy

The `memory/` store is **gitignored** — your consolidated memory is personal and
never leaves your machine via this repo. The skill itself is generic (no hardcoded
projects, paths, or identities). The secrets firewall applies at *retrieval*, so a
credential in a transcript is omitted before it could ever reach a fact file.

## Lineage

Adapted from the mimo harness's `/dream` command — but rebuilt natively for Claude
Code rather than ported. The defining difference is the tier-aware, cross-project
model above, which mimo's single flat store has no concept of.

## License

MIT — see [LICENSE](LICENSE).
