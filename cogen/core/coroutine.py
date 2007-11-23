import types
import sys
import events as Events

def coroutine(func):
    return Coroutine(func)
    
class Coroutine:
    STATE_NEED_INIT, STATE_RUNNING, STATE_COMPLETED, STATE_FAILED = range(4)
    _state_names = "need init", "running", "completed", "failed"
    def __init__(t, coro, caller = None, name = None):
        t.name = name
        if t._valid_gen(coro):
            t.state = t.STATE_RUNNING
            t.name = coro.gi_frame.f_code.co_name
        elif callable(coro):
            t.state = t.STATE_NEED_INIT
            t.name = t.name or coro.func_name
        else:
            t.state = t.STATE_FAILED
            t.exception = ValueError("Bad generator")
            raise t.exception 
        t.coro = coro
        t.caller = caller
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
        return Events.AddCoro(*coros, **{'keep_running':False})
    def run_op(t, op):        
        #~ print 'Run op: %s on coro: %s' % (op, t)
        assert t.state < t.STATE_COMPLETED
        try:
            if t.state == t.STATE_RUNNING:
                if isinstance(op, Exception):
                    rop = t.coro.throw(op.message[0])
                else:
                    rop = t.coro.send(op)
            elif t.state == t.STATE_NEED_INIT:
                t.coro = t.coro()
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
                rop = t.caller.run_op(t.exception)
            else:
                t.handle_error(op)
                rop = t._run_completion()
        return rop
        # or Events.Pass
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
    def __str__(t):
        return "<Coroutine %s, state: %s>" % (t.name, t._state_names[t.state])
        
if __name__ == "__main__":
    @coroutine
    def some_func():
        pass
    
    print some_func