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


# Copied from salt
try:
    __salt_system_encoding__
except NameError:
    def __define_global_system_encoding_variable__():
        import sys
        # This is the most trustworthy source of the system encoding, though, if
        # salt is being imported after being daemonized, this information is lost
        # and reset to None
        if sys.stdin is not None:
            encoding = sys.stdin.encoding
        else:
            encoding = None
        if not encoding:
            # If the system is properly configured this should return a valid
            # encoding. MS Windows has problems with this and reports the wrong
            # encoding
            import locale
            try:
                encoding = locale.getdefaultlocale()[-1]
            except ValueError:
                # A bad locale setting was most likely found:
                #   https://github.com/saltstack/salt/issues/26063
                pass

            # This is now garbage collectable
            del locale
            if not encoding:
                # This is most likely ascii which is not the best but we were
                # unable to find a better encoding. If this fails, we fall all
                # the way back to ascii
                encoding = sys.getdefaultencoding() or 'ascii'

        # We can't use six.moves.builtins because these builtins get deleted sooner
        # than expected. See:
        #    https://github.com/saltstack/salt/issues/21036
        if sys.version_info[0] < 3:
            import __builtin__ as builtins  # pylint: disable=incompatible-py3-code
        else:
            import builtins  # pylint: disable=import-error

        # Define the detected encoding as a built-in variable for ease of use
        setattr(builtins, '__salt_system_encoding__', encoding)

        # This is now garbage collectable
        del sys
        del builtins
        del encoding


    __define_global_system_encoding_variable__()

    # This is now garbage collectable
    del __define_global_system_encoding_variable__
