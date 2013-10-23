# -*- coding: utf-8 -*-
'''
    salttesting.helpers
    ~~~~~~~~~~~~~~~~~~~

    Unit testing helpers

    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`
    :copyright: © 2013 by the SaltStack Team, see AUTHORS for more details.
    :license: Apache 2.0, see LICENSE for more details.
'''

import os
import sys
import types
import socket
import inspect
import logging
import __builtin__
from functools import wraps

log = logging.getLogger(__name__)


def destructiveTest(func):
    @wraps(func)
    def wrap(cls):
        if os.environ.get('DESTRUCTIVE_TESTS', 'False').lower() == 'false':
            cls.skipTest('Destructive tests are disabled')
        return func(cls)
    return wrap


class RedirectStdStreams(object):
    '''
    Temporarily redirect system output to file like objects.
    Default is to redirect to `os.devnull`, which just mutes output, `stdout`
    and `stderr`.
    '''

    def __init__(self, stdout=None, stderr=None):
        if stdout is None:
            stdout = open(os.devnull, 'w')
        if stderr is None:
            stderr = open(os.devnull, 'w')

        self.__stdout = stdout
        self.__stderr = stderr
        self.__redirected = False

    def __enter__(self):
        self.redirect()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.unredirect()

    def redirect(self):
        self.old_stdout = sys.stdout
        self.old_stdout.flush()
        self.old_stderr = sys.stderr
        self.old_stderr.flush()
        sys.stdout = self.__stdout
        sys.stderr = self.__stderr
        self.__redirected = True

    def unredirect(self):
        if not self.__redirected:
            return
        try:
            self.__stdout.flush()
            self.__stdout.close()
        except ValueError:
            # already closed?
            pass
        try:
            self.__stderr.flush()
            self.__stderr.close()
        except ValueError:
            # already closed?
            pass

        sys.stdout = self.old_stdout
        sys.stderr = self.old_stderr

    def flush(self):
        if self.__redirected:
            try:
                self.__stdout.flush()
            except Exception:
                pass
            try:
                self.__stderr.flush()
            except Exception:
                pass


class TestsLoggingHandler(object):
    '''
    Simple logging handler which can be used to test if certain logging
    messages get emitted or not::

    ..code-block: python

        with TestsLoggingHandler() as handler:
            # (...)               Do what ever you wish here
            handler.messages    # here are the emitted log messages

    '''
    def __init__(self, level=0, format='%(levelname)s:%(message)s'):
        self.level = level
        self.format = format
        self.activated = False
        self.prev_logging_level = None

    def activate(self):
        class Handler(logging.Handler):
            def __init__(self, level):
                logging.Handler.__init__(self, level)
                self.messages = []

            def emit(self, record):
                self.messages.append(self.format(record))

        self.handler = Handler(self.level)
        formatter = logging.Formatter(self.format)
        self.handler.setFormatter(formatter)
        logging.root.addHandler(self.handler)
        self.activated = True
        # Make sure we're running with the lowest logging level with our
        # tests logging handler
        current_logging_level = logging.root.getEffectiveLevel()
        if current_logging_level > logging.DEBUG:
            self.prev_logging_level = current_logging_level
            logging.root.setLevel(0)

    def deactivate(self):
        if not self.activated:
            return
        logging.root.removeHandler(self.handler)
        # Restore previous logging level if changed
        if self.prev_logging_level is not None:
            logging.root.setLevel(self.prev_logging_level)

    @property
    def messages(self):
        if not self.activated:
            return []
        return self.handler.messages

    def clear(self):
        self.handler.messages = []

    def __enter__(self):
        self.activate()
        return self

    def __exit__(self, type, value, traceback):
        self.deactivate()
        self.activated = False

    # Mimic some handler attributes and methods
    @property
    def lock(self):
        if self.activated:
            return self.handler.lock

    def createLock(self):
        if self.activated:
            return self.handler.createLock()

    def acquire(self):
        if self.activated:
            return self.handler.acquire()

    def release(self):
        if self.activated:
            return self.handler.release()


