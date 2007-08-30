import base64
import Queue
import os
import re
quoted_slash = re.compile("(?i)%2F")
import rfc822
import socket
try:
    import cStringIO as StringIO
except ImportError:
    import StringIO
import sys
import threading
import time
import traceback
from urllib import unquote
from urlparse import urlparse

comma_separated_headers = ['ACCEPT', 'ACCEPT-CHARSET', 'ACCEPT-ENCODING',
    'ACCEPT-LANGUAGE', 'ACCEPT-RANGES', 'ALLOW', 'CACHE-CONTROL',
    'CONNECTION', 'CONTENT-ENCODING', 'CONTENT-LANGUAGE', 'EXPECT',
    'IF-MATCH', 'IF-NONE-MATCH', 'PRAGMA', 'PROXY-AUTHENTICATE', 'TE',
    'TRAILER', 'TRANSFER-ENCODING', 'UPGRADE', 'VARY', 'VIA', 'WARNING',
    'WWW-AUTHENTICATE']


class WSGIPathInfoDispatcher(object):
    """A WSGI dispatcher for dispatch based on the PATH_INFO.
    
    apps: a dict or list of (path_prefix, app) pairs.
    """
    
    def __init__(t, apps):
        try:
            apps = apps.items()
        except AttributeError:
            pass
        
        # Sort the apps by len(path), descending
        apps.sort()
        apps.reverse()
        
        # The path_prefix strings must start, but not end, with a slash.
        # Use "" instead of "/".
        t.apps = [(p.rstrip("/"), a) for p, a in apps]
    
    def __call__(t, environ, start_response):
        path = environ["PATH_INFO"] or "/"
        for p, app in t.apps:
            # The apps list should be sorted by length, descending.
            if path.startswith(p + "/") or path == p:
                environ = environ.copy()
                environ["SCRIPT_NAME"] = environ["SCRIPT_NAME"] + p
                environ["PATH_INFO"] = path[len(p):]
                return app(environ, start_response)
        
        start_response('404 Not Found', [('Content-Type', 'text/plain'),
                                         ('Content-Length', '0')])
        return ['']


