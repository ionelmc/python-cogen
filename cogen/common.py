"""
A module for quick importing the essential core stuff.
(coroutine, Scheduler, events, sockets, priority)
"""
from .core.coroutines import coroutine, coro
from .core.schedulers import Scheduler
from .core import events
from .core import sockets
from .core import proactors
from .core.events import priority
