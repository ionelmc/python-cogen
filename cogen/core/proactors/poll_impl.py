from __future__ import division
import select, time

from base import ProactorBase
from cogen.core import sockets
from cogen.core.util import priority

class PollProactor(ProactorBase):
    POLL_ERR = select.POLLERR | select.POLLHUP | select.POLLNVAL
    POLL_IN = select.POLLIN | select.POLLPRI | POLL_ERR
    POLL_OUT = select.POLLOUT | POLL_ERR
    
    def __init__(self, scheduler, res):
        super(self.__class__, self).__init__(scheduler, res)
        self.scheduler = scheduler
        self.poller = select.poll()
        self.shadow = {}

    def unregister_fd(self, act):
        try:
            del self.shadow[fileno.sock.fileno()]
            self.poller.unregister(act.sock.fileno())
        except KeyError, e:
            import warnings
            warnings.warn("fd remove error: %r" % e)
                    
    def register_fd(self, act, performer):
        fileno = act.sock.fileno()
        print fileno, act
        self.shadow[fileno] = act
        flag =  self.POLL_IN if performer == self.perform_recv \
                or performer == self.perform_accept else epoll.POLL_OUT 
        self.poller.register(fileno, flag | self.POLL_ERR)
        
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
        if self.tokens:
            events = self.poller.poll(ptimeout)
            len_events = len(events)-1
            for nr, (fd, ev) in enumerate(events):
                print fd, ev
                act = self.shadow.pop(fd)
                if ev & select.POLLHUP:
                    self.handle_error_event(act, 'Hang up.', ConnectionClosed)
                if ev & select.POLLNVAL:
                    self.handle_error_event(act, 'Invalid descriptor.')
                elif ev & select.POLLERR:
                    self.handle_error_event(act, 'Unknown error.')
                else:
                    if nr == len_events:
                        ret = self.yield_event(act)
                        if ret:
                            self.poller.unregister(fd)
                        return ret
                    else:
                        if self.handle_event(act):
                            self.poller.unregister(fd)
                        else:
                            self.shadow[fd] = act
        else:
            time.sleep(self.resolution)
