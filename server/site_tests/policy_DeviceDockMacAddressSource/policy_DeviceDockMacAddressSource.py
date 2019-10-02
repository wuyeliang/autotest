# Copyright (c) 2019 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import logging

from autotest_lib.client.common_lib.cros import tpm_utils
from autotest_lib.server import autotest
from autotest_lib.server import test


class policy_DeviceDockMacAddressSource(test.test):
    """Test that verifies DeviceDockMacAddressSource policy.

    If the policy is set to 1, dock will grab the designated mac address from
    the device.
    If the policy is set to 2, dock mac address will match the device mac.
    If the policy is set to 3, dock will use its own mac address.

    This test has to run on a Wilco device.

    The way the test is currently setup is: ethernet cable is plugged into the
    device and dock is not plugged into the internet directly. This might
    change later on.
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


    def run_once(self, client_test, host, case):
        """Run the test.

        @param client_test: the name of the Client test to run.
        @param case: the case to run for the given Client test.
        """
        self.host = host
        self.clear_tpm_if_owned()

        self.autotest_client = autotest.Autotest(self.host)
        self.autotest_client.run_test(client_test, case=case)

        self.host.reboot()

        self.autotest_client.run_test(
            client_test, case=case, enroll=False, check_mac=True)
