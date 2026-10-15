#!/usr/bin/env python3
"""Checks for the license-compatible codec preset and the private runtime copy rules."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SDK = Path(__file__).resolve().parent
sys.path.insert(0, str(SDK))

from runtime_only import assert_runtime_only, copy_runtime_tree  # noqa: E402
from stage_private_codecs import _install_one  # noqa: E402


def _fail(message: str) -> None:
    raise SystemExit(message)


def test_copy_rejects_non_runtimes() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "libraries"
        dest = Path(tmp) / "out"
        src.mkdir()
        (src / "libBlackmagicRawAPI.so").write_bytes(b"runtime")
        (src / "libBlackmagicRawAPI.a").write_bytes(b"static")
        (src / "BlackmagicRawAPI.h").write_bytes(b"header")
        (src / "notes.txt").write_text("docs", encoding="utf-8")
        samples = src / "Samples"
        samples.mkdir()
        (samples / "demo.cpp").write_text("int main(){return 0;}", encoding="utf-8")
        framework = src / "BlackmagicRawAPI.framework"
        (framework / "Headers").mkdir(parents=True)
        (framework / "Headers" / "BlackmagicRawAPI.h").write_text("header", encoding="utf-8")
        (framework / "BlackmagicRawAPI").write_bytes(b"framework-binary")
        copy_runtime_tree(src, dest)
        names = sorted(path.name for path in dest.rglob("*") if path.is_file() or path.suffix == ".framework")
        if "libBlackmagicRawAPI.so" not in names:
            _fail(f"dynamic library was not copied: {names}")
        if "BlackmagicRawAPI.framework" not in names:
            _fail(f"framework was not copied: {names}")
        leaked = [path.name for path in dest.rglob("*") if path.suffix.lower() in {".h", ".a", ".txt", ".cpp"}]
        if leaked:
            _fail(f"non-runtime files copied: {leaked}")
        header = dest / "BlackmagicRawAPI.framework" / "Headers"
        if header.exists():
            _fail("framework Headers directory was copied")
        assert_runtime_only(dest)


def test_stage_flattens_runtime_only() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        bridge = root / "libbraw_bridge.so"
        bridge.write_bytes(b"bridge")
        redist = root / "redistributable"
        redist.mkdir()
        (redist / "libBlackmagicRawAPI.so").write_bytes(b"runtime")
        (redist / "libBlackmagicRawAPI.a").write_bytes(b"static")
        (redist / "BlackmagicRawAPI.h").write_bytes(b"header")
        dest = root / "private" / "braw"
        _install_one("braw", bridge, dest)
        files = sorted(path.name for path in dest.iterdir())
        if files != ["libBlackmagicRawAPI.so", "libbraw_bridge.so"]:
            _fail(f"private directory contents: {files}")
        assert_runtime_only(dest)


def test_optional_fetch_skips_without_token() -> None:
    env = os.environ.copy()
    env.pop("BRAW_SDK_READ_TOKEN", None)
    env.pop("R3D_SDK_READ_TOKEN", None)
    with tempfile.TemporaryDirectory() as tmp:
        for script in ("fetch_braw_sdk.py", "fetch_r3d_sdk.py"):
            completed = subprocess.run(
                [sys.executable, str(SDK / script), "--optional", "--token-env-only", "--out", tmp],
                check=False,
                capture_output=True,
                text=True,
                env=env,
            )
            if completed.returncode != 0:
                _fail(f"{script} failed: {completed.stderr}")
            if completed.stdout.strip().splitlines()[-1] != "SKIP":
                _fail(f"{script} did not skip: {completed.stdout!r}")


def main() -> None:
    test_copy_rejects_non_runtimes()
    test_stage_flattens_runtime_only()
    test_optional_fetch_skips_without_token()
    codec = subprocess.run([sys.executable, str(ROOT / "scripts" / "ci" / "check_codec_options.py")], check=False)
    if codec.returncode != 0:
        _fail("check_codec_options.py failed")
    print("private codec checks passed")


if __name__ == "__main__":
    main()
