"""
Base events (coroutine operations) and coroutine exceptions.
"""
__all__ = [
    'CoroutineException', 'ConnectionError', 'ConnectionClosed', 
    'OperationTimeout', 'WaitForSignal', 'Signal', 'Call', 'AddCoro', 
    'Join', 'Sleep', 'Operation', 'TimedOperation', 'OldCall'
]
import datetime
import heapq

from cogen.core.util import debug, priority
#~ getnow = debug(0)(datetime.datetime.now)
getnow = datetime.datetime.now

RUNNING, FINALIZED, ERRORED = range(3)

class CoroutineException(Exception):
    """This is used intenally to carry exception state in the poller and 
    scheduler."""
    prio = priority.DEFAULT
    def __init__(self, *args):
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
    
    .. sourcecode:: python
        
        yield Operation(prio=priority.DEFAULT)
           
    
    * prio - a priority constant, where the coro is appended on the active 
      coroutine queue and how the coroutine is runned depend on this.
    
    If you need something that can't be done in a coroutine fashion you 
    probabily need to subclass this and make a custom operation for your
    issue.
    
    Note: you don't really use this, this is for subclassing for other operations.
    """
    __slots__ = ['prio', 'state']
    
    def __init__(self, prio=priority.DEFAULT):
        self.prio = prio
        self.state = RUNNING
    
    def process(self, sched, coro):
        """This is called when the operation is to be processed by the 
        scheduler. Code here works modifies the scheduler and it's usualy 
        very crafty. Subclasses usualy overwrite this method and call it from
        the superclass."""
        
        if self.prio == priority.DEFAULT:
            self.prio = sched.default_priority
    
    def finalize(self):
        """Called just before the Coroutine wrapper passes the operation back
        in the generator. Return value is the value actualy sent in the 
        generator. Subclasses might overwrite this method and call it from
        the superclass."""
        self.state = FINALIZED
        return self
            

class TimedOperation(Operation):
    """Operations that have a timeout derive from this.
    
    Eg:
    
    .. sourcecode:: python
    
        yield TimedOperation(
            timeout=None, 
            weak_timeout=True,
            prio=priority.DEFAULT
        )
    
    * timeout - can be a float/int (number of seconds) or a timedelta or a datetime value
      if it's a datetime the timeout will occur on that moment
    * weak_timeout - strong timeouts just happen when specified, weak_timeouts
      get delayed if some action happens (eg: new but not enough data recieved)
    
    See: `Operation <cogen.core.events.Operation.html>`_.
    Note: you don't really use this, this is for subclassing for other operations.
    """
    __slots__ = ['timeout', 'coro', 'weak_timeout', 'delta', 'last_checkpoint']
    
    def set_timeout(self, val):
        if val and val != -1 and not isinstance(val, datetime.datetime):
            now = datetime.datetime.now()
            if isinstance(val, datetime.timedelta):
                val = now+val
            else:
                val = now+datetime.timedelta(seconds=val)
        self.timeout = val
    def __cmp__(self, other):
        return cmp(self.timeout, other.timeout)    
    

    
    def __init__(self, timeout=None, weak_timeout=True, **kws):
        super(TimedOperation, self).__init__(**kws)
        self.set_timeout(timeout)
        self.weak_timeout = weak_timeout
        
    def process(self, sched, coro):
        """Add the timeout in the scheduler, check for defaults."""
        super(TimedOperation, self).process(sched, coro)
        
        if sched.default_timeout and not self.timeout:
            self.set_timeout(sched.default_timeout)
        if self.timeout and self.timeout != -1:
            self.coro = coro

            if self.weak_timeout:
                self.last_checkpoint = getnow()
                self.delta = self.timeout - self.last_checkpoint
            else:
                self.last_checkpoint = self.delta = None
        
            heapq.heappush(sched.timeouts, self)
            
    def cleanup(self, sched, coro):
        """
        Clean up after a timeout. Implemented in ops that need cleanup.
        If return value evaluated to false the sched won't raise the timeout in 
        the coroutine.
        """
        return True
        
class WaitForSignal(TimedOperation):
    """The coroutine will resume when the same object is Signaled.
    
    Eg:
    
    .. sourcecode:: python
    
        value = yield events.WaitForSignal(
            name, 
            timeout=None, 
            weak_timeout=True,
            prio=priority.DEFAULT
        )
    
    
    * name - a object to wait on, can use strings for this - string used to 
      wait is equal to the string used to signal.
      
    * value - a object sent with the signal. 
      See: `Signal <cogen.core.events.Signal.html>`_
      
    See: `TimedOperation <cogen.core.events.TimedOperation.html>`_.
    """
        
    __slots__ = ['name', 'result']
    
    def __init__(self, name, **kws):
        super(WaitForSignal, self).__init__(**kws)
        self.name = name
    
    def process(self, sched, coro):
        """Add the calling coro in a waiting for signal queue."""
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
        """Remove this coro from the waiting for signal queue."""
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
    
    .. sourcecode:: python
    
        nr = yield events.Signal(
            name, 
            value,
            prio=priority.DEFAULT
        )
    
    * nr - the number of coroutines woken up
    * name - object that coroutines wait on, can be a string 
    * value - object that the waiting coros recieve when they are resumed.
      
    See: `Operation <cogen.core.events.Operation.html>`_.
    """
    __slots__ = ['name', 'value', 'len', 'prio', 'result', 'recipients', 'coro']
    
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
        """If there aren't enough coroutines waiting for the signal as the 
        recipicient param add the calling coro in another queue to be activated
        later, otherwise activate the waiting coroutines."""
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
    
