#
# SPDX-License-Identifier: Apache-2.0
#

INCLUDE(cxx_defaults)

ADD_LIBRARY(PrivateBridgeLoader STATIC load_bridge.cpp)

SET_TARGET_PROPERTIES(
  PrivateBridgeLoader
  PROPERTIES POSITION_INDEPENDENT_CODE ON
)

TARGET_INCLUDE_DIRECTORIES(
  PrivateBridgeLoader
  PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/..
)

TARGET_LINK_LIBRARIES(
  PrivateBridgeLoader
  PUBLIC TwkUtil
)

IF(NOT RV_TARGET_WINDOWS)
  TARGET_LINK_LIBRARIES(
    PrivateBridgeLoader
    PUBLIC ${CMAKE_DL_LIBS}
  )
ENDIF()
