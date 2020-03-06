# Copyright 2020 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""A Batch of Bluetooth AUdio Sanity tests"""

from autotest_lib.server.cros.bluetooth.bluetooth_adapter_quick_tests import (
        BluetoothAdapterQuickTests)
from autotest_lib.server.cros.bluetooth.bluetooth_adapter_audio_tests import (
        BluetoothAdapterAudioTests)


class bluetooth_AdapterAUSanity(BluetoothAdapterQuickTests,
                                BluetoothAdapterAudioTests):
    """A Batch of Bluetooth audio sanity tests."""

    test_wrapper = BluetoothAdapterQuickTests.quick_test_test_decorator
    batch_wrapper = BluetoothAdapterQuickTests.quick_test_batch_decorator


    @test_wrapper('A2dp sinewave test', devices={'BLUETOOTH_AUDIO':1})
    def au_a2dp_test(self):
        """a2dp test with sinewaves on the two channels."""
        device = self.devices['BLUETOOTH_AUDIO'][0]

        self.initialize_bluetooth_audio(device)
        self.test_power_on_adapter()
        self.test_bluetoothd_running()
        self.test_device_set_discoverable(device, True)
        self.test_discover_device(device.address)
        self.test_stop_discovery()
        self.test_pairing(device.address, device.pin, trusted=True)
        device.SetTrustedByRemoteAddress(self.bluetooth_facade.address)
        self.test_connection_by_adapter(device.address)
        self.test_a2dp_sinewaves(device)
        self.test_disconnection_by_adapter(device.address)
        self.cleanup_bluetooth_audio(device)


    @batch_wrapper('Bluetooth Audio Batch Sanity Tests')
    def au_sanity_batch_run(self, num_iterations=1, test_name=None):
        """Run the bluetooth audio sanity test batch or a specific given test.

        @param num_iterations: how many iterations to run
        @param test_name: specific test to run otherwise None to run the
                whole batch
        """
        self.au_a2dp_test()


    def run_once(self, host, num_iterations=1, test_name=None,
                 flag='Quick Sanity'):
        """Run the batch of Bluetooth stand sanity tests

        @param host: the DUT, usually a chromebook
        @param num_iterations: the number of rounds to execute the test
        @test_name: the test to run, or None for all tests
        """
        self.host = host

        self.quick_test_init(host, use_chameleon=True, flag=flag)
        self.au_sanity_batch_run(num_iterations, test_name)
        self.quick_test_cleanup()
