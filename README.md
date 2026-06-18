# consolidate-memory

**Sleep-time memory consolidation for Claude Code agents — with a cross-project shared
consciousness.**

A deliberate, verifiable pass that turns the fluid experience of a work session into
*durable, fact-checked memory* — and keeps that memory accurate, lean, and shared
across every project you work in. It's the agent analogue of what sleep does for a
brain: replay recent experience, keep what's true and useful, discard the rest.

You invoke it by saying **`dream`** (or "consolidate my memory") in any project.

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ✦ DREAM · consolidate-memory                    LIGHT PASS
  my-project · session a1b2c3d
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  SCOPE     git a1b2c3d..HEAD · 0 commits · 2 candidates · 8 reviewed
  VERIFIED  ✓ 1 confirmed · ~ 0 corrected · ⚠ 0 unverifiable   [inline]
  RIGOR     LIGHT · final · magnitude 2 (0 commits + 2 candidates)

  CHANGES
    + added      claude-code-memory-is-slug-scoped
        recall/auto-mem · <global> · recall is slug-scoped; non-obvious · [session]
    · skipped    session-workflow-requests
        <proj> · control flow, not durable

  ALWAYS-LOADED   · paid every session
    project CLAUDE.md ≈1120/4000   [███░░░░░░░] 28%
    global CLAUDE.md  ≈2240        read-only · every project
    auto-mem index    ≈275/1200    [██░░░░░░░░] 23%  +1 ln
    recall facts      6            +1

  CROSS-PROJECT   · global tier · ~/.claude/memory: 4 fact(s)
    ↑ promoted  <global> claude-code-memory-is-slug-scoped

  NEURAL NETWORK   · token cost (≈ est., not a tokenizer)
    network total   ≈3200 always-loaded · ≈48000 recall-pool
    of which ≈280 (9%) mirror-driven (lever: global store demote/GC, not local prune)
    this cycle on my-project: + 1 added
      always-loaded ≈260 → ≈275 tok · 0 refreshed

  HEALTH    ✓ all pointers resolve
  MARKER    → a1b2c3def456 @ 2026-06-16T00:00Z
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
  dashboard is rendered from a structured record of what the pass actually did — including
  a **rigor tier** that scales verification ceremony to the pass's magnitude (a 1-fact pass
  stays light; a 20-fact pass fans out and adds a completeness critic).

## The model: three context-loading tiers

A fact only helps a future session if it actually reaches that session's context —
and everything that loads costs tokens. Claude Code loads memory in three tiers:

| Tier | What loads | Consolidation rule |
|---|---|---|
| **Always-loaded** | `CLAUDE.md` + the auto-memory `MEMORY.md` index, injected every session | scarce & expensive — the auto-memory index is kept lean; `CLAUDE.md` is user-owned, touched conservatively (a guest, not a fact dump) |
| **Recall** | a fact's `description:` rides in the always-loaded index; the body is read on-demand when that hook cues it | the `description:` is a **recall key** — write it as the cue that makes a future session open the fact |
| **On-demand** | repo docs + fact bodies, read when relevant | optimize for completeness, not per-session leanness |

The product of a pass isn't tidy files — it's *correct, well-budgeted context loading*.

## Cross-project shared consciousness

Claude Code recall is **slug-scoped**: a project only auto-recalls its own
`~/.claude/projects/<slug>/memory/`. So a global store alone wouldn't surface
anywhere. The fix:

- Facts get a **`scope`** — `project-local` / `stack-general` / `user-global` — by a hard
  **cascade**, not vibes: is the fact's dependency **fleet-constant** (your OS/account, an
  always-present CLI like `gh`, the Claude Code harness — present in *every* project → can be
  `user-global`) or **fleet-varying** (a per-project stack like `mypy`/release-cutting → at most
  `stack-general`)? Each pass also re-audits existing `user-global` facts by content and **offers**
  demotion for any that drifted over-promoted (never auto-applied).
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

This ships as a **Claude Code plugin** — no clone, no symlinks. In Claude Code:

```text
/plugin marketplace add Zenetusken/consolidate-memory
/plugin install consolidate-memory@zenetusken-plugins
```

(or the CLI form: `claude plugin marketplace add Zenetusken/consolidate-memory` then
`claude plugin install consolidate-memory@zenetusken-plugins`). That's it — the skill
is available in **every** project. Update later with `/plugin update consolidate-memory`.

