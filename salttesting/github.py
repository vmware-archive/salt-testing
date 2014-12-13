# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`


    salttesting.github
    ~~~~~~~~~~~~~~~~~~

    GitHub commit status notification
'''

# Import Python Libs
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


# ----- GitHub Commit Status States --------------------------------------------------------------------------------->
class StatusStates(object):
    PENDING = 'pending'
    SUCCESS = 'success'
    FAILURE = 'failure'
    ERROR = 'error'

    def __iter__(self):
        return iter([self.PENDING, self.SUCCESS, self.FAILURE, self.ERROR])
# <---- GitHub Commit Status States ----------------------------------------------------------------------------------


# ----- GitHub API Requests ----------------------------------------------------------------------------------------->
def api_request(parser, endpoint, params, method='GET', expected_http_status=(200,)):
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

    endpoint = endpoint.format(repo=parser.options.repo, sha=parser.options.sha)

    if method == 'GET':
        http_req = requests.get(endpoint, headers=headers, params=params)
    elif method == 'POST':
        http_req = requests.post(endpoint, headers=headers, json=params)

    print http_req.text
    if http_req.status_code not in expected_http_status:
        parser.error(
            'API requests returned the wrong HTTP status code ({0}): {1[message]}'.format(
                http_req.status_code,
                http_req.json()
            )
        )

    return http_req.json()
# <---- GitHub API Requests ------------------------------------------------------------------------------------------


# ----- Argument Parsing Code --------------------------------------------------------------------------------------->
def main():
    parser = argparse.ArgumentParser(description='GitHub Commit Status Notifications')
    parser.add_argument('sha', metavar='COMMIT_SHA')
    parser.add_argument(
        '--repo',
        default='saltstack/salt',
        help='The GitHub repository for this commit status. Default: {default}'
    )
    parser.add_argument(
        '--state',
        choices=list(StatusStates()),
        help='The commit state to set',
        required=True
    )
    parser.add_argument(
        '--target-url',
        help='The URL link to a full report about the commit status'
    )
    parser.add_argument(
        '--description',
        help='Short description about the status',
        required=True
    )
    parser.add_argument(
        '--context',
        default='default',
        help='The context to use in the status'
    )
    parser.options = options = parser.parse_args()

    api_request(
        parser,
        GH_COMMIT_STATUS_ENDPOINT,
        params={
            'state': options.state,
            'target_url': options.target_url,
            'description': options.description,
            'context': options.context
        },
        method='POST',
        expected_http_status=(201,)
    )


if __name__ == '__main__':
    main()
# <---- Argument Parsing Code ----------------------------------------------------------------------------------------
