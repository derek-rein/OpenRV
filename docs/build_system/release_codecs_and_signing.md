# Release codecs, signing, and installers

This fork's **Multi-platform Build** (`workflow_dispatch` or a `vX.Y.Z` tag) configures every platform with `-DRV_ENABLE_ALL_CODECS=ON`. A local build without that flag keeps upstream's defaults: patent-restricted FFmpeg decoders and encoders stay disabled. Neither build passes `--enable-gpl` or `--enable-nonfree`, and neither links x264 or x265. The release build does link BSD libvpx and libaom.

The canonical lists live in `cmake/defaults/rv_codec_options.cmake`. `scripts/ci/check_codec_options.py` fails if a new name is added to `cmake/dependencies/ffmpeg.cmake` or `src/lib/image/mio_ffmpeg/init.cpp` and the preset does not mention it.

## What the flag turns on

### FFmpeg decoders (`RV_FFMPEG_NON_FREE_DECODERS_TO_ENABLE`)

OpenRV passes each of these to FFmpeg's configure as "do not `--disable-decoder`" when the name is in `NON_FREE_DECODERS_TO_DISABLE`, and defines `__FFMPEG_ENABLE_NON_FREE_DECODER_<name>` so `mio_ffmpeg` will not refuse the codec.

| Name | Role |
|------|------|
| `aac`, `aac_at`, `aac_fixed`, `aac_latm` | AAC decode |
| `ac3`, `ac3_fixed`, `eac3` | Dolby Digital / E-AC-3. `ac3_fixed` and `eac3` are FFmpeg 8 only; passing them on 6/7 only adds the application define |
| `bink`, `binkaudio_dct`, `binkaudio_rdft` | Bink |
| `dnxhd` | Avid DNxHD / DNxHR decode through FFmpeg |
| `dvvideo` | DV |
| `hevc` | H.265/HEVC decode (built-in decoder; the app used to hide it) |
| `mpeg2video` | MPEG-2 video |
| `prores`, `prores_raw`, `prores_aw`, `prores_ks`, `prores_lgpl` | FFmpeg's own ProRes decoders, not Apple's SDK |
| `qtrle` | QuickTime animation |
| `svq1`, `svq3` | Sorenson |
| `vp9`, `vp9_cuvid`, `vp9_mediacodec`, `vp9_qsv`, `vp9_rkmpp`, `vp9_v4l2m2m` | VP9 and its hardware variants |

The VP9 **parser** is left enabled when `vp9` is in that list. Without the parser, VP9 in WebM/MKV does not demux. `webm`, `ogv`, and `aac` are registered as movie extensions again.

`h264` (decode) and `libdav1d` (AV1 decode) were already enabled and stay enabled.

### FFmpeg encoders

GPL encoders are the ones that are dropped. x264 and x265 are not built, and configure refuses `--enable-gpl`, `--enable-nonfree`, `--enable-libx264`, and `--enable-libx265`. The GPL filter `geq` stays disabled. FFmpeg keeps the rest of its encoder set.

With `RV_ENABLE_ALL_CODECS`, the patent encoder list is turned back on: `aac`, `aac_mf`, `dnxhd`, `dvvideo`, `prores`, `qtrle`, `vp9_qsv`, `vp9_vaapi`. FFmpeg's other LGPL encoders (including `prores_ks`, `prores_aw`, `mjpeg`, PCM, and rawvideo) stay at FFmpeg's defaults. `cmake/dependencies/bsd_media_codecs.cmake` builds libvpx 1.15.2 (BSD) and libaom 3.12.1 (BSD-2-Clause, encoder only) and passes `--enable-libvpx` and `--enable-libaom`. AV1 decode stays on dav1d. H.264 and HEVC decode stay on the built-in decoders.

`MovieFFMpeg.cpp` advertises every encoder the build actually contains except the GPL names (`libx264`, `libx264rgb`, `libx265`, `libxvid`, `libxavs`, `libxavs2`). A name that was not compiled does not show up.

`scripts/ci/check_codec_options.py` checks the decoder and encoder presets, the BSD flags, and the GPL refusal.

