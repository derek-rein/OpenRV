#!/usr/bin/env bash
# Fetch optional playback SDKs and compile their bridges.
# Missing tokens print SKIP and exit 0. Download failures exit non-zero.
# Does not print SDK archive contents.
set -euo pipefail

if command -v python3 >/dev/null 2>&1; then
  PY=python3
else
  PY=python
fi

braw="$("$PY" scripts/sdk/fetch_braw_sdk.py --optional --out "${RUNNER_TEMP}/braw-sdk")"
r3d="$("$PY" scripts/sdk/fetch_r3d_sdk.py --optional --out "${RUNNER_TEMP}/r3d-sdk")"

if [ "$braw" != "SKIP" ]; then
  if [ -n "${GITHUB_ENV:-}" ]; then
    echo "BRAW_SDK_ROOT=${braw}" >> "$GITHUB_ENV"
  fi
  BRAW_SDK_ROOT="$braw" "$PY" scripts/sdk/build_braw_bridge.py
fi

if [ "$r3d" != "SKIP" ]; then
  if [ -n "${GITHUB_ENV:-}" ]; then
    echo "R3D_SDK_ROOT=${r3d}" >> "$GITHUB_ENV"
  fi
  R3D_SDK_ROOT="$r3d" "$PY" scripts/sdk/build_r3d_bridge.py
fi
