#!/usr/bin/env python3
"""Validate the plugin + marketplace manifests — zero-dependency, no `claude` CLI needed.

Portable stand-in for `claude plugin validate` (which isn't available everywhere): checks
the schema essentials that actually break installs/updates, so it can run in a pre-release
check anywhere Python does. Pairs with smoke.py / simulate_accumulation.py.

Run:  python3 tests/validate_manifests.py   (exit 0 = valid)
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MARKET = ROOT / ".claude-plugin" / "marketplace.json"
KEBAB = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*$")          # plugin/marketplace name charset
SEMVER = re.compile(r"\d+\.\d+\.\d+(?:[-+].+)?$")          # MAJOR.MINOR.PATCH(+meta)

errors: list[str] = []


def err(msg: str) -> None:
    errors.append(msg)


def _load(path: Path) -> dict | None:
    if not path.exists():
        err(f"missing manifest: {path.relative_to(ROOT)}")
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        err(f"invalid JSON in {path.relative_to(ROOT)}: {exc}")
        return None


def main() -> int:
    mk = _load(MARKET)
    if mk is not None:
        if not KEBAB.match(str(mk.get("name", ""))):
            err(f"marketplace.json name not kebab-case: {mk.get('name')!r}")
        if not isinstance(mk.get("owner"), dict) or not mk["owner"].get("name"):
            err("marketplace.json missing owner.name")
        plugins = mk.get("plugins")
        if not isinstance(plugins, list) or not plugins:
            err("marketplace.json has no plugins[]")
        for i, entry in enumerate(plugins or []):
            name, source = entry.get("name"), entry.get("source")
            if not KEBAB.match(str(name or "")):
                err(f"plugins[{i}].name not kebab-case: {name!r}")
            if not isinstance(source, str) or not source.startswith("./"):
                err(f"plugins[{i}].source must be a relative './' path (got {source!r})")
            else:
                pdir = (ROOT / source).resolve()
                if not pdir.is_dir():
                    err(f"plugins[{i}].source path does not exist: {source}")
                pj = pdir / ".claude-plugin" / "plugin.json"
                plugin = _load(pj)
                if plugin is not None:
                    if plugin.get("name") != name:
                        err(f"plugin.json name {plugin.get('name')!r} != marketplace entry {name!r}")
                    ver = plugin.get("version")
                    if ver is None:
                        err(f"{pj.relative_to(ROOT)} missing version (omit it ONLY for commit-SHA mode)")
                    elif not SEMVER.match(str(ver)):
                        err(f"{pj.relative_to(ROOT)} version not semver: {ver!r}")
                    # the docs warn against setting version in BOTH places (plugin.json wins silently)
                    if "version" in entry:
                        err(f"plugins[{i}] sets version in BOTH marketplace.json and plugin.json — keep it in plugin.json only")

    if errors:
        print("✗ manifest validation FAILED:")
        for e in errors:
            print(f"  - {e}")
        return 1
    ver = json.loads((ROOT / "plugins/consolidate-memory/.claude-plugin/plugin.json").read_text())["version"]
    print(f"✓ manifests valid (consolidate-memory v{ver})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
