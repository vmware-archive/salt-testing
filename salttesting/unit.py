# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`
    :copyright: © 2013 by the SaltStack Team, see AUTHORS for more details.
    :license: Apache 2.0, see LICENSE for more details.


    salttesting.unit
    ~~~~~~~~~~~~~~~~

    Unit test related functions
'''

import sys

# support python < 2.7 via unittest2
if sys.version_info < (2, 7):
    try:
        from unittest2 import (
            TestLoader,
            TextTestRunner,
            TestCase as _TestCase,
            expectedFailure,
            TestSuite,
            skipIf,
            TestResult,
        )
    except ImportError:
        raise SystemExit('You need to install unittest2 to run the salt tests')
else:
    from unittest import (
        TestLoader,
        TextTestRunner,
        TestCase as _TestCase,
        expectedFailure,
        TestSuite,
        skipIf,
        TestResult,
    )


class TestCase(_TestCase):

    def assertEquals(self, *args, **kwargs):
        raise DeprecationWarning(
            'The {0}() function is deprecated. Please start using {1}() '
            'instead.'.format('assertEquals', 'assertEqual')
        )
        return _TestCase.assertEquals(self, *args, **kwargs)

    def failUnlessEqual(self, *args, **kwargs):
        raise DeprecationWarning(
            'The {0}() function is deprecated. Please start using {1}() '
            'instead.'.format('failUnlessEqual', 'assertEqual')
        )
        return _TestCase.failUnlessEqual(self, *args, **kwargs)

    def failIfEqual(self, *args, **kwargs):
        raise DeprecationWarning(
            'The {0}() function is deprecated. Please start using {1}() '
            'instead.'.format('failIfEqual', 'assertNotEqual')
        )
        return _TestCase.failIfEqual(self, *args, **kwargs)

    def failUnless(self, *args, **kwargs):
        raise DeprecationWarning(
            'The {0}() function is deprecated. Please start using {1}() '
            'instead.'.format('failUnless', 'assertTrue')
        )
        return _TestCase.failUnless(self, *args, **kwargs)

    def assert_(self, *args, **kwargs):
        if sys.version_info >= (2, 7):
            # The unittest2 library uses this deprecated method, we can't raise
            # the exception.
            raise DeprecationWarning(
                'The {0}() function is deprecated. Please start using {1}() '
                'instead.'.format('assert_', 'assertTrue')
            )
        return _TestCase.assert_(self, *args, **kwargs)

    def failIf(self, *args, **kwargs):
        raise DeprecationWarning(
            'The {0}() function is deprecated. Please start using {1}() '
            'instead.'.format('failIf', 'assertFalse')
        )
        return _TestCase.failIf(self, *args, **kwargs)

    def failUnlessRaises(self, *args, **kwargs):
        raise DeprecationWarning(
            'The {0}() function is deprecated. Please start using {1}() '
            'instead.'.format('failUnlessRaises', 'assertRaises')
        )
        return _TestCase.failUnlessRaises(self, *args, **kwargs)

    def failUnlessAlmostEqual(self, *args, **kwargs):
        raise DeprecationWarning(
            'The {0}() function is deprecated. Please start using {1}() '
            'instead.'.format('failUnlessAlmostEqual', 'assertAlmostEqual')
        )
        return _TestCase.failUnlessAlmostEqual(self, *args, **kwargs)

    def failIfAlmostEqual(self, *args, **kwargs):
        raise DeprecationWarning(
            'The {0}() function is deprecated. Please start using {1}() '
            'instead.'.format('failIfAlmostEqual', 'assertNotAlmostEqual')
        )
        return _TestCase.failIfAlmostEqual(self, *args, **kwargs)


__all__ = [
    'TestLoader',
    'TextTestRunner',
    'TestCase',
    'expectedFailure',
    'TestSuite',
    'skipIf',
    'TestResult'
]
