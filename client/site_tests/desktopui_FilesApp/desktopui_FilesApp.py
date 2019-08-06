# Copyright 2019 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import logging
import time

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros import chrome
from autotest_lib.client.cros.graphics import graphics_utils
from autotest_lib.client.cros.input_playback import keyboard
from telemetry.internal.backends.chrome_inspector import devtools_http

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
    _IMAGE_FILE = 'screenshot2_reference.png'
    _IMAGE_DIMENSIONS = '100 x 100'
    _DOWNLOADS = 'Downloads'
    _MY_FILES = 'My files'
    _NEW_FOLDER = 'New folder'
    _OPEN_FILE = 'Open'
    _EDIT_IMAGE = 'Edit'


    def cleanup(self):
        """Remove temporary files created during test."""
        for temp_path in self._temp_file_paths:
            try:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
            except OSError:
                logging.info(
                    'Failed to delete %s in cleanup. Ignoring', temp_path)


    def evaluate_javascript(self, code, retries=3):
        """Executes javascript and returns some result.

        Occasionally calls to EvaluateJavascript on the autotest_ext will fail
        to find the extension. Instead of wrapping every call in a try/except,
        calls will go through this function instead.

        @param code: The javascript string to execute
        @param retries: The number of times to retry the code

        """
        for i in range(0, retries):
            try:
                result = self.cr.autotest_ext.EvaluateJavaScript(code)
                return result
            except KeyError:
                logging.exception('Could not find autotest_ext')
            except devtools_http.DevToolsClientUrlError:
                logging.exception('Could not connect to DevTools')

            time.sleep(1)

        raise error.TestFail('Could not execute "%s" in %d retries' %
                             (code, retries))


    def _wait_for_element_to_be_visible(self, role, name, timeout=10,
                                        err_str='element to load'):
        """
        Wait for an element to appear on screen.

        @param role: The chrome.automation role we want to look for
        @param name: The chrome.automation name we want to look for
        @param timeout: How long to wait
        @param err_str: The error string to pass to the TimeoutException

        """
        find_js = "root.find({attributes: {role: '%s', name: '%s'}});" %\
                  (role, name)

        def finished_loading():
            """Check if an element has finished loading."""
            visible = self.evaluate_javascript(find_js)
            return visible is not None
        utils.poll_for_condition(condition=finished_loading, timeout=timeout,
                                 desc=err_str)


    def _click_element(self, role, name):
        """Click an element by role/name combination.

        @param role: The chrome.automation role we want to look for
        @param name: The chrome.automation name we want to look for

        """
        click_js = """
            element = root.find({attributes: {role: '%s',
                                              name: '%s'}});
            element.doDefault(); """ % (role, name)
        self.evaluate_javascript(click_js)


    def _set_navigation_point_on_element(self, role, name):
        """Set navigation point to an element by role/name combination.

        @param role: The chrome.automation role we want to look for
        @param name: The chrome.automation name we want to look for

        """
        focus_js = """
            element = root.find({attributes: {role: '%s',
                                              name: '%s'}});
            element.setSequentialFocusNavigationStartingPoint(); """ %\
            (role, name)
        self.evaluate_javascript(focus_js)


    def _launch_app(self, id):
        """
        Launch the app/extension by its ID and check that it opens.

        @param id: The app ID of the app to launch.

        """
        launch_js = "chrome.autotestPrivate.launchApp('%s', function(){})" % id
        self.evaluate_javascript(launch_js)
        self._files_app = None
        self._foreground_page = None

        def check_open():
            """Check if the app is running."""
            try:
                if self._files_app is None or len(self._files_app) <= 1:
                    self._files_app = \
                        self.cr.browser.extensions.GetByExtensionId(id)
                if len(self._files_app) > 1:
                    if self._foreground_page is None:
                        # Figure out which of the pages is the foreground one.
                        for ext in self._files_app:
                            url = ext.EvaluateJavaScript('location.href;')
                            if url.endswith('main.html'):
                                self._foreground_page = ext
                                break
                    loaded_js = """document.body.hasAttribute('loaded');"""
                    try:
                        return self._foreground_page.EvaluateJavaScript(
                            loaded_js)
                    except:
                        return False
                return False
            except KeyError:
                return False

        try:
            utils.poll_for_condition(condition=check_open, timeout=60)
        except utils.TimeoutError:
            raise error.TestFail('Could not open app: %s' % id)


    def _load_automation_root(self):
        """Load the chrome.automation API and get the on screen elements."""
        load_cmd = "var root; chrome.automation.getDesktop(r => root = r);"
        self.evaluate_javascript(load_cmd)


    def _find_all_by_role(self, role):
        """
        Finds all the visible elements of a certain role type.

        @param role: The type of role to search for.

        """
        find_all_js = """
            var root;
            chrome.automation.getDesktop(r => root = r);
            root.findAll({attributes: {role: '%s'}}).map(node => node.name);
            """ % role
        roles = self.evaluate_javascript(find_all_js)
        logging.info(roles)
        return roles


    def _open_downloads(self):
        """Open the Downloads folder in the Files app."""
        self._wait_for_element_to_be_visible(self._BUTTON,
                                             self._MY_FILES,
                                             err_str='Files to load')
        self._wait_for_element_to_be_visible(self._STATIC_TEXT,
                                             self._DOWNLOADS,
                                             err_str='Downloads to appear')
        self._click_element(self._STATIC_TEXT, self._DOWNLOADS)
        self._wait_for_element_to_be_visible(self._STATIC_TEXT,
                                             self._TEXT_FILE,
                                             err_str='.txt to show')


    def _open_more_options(self):
        """Opens the three dot menu of the Files app."""
        self._click_element(self._BUTTON, 'More\u2026')
        self._wait_for_element_to_be_visible(self._STATIC_TEXT,
                                             self._NEW_FOLDER,
                                             err_str='New folder item')


    def _open_image_preview(self):
        """Open the image for a preview."""
        self._open_downloads()

        # Select the image file
        self._click_element(self._STATIC_TEXT, self._IMAGE_FILE)
        self._wait_for_element_to_be_visible(self._BUTTON,
                                             self._OPEN_FILE,
                                             err_str='Open button to appear')
        # Launch image preview
        with keyboard.Keyboard() as k:
            self._set_navigation_point_on_element(self._STATIC_TEXT,
                                                  self._IMAGE_FILE)
            k.press_key('tab')
            k.press_key('space')
            self._wait_for_element_to_be_visible(self._STATIC_TEXT,
                                                 self._IMAGE_DIMENSIONS,
                                                 err_str='Image info to appear')


    def _setup(self):
        """Populate DUT with assets and load automation APIs."""
        text_dest_path = os.path.join(self._DOWNLOADS_PATH, self._TEXT_FILE)
        image_src_path = os.path.join(self.bindir, 'assets', self._IMAGE_FILE)
        image_dest_path = os.path.join(self._DOWNLOADS_PATH, self._IMAGE_FILE)

        utils.write_one_line(text_dest_path, 'blahblah')
        self._temp_file_paths.append(text_dest_path)

        if self._preview_image:
            utils.force_copy(image_src_path, image_dest_path)
            self._temp_file_paths.append(image_dest_path)

        self._load_automation_root()


    def run_once(self, preview_image=False):
        """Main entry point of test."""
        with chrome.Chrome(autotest_ext=True,
                           disable_default_apps=False) as cr:
            # Setup
            self.cr = cr
            self._preview_image = preview_image
            self._temp_file_paths = [] # Accumulate temp file paths for cleanup
            self._setup()

            try:
                # Files app testing
                self._launch_app(self._FILES_APP_ID)
                self._open_downloads()
                self._open_more_options()
                if self._preview_image:
                    self._open_image_preview()
            except (ValueError, utils.TimeoutError):
                logging.exception('Failed to verify Files app is available.')
                try:
                    graphics_utils.take_screenshot(self.resultsdir, 'failure')
                except:
                    logging.info('Failed to take screenshot')
                raise
            finally:
                logging.info('Extra logging for debugging')
                self._find_all_by_role(self._BUTTON)
                self._find_all_by_role(self._STATIC_TEXT)
