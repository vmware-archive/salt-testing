# -*- coding: utf-8 -*-

from __future__ import absolute_import
from libmodernize.fixes import fix_xrange_six


class FixXrangeSaltSix(fix_xrange_six.FixXrangeSix):

    skip_on = 'salt.ext.six.moves.range'
