# Copyright (c) 2020 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock
import unittest
from autotest_lib.client.common_lib import error
from autotest_lib.server.cros.faft import firmware_test


class TestRunOnce(unittest.TestCase):
    class GoodFirmwareTest(firmware_test.FirmwareTest):
        # Init logic in FirmwareTest is not relevant to this test.
        def __init__(self, *args, **dargs):
            self.test = mock.MagicMock()
            self.test_good = mock.MagicMock()
            self.test_good_better = mock.MagicMock()

    def test_keyword_test_name(self):
        ft = self.GoodFirmwareTest()

        ft.run_once(test_name='GoodFirmwareTest.good')
        ft.test_good.assert_called_with()

        ft.run_once('arg1', test_name='GoodFirmwareTest.good', arg2='arg2')
        ft.test_good.assert_called_with('arg1', arg2='arg2')

    def test_positional_test_name(self):
        ft = self.GoodFirmwareTest()

        ft.run_once('GoodFirmwareTest.good')
        ft.test_good.assert_called_with()

        ft.run_once('GoodFirmwareTest.good', 'arg1', arg2='arg2')
        ft.test_good.assert_called_with('arg1', arg2='arg2')

    def test_no_test_name(self):
        ft = self.GoodFirmwareTest()

        ft.run_once('GoodFirmwareTest')
        ft.test.assert_called_with()

        ft.run_once('GoodFirmwareTest', 'arg1', arg2='arg2')
        ft.test.assert_called_with('arg1', arg2='arg2')

    def test_sub_test_name(self):
        ft = self.GoodFirmwareTest()

        ft.run_once('GoodFirmwareTest.good.better')
        ft.test_good_better.assert_called_with()

        ft.run_once('GoodFirmwareTest.good.better', 'arg1', arg2='arg2')
        ft.test_good_better.assert_called_with('arg1', arg2='arg2')

    def test_missing_test_name(self):
        ft = self.GoodFirmwareTest()

        with self.assertRaises(error.TestError):
            ft.run_once()

    def test_bad_class_name(self):
        ft = self.GoodFirmwareTest()

        with self.assertRaises(error.TestError):
            ft.run_once(test_name='BadFirmwareTest')

    def test_bad_method_name(self):
        ft = self.GoodFirmwareTest()

        with self.assertRaises(error.TestError):
            ft.run_once(test_name='GoodFirmwareTest.bad')

if __name__ == '__main__':
    unittest.main()
