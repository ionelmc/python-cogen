from __future__ import division
from PyQt4.QtCore import QSocketNotifier, QObject, QTimer, QCoreApplication
from PyQt4.QtCore import SIGNAL

from base import ReactorBase
from cogen.core import sockets
from cogen.core.util import priority

class QtSocketNotifier(QSocketNotifier):
    def __init__(self, reactor, op, coro):
        QSocketNotifier.__init__(self, op.sock.fileno(), 
            QSocketNotifier.Read if isinstance(op, sockets.ReadOperation) 
                else QSocketNotifier.Write)
        self.reactor = reactor
        self.operation = op
        self.coro = coro
        QObject.connect(self, SIGNAL("activated(int)"), self.run)
        
    def close(self):
        QObject.disconnect(self, SIGNAL("activated(int)"), self.run)
        
    def run(self, fd):
        self.setEnabled(False)
        coro = self.coro
        op = self.reactor.run_operation(self.operation)
        if op:
            del self.reactor.notifiers[self.operation.sock.fileno()]
            self.close()
            if op.prio & priority.OP:
                op, coro = self.reactor.scheduler.process_op(coro.run_op(op), coro)
            if coro:
                if op.prio & priority.CORO:
                    self.reactor.scheduler.active.appendleft( (op, coro) )
                else:
                    self.reactor.scheduler.active.append( (op, coro) )
        else:
            self.setEnabled(True)
    
class QtReactor(ReactorBase):
    """ A reator that integrated with the Qt main loop.
    Works roughly the same way as the other reactor, but:
    
    * the scheduler is changed to run in a QTimer with the same intervals
      as the reactor would usualy run (0 when there are coroutines to run,
      the resolution value if there are pending socket operations or the 
      timespan to the next timeout.
    
    * the scheduler's run method is monkey patched (yeah i know it doesn't 
      feel right but you're doing some weird stuff if your putting this in a 
      Qt app so it doesn't really count) to call the QApplication's exec_ 
      method - so roughly works the same way as for the other reactors (blocks
      and runs the coroutines) but actualy runs the Qt app.
    
    * the reactor has a extra method _start_ that starts the timer and 
      runs the first cogen scheduler iteration (wich is called by the 
      scheduler's patched run method.
      
    * if there are no more stuff to run (no active coros, no pending 
      operations) the scheduler will die but the Schduler.run method will still
      block - as it is running the Qt app.
      
    To plug this in a qt app you ahve 2 options:
    
    *   do the usual Scheduler initialisation and call start() on the reactor.
        Eg:
        .. sourcecode:: python
        
            # initialise you QApplication or QCoreApplication

            sched = schedulers.Scheduler(reactor=reactors.QtReactor)
            sched.poll.start()

            # call your application's exec_() - or whatever options do you have.
        
      
    *   initialise the scheduler and call run on it.
        Eg:
        .. sourcecode:: python
        
            # initialise you QApplication or QCoreApplication

            sched = schedulers.Scheduler(reactor=reactors.QtReactor)
            sched.run() # this will run your application's exec_() for you
        
        
    Other notes:

    * Qt can only have one QApplication or QCoreApplication
    * Qt can only run in the main thread (this saddens me, really)
    * This reactor will make it's own QApplication if there isn't one - so 
      you'd better initialise the Scheduler after your Qt app.
    * this reactor isn't well tested.
    """
    def __init__(self, scheduler, res):
        super(self.__class__, self).__init__(scheduler, res)
        self.notifiers = {}
        self.timer = QTimer()
        self.timer.setSingleShot(False)
        if QCoreApplication.startingUp():
            self.qt_app = QCoreApplication([])
            self.own_app = True
        else:
            self.qt_app = QCoreApplication.instance()
            self.own_app = False
        self.timer.setInterval(1000) 
        self.sched_iter = self.scheduler.iter_run()
        self.scheduler.run = self.sched_fake_run
        
        QObject.connect(self.timer, SIGNAL("timeout()"), self.sched_run)
        
    def sched_fake_run(self):
        self.start()
        self.qt_app.exec_()
    
    def sched_run(self):
        try:
            self.sched_iter.next()
        except:
            import traceback
            traceback.print_exc()
            QObject.disconnect(self.timer, SIGNAL("timeout()"), self.sched_run)
        
    def __len__(self):
        return len(self.notifiers)
        
    def start(self):
        self.timer.start(0)
        
    def remove(self, op, coro):
        notifier = self.notifiers.pop(op.sock.fileno(), None)
        QObject.disconnect(notifier, SIGNAL("activated(int)"), self.run)

    def add(self, op, coro):
        self.notifiers[op.sock.fileno()] = QtSocketNotifier(self, op, coro)
        
    def run(self, timeout = 0):
        """ 
        Ok, this looks a bit tricky. We set here the interval when the sched
        is runned. Also, events will be runned out of this context when QT 
        decides the sockets are ready.
        """
        ptimeout = int(
            timeout.days * 86400000 + 
            timeout.microseconds / 1000 + 
            timeout.seconds * 1000 
            if timeout else (self.m_resolution if timeout is None else 0)
        )
        self.timer.setInterval(ptimeout)