### Hardware encoders

These are compiled when the build can see them. A missing SDK does not fail configure.

| Path | When it is built |
|------|------------------|
| VideoToolbox (`h264_videotoolbox`, `hevc_videotoolbox`, `prores_videotoolbox`) | Apple. `RV_FFMPEG_USE_VIDEOTOOLBOX` is forced `ON` and FFmpeg gets `--enable-videotoolbox`. This does not replace Apple's ProRes SDK on Linux or Windows |
| Media Foundation (`h264_mf`, `hevc_mf`, `av1_mf`, `aac_mf`) | Windows, when the Windows SDK headers are present. FFmpeg autodetects this |
| NVENC (`h264_nvenc`, `hevc_nvenc`, `av1_nvenc`) | Windows and Linux. `hw_encode_headers.cmake` installs MIT ffnvcodec 12.2.72.0 headers. FFmpeg dlopens the NVIDIA driver; the headers are not shipped. macOS configure disables NVENC |
| AMF (`h264_amf`, `hevc_amf`, `av1_amf`) | Windows. MIT AMF 1.4.36 headers are installed for the compiler only |
| QSV (`h264_qsv`, `hevc_qsv`, `av1_qsv`, `vp9_qsv`) | When `pkg-config` finds `libvpl` >= 2.6 (`--enable-libvpl`) or `libmfx` (`--enable-libmfx`). CI does not vendor oneVPL |
| VAAPI (`h264_vaapi`, `hevc_vaapi`, `av1_vaapi`, `vp9_vaapi`) | Linux release builds omit `--disable-vaapi`, so FFmpeg turns VAAPI on if libva is installed. The Linux job installs `libva-devel` when the package exists. Other platforms keep `--disable-vaapi` |

### OpenEXR and OpenImageIO

OpenEXR is not optional in this tree: `cmake/dependencies/openexr.cmake` always builds it, and OIIO is pointed at that install. With `RV_ENABLE_ALL_CODECS`, OIIO is also configured with `USE_OPENEXR`, `USE_JPEG`, `USE_PNG`, `USE_TIFF`, `USE_OPENJPEG`, `USE_WEBP`, `USE_LIBRAW`, `USE_OPENJPH`, and `USE_FREETYPE` explicitly `ON`, so a missing library fails the build instead of silently dropping a format. Linux CI installs `freetype-devel` for that.

Left off on purpose:

| Switch | Why |
|--------|-----|
| `USE_GIF` | Needs giflib, which this repo does not build |
| `USE_FFMPEG` on OIIO | OIIO's own FFmpeg plugin would fight RV's `mio_ffmpeg` |
| `USE_PYTHON` on OIIO | Needs pybind11 and is not a media codec |
| FFmpeg `--enable-nonfree` | See licensing below. Not passed |

### Already on, no extra flag

JPEG (libjpeg-turbo), PNG, TIFF, OpenJPEG, OpenJPH (HTJ2K), WebP, LibRaw/camera RAW, DPX, Cineon, EXR, and the built-in image plugins under `src/lib/image`.

## Licensing consequences

This is a description of the flags, not legal advice. CompStart.pro should have counsel review a build before public redistribution.

**LGPL / Apache.** OpenRV is Apache-2.0. FFmpeg in this build is the LGPL v2.1+ configuration: shared libraries, no `--enable-gpl`, no `--enable-nonfree`, no GPL codec libraries. libvpx (BSD) and libaom (BSD-2-Clause) are linked into that LGPL FFmpeg. Qt and LibRaw are also LGPL. The installer shows `scripts/windows/INSTALLER_LICENSE.txt`. The About dialog labels FFmpeg as LGPL v2.1+ and lists libvpx and libaom when those versions were set.

**Not FFmpeg "nonfree".** `--enable-nonfree` allows external libraries whose licenses forbid redistribution (the usual example is fdk-aac). This fork does not pass it. The OpenRV variable name `RV_FFMPEG_NON_FREE_*` is the project's own patent list, not that configure flag.

