#!/usr/bin/env python3
"""distill_scan.py — within-project WORKFLOW-RECURRENCE scan for the dream's DISTILL phase (v0.1.51;
extraction rebuilt v0.1.55; hardened + deterministic capture v0.1.58).

Surfaces repeated assistant **Bash-command templates** across a project's recent transcripts, so the distill
phase (SKILL.md) can RECOGNIZE repeated workflows and PROPOSE a durable artifact (report-then-apply; the model
judges + proposes, this script ONLY counts — no proposal, no authoring here). A LIVE within-project scan with
NO persisted cross-dream tally (that is the deferred D1 recurrence family).

The `--json` CONTRACT (v0.1.55; +`scanned.secrets_omitted` v0.1.58): `{"window": <iso|"(all)">,
"scanned": {sessions, commands, days, secrets_omitted},
"recurring": [{template, count, days, sample}, ...], "chains": [{templates: [a, b], count, days}, ...]}`.
`recurring` = templates with `count >= MIN_RECUR`, ranked by (days, count) desc, capped at `MAX_RECUR_OUT`;
`chains` = adjacent kept-segment bigrams WITHIN one compound command (the `&&`/newline/`;`-glued sub-steps
of a workflow — NOT the multi-Bash-call arc, which the model recognizes from co-ranked rows), same
threshold/ranking, capped at `MAX_CHAIN_OUT`. `days` = distinct active days (the EPISODE dimension — ×27
across 9 days is a workflow; ×27 in one hour is a loop; rank is a hint, not a filter). `template` is the
normalized command CLASS; `sample` is ONE raw command (DISPLAY only — the model genericizes any absolute
path / machine value before ever authoring an artifact; see SKILL.md distill phase).

FIREWALL (v0.1.58 — at the EMISSION point; the audited v0.1.55 behavior dropped the whole command, which
silently un-counted ~5% of the measured corpus as false positives with zero transparency): a command-level
`_looks_secret(_norm(cmd))` hit now counts into `scanned.secrets_omitted` and STILL counts its templates —
but its raw text can never be a `sample` (a flagged command's new templates get an omission LABEL), and
`_seg_template` screens every EMITTED template through `_looks_secret` (the choke-point — covers rows AND
chain endpoints). Suppression keys off the ONE `_norm`-based command-level flag, never a re-probe of the
raw sample (a zero-width-split secret is caught by `_norm` but invisible to a raw re-probe).

`--into <seed>` (v0.1.58) injects the script-truth counts (`sessions/commands/n_recurring/n_chains/window/
secrets_omitted`) into the cycle-record seed's `distill` block via a sub-key MERGE — model-authored
`proposed`/`created`/`verdict` are preserved unless the matching `--verdict`/`--proposed`/`--created`
flags replace them (a provided list-flag replaces the WHOLE list — idempotent). Counts are script-ONLY:
the measured hand-mirror failure (a persisted `n_recurring: 47` against a hard cap of 40) is why.

Extraction (v0.1.55, order LOAD-BEARING): join `\\`-continuations → strip heredoc BODIES (FIRST — quote-strip
would delete a quoted tag: `<<'PY'` → `<<`, the proven spec-review B1 defect) → strip quoted strings →
segment on newline/&&/; → per-segment template with keyword handling (PREFIX-STRIP keywords that CARRY a
command: `do`/`then`/`else`/`{`/`!`/`eval`/`exec`; DROP-WHOLE the closed POSIX classes that cannot:
`done`/`fi`/…, control (`exit`/`break`/`continue`/`return`/`:`), test guards (`[`/`[[`/`test`),
env-manipulation (`set`/`trap`/…), assignment keywords (`export`/`declare`/… — they never carry a command),
and `for`/`if`/… condition heads) + a generic/investigation-verb stoplist + a structural interpreter rule
(any-path/any-runner `… python -c|-e|-` inline bodies are one-off scripts, not recurrence). A template
counts ONCE per command. Known residuals (accepted): `||` is not a separator — present in ~16% of measured
commands but low-HARM (only fallback arms are lost); a single `&` does not separate (`a & b` fuses); a
stoplisted-head PIPELINE hides its downstream tool (`cat x | tool`); `;`/`&&` inside a NESTED `$( $( ) )`
mis-segments (the flat case is removed); the FIRST one-line case arm is lost; a bridge-chain can span a
dropped control terminator (`a && break && b` → a→b, contrived-rare).

Reuses `extract_signals`' firewall/window/norm + `memory_status`' slug rule + `_write_private` — does NOT
re-implement them (the reimplementation-pin discipline).
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import _ui  # sibling: shared visual vocabulary
from extract_signals import _parse_ts, _PROBE_CAP, _looks_secret, _norm, _window_transcripts
from memory_status import _write_private, slug_for  # slug rule + 0o600-atomic seed write (house single-source)

MIN_RECUR = 2            # MiMo's bar: a workflow is a candidate only when it actually recurred (>=2x)
MAX_RECUR_OUT = 40       # cap the surfaced templates — the model judges; don't flood the phase
MAX_CHAIN_OUT = 20       # v0.1.55: cap the surfaced chains (same rationale)
# v0.1.82 (W-A, docs/distill-template-persistence.spec.md): how many top rows PERSIST into the cycle
# record (top templates, chains) + the Skill-adoption tally cap. Deliberately far below the surfacing
# caps — the log line is appended every dream forever; fleet joins (W-B) need only the head. Mirrored
# by memory_status._DISTILL_PERSIST_CAP/_DISTILL_USED_CAP (smoke-pinned, the _DISTILL_CAPS pattern).
_DISTILL_PERSIST_CAP = (12, 8)
_USED_CAP = 12
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
# v0.1.58: the REMAINING closed POSIX classes join (the audit's live top-40 carried `[ = ]`/`}`/`continue`/
# `exit 1` junk rows + an `exit 1 → }` junk chain — enumerate-by-idiom rots; POSIX syntax closes):
#   PREFIX-STRIP gains `{` (brace-group opener carries: `{ real-tool run`), `!` (the negated command still
#   executes; the stoplist then applies), `eval`/`exec` (they exec their argument — with an fd-plumbing
#   guard: a post-strip remainder opening with a digit or `<` is `exec 2>&1`/`exec 3< f`, not a command).
#   DROP-WHOLE gains `}` + control (`exit`/`break`/`continue`/`return`/`:` — args irrelevant: `exit 1` is
#   control flow, never a workflow row), env-manipulation (`set`/`shopt`/`trap`/`unset`/`umask`/`ulimit`/
#   `shift`), and the assignment KEYWORDS (`export`/`local`/`declare`/`typeset`/`readonly` — POSIX: they
#   take names/assignments, NEVER a command; drop-whole both kills the measured value-retention
#   (`export CM_FLAG=on` templated WITH its value) and avoids the junk a prefix-strip would open
#   (`export PATH` → a bare `PATH` row — proven in spec review).
#   HEAD-DROP gains the test guards `[`/`[[`/`test` (a condition, not a command; `[ -d x ] && cmd` keeps
#   `cmd`, and the bridge-chain spans the dropped guard — pinned).
_KW_PREFIX = {"do", "then", "else", "{", "!", "eval", "exec"}    # strip the keyword, re-template the remainder
_FD_GUARDED = {"eval", "exec"}                               # a post-strip fd-redirect remainder = plumbing → drop
# An fd-REDIRECT remainder (`exec 2>&1`, `exec 3< f`, `exec >log`, `exec &>log`): an optional fd number then a
# redirect operator. Must NOT match a digit-NAMED command (`exec 7z x a.zip`, `eval 2to3 -w src`) — the naive
# `seg[0].isdigit()` guard false-dropped those (code-review [3]): `7z` is `\d+` then a LETTER, not `[<>&]`.
_FD_REDIR = re.compile(r"^(?:\d+)?[<>&]")
_KW_DROP = {"done", "fi", "esac", "}",
            "exit", "break", "continue", "return", ":",
            "set", "shopt", "trap", "unset", "umask", "ulimit", "shift",
            "export", "local", "declare", "typeset", "readonly"}  # keyword/control/assignment noise → drop whole
_KW_HEAD_DROP = {"for", "while", "if", "case", "elif", "until",
                 "[", "[[", "test"}                          # condition/iterator/guard heads, not commands → drop whole
# v0.1.58: the v0.1.55 interpreter stoplist pinned exact SPELLINGS (`python3 -`), so the false class
# regenerated under any other spelling — measured `.venv/bin/python -` ×204 + `-c` ×95 on the job corpus.
# The structural rule: an inline-body carrier (`… <interp> -|-c|-e`) or a BARE interpreter, matched by the
# token's BASENAME so any path (`/usr/bin/python3`, `.venv/bin/python`) or runner (`uv run python -`,
# `docker run img python -c` — intentionally the same one-off class) is caught. Runs on the POST-TRUNCATION
# SEGMENT tokens (BEFORE the 5-token transform drops abs-path heads — on finalized template tokens
# `/usr/bin/python3 -c` has already lost its head and would leak a bare `-c` row; proven in spec review).
_INTERP = re.compile(r"^(?:python\d*(?:\.\d+)?|pypy\d?|node|deno|bun|ruby|perl|php|bash|sh|zsh|dash|ksh)$")
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


def _day_str(dt: "datetime | None", raw: str) -> str:
    """A parsed instant (+ its raw string, for the fallback) → the UTC calendar date (the episode-day unit),
    or the raw 10-char slice when unparseable, or '' when empty. The SINGLE day-formatting expression —
    `_day_of` and `scan()` both call it (scan passing its already-parsed `ts_dt` to dodge a re-parse), so
    the two can't drift (code-review [7])."""
    return dt.date().isoformat() if dt else (raw[:10] if raw else "")


