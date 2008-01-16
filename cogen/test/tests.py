"""
todo: 
- test for timeout: operator runs before the timeout but it remains allocated.
-
"""


import os 
import sys
import thread, threading
#~ threading._VERBOSE = True
import random
import exceptions
import datetime
from socket import *
from cStringIO import StringIO
from time import sleep  

from cogen.web import *
from cogen.core import events
from cogen.core.schedulers import *
from cogen.core.coroutine import coroutine



import unittest
class SocketTest_MixIn:
    def setUp(self):
        self.local_addr = ('localhost', random.randint(19000,20000))
        self.m = self.scheduler()
        def run():
            try:
                time.sleep(1)
                self.m.run()
            except:
                import traceback
                traceback.print_exc()
        self.m_run = threading.Thread(target=run)
        
    def tearDown(self):
        pass
        
    def test_read_lines(self):
        self.waitobj = None
        @coroutine
        def reader():
            srv = sockets.Socket()
            srv.setblocking(0)
            srv.bind(self.local_addr)
            srv.listen(0)
            conn, addr = (yield sockets.Accept(srv, prio = self.prio))
            self.waitobj = sockets.ReadLine(conn, len=1024, prio = self.prio) 
                                    # test for simple readline, 
                                    #   send data w/o NL, 
                                    #   check poller, send NL, check again
            self.recvobj = yield self.waitobj
            try: 
                # test for readline overflow'
                self.waitobj2 = yield sockets.ReadLine(conn, len=512, prio = self.prio)
            except exceptions.OverflowError, e:
                self.waitobj2 = "OK"
                self.waitobj_cleanup = yield sockets.Read(conn, len=1024*8, prio = self.prio) 
                                        # eat up the remaining data waiting on socket
            self.recvobj2 = (
                (yield sockets.ReadLine(conn, 1024, prio = self.prio)),
                (yield sockets.ReadLine(conn, 1024, prio = self.prio)),
                (yield sockets.ReadLine(conn, 1024, prio = self.prio))
            )
            srv.close()
        coro = self.m.add(reader)
        self.m_run.start()
        sleep(1.5)
        sock = socket()
        sock.connect(self.local_addr)
        sock.send("X"*512)
        sleep(0.5)
        self.assert_(coro not in self.m.active)
        self.assert_(self.m.poll.waiting_op(coro) is self.waitobj)            
        sock.send("\n")
        sleep(0.5)
        self.assert_(len(self.m.poll)==1)
        self.assert_(self.waitobj.buff is self.recvobj)
        self.assertEqual(self.waitobj.buff, "X"*512+"\n")
        sleep(0.5)
        sock.send("X"*1024)

        sleep(0.5)
        self.assertEqual(self.waitobj2, "OK")
        sleep(0.5)
        a_line = "X"*64+"\n"
        sock.send(a_line*3)
        sleep(1.5)
        self.assertEqual(self.recvobj2, (a_line,a_line,a_line))
        self.assertEqual(len(self.m.poll), 0)
        self.assertEqual(len(self.m.active), 0)
        self.failIf(self.m_run.isAlive())
        
    def test_read_all(self):
        @coroutine
        def reader():
            srv = sockets.Socket()
            srv.setblocking(0)
            srv.bind(self.local_addr)
            srv.listen(0)
            conn, addr = yield sockets.Accept(srv, prio = self.prio)
            self.recvobj = yield sockets.Read(conn, 1024*4, prio = self.prio)
            self.recvobj_all = yield sockets.ReadAll(conn, 1024**2-1024*4, prio = self.prio)
            srv.close()
        coro = self.m.add(reader)
        self.m_run.start()
        sleep(1.5)
        sock = socket()
        sock.connect(self.local_addr)
        sent = 0
        length = 1024**2
        buff = "X"*length
        while sent<length:
            sent += sock.send(buff[sent:])
            
        sleep(0.5)
        self.assert_(len(self.recvobj)<=1024*4)
        sleep(1)
        
        self.assertEqual(len(self.recvobj_all)+len(self.recvobj),1024**2)
        self.assertEqual(len(self.m.poll), 0)
        self.assertEqual(len(self.m.active), 0)
        self.failIf(self.m_run.isAlive())
    def test_write_all(self):
        @coroutine
        def writer():
            obj = yield sockets.Connect(sockets.Socket(), self.local_addr)    
            self.writeobj = yield sockets.Write(obj.sock, 'X'*(1024**2))
            self.writeobj_all = yield sockets.WriteAll(obj.sock, 'Y'*(1024**2))
            obj.sock.close()

        srv = socket()
        srv.setblocking(0)
        srv.bind(self.local_addr)
        srv.listen(0)
        coro = self.m.add(writer)
        self.m_run.start()
        sleep(1)
        while 1:
            sleep(0.2)
            try:
                cli, addr = srv.accept()    
                break
            except error, exc:
                if exc[0] in (errno.EAGAIN, errno.EWOULDBLOCK):
                    continue
                else:
                    raise
            
        sleep(0.2)
        cli.setblocking(1)
        buff = cli.recv(1024*2)
        cli.setblocking(0)
        sleep(0.5)
        total = len(buff)
        while len(buff):
            sleep(0.01)
            try:
                buff = cli.recv(1024**2*10)
                total += len(buff)
            except error, exc:
                if exc[0] in (errno.EAGAIN, errno.EWOULDBLOCK):
                    break
                else:
                    raise
        srv.close()
        self.assertEqual(self.writeobj+self.writeobj_all, total)
        self.assertEqual(len(self.m.poll), 0)
        self.assertEqual(len(self.m.active), 0)
        self.failIf(self.m_run.isAlive())
