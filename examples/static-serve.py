#!/usr/bin/env python2.4
"""static - A stupidly simple WSGI way to serve static (or mixed) content.

(See the docstrings of the various functions and classes.)

Copyright (C) 2006 Luke Arno - http://lukearno.com/

This program is free software; you can redistribute it and/or modify 
it under the terms of the GNU General Public License as published by the 
Free Software Foundation; either version 2 of the License, or (at your 
option) any later version.

This program is distributed in the hope that it will be useful, but 
WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU 
General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program; if not, write to:

The Free Software Foundation, Inc., 
51 Franklin Street, Fifth Floor, 
Boston, MA  02110-1301, USA.

Luke Arno can be found at http://lukearno.com/

"""

import mimetypes
import rfc822
import time
import string
import os


from wsgiref import util


class StatusApp:
    """A WSGI app that just returns the given status."""
    
    def __init__(self, status, message=None):
        self.status = status
        if message is None:
            self.message = status
        else:
            self.message = message
        
    def __call__(self, environ, start_response, headers=[]):
        start_response(self.status, headers)
        if environ['REQUEST_METHOD'] == 'GET':
            return [self.message]
        else:
            return [""]
            
def generate_xhtml(path, dirs, files):
    """Return a XHTML document listing the directories and files."""
    # Prepare the path to display.
    if path != '/':
        dirs.insert(0, '..')
    if not path.endswith('/'):
        path += '/'

    def itemize(item):
        return '<a href="%s">%s</a>' % (item, path+item)
    dirs = [d + '/' for d in dirs]
    return """
    <html>
     <body>
      <h1>%s</h1>
       <pre>%s\n%s</pre>
     </body>
    </html>
    """ % (path, '\n'.join(itemize(dir) for dir in dirs), '\n'.join(itemize(file) for file in files))
    
def get_entries(path):
    """Return sorted lists of directories and files in the given path."""
    dirs, files = [], []
    for entry in os.listdir(path):
        # Categorize entry as directory or file.
        if os.path.isdir(os.path.join(path, entry)):
            dirs.append(entry)
        else:
            files.append(entry)
    dirs.sort()
    files.sort()
    return dirs, files
    
class Static(object):
    """A stupidly simple way to serve static content via WSGI.
    
    Serve the file of the same path as PATH_INFO in self.datadir.
    
    Look up the Content-type in self.content_types by extension
    or use 'text/plain' if the extension is not found.

    Serve up the contents of the file or delegate to self.not_found.
    """

    block_size = 16 * 4096
    index_file = 'index.html'
    not_found = StatusApp('404 Not Found')
    not_modified = StatusApp('304 Not Modified', "")
    moved_permanently = StatusApp('301 Moved Permanently')
    method_not_allowed = StatusApp('405 Method Not Allowed')

    def __init__(self, root, **kw):
        """Just set the root and any other attribs passes via **kw."""
        self.root = root
        for k, v in kw.iteritems():
            setattr(self, k, v)

    def __call__(self, environ, start_response):
        """Respond to a request when called in the usual WSGI way."""
        if environ['REQUEST_METHOD'] not in ('GET', 'HEAD'):
            return self.method_not_allowed(environ, start_response)
        path_info = environ.get('PATH_INFO', '')
        full_path = self._full_path(path_info)
        # guard against arbitrary file retrieval
        if not (os.path.abspath(full_path+'/'))\
               .startswith(os.path.abspath(self.root+'/')):
            return self.not_found(environ, start_response)
        if os.path.isdir(full_path):
            if full_path[-1] <> '/' or full_path == self.root:
                location = util.request_uri(environ, include_query=False) + '/'
                if environ.get('QUERY_STRING'):
                    location += '?' + environ.get('QUERY_STRING')
                headers = [('Location', location)]
                return self.moved_permanently(environ, start_response, headers)
            else:
                headers = [('Date', rfc822.formatdate(time.time()))]
                headers.append(('Content-Type', 'text/html' ))
                start_response("200 OK", headers)
                if environ['REQUEST_METHOD'] == 'GET':
                    return [generate_xhtml(path_info, *get_entries(full_path))]
        content_type = self._guess_type(full_path)
        try:
            etag, last_modified, length = self._conditions(full_path, environ)
            headers = [('Date', rfc822.formatdate(time.time())),
                       ('Last-Modified', last_modified),
                       ('ETag', etag),
                       ('Content-Length', str(length))]
            if_modified = environ.get('HTTP_IF_MODIFIED_SINCE')
            if if_modified and (rfc822.parsedate(if_modified)
                                >= rfc822.parsedate(last_modified)):
                return self.not_modified(environ, start_response, headers)
            if_none = environ.get('HTTP_IF_NONE_MATCH')
            if if_none and (if_none == '*' or etag in if_none):
                return self.not_modified(environ, start_response, headers)
            file_like = self._file_like(full_path)
            headers.append(('Content-Type', content_type))
            start_response("200 OK", headers)
            if environ['REQUEST_METHOD'] == 'GET':
                return self._body(full_path, environ, file_like)
            else:
                return ['']
        except (IOError, OSError), e:
            return self.not_found(environ, start_response)

    def _full_path(self, path_info):
        """Return the full path from which to read."""
        return self.root + path_info

    def _guess_type(self, full_path):
        """Guess the mime type using the mimetypes module."""
        return mimetypes.guess_type(full_path)[0] or 'text/plain'

    def _conditions(self, full_path, environ):
        """Return a tuple of etag, last_modified by mtime from stat."""
        mtime = os.stat(full_path).st_mtime
        size = os.stat(full_path).st_size
        return str(mtime), rfc822.formatdate(mtime), size

    def _file_like(self, full_path):
        """Return the appropriate file object."""
        return open(full_path, 'rb')

    def _body(self, full_path, environ, file_like):
        """Return an iterator over the body of the response."""
        way_to_send = environ.get('wsgi.file_wrapper', iter_and_close)
        return way_to_send(file_like, self.block_size)


def iter_and_close(file_like, block_size):
    """Yield file contents by block then close the file."""
    while 1:
        try:
            block = file_like.read(block_size)
            if block: yield block
            else: raise StopIteration
        except StopIteration, si:
            file_like.close()
            return 

from cogen.web import wsgi
from cogen.common import *
wsgi.server_factory({}, '0.0.0.0', 9000)(Static('.'))


#~ from wsgiref.simple_server import make_server
#make_server('localhost', 9000, debug).serve_forever()
#~ make_server('localhost', 9000, app).serve_forever()