def relative_import(import_name, relative_from='../'):
    '''
    Update sys.path to include `relative_from` before importing `import_name`
    '''
    try:
        return __import__(import_name)
    except ImportError:
        previous_frame = inspect.getframeinfo(inspect.currentframe().f_back)
        sys.path.insert(
            0, os.path.realpath(
                os.path.join(
                    os.path.abspath(
                        os.path.dirname(previous_frame.filename)
                    ),
                    relative_from
                )
            )
        )
    return __import__(import_name)


def ensure_in_syspath(*ensure_paths):
    '''
    Make sure that any path passed in `ensure_paths` exists in sys.path
    '''

    previous_frame = None

    for ensure_path in ensure_paths:
        if ensure_path in sys.path:
            # If it's already in sys.path, nothing to do
            continue

        # We reached here? Then ensure_path is not present in sys.path
        if os.path.isabs(ensure_path):
            # It's an absolute path? Then include it in sys.path
            sys.path.insert(0, ensure_path)
            continue

        # If we reached here, it means it's a relative path. Lets compute the
        # relation into a real path
        if previous_frame is None:
            previous_frame = inspect.getframeinfo(
                inspect.currentframe().f_back
            )

        realpath = os.path.realpath(
            os.path.join(
                os.path.abspath(
                    os.path.dirname(previous_frame.filename)
                ),
                ensure_path
            )
        )

        if not os.path.exists(realpath):
            # The path does not exist? Don't even inject it into sys.path
            continue

        if realpath in sys.path:
            # The path is already present in sys.path? Nothing else to do.
            continue

        # Inject the computed path into sys.path
        sys.path.insert(0, realpath)


class ForceImportErrorOn(object):
    '''
    This class is meant to be used in mock'ed test cases which require an
    ``ImportError`` to be raised.

    >>> import os.path
    >>> with ForceImportErrorOn('os.path'):
    ...     import os.path
    ...
    Traceback (most recent call last):
      File "<stdin>", line 2, in <module>
      File "salttesting/helpers.py", line 263, in __import__
        'Forced ImportError raised for {0!r}'.format(name)
    ImportError: Forced ImportError raised for 'os.path'
    >>>


    >>> with ForceImportErrorOn(('os', 'path')):
    ...     import os.path
    ...     sys.modules.pop('os', None)
    ...     from os import path
    ...
    <module 'os' from '/usr/lib/python2.7/os.pyc'>
    Traceback (most recent call last):
      File "<stdin>", line 4, in <module>
      File "salttesting/helpers.py", line 288, in __fake_import__
        name, ', '.join(fromlist)
    ImportError: Forced ImportError raised for 'from os import path'
    >>>


    >>> with ForceImportErrorOn(('os', 'path'), 'os.path'):
    ...     import os.path
    ...     sys.modules.pop('os', None)
    ...     from os import path
    ...
    Traceback (most recent call last):
      File "<stdin>", line 2, in <module>
      File "salttesting/helpers.py", line 281, in __fake_import__
        'Forced ImportError raised for {0!r}'.format(name)
    ImportError: Forced ImportError raised for 'os.path'
    >>>
    '''
    def __init__(self, *module_names):
        self.__module_names = {}
        for entry in module_names:
            if isinstance(entry, (list, tuple)):
                modname = entry[0]
                self.__module_names[modname] = set(entry[1:])
            else:
                self.__module_names[entry] = None

    def patch_import_function(self):
        self.__original_import = __builtin__.__import__
        __builtin__.__import__ = self.__fake_import__

    def restore_import_funtion(self):
        __builtin__.__import__ = self.__original_import

    def __fake_import__(self, name, globals_, locals_, fromlist, level=-1):
        if name in self.__module_names:
            importerror_fromlist = self.__module_names.get(name)
            if importerror_fromlist is None:
                raise ImportError(
                    'Forced ImportError raised for {0!r}'.format(name)
                )

            if importerror_fromlist.intersection(set(fromlist)):
                raise ImportError(
                    'Forced ImportError raised for {0!r}'.format(
                        'from {0} import {1}'.format(
                            name, ', '.join(fromlist)
                        )
                    )
                )

        return self.__original_import(name, globals_, locals_, fromlist, level)

    def __enter__(self):
        self.patch_import_function()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.restore_import_funtion()


