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
        
class SimpleAppTest_Prio(SimpleAppTest_MixIn, WebTest_Base, PrioMixIn, unittest.TestCase):
    pass
class SimpleAppTest_NoPrio(SimpleAppTest_MixIn, WebTest_Base, NoPrioMixIn, unittest.TestCase):
    pass
        
if __name__ == "__main__":
    sys.argv.insert(1, '-v')
    unittest.main()