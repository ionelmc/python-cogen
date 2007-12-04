import datetime
from cogen.core.util import *

class ConnectionClosed(Exception):
    pass
class OperationTimeout(Exception):
    pass    
class CoroutineException(Exception):
    prio = priority.DEFAULT
    pass


class WaitForSignal(object):
    __slots__ = ['name','prio','_timeout','__weakref__']
    timeout = TimeoutDesc('_timeout')
    def __init__(t, obj, timeout=None, prio=priority.DEFAULT):
        "The coroutine will resume when the same object is Signaled"
        t.name = obj
        t.prio = prio
        t.timeout = timeout
        
class Signal(object):
    __slots__ = ['name','len','prio','result']
    def __init__(t, obj, prio=priority.DEFAULT):
        "All the coroutines waiting for this object will be added back in the active coroutine queue."
        t.name = obj
        t.prio = prio
        
class Call(object):
    __slots__ = ['coro', 'args','kwargs','prio']
    def __init__(t, coro, args=None, kwargs=None, prio=priority.DEFAULT):
        t.coro = coro
        t.args = args or ()
        t.kwargs = kwargs or {}
        t.prio = prio
    def __repr__(t):
        return '<%s instance at 0x%X, coro:%s, args: %s, kwargs: %s, prio: %s>' % (t.__class__.__name__, id(t), t.coro, t.args, t.kwargs, t.prio)
    
class AddCoro(object):
    __slots__ = ['coro','args','kwargs','prio']
    def __init__(t, coro, args=None, kwargs=None, prio=priority.DEFAULT):
        t.coro = coro
        t.args = args or ()
        t.kwargs = kwargs or {}
        t.prio = prio
    def __repr__(t):
        return '<%s instance at 0x%X, coro:%s, args: %s, kwargs: %s, prio: %s>' % (t.__class__.__name__, id(t), t.coro, t.args, t.kwargs, t.prio)

class Pass(object):
    __slots__ = ['coro', 'op', 'prio']
    def __init__(t, coro, op=None, prio=priority.DEFAULT):
        t.coro = coro
        t.op = op
        t.prio = prio
    def __repr__(t):
        return '<%s instance at 0x%X, coro: %s, op: %s, prio: %s>' % (t.__class__.__name__, id(t), t.coro, t.op, t.prio)

class Complete(object):
    __slots__ = ['args','prio']
    def __init__(t, *args):
        t.args = tuple(args)
        t.prio = priority.DEFAULT
    def __repr__(t):
        return '<%s instance at 0x%X, args: %s, prio: %s>' % (t.__class__.__name__, id(t), t.args, t.prio)
    
class Join(object):
    __slots__ = ['coro','_timeout','__weakref__']
    timeout = TimeoutDesc('_timeout')
    def __init__(t, coro, timeout=None):
        t.coro = coro
        t.timeout = timeout
    def __repr__(t):
        return '<%s instance at 0x%X, coro: %s>' % (t.__class__.__name__, id(t), t.coro)

    
class Sleep(object):
    """
    Usage:
        yield events.Sleep(time_object)
        
        timeoject - a datetime or timedelta object, or a number of seconds
        
        yield events.Sleep(timestamp=ts)
        
        ts - a timestamp
    """
    __slots__ = ['wake_time','coro']
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
