#~ try:
    #~ import psyco
    #~ psyco.full()
#~ except ImportError:
    #~ pass
#~ import cogen

def lorem_ipsum_app(environ, start_response):
    start_response('200 OK', [('Content-type','text/plain'), ('Content-Length','19')])
    return ['Lorem ipsum dolor..']
    
import cogen
from cogen.web.wsgi import WSGIServer
sched = cogen.core.schedulers.Scheduler(
    default_timeout=-1, 
    #~ proactor=cogen.core.proactors.Pollproactor,
    #~ proactor=cogen.core.proactors.has_select(),
    default_priority=cogen.core.util.priority.FIRST,
    proactor_resolution=1
)
    
server = WSGIServer( 
  ('0.0.0.0', 9021), 
  lorem_ipsum_app, 
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
###############        
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
################  
#~ import hotshot, hotshot.stats, pstats, os
#~ prof = hotshot.Profile("hotshot.log")
#~ prof.runcall(run)
#~ prof.close()
#~ for i in ['calls','cumulative','time']:
    #~ stats = hotshot.stats.load("hotshot.log")
    #~ stats.stream = file('hotshot.%s.%s.txt' % (os.path.split(__file__)[1],i),'w+')
    #~ stats.sort_stats(i)
    #~ stats.print_stats()
