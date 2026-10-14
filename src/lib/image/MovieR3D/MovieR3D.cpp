//
// SPDX-License-Identifier: Apache-2.0
//
#include <MovieR3D/MovieR3D.h>
#include <TwkFB/Attribute.h>
#include <TwkFB/FrameBuffer.h>
#include <TwkMovie/Exception.h>
#include <r3d_bridge.h>
#include <vendor_bridge/load_bridge.h>

#include <cstdlib>
#include <cstring>
#include <mutex>
#include <sstream>
#include <vector>

namespace TwkMovie
{
    using namespace std;
    using namespace TwkFB;

    namespace
    {

        struct Api
        {
            RvPrivateCodec::LoadedBridge bridge;
            int (*initialize)(const char*);
            void* (*open)(const char*);
            void (*close)(void*);
            int (*clipInfo)(void*, R3DBridgeClipInfo*);
            int (*decode)(void*, uint32_t, int, int, float*, size_t, uint32_t*, uint32_t*);
            const char* (*lastError)();
            bool ready;
            string error;

            Api()
                : initialize(0)
                , open(0)
                , close(0)
                , clipInfo(0)
                , decode(0)
                , lastError(0)
                , ready(false)
            {
            }
        };

        const char* libraryName()
        {
#if defined(_WIN32)
            return "libr3d_bridge.dll";
#elif defined(__APPLE__)
            return "libr3d_bridge.dylib";
#else
            return "libr3d_bridge.so";
#endif
        }

        void loadApi(Api* library)
        {
            library->bridge = RvPrivateCodec::loadPrivateBridge("OPENRV_R3D_RUNTIME", "r3d", libraryName());
            if (library->bridge.handle == 0)
            {
                library->error = library->bridge.error.empty() ? "playback runtime is not installed" : library->bridge.error;
                return;
            }
            library->initialize =
                reinterpret_cast<int (*)(const char*)>(RvPrivateCodec::bridgeSymbol(library->bridge.handle, "r3d_bridge_initialize"));
            library->open = reinterpret_cast<void* (*)(const char*)>(RvPrivateCodec::bridgeSymbol(library->bridge.handle, "r3d_bridge_open"));
            library->close = reinterpret_cast<void (*)(void*)>(RvPrivateCodec::bridgeSymbol(library->bridge.handle, "r3d_bridge_close"));
            library->clipInfo = reinterpret_cast<int (*)(void*, R3DBridgeClipInfo*)>(
                RvPrivateCodec::bridgeSymbol(library->bridge.handle, "r3d_bridge_clip_info"));
            library->decode = reinterpret_cast<int (*)(void*, uint32_t, int, int, float*, size_t, uint32_t*, uint32_t*)>(
                RvPrivateCodec::bridgeSymbol(library->bridge.handle, "r3d_bridge_decode_frame"));
            library->lastError =
                reinterpret_cast<const char* (*)()>(RvPrivateCodec::bridgeSymbol(library->bridge.handle, "r3d_bridge_last_error"));
            if (library->initialize == 0 || library->open == 0 || library->close == 0 || library->clipInfo == 0 || library->decode == 0)
            {
                library->error = "playback runtime is incomplete";
                return;
            }
            if (library->initialize(library->bridge.directory.c_str()) != 0)
            {
                const char* message = library->lastError != 0 ? library->lastError() : 0;
                library->error = (message != 0 && message[0] != '\0') ? message : "playback runtime failed to initialize";
                return;
            }
            library->ready = true;
        }

        const Api& api()
        {
            static Api library;
            static once_flag once;
            call_once(once, loadApi, &library);
            return library;
        }

        int decodeMode(float resolution)
        {
            if (!(resolution > 0.f) || resolution >= 0.9f)
            {
                return R3D_DECODE_FULL_PREMIUM;
            }
            if (resolution >= 0.45f)
            {
                return R3D_DECODE_HALF_PREMIUM;
            }
            if (resolution >= 0.2f)
            {
                return R3D_DECODE_QUARTER_GOOD;
            }
            return R3D_DECODE_EIGHTH_GOOD;
        }

        int pipelineFromEnv()
        {
            const char* value = getenv("OPENRV_R3D_PIPELINE");
            if (value != 0 && strcmp(value, "log3g10") == 0)
            {
                return R3D_PIPELINE_PRIMARY_LOG3G10;
            }
            return R3D_PIPELINE_CLIP_DEFAULT;
        }

        void copyRgb(FrameBuffer& fb, const float* rgb, uint32_t width, uint32_t height)
        {
            const size_t tight = static_cast<size_t>(width) * 3 * sizeof(float);
            unsigned char* dst = fb.pixels<unsigned char>();
            if (fb.scanlineSize() == tight)
            {
                memcpy(dst, rgb, tight * height);
                return;
            }
            for (uint32_t y = 0; y < height; ++y)
            {
                memcpy(dst + static_cast<size_t>(y) * fb.scanlineSize(), rgb + static_cast<size_t>(y) * width * 3, tight);
            }
        }

    } // namespace

    MovieR3D::MovieR3D()
        : MovieReader()
        , m_clip(0)
        , m_pipeline(R3D_PIPELINE_CLIP_DEFAULT)
    {
    }

    MovieR3D::~MovieR3D()
    {
        if (m_clip != 0)
        {
            const Api& library = api();
            if (library.close != 0)
            {
                library.close(m_clip);
            }
            m_clip = 0;
        }
    }

    void MovieR3D::preloadOpen(const string& filename, const ReadRequest& request)
    {
        m_filename = filename;
        m_request = request;
    }

