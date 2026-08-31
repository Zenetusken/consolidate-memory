# consolidate-memory Cross-Project Production-Readiness Audit

**Audit date:** 2026-08-31  
**Repository:** `Zenetusken/consolidate-memory`  
**Audited branch / commit:** `main` at `80bcb055c5c25a8e301a73021421940be974d0c8`  
**Audited plugin version:** `0.1.91`  
**Primary concern:** correctness, isolation, relevance, retention, and lifecycle management across a fleet of Claude Code projects.

---

## 1. Executive verdict

`consolidate-memory` is a strong and unusually disciplined pre-1.0 implementation. Its core product idea is sound:

1. keep project-local facts in Claude Code's native per-project auto-memory;
2. maintain cross-project canonical facts in a separate global store;
3. replicate only applicable facts into project stores so Claude Code can actually recall them;
4. verify candidate facts before retention;
5. control the always-loaded `MEMORY.md` cost;
6. use report-before-apply governance for potentially destructive or wide-blast-radius operations.

The repository is materially beyond a prototype. It contains extensive specifications, typed cycle records, deterministic status and accounting utilities, lifecycle simulations, schema checks, strict plugin validation, conservative garbage collection, a secrets firewall for transcript-derived signals, and explicit documentation of residual risks.

However, the **cross-project subsystem is not production-ready yet**. The recommended release decision is:

> **NO-GO for a public 1.0 release until the P0 blockers in this report are fixed and revalidated on clean machines, multiple users, multiple profiles, and real worktree setups.**

The most important blockers are not cosmetic:

| Priority | Blocker | Consequence |
|---|---|---|
| P0 | The plugin does not use a single authoritative Claude Code store resolver | It can read and write a different memory directory than Claude Code actually uses |
| P0 | Applicability scope is conflated with trust and confidentiality scope | Personal, employer, and client projects can receive facts from one another |
| P0 | Managed mirrors have no local-edit conflict protocol | A legitimate edit to a mirror can be overwritten on the next pull |
| P0 | Cross-store operations are not transactional and the global store is not locked | Concurrent or interrupted operations can lose provenance or leave partial state |
| P0 | Project identity is basename/slug-derived and lossy | Same-named repositories, renames, profiles, and worktrees can be conflated or orphaned |

The correct response is **not** to discard the architecture. The correct response is to preserve the plain-Markdown fact layer while adding:

- a native-compatible store resolver;
- profile/domain isolation;
- stable project and fact identities;
- a conflict-aware mirror protocol;
- a small transactional control plane;
- one validated global-ingress API;
- bounded retention for operational records.

With those changes, the current system can become a robust production product without adding embeddings, a remote service, or a heavy orchestration framework.

---

## 2. Audit scope and confidence

### 2.1 What was reviewed

The audit traced the following repository surfaces:

- plugin manifests and hooks;
- the six-phase `dream` procedure;
- project memory discovery and status calculation;
- signal extraction from transcripts and Git;
- global fact selection and replication;
- promotion, reconciliation, demotion, and garbage collection;
- provenance and network modeling;
- staleness and beacon behavior;
- recall-use telemetry and fleet harvesting;
- workflow distillation and fleet registrar logic;
- index and token accounting;
- cycle-record persistence and rendering;
- security and pre-1.0 documentation;
- CI and test gates.

The comparison target was the **current public Claude Code contract**, including:

- native auto-memory storage and frontmatter;
- repository/worktree identity;
- startup loading limits;
- custom auto-memory directories;
- configuration profiles;
- auto-memory enable/disable controls;
- hook lifecycle and hook input;
- plugin persistent-data semantics.

### 2.2 Important limitation

This is a static source and business-logic audit against the public repository and current public Claude Code documentation. It is **not** an audit of Anthropic's proprietary implementation source, which is not available here.

The repository was not run against the user's live `~/.claude` data, and no destructive concurrency or crash-injection test was executed in this environment. Where a conclusion is directly visible in source—for example a hard-coded path, an unguarded overwrite, or an explicitly documented non-atomic operation—it is treated as confirmed. Performance numbers measured by the repository itself are treated as project evidence, not independently reproduced benchmarks.

---

## 3. The native Claude Code memory contract the plugin must govern

A production plugin must treat this as an external protocol, not as an implementation detail.

### 3.1 Native fact classes

Claude Code currently uses four auto-memory fact types:

- `user`: role, expertise, and durable working preferences;
- `feedback`: corrections and approaches the user confirms;
- `project`: ongoing work, deadlines, and decisions not derivable from code or Git;
- `reference`: external information locations.

Claude Code intentionally avoids saving code-derived information and material already represented in `CLAUDE.md`.

This is broadly compatible with `consolidate-memory`'s fact schema and verification-first posture.

### 3.2 Native project identity and storage

Claude Code's project memory directory is repository-derived:

- worktrees and subdirectories of the same Git repository share one auto-memory directory;
- outside Git, the project root is used;
- `CLAUDE_CONFIG_DIR` and `CLAUDE_CODE_PROJECT_DIR_NAME` can change the config and project-directory mapping;
- `autoMemoryDirectory` can override the memory path from user, project, local, policy, or `--settings` scope.

This is the most important compatibility boundary in the audit.

### 3.3 Native loading behavior

At session start, Claude Code loads the first:

- **200 lines**, or
- **25 KB**

of `MEMORY.md`, whichever limit is reached first.

Topic files are not loaded at startup; Claude reads them on demand. The main conversation's auto-memory is not automatically loaded into ordinary subagents. A subagent can have separate memory.

This means a one-line pointer is not free. Every mirrored fact consumes deterministic startup context on every holder project.

### 3.4 Native mutability and metadata

Memory files are plain Markdown and can be edited or deleted by the user or Claude. When Claude writes a frontmatter-bearing memory file, Claude Code adds a `modified` ISO timestamp.

A replication layer therefore cannot safely assume that every `global_ref` file remains a byte-identical cache. Managed files are still native, writable memory files.

### 3.5 Native lifecycle controls

Auto-memory can be disabled through:

