# Copyright 2019 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib import utils

from autotest_lib.client.common_lib.cros import retry

from autotest_lib.client.cros.enterprise import enterprise_policy_base

from py_utils import TimeoutException


class policy_WilcoOnNonWilcoDevice(
        enterprise_policy_base.EnterprisePolicyTest):
    """
    Test for looping through Wilco policies on a non wilco device.

    Setting Wilco policies on a non Wilco device should not cause a crash.

    """
    version = 1

    @retry.retry(TimeoutException, timeout_min=5, delay_sec=10)
    def _run_setup_case(self, tests):
        self.setup_case(
            device_policies={
                tests[0]['Policy_Name']: tests[0]['Policy_Value']},
            enroll=True,
            extra_chrome_flags=['--user-always-affiliated'])

    def _update_policy_page(self):
        policy_tab = self.navigate_to_url(self.CHROME_POLICY_PAGE)
        reload_button = "document.querySelector('button#reload-policies')"
        policy_tab.ExecuteJavaScript("%s.click()" % reload_button)

    def run_once(self, tests):
        """
        Entry point of this test.

        @param case: True, False, or None for the value of the policy.

        """
        self._run_setup_case(tests)
        tests.pop(0)
        for test in tests:
            self.fake_dm_server.setup_policy(self._make_json_blob(
                device_policies={test['Policy_Name']: test['Policy_Value']}))
            self._update_policy_page()
            utils.poll_for_condition(
                lambda: self._get_policy_value_from_new_tab(
                    test['Policy_Name']) == test['Policy_Value'],
                exception=error.TestFail('Policy value not updated.'),
                timeout=10,
                sleep_interval=1)
