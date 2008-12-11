"""
Socket-only coroutine operations and `Socket` wrapper.
Really - the only thing you need to know for most stuff is 
the `Socket <cogen.core.sockets.Socket.html>`_ class.
"""
__all__ = [
    'getdefaulttimeout', 'setdefaulttimeout', 'Socket', 'SendFile', 'Read',
    'ReadAll', 'ReadLine', 'Write', 'WriteAll','Accept','Connect', 
    'SocketOperation'
]

import socket
import errno
import exceptions
import datetime
import struct

try:
    import ctypes
    import win32file
    import win32event
    import pywintypes
except:
    pass

import events
from util import debug, priority, fmt_list
import reactors

getnow = datetime.datetime.now

try:
    import sendfile
except ImportError:
    sendfile = None
    
_TIMEOUT = None

def getdefaulttimeout():
    return _TIMEOUT

def setdefaulttimeout(timeout):
    """Set the default timeout used by the socket wrapper 
    (`Socket <cogen.core.sockets.Socket.html>`_ class)"""
    _TIMEOUT = timeout


class Socket(object):
    """
    A wrapper for socket objects, sets nonblocking mode and
    adds some internal bufers and wrappers. Regular calls to the usual 
    socket methods return operations for use in a coroutine.
    
    So you use this in a coroutine like:
    
    .. sourcecode:: python
    
        sock = Socket(family, type, proto) # just like the builtin socket module
        yield sock.read(1024)
    
    
    Constructor details:
    
    .. sourcecode:: python
    
        Socket([family[, type[, proto]]]) -> socket object
    
    Open a socket of the given type.  The family argument specifies the
    address family; it defaults to AF_INET.  The type argument specifies
    whether this is a stream (SOCK_STREAM, this is the default)
    or datagram (SOCK_DGRAM) socket.  The protocol argument defaults to 0,
    specifying the default protocol.  Keyword arguments are accepted.

    A socket object represents one endpoint of a network connection.
    """
    __slots__ = ['_fd', '_rl_list', '_rl_list_sz', '_rl_pending', '_timeout', '_reactor_added']
    def __init__(self, *a, **k):
        self._fd = socket.socket(*a, **k)
        self._rl_list = [] # for linebreaks checked buffers
        self._rl_list_sz = 0 # a cached size of the summed sizes of rl_list buffers
        self._rl_pending = '' # for linebreaks unchecked buffer
        self._fd.setblocking(0)
        self._timeout = _TIMEOUT
        self._reactor_added = False
        
    def read(self, bufsize, **kws):
        """Receive data from the socket. The return value is a string 
        representing the data received. The amount of data may be less than the
        ammount specified by _bufsize_. """
        return Read(self, bufsize, timeout=self._timeout, **kws)
        
    def readall(self, bufsize, **kws):
        """Receive data from the socket. The return value is a string 
        representing the data received. The amount of data will be the exact
        ammount specified by _bufsize_. """
        return ReadAll(self, bufsize, timeout=self._timeout, **kws)
        
    def readline(self, size, **kws):
        """Receive one line of data from the socket. The return value is a string 
        representing the data received. The amount of data will at most
        ammount specified by _size_. If no line separator has been found and the 
        ammount received has reached _size_ an OverflowException will be raised.
        """
        return ReadLine(self, size, timeout=self._timeout, **kws)
        
    def write(self, data, **kws):
        """Send data to the socket. The socket must be connected to a remote 
        socket. Ammount sent may be less than the data provided."""
        return Write(self, data, timeout=self._timeout, **kws)
        
    def writeall(self, data, **kws):
        """Send data to the socket. The socket must be connected to a remote 
        socket. All the data is guaranteed to be sent."""
        return WriteAll(self, data, timeout=self._timeout, **kws)
        
    def accept(self, **kws):
        """Accept a connection. The socket must be bound to an address and 
        listening for connections. The return value is a pair (conn, address) 
        where conn is a new socket object usable to send and receive data on the 
        connection, and address is the address bound to the socket on the other 
        end of the connection. 
        
        Example:
        {{{
        conn, address = yield mysock.accept()
        }}}
        """
        return Accept(self, **kws)
        
    def close(self, *args):
        """Close the socket. All future operations on the socket object will 
        fail. The remote end will receive no more data (after queued data is 
        flushed). Sockets are automatically closed when they are garbage-collected. 
        """
        self._fd.close()
        
    def bind(self, *args):
        """Bind the socket to _address_. The socket must not already be bound. 
        (The format of _address_ depends on the address family) 
        """
        return self._fd.bind(*args)
        
    def connect(self, address, **kws):
        """Connect to a remote socket at _address_. """
        return Connect(self, address, **kws)
        
    def fileno(self):
        """Return the socket's file descriptor """
        return self._fd.fileno()
        
    def listen(self, backlog):
        """Listen for connections made to the socket. The _backlog_ argument 
        specifies the maximum number of queued connections and should be at 
        least 1; the maximum value is system-dependent (usually 5). 
        """
        return self._fd.listen(backlog)
        
    def getpeername(self):
        """Return the remote address to which the socket is connected."""
        return self._fd.getpeername()
        
    def getsockname(self, *args):
        """Return the socket's own address. """
        return self._fd.getsockname()
        
    def settimeout(self, to):
        """Set a timeout on blocking socket operations. The value argument can 
        be a nonnegative float expressing seconds, timedelta or None. 
        """
        self._timeout = to
        
    def gettimeout(self, *args):
        """Return the associated timeout value. """
        return self._timeout
        
    def shutdown(self, *args):
        """Shut down one or both halves of the connection. Same as the usual 
        socket method."""
        return self._fd.shutdown(*args)
        
    def setblocking(self, val):
        if val: 
            raise RuntimeError("You can't.")
    def setsockopt(self, *args):
        """Set the value of the given socket option. Same as the usual socket 
        method."""
        self._fd.setsockopt(*args)
        
    def __repr__(self):
        return '<socket at 0x%X>' % id(self)
    def __str__(self):
        return 'sock@0x%X' % id(self)