- `autoMemoryEnabled: false`; or
- `CLAUDE_CODE_DISABLE_AUTO_MEMORY=1`.

A production plugin should not inject reminders, create mirrors, or treat absence as drift when native auto-memory is disabled.

### 3.6 Native plugin state

Claude Code supplies `${CLAUDE_PLUGIN_DATA}` as a persistent per-plugin directory intended for state that should survive plugin updates. It has explicit uninstall behavior and a `--keep-data` option.

Operational state such as:

- registry metadata;
- lock files;
- journals;
- usage aggregates;
- workflow evidence;
- migration state;
- cached project capabilities

belongs there, not beside user memory facts.

---

## 4. How consolidate-memory currently works

## 4.1 Single-project lifecycle

A normal `dream` pass is conceptually:

1. **Locate and measure**
   - derive the project auto-memory store;
   - read the last consolidation marker;
   - inspect Git activity;
   - measure `CLAUDE.md`, `MEMORY.md`, fact counts, and structural health.

2. **Orient and pull**
   - identify the project stack;
   - list applicable global facts;
   - pull missing facts and refresh stale mirrors;
   - harvest fleet usage.

3. **Gather candidate knowledge**
   - use Git changes;
   - extract user feedback/preferences and durable error gotchas from transcripts;
   - inspect existing memory for correction, deduplication, promotion, archive, or defragmentation candidates.

4. **Verify**
   - check claims against source files, symbols, configuration, and Git history;
   - drop or correct unsupported claims.

5. **Consolidate**
   - write project facts;
   - promote broadly applicable facts;
   - update indexes;
   - propose or apply approved maintenance.

6. **Measure and record**
   - remeasure the result;
   - update the marker;
   - append a cycle record;
   - collect recall-use and workflow evidence;
   - render the dashboard.

This is a coherent lifecycle. In particular, separating candidate formation from verification is a sound design choice.

## 4.2 Cross-project lifecycle

The cross-project layer adds:

- a canonical store at `~/.claude/memory/`;
- a custom `scope`:
  - `project-local`;
  - `stack-general`;
  - `user-global`;
- managed per-project mirrors marked with `global_ref`;
- a `projects:` list on canonicals as the holder/provenance graph;
- relevance matching:
  - `user-global` applies everywhere;
  - `stack-general` applies when fact stacks intersect detected project stacks;
- lazy pull-based propagation;
- a read-only SessionStart beacon;
- stale/frozen/orphan mirror reporting and GC;
- fleet usage and workflow aggregation;
- global utility and fleet-tax reports.

The current model is eventual consistency:

- promotion deposits a canonical and updates the origin;
- another project absorbs it on that project's next `dream`;
- the beacon advertises lag but does not write.

That default is appropriate. It avoids changing inactive project stores behind the user's back.

---

## 5. What is already strong

## 5.1 Verification-first retention

The plugin does not treat a transcript as truth. It gathers small candidate claims and verifies them against live code, files, symbols, configuration, or Git history before retention.

That materially reduces stale-memory accumulation.

## 5.2 Clear separation of index and body

The design understands the native retrieval mechanism:

- `MEMORY.md` is the always-loaded cue layer;
- topic bodies are on-demand;
- `description` is a recall cue, not merely a summary.

This is one of the best parts of the implementation.

## 5.3 Conservative write posture

The procedure uses report-before-apply for wide or destructive operations. Garbage collection is limited to plugin-managed mirrors. A project-authored same-name fact is classified as local and not overwritten.

## 5.4 Useful index governance

The plugin exposes:

- a curation target;
- native line/byte cliff observability;
- a hard admission ceiling;
- fat-pointer warnings;
- held pulls;
- evict-to-receive accounting;
- per-node and fleet-wide mirror tax.

This is substantially better than counting files alone.

## 5.5 Thoughtful mirror metadata

Managed copies separate canonical-only `projects:` provenance from per-project mirror content. Body lineage and mirror timestamps are used to avoid resetting evidence clocks on metadata-only changes.

## 5.6 Good corruption resistance

The code contains protections for:

- unsafe filenames;
- reserved `MEMORY` names;
- control-character and Markdown injection in pointer descriptions;
- case-insensitive filesystem collisions;
- malformed frontmatter;
- disappearing files during scans;
- dangling links;
- mass-deletion conditions;
- project-authored shadows;
- concurrent creation of the same new canonical.

## 5.7 Strong pre-1.0 discipline

The repository has:

- Python 3.8–3.13 CI;
- smoke tests;
- lifecycle simulations;
- static type checking;
- manifest validation;
- strict Claude plugin validation;
- typed cycle-record contracts;
- extensive design and remediation specifications.

The repository also honestly records its pre-1.0 HOLD and accepted residuals. This makes remediation easier because the project is not pretending those limitations do not exist.

---

## 6. Production-blocking findings

## CM-P0-01 — Native memory-store resolution is not authoritative

**Severity:** Critical  
**Status:** Confirmed in source  
**Affected surfaces:** status, extraction, sync, beacon, fleet scans, network, GC, usage, workflows

### Current behavior

The plugin constructs a project memory path from:

```text
Path.home() / ".claude" / "projects" / slug_for(project_dir) / "memory"
```

The SessionStart beacon reads `cwd` and constructs the same path. The global store is independently hard-coded under the same default home config tree.

### Why this fails in current Claude Code

Claude Code now resolves native memory from repository identity and supports:

- worktree/subdirectory sharing;
- `CLAUDE_CONFIG_DIR`;
- `CLAUDE_CODE_PROJECT_DIR_NAME`;
- `autoMemoryDirectory`;
- settings supplied through `--settings`.

Therefore the plugin and Claude Code can use different directories.

### Concrete failure modes

1. **Subdirectory launch:** plugin derives a store from the current subdirectory while Claude resolves the Git repository.
2. **Worktree launch:** plugin may derive a store from the worktree path while Claude shares the main repository's store.
3. **Alternate profile:** Claude uses an alternate config root while the plugin reads and writes default `~/.claude`.
4. **Custom auto-memory directory:** Claude uses the configured path while the plugin creates a shadow default store.
5. **Project-dir-name override:** multiple repositories intentionally share a configured Claude memory directory, but the plugin maintains separate custom slugs.
6. **Symlinked workspace:** physical and logical path normalization can diverge.
7. **Disabled auto-memory:** the plugin may interpret an absent or inactive native store as lag.