class MockWraps(object):
    '''
    Helper class to be used with the mock library.
    To be used in the ``wraps`` keyword of ``Mock`` or ``MagicMock`` where you
    want to trigger a side effect for X times, and afterwards, call the
    original and un-mocked method.

    As an example:

    >>> def original():
    ...     print 'original'
    ...
    >>> def side_effect():
    ...     print 'side effect'
    ...
    >>> mw = MockWraps(original, 2, side_effect)
    >>> mw()
    side effect
    >>> mw()
    side effect
    >>> mw()
    original
    >>>

    '''
    def __init__(self, original, expected_failures, side_effect):
        self.__original = original
        self.__expected_failures = expected_failures
        self.__side_effect = side_effect
        self.__call_counter = 0

    def __call__(self, *args, **kwargs):
        try:
            if self.__call_counter < self.__expected_failures:
                if isinstance(self.__side_effect, types.FunctionType):
                    return self.__side_effect()
                raise self.__side_effect
            return self.__original(*args, **kwargs)
        finally:
            self.__call_counter += 1


def requires_network(only_local_network=False):
    '''
    Simple decorator which is supposed to skip a test case in case there's no
    network connection to the internet.
    '''
    def decorator(func):
        @wraps(func)
        def wrapper(cls):
            has_local_network = False
            # First lets try if we have a local network. Inspired in
            # verify_socket
            try:
                pubsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                retsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                pubsock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                pubsock.bind(('', 18000))
                pubsock.close()
                retsock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                retsock.bind(('', 18001))
                retsock.close()
                has_local_network = True
            except socket.error:
                # I wonder if we just have IPV6 support?
                try:
                    pubsock = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
                    retsock = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
                    pubsock.setsockopt(
                        socket.SOL_SOCKET, socket.SO_REUSEADDR, 1
                    )
                    pubsock.bind(('', 18000))
                    pubsock.close()
                    retsock.setsockopt(
                        socket.SOL_SOCKET, socket.SO_REUSEADDR, 1
                    )
                    retsock.bind(('', 18001))
                    retsock.close()
                    has_local_network = True
                except socket.error:
                    # Let's continue
                    pass

            if only_local_network is True:
                if has_local_network is False:
                    # Since we're only supposed to check local network, and no
                    # local network was detected, skip the test
                    cls.skipTest('No local network was detected')
                return func(cls)

            # We are using the google.com DNS records as numerical IPs to avoid
            # DNS lookups which could greatly slow down this check
            for addr in ('173.194.41.198', '173.194.41.199', '173.194.41.200',
                         '173.194.41.201', '173.194.41.206', '173.194.41.192',
                         '173.194.41.193', '173.194.41.194', '173.194.41.195',
                         '173.194.41.196', '173.194.41.197'):
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(0.25)
                    sock.connect((addr, 80))
                    sock.close()
                    # We connected? Stop the loop
                    break
                except socket.error:
                    # Let's check the next IP
                    continue
                else:
                    cls.skipTest('No internet network connection was detected')
            return func(cls)
        return wrapper
    return decorator


