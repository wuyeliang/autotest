# -*- coding: utf-8 -*-
#
# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


# DESCRIPTION :
#
# This is only for factory-1987.B branch.
# Discuss further before checking in to trunk.


import gtk
import logging
import os
import pango
import sys

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib import utils
from autotest_lib.client.cros import factory
from autotest_lib.client.cros.factory import ui

LABEL_FONT = pango.FontDescription('courier new extra-condensed 200')

class factory_RuninReview(test.test):
    version = 1

    TEST_LIST='/usr/local/autotest/site_tests/suite_Factory/test_list'
    def key_press_callback(self, widget, event):
        if event.keyval == gtk.keysyms.space:
                gtk.main_quit()
        return True

    def register_callbacks(self, window):
        window.connect('key-press-event', self.key_press_callback)
        window.add_events(gtk.gdk.KEY_PRESS_MASK)

    def run_once(self):

        factory.log('%s run_once' % self.__class__)

        test_list = factory.read_test_list(self.TEST_LIST)
        state_map = test_list.get_state_map()

        runin_tests = [t for t in test_list.walk() if
                       t.path.startswith('RUNIN')]
        all_passed = all(state_map[t].status == factory.TestState.PASSED or
                         state_map[t].status == factory.TestState.ACTIVE
                         for t in runin_tests)
        color = ui.LABEL_COLORS[ui.PASSED if all_passed else ui.FAILED]

        vbox = gtk.VBox()
        vbox.add(ui.make_label('OK' if all_passed else '不行',
                                font=LABEL_FONT,
                                fg=color))
        vbox.add(ui.make_label('按空白鍵繼續\nPress SPACE to continue'))

        ui.run_test_widget(self.job, vbox,
            window_registration_callback=self.register_callbacks)

        factory.log('%s run_once finished' % self.__class__)
