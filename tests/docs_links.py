#!/usr/bin/env python3
"""Documentation drift gate — zero-dependency, no browser, no network.

Docs rot silently: a badge keeps advertising a version that shipped three releases ago, a
renamed section leaves the table of contents pointing at nothing, a moved file turns a link
into a 404 that only a reader ever sees. None of that breaks a build, so nothing catches it.
This does, in the same stdlib-only style as smoke.py / validate_manifests.py, and it runs as
its own CI job (`docs`) rather than inside the 7-way test matrix — the answers do not vary
by Python version or OS.

Invariants:

1. **Badge ↔ manifest.** The shields version badge is a hand-written URL that nothing else
   reads, so it silently drifts from plugin.json. `release.sh` rewrites both in the same
   commit; this asserts they agree.
2. **Every relative link in the checked set resolves the way GitHub resolves it** —
   doc-relative with no repo-root fallback, raw HTML `href`/`src` included. **The set is
   `DOCS` below, which is a CURATED list and not the closure of the README's links** — two
   docs a reader does land on from the README, `CLAUDE.md` and
   `plugins/dream-beta-tester/docs/SPEC-A.md`, are deliberately absent and their links are
   therefore unchecked. This invariant used to state the closure, and the comment inside
   `DOCS` quoted it as its authority for a rule the list does not implement; the note after
   the list now carries the boundary instead.
3. **Manual anchors are balanced.** The README uses explicit `<a id="…">` markers because
   GitHub's auto-slugifier handles emoji-prefixed headings badly, which means a typo can
   silently orphan a section (or a link) with no error anywhere.
4. **The README keeps documenting the cross-project workflow** — the command names smoke.py
   pins; a restructure that drops one is caught here rather than by a reader who follows a
   command that no longer exists.
5. **The theme table matches the shipped theme set, both ways** — a palette added to the
   toggle without a docs row, and a row left behind by a palette that no longer ships.
6. **Every live doc's OPENING currency statement matches plugin.json.** Deliberately narrow, and
   this docstring used to claim considerably more — it said the check closed "the version-sweep
   class … so a doc can no longer advertise a superseded version". It does not, and the
   counterexample sat in this file's own doc set: `AGENTS.md`'s plugin table read `0.4.27` at every
   release from v0.4.28 through v0.4.31 — written at v0.4.27, stale through the **four** releases
   that followed, with every gate green (measured — setting that cell to `9.9.9` also leaves the
   full PR-time gate set green, so the cell was unpinned, not merely stale).
   Three structural blinds do that, all measured on this tree:

   - only the FIRST `\bvX.Y.Z\b` per doc is read — `docs/record-post-state.spec.md` §6 counted
     **183** later matches, every one a correct reference to a past release;
   - a bare `X.Y.Z` carries no `v`, so the sweep cannot tell a currency statement from any other
     dotted triple — the six docs' first bare picks are `1.0.0`, `0.4.32`, `0.4.32`, `127.0.0`,
     *nothing*, `1.0.0`, and only the two that are right are right because something else keeps
     them so (invariant 1, and invariant 7 below);
   - a table cell is a current-version claim shaped like neither of those.

   What remains true, and is why the check is worth keeping: the six `LIVE_DOCS` put their
   currency statement in the opening lines (that is the convention the rule rests on), and a
   *missing* statement is an error — so deleting the line that tripped it cannot be the cheap fix.
7. **The plugin table's Version column equals the manifest it restates.** One pinned site, the
   way invariant 1 pins one badge — NOT a class, and it says so rather than implying otherwise.
   A plugin with no row is an error too, so the table cannot quietly stop covering what ships.
8. **The committed preview matches a fresh render**, closing the same class for a *generated*
   doc: `docs/previews/nocturne/` is produced by `tests/dashboard_fixture.py` and committed,
   and nothing regenerates it on its own. It had drifted for two releases — v0.4.22 changed
   the reason-string format and v0.4.24 the dimmed-node CSS, and the README's linked preview
   still shipped both superseded.

Run:  python3 tests/docs_links.py   (exit 0 = clean)
"""

from __future__ import annotations

import json
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLUGIN = ROOT / "plugins" / "consolidate-memory" / ".claude-plugin" / "plugin.json"
TEMPLATE = ROOT / "plugins" / "consolidate-memory" / "scripts" / "dashboard.template.html"
PREVIEW = ROOT / "docs" / "previews" / "nocturne"
PREVIEW_FILES = ("index.html", "sample.json")

