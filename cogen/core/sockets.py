import socket
import errno
import exceptions
import datetime

from cogen.core import events
from cogen.core.util import *

class WrappedSocket(socket.socket):
    __name__ = "Socket"
    __slots__ = ['_rl_list', '_rl_list_sz', '_rl_pending']
    """
        Wee need some additional buffers and stuff:
            rl_pending - for unchecked for linebreaks buffer
            rl_list - for checked for linebreaks buffers
            rl_list_sz - a cached size of the summed sizes of rl_list buffers
    """
    def __init__(t, *a, **k):
        socket.socket.__init__(t, *a, **k)
        t._rl_list = []
        t._rl_list_sz = 0
        t._rl_pending = ''
        t.setblocking(0)
    def __repr__(t):
        return '<socket at 0x%X>' % id(t)
    def __str__(t):
        return 'sock@0x%X' % id(t)
New = Socket = WrappedSocket
class Operation(object):
    __slots__ = ['_timeout','__weakref__']
    
    def try_run(t):
        try:
            return t.run()
        except socket.error, exc:
            if exc[0] in (errno.EAGAIN, errno.EWOULDBLOCK): 
                return None
            elif exc[0] == errno.EPIPE:
                raise events.ConnectionClosed()
            else:
                raise
        return t
    timeout = TimeoutDesc('_timeout')

class ReadOperation(Operation): 
    pass

class WriteOperation(Operation): 
    pass
    
class Read(ReadOperation):
    """
        `len` is max read size, BUT, if if there are buffers from ReadLine return them first.
    """
    __slots__ = ['sock','len','buff','addr','prio','result']
    def __init__(t, sock, len = 4096, timeout=None, prio=priority.DEFAULT):
        assert isinstance(sock, WrappedSocket)
        t.sock = sock
        t.len = len
        t.buff = None
        t.timeout = timeout
        t.prio = prio
    def run(t):
        if t.sock._rl_list:
            t.sock._rl_pending = ''.join(t.sock._rl_list) + t.sock._rl_pending
            t.sock._rl_list = []
        if t.sock._rl_pending: # XXX tofix
            t.buff = t.result = sock._rl_pending
            t.addr = None
            t.sock._rl_pending = ''
            return t
        else:
            t.buff, t.addr = t.sock.recvfrom(t.len)
            if t.buff:
                t.result = t.buff
                return t
            else:
                raise events.ConnectionClosed()
    def __repr__(t):
        return "<%s at 0x%X %s P:%r L:%r B:%r to:%s>" % (t.__class__.__name__, id(t), t.sock, t.sock._rl_pending, t.sock._rl_list, t.buff, t.timeout)
        
class ReadAll(ReadOperation):
    __slots__ = ['sock','len','buff','addr','prio','result']
    def __init__(t, sock, len = 4096, timeout=None, prio=priority.DEFAULT):
        assert isinstance(sock, WrappedSocket)
        t.sock = sock
        t.len = len
        t.buff = None
        t.timeout = timeout
        t.prio = prio
    def run(t):
        if t.sock._rl_pending:
            t.sock._rl_list.append(t.sock._rl_pending) 
                # we push in the buff list the pending buffer (for the sake of simplicity and effieciency)
                # but we loose the linebreaks in the pending buffer (i've assumed one would not try to use readline 
                #     while using read all, but he would use readall after he would use readline)
            t.sock._rl_list_sz += len(t.sock._rl_pending)
            t.sock._rl_pending = ''
        if t.sock._rl_list_sz < t.len:
            buff, t.addr = t.sock.recvfrom(t.len-t.sock._rl_list_sz)
            if buff:
                t.sock._rl_list.append(buff)
                t.sock._rl_list_sz += len(buff)
            else:
                raise events.ConnectionClosed()
        if t.sock._rl_list_sz == t.len:
            t.buff = t.result =  ''.join(t.sock._rl_list)
            t.sock._rl_list = []
            return t
        else: # damn ! we still didn't recv enough
            return
    def __repr__(t):
        return "<%s at 0x%X %s P:%r L:%r S:%r B:%r to:%s>" % (t.__class__.__name__, id(t), t.sock, t.sock._rl_pending, t.sock._rl_list, t.sock._rl_list_sz, t.buff, t.timeout)
        
