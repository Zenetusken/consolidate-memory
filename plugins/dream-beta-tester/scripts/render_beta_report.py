#!/usr/bin/env python3
"""Dream beta-harness — the RUN-SHAPED report renderer (SPEC §6).

Turns the deterministic oracle's JSON (`beta_checks.py --json`) + the dream's own
rendered dashboard into one structured, version-stamped Markdown report per run. This is
the "model produces data, script renders" split the dream itself uses: ZERO judgment lives
here — every classification is a deterministic function of the oracle payload (+ an optional
freshly-captured rendered surface for the honesty re-verification grep).

This is CONSUMER / beta-tester tooling. It lives OUTSIDE the consolidate-memory skill
(`~/.claude/dream-beta-tester/`) and NEVER patches it.

Report shape (SPEC §6 / the build-plan ARTIFACT 3 contract):

  1. DREAM DASHBOARD — the skill's own rendered output, VERBATIM (the consumer artifact),
     passed in via --dashboard. Omitted-with-a-note when not supplied (scripts-only runs may
     not have a single dashboard; the oracle's surfaces still drive sections 2-3).

  2. BETA FINDINGS — only what THIS run surfaced, in TWO structurally separate groups
     (advisor honesty fix — never blur confirmed with suspected). The prototype empirically
     shipped 3 confident-wrong FAILs (D1/D3/D5) on clean v0.1.21 data, so the split is the
     load-bearing honesty guarantee:
       * (2a) ORACLE-DETECTED, itself split into:
           - 2a-VERIFIED : a FAIL/WARN whose evidence is a literal QUOTED substring of the
             skill's REAL rendered output (oracle `basis == "rendered"` AND a non-empty
             `quote`) — the same quoted-source-contradiction bar §4.2 imposes on lens findings.
             If a freshly-captured rendered surface is supplied (--rendered), the quote is
             RE-GREPPED against it on the critical path; a quote that no longer matches is
             DOWNGRADED to 2a-FLAGGED (the cheap deterministic re-verification q1/q2 mandate).
           - 2a-FLAGGED  : a FAIL/WARN whose evidence is a reconstructed `--json`/recompute
             proxy (basis "reconstructed" | "structural", or a quote that failed re-grep) →
             "oracle-flagged, unconfirmed against rendered output", counted SEPARATELY, never
             as a confirmed defect.
       * (2b) JUDGMENT-FLAGGED (UNVERIFIED) — the lens layer (SPEC §4.2). DEFERRED for the
         core build; the footer DISCLOSES "lens layer deferred" as a stated coverage gap so an
         empty 2b is never read as "no judgment findings", only "judgment not run".

  3. RUN DELTA — vs. the prior report for this repo (matched by repo+slug, older skill
     version): each finding tagged new | known(Dn) | regressed | fixed by diffing this run's
     per-check status against the prior run's. This is the cross-version regression signal
     (SPEC §8). No prior report → every finding is `new` and the delta says so.

  Footer: counts; consolidate-memory VERSION under test; the resolved scripts path (the
  auditable binding); snapshot/restore disposition; a COVERAGE line enumerating which families
  ran vs SKIPped (so an empty FINDINGS section is qualified "N families ran, M skipped", never
  mis-read as verified-clean); and the lens-layer-deferred disclosure.

Usage:
    python3 render_beta_report.py --oracle ORACLE.json [options]
      --oracle FILE        the beta_checks.py --json payload ('-' = stdin)              [required]
      --dashboard FILE     the dream's rendered dashboard, included verbatim as section 1
      --rendered FILE      a freshly-captured skill rendered surface (the memory_status human
                           report / render_dashboard / --triage stdout, concatenated). Each
                           2a-VERIFIED quote is RE-GREPPED against this text; a miss downgrades
                           that finding to 2a-FLAGGED. Omit to trust the oracle's own stamp.
      --prior FILE         the prior report .md for this repo (for the RUN DELTA). If omitted,
                           --reports-dir is scanned for the newest matching prior report.
      --reports-dir DIR    where reports live (default: <this script>/reports). Used to
                           auto-discover the prior report AND to write this one.
      --snapshot FILE      snapshot.py disposition JSON (restored / kept / changed files) for
                           the footer; or use --restored / --kept / --snapshot-note.
      --restored           footer disposition = "store restored to pre-dream state"
      --kept               footer disposition = "consolidation KEPT (writes retained)"
      --snapshot-note STR  free-text snapshot/restore disposition for the footer
      --lens FILE          (optional) JSON list of judgment-flagged lens observations for 2b;
                           absent → 2b is empty + the footer discloses the lens layer deferred
      --out FILE           write the Markdown here (default: stdout). '-' forces stdout.
      --write              write to reports/<slug>__<cmver>__<ts>.md under --reports-dir and
                           print the path (ignored if --out is given)
      --json               emit the structured report model as JSON instead of Markdown

Exit code: 1 if any finding is in 2a-VERIFIED (a confirmed defect shipped this run), else 0.
A parse/usage error is 2. (2a-FLAGGED and 2b never set a non-zero exit — they are unconfirmed.)
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ─────────────────────────────── constants ───────────────────────────────

_SEV_ORDER = {"HIGH": 0, "MED": 1, "LOW": 2}
_STATUS_RANK = {"FAIL": 0, "WARN": 1, "SKIP": 2, "PASS": 3}
# A finding's evidence is a CONFIRMED quoted source-contradiction only when the oracle grounded
# it in a literal line from a RENDERED skill surface. Everything else (a --json proxy, a recompute)
# is unconfirmed-against-rendered-output and must ship as 2a-FLAGGED, never a confirmed defect.
_RENDERED_BASIS = "rendered"
# Statuses that constitute a "finding" worth cataloguing (PASS/SKIP are not findings).
_FINDING_STATUSES = ("FAIL", "WARN")

_DELTA_NEW = "new"
_DELTA_KNOWN = "known"  # rendered as known(Dn)
_DELTA_REGRESSED = "regressed"
_DELTA_FIXED = "fixed"


# ─────────────────────────────── model ───────────────────────────────


@dataclass
class Finding:
    """One oracle result, projected into the report's vocabulary."""

    family: str
    id: str
    title: str
    severity: str
    status: str  # FAIL | WARN (findings only; PASS/SKIP are summarised, not listed)
    expected: str
    actual: str
    evidence: str
    site: str
    defect_ref: str
    basis: str
    quote: str
    group: str  # "2a-VERIFIED" | "2a-FLAGGED"
    verification: str  # how the group was decided (auditable, honest about basis)
    delta: str = _DELTA_NEW  # new | known | regressed | fixed
    delta_detail: str = ""  # e.g. the Dn for known/regressed/fixed

    @property
    def key(self) -> str:
        """Stable identity for cross-run diffing — the check id, scoped by family+site so a
        family that fires on multiple sites tracks each site independently across runs."""
        return f"{self.family}::{self.id}::{self.site}"


