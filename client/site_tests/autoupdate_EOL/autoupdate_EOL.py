# Copyright 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros.update_engine import nano_omaha_devserver
from autotest_lib.client.cros.update_engine import update_engine_test

class autoupdate_EOL(update_engine_test.UpdateEngineTest):
    """Tests end of life (EOL) behaviour."""
    version = 1

    _EXPECTED_EOL_DATE_TEMPLATE = 'EOL_DATE={}'
    _EOL_NOTIFICATION_TITLE = 'Final software update'

    def cleanup(self):
        self._save_extra_update_engine_logs()
        super(autoupdate_EOL, self).cleanup()


    def _check_eol_info(self):
        """Checks update_engines eol status."""
        result = utils.run('update_engine_client --eol_status').stdout.strip()
        if self._EXPECTED_EOL_DATE not in result:
            raise error.TestFail('Expected date %s. Actual: %s' %
                                 (self._EXPECTED_EOL_DATE, result))


    def _check_eol_notification(self):
        """Checks that we are showing an EOL notification to the user."""
        # TODO(crbug.com/995889): Should have notification checks based on
        # EOL date.
        pass


    def run_once(self, eol_date):
        """
        The main test.

        @param eol_date: the value passed along to NanoOmahaDevServer placed
                         within the _eol_date tag in the Omaha response.
        """
        # Override the expected values based on input of |eol_date| and params.
        self._EXPECTED_EOL_DATE = \
            self._EXPECTED_EOL_DATE_TEMPLATE.format(eol_date)

        # Start a devserver to return a response with eol entry.
        self._omaha = nano_omaha_devserver.NanoOmahaDevserver(eol_date=eol_date)
        self._omaha.start()

        # Try to update using the omaha server. It will fail with noupdate.
        self._check_for_update(port=self._omaha.get_port(), ignore_status=True,
                               wait_for_completion=True)

        self._check_eol_info()
        self._check_eol_notification()
