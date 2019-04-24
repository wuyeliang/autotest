# Copyright 2019 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros.enterprise import enterprise_policy_base


class policy_PinnedLauncherApps(
        enterprise_policy_base.EnterprisePolicyTest):
    """
    Test the PinnedLauncherApps policy by pinning the default Google Photos
    application.

    This test will:
        Set the application to be pinned via the user policy.
        Verify the application is on the launch bar.
        Verify the application cannot be removed from the launch bar.
        Remove the application from the PinnedLauncherApps policy.
        Verify the application can be removed from the launch bar.

    """
    version = 1
    PINNED_TEXT = '/pinned/gi'
    EXT_NAME = 'Google Photos'

    def _remove_pinnedAps_policy(self):
        self.fake_dm_server.setup_policy(self._make_json_blob(
            user_policies={}))
        self.reload_policies()

    def _remove_pinned_app(self):
        """Removes the pinned app after the test is done."""
        self.ui.ext.EvaluateJavaScript('photos_app.showContextMenu()')
        self.ui.wait_for_ui_obj('Unpin')
        self.ui.doDefault_on_obj('Unpin')

        self.ui.wait_for_ui_obj(self.EXT_NAME, remove=True)

    def _check_launcher(self):
        """Runs the launcher test"""

        self.ui.wait_for_ui_obj(self.EXT_NAME)
        self.ui.ext.EvaluateJavaScript("""
            photos_app = root.find(
                {attributes: {name: "%s"}}
            )""" % (self.EXT_NAME))

        self.ui.ext.EvaluateJavaScript('photos_app.showContextMenu();')
        self.ui.wait_for_ui_obj(self.PINNED_TEXT, isRegex=True)

        if not self.ui.is_obj_restricted(self.PINNED_TEXT, isRegex=True):
            raise error.TestError(
                'App can be removed when pinned by policy!')

        self._remove_pinnedAps_policy()
        self._remove_pinned_app()

        if self.ui.item_present(self.EXT_NAME):
            raise error.TestError('Could not removed pinned app')

    def run_once(self):
        """
        Setup and run the test configured for the specified test case.

        @param case: Name of the test case to run.

        """
        pol = {'PinnedLauncherApps': ['hcglmfcclpfgljeaiahehebeoaiicbko']}
        self.setup_case(user_policies=pol, real_gaia=True)
        self.ui.start_ui_root(self.cr)
        self._check_launcher()
