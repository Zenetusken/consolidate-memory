# Gate fixtures

`make_fixture.py` generates the **frozen synthetic store** the continuous-QA gate
(`ci_check.sh`) runs the deterministic oracle against — decoupled from any live project's
memory, so the gate's blocking families always fire regardless of how Doc_Flo evolves.

- **What it guarantees:** an over-budget index (→ D3 backfill-under-gate) + a wikilink-reachable
  orphan (→ D4 evict-stage safety). Verified: live v0.1.23 → 0 FAIL; cached v0.1.19 → D3+D4 FAIL.
- **Repo/store:** `gate-repo/` (dummy repo) → its slug resolves the store at
  `~/.claude/projects/<slug>/memory` (the skill derives the store from the repo slug).
- **Regenerate:** `python3 make_fixture.py` (idempotent — clears + rewrites the store).
- Note: the fixture store appears as a node in `sync_global` scans (named `…fixtures-gate-repo`);
  that's the cost of the skill's slug-based store resolution. Harmless.
