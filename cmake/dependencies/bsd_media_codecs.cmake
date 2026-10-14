#
# Copyright (C) 2026 Derek Rein. All Rights Reserved.
#
# SPDX-License-Identifier: Apache-2.0
#

# Static BSD codec libraries linked into the release FFmpeg build.
# libvpx is BSD. libaom is BSD-2-Clause. Neither needs --enable-gpl.
# libaom is built as an encoder only; AV1 decode stays on dav1d.
# x264 and x265 are not built.

IF(NOT RV_ENABLE_ALL_CODECS)
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

PROCESSORCOUNT(_bsd_cpu_count)
IF(_bsd_cpu_count EQUAL 0)
  SET(_bsd_cpu_count
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
    PROPERTY "RV_BSD_CODEC_PKGCONFIG_DIR_LIST" "${prefix}/lib/pkgconfig"
  )
ENDFUNCTION()

IF(WIN32)
  SET(_bsd_pthread_libs
      ""
  )
ELSE()
  SET(_bsd_pthread_libs
      "-lpthread -lm"
  )
ENDIF()

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
  SET(_vpx_target_args
      --target=x86_64-win64-vs17
  )
ELSE()
  SET(_vpx_target_args
      ""
  )
ENDIF()
_rv_write_pc("${_vpx_prefix}" "vpx" "${_vpx_version}" "${_bsd_pthread_libs}")
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
  BUILD_COMMAND make -j${_bsd_cpu_count}
  INSTALL_COMMAND make install COMMAND ${CMAKE_COMMAND} -DPREFIX=${_vpx_prefix} -P ${CMAKE_CURRENT_LIST_DIR}/normalize_codec_libs.cmake
  BUILD_BYPRODUCTS "${_vpx_prefix}/lib/libvpx.a" "${_vpx_prefix}/lib/vpx.lib"
  USES_TERMINAL_BUILD TRUE
)

# --- libaom (AV1 encoder, BSD-2-Clause). Decoder stays off so dav1d remains the AV1 decoder. ---
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
_rv_write_pc("${_aom_prefix}" "aom" "${_aom_version}" "${_bsd_pthread_libs}")
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
  BUILD_COMMAND ${CMAKE_COMMAND} --build ${RV_DEPS_BASE_DIR}/RV_DEPS_LIBAOM/build --config ${CMAKE_BUILD_TYPE} --parallel ${_bsd_cpu_count}
  INSTALL_COMMAND ${CMAKE_COMMAND} --install ${RV_DEPS_BASE_DIR}/RV_DEPS_LIBAOM/build --config ${CMAKE_BUILD_TYPE} --prefix ${_aom_prefix}
                  COMMAND ${CMAKE_COMMAND} -DPREFIX=${_aom_prefix} -P ${CMAKE_CURRENT_LIST_DIR}/normalize_codec_libs.cmake
  BUILD_BYPRODUCTS "${_aom_prefix}/lib/libaom.a" "${_aom_prefix}/lib/aom.lib"
  USES_TERMINAL_BUILD TRUE
)

GET_PROPERTY(
  _bsd_pkgconfig_dirs GLOBAL
  PROPERTY "RV_BSD_CODEC_PKGCONFIG_DIR_LIST"
)
SET(RV_BSD_CODEC_PKGCONFIG_DIRS
    "${_bsd_pkgconfig_dirs}"
    CACHE INTERNAL "pkg-config directories for BSD codec libraries"
)

SET_PROPERTY(
  GLOBAL APPEND
  PROPERTY "RV_FFMPEG_DEPENDS" RV_DEPS_LIBVPX RV_DEPS_LIBAOM
)
SET_PROPERTY(
  GLOBAL APPEND
  PROPERTY "RV_FFMPEG_EXTERNAL_LIBS" "--enable-libvpx" "--enable-libaom" "--pkg-config-flags=--static"
)

MESSAGE(STATUS "BSD FFmpeg encoders: libvpx ${_vpx_version}, libaom ${_aom_version}")
