#
# Copyright (C) 2026 Derek Rein. All Rights Reserved.
#
# SPDX-License-Identifier: Apache-2.0
#

# Static GPL/BSD codec libraries linked into the OpenRV FFmpeg build when
# RV_FFMPEG_ENABLE_GPL is ON (which RV_ENABLE_ALL_CODECS turns on).
#
#   x264   GPL-2.0-or-later   H.264 encoder (8-bit and 10-bit, --bit-depth=all)
#   x265   GPL-2.0-or-later   H.265 encoder (8-bit; 10-bit decode is the native hevc decoder)
#   libvpx BSD                VP8/VP9 encoder, VP9 high bit depth
#   libaom BSD-2              AV1 encoder (decode stays on dav1d, already enabled)
#
# These are source builds. No login-gated SDK is downloaded.
# FFmpeg is configured with --enable-gpl and without --enable-nonfree.

IF(NOT RV_FFMPEG_ENABLE_GPL)
  RETURN()
ENDIF()

INCLUDE(ProcessorCount)
INCLUDE(ExternalProject)

IF(NOT RV_DEPS_BASE_DIR)
  SET(RV_DEPS_BASE_DIR
      "${CMAKE_BINARY_DIR}"
  )
ENDIF()
IF(NOT RV_DEPS_DOWNLOAD_DIR)
  SET(RV_DEPS_DOWNLOAD_DIR
      "${RV_DEPS_BASE_DIR}/downloads"
  )
ENDIF()
FILE(MAKE_DIRECTORY ${RV_DEPS_DOWNLOAD_DIR})

PROCESSORCOUNT(_gpl_cpu_count)
IF(_gpl_cpu_count EQUAL 0)
  SET(_gpl_cpu_count
      1
  )
ENDIF()

IF(NOT CMAKE_BUILD_TYPE)
  SET(CMAKE_BUILD_TYPE
      Release
  )
ENDIF()

FUNCTION(_rv_write_pc prefix name version extra_libs)
  FILE(MAKE_DIRECTORY "${prefix}/lib/pkgconfig")
  FILE(
    WRITE "${prefix}/lib/pkgconfig/${name}.pc"
    "prefix=${prefix}\n"
    "exec_prefix=\${prefix}\n"
    "libdir=\${prefix}/lib\n"
    "includedir=\${prefix}/include\n"
    "\n"
    "Name: ${name}\n"
    "Description: ${name} built for Open RV\n"
    "Version: ${version}\n"
    "Libs: -L\${libdir} -l${name}\n"
    "Libs.private: ${extra_libs}\n"
    "Cflags: -I\${includedir}\n"
  )
ENDFUNCTION()

FUNCTION(_rv_ffmpeg_static_lib prefix)
  SET_PROPERTY(
    GLOBAL APPEND
    PROPERTY "RV_FFMPEG_EXTRA_C_OPTIONS" "--extra-cflags=-I${prefix}/include"
  )
  IF(WIN32)
    SET_PROPERTY(
      GLOBAL APPEND
      PROPERTY "RV_FFMPEG_EXTRA_LIBPATH_OPTIONS" "--extra-ldflags=-LIBPATH:${prefix}/lib"
    )
  ELSE()
    SET_PROPERTY(
      GLOBAL APPEND
      PROPERTY "RV_FFMPEG_EXTRA_LIBPATH_OPTIONS" "--extra-ldflags=-L${prefix}/lib"
    )
  ENDIF()
  SET_PROPERTY(
    GLOBAL APPEND
    PROPERTY "RV_GPL_CODEC_PKGCONFIG_DIR_LIST" "${prefix}/lib/pkgconfig"
  )
ENDFUNCTION()

# pthread is required by the unix static archives. The MSVC x264 build uses win32 threads.
IF(WIN32)
  SET(_gpl_pthread_libs
      ""
  )
ELSE()
  SET(_gpl_pthread_libs
      "-lpthread -lm"
  )
ENDIF()

