# Copyright (c) 2019 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This file provides core logic for labstation verify/repair process."""

import logging

from autotest_lib.client.common_lib import error
from autotest_lib.server.hosts import base_label
from autotest_lib.server.hosts import cros_label
from autotest_lib.server.cros import autoupdater
from autotest_lib.server.hosts import labstation_repair
from autotest_lib.server.hosts import base_servohost


class LabstationHost(base_servohost.BaseServoHost):
    """Labstation specific host class"""

    # Threshold we decide to ignore a in_use file lock. In minutes
    IN_USE_FILE_EXPIRE_MINS = 120

    # Uptime threshold to perform a labstation reboot, this is to prevent a
    # broken DUT keep trying to reboot a labstation. In hours
    UP_TIME_THRESH_HOLD_HOURS = 24

    @staticmethod
    def check_host(host, timeout=10):
        """
        Check if the given host is a labstation host.

        @param host: An ssh host representing a device.
        @param timeout: The timeout for the run command.

        @return: True if the host device is labstation.

        @raises AutoservRunError: If the command failed.
        @raises AutoservSSHTimeout: Ssh connection has timed out.

        """
        try:
            result = host.run(
                'grep -q labstation /etc/lsb-release',
                ignore_status=True, timeout=timeout)
        except (error.AutoservRunError, error.AutoservSSHTimeout):
            return False
        return result.exit_status == 0


    def _initialize(self, hostname, *args, **dargs):
        super(LabstationHost, self)._initialize(hostname=hostname,
                                                *args, **dargs)
        self._repair_strategy = (
            labstation_repair.create_labstation_repair_strategy())
        self.labels = base_label.LabelRetriever(cros_label.LABSTATION_LABELS)


    def is_reboot_requested(self):
        """Check if a reboot is requested for this labstation, the reboot can
        either be requested from labstation or DUTs. For request from DUTs we
        only process it if uptime longer than a threshold because we want
        to prevent a broken servo keep its labstation in reboot cycle.

        @returns True if a reboot is required, otherwise False
        """
        if self._check_update_status() == autoupdater.UPDATER_NEED_REBOOT:
            logging.info('Labstation reboot requested from labstation for'
                         ' update image')
            return True

        if not self._validate_uptime():
            logging.info('Ignoring DUTs reboot request because %s was'
                         ' rebooted in last 24 hours.', self.hostname)
            return False

        cmd = 'find %s*%s' % (self.TEMP_FILE_DIR, self.REBOOT_FILE_POSTFIX)
        output = self.run(cmd, ignore_status=True).stdout
        if output:
            in_use_file_list = output.strip().split('\n')
            logging.info('%s DUT(s) are currently requesting to'
                         ' reboot labstation.', len(in_use_file_list))
            return True
        else:
            return False


    def try_reboot(self):
        """Try to reboot the labstation if it's safe to do(no servo in use,
         and not processing updates), and cleanup reboot control file.
        """
        if (self._is_servo_in_use() or self._check_update_status()
            in autoupdater.UPDATER_PROCESSING_UPDATE):
            logging.info('Aborting reboot action because some DUT(s) are'
                         ' currently using servo(s) or'
                         ' labstation update is in processing.')
            return
        self._servo_host_reboot()
        logging.info('Cleaning up reboot control files.')
        self._cleanup_post_reboot()


    def get_labels(self):
        """Return the detected labels on the host."""
        return self.labels.get_labels(self)


    def get_os_type(self):
        return 'labstation'


    def repair(self):
        """Attempt to repair a labstation.
        """
        message = 'Beginning repair for host %s board %s model %s'
        info = self.host_info_store.get()
        message %= (self.hostname, info.board, info.model)
        self.record('INFO', None, None, message)
        self._repair_strategy.repair(self)


    def _validate_uptime(self):
        return (float(self.check_uptime()) >
                self.UP_TIME_THRESH_HOLD_HOURS * 3600)


    def _is_servo_in_use(self):
        """Determine if there are any DUTs currently running task that uses
         servo, only files that has been touched within pre-set threshold of
          minutes counts.

        @returns True if any DUTs is using servos, otherwise False.
        """
        cmd = 'find %s*%s -mmin -%s' % (self.TEMP_FILE_DIR,
                                        self.LOCK_FILE_POSTFIX,
                                        self.IN_USE_FILE_EXPIRE_MINS)
        result = self.run(cmd, ignore_status=True)
        return bool(result.stdout)


    def _cleanup_post_reboot(self):
        """Clean up all xxxx_reboot file after reboot."""
        cmd = 'rm %s*%s' % (self.TEMP_FILE_DIR, self.REBOOT_FILE_POSTFIX)
        self.run(cmd, ignore_status=True)
