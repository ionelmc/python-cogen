from distutils.core import setup, Extension

module1 = Extension('kqueuemodule',
                    sources = ['kqueuemodule.c'])

setup (name = 'kqueue',
       version = '2.0',
       description = 'This is a kqueue package',
       ext_modules = [module1])
