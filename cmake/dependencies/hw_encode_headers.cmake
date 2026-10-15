#
# Copyright (C) 2026 Derek Rein. All Rights Reserved.
#
# SPDX-License-Identifier: Apache-2.0
#

# Header-only packages so FFmpeg can compile hardware encoders.
# Neither package is shipped. FFmpeg dlopens the driver at runtime.
#
#   ffnvcodec  MIT   NVENC on Windows and Linux (FFmpeg disables it on macOS)
#   AMF        MIT   AMF on Windows
#
# VideoToolbox is an Apple framework (enabled separately).
# Media Foundation comes with the Windows SDK and is autodetected.
# VAAPI is autodetected on Linux when libva is installed.
# QSV is enabled from ffmpeg.cmake only when libvpl >= 2.6 or libmfx is present.

IF(NOT RV_ENABLE_ALL_CODECS)
  RETURN()
ENDIF()

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

SET(_hw_install_script
    "${CMAKE_CURRENT_LIST_DIR}/install_hw_headers.cmake"
)

# FFmpeg's configure disables NVENC outside Windows and Linux.
IF(RV_TARGET_WINDOWS
   OR RV_TARGET_LINUX
)
  SET(_nv_prefix
      "${RV_DEPS_BASE_DIR}/RV_DEPS_FFNVCODEC/install"
  )
  SET(_nv_source
      "${RV_DEPS_BASE_DIR}/RV_DEPS_FFNVCODEC/src"
  )
  EXTERNALPROJECT_ADD(
    RV_DEPS_FFNVCODEC
    URL "https://github.com/FFmpeg/nv-codec-headers/archive/refs/tags/n12.2.72.0.tar.gz"
    URL_HASH SHA256=dbeaec433d93b850714760282f1d0992b1254fc3b5a6cb7d76fc1340a1e47563
    DOWNLOAD_DIR ${RV_DEPS_DOWNLOAD_DIR}
    DOWNLOAD_EXTRACT_TIMESTAMP TRUE
    SOURCE_DIR ${_nv_source}
    CONFIGURE_COMMAND ""
    BUILD_COMMAND ${CMAKE_COMMAND} -DSOURCE_DIR=${_nv_source} -DPREFIX=${_nv_prefix} -DKIND=nv -P ${_hw_install_script}
    INSTALL_COMMAND ""
    BUILD_BYPRODUCTS "${_nv_prefix}/lib/pkgconfig/ffnvcodec.pc" "${_nv_prefix}/include/ffnvcodec/nvEncodeAPI.h"
  )
  SET_PROPERTY(
    GLOBAL APPEND
    PROPERTY "RV_FFMPEG_DEPENDS" RV_DEPS_FFNVCODEC
  )
  SET_PROPERTY(
    GLOBAL APPEND
    PROPERTY "RV_HW_ENCODE_PKGCONFIG_DIR_LIST" "${_nv_prefix}/lib/pkgconfig"
  )
  MESSAGE(STATUS "NVENC headers: ffnvcodec 12.2.72.0")
ENDIF()

IF(RV_TARGET_WINDOWS)
  SET(_amf_prefix
      "${RV_DEPS_BASE_DIR}/RV_DEPS_AMF_HEADERS/install"
  )
  SET(_amf_source
      "${RV_DEPS_BASE_DIR}/RV_DEPS_AMF_HEADERS/src"
  )
  EXTERNALPROJECT_ADD(
    RV_DEPS_AMF_HEADERS
    URL "https://github.com/GPUOpen-LibrariesAndSDKs/AMF/releases/download/v1.4.36/AMF-headers-v1.4.36.tar.gz"
    URL_HASH SHA256=ec07ee21b820a73f5bae224e92fd3c492f52732d4885f0637f48189afdd87564
    DOWNLOAD_DIR ${RV_DEPS_DOWNLOAD_DIR}
    DOWNLOAD_EXTRACT_TIMESTAMP TRUE
    SOURCE_DIR ${_amf_source}
    CONFIGURE_COMMAND ""
    BUILD_COMMAND ${CMAKE_COMMAND} -DSOURCE_DIR=${_amf_source} -DPREFIX=${_amf_prefix} -DKIND=amf -P ${_hw_install_script}
    INSTALL_COMMAND ""
    BUILD_BYPRODUCTS "${_amf_prefix}/include/AMF/core/Version.h"
  )
  SET_PROPERTY(
    GLOBAL APPEND
    PROPERTY "RV_FFMPEG_DEPENDS" RV_DEPS_AMF_HEADERS
  )
  SET_PROPERTY(
    GLOBAL APPEND
    PROPERTY "RV_FFMPEG_EXTRA_C_OPTIONS" "--extra-cflags=-I${_amf_prefix}/include"
  )
  MESSAGE(STATUS "AMF headers: 1.4.36")
ENDIF()

GET_PROPERTY(
  _hw_pkgconfig_dirs GLOBAL
  PROPERTY "RV_HW_ENCODE_PKGCONFIG_DIR_LIST"
)
IF(_hw_pkgconfig_dirs)
  SET(RV_HW_ENCODE_PKGCONFIG_DIRS
      "${_hw_pkgconfig_dirs}"
      CACHE INTERNAL "pkg-config directories for hardware encoder headers"
  )
ENDIF()
