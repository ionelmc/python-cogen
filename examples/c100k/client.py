import sys, os, traceback, socket
from cogen.common import *

m = Scheduler(proactor_multiplex_first=False, ops_greedy=True, default_priority=priority.FIRST, proactor_default_size=102400)
port = len(sys.argv)>1 and int(sys.argv[1]) or 1200

@coroutine
def client():
    socket_list = []
    for i in xrange(50000):
        sock = sockets.Socket()
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("192.168.111.203", 10000+i))
        socket_list.append(sock)
        try:
            yield sock.connect(("192.168.111.201", port))
        except:
            traceback.print_exc()
            return
    for i in xrange(50000):
        sock = sockets.Socket()
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("192.168.111.204", 10000+i))
        socket_list.append(sock)
        try:
            yield sock.connect(("192.168.111.202", port))
        except:
            traceback.print_exc()
            return

m.add(client)

m.run()
