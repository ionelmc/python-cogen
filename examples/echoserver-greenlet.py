import sys

from cogen.core import schedulers
from cogen.magic.corolets import corolet, yield_
from cogen.magic import socketlets

@corolet
def server():
    srv = socketlets.Socket()
    adr = ('0.0.0.0', len(sys.argv)>1 and int(sys.argv[1]) or 1200)
    srv.bind(adr)
    srv.listen(64)
    while 1:
        print "Listening on", adr
        conn, addr = srv.accept()
        print "Connection from %s:%s" % addr
        m.add(handler, args=(conn, addr))

@corolet
def handler(sock, addr):
    fh = sock.makefile()
    fh.write("WELCOME TO ECHO SERVER !\r\n")
    fh.flush()

    while 1:
        line = fh.readline(1024)
        if line.strip() == 'exit':
            fh.write("GOOD BYE")
            fh.close()
            sock.close()
            return
        fh.write(line)
        fh.flush()

m = schedulers.Scheduler()
m.add(server)
m.run()
