import socket
import errno
import exceptions
import events
class WrappedSocket(socket.socket):
    __name__ = "Socket"
    """
        Wee need some additional buffers and stuff:
            rl_pending - for unchecked for linebreaks buffer
            rl_list - for checked for linebreaks buffers
            rl_list_sz - a cached size of the summed sizes of rl_list buffers
    """
    def __init__(t, *a, **k):
        socket.socket.__init__(t, *a, **k)
        t.rl_list = []
        t.rl_list_sz = 0
        t.rl_pending = ''
        t.desc = ''
    def __repr__(t):
        return '<socket at 0x%X>' % id(t)
    def __str__(t):
        return 'sock@0x%X' % id(t)
New = Socket = WrappedSocket

class Operation:
    def try_run(t):
        try:
            print "Operation.try_run(%s):"%t,
            result = t.run()
            print result
            return result
        except socket.error, exc:
            if exc[0] in (errno.EAGAIN, errno.EWOULDBLOCK): #errno.ECONNABORTED
                return None
            elif exc[0] == errno.EPIPE:
                raise events.ConnectionClosed()
            else:
                raise
        return t
class Read(Operation):
    """
        `len` is max read size, BUT, if if there are buffers from ReadLine return them first.
    """
    __slots__ = ['sock','len','buff','addr']
    def __init__(t, sock, len = 4096):
        t.sock = sock
        t.len = len
    def run(t):
        if t.sock.rl_list:
            t.sock.rl_pending = ''.join(t.sock.rl_list) + t.sock.rl_pending
            t.sock.rl_list = []
        if t.sock.rl_pending: # XXX tofix
            t.buff = sock.rl_pending
            t.addr = None
            t.sock.rl_pending = ''
            return t
        else:
            t.buff, t.addr = t.sock.recvfrom(t.len)
            if t.buff:
                return t
            else:
                raise events.ConnectionClosed()
    def __repr__(t):
        return "<%s at 0x%X %s P:%r L:%r B:%r>" % (t.__class__.__name__, id(t), t.sock, t.sock.rl_pending, t.sock.rl_list, t.buff)
        
class ReadAll(Operation):
    __slots__ = ['sock','len','buff','addr']
    def __init__(t, sock, len = 4096):
        t.sock = sock
        t.len = len
    def run(t):
        if t.sock.rl_pending:
            t.sock.rl_list.append(t.sock.rl_pending) 
                # we push in the buff list the pending buffer (for the sake of simplicity and effieciency)
                # but we loose the linebreaks in the pending buffer (i've assumed one would not try to use readline 
                #     while using read all, but he would use readall after he would use readline)
            t.sock.rl_list_sz += len(t.sock.rl_pending)
            t.sock.rl_pending = ''
        if t.sock.rl_list_sz < t.len:
            buff, t.addr = t.sock.recvfrom(t.len-t.sock.rl_list_sz)
            if buff:
                t.sock.rl_list.append(buff)
                t.sock.rl_list_sz += len(buff)
            else:
                raise events.ConnectionClosed()
        if t.sock.rl_list_sz == t.len:
            t.buff = ''.join(t.sock.rl_list)
            t.sock.rl_list = []
            return t
        else: # damn ! we still didn't recv enough
            return
    def __repr__(t):
        return "<%s at 0x%X %s P:%r L:%r S:%r B:%r>" % (t.__class__.__name__, id(t), t.sock, t.sock.rl_pending, t.sock.rl_list, t.sock.rl_list_sz, t.buff)
        
