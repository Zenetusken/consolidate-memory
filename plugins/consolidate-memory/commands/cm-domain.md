---
name: cm-domain
description: Show, enroll, move, or unenroll this project's trust domain (plan-first; enrollment does not silently switch).
---

Domain membership is the operator grant (ADR 008 / 012). Distinct intents:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/cm_ops.py project show .
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/cm_ops.py project enroll --domain personal .
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/cm_ops.py project move-domain --to work .
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/cm_ops.py project unenroll .
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/cm_ops.py project rebind .
```

`enroll` refuses if the project is already enrolled in a different domain — use `move-domain`. Unenroll and move revoke managed mirrors that are not admitted in the destination. Confirm with the user before `--` applying a domain change on an irreplaceable store.
