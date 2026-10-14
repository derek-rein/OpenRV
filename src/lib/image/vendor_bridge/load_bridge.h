//
// SPDX-License-Identifier: Apache-2.0
//
#ifndef __OpenRV__LoadBridge__h__
#define __OpenRV__LoadBridge__h__

#include <string>

namespace RvPrivateCodec
{

    // Locate and dlopen a playback bridge that was staged next to the app.
    // directory is the folder that also holds the vendor dynamic libraries.
    struct LoadedBridge
    {
        void* handle;
        std::string directory;
        std::string error;

        LoadedBridge()
            : handle(0)
        {
        }
    };

    LoadedBridge loadPrivateBridge(const char* envVar, const char* folderName, const char* libraryName);

    void* bridgeSymbol(void* handle, const char* name);

} // namespace RvPrivateCodec

#endif
