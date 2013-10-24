# -*- coding: utf-8 -*-
'''
    salttesting.case
    ~~~~~~~~~~~~~~~~

    Custom reusable ``unittest,case.TestCase`` implementations

    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`
    :copyright: © 2013 by the SaltStack Team, see AUTHORS for more details.
    :license: Apache 2.0, see LICENSE for more details.
'''

# Import python libs
import os
import sys
import signal
import subprocess
from datetime import datetime, timedelta

# Import salt testing libs
from salttesting.unit import TestCase


class ShellTestCase(TestCase):
    '''
    Execute a test for a shell command
    '''

    _code_dir_ = None
    _script_dir_ = None
    _python_executable_ = None

    def run_script(
            self,
            script,
            arg_str,
            catch_stderr=False,
            with_retcode=False,
            timeout=None):
        '''
        Execute a script with the given argument string
        '''
        script_path = os.path.join(self._script_dir_, script)
        if not os.path.isfile(script_path):
            return False

        python_path = 'PYTHONPATH={0}:{1}'.format(
            self._code_dir_, ':'.join(sys.path[1:])
        )
        cmd = '{0} {1} {2} {3}'.format(
            python_path, self._python_executable_, script_path, arg_str
        )

        popen_kwargs = {
            'shell': True,
            'stdout': subprocess.PIPE
        }

        if catch_stderr is True:
            popen_kwargs['stderr'] = subprocess.PIPE

        if not sys.platform.lower().startswith('win'):
            popen_kwargs['close_fds'] = True

            def detach_from_parent_group():
                # detach from parent group (no more inherited signals!)
                os.setpgrp()

            popen_kwargs['preexec_fn'] = detach_from_parent_group

        elif sys.platform.lower().startswith('win') and timeout is not None:
            raise RuntimeError('Timeout is not supported under windows')

        process = subprocess.Popen(cmd, **popen_kwargs)

        if timeout is not None:
            stop_at = datetime.now() + timedelta(seconds=timeout)
            term_sent = False
            while True:
                process.poll()

                if datetime.now() > stop_at:
                    if term_sent is False:
                        # Kill the process group since sending the term signal
                        # would only terminate the shell, not the command
                        # executed in the shell
                        os.killpg(os.getpgid(process.pid), signal.SIGINT)
                        term_sent = True
                        continue

                    try:
                        # As a last resort, kill the process group
                        os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                    except OSError as exc:
                        if exc.errno != 3:
                            raise

                    out = [
                        'Process took more than {0} seconds to complete. '
                        'Process Killed!'.format(timeout)
                    ]
                    if catch_stderr:
                        err = ['Process killed, unable to catch stderr output']
                        if with_retcode:
                            return out, err, process.returncode
                        else:
                            return out, err
                    if with_retcode:
                        return out, process.returncode
                    else:
                        return out

                if process.returncode is not None:
                    break

        if catch_stderr:
            if sys.version_info < (2, 7):
                # On python 2.6, the subprocess'es communicate() method uses
                # select which, is limited by the OS to 1024 file descriptors
                # We need more available descriptors to run the tests which
                # need the stderr output.
                # So instead of .communicate() we wait for the process to
                # finish, but, as the python docs state "This will deadlock
                # when using stdout=PIPE and/or stderr=PIPE and the child
                # process generates enough output to a pipe such that it
                # blocks waiting for the OS pipe buffer to accept more data.
                # Use communicate() to avoid that." <- a catch, catch situation
                #
                # Use this work around were it's needed only, python 2.6
                process.wait()
                out = process.stdout.read()
                err = process.stderr.read()
            else:
                out, err = process.communicate()
            # Force closing stderr/stdout to release file descriptors
            process.stdout.close()
            process.stderr.close()
            try:
                if with_retcode:
                    return out.splitlines(), err.splitlines(), process.returncode
                else:
                    return out.splitlines(), err.splitlines()
            finally:
                try:
                    process.terminate()
                except OSError as err:
                    # process already terminated
                    pass

        data = process.communicate()
        process.stdout.close()

        try:
            if with_retcode:
                return data[0].splitlines(), process.returncode
            else:
                return data[0].splitlines()
        finally:
            try:
                process.terminate()
            except OSError as err:
                # process already terminated
                pass
