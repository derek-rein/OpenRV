#!/usr/bin/env python3
"""Check the release codec preset covers every FFmpeg switch OpenRV knows about.

Parses the disable lists in cmake/dependencies/ffmpeg.cmake and the application
gates in src/lib/image/mio_ffmpeg/init.cpp, then requires each name to appear in
cmake/defaults/rv_codec_options.cmake.
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
FORBIDDEN_FLAGS = (
    "--enable-gpl",
    "--enable-nonfree",
    "--enable-libx264",
    "--enable-libx265",
    "--enable-libvpx",
    "--enable-libaom",
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


def main() -> None:
    ffmpeg = FFMPEG.read_text(encoding="utf-8")
    options = OPTIONS.read_text(encoding="utf-8")
    init = INIT.read_text(encoding="utf-8")
    oiio = OIIO.read_text(encoding="utf-8")

    decoders = set(quoted_block(ffmpeg, "SET(NON_FREE_DECODERS_TO_DISABLE"))
    decoders.update(re.findall(r'LIST\(APPEND NON_FREE_DECODERS_TO_DISABLE "([^"]+)"\)', ffmpeg))
    app_decoders = set(re.findall(r"__FFMPEG_ENABLE_NON_FREE_DECODER_([A-Za-z0-9_]+)", init))

    enabled_decoders = preset_names(options, "_RV_ALL_NONFREE_DECODERS")
    enabled_encoders = {name for name in preset_names(options, "_RV_ALL_NONFREE_ENCODERS") if name}

    missing_decoders = sorted((decoders | app_decoders) - enabled_decoders)
    if missing_decoders or enabled_encoders:
        print("codec preset is wrong:", file=sys.stderr)
        for name in missing_decoders:
            print(f"  decoder {name}", file=sys.stderr)
        for name in sorted(enabled_encoders):
            print(f"  encoder still enabled {name}", file=sys.stderr)
        sys.exit(1)

    gpl_cmake = ROOT / "cmake" / "dependencies" / "gpl_media_codecs.cmake"
    if gpl_cmake.exists():
        raise SystemExit("gpl_media_codecs.cmake must not exist")

    for path in (FFMPEG, OPTIONS):
        for line in active_lines(path.read_text(encoding="utf-8")):
            for flag in FORBIDDEN_FLAGS:
                if flag in line:
                    raise SystemExit(f"{path.name} still contains {flag}")

    if "--disable-encoders" not in ffmpeg or "--disable-filter=geq" not in ffmpeg:
        raise SystemExit("ffmpeg.cmake must disable encoders and the GPL geq filter")
    if "RV_FFMPEG_DISABLE_ENCODERS" not in options:
        raise SystemExit("release preset must force encoders off")
    if "RV_ENABLE_ALL_CODECS" not in oiio or "USE_OPENEXR=ON" not in oiio:
        raise SystemExit("oiio.cmake does not force format plugins on for RV_ENABLE_ALL_CODECS")
    if "USE_GIF=OFF" not in oiio:
        raise SystemExit("GIF must stay off until giflib is vendored")

    print(f"decoders {len(enabled_decoders)} encoders 0")
    print("codec preset keeps every decoder and refuses GPL / nonfree / encoder libraries")


if __name__ == "__main__":
    main()