**Patents.** Enabling the decoders above does not grant a patent license. H.264, H.265/HEVC, AAC, AC-3, MPEG-2, and DNxHD/DNxHR are widely treated as patent-encumbered. Distributing a binary that decodes them can require a license from the relevant pool (Via LA, Dolby, Avid, and others) depending on country and use. VP9 and AV1 decode are included as well.

**dav1d** is BSD 2-Clause and is the AV1 decoder. libaom is built with its decoder off, so it does not replace dav1d. Neither pulls the binary under the GPL.

## Follow-ups (login-gated SDKs — not downloaded)

These exist as CMake hooks but need a zip or installer from a vendor account. CI does not set them.

| Hook | What it is |
|------|------------|
| `RV_DEPS_APPLE_PRORES_SDK_ZIP_PATH` | Apple ProRes decoder SDK (email `prores@apple.com`). Required for the official ProRes path on Linux/Windows. FFmpeg's `prores` decoder above is the non-SDK path and is not Apple's implementation. On Apple Silicon, VideoToolbox is the supported hardware path |
| `RV_DEPS_BMD_DECKLINK_SDK_ZIP_PATH` | Blackmagic Desktop Video / DeckLink output |
| compatible with Blackmagic RAW | Optional. See below. Skipped when `BRAW_SDK_READ_TOKEN` is unset |
| supports R3D files | Optional. See below. Skipped when `R3D_SDK_READ_TOKEN` is unset |
| ARRI RAW (`RV_DEPS_ARRIRAW_VERSION`) | Same: About dialog only |
| NDI | `FindNDI_SDK.cmake` looks for an SDK installed on the machine. The SDK download is account-gated |
| fdk-aac | Would need `--enable-nonfree` and is intentionally not added |
| giflib | Would allow `USE_GIF=ON` in OIIO |

## Optional camera playback

Movie plugins `mio_braw` and `mio_r3d` are always built. They load a small project-owned bridge (`src/lib/image/vendor_bridge`, MIT) only when the vendor runtime was staged. Without that runtime, opening a clip reports that playback is not installed and the rest of the build still succeeds.

CI fetches the SDK only when the matching secret is set:

| Secret | Repository | Release | Asset |
|--------|------------|---------|-------|
| `BRAW_SDK_READ_TOKEN` | `derek-rein/braw-sdk-private` | `sdk-6.0` | `BlackmagicRAWSDK-6.0-full.tar.gz` |
| `R3D_SDK_READ_TOKEN` | `derek-rein/r3d-sdk-private` | `sdk-9.2.1` | `R3DSDKv9_2_1-full.tar.gz` |

`scripts/sdk/fetch_braw_sdk.py` and `scripts/sdk/fetch_r3d_sdk.py` take `--optional` and print `SKIP` when the token is absent. They do not log archive contents. `scripts/sdk/build_*_bridge.py` compiles the bridge against the local SDK and copies **only** vendor dynamic libraries into `build/<name>/redistributable`. `scripts/sdk/stage_private_codecs.py` then installs that runtime into a private app directory:

| Platform | compatible with Blackmagic RAW | supports R3D files |
|----------|--------------------------------|--------------------|
| macOS | `Contents/Frameworks/braw` | `Contents/MacOS/r3d` |
| Linux and Windows | `lib/private/braw` | `lib/private/r3d` |

Headers, static libraries, samples, and docs are refused. The bridge object code is ours; the vendor libraries stay unmodified except that macOS codesign must sign them so the app bundle can be notarized. Set `OPENRV_R3D_PIPELINE=log3g10` for the log primary development path. The default is the clip's stored look, which is the review image.

The plugins read picture only. Audio in those files is not decoded. `THIRD_PARTY_NOTICES.txt` and the installer EULA (`scripts/windows/INSTALLER_LICENSE.txt`, also staged as `EULA.txt`) cover the LGPL pieces and the runtime terms: no further redistribution, no reverse engineering, no warranty, and a liability limit. Do not use vendor marks beyond "compatible with Blackmagic RAW" and "supports R3D files".

Encrypted RTMP protocols (`ffrtmpcrypt`, `rtmpe`, `rtmpte`) stay disabled. They are not media codecs.

## macOS signing and notarization

