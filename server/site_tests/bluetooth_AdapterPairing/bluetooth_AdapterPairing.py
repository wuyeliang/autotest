# Copyright 2016 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""
Server side bluetooth tests on adapter pairing and connecting to a bluetooth
HID device.
"""

import logging

from autotest_lib.client.common_lib import error
from autotest_lib.server.cros.bluetooth import bluetooth_adapter_pairing_tests
from autotest_lib.server.cros.multimedia import remote_facade_factory



class bluetooth_AdapterPairing(
        bluetooth_adapter_pairing_tests.BluetoothAdapterPairingTests):
    """Server side bluetooth adapter pairing and connecting to bluetooth device

    This test tries to verify that the adapter of the DUT could
    pair and connect to a bluetooth HID device correctly.

    """


    def run_once(self, host, device_type, num_iterations=1, min_pass_count=1,
                 pairing_twice=False, suspend_resume=False, reboot=False):
        """Running Bluetooth adapter tests about pairing to a device.

        @param host: the DUT, usually a chromebook
        @param device_type : the bluetooth HID device type, e.g., 'MOUSE'
        @param num_iterations: the number of rounds to execute the test
        @param min_pass_count: the minimal pass count to pass this test
        @param pairing_twice: True if the host tries to pair the device
                again after the paired device is removed.
        @param suspend_resume: True if the host suspends/resumes after
                pairing.
        @param reboot: True if the host reboots after pairing.

        """
        self.host = host
        factory = remote_facade_factory.RemoteFacadeFactory(host)
        self.bluetooth_facade = factory.create_bluetooth_hid_facade()
        self.input_facade = factory.create_input_facade()
        self.check_chameleon()

        pass_count = 0
        self.total_fails = {}
        for iteration in xrange(1, num_iterations + 1):
            self.fails = []

            # Get the device object and query some important properties.
            device = self.get_device(device_type)
            self.pairing_test(device, self.test_mouse_left_click,
                              pairing_twice, suspend_resume, reboot)


            if bool(self.fails):
                self.total_fails['Round %d' % iteration] = self.fails
            else:
                pass_count += 1

            fail_count = iteration - pass_count
            logging.info('===  (pass = %d, fail = %d) / total %d  ===\n',
                         pass_count, fail_count, num_iterations)

        if pass_count < min_pass_count:
            raise error.TestFail(self.total_fails)
