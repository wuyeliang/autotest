# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import glob
import logging
import pprint

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.bin.input.input_device import *

from threading import Timer

class firmware_FAFTClient(test.test):
    version = 1
    actual_output = []
    device = None
    ev = None

    def _get_keyboard(self):
        _key_pressed = False
        for evdev in glob.glob("/dev/input/event*"):
            device = InputDevice(evdev)
            if device.is_keyboard():
                return device
        return None

    def keyboard_input(self):
        index = 0
        while True:
            self.ev.read(self.device.f)
            if self.ev.code != KEY_RESERVED:
                logging.info("EventCode is %d value is %d" % (self.ev.code, self.ev.value))
                if self.ev.type == 0 or self.ev.type == 1:
                    self.actual_output.append(self.ev.code)
                    index = index + 1

    def run_once(self, expected_sequence):
        self.device = self._get_keyboard()
        if not self.device:
            raise error.TestError("Could not find a keyboard")

        self.ev = InputEvent()
        Timer(0, self.keyboard_input).start()

        time.sleep(10)
        if len(self.actual_output) == 0:
            raise error.TestFail("No keys pressed")
            return

        # Keypresses will have a tendency to repeat as there is delay between the
        # down and up events.  We're not interested in precisely how many repeats
        # of the key there is, just what is the sequence of keys, so, we will make
        # the list unique.
        uniq_actual_output = sorted(list(set(self.actual_output)))
        if uniq_actual_output != expected_sequence:
            raise error.TestFail(
                    "Keys mismatched %s" % pprint.pformat(uniq_actual_output))
            return

