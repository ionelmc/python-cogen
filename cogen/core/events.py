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
        
    __slots__ = ['name','prio','_timeout','__weakref__']
    __doc_all__ = ['__init__']
    timeout = TimeoutDesc('_timeout')
    def __init__(t, obj, timeout=None, prio=priority.DEFAULT):
        t.name = obj
        t.prio = prio
        t.timeout = timeout
        
class Signal(object):
    """
    This will resume the coroutines that where paused with WaitForSignal.
    
    Usage:
    
    .. sourcecode:: python
    
        nr = yield events.Signal(obj)
        
    - nr - the number of coroutines woken up
    """
    __slots__ = ['name','len','prio','result']
    __doc_all__ = ['__init__']
    def __init__(t, obj, prio=priority.DEFAULT):
        "All the coroutines waiting for this object will be added back in the active coroutine queue."
        t.name = obj
        t.prio = prio
        
class Call(object):
    """
    This will pause the current coroutine, add a new coro in the scheduler and resume the callee when it returns.
    
    Usage:
    
    .. sourcecode:: python
    
        result = yield events.Call(mycoro, args=<a tuple>, kwargs=<a dict>, prio=<int>)
        
    - if `prio` is set the new coroutine will be added in the top of the scheduler queue
    """
    __slots__ = ['coro', 'args','kwargs','prio']
    __doc_all__ = ['__init__']
    def __init__(t, coro, args=None, kwargs=None, prio=priority.DEFAULT):
        t.coro = coro
        t.args = args or ()
        t.kwargs = kwargs or {}
        t.prio = prio
    def __repr__(t):
        return '<%s instance at 0x%X, coro:%s, args: %s, kwargs: %s, prio: %s>' % (t.__class__, id(t), t.coro, t.args, t.kwargs, t.prio)
    
class AddCoro(object):
    __slots__ = ['coro','args','kwargs','prio']
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
    __slots__ = ['coro', 'op', 'prio']
    __doc_all__ = ['__init__']
    def __init__(t, coro, op=None, prio=priority.DEFAULT):
        t.coro = coro
        t.op = op
        t.prio = prio
    def __repr__(t):
        return '<%s instance at 0x%X, coro: %s, op: %s, prio: %s>' % (t.__class__, id(t), t.coro, t.op, t.prio)

class Complete(object):
    __slots__ = ['args','prio']
    __doc_all__ = ['__init__']
    def __init__(t, *args):
        t.args = tuple(args)
        t.prio = priority.DEFAULT
    def __repr__(t):
        return '<%s instance at 0x%X, args: %s, prio: %s>' % (t.__class__, id(t), t.args, t.prio)
    
class Join(object):
    __slots__ = ['coro','_timeout','__weakref__']
    timeout = TimeoutDesc('_timeout')
    __doc_all__ = ['__init__']
    def __init__(t, coro, timeout=None):
        t.coro = coro
        t.timeout = timeout
    def __repr__(t):
        return '<%s instance at 0x%X, coro: %s>' % (t.__class__, id(t), t.coro)

    
class Sleep(object):
    """
    Usage
    
    .. sourcecode:: python
    
        yield events.Sleep(time_object)
        
    - timeoject - a datetime or timedelta object, or a number of seconds
        
    .. sourcecode:: python
    
        yield events.Sleep(timestamp=ts)
        
    - ts - a timestamp
    """
    __slots__ = ['wake_time','coro']
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
