__doc_all__ = []

import unittest
import sys
import exceptions
import datetime

from cStringIO import StringIO

from cogen.common import *
from cogen.core import pubsub
from cogen.core.util import priority
from base import priorities

class QueueTest_MixIn:
    def setUp(self):
        self.m = Scheduler(default_priority=self.prio)
        self.msgs = []
        
    def tearDown(self):
        pass

    def test_pubsub(self):
        q = pubsub.PublishSubscribeQueue()
        self.msgs = []
        @coroutine
        def foo():
            yield q.subscribe()
            while 1:
                try:
                    val = yield q.fetch(timeout=0.1)
                    self.msgs.extend(val)
                except events.OperationTimeout:
                    self.msgs.append('OK')
                    yield events.Signal('lazy')
                    break
        @coroutine
        def lazy_foo():
            yield q.subscribe()
            yield events.WaitForSignal('lazy')
            while 1:
                try:
                    val = yield q.fetch(timeout=0.1)
                    self.msgs.extend(val)
                except events.OperationTimeout:
                    break
        @coroutine
        def bar():
            for i in range(5):
                yield q.publish(i)
        self.m.add(lazy_foo)
        self.m.add(foo)
        self.m.add(bar)
        self.m.run()
        self.assertEqual(self.msgs, [0,1,2,3,4,'OK',0,1,2,3,4])
    def test_compact(self):
        q = pubsub.PublishSubscribeQueue()
        self.msgs = []
        @coroutine
        def lazy_foo():
            yield events.WaitForSignal('lazy')
            yield q.subscribe()
            while 1:
                try:
                    val = yield q.fetch(timeout=0.1)
                    self.msgs.extend(val)
                except events.OperationTimeout:
                    break
        @coroutine
        def bar():
            for i in range(5):
                yield q.publish(i)
                if i==2:
                    q.compact()
                    yield events.Signal('lazy')
        self.m.add(lazy_foo)
        self.m.add(bar)
        self.m.run()
        self.assertEqual(self.msgs, [3,4])
    def test_compact2(self):
        q = pubsub.PublishSubscribeQueue()
        self.msgs = []
        @coroutine
        def lazy_foo():
            yield q.subscribe()
            while 1:
                try:
                    val = yield q.fetch(timeout=0.1)
                    self.msgs.extend(val)
                except events.OperationTimeout:
                    break
        @coroutine
        def bar():
            for i in range(5):
                yield q.publish(i)
                if i==1:
                    yield events.AddCoro(lazy_foo, prio=priority.CORO)
                if i==2:
                    q.compact()
                    
        self.m.add(bar)
        self.m.run()
        self.assertEqual(self.msgs, [3,4])    

for prio_mixin in priorities:
    name = 'QueueTest_%s' % prio_mixin.__name__
    globals()[name] = type(
        name, (QueueTest_MixIn, prio_mixin, unittest.TestCase), {}
    )
    
if __name__ == "__main__":
    sys.argv.insert(1, '-v')
    unittest.main()
