# Copyright 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os

from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros import chrome
from autotest_lib.client.cros.update_engine import update_engine_test

class autoupdate_UserData(update_engine_test.UpdateEngineTest):
    """
    Modifies some user settings and checks they were not reset by an update.

    This test is used as part of the server test autoupdate_DataPreserved.
    This test will make use of several private Chrome APIs:
    inputMethodPrivate: chrome/common/extensions/api/input_method_private.json
    languageSettingsPrivate: chrome/common/extensions/api/
                             language_settings_private.idl
    settingsPrivate: chrome/common/extensions/api/settings_private.idl

    """
    version = 1

    _TEST_FILE = '/home/chronos/user/Downloads/test.txt'
    _US_IME = '_comp_ime_jkghodnilhceideoidjikpgommlajknkxkb:us::eng'
    _US_INTL_IME = '_comp_ime_jkghodnilhceideoidjikpgommlajknkxkb:us:intl:eng'
    _TIME_ZONE_PREF = 'generated.resolve_timezone_by_geolocation_on_off'

    _GET_IME_JS = '''
        new Promise(function(resolve, reject) {
            chrome.inputMethodPrivate.getCurrentInputMethod(
                function(id) {
                    resolve(id);
                });
        })
    '''
    _GET_PREF_JS = '''
        new Promise(function(resolve, reject) {
            chrome.settingsPrivate.getPref("%s", function(pref) {
                resolve(pref['value']);
            });
        })
    '''
    _SET_IME_JS = 'chrome.inputMethodPrivate.setCurrentInputMethod("%s")'
    _SET_PREF_JS = ('chrome.settingsPrivate.setPref("%s", %s, '
                    'x => console.log(x))')


    def _modify_input_methods(self):
        """ Change default Input Method to US International."""
        current_ime = self._cr.autotest_ext.EvaluateJavaScript(
            self._GET_IME_JS, promise=True)
        logging.info('Current IME is %s', current_ime)
        add_ime_js = ('chrome.languageSettingsPrivate.addInputMethod("%s")' %
                      self._US_INTL_IME)
        self._cr.autotest_ext.EvaluateJavaScript(add_ime_js)
        self._cr.autotest_ext.EvaluateJavaScript(self._SET_IME_JS %
                                                 self._US_INTL_IME)
        new_ime = self._cr.autotest_ext.EvaluateJavaScript(self._GET_IME_JS)
        if current_ime == new_ime:
            raise error.TestFail('IME could not be changed before update.')


    def _modify_time_zone(self):
        """Change time zone to be user selected instead of automatic by IP."""
        current_time_zone = self._cr.autotest_ext.EvaluateJavaScript(
            self._GET_PREF_JS % self._TIME_ZONE_PREF, promise=True)
        logging.info('Calculating timezone by IP: %s', current_time_zone)
        self._cr.autotest_ext.EvaluateJavaScript(
            self._SET_PREF_JS % (self._TIME_ZONE_PREF, 'false'))
        new_timezone = self._cr.autotest_ext.EvaluateJavaScript(
            self._GET_PREF_JS % self._TIME_ZONE_PREF, promise=True)
        if current_time_zone == new_timezone:
            raise error.TestFail('Timezone detection could not be changed.')


    def _perform_after_update_checks(self):
        """Check the user preferences and files are the same."""
        with chrome.Chrome(dont_override_profile=True,
                           autotest_ext=True) as cr:
            # Check test file is still present.
            if not os.path.exists(self._TEST_FILE):
                raise error.TestFail('Test file was not present after update.')

            # Check IME has not changed.
            current_ime = cr.autotest_ext.EvaluateJavaScript(
                self._GET_IME_JS, promise=True)
            if current_ime != self._US_INTL_IME:
                raise error.TestFail('Input method was not preserved after'
                                     'update. Expected %s, Actual: %s' %
                                     (self._US_INTL_IME, current_ime))

            # Check that timezone is user selected.
            current_time_zone = cr.autotest_ext.EvaluateJavaScript(
                self._GET_PREF_JS % self._TIME_ZONE_PREF, promise=True)
            if current_time_zone:
                raise error.TestFail('Time zone detection was changed back to '
                                     'automatic.')


    def run_once(self, server=None, port=None, update_path=None):
        """
        Tests that user settings are not reset by update.

        @param server: The update server to use.
        @param port: The port of the update server.
        @param update_path: The /update part of the url.

        """
        if server:
            with chrome.Chrome(autotest_ext=True) as cr:
                self._cr = cr
                utils.run('echo hello > %s' % self._TEST_FILE)
                self._modify_input_methods()
                self._modify_time_zone()
                self._check_for_update(server=server, port=port,
                                       update_path=update_path)
                self._wait_for_progress(0.2)
        else:
            self._perform_after_update_checks()
