from __future__ import division
from time import sleep
from select import epoll, EPOLLIN, EPOLLOUT, EPOLLPRI, EPOLLERR, EPOLLHUP, \
                            EPOLLET, EPOLLONESHOT, EPOLLMSG 



from base import ProactorBase, perform_recv, perform_accept, perform_send, \
                                perform_sendall, perform_sendfile, \
                                perform_connect

from cogen.core.sockets import ConnectionClosed

class StdlibEpollProactor(ProactorBase):
    "epoll based proactor implementation using python 2.6 select module."
    def __init__(self, scheduler, res, default_size=1024, **options):
        super(self.__class__, self).__init__(scheduler, res, **options)
        self.scheduler = scheduler
        self.epoll_obj = epoll(default_size)
        self.shadow = {}
                    
    def unregister_fd(self, act, fd=None):
        fileno = fd or act.sock.fileno()
        try:
            del self.shadow[fileno]
        except KeyError, e:
            import warnings
            warnings.warn("fd remove error: %r" % e)
            
        try:
            self.epoll_obj.unregister(fileno)
        except OSError, e:
            import warnings
            warnings.warn("fd remove error: %r" % e)
    
    def register_fd(self, act, performer):
        fileno = act.sock.fileno()
        self.shadow[fileno] = act
        flag =  EPOLLIN if performer == perform_recv \
                or performer == perform_accept else EPOLLOUT 
        
        if act.sock._proactor_added:
            self.epoll_obj.modify(fileno, flag | EPOLLONESHOT)
        else:
            self.epoll_obj.register(fileno, flag | EPOLLONESHOT)
        act.sock._proactor_added = True

    def run(self, timeout = 0):
        """ 
        Run a proactor loop and return new socket events. Timeout is a timedelta 
        object, 0 if active coros or None. 
        
        epoll timeout param is a integer number of seconds.
        """
        ptimeout = float(
            timeout.microseconds/1000000+timeout.seconds if timeout 
            else (self.resolution if timeout is None else 0)
        )
        if self.tokens:
            events = self.epoll_obj.poll(ptimeout, 1024)
            len_events = len(events)-1
            for nr, (fd, ev) in enumerate(events):
                act = self.shadow.pop(fd)
                if ev & EPOLLHUP:
                    self.epoll_obj.unregister(fd)
                    self.handle_error_event(act, 'Hang up.', ConnectionClosed)
                elif ev & EPOLLERR:
                    self.epoll_obj.unregister(fd)
                    self.handle_error_event(act, 'Unknown error.')
                else:
                    if nr == len_events:
                        ret = self.yield_event(act)
                        if not ret:
                            self.epoll_obj.modify(fd, ev | EPOLLONESHOT)
                            self.shadow[fd] = act
                        return ret
                    else:
                        if not self.handle_event(act):
                            self.epoll_obj.modify(fd, ev | EPOLLONESHOT)
                            self.shadow[fd] = act
                        
                
        else:
            sleep(timeout)
            # todo; fix this to timeout value
