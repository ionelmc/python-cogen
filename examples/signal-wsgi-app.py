import wsgiref.validate 
import pprint
import cgi
import cogen

def lorem_ipsum_app(environ, start_response):
    start_response('200 OK', [('Content-type','text/plain')])
    return ["""
    Lorem ipsum dolor sit amet, consectetuer adipiscing elit. Nunc feugiat. Nam dictum, eros sed iaculis egestas, odio massa fringilla metus, sed scelerisque velit est id turpis. Integer et arcu vel mi ornare tincidunt. Proin sodales, nibh sit amet posuere porttitor, magna purus facilisis lorem, sed mattis sem lorem auctor magna. Suspendisse aliquet lacus ac turpis. Praesent ut tortor. Nulla facilisi. Phasellus enim. Curabitur lorem nisi, pulvinar at, mollis quis, mattis id, massa. Nulla facilisi. In luctus erat. Proin eget nulla eget felis varius molestie. Curabitur hendrerit massa ac nunc. Donec condimentum leo eu magna. Donec lorem. Vestibulum sed massa in turpis auctor consectetuer. Ut volutpat diam sit amet justo. Mauris et elit tempus tellus gravida tincidunt.

    Sed posuere nunc quis erat. In suscipit sapien nec mi. Vestibulum condimentum erat a dui. Curabitur dictum augue vitae nunc. Aliquam imperdiet nisi non eros. Cum sociis natoque penatibus et magnis dis parturient montes, nascetur ridiculus mus. Etiam sagittis risus vel eros. Praesent lobortis nulla non sapien. Nulla scelerisque quam vitae lectus. Duis eu tortor ut pede faucibus auctor. Nam ullamcorper est id felis. Fusce sit amet risus a mi vestibulum mattis. Fusce nibh nisi, congue at, iaculis ac, blandit quis, erat.

    Duis turpis. Etiam pede nulla, rhoncus vel, laoreet ac, facilisis imperdiet, enim. Praesent viverra placerat lorem. Maecenas dapibus diam sit amet mi. Suspendisse id turpis. Sed quis velit sit amet lorem imperdiet cursus. Donec nonummy. Phasellus condimentum libero sit amet elit. Integer lectus turpis, pharetra sed, mollis quis, porttitor vitae, tortor. Sed eget massa. Suspendisse eu metus. Nam libero. Nullam porta, nisi a rhoncus tincidunt, velit lacus porta diam, a feugiat odio est at eros. Phasellus urna. Suspendisse convallis libero ac mauris. Vestibulum vitae sem in massa tincidunt accumsan. Vestibulum pharetra interdum dolor.

    Aliquam interdum lobortis tellus. In adipiscing dictum enim. Vestibulum magna. Ut rhoncus. Sed arcu. Pellentesque tellus mi, porttitor a, fringilla in, dignissim quis, neque. Aliquam erat volutpat. Aenean non purus quis nunc vestibulum interdum. Quisque non urna. Proin nec mauris. Suspendisse potenti.

    Lorem ipsum dolor sit amet, consectetuer adipiscing elit. Vestibulum luctus. Donec erat quam, facilisis eget, pharetra vel, sagittis et, nisi. Suspendisse hendrerit pellentesque turpis. Curabitur ac velit quis urna rutrum lacinia. Integer pede arcu, laoreet ac, aliquet in, tristique ac, libero. Suspendisse quis mauris. Suspendisse molestie lacinia quam. Phasellus porttitor, odio in posuere vulputate, lorem nunc sollicitudin nisl, et sagittis arcu augue eu urna. Donec tincidunt mauris at ipsum. Sed id neque non ante fringilla tempus. Duis sit amet tortor nec erat condimentum commodo. Vestibulum euismod volutpat erat. In cursus pretium odio. Sed a diam. Mauris at lectus. Integer ipsum augue, tincidunt in, sagittis ac, vestibulum rutrum, tortor. Pellentesque quam. Nam volutpat justo vitae dolor. 
    """]
def wait_app(environ, start_response):
    start_response('200 OK', [('Content-type','text/html')])
    yield "I'm waiting for some signal<br>"
    yield environ['cogen.core'].events.WaitForSignal("abc", timeout=5)
    if isinstance(environ['cogen.wsgi'].result, Exception):
        yield "Your time is up !"
    else:
        yield "Someone signaled me with this message: %s" % cgi.escape(`environ['cogen.wsgi'].result`)
def send_app(environ, start_response):
    start_response('200 OK', [('Content-type','text/html')])
    yield environ['cogen.core'].events.Signal("abc", environ["PATH_INFO"])
    yield "Done."


from cogen.common import *
from cogen.web.wsgi import WSGIServer
sched = Scheduler(default_timeout=-1)
    
server = WSGIServer( 
  ('0.0.0.0', 9001), 
  [('/', lorem_ipsum_app), ('/wait', wait_app), ('/send', send_app)], 
  sched, 
  server_name='localhost', 
  request_queue_size=2048
)
sched.add(server.serve)
sched.run()



