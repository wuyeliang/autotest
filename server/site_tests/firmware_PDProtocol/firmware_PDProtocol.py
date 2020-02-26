# Copyright 2016 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import re

from collections import defaultdict

from autotest_lib.client.common_lib import error
from autotest_lib.server.cros.faft.firmware_test import FirmwareTest
from autotest_lib.server.cros.servo import pd_console


class firmware_PDProtocol(FirmwareTest):
    """
    Servo based USB PD protocol test.

    A charger must be connected to the DUT for this test.

    This test checks that when an appropriate zinger charger is connected that
    the PD is properly negotiated in dev mode and when booted from a test image
    through recovery that the PD is not negotiated.

    Example:
    PD Successfully negotiated
    - ServoV4 in SRC_READY or SNK_READY state

    PD not negotiated
    - ServoV4 in SRC_DISCOVERY or SNK_DISCOVERY state

    """
    version = 1

    PD_NOT_SUPPORTED_PATTERN = 'INVALID_COMMAND'

    ECTOOL_CMD_DICT = defaultdict(lambda: 'ectool usbpdpower')

    def initialize(self, host, cmdline_args):
        """Initialize the test"""
        super(firmware_PDProtocol, self).initialize(host, cmdline_args)

        self.ECTOOL_CMD_DICT['samus'] = 'ectool --dev=1 usbpdpower'

        self.current_board = self.servo.get_board();

        self.check_if_pd_supported()
        self.switcher.setup_mode('dev')
        # The USB disk is used for recovery. But this test wants a fine-grained
        # control, i.e. swapping the role just before booting into recovery,
        # not swapping here. So set used_for_recovery=False.
        self.setup_usbkey(usbkey=True, host=False, used_for_recovery=False)

        self.original_dev_boot_usb = self.faft_client.system.get_dev_boot_usb()
        logging.info('Original dev_boot_usb value: %s',
                     str(self.original_dev_boot_usb))

    def cleanup(self):
        """Cleanup the test"""
        self.ensure_dev_internal_boot(self.original_dev_boot_usb)
        super(firmware_PDProtocol, self).cleanup()

    def check_if_pd_supported(self):
        """ Checks if the DUT responds to ectool usbpdpower and skips the test
        if it isn't supported on the device.
        """
        output = self.run_command(self.ECTOOL_CMD_DICT[self.current_board])

        if (not output or
            self.check_ec_output(output, self.PD_NOT_SUPPORTED_PATTERN)):
            raise error.TestNAError("PD not supported skipping test.")

    def boot_to_recovery(self):
        """Boot device into recovery mode."""
        logging.info('Reboot into Recovery...')
        self.switcher.reboot_to_mode(to_mode='rec')

        self.check_state((self.checkers.crossystem_checker,
                          {'mainfw_type': 'recovery'}))

    def run_command(self, command):
        """Runs the specified command and returns the output
        as a list of strings.

        @param command: The command to run on the DUT
        @return A list of strings of the command output
        """
        logging.info('Command to run: %s', command)

        output = self.faft_client.system.run_shell_command_get_output(command)

        logging.info('Command output: %s', output)

        return output

    def check_ec_output(self, output, pattern):
        """Checks if any line in the output matches the given pattern.

        @param output: A list of strings containg the output to search
        @param pattern: The regex to search the output for

        @return True upon first match found or False
        """
        logging.info('Checking %s for %s.', output, pattern)

        for line in output:
            if bool(re.search(pattern, line)):
                return True

        return False

    def run_once(self):
        """Main test logic"""
        self.pdtester_pd_utils = pd_console.PDConsoleUtils(self.pdtester)
        # TODO(b/35573842): Refactor to use PDPortPartner to probe the port
        self.pdtester_port = 1 if 'servo_v4' in self.pdtester.servo_type else 0
        self.SNK_PD_UNNEGOTIATED = self.pdtester_pd_utils.SNK_DISCOVERY
        self.SNK_CONNECT = self.pdtester_pd_utils.SNK_CONNECT
        self.SRC_CONNECT = self.pdtester_pd_utils.SRC_CONNECT

        self.ensure_dev_internal_boot(self.original_dev_boot_usb)

        # Check servo_v4 is negotiated and in SRC_DISCOVERY
        state = self.pdtester_pd_utils.get_pd_state(self.pdtester_port)
        logging.info('Checking PD negotiation, servo_v4 in %s' % state)
        if state != self.SRC_CONNECT:
            raise error.TestFail('Expect PD state %s, got %s',
                                 (self.SRC_CONNECT, state))

        self.set_servo_v4_role_to_snk(pd_comm=True)
        self.boot_to_recovery()

        # Check PD is not negotiated
        state = self.pdtester_pd_utils.get_pd_state(self.pdtester_port)
        logging.info('Checking PD no negotiation, servo_v4 in %s' % state)
        if state != self.SNK_PD_UNNEGOTIATED:
            raise error.TestFail(
                'Expect PD state %s, got %s, PD comm %sabled',
                (self.SNK_PD_UNNEGOTIATED, state, 'en'
                 if state in [self.SNK_CONNECT, self.SRC_CONNECT] else 'dis'))
