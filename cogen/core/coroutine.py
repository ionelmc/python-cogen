import types
import sys
import events
import gc

def coroutine(func):
    def make_new_coroutine(*args, **kws):
        return Coroutine(func, *args, **kws)
    return make_new_coroutine
    
class Coroutine:
    ''' We need a coroutine wrapper for generators and function alike because
    we want to run functions that don't return generators just like a coroutine 
    '''
    STATE_NEED_INIT, STATE_RUNNING, STATE_COMPLETED, STATE_FAILED = range(4)
    _state_names = "need init", "running", "completed", "failed"
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
        #~ print '>', t, sys.getrefcount(t), gc.get_referrers(t)
        return events.Complete(*coros)
    def run_op(t, op):        
        #~ print 'Run op: %r on coro: %r' % (op, t)
        assert t.state < t.STATE_COMPLETED
        try:
            if t.state == t.STATE_RUNNING:
                if isinstance(op, Exception):
                    rop = t.coro.throw(*op.message)
                else:
                    rop = t.coro.send(op)
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
                raise RuntimeError("Can't run %s coro." % t._state_names[t.state])
                
        except StopIteration, e:
            t.state = t.STATE_COMPLETED
            t.result = e.message
            rop = t._run_completion()
            
        except:
            t.state = t.STATE_FAILED
            t.exception = Exception(sys.exc_info())
            if t.caller:
                rop = t.prio, events.Pass(t.caller, t.exception)
                t.waiters = None
                t.caller = None
            else:
                t.handle_error(op)
                rop = t._run_completion()
        return rop
    def handle_error(t, inner=None):        
        print 
        print '-'*40
        print 'Exception happened during processing of coroutine.'
        import traceback
        traceback.print_exc()
        print "   BTW, %s died. " % t
        if isinstance(inner, Exception):
            print ' -- Inner exception -- '
            traceback.print_exception(*inner.message)
            print ' --------------------- ' 
        else:
            print "Operation was: %s" % inner
        print '-'*40
        
    def __repr__(t):
        return "<%s Coroutine instance at 0x%08X, state: '%s'>" % (t.name, id(t), t._state_names[t.state])
        
if __name__ == "__main__":
    @coroutine
    def some_func():
        pass
    
    print some_func()
    print repr(some_func())