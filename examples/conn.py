from cogen.core.coroutine import coroutine
from cogen.core.schedulers import Scheduler
from cogen.core.sockets import Socket
from cogen.core.reactors import SelectReactor

@coroutine
def somecoroutine():
    mysocket = Socket() # cogen's socket wrapper
    yield mysocket.connect(('www.google.com',80))
    yield mysocket.writeall("GET / HTTP/1.1\r\nHost: www.google.com\r\n\r\n")
    result = yield mysocket.read(10240)
    print result

sched = Scheduler(reactor=SelectReactor)
sched.add(somecoroutine)
sched.run()