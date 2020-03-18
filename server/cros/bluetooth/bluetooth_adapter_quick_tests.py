# Copyright 2019 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""
This class provides wrapper functions for Bluetooth quick sanity test
batches or packages
"""

import functools
import logging
import threading
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
        # Restart the link to device
        logging.info('Restarting peer devices...')

        # Grab current device list for initialization
        connected_devices = self.devices
        self.cleanup(test_state='MID')

        for device_type, device_list in connected_devices.items():
            for device in device_list:
                if device is not None:
                    logging.info('Restarting %s', device_type)
                    self.get_device(device_type, on_start=False)


    def start_peers(self, devices):
        """Start peer devices"""
        # Start the link to devices
        if self.use_btpeer:
            logging.info('Starting peer devices...')
            self.get_device_rasp(devices)

    def _print_delimiter(self):
        logging.info('=======================================================')


    def quick_test_init(self, host, use_btpeer=True, use_chameleon=False,
                        flag='Quick Sanity'):
        """Inits the test batch"""
        self.host = host
        #factory can not be declared as local variable, otherwise
        #factory._proxy.__del__ will be invoked, which shutdown the xmlrpc
        # server, which log out the user.

        try:
            browser_args = ['--enable-features=BluetoothKernelSuspendNotifier']
            self.factory = remote_facade_factory.RemoteFacadeFactory(host,
                           extra_browser_args = browser_args,
                           disable_arc=True)
            self.bluetooth_facade = self.factory.create_bluetooth_hid_facade()

        # For b:142276989, catch 'object_path' fault and reboot to prevent
        # failures from continuing into future tests
        except Exception, e:
            if (e.__class__.__name__ == 'Fault' and
                """object has no attribute 'object_path'""" in str(e)):

                logging.error('Caught b/142276989, rebooting DUT')
                self.reboot()
            # Raise the original exception
            raise

        # Common list to track old/new Bluetooth peers
        # Adding chameleon to btpeer_list causes issue in cros_labels
        self.host.peer_list = []

        # Keep use_chameleon for any unmodified tests
        # TODO(b:149637050) Remove use_chameleon
        self.use_btpeer = use_btpeer or use_chameleon
        if self.use_btpeer:
            self.input_facade = self.factory.create_input_facade()
            self.check_btpeer()

            #
            # During the transition period in the lab, Bluetooth peer can be
            # name <hostname>-btpeer[1-4] or <hostname>-chameleon OR can be
            # specified on cmd line using btpeer_host or chameleon_host.
            #
            # TODO(b:149637050) Cleanup this code after M83 is in stable
            #
            logging.info('%s Bluetooth peers found',
                         len(self.host.btpeer_list))

            self.host.peer_list = self.host.btpeer_list[:]

            if (self.host._chameleon_host is not None and
                self.host.chameleon is not None):
                logging.info('Chameleon Bluetooth peer found')
                # If there is a peer named <hostname>-chameleon, append to the
                # peer list
                self.host.peer_list.append(self.host.chameleon)
                self.host.btpeer = self.host.peer_list[0]
            else:
                logging.info('chameleon Btpeer not found')

            logging.info('Total of %d peers. Peer list %s',
                         len(self.host.peer_list),
                         self.host.peer_list)
            logging.info('labels: %s', self.host.get_labels())

            if len(self.host.peer_list) == 0:
                raise error.TestFail('Unable to find a Bluetooth peer')

            # Query connected devices on our btpeer at init time
            self.available_devices = self.list_devices_available()


            for btpeer in self.host.peer_list:
                btpeer.register_raspPi_log(self.outputdir)

            self.btpeer_group = dict()
            # Create copy of btpeer_group
            self.btpeer_group_copy = dict()
            self.group_btpeers_type()


        # Clear the active devices for this test
        self.active_test_devices = {}

        self.enable_disable_debug_log(enable=True)

        # Delete files created in previous run
        self.host.run('[ ! -d {0} ] || rm -rf {0} || true'.format(
                                                    self.BTMON_DIR_LOG_PATH))
        self.start_new_btmon()
        self.start_new_usbmon()

        self.flag = flag
        self.test_iter = None

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
        self.mtbf_end = False
        self.mtbf_end_lock = threading.Lock()


    @staticmethod
    def quick_test_test_decorator(test_name, devices={}, flags=['All']):
        """A decorator providing a wrapper to a quick test.
           Using the decorator a test method can implement only the core
           test and let the decorator handle the quick test wrapper methods
           (test_start and test_end).

           @param test_name: the name of the test to log.
           @param devices:   list of device names which are going to be used
                             in the following test.
           @param flags: list of string to describe who should run the
                         test. The string could be one of the following:
                         ['AVL', 'Quick Sanity', 'All'].
        """

        def decorator(test_method):
            """A decorator wrapper of the decorated test_method.
               @param test_method: the test method being decorated.
               @returns the wrapper of the test method.
            """

            def _check_runnable(self):
                """Check if the test could be run"""

                # Check that the test is runnable in current setting
                if not(self.flag in flags or 'All' in flags):
                    logging.info('SKIPPING TEST %s', test_name)
                    logging.info('flag %s not in %s', self.flag, flags)
                    self._print_delimiter()
                    return False
                return True

            def _is_enough_peers_present(self):
                """Check if enough peer devices are available."""

                # Check that btpeer has all required devices before running
                for device_type, number in devices.items():
                    if self.available_devices.get(device_type, 0) < number:
                        logging.info('SKIPPING TEST %s', test_name)
                        logging.info('%s not available', device_type)
                        self._print_delimiter()
                        return False

                # Check if there are enough peers
                total_num_devices = sum(devices.values())
                if total_num_devices > len(self.host.peer_list):
                    logging.info('SKIPPING TEST %s', test_name)
                    logging.info('Number of devices required %s is greater'
                                 'than number of peers available %d',
                                 total_num_devices,
                                 len(self.host.peer_list))
                    self._print_delimiter()
                    return False
                return True

            @functools.wraps(test_method)
            def wrapper(self):
                """A wrapper of the decorated method."""
                if not _check_runnable(self):
                    return
                if not _is_enough_peers_present(self):
                    raise error.TestNAError('Not enough peer available')
                self.quick_test_test_start(test_name, devices)
                test_method(self)
                self.quick_test_test_end()
            return wrapper

        return decorator


    def quick_test_test_start(self, test_name=None, devices={}):
        """Start a quick test. The method clears and restarts adapter on DUT
           as well as peer devices. In addition the methods prints test start
           traces.
        """

        self.test_name = test_name

        # Reset the adapter
        self.test_reset_on_adapter()
        # Initialize bluetooth_adapter_tests class (also clears self.fails)
        self.initialize()
        # Start and peer HID devices
        self.start_peers(devices)

        if test_name is not None:
            time.sleep(self.TEST_SLEEP_SECS)
            self._print_delimiter()
            logging.info('Starting test: %s', test_name)
            self.log_message('Starting test: %s'% test_name)

    def quick_test_test_end(self):
        """Log and track the test results"""
        result_msgs = []

        if self.test_iter is not None:
            result_msgs += ['Test Iter: ' + str(self.test_iter)]

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
        self.log_message(result_msg)
        self._print_delimiter()
        self.bat_tests_results.append(result_msg)
        self.pkg_tests_results.append(result_msg)

        if self.test_name is not None:
            logging.info('Cleanning up and restarting towards next test...')

        self.bluetooth_facade.stop_discovery()

        # Store a copy of active devices for raspi reset in the final step
        self.active_test_devices = self.devices

        # Disconnect devices used in the test, and remove the pairing.
        for device_list in self.devices.values():
            for device in device_list:
                if device is not None:
                    logging.info('Clear device %s', device.name)
                    self.bluetooth_facade.disconnect_device(device.address)
                    device_is_paired = self.bluetooth_facade.device_is_paired(
                            device.address)
                    if device_is_paired:
                        self.bluetooth_facade.remove_device_object(
                                device.address)

        # Repopulate btpeer_group for next tests
        # Clear previous tets's leftover entries. Don't delete the
        # btpeer_group dictionary though, it'll be used as it is.
        if self.use_btpeer:
            for device_type in self.btpeer_group:
                if len(self.btpeer_group[device_type]) > 0:
                    del self.btpeer_group[device_type][:]

            # Repopulate
            self.group_btpeers_type()

        # Close the connection between peers
        self.cleanup(test_state='NEW')


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
                    for iter in xrange(1,num_iterations+1):
                        self.test_iter = iter
                        single_test_method()

                    if self.fails:
                        raise error.TestFail(self.fails)
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


    def quick_test_print_summary(self):
        """Print results summary of a test package"""
        logging.info('%s Test Package Summary: total pass %d, total fail %d',
                     self.pkg_name, self.pkg_pass_count, self.pkg_fail_count)
        for result in self.pkg_tests_results:
            logging.info(result)
        self._print_delimiter();


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
        """Print final result of a test package"""
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

        # Clear any raspi devices at very end of test
        for device_list in self.active_test_devices.values():
            for device in device_list:
                if device is not None:
                    self.clear_raspi_device(device)

        # Reset the adapter
        self.test_reset_on_adapter()
        # Initialize bluetooth_adapter_tests class (also clears self.fails)
        self.initialize()


    @staticmethod
    def quick_test_mtbf_decorator(timeout_mins):
        """A decorator enabling a test to be run as a MTBF test, it will run
           the underlying test in a infinite loop until it fails or timeout is
           reached, in both cases the time elapsed time will be reported.

           @param timeout_mins: the max execution time of the test, once the
                                time is up the test will report success and exit
        """

        def decorator(batch_method):
            """A decorator wrapper of the decorated batch_method.
               @param batch_method: the batch method being decorated.
               @returns the wrapper of the batch method.
            """

            @functools.wraps(batch_method)
            def wrapper(self, *args, **kwargs):
                """A wrapper of the decorated method"""
                self.mtbf_end = False
                mtbf_timer = threading.Timer(
                    timeout_mins * 60, self.mtbf_timeout)
                mtbf_timer.start()
                start_time = time.time()
                while True:
                    with self.mtbf_end_lock:
                        # The test ran the full duration without failure
                        if self.mtbf_end:
                            self.report_mtbf_result(
                                True, time.time() - start_time)
                            break
                    try:
                        batch_method(self, *args, **kwargs)
                    except Exception as e:
                        logging.info("Caught a failure: %r", e)
                        self.report_mtbf_result(False, time.time() - start_time)
                        break

                mtbf_timer.cancel()

            return wrapper

        return decorator


    def mtbf_timeout(self):
        """Handle time out event of a MTBF test"""
        with self.mtbf_end_lock:
            self.mtbf_end = True


    def report_mtbf_result(self, success, duration_secs):
        """Report MTBF report"""
        logging.info("Logging MTBF result: %r %r", success, duration_secs)