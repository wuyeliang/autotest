# Copyright 2019 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Bluetooth DBus API tests."""


import logging

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
       DBus APIs. It tests both success and failures cases of each API. It
       checks the following
       - Expected return value
       - Expected exceptions for negative cases
       - Expected change in Dbus variables
       - TODO Expected change in (hci) state of the adapter
    """

    def _reset_state(self):
        """ Reset adapter to a known state.
        These tests changes adapter state. This function resets the adapter
        to known state

        @returns True if reset was successful False otherwise

        """
        logging.debug("resetting state of the adapter")
        power_off = self._wait_till_power_off()
        power_on = self._wait_till_power_on()
        not_discovering = self._wait_till_discovery_stops()
        # unpause_discovery will fail if discovery is not paused
        self.bluetooth_facade.unpause_discovery(False)
        reset_results = {'power_off' : power_off,
                         'power_on' : power_on,
                         'not_discovering' : not_discovering}
        if not all(reset_results.values()):
            logging.error('_reset_state failed %s',reset_results)
            return False
        else:
            return True

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
        reset = self._reset_state()
        is_power_on = self._wait_till_power_on()
        is_not_discovering = self._wait_till_discovery_stops()

        start_discovery, error =  self.bluetooth_facade.start_discovery()

        is_discovering = self._wait_till_discovery_starts(start_discovery=False)
        self.results = {'reset' : reset,
                        'is_power_on' : is_power_on,
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
        reset = self._reset_state()
        is_discovering = self._wait_till_discovery_starts()

        start_discovery, error =  self.bluetooth_facade.start_discovery()

        self.results = {'reset' : reset,
                        'is_discovering' : is_discovering,
                        'start_discovery_failed' : not start_discovery,
                        'error_matches' : error == DBUS_ERRORS['InProgress']}
        return all(self.results.values())

    @_test_retry_and_log(False)
    def test_dbus_start_discovery_fail_power_off(self):
        """ Test Failure case of start_discovery call.

        start discovery when adapter is turned off and confirm it fails with
        'NotReady' : 'org.bluez.Error.NotReady: Resource Not Ready'.
        """
        reset = self._reset_state()
        is_power_off = self._wait_till_power_off()

        start_discovery, error =  self.bluetooth_facade.start_discovery()

        is_power_on = self._wait_till_power_on()
        self.results = {'reset' : reset,
                        'power_off' : is_power_off,
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
        reset = self._reset_state()
        is_power_on = self._wait_till_power_on()
        is_discovering = self._wait_till_discovery_starts()

        stop_discovery, error =  self.bluetooth_facade.stop_discovery()
        is_not_discovering = self._wait_till_discovery_stops(
            stop_discovery=False)
        self.results = {'reset' : reset,
                        'is_power_on' : is_power_on,
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
        reset = self._reset_state()
        is_not_discovering = self._wait_till_discovery_stops()

        stop_discovery, error =  self.bluetooth_facade.stop_discovery()

        still_not_discovering = self._wait_till_discovery_stops(
            stop_discovery=False)

        self.results = {
            'reset' : reset,
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
        reset = self._reset_state()
        is_power_off = self._wait_till_power_off()

        stop_discovery, error =  self.bluetooth_facade.stop_discovery()

        is_power_on = self._wait_till_power_on()
        self.results = {'reset' : reset,
                        'is_power_off' : is_power_off,
                        'stop_discovery_failed' : not stop_discovery,
                        'error_matches' : error == DBUS_ERRORS['NotReady'],
                        'is_power_on' : is_power_on}
        return all(self.results.values())


########################################################################
# dbus call: pause_discovery
# arguments: boolean system_suspend_resume
# returns : True/False
# Notes: 1: argument system_suspend_resume is ignored in the code
#        2: pause/unpause state is not reflected in Discovering state
#####################################################
# Positive cases
# Case 1
# preconditions: Adapter powered on AND
#                Currently discovering
# Argument: [True|False]
# result: Success
# Case 2
# preconditions: Adapter powered on AND
#                Currently not discovering
# Argument: [True|False]
# result: Success
######################################################
# Negative cases
#
# Case 1
# preconditions: Adapter powered off
# result: Failure
# error : NotReady
# postconditions: Discovery can be started after power on
#
# Case 2
# precondition: Adapter powered on AND
#               Discovery paused
# result: Failure
# error: Busy
#########################################################################

    @_test_retry_and_log(False)
    def test_dbus_pause_discovery_success(self):
        """ Test success case of pause_discovery call. """
        reset = self._reset_state()
        is_discovering = self._wait_till_discovery_starts()
        pause_discovery, error = self.bluetooth_facade.pause_discovery(False)

        #TODO: Confirm discovery is paused by check the state of the adapter

        self.results = {'reset' : reset,
                        'is_discovering': is_discovering,
                        'pause_discovery' : pause_discovery,
                        }
        return all(self.results.values())

    @_test_retry_and_log(False)
    def test_dbus_pause_discovery_success_no_discovery_in_progress(self):
        """ Test success case of pause_discovery call. """
        reset = self._reset_state()
        is_power_on = self._wait_till_power_on()
        is_not_discovering = self._wait_till_discovery_stops()

        pause_discovery, error = self.bluetooth_facade.pause_discovery(False)

        #TODO: Confirm discovery is paused by check the state of the adapter

        self.results = {'reset' : reset,
                        'is_power_on' : is_power_on,
                        'is_not_discovering': is_not_discovering,
                        'pause_discovery' : pause_discovery,
                        }
        return all(self.results.values())

    @_test_retry_and_log(False)
    def test_dbus_pause_discovery_fail_power_off(self):
        """ Test Failure case of pause_discovery call.

        pause discovery when adapter is turned off and confirm it fails with
        'NotReady' : 'org.bluez.Error.NotReady: Resource Not Ready'.
        Also check we are able to start discovery after power on
        """
        reset = self._reset_state()
        is_power_off = self._wait_till_power_off()

        pause_discovery, error = self.bluetooth_facade.pause_discovery()

        is_power_on = self._wait_till_power_on()
        discovery_started = self._wait_till_discovery_starts()

        self.results = {'reset' : reset,
                        'is_power_off' : is_power_off,
                        'pause_discovery_failed' : not pause_discovery,
                        'error_matches' : error == DBUS_ERRORS['NotReady'],
                        'is_power_on' : is_power_on,
                        'discovery_started' : discovery_started
                       }
        return all(self.results.values())

    @_test_retry_and_log(False)
    def test_dbus_pause_discovery_fail_already_paused(self):
        """ Test failure case of pause_discovery call.

        Call pause discovery twice and make sure second call fails
        with 'org.bluez.Error.InProgress: Operation already in progress'.
        """
        reset = self._reset_state()
        is_power_on = self._wait_till_power_on()
        is_discovering = self._wait_till_discovery_starts()
        pause_discovery, _ = self.bluetooth_facade.pause_discovery()

        pause_discovery_again, error = self.bluetooth_facade.pause_discovery()
        #TODO: Confirm discovery is paused by check the state of the adapter

        self.results = {'reset' : reset,
                        'is_power_on' : is_power_on,
                        'is_discovering': is_discovering,
                        'pause_discovery' : pause_discovery,
                        'pause_discovery_failed' : not pause_discovery_again,
                        'error_matches' : error == DBUS_ERRORS['InProgress'],
                        }
        return all(self.results.values())


########################################################################
# dbus call: get_suppported_capabilities
# arguments: None
# returns : The dictionary is following the format
#           {capability : value}, where:
#
#           string capability:  The supported capability under
#                       discussion.
#           variant value:      A more detailed description of
#                       the capability.
#####################################################
# Positive cases
# Case 1
# Precondition: Adapter Powered on
# results: Result dictionary returned
#
# Case 2
# Precondition: Adapter Powered Off
# result : Result dictionary returned
################################################################################

    @_test_retry_and_log(False)
    def test_dbus_get_supported_capabilities_success(self):
        """ Test success case of get_supported_capabilities call. """
        reset = self._reset_state()
        is_power_on = self._wait_till_power_on()

        capabilities, error = self.bluetooth_facade.get_supported_capabilities()
        logging.debug('supported capabilities is %s', capabilities)

        self.results = {'reset' : reset,
                        'is_power_on' : is_power_on,
                        'get_supported_capabilities': error is None
                        }
        return all(self.results.values())

    @_test_retry_and_log(False)
    def test_dbus_get_supported_capabilities_success_power_off(self):
        """ Test success case of get_supported_capabilities call.
        Call get_supported_capabilities call with adapter powered off and
        confirm that it succeeds
        """

        reset = self._reset_state()
        is_power_off = self._wait_till_power_off()

        capabilities, error = self.bluetooth_facade.get_supported_capabilities()
        logging.debug('supported capabilities is %s', capabilities)

        self.results = {'reset' : reset,
                        'is_power_off' : is_power_off,
                        'get_supported_capabilities': error is None,
                        }
        return all(self.results.values())