# --- x264 (GPL) ---
SET(_x264_version
    "31e19f92"
)
SET(_x264_prefix
    "${RV_DEPS_BASE_DIR}/RV_DEPS_X264/install"
)
SET(RV_DEPS_X264_VERSION
    "${_x264_version}"
    CACHE STRING "x264 stable snapshot linked into FFmpeg" FORCE
)
_rv_write_pc("${_x264_prefix}" "x264" "${_x264_version}" "${_gpl_pthread_libs}")
_rv_ffmpeg_static_lib("${_x264_prefix}")
IF(WIN32)
  # x264's configure detects cl.exe and emits an MSVC static lib. The Windows
  # CI image has cl on PATH via the VS developer command prompt.
  SET(_x264_configure_env
      ${CMAKE_COMMAND} -E env "CC=cl" "CXX=cl"
  )
ELSE()
  SET(_x264_configure_env
      ${CMAKE_COMMAND} -E env
  )
ENDIF()
EXTERNALPROJECT_ADD(
  RV_DEPS_X264
  URL "https://github.com/mirror/x264/archive/31e19f92f00c7003fa115047ce50978bc98c3a0d.tar.gz"
  URL_HASH SHA256=d053c9d86988d6bc78237ca5205865c5ddf99c98ef4cd9927eec8f6d388f6dd9
  DOWNLOAD_DIR ${RV_DEPS_DOWNLOAD_DIR}
  DOWNLOAD_EXTRACT_TIMESTAMP TRUE
  SOURCE_DIR ${RV_DEPS_BASE_DIR}/RV_DEPS_X264/src
  BUILD_IN_SOURCE TRUE
  CONFIGURE_COMMAND
    ${_x264_configure_env} sh ./configure --prefix=${_x264_prefix} --enable-static --disable-shared --disable-cli --enable-pic --bit-depth=all
    --disable-lavf --disable-swscale --disable-avs --disable-gpac --disable-ffms --disable-lsmash --disable-opencl
  BUILD_COMMAND make -j${_gpl_cpu_count}
  INSTALL_COMMAND make install COMMAND ${CMAKE_COMMAND} -DPREFIX=${_x264_prefix} -P ${CMAKE_CURRENT_LIST_DIR}/normalize_codec_libs.cmake
  BUILD_BYPRODUCTS "${_x264_prefix}/lib/libx264.a" "${_x264_prefix}/lib/x264.lib"
  USES_TERMINAL_BUILD TRUE
)

# --- x265 (GPL) ---
# Newest tag on the public videolan GitHub mirror. Bitbucket release tarballs
# (3.5+) are not anonymously fetchable from CI. 8-bit encoder; 10-bit HEVC
# decode uses FFmpeg's built-in hevc decoder.
SET(_x265_version
    "3.4"
)
SET(_x265_prefix
    "${RV_DEPS_BASE_DIR}/RV_DEPS_X265/install"
)
SET(RV_DEPS_X265_VERSION
    "${_x265_version}"
    CACHE STRING "x265 version linked into FFmpeg" FORCE
)
# x265 3.4 assembly is x86-only and fails to configure on Apple Silicon.
IF(RV_TARGET_APPLE_ARM64)
  SET(_x265_assembly
      OFF
  )
ELSE()
  SET(_x265_assembly
      ON
  )