def _day_of(ts: str) -> str:
    """A transcript timestamp → its UTC calendar date (the episode-day unit). UTC is chosen for
    DETERMINISM: an earlier LOCAL-tz conversion made `scanned.days`/per-row `days` — and thus the
    (days, count) ranking the model reads — depend on the RUNNER's timezone, so the same repo rendered a
    different distill signal on a UTC server vs a local laptop (round-3 finding). The tradeoff (a single
    sitting straddling UTC midnight counts as 2 days) is cosmetic — `days` is an advisory rank hint, not a
    filter. Falls back to the raw slice on unparseable input; '' stays '' (no day accrues)."""
    return _day_str(_parse_ts(ts), ts)


def _seg_template(seg: str) -> str | None:
    """ONE (already quote-stripped) segment → its recurring CLASS template, or None if it is noise:
    pure cd/bare-assignment, a keyword-only/condition/control/guard/assignment-keyword segment, a
    stoplisted head, a structural interpreter inline-body, a purely-numeric residue, or a secret-shaped
    emission. Prefixes that CARRY a command are stripped and the remainder templated: `do`/`then`/`else`/
    `{`/`!`/`eval`/`exec` keywords (M2 + round-2 + v0.1.58), case-arm heads (`start) run-server` →
    `run-server`), and env assignments (`CM_DREAM_ARC=1 python3 …` → `python3 …`). The cd/assignment
    noise gate runs AFTER the prefix strips (round-2: `do cd $d` must drop, not leak a `cd` row)."""
    seg = seg.strip().strip("()").strip()            # subshell fragments: `( cmd && x )` splits to
    #                                                  `( cmd` / `x )` → shed the orphan grouping parens
    if not seg:
        return None
    parts = seg.split(None, 1)
    while parts and parts[0] in _KW_PREFIX:          # `do mypy $f` / `else rollback.sh` / `{ real-tool run`
        kw = parts[0]                                # → keep the carried command (stackable: `! { cmd`)
        seg = parts[1].strip() if len(parts) > 1 else ""
        if not seg:
            return None
        if kw in _FD_GUARDED and _FD_REDIR.match(seg):
            return None                              # `exec 2>&1` / `exec 3< file` — fd plumbing, not a command
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
    # v0.1.58: the structural interpreter rule — on the POST-TRUNCATION segment tokens, BEFORE the
    # transform loop below drops abs-path heads (see _INTERP rationale). Bare interpreter (any path) or
    # an inline-body carrier tail (`… <interp> -|-c|-e`). `git commit -q -F -` survives (toks[-2] `-F`).
    toks = seg.split()
    if toks:
        if len(toks) == 1 and _INTERP.match(toks[0].rsplit("/", 1)[-1]):
            return None
        if toks[-1] in ("-", "-c", "-e") and len(toks) >= 2 and _INTERP.match(toks[-2].rsplit("/", 1)[-1]):
            return None
    out: list[str] = []
    for tok in toks:                                 # reuse the split from the interpreter check (code-review [8])
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
    if re.fullmatch(r"\d+", tpl):                    # v0.1.58: numeric plumbing residue is never a class
        return None
    if _looks_secret(_norm(tpl)):                    # v0.1.58: the EMISSION choke-point — one screen covers
        return None                                  # rows AND chain endpoints (chains derive from kept tpls).
    #   Probe the _norm'd template, matching the command-level flag: a zero-width-split credential is fused
    #   by _norm (Cf-stripped) so it can't slip a raw-probe miss into a template row (code-review [1]).
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


