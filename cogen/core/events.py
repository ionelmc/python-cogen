import datetime

class SimpleAttrib:
    def __init__(t, **kws):
        t.__dict__.update(kws)
class SimpleArgs:
    def __init__(t, *args, **kws):
        t.args = args
        t.kws = kws
    def __repr__(t):
        return '<%s args:%r kws:%r>' % (t.__class__.__name__, t.args, t.kws)
class ConnectionClosed(Exception):
    pass


class WaitForSignal:
    def __init__(t, name):
        t.name = name
class Signal:
    def __init__(t, name):
        t.name = name
class Call(SimpleArgs):
    pass
    
class AddCoro:
    def __init__(t, *args):
        t.args = args
    def __repr__(t):
        return '<%s instance at 0x%X, args: %s>' % (t.__class__.__name__, id(t), t.args)

class Pass:
    def __init__(t, coro, op = None):
        t.coro = coro
        t.op = op

class Complete:
    def __init__(t, *args):
        t.args = args
    def __repr__(t):
        return '<%s instance at 0x%X, args: %s>' % (t.__class__.__name__, id(t), t.args)
    
class Join:
    def __init__(t, coro):
        t.coro = coro
class Semaphore:
    pass #todo

    
class Sleep:
    def __init__(t, val):
        if isinstance(val, datetime.timedelta):
            t.wake_time = datetime.datetime.now() + val
        elif isinstance(val, datetime.datetime):
            t.wake_time = val
        else:
            t.wake_time = datetime.datetime.fromtimestamp(int(val))
    def __cmp__(t, other):
        return cmp(t.wake_time, other.wake_time)
