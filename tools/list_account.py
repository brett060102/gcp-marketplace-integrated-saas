# Copyright 2018 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import sys
import time
from pprint import pp

from googleapiclient.discovery import build

PROJECT_ID = os.environ['GOOGLE_CLOUD_PROJECT']

PROCUREMENT_API = 'cloudcommerceprocurement'


def _get_parent_value():
    return 'providers/DEMO-{}'.format(PROJECT_ID)


def main(argv):
    """Main entrypoint to the Account list tool."""

    if argv[-1] in ('-h', '--help'):
        print('Usage: python3 list_accounts.py')
        return

    parent_value = _get_parent_value()

    procurement = build(PROCUREMENT_API, 'v1', cache_discovery=False)

    request = procurement.providers().accounts().list(parent=parent_value)
    response = request.execute()

    for acct in response['accounts']:
        pp(acct)


if __name__ == '__main__':
    main(sys.argv)
