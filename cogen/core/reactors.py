"""
Network polling code.

The reactor works in tandem with the socket operations.
Here's the basic workflow:

  * the coroutine yields a operation
  * the scheduler runs that operation (the [Docs_CogenCoreEventsOperation#process process] method)
    Note: all the socket operations share the same [Docs_CogenCoreSocketsSocketoperation#process process] method
    * if run_or_add is False then the operation is added in the reactor for 
    polling (with the exception that if we have data in out internal buffers
    the operation is runned first)
    * if run_or_add is set (it's default) in the operation then in process 
    method the reactor's [Docs_CogenCoreReactorsReactorbase#run_or_add run_or_add] 
    is called with the operation and coroutine

  
Nnote: run_or_add is a optimization hack really, first it tries to run the
operation (this asumes the sockets are usualy ready) and if it raises any 
exceptions like EAGAIN, EWOULDBLOCK etc it adds that operation for polling 
(via select, epoll, kqueue etc) then the run method will be called only when 
select, epoll, kqueue says that the socket is ready.
"""

from __future__ import division
import collections
import time
import sys
import warnings
import traceback

try:
    import select
except ImportError:
    select = None

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

try:
    import win32file
    import win32event
    import win32api
    import pywintypes
    import socket
    import ctypes
    import struct       
except ImportError:
    win32file = None



from cogen.core import sockets
from cogen.core import events
from cogen.core.util import debug, TimeoutDesc, priority
__doc_all__ = [
    "ReactorBase",
    "SelectReactor",
    "KQueueReactor",
    "EpollReactor",
]
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
        
class SelectReactor(ReactorBase):
    def remove(self, op, coro):
        #~ print '> remove', op
        if isinstance(op, sockets.ReadOperation):
            if op.sock in self.waiting_reads:
                del self.waiting_reads[op.sock]
                return True
        if isinstance(op, sockets.WriteOperation):
            if op.sock in self.waiting_writes:
                del self.waiting_writes[op.sock]
                return True
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
        Run a reactor loop and return new socket events. Timeout is a timedelta 
        object, 0 if active coros or None. 
        
        select timeout param is a float number of seconds.
        """
        ptimeout = timeout.days*86400 + timeout.microseconds/1000000 + timeout.seconds \
                if timeout else (self.resolution if timeout is None else 0)
        if self.waiting_reads or self.waiting_writes:
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
            time.sleep(self.resolution)
class KQueueReactor(ReactorBase):
    def __init__(self, scheduler, res, default_size = 1024):
        super(self.__class__, self).__init__(scheduler, res)
        self.default_size = default_size
        self.kq = kqueue.kqueue()
        self.klist = {}
    def __len__(self):
        return len(self.klist)
    def __repr__(self):
        return "<%s@%s klist:%r>" % (
            self.__class__.__name__, 
            id(self), 
            self.klist
        )
    def waiting_op(self, testcoro):
        "Returns the registered operation for some specified coroutine."
        if testcoro in self.klist:
            return self.klist[testcoro]
    #~ @debug(0)
    def remove(self, op, coro):
        fileno = getattr(op, 'fileno', None)
        if fileno:
            if coro in self.klist:
                del self.klist[coro]
                filter = kqueue.EVFILT_READ \
                    if isinstance(op, sockets.ReadOperation) \
                    else kqueue.EVFILT_WRITE
                delev = kqueue.EV_SET(fileno, filter, kqueue.EV_DELETE)
                delev.udata = op, coro
                self.kq.kevent(delev)
                return True
    #~ @debug(0)    
    def add(self, op, coro):
        fileno = op.fileno = op.sock.fileno()
        if coro not in self.klist:
            self.klist[coro] = op

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
        Run a reactor loop and return new socket events. Timeout is a timedelta 
        object, 0 if active coros or None. 
        
        kqueue timeout param is a integer number of nanoseconds (seconds/10**9).
        """
        ptimeout = int(
            timeout.days*86400000000000 + 
            timeout.microseconds*1000 + 
            timeout.seconds*1000000000 
            if timeout else (self.n_resolution if timeout is None else 0)
        )
        if ptimeout>sys.maxint:
            ptimeout = sys.maxint
        if self.klist:
            #~ print ptimeout, self.klist
            events = self.kq.kevent(None, self.default_size, ptimeout)
            # should check here if timeout isn't negative or larger than maxint
            nr_events = len(events)-1
            for nr, ev in enumerate(events):
                fd = ev.ident
                op, coro = ev.udata
                if ev.flags & kqueue.EV_ERROR:
                    print ' kqueue.EV_ERROR:', ev
                    if coro in self.klist:
                        del self.klist[coro]

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
                    if coro in self.klist:
                        del self.klist[coro]
                    delev = kqueue.EV_SET(fileno, ev.filter, kqueue.EV_DELETE)
                    delev.udata = ev.udata
                    self.kq.kevent(delev)
                    del delev
                    if nr == nr_events:
                        return op, coro
                        
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

