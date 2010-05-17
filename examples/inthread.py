from cogen.core import schedulers
from cogen.core.coroutines import coroutine
from cogen.core.events import Operation

from threading import Thread

class RunInThread(Operation):
  def __init__(self, callable, args=(), kwargs=None):
    self.callable = callable
    self.args = args
    self.kwargs = kwargs or {}
    super(RunInThread, self).__init__()
  
  def _run_thread(self):
    self.result = self.callable(*self.args, **self.kwargs)
    self.sched.active.append((self, self.coro))
    
  def process(self, sched, coro):
    super(RunInThread, self).process(sched, coro)
    self.coro = coro
    self.sched = sched
    thread = self.thread = Thread(target=self._run_thread)
    thread.daemon = True
    thread.start()
    
  def finalize(self, sched):
    super(RunInThread, self).finalize(sched)
    return self.result

if __name__ == "__main__":
  @coroutine
  def test():
    def computation(a,b,c):
      from time import sleep
      print a, b, c
      sleep(1)
      return a + b + c
    for i in xrange(10):
      print '>', i
      val = yield RunInThread(computation, args=(i+1,i+2,i+3))
      print val
  
  @coroutine
  def some_stuff_to_keep_sched_alive():
    from cogen.core.sockets import Socket
    s = Socket()
    s.bind(('localhost', 8000))
    s.listen(1)
    yield s.accept()
  
  s = schedulers.Scheduler()
  s.add(test)
  s.add(some_stuff_to_keep_sched_alive)
  s.run()
