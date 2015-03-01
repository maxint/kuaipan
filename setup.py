# coding: utf-8

try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

version = dict()
with open('kpfuse/version.py') as f:
    code = compile(f.read(), 'version.py', 'exec')
    exec(code, version)

setup(name='kpfuse',
      version=version['__version__'],
      description='FUSE File System for Cloud Drive in kuaipan.cn',
      long_description=open('README.md').read(),
      keywords=['Cloud Drive', 'FUSE', 'File System'],
      author=version['__author__'],
      author_email=version['__email__'],
      url=version['__url__'],
      packages=['kpfuse'],
      package_data={'kpfuse': ['*.json']},
      entry_points={
          'console_scripts': [
              'kpfs=kpfuse.command:main',
          ]
      },
      install_requires=['requests', 'requests-oauthlib', 'fusepy'],
      license=version['__license__'],
      platforms=['Linux'],
      classifiers=[
          'Development Status :: ' + version['__status__'],
          'Environment :: Console',
          'Intended Audience :: Developers',
          'Intended Audience :: End Users/Desktop',
          'Intended Audience :: System Administrators',
          'Natural Language :: English',
          'License :: OSI Approved :: Python Software Foundation License',
          'Operating System :: POSIX',
          'Programming Language :: Python :: 2.7',
          'Topic :: Internet',
      ],
)