Notarization does not hold the macOS runner. The macOS job signs, builds the DMG, submits it, and exits. A separate `ubuntu-latest` workflow staples the ticket after Apple accepts.

`scripts/macos/sign_and_notarize.sh` runs at the end of the macOS release job.

1. If any required secret is empty, it logs the names and writes an **unsigned** DMG (`openrv-macos-arm64.dmg`). Fork pull requests never receive secrets, so this is the expected path there. Multi-platform Build does not run on pull requests anyway.
2. If `MACOS_SIGNING_IDENTITY` is set to anything other than `Developer ID Application: Medeu Global LLC (83546T4BT8)`, the script exits with an error. It will not sign with a personal Apple Development identity.
3. `APPLE_TEAM_ID` must be `83546T4BT8` when it is set.
4. The Developer ID certificate is imported into a temporary keychain from `MACOS_CERT_P12_BASE64`.
5. Every Mach-O under `RV.app` is signed inside-out (dylibs, `.so`, frameworks, plugins, Python extensions, nested apps), hardened runtime (`--options runtime`) plus a timestamp. Executables and bundles get `scripts/macos/entitlements.plist`: `allow-jit`, `allow-unsigned-executable-memory`, `disable-library-validation` (PySide/Python plugins), plus audio input, network client, and user-selected files.
6. A DMG is built (app plus an `/Applications` symlink) and signed.
7. `xcrun notarytool submit` is called **without** `--wait` and **without** a status poll. The script writes `dist/notarize-pending.json` (`submission_id`, `run_id`, `dmg_name`, `sha256`, `target_tag`) and returns.
8. The workflow uploads that JSON next to the signed DMG as a build artifact, and `scripts/macos/publish_notarize_queue.sh` puts `pending-<submission-id>.json` plus `pending-<submission-id>.dmg` on the **draft** GitHub release tag `notarize-queue`. Do not publish that draft. It is only a mailbox.

The macOS job `timeout-minutes` is still 360 because the compile can take a few hours. Waiting for Apple is no longer part of that window. The only Apple time left on the macOS runner is the `notarytool submit` upload itself (the DMG transfer, typically a few minutes), then the job exits. Notarization analysis costs **0 macOS minutes**.

`workflow_dispatch` input `wait_for_notarization` defaults to **false**. Set it only for a one-off that should poll `notarytool info` for up to 4 hours, staple with `xcrun stapler`, and `spctl` on the macOS runner. That path does not write a queue record.

### Notarize finish (Ubuntu)

`.github/workflows/notarize-finish.yml` runs on `ubuntu-latest` every 15 minutes, and on `workflow_dispatch` with optional `submission_id` and `run_id`. GitHub runs the cron only from the default branch, so it starts after this file is merged. The macOS job does not dispatch the finisher: a dispatch cannot be delayed, and an immediate check would still see "In Progress".

1. `gh release view notarize-queue` lists assets. If there is no `pending-*.json`, the job prints `no pending notarization submissions` and exits 0. It does not call Apple and does not download `rcodesign`.
2. Otherwise one JWT is signed from `ASC_KEY_ID`, `ASC_ISSUER_ID`, and `ASC_API_KEY_P8` (ES256, `aud` `appstoreconnect-v1`) and the script `GET`s `https://appstoreconnect.apple.com/notary/v2/submissions/{id}`.
3. **In Progress** (or any other non-terminal status): log the status and leave the marker. The job still exits in seconds.
4. **Accepted:** download the queued DMG, check its sha256, fetch and print the notary log (`GET .../submissions/{id}/logs`, then the `developerLogUrl`), staple with `rcodesign staple` from the apple-codesign 0.29.0 Linux musl build, then `rcodesign verify` and `rcodesign print-signature-info`. The stapled DMG replaces `openrv-macos-arm64.dmg` on the versioned release (`target_tag` in the JSON) via `gh release upload --clobber`. The `pending-*` assets are deleted so the next cron will not process them again. If the versioned release does not exist yet, the marker stays and the next run retries.
5. **Invalid or Rejected:** print the notary log, upload it as `failed-<id>.log` on the queue, delete the pending marker, and fail the job.