### Required fix

Create one shared `StoreContext` resolver and prohibit all direct construction of Claude paths elsewhere.

Suggested interface:

```python
@dataclass(frozen=True)
class StoreContext:
    config_root: Path
    native_memory_dir: Path
    plugin_data_dir: Path
    git_common_dir: Path | None
    project_id: str
    display_root: Path
    profile_id: str
    domain_id: str
    auto_memory_enabled: bool
    resolution_source: str
```

Resolution order should be explicit and tested:

1. honor `CLAUDE_CONFIG_DIR`;
2. honor `CLAUDE_CODE_PROJECT_DIR_NAME`;
3. detect `autoMemoryDirectory` from effective settings;
4. otherwise derive the Git repository identity using the Git common directory;
5. outside Git, use the actual project root;
6. use hook `transcript_path` as a high-confidence observation of the active native project directory;
7. bind and persist the result for the session in `${CLAUDE_PLUGIN_DATA}`;
8. fail closed for writes when two sources disagree.

For ephemeral `--settings` that cannot be reconstructed reliably from a standalone script, the SessionStart hook should bind the observed active store, or the command should require an explicit `--native-store`.

### Acceptance tests

- repository root;
- nested subdirectory;
- ordinary Git worktree;
- Claude-created isolated worktree;
- symlinked path;
- non-Git project;
- alternate `CLAUDE_CONFIG_DIR`;
- `CLAUDE_CODE_PROJECT_DIR_NAME`;
- user/project/local/policy/CLI `autoMemoryDirectory`;
- auto-memory disabled;
- two concurrent profiles.

No release should proceed until `cm doctor` proves that Claude and the plugin resolve the same store.

---

## CM-P0-02 — Applicability scope is not a trust boundary

**Severity:** Critical  
**Status:** Confirmed architectural gap  
**Affected surfaces:** global promotion, pull, beacon, fleet reports, workflow distillation

### Current behavior

A `user-global` canonical is considered relevant to every project in the fleet. A `stack-general` fact is relevant to every detected project matching a stack.

### Why this is unsafe

The same local Claude installation can contain:

- personal repositories;
- open-source work;
- employer repositories;
- multiple clients;
- regulated or confidential projects;
- intentionally isolated Claude profiles.

Applicability answers:

> “Would this fact be useful here?”

It does **not** answer:

> “Is this project allowed to receive this fact?”

A secrets regex is not sufficient. Confidential architecture, customer names, internal URLs, commercial strategy, incident details, and personal information may not look like credentials.

### Required model

Separate at least four independent dimensions:

| Dimension | Purpose | Example |
|---|---|---|
| `domain` / `audience` | Trust boundary | `personal`, `employer-a`, `client-b` |
| `applicability` | Technical or workflow fit | `claude-code`, `python`, `pdf`, `all-domain-projects` |
| `sensitivity` | Handling policy | `public`, `internal`, `confidential`, `secret` |
| `lifecycle` | Loading and retention | active cue, on-demand, archived, tombstoned |

`user-global` should become **domain-global**, never installation-global by default.

### Required policy

- A project belongs to exactly one default domain.
- Cross-domain replication is denied unless an explicit policy allows it.
- Unknown-domain projects receive no cross-project facts.
- `secret` content is never persisted as a fact; store only a safe pointer.
- `confidential` content cannot cross its domain.
- Promotion must run the policy gate regardless of source.
- Existing global facts must be migrated through a review report, not silently assigned to a universal domain.

### Required user controls

```text
cm domain list
cm domain assign <project> <domain>
cm policy explain <fact> <project>
cm promote --domain personal ...
cm migrate --classify-domains --plan
```

---

## CM-P0-03 — Managed-mirror edits can be silently lost

**Severity:** Critical  
**Status:** Confirmed in pull logic  
**Affected surfaces:** stale refresh, native `/memory` editing, external editors, Claude writes

### Current behavior

A file carrying the plugin's mirror marker is managed as a replica. If its current contents differ from the desired canonical mirror, it is treated as stale and rewritten from the canonical.

### Why this is unsafe

Claude Code explicitly treats auto-memory as editable plain Markdown. A user or Claude can legitimately improve a mirrored fact in a project context.

The current metadata records a canonical body lineage, but the refresh path does not perform a three-way conflict decision.

### Required three-way protocol

For every mirror retain:

- `base_revision`: canonical revision from which this mirror was created;
- `canonical_revision`: latest observed canonical revision;
- a semantic hash of the current mirror content.

Then classify:

| Local mirror | Canonical | Action |
|---|---|---|
| unchanged | changed | refresh safely |
| changed | unchanged | stop; offer `fork-local` or `promote-back` |
| changed | changed identically | restamp |
| changed | changed differently | create conflict; never overwrite |
| corrupt marker/base | any | quarantine and require repair |

The semantic hash must exclude volatile metadata such as:

- native `modified`;
- `mirrored_at`;
- local usage stamps;
- canonical holder provenance.

### Required commands

```text
cm conflicts
cm resolve <fact> --keep-canonical
cm resolve <fact> --fork-local <new-name>
cm resolve <fact> --promote-local
cm repair-mirror <fact>
```

A lightweight `FileChanged` or `PostToolUse` hook may warn when a managed mirror is edited, but correctness must live in the pull algorithm, not in a warning.

---

## CM-P0-04 — Cross-store operations lack transaction and recovery semantics

**Severity:** Critical  
**Status:** Confirmed and explicitly documented by the repository  
**Affected surfaces:** promote, pull, provenance, GC, ledgers, indexes

### Current behavior

The repository has useful atomic single-file helpers, but a logical operation can modify:

- a global canonical;
- global provenance;
- the origin mirror;
- a project index;
- an old local fact during rename;
- state and cycle records.