class ReadLine(Read):
    """
        `len` is the max size for a line
    """
    __slots__ = ['sock','len','buff','addr']
    def __init__(t, sock, len = 4096):
        t.sock = sock
        t.len = len
        t.buff = None
    def check_overflow(t):
        if t.sock.rl_list_sz>=t.len: 
            #~ rl_list    = t.sock.rl_list   
            #~ rl_list_sz = t.sock.rl_list_sz
            #~ rl_pending = t.sock.rl_pending
            t.sock.rl_list    = []
            t.sock.rl_list_sz = 0
            t.sock.rl_pending = ''
            raise exceptions.OverflowError("Recieved %s bytes and no linebreak" % t.len)
    def run(t):
        #~ print '>',t.sock.rl_list_sz
        if t.sock.rl_pending:
            nl = t.sock.rl_pending.find("\n")
            if nl>=0:
                nl += 1
                t.buff = ''.join(t.sock.rl_list)+t.sock.rl_pending[:nl]
                t.sock.rl_list = []
                t.sock.rl_list_sz = 0
                t.sock.rl_pending = t.sock.rl_pending[nl:]
                #~ print 'return t(p)', repr((t.buff, x_buff, t.sock.rl_pending))
                return t
            else:
                t.sock.rl_list.append(t.sock.rl_pending)
                t.sock.rl_list_sz += len(t.sock.rl_pending)
                t.sock.rl_pending = ''
        t.check_overflow()
                
        x_buff, t.addr = t.sock.recvfrom(t.len-t.sock.rl_list_sz)
        nl = x_buff.find("\n")
        if x_buff:
            if nl >= 0:
                nl += 1
                t.sock.rl_list.append(x_buff[:nl])
                t.buff = ''.join(t.sock.rl_list)
                t.sock.rl_list = []
                t.sock.rl_list_sz = 0
                t.sock.rl_pending = x_buff[nl:]
                
                return t
            else:
                t.sock.rl_list.append(x_buff)
                t.sock.rl_list_sz += len(x_buff)
                t.check_overflow()
        else: 
            raise events.ConnectionClosed()
    def __repr__(t):
        return "<%s at 0x%X %s P:%r L:%r S:%r B:%r>" % (t.__class__.__name__, id(t), t.sock, t.sock.rl_pending, t.sock.rl_list, t.sock.rl_list_sz, t.buff)

class Write(Operation):
    __slots__ = ['sock','sent','buff']
    def __init__(t, sock, buff):
        t.sock = sock
        t.buff = buff
        t.sent = 0
    def run(t):
        t.sent = t.sock.send(t.buff)
        return t
    def __repr__(t):
        return "<%s at 0x%X %s S:%r B:%r>" % (t.__class__.__name__, id(t), t.sock, t.sent, t.buff)
        
class WriteAll(Operation):
    __slots__ = ['sock','sent','buff']
    def __init__(t, sock, buff):
        t.sock = sock
        t.buff = buff
        t.sent = 0
    def run(t):
        sent = t.sock.send(buffer(t.buff,t.sent))
        t.sent += sent
        if t.sent == len(t.buff):
            return t
    def __repr__(t):
        return "<%s at 0x%X %s S:%r B:%20r>" % (t.__class__.__name__, id(t), t.sock, t.sent, t.buff)
 
class Accept(Operation):
    __slots__ = ['sock','conn']
    def __init__(t, sock):
        t.sock = sock
        t.conn = None
    def run(t):
        t.conn, t.addr = t.sock.accept()
        t.conn = WrappedSocket(_sock=t.conn)
        t.conn.setblocking(0)
        return t
    def __repr__(t):
        return "<%s at 0x%X %s conn:%r>" % (t.__class__.__name__, id(t), t.sock, t.conn)
             
class Connect(Operation):
    __slots__ = ['sock','addr']
    def __init__(t, sock, addr):
        t.sock = sock
        t.addr = addr
    def run(t):
        t.sock.connect(t.addr)
        return t
    def __repr__(t):
        return "<%s at 0x%X %s>" % (t.__class__.__name__, id(t), t.sock)

ops = (Read, ReadAll, ReadLine, Connect, Write, WriteAll, Accept)
read_ops = (Read, ReadAll, ReadLine, Accept)
write_ops = (Connect, Write, WriteAll)