# Docs a reader lands on. Templates are included because a broken link in an issue form is
# invisible until someone opens the form. This is a CURATED set, not the closure of the
# README's links: destinations that are not reader-facing documents — source code, assets,
# the generated preview, `LICENSE` — are out of scope by design, and neither depth nor a link
# is the membership rule (see the notes inside the list, and after it).
DOCS = [
    "README.md",
    "CONTRIBUTING.md",
    "CODE_OF_CONDUCT.md",
    "SECURITY.md",
    "AGENTS.md",
    "CHANGELOG.md",
    ".github/PULL_REQUEST_TEMPLATE.md",
    ".github/ISSUE_TEMPLATE/bug.yml",
    ".github/ISSUE_TEMPLATE/feature.yml",
    # Linked straight from the README, so a dead link one hop out is still caught.
    "docs/network-guide.md",
    "docs/nocturne-design.md",
    "docs/deep-field-theme.spec.md",
    "plugins/consolidate-memory/skills/consolidate-memory/SKILL.md",
    "plugins/consolidate-memory/skills/consolidate-memory/references/harness-map.md",
    "plugins/dream-beta-tester/docs/SPEC.md",
    "plugins/dream-beta-tester/docs/CONTRACT.md",
    # No markdown link reaches this one, anywhere in the tree — measured, not assumed. It is
    # listed as the design record for the network map's selection, navigation and escape,
    # which is the criterion this list actually applies: whether a reader lands on the doc.
    "docs/network-graph-interaction.spec.md",
    # Reached from SECURITY.md, which is itself in this list — so the chain README →
    # SECURITY.md → spec is walked, and the spec's own outbound links are checked too.
    "docs/redos-guard-linearity.spec.md",
]
# The measured EDGE of this list, recorded so the next editor inherits it rather than
# re-deriving it: `plugins/dream-beta-tester/docs/SPEC-A.md` and the repo-root `CLAUDE.md`
# are each one hop PAST an entry above, and neither is listed. Depth is not the rule —
# `docs/redos-guard-linearity.spec.md` above is also a 2-hop arrival and IS listed — and
# neither is unreachability: both are linked from markdown in the tree — `SPEC-A.md`
# from `SPEC.md` and `STATUS.md`, `CLAUDE.md` from `CONTRIBUTING.md`. Membership is a
# judgment about reader-facing-ness, and these two are where that judgment was measured to
# stop, not a rule that derives it.

# smoke.py pins these as the README's cross-project workflow; a restructure must not lose
# them. Duplicated deliberately: this gate runs without smoke's fixtures, and the strings
# are the documentation contract, not an implementation detail.
REQUIRED_IN_README = (
    "/cm-connect", "/cm-share", "/cm-sync", "/cm-network",
    "/cm-domain", "/cm-group", "docs/network-guide.md",
)

# Docs that describe the CURRENT tree, so their opening version statement is a claim about
# today and must track plugin.json. An explicit list, never a glob, because most version
# mentions in this repo are provenance — they record when something BECAME true and stay
# correct forever. Measured counterexamples, all of which a glob would wrongly sweep:
# `docs/dream-narration-teeth.spec.md` ("Target release: v0.4.19" — still true at v0.4.24),
# `docs/deep-field-theme.spec.md`, `docs/nocturne-design.md` ("the default theme (v0.4.24)")
# and `SECURITY.md` ("at the point of EMISSION (v0.1.58)"). Add a doc here only if its
# version statement goes stale the moment a release lands.
LIVE_DOCS = [
    "CLAUDE.md",
    "AGENTS.md",
    "README.md",
    "plugins/consolidate-memory/skills/consolidate-memory/SKILL.md",
    "plugins/consolidate-memory/skills/consolidate-memory/references/harness-map.md",
    "docs/1.0-preflight.spec.md",
]

# A literal `v` is what separates a currency statement from a version *mention*, and the reason
# is that the bare alternative cannot tell the two apart — not, as an earlier version of this
# comment claimed, that a bare pattern "mis-fires on the README's shields URL". That URL is the
# one bare site a bare rule would get RIGHT, and invariant 1 pins it regardless; citing it as the
# counterexample was wrong even though the rule it justified is not. The measured counterexamples
# are the ones in the invariant-6 list: `SKILL.md`'s `127.0.0` (out of a loopback address) and
# `harness-map.md`'s nothing-at-all are not version statements in any sense, and `preflight`'s
# `**1.0.0**` is the release that checklist certifies rather than the one it describes.
_CURRENCY = re.compile(r"\bv(\d+\.\d+\.\d+)\b")

