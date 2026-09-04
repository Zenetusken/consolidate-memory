---
name: cm-network
description: Show the shared-memory network — per-node token cost, the shared-fact topology, and fleet utility (read-only).
---

Read-only fleet views over the shared layer: what each node pays for the
always-loaded tier, which facts are baseline (everyone-holds) vs this-stack, and
the recall-utility evidence each canonical has accrued.

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sync_global.py --tokens . --json
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sync_global.py --network .
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sync_global.py --utility .
```

Nothing here mutates a store. A canonical showing 0 organic reads is absence of
evidence, never proof of no use — never prune on these numbers alone.
