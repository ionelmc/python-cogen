import sys
import time
import stackless

from cogen.core.schedulers import Scheduler
from cogen.core.coroutines import coroutine
from cogen.core import events
@coroutine
def mycoro():
    while 1:
        yield events.Sleep(1)
        print '#'

sched = Scheduler()
sched.add(mycoro)
sched_iter = sched.iter_run()

def tasklet():

    while True:
        # complicated operation with side-effects
        print '.'
        time.sleep(0.1)

        # run a cogen loop
        sched_iter.next()

# start the simple tasklet
stackless.tasklet(tasklet)()

# start the stackless scheduler
stackless.run()
