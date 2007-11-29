from __future__ import division

import socket
import select
import collections
import time
import sys
import traceback
import types
import errno
import exceptions
from cStringIO import StringIO

import sockets

class Poller:
    """
    A poller just checks if there are ready-sockets for the operations.
    The operations are not done here, they are done in the socket ops instances.
    """
    def run_once(t, sock, sockets):           
        obj, coro = pair = sockets[sock]
        
        try:
            obj = obj.try_run()
            
            if obj:
                del sockets[sock]
                return obj, coro
            #~ else:
                #~ sockets[sock] = pair
        except:
            del sockets[sock]
            #~ print 'SockException', sock, obj, pair
            return Exception(sys.exc_info()), coro
    def try_run_obj(t, obj):
        try:
            r = obj.try_run()
        except:
            r = Exception(sys.exc_info())
        return r
class SelectPoller(Poller):
    def __init__(t):
        t.read_sockets = {}
        t.write_sockets = {}
    def __len__(t):
        return len(t.read_sockets) + len(t.write_sockets)
    def waiting(t, x):
        for socks in (t.read_sockets, t.write_sockets):
            for i in socks:
                obj, coro = socks[i]
                if x is coro:
                    return obj
    def add(t, obj, coro, run_obj=True):
        r = run_obj and t.try_run_obj(obj) or False
        if r: 
            return r
        else:
            if obj.__class__ in sockets.read_ops:
                assert obj.sock not in t.read_sockets
                t.read_sockets[obj.sock] = obj, coro
            if obj.__class__ in sockets.write_ops:
                assert obj.sock not in t.write_sockets
                t.write_sockets[obj.sock] = obj, coro
        
    def run(t, timeout = 0):
        ptimeout = (timeout and timeout>0 and timeout/1000000) or (timeout and 0.02 or 0)
        # set a small step for timeout if it's negative (meaning there are no active coros but there are waiting ones in the socket poll)
        #                            0 if it's none (there are active coros, we don't want to waste time in the poller)
        if t.read_sockets or t.write_sockets:
            #~ print 'SELECTING, timeout:', timeout, 'ptimeout:', ptimeout, 'socks:',t.read_sockets.keys(), t.write_sockets.keys()
            ready_to_read, ready_to_write, in_error = select.select(t.read_sockets.keys(), t.write_sockets.keys(), [], ptimeout)
            for sock in ready_to_read: 
                result = t.run_once(sock, t.read_sockets)
                if result:
                    yield result
            for sock in ready_to_write: 
                result = t.run_once(sock, t.write_sockets)
                if result:
                    yield result
        else:
            time.sleep(timeout>=0 and timeout/1000000 or 0)
            
class EpollPoller(Poller):
    def __init__(t, default_size = 20):
        t.fds = {}
        t.epoll_fd = epoll.epoll_create(default_size)
    def __len__(t):
        return len(t.fds)
    def waiting(t, x):
        for i in t.fds:
            obj, coro = t.fds[i]
            if x is coro:
                return obj
    def add(t, obj, coro):
        r = t.try_run_obj(obj)
        if r: 
            return r
        else:
            fd = obj.sock.fileno()
            assert fd not in t.fds
                    
            if obj.__class__ in sockets.read_ops:
                t.fds[fd] = obj, coro
                epoll.epoll_ctl(t.epoll_fd, epoll.EPOLL_CTL_ADD, fd, epoll.EPOLLIN)
            if obj.__class__ in sockets.write_ops:
                t.fds[fd] = obj, coro
                epoll.epoll_ctl(t.epoll_fd, epoll.EPOLL_CTL_ADD, fd, epoll.EPOLLOUT)
    def run(t, timeout = 0):
        ptimeout = (timeout and timeout>0 and timeout/1000) or (timeout or 0)
        if t.fds:
            events = epoll.epoll_wait(t.epoll_fd, 10, ptimeout)
            for ev, fd in events:
                print "EPOLL Event:", ev, fd
                result = t.run_once(fd, t.fds)
                if result:
                    epoll.epoll_ctl(t.epoll_fd, epoll.EPOLL_CTL_DEL, fd, 0)
                    yield result
        else:
            time.sleep(timeout>=0 and timeout/1000000 or 0)
try:
    import epoll
    DefaultPoller = EpollPoller
except ImportError:
    DefaultPoller = SelectPoller            