_OMIT_SAMPLE = "(sample omitted — credential-shaped command)"


def scan(project_dir: Path, since: str) -> dict:
    """Count recurring Bash-command templates + intra-command chains across the project's in-window
    transcripts, with per-item day-spread (the episode dimension). `since` empty → all (matches
    `_window_transcripts`); the CLI defaults it to ~30 days, and v0.1.58 adds the PER-LINE window skip —
    an INSTANT compare (`_parse_ts(ts) <= _parse_ts(since)`, not a raw-string compare, so a local-offset
    `--since` can't mis-order against CC's `Z` stamps), so a long-lived session file no longer leaks
    out-of-window lines into counts/day-spreads. FIREWALL (v0.1.58): the
    command-level `_looks_secret(_norm(cmd))` hit gates the SAMPLE and counts into `secrets_omitted` —
    the command's templates still count, each screened at emission by `_seg_template` (see module doc)."""
    project_dir = project_dir.resolve()
    proj_root = Path.home() / ".claude" / "projects" / slug_for(project_dir)
    transcripts = _window_transcripts(proj_root, since)
    since_dt = _parse_ts(since) if since else None   # compare INSTANTS, not raw strings (code-review [2])
    counts = {"sessions": len(transcripts), "commands": 0, "days": 0, "secrets_omitted": 0}
    days_seen: set = set()
    tally: dict[str, dict] = {}          # template -> {count, days, sample}
    ctally: dict[tuple, dict] = {}       # (a, b) -> {count, days}
    used_tally: dict[str, int] = {}      # v0.1.82 (W-A): Skill invocations by name — the ADOPTION
    #   denominator the workflow lifecycle loop needs (did a created skill displace its raw commands?).
    #   Accrued per-window NOW or lost to transcript rotation — the exact pre-Phase-A usage lesson.
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
                ts = str(o.get("timestamp") or "")
                ts_dt: "datetime | None" = None   # parsed LAZILY on the first Bash part (a Read/Edit-only
                ts_done = False                   # message — the session majority — never parses a timestamp),
                #   yet the window is enforced per-COMMAND before it counts. `ts_done` memoises the parse.
                day = None
                for p in content:
                    if not (isinstance(p, dict) and p.get("type") == "tool_use"):
                        continue
                    if p.get("name") == "Skill":
                        # v0.1.82 (W-A): the adoption tally — same per-line window rule as Bash below.
                        if not ts_done:
                            ts_dt = _parse_ts(ts); ts_done = True
                        if since_dt and ts_dt and ts_dt <= since_dt:
                            break
                        _sk = str((p.get("input") or {}).get("skill", "") or "")
                        if _sk:
                            used_tally[_sk] = used_tally.get(_sk, 0) + 1
                        continue
                    if p.get("name") != "Bash":
                        continue
                    cmd = str((p.get("input") or {}).get("command", ""))
                    if not cmd:
                        continue
                    if not ts_done:
                        ts_dt = _parse_ts(ts); ts_done = True
                    if since_dt and ts_dt and ts_dt <= since_dt:   # per-line window (file mtime over-included);
                        break                                      # all parts share this line's ts → skip them all
                    # v0.1.58 firewall-at-emission: the ONE command-level flag drives the sample suppression
                    # AND the transparency counter — incremented HERE (before commands++/the all-noise skip:
                    # the measured majority of flagged commands are all-noise `export SECRET=…` shapes that
                    # a later increment would never count). The command still scans; templates are screened
                    # at emission (_seg_template). Never re-probe the raw sample — a zero-width-split secret
                    # is caught by _norm here but invisible to a raw re-probe.
                    flagged = _looks_secret(_norm(cmd)[:_PROBE_CAP])
                    if flagged:
                        counts["secrets_omitted"] += 1
                    if day is None:
                        day = _day_str(ts_dt, ts)       # the shared formatter; ts_dt already parsed above
                        if day:
                            days_seen.add(day)
                    counts["commands"] += 1
                    templates, chains = _scan_cmd(cmd)
                    if not templates and not chains:
                        continue                                # all-noise command — don't build a sample for nothing
                    for t in templates:
                        rec = tally.get(t)
                        if rec is None:                         # new template: seed its sample (label if flagged)
                            rec = tally[t] = {"count": 0, "days": set(),
                                              "sample": _OMIT_SAMPLE if flagged else " ".join(cmd.split())[:160]}
                        elif not flagged and rec["sample"] == _OMIT_SAMPLE:
                            rec["sample"] = " ".join(cmd.split())[:160]   # upgrade a placeholder once a clean
                            #   occurrence of the SAME class exists — arrival order no longer strands it (code-review [8])
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
    used_out = [{"a": k, "n": v} for k, v in
                sorted(used_tally.items(), key=lambda kv: (-kv[1], kv[0]))[:_USED_CAP]]
    return {"window": since or "(all)", "scanned": counts, "recurring": recurring, "chains": chains_out,
            "used": used_out}