class SocketOperation(events.TimedOperation):
    """
    This is a generic class for a operation that involves some socket call.
        
    A socket operation should subclass WriteOperation or ReadOperation, define a
    `run` method and call the __init__ method of the superclass.
    """
    __slots__ = [
        'sock', 'last_update', 'fileno',
        'len', 'buff', 'addr', 'run_first',
        
    ]
    trim = 2000
    def __init__(self, sock, run_first=True, **kws):
        """
        All the socket operations have these generic properties that the 
        poller and scheduler interprets:
        
          * timeout - the ammout of time in seconds or timedelta, or the datetime 
            value till the poller should wait for this operation.
          * weak_timeout - if this is True the timeout handling code will take 
            into account the time of last activity (that would be the time of last
            `try_run` call)
          * prio - a flag for the scheduler
        """
        assert isinstance(sock, Socket)
        
        super(SocketOperation, self).__init__(**kws)
        self.sock = sock
        self.run_first = run_first
        
    def try_run(self, reactor):
        """
        This method will return a None value or raise a exception if the 
        operation can't complete at this time.
        
        The socket poller will run this method if the socket is 
        readable/writeable.
        
        If this returns a value that evaluates to False, the poller will try to
        run this at a later time (when the socket is readable/writeable again).
        """
        try:
            result = self.run(reactor)
            if self.timeout and self.timeout != -1 and self.weak_timeout:
                self.last_update = getnow()
            if result:
                self.state = events.FINALIZED
            return result
        except socket.error, exc:
            if exc[0] in (errno.EAGAIN, errno.EWOULDBLOCK, errno.EINPROGRESS): 
                return None
            elif exc[0] == errno.EPIPE:
                raise events.ConnectionClosed(exc)
            else:
                raise
        return self

    def process(self, sched, coro):
        """Add the operation in the reactor if necessary."""
        super(SocketOperation, self).process(sched, coro)
        if self.run_first or self.pending():
            r = sched.poll.run_or_add(self, coro)
            if r:
                #~ print '>we have result!'
                if self.prio:
                    return r, r and coro
                else:
                    sched.active.appendleft((r, coro))
        else:
            sched.poll.add(self, coro)
            
    def pending(self):
        return True if (self.sock._rl_pending or self.sock._rl_list) else False
    def cleanup(self, sched, coro):
        return sched.poll.remove(self, coro)
    def run(self, reactor):
        raise NotImplementedError()
    
