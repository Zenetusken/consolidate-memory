---
name: cm-connect
description: Hook this repo and another to the shared memory layer end to end — survey, operator-confirmed enrollment, an optional shared fact, absorption both ways, and the network payoff.
---

The two-repo onboarding wizard (see `docs/cm-commands-onboarding.spec.md`).
Enrollment is an OPERATOR grant (ADR 008) — this command sequences the grants,
never self-grants; every enrollment is planned and confirmed.

1. **Survey (read-only).** Doctor both repos and show the plan — enrolled?
   domain? — plus each enrollment's forecast (how many unadmitted mirrors it
   would quarantine; quarantine is recoverable, never delete):

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/cm_ops.py doctor .
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/cm_ops.py doctor <other-repo>
   ```

2. **Grants.** For each unenrolled repo, show its plan and ask the user for ONE
   confirmation covering both. Apply each with its exact phrase (the
   confirmation is the grant):

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/cm_ops.py project enroll . --domain personal --apply --confirm enroll-personal
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/cm_ops.py project enroll <other-repo> --domain personal --apply --confirm enroll-personal
   ```

   A repo enrolled in a DIFFERENT domain is never auto-switched — point at
   `move-domain`. A failed second enroll leaves a valid partial state; re-running
   this command completes it (enroll is idempotent).

3. **Share (optional).** Ask for one claim sentence; if given, run `/cm-share`
   from this repo. Skip cleanly with "link only".

4. **Absorb.** Pull + harvest in BOTH repos — each picks up the domain facts it
   was missing:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sync_global.py --list .
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sync_global.py --pull .
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sync_global.py --harvest .
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sync_global.py --pull <other-repo>
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sync_global.py --harvest <other-repo>
   ```

5. **Payoff.** Show the network view — the links made:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sync_global.py --tokens .
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sync_global.py --network .
   ```
