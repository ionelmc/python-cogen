from __future__ import division
import win32file
import win32event
import win32api
import pywintypes
import socket
import ctypes
import struct    
import sys
from time import sleep

from base import ProactorBase
from cogen.core.util import priority, debug
from cogen.core.sockets import Socket
from cogen.core.events import ConnectionClosed, ConnectionError, CoroutineException

def perform_recv(act, overlapped):
    act.buff = win32file.AllocateReadBuffer(act.len)
    return win32file.WSARecv(act.sock._fd, act.buff, overlapped, 0)

def complete_recv(act, rc, nbytes):
    if nbytes:
        act.buff = act.buff[:nbytes]
        return act
    else:
        raise ConnectionClosed("Empty recv.")
    
    
def perform_send(act, overlapped):
    return win32file.WSASend(act.sock._fd, act.buff, overlapped, 0)

def complete_send(act, rc, nbytes):
    act.sent = nbytes
    return act.sent and act
    
    
def perform_sendall(act, overlapped):
    return win32file.WSASend(act.sock._fd, act.buff[act.sent:], overlapped, 0)

def complete_sendall(act, rc, nbytes):
    act.sent += nbytes
    return act.sent == len(act.buff) and act
    
    
def perform_accept(act, overlapped):
    act.conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    act.cbuff = win32file.AllocateReadBuffer(64)
    return win32file.AcceptEx(
        act.sock._fd.fileno(), act.conn.fileno(), act.cbuff, overlapped
    ), 0
        
def complete_accept(act, rc, nbytes):
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
    

def perform_connect(act, overlapped):
    # ConnectEx requires that the socket be bound beforehand
    try:
        # just in case we get a already-bound socket
        act.sock.bind(('0.0.0.0', 0))
    except socket.error, exc:
        if exc[0] not in (errno.EINVAL, errno.WSAEINVAL):
            raise
    return win32file.ConnectEx(act.sock, act.addr, overlapped)

def complete_connect(act, rc, nbytes):
    act.sock.setsockopt(socket.SOL_SOCKET, win32file.SO_UPDATE_CONNECT_CONTEXT, "")
    return act

def perform_sendfile(act, overlapped):
    return win32file.TransmitFile(
        act.sock, 
        win32file._get_osfhandle(act.file_handle.fileno()), 
        act.length or 0, 
        act.blocksize, overlapped, 0
    ), 0

def complete_sendfile(act, rc, nbytes):
    act.sent = nbytes
    return act

class IOCPProactor(ProactorBase):
    supports_multiplex_first = False
    
    def __init__(self, scheduler, res, **options):
        super(self.__class__, self).__init__(scheduler, res, **options)
        self.scheduler = scheduler
        self.iocp = win32file.CreateIoCompletionPort(
            win32file.INVALID_HANDLE_VALUE, None, 0, 0
        ) 
        
    def set_options(self, **bogus_options):
        self._warn_bogus_options(**bogus_options) #iocp doesn't have any options

    def request_recv(self, act, coro):
        return self.request_generic(act, coro, perform_recv, complete_recv)
            
    def request_send(self, act, coro):
        return self.request_generic(act, coro, perform_send, complete_send)
            
    def request_sendall(self, act, coro):
        return self.request_generic(act, coro, perform_sendall, complete_sendall)
            
    def request_accept(self, act, coro):
        return self.request_generic(act, coro, perform_accept, complete_accept)
            
    def request_connect(self, act, coro):
        return self.request_generic(act, coro, perform_connect, complete_connect)
        
    def request_sendfile(self, act, coro):
        return self.request_generic(act, coro, perform_sendfile, complete_sendfile)
    
    def request_generic(self, act, coro, perform, complete):
        """
        Performs an overlapped request (via `perform` callable) and saves
        the token and the (`overlapped`, `perform`, `complete`) trio.
        """
        overlapped = pywintypes.OVERLAPPED() 
        overlapped.object = act
        self.add_token(act, coro, (overlapped, perform, complete))
        
        rc, nbytes = perform(act, overlapped)
        
        if rc == 0:
            # ah geez, it didn't got in the iocp, we have a result!"
            win32file.PostQueuedCompletionStatus(
                self.iocp, nbytes, 0, overlapped
            )
        

    def register_fd(self, act, performer):
        if not act.sock._proactor_added:
            win32file.CreateIoCompletionPort(act.sock._fd.fileno(), self.iocp, 0, 0)     
            act.sock._proactor_added = True
    
    def unregister_fd(self, act):
        win32file.CancelIo(act.sock._fd.fileno()) 
    
    
    def try_run_act(self, act, func, rc, nbytes):
        try:
            return func(act, rc, nbytes)
        except:
            return CoroutineException(sys.exc_info())
        
    def process_op(self, rc, nbytes, overlap):
        """
        Handles the possible completion or re-queueing if conditions haven't 
        been met (the `complete` callable returns false) of a overlapped request.
        """
        act = overlap.object
        overlap.object = None
        if act in self.tokens:
            ol, perform, complete = self.tokens[act]
            assert ol is overlap
            if rc == 0:
                ract = self.try_run_act(act, complete, rc, nbytes)
                if ract:
                    del self.tokens[act] 
                    win32file.CancelIo(act.sock._fd.fileno()) 
                    return ract, act.coro
                else:
                    # operation hasn't completed yet (not enough data etc)
                    # read it in the iocp
                    self.request_generic(act, act.coro, perform, complete)
                    
                    
            else:
                #looks like we have a problem, forward it to the coroutine.
                
                # this needs some research: ERROR_NETNAME_DELETED, need to reopen 
                #the accept sock ?! something like:
                #    warnings.warn("ERROR_NETNAME_DELETED: %r. Re-registering operation." % op)
                #    self.registered_ops[op] = self.run_iocp(op, coro)
                del self.tokens[act]
                win32file.CancelIo(act.sock._fd.fileno())
                return CoroutineException((
                    ConnectionError, ConnectionError(
                        (rc, "%s on %r" % (ctypes.FormatError(rc), act))
                    )
                )), act.coro
        else:
            import warnings
            warnings.warn("Unknown token %s" % act)
            
    def run(self, timeout = 0):
        """
        Calls GetQueuedCompletionStatus and handles completion via 
        IOCPProactor.process_op.
        """
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
                    rc, nbytes, key, overlap = win32file.GetQueuedCompletionStatus(
                        self.iocp,
                        0 if urgent else ptimeout
                    )
                except RuntimeError:
                    # we will get "This overlapped object has lost all its 
                    # references so was destroyed" when we remove a operation, 
                    # it is garbage collected and the overlapped completes
                    # afterwards
                    break 
                    
                # well, this is a bit weird, if we get a aborted rc (via CancelIo
                #i suppose) evaluating the overlap crashes the interpeter 
                #with a memory read error
                if rc != win32file.WSA_OPERATION_ABORTED and overlap:
                    
                    if urgent:
                        op, coro = urgent
                        urgent = None
                        if op.prio & priority.OP:
                            # imediately run the asociated coroutine step
                            op, coro = self.scheduler.process_op(
                                coro.run_op(op), 
                                coro
                            )
                        if coro:
                            #TODO, what "op and "
                            if op and (op.prio & priority.CORO):
                                self.scheduler.active.appendleft( (op, coro) )
                            else:
                                self.scheduler.active.append( (op, coro) )                     
                    if overlap.object:
                        urgent = self.process_op(rc, nbytes, overlap)
                else:
                    break
            return urgent
        else:
            sleep(min(self.resolution, timeout))
