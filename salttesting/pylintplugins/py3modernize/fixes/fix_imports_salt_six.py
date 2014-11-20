# -*- coding: utf-8 -*-

from __future__ import absolute_import
from libmodernize.fixes import fix_imports_six as libmodernize_fix_imports
from lib2to3.fixes import fix_imports as lib2to3_fix_imports

MAPPING = {}

for key, value in libmodernize_fix_imports.FixImportsSix.mapping.iteritems():
    MAPPING[key] = 'salt.ext.{0}'.format(value)


class FixImportsSaltSix(lib2to3_fix_imports.FixImports):

    mapping = MAPPING
