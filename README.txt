Overview
--------
This is a library for network oriented, coroutine based programming. 

*cogen*'s goal is to enable writing code in a seamingly synchronous and easy 
manner in the form of generators that yield calls and receive the result
from that yield. These calls translate to asynchronous and fast os calls 
in *cogen*'s internals.

Notable features
================

* a WSGI server, HTTP1.1 compliant, with asynchronous extensions
* epoll, kqueue, select, i/o completion ports, sendfile behind the scenes
* a couple of usefull classes for putting the coroutine to sleep, wait for 
  signals, queues, timeouts etc.
  
  
Quick introduction
==================
A coroutine is just a generator wrapped in a helper class:

::
    
    from cogen.core.coroutines import coroutine
    
    @coroutine
    def mycoro(bla):
        result = yield <operation>
        result = yield <operation>


* the `operation` instructs the scheduler what to do with the coroutine: 
  suspend it till something happens, add another coro in the scheduler, raise
  a event and so on.
* if a `operation` has a result associated then the yield will return that 
  result (eg. a string or a (connection, address) tuple) otherwise it will 
  return the operation instance.

Echo server example
'''''''''''''''''''

::

    from cogen.core import sockets
    from cogen.core import schedulers
    from cogen.core.coroutines import coroutine

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


Documentation
=============

http://cogen.googlecode.com/svn/trunk/docs/cogen.html

Development
============

Takes place at: http://code.google.com/p/cogen/

Grab the latest and greatest from trunk with::

    easy_install cogen==dev
