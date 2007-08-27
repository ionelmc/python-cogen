import sys, os
sys.path.append(os.path.split(os.getcwd())[0])

from cogen.core import Socket, GreedyScheduler
from cogen.web import wsgiserver

def my_crazy_app(environ, start_response):
    status = '200 OK'
    response_headers = [('Content-type','text/plain')]
    start_response(status, response_headers)
    return ['Hello world!\n']

server = wsgiserver.WSGIServer(
            ('localhost', 8070), my_crazy_app,
            server_name='localhost')
