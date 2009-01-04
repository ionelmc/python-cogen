"""
Scheduling framework.

The scheduler handles the timeouts, run the operations and does very basic 
management of coroutines. Most of the heavy logic is in each operation class.
See: :mod:`cogen.core.events` and :mod:`cogen.core.sockets`.
Most of those operations work with attributes we set in the scheduler.

`cogen` is multi-state. All the state related to coroutines and network is in 
the scheduler and it's associated proactor. That means you could run several 
cogen schedulers in the same process/thread/whatever.

There is just one thing that uses global objects - the threadlocal-like local 
object in the coroutines module.  It was actually aded for the wsgiserver 
factory that monkey patches the threadlocal module in order to make pylons run
correctly (pylons relies heavily on threadlocals). 
"""
__all__ = ['Scheduler']
import collections
import datetime
import heapq
#~ import weakref
import sys                
import errno
import select

from cogen.core.proactors import DefaultProactor
from cogen.core import events
from cogen.core.util import priority
from cogen.core.coroutines import CoroutineException
#~ getnow = debug(0)(datetime.datetime.now)
getnow = datetime.datetime.now

class Scheduler(object):
    """Basic deque-based scheduler with timeout support and primitive 
    prioritisaiton parameters. 
    
    Usage:
    
    .. sourcecode:: python
        
        mysched = Scheduler(proactor=DefaultProactor, 
                default_priority=priority.LAST, default_timeout=None)
    
    * proactor: a proactor class to use
    
    * default_priority: a default priority option for operations that do not 
      set it. check :class:`cogen.core.util.priority`.
      
    * default_timeout: a default timedelta or number of seconds to wait for 
      the operation, -1 means no timeout.
    
    """
    def __init__(self, proactor=DefaultProactor, default_priority=priority.LAST, 
            default_timeout=None, proactor_resolution=.01, proactor_greedy=True,
            ops_greedy=False, proactor_multiplex_first=None, 
            proactor_default_size=None):
        
        if not callable(proactor):
            raise RuntimeError("Invalid proactor constructor")
        self.timeouts = []
        self.active = collections.deque()
        self.sigwait = collections.defaultdict(collections.deque)
        self.signals = collections.defaultdict(collections.deque)
        proactor_options = {}
        if proactor_multiplex_first is not None:
            proactor_options['multiplex_first'] = proactor_multiplex_first
        if proactor_default_size is not None:
            proactor_options['default_size'] = proactor_default_size
        self.proactor = proactor(self, proactor_resolution, **proactor_options)
                                 
        self.default_priority = default_priority
        self.default_timeout = default_timeout
        self.running = False
        self.proactor_greedy = proactor_greedy
        self.ops_greedy = ops_greedy
    def __repr__(self):
        return "<%s@0x%X active:%s sigwait:%s timeouts:%s proactor:%s default_priority:%s default_timeout:%s>" % (
            self.__class__.__name__, 
            id(self), 
            len(self.active), 
            len(self.sigwait), 
            len(self.timeouts), 
            self.proactor, 
            self.default_priority, 
            self.default_timeout
        )
    def __del__(self):
        if hasattr(self, 'proactor'):
            if hasattr(self.proactor, 'scheduler'):
                del self.proactor.scheduler
            self.proactor.close()
            del self.proactor
            
    def add(self, coro, args=(), kwargs={}, first=True):
        """Add a coroutine in the scheduler. You can add arguments 
        (_args_, _kwargs_) to init the coroutine with."""
        assert callable(coro), "Coroutine not a callable object"
        coro = coro(*args, **kwargs)
        if first:
            self.active.append( (None, coro) )
        else:
            self.active.appendleft( (None, coro) )    
        return coro
       
    def next_timer_delta(self): 
        "Returns a timevalue that the proactor will wait on."
        if self.timeouts and not self.active:
            now = getnow()
            timo = self.timeouts[0].timeout
            if now >= timo:
                #looks like we've exceded the time
                return 0
            else:
                return (timo - now)
        else:
            if self.active:
                return 0
            else:
                return None
    
    def handle_timeouts(self):
        """Handle timeouts. Raise timeouted operations with a OperationTimeout 
        in the associated coroutine (if they are still alive and the operation
        hasn't actualy sucessfuly completed) or, if the operation has a 
        weak_timeout flag, update the timeout point and add it back in the 
        heapq.
        
        weak_timeout notes:
        
        * weak_timeout means a last_update attribute is updated with
          a timestamp of the last activity in the operation - for example, a
          may recieve new data and not complete (not enough data, etc)
        * if there was activity since the last time we've cheched this 
          timeout we push it back in the heapq with a timeout value we'll check 
          it again
        
        Also, we call a cleanup on the op, only if cleanup return true we raise 
        the timeout (finalized isn't enough to check if the op has completed 
        since finalized is set when the operation gets back in the coro - and
        it might still be in the Scheduler.active queue when we get to this 
        timeout - well, this is certainly a problem magnet: TODO: fix_finalized)
        """
        now = getnow()
        #~ print '>to:', self.timeouts, self.timeouts and self.timeouts[0].timeout <= now
        while self.timeouts and self.timeouts[0].timeout <= now:
            op = heapq.heappop(self.timeouts)
                
            coro = op.coro
            if op.weak_timeout and hasattr(op, 'last_update'):
                if op.last_update > op.last_checkpoint:
                    op.last_checkpoint = op.last_update
                    op.timeout = op.last_checkpoint + op.delta
                    heapq.heappush(self.timeouts, op)
                    continue
           
            if op.state is events.RUNNING and coro and coro.running and \
                                                    op.cleanup(self, coro):
                
                self.active.append((
                    CoroutineException(
                        events.OperationTimeout, 
                        events.OperationTimeout(op)
                    ), 
                    coro
                ))
    
    def process_op(self, op, coro):
        "Process a (op, coro) pair and return another pair. Handles exceptions."
        if op is None:
            if self.active:
                self.active.append((op, coro))
            else:
                return op, coro 
        else:
            try:
                result = op.process(self, coro) or (None, None)
            except:
                op.state = events.ERRORED
                result = CoroutineException(*sys.exc_info()), coro
            return result
        return None, None
        
    def iter_run(self):
        """
        The actual processing for the main loop is here.
        
        Running the main loop as a generator (where a iteration is a full 
        sched, proactor and timers/timeouts run) is usefull for interleaving
        the main loop with other applications that have a blocking main loop and 
        require cogen to run in the same thread.
        """
        self.running = True
        urgent = None
        while self.running and (self.active or self.proactor or self.timeouts or urgent):
            if self.active or urgent:
                op, coro = urgent or self.active.popleft()
                urgent = None
                while True:
                    op, coro = self.process_op(coro.run_op(op), coro)
                    if not op and not coro:
                        break  
            
            if (self.proactor_greedy or not self.active) and self.proactor:
                try:
                    urgent = self.proactor.run(timeout = self.next_timer_delta())
                except (OSError, select.error), exc:
                    if exc[0] != errno.EINTR:
                        raise
                #~ if urgent:print '>urgent:', urgent
            if self.timeouts: 
                self.handle_timeouts()
            yield
            # this could had beed a ordinary function and have the run() call 
            #this repeatedly but the _urgent_ operation this is usefull (as it 
            #saves us needlessly hammering the active coroutines queue with 
            #append and pop calls on the same thing
    
    def run(self):
        """This is the main loop.
        This loop will exit when there are no more coroutines to run or stop has
        been called.
        """
        for _ in self.iter_run():
            pass
            
    def stop(self):
        self.running = False
