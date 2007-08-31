# todo: remove errored coros

import socket
import select
import collections
import time
import sys
import traceback
import types
import datetime
import heapq
import exceptions
from cStringIO import StringIO
from poolers import DefaultPooler, Socket
from lib import *
import events as Events
            
            
class Scheduler:
    def __init__(t, pooler=DefaultPooler):
        t.active = collections.deque()
        t.sigwait = collections.defaultdict(collections.deque)
        t.diewait = collections.defaultdict(collections.deque)
        t.timewait = [] # heapq
        t.calls = {}
        t.pool = pooler()
        t.idle = 0
        t.timerc = 1
        
    def gen(t, coro, *args, **kws):
        if not type(coro)==types.GeneratorType: # just in case
            return coro(*args, **kws)
        else:
            return coro
    def add(t, coro, *args, **kws):
        #~ print '> Adding coro:',coro,
        coro = t.gen(coro, *args, **kws)
        #~ print ' gen:',coro
        assert coro
        t.active.append( (None, coro) )
        return coro

    def handle_error(t, coro, inner=None):        
        print 
        print '-'*40
        print 'Exception happened during processing of coroutine.'
        traceback.print_exc()
        print "   BTW, Coroutine #%s died. " % coro
        if isinstance(inner, exceptions.Exception):
            print ' -- Inner exception -- '
            traceback.print_exception(*inner.message)
            print ' --------------------- ' 
        else:
            print "Operation was: %s" % inner
        print '-'*40
    def run(t):
        while t.active or t.pool or t.timewait:
        #~ while 1:
            #~ print len(t.active), len(t.pool), len(t.timewait)
            if t.active:
                print len(t.active), len(t.calls), len(t.pool), t.next_timer_delta()
            
                _op, coro = t.active.popleft()
                try:
                    if isinstance(_op, exceptions.Exception):
                        op = coro.throw(*_op.message)
                    else:
                        op = coro.send(_op)                    
                    #~ print '!', coro, _op, op
                except StopIteration, e:
                    if t.calls.has_key(coro):
                        wakeup = t.calls[coro]
                        wakeup[0].returns = e.message
                        t.active.appendleft(wakeup)
                        del t.calls[coro]
                    if t.diewait.has_key(coro):
                        for wakeup in t.diewait[coro]:
                            wakeup[0].returns = e.message
                        t.active.extend(t.diewait[coro])
                        del t.diewait[coro]
                except:
                    t.handle_error(coro, _op)
                else:
                    if op.__class__ in Socket.ops:
                        #~ print '> add socket op:', op
                        r = t.pool.add(op, coro)
                        if r:
                            t.active.appendleft((r, coro))
                    elif isinstance(op, Events.WaitForSignal):
                        t.sigwait[op.name].append((op, coro))
                    elif isinstance(op, Events.Signal):
                        t.active.extend(t.sigwait[op.name])
                        t.active.append((None, coro))
                        del t.sigwait[op.name]
                    elif isinstance(op, Events.Call):
                        t.calls[ t.add(*op.args, **op.kws) ]= op, coro
                    elif isinstance(op, Events.Join):
                        t.diewait[ op.coro ].append((op, coro))
                    elif isinstance(op, Events.Sleep):
                        op.coro = coro
                        heapq.heappush(t.timewait, op)
                    else:
                        t.active.append((op, coro))
            t.run_pooler()
            t.run_timer()
    def run_timer(t):
        if t.timewait:
            now = datetime.datetime.now() 
            while t.timewait and t.timewait[0].wake_time <= now:
                op = heapq.heappop(t.timewait)
                t.active.appendleft((op, op.coro))
    def next_timer_delta(t): 
        #~ print t.active
        #~ t.timerc -= 1
        if t.timewait and not t.active:
            return (datetime.datetime.now() - t.timewait[0].wake_time).microseconds
        else:
            if t.active:
                return None
            else:
                return -1
    def run_pooler(t):
        for ev in t.pool.run(timeout = t.next_timer_delta()):
            #~ print "EVENT:",ev
            obj, coro = ev
            t.active.appendleft( ev )
