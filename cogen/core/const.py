class priority(object):  
    DEFAULT = -1    
    LAST  = NOPRIO = 0
    CORO  = 1
    OP    = 2
    FIRST = PRIO = 3
class ConnectionClosed(Exception):
    pass
class OperationTimeout(Exception):
    pass    
class CoroutineException(Exception):
    prio = priority.DEFAULT
    pass
    