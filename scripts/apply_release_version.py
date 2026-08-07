#!/usr/bin/env python3
"""Patch CMakeLists.txt point version from a semver string (X.Y.Z).

Used by the multi-platform release workflow so binaries report the tag version
without committing a CMakeLists bump on every ship.

Usage:
  python scripts/apply_release_version.py 4.0.2
  python scripts/apply_release_version.py --from-tag v4.0.2
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CMAKE = REPO_ROOT / "CMakeLists.txt"

KEYS = (
    "RV_MAJOR_VERSION",
    "RV_MINOR_VERSION",
    "RV_REVISION_NUMBER",
)


def parse_version(s: str) -> tuple[str, str, str]:
    raw = s.strip()
    if raw.startswith("v"):
        raw = raw[1:]
    parts = raw.split(".")
    if len(parts) != 3 or not all(p.isdigit() for p in parts):
        raise SystemExit(f"expected semver X.Y.Z or vX.Y.Z, got {s!r}")
    return parts[0], parts[1], parts[2]


def apply(version: str, dry_run: bool = False) -> None:
    major, minor, rev = parse_version(version)
    text = CMAKE.read_text(encoding="utf-8")
    for key, val in zip(KEYS, (major, minor, rev), strict=True):
        text, n = re.subn(
            rf'(SET\({key}\s+")[^"]*(")',
            rf"\g<1>{val}\2",
            text,
            count=1,
        )
        if n != 1:
            raise SystemExit(f"failed to set {key} in {CMAKE}")
    if dry_run:
        print(f"dry-run: would set {major}.{minor}.{rev}")
        return
    CMAKE.write_text(text, encoding="utf-8")
    print(f"Patched {CMAKE.name} → {major}.{minor}.{rev}")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "version",
        nargs="?",
        help="X.Y.Z or vX.Y.Z",
    )
    p.add_argument(
        "--from-tag",
        dest="from_tag",
        help="same as positional version (accepts v-prefix)",
    )
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    version = args.from_tag or args.version
    if not version:
        p.error("version or --from-tag required")
    if not CMAKE.is_file():
        raise SystemExit(f"missing {CMAKE}")
    apply(version, dry_run=args.dry_run)


if __name__ == "__main__":
    try:
        main()
    except BrokenPipeError:
        sys.exit(0)
