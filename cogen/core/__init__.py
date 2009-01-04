'''
This is a library for network oriented, coroutine based programming. 
The interfaces and events/operations aim to mimic some of the regular thread 
and socket features. 

cogen uses the `enhanced generators <http://www.python.org/dev/peps/pep-0342/>`_
in python 2.5. These generators are bidirectional: they allow to pass values in 
and out of the generator. The whole framework is based on this.

The generator yields a `Operation` instance and will receive the result from 
that yield when the operation is ready.

Example::

    @coroutine
    def mycoro(bla):
        yield <operation>
        yield <operation>
    
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


::
    
    Roughly the cogen internals works like this:

    +------------------------+
    | @coroutine             |
    | def foo():             |
    |     ...                |             op.process(sched, coro)
    |  +->result = yield op--|----------------+------------+
    |  |  ...                |                |            |  
    +--|---------------------+    +---------------+  +---------------------+      
       |                          | the operation |  | the operation can't |
      result = op.finalize()      | is ready      |  | complete right now  |
       |                          +------|--------+  +----------|----------+
      scheduler runs foo                 |                      |
       |                                 |                      |
      foo gets in the active             |                      |
      coroutines queue                   |                      |
       |                                 |                      |
       +----------------------<----------+                      |
       |                                                    depening on the op      
      op.run()                                               +---------+
       |      socket is ready               add it in        |         |
       +-------------<------------  ......  the proactor  <--+         |
       |                         later                                 | 
       +------<-------------------  ......  add it in some other     <-+
        some event decides                  queue for later run
        this op is ready
        
        
The scheduler basicaly does 3 things:
  - runs active (coroutine,operations) pairs -- calls process on the op
  - runs the proactor
  - checks for timeouts
 
The proactor basicaly does 2 things:
  - calls the system to check what descriptors are ready
  - runs the operations that have ready descriptors

The operation does most of the work (via the process, finalize, cleanup, run methods):
  - adds itself in the proactor (if it's a socket operation)
  - adds itself in some structure to be activated later by some other event
  - adds itself and the coro in the scheduler's active coroutines queue


The coroutine decorator wrappes foo in a Coroutine class that does some
niceties like exception handling, getting the result from finalize() etc.

'''

