from distutils.core import setup, Extension

module1 = Extension('kqueue',
                    sources = ['kqueuemodule.c'])

setup (name = 'kqueue',
       version = '1.5',
       description = 'Provides an interface to BSD kqueue() and kevent()',
       ext_modules = [module1])
