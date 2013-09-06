# -*- coding: utf-8 -*-
'''
    salttesting.parser
    ~~~~~~~~~~~~~~~~~~

    Salt-Testing CLI access classes

    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`
    :copyright: © 2013 by the SaltStack Team, see AUTHORS for more details.
    :license: Apache 2.0, see LICENSE for more details.
'''

import os
import sys
import shutil
import logging
import optparse
import tempfile

from salttesting import TestLoader, TextTestRunner
from salttesting.ext.HTMLTestRunner import HTMLTestRunner
try:
    from salttesting.ext import console
    width, height = console.getTerminalSize()
    PNUM = width
except:
    PNUM = 70

try:
    import xmlrunner
except ImportError:
    xmlrunner = None


def print_header(header, sep='~', top=True, bottom=True, inline=False,
                 centered=False):
    '''
    Allows some pretty printing of headers on the console, either with a
    "ruler" on bottom and/or top, inline, centered, etc.
    '''
    if top and not inline:
        print(sep * PNUM)

    if centered and not inline:
        fmt = u'{0:^{width}}'
    elif inline and not centered:
        fmt = u'{0:{sep}<{width}}'
    elif inline and centered:
        fmt = u'{0:{sep}^{width}}'
    else:
        fmt = u'{0}'
    print(fmt.format(header, sep=sep, width=PNUM))

    if bottom and not inline:
        print(sep * PNUM)


