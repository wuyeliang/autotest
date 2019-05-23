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
import collections
import json
import logging
import os
import sys
import time

from lucifer import autotest
from lucifer import loglib
from skylab_staging import errors
from skylab_staging import swarming


cros_build_lib = autotest.deferred_chromite_load('cros_build_lib')
metrics = autotest.deferred_chromite_load('metrics')
ts_mon_config = autotest.deferred_chromite_load('ts_mon_config')


_METRICS_PREFIX = 'chromeos/autotest/test_push/skylab'
_POLLING_INTERVAL_S = 10
_WAIT_FOR_DUTS_TIMEOUT_S = 20 * 60

# Dictionary of test results expected in suite:skylab_staging_test.
_EXPECTED_TEST_RESULTS = {'login_LoginSuccess.*':         ['GOOD'],
                          'provision_AutoUpdate.double':  ['GOOD'],
                          'dummy_Pass$':                  ['GOOD'],
                          'dummy_Pass.actionable$':       ['GOOD'],
                          'dummy_Pass.bluetooth$':        ['GOOD'],
                          # ssp and nossp.
                          'dummy_PassServer$':            ['GOOD', 'GOOD'],
                          # The entire dummy_Fail test is retried.
                          'dummy_Fail.Fail$':             ['FAIL', 'FAIL'],
                          'dummy_Fail.Error$':            ['ERROR', 'ERROR'],
                          'dummy_Fail.Warn$':             ['WARN', 'WARN'],
                          'dummy_Fail.NAError$':          ['TEST_NA',
                                                           'TEST_NA'],
                          'dummy_Fail.Crash$':            ['GOOD', 'GOOD'],
                          'tast.*':                       ['GOOD'],
                          }

# Some test could be missing from the test results for various reasons. Add
# such test in this list and explain the reason.
_IGNORED_TESTS = [
]

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
      success = True
    finally:
      metrics.Counter(_METRICS_PREFIX + '/tick').increment(
          fields={'success': success})

def _get_parser():
  parser = argparse.ArgumentParser(
      description='Run test_push against Skylab instance.')
  parser.add_argument(
      '--swarming-url',
      required=True,
      help='Full URL to the Swarming instance to use',
  )
  parser.add_argument(
      '--swarming-cli',
      required=True,
      help='Path to the Swarming cli tool.',
  )
  # TODO(crbug.com/867969) Use model instead of board once skylab inventory has
  # model information.
  parser.add_argument(
      '--dut-board',
      required=True,
      help='Label board of the DUTs to use for testing',
  )
  parser.add_argument(
      '--dut-pool',
      required=True,
      choices=('DUT_POOL_CQ', 'DUT_POOL_BVT', 'DUT_POOL_SUITES'),
      help='Label pool of the DUTs to use for testing',
  )
  parser.add_argument(
      '--build',
      required=True,
      help='ChromeOS build to use for provisioning'
           ' (e.g.: gandolf-release/R54-8743.25.0).',
  )
  parser.add_argument(
      '--timeout-mins',
      type=int,
      required=True,
      help='(Optional) Overall timeout for the test_push. On timeout, test_push'
           ' attempts to abort any in-flight test suites before quitting.',
  )
  parser.add_argument(
      '--num-min-duts',
      type=int,
      help='Minimum number of Ready DUTs required for test suite.',
  )
  parser.add_argument(
      '--service-account-json',
      required=True,
      help='(Optional) Path to the service account credentials file to'
           ' authenticate with Swarming service.',
  )
  return parser


def _skylab_tool():
  """Return path to skylab tool."""
  return os.environ.get('SKYLAB_TOOL', '/opt/infra-tools/skylab')


def _run_test_push(args):
  """Meat of the test_push flow."""
  deadline = time.time() + (args.timeout_mins * 60)
  swclient = swarming.Client(args.swarming_cli, args.swarming_url,
                             args.service_account_json)
  if args.num_min_duts:
    _ensure_duts_ready(
        swclient,
        args.dut_board,
        args.dut_pool,
        args.num_min_duts,
        min(deadline - time.time(), _WAIT_FOR_DUTS_TIMEOUT_S),
    )

  # Just like the builders, first run a provision suite to provision required
  # DUTs, then run the actual suite.
  with metrics.SecondsTimer(_METRICS_PREFIX + '/durations/provision_suite',
                            add_exception_field=True):
    _create_suite_and_wait(
        args.dut_board, args.dut_pool, args.build, deadline,
        args.service_account_json, 'provision')

  with metrics.SecondsTimer(_METRICS_PREFIX + '/durations/push_to_prod_suite',
                            add_exception_field=True):
    task_id = _create_suite_and_wait(
        args.dut_board, args.dut_pool, args.build, deadline,
        args.service_account_json, 'skylab_staging_test',
        require_success=False)

  _verify_test_results(task_id, _EXPECTED_TEST_RESULTS)


