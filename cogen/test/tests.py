import os 
import sys
sys.path.append(os.path.split(os.path.split(os.getcwd())[0])[0])
#~ print sys.path
from cogen.web import *
from cogen.core import events
from cogen.core.schedulers import *
from cogen.core.coroutine import coroutine
import thread, threading
import random
import exceptions

from socket import *
from cStringIO import StringIO
from time import sleep  



import unittest
class SocketTest_MixIn:
    def setUp(t):
        t.local_addr = ('localhost', random.randint(1000,2000))
        t.m = t.scheduler()
        def run():
            try:
                time.sleep(1)
                t.m.run()
            except:
                import traceback
                traceback.print_exc()
        t.m_run = threading.Thread(target=run)
        
    def tearDown(t):
        pass
        
    def test_read_lines(t):
        t.waitobj = None
        @coroutine
        def reader():
            srv = sockets.New()
            srv.setblocking(0)
            srv.bind(t.local_addr)
            srv.listen(0)
            obj = yield t.prio, sockets.Accept(srv)
            t.waitobj = sockets.ReadLine(sock=obj.conn, len=1024) 
                                    # test for simple readline, 
                                    #   send data w/o NL, 
                                    #   check poller, send NL, check again
            t.recvobj = yield t.prio, t.waitobj
            try: 
                # test for readline overflow'
                t.waitobj2 = yield t.prio, sockets.ReadLine(sock=obj.conn, len=512)
            except exceptions.OverflowError, e:
                t.waitobj2 = "OK"
                t.waitobj_cleanup = yield t.prio, sockets.Read(sock=obj.conn, len=1024*8) 
                                        # eat up the remaining data waiting on socket
            t.recvobj2 = (
                (yield t.prio, sockets.ReadLine(obj.conn, 1024)),
                (yield t.prio, sockets.ReadLine(obj.conn, 1024)),
                (yield t.prio, sockets.ReadLine(obj.conn, 1024))
            )
        coro = t.m.add(reader)
        t.m_run.start()
        sleep(0.1)
        sock = socket()
        sock.connect(t.local_addr)
        sock.send("X"*512)
        sleep(0.5)
        t.assert_(coro not in t.m.active)
        t.assert_(t.m.poll.waiting(coro) is t.waitobj)            
        sock.send("\n")
        sleep(0.5)
        t.assert_(len(t.m.poll)==1)
        t.assertEqual(t.waitobj.buff, "X"*512+"\n")
        sleep(0.5)
        sock.send("X"*1024)

        sleep(0.5)
        t.assertEqual(t.waitobj2, "OK")
        sleep(0.5)
        a_line = "X"*64+"\n"
        sock.send(a_line*3)
        sleep(1.5)
        t.assertEqual(map(lambda x: x.buff,t.recvobj2), [a_line,a_line,a_line])
        t.assertEqual(len(t.m.poll), 0)
        t.assertEqual(len(t.m.active), 0)
        t.failIf(t.m_run.isAlive())
        
    def test_read_all(t):
        @coroutine
        def reader():
            srv = sockets.New()
            srv.setblocking(0)
            srv.bind(t.local_addr)
            srv.listen(0)
            obj = yield t.prio, sockets.Accept(srv)
            t.recvobj = yield t.prio, sockets.Read(obj.conn, 1024*4)
            t.recvobj_all = yield t.prio, sockets.ReadAll(obj.conn, 1024**2-1024*4)
        coro = t.m.add(reader)
        t.m_run.start()
        sleep(0.1)
        sock = socket()
        sock.connect(t.local_addr)
        sent = 0
        length = 1024**2
        buff = "X"*length
        while sent<length:
            sent += sock.send(buff[sent:])
            
        sleep(0.5)
        t.assert_(len(t.recvobj.buff)<=1024*4)
        sleep(1)
        t.assertEqual(len(t.recvobj_all.buff)+len(t.recvobj.buff),1024**2)
        t.assertEqual(len(t.m.poll), 0)
        t.assertEqual(len(t.m.active), 0)
        t.failIf(t.m_run.isAlive())
    def test_write_all(t):
        @coroutine
        def writer():
            obj = yield sockets.Connect(sockets.New(), t.local_addr)    
            t.writeobj = yield sockets.Write(obj.sock, 'X'*(1024**2))
            t.writeobj_all = yield sockets.WriteAll(obj.sock, 'Y'*(1024**2))
            obj.sock.close()

        srv = socket()
        srv.setblocking(0)
        srv.bind(t.local_addr)
        srv.listen(0)
        coro = t.m.add(writer)
        t.m_run.start()
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
        t.assertEqual(t.writeobj.sent+t.writeobj_all.sent, total)
        t.assertEqual(len(t.m.poll), 0)
        t.assertEqual(len(t.m.active), 0)
        t.failIf(t.m_run.isAlive())
