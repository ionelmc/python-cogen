__doc_all__ = []

import unittest
import sys
import exceptions
import datetime
import time

from cStringIO import StringIO

from cogen.common import *
from base import PrioMixIn, NoPrioMixIn

class SchedulerTest_MixIn:
    def setUp(self):
        self.m = Scheduler(default_priority=self.prio)
        self.msgs = []
        
    def tearDown(self):
        pass
    def test_signal(self):
        class X:
            pass
        x = X()
        @coroutine
        def signalee():
            self.msgs.append(1)
            yield events.WaitForSignal("test_sig")
            self.msgs.append(3)
            yield events.WaitForSignal(x)
            self.msgs.append(5)
        @coroutine
        def signaler():
            self.msgs.append(2)
            yield events.Signal("test_sig")
            self.msgs.append(4)
            yield events.Signal(x, recipients=1)
            self.msgs.append(6)
            
        self.m.add(signalee)
        self.m.add(signaler)
        self.m.run()
        if self.prio:
            self.assertEqual(self.msgs, [1,2,4,3,6,5])
        else:
            self.assertEqual(self.msgs, [1,2,3,4,5,6])
    def test_add_coro(self):
        @coroutine
        def added(x):
            self.msgs.append(x)
        @coroutine
        def adder(c):
            self.msgs.append(1)
            yield events.AddCoro(c, args=(self.prio and 3 or 2,))
            self.msgs.append(self.prio and 2 or 3)
        self.m.add(adder, args=(added,))
        self.m.run()
        self.assertEqual(self.msgs, [1,2,3])
    def test_call(self):
        @coroutine
        def caller():
            self.msgs.append(1)
            ret = yield events.Call(callee_1)
            self.msgs.append(ret)
            ret = yield events.Call(callee_2)
            self.msgs.append(ret is None and 3 or -1)
            try:
                ret = yield events.Call(callee_3)
            except Exception, e:
                self.msgs.append(e.message=='some_message' and 4 or -1)
             
            ret = yield events.Call(callee_4)
            self.msgs.append(ret)
            try:
                ret = yield events.Call(callee_5)
            except:
                import traceback
                s = traceback.format_exc()
                self.exc = s

            ret = yield events.Call(callee_6, args=(6,))
            self.msgs.append(ret)
            
        @coroutine
        def callee_1():
            raise StopIteration(2)
        @coroutine
        def callee_2():
            pass
        @coroutine
        def callee_3():
            yield
            raise Exception("some_message")
            yield
            
        @coroutine
        def callee_4():
            raise StopIteration((yield events.Call(callee_4_1)))
        @coroutine
        def callee_4_1():
            raise StopIteration((yield events.Call(callee_4_2)))
        @coroutine
        def callee_4_2():
            raise StopIteration(5)
        
        @coroutine
        def callee_5():
            raise StopIteration((yield events.Call(callee_5_1)))
        @coroutine
        def callee_5_1():
            raise StopIteration((yield events.Call(callee_5_2)))
        @coroutine
        def callee_5_2():
            raise Exception("long_one")
        
        @coroutine
        def callee_6(x):
            raise StopIteration(x)
            
        
        self.m.add(caller)
        self.m.run()
        self.assertEqual(self.msgs, [1,2,3,4,5,6])
        self.assert_('raise StopIteration((yield events.Call(callee_5_1)))' in self.exc)
        self.assert_('raise StopIteration((yield events.Call(callee_5_2)))' in self.exc)
        self.assert_('raise Exception("long_one")' in self.exc)
    def test_join(self):
        @coroutine
        def caller():
            self.msgs.append(1)
            ret = yield events.Join(self.m.add(callee_1))
            self.msgs.append(ret)
            ret = yield events.Join(self.m.add(callee_2))
            self.msgs.append(3 if ret is None else -1)
            #~ try:
            self.c = self.m.add(callee_3)
            sys.stderr = StringIO()
            #~ self.c.handle_error=lambda*a:None
            ret = yield events.Join(self.c)
            sys.stderr = sys.__stderr__
            self.msgs.append(
                4 
                if ret is None and self.c.exception[1].message=='some_message' 
                else -1
            )
            
            
        @coroutine
        def callee_1():
            raise StopIteration(2)
        @coroutine
        def callee_2():
            pass
        @coroutine
        def callee_3():
            yield
            raise Exception("some_message")
            yield
        self.m.add(caller)
        self.m.run()
        self.assertEqual(self.msgs, [1,2,3,4])
    def test_bad_ops(self):
        class HarmlessError(Exception):
            pass
        #~ class DoubleOperation(events.Sleep, events.TimedOperation):
            #~ def __init__(self, val=None, timestamp=None, **kws):
                #~ events.Sleep.__init__(self, val, timestamp)
                #~ events.TimedOperation.__init__(**kws)
        #TODO: add this too
        
        class ErrorOperation(events.TimedOperation):
            def process(self, sched, coro):
                super(ErrorOperation, self).process(sched, coro)
                raise HarmlessError
        self.botched = False
        @coroutine
        def worker():
            sticky_reference = ErrorOperation(timeout=0.01)
            try:
                yield sticky_reference
            except HarmlessError:
                pass
            else:
                self.botched = HarmlessError
            try:
                bla = yield events.Sleep(0.05)
            except:
                self.botched = sys.exc_info()
            bla = yield events.Sleep(0.05)

        @coroutine
        def monitor(coro):
            yield events.Join(coro)
        
        self.m.add(monitor, args=(self.m.add(worker),))
        
        self.m.run()
        self.assertEqual(self.botched, False)
    def test_sleep(self):
        self.sleept = False
        @coroutine
        def sleeper():
            #~ yield events.TimedOperation(timeout=1)
            yield events.Sleep(1)
            self.sleept = True
        ts = time.time()
        self.m.add(sleeper)
        self.m.run()
        self.assertAlmostEqual(time.time() - ts, 1.0, 2)
        self.assert_(self.sleept)
        
class SchedulerTest_Prio(SchedulerTest_MixIn, PrioMixIn, unittest.TestCase):
    pass
class SchedulerTest_NoPrio(SchedulerTest_MixIn, NoPrioMixIn, unittest.TestCase):
    pass

if __name__ == "__main__":
    sys.argv.insert(1, '-v')
    unittest.main()
    