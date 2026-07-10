# SessionStart beacon — the absorption-rate lever (Stage B)

**Status:** shipped (this PR). **Scope:** `hooks/hooks.json` (the plugin's FIRST hook component) +
`scripts/session_beacon.py` + the `--pull`-written stacks cache + a SKILL Phase-5 merge rule.
Stage A (`--staleness`, v0.1.80) existed to prove or refute this design's premise before any hook
shipped — it proved it on first live run: **12 of 13 fleet stores behind on user-global
absorption; a real node 18 days behind with 11 missing globals**. A lagging node by definition
never runs the flows that report lag; SessionStart is the one surface every session crosses.

## The measured constraints that shaped the design

- **`detect_stacks` is unaffordable in a hook**: MEASURED 2003ms on the fleet's biggest repo
  (144ms on this one) against the hook's 2s hard timeout. So `--pull` now merge-writes
  **script-truth `stacks` + `project_path`** into `.consolidation-state.json` at the moment
  `detect_stacks` actually ran; the beacon reads the cache and degrades honestly to
  user-global-only (labeled in its line) when absent. `--staleness` consumes the same cache —
  non-trigger rows upgrade to `cached stacks (as of last pull)`. `project_path` is the honest
  slug→path inverse, recorded at the one moment it is authoritatively known.
- **The hook contract** (verified against current docs, not memory): plugin hooks live at
  `hooks/hooks.json`; SessionStart matchers `startup`/`resume` as TWO entries (source-matcher
  alternation is not documented; omitting the matcher would also fire on `clear`/`compact`);
  `timeout` is SECONDS; **stdout is injected into Claude's context** (the SessionStart
  exception) and capped at 10k chars — write factual statements, not imperatives; stderr is
  invisible to Claude; SessionStart cannot block. Personal-scope installs carry no extra
  per-hook trust prompt (the `/plugin install` is the consent); enterprise
  `allowManagedHooksOnly` can disable it wholesale.
- **No subprocess in v1** (budget discipline): the git-based dream-timing advisory stays in
  `cm status` — a documented reach limit, not an oversight. Measured beacon wall time: ~37–53ms
  end-to-end including interpreter startup.

## Behavior

At most ONE factual line, e.g.: *"Cross-project memory: 3 shared global fact(s) are not yet
mirrored here (1 would be ceiling-held); last consolidation 12.4d ago. A consolidation pass
(dream) on this project absorbs them."* (~45 est tok when it fires; ~0 in the common case). The
ceiling-held figure calls **`_plan_pull` itself** — the one accounting replay (PR-#94 review F1
found the first draft's hand-rolled MISSING-only loop omitted STALE-refresh deltas and, in a
verified fixture, advertised a pull the real ceiling refused; the divergence class `_plan_pull`
exists to kill). STALE items enter as POINTER DRIFT (real index line ≠ derived pointer — exactly
the refresh delta a real `--pull` applies; body-only staleness is delta-0). Reach notes: a
hand-edited index line under an in-sync mirror counts a phantom delta (conservative — fewer
advertised as absorbable); `beacon_snooze_until` must be ISO-8601 and fails OPEN (a garbled
suppressor never silently defeats the signal). The gap counts come from `_store_gaps` — the SAME
predicate `fleet_staleness` uses (factored shared, so the beacon and the report cannot disagree).

**Silence rules (no-nag, all deliberate):** global store absent/empty · this store holds no
`*.md` (never-participated dirs must cost zero — the plugin is user-wide; discovery is
`--staleness`'s job) · `beacon_snooze_until` in the future (set per-store on explicit user ask —
report-then-apply applies to snoozing too) · 0 missing and 0 stale.

**Failure posture:** any unexpected error → empty stdout, diagnostic on stderr (hook debug only),
exit 0 — a best-effort advisory must never inject a traceback into every session start nor render
an error notice (exit 2 would). Advisory only: the beacon never pulls, never writes any store —
absorption still happens only through a dream on that project (explicit-trigger-only untouched).

**Complexity bound (PR-#94 review F4):** O(relevant + index_bytes) — the index is split once into
an anchor→cost map (the per-fact re-split measured 4.5s only at a pathological 500-fact × 4MB
fixture; any ceiling-governed store is sub-millisecond, today's fleet ~40ms end-to-end).
**Rollout note (review F1):** the hook arrives via the normal plugin auto-update; whether Claude
Code prompts when an UPDATE introduces a hook that wasn't there at install time is not documented
either way — the README carries the user-facing sentence regardless, and the emitted line names
its own snooze escape (review F2). `cm beacon [DIR]` is the debug lens.

**The SKILL Phase-5 merge rule (load-bearing):** the model writes the state file at marker time —
it must MERGE into the existing JSON, preserving the script-owned keys (`stacks`, `project_path`,
`beacon_snooze_until`), or every dream would wipe the cache the beacon depends on until the next
pull restores it.

## Acceptance gates

1. Sandboxed end-to-end (subprocess, stdin `cwd` JSON): silent on empty store / in-sync store /
   snoozed store; exactly one factual line (token-capped) on a behind store, with the
   no-cache basis labeled; rc=0 + empty stdout under sabotage (garbage state file; HOME pointing
   at a file). MEASURED runtime well under the 2s timeout.
2. `claude plugin validate --strict` passes WITH `hooks/hooks.json`; the hooks schema is pinned
   (double nesting, exact matchers, seconds timeout, `${CLAUDE_PLUGIN_ROOT}` command).
3. `--pull` writes the cache (merge — model keys preserved); `--staleness` shows the upgraded
   basis; a cache-write failure warns and degrades, never fails the pull.
4. Full gates: smoke + sim + mypy + manifests.
