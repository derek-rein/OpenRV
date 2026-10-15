//
// SPDX-License-Identifier: Apache-2.0
//
#include <vendor_bridge/load_bridge.h>

#include <TwkUtil/File.h>

#include <cstring>
#include <vector>

#if defined(_WIN32)
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#include <windows.h>
#else
#include <dlfcn.h>
#endif

namespace RvPrivateCodec
{
    using namespace std;

    namespace
    {

        string parentDir(const string& path)
        {
            const string::size_type pos = path.find_last_of("/\\");
            if (pos == string::npos)
            {
                return string();
            }
            return path.substr(0, pos);
        }

        string joinPath(const string& directory, const string& name)
        {
            if (directory.empty())
            {
                return name;
            }
            const char tail = directory[directory.size() - 1];
            if (tail == '/' || tail == '\\')
            {
                return directory + name;
            }
#ifdef _WIN32
            return directory + "\\" + name;
#else
            return directory + "/" + name;
#endif
        }

        string modulePath()
        {
#if defined(_WIN32)
            HMODULE module = 0;
            if (!GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
                                    reinterpret_cast<LPCSTR>(&modulePath), &module))
            {
                return string();
            }
            char buffer[MAX_PATH];
            const DWORD length = GetModuleFileNameA(module, buffer, MAX_PATH);
            if (length == 0 || length >= MAX_PATH)
            {
                return string();
            }
            return string(buffer, buffer + length);
#else
            Dl_info info;
            memset(&info, 0, sizeof(info));
            if (dladdr(reinterpret_cast<void*>(&modulePath), &info) == 0 || info.dli_fname == 0)
            {
                return string();
            }
            return info.dli_fname;
#endif
        }

        void* openLibrary(const string& path)
        {
#if defined(_WIN32)
            return reinterpret_cast<void*>(LoadLibraryExA(path.c_str(), 0, LOAD_WITH_ALTERED_SEARCH_PATH));
#else
            return dlopen(path.c_str(), RTLD_NOW | RTLD_LOCAL);
#endif
        }

    } // namespace

    void* bridgeSymbol(void* handle, const char* name)
    {
        if (handle == 0 || name == 0)
        {
            return 0;
        }
#if defined(_WIN32)
        return reinterpret_cast<void*>(GetProcAddress(reinterpret_cast<HMODULE>(handle), name));
#else
        return dlsym(handle, name);
#endif
    }

    LoadedBridge loadPrivateBridge(const char* envVar, const char* folderName, const char* libraryName)
    {
        LoadedBridge loaded;
        vector<string> directories;

        if (envVar != 0)
        {
            if (const char* fromEnv = getenv(envVar))
            {
                if (fromEnv[0] != '\0')
                {
                    directories.push_back(fromEnv);
                }
            }
        }

        const string plugin = modulePath();
        const string movieFormats = parentDir(plugin);
        const string plugins = parentDir(movieFormats);
        const string contents = parentDir(plugins);
        if (!contents.empty())
        {
            directories.push_back(joinPath(joinPath(contents, "Frameworks"), folderName));
            directories.push_back(joinPath(joinPath(contents, "MacOS"), folderName));
            directories.push_back(joinPath(joinPath(joinPath(contents, "lib"), "private"), folderName));
            directories.push_back(joinPath(joinPath(contents, "bin"), folderName));
        }

        string found;
        for (size_t i = 0; i < directories.size(); ++i)
        {
            const string candidate = joinPath(directories[i], libraryName);
            if (TwkUtil::fileExists(candidate.c_str()))
            {
                found = candidate;
                loaded.directory = directories[i];
                break;
            }
        }

        if (found.empty())
        {
            loaded.error = "playback runtime is not installed";
            return loaded;
        }

        loaded.handle = openLibrary(found);
        if (loaded.handle == 0)
        {
            loaded.error = "playback runtime failed to load";
            loaded.directory.clear();
        }
        return loaded;
    }

} // namespace RvPrivateCodec
