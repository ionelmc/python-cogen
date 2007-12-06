import collections
import time
import sys
import traceback
import types
import datetime
import heapq
import weakref
                
from cogen.core.pollers import DefaultPoller
from cogen.core import events
from cogen.core import sockets
from cogen.core.util import *


class Timeout(object):
    __slots__= ['coro','op','timeout']
    def __init__(t, op, coro):
        assert isinstance(op.timeout, datetime.datetime)
        t.timeout = op.timeout
        t.coro = weakref.ref(coro)
        t.op = weakref.ref(op)
    def __cmp__(t, other):
        return cmp(t.timeout, other.timeout)    
    def __iter__(t):
        return iter((t.op(), t.coro()))
    def __repr__(t):
        return "<%s@%s timeout:%s, coro:%s, op:%s>" % (t.__class__.__name__, id(t), t.timeout, t.coro(), t.op())

class Scheduler(object):
    def __init__(t, poller=DefaultPoller, default_priority=priority.LAST, default_timeout=None):
        t.timeouts = []
        t.active = collections.deque()
        t.sigwait = collections.defaultdict(collections.deque)
        t.timewait = [] # heapq
        t.poll = poller(t)
        t.default_priority = default_priority
        t.default_timeout = default_timeout
        
    def _init_coro(t, coro, *args, **kws):
        return coro(*args, **kws)
            
    def add(t, coro, *args, **kws):
        coro = t._init_coro(coro, *args, **kws)
        t.active.append( (None, coro) )
        return coro
        
    def add_first(t, coro, *args, **kws):
        coro = t._init_coro(coro, *args, **kws)
        t.active.appendleft( (None, coro) )
        return coro
        
    def run_timer(t):
        if t.timewait:
            now = datetime.datetime.now() 
            while t.timewait and t.timewait[0].wake_time <= now:
                op = heapq.heappop(t.timewait)
                t.active.appendleft((op, op.coro))
    
    def next_timer_delta(t): 
        if t.timewait and not t.active:
            return (datetime.datetime.now() - t.timewait[0].wake_time)
        else:
            if t.active:
                return 0
            else:
                return None
    def run_poller(t):
        
        if len(t.active)<2:
            t.poll.run(timeout = t.next_timer_delta())

    def add_timeout(t, op, coro):
        heapq.heappush(t.timeouts, Timeout(op, coro))
    def handle_timeouts(t):
        now = datetime.datetime.now()
        #~ print '>to:', t.timeouts, t.timeouts and t.timeouts[0].timeout <= now
        if t.timeouts and t.timeouts[0].timeout <= now:
            op, coro = heapq.heappop(t.timeouts)
            if op:
                if isinstance(op, sockets.Operation):
                    t.poll.remove(op)
                elif coro and isinstance(op, events.Join):
                    op.coro.remove_waiter(coro)
                elif isinstance(op, events.WaitForSignal):
                    try:
                        t.sigwait[op.name].remove((op, coro))
                    except ValueError:
                        pass
                t.active.append( (events.CoroutineException((events.OperationTimeout, events.OperationTimeout(op))), coro) )
            
    def process_op(t, op, coro):
        if op is None:
           t.active.append((op, coro))
        else:
            if getattr(op, 'prio', None) == priority.DEFAULT:
                op.prio = t.default_priority
            if hasattr(op, 'timeout'): 
                if not op.timeout:
                    op.timeout = t.default_timeout
                if op.timeout and op.timeout != -1:
                    t.add_timeout(op, coro)
        
            if isinstance(op, sockets.Operation):
                r = t.poll.run_or_add(op, coro)
                if r:
                    if op.prio:
                        return r, coro
                    else:
                        t.active.appendleft((r, coro))
            elif isinstance(op, events.Pass):
                return op.op, op.coro
            elif isinstance(op, events.AddCoro):
                if op.prio & priority.OP:
                    t.add_first(op.coro, *op.args, **op.kwargs)
                else:
                    t.add(op.coro, *op.args, **op.kwargs)
                    
                if op.prio & priority.CORO:
                    return op, coro
                else:
                    t.active.append( (None, coro))
            elif isinstance(op, events.Complete):
                if op.prio:
                    t.active.extendleft(op.args)
                else:
                    t.active.extend(op.args)
            elif isinstance(op, events.WaitForSignal):
                t.sigwait[op.name].append((op, coro))
            elif isinstance(op, events.Signal):
                op.result = len(t.sigwait[op.name])
                if op.prio & priority.OP:
                    t.active.extendleft(t.sigwait[op.name])
                else:
                    t.active.extend(t.sigwait[op.name])
                
                if op.prio & priority.CORO:
                    t.active.appendleft((None, coro))
                else:
                    t.active.append((None, coro))
                    
                del t.sigwait[op.name]
            elif isinstance(op, events.Call):
                if op.prio:
                    callee = t.add_first(op.coro, *op.args, **op.kwargs)
                else:
                    callee = t.add(op.coro, *op.args, **op.kwargs) 
                callee.caller = coro
                callee.prio = op.prio
                del callee
            elif isinstance(op, events.Join):
                op.coro.add_waiter(coro)
            elif isinstance(op, events.Sleep):
                op.coro = coro
                heapq.heappush(t.timewait, op)
            else:
                raise RuntimeError("Bad coroutine operation.")
        return None, None
        
    def run(t):
        while t.active or t.poll or t.timewait:
            if t.active:
                op, coro = t.active.popleft()
                while True:
                    #~ print coro, op
                    op, coro = t.process_op(coro.run_op(op), coro)
                    if not op:
                        break  
                    
            t.run_poller()
            t.run_timer()
            t.handle_timeouts()
            #~ print 'active:  ',len(t.active)
            #~ print 'poll:    ',len(t.poll)
            #~ print 'timeouts:',len(t.poll._timeouts)

