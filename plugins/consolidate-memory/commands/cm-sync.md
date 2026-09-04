---
name: cm-sync
description: Absorb the shared memory layer now — list, pull, and harvest cross-project facts into this project (enrolled projects only).
---

One-shot absorption of the shared layer — the sync half of a dream's Phase 1,
without the consolidation pass. An unenrolled project is local-only and `--pull`
is a no-op by design: say so honestly and point at `/cm-domain`.

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/sync_global.py --list .
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/sync_global.py --pull .
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/sync_global.py --harvest .
```

Run `--list` first (read-only) and report which globals are relevant +
missing/stale BEFORE pulling. `--pull` replicates missing mirrors and refreshes
stale ones, and auto-holds any pull that would push the always-loaded index past
the hard ceiling — report `held N` honestly (shrinking the index is the only way
to receive those). `--harvest` captures every node's organic usage windows into
the shared ledger (idempotent). Summarize the plain diff: pulled N new ·
refreshed M · held H.
