import os 
import sys
sys.path.append(os.path.split(os.path.split(os.getcwd())[0])[0])
#~ print sys.path
from cogen.web import *
from cogen.core import *
import thread, threading
import random

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
            srv = Socket.New()
            srv.setblocking(0)
            srv.bind(t.local_addr)
            srv.listen(0)
            obj = yield t.prio, Socket.Accept(srv)
            t.waitobj = Socket.ReadLine(sock=obj.conn, len=1024) 
                                    # test for simple readline, 
                                    #   send data w/o NL, 
                                    #   check poller, send NL, check again
            t.recvobj = yield t.prio, t.waitobj
            try: 
                # test for readline overflow'
                t.waitobj2 = yield t.prio, Socket.ReadLine(sock=obj.conn, len=512)
            except exceptions.OverflowError, e:
                t.waitobj2 = "OK"
                t.waitobj_cleanup = yield t.prio, Socket.Read(sock=obj.conn, len=1024*8) 
                                        # eat up the remaining data waiting on socket
            t.recvobj2 = (
                (yield t.prio, Socket.ReadLine(obj.conn, 1024)),
                (yield t.prio, Socket.ReadLine(obj.conn, 1024)),
                (yield t.prio, Socket.ReadLine(obj.conn, 1024))
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
            srv = Socket.New()
            srv.setblocking(0)
            srv.bind(t.local_addr)
            srv.listen(0)
            obj = yield t.prio, Socket.Accept(srv)
            t.recvobj = yield t.prio, Socket.Read(obj.conn, 1024*4)
            t.recvobj_all = yield t.prio, Socket.ReadAll(obj.conn, 1024**2-1024*4)
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
            #~ print 'connecting'
            obj = yield Socket.Connect(Socket.New(), t.local_addr)    
            #~ print 'connected', obj            
            #~ t.writeobj = yield Socket.WriteAll(obj.sock, 'X'*(1024**2)*100)
            #~ print t.writeobj, t.writeobj.sent
            t.writeobj = yield Socket.Write(obj.sock, 'X'*(1024**2))
            #~ print 'SEND1',t.writeobj, repr(t.writeobj.sent)
            t.writeobj_all = yield Socket.WriteAll(obj.sock, 'Y'*(1024**2))
            #~ print 'SEND2',t.writeobj_all, t.writeobj_all.sent
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
            #~ print t.m_run.isAlive()
            #~ print t.m_run
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
        @coroutine
        def signalee():
            t.msgs.append(1)
            yield Events.WaitForSignal("test_sig")
            t.msgs.append(3)
        @coroutine
        def signaler():
            t.msgs.append(2)
            yield Events.Signal("test_sig")
            t.msgs.append(4)
        t.m.add(signalee)
        t.m.add(signaler)
        t.m.run()
        t.assertEqual(t.msgs, [1,2,3,4])
    def test_add_coro(t):
        @coroutine
        def added():
            t.msgs.append(2)
        def adder(c):
            t.msgs.append(1)
            yield Events.AddCoro(c)
            t.msgs.append(3)
        t.m.add(coroutine(adder(added)))
        t.m.run()
        t.assertEqual(t.msgs, [1,2,3])
    def test_call(t):
        @coroutine
        def caller():
            t.msgs.append(1)
            ret = yield Events.Call(callee_1)
            t.msgs.append(ret)
            yield Events.Call(callee_2)
            t.msgs.append(3)
            yield Events.Call(callee_3)
            t.msgs.append(3)
            yield Events.Call(callee_4)
            t.msgs.append(3)
        @coroutine
        def callee_1():
            raise StopIteration("return_val")
        @coroutine
        def callee_2():
            pass
        @coroutine
        def callee_3():
            pass
        @coroutine
        def callee_4():
            pass
        t.m.add(caller)
        t.m.run()
        
        print t.msgs
class PrioMixIn:
    prio = True
class NoPrioMixIn:
    prio = False
    
class SchedulerTest(SchedulerTest_MixIn, unittest.TestCase):
    scheduler = Scheduler
class PrioScheduler_SocketTest(SocketTest_MixIn, PrioMixIn, unittest.TestCase):
    scheduler = Scheduler
class NoPrioScheduler_SocketTest(SocketTest_MixIn, NoPrioMixIn, unittest.TestCase):
    scheduler = Scheduler

if __name__ == '__main__':
    sys.argv.append('-v')
    unittest.main()
            