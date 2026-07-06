#!/usr/bin/env python3
"""Extract structured consolidation candidates from a session transcript.

The transcript is large (tens of MB) but the *signal* is tiny and isolated
(probed: human turns are <1% of bytes; error tool-results are ~1% of tool calls).
This streams the `.jsonl` and emits curated, structured candidates from the two
transcript-borne sources — so the workflow never bulk-loads the transcript:

  • human turns        → feedback / preference facts
  • error tool-results → gotchas (env/tooling surprises)

(The third source, git `marker..HEAD`, is structured already and handled by
memory_status.py — not duplicated here.)

Business logic, grounded in the probe:
  - SCOPE to the marker: only entries after the last-consolidation timestamp, so a
    re-run doesn't re-surface everything (efficiency). v0.1.69/A1: the compare is
    PARSED-instant, not raw-string (an offset marker/`--since` could mis-order against
    CC's `Z` stamps otherwise) — and it fails OPEN: an unparseable marker/`--since`, or a
    single line's unparseable `ts`, disables the filter rather than raising. This is a
    DELIBERATE, tested tradeoff (recall-biased, matching the rest of this module's
    posture) that consciously NARROWS the efficiency invariant above in the rare
    malformed-timestamp case — re-surfacing already-consolidated turns is judged safer
    than silently dropping a genuine new one on a parse failure. Sign off on this
    weighing before changing it (Gate-2b, 2026-07-06).
  - DROP unambiguous noise (harness/skill injections, command echoes, image refs).
  - SECRETS firewall at RETRIEVAL: a turn containing a credential-shaped value is
    dropped to a label — never surface the verbatim secret (it could flow to a
    committed doc). Drop-to-label, not partial-scrub.
  - RANK, don't gate: keyword markers rank/classify turns; non-noise turns are all
    surfaced (recall-biased) up to --max, lowest-signal acks last.
  - SCOPE HINT per candidate (user|env|project) to pre-stage routing.

Usage: extract_signals.py [PROJECT_DIR] [--since ISO_TS] [--max N] [--json]
       (default --since: the marker timestamp; default --max 30)
       extract_signals.py --recalls [PROJECT_DIR] [--since ISO_TS] [--json] [--into SEED]
       (Phase A recall-usage telemetry: organic fact-body reads this window, script-only)
"""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

import _ui  # sibling script: the shared visual vocabulary (color / rule / kv / glyphs)
from memory_status import (_is_archive_index, _is_archive_index_text, _parse_ts, _sane, _write_private,
                           index_fact_names, slug_for, _LINK_RE)
# slug rule (v0.1.17) + archive-index classifiers + 0o600-atomic seed write (v0.1.63 --recalls) + the
# relocated single timestamp parser & the index-pointer link anchor + index reader (v0.1.67 miss-detector)
# + _sane: fact STEMS printed by --recalls derive from transcript Read file_paths (attacker-influenceable
# session content) — strip control bytes before they reach the terminal (the git-subject convention)

STATE_FILE = ".consolidation-state.json"


def _norm(text: object) -> str:
    """Collapse whitespace AND drop Unicode format/zero-width (Cf) characters, on the
    SINGLE representation that is both scanned by the firewall and stored. Zero-width
    chars inserted inside a credential would otherwise split it past every regex arm yet
    persist verbatim — so strip them before scan and store stay aligned.

    Arg typed `object` (it str()s internally) so a tool-result `content` of type
    `str | Any | None` — the union dict.get yields off the model-authored transcript —
    flows in without a cast; the str() coercion is the runtime guard."""
    return "".join(c for c in " ".join(str(text).split()) if unicodedata.category(c) != "Cf")
# Max chars of a single turn fed to the classifier/secret regexes. Only text[:300] is
# ever stored, so a larger cap than that is pure defense-in-depth against huge inputs.
_PROBE_CAP = 4000

# Unambiguous noise — harness/skill injections and command echoes, not human intent.
_NOISE = re.compile(
    r"^\s*(<local-command-|<command-|<task-notification|<teammate-message|"
    r"Another Claude session sent a message:|Caveat:|"
    r"Base directory for this skill:|This session is being continued|\[Image:|\[Request interrupted)",
    re.I,
)
# Skill-prompt injections (e.g. the code-review skill's effort header).
_SKILL_PROMPT = re.compile(r"(effort\s*→|angles\s*×|candidates\s*→|1-vote verify|# Consolidate Memory)", re.I)

# v0.1.53: a human turn often opens with harness `[Image #N]` (or `[Image: source: …]`) attachment markers and
# then carries REAL text. The old `_NOISE` `\[Image:` arm matched the colon form only AND dropped the WHOLE turn
# (losing the feedback that follows). Instead STRIP leading image markers; if nothing remains it was an image-
# only turn (noise); else classify the remainder. Runs on the `_norm`'d text so the firewall still scans/stores
# exactly the stripped text (a secret after a marker is still seen). Anchored, non-overlapping → ReDoS-free.
# A QUOTED absolute-path token MAY contain spaces ('/…/Screenshot from ….png' — the real-world screenshot
# paste a bare-\S+ rule misses); a BARE token is whitespace-free.
_QUOTED_PATH = r"(?:'/[^']*'|\"/[^\"]*\")"
_PATH_TOKEN = rf"(?:{_QUOTED_PATH}|/[^\s'\"]+)"
# A turn that is ONLY pasted path token(s) → noise (no durable signal). "see /home/x — broken" does NOT match
# (leading non-path token). Runs on the capped, marker-stripped probe; unix-absolute-only by design.
_PATH_ONLY = re.compile(rf"^{_PATH_TOKEN}(?:\s+{_PATH_TOKEN})*$")
# Leading ATTACHMENT noise to STRIP (revealing the real prose that FOLLOWS): [Image #N] markers + a leading run
# of pasted QUOTED screenshot paths (the dominant case — the user pastes 'screenshot1' 'screenshot2' … THEN the
# actual instruction, which `norm[:300]` would otherwise truncate off the end). A BARE leading path is NOT
# stripped (it may be the subject — "/x/config.py needs fixing"); a bare path-ONLY turn is still caught by _PATH_ONLY.
_LEAD_ATTACH = re.compile(rf"^(?:\[Image[^\]]*\]\s*|{_QUOTED_PATH}\s*)+", re.I)


