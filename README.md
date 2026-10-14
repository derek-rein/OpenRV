# Open RV

---

[![Open RV](docs/images/OpenRV_icon.png)](https://github.com/AcademySoftwareFoundation/OpenRV.git)
---

![Supported Versions](https://img.shields.io/badge/python-3.11-blue)
[![Supported VFX Platform Versions](https://img.shields.io/badge/vfx%20platform-2025-lightgrey.svg)](http://www.vfxplatform.com/)
[![docs](https://readthedocs.org/projects/aswf-openrv/badge/?version=latest)](https://aswf-openrv.readthedocs.io/en/latest)
[![Latest release](https://img.shields.io/github/v/release/derek-rein/OpenRV?label=latest)](https://github.com/derek-rein/OpenRV/releases)

## Overview

Open RV is an image and sequence viewer for VFX and animation artists.
Open RV is high-performant, hardware accelerated, and pipeline-friendly.

[Open RV Documentation on Read the Docs](https://aswf-openrv.readthedocs.io/en/latest/)

## Downloads

Prebuilt **Release** packages from this fork ([derek-rein/OpenRV](https://github.com/derek-rein/OpenRV)). Asset names are stable so these links always point at the latest published release:

| Platform | Download |
|----------|----------|
| Linux x86_64 | [**tar.gz**](https://github.com/derek-rein/OpenRV/releases/latest/download/openrv-linux-x86_64.tar.gz) |
| macOS Apple Silicon | [**DMG**](https://github.com/derek-rein/OpenRV/releases/latest/download/openrv-macos-arm64.dmg) |
| Windows x64 | [**installer**](https://github.com/derek-rein/OpenRV/releases/latest/download/openrv-windows-x86_64-setup.exe) |

Release builds enable every codec switch that does not need a login-gated SDK, including GPL H.264/H.265 encoders. What that means for redistribution is in [release codecs and signing](docs/build_system/release_codecs_and_signing.md).

All releases: [github.com/derek-rein/OpenRV/releases](https://github.com/derek-rein/OpenRV/releases)

Builds use VFX Platform **CY2025** (Qt 6.5.3, Python 3.11). Unpack the archive and run Open RV from the install tree. For source builds and full docs, see upstream [AcademySoftwareFoundation/OpenRV](https://github.com/AcademySoftwareFoundation/OpenRV).

### Publishing a release

Same shape as [exr-converter](https://github.com/derek-rein/exr-converter): **PR → checks → merge → auto-tag → multi-platform build → GitHub Release**.

Tags are plain semver: **`vX.Y.Z`** (example: `v4.0.2`). Version source of truth is `CMakeLists.txt` (`RV_MAJOR_VERSION` / `RV_MINOR_VERSION` / `RV_REVISION_NUMBER`).

```bash
git checkout main && git pull
git checkout -b release/X.Y.Z

# Bump CMakeLists point version (or edit the three RV_* SETs by hand)
python3 scripts/apply_release_version.py X.Y.Z
git add CMakeLists.txt
git commit -m "release: X.Y.Z"

git push -u origin HEAD
gh pr create --base main --title "release: X.Y.Z" --body "Ship Open RV X.Y.Z multi-platform packages."

# Wait for PR Check to go green, then approve + merge
gh pr checks
gh pr merge --merge   # or --squash
```

After merge:

1. **Auto-tag release** reads the version from `CMakeLists.txt`, creates `vX.Y.Z` if missing, and dispatches **Multi-platform Build** (needed because `GITHUB_TOKEN` tag pushes do not start other workflows).
2. **Multi-platform Build** builds Linux / macOS ARM / Windows, then publishes a GitHub Release with the stable asset names above.

Manual fallbacks:

```bash
# Human/PAT tag push (does start Multi-platform Build):
git tag -a vX.Y.Z -m "release: X.Y.Z" && git push origin vX.Y.Z

# Or Actions UI / CLI dispatch:
gh workflow run "Multi-platform Build" --ref main -f tag=vX.Y.Z -f platforms=all
```

Full multi-platform builds run **only after merge** (or manual Actions dispatch / human tag push) — never on the PR itself. The PR only needs the light **PR Check** gate.

**Note:** Upstream's midnight **OpenRV** and **Conan-OpenRV** crons are disabled on this fork so they are not queued. Both were already owner-gated to AcademySoftwareFoundation (a skipped run bills nothing). Prebuilt packages do **not** use the Conan workflow. Dispatch **Multi-platform Build** and pick `linux`, `macos`, or `windows` when you only need one platform. macOS notarization is submitted and the runner exits; **Notarize finish** (Ubuntu, every 15 minutes) staples the DMG after Apple accepts and replaces the release asset. An empty queue is a no-op.

## Cloning the repository

The quickest way to download OpenRV's source code is to clone this repository.

```bash
# Don't forget the --recursive flag! 
git clone --recursive https://github.com/AcademySoftwareFoundation/OpenRV.git
```

However, if you'd like to actually build Open RV or contribute to the project, we recommend you follow the instructions below *before* cloning the repository, as it involves quite a lot more setup than just cloning. If that's your case, skip this step for now, we'll get to cloning in a bit.

## Contributing to Open RV

We welcome community contributions. In general, to maximize your chances of successfully building and contributing to Open RV, you should:

- Be very familiar with git/github and its usage.
- Have your own github account, where you will fork this repository
- Clone your forked repository instead of the main Open RV repository
- Create a branch from your fork's 'main' branch before modifying code
- Fix conflicts prior to creating a pull request
- Update your branch (git pull, git rebase) before creating your pull request

If you're comfortable and familiar with the above, we are looking forward to your contributions. Just continue reading, we'll help you along with your setup.

## Building the workstation

Open RV is currently supported on macOS Ventura 13.x and later, Windows 10 and later, and Rocky Linux 8.x/9.x.

You should start by setting up the platform-specific packages and dependencies for your operating system:

- [macOS Ventura and later](https://aswf-openrv.readthedocs.io/en/latest/build_system/config_macos.html)
- [Windows 10 and later](https://aswf-openrv.readthedocs.io/en/latest/build_system/config_windows.html)
- [Rocky Linux 8/9](https://aswf-openrv.readthedocs.io/en/latest/build_system/config_linux_rocky89.html)

Once this platform-specific setup is complete, move to the common build instructions.

- [Common build instructions](https://aswf-openrv.readthedocs.io/en/latest/build_system/config_common_build.html)

Note that as of 2025, CentOS 7 is no longer supported as a platform for Open RV since CentOS was end-of-life'd as of summer of 2024.

Also note that support for other *current* operating systems (typically, other Linux variants) is on a "if-we-can-find-time" basis because our primary mandate is to support immediate customer needs on official VFX reference platforms. We would however welcome community-driven contributions to support other platforms.

## About third-party licenses

See [THIRD-PARTY.md](THIRD-PARTY.md) for license information about portions of Open RV that have been imported from other projects.
