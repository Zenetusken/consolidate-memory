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
   reads, so it silently drifts from plugin.json. Both are bumped BY HAND together on the
   feature branch, and `release.sh --stage` validates the result; this asserts they agree.
2. **Every relative link in the checked set resolves the way GitHub resolves it** —
   doc-relative with no repo-root fallback, raw HTML `href`/`src` included. **The set is
   `DOCS` below, which is a CURATED list and not the closure of the README's links** — two
   docs the link graph reaches from the README, `CLAUDE.md` and
   `plugins/dream-beta-tester/docs/SPEC-A.md`, are deliberately absent and their links are
   therefore unchecked. ⚠ THE OPERAND IS THE LINK GRAPH this file walks — inline markdown
   destinations resolved relative to the linking file and filtered to tracked `.md` — and
   NOT every way a reader arrives, which is the wider reading the words invite: the README
   also links the DIRECTORY `docs/adr`, holding 24 documents that no `.md`-filtered walk can
   represent at all, and it is neither an entry of the list nor one of the exclusion classes
   the header names. This invariant used to state the closure, and the comment inside
   `DOCS` quoted it as its authority for a rule the list does not implement; the note after
   the list now carries the boundary instead.
3. **Manual anchors are balanced.** The README uses explicit `<a id="…">` markers because
   GitHub's auto-slugifier handles emoji-prefixed headings badly, which means a typo can
   silently orphan a section (or a link) with no error anywhere.
4. **The strings a reader copies are present AND unbroken, per file** — the README's cross-project
   workflow (the command names smoke.py pins) and `CLAUDE.md`'s install/validate path. A
   restructure that drops one, or a reflow that splits one across a line break, is caught here
   rather than by a reader who follows a command that no longer exists. ⚠ The file set is
   `REQUIRED_STRINGS`, and each file brings its OWN needles: MEASURED, the README's set applied to
   `CLAUDE.md` would match nothing at all, so a widened set is not a second file's coverage.
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
9. **A dated currency statement carries its release's date — and the release itself is dated.**
   A release moves the version and the date beside it together, and nothing else reads that
   date: the bump is hand-authored, and a person typing a version is exactly as likely to leave
   its date behind as the old sweep was. Both halves are required, and neither substitutes for
   the other. `check_currency_dates` compares a live doc's paired date against the CHANGELOG's
   date for *the version that doc names*. `check_changelog_dated` refuses the state in which
   there is nothing to compare against: while `plugin.json` names a version the CHANGELOG has
   not dated — precisely the pair `--stage` verifies and `--finalize` tags — the gate is red.
   Without the second, the first prints a green success line over an axis that examined nothing,
   because the `— UNRELEASED` window is the state this repo authors its releases in.
10. **Each plugin's `docs/STATUS.md` opens on its OWN manifest's version.** Invariant 6 is keyed to
   ONE manifest, so a doc whose opening statement is about a *different* plugin is not merely
   unchecked — listed there it would be checked *wrongly*. Measured on this tree: putting
   `plugins/dream-beta-tester/docs/STATUS.md` into `LIVE_DOCS` reds on **two** of its statements
   (`v0.1.8`, its own manifest's — `0.1.8` — and `v0.1.85`, a consolidate-memory release the doc
   cites as provenance, which lives in *this* CHANGELOG), because neither equals `plugin.json`'s.
   So the sibling's header is checked against the manifest BESIDE it, discovered the way invariant
   7's rows are rather than named — a third plugin's STATUS.md is covered the day it lands. ⚠ One
   site, pinned like the badge, and the boundary is stated in the function rather than implied.
11. **Every `docs/*.spec.md` whose header still states a DRAFTING-era status while CHANGELOG.md names it
   inside a `## [X.Y.Z]` release section is a contradiction** (`check_spec_status`, v0.4.61). ⚠ This
   entry was ADDED at v0.4.62: the gate shipped without one, so the file's own index of what it gates
   omitted the gate — and invariant 6 above is the reason the axis was invisible in the first place
   (`LIVE_DOCS` is a CURRENCY set; a status was in no set). 16 pre-shipping headers were found and 14
   swept, and the count moved once per matcher fix — a gate's number is a property of its matcher.
   ⚠ **v0.4.64: this entry names the gate's FIRST arm only.** `check_spec_status` has had a SECOND
   since v0.4.63 — a header stating a pre-shipping status while naming a `Target release:` that has
   **already shipped**, decided with NO citation. Recording it matters for the entry's own reason:
   this index exists so the file does not omit a gate it operates, and an arm is a gate. Its operand
   became the header REGION at v0.4.64 (first `## `, the cap, and the sweep's provenance note); before
   that it read raw `lines[:120]` and was reading preserved history for most of the specs it saw,
   including both of the two it was built for. (Corpus counts live in the CHANGELOG and in the
   target-scan comment, not here.)

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
# invisible until someone opens the form, and the same goes for a design record a reader is
# handed off to rather than linked to. This is a CURATED set, not the closure of the
# README's links: destinations that are not reader-facing documents — source code, assets,
# the generated preview — are out of scope by design, and neither depth nor a link is the
# membership rule (see the notes inside the list, and after it). ⚠ That clause speaks about
# DESTINATIONS, and neither of the README's two unsettled ones is settled by it. The root
# `LICENSE` it does not reach — a reader-facing document is outside the class it excludes — and
# this list omits it: a judgment, not a category. The DIRECTORY `docs/adr` it does reach, and
# reaching it is all it does; the clause says nothing about the 24 documents a reader arrives at
# through it, and a directory's scope is not its contents' scope. This file's own practice is
# the proof: `docs/` is likewise a directory, is likewise linked (from `CONTRIBUTING.md`), and
# five of its 82 tracked documents are listed below. Recorded rather than added, because a
# boundary that is not written down is re-derived, differently, by the next editor.
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
    # The sibling plugin's own status doc. It sat in NEITHER this set NOR `LIVE_DOCS` — both
    # measured 0 — while its opening line stated `dream-beta-tester v0.1.8`, so no gate read that
    # claim and none of its outbound links were checked. Listed here for the links (invariant 2);
    # its version is read by `check_plugin_status_docs` (invariant 10).
    "plugins/dream-beta-tester/docs/STATUS.md",
    # No markdown link reaches this one under the matcher this gate walks — `](...)`
    # destinations in tracked files, doc-relative — measured, not assumed. ⚠ The bound is
    # that matcher and not the tree, and the difference is a DIRECTORY link, which the walk
    # cannot follow: `CONTRIBUTING.md` links `docs/`, and this file is inside it. It is
    # listed as the design record for the network map's selection, navigation and escape —
    # the doc a reader is handed off to.
    "docs/network-graph-interaction.spec.md",
    # Reached from SECURITY.md, which is itself in this list — so the chain README →
    # SECURITY.md → spec is walked, and the spec's own outbound links are checked too.
    "docs/redos-guard-linearity.spec.md",
]
# The measured EDGE of THIS WALK, recorded so the next editor inherits it rather than
# re-deriving it: `plugins/dream-beta-tester/docs/SPEC-A.md` and the repo-root `CLAUDE.md`
# are each one hop PAST an entry above, and neither is listed. Depth is not the rule —
# `docs/redos-guard-linearity.spec.md` above is also a 2-hop arrival and IS listed — and
# neither is unreachability: both are linked from markdown in the tree — `SPEC-A.md`
# from `SPEC.md` and `STATUS.md`, `CLAUDE.md` from `CONTRIBUTING.md`. ⚠ Both of those
# linkers are listed ABOVE, and listing a linker lists nothing it points at: `check_links`
# iterates this list, it is not the closure of it. Membership is a
# judgment about reader-facing-ness, and these two are where that judgment was measured to
# stop, not a rule that derives it. ⚠ The EDGE is the edge of THIS WALK, not of arrival: the
# walk follows markdown destinations from a linking `.md` and filters to tracked `.md`, so a
# DIRECTORY link is invisible to it by construction — the README hands a reader to `docs/adr`
# and to the 24 documents inside it, and this note can name neither.

