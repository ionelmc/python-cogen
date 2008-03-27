from cogen.core.coroutine import coroutine
from cogen.core.schedulers import Scheduler
from cogen.core import events

@coroutine
def foo():
    print 'foo'
    result = yield events.Call(bar, args=("ham",))
    print result

@coroutine
def bar(what):
    print 'bar'
    raise StopIteration("spam, %s and eggs" % what)

sched = Scheduler() 
sched.add(foo)
sched.run()
