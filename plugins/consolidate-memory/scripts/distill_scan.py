#!/usr/bin/env python3
"""distill_scan.py — within-project WORKFLOW-RECURRENCE scan for the dream's DISTILL phase (v0.1.51;
extraction rebuilt v0.1.55).

Surfaces repeated assistant **Bash-command templates** across a project's recent transcripts, so the distill
phase (SKILL.md) can RECOGNIZE repeated workflows and PROPOSE a durable artifact (report-then-apply; the model
judges + proposes, this script ONLY counts — no proposal, no authoring here). A LIVE within-project scan with
NO persisted cross-dream tally (that is the deferred D1 recurrence family).

The `--json` CONTRACT (v0.1.55): `{"window": <iso|"(all)">, "scanned": {sessions, commands, days},
"recurring": [{template, count, days, sample}, ...], "chains": [{templates: [a, b], count, days}, ...]}`.
`recurring` = templates with `count >= MIN_RECUR`, ranked by (days, count) desc, capped at `MAX_RECUR_OUT`;
`chains` = adjacent kept-segment bigrams WITHIN one compound command (the `&&`-glued sub-steps of a workflow
— NOT the multi-Bash-call arc, which the model recognizes from co-ranked rows), same threshold/ranking,
capped at `MAX_CHAIN_OUT`. `days` = distinct active days (the EPISODE dimension — ×27 across 9 days is a
workflow; ×27 in one hour is a loop; rank is a hint, not a filter). `template` is the normalized command
CLASS; `sample` is ONE firewall-screened raw command (DISPLAY only — the model genericizes any absolute
path / machine value before ever authoring an artifact; see SKILL.md distill phase).

Extraction (v0.1.55, order LOAD-BEARING): join `\\`-continuations → strip heredoc BODIES (FIRST — quote-strip
would delete a quoted tag: `<<'PY'` → `<<`, the proven spec-review B1 defect) → strip quoted strings →
segment on newline/&&/; → per-segment template with keyword handling (PREFIX-STRIP `do`/`then`, which CARRY
a command; DROP-WHOLE `done`/`fi`/… + `for`/`if`/… condition heads) + a generic/investigation-verb stoplist.
A template counts ONCE per command. Known residuals (accepted, low-frequency): `||` is not a separator;
`;`/`&&` inside `$(...)` mis-segments.

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
MAX_CHAIN_OUT = 20       # v0.1.55: cap the surfaced chains (same rationale)
DEFAULT_WINDOW_DAYS = 30  # distill scans a BROADER window than the dream's marker..HEAD (recurrence needs episodes)

# Leading shell segments that are NOT the command (constant noise that otherwise ranks #1): a bare `cd`, or a
# `VAR=value` assignment. Measured: 92% of real assistant Bash commands are multi-line `cd <repo>\n<realcmd>`.
_CD_OR_ASSIGN = re.compile(r"(?:cd\s|[A-Za-z_][A-Za-z0-9_]*=)")
# branch-name-like tokens are VARIABLE (drop from the template so `checkout -b feat/X` == `…/feat/Y`).
_BRANCHY = re.compile(r"(?:feat|fix|chore|docs|refactor|release|hotfix)/")
# v0.1.55: heredoc BODY strip — runs FIRST on the continuation-joined RAW command, BEFORE quote-strip
# (which would delete the quoted tag: `<<'PY'` → `<<` — the proven B1 order defect). Round-3 code review
# proved the earlier "unterminated" branch (`.*\Z`) AMPUTATED every following command whenever a quoted or
# multi-line `<<` slipped past — the exact truncation the retired v0.1.51 code avoided. The fix: match
# ONLY a TERMINATED heredoc (opener … a line that is exactly the tag). It is SELF-VALIDATING — a real
# terminator MUST appear — so a stray `<<` (a bit-shift, a `<<` in a commit message, a here-string) simply
# never matches and is left for quote-strip + the per-segment backstop to neutralise; NOTHING is amputated.
#   · `(?!<)` — never a `<<<` here-string;
#   · tag `[A-Za-z_][\w-]*` — starts NON-digit, so `1<<20` / `x<<8` bit-shifts can't be read as a tag
#     (this replaces the old whitespace-lookbehind guard, so a no-space `cat<<EOF` IS now recognised);
#   · `([^\n]*)` (group 3) preserves the opener's same-line tail (`cmd <<EOF && next` — bash runs `next`);
#   · `(?:.*?\n)?` allows an EMPTY body (`cat <<EOF\nEOF` — round-3 finding); the replacement `\3\n`
#     restores the terminator's newline so the command on the NEXT line keeps its own segment.
# Residual (accepted, rare): a backslash/variable tag (`<<\EOF`, `<<$T`) or a genuinely UNTERMINATED
# heredoc leaks its body as segments — a junk row, never an amputation. Real transcript heredocs terminate.
_HEREDOC = re.compile(r"<<(?!<)-?\s*(['\"]?)([A-Za-z_][\w-]*)\1([^\n]*)\n(?:.*?\n)?\s*\2\s*(?:\n|$)", re.S)
# Keyword handling (v0.1.55, spec-review M2 — proven): a keyword-led segment that CARRIES a command must
# keep it. `else` belongs here too (`if …; then A; else B; fi` — round-2 CONFIRMED finding).
_KW_PREFIX = {"do", "then", "else"}                          # strip the keyword, re-template the remainder
_KW_DROP = {"done", "fi", "esac"}                            # keyword-only noise → drop whole
_KW_HEAD_DROP = {"for", "while", "if", "case", "elif", "until"}  # condition/iterator heads, not commands → drop whole
# Stoplist — gates what can BE a row or a chain endpoint: generic verbs + investigation verbs + the
# inline-interpreter false classes (quote-strip collapses their bodies to one identical head, so each
# invocation is a distinct one-off script masquerading as recurrence). BARE interpreters included
# (`python3 <<PY` strips to `python3` — the same false class; round-2 finding).
_STOP_HEADS = {"echo", "printf", "ls", "pwd", "which", "type", "true", "sleep", "date", "touch", "mkdir",
               "grep", "rg", "cat", "head", "tail", "wc", "sed", "awk", "find", "diff"}
_STOP_TPLS = {"python3 -", "python3 -c", "bash -c", "sh -c", "python3", "python", "bash", "sh", "node"}
# Redirect handling is SPLIT-keep-head, never sub (sub would leave the target filename as a noise token:
# `cmd >> app.log` → `cmd  app.log`). `\d?` consumes the `2` of `2>&1`; `&` covers `&>`/`&>>` (round 2).
_REDIR = re.compile(r"\s(?:\d?|&)>{1,2}")
# env-assignment PREFIXES carry a command (`CM_DREAM_ARC=1 python3 …` — the SKILL's own idiom since
# v0.1.54!); strip them and template the carried command. A BARE assignment still drops via _CD_OR_ASSIGN.
# `$(…)` substitution values are already removed in _scan_cmd (round-3), so a plain `\S*` value is safe —
# an earlier `$(…)`-spanning variant BACKTRACKED into the substitution's inner space and split it.
_ENV_PREFIX = re.compile(r"^(?:[A-Za-z_][A-Za-z0-9_]*=\S*\s+)+")


def _strip_heredocs(cmd: str) -> str:
    """Remove each TERMINATED heredoc's marker+body+terminator, PRESERVING the opener line's same-line
    tail (group 3) and restoring the terminator's newline so the next command keeps its own segment.
    Terminated-only ⇒ a stray `<<` is never matched and never amputates (see the regex rationale)."""
    return _HEREDOC.sub(r"\3\n", cmd)


def _day_of(ts: str) -> str:
    """A transcript timestamp → its UTC calendar date (the episode-day unit). UTC is chosen for
    DETERMINISM: an earlier LOCAL-tz conversion (`astimezone()`) made `scanned.days`/per-row `days` — and
    thus the (days, count) ranking the model reads — depend on the RUNNER's timezone, so the same repo
    rendered a different distill signal on a UTC server vs a local laptop (round-3 finding). The tradeoff
    (a single sitting straddling UTC midnight counts as 2 days) is cosmetic — `days` is an advisory rank
    hint, not a filter. `fromisoformat` also normalises an offset stamp (`…-05:00`) to its true UTC date.
    Falls back to the raw slice on unparseable input; '' stays '' (no day accrues)."""
    if not ts:
        return ""
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(timezone.utc).date().isoformat()
    except ValueError:
        return ts[:10]


def _seg_template(seg: str) -> str | None:
    """ONE (already quote-stripped) segment → its recurring CLASS template, or None if it is noise:
    pure cd/bare-assignment, a keyword-only/condition shell keyword, or a stoplisted head. Prefixes that
    CARRY a command are stripped and the remainder templated: `do`/`then`/`else` keywords (M2 + round-2),
    case-arm heads (`start) run-server` → `run-server`), and env assignments (`CM_DREAM_ARC=1 python3 …`
    → `python3 …`). The cd/assignment noise gate runs AFTER the prefix strips (round-2: `do cd $d` must
    drop, not leak a `cd` row)."""
    seg = seg.strip().strip("()").strip()            # subshell fragments: `( cmd && x )` splits to
    #                                                  `( cmd` / `x )` → shed the orphan grouping parens
    if not seg:
        return None
    parts = seg.split(None, 1)
    while parts and parts[0] in _KW_PREFIX:          # `do mypy $f` / `else rollback.sh` → keep the command
        seg = parts[1].strip() if len(parts) > 1 else ""
        if not seg:
            return None
        parts = seg.split(None, 1)
    # case-arm label `pattern)` — `"(" not in` excludes a function def `name()` / a `$(...)` head
    # (round-3: `deploy() { … }` was mis-stripped to a junk `{ …` row). A single-line arm keeps its
    # command (`stop) kill-server` → `kill-server`); a bare pattern-only segment (a multi-line arm's
    # label alone on its line) is dropped so it can't leak as a row (round-3).
    if parts and parts[0].endswith(")") and "(" not in parts[0]:
        if len(parts) > 1:
            seg = parts[1].strip()
            parts = seg.split(None, 1)
        else:
            return None
    if parts and (parts[0] in _KW_DROP or parts[0] in _KW_HEAD_DROP):
        return None
    seg = _ENV_PREFIX.sub("", seg)                   # env-prefixed invocation → the carried command
    if not seg or _CD_OR_ASSIGN.match(seg):
        return None                                  # bare cd / bare assignment — AFTER the prefix strips
    seg = re.split(r"<<", seg)[0]                    # heredoc/here-string RESIDUE backstop (within-segment
    #                                                  truncation only — never amputates a later segment)
    seg = _REDIR.split(seg)[0]                       # truncate at the first redirect (keep head)
    seg = seg.split("|")[0].split(">")[0].strip()    # first pipe stage / any residual redirect
    out: list[str] = []
    for tok in seg.split():
        if tok == "&":
            continue                                 # background/leftover ampersand is never class-defining
        if tok.startswith("-"):
            out.append(tok.split("=")[0])            # flag NAME (drop =value)
        elif tok.startswith(("/", "~")) or "/home/" in tok or _BRANCHY.search(tok):
            continue                                 # drop abs paths + branch-likes (variable)
        elif re.search(r"\d", tok) and len(out) >= 2:
            continue                                 # drop numeric/value args after the head
        else:
            out.append(tok)
        if len(out) >= 5:
            break
    tpl = " ".join(out).strip()
    if not tpl or tpl in _STOP_TPLS or tpl.split()[0] in _STOP_HEADS:
        return None
    return tpl


def _scan_cmd(cmd: str) -> tuple[list[str], list[tuple[str, str]]]:
    """One RAW Bash command → (kept templates, deduped ONCE per command; adjacent kept-pair chains,
    once per command, no self-chains). Pipeline order is LOAD-BEARING (spec-review B1): join
    continuations → strip heredoc BODIES → strip quotes → segment → per-segment template. Chains are
    filter-then-adjacent (BRIDGE semantics): `a && echo ok && b` yields (a, b) — the stoplisted middle
    is decoration (the labeled-gate idiom), not a workflow boundary."""
    cmd = cmd.replace("\\\n", " ")                   # join `\`-continuations (D6c)
    cmd = _strip_heredocs(cmd)                       # BEFORE quote-strip (B1)
    cmd = re.sub(r'"[^"]*"|\'[^\']*\'', "", cmd)     # drop quoted strings (safe now — tags consumed)
    # v0.1.55 (round-3): a command SUBSTITUTION `$(…)` / backtick is a VALUE, never the command — its
    # own tokens (and a split-out closing `)`) otherwise leak as junk rows (`NET=$(… --json)` → a
    # `… --json)` row). Remove it here so the outer command templates cleanly and _ENV_PREFIX stays
    # simple. `[^()]*` = the common non-nested case; a nested `$( $() )` leaves a bare `)`, caught by
    # the per-segment paren-strip in _seg_template.
    cmd = re.sub(r"\$\([^()]*\)|`[^`]*`", " ", cmd)
    kept: list[str] = []
    for seg in re.split(r"\n|&&|;", cmd):
        tpl = _seg_template(seg)
        if tpl:
            kept.append(tpl)
    templates: list[str] = []
    seen: set = set()
    for t in kept:
        if t not in seen:                            # once per command (a retry isn't recurrence)
            seen.add(t)
            templates.append(t)
    chains: list[tuple[str, str]] = []
    cseen: set = set()
    for a, b in zip(kept, kept[1:]):
        if a != b and (a, b) not in cseen:
            cseen.add((a, b))
            chains.append((a, b))
    return templates, chains


def scan(project_dir: Path, since: str) -> dict:
    """Count recurring Bash-command templates + intra-command chains across the project's in-window
    transcripts, with per-item day-spread (the episode dimension). `since` empty → all (matches
    `_window_transcripts`); the CLI defaults it to ~30 days. Firewall runs FIRST, on `_norm(cmd)` —
    BEFORE any template transform (unchanged v0.1.51 contract)."""
    project_dir = project_dir.resolve()
    proj_root = Path.home() / ".claude" / "projects" / slug_for(project_dir)
    transcripts = _window_transcripts(proj_root, since)
    counts = {"sessions": len(transcripts), "commands": 0, "days": 0}
    days_seen: set = set()
    tally: dict[str, dict] = {}          # template -> {count, days, sample}
    ctally: dict[tuple, dict] = {}       # (a, b) -> {count, days}
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
                day = None   # v0.1.55 (round-3): compute the episode-day LAZILY on the first Bash part,
                #              so a Read/Edit/Grep-only message (the session majority) never parses a
                #              timestamp it won't use. Memoised for a multi-Bash message.
                for p in content:
                    if not (isinstance(p, dict) and p.get("type") == "tool_use" and p.get("name") == "Bash"):
                        continue
                    cmd = str((p.get("input") or {}).get("command", ""))
                    if not cmd:
                        continue
                    if _looks_secret(_norm(cmd)[:_PROBE_CAP]):  # FIREWALL first (on _norm); never the template transform
                        continue
                    if day is None:
                        day = _day_of(str(o.get("timestamp") or ""))
                        if day:
                            days_seen.add(day)
                    counts["commands"] += 1
                    templates, chains = _scan_cmd(cmd)
                    if not templates and not chains:
                        continue                                # all-noise command — don't build a sample for nothing
                    # build the sample only when a template is NEW (setdefault would discard it on a repeat —
                    # round-3 efficiency finding); `any` covers a command that introduces two new templates.
                    sample = " ".join(cmd.split())[:160] if any(t not in tally for t in templates) else ""
                    for t in templates:
                        rec = tally.setdefault(t, {"count": 0, "days": set(), "sample": sample})
                        rec["count"] += 1
                        if day:
                            rec["days"].add(day)
                    for pair in chains:
                        crec = ctally.setdefault(pair, {"count": 0, "days": set()})
                        crec["count"] += 1
                        if day:
                            crec["days"].add(day)
    counts["days"] = len(days_seen)
    recurring = sorted(
        ({"template": t, "count": v["count"], "days": len(v["days"]), "sample": v["sample"]}
         for t, v in tally.items() if v["count"] >= MIN_RECUR),
        key=lambda r: (r["days"], r["count"], r["template"]), reverse=True,
    )[:MAX_RECUR_OUT]
    chains_out = sorted(
        ({"templates": list(pair), "count": v["count"], "days": len(v["days"])}
         for pair, v in ctally.items() if v["count"] >= MIN_RECUR),
        key=lambda r: (r["days"], r["count"], r["templates"]), reverse=True,
    )[:MAX_CHAIN_OUT]
    return {"window": since or "(all)", "scanned": counts, "recurring": recurring, "chains": chains_out}


def _report(d: dict) -> None:
    c = d["scanned"]
    out: list = []
    add = out.append
    title = "✦ DISTILL · recurring workflow signal"
    tag = f"{len(d['recurring'])} template(s) · {len(d.get('chains', []))} chain(s)"
    gap = max(2, _ui.W - 2 - len(title) - len(tag))
    add(_ui.rule())
    add("  " + _ui.c("✦", "cyan") + title[1:] + " " * gap + _ui.c(tag, "bold"))
    add("  " + _ui.c(f"{c.get('sessions', 0)} session(s) · {c.get('commands', 0)} Bash cmds · "
                     f"{c.get('days', 0)} active day(s) · window {d['window']}", "dim"))
    add(_ui.rule())
    add("")
    if not d["recurring"]:
        add(_ui.kv("RESULT", _ui.c("no repeated workflow at count≥2 — a valid verdict when the gate says so", "dim")))
    else:
        add(_ui.kv("RECURRING", _ui.c("ranked by day-spread (episodes) then count — rank is a hint, not truth", "dim")))
        for r in d["recurring"]:
            add(f"    {_ui.c('×' + str(r['count']), 'yellow')} {_ui.c(str(r.get('days', 0)) + 'd', 'dim')} "
                f"{_ui.lbl(r['template'][:36])}  {_ui.c(_ui.wrap(r['sample'], hang=8)[:80], 'dim')}")
    if d.get("chains"):
        add("")
        add(_ui.kv("CHAINS", _ui.c("adjacent steps inside one command — a chain IS a candidate workflow", "dim")))
        for r in d["chains"]:
            add(f"    {_ui.c('×' + str(r['count']), 'yellow')} {_ui.c(str(r.get('days', 0)) + 'd', 'dim')} "
                f"{_ui.lbl(r['templates'][0][:30])} → {_ui.lbl(r['templates'][1][:30])}")
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
    # v0.1.54: write-time dream-arc cue (stderr, CM_DREAM_ARC-gated — see _ui.dream_cue)
    _ui.dream_cue("distill beat due — recurring gestures condensing (plain italics, no emoji) "
                  "above the plain scan results")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
