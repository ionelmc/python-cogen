from setuptools import setup
from distutils.core import Extension

module1 = Extension('epoll',
                    sources = ['epollmodule.c'])

setup (name = 'py-epoll',
       version = '1.2.1',
       description = 'A Python interface to epoll(4)',
       author='Ben Woolley', author_email='user ben at host tautology.org',
       ext_modules = [module1],
       zip_safe=False,
       )