class PollReactor(ReactorBase):
    if select and hasattr(select, 'poll'):
        POLL_ERR = select.POLLERR | select.POLLHUP | select.POLLNVAL
        POLL_IN = select.POLLIN | select.POLLPRI | POLL_ERR
        POLL_OUT = select.POLLOUT | POLL_ERR
    def __init__(self, scheduler, res):
        super(self.__class__, self).__init__(scheduler, res)
        self.scheduler = scheduler
        self.poller = select.poll()
    def remove(self, op, coro):
        fileno = getattr(op, 'fileno', None)
        if fileno:
            if isinstance(op, sockets.ReadOperation):
                if fileno in self.waiting_reads:
                    try:
                        self.poller.unregister(fileno)
                    except OSError, e:
                        warnings.warn("FD Remove error: %r" % e)
                    del self.waiting_reads[fileno]
                    return True
            if isinstance(op, sockets.WriteOperation):
                if fileno in self.waiting_writes:
                    try:
                        self.poller.unregister(fileno)
                    except OSError:
                        warnings.warn("FD Remove error: %r" % e)
                    del self.waiting_writes[fileno]
                    return True
    def add(self, op, coro):
        fileno = op.fileno = op.sock.fileno()
        if isinstance(op, sockets.ReadOperation):
            assert fileno not in self.waiting_reads
            self.waiting_reads[fileno] = op, coro
            self.poller.register(fileno, self.POLL_IN)
        if isinstance(op, sockets.WriteOperation):
            assert fileno not in self.waiting_writes
            self.waiting_writes[fileno] = op, coro
            self.poller.register(fileno, self.POLL_OUT)

    def run(self, timeout = 0):
        """ 
        Run a reactor loop and return new socket events. Timeout is a timedelta 
        object, 0 if active coros or None. 
        """
        # poll timeout param is a integer number of miliseconds (seconds/1000).
        ptimeout = int(
            timeout.days * 86400000 + 
            timeout.microseconds / 1000 + 
            timeout.seconds * 1000 
            if timeout else (self.m_resolution if timeout is None else 0)
        )
        #~ print self.waiting_reads
        if self.waiting_reads or self.waiting_writes:
            events = self.poller.poll(ptimeout)
            nr_events = len(events)-1
            for nr, (fd, ev) in enumerate(events):
                if ev & self.POLL_IN:
                    waiting_ops = self.waiting_reads
                elif ev & self.POLL_OUT:
                    waiting_ops = self.waiting_writes
                else:
                    self.handle_errored(fd)
                    continue
                
                op, coro = waiting_ops[fd]
                op = self.run_operation(op)
                if op:
                    del waiting_ops[fd]
                    self.poller.unregister(fd)
                    if nr == nr_events:
                        return op, coro
                        
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
            time.sleep(self.resolution)


