# Copyright 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Wrapper for aborting suites of tests.

Usage: ./abort_suite.py

This code exists to allow buildbot to abort a HWTest run if another part of
the build fails while HWTesting is going on.  If we're going to fail the
build anyway, there's no point in continuing to run tests.

This script aborts suite job and its children jobs.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import argparse
import logging
import sys

from lucifer import autotest
from skylab_suite import suite_tracking
from skylab_suite import swarming_lib


def _abort_suite_tasks(client, suite_tasks):
    aborted_suite_num = 0
    for pt in suite_tasks:
        logging.info('Aborting suite task %s', pt['task_id'])
        client.abort_task(pt['task_id'])
        if 'children_task_ids' not in pt:
            logging.info('No child tasks for task %s', pt['task_id'])
            continue

        for ct in pt['children_task_ids']:
            logging.info('Aborting task %s', ct)
            client.abort_task(ct)


def _get_suite_tasks_by_suite_ids(client, suite_task_ids):
    """Return a list of tasks with the given list of suite_task_ids."""
    suite_tasks = []
    for suite_task_id in suite_task_ids:
        suite_tasks.append(client.query_task_by_id(suite_task_id))

    return suite_tasks


def _get_suite_tasks_by_specs(client, board, build, suite):
    """Return a list of tasks with given board/build/suite."""
    tags = {'pool': swarming_lib.SKYLAB_SUITE_POOL,
            'board': board,
            'build': build,
            'suite': suite}
    return client.query_task_by_tags(tags)


def _abort_suite(options):
    """Abort the suite.

    This method aborts the suite job and its children jobs, including
    'RUNNING' jobs.
    """
    client = swarming_lib.Client(options.swarming_auth_json)
    if options.suite_task_ids:
        parent_tasks = _get_suite_tasks_by_suite_ids(client,
                                                     options.suite_task_ids)
    else:
        parent_tasks = _get_suite_tasks_by_specs(
                client, options.board, options.build, options.suite_name)

    _abort_suite_tasks(client, parent_tasks[:min(options.abort_limit,
                                            len(parent_tasks))])
    logging.info('Suite %s/%s has been aborted.', options.build,
                 options.suite_name)


def parse_args():
    """Parse and validate abort_suite_skylab args."""
    parser = argparse.ArgumentParser(
            prog='abort_suite_skylab',
            description="Abort a test suite in Skylab.")
    parser.add_argument(
        '--suite_name', help='Suite to abort.')
    parser.add_argument(
        '--build', help='Build to abort.')
    parser.add_argument(
        '--board', help='Board to abort.')
    parser.add_argument(
        '--abort_limit', default=sys.maxint, type=int, action='store',
        help=('Only abort first N parent tasks which fulfill the search '
              'requirements.'))
    parser.add_argument(
        '--suite_task_ids', nargs='*', default=[],
        help=('Specify the parent swarming task id to abort.'))

    parser.add_argument(
        '--swarming_auth_json', default=swarming_lib.DEFAULT_SERVICE_ACCOUNT,
        action='store', help="Path to swarming service account json creds. "
        "Specify '' to omit. Otherwise, defaults to bot's default creds.")

    # Deprecated arguments to be deleted once callers are updated.
    parser.add_argument('--pool', help=argparse.SUPPRESS)

    options = parser.parse_args()

    if not options.suite_task_ids:
        if not (options.board and options.suite_name and options.build):
            raise ValueError('Either a suite id, or all of board build and '
                             'suite name must be specified.')

    return options


def main():
    """Entry point."""
    autotest.monkeypatch()

    options = parse_args()
    print (options.suite_task_ids)
    print (options.abort_limit)
    suite_tracking.setup_logging()
    _abort_suite(options)
    return 0


if __name__ == "__main__":
    sys.exit(main())
