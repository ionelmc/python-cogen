import socket
import errno
import exceptions
import datetime

from cogen.core import events
from cogen.core.util import *
try:
    import sendfile
except ImportError:
    sendfile = None
    
__doc_all__ = [
    'Socket',
    'SendFile',    
    'Read',    
    'ReadAll',    
    'ReadLine',    
    'Write',    
    'WriteAll',    
    'Accept',    
    'Connect',
    'Operation',
]

class Socket(socket.socket):
    __slots__ = ['_rl_list', '_rl_list_sz', '_rl_pending']
    """
        We need some additional buffers and stuff:
            rl_pending - for unchecked for linebreaks buffer
            rl_list - for checked for linebreaks buffers
            rl_list_sz - a cached size of the summed sizes of rl_list buffers
    """
    def __init__(self, *a, **k):
        super(self.__class__, self).__init__(*a, **k)
        self._rl_list = []
        self._rl_list_sz = 0
        self._rl_pending = ''
        self.setblocking(0)
    #~ @debug(0)
    #~ def close(self):
        #~ print "> closing sock 0x%X" % id(self)
        #~ super(self.__class__, self).close()
    def __repr__(self):
        return '<socket at 0x%X>' % id(self)
    def __str__(self):
        return 'sock@0x%X' % id(self)
class Operation(object):
    __slots__ = ['sock', '_timeout', 'weak_timeout', 'last_update', '__weakref__', 'fileno', 'prio', 'finalized']
    __doc_all__ = ['__init__', 'try_run']
    trim = 2000
    """
    This is a generic class for a operation that involves some socket call.
        
    A socket operation should subclass WriteOperation or ReadOperation, define a `run` method 
    and call the __init__ method of the superclass.
    """
    def __init__(self, sock, timeout=None, weak_timeout=True, prio=priority.DEFAULT):
        """
        All the socket operations have these generic properties that the 
        poller and scheduler interprets:
        
        * timeout - the ammout of time in seconds or timedelta, or the datetime value till
          the poller should wait for this operation.
        * weak_timeout - if this is True the timeout handling code will take into account
          the time of last activity (that would be the time of last `try_run` call)
        * prio - a flag for the scheduler
        """
        
        assert isinstance(sock, Socket)
        self.sock = sock
        self.timeout = timeout
        self.finalized = False
        self.weak_timeout = weak_timeout
        self.prio = prio
    def try_run(self):
        """
        This method will return a None value or raise a exception if the operation can'self complete at this time.
        
        The socket poller will run this method if the socket is readable/writeable.
        
        If this returns a value that evaluates to False, the poller will try to run this 
        at a later time (when the socket is readable/writeable again).
        """
        try:
            result = self.run()
            self.last_update = datetime.datetime.now()
            return result
        except socket.error, exc:
            if exc[0] in (errno.EAGAIN, errno.EWOULDBLOCK): 
                return None
            elif exc[0] == errno.EPIPE:
                raise events.ConnectionClosed(exc)
            else:
                raise
        return self
    def run(self):
        raise NotImplementedError()
    timeout = TimeoutDesc('_timeout')

class ReadOperation(Operation): 
    pass

class WriteOperation(Operation): 
    pass
    
class SendFile(WriteOperation):
    """
        Uses underling OS sendfile call or a regular memory copy operation if there is no sendfile.
        You can use this as a WriteAll if you specify the length.
        Usage:
            
        .. sourcecode:: python
            
            yield sockets.SendFile(<file handle>, <sock>, 0) 
                # will send till send operations return 0
                
            yield sockets.SendFile(<file handle>, <sock>, 0, blocksize=0)
                # there will be only one send operation (if successfull)
                # that meas the whole file will be read in memory if there is no sendfile
                
            yield sockets.SendFile(<file handle>, <sock>, 0, <file size>)
                # this will hang if we can'self read <file size> bytes from the file
        
    """
    __slots__ = ['sent', 'file_handle', 'offset', 'position', 'length', 'blocksize']
    __doc_all__ = ['__init__', 'run']
    def __init__(self, file_handle, sock, offset=None, length=None, blocksize=4096, **kws):
        self.file_handle = file_handle
        self.offset = self.position = offset or file_handle.tell()
        self.length = length
        self.sent = 0
        self.blocksize = blocksize
        super(self.__class__, self).__init__(sock, **kws)
    def send(self, offset, len):
        if sendfile:
            offset, sent = sendfile.sendfile(self.sock.fileno(), self.file_handle.fileno(), offset, len)
        else:
            self.file_handle.seek(offset)
            sent = self.sock.send(self.file_handle.read(len))
        return sent
    def run(self):
        if self.length:
            if self.blocksize:
                self.sent += self.send(self.offset+self.sent, min(self.length, self.blocksize))
            else:
                self.sent += self.send(self.offset+self.sent, self.length)
            if self.sent == self.length:
                return self
        else:
            if self.blocksize:
                sent = self.send(self.offset+self.sent, self.blocksize)
            else:
                sent = self.send(self.offset+self.sent, self.blocksize)
            self.sent += sent
            if not sent:
                return self
    def __repr__(self):
        return "<%s at 0x%X %s fh:%s offset:%r len:%s bsz:%s to:%s>" % (self.__class__.__name__, id(self), self.sock, self.file_handle, self.offset, self.length, self.blocksize, self.timeout)
    

