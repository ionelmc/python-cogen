from cogen.core import sockets
from cogen.core import schedulers
from cogen.core.coroutine import coroutine

@coroutine
def server():
    srv = sockets.Socket()
    print type(srv)
    srv.bind(('localhost',777))
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

m = schedulers.Scheduler()
m.add(server)
m.run()