# Copyright 2019 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


""" The autotest performing Cr50 update to the TOT image."""


import logging
import os
import re

from autotest_lib.client.common_lib.cros import cr50_utils, dev_server
from autotest_lib.server.cros import filesystem_util, gsutil_wrapper
from autotest_lib.server.cros.faft.firmware_test import FirmwareTest


# TOT cr50 images are built as part of the reef image builder.
BUILDER = 'reef'
GS_URL = 'gs://chromeos-releases/dev-channel/' + BUILDER
# Firmware artifacts are stored in files like this.
#   ChromeOS-firmware-R79-12519.0.0-reef.tar.bz2
FIRMWARE_NAME = 'ChromeOS-firmware-%s-%s.tar.bz2'
REMOTE_TMPDIR = '/tmp/cr50_tot_update'
CR50_IMAGE_PATH = 'cr50/ec.bin'
# Wait 10 seconds for the update to take effect.
WAIT_FOR_UPDATE = 10

class provision_Cr50TOT(FirmwareTest):
    """Update cr50 to TOT.

    The reef builder builds cr50. Fetch the image from the latest reef build
    and update cr50 to that image. This expects that the DUT is running node
    locked RO.
    """
    version = 1

    def get_latest_cr50_build(self):
        """Download the TOT cr50 image from the reef artifacts."""
        self.host.run('mkdir -p %s' % (REMOTE_TMPDIR))

        latest_ver = dev_server.ImageServer.get_latest_build('reef-release')
        bucket = os.path.join(GS_URL, latest_ver.split('-')[-1])
        filename = FIRMWARE_NAME % (latest_ver, BUILDER)
        logging.info('Using cr50 image from %s', latest_ver)

        # Download the firmware artifacts from google storage.
        gsutil_wrapper.copy_private_bucket(host=self.host,
                                           bucket=bucket,
                                           filename=filename,
                                           destination=REMOTE_TMPDIR)

        # Extract the cr50 image.
        dut_path = os.path.join(REMOTE_TMPDIR, filename)
        result = self.host.run('tar xfv %s -C %s' % (dut_path, REMOTE_TMPDIR))
        return os.path.join(REMOTE_TMPDIR, CR50_IMAGE_PATH)


    def get_bin_version(self, dut_path):
        """Get the cr50 version from the image."""
        find_ver_cmd = 'grep -a cr50_v.*tpm2 %s' % dut_path
        version_output = self.host.run(find_ver_cmd).stdout.strip()
        return re.findall('cr50_v\S+\s', version_output)[0].strip()


    def run_once(self, host, force=False):
        """Update cr50 to the TOT image from the reef builder."""
        # TODO(mruthven): remove once the test is successfully scheduled.
        logging.info('SUCCESSFULLY SCHEDULED PROVISION CR50 TOT UPDATE')
        if not force:
            logging.info('skipping update')
            return
        logging.info('cr50 version %s', host.servo.get('cr50_version'))
        self.host = host
        cr50_path = self.get_latest_cr50_build()
        logging.info('cr50 image is at %s', cr50_path)
        local_path = os.path.join(self.resultsdir, 'cr50.bin.tot')
        self.host.get_file(cr50_path, local_path)
        expected_version = self.get_bin_version(cr50_path)

        cr50_utils.GSCTool(self.host, ['-a', cr50_path])

        self.cr50.wait_for_reboot(timeout=WAIT_FOR_UPDATE)
        cr50_version = self.cr50.get_active_version_info()[3].split('/')[-1]
        logging.info('Cr50 running %s. Expected %s', cr50_version,
                     expected_version)
        # TODO(mruthven): Decide if failing to update should be a provisioning
        # failure. Raising a failure will prevent the suite from running. See
        # how often it fails and why.
        if cr50_version.split('/')[-1] != expected_version:
            logging.info('Unable to udpate Cr50.')
        filesystem_util.make_rootfs_writable(self.host)
        cr50_utils.InstallImage(self.host, local_path, cr50_utils.CR50_PREPVT)