class SaltTestingParser(optparse.OptionParser):
    support_destructive_tests_selection = False

    def __init__(self, testsuite_directory, *args, **kwargs):
        # Get XML output settings
        xml_output_dir_env_var = kwargs.pop(
            'xml_output_from_env',
            'XML_TESTS_OUTPUT_DIR'
        )
        xml_output_dir = kwargs.pop('xml_output_dir', None)
        self.xml_output_dir = os.environ.get(
            xml_output_dir_env_var,
            xml_output_dir or os.path.join(
                tempfile.gettempdir(), 'xml-tests-output'
            )
        )

        # Get HTML output settings
        html_output_dir_env_var = kwargs.pop(
            'html_output_from_env',
            'HTML_TESTS_OUTPUT_DIR'
        )
        html_output_dir = kwargs.pop('html_output_dir', None)
        self.html_output_dir = os.environ.get(
            html_output_dir_env_var,
            html_output_dir or os.path.join(
                tempfile.gettempdir(), 'html-tests-output'
            )
        )

        # Get the desired logfile to use while running tests
        self.tests_logfile = kwargs.pop('tests_logfile', None)

        optparse.OptionParser.__init__(self, *args, **kwargs)
        self.testsuite_directory = testsuite_directory
        self.testsuite_results = []

        self.test_selection_group = optparse.OptionGroup(
            self,
            'Tests Selection Options',
            'Select which tests are to be executed'
        )
        if self.support_destructive_tests_selection is True:
            self.test_selection_group.add_option(
                '--run-destructive',
                action='store_true',
                default=False,
                help=('Run destructive tests. These tests can include adding '
                      'or removing users from your system for example. '
                      'Default: %default')
            )
        self.test_selection_group.add_option(
            '-n',
            '--name',
            dest='name',
            action='append',
            default=[],
            help=('Specific test name to run. A named test is the module path '
                  'relative to the tests directory')
        )
        self.add_option_group(self.test_selection_group)

        self.output_options_group = optparse.OptionGroup(
            self, 'Output Options'
        )
        self.output_options_group.add_option(
            '-v',
            '--verbose',
            dest='verbosity',
            default=1,
            action='count',
            help='Verbose test runner output'
        )
        if self.xml_output_dir is not None:
            self.output_options_group.add_option(
                '-x',
                '--xml',
                dest='xml_out',
                default=False,
                action='store_true',
                help='XML test runner output(Output directory: {0})'.format(
                    self.xml_output_dir
                )
            )
        if self.html_output_dir:
            self.output_options_group.add_option(
                '--html-out',
                default=False,
                action='store_true',
                help='HTML test runner output(Output directory: {0})'.format(
                    self.html_output_dir
                )
            )
        self.output_options_group.add_option(
            '--no-report',
            default=False,
            action='store_true',
            help='Do NOT show the overall tests result'
        )
        self.add_option_group(self.output_options_group)

        self.fs_cleanup_options_group = optparse.OptionGroup(
            self, 'File system cleanup Options'
        )
        self.fs_cleanup_options_group.add_option(
            '--clean',
            dest='clean',
            default=True,
            action='store_true',
            help=('Clean up test environment before and after running the '
                  'tests suite (default behaviour)')
        )
        self.fs_cleanup_options_group.add_option(
            '--no-clean',
            dest='clean',
            action='store_false',
            help=('Don\'t clean up test environment before and after the '
                  'tests suite execution (speed up test process)')
        )
        self.add_option_group(self.fs_cleanup_options_group)
        self.setup_additional_options()

    def parse_args(self, args=None, values=None):
        self.options, self.args = optparse.OptionParser.parse_args(
            self, args, values
        )
        self.pre_execution_cleanup()
        self._validate_options()
        self._setup_logging()
        return (self.options, self.args)

    def setup_additional_options(self):
        '''
        Subclasses should add additional options in this overridden method
        '''

    def _validate_options(self):
        '''
        Validate the default available options
        '''
        if self.xml_output_dir is not None and self.options.xml_out and \
                xmlrunner is None:
            self.error(
                '\'--xml\' is not available. The xmlrunner library is not '
                'installed.'
            )
        elif self.xml_output_dir is not None and self.options.xml_out:
            if not os.path.isdir(self.xml_output_dir):
                os.makedirs(self.xml_output_dir)
            print(
                'Generated XML reports will be stored on {0!r}'.format(
                    self.xml_output_dir
                )
            )

        if self.html_output_dir is not None and self.options.html_out:
            if not os.path.isdir(self.html_output_dir):
                os.makedirs(self.html_output_dir)
            print(
                'Generated HTML reports will be stored on {0!r}'.format(
                    self.html_output_dir
                )
            )

        self.validate_options()

        if self.support_destructive_tests_selection:
            # Set the required environment variable in order to know if
            # destructive tests should be executed or not.
            os.environ['DESTRUCTIVE_TESTS'] = str(self.options.run_destructive)

        print('Current Directory: {0}'.format(os.getcwd()))
        print_header(
            'Test suite is running under PID {0}'.format(os.getpid()),
            bottom=False
        )

    def validate_options(self):
        '''
        Validate the provided options. Override this method to run your own
        validation procedures.
        '''

    def _setup_logging(self):
        '''
        Setup python's logging system to work with/for the tests suite
        '''
        # Setup tests logging
        formatter = logging.Formatter(
            '%(asctime)s,%(msecs)03.0f [%(name)-5s:%(lineno)-4d]'
            '[%(levelname)-8s] %(message)s',
            datefmt='%H:%M:%S'
        )
        if self.tests_logfile:
            filehandler = logging.FileHandler(
                mode='w',           # Not preserved between re-runs
                filename=self.tests_logfile
            )
            filehandler.setLevel(logging.DEBUG)
            filehandler.setFormatter(formatter)
            logging.root.addHandler(filehandler)
            logging.root.setLevel(logging.DEBUG)

            print_header(
                'Logging tests on {0}'.format(self.tests_logfile), bottom=False
            )

        # With greater verbosity we can also log to the console
        if self.options.verbosity > 2:
            consolehandler = logging.StreamHandler(sys.stderr)
            consolehandler.setLevel(logging.INFO)       # -vv
            consolehandler.setFormatter(formatter)
            if not hasattr(logging, 'TRACE'):
                logging.TRACE = 5
                logging.addLevelName(logging.TRACE, 'TRACE')
            if not hasattr(logging, 'GARBAGE'):
                logging.GARBAGE = 1
                logging.addLevelName(logging.GARBAGE, 'GARBAGE')
            handled_levels = {
                3: logging.DEBUG,   # -vvv
                4: logging.TRACE,   # -vvvv
                5: logging.GARBAGE  # -vvvvv
            }
            if self.options.verbosity > 3:
                consolehandler.setLevel(
                    handled_levels.get(
                        self.options.verbosity,
                        self.options.verbosity > 5 and 5 or 3
                    )
                )
            logging.root.addHandler(consolehandler)

    def pre_execution_cleanup(self):
        '''
        Run any initial clean up operations. If sub-classed, don't forget to
        call SaltTestingParser.pre_execution_cleanup(self) from the overridden
        method.
        '''
        if self.options.clean is True:
            for path in (self.xml_output_dir, self.html_output_dir):
                if path is None:
                    continue
                if os.path.isdir(path):
                    shutil.rmtree(path)

    def run_suite(self, path, display_name, suffix='[!_]*.py',
                  load_from_name=False):
        '''
        Execute a unit test suite
        '''
        loader = TestLoader()
        if load_from_name:
            tests = loader.loadTestsFromName(display_name)
        else:
            tests = loader.discover(path, suffix, self.testsuite_directory)

        header = '{0} Tests'.format(display_name)
        print_header('Starting {0}'.format(header))

        if self.options.xml_out:
            runner = xmlrunner.XMLTestRunner(
                output=self.xml_output_dir,
                verbosity=self.options.verbosity
            ).run(tests)
            self.testsuite_results.append((header, runner))
        elif self.options.html_out:
            runner = HTMLTestRunner(
                stream=open(
                    os.path.join(
                        self.html_output_dir, 'report_{0}.html'.format(
                            header.replace(' ', '_')
                        )
                    ),
                    'w'
                ),
                verbosity=self.options.verbosity,
                title=header,
            ).run(tests)
            self.testsuite_results.append((header, runner))
        else:
            runner = TextTestRunner(
                stream=sys.stdout,
                verbosity=self.options.verbosity).run(tests)
            self.testsuite_results.append((header, runner))
        return runner.wasSuccessful()

    def print_overall_testsuite_report(self):
        '''
        Print a nicely formatted report about the test suite results
        '''
        print
        print_header(
            u'  Overall Tests Report  ', sep=u'=', centered=True, inline=True
        )

        failures = errors = skipped = passed = 0
        no_problems_found = True
        for (name, results) in self.testsuite_results:
            failures += len(results.failures)
            errors += len(results.errors)
            skipped += len(results.skipped)
            passed += results.testsRun - len(
                results.failures + results.errors + results.skipped
            )

            if not results.failures and not results.errors and \
                    not results.skipped:
                continue

            no_problems_found = False

            print_header(u'*** {0}  '.format(name), sep=u'*', inline=True)
            if results.skipped:
                print_header(
                    u' --------  Skipped Tests  ', sep='-', inline=True
                )
                maxlen = len(
                    max([testcase.id() for (testcase, reason) in
                         results.skipped], key=len)
                )
                fmt = u'   -> {0: <{maxlen}}  ->  {1}'
                for testcase, reason in results.skipped:
                    print(fmt.format(testcase.id(), reason, maxlen=maxlen))
                print_header(u' ', sep='-', inline=True)

            if results.errors:
                print_header(
                    u' --------  Tests with Errors  ', sep='-', inline=True
                )
                for testcase, reason in results.errors:
                    print_header(
                        u'   -> {0}  '.format(testcase.id()),
                        sep=u'.', inline=True
                    )
                    for line in reason.rstrip().splitlines():
                        print('       {0}'.format(line.rstrip()))
                    print_header(u'   ', sep=u'.', inline=True)
                print_header(u' ', sep='-', inline=True)

            if results.failures:
                print_header(
                    u' --------  Failed Tests  ', sep='-', inline=True
                )
                for testcase, reason in results.failures:
                    print_header(
                        u'   -> {0}  '.format(testcase.id()),
                        sep=u'.', inline=True
                    )
                    for line in reason.rstrip().splitlines():
                        print('       {0}'.format(line.rstrip()))
                    print_header(u'   ', sep=u'.', inline=True)
                print_header(u' ', sep='-', inline=True)

        if no_problems_found:
            print_header(
                u'***  No Problems Found While Running Tests  ',
                sep=u'*', inline=True
            )

        print_header(u'', sep=u'=', inline=True)
        total = sum([passed, skipped, errors, failures])
        print(
            '{0} (total={1}, skipped={2}, passed={3}, failures={4}, '
            'errors={5}) '.format(
                (errors or failures) and 'FAILED' or 'OK',
                total, skipped, passed, failures, errors
            )
        )
        print_header(
            '  Overall Tests Report  ', sep='=', centered=True, inline=True
        )
        return

    def post_execution_cleanup(self):
        '''
        Run any final clean-up operations.  If sub-classed, don't forget to
        call SaltTestingParser.post_execution_cleanup(self) from the overridden
        method.
        '''
        if self.options.clean is True:
            for path in (self.xml_output_dir, self.html_output_dir):
                if path is None:
                    continue
                if os.path.isdir(path):
                    shutil.rmtree(path)

    def finalize(self, exit_code=0):
        '''
        Run the finalization procedures. Show report, clean-up file-system, etc
        '''
        if self.options.no_report is False:
            self.print_overall_testsuite_report()
        self.post_execution_cleanup()
        self.exit(exit_code)


