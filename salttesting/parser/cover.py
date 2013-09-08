# -*- coding: utf-8 -*-
'''
    salttesting.parser.cover
    ~~~~~~~~~~~~~~~~~~~~~~~~

    Code coverage aware testing parser

    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`
    :copyright: © 2013 by the SaltStack Team, see AUTHORS for more details.
    :license: Apache 2.0, see LICENSE for more details.
'''

# Import python libs
import os
import re
import sys

# Import salt testing libs
from salttesting.parser import SaltTestingParser

# Import coverage libs
try:
    import coverage
    # Cover any processes if the environ variables are present
    coverage.process_startup()
    coverage_available = True
except ImportError:
    coverage_available = False


class SaltCoverageTestingParser(SaltTestingParser):
    '''
    Code coverage aware testing option parser
    '''
    def __init__(self, *args, **kwargs):
        SaltTestingParser.__init__(self, *args, **kwargs)
        self.code_coverage = None

        # Add the coverage related options
        self.output_options_group.add_option(
            '--coverage',
            default=False,
            action='store_true',
            help='Run tests and report code coverage'
        )
        self.output_options_group.add_option(
            '--coverage-xml',
            default=None,
            help='If provided, the path to where a XML report of the code '
                 'coverage will be written to'
        )
        self.output_options_group.add_option(
            '--coverage-report',
            default=None,
            help=('The directory where the generated HTML coverage report '
                  'will be saved to. The directory, if existing, will be '
                  'deleted before the report is generated. '
                  'Default: ./coverage-report')
        )
        self.output_options_group.add_option(
            '--no-coverage-report',
            default=False,
            action='store_true',
            help='Don\'t build the coverage HTML report'
        )

    def _validate_options(self):
        if (self.options.coverage or self.options.coverage_xml) and \
                coverage_available is False:
            self.error(
                'Cannot run tests with coverage report. '
                'Please install coverage>=3.5.3'
            )
        elif self.options.coverage or self.options.coverage_xml:
            coverage_version = tuple([
                int(part) for part in re.search(
                    r'([0-9.]+)', coverage.__version__).group(0).split('.')
            ])
            if coverage_version < (3, 5, 3):
                # Should we just print the error instead of exiting?
                self.error(
                    'Versions lower than 3.5.3 of the coverage library are '
                    'know to produce incorrect results. Please consider '
                    'upgrading...'
                )
        if self.options.coverage_report is None:
            self.options.coverage_report = os.path.join(
                os.getcwd(), 'coverage-report'
            )
        SaltTestingParser._validate_options(self)

    def start_coverage(self, track_processes=True, **coverage_options):
        '''
        Start code coverage.

        You can pass any coverage options as keyword arguments. For the
        available options please see:
            http://nedbatchelder.com/code/coverage/api.html
        '''
        if not self.options.coverage and not self.options.coverage_xml:
            return

        print(' * Starting Coverage')

        if track_processes is True:
            # Update environ so that any subprocess started on tests are also
            # included in the report
            os.environ['COVERAGE_PROCESS_START'] = '1'

        # Setup coverage
        self.code_coverage = coverage.coverage(**coverage_options)
        self.code_coverage.start()

    def stop_coverage(self, save_coverage=True):
        '''
        Stop code coverage.
        '''
        if not self.options.coverage and not self.options.coverage_xml:
            return

        print(' * Stopping coverage')
        self.code_coverage.stop()
        if save_coverage:
            print(' * Saving coverage info')
            self.code_coverage.save()

        if self.options.coverage_xml is not None:
            self.code_coverage.xml_report(
                outfile=self.options.coverage_xml
            )

        if self.options.no_coverage_report is False:
            print(
                ' * Generating Coverage HTML Report Under {0!r} ... '.format(
                    self.options.coverage_report
                )
            ),
            sys.stdout.flush()

            if os.path.isdir(self.options.coverage_report):
                import shutil
                shutil.rmtree(self.options.coverage_report)
            self.code_coverage.html_report(
                directory=self.options.coverage_report
            )
            print('Done.\n')

    def print_overall_testsuite_report(self, save_coverage=True):
        SaltTestingParser.print_overall_testsuite_report(self)
        if self.options.coverage is False:
            return
        self.stop_coverage(save_coverage)

    def finalize(self, exit_code, save_coverage=True):
        if self.options.no_report:
            if self.options.coverage:
                self.stop_coverage(save_coverage)
        SaltTestingParser.finalize(self, exit_code)
