__doc_all__ = []

import unittest
import random
import threading 
import socket
import sys
import time
import exceptions
import datetime
import traceback
import thread

from cogen.common import *
from cogen.core import reactors
from base import PrioMixIn, NoPrioMixIn

class Timer_MixIn:
    def setUp(self):
        self.local_addr = ('localhost', random.randint(19000,20000))
        self.m = Scheduler(default_priority=self.prio, reactor=self.poller)
        def run():
            try:
                time.sleep(1)
                self.m.run()
            except:
                import traceback
                traceback.print_exc()
        self.m_run = threading.Thread(target=run)
        self.m_run.setDaemon(False)     
        self.local_sock = socket.socket()
        self.msgs = []
    def tearDown(self):
        self.local_sock.close()
    def test_sock_connect_timeout(self):
        self.ev = threading.Event()
        self.ev.clear()
        @coroutine 
        def sleeper(secs):
            now = time.time()
            yield events.Sleep(secs)
            self.msgs.append(time.time() - now)
        @coroutine
        def coro():
            try:
                self.now = time.time()
                yield events.Sleep(1)
                self.msgs.append(time.time() - self.now)
                cli = sockets.Socket()
                yield sockets.Connect(cli, self.local_addr, prio = self.prio, timeout=5)
                try:
                    self.now = time.time()
                    yield sockets.ReadAll(cli, 4096, timeout=2, prio = self.prio)
                except events.OperationTimeout:
                    self.msgs.append(time.time() - self.now)
                
                # well, this is certainly weird - if i close this sock the descriptor
                #will be reused and aparently this one is botched and breaks what 
                #follows
                #~ cli.close()
                # or maybe split this test in two (todo)
                
                time.sleep(5)
                srv = sockets.Socket()
                self.local_addr = ('localhost', random.randint(20000,21000))
                srv.bind(self.local_addr)
                srv.listen(10)
                
                self.ev.set()
                yield sockets.Accept(srv, prio = self.prio, timeout=5)
                try:
                    self.now = time.time()
                    yield sockets.Accept(srv, timeout = 3, prio = self.prio)
                except events.OperationTimeout:
                    self.msgs.append(time.time() - self.now)
                yield events.AddCoro(sleeper, args=(5,))
                try:
                    self.now = time.time()
                    print '> %s;' % (
                        yield events.WaitForSignal('bla', timeout=4, prio=self.prio)
                    )
                except events.OperationTimeout:
                    self.msgs.append(time.time() - self.now)
            except:
                traceback.print_exc()
                self.ev.set()
                thread.interrupt_main()
                
            
        try:    
            self.local_sock.bind(self.local_addr)
            self.local_sock.listen(10)
            self.m.add(coro)
            self.m_run.start()
            self.sock = self.local_sock.accept()
            self.local_sock.close()
            self.ev.wait()
            time.sleep(0.1)
            self.local_sock = socket.socket()
            self.local_sock.connect(self.local_addr)
            self.local_sock.getpeername()
            time.sleep(1)
            #~ print self.m.active
            #~ print self.m.poll
        except KeyboardInterrupt:
            self.failIf("Interrupted from the coroutine, something failed.")
        self.m_run.join()
        self.assertEqual(len(self.m.poll), 0)
        self.assertEqual(len(self.m.active), 0)
        self.assertAlmostEqual(self.msgs[0], 1.0, 1)
        self.assertAlmostEqual(self.msgs[1], 2.0, 1)
        self.assertAlmostEqual(self.msgs[2], 3.0, 1)
        self.assertAlmostEqual(self.msgs[3], 4.0, 1)
        self.assertAlmostEqual(self.msgs[4], 5.0, 1)

        
for poller_cls in reactors.available:
    for prio_mixin in (NoPrioMixIn, PrioMixIn):
        name = 'TimerTest_%s_%s' % (prio_mixin.__name__, poller_cls.__name__)
        globals()[name] = type(
            name, (Timer_MixIn, prio_mixin, unittest.TestCase),
            {'poller':poller_cls}
        )

if __name__ == "__main__":
    sys.argv.insert(1, '-v')
    unittest.main()
