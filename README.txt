Overview
--------
This is a library for network oriented, coroutine based programming. 

*cogen*'s goal is to enable writing code in a synchronous and easy 
manner in the form of generators that yield calls and recieve the result
from that yield. These calls translate to asynchronous and fast os calls 
in *cogen*'s internals.

Notable features
================

* a WSGI server, HTTP1.1 compilat, with asynchronous extensions
* use epoll, kqueue where supported, select based otherwise
* a Queue with the same interface as the standard library Queue, but 
  for coroutines
  
  
Quick introduction
==================
Programming with `cogen` library should be straightforward, similar with 
programming threads but without all the problems. A coroutine is just a 
generator wrapped in a operation handling class:

::

    @coroutine
    def mycoro(bla):
        result = yield <operation>
        result = yield <operation>


* the `operation` instructs the scheduler what to do with the coroutine: 
  suspend it till something happens, add another coro in the scheduler, raise
  a event and so on.
* the `operations` are split up in 2 modules: events and sockets
  * the `operations` from sockets are related to network, like reading and 
  writing, and these are done asynchronously but your code in the coroutine 
  will see them as a regular synchronous or blocking call.
* the `operations` from events are related to signals and 
  coroutine/scheduler management.
* if a `operation` has a result associated then the yield will return that 
  result (eg. a string or a (connection, address) tuple) otherwise it will 
  return the operation instance.

Echo server example
'''''''''''''''''''

::

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
        yield sockets.Write(sock, "WELCOME TO ECHO SERVER !\r\n")
            
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


Links
-----

Documentation
=============
Hosted at: http://code.google.com/p/cogen/wiki/Docs_Cogen

Development
============
Takes place at: http://code.google.com/p/cogen/

Grab the latest and greatest from trunk with::

    easy_install cogen==dev