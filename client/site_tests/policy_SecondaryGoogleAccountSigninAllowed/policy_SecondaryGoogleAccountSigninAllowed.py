# Copyright 2019 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import time

from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib import utils
from autotest_lib.client.cros.enterprise import enterprise_policy_base


class policy_SecondaryGoogleAccountSigninAllowed(
        enterprise_policy_base.EnterprisePolicyTest):
    """
    Tests the SecondaryGoogleAccountSigninAllowed policy in Chrome OS.
    If the policy is set to True/Not Set then users can sign in to Chrome
    with multiple accounts. If the policy is set to False then users won't
    be given an option to sign in with more than one account.

    """
    version = 1
    ACC_REGEX = '/Google Account/'

    def _check_secondary_login(self, case):
        """
        Open a new tab and try using the omnibox as a search box.

        @param case: policy value.

        """
        self.cr.browser.tabs[0].Navigate('https://www.gmail.com/')

        utils.poll_for_condition(
            lambda: self.ui.item_present(role='button',
                                         element=self.ACC_REGEX,
                                         isRegex=True),
            exception=error.TestError('Test page is not ready.'),
            timeout=30,
            sleep_interval=3)

        # It takes another few ms to make the button clickable.
        time.sleep(1)
        self.ui.doDefault_on_obj(role='button',
                                 obj=self.ACC_REGEX,
                                 isRegex=True)

        # This sleep is needed for the all available buttons to load.
        time.sleep(1)
        add_account_button = self.ui.item_present(role='link',
                                                  element='/Add account/',
                                                  isRegex=True)

        if case is False:
            if add_account_button:
                raise error.TestFail(
                    'Add account button is present and it should not be.')

        else:
            if not add_account_button:
                raise error.TestFail(
                    'Add account button is not present and it should be.')

    def run_once(self, case):
        """
        Setup and run the test configured for the specified test case.

        @param case: Name of the test case to run.

        """
        POLICIES = {'SecondaryGoogleAccountSigninAllowed': case}
        self.setup_case(user_policies=POLICIES, real_gaia=True)
        self.ui.start_ui_root(self.cr)
        self._check_secondary_login(case)
