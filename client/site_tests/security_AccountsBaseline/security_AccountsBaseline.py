# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import shutil

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error

class security_AccountsBaseline(test.test):
    version = 1

    def load_path(self, fpath):
        """Load the given passwd/group file."""
        return [x.strip().split(':') for x in open(fpath).readlines()]


    def capture_files(self):
        for f in ['passwd','group']:
            shutil.copyfile(os.path.join('/etc',f),
                            os.path.join(self.resultsdir,f))


    def run_once(self):
        failed = False

        self.capture_files()
        # Match users
        passwd_baseline = self.load_path(os.path.join(
            self.bindir, 'baseline.passwd'))
        passwd_actual = self.load_path('/etc/passwd')

        if len(passwd_actual) != len(passwd_baseline):
            failed = True
            logging.error('User baseline mismatch. '
                'Expected: %d users. Got: %d.' % (
                len(passwd_baseline), len(passwd_actual)))
        for expected in passwd_baseline:
            got = [x for x in passwd_actual if x[0] == expected[0]]
            if not got:
                failed = True
                logging.error('No passwd entry for %s' % expected[0])
                continue
            got = got[0]
            # Match uid (3rd field) and gid (4th field).
            if (expected[2], expected[3]) != (got[2], got[3]):
                failed = True
                logging.error(
                    'Expected uid/gid (%s, %s) for user %s. Got (%s, %s)' %
                    (expected[2], expected[3], got[0], got[2], got[3]))
        for actual in passwd_actual:
            got = [x for x in passwd_baseline if x[0] == actual[0]]
            if not got:
                failed = True
                logging.error('Unexpected passwd entry for %s' % actual[0])

        # Match groups
        group_baseline = self.load_path(os.path.join(
            self.bindir, 'baseline.group'))
        group_actual = self.load_path('/etc/group')

        if len(group_actual) != len(group_baseline):
            failed = True
            logging.error('Group baseline mismatch. '
                'Expected: %d groups. Got: %d.' % (
                len(group_baseline), len(group_actual)))
        for expected in group_baseline:
            got = [x for x in group_actual if x[0] == expected[0]]
            if not got:
                failed = True
                logging.error('No group entry for %s' % expected[0])
                continue
            got = got[0]
            # Match gid (3rd field) and members (4th field. comma separated).
            if expected[2] != got[2]:
                failed = True
                logging.error('Expected id %s for group %s). Got %s' %
                    (expected[2], expected[0], got[2]))
            if set(expected[3].split(',')) != set(got[3].split(',')):
                failed = True
                logging.error(
                    'Expected members %s for group %s. Got %s' % (
                    expected[3], expected[0], got[3]))
        for actual in group_actual:
            got = [x for x in group_baseline if x[0] == actual[0]]
            if not got:
                failed = True
                logging.error('Unexpected group entry for %s' % actual[0])

        # Fail the test after all mismatches have been reported.
        if failed:
            raise error.TestFail('Baseline mismatch.')
