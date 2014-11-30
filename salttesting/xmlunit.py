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
import sys
import logging

try:
    import xmlrunner.runner
    import xmlrunner.result
    HAS_XMLRUNNER = True

    #class _DelegateIO(xmlrunner._DelegateIO):
    #    def __getattr__(self, attr):
    #        try:
    #            return getattr(self._captured, attr)
    #        except AttributeError:
    #            return getattr(self.delegate, attr)

    class _XMLTestResult(xmlrunner.result._XMLTestResult):
        def startTest(self, test):
            logging.getLogger(__name__).debug(
                '>>>>> START >>>>> {0}'.format(test.id())
            )
            # xmlrunner classes are NOT new-style classes
            return xmlrunner.result._XMLTestResult.startTest(self, test)

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

        #def _patch_standard_output(self):
        #    '''
        #    Replaces stdout and stderr streams with string-based streams
        #    in order to capture the tests' output.
        #    '''
        #    sys.stdout = _DelegateIO(sys.stdout)
        #    sys.stderr = _DelegateIO(sys.stderr)

except ImportError:
    HAS_XMLRUNNER = False

    class XMLTestRunner(object):
        '''
        This is a dumb class just so we don't break projects at import time
        '''
