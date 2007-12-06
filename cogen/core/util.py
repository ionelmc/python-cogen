import datetime
import sys
import traceback

                
def debug(trace=True, other=None):
    def debugdeco(func):
        "A decorator for debugging purposes. Shows the call arguments, result and instructions as they are runned."
        def tracer(frame, event, arg):
            print '--- Tracer: %s, %r' % (event, arg)
            traceback.print_stack(frame, 1)
            return tracer
        def wrapped(*a, **k):
            print '--- Calling %s.%s with: %s %s' % (func.__module__, func.__name__, a, k)
            if other:
                print '---      [ %r ]' % (other(func,a,k))
            if trace: sys.settrace(tracer)
            ret = func(*a, **k)
            if trace: sys.settrace(None)
            print '--- %s.%s returned: %r' % (func.__module__, func.__name__, ret)
            return ret
        return wrapped
    return debugdeco
class TimeoutDesc(object):
    __doc_all__ = []
    __slots__ = ['field']
    def __init__(t, field):
        t.field = field
    def __get__(t, instance, owner):
        return getattr(instance, t.field, None)
    def __set__(t, instance, val):
        if val and val != -1 and not isinstance(val, datetime.datetime):
            now = datetime.datetime.now()
            if isinstance(val, datetime.timedelta):
                val = now+val
            else:
                val = now+datetime.timedelta(seconds=val)
        setattr(instance, t.field, val)

class priority(object):  
    """
    ============ =====================================================================
    Property     Description
    ============ =====================================================================
    DEFAULT       Use the default_priority set in the Scheduler
    ------------ ---------------------------------------------------------------------
    LAST, NOPRIO  Allways scheduler the operation/coroutine at the end of the queue
    ------------ ---------------------------------------------------------------------
    CORO          Favor the coroutine - if it's the case.
    ------------ ---------------------------------------------------------------------
    OP            Favor the operation - if it's the case.
    ------------ ---------------------------------------------------------------------
    FIRST, PRIO   Allways schedule with priority
    ============ =====================================================================
    
    """
    __doc_all__ = []
    DEFAULT = -1    
    LAST  = NOPRIO = 0
    CORO  = 1
    OP    = 2
    FIRST = PRIO = 3
