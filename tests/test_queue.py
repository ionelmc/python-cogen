__doc_all__ = []

import unittest
import sys
import exceptions
import datetime

from cStringIO import StringIO

from cogen.common import *
from cogen.core import queue
from base import priorities
from cogen.core.util import priority

class QueueTest_MixIn:
    def setUp(self):
        self.m = Scheduler(default_priority=self.prio)
        self.msgs = []
        
    def tearDown(self):
        pass
    def test_signal_1s2w(self):
        @coroutine
        def signalee():
            self.msgs.append(2)
            yield events.WaitForSignal("test_sig")
            self.msgs.append(5)
        @coroutine
        def second_signalee():
            self.msgs.append(3)
            yield events.Sleep(1)
            self.msgs.append(4)
            yield events.WaitForSignal("test_sig")
            self.msgs.append(6)
        
        @coroutine
        def signaler():
            self.msgs.append(1)
            yield events.Signal("test_sig", recipients=2)
            self.msgs.append(7)
            
        self.m.add(signaler)
        self.m.add(signalee)
        self.m.add(second_signalee)
        self.m.run()
        if self.prio == priority.FIRST:
            self.assertEqual(self.msgs, [1,2,3,4,7,6,5])
        elif self.prio == priority.OP:
            self.assertEqual(self.msgs, [1,2,3,4,6,5,7])
        elif self.prio == priority.CORO:
            self.assertEqual(self.msgs, [1,2,3,4,7,5,6])
        else:
            self.assertEqual(self.msgs, [1,2,3,4,5,6,7])
    def test_queue(self):
        SIZE = 20
        q = queue.Queue(SIZE)
        self.msgs = []
        @coroutine
        def foo():
            for i in xrange(SIZE):
                yield q.put(i)
            thrown = False
            try:
                yield q.put_nowait('x')
            except queue.Full:
                thrown = True
            self.assertEqual(range(SIZE), list(q.queue))
            self.assertEqual(thrown, True)
            
            yield q.put(SIZE)
            self.msgs.append(-1)
            
            
        @coroutine
        def bar():
            yield events.Sleep(1)
            while 1:
                try:
                    el = yield q.get(timeout=0.1)
                    self.msgs.append(el)
                except events.OperationTimeout:
                    self.msgs.append(-2)
                    break
                
        @coroutine
        def wait():
            yield events.Sleep(2)
            
        self.m.add(foo)
        self.m.add(wait)
        self.m.add(bar)
        
        self.m.run()
        if self.prio & priority.CORO:
            self.assertEqual(self.msgs, [-1] + range(SIZE+1) + [-2])
        else:
            self.assertEqual(self.msgs, range(SIZE+1) + [-1, -2])
            
    def test_queue_timo(self):
        q = queue.Queue(50)
        self.msgs = []
        @coroutine
        def get():
            #~ while 1:
            self.msgs.append((yield q.get(timeout=0.1)))
            self.msgs.append((yield q.get(timeout=0.1)))
            self.msgs.append((yield q.get()))

        @coroutine
        def put():
            yield q.put(1)
            yield events.Sleep(1)
            yield q.put(2)

        m = Scheduler(proactor_resolution=0.5)
        m.add(put)
        m.add(get)
        sys.stderr = StringIO()
        m.run()
        self.assert_('OperationTimeout:' in sys.stderr.getvalue())
        sys.stderr = sys.__stderr__
        
        self.assertEqual(self.msgs, [1])
        self.assertEqual(list(q.queue), [2])

    def test_join(self):
        for i in xrange(1,6):
            SIZE = i
            q = queue.Queue(SIZE)
            self.msgs = []
            self.blevel = 0
            self.wlevel = 0
            @coroutine
            def worker(n):
                #~ print 'worka'
                while 1:
                    try:
                        el = yield q.get(timeout=0.1)
                    except events.OperationTimeout:
                        break
                    self.wlevel -= 1
                
                    self.msgs.append(1)
                    yield events.Sleep(0.01)
                    yield q.task_done()
                self.msgs.append(2)
                
                
            @coroutine
            def boss(n):
                self.blevel += 1
                yield q.put(1)
                
                self.blevel += 1
                yield q.put(2)
                
                self.blevel += 1
                yield q.put(3)
                
                self.msgs.append(1)
                yield q.join()
                self.msgs.append(2)
            @coroutine
            def daemon():
                yield events.Sleep(1)
            self.m.add(worker, args=(1,))
            self.m.add(worker, args=(2,))
            self.m.add(worker, args=(3,))
            self.m.add(boss, args=(-1,))
            self.m.add(boss, args=(-2,))
            self.m.add(daemon)
            self.m.run()
            
            self.assertEqual([1, 1, 1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2], self.msgs) 
            self.assertEqual(-self.wlevel, self.blevel)

for prio_mixin in priorities:
    name = 'QueueTest_%s' % prio_mixin.__name__
    globals()[name] = type(
        name, (QueueTest_MixIn, prio_mixin, unittest.TestCase), {}
    )

if __name__ == "__main__":
    sys.argv.insert(1, '-v')
    unittest.main()