def _strip_markers(text: str) -> str:
    """Strip leading attachment noise ([Image #N] markers + pasted quoted paths); return the real remainder."""
    return _LEAD_ATTACH.sub("", text).strip()

# v0.1.49: transient tool-protocol noise in the ERROR channel. A <tool_use_error> wrapper is Claude Code's OWN
# tool-usage error (file-not-read, string-not-found, file-modified, no-task-found) — Claude's retryable mistake,
# NEVER an environment gotcha (env facts arrive as bash stderr / exit codes, unwrapped). It is the one error
# class that is high-volume (~73% of raw error results, measured), harness-stable, and zero-false-drop. We do
# NOT filter inline-script tracebacks (a `python3 -c "import X"` → ModuleNotFoundError IS a durable env fact) or
# lint (a free-form match that rots) — that residual falls to MAX_ERRORS + the model's Phase-2 judgment.
# ANCHORED to a LEADING wrapper (the actual tool-protocol-error shape) so an env error that merely *quotes*
# the marker mid-body is NOT false-dropped — verified zero recall loss vs unanchored (136/136 fleet-wide),
# higher precision (this repo processes transcripts that contain the marker).
_ERROR_NOISE = re.compile(r"^\s*<tool_use_error>", re.I)
# v0.1.53: extend the error-channel filter beyond <tool_use_error> to the other classes the live data showed
# are ~100% of the survivors (a real session surfaced 8 errors, 0 durable gotchas). Each arm is PRECISE — a
# real env error must still pass:
#  • AUTO-MODE — Claude Code's own auto-mode classifier messages (permission denial / model-unavailable). Same
#    harness-artifact class as <tool_use_error>; never an environment fact. Anchored to the SPECIFIC phrasings.
#  • LINT/FORMAT — ruff's RUN output (`=== ruff`, `ruff check`), a lint LINE (an `E###` code PAIRED with its
#    `Line too long` message), and ruff-format's `Would reformat:` / `N file(s) would be reformatted`. Transient
#    style, never durable. Does NOT match `ruff: command not found` (a real env gotcha — kept): no `===`/`check`.
#  • INLINE-SCRIPT OWN-BUG — a `File "<stdin>"`/`File "<string>"` traceback (a `python3 -c`/heredoc the MODEL
#    wrote) whose exception is NOT Import/ModuleNotFound is the model's transient logic bug, not an env fact.
#    A genuine `python3 -c "import x"` ModuleNotFoundError IS a durable env fact → KEPT (the v0.1.49 carve-out).
_AUTOMODE_NOISE = re.compile(
    r"denied by the [Cc]laude [Cc]ode auto mode classifier|auto mode cannot determine|temporarily unavailable, so auto mode", re.I)
_LINT_NOISE = re.compile(
    r"===\s*ruff\b|\bE\d{3}\b[^\n]*\bLine too long\b|\bWould reformat:|\b\d+ files? would be reformatted\b", re.I)
_INLINE_TB = re.compile(r'File "<(?:stdin|string)>"')
# The model's OWN inline-script LOGIC-bug exceptions (a buggy `python3 -c`/heredoc) — distinct from a real ENV
# fact surfaced via the SAME channel (ImportError/ConnectionError/OperationalError/PermissionError/OSError/timeout
# = "X is broken/missing HERE", KEPT). Drop a <stdin>/<string> traceback ONLY when its exception is a clear
# code-bug class — NOT the earlier "non-import" rule, which over-dropped a real env error that merely had an
# incidental <string> frame (jinja/exec) or came from a `python3 -c` probe (e.g. a down-DB OperationalError).
_LOGIC_BUG = re.compile(
    r"\b(?:KeyError|NameError|AttributeError|TypeError|IndexError|UnboundLocalError|ZeroDivisionError|"
    r"IndentationError|SyntaxError)\b")


def _is_error_noise(text: str) -> bool:
    """True if an error tool-result is a HARNESS ARTIFACT or transient style/own-bug — NOT a durable env gotcha.
    Runs AFTER the secrets firewall (a credential-shaped error is omitted, never reaches here)."""
    if _ERROR_NOISE.search(text) or _AUTOMODE_NOISE.search(text) or _LINT_NOISE.search(text):
        return True
    # the model's own inline-script logic bug (KeyError/NameError/… in a -c/heredoc) — NOT an env fact.
    return bool(_INLINE_TB.search(text)) and bool(_LOGIC_BUG.search(text))

# A flood backstop for the UNRANKED, post-filter error survivors (errors carry no salience score). Generous for
# a normal session (real gotchas are rare), bounds a pathological flaky-loop session. NOT a quality ranking.
MAX_ERRORS = 8

# v0.1.50: a dedup KEY that collapses byte-noise variants of ONE error class to a single row (the error channel
# dedups by exact text + caps at MAX_ERRORS, so byte-noise — exit codes, line numbers, temp paths, PIDs,
# timestamps — fragments one class into many and dilutes the cap). HEAD-EXTRACTION does the heavy lifting: keying
# from a `Word…Error/Exception/Warning:` head onward drops the "Exit code 1 Traceback … File "/…", line N" preamble
# + frames (incl. their varying paths/line-numbers) while PRESERVING the message — so 'foo' != 'bar' and
# ModuleNotFoundError != PermissionError stay distinct. Then only LIGHT, UNAMBIGUOUS byte-noise normalization
# (exit codes, line numbers, ISO timestamps). Deliberately we normalize NOTHING whose value could be SIGNAL —
# NO path->/PATH, NO blanket \d{3,}->N, NO bare-hex->HEX, NO bare-clock(HH:MM)->TS: the binary in "foocli: command
# not found", "HTTP 404" vs "500", a Windows HRESULT "0x80004005", and a slice "arr[10:20]" are SIGNAL, not noise
# (the gate-2 asymmetry fix — keep the byte-noise list symmetric: only-noise tokens, never a possible identifier).
# Head-extraction already handles traceback paths/frames. Keys only — the stored verbatim text is untouched
# (display unaffected). The cross-session recurrence MULTIPLIER is deferred (D1).
_ERR_HEAD = re.compile(r"\b\w+(?:Error|Exception|Warning):\s*.*", re.S)
_ERR_KEY_SUBS = (
    (re.compile(r"(?i)\bexit code \d+"), "exit code N"),
    (re.compile(r"(?i)\bline \d+"), "line N"),
    (re.compile(r"\d{4}-\d{2}-\d{2}[ T][\d:]+"), "TS"),   # ISO timestamps only (unambiguous noise)
)


