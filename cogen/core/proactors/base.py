import sys
import errno
from socket import error as soerror
try:
    import sendfile
except:
    sendfile = None

from cogen.core.events import ConnectionClosed, ConnectionError, CoroutineException
from cogen.core.sockets import Socket
from cogen.core.util import priority, debug


def perform_recv(act):
    act.buff = act.sock._fd.recv(act.len)
    if act.buff:
        return act
    else:
        raise ConnectionClosed("Empty recv.")
    
def perform_send(act):
    act.sent = act.sock._fd.send(act.buff)
    return act.sent and act
    
def perform_sendall(act):
    act.sent += act.sock._fd.send(act.buff[act.sent:])
    return act.sent==len(act.buff) and act
    
def perform_accept(act):
    act.conn, act.addr = act.sock._fd.accept()
    act.conn.setblocking(0)
    act.conn = Socket(_sock=act.conn)
    return act
        
def perform_connect(act):
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
            raise ConnectionError(err, errno.errorcode[err])
    else: # err==0 means successful connect
        return act

def wrapped_sendfile(act, offset, length):
    if sendfile:
        offset, sent = sendfile.sendfile(
            act.sock.fileno(), 
            act.file_handle.fileno(), 
            offset, length
        )
    else:
        act.file_handle.seek(offset)
        sent = act.sock._fd.send(act.file_handle.read(length))
    return sent

def perform_sendfile(act):
    if act.length:
        if act.blocksize:
            act.sent += wrapped_sendfile(
                act,
                act.offset + act.sent, 
                min(act.length-act.sent, act.blocksize)
            )
        else:
            act.sent += wrapped_sendfile(act, act.offset+act.sent, act.length-act.sent)
        if act.sent == act.length:
            return act
    else:
        if act.blocksize:
            sent = wrapped_sendfile(act, act.offset+act.sent, act.blocksize)
        else:
            sent = wrapped_sendfile(act, act.offset+act.sent, act.blocksize)
            # we would use self.length but we don't have any,
            #  and we don't know the file's length
        act.sent += sent
        if not sent:
            return act

class ProactorBase(object):
    """
    A proactor just checks if there are ready-sockets for the operations.
    The operations are not done here, they are done in the socket ops instances.
    """
    __doc_all__ = [
        '__init__', 'run_once', 'run_operation', 'run_or_add', 'add', 
        'waiting_op', '__len__', 'handle_errored', 'remove', 'run', 
        'handle_events'
    ]
    supports_multiplex_first = True
    
    def __init__(self, scheduler, resolution, **options):
        self.tokens = {}
        self.scheduler = scheduler
        self.resolution = resolution # seconds
        self.m_resolution = resolution*1000 # miliseconds
        self.n_resolution = resolution*1000000000 #nanoseconds
        self.set_options(**options)
        
    def set_options(self, multiplex_first=True, **bogus_options):
        self.multiplex_first = multiplex_first
        self._warn_bogus_options(**bogus_options)
        
    def _warn_bogus_options(self, **opts):
        if opts:
            import warnings
            for i in opts:
                warnings.warn("Unsupported option %s for %s" % (i, self), stacklevel=2)

    def __len__(self):
        return len(self.tokens)

        
        
    def request_recv(self, act, coro):
        return self.request_generic(act, coro, perform_recv)
            
    def request_send(self, act, coro):
        return self.request_generic(act, coro, perform_send)
            
    def request_sendall(self, act, coro):
        return self.request_generic(act, coro, perform_sendall)
            
    def request_accept(self, act, coro):
        return self.request_generic(act, coro, perform_accept)
    
    def request_connect(self, act, coro):
        result = self.try_run_act(act, perform_connect)
        if result:
            return result, coro
        else:
            self.add_token(act, coro, perform_connect)
    
    def request_sendfile(self, act, coro):
        return self.request_generic(act, coro, perform_sendfile)
    
    def request_generic(self, act, coro, perform):
        result = self.multiplex_first and self.try_run_act(act, perform)
        if result:
            return result, coro
        else:
            self.add_token(act, coro, perform)
    
            
    def add_token(self, act, coro, performer):
        assert act not in self.tokens
        act.coro = coro
        self.tokens[act] = performer
        self.register_fd(act, performer)
        
    def remove_token(self, act):
        if act in self.tokens:
            del self.tokens[act]
            self.unregister_fd(act)
            return True
        else:
            import warnings
            warnings.warn("%s isn't a registered token." % act)
    def try_run_act(self, act, func):
        try:
            return self.run_act(act, func)
        except:
            return CoroutineException(sys.exc_info())
            
    def run_act(self, act, func):
        try:
            return func(act)
        except soerror, exc:
            if exc[0] in (errno.EAGAIN, errno.EWOULDBLOCK, errno.EINPROGRESS): 
                return
            elif exc[0] == errno.EPIPE:
                raise ConnectionClosed(exc)
            else:
                raise
        
    
    def register_fd(self, act, performer):
        pass
        
    def unregister_fd(self, act):
        pass
        
        
    def handle_event(self, act):
        if act in self.tokens:
            coro = act.coro
            op = self.try_run_act(act, self.tokens[act])
            if op:
                del self.tokens[act]
                if self.scheduler.ops_greedy:
                    while True:
                        op, coro = self.scheduler.process_op(coro.run_op(op), coro)
                        if not op and not coro:
                            break  
                else:
                    if op.prio & priority.OP:
                        op, coro = self.scheduler.process_op(coro.run_op(op), coro)
                    if coro:
                        if op.prio & priority.CORO:
                            self.scheduler.active.appendleft( (op, coro) )
                        else:
                            self.scheduler.active.append( (op, coro) )    
            else:
                return
        else:
            import warnings
            warnings.warn("Got event for unkown act: %s" % act)
        return True
    
    def yield_event(self, act):
        if act in self.tokens:
            coro = act.coro
            op = self.try_run_act(act, self.tokens[act])
            if op:
                del self.tokens[act]
                return op, coro
        
    def handle_error_event(self, act, detail, exc=ConnectionError):
        del self.tokens[act]
        self.unregister_fd(act)
        self.scheduler.active.append((
            CoroutineException( (exc, exc(detail)) ), 
            act.coro
        ))
    