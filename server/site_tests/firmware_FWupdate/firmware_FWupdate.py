# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os

from chromite.lib import remote_access
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib import utils
from autotest_lib.server.cros.faft.firmware_test import FirmwareTest


class firmware_FWupdate(FirmwareTest):
    """RO+RW firmware update using chromeos-firmware with various modes.
    If custom images are supplied, the DUT is left running that firmware, so the
    test can be used to apply updates.  Otherwise, it modifies the FWIDs of the
    current firmware before flashing, and restores the firmware after the test.

    Accepted --args names:

    mode=[recovery|factory]
        Run test with the given mode (default 'recovery')

    new_bios=
    new_ec=
    new_pd=
        apply the given image(s) instead of generating an update with fake fwids

    """

    def initialize(self, host, cmdline_args):

        self.images_specified = False
        self.flashed = False

        dict_args = utils.args_to_dict(cmdline_args)
        super(firmware_FWupdate, self).initialize(host, cmdline_args)

        self.new_bios = dict_args.get('new_bios', None)
        self.new_ec = dict_args.get('new_ec', None)
        self.new_pd = dict_args.get('new_pd', None)

        if self.new_bios:
            self.images_specified = True
            if not os.path.isfile(self.new_bios):
                raise error.TestError('Specified BIOS file does not exist: %s'
                                      % self.new_bios)
            logging.info('new_bios=%s', self.new_bios)

        if self.new_ec:
            self.images_specified = True
            if not os.path.isfile(self.new_ec):
                raise error.TestError('Specified EC file does not exist: %s'
                                      % self.new_ec)
            logging.info('new_ec=%s', self.new_ec)

        if self.new_pd:
            self.images_specified = True
            if not os.path.isfile(self.new_pd):
                raise error.TestError('Specified PD file does not exist: %s'
                                      % self.new_pd)
            logging.info('new_pd=%s', self.new_pd)

        if not self.images_specified:
            self.backup_firmware()

        self.set_hardware_write_protect(False)

        self.mode = dict_args.get('mode', 'recovery')

        if self.mode not in ('factory', 'recovery'):
            raise error.TestError('Unhandled mode: %s' % self.mode)

    def get_installed_versions(self):
        """Get the installed versions of BIOS and EC firmware.

        @return: A nested dict keyed by target ('bios' or 'ec') and then section
        @rtype: dict
        """
        versions = dict()
        versions['bios'] = self.faft_client.Updater.GetAllInstalledFwids('bios')
        if self.faft_config.chrome_ec:
            versions['ec'] = self.faft_client.Updater.GetAllInstalledFwids('ec')
        return versions

    def copy_cmdline_images(self, hostname):
        """Copy the specified command line images into the extracted shellball.

        @param hostname: hostname (not the Host object) to copy to
        """
        bios_path = None
        ec_path = None
        pd_path = None
        if self.new_bios or self.new_ec or self.new_pd:

            extract_dir = self.faft_client.Updater.GetWorkPath()

            dut_access = remote_access.RemoteDevice(hostname, username='root')

            # Replace bin files.
            if self.new_bios:
                bios_rel = self.faft_client.Updater.GetBiosRelativePath()
                bios_path = os.path.join(extract_dir, bios_rel)
                dut_access.CopyToDevice(self.new_bios, bios_path, mode='scp')

            if self.new_ec:
                ec_rel = self.faft_client.Updater.GetEcRelativePath()
                ec_path = os.path.join(extract_dir, ec_rel)
                dut_access.CopyToDevice(self.new_ec, ec_path, mode='scp')

            if self.new_pd:
                # note: pd.bin might likewise need special path logic
                pd_path = os.path.join(extract_dir, 'pd.bin')
                dut_access.CopyToDevice(self.new_pd, pd_path, mode='scp')

        return (bios_path, ec_path, pd_path)

    def run_once(self, host):
        """Run chromeos-firmwareupdate with recovery or factory mode.

        @param host: host to run on
        """
        mode = self.mode
        append = 'new'
        have_ec = bool(self.faft_config.chrome_ec)

        self.faft_client.Updater.ExtractShellball()

        before_fwids = self.get_installed_versions()

        # Repack shellball with modded fwids
        if self.images_specified:
            # Use new images as-is
            logging.info(
                    "Applying specified image(s):"
                    "new_bios=%s, new_ec=%s, new_pd=%s",
                    self.new_bios, self.new_ec, self.new_pd)
            self.copy_cmdline_images(host.hostname)
            self.faft_client.Updater.RepackShellball(append)
            modded_fwids = self.identify_shellball(include_ec=have_ec)
        else:
            # Modify the stock image
            logging.info("Applying current firmware with modified fwids")
            self.modify_shellball(append, modify_ro=True, modify_ec=have_ec)
            modded_fwids = self.identify_shellball(include_ec=have_ec)

        case_desc = 'chromeos-firmwareupdate --mode=%s --wp=0' % mode

        logging.info("Run %s", case_desc)

        # make sure we restore firmware after the test, if it tried to flash.
        self.flashed = True
        self.faft_client.Updater.RunFirmwareupdate(mode, append, ['--wp=0'])

        after_fwids = self.get_installed_versions()

        errors = self.check_fwids_written(
                before_fwids, modded_fwids, after_fwids,
                {'bios': ['ro', 'a', 'b'], 'ec': ['ro', 'rw']})

        if not errors:
            logging.debug('versions correct: %s', after_fwids)

        if len(errors) == 1:
            raise error.TestFail(errors[0])
        elif errors:
            errors.insert(0, "%s: %s problems" % (case_desc, len(errors)))
            raise error.TestFail('\n'.join(errors))

    def cleanup(self):
        """
        If test was given custom images to apply, reboot the EC to apply them.

        Otherwise, restore firmware from the backup taken before flashing.
        No EC reboot is needed in that case, because the test didn't actually
        reboot the EC with the new firmware.
        """
        if self.flashed:
            if self.images_specified:
                self.sync_and_ec_reboot('hard')
            else:
                if self.faft_config.chrome_ec:
                    self.faft_client.Ec.Reload()
                logging.info("Restoring firmware")
                self.restore_firmware()

        super(firmware_FWupdate, self).cleanup()
