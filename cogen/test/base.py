__doc_all__ = []
import sys
sys.setcheckinterval(0)

from cogen.common import *


class PrioMixIn:
    prio = priority.FIRST
class NoPrioMixIn:
    prio = priority.LAST
    
