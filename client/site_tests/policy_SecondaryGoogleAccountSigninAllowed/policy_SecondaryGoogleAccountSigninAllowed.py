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

    def _find_add_account_button(self, ext):
        add_account_button = ext.EvaluateJavaScript("""
        var root;
        chrome.automation.getDesktop(r => root = r);
        root.findAll({attributes: {
            role: "link", name: /Add account/}}).map(node => node.name);
        """)
        return add_account_button

    def _click_google_account_button(self, ext):
        # Click the Google account button in gmail.
        ext.ExecuteJavaScript("""
        var root;
        chrome.automation.getDesktop(r => root = r);
        """)
        # This sleep is needed for the all available buttons to load.
        time.sleep(1)
        ext.ExecuteJavaScript("""
        var launcher = root.find({
            attributes: {role: "button", name: /Google Account:/}});
        launcher.doDefault()
        """)

    def _check_for_google_account_button(self, ext):
        try:
            g_account_button = ext.EvaluateJavaScript("""
            var root;
            chrome.automation.getDesktop(r => root = r);
            g_account = root.find({
                attributes: {role: "button", name: /Google Account:/}});
            g_account;
            """)
            return True
        except:
            return False

    def _check_secondary_login(self, case):
        """
        Open a new tab and try using the omnibox as a search box.

        @param case: policy value.

        """
        ext = self.cr.autotest_ext
        self.cr.browser.tabs[0].Navigate('https://www.gmail.com/')

        utils.poll_for_condition(
            lambda: self._check_for_google_account_button(ext),
            exception=error.TestError('Test page is not ready.'),
            timeout=30,
            sleep_interval=3)

        self._click_google_account_button(ext)

        # This sleep is needed for the all available buttons to load.
        time.sleep(1)
        add_account_button = self._find_add_account_button(ext)

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
        self.setup_case(user_policies=POLICIES)
        self._check_secondary_login(case)