@dataclass
class ReportModel:
    repo: str
    repo_name: str
    store: str
    store_present: bool
    store_absent: bool
    skill_path: str
    skill_version: str
    generated_at: str
    summary: dict[str, int]
    families_ran: list[str]
    families_skipped: list[str]
    notes: list[str]
    dashboard: str | None
    verified: list[Finding]  # 2a-VERIFIED
    flagged: list[Finding]  # 2a-FLAGGED
    lens: list[dict[str, Any]]  # 2b (judgment) — empty in the core build
    lens_deferred: bool
    rendered_reverified: bool  # did we re-grep quotes against a fresh rendered surface?
    prior_report: str | None
    prior_skill_version: str | None
    delta_new: list[Finding] = field(default_factory=list)
    delta_known: list[Finding] = field(default_factory=list)
    delta_regressed: list[Finding] = field(default_factory=list)
    delta_fixed: list[dict[str, str]] = field(default_factory=list)  # checks that left findings
    snapshot_disposition: str = "not recorded (no snapshot info supplied)"


# ─────────────────────────────── helpers ───────────────────────────────


def slug_for(repo: Path) -> str:
    """Claude Code project slug: the absolute path with EVERY non-alphanumeric char → '-' (case kept).

    Identical to the skill's / oracle's rule (v0.1.40 M3: re.sub(r'[^A-Za-z0-9]', '-', ...)) so reports for
    one repo share a stable filename prefix across runs (the cross-version diff hinges on this match)."""
    return re.sub(r"[^A-Za-z0-9]", "-", str(repo.resolve()))


def _read_text(path: str) -> str:
    if path == "-":
        return sys.stdin.read()
    return Path(path).expanduser().read_text(encoding="utf-8", errors="replace")


def _load_oracle(path: str) -> dict[str, Any]:
    raw = _read_text(path)
    obj = json.loads(raw)
    if not isinstance(obj, dict):
        raise ValueError("oracle payload is not a JSON object")
    if "results" not in obj or not isinstance(obj["results"], list):
        raise ValueError("oracle payload missing a 'results' array")
    return obj