Promotion is explicitly documented as not crash-atomic. Provenance is a read-modify-write list without mutual exclusion. Some project files and indexes are written directly. The usage ledger accepts rare torn appends.

### Why atomic files are not enough

Atomic replacement prevents a reader from seeing half a single file. It does not guarantee that a multi-file state transition is complete.

A crash or concurrent dream can leave:

- canonical exists, origin still local;
- canonical holder recorded, mirror absent;
- mirror exists, index pointer missing;
- old and new names both present;
- one provenance append overwriting another;
- GC racing with a pull;
- a ledger watermark advancing without durable evidence.

### Minimum viable production fix

Use a portable lock directory and an operation journal:

1. acquire a global/domain lock;
2. acquire project locks in stable project-ID order;
3. snapshot expected revisions;
4. write a journal entry with the intended transition;
5. prepare all temp files;
6. verify source revisions have not changed;
7. atomically publish each file;
8. mark the journal committed;
9. release locks;
10. recover or roll forward any incomplete journal on the next command.

Lock order must always be:

```text
domain/global -> project IDs in sorted order
```

This avoids deadlock.

### Preferred control-plane fix

Use Python's stdlib `sqlite3` in `${CLAUDE_PLUGIN_DATA}` for:

- project registry;
- domain membership;
- canonical/project edges;
- mirror base revisions;
- operation journal;
- tombstones;
- usage windows;
- workflow aggregates;
- migration state.

Keep user knowledge in Markdown. The database is an operational control plane, not the source of fact content, and must be rebuildable from Markdown plus local observations.

SQLite provides transactions and cross-platform locking without violating the runtime's zero-third-party-dependency goal.

---

## CM-P0-05 — Project identity is lossy and collision-prone

**Severity:** Critical for a heterogeneous fleet  
**Status:** Confirmed in source and repository audit records

### Current behavior

Provenance stores a sanitized project basename. Fleet resolution attempts to map that label back onto Claude's lossy project-directory slug using equality or suffix matching.

### Failure modes

- two repositories named `api`;
- repository rename;
- project move;
- profile split;
- worktree path variation;
- underscores, hyphens, dots, spaces, or other slug-normalized characters;
- a short basename that suffix-collides with another project;
- a deleted store that is mistaken for a renamed one;
- one repository cloned into multiple trust domains.

The project has already measured unresolved/ghost provenance in its own fleet, which confirms that the issue is operational, not theoretical.

### Required identity

Use a stable internal identifier, separate from display text:

```text
project_id = sha256(
    schema_version
    + profile_id
    + domain_id
    + normalized_git_common_dir
    + optional_canonical_remote_identity
)
```

For non-Git projects, use a stable generated UUID bound to a normalized root.

Maintain a registry:

```text
project_id
display_name
current_root
git_common_dir
remote_fingerprint
profile_id
domain_id
native_memory_dir
last_seen
capabilities
status
```

A rename changes display/path metadata, not identity. Two same-basename repositories remain distinct.

The human-readable canonical frontmatter can retain labels, but the authoritative edge set should use project IDs.

---

## 7. High-priority correctness findings

## CM-P1-01 — There is more than one global-ingress path

The scripted `promote` path validates scope and detectable stacks, handles collisions, and protects against body loss. The phase instructions also permit net-new global writes outside that path and leave global index maintenance partly model-owned.

This creates policy bypass:

- a malformed scope can be written;
- an undetectable stack tag can create a dead canonical;
- secret/content policy can be bypassed;
- global and origin indexes can diverge;
- future domain rules would be inconsistently enforced.

### Recommendation

Create one sole writer:

```text
cm canonical upsert
```

It must perform:

1. schema validation;
2. content firewall;
3. domain/sensitivity policy;
4. applicability validation;
5. link-scope validation;
6. canonical dedup/conflict check;
7. exact index projection;
8. transactional canonical + mirror + index + edge update;
9. audit record.

The skill should never hand-write canonical files or canonical indexes.

Treat global `MEMORY.md` as a generated inventory or remove it from authoritative state.

---

## CM-P1-02 — Admission control does not enforce both native limits

The plugin observes native line and byte limits, but the hard pull decision is based on an estimated-token ceiling derived from the byte axis. The 200-line limit is not part of the admission decision.

A very terse index can hit 200 lines while remaining under the estimated-token ceiling.

### Recommendation

For every proposed index write, construct the exact resulting UTF-8 file and require:

```text
projected_lines <= configured_line_limit
projected_bytes <= configured_byte_limit
```

Maintain reserve headroom, for example 15–20%, so native and plugin metadata can evolve without landing at the cliff.

Use the character/token estimate for reporting only, not for safety.

Refreshes should also be projected. Correctness does not justify writing an index that causes other entries to disappear from startup context.

---

## CM-P1-03 — Stack detection is a closed, Python-heavy ontology

The current detector has a deliberately closed set centered on:

- Python;
- mypy;
- RAG;
- GPU;
- Playwright;
- PDF;
- Claude Code.

This is precise within that niche, but cross-project memory should generalize to:

- Node.js / TypeScript;
- Go;
- Rust;
- Java / Kotlin;
- .NET;
- Ruby / PHP;
- Docker and container orchestration;
- Terraform and cloud providers;
- databases;
- CI/CD;
- build and test systems;
- operating systems and package managers.

A broad `python` tag is also often too coarse to determine whether a fact truly applies.

### Recommendation

Replace `stacks` with extensible **capabilities**:

```yaml
applies:
  any: [python, linux]
  all: [pdf, gpu]
  exclude: [windows]
```

Each detected capability should carry:

- evidence source;
- confidence;
- detector version;
- last observed timestamp.

Allow user overrides. Never block a legitimate capability because the current binary did not ship a hard-coded detector.

---

## CM-P1-04 — Cross-project workflow capture is Bash-centric and misses tool trajectories

Current signal coverage is strongest for:

- user turns;
- error tool results;
- Git changes;
- organic memory reads and mentions;
- recurring Bash command templates and command chains;
- skill adoption and decline lineage.

It does not fully represent an agentic workflow such as:

```text
search -> read -> edit -> test -> inspect failure -> patch -> test -> commit
```

