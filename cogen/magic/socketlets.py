from cogen.core.sockets import Send, Recv, SendAll, Accept, Connect, \
        getdefaulttimeout, setdefaulttimeout
from cogen.core import sockets
from cogen.magic.corolets import yield_

from socket import _fileobject, socket

class Socket(sockets.Socket):
    """
    A wrapper for socket objects, sets nonblocking mode and
    adds some internal bufers and wrappers. Regular calls to the usual
    socket methods return operations for use in a coroutine.

    So you use this in a corolet like:

    .. sourcecode:: python

        sock = Socket(family, type, proto) # just like the builtin socket module
        sock.read(1024)


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
    __slots__ = ()

    def recv(self, bufsize, **kws):
        """Receive data from the socket. The return value is a string
        representing the data received. The amount of data may be less than the
        ammount specified by _bufsize_. """
        return yield_(Recv(self, bufsize, timeout=self._timeout, **kws))


    def makefile(self, mode='r', bufsize=-1):
        """
        Returns a special fileobject that has corutines instead of the usual
        read/readline/write methods. Will work in the same manner though.
        """
        return _fileobject(self, mode, bufsize)

    def send(self, data, **kws):
        """Send data to the socket. The socket must be connected to a remote
        socket. Ammount sent may be less than the data provided."""
        return yield_(Send(self, data, timeout=self._timeout, **kws))

    def sendall(self, data, **kws):
        """Send data to the socket. The socket must be connected to a remote
        socket. All the data is guaranteed to be sent."""
        return yield_(SendAll(self, data, timeout=self._timeout, **kws))

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
        return yield_(Accept(self, timeout=self._timeout, **kws))

    def connect(self, address, **kws):
        """Connect to a remote socket at _address_. """
        return yield_(Connect(self, address, timeout=self._timeout, **kws))

    def sendfile(self, file_handle, offset=None, length=None, blocksize=4096, **kws):
        return yield_(SendFile(file_handle, self, offset, length, blocksize, **kws))

