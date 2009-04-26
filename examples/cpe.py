#~ from cogen.core.util import debug
#~ print __builtins__.acquire
import socket
realsocket = socket.socket
def socketwrap(family=socket.AF_INET, type=socket.SOCK_STREAM, proto=0):
    sockobj = realsocket(family, type, proto)
    sockobj.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    return sockobj
socket.socket = socketwrap

#~ socket.setdefaulttimeout(200)
#~ import time
#~ time.sleep = debug(0)(time.sleep)
import cherrypy
#~ cherrypy.wsgiserver.HTTPConnection.communicate = debug()(cherrypy.wsgiserver.HTTPConnection.communicate)

#~ class HelloWorld(object):
    #~ def index(self):
        #~ return "Hello World!"
    #~ index.exposed = True

#~ cherrypy.quickstart(HelloWorld(), config={'global':{'engine.autoreload_on':False}})


def lorem_ipsum_app(environ, start_response):
    status = '200 OK'
    response_headers = [('Content-type','text/plain'),
                       ('Content-Length','19')]
    start_response(status, response_headers)
    return ['Lorem ipsum dolor..']

srv = cherrypy.wsgiserver.CherryPyWSGIServer( ('0.0.0.0', 8080), lorem_ipsum_app)
def run():
    try:
        srv.start()
    except:
        srv.stop()

#~ debug()(cherrypy.quickstart)(HelloWorld(), config={'global':{'engine.autoreload_on':False}})

run()
#~ import cProfile, os
#~ # cProfile.run("cherrypy.quickstart(HelloWorld(), config={'global':{'engine.autoreload_on':False}})", "cprofile.log")
#~ cProfile.run("run()", "cprofile.log")
#~ import pstats
#~ for i in [
    #~ 'calls','cumulative','file','module',
    #~ 'pcalls','line','name','nfl','stdname','time'
    #~ ]:
    #~ stats = pstats.Stats("cprofile.log",
        #~ stream = file('cprofile.%s.%s.txt' % (
                #~ os.path.split(__file__)[1],
                #~ i
            #~ ),'w'
        #~ )
    #~ )
    #~ stats.sort_stats(i)
    #~ stats.print_stats()
