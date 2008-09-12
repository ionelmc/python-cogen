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
from cogen.core.proactors import has_iocp, \
                                has_kqueue, has_stdlib_kqueue, \
                                has_epoll, has_stdlib_epoll, \
                                has_poll, has_select
proactors_available = [
    j for j in [
        i() for i in (
            has_iocp,
            has_stdlib_kqueue,             
            has_kqueue, 
            has_stdlib_epoll,
            has_epoll, 
            has_poll, 
            has_select
        )
    ] if j
]
    