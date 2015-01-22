# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import glob
from itertools import groupby
import logging
from threading import Timer

from autotest_lib.client.common_lib import error
from autotest_lib.server.cros.faft.firmware_test import FirmwareTest
from autotest_lib.client.bin.input.input_device import *


class firmware_FAFTSetup(FirmwareTest):
    """This test checks the following FAFT hardware requirement:
      - Warm reset
      - Cold reset
      - Recovery boot with USB stick
      - USB stick is plugged into Servo board, not DUT
      - Keyboard simulation
      - No terminal opened on EC console
    """
    version = 1

    # Delay between starting client-side test and pressing the keys
    KEY_PRESS_DELAY = 4


    def console_checker(self):
        """Verify EC console is available if using Chrome EC."""
        if not self.check_ec_capability(suppress_warning=True):
            # Not Chrome EC. Nothing to check.
            return True
        try:
            self.ec.send_command("chan 0")
            expected_output = ["Chip:\s+[^\r\n]*\r\n",
                               "RO:\s+[^\r\n]*\r\n",
                               "RW:\s+[^\r\n]*\r\n",
                               "Build:\s+[^\r\n]*\r\n"]
            self.ec.send_command_get_output("version",
                                            expected_output)
            self.ec.send_command("chan 0xffffffff")
            return True
        except: # pylint: disable=W0702
            logging.error("Cannot talk to EC console.")
            logging.error(
                    "Please check there is no terminal opened on EC console.")
            raise error.TestFail("Failed EC console check.")

    def base_keyboard_checker(self, press_action):
        """Press key and check from DUT.

        Args:
            press_action: A callable that would press the keys when called.
        """

        # Stop UI so that key presses don't go to Chrome.
        self.faft_client.system.run_shell_command("stop ui")

        # Press the keys
        Timer(self.KEY_PRESS_DELAY, press_action).start()

        # Invoke client side script to monitor keystrokes
        self._autotest_client.run_test("firmware_FAFTClient",
                expected_sequence=[28, 29, 32]) 

        # Turn UI back on
        self.faft_client.system.run_shell_command("start ui")
        return True

    def keyboard_checker(self):
        """Press 'd', Ctrl, ENTER by servo and check from DUT."""

        def keypress():
            self.press_ctrl_d()
            self.press_enter()

        keys = self.faft_config.key_checker


        self.base_keyboard_checker(keypress)
        return True

    def run_once(self):
        logging.info("Check EC console is available and test warm reboot")
        self.console_checker()
        self.reboot_warm()

        logging.info("Check test image is on USB stick and run recovery boot")
        self.assert_test_image_in_usb_disk()
        self.do_reboot_action(self.enable_rec_mode_and_reboot)
        self.wait_fw_screen_and_plug_usb()
        self.check_state((self.checkers.crossystem_checker,
                          {'mainfw_type': 'recovery'}))

        logging.info("Check cold boot")
        self.reboot_cold()

        logging.info("Check keyboard simulation")
        self.check_state(self.keyboard_checker)