> Add the marketplace **via Git** (the `owner/repo` shorthand above), not a direct URL
> to `marketplace.json` — the plugin uses a relative source path that only resolves
> over Git.

**Working on the tool itself?** Clone the repo, then register it as a local marketplace
and install the plugin — `claude plugin marketplace add .` then `claude plugin install
consolidate-memory@zenetusken-plugins` — so you dogfood the exact artifact users get
(the old user-skill symlink model is retired: `SKILL.md` now uses `${CLAUDE_PLUGIN_ROOT}`,
which is only set when the skill loads as a plugin).

## Usage

In any project, just say **`dream`** — or "consolidate my memory" / "what should I
remember from this?". The skill runs a 6-phase pass (locate → orient + pull globals →
gather candidates → verify → consolidate → render). You can also drive the pieces
directly:

```bash
./cm status            # Phase-0 context: stores, git range, marker, token budget + a no-nag dream-timing nudge
./cm extract           # curated session signal (human turns + error-gotchas, secrets omitted)
./cm pull .            # replicate relevant global facts into this project
./cm gc . --apply      # reclaim orphaned mirrors (canonical deleted) — report-only without --apply
./cm tokens .          # per-node + total token consumption across the network (≈ chars/4)
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
consolidate-memory/                         # repo root = plugin marketplace
├── .claude-plugin/marketplace.json         # the marketplace catalog
├── plugins/consolidate-memory/             # the plugin (= ${CLAUDE_PLUGIN_ROOT})
│   ├── .claude-plugin/plugin.json          # plugin manifest (name, version, …)
│   ├── skills/consolidate-memory/
│   │   ├── SKILL.md                         # the 6-phase workflow + loading-tier model
│   │   └── references/harness-map.md        # paths, schema, verification recipes
│   └── scripts/
│       ├── memory_status.py                 # Phase 0: locate stores + git scope + seed
│       ├── extract_signals.py               # Phase 2: curated, secret-safe session signal
│       ├── sync_global.py                   # cross-project: replicate + GC + tokens + --network
│       └── render_dashboard.py              # the data-driven dashboard
├── tests/                                   # zero-dependency smoke + accumulation + manifest checks
├── memory/                                  # gitignored placeholder (.gitkeep) — store is ~/.claude/memory
├── cm                                       # dev CLI over the scripts
├── SECURITY.md · CHANGELOG.md
└── README.md · CLAUDE.md · LICENSE
```

## Privacy & security

Your consolidated memory is personal and **never leaves your machine** — the scripts
are **stdlib-only** (uses 3.8+ stdlib; validated on Python 3.10–3.13), make **no network
calls**, and the only external process is read-only `git`. The `memory/` store is gitignored and is **not** part of the
published plugin (only `plugins/consolidate-memory/` ships). The secrets firewall
applies at *retrieval*, so a credential in a transcript is dropped before it could ever
reach a fact file. Each release is gated by an internal multi-agent white-hat security
review; see **[SECURITY.md](SECURITY.md)** for the full threat model, the security
properties enforced in code, and how to report an issue.

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
  Always-loaded (every session — kept scarce; includes each fact's `description:` as
  its index hook), on-demand (the body is read when the hook cues it — so the
  description is written as that cue). Context budget is a first-class concern.
- **`scope` ≠ `tier`.** *Scope* is how widely a fact applies (this project / this
  stack / everywhere); *tier* is how it loads. Cross-project sharing + the pull-based
  propagation above fall out of one harness fact: recall is per-project, so global
  facts must be *replicated* into each project, not just stored once.
- **Boring-on-purpose engineering.** Zero runtime dependencies (stdlib-only — uses 3.8+
  stdlib, validated on Python 3.10–3.13),
  ships as a self-contained plugin (scripts referenced via `${CLAUDE_PLUGIN_ROOT}`, no
  build step), and the mutating ops are idempotent + reversible (sync refreshes rather
  than duplicates, GC is report-then-apply, a marker scopes each run to "since last
  time").

If a design decision here surprised you, it probably has a one-line "why" in
`plugins/consolidate-memory/skills/consolidate-memory/SKILL.md` or its
`references/harness-map.md` — those explain the reasoning, not just the rules.

## The idea

Agents accumulate experience in a session but wake up forgetting it. This is the
sleep-time analogue: replay the session, keep what's **verified and useful**, discard
the rest — and place each fact in the context-loading tier that fits how often it's
needed, replicated across projects only where it applies. The tier-aware, cross-project
model above is the core of it.

## License

MIT — see [LICENSE](LICENSE).
