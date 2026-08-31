---
name: cm-data
description: Inventory, export, compact, or purge consolidate-memory plugin data (not Claude's native Auto Memory).
---

Operational data lives under plugin-data. Native `~/.claude/projects/<slug>/memory` is also Claude Auto Memory — do not `rm -rf` it to uninstall this plugin.

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/cm_ops.py data inventory --project .
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/cm_ops.py data export --project . --dest /tmp/cm-export
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/cm_ops.py data compact --project .
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/cm_ops.py data purge --scope managed-mirrors --project .
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/cm_ops.py data purge --scope managed-mirrors --apply --confirm purge-managed-mirrors --project .
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/cm_ops.py data purge --scope project-ops --apply --confirm purge-project-ops --project .
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/cm_ops.py data purge --scope domain-canonicals --apply --confirm purge-domain-canonicals --project .
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/cm_ops.py data purge --scope all-plugin-data --apply --confirm purge-all-plugin-data --project .
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/cm_ops.py data retention --project .
```

Show the plan first. Purge **never** deletes Claude's native Auto Memory
(`~/.claude/projects/<slug>/memory` authored files). Export is a tar.gz + sha256
manifest of plugin-data only.
