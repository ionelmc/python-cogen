from cogen.core.coroutines import coroutine
from cogen.core.schedulers import Scheduler
from cogen.core import events

@coroutine
def foo():
    yield events.Signal("bar", 'spam')
    yield events.Signal("bar", 'ham')
    yield events.Signal("bar", 'eggs')
    yield events.Sleep(3)

@coroutine
def bar():
    print (yield events.WaitForSignal("bar"))
    print (yield events.WaitForSignal("bar"))
    print (yield events.WaitForSignal("bar"))
    try:
        print (yield events.WaitForSignal("bar", timeout=2))
    except events.OperationTimeout:
        print 'No more stuff !'

sched = Scheduler()
sched.add(bar)
sched.add(foo)
sched.run()
