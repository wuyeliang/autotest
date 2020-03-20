# Copyright 2020 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os

from autotest_lib.client.common_lib import error
from autotest_lib.server.cros.faft.firmware_test import FirmwareTest
from autotest_lib.server.cros.faft.firmware_test import ConnectionError


class firmware_WriteProtectFunc(FirmwareTest):
    """
    This test checks whether the SPI flash write-protection functionally works
    """
    version = 1

    def initialize(self, host, cmdline_args, dev_mode=False):
        """Initialize the test"""
        super(firmware_WriteProtectFunc, self).initialize(host, cmdline_args)
        self.switcher.setup_mode('dev' if dev_mode else 'normal')
        self._original_wp = 'on' in self.servo.get('fw_wp_state')
        self.backup_firmware()

    def cleanup(self):
        """Cleanup the test"""
        try:
            if self.is_firmware_saved():
                self.restore_firmware()
        except ConnectionError:
            logging.error("ERROR: DUT did not come up after firmware restore!")
        try:
            if hasattr(self, '_original_wp'):
              self.set_hardware_write_protect(self._original_wp)
        except Exception as e:
            logging.error('Caught exception: %s', str(e))
        super(firmware_WriteProtectFunc, self).cleanup()

    def run_cmd(self, command, checkfor=''):
        """
        Log and execute command and return the output.

        @param command: Command to execute on device.
        @param checkfor: If not empty, make the test fail when this param
            is not found in the command output.
        @returns the output of command.
        """
        command = command + ' 2>&1'
        logging.info('Execute %s', command)
        output = self.faft_client.system.run_shell_command_get_output(command)
        logging.info('Output >>> %s <<<', output)
        if checkfor and checkfor not in '\n'.join(output):
            raise error.TestFail('Expect %s in output of %s' %
                                 (checkfor, '\n'.join(output)))
        return output

    def get_wp_ro_firmware_section(self, firmware_file, wp_ro_firmware_file):
        """
        Read out WP_RO section from the firmware file.

        @param firmware_file: The AP or EC firmware binary to be parsed.
        @param wp_ro_firmware_file: The file path for the WP_RO section
            dumped from the firmware_file.
        @returns the output of the dd command.
        """
        cmd_output = self.run_cmd(
                'futility dump_fmap -p %s WP_RO'% firmware_file)
        if cmd_output:
            unused_name, offset, size = cmd_output[0].split()

        return self.run_cmd('dd bs=1 skip=%s count=%s if=%s of=%s' %
                            (offset, size, firmware_file, wp_ro_firmware_file))

    def run_once(self):
        """Runs a single iteration of the test."""
        work_path = self.faft_client.updater.get_work_path()

        bios_ro_before = os.path.join(work_path, 'bios_ro_before.bin')
        bios_ro_after = os.path.join(work_path, 'bios_ro_after.bin')
        bios_ro_test = os.path.join(work_path, 'bios_ro_test.bin')
        ec_ro_before = os.path.join(work_path, 'ec_ro_before.bin')
        ec_ro_after = os.path.join(work_path, 'ec_ro_after.bin')
        ec_ro_test = os.path.join(work_path, 'ec_ro_test.bin')

        # Use the firmware blobs unpacked from the firmware updater for
        # testing. To ensure there is difference in WP_RO section between
        # the firmware on the DUT and the firmware unpacked from the firmware
        # updater, we mess around FRID.

        self.faft_client.updater.modify_fwids('bios', ['ro'])
        self.faft_client.updater.modify_fwids('ec', ['ro'])

        bios_test = os.path.join(work_path,
                self.faft_client.updater.get_bios_relative_path())
        ec_test = os.path.join(work_path,
                self.faft_client.updater.get_ec_relative_path())

        self.get_wp_ro_firmware_section(bios_test, bios_ro_test)
        self.get_wp_ro_firmware_section(ec_test, ec_ro_test)

        # Check if RO FW really can't be overwritten when WP is enabled.
        self.switcher.mode_aware_reboot(
                'custom',
                lambda:self.set_ec_write_protect_and_reboot(True))
        self.faft_client.bios.set_write_protect_region('WP_RO', True)

        self.run_cmd('flashrom -p host -r -i WP_RO:%s' % bios_ro_before,
                     'SUCCESS')
        self.run_cmd('flashrom -p ec -r -i WP_RO:%s' % ec_ro_before,
                     'SUCCESS')
        # Writing WP_RO section is expected to fail.
        self.run_cmd('flashrom -p host -w -i WP_RO:%s' % bios_ro_test, 'FAIL')
        self.run_cmd('flashrom -p ec -w -i WP_RO:%s' % ec_ro_test, 'FAIL')

        self.run_cmd('flashrom -p host -r -i WP_RO:%s' % bios_ro_after,
                     'SUCCESS')
        self.run_cmd('flashrom -p ec -r -i WP_RO:%s' % ec_ro_after,
                     'SUCCESS')

        self.switcher.mode_aware_reboot(reboot_type='cold')

        # The WP_RO section on the DUT should not change.
        cmp_output = self.run_cmd('cmp %s %s' %
                (bios_ro_before, bios_ro_after))
        if ''.join(cmp_output) != '':
            raise error.TestFail('BIOS RO changes when WP is on!')
        cmp_output = self.run_cmd('cmp %s %s' % (ec_ro_before, ec_ro_after))
        if ''.join(cmp_output) != '':
            raise error.TestFail('EC RO changes when WP is on!')

        # Check if RO FW can be overwritten when WP is disabled.
        self.switcher.mode_aware_reboot(
                'custom',
                lambda:self.set_ec_write_protect_and_reboot(False))
        self.faft_client.bios.set_write_protect_region('WP_RO', False)

        # Writing WP_RO section is expected to succeed.
        self.run_cmd('flashrom -p host -w -i WP_RO:%s' % bios_ro_test,
                     'SUCCESS')
        self.run_cmd('flashrom -p ec -w -i WP_RO:%s' % ec_ro_test,
                     'SUCCESS')

        self.run_cmd('flashrom -p host -r -i WP_RO:%s' % bios_ro_after,
                     'SUCCESS')
        self.run_cmd('flashrom -p ec -r -i WP_RO:%s' % ec_ro_after,
                     'SUCCESS')

        # The WP_RO section on the DUT should be the same as the test firmware.
        cmp_output = self.run_cmd('cmp %s %s' % (bios_ro_test, bios_ro_after))
        if ''.join(cmp_output) != '':
            raise error.TestFail('BIOS RO is not flashed correctly'
                                 'when WP is off!')
        cmp_output = self.run_cmd('cmp %s %s' % (ec_ro_test, ec_ro_after))
        if ''.join(cmp_output) != '':
            raise error.TestFail('EC RO is not flashed correctly'
                                 'when WP is off!')
