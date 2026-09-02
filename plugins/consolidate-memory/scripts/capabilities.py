#!/usr/bin/env python3
"""Extensible capability detectors. Closed Python stacks remain one family, not the universe."""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

DETECTOR_VERSION = "1"

# Evidence-producing detectors. Each returns (tag, evidence, confidence) or None.
# Classes named in the audit: Node/TS, Go, Rust, JVM/.NET, Docker/K8s, Terraform/cloud,
# databases, CI/CD, build/test, OS/package managers — plus the existing Python family.


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _exists(root: Path, *rel) -> bool:
    return (root.joinpath(*rel)).exists()


def load_capability_overrides(plugin_data: Path, project_id: str) -> dict:
    """User overrides for detectors. File is opt-in; missing → {} (no clobber).

    Shape: ``{"add": [...], "remove": [...]}`` at the top level, or keyed by
    ``project_id`` for per-project overrides.
    """
    import json
    path = Path(plugin_data) / "capability-overrides.json"
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    scoped = data.get(project_id)
    if isinstance(scoped, dict):
        return scoped
    if "add" in data or "remove" in data or "include" in data or "exclude" in data:
        return data
    return {}


_CACHE_FILES = (
    "pyproject.toml", "setup.py", "mypy.ini", ".mypy.ini", "package.json",
    "tsconfig.json", "go.mod", "go.work", "Cargo.toml", "pom.xml",
    "Dockerfile", "docker-compose.yml", "pnpm-workspace.yaml",
    "lerna.json", "nx.json", "Gemfile", "composer.json",
)


def _detector_sig(root: Path) -> str:
    parts: list = []
    for name in _CACHE_FILES:
        p = root / name
        try:
            parts.append("%s:%s" % (name, int(p.stat().st_mtime) if p.is_file() else 0))
        except OSError:
            parts.append("%s:0" % name)
    # v0.4.0 review: monorepo CHILD markers are part of the detection surface
    # (the workspace scan reads children's package.json/go.mod/…) but were not
    # part of the signature — a child marker change served a stale cache. Fold
    # the scanned children's markers into the sig.
    ws = next((n for n in ("pnpm-workspace.yaml", "go.work", "lerna.json", "nx.json")
               if (root / n).is_file()), None)
    if ws is not None:
        try:
            kids = sorted(p for p in root.iterdir()
                          if p.is_dir() and not p.name.startswith("."))
        except OSError:
            kids = []
        for child in kids[:32]:
            for cname in ("package.json", "go.mod", "pyproject.toml"):
                cp = child / cname
                try:
                    parts.append("%s/%s:%s" % (
                        child.name, cname,
                        int(cp.stat().st_mtime) if cp.is_file() else 0))
                except OSError:
                    parts.append("%s/%s:0" % (child.name, cname))
    return "|".join(parts)


