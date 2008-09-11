import datetime
from cogen.core.util import debug

import wsgiref.validate 
import pprint
import cgi
import cogen

def lorem_ipsum_app(environ, start_response):
    status = '200 OK'
    response_headers = [('Content-type','text/plain'),
                       ('Content-Length','19')]
    start_response(status, response_headers)
    return ['Lorem ipsum dolor..']
    
def wait_app(environ, start_response):
    start_response('200 OK', [('Content-type','text/html')])
    yield "I'm waiting for some signal<br>"
    yield environ['cogen.core'].events.WaitForSignal("abc", timeout=5)
    if isinstance(environ['cogen.wsgi'].result, Exception):
        yield "Your time is up !"
    else:
        yield "Someone signaled me with this message: %s" % cgi.escape(`environ['cogen.wsgi'].result`)
def send_app(environ, start_response):
    start_response('200 OK', [('Content-type','text/html')])
    yield environ['cogen.core'].events.Signal("abc", environ["PATH_INFO"])
    yield "Done."

def input_app(environ, start_response):
    start_response('200 OK', [('Content-type','text/html')])
    return [environ['wsgi.input'].read()]

import cogen
from cogen.web.wsgi import WSGIServer
from cogen.web.async import sync_input
sched = cogen.core.schedulers.Scheduler(
    default_timeout=None, 
    #~ proactor=cogen.core.proactors.Pollproactor,
    default_priority=cogen.core.util.priority.FIRST,
    proactor_resolution=1
)
    
server = WSGIServer( 
  ('0.0.0.0', 9001), 
  [
    ('/', lorem_ipsum_app), 
    ('/wait', wait_app), 
    ('/send', send_app),
    ('/input', sync_input(input_app))
  ], 
  sched, 
  server_name='localhost', 
  request_queue_size=2048,
  #~ sockoper_run_first=False
)
sched.add(server.serve)
sched.run()

#~ def run():
    #~ try:
        #~ sched.run()
    #~ except KeyboardInterrupt:
        #~ pass
#~ import cProfile, os
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
            #~ ),'w+'
        #~ )
    #~ )
    #~ stats.sort_stats(i)
    #~ stats.print_stats()
        
