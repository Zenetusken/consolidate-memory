# cm commands — the cross-project onboarding surface (v0.4.8 spec)

**Design-of-record for the five UX verbs + one beacon line.** Status: draft for
advisor pass → adversarial review-to-zero → implementation.

## 1. Context (measured, 2026-09-04)

A fresh-user dogfood hooked two repos (`agent-loop` + `job-applicator-python`) to the
shared layer through the raw CLI. The machinery performed flawlessly — enroll with
legacy-mirror revocation forecasting (23 + 30 quarantined), one transactional
`canonical upsert --origin` producing canonical + mirror + pointer + catalog line,
the beacon firing the moment the canonical existed, a 0.48s pull in the second repo,
holders all in-sync, beacon silent after absorption. **The friction is entirely
surface**: five CLI incantations (enroll ×2 with four flags + a confirm phrase, a
hand-written schema-v3 file, a raw pull), and `cm` itself is a maintainer tool not on
an end user's PATH. The extension point already exists — marketplace **slash
commands** (`cm-domain`, `cm-doctor`, `cm-data`) — and every mutation primitive
needed is already shipped (the sole canonical writer, the journaled transacts, the
M1-ceiling pull, the network/utility views).

*(Review note F5: the session magnitudes — 23/30 quarantined, 0.48s — are
self-reported session observations; the MECHANISMS are verified in code at
cm_ops.py:2321-2325 (plan-first revocation forecast), cm_ops.py:124-165
(quarantine-not-delete), canonical_ingress.py:444-502 (one-transact origin
upsert), session_beacon.py:190-205 (beacon gated on canonical existence). The
"2 facts" figure is corroborated by the live registry `facts` table.)*

## 2. The verbs (target UX)

| Verb | One-liner | Machinery reused (nothing new) |
|---|---|---|
| `/cm-connect [OTHER-REPO]` | hook this repo and another to the shared layer, end to end | `cm doctor` survey, plan-first `project enroll`, `/cm-share` (optional), `sync_global --list/--pull/--harvest`, `--network` payoff |
| `/cm-share "<claim>"` | author ONE shared fact from one sentence | scope cascade (judgment), verification recipes, `canonical upsert --origin` |
| `/cm-sync` | absorb the shared layer now | `sync_global --list → --pull → --harvest` |
| `/cm-network` | show the shared network | `--network` / `--tokens` (read-only) |

The beacon gains one line (see §4). The dream skill is untouched — it remains the
heavyweight (multi-fact, verification fan-out); these are the single-action verbs
that compose INTO the dream's phases, never a parallel authoring path.

### 2.1 `/cm-connect` — the wizard, sequenced grants, never self-grant