class ReadOperation(SocketOperation): 
    __slots__ = ['iocp_buff', 'temp_buff']
    def __init__(self, sock, **kws):
        super(ReadOperation, self).__init__(sock, **kws)
        self.temp_buff = 0
        
    def iocp(self, overlap):
        self.iocp_buff = win32file.AllocateReadBuffer(
            self.len-self.sock._rl_list_sz
        )
        return win32file.WSARecv(self.sock._fd, self.iocp_buff, overlap, 0)
            
    def iocp_done(self, rc, nbytes):
        self.temp_buff = self.iocp_buff[:nbytes]
    
class WriteOperation(SocketOperation): 
    __slots__ = ['sent']
    def iocp(self, overlap):
        return win32file.WSASend(self.sock._fd, self.buff, overlap, 0)
            
    def iocp_done(self, rc, nbytes):
        self.sent += nbytes
    
class SendFile(WriteOperation):
    """
        Uses underling OS sendfile call or a regular memory copy operation if 
        there is no sendfile.
        You can use this as a WriteAll if you specify the length.
        Usage:
            
        .. sourcecode:: python
            yield sockets.SendFile(file_object, socket_object, 0) 
                # will send till send operations return 0
                
            yield sockets.SendFile(file_object, socket_object, 0, blocksize=0)
                # there will be only one send operation (if successfull)
                # that meas the whole file will be read in memory if there is 
                #no sendfile
                
            yield sockets.SendFile(file_object, socket_object, 0, file_size)
                # this will hang if we can't read file_size bytes
                #from the file

    """
    __slots__ = [
        'sent', 'file_handle', 'offset', 
        'position', 'length', 'blocksize'
    ]
    def __init__(self, file_handle, sock, offset=None, length=None, blocksize=4096, **kws):
        super(SendFile, self).__init__(sock, **kws)
        self.file_handle = file_handle
        self.offset = self.position = offset or file_handle.tell()
        self.length = length
        self.sent = 0
        self.blocksize = blocksize
    def send(self, offset, length):
        if sendfile:
            offset, sent = sendfile.sendfile(
                self.sock.fileno(), 
                self.file_handle.fileno(), 
                offset, 
                length
            )
        else:
            self.file_handle.seek(offset)
            sent = self.sock._fd.send(self.file_handle.read(length))
        return sent
        
    def iocp_send(self, offset, length, overlap):
        self.file_handle.seek(offset)
        return win32file.WSASend(self.sock._fd, self.file_handle.read(length), overlap, 0)
        
    def iocp(self, overlap):
        if self.length:
            if self.blocksize:
                return self.iocp_send(
                    self.offset + self.sent, 
                    min(self.length-self.sent, self.blocksize),
                    overlap
                )
            else:
                return self.iocp_send(self.offset+self.sent, self.length-self.sent, overlap)
        else:
            return self.iocp_send(self.offset+self.sent, self.blocksize, overlap)
            
    def iocp_done(self, rc, nbytes):
        self.sent += nbytes

    def run(self, reactor):
        if self.length:
            assert self.sent <= self.length
        if self.sent == self.length:
            return self
            
        if self.length:
            if self.blocksize:
                self.sent += self.send(
                    self.offset + self.sent, 
                    min(self.length-self.sent, self.blocksize)
                )
            else:
                self.sent += self.send(self.offset+self.sent, self.length-self.sent)
            if self.sent == self.length:
                return self
        else:
            if self.blocksize:
                sent = self.send(self.offset+self.sent, self.blocksize)
            else:
                sent = self.send(self.offset+self.sent, self.blocksize)
                # we would use self.length but we don't have any,
                #  and we don't know the file's length
            self.sent += sent
            if not sent:
                return self
        #TODO: test this some more with bad usage cases
        
        
    def __repr__(self):
        return "<%s at 0x%X %s fh:%s offset:%r len:%s bsz:%s to:%s>" % (
            self.__class__.__name__, 
            id(self), 
            self.sock, 
            self.file_handle, 
            self.offset, 
            self.length, 
            self.blocksize, 
            self.timeout
        )
    

