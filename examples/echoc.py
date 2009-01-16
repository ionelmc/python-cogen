import sys, os, traceback, socket
from cogen.common import *

m = Scheduler(proactor_resolution=.5, proactor=proactors.has_select())
errors = 0
recvs = 0
@coroutine
def client(num):
    global errors, recvs
    sock = sockets.Socket()
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        try:
            yield sock.connect(("127.0.0.1", int(sys.argv[1])))
        except Exception, e:
            errors+=1
            print 'Error in:', num, errors
            traceback.print_exc()
            return
        fh = sock.makefile()
        while 1:
            line = yield fh.readline(8192)
            recvs += 1
            print num, recvs, ": ", line
    finally:
        sock.close()

for i in range(0, 10):
    m.add(client, args=(i,))

m.run()
