"""Download one private GitHub Release asset. Does not print archive contents."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tarfile
import urllib.error
import urllib.request
from pathlib import Path


def token_from(env_keys: tuple[str, ...], allow_gh: bool) -> str:
    for key in env_keys:
        value = os.environ.get(key, "").strip()
        if value:
            return value
    if not allow_gh:
        return ""
    try:
        out = subprocess.check_output(["gh", "auth", "token"], text=True, stderr=subprocess.DEVNULL)
    except (OSError, subprocess.CalledProcessError):
        return ""
    return out.strip()


def download_asset(repo: str, tag: str, asset: str, dest: Path, token: str, user_agent: str) -> None:
    api = f"https://api.github.com/repos/{repo}/releases/tags/{tag}"
    request = urllib.request.Request(
        api,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": user_agent,
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            data = json.load(response)
    except urllib.error.HTTPError as exc:
        raise SystemExit(f"Failed to fetch release {repo}@{tag}: HTTP {exc.code}") from exc

    asset_id = None
    for item in data.get("assets") or []:
        if item.get("name") == asset:
            asset_id = item.get("id")
            break
    if not asset_id:
        raise SystemExit(f"Release asset {asset} is not on {repo}@{tag}")

    asset_url = f"https://api.github.com/repos/{repo}/releases/assets/{asset_id}"
    asset_request = urllib.request.Request(
        asset_url,
        headers={
            "Accept": "application/octet-stream",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": user_agent,
        },
    )
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        with urllib.request.urlopen(asset_request, timeout=600) as response, dest.open("wb") as handle:
            shutil.copyfileobj(response, handle)
    except urllib.error.HTTPError as exc:
        raise SystemExit(f"Failed to download release asset: HTTP {exc.code}") from exc


def safe_extract(archive: Path, dest: Path) -> None:
    """Extract a tarball without logging member names. Refuse paths that escape dest."""
    root = dest.resolve()
    with tarfile.open(archive, "r:gz") as handle:
        for member in handle.getmembers():
            if member.issym() or member.islnk():
                raise SystemExit("Refusing archive entry that is a link")
            target = (root / member.name).resolve()
            if target != root and root not in target.parents:
                raise SystemExit("Refusing archive entry that escapes the cache directory")
        handle.extractall(root)
