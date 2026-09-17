#!/usr/bin/env python3
"""dream_procedure.py — the conversation-truth detector (v0.4.19).

The persist gates v0.4.1 shipped are RECORD-side: they read what the record says about itself
(procedure integrity, dream-arc completeness). A THIRD joined them in v0.4.33 — record-duty
presence, a field the pass seeded and left unfilled (`render_dashboard`'s persist path, spec
`docs/record-duty-presence.spec.md`) — and it is record-side by this paragraph's own test: it reads
the record and nothing else. The measured 2026-09-06 defect class is the conversation side: the
record's dream block was filled AT record-fill instead of narrated in the
session, and Phase 2's extractor never ran with no skip note — both invisible to any record-side
gate, because the record is self-reported data.

This module adds the ground truth the terminal `render_dashboard --persist` can actually see: the
dream's own session transcript (the JSONL extract_signals already reads). Two arms:

  NAR — narration verification. Every checked text in the record's dream block (the `dream.sleep`
        stanza + the six `dream.beats` entries, record indexes 0-5; the surfacing line is the
        last beats entry, WAKE is post-persist and unchecked) must appear verbatim-normalized in
        an ASSISTANT TEXT BLOCK of the in-window transcript. The match domain is text blocks
        ONLY — never tool_use.input, never tool_result: the record-fill Write/Edit's input
        carries the full dream block and its tool_result echoes the file content, both inside
        the window; counting them would self-satisfy the exact fabrication this detector exists
        to catch. Thinking blocks never count.
  EXT — extractor accountability. The in-window transcript must contain an EXECUTED
        extract_signals.py invocation in the Phase-2 form (--json or the human table; --recalls
        does not count) or an entries[] row whose reason begins with the canonical
        `extractor-skip:` marker + a non-empty why (a fixed token, never free-form prose).

Degrade (the honest case): a window with ZERO kept transcript lines (missing/unreadable
transcript — headless runner, early rotation) cannot be verified — BOTH arms degrade loudly and
NEVER hard-block (teeth-loss-never-clean: the absence is stated, never silent; the record's
`narration` block persists the verdict so a degraded pass never reads as verified later).

Window scoping: `since` = the record's Phase-0-seeded `marker.before_timestamp` — NEVER the
state file at persist time (Phase-5 step 5 re-stamps it before --persist runs, so a
persist-time state-file read would yield an empty window on every real pass). The caller passes
it in; this module never reads the state file.

Exit integration (the caller's ladder): NAR gaps -> exit 4 (the arc's conversation-side arm);
EXT unaccounted -> exit 3; both -> 3 (the existing key); record-side verdicts own their renders
first. Degraded/verified -> no exit change. Known ceilings (documented, not solved): the check
verifies PRESENCE of narration text and calls — conversation-truth, not performed-truth (the
coordinated-fabrication burst), and exact containment assumes the mirroring model pastes
verbatim (a lightly-rewording model would false-fire — cheap to fix: narrate and re-render).

Design-of-record: docs/dream-narration-teeth.spec.md (amend-3, review-to-zero).
"""

from __future__ import annotations

import json
import re
import shlex
import time
from pathlib import Path
from typing import Any, Callable, Optional

from distill_scan import _strip_heredocs   # the ONE heredoc rule (see _normalize's docstring)

