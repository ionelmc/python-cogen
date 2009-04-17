from cogen.common import *
import sys


m = Scheduler(
    proactor_multiplex_first=False, 
    ops_greedy=False, 
    default_priority=priority.FIRST, 
    proactor_default_size=102400, 
    proactor_greedy=True,
    proactor_resolution=5
)
port = len(sys.argv)>1 and int(sys.argv[1]) or 1200

@coroutine
def server():
    srv = sockets.Socket()
    adr = ('0.0.0.0', port)
    srv.bind(adr)
    srv.listen(100000)
    connections = []
    print "Listening on", adr
    num = 0
    while 1:
        conn, addr = yield srv.accept()
        num += 1
        if num % 1000 == 0:
            print num
        #~ print "Connection from %s:%s, num=" % addr, num
        #~ m.add(handler, args=(conn, addr))
        connections.append(conn)

@coroutine
def handler(sock, addr):
    yield sock.recv(1024)
    
print 'Using:', proactors.DefaultProactor.__name__
m.add(server)
m.run()