It also misses many non-Bash surfaces:

- Read/Edit/Write/Glob/Grep patterns;
- MCP tools;
- task and subagent outcomes;
- parallel tool batches;
- worktree creation/removal;
- directory additions;
- configuration changes;
- working-directory changes;
- explicit remember/forget requests;
- context compaction and session completion.

### Recommendation

Use current Claude Code hooks selectively:

- `UserPromptSubmit`: explicit preferences, remember/forget intent;
- `PostToolUse` and `PostToolUseFailure`: normalized outcomes;
- `PostToolBatch`: parallel workflow structure;
- `TaskCompleted` and `SubagentStop`: completion evidence;
- `CwdChanged`, `DirectoryAdded`, and worktree events: project-context changes;
- `ConfigChange` and carefully scoped `FileChanged`: environment/memory mutations;
- `Stop`, `SessionEnd`, and `PostCompact`: batch aggregation and flushing.

Do **not** store raw prompts or tool results. Emit compact event sketches:

```json
{
  "project_id": "...",
  "session_id": "...",
  "event": "tool_outcome",
  "tool_family": "test",
  "normalized_action": "pytest targeted",
  "outcome": "success",
  "day": "2026-08-31"
}
```

Aggregate per session and discard raw event details quickly.

---

## CM-P1-05 — Exact-string workflow joining is brittle

Fleet workflow evidence currently favors exact normalized command-template equality and uses family matching as a hint.

Semantically identical workflows can differ because of:

- flag ordering;
- path names;
- test target names;
- `python` versus `python3`;
- `npm` versus `pnpm`;
- shell quoting;
- harmless environment prefixes;
- pipelines, `||`, and conditional branches;
- equivalent non-shell tools.

### Recommendation

Normalize into an intermediate representation:

```text
tool family
verb/action
positional argument classes
option set
path classes
success/failure
predecessor/successor step
```

Represent a workflow as a small directed sequence graph, not one raw command string.

Promotion gates for a fleet workflow should normally include:

- recurrence on at least two independent projects;
- activity on at least two days;
- repeated successful completion;
- no unresolved negative-feedback or decline record;
- distinctive value beyond generic CLI use;
- explicit user confirmation before creating a global skill or command.

An explicit user request can legitimately bypass recurrence.

---

## CM-P1-06 — Native `modified` metadata is not integrated into semantic equality

Claude Code can add or update `modified` when it writes a memory file. Plugin writes and mirror comparisons need a defined policy for this field.

Without one, metadata-only changes can:

- create false staleness;
- obscure actual content change time;
- be overwritten;
- make audit timestamps ambiguous.

### Recommendation

Use distinct timestamps:

- `content_modified`;
- `verified_at`;
- `mirrored_at`;
- `last_observed_at`.

Preserve native `modified` where appropriate, but exclude it from semantic revision hashes. Preserve unknown frontmatter fields during migration and rewrites.

---

## CM-P1-07 — Global link constraints are advisory rather than enforced

A global fact can contain a `[[link]]` to a project-local fact that will not exist in other projects. Promotion warns, but still allows the invalid dependency.

### Recommendation

Enforce monotone dependencies:

- domain-global can link only to same-domain global or broader-safe references;
- capability-scoped can link to compatible capability or domain-global facts;
- project-local can link upward to global facts;
- a broader fact cannot require a narrower fact.

Invalid cross-scope links should block promotion unless converted to plain text or included in the same transaction.

---

## CM-P1-08 — Canonical deletion needs tombstones

Physical disappearance of a canonical is ambiguous:

- intentional forget;
- accidental deletion;
- partial restore;
- filesystem issue;
- concurrent operation.

Current orphan GC eventually removes mirrors, but absence alone is weak deletion intent.

### Recommendation

Create tombstones with:

```yaml
canonical_id: ...
deleted_at: ...
reason: ...
replacement_id: ...
grace_until: ...
```

Pull propagates the tombstone status. Mirror deletion occurs only after a grace period or explicit confirmation. Tombstones prevent a stale project from resurrecting intentionally deleted knowledge.

Add:

```text
cm forget <fact> --domain <domain> --plan
cm forget <fact> --apply
cm restore <fact>
```

---

## 8. Cross-project signal-coverage audit

| Signal or use case | Current coverage | Production assessment | Recommended change |
|---|---|---|---|
| Explicit user preference | Human-turn extraction | Good candidate source; scope/domain judgment is model-owned | Add explicit-intent classifier and domain gate |
| User correction / negative feedback | Human-turn extraction; decline lineage | Strong | Link correction to affected fact/workflow revision |
| Project decision / deadline | Human turn, Git context | Good, but must default project-local | Add expiry/review date |
| Code-derived architecture | Verification and repo-doc routing | Correctly discouraged from private memory | Keep in repository docs |
| Environment/tool gotcha | Error results | Useful, but one-off and version-specific errors can over-generalize | Add platform/tool-version predicates and recurrence |
| Successful command workflow | Bash recurrence | Partial | Capture outcome, not only invocation |
| Multi-tool agent workflow | Largely absent | Major gap | Normalize hook event sequences |
| Parallel tool strategy | Absent | Gap | Use `PostToolBatch` sketches |
| Subagent/task strategy | Absent | Gap | Use `SubagentStop`/`TaskCompleted` summaries |
| MCP workflow | Absent or only indirectly visible | Gap | Normalize MCP tool names and outcomes |
| Worktree/context changes | Not first-class | Important correctness gap | Use worktree, CWD, and directory events |
| Configuration drift | Not first-class | Important for applicability | Use `ConfigChange` and resolver rebind |
| Explicit remember request | Appears as human text | Partial | Recognize as high-priority candidate, not automatic global |
| Explicit forget request | No tombstone lifecycle | Major gap | Add deletion intent and tombstones |
| Organic fact-body use | Read telemetry | Strong but conservative | Keep; combine with mention and outcome evidence |
| Index cue use without body read | Mention telemetry | Useful corroboration | Keep separate from body-read evidence |
| Stale or unused fact | Usage windows and utility | Strong conservative basis | Add domain-aware retention |
| Cross-project contradiction | Model dedup plus canonical reconcile | Partial | Add fact IDs, revisions, and contradiction queue |
| Confidentiality/domain | Absent | Release blocker | Add mandatory domain and sensitivity policy |
| Cross-project workflow adoption | Skill invocation/inventory | Partial | Record artifact ID/version and successful completion |
| Workflow decline | Persisted lineage | Strong | Retain material-new-evidence rule |
| Project rename/deletion | Lossy provenance heuristics | Weak | Stable project registry |
| Profile separation | Not modeled | Release blocker | Include profile in domain/store identity |

