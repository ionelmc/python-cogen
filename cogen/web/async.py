"""
cogen.web.wsgi server is asynchronous by default. If you need to run a app that
uses wsgi.input synchronously you need to wrapp it in 
`SynchronousInputMiddleware <cogen.web.async.SynchronousInputMiddleware.html>`_.

Wsgi asynchronous api only provides a read operation at the moment. Here's a
example:

.. sourcecode:: python

    buff = StringIO()
    while 1:
        yield environ['cogen.input'].Read(self.buffer_length)
        result = environ['cogen.wsgi'].result
        if isinstance(result, Exception):
            import traceback
            traceback.print_exception(*environ['cogen.wsgi'].exception)
            break
        else:
            if not result:
                break
            buff.write(result)
    buff.seek(0)
    # ...
    # do something with the data
    # ...
"""
__all__ = [
    'LazyStartResponseMiddleware', 'SynchronousInputMiddleware', 'Read',
    'ReadLine'
]


from cogen.core import sockets
from cogen.core.util import debug
from cStringIO import StringIO

class COGENOperationWrapper(object):
    def __init__(self, gate, module):
        self.module = module
        self.gate = gate
        
    def __getattr__(self, key):
        #~ if callable(self.module):
            #~ return COGENOperationCall(self.gate, self.module)
        what = getattr(self.module, key)
        if callable(what):
            return COGENOperationCall(self.gate, what)
        else:
            return self.__class__(self.gate, what)
class COGENCallWrapper(object):
    def __init__(self, gate):
        self.gate = gate
        
    def __call__(self, obj):
        return COGENOperationCall(self.gate, obj)

class COGENOperationCall(object):
    def __init__(self, gate, obj):
        self.gate = gate
        self.obj = obj
        
    def __call__(self, *args, **kwargs):
        self.gate.operation = self.obj(*args, **kwargs)
        return ""
class COGENProxy:
    def __init__(self, **kws):
        self.__dict__.update(kws)
    def __str__(self):
        return repr(self.__dict__)

class LazyStartResponseMiddleware:
    """This is a evil piece of middleware that proxyes the start_response
    call and delays it till the appiter yields a non-empty string.
    Also, this returns a fake write callable that buffers the strings passed
    though it.
    """
    def __init__(self, app, global_conf={}):
        self.app = app
        self.sr_called = False
        
    def start_response(self, status, headers, exc=None):
        self.sr_called = True
        self.status = status
        self.headers = headers
        self.exc = exc
        self.out = StringIO()
        return self.out.write
    
    def __call__(self, environ, start_response):
        started = False
        app_iter = self.app(environ, self.start_response)
        for chunk in app_iter:
            if not started and self.sr_called and chunk:
                started = True
                write = start_response(self.status, self.headers, self.exc)
                out = self.out.getvalue()
                if out:
                    write(out)
            yield chunk
        if not started and self.sr_called:
            start_response(self.status, self.headers, self.exc)
lazy_sr = LazyStartResponseMiddleware

class SynchronousInputMiddleware:
    """Middleware for providing a regular synchronous wsgi.input to the app.
    Note that it reads the whole input in memory so you sould rather use the
    async input (environ['cogen.input']) for large requests.
    """
    __doc_all__ = ['__call__']
    def __init__(self, app, global_conf={}, buffer_length=1024):
        self.app = app
        self.buffer_length = int(buffer_length)

    def __call__(self, environ, start_response):
        buff = StringIO()
        length = 0
        while 1:
            yield environ['cogen.input'].Read(self.buffer_length)
            result = environ['cogen.wsgi'].result
            if isinstance(result, Exception):
                import traceback
                traceback.print_exception(*environ['cogen.wsgi'].exception)
                break
            else:
                if not result:
                    break
                buff.write(result)
                length += len(result)
        buff.seek(0)
        environ['wsgi.input'] = buff
        environ['CONTENT_LENGTH'] = str(length)
        iterator = self.app(environ, start_response)
        for i in iterator:
            yield i
        if hasattr(iterator, 'close'): 
            iterator.close()

sync_input = SynchronousInputMiddleware

