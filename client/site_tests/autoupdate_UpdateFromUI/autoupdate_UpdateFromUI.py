# Copyright 2020 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.common_lib import autotemp
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros import chrome
from autotest_lib.client.cros.update_engine import nebraska_wrapper
from autotest_lib.client.cros.update_engine import update_engine_test
from telemetry.core import exceptions

class autoupdate_UpdateFromUI(update_engine_test.UpdateEngineTest):
    """Starts an update from the Chrome OS Settings app. """
    version = 1


    def initialize(self):
        """Test setup."""
        super(autoupdate_UpdateFromUI, self).initialize()
        self._clear_custom_lsb_release()


    def cleanup(self):
        """Test cleanup. Clears the custom lsb-release used by the test. """
        self._clear_custom_lsb_release()
        super(autoupdate_UpdateFromUI, self).cleanup()


    def run_once(self, image_url):
        """
        Tests that a Chrome OS software update can be completed from the UI.

        @param image_url: The payload url to use.

        """
        metadata_dir = autotemp.tempdir()
        self._get_payload_properties_file(image_url, metadata_dir.name)
        base_url = ''.join(image_url.rpartition('/')[0:2])
        with nebraska_wrapper.NebraskaWrapper(
                log_dir=self.resultsdir,
                update_metadata_dir=metadata_dir.name,
                update_payloads_address=base_url) as nebraska:
            with chrome.Chrome(autotest_ext=True) as cr:
                # Need to create a custom lsb-release file to point the UI
                # update button to Nebraska instead of the default update
                # server.
                self._create_custom_lsb_release(nebraska.get_update_url())

                # Go to the OS settings page and check for an update.
                tab = cr.browser.tabs[0]
                tab.Navigate('chrome://os-settings/help')
                tab.WaitForDocumentReadyStateToBeComplete()
                try:
                    tab.EvaluateJavaScript('settings.AboutPageBrowserProxyImpl'
                                           '.getInstance().requestUpdate()')
                except exceptions.EvaluateException:
                    raise error.TestFail(
                        'Failed to find and click Check For Updates button.')
            # Sign out of Chrome and wait for the update to complete.
            # If we waited for the update to complete and then logged out
            # the DUT will auto-reboot and the client test cannot return.
            self._wait_for_update_to_complete()
