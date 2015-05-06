# -*- coding: utf-8 -*-
# ----- DEPRECATED PYLINT PLUGIN ------------------------------------------------------------------------------------>
# This Pylint plugin is deprecated. Development continues on the SaltPyLint package
# <---- DEPRECATED PYLINT PLUGIN -------------------------------------------------------------------------------------
from __future__ import absolute_import
import os
import glob
import stat
from pylint.interfaces import IRawChecker
from pylint.checkers import BaseChecker


class FilePermsChecker(BaseChecker):
    '''
    Check for files with undesirable permissions
    '''

    __implements__ = IRawChecker

    name = 'fileperms'
    msgs = {'E0599': ('Module file has the wrong file permissions: %s',
                      'file-perms',
                      ('Wrong file permissions')),
           }

    priority = -1

    options = (('fileperms-default',
                {'default': '0644', 'type': 'string', 'metavar': 'ZERO_PADDED_PERM',
                 'help': 'Desired file permissons. Default: 0644'}
               ),
               ('fileperms-ignore-paths',
                {'default': (), 'type': 'csv', 'metavar': '<comma-separated-list>',
                 'help': 'File paths to ignore file permission. Glob patterns allowed.'}
               )
              )

    def process_module(self, node):
        '''
        process a module
        '''

        for listing in self.config.fileperms_ignore_paths:
            if node.file.split('{0}/'.format(os.getcwd()))[-1] in glob.glob(listing):
                # File is ignored, no checking should be done
                return

        desired_perm = self.config.fileperms_default
        desired_perm = desired_perm.strip('"').strip('\'').lstrip('0').zfill(4)
        if desired_perm[0] != '0':
            # Always include a leading zero
            desired_perm = '0{0}'.format(desired_perm)

        module_perms = str(oct(stat.S_IMODE(os.stat(node.file).st_mode)))
        if module_perms != desired_perm:
            self.add_message('E0599', line=1, args=module_perms)


def register(linter):
    '''
    required method to auto register this checker
    '''
    linter.register_checker(FilePermsChecker(linter))