def Call(coro, args=None, kwargs=None, **kws):
    """
    You don't need to use this. You can just yield the called coroutine:
    
    .. sourcecode:: python
        
        result = yield mycoro( [arguments] )
    
    
    Compared to `OldCall <cogen.core.events.OldCall.html>`_, 
    instead of returning an Operation object it returns the 
    new Coroutine directly that will act as a Call operation in it's pre-init 
    state. This is faster for 2 reasons: avoids one Operation instatiation and 
    avoids pushing and poping the new coroutine on the active coros queue.
    """
    
    return coro(*(args or ()), **(kwargs or {}))
    
class OldCall(Operation):
    """
    This will pause the current coroutine, add a new coro in the scheduler and 
    resume the callee when it returns. 
    
    Usage:
    
    .. sourcecode:: python
        
        result = yield events.Call(mycoro, args=(), kwargs={}, prio=priority.DEFAULT)
    
    
    * mycoro - the coroutine to add.
    * args, kwargs - params to call the coroutine with
    * if `prio` is set the new coroutine will be added in the top of the 
      scheduler queue
      
    See: `Operation <cogen.core.events.Operation.html>`_.
    """
    __slots__ = ['coro', 'args', 'kwargs']
    
    def __init__(self, coro, args=None, kwargs=None, **kws):
        super(Call, self).__init__(**kws)
        self.coro = coro
        self.args = args or ()
        self.kwargs = kwargs or {}
    
    def process(self, sched, coro):
        """Add the called coro in the sched and set the calling coroutine as
        the caller in the called coro (the called coro will activate the calling
        coro when it dies)."""
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
    A operation for adding a coroutine in the scheduler.
    
    Example:
    
    .. sourcecode:: python
        
        yield events.AddCoro(some_coro, args=(), kwargs={})
        
    This is similar to Call, but it doesn't pause the current coroutine.
    See: `Operation <cogen.core.events.Operation.html>`_.
    """
    __slots__ = ['coro', 'args', 'kwargs', 'result']
    def __init__(self, coro, args=None, kwargs=None, **kws):
        super(AddCoro, self).__init__(**kws)
        self.coro = coro
        self.args = args or ()
        self.kwargs = kwargs or {}
    
    def finalize(self):
        """Return a reference to the instance of the newly added coroutine."""
        super(AddCoro, self).finalize()
        return self.result
    
    def process(self, sched, coro):
        """Add the given coroutine in the scheduler."""
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
    
class Join(TimedOperation):
    """
    A operation for waiting on a coroutine. 
    
    Example:
    
    .. sourcecode:: python
    
        @coroutine
        def coro_a():
            return_value = yield events.Join(ref)
            
            
        @coroutine
        def coro_b():
            yield "bla"
            raise StopIteration("some return value")
        
        ref = scheduler.add(coro_b)
        scheduler.add(coro_a)
    
    This will pause the coroutine and resume it when the other coroutine 
    (`ref` in the example) has died.
    """
    __slots__ = ['coro']
    def __init__(self, coro, **kws):
        super(Join, self).__init__(**kws)
        self.coro = coro
        
    def process(self, sched, coro):
        """Add the calling coroutine as a waiter in the coro we want to join.
        Also, doesn't keep the called active (we'll be activated back when the
        joined coro dies)."""
        super(Join, self).process(sched, coro)
        self.coro.add_waiter(coro)
    
    def cleanup(self, sched, coro):
        """Remove the calling coro from the waiting list."""
        self.coro.remove_waiter(coro)
        return True
        
    def __repr__(self):
        return '<%s instance at 0x%X, coro: %s>' % (
            self.__class__, 
            id(self), 
            self.coro
        )

    
class Sleep(TimedOperation):
    """
    A operation to pausing the coroutine for a specified amount of time.
    
    Usage:
    
    .. sourcecode:: python
        
        yield events.Sleep(time_object)
    
    * time_object - a datetime or timedelta object, or a number of seconds
        
    .. sourcecode:: python
    
        yield events.Sleep(timestamp=ts)
    
    * ts - a timestamp
    """
    __slots__ = []
    def __init__(self, val):
        super(Sleep, self).__init__(timeout=val)
        
    def process(self, sched, coro):
        super(Sleep, self).process(sched, coro)
        
    def cleanup(self, sched, coro):
        sched.active.append((self, coro))
        # this is a sort of TimeoutOperation trick, when the timeout occurs
        #we manualy add the coro back in the sched and don't return the cleanup
        #as valid (valid cleanup means return true in cleanup)
        
        
