import unittest
import random
import threading
import socket
import time
import sys
import exceptions
import datetime

from cStringIO import StringIO

from cogen.common import *
from cogen.core import pollers
from cogen.test.base import PrioMixIn, NoPrioMixIn

class SocketTest_MixIn:
    def setUp(self):
        self.local_addr = ('localhost', random.randint(19000,20000))
        self.m = Scheduler(default_priority=self.prio, poller=self.poller)
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
                self.waitobj2 = yield sockets.ReadLine(
                    conn, 
                    len=512, 
                    prio = self.prio
                )
            except exceptions.OverflowError, e:
                self.waitobj2 = "OK"
                self.waitobj_cleanup = yield sockets.Read(
                    conn, 
                    len=1024*8, 
                    prio = self.prio
                ) 
                    # eat up the remaining data waiting on socket
            self.recvobj2 = (
                (yield sockets.ReadLine(conn, 1024, prio = self.prio)),
                (yield sockets.ReadLine(conn, 1024, prio = self.prio)),
                (yield sockets.ReadLine(conn, 1024, prio = self.prio))
            )
            srv.close()
            self.m.stop()
        coro = self.m.add(reader)
        self.m_run.start()
        time.sleep(1.5)
        sock = socket.socket()
        sock.connect(self.local_addr)
        sock.send("X"*512)
        time.sleep(0.5)
        self.assert_(coro not in self.m.active)
        self.assert_(self.m.poll.waiting_op(coro) is self.waitobj)            
        sock.send("\n")
        time.sleep(0.5)
        self.assert_(len(self.m.poll)==1)
        self.assert_(self.waitobj.buff is self.recvobj)
        self.assertEqual(self.waitobj.buff, "X"*512+"\n")
        time.sleep(0.5)
        sock.send("X"*1024)

        time.sleep(0.5)
        self.assertEqual(self.waitobj2, "OK")
        time.sleep(0.5)
        a_line = "X"*64+"\n"
        sock.send(a_line*3)
        self.m_run.join()
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
            self.recvobj_all = yield sockets.ReadAll(
                conn, 
                1024**2-1024*4, 
                prio = self.prio
            )
            srv.close()
            self.m.stop()
        coro = self.m.add(reader)
        self.m_run.start()
        time.sleep(1.5)
        sock = socket.socket()
        sock.connect(self.local_addr)
        sent = 0
        length = 1024**2
        buff = "X"*length
        while sent<length:
            sent += sock.send(buff[sent:])
        
        self.m_run.join()
        self.assert_(len(self.recvobj)<=1024*4)
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

        srv = socket.socket()
        srv.setblocking(0)
        srv.bind(self.local_addr)
        srv.listen(0)
        coro = self.m.add(writer)
        self.m_run.start()
        time.sleep(1)
        while 1:
            time.sleep(0.2)
            try:
                cli, addr = srv.accept()    
                break
            except error, exc:
                if exc[0] in (errno.EAGAIN, errno.EWOULDBLOCK):
                    continue
                else:
                    raise
            
        time.sleep(0.2)
        cli.setblocking(1)
        buff = cli.recv(1024*2)
        cli.setblocking(0)
        time.sleep(0.5)
        total = len(buff)
        while len(buff):
            time.sleep(0.01)
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

for poller_cls in pollers.available:
    for prio_mixin in (NoPrioMixIn, PrioMixIn):
        name = 'SocketTest_%s_%s' % (prio_mixin.__name__, poller_cls.__name__)
        globals()[name] = type(
            name, (SocketTest_MixIn, prio_mixin, unittest.TestCase),
            {'poller':poller_cls}
        )
    
if __name__ == "__main__":
    sys.argv.insert(1, '-v')
    unittest.main()