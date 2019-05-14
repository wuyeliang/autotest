# Copyright 2019 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""A Batch of of Bluetooth LE sanity tests"""

import logging
import time

from autotest_lib.server.cros.bluetooth import bluetooth_adapter_quick_tests
from autotest_lib.server.cros.bluetooth.bluetooth_adapter_quick_tests import \
     BluetoothAdapterQuickTests

class bluetooth_AdapterLESanity(BluetoothAdapterQuickTests):
    """A Batch of Bluetooth LE sanity tests. This test is written as a batch
       of tests in order to reduce test time, since auto-test ramp up time is
       costly. The batch is using BluetoothAdapterQuickTests wrapper methods to
       start and end a test and a batch of tests.

       This class can be called to run the entire test batch or to run a
       specific test only (todo http://b/132199238)
    """

    test_wrapper = BluetoothAdapterQuickTests.quick_test_test_decorator
    batch_wrapper = BluetoothAdapterQuickTests.quick_test_batch_decorator

    @test_wrapper('Connect Disconnect Loop')
    def le_connect_disconnect_loop(self):
        """Run connect/disconnect loop initiated by DUT.
           The test also checks that there are no undesired
           reconnections.
           TODO(ysahvit) - add connection creation attempts
                           initiated by HID device
        """
        # First pair and disconnect, to emulate real life scenario
        self.test_discover_device(self.device.address)
        # self.bluetooth_facade.is_discovering() doesn't work as expected:s
        # crbug:905374
        # self.test_stop_discovery()
        self.bluetooth_facade.stop_discovery()
        time.sleep(self.TEST_SLEEP_SECS)
        self.test_pairing(self.device.address, self.device.pin, trusted=True)
        time.sleep(self.TEST_SLEEP_SECS)
        # Disconnect the device
        self.test_disconnection_by_adapter(self.device.address)
        total_duration_by_adapter = 0
        loops = 3
        loop_cnt = 0
        for i in xrange(0, loops):

            # Verify device didn't connect automatically
            time.sleep(2)
            self.test_device_is_not_connected(self.device.address)

            start_time = time.time()
            self.test_connection_by_adapter(self.device.address)
            end_time = time.time()
            time_diff = end_time - start_time

            # Verify device is now connected
            self.test_device_is_connected(self.device.address)
            self.test_disconnection_by_adapter(self.device.address)

            if not bool(self.fails):
                loop_cnt += 1
                total_duration_by_adapter += time_diff
                logging.info('%d: Connection establishment duration %f sec',
                             i, time_diff)
            else:
               break

        if not bool(self.fails):
            logging.info('Average duration (by adapter) %f sec',
                         total_duration_by_adapter/loop_cnt)

    @test_wrapper('Mouse Reports')
    def le_mouse_reports(self):
        """Run all bluetooth mouse reports tests"""

         # Let the adapter pair, and connect to the target device.
        self.test_discover_device(self.device.address)
        # self.bluetooth_facade.is_discovering() doesn't work as expected:
        # crbug:905374
        # self.test_stop_discovery()
        self.bluetooth_facade.stop_discovery()
        time.sleep(self.TEST_SLEEP_SECS)
        self.test_pairing(self.device.address, self.device.pin, trusted=True)
        time.sleep(self.TEST_SLEEP_SECS)
        self.test_connection_by_adapter(self.device.address)

        self.test_mouse_left_click(self.device)
        self.test_mouse_right_click(self.device)
        self.test_mouse_move_in_x(self.device, 80)
        self.test_mouse_move_in_y(self.device, -50)
        self.test_mouse_move_in_xy(self.device, -60, 100)
        self.test_mouse_scroll_down(self.device, 70)
        self.test_mouse_scroll_up(self.device, 40)
        self.test_mouse_click_and_drag(self.device, 90, 30)


    @test_wrapper('Auto Reconnect')
    def le_auto_reconnect(self):
        """LE reconnection loop by reseting HID and check reconnection"""

        # Let the adapter pair, and connect to the target device first
        self.test_discover_device(self.device.address)
        # self.bluetooth_facade.is_discovering() doesn't work as expected:
        # crbug:905374
        # self.test_stop_discovery()
        self.bluetooth_facade.stop_discovery()
        time.sleep(self.TEST_SLEEP_SECS)
        self.test_pairing(self.device.address, self.device.pin, trusted=True)
        time.sleep(self.TEST_SLEEP_SECS)
        self.test_connection_by_adapter(self.device.address)

        total_reconnection_duration = 0
        loops = 3
        loop_cnt = 0
        for i in xrange(loops):
            # Restart and clear peer HID device
            self.restart_peers()
            start_time = time.time()

            # Verify that the device is reconnecting
            self.test_device_is_connected(self.device.address)
            end_time = time.time()
            time_diff = end_time - start_time

            if not bool(self.fails):
                total_reconnection_duration += time_diff
                loop_cnt += 1
                logging.info('%d: Reconnection duration %f sec', i, time_diff)
            else:
               break

        if not bool(self.fails):
            logging.info('Average Reconnection duration %f sec',
                         total_reconnection_duration/loop_cnt)

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
        self.quick_test_init(host)
        self.le_sanity_batch_run(num_iterations, test_name)
        self.quick_test_cleanup()
