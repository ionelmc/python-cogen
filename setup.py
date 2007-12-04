#!/usr/bin/env python

from distutils.core import setup
from cogen import __version__ as version
setup(name='cogen',
      version=version,
      description='Coroutines in python using enhanced generators from python 2.5',
      long_description="""
      Coroutines in python using enhanced generators from python 2.5
      
      This is a library for network oriented, coroutine based programming. The interfaces and events/operations aim to mimic thread features. Coroutines work as simple generators, the operations and events work as objects passed in and out of the generator, these objects are managed by the scheduler/network poller. 

      Development version at: http://cogen.googlecode.com/svn/trunk/cogen/#egg=cogen-dev
      """,
      author='Maries Ionel Cristian',
      author_email='ionel.mc@gmail.com  ',
      url='http://code.google.com/p/cogen/',
      packages=['cogen'],
      zip_safe=False,
      classifiers=[
          'Development Status :: 2 - Pre-Alpha',
          'Environment :: Web Environment',
          'Intended Audience :: Developers',
          'Intended Audience :: System Administrators',
          'License :: OSI Approved :: BSD License',
          'Operating System :: Microsoft :: Windows',
          'Operating System :: POSIX',
          'Programming Language :: Python',
          'Topic :: Internet :: WWW/HTTP :: HTTP Servers',
          'Topic :: Internet :: WWW/HTTP :: WSGI :: Server',
          'Topic :: System :: Networking',
          ],      
     )