class HTTPRequest(object):
    """An HTTP Request (and response).
    
    A single HTTP connection may consist of multiple request/response pairs.
    
    sendall: the 'sendall' method from the connection's fileobject.
    wsgi_app: the WSGI application to call.
    environ: a partial WSGI environ (server and connection entries).
        The caller MUST set the following entries:
        * All wsgi.* entries, including .input
        * SERVER_NAME and SERVER_PORT
        * Any SSL_* entries
        * Any custom entries like REMOTE_ADDR and REMOTE_PORT
        * SERVER_SOFTWARE: the value to write in the "Server" response header.
        * ACTUAL_SERVER_PROTOCOL: the value to write in the Status-Line of
            the response. From RFC 2145: "An HTTP server SHOULD send a
            response version equal to the highest version for which the
            server is at least conditionally compliant, and whose major
            version is less than or equal to the one received in the
            request.  An HTTP server MUST NOT send a version for which
            it is not at least conditionally compliant."
    
    outheaders: a list of header tuples to write in the response.
    ready: when True, the request has been parsed and is ready to begin
        generating the response. When False, signals the calling Connection
        that the response should not be generated and the connection should
        close.
    close_connection: signals the calling Connection that the request
        should close. This does not imply an error! The client and/or
        server may each request that the connection be closed.
    chunked_write: if True, output will be encoded with the "chunked"
        transfer-coding. This value is set automatically inside
        send_headers.
    """
    
    def __init__(t, sock, environ, wsgi_app):
        t.sock = sock
        t.environ = environ.copy()
        t.wsgi_app = wsgi_app
        
        t.ready = False
        t.started_response = False
        t.status = ""
        t.outheaders = []
        t.sent_headers = False
        t.close_connection = False
        t.chunked_write = False
    
    def parse_request(t):
        """Parse the next HTTP request start-line and message-headers."""
        # HTTP/1.1 connections are persistent by default. If a client
        # requests a page, then idles (leaves the connection open),
        # then rfile.readline() will raise socket.error("timed out").
        # Note that it does this based on the value given to settimeout(),
        # and doesn't need the client to request or acknowledge the close
        # (although your TCP stack might suffer for it: cf Apache's history
        # with FIN_WAIT_2).
        request_line = yield Socket.ReadLine(t.sock)
        if not request_line:
            # Force t.ready = False so the connection will close.
            t.ready = False
            return
        
        if request_line == "\r\n":
            # RFC 2616 sec 4.1: "...if the server is reading the protocol
            # stream at the beginning of a message and receives a CRLF
            # first, it should ignore the CRLF."
            # But only ignore one leading line! else we enable a DoS.
            request_line = yield Socket.ReadLine(t.sock)
            if not request_line:
                t.ready = False
                return
        
        environ = t.environ
        
        method, path, req_protocol = request_line.strip().split(" ", 2)
        environ["REQUEST_METHOD"] = method
        
        # path may be an abs_path (including "http://host.domain.tld");
        scheme, location, path, params, qs, frag = urlparse(path)
        
        if frag:
            yield Events.Call(t.simple_response, "400 Bad Request",
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
            yield Events.Call(t.simple_response,"505 HTTP Version Not Supported")
            return
        # Bah. "SERVER_PROTOCOL" is actually the REQUEST protocol.
        environ["SERVER_PROTOCOL"] = req_protocol
        t.response_protocol = "HTTP/%s.%s" % min(rp, sp)
        
        # If the Request-URI was an absoluteURI, use its location atom.
        if location:
            environ["SERVER_NAME"] = location
        
        # then all the http headers
        try:
            yield Events.Call(t.read_headers)
        except ValueError, ex:
            yield Events.Call(t.simple_response,"400 Bad Request", repr(ex.args))
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
                    yield Events.Call(t.simple_response,"501 Unimplemented")
                    t.close_connection = True
                    return
        
        if read_chunked:
            if not (yield Events.Call(t.decode_chunked)):
                return
        
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
            yield Events.Call(t.simple_response,100)
        
        t.ready = True
    
    def read_headers(t):
        """Read header lines from the incoming stream."""
        environ = t.environ
        
        while True:
            line = t.rfile.readline()
            if not line:
                # No more data--illegal end of headers
                raise ValueError("Illegal end of headers.")
            
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
    
    def decode_chunked(t):
        """Decode the 'chunked' transfer coding."""
        cl = 0
        data = StringIO.StringIO()
        while True:
            line = (yield Socket.ReadLine(t.sock)).strip().split(";", 1)
            chunk_size = int(line.pop(0), 16)
            if chunk_size <= 0:
                break
##            if line: chunk_extension = line[0]
            cl += chunk_size
            data.write(t.rfile.read(chunk_size))
            crlf = t.rfile.read(2)
            if crlf != "\r\n":
                t.simple_response("400 Bad Request",
                                     "Bad chunked transfer coding "
                                     "(expected '\\r\\n', got %r)" % crlf)
                return
        
        # Grab any trailer headers
        t.read_headers()
        
        data.seek(0)
        t.environ["wsgi.input"] = data
        t.environ["CONTENT_LENGTH"] = str(cl) or ""
        return True
    
    def respond(t):
        """Call the appropriate WSGI app and write its iterable output."""
        response = t.wsgi_app(t.environ, t.start_response)
        try:
            for chunk in response:
                # "The start_response callable must not actually transmit
                # the response headers. Instead, it must store them for the
                # server or gateway to transmit only after the first
                # iteration of the application return value that yields
                # a NON-EMPTY string, or upon the application's first
                # invocation of the write() callable." (PEP 333)
                if chunk:
                    t.write(chunk)
        finally:
            if hasattr(response, "close"):
                response.close()
        if (t.ready and not t.sent_headers):
            t.sent_headers = True
            t.send_headers()
        if t.chunked_write:
            t.sendall("0\r\n\r\n")
    
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
        yield Socket.WriteAll(t.sock,"".join(buf))
    
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
        return t.write
    
    def write(t, chunk):
        """WSGI callable to write unbuffered data to the client.
        
        This method is also used internally by start_response (to write
        data from the iterable returned by the WSGI application).
        """
        if not t.started_response:
            raise AssertionError("WSGI write called before start_response.")
        
        if not t.sent_headers:
            t.sent_headers = True
            t.send_headers()
        
        if t.chunked_write and chunk:
            buf = [hex(len(chunk))[2:], "\r\n", chunk, "\r\n"]
            t.sendall("".join(buf))
        else:
            t.sendall(chunk)
    
    def send_headers(t):
        """Assert, process, and send the HTTP response message-headers."""
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
        t.sendall("".join(buf))

class HTTPConnection(object):
    """An HTTP connection (active socket).
    
    socket: the raw socket object (usually TCP) for this connection.
    wsgi_app: the WSGI application for this server/connection.
    environ: a WSGI environ template. This will be copied for each request.
    
    rfile: a fileobject for reading from the socket.
    sendall: a function for writing (+ flush) to the socket.
    """
    
    rbufsize = -1
    RequestHandlerClass = HTTPRequest
    environ = {"wsgi.version": (1, 0),
               "wsgi.url_scheme": "http",
               "wsgi.multithread": True,
               "wsgi.multiprocess": False,
               "wsgi.run_once": False,
               "wsgi.errors": sys.stderr,
               }
    
    def __init__(t, sock, wsgi_app, environ):
        t.socket = sock
        t.wsgi_app = wsgi_app
        
        # Copy the class environ into t.
        t.environ = t.environ.copy()
        t.environ.update(environ)
        
        t.sock = sock
        
    def communicate(t):
        """Read each request and respond appropriately."""
        yield
        try:
            while True:
                # (re)set req to None so that if something goes wrong in
                # the RequestHandlerClass constructor, the error doesn't
                # get written to the previous request.
                req = None
                req = t.RequestHandlerClass(t.sock, t.environ,
                                               t.wsgi_app)
                # This order of operations should guarantee correct pipelining.
                req.parse_request()
                if not req.ready:
                    return
                req.respond()
                if req.close_connection:
                    return
        except socket.error, e:
            errno = e.args[0]
            if errno not in socket_errors_to_ignore:
                if req:
                    req.simple_response("500 Internal Server Error",
                                        format_exc())
            return
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            if req:
                req.simple_response("500 Internal Server Error", format_exc())
    
    def close(t):
        """Close the socket underlying this connection."""
        t.rfile.close()
        t.socket.close()


def format_exc(limit=None):
    """Like print_exc() but return a string. Backport for Python 2.3."""
    try:
        etype, value, tb = sys.exc_info()
        return ''.join(traceback.format_exception(etype, value, tb, limit))
    finally:
        etype = value = tb = None

class WSGIServer(object):
    """An HTTP server for WSGI.
    
    bind_addr: The interface on which to listen for connections.
        For TCP sockets, a (host, port) tuple. Host values may be any IPv4
        or IPv6 address, or any valid hostname. The string 'localhost' is a
        synonym for '127.0.0.1' (or '::1', if your hosts file prefers IPv6).
        The string '0.0.0.0' is a special IPv4 entry meaning "any active
        interface" (INADDR_ANY), and '::' is the similar IN6ADDR_ANY for
        IPv6. The empty string or None are not allowed.
        
        For UNIX sockets, supply the filename as a string.
    wsgi_app: the WSGI 'application callable'; multiple WSGI applications
        may be passed as (path_prefix, app) pairs.
    numthreads: the number of worker threads to create (default 10).
    server_name: the string to set for WSGI's SERVER_NAME environ entry.
        Defaults to socket.gethostname().
    max: the maximum number of queued requests (defaults to -1 = no limit).
    request_queue_size: the 'backlog' argument to socket.listen();
        specifies the maximum number of queued connections (default 5).
    timeout: the timeout in seconds for accepted connections (default 10).
    
    protocol: the version string to write in the Status-Line of all
        HTTP responses. For example, "HTTP/1.1" (the default). This
        also limits the supported features used in the response.
    """
    
    protocol = "HTTP/1.1"
    _bind_addr = "localhost"
    version = "CherryPy/3.1alpha"
    ready = False
    ConnectionClass = HTTPConnection
    environ = {}
    
    def __init__(t, bind_addr, wsgi_app, numthreads=10, server_name=None,
                 max=-1, request_queue_size=5, timeout=10, shutdown_timeout=5):
        t.requests = Queue.Queue(max)
        
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
        t.numthreads = numthreads or 1
        if not server_name:
            server_name = socket.gethostname()
        t.server_name = server_name
        t.request_queue_size = request_queue_size
        t._workerThreads = []
        
        t.timeout = timeout
        t.shutdown_timeout = shutdown_timeout
    
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
        
        
        t.ready = True
        while t.ready:
            s, addr = yield Socket.Accept(t.socket)
            if not t.ready:
                return
            #TODO: other way to timeout connections
            
            environ = t.environ.copy()
            # SERVER_SOFTWARE is common for IIS. It's also helpful for
            # us to pass a default value for the "Server" response header.
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
            
            try:
                yield Events.Call(conn.communicate)
            finally:
                yield Events.Call(conn.close)
            #TODO: how scheduling ?

   
    def bind(t, family, type, proto=0):
        """Create (or recreate) the actual socket object."""
        t.socket = Socket.New(family, type, proto)
        t.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        t.socket.setblocking(0)
        #~ t.socket.setsockopt(socket.SOL_SOCKET, socket.TCP_NODELAY, 1)
        t.socket.bind(t.bind_addr)
    
    
