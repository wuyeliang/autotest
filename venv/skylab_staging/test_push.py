# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Run the skylab staging test.

This script runs a suite of autotest tests and some other sanity checks against
a given Skylab instance. If all sanity checks and tests have the expected
results, the script exits with success.

This script is intended to be used for the Autotest staging lab's test_push.
This script does not update any software before running the tests (i.e. caller
is responsible for setting up the staging lab with the correct software
beforehand), nor does it update any software refs on success (i.e. caller is
responsible for blessing the newer version of software as needed).
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import argparse
import json
import logging
import os
import re
import sys

from lucifer import autotest
from lucifer import loglib


cros_build_lib = autotest.deferred_chromite_load('cros_build_lib')
metrics = autotest.deferred_chromite_load('metrics')
ts_mon_config = autotest.deferred_chromite_load('ts_mon_config')


_METRICS_PREFIX = 'chromeos/autotest/test_push/skylab'
_WAIT_FOR_DUTS_TIMEOUT_S = 20 * 60

# TODO(crbug.com/1014685): Make the DUT to repair a commandline parameter,
# or autodetected by a swarming query.
_REPAIR_DUT = 'chromeos4-row7-rack6-host21'

_logger = logging.getLogger(__name__)


def main():
  """Entry point of test_push."""
  parser = _get_parser()
  loglib.add_logging_options(parser)
  args = parser.parse_args()
  loglib.configure_logging_with_args(parser, args)

  with ts_mon_config.SetupTsMonGlobalState(service_name='skylab_test_push',
                                           indirect=True):
    success = False
    try:
      with metrics.SecondsTimer(_METRICS_PREFIX + '/durations/total',
                                add_exception_field=True):
        _run_test_push(args)
      logging.info('run_test_push completed successfully')
      success = True
    finally:
      metrics.Counter(_METRICS_PREFIX + '/tick').increment(
          fields={'success': success})

def _get_parser():
  parser = argparse.ArgumentParser(
      description='Run test_push against Skylab instance.')
  parser.add_argument(
      '--swarming-url',
      required=False,
      help='Full URL to the Swarming instance to use',
  )
  parser.add_argument(
      '--swarming-cli',
      required=False,
      help='Path to the Swarming cli tool.',
  )
  # TODO(crbug.com/867969) Use model instead of board once skylab inventory has
  # model information.
  parser.add_argument(
      '--dut-board',
      required=False,
      help='Deprecated.',
  )
  parser.add_argument(
      '--dut-pool',
      required=False,
      choices=('DUT_POOL_CQ', 'DUT_POOL_BVT', 'DUT_POOL_SUITES'),
      help='Deprecated.',
  )
  parser.add_argument(
      '--build',
      required=False,
      help='Deprecated.',
  )
  parser.add_argument(
      '--timeout-mins',
      type=int,
      required=False,
      default=20,
      help='Overall timeout for the test_push. On timeout, test_push'
           ' attempts to abort any in-flight test suites before quitting.',
  )
  parser.add_argument(
      '--num-min-duts',
      type=int,
      help='Deprecated.',
  )
  parser.add_argument(
      '--service-account-json',
      required=False,
      help='(Optional) Path to the service account credentials file to'
           ' authenticate with Swarming service.',
  )
  return parser


def _skylab_tool():
  """Return path to skylab tool."""
  return os.environ.get('SKYLAB_TOOL', '/opt/infra-tools/skylab')


class TestPushFailure(Exception):
  """Raised when test push fails."""


def _run_test_push(args):
  """Meat of the test_push flow."""
  service_account_json = args.service_account_json

  cmd = [
    _skylab_tool(), 'repair', '-dev'
  ]
  if service_account_json:
    cmd += ['-service-account-json', service_account_json]
  cmd.append(_REPAIR_DUT)

  cmd_result = cros_build_lib.RunCommand(cmd, redirect_stdout=True)
  m = re.search('task\?id=(\w*)', cmd_result.output)
  if not m:
    raise TestPushFailure('Found no task ID in `skylab repair` output:\n%s',
                          cmd_result.output)
  task_id = m.group(1)
  logging.info('Launched repair task with ID %s', task_id)

  cmd = [
    _skylab_tool(), 'wait-task', '-dev', '-bb=False',
    '-timeout-mins', str(args.timeout_mins)
  ]
  if service_account_json:
    cmd += ['-service-account-json', service_account_json]
  cmd.append(task_id)

  cmd_result = cros_build_lib.RunCommand(cmd, redirect_stdout=True)
  result = json.loads(cmd_result.output)
  logging.info('Returned from wait with parsed output:\n%s', result)
  if not result['task-result']['success']:
    raise TestPushFailure('repair task did not succeed; test_push failed.')


if __name__ == '__main__':
  autotest.monkeypatch()
  sys.exit(main())
