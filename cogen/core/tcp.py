import socket
import errno

class Connection(object):
    """
        Wee need some additional buffers and stuff:
            rl_pending - for unchecked for linebreaks buffer
            rl_list - for checked for linebreaks buffers
            rl_list_sz - a cached size of the summed sizes of rl_list buffers
    """
    def __init__(t, sock):
        t.sock = sock
        t.rl_list = []
        t.rl_list_sz = 0
        t.rl_pending = ''
        t.ops = {}
        t.sent = 0

    def try_run(t, what):
        def callback():
            try:
                ret = what(t.ops[what])
                del t.ops[what]
                return ret or callback
            except socket.error, exc:
                if exc[0] in (errno.EAGAIN, errno.EWOULDBLOCK):
                    return callback
                else:
                    raise
        def wrapped(*a):
            t.ops[what] = a
            try:
                return what(*a) or callback
            except socket.error, exc:
                if exc[0] in (errno.EAGAIN, errno.EWOULDBLOCK):
                    return callback
                else:
                    raise
        return wrapped
    @t.try_run
    def read(t, len = 4096):
        """
            `len` is max read size, BUT, if if there are buffers from ReadLine return them first.
        """
        if t.sock.rl_list:
            t.sock.rl_pending = ''.join(t.sock.rl_list) + t.sock.rl_pending
            t.sock.rl_list = []
        if t.sock.rl_pending: # XXX tofix
            t.buff = sock.rl_pending
            t.addr = None
            t.sock.rl_pending = ''
            return t.buff, t.addr
        else:
            return t.sock.recvfrom(length)
    @t.try_run
    def readall(t, length = 4096):
        if t.sock.rl_pending:
            t.sock.rl_list.append(t.sock.rl_pending) 
                # we push in the buff list the pending buffer (for the sake of simplicity and effieciency)
                # but we loose the linebreaks in the pending buffer (i've assumed one would not try to use readline 
                #     while using read all, but he would use readall after he would use readline)
            t.sock.rl_list_sz += len(t.sock.rl_pending)
            t.sock.rl_pending = ''
        if t.sock.rl_list_sz < length:
            buff, t.addr = t.sock.recvfrom(length-t.sock.rl_list_sz)
            t.sock.rl_list.append(buff)
            t.sock.rl_list_sz += len(buff)
        if t.sock.rl_list_sz == length:
            t.buff = ''.join(t.sock.rl_list)
            t.sock.rl_list = []
            return t.buff
        else: # damn ! we still didn't recv enough
            return
    def check_rl_overflow(t, length):
        if t.sock.rl_list_sz >= length: 
            rl_list    = t.sock.rl_list   
            rl_list_sz = t.sock.rl_list_sz
            rl_pending = t.sock.rl_pending
            t.sock.rl_list    = []
            t.sock.rl_list_sz = 0
            t.sock.rl_pending = ''
            raise exceptions.OverflowError("Recieved %s bytes and no linebreak" % length)
    @t.try_run            
    def readline(t, length = 4096):
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
        t.check_rl_overflow(length)
                
        x_buff, t.addr = t.sock.recvfrom(length-t.sock.rl_list_sz)
        nl = x_buff.find("\n")
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
            t.check_rl_overflow(length)
    @t.try_run
    def write(t, buff):
        return t.sock.send(t.buff) #todo: what if it's 0 ?
    @t.try_run
    def writeall(t, buff):
        sent = t.sock.send(buffer(buff,t.sent))
        t.sent += sent
        if t.sent == len(buff):
            return t
    @t.try_run
    def accept(t):
        t.conn, t.addr = t.sock.accept()
        #~ t.conn = WrappedSocket(_sock=t.conn)
        t.conn.setblocking(0)
        return t.conn
    @t.try_run
    def connect(t, addr):
        t.sock.connect(addr)
        return t