class Read(ReadOperation):
    """
        `len` is max read size, BUT, if if there are buffers from ReadLine return them first.
        Example usage:
        
        .. sourcecode:: python
            yield sockets.Read(socket_object, buffer_length)
    """
    __slots__ = ['len', 'buff', 'addr', 'result']
    __doc_all__ = ['__init__', 'run']
    def __init__(self, sock, len = 4096, **kws):
        self.len = len
        self.buff = None
        super(self.__class__, self).__init__(sock, **kws)
    def run(self):
        if self.sock._rl_list:
            self.sock._rl_pending = ''.join(self.sock._rl_list) + self.sock._rl_pending
            self.sock._rl_list = []
        if self.sock._rl_pending: # XXX tofix
            self.buff = self.result = self.sock._rl_pending
            self.addr = None
            self.sock._rl_pending = ''
            return self
        else:
            self.buff, self.addr = self.sock.recvfrom(self.len)
            if self.buff:
                self.result = self.buff
                return self
            else:
                raise events.ConnectionClosed("Empty recv.")
    def __repr__(self):
        return "<%s at 0x%X %s P:%r L:%r B:%r to:%s>" % (self.__class__.__name__, id(self), self.sock, self.sock._rl_pending, self.sock._rl_list, self.buff and self.buff[:self.trim], self.timeout)
        
class ReadAll(ReadOperation):
    """
    Run this operator till we've read `len` bytes.
    """
    __slots__ = ['len', 'buff', 'addr', 'result']
    __doc_all__ = ['__init__', 'run']
    def __init__(self, sock, len = 4096, **kws):
        self.len = len
        self.buff = None
        super(self.__class__, self).__init__(sock, **kws)
    def run(self):
        if self.sock._rl_pending:
            self.sock._rl_list.append(self.sock._rl_pending) 
                # we push in the buff list the pending buffer (for the sake of simplicity and effieciency)
                # but we loose the linebreaks in the pending buffer (i've assumed one would not try to use readline 
                #     while using read all, but he would use readall after he would use readline)
            self.sock._rl_list_sz += len(self.sock._rl_pending)
            self.sock._rl_pending = ''
        if self.sock._rl_list_sz < self.len:
            buff, self.addr = self.sock.recvfrom(self.len-self.sock._rl_list_sz)
            if buff:
                self.sock._rl_list.append(buff)
                self.sock._rl_list_sz += len(buff)
            else:
                raise events.ConnectionClosed("Empty recv.")
        if self.sock._rl_list_sz == self.len:
            self.buff = self.result =  ''.join(self.sock._rl_list)
            self.sock._rl_list = []
            return self
        else: # damn ! we still didn'self recv enough
            return
    def __repr__(self):
        return "<%s at 0x%X %s P:%r L:%r S:%r B:%r to:%s>" % (self.__class__.__name__, id(self), self.sock, self.sock._rl_pending, self.sock._rl_list, self.sock._rl_list_sz, self.buff and self.buff[:self.trim], self.timeout)
        
