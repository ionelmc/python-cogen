import sys, os
from cogen.common import *

@coroutine
def server():
    srv = sockets.Socket()
    srv.setblocking(0)
    srv.bind(('localhost',777))
    srv.listen(10)
    while 1:
        print "Listening..."
        conn, addr = yield sockets.Accept(srv)
        print "Connection from %s:%s" % addr
        m.add(handler, conn, addr)

@coroutine
def handler(sock, addr):
    wobj = yield sockets.Write(sock, "WELCOME TO ECHO SERVER !\r\n")
        
    while 1:
        line = yield sockets.ReadLine(sock, 8192)
        if line.strip() == 'exit':
            yield sockets.Write(sock, "GOOD BYE")
            sock.close()
            return
        wobj = yield sockets.Write(sock, line)

m = Scheduler()
m.add(server)
m.run()