The finisher is idempotent. A second run after a successful staple finds no pending marker. A run that dies after Apple accepts but before the marker is deleted staples and uploads again (`--clobber` replaces the same asset name).

There is a window after the GitHub Release is published and before Apple has accepted where the downloadable DMG is signed but not yet stapled. Gatekeeper can still reach Apple for the ticket once notarization has completed; stapling makes that check work offline. Expect the replacement within about 15 minutes after Apple accepts.

### Secrets Derek needs to add

| Secret | Contents |
|--------|----------|
| `MACOS_CERT_P12_BASE64` | Base64 of the Developer ID Application `.p12` for Medeu Global LLC |
| `MACOS_CERT_PASSWORD` | Password for that `.p12` |
| `MACOS_SIGNING_IDENTITY` | Exactly `Developer ID Application: Medeu Global LLC (83546T4BT8)` |
| `APPLE_TEAM_ID` | `83546T4BT8` |
| `ASC_KEY_ID` | App Store Connect API key id |
| `ASC_ISSUER_ID` | App Store Connect issuer id |
| `ASC_API_KEY_P8` | The API key `.p8` PEM, including the `BEGIN PRIVATE KEY` lines (a real multi-line secret, not a `\n`-escaped one-liner) |

## Windows installer

`scripts/windows/openrv.iss` (Inno Setup 6) is compiled in the Windows job after the zip of the install tree.

- Installs the `_install` tree to `C:\Program Files\CompStart.pro\Open RV`
- Publisher **CompStart.pro** (`https://compstart.pro`)
- Start menu shortcut to `bin\rv.exe`, plus an uninstall shortcut
- Optional desktop shortcut (unchecked by default)
- Optional file associations for `.exr`, `.dpx`, `.mov`, `.mp4`, and `.rv` (unchecked by default), removed on uninstall
- Icon is `src/bin/apps/rv/RV.ico`, which already contains 16, 24, 32, 48, 64, 96, 128, and 256 px images
- License page is `scripts/windows/INSTALLER_LICENSE.txt`
- Artifact: `openrv-windows-x86_64-setup.exe`, uploaded next to `openrv-windows-x86_64.zip`

## CI minutes

| Workflow | What the upstream cron does | This fork |
|----------|-----------------------------|-----------|
| `OpenRV` (`.github/workflows/ci.yml`) | `0 0 * * *`. Full matrix via `ci-linux.yml`, `ci-macos.yml`, `ci-windows.yml`: Rocky 8 and 9, macOS x86_64 and arm64, Windows, Release always, Debug when the matrix is full. Several hours per platform | Cron removed. Jobs were already `if: github.repository_owner == 'AcademySoftwareFoundation'`, so a queued run would have skipped and billed about nothing. Removing the cron means GitHub does not queue it. `workflow_dispatch` remains |
| `Conan-OpenRV` | `0 0 * * *`. Conan install/build for Rocky 8/9, macOS arm64, and Windows. Not used by the release packages | Cron removed. Same owner gate, plus `workflow_dispatch` if someone is actually working on Conan packaging |
| `Multi-platform Build` | Tag push or manual dispatch only. Not a nightly. `platforms` input is `all`, `linux`, `macos`, or `windows` | Unchanged trigger. Configure passes `-DRV_ENABLE_ALL_CODECS=ON`. Qt is cached (aqt). macOS dependency objects are cached, with the key including the codec CMake files. ccache (500 MB) is persisted on Linux and macOS. Windows sccache uses the Actions cache (`SCCACHE_GHA_ENABLED=true`). Notarization waiting is not part of the macOS job |
| `Notarize finish` | Not an upstream workflow | `ubuntu-latest` every 15 minutes, plus `workflow_dispatch`. One `gh release view` and exit 0 when `notarize-queue` has no `pending-*.json`. An in-progress submission is a single Notary API GET and exit. `rcodesign` is downloaded only after Apple accepts |

Do not turn the multi-platform workflow on for every push. One platform at a time is the `platforms` input on **Actions → Multi-platform Build → Run workflow**.