class Read(ReadOperation):
    """
    Example usage:
    
    .. sourcecode:: python
        
        yield sockets.Read(socket_object, buffer_length)
    
    `buffer_length` is max read size, BUT, if if there are buffers from ReadLine 
    return them first.    
    """
    __slots__ = []
    
    def __init__(self, sock, len = 4096, **kws):
        super(Read, self).__init__(sock, **kws)
        self.len = len
        self.buff = None
    
    def run(self, reactor):
        if self.sock._rl_list:
            self.sock._rl_pending = ''.join(self.sock._rl_list) + self.sock._rl_pending
            self.sock._rl_list = []
            self.sock._rl_list_sz = 0
        if self.sock._rl_pending: 
            self.buff = self.sock._rl_pending
            self.addr = None
            self.sock._rl_pending = ''
            return self
        else:
            if reactor:
                self.buff, self.addr = self.sock._fd.recvfrom(self.len)
            else:
                self.buff = self.temp_buff
                self.temp_buff = None
                #TODO: self.addr
            if self.buff:
                return self
            else:
                if self.buff is None and not reactor:
                    return
                raise events.ConnectionClosed("Empty recv.")
    def finalize(self):
        super(Read, self).finalize()
        return self.buff
                
    def __str__(self):
        return "<%s at 0x%X %s P:%.100r L:%r B:%r to:%s>" % (
            self.__class__.__name__, 
            id(self), 
            self.sock, 
            self.sock._rl_pending, 
            fmt_list(self.sock._rl_list), 
            self.buff and self.buff[:self.trim], 
            self.timeout
        )
    def __repr__(self):
        return "<%s at 0x%X %s P:%r L:%r B:%r to:%s>" % (
            self.__class__.__name__, 
            id(self), 
            self.sock, 
            len(self.sock._rl_pending), 
            self.sock._rl_list_sz, 
            self.buff and len(self.buff), 
            self.timeout
        )
        
class ReadAll(ReadOperation):
    """
    Run this operation till we've read `len` bytes.
    """
    __slots__ = []
    
    def __init__(self, sock, len = 4096, **kws):
        super(ReadAll, self).__init__(sock, **kws)
        self.len = len
        self.buff = None
    
    def run(self, reactor):
        if self.sock._rl_pending:
            self.sock._rl_list.append(self.sock._rl_pending) 
                # we push in the buff list the pending buffer (for the sake of 
                # simplicity and effieciency) but we loose the linebreaks in the
                # pending buffer (i've assumed one would not try to use readline
                # while using read all, but he would use readall after he 
                # would use readline)
            self.sock._rl_list_sz += len(self.sock._rl_pending)
            self.sock._rl_pending = ''
        # looks like we have a nasty case here: we need to handle read that
        # have len less than _rl_list_sz
        if self.sock._rl_list_sz > self.len:
            # XXX: could need some optimization here
            self.sock._rl_pending = ''.join(self.sock._rl_list)
            self.sock._rl_list = []
            self.sock._rl_list_sz = 0
            self.buff = self.sock._rl_pending[:self.len]
            self.sock._rl_pending = self.sock._rl_pending[self.len:]
            return self
        if self.sock._rl_list_sz < self.len:
            if reactor:
                buff, self.addr = self.sock._fd.recvfrom(self.len-self.sock._rl_list_sz)
            else:
                buff = self.temp_buff
                self.temp_buff = None
                #TODO: self.addr
                
            #~ print '[', buff and len(buff), reactor, self.temp_buff, ']',
            if buff:
                self.sock._rl_list.append(buff)
                self.sock._rl_list_sz += len(buff)
            else:
                if buff is None and not reactor:
                    return
                raise events.ConnectionClosed("Empty recv.")
        if self.sock._rl_list_sz == self.len:
            self.buff = ''.join(self.sock._rl_list)
            self.sock._rl_list = []
            self.sock._rl_list_sz = 0
            return self
        else: # damn ! we still didn't recv enough
            return

    def finalize(self):
        super(ReadAll, self).finalize()
        return self.buff
            
    def __str__(self):
        return "<%s at 0x%X %s P:%.100r L:%r S:%r B:%r to:%s>" % (
            self.__class__.__name__, 
            id(self), 
            self.sock, 
            self.sock._rl_pending, 
            fmt_list(self.sock._rl_list),
            self.sock._rl_list_sz, 
            self.buff and self.buff[:self.trim], 
            self.timeout
        )
    def __repr__(self):
        return "<%s at 0x%X %s P:%r L:%r B:%r to:%s>" % (
            self.__class__.__name__, 
            id(self), 
            self.sock, 
            len(self.sock._rl_pending), 
            self.sock._rl_list_sz, 
            self.buff and len(self.buff), 
            self.timeout
        )
        
