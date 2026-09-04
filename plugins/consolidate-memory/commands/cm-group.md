---
name: cm-group
description: Create and manage operator-granted recipient groups — the routed-link tier above the domain (cross-domain, P2P-scale sharing).
---

Groups are the governed successor to the old A→B layer (v0.4.10 spec
`docs/group-scopes.spec.md`): an operator-granted recipient set that NARROWS a
fact's delivery (`recipients:` on the canonical) and may bridge domains. A
group is created in a HOME domain; membership is granted per project; a fact
may target only groups born in its own domain. Read-only first:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/cm_ops.py group list
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/cm_ops.py group show <name>
```

Plan-first mutations (each needs its exact confirm phrase — the confirmation
IS the grant):

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/cm_ops.py group create <name> --domain <home>
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/cm_ops.py group create <name> --domain <home> --apply --confirm create-group-<name>
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/cm_ops.py group add <name> <project-path>
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/cm_ops.py group add <name> <project-path> --apply --confirm add-group-<name>
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/cm_ops.py group remove <name> <project-path>
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/cm_ops.py group remove <name> <project-path> --apply --confirm remove-group-<name>
```

`group add` across domains IS allowed — the operator declares the bridge.
`group remove` withdraws the member's group mirrors: clean mirrors are
deleted, locally-edited ones quarantined (never lost). A recreated group name
is a fresh identity — facts whose `recipients` predate it refuse to re-point.
