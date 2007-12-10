"""
HTTP protocol handling code taken from the CherryPy wsgi server.
Refactored to fit my coroutine architecture.
"""
from __future__ import with_statement
__all__ = ['WSGIFileWrapper','WSGIServer','WSGIConnection']
from contextlib import closing

import base64
import Queue
import os
import re
import rfc822
import socket
import errno
try:                
    import cStringIO as StringIO
except ImportError: 
    import StringIO
import sys
import time
import traceback
from urllib import unquote
from urlparse import urlparse
from traceback import format_exc
import cogen
from cogen.common import *
quoted_slash = re.compile("(?i)%2F")
useless_socket_errors = {}
for _ in ("EPIPE", "ETIMEDOUT", "ECONNREFUSED", "ECONNRESET",
          "EHOSTDOWN", "EHOSTUNREACH",
          "WSAECONNABORTED", "WSAECONNREFUSED", "WSAECONNRESET",
          "WSAENETRESET", "WSAETIMEDOUT"):
    if _ in dir(errno):
        useless_socket_errors[getattr(errno, _)] = None
useless_socket_errors = useless_socket_errors.keys()
comma_separated_headers = ['ACCEPT', 'ACCEPT-CHARSET', 'ACCEPT-ENCODING',
    'ACCEPT-LANGUAGE', 'ACCEPT-RANGES', 'ALLOW', 'CACHE-CONTROL',
    'CONNECTION', 'CONTENT-ENCODING', 'CONTENT-LANGUAGE', 'EXPECT',
    'IF-MATCH', 'IF-NONE-MATCH', 'PRAGMA', 'PROXY-AUTHENTICATE', 'TE',
    'TRAILER', 'TRANSFER-ENCODING', 'UPGRADE', 'VARY', 'VIA', 'WARNING',
    'WWW-AUTHENTICATE']

class WSGIFileWrapper:
    def __init__(self, filelike, bloksize=8192):
        self.filelike = filelike
        self.bloksize = bloksize
        if hasattr(filelike,'close'):
            self.close = filelike.close    
            
class debugging(object):
    def __init__(self, thing):
        self.thing = thing
    def __enter__(self):
        return self.thing
    def __exit__(self, *exc_info):
        print 'Closing', self.thing.no
        
