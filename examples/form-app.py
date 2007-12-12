def show_post(environ, start_response):
    import cgi
    import pprint
    
    
    
    status = '200 OK'
    response_headers = [('Content-type','text/html')]
    start_response(status, response_headers)
    return ['''<html>
<body>%s
<form action="form" method="post">
 <input name="field1" type="text">
 <input name="field2" type="radio">
 <input name="field3" type="password">
 <textarea name="field4">default text</textarea>
 <input name="submit" type="submit">
</form>
</body>
</html>'''%cgi.FieldStorage(fp=environ['wsgi.input'], environ=environ)]

from cogen.web import wsgi
from cogen.common import *
server = wsgi.WSGIServer( ('localhost', 9000), show_post)
m = Scheduler(default_priority=priority.LAST, default_timeout=15)
m.add(server.start)
m.run()
