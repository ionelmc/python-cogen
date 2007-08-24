from corosive.web import *
from corosive.core import *
import sys
import os 
import thread
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
                t.m.run()
            except:
                import traceback
                traceback.print_exc()
        t.m_run = thread.start_new_thread(run, ())
    def tearDown(t):
        assert len(t.m.pool) == 0
        assert len(t.m.active) == 0
    def test_read_lines(t):
        t.waitobj = None
        def reader():
            srv = Socket.New()
            srv.setblocking(0)
            srv.bind(t.local_addr)
            srv.listen(0)
            obj = yield Socket.Accept(srv)
            t.waitobj = Socket.ReadLine(sock=obj.conn, len=1024) 
                                    # test for simple readline, 
                                    #   send data w/o NL, 
                                    #   check pooler, send NL, check again
            t.recvobj = yield t.waitobj
            try: 
                # test for readline overflow'
                t.waitobj2 = yield Socket.ReadLine(sock=obj.conn, len=512)
            except exceptions.OverflowError, e:
                t.waitobj2 = "OK"
                t.waitobj_cleanup = yield Socket.Read(sock=obj.conn, len=1024*8) 
                                        # eat up the remaining data waiting on socket
            t.recvobj2 = (
                (yield Socket.ReadLine(obj.conn, 1024)),
                (yield Socket.ReadLine(obj.conn, 1024)),
                (yield Socket.ReadLine(obj.conn, 1024))
            )
        coro = t.m.add(reader)
        sock = socket()
        sock.connect(t.local_addr)
        sock.send("X"*512)
        sleep(0.5)
        t.assert_(coro not in t.m.active)
        t.assert_(t.m.pool.waiting(coro) is t.waitobj)            
        sock.send("\n")
        sleep(0.5)
        t.assert_(len(t.m.pool)==1)
        t.assertEqual(t.waitobj.buff, "X"*512+"\n")
        sleep(0.5)
        sock.send("X"*1024)

        sleep(0.5)
        t.assertEqual(t.waitobj2, "OK")
        sleep(0.5)
        a_line = "X"*64+"\n"
        sock.send(a_line*3)
        sleep(0.5)
        t.assertEqual(map(lambda x: x.buff,t.recvobj2), [a_line,a_line,a_line])
        t.assert_(len(t.m.pool)==0)
    def test_read_all(t):
        def reader():
            srv = Socket.New()
            srv.setblocking(0)
            srv.bind(t.local_addr)
            srv.listen(0)
            obj = yield Socket.Accept(srv)
            t.recvobj = yield Socket.Read(obj.conn, 1024*4)
            t.recvobj_all = yield Socket.ReadAll(obj.conn, 1024**2-1024*4)
        coro = t.m.add(reader)
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
    def test_write_all(t):
        def writer():
            obj = yield Socket.Connect(Socket.New(), t.local_addr)        
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
class GreedyScheduler_SocketTest(SocketTest_MixIn, unittest.TestCase):
    scheduler = GreedyScheduler
class Scheduler_SocketTest(SocketTest_MixIn, unittest.TestCase):
    scheduler = Scheduler
#~ def suite():
    #~ return unittest.TestSuite([
        #~ GreedyScheduler_SocketTest,
        #~ Scheduler_SocketTest
    #~ ])
if __name__ == '__main__':
    sys.argv.append('-v')
    unittest.main()
            