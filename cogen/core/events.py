import datetime
import heapq

from cogen.core.util import debug, TimeoutDesc, priority

__doc_all__ = [
    'ConnectionClosed',
    'OperationTimeout',
    'WaitForSignal',
    'Signal',
    'Call',
    'AddCoro',
    'Join',
    'Sleep'
]
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
class CoroutineException(Exception):
    """This is used intenally to carry exception state in the poller and 
    scheduler."""
    __doc_all__ = []
    prio = priority.DEFAULT

class Operation(object):
    """All operations derive from this. This base class handles 
    the priority flag. 
    
    Eg:
    
    .. sourcecode:: python
    
        yield Operation(prio=<int constant>)
        
    
    If you need something that can't be done in a coroutine fashion you 
    probabily need to subclass this and make a custom operation for your
    issue.
    """
    __slots__ = ['prio']
    
    def __init__(self, prio=priority.DEFAULT):
        "Set parameters here."
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
    
    .. sourcecode:: python
    
        yield TimedOperation(
            timeout=<secs or datetime or timedelta>, 
            weak_timeout=<bool>,
            prio=<int constant>
        )
    """
    __slots__ = ['_timeout', '__weakref__', 'finalized', 'weak_timeout']
    timeout = TimeoutDesc('_timeout')
    
    def __init__(self, timeout=None, weak_timeout=True, **kws):
        super(TimedOperation, self).__init__(**kws)
        self.timeout = timeout
        self.finalized = False
        self.weak_timeout = weak_timeout
    
    def finalize(self):
        self.finalized = True
        return self
        
    def process(self, sched, coro):
        super(TimedOperation, self).process(sched, coro)
        
        if not self.timeout:
            self.timeout = sched.default_timeout
        if self.timeout and self.timeout != -1:
            sched.add_timeout(self, coro, False)
        
class WaitForSignal(TimedOperation):
    "The coroutine will resume when the same object is Signaled."
        
    __slots__ = ['name', 'result']
    __doc_all__ = ['__init__']
    
    def __init__(self, name, **kws):
        super(WaitForSignal, self).__init__(**kws)
        self.name = name
    
    def process(self, sched, coro):
        super(WaitForSignal, self).process(sched, coro)
        waitlist = sched.sigwait[self.name]
        waitlist.append((self, coro))
        if sched.signals.has_key(self.name):
            sig = sched.signals[self.name]
            if sig.recipients <= len(waitlist):
                sig.process(sched, sig.coro)
                del sig.coro
                del sched.signals[self.name]
    
    def finalize(self):
        super(WaitForSignal, self).finalize()
        return self.result
           
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
    
        nr = yield events.Signal(name, value)
        
    - nr - the number of coroutines woken up
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
    
    .. sourcecode:: python
    
        result = yield events.Call(mycoro, args=<a tuple>, kwargs=<a dict>, prio=<int>)
        
    - if `prio` is set the new coroutine will be added in the top of the 
      scheduler queue
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
    
    .. sourcecode:: python
        
        yield events.AddCoro(some_coro, args=(), kwargs={})
    """
    __slots__ = ['coro', 'args', 'kwargs']
    __doc_all__ = ['__init__']
    def __init__(self, coro, args=None, kwargs=None, **kws):
        super(AddCoro, self).__init__(**kws)
        self.coro = coro
        self.args = args or ()
        self.kwargs = kwargs or {}
    def process(self, sched, coro):
        super(AddCoro, self).process(sched, coro)
        sched.add(self.coro, self.args, self.kwargs, self.prio & priority.OP)
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
    A operator for setting the next (coro, op) pair to be runned by the 
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
    A operator for adding a list of (coroutine, operator) pairs. Used 
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
    A operator for waiting on a coroutine. 
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
    """
    __slots__ = ['coro']
    __doc_all__ = ['__init__']
    def __init__(self, coro, **kws):
        super(Join, self).__init__(**kws)
        self.coro = coro
    def process(self, sched, coro):
        super(Join, self).process(sched, coro)
        self.coro.add_waiter(coro)
    def __repr__(self):
        return '<%s instance at 0x%X, coro: %s>' % (
            self.__class__, 
            id(self), 
            self.coro
        )

    
class Sleep(Operation):
    """
    Usage:
    
    .. sourcecode:: python
    
        yield events.Sleep(time_object)
        
    - timeoject - a datetime or timedelta object, or a number of seconds
        
    .. sourcecode:: python
    
        yield events.Sleep(timestamp=ts)
        
    - ts - a timestamp
    """
    __slots__ = ['wake_time', 'coro']
    __doc_all__ = ['__init__']
    def __init__(self, val=None, timestamp=None):
        super(Sleep, self).__init__()
        if isinstance(val, datetime.timedelta):
            self.wake_time = datetime.datetime.now() + val
        elif isinstance(val, datetime.datetime):
            self.wake_time = val
        else:
            if timestamp:
                self.wake_time = datetime.datetime.fromtimestamp(int(timestamp))
            else:
                self.wake_time = datetime.datetime.now() + \
                                 datetime.timedelta(seconds=val)
    def process(self, sched, coro):
        super(Sleep, self).process(sched, coro)
        self.coro = coro
        heapq.heappush(sched.timewait, self)
    def __cmp__(self, other):
        return cmp(self.wake_time, other.wake_time)
        