_EXTRACTOR_TOKEN = "extract_signals.py"
_SKIP_MARKER = "extractor-skip:"
# The EXECUTION anchor (v0.4.29; spec §2.3 of docs/dream-teeth-coverage.spec.md). The single
# regex this replaces could not tell an execution from a string SHAPE: it anchored `python3` on
# ANY whitespace, so `echo python3 …/extract_signals.py --json`, `python3 -m py_compile …` and a
# heredoc merely *writing* the token were all accounted — a silent EXT pass on a pass that never
# ran the extractor. The anchor is now the structure the docstring always claimed: unfold →
# strip heredoc bodies → strip comments → split into top-level segments → shlex.split → decide on
# the TOKENS.
#
# DIRECTION OF ERROR (corrected in review — the first cut had this backwards). A form the anchor
# cannot parse is UNACCOUNTED: a loud exit 3 the model sees, reports, and can repair by re-running
# the extractor plainly. A form it parses too generously is a SILENT clean on a pass that never
# ran the extractor. For a verification gate the silent direction is the worse one — the spec's
# own tie-break is "Uncertain → fire" and its own words are "a false clean is permanent and
# invisible" — so every rule below is written to under-account rather than over-account, and each
# widening below carries the measurement that justified it.
#
# The wrapper set is BOUNDED, and the bound is the design. Each entry carries the wrapper's own
# argument grammar, because a wrapper is not a bare keyword: `timeout 300 python3 …` parks a
# positional DURATION between the wrapper and the command, `sudo -u root` and `nice -n 10` park a
# VALUE after a flag, while `stdbuf -oL` and `xargs -I{}` do not. Skipping flags alone (the first
# cut's rule) accounted NONE of those. Measured over the form set the spec's §2.3 table pins, the
# first cut dropped 12 forms and the rules below account all 12: `timeout`/`nice`/`stdbuf`/`flock`
# (wrapper absent from the set) · their positional operand (`timeout 300 …`, `flock /tmp/l …`) ·
# their value flags (`nice -n 10`, `sudo -u root`, `timeout -s KILL 5`) · a `(`-fused subshell ·
# a `then`/`do`-led segment · a `{ …; }` group · an apostrophe inside a `#` comment ·
# a Windows backslash path.
#
# wrapper -> (flags that CONSUME the next token as their value, leading positional operands)
_WRAPPER_GRAMMAR = {
    "env":     (frozenset(("-u", "-C", "-S", "--unset", "--chdir",
                           "--split-string")), 0),   # env -u FOO cmd / env -C /tmp cmd
    "time":    (frozenset(), 0),      # time cmd / time -p cmd
    "nohup":   (frozenset(), 0),
    "command": (frozenset(), 0),      # command -v cmd
    "exec":    (frozenset(), 0),
    "setsid":  (frozenset(), 0),
    "nice":    (frozenset(("-n", "--adjustment")), 0),
    "stdbuf":  (frozenset(("-i", "-o", "-e", "--input", "--output", "--error")), 0),
    "ionice":  (frozenset(("-c", "-n", "-p", "-u")), 0),
    "xargs":   (frozenset(("-I", "-n", "-P", "-s", "-L", "-a", "-d", "-E")), 0),
    "sudo":    (frozenset(("-u", "-g", "-p", "-C", "-h", "-r", "-t", "-U",
                           "--user", "--group")), 0),
    "timeout": (frozenset(("-s", "-k", "--signal", "--kill-after")), 1),   # … 300 cmd
    "flock":   (frozenset(("-w", "-E", "-o", "--wait", "--conflict-exit-code")), 1),  # … /tmp/l cmd
}
_WRAPPERS = frozenset(_WRAPPER_GRAMMAR)
_INTERPRETERS = frozenset(("python3", "python"))
# Tokens that CARRY a command without being one: the shell's grouping/control prefixes. A subset
# of distill_scan._KW_PREFIX (`do`/`then`/`else` proven there; `{`/`!`/`eval` joined with it) —
# `exec` is NOT here even though that set has it, because `exec` is a wrapper in THIS module with
# a grammar to walk (`exec -a NAME python3 …`), and a bare prefix-skip would drop its flags.
# `(` is this module's own addition: distill_scan folds it in via `seg.strip("()")`, which an
# execution test cannot use — that would also erase the grouping from a legitimate subshell form.
#
# A leading `(`/`{` FUSES with the next word under `shlex.split(posix=True)` (punctuation_chars
# is off by default), so `(python3` arrives as ONE token whose basename is `(python3` — not an
# interpreter. `_lead` strips those grouping characters from the head token for that reason;
# the space-separated spellings (`then python3 …`) are the token set below.
_PREFIX_TOKENS = frozenset(("do", "then", "else", "{", "!", "eval", "("))
# A Windows drive path. POSIX `shlex(posix=True)` eats each `\` as an escape, so the separator
# that makes `…\scripts\extract_signals.py` an invocation disappears before the token test sees
# it — measured, the whole form went unaccounted. Normalizing `C:\a\b` → `C:/a/b` BEFORE tokenizing
# restores it. The span is matched by SHAPE, not by context, so the rewrite is not confined to
# paths: measured, `_unfold(r"sed -e 's/a:\.*/b/'")` rewrites the `a:\` inside the quotes. That is
# harmless here because the result feeds only the token test, and a `\` the token test would have
# eaten anyway cannot make an invocation appear or vanish.
_WINPATH = re.compile(r"([A-Za-z]:)\\([^\s\"']*)")


