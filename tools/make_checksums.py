#!/usr/bin/env python3
"""Stdlib SHA256SUMS generator for the release subjects (#152, v0.4.5 release governance).

Walk each subject dir, hash every file, and emit a sha256sum-format manifest
(`<hex>  <path>`, two spaces — the text-mode convention `sha256sum -c` parses).
Paths are written repo-root-relative so the manifest verifies from the repo root,
matching the workflow's CWD. The walk mirrors tools/make_sbom.py: sorted,
symlinks and non-files skipped — the two manifests describe the same file set.
Zero runtime dependencies by design (the project's own rule) — stdlib only.

Usage: python3 tools/make_checksums.py [--out SHA256SUMS] DIR [DIR ...]
"""
from __future__ import annotations

import argparse
import hashlib
import os
import sys
from pathlib import Path


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description="stdlib SHA256SUMS for the release subjects")
    ap.add_argument("dirs", nargs="+", help="subject directories to walk")
    ap.add_argument("--out", default="SHA256SUMS")
    a = ap.parse_args()

    root = Path.cwd()
    lines: list[str] = []
    seen: set[str] = set()
    for d in a.dirs:
        subj = Path(d)
        if not subj.is_dir():
            print(f"make_checksums: not a directory: {subj}", file=sys.stderr)
            return 2
        for p in sorted(subj.rglob("*")):
            if p.is_symlink() or not p.is_file():
                continue
            # review fixes: POSIX separators (sha256sum -c reads `\` literally), no
            # out-of-tree subjects (a `..`-relative manifest can never self-verify from
            # the repo root), and no duplicate lines for overlapping dir args
            rel = os.path.relpath(p, root).replace(os.sep, "/")
            if rel.startswith("../"):
                print(f"make_checksums: subject outside the repo root: {subj}", file=sys.stderr)
                return 2
            if rel in seen:
                continue
            seen.add(rel)
            lines.append(f"{_sha256(p)}  {rel}")

    out = Path(a.out)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"make_checksums: {len(lines)} file(s) -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
