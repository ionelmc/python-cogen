"""
Mischelaneous or common.
"""
__all__ = ['debug', 'priority', 'fmt_list']

import datetime
import sys

                
def debug(trace=True, backtrace=1, other=None):
    """A decorator for debugging purposes. Shows the call arguments, result
    and instructions as they are runned."""
    from pprint import pprint
    import traceback
    def debugdeco(func):
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

    
class TimeoutDesc(object):
    __doc_all__ = []
    __slots__ = ['field']
    def __get__(self, instance, owner):
        return instance._timeout
    def __set__(self, instance, val):
        if val and val != -1 and not isinstance(val, datetime.datetime):
            now = datetime.datetime.now()
            if isinstance(val, datetime.timedelta):
                val = now+val
            else:
                val = now+datetime.timedelta(seconds=val)
        instance._timeout = val

class priority(object):  
    """
    How these priority flags are interpreted depends largely on the operation 
    (since that's where these are checked).
    
    ======== ===================================================================
    Property Description 
    ======== ===================================================================
    DEFAULT  Use the default_priority set in the Scheduler
    -------- -------------------------------------------------------------------
    LAST, 
    NOPRIO   Allways scheduler the operation/coroutine at the end of the queue 
    -------- -------------------------------------------------------------------
    CORO     Favor the coroutine - if it's the case. 
    -------- -------------------------------------------------------------------
    OP       Favor the operation - if it's the case. 
    -------- -------------------------------------------------------------------
    FIRST, 
    PRIO     Allways schedule with priority
    ======== ===================================================================
    
    """
    __doc_all__ = []
    DEFAULT = -1    
    LAST  = NOPRIO = 0
    CORO  = 1
    OP    = 2
    FIRST = PRIO = 3

def fmt_list(lst, lim=100):
    if sum(len(i) for i in lst) > lim:
        ret = []
        length = 0
        for i in lst:
            if length+len(i)>lim:
                ret.append(i[:lim-length] + ' ...')
                break
            else:
                ret.append(i)
            length += len(i)
        post = ''
        if len(ret) < len(lst):
            post = " .. %s more" % (len(lst)-len(ret))
        return "[%s%s]"%(', '.join(repr(i) for i in ret), post)
    else:
        return repr(lst)