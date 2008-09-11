from __future__ import division
import epoll, time

from base import ProactorBase, perform_recv, perform_accept, perform_send, \
                                perform_sendall, perform_sendfile, \
                                perform_connect
from cogen.core import sockets
from cogen.core.util import priority

class EpollProactor(ProactorBase):
    def __init__(self, scheduler, res, default_size=1024, **options):
        super(self.__class__, self).__init__(scheduler, res, **options)
        self.scheduler = scheduler
        self.epoll_fd = epoll.epoll_create(default_size)
        self.shadow = {}
                    
    def unregister_fd(self, act):
        try:
            del self.shadow[fileno.sock.fileno()]
        except KeyError, e:
            import warnings
            warnings.warn("fd remove error: %r" % e)
            
        try:
            epoll.epoll_ctl(self.epoll_fd, epoll.EPOLL_CTL_DEL, act.sock.fileno(), 0)
        except OSError, e:
            import warnings
            warnings.warn("fd remove error: %r" % e)

    
    def register_fd(self, act, performer):
        fileno = act.sock.fileno()
        self.shadow[fileno] = act
        flag =  epoll.EPOLLIN if performer == perform_recv \
                or performer == perform_accept else epoll.EPOLLOUT 
        epoll.epoll_ctl(
            self.epoll_fd, 
            epoll.EPOLL_CTL_MOD if act.sock._proactor_added else epoll.EPOLL_CTL_ADD, 
            fileno, 
            flag | epoll.EPOLLONESHOT
        )
        act.sock._proactor_added = True

    def run(self, timeout = 0):
        """ 
        Run a proactor loop and return new socket events. Timeout is a timedelta 
        object, 0 if active coros or None. 
        
        epoll timeout param is a integer number of miliseconds (seconds/1000).
        """
        ptimeout = int(timeout.microseconds/1000+timeout.seconds*1000 
                if timeout else (self.m_resolution if timeout is None else 0))
        if self.tokens:
            events = epoll.epoll_wait(self.epoll_fd, 1024, ptimeout)
            len_events = len(events)-1
            for nr, (ev, fd) in enumerate(events):
                act = self.shadow.pop(fd)
                if ev & epoll.EPOLLHUP:
                    self.handle_error_event(act, 'Hang up.', ConnectionClosed)
                elif ev & epoll.EPOLLERR:
                    self.handle_error_event(act, 'Unknown error.')
                else:
                    if nr == len_events:
                        ret = self.yield_event(act)
                        if not ret:
                            self.shadow[fd] = act
                            epoll.epoll_ctl(self.epoll_fd, epoll.EPOLL_CTL_MOD, fd, ev | epoll.EPOLLONESHOT)
                        return ret
                    else:
                        if not self.handle_event(act):
                            self.shadow[fd] = act
                            epoll.epoll_ctl(self.epoll_fd, epoll.EPOLL_CTL_MOD, fd, ev | epoll.EPOLLONESHOT)
                
        else:
            time.sleep(self.resolution)
            # todo; fix this to timeout value