class SchedulerTest_MixIn:
    def setUp(t):
        t.m = t.scheduler()
        t.msgs = []
        
    def tearDown(t):
        pass
    def test_signal(t):
        class X:
            pass
        x = X()
        @coroutine
        def signalee():
            t.msgs.append(1)
            yield events.WaitForSignal("test_sig")
            t.msgs.append(3)
            yield events.WaitForSignal(x)
            t.msgs.append(5)
        @coroutine
        def signaler():
            t.msgs.append(2)
            yield events.Signal("test_sig")
            t.msgs.append(4)
            yield events.Signal(x)
            t.msgs.append(6)
            
        t.m.add(signalee)
        t.m.add(signaler)
        t.m.run()
        t.assertEqual(t.msgs, [1,2,3,4,5,6])
    def test_add_coro(t):
        @coroutine
        def added(x):
            t.msgs.append(x)
        @coroutine
        def adder(c):
            t.msgs.append(1)
            yield events.AddCoro(c,2)
            t.msgs.append(3)
        t.m.add(adder, added)
        t.m.run()
        t.assertEqual(t.msgs, [1,2,3])
    def test_call(t):
        @coroutine
        def caller():
            t.msgs.append(1)
            ret = yield events.Call(callee_1)
            t.msgs.append(ret.result)
            ret = yield events.Call(callee_2)
            t.msgs.append(ret.result is None and 3 or -1)
            try:
                ret = yield events.Call(callee_3)
            except Exception, e:
                t.msgs.append(e.message=='some_message' and 4 or -1)
             
            ret = yield events.Call(callee_4)
            t.msgs.append(ret.result)
            try:
                ret = yield events.Call(callee_5)
            except:
                import traceback
                s = traceback.format_exc()
                t.exc = s

            ret = yield events.Call(callee_6, 6)
            t.msgs.append(ret.result)
            
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
            raise StopIteration((yield events.Call(callee_4_1)).result)
        @coroutine
        def callee_4_1():
            raise StopIteration((yield events.Call(callee_4_2)).result)
        @coroutine
        def callee_4_2():
            raise StopIteration(5)
        
        @coroutine
        def callee_5():
            raise StopIteration((yield events.Call(callee_5_1)).result)
        @coroutine
        def callee_5_1():
            raise StopIteration((yield events.Call(callee_5_2)).result)
        @coroutine
        def callee_5_2():
            raise Exception("long_one")
        
        @coroutine
        def callee_6(x):
            raise StopIteration(x)
            
        
        t.m.add(caller)
        t.m.run()
        t.assertEqual(t.msgs, [1,2,3,4,5,6])
        t.assert_('raise StopIteration((yield events.Call(callee_5_1)).result)' in t.exc)
        t.assert_('raise StopIteration((yield events.Call(callee_5_2)).result)' in t.exc)
        t.assert_('raise Exception("long_one")' in t.exc)
    def test_join(t):
        @coroutine
        def caller():
            t.msgs.append(1)
            ret = yield events.Join(t.m.add(callee_1))
            t.msgs.append(ret.result)
            ret = yield events.Join(t.m.add(callee_2))
            t.msgs.append(3 if ret.result is None else -1)
            #~ try:
            t.c = t.m.add(callee_3)
            t.c.handle_error=lambda*a:None
            ret = yield events.Join(t.c)
            t.msgs.append(4 if ret.result is None and t.c.exception[1].message=='some_message' else -1)
            
            
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
        t.m.add(caller)
        t.m.run()
        t.assertEqual(t.msgs, [1,2,3,4])
class PrioMixIn:
    prio = Priority.FIRST
class NoPrioMixIn:
    prio = Priority.LAST
    
class PrioSchedulerTest(SchedulerTest_MixIn, PrioMixIn, unittest.TestCase):
    scheduler = Scheduler
class NoPrioSchedulerTest(SchedulerTest_MixIn, NoPrioMixIn, unittest.TestCase):
    scheduler = Scheduler
class PrioScheduler_SocketTest(SocketTest_MixIn, PrioMixIn, unittest.TestCase):
    scheduler = Scheduler
class NoPrioScheduler_SocketTest(SocketTest_MixIn, NoPrioMixIn, unittest.TestCase):
    scheduler = Scheduler

if __name__ == '__main__':
    sys.argv.append('-v')
    unittest.main()
            