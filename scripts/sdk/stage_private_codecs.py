#!/usr/bin/env python3
"""Build (when an SDK root is set) and stage playback runtimes into the app tree.

Private directories (app-only):

  macOS   Contents/Frameworks/braw     compatible with Blackmagic RAW
          Contents/MacOS/r3d           supports R3D files
  other   <stage>/lib/private/braw
          <stage>/lib/private/r3d

Only the bridge shared library and unmodified vendor dynamic libraries are
copied. Missing SDKs are skipped.
"""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

from runtime_only import assert_runtime_only, copy_runtime_tree, is_dynamic_library, safe_print

ROOT = Path(__file__).resolve().parents[2]
SDK_DIR = Path(__file__).resolve().parent


def _bridge_name(stem: str) -> str:
    system = platform.system()
    if system == "Darwin":
        return f"lib{stem}.dylib"
    if system == "Windows":
        return f"lib{stem}.dll"
    return f"lib{stem}.so"


def _ensure_bridge(kind: str, out_dir: Path) -> Path | None:
    bridge = out_dir / _bridge_name(f"{kind}_bridge")
    if bridge.is_file():
        return bridge
    env_key = "BRAW_SDK_ROOT" if kind == "braw" else "R3D_SDK_ROOT"
    if not os.environ.get(env_key, "").strip():
        safe_print(f"skip: {env_key} unset", file=sys.stderr)
        return None
    script = SDK_DIR / f"build_{kind}_bridge.py"
    safe_print(f"Building {kind} playback bridge", file=sys.stderr)
    subprocess.check_call([sys.executable, str(script), "--out", str(out_dir)])
    if not bridge.is_file():
        raise SystemExit(f"Bridge build did not produce {bridge.name}")
    return bridge


def _install_one(kind: str, bridge: Path, dest: Path) -> None:
    redist = bridge.parent / "redistributable"
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    shutil.copy2(bridge, dest / bridge.name)
    if redist.is_dir():
        staging = dest / "_runtime"
        copy_runtime_tree(redist, staging)
        for item in staging.rglob("*"):
            if item.is_file() and is_dynamic_library(item):
                shutil.copy2(item, dest / item.name, follow_symlinks=False)
            elif item.is_dir() and item.suffix == ".framework":
                target = dest / item.name
                if target.exists():
                    shutil.rmtree(target)
                shutil.copytree(item, target, symlinks=True)
        shutil.rmtree(staging)
    assert_runtime_only(dest)
    if not (dest / bridge.name).is_file():
        raise SystemExit(f"private directory is missing {bridge.name}")
    safe_print(f"Staged {kind} runtime -> {dest}", file=sys.stderr)


def _destinations(stage_root: Path) -> dict[str, Path]:
    macos = (stage_root / "MacOS").is_dir() and (stage_root / "Frameworks").is_dir()
    if macos or (stage_root.name == "Contents" and (stage_root / "MacOS").is_dir()):
        return {
            "braw": stage_root / "Frameworks" / "braw",
            "r3d": stage_root / "MacOS" / "r3d",
        }
    return {
        "braw": stage_root / "lib" / "private" / "braw",
        "r3d": stage_root / "lib" / "private" / "r3d",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage-root", type=Path, required=True)
    parser.add_argument("--build-root", type=Path, default=ROOT / "build")
    args = parser.parse_args()
    stage_root = args.stage_root.expanduser().resolve()
    if not stage_root.is_dir():
        raise SystemExit(f"stage root does not exist: {stage_root}")
    destinations = _destinations(stage_root)
    build_root = args.build_root.expanduser().resolve()
    for kind in ("braw", "r3d"):
        bridge = _ensure_bridge(kind, build_root / kind)
        if bridge is None:
            continue
        _install_one(kind, bridge, destinations[kind])


if __name__ == "__main__":
    main()
