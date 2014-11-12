# -*- coding: utf-8 -*-

import difflib
import warnings
from pylint.interfaces import IRawChecker
from pylint.checkers import BaseChecker

try:
    from lib2to3 import refactor
    from libmodernize.fixes import lib2to3_fix_names, opt_in_fix_names, six_fix_names
    HAS_REQUIRED_LIBS = True
except ImportError:
    HAS_REQUIRED_LIBS = False
    warnings.warn(
        'The modernize pylint plugin will not be available. Either '
        '\'lib2to3\', unlikely, or \'libmodernize\' was not importable.',
        RuntimeWarning
    )

if HAS_REQUIRED_LIBS:
    FIXES = lib2to3_fix_names
    FIXES.update(opt_in_fix_names)
    FIXES.update(six_fix_names)
else:
    FIXES = ()


def diff_texts(old, new):
    diffs = []

    if not isinstance(old, list):
        old = old.splitlines()

    if not isinstance(new, list):
        new = new.splitlines()

    for group in difflib.SequenceMatcher(None, old, new).get_grouped_opcodes(3):
        start_line = None
        diff = []
        for tag, i1, i2, j1, j2 in group:
            if start_line is None:
                start_line = i1
            if tag == 'equal':
                for line in old[i1:i2]:
                    diff.append(' ' + line)
                continue
            if tag in ('replace', 'delete'):
                for line in old[i1:i2]:
                    diff.append('-' + line)
            if tag in ('replace', 'insert'):
                for line in new[j1:j2]:
                    diff.append('+' + line)
        diffs.append((start_line, '\n'.join(diff)))
    return diffs


class PyLintRefactoringTool(refactor.MultiprocessRefactoringTool):

    diff = ()

    def print_output(self, old, new, filename, equal):
        self.diff = () if equal else diff_texts(old, new)


class Py3Modernize(BaseChecker):
    '''
    Check for PEP263 compliant file encoding in file.
    '''

    __implements__ = IRawChecker

    name = 'modernize'
    msgs = {'W1699': ('Incompatible Python 3 code found. Proposed fix:\n%s',
                      'incompatible-py3-code',
                      ('Incompatible Python 3 code found')),
            }

    priority = -1

    options = (('modernize-doctests-only',
               {'default': 0, 'type': 'yn', 'metavar': '<y_or_n>',
                'help': 'Fix up doctests only'}
               ),
               ('modernize-fix',
                {'default': (), 'type': 'csv', 'metavar': '<comma-separated-list>',
                 'help': 'Each FIX specifies a transformation; "default" includes '
                         'default fixes.'}
               ),
               ('modernize-nofix',
                {'default': '', 'type': 'multiple_choice', 'metavar': '<comma-separated-list>',
                 'choices': sorted(FIXES),
                 'help': 'Comma separated list of fixer names not to fix.'}
               ),
               ('modernize-print-function',
                {'default': 1, 'type': 'yn', 'metavar': '<y_or_n>',
                 'help': 'Modify the grammar so that print() is a function.'}
               ),
               ('modernize-six-unicode',
                {'default': 0, 'type': 'yn', 'metavar': '<y_or_n>',
                 'help': 'Wrap unicode literals in six.u().'}
               ),
               ('modernize-future-unicode',
                {'default': 0, 'type': 'yn', 'metavar': '<y_or_n>',
                 'help': 'Use \'from __future__ import unicode_literals\' (only '
                         'useful for Python 2.6+).'}
               ),
               ('modernize-no-six',
                {'default': 0, 'type': 'yn', 'metavar': '<y_or_n>',
                 'help': 'Exclude fixes that depend on the six package.'}
               )
              )

    def process_module(self, node):
        '''
        process a module

        the module's content is accessible via node.file_stream object
        '''

        flags = {}

        if self.config.modernize_print_function:
            flags['print_function'] = True

        avail_fixes = set(refactor.get_fixers_from_package('libmodernize.fixes'))
        avail_fixes.update(lib2to3_fix_names)

        default_fixes = avail_fixes.difference(opt_in_fix_names)
        unwanted_fixes = set(self.config.modernize_nofix)
        if self.config.modernize_six_unicode:
            unwanted_fixes.add('libmodernize.fixes.fix_unicode_future')
        elif self.config.modernize_future_unicode:
            unwanted_fixes.add('libmodernize.fixes.fix_unicode')
        else:
            unwanted_fixes.add('libmodernize.fixes.fix_unicode_future')
            unwanted_fixes.add('libmodernize.fixes.fix_unicode')

        if self.config.modernize_no_six:
            unwanted_fixes.update(six_fix_names)

        explicit = set()

        if self.config.modernize_fix:
            default_present = False
            for fix in self.config.modernize_fix:
                if fix == 'default':
                    default_present = True
                else:
                    explicit.add(fix)

            requested = default_fixes.union(explicit) if default_present else explicit
        else:
            requested = default_fixes

        requested = default_fixes
        fixer_names = requested.difference(unwanted_fixes)

        rft = PyLintRefactoringTool(sorted(fixer_names), flags, sorted(explicit))
        rft.refactor_file(node.file,
                          write=False,
                          doctests_only=self.config.modernize_doctests_only)

        for lineno, diff in rft.diff:
            # Since PyLint's python3 checker uses <Type>16<int><int>, we'll also use that range
            self.add_message('W1699', line=lineno, args=diff)


def register(linter):
    '''
    required method to auto register this checker
    '''
    if HAS_REQUIRED_LIBS:
        linter.register_checker(Py3Modernize(linter))
