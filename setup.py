#!/usr/bin/python
import ez_setup
ez_setup.use_setuptools()

from setuptools import setup
import sys
from cogen import __version__ as version
setup(
    name='cogen',
    version=version,
    description='''
        Coroutines and asynchronous I/O using enhanced generators 
        from python 2.5, including a enhanced WSGI server.
    ''',
    long_description=file('README.txt').read(),
    author='Maries Ionel Cristian',
    author_email='ionel dot mc at gmail dot com',
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
        'Operating System :: POSIX :: Linux',
        'Operating System :: POSIX :: BSD',
        'Programming Language :: Python',
        'Topic :: Internet :: WWW/HTTP :: HTTP Servers',
        'Topic :: Internet :: WWW/HTTP :: WSGI :: Server',
        'Topic :: System :: Networking',
    ],      
    entry_points={
        'paste.server_factory': [
            'wsgi=cogen.web.wsgi:server_factory',
        ],
        'paste.filter_app_factory': [
            'syncinput=cogen.web.async:SynchronousInputMiddleware'
        ],
        'apydia.themes': [
            'cogen=cogen.docs.theme',
            'cogenwiki=cogen.docs.wikitheme',
        ],
        'apydia.docrenderers': [
            'wiki=cogen.docs.wikirender:WikiTextRenderer'
        ]
    },
    install_requires = \
        (["py-kqueue>=2.0"] if 'bsd' in sys.platform else []) +
        (["py-epoll>=1.2"] if 'linux' in sys.platform else []) +\
        (["py-sendfile>=1.2.2"] if ('linux' in sys.platform) or ('bsd' in sys.platform) else []),
    test_suite = "cogen.test"
    
)