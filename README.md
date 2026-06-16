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

`./cm network` shows the topology — the **universal baseline** (facts every project
holds) listed separately from the **differential edges** that carry real signal
(`stack-general` facts binding only the matching-stack projects). Early on, with only
universal facts, it honestly reads `N universal · 0 differential` — no real edges
yet. As stack-general facts accumulate, a graph emerges. Here's the **actual
`--network` output** for a matured network (illustrative project/fact names, but the
exact rendering the script produces):

```
========================================================================
SHARED CONSCIOUSNESS — cross-project memory network
========================================================================
minds (projects) : 5  —  api-gateway, doc-search, ml-trainer, rag-pipeline, web-scraper
shared memories  : 8  (4 universal · 4 differential)

  universal baseline (user-global — every mind holds these):
    • gh-pr-edit-broken-in-env
    • no-secrets-in-config-only-pointers
    • prefer-conventional-commits
    • prefer-typed-stubs-over-ignore

  differential edges (stack-general — the bindings that carry signal):
                  doc-search ●━━● rag-pipeline             (2 shared)
                  ml-trainer ●━━● rag-pipeline             (2 shared)
                 api-gateway ●━● web-scraper              (1 shared)
                  doc-search ●━● ml-trainer               (1 shared)
```

Read it as: all five projects share four **universal** facts (env + preferences — the
baseline). The **edges** are the stack-specific bindings: the RAG projects
(`rag-pipeline` / `doc-search` / `ml-trainer`) cluster tightly, the web projects
(`web-scraper` / `api-gateway`) form their own pair, and nothing RAG-specific ever
leaks to the web projects. Edge weight = how many stack-general facts the pair shares.

### How insights propagate (the honest model)

It's a **shared bloodstream, not telepathy** — and you never hand-edit another
project. When project **A** dreams and learns something cross-cutting:

1. **Deposit — instant.** The fact is written to the shared global store
   (`~/.claude/memory/`) and into A's own store. Done, zero friction.
2. **Absorb — lazy.** Other projects pick it up on **their** next dream (every
   dream's first step is a `pull` that ingests new facts and refreshes changed
   ones). Until B next dreams, B's memory doesn't have A's new insight.

So it's **eventually-consistent**, not a real-time broadcast. Why pull-based and not
push? Because Claude Code only auto-recalls a project's *own* memory folder — a fact
has to physically live in B's folder to surface in B's sessions, so it's *replicated*
there on B's pull (rather than us reaching into projects you're not working in and
editing them behind your back). The upshot: **no manual per-project busywork ever;
each project just syncs itself the next time you consolidate it.**

> Want instant whole-network propagation instead? That's a deliberate opt-in, not the
> default — it would write into every project's memory the moment any one of them
> learns something. The lazy-pull default keeps a project's memory changing only while
> *you're* in it.

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

## Design notes (for the curious)

A few load-bearing choices, in case you're poking at the code or wondering "why is it
built this way" — written to be readable whether you're vibe-coding or shipping prod:

- **Verification is a gate, not a vibe.** Every candidate fact is checked against the
  *live* code/git before it's allowed into memory; anything unverifiable is dropped.
  This is the whole anti-hallucination point — memory you can't trust is worse than no
  memory. (See `extract` → verify in `SKILL.md`.)
- **The model produces *data*; scripts produce *presentation*.** A pass emits a small
  JSON "cycle record" of what it did; `render_dashboard.py` turns that into the
  dashboard. So the output is consistent run-to-run and the rendering is unit-testable
  — the LLM never free-writes the report.
- **Claims-first, secret-safe retrieval.** Transcripts are huge (tens of MB) but the
  signal is tiny, so we never bulk-read them — we stream, scope to the last run, and
  pull out discrete claims. Credential-shaped text is dropped *at retrieval*, before
  it could ever reach a memory file.
- **Memory loads in tiers, so facts are placed by *how often they're needed*.**
  Always-loaded (every session — kept scarce), recall (surfaced when its description
  matches — so the description is written as a search key), on-demand (read when
  relevant). Context budget is a first-class concern.
- **`scope` ≠ `tier`.** *Scope* is how widely a fact applies (this project / this
  stack / everywhere); *tier* is how it loads. Cross-project sharing + the pull-based
  propagation above fall out of one harness fact: recall is per-project, so global
  facts must be *replicated* into each project, not just stored once.
- **Boring-on-purpose engineering.** Zero runtime dependencies (Python stdlib only),
  the repo *is* the live skill (via symlink — edit and it's live, no build), and the
  mutating ops are idempotent + reversible (the installer backs up, sync refreshes
  rather than duplicates, a marker scopes each run to "since last time").

If a design decision here surprised you, it probably has a one-line "why" in
`skill/SKILL.md` or `skill/references/harness-map.md` — those explain the reasoning,
not just the rules.

## Lineage

Adapted from the mimo harness's `/dream` command — but rebuilt natively for Claude
Code rather than ported. The defining difference is the tier-aware, cross-project
model above, which mimo's single flat store has no concept of.

## License

MIT — see [LICENSE](LICENSE).
