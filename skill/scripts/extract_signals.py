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
from pathlib import Path

STATE_FILE = ".consolidation-state.json"

# Unambiguous noise — harness/skill injections and command echoes, not human intent.
_NOISE = re.compile(
    r"^\s*(<local-command-|<command-|Caveat:|Base directory for this skill:|"
    r"This session is being continued|\[Image:|\[Request interrupted)",
    re.I,
)
# Skill-prompt injections (e.g. the code-review skill's effort header).
_SKILL_PROMPT = re.compile(r"(effort\s*→|angles\s*×|candidates\s*→|1-vote verify|# Consolidate Memory)", re.I)

# Credential-shaped values — drop the whole turn to a label if any match.
_SECRET = re.compile(
    r"([A-Za-z0-9+/_-]{40,}={0,2})"  # long base64/token blob
    r"|((?:li_at|cf_clearance|password|api[_-]?key|secret|token|bearer)\s*[:=]\s*\S+)",
    re.I,
)

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
            except json.JSONDecodeError:
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
                            errors.append({"source": "error", "ts": ts,
                                           "text": " ".join(str(t).split())[:200], "scope_hint": "env"})
                # human turns
                text = _human_text(msg)
                if not text:
                    continue
                counts["human_seen"] += 1
                if _NOISE.match(text) or _SKILL_PROMPT.search(text[:200]):
                    counts["noise"] += 1
                    continue
                if _SECRET.search(text):
                    counts["secrets_omitted"] += 1
                    human.append({"source": "human", "ts": ts, "signal_type": "omitted",
                                  "scope_hint": "-", "score": -1,
                                  "text": "(omitted: turn contained a credential-shaped value)"})
                    continue
                stype, scope, score = _classify(text)
                human.append({"source": "human", "ts": ts, "signal_type": stype, "scope_hint": scope,
                              "score": score, "text": " ".join(text.split())[:300]})

    # dedup error-results (the same tool error often repeats verbatim)
    seen: set[str] = set()
    errors = [e for e in errors if not (e["text"] in seen or seen.add(e["text"]))]
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
    print("=" * 72)
    print("CONSOLIDATE-MEMORY — session signal extraction")
    print("=" * 72)
    print(f"transcript : {d['transcript']}")
    print(f"since      : {d['since']}")
    print(f"counts     : {c.get('human_seen',0)} human turns seen · {c.get('noise',0)} noise dropped · "
          f"{c.get('secrets_omitted',0)} secrets omitted · {c.get('errors',0)} error-results · "
          f"{c.get('surfaced',0)} surfaced")
    print("\n--- candidates (ranked; verify + dedup before recording) ---")
    for s in d["signals"]:
        tag = f"{s['source']}/{s.get('signal_type','err')}·{s.get('scope_hint','?')}"
        print(f"  [{tag:>26}] {s['text']}")


def main() -> int:
    argv = sys.argv[1:]
    as_json = "--json" in argv
    argv = [a for a in argv if a != "--json"]
    since = ""
    max_n = 30
    pos = []
    i = 0
    while i < len(argv):
        if argv[i] == "--since" and i + 1 < len(argv):
            since = argv[i + 1]; i += 2
        elif argv[i] == "--max" and i + 1 < len(argv):
            max_n = int(argv[i + 1]); i += 2
        else:
            pos.append(argv[i]); i += 1
    project_dir = Path(pos[0]) if pos else Path.cwd()
    d = extract(project_dir, since, max_n)
    if as_json:
        print(json.dumps(d, indent=2))
    else:
        _report(d)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
