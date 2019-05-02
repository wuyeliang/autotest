# Copyright 2019 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This class implements a Bluetooth quick sanity package"""

from autotest_lib.server.site_tests.bluetooth_AdapterLESanity import\
     bluetooth_AdapterLESanity
from autotest_lib.server.site_tests.bluetooth_AdapterSASanity import\
     bluetooth_AdapterSASanity

class bluetooth_AdapterQuickSanity(
        bluetooth_AdapterLESanity.bluetooth_AdapterLESanity,
        bluetooth_AdapterSASanity.bluetooth_AdapterSASanity):
    """This class implements a Bluetooth quick sanity package, using methods
    provided in BluetoothAdapterQuickTests,
    The package is running several sub batches of tests.
    A batch is defined as a set of tests, preferably with a common subject, e.g
    'LE Sanity' batch, or the 'Stand Alone Sanity' batch.
    The quick sanity test pacakge is imporving test time by doing the minimal
    cleanups between each test and test batches, saving the auto-test ramp up
    time of about 90-120 second per test.
    """

    def run_once(self, host, num_iterations=1):
        """Run the package of Bluetooth LE sanity tests

        @param host: the DUT, usually a chromebook
        @param num_iterations: the number of rounds to execute the test
        """

        # Init the quick test and start the package
        self.quick_test_init(host)
        self.quick_test_package_start('BT Quick Sanity')

        # Run sanity package
        for iter in xrange(num_iterations):
            self.quick_test_package_update_iteration(iter)
            self.sa_sanity_batch_run()
            self.le_sanity_batch_run()

        # End and cleanup test package
        self.quick_test_package_end()
        self.quick_test_cleanup()