def _report(d: dict) -> None:
    c = d["scanned"]
    out: list = []
    add = out.append
    title = "✦ DISTILL · recurring workflow signal"
    tag = f"{len(d['recurring'])} template(s) · {len(d.get('chains', []))} chain(s)"
    gap = max(2, _ui.W - 2 - len(title) - len(tag))
    add(_ui.rule())
    add("  " + _ui.c("✦", "cyan") + title[1:] + " " * gap + _ui.c(tag, "bold"))
    _sec = f" · {c['secrets_omitted']} secret-shaped (samples omitted)" if c.get("secrets_omitted") else ""
    add("  " + _ui.c(f"{c.get('sessions', 0)} session(s) · {c.get('commands', 0)} Bash cmds · "
                     f"{c.get('days', 0)} active day(s){_sec} · window {d['window']}", "dim"))
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


def inject_into(seed_path: str, d: dict, verdict: str, proposed: list, created: list) -> bool:
    """v0.1.58: deterministically inject the SCRIPT-TRUTH distill counts into the cycle-record seed —
    the capture's counts are script-ONLY (the measured hand-mirror failure: a persisted `n_recurring: 47`
    against a hard cap of 40). A sub-key MERGE, deliberately NOT the audit `--into` wholesale assignment
    (the distill block is split-ownership): counts/window/secrets_omitted overwrite; model-authored
    `proposed`/`created`/`verdict` are preserved UNLESS the matching flag was given (a provided flag
    REPLACES its key; a provided list-flag replaces the WHOLE list — idempotent on re-run). Never crashes
    (missing/corrupt/non-object seed → one stderr line, returns False) — but because the hand-mirror
    fallback was DELETED, a False is a real capture loss with no recovery, so `main` surfaces it as a
    non-zero exit (code-review [6]); all messaging is on stderr so `--json` stdout stays pure."""
    try:
        record = json.loads(Path(seed_path).read_text(encoding="utf-8"))
        if not isinstance(record, dict):
            print("--into: skipped (cycle record root is not a JSON object)", file=sys.stderr)
            return False
        blk = record.get("distill")
        blk = blk if isinstance(blk, dict) else {}
        # DEFENSIVE reads — a fresh scan always carries every key, but a `--from` file can be a stale
        # (pre-v0.1.58, no `secrets_omitted`) or hand-edited scan that passed the shape gate; `.get` with
        # defaults keeps a partial-but-valid scan working instead of a KeyError crash + lost capture ([0]).
        sc = d.get("scanned")
        sc = sc if isinstance(sc, dict) else {}
        blk.update({"sessions": sc.get("sessions", 0), "commands": sc.get("commands", 0),
                    "n_recurring": len(d.get("recurring") or []), "n_chains": len(d.get("chains") or []),
                    "window": d.get("window", "(all)"), "secrets_omitted": sc.get("secrets_omitted", 0)})
        # v0.1.82 (W-A): persist the TOP rows — projected to compact {t,n,d}, deliberately WITHOUT
        # `sample` (samples carry raw command text and stay display-only: the privacy tier the module
        # doc pins). Script-truth like the counts; template-level evidence used to DIE with each scan,
        # making fleet aggregation (W-B --workflows) impossible — the exact pre-Phase-A usage mistake.
        # PR-#95 review hardening (all three findings fire only on hand-edited/pre-v0.1.82 --from
        # files; the dream path is unaffected): values COERCED per row (t clamped [:200] — the durable
        # "compact" contract is on VALUES, not just keys; n/d int-or-0, handing W-B clean types), a
        # chain row whose `templates` isn't a list is SKIPPED (the old bare list() was a poison pill:
        # one bad row TypeError'd the WHOLE injection — capture loss — and a string char-split into
        # garbage), and `used` is written ONLY when the scan measured it (an old scan yielding
        # `used: []` would register a FALSE "measured, zero invocations" window in W-B's adoption
        # view — absent-vs-empty honesty, the usage_history discipline).
        def _i(v: object) -> int:
            return v if isinstance(v, int) and not isinstance(v, bool) and v >= 0 else 0
        blk["top"] = [{"t": str(r.get("template", ""))[:200], "n": _i(r.get("count")), "d": _i(r.get("days"))}
                      for r in (d.get("recurring") or [])[:_DISTILL_PERSIST_CAP[0]] if isinstance(r, dict)]
        blk["top_chains"] = [{"t": [str(x)[:200] for x in r["templates"]], "n": _i(r.get("count")), "d": _i(r.get("days"))}
                             for r in (d.get("chains") or [])[:_DISTILL_PERSIST_CAP[1]]
                             if isinstance(r, dict) and isinstance(r.get("templates"), list)]
        if "used" in d:
            blk["used"] = [{"a": str(r.get("a", ""))[:200], "n": _i(r.get("n"))}
                           for r in (d.get("used") or []) if isinstance(r, dict)][:_USED_CAP]
        if verdict:
            blk["verdict"] = verdict
        if proposed:
            blk["proposed"] = proposed
        if created:
            blk["created"] = created
        record["distill"] = blk
        _write_private(Path(seed_path), json.dumps(record, indent=2, ensure_ascii=False) + "\n")
        print(f"distill → injected into {seed_path}", file=sys.stderr)
        return True
    except (OSError, json.JSONDecodeError, ValueError, TypeError, KeyError) as e:
        print(f"--into: skipped ({e}); the scan output above is the fallback", file=sys.stderr)
        return False


