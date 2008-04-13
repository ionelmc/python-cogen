"""
Base events (coroutine operations) and coroutine exceptions.
"""

import datetime
import heapq

from cogen.core.util import debug, TimeoutDesc, priority
#~ getnow = debug(0)(datetime.datetime.now)
getnow = datetime.datetime.now

class CoroutineException(Exception):
    """This is used intenally to carry exception state in the poller and 
    scheduler."""
    __doc_all__ = []
    prio = priority.DEFAULT
    def __init__(self, *args):
        for i in args:
            if isinstance(i, TimedOperation):
                i.finalize()
        super(CoroutineException, self).__init__(*args)

class ConnectionError(Exception):
    "Raised when a socket has a error flag (in epoll or select)"
    __doc_all__ = []
class ConnectionClosed(Exception):
    "Raised when the other peer has closed connection."
    __doc_all__ = []
class OperationTimeout(Exception):
    """Raised when the timeout for a operation expires. The exception 
    message will be the operation"""
    __doc_all__ = []

class Operation(object):
    """All operations derive from this. This base class handles 
    the priority flag. 
    
    Eg:
    
    {{{
    yield Operation(prio=priority.DEFAULT)
    }}}        
    
      * prio - a priority constant, where the coro is appended on the active 
        coroutine queue and how the coroutine is runned depend on this.
    
    If you need something that can't be done in a coroutine fashion you 
    probabily need to subclass this and make a custom operation for your
    issue.
    
    Note: you don't really use this, this is for subclassing for other operations.
    """
    __slots__ = ['prio']
    
    def __init__(self, prio=priority.DEFAULT):
        self.prio = prio
    
    def process(self, sched, coro):
        """This is called when the operation is to be processed by the 
        scheduler. Code here works modifies the scheduler and it's usualy 
        very crafty."""
        
        if self.prio == priority.DEFAULT:
            self.prio = sched.default_priority
    
    def finalize(self):
        """Called just before the Coroutine wrapper passes the operation back
        in the generator. Return value is the value actualy sent in the 
        generator."""
        return self
            

class TimedOperation(Operation):
    """Operations that have a timeout derive from this.
    
    Eg:
    
    {{{
    yield TimedOperation(
        timeout=None, 
        weak_timeout=True,
        prio=priority.DEFAULT
    )
    }}}
    
      * timeout - can be a float/int (number of seconds) or a timedelta or a datetime value
        if it's a datetime the timeout will occur on that moment
      * weak_timeout - strong timeouts just happen when specified, weak_timeouts
        get delayed if some action happens (eg: new but not enough data recieved)
    
    See: [Docs_CogenCoreEventsOperation Operation]
    Note: you don't really use this, this is for subclassing for other operations.
    """
    __slots__ = ['_timeout', '__weakref__', 'finalized', 'weak_timeout']
    timeout = TimeoutDesc()
    
    def __init__(self, timeout=None, weak_timeout=True, **kws):
        super(TimedOperation, self).__init__(**kws)
        if timeout:
            self.timeout = timeout
        else:
            self._timeout = None
        self.finalized = False
        self.weak_timeout = weak_timeout
    
    def finalize(self):
        self.finalized = True
        return self
        
    def process(self, sched, coro):
        super(TimedOperation, self).process(sched, coro)
        
        if not self.timeout:
            self.timeout = sched.default_timeout
        if self._timeout and self._timeout != -1:
            sched.add_timeout(self, coro, False)
            
    def cleanup(self, sched):
        """
        Clean up after a timeout. Implemented in ops that need cleanup.
        If return value evaluated to false the sched won't raise the timeout in 
        the coroutine.
        """
        return True