class WSGIConnection(object):
    connection_environ = {
        "wsgi.version": (1, 0),
        "wsgi.url_scheme": "http",
        "wsgi.multithread": True,
        "wsgi.multiprocess": False,
        "wsgi.run_once": False,
        "wsgi.errors": sys.stderr,
        "wsgi.input": StringIO.StringIO(),
       #~ "wsgi.file_wrapper": WSGIFileWrapper,
    }
    
    def __init__(t, sock, wsgi_app, environ):
        t.conn = sock
        t.wsgi_app = wsgi_app
        t.server_environ = environ
        
    def start_response(t, status, headers, exc_info = None):
        """WSGI callable to begin the HTTP response."""
        if t.started_response:
            if not exc_info:
                raise AssertionError("WSGI start_response called a second "
                                     "time with no exc_info.")
            else:
                try:
                    raise exc_info[0], exc_info[1], exc_info[2]
                finally:
                    exc_info = None
        t.started_response = True
        t.status = status
        t.outheaders.extend(headers)
        
        return t.write_buffer.write
            
    def render_headers(t):
        hkeys = [key.lower() for key, value in t.outheaders]
        status = int(t.status[:3])
        
        if status == 413:
            # Request Entity Too Large. Close conn to avoid garbage.
            t.close_connection = True
        elif "content-length" not in hkeys:
            # "All 1xx (informational), 204 (no content),
            # and 304 (not modified) responses MUST NOT
            # include a message-body." So no point chunking.
            if status < 200 or status in (204, 205, 304):
                pass
            else:
                if t.response_protocol == 'HTTP/1.1':
                    # Use the chunked transfer-coding
                    t.chunked_write = True
                    t.outheaders.append(("Transfer-Encoding", "chunked"))
                else:
                    # Closing the conn is the only way to determine len.
                    t.close_connection = True
        
        if "connection" not in hkeys:
            if t.response_protocol == 'HTTP/1.1':
                if t.close_connection:
                    t.outheaders.append(("Connection", "close"))
            else:
                if not t.close_connection:
                    t.outheaders.append(("Connection", "Keep-Alive"))
        
        if "date" not in hkeys:
            t.outheaders.append(("Date", rfc822.formatdate()))
        
        if "server" not in hkeys:
            t.outheaders.append(("Server", t.environ['SERVER_SOFTWARE']))
        
        buf = [t.environ['ACTUAL_SERVER_PROTOCOL'], " ", t.status, "\r\n"]
        try:
            buf += [k + ": " + v + "\r\n" for k, v in t.outheaders]
        except TypeError:
            if not isinstance(k, str):
                raise TypeError("WSGI response header key %r is not a string.")
            if not isinstance(v, str):
                raise TypeError("WSGI response header value %r is not a string.")
            else:
                raise
        buf.append("\r\n")
        return "".join(buf)

    def simple_response(t, status, msg=""):
        """Write a simple response back to the client."""
        status = str(status)
        buf = ["%s %s\r\n" % (t.environ['ACTUAL_SERVER_PROTOCOL'], status),
               "Content-Length: %s\r\n" % len(msg),
               "Content-Type: text/plain\r\n"]
        
        if status[:3] == "413" and t.response_protocol == 'HTTP/1.1':
            # Request Entity Too Large
            t.close_connection = True
            buf.append("Connection: close\r\n")
        
        buf.append("\r\n")
        if msg:
            buf.append(msg)
        return sockets.WriteAll(t.conn, "".join(buf))
        
    @coroutine
    #~ @cogen.core.schedulers.debug(0, lambda f,a,k:a[0].no)
    def run(t):
       #~ print 'Running', t.no
       #~ with debugging(t):
        t.close_connection = False
        with closing(t.conn):
            try:
                while True:
                    t.started_response = False
                    t.status = ""
                    t.outheaders = []
                    t.sent_headers = False
                    t.chunked_write = False
                    t.write_buffer = StringIO.StringIO()
                    # Copy the class environ into self.
                    environ = t.environ = t.connection_environ.copy()
                    environ.update(t.server_environ)
                            
                    request_line = yield sockets.ReadLine(t.conn)
                    if request_line == "\r\n":
                        # RFC 2616 sec 4.1: "... it should ignore the CRLF."
                        tolerance = 5
                        while tolerance and request_line == "\r\n":
                            request_line = yield sockets.ReadLine(t.conn)
                            tolerance -= 1
                        if not tolerance:
                            return
                    method, path, req_protocol = request_line.strip().split(" ", 2)
                    environ["REQUEST_METHOD"] = method
                    environ["CONTENT_LENGTH"] = ''
                    
                    scheme, location, path, params, qs, frag = urlparse(path)
                    
                    if frag:
                        yield t.simple_response("400 Bad Request",
                                                "Illegal #fragment in Request-URI.")
                        return
                    
                    if scheme:
                        environ["wsgi.url_scheme"] = scheme
                    if params:
                        path = path + ";" + params
                    
                    environ["SCRIPT_NAME"] = ""
                    
                    # Unquote the path+params (e.g. "/this%20path" -> "this path").
                    # http://www.w3.org/Protocols/rfc2616/rfc2616-sec5.html#sec5.1.2
                    #
                    # But note that "...a URI must be separated into its components
                    # before the escaped characters within those components can be
                    # safely decoded." http://www.ietf.org/rfc/rfc2396.txt, sec 2.4.2
                    atoms = [unquote(x) for x in quoted_slash.split(path)]
                    path = "%2F".join(atoms)
                    environ["PATH_INFO"] = path
                    
                    # Note that, like wsgiref and most other WSGI servers,
                    # we unquote the path but not the query string.
                    environ["QUERY_STRING"] = qs
                    
                    # Compare request and server HTTP protocol versions, in case our
                    # server does not support the requested protocol. Limit our output
                    # to min(req, server). We want the following output:
                    #     request    server     actual written   supported response
                    #     protocol   protocol  response protocol    feature set
                    # a     1.0        1.0           1.0                1.0
                    # b     1.0        1.1           1.1                1.0
                    # c     1.1        1.0           1.0                1.0
                    # d     1.1        1.1           1.1                1.1
                    # Notice that, in (b), the response will be "HTTP/1.1" even though
                    # the client only understands 1.0. RFC 2616 10.5.6 says we should
                    # only return 505 if the _major_ version is different.
                    rp = int(req_protocol[5]), int(req_protocol[7])
                    server_protocol = environ["ACTUAL_SERVER_PROTOCOL"]
                    sp = int(server_protocol[5]), int(server_protocol[7])
                    if sp[0] != rp[0]:
                        yield t.simple_response("505 HTTP Version Not Supported")
                        return
                    # Bah. "SERVER_PROTOCOL" is actually the REQUEST protocol.
                    environ["SERVER_PROTOCOL"] = req_protocol
                    t.response_protocol = "HTTP/%s.%s" % min(rp, sp)
                    
                    # If the Request-URI was an absoluteURI, use its location atom.
                    if location:
                        environ["SERVER_NAME"] = location
                    
                    # then all the http headers
                    try:
                        while True:
                            line = yield sockets.ReadLine(t.conn)
                            
                            if line == '\r\n':
                                # Normal end of headers
                                break
                            
                            if line[0] in ' \t':
                                # It's a continuation line.
                                v = line.strip()
                            else:
                                k, v = line.split(":", 1)
                                k, v = k.strip().upper(), v.strip()
                                envname = "HTTP_" + k.replace("-", "_")
                            
                            if k in comma_separated_headers:
                                existing = environ.get(envname)
                                if existing:
                                    v = ", ".join((existing, v))
                            environ[envname] = v
                        
                        ct = environ.pop("HTTP_CONTENT_TYPE", None)
                        if ct:
                            environ["CONTENT_TYPE"] = ct
                        cl = environ.pop("HTTP_CONTENT_LENGTH", None)
                        if cl:
                            environ["CONTENT_LENGTH"] = cl
                    except ValueError, ex:
                        yield t.simple_response("400 Bad Request", repr(ex.args))
                        return
                    
                    creds = environ.get("HTTP_AUTHORIZATION", "").split(" ", 1)
                    environ["AUTH_TYPE"] = creds[0]
                    if creds[0].lower() == 'basic':
                        user, pw = base64.decodestring(creds[1]).split(":", 1)
                        environ["REMOTE_USER"] = user
                    
                    # Persistent connection support
                    if t.response_protocol == "HTTP/1.1":
                        if environ.get("HTTP_CONNECTION", "") == "close":
                            t.close_connection = True
                    else:
                        # HTTP/1.0
                        if environ.get("HTTP_CONNECTION", "") != "Keep-Alive":
                            t.close_connection = True
                    
                    # Transfer-Encoding support
                    te = None
                    if t.response_protocol == "HTTP/1.1":
                        te = environ.get("HTTP_TRANSFER_ENCODING")
                        if te:
                            te = [x.strip().lower() for x in te.split(",") if x.strip()]
                    
                    read_chunked = False
                    
                    if te:
                        for enc in te:
                            if enc == "chunked":
                                read_chunked = True
                            else:
                                # Note that, even if we see "chunked", we must reject
                                # if there is an extension we don't recognize.
                                yield t.simple_response("501 Unimplemented")
                                t.close_connection = True
                                return
                    
                    if read_chunked:
                        """Decode the 'chunked' transfer coding."""
                        cl = 0
                        data = StringIO.StringIO()
                        while True:
                            line = (yield sockets.ReadLine(t.conn)).strip().split(";", 1)
                            chunk_size = int(line.pop(0), 16)
                            if chunk_size <= 0:
                                break
                            cl += chunk_size
                            data.write((yield sockets.ReadAll(t.conn,chunk_size)))
                            crlf = (yield sockets.ReadAll(t.conn,2))
                            if crlf != "\r\n":
                                yield t.simple_response("400 Bad Request",
                                                     "Bad chunked transfer coding "
                                                     "(expected '\\r\\n', got %r)" % crlf)
                                return
                        
                        # Grab any trailer headers
                        while True:
                            line = yield sockets.ReadLine(t.conn)
                            
                            if line == '\r\n':
                                # Normal end of headers
                                break
                            
                            if line[0] in ' \t':
                                # It's a continuation line.
                                v = line.strip()
                            else:
                                k, v = line.split(":", 1)
                                k, v = k.strip().upper(), v.strip()
                                envname = "HTTP_" + k.replace("-", "_")
                            
                            if k in comma_separated_headers:
                                existing = environ.get(envname)
                                if existing:
                                    v = ", ".join((existing, v))
                            environ[envname] = v
                        
                        ct = environ.pop("HTTP_CONTENT_TYPE", None)
                        if ct:
                            environ["CONTENT_TYPE"] = ct
                        cl = environ.pop("HTTP_CONTENT_LENGTH", None)
                        if cl:
                            environ["CONTENT_LENGTH"] = cl

                        
                        data.seek(0)
                        environ["wsgi.input"] = data
                        environ["CONTENT_LENGTH"] = str(cl) or ""
                        
                        
                    # From PEP 333:
                    # "Servers and gateways that implement HTTP 1.1 must provide
                    # transparent support for HTTP 1.1's "expect/continue" mechanism.
                    # This may be done in any of several ways:
                    #   1. Respond to requests containing an Expect: 100-continue request
                    #      with an immediate "100 Continue" response, and proceed normally.
                    #   2. Proceed with the request normally, but provide the application
                    #      with a wsgi.input stream that will send the "100 Continue"
                    #      response if/when the application first attempts to read from
                    #      the input stream. The read request must then remain blocked
                    #      until the client responds.
                    #   3. Wait until the client decides that the server does not support
                    #      expect/continue, and sends the request body on its own.
                    #      (This is suboptimal, and is not recommended.)
                    #
                    # We used to do 3, but are now doing 1. Maybe we'll do 2 someday,
                    # but it seems like it would be a big slowdown for such a rare case.
                    if environ.get("HTTP_EXPECT", "") == "100-continue":
                        yield sockets.WriteAll("HTTP/1.1 100 Continue\r\n\r\n")
                        
                    # If request has Content-Length, read its data
                    if not environ.get("wsgi.input", None) and environ["CONTENT_LENGTH"]:
                        postdata = yield sockets.ReadAll(t.conn, int(environ["CONTENT_LENGTH"]))
                        environ["wsgi.input"] = StringIO(postdata)
                        
                    response = t.wsgi_app(environ, t.start_response)
                    try:
                        if not t.sent_headers:
                            yield sockets.WriteAll(t.conn, t.render_headers())

                        write_data = t.write_buffer.getvalue()
                        if write_data:
                            yield sockets.WriteAll(t.conn, write_data)
                            
                        if isinstance(response, WSGIFileWrapper):
                            yield sockets.SendFile(response.filelike, t.conn, 0, blocksize=response.blocksize)
                        else:
                            for chunk in response:
                                if t.chunked_write and chunk:
                                    buf = [hex(len(chunk))[2:], "\r\n", chunk, "\r\n"]
                                    yield sockets.WriteAll(t.conn, "".join(buf))
                                else:
                                    yield sockets.WriteAll(t.conn, chunk)
                    finally:
                        if hasattr(response, 'close'): response.close()

                    if t.chunked_write:
                        yield sockets.WriteAll(t.conn, "0\r\n\r\n")
                
                    if t.close_connection:
                        return
            except socket.error, e:
                errno = e.args[0]
                if errno not in useless_socket_errors:
                    yield t.simple_response("500 Internal Server Error",
                                            format_exc())
                return
            except (events.OperationTimeout, events.ConnectionClosed):
                return
            except (KeyboardInterrupt, SystemExit):
                raise
            except:
                yield t.simple_response("500 Internal Server Error", format_exc())
        

