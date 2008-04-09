__doc_all__ = []

import unittest
import sys
import exceptions
import datetime
import time
import random
import threading
import wsgiref.validate
import httplib
from cStringIO import StringIO

from cogen.common import *
from cogen.core import reactors
from cogen.core.util import debug
from cogen.test.base import PrioMixIn, NoPrioMixIn
from cogen.web import wsgi, async
from cogen.test.base_web import WebTest_Base

 

class SimpleAppTest_MixIn:
    def app(self, environ, start_response):
        start_response('200 OK', [('Content-type','text/html')])
        self.header = environ['HTTP_X_TEST']
        return ['test-resp-body']
        
    def test_app(self):
        #~ self.conn.set_debuglevel(100)
        self.conn.request('GET', '/', '', {'X-Test': 'test-value'})
        resp = self.conn.getresponse()
        time.sleep(0.1)
        self.assertEqual(resp.read(), 'test-resp-body')
        self.assertEqual(self.header, 'test-value')
        
class InputTest_MixIn:
    #~ @debug(0)
    def app(self, environ, start_response):
        start_response('200 OK', [('Content-type','text/html')])
        return [environ['wsgi.input'].read()]
        
    def make_str(self, pieces, psize=1024*1024, chunked=True):
        f = StringIO()
        for i in xrange(pieces):
            val = chr(i+35)*psize
            
            if chunked: f.write(hex(len(val))[2:]+"\r\n")
            f.write(val)
            if chunked: f.write("\r\n")
        if chunked: f.write("0\r\n")            
        return f.getvalue()
        
    def test_chunked(self):
        for PSIZE in [1024, 10*1024, 10000, 5000, 12345]:
            SIZE = 10
            data = self.make_str(SIZE, PSIZE)
            self.conn.request('GET', '/', data, {"Transfer-Encoding": "chunked"})

            resp = self.conn.getresponse()
            recvdata = resp.read()
            expectdata = self.make_str(SIZE, PSIZE, chunked=False)
            self.assertEqual(recvdata, expectdata)
    def test_nonchunked(self):
        for PSIZE in [1024, 10*1024, 10000, 5000, 12345]:
            SIZE = 10
            data = self.make_str(SIZE, PSIZE, chunked=False)
            self.conn.request('GET', '/', data, {"Content-Length": str(len(data))})

            resp = self.conn.getresponse()
            recvdata = resp.read()
            self.assertEqual(recvdata, data)
            
        
        
class AsyncInputTest_MixIn:
    middleware = []
    def read_app(self, environ, start_response):
        buff = StringIO()
        length = 0
        while 1:
            yield environ['cogen.input'].Read(self.buffer_length)
            result = environ['cogen.wsgi'].result
            #~ print len(result)
            if isinstance(result, Exception):
                import traceback
                traceback.print_exception(*environ['cogen.wsgi'].exception)
                break
            else:
                if not result:
                    break
                buff.write(result)
                length += len(result)
        self.result = buff.getvalue()
        yield 'read'
        
    def readline_app(self, environ, start_response):
        buff = StringIO()
        length = 0
        while 1:
            yield environ['cogen.input'].ReadLine(self.buffer_length)
            result = environ['cogen.wsgi'].result
            #~ print 
            #~ print len(result), `result`
            if isinstance(result, Exception):
                if isinstance(result, OverflowError):
                    self.overflow = "overflow"
                else:
                    import traceback
                    traceback.print_exception(*environ['cogen.wsgi'].exception)
                
                break
            else:
                if not result:
                    break
                buff.write(result)
                length += len(result)
        self.result = buff.getvalue()
        yield 'readline'
        
    def app(self, environ, start_response):
        start_response('200 OK', [('Content-type','text/html')])
        
        if environ["PATH_INFO"] == '/read':
            return self.read_app(environ, start_response)
        elif environ["PATH_INFO"] == '/readline':
            return self.readline_app(environ, start_response)
        else:
            raise Exception('Unknown path_info')
    def make_str(self, pieces, psize=1024*1024, psep='', chunked=True):
        f = StringIO()
        for i in xrange(pieces):
            val = chr(i+35)*psize + psep
            
            if chunked: f.write(hex(len(val))[2:]+"\r\n")
            f.write(val)
            if chunked: f.write("\r\n")
        if chunked: f.write("0\r\n")            
        return f.getvalue()
    def test_read(self):
        for buffer_length in [123, 1234, 10, 1024, 10*1024]:
            self.buffer_length = buffer_length
            self.result = None
            data = self.make_str(10, 4000)
            expectdata = self.make_str(10, 4000, chunked=False)
            self.conn.request('GET', '/read', data, {"Transfer-Encoding": "chunked"})
            resp = self.conn.getresponse()
            recvdata = resp.read()
            self.assertEqual(self.result, expectdata)
            self.assertEqual(recvdata, 'read')
    def test_readline_overflow(self):
        self.buffer_length = 512
        data = self.make_str(1, 512, psep="\n", chunked=False)
        self.result = None
        self.overflow = None
        self.conn.request('GET', '/readline', data)
        resp = self.conn.getresponse()
        recvdata = resp.read()
        self.assertEqual(self.overflow, 'overflow')
        self.assertEqual(recvdata, 'readline')
    def test_readline(self):
        self.buffer_length = 512
        data = self.make_str(1, 256, psep="\n", chunked=False)
        self.result = None
        self.overflow = None
        self.conn.request('GET', '/readline', data)
        resp = self.conn.getresponse()
        recvdata = resp.read()
        self.assertEqual(self.overflow, None)
        self.assertEqual(self.result, data)
        self.assertEqual(recvdata, 'readline')

for poller_cls in reactors.available:
    for prio_mixin in (PrioMixIn, NoPrioMixIn):
        name = 'SimpleAppTest_%s_%s' % (prio_mixin.__name__, poller_cls.__name__)
        globals()[name] = type(
            name, 
            (SimpleAppTest_MixIn, WebTest_Base, prio_mixin, unittest.TestCase),
            {'poller':poller_cls}
        )
        
        name = 'InputTest_%s_%s' % (prio_mixin.__name__, poller_cls.__name__)
        globals()[name] = type(
            name, 
            (InputTest_MixIn, WebTest_Base, prio_mixin, unittest.TestCase),
            {'poller':poller_cls}
        )
        
        name = 'AsyncInputTest_%s_%s' % (prio_mixin.__name__, poller_cls.__name__)
        globals()[name] = type(
            name, 
            (AsyncInputTest_MixIn, WebTest_Base, prio_mixin, unittest.TestCase),
            {'poller':poller_cls}
        )

if __name__ == "__main__":
    sys.argv.insert(1, '-v')
    unittest.main()