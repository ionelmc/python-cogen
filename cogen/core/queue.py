"""
Port of Queue.Queue from the python standard library.
"""
__all__ = ['Full', 'Empty', 'Queue']
import collections
import events

from util import priority


class Full(Exception):
    pass
class Empty(Exception):
    pass
class QGet(events.TimedOperation):
    "A operation for the queue get call."
    __slots__ = ['queue', 'block', 'caller', 'result', 'waiting']
    def __init__(self, queue, block, **kws):
        super(QGet, self).__init__(**kws)
        self.queue = queue
        self.block = block
        self.caller = None
        self.result = None
        self.waiting = False
        
    def finalize(self):
        super(QGet, self).finalize()
        return self.result
        
    def cleanup(self, sched, coro):
        if self.waiting:
            self.queue.waiting_gets.remove(self)
            return True

    def process(self, sched, coro):
        super(QGet, self).process(sched, coro)
        self.caller = coro
        if self.queue._empty():
            if self.block:
                self.queue.waiting_gets.append(self)
                self.waiting = True
            else:
                raise Empty
        else:
            self.result = self.queue._get()
            if self.queue.waiting_puts:
                while not self.queue.full():
                    putop = self.queue.waiting_puts.popleft()
                    putop.waiting = False
                    self.queue._put(putop.item)
                    if putop.prio & priority.CORO:
                        if putop.prio & priority.OP:
                            sched.active.appendleft((self, coro))
                        else:
                            sched.active.append((self, coro))

                        return putop, putop.caller
                    else:
                        if putop.prio & priority.OP:
                            sched.active.appendleft((putop, putop.caller))
                        else:
                            sched.active.append((putop, putop.caller))
            return self, coro
    def __repr__(self):
        return "<%s@%X caller:%s block:%s result:%s>" % (
            self.__class__.__name__,
            id(self),
            self.caller,
            self.block,
            self.result
        )
        
class QPut(events.TimedOperation):
    "A operation for the queue put call."
    __slots__ = ['queue', 'item', 'block', 'caller', 'result', 'waiting']
    def __init__(self, queue, item, block, **kws):
        super(QPut, self).__init__(**kws)
        self.queue = queue
        self.item = item
        self.block = block
        self.caller = None
        self.waiting = False

    def cleanup(self, sched, coro):
        if self.waiting:
            self.queue.waiting_puts.remove(self)
            return True

    def process(self, sched, coro):
        super(QPut, self).process(sched, coro)
        self.caller = coro
        if self.queue._full():
            if self.block:
                self.queue.unfinished_tasks += 1
                self.queue.waiting_puts.append(self)
                self.waiting = True
            else:
                raise Full
        else:
            self.queue.unfinished_tasks += 1
            if self.queue.waiting_gets:
                getop = self.queue.waiting_gets.popleft()
                getop.result = self.item
                getop.waiting = False
                if self.prio:
                    if self.prio & priority.CORO:
                        sched.active.appendleft((self, coro))
                    else:
                        sched.active.append((self, coro))
                    return getop, getop.caller
                else:
                    if getop.prio:
                        sched.active.appendleft((getop, getop.caller))
                    else:
                        sched.active.append((getop, getop.caller))
                    return self, coro
                    
            else:
                self.queue._put(self.item)
                return self, coro
    def __repr__(self):
        return "<%s@%X caller:%s block:%s item:%s>" % (
            self.__class__.__name__,
            id(self),
            self.caller,
            self.block,
            self.item
        )
                
        
class QDone(events.Operation):
    "A operation for the queue done_task call"
    __slots__ = ['queue']
    
    def __init__(self, queue, **kws):
        super(QDone, self).__init__(**kws)
        self.queue = queue
        
    def process(self, sched, coro):
        super(QDone, self).process(sched, coro)
        if self.queue.joinees:
            if self.prio & priority.OP:
                sched.active.extendleft(self.queue.joinees)
            else:
                sched.active.extend(self.queue.joinees)
        return self, coro
        
class QJoin(events.Operation):
    "A operation for the queue join call."
    __slots__ = ['queue']
    
    def __init__(self, queue, **kws):
        super(QJoin, self).__init__(**kws)
        self.queue = queue
        
    def process(self, sched, coro):
        super(QJoin, self).process(sched, coro)
        if self.queue.unfinished_tasks == 0:
            return self, coro
        else:
            self.queue.joinees.append( (self, coro) )
            
