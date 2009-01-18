from __future__ import division
# work in progress

from api_wrappers import _get_osfhandle, CreateIoCompletionPort, CloseHandle,   \
                GetQueuedCompletionStatus, PostQueuedCompletionStatus, CancelIo,\
                getaddrinfo, getsockopt, WSARecv, WSASend, AcceptEx, WSAIoctl,  \
                GetAcceptExSockaddrs, ConnectEx, TransmitFile, AllocateBuffer, \
                LPOVERLAPPED, OVERLAPPED, LPDWORD, PULONG_PTR, cast, c_void_p, \
                byref, c_char_p, create_string_buffer, c_ulong, DWORD, WSABUF, \
                c_long, addrinfo_p, getaddrinfo, addrinfo, WSAPROTOCOL_INFO, \
                c_int, sizeof, string_at, get_osfhandle, sockaddr_in
                
from api_consts import SO_UPDATE_ACCEPT_CONTEXT, SO_UPDATE_CONNECT_CONTEXT, \
                INVALID_HANDLE_VALUE, WSA_OPERATION_ABORTED, WSA_IO_PENDING, \
                SOL_SOCKET, SO_PROTOCOL_INFOA


import sys
import socket
import ctypes
import struct
import errno

from time import sleep

from cogen.core.proactors.base import ProactorBase
from cogen.core.util import priority
from cogen.core.sockets import Socket, SocketError, ConnectionClosed
from cogen.core.coroutines import CoroutineException
def perform_recv(act, overlapped):
    wsabuf = WSABUF()
    buf = create_string_buffer(act.len)
    wsabuf.buf = cast(buf, c_char_p)
    wsabuf.len = act.len
    nbytes = c_ulong(0)
    flags = c_ulong(0)
    act.flags = buf
    
    rc = WSARecv(
        act.sock._fd.fileno(), # SOCKET s
        byref(wsabuf), # LPWSABUF lpBuffers
        1, # DWORD dwBufferCount
        byref(nbytes), # LPDWORD lpNumberOfBytesRecvd
        byref(flags), # LPDWORD lpFlags
        overlapped, # LPWSAOVERLAPPED lpOverlapped
        None # LPWSAOVERLAPPED_COMPLETION_ROUTINE lpCompletionRoutine
    )
    return rc, nbytes.value

def complete_recv(act, rc, nbytes):
    if nbytes:
        act.buff = act.flags[:nbytes]
        return act
    else:
        raise ConnectionClosed("Empty recv.")
    
    
def perform_send(act, overlapped):
    wsabuf = WSABUF()
    wsabuf.buf = c_char_p(act.buff)
    wsabuf.len = len(act.buff)
    nbytes = c_ulong()
    act.flags = wsabuf, nbytes
        
    return WSASend(
        act.sock._fd.fileno(), # SOCKET s
        byref(wsabuf), # LPWSABUF lpBuffers
        1, # DWORD dwBufferCount
        byref(nbytes), # LPDWORD lpNumberOfBytesSent
        0, # DWORD dwFlags
        overlapped, # LPWSAOVERLAPPED lpOverlapped
        None # LPWSAOVERLAPPED_COMPLETION_ROUTINE lpCompletionRoutine
    ), nbytes.value

def complete_send(act, rc, nbytes):
    act.flags = None
    act.sent = nbytes
    return act.sent and act
    
    
def perform_sendall(act, overlapped):
    wsabuf = WSABUF()
    wsabuf.buf = c_char_p(act.buff[act.sent:])
    wsabuf.len = len(act.buff)-act.sent
    nbytes = c_ulong()
    act.flags = wsabuf, nbytes
    
    return WSASend(
        act.sock._fd.fileno(), # SOCKET s
        byref(wsabuf), # LPWSABUF lpBuffers
        1, # DWORD dwBufferCount
        byref(nbytes), # LPDWORD lpNumberOfBytesSent
        0, # DWORD dwFlags
        overlapped, # LPWSAOVERLAPPED lpOverlapped
        None # LPWSAOVERLAPPED_COMPLETION_ROUTINE lpCompletionRoutine
    ), nbytes

def complete_sendall(act, rc, nbytes):
    act.sent += nbytes
    return act.sent == len(act.buff) and act
    
    
