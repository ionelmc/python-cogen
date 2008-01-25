import datetime
import sys
import traceback

                
def debug(trace=True, backtrace=1, other=None):
    from pprint import pprint
    def debugdeco(func):
        """A decorator for debugging purposes. Shows the call arguments, result
        and instructions as they are runned."""
        def tracer(frame, event, arg):
            print '--- Tracer: %s, %r' % (event, arg)
            traceback.print_stack(frame, 1)
            return tracer
        def wrapped(*a, **k):
            print 
            print '--- Calling %s.%s with:' % (
                getattr(func, '__module__', ''), 
                func.__name__
            )
            for i in enumerate(a):
                print '    | %s: %s' % i
            print '    | ',
            pprint(k)
            print '    From:'
            for i in traceback.format_stack(sys._getframe(1), backtrace):
                print i,
            if other:
                print '---      [ %r ]' % (other(func,a,k))
            if trace: sys.settrace(tracer)
            ret = func(*a, **k)
            if trace: sys.settrace(None)
            #~ a = list(a)
            print '--- %s.%s returned: %r' % (
                getattr(func, '__module__', ''), 
                func.__name__, 
                #~ ret not in a and ret or "ARG%s"%a.index(ret)
                ret
            )
            return ret
        return wrapped
    return debugdeco

#~ @debug(0)
#~ def test1():
    #~ test2()

#~ @debug(0)
#~ def test2():
    #~ print 1

#~ test1()
    
class TimeoutDesc(object):
    __doc_all__ = []
    __slots__ = ['field']
    def __init__(self, field):
        self.field = field
    def __get__(self, instance, owner):
        return getattr(instance, self.field, None)
    def __set__(self, instance, val):
        if val and val != -1 and not isinstance(val, datetime.datetime):
            now = datetime.datetime.now()
            if isinstance(val, datetime.timedelta):
                val = now+val
            else:
                val = now+datetime.timedelta(seconds=val)
        setattr(instance, self.field, val)

class priority(object):  
    """
    ============ ===============================================================
    Property     Description
    ============ ===============================================================
    DEFAULT       Use the default_priority set in the Scheduler
    ------------ ---------------------------------------------------------------
    LAST, NOPRIO  Allways scheduler the operation/coroutine at the end of the
                  queue   
    ------------ ---------------------------------------------------------------
    CORO          Favor the coroutine - if it's the case.
    ------------ ---------------------------------------------------------------
    OP            Favor the operation - if it's the case.
    ------------ ---------------------------------------------------------------
    FIRST, PRIO   Allways schedule with priority
    ============ ===============================================================
    
    """
    __doc_all__ = []
    DEFAULT = -1    
    LAST  = NOPRIO = 0
    CORO  = 1
    OP    = 2
    FIRST = PRIO = 3
