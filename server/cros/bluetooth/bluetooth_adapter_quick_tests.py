# Copyright 2019 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""
This class provides wrapper functions for Bluetooth quick sanity test
batches or packages
"""

import functools
import logging
import time

from autotest_lib.client.common_lib import error
from autotest_lib.server.cros.bluetooth import bluetooth_adapter_tests
from autotest_lib.server.cros.multimedia import remote_facade_factory


class BluetoothAdapterQuickTests(bluetooth_adapter_tests.BluetoothAdapterTests):
    """This class provide wrapper function for Bluetooth quick sanity test
    batches or packages.
    The Bluetooth quick test infrastructure provides a way to quickly run a set
    of tests. As for today, auto-test ramp up time per test is about 90-120
    seconds, where a typical Bluetooth test may take ~30-60 seconds to run.

    The quick test infra, implemented in this class, saves this huge overhead
    by running only the minimal reset and cleanup operations required between
    each set of tests (takes a few seconds).

    This class provides wrapper functions to start and end a test, a batch or a
    package. A batch is defined as a set of tests, preferably with a common
    subject. A package is a set of batches.
    This class takes care of tests, batches, and packages test results, and
    prints out summaries to results. The class also resets and cleans up
    required states between tests, batches and packages.

    A batch can also run as a separate auto-test. There is a place holder to
    add a way to run a specific test of a batch autonomously.

    A batch can be implemented by inheriting from this class, and using its
    wrapper functions. A package can be implemented by inheriting from a set of
    batches.

    Adding a test to one of the batches is as easy as adding a method to the
    class of the batch.
    """

    # Some delay is needed between tests. TODO(yshavit): investigate and remove
    TEST_SLEEP_SECS = 3


    def restart_peers(self):
        """Restart and clear peer devices"""
        # Restart the link to HID device
        logging.info('Restarting peer devices...')
        self.cleanup()
        self.devices['BLE_MOUSE'] = None
        self.device = self.get_device('BLE_MOUSE')


    def _print_delimiter(self):
        logging.info('=======================================================')


    def quick_test_init(self, host):
        """Inits the test batch"""
        factory = remote_facade_factory.RemoteFacadeFactory(host)
        self.device = None
        self.host = host
        self.bluetooth_facade = factory.create_bluetooth_hid_facade()
        self.input_facade = factory.create_input_facade()
        self.check_chameleon()

        self.bat_tests_results = []
        self.bat_pass_count = 0
        self.bat_fail_count = 0
        self.bat_name = None
        self.bat_iter = None

        self.pkg_tests_results = []
        self.pkg_pass_count = 0
        self.pkg_fail_count = 0
        self.pkg_name = None
        self.pkg_iter = None
        self.pkg_is_running = False


    @staticmethod
    def quick_test_test_decorator(test_name):
        """A decorator providing a wrapper to a quick test.
           Using the decorator a test method can implement only the core
           test and let the decorator handle the quick test wrapper methods
           (test_start and test_end).

           @param test_name: the name of the test to log
        """

        def decorator(test_method):
            """A decorator wrapper of the decorated test_method.
               @param test_method: the test method being decorated.
               @returns the wrapper of the test method.
            """

            @functools.wraps(test_method)
            def wrapper(self):
                self.quick_test_test_start(test_name)
                test_method(self)
                self.quick_test_test_end()
            return wrapper

        return decorator


    def quick_test_test_start(self, test_name=None):
        """Start a quick test. The method clears and restarts adapter on DUT
           as well as peer devices. In addition the methods prints test start
           traces.
        """
        self.test_name = test_name
        if test_name is not None:
            logging.info('Cleanning up and restarting towards next test...')

        self.bluetooth_facade.stop_discovery()
        # Disconnect the device, and remove the pairing.
        if self.device is not None:
            self.bluetooth_facade.disconnect_device(self.device.address)
            device_is_paired = self.bluetooth_facade.device_is_paired(
                    self.device.address)
            if device_is_paired:
                self.bluetooth_facade.remove_device_object(
                        self.device.address)
        # Reset the adapter
        self.test_reset_on_adapter()
        # Restart and clear peer HID device
        self.restart_peers()
        # Initialize bluetooth_adapter_tests class (also clears self.fails)
        self.initialize()
        if test_name is not None:
            time.sleep(self.TEST_SLEEP_SECS)
            self._print_delimiter()
            logging.info('Starting test: %s', test_name)

    def quick_test_test_end(self):
        """Log and track the test results"""
        result_msgs = []

        if self.bat_iter is not None:
            result_msgs += ['Batch Iter: ' + str(self.bat_iter)]

        if self.pkg_is_running is True:
            result_msgs += ['Package iter: ' + str(self.pkg_iter)]

        if self.bat_name is not None:
            result_msgs += ['Batch Name: ' + self.bat_name]

        if self.test_name is not None:
            result_msgs += ['Test Name: ' + self.test_name]

        result_msg = ", ".join(result_msgs)

        if not bool(self.fails):
            result_msg = 'PASSED | ' + result_msg
            self.bat_pass_count += 1
            self.pkg_pass_count += 1
        else:
            result_msg = 'FAIL   | ' + result_msg
            self.bat_fail_count += 1
            self.pkg_fail_count += 1

        logging.info(result_msg)
        self._print_delimiter()
        self.bat_tests_results.append(result_msg)
        self.pkg_tests_results.append(result_msg)

    @staticmethod
    def quick_test_batch_decorator(batch_name):
        """A decorator providing a wrapper to a batch.
           Using the decorator a test batch method can implement only its
           core tests invocations and let the decorator handle the wrapper,
           which is taking care for whether to run a specific test or the
           batch as a whole and and running the batch in iterations

           @param batch_name: the name of the batch to log
        """

        def decorator(batch_method):
            """A decorator wrapper of the decorated test_method.
               @param test_method: the test method being decorated.
               @returns the wrapper of the test method.
            """

            @functools.wraps(batch_method)
            def wrapper(self, num_iterations=1, test_name=None):
                """A wrapper of the decorated method.
                  @param num_iterations: how many interations to run
                  @param test_name: specifc test to run otherwise None to run
                                    the whole batch
                """
                if test_name is not None:
                    single_test_method = getattr(self,  test_name)
                    single_test_method()
                else:
                    for iter in xrange(1,num_iterations+1):
                        self.quick_test_batch_start(batch_name, iter)
                        batch_method(self, num_iterations, test_name)
                        self.quick_test_batch_end()
            return wrapper

        return decorator


    def quick_test_batch_start(self, bat_name, iteration=1):
        """Start a test batch. The method clears and set batch variables"""
        self.bat_tests_results = []
        self.bat_pass_count = 0
        self.bat_fail_count = 0
        self.bat_name = bat_name
        self.bat_iter = iteration


    def quick_test_batch_end(self):
        """Print results summary of a test batch"""
        logging.info('%s Test Batch Summary: total pass %d, total fail %d',
                     self.bat_name, self.bat_pass_count, self.bat_fail_count)
        for result in self.bat_tests_results:
            logging.info(result)
        self._print_delimiter();
        if self.bat_fail_count > 0:
            logging.error('===> Test Batch Failed! More than one failure')
            self._print_delimiter();
            if self.pkg_is_running is False:
                raise error.TestFail(self.bat_tests_results)
        else:
           logging.info('===> Test Batch Passed! zero failures')
           self._print_delimiter();


    def quick_test_package_start(self, pkg_name):
        """Start a test package. The method clears and set batch variables"""
        self.pkg_tests_results = []
        self.pkg_pass_count = 0
        self.pkg_fail_count = 0
        self.pkg_name = pkg_name
        self.pkg_is_running = True


    def quick_test_package_update_iteration(self, iteration):
        """Update state and print log per package iteration.
           Must be called to have a proper package test result tracking.
        """
        self.pkg_iter = iteration
        if self.pkg_name is None:
            logging.error('Error: no quick package is running')
            raise error.TestFail('Error: no quick package is running')
        logging.info('Starting %s Test Package iteration %d',
                     self.pkg_name, iteration)


    def quick_test_package_end(self):
        """Print results summary of a test package"""
        logging.info('%s Test Package Summary: total pass %d, total fail %d',
                     self.pkg_name, self.pkg_pass_count, self.pkg_fail_count)
        for result in self.pkg_tests_results:
            logging.info(result)
        self._print_delimiter();
        if self.pkg_fail_count > 0:
            logging.error('===> Test Package Failed! More than one failure')
            self._print_delimiter();
            raise error.TestFail(self.bat_tests_results)
        else:
           logging.info('===> Test Package Passed! zero failures')
           self._print_delimiter();
        self.pkg_is_running = False


    def quick_test_cleanup(self):
        """ Cleanup any state test server and all device"""
        self.quick_test_test_start()
