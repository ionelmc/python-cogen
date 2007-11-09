import socket
import errno
import exceptions
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
New = WrappedSocket

class Operation: #(SimpleAttrib):
    def try_run(t):
        try:
            return t.run()
        except socket.error, exc:
            if exc[0] in (errno.EAGAIN, errno.EWOULDBLOCK):
                return None
            else:
                raise
        return t
class Read(Operation):
    """
        `len` is max read size, BUT, if if there are buffers from ReadLine return them first.
    """
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
            return t
class ReadAll(Operation):
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
            t.sock.rl_list.append(buff)
            t.sock.rl_list_sz += len(buff)
        if t.sock.rl_list_sz == t.len:
            t.buff = ''.join(t.sock.rl_list)
            t.sock.rl_list = []
            return t
        else: # damn ! we still didn't recv enough
            return
class ReadLine(Read):
    """
        `len` is the max size for a line
    """
    def __init__(t, sock, len = 4096):
        t.sock = sock
        t.len = len
    def check_overflow(t):
        if t.sock.rl_list_sz>=t.len: 
            rl_list    = t.sock.rl_list   
            rl_list_sz = t.sock.rl_list_sz
            rl_pending = t.sock.rl_pending
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
        if nl >= 0:
            nl += 1
            t.sock.rl_list.append(x_buff[:nl])
            t.buff = ''.join(t.sock.rl_list)
            t.sock.rl_list = []
            t.sock.rl_list_sz = 0
            t.sock.rl_pending = x_buff[nl:]
            #~ print 'return t', repr((t.buff, x_buff, t.sock.rl_pending)), t.len
            return t
        else:
            t.sock.rl_list.append(x_buff)
            t.sock.rl_list_sz += len(x_buff)
            t.check_overflow()

class Write(Operation):
    def __init__(t, sock, buff):
        t.sock = sock
        t.buff = buff
    def run(t):
        t.sent = t.sock.send(t.buff)
        return t
class WriteAll(Operation):
    def __init__(t, sock, buff):
        t.sock = sock
        t.buff = buff
        t.sent = 0
    def run(t):
        sent = t.sock.send(buffer(t.buff,t.sent))
        t.sent += sent
        if t.sent == len(t.buff):
            return t

class Accept(Operation):
    def __init__(t, sock):
        t.sock = sock
    def run(t):
        t.conn, t.addr = t.sock.accept()
        t.conn = WrappedSocket(_sock=t.conn)
        t.conn.setblocking(0)
        return t
            
class Connect(Operation):
    def __init__(t, sock, addr):
        t.sock = sock
        t.addr = addr
    def run(t):
        t.sock.connect(t.addr)
        return t

ops = (Read, ReadAll, ReadLine, Connect, Write, WriteAll, Accept)
read_ops = (Read, ReadAll, ReadLine, Accept)
write_ops = (Connect, Write, WriteAll)