def _create_suite_and_wait(dut_board, dut_pool, build, deadline,
                           service_account_json, suite, require_success=True):
  """Create and wait for a skylab suite (in staging).

  Returns: string task run id of the completed suite.

  Raises: errors.TestPushError if the suite failed and require_success is True.
  """
  mins_remaining = int((deadline - time.time())/60)
  cmd = [
    _skylab_tool(), 'create-suite',
    # test_push always runs in dev instance of skylab
    '-dev',
    '-board', dut_board,
    '-pool', dut_pool,
    '-image', build,
    '-timeout-mins', str(mins_remaining),
    '-service-account-json', service_account_json,
    '-json',
    suite,
  ]

  cmd_result = cros_build_lib.RunCommand(cmd, redirect_stdout=True)
  task_id = json.loads(cmd_result.output)['task_id']
  _logger.info('Triggered suite %s. Task id: %s', suite, task_id)

  cmd = [
    _skylab_tool(), 'wait-task',
    '-dev',
    '-service-account-json', service_account_json,
    task_id
  ]
  cmd_result = cros_build_lib.RunCommand(cmd, redirect_stdout=True)

  _logger.info(
      'Finished suite %s with output: \n%s', suite,
      json.loads(cmd_result.output)['stdout']
  )
  if (require_success and
      not json.loads(cmd_result.output)['task-result']['success']):
    raise errors.TestPushError('Suite %s did not succeed.' % suite)

  return json.loads(cmd_result.output)['task-result']['task-run-id']


def _verify_test_results(task_id, expected_results):
  """Verify if test results are expected."""
  _logger.info('Comparing test results for suite task %s...', task_id)
  test_views = _get_test_views(task_id)
  available_views = [v for v in test_views if _view_is_preserved(v)]
  logging.debug('Test results:')
  for v in available_views:
    logging.debug('%s%s', v['test_name'].ljust(30), v['status'])

  summary = _verify_and_summarize(available_views, expected_results)
  if summary:
    logging.error('\n'.join(summary))
    raise errors.TestPushError('Test results are not consistent with '
                               'expected results')


def _get_test_views(task_id):
  """Retrieve test views from TKO for skylab task id."""
  tko_db = autotest.load('tko.db')
  db = tko_db.db()
  return db.get_child_tests_by_parent_task_id(task_id)


def _view_is_preserved(view):
  """Detect whether to keep the test view for further comparison."""
  job_status = autotest.load('server.cros.dynamic_suite.job_status')
  return (job_status.view_is_relevant(view) and
          (not job_status.view_is_for_suite_job(view)))


def _verify_and_summarize(available_views, expected_results):
  """Verify and generate summaries for test_push results."""
  test_push_common = autotest.load('site_utils.test_push_common')
  views = collections.defaultdict(list)
  for view in available_views:
    views[view['test_name']].append(view['status'])
  return test_push_common.summarize_push(views, expected_results,
                                         _IGNORED_TESTS)


def _ensure_duts_ready(swclient, board, pool, min_duts, timeout_s):
  """Ensure that at least num_duts are in the ready dut_state."""
  start_time = time.time()
  while True:
    _logger.debug('Checking whether %d DUTs are available', min_duts)
    num_duts = swclient.num_ready_duts(board, pool)
    if num_duts >= min_duts:
      _logger.info(
          '%d available DUTs satisfy the minimum requirement of %d DUTs',
          num_duts, min_duts,
      )
      return
    if time.time() - start_time > timeout_s:
      raise errors.TestPushError(
          'Could not find %d ready DUTs with (board:%s, pool:%s) within %d'
          ' seconds' % (min_duts, board, pool, timeout_s)
      )
    time.sleep(_POLLING_INTERVAL_S)


if __name__ == '__main__':
  autotest.monkeypatch()
  sys.exit(main())