class WaitForSignal(TimedOperation):
    """The coroutine will resume when the same object is Signaled.
    
    Eg:
    {{{ 
    value = yield events.WaitForSignal(
        name, 
        timeout=None, 
        weak_timeout=True,
        prio=priority.DEFAULT
    )
    }}}
    
      * name - a object to wait on, can use strings for this - string used to 
        wait is equal to the string used to signal.
      * value - a object sent with the signal. see: [Docs_CogenCoreEventsSignal Signal]
      
    See: [Docs_CogenCoreEventsTimedoperation TimedOperation]
    """
        
    __slots__ = ['name', 'result']
    __doc_all__ = ['__init__']
    
    def __init__(self, name, **kws):
        super(WaitForSignal, self).__init__(**kws)
        self.name = name
    
    def process(self, sched, coro):
        super(WaitForSignal, self).process(sched, coro)
        waitlist = sched.sigwait[self.name]
        waitlist.append((self, coro))
        if self.name in sched.signals:
            sig = sched.signals[self.name]
            if sig.recipients <= len(waitlist):
                sig.process(sched, sig.coro)
                del sig.coro
                del sched.signals[self.name]
    
    def finalize(self):
        super(WaitForSignal, self).finalize()
        return self.result
        
    def cleanup(self, sched, coro):
        try:
            sched.sigwait[self.name].remove((self, coro))
        except ValueError:
            pass
        return True
    def __repr__(self):
        return "<%s at 0x%X name:%s timeout:%s prio:%s>" % (
            self.__class__, 
            id(self), 
            self.name, 
            self.timeout, 
            self.prio
        )
class Signal(Operation):
    """
    This will resume the coroutines that where paused with WaitForSignal.
    
    Usage:
    
    {{{
    nr = yield events.Signal(
        name, 
        value,
        prio=priority.DEFAULT
    )
    }}}
    
      * nr - the number of coroutines woken up
      * name - object that coroutines wait on, can be a string 
      * value - object that the waiting coros recieve when they are resumed.
      
    See: [Docs_CogenCoreEventsOperation Operation]
    """
    __slots__ = ['name', 'value', 'len', 'prio', 'result', 'recipients', 'coro']
    __doc_all__ = ['__init__']
    
    def __init__(self, name, value=None, recipients=0, **kws):
        """All the coroutines waiting for this object will be added back in the
        active coroutine queue."""
        super(Signal, self).__init__(**kws)
        self.name = name
        self.value = value
        self.recipients = recipients
    
    def finalize(self):
        super(Signal, self).finalize()
        return self.result
            
    def process(self, sched, coro):
        super(Signal, self).process(sched, coro)
        self.result = len(sched.sigwait[self.name])
        if self.result < self.recipients:
            sched.signals[self.name] = self
            self.coro = coro
            return
            
        for waitop, waitcoro in sched.sigwait[self.name]:
            waitop.result = self.value
        if self.prio & priority.OP:
            sched.active.extendleft(sched.sigwait[self.name])
        else:
            sched.active.extend(sched.sigwait[self.name])
        
        if self.prio & priority.CORO:
            sched.active.appendleft((None, coro))
        else:
            sched.active.append((None, coro))
            
        del sched.sigwait[self.name]        
        
class Call(Operation):
    """
    This will pause the current coroutine, add a new coro in the scheduler and 
    resume the callee when it returns. 
    
    Usage:
    {{{
    result = yield events.Call(mycoro, args=(), kwargs={}, prio=priority.DEFAULT)
    }}}
    
      * mycoro - the coroutine to add.
      * args, kwargs - params to call the coroutine with
      * if `prio` is set the new coroutine will be added in the top of the 
      scheduler queue
      
    See: [Docs_CogenCoreEventsOperation Operation]
    """
    __slots__ = ['coro', 'args', 'kwargs']
    __doc_all__ = ['__init__']

    def __init__(self, coro, args=None, kwargs=None, **kws):
        super(Call, self).__init__(**kws)
        self.coro = coro
        self.args = args or ()
        self.kwargs = kwargs or {}
    
    def process(self, sched, coro):
        super(Call, self).process(sched, coro)
        callee = sched.add(self.coro, self.args, self.kwargs, self.prio) 
        callee.caller = coro
        callee.prio = self.prio
    
    def __repr__(self):
        return '<%s instance at 0x%X, coro:%s, args: %s, kwargs: %s, prio: %s>' % (
            self.__class__, 
            id(self), 
            self.coro, 
            self.args, 
            self.kwargs, 
            self.prio
        )
    
