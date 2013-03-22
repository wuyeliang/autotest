# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Factory task to select an unique serial number for VPD.

Partners should fill this in with the correct serial number
printed on the box and physical device.
"""

import calendar
import gtk

from autotest_lib.client.cros import factory_setup_modules
from cros.factory.test import task
from cros.factory.test import ui


_MESSAGE_PROMPT = 'Enter Serial Number:'


class SerialNumberTask(task.FactoryTask):

    def __init__(self, vpd, init_value):
        self.vpd = vpd
        self.init_value = init_value

    @staticmethod
    def strip_leading_zero(serial):
      """Remove a leading zero from the serial number if present.

      Printed barcodes used in RMA contain a leading
      zero that must be stripped off.

      Args:
        serial: String. Serial number to parse.

      Returns:
        String. Serial number with extra leading zero removed.
      """
      serial = serial.strip()
      if len(serial) == 18 and serial[0] == '0':
        serial = serial[1:]
      return serial

    def on_validate(self, serial):
        # Link serial number format:
        #
        #   4 digit date of manufacture (YMDD) +
        #   8 digit manufacturing code +
        #   5 digit serial
        #
        # For the YMDD the format is as follows.
        #
        #   Y = 2 for 2012, 3 for 2013
        #   M = 1-9 Jan - Sept, A Oct, B Nov, C Dec
        #   D = 01-31
        #
        def get_num_days_in_month(year_code, month_code):
            month_code_map = {
                'A': 10,
                'B': 11,
                'C': 12,
            }
            year = 2010 + int(year_code)
            month = (month_code_map[month_code] if month_code in month_code_map
                                                else int(month_code))
            return calendar.monthrange(year, month)[1]
        serial = self.strip_leading_zero(serial)
        return (len(serial) == 17 and
                serial[0] in ('2', '3') and
                (serial[1].isdigit() or serial[1] in ['A', 'B', 'C']) and
                1 <= int(serial[2:4]) <= get_num_days_in_month(serial[0],
                                                               serial[1]) and
                serial[4:].isdigit())

    def on_complete(self, serial_number):
        serial_number = self.strip_leading_zero(serial_number)
        self.vpd['ro']['serial_number'] = serial_number
        self.stop()

    def start(self):
        self.add_widget(ui.make_input_window(prompt=_MESSAGE_PROMPT,
                                             init_value=self.init_value,
                                             on_validate=self.on_validate,
                                             on_complete=self.on_complete))