def _unfold(cmd: str) -> str:
    """Remove backslash-newline continuations — the shell's own rule, not a whitespace
    substitution — so a command wrapped across lines is ONE segment and a path split *inside
    quotes* by a continuation rejoins (`…/scripts/\\<newline>extract_signals.py`)."""
    return _WINPATH.sub(lambda m: m.group(1) + "/" + m.group(2).replace("\\", "/"),
                        cmd.replace("\\\n", ""))


def _strip_comments(cmd: str) -> str:
    """Remove shell comments so an apostrophe INSIDE one cannot unbalance a quote. Measured: a
    trailing `# don't re-run this` made `shlex.split` raise, which the caller reads as "Uncertain
    → fire" — correctly, but it was firing on a legitimate, fully-executed call.

    `#` opens a comment only at the START OF A WORD (`foo#bar` is one word in bash) and outside
    quotes, which is what the `at_word_start` flag tracks."""
    out: list[str] = []
    quote = ""
    at_word_start = True
    i = 0
    while i < len(cmd):
        ch = cmd[i]
        if quote:
            out.append(ch)
            if ch == "\\" and quote == '"' and i + 1 < len(cmd):
                out.append(cmd[i + 1])
                i += 2
                continue
            if ch == quote:
                quote = ""
            i += 1
            continue
        if ch in ("'", '"'):
            quote = ch
            out.append(ch)
            i += 1
            at_word_start = False
            continue
        if ch == "\\" and i + 1 < len(cmd):
            out.append(cmd[i:i + 2])
            i += 2
            at_word_start = False
            continue
        if ch == "#" and at_word_start:
            while i < len(cmd) and cmd[i] != "\n":
                i += 1
            continue
        out.append(ch)
        at_word_start = ch in " \t\n;|&("
        i += 1
    return "".join(out)


def _normalize(cmd: str) -> str:
    """The pre-segmentation normalization, in the order distill_scan pinned for the same job
    (B1: unfold continuations → strip heredoc BODIES → then the rest). The heredoc rule is
    IMPORTED, not re-implemented: two copies of one rule drifting apart is the defect class this
    whole cycle is about, and `_strip_heredocs` is a pinned, terminated-heredoc-only rule that
    never amputates on a stray `<<`."""
    return _strip_comments(_strip_heredocs(_unfold(cmd)))


def _segments(cmd: str) -> list[str]:
    """Split a command at its UNQUOTED top-level separators: `;` `&&` `||` `|` and newlines. A
    separator inside quotes (or escaped) is literal. `&` is deliberately NOT split here — it is
    decided at TOKEN granularity (_split_amp), because a character split would truncate
    `python3 <tok> --json 2>&1` to `…2>` and lose a legitimate call."""
    out: list[str] = []
    buf: list[str] = []
    quote = ""
    i = 0
    while i < len(cmd):
        ch = cmd[i]
        if quote:
            buf.append(ch)
            if ch == "\\" and quote == '"' and i + 1 < len(cmd):
                buf.append(cmd[i + 1])   # a \" inside double quotes is not the closing quote
                i += 2
                continue
            if ch == quote:
                quote = ""
            i += 1
            continue
        if ch in ("'", '"'):
            quote = ch
        elif ch == "\\" and i + 1 < len(cmd):
            buf.append(cmd[i:i + 2])     # an escaped separator is data, never a split point
            i += 2
            continue
        elif ch == "\n" or ch == ";":
            out.append("".join(buf)); buf = []; i += 1; continue
        elif ch == "|":
            step = 2 if cmd[i:i + 2] == "||" else 1
            out.append("".join(buf)); buf = []; i += step; continue
        elif ch == "&" and cmd[i:i + 2] == "&&":
            out.append("".join(buf)); buf = []; i += 2; continue
        buf.append(ch)
        i += 1
    out.append("".join(buf))
    return [s for s in out if s.strip()]


