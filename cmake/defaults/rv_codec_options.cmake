#
# Copyright (C) 2026 Derek Rein. All Rights Reserved.
#
# SPDX-License-Identifier: Apache-2.0
#

# Release builds of this fork pass -DRV_ENABLE_ALL_CODECS=ON.
# Default stays OFF so a plain upstream-style configure keeps the
# patent-restricted FFmpeg decoders disabled.
# This fork does not link GPL libraries and does not pass --enable-gpl or --enable-nonfree.
OPTION(RV_ENABLE_ALL_CODECS "Enable every playback decoder that does not need a login-gated SDK" OFF)
OPTION(RV_FFMPEG_DISABLE_ENCODERS "Pass --disable-encoders to FFmpeg (playback-only build)" OFF)

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

# Playback does not advertise or enable encoders. The list stays empty so
# check_codec_options.py can see that the release preset opts out.
SET(_RV_ALL_NONFREE_ENCODERS
    ""
)

IF(RV_ENABLE_ALL_CODECS)
  SET(RV_FFMPEG_DISABLE_ENCODERS
      ON
      CACHE BOOL "Pass --disable-encoders to FFmpeg (playback-only build)" FORCE
  )
  SET(RV_FFMPEG_NON_FREE_DECODERS_TO_ENABLE
      "${_RV_ALL_NONFREE_DECODERS}"
      CACHE STRING "FFmpeg decoders OpenRV otherwise disables" FORCE
  )
  SET(RV_FFMPEG_NON_FREE_ENCODERS_TO_ENABLE
      ""
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
  MESSAGE(STATUS "  encoders disabled: ${RV_FFMPEG_DISABLE_ENCODERS}")
ENDIF()
