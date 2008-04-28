__all__ = ['PublishSubscribeQueue']
from cogen.core import events
from cogen.core.util import priority

class PSPut(events.Operation):
    __slots__ = ['queue', 'message']
    
    def __init__(self, queue, message, **kws):
        super(PSPut, self).__init__(**kws)
        self.queue = queue
        self.message = message
    
    def process(self, sched, coro):
        super(PSPut, self).process(sched, coro)
        self.queue.messages.append(self.message)
        result = [self.message]
        for getcoro in self.queue.active_subscribers:
            self.queue.subscribers[getcoro] += 1
            getop = self.queue.active_subscribers[getcoro]
            getop.result = result
            if getop.prio:
                sched.active.appendleft((getop, getcoro))
            else:
                sched.active.append((getop, getcoro))
        self.queue.active_subscribers.clear()
        if self.prio & priority.CORO:
            return self, coro
        else:
            if self.prio & priority.OP:
                sched.active.appendleft((self, coro))
            else:
                sched.active.append((self, coro))
            return None, None
class PSGet(events.TimedOperation):
    __slots__ = ['queue', 'result']
    
    def __init__(self, queue, **kws):
        super(PSGet, self).__init__(**kws)
        self.queue = queue
    
    def process(self, sched, coro):
        super(PSGet, self).process(sched, coro)
        assert coro in self.queue.subscribers
        level = self.queue.subscribers[coro]
        queue_level = len(self.queue.messages)
        if level < queue_level:
            self.result = self.queue.messages[level:] if level \
                          else self.queue.messages  
            self.queue.subscribers[coro] = queue_level
            return self, coro
        else:
            self.queue.active_subscribers[coro] = self
    
    def finalize(self):
        super(PSGet, self).finalize()
        return self.result
        
    def cleanup(self, sched, coro):
        if coro in self.queue.active_subscribers:
            del self.queue.active_subscribers[coro]
            return True

class PSSubscribe(events.Operation):
    __slots__ = ['queue']
    
    def __init__(self, queue, **kws):
        super(PSSubscribe, self).__init__(**kws)
        self.queue = queue
    
    def process(self, sched, coro):
        super(PSSubscribe, self).process(sched, coro)
        self.queue.subscribers[coro] = 0
        return self, coro
    
class PublishSubscribeQueue:
    """A more robust replacement for the signal operations.
    A coroutine subscribes itself to a PublishSubscribeQueue and get new
    published messages with _fetch_ method.
    """
    def __init__(self):
        self.messages = []
        self.subscribers = {}
        self.active_subscribers = {}
        
    def publish(self, message, **kws):
        """Put a message in the queue and updates any coroutine wating with 
        fetch. *works as a coroutine operation*"""
        return PSPut(self, message, **kws)
    
    def subscribe(self, **kws):
        """Registers the calling coroutine to the queue. Sets the update index 
        to 0 - on fetch, that coroutine will get all the messages from the
        queue. *works as a coroutine operation*"""
        return PSSubscribe(self, **kws)
    
    def fetch(self, **kws):
        """Get all the new messages since the last fetch. Returns a list
        of messages. *works as a coroutine operation*"""
        return PSGet(self, **kws)
    
    def compact(self):
        """Compacts the queue: removes all the messages from the queue that
        have been fetched by all the subscribed coroutines. 
        Returns the number of messages that have been removed."""
        if self.subscribers:
            level = min(self.subscribers.itervalues())
            if level:
                del self.messages[:level]
            return level
        else:
            level = len(self.messages)
            del self.messages[:]
            return level