
import socket
import select
import collections
import time
import sys
import traceback
import types
import datetime
import heapq
from cStringIO import StringIO


from coroutine import coroutine
from pollers import DefaultPoller
import events
import sockets
class Priority:            
    LAST  = NOPRIO = 0
    CORO  = 1
    OP    = 2
    FIRST = PRIO = 3
    
class Scheduler:
    def __init__(t, poller=DefaultPoller, default_priority=Priority.LAST):
        t.active = collections.deque()
        t.sigwait = collections.defaultdict(collections.deque)
        t.diewait = collections.defaultdict(collections.deque)
        t.timewait = [] # heapq
        t.calls = {}
        t.poll = poller()
        t.idle = 0
        t.timerc = 1
        t.default_priority = default_priority
        
    def _init_coro(t, coro, *args, **kws):
        return coro(*args, **kws)
            
    def add(t, coro, *args, **kws):
        coro = t._init_coro(coro, *args, **kws)
        t.active.append( (None, coro) )
        return coro
        
    def add_first(t, coro, *args, **kws):
        coro = t._init_coro(coro, *args, **kws)
        t.active.appendleft( (None, coro) )
        return coro
        
    def run_timer(t):
        if t.timewait:
            now = datetime.datetime.now() 
            while t.timewait and t.timewait[0].wake_time <= now:
                op = heapq.heappop(t.timewait)
                t.active.appendleft((op, op.coro))
    
    def next_timer_delta(t): 
        if t.timewait and not t.active:
            return (datetime.datetime.now() - t.timewait[0].wake_time).microseconds
        else:
            if t.active:
                return None
            else:
                return -1
    def run_poller(t):
        for ev in t.poll.run(timeout = t.next_timer_delta()):
            #~ print "EVENT:",ev
            obj, coro = ev
            t.active.appendleft( ev )

    def run_ops(t, prio, coro, op):
        #~ print '-run_op', prio,coro,op
        if isinstance(op, sockets.ops):
        #~ if op.__class__ in sockets.ops:
            r = t.poll.add(op, coro)
            if r:
                #~ print '\n>>r', prio, coro, op, r
                if prio:
                    return coro, r
                else:
                    t.active.appendleft((r, coro))
        elif isinstance(op, events.Pass):
            #~ print "Passing %r %r" % (op.coro, op.op)
            return op.coro, op.op
        elif isinstance(op, events.AddCoro):
            if prio&Priority.OP:
                t.add_first(*op.args)
            else:
                t.add(*op.args)
                
            if prio&Priority.CORO:
                return coro, op
            else:
                t.active.append( (None, coro))
        elif isinstance(op, events.Complete):
            if prio:
                t.active.extendleft(op.args)
            else:
                t.active.extend(op.args)
        elif isinstance(op, events.WaitForSignal):
            t.sigwait[op.name].append((op, coro))
        elif isinstance(op, events.Signal):
            if prio&Priority.OP:
                t.active.extendleft(t.sigwait[op.name])
            else:
                t.active.extend(t.sigwait[op.name])
            
            if prio&Priority.CORO:
                t.active.appendleft((None, coro))
            else:
                t.active.append((None, coro))
                
            del t.sigwait[op.name]
        elif isinstance(op, events.Call):
            if prio:
                callee = t.add_first(*op.args, **op.kws)
            else:
                callee = t.add(*op.args, **op.kws) 
            callee.caller = coro
            callee.prio = prio
            del callee
        elif isinstance(op, events.Join):
            op.coro.add_waiter(coro)
        elif isinstance(op, events.Sleep):
            op.coro = coro
            heapq.heappush(t.timewait, op)
        else:
            if not prio:
                t.active.append((op, coro))
        return None, None
        
    def run(t):
        #~ try:
            while t.active or t.poll or t.timewait:
                if t.active:
                    _op, coro = t.active.popleft()
                    while True:
                        #~ print ">Sending %s to coro %s, " % (_op, coro),
                        op = coro.run_op(_op)
                        #~ print op, "returned."
                        if op is None:
                            t.active.append((op, coro))
                            break
                        prio = t.default_priority
                        if isinstance(op, types.TupleType):
                            try:
                                prio, op = op
                            except ValueError:
                                t.run_coro(t, coro, Exception("Bad op"))
                        coro, _op = t.run_ops(prio, coro, op)
                        if not _op:
                            break  
                        
                t.run_poller()
                t.run_timer()
        #~ except:
            #~ import pdb
            #~ pdb.pm()
        #~ print 'SCHEDULER IS DEAD'
if __name__ == "__main__":
    
    def coro1(*args):
        print "coro1 start, args:", args
        for i in range(10):
            print "coro1:",i
            yield i
            op = yield events.Call(coro2)
            print 'coro1: coro2 returns:', op.returns
            yield op.returns
        
            
    def coro2():
        print "coro2 start"
        for i in range(10):
            if i%2==0:
                print 'coro2: %s, sending sig "x"' % i
                yield events.Signal(name='x')
                yield i
            else:
                print "coro2:",i
                yield i
            
    def coro3():
        while m.active:
            print 'coro3: wait for sig "x"'
            (yield events.WaitForSignal(name='x'))        
            print 'coro3: recieved "x"'
    def coro4():
        print 'coro4: start'
        op = yield events.Call(coro1, '123', 'mumu')
        print 'coro1 returns:', op.returns
        print 'coro4: end'
        yield "MUMU"
    def coro5():
        print 'coro5: wait to join coro4'
        op = yield events.Join(coro4_instance)
        print 'coro5: coro4 died, returns:', op.returns
    @coroutine            
    def coroA():
        print "coroA start"
        for i in range(10):
            yield events.Sleep(datetime.timedelta(milliseconds=1))
            print "coroA:",i
            yield i
        print "coroA END"
        
    @coroutine
    def coroB():
        print "coroB start"
        for i in range(10):
            yield events.Sleep(datetime.timedelta(milliseconds=1))
            print "coroB:",i
            yield i
        print "coroB END"
        
    @coroutine
    def coroC():
        print "coroC start"
        yield events.Sleep(datetime.timedelta(milliseconds=1000))
        print "coroC END"
        
    m = Scheduler()
    #~ m.add(coro1)
    #~ m.add(coro2)
    #~ m.add(coro3)
    #~ coro4_instance = m.add(coro4)
    #~ m.add(coro5)
    m.add(coroA)
    m.add(coroB)
    m.add(coroC)
    def A():
        yield 'a'
        yield 'A'
        return
    def B():
        yield 'b'
        raise StopIteration('B')
    def T():
        print "call to A returns: %r"%(yield events.Call(A)).returns
        print "call to B returns: %r"%(yield events.Call(B)).returns
    #~ m.add(T)
    m.run()

    #~ print isinstance(sockets.Read(),(sockets.Read,sockets.Read,sockets.Write,sockets.Accept))