# Inline code spans and fenced blocks are stripped before scanning: a doc may legitimately
# *show* a path (`~/.claude/projects/<slug>/dashboards/index.html`) or a link-shaped example
# that is not a repo file. Both are stripped for anchors too, since a fenced example can
# contain an `<a href="#…">`.
_FENCE = re.compile(r"```.*?```", re.S)
_CODE = re.compile(r"`[^`\n]*`")
_LINK = re.compile(r"!?\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
# Markdown links are not the only ones a reader follows: the README's top row uses raw HTML,
# and a broken `href` there fails just as loudly. Reference-style `[x][y]` links are not
# covered — no doc here uses them.
_HTML_LINK = re.compile(r'(?:href|src)="([^"]+)"')
_SKIP_SCHEME = ("http://", "https://", "mailto:", "tel:")


def strip_verbatim(text: str) -> str:
    """Drop fenced blocks and inline code spans — GitHub resolves neither as a link."""
    return _CODE.sub("", _FENCE.sub("", text))

errors: list[str] = []


def err(msg: str) -> None:
    errors.append(msg)


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def check_badge() -> None:
    """The shields badge and plugin.json carry the same version."""
    if not PLUGIN.is_file():
        err("missing plugins/consolidate-memory/.claude-plugin/plugin.json")
        return
    version = json.loads(PLUGIN.read_text(encoding="utf-8")).get("version", "")
    readme = read("README.md")
    badge = re.search(r"img\.shields\.io/badge/version-([0-9][^-?\s]*)", readme)
    if not badge:
        err("README.md has no shields version badge (expected img.shields.io/badge/version-<X.Y.Z>-<colour>)")
        return
    if badge.group(1) != version:
        err(f"README version badge is {badge.group(1)!r} but plugin.json is {version!r} — "
            "release.sh bumps both; a hand-edit drifted one of them")
    # Every alt, not the first: release.sh substitutes the first match only, so a second
    # same-shaped badge higher up would let the tool bump the wrong one and leave the real
    # badge's alt stale while this gate still reported green.
    alts = re.findall(r'alt="Version ([0-9.]+)"', readme)
    if not alts:
        err('README.md version badge has no alt="Version X.Y.Z" — release.sh rewrites that '
            "alt in the same commit as plugin.json, so its absence silently unenforces it")
    for a in alts:
        if a != version:
            err(f"README version badge alt text says {a!r}, plugin.json says {version!r}")


def check_links() -> None:
    """Every relative link and image target resolves the way GitHub resolves it.

    Doc-relative, with NO repo-root fallback. GitHub resolves a relative link against the
    directory the file lives in, so `.github/PULL_REQUEST_TEMPLATE.md` writing
    `CONTRIBUTING.md` is a 404 on GitHub even though the root file exists — and accepting
    the root path here hid exactly that, twice, in files this arc added. A leading `/` is
    the one root-relative form GitHub does honour, so it is resolved from ROOT.
    """
    for rel in DOCS:
        if not (ROOT / rel).is_file():
            err(f"documentation file is missing: {rel}")
            continue
        body = strip_verbatim(read(rel))
        for target in _LINK.findall(body) + _HTML_LINK.findall(body):
            if target.startswith(_SKIP_SCHEME) or target.startswith("//"):
                continue
            path = target.split("#", 1)[0]
            if not path:                     # a bare "#fragment" — checked as an anchor below
                continue
            base = ROOT if path.startswith("/") else (ROOT / rel).parent
            if not base.joinpath(path.lstrip("/")).exists():
                err(f"{rel}: link target does not exist at GitHub's resolution: {target}")


def check_anchors() -> None:
    """Every manual `<a href="#x">` in the README has an `<a id="x">`, and vice versa."""
    readme = strip_verbatim(read("README.md"))
    defined = set(re.findall(r'<a id="([^"]+)"></a>', readme))
    used = set(re.findall(r'<a href="#([^"]+)"', readme))
    for missing in sorted(used - defined):
        err(f"README.md: <a href=\"#{missing}\"> has no matching <a id=\"{missing}\"></a>")
    for orphan in sorted(defined - used):
        err(f"README.md: <a id=\"{orphan}\"></a> is unreachable — no <a href=\"#{orphan}\"> links to it")


def _ws_tolerant(needle: str) -> str:
    """The needle as a pattern tolerating whitespace INSIDE it, for use against RAW text.

    Built over the raw text deliberately. An earlier draft instead flattened the HAYSTACK and
    applied these same boundary lookarounds to the result — which deletes the very characters
    those boundaries read. MEASURED, and quoted in full because the figure IS the argument:
    `"Run the /cm-\\nsync verb"` with its whitespace REMOVED is `"Runthe/cm-syncverb"` — the
    space inside `Run the` dies with the line break, so a flattening cannot be quoted as though
    only the break had gone. Against that haystack ``/cm-sync`` sits with a word character on
    BOTH sides (`e` left, `v` right), so both lookarounds fail and a wrapped needle reads as
    ABSENT. It passed its own mutation test only because every needle in `REQUIRED_IN_README`
    carries PUNCTUATION on **at least one side** in README (`/cm-sync` by backticks,
    `docs/network-guide.md` by parens, `/cm-connect` by a backtick and a SPACE) — a fixture green
    for an AMBIENT reason, which this repo already records. ⚠ This clause read *"is delimited in
    README by PUNCTUATION"* outright, which its own parenthetical already contradicted — it names
    `/cm-connect` as *"a backtick and a space"* — and MEASURED, 5 of the 7 needles carry a
    punctuation neighbour on BOTH sides while the other 2 carry a SPACE on the right, so the
    unqualified form was false of them.

    ⚠ A needle's OWN whitespace had to be MAPPED rather than escaped, and it is the one position the
    join does not reach. `re.escape(" ")` is a backslash-space — a LITERAL space, since space sits
    in `re`'s escape table — so the `\\s*` separators tolerate a dropped or doubled space BETWEEN
    characters while the character that IS a space still demands a space character exactly there.
    MEASURED: the needle `plugin marketplace add` against `run plugin marketplace` + a newline +
    `add ./ now` read ABSENT, so `check_required_strings` reported a present string as gone AND
    `check_contiguity` — the arm that owns precisely that shape — stayed silent: the pair's claimed
    partition broke with NO message at all, in the direction that reads as a clean run. Every needle
    in `REQUIRED_IN_README` is space-free and the case table's probe is `/cm-probe`, so the live file
    cannot expose it. `isspace` rather than `== " "` so a tab in a future needle maps too.
    """
    return r"\s*".join(r"\s+" if c.isspace() else re.escape(c) for c in needle)


def check_required_strings() -> None:
    """The cross-project workflow the README must keep documenting.

    Presence is whitespace-TOLERANT: a mention broken across a line is still a mention, so this
    check's message ("no longer mentions") stays true of genuine absence only. Its companion
    `check_contiguity` owns the broken-but-present case, and the two are a true PARTITION —
    MEASURED over the full seven-case table (contiguous · wrapped in a table cell · wrapped in
    prose · wrapped at line end · broken by a stray space · a longer token · genuinely absent):
    never two messages for one break, and never none for a broken string — the `contiguous` row
    correctly yields none, which is why the property is stated per row rather than as "never
    none" over the whole table. Before this split the two matched the same regex over the same
    haystack, so both always spoke, and the absence line was factually FALSE for a wrapped
    string.
    """
    readme = read("README.md")
    for needle in REQUIRED_IN_README:
        # Word-bounded, not a bare substring: renaming `/cm-network` to `/cm-network2`
        # leaves a superset that CONTAINS the needle, so a containment test keeps passing
        # while the documented command no longer exists. Found by mutation, not by review.
        if not re.search(rf"(?<![\w/-]){_ws_tolerant(needle)}(?![\w-])", readme):
            err(f"README.md no longer mentions {needle!r} (smoke.py pins it as the documented workflow)")


def check_contiguity() -> None:
    """Every required string must be CONTIGUOUS in the file — a wrapped one is not an anchor.

    **A REGRESSION GUARD, not a pin** — by this repo's own rule: no anchor rule existed before it,
    so it cannot fail on pre-fix code.

    The failure mode is measured, twice. BEFORE THIS SPLIT `check_required_strings` matched
    `re.escape(needle)` over the whole RAW file, so a needle containing a space stopped matching
    the moment the source wraps it: `" ".join(t.split())` in a reader crosses a newline, but the
    raw file does not — and inside a COMMENT block it does not cross the `#` that leads the next
    line either. (That function now runs the whitespace-TOLERANT pattern instead, so the strict
    `re.escape` read is the FIRST ARM OF THIS CHECK and not a description of the other one; the
    two remain a partition. An earlier draft stated it in the present tense, which described the
    pre-image rather than the shipped pair.) The measured instance is PRE-FIX and is labelled so:
    at `fbfe07e` `release.yml`'s comment wrapped as `attaches all` / `#          three to the
    GitHub Release` — ten spaces after the `#`, quoted verbatim, where an earlier draft collapsed
    them to three — and a matcher reading for the count phrase saw `all # three` and reported NO
    CLAIM. ⚠ It has to stay labelled pre-fix, and that is not pedantry: v0.4.37's OWN Family 3
    rewrote that comment, so "MEASURED in v0.4.37: it wraps as …" cited, as this release's own
    evidence, a string this release deleted. A matcher fault wearing an absence's clothes — and
    it was INVISIBLE, because a second arm of the same check still reddened. Only a single-arm
    red would have exposed it, which is why this guard exists as its own check rather than as a
    clause inside another.

    **Scope: WHITESPACE breaks only.** The MESSAGE this check emits used to read "CONTIGUOUS",
    which claims every separator while the matcher reaches exactly one; it now names whitespace
    ("a line break, or a stray space inside it"). ⚠ Name which surface, because they disagree:
    the docstring HEADLINE above still reads CONTIGUOUS and the function is still named
    `check_contiguity` — both are scoped by this paragraph rather than replaced by it, so an
    earlier draft's "the label now claims what the matcher tests" was false of each. A break
    introduced by anything else (a Markdown table cell boundary splitting a token, a soft hyphen,
    inline markup) is NOT covered. That is a stated boundary rather than a silent one because the
    separator class is unbounded, and a guard that must be complete over an unbounded class has to
    INVERT rather than enumerate — this repo's own rule.

    A guard that has never fired is not a guard, so this one was mutation-verified: wrapping BOTH
    of README's `docs/network-guide.md` occurrences reddens it (wrapping one does not — the raw
    reader still matches the other, which is itself the lesson that a mutation's effect belongs to
    the FIXTURE as much as to the code).

    ⚠ That mutation is green for an AMBIENT reason, and it is worth naming because it hid a real
    hole: MEASURED, every needle in `REQUIRED_IN_README` carries PUNCTUATION on **at least one**
    side at every occurrence — **5 of the 7 on both sides, and 2 with a SPACE as the right
    neighbour** — so not one is delimited by whitespace on both sides. ⚠ The head clause here used
    to read "delimited by PUNCTUATION" outright, which this sentence's own parenthetical
    contradicted: `/cm-connect` is named below as *"a backtick and a space"*, and a needle with a
    space on one side is not delimited by punctuation. The qualified form is the true one and the
    only one the argument needs. ⚠ **Named per needle — and now all SEVEN rather than four**, because the sentence read
    *"Named per needle"* over a list holding four of them: a universal asserted over a set its own list
    had sampled a fraction of, which is this check's defect class sitting inside its own justification.
    MEASURED 2026-09-19 by reading the immediate neighbours of every occurrence in README.md —
    **backtick on BOTH sides**: `/cm-sync` (3 occurrences), `/cm-network` (2), `/cm-domain` (3),
    `/cm-group` (2), and `docs/network-guide.md` (2, `(` on the left at both and `)` on the right at
    one, `#` at the other — the delimiter is the single `#`; an earlier draft wrote `#)`, and no `#)`
    occurs there); **a backtick and a SPACE**: `/cm-connect` (2) and `/cm-share` (2), space on the right
    at every occurrence. That is the **5 both-sides / 2 space-right** partition the sentence above
    states — reached by naming each member rather than by counting them. So
    the README fixture can only
    ever exercise a needle with at least one PUNCTUATION boundary — never one whose every boundary
    is whitespace — and it cannot reach the
    PROSE case at all. The matcher pair therefore carries its own seven-case table, asserted at the
    end of this function — contiguous · wrapped in a table cell · wrapped in prose · wrapped at
    line end · broken by a stray space, plus two CONTROLS (a longer token, and genuine absence)
    that neither matcher may call a break.

    ⚠ Scope, and the reason: the REGISTRY, not the corpus. `CLAUDE.md:32-33` is the measured
    instance — it splits `` `claude plugin validate `` / `` ./plugins/consolidate-memory --strict` ``
    — and it is deliberately OUT of scope. The reason is the GUEST POSTURE, not a read-only
    property, and an earlier draft of this paragraph got it backwards: the two-CLAUDE.md rule
    makes the USER-GLOBAL file (`~/.claude/CLAUDE.md`) the strictly-read-only one, and a bare
    `CLAUDE.md` coordinate resolves to the PROJECT file — which is the guest-WRITABLE half, edited
    report-then-apply with each change gated by the user. So a gate that reddens on it would demand
    an edit this pass is not entitled to make UNILATERALLY, not one it may never make at all. The
    instance is NAMED here rather than read, and the distinction matters because the two halves of
    the rule take different remedies: one wants a proposal, the other wants silence.
    """
    readme = read("README.md")
    for needle in REQUIRED_IN_README:
        # STRICT: present unbroken. A real anchor — nothing to guard.
        if re.search(rf"(?<![\w/-]){re.escape(needle)}(?![\w-])", readme):
            continue
        # Present-but-broken, or absent? `check_required_strings` now runs this SAME tolerant
        # matcher, so its silence here means whitespace-inside and its speech means genuine
        # absence — a true partition, measured across the case table in the docstring. The
        # message must name what THIS predicate tests: whitespace. It previously asserted "a line
        # break", which a stray space satisfies just as well, sending the reader to reflow a line
        # that was never wrapped.
        if re.search(rf"(?<![\w/-]){_ws_tolerant(needle)}(?![\w-])", readme):
            err(f"README.md's required string {needle!r} is present only BROKEN by whitespace "
                f"(a line break, or a stray space inside it) — it matches with the whitespace "
                f"removed but not in the raw file, so `grep -F` finds nothing and it is not an "
                f"anchor. Restore it as one unbroken token")

    # The matcher pair carries its OWN case table, because the README fixture cannot reach every
    # shape the guard must handle — see the AMBIENT note in the docstring: every real needle here
    # is punctuation-delimited, so a PROSE wrap (the motivating case) is unreachable from the live
    # file. A guard whose only fixture is the file it guards cannot test its own matcher, so this
    # supplies the input the file does not. Expected: strict False AND tolerant True on every
    # broken shape — tolerant False would mean `check_required_strings` calls a present string
    # absent (the false verdict this pair exists to prevent).
    _p = "/cm-probe"
    _head, _tail = _p[:-3], _p[-3:]
    for _lbl, _txt, _want in (
        ("contiguous",       f"run {_p} here",                 (True,  True)),
        ("table-wrapped",    f"| {_head}\n{_tail} | x |",      (False, True)),
        ("prose-wrapped",    f"run the {_head}\n{_tail} now",  (False, True)),
        ("line-end-wrapped", f"use {_head}\n{_tail}\nhere",    (False, True)),
        ("stray-space",      f"run {_head} {_tail} now",       (False, True)),
        # Controls: neither is a break, so NEITHER matcher may claim one. A longer token is the
        # superset case `check_required_strings` was already hardened against, and it must stay a
        # genuine absence rather than being re-labelled a whitespace break by the tolerant form.
        ("longer-token",     f"run {_p}2 here",                (False, False)),
        ("absent",           "nothing here at all",            (False, False)),
    ):
        _got = (bool(re.search(rf"(?<![\w/-]){re.escape(_p)}(?![\w-])", _txt)),
                bool(re.search(rf"(?<![\w/-]){_ws_tolerant(_p)}(?![\w-])", _txt)))
        if _got != _want:
            err(f"the contiguity matcher pair is wrong on the {_lbl!r} case: "
                f"(strict, tolerant) = {_got}, expected {_want}")


def _plain(cell: str) -> str:
    """A table cell reduced to words: markdown emphasis, the icon, and the annotation go.

    "**◉ Deep Field** *(default)*" → "Deep Field default", so a theme name can be compared
    as a whole phrase rather than by containment.
    """
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s-]", " ", cell)).strip()


