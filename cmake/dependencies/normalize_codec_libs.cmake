# Copy MSVC static-lib names onto the basename pkg-config's -l flag searches for.
# Invoked as: cmake -DPREFIX=<install> -P normalize_codec_libs.cmake
# Missing inputs are ignored so Unix installs (lib*.a already named correctly) no-op.

IF(NOT PREFIX)
  RETURN()
ENDIF()

FUNCTION(_rv_alias source dest)
  IF(EXISTS "${source}"
     AND NOT EXISTS "${dest}"
  )
    GET_FILENAME_COMPONENT(_dest_dir "${dest}" DIRECTORY)
    FILE(MAKE_DIRECTORY "${_dest_dir}")
    FILE(COPY_FILE "${source}" "${dest}")
    MESSAGE(STATUS "Codec lib alias ${source} -> ${dest}")
  ENDIF()
ENDFUNCTION()

_rv_alias("${PREFIX}/lib/libaom.lib" "${PREFIX}/lib/aom.lib")
_rv_alias("${PREFIX}/lib/Release/aom.lib" "${PREFIX}/lib/aom.lib")
_rv_alias("${PREFIX}/lib/libvpx.lib" "${PREFIX}/lib/vpx.lib")
_rv_alias("${PREFIX}/x64/Release/vpx.lib" "${PREFIX}/lib/vpx.lib")
_rv_alias("${PREFIX}/Release/vpx.lib" "${PREFIX}/lib/vpx.lib")
