#!/usr/bin/env python
#
# Set-up script for the nodes module.
#

from setuptools import setup

setup(name='nodes',
      version='alpha',
      description='An easy-to-use graph-oriented object model for Python.',
      classifiers=[
          "Programming Language :: Python",
          ("Topic :: Software Development :: Libraries :: Python Modules")
          ],
      keywords='nodes graph functional reactive',
      author='Adam M. Donahue',
      author_email='adam.donahue@gmail.com',
      license='BSD',
      packages=['nodes']
      )
