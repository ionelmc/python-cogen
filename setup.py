#!/usr/bin/env python
import ez_setup
ez_setup.use_setuptools()

from setuptools import setup
from cogen import __version__ as version
setup(
    name='cogen',
    version=version,
    description='''
        Coroutines and asynchronous I/O using enhanced generators 
        from python 2.5, including a enhanced WSGI server.
    ''',
    long_description="""
        Coroutines in python using enhanced generators from python 2.5

        This is a library for network oriented, coroutine based programming. 
        The interfaces and events/operations aim to mimic thread features. 
        Coroutines work as simple generators, the operations and events work as 
        objects passed in and out of the generator, these objects are managed 
        by the scheduler/network poller. 

        Other features include a wsgi server with coroutine extensions, 
        epoll/kqueue/sendfile enhancements, support for both win32 and linux.

        Project page at: http://cogen.googlecode.com/

        Development version at: 
            http://cogen.googlecode.com/svn/trunk/cogen/#egg=cogen-dev
    """,
    author='Maries Ionel Cristian',
    author_email='ionel.mc@gmail.com  ',
    url='http://code.google.com/p/cogen/',
    packages=[
        'cogen',
        'cogen.core',
        'cogen.web',
        'cogen.test',
    ],
    zip_safe=False,
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: MIT License',
        'Operating System :: Microsoft :: Windows',
        'Operating System :: POSIX',
        'Programming Language :: Python',
        'Topic :: Internet :: WWW/HTTP :: HTTP Servers',
        'Topic :: Internet :: WWW/HTTP :: WSGI :: Server',
        'Topic :: System :: Networking',
    ],      
    entry_points={
        'paste.server_factory': [
            'wsgi=cogen.web.wsgi:server_factory',
        ],
        'apydia.themes': [
            'cogen=cogen.docs.theme'
        ]
    },
    install_requires = ['decorator'],
    test_suite = "cogen.test"
    
)