class SchedulerTest_MixIn:
    def setUp(self):
        self.m = self.scheduler()
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
            yield events.Signal(x)
            self.msgs.append(6)
            
        self.m.add(signalee)
        self.m.add(signaler)
        self.m.run()
        self.assertEqual(self.msgs, [1,2,3,4,5,6])
    def test_add_coro(self):
        @coroutine
        def added(x):
            self.msgs.append(x)
        @coroutine
        def adder(c):
            self.msgs.append(1)
            yield events.AddCoro(c, args=(2,))
            self.msgs.append(3)
        self.m.add(adder, added)
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
            self.c.handle_error=lambda*a:None
            ret = yield events.Join(self.c)
            self.msgs.append(4 if ret is None and self.c.exception[1].message=='some_message' else -1)
            
            
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
class Timer_MixIn:
    def setUp(self):
        self.local_addr = ('localhost', random.randint(19000,20000))
        self.m = self.scheduler()
        def run():
            try:
                time.sleep(1)
                self.m.run()
            except:
                import traceback
                traceback.print_exc()
        self.m_run = threading.Thread(target=run)
        self.m_run.setDaemon(False)        
        self.local_sock = socket()        
        self.msgs = []
    def tearDown(self):
        self.local_sock.close()
    def test_sock_connect_timeout(self):
        self.ev = threading.Event()
        self.ev.clear()
        @coroutine 
        def sleeper(secs):
            self.now = time.time()
            yield events.Sleep(secs)
            self.msgs.append(time.time() - self.now)
        @coroutine
        def coro():
            
            self.now = time.time()
            yield events.Sleep(1)
            self.msgs.append(time.time() - self.now)
            cli = sockets.Socket()
            yield sockets.Connect(cli, self.local_addr, prio = self.prio)
            try:
                self.now = time.time()
                yield sockets.ReadAll(cli, 4096, timeout=2, prio = self.prio)
            except events.OperationTimeout:
                self.msgs.append(time.time() - self.now)
            cli.close()
            
            time.sleep(5)
            srv = sockets.Socket()
            self.local_addr = ('localhost', random.randint(20000,21000))
            srv.bind(self.local_addr)
            srv.listen(10)
            
            self.ev.set()
            yield sockets.Accept(srv, prio = self.prio)
            try:
                self.now = time.time()
                yield sockets.Accept(srv, timeout = 3, prio = self.prio)
            except events.OperationTimeout:
                self.msgs.append(time.time() - self.now)
            yield events.AddCoro(sleeper, args=(5,))
            try:
                self.now = time.time()
                print '> %s;' % (yield events.WaitForSignal('bla', 4, prio = self.prio))
            except events.OperationTimeout:
                self.msgs.append(time.time() - self.now)
            
            
            
        self.local_sock.bind(self.local_addr)
        self.local_sock.listen(10)
        self.m.add(coro)
        self.m_run.start()
        self.sock = self.local_sock.accept()
        self.local_sock.close()
        self.ev.wait()
        time.sleep(0.1)
        self.local_sock = socket()
        self.local_sock.connect(self.local_addr)
        self.local_sock.getpeername()
        time.sleep(1)
        #~ print self.m.active
        #~ print self.m.poll
        self.m_run.join()
        self.assertEqual(len(self.m.poll), 0)
        self.assertEqual(len(self.m.active), 0)
        self.assertAlmostEqual(self.msgs[0], 1.0, 1)
        self.assertAlmostEqual(self.msgs[1], 2.0, 1)
        self.assertAlmostEqual(self.msgs[2], 3.0, 1)
        self.assertAlmostEqual(self.msgs[3], 4.0, 1)
        self.assertAlmostEqual(self.msgs[4], 5.0, 1)
        
class PrioMixIn:
    prio = priority.FIRST
class NoPrioMixIn:
    prio = priority.LAST
    
class SchedulerTest_Prio(SchedulerTest_MixIn, PrioMixIn, unittest.TestCase):
    scheduler = Scheduler
class SchedulerTest_NoPrio(SchedulerTest_MixIn, NoPrioMixIn, unittest.TestCase):
    scheduler = Scheduler
class SocketTest_Prio(SocketTest_MixIn, PrioMixIn, unittest.TestCase):
    scheduler = Scheduler
class SocketTest_NoPrio(SocketTest_MixIn, NoPrioMixIn, unittest.TestCase):
    scheduler = Scheduler
class TimerTest_Prio(Timer_MixIn, PrioMixIn, unittest.TestCase):
    scheduler = Scheduler
class TimerTest_NoPrio(Timer_MixIn, NoPrioMixIn, unittest.TestCase):
    scheduler = Scheduler

if __name__ == '__main__':
    sys.argv.append('-v')
    unittest.main()
            