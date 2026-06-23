#!/usr/bin/env python3
"""distill_scan.py — within-project WORKFLOW-RECURRENCE scan for the dream's DISTILL phase (v0.1.51).

Surfaces repeated assistant **Bash-command templates** across a project's recent transcripts, so the distill
phase (SKILL.md) can RECOGNIZE repeated workflows and PROPOSE a durable artifact (report-then-apply; the model
judges + proposes, this script ONLY counts — no proposal, no authoring here). A LIVE within-project scan with
NO persisted cross-dream tally (that is the deferred D1 recurrence family).

The `--json` CONTRACT: `{"window": <iso|"">, "scanned": {sessions, commands}, "recurring": [{template, count,
sample}, ...]}`. `recurring` = templates with `count >= MIN_RECUR`, ranked desc, capped at `MAX_RECUR_OUT`.
`template` is the normalized command CLASS (cd/VAR= prefixes dropped, multi-line segmented, args genericized);
`sample` is ONE firewall-screened raw command for that template (DISPLAY only — the model genericizes any
absolute path / machine value before ever authoring an artifact; see SKILL.md distill phase).

Reuses `extract_signals`' firewall/window/norm + `memory_status`' slug rule — does NOT re-implement them
(the reimplementation-pin discipline).
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import _ui  # sibling: shared visual vocabulary
from extract_signals import _PROBE_CAP, _looks_secret, _norm, _window_transcripts
from memory_status import slug_for  # single source of the CC slug rule

MIN_RECUR = 2            # MiMo's bar: a workflow is a candidate only when it actually recurred (>=2x)
MAX_RECUR_OUT = 40       # cap the surfaced templates — the model judges; don't flood the phase
DEFAULT_WINDOW_DAYS = 30  # distill scans a BROADER window than the dream's marker..HEAD (recurrence needs episodes)

# Leading shell segments that are NOT the command (constant noise that otherwise ranks #1): a bare `cd`, or a
# `VAR=value` assignment. Measured: 92% of real assistant Bash commands are multi-line `cd <repo>\n<realcmd>`.
_CD_OR_ASSIGN = re.compile(r"(?:cd\s|[A-Za-z_][A-Za-z0-9_]*=)")
# branch-name-like tokens are VARIABLE (drop from the template so `checkout -b feat/X` == `…/feat/Y`).
_BRANCHY = re.compile(r"(?:feat|fix|chore|docs|refactor|release|hotfix)/")


def _template(cmd: str) -> str | None:
    """Normalize a (possibly multi-line) Bash command to its recurring CLASS template, or None if it is pure
    cd/assignment noise. This is distill_scan's OWN transform on the RAW command (keeps newlines to segment) —
    separate from `_norm` (which collapses newlines and is used ONLY for the firewall scan)."""
    cmd = re.sub(r'"[^"]*"|\'[^\']*\'', "", cmd)           # drop quoted strings FIRST — BEFORE the split, so a ; or
    #                                                        && inside a quoted arg ("git commit -m 'fix; x'") can't
    #                                                        truncate the segment / leak an open-quote fragment.
    # NOTE: a noise-led chain ("echo ... && <realcmd>") templates to its FIRST real segment ("echo") — acceptable:
    # the distill phase tells the model to ignore generic verbs (echo/grep/ls) + the real workflow recurs standalone.
    for seg in re.split(r"\n|&&|;", cmd):
        seg = seg.strip()
        if not seg or _CD_OR_ASSIGN.match(seg):
            continue                                       # drop empty + pure-cd + leading VAR= assignments
        seg = re.split(r"<<", seg, maxsplit=1)[0]          # heredoc → keep the head ("python3 - <<'PY'" → "python3 -")
        seg = seg.split("|")[0].split(">")[0].strip()      # first pipe / redirect stage
        out: list[str] = []
        for tok in seg.split():
            if tok.startswith("-"):
                out.append(tok.split("=")[0])              # flag NAME (drop =value)
            elif tok.startswith(("/", "~")) or "/home/" in tok or _BRANCHY.search(tok):
                continue                                   # drop abs paths + branch-likes (variable)
            elif re.search(r"\d", tok) and len(out) >= 2:
                continue                                   # drop numeric/value args after the head
            else:
                out.append(tok)
            if len(out) >= 5:
                break
        tpl = " ".join(out).strip()
        return tpl or None
    return None  # nothing but cd / assignments → not a command


def scan(project_dir: Path, since: str) -> dict:
    """Count recurring Bash-command templates across the project's in-window transcripts. `since` empty → all
    (matches `_window_transcripts`); the CLI defaults it to ~30 days. Firewall runs FIRST, on `_norm(cmd)`."""
    project_dir = project_dir.resolve()
    proj_root = Path.home() / ".claude" / "projects" / slug_for(project_dir)
    transcripts = _window_transcripts(proj_root, since)
    counts = {"sessions": len(transcripts), "commands": 0}
    tally: dict[str, dict] = {}  # template -> {count, sample}
    for tr in transcripts:
        try:
            fh = tr.open(encoding="utf-8", errors="replace")
        except OSError:
            continue  # a concurrent gc/chmod must not abort the pooled scan
        with fh as f:
            for line in f:
                if '"tool_use"' not in line:  # cheap pre-filter — skip the lines that can't carry a tool call
                    continue
                try:
                    o = json.loads(line)
                except (json.JSONDecodeError, RecursionError, ValueError):
                    continue
                msg = o.get("message")
                if not isinstance(msg, dict) or msg.get("role") != "assistant":
                    continue
                content = msg.get("content")
                if not isinstance(content, list):
                    continue
                for p in content:
                    if not (isinstance(p, dict) and p.get("type") == "tool_use" and p.get("name") == "Bash"):
                        continue
                    cmd = str((p.get("input") or {}).get("command", ""))
                    if not cmd:
                        continue
                    if _looks_secret(_norm(cmd)[:_PROBE_CAP]):  # FIREWALL first (on _norm); never the template transform
                        continue
                    counts["commands"] += 1
                    tpl = _template(cmd)
                    if not tpl:
                        continue
                    rec = tally.get(tpl)
                    if rec is None:
                        tally[tpl] = {"count": 1, "sample": " ".join(cmd.split())[:160]}  # sample = screened, ws-collapsed
                    else:
                        rec["count"] += 1
    recurring = sorted(
        ({"template": t, "count": v["count"], "sample": v["sample"]} for t, v in tally.items() if v["count"] >= MIN_RECUR),
        key=lambda r: (r["count"], r["template"]), reverse=True,
    )[:MAX_RECUR_OUT]
    return {"window": since or "(all)", "scanned": counts, "recurring": recurring}


def _report(d: dict) -> None:
    c = d["scanned"]
    out: list = []
    add = out.append
    title = "✦ DISTILL · recurring workflow signal"
    tag = f"{len(d['recurring'])} template(s)"
    gap = max(2, _ui.W - 2 - len(title) - len(tag))
    add(_ui.rule())
    add("  " + _ui.c("✦", "cyan") + title[1:] + " " * gap + _ui.c(tag, "bold"))
    add("  " + _ui.c(f"{c.get('sessions', 0)} session(s) · {c.get('commands', 0)} Bash cmds scanned · window {d['window']}", "dim"))
    add(_ui.rule())
    add("")
    if not d["recurring"]:
        add(_ui.kv("RESULT", _ui.c("no repeated workflow at count≥2 — create nothing (the common, valid outcome)", "dim")))
    else:
        add(_ui.kv("RECURRING", _ui.c("templates the model judges → propose the SMALLEST artifact, report-then-apply", "dim")))
        for r in d["recurring"]:
            add(f"    {_ui.c('×' + str(r['count']), 'yellow')} {_ui.lbl(r['template'][:40])}  {_ui.c(_ui.wrap(r['sample'], hang=8)[:90], 'dim')}")
    print(_ui.ascii_translate("\n".join(out)))


def main() -> int:
    argv = sys.argv[1:]
    as_json = "--json" in argv
    argv = [a for a in argv if a != "--json"]
    _ui.set_modes(color=_ui.color_enabled(sys.argv[1:], sys.stdout), ascii="--ascii" in sys.argv, width=_ui.resolve_width(sys.argv[1:], sys.stdout))
    since = ""
    pos = []
    i = 0
    while i < len(argv):
        if argv[i] == "--since" and i + 1 < len(argv):
            since = argv[i + 1]; i += 2
        elif not argv[i].startswith("-"):
            pos.append(argv[i]); i += 1
        else:
            i += 1  # skip visual/unknown flags
    if not since:  # default to a recent window (BROADER than the dream's marker..HEAD; recurrence needs episodes)
        since = (datetime.now(timezone.utc) - timedelta(days=DEFAULT_WINDOW_DAYS)).isoformat()
    project_dir = Path(pos[0]) if pos else Path.cwd()
    d = scan(project_dir, since)
    if as_json:
        print(json.dumps(d, indent=2))
    else:
        _report(d)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
