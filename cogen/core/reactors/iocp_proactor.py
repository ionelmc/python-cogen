from __future__ import division
import win32file
import win32event
import win32api
import pywintypes
import socket
import ctypes
import struct    

from base import ReactorBase
from cogen.core.util import priority
from cogen.core import events

class IOCPProactor(ReactorBase):
    def __init__(self, scheduler, res):
        super(self.__class__, self).__init__(scheduler, res)
        self.scheduler = scheduler
        self.iocp = win32file.CreateIoCompletionPort(
            win32file.INVALID_HANDLE_VALUE, None, 0, 0
        ) 
        self.fds = set()
        self.registered_ops = {}
        
    def __len__(self):
        return len(self.registered_ops)
    def __del__(self):
        win32file.CloseHandle(self.iocp)
        
    def __repr__(self):
        return "<%s@%s reg_ops:%r fds:%r>" % (
            self.__class__.__name__, 
            id(self), 
            self.registered_ops, 
            self.fds
        )
    def add(self, op, coro):
        fileno = op.sock._fd.fileno()
        
        if fileno not in self.fds:
            # silly CreateIoCompletionPort raises a exception if the 
            #fileno(handle) has already been registered with the iocp
            self.fds.add(fileno)
            win32file.CreateIoCompletionPort(fileno, self.iocp, 0, 0) 
        
        self.registered_ops[op] = self.run_iocp(op, coro)
        
    def run_iocp(self, op, coro):
        overlap = pywintypes.OVERLAPPED() 
        overlap.object = (op, coro)
        rc, nbytes = op.iocp(overlap)
        
        if rc == 0:
            # ah geez, it didn't got in the iocp, we have a result!
            win32file.PostQueuedCompletionStatus(
                self.iocp, nbytes, 0, overlap
            )
            # or we could just do it here, but this will get recursive, 
            #(todo: config option for this)
            #~ self.process_op(rc, nbytes, op, coro, overlap)
        return overlap

    def process_op(self, rc, nbytes, op, coro, overlap):
        overlap.object = None
        if rc == 0:
            op.iocp_done(rc, nbytes)
            prev_op = op
            op = self.run_operation(op, False) #no reactor, but proactor
            # result should be the same instance as prev_op or a coroutine exception
            if op:
                del self.registered_ops[prev_op] 
                
                win32file.CancelIo(prev_op.sock._fd.fileno()) 
                return op, coro
            else:
                # operation hasn't completed yet (not enough data etc)
                # read it in the iocp
                self.registered_ops[prev_op] = self.run_iocp(prev_op, coro)
                
        else:
            #looks like we have a problem, forward it to the coroutine.
            
            # this needs some research: ERROR_NETNAME_DELETED, need to reopen 
            #the accept sock ?! something like:
            #    warnings.warn("ERROR_NETNAME_DELETED: %r. Re-registering operation." % op)
            #    self.registered_ops[op] = self.run_iocp(op, coro)
            del self.registered_ops[op]
            win32file.CancelIo(op.sock._fd.fileno())
            return events.CoroutineException((
                events.ConnectionError, events.ConnectionError(
                    (rc, "%s on %r" % (ctypes.FormatError(rc), op))
                )
            )), coro

    def waiting_op(self, testcoro):
        for op in self.registered_ops:
            if self.registered_ops[op].object[1] is testcoro:
                return op
    
    def remove(self, op, coro):
        if op in self.registered_ops:
            self.registered_ops[op].object = None
            win32file.CancelIo(op.sock._fd.fileno())
            del self.registered_ops[op]
            return True

    def run(self, timeout = 0):
        # same resolution as epoll
        ptimeout = int(
            timeout.days * 86400000 + 
            timeout.microseconds / 1000 +
            timeout.seconds * 1000 
            if timeout else (self.m_resolution if timeout is None else 0)
        )
        if self.registered_ops:
            urgent = None
            # we use urgent as a optimisation: the last operation is returned 
            #directly to the scheduler (the sched might just run it till it 
            #goes to sleep) and not added in the sched.active queue
            while 1:
                try:
                    rc, nbytes, key, overlap = win32file.GetQueuedCompletionStatus(
                        self.iocp,
                        0 if urgent else ptimeout
                    )
                except RuntimeError:
                    # we will get "This overlapped object has lost all its 
                    # references so was destroyed" when we remove a operation, 
                    # it is garbage collected and the overlapped completes
                    # afterwards
                    break 
                    
                # well, this is a bit weird, if we get a aborted rc (via CancelIo
                #i suppose) evaluating the overlap crashes the interpeter 
                #with a memory read error
                if rc != win32file.WSA_OPERATION_ABORTED and overlap:
                    
                    if urgent:
                        op, coro = urgent
                        urgent = None
                        if op.prio & priority.OP:
                            # imediately run the asociated coroutine step
                            op, coro = self.scheduler.process_op(
                                coro.run_op(op), 
                                coro
                            )
                        if coro:
                            if op.prio & priority.CORO:
                                self.scheduler.active.appendleft( (op, coro) )
                            else:
                                self.scheduler.active.append( (op, coro) )                     
                    if overlap.object:
                        op, coro = overlap.object
                        urgent = self.process_op(rc, nbytes, op, coro, overlap)
                else:
                    break
            return urgent
        else:
            time.sleep(self.resolution)    
