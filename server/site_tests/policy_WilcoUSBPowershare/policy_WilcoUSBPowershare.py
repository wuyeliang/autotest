# Copyright (c) 2019 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import logging
import time

from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros import tpm_utils
from autotest_lib.server import autotest
from autotest_lib.server import test


class policy_WilcoUSBPowershare(test.test):
    """Test that verifies DeviceUsbPowerShareEnabled policy.

    If the policy is enabled or not set, USB provides power when device is off.
    If the policy is disabled, USB does not provide power when device is off.

    This test uses the servo board to interact with the device once it's
    powered off.

    Note: This test only checks the behavior of the device when it is off,
    it doesn't do the part of the policy when the device is asleep.

    This test has to run on a Wilco device.
    """
    version = 1


    def clear_tpm_if_owned(self):
        """Clear the TPM only if device is already owned."""
        tpm_status = tpm_utils.TPMStatus(self.host)
        logging.info('TPM status: %s', tpm_status)
        if tpm_status['Owned']:
            logging.info('Clearing TPM because this device is owned.')
            tpm_utils.ClearTPMOwnerRequest(self.host)


    def initialize(self, host):
        """Initialize DUT for testing."""
        pass


    def cleanup(self):
        """Clean up DUT."""
        self.clear_tpm_if_owned()


    def _get_average_power_output(self):
        """Gets the average of the list.

        When using the vbus_power command with the DeviceUsbPowerShareEnabled
        policy enabled, it sometimes still returns 0.0. This is why it's safer
        to run the command multiple times instead of once.

        """
        vbus_list = []
        t_end = time.time() + 7
        while time.time() < t_end:
            vbus_list.append(self.host.servo.vbus_power_get())
            time.sleep(1)
        return sum(vbus_list)/len(vbus_list)


    def run_once(self, client_test, host, case):
        """Run the test.

        @param client_test: the name of the Client test to run.
        @param case: the case to run for the given Client test.
        """
        self.host = host
        self.clear_tpm_if_owned()

        self.autotest_client = autotest.Autotest(self.host)
        self.autotest_client.run_test(
            client_test, case=case, check_client_result=False)

        # Turns off the device.
        self.host.servo.power_key('long_press')
        # This makes sure the device is really off before checking power.
        time.sleep(10)

        vbus_average_power = self._get_average_power_output()

        # Bring device back up. I tried using power_key method to power up the
        # device but could not consisnently get it to work. pwr_button method
        # works all the time.
        self.host.servo.pwr_button()
        time.sleep(1)
        self.host.servo.pwr_button('release')

        if case is False:
            if vbus_average_power > 0.0:
                raise error.TestFail('USB is providing power, it should not.')
        else:
            if vbus_average_power is 0.0:
                raise error.TestFail('USB is not providing power, it should.')
