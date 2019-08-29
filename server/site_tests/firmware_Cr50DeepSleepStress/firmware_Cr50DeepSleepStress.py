# Copyright 2017 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import time

from autotest_lib.client.common_lib import error
from autotest_lib.server import autotest
from autotest_lib.server.cros.faft.firmware_test import FirmwareTest


class firmware_Cr50DeepSleepStress(FirmwareTest):
    """Verify cr50 deep sleep after running power_SuspendStress.

    Cr50 should enter deep sleep every suspend. Verify that by checking the
    idle deep sleep count.

    @param suspend_count: The number of times to reboot or suspend the device.
    @param reset_type: a str with the cycle type: 'mem' or 'reboot'
    """
    version = 1

    SLEEP_DELAY = 20
    MIN_RESUME = 15
    MIN_SUSPEND = 15
    MEM = 'mem'

    def initialize(self, host, cmdline_args, suspend_count, reset_type):
        """Make sure the test is running with access to the cr50 console"""
        super(firmware_Cr50DeepSleepStress, self).initialize(host, cmdline_args)
        if not hasattr(self, 'cr50'):
            raise error.TestNAError('Test can only be run on devices with '
                                    'access to the Cr50 console')

        if self.servo.running_through_ccd():
            raise error.TestNAError('deep sleep tests can only be run with a '
                                    'servo flex')

        # Reset the device
        self.servo.get_power_state_controller().reset()

        # Save the original version, so we can make sure cr50 doesn't rollback.
        self.original_cr50_version = self.cr50.get_active_version_info()


    def check_cr50_version(self, expected_version):
        """Return an error message if the version changed running the test."""
        version = self.cr50.get_active_version_info()
        logging.info('running %s', version)

        if version != expected_version:
            raise error.TestFail('version mismatch: expected %s got %s' %
                                 (expected_version, version))


    def run_reboots(self, suspend_count):
        """Reboot the device the requested number of times

        @param suspend_count: the number of times to reboot the device.
        """
        original_mainfw_type = 'developer' if self.checkers.crossystem_checker(
                {'mainfw_type': 'developer'}) else 'normal'
        # Disable CCD so Cr50 can enter deep sleep
        self.cr50.ccd_disable()
        self.cr50.clear_deep_sleep_count()
        self.check_cr50_deep_sleep(0)

        for i in range(suspend_count):
            # Power off the device
            self.servo.get_power_state_controller().power_off()
            time.sleep(self.MIN_SUSPEND)

            # Power on the device
            self.servo.power_short_press()
            time.sleep(self.MIN_RESUME)

            self.check_cr50_deep_sleep(i + 1)

            # Make sure it didn't boot into a different mode
            self.check_state((self.checkers.crossystem_checker,
                              {'mainfw_type': original_mainfw_type}))


    def _dut_is_responsive(self, host):
        """Returns True if the DUT eventually responds"""
        return host.ping_wait_up(180)


    def wait_for_client_after_changing_ccd(self, host, enable):
        """Change CCD and wait for client"""
        if enable:
            self.cr50.ccd_enable()
        else:
            self.cr50.ccd_disable()
        # power suspend stress needs to ssh into the DUT. If ethernet goes
        # down, raise a test error, so we can tell the difference between
        # dts ethernet issues and the dut going down during the suspend stress.
        if self._dut_is_responsive(host):
            return
        logging.info('DUT is not pingable after disabling ccd')

        # TODO(b/135147658): Raise an error once CCD disable is fixed.
        logging.info('Resetting DUT')
        self.servo.get_power_state_controller().reset()
        if not self._dut_is_responsive(host):
            raise error.TestError('DUT is not pingable after %sabling ccd' %
                                  ('en' if enable else 'dis'))


    def run_suspend_resume(self, host, suspend_count):
        """Suspend the device the requested number of times

        @param host: the host object representing the DUT.
        @param suspend_count: the number of times to suspend the device.
        """
        # Disable CCD so Cr50 can enter deep sleep
        self.wait_for_client_after_changing_ccd(host, False)
        self.cr50.clear_deep_sleep_count()
        self.check_cr50_deep_sleep(0)
        client_at = autotest.Autotest(host)
        # Duration is set to 0, because it is required but unused when
        # iterations is given.
        client_at.run_test('power_SuspendStress', tag='idle',
                           duration=0,
                           min_suspend=self.MIN_SUSPEND,
                           min_resume=self.MIN_RESUME,
                           check_connection=False,
                           suspend_iterations=suspend_count,
                           suspend_state=self.MEM)


    def check_cr50_deep_sleep(self, suspend_count):
        """Verify cr50 has entered deep sleep the correct number of times.

        Also print ccdstate and sleepmask output to get some basic information
        about the cr50 state.
        - sleepmask will show what may be preventing cr50 from entering sleep.
        - ccdstate will show what cr50 thinks the AP state is. If the AP is 'on'
          cr50 won't enter deep sleep.
        All of these functions log the state, so no need to log the return
        values.

        @param suspend_count: The number of suspends.
        @raises TestFail if there's an issue with the deep sleep count or if
                         cr50 did a hard reboot.
        """
        exp_count = suspend_count if self._enters_deep_sleep else 0
        act_count = self.cr50.get_deep_sleep_count()
        logging.info('suspend %d: deep sleep count %d', act_count, exp_count)
        self.cr50.get_sleepmask()
        self.cr50.get_ccdstate()
        reset_cause = self.cr50.get_reset_cause()

        if exp_count and (not act_count or 'hibernate' not in reset_cause):
            raise error.TestFail('Issue with cr50 suspend')

        if exp_count != act_count:
            raise error.TestFail('After %d suspends cr50 entered deep sleep'
                                 '%d times' % (exp_count, act_count))


    def run_once(self, host, suspend_count, reset_type):
        """Verify deep sleep after suspending for the given number of cycles

        The test either suspends to s3 or reboots the device depending on
        reset_type. There are two valid reset types: mem and reboot. The test
        will make sure that the device is off or in s3 long enough to ensure
        Cr50 should be able to enter deep sleep. At the end of the test, it
        checks that Cr50 entered deep sleep the same number of times it
        suspended.

        @param host: the host object representing the DUT.
        @param suspend_count: The number of cycles to suspend or reboot the
                device.
        @param reset_type: a str with the cycle type: 'mem' or 'reboot'
        """
        if self.MIN_SUSPEND + self.MIN_RESUME < self.SLEEP_DELAY:
            logging.info('Minimum suspend-resume cycle is %ds. This is '
                         'shorter than the Cr50 idle timeout. Cr50 may not '
                         'enter deep sleep every cycle',
                         self.MIN_SUSPEND + self.MIN_RESUME)
        if not suspend_count:
            raise error.TestFail('Need to provide non-zero suspend_count')

        # x86 devices should suspend once per reset. ARM will only suspend
        # if the device enters s5.
        if reset_type == 'reboot':
            self._enters_deep_sleep = True
        else:
            is_arm = self.check_ec_capability(['arm'], suppress_warning=True)
            self._enters_deep_sleep = not is_arm

        if reset_type == 'reboot':
            self.run_reboots(suspend_count)
        elif reset_type == 'mem':
            self.run_suspend_resume(host, suspend_count)
        else:
            raise error.TestNAError('Invalid reset_type. Use "mem" or "reboot"')

        self.cr50.dump_nvmem()
        self.check_cr50_deep_sleep(suspend_count)
        self.check_cr50_version(self.original_cr50_version)
        # Reenable CCD
        self.wait_for_client_after_changing_ccd(host, True)
