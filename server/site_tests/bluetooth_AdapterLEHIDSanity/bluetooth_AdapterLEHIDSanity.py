# Copyright 2019 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""A package of of Bluetooth LE HID sanity tests"""

import logging
import time

from autotest_lib.client.common_lib import error
from autotest_lib.server.cros.bluetooth import bluetooth_adapter_tests
from autotest_lib.server.cros.multimedia import remote_facade_factory


class bluetooth_AdapterLEHIDSanity(
        bluetooth_adapter_tests.BluetoothAdapterTests):
    """A package of Bluetooth LE HID sanity tests

    This test is written as a package of tests in order to reduce test time,
    since auto-test ramp up time is costy.
    Between each two test, the method _cleanup_and_restart is called to
    restart both peer and DUT. The HID device type can be selected per test
    using this method.
    At the end of each test, the method _update_test_result
    is called to track test results.
    At the end of the package, _print_test_results is called to print a summary
    of the test results.
    """

    hid_results = []
    pass_count = 0
    fail_count = 0

    # Some delay is needed between tests. TODO(yshavit): investigate and remove
    TEST_SLEEP_SECS = 3

    def _update_test_result(self, test_name):
        """Log and track the test results"""
        if not bool(self.fails):
            result_msg = ('PASSED | Iteration: ' + str(self.iteration) +
                          ' Test: ' + test_name)
            self.pass_count += 1
        else:
            result_msg = ('FAIL   | Iteration: ' + str(self.iteration) +
                          ' Test: ' + test_name)
            self.fail_count += 1
        logging.info(result_msg)
        self._print_delimiter()
        self.hid_results.append(result_msg)


    def _print_delimiter(self):
        logging.info('===================================================')


    def _test_connect_disconnect_loop(self):
        """Run connect/disconnect loop initiated by DUT.
           The test also checks that there are no undesired
           reconnections.

           TODO(ysahvit) - add connection creation attempts
                           initiated by HID device
        """

        test_name = 'Connect Disconnect Loop'
        self._cleanup_and_restart('BLE_MOUSE', test_name)

        # First pair and disconnect, to emulate real life scenario
        self.test_discover_device(self.device.address)
        # self.bluetooth_facade.is_discovering() doesn't work as expected:
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

        self._update_test_result(test_name)


    def _test_mouse_reports(self):
        """Run all bluetooth mouse reports tests"""

        test_name = 'Mouse Reports'
        self._cleanup_and_restart('BLE_MOUSE', test_name)

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

        self._update_test_result(test_name)


    def _test_auto_reconnect(self):
        """LE reconnection loop by reseting HID and check reconnection"""

        test_name = 'Auto Reconnect'
        self._cleanup_and_restart('BLE_MOUSE', test_name)

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
            self._restart_hid('BLE_MOUSE')
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

        self._update_test_result(test_name)


    def _restart_hid(self, device_type):
        """Restart and clear peer HID device"""

        # Restart the link to HID device
        logging.info('Restarting HID device...')
        self.cleanup()
        self.device = self.get_device(device_type)

    def _cleanup_and_restart(self, device_type, test_name):
        """Restart and clear peer device and DUT Bluetooth adapter"""

        logging.info('Cleanning up and restarting towards next test...')
        # Restart and clear peer HID device
        self._restart_hid(device_type)

        # Disconnect the device, and remove the pairing.
        self.bluetooth_facade.disconnect_device(self.device.address)
        device_is_paired = self.bluetooth_facade.device_is_paired(
                self.device.address)
        if device_is_paired:
            self.bluetooth_facade.remove_device_object(
                    self.device.address)

        # Reset the adapter
        self.test_reset_on_adapter()

        # Initialize bluetooth_adapter_tests class (also clears self.fails)
        self.initialize()
        time.sleep(self.TEST_SLEEP_SECS)
        self._print_delimiter()
        logging.info('Starting test: %s', test_name)


    def _print_test_results(self):
        """Print test results summary of LE HID tests"""
        logging.info('Test Summary: total pass %d, total fail %d',
                     self.pass_count, self.fail_count)
        for result in self.hid_results:
            logging.info(result)
        self._print_delimiter();
        if self.fail_count > 0:
            logging.error('===> Test Failed! More than one failure')
            self._print_delimiter();
            raise error.TestFail(self.hid_results)
        else:
           logging.info('===> Test Passed! zero failures')
           self._print_delimiter();


    def run_once(self, host, num_iterations=1):
        """Run the package of Bluetooth LE HID sanity tests

        @param host: the DUT, usually a chromebook
        @param num_iterations: the number of rounds to execute the test

        """
        self.host = host
        factory = remote_facade_factory.RemoteFacadeFactory(host)
        self.bluetooth_facade = factory.create_bluetooth_hid_facade()
        self.input_facade = factory.create_input_facade()
        self.check_chameleon()

        self._print_delimiter();
        logging.info('Starting LE HID Sanity Tests')
        # Main loop running all LE HID sanity tests
        for iter in xrange(num_iterations):

            self.iteration = iter

            self._test_connect_disconnect_loop()
            self._test_mouse_reports()
            self._test_auto_reconnect()

        self._print_test_results()
