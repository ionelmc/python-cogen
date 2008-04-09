"""
This module holds the essential stuff.

Programming with this library should be straghtforward. A coroutine is just 
a generator wrapped in a operation handling class:

{{{
@coroutine
def mycoro(bla):
    yield <operation>
    yield <operation>
}}}
    
  * the `operation` instructs the scheduler what to do with the 
  coroutine: suspend it till someting happens, add another coro in 
  the scheduler, raise a event and so on.
  * the `operations` are split up in 2 modules: events and sockets
    * the `operations` from sockets are related to network, like reading and 
    writing, and these are done asynchronously but your code in the 
    coroutine will see them as a regular synchronous or blocking call.
    * the `operations` from events are related to signals and 
    coroutine/scheduler management.
  * if a `operation` has a result associated then the yield will return that 
  result (eg. a string or a (connection, address) tuple) otherwise it will 
  return the operation instance.

Typical example:

{{{
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
    yield sockets.Write(sock, "WELCOME TO ECHO SERVER !\\r\\n")
    while 1:
        line = yield sockets.ReadLine(sock, 8192)
        if line.strip() == 'exit':
            yield sockets.Write(sock, "GOOD BYE")
            sock.close()
            return
            
        yield sockets.Write(sock, line)
        
m = Scheduler()
m.add(server)
m.run()
}}}
"""

from cogen.core import schedulers
from cogen.core import reactors
from cogen.core import coroutines
from cogen.core import events
from cogen.core import sockets
from cogen.core import queue