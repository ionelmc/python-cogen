"""
Network polling code.
"""

from __future__ import division
import select
import collections
import time
import sys
import warnings

from cogen.core import sockets
from cogen.core import events
from cogen.core.util import debug, TimeoutDesc, priority
__doc_all__ = [
    "Poller",
    "SelectPoller",
    "KQueuePoller",
    "EpollPoller",
]
class Poller(object):
    """
    A poller just checks if there are ready-sockets for the operations.
    The operations are not done here, they are done in the socket ops instances.
    """
    __doc_all__ = [
        '__init__', 'run_once', 'run_operation', 'run_or_add', 'add', 
        'waiting_op', '__len__', 'handle_errored', 'remove', 'run', 
        'handle_events'
    ]
    
    RESOLUTION = 0.02
    mRESOLUTION = RESOLUTION*1000
    nRESOLUTION = RESOLUTION*1000000000
    def __init__(self, scheduler):
        self.waiting_reads = {}
        self.waiting_writes = {}
        self.scheduler = scheduler
    def run_once(self, fdesc, waiting_ops):           
        """ Run a operation, remove it from the poller and return the result. 
        Called from the main poller loop. """
        op, coro = waiting_ops[fdesc]
        op = self.run_operation()
        if op:
            del waiting_ops[fdesc]
            return op, coro
    def run_operation(self, op):
        " Run the socket op and return result or exception. "
        try:
            r = op.try_run()
        except:
            r = events.CoroutineException(sys.exc_info())
        return r
    def run_or_add(self, op, coro):
        """ Perform operation or add the operation in the poller if socket isn't
        ready. Called from the scheduller. """
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
        "Returns number of waiting operations registered in the poller."
        return len(self.waiting_reads) + len(self.waiting_writes)
    def __repr__(self):
        return "<%s@%s reads:%r writes:%r>" % (
            self.__class__, 
            id(self), 
            self.waiting_reads, 
            self.waiting_writes
        )

    def handle_errored(self, desc):
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
                events.ConnectionError, events.ConnectionError(op)
            )), 
            coro
        ))
        
class SelectPoller(Poller):
    def remove(self, op, coro):
        #~ print '> remove', op
        if isinstance(op, sockets.ReadOperation):
            if op.sock in self.waiting_reads:
                del self.waiting_reads[op.sock]
        if isinstance(op, sockets.WriteOperation):
            if op.sock in self.waiting_writes:
                del self.waiting_writes[op.sock]
    def add(self, op, coro):
        if isinstance(op, sockets.ReadOperation):
            assert op.sock not in self.waiting_reads
            self.waiting_reads[op.sock] = op, coro
            
        if isinstance(op, sockets.WriteOperation):
            assert op.sock not in self.waiting_writes
            self.waiting_writes[op.sock] = op, coro
            
    def handle_events(self, ready, waiting_ops):
        for id in ready:
            op, coro = waiting_ops[id]
            op = self.run_operation(op)
            if op:
                del waiting_ops[id]
                
            
                if op.prio & priority.OP:
                    op, coro = self.scheduler.process_op(coro.run_op(op), coro)
                if coro:
                    if op.prio & priority.CORO:
                        self.scheduler.active.appendleft( (op, coro) )
                    else:
                        self.scheduler.active.append( (op, coro) )

        
    def run(self, timeout = 0):
        """ 
        Run a poller loop and return new socket events. Timeout is a timedelta 
        object, 0 if active coros or None. 
        
        select timeout param is a float number of seconds.
        """
        ptimeout = timeout.microseconds/1000000+timeout.seconds \
                if timeout else (self.RESOLUTION if timeout is None else 0)
        if self.waiting_reads or self.waiting_writes:
            #~ print 'SELECTING, timeout:', timeout, 'ptimeout:', ptimeout, 'socks:',self.waiting_reads, self.waiting_writes
            ready_to_read, ready_to_write, in_error = select.select(
                self.waiting_reads.keys(), 
                self.waiting_writes.keys(), 
                [], 
                ptimeout
            )
            self.handle_events(ready_to_read, self.waiting_reads)
            self.handle_events(ready_to_write, self.waiting_writes)
            for i in in_error:
                self.handle_errored(i)
        else:
            time.sleep(self.RESOLUTION)
