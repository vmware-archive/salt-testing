# -*- coding: utf-8 -*-

import difflib
from pylint.interfaces import IRawChecker
from pylint.checkers import BaseChecker

from lib2to3 import refactor
from libmodernize.fixes import lib2to3_fix_names, six_fix_names


def diff_texts(old, new, f):
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
    diff = None

    def print_output(self, old, new, filename, equal):
        if equal:
            print 333
            self.diff = None
        else:
            self.diff = diff_texts(old, new, filename)


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
    options = ()

    def process_module(self, node):
        '''
        process a module

        the module's content is accessible via node.file_stream object
        '''

        avail_fixes = lib2to3_fix_names
        avail_fixes.update(six_fix_names)

        rt = PyLintRefactoringTool(
            sorted(avail_fixes), {'print_function': True},
        )
        rt.refactor_file(node.file, write=False)
        if rt.diff:
            for lineno, diff in rt.diff:
                self.add_message('W7001', line=lineno, args=diff)


def register(linter):
    '''
    required method to auto register this checker
    '''
    linter.register_checker(Py3Modernize(linter))
