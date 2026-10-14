#
# SPDX-License-Identifier: Apache-2.0
#

INCLUDE(cxx_defaults)

SET(_target
    "mio_r3d"
)

ADD_LIBRARY(
  ${_target} SHARED
  init.cpp
)

TARGET_LINK_LIBRARIES(
  ${_target}
  PRIVATE MovieR3D TwkFB
)

RV_STAGE(TYPE "MOVIE_FORMAT" TARGET ${_target})
