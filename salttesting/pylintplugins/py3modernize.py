# -*- coding: utf-8 -*-

import difflib
from pylint.interfaces import IRawChecker
from pylint.checkers import BaseChecker

from lib2to3 import refactor
from libmodernize.fixes import lib2to3_fix_names, opt_in_fix_names, six_fix_names

FIXES = lib2to3_fix_names
FIXES.update(opt_in_fix_names)
FIXES.update(six_fix_names)

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
    msgs = {'W7001': ('Incompatible Python 3 code found. Proposed fix:\n%s',
                      'incompatible-py3-code',
                      ('Incompatible Python 3 code found')),
            }

    priority = -1

    options = (('py3modernize-nofix',
                {'default': '', 'type': 'multiple_choice', 'metavar': '<comma-separated-list>',
                 'choices': sorted(FIXES),
                 'help': 'Comma separated list of fixer names not to fix.'}
                ),
                ('py3modernize-six-unicode',
                 {'default': 0, 'type': 'yn', 'metavar': '<y_or_n>',
                  'help': 'Wrap unicode literals in six.u().'}
                 ),
                ('py3modernize-future-unicode',
                 {'default': 0, 'type': 'yn', 'metavar': '<y_or_n>',
                  'help': 'Use \'from __future__ import unicode_literals\' (only '
                          'useful for Python 2.6+).'}
                 ),
                ('py3modernize-no-six',
                 {'default': 0, 'type': 'yn', 'metavar': '<y_or_n>',
                  'help': 'Exclude fixes that depend on the six package.'}
                 ),
                ('py3modernize-print-function',
                 {'default': 1, 'type': 'yn', 'metavar': '<y_or_n>',
                  'help': 'Modify the grammar so that print() is a function.'}
                 ),
              )

    def process_module(self, node):
        '''
        process a module

        the module's content is accessible via node.file_stream object
        '''

        flags = {}

        if self.config.py3modernize_print_function:
            flags['print_function'] = True

        avail_fixes = set(refactor.get_fixers_from_package('libmodernize.fixes'))
        avail_fixes.update(lib2to3_fix_names)

        default_fixes = avail_fixes.difference(opt_in_fix_names)
        unwanted_fixes = set(self.config.py3modernize_nofix)
        if self.config.py3modernize_six_unicode:
            unwanted_fixes.add('libmodernize.fixes.fix_unicode_future')
        elif self.config.py3modernize_future_unicode:
            unwanted_fixes.add('libmodernize.fixes.fix_unicode')
        else:
            unwanted_fixes.add('libmodernize.fixes.fix_unicode_future')
            unwanted_fixes.add('libmodernize.fixes.fix_unicode')

        if self.config.py3modernize_no_six:
            unwanted_fixes.update(six_fix_names)

        requested = default_fixes
        fixer_names = requested.difference(unwanted_fixes)

        rft = PyLintRefactoringTool(sorted(fixer_names), flags)
        rft.refactor_file(node.file, write=False)
        for lineno, diff in rft.diff:
            self.add_message('W7001', line=lineno, args=diff)


def register(linter):
    '''
    required method to auto register this checker
    '''
    linter.register_checker(Py3Modernize(linter))
