from distutils.core import setup, Extension

module1 = Extension('kqueuemodule',
                    sources = ['kqueuemodule.c'])

setup (name = 'kqueue',
       version = '2.0',
       description = 'This is a kqueue package',
       author_email='jdolecek@netbsd.org',
       maintainer_email='ionel.mc@gmail.com',
       ext_modules = [module1])