class WSGIServer(object):
    """
An HTTP server for WSGI.
------------------------
    =================== ======================================================================
    Option              Description
    =================== ======================================================================
    bind_addr           The interface on which to listen for connections.
                        For TCP sockets, a (host, port) tuple. Host values may be any IPv4
                        or IPv6 address, or any valid hostname. The string 'localhost' is a
                        synonym for '127.0.0.1' (or '::1', if your hosts file prefers IPv6).
                        The string '0.0.0.0' is a special IPv4 entry meaning "any active
                        interface" (INADDR_ANY), and '::' is the similar IN6ADDR_ANY for
                        IPv6. The empty string or None are not allowed.
                        
                        For UNIX sockets, supply the filename as a string.
                        
    wsgi_app            the WSGI 'application callable'; multiple WSGI applications
                        may be passed as (path_prefix, app) pairs.
    server_name         the string to set for WSGI's SERVER_NAME environ entry.
                        Defaults to socket.gethostname().
    request_queue_size  the 'backlog' argument to socket.listen();
                        specifies the maximum number of queued connections (default 5).
    protocol            the version string to write in the Status-Line of all
                        HTTP responses. For example, "HTTP/1.1" (the default). This
                        also limits the supported features used in the response.
    =================== ======================================================================
    """
    
    protocol = "HTTP/1.1"
    _bind_addr = "localhost"
    version = "cogen.web.wsgi/%s Python/%s" % (cogen.__version__, sys.version.split()[0])
    ready = False
    ConnectionClass = WSGIConnection
    environ = {}
    
    def __init__(t, bind_addr, wsgi_app, server_name=None, request_queue_size=5):
        t.requests = Queue.Queue(max)
        t.request_queue_size = request_queue_size
        
        if callable(wsgi_app):
            # We've been handed a single wsgi_app, in CP-2.1 style.
            # Assume it's mounted at "".
            t.wsgi_app = wsgi_app
        else:
            # We've been handed a list of (path_prefix, wsgi_app) tuples,
            # so that the server can call different wsgi_apps, and also
            # correctly set SCRIPT_NAME.
            t.wsgi_app = WSGIPathInfoDispatcher(wsgi_app)
        
        t.bind_addr = bind_addr
        if not server_name:
            server_name = socket.gethostname()
        t.server_name = server_name
    
    def __str__(t):
        return "%s.%s(%r)" % (t.__module__, t.__class__.__name__,
                              t.bind_addr)
    
    def _get_bind_addr(t):
        return t._bind_addr
    def _set_bind_addr(t, value):
        if isinstance(value, tuple) and value[0] in ('', None):
            # Despite the socket module docs, using '' does not
            # allow AI_PASSIVE to work. Passing None instead
            # returns '0.0.0.0' like we want. In other words:
            #     host    AI_PASSIVE     result
            #      ''         Y         192.168.x.y
            #      ''         N         192.168.x.y
            #     None        Y         0.0.0.0
            #     None        N         127.0.0.1
            # But since you can get the same effect with an explicit
            # '0.0.0.0', we deny both the empty string and None as values.
            raise ValueError("Host values of '' or None are not allowed. "
                             "Use '0.0.0.0' (IPv4) or '::' (IPv6) instead "
                             "to listen on all active interfaces.")
        t._bind_addr = value
    bind_addr = property(_get_bind_addr, _set_bind_addr,
        doc="""The interface on which to listen for connections.
        
        For TCP sockets, a (host, port) tuple. Host values may be any IPv4
        or IPv6 address, or any valid hostname. The string 'localhost' is a
        synonym for '127.0.0.1' (or '::1', if your hosts file prefers IPv6).
        The string '0.0.0.0' is a special IPv4 entry meaning "any active
        interface" (INADDR_ANY), and '::' is the similar IN6ADDR_ANY for
        IPv6. The empty string or None are not allowed.
        
        For UNIX sockets, supply the filename as a string.""")
    @coroutine
    def start(t):
        """Run the server forever."""
        # We don't have to trap KeyboardInterrupt or SystemExit here,
        # because cherrpy.server already does so, calling t.stop() for us.
        # If you're using this server with another framework, you should
        # trap those exceptions in whatever code block calls start().
        
        # Select the appropriate socket
        if isinstance(t.bind_addr, basestring):
            # AF_UNIX socket
            
            # So we can reuse the socket...
            try: os.unlink(t.bind_addr)
            except: pass
            
            # So everyone can access the socket...
            try: os.chmod(t.bind_addr, 0777)
            except: pass
            
            info = [(socket.AF_UNIX, socket.SOCK_STREAM, 0, "", t.bind_addr)]
        else:
            # AF_INET or AF_INET6 socket
            # Get the correct address family for our host (allows IPv6 addresses)
            host, port = t.bind_addr
            try:
                info = socket.getaddrinfo(host, port, socket.AF_UNSPEC,
                                          socket.SOCK_STREAM, 0, socket.AI_PASSIVE)
            except socket.gaierror:
                # Probably a DNS issue. Assume IPv4.
                info = [(socket.AF_INET, socket.SOCK_STREAM, 0, "", t.bind_addr)]
        
        t.socket = None
        msg = "No socket could be created"
        for res in info:
            af, socktype, proto, canonname, sa = res
            try:
                t.bind(af, socktype, proto)
            except socket.error, msg:
                if t.socket:
                    t.socket.close()
                t.socket = None
                continue
            break
        if not t.socket:
            raise socket.error, msg
        
        # Timeout so KeyboardInterrupt can be caught on Win32
        #~ t.socket.settimeout(1)
        t.socket.listen(t.request_queue_size)
        
        #~ x=1
        while True:
            s, addr = yield sockets.Accept(t.socket, timeout=-1)
             
            environ = t.environ.copy()
            environ["SERVER_SOFTWARE"] = "%s WSGI Server" % t.version
            # set a non-standard environ entry so the WSGI app can know what
            # the *real* server protocol is (and what features to support).
            # See http://www.faqs.org/rfcs/rfc2145.html.
            environ["ACTUAL_SERVER_PROTOCOL"] = t.protocol
            environ["SERVER_NAME"] = t.server_name
            
            if isinstance(t.bind_addr, basestring):
                # AF_UNIX. This isn't really allowed by WSGI, which doesn't
                # address unix domain sockets. But it's better than nothing.
                environ["SERVER_PORT"] = ""
            else:
                environ["SERVER_PORT"] = str(t.bind_addr[1])
                # optional values
                # Until we do DNS lookups, omit REMOTE_HOST
                environ["REMOTE_ADDR"] = addr[0]
                environ["REMOTE_PORT"] = str(addr[1])
            
            conn = t.ConnectionClass(s, t.wsgi_app, environ)
            #~ conn.no = x
            #~ print 'Acceptiong', x
            #~ x += 1
            yield events.AddCoro(conn.run, prio=priority.CORO)
            #TODO: how scheduling ?

   
    def bind(t, family, type, proto=0):
        """Create (or recreate) the actual socket object."""
        t.socket = sockets.Socket(family, type, proto)
        t.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        t.socket.setblocking(0)
        #~ t.socket.setsockopt(socket.SOL_SOCKET, socket.TCP_NODELAY, 1)
        t.socket.bind(t.bind_addr)
    
