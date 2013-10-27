# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`
    :copyright: © 2013 by the SaltStack Team, see AUTHORS for more details.
    :license: Apache 2.0, see LICENSE for more details.


    salttesting.pylintplugins.pep8
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    PEP-8 PyLint Checker
'''

# Let's use absolute imports
from __future__ import absolute_import

# Import PyLint libs
from pylint.interfaces import IRawChecker
from pylint.checkers import BaseChecker

# Import PEP8 libs
try:
    from pep8 import StyleGuide, BaseReport
    HAS_PEP8 = True
except ImportError:
    HAS_PEP8 = False
    import logging
    logging.getLogger(__name__).warning(
        'No pep8 library could be imported. No PEP8 check\'s will be done'
    )


_PROCESSED_NODES = {}


if HAS_PEP8 is True:
    class PyLintPEP8Reporter(BaseReport):
        def __init__(self, options):
            super(PyLintPEP8Reporter, self).__init__(options)
            self.locations = []

        def error(self, line_number, offset, text, check):
            code = super(PyLintPEP8Reporter, self).error(
                line_number, offset, text, check
            )
            if code:
                # E123, at least, is not reporting it's code in the above call,
                # don't want to bother about that now
                self.locations.append((code, line_number))


class _PEP8BaseChecker(BaseChecker):

    __implements__ = IRawChecker

    name = 'pep8'

    priority = -1
    options = ()

    msgs = None
    _msgs = {}
    msgs_map = {}

    def __init__(self, linter=None):
        # To avoid PyLints deprecation about a missing symbolic name and
        # because I don't want to add descriptions, let's make the descriptions
        # equal to the messages.
        if self.msgs is None:
            self.msgs = {}

        for code, (message, symbolic) in self._msgs.iteritems():
            self.msgs[code] = (message, symbolic, message)

        BaseChecker.__init__(self, linter=linter)

    def process_module(self, node):
        '''
        process a module

        the module's content is accessible via node.file_stream object
        '''
        if node.path not in _PROCESSED_NODES:
            stylechecker = StyleGuide(
                parse_argv=False, config_file=True, quiet=2,
                reporter=PyLintPEP8Reporter
            )

            _PROCESSED_NODES[node.path] = stylechecker.check_files([node.path])

        for code, lineno in _PROCESSED_NODES[node.path].locations:
            pylintcode = '{0}8{1}'.format(code[0], code[1:])
            if pylintcode in self.msgs_map:
                # This will be handled by PyLint itself, skip it
                continue

            if pylintcode not in self.msgs:
                # Log warning??
                continue

            self.add_message(pylintcode, line=lineno, args=code)


class PEP8Indentation(_PEP8BaseChecker):
    '''
    Process PEP8 E1 codes
    '''

    _msgs = {
        'E8101': ('PEP8 %s: indentation contains mixed spaces and tabs',
                  'indentation-contains-mixed-spaces-and-tabs'),
        'E8111': ('PEP8 %s: indentation is not a multiple of four',
                  'indentation-is-not-a-multiple-of-four'),
        'E8112': ('PEP8 %s: expected an indented block',
                  'expected-an-indented-block'),
        'E8113': ('PEP8 %s: unexpected indentation',
                  'unexpected-indentation'),
        'E8121': ('PEP8 %s: continuation line indentation is not a multiple of four',
                  'continuation-line-indentation-is-not-a-multiple-of-four'),
        'E8122': ('PEP8 %s: continuation line missing indentation or outdented',
                  'continuation-line-missing-indentation-or-outdented'),
        'E8123': ("PEP8 %s: closing bracket does not match indentation of opening bracket's line",
                  "closing-bracket-does-not-match-indentation-of-opening-bracket's-line"),
        'E8124': ('PEP8 %s: closing bracket does not match visual indentation',
                  'closing-bracket-does-not-match-visual-indentation'),
        'E8125': ('PEP8 %s: continuation line does not distinguish itself from next logical line',
                  'continuation-line-does-not-distinguish-itself-from-next-logical-line'),
        'E8126': ('PEP8 %s: continuation line over-indented for hanging indent',
                  'continuation-line-over-indented-for-hanging-indent'),
        'E8127': ('PEP8 %s: continuation line over-indented for visual indent',
                  'continuation-line-over-indented-for-visual-indent'),
        'E8128': ('PEP8 %s: continuation line under-indented for visual indent',
                  'continuation-line-under-indented-for-visual-indent'),
        'E8133': ('PEP8 %s: closing bracket is missing indentation',
                  'closing-bracket-is-missing-indentation'),
    }


class PEP8Whitespace(_PEP8BaseChecker):
    '''
    Process PEP8 E2 codes
    '''

    _msgs = {
        'E8201': ("PEP8 %s: whitespace after '('", "whitespace-after-'('"),
        'E8202': ("PEP8 %s: whitespace before ')'", "whitespace-before-')'"),
        'E8203': ("PEP8 %s: whitespace before ':'", "whitespace-before-':'"),
        'E8211': ("PEP8 %s: whitespace before '('", "whitespace-before-'('"),
        'E8221': ('PEP8 %s: multiple spaces before operator',
                  'multiple-spaces-before-operator'),
        'E8222': ('PEP8 %s: multiple spaces after operator',
                  'multiple-spaces-after-operator'),
        'E8223': ('PEP8 %s: tab before operator', 'tab-before-operator'),
        'E8224': ('PEP8 %s: tab after operator', 'tab-after-operator'),
        'E8225': ('PEP8 %s: missing whitespace around operator',
                  'missing-whitespace-around-operator'),
        'E8226': ('PEP8 %s: missing whitespace around arithmetic operator',
                  'missing-whitespace-around-arithmetic-operator'),
        'E8227': ('PEP8 %s: missing whitespace around bitwise or shift operator',
                  'missing-whitespace-around-bitwise-or-shift-operator'),
        'E8228': ('PEP8 %s: missing whitespace around modulo operator',
                  'missing-whitespace-around-modulo-operator'),
        'E8231': ("PEP8 %s: missing whitespace after ','",
                  "missing-whitespace-after-','"),
        'E8241': ("PEP8 %s: multiple spaces after ','", "multiple-spaces-after-','"),
        'E8242': ("PEP8 %s: tab after ','", "tab-after-','"),
        'E8251': ('PEP8 %s: unexpected spaces around keyword / parameter equals',
                  'unexpected-spaces-around-keyword-/-parameter-equals'),
        'E8261': ('PEP8 %s: at least two spaces before inline comment',
                  'at-least-two-spaces-before-inline-comment'),
        'E8262': ("PEP8 %s: inline comment should start with '# '",
                  "inline-comment-should-start-with-'#-'"),
        'E8271': ('PEP8 %s: multiple spaces after keyword',
                  'multiple-spaces-after-keyword'),
        'E8272': ('PEP8 %s: multiple spaces before keyword',
                  'multiple-spaces-before-keyword'),
        'E8273': ('PEP8 %s: tab after keyword', 'tab-after-keyword'),
        'E8274': ('PEP8 %s: tab before keyword', 'tab-before-keyword'),
    }


class PEP8BlankLine(_PEP8BaseChecker):
    '''
    Process PEP8 E3 codes
    '''

    _msgs = {
        'E8301': ('PEP8 %s: expected 1 blank line, found 0',
                  'expected-1-blank-line,-found-0'),
        'E8302': ('PEP8 %s: expected 2 blank lines, found 0',
                  'expected-2-blank-lines,-found-0'),
        'E8303': ('PEP8 %s: too many blank lines (3)',
                  'too-many-blank-lines-(3)'),
        'E8304': ('PEP8 %s: blank lines found after function decorator',
                  'blank-lines-found-after-function-decorator'),
    }


class PEP8Import(_PEP8BaseChecker):
    '''
    Process PEP8 E4 codes
    '''

    _msgs = {
        'E8401': ('PEP8 %s: multiple imports on one line',
                  'multiple-imports-on-one-line'),
    }


class PEP8LineLength(_PEP8BaseChecker):
    '''
    Process PEP8 E5 codes
    '''

    _msgs = {
        'E8501': ('PEP8 %s: line too long (82 > 79 characters)',
                  'line-too-long-(82->-79-characters)'),
        'E8502': ('PEP8 %s: the backslash is redundant between brackets',
                  'the-backslash-is-redundant-between-brackets')
    }

    msgs_map = {
        'E8501': 'C0301'
    }


class PEP8Statement(_PEP8BaseChecker):
    '''
    Process PEP8 E7 codes
    '''

    _msgs = {
        'E8701': ('PEP8 %s: multiple statements on one line (colon)',
                  'multiple-statements-on-one-line-(colon)'),
        'E8702': ('PEP8 %s: multiple statements on one line (semicolon)',
                  'multiple-statements-on-one-line-(semicolon)'),
        'E8703': ('PEP8 %s: statement ends with a semicolon',
                  'statement-ends-with-a-semicolon'),
        'E8711': ("PEP8 %s: comparison to None should be 'if cond is None:'",
                  "comparison-to-None-should-be-'if-cond-is-None:'"),
        'E8712': ("PEP8 %s: comparison to True should be 'if cond is True:' or 'if cond:'",
                  "comparison-to-True-should-be-'if-cond-is-True:'-or-'if-cond:'"),
        'E8721': ("PEP8 %s: do not compare types, use 'isinstance()'",
                  "do-not-compare-types,-use-'isinstance()'"),
    }


class PEP8Runtime(_PEP8BaseChecker):
    '''
    Process PEP8 E9 codes
    '''

    _msgs = {
        'E8901': ('PEP8 %s: SyntaxError or IndentationError',
                  'SyntaxError-or-IndentationError'),
        'E8902': ('PEP8 %s: IOError', 'IOError'),
    }


class PEP8IndentationWarning(_PEP8BaseChecker):
    '''
    Process PEP8 W1 codes
    '''

    _msgs = {
        'W8191': ('PEP8 %s: indentation contains tabs',
                  'indentation-contains-tabs'),
    }


class PEP8WhitespaceWarning(_PEP8BaseChecker):
    '''
    Process PEP8 W2 codes
    '''

    _msgs = {
        'W8291': ('PEP8 %s: trailing whitespace', 'trailing-whitespace'),
        'W8292': ('PEP8 %s: no newline at end of file', 'no-newline-at-end-of-file'),
        'W8293': ('PEP8 %s: blank line contains whitespace',
                  'blank-line-contains-whitespace'),
    }


class PEP8BlankLineWarning(_PEP8BaseChecker):
    '''
    Process PEP8 W3 codes
    '''

    _msgs = {
        'W8391': ('PEP8 %s: blank line at end of file',
                  'blank-line-at-end-of-file'),
    }


class PEP8DeprecationWarning(_PEP8BaseChecker):
    '''
    Process PEP8 W6 codes
    '''

    _msgs = {
        'W8601': ("PEP8 %s: .has_key() is deprecated, use 'in'",
                  ".has_key()-is-deprecated,-use-'in'"),
        'W8602': ('PEP8 %s: deprecated form of raising exception',
                  'deprecated-form-of-raising-exception'),
        'W8603': ("PEP8 %s: '<>' is deprecated, use '!='",
                  "'<>'-is-deprecated,-use-'!='"),
        'W8604': ("PEP8 %s: backticks are deprecated, use 'repr()'",
                  "backticks-are-deprecated,-use-'repr()'")
    }


def register(linter):
    '''
    required method to auto register this checker
    '''
    if HAS_PEP8 is False:
        return

    linter.register_checker(PEP8Indentation(linter))
    linter.register_checker(PEP8Whitespace(linter))
    linter.register_checker(PEP8BlankLine(linter))
    linter.register_checker(PEP8Import(linter))
    linter.register_checker(PEP8LineLength(linter))
    linter.register_checker(PEP8Statement(linter))
    linter.register_checker(PEP8Runtime(linter))
    linter.register_checker(PEP8IndentationWarning(linter))
    linter.register_checker(PEP8WhitespaceWarning(linter))
    linter.register_checker(PEP8BlankLineWarning(linter))
    linter.register_checker(PEP8DeprecationWarning(linter))