class ReadLine(ReadOperation):
    """
        `len` is the max size for a line
    """
    __slots__ = ['sock','len','buff','addr','prio','result']
    def __init__(t, sock, len = 4096, timeout=None, prio=priority.DEFAULT):
        assert isinstance(sock, WrappedSocket)
        t.sock = sock
        t.len = len
        t.buff = None
        t.timeout = timeout
        t.prio = prio
    def check_overflow(t):
        if t.sock._rl_list_sz>=t.len: 
            #~ rl_list    = t.sock._rl_list   
            #~ rl_list_sz = t.sock._rl_list_sz
            #~ rl_pending = t.sock._rl_pending
            t.sock._rl_list    = []
            t.sock._rl_list_sz = 0
            t.sock._rl_pending = ''
            raise exceptions.OverflowError("Recieved %s bytes and no linebreak" % t.len)
    def run(t):
        #~ print '>',t.sock._rl_list_sz
        if t.sock._rl_pending:
            nl = t.sock._rl_pending.find("\n")
            if nl>=0:
                nl += 1
                t.buff = t.result = ''.join(t.sock._rl_list)+t.sock._rl_pending[:nl]
                t.sock._rl_list = []
                t.sock._rl_list_sz = 0
                t.sock._rl_pending = t.sock._rl_pending[nl:]
                #~ print 'return t(p)', repr((t.buff, x_buff, t.sock._rl_pending))
                return t
            else:
                t.sock._rl_list.append(t.sock._rl_pending)
                t.sock._rl_list_sz += len(t.sock._rl_pending)
                t.sock._rl_pending = ''
        t.check_overflow()
                
        x_buff, t.addr = t.sock.recvfrom(t.len-t.sock._rl_list_sz)
        nl = x_buff.find("\n")
        if x_buff:
            if nl >= 0:
                nl += 1
                t.sock._rl_list.append(x_buff[:nl])
                t.buff = t.result = ''.join(t.sock._rl_list)
                t.sock._rl_list = []
                t.sock._rl_list_sz = 0
                t.sock._rl_pending = x_buff[nl:]
                
                return t
            else:
                t.sock._rl_list.append(x_buff)
                t.sock._rl_list_sz += len(x_buff)
                t.check_overflow()
        else: 
            raise events.ConnectionClosed()
    def __repr__(t):
        return "<%s at 0x%X %s P:%r L:%r S:%r B:%r to:%s>" % (t.__class__.__name__, id(t), t.sock, t.sock._rl_pending, t.sock._rl_list, t.sock._rl_list_sz, t.buff, t.timeout)

class Write(WriteOperation):
    __slots__ = ['sock','sent','buff','prio','result']
    def __init__(t, sock, buff, timeout=None, prio=priority.DEFAULT):
        assert isinstance(sock, WrappedSocket)
        t.sock = sock
        t.buff = buff
        t.sent = 0
        t.timeout = timeout
        t.prio = prio
    def run(t):
        t.sent = t.result = t.sock.send(t.buff)
        return t
    def __repr__(t):
        return "<%s at 0x%X %s S:%r B:%r to:%s>" % (t.__class__.__name__, id(t), t.sock, t.sent, t.buff, t.timeout)
        
class WriteAll(WriteOperation):
    __slots__ = ['sock','sent','buff','prio']
    def __init__(t, sock, buff, timeout=None, prio=priority.DEFAULT):
        assert isinstance(sock, WrappedSocket)
        t.sock = sock
        t.buff = buff
        t.sent = 0
        t.timeout = timeout
        t.prio = prio
    def run(t):
        sent = t.sock.send(buffer(t.buff,t.sent))
        t.sent += sent
        if t.sent == len(t.buff):
            t.result = t.sent
            return t
    def __repr__(t):
        return "<%s at 0x%X %s S:%r B:%r to:%s>" % (t.__class__.__name__, id(t), t.sock, t.sent, t.buff, t.timeout)
 
class Accept(ReadOperation):
    __slots__ = ['sock','conn','prio','addr','result']
    def __init__(t, sock, timeout=None, prio=priority.DEFAULT):
        assert isinstance(sock, WrappedSocket)
        t.sock = sock
        t.conn = None
        t.timeout = timeout
        t.prio = prio
    def run(t):
        t.conn, t.addr = t.sock.accept()
        t.conn = WrappedSocket(_sock=t.conn)
        t.conn.setblocking(0)
        t.result = t.conn, t.addr
        return t
    def result(t):
        return (t.conn, t.addr)
    def __repr__(t):
        return "<%s at 0x%X %s conn:%r to:%s>" % (t.__class__.__name__, id(t), t.sock, t.conn, t.timeout)
             
class Connect(WriteOperation):
    __slots__ = ['sock','addr','prio']
    def __init__(t, sock, addr, timeout=None, prio=priority.DEFAULT):
        assert isinstance(sock, WrappedSocket)
        t.sock = sock
        t.addr = addr
        t.timeout = timeout
        t.prio = prio
    def run(t):
        """ 
        We need to avoid some non-blocking socket connect quirks: 
            if you attempt a connect in NB mode you will always 
            get EWOULDBLOCK, presuming the addr is correct.
        """
        err = t.sock.connect_ex(t.addr)
        if err:
            if err in (errno.EAGAIN, errno.EWOULDBLOCK, errno.EINPROGRESS):
                try:
                    t.sock.getpeername()
                except socket.error, exc:
                    if exc[0] == errno.ENOTCONN:
                        raise
            else:
                raise socket.error(err, errno.errorcode[err])
        return t
    def __repr__(t):
        return "<%s at 0x%X %s to:%s>" % (t.__class__.__name__, id(t), t.sock, t.timeout)

#~ ops = (Read, ReadAll, ReadLine, Connect, Write, WriteAll, Accept)
#~ read_ops = (Read, ReadAll, ReadLine, Accept)
#~ write_ops = (Connect, Write, WriteAll)
