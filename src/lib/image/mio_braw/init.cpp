//
// SPDX-License-Identifier: Apache-2.0
//
#include <MovieBraw/MovieBraw.h>

extern "C"
{

#ifdef PLATFORM_WINDOWS
    __declspec(dllexport) TwkMovie::MovieIO* create();
    __declspec(dllexport) void destroy(TwkMovie::MovieBrawIO*);
#endif

    TwkMovie::MovieIO* create() { return new TwkMovie::MovieBrawIO(); }

    void destroy(TwkMovie::MovieBrawIO* plug) { delete plug; }

} // extern "C"
