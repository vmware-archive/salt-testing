# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`


    salttesting.jenkins
    ~~~~~~~~~~~~~~~~~~~

    Jenkins execution helper script
'''

# Import python libs
from __future__ import absolute_import, print_function
import os
import sys
import json
import time
import pipes
import random
import hashlib
import argparse

# Import salt libs
from salt.utils import get_colors, vt
from salt.version import SaltStackVersion
from salt.log.setup import SORTED_LEVEL_NAMES

# Import salt-testing libs
from salttesting.runtests import print_header, SCREEN_COLS

# Import 3rd-party libs
import yaml
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

SALT_GIT_URL = 'https://github.com/saltstack/salt.git'


# ----- Argparse Custom Actions ------------------------------------------------------------------------------------->
class GetPullRequestAction(argparse.Action):
    '''
    Load the required pull request information
    '''

    def __call__(self, parser, namespace, values, option_string=None):
        if HAS_REQUESTS is False:
            parser.error(
                'The python \'requests\' library needs to be installed'
            )

        headers = {}
        url = 'https://api.github.com/repos/saltstack/salt/pulls/{0}'.format(values)

        github_access_token_path = os.path.join(
            os.environ.get('JENKINS_HOME', os.path.expanduser('~')),
            '.github_token'
        )
        if os.path.isfile(github_access_token_path):
            headers = {
                'Authorization': 'token {0}'.format(
                    open(github_access_token_path).read().strip()
                )
            }

        http_req = requests.get(url, headers=headers)
        if http_req.status_code != 200:
            parser.error(
                'Unable to get the pull request: {0[message]}'.format(http_req.json())
            )

        pr_details = http_req.json()
        setattr(namespace, 'pull_request_git_url', pr_details['head']['repo']['clone_url'])
        setattr(namespace, 'pull_request_git_commit', pr_details['head']['sha'])
        setattr(namespace, 'pull_request_git_branch', pr_details['head']['ref'])
        setattr(namespace, 'pull_request_git_base_branch', pr_details['base']['ref'])

# <---- Argparse Custom Actions --------------------------------------------------------------------------------------


# ----- Helper Functions -------------------------------------------------------------------------------------------->
def print_bulleted(options, message, color='LIGHT_BLUE'):
    colors = get_colors(options.no_color is False)
    print(' {0}*{ENDC} {1}'.format(colors[color], message, **colors))
    sys.stdout.flush()


def save_state(options):
    '''
    Save some state data to be used between executions, minion external IP, minion states synced, etc...
    '''
    state_file = os.path.join(options.workspace, '.state.json')
    if os.path.isfile(state_file):
        try:
            state = json.load(open(os.path.join(options.workspace, '.state.json'), 'r'))
        except ValueError:
            state = {}
    else:
        state = {}

    for varname in ('workspace',
                    'require_sudo',
                    'output_columns',
                    'salt_minion_synced',
                    'minion_external_ip',
                    'minion_python_executable',
                    'salt_minion_bootstrapped'):
        if varname not in state and varname in options:
            state[varname] = getattr(options, varname)

    json.dump(state, open(state_file, 'w'))


def load_state(options):
    '''
    Load some state data to be used between executions, minion external IP, minion states synced, etc...
    '''
    state_file = os.path.join(options.workspace, '.state.json')
    allow_overwrite_variables = ('output_columns', 'workspace')
    if os.path.isfile(state_file):
        try:
            state = json.load(open(os.path.join(options.workspace, '.state.json'), 'r'))
        except ValueError:
            state = {}
    else:
        state = {}

    for key, value in state.iteritems():
        if key not in allow_overwrite_variables and key in options:
            continue
        setattr(options, key, value)


def generate_ssh_keypair(options):
    '''
    Generate a temporary SSH key, valid for one hour, and set it as an
    authorized key in the minion's root user account on the remote system.
    '''
    print_bulleted(options, 'Generating temporary SSH Key')
    sys.stdout.flush()
    ssh_key_path = os.path.join(options.workspace, 'jenkins_test_account_key')

    if os.path.exists(ssh_key_path):
        os.unlink(ssh_key_path)
        os.unlink(ssh_key_path + '.pub')

    exitcode = run_command(
        'ssh-keygen -b 2048 -C "$(whoami)@$(hostname)-$(date --rfc-3339=seconds)" '
        '-f {0} -N \'\' -V -10m:+2h'.format(ssh_key_path),
        options
    )
    if exitcode != 0:
        exitcode = run_command(
            'ssh-keygen -t rsa -b 2048 -C "$(whoami)@$(hostname)-$(date --rfc-3339=seconds)" '
            '-f {0} -N \'\' -V -10m:+2h'.format(ssh_key_path),
            options
        )
        if exitcode != 0:
            print_bulleted(options, 'Failed to generate temporary SSH ksys', 'RED')
            sys.stdout.flush()
            sys.exit(1)


def generate_vm_name(options):
    '''
    Generate a random enough vm name
    '''
    vm_name_prefix = os.environ.get('JENKINS_VM_NAME_PREFIX', 'Z')
    if 'BUILD_TAG' in os.environ:
        return '{0}{1}'.format(
            vm_name_prefix,
            os.environ.get('BUILD_TAG').replace(
                'jenkins', 'jk').replace(
                'salt-cloud', 'cloud').replace(
                'nightly', 'ntly').replace(
                'salt-', '').replace(
                'salt', 'slt').replace(
                'linode', 'lin').replace(
                '.', '_').replace(
                'branch_tests', '').replace(
                'branch-tests', '')
        )
    else:
        random_part = hashlib.md5(
            str(random.randint(1, 100000000))).hexdigest()[:6]

    return '{0}-{1}-{2}'.format(options.vm_prefix, (options.vm_source or 'UNKNOWN').split('_', 1)[-1], random_part)


def get_vm_name(options):
    '''
    Return the VM name
    '''
    return os.environ.get('JENKINS_VM_NAME', generate_vm_name(options))


def to_cli_yaml(data):
    '''
    Return a YAML string for CLI usage
    '''
    return yaml.dump(data, default_flow_style=True, indent=0, width=sys.maxint).rstrip()


def build_pillar_data(options, convert_to_yaml=True):
    '''
    Build a YAML formatted string to properly pass pillar data
    '''
    pillar = {
        'test_transport': options.test_transport,
        'with_coverage': options.test_without_coverage is False
    }
    if options.test_git_commit is not None:
        pillar['test_git_commit'] = pillar['repo_clone_rev'] = options.test_git_commit
    if options.test_git_url is not None:
        pillar['test_git_url'] = pillar['repo_clone_url'] = options.test_git_url
    if options.bootstrap_salt_url is not None:
        pillar['bootstrap_salt_url'] = options.bootstrap_salt_url
    if options.bootstrap_salt_commit is not None:
        pillar['bootstrap_salt_commit'] = options.bootstrap_salt_commit

    # Build package pillar data
    if options.package_source_dir:
        pillar['package_source_dir'] = options.package_source_dir
    if options.package_build_dir:
        pillar['package_build_dir'] = options.package_build_dir
    if options.package_artifact_dir:
        pillar['package_artifact_dir'] = options.package_artifact_dir

    if options.test_pillar:
        pillar.update(dict(options.test_pillar))

    if options.test_with_new_coverage:
        pillar['new_coverage'] = True

    if options.test_with_python3:
        pillar['py3'] = True

    if convert_to_yaml is True:
        return to_cli_yaml(pillar)
    return pillar


def echo_parseable_environment(options):
    '''
    Echo NAME=VAL parseable output
    '''
    output = [
        'JENKINS_VM_NAME={0}'.format(options.vm_name),
        'JENKINS_VM_SOURCE={0}'.format(options.vm_source),
    ]
    if 'pull_request_git_url' in options:
        output.append('SALT_PR_GIT_URL={0}'.format(options.pull_request_git_url))
    if 'pull_request_git_commit' in options:
        output.append('SALT_PR_GIT_COMMIT={0}'.format(options.pull_request_git_commit))
    if 'pull_request_git_branch' in options:
        output.append('SALT_PR_GIT_BRANCH={0}'.format(options.pull_request_git_branch))
    if 'pull_request_git_base_branch' in options:
        output.append('SALT_PR_GIT_BASE_BRANCH={0}'.format(options.pull_request_git_base_branch))

    sys.stdout.write('\n\n{0}\n\n'.format('\n'.join(output)))
    sys.stdout.flush()


def run_command(cmd, options, sleep=0.5, return_output=False, stream_stdout=True, stream_stderr=True):
    '''
    Run a command using VT
    '''
    print_header(u'', sep='>', inline=True, width=options.output_columns)
    if isinstance(cmd, list):
        cmd = ' '.join(cmd)

    print_bulleted(options, 'Running command: {0}'.format(cmd))
    print_header(u'', sep='-', inline=True, width=options.output_columns)
    sys.stdout.flush()

    if return_output is True:
        stdout_buffer = stderr_buffer = ''

    try:
        proc = vt.Terminal(
            cmd,
            shell=True,
            stream_stdout=stream_stdout,
            stream_stderr=stream_stderr
        )

        proc_terminated = False
        while True:
            stdout, stderr = proc.recv(4096)
            if return_output is True:
                stdout_buffer += stdout or ''
                stderr_buffer += stderr or ''

            if proc_terminated:
                break

            if not proc.isalive() and not stdout and not stderr:
                proc_terminated = True

            time.sleep(sleep)
        if proc.exitstatus != 0:
            print_header(u'', sep='-', inline=True, width=options.output_columns)
            print_bulleted(options, 'Failed execute command. Exit code: {0}'.format(proc.exitstatus), 'RED')
            sys.stdout.flush()
        else:
            print_header(u'', sep='-', inline=True, width=options.output_columns)
            print_bulleted(
                options, 'Command execution succeeded. Exit code: {0}'.format(proc.exitstatus), 'LIGHT_GREEN'
            )
            sys.stdout.flush()
        if return_output is True:
            return stdout_buffer, stderr_buffer, proc.exitstatus
        return proc.exitstatus
    except vt.TerminalException as exc:
        print_header(u'', sep='-', inline=True, width=options.output_columns)
        print_bulleted(options, '\n\nAn error occurred while running command:\n', 'RED')
        print(str(exc))
        sys.stdout.flush()
    finally:
        print_header(u'', sep='<', inline=True, width=options.output_columns)
        sys.stdout.flush()
        proc.close(terminate=True, kill=True)


def bootstrap_cloud_minion(options):
    '''
    Bootstrap a minion using salt-cloud
    '''
    script_args = ['-ZD']
    if options.no_color:
        script_args.append('-n')
    if options.pip_based:
        script_args.append('-P')
    if options.bootstrap_salt_url != SALT_GIT_URL:
        script_args.extend([
            '-g', options.bootstrap_salt_url
        ])
    script_args.extend(['git', options.bootstrap_salt_commit])

    cmd = [
        'salt-cloud',
        '-l', options.log_level,
        '--script-args="{0}"'.format(' '.join(script_args)),
        '-p', options.vm_source,
        options.vm_name
    ]
    if options.no_color:
        cmd.append('--no-color')

    exitcode = run_command(cmd, options)
    if exitcode == 0:
        setattr(options, 'salt_minion_bootstrapped', 'yes')
    return exitcode


def bootstrap_lxc_minion(options):
    '''
    Bootstrap a minion using salt-cloud
    '''

    print_bulleted(options, 'LXC support not implemented', 'RED')
    sys.stdout.flush()
    sys.exit(1)


def prepare_ssh_access(options):
    print_bulleted(options, 'Prepare SSH Access to Bootstrapped VM')
    sys.stdout.flush()
    generate_ssh_keypair(options)

    cmd = [
        'salt',
        '-l', options.log_level,
        '-t', '100',
        options.vm_name,
        'state.sls',
        options.ssh_prepare_state,
        'pillar="{0}"'.format(
            to_cli_yaml({
                'test_username': options.ssh_username,
                'test_pubkey': open(
                    os.path.join(options.workspace, 'jenkins_test_account_key.pub')
                ).read().strip()
            })
        )
    ]
    if options.no_color:
        cmd.append('--no-color')

    return run_command(cmd, options)


def sync_minion(options):
    if 'salt_minion_bootstrapped' not in options:
        print_bulleted(options, 'Minion not boostrapped. Not syncing minion.', 'RED')
        sys.exit(1)
    if 'salt_minion_synced' in options:
        return

    cmd = ['salt', '-t', '100', '-l', options.log_level]
    if options.no_color:
        cmd.append('--no-color')
    cmd.extend([
        options.vm_name,
        'saltutil.sync_all'
    ])
    exitcode = run_command(cmd, options)
    setattr(options, 'salt_minion_synced', 'yes')
    save_state(options)
    return exitcode


def get_minion_external_address(options):
    '''
    Get and store the remote minion external IP
    '''
    if 'salt_minion_bootstrapped' not in options:
        print_bulleted(options, 'Minion not boostrapped. Not grabbing external IP.', 'RED')
        sys.exit(1)
    if getattr(options, 'minion_external_ip', None):
        return options.minion_external_ip

    sync_minion(options)

    attempts = 1
    while attempts <= 3:
        print_bulleted(options, 'Fetching the external IP of the minion. Attempt {0}/3'.format(attempts))
        sys.stdout.flush()
        stdout_buffer = stderr_buffer = ''
        cmd = [
            'salt',
            '--out=json',
            '-l', options.log_level
        ]
        if options.no_color:
            cmd.append('--no-color')
        cmd.extend([
            options.vm_name,
            'grains.get', 'external_ip'
        ])
        stdout, stderr, exitcode = run_command(cmd,
                                               options,
                                               return_output=True,
                                               stream_stdout=False,
                                               stream_stderr=False)
        if exitcode != 0:
            if attempts == 3:
                print_bulleted(
                    options, 'Failed to get the minion external IP. Exit code: {0}'.format(exitcode), 'RED')
                sys.stdout.flush()
                sys.exit(exitcode)
            attempts += 1
            continue

        if not stdout.strip():
            if attempts == 3:
                print_bulleted(options, 'Failed to get the minion external IP(no output)', 'RED')
                sys.stdout.flush()
                sys.exit(1)
            attempts += 1
            continue

        try:
            external_ip_info = json.loads(stdout.strip())
            external_ip = external_ip_info[options.vm_name]
            setattr(options, 'minion_external_ip', external_ip)
            save_state(options)
            return external_ip
        except (ValueError, TypeError):
            print_bulleted(options, 'Failed to load any JSON from {0!r}'.format(stdout.strip()), 'RED')
            sys.stdout.flush()
            attempts += 1


def get_minion_python_executable(options):
    '''
    Get and store the remote minion python executable
    '''
    if 'salt_minion_bootstrapped' not in options:
        print_bulleted(options, 'Minion not boostrapped. Not grabbing remote python executable.', 'RED')
        sys.exit(1)
    if 'minion_python_executable' in options:
        return options.minion_python_executable

    sync_minion(options)

    cmd = [
        'salt',
        '--out=json',
        '-l', options.log_level
    ]
    if options.no_color:
        cmd.append('--no-color')
    cmd.extend([
        options.vm_name,
        'grains.get', 'pythonexecutable'
    ])
    stdout, stderr, exitcode = run_command(cmd,
                                           options,
                                           return_output=True,
                                           stream_stdout=False,
                                           stream_stderr=False)
    if exitcode != 0:
        print_bulleted(
            options, 'Failed to get the minion python executable. Exit code: {0}'.format(exitcode), 'RED'
        )
        sys.exit(exitcode)

    if not stdout.strip():
        print_bulleted(options, 'Failed to get the minion external IP(no output)', 'RED')
        sys.stdout.flush()
        sys.exit(1)

    try:
        python_executable = json.loads(stdout.strip())
        python_executable = python_executable[options.vm_name]
        if options.test_with_python3:
            python_executable = '/usr/bin/python3'
        setattr(options, 'minion_python_executable', python_executable)
        save_state(options)
        return python_executable
    except (ValueError, TypeError):
        print_bulleted(options, 'Failed to load any JSON from {0!r}'.format(stdout.strip()), 'RED')


def delete_cloud_vm(options):
    '''
    Delete a salt-cloud instance
    '''
    cmd = ['salt-cloud', '-l', options.log_level, '-yd']
    if options.no_color:
        cmd.append('--no-color')
    cmd.append(options.vm_name)
    return run_command(cmd, options)


def delete_lxc_vm(options):
    '''
    Delete an lxc instance
    '''
    cmd = ['salt-run']
    if options.no_color:
        cmd.append('--no-color')
    cmd.append('lxc.purge')
    cmd.append(options.vm_name)

    return run_command(cmd, options)


def check_bootstrapped_minion_version(options):
    '''
    Confirm that the bootstrapped minion version matches the desired one
    '''
    if 'salt_minion_bootstrapped' not in options:
        print_bulleted(options, 'Minion not boostrapped. Not grabbing minion version information.', 'RED')
        sys.exit(1)

    print_bulleted(options, 'Grabbing bootstrapped minion version information ... ')
    cmd = [
        'salt',
        '-t', '100',
        '--out=json',
        '-l', options.log_level
    ]
    if options.no_color:
        cmd.append('--no-color')
    cmd.extend([
        options.vm_name,
        'test.version'
    ])

    stdout, stderr, exitcode = run_command(cmd,
                                           options,
                                           return_output=True,
                                           stream_stdout=False,
                                           stream_stderr=False)
    if exitcode:
        print_bulleted(
            options, 'Failed to get the bootstrapped minion version. Exit code: {0}'.format(exitcode), 'RED'
        )
        sys.exit(exitcode)

    if not stdout.strip():
        print_bulleted(options, 'Failed to get the bootstrapped minion version(no output).', 'RED')
        sys.stdout.flush()
        sys.exit(1)

    try:
        version_info = json.loads(stdout.strip())
        bootstrap_minion_version = os.environ.get(
            'SALT_MINION_BOOTSTRAP_RELEASE',
            options.bootstrap_salt_commit[:7]
        )
        if bootstrap_minion_version.startswith('v'):
            bootstrap_minion_version = bootstrap_minion_version[1:]
        if bootstrap_minion_version not in version_info[options.vm_name]:
            print_bulleted(options, '\n\nATTENTION!!!!\n', 'YELLOW')
            print_bulleted(
                options,
                'The boostrapped minion version commit does not contain the desired commit:',
                'YELLOW'
            )
            print_bulleted(
                options,
                '{0!r} does not contain {1!r}'.format(version_info[options.vm_name], bootstrap_minion_version),
                'YELLOW'
            )
            print('\n\n')
            sys.stdout.flush()
        else:
            print_bulleted(options, 'Matches!', 'LIGHT_GREEN')
        setattr(options, 'bootstrapped_salt_minion_version', SaltStackVersion.parse(version_info[options.vm_name]))
    except (ValueError, TypeError):
        print_bulleted(options, 'Failed to load any JSON from {0!r}'.format(stdout.strip()), 'RED')


def run_state_on_vm(options, state_name, timeout=100):
    '''
    Run a state on the VM
    '''
    test_ssh_root_login(options)
    cmd = [
        'salt-call',
        '-l', options.log_level,
        '--retcode-passthrough'
    ]
    if options.bootstrapped_salt_minion_version >= (2015, 2):
        cmd.append('--timeout={0}'.format(timeout))
    if options.no_color:
        cmd.append('--no-color')
    cmd.extend([
        'state.sls',
        state_name,
        'pillar="{0}"'.format(build_pillar_data(options))
    ])
    if options.require_sudo:
        cmd.insert(0, 'sudo')
    if options.no_color:
        cmd.append('--no-color')

    return run_ssh_command(options, cmd)


def check_cloned_reposiory_commit(options):
    '''
    Confirm that the cloned repository commit matches the desired one
    '''
    print_bulleted(options, 'Grabbing the cloned repository commit information ...')
    cmd = [
        'salt',
        '-t', '100',
        '--out=json',
        '-l', options.log_level
    ]
    if options.no_color:
        cmd.append('--no-color')
    cmd.extend([
        options.vm_name,
        'git.revision',
        '/testing'
    ])

    stdout, stderr, exitcode = run_command(cmd,
                                           options,
                                           return_output=True,
                                           stream_stdout=False,
                                           stream_stderr=False)
    if exitcode:
        print_bulleted(
            options, 'Failed to get the cloned repository revision. Exit code: {0}'.format(exitcode), 'RED'
        )
        sys.exit(exitcode)

    if not stdout.strip():
        print_bulleted(options, 'Failed to get the cloned repository revision(no output).', 'RED')
        sys.stdout.flush()
        sys.exit(1)

    try:
        revision_info = json.loads(stdout.strip())
        if revision_info[options.vm_name][7:] != options.test_git_commit[7:]:
            print_bulleted(options, '\n\nATTENTION!!!!\n', 'YELLOW')
            print_bulleted(options, 'The cloned repository commit is not the desired one:', 'YELLOW')
            print_bulleted(
                options,
                ' {0!r} != {1!r}'.format(revision_info[options.vm_name][:7], options.test_git_commit[:7]),
                'YELLOW'
            )
            print('\n\n')
            sys.stdout.flush()
        else:
            print_bulleted(options, 'Matches!', 'LIGHT_GREEN')
    except (ValueError, TypeError):
        print_bulleted(options, 'Failed to load any JSON from {0!r}'.format(stdout.strip()), 'RED')


def build_ssh_opts(options):
    '''
    Return a list of SSH options
    '''
    ssh_args = [
        # Don't add new hosts to the host key database
        '-oStrictHostKeyChecking=no',
        # Set hosts key database path to /dev/null, ie, non-existing
        '-oUserKnownHostsFile=/dev/null',
        # Don't re-use the SSH connection. Less failures.
        '-oControlPath=none',
        # tell SSH to skip password authentication
        '-oPasswordAuthentication=no',
        '-oChallengeResponseAuthentication=no',
        # Make sure public key authentication is enabled
        '-oPubkeyAuthentication=yes',
        # No Keyboard interaction!
        '-oKbdInteractiveAuthentication=no',
        # Also, specify the location of the key file
        '-oIdentityFile={0}'.format(
            os.path.join(options.workspace, 'jenkins_test_account_key')
        )
    ]
    return ssh_args


def run_ssh_command(options, remote_command):
    '''
    Run a command using SSH
    '''
    test_ssh_root_login(options)
    cmd = ['ssh'] + build_ssh_opts(options)
    # Use double `-t` on the `ssh` command, it's necessary when `sudo` has
    # `requiretty` enforced.
    cmd.extend(['-t', '-t'])

    cmd.append(
        '{0}@{1}'.format(
            options.require_sudo and options.ssh_username or 'root',
            get_minion_external_address(options)
        )
    )
    if isinstance(remote_command, (list, tuple)):
        remote_command = ' '.join(remote_command)
    if options.require_sudo and not remote_command.startswith('sudo'):
        remote_command = 'sudo {0}'.format(remote_command)
    cmd.append(pipes.quote(remote_command))
    return run_command(cmd, options)


def test_ssh_root_login(options):
    '''
    Test if we're able to login as root
    '''
    if 'require_sudo' in options:
        return

    cmd = ['ssh'] + build_ssh_opts(options)
    cmd.extend([
        'root@{0}'.format(get_minion_external_address(options)),
        pipes.quote('echo "root login possible"')
    ])
    exitcode = run_command(cmd, options)
    setattr(options, 'require_sudo', exitcode != 0)
    save_state(options)


def download_artifacts(options):
    test_ssh_root_login(options)

    # Check if we're sudo'ing
    using_sudo = 'SUDO_USER' in os.environ
    sudo_uid = int(os.environ.get('SUDO_UID', os.getuid()))
    sudo_gid = int(os.environ.get('SUDO_GID', os.getgid()))

    sftp_command = ['sftp'] + build_ssh_opts(options)
    sftp_command.append(
        '{0}@{1}'.format(
            options.require_sudo and options.ssh_username or 'root',
            get_minion_external_address(options)
        )
    )
    for remote_path, local_path in options.download_artifact:
        if not os.path.isdir(local_path):
            os.makedirs(local_path)
        run_command(
            'echo "get -r {0} {1}" | {2}'.format(
                remote_path,
                local_path,
                ' '.join(sftp_command)
            ),
            options
        )

    if using_sudo:
        print_bulleted(options, 'Updating file permissions for the sudo\'ed account')
        for _, local_path in options.download_artifact:
            if os.path.isdir(local_path):
                for root, dirs, files in os.walk(local_path):
                    for dname in dirs:
                        os.chown(os.path.join(root, dname), sudo_uid, sudo_gid)
                    for fname in files:
                        os.chown(os.path.join(root, fname), sudo_uid, sudo_gid)
            else:
                os.chown(local_path, sudo_uid, sudo_gid)
# <---- Helper Functions ---------------------------------------------------------------------------------------------


# ----- Parser Code ------------------------------------------------------------------------------------------------->
def main():
    parser = argparse.ArgumentParser(description='Jenkins execution helper')
    parser.add_argument(
        '-w', '--workspace',
        default=os.path.abspath(os.environ.get('WORKSPACE', os.getcwd())),
        help=('Path to the execution workspace. Defaults to the \'WORKSPACE\' environment '
              'variable or the current directory.')
    )
    parser.add_argument(
        '-l', '--log-level',
        choices=list(SORTED_LEVEL_NAMES),
        default='info',
        help='Logging log level to pass to salt CLI tools.'
    )

    # Output Options
    output_group = parser.add_argument_group('Output Options')
    output_group.add_argument(
        '--output-columns',
        default=SCREEN_COLS,
        type=int,
        help='Number of maximum columns to use on the output. Default: %(default)s'
    )
    output_group.add_argument(
        '--no-color',
        '--no-colour',
        action='store_true',
        default=False,
        help='Don\'t use colors'
    )
    output_group.add_argument(
        '--echo-parseable-output',
        action='store_true',
        default=False,
        help='Print Jenkins related environment variables and exit'
    )
    output_group.add_argument(
        '--pull-request',
        type=int,
        action=GetPullRequestAction,
        default=None,
        help='Include the Pull Request information in parseable output'
    )

    # SSH Options
    ssh_options_group = parser.add_argument_group(
        'SSH Option(s)',
        'These SSH option(s) are used on all SSH related communications'
        '(except when initially bootstrapping the minion)'
    )
    ssh_options_group.add_argument(
        '--ssh-username',
        default='test-account',
        help='The username to use in all SSH related communications'
    )
    ssh_options_group.add_argument(
        '--ssh-prepare-state',
        default='accounts.test_account',
        help='The name of the state which prepares the remove VM for SSH access'
    )

    # Deployment Selection
    deployment_group = parser.add_argument_group('Deployment Selection')
    deployment_group_mutually_exclusive = deployment_group.add_mutually_exclusive_group()
    deployment_group_mutually_exclusive.add_argument(
        '--cloud-deploy',
        action='store_true',
        default=False,
        help='Salt Cloud Deployment. The default deployment.'
    )
    deployment_group_mutually_exclusive.add_argument(
        '--lxc-deploy',
        action='store_true',
        default=False,
        help='Salt LXC Deployment'
    )
    deployment_group.add_argument(
        '--pip-based',
        action='store_true',
        default=False,
        help='Allow pip based installations'
    )
    deployment_group.add_argument(
        '--lxc-host',
        default=None,
        help='The host where to deploy the LXC VM'
    )

    # Bootstrap Script Options
    bootstrap_script_options = parser.add_argument_group(
        'Bootstrap Script Options',
        'In case there\'s a need to provide the bootstrap script from an '
        'alternate URL and/or from a specific commit.'
    )
    bootstrap_script_options.add_argument(
        '--bootstrap-salt-url',
        default=None,
        help='The salt git repository url used to bootstrap a minion'
    )
    bootstrap_script_options.add_argument(
        '--bootstrap-salt-commit',
        default=None,
        help='The salt git commit used to bootstrap a minion'
    )

    # VM related options
    vm_options_group = parser.add_argument_group('VM Options')
    vm_options_group.add_argument('vm_name', nargs='?', help='Virtual machine name')
    vm_options_group.add_argument(
        '--vm-prefix',
        default=os.environ.get('JENKINS_VM_NAME_PREFIX', 'zjenkins'),
        help='The bootstrapped machine name prefix. Default: %(default)r'
    )
    vm_options_group.add_argument(
        '--vm-source',
        default=os.environ.get('JENKINS_VM_SOURCE', None),
        help=('The VM source. In case of --cloud-deploy usage, the could profile name. '
              'In case of --lxc-deploy usage, the image name.')
    )

    # VM related actions
    vm_actions = parser.add_argument_group(
        'VM Actions',
        'Action to execute on a running VM'
    )
    vm_actions.add_argument(
        '--delete-vm',
        action='store_true',
        default=False,
        help='Delete a running VM'
    )
    vm_actions.add_argument(
        '--download-artifact',
        default=[],
        nargs=2,
        action='append',
        metavar=('REMOTE_PATH', 'LOCAL_PATH'),
        help='Download remote artifacts.'
    )

    testing_source_options = parser.add_argument_group(
        'Testing Options',
        'In case there\'s a need to provide a different repository and/or commit from which '
        'the tests suite should be executed on'
    )
    testing_source_options.add_argument(
        '--test-transport',
        default='zeromq',
        choices=('zeromq', 'raet', 'tcp'),
        help=('Select which transport to run the integration tests with, '
              'zeromq, raet, or tcp. Default: %(default)s')
    )
    testing_source_options.add_argument(
        '--test-git-url',
        default=None,
        help='The testing git repository url')
    testing_source_options.add_argument(
        '--test-git-commit',
        default=None,
        help='The testing git commit to track')
    testing_source_options.add_argument(
        '--test-pillar',
        default=[],
        nargs=2,
        action='append',
        metavar=('PILLAR_KEY', 'PILLAR_VALUE'),
        help=('Additional pillar data use in the build. Pass a key and a value per '
              '\'--test-pillar\' option. Example: --test-pillar foo_key foo_value')
    )
    testing_source_options.add_argument(
        '--test-without-coverage',
        default=False,
        action='store_true',
        help='When running the tests default command, remove the coverage related flags.'
    )
    testing_source_options.add_argument(
        '--test-with-new-coverage',
        default=False,
        action='store_true',
        help='When running the tests default command, run coverage using a more inclusive approach.'
    )
    testing_source_options.add_argument(
        '--test-with-python3',
        default=False,
        action='store_true',
        help='Use python3 instead of python2 to run the test suite'
    )
    testing_source_options.add_argument(
        '--test-prep-sls',
        default=[],
        action='append',
        help='Run a preparation SLS file. Pass one SLS per `--test-prep-sls` option argument'
    )
    testing_source_options_mutually_exclusive = testing_source_options.add_mutually_exclusive_group()
    testing_source_options_mutually_exclusive.add_argument(
        '--test-command',
        default=None,
        help='The command to execute on the deployed VM to run tests'
    )
    testing_source_options_mutually_exclusive.add_argument(
        '--test-default-command',
        action='store_true',
        help=('Run the default salt runtests command: '
              '\'\{python_executable\} /testing/tests/runtests.py -v --run-destructive --sysinfo '
              '\{no_color\} --xml=/tmp/xml-unittests-output --coverage-xml=/tmp/coverage.xml '
              '--transport=\{transport\}\'')
    )

    packaging_options = parser.add_argument_group(
        'Packaging Options',
        'Remove build of packages options'
    )
    packaging_options.add_argument(
        '--build-packages',
        default=True,
        action='store_true',
        help='Run buildpackage.py to create packages off of the git build.'
    )
    # These next four options are ignored if --build-packages is False
    packaging_options.add_argument(
        '--build-packages-sls',
        default='buildpackage',
        help='The state to run for \'--build-packages\'. Default: %(default)s.'
    )
    packaging_options.add_argument(
        '--package-source-dir',
        default='/testing',
        help='Directory where the salt source code checkout is found '
             '(default: %(default)s)',
    )
    packaging_options.add_argument(
        '--package-build-dir',
        default='/tmp/salt-buildpackage',
        help='Build root for automated package builds (default: %(default)s)',
    )
    packaging_options.add_argument(
        '--package-artifact-dir',
        default='/tmp/salt-packages',
        help='Location on the minion from which packages should be '
             'retrieved (default: %(default)s)',
    )

    options = parser.parse_args()
    if options.echo_parseable_output and \
            os.path.exists(os.path.join(options.workspace, '.state.json')):
        # Since this is the first command to run, let's clear any saved state
        os.unlink(os.path.join(options.workspace, '.state.json'))
    load_state(options)

    if options.lxc_deploy or options.lxc_host:
        parser.error('LXC support is not yet implemented')

    if options.vm_name is None:
        options.vm_name = get_vm_name(options)

    if options.echo_parseable_output:
        if not options.vm_source:
            parser.error('--vm-source is required in order to print out the required Jenkins variables')
        echo_parseable_environment(options)
        save_state(options)
        parser.exit(0)

    if options.delete_vm:
        if options.cloud_deploy:
            parser.exit(delete_cloud_vm(options))
        elif options.lxc_deploy:
            parser.exit(delete_lxc_vm(options))
        else:
            parser.error(
                'You need to specify from which deployment to delete the VM from. --cloud-deploy/--lxc-deploy'
            )

    if options.bootstrap_salt_commit is None:
        options.bootstrap_salt_commit = os.environ.get(
            'SALT_MINION_BOOTSTRAP_RELEASE', 'develop'
        )

    if options.bootstrap_salt_url is None:
        options.bootstrap_salt_url = SALT_GIT_URL

    if options.cloud_deploy:
        exitcode = bootstrap_cloud_minion(options)
        if exitcode != 0:
            print_bulleted(options, 'Failed to bootstrap the cloud minion', 'RED')
            sys.stdout.flush()
            parser.exit(exitcode)
        print_bulleted(options, 'Sleeping for 5 seconds to allow the minion to breathe a little', 'YELLOW')
        sys.stdout.flush()
        time.sleep(5)
    elif options.lxc_deploy:
        exitcode = bootstrap_lxc_minion(options)
        if exitcode != 0:
            print_bulleted(options, 'Failed to bootstrap the LXC minion', 'RED')
            sys.stdout.flush()
            parser.exit(exitcode)
        print_bulleted(options, 'Sleeping for 5 seconds to allow the minion to breathe a little', 'YELLOW')
        sys.stdout.flush()
        time.sleep(5)

    if options.cloud_deploy or options.lxc_deploy:
        check_bootstrapped_minion_version(options)
        time.sleep(1)
        prepare_ssh_access(options)
        time.sleep(1)

    # Run preparation SLS
    for sls in options.test_prep_sls:
        exitcode = run_state_on_vm(options, sls, timeout=900)
        if exitcode != 0:
            print_bulleted(options, 'The execution of the {0!r} SLS failed'.format(sls), 'RED')
            sys.stdout.flush()
            parser.exit(exitcode)
        time.sleep(1)

    if options.test_git_commit is not None:
        check_cloned_reposiory_commit(options)

    # Run the main command using SSH for realtime output
    if options.test_default_command:
        # This is a pretty naive aproach to get the coverage binary path
        coverage_bin_path = get_minion_python_executable(options).replace('python', 'coverage')

        options.test_command = '{python_executable} '

        if options.test_without_coverage is False and options.test_with_new_coverage is True:
            options.test_command += (
                '{0} run --branch --concurrency=multiprocessing '
                '--parallel-mode '.format(coverage_bin_path)
            )

        options.test_command += (
            '/testing/tests/runtests.py -v --run-destructive --sysinfo'
            '{no_color} --xml=/tmp/xml-unittests-output --transport={transport} '
            '--output-columns={output_columns}'
        )

        pillar = build_pillar_data(options, convert_to_yaml=False)
        git_branch = pillar.get('git_branch', 'develop')
        if git_branch and git_branch not in('2014.1',):
            options.test_command += ' --ssh'
        if options.test_without_coverage is False and options.test_with_new_coverage is False:
            options.test_command += ' --coverage-xml=/tmp/coverage.xml'

    if options.test_command:
        def generate_xml_coverage_report(exit=True):
            if options.test_without_coverage is False and options.test_with_new_coverage is True:
                # Let's generate the new coverage report
                cmd = '{0} {1} combine; {0} {1} xml -o /tmp/coverage.xml'.format(
                    get_minion_python_executable(options),
                    coverage_bin_path
                )
                exitcode = run_ssh_command(options, cmd)
                if exitcode != 0:
                    print_bulleted(
                        options, 'The execution of the test command {0!r} failed'.format(cmd), 'RED'
                    )
                    sys.stdout.flush()
                    if exit is True:
                        parser.exit(exitcode)
                time.sleep(1)

        options.test_command = options.test_command.format(
            python_executable=get_minion_python_executable(options),
            no_color=options.no_color and ' --no-color' or '',
            transport=options.test_transport,
            output_columns=options.output_columns
        )
        exitcode = run_ssh_command(options, options.test_command)
        if exitcode != 0:
            print_bulleted(
                options, 'The execution of the test command {0!r} failed'.format(options.test_command), 'RED'
            )
            sys.stdout.flush()
            generate_xml_coverage_report(exit=False)
            parser.exit(exitcode)
        time.sleep(1)

        generate_xml_coverage_report(exit=False)

        # If we reached here it means the test command passed, let's build
        # packages if the option is passed
        if options.build_packages:
            run_state_on_vm(options, options.build_packages_sls)
            # Let's download the logs, even if building the packages fails
            logs_dir = os.path.join(options.workspace, 'logs')
            if not os.path.isdir(logs_dir):
                os.makedirs(logs_dir)
            options.download_artifact.append((
                os.path.join(options.package_artifact_dir, 'salt-buildpackage.log'),
                logs_dir
            ))
            packages_dir = os.path.join(options.workspace, 'artifacts', 'packages')
            if not os.path.isdir(packages_dir):
                os.makedirs(packages_dir)
            for fglob in ('salt-*.rpm', 'salt-*.deb', 'salt-*.pkg.xz'):
                options.download_artifact.append((
                    os.path.join(options.package_artifact_dir, fglob),
                    packages_dir
                ))
            time.sleep(1)

    if options.download_artifact:
        download_artifacts(options)
# <---- Parser Code --------------------------------------------------------------------------------------------------

if __name__ == '__main__':
    main()
