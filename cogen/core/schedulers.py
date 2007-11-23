
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


from coroutine import coroutine, Coroutine
from pollers import DefaultPoller, Socket
import events as Events
            
class Scheduler:
    default_prio = None
    def __init__(t, poller=DefaultPoller):
        t.active = collections.deque()
        t.sigwait = collections.defaultdict(collections.deque)
        t.diewait = collections.defaultdict(collections.deque)
        t.timewait = [] # heapq
        t.calls = {}
        t.poll = poller()
        t.idle = 0
        t.timerc = 1
        
            
    def add(t, coro, *args, **kws):
        assert hasattr(coro, 'run_op')
        t.active.append( (None, coro) )
        return coro
        
    def add_first(t, coro, *args, **kws):
        assert hasattr(coro, 'run_op')
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
        if isinstance(op, Socket.ops):
        #~ if op.__class__ in Socket.ops:
            r = t.poll.add(op, coro)
            if r:
                #~ print '\n>>r', prio, coro, op, r
                if prio:
                    return r
                else:
                    t.active.appendleft((r, coro))
        elif isinstance(op, Events.AddCoro):
            #~ print '-', op.args
            for i in op.args:
                if isinstance(i, Coroutine):
                    i = (None, i)
                if prio:
                    t.active.appendleft(i)
                else:
                    t.active.append(i)
            if op.keep_running:
                if prio:
                    return op
                else:
                    t.active.append( (None, coro))
        elif isinstance(op, Events.WaitForSignal):
            t.sigwait[op.name].append((op, coro))
        elif isinstance(op, Events.Signal):
            if prio:
                t.active.appendleft((None, coro))
                t.active.extendleft(t.sigwait[op.name])
            else:
                t.active.extend(t.sigwait[op.name])
                t.active.append((None, coro))
            del t.sigwait[op.name]
        elif isinstance(op, Events.Call):
            if prio:
                t.calls[ t.add_first(*op.args, **op.kws) ] = op, coro
            else:
                t.calls[ t.add(*op.args, **op.kws) ] = op, coro
        elif isinstance(op, Events.Join):
            t.diewait[ op.coro ].append((op, coro))
        elif isinstance(op, Events.Sleep):
            op.coro = coro
            heapq.heappush(t.timewait, op)
        else:
            if not prio:
                t.active.append((op, coro))        
    def run(t):
        while t.active or t.poll or t.timewait:
            if t.active:
                #~ print '>',t.active[0]
                _op, coro = t.active.popleft()
                while True:
                    op = coro.run_op(_op)
                    #~ print "Sending %s to coro %s, %s returned." % (_op, coro, op)
                    if op is None:
                        t.active.append((op, coro))
                        break
                    prio = t.default_prio
                    if isinstance(op, types.TupleType):
                        try:
                            prio, op = op
                        except ValueError:
                            #~ print 'fuck'
                            t.run_coro(t, coro, Exception("Bad op"))
                    #~ if op:
                    _op = t.run_ops(prio, coro, op)
                    #~ print ">_OP", op, _op
                    if not _op:
                        break  
                    #~ else:
                        #~ break
            t.run_poller()
            t.run_timer()
        #~ print 'SCHEDULER IS DEAD'
if __name__ == "__main__":
    
    def coro1(*args):
        print "coro1 start, args:", args
        for i in range(10):
            print "coro1:",i
            yield i
            op = yield Events.Call(coro2)
            print 'coro1: coro2 returns:', op.returns
            yield op.returns
        
            
    def coro2():
        print "coro2 start"
        for i in range(10):
            if i%2==0:
                print 'coro2: %s, sending sig "x"' % i
                yield Events.Signal(name='x')
                yield i
            else:
                print "coro2:",i
                yield i
            
    def coro3():
        while m.active:
            print 'coro3: wait for sig "x"'
            (yield Events.WaitForSignal(name='x'))        
            print 'coro3: recieved "x"'
    def coro4():
        print 'coro4: start'
        op = yield Events.Call(coro1, '123', 'mumu')
        print 'coro1 returns:', op.returns
        print 'coro4: end'
        yield "MUMU"
    def coro5():
        print 'coro5: wait to join coro4'
        op = yield Events.Join(coro4_instance)
        print 'coro5: coro4 died, returns:', op.returns
    @coroutine            
    def coroA():
        print "coroA start"
        for i in range(10):
            yield Events.Sleep(datetime.timedelta(milliseconds=1))
            print "coroA:",i
            yield i
        print "coroA END"
        
    @coroutine
    def coroB():
        print "coroB start"
        for i in range(10):
            yield Events.Sleep(datetime.timedelta(milliseconds=1))
            print "coroB:",i
            yield i
        print "coroB END"
        
    @coroutine
    def coroC():
        print "coroC start"
        yield Events.Sleep(datetime.timedelta(milliseconds=1000))
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
        print "call to A returns: %r"%(yield Events.Call(A)).returns
        print "call to B returns: %r"%(yield Events.Call(B)).returns
    #~ m.add(T)
    m.run()

    #~ print isinstance(Socket.Read(),(Socket.Read,Socket.Read,Socket.Write,Socket.Accept))
