import sys
import errno, socket.error as soerror
from cogen.core.events import ConnectionClosed
from cogen.core.sockets import Socket
class ReactorBase(object):
    """
    A reactor just checks if there are ready-sockets for the operations.
    The operations are not done here, they are done in the socket ops instances.
    """
    __doc_all__ = [
        '__init__', 'run_once', 'run_operation', 'run_or_add', 'add', 
        'waiting_op', '__len__', 'handle_errored', 'remove', 'run', 
        'handle_events'
    ]
    
    def __init__(self, scheduler, resolution):
        self.tokens = {}
        self.scheduler = scheduler
        self.resolution = resolution # seconds
        self.m_resolution = resolution*1000 # miliseconds
        self.n_resolution = resolution*1000000000 #nanoseconds
    
    def request_recv(self, act, coro, run_first):
        result = run_first and self.try_run(act, self, perform_recv)
        if result:
            return result, coro
        else:
            self.add_token(act, coro, perform_recv)
            
    def request_send(self, act, coro, buff, run_first):
        result = run_first and self.try_run(act, self, perform_send)
        if result:
            return result, coro
        else:
            self.add_token(act, coro, perform_send)
    def request_sendall(self, act, coro, buff, run_first):
        result = run_first and self.try_run(act, self, perform_sendall)
        if result:
            return result, coro
        else:
            self.add_token(act, coro, perform_sendall)
    def request_accept(self, act, coro, run_first):
        result = run_first and self.try_run(act, self, perform_accept)
        if result:
            return result, coro
        else:
            self.add_token(act, coro, perform_accept)
    def request_connect(self, act, coro, addr, run_first):
        result = run_first and self.try_run(act, self, perform_connect)
        if result:
            return result, coro
        else:
            self.add_token(act, coro, perform_connect)
    
    def perform_recv(self, act, length):
        act.sock.buff = act.sock._fd.recv(length)
        
    def perform_send(self, act, coro, buff):
        act.sent = act.sock._fd.send(buff)
        
    def perform_sendall(self, act, coro, buff):
        act.sent = act.sock._fd.sendall(buff)
        
    def perform_accept(self, act, coro):
        self.conn, self.addr = self.sock._fd.accept()
        self.conn.setblocking(0)
        self.conn = Socket(_sock=self.conn)
            
    def perform_connect(self, act, coro, addr):
        if act.connect_attempted:
            try:
                act.sock._fd.getpeername()
            except soerror, exc:
                if exc[0] not in (errno.EAGAIN, errno.EWOULDBLOCK, 
                                errno.EINPROGRESS, errno.ENOTCONN):
                    return
            return act
        err = act.sock._fd.connect_ex(act.addr)
        act.connect_attempted = True
        if err:
            if err == errno.EISCONN:
                return act
            if err not in (errno.EAGAIN, errno.EWOULDBLOCK, errno.EINPROGRESS):
                return events.ConnectionError(err, errno.errorcode[err])
        else: # err==0 means successful connect
            return act
            

    def add_token(self, act, coro, performer):
        assert act not in self.tokens
        
        self.tokens[act] = coro, performer
        
    def remove_token(self, act):
        if act in self.tokens:
            del self.tokens[act]
        
    def try_run(self, act, func, *args):
        try:
            return func(*args)
        except soerror, exc:
            if exc[0] in (errno.EAGAIN, errno.EWOULDBLOCK, errno.EINPROGRESS): 
                return
            elif exc[0] == errno.EPIPE:
                return events.ConnectionClosed(exc)
            else:
                return events.ConnectionError(exc)
        return act
    
    def register_fd(self, act, coro, performer):
        raise NotImplementedError()
        
    def unregister_fd(self, act, coro, performer):
        raise NotImplementedError()