def _normalize_grep(text: str) -> str:
    """Collapse a rendered line the way the oracle's `_grep_quote` does — strip control/box-drawing
    bytes and collapse whitespace — so a quote captured by the oracle re-matches a freshly-captured
    surface regardless of ANSI/asciification differences."""
    return re.sub(r"\s+", " ", re.sub(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]", "", text)).strip()


def _quote_present_in(rendered: str, quote: str) -> bool:
    """Is `quote` (an oracle-captured rendered line) actually present in a fresh rendered surface?

    The oracle stores quotes already normalized (control-stripped, whitespace-collapsed). We
    normalize each line of the fresh surface the same way and look for the quote as a substring,
    so trailing punctuation / wrapping differences don't cause a false downgrade. A short or empty
    quote can't be re-verified (too weak to ground) → treated as absent."""
    q = _normalize_grep(quote)
    if len(q) < 8:  # too short to be a meaningful source-contradiction anchor
        return False
    rn = _normalize_grep(rendered)
    if q in rn:
        return True
    # also try line-wise (the oracle grof a single line; the fresh surface may wrap differently)
    return any(q in _normalize_grep(line) for line in rendered.splitlines())


def _classify(result: dict[str, Any], rendered: str | None) -> tuple[str, str]:
    """Decide the report group (2a-VERIFIED | 2a-FLAGGED) for one oracle finding + a reason string.

    The bar for 2a-VERIFIED (the honesty fix): the oracle grounded this finding in a literal line
    from a RENDERED skill surface (basis == 'rendered' AND a non-empty quote). When a fresh rendered
    surface is supplied, the quote is RE-GREPPED against it on the critical path — a quote that no
    longer appears is downgraded to 2a-FLAGGED ('was rendered-quoted, no longer matches'). Everything
    else (a reconstructed --json proxy, a structural recompute) is 2a-FLAGGED: real oracle signal, but
    NOT confirmed against the skill's own rendered words, so never counted as a confirmed defect."""
    basis = str(result.get("basis", "")).strip()
    quote = str(result.get("quote", "")).strip()
    if basis == _RENDERED_BASIS and quote:
        if rendered is not None and not _quote_present_in(rendered, quote):
            return (
                "2a-FLAGGED",
                "oracle stamped 'rendered' but the quote did NOT re-grep against the freshly-captured "
                "surface — downgraded (re-verification miss)",
            )
        if rendered is not None:
            return (
                "2a-VERIFIED",
                "quoted source-contradiction RE-GREPPED against a freshly-captured rendered surface",
            )
        return (
            "2a-VERIFIED",
            "oracle grounded this in a literal quoted line from a rendered skill surface (basis=rendered)",
        )
    return (
        "2a-FLAGGED",
        f"evidence is a reconstructed/recomputed proxy (basis={basis or 'unknown'}), not a quoted "
        "rendered-output contradiction — unconfirmed against the skill's rendered words",
    )


def _to_finding(result: dict[str, Any], rendered: str | None) -> Finding:
    group, reason = _classify(result, rendered)
    return Finding(
        family=str(result.get("family", "?")),
        id=str(result.get("id", "?")),
        title=str(result.get("title", "")),
        severity=str(result.get("severity", "LOW")).upper(),
        status=str(result.get("status", "")).upper(),
        expected=str(result.get("expected", "")),
        actual=str(result.get("actual", "")),
        evidence=str(result.get("evidence", "")),
        site=str(result.get("site", "")),
        defect_ref=str(result.get("defect_ref", "")),
        basis=str(result.get("basis", "")),
        quote=str(result.get("quote", "")),
        group=group,
        verification=reason,
    )


# ─────────────────────────────── prior-report parsing (RUN DELTA) ───────────────────────────────

# The renderer embeds a machine-readable fingerprint block in every report it writes, so the NEXT
# run can diff against it without re-parsing prose. This keeps the cross-version delta deterministic
# and robust to Markdown reflow. The block is a fenced JSON object tagged below.
_FINGERPRINT_OPEN = "<!-- beta-report-fingerprint"
_FINGERPRINT_CLOSE = "beta-report-fingerprint -->"


def _fingerprint(model: ReportModel) -> dict[str, Any]:
    """The cross-run state the next report diffs against: per-check status keyed by Finding.key,
    plus the version + repo for matching. Only FAIL/WARN findings are 'open'; everything else is
    recorded as cleared so a later run can detect a fix (a previously-open key now absent)."""
    checks: dict[str, dict[str, str]] = {}
    for f in [*model.verified, *model.flagged]:
        checks[f.key] = {
            "status": f.status,
            "severity": f.severity,
            "group": f.group,
            "defect_ref": f.defect_ref,
            "title": f.title,
        }
    return {
        "repo": model.repo,
        "skill_version": model.skill_version,
        "generated_at": model.generated_at,
        "open_checks": checks,
    }


def _embed_fingerprint(model: ReportModel) -> str:
    fp = json.dumps(_fingerprint(model), indent=2)
    return f"{_FINGERPRINT_OPEN}\n{fp}\n{_FINGERPRINT_CLOSE}"


def _parse_fingerprint(report_text: str) -> dict[str, Any] | None:
    """Extract the embedded fingerprint JSON from a prior report, or None if absent/unparseable."""
    start = report_text.find(_FINGERPRINT_OPEN)
    if start == -1:
        return None
    start += len(_FINGERPRINT_OPEN)
    end = report_text.find(_FINGERPRINT_CLOSE, start)
    if end == -1:
        return None
    blob = report_text[start:end].strip()
    try:
        obj = json.loads(blob)
    except json.JSONDecodeError:
        return None
    return obj if isinstance(obj, dict) else None


def _discover_prior(reports_dir: Path, slug: str, exclude: Path | None) -> Path | None:
    """The newest prior report for this repo-slug under `reports_dir` (excluding the one we're about
    to write). Reports are named `<slug>__<cmver>__<ts>.md`; we match the slug prefix and pick the
    lexicographically-greatest filename (the embedded ISO-ish timestamp sorts chronologically)."""
    if not reports_dir.is_dir():
        return None
    cands = sorted(
        (p for p in reports_dir.glob(f"{slug}__*.md") if p.is_file() and p != exclude),
        key=lambda p: p.name,
    )
    return cands[-1] if cands else None


def _apply_delta(model: ReportModel, prior_text: str | None) -> None:
    """Tag each finding new | known(Dn) | regressed | fixed vs. the prior report, and collect the
    'fixed' set (checks that had a finding before and are clean now). Deterministic, key-based.

    Lifecycle rules (SPEC §4.3 / §8):
      * a check key present in the prior fingerprint AND still a finding now → `known` (carry its
        defect_ref as Dn). If it WORSENED (WARN→FAIL or moved 2a-FLAGGED→2a-VERIFIED) → `regressed`.
      * a check key NOT in the prior fingerprint (or no prior at all) → `new`.
      * a check key that WAS a finding in the prior fingerprint but is NOT a finding now → `fixed`
        (a FAIL/WARN→PASS/SKIP transition across versions — the regression-gate's positive signal).
    """
    fp = _parse_fingerprint(prior_text) if prior_text else None
    prior_checks: dict[str, dict[str, str]] = (fp or {}).get("open_checks", {}) if fp else {}
    model.prior_skill_version = (fp or {}).get("skill_version") if fp else None

    now_keys: set[str] = set()
    for f in [*model.verified, *model.flagged]:
        now_keys.add(f.key)
        prev = prior_checks.get(f.key)
        dn = f.defect_ref or (prev or {}).get("defect_ref", "")
        if prev is None:
            f.delta, f.delta_detail = _DELTA_NEW, ""
            model.delta_new.append(f)
            continue
        # present before and now → known, unless it worsened.
        worsened = (
            _STATUS_RANK.get(f.status, 9) < _STATUS_RANK.get(prev.get("status", "PASS"), 9)
        ) or (prev.get("group") == "2a-FLAGGED" and f.group == "2a-VERIFIED")
        if worsened:
            f.delta, f.delta_detail = _DELTA_REGRESSED, dn
            model.delta_regressed.append(f)
        else:
            f.delta, f.delta_detail = _DELTA_KNOWN, dn
            model.delta_known.append(f)

    # fixed: a prior finding key that is no longer a finding this run.
    for key, prev in prior_checks.items():
        if key not in now_keys:
            model.delta_fixed.append(
                {
                    "key": key,
                    "defect_ref": prev.get("defect_ref", ""),
                    "title": prev.get("title", ""),
                    "prior_status": prev.get("status", ""),
                    "delta": _DELTA_FIXED,
                }
            )


# ─────────────────────────────── build the model ───────────────────────────────


def build_model(
    oracle: dict[str, Any],
    *,
    dashboard: str | None,
    rendered: str | None,
    lens: list[dict[str, Any]] | None,
    snapshot_disposition: str,
    generated_at: str,
) -> ReportModel:
    results: list[dict[str, Any]] = oracle.get("results", [])
    findings_raw = [r for r in results if str(r.get("status", "")).upper() in _FINDING_STATUSES]
    findings = [_to_finding(r, rendered) for r in findings_raw]

    # severity-then-status ordering within each group (HIGH FAILs first).
    def _order(f: Finding) -> tuple[int, int, str, str]:
        return (_SEV_ORDER.get(f.severity, 9), _STATUS_RANK.get(f.status, 9), f.family, f.id)

    verified = sorted((f for f in findings if f.group == "2a-VERIFIED"), key=_order)
    flagged = sorted((f for f in findings if f.group == "2a-FLAGGED"), key=_order)

    summary = oracle.get("summary", {}) or {}
    repo = str(oracle.get("repo", ""))
    model = ReportModel(
        repo=repo,
        repo_name=Path(repo).name if repo else "?",
        store=str(oracle.get("store", "")),
        store_present=bool(oracle.get("store_present", False)),
        store_absent=bool(oracle.get("store_absent", False)),
        skill_path=str(oracle.get("skill", "")),
        skill_version=str(oracle.get("skill_version", "unknown")),
        generated_at=generated_at,
        summary=summary,
        families_ran=list(oracle.get("families_ran", [])),
        families_skipped=list(oracle.get("families_skipped", [])),
        notes=list(oracle.get("notes", [])),
        dashboard=dashboard,
        verified=verified,
        flagged=flagged,
        lens=lens or [],
        lens_deferred=not lens,
        rendered_reverified=rendered is not None,
        prior_report=None,
        prior_skill_version=None,
        snapshot_disposition=snapshot_disposition,
    )
    return model


# ─────────────────────────────── Markdown rendering ───────────────────────────────


def _md_finding(f: Finding) -> list[str]:
    """One finding as a Markdown block. Honest about basis + verification + lifecycle tag."""
    tag = f.delta if f.delta != _DELTA_KNOWN else f"known({f.delta_detail or f.defect_ref or '?'})"
    if f.delta == _DELTA_REGRESSED and (f.delta_detail or f.defect_ref):
        tag = f"regressed({f.delta_detail or f.defect_ref})"
    lines = [
        f"#### `{f.id}` · {f.severity} · {f.status} · {f.title}",
        "",
        f"- **family · site:** `{f.family}` · `{f.site}`",
        f"- **lifecycle:** {tag}"
        + (
            f"  ·  motivating catalog item: {f.defect_ref}"
            if f.defect_ref and f.defect_ref != "-"
            else ""
        ),
        f"- **expected:** {f.expected}",
        f"- **actual:** {f.actual}",
        f"- **evidence:** {f.evidence}",
    ]
    if f.quote.strip():
        lines.append(f"- **quoted from rendered output:** `{f.quote.strip()}`")
    lines.append(f"- **basis:** {f.basis or 'unknown'}  ·  **classification:** {f.verification}")
    lines.append("")
    return lines


def _render_markdown(model: ReportModel) -> str:
    L: list[str] = []
    a = L.append

    # ── title ──
    a(f"# Dream beta-test report — {model.repo_name}")
    a("")
    a(f"- **repo:** `{model.repo}`")
    a(
        f"- **memory store:** `{model.store}`"
        + (
            ""
            if model.store_present
            else "  _(ABSENT — never-dreamed repo; store-dependent families SKIP)_"
        )
    )
    a(f"- **consolidate-memory under test:** `v{model.skill_version}`")
    a(f"- **skill scripts (resolved binding):** `{model.skill_path}`")
    a(f"- **generated:** {model.generated_at}")
    a("")

    # one-line verdict up top (run-shaped): the only thing that constitutes a confirmed defect is 2a-VERIFIED.
    nverified, nflagged = len(model.verified), len(model.flagged)
    if model.store_absent:
        verdict = "CLEAN — never-dreamed repo (no store); nothing to verify"
    elif nverified:
        verdict = f"{nverified} CONFIRMED defect(s) this run (2a-VERIFIED)"
    elif nflagged:
        verdict = f"CLEAN of confirmed defects; {nflagged} oracle-flagged (unconfirmed) item(s) for triage"
    else:
        verdict = "CLEAN — no findings this run"
    a(f"> **Verdict:** {verdict}.")
    a("")
    a("---")
    a("")

    # ── Section 1: DREAM DASHBOARD (verbatim) ──
    a("## 1. Dream dashboard")
    a("")
    if model.dashboard and model.dashboard.strip():
        a("_The consolidate-memory skill's own rendered output, verbatim (the consumer artifact)._")
        a("")
        a("```text")
        # never let a stray fence in the dashboard break out of the block
        a(model.dashboard.replace("```", "ʼʼʼ").rstrip("\n"))
        a("```")
    else:
        a(
            "_No dashboard was supplied to the renderer for this run._ The oracle drove the skill's "
            "read-only surfaces directly; sections 2–3 reflect those. (In a full-dream run the dream's "
            "rendered dashboard is captured and embedded here verbatim.)"
        )
    a("")
    a("---")
    a("")

    # ── Section 2: BETA FINDINGS ──
    a("## 2. Beta findings")
    a("")
    a(
        "_Only what THIS run surfaced. Two structurally separate groups: deterministically confirmed "
        "vs. judgment-flagged — confirmed is never blurred with suspected (the D1/D2-retraction "
        "honesty discipline)._"
    )
    a("")

    # 2a-VERIFIED
    a("### 2a-VERIFIED — deterministically confirmed (quoted source-contradiction)")
    a("")
    a(
        "_An oracle finding admitted here ONLY because its evidence is a literal quoted substring of "
        "the skill's REAL rendered output"
        + (
            " (re-grepped against a freshly-captured rendered surface this run)"
            if model.rendered_reverified
            else " (as captured by the oracle; pass --rendered to re-grep on the critical path)"
        )
        + ". These are confirmed defects._"
    )
    a("")
    if model.verified:
        for f in model.verified:
            L.extend(_md_finding(f))
    else:
        a(
            "_None._ No oracle finding this run was grounded in a quoted rendered-output contradiction."
        )
        a("")

    # 2a-FLAGGED
    a("### 2a-FLAGGED — oracle-flagged, UNCONFIRMED against rendered output")
    a("")
    a(
        "_Real oracle signal from a reconstructed `--json` proxy or a structural recompute, NOT a "
        "quoted rendered-output contradiction. Counted separately; NEVER counted as a confirmed "
        "defect. These are hypotheses for triage (the prototype shipped 3 confident-wrong FAILs on "
        "clean data — this is the guardrail)._"
    )
    a("")
    if model.flagged:
        for f in model.flagged:
            L.extend(_md_finding(f))
    else:
        a("_None._")
        a("")

    # 2b judgment
    a("### 2b — judgment-flagged (UNVERIFIED)")
    a("")
    if model.lens:
        a(
            "_Lens observations (SPEC §4.2). Shipped explicitly as hypotheses for human triage — "
            "NOT counted as defects until they reduce to a check or a quoted source-contradiction._"
        )
        a("")
        for obs in model.lens:
            lens_name = str(obs.get("lens", "?"))
            sev = str(obs.get("severity", "")).upper()
            note = str(obs.get("observation", obs.get("note", "")))
            site = str(obs.get("site", ""))
            head = f"#### {lens_name} lens" + (f" · {sev}" if sev else "")
            a(head)
            a("")
            if site:
                a(f"- **site:** `{site}`")
            a(f"- **observation:** {note}")
            a("- **status:** UNVERIFIED — judgment-flagged, not a confirmed defect.")
            a("")
    else:
        a(
            "_Lens layer DEFERRED for this build (scripts-only, deterministic floor only). This "
            "section is empty because the judgment lenses were not run, **not** because no judgment "
            "findings exist. See the coverage line in the footer._"
        )
        a("")
    a("---")
    a("")

    # ── Section 3: RUN DELTA ──
    a("## 3. Run delta")
    a("")
    if model.prior_report:
        pv = model.prior_skill_version or "?"
        a(
            f"_Versus the prior report for this repo: `{Path(model.prior_report).name}` "
            f"(consolidate-memory v{pv} → v{model.skill_version})._"
        )
    else:
        a(
            "_No prior report found for this repo under the reports dir — this is the BASELINE run; "
            "every finding is `new` and there is nothing to mark fixed/regressed yet._"
        )
    a("")

    def _delta_line(f: Finding) -> str:
        return f"- `{f.id}` · {f.severity} · {f.status} · {f.group} — {f.title}"

    a(f"- **newly broken (new):** {len(model.delta_new)}")
    for f in model.delta_new:
        a("  " + _delta_line(f).lstrip("- ").rstrip())
    a(f"- **still open (known):** {len(model.delta_known)}")
    for f in model.delta_known:
        a(
            "  "
            + _delta_line(f).lstrip("- ").rstrip()
            + (f"  [{f.defect_ref}]" if f.defect_ref and f.defect_ref != "-" else "")
        )
    a(f"- **regressed (PASS→finding or worsened):** {len(model.delta_regressed)}")
    for f in model.delta_regressed:
        a("  " + _delta_line(f).lstrip("- ").rstrip())
    a(f"- **fixed (prior finding now clean):** {len(model.delta_fixed)}")
    for fx in model.delta_fixed:
        ref = f"  [{fx['defect_ref']}]" if fx.get("defect_ref") and fx["defect_ref"] != "-" else ""
        a(f"  {fx['key']} — {fx.get('title', '')} (was {fx.get('prior_status', '?')}){ref}")
    a("")
    a("---")
    a("")

    # ── Footer ──
    a("## Footer")
    a("")
    s = model.summary
    a(
        f"- **finding counts:** {len(model.verified)} verified (2a-VERIFIED) · "
        f"{len(model.flagged)} flagged (2a-FLAGGED) · {len(model.lens)} judgment (2b)"
    )
    a(
        f"- **oracle tally:** {s.get('fail', 0)} FAIL · {s.get('warn', 0)} WARN · "
        f"{s.get('pass', 0)} PASS · {s.get('skip', 0)} SKIP (of {s.get('total', 0)} checks)"
    )
    a(f"- **consolidate-memory version under test:** v{model.skill_version}")
    a(f"- **resolved skill scripts path:** `{model.skill_path}`")
    a(f"- **snapshot / restore disposition:** {model.snapshot_disposition}")
    # COVERAGE — qualifies an empty findings section so it is never mis-read as verified-clean.
    ran = ", ".join(model.families_ran) or "(none)"
    skipped = ", ".join(model.families_skipped) or "(none)"
    a(
        f"- **coverage:** {len(model.families_ran)} families ran, {len(model.families_skipped)} skipped. "
        f"ran = [{ran}]; skipped = [{skipped}]."
    )
    if model.rendered_reverified:
        a(
            "- **honesty re-verification:** each 2a-VERIFIED quote was RE-GREPPED against a freshly-"
            "captured rendered surface this run (on the critical path)."
        )
    else:
        a(
            "- **honesty re-verification:** 2a-VERIFIED rests on the oracle's own captured quotes "
            "(no fresh rendered surface supplied; pass --rendered to re-grep on the critical path)."
        )
    a(
        "- **lens layer:** DEFERRED — the judgment lenses (SPEC §4.2) were not run this build; 2b is "
        "empty by deferral, not by a clean judgment pass. This is a stated coverage gap."
        if model.lens_deferred
        else "- **lens layer:** judgment lenses ran; 2b carries their UNVERIFIED observations."
    )
    if model.notes:
        a("- **oracle notes:**")
        for n in model.notes:
            a(f"    - {n}")
    a("")
    # machine-readable fingerprint for the NEXT run's delta (kept at the very end, in an HTML comment).
    a(_embed_fingerprint(model))
    a("")
    return "\n".join(L)


# ─────────────────────────────── JSON rendering ───────────────────────────────


def _model_to_json(model: ReportModel) -> dict[str, Any]:
    def _f(f: Finding) -> dict[str, Any]:
        return {
            "id": f.id,
            "family": f.family,
            "site": f.site,
            "title": f.title,
            "severity": f.severity,
            "status": f.status,
            "group": f.group,
            "expected": f.expected,
            "actual": f.actual,
            "evidence": f.evidence,
            "quote": f.quote,
            "basis": f.basis,
            "verification": f.verification,
            "defect_ref": f.defect_ref,
            "delta": f.delta,
            "delta_detail": f.delta_detail,
        }

    return {
        "repo": model.repo,
        "repo_name": model.repo_name,
        "store": model.store,
        "store_present": model.store_present,
        "store_absent": model.store_absent,
        "skill_path": model.skill_path,
        "skill_version": model.skill_version,
        "generated_at": model.generated_at,
        "summary": model.summary,
        "families_ran": model.families_ran,
        "families_skipped": model.families_skipped,
        "verified_count": len(model.verified),
        "flagged_count": len(model.flagged),
        "lens_count": len(model.lens),
        "lens_deferred": model.lens_deferred,
        "rendered_reverified": model.rendered_reverified,
        "snapshot_disposition": model.snapshot_disposition,
        "prior_report": model.prior_report,
        "prior_skill_version": model.prior_skill_version,
        "verified": [_f(f) for f in model.verified],
        "flagged": [_f(f) for f in model.flagged],
        "lens": model.lens,
        "delta": {
            "new": [f.id for f in model.delta_new],
            "known": [f.id for f in model.delta_known],
            "regressed": [f.id for f in model.delta_regressed],
            "fixed": model.delta_fixed,
        },
        "notes": model.notes,
    }


# ─────────────────────────────── CLI ───────────────────────────────


def _load_lens(path: str | None) -> list[dict[str, Any]] | None:
    if not path:
        return None
    obj = json.loads(_read_text(path))
    if isinstance(obj, dict) and "lens" in obj:
        obj = obj["lens"]
    if not isinstance(obj, list):
        raise ValueError("--lens must be a JSON list (or {'lens': [...]}) of observation objects")
    return [o for o in obj if isinstance(o, dict)]


def _snapshot_disposition(a: argparse.Namespace) -> str:
    if a.snapshot:
        try:
            snap = json.loads(_read_text(a.snapshot))
        except (OSError, json.JSONDecodeError) as e:
            return f"snapshot info unreadable ({type(e).__name__})"
        if isinstance(snap, dict):
            disp = snap.get("disposition") or snap.get("note")
            changed = snap.get("changed") or snap.get("changed_files")
            parts: list[str] = []
            if disp:
                parts.append(str(disp))
            if isinstance(changed, list):
                parts.append(
                    f"{len(changed)} file(s) changed by the run"
                    + (f": {', '.join(map(str, changed[:6]))}" if changed else "")
                )
            if parts:
                return " · ".join(parts)
    if a.snapshot_note:
        return str(a.snapshot_note)
    if a.restored:
        return "store restored to pre-dream state (default for a --test run)"
    if a.kept:
        return "consolidation KEPT — writes retained (explicit opt-in)"
    return "not recorded (no snapshot info supplied)"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Render the run-shaped dream beta-test report from the oracle JSON (SPEC §6)."
    )
    ap.add_argument("--oracle", required=True, help="beta_checks.py --json payload ('-' = stdin)")
    ap.add_argument(
        "--dashboard", default=None, help="the dream's rendered dashboard (verbatim §1)"
    )
    ap.add_argument(
        "--rendered",
        default=None,
        help="a freshly-captured skill rendered surface to RE-GREP each 2a-VERIFIED quote against",
    )
    ap.add_argument(
        "--prior", default=None, help="prior report .md for the RUN DELTA (else auto-discovered)"
    )
    ap.add_argument(
        "--reports-dir",
        default=None,
        help="reports dir (default: <script dir>/reports) — prior-report discovery + --write target",
    )
    ap.add_argument("--snapshot", default=None, help="snapshot.py disposition JSON for the footer")
    ap.add_argument(
        "--restored", action="store_true", help="footer: store restored to pre-dream state"
    )
    ap.add_argument(
        "--kept", action="store_true", help="footer: consolidation KEPT (writes retained)"
    )
    ap.add_argument("--snapshot-note", default=None, help="free-text snapshot/restore disposition")
    ap.add_argument(
        "--lens", default=None, help="JSON list of judgment-flagged lens observations (2b)"
    )
    ap.add_argument(
        "--out", default=None, help="write Markdown here (default: stdout; '-' forces stdout)"
    )
    ap.add_argument(
        "--write",
        action="store_true",
        help="write to reports/<slug>__<cmver>__<ts>.md and print the path",
    )
    ap.add_argument("--json", action="store_true", help="emit the structured report model as JSON")
    a = ap.parse_args(argv)

    try:
        oracle = _load_oracle(a.oracle)
    except (OSError, ValueError, json.JSONDecodeError) as e:
        print(f"ERROR: could not load oracle payload: {type(e).__name__}: {e}", file=sys.stderr)
        return 2

    try:
        dashboard = _read_text(a.dashboard) if a.dashboard else None
        rendered = _read_text(a.rendered) if a.rendered else None
        lens = _load_lens(a.lens)
    except (OSError, ValueError, json.JSONDecodeError) as e:
        print(f"ERROR: could not load an input: {type(e).__name__}: {e}", file=sys.stderr)
        return 2

    generated_at = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    snapshot_disposition = _snapshot_disposition(a)

    model = build_model(
        oracle,
        dashboard=dashboard,
        rendered=rendered,
        lens=lens,
        snapshot_disposition=snapshot_disposition,
        generated_at=generated_at,
    )

    # ── RUN DELTA: locate + diff against the prior report for this repo ──
    script_dir = Path(__file__).resolve().parent
    reports_dir = (
        Path(a.reports_dir).expanduser().resolve() if a.reports_dir else (script_dir / "reports")
    )
    repo_path = Path(model.repo) if model.repo else Path.cwd()
    slug = slug_for(repo_path)

    prior_path: Path | None = None
    if a.prior:
        prior_path = Path(a.prior).expanduser()
    else:
        prior_path = _discover_prior(reports_dir, slug, exclude=None)
    prior_text: str | None = None
    if prior_path and prior_path.is_file():
        try:
            prior_text = prior_path.read_text(encoding="utf-8", errors="replace")
            model.prior_report = str(prior_path)
        except OSError:
            prior_text = None
    _apply_delta(model, prior_text)

    # ── emit ──
    if a.json:
        out_text = json.dumps(_model_to_json(model), indent=2)
    else:
        out_text = _render_markdown(model)

    wrote_path: Path | None = None
    if a.write and not a.out:
        reports_dir.mkdir(parents=True, exist_ok=True)
        fname = f"{slug}__{model.skill_version}__{generated_at.replace(':', '-')}.md"
        wrote_path = reports_dir / fname
        # always write the Markdown to the report file (even if --json was asked for stdout)
        wrote_path.write_text(_render_markdown(model), encoding="utf-8")

    if a.out and a.out != "-":
        Path(a.out).expanduser().write_text(out_text, encoding="utf-8")
    elif wrote_path is not None and not a.json:
        # --write without --out: the file IS the deliverable; print its path to stdout.
        print(str(wrote_path))
    else:
        sys.stdout.write(out_text)
        if not out_text.endswith("\n"):
            sys.stdout.write("\n")
        if wrote_path is not None:
            print(str(wrote_path), file=sys.stderr)

    # exit code: a confirmed defect (2a-VERIFIED) shipped this run → 1, else 0.
    return 1 if model.verified else 0


if __name__ == "__main__":
    sys.exit(main())