def _names_theme(label: str, text: str) -> bool:
    """True when a normalized cell names exactly this theme (not a longer theme containing it)."""
    return text == label or text.startswith(label + " ")


def check_themes() -> None:
    """The toggle's shipped theme set and the README's theme table agree, BOTH ways.

    Reads `modes` rather than the `names` label map: `modes` is the list the toggle actually
    cycles (`names` only labels it), so a theme added to one and not the other — which
    renders the button as "undefined" — is caught here rather than shipped.

    Both directions, because a one-way check cannot see a row left behind: a theme removed
    from the toggle with its README row intact reads as "documented but gone". Matched on
    the row's first cell as a whole phrase, since containment lets a new theme named `Field`
    pass on the `Deep Field` row.
    """
    if not TEMPLATE.is_file():
        err("missing dashboard.template.html")
        return
    template = TEMPLATE.read_text(encoding="utf-8")
    modes = re.search(r"modes=\[([^\]]+)\]", template)
    if not modes:
        err("dashboard.template.html: no theme `modes` list found — did the toggle move?")
        return
    order = re.findall(r'"([^"]+)"', modes.group(1))
    if not order:
        err("dashboard.template.html: the theme `modes` list is empty")
        return
    names = re.search(r"names=\{([^}]+)\}", template)
    if not names:
        err("dashboard.template.html: no theme `names` map found — did the toggle move?")
        return
    labels = dict(re.findall(r'([a-z_]+):"([^"]+)"', names.group(1)))
    # `modes` decides what ships; `names` only labels it. Checked in both directions: a mode
    # with no label renders the button as "undefined", and a label with no mode is dead
    # weight the toggle can never reach — while the README is compared against the LABELS,
    # which is what a reader sees there.
    for mode in order:
        if mode not in labels:
            err(f"theme {mode!r} is in the toggle's `modes` but has no `names` label — "
                'the button would render "undefined"')
    for mode in labels:
        if mode not in order:
            err(f"dashboard.template.html: `names` labels {mode!r} but `modes` never cycles "
                "to it — the label is unreachable")
    shipped = [labels[m] for m in order if m in labels]

    readme = read("README.md")
    heading = readme.find("### Pick a theme")
    if heading < 0:
        err("README.md has no '### Pick a theme' section — the theme table is the theme contract")
        return
    after = readme[heading + len("### Pick a theme"):]
    section = re.split(r"\n#{2,3} ", after, maxsplit=1)[0]
    cells = [_plain(ln.split("|")[1]) for ln in section.splitlines()
             if ln.startswith("|") and ln.count("|") >= 3]
    # Drop the header and the `| :--- |` separator: neither names a theme.
    rows = [c for c in cells if c and c.lower() != "theme" and set(c) - {"-", " "}]
    for label in shipped:
        if not any(_names_theme(label, r) for r in rows):
            err(f"theme {label!r} ships in the toggle but has no row in the README's theme table")
    for r in rows:
        if not any(_names_theme(label, r) for label in shipped):
            err(f"README.md: the theme row {r!r} matches no theme the toggle ships "
                f"({', '.join(shipped)}) — a row left behind by a removed theme")


