import sys, os, traceback, socket
from cogen.common import *

m = Scheduler(
    proactor_multiplex_first=False,
    ops_greedy=True,
    default_priority=priority.FIRST,
    proactor_default_size=102400,
    proactor_greedy=False,
    proactor_resolution=5
)
port = len(sys.argv)>1 and int(sys.argv[1]) or 1200
num = 0

@coroutine
def client(local, remote):
    global num
    sock = sockets.Socket()
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(local)
    yield sock.connect(remote)
    num += 1
    if num == 100000:
        # actually we don't need to revive 100k coros
        sys.exit()

        yield events.Signal('done')
    else:
        yield events.WaitForSignal('done')


for i in xrange(50000):
    m.add(client, args=(("192.168.111.203", 10000+i), ("192.168.111.201", port)))
for i in xrange(50000):
    m.add(client, args=(("192.168.111.204", 10000+i), ("192.168.111.202", port)))

m.run()
