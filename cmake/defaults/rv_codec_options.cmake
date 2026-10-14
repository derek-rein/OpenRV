#
# Copyright (C) 2026 Derek Rein. All Rights Reserved.
#
# SPDX-License-Identifier: Apache-2.0
#

# Release builds of this fork pass -DRV_ENABLE_ALL_CODECS=ON.
# Default stays OFF so a plain upstream-style configure keeps the
# patent-restricted FFmpeg decoders disabled and does not link GPL libraries.
OPTION(RV_ENABLE_ALL_CODECS "Enable every codec switch that does not need a login-gated SDK" OFF)
OPTION(RV_FFMPEG_ENABLE_GPL "Build FFmpeg with --enable-gpl and link x264, x265, libvpx, and libaom" OFF)

# Names match cmake/dependencies/ffmpeg.cmake (NON_FREE_*_TO_DISABLE) plus the
# application-level gates in src/lib/image/mio_ffmpeg/init.cpp. Anything in the
# decoder list becomes -D__FFMPEG_ENABLE_NON_FREE_DECODER_<name> on mio_ffmpeg.
SET(_RV_ALL_NONFREE_DECODERS
    "aac"
    "aac_at"
    "aac_fixed"
    "aac_latm"
    "ac3"
    "ac3_fixed"
    "eac3"
    "bink"
    "binkaudio_dct"
    "binkaudio_rdft"
    "dnxhd"
    "dvvideo"
    "hevc"
    "mpeg2video"
    "prores"
    "prores_raw"
    "prores_aw"
    "prores_ks"
    "prores_lgpl"
    "qtrle"
    "svq1"
    "svq3"
    "vp9"
    "vp9_cuvid"
    "vp9_mediacodec"
    "vp9_qsv"
    "vp9_rkmpp"
    "vp9_v4l2m2m"
)

SET(_RV_ALL_NONFREE_ENCODERS
    "aac"
    "aac_mf"
    "dnxhd"
    "dvvideo"
    "prores"
    "qtrle"
    "vp9_qsv"
    "vp9_vaapi"
)

IF(RV_ENABLE_ALL_CODECS)
  SET(RV_FFMPEG_ENABLE_GPL
      ON
      CACHE BOOL "Build FFmpeg with --enable-gpl and link x264, x265, libvpx, and libaom" FORCE
  )
  SET(RV_FFMPEG_NON_FREE_DECODERS_TO_ENABLE
      "${_RV_ALL_NONFREE_DECODERS}"
      CACHE STRING "FFmpeg decoders OpenRV otherwise disables" FORCE
  )
  SET(RV_FFMPEG_NON_FREE_ENCODERS_TO_ENABLE
      "${_RV_ALL_NONFREE_ENCODERS}"
      CACHE STRING "FFmpeg encoders OpenRV otherwise disables" FORCE
  )
  # VideoToolbox is an Apple framework. Forcing it ON on other platforms does nothing useful.
  IF(APPLE)
    SET(RV_FFMPEG_USE_VIDEOTOOLBOX
        ON
        CACHE BOOL "FFmpeg leveraging the VideoToolbox framework" FORCE
    )
  ENDIF()
  MESSAGE(STATUS "RV_ENABLE_ALL_CODECS=ON")
  MESSAGE(STATUS "  non-free decoders: ${RV_FFMPEG_NON_FREE_DECODERS_TO_ENABLE}")
  MESSAGE(STATUS "  non-free encoders: ${RV_FFMPEG_NON_FREE_ENCODERS_TO_ENABLE}")
  MESSAGE(STATUS "  GPL external codecs (x264, x265, libvpx, libaom): ${RV_FFMPEG_ENABLE_GPL}")
ENDIF()
