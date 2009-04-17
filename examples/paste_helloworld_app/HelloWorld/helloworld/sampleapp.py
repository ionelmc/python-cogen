import cgi
from paste.deploy import CONFIG

def application(environ, start_response):
    # Note that usually you wouldn't be writing a pure WSGI
    # application, you might be using some framework or
    # environment.  But as an example...
    start_response('200 OK', [('Content-type', 'text/html')])
    return ["Hello world !!!!!!"]

                        
