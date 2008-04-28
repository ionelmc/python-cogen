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