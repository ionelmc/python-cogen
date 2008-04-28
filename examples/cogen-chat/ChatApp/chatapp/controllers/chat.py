import logging

from pylons import request, response, session
from pylons import tmpl_context as c
from pylons.controllers.util import abort, redirect_to, url_for

from chatapp.lib.base import BaseController
# import chatapp.model as model

log = logging.getLogger(__name__)
from cogen.core import queue, events
from cogen.core.coroutines import coro
from cogen.core.pubsub import PublishSubscribeQueue
pubsub = PublishSubscribeQueue()

class Client:
    def __init__(self):
        self.messages = queue.Queue(10)
    @coro
    def watch(self):
        yield pubsub.subscribe()
        while 1:
            messages = yield pubsub.fetch()
            yield self.messages.put_nowait(messages)
        
class ChatController(BaseController):
    
    def push(self):
        yield request.environ['cogen.call'](pubsub.publish)(
            "%X: %s" % (id(session['client']), request.body)
        )
        yield str(request.environ['cogen.wsgi'].result)
        
    def pull(self):
        if not 'client' in session:
            client = Client()
            session['client'] = client
            session.save()
            yield request.environ['cogen.core'].events.AddCoro(client.watch)
        else:
            client = session['client']
            
        yield request.environ['cogen.call'](client.messages.get)(timeout=10)
        
        if isinstance(request.environ['cogen.wsgi'].result, events.OperationTimeout):
            pass
        elif isinstance(request.environ['cogen.wsgi'].result, Exception):
            import traceback
            traceback.print_exception(*request.environ['cogen.wsgi'].exception)
        else:
            yield "%s\r\n"% '\r\n'.join(request.environ['cogen.wsgi'].result)