from __future__ import division
from epoll import epoll_create, epoll_ctl, EPOLL_CTL_DEL, EPOLLIN, EPOLLOUT, \
                    epoll_ctl, EPOLL_CTL_MOD, EPOLL_CTL_ADD, EPOLLONESHOT, \
                    epoll_wait, EPOLLHUP, EPOLLERR

from time import sleep

from .base import ProactorBase, perform_recv, perform_accept, perform_send, \
                                perform_sendall, perform_sendfile, \
                                perform_connect

from ..sockets import ConnectionClosed

class EpollProactor(ProactorBase):
    def __init__(self, scheduler, res, default_size=1024, **options):
        super(self.__class__, self).__init__(scheduler, res, **options)
        self.scheduler = scheduler
        self.epoll_fd = epoll_create(default_size)
        self.shadow = {}

    def unregister_fd(self, act, fd=None):
        fileno = fd or act.sock.fileno()
        try:
            del self.shadow[fileno]
        except KeyError, e:
            import warnings
            warnings.warn("fd remove error: %r" % e)

        try:
            epoll_ctl(self.epoll_fd, EPOLL_CTL_DEL, fileno, 0)
        except OSError, e:
            import warnings
            warnings.warn("fd remove error: %r" % e)

    def register_fd(self, act, performer):
        fileno = act.sock.fileno()
        self.shadow[fileno] = act
        flag =  EPOLLIN if performer == perform_recv \
                or performer == perform_accept else EPOLLOUT
        epoll_ctl(
            self.epoll_fd,
            EPOLL_CTL_MOD if act.sock._proactor_added else EPOLL_CTL_ADD,
            fileno,
            flag | EPOLLONESHOT
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
            epoll_fd = self.epoll_fd
            events = epoll_wait(epoll_fd, 1024, ptimeout)
            len_events = len(events)-1
            for nr, (ev, fd) in enumerate(events):
                act = self.shadow.pop(fd)
                if ev & EPOLLHUP:
                    epoll_ctl(self.epoll_fd, EPOLL_CTL_DEL, fd, 0)
                    self.handle_error_event(act, 'Hang up.', ConnectionClosed)
                elif ev & EPOLLERR:
                    epoll_ctl(self.epoll_fd, EPOLL_CTL_DEL, fd, 0)
                    self.handle_error_event(act, 'Unknown error.')
                else:
                    if nr == len_events:
                        ret = self.yield_event(act)
                        if not ret:
                            epoll_ctl(epoll_fd, EPOLL_CTL_MOD, fd, ev | EPOLLONESHOT)
                            self.shadow[fd] = act
                        return ret
                    else:
                        if not self.handle_event(act):
                            epoll_ctl(epoll_fd, EPOLL_CTL_MOD, fd, ev | EPOLLONESHOT)
                            self.shadow[fd] = act

        else:
            sleep(timeout)
            # todo; fix this to timeout value
