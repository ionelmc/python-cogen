from distutils.core import setup, Extension

module1 = Extension('sendfile',
                    sources = ['sendfilemodule.c'])

setup (name = 'py-sendfile',
       version = '1.0',
       description = 'A Python interface to sendfile(2)',
       ext_modules = [module1])
