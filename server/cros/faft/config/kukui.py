# Copyright 2019 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""FAFT config setting overrides for Kukui."""

class Values(object):
    """FAFT config values for Kukui."""
    has_keyboard = False
    chrome_ec = True
    ec_capability = ['arm', 'battery', 'charging', 'lid']
    mode_switcher_type = 'tablet_detachable_switcher'
    fw_bypasser_type = 'tablet_detachable_bypasser'
    ec_reboot_to_g3_delay = 10
    usbc_input_voltage_limit = 12
