import socket
from cogen.magic.socketlets import Socket
socket.socket = Socket #monkeypatch!
from cogen.magic.corolets import corolet
from cogen.core import schedulers

import httplib

@corolet
def foo():
    conn = httplib.HTTPConnection("www.python.org")
    conn.request("GET", "/index.html")
    r1 = conn.getresponse()
    print r1.status, r1.reason
    data1 = r1.read()
    print data1[:100]
    conn.request("GET", "/parrot.spam")
    r2 = conn.getresponse()
    print r2.status, r2.reason
    data2 = r2.read()
    conn.close()


m = schedulers.Scheduler()
print m.proactor
m.add(foo)
m.run()
