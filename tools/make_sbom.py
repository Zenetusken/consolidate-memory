#!/usr/bin/env python3
"""Stdlib SPDX 2.3 SBOM generator for the plugin trees (R5, v0.4.2 release teeth).

Walk each subject dir, hash every file, and emit an SPDX tag-value-free JSON
document the release workflow uploads beside the SLSA provenance. Zero runtime
dependencies by design (the project's own rule) — stdlib only.

Usage: python3 tools/make_sbom.py --version X.Y.Z [--out sbom.spdx.json] DIR [DIR ...]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

SPDX_VERSION = "SPDX-2.3"
DATA_LICENSE = "CC0-1.0"
SPDXID = "SPDXRef-DOCUMENT"
DOC_NAMESPACE_BASE = "https://github.com/Zenetusken/consolidate-memory"


def _sha1(path: Path) -> str:
    h = hashlib.sha1()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description="stdlib SPDX SBOM for the plugin trees")
    ap.add_argument("dirs", nargs="+", help="subject directories to walk")
    ap.add_argument("--version", required=True, help="the release version (plugin.json version)")
    ap.add_argument("--out", default="sbom.spdx.json")
    ap.add_argument("--license", default="MIT", help="declared license for every package")
    a = ap.parse_args()

    packages = []
    files = []
    for d in a.dirs:
        root = Path(d).resolve()
        if not root.is_dir():
            print(f"make_sbom: not a directory: {root}", file=sys.stderr)
            return 2
        spdxid = "SPDXRef-Package-" + _spdx_id(root.name)
        files_this = []
        for p in sorted(root.rglob("*")):
            if p.is_symlink() or not p.is_file():
                continue
            try:
                rel = p.relative_to(root).as_posix()
            except ValueError:
                continue
            fname = "SPDXRef-File-" + _spdx_id(rel)
            files_this.append(fname)
            files.append({
                "fileName": f"./{rel}",
                "SPDXID": fname,
                "checksums": [
                    {"algorithm": "SHA1", "checksumValue": _sha1(p)},
                    {"algorithm": "SHA256", "checksumValue": _sha256(p)},
                ],
                "licenseConcluded": a.license,
                "copyrightText": "NOASSERTION",
            })
        packages.append({
            "name": root.name,
            "SPDXID": spdxid,
            "versionInfo": a.version,
            "downloadLocation": "NOASSERTION",
            "licenseConcluded": a.license,
            "licenseDeclared": a.license,
            "copyrightText": "NOASSERTION",
            "filesAnalyzed": True,
            "hasFiles": files_this,
        })
    doc = {
        "spdxVersion": SPDX_VERSION,
        "dataLicense": DATA_LICENSE,
        "SPDXID": SPDXID,
        "name": "consolidate-memory plugins",
        "documentNamespace": f"{DOC_NAMESPACE_BASE}/sbom/{a.version}",
        "creationInfo": {
            "created": "NOASSERTION",
            "creators": ["Tool: tools/make_sbom.py"],
        },
        "packages": packages,
        "files": files,
        "relationships": [
            {"spdxElementId": SPDXID, "relatedSpdxElement": p["SPDXID"],
             "relationshipType": "DESCRIBES"}
            for p in packages
        ],
    }
    out = Path(a.out)
    out.write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8")
    print(f"sbom → {out} ({len(files)} files, {len(packages)} packages)")
    return 0


def _spdx_id(s: str) -> str:
    """SPDX reference ids: alnum, '.', '-' only (no ':' or '/' from paths)."""
    out = []
    for ch in s:
        if ch.isalnum() or ch in ".-":
            out.append(ch)
        else:
            out.append("-")
    return "".join(out) or "pkg"


if __name__ == "__main__":
    sys.exit(main())