---

## 9. Bloat and retention audit

## 9.1 What is controlled well

The plugin actively controls the most expensive memory surface:

- pointer-only index design;
- target budget;
- native cliff visibility;
- pull holds;
- evict-to-receive;
- frozen/orphan reclamation;
- per-fact and fleet-wide pointer tax;
- archive and defragmentation candidates;
- usage-informed demotion.

This is a strong foundation.

## 9.2 What remains unbounded

Operational history is append-only:

- per-project `.consolidation-log.jsonl`;
- global `.fleet-usage.jsonl`;
- audit snapshots and rendered history.

Reads can be logically tail-capped while still loading the entire file before slicing. Full-history render paths intentionally read all records.

Consequences over a long-lived fleet:

- disk growth;
- increasing parse latency;
- larger failure surface from one corrupt file;
- expensive HTML/report generation;
- state mixed with user memory;
- no coherent uninstall or privacy lifecycle.

## 9.3 Mirror amplification

For a canonical fact `f`:

```text
startup_tax(f) = pointer_cost(f) × holder_projects(f)
storage_tax(f) = mirror_body_bytes(f) × holder_projects(f)
maintenance_tax(f) = stale_checks + refreshes + provenance/usage accounting
```

A broadly promoted fact must save more future work than those recurring costs.

This means promotion should consider **utility density**, not only truth:

```text
expected future benefit
-----------------------  > threshold
fleet startup + storage + maintenance tax
```

A technically correct but rarely useful global fact is still bloat.

## 9.4 Recommended retention tiers

Move operational records into `${CLAUDE_PLUGIN_DATA}` and make limits configurable. A reasonable default policy is:

- detailed normalized event sketches: 30–90 days;
- per-session cycle records: latest 500 per project or a byte ceiling;
- daily usage/workflow aggregates: up to 12 months;
- permanent records: confirmed facts, tombstones, migration/audit summaries, explicit user decisions;
- raw transcript-derived text: never copied into plugin state;
- conflicts: retain until resolved;
- backups: retain a bounded number and expose their size.

These are product defaults, not universal truths. The important requirement is that retention is explicit, bounded, observable, and configurable.

## 9.5 Required storage commands

```text
cm data inventory
cm data compact --plan
cm data compact --apply
cm data export <path>
cm data purge --domain <domain> --plan
cm data purge --project <id> --plan
cm data retention show
```

The inventory should show:

- canonical Markdown bytes;
- project mirror bytes;
- index bytes/lines;
- plugin operational bytes;
- oldest/newest records;
- tombstones;
- unresolved conflicts;
- estimated startup tax.

---

## 10. Security and privacy audit

## 10.1 Existing strengths

- local-only design;
- no required network or telemetry;
- transcript streaming rather than bulk loading;
- credential-shaped and high-entropy filtering;
- command/error normalization;
- safe filename and pointer handling;
- conservative GC;
- private file mode for selected generated state.

## 10.2 Mandatory production improvements

### A. Apply the content firewall at every ingress

Transcript extraction is not the only input. A local fact can be promoted, a canonical can be hand-written, and migration can import legacy content.

The same policy must run for:

- transcript candidate;
- Git subject;
- local fact promotion;
- canonical edit;
- migration;
- repair/import;
- workflow artifact creation.

A secret-shaped value must be rejected or transformed into a non-secret pointer.

### B. Add non-secret confidentiality classification

Credentials are not the only sensitive data. Add policy categories and explicit domain enforcement.

### C. Harden filesystem writes

For every write:

- resolve and validate the path is under the expected root;
- use `lstat` and reject unsafe symlink targets;
- create directories as `0700`;
- create sensitive files as `0600`;
- use temp files in the same directory;
- flush and `fsync` before replace where durability matters;
- audit ownership and permissions in `cm doctor`.

### D. Honor disabled auto-memory

The plugin should remain silent and write nothing to native memory when auto-memory is disabled, unless the user explicitly invokes a diagnostic or migration command.

### E. Avoid global raw evidence

The control plane should contain only normalized summaries and identifiers. No raw prompt, tool output, transcript segment, environment dump, or credential-shaped value should enter global plugin state.

---

## 11. Recommended production architecture

Use three explicit planes.

## 11.1 Native project-memory plane

Purpose: integrate with Claude Code recall.

Contains only:

- native `MEMORY.md`;
- project-authored local facts;
- managed mirror facts.

Properties:

- resolved through `StoreContext`;
- exact native line/byte admission;
- managed mirrors are conflict-aware;
- no plugin logs, locks, registries, or fleet ledgers.

## 11.2 Canonical knowledge plane

Purpose: human-readable source of cross-project knowledge.

Suggested location:

```text
<config-root>/consolidate-memory/domains/<domain-id>/facts/
```

or another user-configurable path.

Contains:

- canonical Markdown facts;
- optional generated catalog;
- tombstone Markdown or export.

Properties:

- one trust domain per directory;
- plain text and user-inspectable;
- schema-versioned;
- no mutable holder lists required in fact content;
- no raw operational telemetry.

## 11.3 Plugin control plane

Location:

```text
${CLAUDE_PLUGIN_DATA}/
```

Contains:

- SQLite registry and transactional metadata;
- lock directories;
- operation journals;
- base revisions;
- domain policy;
- usage/workflow aggregates;
- migration state;
- bounded audit history;
- generated reports/caches.

Properties:

- operational, not knowledge content;
- rebuildable where practical;
- bounded retention;
- explicit export/purge;
- compatible with plugin uninstall semantics.

