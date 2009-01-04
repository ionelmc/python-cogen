from __future__ import division
import select, itertools
from time import sleep

from base import ProactorBase, perform_recv, perform_accept, perform_send, \
                                perform_sendall, perform_sendfile, \
                                perform_connect


class SelectProactor(ProactorBase):
    def run(self, timeout = 0):
        """ 
        Run a proactor loop and return new socket events. Timeout is a timedelta 
        object, 0 if active coros or None. 
        
        select timeout param is a float number of seconds.
        """
        ptimeout = timeout.days*86400 + timeout.microseconds/1000000 + timeout.seconds \
                if timeout else (self.resolution if timeout is None else 0)
        if self.tokens:
            #~ print ([act for act in self.tokens 
                    #~ if self.tokens[act] == perform_recv
                    #~ or self.tokens[act] == perform_accept], 
                #~ [act for act in self.tokens 
                    #~ if self.tokens[act] == perform_send 
                    #~ or self.tokens[act] == perform_sendall
                    #~ or self.tokens[act] == perform_sendfile
                    #~ or self.tokens[act] == perform_connect], 
                #~ [act for act in self.tokens])
                    
            ready_to_read, ready_to_write, in_error = select.select(
                [act for act in self.tokens 
                    if self.tokens[act] == perform_recv
                    or self.tokens[act] == perform_accept], 
                [act for act in self.tokens 
                    if self.tokens[act] == perform_send 
                    or self.tokens[act] == perform_sendall
                    or self.tokens[act] == perform_sendfile
                    or self.tokens[act] == perform_connect], 
                [act for act in self.tokens], 
                ptimeout
            )
            #~ print ready_to_read, ready_to_write, in_error
            for act in in_error:
                self.handle_error_event(act, 'Unknown error.')
            last_act = None
            for act in itertools.chain(ready_to_read, ready_to_write):
                if last_act:
                    self.handle_event(last_act)
                        
                last_act = act
            return self.yield_event(last_act)
        else:
            sleep(timeout)
