"""
Coroutine related boilerplate and wrappers.
"""
__all__ = ['corolet']

import sys
import traceback

from py.magic import greenlet
getcurrent = greenlet.getcurrent

from cogen.core import events
from cogen.core.util import priority
from cogen.core import coroutines
from cogen.core.coroutines import CoroutineException


def yield_(op):
    self = getcurrent()
    rop = self.parent.switch(op)
    assert self is getcurrent(), "Something was switched wrong: current is %s but it should be the original yielder (%s)" % (getcurrent(), self)
    return rop

class CoroGreenlet(greenlet):
    __slots__ = ('coro',)

    def __init__(self, coro):
        current = getcurrent()
        super(CoroGreenlet, self).__init__(parent=current.parent or current)
        self.coro = coro

    def run(self, *args, **kwargs):
        """This runs in a greenlet"""
        return_value = self.coro(*args, **kwargs)

        # i don't like this but greenlets are so dodgy i have no other choice
        raise StopIteration(return_value)

        # dead greenlets don't raise exceptions when switched to
        # - they just return the passed value :(

    def __repr__(self):
        return "<%s instance at 0x%08X wrapping %r>" % (
            self.__class__.__name__,
            id(self),
            getattr(self, 'coro', 'N/A'),
        )
    __str__ = __repr__

class CoroletInstance(coroutines.CoroutineInstance):
    '''
    This is patched to work with a greenlet instead of a generator.
    '''
    STATE_NEED_INIT, STATE_RUNNING, STATE_COMPLETED, \
        STATE_FAILED, STATE_FINALIZED = range(5)
    _state_names = "NOTSTARTED", "RUNNING", "COMPLETED", "FAILED", "FINALIZED"
    __slots__ = (
    )
    running = property(lambda self: self.state < self.STATE_COMPLETED)

    def __init__(self, coro, *args, **kws):
        self.debug = False
        self.f_args = args
        self.f_kws = kws

        self.state = self.STATE_NEED_INIT
        self.name = coro.func_name
        self.coro = CoroGreenlet(coro)

        self.caller = None
        self.prio = priority.FIRST
        self.waiters = []
        self.exception = None

    #~ from cogen.core.util import debug as dbg
    #~ @dbg(0)
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
        coroutines.ident = self

        try:
            if self.state == self.STATE_RUNNING:
                if self.debug:
                    traceback.print_stack(self.coro.gr_frame)

                if isinstance(op, CoroutineException):
                    rop = self.coro.throw(*op.args)
                else:
                    rop = self.coro.switch(op and op.finalize())
            elif self.state == self.STATE_NEED_INIT:
                assert op is None
                rop = self.coro.switch(*self.f_args, **self.f_kws)
                self.state = self.STATE_RUNNING

                del self.f_args
                del self.f_kws
            else:
                return None

        except StopIteration, e:
            self.state = self.STATE_COMPLETED
            self.result = e.args and e.args[0]
            #~ del self.coro
            rop = self
        except (KeyboardInterrupt, GeneratorExit, SystemExit):
            raise
        except:
            self.state = self.STATE_FAILED
            self.result = None
            self.exception = sys.exc_info()
            if not self.caller:
                self.handle_error()
            rop = self
            sys.exc_clear()
            #~ del self.coro
        finally:
            coroutines.ident = None
        return rop


class Corolet(coroutines.Coroutine):
    __doc__ = coroutines.CoroutineDocstring("""
    A decorator function for generators.
    Example::

        @corolet
        def plain_ol_func():
            yield_(bla)
            yield_(bla)
            ...
    """)
    __slots__ = ()
    def __init__(self, func, constructor=CoroletInstance):
        super(Corolet, self).__init__(func, constructor)


corolet = Corolet

class DebugCorolet(Corolet):
    def __call__(self, *args, **kwargs):
        "Return a CoroutineInstance instance"
        inst = self.constructor(self.wrapped_func, *args, **kwargs)
        inst.debug = True
        return inst

debug_corolet = DebugCorolet

if __name__ == "__main__":
    from cogen.core.events import Sleep
    from cogen.core.schedulers import Scheduler

    def bar():
        yield_(events.Sleep(1))
        print 2
        raise Exception('BOOOO!!!')

    def foo():
        bar()

    @corolet
    def some_func():
        "blablalbla"
        print 1
        foo()
        print 3


    m = Scheduler()
    m.add(some_func)
    m.run()
