# Copyright 2019 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import time

from autotest_lib.client.common_lib import error
from autotest_lib.server.cros.faft.cr50_test import Cr50Test


class firmware_Cr50WPG3(Cr50Test):
    """Verify WP in G3."""
    version = 1

    WAIT_FOR_STATE = 10

    def cleanup(self):
        """Reenable servo wp."""
        try:
            if hasattr(self, '_start_fw_wp_vref'):
                self.servo.set_nocheck('fw_wp_state', self._start_fw_wp_state)
                self.servo.set_nocheck('fw_wp_vref', self._start_fw_wp_vref)
        finally:
            super(firmware_Cr50WPG3, self).cleanup()


    def run_once(self):
        """Verify WP in G3."""
        if self.check_cr50_capability(['wp_on_in_g3'], suppress_warning=True):
            raise error.TestNAError('WP not pulled up in G3')
        if 'servo_micro' not in self.servo.get_servo_version(True):
            raise error.TestNAError('Need servo flex to check WP')

        self.fast_open(True)

        self._start_fw_wp_state = self.servo.get('fw_wp_state')
        self._start_fw_wp_vref = self.servo.get('fw_wp_vref')
        # Stop forcing wp using servo, so we can set it with ccd.
        self.servo.set_nocheck('fw_wp_state', 'reset')
        self.servo.set_nocheck('fw_wp_vref', 'off')

        # disable write protect
        self.cr50.send_command('wp disable atboot')

        # Verify we can see it's disabled. This should always work. If it
        # doesn't, it may be a setup issue.
        servo_wp_s0 = self.servo.get('fw_wp_state')
        logging.info('servo wp: %s', servo_wp_s0)
        if servo_wp_s0 != 'off':
            raise error.TestError("WP isn't disabled in S0")

        self.faft_client.System.RunShellCommand('poweroff')
        time.sleep(self.WAIT_FOR_STATE)
        if hasattr(self, 'ec'):
            self.ec.send_command('hibernate')
            time.sleep(self.WAIT_FOR_STATE)

        servo_wp_g3 = self.servo.get('fw_wp_state')
        logging.info('servo wp: %s', servo_wp_g3)
        self._try_to_bring_dut_up()
        # Some boards don't power the EC_WP signal in G3, so it can't be
        # disabled by cr50 in G3.
        if servo_wp_g3 != 'off':
            raise error.TestFail("WP can't be disabled by Cr50 in G3")
