# -*- coding: utf-8 -*-
'''
    salttesting
    ~~~~~~~~~~~

    This project includes some if not all the required testing tools needed in
    the several Salt Stack projects.

    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`
    :copyright: © 2013 by the SaltStack Team, see AUTHORS for more details.
    :license: Apache 2.0, see LICENSE for more details.
'''

# Import python libs
from __future__ import absolute_import
import warnings

# Import salt-testing libs
from salttesting.version import __version__, __version_info__
from salttesting.unit import (
    TestLoader,
    TextTestRunner,
    TestCase,
    expectedFailure,
    TestSuite,
    skipIf,
    TestResult,
)


__all__ = [
    'TestLoader',
    'TextTestRunner',
    'TestCase',
    'expectedFailure',
    'TestSuite',
    'skipIf',
    'TestResult',
]


# All salt-testing related deprecation warnings should be shown once each!
warnings.filterwarnings(
    'once',                               # Show once
    '',                                   # No deprecation message match
    DeprecationWarning,                   # This filter is for DeprecationWarnings
    r'^(salttesting|salttesting\.(.*))$'  # Match module(s) 'salttesting' and 'salttesting.<whatever>'
)