def _error_key(text: str) -> str:
    """Collapse byte-noise variants of one error CLASS to a stable key; keep distinct errors distinct."""
    m = _ERR_HEAD.search(text)
    base = m.group(0) if m else text
    for rx, repl in _ERR_KEY_SUBS:
        base = rx.sub(repl, base)
    return " ".join(base.split())[:160]

# Credential-shaped values. Detection is SPLIT in two because the generic high-entropy
# check needs CASE discrimination (mixed-case is the signal that separates a token from
# a file path / slug) and the keyword/vendor arms want case-INSENSITIVITY — and one
# regex can't be both. Use `_looks_secret()` (below) as the firewall, never `_SECRET`
# directly. Contract: drop-to-label, never surface the verbatim secret.
#
# _SECRET (case-insensitive): keyword=value in any serialization (incl. compound names
# AWS_SECRET_ACCESS_KEY= and quoted JSON "password": "..."), plus high-precision vendor /
# protocol shapes that carry no high-entropy blob.
_SECRET = re.compile(
    r"""(
        (?:[A-Za-z0-9]+[_.\-])*(?:li_at|cf_clearance|password|passwd|pwd|pass(?:phrase)?|cred(?:ential)?s?|api[_-]?key|access[_-]?key|private[_-]?key|secret|token|bearer|authorization)(?:[_.\-][A-Za-z0-9]+)*["']?\s*[:=]\s*["']?\S+
                                                                     # keyword as a full SEGMENT of a compound id, with
                                                                     # optional quotes/brackets around the delimiter so
                                                                     # JSON {"password": "..."} / dict / YAML all match
      | (?:authorization|bearer)\b["']?\s*:?\s*(?:bearer\s+)?[A-Za-z0-9._~+/=-]{16,}  # auth header / bearer token
      | [a-z][a-z0-9+.\-]*://[^\s/:@]+:[^\s/@]+@                      # scheme://user:pass@host URI creds
      | (?:AKIA|ASIA)[0-9A-Z]{16}                                    # AWS access key id
      | xox[baprs]-[0-9A-Za-z-]{10,}                                 # Slack token
      | sk-(?:proj-)?[A-Za-z0-9_-]{20,}                              # OpenAI key
      | (?:sk|rk|pk)_(?:live|test)_[0-9A-Za-z]{10,}                  # Stripe key
      | gh[pousr]_[0-9A-Za-z]{20,}                                   # GitHub token
      | AIza[0-9A-Za-z_-]{35}                                        # Google API key
      | AC[0-9a-f]{32}                                               # Twilio account SID
      | eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{6,}   # JWT (header.payload.sig)
      | -----BEGIN[ A-Z]*PRIVATE[ ]KEY-----                          # PEM private key
    )""",
    re.I | re.X,
)

# A contiguous run of base64-ish chars (incl. '/' and '+' so slash-bearing AWS secret
# access keys are caught). Case-SENSITIVE on purpose (see _entropy_blob).
_BLOB = re.compile(r"[A-Za-z0-9+/=_-]{40,}")


def _entropy_blob(text: str) -> bool:
    """True if `text` holds a keyword-less high-entropy token (e.g. a bare AWS secret key
    or base64 blob). Distinguishes a token from a FILE PATH or SLUG without case folding:
    a token is mixed-case or carries digits; a path is slash-dense; a slug is all-lower
    with no digits. This is the half the case-insensitive `_SECRET` regex cannot express."""
    for m in _BLOB.finditer(text):
        s = m.group(0)
        if s.count("/") >= 3:           # slash-dense ⇒ a filesystem path, not a token
            continue
        has_lower = any(c.islower() for c in s)
        has_upper = any(c.isupper() for c in s)
        has_digit = any(c.isdigit() for c in s)
        if (has_lower and has_upper) or has_digit:   # mixed-case OR digit-bearing ⇒ token-like
            return True
    return False


def _looks_secret(text: str) -> bool:
    """The firewall: True if `text` contains a credential-shaped value (keyword/vendor
    arms OR a high-entropy blob). Use THIS everywhere, not `_SECRET` directly."""
    return bool(_SECRET.search(text)) or _entropy_blob(text)

# Pure approvals / workflow control — surface but rank lowest (signal score 0).
_ACK = re.compile(
    r"^\s*(yes|yep|ok(ay)?|sure|go ahead|do it|proceed|continue|push( it)?|"
    r"merge|ship it|approved|fix all( of them)?|try now|dream|next|perfect|thanks?)\b[\s.!]*$",
    re.I,
)
# v0.1.53: the exact-`_ACK` regex only matched a SINGLE ack word, so COMPOUND control turns ("Ship it please",
# "Yes ship it", "Let's continue") escaped → surfaced as `statement`/score-1, diluting the signal. An ack now =
# the exact form OR a turn whose ENTIRE content is ack-VOCABULARY (affirmations + control verbs + pure filler):
# strip every vocab token; if only whitespace/punctuation remains (and ≥1 token matched), the turn carries no
# durable content → ack. A turn with ANY content noun/path/identifier after the control verb ("proceed with the
# postgres migration", "yes the bug is in parser.py") leaves a non-empty remainder → NOT an ack — the recall
# guard (a length-bound alone wrongly demoted those short-but-signal-bearing turns to score-0). `_classify` runs
# `_MARKERS` FIRST, so "yes, but ALWAYS X" is a preference, never reaches here. `.sub` + emptiness ⇒ ReDoS-free.
_ACK_VOCAB = re.compile(
    r"\b(?:yes|yeah|yep|ok|okay|sure|perfect|great|nice|cool|alright|thanks|thank you|sounds good|lgtm|"
    r"please|go ahead|do it|ship it|ship them|send it|go for it|that works|proceed|continue|push|merge|"
    r"retry|approve|approved|next|dream|implement it|"
    r"let'?s (?:go|continue|proceed|ship|do it|finish|wrap|move on)|"
    r"and|then|now|too|also|it|them|the|here|logically|structurally|sequentially|all of them)\b",
    re.I,
)
_ACK_LEFTOVER = re.compile(r"[\s,.!?;:'\"()\[\]-]+")


