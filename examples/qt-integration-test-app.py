import sys
from PyQt4 import QtGui


app = QtGui.QApplication(sys.argv)
hello = QtGui.QPushButton("Hello world!")
hello.resize(100, 30)
hello.show()

from cogen.core import reactors, schedulers, events, sockets, coroutines
from cogen.web import wsgi

m = schedulers.Scheduler(reactor=reactors.QtReactor)
@coroutines.coro
def server():
    srv = sockets.Socket()
    print type(srv)
    srv.bind(('0.0.0.0', 11111))
    srv.listen(10)
    while 1:
        print "Listening..."
        conn, addr = yield srv.accept()
        print "Connection from %s:%s" % addr
        m.add(handler, args=(conn, addr))

@coroutines.coro
def handler(sock, addr):
    yield sock.write("WELCOME TO ECHO SERVER !\r\n")
        
    while 1:
        line = yield sock.readline(8192)
        if line.strip() == 'exit':
            yield sock.write("GOOD BYE")
            sock.close()
            return
        yield sock.write(line)

def lorem_ipsum_app(environ, start_response):
    start_response('200 OK', [('Content-type','text/plain'), ('Content-Length','19')])
    return ['Lorem ipsum dolor..']

server = wsgi.WSGIServer( 
  ('0.0.0.0', 9001), 
  lorem_ipsum_app, 
  m, 
  server_name='localhost', 
  request_queue_size=2048,
  #~ sockoper_run_first=False
)


m.add(server.serve)
m.poll.start()

sys.exit(app.exec_())