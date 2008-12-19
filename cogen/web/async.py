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
from cogen.core.coroutines import coro

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

class COGENSimpleWrapper(object):
    def __init__(self, gate):
        self.gate = gate
        
    def __call__(self, obj):
        self.gate.operation = obj

class COGENOperationCall(object):
    def __init__(self, gate, obj):
        self.gate = gate
        self.obj = obj
        
    def __call__(self, *args, **kwargs):
        self.gate.operation = self.obj(*args, **kwargs)
        return ""
class COGENProxy:
    __slots__ = (
        'content_length', 'read_count', 'operation', 'result', 'exception'
    )
    
    def __init__(self, content_length=None, read_count=None, operation=None, result=None, exception=None):
        self.content_length = content_length
        self.read_count = read_count
        self.operation = operation
        self.result = result
        self.exception = exception
        
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
        remaining = content_length = environ['cogen.wsgi'].content_length or 0
        while remaining:
            yield environ['cogen.input'].read(min(remaining, self.buffer_length))
            result = environ['cogen.wsgi'].result
            if isinstance(result, Exception):
                import traceback
                traceback.print_exception(*environ['cogen.wsgi'].exception)
                break
            else:
                if not result:
                    break
                buff.write(result)
                remaining -= len(result)
        buff.seek(0)
        environ['wsgi.input'] = buff
        environ['CONTENT_LENGTH'] = str(content_length)
        iterator = self.app(environ, start_response)
        for i in iterator:
            yield i
        if hasattr(iterator, 'close'): 
            iterator.close()

sync_input = SynchronousInputMiddleware