def _split_amp(tokens: list[str]) -> list[list[str]]:
    """Split a token list at a standalone `&` token — the background operator, and the only form
    that separates. `2>&1` arrives as ONE token, so redirections survive."""
    out: list[list[str]] = []
    cur: list[str] = []
    for t in tokens:
        if t == "&":
            if cur:
                out.append(cur)
            cur = []
        else:
            cur.append(t)
    if cur:
        out.append(cur)
    return out


def _lead(tok: str) -> str:
    """The token with any LEADING shell grouping character removed — `(python3` → `python3`.
    Only the head characters are touched, so a path or flag that merely CONTAINS one is intact."""
    return tok.lstrip("({!")


def _runs_extractor(tokens: list[str]) -> bool:
    """True iff this token list EXECUTES the extractor (spec §2.3 step 4). Walks past a leading
    prefix of `VAR=VALUE` env assignments (`CM_DREAM_ARC=1 python3 …`, the SKILL's own Phase-2
    form), the shell's grouping/control prefixes, and wrapper commands from the bounded set
    together with their OWN argument grammar (`sudo -n`, `xargs -I{}`, `sudo -u root`,
    `timeout 300`). The next token's basename must be the interpreter; the remainder must carry
    no `-c`, no `-m` and no `--recalls` — matched on the PREFIX, so the attached spelling counts
    (`-c'import os'` / `-mjson.tool` / `--recalls=3` arrive as single tokens) — because the first
    two consume the following token as *code* or as a *module name* (an extractor path inside them
    is a string, never the thing python runs) and the third is the recall-only mode, not the
    Phase-2 extract. Finally the extractor must be the FIRST operand after the interpreter — the
    script python actually runs, not any token in argv (`python3 other.py <path>` hands the path
    to another script) — and it must EQUAL the token or end with `/` + it: the separator
    requirement is what keeps `tools/extract_signalsXpy` and `tests/test_extract_signals.py`
    unaccounted.

    Every widening here is measured (spec §2.3's table): each one closed a form that the first cut
    dropped, and a drop is a LOUD false exit 3 on a legitimate call. Nothing was relaxed in the
    generous direction — the unaccounted verdicts this function returns are unchanged."""
    i, n = 0, len(tokens)
    while i < n:
        raw = tokens[i]
        if raw in _PREFIX_TOKENS:
            i += 1                        # the SPACE-separated spelling — `then python3 …`
            continue
        tok = _lead(raw)                  # …or the fused one, `(python3`
        base = tok.rsplit("/", 1)[-1]
        if base in _INTERPRETERS:
            rest = tokens[i + 1:]
            # `-c`/`-m`/`--recalls` are matched on their PREFIX, not by exact membership: the
            # attached spelling (`-c'import os'`, `-mjson.tool`, `--recalls=3`) arrives from
            # shlex as ONE token, and an exact-membership test credited all three. Measured
            # pre-fix at the judged surface: `python3 -c'import os' <path>` and
            # `python3 -mjson.tool <path>` both read `verified · ext_unaccounted False` — the
            # SILENT direction, which is the one this anchor exists to close.
            if any(t.startswith(("-c", "-m", "--recalls")) for t in rest):
                return False
            # …and the extractor must be the thing python RUNS, not merely present in argv:
            # `python3 other.py <path>` hands the path to another script as an argument. The
            # first non-option operand is that script (an interpreter option like `-u`/`-O` is
            # skipped; one that CONSUMES a value, `-X importtime`, then under-accounts — the
            # loud direction, and no Phase-2 form spells it that way).
            for t in rest:
                if t.startswith("-"):
                    continue
                return t == _EXTRACTOR_TOKEN or t.endswith("/" + _EXTRACTOR_TOKEN)
            return False
        if base in _WRAPPERS:
            value_flags, positionals = _WRAPPER_GRAMMAR[base]
            i += 1
            while i < n and tokens[i].startswith("-"):
                # The wrapper's own FLAGS, each with its VALUE where one is consumed
                # (`sudo -u root`, `nice -n 10`, `timeout -s KILL`). Flags come first because a
                # value is not always flag-shaped: `timeout -s KILL 5 python3 …` would otherwise
                # spend the positional slot on `-s` and read `KILL` as the command word.
                flag = tokens[i]
                i += 1
                if flag in value_flags and i < n:
                    i += 1
            while i < n and positionals > 0:
                # …then the wrapper's POSITIONAL operand — `timeout 300 python3 …`,
                # `flock /tmp/l python3 …`. This is what the first cut dropped outright:
                # `timeout` was not even in the set, and `300` was read as the command word,
                # so the whole legitimate call went unaccounted.
                i += 1
                positionals -= 1
            continue
        if "=" in tok and not tok.startswith("-"):
            i += 1                        # a leading VAR=VALUE environment assignment
            continue
        return False                      # `echo`, `cat`, `grep`, … — never reaches the test
    return False


