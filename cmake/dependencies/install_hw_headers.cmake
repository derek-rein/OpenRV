# Install header-only hardware-encoder SDKs into PREFIX.
# KIND is "nv" (ffnvcodec) or "amf". Nothing here is linked into the app;
# FFmpeg only needs the headers at configure time and dlopens the driver later.

IF(NOT SOURCE_DIR
   OR NOT PREFIX
   OR NOT KIND
)
  MESSAGE(FATAL_ERROR "install_hw_headers.cmake needs SOURCE_DIR, PREFIX, and KIND")
ENDIF()

IF(KIND STREQUAL "nv")
  SET(_include
      ""
  )
  IF(EXISTS "${SOURCE_DIR}/include/ffnvcodec/nvEncodeAPI.h")
    SET(_include
        "${SOURCE_DIR}/include"
    )
  ELSE()
    FILE(GLOB _nested "${SOURCE_DIR}/*/include/ffnvcodec/nvEncodeAPI.h")
    IF(_nested)
      GET_FILENAME_COMPONENT(_include "${_nested}" DIRECTORY)
      GET_FILENAME_COMPONENT(_include "${_include}" DIRECTORY)
    ENDIF()
  ENDIF()
  IF(NOT _include)
    MESSAGE(FATAL_ERROR "ffnvcodec headers not found under ${SOURCE_DIR}")
  ENDIF()
  FILE(COPY "${_include}/" DESTINATION "${PREFIX}/include")
  FILE(MAKE_DIRECTORY "${PREFIX}/lib/pkgconfig")
  FILE(
    WRITE "${PREFIX}/lib/pkgconfig/ffnvcodec.pc"
    "prefix=${PREFIX}\n"
    "includedir=\${prefix}/include\n"
    "\n"
    "Name: ffnvcodec\n"
    "Description: FFmpeg version of Nvidia Codec SDK headers\n"
    "Version: 12.2.72.0\n"
    "Cflags: -I\${includedir}\n"
  )
ELSEIF(KIND STREQUAL "amf")
  SET(_amf
      ""
  )
  IF(EXISTS "${SOURCE_DIR}/AMF/core/Version.h")
    SET(_amf
        "${SOURCE_DIR}/AMF"
    )
  ELSE()
    FILE(GLOB _nested "${SOURCE_DIR}/*/AMF/core/Version.h")
    IF(_nested)
      GET_FILENAME_COMPONENT(_amf "${_nested}" DIRECTORY)
      GET_FILENAME_COMPONENT(_amf "${_amf}" DIRECTORY)
    ENDIF()
  ENDIF()
  IF(NOT _amf)
    MESSAGE(FATAL_ERROR "AMF headers not found under ${SOURCE_DIR}")
  ENDIF()
  FILE(MAKE_DIRECTORY "${PREFIX}/include")
  FILE(COPY "${_amf}" DESTINATION "${PREFIX}/include")
ELSE()
  MESSAGE(FATAL_ERROR "unknown hw header kind ${KIND}")
ENDIF()