class KQueuePoller(Poller):
    def __init__(self, scheduler, default_size = 1024):
        super(self.__class__, self).__init__(scheduler)
        self.default_size = default_size
        self.kq = kqueue.kqueue()
        self.klist = []
    def __len__(self):
        return len(self.klist)
    def __repr__(self):
        return "<%s@%s klist:%r>" % (
            self.__class__, 
            id(self), 
            self.klist
        )
    #~ @debug(0)
    def remove(self, op, coro):
        fileno = getattr(op, 'fileno', None)
        if fileno:
            if fileno in self.klist:
                self.klist.remove(fileno)
                filter = kqueue.EVFILT_READ \
                    if isinstance(op, sockets.ReadOperation) \
                    else kqueue.EVFILT_WRITE
                delev = kqueue.EV_SET(fileno, filter, kqueue.EV_DELETE)
                delev.udata = op, coro
                self.kq.kevent(delev)
    #~ @debug(0)    
    def add(self, op, coro):
        fileno = op.fileno = op.sock.fileno()
        if op.fileno not in self.klist:
            self.klist.append(op.fileno)

        if isinstance(op, sockets.ReadOperation):
            ev = kqueue.EV_SET(
                fileno, 
                kqueue.EVFILT_READ, 
                kqueue.EV_ADD | kqueue.EV_ENABLE
            )
            ev.udata = op, coro
            self.kq.kevent(ev)
        if isinstance(op, sockets.WriteOperation):
            ev = kqueue.EV_SET(
                fileno, 
                kqueue.EVFILT_WRITE, 
                kqueue.EV_ADD | kqueue.EV_ENABLE
            )
            ev.udata = op, coro
            self.kq.kevent(ev)
    def run(self, timeout = 0):
        """ 
        Run a poller loop and return new socket events. Timeout is a timedelta 
        object, 0 if active coros or None. 
        
        kqueue timeout param is a integer number of nanoseconds (seconds/10**9).
        """
        ptimeout = int(timeout.microseconds*1000+timeout.seconds*1000000000 
                if timeout else (self.nRESOLUTION if timeout is None else 0))
        if self.klist:
            events = self.kq.kevent(None, self.default_size, ptimeout)
            for ev in events:
                fd = ev.ident
                op, coro = ev.udata
                if ev.flags & kqueue.EV_ERROR:
                    print ' kqueue.EV_ERROR:', ev
                    if op.fileno in self.klist:
                        self.klist.remove(op.fileno)

                    delev = kqueue.EV_SET(
                        op.fileno, 
                        ev.filter, 
                        kqueue.EV_DELETE
                    )
                    delev.udata = ev.udata
                    self.kq.kevent(delev)
                    del delev
                    self.scheduler.active.append((
                        events.CoroutineException((
                            events.ConnectionError, 
                            events.ConnectionError(op)
                        )), 
                        coro
                    ))
                    continue
                fileno = op.fileno
                op = self.run_operation(op)
                if op:
                    if fileno in self.klist:
                        self.klist.remove(fileno)
                    delev = kqueue.EV_SET(fileno, ev.filter, kqueue.EV_DELETE)
                    delev.udata = ev.udata
                    self.kq.kevent(delev)
                    del delev
                    if op.prio & priority.OP:
                        op, coro = self.scheduler.process_op(
                            coro.run_op(op), 
                            coro
                        )
                    if coro:
                        if op.prio & priority.CORO:
                            self.scheduler.active.appendleft( (op, coro) )
                        else:
                            self.scheduler.active.append( (op, coro) )    
        
                    
class EpollPoller(Poller):
    def __init__(self, scheduler, default_size = 1024):
        super(self.__class__, self).__init__(scheduler)
        self.scheduler = scheduler
        self.epoll_fd = epoll.epoll_create(default_size)
    def remove(self, op, coro):
        fileno = getattr(op, 'fileno', None)
        if fileno:
            if isinstance(op, sockets.ReadOperation):
                if fileno in self.waiting_reads:
                    try:
                        epoll.epoll_ctl(self.epoll_fd, 
                                        epoll.EPOLL_CTL_DEL, fileno, 0)
                    except OSError, e:
                        warnings.warn("FD Remove error: %r" % e)
                    del self.waiting_reads[fileno]
            if isinstance(op, sockets.WriteOperation):
                if fileno in self.waiting_writes:
                    try:
                        epoll.epoll_ctl(self.epoll_fd, 
                                        epoll.EPOLL_CTL_DEL, fileno, 0)
                    except OSError:
                        warnings.warn("FD Remove error: %r" % e)
                    del self.waiting_writes[fileno]
    def add(self, op, coro):
        fileno = op.fileno = op.sock.fileno()
        if isinstance(op, sockets.ReadOperation):
            assert fileno not in self.waiting_reads
            self.waiting_reads[fileno] = op, coro
            epoll.epoll_ctl(
                self.epoll_fd, 
                epoll.EPOLL_CTL_ADD, 
                fileno, 
                epoll.EPOLLIN
            )
        if isinstance(op, sockets.WriteOperation):
            assert fileno not in self.waiting_writes
            self.waiting_writes[fileno] = op, coro
            epoll.epoll_ctl(
                self.epoll_fd, 
                epoll.EPOLL_CTL_ADD, 
                fileno, 
                epoll.EPOLLOUT
            )

    def run(self, timeout = 0):
        """ 
        Run a poller loop and return new socket events. Timeout is a timedelta 
        object, 0 if active coros or None. 
        
        epoll timeout param is a integer number of miliseconds (seconds/1000).
        """
        ptimeout = int(timeout.microseconds/1000+timeout.seconds*1000 
                if timeout else (self.mRESOLUTION if timeout is None else 0))
        #~ print self.waiting_reads
        if self.waiting_reads or self.waiting_writes:
            events = epoll.epoll_wait(self.epoll_fd, 10, ptimeout)
            for ev, fd in events:
                if ev == epoll.EPOLLIN:
                    waiting_ops = self.waiting_reads
                elif ev == epoll.EPOLLOUT:
                    waiting_ops = self.waiting_writes
                else:
                    self.handle_errored(fd)
                    continue
                
                op, coro = waiting_ops[fd]
                op = self.run_operation(op)
                if op:
                    del waiting_ops[fd]
                    epoll.epoll_ctl(self.epoll_fd, epoll.EPOLL_CTL_DEL, fd, 0)
                    if op.prio & priority.OP:
                        op, coro = self.scheduler.process_op(
                            coro.run_op(op), 
                            coro
                        )
                    if coro:
                        if op.prio & priority.CORO:
                            self.scheduler.active.appendleft( (op, coro) )
                        else:
                            self.scheduler.active.append( (op, coro) )    
        else:
            time.sleep(self.RESOLUTION)
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
    DefaultPoller = KQueuePoller
elif epoll:
    DefaultPoller = EpollPoller
else:
    DefaultPoller = SelectPoller            