def _is_ack(text: str) -> bool:
    """A pure approval / workflow-control turn (signal score 0): the ENTIRE turn is ack-vocabulary — nothing but
    affirmations, control verbs, and filler; no durable content noun/path/identifier survives the strip."""
    if _ACK.match(text):
        return True
    if not _ACK_VOCAB.search(text):
        return False
    return _ACK_LEFTOVER.sub("", _ACK_VOCAB.sub(" ", text)) == ""

# Signal markers → (signal_type, scope_hint). Order = priority.
_MARKERS = [
    ("correction", "user", re.compile(r"\b(actually|instead of|should(n'?t)?|why .* when|not just|i meant)\b", re.I)),
    ("preference", "user", re.compile(r"\b(never|always|prefer|make sure|ensure|don'?t|do not|properly|at the root|pin .*test|validate|fully|end.to.end|autonomous|verify)\b", re.I)),
    ("constraint", "project", re.compile(r"\b(i (rely|am based|use|need|want)|my (real|actual)|production|based in|account)\b", re.I)),
    ("decision", "project", re.compile(r"\b(table (it|this|the)|use .* not |go with|start(ing)? with|first,|tune .* first)\b", re.I)),
]


# v0.1.67 (Phase C): _parse_ts RELOCATED to memory_status (the dependency root) — memory_status's
# usage_history/demotion_candidates need it, and this module imports FROM memory_status, so keeping it
# here would force either a circular import or a second parser (the documented already-bitten divergence
# class: a distill-local copy once diverged on a no-colon offset, so the file-prune no-op'd while the
# per-line filter worked). Re-imported at the top so every existing consumer — `_window_transcripts`'
# file-prune cutoff, distill_scan's `from extract_signals import _parse_ts` — resolves the SAME function
# object (smoke-pinned identity across all three modules). Behavior unchanged.


def _window_transcripts(proj_root: Path, since: str) -> list[Path]:
    """v0.1.43: ALL transcripts in the dream window, not just the newest. A marker..HEAD window spans MANY
    sessions (each .jsonl == one session); reading only `ts[-1]` meant a fresh session opened JUST to run dream
    HID the heavy prior session's intent (the killer case the on-disk read was meant to defend). Glob all
    `*.jsonl`; mtime-PRUNE only DEFINITELY-stale files (mtime <= the marker → nothing in scope). The per-line
    `since` filter does the scoping, so the mtime-prune is purely an open-fewer-files optimization. The cutoff
    parse routes through `_parse_ts` (v0.1.58 — the shared parser: handles a bare `Z` [3.10 rejects it → the
    prune would silently no-op], a naive marker as UTC [else `.timestamp()` assumes LOCAL → a west-of-UTC TZ
    shifts the cutoff and wrongly DROPS a prior in-window session], AND a `±HHMM` no-colon offset). No marker /
    unparseable → keep ALL (safe). Oldest-first (deterministic; per-line `since` + dedup handle overlap)."""
    files = sorted(proj_root.glob("*.jsonl"), key=lambda p: p.stat().st_mtime)
    if not since:
        return files
    dt = _parse_ts(since)
    if dt is None:
        return files
    cutoff = dt.timestamp()
    return [f for f in files if f.stat().st_mtime > cutoff]


def _marker_ts(auto_mem: Path) -> str:
    sp = auto_mem / STATE_FILE
    if sp.exists():
        try:
            return json.loads(sp.read_text()).get("timestamp", "")
        except (json.JSONDecodeError, OSError):
            pass
    return ""


def _human_text(msg: dict) -> str | None:
    c = msg.get("content")
    if isinstance(c, str):
        return c.strip() or None
    if isinstance(c, list):
        parts = [p.get("text", "") for p in c if isinstance(p, dict) and p.get("type") == "text"]
        joined = "\n".join(p for p in parts if p).strip()
        return joined or None
    return None


def _classify(text: str) -> tuple[str, str, int]:
    """Return (signal_type, scope_hint, score). Markers rank; they never gate. v0.1.53: _MARKERS run FIRST so a
    marker-bearing turn ("yes, but ALWAYS use X") is never demoted to ack by the broadened ack matcher (_is_ack)."""
    for stype, scope, rx in _MARKERS:
        if rx.search(text):
            return (stype, scope, 2)
    if _is_ack(text):
        return ("ack", "project", 0)
    return ("statement", "project", 1)  # non-noise, no marker — still surfaced


# v0.1.48: the SINGLE signal constructor — every emitted signal goes through here, so it carries EXACTLY the
# canonical keyset and any --json consumer sees a value, never a missing key (the "?"/"s?" bug: error rows +
# the omitted-summary label had grown free-form dict literals that dropped signal_type/score). signal_type +
# score are BOTH keyword-REQUIRED, so a future append site physically cannot omit them; scope_hint/sessionId/
# ts default. `score` is human-turn SALIENCE (2 high · 1 med · 0 low/ack · -1 omitted); non-human (error)
# signals carry _NA_SCORE — N/A, never salience-ranked (they bypass _classify + are appended unranked); the
# source + signal_type fields disambiguate it from a low-salience human turn.
_NA_SCORE = 0


def _signal(source: str, text: str, *, signal_type: str, score: int,
            scope_hint: str = "-", sessionId: str = "", ts: str = "") -> dict:
    return {"source": source, "signal_type": signal_type, "scope_hint": scope_hint,
            "sessionId": sessionId, "ts": ts, "score": score, "text": text}


# Derived FROM the constructor (single-source: the test's expected keyset and the emitted keyset cannot
# drift apart — the repo's "a contract can't silently drift" convention).
_CANONICAL_KEYS = frozenset(_signal("", "", signal_type="", score=0))


