from distutils.core import setup, Extension

module1 = Extension('epoll',
                    sources = ['epollmodule.c'])

setup (name = 'py-epoll',
       version = '1.0',
       description = 'A Python interface to epoll(4)',
       ext_modules = [module1])
