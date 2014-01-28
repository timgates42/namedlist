from distutils.core import setup, Command

# run our tests
class PyTest(Command):
    user_options = []
    def initialize_options(self):
        pass
    def finalize_options(self):
        pass
    def run(self):
        import sys, subprocess
        errno = subprocess.call([sys.executable, 'namedlist.py'])
        raise SystemExit(errno)


setup(name='namedlist',
      version='0.2',
      url='https://bitbucket.org/ericvsmith/namedlist',
      author='Eric V. Smith',
      author_email='eric@trueblade.com',
      description='Similar to namedtuple, but instances are mutable.',
      long_description=open('README.txt').read() + '\n' + open('CHANGES.txt').read(),
      classifiers=['Development Status :: 5 - Production/Stable',
                   'Intended Audience :: Developers',
                   'License :: OSI Approved :: Apache Software License',
                   'Topic :: Software Development :: Libraries :: Python Modules',
                   'Programming Language :: Python :: 2.7',
                   'Programming Language :: Python :: 3.3',
                   ],
      license='Apache License Version 2.0',
      py_modules=['namedlist'],

      cmdclass = {'test': PyTest},
      )