def extract(project_dir: Path, since: str, max_n: int) -> dict:
    """The `--json` CONTRACT (beta finding H; v0.1.43 multi-session): the top-level shape is
    `{"transcripts": [<name>, ...], "since": <iso|"">, "counts": {human_seen, noise, secrets_omitted, errors,
    surfaced}, "signals": [<signal>, ...]}`. v0.1.48: EVERY <signal> carries the SAME canonical keyset (built by
    `_signal` — no missing keys, so no consumer renders a `?`): `{source, signal_type, scope_hint, sessionId, ts,
    score, text}` (was documented as `scope`/no-`score` — the gap that let error rows drift). `score` is human-turn
    salience (2 high · 1 med · 0 low/ack · -1 omitted); non-human (`error`) signals carry `_NA_SCORE` (0) = N/A,
    never salience-ranked. v0.1.43 CHANGES: `transcript` (a single name) → `transcripts` (a LIST — ALL sessions
    pooled across the marker..HEAD window), and each signal carries `sessionId` (the session that PRODUCED it — the
    originSessionId source for a session-derived fact). The candidate count lives at `counts.surfaced` (NOT
    top-level), and the list is `signals` (NOT `candidates`)."""
    project_dir = project_dir.resolve()
    proj_root = Path.home() / ".claude" / "projects" / slug_for(project_dir)
    auto_mem = proj_root / "memory"
    since = since or _marker_ts(auto_mem)
    transcripts = _window_transcripts(proj_root, since)
    # v0.1.69/A1: parse the window ONCE — the per-line compare is instant-vs-instant (an offset
    # marker/--since vs CC's Z stamps mis-orders lexicographically; distill's v0.1.58 twin fix, now
    # ported). Unparseable since/ts fail OPEN — keep the line (recall-biased).
    since_dt = _parse_ts(since) if since else None

    counts = {"human_seen": 0, "noise": 0, "secrets_omitted": 0, "errors": 0}
    human: list[dict] = []
    errors: list[dict] = []
    if not transcripts:
        return {"transcripts": [], "since": since, "counts": counts, "signals": []}

    # v0.1.43: pool EVERY in-window session through the SAME single per-line path (scrub -> since -> classify).
    # The secrets firewall (_looks_secret, below) runs per-line HERE, so it covers every pooled file identically —
    # there is NO second read path for the "extra" sessions (that would risk an un-scrubbed leak + reimplementation
    # drift). The outer loop only chooses WHICH files feed the one path.
    for transcript in transcripts:
        try:
            fh = transcript.open(encoding="utf-8", errors="replace")
        except OSError:
            continue  # a concurrent gc/chmod must not abort the whole pooled scan (matches the store-scan convention)
        with fh as f:
            for line in f:
                try:
                    o = json.loads(line)
                except (json.JSONDecodeError, RecursionError, ValueError):
                    # skip one malformed/pathological line (incl. deeply-nested JSON that
                    # blows the recursion limit) rather than aborting the whole stream
                    continue
                ts = o.get("timestamp", "")
                ts_dt = _parse_ts(ts) if (since_dt and ts) else None
                if since_dt and ts_dt and ts_dt <= since_dt:  # scope to marker (EXACT instant, per-line — across every pooled file)
                    continue
                sid = o.get("sessionId", "")       # v0.1.43: the producing session (the originSessionId source)
                msg = o.get("message")
                if not isinstance(msg, dict):
                    continue
                role = msg.get("role")
                if role == "user":
                    # error tool-results (gotcha source)
                    c = msg.get("content")
                    if isinstance(c, list):
                        for p in c:
                            if isinstance(p, dict) and p.get("type") == "tool_result" and p.get("is_error"):
                                counts["errors"] += 1
                                t = p.get("content")
                                if isinstance(t, list):
                                    t = " ".join(x.get("text", "") for x in t if isinstance(x, dict))
                                # SECRETS FIREWALL — error/stderr output (failed DB connects,
                                # 401 Authorization headers, dumped env) is a top source of
                                # leaked credentials. Normalize once, scan + store the same
                                # representation, capped at _PROBE_CAP like human turns.
                                tn = _norm(t)
                                if _looks_secret(tn[:_PROBE_CAP]):           # firewall FIRST (precedence)
                                    counts["secrets_omitted"] += 1
                                    errors.append(_signal("error", "(omitted: error tool-result contained a credential-shaped value)",
                                                          signal_type="omitted", score=_NA_SCORE, scope_hint="-", sessionId=sid, ts=ts))
                                elif _is_error_noise(tn[:_PROBE_CAP]):       # v0.1.49/53: harness artifact / transient style / own inline-bug (not an env gotcha)
                                    counts["noise"] += 1
                                else:
                                    errors.append(_signal("error", tn[:200], signal_type="error",
                                                          score=_NA_SCORE, scope_hint="env", sessionId=sid, ts=ts))
                    # human turns
                    text = _human_text(msg)
                    if not text:
                        continue
                    counts["human_seen"] += 1
                    # Normalize ONCE (+ v0.1.53 strip leading [Image #N] markers), then scan AND store the SAME
                    # representation, so the firewall examines exactly what would be persisted (no scan/store
                    # offset mismatch — a secret AFTER a stripped marker is still in `norm`, so still scanned).
                    # _PROBE_CAP bounds regex work; the stored excerpt (norm[:300]) is well within it.
                    norm = _strip_markers(_norm(text))
                    if not norm:                           # v0.1.53: an image-marker-only turn → noise (no real text)
                        counts["noise"] += 1
                        continue
                    probe = norm[:_PROBE_CAP]
                    if _NOISE.match(probe) or _SKILL_PROMPT.search(probe[:200]) or _PATH_ONLY.match(probe):  # v0.1.53: + path-only turns
                        counts["noise"] += 1
                        continue
                    if _looks_secret(probe):
                        counts["secrets_omitted"] += 1
                        human.append(_signal("human", "(omitted: turn contained a credential-shaped value)",
                                             signal_type="omitted", score=-1, scope_hint="-", sessionId=sid, ts=ts))
                        continue
                    stype, scope, score = _classify(probe)
                    human.append(_signal("human", norm[:300], signal_type=stype,
                                         score=score, scope_hint=scope, sessionId=sid, ts=ts))

    # dedup error-results AND human turns (the same gotcha/turn can repeat across pooled sessions). Explicit loop
    # rather than the `... or seen.add(x)` trick: set.add returns None (mypy flags it), so ADD first, then use.
    def _dedup(items: list[dict], key: Callable[[dict], str] | None = None) -> list[dict]:
        k = key or (lambda it: it["text"])    # default: exact-text (human behaviour UNCHANGED)
        seen: set[str] = set(); out: list[dict] = []
        for it in items:
            ky = k(it)
            if ky in seen:
                continue
            seen.add(ky); out.append(it)
        return out
    # v0.1.50: dedup errors by a normalized error-CLASS key (byte-noise variants of one class collapse to one
    # row), keeping the first occurrence's verbatim text; THEN the v0.1.49 flood backstop on the UNRANKED survivors.
    errors = _dedup(errors, key=lambda it: _error_key(it["text"]))[:MAX_ERRORS]
    human = _dedup(human)
    # rank human turns: high-signal first, acks last; cap at max_n ACROSS THE POOLED set. Keep ONE
    # omitted-secret label for transparency (the consolidation should know a
    # credential-bearing turn was skipped), but never the value.
    human.sort(key=lambda d: d.get("score", 0), reverse=True)
    surfaced = [s for s in human if s.get("score", 0) >= 0][:max_n]
    if counts["secrets_omitted"]:
        surfaced.append(_signal("human", f"({counts['secrets_omitted']} turn(s) omitted — credential-shaped value)",
                                signal_type="omitted", score=-1, scope_hint="-"))  # synthetic row → sessionId/ts default ""
    signals = surfaced + errors
    counts["surfaced"] = len(signals)
    return {"transcripts": [t.name for t in transcripts], "since": since or "(none — first pass)",
            "counts": counts, "signals": signals}


