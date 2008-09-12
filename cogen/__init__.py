# -*- coding: utf-8 -*-
'''
This is a library for network oriented, coroutine based programming. 
The interfaces and events/operations aim to mimic some of the regular thread 
and socket features. 

cogen uses the `enhanced generators <http://www.python.org/dev/peps/pep-0342/>`_
in python 2.5. These generators are bidirectional: they allow to pass values in 
and out of the generator. The whole framework is based on this.

The generator yields a `Operation` instance and will receive the result from 
that yield when the operation is ready.

::
    
    Roughly the cogen internals works like this:

    +------------------------+
    | @coroutine             |
    | def foo():             |
    |     ...                |             op.process(sched, coro)
    |  +->result = yield op--|----------------+------------+
    |  |  ...                |                |            |  
    +--|---------------------+    +---------------+  +---------------------+      
       |                          | the operation |  | the operation can't |
      result = op.finalize()      | is ready      |  | complete right now  |
       |                          +------|--------+  +----------|----------+
      scheduler runs foo                 |                      |
       |                                 |                      |
      foo gets in the active             |                      |
      coroutines queue                   |                      |
       |                                 |                      |
       +----------------------<----------+                      |
       |                                                    depening on the op      
      op.run()                                               +---------+
       |      socket is ready               add it in        |         |
       +-------------<------------  ......  the proactor  <--+         |
       |                         later                                 | 
       +------<-------------------  ......  add it in some other     <-+
        some event decides                  queue for later run
        this op is ready
        
        
    The scheduler basicaly does 3 things:
     - runs active (coroutine,operations) pairs (calls process on the op)
     - runs the proactor
     - checks for timeouts
     
    The proactor basicaly does 2 things:
     - calls the system to check what descriptors are ready
     - runs the operations that have ready descriptors
     
    The operation does most of the work (via the process, finalize, cleanup, 
    run methods):
     - adds itself in the proactor (if it's a socket operation)
     - adds itself in some structure to be activated later by some other event
     - adds itself and the coro in the scheduler's active coroutines queue

    The coroutine decorator wrappes foo in a Coroutine class that does some
    niceties like exception handling, getting the result from finalize() etc.
'''

__license__ = u'''
Copyright (c) 2007, Mărieş Ionel Cristian

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
'''

__author__ = u"Mărieş Ionel Cristian"
__email__ = "ionel.mc@gmail.com"
__revision__ = "$Revision$"
__version__ = '0.2.0'
__svnid__ = "$Id$"

from cogen import core
from cogen import common
from cogen import web