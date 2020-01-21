# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


""" The autotest performing FW update, both EC and AP."""


import logging
import sys

from autotest_lib.client.common_lib import error
from autotest_lib.server import test


class provision_FirmwareUpdate(test.test):
    """A test that can provision a machine to the correct firmware version."""

    version = 1


    def stage_image_to_usb(self, host):
        """Stage the current ChromeOS image on the USB stick connected to the
        servo.

        @param host:  a CrosHost object of the machine to update.
        """
        info = host.host_info_store.get()
        if not info.build:
            logging.warning('Failed to get build label from the DUT, skip '
                            'staging ChromeOS image on the servo USB stick.')
        else:
            _, update_url = host.stage_image_for_servo(info.build)
            host.servo.image_to_servo_usb(update_url)
            logging.debug('ChromeOS image %s is staged on the USB stick.',
                          info.build)

    def get_ro_firmware_ver(self, host):
        """Get the RO firmware version from the host."""
        result = host.run('crossystem ro_fwid', ignore_status=True)
        if result.exit_status == 0:
            # The firmware ID is something like "Google_Board.1234.56.0".
            # Remove the prefix "Google_Board".
            return result.stdout.split('.', 1)[1]
        else:
            return None

    def get_rw_firmware_ver(self, host):
        """Get the RW firmware version from the host."""
        result = host.run('crossystem fwid', ignore_status=True)
        if result.exit_status == 0:
            # The firmware ID is something like "Google_Board.1234.56.0".
            # Remove the prefix "Google_Board".
            return result.stdout.split('.', 1)[1]
        else:
            return None

    def run_once(self, host, value, rw_only=False, stage_image_to_usb=False,
                flash_device=None, get_release_from_image_archive=False):
        """The method called by the control file to start the test.

        @param host:  a CrosHost object of the machine to update.
        @param value: the provisioning value, which is the build version
                      to which we want to provision the machine,
                      e.g. 'link-firmware/R22-2695.1.144'.
        @param rw_only: True to only update the RW firmware.
        @param stage_image_to_usb: True to stage the current ChromeOS image on
                the USB stick connected to the servo. Default is False.
        @param flash_device: Servo V4 Flash Device name.
                             Use this to choose one other than the default
                             device when  servod has run in dual V4 device mode.
                             e.g. flash_device='ccd_cr50'
        @raise TestFail: if the firmware version remains unchanged.
               TestNAError: if the test environment is not properly set.
                            e.g. the servo type doesn't support this test.
        """
        orig_act_dev = None

        if flash_device == 'ccd_cr50':
            servo_type = host.servo.get_servo_version()
            if flash_device not in servo_type:
                raise error.TestNAError('Unsupporting servo type: %s' %
                                        servo_type)
        try:
            host.repair_servo()

            # Stage the current CrOS image to servo USB stick.
            if stage_image_to_usb:
                self.stage_image_to_usb(host)

            if flash_device == 'ccd_cr50':
                orig_act_dev = host.servo.get('active_v4_device').strip()
                host.servo.set('active_v4_device', 'ccd_cr50')

            # If build info was not given and explicitly it was requested to
            # get the release version from image archive search, then
            # do it so.
            if value == None and get_release_from_image_archive:
                board = host.servo.get_board()
                value = host.get_latest_release_version(board)

            host.firmware_install(build=value, rw_only=rw_only,
                                  dest=self.resultsdir)
        except Exception as e:
            logging.error(e)
            raise error.TestFail, str(e), sys.exc_info()[2]
        finally:
            if orig_act_dev != None:
                host.servo.set_nocheck('active_v4_device', orig_act_dev)

        # DUT reboots after the above firmware_install(). Wait it to boot.
        host.test_wait_for_boot()

        # Only care about the version number.
        firmware_ver = value.rsplit('-', 1)[1]
        if not rw_only:
            current_ro_ver = self.get_ro_firmware_ver(host)
            if current_ro_ver != firmware_ver:
                raise error.TestFail('Failed to update RO, still version %s' %
                                     current_ro_ver)
        current_rw_ver = self.get_rw_firmware_ver(host)
        if current_rw_ver != firmware_ver:
            raise error.TestFail('Failed to update RW, still version %s' %
                                 current_rw_ver)
