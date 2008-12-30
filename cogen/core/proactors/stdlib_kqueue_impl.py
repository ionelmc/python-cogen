from __future__ import division
import sys
from select import kqueue, kevent, \
                    KQ_FILTER_READ, KQ_FILTER_WRITE, KQ_FILTER_AIO, \
                    KQ_FILTER_VNODE, KQ_FILTER_PROC, KQ_FILTER_NETDEV, \
                    KQ_FILTER_SIGNAL, KQ_FILTER_TIMER, KQ_EV_ADD, KQ_EV_DELETE, \
                    KQ_EV_ENABLE, KQ_EV_DISABLE, KQ_EV_ONESHOT, KQ_EV_CLEAR, \
                    KQ_EV_SYSFLAGS, KQ_EV_FLAG1, KQ_EV_EOF, KQ_EV_ERROR 

from time import sleep

from base import ProactorBase, perform_recv, perform_accept, perform_send, \
                                perform_sendall, perform_sendfile, \
                                perform_connect
from cogen.core import sockets
from cogen.core.util import priority
from cogen.core import events

class StdlibKQueueProactor(ProactorBase):
    "kqueue based proactor implementation using python 2.6 select module."
    def __init__(self, scheduler, res, default_size=1024, **options):
        super(self.__class__, self).__init__(scheduler, res, **options)
        self.kq = kqueue()
        self.kcontrol = self.kq.control
        self.default_size = default_size
        self.shadow = {}
    
    def unregister_fd(self, act, fd=None):
        fileno = fd or act.sock.fileno()
        try:
            del self.shadow[fileno]
        except KeyError, e:
            import warnings
            warnings.warn("fd remove error: %r" % e)
        
        try:
            self.kcontrol((kevent(fileno, act.flags, KQ_EV_DELETE),), 0)
        except OSError, e:
            import warnings
            warnings.warn("fd remove error: %r" % e)
    
    def register_fd(self, act, performer):
        fileno = act.sock.fileno()
        self.shadow[fileno] = act
        act.flags = flag = KQ_FILTER_READ if performer == perform_recv \
                or performer == perform_accept else KQ_FILTER_WRITE
        ev = kevent(fileno, flag, KQ_EV_ADD | KQ_EV_ONESHOT)
        self.kcontrol((ev,), 0)

    def run(self, timeout = 0):
        """ 
        Run a proactor loop and return new socket events. Timeout is a timedelta 
        object, 0 if active coros or None. 
        
        kqueue timeout param is a integer number of nanoseconds (seconds/10**9).
        """
        ptimeout = float(
            timeout.microseconds/1000000+timeout.seconds if timeout 
            else (self.resolution if timeout is None else 0)
        )
        if self.tokens:
            events = self.kcontrol(None, self.default_size, ptimeout)
            len_events = len(events)-1
            for nr, ev in enumerate(events):
                fd = ev.ident
                act = self.shadow.pop(fd)
                
                if ev.flags & KQ_EV_ERROR:
                    self.kcontrol((kevent(fd, act.flags, KQ_EV_DELETE),), 0)
                    self.handle_error_event(act, 'System error %s.'%ev.data)
                else:
                    if nr == len_events:
                        ret = self.yield_event(act)
                        if not ret:
                            ev.flags = KQ_EV_ADD | KQ_EV_ONESHOT
                            self.kcontrol((ev,), 0)
                            self.shadow[fd] = act
                        return ret
                    else:
                        if not self.handle_event(act):
                            ev.flags = KQ_EV_ADD | KQ_EV_ONESHOT
                            self.kcontrol((ev,), 0)
                            self.shadow[fd] = act
        else:
            sleep(timeout)
            