from cogen.common import *
count = 0
@coroutine
def cogen_b():
    global count
    count += 1
    yield 
    yield 
    yield 
@coroutine
def cogen_a(prio):
    for i in xrange(10000):
        yield events.Call(cogen_b, prio=prio)

def normal_a():
    global count
    count += 1
    yield 
    yield 
    yield 
def normal_b():
    for i in xrange(10000):
        for i in normal_a():
            pass
def cogen_call(prio=priority.FIRST):
    m = Scheduler(default_priority=priority.FIRST)
    m.add(cogen_a, args=(prio,))
    m.run()
def normal_call():
    normal_b()    

if __name__ == "__main__":
    #~ cogen_call()
    import timeit
    print timeit.Timer(
        'normal_call()', 
        "from __main__ import normal_call"
    ).timeit(3)
    print count
    print timeit.Timer(
        'cogen_call()', 
        "from __main__ import cogen_call"
    ).timeit(3)
    print count
    import cProfile, os
    cProfile.run("cogen_call()", "cprofile.log")
    #cProfile.run("normal_call()", "cprofile.log")
    import pstats
    for i in [
        'calls','cumulative','file','module',
        'pcalls','line','name','nfl','stdname','time'
        ]:
        stats = pstats.Stats("cprofile.log",
            stream = file('cprofile.%s.%s.txt' % (
                    os.path.split(__file__)[1],
                    i
                ),'w'
            )
        )
        stats.sort_stats(i)
        stats.print_stats()
            