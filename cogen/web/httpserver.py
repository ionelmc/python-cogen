__version__ = "0.1"

__all__ = ["HTTPServer", "BaseHTTPRequestHandler"]

import sys
import time
import socket # For gethostbyaddr()
import mimetools
from cStringIO import StringIO
from cogen.common import *

# Default error message
DEFAULT_ERROR_MESSAGE = """\
<head>
<title>Error response</title>
</head>
<body>
<h1>Error response</h1>
<p>Error code %(code)d.
<p>Message: %(message)s.
<p>Error code explanation: %(code)s = %(explain)s.
</body>
"""

def _quote_html(html):
    return html.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

class HTTPServer:

    address_family = socket.AF_INET
    socket_type = socket.SOCK_STREAM
    request_queue_size = 100
    allow_reuse_address = False

    def __init__(t, server_address, RequestHandlerClass):
        t.server_address = server_address
        t.RequestHandlerClass = RequestHandlerClass
        t.socket = sockets.New(t.address_family, t.socket_type)
        t.socket.setblocking(0)
        t.server_bind()
        t.server_activate()

    def server_bind(t):
        if t.allow_reuse_address:
            t.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        t.socket.bind(t.server_address)
        host, port = t.socket.getsockname()[:2]
        t.server_name = socket.getfqdn(host)
        t.server_port = port
    
    def server_activate(t):
        t.socket.listen(t.request_queue_size)
    def server_close(t):
        t.socket.close()
    @coroutine
    def serve_forever(t):
        """Handle one request at a time until doomsday."""
        while 1:
            try:
                #~ print 'wait'
                obj = yield sockets.Accept(sock=t.socket)
                #~ print 'accepted', obj
            except socket.error:
                return
            handler = t.RequestHandlerClass(obj.conn, obj.addr, t)
            #~ print handler
            t.m.add(handler.finish,t.m.add(handler.run))
            yield
    def quickstart(t, manager=Scheduler, **kw):
        
        t.m = manager(**kw)
        t.m.default_prio = 1
        t.m.add(t.serve_forever)
        try:
            t.m.run()
        except KeyboardInterrupt: 
            t.server_close()

