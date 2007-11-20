import datetime
from lib import *

class WaitForSignal:
    def __init__(t, name):
        t.name = name
class Signal:
    def __init__(t, name):
        t.name = name
class Call(SimpleArgs):
    pass    
class AddCoro(SimpleArgs):
    pass    
class Join:
    def __init__(t, coro):
        t.coro = coro
class Semaphore:
    pass #todo

class Pass:
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
