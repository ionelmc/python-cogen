import collections
import datetime
import heapq
import weakref
                
from cogen.core.pollers import DefaultPoller
from cogen.core import events
from cogen.core import sockets
from cogen.core.util import *

class DebugginWrapper:
    def __init__(self, obj):
        self.obj = obj
    
    def __getattr__(self, name):
        if 'append' in name:
            return debug(0)(getattr(self.obj, name))
        else:
            return getattr(self.obj, name)
class Timeout(object):
    __slots__= [
        'coro', 'op', 'timeout', 'weak_timeout', 
        'delta', 'last_checkpoint'
    ]
    def __init__(self, op, coro, weak_timeout=False):
        assert isinstance(op.timeout, datetime.datetime)
        self.timeout = op.timeout
        self.last_checkpoint = datetime.datetime.now()
        self.delta = self.timeout - self.last_checkpoint
        self.coro = weakref.ref(coro)
        self.op = weakref.ref(op)
        self.weak_timeout = weak_timeout
        
    def __cmp__(self, other):
        return cmp(self.timeout, other.timeout)    
    def __repr__(self):
        return "<%s@%s timeout:%s, coro:%s, op:%s, weak:%s, lastcheck:%s, delta:%s>" % (
            self.__class__.__name__, 
            id(self), 
            self.timeout, 
            self.coro(), 
            self.op(), 
            self.weak_timeout, 
            self.last_checkpoint, 
            self.delta
        )

class Scheduler(object):
    def __init__(self, poller=DefaultPoller, default_priority=priority.LAST, default_timeout=None):
        self.timeouts = []
        self.active = collections.deque()
        self.sigwait = collections.defaultdict(collections.deque)
        self.timewait = [] # heapq
        self.poll = poller(self)
        self.default_priority = default_priority
        self.default_timeout = default_timeout
    def __repr__(self):
        return "<%s@0x%X active:%s sigwait:%s timewait:%s poller:%s default_priority:%s default_timeout:%s>" % (
            self.__class__.__name__, 
            id(self), 
            len(self.active), 
            len(self.sigwait), 
            len(self.timewait), 
            self.poll, 
            self.default_priority, 
            self.default_timeout
        )
    def _init_coro(self, coro, *args, **kws):
        return coro(*args, **kws)
            
    def add(self, coro, *args, **kws):
        coro = self._init_coro(coro, *args, **kws)
        self.active.append( (None, coro) )
        return coro
        
    def add_first(self, coro, *args, **kws):
        coro = self._init_coro(coro, *args, **kws)
        self.active.appendleft( (None, coro) )
        return coro
        
    def run_timer(self):
        if self.timewait:
            now = datetime.datetime.now() 
            while self.timewait and self.timewait[0].wake_time <= now:
                op = heapq.heappop(self.timewait)
                self.active.appendleft((op, op.coro))
    
    def next_timer_delta(self): 
        if self.timewait and not self.active:
            return (datetime.datetime.now() - self.timewait[0].wake_time)
        else:
            if self.active:
                return 0
            else:
                return None
    def run_poller(self):
        
        if len(self.active)<2:
            self.poll.run(timeout = self.next_timer_delta())

    def add_timeout(self, op, coro, weak_timeout):
        heapq.heappush(self.timeouts, Timeout(op, coro, weak_timeout))
    def handle_timeouts(self):
        now = datetime.datetime.now()
        #~ print '>to:', self.timeouts, self.timeouts and self.timeouts[0].timeout <= now
        while self.timeouts and self.timeouts[0].timeout <= now:
            timo = heapq.heappop(self.timeouts)
            op, coro = timo.op(), timo.coro()
            if op:
                #~ print timo
                if timo.weak_timeout and hasattr(op, 'last_update'):
                    if op.last_update > timo.last_checkpoint:
                        timo.last_checkpoint = op.last_update
                        timo.timeout = timo.last_checkpoint + timo.delta
                        heapq.heappush(self.timeouts, timo)
                        continue
                
                if isinstance(op, sockets.Operation):
                    self.poll.remove(op, coro)
                elif coro and isinstance(op, events.Join):
                    op.coro.remove_waiter(coro)
                elif isinstance(op, events.WaitForSignal):
                    try:
                        self.sigwait[op.name].remove((op, coro))
                    except ValueError:
                        pass
                if not op.finalized and coro and coro.running:
                    self.active.append((
                        events.CoroutineException((
                            events.OperationTimeout, 
                            events.OperationTimeout(op)
                        )), 
                        coro
                    ))
    #~ @debug(0)        
    def process_op(self, op, coro):
        if op is None:
           self.active.append((op, coro))
        else:
            if getattr(op, 'prio', None) == priority.DEFAULT:
                op.prio = self.default_priority
            if hasattr(op, 'timeout'): 
                if not op.timeout:
                    op.timeout = self.default_timeout
                if op.timeout and op.timeout != -1:
                    self.add_timeout(op, coro, getattr(op, 'weak_timeout', False))
        
            if isinstance(op, sockets.Operation):
                r = self.poll.run_or_add(op, coro)
                if r:
                    if op.prio:
                        return r, coro
                    else:
                        self.active.appendleft((r, coro))
            elif isinstance(op, events.Pass):
                return op.op, op.coro
            elif isinstance(op, events.AddCoro):
                if op.prio & priority.OP:
                    self.add_first(op.coro, *op.args, **op.kwargs)
                else:
                    self.add(op.coro, *op.args, **op.kwargs)
                    
                if op.prio & priority.CORO:
                    return op, coro
                else:
                    self.active.append( (None, coro))
            elif isinstance(op, events.Complete):
                if op.prio:
                    self.active.extendleft(op.args)
                else:
                    self.active.extend(op.args)
            elif isinstance(op, events.WaitForSignal):
                self.sigwait[op.name].append((op, coro))
            elif isinstance(op, events.Signal):
                op.result = len(self.sigwait[op.name])
                for waitop, waitcoro in self.sigwait[op.name]:
                    waitop.result = op.value
                if op.prio & priority.OP:
                    self.active.extendleft(self.sigwait[op.name])
                else:
                    self.active.extend(self.sigwait[op.name])
                
                if op.prio & priority.CORO:
                    self.active.appendleft((None, coro))
                else:
                    self.active.append((None, coro))
                    
                del self.sigwait[op.name]
            elif isinstance(op, events.Call):
                if op.prio:
                    callee = self.add_first(op.coro, *op.args, **op.kwargs)
                else:
                    callee = self.add(op.coro, *op.args, **op.kwargs) 
                callee.caller = coro
                callee.prio = op.prio
                del callee
            elif isinstance(op, events.Join):
                op.coro.add_waiter(coro)
            elif isinstance(op, events.Sleep):
                op.coro = coro
                heapq.heappush(self.timewait, op)
            else:
                raise RuntimeError("Bad coroutine operation.")
        return None, None
        
    def run(self):
        while self.active or self.poll or self.timewait:
            if self.active:
                #~ print 'ACTIVE:', self.active
                op, coro = self.active.popleft()
                while True:
                    #~ print coro, op
                    op, coro = self.process_op(coro.run_op(op), coro)
                    if not op:
                        break  
                    
            self.run_poller()
            self.run_timer()
            self.handle_timeouts()
            #~ print 'active:  ',len(self.active)
            #~ print 'poll:    ',len(self.poll)
            #~ print 'timeouts:',len(self.poll._timeouts)

