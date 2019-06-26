# Copyright 2019 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import logging

from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib import utils
from autotest_lib.server.cros.faft.firmware_test import FirmwareTest


class firmware_UpdateModes(FirmwareTest):
    """RO+RW firmware update using chromeos-firmwareupdate with various modes.

    This test uses --emulate, to avoid writing repeatedly to the flash.
    """

    version = 1

    SHELLBALL = '/usr/sbin/chromeos-firmwareupdate'

    def initialize(self, host, cmdline_args):
        self._fake_bios = 'fake-bios.bin'
        super(firmware_UpdateModes, self).initialize(host, cmdline_args)

    def local_run_cmd(self, command):
        """Execute command on local system.

        @param command: shell command to be executed on local system.
        @return: command output.
        """
        logging.info('Execute %s', command)
        output = utils.system_output(command)
        logging.info('Output %s', output)
        return output

    def get_fake_bios_fwids(self):
        return self.faft_client.Updater.GetInstalledFwid(
                'bios', ('ro', 'a', 'b'), self._fake_bios)

    def run_case(self, mode, write_protected, written, modify_ro=True,
                 should_abort=False):
        """Run chromeos-firmwareupdate with given sub-case

        @param mode: factory or recovery or autoupdate
        @param write_protected: is the flash write protected (--wp)?
        @param modify_ro: should ro fwid be modified?
        @param written: list of bios areas expected to change
        @param should_abort: if True, the updater should abort with no changes
        @return: a list of failure messages for the case
        """
        self.faft_client.Updater.ResetShellball()

        fake_bios_path = self.faft_client.Updater.CopyBios(self._fake_bios)
        before_fwids = {'bios': self.get_fake_bios_fwids()}

        case_desc = ('chromeos-firmwareupdate --mode=%s --wp=%s'
                     % (mode, write_protected))

        if modify_ro:
            append = 'ro+rw'
        else:
            case_desc += ' [rw-only]'
            append = 'rw'

        # Repack the shellball with modded fwids
        self.modify_shellball(append, modify_ro)
        modded_fwids = self.identify_shellball()

        options = ['--emulate', fake_bios_path, '--wp=%s' % write_protected]

        logging.info("%s (should write %s)", case_desc,
                     ', '.join(written).upper() or 'nothing')
        rc = self.faft_client.Updater.RunFirmwareupdate(mode, append, options)

        if should_abort and rc != 0:
            logging.debug('updater aborted as expected')

        after_fwids = {'bios': self.get_fake_bios_fwids()}
        expected_written = {'bios': written or []}

        errors = self.check_fwids_written(
                before_fwids, modded_fwids, after_fwids, expected_written)

        if not errors:
            logging.debug('...bios versions correct: %s', after_fwids['bios'])

        if should_abort and rc == 0:
            msg = ("...updater: with current mode and write-protect value, "
                   "should abort (rc!=0) and not modify anything")
            errors.insert(0, msg)

        if errors:
            case_message = '%s:\n%s' % (case_desc, '\n'.join(errors))
            logging.error('%s', case_message)
            return [case_message]
        return []

    def run_once(self, host):
        """Run test, iterating through combinations of mode and write-protect"""
        errors = []

        # TODO(dgoyette): Add a test that checks EC versions (can't be emulated)

        # factory: update A, B, and RO; reset gbb flags.  If WP=1, abort.
        errors += self.run_case('factory', 0, ['ro', 'a', 'b'])
        errors += self.run_case('factory', 1, [], should_abort=True)

        # recovery: update A and B, and RO if WP=0.
        errors += self.run_case('recovery', 0, ['ro', 'a', 'b'])
        errors += self.run_case('recovery', 1, ['a', 'b'])

        # autoupdate with changed ro: same as recovery (modify ro only if WP=0)
        errors += self.run_case('autoupdate', 0, ['ro', 'a', 'b'])
        errors += self.run_case('autoupdate', 1, ['b'])

        # autoupdate with unchanged ro: update inactive slot
        errors += self.run_case('autoupdate', 0, ['b'], modify_ro=False)
        errors += self.run_case('autoupdate', 1, ['b'], modify_ro=False)

        if len(errors) == 1:
            raise error.TestFail(errors[0])
        elif errors:
            raise error.TestFail(
                    '%s combinations of mode and write-protect failed:\n%s' %
                    (len(errors), '\n'.join(errors)))
