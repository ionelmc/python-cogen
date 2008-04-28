try:
    from setuptools import setup, find_packages
except ImportError:
    from ez_setup import use_setuptools
    use_setuptools()
    from setuptools import setup, find_packages

setup(
    name='ChatApp',
    version='0.1',
    description='',
    author='',
    author_email='',
    #url='',
    install_requires=["Pylons>=0.9.6"],
    packages=find_packages(exclude=['ez_setup']),
    include_package_data=True,
    test_suite='nose.collector',
    package_data={'chatapp': ['i18n/*/LC_MESSAGES/*.mo']},
    #message_extractors = {'chatapp': [
    #        ('**.py', 'python', None),
    #        ('templates/**.mako', 'mako', None),
    #        ('public/**', 'ignore', None)]},
    zip_safe=False,
    entry_points="""
    [paste.app_factory]
    main = chatapp.config.middleware:make_app

    [paste.app_install]
    main = pylons.util:PylonsInstaller
    """,
)
