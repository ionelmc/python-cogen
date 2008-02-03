""" 
Coroutine related boilerplate and wrappers.
"""

import types
import sys
import gc
from cogen.core import events
from cogen.core.util import debug, TimeoutDesc, priority

def coroutine(func):
    """ 
    A decorator function for generators.
    Example:
    
    {{{
    @coroutine
    def plain_ol_generator():
        yield bla
        yield bla
        ...
    }}}
    """
    def make_new_coroutine(*args, **kws):
        return Coroutine(func, *args, **kws)
    make_new_coroutine.__name__ = func.__name__
    make_new_coroutine.__doc__ = func.__doc__
    make_new_coroutine.__module__ = func.__module__ 
    return make_new_coroutine


class Coroutine(object):
    ''' 
    We need a coroutine wrapper for generators and function alike because
    we want to run functions that don't return generators just like a
    coroutine 
    '''
    STATE_NEED_INIT, STATE_RUNNING, STATE_COMPLETED, STATE_FAILED = range(4)
    _state_names = "notstarted", "running", "completed", "failed"
    __slots__ = [ 
        'f_args', 'f_kws', 'name', 'state', 
        'exception', 'coro', 'caller', 'waiters', 'result',
        'prio', 'handle_error', '__weakref__',
    ]
    running = property(lambda self: self.state < self.STATE_COMPLETED)
    
    def __init__(self, coro, *args, **kws):
        self.f_args = args
        self.f_kws = kws
        if self._valid_gen(coro):
            self.state = self.STATE_RUNNING
            self.name = coro.gi_frame.f_code.co_name
        elif callable(coro):
            self.state = self.STATE_NEED_INIT
            self.name = coro.func_name
        else:
            self.state = self.STATE_FAILED
            self.exception = ValueError("Bad generator")
            raise self.exception 
        self.coro = coro
        self.caller = self.prio = None
        self.waiters = []
    
    def add_waiter(self, coro):
        assert self.state < self.STATE_COMPLETED
        assert coro not in self.waiters
        self.waiters.append((self, coro))

    def remove_waiter(self, coro):
        try:
            self.waiters.remove((self, coro))
        except ValueError:
            pass
        
    def _valid_gen(self, coro):
        if isinstance(coro, types.GeneratorType):
            return True
        elif hasattr(coro, 'send') and \
             hasattr(coro, 'throw'):
            return True
    
    def _run_completion(self):
        coros = []
        if self.caller:
            coros.append((self, self.caller))
        if self.waiters:
            coros.extend(self.waiters)
        self.waiters = None
        self.caller = None
        return events.Complete(*coros)
    
    def finalize(self):
        return self.result
    
    #~ @debug(0)
    def run_op(self, op): 
        assert self.state < self.STATE_COMPLETED, \
            "Coroutine at 0x%X called but it is %s state !" % (
                id(self), 
                self._state_names[self.state]
            )
        try:
            if self.state == self.STATE_RUNNING:
                if isinstance(op, events.CoroutineException):
                    rop = self.coro.throw(*op.message)
                else:
                    rop = self.coro.send(op and op.finalize())
            elif self.state == self.STATE_NEED_INIT:
                assert op is None
                self.coro = self.coro(*self.f_args, **self.f_kws)
                del self.f_args
                del self.f_kws 
                if self._valid_gen(self.coro):
                    self.state = self.STATE_RUNNING
                    rop = None
                else:
                    self.state = self.STATE_COMPLETED
                    self.result = self.coro
                    self.coro = None
                    rop = self._run_completion()
            else:
                return None
                
        except StopIteration, e:
            self.state = self.STATE_COMPLETED
            self.result = e.message
            if hasattr(self.coro, 'close'): self.coro.close()
            rop = self._run_completion()
            
        except:
            #~ import traceback
            #~ traceback.print_exc()
            self.state = self.STATE_FAILED
            self.result = None
            self.exception = sys.exc_info()
            if hasattr(self.coro, 'close'): self.coro.close()
            if self.caller:
                if self.waiters:
                    rop = self._run_completion()
                else:
                    rop = events.Pass(
                        self.caller, 
                        events.CoroutineException(self.exception), 
                        prio=self.prio
                    )
                self.waiters = None
                self.caller = None
            else:
                self.handle_error()
                rop = self._run_completion()
        return rop

    def handle_error(self):        
        print>>sys.stderr, '-'*40
        print>>sys.stderr, 'Exception happened during processing of coroutine.'
        import traceback
        traceback.print_exc()
        print>>sys.stderr, "Coroutine %s killed. " % self
        print>>sys.stderr, '-'*40
        
    def __repr__(self):
        return "<%s Coroutine instance at 0x%08X, state: '%s'>" % (
            self.name, 
            id(self), 
            self._state_names[self.state]
        )
        
if __name__ == "__main__":
    @coroutine
    def some_func():
        pass
    
    print some_func()
    print repr(some_func())