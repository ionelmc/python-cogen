try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup
from distutils.core import Extension

module1 = Extension('epoll',
                    sources = ['epollmodule.c'])

setup (name = 'py-epoll',
       version = '1.0',
       description = 'A Python interface to epoll(4)',
       author='Ben Woolley', author_email='user ben at host tautology.org',
       ulr='http://tautology.org/software/python-modules/distfiles/',
       ext_modules = [module1])
