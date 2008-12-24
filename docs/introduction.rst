General concepts
================

Cogen is a coroutine framework. Python 2.5 has support for coroutine-oriented
programming (see :pep:342). Cogen is 
different than the more popular async network-oriented frameworks like twisted or
asyncore in the sense that you do not have weird flows and callbacks. 
You write the code in a seamingly synchronous fashion using generators.

Because cogen does some stuff for you (like handle exceptions, pass results 
arounds and so on) you have to decorate all your generators that you want to use
as coroutines::

    from cogen.core.coroutines import coro
    
    @coro
    def mycoroutine():
        ...
        yield 
        ...
        
Also, the decorator does some handling/checking - so if you decorate a regular
function nothing bad will happen :).

The yield statement
-------------------

Suppose this example: In a coroutine you need to do something that usually blocks,
like reading from a socket.

In cogen you would write a coroutine that yields that read call and expects the
result like this::

    @coro
    def mysocketreader():
        data = yield mysock.recv(1024)
        print "Yay, I have data:", data
        
At that yield statement the coroutine will be paused. The framework will resume it 
when there's data available on that socket and pass the available data through that
yield statement.

What happens behind the scenes: mysock.recv(1024) actually returns a special object
that gets passed to the framework and instructs it what to do with the coroutine.
It's like a request object. There objects are named Operations in cogen (see :class:`~cogen.core.events.Operation`).

Calling other coroutines
------------------------

Using generators like this has some limitations, for example, generators do not
have a stack. So, suppose you have coro A calling coro B, usually one soves this
by making A consume B. However, cogen does this in another way - the caller (A)
yields B, and B works like the request object described in the previous section
- so B will instruct the framework to run itself and when B is finised (or throws an
exception) resume A and pass the result in.


Suppose we extend on the previous example::

    @coro
    def read(sock):
        data = yield sock.recv(1024)
        raise StopIteration(data)

    @coro
    def mycoro():
        result = yield read(mysock)
        print "Yay, data:", result
        
        
Since we can't use the return statement with a value in a generator we use
the standard StopIteration exception that is used internally by the generator
mechanics.

Running your first cogen app
----------------------------

Cogen is mainly composed of a scheduler, a proactor that handles the network 
calls, operations and your coroutines.

::

    >>> from cogen.core.coroutines import coro
    >>> from cogen.core.schedulers import Scheduler
    >>>
    >>> @coro
    ... def a(foo, times):
    ...     for i in range(times):
    ...         print foo, ':', i
    ...         yield
    ...
    >>> sched = Scheduler()
    >>> sched.add(a, args=('foo', 5))
    <a Coroutine instance at 0x01E29A80 wrapping <function a at 0x01E03130>, state: NOTSTARTED>
    >>> sched.add(a, args=('bar', 10))
    <a Coroutine instance at 0x01E29AD8 wrapping <function a at 0x01E03130>, state: NOTSTARTED>
    >>> sched.run()
    foo : 0
    bar : 0
    foo : 1
    bar : 1
    foo : 2
    bar : 2
    foo : 3
    bar : 3
    foo : 4
    bar : 4
    bar : 5
    bar : 6
    bar : 7
    bar : 8
    bar : 9
    >>>
