# -*- coding: utf-8 -*-

from __future__ import absolute_import
from libmodernize.fixes import fix_filter


class FixFilterSaltSix(fix_filter.FixFilter):

    skip_on = 'salt.ext.six.moves.filter'
