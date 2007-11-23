import datetime

class SimpleAttrib:
    def __init__(t, **kws):
        t.__dict__.update(kws)
class SimpleArgs:
    def __init__(t, *args, **kws):
        t.args = args
        t.kws = kws
    def __repr__(t):
        return '<SimpleArgs args:%r kws:%r>' % (t.args, t.kws)



class WaitForSignal:
    def __init__(t, name):
        t.name = name
class Signal:
    def __init__(t, name):
        t.name = name
class Call(SimpleArgs):
    pass
    
class AddCoro:
    def __init__(t, *args, **kws):
        t.args = args
        t.keep_running = kws.get('keep_running', True)
    
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
