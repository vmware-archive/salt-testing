# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`
    :copyright: © 2013-2014 by the SaltStack Team, see AUTHORS for more details
    :license: Apache 2.0, see LICENSE for more details.


    salttesting.unit
    ~~~~~~~~~~~~~~~~

    Unit test related functions
'''

# Import python libs
import sys
import logging


# support python < 2.7 via unittest2
if sys.version_info < (2, 7):
    try:
        from unittest2 import (
            TestLoader as _TestLoader,
            TextTestRunner as __TextTestRunner,
            TestCase as __TestCase,
            expectedFailure,
            TestSuite as _TestSuite,
            skip,
            skipIf,
            TestResult as _TestResult,
            TextTestResult as __TextTestResult
        )
        from unittest2.case import (
            _id,
            _UnexpectedSuccess as unexpectedSuccess
        )

        class NewStyleClassMixin(object):
            '''
            Simple new style class to make pylint shut up!

            And also to avoid errors like:

                'Cannot create a consistent method resolution order (MRO) for bases'
            '''

        class TestLoader(_TestLoader, NewStyleClassMixin):
            pass

        class _TextTestRunner(__TextTestRunner, NewStyleClassMixin):
            pass

        class _TestCase(__TestCase, NewStyleClassMixin):
            pass

        class TestSuite(_TestSuite, NewStyleClassMixin):
            pass

        class TestResult(_TestResult, NewStyleClassMixin):
            pass

        class _TextTestResult(__TextTestResult, NewStyleClassMixin):
            pass

    except ImportError:
        raise SystemExit('You need to install unittest2 to run the salt tests')
else:
    from unittest import (
        TestLoader,
        TextTestRunner as _TextTestRunner,
        TestCase as _TestCase,
        expectedFailure,
        TestSuite,
        skip,
        skipIf,
        TestResult,
        TextTestResult as _TextTestResult
    )
    from unittest.case import (
        _id,
        _UnexpectedSuccess as unexpectedSuccess
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


class TextTestResult(_TextTestResult):
    '''
    Custom TestResult class whith logs the start and the end of a test
    '''

    def startTest(self, test):
        logging.getLogger(__name__).debug(
            '>>>>> START >>>>> {0}'.format(test.id())
        )
        return super(TextTestResult, self).startTest(test)

    def stopTest(self, test):
        logging.getLogger(__name__).debug(
            '<<<<< END <<<<<<< {0}'.format(test.id())
        )
        return super(TextTestResult, self).stopTest(test)


class TextTestRunner(_TextTestRunner):
    '''
    Custom Text tests runner to log the start and the end of a test case
    '''
    resultclass = TextTestResult


__all__ = [
    'TestLoader',
    'TextTestRunner',
    'TestCase',
    'expectedFailure',
    'TestSuite',
    'skipIf',
    'TestResult'
]
