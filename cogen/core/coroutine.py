import types
import sys
import gc
from cogen.core import events
from cogen.core.util import *

def coroutine(func):
    def make_new_coroutine(*args, **kws):
        return Coroutine(func, *args, **kws)
    return make_new_coroutine
    
class Coroutine:
    ''' 
        We need a coroutine wrapper for generators and function alike because
        we want to run functions that don't return generators just like a coroutine 
    '''
    STATE_NEED_INIT, STATE_RUNNING, STATE_COMPLETED, STATE_FAILED = range(4)
    _state_names = "notstarted", "running", "completed", "failed"
    __slots__ = ['f_args','f_kws']
    def __init__(t, coro, *args, **kws):
        t.f_args = args
        t.f_kws = kws
        if t._valid_gen(coro):
            t.state = t.STATE_RUNNING
            t.name = coro.gi_frame.f_code.co_name
        elif callable(coro):
            t.state = t.STATE_NEED_INIT
            t.name = coro.func_name
        else:
            t.state = t.STATE_FAILED
            t.exception = ValueError("Bad generator")
            raise t.exception 
        t.coro = coro
        t.caller = t.prio = None
        t.waiters = []
    def add_waiter(t, coro):
        assert t.state < t.STATE_COMPLETED
        assert coro not in t.waiters
        t.waiters.append((t, coro))
    def remove_waiter(t, coro):
        try:
            t.waiters.remove((t, coro))
        except ValueError:
            pass
        
    def _valid_gen(t, coro):
        if isinstance(coro, types.GeneratorType):
            return True
        elif hasattr(coro, 'send') and \
             hasattr(coro, 'throw'):
            return True
    def _run_completion(t):
        coros = []
        if t.caller:
            coros.append((t, t.caller))
        if t.waiters:
            coros.extend(t.waiters)
        t.waiters = None
        t.caller = None
        return events.Complete(*coros)
    running = property(lambda t: t.state < t.STATE_COMPLETED)
    #~ @debug(0)        
    def run_op(t, op): 
        try:
            if t.state == t.STATE_RUNNING:
                if isinstance(op, events.CoroutineException):
                    rop = t.coro.throw(*op.message)
                else:
                    rop = t.coro.send(getattr(op, 'result', op))
            elif t.state == t.STATE_NEED_INIT:
                assert op is None
                t.coro = t.coro(*t.f_args, **t.f_kws)
                del t.f_args
                del t.f_kws 
                if t._valid_gen(t.coro):
                    t.state = t.STATE_RUNNING
                    rop = None
                else:
                    t.state = t.STATE_COMPLETED
                    t.result = t.coro
                    t.coro = None
                    rop = t._run_completion()
            else:
                return None
                
        except StopIteration, e:
            t.state = t.STATE_COMPLETED
            t.result = e.message
            if hasattr(t.coro, 'close'): t.coro.close()
            rop = t._run_completion()
            
        except:
            t.state = t.STATE_FAILED
            t.result = None
            t.exception = sys.exc_info()
            if hasattr(t.coro, 'close'): t.coro.close()
            if t.caller:
                if t.waiters:
                    rop = t._run_completion()
                else:
                    rop = events.Pass(t.caller, events.CoroutineException(t.exception), prio=t.prio)
                t.waiters = None
                t.caller = None
            else:
                t.handle_error()
                rop = t._run_completion()
        return rop
    def handle_error(t):        
        print 
        print '-'*40
        print 'Exception happened during processing of coroutine.'
        import traceback
        traceback.print_exc()
        print "Coroutine %s killed. " % t
        print '-'*40
        
    def __repr__(t):
        return "<%s Coroutine instance at 0x%08X, state: '%s'>" % (t.name, id(t), t._state_names[t.state])
        
if __name__ == "__main__":
    @coroutine
    def some_func():
        pass
    
    print some_func()
    print repr(some_func())