def _report(d: dict) -> None:
    c = d["counts"]
    out: list = []
    add = out.append
    title = "✦ SESSION SIGNAL · extracted candidates"
    tag = f"{c.get('surfaced', 0)} surfaced"
    gap = max(2, _ui.W - 2 - len(title) - len(tag))
    add(_ui.rule())
    add("  " + _ui.c("✦", "cyan") + title[1:] + " " * gap + _ui.c(tag, "bold"))
    _tx = d.get("transcripts", [])
    _txn = f"{len(_tx)} session(s): {', '.join(_tx)}" if _tx else "(no transcript)"
    # v0.1.69/A2 follow-up (Gate-2a): the header line interpolates `since` (a --since CLI value or
    # the on-disk marker timestamp) and transcript filenames — the SAME injection surface as the
    # per-signal text below, sanitize it the same way rather than leaving it one line away.
    add("  " + _ui.c(_sane(f"{_txn} · since {d['since']}"), "dim"))
    add(_ui.rule())
    add("")
    add(_ui.kv("COUNTS", f"{c.get('human_seen', 0)} human turns  "
              + _ui.c(f"· {c.get('noise', 0)} noise dropped · {c.get('secrets_omitted', 0)} secrets omitted · {c.get('errors', 0)} error-results", "dim")))
    add("")
    add(_ui.kv("FOUND", _ui.c("ranked candidates — verify + dedup before recording", "dim")))
    glyphs = {"human": ("·", "cyan"), "error": ("⚠", "yellow")}
    for s in d["signals"]:
        g, col = glyphs.get(s["source"], ("·", "dim"))
        meta = f"{s['source']}/{s.get('signal_type', 'err')}·{s.get('scope_hint', '?')}"
        # v0.1.69/A2 presentation boundary: _sane strips C0/ESC from repo-controlled text (terminal-
        # escape injection guard). --json stays raw-but-escaped (json.dumps; bytes can BE the signal).
        add(f"    {_ui.c(g, col)} {_ui.lbl(f'{meta[:26]:<26}')} {_ui.wrap(_sane(s['text']), hang=33)}")
    print(_ui.ascii_translate("\n".join(out)))


# ── v0.1.63 (Phase A): --recalls — organic fact-body recall tracking ─────────────────────────────
# docs/index-usage-and-budget-ladder.spec.md. The missing utility axis: merit is judged at write time
# (verification) but nothing measured whether a fact is ever READ. Transcripts record every tool_use
# Read; retention is short (MEASURED 2026-07-04: 3-8 survivors/project), so usage must be accrued
# per-dream while the window is still on disk — the distill_scan pattern. PINNED BIAS: every mechanism
# here UNDERCOUNTS (retention, span over-exclusion, any harness auto-recall invisible to Read events)
# — 0 reads = ABSENCE OF EVIDENCE, never evidence of no use; Phase C must corroborate before acting.

_USAGE_FACT_CAP = 40   # per_fact rows emitted (nonzero, fattest-read first); mirrored by
                       # memory_status._USAGE_FACT_CAP (smoke-pinned) for the validator backstop.
                       # v0.1.67 (Phase C): 20 → 40 — the heaviest fleet node measured 22 facts/window,
                       # so under 20 its every window was cap-truncated = non-probative for zero-read
                       # evidence (see memory_status's mirror comment; the pins move together)
_ARC_MARK = "CM_DREAM_ARC"


def split_dream_span(items: list) -> tuple[list, int]:
    """PURE classifier (smoke-pinned): ONE transcript's ordered items — [{'i': line#, 'kind':
    'arc'|'read', 'stem': …, 'ts': …}] — → (organic_read_items, dream_excluded_count). A read is
    DREAM-PROCEDURE iff first_arc ≤ i ≤ last_arc (Phase 1 reads every fact as procedure — counting
    those as recall would saturate utility); everything outside the span is ORGANIC. Deliberately
    conservative: a multi-dream session's inter-dream gap is over-excluded (undercount = the safe
    direction under the pinned bias above). Whole-TRANSCRIPT exclusion was rejected: on a dream-heavy
    repo every surviving transcript contains a dream, so it measures 0 forever (MEASURED)."""
    arcs = [it["i"] for it in items if it.get("kind") == "arc"]
    reads = [it for it in items if it.get("kind") == "read"]
    if not arcs:
        return reads, 0
    lo, hi = min(arcs), max(arcs)
    organic = [r for r in reads if not (lo <= r["i"] <= hi)]
    return organic, len(reads) - len(organic)