---

## 12. Recommended fact and mirror schema

## 12.1 Canonical fact

```yaml
---
cm_schema: 2
id: 9d1a...
name: prefer-pnpm-for-node-projects
type: feedback
scope: cross-project
domain: personal
sensitivity: internal
applies:
  any: [nodejs]
  all: []
  exclude: []
status: active
content_revision: sha256:...
content_modified: 2026-08-31T18:00:00Z
verified_at: 2026-08-31T18:00:00Z
source:
  project_id: p_...
  session_id: ...
  evidence_kind: user-feedback
review:
  expires_at: null
---
Use pnpm rather than npm for Node.js repositories in the personal domain.

**Why:** ...
**How to apply:** ...
```

## 12.2 Managed mirror

```yaml
---
cm_schema: 2
id: 9d1a...
name: prefer-pnpm-for-node-projects
type: feedback
modified: 2026-08-31T18:01:00Z
managed_by: consolidate-memory
domain: personal
canonical_revision: sha256:...
base_revision: sha256:...
mirrored_at: 2026-08-31T18:01:00Z
---
...
```

Do not place holder provenance in every canonical's mutable frontmatter. Keep authoritative edges in the transactional registry and generate a human-readable report when needed.

---

## 13. Recommended replication and promotion logic

## 13.1 Pull

1. resolve active project context;
2. verify auto-memory is enabled;
3. load project domain and capabilities;
4. enumerate only domain-allowed canonical facts;
5. evaluate applicability;
6. inspect local path:
   - absent;
   - project-authored shadow;
   - in-sync managed mirror;
   - canonical-only change;
   - local-only change;
   - true conflict;
   - corrupt/unrecognized;
7. construct exact future index;
8. enforce native byte and line headroom;
9. journal the transaction;
10. apply safe refreshes and additions;
11. record edges only for successfully committed mirrors;
12. render holds/conflicts separately.

A stale correctness refresh must not overwrite a local divergence and must not silently exceed native startup limits.

## 13.2 Promote

1. resolve project/domain;
2. verify source is project-authored, not already a mirror;
3. run secret/confidentiality policy;
4. classify native type;
5. determine applicability and domain independently;
6. verify claim;
7. detect semantic duplicate or contradiction;
8. validate links;
9. construct canonical revision;
10. project exact origin index;
11. acquire locks and journal;
12. write canonical, convert origin mirror, update index and registry atomically;
13. emit a reversible audit record.

## 13.3 Demote or forget

- applicability demotion changes who may receive a fact;
- loading demotion moves a cue/body to a less expensive tier;
- archive preserves history without startup tax;
- forget creates a tombstone and eventually removes mirrors;
- none of these should be represented as an unexplained file disappearance.

---

## 14. Code-organization recommendation

The current scripts are heavily commented and well tested, but key business logic is concentrated in very large modules. Production hardening will become safer if command wrappers are separated from policy.

Suggested layout:

```text
consolidate_memory/
  context.py       # native/store/profile/domain resolver
  identity.py      # project/fact IDs and registry
  schema.py        # frontmatter parsing and migrations
  policy.py        # domain, sensitivity, applicability
  revisions.py     # semantic hashes and conflict classification
  transaction.py   # locks, journal, recovery
  index.py         # exact byte/line planning
  replication.py   # pull/refresh/freeze
  promotion.py
  deletion.py      # tombstones and GC
  signals/
    transcript.py
    hooks.py
    workflows.py
  retention.py
  doctor.py
  reporting.py
scripts/
  cm               # thin CLI
  session_beacon.py
```

Runtime can remain stdlib-only. Development may use additional test-only dependencies.

---

## 15. Prioritized production roadmap

## Phase 0 — Freeze and specify

- keep the 1.0 release on HOLD;
- write ADRs for:
  - native store resolution;
  - profile/domain isolation;
  - stable identity;
  - transaction/control plane;
  - mirror conflict semantics;
  - schema v2 and migration;
- declare current v0.1.91 data read-compatible during migration.

**Exit:** every P0 behavior has an executable contract before implementation.

## Phase 1 — Resolve the right stores and trust domain

- implement `StoreContext`;
- eliminate hard-coded default Claude paths from business logic;
- add `cm doctor`;
- honor auto-memory disable state;
- add domain assignment and default-deny policy;
- add mandatory write-time content policy.

**Exit:** the plugin cannot write a shadow store or cross a domain unintentionally.

## Phase 2 — Stable identity and transactional control

- create project/fact IDs;
- add registry;
- move operational state to `${CLAUDE_PLUGIN_DATA}`;
- add locks, journal, revision checks, and recovery;
- migrate provenance from names to IDs;
- add crash and multi-process fault tests.

**Exit:** no silent lost update and every interrupted operation is recoverable/idempotent.

## Phase 3 — Conflict-safe mirrors and unified ingress

- add base/canonical revisions;
- implement three-way classification and conflict queue;
- make one canonical upsert/promote API;
- generate canonical catalog/index;
- add tombstones;
- enforce link-scope rules.

**Exit:** no local mirror edit can be silently overwritten; no policy bypass remains.

## Phase 4 — Exact budget and schema interoperability

- enforce exact byte and line limits with reserve;
- standardize native `modified` handling;
- preserve unknown metadata;
- add schema migration and rollback;
- add `cm migrate --plan/--apply`.

**Exit:** no committed operation can place a native index past the configured safety boundary.

## Phase 5 — Capability and workflow expansion

- replace closed stacks with extensible capabilities;
- add normalized hook sketches;
- support non-Bash and multi-tool workflows;
- measure success, retries, failure, adoption, and decline;
- keep raw content out of the control plane.

**Exit:** cross-project workflow promotion is based on independent, outcome-aware evidence.

## Phase 6 — Retention, operations, and external validation

- bounded compaction;
- export/purge;
- permission and symlink doctor;
- clean-machine install;
- second human and multiple trust domains;
- multiple OS/filesystem tests;
- 30-day fleet soak;
- upgrade, downgrade, uninstall, and rollback tests.

**Exit:** all release criteria below are green.

---

