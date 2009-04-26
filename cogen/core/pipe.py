"""An unidirectional pipe.

Your average example::

    @coro
    def iterator():
        iterator = yield Iterate(producer)
        while 1:
            val = yield iterator
            if val is sentinel:
                break
            # do something with val
        
    @coro
    def producer():
        for i in xrange(100):
            yield chunk(i)

        

"""
from __future__ import with_statement

from cogen.core import events, coroutines

class IterationStopped(Exception):
    pass

class IteratedCoroutineInstance(coroutines.CoroutineInstance):
    __slots__ = ('iter_token',)
    def run_op(self, op, sched):
        rop = super(IteratedCoroutineInstance, self).run_op(op, sched)
        if isinstance(rop, chunk):
            if self.iter_token:
                self.iter_token.data = rop
                return self.iter_token
        return rop    

class IterateToken(events.Operation):
    def __init__(self, iterator):
        self.iterator = iterator
        self.abort = False
        self.started = False
        self.ended = False
        self.data = None

        
        coro, args, kwargs = iterator.iterated_coro
        coro.constructor = IteratedCoroutineInstance
        self.coro = coro(*args, **kwargs)
        self.coro.iter_token = self
    
    def finalize(self, sched):
        if self.started:
            assert self.data
            data = self.data.value
            self.data = None
            return data
        else:
            self.started = True
            return self
    
    #~ from cogen.core.util import debug
    #~ @debug(0)
    def process(self, sched, coro):
        if self.abort:
            if self.ended:
                return self.iterator, coro
            else:
                self.ended = True
                self.coro.remove_waiter(coro, self.iterator)
                
                sched.active.appendleft((
                    coroutines.CoroutineException(
                        IterationStopped, 
                        IterationStopped(),
                        None
                    ), 
                    self.coro
                ))
                return self.iterator, coro
        else:
            if self.ended:
                return None, coro
            else:
                if coro is self.coro:
                    return self, self.iterator.coro
                else:
                    return None, self.coro
    
    def stop(self):
        self.abort = True
        self.coro.iter_token = None
        
        return self
        
class chunk(object):
    __slots__ = ('value',)
    def __init__(self, data):
        self.value = data

class chunk_sentinel(object):
    pass    

sentinel = end_sentinel = chunk_sentinel()

class Iterate(events.Operation):
    def __init__(self, coro, args=(), kwargs={}, sentinel=sentinel):
        super(Iterate, self).__init__()
        self.iterated_coro = coro, args, kwargs
        self.started = False
        self.sentinel = sentinel
        self.chunk = IterateToken(self)
        
    def finalize(self, sched):
        self.chunk.ended = True
        return self.sentinel
        
    def process(self, sched, coro):
        assert not self.started
        self.started = True
        self.coro = coro
        self.chunk.coro.add_waiter(coro, self)
        return self.chunk, self.coro
    

