from __future__ import division
import win32file
import win32event
import win32api
import pywintypes
import socket
import ctypes
import struct    

from base import ProactorBase
from cogen.core.util import priority
from cogen.core import events
from cogen.core.sockets import Socket

class IOCPProactor(ProactorBase):
    def __init__(self, scheduler, res):
        super(self.__class__, self).__init__(scheduler, res)
        self.scheduler = scheduler
        self.iocp = win32file.CreateIoCompletionPort(
            win32file.INVALID_HANDLE_VALUE, None, 0, 0
        ) 


    def perform_recv(self, act, overlapped):
        act.buff = win32file.AllocateReadBuffer(act.len)
        return win32file.WSARecv(act.sock._fd, act.buff, overlapped, 0)
    
    def complete_recv(self, act, rc, nbytes):
        if act.buff:
            act.buff = str(act.buff)
            return act
        else:
            raise ConnectionClosed("Empty recv.")
        
        
    def perform_send(self, act, overlapped):
        return win32file.WSASend(act.sock._fd, act.buff, overlapped, 0)
    
    def complete_send(self, act, rc, nbytes):
        act.sent = nbytes
        return act.sent and act
        
        
    def perform_sendall(self, act, overlapped):
        return win32file.WSASend(act.sock._fd, act.buff[act.sent:], overlapped, 0)
    
    def complete_sendall(self, act, rc, nbytes):
        act.sent += nbytes
        return act.sent == len(act.buff) and act
        
        
    def perform_accept(self, act, overlapped):
        act.conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        act.cbuff = win32file.AllocateReadBuffer(64)
        return win32file.WSA_IO_PENDING, win32file.AcceptEx(
            act.sock._fd.fileno(), act.conn.fileno(), act.cbuff, overlapped
        )
            
    def complete_accept(self, act, rc, nbytes):
        act.conn.setblocking(0)
        act.conn.setsockopt(
            socket.SOL_SOCKET, 
            win32file.SO_UPDATE_ACCEPT_CONTEXT, 
            struct.pack("I", act.sock.fileno())
        )
        family, localaddr, act.addr = win32file.GetAcceptExSockaddrs(
            act.conn, act.cbuff
        )
        act.conn = Socket(_sock=act.conn)
        return act
        
    
    def perform_connect(self, act, overlapped):
        # ConnectEx requires that the socket be bound beforehand
        try:
            # just in case we get a already-bound socket
            act.sock.bind(('0.0.0.0', 0))
        except socket.error, exc:
            if exc[0] not in (errno.EINVAL, errno.WSAEINVAL):
                raise
        return win32file.ConnectEx(act.sock, act.addr, overlapped)
    
    def complete_connect(self, act, rc, nbytes):
        act.sock.setsockopt(socket.SOL_SOCKET, win32file.SO_UPDATE_CONNECT_CONTEXT, "")
        return act



    def request_recv(self, act, coro):
        return self.request_generic(act, coro, self.perform_recv, self.complete_recv, )
            
    def request_send(self, act, coro):
        return self.request_generic(act, coro, self.perform_send, self.complete_send)
            
    def request_sendall(self, act, coro):
        return self.request_generic(act, coro, self.perform_sendall, self.complete_sendall)
            
    def request_accept(self, act, coro):
        return self.request_generic(act, coro, self.perform_accept, self.complete_accept)
            
    def request_connect(self, act, coro):
        return self.request_generic(act, coro, self.perform_connect, self.complete_connect)
        
    def request_generic(self, act, coro, perform, complete):
        overlapped = pywintypes.OVERLAPPED() 
        overlapped.object = act
        rc, nbytes = perform(act, overlapped)
        
        if rc == 0:
            # ah geez, it didn't got in the iocp, we have a result!
            win32file.PostQueuedCompletionStatus(
                self.iocp, nbytes, 0, overlapped
            )
        else:
            self.add_token(act, coro, (overlapped, perform, complete))

    def register_fd(self, act, performer):
        win32file.CreateIoCompletionPort(act.sock._fd.fileno(), self.iocp, 0, 0)     
    
    def unregister_fd(self, act):
        win32file.CancelIo(act.sock._fd.fileno()) 
    
    def run_act(self, act, (perform, complete), rc, nbytes):
        try:
            return complete(act, rc, nbytes)
        except soerror, exc:
            if exc[0] in (errno.EAGAIN, errno.EWOULDBLOCK, errno.EINPROGRESS): 
                return
            elif exc[0] == errno.EPIPE:
                raise ConnectionClosed(exc)
            else:
                raise
    
    def handle_completion(self, overlapped, rc, nbytes):
        act = overlapped.object
        overlapped.object = None
        if rc == 0:
            ol, perform, complete = self.tokens[act]
            assert ol is overlapped
            
            if self.handle_event(act, rc, nbytes):
                win32file.CancelIo(act.sock._fd.fileno()) 
            else:
                # operation hasn't completed yet (not enough data etc)
                self.request_generic(act, act.coro, *self.tokens[act])
        else:
            #looks like we have a problem, forward it to the coroutine.
            
            # this needs some research: ERROR_NETNAME_DELETED, need to reopen 
            #the accept sock ?! something like:
            #    warnings.warn("ERROR_NETNAME_DELETED: %r. Re-registering operation." % op)
            #    self.registered_ops[op] = self.run_iocp(op, coro)
            win32file.CancelIo(act.sock._fd.fileno())
            self.handle_error_event(act, (rc, "%s on %r" % (ctypes.FormatError(rc), act)))
            


    def run(self, timeout = 0):
        # same resolution as epoll
        ptimeout = int(
            timeout.days * 86400000 + 
            timeout.microseconds / 1000 +
            timeout.seconds * 1000 
            if timeout else (self.m_resolution if timeout is None else 0)
        )
        if self.tokens:
            urgent = None
            # we use urgent as a optimisation: the last operation is returned 
            #directly to the scheduler (the sched might just run it till it 
            #goes to sleep) and not added in the sched.active queue
            while 1:
                try:
                    rc, nbytes, key, overlapped = win32file.GetQueuedCompletionStatus(
                        self.iocp,
                        0 if urgent else ptimeout
                    )
                except RuntimeError, e:
                    # we will get "This overlapped object has lost all its 
                    # references so was destroyed" when we remove a operation, 
                    # it is garbage collected and the overlapped completes
                    # afterwards
                    import warnings 
                    warnings.warn("Error on GetQueuedCompletionStatus: %s"%e)
                    break 
                    
                # well, this is a bit weird, if we get a aborted rc (via CancelIo
                #i suppose) evaluating the overlap crashes the interpeter 
                #with a memory read error
                if rc != win32file.WSA_OPERATION_ABORTED and overlapped:
                    
                    if urgent:
                        self.handle_completion(*urgent)
                        urgent = None
                        
                    if overlapped.object:
                        urgent = overlapped, rc, nbytes
                        
                else:
                    break
            if urgent:
                return self.yield_event(*urgent)
        else:
            time.sleep(self.resolution)    
