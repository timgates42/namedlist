from __future__ import print_function
from setuptools import setup, Command

# run our tests
class PyTest(Command):
    user_options = []
    def initialize_options(self):
        pass
    def finalize_options(self):
        pass
    def run(self):
        import sys, subprocess
        tests = [('test suite', ['-m', 'test.test_namedlist']),
                 ('doctests',   ['-m' 'doctest', 'README.txt']),
                 ]
        for name, cmds in tests:
            print(name)
            errno = subprocess.call([sys.executable] + cmds)
            if errno != 0:
                raise SystemExit(errno)
        print('test complete')


setup(name='namedlist',
      version='1.8.6',
      url='https://bitbucket.org/ericvsmith/namedlist',
      author='Eric V. Smith',
      author_email='eric@trueblade.com',
      description='Similar to namedtuple, but instances are mutable.',
      long_description=open('README.txt').read() + '\n' + open('CHANGES.txt').read(),
      classifiers=['Development Status :: 5 - Production/Stable',
                   'Intended Audience :: Developers',
                   'License :: OSI Approved :: Apache Software License',
                   'Topic :: Software Development :: Libraries :: Python Modules',
                   'Programming Language :: Python :: 2.6',
                   'Programming Language :: Python :: 2.7',
                   'Programming Language :: Python :: 3.3',
                   'Programming Language :: Python :: 3.4',
                   'Programming Language :: Python :: 3.5',
                   ],
      license='Apache License Version 2.0',
      py_modules=['namedlist'],

      cmdclass = {'test': PyTest},
      )
