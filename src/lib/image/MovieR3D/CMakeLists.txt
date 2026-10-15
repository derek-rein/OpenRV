#
# SPDX-License-Identifier: Apache-2.0
#

INCLUDE(cxx_defaults)

SET(_target
    "MovieR3D"
)

ADD_LIBRARY(
  ${_target} STATIC
  MovieR3D.cpp
)

SET_TARGET_PROPERTIES(
  ${_target}
  PROPERTIES POSITION_INDEPENDENT_CODE ON
)

TARGET_INCLUDE_DIRECTORIES(
  ${_target}
  PUBLIC ${CMAKE_CURRENT_SOURCE_DIR} ${CMAKE_CURRENT_SOURCE_DIR}/../vendor_bridge/r3d ${CMAKE_CURRENT_SOURCE_DIR}/..
)

TARGET_LINK_LIBRARIES(
  ${_target}
  PUBLIC TwkMovie TwkFB PrivateBridgeLoader
  PRIVATE TwkUtil
)