# smoke.py pins these as the README's cross-project workflow; a restructure must not lose
# them. Duplicated deliberately: this gate runs without smoke's fixtures, and the strings
# are the documentation contract, not an implementation detail.
REQUIRED_IN_README = (
    "/cm-connect", "/cm-share", "/cm-sync", "/cm-network",
    "/cm-domain", "/cm-group", "docs/network-guide.md",
)

# ⚠ v0.4.63 — the SECOND file, and it carries its OWN needles rather than a wider README set.
# MEASURED before the map existed: **0 of the README's 7 needles occur in this file at all**, so
# re-running `check_contiguity` under a widened set would have examined a second file and found
# nothing in it — a denominator that reads as coverage while testing nothing, this repo's standing
# failure mode. What makes a file's entry real is the strings a reader COPIES out of THAT file, and
# the failure mode is the same one: a command split across a line break is not copy-pasteable and
# `grep -F` finds nothing. That is what put `CLAUDE.md` here — `` `claude plugin install `` and the
# `consolidate-memory@zenetusken-plugins` token were split across lines 20–21, and the token move
# that closed it is the fix this entry's arm reddened on (a guard that has never fired is not a
# guard, which is the same standard the case table below is held to).
# ⚠ The entry is checked for PRESENCE as well (`check_required_strings`), and that is not
# decoration: without it the cheapest way to clear this arm's red would be DELETING the wrapped
# command, which removes the documented install path and leaves the gate green — `a missing
# statement is an error, not a skip`, the rule `check_version_statements` already states for its
# own axis. The two functions iterate the SAME map, so their claimed partition holds per file.
REQUIRED_IN_CLAUDE_MD = (
    "/plugin marketplace add Zenetusken/consolidate-memory",
    "/plugin install consolidate-memory@zenetusken-plugins",
    "claude plugin marketplace add ./",
    "claude plugin install consolidate-memory@zenetusken-plugins",
    "claude plugin validate ./plugins/consolidate-memory --strict",
)

# file → (why the set exists, the strings a reader must be able to copy and find). An explicit MAP:
# never a glob, and never one file's set reused for another's — see `REQUIRED_IN_CLAUDE_MD` for the
# measurement. Membership is a judgment of the same kind `DOCS` and `LIVE_DOCS` carry (does this
# file hand a reader a command?), NOT the closure of anything, and the next file that does joins by
# bringing its own needles rather than by widening an existing set.
REQUIRED_STRINGS = {
    "README.md": ("smoke.py pins it as the documented cross-project workflow",
                  REQUIRED_IN_README),
    "CLAUDE.md": ("it is the install/validate path this file calls the one gotcha that matters",
                  REQUIRED_IN_CLAUDE_MD),
}

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

# The date a currency statement pairs with its version. The `v` in _CURRENCY is what makes a
# statement *currency*; the date beside it is what makes that statement a claim about *when*,
# and no gate read it before v0.4.40. `release.sh`'s old sweep moved the version and left the
# date behind; that sweep is gone — the bump is hand-authored now — which is why the pair needs
# a gate MORE than it did before rather than less. Word-bounded on purpose: an unbounded
# `\d{4}-\d{2}-\d{2}` would also match the first ten characters of a longer number.
_DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")

# `## [0.4.38] — 2026-09-19`. The top section reads `— UNRELEASED` until the release stamps it,
# which is why `changelog_date` returns None rather than "": an absent date claim is not a
# wrong one, and a version the CHANGELOG has not dated yet is not a version with a bad date.
# ⚠ That tolerance is scoped to the CYCLE — a manifest still naming the shipped version. The
# moment `plugin.json` names the undated one, `check_changelog_dated` makes it an error: that
# pair is what a release ships, and `None` there silences the whole date axis.
_HEADING = re.compile(r"^## \[(\d+\.\d+\.\d+)\] — (.*)$")

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


