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
from cogen.core.const import priority

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
        obj = t.run_operation(waiting_ops[id])
        if obj:
            del waiting_ops[id]
            return obj, obj._coro
    def run_operation(t, obj):
        " Run the socket op and return result or exception. "
        
        try:
            r = obj.try_run()
            #~ print r, obj
        except:
            r = Exception(sys.exc_info())
            r._coro = obj._coro
        return r
    def run_or_add(t, obj, coro):
        " Perform operation or add the operation in the poller if socket isn't ready. Called from the scheduller. "
        r = t.run_operation(obj)
        if r: 
            return r
        else:
            obj._coro = coro
            t.add(obj)
    def waiting_op(t, coro):
        for socks in (t._waiting_reads, t._waiting_writes):
            for i in socks:
                obj = socks[i]
                if coro is obj._coro:
                    return obj
    def handle_timeouts(t):
        now = datetime.datetime.now()
        if t._timeouts and t._timeouts[0] <= now:
            obj = heapq.heappop(t._timeouts)
            t._scheduler.active.append( (events.OperationTimeout(obj), obj._coro) )

class SelectPoller(Poller):
    def __len__(t):
        return len(t._waiting_reads) + len(t._waiting_writes)
    def add(t, obj):
        if obj.__class__ in sockets.read_ops:
            assert obj.sock not in t._waiting_reads
            t._waiting_reads[obj.sock] = obj
            
        if obj.__class__ in sockets.write_ops:
            assert obj.sock not in t._waiting_writes
            t._waiting_writes[obj.sock] = obj
            
    def handle_events(t, ready, waiting_ops):
        for id in ready:
            op = t.run_operation(waiting_ops[id])
            if op:
                del waiting_ops[id]
            
                coro = op._coro
                prio = getattr(op, 'prio', priority.LAST)
                del op._coro
                if prio & priority.OP:
                    coro, op = t._scheduler.process_op(coro, coro.run_op(op))
                if coro:
                    if prio & priority.CORO:
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
        fd = obj.sock.fileno()
        assert fd not in t.fds
                
        if obj.__class__ in sockets.read_ops:
            t._waiting_reads[fd] = obj, coro
            epoll.epoll_ctl(t.epoll_fd, epoll.EPOLL_CTL_ADD, fd, epoll.EPOLLIN)
        if obj.__class__ in sockets.write_ops:
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
    import epoll
    DefaultPoller = EpollPoller
except ImportError:
    DefaultPoller = SelectPoller            