class Read(sockets.ReadAll, sockets.ReadLine):
    """This is actually a hack that mixes ReadAll and ReadLine and 
    patches their state attributes. Hopefully i'll evolve it to
    something more elegant at some point."""
    __slots__ = ['req', 'x_len', 'x_buff', 'x_buff_sz', 'x_ck_sz']
    NEED_SIZE = 0
    NEED_CHUNK = 1
    NEED_TERM = 2
    NEED_HEAD = 3
    NEED_NONE = 4
    def __init__(self, conn, req, len = 4096, **kws):
        """Initial `req` object holds the state of the operations involving
        reading the input and it requires to have these attributes:
        
        * read_chunked = <bool>
        * content_length = <int>
        * read_count = 0
        * state = async.Read.NEED_SIZE
        
        These have to be initialized in the request.
        """
        #check if requested length doesn't excede content-length
        if not req.read_chunked and req.content_length and \
                req.read_count + len > req.content_length:
            len = req.content_length - req.read_count
        
        super(self.__class__, self).__init__(conn, len, **kws)
        self.x_len = len
        self.x_buff = []
        self.x_buff_sz = 0
        self.x_ck_sz = 0
        self.req = req
    
    #~ @debug(0)        
    def run(self, reactor):
        if self.req.read_chunked:
            again = 1
            while again:
                again = 0
                if self.req.state == self.NEED_SIZE:
                    self.len = self.x_len
                    ret = sockets.ReadLine.run(self, reactor)
                    if ret:
                        self.req.state = self.NEED_CHUNK
                        chunk_len = int(self.buff.split(';',1)[0], 16)
                        if chunk_len:
                            if self.x_len - self.x_buff_sz > chunk_len:
                                # the requested read span over this chunk so we
                                # might need to buffer several chunks
                                self.len = chunk_len
                            else:
                                # if we've read more that 1 chunk allready substract
                                # what we've read so far
                                self.len = self.x_len - self.x_buff_sz
                            self.req.chunk_remaining = chunk_len
                        else:
                            self.req.state = self.NEED_NONE
                            if self.x_buff:
                                self.buff = ''.join(self.x_buff)
                                self.x_buff = []
                                self.x_buff_sz = 0
                                self.req.read_count += len(self.buff)
                                return self
                            
                        again = 1
                        # else - we have enough space in the current chunk
                        
                elif self.req.state == self.NEED_CHUNK:
                    self.len = min( self.x_len - self.x_buff_sz, 
                                    self.req.chunk_remaining)
                    ret = sockets.ReadAll.run(self, reactor)
                    if ret:
                        self.x_buff.append(self.buff)
                        self.x_buff_sz += len(self.buff)
                        self.req.chunk_remaining -= len(self.buff)
                        self.buff = None # patching for base classes
                       
                        # if what we have in x_buff is not enough we need to 
                        # read more chunks
                        if self.x_buff_sz >= self.x_len:
                            assert self.x_buff_sz == self.x_len, \
                                    "Something is wrong here !"
                            self.buff = ''.join(self.x_buff)
                            self.x_buff = []
                            self.x_ck_sz -= self.x_buff_sz
                            self.x_buff_sz = 0
                            self.req.read_count += len(self.buff)
                            if not self.req.chunk_remaining:
                                self.len = self.x_len
                                self.req.state = self.NEED_TERM
                            return ret
                        else:
                            # oh my, we don't have enough data
                            self.len = self.x_len - self.x_buff_sz
                            self.req.state = self.NEED_TERM
                            again = 1
                elif self.req.state == self.NEED_TERM:
                    self.len = self.x_len
                    ret = sockets.ReadLine.run(self, reactor)
                    if ret:
                        assert ret.buff == '\r\n', \
                            "Chunk didn't end with a empty line (%r)!" % ret.buff
                        self.req.state = self.NEED_SIZE
                        self.buff = None
                        again = 1
                elif self.req.state == self.NEED_HEAD:
                    self.len = self.x_len
                    ret = sockets.ReadLine.run(self, reactor)
                    # we throw away the trailer headers
                    
                    if ret:
                        if ret.buff == '\r\n':
                            # empty line - end of headers, END
                            self.req.state = self.NEED_NONE
                            return ret
                        self.buff = None
                elif self.req.state == self.NEED_NONE:
                    self.buff = ''
                    return self
        else:
            # and all this chunking madness could had beed avoided !
            if self.req.content_length:
                if self.req.read_count >= self.req.content_length:
                    assert self.req.read_count == self.req.content_length, \
                            "read_count is greater than content_length !"
                    self.buff = ''
                    return self
                ret = sockets.ReadAll.run(self, reactor)
                if ret:
                    self.req.read_count += len(ret.buff)
                return ret
            else:
                self.buff = ''
                return self
                                
    def __repr__(self):
        return "<%s at 0x%X %s in STATE%s RQ.RD_CNT:%r RQ.CL:%r XBF:%s XLEN:%s XBF_SZ:%s RL_PND:%.100r RL_LIST:%r RL_LIST_SZ:%r BUFF:%r LEN:%s to:%s>" % (
            self.__class__.__name__, 
            id(self), 
            self.sock, 
            self.req.state,
            self.req.read_count,
            self.req.content_length,
            self.x_buff,
            self.x_len,
            self.x_buff_sz,
            
            self.sock._rl_pending, 
            self.sock._rl_list, 
            self.sock._rl_list_sz, 
            self.buff and self.buff[:self.trim], 
            self.len,
            self.timeout
        )
    def __str__(self):
        return repr(self)
        
class ReadLine(sockets.ReadAll, sockets.ReadLine):
    """
    Same a async.Read but doesn't work with chunked input (it would complicate
    things too much at the moment).
    """
    __slots__ = ['req']
    def __init__(self, conn, req, len = 4096, **kws):
        """Initial `req` object holds the state of the operations involving
        reading the input and it requires to have these attributes:
        
        * read_chunked = <bool>
        * content_length = <int>
        * read_count = 0
        * state = async.Read.NEED_SIZE
        
        These have to be initialized in the request.
        """
        #check if requested length doesn't excede content-length
        if not req.read_chunked and req.content_length and \
                req.read_count + len > req.content_length:
            len = req.content_length - req.read_count
        
        super(self.__class__, self).__init__(conn, len, **kws)
        self.req = req
    
    #~ @debug(0)        
    def run(self, reactor=True):
        if self.req.read_chunked:
            raise NotImplementedError("No readline for chunked input.")
        else:
            if self.req.content_length:
                if self.req.read_count >= self.req.content_length:
                    assert self.req.read_count == self.req.content_length, \
                            "read_count is greater than content_length !"
                    self.buff = ''
                    return self
                ret = sockets.ReadLine.run(self, reactor)
                if ret:
                    self.req.read_count += len(ret.buff)
                return ret
            else:
                self.buff = ''
                return self