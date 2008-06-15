from __future__ import division
import kqueue, time, sys

from base import ReactorBase
from cogen.core import sockets
from cogen.core.util import priority
from cogen.core import events

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
        fileno = op.fileno
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
                kqueue.EV_ADD | kqueue.EV_ENABLE | kqueue.EV_ONESHOT
            )
            ev.udata = op, coro
            self.kq.kevent(ev)
        if isinstance(op, sockets.WriteOperation):
            ev = kqueue.EV_SET(
                fileno, 
                kqueue.EVFILT_WRITE, 
                kqueue.EV_ADD | kqueue.EV_ENABLE | kqueue.EV_ONESHOT
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
                            events.ConnectionError(ev.flags, ev.data, "EV_ERROR on %s" % op)
                        )), 
                        coro
                    ))
                    continue
                fileno = op.fileno
                op = self.run_operation(op)
                if op:
                    if coro in self.klist:
                        del self.klist[coro]
                    #~ delev = kqueue.EV_SET(fileno, ev.filter, kqueue.EV_DELETE)
                    #~ delev.udata = ev.udata
                    #~ self.kq.kevent(delev)
                    #~ del delev
                    # one-shot
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
                    ev.flags = kqueue.EV_ADD | kqueue.EV_ENABLE | kqueue.EV_ONESHOT
                    self.kq.kevent(ev)
