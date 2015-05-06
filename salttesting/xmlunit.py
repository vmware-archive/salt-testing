# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`
    :copyright: © 2014 by the SaltStack Team, see AUTHORS for more details.
    :license: Apache 2.0, see LICENSE for more details.


    salttesting.xmlunit
    ~~~~~~~~~~~~~~~~~~~

    XML Unit Tests
'''

# Import python libs
from __future__ import absolute_import
import sys
import locale
import logging

# Import 3rd-party libs
import six
from six import StringIO

log = logging.getLogger(__name__)


try:
    import xmlrunner.runner
    import xmlrunner.result
    HAS_XMLRUNNER = True

    class _DelegateIO(object):
        '''
        This class defines an object that captures whatever is written to
        a stream or file.
        '''

        def __init__(self, delegate):
            self._captured = StringIO()
            self.delegate = delegate

        def _get_encodings(self):
            if hasattr(self, '_encodings'):
                return self._encodings
            encodings = []
            loc_enc = locale.getdefaultlocale()[-1]
            if loc_enc:
                encodings.append(loc_enc)
            def_enc = sys.getdefaultencoding()
            if def_enc not in encodings:
                encodings.append(def_enc)
            if 'utf-8' not in encodings:
                encodings.append('utf-8')
            self._encodings = encodings
            return encodings

        def write(self, text):
            if not isinstance(text, six.text_type):
                log.debug('Converting non unicode text into unicde')
                for enc in self._get_encodings():
                    try:
                        text = text.decode(enc)
                        break
                    except UnicodeDecodeError:
                        continue
            if isinstance(text, six.text_type):
                text = text.encode('utf-8')
            self._captured.write(text)
            self.delegate.write(text)

        def __getattr__(self, attr):
            try:
                return getattr(self._captured, attr)
            except AttributeError:
                return getattr(self.delegate, attr)

    class _XMLTestResult(xmlrunner.result._XMLTestResult):
        def startTest(self, test):
            logging.getLogger(__name__).debug(
                '>>>>> START >>>>> {0}'.format(test.id())
            )
            # xmlrunner classes are NOT new-style classes
            xmlrunner.result._XMLTestResult.startTest(self, test)
            if self.buffer:
                # Let's override the values of self._stdXXX_buffer
                # We want a similar sys.stdXXX file like behaviour
                self._stderr_buffer = _DelegateIO(sys.__stderr__)
                self._stdout_buffer = _DelegateIO(sys.__stdout__)
                sys.stderr = self._stderr_buffer
                sys.stdout = self._stdout_buffer

        def stopTest(self, test):
            logging.getLogger(__name__).debug(
                '<<<<< END <<<<<<< {0}'.format(test.id())
            )
            # xmlrunner classes are NOT new-style classes
            return xmlrunner.result._XMLTestResult.stopTest(self, test)

    class XMLTestRunner(xmlrunner.runner.XMLTestRunner):
        def _make_result(self):
            return _XMLTestResult(
                self.stream,
                self.descriptions,
                self.verbosity,
                self.elapsed_times
            )

        def run(self, test):
            result = xmlrunner.runner.XMLTestRunner.run(self, test)
            self.stream.writeln('Finished generating XML reports')
            return result

except ImportError:
    HAS_XMLRUNNER = False

    class XMLTestRunner(object):
        '''
        This is a dumb class just so we don't break projects at import time
        '''
