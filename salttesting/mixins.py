# -*- coding: utf-8 -*-
'''
    salttesting.mixins
    ~~~~~~~~~~~~~~~~~~

    Some reusable TestCase MixIns

    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`
    :copyright: © 2013 by the SaltStack Team, see AUTHORS for more details.
    :license: Apache 2.0, see LICENSE for more details.
'''

# Import python libs
import pprint
import logging

# Import salt libs
import salt.version

log = logging.getLogger(__name__)


class CheckShellBinaryNameAndVersionMixIn(object):

    _call_binary_ = None
    _call_binary_expected_version_ = salt.version.__version__

    def test_version_includes_binary_name(self):
        if getattr(self, '_call_binary_', None) is None:
            self.skipTest('\'_call_binary_\' not defined.')

        out = '\n'.join(self.run_script(self._call_binary_, '--version'))
        self.assertIn(self._call_binary_, out)
        self.assertIn(self._call_binary_expected_version_, out)


class SaltReturnAssertsMixIn(object):

    def assertReturnSaltType(self, ret):
        try:
            self.assertTrue(isinstance(ret, dict))
        except AssertionError:
            raise AssertionError(
                '{0} is not dict. Salt returned: {1}'.format(
                    type(ret).__name__, ret
                )
            )

    def assertReturnNonEmptySaltType(self, ret):
        self.assertReturnSaltType(ret)
        try:
            self.assertNotEqual(ret, {})
        except AssertionError:
            raise AssertionError(
                '{} is equal to {}. Salt returned an empty dictionary.'
            )

    def __return_valid_keys(self, keys):
        if isinstance(keys, tuple):
            # If it's a tuple, turn it into a list
            keys = list(keys)
        elif isinstance(keys, basestring):
            # If it's a basestring , make it a one item list
            keys = [keys]
        elif not isinstance(keys, list):
            # If we've reached here, it's a bad type passed to keys
            raise RuntimeError('The passed keys need to be a list')
        return keys

    def __getWithinSaltReturn(self, ret, keys):
        self.assertReturnNonEmptySaltType(ret)
        keys = self.__return_valid_keys(keys)
        okeys = keys[:]
        for part in ret.itervalues():
            try:
                ret_item = part[okeys.pop(0)]
            except (KeyError, TypeError):
                raise AssertionError(
                    'Could not get ret{0} from salt\'s return: {1}'.format(
                        ''.join(['[{0!r}]'.format(k) for k in keys]), part
                    )
                )
            while okeys:
                try:
                    ret_item = ret_item[okeys.pop(0)]
                except (KeyError, TypeError):
                    raise AssertionError(
                        'Could not get ret{0} from salt\'s return: {1}'.format(
                            ''.join(['[{0!r}]'.format(k) for k in keys]), part
                        )
                    )
            return ret_item

    def assertSaltTrueReturn(self, ret):
        try:
            self.assertTrue(self.__getWithinSaltReturn(ret, 'result'))
        except AssertionError:
            log.info('Salt Full Return:\n{0}'.format(pprint.pformat(ret)))
            try:
                raise AssertionError(
                    '{result} is not True. Salt Comment:\n{comment}'.format(
                        **(ret.values()[0])
                    )
                )
            except (AttributeError, IndexError):
                raise AssertionError(
                    'Failed to get result. Salt Returned:\n{0}'.format(
                        pprint.pformat(ret)
                    )
                )

    def assertSaltFalseReturn(self, ret):
        try:
            self.assertFalse(self.__getWithinSaltReturn(ret, 'result'))
        except AssertionError:
            log.info('Salt Full Return:\n{0}'.format(pprint.pformat(ret)))
            try:
                raise AssertionError(
                    '{result} is not False. Salt Comment:\n{comment}'.format(
                        **(ret.values()[0])
                    )
                )
            except (AttributeError, IndexError):
                raise AssertionError(
                    'Failed to get result. Salt Returned: {0}'.format(ret)
                )

    def assertSaltNoneReturn(self, ret):
        try:
            self.assertIsNone(self.__getWithinSaltReturn(ret, 'result'))
        except AssertionError:
            log.info('Salt Full Return:\n{0}'.format(pprint.pformat(ret)))
            try:
                raise AssertionError(
                    '{result} is not None. Salt Comment:\n{comment}'.format(
                        **(ret.values()[0])
                    )
                )
            except (AttributeError, IndexError):
                raise AssertionError(
                    'Failed to get result. Salt Returned: {0}'.format(ret)
                )

    def assertInSaltComment(self, in_comment, ret):
        return self.assertIn(
            in_comment, self.__getWithinSaltReturn(ret, 'comment')
        )

    def assertNotInSaltComment(self, not_in_comment, ret):
        return self.assertNotIn(
            not_in_comment, self.__getWithinSaltReturn(ret, 'comment')
        )

    def assertSaltCommentRegexpMatches(self, ret, pattern):
        return self.assertInSaltReturnRegexpMatches(ret, pattern, 'comment')

    def assertInSalStatetWarning(self, in_comment, ret):
        return self.assertIn(
            in_comment, self.__getWithinSaltReturn(ret, 'warnings')
        )

    def assertNotInSaltStateWarning(self, not_in_comment, ret):
        return self.assertNotIn(
            not_in_comment, self.__getWithinSaltReturn(ret, 'warnings')
        )

    def assertInSaltReturn(self, item_to_check, ret, keys):
        return self.assertIn(
            item_to_check, self.__getWithinSaltReturn(ret, keys)
        )

    def assertNotInSaltReturn(self, item_to_check, ret, keys):
        return self.assertNotIn(
            item_to_check, self.__getWithinSaltReturn(ret, keys)
        )

    def assertInSaltReturnRegexpMatches(self, ret, pattern, keys=()):
        return self.assertRegexpMatches(
            self.__getWithinSaltReturn(ret, keys), pattern
        )

    def assertSaltStateChangesEqual(self, ret, comparison, keys=()):
        keys = ['changes'] + self.__return_valid_keys(keys)
        return self.assertEqual(
            self.__getWithinSaltReturn(ret, keys), comparison
        )

    def assertSaltStateChangesNotEqual(self, ret, comparison, keys=()):
        keys = ['changes'] + self.__return_valid_keys(keys)
        return self.assertNotEqual(
            self.__getWithinSaltReturn(ret, keys), comparison
        )
