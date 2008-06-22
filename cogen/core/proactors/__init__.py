"""
Network polling code.

The proactor works in tandem with the socket operations.
Here's the basic workflow:

* the coroutine yields a operation

* the scheduler runs that operation (the `process 
  <cogen.core.events.Operation.html#method-process>`_ method)
  Note: all the socket operations share the same `process method
  <cogen.core.sockets.SocketOperation.html#method-process>`_. 
  
  * if run_first is False then the operation is added in the proactor for 
    polling (with the exception that if we have data in out internal buffers
    the operation is runned first)
  
  * if run_first is set (it's default) in the operation then in process 
    method the proactor's `run_or_add 
    <cogen.core.proactors.proactorBase#method-run_or_add>`_ is called with the 
    operation and coroutine

  
Note: run_first is a optimization hack really, first it tries to run the
operation (this asumes the sockets are usualy ready) and if it raises any 
exceptions like EAGAIN, EWOULDBLOCK etc it adds that operation for polling 
(via select, epoll, kqueue etc) then the run method will be called only when 
select, epoll, kqueue says that the socket is ready.
"""

def has_select():
    #~ try:
        import select
        import select_impl
        return select_impl.SelectProactor
    #~ except ImportError:
        #~ pass
    

def has_poll():
    try:
        import select
        if select and hasattr(select, 'poll'):
            import poll_impl
            return poll_impl.PollProactor
    except ImportError:
        pass
    

def has_epoll():
    try:
        import epoll
        import epoll_impl
        return epoll_impl.EpollProactor
    except ImportError:
        pass

def has_kqueue():
    try:
        import kqueue
        if kqueue.PYKQ_VERSION.split('.')[0] != '2':
            raise ImportError("%s too old."%kqueue.PYKQ_VERSION)
        import kqueue_impl
        return kqueue_impl.KQueueProactor
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
        import iocp_impl
        return iocp_impl.IOCPProactor
    except ImportError:
        pass
        
def get_first(*imps):
    for imp in imps:
        proactor = imp()
        if proactor:
            return proactor

def has_any():
    return get_first(has_epoll, has_select)
    #, has_iocp, has_kqueue, has_epoll, has_poll, has_select)

DefaultProactor = has_any()
