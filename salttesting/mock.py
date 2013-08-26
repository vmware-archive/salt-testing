# -*- coding: utf-8 -*-
'''
    salttesting.mock
    ~~~~~~~~~~~~~~~~

    Helper module that wraps `mock`_ and provides some fake objects in order to
    properly set the function/class decorators and yet skip the test cases
    execution.

    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`
    :copyright: © 2013 by the SaltStack Team, see AUTHORS for more details.
    :license: Apache 2.0, see LICENSE for more details.
'''

from __future__ import absolute_import

try:
    from mock import (
        Mock,
        MagicMock,
        patch,
        sentinel,
        DEFAULT,
        # ANY and call will be imported further down
        create_autospec,
        FILTER_DIR,
        NonCallableMock,
        NonCallableMagicMock,
        mock_open,
        PropertyMock
    )
    NO_MOCK = False
    NO_MOCK_REASON = ''
except ImportError:
    NO_MOCK = True
    NO_MOCK_REASON = 'mock python module is unavailable'

    class MagicMock(object):

        __name__ = '{0}.fakemock'.format(__name__)

        def __init__(self, *args, **kwargs):
            pass

        def dict(self, *args, **kwargs):
            return self

        def multiple(self, *args, **kwargs):
            return self

        def __call__(self, *args, **kwargs):
            return self

    Mock = MagicMock
    patch = MagicMock()
    call = tuple
    ANY = object()


if NO_MOCK is False:
    try:
        from mock import call, ANY
    except ImportError:
        NO_MOCK = True
        NO_MOCK_REASON = 'you need to upgrade your mock version to >= 0.8.0'
