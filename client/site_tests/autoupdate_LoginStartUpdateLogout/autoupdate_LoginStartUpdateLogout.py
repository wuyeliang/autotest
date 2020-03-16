# Copyright 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.common_lib.cros import chrome
from autotest_lib.client.cros.update_engine import update_engine_test

class autoupdate_LoginStartUpdateLogout(update_engine_test.UpdateEngineTest):
    """
    Logs in, starts an update, waits for a while, then logs out.

    This test is used as part of the server test autoupdate_Interruptions.

    """
    version = 1

    def run_once(self, update_url, progress_to_complete, full_payload=True):
        """The entry point for this test."""
        # Login as regular user. Start an update. Then Logout
        with chrome.Chrome(logged_in=True):
            self._check_for_update(update_url, critical_update=True,
                                   full_payload=full_payload)
            self._wait_for_progress(progress_to_complete)