def _recall_items(transcript: Path, store_prefix: str, since: str, archive_stems: frozenset) -> list:
    """Stream ONE transcript → ordered arc/read items for split_dream_span. Substring pre-filters keep
    the hot loop cheap on tens-of-MB files (json.loads only lines that can matter). An ARC item is a
    Bash tool_use whose command carries CM_DREAM_ARC (the dream's scripted invocations — the spec's
    strict rule: prose mentions of the marker must NOT widen the span); a READ item is a Read tool_use
    on a fact file directly under the store (MEMORY.md + archive indexes excluded — an archive read is
    not a fact recall). The per-line `since` compare scopes to the window exactly like extract()
    (transcripts straddle the marker)."""
    items: list = []
    since_dt = _parse_ts(since) if since else None   # v0.1.69/A1: instant compare — twin of extract()'s
    try:
        fh = transcript.open(encoding="utf-8", errors="replace")
    except OSError:
        return items                      # concurrent gc/chmod must not abort the scan (store-scan convention)
    with fh as f:
        for i, line in enumerate(f):
            arc_hint = _ARC_MARK in line
            if not arc_hint and (store_prefix not in line or '"Read"' not in line):
                continue
            try:
                o = json.loads(line)
            except (json.JSONDecodeError, RecursionError, ValueError):
                continue
            ts = o.get("timestamp", "")
            ts_dt = _parse_ts(ts) if (since_dt and ts) else None
            if since_dt and ts_dt and ts_dt <= since_dt:
                continue
            msg = o.get("message")
            if not isinstance(msg, dict) or not isinstance(msg.get("content"), list):
                continue
            for p in msg["content"]:
                if not (isinstance(p, dict) and p.get("type") == "tool_use"):
                    continue
                inp = p.get("input")
                if not isinstance(inp, dict):
                    inp = {}
                if arc_hint and p.get("name") == "Bash" and _ARC_MARK in str(inp.get("command", "")):
                    items.append({"i": i, "kind": "arc", "stem": "", "ts": ts})
                elif p.get("name") == "Read":
                    fp = str(inp.get("file_path", ""))
                    if fp.startswith(store_prefix) and fp.endswith(".md") and "/" not in fp[len(store_prefix):]:
                        stem = fp[len(store_prefix):-3]
                        if stem != "MEMORY" and stem not in archive_stems:
                            items.append({"i": i, "kind": "read", "stem": stem, "ts": ts})
    return items


def _tier_sets(auto_mem: Path, snapshot: "dict | None") -> tuple:
    """v0.1.67 (Phase C): → (indexed_stems, archived_stems) for the miss-detector's tier classification.
    From the Phase-0 `--snapshot` dict when given — the state that HELD at window start, so a fact
    archived THIS pass (whose organic reads happened while it was still indexed) is never misclassified
    as a miss (the SKILL's Phase-5 archive steps run BEFORE the --recalls capture — a spec-gate finding).
    Falls back to the live store (documented limitation; the SKILL step always passes the snapshot).
    archived = `](stem.md)` link-targets of archive-index docs, MINUS indexed (indexed wins when both).
    Both classifiers share memory_status's single archive-index rule (_is_archive_index[_text])."""
    if isinstance(snapshot, dict):
        idx_content = ""
        arch_targets: set = set()
        for label, entry in snapshot.items():
            if not (isinstance(label, str) and label.startswith("memory/") and isinstance(entry, dict)):
                continue
            content = str(entry.get("content", "") or "")
            if label == "memory/MEMORY.md":
                idx_content = content
            elif _is_archive_index_text(content):
                arch_targets.update(_LINK_RE.findall(content))
        indexed = frozenset(_LINK_RE.findall(idx_content))
        return indexed, frozenset(arch_targets - indexed)
    indexed = frozenset(index_fact_names(auto_mem / "MEMORY.md"))
    arch: set = set()
    if auto_mem.exists():
        for f in auto_mem.glob("*.md"):
            if f.name == "MEMORY.md" or not _is_archive_index(f):
                continue
            try:
                arch.update(_LINK_RE.findall(f.read_text(encoding="utf-8", errors="replace")))
            except OSError:
                continue
    return indexed, frozenset(arch - indexed)


def recall_scan(project_dir: Path, since: str, before: str = "") -> dict:
    """The --recalls entry: scan the window's transcripts for ORGANIC fact-body Read events → the
    cycle record's `usage` block shape (script-truth; injected via --into, never hand-authored).
    v0.1.67 (Phase C): `before` = the Phase-0 --snapshot path — tier classification for the
    miss-detector (`archive_reads`/`misses`) is judged against that WINDOW-START state when given.
    `misses` derives from the UNCAPPED tally (never the capped per_fact rows — a spec-gate finding:
    a rare archived read must not fall off the cap and vanish), with its own cap."""
    project_dir = project_dir.resolve()
    proj_root = Path.home() / ".claude" / "projects" / slug_for(project_dir)
    auto_mem = proj_root / "memory"
    since = since or _marker_ts(auto_mem)
    store_prefix = str(auto_mem) + "/"
    archive_stems = (frozenset(f.stem for f in auto_mem.glob("*.md") if _is_archive_index(f))
                     if auto_mem.exists() else frozenset())
    transcripts = _window_transcripts(proj_root, since)
    reads: dict = {}     # stem -> {"reads": n, "last": iso} — the UNCAPPED tally
    excluded = 0
    for tr in transcripts:
        organic, dream_n = split_dream_span(_recall_items(tr, store_prefix, since, archive_stems))
        excluded += dream_n
        for r in organic:
            rec = reads.setdefault(r["stem"], {"reads": 0, "last": ""})
            rec["reads"] += 1
            rec["last"] = max(rec["last"], r["ts"] or "")   # CC ISO stamps compare lexicographically
    per_fact = [{"name": k, "reads": v["reads"], "last": v["last"]}
                for k, v in sorted(reads.items(), key=lambda kv: (-kv[1]["reads"], kv[0]))][:_USAGE_FACT_CAP]
    # v0.1.67 (Phase C): the miss-detector — organic reads of ARCHIVED-tier facts. A miss is a
    # transcript-visible demotion error; usage_history folds it into miss_stems (a permanent candidacy
    # veto) and Phase 5 proposes re-promoting the pointer (report-then-apply).
    snap: "dict | None" = None
    if before:
        try:
            _s = json.loads(Path(before).read_text(encoding="utf-8"))
            if isinstance(_s, dict):
                snap = _s
            else:   # valid JSON, wrong shape — warn like the unreadable path (review nit: no silent fallback)
                print("--before: snapshot root is not a JSON object — tier falls back to the LIVE store",
                      file=sys.stderr)
        except (OSError, json.JSONDecodeError, ValueError) as e:
            print(f"--before: unreadable snapshot ({e}) — tier falls back to the LIVE store", file=sys.stderr)
    _archived = _tier_sets(auto_mem, snap)[1]   # [0] (indexed) is _tier_sets-internal (indexed-wins subtraction)
    misses = sorted(k for k in reads if k in _archived)[:_USAGE_FACT_CAP]
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return {"window": f"{since or '(no marker — all transcripts)'}..{now}",
            "transcripts": len(transcripts), "dream_excluded": excluded,
            "reads": sum(v["reads"] for v in reads.values()), "facts_read": len(reads),
            "per_fact": per_fact,
            "archive_reads": sum(v["reads"] for k, v in reads.items() if k in _archived),
            "misses": misses}


