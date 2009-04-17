import pprint
def lorem_ipsum_app(environ, start_response):
        start_response('200 OK', [('Content-type','text/plain')])
        #~ data = environ['wsgi.input'].read()
        #~ fh = file("INPUT", 'wb')
        #~ fh.write(data)
        #~ fh.close()
        return [
            #~ "inputlen:%s"%len(data),
            pprint.pformat(environ)
        ]

from cogen.web import wsgi
def run():
    try:
        wsgi.server_factory({}, '0.0.0.0', 9000)(wsgi.async.SynchronousInputMiddleware(lorem_ipsum_app))
    except:
        import traceback
        traceback.print_exc()

import cProfile, os
cProfile.run("run()", "cprofile.log")
import pstats
for i in [
    'calls','cumulative','file','module',
    'pcalls','line','name','nfl','stdname','time'
    ]:
    stats = pstats.Stats("cprofile.log",
        stream = file('cprofile.%s.%s.txt' % (
                os.path.split(__file__)[1],
                i
            ),'w'
        )
    )
    stats.sort_stats(i)
    stats.print_stats()