def normalize_beat_text(text: str) -> str:
    """The NAR normalizer (spec §2; F-8 order pinned): per-line `"> "` blockquote prefixes
    stripped BEFORE collapsing (strip-then-collapse, never the reverse — a wrapped `"> "`-quoted
    narration must match the record's unquoted text); whitespace collapsed; surrounding /
    trailing / unpaired asterisks (the italics markers) stripped; case preserved."""
    lines = [ln[2:] if ln.startswith("> ") else ln for ln in str(text).splitlines()]
    collapsed = " ".join(" ".join(lines).split())
    return collapsed.strip("*").strip()


def _checked_texts(record: Any) -> Optional[list[tuple[str, str]]]:
    """The NAR checked set: (label, raw-text) for `dream.sleep` + the six `dream.beats` entries
    (record indexes 0-5 — the surfacing line is the last beats entry; WAKE is post-persist and
    correctly unchecked).

    THE SET CANNOT SILENTLY SHRINK (v0.4.29, spec §2.2). It used to admit a stanza only if
    `isinstance(x, str) and x.strip()`, so a beat that was `null`, `{}` or `0` did not FAIL the
    check — it LEFT the set, and the reason string's numerator is `len(checked)`. Measured on the
    shipped code: `beats: [null]*6` yielded a checked set of exactly `['sleep']` and could still
    read `verified`. The rule now: a stanza whose KEY IS PRESENT is judged — a non-string is
    carried as an empty needle so it fails (and _gaps names it). A stanza whose key is ABSENT
    stays out, because the arc gate owns absence (its have_sleep/have_wake arms fire exit 4) and
    pin (6)'s "record-arc wins" forbids double-reporting one absence in two panels.

    None when the record has no dream block — a legacy/dreamless record is OUTSIDE both arms
    (the v0.4.1 legacy carve-out extended: the arms judge only records that claim a dream). The
    empty LIST is a different state — a dream block carrying nothing usable — and `judge` reads
    the two apart; collapsing them is defect C6."""
    if not isinstance(record, dict):
        return None
    dream = record.get("dream")
    if not isinstance(dream, dict):
        return None
    out: list[tuple[str, str]] = []
    if "sleep" in dream:
        sleep = dream["sleep"]
        out.append(("sleep", sleep if isinstance(sleep, str) else ""))
    beats = dream.get("beats")
    if isinstance(beats, list):
        for i, b in enumerate(beats):
            out.append((f"beats[{i}]", b if isinstance(b, str) else ""))
    return out


def _window_lines(session_dir: Path, since: str) -> tuple[list[dict], bool]:
    """(kept_lines, unavailable). Reuses extract_signals._window_transcripts (glob + mtime-prune)
    and the SAME per-line keep-semantics (spec F-5): a parseable line with ts > since is kept;
    ts-less / unparseable-ts lines are kept too (never <= since); json-malformed lines are
    skipped; a transcript file that fails to open counts as UNAVAILABLE. Zero kept lines is the
    seam's zero-content case — the verdict degrades, it never fires."""
    try:
        from extract_signals import _window_transcripts
        files = _window_transcripts(Path(session_dir), since)
    except Exception:
        return [], True
    if not files:
        return [], False
    try:
        from memory_status import _parse_ts
    except Exception:
        return [], True
    since_dt = _parse_ts(since) if since else None
    kept: list[dict] = []
    opened_any = False
    for f in files:
        try:
            fh = f.open(encoding="utf-8", errors="replace")
        except OSError:
            # One unopenable pooled file (a chmod/gc race mid-scan — the spec's own rotation
            # scenario) must NOT degrade the whole window: the reused machinery's convention is
            # skip-and-continue (extract_signals), and the seam's contract is "only the
            # zero-content case degrades". Unavailable is only for the NOTHING-readable case.
            continue
        opened_any = True
        with fh:
            for line in fh:
                try:
                    o = json.loads(line)
                except (json.JSONDecodeError, RecursionError, ValueError):
                    continue
                ts = o.get("timestamp", "")
                ts_dt = _parse_ts(ts) if (since_dt and ts) else None
                if since_dt and ts_dt and ts_dt <= since_dt:
                    continue
                kept.append(o)
    return kept, not opened_any


