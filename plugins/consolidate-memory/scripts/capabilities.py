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


def detect_capabilities(project_dir: Path, *, overrides: Optional[dict] = None,
                        observation_time: Optional[str] = None) -> list:
    """Return a list of {tag, evidence, confidence, detector_version, observed_at}."""
    root = Path(project_dir)
    observed = observation_time or _now()
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

    ov = overrides or {}
    extra = ov.get("add") or ov.get("include") or []
    for tag in extra:
        if not any(x["tag"] == tag for x in found):
            add(str(tag), "user-override", 1.0)
    drop = set(ov.get("remove") or ov.get("exclude") or [])
    if drop:
        found = [x for x in found if x["tag"] not in drop]
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
    """Read applies from frontmatter (any/all/exclude lists or a legacy stacks: field)."""
    raw = fm.get("applies")
    if isinstance(raw, dict):
        return {
            "any": list(raw.get("any") or []),
            "all": list(raw.get("all") or []),
            "exclude": list(raw.get("exclude") or []),
        }
    # legacy stacks: [python, gpu] ≡ applies.any
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