class ReadLine(ReadOperation):
    """
    Run this operation till we read a newline (\\n) or we have a overflow.
    
    """
    __slots__ = []
    
    def __init__(self, sock, len = 4096, **kws):
        """`len` is the max size for a line"""
        super(ReadLine, self).__init__(sock, **kws)
        self.len = len
        self.buff = None
        
    def check_overflow(self):
        if self.sock._rl_list_sz >= self.len: 
            #XXX: maybe we should keep the overflowing buffer? - in case
            # the user might try to readline again with a bigger buffer size
            
            self.sock._rl_list    = []
            self.sock._rl_list_sz = 0
            self.sock._rl_pending = ''
            # but then, if the user tries again with the same buffer size, it 
            # would error forever
            
            raise exceptions.OverflowError(
                "Recieved more than %s bytes (%s) and no linebreak" % (
                    self.len,
                    self.sock._rl_list_sz
                )
            )

    def run(self, reactor):
        if self.sock._rl_pending:
            nl = self.sock._rl_pending.find("\n")
            if nl >= 0:
                if nl + self.sock._rl_list_sz >= self.len:
                    self.sock._rl_list    = []
                    self.sock._rl_list_sz = 0
                    self.sock._rl_pending = ''
                    raise exceptions.OverflowError(
                        "Recieved more than %s bytes (%s) and no linebreak" % (
                            self.len, self.sock._rl_list_sz+nl
                        )
                    )
                
                nl += 1
                self.buff = ''.join(self.sock._rl_list) + \
                                            self.sock._rl_pending[:nl]
                self.sock._rl_list = []
                self.sock._rl_list_sz = 0
                self.sock._rl_pending = self.sock._rl_pending[nl:]
                return self
            else:
                self.sock._rl_list.append(self.sock._rl_pending)
                self.sock._rl_list_sz += len(self.sock._rl_pending)
                self.sock._rl_pending = ''
        self.check_overflow()
        
        if reactor:        
            x_buff, self.addr = self.sock._fd.recvfrom(self.len-self.sock._rl_list_sz)
        else:
            x_buff = self.temp_buff
            self.temp_buff = None
            #TODO: self.addr
            
        #~ print '[[', x_buff and len(x_buff), reactor, self.temp_buff, ']]',
            
        if x_buff:
            nl = x_buff.find("\n")
            if nl >= 0:
                nl += 1
                self.sock._rl_list.append(x_buff[:nl])
                self.buff = ''.join(self.sock._rl_list)
                self.sock._rl_list = []
                self.sock._rl_list_sz = 0
                self.sock._rl_pending = x_buff[nl:]
                
                return self
            else:
                self.sock._rl_list.append(x_buff)
                self.sock._rl_list_sz += len(x_buff)
                self.check_overflow()
        else: 
            if x_buff is None and not reactor:
                return
            raise events.ConnectionClosed("Empty recv.")
            
    def finalize(self):
        super(ReadLine, self).finalize()
        return self.buff
            
    def __str__(self):
        return "<%s at 0x%X %s P:%.100r L:%r S:%r B:%r to:%s>" % (
            self.__class__.__name__, 
            id(self), 
            self.sock, 
            self.sock._rl_pending, 
            fmt_list(self.sock._rl_list), 
            self.sock._rl_list_sz, 
            self.buff and self.buff[:self.trim], 
            self.timeout
        )
    def __repr__(self):
        return "<%s at 0x%X %s P:%r L:%r B:%r to:%s>" % (
            self.__class__.__name__, 
            id(self), 
            self.sock, 
            len(self.sock._rl_pending), 
            self.sock._rl_list_sz, 
            self.buff and len(self.buff), 
            self.timeout
        )

