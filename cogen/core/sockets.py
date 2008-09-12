"""
Socket-only coroutine operations and `Socket` wrapper.
Really - the only thing you need to know for most stuff is 
the `Socket <cogen.core.sockets.Socket.html>`_ class.
"""

#TODO: how to deal with requets that have unicode params

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
from coroutines import coro, debug_coro
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
    __slots__ = ['_fd', '_timeout', '_proactor_added']
    def __init__(self, *a, **k):
        self._fd = socket.socket(*a, **k)
        self._fd.setblocking(0)
        self._timeout = _TIMEOUT
        self._proactor_added = False
            
    def recv(self, bufsize, **kws):
        """Receive data from the socket. The return value is a string 
        representing the data received. The amount of data may be less than the
        ammount specified by _bufsize_. """
        return Recv(self, bufsize, timeout=self._timeout, **kws)
        
       
    def makefile(self, mode='r', bufsize=-1):
        """
        Returns a special fileobject that has corutines instead of the usual
        read/readline/write methods. Will work in the same manner though.
        """
        return _fileobject(self, mode, bufsize)
        
    def send(self, data, **kws):
        """Send data to the socket. The socket must be connected to a remote 
        socket. Ammount sent may be less than the data provided."""
        return Send(self, data, timeout=self._timeout, **kws)
        
    def sendall(self, data, **kws):
        """Send data to the socket. The socket must be connected to a remote 
        socket. All the data is guaranteed to be sent."""
        return SendAll(self, data, timeout=self._timeout, **kws)
        
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
        return Accept(self, timeout=self._timeout, **kws)
        
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
        return Connect(self, address, timeout=self._timeout, **kws)
    
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
    
    def sendfile(self, file_handle, offset=None, length=None, blocksize=4096, **kws):
        return SendFile(file_handle, self, offset=None, length=None, blocksize=4096, **kws)
        
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
        'sock', 'last_update', 'coro', 'flags'
    ]
    def __init__(self, sock, **kws):
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
    
    def fileno(self):
        return self.sock._fd.fileno()
        
    def cleanup(self, sched, coro):
        return sched.proactor.remove_token(self)
    
    
