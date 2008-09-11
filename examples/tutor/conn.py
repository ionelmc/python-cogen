from cogen.core.coroutines import coroutine
from cogen.core.schedulers import Scheduler
from cogen.core.sockets import Socket
from cogen.core.proactors import has_select

@coroutine
def somecoroutine():
    mysocket = Socket() # cogen's socket wrapper
    yield mysocket.connect(('www.google.com',80))
    fh = mysocket.makefile()
    yield mysocket.sendall("GET / HTTP/1.1\r\nHost: www.google.com\r\n\r\n")
    #~ result = yield fh.readline()
    result = yield mysocket.recv(10240)
    print result

sched = Scheduler(proactor=has_select()) 
#~ sched = Scheduler() 
sched.add(somecoroutine)
sched.run() # this is the main loop