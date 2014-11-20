# -*- coding: utf-8 -*-

from __future__ import absolute_import
from libmodernize.fixes import fix_zip


class FixZipSaltSix(fix_zip.FixZip):

    skip_on = 'salt.ext.six.moves.zip'