def with_system_account(username, on_existing='delete', delete=True):
    '''
    Create and optionally destroy a system account to be used within a test
    case. The system account is crated using the ``user`` salt module.

    The decorated testcase function must accept 'username' as an argument.

    :param username: The desired username for the system account.
    :param on_existing: What to do when the desired username is taken. The
    available options are:

        * nothing: Do nothing, act as if the account was created.
        * delete: delete and re-create the existing account
        * skip: skip the test case
    '''
    if on_existing not in ('nothing', 'delete', 'skip'):
        raise RuntimeError(
            'The value of \'on_existing\' can only be one of, '
            '\'nothing\', \'delete\' and \'skip\''
        )

    if not isinstance(delete, bool):
        raise RuntimeError(
            'The value of \'delete\' can only be \'True\' or \'False\''
        )

    def decorator(func):

        @wraps(func)
        def wrap(cls):

            # Let's add the account to the system.
            log.debug('Creating system account for {0!r}'.format(username))
            create_account = cls.run_function('user.add', [username])
            if not create_account:
                log.debug('Failed to create system account')
                # The account was not created
                if on_existing == 'skip':
                    cls.skipTest(
                        'Failed to create system account for {0!r}'.format(
                            username
                        )
                    )

                if on_existing == 'delete':
                    log.debug(
                        'Deleting the system account for {0!r}'.format(
                            username
                        )
                    )
                    delete_account = cls.run_function(
                        'user.delete', [username, True, True]
                    )
                    if not delete_account:
                        cls.skipTest(
                            'An account by the username {0!r} already '
                            'existed on the system and re-creating it was '
                            'not possible'.format(username)
                        )
                    log.debug(
                        'Second time creating system account for {0!r}'.format(
                            username
                        )
                    )
                    create_account = cls.run_function('user.add', [username])
                    if not create_account:
                        cls.skipTest(
                            'An account by the username {0!r} already '
                            'existed, was deleted as requested, but '
                            're-creating it was not possible'.format(username)
                        )

            failure = None
            try:
                try:
                    return func(cls, username)
                except Exception as exc:
                    log.exception(exc)
                    failure = exc
            finally:
                if delete:
                    delete_account = cls.run_function(
                        'user.delete', [username, True, True]
                    )
                    if not delete_account:
                        if failure is None:
                            log.warning(
                                'Although the actual test-case did not fail '
                                'deleting the created system account for '
                                '{0!r} afterwards did.'.format(username)
                            )
                        else:
                            log.warning(
                                'The test-case failed and also did the removal'
                                ' of the system account for {0!r}'.format(
                                    username
                                )
                            )
                if failure is not None:
                    # If an exception was thrown, raise it
                    raise failure
        return wrap
    return decorator


def requires_system_grains(func):
    '''
    Function decorator which loads and passes the system's grains to the test
    case.
    '''
    @wraps(func)
    def decorator(cls):
        if not hasattr(cls, 'run_function'):
            raise RuntimeError(
                '{0} does not have the \'run_function\' method which is '
                'necessary to collect the system grains'.format(
                    cls.__class__.__name__
                )
            )
        return func(cls, grains=cls.run_function('grains.items'))
    return decorator


def requires_salt_modules(*names):
    '''
    Makes sure the passed salt module is available. Skips the test if not

    .. versionadded:: 0.5.2
    '''
    def decorator(caller):

        if inspect.isclass(caller):

            # We're decorating a class
            old_init = caller.__init__

            def new_init(self, *args, **kwargs):
                old_init(self, *args, **kwargs)

                if not hasattr(self, 'run_function'):
                    raise RuntimeError(
                        '{0} does not have the \'run_function\' method which '
                        'is necessary to collect the loaded modules'.format(
                            self.__class__.__name__
                        )
                    )

                for name in names:
                    if name not in self.run_function('sys.doc'):
                        reason = '{0!r} is not available'.format(name)
                        for fname in dir(self):
                            if not fname.startswith('test_'):
                                continue
                            setattr(self, fname, lambda: self.skipTest(reason))
                        break
            caller.__init__ = new_init
            return caller

        # We're simply decorating functions
        @wraps(caller)
        def wrapper(cls):

            if not hasattr(cls, 'run_function'):
                raise RuntimeError(
                    '{0} does not have the \'run_function\' method which is '
                    'necessary to collect the loaded modules'.format(
                        cls.__class__.__name__
                    )
                )

            for name in names:
                if name not in cls.run_function('sys.doc'):
                    cls.skipTest('{0!r} is not available'.format(name))
                    break

            return caller(cls)
        return wrapper
    return decorator
