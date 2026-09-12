#!/usr/bin/env python3
"""Documentation drift gate — zero-dependency, no browser, no network.

Docs rot silently: a badge keeps advertising a version that shipped three releases ago, a
renamed section leaves the table of contents pointing at nothing, a moved file turns a link
into a 404 that only a reader ever sees. None of that breaks a build, so nothing catches it.
This does, in the same stdlib-only style as smoke.py / validate_manifests.py, and it runs as
its own CI job (`docs`) rather than inside the 7-way test matrix — the answers do not vary
by Python version or OS.

Five invariants:

1. **Badge ↔ manifest.** The shields version badge is a hand-written URL that nothing else
   reads, so it silently drifts from plugin.json. `release.sh` rewrites both in the same
   commit; this asserts they agree.
2. **Every relative link resolves the way GitHub resolves it** — doc-relative with no
   repo-root fallback, in the README and every other doc a reader lands on from it, raw
   HTML `href`/`src` included.
3. **Manual anchors are balanced.** The README uses explicit `<a id="…">` markers because
   GitHub's auto-slugifier handles emoji-prefixed headings badly, which means a typo can
   silently orphan a section (or a link) with no error anywhere.
4. **The theme table matches the shipped theme set, both ways** — a palette added to the
   toggle without a docs row, and a row left behind by a palette that no longer ships.
5. **Every live doc states the current release**, closing the version-sweep class: the sweep
   is a manual grep, and three consecutive releases left statements behind (v0.4.14 missed
   five files; v0.4.24 missed four of the same ones). This runs on every PR, not just at
   release time, so a doc can no longer advertise a superseded version.
6. **The committed preview matches a fresh render**, closing the same class for a *generated*
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

# Docs a reader can arrive at from the README. Templates are included because a broken link
# in an issue form is invisible until someone opens the form.
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
    # Every doc the README links to, so a dead link one hop out is still caught — the
    # docstring's promise is "every other doc a reader lands on from it".
    "docs/network-guide.md",
    "docs/nocturne-design.md",
    "docs/deep-field-theme.spec.md",
]

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

# A literal `v` is what separates a currency statement from a version *mention*, and it is
# not cosmetic — a bare `\d+\.\d+\.\d+` mis-fires on two things in these very files: the
# README's shields URL — whose version token carries no `v` and is renamed every release,
# so it is cited by shape (`badge/version-<X.Y.Z>`) rather than by a value that rots — and
# preflight's `**1.0.0**` (the release the checklist certifies, not the current one). Both
# measured; neither is a false positive under this rule, and it finds the right token in all
# six docs.
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


def check_required_strings() -> None:
    """The cross-project workflow the README must keep documenting."""
    readme = read("README.md")
    for needle in REQUIRED_IN_README:
        # Word-bounded, not a bare substring: renaming `/cm-network` to `/cm-network2`
        # leaves a superset that CONTAINS the needle, so a containment test keeps passing
        # while the documented command no longer exists. Found by mutation, not by review.
        if not re.search(rf"(?<![\w/-]){re.escape(needle)}(?![\w-])", readme):
            err(f"README.md no longer mentions {needle!r} (smoke.py pins it as the documented workflow)")


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
        dashboard_fixture.write_preview(Path(td))
        for name in PREVIEW_FILES:
            fresh, committed = Path(td) / name, PREVIEW / name
            if not committed.is_file():
                err(f"preview file is missing: docs/previews/nocturne/{name}")
            elif fresh.read_bytes() != committed.read_bytes():
                err(f"docs/previews/nocturne/{name} is stale — regenerate both with "
                    "`python3 tests/dashboard_fixture.py --out docs/previews/nocturne`")


def main() -> int:
    check_badge()
    check_links()
    check_anchors()
    check_required_strings()
    check_themes()
    check_version_statements()
    check_preview()
    if errors:
        print("✗ documentation gate FAILED:")
        for e in errors:
            print(f"  - {e}")
        return 1
    version = json.loads(PLUGIN.read_text(encoding="utf-8"))["version"]
    print(f"✓ docs valid (badge + {len(LIVE_DOCS)} live-doc statements at v{version}, "
          f"{len(DOCS)} files link-checked, anchors balanced, preview current)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