class EpollReactor(ReactorBase):
    def __init__(self, scheduler, res, default_size = 1024):
        super(self.__class__, self).__init__(scheduler, res)
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
                    return True
            if isinstance(op, sockets.WriteOperation):
                if fileno in self.waiting_writes:
                    try:
                        epoll.epoll_ctl(self.epoll_fd, 
                                        epoll.EPOLL_CTL_DEL, fileno, 0)
                    except OSError:
                        warnings.warn("FD Remove error: %r" % e)
                    del self.waiting_writes[fileno]
                    return True
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
        Run a reactor loop and return new socket events. Timeout is a timedelta 
        object, 0 if active coros or None. 
        
        epoll timeout param is a integer number of miliseconds (seconds/1000).
        """
        ptimeout = int(timeout.microseconds/1000+timeout.seconds*1000 
                if timeout else (self.m_resolution if timeout is None else 0))
        #~ print self.waiting_reads
        if self.waiting_reads or self.waiting_writes:
            events = epoll.epoll_wait(self.epoll_fd, 1024, ptimeout)
            nr_events = len(events)-1
                
            for nr, (ev, fd) in enumerate(events):
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
                    if nr == nr_events:
                        return op, coro
                        
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
            time.sleep(self.resolution)
    
class IOCPProactor(ReactorBase):
    def __init__(self, scheduler, res):
        super(self.__class__, self).__init__(scheduler, res)
        self.scheduler = scheduler
        self.iocp = win32file.CreateIoCompletionPort(
            win32file.INVALID_HANDLE_VALUE, None, 0, 0
        ) 
        self.fds = set()
        self.registered_ops = {}
        
    def __len__(self):
        return len(self.registered_ops)
    def __del__(self):
        win32file.CloseHandle(self.iocp)
        
    def __repr__(self):
        return "<%s@%s reg_ops:%r fds:%r>" % (
            self.__class__.__name__, 
            id(self), 
            self.registered_ops, 
            self.fds
        )
    def add(self, op, coro):
        fileno = op.sock._fd.fileno()
        self.registered_ops[op] = self.run_iocp(op, coro)
        
        if fileno not in self.fds:
            # silly CreateIoCompletionPort raises a exception if the 
            #fileno(handle) has already been registered with the iocp
            self.fds.add(fileno)
            win32file.CreateIoCompletionPort(fileno, self.iocp, 0, 0) 

    def run_iocp(self, op, coro):
        overlap = pywintypes.OVERLAPPED() 
        overlap.object = (op, coro)
        rc, nbytes = op.iocp(overlap)
        
        if rc == 0:
            # ah geez, it didn't got in the iocp, we have a result!
            win32file.PostQueuedCompletionStatus(
                self.iocp, nbytes, 0, overlap
            )
            # or we could just do it here, but this will get recursive, 
            #(todo: config option for this)
            #~ self.process_op(rc, nbytes, op, coro, overlap)
        return overlap

    def process_op(self, rc, nbytes, op, coro, overlap):
        overlap.object = None
        if rc == 0:
            op.iocp_done(rc, nbytes)
            prev_op = op
            op = self.run_operation(op, False) #no reactor, but proactor
            # result should be the same instance as prev_op or a coroutine exception
            if op:
                del self.registered_ops[prev_op] 
                
                win32file.CancelIo(prev_op.sock._fd.fileno()) 
                return op, coro
            else:
                # operation hasn't completed yet (not enough data etc)
                # readd it in the iocp
                self.registered_ops[prev_op] = self.run_iocp(prev_op, coro)
                
        else:
            #looks like we have a problem, forward it to the coroutine.
            
            # this needs some research: ERROR_NETNAME_DELETED, need to reopen 
            #the accept sock ?! something like:
            #    warnings.warn("ERROR_NETNAME_DELETED: %r. Re-registering operation." % op)
            #    self.registered_ops[op] = self.run_iocp(op, coro)
            del self.registered_ops[op]
            win32file.CancelIo(op.sock._fd.fileno())
            warnings.warn("%s on %r/%r" % (
                ctypes.FormatError(rc), op, coro), stacklevel=1
            )
            return events.CoroutineException((
                events.ConnectionError, events.ConnectionError(
                    (rc, "%s on %r" % (ctypes.FormatError(rc), op))
                )
            )), coro

    def waiting_op(self, testcoro):
        for op in self.registered_ops:
            if self.registered_ops[op].object[1] is testcoro:
                return op
    #~ @debug(0)
    def remove(self, op, coro):
        if op in self.registered_ops:
            self.registered_ops[op].object = None
            win32file.CancelIo(op.sock._fd.fileno())
            del self.registered_ops[op]
            return True

    def run(self, timeout = 0):
        # same resolution as epoll
        ptimeout = int(
            timeout.days * 86400000 + 
            timeout.microseconds / 1000 +
            timeout.seconds * 1000 
            if timeout else (self.m_resolution if timeout is None else 0)
        )
        if self.registered_ops:
            urgent = None
            # we use urgent as a optimisation: the last operation is returned 
            #directly to the scheduler (the sched might just run it till it 
            #goes to sleep) and not added in the sched.active queue
            while 1:
                try:
                    rc, nbytes, key, overlap = win32file.GetQueuedCompletionStatus(
                        self.iocp,
                        ptimeout
                    )
                except RuntimeError, e:
                    # this needs some research
                    print e
                    sys.exc_clear()
                    break 
                    
                # well, this is a bit weird, if we get a aborted rc (via CancelIo
                #i suppose) evaluating the overlap crashes the interpeter 
                #with a memory read error
                if rc != win32file.WSA_OPERATION_ABORTED and overlap:
                    
                    if urgent:
                        op, coro = urgent
                        urgent = None
                        if op.prio & priority.OP:
                            # imediately run the asociated coroutine step
                            op, coro = self.scheduler.process_op(
                                coro.run_op(op), 
                                coro
                            )
                        if coro:
                            if op.prio & priority.CORO:
                                self.scheduler.active.appendleft( (op, coro) )
                            else:
                                self.scheduler.active.append( (op, coro) )                     
                    if overlap.object:
                        op, coro = overlap.object
                        urgent = self.process_op(rc, nbytes, op, coro, overlap)
                else:
                    break
            return urgent
        else:
            time.sleep(self.resolution)    
            

available = []
if select:
    DefaultReactor = SelectReactor
    available.append(SelectReactor)
if select and hasattr(select, 'poll'):
    DefaultReactor = PollReactor
    available.append(PollReactor)
if kqueue:
    DefaultReactor = KQueueReactor
    available.append(KQueueReactor)
if epoll:
    DefaultReactor = EpollReactor
    available.append(EpollReactor)
if win32file:
    DefaultReactor = IOCPProactor
    available.append(IOCPProactor)