def perform_accept(act, overlapped):
    act.conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    act.cbuff = create_string_buffer((sizeof(sockaddr_in) + 16) * 2)
    nbytes = c_ulong()
    
    prot_info = WSAPROTOCOL_INFO()
    prot_info_len = c_int(sizeof(prot_info))
    getsockopt(act.sock.fileno(), SOL_SOCKET, SO_PROTOCOL_INFOA, cast(byref(prot_info), c_char_p), byref(prot_info_len))
    
    # BOOL  
    return AcceptEx(
        act.sock._fd.fileno(), # SOCKET sListenSocket
        act.conn.fileno(), # SOCKET sAcceptSocket
        cast(act.cbuff, c_void_p), # PVOID lpOutputBuffer
        0, # DWORD dwReceiveDataLength
        prot_info.iMaxSockAddr + 16, # DWORD dwLocalAddressLength
        prot_info.iMaxSockAddr + 16, # DWORD dwRemoteAddressLength
        nbytes, # LPDWORD lpdwBytesReceived
        overlapped # LPOVERLAPPED lpOverlapped
    ), 0
        
def complete_accept(act, rc, nbytes):
    act.conn.setblocking(0)
    act.conn.setsockopt(
        socket.SOL_SOCKET, 
        SO_UPDATE_ACCEPT_CONTEXT, 
        struct.pack("I", act.sock.fileno())
    )
    act.addr = act.conn.getpeername()
    
    # void = PVOID lpOutputBuffer, DWORD dwReceiveDataLength, DWORD dwLocalAddressLength, DWORD dwRemoteAddressLength, LPSOCKADDR *LocalSockaddr, LPINT LocalSockaddrLength, LPSOCKADDR *RemoteSockaddr, LPINT RemoteSockaddrLength
    # TODO ?
    #~ family, localaddr, act.addr = GetAcceptExSockaddrs(
        #~ act.conn, act.cbuff
    #~ )
    act.conn = act.sock.__class__(_sock=act.conn)
    return act
    
def perform_connect(act, overlapped):
    # ConnectEx requires that the socket be bound beforehand
    try:
        # just in case we get a already-bound socket
        act.sock.bind(('0.0.0.0', 0))
    except socket.error, exc:
        if exc[0] not in (errno.EINVAL, errno.WSAEINVAL):
            raise
    fileno = act.sock._fd.fileno()
    
    prot_info = WSAPROTOCOL_INFO()
    prot_info_len = c_int(sizeof(prot_info))
    getsockopt(fileno, SOL_SOCKET, SO_PROTOCOL_INFOA, cast(byref(prot_info), c_char_p), byref(prot_info_len))
    
    hints = addrinfo()
    hints.ai_family = prot_info.iAddressFamily
    hints.ai_socktype = prot_info.iSocketType
    hints.ai_protocol = prot_info.iProtocol
    
    result = addrinfo_p()
    getaddrinfo(act.addr[0], str(act.addr[1]), byref(hints), byref(result));
    
    act.flags = result
    
    #~ act.sock.bind(('0.0.0.0', 0))
    return ConnectEx(
        fileno, # SOCKET s
        result.contents.ai_addr, result.contents.ai_addrlen,
        None,
        0,
        None,
        overlapped
    ), 0

def complete_connect(act, rc, nbytes):
    act.sock.setsockopt(socket.SOL_SOCKET, SO_UPDATE_CONNECT_CONTEXT, "")
    return act

def perform_sendfile(act, overlapped):
    # BOOL 
    return TransmitFile(
        act.sock._fd.fileno(), # SOCKET hSocket
        get_osfhandle(act.file_handle.fileno()), # HANDLE hFile
        act.length or 0, # DWORD nNumberOfBytesToWrite
        act.blocksize, # DWORD nNumberOfBytesPerSend
        overlapped, # LPOVERLAPPED lpOverlapped
        None, # LPTRANSMIT_FILE_BUFFERS lpTransmitBuffers
        0 # DWORD dwFlags
    ), 0

def complete_sendfile(act, rc, nbytes):
    act.sent = nbytes
    return act