class GreedyScheduler(Scheduler):
    def run(t):
        #~ print 'RUN'
        import win32console
        t.max_calls=0
        t.max_active=0
        #~ while t.active or t.pool or t.timewait:
        while 1:
            if t.active:
                _op, coro = t.active.popleft()
                op = None
                while True:
                    print len(t.active), len(t.calls), len(t.pool), t.next_timer_delta()
            
                    t.max_active |= len(t.active)
                    t.max_calls |= len(t.calls)
                    win32console.SetConsoleTitle("[active: %3d] [max active: %3d] [max call stack: %3d] [timer: %5s]" % (
                        len(t.active),
                        t.max_active, 
                        t.max_calls,
                        0
                    ))  
                    #~ print t.active, t.diewait
                    try:
                        if isinstance(_op, exceptions.Exception):
                            op = coro.throw(_op.message[0])
                        else:
                            op = coro.send(_op)
                        print '!', coro, _op, op
                        
                    except StopIteration, e:
                        print ">", repr(e)
                        if t.calls.has_key(coro):
                            wakeup = t.calls[coro]
                            wakeup[0].returns = e.message
                            t.active.appendleft(wakeup)
                            del t.calls[coro]
                            del wakeup
                        if t.diewait.has_key(coro):
                            for wakeup in t.diewait[coro]:
                                wakeup[0].returns = e.message
                            t.active.extendleft(t.diewait[coro])
                            del wakeup
                            del t.diewait[coro]
                        break
                    except:
                        t.handle_error(coro, _op)
                        break
                    else:
                        #~ if op is None:
                            #~ t.active.append((op, coro))
                        if op.__class__ in Socket.ops:
                            #~ print '> add socket op:', op
                            r = t.pool.add(op, coro)
                            #~ print 'R',r
                            if r:
                                _op = r
                                continue
                            else:
                                #~ print '#~ t.active.append((op, coro))'
                                break
                        elif isinstance(op, Events.WaitForSignal):
                            t.sigwait[op.name].append((op, coro))
                            break
                        elif isinstance(op, Events.Signal):
                            t.active.appendleft((None, coro))
                            t.active.extendleft(t.sigwait[op.name])
                            del t.sigwait[op.name]
                            break
                        elif isinstance(op, Events.Call):
                            print '-------------------'
                            #~ t.diewait[ t.add(*op.args, **op.kws) ].appendleft((op, coro))
                            #~ break
                            newcoro = t.gen(*op.args, **op.kws) #t.active.append( (None, newcoro) )
                            print t.active, op, coro, newcoro
                            
                            t.calls[ newcoro ] = op, coro
                            #~ _op = op = None
                            #~ coro = newcoro
                            #~ del newcoro
                            #~ continue
                            t.active.appendleft( (None, newcoro) )
                            break
                        elif isinstance(op, Events.Join):
                            t.diewait[ op.coro ].append((op, coro))
                            break
                        elif isinstance(op, Events.Sleep):
                            op.coro = coro
                            heapq.heappush(t.timewait, op)
                        else:
                            pass
                            #~ t.active.append((op, coro))
                    _op = op
            #~ print '> POOLER'
            t.run_pooler()
            #~ print '> TIMER'
            t.run_timer()
            #~ print '> DONE', len(t.pool)
            
            

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
                
    def coroA():
        print "coroA start"
        for i in range(10):
            yield Events.Sleep(datetime.timedelta(milliseconds=1))
            print "coroA:",i
            yield i
    def coroB():
        print "coroB start"
        for i in range(10):
            yield Events.Sleep(datetime.timedelta(milliseconds=1))
            print "coroB:",i
            yield i
    def coroC():
        print "coroC start"
        yield Events.Sleep(datetime.timedelta(milliseconds=100))
        print "coroC END"
        
    m = GreedyScheduler()
    #~ m.add(coro1)
    #~ m.add(coro2)
    #~ m.add(coro3)
    #~ coro4_instance = m.add(coro4)
    #~ m.add(coro5)
    #~ m.add(coroA)
    #~ m.add(coroB)
    #~ m.add(coroC)
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
    m.add(T)
    m.run()

    #~ print isinstance(Socket.Read(),(Socket.Read,Socket.Read,Socket.Write,Socket.Accept))
