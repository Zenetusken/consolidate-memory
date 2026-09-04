---
name: cm-doctor
description: Print the resolved StoreContext (native/canonical/control-plane paths, enrollment, registry health).
---

Run the plugin doctor against the current project:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/cm_ops.py doctor .
```

Unenrolled projects are local-only until `cm project enroll --domain NAME`. Registry failures fail closed for mutations; this command still prints `registry_state`.
