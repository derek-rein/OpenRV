//
// SPDX-License-Identifier: Apache-2.0
//
#include <MovieR3D/MovieR3D.h>

extern "C"
{

#ifdef PLATFORM_WINDOWS
    __declspec(dllexport) TwkMovie::MovieIO* create();
    __declspec(dllexport) void destroy(TwkMovie::MovieR3DIO*);
#endif

    TwkMovie::MovieIO* create() { return new TwkMovie::MovieR3DIO(); }

    void destroy(TwkMovie::MovieR3DIO* plug) { delete plug; }

} // extern "C"
