# Copyright 2019 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""A Batch of of Bluetooth LE sanity tests"""

import logging
import time

from autotest_lib.server.cros.bluetooth.bluetooth_adapter_quick_tests import \
     BluetoothAdapterQuickTests

from server.site_tests.bluetooth_AdapterPairing.bluetooth_AdapterPairing  import bluetooth_AdapterPairing
from server.site_tests.bluetooth_AdapterHIDReports.bluetooth_AdapterHIDReports  import bluetooth_AdapterHIDReports

class bluetooth_AdapterLESanity(BluetoothAdapterQuickTests,
        bluetooth_AdapterPairing,
        bluetooth_AdapterHIDReports):
    """A Batch of Bluetooth LE sanity tests. This test is written as a batch
       of tests in order to reduce test time, since auto-test ramp up time is
       costly. The batch is using BluetoothAdapterQuickTests wrapper methods to
       start and end a test and a batch of tests.

       This class can be called to run the entire test batch or to run a
       specific test only
    """

    test_wrapper = BluetoothAdapterQuickTests.quick_test_test_decorator
    batch_wrapper = BluetoothAdapterQuickTests.quick_test_batch_decorator

    @test_wrapper('Connect Disconnect Loop', devices=['BLE_MOUSE'])
    def le_connect_disconnect_loop(self):
        """Run connect/disconnect loop initiated by DUT.
           The test also checks that there are no undesired
           reconnections.
           TODO(ysahvit) - add connection creation attempts
                           initiated by HID device
        """

        device = self.devices['BLE_MOUSE']
        self.connect_disconnect_loop(device=device, loops=3)

    @test_wrapper('Mouse Reports', devices=['BLE_MOUSE'])
    def le_mouse_reports(self):
        """Run all bluetooth mouse reports tests"""

        device = self.devices['BLE_MOUSE']
        # Let the adapter pair, and connect to the target device.
        self.test_discover_device(device.address)
        # self.bluetooth_facade.is_discovering() doesn't work as expected:
        # crbug:905374
        # self.test_stop_discovery()
        self.bluetooth_facade.stop_discovery()
        time.sleep(self.TEST_SLEEP_SECS)
        self.test_pairing(device.address, device.pin, trusted=True)
        time.sleep(self.TEST_SLEEP_SECS)
        self.test_connection_by_adapter(device.address)
        self.run_mouse_tests(device=device)


    @test_wrapper('Auto Reconnect', devices=['BLE_MOUSE'])
    def le_auto_reconnect(self):
        """LE reconnection loop by reseting HID and check reconnection"""

        device = self.devices['BLE_MOUSE']
        self.auto_reconnect_loop(device=device, loops=3)


    @batch_wrapper('LE Sanity')
    def le_sanity_batch_run(self, num_iterations=1, test_name=None):
        """Run the LE sanity test batch or a specific given test.
           The wrapper of this method is implemented in batch_decorator.
           Using the decorator a test batch method can implement the only its
           core tests invocations and let the decorator handle the wrapper,
           which is taking care for whether to run a specific test or the
           batch as a whole, and running the batch in iterations

           @param num_iterations: how many interations to run
           @param test_name: specifc test to run otherwise None to run the
                             whole batch
        """
        self.le_connect_disconnect_loop()
        self.le_mouse_reports()
        self.le_auto_reconnect()


    def run_once(self, host, num_iterations=1, test_name=None):
        """Run the batch of Bluetooth LE sanity tests

        @param host: the DUT, usually a chromebook
        @param num_iterations: the number of rounds to execute the test
        @test_name: the test to run, or None for all tests
        """

        # Initialize and run the test batch or the requested specific test
        self.quick_test_init(host, use_chameleon=True)
        self.le_sanity_batch_run(num_iterations, test_name)
        self.quick_test_cleanup()
