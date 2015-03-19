`cogen` is a crossplatform library for network oriented, [coroutine](http://en.wikipedia.org/wiki/Coroutine) based programming using the [enhanced generators](http://www.python.org/dev/peps/pep-0342/) from python 2.5. The project aims to provide a simple straightforward programming model similar to threads but without all the problems and costs.

## Features ##
  * wsgi server with coroutine extensions - enabling asynchronous wsgi apps in a regular wsgi stack
  * fast network multiplexing with epoll, kqueue, select, poll or io completion ports (on windows)
    * epoll/kqueue support via the wrappers in the python 2.6's stdlib or separate modules [py-kqueue](http://pypi.python.org/pypi/py-kqueue), [py-epoll](http://pypi.python.org/pypi/py-epoll)
    * iocp support via ctypes wrappers or pywin32
  * sendfile/TransmitFile support (the wsgi server also uses this for `wsgi.file_wrapper`)
  * timeouts for socket calls, signal waits etc
  * various mechanisms to work with (signals, joins, a Queue with the same features as the stdlib one) and some other stuff you can find in the docs :)

## Documentation ##
Docs are available at:

  * 0.2.1: http://cogen.googlecode.com/svn/tags/0.2.1/docs/build/index.html
  * 0.2.0: http://cogen.googlecode.com/svn/tags/0.2.0/docs/build/index.html
  * 0.1.9: http://cogen.googlecode.com/svn/tags/0.1.9/docs/cogen.html
  * 0.1.8: http://cogen.googlecode.com/svn/tags/0.1.8/docs/cogen.html

## Download ##

`cogen` is available for download at PYPI:
> http://pypi.python.org/pypi/cogen/
or using
```
easy_install cogen
```

_But the code in trunk is usually the best code._

## Development ##

_Latest and Greatest._

Subversion access:
```
svn co http://cogen.googlecode.com/svn/trunk/ cogen
```
Also, you can use easy\_install to install a development snapshot from [svn](http://cogen.googlecode.com/svn/trunk/#egg=cogen-dev):
```
easy_install cogen==dev
```
You can run the test suite with: `python setup.py test`

## Similar projects ##

  * multitask - http://o2s.csail.mit.edu/o2s-wiki/multitask
  * chiral - http://chiral.j4cbo.com/trac
  * eventlet - http://wiki.secondlife.com/wiki/Eventlet
  * spawning wsgi server (based on eventlet) - http://pypi.python.org/pypi/Spawning
  * asynwsgi - http://trac.wiretooth.com/public/wiki
  * friendlyflow - http://code.google.com/p/friendlyflow
  * weightless - http://weightless.io/weightless
  * fibra - http://code.google.com/p/fibra/
  * concurrence - http://code.google.com/p/concurrence/
  * circuits.web - http://trac.softcircuit.com.au/circuits/
  * diesel - http://dieselweb.org/lib/

## Plug ##

&lt;wiki:gadget url="http://www.ohloh.net/projects/cogen/widgets/project\_basic\_stats.xml" height="220" border="1" /&gt;