def check_version_statements() -> None:
    """Each live doc names the current release, and names it first.

    The convention this rests on: the FIRST `vX.Y.Z` in a live doc is its currency
    statement. All six put it in the opening lines today (the introduction, the status
    line), so the only way to trip a false positive is to mention a version *earlier* than
    the currency statement — write that mention without the `v` (as in "shipped in 0.3.0")
    and this ignores it, which is also what keeps the rule honest for the historical docs
    that LIVE_DOCS deliberately excludes.

    A missing statement is an error too, not a skip: otherwise the cheapest fix for a red
    gate would be deleting the line that tripped it.
    """
    if not PLUGIN.is_file():
        err("missing plugins/consolidate-memory/.claude-plugin/plugin.json")
        return
    version = json.loads(PLUGIN.read_text(encoding="utf-8")).get("version", "")
    for rel in LIVE_DOCS:
        path = ROOT / rel
        if not path.is_file():
            err(f"live doc is missing: {rel} (in LIVE_DOCS — restore the file or drop the entry)")
            continue
        stated, where = None, ""
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            m = _CURRENCY.search(line)
            if m:
                stated, where = m.group(1), f":{n}"
                break
        if stated is None:
            err(f"{rel}: no `vX.Y.Z` statement of the current release — a live doc opens by "
                f"naming the release it describes (expected v{version})")
        elif stated != version:
            err(f"{rel}{where}: states v{stated} but plugin.json is {version} — the version "
                "sweep missed this file")


