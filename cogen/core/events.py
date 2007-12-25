import datetime
from cogen.core.util import *

__doc_all__ = [
    'ConnectionClosed',
    'OperationTimeout',
    'WaitForSignal',
    'Signal',
    'Call',
    'AddCoro',
    'Join',
    'Sleep'
]
class ConnectionError(Exception):
    "Raised when a socket has a error flag (in epoll or select)"
    __doc_all__ = []
class ConnectionClosed(Exception):
    "Raised when the other peer has closed connection."
    __doc_all__ = []
class OperationTimeout(Exception):
    "Raised when the timeout for a operation expires. The exception message will be the operation"
    __doc_all__ = []
class CoroutineException(Exception):
    "This is used intenally to carry exception state in the poller and scheduler."
    __doc_all__ = []
    prio = priority.DEFAULT


class WaitForSignal(object):
    "The coroutine will resume when the same object is Signaled."
        
    __slots__ = ['name', 'prio', '_timeout', 'finalized', '__weakref__', 'result']
    __doc_all__ = ['__init__']
    timeout = TimeoutDesc('_timeout')
    def __init__(t, name, timeout=None, prio=priority.DEFAULT):
        t.name = name
        t.prio = prio
        t.timeout = timeout
        t.finalized = False
    def __repr__(t):
        return "<%s at 0x%X name:%s timeout:%s prio:%s>" % (t.__class__.__name__, id(t), t.name, t.timeout, t.prio)
class Signal(object):
    """
    This will resume the coroutines that where paused with WaitForSignal.
    
    Usage:
    
    .. sourcecode:: python
    
        nr = yield events.Signal(name, value)
        
    - nr - the number of coroutines woken up
    """
    __slots__ = ['name', 'value', 'len', 'prio', 'result']
    __doc_all__ = ['__init__']
    def __init__(t, name, value=None, prio=priority.DEFAULT):
        "All the coroutines waiting for this object will be added back in the active coroutine queue."
        t.name = name
        t.value = value
        t.prio = prio
        
class Call(object):
    """
    This will pause the current coroutine, add a new coro in the scheduler and resume the callee when it returns.
    
    Usage:
    
    .. sourcecode:: python
    
        result = yield events.Call(mycoro, args=<a tuple>, kwargs=<a dict>, prio=<int>)
        
    - if `prio` is set the new coroutine will be added in the top of the scheduler queue
    """
    __slots__ = ['coro', 'args', 'kwargs', 'prio']
    __doc_all__ = ['__init__']
    def __init__(t, coro, args=None, kwargs=None, prio=priority.DEFAULT):
        t.coro = coro
        t.args = args or ()
        t.kwargs = kwargs or {}
        t.prio = prio
    def __repr__(t):
        return '<%s instance at 0x%X, coro:%s, args: %s, kwargs: %s, prio: %s>' % (t.__class__, id(t), t.coro, t.args, t.kwargs, t.prio)
    
class AddCoro(object):
    """
    A operator for adding a coroutine in the scheduler.
    Example:
    
    .. sourcecode:: python
        
        yield events.AddCoro(some_coro, args=(), kwargs={})
    """
    __slots__ = ['coro', 'args', 'kwargs', 'prio']
    __doc_all__ = ['__init__']
    def __init__(t, coro, args=None, kwargs=None, prio=priority.DEFAULT):
        "Some DOC."
        t.coro = coro
        t.args = args or ()
        t.kwargs = kwargs or {}
        t.prio = prio
    def __repr__(t):
        return '<%s instance at 0x%X, coro:%s, args: %s, kwargs: %s, prio: %s>' % (t.__class__, id(t), t.coro, t.args, t.kwargs, t.prio)

class Pass(object):
    """
    A operator for setting the next (coro, op) pair to be runned by the scheduler. Used internally.
    """
    __slots__ = ['coro', 'op', 'prio']
    __doc_all__ = ['__init__']
    def __init__(t, coro, op=None, prio=priority.DEFAULT):
        t.coro = coro
        t.op = op
        t.prio = prio
    def __repr__(t):
        return '<%s instance at 0x%X, coro: %s, op: %s, prio: %s>' % (t.__class__, id(t), t.coro, t.op, t.prio)

class Complete(object):
    """
    A operator for adding a list of (coroutine, operator) pairs. Used internally.
    """
    __slots__ = ['args', 'prio']
    __doc_all__ = ['__init__']
    def __init__(t, *args):
        t.args = tuple(args)
        t.prio = priority.DEFAULT
    def __repr__(t):
        return '<%s instance at 0x%X, args: %s, prio: %s>' % (t.__class__, id(t), t.args, t.prio)
    
class Join(object):
    """
    A operator for waiting on a coroutine. 
    Example:
    
    .. sourcecode:: python

        @coroutine
        def coro_a():
            return_value = yield events.Join(ref)
            
            
        @coroutine
        def coro_b():
            yield "bla"
            raise StopIteration("some return value")
        
        ref = scheduler.add(coro_b)
        scheduler.add(coro_a)
    """
    __slots__ = ['coro', '_timeout', 'finalized', '__weakref__']
    timeout = TimeoutDesc('_timeout')
    __doc_all__ = ['__init__']
    def __init__(t, coro, timeout=None):
        t.coro = coro
        t.timeout = timeout
        t.finalized = False
    def __repr__(t):
        return '<%s instance at 0x%X, coro: %s>' % (t.__class__, id(t), t.coro)

    
class Sleep(object):
    """
    Usage:
    
    .. sourcecode:: python
    
        yield events.Sleep(time_object)
        
    - timeoject - a datetime or timedelta object, or a number of seconds
        
    .. sourcecode:: python
    
        yield events.Sleep(timestamp=ts)
        
    - ts - a timestamp
    """
    __slots__ = ['wake_time', 'coro']
    __doc_all__ = ['__init__']
    def __init__(t, val=None, timestamp=None):
        if isinstance(val, datetime.timedelta):
            t.wake_time = datetime.datetime.now() + val
        elif isinstance(val, datetime.datetime):
            t.wake_time = val
        else:
            if timestamp:
                t.wake_time = datetime.datetime.fromtimestamp(int(timestamp))
            else:
                t.wake_time = datetime.datetime.now() + datetime.timedelta(seconds=val)
        
    def __cmp__(t, other):
        return cmp(t.wake_time, other.wake_time)