## 16. Required test matrix

## 16.1 Native compatibility

- default Linux profile;
- macOS case-insensitive filesystem;
- Windows-supported environment;
- Python 3.8–3.13;
- nested project directory;
- normal worktree;
- Claude-created worktree;
- non-Git root;
- symlinked repository;
- alternate config directory;
- explicit project directory name;
- custom auto-memory directory at every settings scope;
- auto-memory disabled;
- current and minimum supported Claude Code versions.

## 16.2 Identity and isolation

- two repositories with the same basename;
- moved repository;
- renamed repository;
- same repo in two profiles;
- personal and employer domains;
- unknown-domain project;
- domain-policy migration;
- deleted and later-restored project store.

## 16.3 Concurrency and crash injection

Run two or more processes for:

- pull versus pull;
- pull versus promote;
- promote versus promote to same name;
- promote versus GC;
- GC versus canonical update;
- forget versus pull;
- registry migration versus normal command.

Kill the process after every transaction stage. Re-run recovery and assert exactly one coherent end state.

## 16.4 Mirror conflict matrix

- no changes;
- canonical-only body change;
- local-only body change;
- both same change;
- divergent change;
- metadata-only native `modified` change;
- corrupt frontmatter;
- missing base revision;
- local file converted to project-authored shadow;
- case-only filename collision.

## 16.5 Budget

- 200 lines reached before 25 KB;
- 25 KB reached before 200 lines;
- UTF-8 multibyte descriptions;
- stale refresh increasing line length;
- rename/dedup changing pointer count;
- held facts after an eviction;
- native write error after over-limit write;
- exact headroom boundary.

## 16.6 Security

- credential in user turn;
- credential in error result;
- credential in Git subject;
- credential in project fact promoted manually;
- credential introduced by canonical edit;
- high-entropy but non-secret path;
- confidential non-credential text;
- path traversal name;
- symlinked canonical or mirror;
- unsafe file permissions;
- malicious frontmatter;
- ANSI/control injection.

## 16.7 Retention and lifecycle

- log rotation;
- ledger compaction;
- tombstone propagation;
- stale project returning after deletion;
- purge by project/domain;
- export and restore;
- plugin uninstall with and without `--keep-data`;
- old schema migration and rollback.

---

## 17. Production release criteria

A 1.0 release should require all of the following.

### Correctness

- zero silent data loss in crash/fault tests;
- idempotent pull, promote, repair, recovery, and GC;
- exact native store resolution;
- exact byte/line budget enforcement;
- no project identity collision;
- no local mirror edit overwritten without a decision.

### Isolation

- zero unauthorized cross-domain replication;
- profile isolation verified;
- unknown domain defaults to no cross-project import;
- secret content rejected at every ingress.

### Performance

- SessionStart beacon p95 below 100 ms on representative fleets;
- p99 below 250 ms;
- hard timeout remains fail-silent;
- no full-file read for bounded-tail operations;
- large reports operate on aggregates or paged history.

### Storage

- bounded plugin operational data;
- storage inventory is user-visible;
- compaction does not change facts or evidence conclusions;
- purge and export are tested.

### Compatibility

- worktrees and subdirectories map to the same native memory when Claude does;
- custom profile and memory-directory settings are honored;
- disabled auto-memory is honored;
- native `modified` metadata does not create false conflicts;
- supported Claude Code version range is explicit.

### External evidence

- clean-machine installation;
- at least one independent user's fleet;
- personal/work or equivalent domain separation;
- multi-week soak;
- no unresolved P0 or P1 correctness finding;
- documented migration and rollback.

---

## 18. Final assessment

### Single-project layer

**Assessment:** strong beta, near-production for one operator using the default Claude layout, provided the operator accepts the documented residuals.

The verification, deduplication, index discipline, schema checks, and conservative maintenance are good. The native path resolver and mirror edit semantics still affect single-project correctness in custom profiles, worktrees, and subdirectory launches.

### Cross-project layer

**Assessment:** conceptually coherent, operationally incomplete.

The canonical-plus-mirror model is the right response to project-scoped native recall. The scope cascade, lazy propagation, fleet tax, staleness beacon, usage evidence, and workflow registrar are meaningful differentiators.

The missing trust boundary, stable identity, conflict protocol, and transaction layer prevent production use across a genuinely heterogeneous fleet.

### Production conclusion

The repository should remain pre-1.0 while the P0 work is completed. The current preflight HOLD is correct, but clean-machine and second-user testing alone are no longer sufficient: the native store contract has evolved, and the cross-project layer needs explicit safety boundaries before broad release.

The shortest safe path is:

1. central resolver;
2. domain isolation;
3. stable IDs plus transactional control plane;
4. conflict-safe mirrors;
5. unified canonical ingress;
6. exact native budgeting;
7. bounded operational retention;
8. external validation.

That preserves the project's strongest qualities while eliminating the failure modes most likely to cause silent memory loss, leakage, or a false sense of cross-project coherence.

---

## 19. Primary source map

### Repository files

- `README.md`
- `.system-architecture/context.md`
- `docs/1.0-preflight.spec.md`
- `docs/provenance-liveness.spec.md`
- `docs/dangling-cross-store-resolution.spec.md`
- `docs/fleet-workflows.spec.md`
- `docs/session-beacon.spec.md`
- `plugins/consolidate-memory/hooks/hooks.json`
- `plugins/consolidate-memory/skills/consolidate-memory/SKILL.md`
- `plugins/consolidate-memory/skills/consolidate-memory/references/harness-map.md`
- `plugins/consolidate-memory/scripts/memory_status.py`
- `plugins/consolidate-memory/scripts/sync_global.py`
- `plugins/consolidate-memory/scripts/session_beacon.py`
- `plugins/consolidate-memory/scripts/extract_signals.py`
- `plugins/consolidate-memory/scripts/distill_scan.py`
- `.github/workflows/ci.yml`

### Claude Code public documentation

- “How Claude remembers your project”
- “Hooks reference”
- “Plugins reference”

The conclusions in this report use the current public contract available on the audit date and should be revalidated when the supported Claude Code version changes.