class Write(WriteOperation):
    """
    Write the buffer to the socket and return the number of bytes written.
    """    
    __slots__ = []
    
    def __init__(self, sock, buff, **kws):
        super(Write, self).__init__(sock, **kws)
        self.buff = buff
        self.sent = 0
        
    def run(self, reactor):
        if reactor:
            self.sent = self.sock._fd.send(self.buff)
        return self
    
    def finalize(self):
        super(Write, self).finalize()
        return self.sent
        
    def __str__(self):
        return "<%s at 0x%X %s S:%r B:%r to:%s>" % (
            self.__class__.__name__, 
            id(self), 
            self.sock, 
            self.sent, 
            self.buff and self.buff[:self.trim], 
            self.timeout
        )
    def __repr__(self):
        return "<%s at 0x%X %s S:%r B:%r to:%s>" % (
            self.__class__.__name__, 
            id(self), 
            self.sock, 
            self.sent, 
            self.buff and len(self.buff), 
            self.timeout
        )
        
class WriteAll(WriteOperation):
    """
    Run this operation till all the bytes have been written.
    """
    __slots__ = []
    
    def __init__(self, sock, buff, **kws):
        super(WriteAll, self).__init__(sock, **kws)
        self.buff = buff
        self.sent = 0
        
    def run(self, reactor):
        if reactor:
            sent = self.sock._fd.send(buffer(self.buff, self.sent))
            self.sent += sent
        assert self.sent <= len(self.buff)
        if self.sent == len(self.buff):
            return self
    
    def finalize(self):
        super(WriteAll, self).finalize()
        return self.sent
    
    def __str__(self):
        return "<%s at 0x%X %s S:%r B:%r to:%s>" % (
            self.__class__.__name__, 
            id(self), 
            self.sock, 
            self.sent, 
            self.buff and self.buff[:self.trim], 
            self.timeout
        )
    def __repr__(self):
        return "<%s at 0x%X %s S:%r B:%r to:%s>" % (
            self.__class__.__name__, 
            id(self), 
            self.sock, 
            self.sent, 
            self.buff and len(self.buff), 
            self.timeout
        )
 
class Accept(ReadOperation):
    """
    Returns a (conn, addr) tuple when the operation completes.
    """
    __slots__ = ['conn', 'conn_buff']
    
    def __init__(self, sock, **kws):
        super(Accept, self).__init__(sock, **kws)
        self.conn = None
        
    def run(self, reactor):
        if reactor:
            self.conn, self.addr = self.sock._fd.accept()
            self.conn = Socket(_sock=self.conn)
            self.conn.setblocking(0)
        else:
            if not self.conn:
                return
            self.conn.setblocking(0)
            self.conn.setsockopt(
                socket.SOL_SOCKET, 
                win32file.SO_UPDATE_ACCEPT_CONTEXT, 
                struct.pack("I", self.sock.fileno())
            )
            self.conn = Socket(_sock=self.conn)
            family, localaddr, self.addr = win32file.GetAcceptExSockaddrs(
                self.conn, self.conn_buff
            )
            
        return self

    def iocp(self, overlap):
        self.conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.conn_buff = win32file.AllocateReadBuffer(64)
        return win32file.WSA_IO_PENDING, win32file.AcceptEx(
            self.sock._fd.fileno(), self.conn.fileno(), self.conn_buff, overlap
        )
        
    def iocp_done(self, rc, nbytes):
        pass
        
        
    def finalize(self):
        super(Accept, self).finalize()
        return (self.conn, self.addr)
        
    def __repr__(self):
        return "<%s at 0x%X %s conn:%r to:%s>" % (
            self.__class__.__name__, 
            id(self), 
            self.sock, 
            self.conn, 
            self.timeout
        )
             
