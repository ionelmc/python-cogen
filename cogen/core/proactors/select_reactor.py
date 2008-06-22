from __future__ import division
import select, time

from base import ReactorBase
from cogen.core import sockets
from cogen.core.util import priority

class SelectReactor(ReactorBase):
    def remove(self, op, coro):
        #~ print '> remove', op
        fileno = op.sock.fileno()
        if isinstance(op, sockets.ReadOperation):
            if fileno in self.waiting_reads:
                del self.waiting_reads[fileno]
                return True
        if isinstance(op, sockets.WriteOperation):
            if fileno in self.waiting_writes:
                del self.waiting_writes[fileno]
                return True
    def add(self, op, coro):
        if isinstance(op, sockets.ReadOperation):
            assert op.sock not in self.waiting_reads
            self.waiting_reads[op.sock.fileno()] = op, coro
            
        if isinstance(op, sockets.WriteOperation):
            assert op.sock not in self.waiting_writes
            self.waiting_writes[op.sock.fileno()] = op, coro
            
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