1. **Survey (read-only).** `cm doctor` on THIS repo and the OTHER repo. Emit the plan:
   for each repo — enrolled? domain? store health? — plus the enrollment forecast
   (revocation counts: "A revokes 0, B revokes 30 unadmitted mirrors, quarantined not
   deleted"). Any survey failure (bad path, foreign dir) → clean error, zero
   mutations.
2. **Grants.** If either repo is unenrolled, show the combined plan and ask ONE
   confirmation covering both. The confirmation runs the existing
   `project enroll --apply --confirm enroll-<domain>` per repo. **ADR 008 is
   conserved by construction**: the operator confirms the shown plan; the command
   sequences, it never grants silently.
3. **Share (optional).** Ask for a claim sentence; if given, run the `/cm-share`
   pipeline (§2.2) from THIS repo. Skip cleanly with "link only".
4. **Absorb.** `--list` → `--pull` → `--harvest` in BOTH repos (each picks up the
   domain facts it was missing; the new fact replicates).
5. **Payoff.** The `--network` / `--tokens` view — the links made (nodes, shared
   facts, always-loaded cost), plainly.

Error states: path nonexistent / not a repo / unreadable → survey error; already
enrolled in a DIFFERENT domain → point at `move-domain`, never auto-switch; an
irreplaceable store → its revocation forecast is visible in the plan before the
confirm, so the operator can abort. **Mid-sequence failure (F4):** a failed second
enroll leaves a valid partial state (A enrolled, B not); re-running `/cm-connect`
completes it — enroll is idempotent ("already in &lt;d&gt;" exits 0).

### 2.2 `/cm-share` — guided authoring, one confirmation IS the gate

Input: one claim sentence (optional stem name). Pipeline:

1. **Cascade.** Judge scope by content (the SKILL's hard cascade: Gate 0 → Gate 1 →
   Gate 2; G2.3 needs ≥1 named other project — ask the user if the fleet evidence
   isn't obvious). Refuse `project-local` claims with "this belongs in this repo's
   own memory (`cm local upsert`), not the shared layer".
2. **Verify.** Check the claim against the live repo (files/grep/git) and the named
   other project — the dream's recipes, scaled to one fact. A claim that fails
   verification is reported, never written.
3. **Dedup.** Content-grep the domain canonicals; a same-content fact reconciles
   onto the existing canonical, never a second copy.
4. **Draft + show.** The agent drafts the canonical (frontmatter + body); the user
   sees it and confirms — **the confirmation is the report-then-apply gate** (same
   shape as the dream's Phase 4, one fact).
5. **Write.** `cm canonical upsert <stem> --file <draft> --origin --project .` — the
   sole writer, unchanged: mirror + pointer + holder + catalog in one journaled
   transact.

**Verification is load-bearing, never paraphrase (F7):** the command's body must
instruct the agent to READ
`${CLAUDE_PLUGIN_ROOT}/skills/consolidate-memory/references/harness-map.md` §
"verification recipes" and the Phase-2 cascade in
`${CLAUDE_PLUGIN_ROOT}/skills/consolidate-memory/SKILL.md` (full plugin-root
paths — a command file at `${CLAUDE_PLUGIN_ROOT}/commands/` cannot use the
SKILL's relative spelling; the single sources, never a re-telling in the command
file), to SHOW the existing canonical's before/after diff when the stem already
exists (a replace frozen the holder mirrors at the next pull —
canonical_ingress.py:467-474), and to enforce **no-verify-no-write**: a claim
that fails verification is reported and dropped, never written.

Error states: firewall refusal (secret-shaped content) → rephrase, never weaken;
admission/index refusal → surfaced; undetectable `stacks:` → the writer's own error,
shown; unenrolled → "run /cm-domain first" (the writer refuses anyway).

### 2.3 `/cm-sync` + `/cm-network` — thin wrappers

`/cm-sync`: `--list` (read-only) → `--pull` → `--harvest`, then a plain human diff
("pulled 2 new: X, Y · refreshed 1 · held 0 · harvested 1 node window"). Unenrolled →
one line pointing at `/cm-domain` (pull is a no-op by design — say so, honestly).
`/cm-network`: render `--network` + `--tokens` plainly; read-only, no gates.

## 3. Implementation shape — four files + one small script edit + pins

- `plugins/consolidate-memory/commands/cm-connect.md`, `cm-share.md`, `cm-sync.md`,
  `cm-network.md` — the same frontmatter + `${CLAUDE_PLUGIN_ROOT}/scripts/...`
  invocation format as the shipped `cm-domain.md` (which may carry a positional-order
  doc bug — see §6).
- `plugins/consolidate-memory/scripts/session_beacon.py` — the unenrolled branch
  (~25 lines): `if not cross_project_allowed: return 0` becomes: if the store
  PARTICIPATES (holds ≥1 `*.md` — the existing never-participated-silence
  definition, `beacon_line` line 90) AND the user's enrolled domain(s) hold
  active facts, emit the behind-advisory generalized — *"Cross-project memory: N
  shared fact(s) not reachable here — this project is unenrolled; /cm-domain can
  enroll it."* (F8: statement, not imperative — the beacon's own spec bans
  directives in the injected line.) **Zero new writes, zero new state**; it
  repeats until enrolled (the behind-advisory's semantics) and the existing
  `beacon_snooze_until` quiets participating stores. Read-only contract, 2s
  budget held.
  **Measured mechanism (2026-09-04, review F1/F2/F3):** an unenrolled ctx resolves
  `domain_id='unknown'` → `canonical_domain_dir = …/domains/unknown/facts` (the
  WRONG dir), and `iter_admissible_facts` is enrollment-gated (returns 0). So N
  derives from the REGISTRY by PURE SQL — no filesystem walk, no path join, no
  DB-name-to-path validation surface: `connect_if_exists` +
  `SELECT COUNT(*) FROM facts WHERE domain_id IN (SELECT DISTINCT domain_id FROM
  projects WHERE status='enrolled' AND domain_id!='unknown') AND status='active'`
  (sub-ms; the `domains` table is lifecycle-only — purges write it via
  `domain_status_set`; `projects` is the membership source). Silent when the
  registry is absent, no enrolled domain has active facts, or the store has never
  participated (F1: the snooze stamp REFUSES a store with no state file —
  memory_status.py:1864-1865 — so a never-participated store could never quiet
  the line; the participation gate restores "never-participated dirs cost 0"
  literally, and both dogfood repos were mirror-heavy pre-enroll so the gate
  still captures the dogfood case). **F3:** the beacon docstring silence block +
  `docs/session-beacon.spec.md` are amended in the same PR — the new tier is part
  of the design-of-record, not a contradiction of it.
- `tests/smoke.py` pins.

**Zero new scripts. Zero new writers.** Every mutation stays inside the existing
journaled transacts, the canonical writer, and the enrolled-project gates.

## 4. Invariants conserved (the argument table)

| Invariant | How the design conserves it |
|---|---|
| ADR 008 — enrollment is an operator grant, never self-service | `/cm-connect` shows the plan (incl. revocation forecast) BEFORE the confirm; the confirmation is the grant; nothing auto-enrolls |
| Report-then-apply for authoring | `/cm-share`'s confirmation is the gate; no write without it |
| Beacon: read-only, never writes, 2s budget | the unenrolled advisory reads the same inputs the behind-advisory already reads; no new state, no writes |
| Single canonical writer | `/cm-share` calls `cm canonical upsert --origin` — the same ingress as dreams/promotion |
| Zero runtime dependencies | command files are prose; the beacon edit is stdlib |
| M1 ceiling / index admission | unchanged — pulls still hold past the ceiling; pointers still linted |
| Secrets firewall | the writer still refuses secret-shaped content; `/cm-share` surfaces the refusal |

## 5. Non-goals (explicitly rejected)

- **No auto-pull on SessionStart** — surprise writes every session + budget risk; the
  beacon nudges, `/cm-sync` acts (the measured-absorption premise).
- **No self-service enrollment** — the wizard sequences operator-confirmed grants;
  it never skips the confirm.
- **No parallel authoring path** — the dream remains the verification-heavy curator;
  `/cm-share` is one fact, one confirmation.
- **No new state in the beacon** — no first-seen flags, no new snooze keys.

## 6. Arc findings folded in

- **cm-domain.md positional-order bug (verified 2026-09-04):** the shipped
  `cm-domain.md` examples `project enroll --domain personal .` (flags before the
  positional) fail argparse — measured: usage-error on `enroll --domain personal .`,
  correct behavior on `enroll . --domain personal`. Fix every
  `enroll`/`move-domain`/`unenroll`/`rebind` example to positional-first order in
  this same PR (doc-only, no behavior change).

## 7. Verification (the no-shortcuts rule)

- **Smoke pins** (each must fail on pre-fix code):
  - the beacon emits the unenrolled advisory **with the exact N** from the
    registry query — fixture: seed 2 active + 1 superseded facts in the enrolled
    domain → line says "2 shared fact(s)", never 3 (F2);
  - the beacon stays **silent** for a never-participated unenrolled store (empty
    store dir) even with a non-empty domain (F1);
  - the beacon stays silent for a participating unenrolled store with an
    empty/absent domain;
  - the line's wording carries the statement form ("/cm-domain can enroll it"),
    never an imperative (F8);
  - the four command files exist with frontmatter and reference the canonical
    script paths (`cm_ops.py` / `sync_global.py` via `${CLAUDE_PLUGIN_ROOT}`);
  - `/cm-share`'s body names the reads with the EXACT full path strings
    `${CLAUDE_PLUGIN_ROOT}/skills/consolidate-memory/references/harness-map.md`
    and `${CLAUDE_PLUGIN_ROOT}/skills/consolidate-memory/SKILL.md` (F7 — a
    wrong path fails the pin);
  - the command files' enroll invocations match the argparse-surviving positional
    order (pin the cm-domain.md fix).
- Full suite per round: smoke / concurrency / simulate_accumulation / mypy /
  manifests / bench --quick / pre-push gate / CI.
- One review agent over the PR; findings fixed and re-verified before merge.

## 8. Ship shape

Additive, backward-compatible → **patch** (next release after the arc's PR merges;
CHANGELOG-first per the release policy).
