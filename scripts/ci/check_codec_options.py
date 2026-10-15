#!/usr/bin/env python3
"""Check the release codec preset covers every FFmpeg switch OpenRV knows about.

Parses the disable lists in cmake/dependencies/ffmpeg.cmake and the application
gates in src/lib/image/mio_ffmpeg/init.cpp, then requires each name to appear in
cmake/defaults/rv_codec_options.cmake.

Encoders that OpenRV would otherwise disable must be in the release preset.
GPL libraries stay forbidden. BSD libvpx and libaom must be enabled.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FFMPEG = ROOT / "cmake" / "dependencies" / "ffmpeg.cmake"
OPTIONS = ROOT / "cmake" / "defaults" / "rv_codec_options.cmake"
INIT = ROOT / "src" / "lib" / "image" / "mio_ffmpeg" / "init.cpp"
OIIO = ROOT / "cmake" / "dependencies" / "oiio.cmake"
DEPS = ROOT / "cmake" / "dependencies" / "CMakeLists.txt"
BSD = ROOT / "cmake" / "dependencies" / "bsd_media_codecs.cmake"
HW = ROOT / "cmake" / "dependencies" / "hw_encode_headers.cmake"
FORBIDDEN_FLAGS = (
    "--enable-gpl",
    "--enable-nonfree",
    "--enable-libx264",
    "--enable-libx265",
)


def quoted_block(text: str, start_marker: str) -> list[str]:
    start = text.find(start_marker)
    if start < 0:
        raise SystemExit(f"missing {start_marker}")
    paren = text.find("(", start)
    depth = 0
    end = paren
    for index, char in enumerate(text[paren:], paren):
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                end = index
                break
    body = text[paren : end + 1]
    return re.findall(r'"([^"]+)"', body)


def preset_names(text: str, variable: str) -> set[str]:
    return set(quoted_block(text, f"SET({variable}"))


def active_lines(text: str) -> list[str]:
    lines = []
    for line in text.splitlines():
        code = line.split("#", 1)[0]
        if "MATCHES" in code or "FATAL_ERROR" in code:
            continue
        lines.append(code)
    return lines


def require_absent(path: Path, flags: tuple[str, ...]) -> None:
    for line in active_lines(path.read_text(encoding="utf-8")):
        for flag in flags:
            if flag in line:
                raise SystemExit(f"{path.name} still contains {flag}")


def main() -> None:
    ffmpeg = FFMPEG.read_text(encoding="utf-8")
    options = OPTIONS.read_text(encoding="utf-8")
    init = INIT.read_text(encoding="utf-8")
    oiio = OIIO.read_text(encoding="utf-8")
    deps = DEPS.read_text(encoding="utf-8")

    decoders = set(quoted_block(ffmpeg, "SET(NON_FREE_DECODERS_TO_DISABLE"))
    decoders.update(re.findall(r'LIST\(APPEND NON_FREE_DECODERS_TO_DISABLE "([^"]+)"\)', ffmpeg))
    encoders = set(quoted_block(ffmpeg, "SET(NON_FREE_ENCODERS_TO_DISABLE"))
    app_decoders = set(re.findall(r"__FFMPEG_ENABLE_NON_FREE_DECODER_([A-Za-z0-9_]+)", init))

    enabled_decoders = preset_names(options, "_RV_ALL_NONFREE_DECODERS")
    enabled_encoders = {name for name in preset_names(options, "_RV_ALL_NONFREE_ENCODERS") if name}

    missing_decoders = sorted((decoders | app_decoders) - enabled_decoders)
    missing_encoders = sorted(encoders - enabled_encoders)
    if missing_decoders or missing_encoders:
        print("codec preset is wrong:", file=sys.stderr)
        for name in missing_decoders:
            print(f"  decoder {name}", file=sys.stderr)
        for name in missing_encoders:
            print(f"  encoder {name}", file=sys.stderr)
        sys.exit(1)

    gpl_cmake = ROOT / "cmake" / "dependencies" / "gpl_media_codecs.cmake"
    if gpl_cmake.exists():
        raise SystemExit("gpl_media_codecs.cmake must not exist")
    if not BSD.is_file():
        raise SystemExit("bsd_media_codecs.cmake is required")
    if not HW.is_file():
        raise SystemExit("hw_encode_headers.cmake is required")

    bsd_active = "\n".join(active_lines(BSD.read_text(encoding="utf-8")))
    for flag in ("--enable-libvpx", "--enable-libaom"):
        if flag not in bsd_active:
            raise SystemExit(f"bsd_media_codecs.cmake must pass {flag}")
    require_absent(BSD, FORBIDDEN_FLAGS)
    require_absent(FFMPEG, FORBIDDEN_FLAGS)
    require_absent(OPTIONS, FORBIDDEN_FLAGS)
    require_absent(HW, FORBIDDEN_FLAGS)

    ffmpeg_active = "\n".join(active_lines(ffmpeg))
    if "--disable-filter=geq" not in ffmpeg_active:
        raise SystemExit("ffmpeg.cmake must disable the GPL geq filter")
    if "--disable-encoders" in ffmpeg_active:
        raise SystemExit("ffmpeg.cmake must not disable every encoder")
    if "RV_FFMPEG_DISABLE_ENCODERS" in options:
        raise SystemExit("release preset must not force encoders off")
    if "IF(NOT RV_ENABLE_ALL_CODECS OR NOT RV_TARGET_LINUX)" not in ffmpeg:
        raise SystemExit("Linux release builds must leave VAAPI to autodetect")
    if "--enable-libvpl" not in ffmpeg_active or "--enable-libmfx" not in ffmpeg_active:
        raise SystemExit("QSV must be enabled when libvpl or libmfx is present")
    if "--enable-videotoolbox" not in ffmpeg_active:
        raise SystemExit("VideoToolbox must stay available on Apple")

    hw_text = HW.read_text(encoding="utf-8")
    if "ffnvcodec" not in hw_text or "AMF/core/Version.h" not in hw_text:
        raise SystemExit("hardware encoder headers must cover NVENC and AMF")

    bsd_at = deps.find("INCLUDE(bsd_media_codecs)")
    hw_at = deps.find("INCLUDE(hw_encode_headers)")
    ffmpeg_at = deps.find("INCLUDE(ffmpeg)")
    if not (0 <= bsd_at < hw_at < ffmpeg_at):
        raise SystemExit("BSD and hardware headers must be included before FFmpeg")

    if "RV_ENABLE_ALL_CODECS" not in oiio or "USE_OPENEXR=ON" not in oiio:
        raise SystemExit("oiio.cmake does not force format plugins on for RV_ENABLE_ALL_CODECS")
    if "USE_GIF=OFF" not in oiio:
        raise SystemExit("GIF must stay off until giflib is vendored")

    print(f"decoders {len(enabled_decoders)} encoders {len(enabled_encoders)}")
    print("codec preset keeps decoders, BSD and native encoders, and refuses GPL / nonfree")


if __name__ == "__main__":
    main()
