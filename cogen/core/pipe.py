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
    def run_op(self, op):
        rop = super(IteratedCoroutineInstance, self).run_op(op)
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
    
    def finalize(self):
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
        
    def finalize(self):
        self.chunk.ended = True
        return self.sentinel
        
    def process(self, sched, coro):
        assert not self.started
        self.started = True
        self.coro = coro
        self.chunk.coro.add_waiter(coro, self)
        return self.chunk, self.coro
    

if __name__ == "__main__":
    from cogen.common import *
    from cogen.core.coroutines import debug_coro
    XXX = 10000

    @debug_coro
    #~ @coro
    def iterator():
        iterator = yield Iterate(producer)
        while 1:
            print "> not"
            val = yield iterator
            if val is sentinel:
                break
            if val > 2:
                yield iterator.stop()
                print "> breaking"
                #~ break
            #~ print val
        
        print "> BROKE"
        #~ yield events.Sleep(1)
        yield None
        #~ yield iterator
        yield None
        #~ yield events.Sleep(1)
        print "> >>>> EXIT"
    @coro
    def producer():
        for i in xrange(XXX):
            print '>', i
            yield chunk(i)
        yield chunk(None)
        
    s = Scheduler()
    import cogen
    q = cogen.core.queue.Queue()
        
    @coro 
    def getter():
        yield events.AddCoro(putter)
        while 1:
            val = yield q.get()
            if val is None:
                break
                
    @coroutine
    def putter():
        for i in xrange(XXX):
            #~ print '>', i
            yield q.put(i)
        yield q.put(None)

    #~ s.add(getter)
    s.add(iterator)
    import time
    t1 = time.time()
    s.run()
    print time.time()-t1

    #~ import cProfile, os
    #~ cProfile.run("s.run()", "cprofile.log")
    #~ #cProfile.run("normal_call()", "cprofile.log")
    #~ import pstats
    #~ for i in [
        #~ 'calls','cumulative','file','module',
        #~ 'pcalls','line','name','nfl','stdname','time'
        #~ ]:
        #~ stats = pstats.Stats("cprofile.log",
            #~ stream = file('cprofile.%s.%s.txt' % (
                    #~ os.path.split(__file__)[1],
                    #~ i
                #~ ),'w'
            #~ )
        #~ )
        #~ stats.sort_stats(i)
        #~ stats.print_stats()
    
    
    
    
    
    
    
    
    
    t1 = time.time()
    def a():
        for i in xrange(XXX):
            yield i
        yield None
    a=a()
    while 1:
        x=a.send(None)
        if x is None: break
    print time.time()-t1
    
    