class BaseHTTPRequestHandler:
    # The Python system version, truncated to its first component.
    sys_version = "Python/" + sys.version.split()[0]

    # The server software version.  You may want to override this.
    # The format is multiple whitespace-separated strings,
    # where each string is of the form name[/version].
    server_version = "cogen_httpserver/" + __version__
    
    
    def __init__(t, request, client_address, server):
        #~ print 'MUMU'
        t.request = request
        t.client_address = client_address
        t.server = server
    @coroutine    
    def run(t):
        #~ print 'MUMUx'
        try:
            t.close_connection = 1
            yield events.Call(t.handle_one_request)
            while not t.close_connection:
                yield events.Call(t.handle_one_request)
        finally:
            sys.exc_traceback = None    # Help garbage collection
    @coroutine
    def finish(t, coro):
        yield events.Join(coro)
        t.request.close()
    @coroutine        
    def parse_request(t, headers_buff):
        """Parse a request (internal).

        The request should be stored in t.raw_requestline; the results
        are in t.command, t.path, t.request_version and
        t.headers.

        Return True for success, False for failure; on failure, an
        error is sent back.

        """
        t.command = None  # set in case of error on the first line
        t.request_version = version = "HTTP/0.9" # Default
        t.close_connection = 1
        requestline = t.raw_requestline
        if requestline[-2:] == '\r\n':
            requestline = requestline[:-2]
        elif requestline[-1:] == '\n':
            requestline = requestline[:-1]
        t.requestline = requestline
        words = requestline.split()
        #~ print words
        if len(words) == 3:
            [command, path, version] = words
            if version[:5] != 'HTTP/':
                yield events.Call(t.send_error, 400, "Bad request version (%r)" % version)
                raise StopIteration(False)
            try:
                base_version_number = version.split('/', 1)[1]
                version_number = base_version_number.split(".")
                # RFC 2145 section 3.1 says there can be only one "." and
                #   - major and minor numbers MUST be treated as
                #      separate integers;
                #   - HTTP/2.4 is a lower version than HTTP/2.13, which in
                #      turn is lower than HTTP/12.3;
                #   - Leading zeros MUST be ignored by recipients.
                if len(version_number) != 2:
                    raise ValueError
                version_number = int(version_number[0]), int(version_number[1])
            except (ValueError, IndexError):
                yield events.Call(t.send_error, 400, "Bad request version (%r)" % version)
                raise StopIteration(False)
            if version_number >= (1, 1) and t.protocol_version >= "HTTP/1.1":
                t.close_connection = 0
            if version_number >= (2, 0):
                yield events.Call(t.send_error, 505, "Invalid HTTP Version (%s)" % base_version_number)
                raise StopIteration(False)
        elif len(words) == 2:
            [command, path] = words
            t.close_connection = 1
            if command != 'GET':
                yield events.Call(t.send_error, 400, "Bad HTTP/0.9 request type (%r)" % command)
                raise StopIteration(False)
        elif not words:
            raise StopIteration(False)
        else:
            yield events.Call(t.send_error, 400, "Bad request syntax (%r)" % requestline)
            raise StopIteration(False)
        #~ print command, path, version
        t.command, t.path, t.request_version = command, path, version

        # Examine the headers and look for a Connection directive
        t.headers = t.MessageClass(headers_buff, 0)

        conntype = t.headers.get('Connection', "")
        if conntype.lower() == 'close':
            t.close_connection = 1
        elif (conntype.lower() == 'keep-alive' and
              t.protocol_version >= "HTTP/1.1"):
            t.close_connection = 0
        raise StopIteration(True)
    @coroutine
    def handle_one_request(t):
        """Handle a single HTTP request.

        You normally don't need to override this method; see the class
        __doc__ string for information on how to handle specific HTTP
        commands such as GET and POST.

        """
        #~ print "handle_one_request"
        robj = (yield sockets.ReadLine(sock=t.request, len=8182))
        #~ print '--- READLINE', robj
        #~ print "handle_one_request2", repr(robj.buff)
        t.raw_requestline = robj.buff
        if not t.raw_requestline:
            t.close_connection = 1
            return
        _headers = 1    
        headers_buff = StringIO()
        while _headers:
            #~ print '- mumu'
            o = sockets.ReadLine(sock=t.request, len=8182)
            #~ print '-',o
            robj = yield o
            #~ print '--- READLINE', robj, robj.buff
            #~ print "handle_one_request?", line
            headers_buff.write(robj.buff)
            if robj.buff in ('\r\n', '\n'):
                break
        headers_buff.seek(0)
        #~ print "handle_one_request", headers_buff.getvalue()
        cobj = yield events.Call(t.parse_request,headers_buff)
        #~ print cobj
        if not cobj.result: # An error code has been sent, just exit
            return
        mname = 'do_' + t.command
        #~ print hasattr(t, mname)
        if not hasattr(t, mname):
            yield events.Call(t.send_error, 501, "Unsupported method (%r)" % t.command)
            return
        method = getattr(t, mname)
        yield events.Call(method)
        t.request.close()

    @coroutine
    def send_error(t, code, message=None):
        """Send and log an error reply.

        Arguments are the error code, and a detailed message.
        The detailed message defaults to the short entry matching the
        response code.

        This sends an error response (so it must be called before any
        output has been generated), logs the error, and finally sends
        a piece of HTML explaining the error to the user.

        """

        try:
            short, long = t.responses[code]
        except KeyError:
            short, long = '???', '???'
        if message is None:
            message = short
        explain = long
        t.log_error("code %d, message %s", code, message)
        # using _quote_html to prevent Cross Site Scripting attacks (see bug #1100201)
        content = (t.error_message_format %
                   {'code': code, 'message': _quote_html(message), 'explain': explain})
        yield events.Call(t.send_response, code, message)
        yield events.Call(t.send_header, "Content-Type", "text/html")
        yield events.Call(t.send_header, 'Connection', 'close')
        yield events.Call(t.end_headers)
        if t.command != 'HEAD' and code >= 200 and code not in (204, 304):
            yield sockets.Write(sock=t.request, buff=content)

    error_message_format = DEFAULT_ERROR_MESSAGE
    @coroutine
    def send_response(t, code, message=None):
        """Send the response header and log the response code.

        Also send two standard headers with the server software
        version and the current date.

        """
        t.log_request(code)
        if message is None:
            if code in t.responses:
                message = t.responses[code][0]
            else:
                message = ''
        if t.request_version != 'HTTP/0.9':
            yield sockets.Write(sock=t.request, buff="%s %d %s\r\n" %
                             (t.protocol_version, code, message))
            # print (t.protocol_version, code, message)
        yield events.Call(t.send_header, 'Server', t.version_string())
        yield events.Call(t.send_header, 'Date', t.date_time_string())
    @coroutine
    def send_header(t, keyword, value):
        """Send a MIME header."""
        if t.request_version != 'HTTP/0.9':
            yield sockets.Write(sock=t.request, buff="%s: %s\r\n" % (keyword, value))

        if keyword.lower() == 'connection':
            if value.lower() == 'close':
                t.close_connection = 1
            elif value.lower() == 'keep-alive':
                t.close_connection = 0
    @coroutine
    def end_headers(t):
        """Send the blank line ending the MIME headers."""
        if t.request_version != 'HTTP/0.9':
            yield sockets.Write(sock=t.request, buff="\r\n")

    def log_request(t, code='-', size='-'):
        """Log an accepted request.

        This is called by send_response().

        """

        #~ t.log_message('"%s" %s %s', t.requestline, str(code), str(size))

    def log_error(t, *args):
        """Log an error.

        This is called when a request cannot be fulfilled.  By
        default it passes the message on to log_message().

        Arguments are the same as for log_message().

        XXX This should go to the separate error log.

        """

        t.log_message(*args)

    def log_message(t, format, *args):
        """Log an arbitrary message.

        This is used by all other logging functions.  Override
        it if you have specific logging wishes.

        The first argument, FORMAT, is a format string for the
        message to be logged.  If the format string contains
        any % escapes requiring parameters, they should be
        specified as subsequent arguments (it's just like
        printf!).

        The client host and current date/time are prefixed to
        every message.

        """

        sys.stderr.write("%s - - [%s] %s\n" %
                         (t.address_string(),
                          t.log_date_time_string(),
                          format%args))

    def version_string(t):
        """Return the server software version string."""
        return t.server_version + ' ' + t.sys_version

    def date_time_string(t, timestamp=None):
        """Return the current date and time formatted for a message header."""
        if timestamp is None:
            timestamp = time.time()
        year, month, day, hh, mm, ss, wd, y, z = time.gmtime(timestamp)
        s = "%s, %02d %3s %4d %02d:%02d:%02d GMT" % (
                t.weekdayname[wd],
                day, t.monthname[month], year,
                hh, mm, ss)
        return s

    def log_date_time_string(t):
        """Return the current time formatted for logging."""
        now = time.time()
        year, month, day, hh, mm, ss, x, y, z = time.localtime(now)
        s = "%02d/%3s/%04d %02d:%02d:%02d" % (
                day, t.monthname[month], year, hh, mm, ss)
        return s

    weekdayname = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

    monthname = [None,
                 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

    def address_string(t):
        """Return the client address formatted for logging.

        This version looks up the full hostname using gethostbyaddr(),
        and tries to find a name that contains at least one dot.

        """

        host, port = t.client_address[:2]
        return socket.getfqdn(host)

    # Essentially static class variables

    # The version of the HTTP protocol we support.
    # Set this to HTTP/1.1 to enable automatic keepalive
    protocol_version = "HTTP/1.0"

    # The Message-like class used to parse headers
    MessageClass = mimetools.Message

    # Table mapping response codes to messages; entries have the
    # form {code: (shortmessage, longmessage)}.
    # See RFC 2616.
    responses = {
        100: ('Continue', 'Request received, please continue'),
        101: ('Switching Protocols',
              'Switching to new protocol; obey Upgrade header'),

        200: ('OK', 'Request fulfilled, document follows'),
        201: ('Created', 'Document created, URL follows'),
        202: ('Accepted',
              'Request accepted, processing continues off-line'),
        203: ('Non-Authoritative Information', 'Request fulfilled from cache'),
        204: ('No Content', 'Request fulfilled, nothing follows'),
        205: ('Reset Content', 'Clear input form for further input.'),
        206: ('Partial Content', 'Partial content follows.'),

        300: ('Multiple Choices',
              'Object has several resources -- see URI list'),
        301: ('Moved Permanently', 'Object moved permanently -- see URI list'),
        302: ('Found', 'Object moved temporarily -- see URI list'),
        303: ('See Other', 'Object moved -- see Method and URL list'),
        304: ('Not Modified',
              'Document has not changed since given time'),
        305: ('Use Proxy',
              'You must use proxy specified in Location to access this '
              'resource.'),
        307: ('Temporary Redirect',
              'Object moved temporarily -- see URI list'),

        400: ('Bad Request',
              'Bad request syntax or unsupported method'),
        401: ('Unauthorized',
              'No permission -- see authorization schemes'),
        402: ('Payment Required',
              'No payment -- see charging schemes'),
        403: ('Forbidden',
              'Request forbidden -- authorization will not help'),
        404: ('Not Found', 'Nothing matches the given URI'),
        405: ('Method Not Allowed',
              'Specified method is invalid for this server.'),
        406: ('Not Acceptable', 'URI not available in preferred format.'),
        407: ('Proxy Authentication Required', 'You must authenticate with '
              'this proxy before proceeding.'),
        408: ('Request Timeout', 'Request timed out; try again later.'),
        409: ('Conflict', 'Request conflict.'),
        410: ('Gone',
              'URI no longer exists and has been permanently removed.'),
        411: ('Length Required', 'Client must specify Content-Length.'),
        412: ('Precondition Failed', 'Precondition in headers is false.'),
        413: ('Request Entity Too Large', 'Entity is too large.'),
        414: ('Request-URI Too Long', 'URI is too long.'),
        415: ('Unsupported Media Type', 'Entity body in unsupported format.'),
        416: ('Requested Range Not Satisfiable',
              'Cannot satisfy request range.'),
        417: ('Expectation Failed',
              'Expect condition could not be satisfied.'),

        500: ('Internal Server Error', 'Server got itself in trouble'),
        501: ('Not Implemented',
              'Server does not support this operation'),
        502: ('Bad Gateway', 'Invalid responses from another server/proxy.'),
        503: ('Service Unavailable',
              'The server cannot process the request due to a high load'),
        504: ('Gateway Timeout',
              'The gateway server did not receive a timely response'),
        505: ('HTTP Version Not Supported', 'Cannot fulfill request.'),
        }

