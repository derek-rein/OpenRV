#!/usr/bin/env python3
"""Build the optional R3D SDK C ABI bridge shared library.

Requires a local copy of the official RED R3D SDK (headers + static lib +
Redistributable dynamic libraries). The SDK is proprietary — do not commit it.

Usage:
  R3D_SDK_ROOT=/path/to/sdk python3 scripts/sdk/build_r3d_bridge.py

Outputs:
  build/r3d/libr3d_bridge.{dylib,so,dll}
  build/r3d/redistributable/   (vendor dynamic libraries only)

See docs/build_system/release_codecs_and_signing.md.
"""

from __future__ import annotations

import argparse
import os
import platform
import subprocess
import sys
from pathlib import Path

from runtime_only import assert_runtime_only, copy_runtime_tree, safe_print

ROOT = Path(__file__).resolve().parents[2]
_BRIDGE = ROOT / "src" / "lib" / "image" / "vendor_bridge" / "r3d"
SRC = _BRIDGE / "r3d_bridge.cpp"
METAL_SRC = _BRIDGE / "r3d_bridge_metal.mm"
DECODER_SRC = _BRIDGE / "r3d_bridge_decoder.cpp"
HDR_DIR = _BRIDGE
OUT_DIR = ROOT / "build" / "r3d"


def _find_sdk(explicit: str | None) -> Path:
    candidates: list[Path] = []
    if explicit:
        candidates.append(Path(explicit).expanduser().resolve())
    env = os.environ.get("R3D_SDK_ROOT", "").strip()
    if env:
        candidates.append(Path(env).expanduser().resolve())
    # Private stash (recommended local layout) + CI fetch cache.
    candidates.append((Path.home() / "code" / "r3d-sdk-private" / "R3DSDKv9_2_1").resolve())
    candidates.append((ROOT / ".r3d-sdk" / "R3DSDKv9_2_1").resolve())
    candidates.append((ROOT / ".r3d-sdk").resolve())
    # Common local drop locations (gitignored — never commit the SDK).
    for name in ("R3DSDKv9_2_1", "R3DSDK", "r3d_sdk"):
        candidates.append((ROOT / name).resolve())
        candidates.append((Path.home() / "sdk" / name).resolve())
        candidates.append((Path.home() / "code" / "r3d-sdk-private" / name).resolve())

    for c in candidates:
        if (c / "Include" / "R3DSDK.h").is_file():
            return c
    raise SystemExit(
        "R3D SDK not found. Set R3D_SDK_ROOT, or place the SDK at "
        "~/code/r3d-sdk-private/R3DSDKv9_2_1, or run: "
        "python3 scripts/sdk/fetch_r3d_sdk.py."
    )


def _platform_bits() -> tuple[str, str, str, list[str]]:
    """Return (lib_subdir, redistrib_subdir, shared_ext, extra_link_args)."""
    system = platform.system()
    machine = platform.machine().lower()
    if system == "Darwin":
        # Universal static lib covers arm64 + x86_64.
        return (
            "mac64",
            "mac",
            "dylib",
            [
                "-framework",
                "Foundation",
                "-framework",
                "CoreFoundation",
                "-framework",
                "IOKit",
                "-framework",
                "Metal",
                "-framework",
                "AppKit",
                "-lc++",
            ],
        )
    if system == "Linux":
        return "linux64", "linux", "so", ["-ldl", "-lpthread", "-luuid", "-lstdc++"]
    if system == "Windows":
        # Prefer VS2017 MD release static lib (compatible with VS2019+).
        return "win64", "win", "dll", []
    raise SystemExit(f"Unsupported platform: {system} {machine}")


def _static_lib(sdk: Path, lib_subdir: str) -> Path:
    system = platform.system()
    if system == "Darwin":
        p = sdk / "Lib" / lib_subdir / "libR3DSDK-libcpp.a"
        if p.is_file():
            return p
    elif system == "Linux":
        for name in ("libR3DSDKPIC-cpp11.a", "libR3DSDK-cpp11.a", "libR3DSDKPIC.a", "libR3DSDK.a"):
            p = sdk / "Lib" / lib_subdir / name
            if p.is_file():
                return p
    else:
        # Windows: pick 2017 MD release.
        for name in (
            "R3DSDK-2017MD.lib",
            "R3DSDK-2015MD.lib",
            "R3DSDK-2013MD.lib",
        ):
            p = sdk / "Lib" / lib_subdir / name
            if p.is_file():
                return p
    raise SystemExit(f"No suitable static library under {sdk / 'Lib' / lib_subdir}")


