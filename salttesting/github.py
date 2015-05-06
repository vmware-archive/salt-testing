# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`


    salttesting.github
    ~~~~~~~~~~~~~~~~~~

    GitHub commit status notification
'''

# Import Python Libs
from __future__ import absolute_import
import os
import argparse

# Import 3rd-party libs
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

# ----- GitHub Endpoints -------------------------------------------------------------------------------------------->
GH_PULL_REQUEST_ENDPOINT = 'https://api.github.com/repos/{repo}/pulls/{pr}'
GH_COMMIT_STATUS_ENDPOINT = 'https://api.github.com/repos/{repo}/statuses/{sha}'
# <---- GitHub Endpoints ---------------------------------------------------------------------------------------------


# ----- GitHub API Requests ----------------------------------------------------------------------------------------->
def set_commit_status(parser, params, expected_http_status=(200,)):
    if HAS_REQUESTS is False:
        parser.error(
            'The python \'requests\' library needs to be installed'
        )

    headers = {}

    if parser.options.github_auth_token is None:
        github_access_token_path = os.path.join(
            os.environ.get('JENKINS_HOME', os.path.expanduser('~')),
            '.github_token'
        )
        if os.path.isfile(github_access_token_path):
            parser.options.github_auth_token = open(github_access_token_path).read().strip()

    if parser.options.github_auth_token is not None:
        headers = {
            'Authorization': 'token {0}'.format(
                parser.options.github_auth_token
            )
        }

    endpoint = GH_COMMIT_STATUS_ENDPOINT.format(repo=parser.options.repo, sha=parser.options.sha)

    http_req = requests.post(endpoint, headers=headers, json=params)

    if http_req.status_code not in expected_http_status:
        parser.error(
            'API request to {0!r} returned the wrong HTTP status code ({1}): {2[message]}'.format(
                endpoint,
                http_req.status_code,
                http_req.json()
            )
        )

    return http_req.json()
# <---- GitHub API Requests ------------------------------------------------------------------------------------------


# ----- Jenkins API Requests ---------------------------------------------------------------------------------------->
def get_jenkins_build_data(parser, build_url):
    if HAS_REQUESTS is False:
        parser.error(
            'The python \'requests\' library needs to be installed'
        )

    http_req = requests.get('{0}/api/json'.format(build_url))
    if http_req.status_code != 200:
        parser.error(
            'Jenkins API request returned the wrong HTTP status code ({0}): {1}'.format(
                http_req.status_code,
                http_req.text
            )
        )
    return http_req.json()
# <---- Jenkins API Requests -----------------------------------------------------------------------------------------


# ----- Argument Parsing Code --------------------------------------------------------------------------------------->
def main():
    parser = argparse.ArgumentParser(description='GitHub Commit Status Notifications')
    parser.add_argument('sha', metavar='COMMIT_SHA')
    parser.add_argument(
        '--auth-token',
        default=None,
        dest='github_auth_token',
        help='The GitHub API authentication token'
    )
    parser.add_argument(
        '--repo',
        default='saltstack/salt',
        help='The GitHub repository for this commit status. Default: {default}'
    )
    parser.add_argument(
        '--target-url',
        help='The URL link to a full report about the commit status',
        required=True
    )
    parser.add_argument(
        '--context',
        default='default',
        help='The context to use in the status'
    )
    parser.options = options = parser.parse_args()

    jenkins_build_data = get_jenkins_build_data(parser, options.target_url)

    description = u'{0} \u2014 '.format(jenkins_build_data['fullDisplayName'])
    if jenkins_build_data['building'] and jenkins_build_data.get('result', None) is None:
        description += 'RUNNING'
        state = 'pending'
    else:
        description += jenkins_build_data['result']
        if jenkins_build_data['result'] == 'SUCCESS':
            state = 'success'
        elif jenkins_build_data['result'] == 'ABORTED':
            state = 'error'
        else:
            state = 'failure'

    set_commit_status(
        parser,
        params={
            'state': state,
            'target_url': options.target_url,
            'description': description,
            'context': options.context
        },
        expected_http_status=(201,)
    )


if __name__ == '__main__':
    main()
# <---- Argument Parsing Code ----------------------------------------------------------------------------------------
