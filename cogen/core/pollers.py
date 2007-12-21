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

class Poller(object):
    """
    A poller just checks if there are ready-sockets for the operations.
    The operations are not done here, they are done in the socket ops instances.
    """
    RESOLUTION = 0.02
    mRESOLUTION = RESOLUTION*1000
    nRESOLUTION = RESOLUTION*1000000000
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

    def handle_errored(t, desc):
        if desc in t.waiting_reads:
            waiting_ops = t.waiting_reads
        elif desc in t.waiting_writes:
            waiting_ops = t.waiting_writes
        else:
            return
        op, coro = waiting_ops[desc]
        del waiting_ops[desc]
        t.scheduler.active.append( (events.CoroutineException((events.ConnectionError, events.ConnectionError(op))), coro) )
        
class SelectPoller(Poller):
    def remove(t, op, coro):
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
        ptimeout = timeout.microseconds/1000000+timeout.seconds if timeout else (t.RESOLUTION if timeout is None else 0)
        if t.waiting_reads or t.waiting_writes:
            #~ print 'SELECTING, timeout:', timeout, 'ptimeout:', ptimeout, 'socks:',t.waiting_reads.keys(), t.waiting_writes.keys()
            ready_to_read, ready_to_write, in_error = select.select(t.waiting_reads.keys(), t.waiting_writes.keys(), [], ptimeout)
            t.handle_events(ready_to_read, t.waiting_reads)
            t.handle_events(ready_to_write, t.waiting_writes)
            for i in in_error:
                t.handle_errored(i)
        else:
            time.sleep(t.RESOLUTION)
class KqueuePoller(Poller):
    def __init__(t, scheduler, default_size = 1024):
        super(t.__class__, t).__init__(scheduler)
        t.default_size = default_size
        t.kq = kqueue.kqueue()
        t.klist = []
    def __len__(t):
        return len(t.klist)
    def __repr__(t):
        return "<%s@%s klist:%r>" % (t.__class__.__name__, id(t), t.klist)
    #~ @debug(0)
    def remove(t, op, coro):
        fileno = getattr(op, 'fileno', None)
        if fileno:
            if fileno in t.klist:
                t.klist.remove(fileno)
                filter = kqueue.EVFILT_READ if isinstance(op, sockets.ReadOperation) else kqueue.EVFILT_WRITE
                delev = kqueue.EV_SET(fileno, filter, kqueue.EV_DELETE)
                delev.udata = op, coro
                t.kq.kevent(delev)
    #~ @debug(0)    
    def add(t, op, coro):
        fileno = op.fileno = op.sock.fileno()
        if op.fileno not in t.klist:
            t.klist.append(op.fileno)

        if isinstance(op, sockets.ReadOperation):
            ev = kqueue.EV_SET(fileno, kqueue.EVFILT_READ, kqueue.EV_ADD | kqueue.EV_ENABLE)
            ev.udata = op, coro
            t.kq.kevent(ev)
        if isinstance(op, sockets.WriteOperation):
            ev = kqueue.EV_SET(fileno, kqueue.EVFILT_WRITE, kqueue.EV_ADD | kqueue.EV_ENABLE)
            ev.udata = op, coro
            t.kq.kevent(ev)
    def run(t, timeout = 0):
        """ 
        Run a poller loop and return new socket events. Timeout is a timedelta object, 0 if active coros or None. 
        
        kqueue timeout param is a integer number of nanoseconds (seconds/10**9).
        """
        ptimeout = int(timeout.microseconds*1000+timeout.seconds*1000000000 if timeout else (t.nRESOLUTION if timeout is None else 0))
        if t.klist:
            events = t.kq.kevent(None, t.default_size, ptimeout)
            for ev in events:
                fd = ev.ident
                op, coro = ev.udata
                if ev.flags & kqueue.EV_ERROR:
                    print ' kqueue.EV_ERROR:', ev
                    if op.fileno in t.klist:
                        t.klist.remove(op.fileno)

                    delev = kqueue.EV_SET(op.fileno, ev.filter, kqueue.EV_DELETE)
                    delev.udata = ev.udata
                    t.kq.kevent(delev)
                    del delev
                    t.scheduler.active.append( (events.CoroutineException((events.ConnectionError, events.ConnectionError(op))), coro) )
                    continue
                fileno = op.fileno
                op = t.run_operation(op)
                if op:
                    if fileno in t.klist:
                        t.klist.remove(fileno)
                    delev = kqueue.EV_SET(fileno, ev.filter, kqueue.EV_DELETE)
                    delev.udata = ev.udata
                    t.kq.kevent(delev)
                    del delev
                    if op.prio & priority.OP:
                        op, coro = t.scheduler.process_op(coro.run_op(op), coro)
                    if coro:
                        if op.prio & priority.CORO:
                            t.scheduler.active.appendleft( (op, coro) )
                        else:
                            t.scheduler.active.append( (op, coro) )    
        
                    
