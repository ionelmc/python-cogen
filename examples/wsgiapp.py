import sys, os
sys.path.append(os.path.split(os.getcwd())[0])

from cogen.core import Socket, GreedyScheduler
from cogen.web import wsgiserver
#~ from cogen.web import httpd

def my_crazy_app(environ, start_response):
    status = '200 OK'
    response_headers = [('Content-type','text/plain')]
    start_response(status, response_headers)
    return ['''Lorem ipsum dolor sit amet, consectetuer adipiscing elit. Donec commodo tincidunt urna. Phasellus commodo metus sit amet dolor. Fusce vitae sapien. Donec consectetuer nonummy ipsum. Donec enim enim, placerat nec, faucibus eget, commodo a, risus. Cras tincidunt. Lorem ipsum dolor sit amet, consectetuer adipiscing elit. Donec eros leo, adipiscing a, ornare at, imperdiet vel, arcu. Cum sociis natoque penatibus et magnis dis parturient montes, nascetur ridiculus mus. In feugiat lacus eu leo. Etiam bibendum urna nec metus. Fusce egestas accumsan nulla. Nulla molestie auctor arcu. Curabitur mi urna, imperdiet sed, consectetuer fermentum, iaculis vitae, velit.
    Nam in nisi. Cras orci. Praesent ac eros ut diam consectetuer sagittis. Etiam augue ligula, egestas elementum, porta vitae, gravida nec, nisl. Ut lacinia. Etiam bibendum lacus et est. Aenean interdum. Nulla nec libero. Fusce viverra lectus in orci. Nam et erat. Praesent nulla mauris, molestie ac, fermentum sed, luctus vel, leo. Pellentesque habitant morbi tristique senectus et netus et malesuada fames ac turpis egestas. Etiam pharetra mauris non justo.
    Fusce tellus nisl, sodales at, semper id, adipiscing eu, purus. Aliquam sed urna. Aliquam dapibus augue et elit. Donec volutpat risus in sapien. In hac habitasse platea dictumst. Nunc pharetra. Sed vulputate vulputate justo. Vestibulum ante ipsum primis in faucibus orci luctus et ultrices posuere cubilia Curae; Nunc nisi. Maecenas purus.
    Nullam massa purus, placerat ac, aliquam ut, dapibus id, neque. Nullam hendrerit eros id urna. In hac habitasse platea dictumst. In suscipit. In nonummy. Etiam ultrices arcu vel nunc. Donec feugiat massa at dolor. Mauris facilisis lectus vel libero. Vestibulum viverra mattis nisi. Sed dapibus. Nunc ligula turpis, ultrices nec, laoreet vel, fermentum eu, justo. Fusce volutpat, lorem vel fermentum sodales, sapien augue auctor risus, sed consectetuer metus urna in nisl. Nulla nec lorem vitae nunc placerat tempus. Pellentesque non pede. Ut mollis velit sit amet risus vestibulum eleifend. Suspendisse vel sem. Duis accumsan varius erat. Donec sodales. Proin justo.
    Nulla quis felis. Mauris ultrices, arcu ut blandit eleifend, arcu odio porta libero, a posuere mi nisi nec elit. Phasellus in neque. In diam eros, venenatis quis, consectetuer et, ultrices non, arcu. Ut pretium, turpis a imperdiet suscipit, sapien tellus venenatis urna, feugiat egestas ante neque a orci. Cras orci sapien, porta et, pharetra sit amet, dignissim nonummy, lacus. Suspendisse facilisis turpis quis ante venenatis egestas. Sed et magna nec eros suscipit varius. Aliquam eu pede ut lectus rutrum bibendum. Ut ac tellus. Fusce porta dictum augue. Nunc vel nibh nec nulla pulvinar tempus. Mauris in tortor. Proin vehicula. Pellentesque consequat. Sed metus augue, condimentum eget, iaculis a, aliquam in, tellus.''']

server = wsgiserver.WSGIServer(
            ('localhost', 8070), my_crazy_app,
            server_name='localhost')
m = GreedyScheduler()
m.add(server.start)
m.run()