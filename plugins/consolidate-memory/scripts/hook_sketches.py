#!/usr/bin/env python3
"""EXPERIMENTAL / out of product contract.

Opt-in (`CM_HOOK_SKETCHES=1`) transcript-derived sketches. Not part of the
installed hook manifest, registrar, or retention path. Never store raw
prompts, commands, results, or diffs.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Families we collapse tool names into. Unknown tools stay "other" (not dropped).
_FAMILY = {
    "bash": "shell", "shell": "shell", "run_terminal_command": "shell",
    "read": "read", "read_file": "read",
    "edit": "edit", "write": "write", "write_file": "write",
    "grep": "search", "glob": "search", "search": "search",
    "web_search": "web", "web_fetch": "web",
    "task": "subagent", "agent": "subagent",
    "mcp": "mcp",
}


_FORBIDDEN_KEYS = (
    "prompt", "content", "result", "output", "transcript", "input", "messages",
    "diff", "old_string", "new_string", "command", "stdout", "stderr",
)


def _day(ts: Optional[str] = None) -> str:
    if ts and len(ts) >= 10 and ts[4] == "-":
        return ts[:10]
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def tool_family(name: str) -> str:
    n = (name or "").strip()
    low = n.lower()
    if low.startswith("mcp__") or low.startswith("mcp:"):
        return "mcp"
    if "pytest" in low or low.endswith("_test") or low == "test":
        return "test"
    return _FAMILY.get(low, "other")


def normalize_hook_event(event: dict, *, project_id: str = "",
                         session_id: str = "") -> Optional[dict]:
    """Return a compact sketch or None if the event is empty/unusable.

    Refuses to copy raw prompt/result keys even if present on the input.
    """
    if not isinstance(event, dict):
        return None
    kind = str(event.get("event") or event.get("hook_event_name") or event.get("type") or "").strip()
    if not kind:
        return None
    tool = str(event.get("tool_name") or event.get("tool") or "").strip()
    outcome = str(event.get("outcome") or event.get("status") or "").strip().lower()
    if outcome not in ("success", "failure", "error", "cancelled", "skipped"):
        if event.get("is_error") or kind.endswith("Failure"):
            outcome = "failure"
        elif kind in ("PostToolUse", "TaskCompleted", "SubagentStop"):
            outcome = "success"
        else:
            outcome = "invocation"
    action = str(event.get("normalized_action") or event.get("action") or tool or kind)
    # Strip anything that looks like a prompt or payload.
    action = action.split("\n", 1)[0][:80]
    sketch = {
        "project_id": project_id or str(event.get("project_id") or ""),
        "session_id": session_id or str(event.get("session_id") or ""),
        "event": kind[:64],
        "tool_family": tool_family(tool) if tool else str(event.get("tool_family") or "other"),
        "normalized_action": action,
        "outcome": outcome,
        "day": _day(str(event.get("day") or event.get("timestamp") or "")),
    }
    # Guarantee no forbidden keys leaked in.
    for k in _FORBIDDEN_KEYS:
        sketch.pop(k, None)
    if any(k in event and k in _FORBIDDEN_KEYS for k in event):
        # We didn't copy them; still assert the sketch is clean.
        pass
    if any(k in sketch for k in _FORBIDDEN_KEYS):
        return None
    return sketch


def workflow_promotion_allowed(evidence: dict, *, explicit_user_request: bool = False) -> dict:
    """Gates: ≥2 projects, ≥2 days, repeated success, no unresolved decline,
    distinctiveness, explicit confirmation. User request may bypass recurrence."""
    if explicit_user_request:
        return {"allowed": True, "reason": "user-request-bypass", "needs_confirmation": False}
    n_proj = int(evidence.get("n_projects") or 0)
    n_days = int(evidence.get("n_days") or 0)
    n_ok = int(evidence.get("n_success") or 0)
    decline = bool(evidence.get("unresolved_decline"))
    distinctive = bool(evidence.get("distinctive", True))
    confirmed = bool(evidence.get("confirmed"))
    if n_proj < 2:
        return {"allowed": False, "reason": "need-2-projects", "needs_confirmation": False}
    if n_days < 2:
        return {"allowed": False, "reason": "need-2-days", "needs_confirmation": False}
    if n_ok < 2:
        return {"allowed": False, "reason": "need-repeated-success", "needs_confirmation": False}
    if decline:
        return {"allowed": False, "reason": "unresolved-decline", "needs_confirmation": False}
    if not distinctive:
        return {"allowed": False, "reason": "generic-cli", "needs_confirmation": False}
    if not confirmed:
        return {"allowed": False, "reason": "needs-confirmation", "needs_confirmation": True}
    return {"allowed": True, "reason": "gates-passed", "needs_confirmation": False}


def sketch_is_safe(sketch: dict) -> bool:
    if not isinstance(sketch, dict):
        return False
    return not any(k in sketch for k in _FORBIDDEN_KEYS)


def persist_sketches(plugin_data: Path, project_id: str, sketches: list) -> int:
    """Append compact sketches to plugin-data ops. Never writes native memory."""
    rows = [s for s in sketches if isinstance(s, dict) and sketch_is_safe(s)]
    if not rows:
        return 0
    try:
        from retention import operational_dir
        d = operational_dir(plugin_data, project_id)
        d.mkdir(parents=True, exist_ok=True)
        path = d / "hook-sketches.jsonl"
        with path.open("a", encoding="utf-8") as fh:
            for s in rows:
                fh.write(json.dumps(s, sort_keys=True) + "\n")
        return len(rows)
    except OSError:
        return 0
