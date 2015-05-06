# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`
    :copyright: © 2013 by the SaltStack Team, see AUTHORS for more details.
    :license: Apache 2.0, see LICENSE for more details.


    ===========================
    Pylint Smartup Transformers
    ===========================

    This plugin will register some transform functions which will allow PyLint to better
    understand some classed used in Salt which trigger, `no-member` and `maybe-no-member`
    A bridge between the `pep8`_ library and PyLint

'''
# ----- DEPRECATED PYLINT PLUGIN ------------------------------------------------------------------------------------>
# This Pylint plugin is deprecated. Development continues on the SaltPyLint package
# <---- DEPRECATED PYLINT PLUGIN -------------------------------------------------------------------------------------
from __future__ import absolute_import
# Import PyLint libs
from astroid import nodes, MANAGER


def rootlogger_transform(obj):
    if obj.name != 'RootLogger':
        return

    def _inject_method(cls, msg, *args, **kwargs):
        pass

    if not hasattr(obj, 'trace'):
        setattr(obj, 'trace', _inject_method)

    if not hasattr(obj, 'garbage'):
        setattr(obj, 'garbage', _inject_method)


def register(linter):
    '''
    Register the transformation functions.
    '''
    MANAGER.register_transform(nodes.Class, rootlogger_transform)
