#!/usr/bin/env python3
"""dream_procedure.py — the conversation-truth detector (v0.4.19).

The persist gates v0.4.1 shipped are RECORD-side: they read what the record says about itself
(procedure integrity, dream-arc completeness). The measured 2026-09-06 defect class is the
conversation side: the record's dream block was filled AT record-fill instead of narrated in the
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
import time
from pathlib import Path
from typing import Any, Callable, Optional

_EXTRACTOR_TOKEN = "extract_signals.py"
_SKIP_MARKER = "extractor-skip:"
# Anchored on EXECUTION (spec §2): python3/python as an invocation word (start-of-command or
# after a whitespace/;/&/| separator — `$(...)` fails the class: '(' is not in it), followed by
# a command segment (no ;/&/|/newline) containing `extract_signals.py` with a word-boundary
# guard (tests/test_extract_signals.py never matches). The match extends to the SEGMENT TAIL so
# the form check sees the flags (`--recalls` follows the token — it must be inside the match or
# the recall-only form would pass for the Phase-2 extract). grep/sed/cat targets never match —
# no python invocation word precedes them.
_INVOKE_RE = re.compile(
    r"(?:^|[\s;&|])(?:python3|python)\s+[^\n;&|]*?(?<![A-Za-z0-9_])" + _EXTRACTOR_TOKEN + r"[^\n;&|]*")


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
    correctly unchecked). None when the record has no dream block — a legacy/dreamless record is
    OUTSIDE both arms (the v0.4.1 legacy carve-out extended: the arms judge only records that
    claim a dream)."""
    if not isinstance(record, dict):
        return None
    dream = record.get("dream")
    if not isinstance(dream, dict):
        return None
    out: list[tuple[str, str]] = []
    sleep = dream.get("sleep")
    if isinstance(sleep, str) and sleep.strip():
        out.append(("sleep", sleep))
    beats = dream.get("beats")
    if isinstance(beats, list):
        for i, b in enumerate(beats):
            if isinstance(b, str) and b.strip():
                out.append((f"beats[{i}]", b))
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
    for f in files:
        try:
            fh = f.open(encoding="utf-8", errors="replace")
        except OSError:
            return [], True  # a file that fails to open counts as unavailable (spec F-5)
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
    return kept, False


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
    _INVOKE_RE; a fragment carrying --recalls does NOT count: the recall-only mode is not the
    Phase-2 extract), OR an entries[] row whose reason begins with the canonical
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
            for m in _INVOKE_RE.finditer(cmd_s):
                if "--recalls" in m.group(0):
                    continue
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
    if not checked:
        return {"verdict": "verified",
                "reason": "no dream block — a legacy record is outside both arms",
                "gaps": [], "ext_unaccounted": False}

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
