Server overview
===============

Paste Integration
-----------------

You can use this server with paste:

Example config ini::

    [server:main]
    use = egg:cogen#wsgi
    # Server configuration
    host = 127.0.0.1
    port = 85

Usage example
-------------

::

    from cogen.web import wsgi
    from cogen.common import *
    def my_crazy_app(environ, start_response):
        status = '200 OK'
        response_headers = [('Content-type','text/plain')]
        start_response(status, response_headers)
        return ["Lorem ipsum dolor sit amet, consectetuer adipiscing elit."]
    server = wsgi.WSGIServer(
                ('localhost', 8070),
                my_crazy_app,
                server_name='localhost')
    m = Scheduler(default_priority=priority.LAST, default_timeout=15)
    m.add(server.start)
    try:
        m.run()
    except (KeyboardInterrupt, SystemExit):
        pass