def detect_capabilities(project_dir: Path, *, overrides: Optional[dict] = None,
                        observation_time: Optional[str] = None,
                        cache_dir: Optional[Path] = None,
                        project_id: str = "") -> list:
    """Return a list of {tag, evidence, confidence, detector_version, observed_at}."""
    root = Path(project_dir)
    observed = observation_time or _now()
    sig = _detector_sig(root)
    if cache_dir is not None and project_id:
        import json
        cp = Path(cache_dir) / "capability-cache.json"
        try:
            cached = json.loads(cp.read_text(encoding="utf-8")) if cp.is_file() else {}
        except (OSError, ValueError, TypeError):
            cached = {}
        hit = cached.get(project_id) if isinstance(cached, dict) else None
        if isinstance(hit, dict) and hit.get("sig") == sig and isinstance(hit.get("rows"), list):
            return list(hit["rows"])
    found: list = []

    def add(tag: str, evidence: str, confidence: float = 0.9) -> None:
        found.append({
            "tag": tag,
            "evidence": evidence,
            "confidence": confidence,
            "detector_version": DETECTOR_VERSION,
            "observed_at": observed,
        })

    # Python family (existing closed set, now one class among many)
    if list(root.glob("*.py")) or _exists(root, "pyproject.toml") or _exists(root, "setup.py"):
        add("python", "python-sources-or-pyproject")
    if _exists(root, "mypy.ini") or _exists(root, ".mypy.ini"):
        add("mypy", "mypy-config")
    if _exists(root, "package.json"):
        add("node", "package.json")
        try:
            txt = (root / "package.json").read_text(encoding="utf-8", errors="replace")[:65536]
        except OSError:
            txt = ""
        if "typescript" in txt or _exists(root, "tsconfig.json"):
            add("typescript", "tsconfig-or-dep")
    if _exists(root, "tsconfig.json") and not any(x["tag"] == "typescript" for x in found):
        add("typescript", "tsconfig.json")
    if _exists(root, "go.mod"):
        add("go", "go.mod")
    if _exists(root, "Cargo.toml"):
        add("rust", "Cargo.toml")
    if (_exists(root, "pom.xml") or _exists(root, "build.gradle")
            or _exists(root, "build.gradle.kts") or list(root.glob("*.java"))
            or list(root.glob("*.kt"))):
        add("jvm", "maven-gradle-or-jvm-sources")
    if list(root.glob("*.csproj")) or list(root.glob("*.fsproj")) or _exists(root, "global.json"):
        add("dotnet", "csproj-or-global.json")
    if (_exists(root, "Dockerfile") or _exists(root, "docker-compose.yml")
            or _exists(root, "compose.yml") or _exists(root, "compose.yaml")):
        add("docker", "dockerfile-or-compose")
    if list((root / "k8s").glob("*")) if (root / "k8s").is_dir() else False:
        add("kubernetes", "k8s/")
    else:
        for p in list(root.glob("*.yaml")) + list(root.glob("*.yml")):
            try:
                head = p.read_text(encoding="utf-8", errors="replace")[:400]
            except OSError:
                continue
            if "apiVersion:" in head and ("kind:" in head):
                add("kubernetes", p.name)
                break
    if list(root.glob("*.tf")) or _exists(root, "terragrunt.hcl"):
        add("terraform", "tf-or-terragrunt")
    if (_exists(root, "prisma") or _exists(root, "alembic.ini")
            or _exists(root, "migrations") or list(root.glob("*.sql"))):
        add("database", "orm-migrations-or-sql")
    if (_exists(root, ".github", "workflows") or _exists(root, ".gitlab-ci.yml")
            or _exists(root, "Jenkinsfile") or _exists(root, ".circleci")):
        add("ci", "ci-config")
    if (_exists(root, "Makefile") or _exists(root, "justfile")
            or _exists(root, "CMakeLists.txt") or _exists(root, "meson.build")):
        add("build", "makefile-or-cmake")
    if _exists(root, "Gemfile"):
        add("ruby", "Gemfile")
    if _exists(root, "composer.json"):
        add("php", "composer.json")

    plat = sys.platform
    if plat.startswith("linux"):
        add("linux", "sys.platform", 1.0)
    elif plat == "darwin":
        add("macos", "sys.platform", 1.0)
    elif plat.startswith("win"):
        add("windows", "sys.platform", 1.0)

    if _exists(root, ".claude"):
        add("claude-code", ".claude/")

    ws = None
    for name in ("pnpm-workspace.yaml", "go.work", "lerna.json", "nx.json"):
        if _exists(root, name):
            ws = name
            add("workspace", name)
            break
    if ws is not None:
        try:
            kids = sorted(p for p in root.iterdir()
                          if p.is_dir() and not p.name.startswith("."))
        except OSError:
            kids = []
        for child in kids[:32]:
            if _exists(child, "package.json") and not any(x["tag"] == "node" for x in found):
                add("node", str(child.name) + "/package.json")
            if _exists(child, "go.mod") and not any(x["tag"] == "go" for x in found):
                add("go", str(child.name) + "/go.mod")
            if list(child.glob("*.py")) and not any(x["tag"] == "python" for x in found):
                add("python", str(child.name) + "/python")

    ov = overrides or {}
    extra = ov.get("add") or ov.get("include") or []
    for tag in extra:
        if not any(x["tag"] == tag for x in found):
            add(str(tag), "user-override", 1.0)
    drop = set(ov.get("remove") or ov.get("exclude") or [])
    if drop:
        found = [x for x in found if x["tag"] not in drop]
    if cache_dir is not None and project_id:
        import json
        cp = Path(cache_dir) / "capability-cache.json"
        try:
            cached = json.loads(cp.read_text(encoding="utf-8")) if cp.is_file() else {}
        except (OSError, ValueError, TypeError):
            cached = {}
        if not isinstance(cached, dict):
            cached = {}
        cached[project_id] = {"sig": sig, "rows": found}
        try:
            cp.parent.mkdir(parents=True, exist_ok=True)
            cp.write_text(json.dumps(cached) + "\n", encoding="utf-8")
            os.chmod(str(cp), 0o600)
        except OSError:
            pass
    return found


def capability_tags(rows: list) -> set:
    return {r["tag"] for r in rows}


def applies_match(applies: dict, caps: set) -> bool:
    """applies.any / applies.all / applies.exclude against detected tags."""
    if not applies:
        return True
    exclude = set(applies.get("exclude") or [])
    if exclude and (exclude & caps):
        return False
    all_ = set(applies.get("all") or [])
    if all_ and not all_.issubset(caps):
        return False
    any_ = set(applies.get("any") or [])
    if any_ and not (any_ & caps):
        return False
    return True


def parse_applies(fm: dict) -> dict:
    """Single production applies parser: fact_schema.applies_from_fm + legacy stacks."""
    from fact_schema import applies_from_fm
    got = applies_from_fm(fm)
    if got.get("error"):
        return got
    if got.get("any") or got.get("all") or got.get("exclude"):
        return got
    stacks = fm.get("stacks") or ""
    if isinstance(stacks, str):
        tags = re_tokens(stacks)
    elif isinstance(stacks, (list, tuple)):
        tags = [str(x).lower() for x in stacks]
    else:
        tags = []
    if tags:
        return {"any": tags, "all": [], "exclude": []}
    return {"any": [], "all": [], "exclude": []}


def re_tokens(s: str) -> list:
    import re
    return re.findall(r"[a-z0-9-]+", (s or "").lower())
