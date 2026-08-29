# Frozen known-bad canary — consolidate-memory v0.1.19 (VENDORED)

The gate's watch-the-watcher self-test runs the oracle against a frozen KNOWN-BAD version of
the skill (v0.1.19 carries the real D3 backfill-under-gate + D4 evict-orphan defects) and
blocks-on-identity (`{CHK-GATE-BACKFILL, CHK-EVICT-STAGE} ⊆` detected FAIL ids) before
trusting an "allow".

**Why vendored:** the canary previously existed ONLY in the plugin cache
(`~/.claude/plugins/cache/*/consolidate-memory/0.1.19/scripts`) — a copy that exists only if
that exact version was once installed on the machine. v0.1.19 is not installable today
(install always fetches the latest), so a fresh machine or a cleared cache permanently lost
the canary and the self-test silently degraded to a fail-open SKIP. A frozen known-bad
artifact must be frozen IN THE REPO, not in an ephemeral cache.

**Provenance:** these five files are byte-identical to the `v0.1.19` git tag
(commit `e28c6bd72e171a46815eb3e9c642243582fca406`, `git ls-tree v0.1.19 --
plugins/consolidate-memory/scripts/`), committed PRE-GRAFT. The M3-slug graft is applied at
install time by `install-gate.sh` (it must be — v0.1.19 computes the OLD slug, which resolves
a DIFFERENT, empty store on a `.`-bearing state path; the graft is not the defect). Verify
with `sha256sum -c SHA256SUMS` — a smoke pin re-checks the manifest on every gate run.
`install-gate.sh` prefers a cached copy when present and falls back to this directory.

Consolidate-memory is MIT-licensed by the same author/repo — vendoring its own historical
scripts into the companion QA plugin is in-license and documented here.
