import sys, os, traceback
from cogen.common import *

m = Scheduler()
#~ reactor_resolution=.5, reactor=reactors.PollReactor)
errors = 0
recvs = 0
@coroutine
def client(num):
    global errors, recvs
    sock = sockets.Socket()
    try:
        yield sock.connect(("192.168.111.128", 776), run_first=False)
    except Exception, e:
        errors+=1
        print 'Error in:', num, errors, e
        return
    
    try:
        while 1:
            line = yield sockets.ReadLine(sock, 8192)
            recvs += 1
            print num, recvs, ": ", line
    finally:
        sock.close()

for i in range(0, 10000):
    m.add(client, args=(i,))

m.run()
