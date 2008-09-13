from cogen.core.coroutines import coroutine
from cogen.core.schedulers import Scheduler
from cogen.core import events

@coroutine
def foo():
    print 'foo'
    result = yield bar("ham")
    print result

@coroutine
def bar(what):
    print 'bar'
    raise StopIteration("spam, %s and eggs" % what)

sched = Scheduler() 
sched.add(foo)
sched.run()