class Connect(WriteOperation):
    """
    
    """
    __slots__ = ['connect_attempted']
    
    def __init__(self, sock, addr, **kws):
        """
        Connect to the given `addr` using `sock`.
        """
        super(Connect, self).__init__(sock, **kws)
        self.addr = addr
        self.connect_attempted = False # this is a shield against multiple 
                                       #connect_ex calls
    def process(self, sched, coro):
        #  we can't just try-run this with iocp, because if we do ConnectEx 
        # will fail
        super(SocketOperation, self).process(sched, coro)
        has_iocp = reactors.has_iocp()
        if not (has_iocp and isinstance(sched.poll, has_iocp)) and \
                                (self.run_first or self.pending()):
            r = sched.poll.run_or_add(self, coro)
            if r:
                if self.prio:
                    return r, r and coro
                else:
                    sched.active.appendleft((r, coro))
        else:
            sched.poll.add(self, coro)
            
    def iocp(self, overlaped):
        # ConnectEx requires that the socket be bound beforehand
        try:
            # just in case we get a already-bound socket
            self.sock.bind(('0.0.0.0', 0))
        except socket.error, exc:
            if exc[0] not in (errno.EINVAL, errno.WSAEINVAL):
                raise
        self.connect_attempted = True
        x=win32file.ConnectEx(self.sock, self.addr, overlaped)
        print x, overlaped
        return x
        
    def iocp_done(self, *args):
        self.sock.setsockopt(socket.SOL_SOCKET, win32file.SO_UPDATE_CONNECT_CONTEXT, "")
    
    def run(self, reactor):
        if not reactor:
            # this means we've been called from IOCPProactor
            # we can't just attempt a blind connect because we can't use 
            #ConnectEx then.
            
            # so basicaly we do this:
            if self.connect_attempted:
                # connection has been successful - as we've got here from a gqcs
                return self
            else:
                # we need to connect via ConnectEx - we force adding this op in 
                #the reactor
                return 
                
            
        #
        #We need to avoid some non-blocking socket connect quirks: 
        #  - if you attempt a connect in NB mode you will always 
        #  get EWOULDBLOCK, presuming the addr is correct.
        #
        # check: http://cr.yp.to/docs/connect.html
        if self.connect_attempted:
            try:
                self.sock._fd.getpeername()
            except socket.error, exc:
                if exc[0] not in (errno.EAGAIN, errno.EWOULDBLOCK, 
                                errno.EINPROGRESS, errno.ENOTCONN):
                    raise
                    #TODO, getsockopt(SO_ERROR)
            return self
        #~ print 'self.sock._fd.connect_ex(self.addr)'
        #~ raise Exception, reactor
        err = self.sock._fd.connect_ex(self.addr)
        self.connect_attempted = True
        if err:
            if err == errno.EISCONN:
                return self
            if err not in (errno.EAGAIN, errno.EWOULDBLOCK, errno.EINPROGRESS):
                raise socket.error(err, errno.errorcode[err])
        else:
            return self
        
    def __repr__(self):
        return "<%s at 0x%X %s to:%s attempted:%s>" % (
            self.__class__.__name__, 
            id(self), 
            self.sock, 
            self.timeout,
            self.connect_attempted
        )
