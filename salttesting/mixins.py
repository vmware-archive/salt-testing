# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`

    =============
    Class Mix-Ins
    =============

    Some reusable class MixIns
'''

# Import python libs
from __future__ import absolute_import
import os
import pprint
import logging
import warnings
import subprocess

# Import Salt Testing Libs
from salttesting.runtests import RUNTIME_VARS

# Import 3rd-party libs
import six

log = logging.getLogger(__name__)


class CheckShellBinaryNameAndVersionMixIn(object):
    '''
    Simple class mix-in to subclass in companion to :class:`ShellTestCase<salttesting.case.ShellTestCase>` which
    adds a test case to verify proper version report from Salt's CLI tools.
    '''

    _call_binary_ = None
    _call_binary_expected_version_ = None

    def test_version_includes_binary_name(self):
        if getattr(self, '_call_binary_', None) is None:
            self.skipTest('\'_call_binary_\' not defined.')

        if self._call_binary_expected_version_ is None:
            # Late import
            import salt.version
            self._call_binary_expected_version_ = salt.version.__version__

        out = '\n'.join(self.run_script(self._call_binary_, '--version'))
        self.assertIn(self._call_binary_, out)
        self.assertIn(self._call_binary_expected_version_, out)


class SaltReturnAssertsMixIn(object):
    '''
    Mix-in class to add as a companion to the TestCase class or it's subclasses which
    adds test assertions for Salt's return data.

    .. code-block: python

        from salttesting.case import ModuleCase
        from salttesting.mixins import SaltReturnAssertsMixIn

        class FooTestCase(ModuleCase, SaltReturnAssertsMixIn):

            def test_bar(self):
                ret = self.run_function('publish.publish', ['minion', 'test.ping'])
                self.assertReturnSaltType(ret)
    '''

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
        elif isinstance(keys, six.string_types):
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


class AdaptedConfigurationTestCaseMixIn(object):

    __slots__ = ()

    def get_config_dir(self):
        return RUNTIME_VARS.TMP_CONF_DIR

    def get_config_file_path(self, filename):
        return os.path.join(RUNTIME_VARS.TMP_CONF_DIR, filename)

    @property
    def master_opts(self):
        # Late import
        import salt.config

        warnings.warn(
            'Please stop using the \'master_opts\' attribute in \'{0}.{1}\' and instead '
            'import \'RUNTIME_VARS\' from {2!r} and instantiate the master configuration like '
            '\'salt.config.master_config(os.path.join(RUNTIME_VARS.TMP_CONF_DIR, "master"))\''.format(
                self.__class__.__module__,
                self.__class__.__name__,
                __name__
            ),
            DeprecationWarning,
        )
        return salt.config.master_config(
            self.get_config_file_path('master')
        )

    @property
    def minion_opts(self):
        '''
        Return the options used for the minion
        '''
        # Late import
        import salt.config

        warnings.warn(
            'Please stop using the \'minion_opts\' attribute in \'{0}.{1}\' and instead '
            'import \'RUNTIME_VARS\' from {2!r} and instantiate the minion configuration like '
            '\'salt.config.minion_config(os.path.join(RUNTIME_VARS.TMP_CONF_DIR, "minion"))\''.format(
                self.__class__.__module__,
                self.__class__.__name__,
                __name__
            ),
            DeprecationWarning,
        )
        return salt.config.minion_config(
            self.get_config_file_path('minion')
        )

    @property
    def sub_minion_opts(self):
        '''
        Return the options used for the sub-minion
        '''
        # Late import
        import salt.config

        warnings.warn(
            'Please stop using the \'sub_minion_opts\' attribute in \'{0}.{1}\' and instead '
            'import \'RUNTIME_VARS\' from {2!r} and instantiate the sub-minion configuration like '
            '\'salt.config.minion_config(os.path.join(RUNTIME_VARS.TMP_CONF_DIR, "sub_minion_opts"))\''.format(
                self.__class__.__module__,
                self.__class__.__name__,
                __name__
            ),
            DeprecationWarning,
        )
        return salt.config.minion_config(
            self.get_config_file_path('sub_minion')
        )



class SaltClientTestCaseMixIn(AdaptedConfigurationTestCaseMixIn):
    '''
    Mix-in class that provides a ``client`` attribute which returns a Salt
    :class:`LocalClient<salt:salt.client.LocalClient>`.

    .. code-block:: python

        class LocalClientTestCase(TestCase, SaltClientTestCaseMixIn):

            def test_check_pub_data(self):
                just_minions = {'minions': ['m1', 'm2']}
                jid_no_minions = {'jid': '1234', 'minions': []}
                valid_pub_data = {'minions': ['m1', 'm2'], 'jid': '1234'}

                self.assertRaises(EauthAuthenticationError,
                                  self.client._check_pub_data, None)
                self.assertDictEqual({},
                    self.client._check_pub_data(just_minions),
                    'Did not handle lack of jid correctly')

                self.assertDictEqual(
                    {},
                    self.client._check_pub_data({'jid': '0'}),
                    'Passing JID of zero is not handled gracefully')
    '''
    _salt_client_config_file_name_ = 'master'

    @property
    def client(self):
        # Late import
        import salt.client
        return salt.client.get_local_client(
            self.get_config_file_path(self._salt_client_config_file_name_)
        )


class ShellCaseCommonTestsMixIn(CheckShellBinaryNameAndVersionMixIn):

    def test_salt_with_git_version(self):
        # Late import
        import salt
        import salt.utils
        import salt.version

        if getattr(self, '_call_binary_', None) is None:
            self.skipTest('\'_call_binary_\' not defined.')
        git = salt.utils.which('git')
        if not git:
            self.skipTest('The git binary is not available')

        # Let's get the output of git describe
        process = subprocess.Popen(
            [git, 'describe', '--tags', '--match', 'v[0-9]*'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            close_fds=True,
            cwd=os.path.dirname(salt.__file__),
        )
        out, err = process.communicate()
        if not out:
            self.skipTest(
                'Failed to get the output of \'git describe\'. '
                'Error: {0!r}'.format(
                    err
                )
            )

        parsed_version = salt.version.SaltStackVersion.parse(out)

        if parsed_version.info < salt.version.__version_info__:
            self.skipTest(
                'We\'re likely about to release a new version. This test '
                'would fail. Parsed({0!r}) < Expected({1!r})'.format(
                    parsed_version.info, salt.version.__version_info__
                )
            )
        elif parsed_version.info != salt.version.__version_info__:
            self.skipTest(
                'In order to get the proper salt version with the '
                'git hash you need to update salt\'s local git '
                'tags. Something like: \'git fetch --tags\' or '
                '\'git fetch --tags upstream\' if you followed '
                'salt\'s contribute documentation. The version '
                'string WILL NOT include the git hash.'
            )
        out = '\n'.join(self.run_script(self._call_binary_, '--version'))
        self.assertIn(parsed_version.string, out)
