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
import os
import tempfile
import socket
from cStringIO import StringIO

from cogen.common import *
from cogen.core.util import debug
from cogen.web import wsgi, async

from base import priorities, proactors_available
from base_web import WebTest_Base

 

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
        
class LazyStartResponseTest_MixIn:
    middleware = [async.lazy_sr]
    def app(self, environ, start_response):
        start_response('200 OK', [('Content-type','text/html')])
        return ['']
        
    def test_app(self):
        #~ self.conn.set_debuglevel(100)
        socket.setdefaulttimeout(5)
        self.conn = httplib.HTTPConnection(*self.local_addr)
        self.conn.connect()
        self.conn.request('GET', '/')
        resp = self.conn.getresponse().read()
        socket.setdefaulttimeout(None)        
        self.assertEqual(resp, '')
        
class InputTest_MixIn:
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
        
    def test_nonchunked(self):
        for PSIZE in [10, 100, 1000, 1024]:
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
        self.result = buff.getvalue()
        yield 'read'
    def readline_app(self, environ, start_response):
        buff = StringIO()
        remaining = content_length = environ['cogen.wsgi'].content_length or 0
        while remaining:
            yield environ['cogen.input'].readline(min(remaining, self.buffer_length))
            result = environ['cogen.wsgi'].result
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
                remaining -= len(result)
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
        for buffer_length in [10, 100, 400]:
            self.buffer_length = buffer_length
            self.result = None
            data = self.make_str(3, 400, chunked=False)
            expectdata = self.make_str(3, 400, chunked=False)
            self.conn.request('GET', '/read', data, {"Content-Length": str(len(data))})
            resp = self.conn.getresponse()
            recvdata = resp.read()
            self.assertEqual(recvdata, 'read')
            self.assertEqual(self.result, expectdata)
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

class FileWrapperTest_MixIn:
    CKSIZE = 300
    POS = 100
    DIFF = CKSIZE-POS
    val = os.urandom(CKSIZE)
    middleware = []
    def app(self, environ, start_response):
        tfile = tempfile.TemporaryFile()
        tfile.write(self.val)
        tfile.seek(self.POS)
        sz, cl = environ['PATH_INFO'].lstrip('/').split('/')
        headers = [('Content-type','application/octet-stream')]
        if cl:
            headers.append(('Content-length', str(self.DIFF)))
        start_response('200 OK', headers)
        return environ['wsgi.file_wrapper'](tfile, int(sz))
        
      
    def test_http10_conn_close(self):
        for sz in [10, 100, 300]:
            #~ print 'SZ:', sz
            self.conn = httplib.HTTPConnection(*self.local_addr)
            self.conn.connect()
            self.conn._http_vsn = 10
            self.conn._http_vsn_str = 'HTTP/1.0'
            self.conn.auto_open = 0
            self.conn.request('GET', '/%s/'%sz)
            resp = self.conn.getresponse()
            recvdata = resp.read()
            self.assertEqual(len(recvdata), self.DIFF)
            self.assert_(recvdata == self.val[self.POS:])
            try:
                self.conn.request('GET', '/%s/'%sz, headers={})
            except httplib.NotConnected:
                pass
            else:
                self.failIf("Connection not closed!")
    def test_http10_kalive(self):
        for sz in [10, 100, 300]:
            self.conn._http_vsn = 10
            self.conn._http_vsn_str = 'HTTP/1.0'
            self.conn.auto_open = 0
            self.conn.request('GET', '/%s/cl'%sz, headers={'Connection': 'keep-alive'})
            resp = self.conn.getresponse()
            recvdata = resp.read()
            self.assertEqual(len(recvdata), self.DIFF)
            self.assert_(recvdata == self.val[self.POS:])
        try:
            self.conn.request('GET', '/%s/'%sz, headers={})
        except httplib.NotConnected:
            self.failIf("Connection closed!")
    
    def test_http11_kalive(self):
        # should use chunking
        for sz in [10, 100, 300]:
            self.conn.auto_open = 0
            self.conn.request('GET', '/%s/'%sz)
            resp = self.conn.getresponse()
            self.assertEqual(resp.chunked, 1)
            recvdata = resp.read()
            self.assertEqual(len(recvdata), self.DIFF)
            self.assert_(recvdata == self.val[self.POS:])
        try:
            self.conn.request('GET', '/%s/'%sz, headers={})
        except httplib.NotConnected:
            self.failIf("Connection closed!")
    
    def test_http11_conn_close(self):
        for sz in [10, 100, 300]:
            self.conn = httplib.HTTPConnection(*self.local_addr)
            self.conn.connect()
            self.conn.auto_open = 0
            self.conn.request('GET', '/%s/cl'%sz, headers={'Connection': 'close'})
            resp = self.conn.getresponse()
            self.assertEqual(resp.chunked, 0)
            recvdata = resp.read()
            self.assertEqual(len(recvdata), self.DIFF)
            self.assert_(recvdata == self.val[self.POS:])
            try:
                self.conn.request('GET', '/%s/'%sz, headers={})
            except httplib.NotConnected:
                pass
            else:
                self.failIf("Connection not closed!")
        
import cogen
#~ for poller_cls in [cogen.core.proactors.has_select()]:#proactors_available:
for poller_cls in proactors_available:
    for prio_mixin in priorities:
        
        name = 'LazyStartResponseTest_%s_%s' % (prio_mixin.__name__, poller_cls.__name__)
        globals()[name] = type(
            name, 
            (LazyStartResponseTest_MixIn, WebTest_Base, prio_mixin, unittest.TestCase),
            {'poller':poller_cls}
        )
        name = 'FileWrapperTest_%s_%s' % (prio_mixin.__name__, poller_cls.__name__)
        globals()[name] = type(
            name, 
            (FileWrapperTest_MixIn, WebTest_Base, prio_mixin, unittest.TestCase),
            {'poller':poller_cls}
        )
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