class SendFile(SocketOperation):
    """
        Uses underling OS sendfile (or equivalent) call or a regular memory copy 
        operation if there is no sendfile.
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
        
    def process(self, sched, coro):
        super(SendFile, self).process(sched, coro)
        return sched.proactor.request_sendfile(self, coro)
    
    def finalize(self):
        super(SendFile, self).finalize()
        return self.sent


class Recv(SocketOperation):
    """
    Example usage:
    
    .. sourcecode:: python
        
        yield sockets.Read(socket_object, buffer_length)
    
    `buffer_length` is max read size, BUT, if if there are buffers from ReadLine 
    return them first.    
    """
    __slots__ = ['buff', 'len']
        
    def __init__(self, sock, len = 4096, **kws):
        super(Recv, self).__init__(sock, **kws)
        self.len = len
        self.buff = None
    
    def process(self, sched, coro):
        super(Recv, self).process(sched, coro)
        return sched.proactor.request_recv(self, coro)
        
    def finalize(self):
        super(Recv, self).finalize()
        return self.buff


class Send(SocketOperation):
    """
    Write the buffer to the socket and return the number of bytes written.
    """    
    __slots__ = ['sent', 'buff']
    
    def __init__(self, sock, buff, **kws):
        super(Send, self).__init__(sock, **kws)
        self.buff = buff
        self.sent = 0
        
    def process(self, sched, coro):
        super(Send, self).process(sched, coro)
        return sched.proactor.request_send(self, coro)
    
    def finalize(self):
        super(Send, self).finalize()
        return self.sent
        
class SendAll(SocketOperation):
    """
    Run this operation till all the bytes have been written.
    """
    __slots__ = ['sent', 'buff']
    
    def __init__(self, sock, buff, **kws):
        super(SendAll, self).__init__(sock, **kws)
        self.buff = buff
        self.sent = 0
        
    def process(self, sched, coro):
        super(SendAll, self).process(sched, coro)
        return sched.proactor.request_sendall(self, coro)
    
    def finalize(self):
        super(SendAll, self).finalize()
        return self.sent
 
class Accept(SocketOperation):
    """
    Returns a (conn, addr) tuple when the operation completes.
    """
    __slots__ = ['conn', 'addr', 'cbuff']
    
    def __init__(self, sock, **kws):
        super(Accept, self).__init__(sock, **kws)
        self.conn = None
        
    def process(self, sched, coro):
        super(Accept, self).process(sched, coro)
        return sched.proactor.request_accept(self, coro)

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
             
class Connect(SocketOperation):
    """
    
    """
    __slots__ = ['addr', 'conn', 'connect_attempted']
    
    def __init__(self, sock, addr, **kws):
        """
        Connect to the given `addr` using `sock`.
        """
        super(Connect, self).__init__(sock, **kws)
        self.addr = addr
        self.connect_attempted = False

    def process(self, sched, coro):
        super(Connect, self).process(sched, coro)
        return sched.proactor.request_connect(self, coro)
        
    def finalize(self):
        super(Connect, self).finalize()
        return self.sock

@coro
def RecvAll(sock, length, **k):
    recvd = 0
    data = []
    while recvd < length:
        chunk = (yield Recv(sock, length-recvd,  **k))
        recvd += len(chunk)
        data.append(chunk)
    assert recvd == length
    
    raise StopIteration(''.join(data))

class _fileobject(object):
    """Faux file object attached to a socket object."""

    default_bufsize = 8192
    name = "<socket>"

    __slots__ = ["mode", "bufsize", "softspace",
                 # "closed" is a property, see below
                 "_sock", "_rbufsize", "_wbufsize", "_rbuf", "_wbuf",
                 "_close"]

    def __init__(self, sock, mode='rb', bufsize=-1, close=False):
        self._sock = sock
        self.mode = mode # Not actually used in this version
        if bufsize < 0:
            bufsize = self.default_bufsize
        self.bufsize = bufsize
        self.softspace = False
        if bufsize == 0:
            self._rbufsize = 1
        elif bufsize == 1:
            self._rbufsize = self.default_bufsize
        else:
            self._rbufsize = bufsize
        self._wbufsize = bufsize
        self._rbuf = "" # A string
        self._wbuf = [] # A list of strings
        self._close = close

    def _getclosed(self):
        return self._sock is None
    closed = property(_getclosed, doc="True if the file is closed")
    
    @coro
    def close(self, **kws):
        try:
            if self._sock:
                yield self.flush(**kws)
        finally:
            if self._close:
                self._sock.close()
            self._sock = None

    def __del__(self):
        try:
            self.close()
        except:
            # close() may fail if __init__ didn't complete
            pass

    @coro
    def flush(self, **kws):
        if self._wbuf:
            buffer = "".join(self._wbuf)
            self._wbuf = []
            yield self._sock.sendall(buffer, **kws)

    def fileno(self):
        return self._sock.fileno()

    @coro
    def write(self, data, **kws):
        data = str(data) # XXX Should really reject non-string non-buffers
        if not data:
            return
        self._wbuf.append(data)
        if (self._wbufsize == 0 or
            self._wbufsize == 1 and '\n' in data or
            self._get_wbuf_len() >= self._wbufsize):
            yield self.flush(**kws)

    @coro
    def writelines(self, list, **kws):
        # XXX We could do better here for very long lists
        # XXX Should really reject non-string non-buffers
        self._wbuf.extend(filter(None, map(str, list)))
        if (self._wbufsize <= 1 or
            self._get_wbuf_len() >= self._wbufsize):
            yield self.flush(**kws)

    def _get_wbuf_len(self):
        buf_len = 0
        for x in self._wbuf:
            buf_len += len(x)
        return buf_len

    #~ from cogen.core.coroutines import debug_coro
    #~ @debug_coro
    @coro
    def read(self, size=-1, **kws):
        data = self._rbuf
        if size < 0:
            # Read until EOF
            buffers = []
            if data:
                buffers.append(data)
            self._rbuf = ""
            if self._rbufsize <= 1:
                recv_size = self.default_bufsize
            else:
                recv_size = self._rbufsize
            while True:
                data = (yield self._sock.recv(recv_size, **kws))
                if not data:
                    break
                buffers.append(data)
            raise StopIteration("".join(buffers))
        else:
            # Read until size bytes or EOF seen, whichever comes first
            buf_len = len(data)
            if buf_len >= size:
                self._rbuf = data[size:]
                raise StopIteration(data[:size])
            buffers = []
            if data:
                buffers.append(data)
            self._rbuf = ""
            while True:
                left = size - buf_len
                recv_size = max(self._rbufsize, left)
                data = (yield self._sock.recv(recv_size, **kws))
                if not data:
                    break
                buffers.append(data)
                n = len(data)
                if n >= left:
                    self._rbuf = data[left:]
                    buffers[-1] = data[:left]
                    break
                buf_len += n
            raise StopIteration("".join(buffers))
    #~ from coroutines import debug_coro
    #~ @debug_coro
    @coro
    def readline(self, size=-1, **kws):
        data = self._rbuf
        if size < 0:
            # Read until \n or EOF, whichever comes first
            if self._rbufsize <= 1:
                # Speed up unbuffered case
                assert data == ""
                buffers = []
                recv = self._sock.recv
                while data != "\n":
                    data = (yield recv(1, **kws))
                    if not data:
                        break
                    buffers.append(data)
                raise StopIteration("".join(buffers))
            nl = data.find('\n')
            if nl >= 0:
                nl += 1
                self._rbuf = data[nl:]
                raise StopIteration(data[:nl])
            buffers = []
            if data:
                buffers.append(data)
            self._rbuf = ""
            while True:
                data = (yield self._sock.recv(self._rbufsize, **kws))
                if not data:
                    break
                buffers.append(data)
                nl = data.find('\n')
                if nl >= 0:
                    nl += 1
                    self._rbuf = data[nl:]
                    buffers[-1] = data[:nl]
                    break
            raise StopIteration("".join(buffers))
        else:
            # Read until size bytes or \n or EOF seen, whichever comes first
            nl = data.find('\n', 0, size)
            if nl >= 0:
                nl += 1
                self._rbuf = data[nl:]
                raise StopIteration(data[:nl])
            buf_len = len(data)
            if buf_len >= size:
                self._rbuf = data[size:]
                raise StopIteration(data[:size])
            buffers = []
            if data:
                buffers.append(data)
            self._rbuf = ""
            while True:
                data = (yield self._sock.recv(self._rbufsize, **kws))
                if not data:
                    break
                buffers.append(data)
                left = size - buf_len
                nl = data.find('\n', 0, left)
                if nl >= 0:
                    nl += 1
                    self._rbuf = data[nl:]
                    buffers[-1] = data[:nl]
                    break
                n = len(data)
                if n >= left:
                    self._rbuf = data[left:]
                    buffers[-1] = data[:left]
                    break
                buf_len += n
            raise StopIteration("".join(buffers))

    @coro
    def readlines(self, sizehint=0, **kws):
        total = 0
        list = []
        while True:
            line = (yield self.readline(**kws))
            if not line:
                break
            list.append(line)
            total += len(line)
            if sizehint and total >= sizehint:
                break
        raise StopIteration(list)

