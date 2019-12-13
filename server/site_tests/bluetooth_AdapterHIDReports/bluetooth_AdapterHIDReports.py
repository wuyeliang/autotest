# Copyright 2016 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Server side bluetooth tests about sending bluetooth HID reports."""

import logging

from autotest_lib.client.common_lib import error
from autotest_lib.server.cros.bluetooth import \
     bluetooth_adapter_hidreports_tests
from autotest_lib.server.cros.multimedia import remote_facade_factory


class bluetooth_AdapterHIDReports(
        bluetooth_adapter_hidreports_tests.BluetoothAdapterHIDReportTests):
    """Server side bluetooth tests about sending bluetooth HID reports.

    This test tries to send HID reports to a DUT and verifies if the DUT
    could receive the reports correctly. For the time being, only bluetooth
    mouse events are tested. Bluetooth keyboard events will be supported
    later.
    """


    def run_once(self, host, device_type, num_iterations=1, min_pass_count=1,
                 suspend_resume=False, reboot=False):
        """Running Bluetooth HID reports tests.

        @param host: the DUT, usually a chromebook
        @param device_type : the bluetooth HID device type, e.g., 'MOUSE'
        @param num_iterations: the number of rounds to execute the test
        @param min_pass_count: the minimal pass count to pass this test

        """
        self.host = host
        factory = remote_facade_factory.RemoteFacadeFactory(host)
        self.bluetooth_facade = factory.create_bluetooth_hid_facade()
        self.input_facade = factory.create_input_facade()
        self.check_chameleon()

        if (device_type == 'KEYBOARD' and
            self.host.chameleon.get_platform() != 'RASPI'):
                logging.info("KEYBOARD device is not supported on Fizz peer")
                raise error.TestNAError("b/146231141 KEYBOARD test is not"
                               " supported on  Fizz peer devices")

        pass_count = 0
        self.total_fails = {}
        for iteration in xrange(1, num_iterations + 1):
            self.fails = []

            # Get the bluetooth device object.
            device = self.get_device(device_type)

            self.run_hid_reports_test(device, suspend_resume, reboot)
            if bool(self.fails):
                self.total_fails['Round %d' % iteration] = self.fails
            else:
                pass_count += 1

            fail_count = iteration - pass_count
            logging.info('===  (pass = %d, fail = %d) / total %d  ===\n',
                         pass_count, fail_count, num_iterations)

        if pass_count < min_pass_count:
            raise error.TestFail(self.total_fails)
