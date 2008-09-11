from __future__ import division
import select, time

from base import ReactorBase
from cogen.core import sockets
from cogen.core.util import priority

class PollReactor(ReactorBase):
    if hasattr(select, 'poll'):
        POLL_ERR = select.POLLERR | select.POLLHUP | select.POLLNVAL
        POLL_IN = select.POLLIN | select.POLLPRI | POLL_ERR
        POLL_OUT = select.POLLOUT | POLL_ERR
        
    def __init__(self, scheduler, res):
        super(self.__class__, self).__init__(scheduler, res)
        self.scheduler = scheduler
        self.poller = select.poll()
    def remove(self, op, coro):
        fileno = op.fileno
        if fileno:
            if isinstance(op, sockets.ReadOperation):
                if fileno in self.waiting_reads:
                    try:
                        self.poller.unregister(fileno)
                    except OSError, e:
                        import warnings
                        warnings.warn("FD Remove error: %r" % e)
                    del self.waiting_reads[fileno]
                    return True
            if isinstance(op, sockets.WriteOperation):
                if fileno in self.waiting_writes:
                    try:
                        self.poller.unregister(fileno)
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
                if (ev & select.POLLIN) or (ev & select.POLLPRI):
                    waiting_ops = self.waiting_reads
                elif ev & select.POLLOUT:
                    waiting_ops = self.waiting_writes
                else:
                    self.handle_errored(fd, ev)
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
