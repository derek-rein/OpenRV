//
// SPDX-License-Identifier: Apache-2.0
//
#ifndef __MovieR3D__MovieR3D__h__
#define __MovieR3D__MovieR3D__h__

#include <TwkMovie/MovieIO.h>
#include <TwkMovie/MovieReader.h>
#include <iosfwd>
#include <string>

namespace TwkMovie
{

    class MovieR3D : public MovieReader
    {
    public:
        MovieR3D();
        virtual ~MovieR3D();

        virtual void preloadOpen(const std::string& filename, const ReadRequest& request);
        virtual void postPreloadOpen(const MovieInfo& info = MovieInfo(), const ReadRequest& request = ReadRequest());
        virtual void imagesAtFrame(const ReadRequest& request, FrameBufferVector& fbs);
        virtual void identifiersAtFrame(const ReadRequest& request, IdentifierVector& ids);
        virtual Movie* clone() const;

    private:
        void identifier(int frame, std::ostream& stream);

        void* m_clip;
        std::string m_colorspace;
        int m_pipeline;
    };

    class MovieR3DIO : public MovieIO
    {
    public:
        MovieR3DIO();
        virtual ~MovieR3DIO();

        virtual std::string about() const;
        virtual MovieReader* movieReader() const;
        virtual MovieWriter* movieWriter() const;
    };

} // namespace TwkMovie

#endif