def _assistant_text_blocks(lines: list[dict]) -> list[str]:
    """The NAR match domain (spec §2; F-6): assistant-role lines' `type == "text"` content
    blocks ONLY — never tool_use.input, never tool_result (the record-fill echoes), and thinking
    blocks (any other content type) never count. The extraction is NEW: extract_signals' own
    pipeline skips assistant messages entirely, so `_human_text` is the block-filter pattern,
    not a callable precedent."""
    out: list[str] = []
    for o in lines:
        msg = o.get("message")
        if not isinstance(msg, dict) or msg.get("role") != "assistant":
            continue
        c = msg.get("content")
        if isinstance(c, str):
            if c.strip():
                out.append(c)
            continue
        if isinstance(c, list):
            for p in c:
                if isinstance(p, dict) and p.get("type") == "text":
                    t = p.get("text", "")
                    if isinstance(t, str) and t.strip():
                        out.append(t)
    return out


def _extractor_accounted(lines: list[dict], entries: Any) -> tuple[bool, str]:
    """EXT: (accounted, detail). Accounted iff an EXECUTED extract_signals.py invocation in the
    Phase-2 form appears in an in-window Bash tool_use command (anchored on execution — see
    _runs_extractor; a fragment carrying --recalls does NOT count: the recall-only mode is not
    the Phase-2 extract), OR an entries[] row whose reason begins with the canonical
    `extractor-skip:` marker + a non-empty why (the fixed token the SKILL defines — a prose
    matcher would false-exit-3 legitimate skips)."""
    for o in lines:
        msg = o.get("message")
        if not isinstance(msg, dict) or msg.get("role") != "assistant":
            continue
        c = msg.get("content")
        if not isinstance(c, list):
            continue
        for p in c:
            if not isinstance(p, dict) or p.get("type") != "tool_use" or p.get("name") != "Bash":
                continue
            cmd = p.get("input", {})
            cmd_s = cmd.get("command", "") if isinstance(cmd, dict) else ""
            if not isinstance(cmd_s, str):
                continue
            if _EXTRACTOR_TOKEN not in cmd_s:
                continue                  # cheap pre-filter: keep the tokenizer off the hot path
            for seg in _segments(_normalize(cmd_s)):
                if _EXTRACTOR_TOKEN not in seg:
                    continue
                try:
                    toks = shlex.split(seg, posix=True)
                except ValueError:
                    continue              # unbalanced quotes — Uncertain → fire, never accounted
                if any(_runs_extractor(part) for part in _split_amp(toks)):
                    return True, "extract_signals.py executed in-window (Phase-2 form)"
    if isinstance(entries, list):
        for e in entries:
            if not isinstance(e, dict):
                continue
            reason = e.get("reason", "")
            if not isinstance(reason, str):
                continue
            if reason.startswith(_SKIP_MARKER):
                if reason[len(_SKIP_MARKER):].strip():
                    return True, "entries[] carries the extractor-skip: marker + why"
    return False, "no Phase-2 extract_signals.py invocation and no extractor-skip: entry"


def _preview(text: str) -> str:
    return " ".join(str(text).split())[:90]


