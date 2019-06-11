# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.server.cros.bluetooth import bluetooth_default_state_test
from autotest_lib.server.cros.multimedia import remote_facade_factory


class bluetooth_Sanity_DefaultState(
        bluetooth_default_state_test.bluetooth_Sanity_DefaultStateTest):
    """
    Verify that the Bluetooth adapter has correct state.
    """

    def test_init(self, device_host):
        """Initialize the test"""
        factory = remote_facade_factory.RemoteFacadeFactory(device_host)
        self.bluetooth_facade = factory.create_bluetooth_hid_facade()


    def run_once(self, device_host):
        """Run the bluetooth sanity default state test

        @param device_host: the DUT, usually a chromebook
        """
        self.test_init(device_host)
        self.default_state_test()

