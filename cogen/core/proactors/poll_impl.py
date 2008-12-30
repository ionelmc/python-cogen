from __future__ import division
from select import poll, POLLERR, POLLHUP, POLLNVAL, POLLIN, POLLPRI, POLLOUT
from time import sleep

from base import ProactorBase, perform_recv, perform_accept, perform_send, \
                                perform_sendall, perform_sendfile, \
                                perform_connect
                                
from cogen.core.sockets import ConnectionClosed
from cogen.core import sockets
from cogen.core.util import priority

class PollProactor(ProactorBase):
    POLL_ERR = POLLERR | POLLHUP | POLLNVAL
    POLL_IN = POLLIN | POLLPRI | POLL_ERR
    POLL_OUT = POLLOUT | POLL_ERR
    
    def __init__(self, scheduler, res, **options):
        super(self.__class__, self).__init__(scheduler, res, **options)
        self.scheduler = scheduler
        self.poller = poll()
        self.shadow = {}

    def unregister_fd(self, act, fd=None):
        fileno = fd or act.sock.fileno()
        try:
            del self.shadow[fileno]
        except KeyError, e:
            import warnings
            warnings.warn("fd remove error: %r" % e)
        self.poller.unregister(fileno)
                    
    def register_fd(self, act, performer):
        fileno = act.sock.fileno()
        self.shadow[fileno] = act
        flag =  self.POLL_IN if performer == perform_recv \
                or performer == perform_accept else self.POLL_OUT 
        self.poller.register(fileno, flag | self.POLL_ERR)
        
    def run(self, timeout = 0):
        """ 
        Run a proactor loop and return new socket events. Timeout is a timedelta 
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
                act = self.shadow[fd]
                if ev & POLLHUP:
                    self.handle_error_event(act, 'Hang up.', fd, ConnectionClosed)
                elif ev & POLLNVAL:
                    self.handle_error_event(act, 'Invalid descriptor.', fd)
                elif ev & POLLERR:
                    self.handle_error_event(act, 'Unknown error.', fd)
                else:
                    if nr == len_events:
                        ret = self.yield_event(act)
                        if ret:
                            self.poller.unregister(fd)
                            del self.shadow[fd]
                        return ret
                    else:
                        if self.handle_event(act):
                            self.poller.unregister(fd)
                            del self.shadow[fd]
        else:
            sleep(timeout)
