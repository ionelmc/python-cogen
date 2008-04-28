__doc_all__ = []

import unittest
import random
import threading
import socket
import time
import sys
import errno
import exceptions
import datetime
import traceback 
import thread

from cStringIO import StringIO

from cogen.common import *
from cogen.core import reactors
from base import priorities
from cogen.core.coroutines import debug_coroutine

class SocketTest_MixIn:
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
        
    def tearDown(self):
        del self.m
        import gc; gc.collect()
        
    def test_read_lines(self):
        self.waitobj = None
        @coroutine
        def reader():
            srv = sockets.Socket()
            srv.setblocking(0)
            srv.bind(self.local_addr)
            srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            srv.listen(0)
            conn, addr = (yield sockets.Accept(srv, prio=self.prio, run_first=self.run_first))
            self.waitobj = sockets.ReadLine(conn, len=1024, prio=self.prio, run_first=self.run_first) 
                                    # test for simple readline, 
                                    #   send data w/o NL, 
                                    #   check poller, send NL, check again
            self.recvobj = yield self.waitobj
            try:
                # test for readline overflow'
                self.waitobj2 = yield sockets.ReadLine(
                    conn, 
                    len=512, 
                    prio=self.prio, run_first=self.run_first
                )
            except exceptions.OverflowError, e:
                self.waitobj2 = "OK"
                self.waitobj_cleanup = yield sockets.Read(
                    conn, 
                    len=1024*8, 
                    prio=self.prio, run_first=self.run_first
                ) 
                    # eat up the remaining data waiting on socket
            y1 = sockets.ReadLine(conn, 1024, prio=self.prio, run_first=self.run_first)
            y2 = sockets.ReadLine(conn, 1024, prio=self.prio, run_first=self.run_first)
            y3 = sockets.ReadLine(conn, 1024, prio=self.prio, run_first=self.run_first)
            a1 = yield y1 
            a2 = yield y2
            a3 = yield y3
            self.recvobj2 = (a1,a2,a3)
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

        time.sleep(1.5)
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
            srv.bind(self.local_addr)
            srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            srv.listen(0)
            conn, addr = yield sockets.Accept(srv, prio=self.prio, run_first=self.run_first)
            self.recvobj = yield sockets.Read(conn, 1024*4, prio=self.prio, run_first=self.run_first)
            self.recvobj_all = yield sockets.ReadAll(
                conn, 
                1024**2-1024*4, 
                prio=self.prio, run_first=self.run_first
            )
            #~ srv.close()
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
            time.sleep(0.1)
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
            try:
                obj = yield sockets.Connect(sockets.Socket(), self.local_addr, timeout=0.5)    
                self.writeobj = yield sockets.Write(obj.sock, 'X'*(1024**2))
                self.writeobj_all = yield sockets.WriteAll(obj.sock, 'Y'*(1024**2))
                obj.sock.close()
            except:
                traceback.print_exc()
                thread.interrupt_main()
                
        try:
            srv = socket.socket()
            srv.setblocking(0)
            srv.bind(self.local_addr)
            srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
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
                except socket.error, exc:
                    if exc[0] in (errno.EAGAIN, errno.EWOULDBLOCK):
                        break
                    else:
                        raise
            srv.close()
            self.assertEqual(self.writeobj+self.writeobj_all, total)
            self.assertEqual(len(self.m.poll), 0)
            self.assertEqual(len(self.m.active), 0)
            self.failIf(self.m_run.isAlive())
        except KeyboardInterrupt:
            self.failIf("Interrupted from the coroutine, something failed.")
            
for poller_cls in reactors.available:
    for prio_mixin in priorities:
        for run_first in (True, False):
            name = 'SocketTest_%s_%s_%s' % (prio_mixin.__name__, poller_cls.__name__, run_first and 'RunFirst' or 'PollFirst')
            globals()[name] = type(
                name, (SocketTest_MixIn, prio_mixin, unittest.TestCase),
                {'poller':poller_cls, 'run_first':run_first}
            )
    
if __name__ == "__main__":
    sys.argv.insert(1, '-v')
    unittest.main()