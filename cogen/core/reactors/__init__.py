"""
Network polling code.

The reactor works in tandem with the socket operations.
Here's the basic workflow:

* the coroutine yields a operation

* the scheduler runs that operation (the `process 
  <cogen.core.events.Operation.html#method-process>`_ method)
  Note: all the socket operations share the same `process method
  <cogen.core.sockets.SocketOperation.html#method-process>`_. 
  
  * if run_first is False then the operation is added in the reactor for 
    polling (with the exception that if we have data in out internal buffers
    the operation is runned first)
  
  * if run_first is set (it's default) in the operation then in process 
    method the reactor's `run_or_add 
    <cogen.core.reactors.ReactorBase#method-run_or_add>`_ is called with the 
    operation and coroutine

  
Note: run_first is a optimization hack really, first it tries to run the
operation (this asumes the sockets are usualy ready) and if it raises any 
exceptions like EAGAIN, EWOULDBLOCK etc it adds that operation for polling 
(via select, epoll, kqueue etc) then the run method will be called only when 
select, epoll, kqueue says that the socket is ready.
"""

def has_select():
    try:
        import select
        import select_reactor
        return select_reactor.SelectReactor
    except ImportError:
        pass
    

def has_poll():
    try:
        import select
        if select and hasattr(select, 'poll'):
            import poll_reactor
            return poll_reactor.PollReactor
    except ImportError:
        pass
    

def has_epoll():
    try:
        import epoll
        import epoll_reactor
        return epoll_reactor.EpollReactor
    except ImportError:
        pass

def has_kqueue():
    try:
        import kqueue
        if kqueue.PYKQ_VERSION.split('.')[0] != '2':
            raise ImportError("%s too old."%kqueue.PYKQ_VERSION)
        import kqueue_reactor
        return kqueue_reactor.KQueueReactor
    except ImportError:
        pass

def has_iocp():
    try:
        import win32file
        import win32event
        import win32api
        import pywintypes
        import socket
        import ctypes
        import struct       
        import iocp_proactor
        return iocp_proactor.IOCPProactor
    except ImportError:
        pass
        
def has_qt():
    try:
        from PyQt4.QtCore import QSocketNotifier, QObject, QTimer, QCoreApplication
        from PyQt4.QtCore import SIGNAL
        import qt_reactor
        return qt_reactor.QtReactor
    except ImportError:
        pass

def get_first(*imps):
    for imp in imps:
        reactor = imp()
        if reactor:
            return reactor

def has_any():
    return get_first(has_iocp, has_kqueue, has_epoll, has_poll, has_select, has_qt)

DefaultReactor = has_any()
