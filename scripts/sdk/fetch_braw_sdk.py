#!/usr/bin/env python3
"""Download the private camera-RAW SDK used for optional playback.

Release: derek-rein/braw-sdk-private tag sdk-6.0
Asset:   BlackmagicRAWSDK-6.0-full.tar.gz

Auth: BRAW_SDK_READ_TOKEN, then `gh auth token` unless --token-env-only.
With --optional and no token, prints SKIP and exits 0.

The last stdout line is the unpacked SDK root, or SKIP. Progress goes to stderr.
Archive member names are not logged.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import tempfile
from pathlib import Path

from github_release import download_asset, safe_extract, token_from

DEFAULT_REPO = "derek-rein/braw-sdk-private"
DEFAULT_TAG = "sdk-6.0"
DEFAULT_ASSET = "BlackmagicRAWSDK-6.0-full.tar.gz"
ROOT = Path(__file__).resolve().parents[2]


def _header_ok(path: Path) -> bool:
    markers = (
        path / "Linux" / "Include" / "BlackmagicRawAPI.h",
        path / "Mac" / "Include" / "BlackmagicRawAPI.h",
        path / "Win" / "Include" / "BlackmagicRawAPI.h",
        path / "Win" / "Include" / "BlackmagicRawAPI.idl",
        path / "Include" / "BlackmagicRawAPI.h",
        path / "Include" / "BlackmagicRawAPI.idl",
    )
    return any(marker.is_file() for marker in markers)


def _find_root(extract_dir: Path) -> Path:
    if _header_ok(extract_dir):
        return extract_dir
    if extract_dir.is_dir():
        for child in sorted(extract_dir.iterdir()):
            if child.is_dir() and _header_ok(child):
                return child
    raise SystemExit("Unpacked SDK is missing the expected API header")


def _existing(cache: Path) -> Path | None:
    if not cache.is_dir():
        return None
    if _header_ok(cache):
        return cache
    for child in sorted(cache.iterdir()):
        if child.is_dir() and _header_ok(child):
            return child
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=os.environ.get("BRAW_SDK_GITHUB_REPO", DEFAULT_REPO))
    parser.add_argument("--tag", default=os.environ.get("BRAW_SDK_RELEASE_TAG", DEFAULT_TAG))
    parser.add_argument("--asset", default=os.environ.get("BRAW_SDK_ASSET", DEFAULT_ASSET))
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--optional", action="store_true", help="Exit 0 with SKIP when no token is available")
    parser.add_argument("--token-env-only", action="store_true", help="Do not fall back to gh auth token")
    args = parser.parse_args()

    cache = args.out
    if cache is None:
        env_cache = os.environ.get("BRAW_SDK_CACHE", "").strip()
        cache = Path(env_cache) if env_cache else (ROOT / ".braw-sdk")
    cache = cache.expanduser().resolve()

    existing = _existing(cache)
    if existing is not None and not args.force:
        print(f"Using cached SDK at {existing}", file=sys.stderr)
        print(existing)
        return

    auth = token_from(("BRAW_SDK_READ_TOKEN",), allow_gh=not args.token_env_only)
    if not auth:
        if args.optional:
            print("BRAW_SDK_READ_TOKEN not set; skipping camera RAW playback", file=sys.stderr)
            print("SKIP")
            return
        raise SystemExit("No token. Set BRAW_SDK_READ_TOKEN, or run gh auth login.")

    cache.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="braw-sdk-") as tmp:
        tarball = Path(tmp) / args.asset
        print(f"Downloading {args.repo}@{args.tag}", file=sys.stderr)
        download_asset(args.repo, args.tag, args.asset, tarball, auth, "openrv-fetch-braw-sdk")
        print("Extracting SDK cache", file=sys.stderr)
        for child in list(cache.iterdir()):
            if child.name.startswith("BlackmagicRAW") or child.name in {"Linux", "Mac", "Win", "Include", "Libraries"}:
                if child.is_dir():
                    shutil.rmtree(child)
                else:
                    child.unlink()
        safe_extract(tarball, cache)

    sdk_root = _find_root(cache)
    print("SDK cache ready", file=sys.stderr)
    print(sdk_root)


if __name__ == "__main__":
    main()
