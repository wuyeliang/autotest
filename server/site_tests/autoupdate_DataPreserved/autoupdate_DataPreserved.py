# Copyright 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import urlparse

from autotest_lib.server.cros.update_engine import update_engine_test


class autoupdate_DataPreserved(update_engine_test.UpdateEngineTest):
    """Ensure user data and preferences are preserved during an update."""

    version = 1
    _USER_DATA_TEST = 'autoupdate_UserData'


    def cleanup(self):
        self._save_extra_update_engine_logs()
        super(autoupdate_DataPreserved, self).cleanup()


    def run_once(self, full_payload=True, job_repo_url=None):
        """
        Tests that users timezone, input methods, and downloads are preserved
        during an update.

        @param full_payload: True for a full payload. False for delta.
        @param job_repo_url: Used for debugging locally. This is used to figure
                             out the current build and the devserver to use.
                             The test will read this from a host argument
                             when run in the lab.

        """
        update_url = self.get_update_url_for_test(job_repo_url,
                                                  full_payload=full_payload)

        # Split the URL into server and port.
        url_split = urlparse.urlsplit(update_url)
        server, port = url_split.netloc.split(':')

        # Change input method and timezone, create a file, then start update.
        self._run_client_test_and_check_result(self._USER_DATA_TEST,
                                               server=server, port=int(port),
                                               update_path=url_split.path,
                                               tag='before_update')
        self._wait_for_update_to_complete()
        self._host.reboot()

        # Ensure preferences and downloads are the same as before the update.
        self._run_client_test_and_check_result(self._USER_DATA_TEST,
                                               tag='after_update')
