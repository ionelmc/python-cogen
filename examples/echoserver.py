from cogen.core import sockets
from cogen.core import schedulers
from cogen.core.coroutines import coroutine
from cogen.core import reactors
import sys

@coroutine
def server():
    srv = sockets.Socket()
    print type(srv)
    srv.bind(('0.0.0.0', len(sys.argv)>1 and int(sys.argv[1]) or 1200))
    srv.listen(10)
    while 1:
        print "Listening..."
        conn, addr = yield srv.accept()
        print "Connection from %s:%s" % addr
        m.add(handler, args=(conn, addr))

@coroutine
def handler(sock, addr):
    yield sock.write("WELCOME TO ECHO SERVER !\r\n")
        
    while 1:
        line = yield sock.readline(8192)
        if line.strip() == 'exit':
            yield sock.write("GOOD BYE")
            sock.close()
            return
        yield sock.write(line)

m = schedulers.Scheduler(reactor_resolution=.5)
m.add(server)
m.run()