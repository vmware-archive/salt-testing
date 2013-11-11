# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`
    :copyright: © 2013 by the SaltStack Team, see AUTHORS for more details.
    :license: Apache 2.0, see LICENSE for more details.


    salttesting.pylintplugins.strings
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Extended String Formatting Checkers
'''

import sys
from logilab import astng
from pylint.checkers import utils
from pylint.checkers import BaseChecker
from pylint.checkers.utils import check_messages
from pylint.interfaces import IASTNGChecker


MSGS = {
    'W1320': ('String format call with un-indexed curly braces',
              'un-indexed-curly-braces-warning',
              'Under python 2.6 the curly braces on a \'string.format()\' '
              'call MUST be indexed.'),
    'E1320': ('String format call with un-indexed curly braces',
              'un-indexed-curly-braces-error',
              'Under python 2.6 the curly braces on a \'string.format()\' '
              'call MUST be indexed.')
}


class StringCurlyBracesFormatIndexChecker(BaseChecker):

    __implements__ = (IASTNGChecker,)

    name = 'string'
    msgs = MSGS
    priority = -1

    options = (('un-indexed-curly-braces-always-error',
                {'default': 1, 'type': 'yn', 'metavar': '<y_or_n>',
                 'help': 'Force un-indexed curly braces on a '
                         '\'string.format()\' call to always be an error.'}
                ),
               )

    @check_messages(*(MSGS.keys()))
    def visit_callfunc(self, node):
        func = utils.safe_infer(node.func)
        if isinstance(func, astng.BoundMethod) and func.name == 'format':

            if '{}' in node.func.expr.value:
                if self.config.un_indexed_curly_braces_always_error or \
                        sys.version_info[:2] < (2, 7):
                    self.add_message('E1320', node=node)
                else:
                    self.add_message('W1320', node=node)


def register(linter):
    '''required method to auto register this checker '''
    linter.register_checker(StringCurlyBracesFormatIndexChecker(linter))
