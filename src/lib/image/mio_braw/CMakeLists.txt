#
# SPDX-License-Identifier: Apache-2.0
#

INCLUDE(cxx_defaults)

SET(_target
    "mio_braw"
)

ADD_LIBRARY(
  ${_target} SHARED
  init.cpp
)

TARGET_LINK_LIBRARIES(
  ${_target}
  PRIVATE MovieBraw TwkFB
)

RV_STAGE(TYPE "MOVIE_FORMAT" TARGET ${_target})
