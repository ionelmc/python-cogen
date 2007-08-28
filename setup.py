#!/usr/bin/env python

from distutils.core import setup

setup(name='cogen',
      version='0.0.1',
      description='Coroutines in python using enhanced generators from python 2.5',
      author='Maries Ionel Cristian',
      author_email='ionel.mc@gmail.com  ',
      url='http://code.google.com/p/cogen/',
      packages=['cogen','cogen.core','cogen.web','cogen.test'],
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