def build(sdk: Path, out_dir: Path, verbose: bool) -> Path:
    lib_subdir, redistrib_subdir, ext, extra = _platform_bits()
    static = _static_lib(sdk, lib_subdir)
    redistrib_src = sdk / "Redistributable" / redistrib_subdir
    if not redistrib_src.is_dir():
        raise SystemExit(f"Missing Redistributable folder: {redistrib_src}")

    out_dir.mkdir(parents=True, exist_ok=True)
    out_lib = out_dir / f"libr3d_bridge.{ext}"

    include = sdk / "Include"
    if not SRC.is_file():
        raise SystemExit(f"Missing bridge source: {SRC}")

    system = platform.system()
    if system == "Windows":
        # Expect cl.exe on PATH (Developer Command Prompt / msvc-dev-cmd).
        # Must match the RED static lib CRT: R3DSDK-*-MD.lib → /MD (DLL runtime).
        # Without explicit /MD, some CI images default to /MT and LNK2038.
        # Prefer /Fo + /Fe into out_dir so intermediates stay out of the source tree.
        if not DECODER_SRC.is_file():
            raise SystemExit(f"Missing decoder bridge source: {DECODER_SRC}")
        win_common = [
            "cl.exe",
            "/nologo",
            "/O2",
            "/MD",
            "/EHsc",
            "/std:c++17",
            f"/I{include}",
            f"/I{HDR_DIR}",
            "/DR3D_BRIDGE_EXPORTS",
            "/c",
        ]
        objs: list[Path] = []
        for src in (SRC, DECODER_SRC):
            obj = out_dir / f"{src.stem}.obj"
            cmd = [*win_common, str(src), f"/Fo{obj}"]
            if verbose:
                print(" ".join(cmd), file=sys.stderr)
            subprocess.check_call(cmd)
            objs.append(obj)
        cmd = [
            "cl.exe",
            "/nologo",
            "/LD",
            "/MD",
            *[str(o) for o in objs],
            str(static),
            f"/Fe{out_lib}",
        ]
        if verbose:
            print(" ".join(cmd), file=sys.stderr)
        subprocess.check_call(cmd)
    else:
        cxx = os.environ.get("CXX", "c++")
        common = [
            "-std=c++17",
            "-O2",
            "-fPIC",
            f"-I{include}",
            f"-I{HDR_DIR}",
            "-DR3D_BRIDGE_EXPORTS",
        ]
        obj = out_dir / "r3d_bridge.o"
        compile_cpp = [cxx, *common, "-c", str(SRC), "-o", str(obj)]
        if verbose:
            print(" ".join(compile_cpp), file=sys.stderr)
        subprocess.check_call(compile_cpp)
        link_inputs = [str(obj)]
        if system == "Darwin":
            if not METAL_SRC.is_file():
                raise SystemExit(f"Missing Metal bridge source: {METAL_SRC}")
            metal_obj = out_dir / "r3d_bridge_metal.o"
            compile_mm = [
                cxx,
                *common,
                "-fobjc-arc",
                "-x",
                "objective-c++",
                "-c",
                str(METAL_SRC),
                "-o",
                str(metal_obj),
            ]
            if verbose:
                print(" ".join(compile_mm), file=sys.stderr)
            subprocess.check_call(compile_mm)
            link_inputs.append(str(metal_obj))
        else:
            if not DECODER_SRC.is_file():
                raise SystemExit(f"Missing decoder bridge source: {DECODER_SRC}")
            decoder_obj = out_dir / "r3d_bridge_decoder.o"
            compile_dec = [cxx, *common, "-c", str(DECODER_SRC), "-o", str(decoder_obj)]
            if verbose:
                print(" ".join(compile_dec), file=sys.stderr)
            subprocess.check_call(compile_dec)
            link_inputs.append(str(decoder_obj))
        cmd = [
            cxx,
            "-shared",
            *link_inputs,
            str(static),
            "-o",
            str(out_lib),
            *extra,
        ]
        if system == "Darwin":
            # Allow loading RED dylibs from same folder as the bridge at runtime.
            cmd.extend(
                [
                    "-Wl,-rpath,@loader_path",
                    "-Wl,-rpath,@loader_path/redistributable",
                ]
            )
        elif system == "Linux":
            cmd.extend(["-Wl,-rpath,$ORIGIN", "-Wl,-rpath,$ORIGIN/redistributable"])
        if verbose:
            print(" ".join(cmd), file=sys.stderr)
        subprocess.check_call(cmd)

    dest_redist = out_dir / "redistributable"
    copy_runtime_tree(redistrib_src, dest_redist)
    assert_runtime_only(dest_redist)

    safe_print(f"Built {out_lib.name}")
    safe_print("Runtime libraries staged")
    return out_lib


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--sdk",
        default=None,
        help="Path to unpacked R3D SDK root (or set R3D_SDK_ROOT)",
    )
    ap.add_argument(
        "--out",
        type=Path,
        default=OUT_DIR,
        help=f"Output directory (default: {OUT_DIR})",
    )
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()
    sdk = _find_sdk(args.sdk)
    build(sdk, args.out.resolve(), args.verbose)


if __name__ == "__main__":
    main()
