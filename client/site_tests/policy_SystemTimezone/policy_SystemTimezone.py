# Copyright 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib import utils
from autotest_lib.client.cros.enterprise import enterprise_policy_base
import time


class policy_SystemTimezone(
        enterprise_policy_base.EnterprisePolicyTest):
    """
    Test effect of SystemTimezone policy on Chrome OS behavior.

    This will test that both the timezone can be set by the policy, and that
    when the policy is not set a user can change the settings.

    """
    version = 1
    POLICY_NAME = 'SystemTimezone'

    def _is_timezone_selectable(self):
        """
        Check if the timezone is selectable via the UI. If the timezone
        dropdown is greyed out, then it is not selectable.

        @returns: True if dropdown is usable, False if not.

        """
        SETTINGS_URL = "chrome://settings/dateTime/timeZone"
        tab = self.navigate_to_url(SETTINGS_URL)
        tab.WaitForDocumentReadyStateToBeComplete()

        self.ui.wait_for_ui_obj('Choose from list')
        self.ui.doDefault_on_obj('Choose from list')

        # Give the dropdown a second to load.
        time.sleep(1)

        return not self.ui.is_obj_restricted('Time zone', role='popUpButton')

    def _set_timezone(self):
        """Sets the timezone to the first option in the list."""
        self.ui.doDefault_on_obj('/(UTC-10:00)/',
                                 isRegex=True,
                                 role='menuListOption')

    def _test_timezone(self, expected):
        """
        Verify the Timezone set on the device.

        This is done by running the UNIX date command (%z) and verifying the
        timezone matches the expected result.

        """
        def check_timezone(expected):
            return utils.system_output('date +%z') == expected

        utils.poll_for_condition(
            lambda: check_timezone(expected),
            exception=error.TestFail('Time zone was not set! Expected {}'
                                     .format(expected)),
            timeout=5,
            sleep_interval=1,
            desc='Polling for timezone change')

    def set_timezones(self):
        """
        Iterate through different time zones, and verify they can be set.

        This is specifically being done to verify the timezone via seeing
        the reported timezone is changing, and not just on the first one via
        luck.

        """
        cases = [{'policy': 'America/Costa_Rica', 'expected': '-0600'},
                 {'policy': 'Asia/Kathmandu', 'expected': '+0545'}]

        for setting in cases:
            policy_value = setting['policy']
            expected = setting['expected']
            policies = {self.POLICY_NAME: policy_value}
            self.setup_case(device_policies=policies, enroll=True)

            self.ui.start_ui_root(self.cr)
            # Logout so the policy can take effect
            if self._is_timezone_selectable():
                raise error.TestError(
                    'Timezone is selectable when the policy is set')
            self.log_out_via_keyboard()
            self._test_timezone(expected)

            # The device needs a bit of time to reliably clean up between
            # iterations.
            time.sleep(20)

    def set_empty_timezone(self):
        """
        Set and verify the timezone when the policy is empty.

        This will be done by adjusting the setting on the ://settings page,
        and verfying the date reported. Additionally log out, then verify the
        timezone matches as well.

        """

        policies = {self.POLICY_NAME: ''}
        self.setup_case(device_policies=policies, enroll=True)
        self.ui.start_ui_root(self.cr)

        # Check if the Timezone is changable in the settings.
        if not self._is_timezone_selectable():
            raise error.TestError('User cannot change timezone')
        self._set_timezone()

        self._test_timezone('-1000')

        self.log_out_via_keyboard()
        self._test_timezone('-1000')

    def run_once(self, case):
        """
        Run the proper test based on the selected case.

        @param case: bool or None, value of the test case to run.

        """
        if case:
            self.set_timezones()
        else:
            self.set_empty_timezone()
