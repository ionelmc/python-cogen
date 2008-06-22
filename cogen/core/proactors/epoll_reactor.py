from __future__ import division
import epoll, time

from base import ReactorBase
from cogen.core import sockets
from cogen.core.util import priority

class EpollReactor(ReactorBase):
    def __init__(self, scheduler, res, default_size = 1024):
        super(self.__class__, self).__init__(scheduler, res)
        self.scheduler = scheduler
        self.epoll_fd = epoll.epoll_create(default_size)
    def remove(self, op, coro):
        fileno = op.fileno
        if fileno:
            if isinstance(op, sockets.ReadOperation):
                if fileno in self.waiting_reads:
                    try:
                        epoll.epoll_ctl(self.epoll_fd, 
                                        epoll.EPOLL_CTL_DEL, fileno, 0)
                    except OSError, e:
                        import warnings
                        warnings.warn("FD Remove error: %r" % e)
                    del self.waiting_reads[fileno]
                    return True
            if isinstance(op, sockets.WriteOperation):
                if fileno in self.waiting_writes:
                    try:
                        epoll.epoll_ctl(self.epoll_fd, 
                                        epoll.EPOLL_CTL_DEL, fileno, 0)
                    except OSError:
                        import warnings
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
                epoll.EPOLL_CTL_MOD if op.sock._reactor_added else epoll.EPOLL_CTL_ADD, 
                fileno, 
                epoll.EPOLLIN | epoll.EPOLLONESHOT
            )
        elif isinstance(op, sockets.WriteOperation):
            assert fileno not in self.waiting_writes
            self.waiting_writes[fileno] = op, coro
            epoll.epoll_ctl(
                self.epoll_fd, 
                epoll.EPOLL_CTL_MOD if op.sock._reactor_added else epoll.EPOLL_CTL_ADD,
                fileno, 
                epoll.EPOLLOUT | epoll.EPOLLONESHOT 
            )
        else:
            raise RuntimeError("Bad operation %s" % op)
        op.sock._reactor_added = True

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
                    print fd, ev
                    self.handle_errored(fd, ev)
                    continue
                op, coro = waiting_ops[fd]
                op = self.run_operation(op)
                if op:
                    del waiting_ops[fd]
                    
                    #~ epoll.epoll_ctl(self.epoll_fd, epoll.EPOLL_CTL_DEL, fd, 0)
                    # no longer necesary because of EPOLLONESHOT
                    if self.scheduler.ops_greedy:
                        while True:
                            op, coro = self.scheduler.process_op(coro.run_op(op), coro)
                            if not op and not coro:
                                break  
                    else:
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
                    epoll.epoll_ctl(self.epoll_fd, epoll.EPOLL_CTL_MOD, fd, ev | epoll.EPOLLONESHOT)
        else:
            time.sleep(self.resolution)
            # todo; fix this to timeout value