def check_plugin_table() -> int:
    """`AGENTS.md`'s plugin table restates each manifest's version, and nothing could see it drift.

    Returns the number of rows checked, so `main` can report the coverage instead of implying it.

    Why this exists at all: the cell is a *current-version claim* that the currency sweep is
    structurally blind to (invariant 6). It was measured stale at every release from v0.4.28 through
    v0.4.31 — the cell read `0.4.27` against four successive manifests — and measured UNPINNED:
    rewriting it to `9.9.9` left every gate green. So this is one site, pinned the way `check_badge`
    pins the badge, and it is not offered as coverage of the class.

    Rows are matched by MANIFEST, not by shape: for each `plugins/*/.claude-plugin/plugin.json`
    the table is searched for a row naming it, so an unrelated table in the same file cannot be
    mistaken for a plugin row (and a plugin the table forgot is an error rather than a silence).
    """
    rel = "AGENTS.md"
    path = ROOT / rel
    if not path.is_file():
        err(f"missing {rel} — its plugin table is the manifest's restatement")
        return 0
    manifests = sorted((ROOT / "plugins").glob("*/.claude-plugin/plugin.json"))
    if not manifests:
        err("no manifests under plugins/*/.claude-plugin/ — this check would pass vacuously")
        return 0
    rows: dict[str, tuple[str, int]] = {}
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 2:
            continue
        name = cells[0].strip("`")
        if not (ROOT / "plugins" / name / ".claude-plugin" / "plugin.json").is_file():
            continue                       # not a plugin row — some other table in the same file
        rows.setdefault(name, (cells[1].strip("`"), n))
    for manifest in manifests:
        name = manifest.parent.parent.name
        version = json.loads(manifest.read_text(encoding="utf-8")).get("version", "")
        if name not in rows:
            err(f"{rel}: no plugin-table row for {name!r} — a manifest with no row is a version "
                "site nothing checks (or the table moved; either way this check just shrank)")
            continue
        stated, where = rows[name]
        if stated != version:
            err(f"{rel}:{where}: the plugin table says {name} is {stated!r} but its manifest is "
                f"{version!r} — a table cell is a current-version claim the `v`-sweep cannot see")
    return len(manifests)