class AddCoro(Operation):
    """
    A operator for adding a coroutine in the scheduler.
    Example:
    
    {{{
    yield events.AddCoro(some_coro, args=(), kwargs={})
    }}}
    
    This is similar to Call, but it doesn't pause the current coroutine.
    See: [Docs_CogenCoreEventsOperation Operation]
    """
    __slots__ = ['coro', 'args', 'kwargs', 'result']
    __doc_all__ = ['__init__']
    def __init__(self, coro, args=None, kwargs=None, **kws):
        super(AddCoro, self).__init__(**kws)
        self.coro = coro
        self.args = args or ()
        self.kwargs = kwargs or {}
    
    def finalize(self):
        super(AddCoro, self).finalize()
        return self.result
    
    def process(self, sched, coro):
        super(AddCoro, self).process(sched, coro)
        self.result = sched.add(self.coro, self.args, self.kwargs, self.prio & priority.OP)
        if self.prio & priority.CORO:
            return self, coro
        else:
            sched.active.append( (None, coro))
    def __repr__(self):
        return '<%s instance at 0x%X, coro:%s, args: %s, kwargs: %s, prio: %s>' % (
            self.__class__, 
            id(self), 
            self.coro, 
            self.args, 
            self.kwargs, 
            self.prio
        )

class Pass(Operation):
    """
    A operation for setting the next (coro, op) pair to be runned by the 
    scheduler. Used internally.
    """
    __slots__ = ['coro', 'op']
    __doc_all__ = ['__init__']
    def __init__(self, coro, op=None, **kws):
        super(Pass, self).__init__(**kws)
        self.coro = coro
        self.op = op
    def process(self, sched, coro):
        super(Pass, self).process(sched, coro)
        return self.op, self.coro
    def __repr__(self):
        return '<%s instance at 0x%X, coro: %s, op: %s, prio: %s>' % (
            self.__class__, 
            id(self), 
            self.coro, 
            self.op, 
            self.prio
        )

class Complete(Operation):
    """
    A operation for adding a list of (coroutine, operator) pairs. Used 
    internally.
    """
    __slots__ = ['args']
    __doc_all__ = ['__init__']
    def __init__(self, *args, **kws):
        super(Complete, self).__init__(**kws)
        self.args = tuple(args)
    def process(self, sched, coro):
        super(Complete, self).process(sched, coro)
        if self.args:
            if self.prio:
                sched.active.extendleft(self.args)
            else:
                sched.active.extend(self.args)
    def __repr__(self):
        return '<%s instance at 0x%X, args: %s, prio: %s>' % (
            self.__class__, 
            id(self), 
            self.args, 
            self.prio
        )
    
class Join(TimedOperation):
    """
    A operation for waiting on a coroutine. 
    Example:
    
    {{{
    @coroutine
    def coro_a():
        return_value = yield events.Join(ref)
        
        
    @coroutine
    def coro_b():
        yield "bla"
        raise StopIteration("some return value")
    
    ref = scheduler.add(coro_b)
    scheduler.add(coro_a)
    }}}
    
    This will pause the coroutine and resume it when the other coroutine 
    (`ref` in the example) has died.
    """
    __slots__ = ['coro']
    __doc_all__ = ['__init__']
    def __init__(self, coro, **kws):
        super(Join, self).__init__(**kws)
        self.coro = coro
    def process(self, sched, coro):
        super(Join, self).process(sched, coro)
        self.coro.add_waiter(coro)
    
    def cleanup(self, sched, coro):
        self.coro.remove_waiter(coro)
        return True
        
    def __repr__(self):
        return '<%s instance at 0x%X, coro: %s>' % (
            self.__class__, 
            id(self), 
            self.coro
        )

    
class Sleep(Operation):
    """
    A operation to pausing the coroutine for a specified amount of time.
    
    Usage:
    
    {{{
    yield events.Sleep(time_object)
    }}}
    
      * time_object - a datetime or timedelta object, or a number of seconds
        
    {{{
    yield events.Sleep(timestamp=ts)
    }}}
    
      * ts - a timestamp
    """
    __slots__ = ['wake_time', 'coro']
    __doc_all__ = ['__init__']
    def __init__(self, val=None, timestamp=None):
        super(Sleep, self).__init__()
        if isinstance(val, datetime.timedelta):
            self.wake_time = getnow() + val
        elif isinstance(val, datetime.datetime):
            self.wake_time = val
        else:
            if timestamp:
                self.wake_time = datetime.datetime.fromtimestamp(int(timestamp))
            else:
                self.wake_time = getnow() + datetime.timedelta(seconds=val)
    def process(self, sched, coro):
        super(Sleep, self).process(sched, coro)
        self.coro = coro
        heapq.heappush(sched.timewait, self)
    def __cmp__(self, other):
        return cmp(self.wake_time, other.wake_time)
        
