Introduction
============

cogen is a library for network oriented, coroutine based programming.
The interfaces and events/operations aim to mimic thread features.

Programming with `cogen` library should be straightforward, similar with 
programming threads but without all the problems. A coroutine is just a 
generator wrapped in a operation handling class:

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

Features
========

  * basic scheduling priority management
  * timeouts for socket operations
  * fast network polling:
    * epoll for linux platforms
    * kqueue for bsd 
    * select for any
  * send file support
  * signal events
  * wsgi server with coroutine extensions

Documentation
=============

    Docs are in the docs directory

Instalation
===========
    
    Run: 
        setup.py install
    
    To run the unittests run:
        setup.py test
