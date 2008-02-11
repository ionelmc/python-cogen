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
from cogen.web import wsgi, async

sys.setcheckinterval(0)


class WebTest_Base:
    middleware = [async.sync_input, wsgiref.validate.validator]
    def setUp(self):
        self.local_host = 'localhost'
        self.local_port = random.randint(10000,10010)
        print "http://localhost:%s/"%self.local_port
        def run():
            try:
                app = self.app
                while self.middleware:
                    app = self.middleware.pop()(app)
                wsgi.server_factory(
                    {}, 
                    self.local_host, 
                    self.local_port,
                    default_priority=self.prio
                )(app)
            except:
                import traceback
                traceback.print_exc()
        self.m_run = threading.Thread(target=run)
        self.m_run.start()
        time.sleep(0.1)
        self.conn = httplib.HTTPConnection(self.local_host, self.local_port)

    def tearDown(self):
        pass
        
        
