#!/usr/bin/env python
'''
The setup script for SaltTesting
'''

from __future__ import with_statement
import io
import os
import sys

SETUP_KWARGS = {
    'scripts': [
        'scripts/salt-jenkins-build',
        'scripts/github-commit-status'
    ]
}
USE_SETUPTOOLS = False

# Change to salt source's directory prior to running any command
try:
    SETUP_DIRNAME = os.path.dirname(__file__)
except NameError:
    # We're most likely being frozen and __file__ triggered this NameError
    # Let's work around that
    SETUP_DIRNAME = os.path.dirname(sys.argv[0])

if SETUP_DIRNAME != '':
    os.chdir(SETUP_DIRNAME)


if 'USE_SETUPTOOLS' in os.environ:
    try:
        from setuptools import setup
        USE_SETUPTOOLS = True
        SETUP_KWARGS['extras_require'] = {
            'GitHub': ['requests>=2.4.2']
        }
        SETUP_KWARGS['install_requires'] = ['six']

        if sys.version_info < (2, 7):
            SETUP_KWARGS['install_requires'].extend(['unittest2', 'argparse'])
        SETUP_KWARGS['entry_points'] = {
            'console_scripts': [
                'salt-jenkins-build = salttesting.jenkins:main',
                'github-commit-status = salttesting.github:main'
            ]
        }
    except ImportError:
        USE_SETUPTOOLS = False


if USE_SETUPTOOLS is False:
    from distutils.core import setup

with io.open(os.path.join(SETUP_DIRNAME, 'salttesting', 'version.py'), encoding='utf-8') as fh_:
    contents = fh_.read()
    if not isinstance(contents, str):
        contents = contents.encode('utf-8')
    exec(  # pylint: disable=exec-used
        compile(
            contents,
            os.path.join(SETUP_DIRNAME, 'salttesting', 'version.py'),
            'exec'
        )
    )


NAME = 'SaltTesting'
VERSION = __version__
DESCRIPTION = (
    'Required testing tools needed in the several SaltStack projects.'
)

setup(
    name=NAME,
    version=VERSION,
    description=DESCRIPTION,
    author='Pedro Algarvio',
    author_email='pedro@algarvio.me',
    url='https://github.com/saltstack/salt-testing',
    classifiers=[
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Development Status :: 5 - Production/Stable',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'Intended Audience :: Information Technology',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: Apache Software License',
        'Operating System :: POSIX :: Linux',
    ],
    packages=[
        'salttesting',
        'salttesting/ext',
        'salttesting/parser',
        'salttesting/cherrypytest',
        'salttesting/pylintplugins',
        'salttesting/pylintplugins/py3modernize',
        'salttesting/pylintplugins/py3modernize/fixes',
    ],
    **SETUP_KWARGS
)
