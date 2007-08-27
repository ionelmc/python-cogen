from cogen.core import Socket, GreedyScheduler
from cStringIO import StringIO

def server():
    srv = Socket.New()
    srv.setblocking(0)
    srv.bind(('localhost',777))
    srv.listen(10)
    while 1:
        print "Listening..."
        obj = yield Socket.Accept(srv)
        print "Connection from %s:%s" % obj.addr
        m.add(handler, obj.conn, obj.addr)
        yield
        
def handler(sock, addr):
    wobj = yield Socket.Write(sock, "WELCOME TO ECHO SERVER !\r\n")
        
    linebuff = StringIO()
    while 1:
        robj = yield Socket.ReadLine(sock, 8192)
        if robj.buff.strip() == 'exit':
            yield Socket.Write(sock, "GOOD BYE")
            sock.close()
            return
        wobj = yield Socket.Write(sock, robj.buff)

m = GreedyScheduler()
m.add(server)
m.run()