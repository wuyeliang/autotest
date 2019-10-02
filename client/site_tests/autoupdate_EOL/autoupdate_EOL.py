# Copyright 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import datetime

from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros import chrome
from autotest_lib.client.cros.update_engine import nano_omaha_devserver
from autotest_lib.client.cros.update_engine import update_engine_test

class autoupdate_EOL(update_engine_test.UpdateEngineTest):
    """Tests end of life (EOL) behaviour."""
    version = 1

    _EXPECTED_FINAL_TITLE = 'Final software update'
    _DAYS_BEFORE_EOL_START_WARNING = 180
    # Value within {} expected to be number of days since epoch.
    _EXPECTED_EOL_DATE_TEMPLATE = 'EOL_DATE={}'
    # Value within {} expected to be the month and year.
    _EXPECTED_WARNING_TITLE = 'Updates end {}'

    def cleanup(self):
        self._save_extra_update_engine_logs()
        super(autoupdate_EOL, self).cleanup()


    def _check_eol_info(self):
        """Checks update_engines eol status."""
        result = utils.run('update_engine_client --eol_status').stdout.strip()
        if self._EXPECTED_EOL_DATE not in result:
            raise error.TestFail('Expected date %s. Actual: %s' %
                                 (self._EXPECTED_EOL_DATE, result))


    def _check_eol_notification(self, eol_date):
        """Checks that we are showing an EOL notification to the user."""
        epoch = datetime.datetime(1970,1,1)
        expected_eol_date = (epoch + datetime.timedelta(eol_date))
        expected_warning_begins_date = (expected_eol_date
                                        - datetime.timedelta(
                                          self._DAYS_BEFORE_EOL_START_WARNING))

        expected_final_title = self._EXPECTED_FINAL_TITLE
        expected_warning_title = (self._EXPECTED_WARNING_TITLE.
            format(expected_eol_date.strftime("%B %Y")))

        def find_notification(expected_title):
            """Helper to find notification."""
            notifications = cr.get_visible_notifications()
            return any([n['title'] == expected_title
                        for n in (notifications or [])])

        with chrome.Chrome(autotest_ext=True, logged_in=True) as cr:
            def check_eol_notifications():
                """ Checks if correct notification is shown """
                final_notification = find_notification(expected_final_title)
                warning_notification = find_notification(expected_warning_title)

                now = datetime.datetime.utcnow()
                if expected_eol_date <= now:
                    return final_notification and not warning_notification
                elif expected_warning_begins_date <= now:
                    return not final_notification and warning_notification
                return not final_notification and not warning_notification

            utils.poll_for_condition(
                                condition=lambda: check_eol_notifications(),
                                desc='End of Life Notification UI passed',
                                timeout=5,
                                sleep_interval=1)

    def run_once(self, eol_date):
        """
        The main test.

        @param eol_date: the days from epoch value passed along to
                         NanoOmahaDevServer placed within the _eol_date tag
                         in the Omaha response.
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
        self._check_eol_notification(eol_date)
