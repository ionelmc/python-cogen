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

from cogen.core import sockets
from cogen.core import events
from cogen.core.util import *

class Poller:
    """
    A poller just checks if there are ready-sockets for the operations.
    The operations are not done here, they are done in the socket ops instances.
    """
    RESOLUTION = 0.02
    mRESOLUTION = RESOLUTION*1000
    def __init__(t, scheduler):
        t.waiting_reads = {}
        t.waiting_writes = {}
        t.scheduler = scheduler
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
        for socks in (t.waiting_reads, t.waiting_writes):
            for i in socks:
                op, coro = socks[i]
                if testcoro is coro:
                    return op
    def __len__(t):
        return len(t.waiting_reads) + len(t.waiting_writes)
    def __repr__(t):
        return "<%s@%s reads:%r writes:%r>" % (t.__class__.__name__, id(t), t.waiting_reads, t.waiting_writes)
class SelectPoller(Poller):
    def remove(t, op):
        #~ print '> remove', op
        if isinstance(op, sockets.ReadOperation):
            if op.sock in t.waiting_reads:
                del t.waiting_reads[op.sock]
        if isinstance(op, sockets.WriteOperation):
            if op.sock in t.waiting_writes:
                del t.waiting_writes[op.sock]
    def add(t, op, coro):
        if isinstance(op, sockets.ReadOperation):
            assert op.sock not in t.waiting_reads
            t.waiting_reads[op.sock] = op, coro
            
        if isinstance(op, sockets.WriteOperation):
            assert op.sock not in t.waiting_writes
            t.waiting_writes[op.sock] = op, coro
            
    def handle_events(t, ready, waiting_ops):
        for id in ready:
            op, coro = waiting_ops[id]
            heapq.heapreplace
            op = t.run_operation(op)
            if op:
                del waiting_ops[id]
                
            
                if op.prio & priority.OP:
                    op, coro = t.scheduler.process_op(coro.run_op(op), coro)
                if coro:
                    if op.prio & priority.CORO:
                        t.scheduler.active.appendleft( (op, coro) )
                    else:
                        t.scheduler.active.append( (op, coro) )

        
    def run(t, timeout = 0):
        """ 
        Run a poller loop and return new socket events. Timeout is a timedelta object, 0 if active coros or None. 
        
        select timeout param is a float number of seconds.
        """
        ptimeout = timeout.microseconds*1000000+timeout.seconds if timeout else (t.RESOLUTION if timeout is None else 0)
        if t.waiting_reads or t.waiting_writes:
            #~ print 'SELECTING, timeout:', timeout, 'ptimeout:', ptimeout, 'socks:',t.waiting_reads.keys(), t.waiting_writes.keys()
            ready_to_read, ready_to_write, in_error = select.select(t.waiting_reads.keys(), t.waiting_writes.keys(), [], ptimeout)
            t.handle_events(ready_to_read, t.waiting_reads)
            t.handle_events(ready_to_write, t.waiting_writes)
        else:
            time.sleep(t.RESOLUTION)
        
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
            t.waiting_reads[fd] = obj, coro
            epoll.epoll_ctl(t.epoll_fd, epoll.EPOLL_CTL_ADD, fd, epoll.EPOLLIN)
        if op.__class__ in sockets.write_ops:
            t.waiting_writes[fd] = obj, coro
            epoll.epoll_ctl(t.epoll_fd, epoll.EPOLL_CTL_ADD, fd, epoll.EPOLLOUT)
    def run(t, timeout = 0):
        """ 
        Run a poller loop and return new socket events. Timeout is a timedelta object, 0 if active coros or None. 
        
        epoll timeout param is a integer number of miliseconds (seconds/1000).
        """
        ptimeout = timeout.microseconds*1000+timeout.seconds/1000 if timeout else (t.mRESOLUTION if timeout is None else 0)
        if t.fds:
            events = epoll.epoll_wait(t.epoll_fd, 10, ptimeout)
            for ev, fd in events:
                #~ print "EPOLL Event:", ev, fd
                    
                if ev == epoll.EPOLLIN:
                    result = t.run_once(fd, t.waiting_reads)
                    if result:
                        epoll.epoll_ctl(t.epoll_fd, epoll.EPOLL_CTL_DEL, fd, 0)
                        yield result
                elif ev == epoll.EPOLLOUT:
                    result = t.run_once(fd, t.waiting_writes)
                    if result:
                        epoll.epoll_ctl(t.epoll_fd, epoll.EPOLL_CTL_DEL, fd, 0)
                        yield result
                
        else:
            time.sleep(t.RESOLUTION)
try:
    import epollx
    DefaultPoller = EpollPoller
except ImportError:
    DefaultPoller = SelectPoller            
