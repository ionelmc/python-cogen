def lorem_ipsum_app(environ, start_response):
    start_response('200 OK', [('Content-type','text/plain'), ('Content-Length','19')])
    return ['Lorem ipsum dolor..']

# Now on to the real stuff
from twisted.web2 import server, channel, wsgi
from twisted.application import service, strports

application = service.Application('web2-wsgi') # call this anything you like
site = server.Site(wsgi.WSGIResource(lorem_ipsum_app))
s = strports.service('tcp:9005', channel.HTTPFactory(site))
s.setServiceParent(application)
