import sys
import random, time
random.seed(time.time())
from cogen.core import events

class ReactorBase(object):
    """
    A reactor just checks if there are ready-sockets for the operations.
    The operations are not done here, they are done in the socket ops instances.
    """
    __doc_all__ = [
        '__init__', 'run_once', 'run_operation', 'run_or_add', 'add', 
        'waiting_op', '__len__', 'handle_errored', 'remove', 'run', 
        'handle_events'
    ]
    
    def __init__(self, scheduler, resolution):
        self.waiting_reads = {}
        self.waiting_writes = {}
        self.scheduler = scheduler
        self.resolution = resolution # seconds
        self.m_resolution = resolution*1000 # miliseconds
        self.n_resolution = resolution*1000000000 #nanoseconds
    
    def run_once(self, fdesc, waiting_ops):           
        """ Run a operation, remove it from the reactor and return the result. 
        Called from the main reactor loop. """
        op, coro = waiting_ops[fdesc]
        op = self.run_operation()
        if op:
            del waiting_ops[fdesc]
            return op, coro
    def run_operation(self, op, reactor=True):
        " Run the socket op and return result or exception. "
        try:
            r = op.try_run(reactor)
        except:
            r = events.CoroutineException(sys.exc_info())
            sys.exc_clear()
        del op
        return r
    def run_or_add(self, op, coro):
        """ Perform operation and return result or add the operation in 
        the reactor if socket isn't ready and return none. 
        Called from the scheduller via SocketOperation.process. """
        r = self.run_operation(op)
        if r: 
            return r
        else:
            self.add(op, coro)
    def add(self, op, coro):
        """Implemented by the child class that actualy implements the polling.
        Registers an operation.
        """
        raise NotImplementedError()
    def remove(self, op, coro):
        """Implemented by the child class that actualy implements the polling.
        Removes a operation.
        """
        raise NotImplementedError()
    def run(self, timeout = 0):
        """Implemented by the child class that actualy implements the polling.
        Calls the underlying OS polling mechanism and runs the operations for
        any ready descriptor.
        """
        raise NotImplementedError()
    def waiting_op(self, testcoro):
        "Returns the registered operation for some specified coroutine."
        for socks in (self.waiting_reads, self.waiting_writes):
            for i in socks:
                op, coro = socks[i]
                if testcoro is coro:
                    return op
    def __len__(self):
        "Returns number of waiting operations registered in the reactor."
        return len(self.waiting_reads) + len(self.waiting_writes)
    def __repr__(self):
        return "<%s@%s reads:%r writes:%r>" % (
            self.__class__.__name__, 
            id(self), 
            self.waiting_reads, 
            self.waiting_writes
        )

    def handle_errored(self, desc, code=None):
        "Handles descriptors that have errors."
        if desc in self.waiting_reads:
            waiting_ops = self.waiting_reads
        elif desc in self.waiting_writes:
            waiting_ops = self.waiting_writes
        else:
            return
        op, coro = waiting_ops[desc]
        del waiting_ops[desc]
        self.scheduler.active.append((
            events.CoroutineException((
                events.ConnectionError, events.ConnectionError(code, op)
            )), 
            coro
        ))
