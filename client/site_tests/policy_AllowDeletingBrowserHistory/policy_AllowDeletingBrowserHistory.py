# Copyright 2019 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros.enterprise import enterprise_policy_base

COMMON_ELEMENTS_ONE = "['settings-ui', '#main', 'settings-basic-page', "
COMMON_ELEMENTS_TWO = (
    "'settings-privacy-page', 'settings-clear-browsing-data-dialog', ")
ADVANCED_TAB = (
    COMMON_ELEMENTS_ONE + COMMON_ELEMENTS_TWO + "'#advancedTabTitle']")
BROWSER_HISTORY_CHECK = (
    COMMON_ELEMENTS_ONE + COMMON_ELEMENTS_TWO + "'#browsingCheckbox'," +
    " '#outerRow']")
DOWNLOAD_HISTORY_CHECK = (
    COMMON_ELEMENTS_ONE + COMMON_ELEMENTS_TWO + "'#downloadCheckbox'," +
    " '#outerRow']")

ARIA_DISABLED = 'aria-disabled="true"'
ARIA_ENABLED = 'aria-disabled="false"'
ARIA_CHECKED = 'aria-checked="true"'
ARIA_UNCHECKED = 'aria-checked="false"'
DISABLED = 'disabled=""'

# /deep/ CSS query has been removed from ShadowDOM. The only way to access
# elements now is to recursively query in each shadowRoot.
SHADOWROOT_SCRIPT = """
function deepQuerySelectorAll(root, targetQuery) {
    const elems = Array.prototype.slice.call(root.querySelectorAll(targetQuery[0]));
    const remaining = targetQuery.slice(1);
    if (remaining.length === 0) {
        return elems;
    }

    let res = [];
    for (let i = 0; i < elems.length; i++) {
        if (elems[i].shadowRoot) {
            res = res.concat(deepQuerySelectorAll(elems[i].shadowRoot, remaining));
        }
    }
    return res;
};
var testing_element = deepQuerySelectorAll(document, %s);
testing_element[0].%s;
"""


class policy_AllowDeletingBrowserHistory(
        enterprise_policy_base.EnterprisePolicyTest):
    """
    Tests the AllowDeletingBrowserHistory policy in Chrome OS.
    If the policy is set to True/Not Set then the user will be able to delete
    browse and download histories.
    If the policy is set to False then the user will not be able to
    delete browse and download histories.

    """
    version = 1

    def _modify_shadowroot_script(self, element, action):
        script_to_execute = SHADOWROOT_SCRIPT % (element, action)
        return script_to_execute

    def _click_advanced_tab(self, active_tab):
        advanced_tab_content = self._modify_shadowroot_script(
            ADVANCED_TAB, "innerHTML")
        utils.poll_for_condition(
            lambda: self.check_page_readiness(
                active_tab, advanced_tab_content),
            exception=error.TestFail('Advanced tab is not ready.'),
            timeout=5,
            sleep_interval=1)

        click_advanced_tab = self._modify_shadowroot_script(
            ADVANCED_TAB, "click()")
        active_tab.EvaluateJavaScript(click_advanced_tab)

    def _get_browser_history_content(self, active_tab):
        browser_history_content = self._modify_shadowroot_script(
            BROWSER_HISTORY_CHECK, "innerHTML")
        utils.poll_for_condition(
            lambda: self.check_page_readiness(
                active_tab, browser_history_content),
            exception=error.TestFail(
                'Browser history content not loaded.'),
            timeout=5,
            sleep_interval=1)

        browsing_history = active_tab.EvaluateJavaScript(
            browser_history_content)
        return browsing_history

    def _get_download_history_content(self, active_tab):
        download_history_content = self._modify_shadowroot_script(
            DOWNLOAD_HISTORY_CHECK, "innerHTML")
        download_history = active_tab.EvaluateJavaScript(
            download_history_content)
        return download_history

    def _check_safety_browsing_page(self, case):
        """
        Opens a new chrome://settings/clearBrowserData page and checks
        if the browse and download histories are deletable.

        @param case: policy value.

        """
        active_tab = self.navigate_to_url("chrome://settings/clearBrowserData")

        self._click_advanced_tab(active_tab)

        browsing_history = self._get_browser_history_content(active_tab)

        download_history = self._get_download_history_content(active_tab)

        if case is False:
            if (ARIA_DISABLED and ARIA_UNCHECKED and DISABLED not in
                browsing_history) and (ARIA_ENABLED and ARIA_CHECKED and
                DISABLED not in download_history):
                    raise error.TestFail('User is able to delete history.')

        else:
            if (ARIA_ENABLED and ARIA_CHECKED not in
                browsing_history) and (ARIA_ENABLED and ARIA_CHECKED not in
                download_history):
                    raise error.TestFail('User is unable to delete history.')


    def run_once(self, case):
        """
        Setup and run the test configured for the specified test case.

        @param case: Name of the test case to run.

        """
        POLICIES = {'AllowDeletingBrowserHistory': case}
        self.setup_case(user_policies=POLICIES)
        self._check_safety_browsing_page(case)