def changelog_date(version: str) -> str | None:
    """The date the CHANGELOG pairs with `version`, or None when it makes no date claim.

    Deliberately uncached: one full scan costs ~1.4 ms (measured, n=20, on the ~500 KB
    CHANGELOG), so the calls a full pass makes — one per dated statement (two today), plus
    `check_changelog_dated`'s own probe of the manifest's version, three measured — add ~4 ms
    to a gate that runs in ~100 ms. Cheaper than the mutable module state a cache would need,
    and it keeps this a pure function.

    Reads the date of the version it is ASKED about rather than plugin.json's, so the two axes
    stay independent: a doc left on a stale version still gets its date checked against *that*
    release, and the version error is reported once rather than twice.
    """
    for line in read("CHANGELOG.md").splitlines():
        m = _HEADING.match(line)
        if m and m.group(1) == version:
            found = _DATE.findall(m.group(2))
            return found[0] if found else None
    return None


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
            "both are hand-bumped together; one of them drifted")
    # EVERY alt, not the first: nothing substitutes these any more, so the only thing that keeps
    # them in step is a reader noticing — and a second same-shaped badge higher up would let a
    # hand edit move one and leave the other stale while this gate still reported green.
    alts = re.findall(r'alt="Version ([0-9.]+)"', readme)
    if not alts:
        err('README.md version badge has no alt="Version X.Y.Z" — the alt carries its own copy '
            "of the version, and an absent one is unenforceable rather than correct")
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
    """Every string a reader must be able to FIND, per file — README's workflow, CLAUDE.md's installs.

    Iterates `REQUIRED_STRINGS`, so the file set and the reason text are the map's, not this
    function's — the README arm used to be the whole check, and the second file arrived with its
    own needles rather than by widening the first file's.

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
    for rel, (_why, needles) in REQUIRED_STRINGS.items():
        body = read(rel)
        for needle in needles:
            # Word-bounded, not a bare substring: renaming `/cm-network` to `/cm-network2`
            # leaves a superset that CONTAINS the needle, so a containment test keeps passing
            # while the documented command no longer exists. Found by mutation, not by review.
            if not re.search(rf"(?<![\w/-]){_ws_tolerant(needle)}(?![\w-])", body):
                err(f"{rel} no longer mentions {needle!r} ({_why})")


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

    ⚠ Scope, and why it moved at v0.4.63: the MAP, not the corpus. `CLAUDE.md`'s own entry now
    carries the pair's arms — and the coordinate this paragraph used to NAME is NOT the instance
    that put it there. The v0.4.57 record cited `CLAUDE.md:32-33` — `` `claude plugin validate ``
    / `` ./plugins/consolidate-memory --strict` `` split across the break. ⚠ THAT SPAN IS CONTIGUOUS
    TODAY, and it was contiguous at the tag that recorded it and at the tag before this one:
    `git show v0.4.57:CLAUDE.md` puts the whole command on line 33, and so does `v0.4.62`. The
    record named a coordinate that had already stopped being an instance, while the SAME class sat
    live at `:20-21` of that very file (both tags split `claude plugin install` from its
    `consolidate-memory@…` token) and stayed invisible because the boundary was read from the
    record rather than re-measured — the docket's own lesson, on the file that records it. A stale
    instance named instead of a census re-run is how a scope decision outlives its subject.
    ⚠ The reason this paragraph gave for excluding the file is not overturned, it is SCOPED: it
    rested on the GUEST POSTURE — the two-CLAUDE.md rule makes the USER-GLOBAL file
    (`~/.claude/CLAUDE.md`) the strictly-read-only one, so a gate reddening on a bare `CLAUDE.md`
    coordinate would demand an edit "this pass is not entitled to make UNILATERALLY". That is an
    argument about who may EDIT a guest repo's file from inside a skill. This is a repo-local CI
    gate that edits nothing: a red here is a report to the maintainer, on a file this repo authors
    like every other doc the gate covers. So the boundary that survives is the one about the
    GLOBAL file — nothing here reads, or may read, `~/.claude/CLAUDE.md`.
    ⚠ And the boundary that remains is a MAP of two files, not the corpus: a third file joins by
    bringing its own needles, and the widening trap is MEASURED in `REQUIRED_IN_CLAUDE_MD` (the
    README's set has 0 occurrences here — a widened set would have examined a second file and seen
    nothing in it). A per-needle census is still owed when an entry is added, and the README's is
    above. `CLAUDE.md`'s five needles ALL carry whitespace inside, and EVERY occurrence of each is
    delimited by a backtick on both sides — measured, one or two occurrences per needle — so the
    second file inherits this limit rather than escaping it: a needle whose every boundary is
    whitespace cannot be exercised by the live file, and the case table below is the only fixture
    for that shape.
    """
    for rel, (_why, needles) in REQUIRED_STRINGS.items():
        body = read(rel)
        for needle in needles:
            # STRICT: present unbroken. A real anchor — nothing to guard.
            if re.search(rf"(?<![\w/-]){re.escape(needle)}(?![\w-])", body):
                continue
            # Present-but-broken, or absent? `check_required_strings` now runs this SAME tolerant
            # matcher over the SAME map, so its silence here means whitespace-inside and its speech
            # means genuine absence — a true partition per file, measured across the case table in
            # the docstring. The message must name what THIS predicate tests: whitespace. It
            # previously asserted "a line break", which a stray space satisfies just as well,
            # sending the reader to reflow a line that was never wrapped.
            if re.search(rf"(?<![\w/-]){_ws_tolerant(needle)}(?![\w-])", body):
                err(f"{rel}'s required string {needle!r} is present only BROKEN by whitespace "
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


def check_currency_dates(rel: str, where: str, stated: str, line: str) -> tuple[int, int]:
    """A currency statement that carries a date must carry the release's date.

    Returns (eligible, checked): `eligible` is 1 when the line carries a date at all, `checked`
    is 1 when that date was actually compared against the release's. They differ in exactly one
    state — the CHANGELOG has not dated the version the statement names — and that state is
    ALWAYS a red one, because a green run requires every statement to name the manifest's version
    and the undated case is the one `check_changelog_dated` refuses. So `main` prints the pair on
    the failing path as well: a single number reads the same whether the axis examined both sites
    or skipped both, and the only run that can tell them apart is the one that never reached the
    ✓. "0 of 2" is the skip; "0 of 0" is a tree with nothing dated.

    Four of the six live docs put no date on their statement, which is why the denominator is not
    `len(LIVE_DOCS)`: reporting six would claim coverage this check does not have.

    Called *from* `check_version_statements`'s walk rather than given a walk of its own: that
    loop already has the currency claim's line in hand, and a second sweep would be a second
    copy of the rule — the defect class this whole division exists to close.

    ⚠ Scope is the currency claim's own line — never a `v`-token's line, never file-wide.
    Measured: `docs/1.0-preflight.spec.md` carries six `2026-` lines in total, and `:18` pairs
    a HISTORICAL token with a date the CHANGELOG contradicts (`v0.4.2` against `## [0.4.2] —
    2026-09-03`), so a file-wide sweep would redden the current, correct tree. The caller's
    `break` is load-bearing for the same reason: it stops at the first currency line, so `:18`
    is never reached.

    Every date on that line must agree. Both dated sites today carry exactly one date, so this
    is not yet a distinction — but the statement makes ONE claim about *when*, and a second,
    different date on the same line is a stale date sitting beside the current version, which
    is the defect rather than an exception to it.
    ⚠ That rule is a deliberate OVER-approximation, stated because the message must not claim
    more than the check can do: a `findall` over a physical line cannot bind a date to a token,
    so a line that names a superseded release *with its date* reads as a second date on the
    currency line and reds. The error says what was seen and what the rule is, never which token
    the date belongs to and never why the author moved it — a re-verification that re-dates a
    statement is a real edit, and naming a release as the cause would be a diagnosis the check
    cannot make.

    ⚠ KNOWN BLIND SPOT, measured — this reads PHYSICAL lines, so it sees the pair only while
    both tokens share one. A reflow that puts a line break between the version and its date
    leaves the currency line undated, and the check SKIPS rather than firing: a fixture doing
    exactly that reports `1 of 1` where the tree carries two dated statements, with no error.
    Widening the scope to a window of following lines would fix it. It was not taken, and not
    for safety: the `:18` false positive above is reached by a FILE-WIDE sweep, never by a
    window — `:18` sits ten lines below the currency line, where a reflow bridges one. The
    reason is scope: a window's correctness would rest on each document's layout, where the
    claim's own line is the claim's own extent by construction. The ELIGIBLE count is the
    trace, not the checked one: if it falls without a doc having dropped its date, look for a
    wrap.
    """
    dates = _DATE.findall(line)
    if not dates:
        return 0, 0
    expected = changelog_date(stated)
    if expected is None:
        return 1, 0
    for d in dates:
        if d != expected:
            err(f"{rel}{where}: the v{stated} statement's line carries {d}, but the CHANGELOG's "
                f"`## [{stated}]` section is dated {expected} — every date on a currency line "
                "must be its release's date")
    return 1, 1


def check_version_statements() -> tuple[int, int]:
    """Each live doc names the current release, and names it first — and, if it dates that
    statement, names the release's date with it.

    The convention this rests on: the FIRST `vX.Y.Z` in a live doc is its currency
    statement. All six put it in the opening lines today (the introduction, the status
    line), so the only way to trip a false positive is to mention a version *earlier* than
    the currency statement — write that mention without the `v` (as in "shipped in 0.3.0")
    and this ignores it, which is also what keeps the rule honest for the historical docs
    that LIVE_DOCS deliberately excludes.

    A missing statement is an error too, not a skip: otherwise the cheapest fix for a red
    gate would be deleting the line that tripped it.

    Returns (eligible, checked) — the dated statements the walk found, and the ones it could
    compare against a release date — the way `check_plugin_table` returns its row count: a
    reader must be able to tell "0 problems in 2 dated statements" from "0 problems in 0", and
    a check that has silently stopped examining anything prints as green as one that examined
    everything. Two numbers rather than one, because `check_currency_dates` skips a dated
    statement whose release the CHANGELOG has not dated: a single count cannot separate "nothing
    was dated" from "everything dated was skipped", and the state that does the skipping is the
    one this repo authors its releases in.
    """
    if not PLUGIN.is_file():
        err("missing plugins/consolidate-memory/.claude-plugin/plugin.json")
        return 0, 0
    version = json.loads(PLUGIN.read_text(encoding="utf-8")).get("version", "")
    eligible = checked = 0
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
                e, c = check_currency_dates(rel, where, stated, line)
                eligible += e
                checked += c
                break
        if stated is None:
            err(f"{rel}: no `vX.Y.Z` statement of the current release — a live doc opens by "
                f"naming the release it describes (expected v{version})")
        elif stated != version:
            err(f"{rel}{where}: states v{stated} but plugin.json is {version} — the hand-bump "
                "missed this file")
    return eligible, checked


def check_changelog_dated() -> None:
    """The release the manifest claims must be DATED in the CHANGELOG.

    This is the half D3 did not close. `changelog_date` returns None both for a version the
    CHANGELOG never dated and for one it never mentions; `check_currency_dates` then SKIPS a
    dated statement whose release has no date to compare against. So an undated top section
    silences the date axis for every doc that names it, while every other check stays green.
    MEASURED before this check existed: a tree whose CHANGELOG top reads `## [0.4.40] —
    UNRELEASED` with real notes passed `--stage`, passed `--finalize`, shipped, and printed a
    success line over an axis that examined nothing. The silence is not hypothetical — the
    `— UNRELEASED` window is the state this repo authors its releases in, and nothing stamped
    it: the convention had no producer anywhere in the tooling.

    The discriminator is `plugin.json`, and it is the one `--stage` already verifies: the
    pre-bump contract makes "the manifest equals the CHANGELOG's version" the RELEASABLE state,
    so a manifest naming an undated version is a release that cannot be honestly dated. A
    manifest BEHIND the CHANGELOG — the mid-cycle state, where the next section is authored
    `— UNRELEASED` and the manifest still names the shipped one — stays green, because there is
    no release to date yet. Requiring the TOP section to be dated would red on every cycle;
    requiring the MANIFEST'S version to be dated reds exactly when shipping would be wrong.

    ⚠ The remedy is to date the section, never to drop the version from the heading: the version
    axis reads that heading, and so does the release harness.
    """
    if not PLUGIN.is_file():
        err("missing plugins/consolidate-memory/.claude-plugin/plugin.json")
        return
    version = json.loads(PLUGIN.read_text(encoding="utf-8")).get("version", "")
    if not version:
        return  # a versionless manifest is reported per doc by check_version_statements
    if changelog_date(version) is None:
        err(f"plugin.json is {version}, but CHANGELOG.md dates no `## [{version}]` section — "
            "that pair is what ships, and an undated section leaves every dated currency "
            "statement with nothing to check against (stamp the section if it exists, author it "
            "if it does not — `changelog_date` returns None for both, so this message cannot tell "
            "you which and names both remedies rather than the wrong one)")


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


def check_plugin_status_docs() -> int:
    """Each plugin's `docs/STATUS.md` opens on its OWN manifest's version, and nothing read it.

    Returns the number of headers checked, so `main` can report the coverage instead of implying it.

    Invariant 6, one manifest out. `check_version_statements` walks `LIVE_DOCS` against `PLUGIN` —
    consolidate-memory's manifest — so a doc opening on a DIFFERENT plugin's version is not only
    unchecked, it is checked *wrongly* if listed there (measured: two errors, invariant 10). The
    manifest such a doc tracks is the one beside it, so this discovers it the way
    `check_plugin_table` discovers its rows rather than naming it: `plugins/*/.claude-plugin/
    plugin.json`, paired with `plugins/<name>/docs/STATUS.md`. A third plugin is covered on landing.

    ⚠ THE SITE IS THE OPENING LINE, and that is a boundary rather than a claim of coverage. The
    sibling's own line 6 restates the same figure as a bare `**0.1.8**`, which carries no `v` and
    so is not a currency statement under `_CURRENCY` — this check does not read it. One site, pinned
    the way the badge and the plugin table are, and the class is not offered.

    ⚠ Paths are built from `ROOT` AT CALL TIME, never from the module-level `PLUGIN` constant. That
    is not style: `PLUGIN` is bound at import, so a caller that repoints `ROOT` — the in-tree pin in
    `tests/smoke.py` does exactly that, to exercise this check against a two-file fixture — would
    still have it reading the live manifest, and the pin would pass on a tree that never changed.
    """
    plugins = ROOT / "plugins"
    checked = 0
    for manifest in sorted(plugins.glob("*/.claude-plugin/plugin.json")):
        name = manifest.parent.parent.name
        rel = f"plugins/{name}/docs/STATUS.md"
        path = ROOT / rel
        if not path.is_file():
            continue                        # optional per plugin — the printed count is the coverage
        version = json.loads(manifest.read_text(encoding="utf-8")).get("version", "")
        if not version:
            err(f"{rel} tracks {name!r}'s manifest, which carries no version — the check cannot run")
            continue
        lines = path.read_text(encoding="utf-8").splitlines()
        first = lines[0] if lines else ""
        if f"v{version}" not in first:
            err(f"{rel}:1: the opening line is this plugin's currency statement and must carry "
                f"v{version}, {name!r}'s manifest version; it states "
                f"{_CURRENCY.findall(first)!r} — a header that outlives its manifest is the same "
                "drift invariant 6 catches, one plugin out")
        elif name not in first:
            err(f"{rel}:1: the line carries v{version} but never names {name!r} — this check pairs "
                "each manifest with the header beside it, so a header naming no plugin cannot be "
                "attributed to one")
        else:
            checked += 1
    return checked


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


# v0.4.61 (RC-4): the matcher must not assume a header LEADs with its status word.
# ⚠ The first draft was `^\s*[>*_\-]*\s*\**\s*status…` — anchored on `status` starting the line — and
# a review lens measured the cost: `docs/cm-commands-onboarding.spec.md:3` reads
# `**Design-of-record for the five UX verbs…** Status: draft for advisor pass → …` and was NAMED in
# CHANGELOG §0.4.8, so a stale, release-named drafting line survived the very sweep written to catch
# it. A gate whose matcher assumes a SPELLING has a blind spot proportional to the spelling.
# `.*?` (lazy, no DOTALL) matches the minimal prefix on the line, so the word may sit anywhere in it.
# ⚠ TWO SHAPES, RANKED. A bare `\bstatus\b` search takes the FIRST line that merely CONTAINS the
# word — which can be a PROSE MENTION sitting above the real declaration. MEASURED on
# `docs/1.0-preflight.spec.md`: it matched line 5 (`… call reads. Status per item: ✓ certified …`) and
# never the `**STATUS (2026-09-24): …**` at line 8 that `LIVE_DOCS` reads — so the gate counted the
# file as EXAMINED while inspecting a sentence, and rewriting line 8 to DRAFT would have left it
# green. A declaration wins over a mention; a mention is still accepted, because a status stated
# mid-sentence is a real shape (see `cm-commands-onboarding.spec.md`).
_SPEC_STATUS_DECL = re.compile(r"(?im)^\s*[>*_\-]*\s*\**\s*status\b[^\n]*")
# ⚠ A2 (v0.4.63): the fallback requires the LABEL shape — `status` immediately followed by a
# colon (markup between) — not merely the word. Measured: narrowing this way drops the
# deletion-mutation leaks 7 → 1 while KEEPING the mid-sentence declaration it exists for
# (`**Design-of-record for the five UX verbs…** Status: draft for advisor pass…`), and it drops
# `Status per item:`, `status WORD`, `STATUS.md`, `phase C status note` and `cm status —`.
_SPEC_STATUS_MENTION = re.compile(r"(?im)^.*?\bstatus\b\s*\**:[^\n]*")

# ⚠ THE SWEEP'S OWN CONVENTION IS A TRAP FOR THE MENTION FALLBACK, and a late review lens measured it:
# the v0.4.61 sweep preserves each retired line inside a blockquote BEGINNING `**Drafting-era status —
# never revisited after the arc closed.**`, which matches `_SPEC_PRE_SHIPPING` through "Drafting". So in
# any swept spec, if the LIVE declaration is deleted (the cheap fix this gate's own message invites) or
# pushed past the window, a fallback landing on the PRESERVED line would RED while quoting HISTORY as
# "the header still states a pre-shipping status". Measured: 0 misfires today — the pass rested entirely
# on the live line happening to precede the quote. The provenance note is not a declaration, and is
# excluded by its own words.
# ⚠ WIDENED at v0.4.63 from `drafting-era status` to `drafting-era\b`: the sweep writes the note as
# `**Drafting-era status — never revisited…**`, and a variant whose wording differs by one word
# would have slipped the boundary.
_SPEC_PROVENANCE_QUOTE = re.compile(r"(?i)drafting-era|preserved verbatim")


def _spec_header_end(lines: "list[str]") -> int:
    """v0.4.64: the index ending a spec's HEADER REGION — the first `## ` heading, the preamble cap,
    or the sweep's provenance note, whichever comes first.

    **A boundary is a property of the FIELD, not of the reader that happened to observe the defect.**
    Every reader of a header takes `lines[:_spec_header_end(lines)]`. Before this helper three readers
    each computed their own bound — and the target-release scan had none — so one header was read in
    three different regions.

    ⚠ The note must be a **BLOCKQUOTE** line. The sweep writes its own correction sentence into the
    LIVE header (*"⚠ The drafting-era status survived because no gate re-read it"*), so matching the
    phrase alone cut **four** live specs at the sweep's feedback instead of at the quote — regions
    ending at lines 3/3/9/5 rather than at their `## ` headings 5/5/11/8. **That is v0.4.63's own
    lesson — the sweep writes prose into the header the gate reads — broken by the sweep that
    recorded it.**

    ⚠ The two downstream cuts (`_spec_status_line`'s, and the statement join's `_cut2`) are
    **load-bearing, not defensive**: because the region now runs *past* that live correction sentence,
    they are what remove it from the window and the statement. MEASURED: `_cut2` fires on 4 specs.

    ⚠ KNOWN ASYMMETRY: this is a **LINE-index** cut where the cuts it replaces were **CHARACTER-index**.
    They diverge when a declaration shares a line with a provenance phrase — the whole line drops, so
    the spec goes `checked` 1 → 0 and stops being examined, SILENTLY. MEASURED: 0 live instances, but
    4 lines carry a phrase after non-markup text, so the shape exists. **`checked` is the tell** —
    re-measure it whenever this region changes.

    ⚠ The heading predicate `ln.startswith("## ")` now lives HERE and nowhere else: the arms consume
    this helper rather than computing their own bound, so the drift this comment used to warn about
    ("a fresh regex here would let the two regions drift") can no longer occur. An earlier version
    kept the predicate inline AND warned about a second site — a stale justification for its own
    absence, which a review lens measured as vacuous (one executable `startswith("## ")` remains).
    """
    # ⚠ `min` of three first-hits, in the `next(…, default)` idiom this file already uses — and
    # BOTH scans are bounded to `_n = min(len(lines), cap)`.
    # ⚠ v0.4.65: an earlier form (this PR's own first cut, adopted because a review lens suggested
    # the idiom) scanned ALL of `lines` for both the heading and the note. The RESULT was identical —
    # measured across all 58 specs — but the COST was not: **15,074** provenance searches over the
    # corpus against **968** for the bounded scan — ⚠ 6,960 is the cap-bound CEILING (58 x 120), not
    # the cost; a review lens caught this line pairing a measured figure with a theoretical one —
    # because a spec whose heading sits at
    # line 8 still had every one of its lines searched for a note. The longest spec here is 3,646
    # lines. ⚠ Equivalence proven by RESULT is not equivalence proven by COST, and this gate runs in
    # CI on every push.
    # ⚠ v0.4.66: the note must be a BLOCKQUOTE line. MEASURED: the sweep whose OUTPUT this boundary
    # exists to fence off writes its own correction sentence into the LIVE header — "⚠ The
    # drafting-era status survived because no gate re-read it" — and the phrase alone therefore
    # matched four specs' *live* lines, cutting the region at the sweep's own feedback instead of at
    # the preserved quote. Anchoring on `>` is exact: the marker the sweep writes is
    # `> **Drafting-era status — never revisited after the arc closed.**`, and its live sentences are
    # never quoted. ⚠ This is v0.4.63's own recorded lesson — "the sweep writes prose into the header
    # the gate reads, so its own annotation must be written around the detector's vocabulary" —
    # broken by the sweep that recorded it.
    _n = min(len(lines), _SPEC_PREAMBLE_CAP)
    _hd = next((k for k in range(_n) if lines[k].startswith("## ")), len(lines))
    _note = next((k for k in range(min(_hd, _n))
                  if lines[k].lstrip().startswith(">") and _SPEC_PROVENANCE_QUOTE.search(lines[k])), _n)
    return min(_hd, _note, _n)


def _spec_status_line(window: str):
    """The status DECLARATION in a header window, or None.

    Prefers a line that LEADS with the status word; falls back to one that merely mentions it — and
    STOPS at the sweep's provenance note, because everything after it is preserved HISTORY, not the
    header's own status. ⚠ Excluding matches by their own text is not enough: the swept blockquote's
    SECOND line is `> Status: draft → …`, which is DECL-shaped, so a text-level exclusion leaves the
    fallback landing on it — measured. The note is a BOUNDARY, not a filter."""
    _cut = _SPEC_PROVENANCE_QUOTE.search(window)
    if _cut:
        window = window[:_cut.start()]
    m = _SPEC_STATUS_DECL.search(window)
    if m:
        return m
    return _SPEC_STATUS_MENTION.search(window)
# ⚠ A4 (v0.4.63): the rule that needs no versioned CITATION. A header that names
# `Target release: vX.Y.Z` where **vX.Y.Z already exists as a release section** is stale by definition.
# ⚠ The version must be ADJACENT to the label (markup only between), which excludes the drafting-era
# `target: cm v0.1.49` form.
# ⚠ CORRECTED (v0.4.64, defect 2). This said the arm's two instances "are named NOWHERE in
# CHANGELOG.md — the citation OPERAND hides them, not the matcher". True when written (`24e2ea8`);
# false one commit later, when `e0a8970` — a descendant — added both citations. Re-measured: all 17
# target-bearing specs are named there and the arm fires on 0. Stated historically; see the arm's own
# comment in `check_spec_status`.
# ⚠ CORRECTED (v0.4.64, defect 3). This said "an UNSHIPPED target anywhere in the preamble suppresses
# the arm, so a spec legitimately aiming at a future release stays silent". No suppression is
# implemented — the arm filters to targets that HAVE shipped, so a future-ONLY target is silent by the
# FILTER, while a header naming both a shipped and an unshipped target FIRES. The claim now matches the
# code (recall-biased), which is the disposition the operator chose over implementing suppression.
_SPEC_TARGET_RELEASE = re.compile(r"(?i)target(?: release)?\s*:?\s*\**\s*(v?\d+\.\d+\.\d+)\b")
_SPEC_PREAMBLE_CAP = 120      # `marker-coordinate-truth`'s label sits at line 84, past the 40-line window

# ⚠ …and a window, not a line 1. Two specs state their status further down a header the v0.4.61 sweep
# itself lengthened, and two state it as a title (`— spec DRAFT`), which carries no `status` word at
# all. Both were invisible to a 14-line, `status`-only search.
_SPEC_STATUS_WINDOW = 40
_SPEC_TITLE_DRAFT = re.compile(r"(?i)\bdraft\b")
# ⚠ `_SPEC_DONE` must be NEGATION-AWARE, and both predicates must see the SAME string. The first draft
# matched DONE over `line[:60]` while PRE saw the whole line — two predicates over two strings — and
# DONE was negation-blind, so `awaiting approval; nothing shipped yet` and `drafted, unimplemented`
# were both EXEMPTED by the very words that state the defect. A silent false negative on a coverage
# gate is the failure this repo has a standing lesson about.
# ⚠ A3 (v0.4.63): the alternative list was missing the shapes four headers actually use — MEASURED.
# `revised for review` (`marker-coordinate-truth`), `design-of-record` (`periphery-parity`,
# `store-classifier-parity`), `ready to ship` (`dangling-cross-store-resolution`) and
# `awaiting approval` (`0.4.5-issue-closeout`) all state a vetting state and none was matched, so those
# headers were invisible to every arm. ⚠ Widened WITH A4, never alone: the target-release arm is what
# keeps a spec legitimately aiming at a FUTURE release silent, so the vocabulary can afford to be wide.
_SPEC_PRE_SHIPPING = re.compile(
    r"awaiting|pending|→\s*implementation|for adversarial review|proposed v|"
    r"amend-\d+ folded|review-to-zero|unimplemented|nothing shipped|"
    r"revised for review|design-of-record|ready to ship", re.I)
# ⚠ `draft` is NOT a bare alternative — it needs a CLAIM CONTEXT. MEASURED: with it bare, raising the
# statement cap to reach a wrapped status made `index-usage-and-budget-ladder` fire, purely on prose that
# reads *"a code-review-skill gate on the draft: 6 finder angles…"* — a header whose status is
# "Phase A/B/C SHIPPED". The word is the canonical status word, so it cannot simply be dropped; it must be
# adjacent to a status label or bare emphasis.
_SPEC_DRAFT_CLAIM = re.compile(r"(?i)(?:\bstatus\b|[:*])\s*\**\s*draft")
_SPEC_DONE = re.compile(r"\b(?:SHIPPED|shipped|implemented|implementation complete)\b", re.I)
# ⚠ NEGATION IS CHECKED BY DISTANCE, NOT BY A LOOKBEHIND. The first cut was fixed-width
# (`(?<!un)(?<!not )(?<!nothing )(?<!never )`), and that is DISTANCE-anchored: in
# `**Status: draft — not yet shipped.**` the token is preceded by `yet `, not `not `, so the guard
# passed and a genuinely stale header was EXEMPTED BY THE WORDS STATING ITS DEFECT. MEASURED against
# the shipped regexes, along with `draft (hasn't shipped yet)` and `awaiting approval; not yet
# implemented` — only the exact spellings the earlier review round happened to quote were caught.
_SPEC_NEGATED = re.compile(
    r"(?i)(?:\bnot\b|\bno\b|\bnever\b|\bnothing\b|\byet\b|\bun\b|\bun$|without"
    r"|hasn['\u2019]?t|haven['\u2019]?t|isn['\u2019]?t|doesn['\u2019]?t|has yet to)")
# ⚠ `['\u2019]` — the straight AND the typographic apostrophe, the same idiom `_KEEP_RE` already uses.
# A contraction the reader types with a curly quote is the same negation; matching only `'` is a
# spelling-blindness of exactly the kind this gate exists to avoid.
_SPEC_NEG_WINDOW = 24      # chars of lookback searched for a negation


def spec_done(stated: str) -> bool:
    """True when the statement ASSERTS shipping — i.e. a DONE token with no negation just before it.

    ⚠ A FUNCTION, not a single lookbehind: the negation may be separated from the token by any number
    of words (`not yet shipped`, `has not been implemented`), and a fixed-width guard cannot express
    that. See the note on `_SPEC_NEGATED` for the measurement that forced this."""
    for m in _SPEC_DONE.finditer(stated):
        if not _SPEC_NEGATED.search(stated[max(0, m.start() - _SPEC_NEG_WINDOW):m.start()]):
            return True
    return False
_RELEASE_SECTION = re.compile(r"^##\s*\[(\d+\.\d+\.\d+)\]", re.M)


def release_sections(ch: str) -> "list[tuple[str, str]]":
    """`(version, body)` for every `## [X.Y.Z]` release section in the CHANGELOG.

    `re.split` with a capturing group yields `[preamble, v1, body1, v2, body2, …]`, so the pairs walk
    every other index — the bodies are the section TEXT, which is what a citation search must see."""
    parts = _RELEASE_SECTION.split(ch)
    return [(parts[i], parts[i + 1]) for i in range(1, len(parts) - 1, 2)]


def check_spec_status() -> int:
    """v0.4.61 (RC-4): a `docs/*.spec.md` whose header still states a DRAFTING-era state while
    CHANGELOG.md names that file inside a `## [X.Y.Z]` release section.

    ⚠ **THIS CONTRACT HAS TWO ARMS since v0.4.63, and this docstring described only the first until
    v0.4.64** — a review lens measured it, after the file-level invariant list had already been
    corrected for the same omission. The SECOND needs NO citation: a header stating a pre-shipping
    status while naming a `Target release:` that has **already shipped** is stale by definition. It
    is the `elif`, so it fires only where the citation arm did not — which is exactly why the
    distinction matters and why a reader told "there is one rule here" would miss it.

    ⚠ WHY THIS EXISTS. `LIVE_DOCS` is a VERSION-CURRENCY set — membership means "this doc's version
    statement goes stale when a release lands". A spec's STATUS is a different axis and was in NO
    set, so a drafting-era line could survive every check: four headers did, for months, with the
    whole suite green, and the census that followed found SIXTEEN pre-shipping headers, 13 of them
    release-named under THIS matcher (docs/asserted-support.spec.md §RC-4). ⚠ That count moved TWICE,
    once per matcher fix — 13, then 14 when the word was searched anywhere on the line, then 13 again
    when a DECLARATION was ranked above a prose mention — which is this docstring's own lesson turned
    on it: a gate's NUMBER is a property of its matcher, and every fix to one must re-measure the other.
    Nothing ever REVISITS a spec header once the arc closes. That is `gate-coverage-is-its-match-set` — a gate proves only what its
    matcher can see.

    ⚠ THE RULE IS VERSIONED ON PURPOSE. Its first form was "cited ANYWHERE in CHANGELOG", and that
    measurement was CIRCULAR: the same signal was both the rule's input and the evidence that the
    work had landed. Restricting the citation to text inside a `## [X.Y.Z]` section makes the signal
    independent, and the corpus's legitimately-unreleased specs drop out on their own — TWO of them
    (`0.4.5-issue-closeout.spec.md`, `track-c-ci-docs-hygiene.spec.md`). ⚠ This said "one" until a review
    lens counted them; a gate whose own account of its blind spot understates it by half is the lesson
    in the paragraph above, applied to the paragraph itself.

    ⚠ HONEST LIMIT, stated rather than buried: a release section could cite a spec FORWARD ("staged
    for a later release"), which would fire on a legitimately-open spec. The message names both
    readings, and the remedy — update the header — is correct under either. A gate with a stated
    ceiling, not a proof.

    ⚠ SECOND, MEASURED, and found while closing a third: the MENTION fallback can still land on ordinary
    PROSE that happens to contain "status" when a spec has no declaration at all. Probed across the
    corpus — remove every `Status…`-leading line, then ask what the fallback finds — **2 of 50 specs
    leak**: `completion-driven-archiving.spec.md` (a continuation line of the deleted declaration) and
    `index-usage-and-budget-ladder.spec.md` (a genuine "Phase C status note"). ⚠ The remedy is to state
    the shape, not to widen again: the fallback exists for the MID-SENTENCE declaration
    (`cm-commands-onboarding.spec.md` was one before the sweep), and a spec that deletes its declaration
    entirely is the pathological case this gate's own message invites. Left live and recorded rather
    than narrowed, because narrowing it would drop the mid-sentence shape that caught a real file.

    Returns the number of spec status lines EXAMINED, for the ✓ line's denominator: without it a
    scan that stopped finding status lines would print exactly as green as one examining everything.
    """
    sections = release_sections(read("CHANGELOG.md"))
    checked = 0
    for spec in sorted((ROOT / "docs").glob("*.spec.md")):
        lines = spec.read_text(encoding="utf-8", errors="replace").splitlines()
        # ⚠ v0.4.64: ONE region, bound once and sliced nowhere else. `_spec_header_end` bounds the
        # heading, the cap AND the provenance note together — `_spec_status_line`'s own internal cut
        # is now a no-op on this window (kept as a defensive guard for a caller handing it a raw str).
        _hdr = lines[:_spec_header_end(lines)]
        _win = "\n".join(_hdr)
        m = _spec_status_line(_win)
        if m:
            # ⚠ THE STATEMENT, NOT THE LINE. The matcher LOCATES the status over a 40-line window but
            # `[^\n]*` captures only to the end of that one line — so a status that WRAPS was judged on
            # its first line alone. MEASURED: `**Status: all three lenses have signed off; the code is` /
            # `awaiting merge.**` yielded a first line with no PRE token, and the gate stayed silent on
            # a pre-shipping, release-named spec. The release's own design-of-record was the live
            # instance (`awaiting merge` on line 4, which no predicate saw). The statement is the
            # matched line plus its continuation up to a blank line, capped.
            # ⚠ A1's sibling (v0.4.63): the DECLARATION's own line, not merely the first line matching
            # EITHER shape. v0.4.62 ranked a DECL above a MENTION when locating the window match but left
            # this statement locator taking `next(… if _spec_status_line(ln))`, so
            # `docs/1.0-preflight.spec.md` was STILL judged on line 5's prose while its declaration sits at
            # line 8. A late review lens measured it as v0.4.62's own residual.
            # ⚠ A5 (v0.4.63): the search region is the PREAMBLE — the lines before the first `## `
            # heading — not a fixed 40. `docs/marker-coordinate-truth.spec.md` declares its status at
            # line 84 and its header runs to line 93, so a 40-line window never reached it. ⚠ The
            # diagnostic that found this first claimed SEVEN files were unreached; six were body prose
            # and one a table row, which the gate is RIGHT to ignore — measure with the instrument.
            # ⚠ v0.4.64: the SAME region as the window above — this per-line locator used to rebuild
            # `min(_hd, cap)` itself and, unlike `_spec_status_line`, never applied the provenance
            # boundary. MEASURED **PRE-FIX** — the only informative direction, since post-fix the
            # bound makes it impossible BY CONSTRUCTION: **0 of the 26** note-carrying specs land at
            # or after the note, so the bound is observationally a no-op and this is a regression
            # GUARD, not a pin. ⚠ An earlier version of this line said "0 of 52", which names the
            # wrong population — only 26 of the 58 specs carry a note at all — and, quoted post-fix,
            # is a TAUTOLOGY rather than a measurement.
            _ix = next((k for k, ln in enumerate(_hdr) if _SPEC_STATUS_DECL.match(ln)), None)
            if _ix is None:
                _ix = next((k for k, ln in enumerate(_hdr)
                            if _SPEC_STATUS_MENTION.match(ln)), None)
            _jx = _ix
            # ⚠ `_ix is not None` is a conjunct of the GUARD, not just of the ternary below: without it
            # mypy cannot narrow `_ix` and `(_jx - _ix)` is an int-minus-optional.
            # ⚠ v0.4.64 (review finding): bounded by `len(_hdr)`, NOT `len(lines)`. The join walked
            # past the region — it is the ONE reader whose walk was not region-bounded — so `_pending`
            # could be selected by a clause the region deliberately EXCLUDES, while `_tgt` came from
            # the region: the two conjuncts of `elif _tgt and _pending` measured over two regions.
            # REACHABLE repro on pre-fix `main`: a region ending `**Status:** SHIPPED (v0.1.0).`
            # followed by a note line `⚠ awaiting review — Drafting-era history follows.` fires,
            # quoting `awaiting review` as a pre-shipping status, because `_cut2` truncates at the
            # phrase and the text BEFORE it on that line survives. MEASURED: 4 of 58 joins crossed the
            # region; bounding is a no-op on all 4 today (each crossing line IS the phrase match, so
            # `_cut2` already cut it) — a GUARD, not a pin. It makes this docstring's own invariant
            # true: every reader now takes the region.
            # ⚠ CORRECTION (review): "no-op" is accurate for the VERDICT and NOT for `stated`, which
            # is the operand `_cut2` and the firing message actually read. MEASURED: the clamp changes
            # `stated` for **3** live specs (`body-defragmentation`, `completion-driven-archiving`,
            # `group-lifecycle-completion`), each losing the trailing note-line prefix the old join
            # left behind. No observable in any firing path (`_pending` False→False for all three,
            # `checked` 52, errors 0), and it cannot EMPTY `stated` (`_ix < len(_hdr)` always) — so it
            # cannot silently drop a spec. Prose-level, but the operand is `stated`.
            while (_ix is not None and _jx is not None and _jx < len(_hdr)
                   # ⚠ SIX, not three. At three, a status that wraps to a fifth line
                   # (`asserted-support.spec.md`'s "awaiting merge" sits on line 6) fell outside the
                   # join and the header read as settled — the very instance A1 exists for. The
                   # provenance boundary and the DECL preference now bound the join, so the cap can
                   # afford to be generous. MEASURED: raising it adds no false positive.
                   and lines[_jx].strip() and (_jx - _ix) < 6):
                _jx += 1
            stated = " ".join(ln.strip() for ln in lines[_ix:_jx]) if _ix is not None else m.group(0).strip()
            # ⚠ AND the provenance note bounds the STATEMENT too, not just the locator. v0.4.62 applied
            # the boundary to `_spec_status_line`'s window and left the join reading RAW lines — so the
            # correction text this very gate's sweep writes (*"⚠ The drafting-era status survived
            # because…"*) was parsed as the header's own status and made a SHIPPED header read as
            # pre-shipping. MEASURED on the four swept headers that carry that sentence.
            _cut2 = _SPEC_PROVENANCE_QUOTE.search(stated)
            if _cut2:
                stated = stated[:_cut2.start()].strip()
        else:
            # The title-only form (`# … — spec DRAFT`) states a status with no `status` word at all.
            stated = lines[0].strip() if lines and _SPEC_TITLE_DRAFT.search(lines[0]) else ""
        if not stated:
            continue
        checked += 1
        # ⚠ A1 (v0.4.63): a DONE token NO LONGER EXEMPTS the statement. It did, and the live instance
        # survived TWO merges: `docs/asserted-support.spec.md` reads "implemented and REVIEWED … awaiting
        # merge" — both tokens — and "implemented" excused it. Judging the pending clause too is the
        # design decision; positional ranking ("last clause wins") was simulated and MEASURED producing a
        # FALSE NEGATIVE, because `network-graph-interaction`'s "pending merge" is followed by a later
        # shipped clause. A statement asserting BOTH is a contradiction, and `spec_done` now only
        # SELECTS THE MESSAGE.
        _pending = bool(_SPEC_PRE_SHIPPING.search(stated) or _SPEC_DRAFT_CLAIM.search(stated))
        # ⚠ ONE string for BOTH predicates. The first draft matched DONE over a 60-char slice while PRE
        # saw the whole line, so the two tests were about different text.
        named = [v for v, body in sections if spec.name in body]
        # ⚠ A4 (v0.4.63): a target release **that has already shipped** is stale with NO citation.
        # ⚠ THE OPERAND, corrected at v0.4.64. This read raw `lines[:_SPEC_PREAMBLE_CAP]` — two
        # over-reaches on one line, both found by the 2026-09-25 dream pass:
        #   (a) NO provenance boundary. `_SPEC_PROVENANCE_QUOTE` bounds the status locator and the
        #       statement join; this THIRD reader of the same field had no cut, so it read the
        #       preserved drafting-era blockquote as the header's own target. MEASURED: the region
        #       bound removes the target for 12 of the 17 — 11 on `>`-marked quote lines, the 12th
        #       an UNMARKED continuation. (Corpus counts live in the CHANGELOG; this is the operand
        #       comment. ⚠ The count here read "12 ... inside the blockquote" until v0.4.65, which
        #       over-states 11 of them.) The detail that used to follow: 12 of the 17
        #       target-bearing specs carry their version ONLY inside that quote, so the arm was reading
        #       preserved HISTORY for most of its population. ⚠ And the operand was RIGHT when the arm
        #       was authored — at `f0a4b75` this spec's target sat in the LIVE header, and `24e2ea8`,
        #       the commit that ADDED the arm, swept it into the quote in the same commit. The arm was
        #       dead on arrival for its own motivating instances; the sweep moved what it reads.
        #   (b) NO preamble bound — the status arms use `min(first '## ', cap)`; this used the bare cap
        #       and therefore read up to 120 lines REGARDLESS of where the header ends. ⚠ An earlier
        #       version of this bullet said those were "120 lines of BODY", and a review lens measured
        #       it false for the one spec it matters most for: `identity-from-the-input.spec.md` has
        #       its first `## ` at line 149, so its lines 27-120 are PREAMBLE — the region is a subset
        #       of the preamble, not an overrun into the body. What is true is narrower: the bound is
        #       INERT there (see the caveat below), not that it reads body.
        # Both now come from `_spec_header_end`, so the boundary has ONE site.
        # ⚠ CAVEAT on (b), measured: the preamble bound is **INERT for a spec whose first `## ` lies
        # at or past the cap and that carries no note** — there `min(hd, cap)` is just the cap, so the
        # region is byte-identical to the pre-fix `lines[:120]`. MEASURED: exactly TWO specs have
        # `hd >= 120`; `record-post-state.spec.md` (hd=212) is saved by its note at index 8, but
        # `identity-from-the-input.spec.md` (hd=149, no note) is bounded by nothing but the cap.
        # ⚠ This caveat first said those lines were "what the A5 rule calls BODY" — FALSE: with
        # `hd=149`, lines 0-148 ARE the preamble, so lines 27-120 are preamble too. The region is a
        # subset of the preamble, not an overrun into the body; what is inert is the BOUND, not the
        # region's membership. Verdict-safe today only because its target at line 27 is genuine
        # header text. The O2 pin cannot see this shape — its fixture's `## ` sits at index 4.
        # ⚠ CORRECTED CLAIM (defect 2, v0.4.64). This comment asserted, present tense, that the two
        # instance specs are named *"NOWHERE in CHANGELOG.md — the citation OPERAND hides them, not the
        # matcher"*. That was TRUE when the arm was added (`24e2ea8`) and FALSE one commit later:
        # `e0a8970`, a DESCENDANT of the commit that wrote the claim, swept the headers AND added both
        # specs to CHANGELOG.md. Re-measured on the live tree: **all 17** target-bearing specs appear
        # there and the arm fires on **zero** (`checked = 52`, `errors = []`). The repair invalidated
        # its own diagnosis. The arm is KEPT as future-proofing — a landed target is stale without
        # needing a citation — so the rationale is stated historically, never deleted.
        # ⚠ CORRECTED CLAIM (defect 3, v0.4.64). The constant's comment claimed *"an UNSHIPPED target
        # anywhere in the preamble suppresses the arm"*. The code never implemented suppression: `_tgt`
        # below filters to targets that HAVE shipped and the arm is `elif _tgt and _pending`, so a
        # header naming BOTH a shipped and an unshipped target FIRES. Stated as the code behaves —
        # recall-biased, with the future-ONLY case still silent (the `_tgt` filter is what keeps a spec
        # legitimately aiming at a future release quiet, not a suppression rule).
        _targets = {x.lstrip("v") for x in _SPEC_TARGET_RELEASE.findall("\n".join(_hdr))}
        _tgt = sorted(t for t in _targets if t in {v.lstrip("v") for v, _ in sections})
        if _pending and named:
            err(f"{spec.name}: the header still states a pre-shipping status ({stated[:90]!r})"
                + (" — ALONGSIDE a done-state, which is itself the contradiction"
                   if spec_done(stated) else "")
                + f" — while CHANGELOG.md names this file in the v{named[0]} release section. The header"
                  f" is stale (state what shipped) or the citation is forward-looking (say so in the header)")
        # ⚠ NO `spec_done` guard here. Leaving one in would be A1's hole re-committed inside the arm
        # written to close it — and it did exactly that to this release's OWN spec, which says
        # "implemented … awaiting merge". A pending clause beside a shipped target IS the contradiction;
        # a swept header (`Status: **SHIPPED (vX)**`) carries no pending clause, so this arm stays silent
        # on it without needing the guard.
        elif _tgt and _pending:
            err(f"{spec.name}: the header states a pre-shipping status ({stated[:90]!r}) while naming "
                f"\"Target release: v{_tgt[0]}\" — a release that ALREADY SHIPPED (CHANGELOG §v{_tgt[0]}). No "
                f"citation is needed for this arm: a target that has landed is stale by definition.")
    return checked


def main() -> int:
    check_badge()
    check_links()
    check_anchors()
    check_required_strings()
    check_contiguity()
    check_themes()
    check_changelog_dated()
    dated_eligible, dated_checked = check_version_statements()
    plugin_rows = check_plugin_table()
    status_headers = check_plugin_status_docs()
    spec_status = check_spec_status()
    check_preview()
    if errors:
        print("✗ documentation gate FAILED:")
        for e in errors:
            print(f"  - {e}")
        # ⚠ THE PAIR PRINTS ON THIS PATH TOO, and it is not decoration. `checked != eligible` is
        # reachable ONLY here: a green run requires every statement to name the manifest's version,
        # and the undated case is exactly what `check_changelog_dated` refuses — so printing the
        # pair only beside the ✓ made the one distinction it exists to draw unobservable, since
        # every run that reaches the ✓ has the two numbers equal by construction. It prints as a
        # parenthesized aside rather than a `  - ` line, so it is never read as another error.
        print(f"  ({dated_checked} of {dated_eligible} dated statements checked)")
        return 1
    version = json.loads(PLUGIN.read_text(encoding="utf-8"))["version"]
    # The denominators are not decoration: without them a reader cannot tell "0 problems in 7
    # required strings" from "0 problems in 0", and a check that has silently stopped examining
    # anything prints exactly as green as one that examined everything. The date axis prints a
    # PAIR for the same reason: those two numbers differ exactly when a dated statement was
    # found and then skipped, which is the one failure a single count cannot express — and since
    # that state is always a RED one, the pair is printed on the failing path above as well.
    print(f"✓ docs valid (badge + {len(LIVE_DOCS)} live-doc statements at v{version}, "
          f"{dated_checked} of {dated_eligible} dated statements checked, "
          f"{plugin_rows} plugin-table rows, "
          f"{status_headers} plugin STATUS headers, "
          f"{spec_status} spec status lines, "
          f"{len(DOCS)} files link-checked, "
          f"{sum(len(_n) for _, _n in REQUIRED_STRINGS.values())} required strings unbroken "
          f"across {len(REQUIRED_STRINGS)} files, anchors balanced, "
          "preview current)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
