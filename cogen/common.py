"""
A module for quick importing the essential core stuff.
(coroutine, Scheduler, events, sockets, priority)
"""
from cogen.core.coroutines import coroutine, coro
from cogen.core.schedulers import Scheduler
from cogen.core import events
from cogen.core import sockets
from cogen.core import proactors
from cogen.core.events import priority
