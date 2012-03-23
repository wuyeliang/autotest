# -*- coding: utf-8 -*-
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import gtk

from autotest_lib.client.bin import test
from autotest_lib.client.cros import factory
from autotest_lib.client.cros.factory import ui as ful

class factory_ScanSN(test.test):
    version = 1

    def on_sn_complete(self, serial_number):
        factory.log('Serial number is: %s' % serial_number)
        gtk.main_quit()

    def run_once(self):
        factory.log('%s run_once' % self.__class__)

        self.sn_input_widget = ful.make_input_window(
            prompt='請掃描A/B面板條碼\nScan A/B panel serial number:',
            on_validate=None,
            on_keypress=None,
            on_complete=self.on_sn_complete)

        # Make sure the entry in widget will have focus.
        self.sn_input_widget.connect(
            "show",
            lambda *x : self.sn_input_widget.get_entry().grab_focus())

        self.test_widget = gtk.VBox()
        self.test_widget.add(self.sn_input_widget)
        ful.run_test_widget(self.job, self.test_widget)

        factory.log('%s run_once finished' % self.__class__)
