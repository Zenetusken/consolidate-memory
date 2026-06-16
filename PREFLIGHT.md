# Pre-flight checklist — before consolidate-memory goes live

Run top to bottom. **Every box must be green before merging to `main` / publishing.**
The security gate (step 6) is a hard gate: any confirmed High/Critical blocks go-live.

## 1. Manifests validate
- [ ] `claude plugin validate ./plugins/consolidate-memory --strict` → passed
- [ ] `claude plugin validate .` (marketplace) → passed

## 2. Tests green
- [ ] `python3 tests/smoke.py` → all passed
- [ ] `python3 tests/simulate_accumulation.py` → exit 0 (all lifecycle properties hold)

## 3. Plugin-runtime resolution
- [ ] With `CLAUDE_PLUGIN_ROOT=$PWD/plugins/consolidate-memory`, every `${CLAUDE_PLUGIN_ROOT}`
      command in `SKILL.md` resolves and a script runs.
- [ ] (If CLI available) real local install round-trips: `claude plugin marketplace add .`
      → `claude plugin install consolidate-memory@zenetusken-plugins` → skill loads.

## 4. Secrets & privacy boundary
- [ ] No credentials in the repo or git history (scan).
- [ ] Nothing personal/secret under `plugins/` (the published dir): no `memory/`,
      no `.consolidation-state.json`, no transcripts.
- [ ] `git ls-tree -r --name-only origin/main | grep -i memory` → only `memory/.gitkeep`.

## 5. Code-safety invariants (defensive)
- [ ] stdlib only; no `eval`/`exec`/`os.system`/`shell=True`; no network.
- [ ] only external process is read-only `git`, fixed-arg list, with timeout.
- [ ] state-file SHA is validated before reaching `git` (`_valid_sha`).
- [ ] secrets firewall + input length caps present in `extract_signals.py`.

## 6. DevSecOps security gate (hard gate)
- [ ] `security/devsecops.workflow.js` run → **gate = PASS** (0 confirmed High/Critical).
- [ ] Findings report saved under `security/findings-<date>.md`; Medium/Low triaged.

## 7. Metadata & docs
- [ ] `version` set to the release in `plugin.json` **only** (not the marketplace entry).
- [ ] `CHANGELOG.md` has an entry for this version.
- [ ] README install section = the plugin flow; layout + privacy/security current.
- [ ] `CLAUDE.md` layout / gotcha / dev-loop reflect the plugin model.

## 8. Go-live
- [ ] Branch → commit → push → PR (full body) → MERGEABLE → squash-merge → delete branch.
- [ ] `main` local == `origin/main`; working tree clean.
- [ ] Dev migration: legacy `~/.claude/skills/consolidate-memory` symlink removed; plugin
      installed locally; personal `~/.claude/memory` store untouched.
- [ ] End-user install commands verified and reported.
