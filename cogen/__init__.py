# -*- coding: utf-8 -*-
'''
This is a library for network oriented, coroutine based programming. 
The interfaces and events/operations aim to mimic thread features. Coroutines 
work as simple generators, the operations and events work as objects passed in 
and out of the generator, these objects are managed by the scheduler/network 
poller. 

Check each modules for specific help.
'''

__license__ = '''
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

__author__ = "Mărieş Ionel Cristian"
__email__ = "ionel dot mc at gmail dot com"
__revision__ = "$Revision$"
__version__ = '0.1.4'
__svnid__ = "$Id$"

from cogen import core
from cogen import common
from cogen import web