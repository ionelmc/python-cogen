import sys, os
sys.path.append(os.path.split(os.getcwd())[0])

try:
    import psyco
    psyco.full()
except ImportError:
    pass

from cogen.web.httpserver import *
from cogen.common import *
import sys
import string

def test(ServerClass = HTTPServer, protocol="HTTP/1.1"):
    class HandlerClass(BaseHTTPRequestHandler):
        def version_string(t):
            return "CoroServe/%s-%s %s" % (
                    filter(lambda x:x.isupper(),t.server.m.__class__.__name__), 
                    filter(lambda x:x.isupper(),t.server.m.poll.__class__.__name__), 
                    t.sys_version
                )
        @coroutine
        def do_GET(t):
            yield events.Call(t.send_response,200)
            yield events.Call(t.send_header,"Content-type", "text/html")
            yield events.Call(t.end_headers)
            yield sockets.Write(sock=t.request, buff="""Lorem ipsum dolor sit amet""")
            #~ print '---- DONE ----'
    if sys.argv[1:]:
        port = int(sys.argv[1])
    else:
        port = 5000
    server_address = ('', port)

    HandlerClass.protocol_version = protocol
    httpd = ServerClass(server_address, HandlerClass)
    httpd.allow_reuse_address = True

    sa = httpd.socket.getsockname()
    print "Serving HTTP on", sa[0], "port", sa[1], "..."
    httpd.quickstart()


if __name__ == '__main__':
    #~ import cProfile
    #~ cProfile.run("test()", "cprofile.log")
    #~ import pstats
    #~ for i in ['calls','cumulative','file','module','pcalls','line','name','nfl','stdname','time']:
        #~ stats = pstats.Stats("cprofile.log",stream = file('cprofile.%s.txt' %i,'w'))
        #~ stats.sort_stats(i)
        #~ stats.print_stats()
    test()