class ReadLine(ReadOperation):
    """
        Run this operator till we read a newline (\\n) or we have a overflow.
        
        `len` is the max size for a line
    """
    __slots__ = ['len', 'buff', 'addr', 'result']
    __doc_all__ = ['__init__', 'run']
    def __init__(self, sock, len = 4096, **kws):
        self.len = len
        self.buff = None
        super(self.__class__, self).__init__(sock, **kws)
    def check_overflow(self):
        if self.sock._rl_list_sz>=self.len: 
            #~ rl_list    = self.sock._rl_list   
            #~ rl_list_sz = self.sock._rl_list_sz
            #~ rl_pending = self.sock._rl_pending
            self.sock._rl_list    = []
            self.sock._rl_list_sz = 0
            self.sock._rl_pending = ''
            raise exceptions.OverflowError("Recieved %s bytes and no linebreak" % self.len)
    def run(self):
        #~ print '>',self.sock._rl_list_sz
        if self.sock._rl_pending:
            nl = self.sock._rl_pending.find("\n")
            if nl>=0:
                nl += 1
                self.buff = self.result = ''.join(self.sock._rl_list)+self.sock._rl_pending[:nl]
                self.sock._rl_list = []
                self.sock._rl_list_sz = 0
                self.sock._rl_pending = self.sock._rl_pending[nl:]
                #~ print 'return self(p)', repr((self.buff, x_buff, self.sock._rl_pending))
                return self
            else:
                self.sock._rl_list.append(self.sock._rl_pending)
                self.sock._rl_list_sz += len(self.sock._rl_pending)
                self.sock._rl_pending = ''
        self.check_overflow()
                
        x_buff, self.addr = self.sock.recvfrom(self.len-self.sock._rl_list_sz)
        nl = x_buff.find("\n")
        if x_buff:
            if nl >= 0:
                nl += 1
                self.sock._rl_list.append(x_buff[:nl])
                self.buff = self.result = ''.join(self.sock._rl_list)
                self.sock._rl_list = []
                self.sock._rl_list_sz = 0
                self.sock._rl_pending = x_buff[nl:]
                
                return self
            else:
                self.sock._rl_list.append(x_buff)
                self.sock._rl_list_sz += len(x_buff)
                self.check_overflow()
        else: 
            raise events.ConnectionClosed("Empty recv.")
    def __repr__(self):
        return "<%s at 0x%X %s P:%r L:%r S:%r B:%r to:%s>" % (self.__class__.__name__, id(self), self.sock, self.sock._rl_pending, self.sock._rl_list, self.sock._rl_list_sz, self.buff and self.buff[:self.trim], self.timeout)

class Write(WriteOperation):
    """
    Write the buffer to the socket and return the number of bytes written.
    """    
    __slots__ = ['sent', 'buff', 'result']
    __doc_all__ = ['__init__', 'run']
    def __init__(self, sock, buff, **kws):
        self.buff = buff
        self.sent = 0
        super(self.__class__, self).__init__(sock, **kws)
    def run(self):
        self.sent = self.result = self.sock.send(self.buff)
        return self
    def __repr__(self):
        return "<%s at 0x%X %s S:%r B:%r to:%s>" % (self.__class__.__name__, id(self), self.sock, self.sent, self.buff and self.buff[:self.trim], self.timeout)
        
class WriteAll(WriteOperation):
    """
    Run this operation till all the bytes have been written.
    """
    __slots__ = ['sent', 'buff']
    __doc_all__ = ['__init__', 'run']
    def __init__(self, sock, buff, **kws):
        self.buff = buff
        self.sent = 0
        super(self.__class__, self).__init__(sock, **kws)
    def run(self):
        sent = self.sock.send(buffer(self.buff,self.sent))
        self.sent += sent
        if self.sent == len(self.buff):
            self.result = self.sent
            return self
    def __repr__(self):
        return "<%s at 0x%X %s S:%r B:%r to:%s>" % (self.__class__.__name__, id(self), self.sock, self.sent, self.buff and self.buff[:self.trim], self.timeout)
 
class Accept(ReadOperation):
    """
    Returns a (conn, addr) tuple when the operation completes.
    """
    __slots__ = ['conn', 'addr', 'result']
    __doc_all__ = ['__init__', 'run']
    def __init__(self, sock, **kws):
        self.conn = None
        super(self.__class__, self).__init__(sock, **kws)
    def run(self):
        self.conn, self.addr = self.sock.accept()
        self.conn = Socket(_sock=self.conn)
        self.conn.setblocking(0)
        self.result = self.conn, self.addr
        return self
        def __repr__(self):
        return "<%s at 0x%X %s conn:%r to:%s>" % (self.__class__.__name__, id(self), self.sock, self.conn, self.timeout)
             
class Connect(WriteOperation):
    """
    Connect to the given `addr` using `sock`.
    """
    __slots__ = ['addr']
    __doc_all__ = ['__init__', 'run']
    def __init__(self, sock, addr, **kws):
        self.addr = addr
        super(self.__class__, self).__init__(sock, **kws)
    def run(self):
        """ 
        We need to avoid some non-blocking socket connect quirks: 
            if you attempt a connect in NB mode you will always 
            get EWOULDBLOCK, presuming the addr is correct.
        """
        err = self.sock.connect_ex(self.addr)
        if err:
            if err in (errno.EAGAIN, errno.EWOULDBLOCK, errno.EINPROGRESS):
                try:
                    self.sock.getpeername()
                except socket.error, exc:
                    if exc[0] == errno.ENOTCONN:
                        raise
            else:
                raise socket.error(err, errno.errorcode[err])
        return self
    def __repr__(self):
        return "<%s at 0x%X %s to:%s>" % (self.__class__.__name__, id(self), self.sock, self.timeout)

#~ ops = (Read, ReadAll, ReadLine, Connect, Write, WriteAll, Accept)
#~ read_ops = (Read, ReadAll, ReadLine, Accept)
#~ write_ops = (Connect, Write, WriteAll)
