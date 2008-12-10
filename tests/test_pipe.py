__doc_all__ = []

import unittest
import sys
import exceptions
import datetime

from cStringIO import StringIO

from cogen.common import *
from base import priorities
from cogen.core.util import priority
from cogen.core.pipe import chunk, Iterate, sentinel

class PipeTest(unittest.TestCase):
    def setUp(self):
        self.m = Scheduler()
        self.msgs = []
        
    def tearDown(self):
        pass
    def test_iter(self):
        put = self.msgs.append
        
        @coroutine
        def iterable():
            put('started')
            assert not (yield chunk(1))
            assert not (yield chunk(2))
            assert not (yield chunk(3))
            yield events.WaitForSignal("test_sig")
            put('sig')
            assert not (yield chunk(None))
            assert not (yield chunk(sentinel))
            yield events.WaitForSignal("test_sig2")
            put('sig2')
        @coroutine
        def sig1(n):
            yield events.Signal(n)
        @coroutine
        def iterator():
            it = yield Iterate(iterable)
            while 1:
                val = yield it
                if val is sentinel:
                    put('end')
                    break
                put(val)
                if val == 3:
                    yield events.AddCoro(sig1, args=("test_sig",))
                if val == 'xxx':
                    yield events.AddCoro(sig1, args=("test_sig2",))
                
        self.m.add(iterator)
        self.m.run()
        
        self.assertEqual(self.msgs, ['started', 1, 2, 3, 'sig', None, 'end'])
        
    

if __name__ == "__main__":
    sys.argv.insert(1, '-v')
    unittest.main()