ENDIF()
_rv_write_pc("${_x265_prefix}" "x265" "${_x265_version}" "${_gpl_pthread_libs}")
_rv_ffmpeg_static_lib("${_x265_prefix}")
EXTERNALPROJECT_ADD(
  RV_DEPS_X265
  URL "https://github.com/videolan/x265/archive/refs/tags/3.4.tar.gz"
  URL_HASH SHA256=544d147bf146f8994a7bf8521ed878c93067ea1c7c6e93ab602389be3117eaaf
  DOWNLOAD_DIR ${RV_DEPS_DOWNLOAD_DIR}
  DOWNLOAD_EXTRACT_TIMESTAMP TRUE
  SOURCE_DIR ${RV_DEPS_BASE_DIR}/RV_DEPS_X265/src
  SOURCE_SUBDIR source
  BINARY_DIR ${RV_DEPS_BASE_DIR}/RV_DEPS_X265/build
  CMAKE_ARGS -DCMAKE_INSTALL_PREFIX=${_x265_prefix} -DCMAKE_BUILD_TYPE=${CMAKE_BUILD_TYPE} -DCMAKE_INSTALL_LIBDIR=lib
             -DCMAKE_POSITION_INDEPENDENT_CODE=ON -DENABLE_SHARED=OFF -DENABLE_CLI=OFF -DENABLE_PIC=ON -DENABLE_ASSEMBLY=${_x265_assembly}
  BUILD_COMMAND ${CMAKE_COMMAND} --build ${RV_DEPS_BASE_DIR}/RV_DEPS_X265/build --config ${CMAKE_BUILD_TYPE} --parallel ${_gpl_cpu_count}
  INSTALL_COMMAND ${CMAKE_COMMAND} --install ${RV_DEPS_BASE_DIR}/RV_DEPS_X265/build --config ${CMAKE_BUILD_TYPE} --prefix ${_x265_prefix}
                  COMMAND ${CMAKE_COMMAND} -DPREFIX=${_x265_prefix} -P ${CMAKE_CURRENT_LIST_DIR}/normalize_codec_libs.cmake
  BUILD_BYPRODUCTS "${_x265_prefix}/lib/libx265.a" "${_x265_prefix}/lib/x265-static.lib" "${_x265_prefix}/lib/x265.lib"
  USES_TERMINAL_BUILD TRUE
)

# --- libvpx (BSD) ---
SET(_vpx_version
    "1.15.2"
)
SET(_vpx_prefix
    "${RV_DEPS_BASE_DIR}/RV_DEPS_LIBVPX/install"
)
SET(RV_DEPS_LIBVPX_VERSION
    "${_vpx_version}"
    CACHE STRING "libvpx version linked into FFmpeg" FORCE
)
IF(WIN32)
  # Visual Studio solution target. `make` invokes msbuild for this target.
  SET(_vpx_target_args
      --target=x86_64-win64-vs17
  )
ELSE()
  SET(_vpx_target_args
      ""
  )
ENDIF()
_rv_write_pc("${_vpx_prefix}" "vpx" "${_vpx_version}" "${_gpl_pthread_libs}")
_rv_ffmpeg_static_lib("${_vpx_prefix}")
EXTERNALPROJECT_ADD(
  RV_DEPS_LIBVPX
  URL "https://github.com/webmproject/libvpx/archive/refs/tags/v1.15.2.tar.gz"
  URL_HASH SHA256=26fcd3db88045dee380e581862a6ef106f49b74b6396ee95c2993a260b4636aa
  DOWNLOAD_DIR ${RV_DEPS_DOWNLOAD_DIR}
  DOWNLOAD_EXTRACT_TIMESTAMP TRUE
  SOURCE_DIR ${RV_DEPS_BASE_DIR}/RV_DEPS_LIBVPX/src
  BUILD_IN_SOURCE TRUE
  CONFIGURE_COMMAND
    sh ./configure --prefix=${_vpx_prefix} ${_vpx_target_args} --enable-static --disable-shared --disable-examples --disable-tools --disable-docs
    --disable-unit-tests --enable-pic --enable-vp8 --enable-vp9 --enable-vp9-highbitdepth --as=nasm
  BUILD_COMMAND make -j${_gpl_cpu_count}
  INSTALL_COMMAND make install COMMAND ${CMAKE_COMMAND} -DPREFIX=${_vpx_prefix} -P ${CMAKE_CURRENT_LIST_DIR}/normalize_codec_libs.cmake
  BUILD_BYPRODUCTS "${_vpx_prefix}/lib/libvpx.a" "${_vpx_prefix}/lib/vpx.lib"
  USES_TERMINAL_BUILD TRUE
)