    void MovieR3D::postPreloadOpen(const MovieInfo& info, const ReadRequest& request)
    {
        m_request = request;
        m_pipeline = pipelineFromEnv();
        const Api& library = api();
        if (!library.ready)
        {
            TWK_THROW_STREAM(IOException, "supports R3D files: " << library.error);
        }
        if (m_clip != 0)
        {
            library.close(m_clip);
            m_clip = 0;
        }
        m_clip = library.open(m_filename.c_str());
        if (m_clip == 0)
        {
            const char* message = library.lastError != 0 ? library.lastError() : 0;
            TWK_THROW_STREAM(IOException, "supports R3D files: " << ((message != 0 && message[0] != '\0') ? message : "open failed"));
        }

        R3DBridgeClipInfo clip;
        memset(&clip, 0, sizeof(clip));
        if (library.clipInfo(m_clip, &clip) != 0 || clip.frame_count == 0 || clip.width == 0 || clip.height == 0)
        {
            TWK_THROW_STREAM(IOException, "supports R3D files: unreadable clip");
        }

        m_info = info;
        m_info.start = 1;
        m_info.end = m_info.start + static_cast<int>(clip.frame_count) - 1;
        m_info.inc = 1;
        m_info.fps = clip.fps > 0.f ? clip.fps : 24.f;
        m_info.width = static_cast<int>(clip.width);
        m_info.height = static_cast<int>(clip.height);
        m_info.uncropWidth = m_info.width;
        m_info.uncropHeight = m_info.height;
        m_info.uncropX = 0;
        m_info.uncropY = 0;
        m_info.audio = false;
        m_info.video = true;
        m_info.pixelAspect = 1.0;
        m_info.numChannels = 3;
        m_info.dataType = FrameBuffer::FLOAT;
        m_info.orientation = FrameBuffer::TOPLEFT;
        m_colorspace = clip.colorspace_hint;
    }

    void MovieR3D::imagesAtFrame(const ReadRequest& request, FrameBufferVector& fbs)
    {
        const Api& library = api();
        if (m_clip == 0 || !library.ready)
        {
            TWK_THROW_STREAM(IOException, "supports R3D files: clip is not open");
        }

        int frame = request.frame;
        if (frame < m_info.start)
        {
            frame = m_info.start;
        }
        if (frame > m_info.end)
        {
            frame = m_info.end;
        }
        const uint32_t index = static_cast<uint32_t>(frame - m_info.start);
        uint32_t width = 0;
        uint32_t height = 0;
        const int mode = decodeMode(request.resolution);
        const size_t bytes = static_cast<size_t>(m_info.width) * static_cast<size_t>(m_info.height) * 3 * sizeof(float);
        vector<float> rgb(bytes / sizeof(float));
        if (library.decode(m_clip, index, mode, m_pipeline, rgb.empty() ? 0 : &rgb[0], bytes, &width, &height) != 0 || width == 0
            || height == 0)
        {
            const char* message = library.lastError != 0 ? library.lastError() : 0;
            TWK_THROW_STREAM(IOException, "supports R3D files: " << ((message != 0 && message[0] != '\0') ? message : "decode failed"));
        }
        if (static_cast<size_t>(width) * static_cast<size_t>(height) * 3 > rgb.size())
        {
            TWK_THROW_STREAM(IOException, "supports R3D files: decoded frame is larger than the clip");
        }

        fbs.resize(1);
        if (!fbs.front())
        {
            fbs.front() = new FrameBuffer();
        }
        FrameBuffer& fb = *fbs.front();
        FrameBuffer::StringVector channelNames;
        channelNames.push_back("R");
        channelNames.push_back("G");
        channelNames.push_back("B");
        fb.restructure(static_cast<int>(width), static_cast<int>(height), 0, 3, FrameBuffer::FLOAT, 0, &channelNames, FrameBuffer::TOPLEFT);
        copyRgb(fb, &rgb[0], width, height);
        fb.setIdentifier("");
        identifier(frame, fb.idstream());
        fb.addAttribute(new StringAttribute("File", m_filename));
        if (!m_colorspace.empty())
        {
            fb.addAttribute(new StringAttribute("Colorspace", m_colorspace));
        }
    }

    void MovieR3D::identifiersAtFrame(const ReadRequest& request, IdentifierVector& ids)
    {
        int frame = request.frame;
        ostringstream stream;
        identifier(frame, stream);
        ids.resize(1);
        ids.front() = stream.str();
    }

    void MovieR3D::identifier(int frame, ostream& stream)
    {
        if (frame < m_info.start)
        {
            frame = m_info.start;
        }
        if (frame > m_info.end)
        {
            frame = m_info.end;
        }
        stream << frame << ":" << m_filename;
    }

    Movie* MovieR3D::clone() const
    {
        MovieR3D* copy = new MovieR3D();
        copy->open(m_filename, m_info, m_request);
        return copy;
    }

    MovieR3DIO::MovieR3DIO()
        : MovieIO("MovieR3D", "v1")
    {
        StringPairVector video;
        StringPairVector audio;
        const unsigned int capabilities = MovieIO::MovieRead | MovieIO::AttributeRead;
        addType("r3d", "supports R3D files", capabilities, video, audio);
    }

    MovieR3DIO::~MovieR3DIO() {}

    string MovieR3DIO::about() const { return "supports R3D files"; }

    MovieReader* MovieR3DIO::movieReader() const { return new MovieR3D(); }

    MovieWriter* MovieR3DIO::movieWriter() const { return 0; }

} // namespace TwkMovie
