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
import logging

try:
    import xmlrunner
    HAS_XMLRUNNER = True

    class _XMLTestResult(xmlrunner._XMLTestResult):
        def startTest(self, test):
            logging.getLogger(__name__).debug(
                '>>>>> START >>>>> {0}'.format(test.id())
            )
            # xmlrunner classes are NOT new-style classes
            return xmlrunner._XMLTestResult.startTest(self, test)

        def stopTest(self, test):
            logging.getLogger(__name__).debug(
                '<<<<< END <<<<<<< {0}'.format(test.id())
            )
            # xmlrunner classes are NOT new-style classes
            return xmlrunner._XMLTestResult.stopTest(self, test)

    class XMLTestRunner(xmlrunner.XMLTestRunner):
        def _make_result(self):
            return _XMLTestResult(
                self.stream,
                self.descriptions,
                self.verbosity,
                self.elapsed_times
            )

        def run(self, test):
            result = xmlrunner.XMLTestRunner.run(self, test)
            self.stream.writeln('Finished generating XML reports')
            return result

except ImportError:
    HAS_XMLRUNNER = False

    class XMLTestRunner(object):
        '''
        This is a dumb class just so we don't break projects at import time
        '''
