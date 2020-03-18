# Copyright 2020 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""A Bluetooth adapter MTBF test of some Bluetooth use cases.

   To add a new use case we just need to inherit from the existing test class
   and then call the desired test methods in the batch method below. This allows
   the test case to be used as both part of a MTBF batch and a normal batch.
"""

from autotest_lib.server.cros.bluetooth.bluetooth_adapter_quick_tests import \
    BluetoothAdapterQuickTests
from autotest_lib.server.cros.bluetooth.bluetooth_adapter_better_together \
    import BluetoothAdapterBetterTogether

class bluetooth_AdapterMTBF(BluetoothAdapterBetterTogether):
    """A Batch of Bluetooth adapter tests for MTBF. This test is written
       as a batch of tests in order to reduce test time, since auto-test ramp up
       time is costly. The batch is using BluetoothAdapterQuickTests wrapper
       methods to start and end a test and a batch of tests.

       This class can be called to run the entire test batch or to run a
       specific test only
    """

    MTBF_TIMEOUT_MINS = 2
    batch_wrapper = BluetoothAdapterQuickTests.quick_test_batch_decorator
    mtbf_wrapper = BluetoothAdapterQuickTests.quick_test_mtbf_decorator

    @mtbf_wrapper(timeout_mins=MTBF_TIMEOUT_MINS)
    @batch_wrapper('Adapter MTBF')
    def mtbf_batch_run(self, num_iterations=1, test_name=None):
        """Run the Bluetooth MTBF test batch or a specific
           given test. The wrapper of this method is implemented in
           batch_decorator. Using the decorator a test batch method can
           implement the only its core tests invocations and let the
           decorator handle the wrapper, which is taking care for whether to
           run a specific test or the batch as a whole, and running the batch
           in iterations

           @param num_iterations: how many iterations to run
           @param test_name: specific test to run otherwise None to run the
                             whole batch
        """
        # TODO: finalize the test cases that need to be run as MTBF
        self.smart_unlock_test()


    def run_once(self, host, num_iterations=1, test_name=None):
        """Run the batch of Bluetooth MTBF tests

        @param host: the DUT, usually a chromebook
        @param num_iterations: the number of rounds to execute the test
        @test_name: the test to run, or None for all tests
        """

        # Initialize and run the test batch or the requested specific test
        self.quick_test_init(host, use_btpeer=True)
        self.mtbf_batch_run(num_iterations, test_name)
        self.quick_test_cleanup()
