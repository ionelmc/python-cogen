try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup
from distutils.core import Extension

module1 = Extension('kqueuemodule',
                    sources = ['kqueuemodule.c'])

setup (name = 'py-kqueue',
       version = '2.0',
       description = 'This is a kqueue package',
       author='Jaromir Dolecek',author_email='jdolecek@netbsd.org',
       url='ftp://ftp.NetBSD.org/pub/NetBSD/misc/jdolecek/',
       ext_modules = [module1])
