# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.server.cros.bluetooth import bluetooth_valid_address_test
from autotest_lib.server.cros.multimedia import remote_facade_factory


class bluetooth_Sanity_ValidAddress(
        bluetooth_valid_address_test.bluetooth_Sanity_ValidAddressTest):
    """
    Verify that the client Bluetooth adapter has a valid address.
    """

    def test_init(self, device_host):
        """Initialize the test"""
        factory = remote_facade_factory.RemoteFacadeFactory(device_host)
        self.bluetooth_facade = factory.create_bluetooth_hid_facade()


    def run_once(self, device_host):
        """Run the bluetooth sanity valid address test

        @param device_host: the DUT, usually a chromebook
        """
        self.test_init(device_host)
        self.valid_address_test()
