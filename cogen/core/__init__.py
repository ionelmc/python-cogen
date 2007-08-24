from schedulers import *
from poolers import *

## need cleaup this
class DefaultComposition:
    def __init__(t):
        t.base_scheduler = Scheduler()
        t.worker = GreedyScheduler()
        t.pooler = SelectPooler(t.worker)
        t.master.add(t.pooler.run)
        t.master.add(t.worker.run)
    def add(t, *a, **k):
        t.worker.add(*a, **k)
    def run(t):
        return t.master.run()


class Runner:
    def __init__(t, coro):
        t.coro = coro
    def run():
        op = None
        while 1:
            op = t.coro.send(op)
            