class EpollPoller(Poller):
    def __init__(t, scheduler, default_size = 1024):
        t.scheduler = scheduler
        t.epoll_fd = epoll.epoll_create(default_size)
    def remove(t, op, coro):
        fileno = getattr(op, 'fileno', None)
        if fileno:
            if isinstance(op, sockets.ReadOperation):
                if fileno in t.waiting_reads:
                    del t.waiting_reads[fileno]
            if isinstance(op, sockets.WriteOperation):
                if fileno in t.waiting_writes:
                    del t.waiting_writes[fileno]
    def add(t, op, coro):
        fileno = op.fileno = op.sock.fileno()
        if isinstance(op, sockets.ReadOperation):
            assert fileno not in t.waiting_reads
            t.waiting_reads[fileno] = op, coro
            epoll.epoll_ctl(t.epoll_fd, epoll.EPOLL_CTL_ADD, fileno, epoll.EPOLLIN)
        if isinstance(op, sockets.WriteOperation):
            assert fileno not in t.waiting_writes
            t.waiting_writes[fileno] = op, coro
            epoll.epoll_ctl(t.epoll_fd, epoll.EPOLL_CTL_ADD, fileno, epoll.EPOLLOUT)

    def run(t, timeout = 0):
        """ 
        Run a poller loop and return new socket events. Timeout is a timedelta object, 0 if active coros or None. 
        
        epoll timeout param is a integer number of miliseconds (seconds/1000).
        """
        ptimeout = int(timeout.microseconds/1000+timeout.seconds*1000 if timeout else (t.mRESOLUTION if timeout is None else 0))
        if t.waiting_reads or t.waiting_writes:
            events = epoll.epoll_wait(t.epoll_fd, 10, ptimeout)
            for ev, fd in events:
                if ev == epoll.EPOLLIN:
                    waiting_ops = t.waiting_reads
                elif ev == epoll.EPOLLOUT:
                    waiting_ops = t.waiting_writes
                else:
                    t.handle_errored(fd)
                    continue
                    
                op, coro = waiting_ops[fd]
                op = t.run_operation(op)
                if op:
                    del waiting_ops[fd]
                    epoll.epoll_ctl(t.epoll_fd, epoll.EPOLL_CTL_DEL, fd, 0)
                    if op.prio & priority.OP:
                        op, coro = t.scheduler.process_op(coro.run_op(op), coro)
                    if coro:
                        if op.prio & priority.CORO:
                            t.scheduler.active.appendleft( (op, coro) )
                        else:
                            t.scheduler.active.append( (op, coro) )    
                
        else:
            time.sleep(t.RESOLUTION)
try:
    import epoll
except ImportError:
    epoll = None
try:
    import kqueue
    if kqueue.PYKQ_VERSION.split('.')[0] != '2':
        raise ImportError()
except ImportError:
    kqueue = None

if kqueue:
    DefaultPoller = KqueuePoller
elif epoll:
    DefaultPoller = EpollPoller
else:
    DefaultPoller = SelectPoller            