class Queue:
    """This class attempts to mimic the exact functionality of the 
    python standard library Queue.Queue class, but with a coroutine context:
    
    * the queue calls return coroutine operations
    
    So, to use this you write someting like:
    
    {{{
    @coroutine
    def foo():
        q = cogen.core.queue.Queue(<size>)
        yield q.put(123)
        val = yield q.get()
    }}}
    """
    def __init__(self, maxsize=0):
        self._init(maxsize)
        self.waiting_puts = collections.deque()
        self.waiting_gets = collections.deque()
        self.unfinished_tasks = 0
        self.joinees = []
        
    def __repr__(self):
        return "<%s %s wput:%s wget:%s>" % (
            self.__class__,
            self._repr(),
            self.waiting_puts,
            self.waiting_gets
        )
            
    def task_done(self, **kws):
        """Indicate that a formerly enqueued task is complete.

        Used by Queue consumer threads.  For each get() used to fetch a task,
        a subsequent call to task_done() tells the queue that the processing
        on the task is complete.

        If a join() is currently blocking, it will resume when all items
        have been processed (meaning that a task_done() call was received
        for every item that had been put() into the queue).

        Raises a ValueError if called more times than there were items
        placed in the queue.
        """
        unfinished = self.unfinished_tasks - 1
        op = None
        if unfinished <= 0:
            if unfinished < 0:
                raise ValueError('task_done() called too many times')
            op = QDone(self, **kws)
        self.unfinished_tasks = unfinished
        return op
        
    def join(self):
        """Blocks until all items in the Queue have been gotten and processed.

        The count of unfinished tasks goes up whenever an item is added to the
        queue. The count goes down whenever a consumer thread calls task_done()
        to indicate the item was retrieved and all work on it is complete.

        When the count of unfinished tasks drops to zero, join() unblocks.
        """
        if self.unfinished_tasks:
            return QJoin(self)
        
    def qsize(self):
        """Return the approximate size of the queue (not reliable!)."""
        return self._qsize()
        
    def empty(self):
        """Return True if the queue is empty, False otherwise (not reliable!)."""
        return self._empty()

    def full(self):
        """Return True if the queue is full, False otherwise (not reliable!)."""
        return self._full()
    
    def put(self, item, block=True, **kws):
        """Put an item into the queue.

        If optional args 'block' is true and 'timeout' is None (the default),
        block if necessary until a free slot is available. If 'timeout' is
        a positive number, it blocks at most 'timeout' seconds and raises
        the Full exception if no free slot was available within that time.
        Otherwise ('block' is false), put an item on the queue if a free slot
        is immediately available, else raise the Full exception ('timeout'
        is ignored in that case).
        """
        return QPut(self, item, block, **kws)
    
    def put_nowait(self, item):
        """Put an item into the queue without blocking.

        Only enqueue the item if a free slot is immediately available.
        Otherwise raise the Full exception.
        """
        return self.put(item, False)
    
    def get(self, block=True, **kws):
        """Remove and return an item from the queue.

        If optional args 'block' is true and 'timeout' is None (the default),
        block if necessary until an item is available. If 'timeout' is
        a positive number, it blocks at most 'timeout' seconds and raises
        the Empty exception if no item was available within that time.
        Otherwise ('block' is false), return an item if one is immediately
        available, else raise the Empty exception ('timeout' is ignored
        in that case).
        """
        return QGet(self, block, **kws)
    
    def get_nowait(self):
        """Remove and return an item from the queue without blocking.

        Only get an item if one is immediately available. Otherwise
        raise the Empty exception.
        """
        return self.get(False)
            
        
    # Override these methods to implement other queue organizations
    # (e.g. stack or priority queue).
    # These will only be called with appropriate locks held

    # Initialize the queue representation
    def _init(self, maxsize):
        self.maxsize = maxsize
        self.queue = collections.deque()

    def _qsize(self):
        return len(self.queue)

    # Check whether the queue is empty
    def _empty(self):
        return not self.queue

    # Check whether the queue is full
    def _full(self):
        return self.maxsize > 0 and len(self.queue) == self.maxsize

    # Put a new item in the queue
    def _put(self, item):
        self.queue.append(item)

    # Get an item from the queue
    def _get(self):
        return self.queue.popleft()
    
    def _repr(self):
        return repr(self.queue)

