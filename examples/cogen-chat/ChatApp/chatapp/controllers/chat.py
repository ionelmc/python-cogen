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
from cogen.core.util import priority

pubsub = PublishSubscribeQueue()

class Client:
    def __init__(self, name):
        self.messages = queue.Queue(10)
        self.dead = False
        self.name = name
    @coro
    def watch(self):
        """This is a coroutine that runs permanently for each participant to the
        chat. If the participant has more than 10 unpulled messages this
        coroutine will die.

        `pubsub` is a queue that hosts the messages from all the
        participants.
          * subscribe registers this coro to the queue
          * fetch pulls the recent messages from the queue or waits if there
        are no new ones.

        self.messages is another queue for the frontend comet client (the
        pull action from the ChatController will pop messages from this queue)
        """
        yield pubsub.subscribe()
        while 1:
            messages = yield pubsub.fetch()
            print messages
            try:
                yield self.messages.put_nowait(messages)
            except:
                print 'Client %s is dead.' % self
                self.dead = True
                break
class ChatController(BaseController):

    def push(self):
        """This action puts a message in the global queue that all the clients
        will get via the 'pull' action."""
        print `request.body`
        yield request.environ['cogen.call'](pubsub.publish)(
            "%s: %s" % (session['client'].name, request.body)
        )
        # the request.environ['cogen.*'] objects are the the asynchronous
        # make the code here work as a coroutine and still work with any
        # wsgi extensions offered by cogen - basicaly they do some magic to
        # middleware
        yield str(request.environ['cogen.wsgi'].result)

    def pull(self):
        """This action does some state checking (adds a object in the session
        that will identify this chat participant and adds a coroutine to manage
        it's state) and gets new messages or bail out in 10 seconds if there are
        no messages."""
        if not 'client' in session or session['client'].dead:
            client = Client(str(request.environ['pylons.routes_dict']['id']))
            print 'Adding new client:', client
            session['client'] = client
            session.save()
            yield request.environ['cogen.core'].events.AddCoro(client.watch, prio=priority.CORO)
            return
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
