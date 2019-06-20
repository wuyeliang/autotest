# Copyright 2019 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import logging

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros import chrome
from autotest_lib.client.cros.graphics import graphics_utils


class desktopui_FilesApp(test.test):
    """Smoke test of Files app using chrome.automation API."""
    version = 1

    _FILES_APP_ID = 'hhaomjibdihmijegdhdafkllkbggdgoj'
    _DOWNLOADS_PATH = '/home/chronos/user/Downloads'

    # chrome.automation roles
    _BUTTON = 'button'
    _STATIC_TEXT = 'staticText'

    # On screen elements
    _TEXT_FILE = 'text.txt'
    _DOWNLOADS = 'Downloads'
    _MY_FILES = 'My files'
    _NEW_FOLDER = 'New folder'


    def _wait_for_element_to_be_visible(self, cr, role, name, timeout=10,
                                        err_str=None):
        """
        Wait for an element to appear on screen.

        @param cr: The chrome browser running
        @param role: The chrome.automation role we want to look for
        @param name: The chrome.automation name we want to look for
        @param timeout: How long to wait
        @param err_str: The error string to pass to the TimeoutException

        """
        def finished_loading():
            """Check if an element has finished loading."""
            try:
                visible = cr.autotest_ext.EvaluateJavaScript("""
                   root.find({attributes: {role: '%s', name: '%s'}});
                   """ % (role, name))
                logging.info(visible)
                return visible is not None
            except KeyError as e:
                logging.exception('Could not find autotest_ext')
                return False
        utils.poll_for_condition(condition=finished_loading, timeout=timeout,
                                 desc=err_str)


    def _launch_app(self, cr, app_id):
        """
        Launch the app/extension by its ID and check that it opens.

        @param cr: The chrome browser instance that is running.
        @param app_id: The app ID of the app to launch.

        """
        ext = cr.autotest_ext
        ext.ExecuteJavaScript("""
            chrome.autotestPrivate.launchApp('%s', function(){})""" % app_id)

        def check_open():
            """Check if the app is running."""
            try:
                cr.browser.extensions.GetByExtensionId(app_id)
            except KeyError:
                return False
            return True

        try:
            utils.poll_for_condition(condition=check_open, timeout=60)
        except utils.TimeoutError:
            raise error.TestFail('Could not open app: %s' % app_id)


    def _load_automation_root(self, cr):
        """
        Load the chrome.automation API and get the on screen elements.

        @param cr: The browser instance that is running.

        """
        cr.autotest_ext.ExecuteJavaScript("""
            var root;
            chrome.automation.getDesktop(r => root = r);
            """)


    def _open_downloads(self, cr):
        """
        Open the Downloads folder in the Files app.

        @param cr: The browser instance that is running.

        """
        self._wait_for_element_to_be_visible(cr, self._STATIC_TEXT,
                                             self._DOWNLOADS,
                                             err_str='Downloads to appear')
        cr.autotest_ext.EvaluateJavaScript("""
            downloads = root.find({attributes: {role: '%s',
                                                name: '%s'}});
            downloads.doDefault();
            """ % (self._STATIC_TEXT, self._DOWNLOADS))


    def _find_all_by_role(self, cr, role):
        """
        Finds all the visible elements of a certain role type.

        @param cr: The browser instance that is running
        @param role: The type of role to search for.

        """
        try:
            roles = cr.autotest_ext.EvaluateJavaScript("""
                var root;
                chrome.automation.getDesktop(r => root = r);
                root.findAll({attributes: {role: '%s'}}).map(node => node.name);
                """ % role)
            logging.info(roles)
            return roles
        except Exception:
            logging.exception('Failed to get elements by role.')


    def _open_more_options(self, cr):
        """
        Opens the three dot menu of the Files app.

        @param cr: The browser instance that is open.

        """
        cr.autotest_ext.EvaluateJavaScript("""
            more = root.find({attributes: {role: '%s',
                                           name: 'More\u2026'}});
            more.doDefault();
            """ % self._BUTTON)


    def cleanup(self):
        """Remove temporary files created during test."""
        text_file = os.path.join(self._DOWNLOADS_PATH, self._TEXT_FILE)
        try:
            if os.path.exists(text_file):
                os.remove(text_file)
        except OSError:
            logging.info('Failed to delete files in cleanup. Ignoring.')


    def run_once(self):
        """Main entry point of test."""
        with chrome.Chrome(autotest_ext=True,
                           disable_default_apps=False) as cr:
            # Setup
            utils.write_one_line(os.path.join(self._DOWNLOADS_PATH,
                                              self._TEXT_FILE), 'blahblah')
            self._load_automation_root(cr)

            try:
                # Files app testing
                self._launch_app(cr, self._FILES_APP_ID)
                self._wait_for_element_to_be_visible(cr, self._BUTTON,
                                                     self._MY_FILES,
                                                     err_str='Files to load')
                self._open_downloads(cr)
                self._wait_for_element_to_be_visible(cr, self._STATIC_TEXT,
                                                     self._TEXT_FILE,
                                                     err_str='.txt to show')
                self._open_more_options(cr)
                self._wait_for_element_to_be_visible(cr, self._STATIC_TEXT,
                                                     self._NEW_FOLDER,
                                                     err_str='New folder item')
            except (ValueError, utils.TimeoutError):
                logging.exception('Failed to verify Files app is available.')
                try:
                    graphics_utils.take_screenshot(self.resultsdir, 'failure')
                except:
                    logging.info('Failed to take screenshot')
                raise
            finally:
                logging.info('Extra logging for debugging')
                self._find_all_by_role(cr, self._BUTTON)
                self._find_all_by_role(cr, self._STATIC_TEXT)
