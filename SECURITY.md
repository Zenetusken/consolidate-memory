# Security & data handling — consolidate-memory

This plugin reads your work session and your memory stores to consolidate durable
facts. Because it touches transcripts and persistent memory, here is exactly what it
does, what it never does, and how to report a problem.

## What it touches

- **Reads (local only):** the current project's git log, the repo memory docs
  (`MEMORY.md`/`AGENTS.md`/`CLAUDE.md`), Claude Code's per-project auto-memory
  (resolved by StoreContext — default `~/.claude/projects/<slug>/memory/`), domain
  canonicals under `~/.claude/consolidate-memory/domains/<domain>/facts/` (legacy
  `~/.claude/memory/` is a read-only migration source), and — via the bundled
  `extract_signals.py` — the *tail signal* of the active session transcript (it
  streams the `.jsonl`; it never bulk-loads or copies it).
- **Writes (local only):** memory fact files + index in the native store and the
  project's enrolled domain (unenrolled projects cannot write canonicals), plus
  operational state under plugin-data. **Not all writes wait for Phase 4:** Phase 1
  `--pull` / `--harvest` replicate already-approved canonicals and usage ledgers
  before the Phase-4 proposal. Authoring, deletion, promotion, migration, and
  committed-doc edits stay report-then-apply.
- **Never:** makes network calls, sends telemetry, or transmits any of your data
  anywhere. Every script is **Python 3 stdlib only** — no third-party packages, no
  `pip install`.

## Security properties (enforced in code)

- **No code execution surface:** no `eval`/`exec`/`os.system`/`shell=True`. The only
  external process is `git` (read-only: `rev-parse`, `log`), invoked with a fixed
  argument **list** (never a shell string).
- **Argument-injection guard:** the commit SHA read from the on-disk state file is
  validated as hex before being passed to `git` (`memory_status._valid_sha`), so a
  tampered state file cannot inject `git` options.