def inject_usage(seed_path: str, block: dict) -> bool:
    """Deterministically inject the script-truth `usage` block into a cycle-record seed — wholesale
    assignment (the whole block is script-produced; no model judgment fields to merge around, unlike
    distill's sub-key merge). stderr + False on any failure, so a typo'd path is caught LOUD, never a
    silently-dropped count (the distill --into contract)."""
    try:
        record = json.loads(Path(seed_path).read_text(encoding="utf-8"))
        if not isinstance(record, dict):
            print("--into: skipped (cycle record root is not a JSON object)", file=sys.stderr)
            return False
        record["usage"] = block
        # v0.1.67 (Phase C): close the rank's CURRENT-WINDOW blindness deterministically — the demotion
        # block was seeded at Phase 0 from the LOG, before this window's usage existed; a surfaced stem
        # with reads in the block being injected RIGHT NOW must not stay a candidate (it could be demoted
        # in the very record that shows its reads — a spec-gate finding). Script-truth strike; the SKILL
        # step also instructs the cross-check, but nothing relies on the model doing it.
        demo = record.get("demotion")
        if isinstance(demo, dict) and isinstance(demo.get("surfaced"), list):
            read_stems = {str(r.get("name", "")) for r in (block.get("per_fact") or [])
                          if isinstance(r, dict) and r.get("reads")}
            struck = sorted(s for s in demo["surfaced"] if isinstance(s, str) and s in read_stems)
            if struck:
                demo["surfaced"] = [s for s in demo["surfaced"] if s not in read_stems]
                prev_raw = demo.get("struck")            # assign-then-narrow (the codebase's mypy idiom)
                prev = prev_raw if isinstance(prev_raw, list) else []
                demo["struck"] = sorted({*(x for x in prev if isinstance(x, str)), *struck})
                print(f"demotion: struck {len(struck)} surfaced stem(s) read THIS window — "
                      + ", ".join(_sane(s) for s in struck), file=sys.stderr)
        _write_private(Path(seed_path), json.dumps(record, indent=2, ensure_ascii=False) + "\n")
        print(f"usage → injected into {seed_path}", file=sys.stderr)
        return True
    except (OSError, json.JSONDecodeError, ValueError) as e:
        print(f"--into: skipped ({e}); the scan output above is the fallback", file=sys.stderr)
        return False


def _recalls_report(d: dict) -> None:
    """Human view of the recall scan (reserve --json for machine capture, like the signal report)."""
    print(_ui.rule())
    print("  " + _ui.c("✦ RECALLS · organic fact-body reads this window", "cyan"))
    print(_ui.rule())
    print("  " + _ui.c(f"{d['transcripts']} transcript(s) · {d['dream_excluded']} dream-procedure "
                       f"read(s) excluded · window {d['window']}", "dim"))
    for f in d["per_fact"]:
        # _sane (v0.1.67 review): the stem derives from a transcript Read file_path — terminal-inject guard
        print(f"  {f['reads']:>4} × {_sane(f['name'])}  " + _ui.c(f"last {str(f['last'])[:16]}", "dim"))
    if not d["per_fact"]:
        print("  (no organic fact reads in the window — 0 reads = absence of evidence, not proof of no use)")
    print("  " + _ui.c(f"total {d['reads']} read(s) over {d['facts_read']} fact(s)", "dim"))
    # v0.1.67 (Phase C): the miss-detector — loud, it is the demotion policy's own error signal.
    if d.get("misses"):
        print("  " + _ui.c(f"⚠ demotion MISS: {len(d['misses'])} archived-tier fact(s) read organically "
                           f"({d.get('archive_reads', 0)} read(s)) — " + ", ".join(_sane(m) for m in d["misses"])
                           + " · re-promote the pointer(s) to MEMORY.md (report-then-apply)", "red"))


def main() -> int:
    argv = sys.argv[1:]
    as_json = "--json" in argv
    recalls = "--recalls" in argv   # v0.1.63 (Phase A): the recall-utility scan — its own mode
    argv = [a for a in argv if a not in ("--json", "--recalls")]
    _ui.set_modes(color=_ui.color_enabled(sys.argv[1:], sys.stdout), ascii="--ascii" in sys.argv, width=_ui.resolve_width(sys.argv[1:], sys.stdout))
    since = ""
    into = ""
    before = ""
    max_n = 30
    pos = []
    i = 0
    while i < len(argv):
        if argv[i] == "--since" and i + 1 < len(argv):
            since = argv[i + 1]; i += 2
        elif argv[i] == "--into" and i + 1 < len(argv):   # v0.1.63: --recalls seed-injection target
            into = argv[i + 1]; i += 2
        elif argv[i] == "--before" and i + 1 < len(argv):   # v0.1.67: Phase-0 snapshot → window-start tiering
            before = argv[i + 1]; i += 2
        elif argv[i] == "--max" and i + 1 < len(argv):
            try:
                max_n = max(0, int(argv[i + 1]))
            except ValueError:
                print(f"--max expects an integer, got {argv[i + 1]!r}", file=sys.stderr)
                return 2
            i += 2
        elif not argv[i].startswith("-"):
            pos.append(argv[i]); i += 1
        else:
            i += 1   # skip visual flags (--ascii/--color/--no-color, handled by set_modes) + unknown flags
    project_dir = Path(pos[0]) if pos else Path.cwd()
    if recalls:
        # v0.1.63 (Phase A): the recall scan is a Phase-5 command — no Phase-2 cue here (the phase's
        # beat is already cued by its sibling commands; a wrong-phase cue would misdirect the arc).
        u = recall_scan(project_dir, since, before=before)
        if as_json:
            print(json.dumps(u, indent=2))
        else:
            _recalls_report(u)
        if into and not inject_usage(into, u):
            return 3   # a typo'd seed path FAILS LOUD — counts must never silently drop (distill contract)
        return 0
    if into or before:
        print("warning: --into/--before apply to --recalls only — not captured", file=sys.stderr)
    d = extract(project_dir, since, max_n)
    if as_json:
        print(json.dumps(d, indent=2))
    else:
        _report(d)
    # v0.1.54: write-time dream-arc cue (stderr, CM_DREAM_ARC-gated — see _ui.dream_cue)
    _ui.dream_cue("Phase-2 beat due — the session's signals as dream imagery (plain italics, "
                  "no emoji) above the plain counts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
