__all__ = ['PublishSubscribeQueue']
import events
from util import priority

class PSPut(events.Operation):
    __slots__ = ('queue', 'message', 'key')
    
    def __init__(self, queue, message, key, **kws):
        super(PSPut, self).__init__(**kws)
        self.queue = queue
        self.message = message
        self.key = key
    
    def process(self, sched, coro):
        super(PSPut, self).process(sched, coro)
        self.queue.messages.append(self.message)
        result = [self.message]
        key = self.key or coro
        for getkey in self.queue.active_subscribers:
            self.queue.subscribers[getkey] += 1
            getop, getcoro = self.queue.active_subscribers[getkey]
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
    __slots__ = ('queue', 'result', 'key')
    
    def __init__(self, queue, key, **kws):
        super(PSGet, self).__init__(**kws)
        self.queue = queue
        self.key = key
    
    def process(self, sched, coro):
        super(PSGet, self).process(sched, coro)
        key = self.key or coro
        assert key in self.queue.subscribers
        level = self.queue.subscribers[key]
        queue_level = len(self.queue.messages)
        if level < queue_level:
            self.result = self.queue.messages[level:] if level \
                          else self.queue.messages  
            self.queue.subscribers[key] = queue_level
            return self, coro
        else:
            self.queue.active_subscribers[key] = self, coro
    
    def finalize(self):
        super(PSGet, self).finalize()
        return self.result
        
    def cleanup(self, sched, coro):
        if coro in self.queue.active_subscribers:
            del self.queue.active_subscribers[coro]
            return True

class PSSubscribe(events.Operation):
    __slots__ = ('queue', 'key')
    
    def __init__(self, queue, key, **kws):
        super(PSSubscribe, self).__init__(**kws)
        self.queue = queue
        self.key = key
    
    def process(self, sched, coro):
        super(PSSubscribe, self).process(sched, coro)
        self.queue.subscribers[self.key or coro] = 0
        return self, coro

class PSUnsubscribe(events.Operation):
    __slots__ = ('queue', 'key')
    
    def __init__(self, queue, key, **kws):
        super(PSUnsubscribe, self).__init__(**kws)
        self.queue = queue
        self.key = key
    
    def process(self, sched, coro):
        super(PSSubscribe, self).process(sched, coro)
        del self.queue.subscribers[self.key or coro]
        return self, coro


class PublishSubscribeQueue:
    """A more robust replacement for the signal operations.
    A coroutine subscribes itself to a PublishSubscribeQueue and get new
    published messages with _fetch_ method.
    """
    def __init__(self):
        self.messages = []
        self.subscribers = {}
        self.active_subscribers = {} # holds waiting fetch ops
        
    def publish(self, message, key=None, **kws):
        """Put a message in the queue and updates any coroutine wating with 
        fetch. *works as a coroutine operation*"""
        return PSPut(self, message, key, **kws)
    
    def subscribe(self, key=None, **kws):
        """Registers the calling coroutine to the queue. Sets the update index 
        to 0 - on fetch, that coroutine will get all the messages from the
        queue. *works as a coroutine operation*"""
        return PSSubscribe(self, key, **kws)
    
    def unsubscribe(self, key=None, **kws):
        """Unregisters the calling coroutine to the queue. """
        # TODO: unittest
        return PSUnsubscribe(self, key, **kws)
    
    def fetch(self, key=None, **kws):
        """Get all the new messages since the last fetch. Returns a list
        of messages. *works as a coroutine operation*"""
        return PSGet(self, key, **kws)
    
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