- **Secrets firewall at retrieval:** `extract_signals.py` drops any session turn that
  contains a credential-shaped value to a label — the verbatim secret never reaches a
  memory file (repo docs are committed; auto-memory persists). It records a *pointer*,
  never a value. `distill_scan.py` (the workflow-recurrence reader) is the other
  transcript consumer and applies the **same** `extract_signals._looks_secret` firewall,
  at the point of EMISSION (v0.1.58): a credential-shaped command still counts into its
  command-CLASS template (so recurrence stays accurate) and into a `scanned.secrets_omitted`
  transparency counter, but its raw text can never surface — its display `sample` becomes an
  omission label, and every emitted template is screened through the same firewall (on the
  `_norm`'d form, so a zero-width-split secret is caught) before it can become a row or a
  chain endpoint.
- **Bounded input:** the defense is that **the quantifier which can sweep a separator-free run to
  the end of the string is bounded** — *not* the stronger and more flattering claim that `_SECRET`
  is built only from bounded quantifiers. That universal is false, so it is worth stating the
  narrower truth plainly: scanning the live pattern (comments stripped, character classes and
  escapes collapsed) for `[*+]|\{\d+,\}` finds **20 unbounded quantifiers** in non-comment parts of
  it — `\s*`, `\S+`, `\S{8,}`, `{16,}`, the vendor-key arms. The bounded-quantifier property holds
  **at the four instances**, not of the regex. An earlier version of this bullet argued the
  opposite — "each alphanumeric run and its required separator are disjoint, so there's no
  ambiguity to blow up" — and that reasoning was falsified: v0.1.70's pentest found **four**
  instances in `_SECRET` where adjacent unbounded quantifiers could sweep a separator-free run for
  genuine O(n²) blowup (the compound-keyword prefix, a URI-creds arm, the JWT arm via a
  repeated-anchor attack, and the `authorization|bearer` arm). In each, the *offending* quantifier
  is now bounded — some by a `{n,MAX}` cap where there was none, some by a cap replacing a `*` or
  `+`; the arm around it is not uniformly bounded, and does not need to be. The `_PROBE_CAP` = 4000
  length cap on transcript turns is **defense-in-depth, not the defense**, and it does not cover
  every call site — `extract_signals.py`'s probes cap, `facts_manifest.py` caps its fact-body read at
  4 MiB, and `sync_global.py`'s shared `_safe_read_text` is **uncapped**. It is not only that helper:
  `distill_scan.py` screens **uncapped** text at its emission choke-point (`_looks_secret(_norm(tpl))`)
  and again on its row scan, where the only cap is `_USED_CAP` applied *after* the screen. (The irony
  is on the record at `_safe_read_text`: that helper was factored once precisely because "copy-paste
  doesn't propagate a fix" — and the cap is the part that did not propagate.) This is why the cap is
  *defense-in-depth* rather than the defense, and why the sentence above is about **bounded
  quantifiers** instead: what keeps uncapped input affordable is that the scan is **linear**, which is
  measured rather than argued — an uncapped call site costs more, not catastrophically more.
- **One instance no timing bound can separate is asserted structurally instead** — the JWT arm, whose
  separation grows only `~0.37 × (n/cap)` because its blowup is `occurrences × sweep` with the sweep
  capped; at n=24000 the shipped scan *under load* already exceeds the pre-fix scan *idle*, so the
  window is empty rather than narrow. That pin takes **two** checks since v0.4.28, because a
  source scan returning a *verdict* about linearity proved undecidable in practice (six one-token
  evasions across three review rounds): a behavioural check on a repeated-anchor payload, and a check
  that the arm's text **is** its measured text, byte for byte — which is decidable, and which makes
  the scanner's own bugs fail **safe**. The guard asserts a **measured CPU-time bound, not proven
  linearity**, so the rest of the pattern's linearity rests on measurement rather than on an argument;
  the measurements, the margin every bound carries, and the guard's own blind spots are recorded in
  the ReDoS guard's design-of-record,
  [docs/redos-guard-linearity.spec.md](docs/redos-guard-linearity.spec.md).
- **Filesystem safety:** `sync_global.py --gc` only deletes files marked as managed
  mirrors (`global_ref:`) whose canonical is gone — never project-authored facts — and
  defaults to report-only (deletion requires `--apply`).

## What ships in the plugin

Only `plugins/consolidate-memory/` is packaged. Your personal memory store (`memory/`
at the repo root) is **gitignored and never published** — verify with
`git ls-tree -r --name-only origin/main | grep memory` (only `memory/.gitkeep`).
`tests/`, `security/`, and operational state stay outside the plugin directory.

## Supply chain

- Pin what you install. Install from the marketplace via Git
  (`/plugin marketplace add Zenetusken/consolidate-memory`); a tagged release or pinned
  `sha` gives reproducible installs.
- Plugins are copied to a local cache on install and run from there; this plugin adds
  exactly one hook — a SessionStart beacon (matchers `startup` + `resume`, 2 s timeout)
  that may inject at most one read-only advisory line — and no MCP servers and no
  background processes: skill + scripts + that one advisory hook.

## Threat model (v0.3.0)

These attacker stories are what ADRs 008–016 close. They are not a pentest
report; they are the stories `cm doctor` / mutating commands must fail closed on.

- **Newly cloned / malicious unenrolled repo.** Must not create or pull
  cross-project canonicals. `unknown` is local-only.
- **Corrupt `control.sqlite`.** Mutations and cross-project reads refuse;
  the SessionStart beacon stays silent; `cm doctor` names `registry_state`.
- **Enroll switch leaving always-loaded pointers.** `enroll` refuses a silent
  domain switch. `move-domain` / `unenroll` journal a revoke (clean mirrors
  deleted, local edits quarantined under `native/quarantine/`).
- **Classify/lock race.** Pull records plan-time hashes; dest-verify-before-delete;
  a local edit under lock re-classifies to stop/conflict/quarantine, never overwrite.
- **Crash mid-publish.** Journal v3: no origin delete until every dest hash
  matches; registry COMMIT precedes journal complete.
- **Migrate rollback of an edited file.** Hash-aware: edited-after-apply files
  are conflicts, never deleted.

## Known limitations (v0.3.6)

- Unenrolled projects are **local-only** (ADR 008). They cannot create or pull
  cross-project canonicals. Enroll into a named domain to share.
- `forget` is **lazy acknowledgment**: other projects drop the mirror on their
  next `--pull` / `--gc --apply`. Offline clones keep bytes until they run.
- Completed `journal.sqlite` rows from before 0.3.5 may still contain fact
  bodies (`bytes_b64` / `text`) until `cm journal compact` (also run from
  `cm data compact`). New operations do not. Export archives a redacted copy.
- A crafted project/local `autoMemoryDirectory` cannot select another project's
  store; a dedicated namespace requires `cm project grant-native`. User/managed
  settings may still name an absolute dir.
- A corrupt/locked `control.sqlite` **refuses mutations and cross-project reads**.
  The SessionStart beacon stays silent on registry failure.
- Public 1.0 remains HOLD.

## Release integrity (R5, v0.4.2)

- Every release tag is **SSH-signed** (`release.sh --finalize` refuses without
  `user.signingkey`); the committed public key (`.github/release-tag.pub`) is
  the trust anchor — the CI `verify` job runs `git verify-tag` on every pushed
  tag. Threat model: `main` is PR-only (branch ruleset) and the pubkey is
  committed, so a tag the key did not sign cannot pass the gate.
- The tag-triggered workflow also re-runs the strict plugin validates
  (marketplace + both plugins) and publishes **SLSA build provenance** to the GitHub
  **attestations API** — not a release asset — while a **stdlib-generated SPDX SBOM**
  and `SHA256SUMS` are attached to the GitHub Release.

## Reporting a vulnerability

Please open a GitHub security advisory or a private issue at
<https://github.com/Zenetusken/consolidate-memory>. Do not include real credentials in
reports. We aim to acknowledge within a few days.
