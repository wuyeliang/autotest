#!/usr/bin/python2
# pylint: disable-msg=C0111
#
# Copyright 2019 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file
"""Test for skylab json utils."""

from __future__ import unicode_literals

import unittest

import common
from autotest_lib.cli import skylab_rollback


class skylab_rollback_unittest(unittest.TestCase):
    def test_batches(self):
        xs = list(range(40))
        expected = [list(range(20)), list(range(20, 40))]
        actual = list(skylab_rollback._batches(xs, batch_size=20))
        self.assertEqual(expected, actual)

    def test_rollback(self):
        actual = skylab_rollback.rollback(["a", "b"], dry_run=True)
        expected = [["bash", "-c", skylab_rollback.ROLLBACK_CMD, "bash", "a", "b"]]
        self.assertEqual(expected, actual)


if __name__ == "__main__":
    unittest.main()