class CTYPES_IOCPProactor(ProactorBase):
    supports_multiplex_first = False
    
    def __init__(self, scheduler, res, **options):
        super(self.__class__, self).__init__(scheduler, res, **options)
        self.scheduler = scheduler
        self.iocp = CreateIoCompletionPort(
            INVALID_HANDLE_VALUE, 0, None, 0
        ) 
        
    def __del__(self):
        self.close()
    
    def close(self):
        if self.iocp:
            poverlapped = LPOVERLAPPED()
            nbytes = DWORD()
            completion_key = c_ulong()
            while 1:
                rc = GetQueuedCompletionStatus(
                    self.iocp, # HANDLE CompletionPort
                    byref(nbytes), # LPDWORD lpNumberOfBytes
                    byref(completion_key), # PULONG_PTR lpCompletionKey
                    byref(poverlapped),
                    0
                )
                if not poverlapped:
                    break
                else:
                    act = poverlapped.contents.object
                    if act in self.tokens:
                        del self.tokens[act]
                        CancelIo(act.sock._fd.fileno()) 
                    else:
                        import warnings
                        warnings.warn("act(%s) not in self.tokens" % act)
            CloseHandle(self.iocp)
            self.iocp = None
            if self.tokens:
                import warnings
                warnings.warn("self.tokens still pending: %s" % self.tokens)
        super(self.__class__, self).close()
        
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
        overlapped = OVERLAPPED() 
        overlapped.object = act
        self.add_token(act, coro, (overlapped, perform, complete))
        
        rc, nbytes = perform(act, overlapped)
        completion_key = c_long(0)
        if rc == 0:
            # ah geez, it didn't got in the iocp, we have a result!
            pass
            
            
            # ok this is weird, apparently this doesn't need to be requeued
            #  - need to investigate why (TODO)
            #~ PostQueuedCompletionStatus(
                #~ self.iocp, # HANDLE CompletionPort
                #~ nbytes, # DWORD dwNumberOfBytesTransferred
                #~ byref(completion_key), # ULONG_PTR dwCompletionKey
                #~ overlapped # LPOVERLAPPED lpOverlapped
            #~ )
        elif rc != WSA_IO_PENDING:
            self.remove_token(act)
            raise SocketError(rc, "%s on %r" % (ctypes.FormatError(rc), act))
        

    def register_fd(self, act, performer):
        if not act.sock._proactor_added:
            CreateIoCompletionPort(act.sock._fd.fileno(), self.iocp, None, 0)     
            act.sock._proactor_added = True
    
    def unregister_fd(self, act):
        overlapped, perform, complete = self.tokens[act]
        overlapped.object = None
        CancelIo(act.sock._fd.fileno()) 
    
    
    def try_run_act(self, act, func, rc, nbytes):
        try:
            return func(act, rc, nbytes)
        except:
            return CoroutineException(*sys.exc_info())
        
    def process_op(self, rc, nbytes, overlap):
        """
        Handles the possible completion or re-queueing if conditions haven't 
        been met (the `complete` callable returns false) of a overlapped request.
        """
        act = overlap.object
        overlap.object = None
        if act in self.tokens:
            ol, perform, complete = self.tokens[act]
            #~ assert ol is overlap, "%r is not %r" % (ol, overlap)
            if rc == 0:
                ract = self.try_run_act(act, complete, rc, nbytes)
                if ract:
                    del self.tokens[act] 
                    CancelIo(act.sock._fd.fileno()) 
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
                CancelIo(act.sock._fd.fileno())
                #~ import traceback
                #~ traceback.print_stack()
                return CoroutineException(
                    SocketError, SocketError(
                        (rc, "%s on %r" % (ctypes.FormatError(rc), act))
                    )
                ), act.coro
        else:
            import warnings
            warnings.warn("Unknown token %s" % act)
            
    def run(self, timeout = 0):
        """
        Calls GetQueuedCompletionStatus and handles completion via 
        process_op.
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
                    poverlapped = LPOVERLAPPED()
                    nbytes = DWORD()
                    completion_key = c_ulong()
                    #~ BOOL WINAPI GetQueuedCompletionStatus(
                      #~ __in   HANDLE CompletionPort,
                      #~ __out  LPDWORD lpNumberOfBytes,
                      #~ __out  PULONG_PTR lpCompletionKey,
                      #~ __out  LPOVERLAPPED *lpOverlapped,
                      #~ __in   DWORD dwMilliseconds
                    #~ );

                    rc = GetQueuedCompletionStatus(
                        self.iocp, # HANDLE CompletionPort
                        byref(nbytes), # LPDWORD lpNumberOfBytes
                        byref(completion_key), # PULONG_PTR lpCompletionKey
                        byref(poverlapped),
                        0 if urgent else ptimeout
                    )
                    overlap = poverlapped and poverlapped.contents
                    nbytes = nbytes.value
                except RuntimeError, e:
                    import warnings
                    warnings.warn("RuntimeError(%s) on GetQueuedCompletionStatus." % e)
                    # we will get "This overlapped object has lost all its 
                    # references so was destroyed" when we remove a operation, 
                    # it is garbage collected and the overlapped completes
                    # afterwards
                    break 
                    
                # well, this is a bit weird, if we get a aborted rc (via CancelIo
                #i suppose) evaluating the overlap crashes the interpeter 
                #with a memory read error
                # also, we might get a "wait operation timed out", and no overlap pointer
                if rc != WSA_OPERATION_ABORTED and overlap:
                    
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
                        assert overlap.object in self.tokens
                        urgent = self.process_op(rc, nbytes, overlap)
                else:
                    #~ import warnings
                    #~ warnings.warn("rc=(%s: %s) overlap=(%s)" % (rc, ctypes.FormatError(rc), overlap))
                    break
            return urgent
        else:
            sleep(timeout)