def main():    
    from cogen.web import wsgi
    import wsgiref.validate 
    import pprint
    #~ from cogen.web import httpd
    def my_crazy_app(environ, start_response):
        status = '200 OK'
        response_headers = [('Content-type','text/plain')]
        start_response(status, response_headers)
        return ["""
        Lorem ipsum dolor sit amet, consectetuer adipiscing elit. Nunc feugiat. Nam dictum, eros sed iaculis egestas, odio massa fringilla metus, sed scelerisque velit est id turpis. Integer et arcu vel mi ornare tincidunt. Proin sodales, nibh sit amet posuere porttitor, magna purus facilisis lorem, sed mattis sem lorem auctor magna. Suspendisse aliquet lacus ac turpis. Praesent ut tortor. Nulla facilisi. Phasellus enim. Curabitur lorem nisi, pulvinar at, mollis quis, mattis id, massa. Nulla facilisi. In luctus erat. Proin eget nulla eget felis varius molestie. Curabitur hendrerit massa ac nunc. Donec condimentum leo eu magna. Donec lorem. Vestibulum sed massa in turpis auctor consectetuer. Ut volutpat diam sit amet justo. Mauris et elit tempus tellus gravida tincidunt.

        Sed posuere nunc quis erat. In suscipit sapien nec mi. Vestibulum condimentum erat a dui. Curabitur dictum augue vitae nunc. Aliquam imperdiet nisi non eros. Cum sociis natoque penatibus et magnis dis parturient montes, nascetur ridiculus mus. Etiam sagittis risus vel eros. Praesent lobortis nulla non sapien. Nulla scelerisque quam vitae lectus. Duis eu tortor ut pede faucibus auctor. Nam ullamcorper est id felis. Fusce sit amet risus a mi vestibulum mattis. Fusce nibh nisi, congue at, iaculis ac, blandit quis, erat.

        Duis turpis. Etiam pede nulla, rhoncus vel, laoreet ac, facilisis imperdiet, enim. Praesent viverra placerat lorem. Maecenas dapibus diam sit amet mi. Suspendisse id turpis. Sed quis velit sit amet lorem imperdiet cursus. Donec nonummy. Phasellus condimentum libero sit amet elit. Integer lectus turpis, pharetra sed, mollis quis, porttitor vitae, tortor. Sed eget massa. Suspendisse eu metus. Nam libero. Nullam porta, nisi a rhoncus tincidunt, velit lacus porta diam, a feugiat odio est at eros. Phasellus urna. Suspendisse convallis libero ac mauris. Vestibulum vitae sem in massa tincidunt accumsan. Vestibulum pharetra interdum dolor.

        Aliquam interdum lobortis tellus. In adipiscing dictum enim. Vestibulum magna. Ut rhoncus. Sed arcu. Pellentesque tellus mi, porttitor a, fringilla in, dignissim quis, neque. Aliquam erat volutpat. Aenean non purus quis nunc vestibulum interdum. Quisque non urna. Proin nec mauris. Suspendisse potenti.

        Lorem ipsum dolor sit amet, consectetuer adipiscing elit. Vestibulum luctus. Donec erat quam, facilisis eget, pharetra vel, sagittis et, nisi. Suspendisse hendrerit pellentesque turpis. Curabitur ac velit quis urna rutrum lacinia. Integer pede arcu, laoreet ac, aliquet in, tristique ac, libero. Suspendisse quis mauris. Suspendisse molestie lacinia quam. Phasellus porttitor, odio in posuere vulputate, lorem nunc sollicitudin nisl, et sagittis arcu augue eu urna. Donec tincidunt mauris at ipsum. Sed id neque non ante fringilla tempus. Duis sit amet tortor nec erat condimentum commodo. Vestibulum euismod volutpat erat. In cursus pretium odio. Sed a diam. Mauris at lectus. Integer ipsum augue, tincidunt in, sagittis ac, vestibulum rutrum, tortor. Pellentesque quam. Nam volutpat justo vitae dolor. 
        """]

    server = wsgi.WSGIServer(
                ('localhost', 8070), 
                #~ wsgiref.validate.validator(my_crazy_app),
                my_crazy_app,
                server_name='localhost')
    m = Scheduler(default_priority=priority.LAST, default_timeout=15)
    m.add(server.start)
    try:
        m.run()
    except (KeyboardInterrupt, SystemExit):
        pass
        
def server_factory(global_conf, host, port):
    port = int(port)
    def serve(app):
        server = WSGIServer( (host, port), app, server_name=host)
        m = Scheduler(default_priority=priority.LAST, default_timeout=15)
        m.add(server.start)
        m.run()
    return serve
    
if __name__ == "__main__":
    main()
    #~ import cProfile
    #~ cProfile.run("main()", "cprofile.log")
    #~ import pstats
    #~ for i in ['calls','cumulative','file','module','pcalls','line','name','nfl','stdname','time']:
        #~ stats = pstats.Stats("cprofile.log",stream = file('cprofile.%s.%s.txt' %(os.path.split(__file__)[1],i),'w'))
        #~ stats.sort_stats(i)
        #~ stats.print_stats()

