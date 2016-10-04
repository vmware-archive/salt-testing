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
import time
import random
import hashlib
import socket
import argparse

# Import salt libs
import salt.config
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
class GitHubAction(argparse.Action):
    '''
    Access salt git repository information from GitHub
    '''
    def get_github_data(self, url, parser, namespace, values, option_string=None):
        '''
        Retrieve information from GitHub
        '''
        if HAS_REQUESTS is False:
            parser.error(
                'The python \'requests\' library needs to be installed'
            )

        headers = {}

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
                'Unable to get the GitHub data: {0[message]}'.format(http_req.json())
            )

        return http_req.json()


class GetPullRequestAction(GitHubAction):
    '''
    Load the required pull request information
    '''
    def __call__(self, parser, namespace, values, option_string=None):
        url = 'https://api.github.com/repos/saltstack/salt/pulls/{0}'.format(values)
        pr_details = self.get_github_data(url, parser, namespace, values, option_string=option_string)

        setattr(namespace, 'pull_request_git_url', pr_details['head']['repo']['clone_url'])
        setattr(namespace, 'pull_request_git_commit', pr_details['head']['sha'])
        setattr(namespace, 'pull_request_git_branch', pr_details['head']['ref'])
        setattr(namespace, 'pull_request_git_base_branch', pr_details['base']['ref'])


class GetBranchAction(GitHubAction):
    '''
    Load the required branch information
    '''
    def __call__(self, parser, namespace, values, option_string=None):
        # Get a branch from a different GitHub account if requested
        if ':' in values:
            account, branch = values.split(':', 1)
        else:
            account, branch = 'saltstack', values
        url = 'https://api.github.com/repos/{0}/salt/branches/{1}'.format(account, branch)
        branch_details = self.get_github_data(url, parser, namespace, values, option_string=option_string)
        setattr(namespace, 'branch_git_commit', branch_details['commit']['sha'])
# <---- Argparse Custom Actions --------------------------------------------------------------------------------------


# ----- Helper Functions -------------------------------------------------------------------------------------------->
def print_flush(*args, **kwargs):
    print(*args, **kwargs)
    sys.stdout.flush()


def print_bulleted(options, message, color='LIGHT_BLUE'):
    colors = get_colors(options.no_color is False)
    print_flush(' {0}*{ENDC} {1}'.format(colors[color], message, **colors))


