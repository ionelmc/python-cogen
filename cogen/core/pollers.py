from __future__ import division
import socket
import select
import collections
import time
import sys
import traceback
import types
import errno
import exceptions
import datetime
import heapq
import weakref

from cogen.core import sockets
from cogen.core import events
from cogen.core.events import priority

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
class Poller:
    """
    A poller just checks if there are ready-sockets for the operations.
    The operations are not done here, they are done in the socket ops instances.
    """
    resolution = 0.02
    mresolution = resolution*1000
    def __init__(t, scheduler):
        t._timeouts = []
        t._waiting_reads = {}
        t._waiting_writes = {}
        t._scheduler = scheduler
    def run_once(t, id, waiting_ops):           
        " Run a operation, remove it from the poller and return the result. Called from the main poller loop. "
        op, coro = waiting_ops[id]
        op = t.run_operation()
        if op:
            del waiting_ops[id]
            return op, coro
    def run_operation(t, op):
        " Run the socket op and return result or exception. "
        try:
            r = op.try_run()
        except:
            r = events.CoroutineException(sys.exc_info())
        return r
    def run_or_add(t, op, coro):
        " Perform operation or add the operation in the poller if socket isn't ready. Called from the scheduller. "
        r = t.run_operation(op)
        if r: 
            return r
        else:
            t.add(op, coro)
    def waiting_op(t, testcoro):
        for socks in (t._waiting_reads, t._waiting_writes):
            for i in socks:
                op, coro = socks[i]
                if testcoro is coro:
                    return op
    def add_timeout(t, op, coro):
        heapq.heappush(t._timeouts, Timeout(op, coro))
    def handle_timeouts(t):
        now = datetime.datetime.now()
        #~ print '>to:', t._timeouts, t._timeouts and t._timeouts[0].timeout <= now
        if t._timeouts and t._timeouts[0].timeout <= now:
            op, coro = heapq.heappop(t._timeouts)
            if op and coro:
                t.remove(op)
                t._scheduler.active.append( (events.CoroutineException((events.OperationTimeout, events.OperationTimeout(op))), coro) )
    def __len__(t):
        return len(t._waiting_reads) + len(t._waiting_writes)
    
class SelectPoller(Poller):
    def remove(t, op):
        if isinstance(op, sockets.ReadOperation):
            del t._waiting_reads[op.sock]
        if isinstance(op, sockets.WriteOperation):
            del t._waiting_writes[op.sock]
    def add(t, op, coro):
        if op.timeout: t.add_timeout(op, coro)
            
        if isinstance(op, sockets.ReadOperation):
            assert op.sock not in t._waiting_reads
            t._waiting_reads[op.sock] = op, coro
            
        if isinstance(op, sockets.WriteOperation):
            assert op.sock not in t._waiting_writes
            t._waiting_writes[op.sock] = op, coro
            
    def handle_events(t, ready, waiting_ops):
        for id in ready:
            op, coro = waiting_ops[id]
            heapq.heapreplace
            op = t.run_operation(op)
            if op:
                del waiting_ops[id]
                
            
                if op.prio & priority.OP:
                    op, coro = t._scheduler.process_op(coro.run_op(op), coro)
                if coro:
                    if op.prio & priority.CORO:
                        t._scheduler.active.appendleft( (op, coro) )
                    else:
                        t._scheduler.active.append( (op, coro) )

        
    def run(t, timeout = 0):
        """ 
        Run a poller loop and return new socket events. Timeout is a timedelta object, 0 if active coros or None. 
        
        select timeout param is a float number of seconds.
        """
        ptimeout = timeout.microseconds*1000000+timeout.seconds if timeout else (t.resolution if timeout is None else 0)
        if t._waiting_reads or t._waiting_writes:
            #~ print 'SELECTING, timeout:', timeout, 'ptimeout:', ptimeout, 'socks:',t._waiting_reads.keys(), t._waiting_writes.keys()
            ready_to_read, ready_to_write, in_error = select.select(t._waiting_reads.keys(), t._waiting_writes.keys(), [], ptimeout)
            t.handle_events(ready_to_read, t._waiting_reads)
            t.handle_events(ready_to_write, t._waiting_writes)
        else:
            time.sleep(t.resolution)
        t.handle_timeouts()
class EpollPoller(Poller):
    def __init__(t, default_size = 100):
        super(t.__class__,t).__init__()
        t.epoll_fd = epoll.epoll_create(default_size)
    def __len__(t):
        return len(t.fds)
    def waiting(t, x):
        for i in t.fds:
            obj, coro = t.fds[i]
            if x is coro:
                return obj
    def add(t, obj, coro):
        fd = op.sock.fileno()
        assert fd not in t.fds
                
        if op.__class__ in sockets.read_ops:
            t._waiting_reads[fd] = obj, coro
            epoll.epoll_ctl(t.epoll_fd, epoll.EPOLL_CTL_ADD, fd, epoll.EPOLLIN)
        if op.__class__ in sockets.write_ops:
            t._waiting_writes[fd] = obj, coro
            epoll.epoll_ctl(t.epoll_fd, epoll.EPOLL_CTL_ADD, fd, epoll.EPOLLOUT)
    def run(t, timeout = 0):
        """ 
        Run a poller loop and return new socket events. Timeout is a timedelta object, 0 if active coros or None. 
        
        epoll timeout param is a integer number of miliseconds (seconds/1000).
        """
        ptimeout = timeout.microseconds*1000+timeout.seconds/1000 if timeout else (t.mresolution if timeout is None else 0)
        if t.fds:
            events = epoll.epoll_wait(t.epoll_fd, 10, ptimeout)
            for ev, fd in events:
                #~ print "EPOLL Event:", ev, fd
                    
                if ev == epoll.EPOLLIN:
                    result = t.run_once(fd, t._waiting_reads)
                    if result:
                        epoll.epoll_ctl(t.epoll_fd, epoll.EPOLL_CTL_DEL, fd, 0)
                        yield result
                elif ev == epoll.EPOLLOUT:
                    result = t.run_once(fd, t._waiting_writes)
                    if result:
                        epoll.epoll_ctl(t.epoll_fd, epoll.EPOLL_CTL_DEL, fd, 0)
                        yield result
                
        else:
            time.sleep(t.resolution)
try:
    import epollx
    DefaultPoller = EpollPoller
except ImportError:
    DefaultPoller = SelectPoller            
