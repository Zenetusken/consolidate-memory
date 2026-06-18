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
    re-run doesn't re-surface everything (efficiency).
  - DROP unambiguous noise (harness/skill injections, command echoes, image refs).
  - SECRETS firewall at RETRIEVAL: a turn containing a credential-shaped value is
    dropped to a label — never surface the verbatim secret (it could flow to a
    committed doc). Drop-to-label, not partial-scrub.
  - RANK, don't gate: keyword markers rank/classify turns; non-noise turns are all
    surfaced (recall-biased) up to --max, lowest-signal acks last.
  - SCOPE HINT per candidate (user|env|project) to pre-stage routing.

Usage: extract_signals.py [PROJECT_DIR] [--since ISO_TS] [--max N] [--json]
       (default --since: the marker timestamp; default --max 30)
"""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path

import _ui  # sibling script: the shared visual vocabulary (color / rule / kv / glyphs)

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
    r"^\s*(<local-command-|<command-|<task-notification|<teammate-message|Caveat:|"
    r"Base directory for this skill:|This session is being continued|\[Image:|\[Request interrupted)",
    re.I,
)
# Skill-prompt injections (e.g. the code-review skill's effort header).
_SKILL_PROMPT = re.compile(r"(effort\s*→|angles\s*×|candidates\s*→|1-vote verify|# Consolidate Memory)", re.I)

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

# Signal markers → (signal_type, scope_hint). Order = priority.
_MARKERS = [
    ("correction", "user", re.compile(r"\b(actually|instead of|should(n'?t)?|why .* when|not just|i meant)\b", re.I)),
    ("preference", "user", re.compile(r"\b(never|always|prefer|make sure|ensure|don'?t|do not|properly|at the root|pin .*test|validate|fully|end.to.end|autonomous|verify)\b", re.I)),
    ("constraint", "project", re.compile(r"\b(i (rely|am based|use|need|want)|my (real|actual)|production|based in|account)\b", re.I)),
    ("decision", "project", re.compile(r"\b(table (it|this|the)|use .* not |go with|start(ing)? with|first,|tune .* first)\b", re.I)),
]


def _latest_transcript(proj_root: Path) -> Path | None:
    ts = sorted(proj_root.glob("*.jsonl"), key=lambda p: p.stat().st_mtime)
    return ts[-1] if ts else None


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
    """Return (signal_type, scope_hint, score). Markers rank; they never gate."""
    if _ACK.match(text):
        return ("ack", "project", 0)
    for stype, scope, rx in _MARKERS:
        if rx.search(text):
            return (stype, scope, 2)
    return ("statement", "project", 1)  # non-noise, no marker — still surfaced


def extract(project_dir: Path, since: str, max_n: int) -> dict:
    project_dir = project_dir.resolve()
    proj_root = Path.home() / ".claude" / "projects" / str(project_dir).replace("/", "-")
    auto_mem = proj_root / "memory"
    since = since or _marker_ts(auto_mem)
    transcript = _latest_transcript(proj_root)

    counts = {"human_seen": 0, "noise": 0, "secrets_omitted": 0, "errors": 0}
    human: list[dict] = []
    errors: list[dict] = []
    if not transcript:
        return {"transcript": None, "since": since, "counts": counts, "signals": []}

    with transcript.open(encoding="utf-8", errors="replace") as f:
        for line in f:
            try:
                o = json.loads(line)
            except (json.JSONDecodeError, RecursionError, ValueError):
                # skip one malformed/pathological line (incl. deeply-nested JSON that
                # blows the recursion limit) rather than aborting the whole stream
                continue
            ts = o.get("timestamp", "")
            if since and ts and ts <= since:  # scope to marker
                continue
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
                            if _looks_secret(tn[:_PROBE_CAP]):
                                counts["secrets_omitted"] += 1
                                errors.append({"source": "error", "ts": ts, "scope_hint": "-",
                                               "text": "(omitted: error tool-result contained a credential-shaped value)"})
                            else:
                                errors.append({"source": "error", "ts": ts,
                                               "text": tn[:200], "scope_hint": "env"})
                # human turns
                text = _human_text(msg)
                if not text:
                    continue
                counts["human_seen"] += 1
                # Normalize ONCE, then scan AND store the same representation, so the
                # firewall examines exactly what would be persisted (no scan/store offset
                # mismatch). _PROBE_CAP bounds regex work (ReDoS/blow-up guard); the stored
                # excerpt (norm[:300]) is well within it, so everything stored is scanned.
                norm = _norm(text)
                probe = norm[:_PROBE_CAP]
                if _NOISE.match(probe) or _SKILL_PROMPT.search(probe[:200]):
                    counts["noise"] += 1
                    continue
                if _looks_secret(probe):
                    counts["secrets_omitted"] += 1
                    human.append({"source": "human", "ts": ts, "signal_type": "omitted",
                                  "scope_hint": "-", "score": -1,
                                  "text": "(omitted: turn contained a credential-shaped value)"})
                    continue
                stype, scope, score = _classify(probe)
                human.append({"source": "human", "ts": ts, "signal_type": stype, "scope_hint": scope,
                              "score": score, "text": norm[:300]})

    # dedup error-results (the same tool error often repeats verbatim). Explicit loop
    # rather than the `... or seen.add(x)` comprehension trick: set.add returns None (a
    # value mypy rightly flags as unusable in a boolean), so ADD first, then use the set.
    seen: set[str] = set()
    deduped: list[dict] = []
    for e in errors:
        if e["text"] in seen:
            continue
        seen.add(e["text"])
        deduped.append(e)
    errors = deduped
    # rank human turns: high-signal first, acks last; cap at max_n. Keep ONE
    # omitted-secret label for transparency (the consolidation should know a
    # credential-bearing turn was skipped), but never the value.
    human.sort(key=lambda d: d.get("score", 0), reverse=True)
    surfaced = [s for s in human if s.get("score", 0) >= 0][:max_n]
    if counts["secrets_omitted"]:
        surfaced.append({"source": "human", "signal_type": "omitted", "scope_hint": "-",
                         "text": f"({counts['secrets_omitted']} turn(s) omitted — credential-shaped value)"})
    signals = surfaced + errors
    counts["surfaced"] = len(signals)
    return {"transcript": transcript.name, "since": since or "(none — first pass)",
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
    add("  " + _ui.c(f"{d['transcript']} · since {d['since']}", "dim"))
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
        add(f"    {_ui.c(g, col)} {_ui.lbl(f'{meta[:26]:<26}')} {s['text']}")
    print(_ui.ascii_translate("\n".join(out)))


def main() -> int:
    argv = sys.argv[1:]
    as_json = "--json" in argv
    argv = [a for a in argv if a != "--json"]
    _ui.set_modes(color=_ui.color_enabled(sys.argv[1:], sys.stdout), ascii="--ascii" in sys.argv)
    since = ""
    max_n = 30
    pos = []
    i = 0
    while i < len(argv):
        if argv[i] == "--since" and i + 1 < len(argv):
            since = argv[i + 1]; i += 2
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
    d = extract(project_dir, since, max_n)
    if as_json:
        print(json.dumps(d, indent=2))
    else:
        _report(d)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
