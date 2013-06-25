# -*- coding: utf-8 -*-
'''
    salttesting.mixins
    ~~~~~~~~~~~~~~~~~~

    Some reusable TestCase MixIns

    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`
    :copyright: © 2013 by the SaltStack Team, see AUTHORS for more details.
    :license: Apache 2.0, see LICENSE for more details.
'''


class CheckShellBinaryNameAndVersionMixIn(object):

    _call_binary_ = None
    _call_binary_expected_version_ = None

    def test_version_includes_binary_name(self):
        if getattr(self, '_call_binary_', None) is None:
            self.skipTest('\'_call_binary_\' not defined.')

        out = '\n'.join(self.run_script(self._call_binary_, '--version'))
        self.assertIn(self._call_binary_, out)
        self.assertIn(self._call_binary_expected_version_, out)
