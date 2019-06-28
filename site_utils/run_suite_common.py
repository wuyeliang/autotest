# Copyright 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Shared libs by run_suite.py & run_suite_skylab.py."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import collections
import json
import sys
import time

from autotest_lib.client.common_lib import enum


# Return code that will be sent back to callers.
#
# Note: Do not modify this enum; it is dependend upon by several clients.
RETURN_CODES = enum.Enum(
        'OK',
        'ERROR',
        'WARNING',
        'INFRA_FAILURE',
        'SUITE_TIMEOUT',
        'BOARD_NOT_AVAILABLE',
        'INVALID_OPTIONS',
)

# TODO (xixuan):  This is duplicated from suite_tracking.py in skylab.
# Make skylab caller also use this func.
TASK_COMPLETED = 'COMPLETED'
TASK_COMPLETED_SUCCESS = 'COMPLETED (SUCCESS)'
TASK_COMPLETED_FAILURE = 'COMPLETED (FAILURE)'
TASK_EXPIRED = 'EXPIRED'
TASK_CANCELED = 'CANCELED'
TASK_TIMEDOUT = 'TIMED_OUT'
TASK_RUNNING = 'RUNNING'
TASK_PENDING = 'PENDING'
TASK_BOT_DIED = 'BOT_DIED'
TASK_NO_RESOURCE = 'NO_RESOURCE'
TASK_KILLED = 'KILLED'

# Test status in _IGNORED_TEST_STATE won't be reported as test failure.
# Or test may be reported as failure as
# it's probably caused by the DUT is not well-provisioned.
# TODO: Stop ignoring TASK_NO_RESOURCE if we drop TEST_NA feature.
# Blocking issues:
#     - Not all DUT labels are in skylab yet (crbug.com/871978)
IGNORED_TEST_STATE = [TASK_NO_RESOURCE]


class SuiteResult(collections.namedtuple('SuiteResult',
                                         ['return_code', 'output_dict'])):
    """Result of running a suite to return."""

    def __new__(cls, return_code, output_dict=None):
        if output_dict is None:
            output_dict = dict()
        else:
            output_dict = output_dict.copy()
        output_dict['return_code'] = return_code
        return super(SuiteResult, cls).__new__(cls, return_code, output_dict)

    @property
    def string_code(self):
        """Return the enum string name of the numerical return_code."""
        return RETURN_CODES.get_string(self.return_code)


def dump_json(obj):
    """Write obj JSON to stdout."""
    output_json = json.dumps(obj, sort_keys=True)
    # These sleeps and flushes are a hack around the fact that when running
    # in the autotest proxy in --json_dump_postfix mode, run_suite.py co-mingles
    # both stdout and stderr (which include both logging output and json output)
    # to a single output stream. This can cause the json output to be corrupted
    # by concurrent writes (which is particularly likely because this dump
    # occurs at the end of run_suite's execution, along with other ending
    # logging). Buffer time and forced stream flushes reduce the likelihood of
    # concurrent writes.
    sys.stderr.flush()
    time.sleep(0.5)
    sys.stdout.flush()
    sys.stdout.write('\n#JSON_START#%s#JSON_END#\n' % output_json.strip())
    sys.stdout.flush()
    time.sleep(0.5)


# TODO (xixuan): This is duplicated from suite_tracking.py in skylab.
# Make skylab caller also use this func.
def get_final_skylab_task_state(task_result):
    """Get the final state of a swarming task.

    @param task_result: A json dict of SwarmingRpcsTaskResult object.
    """
    state = task_result['state']
    if state == TASK_COMPLETED:
        state = (TASK_COMPLETED_FAILURE if task_result['failure'] else
                 TASK_COMPLETED_SUCCESS)

    return state


def get_final_skylab_suite_states():
    return {
            TASK_COMPLETED_FAILURE:
            (
                    TASK_COMPLETED_FAILURE,
                    RETURN_CODES.ERROR,
            ),
            # Task No_Resource means no available bots to accept the task.
            # Deputy should check whether it's infra failure.
            TASK_NO_RESOURCE:
            (
                    TASK_NO_RESOURCE,
                    RETURN_CODES.INFRA_FAILURE,
            ),
            # Task expired means a task is not triggered, could be caused by
            #   1. No healthy DUTs/bots to run it.
            #   2. Expiration seconds are too low.
            #   3. Suite run is too slow to finish.
            # Deputy should check whether it's infra failure.
            TASK_EXPIRED:
            (
                    TASK_EXPIRED,
                    RETURN_CODES.INFRA_FAILURE,
            ),
            # Task canceled means a task is canceled intentionally. Deputy
            # should check whether it's infra failure.
            TASK_CANCELED:
            (
                    TASK_CANCELED,
                    RETURN_CODES.INFRA_FAILURE,
            ),
            TASK_TIMEDOUT:
            (
                    TASK_TIMEDOUT,
                    RETURN_CODES.SUITE_TIMEOUT,
            ),
            # Task pending means a task is still waiting for picking up, but
            # the suite already hits deadline. So report it as suite TIMEOUT.
            # It could also be an INFRA_FAILURE due to DUTs/bots shortage.
            TASK_PENDING:
            (
                    TASK_TIMEDOUT,
                    RETURN_CODES.SUITE_TIMEOUT,
            ),
    }
