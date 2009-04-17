"""
Mischelaneous or common.
"""
__all__ = ['debug', 'priority', 'fmt_list']

import sys

                
def debug(trace=True, backtrace=1, other=None, output=sys.stderr):
    """A decorator for debugging purposes. Shows the call arguments, result
    and instructions as they are runned."""
    from pprint import pprint
    import traceback
    def debugdeco(func):
        def tracer(frame, event, arg):
            print>>output, '--- Tracer: %s, %r' % (event, arg)
            traceback.print_stack(frame, 1, output)
            return tracer
        def wrapped(*a, **k):
            print>>output 
            print>>output, '--- Calling %s.%s with:' % (
                getattr(func, '__module__', ''), 
                func.__name__
            )
            for i in enumerate(a):
                print>>output, '    | %s: %s' % i
            print>>output, '    | ',
            pprint(k, output)
            print>>output, '    From:'
            for i in traceback.format_stack(sys._getframe(1), backtrace):
                print>>output, i,
            if other:
                print>>output, '---      [ %r ]' % (other(func,a,k))
            if trace: sys.settrace(tracer)
            ret = func(*a, **k)
            if trace: sys.settrace(None)
            #~ a = list(a)
            print>>output, '--- %s.%s returned: %r' % (
                getattr(func, '__module__', ''), 
                func.__name__, 
                #~ ret not in a and ret or "ARG%s"%a.index(ret)
                ret
            )
            return ret
        return wrapped
    return debugdeco

    
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
