# consolidate-memory

**Cross-project, verification-first memory for Claude Code — the layer beyond Auto Dream.**

Claude Code is rolling out a built-in **Auto Dream** that consolidates each project's memory in place. `consolidate-memory`
goes further, on the two axes Auto Dream doesn't cover: it **shares memory across enrolled
projects in the same trust domain** (a governed store, replicated into those projects) — and **verifies
facts against the live code** (grep / file & symbol existence / `git log`), dropping any it can't
confirm. Fact-checked, fleet-wide memory — not a per-project transcript-merge.

It **complements** Auto Dream rather than replacing it — a deliberately *explicit*, rigorous pass: Auto Dream keeps each
project tidy automatically; you invoke **`dream`** (or "consolidate my memory") when you want
*verified* + *cross-project* consolidation.

> **Current release: v0.4.7.** Public **1.0 remains HOLD** (evidence-gated — see
> [`docs/1.0-preflight.spec.md`](docs/1.0-preflight.spec.md)). Per-version detail lives in
> [**CHANGELOG.md**](CHANGELOG.md).

## Contents

- [Install](#install)
- [Cross-project sharing, out of the box](#cross-project-sharing-out-of-the-box)
- [Usage](#usage)
- [How it works](#how-it-works)
- [Upgrading from v0.1.x → v0.3.0](#upgrading-from-v01x--v030)
- [Security & privacy](#security--privacy)
- [Architecture](#architecture)
- [Design notes](#design-notes)

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

**Working on the tool itself?** Clone the repo, register it as a local marketplace, and install
the plugin — `claude plugin marketplace add ./` then `claude plugin install
consolidate-memory@zenetusken-plugins` — so you dogfood the exact artifact users get.

**The QA companion.** This repo also ships an optional second plugin, **`dream-beta-tester`** —
a deterministic regression oracle plus an agent-driven judgment-lens pass that beta-tests
consolidate-memory *itself* (`/dream-beta-test`). For maintainers/contributors validating a
change, not day-to-day `dream` use; install it the same way (`/plugin install dream-beta-tester@zenetusken-plugins`) if you want to help QA new versions.

### Uninstall / purge your data

`/plugin uninstall consolidate-memory` removes the code. Your consolidated memory is
**separate and untouched by uninstall** — that split is the whole privacy posture.

Do **not** `rm -rf ~/.claude/projects/<slug>/memory/` to "uninstall this plugin": that
directory is also Claude Code's native Auto Memory, and blanket deletion removes
memory this plugin does not own. Domain canonicals live under
`<config>/consolidate-memory/domains/<domain>/facts/`; the control plane lives under
`~/.claude/plugins/data/consolidate-memory/`. Legacy `~/.claude/memory/` is a
read-only migration source. Scoped purge commands are the right tool; hand-deleting
the native store is **not recoverable** and can destroy unrelated Auto Memory.

### Known limitations

- **Unenrolled projects are local-only.** They cannot create or pull cross-project
  canonicals. Enroll with `/cm-domain` (marketplace) or `cm project enroll --domain
  personal --apply --confirm enroll-personal` (this checkout). `cm doctor` prints
  `UNENROLLED LOCAL-ONLY` when this applies.
- Use `move-domain` / `unenroll` to revoke managed mirrors that the destination does
  not admit. Do not run `cm migrate --apply` / `--rollback` or domain switches on
  irreplaceable stores without a reviewed assignment plan.
- `forget` is **lazy acknowledgment**: other projects drop the mirror on their next
  `--pull` / `--gc --apply`. Offline clones keep bytes until they run.
- 1.0 is **POSIX-only** (ADR 016): native Windows mutation is out of scope — run
  under WSL. Missing `fcntl` is fail-closed `WriteRefused`, never an unlocked fallback.

## Cross-project sharing, out of the box

Everything works locally with zero setup; sharing takes **one deliberate step per
project** — enrollment (a domain is a trust boundary, so a project can never grant
itself one — the operator grants it). The consolidated workflow:

1. **Install** (above) — two commands.
2. **Hook your repos together:** in one of them run **`/cm-connect <other-repo>`** —
   it surveys both repos, shows each enrollment plan (the grants are
   operator-confirmed there — a repo never grants itself), offers to share a first
   fact, absorbs the shared layer in both directions, and prints the network it
   just linked.
3. **Share a fact:** **`/cm-share "…"`** in any enrolled project — one sentence,
   verified against the live repo(s), shown to you, written only on your
   confirmation.
4. **Stay in sync:** each project absorbs the shared layer on **its own next
   dream** — or right now with **`/cm-sync`** — and the session beacon names exactly
   which repos are behind, including unenrolled ones (*"2 shared fact(s) not
   reachable here"*). **`/cm-network`** shows the whole network's token cost and
   topology, read-only.

Enrolling a single project alone is just **`/cm-domain`**; `cm doctor` — or
`/cm-doctor` — in any project prints the resolved setup, and the
`UNENROLLED LOCAL-ONLY` line means that project keeps everything local until you
enroll it. The full model (scopes, domains, replication) is below under
[How it works](#how-it-works).

## Usage

In any project, just say **`dream`** — or "consolidate my memory" / "what should I
remember from this?". The skill runs a 6-phase pass (locate → orient + pull globals →
gather candidates → verify → consolidate → render), performed as a brief sleep → per-phase
narration → wake, in a distinct italic voice layered *on top of* the dense technical
reporting (never replacing it). You can also drive the pieces directly:

```bash
./cm status            # Phase-0 context: stores, git range, marker, token budget + a no-nag dream-timing nudge
./cm doctor            # resolved Claude store, source, profile, domain, auto-memory, ambiguity
./cm project enroll --domain NAME   # maintainer CLI: operator grant (marketplace users: ask the skill)
./cm extract           # curated session signal (human turns + error-gotchas, secrets omitted)
./cm distill           # recurring Bash-command workflows (templates + compound-command chains) — distill's raw signal
./cm pull .            # replicate relevant global facts into this project
./cm gc . --apply      # reclaim orphaned mirrors (canonical deleted) — report-only without --apply
./cm tokens .          # per-node + total token consumption across the network (≈ chars/4)
./cm network           # the cross-project shared-memory graph
./cm conflicts         # three-way mirror conflict queue (local edits are never silently overwritten)
./cm render cycle.json # render ONE cycle record → the ASCII dashboard
./cm report            # open the rich self-contained HTML archive (all dreams for this repo)
./cm log               # the lean per-dream audit table (all cycles)
```

(`./cm` is a **maintainer** wrapper in this checkout; marketplace users invoke the skill
and the packaged `/cm-*` commands.)

**A second vertical — distill.** Beyond consolidating *facts*, a dream also watches for repeated
*workflows*: recurring command templates and their compound-command chains, with a
day-spread so a genuine multi-day workflow outranks a one-hour retry loop — and the pass
proposes packaging a high-confidence one into a durable command/skill, **report-then-apply,
never auto-written**. Across the fleet, only **distinctive** command classes that recur on
more than one project over more than one day are proposed (ordinary `git add` is not a
workflow). "Create nothing" is a frequent, honorable verdict; every distill step ends with a
one-line disposition captured on the cycle record.

## How it works

### Three context-loading tiers

A fact only helps a future session if it reaches that session's context — and everything
that loads costs tokens. Claude Code loads memory in three tiers, and each fact belongs in
the one that fits how often it's needed:

| Tier | What loads | Consolidation rule |
|---|---|---|
| **Always-loaded** | `CLAUDE.md` + the auto-memory `MEMORY.md` index, injected every session | scarce & expensive — the index is kept lean; `CLAUDE.md` is user-owned, touched conservatively (a guest, not a fact dump) |
| **Recall** | a fact's `description:` rides in the always-loaded index; the body is read on-demand when that hook cues it | the `description:` is a **recall key** — write it as the cue that makes a future session open the fact |
| **On-demand** | repo docs + fact bodies, read when relevant | optimize for completeness, not per-session leanness |

The product of a pass isn't tidy files — it's *correct, well-budgeted context loading*.
Every candidate fact is **verified against the live code** before it can land; an
unverifiable claim is dropped, not kept. A no-op pass and a heavy pass render visibly
differently — the dashboard comes from a structured record of what the pass actually
did, and a **rigor tier** scales the verification ceremony to the pass's magnitude.

### Cross-project shared consciousness

**This is the tier Auto Dream doesn't have.** Claude Code recall is **slug-scoped** — a
project only auto-recalls its own `~/.claude/projects/<slug>/memory/` — so a fact learned
in one project has to be **replicated** into the others to surface there. The model:

- Facts get a **`scope`** — `project-local` / `stack-general` / `user-global` — by a hard
  cascade, not vibes: does the fact depend on the user's **fleet-constant** substrate
  (OS/account, `gh`, the Claude Code harness — present everywhere) or a **fleet-varying**
  stack (a per-project tool like `mypy`)? Each pass re-audits existing `user-global`
  facts by content and *offers* demotion for over-promoted ones (never auto-applied).
- Cross-scope facts live canonically in a **domain-scoped store**
  (`<config>/consolidate-memory/domains/<domain>/facts`); enrollment is an **operator
  grant** — a repository cannot grant itself a domain, and `user-global` is
  *domain*-global, not installation-global.
- They're **replicated** into each enrolled project's store on that project's next pull.

`./cm network` shows the topology — the **universal baseline** (facts every project holds)
listed separately from the **differential edges** that carry real signal
(`stack-general` facts binding only the matching-stack projects). Early on, with only
universal facts, it honestly reads `N shared · N universal · 0 differential`. As stack-general facts
accumulate, a graph emerges — the same split the HTML archive's Shared Consciousness view draws.

### How insights propagate (the honest model)

It's a **shared bloodstream, not telepathy** — and you never hand-edit another project.
When project **A** dreams and learns something cross-cutting:

1. **Deposit — instant.** The fact is written to the enrolled domain's canonical dir and
   into A's own store.
2. **Absorb — lazy.** Other projects pick it up on **their** next dream (every dream's
   first step is a `pull`). Until B next dreams, B doesn't have A's new insight.

So it's **eventually-consistent**, not a real-time broadcast — because recall is
slug-scoped, a fact has to physically live in B's folder to surface in B's sessions, and
replication on B's pull beats writing into projects you're not working in. The upshot:
**no manual per-project busywork; each project syncs itself the next time you
consolidate it.** Instant whole-network propagation would be a deliberate opt-in, not the
default — the lazy pull keeps a project's memory changing only while *you're* in it.

### The session beacon

Lazy absorption has one honest cost: a project you rarely consolidate can drift far behind
the fleet without anything telling you. The plugin ships a tiny **SessionStart hook** that
measures exactly that — when you open a session in a project whose memory store is behind,
it adds **at most one factual line** to the session's context, e.g.:

> *Cross-project memory: 3 shared global fact(s) are not yet mirrored here (1 would be
> ceiling-held); last consolidation 12.4d ago. A consolidation pass (dream) on this
> project absorbs them; asking to snooze this reminder quiets it for this store.*

It is read-only and advisory — it never pulls or writes anything; absorption still happens
only when *you* run a dream. It stays **silent** in the common cases: projects that have
never used the memory system, stores that are in sync, and stores you've snoozed (ask
Claude to "snooze the memory beacon for this project"). It runs in ~40ms, needs `python3`
on PATH, and if anything goes wrong it says nothing rather than guessing.

## Upgrading from v0.1.x → v0.3.0

**v0.3.0 moved the trust boundary.** Pre-0.3.0, any project could read or write the shared
global store (`~/.claude/memory/`). v0.3.0 replaces that with **domain-scoped canonicals +
enrollment** (ADR 008) — the big change in one sentence: **unenrolled is local-only.**

| Was (≤ v0.1.91) | Is (≥ v0.3.0) |
|---|---|
| One global store at `~/.claude/memory/`, open to every project | Domain-scoped canonicals at `<config>/consolidate-memory/domains/<domain>/facts` |
| Any dream could write or pull anything | Enrollment (`cm project enroll --domain NAME`) is an **operator grant**, per project |
| Mirrors replicated everywhere by default | First-enroll **revokes managed mirrors the destination does not admit** |
| Files + a hand-written index were the record | A **SQLite control plane** journals every op; `cm canonical upsert` is the **sole** canonical writer |
| `~/.claude/memory/` was live | It is now a **read-only migration source** |

**Migrate an existing fleet in this order (order matters):**

1. **Update the plugin** (`/plugin update consolidate-memory`). Everything old keeps
   working; unenrolled projects simply stop sharing until enrolled.
2. **Populate the domain FIRST.** `cm migrate --plan` inventories the legacy facts and
   stages an assignment plan — review it, then `cm migrate --apply --confirm migrate-apply`, then `--finalize`
  (rollback: `cm migrate --rollback --confirm migrate-rollback`).
3. **Then enroll each project** that should share: `cm project enroll --domain personal
   --apply --confirm enroll-personal` (marketplace users: `/cm-domain`).
4. **Enroll after migrating, not before.** A first-enroll revokes unadmitted mirrors —
   enrolling into a still-empty domain strips every mirror with nothing to replace them.
5. Projects you leave unenrolled stay fully functional **locally** — they just don't
   share, and they drop out of the cross-project fleet view.

`cm doctor` in any project prints the resolved StoreContext (domain, enrollment, paths,
registry health) — the one command that answers "what is my memory setup?"

## Security & privacy

Your consolidated memory is personal and **never leaves your machine** — the scripts are
**stdlib-only** (uses 3.8+ stdlib; CI validates the full 3.8–3.13 range), make **no
network calls**, and the pipeline’s only external process is read-only `git` — the
HTML archive’s render opens your local browser, the one other process it ever spawns. The `memory/` store is
gitignored and is **not** part of the published plugin (only `plugins/consolidate-memory/`
ships). The secrets firewall applies at *retrieval*: a credential-shaped turn in a
transcript is dropped before it could ever reach a fact file. Control-plane locks use
`fcntl.flock` (POSIX); missing `fcntl` is **WriteRefused** — fail-closed (ADR 016). Each
release is gated by an internal multi-agent white-hat security review; see
**[SECURITY.md](SECURITY.md)** for the full threat model and how to report an issue.

## Architecture

```
consolidate-memory/                         # repo root = plugin marketplace
├── .claude-plugin/marketplace.json         # the marketplace catalog
├── plugins/consolidate-memory/             # the plugin (= ${CLAUDE_PLUGIN_ROOT})
│   ├── .claude-plugin/plugin.json          # plugin manifest (name, version, …)
│   ├── skills/consolidate-memory/
│   │   ├── SKILL.md                         # the 6-phase workflow + loading-tier model
│   │   └── references/harness-map.md        # paths, schema, verification recipes
│   └── scripts/                            # stdlib-only runtime — store_context (sole path
│                                           # constructor), memory_status (Phase 0), extract_signals
│                                           # (secret-safe signal), sync_global (cross-project),
│                                           # canonical_ingress (sole canonical writer), distill_scan,
│                                           # render_dashboard / render_html / render_log (+ template), cm_ops
├── plugins/dream-beta-tester/              # the QA companion plugin
├── tests/                                   # zero-dependency smoke + accumulation + manifest checks
├── memory/                                  # gitignored placeholder (.gitkeep) — live canonicals are domain dirs
├── cm                                       # dev CLI over the scripts
├── docs/                                    # ADRs, the 1.0 preflight, design specs
└── SECURITY.md · CHANGELOG.md · LICENSE
```

## Design notes

A few load-bearing choices, in case you're poking at the code or wondering "why is it
built this way":

- **The model produces *data*; scripts produce *presentation*.** A pass emits a small
  JSON "cycle record" of what it did; `render_dashboard.py` turns that into the
  dashboard. Output is consistent run-to-run and the rendering is unit-testable — the
  LLM never free-writes the report.
- **Claims-first, secret-safe retrieval.** Transcripts are huge (tens of MB) but the
  signal is tiny, so they're never bulk-read — the extractor streams, scopes to the last
  consolidation marker, and drops credential-shaped text *at retrieval*.
- **`scope` ≠ `tier`.** *Scope* is how widely a fact applies (this project / this stack /
  everywhere); *tier* is how it loads. Cross-project sharing falls out of one harness
  fact: recall is per-project, so global facts must be *replicated*, not just stored once.
- **Boring-on-purpose engineering.** Zero runtime dependencies, ships as a
  self-contained plugin (scripts referenced via `${CLAUDE_PLUGIN_ROOT}`, no build step),
  and the mutating ops are idempotent + reversible (sync refreshes rather than
  duplicates, GC is report-then-apply, a marker scopes each run to "since last time").

If a design decision here surprised you, it probably has a one-line "why" in
[`SKILL.md`](plugins/consolidate-memory/skills/consolidate-memory/SKILL.md) or its
[`harness-map.md`](plugins/consolidate-memory/skills/consolidate-memory/references/harness-map.md).

## License

MIT — see [LICENSE](LICENSE).