def save_state(options):
    '''
    Save some state data to be used between executions, minion IP address, minion states synced, etc...
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
                    'minion_ip_address',
                    'minion_python_executable',
                    'salt_minion_bootstrapped'):
        if varname not in state and varname in options:
            state[varname] = getattr(options, varname)

    json.dump(state, open(state_file, 'w'))


def load_state(options):
    '''
    Load some state data to be used between executions, minion IP address, minion states synced, etc...
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
    Generate a temporary SSH key, valid for two hours, and set it as an
    authorized key in the minion's root user account on the remote system.
    '''
    print_bulleted(options, 'Generating temporary SSH Key')
    ssh_key_path = os.path.join(options.workspace, 'jenkins_test_account_key')

    if os.path.exists(ssh_key_path):
        os.unlink(ssh_key_path)
        os.unlink(ssh_key_path + '.pub')

    exitcode = run_command(
        'ssh-keygen -b 2048 -C "$(whoami)@$(hostname)-$(date \"+%Y-%m-%dT%H:%M:%S%z\")" '
        '-f {0} -N \'\' -V -10m:+2h'.format(ssh_key_path),
        options
    )
    if exitcode != 0:
        exitcode = run_command(
            'ssh-keygen -t rsa -b 2048 -C "$(whoami)@$(hostname)-$(date \"+%Y-%m-%dT%H:%M:%S%z\")" '
            '-f {0} -N \'\' -V -10m:+2h'.format(ssh_key_path),
            options
        )
        if exitcode != 0:
            print_bulleted(options, 'Failed to generate temporary SSH ksys', 'RED')
            sys.exit(1)


def generate_vm_name(options):
    '''
    Generate a random enough vm name
    '''
    vm_name_prefix = os.environ.get('JENKINS_VM_NAME_PREFIX', 'Z')
    random_part = hashlib.md5(str(random.randint(1, 100000000))).hexdigest()[:6]

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
                'branch_tests-', '')
        )
    elif getattr(options, 'parallels_deploy', False):
        modified_source = options.vm_source.split('-template')[0]
    else:
        modified_source = (options.vm_source or 'UNKNOWN').split('_', 1)[-1]
    return '-'.join([options.vm_prefix, modified_source, random_part])


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
    if options['salttesting_version'] is not None:
        pillar['salttesting_version'] = options.salttesting_version

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
    # Standard environment
    output = [
        'JENKINS_VM_NAME={0}'.format(options.vm_name),
        'JENKINS_VM_SOURCE={0}'.format(options.vm_source),
    ]

    # VM environment
    if 'vm_host' in options:
        output.append('JENKINS_VM_HOST={0}'.format(options.vm_host))
    if 'vm_host_user' in options:
        output.append('JENKINS_VM_HOST_USER={0}'.format(options.vm_host_user))
    if 'vm_master' in options:
        output.append('JENKINS_VM_MASTER={0}'.format(options.vm_master))
    if 'vm_snapshot' in options:
        output.append('JENKINS_VM_SNAPSHOT={0}'.format(options.vm_snapshot))

    # Git environment
    if 'branch_git_commit' in options:
        output.append('SALT_BRANCH_GIT_COMMIT={0}'.format(options.branch_git_commit))
    if 'pull_request_git_url' in options:
        output.append('SALT_PR_GIT_URL={0}'.format(options.pull_request_git_url))
    if 'pull_request_git_commit' in options:
        output.append('SALT_PR_GIT_COMMIT={0}'.format(options.pull_request_git_commit))
    if 'pull_request_git_branch' in options:
        output.append('SALT_PR_GIT_BRANCH={0}'.format(options.pull_request_git_branch))
    if 'pull_request_git_base_branch' in options:
        output.append('SALT_PR_GIT_BASE_BRANCH={0}'.format(options.pull_request_git_base_branch))

    print_flush('\n\n{0}\n\n'.format('\n'.join(output)))


def run_interactive():
    print('Running interactive. Display some data here.')
    # Then register a handler for ctl-c and call the shutdown routine when heard.
    while True:
        print ('Still running interactive')
        time.sleep(10)


def run_command(cmd, options, sleep=0.5, return_output=False, stream_stdout=True, stream_stderr=True):
    '''
    Run a command using VT

    :param str cmd: Command to be run

    :param namespace options: Program options

    :param float sleep:  Sleep interval while polling process status

    :param bool return_output: If true, return ``(stdout, stderr, returncode)`` instead of ``returncode``

    :param bool stream_stdout: If true, stream ``stdout`` while process is running

    :param bool stream_stderr: If true, stream ``stderr`` while process is running
    '''
    print_header(u'', sep='>', inline=True, width=options.output_columns)
    if isinstance(cmd, list):
        cmd = ' '.join(cmd)

    print_bulleted(options, 'Running command: {0}'.format(cmd))
    print_header(u'', sep='-', inline=True, width=options.output_columns)

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
        else:
            print_header(u'', sep='-', inline=True, width=options.output_columns)
            print_bulleted(
                options, 'Command execution succeeded. Exit code: {0}'.format(proc.exitstatus), 'LIGHT_GREEN'
            )
        if return_output is True:
            return stdout_buffer, stderr_buffer, proc.exitstatus
        return proc.exitstatus
    except vt.TerminalException as exc:
        print_header(u'', sep='-', inline=True, width=options.output_columns)
        print_bulleted(options, '\n\nAn error occurred while running command:\n', 'RED')
        print_flush(str(exc))
    finally:
        print_header(u'', sep='<', inline=True, width=options.output_columns)
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
    if options.insecure:
        script_args.append('-I')
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
        '--out=yaml',
        '--no-color',
        options.vm_name
    ]
    if options.no_color:
        cmd.append('--no-color')
    cloud_stdout, _, exitcode = run_command(cmd, options, return_output=True)
    if exitcode == 0:
        setattr(options, 'salt_minion_bootstrapped', 'yes')
        # Strip off the header
        clean_stdout = '\n'.join(cloud_stdout.split('\n')[2:])
        try:
            print('IP', yaml.load(clean_stdout)['public_ips'][0].split()[0].encode())
            setattr(options, 'minion_ip_address', yaml.load(clean_stdout)['public_ips'][0].split()[0].encode())
        except Exception as exc:
            print('Exception encountered when processing bootstrap return for display: {0}'.format(exc))
    return exitcode


def bootstrap_lxc_minion(options):
    '''
    Bootstrap a minion using salt-cloud
    '''
    print_bulleted(options, 'LXC support not implemented', 'RED')
    sys.exit(1)


def bootstrap_parallels_minion(options):
    '''
    Bootstrap a parallels minion
    '''
    def _prl_cmd(sub_cmd, *args, **kwargs):
        '''
        Construct a parallels desktop execution module command for which the
        parallels host and parallels VM are hardcoded to the options given upon
        invocation of this script file.

        The resulting salt command will have the following form:

        .. code-block::

            salt -l info prl-host parallels.status macvm runas=macdev
        '''
        # Base command
        cmd = ['salt', '-l', options.log_level]
        if options.no_color:
            cmd.append('--no-color')
        cmd.extend(['--timeout', '32'])

        # parallels host, command, vm_name
        cmd.extend([
            options.vm_host,
            'parallels.{0}'.format(sub_cmd),
        ])

        # args and kwargs unique to sub_cmd
        cmd.extend([arg for arg in args])
        cmd.extend(['{0}={1}'.format(k, v) for k, v in kwargs.items()])

        # user on parallels host
        cmd.append('runas={0}'.format(options.vm_host_user))

        return cmd

    def _repeat(command, key, tries=19, sleep=7):
        '''
        Poll the state of a VM and wait until the desired change has been made
        before returning.

        Some parallels actions take a long time and prlctl returns before the
        action completes under cmd.run even when this doesn't necessarily
        happen when running prlctl in a login shell.  The job does return the
        output when it has completed, though long after salt has stopped
        waiting for the minion to return.

        :param str command: The poll command to execute

        :param str key: Substring to be found in the command std_out, which
            indicates the desired successful change in the state of the VM

        :param int tries: Number of tries to attempt

        :param int sleep: Amount of time to wait between each try
        '''
        for i in range(tries):
            std_out = run_command(command, options, return_output=True)[0]
            if key in std_out:
                return 0
            print_bulleted(options, 'Waiting {0}s for parallels to complete action on VM '
                                    '(try {2} of {1})'.format(sleep, tries, i + 1), 'YELLOW')
            time.sleep(sleep)

        return 1

    def vm_cloned():
        '''
        Clone a new VM from a snapshot in the stopped state of the template VM

        .. note::

            'template' here does not mean a parallels template because the
            'template' VMs need to be periodically started, updated, and
            resnapshotted, so it is easier and simpler to work directly with
            normal VMs as template VMs cannot be booted.

        .. note::

            When updating the template VM snapshots, ensure that the snapshot
            is made after the template VM has shutdown so that jenkins doesn't
            have to wait to for it to shutdown on every test run.
        '''
        # Ensure source VM is reverted to the desired snapshot before cloning
        run_command(_prl_cmd('revert_snapshot', options.vm_source, options.vm_snapshot), options)
        # Get source VM state
        source_state = run_command(_prl_cmd('status', options.vm_source),
                                            options,
                                            return_output=True)[0]

        # Ensure source VM is stopped since running VMs cannot be cloned
        if 'running' in source_state:
            run_command(_prl_cmd('stop', options.vm_source), options)
            # Wait until template VM is in stopped state
            if _repeat(_prl_cmd('status', options.vm_source), 'stopped') != 0:
                return 1

        # Clone source VM
        run_command(_prl_cmd('clone', options.vm_source, options.vm_name, linked=True), options)
        # Wait for prlctl to clone VM
        if _repeat(_prl_cmd('exists', options.vm_name), 'True') != 0:
            return 1

        return 0

    def vm_started():
        '''
        Ensure VM is started
        '''
        stat_cmd = _prl_cmd('status', options.vm_name)
        stat_out, stat_err, stat_retcode = run_command(stat_cmd, options, return_output=True)
        if 'stopped' in stat_out:
            run_command(_prl_cmd('start', options.vm_name), options)
            # Wait for prlctl to start VM
            if _repeat(_prl_cmd('status', options.vm_name), 'running') != 0:
                return 1
            return 0
        else:
            return stat_retcode

    def bootstrap_salt():
        '''
        Ensure that the salt package is installed
        '''
        # TODO: This function needs to be refactored into bootstrap for MacOS

        pkg_name = 'salt-{0}-x86_64.pkg'.format(options.bootstrap_salt_commit.lstrip('v'))

        # Wait for network to finish configuring (and VM to finish starting)
        ping_cmd = 'ping -c 3 repo.saltstack.com'
        ping_wrap = _prl_cmd('exec', options.vm_name, command=pipes.quote(ping_cmd))
        if _repeat(ping_wrap, '3 packets received') != 0:
            return 1

        # Download package hash
        downl_hash_cmd = 'curl https://repo.saltstack.com/osx/{0}.md5 > /tmp/{0}.md5'.format(pkg_name)
        downl_hash_wrap = _prl_cmd('exec', options.vm_name, command=pipes.quote(downl_hash_cmd))
        downl_hash_retcode = run_command(downl_hash_wrap, options)
        if downl_hash_retcode != 0:
            return downl_hash_retcode

        # Download package
        downl_cmd = 'curl https://repo.saltstack.com/osx/{0} > /tmp/{0}'.format(pkg_name)
        downl_wrap = _prl_cmd('exec', options.vm_name, command=pipes.quote(downl_cmd))
        run_command(downl_wrap, options)
        # Wait for package to finish downloading by first downloading the hash
        hash_cmd = 'cat /tmp/{0}.md5'.format(pkg_name)
        hash_wrap = _prl_cmd('exec', options.vm_name, command=pipes.quote(hash_cmd))
        hash_code = run_command(hash_wrap, options, return_output=True)[0]
        # And then comparing it to the actual hash
        get_hash_cmd = 'md5 -q /tmp/{0}'.format(pkg_name)
        get_hash_wrap = _prl_cmd('exec', options.vm_name, command=pipes.quote(get_hash_cmd))
        if _repeat(get_hash_wrap, hash_code) != 0:
            return 1
        else:
            print_bulleted(options, 'Matches!', 'LIGHT_GREEN')

        # Install package
        inst_cmd = 'installer -pkg /tmp/{0} -target / ; exit 0'.format(pkg_name)
        inst_wrap = _prl_cmd('exec', options.vm_name, command=pipes.quote(inst_cmd))
        inst_retcode = run_command(inst_wrap, options)
        if inst_retcode != 0:
            return inst_retcode

        # Install psutil until it becomes an official dep of the package; also
        # source salt envs since the environment setup by ``parallels exec`` is
        # very limited and does not source standard profiles
        psutil_cmd = 'source /etc/profile ; pip install psutil'
        psutil_wrap = _prl_cmd('exec', options.vm_name, command=pipes.quote(psutil_cmd))
        psutil_retcode = run_command(psutil_wrap, options)
        if psutil_retcode != 0:
            return psutil_retcode

        # Configure salt minion
        for config_str in ('echo id: {0} > /etc/salt/minion'.format(options.vm_name),
                           'echo master: {0} >> /etc/salt/minion'.format(options.vm_master)):
            config_cmd = _prl_cmd('exec', options.vm_name, command=pipes.quote(config_str))
            config_retcode = run_command(config_cmd, options)
            if config_retcode != 0:
                return config_retcode

        return 0

    def minion_reloaded():
        '''
        Stop if necessary and start salt-minion service
        '''
        # Get list of running daemons
        list_cmd = _prl_cmd('exec', options.vm_name, command=pipes.quote('launchctl list'))
        list_out, list_err, list_retcode = run_command(list_cmd, options, return_output=True, stream_stdout=False)
        if list_retcode != 0:
            return list_retcode

        # Unload salt-minion if it is running
        if 'com.saltstack.salt.minion' in list_out:
            lctl_unload = 'launchctl unload /Library/LaunchDaemons/com.saltstack.salt.minion.plist'
            unload_cmd = _prl_cmd('exec', options.vm_name, command=pipes.quote(lctl_unload))
            unload_retcode = run_command(unload_cmd, options)
            if unload_retcode != 0:
                return unload_retcode

        # Load salt-minion
        lctl_load = 'launchctl load /Library/LaunchDaemons/com.saltstack.salt.minion.plist'
        list_cmd = _prl_cmd('exec', options.vm_name, command=pipes.quote(lctl_load))
        return run_command(list_cmd, options)

    def accept_key():
        '''
        Accept minion key
        '''
        # Wait for key to be generated and sent to master
        if _repeat(['salt-key', '--list', 'unaccepted'], options.vm_name, tries=10, sleep=5) != 0:
            return 1
        return run_command(['salt-key', '-ya', options.vm_name], options)

    for fcn in (vm_cloned, vm_started, bootstrap_salt, minion_reloaded, accept_key):
        exitcode = fcn()
        if exitcode != 0:
            return exitcode

    setattr(options, 'salt_minion_bootstrapped', 'yes')
    return 0


def prepare_ssh_access(options):
    print_bulleted(options, 'Prepare SSH Access to Bootstrapped VM')
    generate_ssh_keypair(options)

    if options.test_interactive:

        cloud_config = salt.config.cloud_config('/etc/salt/cloud')  # TODO Is this always the case?

        # Determine which provider we are using by looking it up in the profile
        vm_provider = cloud_config['profiles'][options.vm_source]['provider'].split(':')[0]

        # Finally, we can get the provider password
        provider_password = cloud_config['providers']['linode']['linode']['password']

        # Using the password, we can construct a data structure for a salt-ssh roster
        roster_data = {options.vm_name:
                            {'host': get_minion_ip_address(options, sync=False),
                            'passwd': provider_password}
                        }
        # FIXME Perms!
        if not os.path.exists('/tmp/.jenkins_ssh'):
            os.mkdir('/tmp/.jenkins_ssh')
        with open('/tmp/.jenkins_ssh/roster', 'w') as roster_fh:
            yaml.dump(roster_data, stream=roster_fh)
        roster_fh.close()

        # We also need a master config file. Ours will point to the salt-jenkins repo and mount it with GitFS
        ssh_master_conf_data = {'fileserver_backend': ['git'], 'gitfs_remotes': ['https://github.com/saltstack/salt-jenkins.git']}

        with open('/tmp/.jenkins_ssh/master', 'w') as master_fh:
            yaml.dump(ssh_master_conf_data, stream=master_fh)
        master_fh.close()

        # Wait until the SSH server on the remote end is up
        while True:
            print_bulleted(options, 'Waiting for SSH to become available', 'LIGHT_GREEN')
            s = socket.socket()
            s.settimeout(5)
            retcode = s.connect_ex((get_minion_ip_address(options, sync=False), 22))
            if retcode == 0:
                print_bulleted(options, 'SSH access is ready')
                break
            else:
                time.sleep(2)
        return True

    else:
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


def find_private_addr(ip_addrs):
    '''
    Find an RFC 1918 IP address in ip_addrs
    '''
    for ip_address in ip_addrs:
        ip = [int(quad) for quad in ip_address.strip().split('.')]
        if ip[0] == 10:
            return ip_address
        elif ip[0] == 172 and ip[1] in [i for i in range(16, 32)]:
            return ip_address
        elif ip[0] == 192 and ip[1] == 168:
            return ip_address
        return ''


def get_minion_ip_address(options, sync=True):
    '''
    Get and store the remote minion IP address
    '''
    if 'salt_minion_bootstrapped' not in options:
        print_bulleted(options, 'Minion not boostrapped. Not grabbing IP address.', 'RED')
        sys.exit(1)
    if getattr(options, 'minion_ip_address', None):
        return options.minion_ip_address
    if sync:
        sync_minion(options)

    attempts = 1
    while attempts <= 3:
        print_bulleted(options, 'Fetching the IP address of the minion. Attempt {0}/3'.format(attempts))
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
            'grains.get', 'ipv4' if options.ssh_private_address else 'external_ip'
        ])
        stdout, stderr, exitcode = run_command(cmd,
                                               options,
                                               return_output=True,
                                               stream_stdout=False,
                                               stream_stderr=False)
        if exitcode != 0:
            if attempts == 3:
                print_bulleted(
                    options, 'Failed to get the minion IP address. Exit code: {0}'.format(exitcode), 'RED')
                sys.exit(exitcode)
            attempts += 1
            continue

        if not stdout.strip():
            if attempts == 3:
                print_bulleted(options, 'Failed to get the minion IP address(no output)', 'RED')
                sys.exit(1)
            attempts += 1
            continue

        try:

            ip_info = json.loads(stdout.strip())
            if options.ssh_private_address:
                ip_address = find_private_addr(ip_info[options.vm_name])
            else:
                ip_address = ip_info[options.vm_name]
            if not ip_address:
                print_bulleted(options, 'Failed to get the minion IP address(not found)', 'RED')
                sys.exit(1)
            setattr(options, 'minion_ip_address', ip_address)
            save_state(options)
            return ip_address
        except (ValueError, TypeError):
            print_bulleted(options, 'Failed to load any JSON from {0!r}'.format(stdout.strip()), 'RED')
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
        print_bulleted(options, 'Failed to get the minion IP address(no output)', 'RED')
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


def delete_parallels_vm(options):
    '''
    Delete a parallels instance
    '''
    base_cmd = ['salt', '-l', options.log_level]
    if options.no_color:
        base_cmd.append('--no-color')

    # Stop the VM; VMs must be stopped before they can be deleted
    stop_cmd = base_cmd + [options.vm_host,
                           'parallels.stop',
                           options.vm_name,
                           'kill=True',  # Immediate shutdown
                           'runas={0}'.format(options.vm_host_user)]
    stop_retcode = run_command(stop_cmd, options)

    # Delete the VM
    delete_cmd = base_cmd + [options.vm_host,
                             'parallels.delete',
                             options.vm_name,
                             'runas={0}'.format(options.vm_host_user)]
    delete_retcode = run_command(delete_cmd, options)

    # Delete the minion key
    key_cmd = ['salt-key']
    if options.no_color:
        key_cmd.append('--no-color')
    key_cmd.extend(['-yd', options.vm_name])
    key_retcode = run_command(key_cmd, options)

    if not all([stop_retcode, delete_retcode, key_retcode]):  # If all are zero
        return 0
    else:
        return 1


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
            print_flush('\n\n')
        else:
            print_bulleted(options, 'Matches!', 'LIGHT_GREEN')
        setattr(options, 'bootstrapped_salt_minion_version', SaltStackVersion.parse(version_info[options.vm_name]))
    except (ValueError, TypeError):
        print_bulleted(options, 'Failed to load any JSON from {0!r}'.format(stdout.strip()), 'RED')


def run_ssh_state_on_vm(options, state_name, saltenv=None, timeout=100):
    '''
    Run a state on a VM via SSH
    '''
    cmd = [
            'salt-ssh',
            '-l', options.log_level,
            '-c', '/tmp/.jenkins_ssh',
            '-i',
            options.vm_name,
            'state.sls', state_name,
            'pillar="{0}"'.format(build_pillar_data(options))
            ]
    if saltenv:
        cmd.extend(['saltenv={0}'.format(saltenv)])
    run_command(cmd, options)


def run_state_on_vm(options, state_name, saltenv=None, timeout=100):
    '''
    Run a state on the VM
    '''
    test_ssh_root_login(options)
    cmd = [
        'salt-call',
        '-l', options.log_level,
        '--retcode-passthrough'
    ]
    boot_version = getattr(options, 'bootstrapped_salt_minion_version', False)
    if boot_version and boot_version >= (2015, 2):
        cmd.append('--timeout={0}'.format(timeout))
    if options.no_color:
        cmd.append('--no-color')
    cmd.extend([
        'state.sls',
        state_name,
        'pillar="{0}"'.format(build_pillar_data(options))

    ])
    if saltenv:
        cmd.extend(['saltenv={0}'.format(saltenv)])
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
            print_flush('\n\n')
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
    # Setup SSH options
    test_ssh_root_login(options)
    cmd = ['ssh'] + build_ssh_opts(options)

    # Use double `-t` on the `ssh` command, it's necessary when `sudo` has
    # `requiretty` enforced.
    cmd.extend(['-t', '-t'])

    # Add VM URL
    cmd.append(
        '{0}@{1}'.format(
            options.require_sudo and options.ssh_username or 'root',
            get_minion_ip_address(options)
        )
    )

    # Compile remote command to a string
    if isinstance(remote_command, (list, tuple)):
        remote_command = ' '.join(remote_command)

    # Prepend sudo if needed
    if options.require_sudo and not remote_command.startswith('sudo'):
        remote_command = 'sudo {0}'.format(remote_command)

    # Workaround nonstandard path issue on MacOS
    if options.parallels_deploy:
        remote_command = 'source /etc/profile ; {0}'.format(remote_command)

    # Assemble local and remote parts into final command and return result
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
        'root@{0}'.format(get_minion_ip_address(options)),
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
            get_minion_ip_address(options)
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


def build_default_test_command(options):
    '''
    Construct the command that is sent to the minion to execute the test run
    '''
    python_bin_path = get_minion_python_executable(options)
    # This is a pretty naive aproach to get the coverage binary path
    coverage_bin_path = python_bin_path.replace('python', 'coverage')

    # Select python executable
    if 'salt_minion_bootstrapped' in options:
        test_command = [get_minion_python_executable(options)]
    else:
        print_bulleted(options, 'Minion not boostrapped. Not grabbing remote python executable.', 'YELLOW')
        test_command = ['python']

    # Append coverage parameters
    if options.test_without_coverage is False and options.test_with_new_coverage is True:
        test_command.extend([
            coverage_bin_path,
            'run',
            '--branch',
            '--concurrency=multiprocessing',
            '--parallel-mode',
        ])

    # Append basic command parameters
    test_command.extend([
        '/testing/tests/runtests.py',
        '-v',
        '--run-destructive',
        '--sysinfo',
        '--xml=/tmp/xml-unittests-output',
        '--transport={0}'.format(options.test_transport),
        '--output-columns={0}'.format(options.output_columns),
    ])

    # Append extra and conditional parameters
    pillar = build_pillar_data(options, convert_to_yaml=False)
    git_branch = pillar.get('git_branch', 'develop')
    if git_branch and git_branch not in('2014.1',):
        test_command.append('--ssh')
    if options.test_without_coverage is False and options.test_with_new_coverage is False:
        test_command.append('--coverage-xml=/tmp/coverage.xml')
    if options.no_color:
        test_command.append('--no-color')

    return test_command


def generate_xml_coverage_report(options, exit=True):
    '''
    generate coverage report
    '''
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
# <---- Helper Functions ---------------------------------------------------------------------------------------------


# ----- Parser Code ------------------------------------------------------------------------------------------------->
def get_args():
    '''
    Process command line arguments
    '''
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
    output_group_mutually_exclusive = output_group.add_mutually_exclusive_group()
    output_group_mutually_exclusive.add_argument(
        '--pull-request',
        type=int,
        action=GetPullRequestAction,
        default=None,
        help='Include the Pull Request information in parseable output'
    )
    output_group_mutually_exclusive.add_argument(
        '--branch',
        type=str,
        action=GetBranchAction,
        default='develop',
        help='Include the branch information in parseable output.  A GitHub'
             ' account/org other than saltstack can be specified by prefixing'
             ' it as <account>:<branch>'
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
        help='The name of the state which prepares the remote VM for SSH access'
    )
    ssh_options_group.add_argument(
        '--ssh-private-address',
        action='store_true',
        help='Try to find the RFC 1918 private address of the minion rather than the external address'
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
    deployment_group_mutually_exclusive.add_argument(
        '--parallels-deploy',
        action='store_true',
        default=False,
        help='Salt Parallels Desktop Deployment'
    )
    deployment_group.add_argument(
        '--pip-based',
        action='store_true',
        default=False,
        help='Allow pip based installations'
    )
    deployment_group.add_argument(
        '--insecure',
        action='store_true',
        default=False,
        help='Allow insecure connections while downloading any files'
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
        help='The salt git commit or tag used to bootstrap a minion'
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
        help=('The VM source. In case of --cloud-deploy usage, the cloud profile name. '
              'In case of --lxc-deploy usage, the image name. '
              'In case of --parallels-deploy usage, the VM to clone from.')
    )
    vm_options_group.add_argument(
        '--vm-host',
        default='prl-host',
        help=('The minion ID of the VM host system.')
    )
    vm_options_group.add_argument(
        '--vm-host-user',
        default='prl-user',
        help=('The user that parallels desktop runs as on the VM host system.')
    )
    vm_options_group.add_argument(
        '--vm-master',
        default='salt',
        help=('Until MacOS is supportd by bootstrap, this argument is used to '
              'supply the master location for custom bootstrapping of '
              'parallels VMs.')
    )
    vm_options_group.add_argument(
        '--vm-snapshot',
        default='system-updates',
        help=('Used with parallels base VMs to create linked VMs for test runs')
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
        '--salttesting-version',
        default=None,
        help='The version of salttesting to be installed into the test environment. i.e. 2016.7.22')
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
    testing_source_options.add_argument(
            '--test-prep-sls-branch',
            action='store_true',
            help='Pull test preparation states from a particular branch',
    )
    testing_source_options.add_argument(
        '--show-default-command',
        action='store_true',
        help='Print out the default command that runs the test suite on the deployed VM'
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
        help=('Execute the default command that runs the test suite on the deployed VM. '
              'To view the default command, use the --show-default-command option')
    )
    testing_source_options_mutually_exclusive.add_argument(
        '--test-interactive',
        action='store_true',
        help=('Bring up a VM will all the test dependencies and then wait. Access is '
              'handled via SSH keys. When finished, ctl-c to destroy the VM')
    )

    packaging_options = parser.add_argument_group(
        'Packaging Options',
        'Remove build of packages options'
    )
    packaging_options.add_argument(
        '--build-packages',
        default=False,
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
    return parser


def main():
    parser = get_args()
    options = parser.parse_args()

    # Print test suite command line and exit
    if options.show_default_command:
        print_flush(' '.join(build_default_test_command(options)))
        sys.exit(0)

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
        elif options.parallels_deploy:
            parser.exit(delete_parallels_vm(options))
        else:
            parser.error(
                'You need to specify from which deployment to delete the VM from. --{cloud|lxc|parallels}-deploy'
            )

    if options.bootstrap_salt_commit is None:
        options.bootstrap_salt_commit = os.environ.get(
            'SALT_MINION_BOOTSTRAP_RELEASE', 'develop'
        )

    if options.bootstrap_salt_url is None:
        options.bootstrap_salt_url = SALT_GIT_URL

    if any([options.cloud_deploy, options.lxc_deploy, options.parallels_deploy]):
        if options.cloud_deploy:
            exitcode = bootstrap_cloud_minion(options)
            if exitcode != 0:
                print_bulleted(options, 'Failed to bootstrap the cloud minion', 'RED')
                parser.exit(exitcode)
        elif options.lxc_deploy:
            exitcode = bootstrap_lxc_minion(options)
            if exitcode != 0:
                print_bulleted(options, 'Failed to bootstrap the LXC minion', 'RED')
                parser.exit(exitcode)
        elif options.parallels_deploy:
            exitcode = bootstrap_parallels_minion(options)
            if exitcode != 0:
                print_bulleted(options, 'Failed to bootstrap the parallels minion', 'RED')
                parser.exit(exitcode)

        print_bulleted(options, 'Sleeping for 5 seconds to allow the minion to breathe a little', 'YELLOW')
        time.sleep(5)
        if not options.test_interactive:
            check_bootstrapped_minion_version(options)
        time.sleep(1)
        prepare_ssh_access(options)
        time.sleep(1)

    # Run preparation SLS
    for sls in options.test_prep_sls:
        if options.test_interactive:
            exitcode = run_ssh_state_on_vm(options, sls, saltenv=options.test_prep_sls_branch, timeout=900)
        else:
            exitcode = run_state_on_vm(options, sls, saltenv=options.test_prep_sls_branch, timeout=900)
        if exitcode != 0:
            print_bulleted(options, 'The execution of the {0!r} SLS failed'.format(sls), 'RED')
            parser.exit(exitcode)
        time.sleep(1)

    if options.test_git_commit is not None:
        check_cloned_reposiory_commit(options)

    # If running in interactive mode, pause and wait for further instruction
    if options.test_interactive:
        run_interactive()

    # Construct default test runner command
    if options.test_default_command:
        options.test_command = build_default_test_command(options)

    # Run the main command using SSH for realtime output
    if options.test_command:
        exitcode = run_ssh_command(options, options.test_command)
        if exitcode != 0:
            print_bulleted(
                options, 'The execution of the test command {0!r} failed'.format(options.test_command), 'RED'
            )
            generate_xml_coverage_report(options, exit=False)
            parser.exit(exitcode)
        time.sleep(1)

        generate_xml_coverage_report(options, exit=False)

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
