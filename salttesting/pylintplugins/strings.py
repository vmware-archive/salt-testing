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
    'W1320': ('String format call with un-indexed curly braces: %r',
              'un-indexed-curly-braces-warning',
              'Under python 2.6 the curly braces on a \'string.format()\' '
              'call MUST be indexed.'),
    'E1320': ('String format call with un-indexed curly braces: %r',
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
            # If there's a .format() call, run the code below

            if isinstance(node.func.expr, astng.Name):
                # This is for:
                #   foo = 'Foo {} bar'
                #   print(foo.format(blah)
                for inferred in node.func.expr.infer():
                    if not hasattr(inferred, 'value'):
                        # If there's no value attribute, it's not worth
                        # checking.
                        continue

                    if '{}' in inferred.value:
                        if self.config.un_indexed_curly_braces_always_error or \
                                sys.version_info[:2] < (2, 7):
                            msgid = 'E1320'
                        else:
                            msgid = 'W1320'
                        self.add_message(
                            msgid, node=inferred, args=inferred.value
                        )
            elif not hasattr(node.func.expr, 'value'):
                # If it does not have an value attribute, it's not worth
                # checking
                return
            elif isinstance(node.func.expr.value, astng.Name):
                # No need to check these either
                return
            elif '{}' in node.func.expr.value:
                if self.config.un_indexed_curly_braces_always_error or \
                        sys.version_info[:2] < (2, 7):
                    msgid = 'E1320'
                else:
                    msgid = 'W1320'
                self.add_message(
                    'E1320', node=node, args=node.func.expr.value
                )


def register(linter):
    '''required method to auto register this checker '''
    linter.register_checker(StringCurlyBracesFormatIndexChecker(linter))
