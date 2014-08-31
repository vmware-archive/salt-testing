# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`


    salttesting.runtests
    ~~~~~~~~~~~~~~~~~~~~

    CLI entry point to run salt related tests
'''

# Import Python modules
from __future__ import absolute_import
import os
import imp
import sys
import time
import shutil
import fnmatch
import logging
import argparse
import tempfile
import warnings
import multiprocessing
from copy import deepcopy
from datetime import datetime, timedelta
try:
    import pwd
except ImportError:
    pass


# Import Salt Testing libs
from salttesting import version
from salttesting.unit import TestLoader, TestSuite, TextTestRunner
from salttesting.xmlunit import HAS_XMLRUNNER, XMLTestRunner
try:
    from salttesting.ext import console
    SCREEN_COLS, SCREEN_ROWS = console.getTerminalSize()  # pylint: disable=unpacking-non-sequence
except Exception:  # pylint: disable=broad-except
    SCREEN_COLS = 80


# Import Salt libs
try:
    from salt.log.handlers import TemporaryLoggingHandler
except ImportError:
    if sys.version_info < (2, 7):
        class NewStyleClassMixIn(object):
            '''
            Simple new style class to make pylint shut up!
            This is required because SaltLoggingClass can't subclass object directly:

                'Cannot create a consistent method resolution order (MRO) for bases'
            '''

        # Since the NullHandler is only available on python >= 2.7, here's a copy
        # with NewStyleClassMixIn so it's also a new style class
        class NullHandler(logging.Handler, NewStyleClassMixIn):
            '''
            This is 1 to 1 copy of python's 2.7 NullHandler
            '''
            def handle(self, record):
                pass

            def emit(self, record):
                pass

            def createLock(self):  # pylint: disable=C0103
                self.lock = None

        logging.NullHandler = NullHandler

    class TemporaryLoggingHandler(logging.NullHandler):
        '''
        Copied from ``salt.log.handlers``
        '''

        def __init__(self, level=logging.NOTSET, max_queue_size=10000):
            self.__max_queue_size = max_queue_size
            super(TemporaryLoggingHandler, self).__init__(level=level)  # pylint: disable=bad-super-call
            self.__messages = []

        def handle(self, record):
            self.acquire()
            if len(self.__messages) >= self.__max_queue_size:
                # Loose the initial log records
                self.__messages.pop(0)
            self.__messages.append(record)
            self.release()

        def sync_with_handlers(self, handlers=()):
            '''
            Sync the stored log records to the provided log handlers.
            '''
            if not handlers:
                return

            while self.__messages:
                record = self.__messages.pop(0)
                for handler in handlers:
                    if handler.level > record.levelno:
                        # If the handler's level is higher than the log record one,
                        # it should not handle the log record
                        continue
                    handler.handle(record)


# Import 3rd-party libs
import yaml

# ----- Setup Temporary Logging ------------------------------------------------------------------------------------->
# Store a reference to the temporary queue logging handler
LOGGING_TEMP_HANDLER = TemporaryLoggingHandler()
# Add the handler to python's logging system
logging.root.addHandler(LOGGING_TEMP_HANDLER)
# <---- Setup Temporary Logging --------------------------------------------------------------------------------------

log = logging.getLogger(__name__)

# ----- Global Variables -------------------------------------------------------------------------------------------->
CONF_DIR = os.path.join(os.path.abspath(os.path.dirname(__file__)), '_saltconf')
# Gentoo Portage prefers ebuild tests are rooted in ${TMPDIR}
SYS_TMP_DIR = os.environ.get('TMPDIR', tempfile.gettempdir())
TMP = os.path.join(SYS_TMP_DIR, 'salt-tests-tmpdir')
TMP_CONF_DIR = os.path.join(TMP, 'etc-salt')
XML_OUTPUT_DIR = os.environ.get('SALT_XML_TEST_REPORTS_DIR', os.path.join(TMP, 'xml-test-reports'))
TMP_STATE_TREE = os.path.join(SYS_TMP_DIR, 'salt-temp-state-tree')
TMP_PRODENV_STATE_TREE = os.path.join(SYS_TMP_DIR, 'salt-temp-prodenv-state-tree')
INTEGRATION_FILES = None  # late evaluation
# <---- Global Variables ---------------------------------------------------------------------------------------------


# ----- Helper Methods ---------------------------------------------------------------------------------------------->
def print_header(header, sep='~', top=True, bottom=True, inline=False, centered=False, width=SCREEN_COLS):
    '''
    Allows some pretty printing of headers on the console, either with a
    "ruler" on bottom and/or top, inline, centered, etc.
    '''
    if top and not inline:
        print(sep * width)

    if centered and not inline:
        fmt = u'{0:^{width}}'
    elif inline and not centered:
        fmt = u'{0:{sep}<{width}}'
    elif inline and centered:
        fmt = u'{0:{sep}^{width}}'
    else:
        fmt = u'{0}'
    print(fmt.format(header, sep=sep, width=width))

    if bottom and not inline:
        print(sep * width)


class RootsDict(dict):
    def merge(self, data):
        for key, values in data.iteritems():
            if key not in self:
                self[key] = values
                continue
            for value in values:
                if value not in self[key]:
                    self[key].append(value)
        return self

    def to_dict(self):
        return dict(self)


def recursive_copytree(source, destination, overwrite=False):
    for root, dirs, files in os.walk(source):
        for item in dirs:
            src_path = os.path.join(root, item)
            dst_path = os.path.join(destination, src_path.replace(source, '').lstrip(os.sep))
            if not os.path.exists(dst_path):
                log.debug('Creating directory: {0}'.format(dst_path))
                os.makedirs(dst_path)
        for item in files:
            src_path = os.path.join(root, item)
            dst_path = os.path.join(destination, src_path.replace(source, '').lstrip(os.sep))
            if os.path.exists(dst_path) and not overwrite:
                if os.stat(src_path).st_mtime > os.stat(dst_path).st_mtime:
                    log.debug('Copying {0} to {1}'.format(src_path, dst_path))
                    shutil.copy2(src_path, dst_path)
            else:
                if not os.path.isdir(os.path.dirname(dst_path)):
                    log.debug('Creating directory: {0}'.format(os.path.dirname(dst_path)))
                    os.makedirs(os.path.dirname(dst_path))
                log.debug('Copying {0} to {1}'.format(src_path, dst_path))
                shutil.copy2(src_path, dst_path)
# <---- Helper Methods -----------------------------------------------------------------------------------------------


# ----- Custom Argument Parser Actions ------------------------------------------------------------------------------>
class AppendToSearchPathAction(argparse._AppendAction):
    def __call__(self, parser, namespace, values, option_string=None):
        super(AppendToSearchPathAction, self).__call__(parser, namespace, values, option_string)
        parser.__search_paths__.append(os.path.abspath(values))


class ChangeDirectoryAction(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        workspace = os.path.abspath(values)
        os.chdir(workspace)
        setattr(namespace, self.dest, workspace)


class DestructiveTestsAction(argparse._StoreTrueAction):
    def __call__(self, parser, namespace, values, option_string=None):
        super(DestructiveTestsAction, self).__call__(parser, namespace, values, option_string)
        os.environ['DESTRUCTIVE_TESTS'] = 'YES'


class NoColorAction(argparse._StoreTrueAction):
    def __call__(self, parser, namespace, values, option_string=None):
        # Late import
        from salt.utils import get_colors

        super(NoColorAction, self).__call__(parser, namespace, values, option_string)
        parser.colors = get_colors(False)


class VerbosityAction(argparse._CountAction):
    def __call__(self, parser, namespace, value, option_string=None):
        super(VerbosityAction, self).__call__(parser, namespace, value, option_string)
        verbosity = getattr(namespace, 'verbosity', self.default)

        if verbosity <= 2:
            return

        if 'consolehandler' not in namespace and \
                not getattr(parser, '__console_logging_handler__', None):
            formatter = logging.Formatter(
                '%(asctime)s,%(msecs)03.0f [%(name)-5s:%(lineno)-4d]'
                '[%(levelname)-8s] %(message)s',
                datefmt='%H:%M:%S'
            )

            consolehandler = logging.StreamHandler(sys.stderr)
            consolehandler.setLevel(logging.INFO)       # -vv
            consolehandler.setFormatter(formatter)
            setattr(namespace, 'consolehandler', consolehandler)
            parser.__console_logging_handler__ = consolehandler
            if not hasattr(logging, 'TRACE'):
                logging.TRACE = 5
                logging.addLevelName(logging.TRACE, 'TRACE')
            if not hasattr(logging, 'GARBAGE'):
                logging.GARBAGE = 1
                logging.addLevelName(logging.GARBAGE, 'GARBAGE')

            logging.root.addHandler(consolehandler)
            logging.getLogger(__name__).info('Runtests logging has been setup')

        handled_levels = {
            3: logging.DEBUG,   # -vvv
            4: logging.TRACE,   # -vvvv
            5: logging.GARBAGE  # -vvvvv
        }
        if verbosity > 3:
            getattr(namespace, 'consolehandler',
                    getattr(parser, '__console_logging_handler__', None)).setLevel(
                handled_levels.get(
                    verbosity,
                    verbosity > 5 and 5 or 3
                )
            )


class SaltCheckoutPathAction(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        python_path = os.environ.get('PYTHONPATH', None)
        salt_checkout_path = os.path.abspath(values)
        if python_path is not None:
            python_path = '{0}:{1}'.format(
                salt_checkout_path, python_path
            )
        else:
            python_path = salt_checkout_path
        os.environ['PYTHONPATH'] = python_path
        setattr(namespace, self.dest, salt_checkout_path)
# <---- Custom Argument Parser Actions -------------------------------------------------------------------------------


class SaltRuntests(argparse.ArgumentParser):

    VERSION = version.__version__

    EPILOG = None

    DESCRIPTION = None

    def __init__(self,
                 prog=None,
                 usage=None,
                 description=None,
                 epilog=None,
                 parents=None,
                 formatter_class=argparse.HelpFormatter,
                 prefix_chars='-',
                 fromfile_prefix_chars=None,
                 argument_default=None,
                 conflict_handler='error',
                 add_help=True):
        super(SaltRuntests, self).__init__(prog=prog,
                                           usage=usage,
                                           description=description or self.DESCRIPTION,
                                           epilog=epilog or self.EPILOG,
                                           version=None,
                                           parents=parents or [],
                                           formatter_class=formatter_class,
                                           prefix_chars=prefix_chars,
                                           fromfile_prefix_chars=fromfile_prefix_chars,
                                           argument_default=argument_default,
                                           conflict_handler=conflict_handler,
                                           add_help=False)

        # Late import
        from salt.utils import get_colors

        self.colors = get_colors(True)
        # ----- Tests Suite Attributes ------------------------------------------------------------------------------>
        self.__testsuite__ = {}
        self.__testsuite_status__ = []
        self.__testsuite_results__ = []
        self.__testsuite_searched_paths__ = set()
        # <---- Tests Suite Attributes -------------------------------------------------------------------------------

        # ----- Let's not use argparse's help action ---------------------------------------------------------------->
        # We need some additional processing ( double parse_args() )
        self.help_action = self.add_argument(
            '-h', '--help',
            action='store_true',
            default=argparse.SUPPRESS,
            help='show this help message and exit'
        )
        # <---- Let's not use argparse's help action -----------------------------------------------------------------

        # ----- Add the versions argument --------------------------------------------------------------------------->
        self.add_argument(
            '--version',
            action='version',
            version='{0} {1}'.format(self.prog, self.VERSION),
            default=argparse.SUPPRESS,
            help='show program\'s version number and exit'
        )
        # <---- Add the versions argument ----------------------------------------------------------------------------

        # ----- Operational Options --------------------------------------------------------------------------------->
        self.operational_options_group = self.add_argument_group('Operational Options')
        self.operational_options_group.add_argument(
            '--workspace',
            default=os.getcwd(),
            action=ChangeDirectoryAction,
            help='Directory to change to before tests discovery and execution. Default: \'./\''
        )

        # Every path passed as --search-path <path-to-search> will be searched
        # for a __salttest__.py python module which will be imported and will
        # allow for extra and custom setup
        self.__search_paths__ = []
        self.operational_options_group.add_argument(
            '--search-path',
            action=AppendToSearchPathAction,
            default=self.__search_paths__,
            help='Path for tests preparation and discovery'
        )
        self.operational_options_group.add_argument(
            '--salt-checkout',
            action=SaltCheckoutPathAction,
            metavar='PATH_TO_SALT_CHECKOUT',
            help='Path to the salt checkout directory in case salt is not installed'
        )
        self.operational_options_group.add_argument(
            '--no-salt-daemons',
            action='store_true',
            help='Don\'t start the Salt testing daemons. Tests requiring them WILL fail'
        )
        # <---- Operational Options ----------------------------------------------------------------------------------

        # ----- Output Options -------------------------------------------------------------------------------------->
        self.output_options_group = self.add_argument_group('Output Options')
        self.output_options_group.add_argument(
            '-v',
            '--verbose',
            dest='verbosity',
            default=1,
            action=VerbosityAction,
            help='Verbose test runner output'
        )
        self.output_options_group.add_argument(
            '--output-columns',
            default=SCREEN_COLS,
            type=int,
            help='Number of maximum columns to use on the output. Default: %(default)s'
        )
        self.output_options_group.add_argument(
            '--tests-logfile',
            default=os.path.join(tempfile.gettempdir(), 'salt-runtests.log'),
            help='The path to the tests suite logging logfile. Default: %(default)r'
        )
        self.output_options_group.add_argument(
            '--sysinfo',
            default=False,
            action='store_true',
            help='Print some system information. Needs the salt daemons running.'
        )
        self.output_options_group.add_argument(
            '--no-colors',
            '--no-colours',
            action=NoColorAction,
            help='Disable colour printing.'
        )
        if HAS_XMLRUNNER:
            self.output_options_group.add_argument(
                '--xml-out',
                action='store_true',
                help='XML test runner output'
            )
            self.output_options_group.add_argument(
                '--xml-out-path',
                default=XML_OUTPUT_DIR,
                help='XML test runner output directory. Default: %(default)r'
            )
        self.output_options_group.add_argument(
            '--no-report',
            action='store_true',
            help='Do NOT show the overall tests result'
        )
        # <---- Output Options ---------------------------------------------------------------------------------------

        # ----- Files-system cleanup options ------------------------------------------------------------------------>
        self.fs_cleanup_options_group = self.add_argument_group('File-system cleanup Options')
        self.fs_cleanup_options_group.add_argument(
            '--no-clean',
            action='store_true',
            help=('Don\'t clean up test environment before and after the '
                  'tests suite execution (speed up test process)')
        )
        # <---- Files-system cleanup options -------------------------------------------------------------------------

        # ----- Tests Selection Group ------------------------------------------------------------------------------->
        self.test_selection_group = self.add_argument_group(
            'Tests Selection',
            'Select which tests are to be executed'
        )
        self.test_selection_group.add_argument(
            '--transport',
            default='zeromq',
            choices=('zeromq', 'raet'),
            help='Set to raet to run integration tests with raet transport. Default: %(default)s'
        )
        self.test_selection_group.add_argument(
            '--run-destructive',
            action=DestructiveTestsAction,
            help=('Run destructive tests. These tests can include adding '
                  'or removing users from your system for example. '
                  'Default: %(default)s')
        )
        self.test_selection_group.add_argument(
            '-n',
            '--name',
            action='append',
            help=('Specific test name to run. A named test is the module path '
                  'relative to the tests directory.')
        )
        # <---- Tests Selection Group --------------------------------------------------------------------------------

        # ----- Tests discovery search path ------------------------------------------------------------------------->
        # TestDaemon context manager extension attributes
        self.__ext_pillar__ = []
        self.__file_roots__ = RootsDict()
        self.__pillar_roots__ = RootsDict()
        self.__mockbin_paths__ = []
        self.__pre_test_daemon_enter__ = []
        self.__test_daemon_enter__ = []
        self.__test_daemon_exit__ = []
        self.__post_test_daemon_exit__ = []
        self.__extension_modules__ = []

        self.add_argument(
            'testfiles',
            nargs=argparse.REMAINDER,
            help='Test files to run tests from'
        )
        # <---- Tests discovery search path --------------------------------------------------------------------------

    def __load_metadata__(self, root, filename):
        log.info('Loading metadata from {0} under {1}'.format(filename, root))
        filename, _ = os.path.splitext(filename)
        try:
            fn_, path, desc = imp.find_module(filename, [root])
            mod = imp.load_module(filename, fn_, path, desc)
        except ImportError as exc:
            # Failed to import
            log.warning('Failed to import {0} from {1}: {2}'.format(filename, root, exc))
            return argparse.Namespace(
                needs_daemons=True,
                suffix_pattern='test_*.py',
            )

        # ----- Allow the discovered salt tests to tweak the parser ------------------------------------->
        setup_parser = getattr(mod, 'setup_parser', None)
        if setup_parser is not None:
            setup_parser(self)
        # <---- Allow the discovered salt tests to tweak the parser --------------------------------------

        # ----- Setup Daemons Directories --------------------------------------------------------------->
        self.__ext_pillar__.extend(getattr(mod, '__ext_pillar__', []))
        self.__mockbin_paths__.extend(getattr(mod, '__mockbin_paths__', []))

        for entry in ('__pre_test_daemon_enter__', '__test_daemon_enter__',
                      '__test_daemon_exit__', '__post_test_daemon_exit__'):
            entry_instance = getattr(mod, entry, None)
            if entry_instance is not None:
                if callable(entry_instance):
                    getattr(self, entry).append(entry_instance)
                else:
                    getattr(self, entry).extend(entry_instance)

        self.__file_roots__.merge(getattr(mod, '__file_roots__', {}))
        self.__pillar_roots__.merge(getattr(mod, '__pillar_roots__', {}))
        extension_modules = getattr(mod, '__extension_modules_path__', None)
        if extension_modules is not None:
            if isinstance(extension_modules, (list, tuple)):
                self.__extension_modules__.extend(list(extension_modules))
            else:
                self.__extension_modules__.append(extension_modules)
        # <---- Setup Daemons Directories ----------------------------------------------------------------

        # ----- Return defined metadata ----------------------------------------------------------------------------->
        metadata = argparse.Namespace(
            #display_name=getattr(mod, '__display_name__', u' '.join([
            #    part.capitalize() for part in os.path.basename(root).split('_')
            #])),
            suffix_pattern=getattr(mod, '__suffix_pattern__', 'test_*.py'),
            needs_daemons=getattr(mod, '__needs_daemons__', True),
            top_level_dir=getattr(mod, '__suite_root__', os.path.dirname(root))
        )
        log.info('Loaded metadata: {0}'.format(metadata))

        # Unload the __salttest__ module from memory
        if mod.__name__ in sys.modules:
            sys.modules.pop(mod.__name__)
            del mod
        return metadata
        # <---- Return defined metadata ------------------------------------------------------------------------------

    def __load_tests__(self, metadata, filename=None, start_dir=None):
        loader = TestLoader()
        if filename is not None:
            log.info('Loading tests from {0}. Meta: {1}'.format(filename, metadata))
            if start_dir is None:
                start_dir = os.path.dirname(filename)

            if start_dir.startswith(tuple(self.__testsuite_searched_paths__)):
                return

            discovered_tests = loader.discover(
                start_dir, pattern=os.path.basename(filename), top_level_dir=metadata.top_level_dir
            )
            if discovered_tests.countTestCases():
                log.info('Found {0} tests'.format(discovered_tests.countTestCases()))
                for test in self.__flatten_testsuite__(discovered_tests):
                    if 'ModuleImportFailure' in test.id():
                        self.__testsuite__[test._testMethodName] = (test, metadata.needs_daemons)
                        continue
                    self.__testsuite__[test.id()] = (test, metadata.needs_daemons)

            self.__testsuite_searched_paths__.add(start_dir)
            return

        try:
            if start_dir.startswith(tuple(self.__testsuite_searched_paths__)):
                return
            log.info('Loading tests from {0}  Meta: {1}'.format(start_dir, metadata))
            discovered_tests = loader.discover(
                start_dir, pattern=metadata.suffix_pattern, top_level_dir=metadata.top_level_dir
            )
            if discovered_tests.countTestCases():
                log.info('Found {0} tests'.format(discovered_tests.countTestCases()))
                for test in self.__flatten_testsuite__(discovered_tests):
                    if 'ModuleImportFailure' in test.id():
                        self.__testsuite__[test._testMethodName] = (test, metadata.needs_daemons)
                        continue
                    self.__testsuite__[test.id()] = (test, metadata.needs_daemons)
            if start_dir != self.options.workplace:
                self.__testsuite_searched_paths__.add(start_dir)
        except Exception as exc:
            log.debug('A failure occurred while discovering tests: {0}'.format(exc))

    def __flatten_testsuite__(self, tests):
        if hasattr(tests, '_tests'):
            for suite in tests._tests:
                for test in self.__flatten_testsuite__(suite):
                    yield test
        else:
            yield tests

    def __find_meta__(self, directory):
        log.info('Finding meta in {0}'.format(directory))
        for filename in fnmatch.filter(os.listdir(directory), '__salttest__.py*'):
            log.info('Found meta in {0}'.format(directory))
            return self.__load_metadata__(directory, filename)
        parent = os.path.dirname(directory)
        if self.options.workspace == directory:
            log.debug(
                'Reached originating CWD({0}), stop searching for meta in parent directories'.format(
                    self.options.workspace
                )
            )
            # Don't search parent directories above CWD
            return argparse.Namespace(
                needs_daemons=True,
                suffix_pattern='test_*.py',
                top_level_dir=directory
            )
        metadata = self.__find_meta__(parent)
        if 'top_level_dir' not in metadata:
            setattr(metadata, 'top_level_dir', directory)
        return metadata

    def __discover_salttests__(self, start_discovery_in=None):
        if start_discovery_in is None:
            start_discovery_in = os.getcwd()

        for root in [start_discovery_in] + self.__search_paths__:
            log.info('Searching for tests under {0}'.format(root))
            for top_level_dir, start_dirs, filenames in os.walk(root):
                if not fnmatch.filter(filenames, '*.py*'):
                    continue
                self.__load_tests__(self.__find_meta__(top_level_dir), start_dir=top_level_dir)

    def print_bulleted(self, message, color='LIGHT_BLUE'):
        print(' {0}*{ENDC} {1}'.format(self.colors[color], message, **self.colors))

    def parse_args(self, args=None, namespace=None):
        # We will ignore this parse_args result, we just need to trigger the
        # tests discovery with the additional search paths
        self.options = options = super(SaltRuntests, self).parse_args(args, namespace)

        # Let's now remove the bogus help handler added above and add the real
        # one just before parsing args again
        self._remove_action(self.help_action)
        self._option_string_actions.pop('--help')
        self._option_string_actions.pop('-h')

        if not options.testfiles:
            # Since we're not being passed test files, we can search for them
            self.__discover_salttests__()

        # Add the real help action argument
        self.add_argument(
            '-h', '--help',
            action='help',
            default=argparse.SUPPRESS,
            help='show this help message and exit'
        )

        # Parse ARGV again now that we have more of the required data, Yes,
        # it's not neat...
        self.options = super(SaltRuntests, self).parse_args(args, namespace)
        try:
            import salt
        except ImportError:
            self.error(
                'Salt is not importable. Please point --salt-checkout to the directory '
                'where the salt code resides'
            )

        global INTEGRATION_FILES  # pylint: disable=global-statement
        INTEGRATION_FILES = os.path.join(
            os.path.dirname(os.path.dirname(salt.__file__)), 'tests', 'integration', 'files'
        )
        if not os.path.isdir(INTEGRATION_FILES):
            self.error(
                'The calculated path to salt\'s testing integration files({0}) does not exist. '
                'This might be due to the fact that the salt module imported is a system-wide '
                'installation and not from a salt source code tree. Please point --salt-checkout '
                'to the directory where the salt code resides'
            )

        # ----- Setup File Logging ---------------------------------------------------------------------------------->
        log.info('Logging tests on {0}'.format(options.tests_logfile))
        print_header(u'', inline=True, width=getattr(options, 'output_columns', SCREEN_COLS))
        # Setup tests logging
        formatter = logging.Formatter(
            '%(asctime)s,%(msecs)03.0f [%(name)-5s:%(lineno)-4d]'
            '[%(levelname)-8s] %(message)s',
            datefmt='%H:%M:%S'
        )
        filehandler = logging.FileHandler(
            mode='w',   # Not preserved between re-runs
            filename=options.tests_logfile
        )
        filehandler.setLevel(logging.DEBUG)
        filehandler.setFormatter(formatter)
        logging.root.addHandler(filehandler)
        logging.root.setLevel(logging.DEBUG)

        global LOGGING_TEMP_HANDLER
        # Sync in memory log messages to the log file
        LOGGING_TEMP_HANDLER.sync_with_handlers((filehandler,))
        # Remove and reset the temporary logging handler
        logging.root.removeHandler(LOGGING_TEMP_HANDLER)
        LOGGING_TEMP_HANDLER = None
        # <---- Setup File Logging -----------------------------------------------------------------------------------

        # If we're passed filenames as arguments, then those are the tests
        # which are going to be loaded
        if options.testfiles:
            for testfile in options.testfiles:
                log.info('Processing {0}'.format(testfile))
                abs_testfile = os.path.abspath(testfile)
                if os.path.isdir(abs_testfile):
                    self.__discover_salttests__(abs_testfile)
                    continue
                start_dir = os.path.dirname(abs_testfile)
                self.__load_tests__(self.__find_meta__(start_dir), filename=abs_testfile, start_dir=start_dir)

        if self.__count_test_cases__() < 1:
            # No need to continue if no tests were discovered
            self.error('No tests were found')

        if os.getcwd() != options.workspace:
            # Freakin' GPG python lib and it's cwd changes and deletions
            os.chdir(options.workspace)

        self.print_bulleted('Logging tests on {0}'.format(options.tests_logfile))
        self.print_bulleted('Current Directory: {0}'.format(os.getcwd(), **self.colors))
        self.print_bulleted('Test suite is running under PID {0}'.format(os.getpid()))
        if os.getcwd() not in sys.path:
            sys.path.insert(0, os.getcwd())

        if any([os.path.isdir(path) for path in [TMP, TMP_CONF_DIR, TMP_PRODENV_STATE_TREE, TMP_STATE_TREE]]):
            self.print_bulleted('Cleaning up previous execution temporary directories')
            for path in [TMP, TMP_CONF_DIR, TMP_PRODENV_STATE_TREE, TMP_STATE_TREE]:
                if os.path.isdir(path):
                    shutil.rmtree(path)

        self.print_bulleted('Found {0} test cases'.format(self.__count_test_cases__()))
        self.__transplant_configs__()

        for func in self.__pre_test_daemon_enter__:
            func(self, start_daemons=self.__testsuite_needs_daemons_running__())

        print_header(u'', inline=True, width=self.options.output_columns)
        with TestDaemon(self, start_daemons=self.__testsuite_needs_daemons_running__()):
            self.run_collected_tests()
        if self.__testsuite_status__.count(False) > 0:
            self.finalize(1)
        self.finalize(0)

    def __count_test_cases__(self):
        return len(self.__testsuite__)

    def __testsuite_needs_daemons_running__(self):
        if self.options.no_salt_daemons:
            return False
        for test, needs_daemons in self.__testsuite__.itervalues():
            if needs_daemons:
                return True
        return False

    def __transplant_configs__(self):
        # Late import
        import salt.config

        if os.path.isdir(TMP_CONF_DIR):
            shutil.rmtree(TMP_CONF_DIR)
        os.makedirs(TMP_CONF_DIR)
        self.print_bulleted('Transplanting configuration files to {0!r}'.format(TMP_CONF_DIR))
        running_tests_user = pwd.getpwuid(os.getuid()).pw_name
        master_opts = salt.config._read_conf_file(os.path.join(CONF_DIR, 'master'))
        master_opts['user'] = running_tests_user

        minion_config_path = os.path.join(CONF_DIR, 'minion')
        minion_opts = salt.config._read_conf_file(minion_config_path)
        minion_opts['user'] = running_tests_user
        minion_opts['root_dir'] = master_opts['root_dir'] = os.path.join(TMP, 'master-minion-root')

        syndic_opts = salt.config._read_conf_file(os.path.join(CONF_DIR, 'syndic'))
        syndic_opts['user'] = running_tests_user

        sub_minion_opts = salt.config._read_conf_file(os.path.join(CONF_DIR, 'sub_minion'))
        sub_minion_opts['root_dir'] = os.path.join(TMP, 'sub-minion-root')
        sub_minion_opts['user'] = running_tests_user

        syndic_master_opts = salt.config._read_conf_file(os.path.join(CONF_DIR, 'syndic_master'))
        syndic_master_opts['user'] = running_tests_user
        syndic_master_opts['root_dir'] = os.path.join(TMP, 'syndic-master-root')

        if self.options.transport == 'raet':
            master_opts['transport'] = 'raet'
            master_opts['raet_port'] = 64506
            minion_opts['transport'] = 'raet'
            minion_opts['raet_port'] = 64510
            sub_minion_opts['transport'] = 'raet'
            sub_minion_opts['raet_port'] = 64520
            #syndic_master_opts['transport'] = 'raet'

        # Set up config options that require internal data
        master_opts['pillar_roots'] = self.__pillar_roots__.to_dict()
        master_opts['file_roots'] = self.__file_roots__.merge({
            'base': [
                # Let's support runtime created files that can be used like:
                #   salt://my-temp-file.txt
                TMP_STATE_TREE
            ],
            # Alternate root to test __env__ choices
            'prod': [
                TMP_PRODENV_STATE_TREE
            ]
        }).to_dict()
        master_opts['ext_pillar'].extend(self.__ext_pillar__)

        # Point the config values to the correct temporary paths
        for name in ('hosts', 'aliases'):
            optname = '{0}.file'.format(name)
            optname_path = os.path.join(TMP, name)
            master_opts[optname] = optname_path
            minion_opts[optname] = optname_path
            sub_minion_opts[optname] = optname_path

        # ----- Transcribe Configuration ---------------------------------------------------------------------------->
        for entry in os.listdir(CONF_DIR):
            if entry in ('master', 'minion', 'sub_minion', 'syndic_master'):
                # These have runtime computed values and will be handled
                # differently
                continue
            entry_path = os.path.join(CONF_DIR, entry)
            if os.path.isfile(entry_path):
                shutil.copy(
                    entry_path,
                    os.path.join(TMP_CONF_DIR, entry)
                )
            elif os.path.isdir(entry_path):
                shutil.copytree(
                    entry_path,
                    os.path.join(TMP_CONF_DIR, entry)
                )

        for entry in ('master', 'minion', 'sub_minion', 'syndic_master'):
            computed_config = deepcopy(locals()['{0}_opts'.format(entry)])
            open(os.path.join(TMP_CONF_DIR, entry), 'w').write(
                yaml.dump(computed_config, default_flow_style=False)
            )
        # <---- Transcribe Configuration -----------------------------------------------------------------------------

    def run_collected_tests(self):
        self.run_suite(
            TestSuite(
                sorted([test for (test, needs_daemon) in self.__testsuite__.values()],
                       key=lambda x: x.id())
            )
        )

    def run_suite(self, suite):
        '''
        Execute a unit test suite
        '''

        if HAS_XMLRUNNER and self.options.xml_out:
            runner = XMLTestRunner(
                stream=sys.stdout,
                output=self.options.xml_out_path,
                verbosity=self.options.verbosity
            )
        else:
            runner = TextTestRunner(
                stream=sys.stdout,
                verbosity=self.options.verbosity)
        results = runner.run(suite)
        self.__testsuite_results__.append(results)
        return results.wasSuccessful()

    def print_overall_testsuite_report(self):
        '''
        Print a nicely formatted report about the test suite results
        '''
        print
        print_header(
            u'  Overall Tests Report  ', sep=u'=', centered=True, inline=True,
            width=self.options.output_columns
        )

        failures = errors = skipped = passed = 0
        no_problems_found = True
        for results in self.__testsuite_results__:
            failures += len(results.failures)
            errors += len(results.errors)
            skipped += len(results.skipped)
            passed += results.testsRun - len(
                results.failures + results.errors + results.skipped
            )

            if not results.failures and not results.errors and not results.skipped:
                continue

            no_problems_found = False

            if results.skipped:
                print_header(
                    u' --------  Skipped Tests  ', sep='-', inline=True,
                    width=self.options.output_columns
                )
                maxlen = len(
                    max([testcase.id() for (testcase, reason) in
                         results.skipped], key=len)
                )
                fmt = u'   -> {0: <{maxlen}}  ->  {1}'
                for testcase, reason in results.skipped:
                    print(fmt.format(testcase.id(), reason, maxlen=maxlen))
                print_header(u' ', sep='-', inline=True,
                             width=self.options.output_columns)

            if results.errors:
                print_header(
                    u' --------  Tests with Errors  ', sep='-', inline=True,
                    width=self.options.output_columns
                )
                for testcase, reason in results.errors:
                    print_header(
                        u'   -> {0}  '.format(testcase.id()),
                        sep=u'.', inline=True,
                        width=self.options.output_columns
                    )
                    for line in reason.rstrip().splitlines():
                        print('       {0}'.format(line.rstrip()))
                    print_header(u'   ', sep=u'.', inline=True,
                                width=self.options.output_columns)
                print_header(u' ', sep='-', inline=True,
                             width=self.options.output_columns)

            if results.failures:
                print_header(
                    u' --------  Failed Tests  ', sep='-', inline=True,
                    width=self.options.output_columns
                )
                for testcase, reason in results.failures:
                    print_header(
                        u'   -> {0}  '.format(testcase.id()),
                        sep=u'.', inline=True,
                        width=self.options.output_columns
                    )
                    for line in reason.rstrip().splitlines():
                        print('       {0}'.format(line.rstrip()))
                    print_header(u'   ', sep=u'.', inline=True,
                                width=self.options.output_columns)
                print_header(u' ', sep='-', inline=True,
                             width=self.options.output_columns)

        if no_problems_found:
            print_header(
                u'***  No Problems Found While Running Tests  ',
                sep=u'*', inline=True, width=self.options.output_columns
            )

        print_header(u'', sep=u'=', inline=True,
                     width=self.options.output_columns)
        total = sum([passed, skipped, errors, failures])
        print(
            '{0} (total={1}, skipped={2}, passed={3}, failures={4}, '
            'errors={5}) '.format(
                (errors or failures) and 'FAILED' or 'OK',
                total, skipped, passed, failures, errors
            )
        )
        print_header(
            '  Overall Tests Report  ', sep='=', centered=True, inline=True,
            width=self.options.output_columns
        )
        return

    def finalize(self, exit_code=0):
        '''
        Run the finalization procedures. Show report, clean-up file-system, etc
        '''
        for func in self.__post_test_daemon_exit__:
            func(self, start_daemons=self.__testsuite_needs_daemons_running__())

        if self.options.no_report is False:
            self.print_overall_testsuite_report()
        log.info(
            'Test suite execution finalized with exit code: {0}'.format(
                exit_code
            )
        )
        self.exit(exit_code)


# ----- Salt Tests Daemons Context Manager -------------------------------------------------------------------------->
class TestDaemon(object):
    '''
    Set up the master and minion daemons, and run related cases
    '''
    MINIONS_CONNECT_TIMEOUT = MINIONS_SYNC_TIMEOUT = 120

    def __init__(self, parser, start_daemons=True):
        # Late import
        from salt.utils import get_colors
        self.parser = parser
        self.start_daemons = start_daemons
        self.colors = get_colors(self.parser.options.no_colors is False)

    def __enter__(self):
        try:
            return self.__real_enter__()
        except Exception as exc:
            log.error(
                'Failed to __enter__ the TestDaemon: {0}'.format(exc),
                exc_info=log.isEnabledFor(logging.DEBUG)
            )
            self.parser.error('Failed to start the TestDaemon: {0}'.format(exc))

    def __real_enter__(self):
        '''
        Start a master and minion
        '''
        # Late import
        import salt.config
        from salt.utils.verify import verify_env

        self.parser.print_bulleted('Setting up Salt daemons to execute tests')
        print_header(u'', inline=True, width=self.parser.options.output_columns)

        running_tests_user = pwd.getpwuid(os.getuid()).pw_name
        self.master_opts = salt.config.master_config(os.path.join(TMP_CONF_DIR, 'master'))
        minion_config_path = os.path.join(TMP_CONF_DIR, 'minion')
        self.minion_opts = salt.config.minion_config(minion_config_path)

        self.syndic_opts = salt.config.syndic_config(
            os.path.join(TMP_CONF_DIR, 'syndic'),
            minion_config_path
        )
        self.sub_minion_opts = salt.config.minion_config(os.path.join(TMP_CONF_DIR, 'sub_minion'))
        self.syndic_master_opts = salt.config.master_config(os.path.join(TMP_CONF_DIR, 'syndic_master'))

        verify_env_entries = [
            os.path.join(self.master_opts['pki_dir'], 'minions'),
            os.path.join(self.master_opts['pki_dir'], 'minions_pre'),
            os.path.join(self.master_opts['pki_dir'], 'minions_rejected'),
            os.path.join(self.syndic_master_opts['pki_dir'], 'minions'),
            os.path.join(self.syndic_master_opts['pki_dir'], 'minions_pre'),
            os.path.join(self.syndic_master_opts['pki_dir'], 'minions_rejected'),
            os.path.join(self.master_opts['pki_dir'], 'accepted'),
            os.path.join(self.master_opts['pki_dir'], 'rejected'),
            os.path.join(self.master_opts['pki_dir'], 'pending'),
            os.path.join(self.syndic_master_opts['pki_dir'], 'accepted'),
            os.path.join(self.syndic_master_opts['pki_dir'], 'rejected'),
            os.path.join(self.syndic_master_opts['pki_dir'], 'pending'),
            os.path.join(self.minion_opts['pki_dir'], 'accepted'),
            os.path.join(self.minion_opts['pki_dir'], 'rejected'),
            os.path.join(self.minion_opts['pki_dir'], 'pending'),
            os.path.join(self.sub_minion_opts['pki_dir'], 'accepted'),
            os.path.join(self.sub_minion_opts['pki_dir'], 'rejected'),
            os.path.join(self.sub_minion_opts['pki_dir'], 'pending'),
            os.path.dirname(self.master_opts['log_file']),
            self.master_opts['extension_modules'],
            self.syndic_opts['extension_modules'],
            self.syndic_master_opts['extension_modules'],
            self.minion_opts['extension_modules'],
            self.sub_minion_opts['extension_modules'],
            self.sub_minion_opts['pki_dir'],
            self.master_opts['sock_dir'],
            self.syndic_master_opts['sock_dir'],
            self.sub_minion_opts['sock_dir'],
            self.minion_opts['sock_dir'],
            TMP_STATE_TREE,
            TMP_PRODENV_STATE_TREE,
            TMP,
        ]

        if self.parser.options.transport == 'raet':
            verify_env_entries.extend([
                os.path.join(self.master_opts['cachedir'], 'raet'),
                os.path.join(self.minion_opts['cachedir'], 'raet'),
                os.path.join(self.sub_minion_opts['cachedir'], 'raet'),
            ])
        else:
            verify_env_entries.extend([
                os.path.join(self.master_opts['cachedir'], 'jobs'),
                os.path.join(self.syndic_master_opts['cachedir'], 'jobs'),
            ])

        verify_env(verify_env_entries, running_tests_user)

        # Copy any provided extension modules to the proper path
        for extension_modules_dest in set([self.master_opts['extension_modules'],
                                           self.syndic_opts['extension_modules'],
                                           self.syndic_master_opts['extension_modules'],
                                           self.minion_opts['extension_modules'],
                                           self.sub_minion_opts['extension_modules']]):
            for extension_module_source in set(self.parser.__extension_modules__):
                log.info(
                    'Copying extension_modules from {0} to {1}'.format(
                        extension_module_source, extension_modules_dest
                    )
                )
                recursive_copytree(extension_module_source, extension_modules_dest)

        # Set up PATH to mockbin
        self._enter_mockbin()

        if self.start_daemons:
            if self.parser.options.transport == 'raet':
                self.start_raet_daemons()
            else:
                self.start_zeromq_daemons()

            self.minion_targets = set(['minion', 'sub_minion'])
            self.pre_setup_minions()
            self.setup_minions()

        for func in self.parser.__test_daemon_enter__:
            func(self, start_daemons=self.start_daemons)

        #if self.parser.options.ssh:
        #    self.prep_ssh()

        if self.start_daemons and self.parser.options.sysinfo:
            try:
                print_header(
                    '~~~~~~~ Versions Report ', inline=True,
                    width=getattr(self.parser.options, 'output_columns', SCREEN_COLS)
                )
            except TypeError:
                print_header('~~~~~~~ Versions Report ', inline=True)

            # Late import
            import salt.version
            print('\n'.join(salt.version.versions_report()))

            try:
                print_header(
                    '~~~~~~~ Minion Grains Information ', inline=True,
                    width=getattr(self.parser.options, 'output_columns', SCREEN_COLS)
                )
            except TypeError:
                print_header('~~~~~~~ Minion Grains Information ', inline=True)

            grains = self.client.cmd('minion', 'grains.items')

            minion_opts = self.minion_opts.copy()
            minion_opts['color'] = self.parser.options.no_colors is False

            # Late import
            import salt.output
            salt.output.display_output(grains, 'grains', minion_opts)

        try:
            print_header(
                '=', sep='=', inline=True,
                width=getattr(self.parser.options, 'output_columns', SCREEN_COLS)
            )
        except TypeError:
            print_header('', sep='=', inline=True)

        try:
            return self
        finally:
            if self.start_daemons:
                self.post_setup_minions()

    def start_zeromq_daemons(self):
        # Late import Salt
        import salt.master
        import salt.minion

        master = salt.master.Master(self.master_opts)
        self.master_process = multiprocessing.Process(target=master.start)
        self.master_process.start()

        minion = salt.minion.Minion(self.minion_opts)
        self.minion_process = multiprocessing.Process(target=minion.tune_in)
        self.minion_process.start()

        sub_minion = salt.minion.Minion(self.sub_minion_opts)
        self.sub_minion_process = multiprocessing.Process(
            target=sub_minion.tune_in
        )
        self.sub_minion_process.start()

        smaster = salt.master.Master(self.syndic_master_opts)
        self.smaster_process = multiprocessing.Process(target=smaster.start)
        self.smaster_process.start()

        syndic = salt.minion.Syndic(self.syndic_opts)
        self.syndic_process = multiprocessing.Process(target=syndic.tune_in)
        self.syndic_process.start()

    def start_raet_daemons(self):
        import salt.daemons.flo
        master = salt.daemons.flo.IofloMaster(self.master_opts)
        self.master_process = multiprocessing.Process(target=master.start)
        self.master_process.start()

        minion = salt.daemons.flo.IofloMinion(self.minion_opts)
        self.minion_process = multiprocessing.Process(target=minion.tune_in)
        self.minion_process.start()

        sub_minion = salt.daemons.flo.IofloMinion(self.sub_minion_opts)
        self.sub_minion_process = multiprocessing.Process(
            target=sub_minion.tune_in
        )
        self.sub_minion_process.start()
        # Wait for the daemons to all spin up
        time.sleep(5)

        #smaster = salt.daemons.flo.IofloMaster(self.syndic_master_opts)
        #self.smaster_process = multiprocessing.Process(target=smaster.start)
        #self.smaster_process.start()

        # no raet syndic daemon yet

    def prep_ssh(self):
        '''
        Generate keys and start an ssh daemon on an alternate port
        '''
        '''
        keygen = salt.utils.which('ssh-keygen')
        sshd = salt.utils.which('sshd')

        if not (keygen and sshd):
            print('WARNING: Could not initialize SSH subsystem. Tests for salt-ssh may break!')
            return
        if not os.path.exists(TMP_CONF_DIR):
            os.makedirs(TMP_CONF_DIR)

        keygen_process = subprocess.Popen(
                [keygen, '-t', 'ecdsa', '-b', '521', '-C', '"$(whoami)@$(hostname)-$(date -I)"', '-f', 'key_test',
                 '-P', 'INSECURE_TEMPORARY_KEY_PASSWORD'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                close_fds=True,
                cwd=TMP_CONF_DIR
        )
        out, err = keygen_process.communicate()
        if err:
            print('ssh-keygen had errors: {0}'.format(err))
        sshd_config_path = os.path.join(FILES, 'files/ext-conf/sshd_config')
        shutil.copy(sshd_config_path, TMP_CONF_DIR)
        auth_key_file = os.path.join(TMP_CONF_DIR, 'key_test.pub')
        with open(os.path.join(TMP_CONF_DIR, 'sshd_config'), 'a') as ssh_config:
            ssh_config.write('AuthorizedKeysFile {0}\n'.format(auth_key_file))
        sshd_process = subprocess.Popen(
                [sshd, '-f', 'sshd_config'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                close_fds=True,
                cwd=TMP_CONF_DIR
        )
        shutil.copy(os.path.join(FILES, 'conf/roster'), TMP_CONF_DIR)
        '''

    @property
    def client(self):
        '''
        Return a local client which will be used for example to ping and sync
        the test minions.

        This client is defined as a class attribute because its creation needs
        to be deferred to a latter stage. If created it on `__enter__` like it
        previously was, it would not receive the master events.
        '''
        # Late import
        import salt.client
        return salt.client.LocalClient(mopts=self.master_opts)

    def __exit__(self, type, value, traceback):
        '''
        Kill the minion and master processes
        '''
        # Late import
        import salt.master

        if self.start_daemons:
            salt.master.clean_proc(self.sub_minion_process, wait_for_kill=50)
            self.sub_minion_process.join()
            salt.master.clean_proc(self.minion_process, wait_for_kill=50)
            self.minion_process.join()
            salt.master.clean_proc(self.master_process, wait_for_kill=50)
            self.master_process.join()

            if self.parser.options.transport == 'zeromq':
                salt.master.clean_proc(self.syndic_process, wait_for_kill=50)
                self.syndic_process.join()
                salt.master.clean_proc(self.smaster_process, wait_for_kill=50)
                self.smaster_process.join()

        self._exit_mockbin()
        for func in self.parser.__test_daemon_exit__:
            func(self, start_daemons=self.start_daemons)
        self._clean()

    def pre_setup_minions(self):
        '''
        Subclass this method for additional minion setups.
        '''

    def setup_minions(self):
        # Wait for minions to connect back
        wait_minion_connections = multiprocessing.Process(
            target=self.wait_for_minion_connections,
            args=(self.minion_targets, self.MINIONS_CONNECT_TIMEOUT)
        )
        wait_minion_connections.start()
        wait_minion_connections.join()
        wait_minion_connections.terminate()
        if wait_minion_connections.exitcode > 0:
            print(
                '\n {RED_BOLD}*{ENDC} ERROR: Minions failed to connect'.format(
                **self.colors
                )
            )
            return False

        del wait_minion_connections

        # Wait for minions to "sync_all"
        for target in [self.sync_minion_modules,
                       self.sync_minion_states]:
            sync_minions = multiprocessing.Process(
                target=target,
                args=(self.minion_targets, self.MINIONS_SYNC_TIMEOUT)
            )
            sync_minions.start()
            sync_minions.join()
            if sync_minions.exitcode > 0:
                return False
            sync_minions.terminate()
            del sync_minions

        return True

    def post_setup_minions(self):
        '''
        Subclass this method to execute code after the minions have been setup
        '''

    def _enter_mockbin(self):
        env_path = os.environ.get('PATH', '')
        path_items = env_path.split(os.pathsep)
        for path in self.parser.__mockbin_paths__:
            if path not in path_items:
                path_items.insert(0, path)
        os.environ['PATH'] = os.pathsep.join(path_items)

    def _exit_mockbin(self):
        env_path = os.environ.get('PATH', '')
        path_items = env_path.split(os.pathsep)
        for path in self.parser.__mockbin_paths__:
            try:
                path_items.remove(path)
            except ValueError:
                pass
        os.environ['PATH'] = os.pathsep.join(path_items)

    def _clean(self):
        '''
        Clean out the tmp files
        '''
        if self.parser.options.no_clean:
            return
        if os.path.isdir(self.sub_minion_opts['root_dir']):
            shutil.rmtree(self.sub_minion_opts['root_dir'])
        if os.path.isdir(self.master_opts['root_dir']):
            shutil.rmtree(self.master_opts['root_dir'])
        if os.path.isdir(self.syndic_master_opts['root_dir']):
            shutil.rmtree(self.syndic_master_opts['root_dir'])

        for dirname in (TMP, TMP_STATE_TREE, TMP_PRODENV_STATE_TREE):
            if os.path.isdir(dirname):
                shutil.rmtree(dirname)

    def wait_for_jid(self, targets, jid, timeout=120):
        time.sleep(1)  # Allow some time for minions to accept jobs
        now = datetime.now()
        expire = now + timedelta(seconds=timeout)
        job_finished = False
        while now <= expire:
            running = self.__client_job_running(targets, jid)
            sys.stdout.write(
                '\r{0}\r'.format(
                    ' ' * getattr(self.parser.options, 'output_columns', SCREEN_COLS)
                )
            )
            if not running and job_finished is False:
                # Let's not have false positives and wait one more seconds
                job_finished = True
            elif not running and job_finished is True:
                return True
            elif running and job_finished is True:
                job_finished = False

            if job_finished is False:
                sys.stdout.write(
                    '   * {YELLOW}[Quit in {0}]{ENDC} Waiting for {1}'.format(
                        '{0}'.format(expire - now).rsplit('.', 1)[0],
                        ', '.join(running),
                        **self.colors
                    )
                )
                sys.stdout.flush()
            time.sleep(1)
            now = datetime.now()
        else:  # pylint: disable=W0120
            sys.stdout.write(
                '\n {RED_BOLD}*{ENDC} ERROR: Failed to get information '
                'back\n'.format(**self.colors)
            )
            sys.stdout.flush()
        return False

    def __client_job_running(self, targets, jid):
        running = self.client.cmd(
            list(targets), 'saltutil.running', expr_form='list'
        )
        return [
            k for (k, v) in running.iteritems() if v and v[0]['jid'] == jid
        ]

    def wait_for_minion_connections(self, targets, timeout):
        sys.stdout.write(
            ' {LIGHT_BLUE}*{ENDC} Waiting at most {0} for minions({1}) to '
            'connect back\n'.format(
                (timeout > 60 and
                 timedelta(seconds=timeout) or
                 '{0} secs'.format(timeout)),
                ', '.join(targets),
                **self.colors
            )
        )
        sys.stdout.flush()
        expected_connections = set(targets)
        now = datetime.now()
        expire = now + timedelta(seconds=timeout)
        while now <= expire:
            sys.stdout.write(
                '\r{0}\r'.format(
                    ' ' * getattr(self.parser.options, 'output_columns', SCREEN_COLS)
                )
            )
            sys.stdout.write(
                ' * {YELLOW}[Quit in {0}]{ENDC} Waiting for {1}'.format(
                    '{0}'.format(expire - now).rsplit('.', 1)[0],
                    ', '.join(expected_connections),
                    **self.colors
                )
            )
            sys.stdout.flush()

            responses = self.client.cmd(
                list(expected_connections), 'test.ping', expr_form='list',
            )
            for target in responses:
                if target not in expected_connections:
                    # Someone(minion) else "listening"?
                    continue
                expected_connections.remove(target)
                sys.stdout.write(
                    '\r{0}\r'.format(
                        ' ' * getattr(self.parser.options, 'output_columns',
                                      SCREEN_COLS)
                    )
                )
                sys.stdout.write(
                    '   {LIGHT_GREEN}*{ENDC} {0} connected.\n'.format(
                        target, **self.colors
                    )
                )
                sys.stdout.flush()

            if not expected_connections:
                return

            time.sleep(1)
            now = datetime.now()
        else:  # pylint: disable=W0120
            print(
                '\n {RED_BOLD}*{ENDC} WARNING: Minions failed to connect '
                'back. Tests requiring them WILL fail'.format(**self.colors)
            )
            try:
                print_header(
                    '=', sep='=', inline=True,
                    width=getattr(self.parser.options, 'output_columns', SCREEN_COLS)

                )
            except TypeError:
                print_header('=', sep='=', inline=True)
            raise SystemExit()

    def sync_minion_modules_(self, modules_kind, targets, timeout=None):
        if not timeout:
            timeout = 120
        # Let's sync all connected minions
        print(
            ' {LIGHT_BLUE}*{ENDC} Syncing minion\'s {1} '
            '(saltutil.sync_{1})'.format(
                ', '.join(targets),
                modules_kind,
                **self.colors
            )
        )
        syncing = set(targets)
        jid_info = self.client.run_job(
            list(targets), 'saltutil.sync_{0}'.format(modules_kind),
            expr_form='list',
            timeout=9999999999999999,
        )

        if self.wait_for_jid(targets, jid_info['jid'], timeout) is False:
            print(
                ' {RED_BOLD}*{ENDC} WARNING: Minions failed to sync {0}. '
                'Tests requiring these {0} WILL fail'.format(
                    modules_kind, **self.colors)
            )
            raise SystemExit()

        # Late import
        import salt._compat

        while syncing:
            rdata = self.client.get_full_returns(jid_info['jid'], syncing, 1)
            if rdata:
                for name, output in rdata.iteritems():
                    if not output['ret']:
                        # Already synced!?
                        syncing.remove(name)
                        continue

                    if isinstance(output['ret'], salt._compat.string_types):
                        # An errors has occurred
                        print(
                            ' {RED_BOLD}*{ENDC} {0} Failed so sync {2}: '
                            '{1}'.format(
                                name, output['ret'],
                                modules_kind,
                                **self.colors)
                        )
                        return False

                    print(
                        '   {LIGHT_GREEN}*{ENDC} Synced {0} {2}: '
                        '{1}'.format(
                            name,
                            ', '.join(output['ret']),
                            modules_kind, **self.colors
                        )
                    )
                    # Synced!
                    try:
                        syncing.remove(name)
                    except KeyError:
                        print(
                            ' {RED_BOLD}*{ENDC} {0} already synced??? '
                            '{1}'.format(name, output, **self.colors)
                        )
        return True

    def sync_minion_states(self, targets, timeout=None):
        self.sync_minion_modules_('states', targets, timeout=timeout)

    def sync_minion_modules(self, targets, timeout=None):
        self.sync_minion_modules_('modules', targets, timeout=timeout)
# <---- Salt Tests Daemons Context Manager ---------------------------------------------------------------------------


class AdaptedConfigurationTestCaseMixIn(object):

    __slots__ = ()

    def get_config_dir(self):
        return TMP_CONF_DIR

    def get_config_file_path(self, filename):
        return os.path.join(TMP_CONF_DIR, filename)

    @property
    def master_opts(self):
        # Late import
        import salt.config

        warnings.warn(
            'Please stop using the \'master_opts\' attribute in \'{0}.{1}\' and instead '
            'import \'{2}.TMP_CONF_DIR\' and instantiate the master configuration like '
            '\'salt.config.master_config(os.path.join(TMP_CONF_DIR, "master"))\''.format(
                self.__class__.__module__,
                self.__class__.__name__,
                __name__
            ),
            DeprecationWarning,
        )
        return salt.config.master_config(
            self.get_config_file_path('master')
        )

    @property
    def minion_opts(self):
        '''
        Return the options used for the minion
        '''
        # Late import
        import salt.config

        warnings.warn(
            'Please stop using the \'minion_opts\' attribute in \'{0}.{1}\' and instead '
            'import \'{2}.TMP_CONF_DIR\' and instantiate the minion configuration like '
            '\'salt.config.minion_config(os.path.join(TMP_CONF_DIR, "minion"))\''.format(
                self.__class__.__module__,
                self.__class__.__name__,
                __name__
            ),
            DeprecationWarning,
        )
        return salt.config.minion_config(
            self.get_config_file_path('minion')
        )

    @property
    def sub_minion_opts(self):
        '''
        Return the options used for the sub-minion
        '''
        # Late import
        import salt.config

        warnings.warn(
            'Please stop using the \'sub_minion_opts\' attribute in \'{0}.{1}\' and instead '
            'import \'{2}.TMP_CONF_DIR\' and instantiate the sub-minion configuration like '
            '\'salt.config.minion_config(os.path.join(TMP_CONF_DIR, "sub_minion_opts"))\''.format(
                self.__class__.__module__,
                self.__class__.__name__,
                __name__
            ),
            DeprecationWarning,
        )
        return salt.config.minion_config(
            self.get_config_file_path('sub_minion')
        )


def main():
    '''
    Run it!
    '''
    SaltRuntests().parse_args()


if __name__ == '__main__':
    main()
