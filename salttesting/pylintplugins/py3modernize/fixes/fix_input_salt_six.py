# This is a derived work of libmodernize.fixes.fix_input_six which
# in turn is deriverd work of Lib/lib2to3/fixes/fix_input.py and
# Lib/lib2to3/fixes/fix_raw_input.py. Those files are under the
# copyright of the Python Software Foundation and licensed under the
# Python Software Foundation License 2.
#
# Copyright notice:
#
#     Copyright (c) 2001, 2002, 2003, 2004, 2005, 2006, 2007, 2008, 2009, 2010,
#     2011, 2012, 2013, 2014 Python Software Foundation. All rights reserved.
from __future__ import absolute_import
from libmodernize.fixes import fix_input_six


class FixInputSaltSix(fix_input_six.FixInputSix):

    skip_on = 'salt.ext.six.moves.input'
