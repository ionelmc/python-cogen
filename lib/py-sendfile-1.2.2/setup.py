from setuptools import setup
from distutils.core import Extension

module1 = Extension('sendfile',
                    sources = ['sendfilemodule.c'])

setup (name = 'py-sendfile',
       version = '1.2.3',
       description = 'A Python interface to sendfile(2)',
       author='Ben Woolley', author_email='user ben at host tautology.org',
       ext_modules = [module1],
       zip_safe=False,
       )
