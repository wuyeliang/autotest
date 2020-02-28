# Copyright 2020 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from autotest_lib.server.cros.update_engine import update_engine_test


class autoupdate_FromUI(update_engine_test.UpdateEngineTest):
    """Trigger an update from the UI.

    Start an update by clicking on the 'Check for update' button in the
    Chrome OS settings menu, instead of calling to update_engine_client
    directly.

    """
    version = 1
    _UI_TEST = 'autoupdate_UpdateFromUI'


    def run_once(self, full_payload=True, job_repo_url=None,
                 running_at_desk=False):
        """
        Tests that we can successfully perform an update via the UI.

        @param full_payload: True for a full payload. False for delta.
        @param job_repo_url: Used for debugging locally. This is used to figure
                             out the current build and the devserver to use.
                             The test will read this from a host argument
                             when run in the lab.
        @param running_at_desk: True if the test is being run locally.

        """
        self._job_repo_url = job_repo_url
        payload = self._get_payload_url(full_payload=full_payload)
        image_url, _ = self._stage_payload_by_uri(payload)

        if running_at_desk:
            image_url = self._copy_payload_to_public_bucket(payload)
            logging.info('We are running from a workstation. Putting URL on a'
                         ' public location: %s', image_url)

        # Login and click 'Check for update' in the Settings app.
        self._run_client_test_and_check_result(self._UI_TEST,
                                               image_url=image_url)

        self._host.reboot()

        # Check that the update completed successfully
        before_reboot_file = self._get_second_last_update_engine_log()
        success = 'Update successfully applied, waiting to reboot.'
        self._check_update_engine_log_for_entry(
            success, raise_error=True, update_engine_log=before_reboot_file)
