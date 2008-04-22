""" 
Coroutine related boilerplate and wrappers.
"""
__all__ = ['local', 'Coroutine', 'coro', 'coroutine']

import types
import sys

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
coro = coroutine

def debug_coroutine(func):
    def make_new_coroutine(*args, **kws):
        c = Coroutine(func, *args, **kws)
        c.debug = True
        return c
    make_new_coroutine.__name__ = func.__name__
    make_new_coroutine.__doc__ = func.__doc__
    make_new_coroutine.__module__ = func.__module__ 
    return make_new_coroutine

ident = None

class local(object):
    """A threadlocal-like object that works in the context of coroutines.
    That means, the current running coroutine has the _ident_.
    
    Coroutine.run_op sets the indent before running a step and unsets after.
    
    Example:
    {{{
    loc = local() 
    loc.foo = 1
    }}}
    The *loc* instance's values will be different for separate coroutines.
    """
    def __init__(self):
        self.__dict__['__objs'] = {}
    def __getattr__(self, attr):
        try:
            return self.__dict__['__objs'][ident][attr]
        except KeyError:
            raise AttributeError(
                "No variable %s defined for the thread %s" % (attr, ident))
    def __setattr__(self, attr, value):
        self.__dict__['__objs'].setdefault(ident, {})[attr] = value
    def __delattr__(self, attr):
        try:
            del self.__dict__['__objs'][ident][attr]
        except KeyError:
            raise AttributeError(
                "No variable %s defined for thread %s" % (attr, ident))
    def __repr__(self):
        return "<coroutine.local at 0x%X %r>"%(id(self), self.__dict__['__objs'])

class Coroutine(events.Operation):
    ''' 
    We need a coroutine wrapper for generators and function alike because
    we want to run functions that don't return generators just like a
    coroutine.
    '''
    STATE_NEED_INIT, STATE_RUNNING, STATE_COMPLETED, \
        STATE_FAILED, STATE_FINALIZED = range(5)
    _state_names = "NOTSTARTED", "RUNNING", "COMPLETED", "FAILED", "FINALIZED"
    __slots__ = [ 
        'f_args', 'f_kws', 'name', 'state', 
        'exception', 'coro', 'caller', 'waiters', 'result',
        'prio', 'handle_error', '__weakref__',
        'lastop', 'debug'
    ]
    running = property(lambda self: self.state < self.STATE_COMPLETED)
    
    def __init__(self, coro, *args, **kws):
        self.debug = False
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
        self.exception = None
    
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
    
    def finalize(self):
        self.state = self.STATE_FINALIZED
        return self.result
        
    def process(self, sched, coro):
        assert self.state < self.STATE_FINALIZED, \
            "%s called, expected state less than %s!" % (
                self, 
                self._state_names[self.STATE_FINALIZED]
            )
        if self.waiters:    
            if sched.default_priority:
                sched.active.extendleft(self.waiters)
            else:
                sched.active.extend(self.waiters)
        self.waiters = []
        if self.caller:
            try:
                if self.exception:
                    return events.CoroutineException(self.exception), self.caller
                else:                
                    return self, self.caller
            finally:
                self.caller = None

    #~ @debug(0)
    def run_op(self, op): 
        """
        Handle the operation:
          * if coro is in STATE_RUNNING, send or throw the given op
          * if coro is in STATE_NEED_INIT, call the init function and if it 
          doesn't return a generator, set STATE_COMPLETED and set the result
          to whatever the function returned. 
            * if StopIteration is raised, set STATE_COMPLETED and return self.
            * if any other exception is raised, set STATE_FAILED, handle error
            or send it to the caller, return self
        
        Return self is used as a optimization. Coroutine is also a Operation 
        which handles it's own completion (resuming the caller and the waiters).
        """
        if op is self:
            import warnings
            warnings.warn("Running coro %s with itself. Something is fishy."%op)
        assert self.state < self.STATE_COMPLETED, \
            "%s called with %s op %r, coroutine state (%s) should be less than %s!" % (
                self, {0:'RUNNING', 1:'FINALIZED', 2:'ERRORED'}[op.state], op,
                self._state_names[self.state],
                self._state_names[self.STATE_COMPLETED]
            )
        #~ assert self.state < self.STATE_COMPLETED, \
            #~ "%s called with:%s, last one:%s, expected state less than %s!" % (
                #~ self, 
                #~ op,
                #~ isinstance(self.lastop, events.CoroutineException) and ''.join(traceback.format_exception(*self.lastop.message)) or self.lastop,
                #~ self._state_names[self.STATE_COMPLETED]
            #~ )
        #~ self.lastop = op
        if self.debug:
            print 'Running %s with: %s' % (self, op)
        global ident
        ident = self
        try:
            if self.state == self.STATE_RUNNING:
                if self.debug:
                    import traceback
                    print traceback.print_stack(self.coro.gi_frame)
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
                    rop = self
            else:
                return None
                
        except StopIteration, e:
            self.state = self.STATE_COMPLETED
            self.result = e.message
            if hasattr(self.coro, 'close'): self.coro.close()
            rop = self
        except (KeyboardInterrupt, GeneratorExit, SystemExit):
            raise
        except:
            self.state = self.STATE_FAILED
            self.result = None
            self.exception = sys.exc_info()
            if hasattr(self.coro, 'close'): 
                self.coro.close()
            if not self.caller:
                self.handle_error()
            rop = self
            sys.exc_clear()
        finally:
            ident = None
        return rop
    def handle_error(self):        
        print>>sys.stderr, '-'*40
        print>>sys.stderr, 'Exception happened during processing of coroutine.'
        import traceback
        traceback.print_exc()
        print>>sys.stderr, "Coroutine %s killed. " % self
        print>>sys.stderr, '-'*40
        
    def __repr__(self):
        return "<%s Coroutine instance at 0x%08X wrapping %r, state: %s>" % (
            self.name, 
            id(self), 
            self.coro,
            self._state_names[self.state]
        )
        
if __name__ == "__main__":
    @coroutine
    def some_func():
        pass
    
    print some_func()
    print repr(some_func())