class SaltTestcaseParser(SaltTestingParser):
    '''
    Option parser to run one or more ``unittest.case.TestCase``, ie, no
    discovery involved.
    '''
    def __init__(self, *args, **kwargs):
        SaltTestingParser.__init__(self, None, *args, **kwargs)
        self.usage = '%prog [options]'
        self.option_groups.remove(self.test_selection_group)
        if self.has_option('--xml-out'):
            self.remove_option('--xml-out')
        if self.has_option('--html-out'):
            self.remove_option('--html-out')

    def get_prog_name(self):
        return '{0} {1}'.format(sys.executable.split(os.sep)[-1], sys.argv[0])

    def run_testcase(self, testcase):
        '''
        Run one or more ``unittest.case.TestCase``
        '''
        header = ''
        loader = TestLoader()
        if isinstance(testcase, list):
            for case in testcase:
                tests = loader.loadTestsFromTestCase(case)
        else:
            tests = loader.loadTestsFromTestCase(testcase)

        if not isinstance(testcase, list):
            header = '{0} Tests'.format(testcase.__name__)
            print_header('Starting {0}'.format(header))

        runner = TextTestRunner(
            verbosity=self.options.verbosity).run(tests)
        self.testsuite_results.append((header, runner))
        return runner.wasSuccessful()


def run_testcase(testcase):
    '''
    Helper function which can be used in `__main__` block to execute that
    specific ``unittest.case.TestCase`` tests.
    '''
    parser = SaltTestcaseParser()
    parser.parse_args()
    if parser.run_testcase(testcase) is False:
        parser.finalize(1)
    parser.finalize(0)
