# Copyright 2019 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Bluetooth DBus API tests."""

from autotest_lib.server.cros.bluetooth import bluetooth_adapter_tests

# Assigning local names for some frequently used long method names.
method_name = bluetooth_adapter_tests.method_name
_test_retry_and_log = bluetooth_adapter_tests._test_retry_and_log

# String representation of DBus exceptions
DBUS_ERRORS  ={
    'InProgress' : 'org.bluez.Error.InProgress: Operation already in progress',
    'NotReady' : 'org.bluez.Error.NotReady: Resource Not Ready',
    'Failed': {
        'discovery' : 'org.bluez.Error.Failed: No discovery started'}}


class BluetoothDBusAPITests(bluetooth_adapter_tests.BluetoothAdapterTests):
    """Bluetooth DBus API Test

       These test verifies return values and functionality of various Bluetooth
       DBus APIs. It tests both success and failures cases of each API
    """


    def _wait_till_discovery_stops(self, stop_discovery=True):
        """stop discovery if specified and wait for discovery to stop

        @params: stop_discovery: Specifies whether stop_discovery should be
                 executed
        @returns: True if discovery is stopped
        """
        if stop_discovery:
            self.bluetooth_facade.stop_discovery()
        is_not_discovering = self._wait_for_condition(
            lambda: not self.bluetooth_facade.is_discovering(),
            method_name())
        return is_not_discovering

    def _wait_till_discovery_starts(self, start_discovery=True):
        """start discovery if specified and wait for discovery to start

        @params: start_discovery: Specifies whether start_discovery should be
                 executed
        @returns: True if discovery is started
        """

        if start_discovery:
            self.bluetooth_facade.start_discovery()
        is_discovering = self._wait_for_condition(
            self.bluetooth_facade.is_discovering, method_name())
        return is_discovering

    def _wait_till_power_off(self):
        """power off the adapter and wait for it to be powered off

        @returns: True if adapter can be powered off
        """

        power_off = self.bluetooth_facade.set_powered(False)
        is_powered_off = self._wait_for_condition(
                lambda: not self.bluetooth_facade.is_powered_on(),
                method_name())
        return is_powered_off

    def _wait_till_power_on(self):
        """power on the adapter and wait for it to be powered on

        @returns: True if adapter can be powered on
        """
        power_on = self.bluetooth_facade.set_powered(True)
        is_powered_on = self._wait_for_condition(
            self.bluetooth_facade.is_powered_on, method_name())
        return is_powered_on



########################################################################
# dbus call : start_discovery
#
#####################################################
# Positive cases
# Case 1
# preconditions: Adapter powered on AND
#                Currently not discovering
# result: Success
#
######################################################
# Negative cases
#
# Case 1
# preconditions: Adapter powered off
# result: Failure
# error : NotReady
#
# Case 2
# precondition: Adapter power on AND
#               Currently discovering
# result: Failure
# error: Inprogress
#########################################################################
    @_test_retry_and_log(False)
    def test_dbus_start_discovery_success(self):
        """ Test success case of start_discovery call. """
        is_power_on = self._wait_till_power_on()
        is_not_discovering = self._wait_till_discovery_stops()

        start_discovery, error =  self.bluetooth_facade.start_discovery()

        is_discovering = self._wait_till_discovery_starts(start_discovery=False)
        self.results = {'is_power_on' : is_power_on,
                        'is_not_discovering': is_not_discovering,
                        'start_discovery' : start_discovery,
                        'is_discovering': is_discovering
                        }
        return all(self.results.values())

    @_test_retry_and_log(False)
    def test_dbus_start_discovery_fail_discovery_in_progress(self):
        """ Test Failure case of start_discovery call.

        start discovery when discovery is in progress and confirm it fails with
        'org.bluez.Error.InProgress: Operation already in progress'.
        """

        is_discovering = self._wait_till_discovery_starts()

        start_discovery, error =  self.bluetooth_facade.start_discovery()
        self.results = {'is_discovering' : is_discovering,
                        'start_discovery_failed' : not start_discovery,
                        'error_matches' : error == DBUS_ERRORS['InProgress']}
        return all(self.results.values())

    @_test_retry_and_log(False)
    def test_dbus_start_discovery_fail_power_off(self):
        """ Test Failure case of start_discovery call.

        start discovery when adapter is turned off and confirm it fails with
        'NotReady' : 'org.bluez.Error.NotReady: Resource Not Ready'.
        """
        is_power_off = self._wait_till_power_off()

        start_discovery, error =  self.bluetooth_facade.start_discovery()

        is_power_on = self._wait_till_power_on()
        self.results = {'power_off' : is_power_off,
                        'start_discovery_failed' : not start_discovery,
                        'error_matches' : error == DBUS_ERRORS['NotReady'],
                        'power_on' : is_power_on}
        return all(self.results.values())

########################################################################
# dbus call : stop_discovery
#
#####################################################
# Positive cases
# Case 1
# preconditions: Adapter powered on AND
#                Currently discovering
# result: Success
#
#####################################################
# Negative cases
#
# Case 1
# preconditions: Adapter powered off
# result: Failure
# error : NotReady
#
# Case 2
# precondition: Adapter power on AND
#               Currently not discovering
# result: Failure
# error: Failed
#
#TODO
#Case 3  org.bluez.Error.NotAuthorized
#########################################################################

    @_test_retry_and_log(False)
    def test_dbus_stop_discovery_success(self):
        """ Test success case of stop_discovery call. """
        is_power_on = self._wait_till_power_on()
        is_discovering = self._wait_till_discovery_starts()

        stop_discovery, error =  self.bluetooth_facade.stop_discovery()
        is_not_discovering = self._wait_till_discovery_stops(
            stop_discovery=False)
        self.results = {'is_power_on' : is_power_on,
                        'is_discovering': is_discovering,
                        'stop_discovery' : stop_discovery,
                        'is_not_discovering' : is_not_discovering}
        return all(self.results.values())


    @_test_retry_and_log(False)
    def test_dbus_stop_discovery_fail_discovery_not_in_progress(self):
        """ Test Failure case of stop_discovery call.

        stop discovery when discovery is not in progress and confirm it fails
        with 'org.bluez.Error.Failed: No discovery started'.
        """
        is_not_discovering = self._wait_till_discovery_stops()

        stop_discovery, error =  self.bluetooth_facade.stop_discovery()

        still_not_discovering = self._wait_till_discovery_stops(
            stop_discovery=False)
        self.results = {
            'is_not_discovering' : is_not_discovering,
            'stop_discovery_failed' : not stop_discovery,
            'error_matches' : error == DBUS_ERRORS['Failed']['discovery'],
            'still_not_discovering': still_not_discovering}
        return all(self.results.values())


    @_test_retry_and_log(False)
    def test_dbus_stop_discovery_fail_power_off(self):
        """ Test Failure case of stop_discovery call.

        stop discovery when adapter is turned off and confirm it fails with
        'NotReady' : 'org.bluez.Error.NotReady: Resource Not Ready'.
        """

        is_power_off = self._wait_till_power_off()

        stop_discovery, error =  self.bluetooth_facade.stop_discovery()

        is_power_on = self._wait_till_power_on()
        self.results = {'is_power_off' : is_power_off,
                        'stop_discovery_failed' : not stop_discovery,
                        'error_matches' : error == DBUS_ERRORS['NotReady'],
                        'is_power_on' : is_power_on}
        return all(self.results.values())