# --- libaom (AV1 encoder, BSD) ---
SET(_aom_version
    "3.12.1"
)
SET(_aom_prefix
    "${RV_DEPS_BASE_DIR}/RV_DEPS_LIBAOM/install"
)
SET(RV_DEPS_LIBAOM_VERSION
    "${_aom_version}"
    CACHE STRING "libaom version linked into FFmpeg" FORCE
)
_rv_write_pc("${_aom_prefix}" "aom" "${_aom_version}" "${_gpl_pthread_libs}")
_rv_ffmpeg_static_lib("${_aom_prefix}")
EXTERNALPROJECT_ADD(
  RV_DEPS_LIBAOM
  URL "https://storage.googleapis.com/aom-releases/libaom-3.12.1.tar.gz"
  URL_HASH SHA256=9e9775180dec7dfd61a79e00bda3809d43891aee6b2e331ff7f26986207ea22e
  DOWNLOAD_DIR ${RV_DEPS_DOWNLOAD_DIR}
  DOWNLOAD_EXTRACT_TIMESTAMP TRUE
  SOURCE_DIR ${RV_DEPS_BASE_DIR}/RV_DEPS_LIBAOM/src
  BINARY_DIR ${RV_DEPS_BASE_DIR}/RV_DEPS_LIBAOM/build
  CMAKE_ARGS -DCMAKE_INSTALL_PREFIX=${_aom_prefix} -DCMAKE_BUILD_TYPE=${CMAKE_BUILD_TYPE} -DCMAKE_INSTALL_LIBDIR=lib
             -DCMAKE_POSITION_INDEPENDENT_CODE=ON -DBUILD_SHARED_LIBS=OFF -DENABLE_DOCS=OFF -DENABLE_EXAMPLES=OFF -DENABLE_TESTS=OFF
             -DENABLE_TESTDATA=OFF -DENABLE_TOOLS=OFF -DENABLE_NASM=ON -DCONFIG_AV1_DECODER=0 -DCONFIG_AV1_ENCODER=1
  BUILD_COMMAND ${CMAKE_COMMAND} --build ${RV_DEPS_BASE_DIR}/RV_DEPS_LIBAOM/build --config ${CMAKE_BUILD_TYPE} --parallel ${_gpl_cpu_count}
  INSTALL_COMMAND ${CMAKE_COMMAND} --install ${RV_DEPS_BASE_DIR}/RV_DEPS_LIBAOM/build --config ${CMAKE_BUILD_TYPE} --prefix ${_aom_prefix}
                  COMMAND ${CMAKE_COMMAND} -DPREFIX=${_aom_prefix} -P ${CMAKE_CURRENT_LIST_DIR}/normalize_codec_libs.cmake
  BUILD_BYPRODUCTS "${_aom_prefix}/lib/libaom.a" "${_aom_prefix}/lib/aom.lib"
  USES_TERMINAL_BUILD TRUE
)

GET_PROPERTY(
  _gpl_pkgconfig_dirs GLOBAL
  PROPERTY "RV_GPL_CODEC_PKGCONFIG_DIR_LIST"
)
SET(RV_GPL_CODEC_PKGCONFIG_DIRS
    "${_gpl_pkgconfig_dirs}"
    CACHE INTERNAL "pkg-config directories for GPL/BSD codec libraries"
)

SET_PROPERTY(
  GLOBAL APPEND
  PROPERTY "RV_FFMPEG_DEPENDS" RV_DEPS_X264 RV_DEPS_X265 RV_DEPS_LIBVPX RV_DEPS_LIBAOM
)
SET_PROPERTY(
  GLOBAL APPEND
  PROPERTY "RV_FFMPEG_EXTERNAL_LIBS" "--enable-gpl" "--enable-libx264" "--enable-libx265" "--enable-libvpx" "--enable-libaom"
                                     "--pkg-config-flags=--static"
)

MESSAGE(STATUS "GPL/BSD FFmpeg codecs: x264 ${_x264_version}, x265 ${_x265_version}, libvpx ${_vpx_version}, libaom ${_aom_version}")
