# Copyright 2019 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""FAFT configuration overrides for Mistral."""

from autotest_lib.server.cros.faft.config import jetstream


class Values(jetstream.Values):
    """Inherit overrides from Jetstream."""

    chrome_ec = False
    rec_button_dev_switch = False
    warm_reset_hold_time = 0.7
    has_power_button = False
