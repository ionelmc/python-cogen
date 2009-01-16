from cogen.common import *
import sys

port = len(sys.argv)>1 and int(sys.argv[1]) or 1200

@coroutine
def server():
    srv = sockets.Socket()
    adr = ('0.0.0.0', port)
    srv.bind(adr)
    srv.listen(64)
    print "Listening on", adr
    num = 0
    while 1:
        conn, addr = yield srv.accept()
        num += 1
        print "Connection from %s:%s, num=" % addr, num
        m.add(handler, args=(conn, addr))

@coroutine
def handler(sock, addr):
    yield sock.recv(1024)
    
print 'Using:', proactors.DefaultProactor.__name__
m = Scheduler(proactor_multiplex_first=False, ops_greedy=True, default_priority=priority.FIRST, proactor_default_size=102400)
m.add(server)
m.run()