""" 
Coroutine related boilerplate and wrappers.
"""
__all__ = ['local', 'coro', 'coroutine', 'Coroutine', 'CoroutineInstance', 'CoroutineException']

import types
import sys
import traceback
        
import events
from util import priority

ident = None

class local(object):
    """A threadlocal-like object that works in the context of coroutines.
    That means, the current running coroutine has the _ident_.
    
    Coroutine.run_op sets the indent before running a step and unsets after.
    
    Example:
    
    .. sourcecode:: python
    
        loc = local() 
        loc.foo = 1

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
        return "<coroutine.local at 0x%X %r>" % (id(self), self.__dict__['__objs'])

class CoroutineException(Exception):
    """This is used intenally to carry exception state in the poller and 
    scheduler."""
    prio = priority.DEFAULT
    def __str__(self):
        return "<%s [[[%s]]]>" % (
            self.__class__.__name__, 
            len(self.args)==3 and traceback.format_exception(*self.args) or
            traceback.format_exception_only(*self.args)
        )

class CoroutineInstance(events.Operation):
    ''' 
    We need a coroutine wrapper for generators and functions alike because
    we want to run functions that don't return generators just like a
    coroutine, also, we do some exception handling here.
    '''
    STATE_NEED_INIT, STATE_RUNNING, STATE_COMPLETED, \
        STATE_FAILED, STATE_FINALIZED = range(5)
    _state_names = "NOTSTARTED", "RUNNING", "COMPLETED", "FAILED", "FINALIZED"
    __slots__ = (
        'f_args', 'f_kws', 'name', 'state', 
        'exception', 'coro', 'caller', 'waiters', 'result',
        'prio', '__weakref__', 'lastop', 'debug', 'run_op',
    )
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
        self.caller = None
        self.prio = priority.FIRST
        self.waiters = []
        self.exception = None
    
    def add_waiter(self, coro, op=None):
        assert self.state < self.STATE_COMPLETED
        assert coro not in self.waiters
        self.waiters.append((op or self, coro))

    def remove_waiter(self, coro, op=None):
        try:
            self.waiters.remove((op or self, coro))
        except ValueError:
            pass
        
    def _valid_gen(self, coro):
        if isinstance(coro, types.GeneratorType):
            return True
        elif hasattr(coro, 'send') and \
             hasattr(coro, 'throw'):
            return True
    
    def finalize(self, sched):
        self.state = self.STATE_FINALIZED
        return self.result
    
    def process(self, sched, coro):
        assert self.state < self.STATE_FINALIZED, \
            "%s called, expected state less than %s!" % (
                self, 
                self._state_names[self.STATE_FINALIZED]
            )
        if self.state == self.STATE_NEED_INIT:
            self.caller = coro
            if coro.debug:
                self.debug = True
            return None, self
        else:
            if self.caller:
                if self.waiters:    
                    if sched.default_priority:
                        sched.active.extendleft(self.waiters)
                    else:
                        sched.active.extend(self.waiters)
                    self.waiters = None
                
                try:
                    if self.exception:
                        return CoroutineException(*self.exception), self.caller
                    else:                
                        return self, self.caller
                finally:
                    self.caller = None
            else:
                if self.waiters:    
                    lucky_waiter = self.waiters.pop()
                    
                    if sched.default_priority:
                        sched.active.extendleft(self.waiters)
                    else:
                        sched.active.extend(self.waiters)
                    
                    self.waiters = []
                    
                    return lucky_waiter
                
                
    def run_op(self, op, sched): 
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
                self, isinstance(op, CoroutineException) and op or 
                (hasattr(op, 'state') and {0:'RUNNING', 1:'FINALIZED', 2:'ERRORED'}[op.state] or 'NOP'), op,
                self._state_names[self.state],
                self._state_names[self.STATE_COMPLETED]
            )
        #~ assert self.state < self.STATE_COMPLETED, \
            #~ "%s called with:%s, last one:%s, expected state less than %s!" % (
                #~ self, 
                #~ op,
                #~ isinstance(self.lastop, CoroutineException) and ''.join(traceback.format_exception(*self.lastop.message)) or self.lastop,
                #~ self._state_names[self.STATE_COMPLETED]
            #~ )
        #~ self.lastop = op
        if self.debug:
            print 
            if isinstance(op, CoroutineException):
                print 'Running %r with exception:' % self,
                if len(op.args) == 3:
                    print '[[['
                    traceback.print_exception(*op.args)
                    print ']]]'
                else:
                    print op.args
            else:
                print 'Running %r with: %r' % (self, op)
        global ident
        ident = self
        try:
            if self.state == self.STATE_RUNNING:
                if self.debug:
                    traceback.print_stack(self.coro.gi_frame)
                if isinstance(op, CoroutineException):
                    rop = self.coro.throw(*op.args)
                else:
                    rop = self.coro.send(op and op.finalize(sched))
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
            self.result = e.args and e.args[0]
            if hasattr(self.coro, 'close'): 
                self.coro.close()
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
                self.handle_error(op)
            rop = self
            sys.exc_clear()
        finally:
            ident = None
        if self.debug:
            print "Yields %s." % rop
        return rop
    def handle_error(self, op):        
        print>>sys.stderr, '-'*40
        print>>sys.stderr, 'Exception happened during processing of coroutine.'
        traceback.print_exception(*self.exception)
        print>>sys.stderr, "Coroutine %s killed. Last op: %s" % (self, op)
        print>>sys.stderr, '-'*40
        
    def __repr__(self):
        return "<%s %s instance at 0x%08X wrapping %r, state: %s>" % (
            self.name, 
            self.__class__.__name__,
            id(self), 
            self.coro,
            self._state_names[self.state]
        )
    __str__ = __repr__

class CoroutineDocstring(object):
    """
    Evil class to make docstrings accesable on different places like:
    
      - the Corutine class
      - the Coroutine instance
      - the Coroutine instance as a descriptor (that means as a method in a class)
    
    """
    def __init__(self, doc):
        self.doc = doc
        
    def __get__(self, inst, ownr):
        if inst:
            return inst.wrapped_func.__doc__
        else:
            return self.doc
        
        
class Coroutine(object):
    __doc__ = CoroutineDocstring(""" 
    A decorator function for generators.
    Example::

        @coroutine
        def plain_ol_generator():
            yield bla
            yield bla
            ...
    """)
    __slots__ = ('wrapped_func', 'constructor')
    def __init__(self, func, constructor=CoroutineInstance):
        self.wrapped_func = func
        self.constructor = constructor
        
    @property
    def __name__(self):
        #~ if hasattr(self, 'wrapped_func'):
            return self.wrapped_func.__name__
        #~ else:
            #~ return self.__name__
    
    def __repr__(self):
        return "<Coroutine constructor at 0x%08X wrapping %r>" % (
            id(self), 
            self.wrapped_func,
        )
    __str__ = __repr__
    
    def __get__(self, instance, owner):
        """
        Previously coroutine was a simple function-based decorator but we needed
        something like an instance (in order to expose the constructor and so on).
        Decorating methods with a class, however need that class to be an 
        descriptor as the __call__ doesn't get automaticaly binded to the instance
        as functions do - btw, functions are decorators.
        """
        return self.__class__(self.wrapped_func.__get__(instance or owner))
        
    def __call__(self, *args, **kwargs):
        "Return a CoroutineInstance instance" # funny wording
        return self.constructor(self.wrapped_func, *args, **kwargs)
           
coro = coroutine = Coroutine

class DebugCoroutine(Coroutine):
    def __call__(self, *args, **kwargs):
        "Return a CoroutineInstance instance"
        inst = self.constructor(self.wrapped_func, *args, **kwargs)
        inst.debug = True
        return inst

debug_coro = debug_coroutine = DebugCoroutine

if __name__ == "__main__":
    @Coroutine
    def some_func():
        "blablalbla"
        pass
    
    class Foo:
        @Coroutine
        def some_func(*args):
            "Foo blablalbla"
            print args
        
    print some_func()
    print repr(some_func)
    print `some_func.__doc__`
    print `some_func`

    print `Coroutine.__doc__`
    print '>', `Coroutine.__name__`
    print `Coroutine`
    
    print `Foo.some_func.__doc__`
    print `Foo.some_func`
    
    Foo.some_func(3,2,1).run_op(None)
    
    foo = Foo()
    
    print `foo.some_func.__doc__`
    print `foo.some_func`
    
    foo.some_func(3,2,1).run_op(None)