def check_preview() -> None:
    """The committed preview is byte-identical to a fresh render of its own fixture.

    `docs/previews/nocturne/` is GENERATED and then committed, so it drifts silently: the
    fixture is edited, the artifact is not re-rendered, and the README keeps linking a stale
    page. Rendering is deterministic (two renders were byte-identical, and the CLI and the
    library entry point agree), so a byte-compare is a fair gate rather than a flaky one.

    The renderer is imported lazily so a broken renderer still lets every other check report
    — but it does fail the gate, because an unverifiable preview is not a verified one.
    """
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    try:
        import dashboard_fixture  # noqa: PLC0415 — deliberate: see the docstring
    except Exception as e:                                    # pragma: no cover - env failure
        err(f"could not import the preview renderer (tests/dashboard_fixture.py): {e}")
        return
    if not PREVIEW.is_dir():
        err("the committed preview is missing: docs/previews/nocturne/")
        return
    with tempfile.TemporaryDirectory() as td:
        try:
            dashboard_fixture.write_preview(Path(td))
        except Exception as e:
            # write_preview ASSERTS that its sample-notice splice matched the document's <body> tag
            # exactly once (tests/dashboard_fixture.py). That assert is the enforcement site for
            # "the notice reaches the page a reader sees": the byte-compare below renders BOTH
            # sides, so a splice that fires in the wrong place is byte-identical on both and would
            # be green by construction. Report it as a gate failure rather than a traceback, so the
            # failure names the check that failed.
            err(f"could not render the preview fixture: {type(e).__name__}: {e}")
            return
        for name in PREVIEW_FILES:
            fresh, committed = Path(td) / name, PREVIEW / name
            if not committed.is_file():
                err(f"preview file is missing: docs/previews/nocturne/{name}")
            elif fresh.read_bytes() != committed.read_bytes():
                err(f"docs/previews/nocturne/{name} is stale — regenerate both with "
                    "`python3 tests/dashboard_fixture.py --out docs/previews/nocturne`")
        # NOT re-counted here: the notice's presence and position. An earlier version of this check
        # counted `class="sample-notice"` in the committed artifact and demanded exactly one, with a
        # message claiming it detected an unbounded splice. It could not: given the render assert
        # above and the byte-compare, a committed artifact is a render, so its count is one by
        # construction — the check was red-reachable in no run at all, while reading as coverage.
        # The invariant lives at the stronger site (the fixture cannot emit a misplaced notice),
        # which is why nothing is re-added here.


def main() -> int:
    check_badge()
    check_links()
    check_anchors()
    check_required_strings()
    check_contiguity()
    check_themes()
    check_version_statements()
    plugin_rows = check_plugin_table()
    check_preview()
    if errors:
        print("✗ documentation gate FAILED:")
        for e in errors:
            print(f"  - {e}")
        return 1
    version = json.loads(PLUGIN.read_text(encoding="utf-8"))["version"]
    # The denominators are not decoration: without them a reader cannot tell "0 problems in 7
    # required strings" from "0 problems in 0", and a check that has silently stopped examining
    # anything prints exactly as green as one that examined everything.
    print(f"✓ docs valid (badge + {len(LIVE_DOCS)} live-doc statements at v{version}, "
          f"{plugin_rows} plugin-table rows, {len(DOCS)} files link-checked, "
          f"{len(REQUIRED_IN_README)} required strings unbroken, anchors balanced, "
          "preview current)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