# CLI flags this script OWNS. Value-taking flags consume the next argv slot; `--from` feeds a saved scan
# JSON (single-scan capture — code-review [10]); the visual flags are consumed by _ui from sys.argv. A
# genuinely unknown flag, or a value-flag missing its value, is a USAGE ERROR (exit 2 — consistent with
# garbage `--since`), never a swallowed value that becomes a wrong-dir 0-session scan (audit F8 / [4]/[7]).
_VALUE_FLAGS = ("--since", "--into", "--from", "--verdict", "--proposed", "--created")
_VISUAL_FLAGS = ("--ascii", "--color", "--no-color")


def main() -> int:
    argv = sys.argv[1:]
    as_json = "--json" in argv
    argv = [a for a in argv if a != "--json"]
    _ui.set_modes(color=_ui.color_enabled(sys.argv[1:], sys.stdout), ascii="--ascii" in sys.argv, width=_ui.resolve_width(sys.argv[1:], sys.stdout))
    since = into = from_path = verdict = ""
    proposed: list = []
    created: list = []
    pos = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in _VALUE_FLAGS:
            if i + 1 >= len(argv):                       # a trailing value-flag (its value lost) is a usage
                print(f"{a} requires a value", file=sys.stderr)  # error, not an "unknown flag" (code-review [4])
                return 2
            v = argv[i + 1]
            if a == "--since":
                since = v
            elif a == "--into":
                into = v
            elif a == "--from":
                from_path = v
            elif a == "--verdict":
                verdict = v
            elif a == "--proposed":
                proposed.append(v)
            else:
                created.append(v)
            i += 2
        elif not a.startswith("-"):
            pos.append(a); i += 1
        elif a in _VISUAL_FLAGS or a.startswith(("--color=", "--width=")):
            i += 1                                       # visual flags are handled by _ui.set_modes
        else:
            print(f"unknown flag: {a}", file=sys.stderr)  # exit 2, not a swallowed value → wrong scan ([7])
            return 2
    if (verdict or proposed or created) and not into:    # judgment flags go nowhere without --into: warn LOUD
        print("warning: --verdict/--proposed/--created require --into — not captured", file=sys.stderr)  # [5]
    if from_path:                                        # single-scan capture: inject a SAVED scan (code-review [10])
        try:
            d = json.loads(Path(from_path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, ValueError) as e:
            print(f"--from: cannot read {from_path} ({e})", file=sys.stderr)
            return 2
        if not (isinstance(d, dict) and isinstance(d.get("scanned"), dict)
                and isinstance(d.get("recurring"), list) and isinstance(d.get("chains"), list)):
            print(f"--from: {from_path} is not a distill scan JSON", file=sys.stderr)
            return 2
    else:
        if since:
            if _parse_ts(since) is None:                 # validate BEFORE the instant compare (garbage → drop-all)
                print(f"--since expects an ISO timestamp, got {since!r}", file=sys.stderr)
                return 2
        else:  # default to a recent window (BROADER than the dream's marker..HEAD; recurrence needs episodes)
            since = (datetime.now(timezone.utc) - timedelta(days=DEFAULT_WINDOW_DAYS)).isoformat()
        project_dir = Path(pos[0]) if pos else Path.cwd()
        if not project_dir.is_dir():  # visible, recall-safe (the scan proceeds and prints zeros)
            print(f"warning: project dir does not exist: {project_dir}", file=sys.stderr)
        d = scan(project_dir, since)
    if as_json:
        print(json.dumps(d, indent=2))
    elif not from_path:                                  # --from is a capture-only mode; no report to re-print
        _report(d)
    rc = 0
    if into and not inject_into(into, d, verdict, proposed, created):
        rc = 1                                           # capture failure is detectable by exit code (code-review [6])
    # v0.1.54: write-time dream-arc cue (stderr, CM_DREAM_ARC-gated — see _ui.dream_cue)
    _ui.dream_cue("distill beat due — recurring gestures condensing (plain italics, no emoji) "
                  "above the plain scan results")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
