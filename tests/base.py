__doc_all__ = []
import sys
sys.setcheckinterval(0)

from cogen.common import *


class PrioFIRST:
    prio = priority.FIRST
class PrioLAST:
    prio = priority.LAST
class PrioOP:
    prio = priority.OP
class PrioCORO:
    prio = priority.CORO
    
priorities = (PrioCORO, PrioOP, PrioFIRST, PrioLAST)
from cogen.core.reactors import has_iocp, has_kqueue, has_epoll, has_poll, has_select, has_qt
reactors_available = [j for j in [i() for i in (has_iocp, has_kqueue, has_epoll, has_poll, has_select)] if j]