def judge(record: Any, session_dir: Path, since: str,
          retry_delay: float = 0.5, sleep_fn: Callable[[float], None] = time.sleep,
          scan_fn: Optional[Callable[[], tuple[list[str], list[dict], bool]]] = None) -> dict:
    """The two-arm verdict (spec §2). Returns {"verdict": "verified"|"degraded"|"failed",
    "reason": str, "gaps": [{"label", "preview"}], "ext_unaccounted": bool}. `gaps` names the
    missing checked texts (sleep by name, beats by record index 0-5) + their first ~15 words so
    the panel's backfill is targeted. scan_fn injectable for the pins (returns
    (text_blocks, lines, unavailable)).

    Order pinned by the spec: zero-content degrades IMMEDIATELY (no re-read — a retry cannot
    rescue a rotated transcript); on a GAP the window is re-read once (~500 ms) and the verdict
    fires only if the second read confirms — scoped to the sub-second same-message flush race
    (the 5-minute write-behind class is handled by persist-then-re-render, not by any in-call
    re-read). The retry recomputes EXT too — free and consistent.
    """
    checked = _checked_texts(record)
    if checked is None:
        return {"verdict": "verified",
                "reason": "no dream block — a legacy record is outside both arms",
                "gaps": [], "ext_unaccounted": False}
    if not checked:
        # A dream block that carries nothing usable is a FAILED pass, not an absent one (v0.4.29,
        # spec §2.2). Returns BEFORE the scan: there is nothing to look for, and falling through
        # would reach the `missing or not accounted` conjunction with `missing == []` — which
        # would certify an empty block as verified. Distinguished from the None arm above because
        # the two mean opposite things and only `None` is the legacy carve-out (C6).
        return {"verdict": "failed",
                "reason": "dream block empty — no narratable stanza",
                "gaps": [{"label": "dream block", "preview": "no narratable stanza"}],
                "ext_unaccounted": False}

    def _scan():
        if scan_fn is not None:
            return scan_fn()
        lines, unavailable = _window_lines(session_dir, since)
        return _assistant_text_blocks(lines), lines, unavailable

    def _gaps(blocks):
        norms = [normalize_beat_text(b) for b in blocks]
        missing = []
        for label, raw in checked:
            needle = normalize_beat_text(raw)
            if not needle:
                # An empty needle is a GAP, never a `continue` (v0.4.29, spec §2.2). Skipping it
                # removed the item from the check while leaving it in the numerator, so a record
                # whose every stanza was `*` (or `***`, or `> `) recorded as 7/7 narrated against
                # a transcript with no narration at all. The spec's tie-break is Uncertain → fire.
                missing.append({"label": label,
                                "preview": "no narratable content (empty after normalize)"})
                continue
            if not any(needle in n for n in norms):
                missing.append({"label": label, "preview": _preview(raw)})
        return missing

    blocks, lines, unavailable = _scan()
    if unavailable or not lines:
        return {"verdict": "degraded", "reason": "transcript unavailable",
                "gaps": [], "ext_unaccounted": False}
    missing = _gaps(blocks)
    accounted, detail = _extractor_accounted(lines, record.get("entries"))
    if missing or not accounted:
        try:
            sleep_fn(retry_delay)
        except Exception:
            pass
        blocks2, lines2, unavailable2 = _scan()
        if not unavailable2 and lines2:
            missing = _gaps(blocks2)
            accounted, detail = _extractor_accounted(lines2, record.get("entries"))
    if missing or not accounted:
        gaps = list(missing)
        if not accounted:
            gaps.append({"label": "extractor unaccounted", "preview": ""})
        bits = []
        if missing:
            bits.append("missing narration: " + ", ".join(g["label"] for g in missing))
        if not accounted:
            bits.append(detail)
        return {"verdict": "failed", "reason": "; ".join(bits), "gaps": gaps,
                "ext_unaccounted": not accounted}
    return {"verdict": "verified",
            "reason": "%d/%d narrated · %s" % (len(checked), len(checked), detail),
            "gaps": [], "ext_unaccounted": False}


def narration_block(verdict: dict) -> dict:
    """The additive record block every judged persist writes pre-append (spec F-2): the block on
    the log line is THAT attempt's scan result — absence on a log line then unambiguously means
    pre-feature (the beta min_version gate skips). Failed carries the gap indexes; degraded
    carries the reason; verified carries the count."""
    out = {"verdict": verdict.get("verdict", ""), "reason": verdict.get("reason", "")}
    gaps = [g.get("label") for g in (verdict.get("gaps") or []) if g.get("label")]
    if gaps:
        out["gaps"] = gaps
    return out
