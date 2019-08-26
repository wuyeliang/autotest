# Copyright 2019 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import time

from autotest_lib.client.common_lib import error
from autotest_lib.server.cros.faft.cr50_test import Cr50Test


class firmware_Cr50RddG3(Cr50Test):
    """Verify Rdd in G3."""
    version = 1

    WAIT_FOR_STATE = 10

    def rdd_is_connected(self):
        """Return True if Cr50 detects Rdd."""
        time.sleep(2)
        return self.cr50.get_ccdstate()['Rdd'] == 'connected'

    def run_once(self):
        """Verify Rdd in G3."""
        if not hasattr(self, 'ec'):
            raise error.TestNAError('Board does not have an EC.')
        if self.check_cr50_capability(['rdd_leakage']):
            raise error.TestNAError('Leakage on the rdd signals breaks '
                                    'detection in G3')

        self.servo.set_servo_v4_dts_mode('on')
        if not self.rdd_is_connected():
            raise error.TestNAError('Cr50 does not detect Rdd with dts mode on')

        self.servo.set_servo_v4_dts_mode('off')

        if self.rdd_is_connected():
            raise error.TestFail('Cr50 detects Rdd with dts mode off')

        self.faft_client.System.RunShellCommand('poweroff')
        time.sleep(self.WAIT_FOR_STATE)
        self.ec.send_command('hibernate')

        time.sleep(self.WAIT_FOR_STATE)
        rdd_connected = self.rdd_is_connected()

        self.servo.set_servo_v4_dts_mode('on')
        self._try_to_bring_dut_up()

        if rdd_connected:
            raise error.TestFail('Rdd is broken in G3')
