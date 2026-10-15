//
// SPDX-License-Identifier: Apache-2.0
//
#ifndef __MovieBraw__MovieBraw__h__
#define __MovieBraw__MovieBraw__h__

#include <TwkMovie/MovieIO.h>
#include <TwkMovie/MovieReader.h>
#include <iosfwd>
#include <string>

namespace TwkMovie
{

    class MovieBraw : public MovieReader
    {
    public:
        MovieBraw();
        virtual ~MovieBraw();

        virtual void preloadOpen(const std::string& filename, const ReadRequest& request);
        virtual void postPreloadOpen(const MovieInfo& info = MovieInfo(), const ReadRequest& request = ReadRequest());
        virtual void imagesAtFrame(const ReadRequest& request, FrameBufferVector& fbs);
        virtual void identifiersAtFrame(const ReadRequest& request, IdentifierVector& ids);
        virtual Movie* clone() const;

    private:
        void identifier(int frame, std::ostream& stream);

        void* m_clip;
        std::string m_colorspace;
    };

    class MovieBrawIO : public MovieIO
    {
    public:
        MovieBrawIO();
        virtual ~MovieBrawIO();

        virtual std::string about() const;
        virtual MovieReader* movieReader() const;
        virtual MovieWriter* movieWriter() const;
    };

} // namespace TwkMovie

#endif
