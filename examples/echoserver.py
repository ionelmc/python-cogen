from cogen.core import sockets
from cogen.core import schedulers
from cogen.core.coroutines import coroutine
from cogen.core import proactors
import sys

@coroutine
def server():
    srv = sockets.Socket()
    print type(srv)
    adr = ('0.0.0.0', len(sys.argv)>1 and int(sys.argv[1]) or 1200)
    srv.bind(adr)
    srv.listen(10)
    while 1:
        print "Listening on", adr
        conn, addr = yield srv.accept()
        print "Connection from %s:%s" % addr
        m.add(handler, args=(conn, addr))

@coroutine
def handler(sock, addr):
    fh = sock.makefile()
    yield fh.write("WELCOME TO ECHO SERVER !\r\n")
    yield fh.flush()
        
    while 1:
        line = yield fh.readline()
        print `line`
        if line.strip() == 'exit':
            yield fh.write("GOOD BYE")
            yield fh.close()
            sock.close()
            return
        yield fh.write(line)
        yield fh.flush()

m = schedulers.Scheduler(proactor_resolution=.5)
m.add(server)
m.run()