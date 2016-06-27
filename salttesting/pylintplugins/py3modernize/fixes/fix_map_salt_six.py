# -*- coding: utf-8 -*-

from __future__ import absolute_import
from libmodernize.fixes import fix_map


class FixMapSaltSix(fix_map.FixMap):

    skip_on = 'salt.ext.six.moves.map'
