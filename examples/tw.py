from twisted.internet import epollreactor
epollreactor.install()

from twisted.web import server, resource
from twisted.internet import reactor

class Simple(resource.Resource):
    isLeaf = True
    def render_GET(self, request):
        return "<html>Hello!</html>"

site = server.Site(Simple())
reactor.listenTCP(9002, site)
reactor.run()
