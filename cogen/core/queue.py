import events
class Full(Exception):
    pass
class Empty(Exception):
    pass
class Queue_Get:
    __slots__ = ['queue', 'value']
    def __init__(self, queue, value):
        self.queue = queue
        self.value = value
        
class Queue_Put:
    __slots__ = ['queue']
    def __init__(self, queue):
        self.queue = queue
    
class Queue:
    def __init__(self, size):
        self.size = size
        self.buf = collections.deque()
    def put(self, value):
        if se
        return 
    def put_nowait(self, value):
        if len(self.buf) >= self.size:
            raise Full()
        else:
            self.buf.append(value)
            return events.Signal(self, 
    def get(self):
        if not self.buf:
            return events.WaitForSignal(self)
        else:
            return self.buf.popleft()
        
    def get_nowait(self):
        if not self.buf:
            raise Empty()
        else:
            return self.buf.popleft()
