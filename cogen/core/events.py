import datetime
from cogen.core.const import *

class SimpleAttrib:
    def __init__(t, **kws):
        t.__dict__.update(kws)
class SimpleArgs:
    def __init__(t, *args, **kws):
        t.args = tuple(args)
        t.kws = kws
    def __repr__(t):
        return '<%s args:%r kws:%r>' % (t.__class__.__name__, t.args, t.kws)



class WaitForSignal(object):
    __slots__ = ['name','prio']
    def __init__(t, name, prio=priority.DEFAULT):
        t.name = name
        t.prio = prio
class Signal(object):
    __slots__ = ['name','prio']
    def __init__(t, name, prio=priority.DEFAULT):
        t.name = name
        t.prio = prio
class Call(object):
    __slots__ = ['coro', 'args','kwargs','prio']
    def __init__(t, coro, args=(), kwargs={}, prio=priority.DEFAULT):
        t.coro = coro
        t.args = tuple(args)
        t.kwargs = dict(kwargs)
        t.prio = prio
    def __repr__(t):
        return '<%s instance at 0x%X, coro:%s, args: %s, kwargs: %s, prio: %s>' % (t.__class__.__name__, id(t), t.coro, t.args, t.kwargs, t.prio)
    
class AddCoro(object):
    __slots__ = ['coro','args','kwargs','prio']
    def __init__(t, coro, args=(), kwargs={}, prio=priority.DEFAULT):
        t.coro = coro
        t.args = tuple(args)
        t.kwargs = dict(kwargs)
        t.prio = prio
    def __repr__(t):
        return '<%s instance at 0x%X, coro:%s, args: %s, kwargs: %s, prio: %s>' % (t.__class__.__name__, id(t), t.coro, t.args, t.kwargs, t.prio)

class Pass(object):
    __slots__ = ['coro', 'op', 'prio']
    def __init__(t, coro, op = None, prio=priority.DEFAULT):
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
    
class Join:
    __slots__ = ['coro']
    def __init__(t, coro):
        t.coro = coro
    def __repr__(t):
        return '<%s instance at 0x%X, coro: %s>' % (t.__class__.__name__, id(t), t.coro)

    
class Sleep:
    __slots__ = ['wake_time']
    def __init__(t, val):
        if isinstance(val, datetime.timedelta):
            t.wake_time = datetime.datetime.now() + val
        elif isinstance(val, datetime.datetime):
            t.wake_time = val
        else:
            t.wake_time = datetime.datetime.fromtimestamp(int(val))
    def __cmp__(t, other):
        return cmp(t.wake_time, other.wake_time)
