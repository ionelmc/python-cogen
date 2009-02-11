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
from base import priorities, proactors_available
from cogen.core.coroutines import debug_coroutine

class SocketTest_MixIn:
    sockets = []
    def setUp(self):
        self.thread_exception = None
        self.local_addr = ('localhost', random.randint(10000,64000))
        if self.run_first is None:
            self.m = Scheduler( default_priority=self.prio, proactor=self.poller,
                                proactor_resolution=0.01)
        else:
            self.m = Scheduler( default_priority=self.prio, proactor=self.poller,
                                proactor_resolution=0.01,
                                proactor_multiplex_first=self.run_first)
        def run():
            try:
                time.sleep(1)
                self.m.run()
            except:
                import traceback
                traceback.print_exc()
                self.thread_exception = sys.exc_info
                
        self.m_run = threading.Thread(target=run)

    def tearDown(self):
        for s in self.sockets:
            s.close()
        self.sockets = []
        del self.m
        import gc; gc.collect()

    def test_proper_err_cleanup(self):
        @coroutine
        def foo():
            yield events.Sleep(0.2)
            s = sockets.Socket()
            yield s.connect(self.local_addr)
            s.settimeout(0.01)
            yield events.Sleep(0.2)
            try:
                yield s.send("aaaaaaaa")
                yield s.send("bbbbbbbb") #should throw a EHUP or something in the mp
            except sockets.SocketError, e:
                #~ import traceback
                #~ traceback.print_exc()
                pass
            
            #test for proper cleanup
            
            x = sockets.Socket()
            x.settimeout(0.1)
            yield x.connect(self.local_addr)
            

        self.m.add(foo)
        self.sock = socket.socket()
        self.sock.bind(self.local_addr)
        self.sock.listen(1)

        self.m_run.start()
        conn, addr = self.sock.accept()
        #~ conn.shutdown(socket.SHUT_RDWR)
        conn.close()

        self.m_run.join()
        self.failIf(self.thread_exception)
        
    def test_read_lines(self):
        self.waitobj = None
        @coroutine
        def reader():
            srv = sockets.Socket()
            self.sockets.append(srv)
            srv.setblocking(0)
            srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            srv.bind(self.local_addr)
            srv.listen(0)
            conn, addr = (yield srv.accept(prio=self.prio))
            fh = conn.makefile()
            self.line1 = yield fh.readline(1024, prio=self.prio)
            self.line2 = yield fh.readline(512, prio=self.prio)
            self.line3 = yield fh.readline(1512, prio=self.prio)
            # eat up the remaining data waiting on socket
            y1 = fh.readline(1024, prio=self.prio)
            y2 = fh.readline(1024, prio=self.prio)
            y3 = fh.readline(1024, prio=self.prio)
            a1 = yield y1
            a2 = yield y2
            a3 = yield y3
            self.recvobj2 = (a1,a2,a3)
            #~ srv.close()
            self.m.shutdown()
        coro = self.m.add(reader)
        self.m_run.start()
        time.sleep(1.5)
        sock = socket.socket()
        sock.connect(self.local_addr)
        sock.send("X"*512)
        time.sleep(0.5)
        self.assert_(coro not in self.m.active)
        sock.send("\n")
        time.sleep(0.5)
        self.assert_(len(self.m.proactor)==1)
        #~ self.assert_(self.waitobj.buff is self.recvobj)
        self.assertEqual(self.line1, "X"*512+"\n")
        time.sleep(0.5)
        sock.send("X"*1024)

        time.sleep(1.5)
        self.assertEqual(self.line2, "X"*512)
        sock.send("\n")
        time.sleep(0.5)
        a_line = "X"*64+"\n"
        sock.send(a_line*3)
        self.m_run.join()
        self.assertEqual(self.recvobj2, (a_line,a_line,a_line))
        self.assertEqual(len(self.m.proactor), 0)
        self.assertEqual(len(self.m.active), 0)
        self.failIf(self.m_run.isAlive())

    def test_read_all(self):
        @coroutine
        def reader():
            srv = sockets.Socket()
            self.sockets.append(srv)
            srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            srv.bind(self.local_addr)
            srv.listen(0)
            conn, addr = yield sockets.Accept(srv, prio=self.prio)
            self.recvobj = yield sockets.Recv(conn, 1024*4, prio=self.prio)
            self.recvobj_all = yield sockets.RecvAll(conn, 1024**2-1024*4, prio=self.prio)
            #~ srv.close()
            self.m.shutdown()
        coro = self.m.add(reader)
        self.m_run.start()
        time.sleep(1.5)
        sock = socket.socket()
        self.sockets.append(sock)
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
        self.assertEqual(len(self.m.proactor), 0)
        self.assertEqual(len(self.m.active), 0)
        self.failIf(self.m_run.isAlive())
    def test_write_all(self):
        @coroutine
        def writer():
            try:
                cli = sockets.Socket()
                self.sockets.append(cli)
                conn = yield sockets.Connect(cli, self.local_addr, timeout=0.5, prio=self.prio)
                self.writeobj = yield sockets.Send(conn, 'X'*(1024**2), prio=self.prio)
                self.writeobj_all = yield sockets.SendAll(conn, 'Y'*(1024**2), prio=self.prio)
                self.sockets.append(conn)
                self.sockets.append(cli)
            except:
                traceback.print_exc()
                thread.interrupt_main()

        try:
            srv = socket.socket()
            self.sockets.append(srv)
            srv.setblocking(1)
            srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            srv.bind(self.local_addr)
            srv.listen(0)
            coro = self.m.add(writer)
            thread.start_new_thread(lambda: time.sleep(0.3) or self.m_run.start(), ())
            while 1:
                try:
                    cli, addr = srv.accept()
                    break
                except socket.error, exc:
                    if exc[0] in (errno.EAGAIN, errno.EWOULDBLOCK):
                        continue
                    else:
                        raise
            self.sockets.append(cli)

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
            self.assertEqual(self.writeobj+self.writeobj_all, total)
            self.assertEqual(len(self.m.proactor), 0)
            self.assertEqual(len(self.m.active), 0)
            self.failIf(self.m_run.isAlive())
        except KeyboardInterrupt:
            self.failIf("Interrupted from the coroutine, something failed.")

for poller_cls in proactors_available:
    for prio_mixin in priorities:
        if poller_cls.supports_multiplex_first:
            for run_first in (True, False):
                name = 'SocketTest_%s_%s_%s' % (prio_mixin.__name__, poller_cls.__name__, run_first and 'RunFirst' or 'PollFirst')
                globals()[name] = type(
                    name, (SocketTest_MixIn, prio_mixin, unittest.TestCase),
                    {'poller':poller_cls, 'run_first':run_first}
                )
        else:
            name = 'SocketTest_%s_%s' % (prio_mixin.__name__, poller_cls.__name__)
            globals()[name] = type(
                name, (SocketTest_MixIn, prio_mixin, unittest.TestCase),
                {'poller':poller_cls, 'run_first':None}
            )


if __name__ == "__main__":
    sys.argv.insert(1, '-v')
    unittest.main()
